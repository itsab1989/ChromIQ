"""The Measurement Report window fixes after challenge C of beta 39 (RW-fix).

* C5: "Report shown" always names what the window holds: the loaded report,
  or "New report…" with its defaults; after a Delete as well.
* C6: every greyed Generate carries its reason, as a tooltip and on screen.
* C9: no button of the Measurement Report family is the default, so Return
  opens no chooser.
* C10: an Update that covers the same measurements keeps its name's scope.
* C12: "Already generated for this run" only counts this run's reports; a
  count of more says "for these measurements".
* K30 leftovers: a calibration row is not "1 run"; a Grey and tone check
  draws no colour-accuracy limit line; the demo texts from before the ISO
  values shipped.

Spec: `docs/design/measurement_report_limits.md` §13.13, §17 item 4, §24.
Every test names the mutation that turns it red in its docstring; each was
run (`~/Desktop/ChromIQ-beta39-proof/report-window-fixes/mutations.txt`).
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from tests.test_report_shown_is_grouped_by_run_and_project import (  # noqa
    _add, _dated, _dialog, _save_doc, _second_project, _two_runs)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "update")
    monkeypatch.setattr(MeasurementReportDialog, "_confirm",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(MeasurementReportDialog, "_say_generated",
                        lambda self, saved, failed: None)


def _entry_keys(dlg):
    c = dlg._saved_combo
    return [str(c.itemData(i)) for i in range(c.count()) if c.itemData(i)]


def _pick(dlg, key, qapp):
    """A user's pick: the index moves, then `activated` fires."""
    c = dlg._saved_combo
    i = c.findData(key)
    assert i >= 0, (key, _entry_keys(dlg))
    c.setCurrentIndex(i)
    c.activated.emit(i)
    qapp.processEvents()


def _the_list_names_what_is_loaded(dlg):
    shown = str(dlg._saved_combo.currentData() or "")
    assert shown == str(dlg._loaded_doc_id or ""), (
        f"'Report shown' names {shown!r} while the window holds "
        f"{dlg._loaded_doc_id!r}")


# --------------------------------------------------------------------------
# C5
# --------------------------------------------------------------------------
def _one_date_and_a_multi_date_report(tmp_path):
    """Run1 with two dates, a one-date report on each, and a LATER report
    across both whose verdict record sits in the second date's folder, so
    after the second date's own report is deleted the page's newest file
    there belongs to the report across both."""
    from tests.test_import_measurement_module import _verify_env
    s, fm, _ctl, run1 = _verify_env(tmp_path)
    a, b = _dated(run1), _dated(run1)
    _save_doc([b.dir, a.dir], [b.measurement_ti3, a.measurement_ti3])
    return s, run1, a, b


def _one_date_key_of(dlg, v):
    docs = dlg._saved_documents(dlg._run_ctx.run if dlg._run_ctx else None)
    for d in docs:
        dirs = {str(r.get("_origin_dir")) for r, _n in d["members"]}
        if dirs == {str(v.dir)} and not d.get("file"):
            return d["key"]
    raise AssertionError(f"no one-date report of {v.dir}")


def test_after_a_delete_the_shown_entry_is_the_loaded_report(tmp_path, qapp):
    """Challenge C, C5: a report loaded, a setting changed ("Show detailed
    data" flipped), the report deleted. The list lands on the report across
    both dates (the page's newest file); it must be LOADED, whole, with both
    dates ticked, and Generate live, not a page that nobody loaded under a
    name that says otherwise.

    MUTATION, proven red: make `_load_what_the_list_names` return at once
    AND drop the reset of `_doc_settings_moved` in `_on_delete_report` (the
    list names the report across both dates, `_loaded_doc_id` is ""). Each
    of the two alone keeps the list honest; the first is the general rule."""
    s, _run1, a, b = _one_date_and_a_multi_date_report(tmp_path)
    dlg = _dialog(s, b.measurement_ti3, qapp)
    try:
        key_b = _one_date_key_of(dlg, b)
        _pick(dlg, key_b, qapp)
        assert dlg._loaded_doc_id == key_b
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        dlg._on_delete_report()
        qapp.processEvents()
        assert key_b not in _entry_keys(dlg)
        _the_list_names_what_is_loaded(dlg)
        shown = str(dlg._saved_combo.currentData())
        assert shown.startswith("id:"), shown
        assert dlg._loaded_doc is not None
        ticked = {k for kind, _si, k in dlg._list_rows
                  if kind == "run" and k not in dlg._hidden_runs}
        assert len(ticked) == 2, ticked
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
    finally:
        dlg.close()


