"""Review AM (4.3.3-beta.5): Restore Used Chart, with the run's .cht/.cie now
archived beside the replaced meta.json (Knut #182 5958921500, 5959825756),
must still roll back exactly and never lose the chart it replaces.

Three faults measured by fault injection before the fix:

1. the side-file archive moved meta.json, then failed on the .cht: no archive
   folder was returned, so the rollback put nothing back and the run was left
   WITHOUT its meta.json (and its .cht);
2. two restores in the same second share ``old/<date>/``; when the second one
   rolled back it moved the FIRST restore's ``meta.json`` into the run (its
   own had been renamed ``meta_1.json``), silently reverting the Description;
3. a stash left by an earlier restore whose archive step failed (it then holds
   the only copy of a chart) was reused by the next restore, whose files
   replaced it by name: that chart was gone.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime

import core.file_manager as FM
import workflow.verify_chart_snapshot as V
from workflow.chart_slot import slot_for_run
from workflow.verify_chart_snapshot import restore_slot

from tests.test_knut_beta3_the_run_cht_is_not_the_chart import (  # noqa: E402
    _layout, _measured, _new_chart)


def _set_description(run, text):
    m = json.loads(run.meta_path.read_text(encoding="utf-8"))
    m["description"] = text
    run.meta_path.write_text(json.dumps(m), encoding="utf-8")


def _description(run):
    return json.loads(run.meta_path.read_text(encoding="utf-8")).get(
        "description")


def test_a_side_archive_failing_part_way_puts_meta_and_cht_back(
        tmp_path, monkeypatch):
    _proj, run, _ = _measured(tmp_path, _layout())
    _set_description(run, "LIVE")
    chts = _new_chart(run, _layout(shift=3))
    before = {p.name: p.read_bytes() for p in run.dir.iterdir() if p.is_file()}
    real = shutil.move
    calls = {"n": 0}

    def second_move_fails(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:            # meta.json went, the .cht does not
            raise OSError("disk full")
        return real(*a, **k)
    monkeypatch.setattr(shutil, "move", second_move_fails)
    result = restore_slot(slot_for_run(run))
    monkeypatch.setattr(shutil, "move", real)
    assert result.rolled_back
    after = {p.name: p.read_bytes() for p in run.dir.iterdir() if p.is_file()}
    assert after == before, "the rollback must leave the run exactly as it was"
    assert run.meta_path.is_file() and chts[0].is_file()


def test_a_rollback_in_a_shared_dated_folder_brings_back_its_own_meta(
        tmp_path, monkeypatch):
    _proj, run, _ = _measured(tmp_path, _layout())

    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 2, 22, 0, 0)
    monkeypatch.setattr(FM, "datetime", Frozen)
    _set_description(run, "FIRST")
    run.chart_ti1.write_text("TI1 chart B", encoding="utf-8")
    assert restore_slot(slot_for_run(run)).ok
    _set_description(run, "SECOND")
    run.chart_ti1.write_text("TI1 chart C", encoding="utf-8")

    def full(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(V.shutil, "copy2", full)
    result = restore_slot(slot_for_run(run))
    assert result.rolled_back
    assert _description(run) == "SECOND"


def test_a_stash_left_by_an_earlier_restore_is_never_overwritten(
        tmp_path, monkeypatch):
    _proj, run, _ = _measured(tmp_path, _layout())
    run.chart_ti1.write_text("TI1 chart B", encoding="utf-8")

    def archive_fails(*_a, **_k):
        raise OSError("archive failed")
    monkeypatch.setattr(V, "_archive_replaced_chart", archive_fails)
    assert restore_slot(slot_for_run(run)).ok       # B is kept in the stash
    monkeypatch.undo()
    run.chart_ti1.write_text("TI1 chart C", encoding="utf-8")
    assert restore_slot(slot_for_run(run)).ok
    digests = {hashlib.sha1(p.read_bytes()).hexdigest()
               for p in run.dir.rglob("*") if p.is_file()}
    for text in (b"TI1 chart B", b"TI1 chart C"):
        assert hashlib.sha1(text).hexdigest() in digests, \
            f"{text!r} was lost"
