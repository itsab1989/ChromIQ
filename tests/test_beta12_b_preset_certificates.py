"""Beta 12: preset metric certificates (Knut, #182 6045500910, answer 5).

A certificate is the answer `preset_eligibility.chart_row_values` gives for a
preset's chart, keyed by the preset's hash and the ChromIQ that judged it.
Built-in presets ship theirs (`data/preset_certificates.json`, written at
release time by `scripts/make_preset_certificates.py`); a user's own preset
gets one the first time it is checked, in the user's app data. The presets
window and the run-type check read the certificate first and lay a chart out
only without a valid one. A stale certificate is never used.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from workflow import measurement_report as MR
from workflow import preset_certificates as PC
from workflow import preset_eligibility as PE

ROOT = Path(__file__).resolve().parents[1]
SHIPPED = ROOT / "data" / "preset_certificates.json"


@pytest.fixture()
def rows(qapp):
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    PE.clear_cache()
    yield verification_preset_rows(AppSettings())
    PE.clear_cache()


def _no_judging(monkeypatch):
    """Make any attempt to work a chart out fail loudly."""
    def boom(*a, **k):
        raise AssertionError("a chart was worked out although a valid "
                             "certificate exists")
    monkeypatch.setattr(MR, "row_values", boom)


# --------------------------------------------------------- the shipped file
def test_every_built_in_preset_ships_a_valid_certificate(rows, preset_certificates):
    """FAILS AT A VERSION BUMP OR A CHANGED BUILT-IN PRESET, ON PURPOSE: run
    `python scripts/make_preset_certificates.py` and commit the file."""
    data = json.loads(SHIPPED.read_text(encoding="utf-8"))
    assert data["code_version"] == PC.code_version(), (
        "data/preset_certificates.json was written by another ChromIQ "
        f"({data['code_version']}, this is {PC.code_version()}): run "
        "python scripts/make_preset_certificates.py")
    missing = [r.key for r in rows if r.builtin and r.chart is not None
               and PC.preset_hash(r.chart, r.recipe) not in data["certificates"]]
    assert not missing, ("built-in presets without a certificate (run "
                         f"python scripts/make_preset_certificates.py): {missing[:5]}")


def test_the_shipped_file_names_no_home_folder():
    text = SHIPPED.read_text(encoding="utf-8")
    for marker in ("/Users/", "/home/", "C:\\\\Users", "C:/Users"):
        assert marker not in text


def test_a_certificate_says_what_working_it_out_says(rows, preset_certificates):
    """The certificate is the answer, not an approximation of it."""
    sample = [r for r in rows if r.builtin and r.chart is not None][::25]
    assert sample
    for r in sample:
        cert = PC.lookup(r.chart, r.recipe)
        assert cert is not None, r.key
        PC.set_disabled(True)
        PE.clear_cache()
        fresh = json.loads(json.dumps(
            PE.chart_row_values(r.chart, r.recipe, lay_out=True)))
        PC.set_disabled(False)
        assert cert == fresh, r.key


def test_the_window_reads_the_certificate_and_works_nothing_out(
        rows, preset_certificates, monkeypatch):
    r = next(r for r in rows if r.builtin and r.chart is not None)
    PE.clear_cache()
    _no_judging(monkeypatch)
    assert PE.values_ready(r.chart, r.recipe)            # no "working" row
    a = PE.assess_any(r.chart, None, recipe=r.recipe)
    assert a.checked and a.answered


# ------------------------------------------------- a stale one is never used
def test_another_chromiq_s_certificate_is_never_used(rows, preset_certificates,
                                                     monkeypatch):
    r = next(r for r in rows if r.builtin and r.chart is not None)
    assert PC.lookup(r.chart, r.recipe) is not None
    monkeypatch.setattr(PC, "code_version", lambda: "9.9.9/cert1")
    assert PC.lookup(r.chart, r.recipe) is None
    PE.clear_cache()
    _no_judging(monkeypatch)
    with pytest.raises(AssertionError, match="worked out"):
        PE.chart_row_values(r.chart, r.recipe)          # it is worked out


def test_a_changed_preset_is_never_served_its_old_certificate(
        rows, preset_certificates, tmp_path):
    r = next(r for r in rows if r.builtin and r.chart is not None)
    copy = tmp_path / r.chart.name
    shutil.copy2(r.chart, copy)
    assert PC.lookup(copy, r.recipe) is not None        # same content: valid
    copy.write_text(copy.read_text(encoding="utf-8") + "\n# changed\n",
                    encoding="utf-8")
    assert PC.lookup(copy, r.recipe) is None             # changed chart
    shutil.copy2(r.chart, copy)
    other = dict(r.recipe or {}, dpi=123456)
    assert PC.lookup(copy, other) is None                # changed layout


# ---------------------------------------------------- the user's own presets
def _user_preset(name="My verify 616") -> Path:
    from core.platform_paths import presets_dir
    src = ROOT / "assets" / "charts" / "knut" / "rgb"
    ti1 = next(src.rglob("chart.ti1"))
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


def test_a_user_preset_is_certified_once_and_read_after(
        qapp, clean_user_store, monkeypatch):
    chart = _user_preset()
    PE.clear_cache()
    first = PE.chart_row_values(chart, None)
    store = json.loads(clean_user_store.read_text(encoding="utf-8"))
    (cert,) = store["certificates"].values()
    assert cert["preset"] == chart.stem
    assert cert["code_version"] == PC.code_version()
    # a new session reads it and works nothing out
    PC.reset()
    PE.clear_cache()
    _no_judging(monkeypatch)
    assert PE.chart_row_values(chart, None) == json.loads(json.dumps(first))
    assert str(clean_user_store).find(str(ROOT)) != 0, \
        "the user's certificates must never be written into the repository"


def test_a_changed_user_preset_replaces_its_certificate(qapp, clean_user_store):
    chart = _user_preset()
    PE.clear_cache()
    PE.chart_row_values(chart, None)
    PE.clear_cache()
    PE.chart_row_values(chart, {"dpi": 150})             # its layout changed
    store = json.loads(clean_user_store.read_text(encoding="utf-8"))
    assert len(store["certificates"]) == 1               # replaced, not added
    assert PC.lookup(chart, {"dpi": 150}) is not None
    assert PC.lookup(chart, None) is None


def test_a_stale_user_certificate_is_never_used(qapp, clean_user_store,
                                                monkeypatch):
    chart = _user_preset()
    PE.clear_cache()
    PE.chart_row_values(chart, None)
    monkeypatch.setattr(PC, "code_version", lambda: "0.0.1/cert1")
    assert PC.lookup(chart, None) is None


def test_a_deleted_user_preset_loses_its_certificate(qapp, clean_user_store):
    a, b = _user_preset("Keep me"), _user_preset("Delete me")
    PE.clear_cache()
    PE.chart_row_values(a, None)
    PE.chart_row_values(b, {"dpi": 150})
    assert PC.forget(b) == 1
    assert PC.lookup(b, {"dpi": 150}) is None and PC.lookup(a, None) is not None
    # and one removed outside ChromIQ is tidied when the window lists presets
    assert PC.keep_only([]) == 1
    assert PC.lookup(a, None) is None


def test_a_run_chart_is_not_certified(qapp, clean_user_store, tmp_path):
    """Only a user preset's own patch set gets a certificate: the current
    chart of a run changes with every Generate."""
    chart = tmp_path / "proj" / "runs" / "run1" / "x.ti1"
    chart.parent.mkdir(parents=True)
    shutil.copy2(_user_preset(), chart)
    PE.clear_cache()
    PE.chart_row_values(chart, {"dpi": 77})
    assert not clean_user_store.exists() or not json.loads(
        clean_user_store.read_text(encoding="utf-8"))["certificates"]


def test_the_delete_button_forgets_the_certificate():
    import inspect
    from ui.tabs.tab_chart import TabChart, verification_preset_rows
    assert "_pc.forget(sidecar)" in inspect.getsource(TabChart._on_preset_delete)
    assert "keep_only(" in inspect.getsource(verification_preset_rows)


def test_the_app_bundle_ships_the_certificates():
    assert "data/preset_certificates.json" in (ROOT / "ChromIQ.spec").read_text(
        encoding="utf-8")
