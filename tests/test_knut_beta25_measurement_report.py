"""Knut's three beta-25 defects in the Measurement Report window.

His comment, 2026-09-19, after loading the demo "Report-Limits-Report-Types",
entering run1 and selecting the report shown as *"2026-11-16 10:00 Colour
summary…"*:

  1. *"The report text updates, but the first line says 'Created: 2026-09-19
     17:57:22', which is not the same creation time as the report name is
     giving. They should be the same (but it is ok that the report name and
     report text does not show the seconds)"*  — B8-461.
  2. *"If I change Judged against from 'ChromIQ default' to 'ChromIQ tight',
     then suddenly report type also changes to 'Grey and tone check'. Changing
     judged agains parameter shall not ever alter report type."*  — B8-462.
  3. *"Whatever metrics are shown in Report Results: each metric used in the
     report shall have a corresponding explanation of each metric in the 'How
     to read this report' section. Currently, only 4 metrics are described in a
     bullet list … The bullet list of parameters explained is then changing
     with which metrics the report contains."*  — B8-463.

All three were reproduced in a REAL window first, on his own demo project:
`scripts/drive_k25_report_window_bugs.py` and
`scripts/drive_k25_bug2_mechanism.py`, with the photographs in
`~/Desktop/ChromIQ-beta26-proof/knut-report-window/`.
"""
from __future__ import annotations

import re

import pytest

