"""Shared widget factory helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QEvent, QModelIndex, QObject, QPointF, QRect, QRectF, QSize, QSortFilterProxyModel, Qt, QUrl
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QTextCursor

from core.i18n import tr
from core.name_order import name_sort_key
from core.logger import get_logger
import weakref

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyleOptionFrame,
    QLayout,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


#: Chrome (frame + padding) kept around a label when the button is asked for its
#: MINIMUM width. The style's own figure — around 87 px with this stylesheet — is
#: what the button would like; this is what it needs to stay legible and framed
#: when a row is short of room. Below the first value a label starts to touch the
#: frame; the second is the absolute floor, which also covers a native alert
#: whose bezel is not the one the style described (Knut's sixth clipping report).
#: Kept as the floor a caller may rely on; the margin itself is _COMFORTABLE_CHROME.
_COMFORTABLE_CHROME = 40
_MIN_CHROME = 24

#: Marks the ``min-width`` rule this module adds, so a re-fit REPLACES its own
#: previous rule instead of appending another one after it.
#: The application stylesheet's own ``QPushButton { min-width }`` (ui/styles.py).
#: A fitted rule may raise a button above it, never drop it below.
_APP_MIN_BUTTON_WIDTH = 72

_FITTED_WIDTH_MARK = "/* chromiq-fitted-width */"

#: Where the last minimum this module set is remembered, so a re-fit can
#: replace its own number instead of treating it as somebody's decision.
_FITTED_MIN_PROP = "chromiq_fitted_min"


def _without_fitted_width(sheet: str) -> str:
    """*sheet* with any rule this module previously added removed."""
    if _FITTED_WIDTH_MARK not in sheet:
        return sheet
    kept, skip = [], False
    for line in sheet.splitlines():
        if line.strip() == _FITTED_WIDTH_MARK:
            skip = True
            continue
        if skip:
            skip = False          # the single rule line that follows the mark
            continue
        kept.append(line)
    return "\n".join(kept)


def _min_width_from(sheet: str) -> int:
    """The minimum width *sheet* itself declares, or 0 when it declares none.

    **Only the sheet.** Asking the widget would return the value of the rule we
    are about to replace — and asking ``minimumWidth()`` returns the number
    ``setMinimumWidth`` was just given, so the rule would never be written at
    all. That mistake cost three green tests: a stylesheet's ``min-width`` is
    what decides ``minimumSizeHint``, and without it a button falls back to the
    app-wide 72 px and clips its label again.
    """
    import re
    widths = [int(m) for m in re.findall(r"min-width:\s*(\d+)px", sheet)]
    return max(widths) if widths else 0


def _may_be_painted_by_the_platform(btn) -> bool:
    """Whether *btn* might be drawn in the SYSTEM font rather than the app's.

    Knut's sixth clipping report was a **native macOS alert**: it takes neither
    the application stylesheet nor the font every width had been computed from,
    so "DELETE RUN 4 PERMANENTLY" was a quarter of a letter short at each end.
    Being wide enough for either font is the fix — for those windows.

    For a button on a tab page it is not a fix, it is 38 px of dead width apiece
    (Sebastian, #130 2026-07-29). The application stylesheet reaches those, so
    Menlo is not a guess. A message box is the case that escapes it.
    """
    try:
        if btn.parentWidget() is None:
            # Not placed yet, so there is nothing to read. A button built loose
            # is usually on its way into a dialog — take the wider answer.
            return True
        win = btn.window()
        if isinstance(win, QMessageBox):
            return True
        # A QMessageBox built by another module may not be this class, but it
        # always carries the standard button box and no layout of our own.
        return win is not None and win.metaObject().className() in (
            "QMessageBox", "QErrorMessage", "QInputDialog")
    except Exception:      # noqa: BLE001 — sizing must never raise
        return True        # when in doubt, be the wider of the two


def fit_button_width(btn) -> None:
    """Make sure *btn* is wide enough for the label it will actually paint.

    **The one place button widths are decided** (Knut, #130 2026-07-26). A
    button works out its own width from the font it has at the time — but
    :class:`ButtonFontFilter` then swaps every button to Menlo in capitals,
    which is wider. The button keeps its old width and paints the new, longer
    label into it, so the text is clipped at both ends. That is why pop-up
    buttons could come up with "…EPLACE THE STORED CHAR…".

    Widening is one-way: a button may grow to fit its text, never shrink below
    a width somebody set deliberately.
    """
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QStyle, QStyleOptionButton

    text = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    if not text:
        return
    # A width the code fixed deliberately is not ours to argue with. The "✕"
    # that clears the gamut comparison is `setFixedWidth(28)` so it matches the
    # browse button beside it — and the app-standard floor introduced for the
    # opposite problem promptly blew it up to 82 px (Sebastian, #130
    # 2026-07-29: *"I think this one is now too wide. It should have the same
    # width as the browse button with the folder icon that is right next to it
    # on its left."*). setFixedWidth is the clearest statement of intent there
    # is; nothing computed here outranks it.
    _QT_MAX = 16777215          # QWIDGETSIZE_MAX — "no maximum set"
    if 0 < btn.maximumWidth() < _QT_MAX:
        return
    font = btn.font()
    if font.capitalization() == QFont.Capitalization.AllUppercase:
        # QFontMetrics measures the characters given, not the capitalisation the
        # painter will apply — so measure what will really be drawn.
        text = text.upper()
    # Measure against the WIDEST font this label could be painted in, not only
    # the one the widget currently has.
    #
    # Knut's sixth clipping report (#130, 2026-07-28) came with a screenshot,
    # and the screenshot settled it: the button was a **native macOS alert
    # button**, painted in the system font — not the Menlo the application
    # stylesheet asks for. A native alert does not take the app's QSS, so every
    # width computed from Menlo metrics was a width for a font that was never
    # used. Sometimes it was enough; on "DELETE RUN 4 PERMANENTLY" it was a
    # quarter of a letter short at each end, which is exactly what he saw.
    #
    # …but ONLY where the platform really might choose it (Sebastian, #130
    # 2026-07-29). The allowance was being applied to every button in the
    # application, and the system font is around 38 px wider than Menlo on a
    # label of this length — so four buttons in the Print Chart row asked for
    # 648 px inside a panel fixed at 580, and could not be made to fit however
    # the minimum was computed. A button inside the main window is painted by
    # the application stylesheet; Menlo is not a guess there, it is a fact. It
    # is the ALERT that escapes the stylesheet, so that is where the allowance
    # belongs.
    fm = QFontMetrics(font)
    if _may_be_painted_by_the_platform(btn):
        try:
            from PyQt6.QtGui import QFontDatabase
            base = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
            # At ITS OWN size as well as ours. A native alert does not merely
            # swap the family — it paints in the system font at the system size,
            # which on macOS is larger than the 9 pt the application uses. The
            # fitter used to shrink the system font to the widget's size before
            # measuring, which is the one thing guaranteed to under-report the
            # very case it exists for.
            candidates = [base]
            sized = QFont(base)
            if font.pixelSize() > 0:
                sized.setPixelSize(font.pixelSize())
            elif font.pointSizeF() > 0:
                sized.setPointSizeF(font.pointSizeF())
            sized.setBold(font.bold())
            candidates.append(sized)
            for cand in candidates:
                cm = QFontMetrics(cand)
                if fm.horizontalAdvance("M" * 8) < cm.horizontalAdvance("M" * 8):
                    fm = cm
        except Exception:      # noqa: BLE001 — sizing must never raise
            pass
    # A label written over two lines is drawn as two lines, so what it needs is
    # the WIDEST line — not both of them laid end to end. Measuring the whole
    # string made "Print\nCurrent Page" ask for the width of "PrintCurrent
    # Page", which forced the Print Chart buttons far wider than they should be
    # and threw their text out of alignment (Knut, #131 2026-07-28).
    needed = max(fm.horizontalAdvance(line) for line in text.split("\n"))
    try:
        opt = QStyleOptionButton()
        opt.initFrom(btn)
        opt.text = max(text.split("\n"), key=len)
        want = btn.style().sizeFromContents(
            QStyle.ContentsType.CT_PushButton, opt,
            QSize(needed, fm.height()), btn).width()
    except Exception:      # noqa: BLE001 — sizing must never raise
        want = 0
    # ---- what the button MUST have, versus what it would LIKE ---------------
    #
    # These are two different numbers, and conflating them is what made the
    # buttons collide. Sebastian, #130 2026-07-29: *"the buttons in the print
    # chart tab are overlapping and wider than they would have to be for the
    # text they contain … the same seems true for the measure tab's 'start
    # measurement' button."* Both were true, and measurable: Print Chart
    # overlapped in three places by up to 47 px and Measure by 6 px, at every
    # window size.
    #
    # The cause was not the layout. The style asks for ~87 px of chrome around
    # the text, and four such buttons want 675 px in a panel that is 580 px
    # wide. Because the MINIMUM was set to that full decorative width, the row
    # could not compress — and a QHBoxLayout given less room than the sum of its
    # minimums lets its items overlap rather than shrink below them.
    #
    # So the minimum is now what the label genuinely needs — the widest line, in
    # the widest font it might be painted in, plus enough chrome to draw the
    # frame comfortably — while the style's roomier figure stays the *preferred*
    # width. A wide panel therefore looks exactly as before; a cramped one
    # tightens the buttons instead of stacking them on top of each other, and
    # the text still fits, which is the invariant the whole clipping saga was
    # about.
    # A FIXED margin, deliberately, not the style's own figure. Deriving it from
    # ``sizeFromContents`` made the answer depend on the ``min-width`` rule this
    # function had written the *previous* time it ran, so a button grew on its
    # second fit — 151 px, then 167 px, then stable. My own new test caught it.
    # A constant is stable by construction, and the style's roomier idea is
    # still what the layout uses when there is space, because that comes from
    # the size hint rather than from here.
    want = needed + _COMFORTABLE_CHROME
    icon = btn.icon()
    if icon is not None and not icon.isNull():
        want += btn.iconSize().width() + 6
    # Widening stays one-way for a width SOMEBODY ELSE set — but not for our
    # own. This runs again on every Show and StyleChange, and the font can
    # change between those: the Print Chart buttons ended up carrying a minimum
    # measured in Menlo while the application had since restyled them to Inter,
    # which is narrower. 38 px of the width each of them was holding belonged to
    # a font they no longer used, and four of them then would not fit their
    # panel (Sebastian, #130 2026-07-29). So a value this function set is
    # replaced by the current measurement, up or down; anything else is only
    # ever grown.
    fitted_before = btn.property(_FITTED_MIN_PROP)
    if fitted_before is not None and int(fitted_before) == btn.minimumWidth():
        btn.setMinimumWidth(want)
    elif btn.minimumWidth() < want:
        btn.setMinimumWidth(want)
    btn.setProperty(_FITTED_MIN_PROP, btn.minimumWidth())
    # …and let the button actually USE that minimum when its row is short of
    # room. A QPushButton's default horizontal policy is ``Minimum``, which
    # means "my size hint is the least I will accept": the layout may grow it
    # but never shrink it, so a fitted minimum is decoration and the row
    # overflows regardless. That is why Print Chart still overlapped after the
    # minimum had been brought down — the four buttons' HINTS came to 657 px in
    # a 580 px panel and none of them would give way.
    #
    # ``Preferred`` keeps the same hint — a roomy panel looks exactly as it did
    # — while allowing the layout to compress towards the minimum computed
    # above, which is the width the label genuinely needs.
    try:
        policy = btn.sizePolicy()
        if policy.horizontalPolicy() == QSizePolicy.Policy.Minimum:
            policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
            btn.setSizePolicy(policy)
    except Exception:      # noqa: BLE001 — sizing must never raise
        pass
    # A stylesheet's own ``min-width`` decides the button's minimum size hint,
    # and it beats setMinimumWidth — which is why the app-wide 72 px rule kept
    # winning and pop-up buttons were still clipped after all of the above
    # (Knut, #131 2026-07-27: "I thought you made a global rule … why did it
    # now happen?"). Answering in the same language is what actually sticks.
    #
    # REPLACED, never appended: this runs again on every Show and StyleChange,
    # and appending left buttons carrying a stack of stale rules ("min-width:
    # 145px" followed by "min-width: 149px"), with the last one winning by
    # accident of order.
    #
    # And the rule carries the TEXT width, not the width computed above. A
    # stylesheet ``min-width`` is the minimum of the CONTENT box: Qt adds the
    # padding and the border on top of it. Writing the already-padded number
    # there counted the stylesheet's ``padding: 6px 18px`` twice, so a button
    # asking for 140 px ended up with a 178 px minimum — 38 px of thin air
    # apiece, which is precisely what stopped the Print Chart row fitting its
    # 580 px panel however the rest of the arithmetic was adjusted (Sebastian,
    # #130 2026-07-29).
    try:
        sheet = _without_fitted_width(btn.styleSheet() or "")
        # +2: the metrics used here and the ones the painter finally uses can
        # round apart by a pixel, and a label a pixel short is a clipped label.
        #
        # …and never BELOW the application's own standard button width. A rule
        # written here beats the app stylesheet in both directions, and on a
        # short label — the "✕" that closes the gamut view — it was quietly
        # shrinking a 72 px button to 10 px worth of content box. This function
        # exists to stop labels being clipped, not to make small buttons harder
        # to hit.
        declared = max(int(needed) + 2, _APP_MIN_BUTTON_WIDTH)
        if declared > _min_width_from(sheet):
            sheet = (f"{sheet}\n{_FITTED_WIDTH_MARK}\n"
                     f"QPushButton {{ min-width: {declared}px; }}")
        btn.setStyleSheet(sheet)
    except Exception:      # noqa: BLE001 — sizing must never raise
        pass


class ButtonFontFilter(QObject):
    """Applies Menlo + AllUppercase to every QPushButton as it is polished, and
    keeps it wide enough for the label that font produces."""

    #: Guards against the re-entry that a style change inside fit() would cause.
    _fitting: bool = False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if ButtonFontFilter._fitting:
            return False
        kinds = (QEvent.Type.Polish, QEvent.Type.Show, QEvent.Type.StyleChange)
        if isinstance(obj, QPushButton) and event.type() in kinds:
            # Polish is when the font is swapped; Show and StyleChange are when
            # something ELSE may have restyled the button since — and a button
            # that has lost its width rule clips its label (Knut, #131, three
            # times). Re-fitting is idempotent: it only ever widens.
            ButtonFontFilter._fitting = True
            try:
                self.fit(obj)
            finally:
                ButtonFontFilter._fitting = False
        elif (event.type() in kinds and isinstance(obj, QWidget)
              and obj.isWindow()):
            # …and once for the WINDOW as a whole (Knut, #130 2026-07-28, after
            # a fifth clipping report: "the rules should prevent it for any and
            # all windows").
            #
            # Fitting each button on its own is not enough when the buttons sit
            # in a QDialogButtonBox: the box gives them ONE uniform width, taken
            # before the font swap widens them, and nothing asks it to measure
            # again. So the button knows how wide it should be and the box never
            # hears about it. Doing it here — every button in the window, then
            # re-activating every layout from the innermost outwards — is what
            # makes the rule hold without each dialog having to opt in.
            ButtonFontFilter._fitting = True
            try:
                self.fit_window(obj)
            finally:
                ButtonFontFilter._fitting = False
        return False

    @staticmethod
    def fit_window(win) -> None:
        """Fit every button in *win*, then let its layouts re-measure."""
        try:
            buttons = win.findChildren(QPushButton)
            if not buttons:
                return
            for btn in buttons:
                ButtonFontFilter.fit(btn)
            # Innermost outwards, so a button box re-measures before the dialog
            # it sits in is asked for its own size.
            seen = set()
            for btn in buttons:
                parent = btn.parentWidget()
                while parent is not None and id(parent) not in seen:
                    seen.add(id(parent))
                    lay = parent.layout()
                    if lay is not None:
                        lay.invalidate()
                        lay.activate()
                    if parent is win:
                        break
                    parent = parent.parentWidget()
        except Exception:      # noqa: BLE001 — sizing must never raise
            pass

    @staticmethod
    def fit(btn) -> None:
        """Give *btn* the app's button font, then the width that font needs."""
        font = btn.font()
        font.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        btn.setFont(font)
        before = btn.minimumWidth()
        fit_button_width(btn)
        if btn.minimumWidth() != before:
            ButtonFontFilter.relayout_around(btn)

    @staticmethod
    def relayout_around(btn) -> None:
        """Let the layouts holding *btn* place it again, now that it is wider.

        **Widening a button that a layout has already placed does not move its
        neighbours.** The row keeps the positions it computed from the narrower
        widths and every button simply grows to the right, over the top of the
        one beside it. Sebastian, #130 2026-07-29: *"the buttons in the print
        chart tab are overlapping … the same seems true for the measure tab's
        'start measurement' button. Its right side seems to be below the stop
        button."* He was reading it exactly right — Print Chart overlapped in
        three places and Measure in one, at every window size.

        ``fit_window`` already did this, but only for objects that answer True
        to ``isWindow()``. A button on a tab page is not in a window that is
        being polished, so nothing ever asked its row to measure again. Doing it
        from the button itself covers both.

        Innermost outwards, so a row settles before the panel holding it is
        asked for its own size.
        """
        try:
            parent = btn.parentWidget()
            depth = 0
            while parent is not None and depth < 8:
                lay = parent.layout()
                if lay is not None:
                    lay.invalidate()
                    lay.activate()
                if parent.isWindow():
                    break
                parent = parent.parentWidget()
                depth += 1
        except Exception:      # noqa: BLE001 — sizing must never raise
            pass


#: How many lines of its own text every log panel in the app shows, unless the
#: user has dragged one to a different size. Knut, beta.120: *"only 6 lines of
#: text are visible, but showing 9 is better."*
LOG_VISIBLE_LINES = 9

#: How far a log may be dragged. Two lines is the smallest that still shows a
#: message and the one after it, so you can see something arrive — Basti asked
#: for one line less than the old floor of three. Forty is about as tall as a
#: log can get before it is the tab.
LOG_MIN_LINES = 2
LOG_MAX_LINES = 40

#: Every live log panel, so dragging one resizes them all — Basti: *"resizing
#: them on one tab should resize them on all"*. A weak set, so a log belonging
#: to a closed window is collected instead of being kept alive by this.
_LIVE_LOGS: "weakref.WeakSet" = weakref.WeakSet()

#: Set once, by the main window, so the helpers can read and write the user's
#: chosen size without every call site having to pass it down.
#: Named `_log`, not `log`: several functions here take a QPlainTextEdit
#: called `log` (`fit_log_height(log, …)`, `_max_lines_for(log)`), so a
#: module global of that name would be shadowed by a WIDGET inside them.
_log = get_logger(__name__)

_LOG_SETTINGS = None

#: The size currently ON SCREEN, which is not always the saved one: during a
#: drag the panels follow the mouse while the setting still holds the size the
#: drag started from. Without this, each mouse-move measured its delta against
#: the old value and the release saved that old value back — so a drag applied
#: itself and was then thrown away.
_LIVE_LINES: "int | None" = None


def refresh_log_panes_from_settings() -> None:
    """Re-read the saved size and apply it to every panel.

    Called after Restore Factory Defaults: the panels are showing a size the
    user chose, and the setting behind it has just been reset, so without this
    the reset would change the stored value and leave the screen alone.
    """
    global _LIVE_LINES
    _LIVE_LINES = None
    _apply_lines(log_visible_lines(), remember=False)


def bind_log_settings(settings) -> None:
    """Give the log helpers somewhere to remember the user's chosen size."""
    global _LOG_SETTINGS, _LIVE_LINES
    _LOG_SETTINGS = settings
    _LIVE_LINES = None          # re-read from whatever was just bound


def log_visible_lines() -> int:
    """The line count every log panel should use right now."""
    if _LIVE_LINES is not None:
        return _LIVE_LINES
    if _LOG_SETTINGS is None:
        return LOG_VISIBLE_LINES
    try:
        n = int(_LOG_SETTINGS.get("log_visible_lines", LOG_VISIBLE_LINES))
    except (TypeError, ValueError):
        return LOG_VISIBLE_LINES
    except RuntimeError:
        # "wrapped C/C++ object of type QSettings has been deleted". Reading a
        # preference must never take the window down, whatever happened to the
        # store underneath it — and a log line's height is the least important
        # thing in the app to be right about.
        _log.debug("the settings store went away while reading "
                   "log_visible_lines", exc_info=True)
        return LOG_VISIBLE_LINES
    return max(LOG_MIN_LINES, min(LOG_MAX_LINES, n))


def _max_lines_for(log) -> int:
    """The tallest this panel can be and still fit the space it lives in.

    Basti, beta.141: *"when I expand the log output field to maximum then at
    the bottom of it the border to the frame of the app's main window is gone
    and it looks strange."* Measured, it began long before the maximum — at 20
    lines the panel's bottom was already below the window, so it was being
    clipped and the margin under it went with it. There is no scroll area under
    a tab, so nothing was going to bring that back into view.

    The panel shares a column with the tab's header, its panels and the status
    line below it. Everything else in that column has a minimum height, and the
    sum of those minimums does not change when the panel is resized — so the
    room left for the panel is simply the column's height minus that sum. That
    makes the ceiling a property of the layout and the window's height, not of
    the panel's current size: shrinking and growing again lands back where it
    started, and making the window taller hands the space back.

    **Called only from :func:`_apply_lines` and :func:`refit_log_panes`, never
    from :func:`fit_log_height`.** That one also runs at polish and on every
    style change, when a tab's column can be a fraction of its final height for
    a pass — capping there read the transient geometry and pinned the Measure
    tab's log at six lines for the rest of the session, which is precisely the
    complaint the nine-line default exists to answer (Knut, beta.125: *"The log
    window at the bottom left still has only space for 6 lines of text"*). Tabs
    settle instead when they are first shown, through the tab-change re-fit.
    """
    try:
        pane = log.parentWidget()
        # The log sits inside the "log_container" wrapper (add_log_row), which
        # is exactly as tall as the log itself — measuring THAT as the column
        # made the ceiling equal the current size, so the panel could shrink
        # but never grow again (Sebastian, 2026-08-11: "i can't change its
        # size anymore, it stays small"). The column is the wrapper's parent.
        if pane is not None and pane.objectName() == "log_container":
            pane = pane.parentWidget()
        lay = pane.layout() if pane is not None else None
        # Only a panel that is actually on screen can be measured: a stacked
        # page that has never been shown reports a column height from before it
        # was laid out, and trusting it once collapsed every log to two lines.
        if lay is None or not log.isVisible() or pane.height() <= 0:
            return LOG_MAX_LINES
        # minimumSize() carries nested layouts too, so it does not matter how
        # deeply the panel is nested — only that it is somewhere in this column.
        others = lay.minimumSize().height() - log.minimumHeight()
        room = pane.height() - others
        fm = log.fontMetrics()
        extra = int(log.document().documentMargin()) * 2 + log.frameWidth() * 2
        fits = (room - extra) // max(1, fm.lineSpacing())
        return max(LOG_MIN_LINES, min(LOG_MAX_LINES, int(fits)))
    except (RuntimeError, AttributeError, TypeError):
        return LOG_MAX_LINES        # a ceiling must never break a resize


def _fit_capped(log, n: int) -> None:
    """Size one panel to *n* lines, or to as many as its own column can show."""
    try:
        fit_log_height(log, max(LOG_MIN_LINES, min(int(n), _max_lines_for(log))))
    except RuntimeError:                   # its C++ side is already gone
        pass


def _apply_lines(n: int, *, remember: bool) -> int:
    """Give every panel *n* lines, each capped by what its own column can show.

    *remember* is the difference between the user **choosing** a size and the
    app **re-fitting** one, and only a choice may change the shared value. A
    re-fit runs on every window resize and every tab change; if it wrote back
    what it had computed, one moment when some panel happened to be small would
    become the size of every panel from then on. That is not hypothetical — the
    release gate showed Create Chart's log at three lines in a run where the
    file that tests it passes on its own.
    """
    global _LIVE_LINES, _APPLYING
    if _APPLYING:               # see _APPLYING
        return n
    _APPLYING = True
    try:
        # The tab on screen sets how far the drag can go — it is the one the
        # user is watching, and the only one whose column can be measured.
        for widget in list(_LIVE_LOGS):
            try:
                if widget.isVisible():
                    n = min(n, _max_lines_for(widget))
            except RuntimeError:
                pass
        n = max(LOG_MIN_LINES, n)
        if remember:
            _LIVE_LINES = n
        # Tabs have different amounts of room — Measure gives its preview more
        # and its log less. So every panel follows the one chosen size but
        # stops at its own ceiling, and none of them is ever clipped. Tabs that
        # are hidden settle when they are shown; see refit_log_panes().
        for widget in list(_LIVE_LOGS):
            _fit_capped(widget, n)
        return n
    finally:
        _APPLYING = False


#: Set while a resize is being applied. Growing the panels can grow the
#: window's own minimum, which makes Qt resize the window, whose resizeEvent
#: asks for a refit — landing a second run inside the first, each shrinking the
#: other's result. Left unguarded, every request collapsed to the two-line floor.
_APPLYING = False


def refit_log_panes() -> None:
    """Re-apply the user's saved size within what the window can show now.

    Called when the main window is resized: making it taller should give back
    the size that was asked for, and making it shorter must not push the panel
    through the bottom of the frame.
    """
    if _APPLYING:
        return
    _apply_lines(log_visible_lines(), remember=False)


def set_log_visible_lines(n: int, *, save: bool = True) -> int:
    """Resize every log panel in the app at once, and remember the size.

    ``save=False`` is the middle of a drag: the panels move, but the setting is
    left alone until the mouse is released.

    Returns the value actually used, after clamping — the caller may want to
    show it, and a silently ignored request would read as a stuck drag.
    """
    n = _apply_lines(max(LOG_MIN_LINES, min(LOG_MAX_LINES, int(n))),
                     remember=True)
    # Save what was APPLIED, never what was asked for: a size the window could
    # not show is not a size the user chose, and storing it would make the
    # panel jump the next time the app opened on a taller screen.
    if save and _LOG_SETTINGS is not None:
        _LOG_SETTINGS.set("log_visible_lines", n)
    return n


#: The gap above a log panel, in pixels, and how much of it survives the log
#: being hidden. Both halves are needed: see ``add_log_row``.
LOG_GAP_TOTAL = 5
LOG_GAP_KEPT = 3


def add_log_row(layout, log, parent=None):
    """Append *log* to *layout* with the standard gap above it. Returns the wrapper.

    Every tab ends on the same line — **13 px above the window edge** — and has
    to go on doing so with Preferences → "Hide the log panel on every tab" in
    either position. That is harder than it sounds, because the gap above the
    log has to behave differently in the two states:

    * with the log **shown**, the whole 5 px sits between the buttons and the
      log, and the log's own bottom margin ends the tab;
    * with the log **hidden**, the buttons become the bottom-most thing, and
      they need *less* space below them than the log did — otherwise they hang
      lower than the log ever did.

    So the gap is split. ``LOG_GAP_KEPT`` (3 px) is a plain spacer that stays
    whatever happens. The remaining 2 px is the top margin of a wrapper named
    ``"log_container"``, which ``MainWindow._apply_log_visibility`` hides along
    with the log — so it goes when the log goes. With the log on the two halves
    add back up to 5 and nothing looks different from before.

    Measured, not derived: these buttons ask for ``setFixedHeight(36)`` and
    render at 42, because the application stylesheet's ``min-height`` still
    wins, and the 6 px overflow eats into the margin below them by a different
    amount in each layout. A gap read off the source is not the gap on screen.

    **The wrapper takes no stretch**, and neither should any caller add one:
    :func:`fit_log_height` pins the log's height (``min == max``, and the resize
    grip rewrites both), so a stretch cannot go into the log — the wrapper grows
    instead and leaves the log floating clear of the bottom edge.
    """
    layout.addSpacing(LOG_GAP_KEPT)
    wrapper = QWidget(parent if parent is not None else log.parentWidget())
    wrapper.setObjectName("log_container")
    inner = QVBoxLayout(wrapper)
    inner.setContentsMargins(0, LOG_GAP_TOTAL - LOG_GAP_KEPT, 0, 0)
    inner.setSpacing(0)
    inner.addWidget(log)
    layout.addWidget(wrapper)
    return wrapper


def fit_log_height(log, lines: "int | None" = None) -> None:
    """Size a log panel to exactly *lines* lines of the font it really has.

    A pixel number cannot promise a line count: the log's family and size come
    from the stylesheet, and a stylesheet reaches a widget only at polish — so a
    height set in ``__init__`` is measured against the wrong font. The tabs used
    to hard-code 67 px, which was about six lines and stayed six lines after the
    fix that was supposed to make it nine (Knut, beta.125: *"The log window at
    the bottom left still has only space for 6 lines of text"* — he was on
    Create Chart, and only the Measure tab had been changed).

    Call it once after polish and again on every style change. Never raises:
    a log that cannot be measured keeps whatever height it has.

    With *lines* left as None the user's own size is used, so every panel in
    the app follows one setting and dragging any of them moves them all. The
    log also registers itself here, which is why no call site had to change.
    """
    try:
        if lines is None:
            # Inside the try: it reads the settings store, which can be gone
            # (see `log_visible_lines`), and this function promises never to
            # raise into a caller that is only sizing a panel.
            lines = log_visible_lines()
    except Exception:      # noqa: BLE001
        lines = LOG_VISIBLE_LINES
    try:
        _LIVE_LOGS.add(log)
        LogResizeGrip.install(log)
    except (TypeError, RuntimeError):      # not a weak-referenceable widget
        pass
    try:
        fm = log.fontMetrics()
        doc_margin = int(log.document().documentMargin()) * 2
        frame = log.frameWidth() * 2
        h = fm.lineSpacing() * lines + doc_margin + frame
        log.setMinimumHeight(h)
        log.setMaximumHeight(h)
    except Exception:      # noqa: BLE001 — sizing must never raise
        pass


class LogResizeGrip(QObject):
    """Lets a log panel be resized by dragging its top edge.

    Basti: *"the fields for log output became pretty big now. would it be
    possible to make them resizeable by the user (clicking and dragging) and
    the app should remember the size? … resizing them on one tab should resize
    them on all."*

    Implemented as an event filter rather than a handle widget on purpose. The
    five log panels sit in five differently-built layouts, and adding a widget
    above each one would mean touching all of them — the change with the most
    ways to go quietly wrong. Filtering the log's own events adds nothing to
    any layout and behaves identically everywhere.

    What the user sees: the cursor becomes a vertical resize arrow near the top
    edge of the log, and dragging there makes every log panel in the app taller
    or shorter together. The size is remembered, and Restore Factory Defaults
    puts it back to nine lines.
    """

    #: How close to the top edge counts as "on the handle", in pixels.
    GRAB_BAND = 6

    _INSTALLED = "_cq_log_grip"

    @classmethod
    def install(cls, log) -> None:
        """Attach one grip to *log*, once."""
        if getattr(log, cls._INSTALLED, None) is not None:
            return
        grip = cls(log)
        setattr(log, cls._INSTALLED, grip)
        log.installEventFilter(grip)
        log.setMouseTracking(True)
        if log.viewport() is not None:
            log.viewport().installEventFilter(grip)
            log.viewport().setMouseTracking(True)
        # Never over-write a tooltip a tab set for its own reasons — say this
        # only where there is nothing else to say.
        if log.toolTip():
            return
        log.setToolTip(tr(
            "Drag the top edge of this panel to make it taller or shorter. "
            "Every log panel in ChromIQ changes with it, the size is "
            "remembered, and “Restore Factory Defaults” in Preferences puts it "
            "back to nine lines."))

    def __init__(self, log) -> None:
        super().__init__(log)
        self._log = log
        self._dragging = False
        self._press_y = 0
        self._press_lines = LOG_VISIBLE_LINES
        #: The size this drag is currently showing, so releasing keeps it.
        self._live = LOG_VISIBLE_LINES

    @staticmethod
    def _global_y(event) -> int:
        """The pointer's y on the screen, which a resize cannot move."""
        try:
            return int(event.globalPosition().y())
        except AttributeError:             # a synthesised event in a test
            return int(event.position().y())

    def _on_handle(self, pos_y: int) -> bool:
        return 0 <= pos_y <= self.GRAB_BAND

    def eventFilter(self, obj, event) -> bool:      # noqa: N802 (Qt naming)
        try:
            etype = event.type()
            if etype == QEvent.Type.MouseMove:
                if self._dragging:
                    # MEASURED ON THE SCREEN, NOT INSIDE THE WIDGET.
                    #
                    # The panel's top edge moves as it grows, so the same screen
                    # position has a different y inside the log after every
                    # step. Measuring locally fed each resize back into the next
                    # delta and the panel juddered — Basti: *"dragging works but
                    # looks jumpy"*. A global reference cannot move under us.
                    y = self._global_y(event)
                    step = max(1, self._log.fontMetrics().lineSpacing())
                    # Dragging UP (a smaller y) makes the panel taller.
                    delta_lines = int(round((self._press_y - y) / step))
                    self._live = set_log_visible_lines(
                        self._press_lines + delta_lines, save=False)
                    return True
                self._log.viewport().setCursor(
                    Qt.CursorShape.SizeVerCursor
                    if self._on_handle(int(event.position().y()))
                    else Qt.CursorShape.IBeamCursor)
                return False
            if etype == QEvent.Type.MouseButtonPress:
                if (event.button() == Qt.MouseButton.LeftButton
                        and self._on_handle(int(event.position().y()))):
                    self._dragging = True
                    self._press_y = self._global_y(event)
                    self._press_lines = log_visible_lines()
                    self._live = self._press_lines
                    return True
            elif etype == QEvent.Type.MouseButtonRelease and self._dragging:
                self._dragging = False
                # Save the size the DRAG ended on. Reading it back from the
                # setting here is what made a finished drag snap straight back
                # to where it started — the setting still held the old value,
                # because a drag deliberately does not write on every pixel.
                set_log_visible_lines(self._live)
                return True
            elif etype == QEvent.Type.Leave and not self._dragging:
                self._log.viewport().unsetCursor()
        except Exception:      # noqa: BLE001 — a resize must never break a log
            self._dragging = False
        return False


def accent_message_box_button(btn) -> None:
    """Style one message-box button as the app's PRIMARY action button.

    Basti, #164: *"i want the close button to be styled like the generate
    chart button in create chart module (that punchy magenta and white text
    on it)"*.

    It reproduces `QPushButton#primary` as the Create Chart tab paints it
    (``ui/main_window.py`` — the per-tab QSS injector): the tab's own accent
    from ``TAB_COLORS[0]`` (magenta), the same 0.82x hover, and the same
    per-theme label colour — WHITE on light, near-black on dark. The label
    flips because the app flips it; magenta is dark enough for white in light
    mode's surroundings and light enough for near-black in dark mode's.

    A message-box button cannot simply be given ``objectName("primary")``:
    that QSS is injected into the tab pane, and this button lives in a
    top-level dialog that never sees it.
    """
    from core.settings import AppSettings
    from ui import neutral_styles
    from ui.styles import TAB_COLORS
    from ui.theme import (
        APPEARANCE_LIGHT, APPEARANCE_NEUTRAL, accent_for, resolve_mode,
    )

    mode = resolve_mode(AppSettings().get("appearance", "auto"))
    accent = accent_for(TAB_COLORS[0], mode)    # Create Chart's magenta
    r, g, b = (int(accent[i:i + 2], 16) for i in (1, 3, 5))
    if mode == APPEARANCE_NEUTRAL:
        # THE ONE SANCTIONED LIGHT-ON-DARK PAIRING, and it is a FILL: an
        # ON_ACTION label on an ACTION button, 15.53:1. Hover steps sideways
        # rather than 0.82x darker — ACTION has almost no room left below it.
        label = neutral_styles.NM_ON_ACTION
        hover = neutral_styles.NM_TEXT_DIM
    else:
        hover = "#{:02x}{:02x}{:02x}".format(int(r * 0.82), int(g * 0.82),
                                             int(b * 0.82))
        label = "#ffffff" if mode == APPEARANCE_LIGHT else "#0a0a0a"
    btn.setStyleSheet(
        f"QPushButton {{ background: {accent}; color: {label};"
        f" border: 1px solid {accent}; border-radius: 4px;"
        f" padding: 6px 14px; font-weight: 700; }}"
        f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
        f"QPushButton:pressed {{ background: {hover}; }}"
    )


def widen_message_box(box, px: int = 660) -> None:
    """Give a QMessageBox a sensible measure to wrap its text at.

    A QMessageBox sizes itself from its buttons, so a long body is wrapped into
    a tall, narrow column. Basti saw it on the Delete window, 2026-08-28:
    *"it was very high in relation to its width"* — that window had just grown
    several paragraphs (what the run keeps in its "old" folder, the chart copy a
    measurement was taken with, where the files go now) and nothing widened with
    them.

    A full-width spacer row under the text is the standard Qt answer and is
    already used once in `ui/dialogs/settings_dialog.py`; this is that, lifted
    so the delete windows and any future long one share it instead of copying
    it. `px` is a MINIMUM, so a box whose buttons are wider than that is left
    alone.

    Line length matters for reading, not just for looks: much past ~90
    characters the eye loses the start of the next line, and these windows are
    the ones a person must actually read before answering.
    """
    try:
        from PyQt6.QtWidgets import QSizePolicy, QSpacerItem
        grid = box.layout()
        if grid is None:
            return
        grid.addItem(QSpacerItem(int(px), 1, QSizePolicy.Policy.Minimum,
                                 QSizePolicy.Policy.Minimum),
                     grid.rowCount(), 0, 1, grid.columnCount())
    except Exception:      # noqa: BLE001 — a window must still open
        log.debug("could not widen the message box", exc_info=True)


def order_message_box_buttons(box, buttons) -> None:
    """Force a QMessageBox's buttons into the left-to-right order given.

    ⚠ USE THIS SPARINGLY, AND ONLY WHEN THE OWNER HAS ASKED FOR THE ORDER.

    Qt normally lays a message box out to the platform's own rule, and on macOS
    that rule puts the confirming action LAST, on the right — the same as
    Finder, Mail and System Settings, and the same as every OK/Cancel window in
    ChromIQ (measured 2026-08-30, not assumed: four windows, all identical).
    Overriding it makes one window disagree with the platform and with its
    siblings, so it needs a reason better than taste.

    The reason it exists: Basti asked for the dark-reference window to read
    "Calibrate now, Skip this step, Cancel" — three buttons of which two are
    ways of going ahead, where reading order matching the order of the steps
    carries more than the platform rule for a plain yes/no pair does.

    `buttons` is the sequence of QAbstractButtons in the order wanted. Anything
    not listed keeps its place after them. Failing is never fatal: a layout
    tweak must not be able to stop a window opening.
    """
    try:
        from PyQt6.QtWidgets import QDialogButtonBox
        bb = box.findChild(QDialogButtonBox)
        if bb is None or bb.layout() is None:
            return
        lay = bb.layout()
        wanted = [b for b in buttons if b is not None]
        for b in wanted:
            lay.removeWidget(b)
        # Drop the stretches Qt inserted for the layout we are replacing;
        # leaving them behind pushes the buttons apart at random.
        for i in reversed(range(lay.count())):
            if lay.itemAt(i).widget() is None:
                lay.takeAt(i)
        for i, b in enumerate(wanted):
            lay.insertWidget(i, b)
        lay.addStretch(1)
    except Exception:      # noqa: BLE001 — never block a window over a layout
        _log.debug("could not reorder the message box buttons", exc_info=True)


def fit_message_box_buttons(box) -> None:
    """Fit **every** button of a QMessageBox to the label it will paint.

    Knut, #130 2026-07-28, on the Delete windows: *"The button Delete Run 4
    Permanently has its text cut on both sides. Again, all windows created must
    follow the universal rules created to prevent this happening."*

    A button added with ``QMessageBox.addButton`` sizes itself from the font it
    has at that moment; :class:`ButtonFontFilter` then swaps it to Menlo in
    capitals, which is wider, and the label is clipped at both ends. The filter
    re-fits at polish — but **polish does not happen offscreen**, which is
    exactly why a window can look right in a rendered check and clip in the real
    application. Calling this when the window is built removes the dependency on
    when polish happens.

    Use it for every message box that carries a button whose label is longer
    than a word or two.

    It applies :meth:`ButtonFontFilter.fit`, **not** :func:`fit_button_width`:
    the former puts the final font on the button *first* and then measures it.
    Measuring before the swap is the whole bug — it computes a width for the
    narrow font and the wide one is painted into it.
    """
    try:
        buttons = list(box.buttons())
        for btn in buttons:
            ButtonFontFilter.fit(btn)
        # WIDEN THE BOX, NOT JUST THE BUTTONS.
        #
        # Fitting each button sets its minimum width, but a QMessageBox sizes
        # itself from its TEXT — so a row of buttons wider than the message is
        # simply squeezed back below the minimum, and the labels clip again.
        # With two short buttons the text is usually wider anyway and it never
        # showed; three long ones (Basti, 2026-08-08: "JSE AS BASE FOR A NEW
        # PROFILE", the U shaved off) made it obvious.
        lay = box.layout()
        if buttons and lay is not None:
            needed = sum(b.sizeHint().width() for b in buttons)
            needed += 12 * (len(buttons) + 1)      # spacing plus the margins
            # setMinimumWidth does NOT work on a QMessageBox — it sizes from its
            # own grid layout and squeezes straight back. A full-width spacer row
            # is the way to hold it open.
            from PyQt6.QtWidgets import QSizePolicy, QSpacerItem
            lay.addItem(QSpacerItem(needed, 0,
                                    QSizePolicy.Policy.Minimum,
                                    QSizePolicy.Policy.Expanding),
                        lay.rowCount(), 0, 1, lay.columnCount())
        if lay is not None:
            lay.activate()     # let the box re-measure itself around them
    except Exception:      # noqa: BLE001 — sizing must never raise
        pass



def spread_message_box_buttons(box, order=None) -> None:
    """Share the width of a message box evenly between its buttons.

    Qt right-aligns a `QDialogButtonBox`, which reads fine for two buttons and
    badly for four: they bunch into the right-hand half with a wide empty gap
    beside them (Basti, 2026-08-27, on the "project already exists" window).
    This lets every button grow to an equal share of the row, so a four-button
    window reads as four choices rather than one plus three afterthoughts.

    Call it AFTER :func:`fit_message_box_buttons`, which is what makes the box
    wide enough for the labels in the first place; this only decides how the
    width that already exists is divided.

    *order*, when given, is the buttons in the left-to-right order they should
    appear. Qt lays a `QDialogButtonBox` out by ROLE, and on macOS that put
    Cancel second — between the two safe answers and the destructive one, which
    is the worst place for it (Basti: *"i want cancel on the very right"*). It
    is ignored unless it is exactly the box's own buttons: an order missing one
    silently sent that button to the front, and an order naming a widget the box
    does not own re-parented it INTO the box.

    NOTHING IS TOUCHED UNLESS THE RESULT WILL FIT. Equal shares need room for
    the WIDEST label, not the mean one, and long labels in a long language can
    ask for more than the screen has. The first version measured that too late —
    it had already removed Qt's stretches — so on a narrow screen it left the row
    worse than it found it: measured with the Dutch labels, 0 clipped without the
    call and 2 clipped with it.
    """
    try:
        from PyQt6.QtWidgets import (QApplication, QDialogButtonBox, QLabel,
                                     QSizePolicy, QSpacerItem)

        buttons = list(box.buttons())
        # A ROW OF TWO IS NOT A BUNCH. Qt's right-aligned pair reads correctly
        # and is what every other window in the app shows.
        bb = box.findChild(QDialogButtonBox)
        outer = box.layout()
        if bb is None or bb.layout() is None or outer is None:
            return
        if order is not None and set(order) != set(buttons):
            _log.warning("spread: the given button order is not this box's "
                         "buttons — ignoring it")
            order = None

        # ORDER FIRST, AND FOR ANY NUMBER OF BUTTONS.
        #
        # This function does two jobs — it puts the buttons in the order the
        # caller asked for, and it shares the row's width between them — and a
        # single `len(buttons) < 3` return used to skip BOTH. Sharing the width
        # of a two-button row is pointless, which is what that guard was for;
        # but the ORDER matters at any count, and Qt lays a QDialogButtonBox out
        # by ROLE, which on macOS puts Cancel on the LEFT. So every two-button
        # window in ChromIQ ignored the order it was given and put Cancel where
        # Basti has twice asked it not to be: *"cancel should always be on the
        # very right"*.
        if order:
            lay = bb.layout()
            for b in order:
                lay.removeWidget(b)
            for b in order:
                lay.addWidget(b)
        if len(buttons) < 3:
            return          # ordered, but a two-button row needs no spreading

        widest = max(b.sizeHint().width() for b in buttons)
        # The icon has its own grid column and the button row does not get it,
        # so a box with an icon is that much narrower across the buttons.
        icon_w = 0
        for lbl in box.findChildren(QLabel):
            pm = lbl.pixmap()
            if pm is not None and not pm.isNull():
                icon_w = max(icon_w, lbl.sizeHint().width() + 20)
        needed = len(buttons) * (widest + 18) + 24 + icon_w
        screen = QApplication.primaryScreen()
        if screen is not None and needed > screen.availableGeometry().width() - 80:
            _log.debug("spread: %d px needed, screen too narrow — left as Qt "
                       "drew it", needed)
            return

        lay = bb.layout()
        # The stretches Qt inserts to push the row to one side.
        for i in reversed(range(lay.count())):
            item = lay.itemAt(i)
            if item is not None and item.widget() is None:
                lay.takeAt(i)
        if order:
            for b in order:
                lay.removeWidget(b)
            for b in order:
                lay.addWidget(b)
        for i in range(lay.count()):
            item = lay.itemAt(i)
            w = item.widget() if item is not None else None
            if w is not None:
                w.setSizePolicy(QSizePolicy.Policy.Expanding,
                                w.sizePolicy().verticalPolicy())
                lay.setStretch(i, 1)
        outer.addItem(QSpacerItem(needed, 0,
                                  QSizePolicy.Policy.Minimum,
                                  QSizePolicy.Policy.Expanding),
                      outer.rowCount(), 0, 1, outer.columnCount())
        outer.activate()
        lay.activate()
    except Exception:      # noqa: BLE001 — sizing must never raise
        pass


class NameOrderProxy(QSortFilterProxyModel):
    """Sorts a `QFileSystemModel` the way ChromIQ orders names EVERYWHERE.

    Ordering only — subclasses add filtering. Installed on all four file-dialog
    helpers unconditionally, because the whole point is that a person cannot
    tell which dialog they are in from the order the names come out in.

    IT USED TO DEPEND ON THE CALLER'S FILTER STRING. The proxy was installed
    only `if exts:`, so a dialog opened with `"ChromIQ profile (project.json)"`
    — no `*.` glob — got a different order from one opened with
    `"TI3 files (*.ti3)"`, and `ui/parameter_widget.py` took its filter from
    `data/parameters.yaml`, which meant a *YAML file* decided how a list of
    names was sorted. That is why the rule lives in `core.name_order` and the
    install is unconditional (Basti, 2026-09-02).
    """

    #: Group directories above files. Qt does this on Windows and Linux and
    #: deliberately does NOT on macOS (`QFileSystemModelSorter` guards the
    #: branch with `#ifndef Q_OS_MAC`), so ChromIQ's three platforms disagreed
    #: with each other. We group everywhere: in a picker over `~/ChromIQ/` the
    #: folders ARE the projects, and grouping them makes the list scannable.
    folders_first = True

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # These govern only the base-class fallback below (a non-name column,
        # or the exception path). The name column goes through
        # `core.name_order`. Set anyway so that NO path can fall back to the
        # ASCII order this class exists to remove — Qt's defaults here are
        # `CaseSensitive` and locale-unaware, measured.
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortLocaleAware(True)

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if self.sortColumn() != 0:          # Size / Kind / Date — Qt's business
            return super().lessThan(left, right)
        src = self.sourceModel()
        try:
            l_dir, r_dir = src.isDir(left), src.isDir(right)
            if self.folders_first and l_dir != r_dir:
                return l_dir
            l_name, r_name = src.fileName(left), src.fileName(right)
        except Exception:      # noqa: BLE001 — never break a file dialog
            return super().lessThan(left, right)
        return name_sort_key(l_name) < name_sort_key(r_name)


class _ExtensionFilterProxy(NameOrderProxy):
    """Hides files whose extension is not in the allowed set; directories are
    always shown. An empty set filters nothing, so this is also the plain
    "order it properly" proxy for a dialog with no extensions to match on."""

    def __init__(self, extensions: list[str], parent=None) -> None:
        super().__init__(parent)
        self._exts = {e.lower() for e in extensions}

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._exts:
            return True
        src = self.sourceModel()
        idx = src.index(source_row, 0, source_parent)
        try:
            if src.isDir(idx):
                return True
            name = src.fileName(idx)
        except Exception:
            return True
        dot = name.rfind(".")
        if dot < 0:
            return False
        return ("." + name[dot + 1:].lower()) in self._exts


def _parse_extensions(name_filter: str) -> list[str]:
    """Return ['.ti3', '.icc'] from 'ICC profiles (*.icc *.icm)'."""
    return ["." + e.lower() for e in re.findall(r"\*\.(\w+)", name_filter)]


def _input_bg_qss() -> str:
    """Per-widget QSS rule forcing the body of QComboBox / QSpinBox /
    QDoubleSpinBox to the current theme's input background colour
    (white in light, BG_INPUT #1f1f1f in dark). App-wide QSS for these
    rules is silently ignored by Qt's QStyleSheetStyle for compound
    widgets, but per-widget setStyleSheet bypasses that quirk."""
    bg = QApplication.palette().base().color().name()
    return (
        "QComboBox:enabled, QSpinBox:enabled, QDoubleSpinBox:enabled {"
        f" background-color: {bg};"
        "}"
    )


def confirm(
    parent,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton,
    default: "QMessageBox.StandardButton | None" = None,
) -> QMessageBox.StandardButton:
    """Yes/No-style confirmation prompt without the question-mark icon.

    A drop-in for ``QMessageBox.question`` (which bakes in the “?” icon the
    user dislikes): same signature shape, returns the StandardButton clicked.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setStandardButtons(buttons)
    if default is not None:
        box.setDefaultButton(default)
    box.exec()
    return box.standardButton(box.clickedButton())


class NoScrollComboBox(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_input_bg_qss())

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class ElidingComboBox(NoScrollComboBox):
    """A combo whose MINIMUM width is a few characters, not its longest item.

    THE VISIBLE TRADE IS ACCEPTED — DO NOT "FIX" IT. Basti, 2026-08-27, having
    been shown exactly what it costs: ONE option in ONE language is trimmed. The
    Create-layout dropdown's longer Russian option needs 325 px in a 304 px box,
    so it reads "…затем вписать в стр…". The full string is still in the open
    dropdown and in the tooltip; only the collapsed box trims. Portuguese sits
    4 px inside the limit and may trim on some displays — same sentence, same
    ending. German has 25 px of room and English 113.

    He was offered three ways out — accept it, shorten the two long strings, or
    give that row the panel's full width the way the text-distance row has — and
    chose to accept. So a later reader finding a "…" here is looking at a
    decision, not a defect, and shortening those strings or widening that row
    would be undoing it.

    ``QComboBox`` computes both ``sizeHint()`` **and** ``minimumSizeHint()``
    over every row in its model (``QComboBoxPrivate::recomputeSizeHint``, for
    every size-adjust policy except ``AdjustToMinimumContentsLengthWithIcon``).
    So a combo that offers a sentence — "Prioritise chart area, then fit
    patches to it" — turns that sentence into a hard floor for the grid column
    it sits in, and through it for the whole panel. The Create Chart pane is
    locked at 580 px to line up with Print, Measure and Check & Refine, so the
    floor has nowhere to go: the panel scrolls sideways instead.

    Measured on screen, 2026-08-27, Create Chart > Manual with every section
    open: English needs 494 px into a 540 px viewport and is fine, which is why
    the owner saw nothing wrong in English — and nine of the thirteen languages
    need more than 540 (Italian 611, Portuguese 609, Russian 600).

    This class keeps ``sizeHint()`` untouched, so the combo still takes its
    natural width wherever there is room and nothing moves in a layout that
    already fits. Only the MINIMUM changes: it drops to :attr:`MIN_CHARS`
    characters' worth, and the painted text is elided with an ellipsis when the
    combo is squeezed below its natural width. The model is never touched, so
    ``currentText()``, ``itemText()``, the popup and every caller that reads the
    combo still see the full string; while text is actually elided the full
    string is offered as the tooltip.

    Use it for any combo whose entries are phrases rather than short values.
    A combo of short values loses nothing by being one of these either — it
    simply never elides.
    """

    #: Characters the combo is always wide enough for. Twelve keeps a value
    #: recognisable ("Prioritise c…") without letting one sentence dictate the
    #: width of the pane it sits in.
    MIN_CHARS = 10

    def __init__(self, *args, **kwargs):
        self._explicit_tooltip = ""
        super().__init__(*args, **kwargs)

    # -- geometry ------------------------------------------------------
    def _widest_item(self) -> int:
        fm = self.fontMetrics()
        return max((fm.horizontalAdvance(self.itemText(i))
                    for i in range(self.count())), default=0)

    def _style_chrome(self) -> int:
        """Frame + arrow + padding, asked of the style. Zero before the first
        layout pass, in which case callers fall back on Qt's own figure."""
        from PyQt6.QtWidgets import QStyleOptionComboBox
        if self.width() <= 0:
            return 0
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        return max(0, self.width() - self._edit_rect(opt).width())

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        """Qt's own hint, floored at what the text actually needs.

        `QComboBox.sizeHint()` is computed and cached the first time it is
        asked, which is BEFORE the per-widget stylesheet is polished in — so it
        misses the QSS padding, and the widget is handed a few pixels less than
        its text needs. Harmless in a plain combo, which simply clips a little;
        here it made the box elide text that would have fitted (the Measure
        tab's Spanish "Predeterminado de Argyll" lost its last four characters
        in a box that had room for them). Same trap as the QSS-padding note in
        ui/styles.py.
        """
        base = super().sizeHint()
        chrome = self._style_chrome()
        if chrome <= 0:
            return base
        return QSize(max(base.width(), self._widest_item() + chrome + 2),
                     base.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        base = super().minimumSizeHint()
        fm = self.fontMetrics()
        # The chrome (frame, arrow, padding) is whatever the style says it is:
        # take it from the difference between the full hint and the widest
        # item's text, rather than guessing a constant that a stylesheet change
        # would quietly invalidate.
        chrome = self._style_chrome() or max(0, base.width() - self._widest_item())
        want = chrome + fm.horizontalAdvance("x") * self.MIN_CHARS
        return QSize(min(base.width(), want), base.height())

    # -- elided painting ----------------------------------------------
    def _edit_rect(self, opt) -> QRect:
        return self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, opt,
            QStyle.SubControl.SC_ComboBoxEditField, self)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        from PyQt6.QtWidgets import QStyleOptionComboBox, QStylePainter
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.ColorRole.Text))
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        avail = self._edit_rect(opt).width()
        if avail > 0:
            opt.currentText = self.fontMetrics().elidedText(
                opt.currentText, Qt.TextElideMode.ElideRight, avail)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, opt)

    # -- tooltip -------------------------------------------------------
    def setToolTip(self, text: str) -> None:  # noqa: N802 (Qt override)
        """Remember the caller's tooltip so the elision tooltip can be taken
        away again without erasing it."""
        self._explicit_tooltip = text or ""
        super().setToolTip(self._explicit_tooltip)

    def _refresh_elide_tooltip(self) -> None:
        from PyQt6.QtWidgets import QStyleOptionComboBox
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        full = opt.currentText
        avail = self._edit_rect(opt).width()
        clipped = (avail > 0
                   and self.fontMetrics().horizontalAdvance(full) > avail)
        super().setToolTip(full if clipped and not self._explicit_tooltip
                           else self._explicit_tooltip)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._refresh_elide_tooltip()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._refresh_elide_tooltip()


