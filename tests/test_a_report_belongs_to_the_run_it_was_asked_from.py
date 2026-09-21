"""A report asked for on run N is ABOUT run N and is filed in run N.

**The fault this pins down.** In a project with more than one profile run, the
Measurement Report window opened on a run's own measurement stopped being about
that run. `_gather_runs` built the window from `list_project_reports(ti3.parent)`,
which deliberately globs `runs/*/reports/report_*.json` across EVERY run, and the
fall-back that uses the measurement the window was opened on was reached only
when the project held no saved report at all. So the first report anybody ever
generated became the answer for every other run: opened on run 2 the window
showed run 1's measurement, and Generate filed run 1's numbers back into run 1,
while run 2 went on saying "No report has been generated for this run yet" for
ever. No error, no log line. The tester who met it reported a button that does
nothing.

Photographed on screen, 2026-09-15, on a real two-run project built with real
Argyll tools (`~/Desktop/ChromIQ-beta18-proof/katrina-journey/report-fix/`):
opened on run 1, the window read "Report type (run1)" over run 2's measurement
(avg dE 0.669 where run 1's is 4.206) and wrote into `runs/run2/reports/`.

**And the cross-run gathering is the FEATURE, not the fault** (#40, Knut: the
printer's full measurement history). So these tests hold BOTH halves apart:

* what the window shows as HISTORY may span the project's runs, and still does;
* what Generate is about, and where it is filed, is the measurement the window
  was opened on, and only that run.

Design rules relied on, both in `docs/design/measurement_report_limits.md`:
§5 "the set belongs to the profile run", §10 "the type belongs to the profile
run" and "Generate report writes a dated report of the type now chosen". Both
sections are marked awaiting confirmation; neither is contradicted here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _two_run_project(tmp_path, qapp):
    """A project with run1 and run2, each holding its own measurement.

    The two measurements differ patch for patch, so a report about the wrong one
    is tellable from a report about the right one by its numbers alone.
    """
    from tests.test_import_measurement_module import _cgats, _env, _PATCHES
    s, fm, _ctl = _env(tmp_path)
    proj = fm.project()
    run1 = proj.current_run()
    run1.ensure_dir()
    run1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    run2 = proj.new_run()
    run2.ensure_dir()
    shifted = [(min(100.0, r + 3.0), g, b) for r, g, b in _PATCHES]
    run2.measurement_ti3.write_text(_cgats("CTI3", shifted), encoding="utf-8")
    return s, proj, run1, run2


def _window_on(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def _generate(dlg, monkeypatch, qapp):
    monkeypatch.setattr(dlg, "_say_generated", lambda saved, failed: None)
    dlg._on_generate_report()
    qapp.processEvents()


def _reports_in(run) -> list:
    d = run.dir / "reports"
    return sorted(p.name for p in d.glob("report_*.json")) if d.is_dir() else []


# ---------------------------------------------------------------------------
# The subject: what the window is ABOUT
# ---------------------------------------------------------------------------

def test_the_window_shows_the_measurement_it_was_opened_on(tmp_path, qapp,
                                                           monkeypatch):
    """THE FAULT ITSELF. Run 1 has a saved report; the window is opened on
    run 2's measurement and must be about run 2's measurement.

    MUTATION: put `if not runs:` back in front of the fall-back in
    `_gather_runs` and this goes red — `_report` becomes run 1's.
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    assert _reports_in(run1), "the control failed: run 1 saved nothing"

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        assert dlg._report is not None
        assert dlg._report["_origin_dir"] == str(run2.dir), (
            "the window opened on run 2 is about %s"
            % dlg._report.get("_origin_dir"))
    finally:
        dlg.close()


def test_a_report_generated_from_a_run_is_filed_in_that_run(tmp_path, qapp,
                                                            monkeypatch):
    """Asked from run 2, written into run 2 — and NOTHING into run 1.

    MUTATION: drop the `mine` filter from `_reports_to_generate` and this goes
    red, because the history spans both runs.
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    before1 = _reports_in(run1)

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    assert len(_reports_in(run2)) == 1, _reports_in(run2)
    assert _reports_in(run1) == before1, "run 1 was written to as well"


def test_the_filed_report_carries_that_runs_own_numbers(tmp_path, qapp,
                                                        monkeypatch):
    """A file in the right folder about the wrong measurement is the same bug.

    The two runs' measurements differ, so the saved JSON must name run 2's
    measurement and carry its patch count and its own dE figures.
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    for run in (run1, run2):
        dlg = _window_on(s, run.measurement_ti3, qapp)
        try:
            _generate(dlg, monkeypatch, qapp)
        finally:
            dlg.close()
    docs = {}
    for run in (run1, run2):
        name = _reports_in(run)[0]
        docs[run.dir.name] = json.loads(
            (run.dir / "reports" / name).read_text(encoding="utf-8"))
    assert docs["run1"]["de00"]["avg_all"] != docs["run2"]["de00"]["avg_all"], (
        "both runs filed the same numbers: %s" % docs)