def test_picking_an_entry_the_window_does_not_hold_loads_it(tmp_path, qapp):
    """C5, the second half: "reselecting the entry does not load it". A pick
    of the entry the list is already on fires `activated` only; it loaded
    the report only when it was ALREADY the loaded one.

    MUTATION, proven red: `if not key or key != self._loaded_doc_id: return`
    back at the head of `_on_saved_picked_again` (nothing is loaded)."""
    s, _run1, a, b = _one_date_and_a_multi_date_report(tmp_path)
    dlg = _dialog(s, b.measurement_ti3, qapp)
    try:
        key_a = _one_date_key_of(dlg, a)
        c = dlg._saved_combo
        c.blockSignals(True)
        c.setCurrentIndex(c.findData(key_a))
        c.blockSignals(False)
        dlg._loaded_doc_id = ""           # the state C5 left the window in
        c.activated.emit(c.currentIndex())
        qapp.processEvents()
        assert dlg._loaded_doc_id == key_a
        _the_list_names_what_is_loaded(dlg)
    finally:
        dlg.close()


def test_a_pick_that_moves_the_index_loads_once(tmp_path, qapp, monkeypatch):
    """A real pick fires `currentIndexChanged` and then `activated`; the
    report is loaded once, not twice.

    MUTATION, proven red: drop the `_pick_just_loaded` check from
    `_on_saved_picked_again` (two loads)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _run1, a, b = _one_date_and_a_multi_date_report(tmp_path)
    dlg = _dialog(s, b.measurement_ti3, qapp)
    try:
        key_a = _one_date_key_of(dlg, a)
        calls = []
        real = MeasurementReportDialog._load_document
        monkeypatch.setattr(MeasurementReportDialog, "_load_document",
                            lambda self, k: (calls.append(k), real(self, k)))
        _pick(dlg, key_a, qapp)
        assert calls == [key_a], calls
    finally:
        dlg.close()


def test_every_delete_leaves_the_list_on_what_is_loaded(tmp_path, qapp):
    """Delete every entry in turn, with a setting changed before each, and
    after every press the entry shown is what the window holds; at the end
    "New report…" with its defaults.

    MUTATION, proven red: as the first test (`_load_what_the_list_names`
    returns at once)."""
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, _run1, a, b = _one_date_and_a_multi_date_report(tmp_path)
    dlg = _dialog(s, b.measurement_ti3, qapp)
    try:
        deleted = 0
        for _n in range(6):
            docs = [k for k in _entry_keys(dlg) if k != NEW_REPORT_KEY]
            live = []
            for k in docs:
                _pick(dlg, k, qapp)
                _the_list_names_what_is_loaded(dlg)
                if dlg._delete_report_btn.isEnabled():
                    live.append(k)
            if not live:
                break
            _pick(dlg, live[0], qapp)
            dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
            qapp.processEvents()
            dlg._on_delete_report()
            qapp.processEvents()
            deleted += 1
            _the_list_names_what_is_loaded(dlg)
            if dlg._saved_combo.currentData() == NEW_REPORT_KEY:
                assert dlg._loaded_doc_id == NEW_REPORT_KEY
        assert deleted >= 2, deleted
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# C6
# --------------------------------------------------------------------------
def _reason_on_screen(dlg):
    return (dlg._generate_why.isVisibleTo(dlg),
            dlg._generate_why_full, dlg._generate_btn.toolTip())


def test_every_greyed_generate_says_why(tmp_path, qapp):
    """§13.13: Generate refuses, and says why. Every path that greys the
    button is driven, and each leaves a reason in its tooltip AND in the
    line beside the buttons; a live button carries neither.

    Paths: (1) only another run's measurement ticked, one source (the C6
    case: a Profiling window lists every run's sheet), which K31 made LIVE
    (Knut, 5801677743: a report is saved where its ticks decide, from any
    window), so it is the control here; (2) nothing ticked;
    (3) no measurement loaded (Clear list); (4) under Calibration, a run's
    measurement only; the others (a measurement outside a project, FC-2,
    a calibration not on disk) have their own tests and reach the same
    last line.

    MUTATION, proven red: `if False:` for the last-reasons block
    (`if not live and not self._generate_btn.toolTip():`) in
    `_sync_type_combo` (paths 2 and 3 grey with no reason), or drop the
    `_set_generate_why` call (no reason on screen). Path 1 with ONE source
    is `test_the_c6_state_one_profiling_source_other_run_ticked`."""
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        dlg._select_all_btn.click()
        qapp.processEvents()
        assert dlg._generate_btn.isEnabled()
        shown, full, tip = _reason_on_screen(dlg)
        assert not shown and not full and not tip, (shown, full, tip)
        # (1) run2's dates only, added into a run1 window as ONE source
        _add(dlg, v2[0].measurement_ti3, qapp)
        mine = {dlg._run_key(r) for r in dlg._history
                if str(r.get("_origin_dir", "")).startswith(str(run1.dir))}
        dlg._hidden_runs = set(mine)
        dlg._sync_limit_controls()
        qapp.processEvents()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        shown, full, tip = _reason_on_screen(dlg)
        assert not shown and not tip, (shown, tip)
        # (2) nothing ticked
        dlg._deselect_all_btn.click()
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled()
        shown, full, tip = _reason_on_screen(dlg)
        assert shown and "No measurement is ticked" in tip, tip
        # (3) nothing loaded
        dlg._on_clear_list()
        qapp.processEvents()
        assert not dlg._generate_btn.isEnabled()
        shown, full, tip = _reason_on_screen(dlg)
        assert shown and "No measurement is loaded" in tip, tip
    finally:
        dlg.close()


def test_the_c6_state_one_profiling_source_other_run_ticked(tmp_path, qapp):
    """The tester's state exactly: a Profiling window on run 1 lists both
    runs' sheets from ONE source; run 2's Printing record selected ticks
    run 2's sheet alone. K31: Generate is LIVE (the report of run 2's sheet
    is saved in run 2), and the labels do not name run 1.

    MUTATION: put the own-run filter back into `_reports_to_generate` (the
    button greys), or drop `and self._ticks_are_the_runs_own(run)` from the
    type label ("Report type (run1):"), and this goes red."""
    from tests.test_calibration_reports import _settings
    from workflow.measurement_report import (REPORT_TYPE_RECORD,
                                             build_report, save_report,
                                             set_report_type)
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from core.file_manager import Project
    proj = Project.create(tmp_path / "P", "P")
    run1 = proj.current_run()
    run1.ensure_dir()
    run2 = proj.new_run()
    run2.ensure_dir()
    for r in (run1, run2):
        t = r.dir / "P.ti3"
        t.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        rep = build_report(t)
        set_report_type(rep, REPORT_TYPE_RECORD)
        save_report(rep, r.dir)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(_settings(), None,
                                  initial_ti3=run1.dir / "P.ti3")
    dlg.show()
    qapp.processEvents()
    try:
        assert len({str(r.get("_origin_dir")) for r in dlg._history}) == 2
        mine = {dlg._run_key(r) for r in dlg._history
                if str(r.get("_origin_dir")) == str(run1.dir)}
        dlg._hidden_runs = set(mine)
        dlg._sync_limit_controls()
        qapp.processEvents()
        assert not dlg._several_runs()
        assert dlg._generate_btn.isEnabled(), dlg._generate_btn.toolTip()
        assert "another profile run" not in dlg._generate_btn.toolTip()
        # and the labels stop naming run 1 (K30 leftover)
        assert dlg._type_label.text() == "Report type:", dlg._type_label.text()
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# C9
# --------------------------------------------------------------------------
def test_no_button_of_the_report_windows_is_the_default(tmp_path, qapp):
    """Challenge C, C9: "Add Profile's Measurements…" was the window's
    default button, so Return anywhere opened its file chooser (10 of 10 on
    screen). No push button of the Measurement Report window, the Report
    limits window or the Reference values window is autoDefault or default
    once shown, and Return in the report window opens nothing.

    MUTATION, proven red: drop the `no_default_button(self)` call from
    `MeasurementReportDialog.showEvent` (the Add button is default and
    Return calls `_on_add_project`), or from `ThresholdsDialog.showEvent`
    ("Reference values…" is autoDefault)."""
    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QPushButton
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    s, _run1, a, _b = _one_date_and_a_multi_date_report(tmp_path)
    opened = []
    dlg = _dialog(s, a.measurement_ti3, qapp)
    try:
        dlg._on_add_project = lambda: opened.append("add")   # no chooser
        dlg._add_btn.clicked.disconnect()
        dlg._add_btn.clicked.connect(dlg._on_add_project)
        bad = [b.text() for b in dlg.findChildren(QPushButton)
               if b.isDefault() or b.autoDefault()]
        assert not bad, bad
        for target in (dlg, dlg._saved_combo, dlg._profile_list):
            ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                           Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(target, ev)
            qapp.processEvents()
        assert opened == [], opened
        th = ThresholdsDialog(s, dlg)
        th.show()
        qapp.processEvents()
        bad = [b.text() for b in th.findChildren(QPushButton)
               if b.isDefault() or b.autoDefault()]
        th.close()
        assert not bad, bad
        rv = ReferenceValuesDialog(th)
        rv.show()
        qapp.processEvents()
        bad = [b.text() for b in rv.findChildren(QPushButton)
               if b.isDefault() or b.autoDefault()]
        rv.close()
        assert not bad, bad
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# C10
# --------------------------------------------------------------------------
def test_an_update_that_changes_what_it_covers_is_still_renamed(tmp_path,
                                                                qapp):
    """§24.2 stands beside C10: an Update that covers FEWER measurements is
    renamed by what it covers ("Multiple dates" to "One date"); only an
    Update over the same measurements keeps its scope.

    MUTATION, proven red: `if False:` for `_document_scope`'s one-member
    line (the one-date Update is named "Multiple dates")."""
    import json
    from workflow.measurement_report import DOCUMENT_BLOCK, SCOPE_ONE_DATE
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    _save_doc([v1[0].dir, v1[1].dir],
              [v1[0].measurement_ti3, v1[1].measurement_ti3])
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        docs = dlg._saved_documents(dlg._run_ctx.run)
        multi = next(d for d in docs if d.get("file"))
        _pick(dlg, multi["key"], qapp)
        dlg._hidden_runs = {dlg._run_key(r) for r in dlg._history
                            if str(r.get("_origin_dir")) != str(v1[0].dir)}
        dlg._sync_limit_controls()
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        doc_id = str((multi.get("doc") or {}).get("id") or "")
        assert doc_id
        scopes = []
        for f in Path(run1.dir).rglob("report_*.json"):
            if "old" in f.parts:
                continue
            blk = json.loads(f.read_text(encoding="utf-8")).get(
                DOCUMENT_BLOCK) or {}
            # K31: an earlier ChromIQ's verdict records are read-only
            # history and keep the block they were written with.
            if blk.get("role") == "record":
                continue
            if blk.get("id") == doc_id:
                scopes.append(blk.get("scope"))
        assert scopes, "the updated report is not on disk"
        assert set(scopes) == {SCOPE_ONE_DATE}, scopes
    finally:
        dlg.close()


def test_the_scope_rule_on_the_document_writer(tmp_path, qapp):
    """The C10 rule on its own: with every measurement of the list ticked
    (2 of 2 here) but the report recording "Multiple dates" over the same
    two, an Update keeps "Multiple dates".

    MUTATION, proven red: as above."""
    import json
    from workflow.measurement_report import (DOCUMENT_BLOCK,
                                             SCOPE_MULTIPLE_DATES)
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    _save_doc([v1[0].dir, v1[1].dir],
              [v1[0].measurement_ti3, v1[1].measurement_ti3])
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        docs = dlg._saved_documents(dlg._run_ctx.run)
        multi = next(d for d in docs if d.get("file"))
        _pick(dlg, multi["key"], qapp)
        ticked = [r for r in dlg._history
                  if dlg._run_key(r) not in dlg._hidden_runs]
        assert len(ticked) == 2 and len(dlg._history) == 2
        dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
        qapp.processEvents()
        dlg._on_generate_report()
        qapp.processEvents()
        body = json.loads(Path(multi["file"]).read_text(encoding="utf-8"))
        assert body[DOCUMENT_BLOCK]["scope"] == SCOPE_MULTIPLE_DATES
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# C12 and the K30 "run" words
# --------------------------------------------------------------------------
def test_already_generated_says_these_measurements_across_projects(
        tmp_path, qapp):
    """Challenge C, C12: a Verification window with another project's date
    in its list counts that project's reports too (K25), and the line said
    "Already generated for this run". It says "for these measurements"
    then, and "for this run" while the list is the run's own.

    MUTATION, proven red: drop `or not self._dirs_are_the_runs_own(run,
    dirs)` from `_generated_types_line`."""
    s, _fm, run1, _run2, v1, _v2 = _two_runs(tmp_path)
    _qrun, qv = _second_project(tmp_path)
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        line = dlg._generated_types_line(dlg._run_ctx.run)
        assert line.startswith("Already generated for this run:"), line
        _add(dlg, qv.measurement_ti3, qapp)
        line = dlg._generated_types_line(dlg._run_ctx.run)
        assert line.startswith("Already generated for these measurements:"), \
            line
    finally:
        dlg.close()


def test_a_calibration_row_counts_measurements_not_runs(tmp_path, qapp):
    """K30 leftover (as B10 put it for the Scope): the Included
    Measurements header of a calibration read "P-cal · 1 run".

    MUTATION, proven red: drop the `if cal else` branch in
    `_rebuild_from_sources` ("· 1 run")."""
    from tests.test_calibration_reports import (_project_with_cal, _settings,
                                                _window)
    _proj, ti3 = _project_with_cal(tmp_path, "P")
    dlg = _window(_settings(), ti3, qapp)
    try:
        head = dlg._profile_list.item(0).text()
        assert "1 measurement" in head and " run" not in head, head
    finally:
        dlg.close()


def test_a_grey_and_tone_check_draws_no_colour_accuracy_limit(tmp_path,
                                                               qapp):
    """K30 leftover, §17 item 4: a limit line sits at the limit the report
    was judged against, and a Grey and tone check judges no colour-accuracy
    row. Its Colour accuracy graph draws neither the Avg nor the Max line,
    and says no line note; a Full colour check still draws both.

    MUTATION, proven red: drop the `not judged(...)` terms from
    `_accuracy_thresholds` (both lines come back)."""
    from workflow.measurement_report import REPORT_TYPE_FULL, REPORT_TYPE_GREY
    s, _fm, _run1, _run2, v1, _v2 = _two_runs(tmp_path)
    dlg = _dialog(s, v1[0].measurement_ti3, qapp)
    try:
        for tid, want in ((REPORT_TYPE_GREY, (None, None)),
                          (REPORT_TYPE_FULL, "numbers")):
            dlg._session_type = tid
            dlg._sticky_type = tid
            dlg._report_type_now = (lambda t=tid: t)
            plan = {e[0]: e for e in dlg._trend_plan()}
            thr = plan[dlg._trend_de][6]
            notes = dlg._trend_extras(dlg._trend_de)["line_notes"]
            if want == "numbers":
                assert all(isinstance(v, (int, float)) for v in thr), thr
                assert any(notes), notes
            else:
                assert tuple(thr) == want, thr
                assert not any(notes), notes
    finally:
        dlg.close()


def test_the_demo_texts_follow_the_shipped_iso_values():
    """K30 leftover, spec §23: the ISO values ship. The release demo README
    and the Custom runs' chart notes no longer say the numbers are
    "placeholders under a permission condition" or that ChromIQ has "no
    permission to include" the standards' figures.

    MUTATION, proven red: put either old sentence back into
    `scripts/make_report_limit_demos.py`."""
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "make_report_limit_demos.py").read_text(encoding="utf-8")
    rel = (Path(__file__).resolve().parent.parent / "scripts"
           / "make_release_demo_package.py").read_text(encoding="utf-8")
    assert "permission condition" not in src
    assert '"no permission to include' not in src
    assert "contains no licensed reference values" not in rel


# --------------------------------------------------------------------------
# GAP 0 (answers-for-knut-v2): a borrowed measurement's own report
# --------------------------------------------------------------------------
def test_picking_a_borrowed_runs_own_report_keeps_it_and_asks(tmp_path, qapp,
                                                              monkeypatch):
    """A Verification window on run 2 opens on a report across run 2 and
    run 1, so run 1's date is BORROWED. Picking run 1's own "One date"
    report unloaded run 1 first: "Report shown" landed on another entry
    while the page showed the picked date, and Generate wrote a NEW report
    without the Update / Create New / Cancel question (K4, confirmed).
    Now the picked report stays listed, shown and loaded, and a press of
    Generate writes nothing unasked (here it is refused with its reason:
    run 1's report belongs to run 1's window).

    MUTATION, proven red: call `self._drop_borrowed_sources()` without
    `keep_for=entry` in `_apply_document` (the list lands elsewhere)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    _save_doc([v2[1].dir, v1[0].dir],
              [v2[1].measurement_ti3, v1[0].measurement_ti3])
    asked = []
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: (asked.append(self._loaded_doc_id),
                                      "cancel")[1])
    dlg = _dialog(s, v2[1].measurement_ti3, qapp)
    try:
        assert any(str(v1[0].dir) in str(t) for t in dlg._borrowed_sources), \
            "the fixture did not open on the report across runs"
        key = _one_date_key_of(dlg, v1[0])
        _pick(dlg, key, qapp)
        assert key in _entry_keys(dlg), "the picked report left the list"
        _the_list_names_what_is_loaded(dlg)
        assert dlg._loaded_doc_id == key
        before = sorted(str(p) for p in Path(run1.dir).parent.rglob(
            "report_*.json") if "old" not in p.parts)
        live = dlg._generate_btn.isEnabled()
        dlg._on_generate_report()
        qapp.processEvents()
        after = sorted(str(p) for p in Path(run1.dir).parent.rglob(
            "report_*.json") if "old" not in p.parts)
        assert after == before, "a press wrote a report without asking"
        if live:
            assert asked == [key], asked
        else:
            # run 1's own report in a run 2 window: refused, and it says so
            assert "another profile run" in dlg._generate_btn.toolTip()
    finally:
        dlg.close()


def test_a_borrowed_measurement_the_user_adds_is_the_users(tmp_path, qapp):
    """GAP 0, the other half: "Add Profile's Measurements…" with a
    measurement a report had borrowed makes it the user's, so "New report…"
    no longer unloads it.

    MUTATION, proven red: drop the `borrowed.discard(...)` in
    `_append_source` (run 1's date leaves the list on "New report…")."""
    s, _fm, run1, run2, v1, v2 = _two_runs(tmp_path)
    _save_doc([v2[1].dir, v1[0].dir],
              [v2[1].measurement_ti3, v1[0].measurement_ti3])
    dlg = _dialog(s, v2[1].measurement_ti3, qapp)
    try:
        assert dlg._borrowed_sources
        _add(dlg, v1[0].measurement_ti3, qapp)
        dlg._saved_combo.setCurrentIndex(0)                # New report…
        qapp.processEvents()
        dirs = {str(r.get("_origin_dir")) for r in dlg._history}
        assert str(v1[0].dir) in dirs, dirs
    finally:
        dlg.close()