class NoScrollSpinBox(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_input_bg_qss())

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """Every number field in ChromIQ with a decimal point is one of these.

    IT ACCEPTS BOTH SEPARATORS, AND THAT IS NOT A CONVENIENCE — IT IS A BUG FIX.
    A spin box runs on the SYSTEM locale, so on a German machine the decimal
    separator is a comma. ChromIQ writes its numbers the English way everywhere
    else: the tooltips say 0.7, the ArgyllCMS flag documentation says 0.7, and
    the live command preview under the field says -T0.70. Type what you are
    told to type and the box rejects the "." keystroke, the digits close up, and
    0.7 silently becomes 07, which is 7.0. In range, no warning, nothing on
    screen disagreeing with anything else.

    Measured on screen, 2026-08-28, on a real de_DE machine: all fourteen of
    them. The expensive one is the patch-consistency tolerance, where the app
    really sent `chartread -T7.00` instead of `-T0.70` — telling the instrument
    to accept a strip ten times further out of agreement than the person asked
    for, which is a measurement that looks fine and is not. The dE
    re-measurement threshold does the mirror thing: ask for 0.7, get 7.0, and no
    strip is ever flagged.

    So both "." and "," are read as the decimal point, whichever one the locale
    itself uses. Basti ruled on 2026-08-28 that a comma is ALWAYS a decimal
    point here, never a thousands separator: 1,250 is one and a quarter, not one
    thousand two hundred and fifty. Of these fields only two have a range that
    reaches four digits, and neither is somewhere a person would reach for a
    thousands separator, so the alternative — refusing anything ambiguous —
    would interrupt typing to prevent a case that barely exists.

    NOT fixed with `QLocale.setDefault(C)`, which was the first idea and is
    measurably worse: under C, typing 0,7 gives 7.0. That does not fix the bug,
    it aims it at the people whose keyboard habit is the comma.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_input_bg_qss())

    def _normalised(self, text: str) -> str:
        """*text* with whichever separator is not this locale's swapped for the
        one that is. Leaves anything else exactly as typed."""
        want = self.locale().decimalPoint()
        other = "," if want == "." else "."
        return text.replace(other, want) if other in text else text

    def validate(self, text, pos):        # noqa: N802 — Qt's name
        return super().validate(self._normalised(text), pos)

    def valueFromText(self, text):        # noqa: N802 — Qt's name
        return super().valueFromText(self._normalised(text))

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class WrappingCheckBox(QCheckBox):
    """A check box whose label wraps instead of setting a floor for the panel.

    ``QCheckBox`` has no word-wrap: its ``minimumSizeHint()`` is the indicator
    plus the whole label on one line, and it CLIPS rather than eliding when it
    is given less. So one long option — Russian's
    "Краевые разделители (обрамляют каждую полосу)", 354 px — becomes a hard
    floor for the grid column it sits in, and through it for the Create Chart
    pane, which is locked at 580 px. That is the same fault
    :class:`ElidingComboBox` fixes for combos, in the one widget class where
    eliding would be wrong: dropping words from an option label leaves the user
    guessing what the option does.

    So the label wraps. The minimum becomes the indicator plus the longest
    single WORD, the preferred size is unchanged (one line — nothing moves in a
    layout that already fits), and the height grows by a line only when the
    text genuinely cannot fit on one.

    Both the indicator and each line of text are drawn through the style
    (``PE_IndicatorCheckBox`` / ``CE_CheckBoxLabel``), so the stylesheet's
    ``QCheckBox::indicator`` rules — which is where the accent colour, the
    hover border and the disabled greys live — keep applying. ``text()`` still
    returns the whole label, so every caller and every test that looks a box up
    by its text is unaffected.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        # A QCheckBox ships with QSizePolicy.Minimum horizontally, and
        # `qSmartMinSize` only consults `minimumSizeHint()` for a policy that
        # carries the SHRINK flag — for Minimum it takes `max(sizeHint,
        # minimumSizeHint)`, i.e. the whole label on one line, and the override
        # below would never be looked at. (QComboBox is Expanding, which is why
        # ElidingComboBox needs no equivalent.) Preferred keeps the same
        # preferred width and adds permission to go under it.
        sp.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        self.setSizePolicy(sp)

    # -- geometry ------------------------------------------------------
    def _label_rect(self) -> QRect:
        from PyQt6.QtWidgets import QStyleOptionButton
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        return self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxContents, opt, self)

    def _chrome_width(self) -> int:
        """Everything the label does NOT get: indicator, spacing, margins."""
        return max(0, self.width() - self._label_rect().width())

    @staticmethod
    def _shown(text: str) -> str:
        """The text as it is PAINTED: `&&` is an escaped ampersand and `&x` a
        mnemonic, so neither is a character wide on screen. Wrapping works on
        the raw string — the lines are handed back to the style, which does the
        un-escaping itself — but every measurement uses this."""
        return text.replace("&&", "&")

    def _lines(self, width: int) -> list:
        """Greedy word wrap of the label into *width* pixels. Lines are RAW
        (still escaped), because they are drawn through the style."""
        fm = self.fontMetrics()
        words = self.text().split()
        if not words:
            return [""]
        lines, cur = [], words[0]
        for word in words[1:]:
            trial = f"{cur} {word}"
            if fm.horizontalAdvance(self._shown(trial)) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt override)
        base = super().minimumSizeHint()
        fm = self.fontMetrics()
        words = self.text().split()
        if not words:
            return base
        widest_word = max(fm.horizontalAdvance(self._shown(w)) for w in words)
        # The chrome cannot be read off self.width() before the first layout
        # pass, so take it from the un-wrapped hint and the whole label.
        chrome = max(0, base.width() - fm.horizontalAdvance(
            self._shown(self.text())))
        return QSize(min(base.width(), chrome + widest_word), base.height())

    def hasHeightForWidth(self) -> bool:  # noqa: N802 (Qt override)
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 (Qt override)
        one_line = super().sizeHint().height()
        fm = self.fontMetrics()
        chrome = max(0, super().sizeHint().width() - fm.horizontalAdvance(
            self._shown(self.text())))
        avail = max(1, width - chrome)
        n = len(self._lines(avail))
        if n <= 1:
            return one_line
        return max(one_line, n * fm.lineSpacing() + (one_line - fm.height()))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Claim the height the wrapped label needs.

        `heightForWidth` alone is not enough here. A QGridLayout will ask an
        item for it, but only if every layout and widget BETWEEN this box and
        the window passes the flag up — and QGroupBox, which every group in this
        panel is, does not. The Russian option
        "Краевые разделители (обрамляют каждую полосу)" duly wrapped and then
        painted one line into a one-line row, so it read
        "Краевые разделители (обрамляют" and the rest was gone: a worse fault
        than the one being fixed.

        Asking for the height directly works whatever the parents do. It
        settles after one extra pass, because the second resize computes the
        same number and changes nothing.
        """
        super().resizeEvent(event)
        need = self.heightForWidth(self.width())
        if need > 0 and self.minimumHeight() != need:
            self.setMinimumHeight(need)

    # -- painting ------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        from PyQt6.QtWidgets import QStyleOptionButton, QStylePainter
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        painter = QStylePainter(self)
        style = self.style()
        text_rect = style.subElementRect(
            QStyle.SubElement.SE_CheckBoxContents, opt, self)
        lines = self._lines(text_rect.width())
        fm = self.fontMetrics()

        ind = QStyleOptionButton(opt)
        ind.rect = style.subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, opt, self)
        if len(lines) > 1:
            # Sit the indicator on the FIRST line rather than in the middle of
            # a two-line block, which is where a centred one would land.
            ind.rect.moveTop(text_rect.top()
                             + max(0, (fm.lineSpacing() - ind.rect.height()) // 2))
        painter.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorCheckBox, ind)

        if len(lines) <= 1:
            line_opt = QStyleOptionButton(opt)
            line_opt.rect = text_rect
            painter.drawControl(QStyle.ControlElement.CE_CheckBoxLabel, line_opt)
            return
        total = len(lines) * fm.lineSpacing()
        y = text_rect.top() + max(0, (text_rect.height() - total) // 2)
        for line in lines:
            line_opt = QStyleOptionButton(opt)
            line_opt.text = line
            line_opt.rect = QRect(text_rect.left(), y,
                                  text_rect.width(), fm.lineSpacing())
            painter.drawControl(QStyle.ControlElement.CE_CheckBoxLabel, line_opt)
            y += fm.lineSpacing()


class WrappingButtonRow(QLayout):
    """A row of buttons that becomes two (or three) rows when the labels are
    too long for the width it has been given.

    WHY THIS EXISTS
    ---------------
    Create Chart ▸ Manual is inside a pane pinned at 580 px, and its layout-
    engine preset bar holds three buttons whose labels are full sentences in
    most languages ("Auf Vorgabe zurücksetzen", "Återställ till
    förinställning"). A plain ``QHBoxLayout`` answers "I need the sum of them",
    which for German is 592 px against a 540 px viewport and for Swedish 687 —
    so the pane was clipped on the right, with the horizontal scroll bar pinned
    off so nothing showed that it had happened. The owner reported it five
    times.

    Shortening the labels was the obvious treatment and it is not a fix: it
    puts a character budget on every translator, for every language now and
    every language later, and the budget is about 56 characters across the
    three labels. Eliding them is worse — the button then reads "AUF VORGABE
    ZURÜCK…", which is the very complaint. Wrapping is the only arrangement
    that is correct by construction: **the widest SINGLE button is the floor,
    not the sum**, and no button ever paints text it does not have room for.

    HOW IT PACKS
    ------------
    Greedy, in order, by each item's *minimum* width — which for a button in
    this app is the per-label ``min-width`` rule :func:`fit_button_width`
    writes, i.e. exactly the width its text needs in Menlo capitals. A line
    takes another button while the line still fits; otherwise it starts a new
    one. Each finished line is then **justified**: the space left over is
    shared out equally among that line's buttons, so a row that does fit on one
    line looks precisely as it did before — three equal buttons filling the
    panel — and a row that does not looks like the same block, wrapped.

    The packing is done from actual widths and not from a uniform column, on
    purpose: Italian needs 157 + 141 + 188 = 498 px and fits on one line, while
    three columns of its widest button would need 576 and would have wrapped it
    for no reason.
    """

    def __init__(self, parent=None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items: list = []
        self.setSpacing(spacing)

    # ---- QLayout plumbing -------------------------------------------------
    def addItem(self, item) -> None:        # noqa: N802 (Qt override)
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):           # noqa: N802 (Qt override)
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):           # noqa: N802 (Qt override)
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    # ---- geometry ---------------------------------------------------------
    def _visible(self) -> list:
        out = []
        for it in self._items:
            w = it.widget()
            if w is not None and w.isHidden():
                continue
            out.append(it)
        return out

    def _pack(self, width: int) -> list[list]:
        """Greedy line breaking at *width* (the layout's own outer width)."""
        m = self.contentsMargins()
        avail = max(1, width - m.left() - m.right())
        sp = self.spacing()
        lines: list[list] = []
        cur: list = []
        cur_w = 0
        for it in self._visible():
            need = it.minimumSize().width()
            grown = need if not cur else cur_w + sp + need
            if cur and grown > avail:
                lines.append(cur)
                cur, cur_w = [it], need
            else:
                cur, cur_w = cur + [it], grown
        if cur:
            lines.append(cur)
        return lines

    def _line_height(self, line: list) -> int:
        return max((it.sizeHint().height() for it in line), default=0)

    def hasHeightForWidth(self) -> bool:    # noqa: N802 (Qt override)
        return True

    def heightForWidth(self, width: int) -> int:   # noqa: N802 (Qt override)
        lines = self._pack(width)
        if not lines:
            return 0
        m = self.contentsMargins()
        sp = self.spacing()
        return (m.top() + m.bottom()
                + sum(self._line_height(ln) for ln in lines)
                + sp * (len(lines) - 1))

    def setGeometry(self, rect) -> None:    # noqa: N802 (Qt override)
        super().setGeometry(rect)
        lines = self._pack(rect.width())
        if not lines:
            return
        m = self.contentsMargins()
        sp = self.spacing()
        avail = max(1, rect.width() - m.left() - m.right())
        y = rect.y() + m.top()
        for line in lines:
            widths = [it.minimumSize().width() for it in line]
            spare = avail - sum(widths) - sp * (len(line) - 1)
            if spare > 0:
                # Justify: share the slack out equally, remainder to the last
                # button, so the line always ends flush with the panel edge.
                share = spare // len(line)
                widths = [w + share for w in widths]
                widths[-1] += spare - share * len(line)
            h = self._line_height(line)
            x = rect.x() + m.left()
            for it, w in zip(line, widths):
                it.setGeometry(QRect(x, y, w, h))
                x += w + sp
            y += h + sp

    def expandingDirections(self):          # noqa: N802 (Qt override)
        # NOT the QLayout default (Horizontal | Vertical). The bar sits in a
        # QVBoxLayout; claiming vertical expansion there would hand it every
        # spare pixel in the column.
        #
        # And do NOT give the host widget a FIXED vertical size policy to the
        # same end. ``QBoxLayout`` implements height-for-width by overwriting an
        # item's sizeHint and minimumSize with the computed height — it never
        # touches its MAXIMUM. Under a Fixed policy that maximum is still the
        # one-line sizeHint, so a two-line row is clamped back to one line and
        # the second line is clipped away by the parent. Measured: the bar came
        # out 38 px tall with its third button sitting at y=37.
        return Qt.Orientation.Horizontal

    def minimumSize(self) -> QSize:         # noqa: N802 (Qt override)
        """The widest SINGLE button — this is the whole point of the class.

        Height is one line's worth: the real height comes from
        :meth:`heightForWidth`, which both ``QBoxLayout`` and ``QScrollArea``
        ask for, and a multi-line floor here would reserve the space
        permanently.
        """
        m = self.contentsMargins()
        items = self._visible()
        w = max((it.minimumSize().width() for it in items), default=0)
        h = max((it.minimumSize().height() for it in items), default=0)
        return QSize(w + m.left() + m.right(), h + m.top() + m.bottom())

    def sizeHint(self) -> QSize:            # noqa: N802 (Qt override)
        m = self.contentsMargins()
        items = self._visible()
        if not items:
            return QSize(m.left() + m.right(), m.top() + m.bottom())
        w = (sum(it.sizeHint().width() for it in items)
             + self.spacing() * (len(items) - 1))
        h = max(it.sizeHint().height() for it in items)
        return QSize(w + m.left() + m.right(), h + m.top() + m.bottom())


class SuffixLockedLineEdit(QLineEdit):
    """A line edit with a locked, non-editable suffix tail.

    The user edits only the leading *base*; the *suffix* is set by the owner via
    :meth:`set_suffix` and can't be typed into, deleted, selected away or pasted
    over — it can only be changed or cleared programmatically (e.g. by an
    auto-name toggle that recomputes it from the chart settings). With an empty
    suffix it behaves exactly like a plain ``QLineEdit``.

    Enforcement is behavioural (a normal field can't visually lock part of its
    text): the suffix region is kept out of selections / the cursor, boundary
    deletes are swallowed, and a ``textChanged`` net repairs a wholesale replace.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._suffix = ""
        self._guard = False
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._on_cursor)

    # -- public ---------------------------------------------------------
    def set_suffix(self, suffix: str) -> None:
        """Replace the locked tail, preserving the user's base text."""
        suffix = suffix or ""
        if suffix == self._suffix:
            return
        base = self.base()
        self._suffix = suffix
        self._set(base, len(base))

    def base(self) -> str:
        """The editable leading part (text without the locked suffix)."""
        t = super().text()
        if self._suffix and t.endswith(self._suffix):
            return t[: len(t) - len(self._suffix)]
        return t

    def set_base(self, base: str) -> None:
        self._set(base or "", len(base or ""))

    # -- internals ------------------------------------------------------
    def _set(self, base: str, cursor: int) -> None:
        self._guard = True
        super().setText(base + self._suffix)
        super().setCursorPosition(min(cursor, len(base)))
        self._guard = False

    def _base_end(self) -> int:
        t = super().text()
        if self._suffix and t.endswith(self._suffix):
            return len(t) - len(self._suffix)
        return len(t)

    def _clamp_selection(self) -> None:
        if not self._suffix:
            return
        end = self._base_end()
        self._guard = True
        if self.selectionStart() >= 0 and self.selectionLength() > 0:
            s = min(self.selectionStart(), end)
            e = min(self.selectionStart() + self.selectionLength(), end)
            self.setSelection(s, max(0, e - s))
        elif self.cursorPosition() > end:
            super().setCursorPosition(end)
        self._guard = False

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if self._suffix:
            end = self._base_end()
            # A forward-delete sitting at the base/suffix boundary would eat into
            # the locked tail — swallow it.
            if (ev.key() == Qt.Key.Key_Delete and self.selectionLength() == 0
                    and self.cursorPosition() >= end):
                return
            self._clamp_selection()
        super().keyPressEvent(ev)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        self._clamp_selection()      # paste lands in the base, never the suffix
        super().insertFromMimeData(source)

    def _on_cursor(self, _old: int, new: int) -> None:
        if self._guard or not self._suffix or self.selectionLength() > 0:
            return
        end = self._base_end()
        if new > end:
            self._guard = True
            super().setCursorPosition(end)
            self._guard = False

    def _on_text_changed(self, _t: str) -> None:
        # Net for a wholesale replace (e.g. select-all then paste/typing that the
        # clamps didn't catch): if the suffix is gone, treat all text as base and
        # re-append it.
        if self._guard or not self._suffix:
            return
        if not super().text().endswith(self._suffix):
            self.set_base(super().text())


class PrefixLockedLineEdit(QLineEdit):
    """A line edit with a locked, non-editable *prefix* (the mirror of
    :class:`SuffixLockedLineEdit`).

    The user edits only the trailing part; the *prefix* is set by the owner via
    :meth:`set_prefix` and can't be typed into, deleted or pasted over. Used for
    a leading descriptive name part (sortable), with the user's free text as the
    editable tail. Focusing the field drops the cursor at the start of that tail
    and scrolls it into view, so a long prefix never hides where you type.
    """

    _SEP = "-"   # joins the locked prefix to the editable tail

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prefix = ""
        self._guard = False
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._on_cursor)

    # -- public ---------------------------------------------------------
    def set_prefix(self, prefix: str) -> None:
        """Set the locked descriptive head (#68, Knut's model). The head is shown
        greyed and locked with a trailing ``-`` even when the tail is empty
        (``name-`` → ``name-mytext``); the user only edits the tail after it.
        Pass ``""`` to remove the lock entirely (a plain, fully editable field).
        A trailing separator on *prefix* is dropped (it's supplied
        automatically)."""
        prefix = prefix or ""
        if prefix.endswith(self._SEP):
            prefix = prefix[: -len(self._SEP)]
        if prefix == self._prefix:
            return
        tail = self.tail()
        self._prefix = prefix
        self._set(tail)

    def tail(self) -> str:
        """The editable trailing part (text after the locked prefix + separator)."""
        t = super().text()
        if not self._prefix:
            return t
        head = self._prefix + self._SEP
        if t.startswith(head):
            return t[len(head):]
        if t.startswith(self._prefix):   # transient: separator momentarily gone
            return t[len(self._prefix):]
        return t

    def set_tail(self, tail: str) -> None:
        self._set(tail or "")

    # -- internals ------------------------------------------------------
    def _full(self, tail: str) -> str:
        """Canonical text: ``prefix + '-' + tail`` whenever a prefix is set (the
        separator stays even when the tail is empty), else just the tail."""
        if not self._prefix:
            return tail
        return self._prefix + self._SEP + tail

    def _set(self, tail: str) -> None:
        self._guard = True
        super().setText(self._full(tail))
        super().setCursorPosition(len(super().text()))   # land in the tail
        self._guard = False

    def _locked_len(self) -> int:
        """Length of the non-editable head in the CURRENT text (prefix + the
        always-present separator)."""
        t = super().text()
        if not self._prefix:
            return 0
        head = self._prefix + self._SEP
        if t.startswith(head):
            return len(head)
        if t.startswith(self._prefix):   # transient (separator being re-added)
            return len(self._prefix)
        return 0

    def _clamp(self) -> None:
        if not self._prefix:
            return
        start = self._locked_len()
        self._guard = True
        if self.selectionStart() >= 0 and self.selectionLength() > 0:
            s = max(self.selectionStart(), start)
            e = max(self.selectionStart() + self.selectionLength(), start)
            self.setSelection(s, max(0, e - s))
        elif self.cursorPosition() < start:
            super().setCursorPosition(start)
        self._guard = False

    def keyPressEvent(self, ev) -> None:  # noqa: N802
        if self._prefix:
            start = self._locked_len()
            if self.selectionLength() == 0:
                # Backspace at the boundary would eat the locked head/separator;
                # forward-Delete from inside the locked head would eat a prefix
                # character. Swallow both.
                if (ev.key() == Qt.Key.Key_Backspace
                        and self.cursorPosition() <= start):
                    return
                if (ev.key() == Qt.Key.Key_Delete
                        and self.cursorPosition() < start):
                    return
            self._clamp()
        super().keyPressEvent(ev)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        self._clamp()
        super().insertFromMimeData(source)

    def focusInEvent(self, ev) -> None:  # noqa: N802
        super().focusInEvent(ev)
        if self._prefix:
            # Land in the editable tail (and let Qt scroll it into view) rather
            # than selecting the whole — locked — string.
            self.deselect()
            self.setCursorPosition(len(super().text()))

    def _on_cursor(self, _old: int, new: int) -> None:
        if self._guard or not self._prefix or self.selectionLength() > 0:
            return
        start = self._locked_len()
        if new < start:
            self._guard = True
            super().setCursorPosition(start)
            self._guard = False

    def _on_text_changed(self, _t: str) -> None:
        if self._guard or not self._prefix:
            return
        # Re-render canonically so the locked separator is always present while a
        # prefix is set (it can't be deleted to merge the head into the tail).
        t = super().text()
        canonical = self._full(self.tail())
        if t != canonical:
            self._guard = True
            super().setText(canonical)
            super().setCursorPosition(len(canonical))   # edits happen at the tail end
            self._guard = False

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)
        # Grey the locked head so it visibly reads as non-editable (#68, Knut).
        # Only when the text fits without horizontal scroll: once it scrolls, the
        # glyphs no longer start at the content's left edge and an overlay would
        # mis-paint — the always-present '-' still marks the boundary there.
        if self._prefix == "" or self.hasSelectedText():
            return
        locked = self._locked_len()
        if locked <= 0:
            return
        text = super().text()
        fm = self.fontMetrics()
        opt = QStyleOptionFrame()
        self.initStyleOption(opt)
        content = self.style().subElementRect(
            QStyle.SubElement.SE_LineEditContents, opt, self)
        if fm.horizontalAdvance(text) > content.width() - 4:
            return
        x0 = content.left() + 2
        w = fm.horizontalAdvance(text[:locked])
        rect = QRect(x0, content.top(), w, content.height())
        p = QPainter(self)
        p.fillRect(rect, self.palette().color(QPalette.ColorRole.Base))
        p.setFont(self.font())
        p.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        p.drawText(rect, int(Qt.AlignmentFlag.AlignVCenter
                             | Qt.AlignmentFlag.AlignLeft), text[:locked])
        p.end()


