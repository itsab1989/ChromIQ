"""The Report type pulldown: what it offers, what it stores, what it refuses.

#182 W-A (D28, issue section 19). Six types, one pulldown, and the same rule
that governs the limit set beside it: the choice belongs to the profile RUN, so
every dated verification of the run produces the same kind of document
(Knut D9).

Two things separate this control from the one beside it, and both are tested
here.

**Nothing is recalculated.** A limit set decides what a measurement is judged
against, so changing it moves verdicts already on disk. A type decides which
document is produced from numbers that do not move.

**Most of the menu cannot be chosen yet**, and it is SHOWN anyway. Knut,
2026-09-09: *"those metrics, compliance sets and report types that depend on
information in documents that are behind the ISO paywall are marked as not yet
implemented and a reason for it."* A hidden entry says nothing about why it is
not there.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_report import (  # noqa: E402
    REPORT_TYPE_FULL, REPORT_TYPE_GREY, REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8,
    REPORT_TYPE_MENU, REPORT_TYPE_MENU_HEADING, REPORT_TYPE_RECORD,
    REPORT_TYPE_SUMMARY, REPORT_TYPES)


def _dialog(tmp_path, qapp):
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run


def _ids(dlg):
    c = dlg._type_combo
    return [c.itemData(i) for i in range(c.count())]


def _enabled(dlg, i):
    m = dlg._type_combo.model()
    return m.item(i).isEnabled()


# ---------------------------------------------------------------------------
# What it offers
# ---------------------------------------------------------------------------
def test_all_six_types_are_offered_and_the_heading_sits_between_them(tmp_path, qapp):
    """MUTATION: drop the heading item and this goes red."""
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        ids = _ids(dlg)
        assert [i for i in ids if i] == list(REPORT_TYPES)
        assert "" in ids, "the heading over the formal half is missing"
        assert ids.index("") == ids.index(REPORT_TYPE_ISO_8) - 1
        texts = [dlg._type_combo.itemText(i)
                 for i in range(dlg._type_combo.count())]
        assert REPORT_TYPE_MENU_HEADING in texts
    finally:
        dlg.close()


def test_the_heading_does_not_read_as_a_refused_choice(tmp_path, qapp):
    """Photographed on screen: greyed and unadorned, the heading sat in the
    list looking exactly like the four types that cannot be picked, and a
    reader had no way to tell a section title from a refusal.

    A rule above it and a bold italic face fix that, and both have to survive
    the day T5 and T6 become selectable, which is when greying stops carrying
    any of the meaning.

    MUTATION: drop the `insertSeparator`, or the bold/italic, and this goes
    red.
    """
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        c, model = dlg._type_combo, dlg._type_combo.model()
        h = [i for i in range(c.count())
             if c.itemText(i) == REPORT_TYPE_MENU_HEADING][0]
        f = model.item(h).font()
        assert f.bold() and f.italic(), "the heading wears the same face as a type"
        above = model.item(h - 1)
        assert above is not None and not above.text().strip(), \
            "nothing separates the two halves of the menu"
        assert not above.isEnabled()
    finally:
        dlg.close()


def test_only_the_types_chromiq_can_produce_may_be_picked(tmp_path, qapp):
    """The greying follows `REPORT_TYPE_MENU`, not a list written twice.

    MUTATION: enable every item and this goes red.
    """
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        ids = _ids(dlg)
        built = {tid for tid, _n, _b, b in REPORT_TYPE_MENU if b}
        assert built, "nothing is buildable, which cannot be right"
        for i, tid in enumerate(ids):
            if tid == "":
                assert not _enabled(dlg, i), "the heading is selectable"
            else:
                assert _enabled(dlg, i) is (tid in built), tid
    finally:
        dlg.close()


def test_a_type_that_is_not_built_says_WHY_not_that_it_is_missing(tmp_path, qapp):
    """The two ISO types cannot be produced for a reason a user can act on,
    and the other unbuilt ones for a different reason. One sentence each, and
    they are not the same sentence.

    MUTATION: return one line for every unbuilt type and this goes red.
    """
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        iso = dlg._not_built_line(REPORT_TYPE_ISO_8)
        soon = dlg._not_built_line(REPORT_TYPE_GREY)
        assert iso != soon
        assert "standard" in iso.lower()
        for line in (iso, soon):
            assert line and not line.endswith("unavailable")
    finally:
        dlg.close()


def test_the_line_beside_the_pulldown_describes_the_chosen_type(tmp_path, qapp):
    """…and says which types this run already has, which Knut asked for on
    2026-09-11: *"The Report window must thus show which type of reports have
    been generated."*"""
    dlg, run = _dialog(tmp_path, qapp)
    try:
        assert dlg._type_blurb_full, "the pulldown stands there explaining nothing"
        assert dlg._type_blurb_for(REPORT_TYPE_FULL) in dlg._type_blurb_full
        assert dlg._type_blurb.toolTip() == dlg._type_blurb_full
        # nothing generated yet, and the line says so rather than going quiet
        assert "generated" in dlg._type_blurb_full.lower(), dlg._type_blurb_full
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# What it stores
# ---------------------------------------------------------------------------
def test_a_run_starts_on_todays_report(tmp_path, qapp):
    from workflow.run_compliance import run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        assert dlg._report_type_now() == REPORT_TYPE_FULL
        assert run_report_type(run) == REPORT_TYPE_FULL
        assert dlg._type_combo.currentData() == REPORT_TYPE_FULL
    finally:
        dlg.close()


