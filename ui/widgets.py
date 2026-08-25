"""Shared widget factory helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QEvent, QModelIndex, QObject, QPointF, QRect, QRectF, QSize, QSortFilterProxyModel, Qt, QUrl
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QTextCursor

from core.i18n import tr
from core.logger import get_logger
import weakref

from PyQt6.QtWidgets import (
    QApplication,
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


class _ExtensionFilterProxy(QSortFilterProxyModel):
    """Hides files whose extension is not in the allowed set; directories always shown."""

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(_input_bg_qss())

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


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
    app_pal = QApplication.palette()
    is_light = app_pal.window().color().lightness() > 150
    if is_light:
        from ui.light_styles import LM_BG_SURFACE
        gb.setAutoFillBackground(True)
        pal = gb.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(LM_BG_SURFACE))
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
    candidates.append(Path.home() / "ChromIQ")    # the app's working folder
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
    dlg = QFileDialog(parent, title, start_dir or str(Path.home()))
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        _style_file_dialog_toolbar(dlg)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
    if name_filter:
        dlg.setNameFilter(name_filter)
        if not native:
            exts = _parse_extensions(name_filter)
            if exts:
                dlg.setProxyModel(_ExtensionFilterProxy(exts, dlg))
    if not native:
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
    dlg = QFileDialog(parent, title, start_dir or str(Path.home()))
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        _style_file_dialog_toolbar(dlg)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
    if name_filter:
        dlg.setNameFilter(name_filter)
        if not native:
            exts = _parse_extensions(name_filter)
            if exts:
                dlg.setProxyModel(_ExtensionFilterProxy(exts, dlg))
    if not native:
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
    p = Path(start_path) if start_path else None
    if p is not None and p.is_dir():
        start_dir, default_name = str(p), ""
    elif p is not None:
        start_dir, default_name = str(p.parent), p.name
    else:
        start_dir, default_name = str(Path.home()), ""
    native = _prefer_native_dialogs()
    dlg = QFileDialog(parent, title, start_dir)
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog)
        _style_file_dialog_toolbar(dlg)
    dlg.setFileMode(QFileDialog.FileMode.AnyFile)
    dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    if name_filter:
        dlg.setNameFilter(name_filter)
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
    dlg = QFileDialog(parent, title, start_dir or str(Path.home()))
    dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
    dlg.setFileMode(QFileDialog.FileMode.Directory)
    if not native:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        _style_file_dialog_toolbar(dlg)
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
        if name == "folder" and _is_light_palette():
            from PyQt6.QtGui import QImage, QPainter
            img = scaled.toImage().convertToFormat(
                QImage.Format.Format_ARGB32_Premultiplied
            )
            painter = QPainter(img)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn
            )
            painter.fillRect(img.rect(), QColor("#22211f"))
            painter.end()
            recoloured = QPixmap.fromImage(img)
            recoloured.setDevicePixelRatio(dpr)
            return QIcon(recoloured)
        scaled.setDevicePixelRatio(dpr)
        return QIcon(scaled)
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)


def _is_light_palette() -> bool:
    """True when the active app palette is a light theme."""
    from PyQt6.QtGui import QGuiApplication
    pal = QGuiApplication.palette()
    return pal.window().color().lightness() > 150


def load_preset_icon(name: str) -> QIcon:
    """Load a preset +/- icon, switching to the *_dark variant in light mode.

    `name` is the bare asset stem ("plus" or "minus"). On a light palette,
    we load the *_dark.svg sibling so the glyph reads on the warm-white
    Presets row.
    """
    from core.resource_path import resource_path
    stem = f"{name}_dark" if _is_light_palette() else name
    return QIcon(str(resource_path(f"assets/{stem}.svg")))


def load_tinted_folder_icon(color: str, size: int = 22) -> QIcon:
    """The standard folder glyph tinted in an arbitrary accent ``color``.

    Repaints every opaque pixel of ``folder.png`` via SourceIn, preserving the
    icon's alpha mask (same trick :func:`load_folder_icon` uses for the
    light-theme recolour). Spectrum accents read on both themes, so no
    light/dark variant is needed. Used where a browse button should match its
    dialog's masthead accent rather than a tab-coded variant."""
    from core.resource_path import resource_path
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
    the two buttons don't read as the same action."""
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QPainterPath, QPen

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
    """
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    hover = "#{:02x}{:02x}{:02x}".format(int(r * 0.82), int(g * 0.82), int(b * 0.82))
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
                f" color: #0a0a0a; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
            )
            # …and re-assert the width afterwards, so the order of the two never
            # matters again.
            fit_button_width(btn)


def load_refresh_icon(name: str) -> QIcon:
    """Load a colored refresh icon from assets/refresh/<name>.png.

    Falls back to the OS browser-reload icon if the file is not found.
    """
    from core.resource_path import resource_path
    from PyQt6.QtGui import QGuiApplication
    px = QPixmap(str(resource_path(f"assets/refresh/{name}.png")))
    if not px.isNull():
        dpr  = QGuiApplication.primaryScreen().devicePixelRatio()
        phys = round(20 * dpr)
        scaled = px.scaled(phys, phys,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        return QIcon(scaled)
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)


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
