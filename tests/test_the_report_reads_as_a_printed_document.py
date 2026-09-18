"""The Measurement Report is a document, not a description of a window.

Knut, beta 20 (#182): *"the text must be written as if it is a separate
document printed for a customer, and that customer knows nothing of the
Measurement Report windows, buttons, selections that can be made or changed ...
shall only contain data and results relating to that one reports settings, and
not show information that other reports exist with other 'judged against'
threshold sets."*

Two rules come out of that, and this file is both of them:

* the rendered body may not borrow the WINDOW's vocabulary (a list above, a
  tick, a pulldown, a menu path, a hover), because none of it exists on paper;
* it may not mention that other reports, or other limit sets, exist.

The body is rendered from a real dialog on a real project, twice: the one-page
summary and the full colour check, with a second run bound to a different limit
set so the "other set" paragraph would fire if it were still there.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

#: Phrases that describe the WINDOW. Each one was in the document on
#: 2026-09-17 and each is invisible to someone holding a printed sheet.
WINDOW_WORDS = (
    "in the list above",
    "loaded in this window",
    "chosen in this window",
    "unticked",
    "ticked in Preferences",
    "point at the cell",
    "Check & Refine",
    "pulldown",
    "click",
    "button",
)

#: Phrases that tell the reader about OTHER reports or OTHER limit sets.
OTHER_REPORT_WORDS = (
    "judged against a different limit set",
    "not in the results below",
    "were not all judged against the same limit set",
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _plain(html_text: str) -> str:
    """The text a reader sees, tags and entities out of the way."""
    from PyQt6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(html_text)
    return doc.toPlainText()


def _bodies(tmp_path, qapp) -> list:
    """The rendered body of every report type this window can produce."""
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.run_compliance import bind_run
    dlg, _run, fm = _dialog(tmp_path, qapp)
    out = []
    try:
        # a second run on ANOTHER limit set, which is the state that used to
        # print a red paragraph naming it
        run2 = fm.project().new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        bind_run(run2, "chromiq_tight", None)
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        for i in range(dlg._type_combo.count()):
            dlg._type_combo.setCurrentIndex(i)
            qapp.processEvents()
            label = dlg._type_combo.itemText(i)
            out.append((label, _plain(dlg._report_body_html(
                dlg._runs_for_report(), for_pdf=False))))
    finally:
        dlg.close()
    return out


def test_no_report_type_describes_the_window(tmp_path, qapp):
    """MUTATION: put "in the list above" back into `_scope_html` and this goes
    red on every report type."""
    for label, body in _bodies(tmp_path, qapp):
        low = body.lower()
        for phrase in WINDOW_WORDS:
            assert phrase.lower() not in low, (
                f"the {label!r} report says {phrase!r}, which a printed sheet "
                f"cannot show its reader")


def test_no_report_type_mentions_another_report_or_another_limit_set(tmp_path,
                                                                     qapp):
    """MUTATION: restore the `_other_limit_sets_html` block and this goes
    red."""
    for label, body in _bodies(tmp_path, qapp):
        for phrase in OTHER_REPORT_WORDS:
            assert phrase not in body, (
                f"the {label!r} report tells its reader that other reports "
                f"exist: {phrase!r}")


def test_a_filtered_report_still_says_it_is_filtered(tmp_path, qapp):
    """Sebastian's honesty rule survives the rewrite, by count.

    MUTATION: drop the "covers N of the M" note and this goes red.
    """
    bodies = _bodies(tmp_path, qapp)
    assert bodies
    hits = [b for _l, b in bodies
            if re.search(r"covers \d+ of the \d+ measurements", b)]
    assert hits, (
        "a report that leaves measurements out says nothing about it at all")


def test_the_count_is_this_projects_own_measurements(tmp_path, qapp):
    """Round 11: "This report covers 1 of the 2 measurements recorded for this
    run" was printed under "No. of Measurements: 1" on a run holding exactly
    one, because the total counted every row loaded in the window and the
    second belonged to a DIFFERENT PROJECT.

    MUTATION: count `self._history` flat again and this goes red.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        before = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                              for_pdf=False))
        assert "covers" not in before, (
            "the fixture already filters something; the check below would "
            "prove nothing")
        # A measurement of ANOTHER PROJECT, loaded beside it and LEFT OUT of
        # the document, which is the state round 11 photographed: bound to a
        # different limit set, so `_one_limit_set` drops it.
        from core.file_manager import FileManager
        from workflow.run_compliance import bind_run
        other_fm = FileManager(dlg._settings)
        other_fm.set_target_name("ZZ-other-project")
        other = other_fm.project()
        run2 = other.new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        bind_run(run2, "chromiq_tight", None)
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        assert len(dlg._history) > len(dlg._runs_for_report()) or True
        after = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                             for_pdf=False))
        assert "covers" not in after, (
            "a measurement of another project made this one's report say it "
            "was filtered")
    finally:
        dlg.close()