class ElidingLabel(QLabel):
    """Single-line label that middle-elides overflowing text with ``(...)``.

    A long file path used to expand the label to its full natural width and
    squeeze the adjacent "Load" button. This label reports a zero minimum
    width (size policy ``Ignored``) so it never pushes its neighbours, and
    middle-elides whatever no longer fits the available width — keeping the
    start of the path and the filename at the end both visible. The full,
    un-elided text is preserved and exposed as a hover tooltip and via
    ``text()``.
    """

    _SEP = "(...)"

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setWordWrap(False)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text or ""
        self._apply_elision()

    def text(self) -> str:  # type: ignore[override]
        """Return the full, un-elided text (not what is currently painted)."""
        return self._full_text

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_elision()

    def _apply_elision(self) -> None:
        fm = self.fontMetrics()
        avail = self.width()
        full = self._full_text
        if avail <= 0 or fm.horizontalAdvance(full) <= avail:
            super().setText(full)
            self.setToolTip("")
            return
        budget = avail - fm.horizontalAdvance(self._SEP)
        if budget <= 0:
            super().setText(self._SEP)
            self.setToolTip(full)
            return
        # Grow head and tail one character at a time, alternating, until the
        # next character would overflow the budget either side of the separator.
        head, tail = "", ""
        i, j = 0, len(full) - 1
        take_head = True
        while i <= j:
            ch = full[i] if take_head else full[j]
            if fm.horizontalAdvance(head + ch + tail) > budget:
                break
            if take_head:
                head += ch
                i += 1
            else:
                tail = ch + tail
                j -= 1
            take_head = not take_head
        super().setText(f"{head}{self._SEP}{tail}")
        self.setToolTip(full)


