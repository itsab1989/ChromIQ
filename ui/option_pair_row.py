"""Two options side by side, stacked only when the width is genuinely not there.

**Why this exists.** The Create Chart / Guided "Chart Size" group put its two
switches on one `QHBoxLayout`: `-L`, its info button, a stretch, `-P`, its info
button. A `QHBoxLayout`'s minimum width is the sum of its items, so that row
demanded 527 px however narrow the panel got, the panel's own minimum rose with
it, and the panel sits in a `FadeScrollArea` whose horizontal policy is
`ScrollBarAlwaysOff` inside a left column pinned by `setFixedWidth(580)`.

Measured on the downloaded v4.3.0-beta.30 arm64 dmg, driven on screen: in
Ukrainian the panel wanted **569 px inside a 540 px viewport**, the scroll area's
`horizontalScrollBar().maximum()` was **29** with the bar switched off, and
**five of the six info buttons on that panel were sliced in half** by the
viewport edge. Thirteen languages fitted. That is not a Ukrainian fault: it is a
cliff every language stands on, and Swedish stood 2 px from it
(`minimumSizeHint` 538 against the same 540).

**What this widget does not change.** When the one-line arrangement fits, the
geometry is the one the `QHBoxLayout` produced, to the pixel: first option hard
left, its button ten pixels after it, second option's button flush to the right
edge so it lines up under the row above, second option ten pixels left of that.
Every language that fits today is untouched. Only when the line cannot hold both
does the second option drop to its own line, and there its button keeps the same
right edge, which is where every other info button on that panel already sits.

The width it reports as its minimum is therefore the WIDER OF THE TWO OPTIONS,
not their sum, so the panel can no longer demand more width than it is given.
"""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QSizePolicy, QWidget

#: The EXPLICIT half of the gap between an option and its own info button:
#: what the replaced row spelled as `addSpacing(10)`. A `QHBoxLayout` also puts
#: its own `spacing()` between every pair of items, so the gap on screen was
#: 10 + 6 = 16, not 10. Measured at HEAD before the replacement: the -L button
#: sat at x=228 with the option ending at 212. Getting this wrong moved two
#: widgets six pixels and left the outer edges looking right.
BUTTON_GAP = 10

#: Smallest gap tolerated between the two options before the row wraps. A row
#: whose two halves touch reads as one control, so "it fits" has to mean "it
#: fits with a gap you can see". Measured against the panel's own rhythm: the
#: group box's layout spacing is 6, and this is the same value.
MIN_SPREAD = 6