def test_the_run_stops_saying_it_has_no_report(tmp_path, qapp, monkeypatch):
    """The symptom the user reads. Before the fix the line under the pulldown
    never changed, because the file went to another run."""
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        assert "No report has been generated" in dlg._type_blurb_full
        _generate(dlg, monkeypatch, qapp)
        dlg._forget_limits()
        dlg._sync_limit_controls()
        assert "Already generated for this run" in dlg._type_blurb_full, (
            dlg._type_blurb_full)
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# The history: what may legitimately span runs
# ---------------------------------------------------------------------------

def test_the_history_still_spans_every_run_of_the_project(tmp_path, qapp,
                                                          monkeypatch):
    """THE FEATURE, and it must not be a casualty of the fix (#40, Knut: the
    printer's full measurement history).

    MUTATION: narrow `_gather_runs` to `list_reports(ti3.parent)` and this goes
    red.
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        origins = {str(r.get("_origin_dir")) for r in dlg._history}
        assert origins == {str(run1.dir), str(run2.dir)}, origins
        # ...and the trend has two points to draw, which is what the history
        # is for.
        assert len(dlg._runs_for_report()) == 2
    finally:
        dlg.close()


def test_the_run_the_window_is_on_is_in_the_history_even_unsaved(tmp_path,
                                                                 qapp):
    """A measurement with no saved report of its own is still a point on the
    trend — the same rule the dated fall-back above it already applies."""
    s, _proj, _run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        mine = [r for r in dlg._history
                if r.get("_origin_dir") == str(run2.dir)]
        assert len(mine) == 1 and mine[0].get("_fresh") is True
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# Generate: one report, per measurement, inside one run
# ---------------------------------------------------------------------------

def test_generate_never_crosses_a_run_boundary(tmp_path, qapp, monkeypatch):
    """With the whole project's history loaded and shown, the button still
    writes for one run: the one the window is on."""
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        # The window opens with every measurement ticked, which is what this
        # check assumes; it used to ask "Show all measurement runs", removed
        # with the feature behind it (B8-590, Knut 2026-09-20).
        dlg._select_all_btn.click()
        qapp.processEvents()
        assert dlg._hidden_runs == set(), "the premise: the history is in"
        assert len(dlg._runs_for_document()) == 2, "the document lost the history"
        targets = dlg._reports_to_generate()
        assert [r["_origin_dir"] for r in targets] == [str(run2.dir)], targets
    finally:
        dlg.close()


def test_three_presses_leave_three_reports_not_eight(tmp_path, qapp,
                                                     monkeypatch):
    """A SECOND FAULT IN THE SAME LINE, measured on screen: every saved report
    came back as a history entry and every history entry was written again, so
    the count DOUBLED on each press. Three presses left four files where the
    user asked for three.

    MUTATION: drop the `seen` dedup from `_reports_to_generate` and this goes
    red.
    """
    s, _proj, _run1, run2 = _two_run_project(tmp_path, qapp)
    for _ in range(3):
        dlg = _window_on(s, run2.measurement_ti3, qapp)
        try:
            _generate(dlg, monkeypatch, qapp)
        finally:
            dlg.close()
    assert len(_reports_in(run2)) == 3, _reports_in(run2)


def test_every_date_of_one_run_still_gets_its_own_report(tmp_path, qapp):
    """The restriction is a RUN boundary, not a folder boundary: a run's dated
    verifications are the run's, and a window holding several of them still
    writes one report per date."""
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from workflow.run_compliance import ensure_bound
    s, _proj, run1, _run2 = _two_run_project(tmp_path, qapp)
    run1.profile_icc.write_bytes(b"icc")
    dates = []
    for day in ("2026-09-01_10-00-00", "2026-09-02_10-00-00"):
        v = run1.verification(day) if hasattr(run1, "verification") else None
        if v is None:
            v = run1.new_verification()
        v.ensure_dir()
        v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        dates.append(v)
    ensure_bound(run1, None, "chromiq_default")
    assert len({str(v.dir) for v in dates}) == 2, "the two dates collided"

    dlg = _window_on(s, dates[-1].measurement_ti3, qapp)
    try:
        targets = {r["_origin_dir"] for r in dlg._reports_to_generate()}
        assert targets == {str(v.dir) for v in dates}, targets
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# The identity the whole fix rests on
# ---------------------------------------------------------------------------

def test_a_report_of_another_file_in_the_same_folder_is_not_about_this_one():
    """The folder alone is not an identity: a run folder holds
    `preconditioning.ti3` and `merged.ti3` beside the chart's own measurement,
    and somebody's Downloads folder holds whatever they put there."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    about = MeasurementReportDialog._report_is_about
    ti3 = Path("/p/runs/run1/chart.ti3")
    assert about({"_origin_dir": "/p/runs/run1", "ti3": "chart.ti3"}, ti3)
    assert not about({"_origin_dir": "/p/runs/run1",
                      "ti3": "preconditioning.ti3"}, ti3)
    assert not about({"_origin_dir": "/p/runs/run2", "ti3": "chart.ti3"}, ti3)
    # A report saved before the name was kept is matched on its folder rather
    # than declared foreign, so no old report is re-derived by this rule.
    assert about({"_origin_dir": "/p/runs/run1"}, ti3)


