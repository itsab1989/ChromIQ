"""A wrapped checkbox label is drawn by ONE style call, not one per line.

WHY THIS FILE EXISTS
--------------------
`WrappingCheckBox.paintEvent` used to loop over the wrapped lines and call
``QStyle::drawControl(CE_CheckBoxLabel, …)`` once for each, with a
`QStyleOptionButton` it built itself and a rect it placed itself. On the
owner's Windows 11 ARM64 VM, 2026-09-03, an xdist worker died inside exactly
that call:

    Windows fatal exception: access violation
    Current thread 0x000003f4 (most recent call first):
      File "...\\ui\\widgets.py", line 1737 in paintEvent
      File "...\\pytestqt\\plugin.py", line 220 in _process_events

Line 1737 was the `drawControl` **inside the loop** — verified against the
commit the VM ran (`4305d211`). It happened in two independent `--runslow`
attempts, under different `PYTHONUTF8` settings, and each time the session then
hung instead of ending.

**The mechanism was never named**, and this file does not claim otherwise. It
could not be reproduced on macOS: over a full suite, no garbage collection ever
began inside this paint (0 of 39,339), the painter was never inactive, no rect
was ever invalid, Qt emitted no message inside it, and painting a deliberately
deleted widget raises `RuntimeError` rather than faulting. What the change does
is make the multi-line path do the same two style calls the single-line path
does — the branch that has never been implicated — and Qt lay the lines out
instead of us.

So what is pinned here is the SHAPE, because the shape is the only part anybody
can be sure about: **however many lines the label wraps to, the style is
entered once for the label.** Plus the two things that must not regress with
it: every line still reaches the screen, and the indicator still sits on the
first line rather than in the middle of the block.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Long enough to wrap to several lines in a narrow parent. German is the
# language whose labels wrap most, which is why it is the one that matters.
LONG_DE = ("Messgeräte-Rand-Hilfslinien in der Vorschau anzeigen "
           "(gepunktete Linien) und jede Zeile dabei sauber umbrechen")
SHORT = "Show strip indicators"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _Counting:
    """A QProxyStyle that counts what the widget asks the style to draw.

    It is built from a style of its OWN (`QProxyStyle(name)`), never from
    `QApplication.style()`. A QProxyStyle takes ownership of the style it wraps,
    so wrapping the application's style hands it to a Python object that dies at
    the end of the test — and the next widget built after that segfaults on a
    dangling `QStyle*`. Written down because it happened here, on macOS, while
    writing this file: `WrappingCheckBox.__init__` line 1604,
    `Fatal Python error: Segmentation fault`.
    """

    def __new__(cls, base_name="Fusion"):
        from PyQt6.QtWidgets import QProxyStyle, QStyle

        class Counter(QProxyStyle):
            def __init__(self, b):
                super().__init__(b)
                self.labels = 0
                self.indicators = 0
                self.label_texts = []
                self.label_rects = []
                self.indicator_rects = []

            def drawControl(self, element, option, painter, widget=None):  # noqa: N802
                if element == QStyle.ControlElement.CE_CheckBoxLabel:
                    self.labels += 1
                    self.label_texts.append(option.text)
                    self.label_rects.append(option.rect)
                super().drawControl(element, option, painter, widget)

            def drawPrimitive(self, element, option, painter, widget=None):  # noqa: N802
                if element == QStyle.PrimitiveElement.PE_IndicatorCheckBox:
                    self.indicators += 1
                    self.indicator_rects.append(option.rect)
                super().drawPrimitive(element, option, painter, widget)

        return Counter(base_name)


def _box(qapp, text, parent_width):
    """A shown WrappingCheckBox in a parent of the given width, with a counting
    style installed, plus the counter."""
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    from ui.widgets import WrappingCheckBox

    host = QWidget()
    host.resize(parent_width, 300)
    lay = QVBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    cb = WrappingCheckBox(text, host)
    lay.addWidget(cb)
    lay.addStretch(1)
    counter = _Counting()
    cb.setStyle(counter)
    host.show()
    qapp.processEvents()
    return host, cb, counter


def _lines_of(cb):
    from PyQt6.QtWidgets import QStyle, QStyleOptionButton
    opt = QStyleOptionButton()
    cb.initStyleOption(opt)
    r = cb.style().subElementRect(
        QStyle.SubElement.SE_CheckBoxContents, opt, cb)
    return cb._lines(r.width())


@pytest.mark.parametrize("width", [120, 160, 200, 240])
def test_a_wrapped_label_is_one_style_call_however_many_lines(qapp, width):
    """The whole point. Four lines used to mean four `drawControl` calls."""
    host, cb, counter = _box(qapp, LONG_DE, width)
    try:
        n = len(_lines_of(cb))
        assert n > 1, (
            f"this case no longer wraps at {width} px, so it proves nothing — "
            f"pick a narrower parent or a longer label")
        counter.labels = 0
        cb.repaint()
        qapp.processEvents()
        assert counter.labels == 1, (
            f"the label wrapped to {n} lines and the style was entered "
            f"{counter.labels} times to draw it. It must be entered ONCE. "
            f"Drawing a wrapped label one line at a time, with hand-built "
            f"options and hand-placed rects, is the construct a Windows worker "
            f"died inside on 2026-09-03")
    finally:
        host.close()


def test_a_one_line_label_is_also_one_style_call(qapp):
    """The branch that never crashed must not have grown a second call."""
    host, cb, counter = _box(qapp, SHORT, 600)
    try:
        assert len(_lines_of(cb)) == 1
        counter.labels = 0
        cb.repaint()
        qapp.processEvents()
        assert counter.labels == 1
    finally:
        host.close()


def test_the_style_is_handed_every_line_not_just_the_first(qapp):
    """One call must not mean one LINE. The text the style receives carries all
    of them, separated by newlines — which is a hard break to
    `QPainter::drawText(rect, flags, text)`."""
    host, cb, counter = _box(qapp, LONG_DE, 160)
    try:
        lines = _lines_of(cb)
        assert len(lines) > 1
        counter.label_texts.clear()
        cb.repaint()
        qapp.processEvents()
        assert counter.label_texts, "the label was never drawn"
        drawn = counter.label_texts[-1]
        assert drawn == "\n".join(lines), (
            f"the style was handed {drawn!r}, which is not the whole wrapped "
            f"label {lines!r}. If only the first line arrives, the user reads "
            f"half an option")
        assert drawn.count("\n") == len(lines) - 1
    finally:
        host.close()


def test_every_wrapped_line_actually_reaches_the_pixels(qapp):
    """A guard against the failure the newline join could have: the style
    honouring `\\n` is a property of `QStyle::drawItemText`, not a promise. So
    look at the ink, not at the call."""
    from PyQt6.QtGui import QColor, QImage

    host, cb, counter = _box(qapp, LONG_DE, 160)
    try:
        lines = _lines_of(cb)
        assert len(lines) > 1
        img = QImage(cb.width(), cb.height(),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor("white"))
        cb.render(img)

        # ink to the RIGHT of the indicator, per row: which rows carry text?
        left = counter.indicator_rects[-1].right() + 4
        inked = [y for y in range(img.height())
                 if any(img.pixelColor(x, y) != QColor("white")
                        for x in range(left, img.width()))]
        assert inked, "no label ink at all"
        # Rows of ink can touch (a descender meets the next line's ascender),
        # so count the vertical REACH rather than the gaps: N lines cannot fit
        # in less than (N-1) line spacings plus a little.
        reach = inked[-1] - inked[0] + 1
        line_h = cb.fontMetrics().lineSpacing()
        assert reach >= (len(lines) - 1) * line_h, (
            f"the label wraps to {len(lines)} lines at {line_h} px each, but "
            f"its ink is only {reach} px tall. Only the first line, or too few "
            f"of them, is being painted")
    finally:
        host.close()


def test_the_indicator_sits_on_the_first_line(qapp):
    """A box centred over a four-line block reads as belonging to none of them.
    This is the deliberate placement the multi-line branch exists for."""
    host, cb, counter = _box(qapp, LONG_DE, 160)
    try:
        lines = _lines_of(cb)
        assert len(lines) > 1
        counter.indicator_rects.clear()
        counter.label_rects.clear()
        cb.repaint()
        qapp.processEvents()
        ind = counter.indicator_rects[-1]
        block = counter.label_rects[-1]
        line_h = cb.fontMetrics().lineSpacing()
        assert ind.center().y() <= block.top() + line_h, (
            f"the indicator is centred at y={ind.center().y()}, below the "
            f"first line of a block that starts at {block.top()} and is "
            f"{line_h} px per line — it has drifted into the middle of the "
            f"label again")
    finally:
        host.close()


def test_the_label_block_is_centred_in_the_contents_rect(qapp):
    """The block keeps the vertical placement the per-line loop computed, so
    nothing moves on screen."""
    from PyQt6.QtWidgets import QStyle, QStyleOptionButton

    host, cb, counter = _box(qapp, LONG_DE, 160)
    try:
        lines = _lines_of(cb)
        assert len(lines) > 1
        counter.label_rects.clear()
        cb.repaint()
        qapp.processEvents()
        block = counter.label_rects[-1]
        opt = QStyleOptionButton()
        cb.initStyleOption(opt)
        contents = cb.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxContents, opt, cb)
        line_h = cb.fontMetrics().lineSpacing()
        assert block.height() == len(lines) * line_h
        assert block.left() == contents.left()
        assert block.width() == contents.width()
        expected_top = contents.top() + max(
            0, (contents.height() - len(lines) * line_h) // 2)
        assert block.top() == expected_top
    finally:
        host.close()
