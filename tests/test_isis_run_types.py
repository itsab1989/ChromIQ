"""The i1iSis chart (Beta) in every run type, built for real in the window.

Profiling, Verification and Calibration make i1iSis charts as they do for
every instrument (PROPOSAL v2 §7), in their usual folders, each with its side
file, its i1Profiler test chart (.txf) and order file in exports/, and the
Measure tab answers Start with M-ISIS-NOT-YET. A calibration chart arranges
each ink's ramp in its own column with paper-white cells inside the patch set
(`calibration_ramps`), so the .txf lists them like any patch.

Real builds: targen from ArgyllCMS and the layout engine. Fakes for the rest.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.measurement_target import (RUN_TYPE_CALIBRATION,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)

_TARGEN = Path("/Applications/Argyll/bin/targen")
requires_argyll = pytest.mark.skipif(
    not _TARGEN.exists() and shutil.which("targen") is None,
    reason="ArgyllCMS targen is not installed here")


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
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
    qs = AppSettings()._qs
    kept = {k: qs.value(k) for k in qs.allKeys()}
    w = make_window(qapp, tmp_path)
    tc = w._tab_chart
    show_run(w, qapp, w._file_mgr.project().current_run().id)
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)
    yield w
    w.close()
    for k in qs.allKeys():
        if k not in kept:
            qs.remove(k)
    for k, v in kept.items():
        qs.setValue(k, v)
    qs.sync()


def _pick(tc, qapp, code="XRISIS"):
    tc._switch_mode("manual")
    tc._init_manual_layout_panel()
    p = tc._manual_layout_panel
    k = p.instr.findData(code)
    assert k >= 0, f"{code} is not offered in the layout panel"
    p.instr.setCurrentIndex(k)
    p.instr.activated.emit(k)
    qapp.processEvents()
    assert str(tc._manual_value("printtarg", "-i")) == code


def _generate(w, qapp, qtbot, expect):
    tc = w._tab_chart
    before = expect.stat().st_mtime_ns if expect.exists() else None

    def done():
        if w._runner.is_running or not tc._generate_btn.isEnabled():
            return False
        return expect.exists() and expect.stat().st_mtime_ns != before
    tc._on_generate()
    qtbot.waitUntil(done, timeout=180_000)
    for _ in range(10):
        qapp.processEvents()


def _assert_an_isis_chart(ti2: Path) -> dict:
    assert ti2.is_file(), f"no chart at {ti2}"
    head = ti2.read_text(encoding="latin-1").split("BEGIN_DATA_FORMAT")[0]
    assert 'TARGET_INSTRUMENT "X-Rite i1iSis"' in head
    assert 'CHROMIQ_ISIS_LAYOUT "1"' in head
    side = json.loads(ti2.with_name(ti2.name[:-4] + ".isis.json").read_text(
        encoding="utf-8"))
    from core.file_manager import exports_subdir
    stem = ti2.name[:-4]
    ex = exports_subdir(ti2.parent)
    assert (ex / f"{stem}-i1profiler-isis.txf").is_file()
    order = json.loads((ex / f"{stem}-i1profiler-isis.order.json")
                       .read_text(encoding="utf-8"))
    assert order["kind"] == "isis" and order["columns"] == side["columns"]
    assert order["patches"] == side["patches"]
    return side


def _measure_refuses(w, ti2, monkeypatch) -> str:
    tm = w._tab_measure
    shown = []
    monkeypatch.setattr(type(tm), "_i1io_window",
                        lambda self, t, b: shown.append((t, b)))
    tm._ti1_path = ti2
    assert tm._refused_as_an_isis_chart() is True
    assert len(shown) == 1
    return shown[0][0]


@requires_argyll
def test_profiling_and_verification_charts(win, qapp, qtbot, monkeypatch):
    w, tc = win, win._tab_chart
    run1 = w._file_mgr.project().current_run()
    _pick(tc, qapp)
    _generate(w, qapp, qtbot, run1.chart_ti2)
    side = _assert_an_isis_chart(run1.chart_ti2)
    assert side["patch_mm"] == [6.0, 6.0] and side["header_mm"] == 32.0
    from workflow import measurement_messages as M
    title = M.M_ISIS_NOT_YET.render(cut_or_not="", txf="", cols=0, rows=0,
                                    pages=1, multipage_note="")[0]
    assert _measure_refuses(w, run1.chart_ti2, monkeypatch) == title

    w._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    qapp.processEvents()
    _pick(tc, qapp)
    vti2 = run1.verifications_dir / f"{run1.stem}-verify.ti2"
    _generate(w, qapp, qtbot, vti2)
    _assert_an_isis_chart(vti2)
    _assert_an_isis_chart(run1.chart_ti2)


@requires_argyll
def test_a_calibration_chart(win, qapp, qtbot, monkeypatch):
    w, tc = win, win._tab_chart
    project = w._file_mgr.project()
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    _pick(tc, qapp)
    cal = project.calibration
    cti2 = cal.dir / f"{cal.stem}.ti2"
    _generate(w, qapp, qtbot, cti2)
    side = _assert_an_isis_chart(cti2)
    assert not project.current_run().chart_ti2.exists()
    # every printed cell is in the .txf's list, paper-white cells included
    from core.file_manager import exports_subdir
    order = json.loads((exports_subdir(cti2.parent)
                        / f"{cal.stem}-i1profiler-isis.order.json")
                       .read_text(encoding="utf-8"))
    assert len(order["order"]) == side["patches"]
