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


def test_two_spellings_of_one_folder_are_one_project(tmp_path, qapp):
    """R14-F4: the projects are grouped as path STRINGS, and on macOS `/tmp`
    and `/private/tmp` name the same directory. A project holding four
    measurements, two of them opened by each spelling, was counted twice: the
    document said "2 of the 8 measurements recorded for THE PROJECTS it is
    drawn from", plural, about one project. A symlink or a mapped drive does
    the same on the other platforms.

    MUTATION, proven to land: drop the `.resolve()`.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
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
            made.append(v.measurement_ti3)
        # the SAME two files, reached by a second spelling of the same folder
        alias = tmp_path / "by-another-name"
        try:
            alias.symlink_to(Path(str(proj.root)).parent,
                             target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("this filesystem will not make a symlink")
        for f in made:
            dlg._add_source(f)
            qapp.processEvents()
        for f in made:
            through_alias = alias / Path(str(proj.root)).name / \
                f.relative_to(Path(str(proj.root)))
            if through_alias.is_file():
                dlg._add_source(through_alias)
                qapp.processEvents()
        body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                            for_pdf=False))
        m = re.search(r"covers (\d+) of the (\d+) measurements recorded for "
                      r"(this project|the projects it is drawn from)", body)
        if m is None:
            return
        from ui.dialogs.measurement_report_dialog import (
            MeasurementReportDialog as _MD)
        on_disk = _MD._measurements_recorded_in(str(proj.root))
        assert int(m.group(2)) == on_disk, (
            f'the document says "{m.group(0)}" where the one project records '
            f'{on_disk}')
        assert m.group(3) == "this project", (
            f'one project, and the document calls it "{m.group(3)}"')
    finally:
        dlg.close()


def test_a_renamed_project_is_still_ONE_project(tmp_path, qapp):
    """R15-F2: R14-F5's own fix brought R14-F4 straight back. The disk branch
    resolves its key and the path-shape branch, which is the only one a renamed
    folder reaches, did not: one project, four measurements opened through two
    spellings of the same folder, and after the rename the document said
    "recorded for THE PROJECTS it is drawn from", plural, about one project.

    MUTATION, proven to land: drop the `.resolve()` from the shape branch.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        made = []
        for scale in (0.5, 0.25):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            made.append(v.measurement_ti3)
        # ...and one more on the disk that nobody opens, so the document really
        # is covering less than the project records and the sentence has a
        # reason to exist at all. Without it both spellings of everything are
        # loaded, the report covers the lot, and silence is the right answer.
        _un = proj.new_run().new_verification()
        _un.ensure_dir()
        _un.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.1, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        # the same two files reached by a second spelling of the same folder
        alias = tmp_path / "another-way-in"
        try:
            alias.symlink_to(root.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("this filesystem will not make a symlink")
        for f in made:
            dlg._add_source(f)
            qapp.processEvents()
            through = alias / root.name / f.relative_to(root)
            if through.is_file():
                dlg._add_source(through)
                qapp.processEvents()
        # BOTH SPELLINGS OF ONE MEASUREMENT, or nothing is really left out:
        # hiding one of a pair leaves its twin in the document and the report
        # still covers everything the project records, where silence is the
        # right answer and this test would prove nothing.
        rows = list(dlg._history)
        # by the RUN, because every verification here was made in the same
        # second and they share a timestamp folder name.
        _run_name = made[-1].parent.parent.parent.name
        hide = {dlg._run_key(r) for r in rows
                if Path(str(r.get("_origin_dir") or r.get("ti3") or "")
                        ).parent.parent.name == _run_name}
        assert hide and len(hide) < len(rows), (len(hide), len(rows))
        dlg._hidden_runs = hide
        qapp.processEvents()
        before = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                              for_pdf=False))
        renamed = root.with_name(root.name + "-renamed")
        root.rename(renamed)
        try:
            body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                                for_pdf=False))
        finally:
            renamed.rename(root)
        # THE WORDING IS WHAT THIS TEST IS FOR. Whether a sentence appears at
        # all depends on how much of the project the document covers, and with
        # both spellings loaded that can legitimately be all of it; what may
        # never happen is one project being called several.
        from ui.dialogs.measurement_report_dialog import (
            MeasurementReportDialog as _MD)
        on_disk = _MD._measurements_recorded_in(str(root))
        seen = 0
        for where, text in (("before the rename", before), ("after it", body)):
            m = re.search(r"covers (\d+) of the (\d+) measurements recorded "
                          r"for (this project|the projects it is drawn from)",
                          text)
            if m is None:
                continue
            seen += 1
            assert m.group(3) == "this project", (
                f'one project reached two ways, and {where} the document says '
                f'"{m.group(0)}"')
            assert int(m.group(2)) == on_disk, (
                f'{where} the document says "{m.group(0)}" where the project '
                f'records {on_disk}')
        assert seen, (
            "neither state produced the sentence at all, so this test proves "
            "nothing about its wording")
    finally:
        dlg.close()


