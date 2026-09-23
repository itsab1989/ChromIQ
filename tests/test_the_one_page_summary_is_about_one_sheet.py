"""The page you hand over must be about the sheet you are handing over.

T1, "Colour summary (one page)", is the document Knut described as going out
with a job: *"a very short overview of accuracy of a selection of colors, with
some statistics, that can be printed out for every job."* One job, one printed
sheet, one page.

It was reading `runs[0]`. With "Show all measurement runs" ticked — the ordinary
state for any run measured more than once — `_runs_for_report` hands back the
whole history, oldest first. Measured on two dated verifications of one run: the
Report Scope said "2 verification runs" over a date range covering both, and the
verdict, the example colours and the cube corners under it all came from the
OLDER sheet, with nothing on the page saying which one it was describing.

Two rules now, and this file holds both:

* the page describes the measurement the window is ON, and the Report Scope is
  given that same single item, so the heading and the numbers agree;
* a press of "Generate report" with more than one measurement ticked is
  REFUSED, with M-REPORT-ONE-PAGE-ONE-DATE saying why and no tick moved.

**THE SECOND RULE USED TO BE A DISABLED CONTROL, AND THAT WAS THE FAULT
(B8-590/B8-591).** It read: *"the tick box that widens every other report is
disabled while T1 is chosen, rather than left on screen doing nothing"*. That
box was "Show all measurement runs", and Knut removed it and the feature behind
it on 2026-09-20: *"Remove the feature 'Show all measurement runs' totally from
the design, and any feature that belongs to that button … only the
selected/ticked measurements shall be part of the report when created/updated
(always)."* Its replacement, a disabled measurement LIST, is what he reported
next, in the same batch: *"Then the 'included measurements in report' became
unticked for all measurements and it froze, so I cannot scroll or select."*

So nothing is taken away from the user here any more. The list stays live, it
keeps showing the ticks it really holds, and the one-page summary says at
Generate what it can carry: *"the user should be informed … Then the user can
close that message and do the changes, and then click generate report again."*
Every check below that used to tick "Show all measurement runs" presses
"Select all" instead, which is what covering the whole history means now.

And the sentence that owns up to a filtered report counts what the USER
unticked. It was `len(history) - len(shown)`, which is the same number only
while the ticks are the only thing that narrows a report — so the one-page
summary made it accuse a user who had unticked nothing.
"""
from __future__ import annotations

import re

import pytest

import workflow.measurement_report as mr

pytestmark = pytest.mark.usefixtures("qapp")


def _text(html: str) -> str:
    return " ".join(re.sub("<[^>]+>", " ", html).split())


def _cover_only_the_sheet_on_screen(dlg, qapp):
    """Untick every row EXCEPT the measurement the window is on.

    The one-page summary is about one sheet, and since B8-591 that is a state
    the USER puts the list in rather than one the window imposes.

    **THE OTHER ROWS ARE UNTICKED ONE BY ONE, AND NOT THROUGH "Deselect
    all".** Both reach the same ticks, but the button passes through a state
    where NOTHING is ticked, and a repaint taken there re-stamps
    `_doc_built_with` from it: putting the last tick back then leaves the
    window saying the settings have moved when they are exactly where the
    document was built, and Generate asks "Update or Create New?" about a
    document nobody changed. That is a fault in its own right and is reported
    separately; it is not what these checks are about, and unticking the rows
    you do not want is what a reader does anyway.
    """
    from PyQt6.QtCore import Qt
    here = dlg._run_key(dlg._report)
    found = False
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind != "run" or key is None:
            continue
        if key == here:
            found = True
            continue
        dlg._profile_list.item(i).setCheckState(Qt.CheckState.Unchecked)
    qapp.processEvents()
    assert found, f"the window's measurement has no row: {here!r}"
    assert [dlg._run_key(r) for r in dlg._runs_for_report()] == [here]


def _cover_the_whole_history(dlg):
    """Tick every measurement, which is what "Show all measurement runs" ON
    used to mean before it was removed (B8-590).

    It is pressed through the button Knut asked for, so this also keeps the
    checks below honest about the door a user really has.
    """
    dlg._select_all_btn.click()
    dlg._refresh()
    assert dlg._hidden_runs == set(), (
        f"“Select all” left rows unticked: {dlg._hidden_runs!r}")


