"""K32, Knut on beta 41 (#182 5813851807): what a Printing record lists, and
the freeze after switching the run type.

*"The resulting report for a Printing record type with limit set Custom ISO
12647-7 does not seem to list all the metrics that "Custom ISO 12647-7" has
values for ... (only metrics from ChromIQ default limit set is showing), and
the Graph tabs are also only those for ChromIQ default limit set"*; and
*"Changing from Profiling to Verification took several seconds and it felt
like the app was freezing"*.

Driven on screen before and after: `scripts/drive_k32_report_rows_and_switch.py`,
proof in ~/Desktop/ChromIQ-beta42-proof/knut-k32/.
"""
from __future__ import annotations

import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _profiling_window(tmp_path, qapp):
    """A Profiling window (the bar says Profiling) on a run's own sheet whose
    automatic Printing record was judged against ChromIQ default."""
    from core.measurement_target import RUN_TYPE_PROFILING
    from PyQt6.QtWidgets import QWidget
    from tests.test_k19_counts_follow_the_run_type import (
        _run_with_a_profiling_record)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import effective_limits
    from workflow.measurement_report import (REPORT_TYPE_RECORD, build_report,
                                             save_report, stamp_verdict)
    s, _fm, run, _vs = _run_with_a_profiling_record(tmp_path)
    # THE SHEET'S AUTOMATIC REPORT RECORDS ITS OWN SET, as every sheet of the
    # demo pack does: this is what the early return kept on the page.
    for f in (run.dir / "reports").glob("report_*.json"):
        f.unlink()
    rep = build_report(run.dir / "sheet.ti3")
    rep["report_type"] = REPORT_TYPE_RECORD
    stamp_verdict(rep, effective_limits("chromiq_default", {}),
                  set_id="chromiq_default",
                  set_label="ChromIQ default (recommended)")
    save_report(rep, run.dir)
    host = QWidget()
    host._target_ctl = types.SimpleNamespace(
        target=types.SimpleNamespace(run_type=RUN_TYPE_PROFILING))
    dlg = MeasurementReportDialog(s, host, initial_ti3=run.dir / "sheet.ti3")
    dlg.show()
    qapp.processEvents()
    return dlg, host


def _choose(dlg, qapp, set_id):
    i = dlg._set_combo.findData(set_id)
    assert i >= 0, f"{set_id} is not in Judged against"
    dlg._set_combo.setCurrentIndex(i)
    dlg._on_set_chosen(i)
    qapp.processEvents()


def test_a_printing_record_lists_the_rows_of_the_reports_own_set(
        tmp_path, qapp):
    """Knut's case on a Profiling window: Custom ISO 12647-7 chosen, and the
    Printing record's results, its "Judged against" line and its graphs are
    the ones of Custom ISO 12647-7, not of the set each sheet's automatic
    report used.

    MUTATION, proved to land: put back the early return
    `if self._window_kind() == KIND_PROFILING: return rows` in
    `_judged_by_the_document`: the solids and control-strip rows are missing
    and the column says "ChromIQ default": red.
    """
    from workflow.measurement_report import KIND_PROFILING
    dlg, host = _profiling_window(tmp_path, qapp)
    try:
        assert dlg._window_kind() == KIND_PROFILING
        assert dlg._ungraded_by_type(), "a profiling window is a Printing record"
        runs = dlg._runs_for_document()
        before = dlg._rows_the_results_show(runs)
        assert "solids_de00_max" not in before, (
            "ChromIQ default puts no limit on the solids; the fixture is not "
            "the state Knut started from")
        _choose(dlg, qapp, "custom_iso_12647_7")
        runs = dlg._runs_for_document()
        after = dlg._rows_the_results_show(runs)
        for rid in ("solids_de00_max", "control_strip_de00_avg",
                    "substrate_de00_max", "surface_gamut_de00_avg",
                    "ramps_30_70_dl_max"):
            assert rid in after, (
                f"{rid} has a value in Custom ISO 12647-7 and is not in the "
                f"Printing record's results: {after}")
        label = dlg._judged_label_for(runs[0], mark_unsaved=False)
        assert "Custom ISO 12647-7" in label, (
            f"the column says it was judged against {label!r}")
    finally:
        dlg.close()
        host.deleteLater()


def test_a_printing_record_says_why_it_has_only_four_graphs(tmp_path, qapp):
    """§17 item 3 (Knut's rule): a judged metric's graph is shown only where
    one of its rows was judged, and a Printing record judges nothing. That is
    by design; what was missing is the report SAYING so, which Knut asked
    for: "nothing in the report seems to say why metrics are missing".

    MUTATION, proved to land: drop the sentence from `_report_results_html`
    (or print it on every type) and one of the two assertions is red.
    """
    from workflow.measurement_report import REPORT_TYPE_FULL
    dlg, host = _profiling_window(tmp_path, qapp)
    try:
        _choose(dlg, qapp, "custom_iso_12647_7")
        runs = dlg._runs_for_document()
        html = dlg._report_results_html(runs,
                                        dlg._rows_the_results_show(runs))
        # K51 (B8-1334): its limit lines are shown for information now
        assert "a limit line on its graphs is shown for information " \
            "only" in html
        shown = [dlg._trend_tabs.tabText(i)
                 for i in range(dlg._trend_tabs.count())
                 if dlg._trend_tabs.isTabVisible(i)]
        assert len(shown) == 4, shown
        # …and a report that judges does not print it.
        dlg._sync_type_combo_to(REPORT_TYPE_FULL)
        dlg._report_type_now = lambda: REPORT_TYPE_FULL
        html = dlg._report_results_html(runs,
                                        dlg._rows_the_results_show(runs))
        assert "a limit line on its graphs is shown for information" \
            not in html
    finally:
        dlg.close()
        host.deleteLater()