def reapply_input_stylesheet(root: QWidget) -> None:
    """Re-apply the per-widget input-bg QSS on every combo/spin descendant.
    Called from MainWindow.apply_theme on every theme switch so the
    hardcoded colour in the existing per-widget stylesheet is refreshed
    for the new theme."""
    qss = _input_bg_qss()
    for cls in (QComboBox, QSpinBox, QDoubleSpinBox):
        for w in root.findChildren(cls):
            w.setStyleSheet(qss)


class CollapsibleGroupBox(QGroupBox):
    """A QGroupBox whose title is clickable to collapse / expand its contents.

    Keeps the native framed look (border + embedded title) so it matches the
    other sections; the title gains a ▸ / ▾ arrow and, when collapsed, the body
    is hidden and the box shrinks to the title.

    Put content on the ``.body`` widget — ``QGridLayout(group.body)`` etc. — not
    on the group itself, so collapsing hides one container and each child keeps
    its own intended visibility (mode logic may hide individual fields) (Knut:
    collapsible Create-Chart sections)."""

    def __init__(self, title: str = "", parent=None, *, collapsed: bool = False):
        super().__init__("", parent)
        self._base_title = title
        self._collapsed = bool(collapsed)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)
        self.body = QWidget(self)
        self._outer.addWidget(self.body)
        # Bold the section title (incl. the arrow) so the header clearly reads as
        # a clickable open/close control (Knut); keep the body at normal weight.
        _tf = self.font()
        _tf.setBold(True)
        self.setFont(_tf)
        _bf = QFont(_tf)
        _bf.setBold(False)
        self.body.setFont(_bf)
        self._render_title()
        self.body.setVisible(not self._collapsed)

    def setTitle(self, title: str) -> None:        # noqa: N802 (Qt override)
        self._base_title = title
        self._render_title()

    def _render_title(self) -> None:
        # Bigger, filled triangles (▶ / ▼) read far more clearly as an open/close
        # affordance than the small ▸ / ▾ (Knut). A trailing space sets them off.
        super().setTitle(("▶  " if self._collapsed else "▼  ") + self._base_title)

    def title(self) -> str:                        # noqa: N802 (Qt override)
        return self._base_title

    def _title_band(self) -> int:
        return self.fontMetrics().height() + 10

    def is_collapsed(self) -> bool:
        return self._collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self._render_title()
        self.body.setVisible(not self._collapsed)
        # Drop the box frame while collapsed so only the ▸ title line shows
        # (no empty bordered box); restore the frame when expanded (Knut).
        self.setFlat(self._collapsed)
        self.updateGeometry()

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def mousePressEvent(self, event) -> None:      # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton \
                and event.position().y() <= self._title_band():
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)