def test_choosing_a_buildable_type_writes_it_to_the_run(tmp_path, qapp):
    """The only type that can be chosen today is the one already selected, so
    this drives the write through the handler directly and checks it lands.

    MUTATION: drop the `set_run_report_type` call and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_MENU
    from workflow.run_compliance import run_report_type, set_run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        # put the run somewhere else first, so choosing T2 is a real change
        set_run_report_type(run, REPORT_TYPE_SUMMARY)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._type_combo.currentData() == REPORT_TYPE_SUMMARY
        i = _ids(dlg).index(REPORT_TYPE_FULL)
        dlg._type_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert run_report_type(run) == REPORT_TYPE_FULL
    finally:
        dlg.close()


def test_a_greyed_type_cannot_be_stored_even_when_the_handler_is_reached(
        tmp_path, qapp):
    """A GUARDED WRITE BEHIND AN UNGUARDED CONTROL is the shape that came back
    in three separate challenge rounds. The entry is greyed, and the handler
    refuses it anyway, because a keyboard, a style or a later refactor that
    ignores the flag must not be able to store a type ChromIQ cannot produce.

    MUTATION: drop the `report_type_is_built` check in the handler and this
    goes red.
    """
    from workflow.run_compliance import run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        i = _ids(dlg).index(REPORT_TYPE_ISO_7)
        dlg._type_combo.blockSignals(True)
        dlg._type_combo.setCurrentIndex(i)
        dlg._type_combo.blockSignals(False)
        dlg._on_type_chosen(i)
        qapp.processEvents()
        assert run_report_type(run) == REPORT_TYPE_FULL, \
            "a type ChromIQ cannot produce was written to the run"
        assert dlg._type_combo.currentData() == REPORT_TYPE_FULL, \
            "the pulldown was left naming a type the run is not on"
    finally:
        dlg.close()


def test_a_run_that_moved_while_the_window_sat_there_is_not_written_to(
        tmp_path, qapp, monkeypatch):
    """A WINDOW MUST BE ABLE TO TELL ITS OWN WRITE FROM SOMEBODY ELSE'S. The
    set pulldown beside this one learned that over four rounds; this control
    was built with it rather than without.

    MUTATION: drop the `_run_state_at_sync` comparison and this goes red.
    """
    from workflow.run_compliance import run_report_type, set_run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    said = []
    monkeypatch.setattr(dlg, "_say_run_moved_while_asking",
                        lambda r: said.append(r))
    try:
        set_run_report_type(run, REPORT_TYPE_SUMMARY)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        # …and now somebody else changes the run, after this window drew it
        meta = run.load_meta()
        meta.compliance_unlocked = True
        run.save_meta(meta)
        i = _ids(dlg).index(REPORT_TYPE_FULL)
        dlg._type_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert run_report_type(run) == REPORT_TYPE_SUMMARY, \
            "the window wrote over a run that had moved under it"
        assert said, "and it did not say so"
    finally:
        dlg.close()


def test_the_type_moving_is_visible_to_every_doors_guard(tmp_path, qapp):
    """`_run_state_now` is documented as everything this window's decisions
    depend on, and the type is now one of them. A second window changing it
    while a question is on screen has to be visible to the door that asked.

    MUTATION: leave `report_type` out of `_run_state_now` and this goes red.
    """
    from workflow.run_compliance import set_run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        before = dlg._run_state_now(run)
        set_run_report_type(run, REPORT_TYPE_SUMMARY)
        assert dlg._run_state_now(run) != before
    finally:
        dlg.close()


def test_a_measurement_in_no_project_keeps_its_choice_for_the_session(
        tmp_path, qapp):
    """CH-14: a file that is in no run has nowhere to store a choice, and the
    window must not invent one. The limit set beside it behaves the same way.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from core.settings import AppSettings
    s, _fm, _ctl, _run = _verify_env(tmp_path)
    loose = tmp_path / "downloads" / "somebody.ti3"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=loose)
    dlg.show()
    qapp.processEvents()
    try:
        assert dlg._run_ctx is None
        assert dlg._report_type_now() == REPORT_TYPE_FULL
        dlg._session_type = REPORT_TYPE_SUMMARY
        assert dlg._report_type_now() == REPORT_TYPE_SUMMARY
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# …and today's report did not move
# ---------------------------------------------------------------------------
#: Types that produce a document of their own. Every OTHER type still renders
#: today's report, byte for byte, and that is the regression surface: a user
#: who has not chosen, or who has chosen a type nobody has built, must see
#: exactly what they see now.
#:
#: THIS IS A RATCHET. The step that builds a type comes here and adds it; a
#: step that builds one and leaves this untouched has either changed nothing or
#: changed T2. It bit on the first try: adding T4 turned this red.
_DIFFERS_FROM_T2 = {REPORT_TYPE_RECORD, REPORT_TYPE_GREY}


