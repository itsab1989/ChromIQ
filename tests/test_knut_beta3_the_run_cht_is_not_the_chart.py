"""Knut, #182 5958921500 (4.3.3-beta.3): the run's ``.cht`` is not the chart.

    *"Why is the .cht file backed up into chart/ folder? The cht file is only
    created at the end of a completed measurement, so it should never actually
    be backed up to chart/ folder (which happens at the start of a
    measurement). During a restore, if the cht file exists in the run's folder
    (not applicable for a verification run), and the content of the cht file
    is in agreement with the chart in the chart/ folder, then the cht file
    should be kept in the run's folder. If the cht file differs from the chart
    that is being restored (after clicking Restore Used Chart), then the cht
    file should be backed up to the old/ folder (as usual, like other chart
    files) and removed from the run when the restored chart is copied back to
    the run's folder (because it does not belong to the restored chart). The
    popup window (after clicking Restore Used Chart), which lists what will
    happen should specify if the cht file in the run folder is removed or
    kept."*

A run's ``<stem>.cht`` (``<stem>_NN.cht`` per page) is written only by the
scanner target (``workflow/scanin_target.py``) from the run's ``.ti3``.

AGREEMENT: a ``.cht`` is kept when it is a page the scanner target would write
for the RESTORED chart (rebuilt from the stored ``.channels.json``, under the
same name), everything but its EXPECTED rows compared.
"""
from __future__ import annotations

import json
import types

import pytest

from core.file_manager import Project, RunMeta
from workflow.chart_slot import slot_for_run, slot_for_verification
from workflow.layout_engine import cht_writer
from workflow.scanin_target import scanner_cht_pages
from workflow.verify_chart_snapshot import (restore_cht_plan, restore_slot,
                                            slot_has_snapshot,
                                            slot_live_differs,
                                            snapshot_matches_live,
                                            snapshot_slot)


def _layout(pages=1, shift=0):
    patches = []
    for pg in range(pages):
        for i, loc in enumerate(("A1", "A2")):
            patches.append({"loc": f"{loc}p{pg}", "x": 260,
                            "y": 387 + 89 * i + shift, "w": 75, "h": 81,
                            "page": pg})
    return {"engine": "chromiq", "dpi": 254, "paper_mm": [210, 297],
            "patches": patches}


def _write_scanner_cht(run, layout, xyz=1.0, crlf=False):
    """What "Save scanner files" writes after a measurement of *layout*."""
    pages = sorted({p["page"] for p in layout["patches"]})
    out = []
    for pg in pages:
        boxes = cht_writer.boxes_from_patch_rects(layout["patches"], 297, 254,
                                                  page=pg)
        name = (f"{run.stem}.cht" if len(pages) == 1
                else f"{run.stem}_{pg + 1:02d}.cht")
        text = cht_writer.build_cht_text(
            boxes, [(b["loc"], xyz, xyz + 1, xyz + 2) for b in boxes])
        if crlf:
            text = text.replace("\n", "\r\n")
        (run.dir / name).write_bytes(text.encode("utf-8"))
        out.append(run.dir / name)
    return out


def _run(tmp_path, layout):
    proj = Project.create(tmp_path / "test", "test")
    run = proj.all_runs()[-1]
    run.ensure_dir()
    if not run.meta_path.exists():
        run.save_meta(RunMeta.fresh(run.id))
    run.chart_ti1.write_text("TI1 patches", encoding="utf-8")
    run.chart_ti2.write_text("TI2 layout", encoding="utf-8")
    run.chart_channels_json.write_text(json.dumps({"layout": layout}),
                                       encoding="utf-8")
    run.measurement_ti3.write_text("MEASUREMENT", encoding="utf-8")
    return proj, run


def _measured(tmp_path, layout):
    """A run whose scanner files exist when the next measurement starts."""
    proj, run = _run(tmp_path, layout)
    chts = _write_scanner_cht(run, layout)
    snapshot_slot(slot_for_run(run))
    return proj, run, chts