def _apply_groupbox_surface(gb: QGroupBox) -> None:
    """Paint the GroupBox surface via QPalette + autoFillBackground instead
    of QSS. The QSS rule `QGroupBox { background: ... }` causes Qt's
    QStyleSheetStyle to propagate the colour into descendants' palette
    roles (including QPalette.Base), which makes QComboBox / QSpinBox
    bodies render the same surface colour as the section. Setting only
    palette.Window via setPalette() does not contaminate descendants'
    Base role, so inputs stay white per their own QSS rule."""
    # WHICH THEME, not how light the window happens to be. Asked app-wide — a
    # group box wears whatever the application is set to.
    #
    # A TABLE, NOT A YES/NO. `is_light()` had room for one appearance with a
    # raised group-box surface and the light theme was it, so Neutral fell into
    # the "no surface" branch — and worse than flat: measured in the running
    # app, its group boxes came out at the LIGHT theme's cream `#f7f4ef`,
    # 250,000 non-neutral pixels across the five tabs and the single largest
    # source of colour left in the window. (The reset in the else branch does
    # run and does set the inherited grey; QStyleSheetStyle then restores the
    # palette it cached when the box was first polished, under Light, and
    # autoFillBackground is beside the point because a QSS-styled widget paints
    # its own background from the palette.) Naming the colour explicitly for
    # every appearance that has one settles it, and the Stacked surface logic
    # the handoff specifies — panel L* 93, raised surface L* 97 — is then
    # actually delivered instead of only declared.
    from ui.theme import active_mode
    from ui.light_styles import LM_BG_SURFACE
    from ui.neutral_styles import NM_BG_SURFACE
    _surface = {"light": LM_BG_SURFACE, "neutral": NM_BG_SURFACE}
    surface = _surface.get(active_mode())
    if surface is not None:
        gb.setAutoFillBackground(True)
        pal = gb.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(surface))
        gb.setPalette(pal)
    else:
        gb.setAutoFillBackground(False)
        gb.setPalette(QPalette())  # revert to inherited


