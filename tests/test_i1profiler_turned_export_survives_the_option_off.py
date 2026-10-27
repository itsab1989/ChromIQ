"""A chart made with the turned i1Profiler export keeps it when the option is
switched off later (beta; review 4.3.17 r2, SF-1; §I.14 point 2).

The rule is tied to the chart, not to the option: the order file is bound to
the chart by its SHA-256 and is what pairs a turned measurement of THAT sheet.
Restore Used Chart redraws the pages of the same chart, and with the option
off it used to delete the order twice over: the build clears exports/ before
it starts, and the finish removed "stale" turned files without asking whether
they were stale. Driven here through the chart creator's own `_finish` (which
settles the stash) and `TabChart._on_generate_finished`.
"""
from __future__ import annotations

import re
import shutil

import pytest

from workflow import i1profiler_turned as T

from tests.test_i1profiler_turned_export_after_restore import _tab_on_a_run
from tests.test_i1profiler_turned_import import _mxf_from_txf


def _quiet(tab, monkeypatch):
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                        lambda *a, **kw: type("D", (), {"exec": lambda s: 0})())
    monkeypatch.setattr(type(tab), "_warn_no_control_strip",
                        lambda self, n: None)


def _turned(run):
    if not run.exports_dir.is_dir():
        return []
    return sorted(p.name for p in run.exports_dir.iterdir()
                  if "turned" in p.name)


def _build_on_then_switch_off(tab, run, tif, monkeypatch):
    _quiet(tab, monkeypatch)
    tab._on_generate_finished([tif])
    assert T.turned_order_for(run.chart_ti2) is not None
    files = _turned(run)
    assert len(files) == 4, files
    tab._settings.set("i1profiler_turned_export", False)
    return files


def _redraw(tab, run, tif, *, relaid: bool, built: bool = True,
            guarded: bool = True):
    """What Create Chart does for Restore Used Chart (guarded) or a plain
    rebuild (not guarded): arm the guard, set the chart aside, write another
    .ti2, then end through the creator's one ending."""
    from ui.tabs.tab_chart import _ChartRebuildGuard
    held = run.chart_ti2.read_bytes()
    if guarded:
        tab._rebuild_guard = _ChartRebuildGuard(run.chart_ti2)
    # the build writes the chart's other own files again too
    rewritten = {q: q.read_bytes() for q in (run.chart_ti1, run.artefact(".channels.json"))
                 if q.is_file()}
    creator = tab._creator
    creator._chart_stash_owner = run
    creator._chart_stash = run.reset_chart_artefacts(keep_results=True,
                                                     stash=True)
    text = held.decode("utf-8")
    redrawn = re.sub(r'^CREATED ".*"$', 'CREATED "Wed Oct 28 09:00:00 2026"',
                     text, count=1, flags=re.M)
    if relaid:
        redrawn = redrawn.replace('DESCRIPTOR "', 'DESCRIPTOR "redrawn ', 1)
    if built:
        for q, data in rewritten.items():
            q.write_bytes(data)
        run.chart_ti2.write_text(redrawn, encoding="utf-8")
        tif.write_bytes(b"page")
    creator._pending_on_finish = tab._on_generate_finished
    creator._finish([tif] if built else [])
    return held


@pytest.mark.parametrize("relaid", [False, True], ids=["faithful", "relaid"])
def test_restore_used_chart_with_the_option_off_keeps_the_order(
        qapp, tmp_path, monkeypatch, relaid):
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    files = _build_on_then_switch_off(tab, run, tif, monkeypatch)
    held = _redraw(tab, run, tif, relaid=relaid)
    assert run.chart_ti2.read_bytes() == held, "the chart bytes were not kept"
    assert _turned(run) == files
    order = T.turned_order_for(run.chart_ti2)
    assert order is not None and order.path.parent == run.exports_dir
    # …and a turned measurement of that sheet still pairs
    from workflow.measurement_import import assess
    from workflow.reference_convert import cxf_measurement_to_ti3
    mxf = _mxf_from_txf(run.i1profiler_turned.txf("i1Pro 3"),
                        tmp_path / "m.mxf")
    v = assess(cxf_measurement_to_ti3(mxf, tmp_path / "m.ti3"), run.chart_ti2)
    assert v.ok and v.turned_order, v.reason