# ---------------------------------------------------------------------------
# fixtures: a real run, a real limit set, a real saved report
# ---------------------------------------------------------------------------
_HDR = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "OUTPUT"
COLOR_REP "RGB_XYZ"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS {n}
BEGIN_DATA
{rows}
END_DATA
"""


def _rich_ti3() -> str:
    """A measurement with enough SHAPE to be judged on many rows at once.

    **A FIXTURE TOO TIDY TO CONTAIN THE FAULT AGREES WITH THE CODE.** A
    two-patch stub produces one or two verdict rows, and a guide that explains
    one metric out of one passes a test about explaining every metric while the
    real window explains none of thirteen. So: a 17-step neutral ramp from
    white to black (the grey rows and the tone-ramp row), the full 3x3x3 device
    cube including all eight corners (the cube-corner figures and the surface-
    gamut row), and sixty more patches spread through the cube so the
    percentile rows and the outer-gamut row have a population to work on.
    """
    rows, i = [], 0

    def _xyz(r, g, b):
        y = 0.04 + 0.92 * ((0.299 * r + 0.587 * g + 0.114 * b) / 100.0) ** 2.0
        return (y * (0.96 + 0.0008 * r), y, y * (1.04 + 0.0008 * b))

    for step in range(17):                       # the neutral ramp
        v = step * 100.0 / 16.0
        i += 1
        x, y, z = _xyz(v, v, v)
        rows.append(f"{i} {v:.4f} {v:.4f} {v:.4f} "
                    f"{x * 0.985:.4f} {y:.4f} {z * 1.015:.4f}")
    for r in (0, 50, 100):                       # the device cube
        for g in (0, 50, 100):
            for b in (0, 50, 100):
                i += 1
                x, y, z = _xyz(r, g, b)
                rows.append(f"{i} {r:.4f} {g:.4f} {b:.4f} "
                            f"{x:.4f} {y:.4f} {z:.4f}")
    for n in range(60):                          # a spread through the cube
        r = (n * 37) % 101
        g = (n * 53) % 101
        b = (n * 71) % 101
        i += 1
        x, y, z = _xyz(r, g, b)
        rows.append(f"{i} {r:.4f} {g:.4f} {b:.4f} "
                    f"{x * 1.01:.4f} {y * 0.995:.4f} {z:.4f}")
    return _HDR.format(n=len(rows), rows="\n".join(rows))


@pytest.fixture
def a_saved_report(tmp_path, qapp):
    """A run with one dated verification and one SAVED report of it.

    Saved the way the app saves one, through `build_report` / `stamp_verdict` /
    `save_report`, so the file on disk is a real report and not a dict this
    test wrote.
    """
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import (REPORT_TYPE_FULL, build_report,
                                             save_report, set_report_type,
                                             stamp_verdict)
    from workflow.run_compliance import ensure_bound
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_rich_ti3(), encoding="utf-8")
    lim = ensure_bound(run, None, "chromiq_default")
    rep = build_report(str(v.measurement_ti3))
    stamp_verdict(rep, lim.limits, set_id=lim.set_id, set_label=lim.label_en,
                  edited=lim.edited)
    # THE FILE SAYS WHICH KIND OF DOCUMENT IT IS, as every report the app saves
    # has since 4.2.0. Without it the window falls back to the RUN's type and
    # the fixture cannot hold a report of one kind on a run of another, which
    # is the state Knut's second defect lives in.
    set_report_type(rep, REPORT_TYPE_FULL)
    path = save_report(rep, v.dir)
    # **AND IT WAS SAVED LONG AGO.** `save_report` names the file with the
    # second it wrote it, so a report saved by the fixture and read back in the
    # same second cannot tell "the report's creation time" from "the window's
    # own clock" apart: the guard would pass over the fault it is about. The
    # demo packs seed their reports exactly this way, and `_report_file_order`
    # reads the stamp off the name.
    path = path.rename(path.with_name("report_2026-11-16_10-00-00.json"))
    # **AND THE NEWEST REPORT IS JUDGED AGAINST ANOTHER SET THAN THE RUN.**
    # Ordinary, and the state the mirror of Knut's second defect lives in: a
    # saved report keeps the set it was judged against, and the run keeps its
    # own binding. Nothing is bound behind the window's back to arrange it,
    # because that fires the window's own "the run moved" guard, which is a
    # different rule being tested somewhere else.
    from workflow.compliance_sets import SET_BY_ID, effective_limits
    other = "chromiq_tight"
    rep2 = build_report(str(v.measurement_ti3))
    stamp_verdict(rep2, effective_limits(other, None), set_id=other,
                  set_label=SET_BY_ID[other].label, edited=False)
    set_report_type(rep2, REPORT_TYPE_FULL)
    p2 = save_report(rep2, v.dir)
    p2.rename(p2.with_name("report_2026-11-17_11-30-00.json"))
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    yield dlg, run, path
    dlg.close()


def _plain(dlg) -> str:
    return " ".join(re.sub("<[^>]+>", " ", dlg._view.toHtml()).split())


def _select_the_saved_report(dlg, qapp) -> str:
    """Click the one saved entry, as a user does, and return its name."""
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    i = next(i for i in range(dlg._saved_combo.count())
             if dlg._saved_combo.itemData(i)
             and dlg._saved_combo.itemData(i) != NEW_REPORT_KEY)
    dlg._saved_combo.setCurrentIndex(i)
    # `currentIndexChanged` does not fire for the entry the box is already on
    # (the window opens on the newest report), and `activated` is what a real
    # click sends.
    dlg._saved_combo.activated.emit(i)
    qapp.processEvents()
    return dlg._saved_combo.currentText()


# ---------------------------------------------------------------------------
# B8-461 — the "Created:" line is the REPORT's creation time
# ---------------------------------------------------------------------------
def test_the_created_line_is_the_reports_own_creation_time(a_saved_report, qapp):
    """Knut: *"the first line says 'Created: …', which is not the same creation
    time as the report name is giving. They should be the same."*

    The body was stamped with `self._created`, the second the WINDOW opened, so
    a report saved in November and opened today announced itself as made today
    under an entry whose name said November. Driven on his own demo before the
    fix: entry *"2026-11-16 10:00 · Colour summary (one page) · ChromIQ default
    (recommended) · saved 2026-11-16 10:00:00"*, body *"Created: 2026-09-19
    22:07:08"*.

    MUTATION (run 2026-09-19, seen red, restored): in `_report_body_html` put
    `when` back to `(created or self._created)`::

        E  AssertionError: the name says '2026-11-17 11:30' and the report
           text says '2026-09-19 22:40'
    """
    dlg, _run, _path = a_saved_report
    name = _select_the_saved_report(dlg, qapp)
    body = _plain(dlg)
    m = re.search(r"Created: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", body)
    assert m, f"the report text has no Created line:\n{body[:200]}"
    # the name carries the same stamp after "saved"
    n = re.search(r"saved (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", name)
    assert n, f"the entry name carries no saved stamp: {name!r}"
    assert m.group(1) == n.group(1), (
        f"the name says {n.group(1)!r} and the report text says "
        f"{m.group(1)!r}")


def test_a_new_report_still_shows_this_windows_own_clock(a_saved_report, qapp):
    """The other half: with "New report…" chosen nothing is loaded, so the line
    is the window's own time and must not be blank or stuck on the last
    document's.

    MUTATION (run 2026-09-19, seen red, restored): drop the
    `self._doc_created = ""` line from `_load_the_defaults`::

        E  AssertionError: New report says '2026-11-17 11:30:00', the window
           opened at '2026-09-19T22:40:14' (the loaded report said
           '2026-11-17 11:30:00')
    """
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    dlg, _run, _path = a_saved_report
    _select_the_saved_report(dlg, qapp)
    was = re.search(r"Created: (\S+ \S+)", _plain(dlg)).group(1)
    i = dlg._saved_combo.findData(NEW_REPORT_KEY)
    assert i >= 0
    dlg._saved_combo.setCurrentIndex(i)
    dlg._saved_combo.activated.emit(i)
    qapp.processEvents()
    now = re.search(r"Created: (\S+ \S+)", _plain(dlg))
    assert now, "the New report state has no Created line at all"
    assert now.group(1) == dlg._created.replace("T", " "), (
        f"New report says {now.group(1)!r}, the window opened at "
        f"{dlg._created!r} (the loaded report said {was!r})")


# ---------------------------------------------------------------------------
# B8-462 — one control moved may not move another
# ---------------------------------------------------------------------------
def test_changing_the_limit_set_never_moves_the_report_type(a_saved_report,
                                                            qapp):
    """Knut: *"Changing judged agains parameter shall not ever alter report
    type."*

    The report on screen is of one kind and the RUN carries another, which is
    ordinary: a saved report keeps the type it was made with, and the type
    pulldown writes to the run the moment it is used. Moving "Judged against"
    dropped the loaded document's claim on ALL the controls, and the type
    pulldown fell back to the run's.

    Driven on his own demo before the fix: *"Colour summary (one page)"* became
    *"Grey and tone check"* on a change to "Judged against" alone
    (`~/Desktop/ChromIQ-beta26-proof/knut-report-window/before/result.json`).

    MUTATION (run 2026-09-19, seen red, restored): delete the
    `self._remember_what_is_on_screen()` call from `_settings_touched`::

        E  AssertionError: the report type moved from 't2_full_colour_check'
           to 't3_grey_and_tone' on a limit-set change
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    from workflow.run_compliance import set_run_report_type
    dlg, run, _path = a_saved_report
    # the run carries a different kind of document from the report on screen
    set_run_report_type(run, REPORT_TYPE_GREY)
    _select_the_saved_report(dlg, qapp)
    before = dlg._type_combo.currentData()
    assert before and before != REPORT_TYPE_GREY, (
        f"the fixture does not contain the fault: the report and the run are "
        f"both {before!r}")

    sets = [i for i in range(dlg._set_combo.count())
            if dlg._set_combo.itemData(i)
            and dlg._set_combo.itemData(i) != dlg._set_combo.currentData()]
    assert sets, "no other limit set can be chosen, so nothing is proved"
    dlg._set_combo.setCurrentIndex(sets[0])
    qapp.processEvents()
    after = dlg._type_combo.currentData()
    assert after == before, (
        f"the report type moved from {before!r} to {after!r} on a "
        f"limit-set change")