def _new_chart(run, layout):
    """A different chart is made in the run, measured, its scanner files
    saved."""
    run.chart_ti2.write_text("TI2 another layout", encoding="utf-8")
    run.chart_channels_json.write_text(json.dumps({"layout": layout}),
                                       encoding="utf-8")
    return _write_scanner_cht(run, layout, xyz=7.0)


# ---- 1. never backed up to chart/ -----------------------------------------
def test_a_measurement_start_never_stores_the_runs_cht(tmp_path):
    _proj, run, chts = _measured(tmp_path, _layout())
    stored = {p.name for p in (run.dir / "chart").iterdir()}
    assert f"{run.stem}.ti2" in stored
    assert not any(n.endswith(".cht") for n in stored), stored
    assert chts[0].is_file()                 # and the run keeps its own


def test_nor_any_page_of_a_multi_page_one(tmp_path):
    _proj, run, chts = _measured(tmp_path, _layout(pages=2))
    assert [c.name for c in chts] == [f"{run.stem}_01.cht",
                                      f"{run.stem}_02.cht"]
    assert not list((run.dir / "chart").glob("*.cht"))


# ---- 2. an older snapshot's .cht stays on disk and is ignored -------------
def test_a_cht_in_an_older_snapshot_is_left_alone_and_ignored(tmp_path):
    _proj, run, _ = _measured(tmp_path, _layout())
    legacy = run.dir / "chart" / f"{run.stem}.cht"
    legacy.write_text("BOXES 1\n  X Z9 Z9 _ _ 1 1 1 1 0 0\n", encoding="utf-8")
    slot = slot_for_run(run)
    assert snapshot_matches_live(slot) is True
    assert slot_live_differs(slot) is False

    run.chart_ti2.write_text("TI2 changed", encoding="utf-8")
    assert restore_slot(slot).ok
    assert legacy.read_text(encoding="utf-8").startswith("BOXES 1")
    assert "Z9" not in (run.dir / f"{run.stem}.cht").read_text(
        encoding="utf-8"), "the snapshot's .cht must not be restored"


def test_a_snapshot_of_only_a_cht_is_no_stored_chart(tmp_path):
    _proj, run = _run(tmp_path, _layout())
    (run.dir / "chart").mkdir()
    (run.dir / "chart" / f"{run.stem}.cht").write_text("x", encoding="utf-8")
    assert slot_has_snapshot(slot_for_run(run)) is False


# ---- 3. restore: kept when in agreement ----------------------------------
def test_a_cht_that_agrees_with_the_restored_chart_is_kept(tmp_path):
    _proj, run, chts = _measured(tmp_path, _layout())
    # re-measured: same boxes, new EXPECTED values
    _write_scanner_cht(run, _layout(), xyz=42.0)
    before = chts[0].read_bytes()
    run.chart_ti2.write_text("TI2 changed", encoding="utf-8")
    slot = slot_for_run(run)
    plan = restore_cht_plan(slot)
    assert [p.name for p in plan.keep] == [chts[0].name] and not plan.remove

    result = restore_slot(slot)
    assert result.ok and result.cht_kept == [chts[0].name]
    assert result.cht_removed == []
    assert chts[0].read_bytes() == before     # its measured values too
    assert not list((run.dir / "old").rglob("*.cht")) \
        if (run.dir / "old").exists() else True


def test_line_endings_do_not_make_a_cht_disagree(tmp_path):
    _proj, run, chts = _measured(tmp_path, _layout())
    _write_scanner_cht(run, _layout(), crlf=True)
    assert restore_cht_plan(slot_for_run(run)).keep == chts


