"""The window behind the gear button in Create Chart's Presets frame.

Knut, #182 5818659478: *"Clicking this button will open a list of all built-in
presets available (not local made presets). Each preset in the list will have
a checkmark-box in front of the preset name. The window shall have text
explaining that all marked built-in presets will be shown in the pulldown list
for 'Select preset' and when clicking on the Built-in presets button [...] and
all other presets for the group they belong to, are still available, but are
available in a collapsable arrow."* And: *"The window has only a Close button.
Closing the window will automatically apply the changes."*

So there is no Cancel and no OK. Every way out (the Close button, Escape, the
window's own close box) hands back the same thing, :meth:`ticked`, and the
caller stores it (:func:`core.curated_presets.store_choices`) and rebuilds both
lists. The groups and their order are the pulldown's own
(``BUILTIN_PRESET_GROUPS``), handed in by the caller, so this window cannot list
a preset the pulldown does not have or in a different order.

A group's own box ticks or clears the whole group (a tri-state box, partly
ticked while the group is mixed), and its second column counts what is ticked,
because a group of 74 presets does not show its own total on one screen.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHeaderView, QLabel,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core.i18n import tr

_KEY_ROLE = Qt.ItemDataRole.UserRole + 1


def _count_text(shown: int, total: int) -> str:
    return tr("{shown} of {total} shown").format(shown=shown, total=total)


class BuiltinPresetsShownDialog(QDialog):
    """``groups`` is ``[(heading, [(label, tooltip, key), …]), …]``; ``shown``
    the keys ticked when the window opens."""

    def __init__(self, groups: list[tuple[str, list[tuple[str, str, str]]]],
                 shown: set[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("builtin_presets_shown_dialog")
        self.setWindowTitle(tr("Built-in presets in the lists"))
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        self._intro = QLabel(
            tr("Ticked built-in presets are listed directly in “Select "
               "preset” and in the list the Built-in presets button opens "
               "(the middle one of the three buttons at the top of Create "
               "Chart).") + "\n\n"
            + tr("The others are still available. In each group they wait "
                 "under an arrow, placed after the group's last ticked preset: "
                 "click the arrow, or select it and press the Right arrow key, "
                 "to show them.") + "\n\n"
            + tr("Your own presets are not affected and always stay at the "
                 "top. Your choice is kept when you close this window."),
            self)
        self._intro.setWordWrap(True)
        self._intro.setObjectName("builtin_presets_shown_intro")
        lay.addWidget(self._intro)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName("builtin_presets_shown_tree")
        self._tree.setColumnCount(2)
        self._tree.setHeaderHidden(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setAccessibleName(tr("Built-in presets in the lists"))
        self._groups: list[QTreeWidgetItem] = []
        for heading, entries in groups:
            g = QTreeWidgetItem(self._tree, [heading, ""])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                       | Qt.ItemFlag.ItemIsUserCheckable
                       | Qt.ItemFlag.ItemIsAutoTristate)
            font = g.font(0)
            font.setBold(True)
            g.setFont(0, font)
            for label, tip, key in entries:
                c = QTreeWidgetItem(g, [label, ""])
                c.setFlags(Qt.ItemFlag.ItemIsEnabled
                           | Qt.ItemFlag.ItemIsSelectable
                           | Qt.ItemFlag.ItemIsUserCheckable
                           | Qt.ItemFlag.ItemNeverHasChildren)
                c.setData(0, _KEY_ROLE, key)
                if tip:
                    c.setToolTip(0, tip)
                c.setCheckState(0, Qt.CheckState.Checked if key in shown
                                else Qt.CheckState.Unchecked)
            g.setExpanded(True)
            self._groups.append(g)
            self._recount(g)
        self._tree.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self._tree, 1)

        bb = self._buttons = QDialogButtonBox(self)
        self._close_btn = bb.addButton(
            tr("Close"), QDialogButtonBox.ButtonRole.RejectRole)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        if self._groups:
            self._tree.setCurrentItem(self._groups[0])
        self._tree.setFocus()
        self._fit()

    #: The narrowest the window may be made, and the fewest list rows it must
    #: always show.
    MIN_WIDTH = 560
    MIN_ROWS = 10

    def _minimum(self) -> None:
        """**A SENSIBLE SMALLEST SIZE (challenge 3 of beta 42, B8-1035).** The
        window had none: Qt's own minimum was 146 x 218 px, and measured at
        420 x 360 the three paragraphs took 176 px (German 208) and left the
        list five rows (German three). Now the list keeps :attr:`MIN_ROWS`
        rows at the smallest size, with the paragraphs wrapped whole above
        it, in whatever language: the height is measured from the paragraphs
        at :attr:`MIN_WIDTH`, not written down."""
        self.ensurePolished()
        self._tree.ensurePolished()
        row_h = self._tree.sizeHintForRow(0)
        if row_h <= 0:
            row_h = self._tree.fontMetrics().height() + 6
        frame = 2 * self._tree.frameWidth() + 4
        tree_min = row_h * self.MIN_ROWS + frame
        self._tree.setMinimumHeight(tree_min)
        lay = self.layout()
        m = lay.contentsMargins()
        text_w = self.MIN_WIDTH - m.left() - m.right()
        intro_h = self._intro.heightForWidth(text_w)
        if intro_h <= 0:
            intro_h = self._intro.sizeHint().height()
        min_h = (m.top() + m.bottom() + intro_h + tree_min
                 + self._buttons.sizeHint().height() + 2 * lay.spacing())
        self.setMinimumSize(self.MIN_WIDTH, min_h)

    # ------------------------------------------------------------------
    def _fit(self) -> None:
        self._minimum()
        # 880: measured on screen at 720, the longest ColorMunki names
        # ("…-Hand Held · Full layout setup") were cut with an ellipsis.
        width, height = 880, 720
        screen = self.screen()
        if screen is not None:
            avail = screen.availableGeometry()
            width = min(width, avail.width() - 40)
            height = min(height, avail.height() - 60)
        self.resize(max(width, self.minimumWidth()),
                    max(height, self.minimumHeight()))

    def _recount(self, group: QTreeWidgetItem) -> None:
        total = group.childCount()
        shown = sum(1 for i in range(total)
                    if group.child(i).checkState(0) == Qt.CheckState.Checked)
        group.setText(1, _count_text(shown, total))

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return
        group = item if item.parent() is None else item.parent()
        self._tree.blockSignals(True)
        try:
            self._recount(group)
        finally:
            self._tree.blockSignals(False)

    # ------------------------------------------------------------------
    def ticked(self) -> set[str]:
        """The keys whose box is ticked now."""
        out: set[str] = set()
        for g in self._groups:
            for i in range(g.childCount()):
                c = g.child(i)
                if c.checkState(0) == Qt.CheckState.Checked:
                    out.add(str(c.data(0, _KEY_ROLE)))
        return out

    def set_ticked(self, key: str, on: bool) -> bool:
        """Tick or clear one preset, as a click on its box would. For drivers
        and tests; answers whether the key is in the window."""
        for g in self._groups:
            for i in range(g.childCount()):
                c = g.child(i)
                if c.data(0, _KEY_ROLE) == key:
                    c.setCheckState(0, Qt.CheckState.Checked if on
                                    else Qt.CheckState.Unchecked)
                    return True
        return False