def test_changing_the_report_type_never_moves_the_limit_set(a_saved_report,
                                                            qapp):
    """The mirror, and the same line of code: a report judged against one set
    may sit on a run bound to another, and choosing a report TYPE must not
    silently rejudge the page against the run's set.

    MUTATION (run 2026-09-19, seen red, restored): the same deletion::

        E  AssertionError: the limit set moved from 'chromiq_tight' to
           'chromiq_default' on a report-type change
    """
    from workflow.measurement_report import REPORT_TYPE_GREY
    dlg, run, _path = a_saved_report
    _select_the_saved_report(dlg, qapp)
    shown = dlg._set_combo.currentData()
    assert shown == "chromiq_tight", (
        f"the fixture does not contain the fault: the report and the run are "
        f"both judged against {shown!r}")
    i = dlg._type_combo.findData(REPORT_TYPE_GREY)
    assert i >= 0 and dlg._type_combo.currentData() != REPORT_TYPE_GREY
    dlg._type_combo.setCurrentIndex(i)
    qapp.processEvents()
    assert dlg._set_combo.currentData() == shown, (
        f"the limit set moved from {shown!r} to "
        f"{dlg._set_combo.currentData()!r} on a report-type change")


# ---------------------------------------------------------------------------
# B8-463 — every metric the results table judges is explained
# ---------------------------------------------------------------------------
def _rows_and_guide(dlg):
    """(metric labels in Report Results, the guide's text)."""
    from core.i18n import tr
    from workflow.compliance_sets import ROW_BY_ID
    txt = _plain(dlg)
    assert "Report Results" in txt and "How to read this report" in txt, txt[:300]
    guide = txt.split("How to read this report", 1)[1].split("Report Results", 1)[0]
    table = txt.split("Report Results", 1)[1]
    shown = [tr(r.label) for r in ROW_BY_ID.values()
             if tr(r.label) and tr(r.label) in table]
    return shown, guide


