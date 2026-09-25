"""A tab bar that shows it has more tabs than it can hold (#182 K32).

Knut, on the Measurement Report's graph tabs (#182 5814390886):

    *"When clicking the arrows for scrolling the tabs so to select graph tabs
    further to the right, then the right-most tab visible fits exactly on the
    left side of the two arrows. This means that the user cannot see if there
    are any more tabs hidden to the right."*

and what he asked for instead, which is what this bar does:

* **Nothing hidden on the left**: the left-most tab sits at the left edge of
  the scroll area and the LEFT arrow is greyed out.
* **Nothing hidden on the right**: the right-most tab sits at the right edge
  of the scroll area and the RIGHT arrow is greyed out.
* **Tabs hidden on a side**: part of the next tab on that side shows at the
  edge of the scroll area, `PEEK` of its width (between 1/6 and 1/4, as he
  put it), so it is plain there is more; with tabs hidden on both sides both
  arrows are live and both neighbours peek.
* **A partly shown tab is a tab**: clicking it selects it as usual, and the
  bar then moves by the same rules so it is shown whole.
* **No gap, ever** (Knut, #182 5817448879: *"always start the row at the
  left edge and let the tabs run up to the arrows, so there is never an
  empty gap"*): the row fills the whole scroll area in every state, and the
  peek on the side that ends the row takes whatever the whole tabs leave, so
  it is no longer held to 1/6..1/4 there.

Qt's own scrolling tab bar cannot do this: its scroll offset is private and
always puts the tab it scrolls to flush against the arrows. So this bar lays
the tabs out itself (`_plan`), paints them with the style (so the app's style
sheet and theme still draw every tab), and answers the mouse and the
tooltips from its own geometry.

Reusable: `PeekTabBar` is a QTabBar, so any QTabWidget can take it with
``setTabBar(PeekTabBar())`` before its first tab is added. Only the
Measurement Report's graph tabs use it today.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import (QColor, QIcon, QMouseEvent, QPainter, QPalette,
                         QPixmap, QPolygonF)
from PyQt6.QtWidgets import (QStyle, QStyleOptionTab, QStylePainter, QTabBar,
                             QToolButton)

#: How much of a hidden neighbour tab shows at the edge of the scroll area:
#: a fifth of its width, inside Knut's "between 1/4 part and 1/6 part".
PEEK = 1.0 / 5.0
#: The range the peek must stay in (what the tests hold it to).
PEEK_MIN, PEEK_MAX = 1.0 / 6.0, 1.0 / 4.0

#: How far a GREYED arrow's ink goes from the bar's ground towards the text
#: colour: a quarter of the way, against the whole way for a live one.
DEAD_ARROW_INK = 0.28

#: The arrow's triangle, in logical pixels.
ARROW_ICON = 10

#: The object name the three style sheets give the arrows' outline by
#: (Knut, #182 5832746557: the arrows had "no outline like all other buttons").
ARROW_OBJECT_NAME = "peek_tab_arrow"

#: The narrowest an arrow may be, whatever the style says.
ARROW_MIN_WIDTH = 14


def arrow_colours(pal: QPalette) -> "tuple[QColor, QColor]":
    """``(live, greyed)`` ink for the scroll arrows under *pal*.

    Taken from the palette's text and ground and mixed here, NOT from the
    palette's Disabled group: none of the app's three appearances writes that
    group, so Qt's own disabled arrow came out in the live colour and a greyed
    arrow looked exactly like a live one (challenge 2 of beta 42, #2; Knut's
    rule, #182 5814390886, is that an arrow with nowhere to go is greyed OUT,
    which is a thing a reader sees, not a flag)."""
    live = QColor(pal.color(QPalette.ColorGroup.Active,
                            QPalette.ColorRole.WindowText))
    ground = QColor(pal.color(QPalette.ColorGroup.Active,
                              QPalette.ColorRole.Window))
    t = DEAD_ARROW_INK
    dead = QColor(round(ground.red() + (live.red() - ground.red()) * t),
                  round(ground.green() + (live.green() - ground.green()) * t),
                  round(ground.blue() + (live.blue() - ground.blue()) * t))
    return live, dead


def _triangle(direction: str, colour: QColor, dpr: float) -> QPixmap:
    """A filled triangle pointing *direction* ("left"/"right")."""
    n = ARROW_ICON
    pm = QPixmap(int(round(n * dpr)), int(round(n * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(colour)
    a, b, m = 2.5, n - 2.5, n / 2.0
    if direction == "left":
        pts = [QPointF(b, 1.5), QPointF(b, n - 1.5), QPointF(a, m)]
    else:
        pts = [QPointF(a, 1.5), QPointF(a, n - 1.5), QPointF(b, m)]
    p.drawPolygon(QPolygonF(pts))
    p.end()
    return pm


class PeekTabBar(QTabBar):
    """A horizontal tab bar whose overflow shows a part of the hidden tabs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        #: Index (into the VISIBLE tabs) of the first tab shown whole.
        self._first = 0
        self._hover = -1
        # THE ARROWS ARE PAINTED HERE, NOT BY THE STYLE (challenge 2 of beta
        # 42, #2): `arrow_colours` says why the style's disabled arrow was
        # indistinguishable from a live one in all three appearances.
        self._left_btn = QToolButton(self)
        self._right_btn = QToolButton(self)
        for b in (self._left_btn, self._right_btn):
            # NOT auto-raised: an auto-raised tool button draws no frame
            # until the pointer is over it, and Knut (#182 5832746557) asked
            # for the outline every other button has. The outline itself is
            # the style sheets' `QToolButton#peek_tab_arrow` rule, one per
            # appearance, beside each sheet's QPushButton rule.
            b.setObjectName(ARROW_OBJECT_NAME)
            b.setAutoRaise(False)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setArrowType(Qt.ArrowType.NoArrow)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            b.setIconSize(QSize(ARROW_ICON, ARROW_ICON))
            b.hide()
        self._paint_arrows()
        # Bound methods, never closures (CLAUDE.md: a self-capturing lambda
        # on a signal a widget's own child emits can fault PyQt6).
        self._left_btn.clicked.connect(self.scroll_left)
        self._right_btn.clicked.connect(self.scroll_right)
        self.currentChanged.connect(self._on_current_changed)
        # Qt's own arrows and its private scroll offset are switched off:
        # this bar places the tabs itself. (After the arrows exist: each of
        # these relays the tabs out, which calls back into this class.)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setExpanding(False)
        self.setMouseTracking(True)

    # ---- geometry ----------------------------------------------------------
    def _visible(self) -> "list[int]":
        return [i for i in range(self.count()) if self.isTabVisible(i)]

    def _widths(self, vis: "list[int]") -> "list[int]":
        # Qt's own layout of each tab (never squeezed: no scroll buttons and
        # no eliding), so a tab is drawn exactly where the style expects it.
        return [self.tabRect(i).width() or self.tabSizeHint(i).width()
                for i in vis]

    def _arrow_width(self) -> int:
        """Qt's own scroll-button width, which is what the arrows were before
        this bar painted its own (Knut, #182 5832746557: *"Reduce the width of
        the arrow buttons to what they were before, approx. half the width
        they are in beta 42"*). Beta 42 made each arrow as wide as the bar is
        tall less 4 px, a square of 26 to 33 px."""
        return max(ARROW_MIN_WIDTH, self.style().pixelMetric(
            QStyle.PixelMetric.PM_TabBarScrollButtonWidth, None, self))

    def _arrow_height(self) -> int:
        return max(16, self.height() - 4)

    def _overflows(self) -> bool:
        vis = self._visible()
        return sum(self._widths(vis)) > self.width()

    def _area(self) -> int:
        """The width the tabs have: all of it, or all but the two arrows."""
        if not self._overflows():
            return self.width()
        return max(1, self.width() - 2 * self._arrow_width() - 2)

    def _window(self, first: int) -> "tuple[int, int, int, int, int]":
        """``(first, last, offset, clip_left, clip_right)`` for a start at
        *first*: the visible tabs first..last are shown whole, the content is
        shifted left by *offset* px, and only clip_left <= x < clip_right is
        drawn.

        **THE ROW ALWAYS RUNS FROM THE LEFT EDGE TO THE ARROWS (Knut, #182
        5817448879):** *"always start the row at the left edge and let the
        tabs run up to the arrows, so there is never an empty gap."* So the
        clip is always the whole scroll area, and the peeks take what the
        whole tabs leave:

        * at the left end the first tab is at the edge and the next hidden
          tab on the right fills the rest up to the arrows;
        * in the middle the hidden neighbour on the left shows `PEEK` of its
          width, the whole tabs follow, and the next hidden tab on the right
          fills the rest;
        * at the right end the last tab is against the arrows and the hidden
          neighbour on the left fills the rest from the edge.

        A peek that fills the rest is not held to `PEEK_MIN`..`PEEK_MAX`
        (K32): Knut chose no gap over an even peek."""
        vis = self._visible()
        ws = self._widths(vis)
        n = len(ws)
        area = self._area()
        total = sum(ws)
        if n == 0 or total <= area:
            return 0, n - 1, 0, 0, area
        lefts = [sum(ws[:k]) for k in range(n)]
        end = self._first_of_the_right_end(ws, area)
        first = max(0, min(first, end))
        if first == end:
            # the last tab against the arrows; the left neighbour fills the
            # rest from the edge
            return first, n - 1, total - area, 0, area
        pl = int(round(ws[first - 1] * PEEK)) if first > 0 else 0
        last = first
        while last + 1 < n:
            nxt = last + 1
            span = lefts[nxt] + ws[nxt] - lefts[first]
            if pl + span > area:
                break
            last = nxt
        return first, last, lefts[first] - pl, 0, area

    @staticmethod
    def _first_of_the_right_end(ws: "list[int]", area: int) -> int:
        """The smallest first whole tab with which every tab after it fits:
        where the bar stops going right. What is left before it is the left
        neighbour's peek."""
        n = len(ws)
        first = n - 1
        while first > 0 and sum(ws[first - 1:]) <= area:
            first -= 1
        return first

    def _plan(self) -> dict:
        """Where every visible tab is drawn: ``{"rects": {index: QRect},
        "clip": QRect, "first", "last", "left_hidden", "right_hidden"}``.
        One answer for painting, the mouse, the tooltips and a test."""
        vis = self._visible()
        ws = self._widths(vis)
        first, last, offset, c0, c1 = self._window(self._first)
        self._first = max(0, first)
        h = self.height()
        rects, x = {}, 0
        for i, w in zip(vis, ws):
            rects[i] = QRect(x - offset, 0, w, h)
            x += w
        return {"rects": rects, "clip": QRect(c0, 0, max(0, c1 - c0), h),
                "first": first, "last": last,
                "left_hidden": first > 0,
                "right_hidden": last < len(vis) - 1,
                "visible": vis}

    def _place_arrows(self) -> None:
        over = self._overflows()
        aw, ah = self._arrow_width(), self._arrow_height()
        y = max(0, (self.height() - ah) // 2)
        self._right_btn.setGeometry(self.width() - aw, y, aw, ah)
        self._left_btn.setGeometry(self.width() - 2 * aw - 1, y, aw, ah)
        self._left_btn.setVisible(over)
        self._right_btn.setVisible(over)
        if over:
            plan = self._plan()
            # KNUT: an arrow with nothing to scroll to is greyed out.
            self._left_btn.setEnabled(plan["left_hidden"])
            self._right_btn.setEnabled(plan["right_hidden"])

    # ---- scrolling ---------------------------------------------------------
    def scroll_left(self) -> None:
        if self._first > 0:
            self._first -= 1
        self._relayout()

    def scroll_right(self) -> None:
        plan = self._plan()
        if plan["right_hidden"]:
            # far enough that the next hidden tab is shown whole
            vis = plan["visible"]
            target = plan["last"] + 1
            while self._first < len(vis) - 1:
                self._first += 1
                if self._plan()["last"] >= target:
                    break
        self._relayout()

    def ensure_shown(self, index: int) -> None:
        """Move as little as needed for tab *index* to be shown whole."""
        vis = self._visible()
        if index not in vis or not self._overflows():
            self._relayout()
            return
        k = vis.index(index)
        plan = self._plan()
        if k < plan["first"]:
            self._first = k
        elif k > plan["last"]:
            while self._first < len(vis) - 1 and self._plan()["last"] < k:
                self._first += 1
        self._relayout()

    def _on_current_changed(self, index: int) -> None:
        self.ensure_shown(index)

    def _relayout(self) -> None:
        if not hasattr(self, "_right_btn"):
            return                      # still inside QTabBar.__init__
        self._place_arrows()
        self.update()

    def _paint_arrows(self) -> None:
        """Give each arrow a live and a greyed picture in this palette."""
        live, dead = arrow_colours(self.palette())
        dpr = max(1.0, float(self.devicePixelRatioF()), 2.0)
        for btn, direction in ((self._left_btn, "left"),
                               (self._right_btn, "right")):
            icon = QIcon()
            for mode in (QIcon.Mode.Normal, QIcon.Mode.Active,
                         QIcon.Mode.Selected):
                icon.addPixmap(_triangle(direction, live, dpr), mode)
            icon.addPixmap(_triangle(direction, dead, dpr),
                           QIcon.Mode.Disabled)
            btn.setIcon(icon)
        self._arrow_ink = (live.name(), dead.name())

    def changeEvent(self, ev) -> None:  # noqa: N802
        super().changeEvent(ev)
        if ev.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange) \
                and hasattr(self, "_right_btn"):
            self._paint_arrows()

    # ---- Qt's hooks --------------------------------------------------------
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Not the width of every tab: the window may be narrower than that,
        which is what the arrows are for."""
        full = super().sizeHint()
        return QSize(min(full.width(), 2 * self._arrow_width() + 120),
                     full.height())

    def tabLayoutChange(self) -> None:  # noqa: N802
        super().tabLayoutChange()
        self._relayout()

    def resizeEvent(self, ev) -> None:  # noqa: N802
        super().resizeEvent(ev)
        self.ensure_shown(self.currentIndex())

    def showEvent(self, ev) -> None:  # noqa: N802
        super().showEvent(ev)
        self._relayout()

    def tab_at(self, pos: QPoint) -> int:
        """The tab under *pos*, counting only the part that is drawn."""
        plan = self._plan()
        if not plan["clip"].contains(pos):
            return -1
        for i, r in plan["rects"].items():
            if r.contains(pos):
                return i
        return -1

    def paintEvent(self, _ev) -> None:  # noqa: N802
        plan = self._plan()
        p = QStylePainter(self)
        p.setClipRect(plan["clip"])
        cur = self.currentIndex()
        # the selected tab last, so its raised frame is on top
        order = [i for i in plan["rects"] if i != cur] + (
            [cur] if cur in plan["rects"] else [])
        for i in order:
            r = plan["rects"][i]
            if not r.intersects(plan["clip"]):
                continue
            opt = QStyleOptionTab()
            self.initStyleOption(opt, i)
            # DRAWN AT QT'S OWN PLACE FOR THE TAB, MOVED BY THE PAINTER: the
            # style sheet style places a tab's LABEL from the bar's own
            # layout, not from the option, so a label drawn with a moved
            # option landed where the tab would be unscrolled and was clipped
            # away (photographed on screen: blank tabs once scrolled).
            own = self.tabRect(i)
            p.save()
            p.translate(r.left() - own.left(), 0)
            opt.rect = own
            if i == self._hover:
                opt.state |= QStyle.StateFlag.State_MouseOver
            else:
                opt.state &= ~QStyle.StateFlag.State_MouseOver
            # SHAPE, THEN LABEL: under the app's style sheet CE_TabBarTab
            # draws the shape alone, and the first cut painted blank tabs
            # (photographed on screen). Drawn apart, as QTabBar does.
            p.drawControl(QStyle.ControlElement.CE_TabBarTabShape, opt)
            p.drawControl(QStyle.ControlElement.CE_TabBarTabLabel, opt)
            p.restore()
        p.end()

    def mousePressEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        if ev.button() != Qt.MouseButton.LeftButton:
            ev.ignore()
            return
        i = self.tab_at(ev.position().toPoint())
        if i >= 0 and self.isTabEnabled(i):
            self.setCurrentIndex(i)
            # a partly shown tab that was already current still comes whole
            self.ensure_shown(i)
        ev.accept()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        ev.accept()

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:  # noqa: N802
        i = self.tab_at(ev.position().toPoint())
        if i != self._hover:
            self._hover = i
            self.update()
        ev.accept()

    def leaveEvent(self, ev) -> None:  # noqa: N802
        self._hover = -1
        self.update()
        super().leaveEvent(ev)

    def wheelEvent(self, ev) -> None:  # noqa: N802
        d = ev.angleDelta()
        step = d.y() or d.x()
        if step > 0:
            self.scroll_left()
        elif step < 0:
            self.scroll_right()
        ev.accept()

    def event(self, ev) -> bool:  # noqa: D401
        from PyQt6.QtCore import QEvent
        if ev.type() == QEvent.Type.ToolTip:
            from PyQt6.QtWidgets import QToolTip
            i = self.tab_at(ev.pos())
            tip = self.tabToolTip(i) if i >= 0 else ""
            if tip:
                QToolTip.showText(ev.globalPos(), tip, self)
            else:
                QToolTip.hideText()
                ev.ignore()
            return True
        return super().event(ev)

    # ---- for a test and a driver ------------------------------------------
    def peek_state(self) -> dict:
        """What is shown, in the bar's own pixels: the drawn part of each
        visible tab, the clip, and the arrows' states."""
        plan = self._plan()
        clip = plan["clip"]
        shown = {}
        for i, r in plan["rects"].items():
            part = r.intersected(clip)
            shown[i] = (part.width() / r.width()) if r.width() else 0.0
        return {"clip": (clip.left(), clip.right()),
                "shown": shown, "first": plan["first"],
                "last": plan["last"], "visible": plan["visible"],
                "rects": {i: (r.left(), r.right())
                          for i, r in plan["rects"].items()},
                "arrows": (self._left_btn.isVisible()
                           and self._left_btn.isEnabled(),
                           self._right_btn.isVisible()
                           and self._right_btn.isEnabled()),
                "arrows_shown": self._left_btn.isVisible(),
                "arrow_rects": (self._left_btn.geometry().getRect(),
                                self._right_btn.geometry().getRect()),
                "arrow_ink": getattr(self, "_arrow_ink", None),
                "area": self._area()}
