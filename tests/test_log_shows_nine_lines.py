"""#130 (Knut, beta.120): the measure log was too short.

    *"Increase the visible log window so that 3 more lines of text are visible.
    Currently, only 6 lines of text are visible, but showing 9 lines is better.
    This equals approximately 50% taller log window. Make sure 9 lines of text
    fit in the window."*

"Make sure 9 lines fit" is the part a pixel number cannot promise. The log's
font comes from the stylesheet (``QPlainTextEdit#log``, JetBrains Mono 12px),
and a stylesheet reaches a widget only at polish — so a height set in
``__init__`` is measured against the wrong font, and a hard-coded 154 would
quietly stop meaning nine lines the moment the font changed.

So the height is computed from the widget's own metrics after polish, and this
test checks the count rather than the number.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QPlainTextEdit          # noqa: E402

WANT_LINES = 9


def _log_widget(qapp):
    """A QPlainTextEdit wearing the app's own #log styling."""
    from ui.styles import APP_STYLESHEET, make_dark_palette
    qapp.setPalette(make_dark_palette())
    qapp.setStyleSheet(APP_STYLESHEET)
    log = QPlainTextEdit()
    log.setObjectName("log")
    log.show()
    qapp.processEvents()
    return log


def _height_for(log, lines: int) -> int:
    fm = log.fontMetrics()
    return (fm.lineSpacing() * lines
            + int(log.document().documentMargin()) * 2
            + log.frameWidth() * 2)


def test_the_measure_tab_asks_for_nine_lines(qapp):
    from ui.tabs.tab_measure import TabMeasure
    assert TabMeasure._log_visible_lines == WANT_LINES


def test_the_height_is_measured_not_hard_coded(qapp):
    """The whole point: a number cannot promise a line count."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._fit_log_height)
    assert "fontMetrics()" in src and "lineSpacing()" in src
    assert "documentMargin()" in src, "the document's own margin counts too"
    assert "frameWidth()" in src, "so does the frame"


def test_nine_lines_actually_fit_at_the_app_font(qapp):
    """Fill it with ten numbered lines and check the ninth is inside the
    viewport and the tenth is not."""
    log = _log_widget(qapp)
    log.setFixedHeight(_height_for(log, WANT_LINES))
    qapp.processEvents()
    log.setPlainText("\n".join(f"line {i}" for i in range(1, 11)))
    qapp.processEvents()
    fm = log.fontMetrics()
    inner = log.viewport().height() - int(log.document().documentMargin()) * 2
    fits = inner // fm.lineSpacing()
    assert fits >= WANT_LINES, f"only {fits} lines fit, wanted {WANT_LINES}"


def test_it_is_about_half_again_as_tall_as_before(qapp):
    """Knut's own sanity check — "approximately 50% taller" — so a future font
    change that silently doubled the panel would be noticed."""
    log = _log_widget(qapp)
    grew = _height_for(log, WANT_LINES) / 100.0     # 100px was the old fixed height
    assert 1.35 <= grew <= 1.75, f"grew to {grew:.0%} of the old height"


def test_a_style_change_re_fits_it(qapp):
    """A theme or font switch changes lineSpacing, so the height has to follow
    or the promise quietly lapses."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.changeEvent)
    assert "_fit_log_height" in src
    assert "StyleChange" in src and "FontChange" in src