def test_a_warming_tick_gives_the_event_loop_back_after_its_budget(
        qapp, monkeypatch, tmp_path):
    """Switching the run type to Verification starts warming the preset
    eligibility cache on the event loop. A tick took FOUR charts whatever they
    cost, and a chart with page TIFFs costs about 0.57 s on this machine, so
    the window froze for 3.0 to 3.2 s in one piece (measured on screen on
    Report-Limits-Evenness). K32 made it one chart a tick; B8-1161 (challenge
    1 of beta 43) found that one chart still froze the presets window for a
    second, and a tick now works nothing out itself: it hands the chart to
    the background thread and returns
    (tests/test_c1b43_the_presets_window_never_stalls.py has the heartbeat).

    MUTATION, proved to land: `_warm_one_preset_batch` calling
    ``_pe.chart_row_values`` itself (red: a heavy chart in the tick)."""
    import time
    from ui.tabs import tab_chart as TC
    from workflow import preset_eligibility as PE
    from workflow import preset_layout as PL
    from workflow.i1profiler_import import RgbPatch, write_ti1
    calls: list = []

    def slow(chart, recipe=None, **_k):
        calls.append(chart)
        time.sleep(TC._PRESET_WARM_BUDGET_S * 1.2)   # a heavy chart
        return {}
    monkeypatch.setattr(PE, "chart_row_values", slow)
    charts = []
    for i in range(3):
        c = tmp_path / f"c{i}.ti1"
        write_ti1([RgbPatch(i, 0, 0)], c)
        charts.append(c)
    PE.clear_cache()
    host = types.SimpleNamespace(
        _preset_warm_charts=[(c, None) for c in charts],
        _preset_warm_at=0, _preset_warm_timer=None)
    t0 = time.monotonic()
    TC.TabChart._warm_one_preset_batch(host)
    took = time.monotonic() - t0
    assert took < TC._PRESET_WARM_BUDGET_S, (
        f"one tick held the event loop {took:.2f} s")
    assert host._preset_warm_at == 1
    # the chart went to the background thread, and nothing is lost
    end = time.monotonic() + 10
    while PL.pending() and time.monotonic() < end:
        time.sleep(0.02)
    assert calls == [charts[0]]
    PE.clear_cache()


# ---------------------------------------------------------------------------
# Item 7 (Knut, 5814558912 and 5814673639): nothing measured, nothing listed
# ---------------------------------------------------------------------------
class _Parent:
    def __init__(self, ctl):
        self._target_ctl = ctl


def _seed(ctl, proj):
    from ui.dialogs.tools_dialogs import _report_seed
    return _report_seed(_Parent(ctl), proj)


def test_a_verification_run_with_no_date_seeds_nothing(qapp, tmp_path):
    """Report-Limits-Evenness run 3: a verification run with no dated
    verification opened the window on the run's PROFILING sheet, and the list
    filled with the sheets of all eight runs. Knut: the list is empty.

    MUTATION, proved to land: seed the run's sheet again when there is no
    date."""
    import shutil
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from tests.test_the_tools_door_opens_on_this_selection import (
        _project_with_everything)
    _s, _fm, ctl, proj, run, v, _cal = _project_with_everything(tmp_path)
    shutil.rmtree(v.dir)
    assert not [x for x in run.verifications() if x.exists()]
    assert run.measurement_ti3.exists(), "the sheet it used to borrow"
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert _seed(ctl, proj) is None


def test_a_profiling_run_never_borrows_a_verification(qapp, tmp_path):
    """Knut's addition: under Profiling the list is filled from no other kind.
    A profile run with no sheet borrowed its newest dated verification; with
    no sheet in the whole project it is empty.

    MUTATION, proved to land: put back the final `if dated: return
    dated[-1].measurement_ti3` for a selection with a bar."""
    from core.measurement_target import RUN_TYPE_PROFILING
    from tests.test_the_tools_door_opens_on_this_selection import (
        _project_with_everything)
    _s, _fm, ctl, proj, run, v, _cal = _project_with_everything(tmp_path)
    run.measurement_ti3.unlink()
    assert v.measurement_ti3.exists(), "the verification it used to borrow"
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert _seed(ctl, proj) is None


def test_an_empty_window_says_why_in_its_run_types_words(qapp, tmp_path):
    """The window opened with nothing says what is missing and the two ways
    forward (measure, or Add Profile's Measurements…), per run type; a list
    the user cleared keeps the old sentence.

    MUTATION, proved to land: always return the old sentence from
    `_empty_text`."""
    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from PyQt6.QtWidgets import QWidget
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    words = {RUN_TYPE_VERIFICATION: "no dated measurement",
             RUN_TYPE_PROFILING: "No profile run of this project",
             RUN_TYPE_CALIBRATION: "This calibration has no measurement"}
    for rt, want in words.items():
        host = QWidget()
        host._target_ctl = types.SimpleNamespace(
            target=types.SimpleNamespace(run_type=rt))
        dlg = MeasurementReportDialog(AppSettings(), host, initial_ti3=None)
        try:
            text = dlg._view.toPlainText()
            assert want in text, (rt, text)
            assert "Add Profile's Measurements" in text
            assert dlg._profile_list.count() == 0
            dlg._on_clear_list()
            assert "Open a measurement file" in dlg._view.toPlainText()
        finally:
            dlg.close()
            host.deleteLater()