def test_the_page_and_its_heading_are_about_the_same_sheet(two_dated, qapp):
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    assert len(dlg._runs_for_report()) == 2, "the history really is loaded"
    txt = _text(dlg._view.toHtml())
    assert "1 verification run" in txt
    assert "No. of Measurements: 1" in txt


def test_it_is_the_measurement_the_window_is_on_not_the_oldest(two_dated, qapp):
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    chosen = dlg._one_measurement(dlg._runs_for_report())
    assert len(chosen) == 1
    assert dlg._run_key(chosen[0]) == dlg._run_key(dlg._report)


def test_with_no_match_it_takes_the_newest_never_the_first(two_dated, qapp):
    """The history is oldest-first, so a fallback to `runs[0]` is a fallback to
    the sheet furthest from the one in hand."""
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    runs = dlg._runs_for_report()
    dlg._report = None
    assert dlg._one_measurement(runs) == runs[-1:]


def test_nothing_is_disabled_on_the_one_page_and_the_list_says_why(two_dated,
                                                                  qapp):
    """**KNUT'S FREEZE, FROM BOTH ENDS (B8-590, B8-591).**

    This used to read `assert dlg._all_runs_check.isEnabled() is False` — the
    one-page summary proved it was about one sheet by taking a control away.
    The box is gone with the feature behind it (B8-590), and what took its
    place, `lst.setEnabled(False)`, is what Knut reported on 2026-09-20: *"Now
    I tried selecting report type Colour summary. Then the 'included
    measurements in report' became unticked for all measurements and it froze,
    so I cannot scroll or select."* A disabled QListWidget does not scroll,
    does not take a click and gives no reason, so from the outside it is a hung
    window.

    The same fact is still told, and in a way that leaves the choice with the
    user: the list stays live, it keeps its ticks, and it carries the sentence
    saying the page is about ONE measurement.
    """
    dlg, older, newer = two_dated
    assert getattr(dlg, "_all_runs_check", None) is None, (
        "“Show all measurement runs” is still built")
    _no_string_still_names_the_removed_box()
    assert dlg._profile_list.isEnabled() is True, (
        "the measurement list is disabled under “Colour summary”, which is "
        "the freeze Knut reported")
    assert dlg._profile_list.viewport().isEnabled() is True
    assert "ONE measurement" in dlg._profile_list.toolTip(), \
        dlg._profile_list.toolTip()
    assert dlg._detail_check.isEnabled() is False, (
        "the one-page summary has no detail section, so its box stays "
        "disabled with a tooltip: that half of B8-523 is unchanged")
    assert "one page about one measurement" in dlg._detail_check.toolTip()
    # and a tick still moves, which is the whole of what "frozen" meant
    before = set(dlg._hidden_runs)
    dlg._deselect_all_btn.click()
    qapp.processEvents()
    assert dlg._hidden_runs != before and dlg._hidden_runs == {
        dlg._run_key(r) for r in dlg._history}


def test_and_the_list_gets_its_own_sentence_back_when_another_type_is_chosen(
        two_dated, qapp):
    """The one-page sentence is put in FRONT of the list's own and given back,
    which is what it used to do for the removed box's tooltip."""
    from tests.helpers.report_window import choose_report_type
    dlg, older, newer = two_dated
    choose_report_type(dlg, mr.REPORT_TYPE_FULL)   # K31: the report's type
    dlg._forget_limits()
    dlg._sync_limit_controls()
    assert dlg._profile_list.isEnabled() is True
    assert dlg._profile_list.toolTip() == dlg._list_tooltip
    assert dlg._detail_check.isEnabled() is True
    assert dlg._detail_check.toolTip() == ""


def test_nobody_is_accused_of_hiding_a_run_they_did_not_hide(two_dated, qapp):
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    txt = _text(dlg._view.toHtml())
    assert "hidden by you" not in txt


def test_but_a_run_the_user_really_unticked_is_still_owned_up_to(two_dated, qapp):
    """The honesty note must not be lost with the false positive.

    ITS WORDS CHANGED IN BETA 20, NOT ITS JOB. Knut ruled that the report reads
    as a document printed for someone who has never seen this window, so it no
    longer says "runs in the list above are hidden by you (unticked)" — a list
    a printed sheet cannot show. It says what it covers instead, by count.
    """
    from tests.helpers.report_window import choose_report_type
    dlg, older, newer = two_dated
    choose_report_type(dlg, mr.REPORT_TYPE_FULL)   # K31: the report's type
    dlg._forget_limits()
    dlg._sync_limit_controls()
    _cover_the_whole_history(dlg)
    dlg._hidden_runs.add(dlg._run_key(dlg._history[0]))
    dlg._refresh()
    txt = _text(dlg._view.toHtml())
    import re
    assert re.search(r"covers \d+ of the \d+ measurements", txt), txt[-400:]


