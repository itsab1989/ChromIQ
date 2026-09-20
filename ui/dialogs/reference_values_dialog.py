"""One window for every set of numbers ChromIQ reads but may not ship.

**WHY THIS EXISTS AT ALL.** ChromIQ keeps other people's published values out
of its own code: the ISO 12647 tolerance limits, and, when it comes,
Fogra's characterisation data. A licence holder supplies their own copy and
ChromIQ reads it. Beta 26 gave that three buttons in the Report limits window,
and Basti, 2026-09-20, saw where it was going: *"if you are putting in 3 more
buttons there will be quite a lot in the end"*.

He is right, and the arithmetic is the argument: one data source cost three
buttons, so two sources cost six, in a window whose subject is a table of
limits and not a file manager. **One door, and a small window behind it with a
section per source.** Adding Fogra is then a new entry in `SOURCES` and nothing
in the Report limits window changes at all.

The window also does something the row of buttons could not: it SAYS WHAT IS IN
USE. A button cannot tell you that ChromIQ is judging against your own file,
and that is the one fact a person opening this wants first.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout)

from core.i18n import tr
from ui.styles import SPEC_GREEN
from ui.tooltip_button import TooltipButton

#: How a control in here is made short, and it is NOT ``setFixedHeight``.
#:
#: Basti asked twice: *"the three buttons should be reduced in heigth"*, then
#: *"the current ones are still big ... they could be smaller i think"*. Beta 26
#: answered with a fixed height of 22 and this window first answered with one of
#: 18, and BOTH ARE 42 px ON SCREEN. `ui/styles.py` sets
#: `QPushButton { padding: 6px 18px; min-height: 28px; }` for the whole app, and
#: Qt's stylesheet style folds that into `minimumSizeHint` (28+6+6+1+1 = 42),
#: which a layout honours over a fixed height. A fixed height therefore cannot
#: make ANY button in ChromIQ shorter than 42 px, and the guard that read
#: `.height()` off a dialog nobody showed read back the 18 nobody sees.
#:
#: A per-widget stylesheet can, because it puts `min-height` DOWN as well as
#: capping `max-height`. This is the declaration the Report limits window's own
#: "Restore this column" button already uses, and it measures 22 px, which is
#: what the preset window's button settled on (B8-420).
#:
#: Measured on screen, round 30, `scripts/adv30_eighteen_px_is_forty_two.py`;
#: guarded by `tests/test_a_short_button_is_short_on_screen.py`, which lays the
#: button out under the app's own stylesheet before it measures anything.
SMALL_BTN_QSS = ("QPushButton { padding: 1px 6px; font-size: 10px;"
                 " min-height: 22px; max-height: 22px; }")


@dataclass(frozen=True)
class Source:
    """One set of numbers somebody else publishes and ChromIQ reads."""

    key: str
    title: str
    why: str
    #: "" when nothing is supplied, else the path in use
    in_use: Callable[[], str]
    #: Where ChromIQ keeps its OWN copy of this source. Two different
    #: questions hide behind one answer otherwise: `in_use` says "is ChromIQ
    #: judging against somebody's numbers", and this says "are they in a file
    #: ChromIQ may delete". `CHROMIQ_COMPLIANCE_ISO_FILE` makes them differ,
    #: and with only the first of them "Stop using it" sat ENABLED over a
    #: `forget` that could not remove anything: measured on screen, round 30,
    #: pressed, and NOTHING happened -- no message, no state change, no file
    #: touched. Exactly the shape beta 26 shipped.
    own_copy: Callable[[], Path]
    write_template: Callable[[Path], None]
    install: Callable[[Path], Path]
    forget: Callable[[], bool]
    template_name: str
    #: What the file is called in a file dialog's filter
    file_filter: str = "JSON files (*.json)"


def iso_source() -> Source:
    from workflow import compliance_sets as cs

    return Source(
        key="iso12647",
        title=tr("ISO 12647-7 and ISO 12647-8 limit values"),
        why=tr("ChromIQ does not ship these numbers and cannot: they are the "
               "content of a paid standard. Supply your own copy's values and "
               "the two ISO columns stop showing ? and start judging."),
        in_use=cs.iso_data_path_text,
        own_copy=cs.user_values_path,
        write_template=lambda p: p.write_text(cs.iso_values_template(),
                                              encoding="utf-8"),
        install=cs.install_user_values,
        forget=cs.forget_user_values,
        template_name=cs.ISO_USER_FILE,
    )


def sources() -> "list[Source]":
    """Every source, in the order the window shows them.

    Fogra's characterisation data joins this list when the question of reading
    it rather than shipping it is settled; nothing else has to change.
    """
    return [iso_source()]


class ReferenceValuesDialog(QDialog):
    """Supply, replace or remove the values ChromIQ reads but does not ship."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Reference values"))
        self.setMinimumWidth(560)
        self._rows: "list[tuple[Source, QLabel, QPushButton]]" = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)

        head = QLabel(tr(
            "Some numbers ChromIQ judges against are published by somebody "
            "else and cannot be shipped inside the program. If you hold a "
            "copy, supply it here and ChromIQ will use it. Everything you "
            "supply stays on this computer."), self)
        head.setWordWrap(True)
        outer.addWidget(head)

        for src in sources():
            outer.addWidget(self._section(src))
        outer.addStretch(1)

        close = QPushButton(tr("Close"), self)
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(close)
        outer.addLayout(row)
        self._refresh()

    # ------------------------------------------------------------------
    def _section(self, src: Source) -> QFrame:
        box = QFrame(self)
        box.setFrameShape(QFrame.Shape.StyledPanel)
        col = QVBoxLayout(box)
        col.setContentsMargins(12, 10, 12, 10)
        col.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel(f"<b>{src.title}</b>", box)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(TooltipButton(src.title, self._help(src), box,
                                          min_width=520, color=SPEC_GREEN))
        col.addLayout(title_row)

        why = QLabel(src.why, box)
        why.setWordWrap(True)
        col.addWidget(why)

        state = QLabel("", box)
        state.setWordWrap(True)
        state.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(state)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        for label, slot in (
                (tr("Save a file to fill in…"), lambda _=0, s=src: self._template(s)),
                (tr("Use a file I filled in…"), lambda _=0, s=src: self._install(s)),
        ):
            b = QPushButton(label, box)
            b.setStyleSheet(SMALL_BTN_QSS)
            b.clicked.connect(slot)
            btns.addWidget(b)
        forget = QPushButton(tr("Stop using it"), box)
        forget.setStyleSheet(SMALL_BTN_QSS)
        forget.clicked.connect(lambda _=0, s=src: self._forget(s))
        btns.addWidget(forget)
        btns.addStretch(1)
        col.addLayout(btns)

        self._rows.append((src, state, forget))
        return box

    @staticmethod
    def _help(src: Source) -> str:
        return tr(
            "Three steps, and no typing of file paths:\n\n"
            "1.  Press “Save a file to fill in” and choose where to "
            "keep it. ChromIQ writes a file listing every value it can use, "
            "in the order the table shows them, with the numbers left "
            "blank.\n"
            "2.  Open that file in any text editor and type the numbers from "
            "your own copy in place of the word null. A value you leave alone "
            "goes on showing ?, so you can do a few at a time.\n"
            "3.  Press “Use a file I filled in” and pick it. ChromIQ "
            "copies it into its own folder, so the values stay even if you "
            "tidy the file away afterwards.\n\n"
            "“Stop using it” removes ChromIQ's copy and goes back to "
            "ChromIQ's own numbers. The file you made it from is never "
            "touched.\n\n"
            "The values stay on this computer. ChromIQ does not send them "
            "anywhere, they are not part of a report you share, and they are "
            "not written into any project.")

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        for src, state, forget in self._rows:
            where = src.in_use()
            if where:
                state.setText(tr("In use: {path}").format(path=where))
            else:
                state.setText(tr("Nothing supplied, so ChromIQ uses its own "
                                 "numbers and shows ? where it has none."))
            # `in_use` is the wrong question for this button. It answers "is
            # ChromIQ judging against somebody's numbers", and
            # `CHROMIQ_COMPLIANCE_ISO_FILE` makes that true without there
            # being anything here to remove -- `forget` only ever deletes
            # ChromIQ's OWN copy, returns False, and this method never runs.
            # The button then sat enabled and did NOTHING when pressed, which
            # is the fault beta 26 shipped three times over. Ask the question
            # the button actually answers.
            forget.setEnabled(src.own_copy().is_file())

    def _say(self, text: str) -> None:
        from ui.tooltip_button import InfoDialog

        InfoDialog(tr("Reference values"), text, self, min_width=520).exec()

    def _template(self, src: Source) -> None:
        from PyQt6.QtCore import QStandardPaths

        from ui.widgets import save_file_dialog

        docs = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
        # THE SIDEBAR SHORTCUT IS NOT DECORATION. Commit 758bfbbb added it to
        # both dialogs so a user could reach ChromIQ's own folder without
        # typing a path, and the move to one door dropped it from both. The
        # guard that was supposed to hold it read the slots' SOURCE, so it
        # could not notice (6d7b265c).
        where = save_file_dialog(
            self, tr("Save a file to fill in"), src.file_filter,
            start_path=str(Path(docs) / src.template_name),
            extra_paths=(str(src.own_copy().parent),))
        if not where:
            return
        try:
            src.write_template(Path(where))
        except OSError as exc:
            self._say(tr("That file could not be written: {error}")
                      .format(error=exc))
            return
        self._say(tr(
            "Saved to {path}. Open it in any text editor, type the numbers "
            "from your own copy in place of the word null, then come back and "
            "press “Use a file I filled in”.").format(path=where))

    def _install(self, src: Source) -> None:
        from PyQt6.QtCore import QStandardPaths

        from ui.widgets import open_file_dialog

        docs = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
        chosen = open_file_dialog(
            self, tr("Use a file I filled in"), src.file_filter,
            start_dir=docs,
            extra_paths=(str(src.own_copy().parent),))
        if not chosen:
            return
        try:
            dst = src.install(Path(chosen))
        except (OSError, ValueError) as exc:
            self._say(tr("ChromIQ could not read that file: {error}")
                      .format(error=exc))
            return
        self._refresh()
        self._say(tr(
            "ChromIQ is using {path} now. Close and reopen the Report limits "
            "window to see the values in the table.").format(path=dst))

    def _forget(self, src: Source) -> None:
        if src.forget():
            self._refresh()
            self._say(tr("ChromIQ is back to its own numbers. Close and "
                         "reopen the Report limits window to see the table "
                         "change."))
