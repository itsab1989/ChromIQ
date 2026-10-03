"""Knut, #182 5956210745 (4.3.3-beta.3): "Stored chart differs" on a chart that
had not changed.

He re-measured run1 (run 5 before runs 1-4 were deleted) and was told the chart
stored in ``runs/run1/chart/`` was not the one he was about to measure. Restore
Used Chart then changed nothing he could see, and after "Replace stored chart"
the same question came back at the next start.

His run1, compared file by file with its ``chart/`` copy: ``.ti1``, ``.ti2`` and
``.channels.json`` identical byte for byte; ``meta.json`` different (run id,
description, measure and profile settings, profile description), but
``meta.json`` has never been compared; and ``test.cht`` different in five rows
of its ``EXPECTED XYZ`` block and nowhere else. Those rows are the patches he
had re-read: with "Save scanner files" ticked (``scanner_target_enabled``) the
Quality Check rewrites ``<stem>.cht`` from the run's ``.ti3`` after every
measurement (``workflow/scanin_target.py``). So the file the comparison tripped
on carries the MEASUREMENT in that block, not the chart, and every re-measure
plus Quality Check made the stored copy "differ" again.

What defines the chart in a ``.cht`` is where the patches sit; the colours are
the ``.ti1``/``.ti2``'s. The comparison now leaves the ``EXPECTED`` block out,
and a restore leaves a live ``.cht`` that is the same chart where it is.
"""
from __future__ import annotations

import json

from core.file_manager import Project, RunMeta
from workflow.chart_slot import slot_for_run, slot_for_verification
from workflow.layout_engine import cht_writer
from workflow.verify_chart_snapshot import (chart_content, restore_slot,
                                            slot_live_differs, snapshot_slot,
                                            snapshot_matches_live)

#: A two-patch engine layout, and the boxes the scanner target writes from it
#: (top-left mm). Since Knut's #182 5958921500 a restore keeps the run's .cht
#: only when it agrees with the restored chart's layout, so the layout is real.
_LAYOUT = {"engine": "chromiq", "dpi": 254, "paper_mm": [210, 297],
           "patches": [{"loc": "A1", "x": 260, "y": 387, "w": 75, "h": 81,
                        "page": 0},
                       {"loc": "A2", "x": 260, "y": 476, "w": 75, "h": 81,
                        "page": 0}]}
_BOXES = cht_writer.boxes_from_patch_rects(_LAYOUT["patches"], 297, 254)
#: EXPECTED rows from Knut's own files: the stored copy, then the live file
#: after he re-read the patch (E23 in his run1, renamed to a box we have here).
_STORED_XYZ = [("A1", 51.192480, 52.309440, 41.126560),
               ("A2", 14.837750, 15.195730, 16.116550)]
_REREAD_XYZ = [("A1", 50.882930, 52.085720, 40.903410),
               ("A2", 14.716160, 15.192070, 16.179570)]


def _write_cht(path, xyz, boxes=_BOXES):
    cht_writer.write_cht(path, boxes, xyz)


def _measured_run(tmp_path, runs=1):
    proj = Project.create(tmp_path / "test", "test")
    for _ in range(runs - 1):
        proj.new_run()
    for r in proj.all_runs():
        r.ensure_dir()
        if not r.meta_path.exists():
            r.save_meta(RunMeta.fresh(r.id))
    run = proj.all_runs()[-1]
    run.chart_ti1.write_text("TI1 patches", encoding="utf-8")
    run.chart_ti2.write_text("TI2 layout", encoding="utf-8")
    run.chart_channels_json.write_text(json.dumps({"layout": _LAYOUT}),
                                       encoding="utf-8")
    _write_cht(run.dir / f"{run.stem}.cht", _STORED_XYZ)
    run.measurement_ti3.write_text("MEASUREMENT", encoding="utf-8")
    _edit_meta(run, run_id=run.id, description="", profile_description="P-m",
               profile_settings={"quality": "m"},
               create_chart_settings={"patches": 648},
               chart_notes="the notes the chart was made with")
    # Measurement starts: the copy is taken (Replace stored chart / first read).
    snapshot_slot(slot_for_run(run))
    return proj, run


def _edit_meta(run, **fields):
    data = json.loads(run.meta_path.read_text(encoding="utf-8"))
    data.update(fields)
    run.meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _quality_check_rewrites_the_scanner_cht(run):
    """What "Save scanner files" does after a re-measurement: the same boxes,
    the newly measured XYZ."""
    _write_cht(run.dir / f"{run.stem}.cht", _REREAD_XYZ)


# ---------------------------------------------------------------------------
def test_a_remeasured_scanner_cht_is_still_the_same_chart(tmp_path):
    _proj, run = _measured_run(tmp_path)
    _quality_check_rewrites_the_scanner_cht(run)
    # Knut, #182 5958921500: the .cht is never stored in chart/ at all now.
    assert not (run.dir / "chart" / f"{run.stem}.cht").exists()

    slot = slot_for_run(run)
    # the warning before a measurement…
    assert slot_live_differs(slot) is False
    # …and the Restore Used Chart button agree: nothing to restore.
    assert snapshot_matches_live(slot) is True


