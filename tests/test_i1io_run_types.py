"""The X-Rite i1iO chart (Beta) in Run type Verification and Calibration.

The owner, relayed 2026-11-13: *"verification and calibration runs must work
like for other instruments."* With i1iO support on, both run types make their
charts for the i1iO exactly as they do for any instrument (the same flow, the
same files in the same places: ``runs/runN/verifications/`` and ``cal/``),
laid out with the i1iO's rules and tagged, so the Measure tab recognises them
and shows the i1iO notice.

Which instrument a target with NOTHING STORED opens on is not the i1iO's own
question: ``per_target_settings.md`` §4 S5 and S8 (Knut's ruling) say the
saved defaults, else the factory ones, for every instrument. Measured on
screen the same day for the ColorMunki too (``runtypes/repro-CM`` in the
round's folder). These tests pin that the i1iO follows that rule and nothing
else: once chosen, a target keeps it (§4 S1 to S3), and Save as Defaults on
the i1iO opens a fresh verification on it.

Real builds: targen from ArgyllCMS and the layout engine.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.measurement_target import (RUN_TYPE_CALIBRATION,  # noqa: E402
                                     RUN_TYPE_PROFILING,
                                     RUN_TYPE_VERIFICATION)

_TARGEN = Path("/Applications/Argyll/bin/targen")
requires_argyll = pytest.mark.skipif(
    not _TARGEN.exists() and shutil.which("targen") is None,
    reason="ArgyllCMS targen is not installed here")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    from core.settings import AppSettings
    from tests._cal_target_fixture import make_window, show_run
    qs = AppSettings()._qs           # the worker's sandboxed store
    kept = {k: qs.value(k) for k in qs.allKeys()}
    w = make_window(qapp, tmp_path)
    tc = w._tab_chart
    # the bar on run 1, so every build of a test lands in the same run
    show_run(w, qapp, w._file_mgr.project().current_run().id)
    # the questions a Generate may ask: answered as a person going ahead
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)
    yield w
    w.close()
    # Save as Defaults writes the store; leave it as this test found it
    for k in qs.allKeys():
        if k not in kept:
            qs.remove(k)
    for k, v in kept.items():
        qs.setValue(k, v)
    qs.sync()


def _instrument(tc) -> str:
    """The instrument the build will use: printtarg's -i, which the layout
    panel and Guided mirror."""
    return str(tc._manual_value("printtarg", "-i"))


def _pick(tc, qapp, code: str) -> None:
    """Choose *code* in the layout panel, as a person does in Manual."""
    tc._switch_mode("manual")
    tc._init_manual_layout_panel()
    p = tc._manual_layout_panel
    k = p.instr.findData(code)
    assert k >= 0, f"{code} is not offered in the layout panel"
    p.instr.setCurrentIndex(k)
    p.instr.activated.emit(k)
    qapp.processEvents()
    assert _instrument(tc) == code


def _set_type(w, qapp, run_type: str) -> None:
    w._target_ctl.set_run_type(run_type)
    qapp.processEvents()


def _generate(w, qapp, qtbot, expect: "Path | None" = None) -> None:
    """Generate, and wait until the build has finished: the runner is idle,
    the button is back and (when given) *expect* has been written."""
    tc = w._tab_chart
    before = expect.stat().st_mtime_ns if expect and expect.exists() else None

    def done():
        if w._runner.is_running or not tc._generate_btn.isEnabled():
            return False
        if expect is None:
            return True
        return expect.exists() and expect.stat().st_mtime_ns != before
    tc._on_generate()
    qtbot.waitUntil(done, timeout=180_000)
    for _ in range(10):
        qapp.processEvents()


def _prof(w) -> Path:
    return w._file_mgr.project().current_run().chart_ti2


def _verif(w) -> Path:
    run = w._file_mgr.project().current_run()
    return run.verifications_dir / f"{run.stem}-verify.ti2"


def _calib(w) -> Path:
    cal = w._file_mgr.project().calibration
    return cal.dir / f"{cal.stem}.ti2"


def _ti2_header(ti2: Path) -> str:
    return ti2.read_text(encoding="latin-1").split("BEGIN_DATA_FORMAT")[0]


def _assert_an_i1io_chart(ti2: Path) -> None:
    assert ti2.is_file(), f"no chart at {ti2}"
    head = _ti2_header(ti2)
    assert 'TARGET_INSTRUMENT "X-Rite i1iO"' in head
    assert 'CHROMIQ_I1IO_LAYOUT "1"' in head
    assert 'CHROMIQ_I1IO_TABLE "i1iO 2"' in head
    side = ti2.with_suffix("").with_name(ti2.stem + ".i1io.json")
    assert side.is_file(), "no .i1io.json beside the chart"
    data = json.loads(side.read_text(encoding="utf-8"))
    assert data["instrument"] and data["paper"] in ("A4", "Letter")
    assert len(data["marks_mm"]) == 3
    from workflow.i1io.support import chart_names_i1io, pages_are_i1io_chart
    assert chart_names_i1io(ti2) is True
    pages = sorted(ti2.parent.glob(ti2.stem + "*.tif"))
    assert pages and pages_are_i1io_chart(pages)


def _measure_refuses(w, ti2: Path, monkeypatch) -> str:
    """Start on the Measure tab with *ti2* loaded: which i1iO notice."""
    tm = w._tab_measure
    shown = []
    monkeypatch.setattr(type(tm), "_i1io_window",
                        lambda self, t, b: shown.append((t, b)))
    tm._ti1_path = ti2
    assert tm._refused_as_an_i1io_chart() is True
    assert len(shown) == 1
    from workflow import measurement_messages as M
    for msg in (M.M_I1IO_NOT_YET, M.M_I1IO_NOT_YET_BY_HAND):
        # the notice, and as its last paragraph what to aim at
        # (`measurement_messages.i1io_aim_text`)
        title, body = msg.render()
        if shown[0][0] == title and shown[0][1].startswith(body + "\n\n"):
            return msg.id
    raise AssertionError(f"an unknown notice: {shown[0][0]!r}")


@requires_argyll
def test_a_verification_chart_is_made_for_the_i1io(win, qapp, qtbot,
                                                   monkeypatch):
    w, tc = win, win._tab_chart
    run1 = w._file_mgr.project().current_run()
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _prof(w))
    _assert_an_i1io_chart(run1.chart_ti2)

    _set_type(w, qapp, RUN_TYPE_VERIFICATION)
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _verif(w))
    vti2 = run1.verifications_dir / f"{run1.stem}-verify.ti2"
    _assert_an_i1io_chart(vti2)
    # the run's profiling chart is still its own, and still an i1iO chart
    _assert_an_i1io_chart(run1.chart_ti2)
    assert _measure_refuses(w, vti2, monkeypatch) == "M-I1IO-NOT-YET-BY-HAND"


@requires_argyll
def test_a_calibration_chart_is_made_for_the_i1io(win, qapp, qtbot,
                                                  monkeypatch):
    w, tc = win, win._tab_chart
    project = w._file_mgr.project()
    _set_type(w, qapp, RUN_TYPE_CALIBRATION)
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _calib(w))
    cal = project.calibration
    cti2 = cal.dir / f"{cal.stem}.ti2"
    _assert_an_i1io_chart(cti2)
    # nothing went into a run
    run1 = project.current_run()
    assert not run1.chart_ti2.exists()
    # each ink's ramp starts its own strip, as on every calibration chart
    ch = json.loads(cti2.with_suffix(".channels.json").read_text("utf-8"))
    assert ch["patch_set_given"] is False
    assert _measure_refuses(w, cti2, monkeypatch) == "M-I1IO-NOT-YET-BY-HAND"


@requires_argyll
def test_a_profiling_chart_keeps_the_first_notice(win, qapp, qtbot,
                                                  monkeypatch):
    w, tc = win, win._tab_chart
    run1 = w._file_mgr.project().current_run()
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _prof(w))
    assert _measure_refuses(w, run1.chart_ti2, monkeypatch) == "M-I1IO-NOT-YET"


@requires_argyll
def test_each_target_keeps_the_i1io_once_chosen(win, qapp, qtbot):
    """§4 S1 to S3: a target that has its settings opens on its own. The
    i1iO, once chosen and built on in each run type, is there again after
    every switch of the run type."""
    w, tc = win, win._tab_chart
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _prof(w))
    _set_type(w, qapp, RUN_TYPE_VERIFICATION)
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _verif(w))
    _set_type(w, qapp, RUN_TYPE_CALIBRATION)
    _pick(tc, qapp, "IO2")
    _generate(w, qapp, qtbot, _calib(w))
    for rt in (RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
               RUN_TYPE_CALIBRATION, RUN_TYPE_VERIFICATION,
               RUN_TYPE_PROFILING, RUN_TYPE_CALIBRATION):
        _set_type(w, qapp, rt)
        assert _instrument(tc) == "IO2", f"{rt} lost the i1iO"
        assert tc._manual_layout_panel.instr.currentData() == "IO2", rt


@requires_argyll
@pytest.mark.parametrize("code", ["IO2", "CM"])
def test_a_fresh_target_opens_on_the_defaults_not_on_the_runs_instrument(
        win, qapp, qtbot, code):
    """§4 S5 / S8, the same for the i1iO as for the ColorMunki: a
    verification or calibration with nothing stored opens on the saved
    defaults (here the factory i1Pro), not on the instrument of the run."""
    w, tc = win, win._tab_chart
    default = tc._stored_defaults_selection()[0]
    assert default == "i1"
    _pick(tc, qapp, code)
    _generate(w, qapp, qtbot, _prof(w))
    for rt in (RUN_TYPE_VERIFICATION, RUN_TYPE_CALIBRATION):
        _set_type(w, qapp, rt)
        assert _instrument(tc) == default, rt
    _set_type(w, qapp, RUN_TYPE_PROFILING)
    assert _instrument(tc) == code


@requires_argyll
@pytest.mark.parametrize("code", ["IO2", "CM"])
def test_save_as_defaults_opens_a_fresh_target_on_that_instrument(
        win, qapp, qtbot, code):
    """§4 S5 / S8's other half: with Save as Defaults on the i1iO, a fresh
    verification and the calibration open on the i1iO, as they do on the
    ColorMunki when that is saved."""
    w, tc = win, win._tab_chart
    _pick(tc, qapp, code)
    _generate(w, qapp, qtbot, _prof(w))
    tc._on_save_defaults()
    qapp.processEvents()
    for rt in (RUN_TYPE_VERIFICATION, RUN_TYPE_CALIBRATION):
        _set_type(w, qapp, rt)
        assert _instrument(tc) == code, f"{rt} did not open on the defaults"
