"""The window behind the gear button in Create Chart's Presets frame.

Knut, #182 5818659478: *"Clicking this button will open a list of all built-in
presets available (not local made presets). Each preset in the list will have
a checkmark-box in front of the preset name. The window shall have text
explaining that all marked built-in presets will be shown in the pulldown list
for 'Select preset' and when clicking on the Built-in presets button [...] and
all other presets for the group they belong to, are still available, but are
available in a collapsable arrow."*

**OK AND CLOSE (Basti, owner, 2026-09-25, B8-1097).** Knut had asked for *"only
a Close button. Closing the window will automatically apply the changes."*
Basti replaced that: the window has two buttons at the bottom right, **OK** to
the left of **Close**. OK is the default button (Return); it accepts, and the
caller then stores :meth:`ticked` (:func:`core.curated_presets.store_choices`)
and rebuilds both lists. Close, Escape and the window's own close box all
reject, and the caller stores nothing: the ticks are discarded.

The two buttons are placed by hand in a plain row, not in a
``QDialogButtonBox``: a button box orders its buttons by the style's
``SH_DialogButtonLayout``, which is the Windows order only while
``main.py``'s ``WinButtonLayoutStyle`` is in front of the style (macOS's and
GNOME's own layouts put the accept button LAST). A row of our own is OK then
Close whatever the style says. The groups and their order are the pulldown's own
(``BUILTIN_PRESET_GROUPS``), handed in by the caller, so this window cannot list
a preset the pulldown does not have or in a different order.

A group's own box ticks or clears the whole group (a tri-state box, partly
ticked while the group is mixed), and its second column counts what is ticked,
because a group of 74 presets does not show its own total on one screen.

**EXPORT LIST AND IMPORT LIST (Knut, #182 5831246553, beta 43, B8-1101).**
*"one "Export list" and one "Import list". The export button saves a csv file
of the table with the current settings. The import button imports the same
type of file back into the app and updates the checked settings."* Both sit at
the bottom LEFT, so OK and Close stay the pair at the right. The file is the
table ``scripts/make_preset_defaults.py --table`` writes for Knut's users,
written and read by :mod:`core.curated_presets` for both, so an exported file
goes through ``--from-table`` and a filled-in table comes back through Import
list. Export writes the boxes AS SHOWN, unsaved changes included. Import sets
the boxes and nothing else: like every other change in this window, OK keeps
it and Close discards it (Knut wrote "closing the window then updates"; the
window has had OK and Close since B8-1097, so it is OK that applies). A row is
matched by its key; a key this ChromIQ does not have, a row with no key, and an
empty or unreadable yes/no are reported and change nothing, and a preset the
file does not name keeps its box. Both file windows open in the ChromIQ folder
(``custom_output_path``, else ~/ChromIQ), the same folder projects go in.

**THE PAPER FILTER (Knut, #182 5832303551, beta 43, B8-1131).** *"Add a
checkbox in the window named "Filter preset-dropdown list according to
selected paper size"."* It sits under the list, above the buttons. Like the
ticks, OK stores it (the setting
:data:`core.curated_presets.PAPER_FILTER_KEY`) and Close discards it; what it
does to the two lists is in ``ui/tabs/tab_chart.py``
(``_apply_preset_collapse``, ``paper_filter_groups``).
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from core import curated_presets as cp
from core.i18n import tr

_KEY_ROLE = Qt.ItemDataRole.UserRole + 1


def _count_text(shown: int, total: int) -> str:
    return tr("{shown} of {total} shown").format(shown=shown, total=total)


class BuiltinPresetsShownDialog(QDialog):
    """``groups`` is ``[(heading, [(label, tooltip, key), …]), …]``; ``shown``
    the keys ticked when the window opens. ``facts`` are the rows the table
    names (:func:`ui.tabs.tab_chart.builtin_preset_facts`); without them the
    table is written from ``groups``. ``folder`` is where the two file windows
    open; without it, the ChromIQ folder."""

    #: How many problem lines the import summary lists before "and N more".
    SUMMARY_LINES = 10

    def __init__(self, groups: list[tuple[str, list[tuple[str, str, str]]]],
                 shown: set[str], parent: QWidget | None = None, *,
                 facts: list[dict] | None = None,
                 folder: Path | str | None = None,
                 paper_filter: bool = False) -> None:
        super().__init__(parent)
        self._facts = facts if facts is not None else [
            {"group": heading, "name": label, "key": key}
            for heading, entries in groups for (label, _tip, key) in entries]
        self._folder = Path(folder) if folder else None
        #: Comments read by Import list, written back by Export list, so a
        #: table's comments survive a round trip through the window.
        self._comments: dict[str, str] = {}
        self._last_box: QMessageBox | None = None
        self.setObjectName("builtin_presets_shown_dialog")
        # NAMED (Knut, #182 5834773589, B8-1172): "Settings for built-in
        # presets", the name the gear's tooltip, the help texts and the
        # note at the bottom of both preset lists use for this window.
        self.setWindowTitle(tr("Settings for built-in presets"))
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
            # K42-3 (Knut, #182 5833232475): the paper filter applies to
            # built-in presets only, and the window says so here.
            + tr("Your own presets are not affected: neither the ticks nor "
                 "the paper filter below changes them, and they always "
                 "stay at the top. OK keeps your choice; Close leaves the "
                 "lists as they were.") + "\n\n"
            + tr("Export list saves this table as a CSV file, with the ticks "
                 "as they are now. Import list sets the ticks from such a "
                 "file. Like any change here, an imported list is kept only "
                 "by OK; Close discards it."),
            self)
        self._intro.setWordWrap(True)
        self._intro.setObjectName("builtin_presets_shown_intro")
        # A HELP ICON FOR THE WHOLE WINDOW (Knut, #182 5833232475), beside
        # the paragraphs, through the app's own ⓘ.
        from ui.tooltip_button import TooltipButton
        self._help = TooltipButton(
            tr("How the built-in preset lists work"),
            # THE RULES FOR WHEN A PRESET SHOWS (Knut, #182 5840677938 and
            # 5840692243, K48): the paper filter, the ticks, "N more", Custom
            # and Scanner, all in one place.
            tr("“Settings for built-in presets” chooses which built-in "
               "presets “Select preset” and the Built-in presets list show "
               "directly. It always lists every built-in preset with its "
               "tick; the paper filter does not change what it lists."
               "\n\nWhen a built-in preset is shown in those two lists:"
               "\n\n•  Paper filter on (the default): only the presets for "
               "the paper selected in Create Chart, Guided's Paper size or "
               "Manual's Paper, whichever mode is shown. Every group follows "
               "it, Scanner too. The orientation counts: A3 Portrait and A3 "
               "Landscape are two papers."
               "\n\n•  Custom paper: every preset laid out on a size the "
               "paper list does not name. A Custom width and height that "
               "equal a named paper, orientation included, count as that "
               "paper: 210 × 297 lists the A4 Portrait presets, 297 × 210 "
               "the A4 Landscape ones."
               "\n\n•  A ticked preset for that paper is listed directly. The "
               "group's other presets for that paper wait under “▸ N more "
               "presets”: click it, or select it and press the Right arrow "
               "key, to show them."
               "\n\n•  A group with presets for that paper but none of them "
               "ticked shows its heading and “▸ N more presets” only. A group "
               "with no preset for that paper is not shown."
               "\n\n•  Paper filter off: every built-in preset, the ticked "
               "ones directly and the rest under “▸ N more presets”."
               "\n\nA group's own box ticks or clears the whole group. OK "
               "keeps the ticks and the paper filter. Close, Escape and the "
               "window's close box leave both lists as they were."
               "\n\nExport list saves this table as a CSV file, with the "
               "ticks as they are now. Import list sets the ticks from such "
               "a file; OK keeps them."
               "\n\nYour own presets are never changed by any of this: they "
               "are always listed, at the top."), self)
        # NOT RENAMED (Knut, #182 5840677938, K48): the style sheets draw
        # the app's flat ⓘ by its object name, QToolButton#tooltip_btn
        # (no frame, no fill). This window gave its two icons names of
        # their own, so neither rule reached them and they were drawn as
        # framed tool buttons. Reach them as `_help` and
        # `_paper_filter_help`.
        top = self._top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self._intro, 1)
        top.addWidget(self._help, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)

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
        self._tree.setAccessibleName(tr("Settings for built-in presets"))
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

        # Knut, #182 5832303551: the paper filter, kept by OK like the ticks.
        self._paper_filter = QCheckBox(
            tr("Filter preset-dropdown list according to selected paper size"),
            self)
        self._paper_filter.setObjectName("builtin_presets_paper_filter")
        self._paper_filter.setChecked(bool(paper_filter))
        # ITS OWN HELP ICON, ON ITS RIGHT (Knut, #182 5833232475), in place
        # of the tooltip it had in B8-1131.
        from ui.tooltip_button import TooltipButton
        self._paper_filter_help = TooltipButton(
            tr("The paper filter"),
            tr("While this box is ticked (the default), “Select preset” "
               "and the Built-in presets list show only the built-in "
               "presets for the paper selected in Create Chart: Guided's "
               "Paper size or Manual's Paper, whichever mode is shown. "
               "They follow the paper as you change it.\n\nIt applies to "
               "built-in presets only, in every group, Scanner included. "
               "Your own presets are never filtered, and neither is the "
               "list in “Settings for built-in presets”, which always "
               "shows every built-in preset with its tick.\n\nA preset's "
               "paper is the paper its chart is laid out on, and the "
               "orientation counts: A3 Portrait shows only the portrait A3 "
               "presets, A3 Landscape only the landscape ones.\n\nWith a "
               "Custom paper, every preset laid out on a size the paper "
               "list does not name is shown. A Custom width and height that "
               "equal a named paper, orientation included, count as that "
               "paper: 210 × 297 shows the A4 Portrait presets, 297 × 210 "
               "the A4 Landscape ones.\n\nThe ticks and the arrows still apply within "
               "what the filter leaves: the ticked presets of that paper "
               "are listed directly, and “▸ N more presets” opens the rest "
               "of that paper's presets. A group with presets for the paper "
               "but none of them ticked shows its heading and “▸ N more "
               "presets” only; a group with none for the paper is not "
               "shown.\n\nUntick the box to list every built-in preset "
               "whatever the paper. OK keeps the choice; Close discards "
               "it."), self)
        box_row = QHBoxLayout()
        box_row.setContentsMargins(0, 0, 0, 0)
        box_row.addWidget(self._paper_filter)
        box_row.addWidget(self._paper_filter_help)
        box_row.addStretch(1)
        lay.addLayout(box_row)

        # What the last export or import did, in one line, above the buttons.
        self._status = QLabel(self)
        self._status.setObjectName("builtin_presets_shown_status")
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._status.hide()
        lay.addWidget(self._status)

        # Export list and Import list at the bottom LEFT; OK, then Close, at
        # the bottom right, placed by hand (see the module docstring: a
        # QDialogButtonBox would let the style reorder them).
        bb = self._buttons = QWidget(self)
        bb.setObjectName("builtin_presets_shown_buttons")
        row = QHBoxLayout(bb)
        row.setContentsMargins(0, 0, 0, 0)
        self._export_btn = QPushButton(tr("Export list"), bb)
        self._export_btn.setObjectName("builtin_presets_shown_export")
        self._export_btn.setAutoDefault(False)
        self._export_btn.setToolTip(
            tr("Save this table as a CSV file, with the ticks as they are "
               "now."))
        self._export_btn.clicked.connect(self._on_export)
        self._import_btn = QPushButton(tr("Import list"), bb)
        self._import_btn.setObjectName("builtin_presets_shown_import")
        self._import_btn.setAutoDefault(False)
        self._import_btn.setToolTip(
            tr("Set the ticks from a CSV file saved with Export list. OK "
               "keeps them; Close discards them."))
        self._import_btn.clicked.connect(self._on_import)
        row.addWidget(self._export_btn)
        row.addWidget(self._import_btn)
        row.addStretch(1)
        self._ok_btn = QPushButton(tr("OK"), bb)
        self._ok_btn.setObjectName("builtin_presets_shown_ok")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self.accept)
        self._close_btn = QPushButton(tr("Close"), bb)
        self._close_btn.setObjectName("builtin_presets_shown_close")
        self._close_btn.setAutoDefault(False)
        self._close_btn.clicked.connect(self.reject)
        row.addWidget(self._ok_btn)
        row.addWidget(self._close_btn)
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
        # the paragraphs share their row with the window's help icon
        intro_w = (text_w - self._help.sizeHint().width()
                   - max(0, self._top.spacing()))
        intro_h = self._intro.heightForWidth(intro_w)
        if intro_h <= 0:
            intro_h = self._intro.sizeHint().height()
        status_h = 0
        if not self._status.isHidden():
            status_h = (self._status.heightForWidth(text_w)
                        + lay.spacing())
        min_h = (m.top() + m.bottom() + intro_h + tree_min + status_h
                 + max(self._paper_filter.sizeHint().height(),
                       self._paper_filter_help.sizeHint().height())
                 + self._buttons.sizeHint().height() + 3 * lay.spacing())
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

    def paper_filter(self) -> bool:
        """Whether "Filter preset-dropdown list according to selected paper
        size" is ticked now."""
        return self._paper_filter.isChecked()

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

    def _items(self):
        for g in self._groups:
            for i in range(g.childCount()):
                yield g.child(i)

    # ------------------------------------------------------------------
    # Export list / Import list
    # ------------------------------------------------------------------
    def folder(self) -> Path:
        """Where the two file windows open: the ChromIQ folder."""
        if self._folder is not None:
            return self._folder
        from ui.widgets import chromiq_root_dir
        return chromiq_root_dir()

    def export_to(self, path: Path | str) -> None:
        """Write the table with the boxes as they are NOW. Raises OSError."""
        with Path(path).open("w", newline="",
                             encoding=cp.TABLE_ENCODING) as fh:
            cp.write_table(fh, self._facts, self.ticked(), self._comments)

    def import_from(self, path: Path | str) -> "cp.TableReading":
        """Set the boxes from a table and answer what was found. Only the
        boxes change; nothing is stored until OK. Raises OSError, or
        :class:`core.curated_presets.TableError` for a file that is not a
        table (and then no box has changed)."""
        raw = Path(path).read_bytes()
        known = [str(c.data(0, _KEY_ROLE)) for c in self._items()]
        reading = cp.read_table(raw, known)
        for c in self._items():
            key = str(c.data(0, _KEY_ROLE))
            if key in reading.answers:
                c.setCheckState(0, Qt.CheckState.Checked
                                if reading.answers[key]
                                else Qt.CheckState.Unchecked)
        self._comments.update(reading.comments)
        return reading

    def _ask_save_path(self) -> str:
        from ui.widgets import save_file_dialog
        return save_file_dialog(
            self, tr("Export list"), tr("CSV files (*.csv)"),
            str(self.folder() / cp.EXPORT_FILENAME))

    def _ask_open_path(self) -> str:
        from ui.widgets import open_file_dialog
        folder = self.folder()
        return open_file_dialog(
            self, tr("Import list"), tr("CSV files (*.csv)"),
            start_dir=str(folder) if folder.is_dir() else "")

    def _exec_box(self, box: QMessageBox) -> None:
        """Every message this window shows goes through here: one door for a
        driver and for a test."""
        self._last_box = box
        box.exec()

    def _message(self, icon, title: str, text: str, info: str = "",
                 details: str = "", button: str = "") -> None:
        box = QMessageBox(self)
        box.setObjectName("builtin_presets_shown_message")
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        if info:
            box.setInformativeText(info)
        if details:
            box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        if button:
            # Not "OK": beside a sentence about the window's own OK, a second
            # OK that only closes this message would read as the same one.
            box.button(QMessageBox.StandardButton.Ok).setText(button)
        self._exec_box(box)

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.show()
        self._minimum()

    def _on_export(self) -> None:
        path = self._ask_save_path()
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self.export_to(path)
        except OSError as exc:
            self._set_status(tr("The list was not saved to {path}.").format(
                path=path))
            self._message(QMessageBox.Icon.Warning, tr("Export list"),
                          tr("The list could not be saved."), str(exc))
            return
        self._set_status(tr("Saved the list to {path}.").format(path=path))

    def _on_import(self) -> None:
        path = self._ask_open_path()
        if not path:
            return
        try:
            reading = self.import_from(path)
        except cp.TableError as exc:
            # B8-1164: the status line says what happened to THIS import; it
            # kept the last export's "Saved the list to …" before
            self._set_status(tr("{path} was not imported. Nothing was "
                                "changed.").format(path=path))
            if getattr(exc, "unreadable", False):
                why = tr("It cannot be read as a table: a cell is too long, "
                         "or it is not a text file.")
            else:
                why = tr("It needs the columns {key} and {answer}, as Export "
                         "list writes them.").format(key=cp.TABLE_KEY,
                                                     answer=cp.TABLE_ANSWER)
            self._message(
                QMessageBox.Icon.Warning, tr("Import list"),
                tr("This file is not a list of built-in presets. Nothing "
                   "was changed."), why)
            return
        except OSError as exc:
            self._set_status(tr("{path} was not imported. Nothing was "
                                "changed.").format(path=path))
            self._message(QMessageBox.Icon.Warning, tr("Import list"),
                          tr("The file could not be read. Nothing was "
                             "changed."), str(exc))
            return
        self._show_import_summary(reading)
        self._set_status(
            tr("Imported {path}. OK keeps these ticks; Close discards "
               "them.").format(path=path))

    def import_summary(self, reading: "cp.TableReading"
                       ) -> tuple[str, list[str]]:
        """``(the counts, one line per problem)`` for the import summary."""
        ticked = sum(1 for v in reading.answers.values() if v)
        unticked = len(reading.answers) - ticked
        named = (set(reading.answers) | {k for _l, k, _n in reading.blank}
                 | {k for _l, k, _n, _a in reading.invalid})
        missing = sum(1 for c in self._items()
                      if str(c.data(0, _KEY_ROLE)) not in named)
        counts = [tr("Ticked: {count}").format(count=ticked),
                  tr("Unticked: {count}").format(count=unticked),
                  tr("Skipped: {count}").format(count=reading.skipped)]
        if missing:
            counts.append(tr("Not in the file, so left as they were: "
                             "{count}").format(count=missing))
        problems: list[tuple[int, str]] = []
        for line, key, _name in reading.unknown:
            problems.append((line, tr(
                "Line {line}: “{key}” is not a built-in preset of this "
                "ChromIQ. Skipped.").format(line=line, key=key)))
        for line, name in reading.no_key:
            problems.append((line, tr(
                "Line {line}: {name}: no key, so the row cannot be "
                "matched. Skipped.").format(line=line, name=name or "?")))
        for line, _key, name in reading.blank:
            problems.append((line, tr(
                "Line {line}: {name}: no yes or no. Its tick is "
                "unchanged.").format(line=line, name=name)))
        for lines, key, name, answer in reading.duplicates:
            # B8-1163: a key listed twice was settled by its last line, and
            # the summary did not say so
            at = ", ".join(str(n) for n in lines)
            text = (tr("Lines {lines}: {name} is listed more than once. The "
                       "last of them counts, so it is ticked.")
                    if answer else
                    tr("Lines {lines}: {name} is listed more than once. The "
                       "last of them counts, so it is unticked."))
            problems.append((lines[0], text.format(lines=at,
                                                   name=name or key)))
        for line, _key, name, answer in reading.invalid:
            problems.append((line, tr(
                "Line {line}: {name}: “{answer}” is not yes or no. Its tick "
                "is unchanged.").format(line=line, name=name,
                                        answer=answer)))
        problems.sort(key=lambda p: p[0])
        return "\n".join(counts), [text for _line, text in problems]

    def _show_import_summary(self, reading: "cp.TableReading") -> None:
        counts, problems = self.import_summary(reading)
        info = counts
        if problems:
            shown = problems[: self.SUMMARY_LINES]
            info += "\n\n" + "\n".join(shown)
            if len(problems) > len(shown):
                info += "\n" + tr("And {count} more, listed under the "
                                   "details.").format(
                    count=len(problems) - len(shown))
        info += "\n\n" + tr("Nothing is stored yet: OK keeps these ticks, "
                               "Close discards them.")
        self._message(
            QMessageBox.Icon.Warning if problems
            else QMessageBox.Icon.Information,
            tr("Import list"),
            tr("The window now shows the ticks from the list."),
            info, "\n".join(problems) if len(problems) > self.SUMMARY_LINES
            else "", button=tr("Back to the list"))
