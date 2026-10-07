"""Beta-12 review of build B: what the review found in the preview-as-printed
and the preset certificates, each pinned here.

1. The Print Chart tab's Rendering intent never reached the preview: only the
   Colour radios refreshed it, so a verification printed through the profile
   was shown in the intent it had when the tab opened.
2. Every profile rebuild or Generate left the previous page renders in the
   temporary folder until ChromIQ quit (3 to 8 MB a page).
3. A user preset judged while printtarg was missing, refusing, or too slow was
   CERTIFIED with that answer, and kept it after ArgyllCMS was fixed.
4. A certificate store whose ``"certificates"`` is not a mapping raised out of
   `lookup`, which promises never to raise, and so out of the presets window.
5. The shipped certificates were only checked for being PRESENT for this
   version; a judging change after the version bump went unnoticed except for
   one preset in 25. The release gate now works every one out again.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from workflow import measurement_report as MR
from workflow import preset_certificates as PC
from workflow import preset_eligibility as PE
from workflow import print_preview as PP

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
NAME = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26"


# ------------------------------------------------ 1. the intent reaches it
def test_the_intent_combo_is_wired_to_the_preview():
    import inspect
    from ui.tabs.tab_print import TabPrint
    src = inspect.getsource(TabPrint)
    assert ("self._cm_intent_combo.currentIndexChanged.connect(\n"
            "            self._on_cm_intent_changed)") in src


class _Combo:
    def __init__(self, v):
        self.v = v

    def currentData(self):
        return self.v


class _Radio:
    def __init__(self, on):
        self.on = on

    def isChecked(self):
        return self.on

    def isEnabled(self):
        return True


def _fake_tab(intent, *, verification=True):
    from ui.tabs.tab_print import TabPrint
    calls = []
    target = SimpleNamespace(is_verification=lambda: verification)
    tab = SimpleNamespace(
        _updating_cm=False, _tiff_pages=[Path("p.tif")],
        _target_ctl=SimpleNamespace(target=target),
        _cm_through_rb=_Radio(True), _cm_intent_combo=_Combo(intent),
        _preview=SimpleNamespace(
            set_print_preview=lambda on, **kw: calls.append((on, kw))))
    tab._cm_selected_colour = lambda: TabPrint._cm_selected_colour(tab)
    tab._cm_selected_intent = lambda: TabPrint._cm_selected_intent(tab)
    return TabPrint, tab, calls


def test_a_new_intent_is_shown_at_once():
    from workflow import verification_print as vp
    TabPrint, tab, calls = _fake_tab("perceptual")
    TabPrint._on_cm_intent_changed(tab)
    assert calls == [(True, {"colour": vp.COLOUR_THROUGH,
                             "intent": "perceptual"})]


def test_an_intent_set_while_loading_or_off_a_verification_does_nothing():
    TabPrint, tab, calls = _fake_tab("absolute")
    tab._updating_cm = True                     # load_target_settings
    TabPrint._on_cm_intent_changed(tab)
    TabPrint, tab2, calls2 = _fake_tab("absolute", verification=False)
    TabPrint._on_cm_intent_changed(tab2)
    assert calls == [] and calls2 == []


# ----------------------------------------- 2. superseded renders are deleted
@pytest.fixture()
def fake_bin(tmp_path):
    from core.resource_path import argyll_binary
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    PP.clear_cache()
    yield b
    PP.clear_cache()


def _copying_runner(cmd, **kw):
    assert kw.get("timeout")
    shutil.copy2(cmd[-2], cmd[-1])
    return subprocess.CompletedProcess(cmd, 0, "", "")


def _profiling_page(tmp_path) -> Path:
    run = tmp_path / NAME / "runs" / "run1"
    run.mkdir(parents=True)
    shutil.copy2(DATA / f"{NAME}.icc", run / f"{NAME}.icc")
    (run / f"{NAME}.ti2").write_text("CTI2\n", encoding="utf-8")
    tif = run / f"{NAME}.tif"
    Image.fromarray(np.full((8, 8, 3), 200, np.uint8), "RGB").save(tif)
    return tif


def _bump(p: Path):
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))


def test_a_rebuilt_profile_or_page_deletes_the_render_it_replaces(
        tmp_path, fake_bin):
    tif = _profiling_page(tmp_path)
    plan = PP.plan_for_page(tif)
    first = PP.softproof_page(tif, plan, fake_bin, runner=_copying_runner)
    _bump(plan.profile)                                  # profile rebuilt
    second = PP.softproof_page(tif, plan, fake_bin, runner=_copying_runner)
    assert second != first and second.is_file()
    assert not first.exists(), "the old profile's render was left on disk"
    _bump(tif)                                           # chart generated again
    third = PP.softproof_page(tif, plan, fake_bin, runner=_copying_runner)
    assert third.is_file() and not second.exists()
    assert len(PP._cache) == 1


def test_another_way_of_showing_the_same_page_is_kept(tmp_path, fake_bin):
    """Toggling Raw / Through in the Print tab must not throw away the other
    render: both are current."""
    tif = _profiling_page(tmp_path)
    plan = PP.plan_for_page(tif)
    a = PP.softproof_page(tif, plan, fake_bin, runner=_copying_runner)
    other = PP.PreviewPlan(PP.KIND_RAW, profile=plan.profile, intent="x")
    b = PP.softproof_page(tif, other, fake_bin, runner=_copying_runner)
    assert a.is_file() and b.is_file() and a != b


# ------------------------------------- 3. a tool's bad moment is not certified
def _user_preset(name="Review preset") -> Path:
    from core.platform_paths import presets_dir
    ti1 = next((ROOT / "assets" / "charts" / "knut" / "rgb").rglob("chart.ti1"))
    dst = presets_dir() / "create_chart" / f"{name}.ti1"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ti1, dst)
    return dst


@pytest.fixture()
def clean_user_store(preset_certificates):
    p = PC.user_store_path()
    if p.exists():
        p.unlink()
    PC.reset()
    yield p
    if p.exists():
        p.unlink()
    PC.reset()


@pytest.mark.parametrize("reason", sorted(PE._NOT_CERTIFIABLE))
def test_an_answer_about_the_tools_is_never_certified(
        qapp, clean_user_store, monkeypatch, reason):
    chart = _user_preset()
    PE.clear_cache()
    monkeypatch.setattr(MR, "row_values", lambda rep: {
        "all_de00_avg": {"value": 1.0, "reason": None},
        "uniformity_sd": {"value": None, "reason": reason}})
    monkeypatch.setattr(PE, "_perfect_print", lambda *a, **k: {})
    PE.chart_row_values(chart, None)
    assert PC.lookup(chart, None) is None
    assert not clean_user_store.exists() or not json.loads(
        clean_user_store.read_text(encoding="utf-8"))["certificates"]


def test_a_full_answer_is_still_certified(qapp, clean_user_store, monkeypatch):
    """MUTATION guard for the test above: the same path with a real reason
    does write a certificate."""
    chart = _user_preset()
    PE.clear_cache()
    monkeypatch.setattr(MR, "row_values", lambda rep: {
        "all_de00_avg": {"value": 1.0, "reason": None},
        "uniformity_sd": {"value": None, "reason": "evenness_grid_too_small"}})
    monkeypatch.setattr(PE, "_perfect_print", lambda *a, **k: {})
    PE.chart_row_values(chart, None)
    assert PC.lookup(chart, None) is not None


# --------------------------------------------- 4. a malformed store is empty
@pytest.mark.parametrize("text", [
    '{"certificates": []}', '{"certificates": "x"}', '[1, 2]', '{"cert',
    '{"code_version": "%s", "certificates": [1]}'])
def test_a_malformed_store_is_read_as_empty(qapp, clean_user_store, text):
    chart = _user_preset()
    clean_user_store.parent.mkdir(parents=True, exist_ok=True)
    clean_user_store.write_text(text.replace("%s", PC.code_version()),
                                encoding="utf-8")
    PC.reset()
    assert PC.lookup(chart, None) is None                  # no raise
    assert PC.forget(chart) == 0
    assert PC.keep_only([chart]) == 0
    assert PC.record(chart, None, {"x": {"value": 1.0, "reason": None}})
    assert PC.lookup(chart, None) == {"x": {"value": 1.0, "reason": None}}


def test_a_malformed_shipped_file_is_read_as_empty(monkeypatch, tmp_path,
                                                   preset_certificates):
    bad = tmp_path / "preset_certificates.json"
    bad.write_text(json.dumps({"code_version": PC.code_version(),
                               "certificates": ["not", "a", "mapping"]}),
                   encoding="utf-8")
    import core.resource_path as rp
    monkeypatch.setattr(rp, "resource_path", lambda rel: bad)
    PC.reset()
    chart = tmp_path / "c.ti1"
    shutil.copy2(next((ROOT / "assets" / "charts" / "knut" / "rgb")
                      .rglob("chart.ti1")), chart)
    assert PC.lookup(chart, None) is None
    PC.reset()


# ----------------------------- 5. the shipped answers are today's answers
@pytest.mark.slow
def test_the_shipped_certificates_are_what_this_chromiq_works_out():
    """Every built-in preset worked out again, both values of the one setting
    a built-in recipe reads, and compared with the shipped file. A judging
    change made after the version bump fails HERE, in the release gate:
    run `python scripts/make_preset_certificates.py` and commit the file."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("CHROMIQ_SETTINGS_FILE", "CHROMIQ_PRESETS_DIR")}
    env["QT_QPA_PLATFORM"] = "offscreen"
    try:
        r = subprocess.run([sys.executable,
                            str(ROOT / "scripts" / "make_preset_certificates.py"),
                            "--check"], cwd=ROOT, env=env, capture_output=True,
                           text=True, encoding="utf-8", timeout=900)
    except subprocess.TimeoutExpired:
        pytest.fail("make_preset_certificates.py --check did not finish in "
                    "15 minutes on the loaded machine")
    assert r.returncode == 0, (r.stdout + r.stderr)[-2000:]
