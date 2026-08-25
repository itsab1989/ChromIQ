"""Duplicating a run copies the settings the copied files were made with.

`docs/design/per_target_settings.md` §6.3: *"Duplicate run — the copy takes the
source's settings, since it takes the source's chart."* That is confirmed
specification text, not a proposal, so this is a conformance fix.

Before it, `duplicate_run` wrote a fresh `RunMeta` carrying four fields, and
**17 of 27 were silently dropped** — including all five settings groups and the
TI2-editor state, which its own docstring says *"can't be recovered from the
.ti2 alone."*

The mechanism is an exhaustive partition, not a deny-list: a deny-list would
make a newly added field carried by accident, an allow-list would make it
dropped by accident. `test_every_field_is_classified` is what makes the choice
unavoidable.
"""
from __future__ import annotations

import dataclasses as dc

import pytest

from core.file_manager import (DUPLICATE_META_CARRY, DUPLICATE_META_FRESH,
                               Project, RunMeta)


@pytest.fixture
def project(tmp_path):
    return Project.create(tmp_path / "Demo-Duplicate-Settings",
                          "Demo-Duplicate-Settings")


def test_every_field_is_classified():
    """THE GUARD. Add a field to RunMeta and this fails until you choose.

    Without it, the next field added is carried or dropped by whichever
    default happens to apply — silently, and nobody finds out until a user's
    duplicate behaves differently from its source.
    """
    everything = {f.name for f in dc.fields(RunMeta)}
    both = DUPLICATE_META_CARRY | DUPLICATE_META_FRESH
    assert not (DUPLICATE_META_CARRY & DUPLICATE_META_FRESH), \
        "a field is in both sets — decide which"
    assert both == everything, (
        f"unclassified: {sorted(everything - both)}  "
        f"unknown: {sorted(both - everything)}")


def _seed(run):
    """Put a distinct, recognisable value in every carried field."""
    m = run.load_meta()
    m.create_chart_settings = {"targen_-f": 1944}
    m.create_chart_ui = {"engine": True, "recipe": {"area_cols": 21}}
    m.measure_settings = {"chartread_-T": 0.6}
    m.profile_settings = {"colprof_-q": "h"}
    m.print_settings = {"printer": "Canon PRO-300"}
    m.instrument, m.paper = "i1", "A4"
    m.chart_notes = "notes on the sheet"
    m.scanner_target_enabled = True
    m.chart_snapshot_stale = True
    m.averaging_enabled, m.averaging_method, m.averaging_read_count = \
        True, "median", 3
    m.profile_built_from = "merged.ti3"
    m.calibration_used = "cal/target-cal.cal"
    m.parent_run = "run1"
    m.preconditioning_source_run = "run1"
    m.editor_layout = {"cols": 21}
    m.editor_basename = "my-chart"
    m.editor_recipe = {"mode": "generate"}
    # …and the ones that must NOT come across
    m.description = "the original"
    m.verify_chart_notes = "notes about a verification sheet"
    m.profile_description = "My Printer Profile v1"
    m.status = "finished"
    run.save_meta(m)
    return m


def test_every_carried_field_arrives(project):
    src = project.current_run() or project.new_run()
    seeded = _seed(src)
    dup = project.duplicate_run(src)
    got = dup.load_meta()
    for name in sorted(DUPLICATE_META_CARRY):
        assert getattr(got, name) == getattr(seeded, name), (
            f"{name} was dropped by Duplicate — the copy has the source's "
            f"files but not what describes them")


def test_the_copy_does_not_claim_the_source_s_identity(project):
    src = project.current_run() or project.new_run()
    seeded = _seed(src)
    dup = project.duplicate_run(src)
    got = dup.load_meta()

    assert got.run_id == dup.id != seeded.run_id
    assert got.duplicated_from == src.id
    assert got.description.startswith("(copy) "), \
        "two runs would read as the same work"
    assert got.verify_chart_notes == "", \
        "notes about a verification sheet the copy does not have"
    assert got.profile_description == "", \
        "two different profiles would ship under one ICC Description"
    assert got.status != "finished" or got.status == RunMeta().status


def test_a_chain_of_copies_names_the_run_it_came_from(project):
    """`duplicated_from` must not be inherited, or every copy names run1."""
    a = project.current_run() or project.new_run()
    _seed(a)
    b = project.duplicate_run(a)
    c = project.duplicate_run(b)
    assert c.load_meta().duplicated_from == b.id, \
        "the second copy names the first run instead of the one it came from"


def test_an_empty_source_stays_empty(project):
    """The control: carrying must not invent values."""
    src = project.current_run() or project.new_run()
    dup = project.duplicate_run(src)
    got, fresh = dup.load_meta(), RunMeta()
    for name in sorted(DUPLICATE_META_CARRY):
        assert getattr(got, name) == getattr(fresh, name), (
            f"{name} was invented by Duplicate from an empty source")