class OptionPairRow(QWidget):
    """One line holding two (option, info button) pairs, wrapping when needed.

    The four widgets are parented elsewhere by the caller and re-parented here.
    Either pair may be hidden (the instrument decides), and a hidden pair takes
    no width and no line.
    """

    def __init__(self, left, left_button, right, right_button,
                 parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._left = left
        self._left_button = left_button
        self._right = right
        self._right_button = right_button
        self._spacing = spacing
        for w in (left, left_button, right, right_button):
            w.setParent(self)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Minimum)

    # -- the two halves -------------------------------------------------
    def _gap(self) -> int:
        """The gap the replaced `QHBoxLayout` actually put on screen."""
        return BUTTON_GAP + self._spacing

    @staticmethod
    def _effective(widget) -> QSize:
        """The size a QLayout would give this widget, not its bare sizeHint.

        **A ONE-PIXEL BUG LIVED HERE AND WAS MEASURED OUT OF IT.** The info
        buttons report `sizeHint().width()` 21 and enforce a minimum of 22, so
        placing one at `right - 21` and handing `setGeometry` a width of 21 let
        Qt grow it back to 22 *keeping its left edge* — one pixel past the
        right edge, while the five other info buttons on the panel sat at 526.
        A layout expands the hint against the minimum BEFORE it positions
        anything, which is what this does.
        """
        return (widget.sizeHint()
                .expandedTo(widget.minimumSizeHint())
                .expandedTo(QSize(widget.minimumWidth(),
                                  widget.minimumHeight())))

    def _pair(self, widget, button) -> tuple:
        """(visible, width, height) of one option and its button."""
        if not widget.isVisibleTo(self) and not button.isVisibleTo(self):
            return (False, 0, 0)
        ws, bs = self._effective(widget), self._effective(button)
        return (True, ws.width() + self._gap() + bs.width(),
                max(ws.height(), bs.height()))

    def _halves(self) -> tuple:
        return (self._pair(self._left, self._left_button),
                self._pair(self._right, self._right_button))

    def _one_line_width(self) -> int:
        (lv, lw, _), (rv, rw, _) = self._halves()
        if lv and rv:
            return lw + MIN_SPREAD + rw
        return lw if lv else rw

    # -- Qt size protocol ----------------------------------------------
    def hasHeightForWidth(self) -> bool:                      # noqa: D102
        return True

    def heightForWidth(self, width: int) -> int:              # noqa: D102
        (lv, _, lh), (rv, _, rh) = self._halves()
        if not lv and not rv:
            return 0
        if lv and rv and width < self._one_line_width():
            return lh + self._spacing + rh
        return max(lh, rh)

    def sizeHint(self) -> QSize:                              # noqa: D102
        (lv, _, lh), (rv, _, rh) = self._halves()
        return QSize(self._one_line_width(), max(lh, rh, 0))

    def minimumSizeHint(self) -> QSize:                       # noqa: D102
        # THE WHOLE POINT. The sum of the two halves is what the QHBoxLayout
        # demanded and what pushed the panel past its viewport; the wider
        # single half is what this row actually cannot go below.
        (lv, lw, lh), (rv, rw, rh) = self._halves()
        if not lv and not rv:
            return QSize(0, 0)
        return QSize(max(lw, rw), self.heightForWidth(max(lw, rw)))

    # -- placement ------------------------------------------------------
    def resizeEvent(self, event) -> None:                     # noqa: D102
        super().resizeEvent(event)
        self._place()

    def showEvent(self, event) -> None:                       # noqa: D102
        super().showEvent(event)
        self._place()

    def relayout(self) -> None:
        """Re-place after a caller changed which halves are visible."""
        self.updateGeometry()
        self._place()

    def _put(self, widget, button, x_left: int, x_right: int,
             top: int, line_h: int) -> None:
        """One option at the left edge, its button flush to the right edge."""
        ws, bs = self._effective(widget), self._effective(button)
        widget.setGeometry(x_left, top + (line_h - ws.height()) // 2,
                           ws.width(), ws.height())
        button.setGeometry(x_right - bs.width(),
                           top + (line_h - bs.height()) // 2,
                           bs.width(), bs.height())

    def _place(self) -> None:
        (lv, lw, lh), (rv, rw, rh) = self._halves()
        width = self.width()
        if lv and rv and width >= self._one_line_width():
            # ONE LINE, exactly as the QHBoxLayout laid it out: the left
            # option hard left with its button BUTTON_GAP after it, and the
            # right option's button flush to the right edge.
            line_h = max(lh, rh)
            ls = self._effective(self._left)
            bs = self._effective(self._left_button)
            self._left.setGeometry(0, (line_h - ls.height()) // 2,
                                   ls.width(), ls.height())
            self._left_button.setGeometry(
                ls.width() + self._gap(), (line_h - bs.height()) // 2,
                bs.width(), bs.height())
            self._put(self._right, self._right_button,
                      width - rw, width, 0, line_h)
            return
        # STACKED, or a single visible half. Each visible option starts at the
        # left edge and its button ends at the right edge, which is where every
        # other info button in this panel sits.
        top = 0
        if lv:
            self._put(self._left, self._left_button, 0, width, top, lh)
            top += lh + (self._spacing if rv else 0)
        if rv:
            self._put(self._right, self._right_button, 0, width, top, rh)
