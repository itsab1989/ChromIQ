"""Shared widget factory helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QEvent, QModelIndex, QObject, QPointF, QRect, QRectF, QSize, QSortFilterProxyModel, Qt, QUrl
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QTextCursor

from core.i18n import tr
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
    font = btn.font()
    if font.capitalization() == QFont.Capitalization.AllUppercase:
        # QFontMetrics measures the characters given, not the capitalisation the
        # painter will apply — so measure what will really be drawn.
        text = text.upper()
    fm = QFontMetrics(font)
    needed = fm.horizontalAdvance(text)
    try:
        opt = QStyleOptionButton()
        opt.initFrom(btn)
        opt.text = text
        want = btn.style().sizeFromContents(
            QStyle.ContentsType.CT_PushButton, opt,
            QSize(needed, fm.height()), btn).width()
    except Exception:      # noqa: BLE001 — sizing must never raise
        want = 0
    # A floor of its own, in case the style under-reports the frame and padding.
    want = max(want, needed + 36)
    icon = btn.icon()
    if icon is not None and not icon.isNull():
        want += btn.iconSize().width() + 6
    if btn.minimumWidth() < want:
        btn.setMinimumWidth(want)


class ButtonFontFilter(QObject):
    """Applies Menlo + AllUppercase to every QPushButton as it is polished, and
    keeps it wide enough for the label that font produces."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if isinstance(obj, QPushButton) and event.type() == QEvent.Type.Polish:
            self.fit(obj)
        return False

    @staticmethod
    def fit(btn) -> None:
        """Give *btn* the app's button font, then the width that font needs."""
        font = btn.font()
        font.setFamilies(["Menlo", "Consolas", "Courier New", "monospace"])
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        btn.setFont(font)
        fit_button_width(btn)


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
        if not self._hover:
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
            btn.setStyleSheet(
                f"QPushButton {{ background: {color}; border: 1px solid {color};"
                f" color: #0a0a0a; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
            )


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
