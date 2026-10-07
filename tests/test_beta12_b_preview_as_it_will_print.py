"""Beta 12: the chart preview shows the sheet as it will print.

Knut, #182 6045500910 answer 4: *"preview should always look as paper would
look printed, assuming normal printing path, as Sebastian said."* Basti,
6045468325: once the print route is set for a verification run, show the
soft-proofed version, with a small indicator saying what the preview shows.

`workflow/print_preview.py` decides the printing path of one page and renders
it; `TiffPreview.set_print_preview` (Create Chart, Print Chart, Measure) shows
it with the M-PREVIEW-AS-PRINTED indicator. Nothing printed changes.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from workflow import print_preview as PP
from workflow import verification_print as vp

DATA = Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
NAME = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26"


def _tiff(path: Path, rgb=((255, 255, 255), (200, 40, 40), (30, 30, 30))) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    px = np.array([list(rgb)], dtype=np.uint8)
    px = np.repeat(np.repeat(px, 8, axis=0), 8, axis=1)
    Image.fromarray(px, "RGB").save(path)
    return path


def _project(tmp_path, *, profile=True, verification=False, gamut=False,
             record: "dict | None" = None, stored: "dict | None" = None):
    run = tmp_path / NAME / "runs" / "run1"
    run.mkdir(parents=True)
    (run / "meta.json").write_text("{}", encoding="utf-8")
    if profile:
        shutil.copy2(DATA / f"{NAME}.icc", run / f"{NAME}.icc")
    if not verification:
        (run / f"{NAME}.ti2").write_text("CTI2\n", encoding="utf-8")
        return _tiff(run / f"{NAME}.tif")
    v = run / "verifications"
    v.mkdir()
    shutil.copy2(DATA / f"{NAME}-verify.ti2", v / f"{NAME}-verify.ti2")
    if gamut:
        (v / f"{NAME}-verify-reference.ti3").write_text("CTI3\n", encoding="utf-8")
    meta = {"print_settings": stored or {}}
    (v / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    tif = _tiff(v / f"{NAME}-verify.tif")
    if record is not None:
        (v / f"{NAME}-verify.print.json").write_text(json.dumps(record),
                                                     encoding="utf-8")
    return tif


def _record(colour, *, when=None, intent="relative"):
    when = when or (datetime.now() + timedelta(minutes=5))
    return {"printed_at": when.isoformat(timespec="seconds"), "colour": colour,
            "intent": intent if colour == vp.COLOUR_THROUGH else "",
            "route": "chromiq", "source_profile": "/nowhere/sRGB.icm"}


# ---------------------------------------------------------------- the plan
def test_a_page_outside_a_run_has_no_plan(tmp_path):
    assert PP.plan_for_page(_tiff(tmp_path / "loose" / "chart.tif")) is None
    assert PP.plan_for_page(_tiff(tmp_path / "proj" / "cal" / "x-cal.tif")) is None


def test_a_profiling_chart_without_a_profile_shows_device_values(tmp_path):
    plan = PP.plan_for_page(_project(tmp_path, profile=False))
    assert plan.kind == PP.KIND_DEVICE and plan.why == PP.WHY_NO_PROFILE


def test_a_profiling_chart_with_a_profile_is_shown_through_it(tmp_path):
    plan = PP.plan_for_page(_project(tmp_path))
    assert plan.kind == PP.KIND_RAW and plan.profile.name == f"{NAME}.icc"


def test_a_page_with_calibrated_pixels_is_not_soft_proofed(tmp_path, monkeypatch):
    from workflow import printer_calibration as pc
    monkeypatch.setattr(pc, "calibration_mode_of", lambda *a, **k: pc.MODE_APPLY)
    plan = PP.plan_for_page(_project(tmp_path))
    assert plan.kind == PP.KIND_DEVICE and plan.why == PP.WHY_CALIBRATED


def test_a_from_profile_gamut_chart_is_always_raw(tmp_path):
    tif = _project(tmp_path, verification=True, gamut=True,
                   stored={"colour": vp.COLOUR_THROUGH})
    plan = PP.plan_for_page(tif, selected_colour=vp.COLOUR_THROUGH)
    assert plan.kind == PP.KIND_RAW


def test_the_print_record_decides_after_printing(tmp_path):
    tif = _project(tmp_path, verification=True,
                   record=_record(vp.COLOUR_THROUGH, intent="perceptual"),
                   stored={"colour": vp.COLOUR_RAW})
    plan = PP.plan_for_page(tif)
    assert plan.kind == PP.KIND_THROUGH and plan.printed
    assert plan.intent == "perceptual"
    assert plan.source_profile == "/nowhere/sRGB.icm"


def test_a_record_older_than_the_page_is_not_used(tmp_path):
    old = datetime.now() - timedelta(days=2)
    tif = _project(tmp_path, verification=True,
                   record=_record(vp.COLOUR_THROUGH, when=old),
                   stored={"colour": vp.COLOUR_RAW})
    plan = PP.plan_for_page(tif)
    assert plan.kind == PP.KIND_RAW and not plan.printed


def test_before_printing_the_stored_choice_decides(tmp_path):
    tif = _project(tmp_path, verification=True,
                   stored={"colour": vp.COLOUR_THROUGH, "intent": "absolute"})
    plan = PP.plan_for_page(tif)
    assert plan.kind == PP.KIND_THROUGH and plan.intent == "absolute"
    assert not plan.printed


def test_with_nothing_stored_the_print_tabs_default_decides(tmp_path):
    tif = _project(tmp_path, verification=True)
    # a run with no verification history defaults to "through the profile"
    assert PP.plan_for_page(tif).kind == PP.KIND_THROUGH


def test_the_print_tabs_live_choice_outranks_the_record(tmp_path):
    tif = _project(tmp_path, verification=True,
                   record=_record(vp.COLOUR_THROUGH))
    plan = PP.plan_for_page(tif, selected_colour=vp.COLOUR_RAW)
    assert plan.kind == PP.KIND_RAW


def test_a_dated_verifications_own_chart_snapshot(tmp_path):
    tif = _project(tmp_path, verification=True)
    day = tif.parent / "2026-10-06_154750" / "chart"
    day.mkdir(parents=True)
    shutil.copy2(tif.with_suffix(".ti2"), day / f"{NAME}-verify.ti2")
    snap = _tiff(day / f"{NAME}-verify.tif")
    (day / f"{NAME}-verify.print.json").write_text(
        json.dumps(_record(vp.COLOUR_RAW)), encoding="utf-8")
    plan = PP.plan_for_page(snap)
    assert plan.kind == PP.KIND_RAW and plan.printed


# ------------------------------------------------------- the render, cached
class _FakeCctiff:
    def __init__(self, ok=True):
        self.calls: "list[list[str]]" = []
        self.ok = ok

    def __call__(self, cmd, **kw):
        assert kw.get("timeout"), "every ArgyllCMS call needs a timeout"
        self.calls.append([str(c) for c in cmd])
        if self.ok:
            shutil.copy2(cmd[-2], cmd[-1])
        return subprocess.CompletedProcess(cmd, 0 if self.ok else 1, "", "")


@pytest.fixture()
def fake_bin(tmp_path):
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    from core.resource_path import argyll_binary
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    PP.clear_cache()
    yield b
    PP.clear_cache()


def test_a_page_is_soft_proofed_once(tmp_path, fake_bin):
    tif = _project(tmp_path)
    plan = PP.plan_for_page(tif)
    run = _FakeCctiff()
    a = PP.softproof_page(tif, plan, fake_bin, runner=run)
    b = PP.softproof_page(tif, plan, fake_bin, runner=run)
    assert a == b and a.is_file()
    assert len(run.calls) == 1                       # cached
    cmd = run.calls[0]
    # the run's profile as the input, relative colorimetric to sRGB
    assert cmd[cmd.index(str(plan.profile)) - 1] == "r"
    assert cmd[-3].endswith("sRGB.icm")


def test_a_through_page_is_converted_exactly_as_the_print_converts_it(
        tmp_path, fake_bin):
    tif = _project(tmp_path, verification=True,
                   stored={"colour": vp.COLOUR_THROUGH, "intent": "perceptual"})
    src = fake_bin.parent / "ref" / "sRGB.icm"
    plan = PP.plan_for_page(tif, bin_dir=fake_bin)
    assert plan.source_profile == str(src)
    run = _FakeCctiff()
    assert PP.softproof_page(tif, plan, fake_bin, runner=run) is not None
    assert len(run.calls) == 2
    from workflow.cctiff_apply import convert_args
    first = run.calls[0]
    expected = convert_args(src, plan.profile, tif, Path(first[-1]),
                            verbose=False, intent="p")
    assert first[1:] == [str(x) for x in expected]


def test_a_failed_render_is_remembered_and_shows_device_values(tmp_path, fake_bin):
    tif = _project(tmp_path)
    plan = PP.plan_for_page(tif)
    run = _FakeCctiff(ok=False)
    assert PP.softproof_page(tif, plan, fake_bin, runner=run) is None
    assert PP.softproof_page(tif, plan, fake_bin, runner=run) is None
    assert len(run.calls) == 1


def test_a_new_profile_renders_again(tmp_path, fake_bin):
    tif = _project(tmp_path)
    plan = PP.plan_for_page(tif)
    run = _FakeCctiff()
    PP.softproof_page(tif, plan, fake_bin, runner=run)
    st = plan.profile.stat()
    os.utime(plan.profile, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    PP.softproof_page(tif, plan, fake_bin, runner=run)
    assert len(run.calls) == 2


# ---------------------------------------------------- the preview's indicator
@pytest.fixture()
def preview(qapp):
    from ui.tiff_preview import TiffPreview
    w = TiffPreview(None)
    yield w
    w.deleteLater()


def test_the_preview_shows_the_soft_proof_and_says_so(tmp_path, preview,
                                                       fake_bin, monkeypatch):
    from ui.tiff_preview import TiffPreview
    tif = _project(tmp_path)
    out = tmp_path / "proof.tif"
    _tiff(out, rgb=((250, 250, 250), (150, 30, 30), (40, 40, 40)))
    monkeypatch.setattr(TiffPreview, "_argyll_bin_with", staticmethod(lambda t: fake_bin))
    monkeypatch.setattr(PP, "softproof_page", lambda *a, **k: out)
    preview.set_print_preview(True)
    assert preview._as_it_will_print(tif) == out
    text, tip = preview.print_preview_badge()
    assert text == "As on paper, via the run's profile"
    assert f"{NAME}.icc" in tip


def test_the_indicator_says_device_values_before_a_profile(tmp_path, preview):
    tif = _project(tmp_path, profile=False)
    preview.set_print_preview(True)
    assert preview._as_it_will_print(tif) == tif
    assert preview.print_preview_badge()[0] == "Device values, no profile yet"


def test_the_indicator_says_when_the_profile_could_not_be_applied(
        tmp_path, preview, fake_bin, monkeypatch):
    from ui.tiff_preview import TiffPreview
    tif = _project(tmp_path)
    monkeypatch.setattr(TiffPreview, "_argyll_bin_with", staticmethod(lambda t: fake_bin))
    monkeypatch.setattr(PP, "softproof_page", lambda *a, **k: None)
    preview.set_print_preview(True)
    assert preview._as_it_will_print(tif) == tif
    assert preview.print_preview_badge()[0] == "Device values, profile not applied"


def test_off_by_default_and_never_outside_a_run(tmp_path, preview):
    tif = _project(tmp_path)
    assert preview._as_it_will_print(tif) == tif          # not asked for
    assert preview.print_preview_badge() == ("", "")
    preview.set_print_preview(True)
    loose = _tiff(tmp_path / "elsewhere" / "chart.tif")
    assert preview._as_it_will_print(loose) == loose
    assert preview.print_preview_badge() == ("", "")


def test_the_three_tabs_ask_for_it_and_the_print_tab_passes_its_choice():
    import inspect
    from ui.tabs import tab_chart, tab_measure, tab_print
    for mod in (tab_chart, tab_measure, tab_print):
        assert "self._preview.set_print_preview(True)" in inspect.getsource(mod)
    src = inspect.getsource(tab_print.TabPrint._update_colour_row_visible)
    assert "colour=self._cm_selected_colour()" in src


# ------------------------------------------------------- real ArgyllCMS
def _bin():
    from tests.argyll_env import argyll_bin_dir
    b = argyll_bin_dir()
    if b is None or not (b.parent / "ref" / "sRGB.icm").is_file():
        return None
    return b


@pytest.mark.skipif(_bin() is None, reason="needs ArgyllCMS with ref/sRGB.icm")
def test_real_cctiff_renders_the_page_and_never_touches_it(tmp_path):
    PP.clear_cache()
    tif = _project(tmp_path)
    before = hashlib.sha256(tif.read_bytes()).hexdigest()
    plan = PP.plan_for_page(tif, bin_dir=_bin())
    out = PP.softproof_page(tif, plan, _bin())
    assert out is not None and out != tif
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == before   # nothing printed changes
    a = np.asarray(Image.open(tif).convert("RGB"), dtype=float)
    b = np.asarray(Image.open(out).convert("RGB"), dtype=float)
    assert a.shape == b.shape
    # paper stays the screen's white (relative), the red patch is shown
    # as the printer prints it, not as its device value reads as screen RGB
    assert b[0, 0].min() >= 250
    assert np.abs(b[0, 12] - a[0, 12]).max() > 10       # the red patch moves
    PP.clear_cache()