def test_every_metric_in_report_results_is_explained_in_the_guide(
        a_saved_report, qapp):
    """Knut: *"each metric used in the report shall have a corresponding
    explanation of each metric in the 'How to read this report' section."*

    Measured in a real window before the fix, on his own demo project, every
    buildable report type crossed with every choosable limit set: **13 metrics
    judged and 0 of them named in the guide, in all 20 combinations**
    (`before/bug3.json`). After: 0 unexplained in all 20.

    MUTATION (run 2026-09-19, seen red, restored), twice over: return `""`
    from `_metrics()` in `_how_to_read_html`, and separately call
    `self._how_to_read_html()` with no argument from `_report_body_html`. Both
    give::

        E  AssertionError: 8 of 8 metrics are judged with no explanation in
           the guide: ['Grey balance of the grey ramp, average', …]
    """
    from workflow.measurement_report import REPORT_TYPE_FULL
    from workflow.run_compliance import set_run_report_type
    dlg, run, _path = a_saved_report
    set_run_report_type(run, REPORT_TYPE_FULL)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    dlg._refresh()
    qapp.processEvents()
    shown, guide = _rows_and_guide(dlg)
    assert len(shown) >= 5, (
        f"the fixture is too tidy to contain the fault: only {len(shown)} "
        f"metrics are judged ({shown})")
    missing = [lab for lab in shown if lab not in guide]
    assert not missing, (
        f"{len(missing)} of {len(shown)} metrics are judged with no "
        f"explanation in the guide: {missing}")


@pytest.fixture
def a_fresh_measurement(tmp_path, qapp):
    """The same rich measurement with NO report saved for it.

    Needed for the half of Knut's third point that is about the list CHANGING:
    a saved report carries its own recorded verdict, so its rows are the rows
    it was saved with whatever the pulldown now says, and only a measurement
    with nothing saved is judged live against the set on screen.
    """
    from tests.test_import_measurement_module import _verify_env
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_rich_ti3(), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    yield dlg, run
    dlg.close()