# ---- 4. restore: archived and removed when not -----------------------------
def test_a_cht_made_from_another_chart_is_archived_and_removed(tmp_path):
    _proj, run, _ = _measured(tmp_path, _layout())
    chts = _new_chart(run, _layout(shift=3))
    content = chts[0].read_bytes()
    slot = slot_for_run(run)
    plan = restore_cht_plan(slot)
    assert plan.remove == chts and not plan.keep

    result = restore_slot(slot)
    assert result.ok and result.cht_removed == [chts[0].name]
    assert not chts[0].exists(), "it does not belong to the restored chart"
    archived = list((run.dir / "old").rglob(chts[0].name))
    assert len(archived) == 1 and archived[0].read_bytes() == content
    # in the same dated folder as the meta.json the restore replaced
    assert (archived[0].parent / "meta.json").is_file()
    assert run.chart_ti2.read_text(encoding="utf-8") == "TI2 layout"


def test_a_page_the_restored_chart_does_not_have_is_removed(tmp_path):
    """Per file: the stored chart has one page, the new chart's .cht set two.
    The first chart's own ``<stem>.cht`` is still in the run, and it IS the
    restored chart's page, so it stays."""
    _proj, run, first = _measured(tmp_path, _layout())
    chts = _new_chart(run, _layout(pages=2))
    plan = restore_cht_plan(slot_for_run(run))
    assert plan.remove == chts
    assert plan.keep == first


def test_a_stored_chart_without_scanner_geometry_keeps_no_cht(tmp_path):
    """It could never have produced the file."""
    _proj, run = _run(tmp_path, {})
    cht = _write_scanner_cht(run, _layout())[0]
    snapshot_slot(slot_for_run(run))
    assert restore_cht_plan(slot_for_run(run)).remove == [cht]


