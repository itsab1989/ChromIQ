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

from PyQt6.QtCore import Qt  # noqa: E402
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
                # K13: this window is on a VERIFICATION, which is never a
                # Printing record, so that one is greyed as well.
                assert _enabled(dlg, i) is (
                    tid in built and tid != REPORT_TYPE_RECORD), tid
    finally:
        dlg.close()


def test_a_type_that_is_not_built_says_WHY_not_that_it_is_missing(
        tmp_path, qapp, monkeypatch):
    """While a standard's values do not ship, its ISO type cannot be produced
    for that reason, and the other unbuilt ones for a different one: one
    sentence each, not the same sentence. Once the values ship (#182 S-2,
    §23 item 4: "the paywall reason only while that standard's values do not
    ship"), what is left is the document itself, so the ISO type says what
    every unbuilt type says.

    The repository's file ships both sets, so the empty state is made by
    fixture and both states are driven.
    MUTATION: return one line for every unbuilt type and the empty half goes
    red; always give the paywall reason and the shipped half goes red.
    """
    from tests.helpers.iso_files import use_empty_shipped_iso, use_repo_iso
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        ground = tmp_path / "ground"
        ground.mkdir()
        use_empty_shipped_iso(ground, monkeypatch)
        iso = dlg._not_built_line(REPORT_TYPE_ISO_8)
        soon = dlg._not_built_line(REPORT_TYPE_GREY)
        assert iso != soon
        assert "standard" in iso.lower()
        for line in (iso, soon):
            assert line and not line.endswith("unavailable")
        use_repo_iso(monkeypatch)
        for tid in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8):
            line = dlg._not_built_line(tid)
            assert line == soon, line
            assert "standard" not in line.lower(), line
    finally:
        dlg.close()
        from workflow import compliance_sets as cs
        cs.reset_iso_cache()


def test_the_line_beside_the_pulldown_describes_the_chosen_type(tmp_path, qapp):
    """…and says which types this run already has, which Knut asked for on
    2026-09-11: *"The Report window must thus show which type of reports have
    been generated."*

    **THE DESCRIPTION MOVED OFF THE LINE ON 2026-09-13**, because sharing it
    with the generated list is what cut the list short. It is on the pulldown
    it describes; the line carries the list.
    """
    dlg, run = _dialog(tmp_path, qapp)
    try:
        assert dlg._type_blurb_full, "the pulldown stands there explaining nothing"
        assert dlg._type_combo.toolTip() == dlg._type_blurb_for(REPORT_TYPE_FULL), (
            "the type's description is not reachable anywhere")
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
_DIFFERS_FROM_T2 = {REPORT_TYPE_RECORD, REPORT_TYPE_GREY, REPORT_TYPE_SUMMARY}


@pytest.mark.parametrize("tid", REPORT_TYPES)
def test_an_unbuilt_type_still_renders_todays_report(tmp_path, qapp, tid):
    """THE REGRESSION SURFACE, and the ratchet above says which types are out
    of it."""
    if tid in _DIFFERS_FROM_T2:
        pytest.skip(f"{tid} has a document of its own now")
    from workflow.measurement_report import report_type_is_built
    from workflow.run_compliance import set_run_report_type
    dlg, run = _dialog(tmp_path, qapp)
    try:
        base = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        if report_type_is_built(tid):
            set_run_report_type(run, tid)
        else:
            # The write refuses a type this build cannot produce, so the only
            # way a run carries one is the way a real user gets one: a project
            # made on a later ChromIQ. Put it there as that ChromIQ would.
            meta = run.load_meta()
            meta.report_type = tid
            run.save_meta(meta)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        after = dlg._report_body_html(dlg._runs_for_report(), for_pdf=False)
        assert after == base, f"{tid} changed the report and nothing says why"
    finally:
        dlg.close()


