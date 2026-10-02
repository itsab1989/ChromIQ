"""Knut's beta 5 runs (#182, 2026-10-03): the clear bugs the challenge found.

Evidence: Knut's run2/run3 folders, his chromiq.log and the challenge notes
(``CHALLENGE_NOTES.txt``, verdicts 3 and 6). None of these changes the Check &
Refine decision rule itself; that is k5, awaiting Knut.

1. The start-over reason sentence was an f-string outside ``tr()`` with two em
   dashes in it; the .txt report's two headings were untranslated.
2. A start-over window explained the grade with *"Re-measuring the flagged
   strips can help"* directly above *"Re-measuring individual strips is
   unlikely to reliably fix this"*, and offered no strips.
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
    ProfcheckResult, quality_explanation, recommends_start_over,
    start_over_reason)


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
            errs.append((f"{s}{row}", 2.6 if row == 5 else 0.8))
    return ProfcheckResult(avg_de=1.03, peak_de=4.87, patch_errors=errs,
                           raw_log="profcheck output")


# ---- 1. the reason sentence --------------------------------------------------

def test_the_start_over_reason_is_translated_and_has_no_em_dash(german):
    strips = start_over_reason(24, 648, 24, 24, 2.0)
    assert strips == ("24 von 24 Streifen (100 %) müssen nachgemessen werden: "
                      "mehr als drei Viertel deines Charts.")
    patches = start_over_reason(400, 648, 24, 24, 2.0)
    assert patches.startswith("400 von 648 Messfeldern (62 %) liegen über ΔE 2.0")
    for text in (strips, patches):
        assert "—" not in text


def test_the_start_over_reason_has_a_real_singular():
    assert start_over_reason(1, 1, 1, 1, 2.0) == "Your only patch exceeds ΔE 2.0."
    assert start_over_reason(0, 27, 1, 1, 2.0) == \
        "Your chart's only strip needs re-measuring."
    assert start_over_reason(3, 5, 1, 1, 2.0).startswith(
        "3 out of 5 patches (60%) exceed")


def test_the_window_no_longer_builds_the_sentence_itself():
    from ui.tabs.tab_check_refine import TabCheckRefine
    src = inspect.getsource(TabCheckRefine._show_result_dialog)
    assert "more than three-quarters" not in src
    assert "start_over_reason(" in src


def test_the_rule_itself_is_unchanged():
    """>50 % of patches or >75 % of strips, strictly greater, as before."""
    assert recommends_start_over(325, 648, 0, 24)
    assert not recommends_start_over(324, 648, 0, 24)
    assert recommends_start_over(0, 648, 19, 24)
    assert not recommends_start_over(0, 324, 9, 12)   # Knut's run3 QC1: 75 %


# ---- 2. the grade text agrees with the verdict -----------------------------

@pytest.mark.parametrize("avg, peak", [
    (1.5, 6.0),     # rank 2, peak-limited
    (2.2, 2.5),     # rank 2, average-limited
    (1.0, 9.0),     # rank 3, peak-limited (avg good)
    (6.0, 7.0),     # rank 3, average-limited
])
def test_a_start_over_explanation_advises_no_re_measuring(avg, peak):
    plain = quality_explanation(avg, peak)
    over = quality_explanation(avg, peak, start_over=True)
    assert "Re-measuring" in plain, "precondition: the refine advice exists"
    assert "Re-measuring" not in over and "re-measuring" not in over
    # the description of the grade itself is kept, word for word
    assert plain.startswith(over)


def test_a_start_over_explanation_is_translated(german):
    over = quality_explanation(1.5, 6.0, start_over=True)
    assert "Nachmessen" not in over
    assert over.endswith("in bestimmten Bereichen.")


# ---- 1/2/3 the window and the report agree ------------------------------------

def _tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    return TabCheckRefine(ArgyllRunner(s), s)


def _window_text(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QLabel
    from workflow.profcheck_runner import group_by_strip, strips_to_refine
    tab = _tab(qapp, tmp_path)
    tab._threshold_spin.setValue(2.0)
    res = _run2_like_result()
    seen = []

    def _exec(dlg):
        seen.append("\n".join(lbl.text() for lbl in dlg.findChildren(QLabel)))
        return 0
    monkeypatch.setattr(QDialog, "exec", _exec)
    refine = strips_to_refine(res.patch_errors, threshold=2.0)
    tab._show_result_dialog(res, group_by_strip(res.patch_errors), refine,
                            None, True, len(refine), 24, 24, 648)
    return tab, res, refine, seen[0]


def test_the_start_over_window_says_one_thing(qapp, tmp_path, monkeypatch):
    _tab_, _res, _refine, text = _window_text(qapp, tmp_path, monkeypatch)
    assert "Starting over with a freshly printed" in text
    assert "24 out of 24 strips (100%) need re-measuring" in text
    assert "can help" not in text
    assert "— more than" not in text


def test_the_report_carries_the_verdict_the_window_shows(qapp, tmp_path,
                                                         monkeypatch):
    from ui.tabs.tab_check_refine import TabCheckRefine
    from workflow.profcheck_runner import group_by_strip
    res = _run2_like_result()
    refine = [(chr(ord("A") + i), 2.6) for i in range(24)]
    text = TabCheckRefine._report_summary_text(
        res, group_by_strip(res.patch_errors), refine, True, 2.0,
        24, 24, 24, 648)
    assert "24 out of 24 strips (100%) need re-measuring" in text
    assert "Starting over with a freshly printed and measured chart is " \
           "strongly recommended." in text
    assert "<b>" not in text and "<br>" not in text
    assert "can help" not in text
    assert "Patches with highest error" in text
    # no flagged-strip list: the window offers none either
    assert "Strips flagged for re-measurement" not in text


def test_the_report_without_start_over_keeps_its_strip_list(qapp):
    from ui.tabs.tab_check_refine import TabCheckRefine
    res = ProfcheckResult(avg_de=1.5, peak_de=3.0,
                          patch_errors=[("A1", 3.0), ("B1", 0.5),
                                        ("C1", 0.4), ("D1", 0.3)])
    text = TabCheckRefine._report_summary_text(
        res, [("A", 3.0)], [("A", 3.0)], False, 2.0, 1, 4, 1, 4)
    assert "Strips flagged for re-measurement (in measurement order, " \
           "threshold ΔE > 2.0):\n  A     max ΔE: 3.00" in text
    assert "Starting over" not in text


def test_the_report_headings_are_translated(german):
    from ui.tabs.tab_check_refine import TabCheckRefine
    res = _run2_like_result()
    text = TabCheckRefine._report_summary_text(
        res, [("A", 1.0)], [("A", 2.6)], False, 2.0, 1, 24, 24, 648)
    assert "Streifen mit dem größten Fehler (schlechteste zuerst, Ø ΔE):" in text
    assert "Messfelder mit dem größten Fehler" in text
    assert "Zum Nachmessen markierte Streifen (in Messreihenfolge, " \
           "Schwelle ΔE > 2.0):" in text
    assert "Strips with highest error" not in text


def test_the_saved_report_is_the_summary(qapp, tmp_path, monkeypatch):
    """`_on_done` writes the same text into Quality_Check_N.txt."""
    from PyQt6.QtWidgets import QDialog
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
    assert "24 out of 24 strips (100%) need re-measuring" in body
    assert "Starting over with a freshly printed" in body
    assert "can help" not in body
    assert not list(ti3.parent.glob("Refine_Strips_*"))


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