def test_a_redraw_that_does_not_finish_puts_the_order_back(
        qapp, tmp_path, monkeypatch):
    """Stopped or failed: the chart is put back from the stash, and its turned
    export with it (it used to be lost with exports/)."""
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    files = _build_on_then_switch_off(tab, run, tif, monkeypatch)
    _redraw(tab, run, tif, relaid=False, built=False)
    assert _turned(run) == files
    assert T.turned_order_for(run.chart_ti2) is not None
    assert not run.chart_stash_dirs()


def test_a_new_chart_with_the_option_off_drops_the_old_order(
        qapp, tmp_path, monkeypatch):
    """A chart that really changes (no Restore guard): the turned files
    describe a chart that no longer exists, so they go."""
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    _build_on_then_switch_off(tab, run, tif, monkeypatch)
    _redraw(tab, run, tif, relaid=True, guarded=False)
    assert _turned(run) == []
    assert T.turned_order_for(run.chart_ti2) is None
    assert not run.chart_stash_dirs()


def test_a_stale_order_left_beside_a_new_chart_is_removed(
        qapp, tmp_path, monkeypatch):
    """Without any rebuild clearing: the finish itself removes turned files
    whose order names another chart, and keeps nothing else away."""
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    _build_on_then_switch_off(tab, run, tif, monkeypatch)
    run.chart_ti2.write_text(
        run.chart_ti2.read_text(encoding="utf-8").replace(
            'DESCRIPTOR "', 'DESCRIPTOR "other ', 1), encoding="utf-8")
    tab._on_generate_finished([tif])
    assert _turned(run) == []


def test_with_no_turned_files_a_redraw_with_the_option_off_is_as_before(
        qapp, tmp_path, monkeypatch):
    """No turned files ever: nothing is set aside, held or written for them."""
    tab, run, tif = _tab_on_a_run(tmp_path, on=False)
    _quiet(tab, monkeypatch)
    tab._on_generate_finished([tif])
    before = sorted(p.name for p in run.exports_dir.iterdir())
    from ui.tabs.tab_chart import _ChartRebuildGuard
    g = _ChartRebuildGuard(run.chart_ti2)
    assert not any("turned" in p.name for p in g._companions)
    _redraw(tab, run, tif, relaid=False)
    assert sorted(p.name for p in run.exports_dir.iterdir()) == before
    assert _turned(run) == []


def test_remove_unless_current_judges_the_folder_it_is_given(tmp_path):
    """The TI2 layout editor writes the turned files beside the chart."""
    from tests.test_i1profiler_turned_export import _chart
    ti2 = _chart(tmp_path / "c", "C", 350)
    T.write_turned_export(ti2, ti2.parent, "C")
    assert T.remove_unless_current(ti2.parent, "C", ti2) == []
    assert T.turned_order_for(ti2) is not None
    shutil.copy2(ti2, tmp_path / "held.ti2")
    ti2.write_text(ti2.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    gone = T.remove_unless_current(ti2.parent, "C", ti2)
    assert len(gone) == 4
    assert T.turned_order_for(ti2) is None


def test_the_option_off_branches_ask_before_removing():
    import inspect
    from ui.tabs.tab_chart import TabChart
    from ui.dialogs import ti2_relayout_dialog
    src = inspect.getsource(TabChart._write_turned_i1profiler_export)
    assert "remove_unless_current(" in src and "remove_stale(" not in src
    src = inspect.getsource(ti2_relayout_dialog)
    assert "_turned.remove_stale(" not in src
    assert "_turned.remove_unless_current(" in src
