"""The five report settings wait for "Generate report", and the window says so.

Knut, 2026-09-13, on beta 12:

    The generate report button seems not to do much, as the report
    auto-generates whenever report type or judged against is changed.

and, when the change was put to him with its cost, 2026-09-14:

    This change give the user more feeling of control and understanding of when
    something should change, or when a change will result in a changed report,
    and will see that it does change or not when clicking "Generate report". It
    will also give a user a chance to undo a changed field, if not wanting to
    regenerate the report. Make the change.

So five settings now change the CONTROL and leave the DOCUMENT standing:

* Report type
* Judged against
* Show all measurement runs
* Show detailed data for each run
* the measurements ticked in the list

Everything else still repaints at once, and the difference is not arbitrary.
Those five choose how the same measurements are PRESENTED; opening a
measurement, removing one, or writing a limit number changes what there IS to
report on, and a document still showing a measurement that is no longer loaded
would be a worse lie than the one this defers.

**AND WHAT EACH SETTING DOES ON DISK IT STILL DOES AT ONCE.** Choosing a limit
set still binds the run and still asks its recalculate question; choosing a
type still stores the type on the run. Those are deliberate acts with their own
consequences, not redraws. What waits is the document on screen.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402


def _dialog(tmp_path, qapp, dates: int = 1):
    """A report window on one profile run with *dates* dated verifications.

    More than one matters for the unticking test: with a single measurement,
    unticking it empties the report, which disables "Generate report" and puts
    that test into the state
    `test_nothing_waits_for_a_button_that_cannot_be_pressed` is about.
    """
    import os
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, fm, _ctl, run = _verify_env(tmp_path)
    first = None
    for n in range(max(1, dates)):
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(
            _cgats("CTI3", [(r, g, max(0.0, b - n)) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        # DISTINCT MEASUREMENT TIMES. A run's identity in the list is
        # `created|ti3 name`, and `created` falls back to the file's own mtime;
        # two verifications written inside one second are therefore ONE key,
        # and unticking either hides both. That is a real collision, recorded
        # as a lead, and it is not what this file is about.
        os.utime(v.measurement_ti3, (1_700_000_000 + n * 86_400,) * 2)
        first = first or v
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=first.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg, run, fm


# ---------------------------------------------------------------- the banner
def test_a_fresh_window_says_nothing(tmp_path, qapp):
    """The document was just built from the controls, so there is nothing to
    warn about. A banner up on open would be noise, and a reader who sees it
    once for no reason will not read it the time it matters."""
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        assert not dlg._stale_label.isVisible()
    finally:
        dlg.close()


def _toggle_a_measurement_tick(dlg):
    """Untick (or re-tick) the FIRST measurement row, the way a click does.

    It replaces the "Show all measurement runs" half of the parametrisation
    below: the box was removed with the feature behind it on Knut's 2026-09-20
    ruling (B8-590), and what decides the measurements a report covers is the
    list. A row tick defers exactly as the box did — `_on_run_row_toggled`
    calls `_settings_touched` — so the rule under test is unchanged.
    """
    from PyQt6.QtCore import Qt
    row = next(i for i, (kind, _si, key) in enumerate(dlg._list_rows)
               if kind == "run" and key)
    item = dlg._profile_list.item(row)
    item.setCheckState(Qt.CheckState.Unchecked
                       if item.checkState() == Qt.CheckState.Checked
                       else Qt.CheckState.Checked)
    return "a measurement tick"


@pytest.mark.parametrize("setting", ["ticks", "detail"])
def test_the_deferred_settings_wait_and_say_so(tmp_path, qapp, setting):
    """MUTATION: connect the detail box, or `_on_run_row_toggled`, back to
    `_refresh` and this goes red on the first assertion, because the document
    rebuilds itself.

    TWO DATES. It used to be because of B8-392 — a window whose list held ONE
    measurement turned "Show all measurement runs" off and greyed it, so that
    box could not be moved at all on a one-date project. That box and that rule
    are gone (B8-590), and two dates are still what this needs: unticking the
    only measurement leaves nothing to generate, which is a different state
    (`test_the_last_measurement_unticked_leaves_nothing_to_generate`).
    """
    dlg, _run, _fm = _dialog(tmp_path, qapp, dates=2)
    try:
        def _move():
            if setting == "detail":
                dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
                return f"“{dlg._detail_check.text()}”"
            return _toggle_a_measurement_tick(dlg)

        before = dlg._view.toHtml()
        what = _move()
        qapp.processEvents()
        assert dlg._view.toHtml() == before, (
            f"{what} rebuilt the document instead of waiting")
        assert dlg._stale_label.isVisible(), (
            f"{what} moved and nothing on screen says the report has not")
        # …and putting it back takes the warning away, with no press needed.
        _move()
        qapp.processEvents()
        assert not dlg._stale_label.isVisible(), (
            "the setting is back where the document was built from and the "
            "window still says the report is out of date")
    finally:
        dlg.close()


def test_the_ticked_measurements_are_one_of_the_five(tmp_path, qapp):
    """Unticking a run in the list is a report setting like the other four.

    MUTATION: call `_refresh` from `_on_run_row_toggled` and this goes red.
    """
    from PyQt6.QtCore import Qt
    dlg, _run, _fm = _dialog(tmp_path, qapp, dates=2)
    try:
        rows = [i for i, (kind, _si, key) in enumerate(dlg._list_rows)
                if kind == "run" and key]
        assert len(rows) > 1, "the list needs two run rows for this test"
        assert dlg._generate_btn.isEnabled(), (
            "the button is already dead, so this test is about the other rule")
        item = dlg._profile_list.item(rows[0])
        before = dlg._view.toHtml()
        item.setCheckState(Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert dlg._view.toHtml() == before, \
            "unticking a run rebuilt the document instead of waiting"
        assert dlg._stale_label.isVisible()
        item.setCheckState(Qt.CheckState.Checked)
        qapp.processEvents()
        assert not dlg._stale_label.isVisible(), \
            "the run is ticked again and the warning is still up"
    finally:
        dlg.close()


def test_generate_builds_the_document_and_clears_the_warning(tmp_path, qapp):
    """The button is what the banner points at, so it has to do both.

    MUTATION: drop the `self._refresh()` at the end of `_on_generate_report`
    and this goes red.
    """
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        before = dlg._view.toHtml()
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._stale_label.isVisible()
        dlg._on_generate_report()
        qapp.processEvents()
        assert dlg._view.toHtml() != before, \
            "the button did not rebuild the document with the new setting"
        assert not dlg._stale_label.isVisible()
    finally:
        dlg.close()


# ------------------------------------------- what must NOT start waiting
def test_a_new_measurement_still_appears_at_once(tmp_path, qapp):
    """The line this rule is drawn on. Adding a measurement changes what there
    IS to report on, so a document that stood still would be showing a set of
    runs the list beside it contradicts.

    MUTATION: route `_rebuild_from_sources`'s repaint through
    `_settings_touched` and this goes red.
    """
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, run, fm = _dialog(tmp_path, qapp)
    try:
        before = dlg._view.toHtml()
        rows = len(dlg._list_rows)
        run2 = fm.project().new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        # MEASURABLY DIFFERENT NUMBERS, or the second profile renders the same
        # table as the first and "the document did not change" would be true
        # for a reason that has nothing to do with this rule.
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        assert len(dlg._list_rows) > rows, \
            "the measurement was not added at all, so nothing is being tested"
        assert dlg._view.toHtml() != before, \
            "a measurement was added and the report did not show it"
        assert not dlg._stale_label.isVisible(), \
            "adding a measurement is not one of the five settings"
    finally:
        dlg.close()


# ---------------------------------------------------- the wiring, in the source
def test_every_one_of_the_five_goes_through_one_door(tmp_path, qapp):
    """Five controls, one method, so a sixth cannot be wired to half the rule.

    Read off the source rather than the behaviour, because the four behavioural
    tests above cover four of the five and the fifth (the limit-set pulldown)
    needs a run whose set may still be changed.
    """
    import inspect
    from ui.dialogs import measurement_report_dialog as mrd

    src = inspect.getsource(mrd.MeasurementReportDialog)
    # **THE DOOR TAKES AN ARGUMENT NOW (B8-462), so the locator is the call and
    # not the empty pair of brackets.** Two of the five name the value they
    # just changed, `_settings_touched(set_id=…)` and `(type_id=…)`, so that
    # the pin it takes is the control the user moved rather than the one the
    # page still shows. The claim is unchanged: five controls, one method.
    assert src.count("self._settings_touched(") >= 5, (
        "fewer than five call sites reach the one door; a control was wired "
        "straight to _refresh again")
    for name in ("_on_type_chosen", "_on_set_chosen"):
        body = inspect.getsource(getattr(mrd.MeasurementReportDialog, name))
        assert "self._settings_touched(" in body, (
            f"{name} does not defer the document at all")


def test_the_banner_is_a_comparison_and_not_a_flag(tmp_path, qapp):
    """*"a chance to undo a changed field"* only exists if the window can see
    an undo, and a boolean set on change cannot.

    MUTATION: return a constant from `_doc_settings` and this goes red.

    TWO DATES, so that a row can be unticked with one measurement still left
    to generate. The setting this moves used to be "Show all measurement
    runs", which was greyed and off on a window holding one measurement; it is
    the measurement ticks since B8-590, and `_doc_settings` is a four-tuple
    rather than a five-tuple for the same reason.
    """
    dlg, _run, _fm = _dialog(tmp_path, qapp, dates=2)
    try:
        first = dlg._doc_settings()
        assert len(first) == 4, (
            "“Show all measurement runs” is back in the snapshot: " + repr(first))
        assert dlg._doc_built_with == first
        _toggle_a_measurement_tick(dlg)
        qapp.processEvents()
        assert dlg._doc_settings() != first, \
            "the snapshot cannot tell the two states apart"
        assert dlg._doc_built_with == first, \
            "the document's own snapshot moved without the document"
    finally:
        dlg.close()


# ---------------------------------------------------------- and it fits
def test_the_warning_does_not_squash_the_buttons_it_names(tmp_path, qapp):
    """MEASURED ON A PHOTOGRAPH OF THE REAL WINDOW, and it was wrong.

    The banner was first added inside the button row with a stretch. Shown, it
    took the room the four buttons needed: "Generate report" read *"erate
    rep"*, "Save report as PDF…" read *"report as"*, "Reveal folder" read
    *"veal fold"*, and the warning itself was cut off at *"or put the s"*. A
    warning that eats the button it points at is worse than no warning.

    It has its own row now, under the row it talks about, and a hidden widget
    claims no space in a Qt layout, so it costs nothing until it speaks.

    MUTATION: put `self._stale_label` back into `out_row` and this goes red.
    """
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        dlg.resize(1200, 900)
        qapp.processEvents()
        # THE MEASURE IS THE WINDOW'S OWN MINIMUM WIDTH, not what the buttons
        # happen to get at one size. A row that has to hold the warning as well
        # needs more paper, and Qt says exactly how much: with the label back
        # inside `out_row` this goes from 996 px to 1072 px the moment the
        # warning speaks, and on the real 1500 px window that is what clipped
        # four buttons at once.
        before = dlg.minimumSizeHint().width()
        wide = {b.text(): b.width() for b in
                (dlg._generate_btn, dlg._pdf_btn, dlg._reveal_btn)}
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._stale_label.isVisible()
        after = dlg.minimumSizeHint().width()
        assert after <= before, (
            f"the window needs {after} px to hold the warning and {before} px "
            f"without it, so the warning is taking room from the row")
        for btn in (dlg._generate_btn, dlg._pdf_btn, dlg._reveal_btn):
            assert btn.width() >= btn.sizeHint().width(), (
                f"“{btn.text()}” is {btn.width()} px wide and needs "
                f"{btn.sizeHint().width()}; the warning is eating the row")
            assert btn.width() >= wide[btn.text()], (
                f"“{btn.text()}” shrank from {wide[btn.text()]} to "
                f"{btn.width()} px when the warning appeared")
        # …and the warning itself is not clipped either.
        lbl = dlg._stale_label
        assert lbl.wordWrap() or lbl.width() >= lbl.sizeHint().width(), (
            "the warning is narrower than its own text and does not wrap")
    finally:
        dlg.close()


def test_nothing_waits_for_a_button_that_cannot_be_pressed(tmp_path, qapp):
    """FOUND BY READING THE ENABLE CONDITION, AND DRIVEN ON SCREEN BY AN
    ADVERSARY ROUND THE SAME HOUR.

    `_generate_btn` is disabled when the window is on a measurement that
    belongs to no run, when SEVERAL profile runs are loaded, and when every
    measurement has been unticked. The two tick boxes and the run ticks stay
    live in all three. So the first version of this feature let a user with two
    profiles loaded, which is this window's main job, toggle "Show detailed
    data", freeze the document, and read a red line telling them to press a
    greyed-out button. Those settings did nothing at all, ever.

    The rule is: the document waits only when the button can build it.

    MUTATION: drop the `isEnabled()` branch from `_settings_touched` and this
    goes red.
    """
    dlg, run, fm = _dialog(tmp_path, qapp)
    try:
        from tests.test_import_measurement_module import _cgats, _PATCHES
        run2 = fm.project().new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled(), (
            "two profile runs are loaded and the button is still live, so "
            "this test is no longer about the state it was written for")
        before = dlg._view.toHtml()
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        assert dlg._view.toHtml() != before, (
            "the document waited for a button that cannot be pressed")
        assert not dlg._stale_label.isVisible(), (
            "a red line is telling the reader to press a disabled button")
    finally:
        dlg.close()


def test_the_last_measurement_unticked_leaves_nothing_to_generate(tmp_path, qapp):
    """The third state the button dies in, and the one a reader reaches by
    accident: untick every measurement and there is no report to build.

    TWO DATES, which used to be forced by B8-392: the row ticks only decided
    what the document covered while "Show all measurement runs" was ON, and a
    window holding ONE measurement turned that box off and greyed it. Since
    B8-590 the ticks decide it always, so a one-date project could reach this
    state too; two dates are kept because unticking two rows one at a time is
    the way a reader really arrives here by accident.
    """
    from PyQt6.QtCore import Qt
    dlg, _run, _fm = _dialog(tmp_path, qapp, dates=2)
    try:
        rows = [i for i, (kind, _si, key) in enumerate(dlg._list_rows)
                if kind == "run" and key]
        assert len(rows) == 2, rows
        assert dlg._hidden_runs == set(), "every row starts ticked"
        for i in rows:
            dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled()
        assert not dlg._stale_label.isVisible(), (
            "the window is asking for a press it cannot accept")
    finally:
        dlg.close()


def test_the_loose_type_pulldown_goes_through_the_same_door(tmp_path, qapp):
    """A measurement in no project: both pulldowns behave the same way.

    An adversary round photographed them behaving differently in one window,
    which is Knut's original complaint still standing in a corner of it.

    MUTATION: put `self._refresh()` back in `_on_type_chosen`'s `ctx is None`
    branch and the source assertion goes red.
    """
    import inspect
    from ui.dialogs import measurement_report_dialog as mrd
    for name in ("_on_type_chosen", "_on_set_chosen"):
        body = inspect.getsource(getattr(mrd.MeasurementReportDialog, name))
        loose = body.split("ctx is None", 1)
        assert len(loose) == 2, f"{name} no longer has a no-run branch"
        head = loose[1].split("return", 1)[0]
        assert "self._settings_touched(" in head, (
            f"{name}'s no-run branch does not go through the one door")
        assert "self._refresh()" not in head, (
            f"{name}'s no-run branch still repaints on its own")


def test_an_at_once_door_never_leaves_the_window_saying_something_untrue(
        tmp_path, qapp):
    """An adversary round asked what happens when a door that repaints AT ONCE
    fires while one of the five is still pending, and the answer is that the
    pending setting is adopted: adding a measurement rebuilds the document, and
    it rebuilds it from the controls, which include the change nobody confirmed.

    **That is accepted, and it is not a lie at any step.** After the rebuild the
    document really does match every control, so the red line really should be
    down; put the control back afterwards and the document really is out of
    date again, so the line really should be up. What is lost is the cheap
    undo, for one setting, at the moment the reader does something that had to
    rebuild the report anyway. Building the document from the committed five
    instead would mean rendering from a snapshot rather than from the window,
    which is a different window.

    So what is pinned here is the invariant, not the convenience: **the banner
    is up exactly when the document does not match the controls**, through an
    at-once door and out the other side.

    MUTATION: leave the banner standing across `_render` (drop the
    `_show_stale_banner()` call from it) and this goes red.
    """
    dlg, run, fm = _dialog(tmp_path, qapp)
    try:
        from tests.test_import_measurement_module import _cgats, _PATCHES

        def _true_here(where):
            stale = tuple(dlg._doc_built_with) != dlg._doc_settings()
            assert dlg._stale_label.isVisible() == stale, (
                f"{where}: the red line says "
                f"{'out of date' if dlg._stale_label.isVisible() else 'up to date'} "
                f"and the document is "
                f"{'out of date' if stale else 'up to date'}")

        _true_here("fresh")
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _true_here("with a setting pending")
        assert dlg._stale_label.isVisible()
        # A SECOND PROFILE RUN, not a second verification of this one: a
        # verification created after the window opened is not picked up by
        # `_append_source` at all, so the first version of this test measured a
        # door that never fired and passed under its own mutation.
        run2 = fm.project().new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r, g * 0.5, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        rows = len(dlg._list_rows)
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        assert len(dlg._list_rows) > rows, "the at-once door never fired"
        _true_here("after a door that repaints at once")
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        _true_here("after putting the control back")
    finally:
        dlg.close()