def test_a_failed_restore_puts_the_cht_back(tmp_path, monkeypatch):
    _proj, run, _ = _measured(tmp_path, _layout())
    chts = _new_chart(run, _layout(shift=3))
    import workflow.verify_chart_snapshot as V

    def broken(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(V.shutil, "copy2", broken)
    result = restore_slot(slot_for_run(run))
    assert result.rolled_back and result.cht_removed == []
    assert chts[0].is_file()


def test_other_cht_files_in_the_run_are_not_touched(tmp_path):
    """Only the scanner target's own names: a user's file stays."""
    _proj, run, _ = _measured(tmp_path, _layout())
    mine = run.dir / "my-own-target.cht"
    mine.write_text("mine", encoding="utf-8")
    sample = run.dir / f"{run.stem}-sample.cht"
    sample.write_text("scanin", encoding="utf-8")
    run.chart_ti2.write_text("TI2 changed", encoding="utf-8")
    assert restore_slot(slot_for_run(run)).ok
    assert mine.read_text(encoding="utf-8") == "mine"
    assert sample.read_text(encoding="utf-8") == "scanin"


# ---- 5. not applicable to a verification date ------------------------------
def test_a_verification_date_has_no_cht_plan(tmp_path):
    _proj, run, _ = _measured(tmp_path, _layout())
    v = run.new_verification()
    v.ensure_dir()
    vdir = run.verifications_dir
    (vdir / f"{run.verify_stem}.ti2").write_text("V", encoding="utf-8")
    (vdir / f"{run.verify_stem}.cht").write_text("V cht", encoding="utf-8")
    snapshot_slot(slot_for_verification(v))
    slot = slot_for_verification(v)
    assert slot.scanner_cht_files() == []
    plan = restore_cht_plan(slot)
    assert not plan.keep and not plan.remove
    # its chart still travels whole, .cht included, as before
    assert (v.dir / "chart" / f"{run.verify_stem}.cht").is_file()


# ---- the agreement is the writer's own geometry ---------------------------
def test_the_rebuilt_pages_are_what_the_scanner_target_writes(tmp_path):
    from workflow.scanin_target import build_scanin_target_from_paths
    _proj, run = _run(tmp_path, _layout(pages=2))
    locs = [p["loc"] for p in _layout(pages=2)["patches"]]
    run.measurement_ti3.write_text(
        "CTI3\n\nKEYWORD \"SAMPLE_LOC\"\nNUMBER_OF_FIELDS 8\n"
        "BEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {len(locs)}\nBEGIN_DATA\n"
        + "".join(f"{i + 1} {loc} 1 2 3 10 20 30\n"
                  for i, loc in enumerate(locs))
        + "END_DATA\n", encoding="utf-8")
    res = build_scanin_target_from_paths(run.chart_channels_json,
                                         run.measurement_ti3,
                                         run.dir / run.stem)
    pages = scanner_cht_pages(run.chart_channels_json, run.stem)
    assert sorted(pages) == sorted(p.name for p in res.cht_paths)
    snapshot_slot(slot_for_run(run))
    assert restore_cht_plan(slot_for_run(run)).keep == sorted(res.cht_paths)


def test_a_printtarg_chart_compares_its_captured_pages(tmp_path):
    page = cht_writer.build_cht_text(
        cht_writer.boxes_from_patch_rects(_layout()["patches"], 297, 254),
        [("A1p0", 1, 2, 3), ("A2p0", 1, 2, 3)])
    layout = {"engine": "printtarg", "cht_pages": [page],
              "locs": ["A1p0", "A2p0"]}
    _proj, run = _run(tmp_path, layout)
    cht = run.dir / f"{run.stem}.cht"
    cht.write_text(page.replace("1.000000 2.000000", "9.000000 9.000000"),
                   encoding="utf-8")
    snapshot_slot(slot_for_run(run))
    assert restore_cht_plan(slot_for_run(run)).keep == [cht]


# ---- 6. the window says which -------------------------------------------
def _sentence(plan):
    from ui.measurement_target_bar import MeasurementTargetBar
    fake = types.SimpleNamespace(
        _ctl=types.SimpleNamespace(restore_cht_plan=lambda: plan))
    return MeasurementTargetBar._restore_cht_sentence(fake)


def test_the_window_says_kept(tmp_path):
    from pathlib import Path
    from workflow.verify_chart_snapshot import ChtPlan
    text = _sentence(ChtPlan(keep=[Path("P.cht")]))
    assert "P.cht" in text and "kept in the run" in text
    assert "removed" not in text


def test_the_window_says_removed(tmp_path):
    from pathlib import Path
    from workflow.verify_chart_snapshot import ChtPlan
    text = _sentence(ChtPlan(remove=[Path("P_01.cht"), Path("P_02.cht")]))
    assert "P_01.cht, P_02.cht" in text
    assert "“old” folder and removed from the run" in text
    assert "kept" not in text


def test_the_window_says_nothing_when_there_is_no_cht():
    from workflow.verify_chart_snapshot import ChtPlan
    assert _sentence(ChtPlan()) == ""


def test_the_window_is_shown_when_a_cht_would_be_removed(monkeypatch):
    """Even when nothing else differs, the user is told before a .cht goes."""
    from pathlib import Path
    import workflow.chart_slot as CS
    import workflow.verify_chart_snapshot as V
    from ui.measurement_target_bar import MeasurementTargetController
    from workflow.verify_chart_snapshot import ChtPlan
    ctl = types.SimpleNamespace(
        restore_target=lambda: object(),
        restore_cht_plan=lambda: ChtPlan(remove=[Path("P.cht")]))
    monkeypatch.setattr(CS, "slot_for", lambda _t: None)
    monkeypatch.setattr(V, "slot_live_differs", lambda _s: False)
    assert MeasurementTargetController.restore_needs_confirmation(ctl)
    ctl.restore_cht_plan = lambda: ChtPlan(keep=[Path("P.cht")])
    assert not MeasurementTargetController.restore_needs_confirmation(ctl)


@pytest.mark.parametrize("key", [
    "The scanner recognition file {names} in this run matches the chart being "
    "restored, so it is kept in the run.",
    "The scanner recognition files {names} in this run were not made from the "
    "chart being restored. They are moved to the run's “old” folder and "
    "removed from the run.",
])
def test_every_language_has_the_words(key):
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    for cat in sorted(root.glob("*.json")):
        d = json.loads(cat.read_text(encoding="utf-8"))
        assert d.get(key), f"{cat.name} lacks {key[:40]!r}"
        assert "{names}" in d[key]
