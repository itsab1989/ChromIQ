"""Restore Used Chart brings the chart's turned i1Profiler export back with it
(beta; review 4.3.17 r3, NIT-5).

The snapshot taken when a measurement starts held the chart files and not the
turned order. So: chart A made with the option on and measured, replaced by
chart B, the option switched off, A restored. A came back and its pages were
redrawn under the rebuild guard, which (option off) then removed B's turned
files as stale, and A was left with no order at all: a device-less
re-measurement of A's turned sheet would have been paired by name. §I.14
point 2 says the files are tied to the chart, not to the switch.
"""
from __future__ import annotations

import re
import shutil

import pytest

from core.file_manager import Project, exports_subdir
from workflow import i1profiler_turned as T
from workflow.chart_slot import slot_for_run
from workflow.verify_chart_snapshot import (restore_slot, snapshot_matches_live,
                                            snapshot_slot)

from tests.test_i1profiler_turned_export import _chart
from tests.test_i1profiler_turned_export_after_restore import (_finish,
                                                               _tab_on_a_run)


def test_a_chart_made_with_the_option_on_keeps_its_order_through_a_restore(
        qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_chart import _ChartRebuildGuard
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    _finish(tab, tif, monkeypatch)                       # 1. chart A, option on
    a = run.chart_ti2.read_bytes()
    a_order = run.i1profiler_turned.order.read_bytes()
    slot = slot_for_run(run)
    snapshot_slot(slot)                                  # A is measured
    run.chart_ti2.write_text(a.decode("utf-8").replace(
        'DESCRIPTOR "', 'DESCRIPTOR "chart B ', 1), encoding="utf-8")
    _finish(tab, tif, monkeypatch)                       # 2. chart B
    b_order = run.i1profiler_turned.order.read_bytes()
    assert b_order != a_order
    tab._settings.set("i1profiler_turned_export", False)  # 3. option off
    res = restore_slot(slot)                             # 4. restore A
    assert res.ok and run.chart_ti2.read_bytes() == a
    assert T.turned_order_for(run.chart_ti2) is not None
    # …and the pages are redrawn under the rebuild guard, option off
    tab._rebuild_guard = _ChartRebuildGuard(run.chart_ti2)
    run.chart_ti2.write_text(re.sub(
        r'^CREATED ".*"$', 'CREATED "Wed Oct 28 09:00:00 2026"',
        a.decode("utf-8"), count=1, flags=re.M), encoding="utf-8")
    _finish(tab, tif, monkeypatch)
    assert run.chart_ti2.read_bytes() == a
    order = T.turned_order_for(run.chart_ti2)
    assert order is not None and order.path.parent == run.exports_dir
    assert run.i1profiler_turned.order.read_bytes() == a_order
    # B's turned files are kept with chart B in its old/ archive
    assert res.archive is not None
    assert (res.archive / "exports" / run.i1profiler_turned.order.name
            ).read_bytes() == b_order
    # the button is greyed: the turned files never decide "differs"
    assert snapshot_matches_live(slot)


def _run_with_chart(tmp_path, *, turned: bool):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    src = _chart(tmp_path / "src", "Src", 350)
    for f in src.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, run.dir / ("P" + f.name[len("Src"):]))
    if turned:
        T.write_turned_export(run.chart_ti2, run.exports_dir, run.stem)
    return run


def test_an_order_for_another_chart_is_not_stored(tmp_path):
    run = _run_with_chart(tmp_path, turned=True)
    run.chart_ti2.write_text(run.chart_ti2.read_text(encoding="utf-8") + "\n",
                             encoding="utf-8")
    slot = slot_for_run(run)
    snapshot_slot(slot)
    assert not (slot.snapshot_dir / "exports").exists()


def test_the_option_off_restore_puts_the_order_back_only_for_its_chart(
        tmp_path):
    """A snapshot whose order does not name the restored chart (the snapshot
    edited by hand) puts nothing back and touches no live turned file."""
    run = _run_with_chart(tmp_path, turned=True)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    snap_order = slot.snapshot_dir / "exports" / run.i1profiler_turned.order.name
    text = snap_order.read_text(encoding="utf-8")
    edited = re.sub(r'("chart_sha256":\s*")', r"\g<1>0", text, count=1)
    assert edited != text
    snap_order.write_text(edited, encoding="utf-8")
    # the live turned files differ from the snapshot's, so a put-back shows
    run.i1profiler_turned.note.write_text("live", encoding="utf-8")
    run.chart_ti2.write_text(run.chart_ti2.read_text(encoding="utf-8") + "\n",
                             encoding="utf-8")
    live_before = {p.name: p.read_bytes() for p in run.exports_dir.iterdir()}
    assert restore_slot(slot).ok
    assert {p.name: p.read_bytes() for p in run.exports_dir.iterdir()} == \
        live_before


@pytest.mark.parametrize("restore", [False, True])
def test_without_turned_files_snapshot_and_restore_are_as_before(
        tmp_path, restore):
    """4.3.16: the snapshot holds the chart files and nothing else, and a
    restore creates no exports/."""
    run = _run_with_chart(tmp_path, turned=False)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    held = sorted(p.name for p in slot.snapshot_dir.rglob("*"))
    assert held == sorted(["P.channels.json", "P.ti1", "P.ti2"]
                          + (["meta.json"] if (run.dir / "meta.json").is_file()
                             else []))
    if restore:
        run.chart_ti2.write_text(
            run.chart_ti2.read_text(encoding="utf-8") + "\n",
            encoding="utf-8")
        assert restore_slot(slot).ok
        assert not exports_subdir(run.dir).exists()
