"""#130 (Knut, 2026-07-27): the margin inspector must judge a chart against the
instrument the CHART was laid out for.

Knut built a ColorMunki chart with the layout engine and was told his margins
were "below the 38 mm minimum" — i1Pro's A4 Portrait figures. With the engine
on, the printtarg -i widget is not shown, so reading the instrument from it fell
back to "i1" and the wrong thresholds were applied.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager            # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _engine_chart(tmp_path, instrument):
    ti2 = tmp_path / "P.ti2"
    ti2.write_text("chart", encoding="utf-8")
    (tmp_path / "P.channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": {"instrument": instrument}}}), encoding="utf-8")
    return ti2


def test_the_chart_says_which_instrument_it_was_laid_out_for(tab, tmp_path):
    tab._margin_ti2 = _engine_chart(tmp_path, "CM")
    assert tab._chart_instrument_flag() == "CM"


def test_a_printtarg_chart_has_nothing_to_say(tab, tmp_path):
    """No recipe, so the answer is empty and the panel's own choice stands."""
    ti2 = tmp_path / "P.ti2"; ti2.write_text("chart", encoding="utf-8")
    (tmp_path / "P.channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    tab._margin_ti2 = ti2
    assert tab._chart_instrument_flag() == ""


def test_no_chart_and_no_sidecar_are_both_safe(tab, tmp_path):
    tab._margin_ti2 = None
    assert tab._chart_instrument_flag() == ""
    ti2 = tmp_path / "Q.ti2"; ti2.write_text("chart", encoding="utf-8")
    tab._margin_ti2 = ti2                       # no .channels.json beside it
    assert tab._chart_instrument_flag() == ""


def test_a_damaged_sidecar_does_not_break_the_inspector(tab, tmp_path):
    ti2 = tmp_path / "P.ti2"; ti2.write_text("chart", encoding="utf-8")
    (tmp_path / "P.channels.json").write_text("{ not json", encoding="utf-8")
    tab._margin_ti2 = ti2
    assert tab._chart_instrument_flag() == ""


@pytest.mark.parametrize("flag,expected", [
    ("CM", "ColorMunki"), ("i1", "i1Pro"), ("p3", "i1Pro 3+"),
    ("SS", "SpectroScan"),
])
def test_each_recorded_instrument_maps_to_its_threshold_name(tab, tmp_path,
                                                             flag, expected):
    """The mapping the thresholds are looked up with — a ColorMunki chart must
    never be measured against i1Pro's minimums."""
    from ui.tabs.tab_chart import _MARGIN_INSTR_LABEL
    tab._margin_ti2 = _engine_chart(tmp_path, flag)
    assert _MARGIN_INSTR_LABEL.get(tab._chart_instrument_flag()) == expected


# ---- "Use instrument margins" switched off (Knut, #130 2026-07-27) --------
def _engine_chart_with(tmp_path, **recipe):
    ti2 = tmp_path / "P.ti2"
    ti2.write_text("chart", encoding="utf-8")
    (tmp_path / "P.channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": recipe}}), encoding="utf-8")
    return ti2


# The three tests that lived here exercised `_chart_uses_instrument_margins`,
# which nothing in the application ever called — only these assertions did. They
# were green while proving nothing about what a user sees, so the function and
# they went together (Basti, 2026-08-26). Every scenario they described is still
# covered, by the `_chart_own_margins` tests below and by
# `test_a_guided_chart_is_judged_against_its_jig.py`; that is the panel's real
# decision path.

# ---- which minimums a chart is judged against (Knut, #130 2026-07-27) -----
def test_a_chart_that_declined_the_instrument_is_judged_by_its_own_margins(
        tab, tmp_path):
    """Knut's correction: switching the guideline off must not switch the check
    off. A margin that came out under what he asked for still has to be
    reported — against HIS numbers, not the instrument's."""
    tab._margin_ti2 = _engine_chart_with(
        tmp_path, instrument="CM", use_instrument_margins=False,
        margin_top=28.0, margin_bottom=10.0, margin_left=6.0, margin_right=6.0)

    own = tab._chart_own_margins()

    assert own is not None
    assert (own["L"], own["R"], own["T"], own["B"]) == (6.0, 6.0, 28.0, 10.0)


def test_a_chart_that_kept_the_instrument_guideline_uses_preferences(tab,
                                                                     tmp_path):
    """None means "fall back to the per-instrument minimums"."""
    tab._margin_ti2 = _engine_chart_with(
        tmp_path, instrument="CM", use_instrument_margins=True,
        margin_top=28.0, margin_bottom=10.0)
    assert tab._chart_own_margins() is None


def test_charts_with_no_recipe_use_preferences(tab, tmp_path):
    ti2 = tmp_path / "P.ti2"; ti2.write_text("chart", encoding="utf-8")
    (tmp_path / "P.channels.json").write_text(json.dumps({"channels": []}), encoding="utf-8")
    tab._margin_ti2 = ti2
    assert tab._chart_own_margins() is None

    tab._margin_ti2 = None
    assert tab._chart_own_margins() is None


def test_the_reported_source_names_itself(tab, tmp_path):
    """So the panel can say where a minimum came from rather than implying it
    is the instrument's."""
    tab._margin_ti2 = _engine_chart_with(
        tmp_path, instrument="CM", use_instrument_margins=False,
        margin_top=28.0, margin_bottom=10.0)
    assert "laid out to" in tab._chart_own_margins()["desc"]


# ---- the warning must name WHICH minimum it means (Knut, 2026-07-27) ------
def test_the_warning_names_the_source_of_the_minimum():
    """Saying only "the minimum" let Knut read instrument figures into a chart
    that had declined them."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "ui" / "margin_inspector_panel.py").read_text(encoding="utf-8")
    assert "minimum set for this chart" in src
    assert "instrument minimum" in src