# ---------------------------------------------------------------------------
@pytest.fixture
def two_dated(tmp_path, qapp):
    """A run with two dated verifications, nine days apart, set to T1."""
    import sys
    from pathlib import Path

    from PyQt6.QtCore import QSettings

    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _GRID, _srgb_to_xyz_d50

    work = tmp_path / "w"
    work.mkdir()
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    st.set("custom_output_path", str(work))
    proj = Project.create(work / "Two", "Two")
    run = proj.current_run()
    run.ensure_dir()

    def write(path, scale):
        rows, n = [], 0
        for r in _GRID:
            for g in _GRID:
                for b in _GRID:
                    n += 1
                    x, y, z = _srgb_to_xyz_d50(r, g, b)
                    x, y, z = x * scale + 0.25, y * scale + 0.2, z * scale + 0.15
                    rows.append(f"{n} {r:.4f} {g:.4f} {b:.4f} "
                                f"{x / 100:.6f} {y / 100:.6f} {z / 100:.6f}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            'CTI3\n\nDESCRIPTOR "x"\nKEYWORD "DEVICE_CLASS"\n'
            'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
            "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
            encoding="utf-8")

    paths = []
    # THE TWO SHEETS CARRY DIFFERENT CHART NAMES, on purpose. The report's
    # title appends the dominant chart name across the measurements it covers,
    # so the two lists give two different titles and a title built from the
    # wrong list is visible on the page rather than only in a variable.
    for stamp, scale, when, chart in (
            ("2026-09-01_100000", 0.985, "2026-09-01T10:00:00", "Alpha"),
            ("2026-09-10_100000", 0.90, "2026-09-10T10:00:00", "Bravo")):
        p = run.dir / "verifications" / stamp / f"{chart}.ti3"
        write(p, scale)
        # A REAL DATED VERIFICATION CARRIES ITS SAVED REPORT, and its `created`
        # is when it was MEASURED. Without one, both reports are built at load
        # time, both get today's second, and `_run_key` — created plus file
        # name — is the same string for both. That collision made one of these
        # tests vacuous and hid the other's run when a single one was unticked.
        rep = mr.build_report(p)
        rep["created"] = when
        # K31: the type is the REPORT's. These stand for reports the
        # one-page summary wrote, so they say so themselves (before K31 the
        # run's stored type named an untyped report).
        mr.set_report_type(rep, mr.REPORT_TYPE_SUMMARY)
        mr.save_report(rep, p.parent)
        paths.append(p)
    # K31: a new report starts on the Preferences type (it was the run's).
    st.set("report_default_type", mr.REPORT_TYPE_SUMMARY)
    dlg = MeasurementReportDialog(st, None, initial_ti3=paths[-1])
    yield dlg, paths[0], paths[1]
    dlg.close()


def test_the_fixture_itself_holds_two_tellable_apart_measurements(two_dated, qapp):
    """A GUARD ON THE TEST, not on the product. The first version of this
    fixture built both reports at load time, so both carried today's second and
    `_run_key` — created plus file name — was the same string for each. Hiding
    one hid both, and the "it is the measurement the window is on" test passed
    because every candidate matched. Each verification now carries its own
    saved report with its own measured date, as a real one does."""
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    keys = [dlg._run_key(r) for r in dlg._history]
    assert len(set(keys)) == len(keys) == 2, keys
    assert dlg._run_key(dlg._report) == keys[-1], \
        "the window is on the NEWER sheet, so the older one is a real decoy"