def test_a_measurement_that_cannot_be_read_says_so(tmp_path, qapp,
                                                   monkeypatch):
    """The other half of the same rule. With run 1 holding a saved report, a
    window opened on run 2's unreadable measurement used to answer with run 1's
    numbers. It must refuse instead: silently right-looking and wrong is the
    failure this whole change is about.

    (A measurement that is simply MISSING cannot reach here: the window checks
    `exists()` before it loads anything.)
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    run2.measurement_ti3.write_text("not a CGATS file", encoding="utf-8")

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        assert dlg._report is None, (
            "it answered with %s" % dlg._report.get("_origin_dir"))
        assert run1.dir.name not in dlg._view.toHtml()
    finally:
        dlg.close()


def test_two_runs_measured_in_the_same_second_are_two_rows(tmp_path, qapp,
                                                           monkeypatch):
    """Every run's measurement carries the SAME file name (the project's), so
    created-plus-name was one key for two runs. Unticking one row hid both, and
    the one-page summary could pick either.

    MUTATION: take `_origin_dir` back out of `_run_key` and this goes red.
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()
    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        rows = [dict(r) for r in dlg._history]
        assert len(rows) == 2, rows
        for r in rows:                     # as two runs measured in one second
            r["created"] = "2026-09-15T10:00:00"
        keys = [dlg._run_key(r) for r in rows]
        assert len(set(keys)) == 2, keys
    finally:
        dlg.close()
    assert run1.dir != run2.dir


def test_the_button_refuses_when_its_own_run_is_unticked(tmp_path, qapp,
                                                         monkeypatch):
    """FOUND BY THE ADVERSARY ROUND ON THE FIX ITSELF, on screen. Unticking the
    row of the run you are standing in left Generate enabled over an empty
    target list: pressing it wrote nothing and said nothing, which is the same
    shape as the fault this file is about.

    MUTATION: put `_runs_for_report` back in the enable line and this goes red.
    """
    s, _proj, run1, run2 = _two_run_project(tmp_path, qapp)
    dlg = _window_on(s, run1.measurement_ti3, qapp)
    try:
        _generate(dlg, monkeypatch, qapp)
    finally:
        dlg.close()

    dlg = _window_on(s, run2.measurement_ti3, qapp)
    try:
        assert dlg._generate_btn.isEnabled()
        dlg._hidden_runs.add(dlg._run_key(dlg._report))
        dlg._refresh()
        dlg._sync_limit_controls()
        qapp.processEvents()
        assert dlg._runs_for_document(), "the control failed: nothing is loaded"
        assert not dlg._reports_to_generate()
        assert not dlg._generate_btn.isEnabled(), (
            "the button is live over an empty target list")
        # ...and ticking it back brings the button back.
        dlg._hidden_runs.clear()
        dlg._refresh()
        dlg._sync_limit_controls()
        assert dlg._generate_btn.isEnabled()
    finally:
        dlg.close()
