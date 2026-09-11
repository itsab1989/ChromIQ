"""ChromIQ must not claim to have produced a document it cannot produce.

Two of the six report types — Validation print check (ISO 12647-8) and Contract
proof check (ISO 12647-7) — are declared so the pulldown can SHOW them and say
why they are unavailable. The figures they judge against are behind a paywall
ChromIQ has no permission to ship. The pulldown greys them and refuses a click.

That guard sits on the control, and a guard on a control is not a guard on the
write. `set_run_report_type` accepted either id, and `report_type` handed either
straight back, because both asked only whether the id was KNOWN. Two ways in
with no hand-editing at all:

* a project made on a later ChromIQ that DOES build one of them, opened here —
  Knut and Sebastian swap projects between versions constantly;
* a run duplicated from such a project, because `report_type` is carried across
  in `DUPLICATE_META_CARRY`.

Either way the window sat on "Validation print check (ISO 12647-8)" above a
full colour check, and the line that lists what the run has already produced
named a document ChromIQ never wrote.

So: the write refuses, and the read falls back to the report this build does
produce. The stored value is NOT rewritten — the later ChromIQ that put it
there must still find the user's choice where it left it.
"""
from __future__ import annotations

import pytest

from workflow import measurement_report as mr
from workflow.run_compliance import run_report_type, set_run_report_type

UNBUILT = [t[0] for t in mr.REPORT_TYPE_MENU if not t[3]]
BUILT = [t[0] for t in mr.REPORT_TYPE_MENU if t[3]]


def test_there_are_types_this_build_cannot_produce():
    """The whole test hangs on this being a real distinction."""
    assert UNBUILT, "nothing to guard — has a type been built without updating this?"
    assert BUILT


@pytest.mark.parametrize("type_id", UNBUILT)
def test_the_run_refuses_to_store_one(tmp_path, type_id, qapp):
    run = _a_run(tmp_path)
    with pytest.raises(ValueError):
        set_run_report_type(run, type_id)
    assert run.load_meta().report_type == "", "nothing may be written on refusal"


@pytest.mark.parametrize("type_id", BUILT)
def test_and_still_stores_the_four_it_can(tmp_path, type_id, qapp):
    run = _a_run(tmp_path)
    set_run_report_type(run, type_id)
    assert run_report_type(run) == type_id


@pytest.mark.parametrize("type_id", UNBUILT)
def test_a_run_carrying_one_reads_back_as_the_report_this_build_makes(
        tmp_path, type_id, qapp):
    run = _a_run(tmp_path)
    meta = run.load_meta()
    meta.report_type = type_id            # as a later ChromIQ left it
    run.save_meta(meta)
    assert run_report_type(run) == mr.REPORT_TYPE_DEFAULT
    assert run.load_meta().report_type == type_id, \
        "the later ChromIQ's choice must survive being opened here"


@pytest.mark.parametrize("type_id", UNBUILT)
def test_a_saved_report_claiming_one_is_shown_as_what_it_is(type_id):
    assert mr.report_type({"report_type": type_id}) == mr.REPORT_TYPE_DEFAULT


def test_an_unknown_id_still_falls_back_too():
    assert mr.report_type({"report_type": "t9_from_the_future"}) == \
        mr.REPORT_TYPE_DEFAULT
    assert mr.report_type({}) == mr.REPORT_TYPE_DEFAULT


@pytest.mark.parametrize("type_id", UNBUILT)
def test_the_already_generated_list_cannot_name_one(tmp_path, type_id, qapp):
    """`generated_report_types` counts what is on disk BY TYPE, and it is what
    the line under the pulldown reads. A report file claiming an unbuilt type
    must be counted as the document it really is."""
    import json
    run = _a_run(tmp_path)
    reports = run.dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "report_20260911_120000.json").write_text(
        json.dumps({"report_type": type_id}), encoding="utf-8")
    counts = mr.generated_report_types(run)
    assert type_id not in counts
    assert counts.get(mr.REPORT_TYPE_DEFAULT) == 1


def _a_run(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    return run