def test_the_pdf_title_is_about_the_same_sheet_as_the_page(two_dated, qapp):
    """A user can reach this page with the whole history ticked — nothing
    unticks rows for them any more (B8-591), and nothing should: "Select all"
    under another type and then the one-page summary is exactly that state.
    The title, the PDF file name and `_report_kind` are all worked out from the
    run list, so the list is narrowed before any of them, not only before the
    body."""
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    runs = dlg._runs_for_report()
    assert len(runs) == 2
    assert dlg._report_title(runs).endswith("Alpha"), \
        "the whole history really does title itself after the older sheet"
    assert dlg._report_title(dlg._one_measurement(runs)).endswith("Bravo")
    pdf = _text(dlg._report_body_html(runs, for_pdf=True))
    assert "No. of Measurements: 1" in pdf
    assert "Bravo" in pdf
    assert "Alpha" not in pdf


def test_generate_with_the_history_ticked_is_refused_and_says_why(two_dated,
                                                                 qapp,
                                                                 monkeypatch):
    """**THE PRESS STOPS. IT DOES NOT NARROW (B8-591).**

    This used to pin the narrowing: with the whole history ticked, the button
    was expected to write ONE file, into the folder of the sheet on screen, and
    none into the other. The half about the other folder was right and is still
    here; the half that let the press succeed silently is what Knut reported on
    2026-09-20, from the user's side: *"This unselected all but the last
    measurement without a warning"*, and *"the measurement I had ticked was
    unticked and the last measurement in the list was automatically ticked (I
    did not ask for that)"*.

    His rule for what replaces it, in the same message: *"the user should be
    informed … Then the user can close that message and do the changes, and
    then click generate report again."* So nothing is written, and no tick is
    moved: the user still has the eleven ticks they made, and the message names
    the two ways out.
    """
    import ui.warning_sign as WS
    import workflow.measurement_report as mr
    from workflow import measurement_messages as M
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    assert len(dlg._runs_for_report()) == 2
    said: list = []
    monkeypatch.setattr(WS, "inform",
                        lambda parent, title, text, *a, **k: said.append(
                            (title, text)))
    before = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    ticks_before = set(dlg._hidden_runs)
    dlg._on_generate_report()
    after = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    assert after == before, ("a press that was refused still wrote a report: "
                             f"{before!r} -> {after!r}")
    assert said, "the press was refused with nothing said"
    assert said[0] == M.CATALOGUE["M-REPORT-ONE-PAGE-ONE-DATE"].render(count=2)
    assert set(dlg._hidden_runs) == ticks_before, (
        "the refusal moved a tick, which is the half he reported twice")


def test_generate_writes_the_one_report_the_page_is_about(two_dated, qapp):
    """With ONE measurement ticked, which is what the page can carry, the sheet
    on screen gets its report and the other folder is not written to.

    The button used to iterate `_runs_for_report`, which is what is LOADED,
    while the page in front of the user described one sheet: it wrote a file
    into every dated verification folder, and `_say_generated` is deliberately
    quiet on success, so nothing said so. That is still the subject here; the
    fixture reaches the one-measurement state through the ticks now, because
    the ticks are the whole of what a report covers (B8-590)."""
    import workflow.measurement_report as mr
    dlg, older, newer = two_dated
    _cover_only_the_sheet_on_screen(dlg, qapp)
    assert len(dlg._runs_for_report()) == 1
    before = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    dlg._on_generate_report()
    after = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    assert after[newer] == before[newer] + 1, "the sheet on screen got its report"
    assert after[older] == before[older], \
        "a sheet the page never described must not be written to"


def test_and_the_other_types_still_write_every_loaded_run(two_dated, qapp):
    """The narrowing belongs to the one-page summary, not to the button.

    K31: a report of both dates is ONE file, in the run's
    `verifications/reports/`, covering both; nothing is written into either
    date's folder (Knut, 5801677743: no verdict records).

    MUTATION: write a record into each date again, or leave a ticked date out
    of the document's measurements, and this goes red."""
    import json
    import workflow.measurement_report as mr
    from tests.helpers.report_window import choose_report_type
    dlg, older, newer = two_dated
    choose_report_type(dlg, mr.REPORT_TYPE_FULL)   # K31: the report's type
    dlg._forget_limits()
    dlg._sync_limit_controls()
    _cover_the_whole_history(dlg)
    before = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    home = older.parent.parent / "reports"
    had = set(home.glob("report_*.json")) if home.is_dir() else set()
    dlg._on_generate_report()
    after = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    assert after == before, "a report of two dates wrote into a date's folder"
    new_files = set(home.glob("report_*.json")) - had
    assert len(new_files) == 1, new_files
    block = mr.recorded_document(json.loads(next(iter(new_files)).read_text(encoding="utf-8")))
    assert len(block["measurements"]) == 2
    assert all(m.get(mr.JUDGED_KEY) for m in block["measurements"])