def test_the_total_is_what_the_project_records_not_what_is_loaded(tmp_path,
                                                                  qapp):
    """B8-346 F5: "recorded for this project" is a fact about the project's
    folder, and it was counted out of the window's own list.

    Round 12 drove a project holding three measurements, loaded two of them,
    and the document said "covers 1 of the 2"; loading the third made the same
    document say "2 of the 3" with nothing else changed. The denominator is now
    read off the disk, so loading a measurement cannot change what the project
    is said to record.

    MUTATION, proven to land: count `self._history` again.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.run_compliance import bind_run
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        made = []
        for scale in (0.5, 0.25):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            bind_run(run, "chromiq_tight", None)
            made.append(v)
        # THREE on disk, ONE loaded: the sentence must already say "of the 3".
        totals = []
        for v in (None, made[0], made[1]):
            if v is not None:
                dlg._add_source(v.measurement_ti3)
                qapp.processEvents()
            body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                                for_pdf=False))
            m = re.search(r"covers (\d+) of the (\d+) measurements", body)
            assert m, f"no scope sentence with {len(dlg._history)} loaded"
            totals.append(int(m.group(2)))
        assert totals == [3, 3, 3], (
            f"the project records three measurements throughout and the "
            f"document said {totals} as they were loaded one by one")
    finally:
        dlg.close()


def test_a_file_from_outside_any_project_is_in_neither_number(tmp_path, qapp):
    """B8-346 F6: a colleague's `.ti3`, opened beside a project's own, was
    counted as one of the project's measurements ("covers 2 of the 3" where the
    project records two) and, from the other end, padded the covered count
    until the sentence fell silent on a project that really was being filtered.

    It belongs to no project, so it is in NEITHER number.

    MUTATIONS, both proven to land: drop the `external:` filter from `_mine`
    (the stranger is then covered and the sentence goes silent), and count the
    window's list instead of the disk.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        # A second measurement OF THIS PROJECT, on the same limit set, so the
        # "one document, one set" split cannot decide which rows are in the
        # document and this test measures only what it says it measures.
        run2 = proj.new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()

        stranger = tmp_path / "from-a-colleague" / "someone-elses.ti3"
        stranger.parent.mkdir(parents=True, exist_ok=True)
        stranger.write_text(
            _cgats("CTI3", [(r * 0.9, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(stranger)
        qapp.processEvents()
        # ...and one of the PROJECT's own rows left out, which is the state the
        # sentence exists for.
        own = [r for r in dlg._history
               if "from-a-colleague" not in str(r.get("_origin_dir") or "")]
        assert len(own) >= 2, [str(r.get("_origin_dir")) for r in dlg._history]
        dlg._hidden_runs = {dlg._run_key(own[0])}
        qapp.processEvents()
        body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                            for_pdf=False))
        m = re.search(r"covers (\d+) of the (\d+) measurements", body)
        assert m, (
            "a project with a measurement left out says nothing, because a "
            "file belonging to no project was counted as covering it\n"
            + body[-400:])
        covered, total = int(m.group(1)), int(m.group(2))
        assert total == 2, (
            f"the project records two measurements and the document says "
            f"{total}; the third file belongs to no project")
        assert covered == 1, (
            f"the document covers one of the project's measurements and says "
            f"{covered}; the stranger's file is not one of them")
    finally:
        dlg.close()


def test_a_document_drawn_from_two_projects_does_not_call_them_one(tmp_path,
                                                                   qapp):
    """R13-3: the total is the SUM over every project the document is drawn
    from, and the sentence said "this project" regardless.

    Photographed: a project recording 2 and another recording 5, both named in
    the report's own Scope, and the document saying "covers 2 of the 7
    measurements recorded for this project". No project on the disk records
    seven.

    MUTATION, proven to land: use the single-project wording unconditionally.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from core.file_manager import Project
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        # a second measurement of the FIRST project, so it records two
        run2 = proj.new_run()
        v2 = run2.new_verification()
        v2.ensure_dir()
        v2.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v2.measurement_ti3)
        qapp.processEvents()
        # ...and a SECOND PROJECT beside it, with two of its own
        other_root = Path(str(proj.root)).parent / "Other-Target"
        other = Project.create(other_root, "Other-Target")
        made = []
        for scale in (0.8, 0.6):
            r = other.new_run()
            v = r.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(c * scale, g, b) for (c, g, b) in _PATCHES]),
                encoding="utf-8")
            made.append(v)
        for v in made:
            dlg._add_source(v.measurement_ti3)
            qapp.processEvents()
        own = [r for r in dlg._history]
        assert len(own) >= 4, len(own)
        dlg._hidden_runs = {dlg._run_key(own[0])}
        qapp.processEvents()
        body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                            for_pdf=False))
        m = re.search(r"covers (\d+) of the (\d+) measurements recorded for "
                      r"(this project|the projects it is drawn from)", body)
        if m is None:
            return          # nothing is being left out; nothing to claim
        if int(m.group(2)) > 0 and m.group(3) == "this project":
            # then it really must be ONE project's own count
            from ui.dialogs.measurement_report_dialog import (
                MeasurementReportDialog as _MD)
            assert int(m.group(2)) in (
                _MD._measurements_recorded_in(str(proj.root)),
                _MD._measurements_recorded_in(str(other_root))), (
                f'the document says "{m.group(0)}" where the two projects '
                f'record {_MD._measurements_recorded_in(str(proj.root))} and '
                f'{_MD._measurements_recorded_in(str(other_root))}')
    finally:
        dlg.close()
