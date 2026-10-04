"""Knut's beta 5 runs (#182, 2026-10-03): the clear bugs the challenge found.

Evidence: Knut's run2/run3 folders, his chromiq.log and the challenge notes
(``CHALLENGE_NOTES.txt``, verdicts 3 and 6). None of these changes the Check &
Refine decision rule itself; that is k5, awaiting Knut.

1. The start-over reason sentence was an f-string outside ``tr()`` with two em
   dashes in it; the .txt report's two headings were untranslated.
2. (Reverted on Knut's ruling, #182 5963360295: the grade's *"Re-measuring
   the flagged strips can help"* stays in a start-over window too.)
3. The saved Quality_Check .txt left out the start-over verdict the window
   showed.
4. Guided refinement announced *"worst ΔE first"* and then visited the strips
   in chart order (A, C, D, E, G, ...).
5. *"has no measurement to resume from"* was logged a moment before the dated
   verification was staged beside the chart and resumed.
6. A profile build wrote neither its parameters nor its result to chromiq.log.
"""
from __future__ import annotations

import inspect
import logging
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import i18n                                       # noqa: E402
from workflow.profcheck_runner import (                     # noqa: E402
    ProfcheckResult, quality_explanation, quality_explanation_body)


@pytest.fixture
def german():
    i18n.set_language("de")
    try:
        yield
    finally:
        i18n.set_language("en")


def _run2_like_result():
    """24 strips of 27 patches, every strip with one patch above 2.0 (QC6)."""
    letters = [chr(ord("A") + i) for i in range(24)]
    errs = []
    for s in letters:
        for row in range(1, 28):
            errs.append((f"{s}{row}",
                         2.1 if row == 5 else 0.3 + 0.05 * (row % 10)))
    return ProfcheckResult(avg_de=1.03, peak_de=4.87, patch_errors=errs,
                           raw_log="profcheck output")


# ---- 1. the start-over sentence ----------------------------------------------
# The strip-count reason ("more than three-quarters of your chart") went with
# the rule itself: Knut approved the redesign on 2026-10-03 (#182 5963903650),
# start over only above half of ALL patches, refinement still offered. Its
# note is M-CR-START-OVER; test_182_check_refine_redesign.py holds the rest.

def _plan(res, thr=2.0):
    from workflow.refine_plan import build_plan, parse_patches
    return build_plan(parse_patches("", res.patch_errors), thr, "ΔE00")


def test_the_start_over_note_is_translated_and_has_no_em_dash(german):
    from workflow.refine_plan import plan_text
    res = _run2_like_result()
    res.patch_errors = [(p, 2.1) for p, _de in res.patch_errors[:400]] \
        + res.patch_errors[400:]
    t = plan_text(_plan(res), res.avg_de, res.peak_de)
    assert t.start_over
    assert "More than half" not in t.start_over
    assert "—" not in t.start_over


def test_the_window_no_longer_builds_the_sentence_itself():
    from ui.tabs.tab_check_refine import TabCheckRefine
    src = inspect.getsource(TabCheckRefine._show_result_dialog)
    assert "more than three-quarters" not in src
    assert "plan_text(" in src


def test_the_strip_count_rule_is_retired():
    """>50 % of ALL patches, strictly; the >75 %-of-strips rule is gone
    (Knut, 5963903650 Q2)."""
    from workflow.refine_plan import recommends_start_over
    assert recommends_start_over(325, 648)
    assert not recommends_start_over(324, 648)
    plan = _plan(_run2_like_result())          # every strip flagged
    assert len(plan.offered) == 24 and not plan.start_over


# ---- 2. the grade text keeps its refine advice (Knut, 5963360295) ----------

@pytest.mark.parametrize("avg, peak", [
    (1.5, 6.0),     # rank 2, peak-limited
    (2.2, 2.5),     # rank 2, average-limited
    (1.0, 9.0),     # rank 3, peak-limited (avg good)
    (6.0, 7.0),     # rank 3, average-limited
])
def test_the_explanation_keeps_its_re_measuring_advice(avg, peak):
    """Knut, #182 5963360295: *"Re-measuring the flagged strips can help"*
    stays, start-over or not: on a first run nobody knows that re-measuring
    would not help. The explanation has no start-over variant."""
    assert "Re-measuring" in quality_explanation(avg, peak)
    assert "start_over" not in inspect.signature(quality_explanation).parameters


# ---- 1/2/3 the window and the report agree ------------------------------------

def _tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    return TabCheckRefine(ArgyllRunner(s), s)


def _window_text(qapp, tmp_path, monkeypatch, res, thr=2.0):
    from PyQt6.QtWidgets import QDialog, QLabel
    tab = _tab(qapp, tmp_path)
    tab._threshold_spin.setValue(thr)
    seen = []

    def _exec(dlg):
        seen.append("\n".join(lbl.text() for lbl in dlg.findChildren(QLabel)))
        return 0
    monkeypatch.setattr(QDialog, "exec", _exec)
    plan = _plan(res, thr)
    tab._show_result_dialog(res, plan, None)
    return plan, seen[0]


def test_the_every_strip_window_offers_refinement(qapp, tmp_path, monkeypatch):
    plan, text = _window_text(qapp, tmp_path, monkeypatch, _run2_like_result())
    assert "Starting over with a freshly printed" not in text
    assert "need re-measuring" not in text
    assert len(plan.offered) == 24
    assert "in chart order" in text
    assert quality_explanation_body(1.03, 4.87, "ΔE00") in text