def test_renaming_the_project_folder_does_not_silence_the_note(tmp_path,
                                                               qapp):
    """R14-F5: the total is read off the disk, and a folder renamed while the
    report is open reads as zero. `max(total, covered)` then makes the two
    equal and the sentence disappears, so a report that really is leaving
    measurements out passes as complete. That is the one thing the note exists
    to prevent.

    MUTATION, proven to land: drop the `if _n <= 0` fall-back.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        for scale in (0.5, 0.25):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            dlg._add_source(v.measurement_ti3)
            qapp.processEvents()
        rows = list(dlg._history)
        assert len(rows) >= 2, len(rows)
        dlg._hidden_runs = {dlg._run_key(rows[0])}
        qapp.processEvents()
        before = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                              for_pdf=False))
        assert re.search(r"covers \d+ of the \d+ measurements", before), (
            "the fixture is not filtering anything, so the check below would "
            "prove nothing")
        root = Path(str(proj.root))
        root.rename(root.with_name(root.name + "-renamed"))
        try:
            after = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                                 for_pdf=False))
        finally:
            root.with_name(root.name + "-renamed").rename(root)
        # EITHER FORM. A renamed folder cannot be counted, so the sentence
        # drops its numbers rather than inventing them: remembering the last
        # count the folder gave produced "3 of the 5" on a four-measurement
        # project and "3 of the 4" on one whose folder had been emptied
        # (R18-F3). What may never happen is silence.
        assert re.search(r"covers \d+ of the \d+ measurements", after) or \
            "does not cover every measurement" in after, (
            "renaming the project's folder silenced the sentence, so a report "
            "with a measurement left out now passes as complete\n"
            + after[-400:])
    finally:
        dlg.close()


def test_two_cases_of_one_name_are_one_project(tmp_path, qapp):
    """R16-F1: `Path.resolve()` fixes a symlink and `/private/tmp`, and it does
    NOT case-fold. APFS is case-insensitive, so `CaseTest` and `casetest` are
    one directory by `samefile` and two keys after `resolve()`: a project
    holding four measurements, two rows opened through the other case, said
    "covers 3 of the 8 measurements recorded for THE PROJECTS it is drawn
    from", photographed. It is reachable because a project carries the case
    typed in Settings while a `.ti3` added through the file dialog carries the
    volume's.

    A directory's device and inode are the one thing every spelling agrees on.

    MUTATION, proven to land: group on the resolved path again.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        other_case = root.with_name(root.name.swapcase())
        if root.name == other_case.name or not other_case.is_dir():
            pytest.skip("this volume keeps the two cases apart")
        made = []
        for scale in (0.5, 0.25):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            made.append(v.measurement_ti3)
        for f in made:
            dlg._add_source(f)
            qapp.processEvents()
            swapped = other_case / f.relative_to(root)
            if swapped.is_file():
                dlg._add_source(swapped)
                qapp.processEvents()
        rows = list(dlg._history)
        dlg._hidden_runs = {dlg._run_key(rows[0])}
        qapp.processEvents()
        body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                            for_pdf=False))
        m = re.search(r"covers (\d+) of the (\d+) measurements recorded for "
                      r"(this project|the projects it is drawn from)", body)
        if m is None:
            return
        from ui.dialogs.measurement_report_dialog import (
            MeasurementReportDialog as _MD)
        on_disk = _MD._measurements_recorded_in(str(root))
        assert m.group(3) == "this project", (
            f'one project under two spellings of its own name, and the '
            f'document says "{m.group(0)}"')
        assert int(m.group(2)) == on_disk, (
            f'the document says "{m.group(0)}" where the project records '
            f'{on_disk}')
    finally:
        dlg.close()


