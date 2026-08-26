"""The margin warning must name WHICH minimum was missed — in every language.

The panel shows one of two sentences when a margin is short:

    "… is below the 38 mm instrument minimum"
    "… is below the 34 mm minimum set for this chart"

Knut asked for that distinction in #130 (2026-07-27) because "the minimum" alone
had him reading instrument figures into a chart that had declined them.

It was implemented by testing whether the threshold dict's `desc` ENDS WITH
"laid out to" — and `desc` is `tr()`-translated. So the test could only ever
match in English. Confirmed on screen 2026-08-26: the same chart, its own right
margin set to 20 mm, reads "below the 20 mm minimum set for this chart" in
English and "liegt unter dem Messgeräte-Minimum von 20 mm" in German, where no
instrument row anywhere says 20.

CI could not see it, because CI runs in English — and the existing test asserts
the English substring. This one asserts the CHOICE, not the wording, so it holds
in any language.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication            # noqa: E402

from workflow.margin_inspector import MarginReport, Violation   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    from ui.margin_inspector_panel import MarginInspectorPanel
    return MarginInspectorPanel()


def _report():
    return MarginReport(left_mm=20.0, right_mm=8.0, top_mm=20.0, bottom_mm=20.0,
                        strip_width_mm=10.0, page_w_mm=210.0, page_h_mm=297.0,
                        strip_length_mm=200.0, dpi=300.0)


_SHORT_RIGHT = [Violation("Right", 8.0, 20.0)]


def test_a_chart_that_declined_the_guideline_is_told_so(panel):
    panel.update_report(_report(), _SHORT_RIGHT, thresholds_defined=True,
                        notify=True,
                        thresholds={"R": 20.0, "desc": "anything at all",
                                    "source": "chart"})
    assert panel._thresholds_are_the_charts_own is True


def test_an_instrument_threshold_is_not_mistaken_for_the_charts_own(panel):
    panel.update_report(_report(), _SHORT_RIGHT, thresholds_defined=True,
                        notify=True,
                        thresholds={"R": 20.0, "desc": "i1Pro A4 Portrait"})
    assert panel._thresholds_are_the_charts_own is False


@pytest.mark.parametrize("lang", ["de", "fr", "ja", "ru", "zh_CN"])
def test_the_choice_does_not_depend_on_the_ui_language(qapp, lang):
    """THE POINT OF THIS FILE. The English-only test beside it passes today and
    passed all the way through the bug."""
    import core.i18n as i18n
    from ui.margin_inspector_panel import MarginInspectorPanel

    previous = getattr(i18n, "_language", "en")
    try:
        i18n.set_language(lang)
        p = MarginInspectorPanel()
        p.update_report(_report(), _SHORT_RIGHT, thresholds_defined=True,
                        notify=True,
                        thresholds={"R": 20.0,
                                    "desc": i18n.tr(
                                        "the margins this chart was laid out to"),
                                    "source": "chart"})
        assert p._thresholds_are_the_charts_own is True, (
            f"in {lang} the panel decided these were the INSTRUMENT's minimums, "
            "so it names a figure no instrument row carries")
    finally:
        i18n.set_language(previous)


def test_this_file_can_see_the_bug_it_was_written_for(qapp):
    """Control. Restore the old sniff and the German case must go red — without
    this, the assertions above would hold against any implementation."""
    import core.i18n as i18n
    from ui.margin_inspector_panel import MarginInspectorPanel

    previous = getattr(i18n, "_language", "en")
    try:
        i18n.set_language("de")
        desc = i18n.tr("the margins this chart was laid out to")
        assert not desc.endswith("laid out to"), (
            "the German catalogue now ends this string with the English words, "
            "so the old sniff would accidentally work and this control proves "
            "nothing")
        # The old rule, applied to the real German string:
        assert bool(desc.endswith("laid out to")) is False
        # …and the new one gets it right on the same data.
        p = MarginInspectorPanel()
        p.update_report(_report(), _SHORT_RIGHT, thresholds_defined=True,
                        notify=True,
                        thresholds={"R": 20.0, "desc": desc, "source": "chart"})
        assert p._thresholds_are_the_charts_own is True
    finally:
        i18n.set_language(previous)