def test_the_suggested_pdf_name_matches_the_page_it_saves(two_dated, qapp,
                                                         monkeypatch):
    """The document, its title and its kind are all narrowed to one
    measurement. The suggested file name was not, so with a mixed history it
    could name a different chart from the one printed inside the PDF.

    THE TEST EXERCISES THE WIRING, NOT THE HELPER. Asking the helper for a name
    from the narrowed list is a test of the narrowing, which was never in doubt:
    it passed with the export still reading the wide one, so it proved nothing.
    This captures the path the export actually offers the save dialog.
    """
    import ui.widgets as W
    dlg, older, newer = two_dated
    _cover_the_whole_history(dlg)
    assert len(dlg._runs_for_report()) == 2, "the history really is loaded"
    assert dlg._report_filename(dlg._runs_for_report()) != \
        dlg._report_filename(dlg._runs_for_document()), \
        "the two lists really do give different names"

    seen: list = []

    def _grab(*a, **k):
        seen.append(k.get("start_path", ""))
        return ""                      # cancel: nothing is written

    monkeypatch.setattr(W, "save_file_dialog", _grab)
    dlg._export_pdf()
    assert seen, "the export never reached the save dialog"
    assert "Bravo" in seen[0] and "Alpha" not in seen[0], seen[0]


# ---------------------------------------------------------------------------
# …AND THE APP MUST STOP NAMING IT, WHICH THE GUARD ABOVE NEVER ASKED
# ---------------------------------------------------------------------------
def _no_string_still_names_the_removed_box() -> None:
    """**THE HOLE THIS FILE HAD, FOUND BY CHALLENGE ROUND 32.** Every check
    above asserts the WIDGET is gone. None of them asked whether the app had
    stopped talking about it, and it had not: the Report type help went on
    saying *"While it is chosen, “Show all measurement runs” and the list of
    included measurements are fixed to that sheet"* for both a control that
    is not built and a freeze that was removed in the same commit. The key is
    in all thirteen catalogues and German is translated, so the false
    sentence was shipped in German too.

    A widget assertion cannot see that. This one reads the text.
    """
    import re
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from i18n_extract import extract_keys
    named = sorted(k for k in extract_keys()
                   if re.search(r"Show all measurement runs", k))
    assert not named, (
        "a user-facing string still names \u201cShow all measurement runs\u201d, "
        "which Knut removed from the design on 2026-09-20 along with the "
        "feature behind it:\n\n"
        + "\n\n".join(repr(k[:400]) for k in named))


def test_no_user_facing_string_names_the_removed_box():
    _no_string_still_names_the_removed_box()


def test_the_type_help_says_what_the_window_really_does(two_dated, qapp):
    """The sentence that replaced it is the list's own tooltip, in the help.

    It has to be TRUE of the window beside it, so it is checked against that
    window and not only against itself: the list is live, a press of Generate
    with more than one ticked asks rather than corrects, and there is no
    detailed section.
    """
    from ui.dialogs.measurement_report_dialog import _types_and_pairing_help
    help_text = _types_and_pairing_help()
    assert "Show all measurement runs" not in help_text, help_text
    assert "are fixed to that sheet" not in help_text, help_text
    assert "Tick the one you want the page to be about" in help_text
    assert "asks you to choose" in help_text
    assert "no detailed section" in help_text

    dlg, older, newer = two_dated
    assert dlg._profile_list.isEnabled() is True, (
        "the help says the user picks the sheet; the list is disabled")
    assert dlg._detail_check.isEnabled() is False, (
        "the help says there is no detailed section; the box is live")


@pytest.fixture(autouse=True)
def _each_press_answers_create_new(monkeypatch):
    """**K4 (Knut on beta 34): Generate on a selected report now asks**,
    whether or not a setting moved, because pressing it on a report with
    nothing changed created a new one in silence. These checks press Generate
    repeatedly to count what a CREATING press writes, which is what a user
    reaches by answering "Create New"; so that is the answer, given through
    the question's one method. The question itself is guarded in
    `tests/test_generate_report_asks_what_to_do.py`.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    monkeypatch.setattr(MeasurementReportDialog, "_ask_update_or_create_new",
                        lambda self: "new")