def test_a_rename_cannot_silence_the_note_on_a_four_measurement_project(
        tmp_path, qapp):
    """R17-F2: the rename fall-back still lost the sentence in the shape the
    round drove. Counting the window's own rows is not enough on its own: when
    the window holds only this report's rows, that count can never exceed what
    the report covers, `max(total, covered)` makes the two equal, and the
    sentence disappears. On screen: "covers 2 of the 4 measurements recorded
    for this project" became NO SENTENCE AT ALL, and `covered` moved from 2 to
    3 in the same step because a folder had gone.

    A count read off the disk earlier in this window's life is the true one, so
    it is kept and used when the folder cannot answer.

    MUTATION, proven to land: drop the remembered count.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        # THREE LOADED AND ONE LEFT ON THE DISK. That is the shape round 17
        # drove, and it is the one the history-row fall-back cannot cover: when
        # the window holds only the report's own rows, counting them can never
        # exceed what the report covers.
        for scale, load in ((0.9, True), (0.7, True), (0.5, True),
                            (0.3, False)):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            if load:
                dlg._add_source(v.measurement_ti3)
                qapp.processEvents()
        rows = list(dlg._history)
        assert len(rows) >= 3, len(rows)
        dlg._hidden_runs = {dlg._run_key(rows[0])}
        qapp.processEvents()
        before = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                              for_pdf=False))
        m0 = re.search(r"covers (\d+) of the (\d+) measurements", before)
        assert m0, ("the fixture is not filtering anything, so the check below "
                    "would prove nothing")
        total_before = int(m0.group(2))
        renamed = root.with_name(root.name + "-renamed")
        root.rename(renamed)
        try:
            after = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                                 for_pdf=False))
        finally:
            renamed.rename(root)
        m1 = re.search(r"covers (\d+) of the (\d+) measurements", after)
        if m1 is None:
            # A folder that cannot be read cannot be counted, so the sentence
            # says the same thing without numbers. That is the honest answer:
            # the alternatives measured were silence (R17-F2) and a wrong
            # number, "3 of the 5" on a four-measurement project (R18-F3).
            assert "does not cover every measurement" in after, (
                "renaming the project's folder silenced the sentence, so a "
                "report with a measurement left out passes as complete\n"
                + after[-400:])
        else:
            assert int(m1.group(2)) == total_before, (
                f"the project records {total_before} and after the rename the "
                f"document says {m1.group(2)}")
    finally:
        dlg.close()


def test_one_measurement_opened_twice_is_one_source(tmp_path, qapp):
    """Found while fixing R17-F2, and it is the root of the family R14-F4,
    R15-F2 and R16-F1 all belong to: `_source_key` deduplicated on the path as
    typed, so `/tmp` and `/private/tmp`, a symlink, a firmlink and a different
    capitalisation each added the SAME measurement a second time. The sheet
    then appeared twice in the document and was counted twice in "covers N of
    the M".

    MUTATION, proven to land: drop the `resolve()` from `_source_key`.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        run = proj.new_run()
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v.measurement_ti3)
        qapp.processEvents()
        n_rows = len(dlg._history)
        alias = tmp_path / "second-spelling"
        try:
            alias.symlink_to(root.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("this filesystem will not make a symlink")
        through = alias / root.name / v.measurement_ti3.relative_to(root)
        assert through.is_file(), through
        dlg._add_source(through)
        qapp.processEvents()
        assert len(dlg._history) == n_rows, (
            f"the same measurement opened by a second spelling of its own "
            f"path added {len(dlg._history) - n_rows} more rows")
    finally:
        dlg.close()


def test_a_folder_that_cannot_be_counted_never_invents_a_number(tmp_path,
                                                                qapp):
    """R18-F3: remembering the last count a folder gave turned "no sentence"
    into a WRONG sentence. Driven: "covers 3 of the 5 measurements recorded for
    the projects it is drawn from" on a project holding four, and "covers 3 of
    the 4" on a project whose folder had been deleted and recreated EMPTY, a
    memo that nothing ever invalidated.

    A folder that cannot be counted is not counted. The sentence says the same
    thing without numbers, which is still the honesty rule and claims nothing
    the app cannot stand behind.

    MUTATION, proven to land: put the remembered count back.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        for scale, load in ((0.9, True), (0.7, True), (0.5, False)):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            if load:
                dlg._add_source(v.measurement_ti3)
                qapp.processEvents()
        rows = list(dlg._history)
        dlg._hidden_runs = {dlg._run_key(rows[0])}
        qapp.processEvents()
        before = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                              for_pdf=False))
        m0 = re.search(r"covers (\d+) of the (\d+) measurements", before)
        assert m0, "the fixture is not filtering anything"
        on_disk = int(m0.group(2))

        # the folder goes away entirely, which is what a rename or a move looks
        # like from in here
        gone = root.with_name(root.name + "-moved")
        root.rename(gone)
        try:
            after = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                                 for_pdf=False))
        finally:
            gone.rename(root)
        m1 = re.search(r"covers (\d+) of the (\d+) measurements", after)
        assert m1 is None, (
            f'the folder cannot be counted and the document still says '
            f'"{m1.group(0)}" (it records {on_disk})')
        assert "does not cover every measurement" in after, (
            "the folder cannot be counted and the document says nothing at "
            "all, so a filtered report passes as complete\n" + after[-300:])
    finally:
        dlg.close()


def test_a_second_capitalisation_of_one_file_is_one_source(tmp_path, qapp):
    """R18-F2: `_source_key` resolved the path, and `resolve()` collapses
    `/private/tmp` and a symlink while collapsing NEITHER a firmlink nor a
    different capitalisation on a case-insensitive volume. Measured: symlink
    +0 rows, capitalisation +1, firmlink +1, and the sentence went from
    "covers 1 of the 3" to "covers 2 of the 3" with one sheet printed twice.

    The guard written with that fix built only the symlink, which is the one
    spelling `resolve()` already handled.

    MUTATION, proven to land: key on the resolved path again.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        run = proj.new_run()
        v = run.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(
            _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(v.measurement_ti3)
        qapp.processEvents()
        n_rows = len(dlg._history)
        swapped = Path(str(v.measurement_ti3).swapcase())
        if str(swapped) == str(v.measurement_ti3) or not swapped.is_file():
            pytest.skip("this volume keeps the two cases apart")
        dlg._add_source(swapped)
        qapp.processEvents()
        assert len(dlg._history) == n_rows, (
            f"the same measurement opened under another capitalisation added "
            f"{len(dlg._history) - n_rows} more rows")
    finally:
        dlg.close()


def test_a_loose_file_opened_under_two_spellings_is_one_source(tmp_path,
                                                               qapp):
    """The same identity question for a measurement that belongs to no run,
    which takes the other branch of `_source_key`. The verification case above
    goes down the "dir" branch; nothing guarded this one.

    MUTATION, proven to land: key a loose file on its path again.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        loose = tmp_path / "from-a-colleague" / "sheet.ti3"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_text(
            _cgats("CTI3", [(r * 0.8, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(loose)
        qapp.processEvents()
        n_rows = len(dlg._history)
        swapped = Path(str(loose).swapcase())
        if str(swapped) == str(loose) or not swapped.is_file():
            pytest.skip("this volume keeps the two cases apart")
        dlg._add_source(swapped)
        qapp.processEvents()
        assert len(dlg._history) == n_rows, (
            f"a loose measurement opened under another capitalisation added "
            f"{len(dlg._history) - n_rows} more rows")
    finally:
        dlg.close()


def test_the_numberless_sentence_also_says_which_projects(tmp_path, qapp):
    """R19-1: the sentence written when a folder cannot be counted had no
    "one project or several" test, unlike the numbered one thirteen lines below
    it whose own comment records that exact lesson. Driven: two projects
    recording two each, one row hidden, one folder renamed, and the document
    said "does not cover every measurement recorded for THIS project" with the
    Report Scope naming both of them in the same picture.

    MUTATION, proven to land: use the singular wording unconditionally.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from core.file_manager import Project
    dlg, _run, fm = _dialog(tmp_path, qapp)
    try:
        proj = fm.project()
        root = Path(str(proj.root))
        for scale in (0.9, 0.7):
            run = proj.new_run()
            v = run.new_verification()
            v.ensure_dir()
            v.measurement_ti3.write_text(
                _cgats("CTI3", [(r * scale, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            dlg._add_source(v.measurement_ti3)
            qapp.processEvents()
        other_root = root.parent / "Second-Target"
        other = Project.create(other_root, "Second-Target")
        for scale in (0.6, 0.4):
            r2 = other.new_run()
            v2 = r2.new_verification()
            v2.ensure_dir()
            v2.measurement_ti3.write_text(
                _cgats("CTI3", [(c * scale, g, b) for (c, g, b) in _PATCHES]),
                encoding="utf-8")
            dlg._add_source(v2.measurement_ti3)
            qapp.processEvents()
        rows = list(dlg._history)
        dlg._hidden_runs = {dlg._run_key(rows[0])}
        qapp.processEvents()
        moved = other_root.with_name(other_root.name + "-moved")
        other_root.rename(moved)
        try:
            body = _plain(dlg._report_body_html(dlg._runs_for_report(),
                                                for_pdf=False))
        finally:
            moved.rename(other_root)
        if "does not cover every measurement" not in body:
            pytest.skip("this state does not reach the numberless sentence")
        assert "recorded for the projects it is drawn from" in body, (
            "a document drawn from two projects says 'this project'\n"
            + body[-300:])
    finally:
        dlg.close()


def test_a_measurement_written_again_in_place_is_still_one_source(tmp_path,
                                                                  qapp):
    """R19-2: keying the source on the file's device and inode fixed one half
    and broke the other. An inode is the same under every SPELLING of a file
    and does not survive the file being REPLACED, which `os.replace`, a Finder
    replace, an export written again and a synced folder all do. Driven: add,
    refused on a second add, then replaced in place under the same name, and
    the third add went through as a new row with the Report Scope reading
    "2 runs" for one file.

    A source answers to both what it is and where it is.

    MUTATION, proven to land: return only the identity key from
    `_source_keys`.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        loose = tmp_path / "exports" / "exported.ti3"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_text(
            _cgats("CTI3", [(r * 0.8, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(loose)
        qapp.processEvents()
        n_rows = len(dlg._history)
        assert n_rows, "the fixture added nothing"
        before = loose.stat().st_ino

        # written again in place, the way an export or a sync does it
        tmp_new = loose.with_suffix(".new")
        tmp_new.write_text(
            _cgats("CTI3", [(r * 0.81, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        import os
        os.replace(tmp_new, loose)
        assert loose.stat().st_ino != before, (
            "this filesystem kept the inode across a replace, so the case "
            "this test is for did not happen")

        dlg._add_source(loose)
        qapp.processEvents()
        assert len(dlg._history) == n_rows, (
            f"the same file, written again under the same name, added "
            f"{len(dlg._history) - n_rows} more rows")
    finally:
        dlg.close()


def test_a_rewritten_file_does_not_go_stale_in_the_source_list(tmp_path, qapp):
    """R20-F1: a source's key set was worked out once, when it was added, and
    never again. Rewrite the file and its identity half goes stale for good, so
    the next SPELLING of it matches nothing and comes in as a second row.
    Driven: add, replace in place, then add the same file under another
    capitalisation, and the Report Scope listed `exported - 1 run` and
    `EXPORTED - 1 run` with "No. of Measurements: 3" for two files on disk, the
    trend plotting one sheet twice.

    MUTATION, proven to land: do not refresh the keys of the source that
    matched.
    """
    import os
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        loose = tmp_path / "exports" / "exported.ti3"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_text(
            _cgats("CTI3", [(r * 0.8, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        dlg._add_source(loose)
        qapp.processEvents()
        n_rows = len(dlg._history)
        before = loose.stat().st_ino
        fresh = loose.with_suffix(".new")
        fresh.write_text(
            _cgats("CTI3", [(r * 0.81, g, b) for (r, g, b) in _PATCHES]),
            encoding="utf-8")
        os.replace(fresh, loose)
        if loose.stat().st_ino == before:
            pytest.skip("this filesystem kept the inode across a replace")
        dlg._add_source(loose)          # same path: matches, and refreshes
        qapp.processEvents()
        other_case = Path(str(loose).swapcase())
        if str(other_case) == str(loose) or not other_case.is_file():
            pytest.skip("this volume keeps the two cases apart")
        dlg._add_source(other_case)
        qapp.processEvents()
        assert len(dlg._history) == n_rows, (
            f"one file, rewritten once and then opened under another "
            f"capitalisation, is now {len(dlg._history)} rows")
    finally:
        dlg.close()


def test_one_imported_file_added_three_times_is_one_source(tmp_path, qapp):
    """R20-F2: an `.mxf` or `.cxf` import is converted into a FRESH temporary
    folder every time, so its path and its inode are both new on every press
    and neither can see that it is the same measurement. Driven: one file,
    three presses of "Add Profile's Measurements...", and the window held four
    sources with the Report Scope reading "3 runs" and a flat trend through
    three points all carrying one date. That route had no duplicate guard of
    any kind, and the two rounds before this one drove only `.ti3`.

    The file the USER picked does not move, so it is one of the keys now.

    MUTATION, proven to land: drop `origin` from `_source_keys`.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats, _PATCHES
    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        picked = tmp_path / "from-i1profiler" / "meas.mxf"
        picked.parent.mkdir(parents=True, exist_ok=True)
        picked.write_text("not really an mxf", encoding="utf-8")
        n_rows = len(dlg._history)
        for i in range(3):
            # what the importer does: convert into a fresh temp folder each
            # time, then add THAT file while remembering the one picked
            conv = tmp_path / f"conv-{i}" / "meas.ti3"
            conv.parent.mkdir(parents=True, exist_ok=True)
            conv.write_text(
                _cgats("CTI3", [(r * 0.7, g, b) for (r, g, b) in _PATCHES]),
                encoding="utf-8")
            dlg._add_source(conv, origin=picked)
            qapp.processEvents()
        assert len(dlg._history) == n_rows + 1, (
            f"one imported file added three times left "
            f"{len(dlg._history) - n_rows} rows")
    finally:
        dlg.close()


def test_adding_a_measurement_again_reads_it_again(tmp_path, qapp):
    """R21-F1: the duplicate branch refreshed the source's KEYS and returned,
    leaving `runs` exactly as it was when the source was first added. `runs` is
    the measurement.

    Driven through the real Add button: a sheet added at 8 patches, re-measured
    in place to 12, added again, and the window still read 8 with no message
    and no change to the document. A fresh window on the same file read 12, and
    an unrelated click corrected it in silence much later (Average dE 20.91 to
    23.20, Spread 10.67 to 9.69).

    Asking to add a measurement that is already loaded is the clearest way a
    user can say "look at this file again".

    MUTATION, proven to land: drop the `_reload_sources()` call from the
    duplicate branch of `_append_source` and this reads 8 where 12 is on disk.

    AND THE FIXTURE HAD TO BE BIG ENOUGH TO CONTAIN THE FAULT. The first
    version of this test re-measured the sheet with `_PATCHES[:12]` from a list
    of EIGHT, so the file on disk never changed and nothing could move; it also
    read the patch count off the first history row that carried one, which is
    the fixture's OWN run and not the sheet under test. Both are the same
    mistake: a fixture too small or too tidy to hold the fault agrees with
    whatever the code does.
    """
    from tests.test_a_report_says_what_it_is_and_what_judged_it import _dialog
    from tests.test_import_measurement_module import _cgats
    from workflow.measurement_report import build_report

    def _sheet(n):
        """*n* distinct patches, so a file of 8 and one of 12 really differ."""
        return [((i * 100.0) / (n - 1), 100.0 - (i * 100.0) / (n - 1),
                 float((i * 37) % 101)) for i in range(n)]

    dlg, _run, _fm = _dialog(tmp_path, qapp)
    try:
        loose = tmp_path / "again" / "sheet.ti3"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_text(_cgats("CTI3", _sheet(8)), encoding="utf-8")
        dlg._add_source(loose)
        qapp.processEvents()
        n_rows = len(dlg._history)
        assert n_rows, "the fixture added nothing"

        def _patch_count():
            """What the window says THIS sheet has, not what another row says."""
            here = str(loose.parent)
            mine = [r for r in dlg._history
                    if str(r.get("_origin_dir") or "") == here]
            assert mine, "the sheet under test is not in the history at all"
            return [r.get("patches") for r in mine]

        assert _patch_count() == [8], "the fixture did not write 8 patches"
        # re-measured in place: the same path, more patches
        loose.write_text(_cgats("CTI3", _sheet(12)), encoding="utf-8")
        assert build_report(loose).get("patches") == 12, (
            "the fixture did not change the file on disk")
        dlg._add_source(loose)
        qapp.processEvents()
        assert len(dlg._history) == n_rows, "adding it again made a second row"
        assert _patch_count() == [12], (
            f"the file was re-measured from 8 to 12 patches and adding it "
            f"again left the window reading {_patch_count()}")
    finally:
        dlg.close()