def test_a_type_the_menu_calls_BUILT_produces_a_different_document(tmp_path, qapp,
                                                                  monkeypatch):
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
    # THE FLAG, NOT THE KIND. Since K13 a verification may not be a Printing
    # record, so on this fixture T4 would fall back to T2 and "differ" would
    # be asked of the fallback. What this checks is whether each BUILT type
    # renders a document of its own, which has nothing to do with which kind
    # may choose it, so the window is told it has no kind: every type, as
    # for a measurement outside any project.
    monkeypatch.setattr(dlg, "_window_kind", lambda: None)
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


def test_choosing_a_type_WAITS_FOR_GENERATE_and_says_so(tmp_path, qapp):
    """THE WINDOW, NOT THE FUNCTION THAT BUILDS ITS TEXT.

    Every other test here asks `_report_body_html` what the document is. That
    is not what a user reads. An on-screen driver wrote the run and re-synced
    the controls without redrawing, and ten checks passed while the two
    photographs were identical and both showed the full report.

    **THIS TEST USED TO ASSERT THE OPPOSITE, AND KNUT CHANGED THE RULE.**
    2026-09-14, on *"The Generate report button"*:

        This change give the user more feeling of control and understanding of
        when something should change, or when a change will result in a changed
        report, and will see that it does change or not when clicking "Generate
        report". It will also give a user a chance to undo a changed field, if
        not wanting to regenerate the report. Make the change.

    So the pulldown moving is no longer a redraw. It stores the type on the run
    exactly as before, the document stands still, and the window says why.
    Pressing the button is what builds it.

    MUTATION: put `self._refresh()` back at the end of `_on_type_chosen` and
    this goes red on the first assertion.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    dlg, run = _dialog(tmp_path, qapp)
    try:
        before = dlg._view.toHtml()
        i = _ids(dlg).index(REPORT_TYPE_GREY)
        dlg._type_combo.setCurrentIndex(i)
        qapp.processEvents()
        assert dlg._view.toHtml() == before, \
            "the document rebuilt itself instead of waiting for Generate"
        assert dlg._stale_label.isVisible(), \
            "the setting moved and nothing on screen says the report has not"
        # AND THE BUTTON IS WHAT BUILDS IT.
        dlg._on_generate_report()
        qapp.processEvents()
        assert dlg._view.toHtml() != before, \
            "“Generate report” did not rebuild the document with the new type"
        assert not dlg._stale_label.isVisible(), \
            "the document was rebuilt and the warning is still up"
    finally:
        dlg.close()


def test_putting_the_type_back_takes_the_warning_away(tmp_path, qapp):
    """*"It will also give a user a chance to undo a changed field, if not
    wanting to regenerate the report."*

    A one-way flag cannot see an undo: it would leave a red line over a
    document that already matches every control, which is the same lie the
    other way round. The banner is a COMPARISON against what the document was
    built from.

    MUTATION: make `_settings_touched` set a `_doc_is_stale` flag that
    `_show_stale_banner` reads, and this goes red.
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    dlg, run = _dialog(tmp_path, qapp)
    try:
        was = dlg._type_combo.currentIndex()
        assert not dlg._stale_label.isVisible()
        dlg._type_combo.setCurrentIndex(_ids(dlg).index(REPORT_TYPE_GREY))
        qapp.processEvents()
        assert dlg._stale_label.isVisible()
        dlg._type_combo.setCurrentIndex(was)
        qapp.processEvents()
        assert not dlg._stale_label.isVisible(), (
            "the type is back where the document was built from and the "
            "window still says the report is out of date")
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
        set_run_report_type(run1, REPORT_TYPE_GREY)
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
        set_run_report_type(run1, REPORT_TYPE_GREY)
        set_run_report_type(run2, REPORT_TYPE_GREY)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_GREY
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
        set_run_report_type(run1, REPORT_TYPE_GREY)
        set_run_report_type(run2, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        said = dlg._type_blurb_full
        assert "different report types" in said, said
        # ENABLED since K17 (Knut, beta 34): a choice across runs is the
        # window's, for the session, and written to neither run.
        assert dlg._type_combo.isEnabled()
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
        set_run_report_type(run1, REPORT_TYPE_GREY)
        set_run_report_type(run2, REPORT_TYPE_GREY)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_GREY
        set_run_report_type(run2, REPORT_TYPE_FULL)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert dlg._report_type_now() == REPORT_TYPE_FULL, \
            "the window answered from a cache taken before the run moved"
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# K17, Knut on beta 34: two runs ticked, and the type could not be chosen
# ---------------------------------------------------------------------------
def _meta_bytes(*runs):
    out = {}
    for run in runs:
        for p in sorted(run.dir.glob("*.json")):
            out[str(p)] = p.read_bytes()
    return out


def test_with_two_runs_ticked_the_type_can_be_chosen_and_neither_run_is_written(
        tmp_path, qapp):
    """*"I select some measurements from both sets, but now I am not allowed
    to select report type at all."* The pulldown is live; the choice is the
    window's, for the session; neither run's stored type moves, because with
    two runs there is no one run it belongs to.

    MUTATION: put back `setEnabled(not several)` -> the first assert is red;
    drop `or self._several_runs()` in `_on_type_chosen` -> run1's meta.json
    changes and the byte comparison is red.
    """
    dlg, run1, run2 = _two_runs(tmp_path, qapp)
    try:
        assert dlg._several_runs(), "the fixture no longer ticks two runs"
        assert dlg._type_combo.isEnabled(), (
            "the report type is greyed with two runs ticked")
        before = _meta_bytes(run1, run2)
        dlg._sync_type_combo_to(REPORT_TYPE_GREY)
        dlg._on_type_chosen(dlg._type_combo.currentIndex())
        qapp.processEvents()
        assert dlg._report_type_now() == REPORT_TYPE_GREY
        assert _meta_bytes(run1, run2) == before, (
            "a choice made across two runs was written onto a run")
    finally:
        dlg.close()


def test_with_two_runs_ticked_generate_is_live(tmp_path, qapp):
    """G7 (#182 beta 39). Two profile runs loaded and ticked no longer grey
    Generate: Knut, 5794078008, *"a user may need to see how a printers
    profile has changed across different periods"*, and 5794311113, one
    report judged against its own set. The old sentence asking the reader to
    remove every other entry is gone, and so is ROUND B's test that followed
    that advice.

    MUTATION, proven red: put `and not several` back into the enable line in
    `_sync_type_combo`."""
    dlg, _run1, _run2 = _two_runs(tmp_path, qapp)
    try:
        assert dlg._several_runs()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        assert "Remove Profile's Measurements" not in \
            dlg._generate_btn.toolTip()
    finally:
        dlg.close()


def test_a_greyed_generate_says_why_when_only_another_run_is_ticked(
        tmp_path, qapp):
    """A greyed control says why. With two runs loaded and ONLY the other
    run's measurement ticked, a report of that run alone would be filed into
    it under this window's type and set; Generate is greyed and names why.

    MUTATION, proven red: delete the "Every ticked measurement belongs to
    another profile run" tooltip branch in `_sync_type_combo` (the button is
    grey with no reason)."""
    dlg, run1, _run2 = _two_runs(tmp_path, qapp)
    try:
        mine = {dlg._run_key(r) for r in dlg._history
                if str(r.get("_origin_dir") or "").startswith(str(run1.dir))}
        assert mine
        dlg._hidden_runs = set(mine)
        dlg._sync_limit_controls()
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled()
        tip = dlg._generate_btn.toolTip()
        assert "belongs to another profile run" in tip, tip
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# K13, Knut on beta 34: which types each kind of measurement may be
# ---------------------------------------------------------------------------
def _profiling_dialog(tmp_path, qapp):
    """A window on a run's OWN sheet: a profiling measurement."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    s, _fm, _ctl, run = _verify_env(tmp_path)
    ti3 = run.dir / "sheet.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run


def _enabled_texts(dlg):
    c = dlg._type_combo
    return [c.itemText(i) for i in range(c.count())
            if c.itemData(i) and _enabled(dlg, i)]


def test_a_profiling_measurement_offers_only_the_printing_record(tmp_path, qapp):
    """*"when run type is Profiling, all report types are still available, but
    only 'Printing record' should be available."* The others are shown greyed
    with the reason, and the window is on the Printing record.

    MUTATION: make `report_types_for_kind` return every type for profiling
    and this goes red.
    """
    dlg, _run = _profiling_dialog(tmp_path, qapp)
    try:
        assert dlg._window_kind() == "profiling"
        assert _enabled_texts(dlg) == ["Printing record (not graded)"], \
            _enabled_texts(dlg)
        assert dlg._report_type_now() == REPORT_TYPE_RECORD
        i = dlg._type_combo.findData(REPORT_TYPE_FULL)
        tip = dlg._type_combo.itemData(i, Qt.ItemDataRole.ToolTipRole)
        assert "its only report is the Printing record" in tip, tip
    finally:
        dlg.close()


def test_a_verification_never_offers_the_printing_record(tmp_path, qapp):
    """*"The report type 'Printing record' is still available when run type is
    verification, but should not be available."* Greyed, with the reason.

    MUTATION: drop the `elif tid not in allowed` branch in `_sync_type_combo`
    and this goes red.
    """
    dlg, _run = _dialog(tmp_path, qapp)
    try:
        assert dlg._window_kind() == "verification"
        assert "Printing record (not graded)" not in _enabled_texts(dlg)
        assert _enabled_texts(dlg) == ["Colour summary (one page)",
                                       "Full colour check",
                                       "Grey and tone check"], _enabled_texts(dlg)
        i = dlg._type_combo.findData(REPORT_TYPE_RECORD)
        tip = dlg._type_combo.itemData(i, Qt.ItemDataRole.ToolTipRole)
        assert "report of a profiling measurement" in tip, tip
    finally:
        dlg.close()


def test_a_forced_printing_record_on_a_verification_is_refused_and_writes_nothing(
        tmp_path, qapp):
    """A keyboard or a style that ignores the grey must not be able to store
    it. MUTATION: drop the kind half of the refusal in `_on_type_chosen` and
    run.meta changes."""
    dlg, run = _dialog(tmp_path, qapp)
    try:
        before = {p: p.read_bytes() for p in run.dir.glob("*.json")}
        i = dlg._type_combo.findData(REPORT_TYPE_RECORD)
        dlg._type_combo.blockSignals(True)
        dlg._type_combo.setCurrentIndex(i)
        dlg._type_combo.blockSignals(False)
        dlg._on_type_chosen(i)
        qapp.processEvents()
        assert dlg._report_type_now() != REPORT_TYPE_RECORD
        assert {p: p.read_bytes() for p in run.dir.glob("*.json")} == before
    finally:
        dlg.close()


def test_the_automatic_report_of_a_profiling_measurement_is_a_printing_record(
        tmp_path, qapp):
    """*"When run type is Profiling, and measurement reports are generated
    after a finished measurement, only the 'Printing record' type should be
    created"*, whatever Preferences say.

    MUTATION: pass kind None from `_stamp_the_automatic_document` and this
    goes red (the Preferences type is written).
    """
    import json
    from pathlib import Path
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    from workflow.measurement_report import (list_reports, recorded_document,
                                             REPORT_TYPE_GREY)
    s, _fm, _ctl, run = _verify_env(tmp_path)
    s.set("report_default_type", REPORT_TYPE_GREY)
    ti3 = run.dir / "sheet.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(s), s)
    try:
        tab._maybe_save_measurement_report(ti3)
        paths = list_reports(run.dir)
        assert paths, "no automatic report was written"
        doc = recorded_document(json.loads(
            Path(paths[-1]).read_text(encoding="utf-8")))
        assert doc["type"] == REPORT_TYPE_RECORD, doc["type"]
    finally:
        tab.deleteLater()