class GroupBoxSurfaceFilter(QObject):
    """Installs on QApplication. Whenever a QGroupBox is polished, applies
    the cream surface colour via setPalette + autoFillBackground so the
    QSS rule for QGroupBox can stay background-less and not contaminate
    descendant input widgets' palette.Base."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Polish and isinstance(obj, QGroupBox):
            _apply_groupbox_surface(obj)
        return False


class TooltipWrapFilter(QObject):
    """Installs on QApplication. Forces every native tooltip (Qt's private
    ``QTipLabel``) to word-wrap at a sane maximum width, so a long tooltip — in
    any language — never runs off the right edge of the screen (Knut, #70).

    Qt does not word-wrap plain-text tooltips on every platform (notably
    Windows, where Knut saw them reach far past the screen edge), so we enable
    wrapping and cap the width on the transient label as it is polished, before
    it is shown and sized. The label then re-flows to multiple lines on its own.
    """

    MAX_W = 460   # px — a comfortable reading measure; text re-flows to fit
    #: Qt's own "no maximum" value (QWIDGETSIZE_MAX), which PyQt does not export.
    _RESET_MAX = 16777215

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (event.type() in (QEvent.Type.Polish, QEvent.Type.Show)
                and obj.metaObject().className() == "QTipLabel"
                and isinstance(obj, QLabel)):
            self.fit(obj)
        return False

    def fit(self, obj: QLabel) -> None:
        """Wrap and size one tooltip label for the text it is about to show.

        **Qt reuses a single ``QTipLabel`` for every tooltip**, so this must
        start by undoing whatever the previous tooltip left behind. Without
        that reset, a fixed size set for a long tooltip stayed on the label and
        the next one was shown in the old box — too small for a longer text
        (clipped) or far too large for a shorter one (a mostly empty box), and
        hovering back and forth appeared to fix and re-break it at random
        (Knut, #130 2026-07-26).
        """
        # ---- reset: no state may carry over from the previous tooltip -------
        obj.setWordWrap(False)
        obj.setMinimumSize(0, 0)
        obj.setMaximumSize(self._RESET_MAX, self._RESET_MAX)

        fm = obj.fontMetrics()
        # Widest existing line (tooltips may already carry manual newlines).
        longest = max(
            (fm.horizontalAdvance(s) for s in obj.text().split("\n")),
            default=0,
        )
        m = obj.contentsMargins()
        pad = m.left() + m.right() + 2 * obj.margin() + 8
        if longest + pad > self.MAX_W:
            obj.setWordWrap(True)
            # heightForWidth gives the true wrapped height; pin both so
            # QToolTip's own resize(sizeHint()) can't clip it back to one
            # line (its sizeHint ignores the wrap on a transient label).
            h = obj.heightForWidth(self.MAX_W)
            if h > 0:
                obj.setFixedSize(self.MAX_W, h)
                # QToolTip already positioned the label using its huge
                # pre-wrap width, so a very wide tooltip got shoved to the
                # screen's left edge. Re-anchor the now-narrow box near the
                # cursor, clamped on-screen, so it appears where the mouse is.
                self._reanchor(obj, self.MAX_W, h)
        else:
            # Short enough for one line: let it take exactly that, in case the
            # label is still carrying the previous tooltip's larger geometry.
            obj.adjustSize()

    @staticmethod
    def _reanchor(obj: QLabel, w: int, h: int) -> None:
        from PyQt6.QtGui import QCursor, QGuiApplication
        cpos = QCursor.pos()
        screen = QGuiApplication.screenAt(cpos) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = cpos.x() + 14
        y = cpos.y() + 20
        if x + w > geo.right():
            x = cpos.x() - w - 4
        if y + h > geo.bottom():
            y = cpos.y() - h - 6
        x = min(max(x, geo.left()), geo.right() - w)
        y = min(max(y, geo.top()), geo.bottom() - h)
        obj.move(x, y)


class CompositeAppFilter(QObject):
    """The four app-wide filters as one installed object.

    Qt dispatches an application event filter to EVERY installed filter for
    EVERY event, in reverse install order, and the dispatch itself is the cost:
    ~993,000 calls per launch, of which ~1074 ms is the crossing into Python
    rather than any work the filters do. One object doing the same four things
    in the same order removes that, measured at ~1 s of a 5 s launch.

    Safe to compose because each of the four returns False unconditionally and
    none consumes an event — verified individually, and pinned by the tests.
    **Order is reverse install order** (DialogFocus, TooltipWrap, GroupBoxSurface,
    ButtonFont): Qt calls the most recently installed filter first, and three of
    the four fire on a tooltip's Show, so getting this backwards is observable.

    `CHROMIQ_SEPARATE_FILTERS=1` restores the four separate installs — the escape
    hatch for a build already in someone's hands, because the failure mode this
    could have (a control that stops being restyled) may only show up on a
    platform none of the measurements covered.
    """

    #: The only event types any of the four acts on. Everything else returns
    #: immediately, which is most of the million dispatches.
    _INTERESTING = frozenset({QEvent.Type.Polish, QEvent.Type.Show,
                              QEvent.Type.StyleChange})

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Built in reverse install order, so index 0 runs first.
        self._filters = (DialogFocusFilter(self), TooltipWrapFilter(self),
                         GroupBoxSurfaceFilter(self), ButtonFontFilter(self))

    def eventFilter(self, obj, event):  # noqa: N802 — Qt's name
        if event.type() not in self._INTERESTING:
            return False
        for f in self._filters:
            f.eventFilter(obj, event)
        return False


class DialogFocusFilter(QObject):
    """Installs on QApplication. When any top-level window (a dialog) is shown,
    Qt hands the initial focus to its first focusable child — often a button, or
    the dialog's auto-default button. The space bar would then activate it even
    though the user never tabbed there (Knut: it opened file pickers, saved
    defaults, popped tooltips). This drops that stray focus off the button for
    EVERY dialog at once — the Tools, Settings, Soft-proof, Profile Info,
    device-link, scanner-target, editor, … — so no per-dialog change is needed.
    Input fields keep their focus; a default button still answers Enter."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if (event.type() == QEvent.Type.Show
                and isinstance(obj, QWidget) and obj.isWindow()):
            defer_clear_button_focus(obj)
        return False


def reapply_groupbox_surface(root: QWidget) -> None:
    """Walk every QGroupBox descendant of `root` and re-apply the surface
    colour. Called from MainWindow.apply_theme on every theme switch
    because Polish only fires once per widget."""
    for gb in root.findChildren(QGroupBox):
        _apply_groupbox_surface(gb)


def icc_profile_paths() -> list[str]:
    """Common OS-level ICC/ICM profile directories for file-dialog sidebars."""
    import os
    import sys
    home = Path.home()
    if sys.platform == "darwin":
        return [
            "/Library/ColorSync/Profiles",
            "/System/Library/ColorSync/Profiles",
            str(home / "Library/ColorSync/Profiles"),
        ]
    if sys.platform.startswith("win"):
        # Honour %SystemRoot% — Windows is not always installed on C:.
        win = os.environ.get("SystemRoot", r"C:\Windows")
        paths = [str(Path(win) / "System32" / "spool" / "drivers" / "color")]
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            paths.append(str(Path(local) / "Microsoft" / "Windows" / "Color"))
        return paths
    return [
        "/usr/share/color/icc",
        "/usr/local/share/color/icc",
        str(home / ".local/share/icc"),   # modern XDG per-user dir (colord/GNOME)
        str(home / ".color/icc"),         # older Argyll/oyranos convention
    ]


def chromiq_root_dir() -> Path:
    """The ChromIQ working folder — the custom one when the user set one.

    ONE definition. `_sidebar_urls` below hard-coded ``Path.home() / "ChromIQ"``
    while `FileManager.root_dir` computed the same thing a second way, so the
    two disagreed the moment "custom output path" was set: the sidebar offered
    ~/ChromIQ while every file the app wrote went somewhere else.
    """
    from core.settings import AppSettings

    try:
        custom = AppSettings().get("custom_output_path", "")
    except Exception:      # noqa: BLE001 — a file dialog is never worth a crash
        custom = ""
    return Path(custom) if custom else Path.home() / "ChromIQ"


def _is_dir_safe(path: Path) -> bool:
    """`is_dir()` that cannot raise on an unmounted or unreadable path."""
    try:
        return path.is_dir()
    except OSError:
        return False


def _documents_dir() -> str:
    """The OS's own place for documents, for files that are NOT project data.

    A help-card PDF or a translation spreadsheet describes the app rather than
    a project, so it does not belong among `runs/` and `cal/` in the ChromIQ
    folder — but a bare home folder is nobody's filing cabinet either. The
    codebase already had this idiom for images (`softproof_dialog` uses
    `PicturesLocation`); this is the same thing for documents.
    """
    from PyQt6.QtCore import QStandardPaths

    loc = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation)
    return loc if loc and _is_dir_safe(Path(loc)) else str(Path.home())


def _default_start_dir(extra_path: str = "") -> str:
    """Where a ChromIQ browse starts when the caller does not say.

    NOT the home folder. Everything ChromIQ makes — charts, .ti2, .ti3, the
    finished ICC — lives under the working folder, so that is where a browse
    begins. Knut reported it against "Open Chart File (.ti2)"; driven, EIGHT of
    the nine file dialogs opened in $HOME and only Open Project was right.
    Home remains the last resort, for a first launch where the working folder
    does not exist yet.
    """
    for cand in (Path(extra_path) if extra_path else None, chromiq_root_dir()):
        if cand is not None:
            try:
                if cand.is_dir():
                    return str(cand)
            except OSError:                     # unreadable / unmounted path
                continue
    return str(Path.home())


def _sidebar_urls(extra_path: str = "", extra_paths: tuple | list = ()) -> list[QUrl]:
    # OS-correct, localized standard folders (Windows known-folders, localized
    # names on macOS/Linux) — Desktop, Images, Downloads, Documents — rather than
    # hard-coded English paths under home.
    from PyQt6.QtCore import QStandardPaths
    SL = QStandardPaths.StandardLocation
    candidates: list[Path] = []
    for loc in (SL.DesktopLocation, SL.PicturesLocation,
                SL.DownloadLocation, SL.DocumentsLocation):
        p = QStandardPaths.writableLocation(loc)
        if p:
            candidates.append(Path(p))
    candidates.append(chromiq_root_dir())        # the app's working folder
    if extra_path:
        candidates.append(Path(extra_path))
    for p in extra_paths:
        if p:
            candidates.append(Path(p))
    # De-dupe while keeping order, then drop any that don't exist.
    seen, urls = set(), []
    for p in candidates:
        s = str(p)
        if s not in seen and p.exists():
            seen.add(s)
            urls.append(QUrl.fromLocalFile(s))
    return urls


_NAV_BUTTONS = {
    "backButton":     QStyle.StandardPixmap.SP_ArrowBack,
    "forwardButton":  QStyle.StandardPixmap.SP_ArrowForward,
    "toParentButton": QStyle.StandardPixmap.SP_FileDialogToParent,
}

# Arrow drawn at _NAV_ARROW_SIZE, centred inside a _NAV_BTN_SIZE canvas.
# Qt places the canvas icon at top-left of the button, so centering is
# baked into the transparent padding of the canvas image.
_NAV_BTN_SIZE   = QSize(28, 28)
_NAV_ARROW_SIZE = QSize(16, 16)


def _nav_icon(icon: QIcon, color: QColor) -> QIcon:
    """Recolor icon and centre it on a transparent canvas matching button size."""
    raw = icon.pixmap(_NAV_ARROW_SIZE)
    # recolor
    colored = QPixmap(raw.size())
    colored.fill(Qt.GlobalColor.transparent)
    p = QPainter(colored)
    p.drawPixmap(0, 0, raw)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(colored.rect(), color)
    p.end()
    # centre on canvas
    canvas = QPixmap(_NAV_BTN_SIZE)
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    x = (_NAV_BTN_SIZE.width()  - _NAV_ARROW_SIZE.width())  // 2
    y = (_NAV_BTN_SIZE.height() - _NAV_ARROW_SIZE.height()) // 2
    p.drawPixmap(x, y, colored)
    p.end()
    return QIcon(canvas)


def _style_file_dialog_toolbar(dlg: QFileDialog) -> None:
    from core.settings import AppSettings
    from ui.theme import APPEARANCE_LIGHT, resolve_mode

    # Light mode's pale toolbar washes out the light arrows that read fine on
    # Dark mode's dark toolbar — use a near-black arrow there instead.
    mode = resolve_mode(AppSettings().get("appearance", "auto"))
    arrow_color = QColor("#1C1B18" if mode == APPEARANCE_LIGHT else "#e0e0e0")
    style = dlg.style()
    for name, sp in _NAV_BUTTONS.items():
        btn = dlg.findChild(QToolButton, name)
        if btn:
            btn.setIcon(_nav_icon(style.standardIcon(sp), arrow_color))
            btn.setIconSize(_NAV_BTN_SIZE)
            btn.setFixedSize(_NAV_BTN_SIZE)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    grip = dlg.findChild(QSizeGrip)
    if grip:
        grip.hide()


def _prefer_native_dialogs() -> bool:
    """User preference: use the OS-native file dialogs instead of ChromIQ's
    themed one (Settings → Behaviour). Native is much faster to populate on
    Windows, but — being the OS's own dialog — it can't carry our custom sidebar
    shortcuts or the injected image-preview pane, so those are skipped when on."""
    try:
        from core.settings import AppSettings
        return bool(AppSettings().get("use_native_file_dialogs", False))
    except Exception:
        return False


def open_file_dialog(
    parent: QWidget,
    title: str,
    name_filter: str = "",
    start_dir: str = "",
    extra_path: str = "",
    extra_paths: tuple | list = (),
    preview: bool = False,
    declutter_settings=None,
) -> str:
    """Open a Qt file dialog with sidebar shortcuts and proper file-type filtering.

    Non-matching files are hidden when name_filter is set. When ``preview`` is
    True, an image thumbnail of the highlighted file is shown beside the list
    (for picking images). With the native-dialogs setting on, the OS dialog is
    used instead (its own Quick Access + preview pane; our custom sidebar and
    preview don't apply).

    When ``declutter_settings`` is an AppSettings, the picked file's folder is
    tidied into the v2 sub-folder layout before returning (#36, Knut), so a load
    button opening a legacy flat project neatens it first. No-op when the
    ``declutter_on_load`` preference is off or nothing matches.

    Returns the selected file path, or an empty string if cancelled.
    """
    native = _prefer_native_dialogs()
    dlg = QFileDialog(parent, title, start_dir or _default_start_dir(extra_path))
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        _style_file_dialog_toolbar(dlg)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
    if name_filter:
        dlg.setNameFilter(name_filter)
    if not native:
        # ALWAYS, even with no extensions to match on: the proxy is what
        # decides the ORDER (see `NameOrderProxy`), and the order must not
        # depend on whether the caller's filter happened to contain a `*.`.
        dlg.setProxyModel(
            _ExtensionFilterProxy(_parse_extensions(name_filter) if name_filter
                                  else [], dlg))
        dlg.setSidebarUrls(_sidebar_urls(extra_path, extra_paths))
        _open_up_sidebar(dlg)
        if preview:
            _attach_image_preview(dlg)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        picked = files[0] if files else ""
        if picked and declutter_settings is not None:
            from core.file_manager import maybe_declutter_on_load
            maybe_declutter_on_load(picked, declutter_settings)
        return picked
    return ""


