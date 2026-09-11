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
* the tick box that widens every other report is disabled while T1 is chosen,
  rather than left on screen doing nothing.

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


def test_the_page_and_its_heading_are_about_the_same_sheet(two_dated, qapp):
    dlg, older, newer = two_dated
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    assert len(dlg._runs_for_report()) == 2, "the history really is loaded"
    txt = _text(dlg._view.toHtml())
    assert "1 verification run" in txt
    assert "No. of Measurements: 1" in txt


def test_it_is_the_measurement_the_window_is_on_not_the_oldest(two_dated, qapp):
    dlg, older, newer = two_dated
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    chosen = dlg._one_measurement(dlg._runs_for_report())
    assert len(chosen) == 1
    assert dlg._run_key(chosen[0]) == dlg._run_key(dlg._report)


def test_with_no_match_it_takes_the_newest_never_the_first(two_dated, qapp):
    """The history is oldest-first, so a fallback to `runs[0]` is a fallback to
    the sheet furthest from the one in hand."""
    dlg, older, newer = two_dated
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    runs = dlg._runs_for_report()
    dlg._report = None
    assert dlg._one_measurement(runs) == runs[-1:]


def test_the_tick_that_widens_a_report_is_disabled_on_the_one_page(two_dated, qapp):
    dlg, older, newer = two_dated
    assert dlg._all_runs_check.isEnabled() is False
    assert "single measurement" in dlg._all_runs_check.toolTip()


def test_and_comes_back_when_another_type_is_chosen(two_dated, qapp):
    from workflow.run_compliance import set_run_report_type
    dlg, older, newer = two_dated
    set_run_report_type(dlg._run_ctx.run, mr.REPORT_TYPE_FULL)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    assert dlg._all_runs_check.isEnabled() is True
    assert dlg._all_runs_check.toolTip() == ""


def test_nobody_is_accused_of_hiding_a_run_they_did_not_hide(two_dated, qapp):
    dlg, older, newer = two_dated
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    txt = _text(dlg._view.toHtml())
    assert "hidden by you" not in txt


def test_but_a_run_the_user_really_unticked_is_still_owned_up_to(two_dated, qapp):
    """The honesty note must not be lost with the false positive."""
    from workflow.run_compliance import set_run_report_type
    dlg, older, newer = two_dated
    set_run_report_type(dlg._run_ctx.run, mr.REPORT_TYPE_FULL)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    dlg._hidden_runs.add(dlg._run_key(dlg._history[0]))
    dlg._refresh()
    txt = _text(dlg._view.toHtml())
    assert "hidden by you" in txt


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
    from workflow.run_compliance import set_run_report_type
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
        mr.save_report(rep, p.parent)
        paths.append(p)
    set_run_report_type(run, mr.REPORT_TYPE_SUMMARY)
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
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    keys = [dlg._run_key(r) for r in dlg._history]
    assert len(set(keys)) == len(keys) == 2, keys
    assert dlg._run_key(dlg._report) == keys[-1], \
        "the window is on the NEWER sheet, so the older one is a real decoy"


def test_the_pdf_title_is_about_the_same_sheet_as_the_page(two_dated, qapp):
    """Disabling the tick box does not UNTICK it, so a user who ticked "Show
    all measurement runs" under another type and then chose the one-page
    summary still arrives here with the whole history. The title, the PDF file
    name and `_report_kind` are all worked out from the run list, so the list
    is narrowed before any of them, not only before the body."""
    dlg, older, newer = two_dated
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    runs = dlg._runs_for_report()
    assert len(runs) == 2
    assert dlg._report_title(runs).endswith("Alpha"), \
        "the whole history really does title itself after the older sheet"
    assert dlg._report_title(dlg._one_measurement(runs)).endswith("Bravo")
    pdf = _text(dlg._report_body_html(runs, for_pdf=True))
    assert "No. of Measurements: 1" in pdf
    assert "Bravo" in pdf
    assert "Alpha" not in pdf


def test_generate_writes_the_one_report_the_page_is_about(two_dated, qapp):
    """The button iterated `_runs_for_report`, which is what is LOADED, while
    the page in front of the user described one sheet. With the history ticked
    on it wrote a file into every dated verification folder, and
    `_say_generated` is deliberately quiet on success, so nothing said so."""
    import workflow.measurement_report as mr
    dlg, older, newer = two_dated
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    assert len(dlg._runs_for_report()) == 2
    before = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    dlg._on_generate_report()
    after = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    assert after[newer] == before[newer] + 1, "the sheet on screen got its report"
    assert after[older] == before[older], \
        "a sheet the page never described must not be written to"


def test_and_the_other_types_still_write_every_loaded_run(two_dated, qapp):
    """The narrowing belongs to the one-page summary, not to the button."""
    import workflow.measurement_report as mr
    from workflow.run_compliance import set_run_report_type
    dlg, older, newer = two_dated
    set_run_report_type(dlg._run_ctx.run, mr.REPORT_TYPE_FULL)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    dlg._all_runs_check.setChecked(True)
    dlg._refresh()
    before = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    dlg._on_generate_report()
    after = {p: len(mr.list_reports(p.parent)) for p in (older, newer)}
    assert after[older] == before[older] + 1
    assert after[newer] == before[newer] + 1
