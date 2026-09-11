"""A report records which TYPE it was written as, and an old one still opens.

#182, W-A. The Measurement Report is becoming six reports behind one dropdown,
and the first thing that has to be right is the storage, because every other
part of the feature reads it back.

THE SCHEMA MAY NOT BE BUMPED FOR THIS, and that is the whole design. The report
window treats a report whose schema is older than it expects as stale and
rebuilds it from the run's `.ti3`, so bumping would silently re-derive every
report on disk — the exact thing the stored-verdict work exists to prevent
(`measurement_report.py`, the note above `VERDICT_SOURCE_IN_GAMUT`). So the key
is optional and ABSENCE is the signal, exactly as `compliance` was added
(`docs/design/measurement_report_limits.md` §6).

What absence means is T2, "Full colour check", which is defined as today's
report unchanged. That is what makes this feature ship invisible: every report
saved before the dropdown existed, and every run nobody has chosen for, renders
precisely as it does now.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import (  # noqa: E402
    REPORT_SCHEMA, REPORT_TYPE_DEFAULT, REPORT_TYPE_FULL, REPORT_TYPE_SUMMARY,
    REPORT_TYPES, report_type, set_report_type)


def test_a_report_that_says_nothing_is_todays_report():
    """MUTATION: default to any other type and this goes red."""
    assert report_type({}) == REPORT_TYPE_FULL
    assert report_type(None) == REPORT_TYPE_FULL
    assert REPORT_TYPE_DEFAULT == REPORT_TYPE_FULL, (
        "the default stopped being T2, so every report written before this "
        "feature would render as something nobody chose")


@pytest.mark.parametrize("tid", REPORT_TYPES)
def test_every_type_survives_a_round_trip_through_json(tid, tmp_path):
    rep: dict = {"schema": REPORT_SCHEMA}
    set_report_type(rep, tid)
    p = tmp_path / "r.json"
    p.write_text(json.dumps(rep), encoding="utf-8")
    assert report_type(json.loads(p.read_text(encoding="utf-8"))) == tid


def test_a_type_from_a_later_chromiq_opens_as_todays_report():
    """A seventh type is a real possibility: Knut has already asked whether a
    printer-drift type should exist. A report carrying one must still OPEN
    here, and rendering it as today's report is the one answer that cannot be
    wrong about the numbers.

    MUTATION: return the unknown id unchanged and this goes red.
    """
    assert report_type({"report_type": "t9_drift_check"}) == REPORT_TYPE_FULL
    assert report_type({"report_type": ""}) == REPORT_TYPE_FULL
    assert report_type({"report_type": None}) == REPORT_TYPE_FULL


def test_an_unknown_type_is_refused_on_the_way_IN():
    """Reading is forgiving and writing is not, deliberately. A typo stored
    here would render as today's report for ever with nothing to say why.

    MUTATION: accept any string and this goes red.
    """
    rep: dict = {}
    with pytest.raises(ValueError):
        set_report_type(rep, "t2_full_colour_chekc")
    assert "report_type" not in rep, "the bad id was stored anyway"


def test_the_schema_is_not_bumped_by_this():
    """The one thing that would turn this feature into a data loss.

    If a later change genuinely needs a bump, the report window's staleness
    rule has to be dealt with FIRST, and this test is where to start reading.
    """
    assert REPORT_SCHEMA == 7


def test_the_stored_ids_are_not_the_labels():
    """Knut approved the NAMES, which are user-facing and translated. The ids
    are what goes on disk and they never change, or every saved report loses
    its type on the day somebody rewords a menu entry."""
    for tid in REPORT_TYPES:
        assert tid.islower() and " " not in tid, tid
    assert REPORT_TYPE_SUMMARY == "t1_colour_summary"


# ---------------------------------------------------------------------------
# …and the RUN remembers it too (D9)
# ---------------------------------------------------------------------------
def _run(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "t", "t")
    return proj.new_run()


def test_a_run_that_never_chose_is_verified_as_todays_report(tmp_path):
    """MUTATION: return meta.report_type raw and this goes red on the fresh
    run, whose value is ""."""
    from workflow.run_compliance import run_report_type
    assert run_report_type(_run(tmp_path)) == REPORT_TYPE_FULL
    assert run_report_type(None) == REPORT_TYPE_FULL


def test_the_chosen_type_survives_a_reload(tmp_path):
    from workflow.run_compliance import run_report_type, set_run_report_type
    run = _run(tmp_path)
    set_run_report_type(run, REPORT_TYPE_SUMMARY)
    assert run_report_type(run) == REPORT_TYPE_SUMMARY
    from core.file_manager import Run
    assert run_report_type(Run.for_dir(run.dir)) == REPORT_TYPE_SUMMARY


def test_a_typo_is_refused_before_it_reaches_the_run(tmp_path):
    """MUTATION: drop the membership check and this goes red."""
    from workflow.run_compliance import run_report_type, set_run_report_type
    run = _run(tmp_path)
    with pytest.raises(ValueError):
        set_run_report_type(run, "t4-printing-record")
    assert run_report_type(run) == REPORT_TYPE_FULL


def test_a_type_written_by_a_later_chromiq_does_not_break_the_run(tmp_path):
    from workflow.run_compliance import run_report_type
    run = _run(tmp_path)
    meta = run.load_meta()
    meta.report_type = "t9_drift_check"
    run.save_meta(meta)
    assert run_report_type(run) == REPORT_TYPE_FULL


def test_a_duplicated_run_is_verified_the_same_way(tmp_path):
    """A duplicate exists to repeat a job. Verified as a different KIND of
    document, the two cannot be compared, which is the whole reason the type
    belongs to the run (D9).

    The classification itself is guarded by the exhaustive partition in
    `test_a_duplicate_carries_its_settings.py`, which also now SEEDS this
    field: an unseeded field compares "" with "" and proves nothing.

    MUTATION: drop "report_type" from DUPLICATE_META_CARRY and this goes red.
    """
    from core.file_manager import Project
    from workflow.run_compliance import run_report_type, set_run_report_type
    proj = Project.create(tmp_path / "t", "t")
    src = proj.new_run()
    set_run_report_type(src, REPORT_TYPE_SUMMARY)
    dup = proj.duplicate_run(src)
    assert run_report_type(dup) == REPORT_TYPE_SUMMARY


# ---------------------------------------------------------------------------
# …and something has to WRITE it
# ---------------------------------------------------------------------------
def test_the_writer_has_a_caller_at_all():
    """THE WHOLE FEATURE WAS BUILT AND NEVER CALLED. Storage, a strict writer,
    a forgiving reader and four proven mutations landed in one commit, and an
    adversarial round grepped for the writer and found only its own tests, so
    eleven saved reports carried no type at all.

    MUTATION: delete the call in `tab_measure` and this goes red.
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    # BOTH paths that write a report, named. "Somebody calls it" is not the
    # rule: the recalculate path alone would satisfy that while every report
    # saved at measurement time carried nothing, and the two together are what
    # keeps a run's files agreeing with the run.
    required = {
        "ui/tabs/tab_measure.py": "the report saved after a measurement",
        "ui/dialogs/measurement_report_dialog.py":
            "the reports rewritten when a run's limits are unlocked",
    }
    for rel, what in required.items():
        src = (root / rel).read_text(encoding="utf-8")
        assert "stamp_report_type(" in src, (
            f"{rel} does not stamp the type, so {what} records none")

    # …AND THE SAVE PATH MAY NOT SKIP THE CASE THE READER CARES ABOUT. The
    # writer was gated on the measurement being IN a run, while the reader
    # consults the stamp only when it is NOT: placed in the two halves that
    # never meet. This reads the source rather than the behaviour because
    # `_maybe_save_measurement_report` needs a whole Measure tab; the
    # behavioural half is the on-screen driver, `d06_saved_report_types.py`.
    tm = (root / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    i = tm.index("stamp_report_type(")
    j = tm.rindex("_ctx = run_context_for", 0, i)
    between = tm[j:i]
    assert "if _ctx is not None" not in between, (
        "the save path stamps only when the measurement is in a run, which is "
        "the one case the reader never asks about")


def test_a_measurement_in_no_project_still_records_its_type(tmp_path):
    """The case the docstring names, and the one the call site used to skip.

    The writer was gated on the measurement being IN a run, and the reader
    consults the report's stamp only when it is NOT, so the two were placed in
    the two halves that never meet. `run_report_type(None)` answers with
    today's report, which is what such a file renders as, so the record is
    true either way.

    MUTATION: gate the call on `run_context_for(...) is not None` and this
    goes red.
    """
    from workflow.measurement_report import stamp_report_type
    rep: dict = {}
    stamp_report_type(rep, None)
    assert report_type(rep) == REPORT_TYPE_FULL
    assert rep.get("report_type") == REPORT_TYPE_FULL, \
        "a measurement in no project recorded nothing at all"


def test_stamping_never_raises_and_never_stops_a_report(tmp_path):
    """A report that cannot be stamped is still a report."""
    from workflow.measurement_report import stamp_report_type

    class Broken:
        def load_meta(self):
            raise OSError("no")

    rep: dict = {"schema": REPORT_SCHEMA}
    stamp_report_type(rep, Broken())
    assert report_type(rep) == REPORT_TYPE_FULL