def test_the_explained_list_changes_with_the_metrics_the_report_contains(
        a_fresh_measurement, qapp):
    """*"The bullet list of parameters explained is then changing with which
    metrics the report contains."*

    Every buildable report type crossed with every choosable limit set: each
    combination must explain everything its own table judges, and the lists
    across the combinations must not all be the same, or the test would pass on
    a guide that ignored the table entirely.

    **THE TYPE IS WHAT MOVES THE LIST ON THIS CHART, NOT THE SET, and that is
    measured rather than assumed.** A limit set decides which rows carry a
    NUMBER; which rows the table lists at all is decided by what the chart can
    supply, so on one measurement the five sets produced the identical eight
    rows here, and on Knut's own demo the identical thirteen
    (`~/Desktop/ChromIQ-beta26-proof/knut-report-window/before/bug3.json`). The
    report TYPE does move it: "Grey and tone check" drops the five colour rows.
    The rule under test is the same either way, so the cross is driven whole.

    MUTATION (run 2026-09-19, seen red, restored): return `list(ROW_BY_ID)`
    from `_rows_the_results_show`::

        E  AssertionError: every combination judges the identical metric list,
           so the guide cannot be shown to follow the table: [('Paper white,
           difference from the reference paper', …, 'Measurement condition
           (M0, M1, M2) stated and matched')]
        E  assert 1 >= 2
    """
    from workflow.measurement_report import report_type_is_built
    from workflow.run_compliance import set_run_report_type
    dlg, run = a_fresh_measurement
    seen = {}
    for ti in range(dlg._type_combo.count()):
        tid = dlg._type_combo.itemData(ti)
        if not tid or not report_type_is_built(tid):
            continue
        set_run_report_type(run, tid)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        dlg._refresh()
        qapp.processEvents()
        if "Report Results" not in _plain(dlg):
            continue            # the one-page summary is a different document
        for si in range(dlg._set_combo.count()):
            sid = dlg._set_combo.itemData(si)
            if not sid:
                continue
            dlg._set_combo.setCurrentIndex(si)
            qapp.processEvents()
            shown, guide = _rows_and_guide(dlg)
            missing = [lab for lab in shown if lab not in guide]
            assert not missing, (
                f"{tid} / {sid}: {len(missing)} of {len(shown)} metrics are "
                f"judged with no explanation: {missing}")
            seen[(tid, sid)] = tuple(shown)
    assert len(seen) >= 4, f"only {len(seen)} combinations were driven"
    assert len(set(seen.values())) >= 2, (
        f"every combination judges the identical metric list, so the guide "
        f"cannot be shown to follow the table: {sorted(set(seen.values()))}")


def test_the_guide_and_the_table_read_the_same_list(a_saved_report, qapp):
    """One answer to one question: `_rows_the_results_show` feeds BOTH.

    MUTATION (run 2026-09-19, seen red, restored): return `""` from
    `_metrics()` in `_how_to_read_html`. (Emptying the caller's argument does
    NOT reach this one, which calls `_how_to_read_html` itself: measured.)::

        E  AssertionError: grey_balance_neutral_ramp_avg is judged and not
           explained
    """
    dlg, _run, _path = a_saved_report
    qapp.processEvents()
    runs = dlg._runs_for_report()
    present = dlg._rows_the_results_show(runs)
    assert present, "no metric row at all, so nothing is proved"
    html = dlg._how_to_read_html(present)
    from core.i18n import tr
    from workflow.compliance_sets import ROW_BY_ID
    for rid in present:
        row = ROW_BY_ID.get(rid)
        if row is None or not row.blurb:
            continue
        assert tr(row.label) in html, f"{rid} is judged and not explained"