@pytest.mark.parametrize("tid", REPORT_TYPES)
def test_an_unbuilt_type_still_renders_todays_report(tmp_path, qapp, tid):
    """THE REGRESSION SURFACE, and the ratchet above says which types are out
    of it."""
    if tid in _DIFFERS_FROM_T2:
        pytest.skip(f"{tid} has a document of its own now")
    from workflow.run_compliance import set_run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        base = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        set_run_report_type(run, tid)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        after = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        assert after == base, f"{tid} changed the report and nothing says why"
    finally:
        dlg.close()


def test_a_type_the_menu_calls_BUILT_produces_a_different_document(tmp_path, qapp):
    """THE CLAIM HAS TO BE TRUE, and the ratchet above cannot check it.

    `REPORT_TYPE_MENU`'s `built` flag is what un-greys an entry, and the test
    above reads that same flag to decide what it expects, so it validates
    itself: flipping T4 to True passed every test in this file while T4 was
    still today's report. A user would have picked "Printing record (not
    graded)" and been handed the full graded report.

    So the flag is checked against the document instead. A type ChromIQ says it
    can produce must produce something other than T2, because T2 is what the
    other five are alternatives to.

    MUTATION: flip any `built` to True without building the document and this
    goes red.
    """
    from workflow.run_compliance import set_run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        set_run_report_type(run, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        t2 = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        for tid, name, _blurb, built in REPORT_TYPE_MENU:
            if not built or tid == REPORT_TYPE_FULL:
                continue
            set_run_report_type(run, tid)
            dlg._forget_limits()
            dlg._sync_limit_controls()
            body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
            assert body != t2, (
                f"the pulldown offers {name!r} as something ChromIQ can "
                f"produce, and it hands the user today's report instead")
    finally:
        dlg.close()


def test_choosing_a_type_REDRAWS_the_report_on_screen(tmp_path, qapp):
    """THE WINDOW, NOT THE FUNCTION THAT BUILDS ITS TEXT.

    Every other test here asks `_report_body_html` what the document is. That
    is not what a user reads. An on-screen driver wrote the run and re-synced
    the controls without redrawing, and ten checks passed while the two
    photographs were identical and both showed the full report.

    MUTATION: drop the `self._refresh()` at the end of `_on_type_chosen` and
    this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    dlg, run = _dialog(tmp_path, qapp)
    try:
        before = dlg._view.toHtml()
        i = _ids(dlg).index(REPORT_TYPE_GREY)
        dlg._type_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert dlg._view.toHtml() != before, \
            "the pulldown moved and the report on screen did not"
    finally:
        dlg.close()


def _two_runs(tmp_path, qapp):
    """Two profile runs in one project, each with one dated verification."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    v1 = run1.new_verification()
    v1.ensure_dir()
    v1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    run2 = fm.project().new_run()
    v2 = run2.new_verification()
    v2.ensure_dir()
    v2.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v1.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    dlg._add_source(v2.measurement_ti3)
    qapp.processEvents()
    return dlg, run1, run2


def test_one_runs_choice_is_not_applied_to_another_runs_data(tmp_path, qapp):
    """MEASURED, AND IT WAS WRONG. The window asked ITS OWN run, which is the
    first one loaded, and applied that answer to every column: run 1 set to
    "Printing record" and run 2 left on "Full colour check" came out with run
    2's verdicts withheld, because run 1 had chosen that.

    Knut's rule is the opposite: another run in the project may use a different
    report type. A window produces ONE document, so the columns cannot each
    have their own; the answer is the one type that withholds nothing and drops
    no row, which is today's report.

    MUTATION: drop the `len(types) > 1` branch from `_report_type_now` and this
    goes red.
    """
    from workflow.compliance_sets import INFO
    from workflow.run_compliance import set_run_report_type
    dlg, run1, run2 = _two_runs(tmp_path, qapp)
    try:
        assert len(dlg._distinct_run_dirs()) == 2, "the second run did not load"
        set_run_report_type(run1, REPORT_TYPE_RECORD)
        set_run_report_type(run2, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_FULL, \
            "one run's choice was applied to the whole document"
        for r in dlg._runs_for_report():
            rows, _rc = dlg._verdict_rows(r)
            assert any(x["word"] not in (INFO, "N-A") for x in rows), \
                "a column was left ungraded by a choice its own run never made"
    finally:
        dlg.close()


def test_when_the_runs_AGREE_their_type_is_used(tmp_path, qapp):
    """The control. The fallback must not fire whenever two runs are loaded,
    only when they disagree.

    MUTATION: fall back on `len(types) >= 1` and this goes red.
    """
    from workflow.run_compliance import set_run_report_type
    dlg, run1, run2 = _two_runs(tmp_path, qapp)
    try:
        set_run_report_type(run1, REPORT_TYPE_RECORD)
        set_run_report_type(run2, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
    finally:
        dlg.close()


def test_the_window_says_why_it_ignored_both_choices(tmp_path, qapp):
    """A greyed pulldown over a value that is nobody's choice explains nothing.

    MUTATION: drop the disagreement branch in `_sync_type_combo` and this goes
    red.
    """
    from workflow.run_compliance import set_run_report_type
    dlg, run1, run2 = _two_runs(tmp_path, qapp)
    try:
        set_run_report_type(run1, REPORT_TYPE_RECORD)
        set_run_report_type(run2, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        said = dlg._type_blurb_full
        assert "different report types" in said, said
        assert not dlg._type_combo.isEnabled()
    finally:
        dlg.close()


def test_the_type_cache_does_not_outlive_the_read_it_was_taken_for(tmp_path, qapp):
    """A cache that survives a refresh is a baseline taken later than the write
    it should have caught, which is a fault shape this window has been bitten
    by four times.

    MUTATION: leave `_types_cache` alone in `_forget_limits` and this goes red.
    """
    from workflow.run_compliance import set_run_report_type
    dlg, run1, run2 = _two_runs(tmp_path, qapp)
    try:
        set_run_report_type(run1, REPORT_TYPE_RECORD)
        set_run_report_type(run2, REPORT_TYPE_RECORD)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
        set_run_report_type(run2, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_FULL, \
            "the window answered from a cache taken before the run moved"
    finally:
        dlg.close()