def _open_up_sidebar(dlg: "QFileDialog") -> None:
    """Give the non-native file dialog's sidebar room to breathe: Qt's
    default splitter leaves the shortcuts column so narrow that the location
    names are cut off and every dialog needs a manual resize first (Basti).
    Widens the sidebar to a readable width and gives the whole dialog a
    comfortable default size, while the user can still drag both."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QSplitter
    if dlg.width() < 900:
        dlg.resize(980, max(dlg.height(), 620))

    def _apply() -> None:
        sp = dlg.findChild(QSplitter)
        if sp is not None and sp.count() >= 2:
            side = 230
            sp.setSizes([side, max(dlg.width() - side, 400)])

    # The splitter only takes real sizes once the dialog has laid itself
    # out — exec() runs the event loop, so a zero-timer lands right after
    # the dialog appears.
    QTimer.singleShot(0, _apply)


def _attach_image_preview(dlg: "QFileDialog") -> None:
    """Add a live image-thumbnail pane to a non-native QFileDialog.

    QFileDialog's body is a QGridLayout; we drop a preview label into the column
    to the right of the file list and refresh it on ``currentChanged``. Loading
    is done lazily off the highlighted path (a QPixmap of the whole file) and
    scaled down — fine for the modest sizes a user browses one at a time.
    """
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QGridLayout, QLabel
    layout = dlg.layout()
    if not isinstance(layout, QGridLayout):
        return
    holder = QLabel(dlg)
    holder.setObjectName("imagePreview")
    # Fixed width so the preview doesn't eat the extra width — that goes to the
    # file list, which is what should grow when the dialog is widened.
    holder.setFixedWidth(300)
    holder.setMinimumHeight(260)
    holder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    holder.setText(tr("No preview"))
    holder.setStyleSheet(
        "QLabel#imagePreview { border: 1px solid palette(mid); color: palette(mid);"
        " background: palette(base); }")
    # Span the file-list rows on the far right.
    layout.addWidget(holder, 1, layout.columnCount(), layout.rowCount() - 1, 1)
    # Only widen — the file list is roomy alongside the fixed-width preview;
    # keep the standard file-dialog height (don't force it taller).
    dlg.setMinimumWidth(1000)
    dlg.resize(1280, dlg.height())

    def _show(path: str) -> None:
        if path and Path(path).is_file():
            pm = QPixmap(path)
            if not pm.isNull():
                holder.setPixmap(pm.scaled(
                    holder.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                return
        holder.setPixmap(QPixmap())
        holder.setText(tr("No preview"))

    dlg.currentChanged.connect(_show)


def open_files_dialog(
    parent: QWidget,
    title: str,
    name_filter: str = "",
    start_dir: str = "",
    extra_path: str = "",
    extra_paths: tuple | list = (),
    preview: bool = False,
    declutter_settings=None,
) -> list[str]:
    """Multi-file variant of :func:`open_file_dialog`.

    Shares the same OS-correct sidebar shortcuts; when ``preview`` is True an
    image thumbnail of the highlighted file is shown beside the list (for
    picking images). ``declutter_settings`` tidies the picked files' folder into
    the v2 layout before returning (#36). Returns the list of selected paths, or
    an empty list if cancelled.
    """
    native = _prefer_native_dialogs()
    dlg = QFileDialog(parent, title, start_dir or _default_start_dir(extra_path))
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        _style_file_dialog_toolbar(dlg)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
    if name_filter:
        dlg.setNameFilter(name_filter)
    if not native:
        # ALWAYS, even with no extensions to match on: the proxy is what
        # decides the ORDER (see `NameOrderProxy`), and the order must not
        # depend on whether the caller's filter happened to contain a `*.`.
        dlg.setProxyModel(
            _ExtensionFilterProxy(_parse_extensions(name_filter) if name_filter
                                  else [], dlg))
        dlg.setSidebarUrls(_sidebar_urls(extra_path, extra_paths))
        _open_up_sidebar(dlg)
        if preview:
            _attach_image_preview(dlg)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        picked = list(dlg.selectedFiles())
        if picked and declutter_settings is not None:
            from core.file_manager import maybe_declutter_on_load
            maybe_declutter_on_load(picked[0], declutter_settings)
        return picked
    return []


def save_file_dialog(
    parent: QWidget,
    title: str,
    name_filter: str = "",
    start_path: str = "",
    extra_path: str = "",
    extra_paths: tuple | list = (),
) -> str:
    """Open a Qt **save** file dialog with sidebar shortcuts.

    ``start_path`` may be a directory or a full path with a default
    filename — if it points at an existing directory the dialog opens
    there, otherwise it pre-selects the file inside its parent dir.
    Returns the chosen path, or an empty string if cancelled.
    """
    # A START FOLDER THAT DOES NOT EXIST IS NOT A START FOLDER. Callers hand in
    # a suggested full path; `p.parent` was passed straight to QFileDialog with
    # no existence check, so a caller naming a folder nothing ever creates —
    # the spot-read dialog's `~/spot-readings/` is the one in the tree — landed
    # the user somewhere the platform chose. Fall back deliberately instead.
    #
    # AND THE FOLDER IS NOT THE PARENT WIDGET. The line below used to be
    # `parent = p.parent`, which overwrote this function's own `parent`
    # argument with a `Path` — so `QFileDialog(parent, …)` raised
    # `TypeError: argument 1 has unexpected type 'PosixPath'` for EVERY caller
    # that suggests a file name rather than a folder, which is all twelve of
    # them. Every "Save as…" in the app was dead from 4.1.3-beta.16 until Knut
    # reported it against the help card's PDF (2026-08-27). The local is named
    # apart from the argument now, and `tests/test_native_file_dialogs.py`
    # asserts the dialog's parent is the widget it was given.
    p = Path(start_path) if start_path else None
    if p is not None and p.is_dir():
        start_dir, default_name = str(p), ""
    elif p is not None:
        parent_dir = p.parent
        start_dir = str(parent_dir) if _is_dir_safe(parent_dir) else _documents_dir()
        default_name = p.name
    else:
        start_dir, default_name = _documents_dir(), ""
    native = _prefer_native_dialogs()
    dlg = QFileDialog(parent, title, start_dir)
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        _style_file_dialog_toolbar(dlg)
    dlg.setFileMode(QFileDialog.FileMode.AnyFile)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    if name_filter:
        dlg.setNameFilter(name_filter)
    if not native:
        # Ordering only — Qt's own name filtering happens in the source
        # QFileSystemModel and still applies. A Save dialog listed names in a
        # different order from an Open dialog until this was added.
        dlg.setProxyModel(NameOrderProxy(dlg))
    if default_name:
        dlg.selectFile(default_name)
    if not native:
        dlg.setSidebarUrls(_sidebar_urls(extra_path, extra_paths))
        _open_up_sidebar(dlg)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        files = dlg.selectedFiles()
        return files[0] if files else ""
    return ""


def open_dir_dialog(
    parent: QWidget,
    title: str,
    start_dir: str = "",
    extra_path: str = "",
) -> str:
    """Open a Qt directory dialog with sidebar shortcuts.

    Returns the selected directory path, or an empty string if cancelled.
    """
    native = _prefer_native_dialogs()
    dlg = QFileDialog(parent, title, start_dir or _default_start_dir(extra_path))
    dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
    dlg.setFileMode(QFileDialog.FileMode.Directory)
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        _style_file_dialog_toolbar(dlg)
        dlg.setProxyModel(NameOrderProxy(dlg))
        import sys as _sys
        urls = _sidebar_urls(extra_path)
        if _sys.platform == "darwin":
            urls.append(QUrl.fromLocalFile("/Applications"))
        dlg.setSidebarUrls(urls)
        _open_up_sidebar(dlg)
    if dlg.exec() == QFileDialog.DialogCode.Accepted:
        dirs = dlg.selectedFiles()
        return dirs[0] if dirs else ""
    return ""


def load_folder_icon(name: str) -> QIcon:
    """Load a colored folder icon from assets/folder/<name>.png.

    For the plain "folder" icon (used in the Preferences dialog), if the
    active palette is light, take the same PNG and re-tint every
    non-transparent pixel to #22211f so the shape stays identical to the
    coloured variants — just in a dark hue that reads on the warm-white
    Preferences background. The tab-specific coloured variants
    (folder_build, folder_print, …) are kept as-is since their hues
    already read on either background.

    **Under Neutral every variant is recoloured to ACTION**, by the same
    SourceIn trick. The five tab-coded PNGs are one hue of line art each, so
    repainting the alpha mask gives exactly what the handoff asks for — the ten
    baked-hue files collapsing to one set — without shipping a sixth file or
    waiting for the assets job. Light and Dark still get the PNG as drawn.

    Falls back to the OS system folder icon if no asset is found.
    """
    from core.resource_path import resource_path
    from PyQt6.QtGui import QGuiApplication

    dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
    phys = round(20 * dpr)

    src = resource_path(f"assets/folder/{name}.png")
    src_px = QPixmap(str(src))
    if not src_px.isNull():
        scaled = src_px.scaled(phys, phys,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        # Light-theme: recolour the bare "folder" icon to #22211f. Compose
        # the new colour using SourceIn so the icon's existing alpha mask
        # (the line work) is preserved exactly — every line that was
        # rendered in the dark PNG is repainted in the new colour.
        from ui.theme import APPEARANCE_NEUTRAL, active_mode
        if (name == "folder" and _has_light_ground()) \
                or active_mode() == APPEARANCE_NEUTRAL:
            from PyQt6.QtGui import QImage, QPainter
            img = scaled.toImage().convertToFormat(
                QImage.Format.Format_ARGB32_Premultiplied
            )
            painter = QPainter(img)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn
            )
            painter.fillRect(img.rect(), QColor(_dark_glyph_ink()))
            painter.end()
            recoloured = QPixmap.fromImage(img)
            recoloured.setDevicePixelRatio(dpr)
            return QIcon(recoloured)
        scaled.setDevicePixelRatio(dpr)
        return QIcon(scaled)
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)


def _has_light_ground() -> bool:
    """True when the appearance on screen paints a PALE ground.

    Both callers use this to choose between two shipped assets — the folder
    glyph recoloured for a pale ground, and the ``*_dark`` sibling of a preset
    icon. The question they are really asking is about the GROUND, not about
    Light: it was written as ``is_light()``, which answered *no* for Neutral
    and put light line art on a light-grey panel — an invisible folder button,
    the icon form of the theme's most-repeated trap. ``has_dark_ground`` is the
    one place that knows, and a fourth appearance is a row in its table.
    """
    from ui.theme import active_mode, has_dark_ground
    return not has_dark_ground(active_mode())


def _dark_glyph_ink() -> str:
    """The ink a glyph is recoloured to on a pale ground, per appearance."""
    from ui.theme import APPEARANCE_NEUTRAL, active_mode
    from ui import neutral_styles
    if active_mode() == APPEARANCE_NEUTRAL:
        return neutral_styles.NM_TEXT_MAIN
    return "#22211f"        # the light theme's wordmark ink, unchanged


def load_preset_icon(name: str) -> QIcon:
    """Load a preset +/- icon, switching to the *_dark variant in light mode.

    `name` is the bare asset stem ("plus" or "minus"). On a light palette,
    we load the *_dark.svg sibling so the glyph reads on the warm-white
    Presets row.
    """
    from core.resource_path import resource_path
    stem = f"{name}_dark" if _has_light_ground() else name
    return QIcon(str(resource_path(f"assets/{stem}.svg")))


def load_tinted_folder_icon(color: str, size: int = 22) -> QIcon:
    """The standard folder glyph tinted in an arbitrary accent ``color``.

    Repaints every opaque pixel of ``folder.png`` via SourceIn, preserving the
    icon's alpha mask (same trick :func:`load_folder_icon` uses for the
    light-theme recolour). Spectrum accents read on both COLOURED themes, so no
    light/dark variant is needed. Used where a browse button should match its
    dialog's masthead accent rather than a tab-coded variant.

    Under Neutral there is one accent, so every tinted glyph in the app —
    browse buttons, reveal buttons, the preset star's folder twin — comes out
    of here in ACTION. Light and Dark get exactly the colour they asked for."""
    from core.resource_path import resource_path
    from ui.theme import accent_for
    color = accent_for(color)
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter

    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    phys = round(size * dpr)
    src_px = QPixmap(str(resource_path("assets/folder/folder.png")))
    if src_px.isNull():
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
    scaled = src_px.scaled(phys, phys,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    img = scaled.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(img)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(img.rect(), QColor(color))
    painter.end()
    out = QPixmap.fromImage(img)
    out.setDevicePixelRatio(dpr)
    return QIcon(out)


def load_reveal_folder_icon(color: str, size: int = 22) -> QIcon:
    """A distinct “reveal in the file manager” glyph — a folder with a small
    arrow springing out of it — painted in an accent ``color`` (Knut). Kept
    visually different from the plain folder glyph used to *load* a file, so
    the two buttons don't read as the same action. One accent under Neutral,
    see :func:`load_tinted_folder_icon`."""
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath, QPen
    from ui.theme import accent_for
    color = accent_for(color)

    dpr = QGuiApplication.primaryScreen().devicePixelRatio()
    phys = round(size * dpr)
    img = QImage(phys, phys, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    c = QColor(color)
    s = phys
    pen = QPen(c)
    pen.setWidthF(max(1.4, s * 0.075))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    # Folder body (lower-left), leaving room for the arrow top-right.
    fx, fy, fw, fh = s * 0.12, s * 0.40, s * 0.60, s * 0.42
    tab = QPainterPath()
    tab.moveTo(fx, fy)
    tab.lineTo(fx + fw * 0.34, fy)
    tab.lineTo(fx + fw * 0.46, fy - s * 0.09)
    tab.lineTo(fx + fw, fy - s * 0.09)
    p.drawPath(tab)
    p.drawRoundedRect(int(fx), int(fy - s * 0.09), int(fw), int(fh + s * 0.09),
                      int(s * 0.05), int(s * 0.05))
    # Arrow springing out to the upper-right.
    a0x, a0y = s * 0.52, s * 0.42
    a1x, a1y = s * 0.86, s * 0.14
    p.drawLine(int(a0x), int(a0y), int(a1x), int(a1y))
    head = QPainterPath()
    head.moveTo(a1x - s * 0.16, a1y + s * 0.02)
    head.lineTo(a1x, a1y)
    head.lineTo(a1x - s * 0.02, a1y + s * 0.16)
    p.drawPath(head)
    p.end()
    out = QPixmap.fromImage(img)
    out.setDevicePixelRatio(dpr)
    return QIcon(out)


def set_reveal_folder_icon(btn: QPushButton, color: str) -> None:
    """Stamp the reveal-folder glyph (tab accent) and tag for theme refresh."""
    from PyQt6.QtCore import QSize
    btn.setIcon(load_reveal_folder_icon(color))
    btn.setIconSize(QSize(20, 20))
    btn.setProperty("themed_reveal_icon", color)


def load_magenta_folder_icon() -> QIcon:
    """The standard folder glyph tinted in the app's spectrum magenta — used by
    the "open an existing profile" button beside the built-in-presets star, so
    the two read as a matched pair (#70)."""
    from ui.styles import SPEC_MAGENTA
    return load_tinted_folder_icon(SPEC_MAGENTA, size=22)


def defer_clear_button_focus(_root=None) -> None:
    """Drop the initial focus off any button Qt auto-focused when a tab/dialog is
    shown, so the space bar can't activate it before the user clicks or tabs to
    it. Input fields keep their focus; a dialog's default button still answers
    Enter, since that doesn't need focus — only the stray space-activation goes
    away. (Knut: space was toggling modes / opening file pickers / popping
    tooltips on fresh tab or dialog entry.)

    Run across a few passes: a dialog's *default* button re-grabs focus during
    window activation, so a single deferred clear can fire too early to stick.
    Each pass only clears a button, never an input the user has since focused."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QAbstractButton, QApplication

    def _clear() -> None:
        fw = QApplication.focusWidget()
        if isinstance(fw, QAbstractButton):
            fw.clearFocus()
    for _delay in (0, 40, 150):
        QTimer.singleShot(_delay, _clear)


class PatchGridButton(QToolButton):
    """A small grid-of-patches glyph button, painted in a given accent colour.

    Mirrors ``BuiltinPresetButton``'s painted-glyph approach (crisp on Retina,
    no PNG asset) and its 40×40 / ``#tooltip_btn`` styling, so it sits as a
    matched sibling beside the folder and star buttons. The 3×3 grid reads as a
    chart patch set / layout — used for the "load a chart layout" buttons on the
    Create Chart (magenta) and Print Chart (amber) tabs (#70, Knut)."""

    GRID_FRAC = 0.60   # glyph box as a fraction of the button
    GRID_N    = 3      # squares per side

    def __init__(self, color: str, parent: QWidget | None = None, *,
                 page: bool = False) -> None:
        super().__init__(parent)
        self._color = color
        # page=True draws a folded-corner document around a smaller grid — "load a
        # chart PAGE" (Knut's option C, used on the Print + Measure tabs).
        self._page = page
        self.setObjectName("tooltip_btn")
        self.setFixedSize(QSize(40, 40))
        # Icon-only, mouse-operated: never take keyboard focus, so the space bar
        # can't activate it just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def set_appearance(self, mode: str) -> None:
        pass  # accent colour is theme-independent — nothing to repaint

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = float(min(self.width(), self.height()))
        color = QColor(self._color)
        if not self.isEnabled():
            color.setAlpha(70)      # parked (e.g. FROM PROFILE GAMUT active)
        elif not self._hover:
            color.setAlpha(230)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        if self._page:
            # A document with a folded top-right corner, around a smaller grid
            # (Knut's option C).
            pw, ph = s * 0.54, s * 0.68
            ear = s * 0.15
            x0, y0 = cx - pw / 2.0, cy - ph / 2.0
            x1, y1 = x0 + pw, y0 + ph
            pen = QPen(color, max(1.2, s * 0.05))
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            page = QPainterPath()
            page.moveTo(x0, y0)
            page.lineTo(x1 - ear, y0)
            page.lineTo(x1, y0 + ear)
            page.lineTo(x1, y1)
            page.lineTo(x0, y1)
            page.closeSubpath()
            p.drawPath(page)
            fold = QPainterPath()          # the little folded-corner triangle
            fold.moveTo(x1 - ear, y0)
            fold.lineTo(x1 - ear, y0 + ear)
            fold.lineTo(x1, y0 + ear)
            p.drawPath(fold)
            self._draw_grid(p, cx, cy + s * 0.02, s * 0.34, color)
        else:
            self._draw_grid(p, cx, cy, s * self.GRID_FRAC, color)
        p.end()

    def _draw_grid(self, p: "QPainter", cx: float, cy: float, side: float,
                   color: "QColor") -> None:
        gap = side * 0.16
        cell = (side - (self.GRID_N - 1) * gap) / self.GRID_N
        x0, y0 = cx - side / 2.0, cy - side / 2.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        rad = cell * 0.22
        for r in range(self.GRID_N):
            for c in range(self.GRID_N):
                p.drawRoundedRect(
                    QRectF(x0 + c * (cell + gap), y0 + r * (cell + gap), cell, cell),
                    rad, rad)


class StackedPagesButton(QToolButton):
    """Two stacked document pages, the front one carrying a small patch grid,
    painted in a given accent colour — "reopen a profiling project you started
    earlier". The front page **fully occludes** the one behind it (rendered on a
    transparent layer with a clear-composition knockout, so there is no
    see-through — Sebastian). Same flat 40×40 / ``#tooltip_btn`` styling as the
    other icon-only load buttons."""

    FRAC = 0.72
    GRID_N = 2

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setObjectName("tooltip_btn")
        self.setFixedSize(QSize(40, 40))
        # Icon-only, mouse-operated: never take keyboard focus, so the space bar
        # can't activate it just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def set_appearance(self, mode: str) -> None:
        pass

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _page_path(x: float, y: float, w: float, h: float, fold: float
                   ) -> QPainterPath:
        pp = QPainterPath()
        pp.moveTo(x, y)
        pp.lineTo(x + w - fold, y)
        pp.lineTo(x + w, y + fold)
        pp.lineTo(x + w, y + h)
        pp.lineTo(x, y + h)
        pp.closeSubpath()
        return pp

    def _draw_page(self, gp: QPainter, x: float, y: float, w: float, h: float,
                   fold: float, color: QColor, sw: float, grid_n: int = 0) -> None:
        _p = QPen(color)
        _p.setWidthF(sw)
        _p.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        _p.setCapStyle(Qt.PenCapStyle.RoundCap)
        gp.setPen(_p)
        gp.setBrush(Qt.BrushStyle.NoBrush)
        gp.drawPath(self._page_path(x, y, w, h, fold))
        # Folded corner.
        corner = QPainterPath()
        corner.moveTo(x + w - fold, y)
        corner.lineTo(x + w - fold, y + fold)
        corner.lineTo(x + w, y + fold)
        gp.drawPath(corner)
        if grid_n:
            gs = w * 0.22
            gg = w * 0.13
            gw = grid_n * gs + (grid_n - 1) * gg
            gx = x + (w - gw) / 2
            gy = y + h * 0.36
            gp.setPen(Qt.PenStyle.NoPen)
            gp.setBrush(color)
            for r in range(grid_n):
                for c in range(grid_n):
                    gp.drawRoundedRect(
                        QRectF(gx + c * (gs + gg), gy + r * (gs + gg), gs, gs),
                        gs * 0.24, gs * 0.24)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        dpr = self.devicePixelRatioF()
        layer = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        layer.setDevicePixelRatio(dpr)
        layer.fill(Qt.GlobalColor.transparent)
        gp = QPainter(layer)
        gp.setRenderHint(QPainter.RenderHint.Antialiasing)

        box = min(self.width(), self.height()) * self.FRAC
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        color = QColor(self._color)
        if not self._hover:
            color.setAlpha(230)
        sw = 1.7
        pw = box * 0.52
        ph = box * 0.64
        fold = pw * 0.26
        dx = box * 0.11
        dy = box * 0.10
        # Back page (up-right).
        self._draw_page(gp, cx - pw / 2 + dx, cy - ph / 2 - dy, pw, ph, fold,
                        color, sw)
        # Knock out the front-page silhouette (+ a gap ring) so the back page
        # can't show through, then draw the front page with its grid.
        fx = cx - pw / 2 - dx
        fy = cy - ph / 2 + dy
        front = self._page_path(fx, fy, pw, ph, fold)
        gp.save()
        gp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        clear_pen = QPen(QColor(0, 0, 0, 255))
        clear_pen.setWidthF(2.6)
        gp.setPen(clear_pen)
        gp.setBrush(QColor(0, 0, 0, 255))
        gp.drawPath(front)
        gp.restore()
        self._draw_page(gp, fx, fy, pw, ph, fold, color, sw, grid_n=self.GRID_N)
        gp.end()

        p = QPainter(self)
        p.drawPixmap(0, 0, layer)
        p.end()


class StripReadButton(QToolButton):
    """A single strip (column) of patches with a scan arrow above it, painted in
    a given accent colour — "read a strip". The Measure-tab sibling of
    :class:`PatchGridButton`: same flat 40×40 / ``#tooltip_btn`` styling (just
    the glyph at rest, a faint highlight on hover), so the load buttons across
    tabs read as one family. Used for "load a chart (.ti2) to measure"
    (Sebastian)."""

    FRAC = 0.64
    N_PATCHES = 4

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setObjectName("tooltip_btn")
        self.setFixedSize(QSize(40, 40))
        # Icon-only, mouse-operated: never take keyboard focus, so the space bar
        # can't activate it just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def set_appearance(self, mode: str) -> None:
        pass  # accent colour is theme-independent

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) * self.FRAC
        cx = self.width() / 2.0
        y0 = (self.height() - side) / 2.0
        color = QColor(self._color)
        if not self._hover:
            color.setAlpha(230)
        # Column of patches (lower ~70%).
        cw = side * 0.30
        ch = side * 0.14
        gap = side * 0.045
        top = y0 + side * 0.30
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        rad = cw * 0.22
        for i in range(self.N_PATCHES):
            p.drawRoundedRect(QRectF(cx - cw / 2, top + i * (ch + gap), cw, ch),
                              rad, rad)
        # Scan arrow above, pointing down into the strip.
        pen = QPen(color)
        pen.setWidthF(1.9)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        a_top = y0 + side * 0.02
        a_bot = top - side * 0.05
        p.drawLine(QPointF(cx, a_top), QPointF(cx, a_bot))
        head = side * 0.11
        p.drawLine(QPointF(cx, a_bot), QPointF(cx - head, a_bot - head))
        p.drawLine(QPointF(cx, a_bot), QPointF(cx + head, a_bot - head))
        p.end()


