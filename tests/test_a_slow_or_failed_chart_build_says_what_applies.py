"""Beta 12, from the beta-11 targen review (F-10, on screen):

1. The "taking longer than usual" window shown during a PLAIN CMYK chart build
   spoke of pre-conditioning profiles, "the same profile" and "a refinement
   chart", though the build used neither. It now names only what applies: a
   build that passes targen a profile (-c) keeps the window's text, one without
   shows M-CHART-SLOW-NO-PROFILE.
2. The targen failure window quoted only "targen: Error -", because Argyll
   writes the marker and the sentence as two writes and the runner emits a
   read without a newline at once. The continuation is joined on.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from workflow import chart_creator as cc  # noqa: E402
from workflow.chart_creator import ChartCreator  # noqa: E402
from workflow.measurement_messages import M_CHART_SLOW_NO_PROFILE  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _creator():
    c = ChartCreator.__new__(ChartCreator)
    c._matched_errors = []
    c._matched_warnings = []
    c._raw_errors = []
    return c


# ---- 2. the whole Argyll error -------------------------------------------
OFPS = ("ofps: assert, node vertex info should be empty on "
        "add_node2voronoi() entry")


def test_an_error_split_over_two_reads_is_quoted_whole():
    c = _creator()
    c._scan_line("targen", "Re-seeding")
    c._scan_line("targen", "targen: Error -")
    c._scan_line("targen", OFPS)
    tool, said = c.unmatched_failure()
    assert tool == "targen"
    assert said == f"targen: Error - {OFPS}"
    assert len(c._raw_errors) == 1, c._raw_errors


def test_the_marker_with_a_trailing_space_is_joined_too():
    c = _creator()
    c._scan_line("targen", "targen: Error - ")
    c._scan_line("targen", "Failed to re-seed the voronoi after 100 tries")
    assert c.unmatched_failure()[1] == (
        "targen: Error - Failed to re-seed the voronoi after 100 tries")


def test_an_error_on_one_line_is_unchanged():
    c = _creator()
    c._scan_line("targen", f"targen: Error - {OFPS}")
    c._scan_line("targen", "some later line")
    assert c.unmatched_failure()[1] == f"targen: Error - {OFPS}"


def test_a_joined_line_still_reaches_the_known_patterns():
    """A recognised message split the same way is still recognised."""
    c = _creator()
    c._scan_line("targen", "targen: Error -")
    c._scan_line("targen", "ICC profile doesn't match device!")
    assert c.primary_failure() is not None
    assert c.primary_failure()[1] == "icc_profile_mismatch"
    assert c.unmatched_failure() is None


def test_a_line_from_another_tool_is_not_joined():
    c = _creator()
    c._scan_line("targen", "targen: Error -")
    c._scan_line("printtarg", "printtarg: something else")
    assert c.unmatched_failure() == ("targen", "targen: Error -")


def test_a_new_build_forgets_a_held_marker():
    """Every place that resets the error lists resets the held marker too."""
    src = inspect.getsource(ChartCreator)
    assert src.count("self._raw_errors = []") == src.count(
        "self._error_stem = None") - 1   # plus the one inside _scan_line


# ---- 1. the slow-chart window --------------------------------------------
@pytest.mark.parametrize("argv,expected", [
    (["-v", "-d4", "-f200", "-l300"], False),
    (["-v", "-d2", "-f400", "-c", "/x/profile.icc"], True),
    (["-v", "-d2", "-c/x/profile.icc"], True),
    (["-v", "-d2", "-c"], False),
])
def test_the_creator_knows_whether_targen_has_a_profile(argv, expected):
    assert cc._argv_has_profile(argv) is expected


def test_the_creator_reports_it_for_the_window():
    c = _creator()
    assert c.targen_uses_profile() is False      # before any targen ran
    c._targen_uses_profile = True
    assert c.targen_uses_profile() is True
    src = inspect.getsource(ChartCreator._start_targen)
    assert "self._targen_uses_profile = _argv_has_profile(targen_args)" in src


def _body(dlg) -> str:
    texts = [lab.text() for lab in dlg.findChildren(QLabel)]
    return max(texts, key=len)


def test_a_plain_build_hears_nothing_about_profiles(qapp):
    from ui.dialogs.slow_chart_dialog import SlowChartDialog
    dlg = SlowChartDialog(None, uses_profile=False)
    try:
        body = _body(dlg)
        assert body == M_CHART_SLOW_NO_PROFILE.render()[1]
        low = body.lower()
        for word in ("pre-conditioning", "refinement", "profile"):
            assert word not in low, word
    finally:
        dlg.deleteLater()


def test_a_build_with_a_profile_keeps_its_text(qapp):
    from ui.dialogs.slow_chart_dialog import SlowChartDialog
    dlg = SlowChartDialog(None, uses_profile=True)
    try:
        body = _body(dlg)
        assert "pre-conditioning profiles" in body
        assert "refinement chart" in body
    finally:
        dlg.deleteLater()


def test_the_tab_asks_the_creator():
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_slow_watchdog)
    assert "uses_profile=self._creator.targen_uses_profile()" in src