def test_the_report_carries_the_start_over_note_and_the_strips(qapp):
    from ui.tabs.tab_check_refine import TabCheckRefine
    res = _run2_like_result()
    plan = _plan(res, 0.4)
    text = TabCheckRefine._report_summary_text(res, plan)
    assert "More than half of your patches are above your limit" in text
    assert len(plan.offered) == 24 and plan.start_over
    assert "Strip A  " in text and "Strip X  " in text
    assert "<b>" not in text and "<br>" not in text
    assert quality_explanation_body(1.03, 4.87, "ΔE00") in text


def test_the_report_headings_are_translated(german):
    from ui.tabs.tab_check_refine import TabCheckRefine
    res = _run2_like_result()
    text = TabCheckRefine._report_summary_text(res, _plan(res))
    assert "strips have patches above" not in text
    assert "Profile Quality Assessment" not in text


def test_the_saved_report_is_the_summary(qapp, tmp_path, monkeypatch):
    """`_on_done` writes the same text into Quality_Check_N.txt, and the
    strips file beside it."""
    from PyQt6.QtWidgets import QDialog
    from ui.tabs.tab_check_refine import TabCheckRefine
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab = _tab(qapp, tmp_path)
    tab._threshold_spin.setValue(2.0)
    ti3 = tmp_path / "run2" / "test.ti3"
    ti3.parent.mkdir()
    ti3.write_text("CTI3\n", encoding="utf-8")
    tab._ti3_path = ti3
    tab._checking_in_place = True
    res = _run2_like_result()
    monkeypatch.setattr(tab._checker, "parse_results", lambda: res)
    tab._on_done(1)
    report = next(ti3.parent.glob("Quality_Check_*_test.txt"))
    body = report.read_text(encoding="utf-8")
    assert TabCheckRefine._report_summary_text(res, tab._last_plan) in body
    assert list(ti3.parent.glob("Refine_Strips_*"))


# ---- 4. guided refinement says the order it uses -----------------------------

def test_guided_refinement_announces_chart_order():
    from workflow.measure_manager import MeasureManager

    class _M:
        _guided_step = MeasureManager._guided_step

        def __init__(self):
            self._guided_strips = ["A", "C", "D"]
            self._guided_idx = 0
            self._guided_state = "idle"
            self.moves = []

        def _navigate_toward(self, cur, tgt):
            self.moves.append((cur, tgt))

    m, lines = _M(), []
    m._guided_step("A", lines.append)
    first = lines[0]
    assert "worst" not in first
    assert first == ("[Guided Refinement] Starting auto-navigation to "
                     "3 strips: A, C, D, in chart order.")


def test_guided_refinement_line_is_translated(german):
    from workflow.measure_manager import MeasureManager

    class _M:
        _guided_step = MeasureManager._guided_step
        _guided_strips = ["B"]
        _guided_idx = 0
        _guided_state = "idle"

        def _navigate_toward(self, cur, tgt):
            pass

    lines = []
    _M()._guided_step("A", lines.append)
    assert lines[0] == ("[Geführte Verfeinerung] Automatische Navigation zu "
                        "1 Streifen: B, in Chart-Reihenfolge.")


# ---- 6. the profile build is in the log -------------------------------------

def test_an_engine_build_logs_its_settings_and_its_result(qapp, tmp_path,
                                                          monkeypatch, caplog):
    import workflow.profile_engine as pe
    from workflow import engine_builder
    from workflow.profile_engine import BuildSettings

    class _Res:
        icc_path = tmp_path / "test.icc"
        n_channels = 3
        color_rep = "RGB_XYZ"
        a2b_grid = 17
        b2a_grid = 17
        fit_median_de = 0.41
        fit_p95_de = 1.23
        fit_median_de00 = 0.30
        fit_p95_de00 = 0.90
        b2a_ingamut_median_de = 0.12
        oog_fraction = 0.25
        perceptual_distinct = False
        outlier_rows = (4, 9)

    def _fake_build(ti3, out, settings):
        settings.progress("Fitting the printer model: robust fit 1/2…")
        return _Res()
    monkeypatch.setattr(pe, "build_profile", _fake_build)
    log = logging.getLogger(engine_builder.log.name)
    monkeypatch.setattr(log, "propagate", True)
    caplog.set_level(logging.DEBUG, logger=log.name)

    s = BuildSettings(quality="h", algorithm="x", smoothing=0.7)
    summary = engine_builder.build_settings_summary(s)
    for part in ("quality='h'", "algorithm='x'", "smoothing=0.7",
                 "b2a_quality=''", "icc_version='2'"):
        assert part in summary
    assert "progress=" not in summary

    t = engine_builder._EngineThread(tmp_path / "test.ti3", tmp_path / "test.icc", s)
    t.run()                                    # synchronously, no thread
    text = caplog.text
    assert "[engine] Fitting the printer model: robust fit 1/2" in text
    assert "engine build finished in" in text
    assert "A2B grid 17" in text and "median 0.41 / 95% 1.23" in text
    assert "likely misreads 2" in text


def test_the_engine_build_call_logs_before_it_starts():
    from workflow.engine_builder import EngineProfileBuilder
    src = inspect.getsource(EngineProfileBuilder.build)
    assert 'log.info("engine build: %s -> %s  [%s]"' in src
    assert "build_settings_summary(settings)" in src


def test_a_colprof_build_logs_how_it_ended():
    from workflow.profile_builder import ProfileBuilder
    src = inspect.getsource(ProfileBuilder.build)
    assert 'log.info("colprof finished: %s"' in src
    assert 'log.warning("colprof failed with exit code %d: %s"' in src