def test_a_cht_is_no_longer_what_decides_a_runs_chart(tmp_path):
    """Superseded by Knut, #182 5958921500: a run's .cht is made from the
    measurement and is not part of the stored chart. Neither a live .cht with
    moved patches nor one left in an older snapshot makes the charts differ;
    whether the live one stays is decided at restore (`restore_cht_plan`)."""
    _proj, run = _measured_run(tmp_path)
    moved = [dict(b) for b in _BOXES]
    moved[1]["y"] += 1.0
    _write_cht(run.dir / f"{run.stem}.cht", _STORED_XYZ, boxes=moved)
    _write_cht(run.dir / "chart" / f"{run.stem}.cht", _REREAD_XYZ)

    slot = slot_for_run(run)
    assert slot_live_differs(slot) is False
    assert snapshot_matches_live(slot) is True


def test_chart_content_drops_only_the_expected_block(tmp_path):
    p = tmp_path / "x.cht"
    _write_cht(p, _STORED_XYZ)
    kept = chart_content(p).decode()
    assert "BOXES 2" in kept and "XLIST" in kept and "YLIST" in kept
    assert "  X A2 A2" in kept
    assert "EXPECTED" not in kept and "51.192480" not in kept
    # every other chart file is compared in full
    q = tmp_path / "x.ti2"
    q.write_bytes(b"EXPECTED\n  1 2 3\n")
    assert chart_content(q) == q.read_bytes()


def test_a_renumbered_run_does_not_ask(tmp_path):
    """Runs before it deleted, so run 2 became run 1, and everything in its
    meta.json that is not the chart changed: no question at the next start."""
    import core.run_delete as rd

    class _Target:
        profile_run, run_type, verification_id = "run1", "profiling", ""

        def is_verification(self):
            return False

    proj, run = _measured_run(tmp_path, runs=2)
    assert run.id == "run2"
    rd.delete_run(proj, rd.plan_for(proj, _Target()))
    proj = Project.load(proj.root)
    run1 = proj.run("run1")
    assert run1.load_meta().run_id == "run1"
    assert json.loads((run1.dir / "chart" / "meta.json").read_text(
        encoding="utf-8"))["run_id"] == "run2"
    _edit_meta(run1, description="Test of Profiling and Verification run",
               profile_description="P-high", profile_settings={"quality": "h"},
               measure_settings={"bidirectional": {"value": "force"}})
    _quality_check_rewrites_the_scanner_cht(run1)

    slot = slot_for_run(run1)
    assert slot_live_differs(slot) is False
    assert snapshot_matches_live(slot) is True


def test_restore_puts_back_the_chart_and_nothing_of_the_run(tmp_path):
    """A restore that is needed (the layout really changed) brings back the
    chart files and the chart's meta fields, keeps the run's own fields as
    they are now, archives the meta.json it rewrites, and leaves a live .cht
    that is the same chart alone, so its EXPECTED values keep describing the
    measurement the run holds."""
    _proj, run = _measured_run(tmp_path)
    _quality_check_rewrites_the_scanner_cht(run)
    run.chart_ti2.write_text("TI2 a different layout", encoding="utf-8")
    _edit_meta(run, run_id="run1", description="typed since",
               profile_description="P-high", profile_settings={"quality": "h"},
               create_chart_settings={"patches": 99},
               chart_notes="notes typed since")
    live_cht = (run.dir / f"{run.stem}.cht").read_bytes()

    slot = slot_for_run(run)
    assert slot_live_differs(slot) is True
    result = restore_slot(slot)
    assert result.ok

    assert run.chart_ti2.read_text(encoding="utf-8") == "TI2 layout"
    assert (run.dir / f"{run.stem}.cht").read_bytes() == live_cht
    meta = json.loads(run.meta_path.read_text(encoding="utf-8"))
    # the chart's fields, from the copy
    assert meta["create_chart_settings"] == {"patches": 648}
    assert meta["chart_notes"] == "the notes the chart was made with"
    # the run's own, as they are now
    assert meta["run_id"] == "run1"
    assert meta["description"] == "typed since"
    assert meta["profile_description"] == "P-high"
    assert meta["profile_settings"] == {"quality": "h"}
    # what was rewritten is kept in old/
    archived = list((run.dir / "old").rglob("meta.json"))
    assert archived, "the replaced meta.json must be archived"
    assert json.loads(archived[0].read_text(encoding="utf-8"))[
        "description"] == "typed since"
    assert snapshot_matches_live(slot) is True


def test_a_verification_cht_follows_the_same_rule(tmp_path):
    _proj, run = _measured_run(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    vdir = run.verifications_dir
    (vdir / f"{run.verify_stem}.ti2").write_text("V TI2", encoding="utf-8")
    _write_cht(vdir / f"{run.verify_stem}.cht", _STORED_XYZ)
    snapshot_slot(slot_for_verification(v))
    _write_cht(vdir / f"{run.verify_stem}.cht", _REREAD_XYZ)

    from workflow.verify_chart_snapshot import live_differs_from_snapshot
    assert slot_live_differs(slot_for_verification(v)) is False
    assert live_differs_from_snapshot(v) is False
    assert snapshot_matches_live(slot_for_verification(v)) is True
