"""#130 (Knut, 2026-07-27): a profiling run keeps a copy of the chart it was
measured with, exactly as a dated verification already does.

The one thing that must differ is WHICH files are copied. A verification folder
holds nothing but the chart, so "everything except the page images" is safe
there. A run's folder also holds the measurement, the profile and its own
book-keeping — and the copy is taken before the measurement exists, so anything
like a .ti3 found there is a leftover from a previous read, never part of the
chart about to be measured.
"""
from __future__ import annotations

from core.file_manager import Project
from workflow.chart_slot import slot_for_run, slot_for_verification
from workflow.verify_chart_snapshot import (restore_slot, slot_has_snapshot,
                                            slot_live_differs, snapshot_slot,
                                            slot_snapshot_files)


def _run_with_chart(tmp_path, name="P", recipe=True):
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run(); run.ensure_dir()
    run.chart_ti1.write_text("TI1")
    run.chart_ti2.write_text("TI2")
    if recipe:
        run.chart_channels_json.write_text("{}")
    (run.dir / f"{run.stem}_01.tif").write_text("PAGE")
    # the things a run also holds, which are NOT the chart
    run.measurement_ti3.write_text("MEASUREMENT")
    run.profile_icc.write_bytes(b"ICC")
    return proj, run


# ---- what a profiling copy takes -----------------------------------------
def test_only_chart_files_are_copied(tmp_path):
    _proj, run = _run_with_chart(tmp_path)

    snapshot_slot(slot_for_run(run))

    names = sorted(p.name for p in slot_snapshot_files(slot_for_run(run)))
    # meta.json joined the list on Knut's instruction of 2026-07-27: it holds
    # the patch-set editor's design and the printtarg knobs, so a chart restored
    # without it comes back without the settings it was made with.
    assert names == [f"{run.stem}.channels.json", f"{run.stem}.ti1",
                     f"{run.stem}.ti2", "meta.json"], names


def test_the_settings_file_travels_with_the_chart(tmp_path):
    """Knut, #130 2026-07-27: "this file should also be backed up to the chart/
    folders … Restoring the chart files should then also copy that meta.json
    file"."""
    _proj, run = _run_with_chart(tmp_path)
    (run.dir / "meta.json").write_text('{"editor_recipe": {"count": 540}}')

    snapshot_slot(slot_for_run(run))
    (run.dir / "meta.json").write_text('{"editor_recipe": {"count": 9}}')
    from workflow.verify_chart_snapshot import restore_slot
    restore_slot(slot_for_run(run))

    assert '"count": 540' in (run.dir / "meta.json").read_text()


def test_a_changed_settings_file_is_not_a_changed_chart(tmp_path):
    """It travels with the chart but does not describe it — otherwise editing
    the printtarg knobs would raise "this is a different chart"."""
    _proj, run = _run_with_chart(tmp_path)
    slot = slot_for_run(run)
    snapshot_slot(slot)

    (run.dir / "meta.json").write_text('{"editor_recipe": {"count": 1}}')

    assert slot_live_differs(slot) is False


def test_a_run_with_only_a_settings_file_has_no_chart(tmp_path):
    """Every run has a meta.json; that must never make an empty run look as if
    it had a chart to copy."""
    from core.file_manager import Project
    proj = Project.create(tmp_path / "Bare", "Bare")
    run = proj.current_run(); run.ensure_dir()
    (run.dir / "meta.json").write_text("{}")

    assert snapshot_slot(slot_for_run(run)) is None


def test_the_measurement_and_the_profile_are_never_copied(tmp_path):
    """The copy is taken BEFORE measuring, so a .ti3 or .icc in the folder is a
    leftover — restoring one over a later measurement would be data loss."""
    _proj, run = _run_with_chart(tmp_path)

    snapshot_slot(slot_for_run(run))

    copied = {p.suffix for p in slot_snapshot_files(slot_for_run(run))}
    assert ".ti3" not in copied and ".icc" not in copied


def test_the_pages_travel_when_there_is_no_recipe(tmp_path):
    """Without a layout recipe the images cannot be redrawn, so they must be
    kept or a restore would leave nothing printable."""
    _proj, run = _run_with_chart(tmp_path, recipe=False)

    snapshot_slot(slot_for_run(run))

    names = sorted(p.name for p in slot_snapshot_files(slot_for_run(run)))
    assert f"{run.stem}_01.tif" in names


def test_a_run_with_no_chart_copies_nothing(tmp_path):
    proj = Project.create(tmp_path / "Empty", "Empty")
    run = proj.current_run(); run.ensure_dir()
    assert snapshot_slot(slot_for_run(run)) is None
    assert not slot_has_snapshot(slot_for_run(run))


# ---- comparing ------------------------------------------------------------
def test_an_unchanged_chart_is_not_reported_as_different(tmp_path):
    _proj, run = _run_with_chart(tmp_path)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    assert slot_live_differs(slot) is False


def test_a_changed_chart_is_reported_as_different(tmp_path):
    _proj, run = _run_with_chart(tmp_path)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    run.chart_ti2.write_text("A DIFFERENT CHART")
    assert slot_live_differs(slot) is True


def test_a_new_measurement_does_not_count_as_a_changed_chart(tmp_path):
    """Measuring writes a .ti3 into the same folder; that must not make the
    chart look changed, or every second measurement would ask a pointless
    question."""
    _proj, run = _run_with_chart(tmp_path)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    run.measurement_ti3.write_text("A FRESH MEASUREMENT")
    assert slot_live_differs(slot) is False


# ---- restoring ------------------------------------------------------------
def test_restoring_puts_the_chart_back_and_leaves_the_measurement(tmp_path):
    _proj, run = _run_with_chart(tmp_path)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    run.chart_ti2.write_text("REPLACED LATER")
    run.measurement_ti3.write_text("MEASURED AFTERWARDS")

    result = restore_slot(slot)

    assert result.ok
    assert run.chart_ti2.read_text() == "TI2"
    assert run.measurement_ti3.read_text() == "MEASURED AFTERWARDS", \
        "a restore replaces the chart, never the measurement"


def test_a_restore_asks_for_the_pages_to_be_rebuilt(tmp_path):
    _proj, run = _run_with_chart(tmp_path)
    slot = slot_for_run(run)
    snapshot_slot(slot)

    result = restore_slot(slot)

    assert result.should_rebuild, "the recipe is there, so redraw the pages"
    assert not result.needs_regeneration


def test_a_restore_without_a_recipe_brings_the_pages_back_itself(tmp_path):
    _proj, run = _run_with_chart(tmp_path, recipe=False)
    slot = slot_for_run(run)
    snapshot_slot(slot)
    (run.dir / f"{run.stem}_01.tif").write_text("A DIFFERENT PAGE")

    result = restore_slot(slot)

    assert result.images_restored and not result.needs_regeneration
    assert (run.dir / f"{run.stem}_01.tif").read_text() == "PAGE"


def test_the_two_slots_do_not_touch_each_other(tmp_path):
    """A run and its verifications each keep their own copy in their own
    place; restoring one must leave the other exactly as it was."""
    _proj, run = _run_with_chart(tmp_path)
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("VERIFY CHART")
    v = run.verification("2026-07-20_100000"); v.ensure_dir()
    snapshot_slot(slot_for_verification(v))
    snapshot_slot(slot_for_run(run))

    run.chart_ti2.write_text("changed")
    restore_slot(slot_for_run(run))

    assert run.verify_chart_ti2.read_text() == "VERIFY CHART"
    assert slot_has_snapshot(slot_for_verification(v))