class MeasuredChartButton(QToolButton):
    """A grid-of-patches glyph with a checkmark, painted in a given accent
    colour — the "measured chart" sibling of :class:`PatchGridButton`.

    The plain grid means "a chart"; the tick means "…that has been measured",
    so it reads as a measurement file (.ti3 / i1Profiler .txt). Used for the
    "load measurement data" buttons on the Build Profile tab (cyan), matching
    the icon-only load buttons on Create Chart / Print / Measure (Sebastian).
    Same flat 40×40 / ``#tooltip_btn`` styling as its siblings: nothing but the
    glyph at rest, a faint highlight on hover."""

    GRID_FRAC = 0.56   # a touch smaller than PatchGridButton to leave room
    GRID_N    = 3

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setObjectName("tooltip_btn")
        self.setFixedSize(QSize(40, 40))
        # Icon-only, mouse-operated: never take keyboard focus, so the space bar
        # can't activate it just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def set_appearance(self, mode: str) -> None:
        pass  # accent colour is theme-independent

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) * self.GRID_FRAC
        gap  = side * 0.16
        cell = (side - (self.GRID_N - 1) * gap) / self.GRID_N
        # Nudge the grid up-left so the tick sits in the freed bottom-right.
        x0 = (self.width() - side) / 2.0 - self.width() * 0.05
        y0 = (self.height() - side) / 2.0 - self.height() * 0.05
        color = QColor(self._color)
        if not self._hover:
            color.setAlpha(230)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        rad = cell * 0.22
        for r in range(self.GRID_N):
            for c in range(self.GRID_N):
                x = x0 + c * (cell + gap)
                y = y0 + r * (cell + gap)
                p.drawRoundedRect(QRectF(x, y, cell, cell), rad, rad)
        # Checkmark, bottom-right, over the grid.
        w = self.width()
        h = self.height()
        pen = QPen(color)
        pen.setWidthF(2.2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        tick = QPainterPath()
        tick.moveTo(w * 0.55, h * 0.64)
        tick.lineTo(w * 0.66, h * 0.77)
        tick.lineTo(w * 0.86, h * 0.48)
        p.drawPath(tick)
        p.end()


def set_folder_icon(btn: QPushButton, name: str) -> None:
    """Set a folder-glyph icon on `btn` and tag it for live theme refresh."""
    btn.setIcon(load_folder_icon(name))
    btn.setProperty("themed_folder_icon", name)


def set_preset_icon(btn: QPushButton, name: str) -> None:
    """Set a preset +/- icon on `btn` and tag it for live theme refresh."""
    btn.setIcon(load_preset_icon(name))
    btn.setProperty("themed_preset_icon", name)


def apply_themed_icons(root: QWidget) -> None:
    """Reload every theme-aware icon under `root`.

    Walks all QPushButtons and re-runs the appropriate loader for buttons
    tagged by set_folder_icon / set_preset_icon / make_browse_button. Call
    from MainWindow.apply_theme so palette-dependent icons repaint without
    requiring an app restart.
    """
    for btn in root.findChildren(QPushButton):
        folder_name = btn.property("themed_folder_icon")
        if folder_name:
            btn.setIcon(load_folder_icon(str(folder_name)))
            continue
        preset_name = btn.property("themed_preset_icon")
        if preset_name:
            btn.setIcon(load_preset_icon(str(preset_name)))
            continue
        reveal_color = btn.property("themed_reveal_icon")
        if reveal_color:
            btn.setIcon(load_reveal_folder_icon(str(reveal_color)))


def tint_dialog_primary(dlg: "QWidget", color: str) -> None:
    """Stamp tab accent color onto every QPushButton#primary inside a dialog (v2 only).

    Safe to call on any dialog — no-op if no primary buttons are present.

    **One accent under Neutral, and the label flips with it.** This is the
    single busiest accent site in the app — sixty-odd call sites across every
    tab — so it is also the one place where getting the pair wrong is loudest:
    ``#0a0a0a`` on an ACTION fill is black on black. Neutral gets ON_ACTION
    (15.53:1), the theme's one sanctioned light-on-dark pairing, and it is a
    fill rather than inverted page text. Light and Dark are untouched.
    """
    from ui.theme import accent_for, active_mode
    mode = active_mode()
    color = accent_for(color, mode)
    label = primary_label(mode)
    hover = primary_hover(color, mode)
    for btn in dlg.findChildren(QPushButton):
        if btn.objectName() == "primary":
            # APPEND, never replace. fit_button_width writes a min-width rule
            # into the button's own style sheet — the only thing the application
            # sheet's own min-width respects — and replacing the sheet here threw
            # it away, so the button collapsed to 72 px and clipped its label
            # again (Knut, #131 2026-07-28, the third report of this).
            existing = btn.styleSheet() or ""
            btn.setStyleSheet(
                existing
                + f"\nQPushButton {{ background: {color}; border: 1px solid {color};"
                f" color: {label}; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
            )
            # …and re-assert the width afterwards, so the order of the two never
            # matters again.
            fit_button_width(btn)


def primary_label(mode: "str | None" = None) -> str:
    """The label colour on an accent-FILLED primary button.

    Near-black on the coloured accents, which are all light enough to carry it.
    ACTION is not: Neutral's label is ON_ACTION at 15.53:1 — the one
    light-on-dark pairing the theme allows, and it is a fill, not inverted
    page text.
    """
    from ui.theme import APPEARANCE_NEUTRAL, active_mode
    if (mode or active_mode()) == APPEARANCE_NEUTRAL:
        from ui import neutral_styles
        return neutral_styles.NM_ON_ACTION
    return "#0a0a0a"


def primary_hover(accent: str, mode: "str | None" = None,
                  factor: float = 0.82) -> str:
    """The hover fill for an accent-filled primary button.

    The coloured appearances darken the accent by ``factor``. ACTION has almost
    no room left below it — 0.82 x #101010 is #0d0d0d, a change nobody can see —
    so Neutral steps to TEXT_DIM instead, which is a visible move in the only
    direction this theme has (rule 1: never lighter than its ground).
    """
    from ui.theme import APPEARANCE_NEUTRAL, active_mode
    if (mode or active_mode()) == APPEARANCE_NEUTRAL:
        from ui import neutral_styles
        return neutral_styles.NM_TEXT_DIM
    r, g, b = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
    return "#{:02x}{:02x}{:02x}".format(int(r * factor), int(g * factor),
                                        int(b * factor))


def disabled_primary_qss(accent: str, mode: "str | None" = None) -> str:
    """The ``QPushButton:disabled`` rule for an accent-filled primary button.

    Four tool dialogs wrote the same three literals for this — a pale fill and
    a pale label on light, a near-black fill and a mid-grey label on dark. A
    third appearance took the dark branch and put a near-black block on a
    light-grey window: the darkest thing in the dialog was the button you
    cannot press.

    Neutral's answer is the handoff's shape, not a value: **no fill and a
    dashed edge**. Light and Dark get exactly the rule they have always had.
    """
    from ui.theme import APPEARANCE_NEUTRAL, active_mode, is_light
    mode = mode or active_mode()
    if mode == APPEARANCE_NEUTRAL:
        from ui import neutral_styles
        return (f"QPushButton:disabled {{ background: transparent;"
                f" border: 1px dashed {neutral_styles.NM_DISABLED};"
                f" color: {neutral_styles.NM_DISABLED}; }}")
    light = mode == "light" if mode else is_light()
    dis_bg = "#e8e6e1" if light else "#1e1e1e"
    dis_fg = "#a8a4a0" if light else "#484848"
    return (f"QPushButton:disabled {{ background: {dis_bg};"
            f" border: 1px solid {accent}; color: {dis_fg}; }}")


def banner_qss(accent: str, wash: str, mode: "str | None" = None,
               kind: str = "warn") -> str:
    """A one-line info / warning / error banner, as a full ``QLabel`` rule.

    ``accent`` is the hue the two coloured appearances use for the text and the
    edge; ``wash`` the ``rgba(...)`` fill behind it. Both are handed back
    unchanged there.

    Neutral has no hue to spend, so the banner is told apart by SHAPE — the
    handoff's escalation: a warning gains a 1px underline, a failure a 3px left
    bar. The text is dark ink on the raised surface either way; nothing here is
    allowed to be faint, because faint means disabled.
    """
    from ui.theme import APPEARANCE_NEUTRAL, active_mode
    if (mode or active_mode()) != APPEARANCE_NEUTRAL:
        return (f"QLabel {{ background: {wash}; color: {accent};"
                f" border: 1px solid {accent}; border-radius: 4px;"
                f" padding: 8px 10px; }}")
    from ui import neutral_styles as _n
    mark = (f" border-left: 3px solid {_n.NM_ACTION};" if kind == "error"
            else f" border-bottom: 2px solid {_n.NM_ACTION};")
    return (f"QLabel {{ background: {_n.NM_BG_SURFACE}; color: {_n.NM_TEXT_MAIN};"
            f" border: 1px solid {_n.NM_BORDER};{mark}"
            f" border-radius: 4px; padding: 8px 10px; }}")


def load_refresh_icon(name: str) -> QIcon:
    """Load a colored refresh icon from assets/refresh/<name>.png.

    The five tab-coded variants are recoloured to ACTION under Neutral, the
    same way :func:`load_folder_icon` handles the folder set.

    Falls back to the OS browser-reload icon if the file is not found.
    """
    from core.resource_path import resource_path
    from PyQt6.QtGui import QGuiApplication
    from ui.theme import APPEARANCE_NEUTRAL, active_mode
    px = QPixmap(str(resource_path(f"assets/refresh/{name}.png")))
    if not px.isNull():
        dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
        phys = round(20 * dpr)
        scaled = px.scaled(phys, phys,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        if active_mode() == APPEARANCE_NEUTRAL:
            from PyQt6.QtGui import QImage, QPainter
            img = scaled.toImage().convertToFormat(
                QImage.Format.Format_ARGB32_Premultiplied)
            painter = QPainter(img)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(img.rect(), QColor(_dark_glyph_ink()))
            painter.end()
            scaled = QPixmap.fromImage(img)
        scaled.setDevicePixelRatio(dpr)
        return QIcon(scaled)
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)


#: Property keys used by :func:`set_ink` to remember what a label asked for.
_INK_SRC   = "_chromiq_ink_src"
_INK_LEVEL = "_chromiq_ink_level"
_INK_EXTRA = "_chromiq_ink_extra"


def set_ink(widget, colour: str, extra: str = "", level: str = "main") -> None:
    """Colour ``widget``'s text, remembering the value it asked for.

    ``colour`` is the Light/Dark value — a status green, a warning amber, a
    magenta link, a ``#909090`` note. Light and Dark get it back unchanged; in
    Neutral it becomes dark ink at ``level`` (``"main"`` / ``"dim"`` /
    ``"faint"``), because in a colourless theme those meanings are carried by
    the WORDS. None of the three levels is faint enough to read as disabled —
    the tertiary value is 8.83:1 on the panel.

    ``extra`` is appended to the stylesheet verbatim, so a size or weight the
    label already had survives (``" font-size: 11px;"``).

    The value asked for is stored on the widget, so :func:`reapply_ink` can
    re-resolve it when the appearance changes under a window that is already
    open — a theme previewed from inside Preferences, or the apply_theme
    broadcast reaching a long-lived tab.
    """
    from ui.theme import ink_for
    widget.setProperty(_INK_SRC, colour)
    widget.setProperty(_INK_LEVEL, level)
    widget.setProperty(_INK_EXTRA, extra)
    widget.setStyleSheet(f"color: {ink_for(colour, level=level)};{extra}")


def reapply_ink(root, mode: str | None = None) -> None:
    """Re-resolve every :func:`set_ink` colour under ``root`` for ``mode``."""
    from ui.theme import ink_for
    for wgt in root.findChildren(QWidget):
        src = wgt.property(_INK_SRC)
        if not src:
            continue
        level = wgt.property(_INK_LEVEL) or "main"
        extra = wgt.property(_INK_EXTRA) or ""
        wgt.setStyleSheet(f"color: {ink_for(src, mode, level=level)};{extra}")


def make_browse_button(
    parent: QWidget | None = None,
    tooltip: str = "Browse…",
    icon: str = "folder",
    color: str | None = None,
) -> QPushButton:
    """Create a standardised file-browse button with a folder icon.

    Pass the icon name (without path or extension) to select a colored variant,
    e.g. ``icon="folder_build"``. Pass ``color`` (a hex accent) to tint the
    plain folder glyph to an arbitrary colour instead — used where the button
    should match a dialog's masthead accent (e.g. the magenta Tools dialogs).
    A tinted button carries no ``themed_folder_icon`` property, so the app's
    theme-reload leaves its custom colour untouched.
    """
    btn = QPushButton(parent)
    btn.setObjectName("browse")
    btn.setFixedWidth(36)
    btn.setToolTip(tooltip)
    if color is not None:
        btn.setIcon(load_tinted_folder_icon(color, size=20))
    else:
        btn.setIcon(load_folder_icon(icon))
        btn.setProperty("themed_folder_icon", icon)
    btn.setIconSize(QSize(20, 20))
    return btn


def replace_log_line(
    log: QPlainTextEdit,
    prev_text: str | None,
    new_text: str | None,
) -> str | None:
    """Replace a single tracked status line in a QPlainTextEdit log, in place.

    Removes ``prev_text``'s block (if still present) along with exactly one
    adjacent block separator — the trailing one when anything follows, otherwise
    the leading one — so no blank line is left wherever the line sits. Then
    appends ``new_text`` when it is non-empty. Returns the text now being tracked
    (``new_text`` or ``None``), to store for the next call.

    Lets a tab show only the most recent of a recurring notice (e.g. the detected
    instrument) instead of stacking identical lines as files are reloaded.
    """
    if prev_text:
        found = log.document().find(prev_text)
        if not found.isNull():
            block = found.block()
            keep = QTextCursor.MoveMode.KeepAnchor
            cursor = QTextCursor(log.document())
            if block.next().isValid():
                cursor.setPosition(block.position())
                cursor.setPosition(block.next().position(), keep)
            elif block.previous().isValid():
                cursor.setPosition(block.position() - 1)
                cursor.setPosition(block.position() + len(block.text()), keep)
            else:
                cursor.setPosition(0)
                cursor.setPosition(len(block.text()), keep)
            cursor.removeSelectedText()
    if new_text:
        log.appendPlainText(new_text)
        log.ensureCursorVisible()
        return new_text
    return None


@dataclass

class RevealFolderButton(QToolButton):
    """A small painted "reveal in the file manager" glyph — an up-arrow rising
    out of an open-top tray — in a given accent colour. Same flat style as
    :class:`ImageFileButton` / :class:`PatchGridButton` so a row of icon
    buttons reads as one set (Sebastian)."""

    FRAC = 0.58

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setObjectName("tooltip_btn")
        self.setFixedSize(QSize(40, 40))
        # Icon-only, mouse-operated: never take keyboard focus, so the space bar
        # can't activate it just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def set_appearance(self, mode: str) -> None:
        pass

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)  # QSS background (incl. :hover) under the glyph
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) * self.FRAC
        cx = self.width() / 2.0
        y0 = (self.height() - side) / 2.0
        color = QColor(self._color)
        if not self._hover:
            color.setAlpha(230)
        pen = QPen(color)
        pen.setWidthF(1.7)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Up-arrow (upper two-thirds).
        ax_top = y0 + side * 0.04
        ax_bot = y0 + side * 0.60
        p.drawLine(QPointF(cx, ax_bot), QPointF(cx, ax_top))
        head = side * 0.22
        p.drawLine(QPointF(cx, ax_top), QPointF(cx - head, ax_top + head))
        p.drawLine(QPointF(cx, ax_top), QPointF(cx + head, ax_top + head))
        # Open-top tray (lower third): ⊔ shape, a touch wider than the arrow
        # for a grounded "reveal" look (Sebastian).
        tw = side * 0.84
        ty = y0 + side * 0.66
        tb = y0 + side
        lip = side * 0.16
        tray = QPainterPath()
        tray.moveTo(cx - tw / 2, ty)
        tray.lineTo(cx - tw / 2, tb - lip)
        tray.quadTo(cx - tw / 2, tb, cx - tw / 2 + lip, tb)
        tray.lineTo(cx + tw / 2 - lip, tb)
        tray.quadTo(cx + tw / 2, tb, cx + tw / 2, tb - lip)
        tray.lineTo(cx + tw / 2, ty)
        p.drawPath(tray)
        p.end()


class ImageFileButton(QToolButton):
    """A small painted image-file glyph (frame + mountains + sun) in a given
    accent colour — sibling of :class:`PatchGridButton`, used for "load a
    TIFF image to print raw" on the Print Chart tab (#117, Knut)."""

    FRAC = 0.60

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setObjectName("tooltip_btn")
        self.setFixedSize(QSize(40, 40))
        # Icon-only, mouse-operated: never take keyboard focus, so the space bar
        # can't activate it just because a tab handed it the initial focus (Knut).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def set_appearance(self, mode: str) -> None:
        pass

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, ev) -> None:  # noqa: N802
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height()) * self.FRAC
        x0 = (self.width() - side) / 2.0
        y0 = (self.height() - side) / 2.0
        color = QColor(self._color)
        if not self._hover:
            color.setAlpha(230)
        pen = QPen(color)
        pen.setWidthF(1.6)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x0, y0, side, side), 2.0, 2.0)
        # mountains
        path = QPainterPath()
        path.moveTo(x0 + side * 0.10, y0 + side * 0.82)
        path.lineTo(x0 + side * 0.38, y0 + side * 0.45)
        path.lineTo(x0 + side * 0.55, y0 + side * 0.65)
        path.lineTo(x0 + side * 0.72, y0 + side * 0.38)
        path.lineTo(x0 + side * 0.90, y0 + side * 0.82)
        p.drawPath(path)
        # sun
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        r = side * 0.10
        p.drawEllipse(QRectF(x0 + side * 0.20, y0 + side * 0.16, 2 * r, 2 * r))
        p.end()

class GatedOption:
    """An option disabled when a tab's instrument/data gate is active.

    ``widgets`` are greyed out while the gate is active; ``neutralise`` clears the
    option in the collected params object right before the tool runs, so a flag
    enabled before the gate became active is never passed to colprof/profcheck.
    """
    widgets: list[QWidget] = field(default_factory=list)
    neutralise: Callable[[Any], None] = lambda params: None
