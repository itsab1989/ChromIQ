"""Choose one of your projects from a list, instead of remembering its name.

WHY THIS EXISTS. The import asks which project a measurement belongs in, and
the first answer was to type the name — which reuses the name box, its live
validation and its "this name is taken" line, and invents nothing. That is
right for somebody who remembers the name. With twenty-odd projects it is not:
typing beats picking only when you already know what to type, and ChromIQ had
no way to see the list at all. There is no project chooser anywhere in the app
— Open Project is a file dialog on `project.json` — so this is the first one.

WHAT IT SHOWS, AND WHY. Each row names the project and says what it holds, from
`peek_project`, which reads `project.json` as plain JSON and looks at the run
folder with `glob`. It never calls `Project.load`, because loading MIGRATES a
folder in place and this list is drawn while somebody is merely looking.

Rows are ordered most-recently-changed first: the project you want is almost
always the one you were last working in.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QWidget,
)

from core.i18n import count_phrase, tr

log = logging.getLogger(__name__)

#: More than this and the list is scrolled rather than grown.
_VISIBLE_ROWS = 12


def _holds_phrase(peek) -> str:
    """What this project holds, in a person's words and count-aware."""
    bits: list[str] = []
    if peek.runs:
        bits.append(count_phrase(len(peek.runs), tr("1 run"), tr("{n} runs")))
    if peek.measurement:
        bits.append(tr("a measurement"))
    if peek.profile:
        bits.append(tr("a profile"))
    if peek.verifications:
        bits.append(count_phrase(peek.verifications, tr("1 verification"),
                                 tr("{n} verifications")))
    if peek.calibration:
        bits.append(tr("a calibration"))
    if not bits:
        return tr("empty")
    return ", ".join(bits)


def list_projects(working_dir: "Path | str") -> "list[tuple[str, object]]":
    """``[(name, peek)]`` for every project directly under *working_dir*.

    Only one level down, deliberately: a project may be organised in a
    sub-folder, but walking the whole tree would read every folder on the disk
    to draw a list. Anything deeper is still reachable by typing its name.
    """
    from core.file_manager import peek_project
    root = Path(working_dir)
    out: list[tuple[str, object]] = []
    try:
        entries = sorted(root.iterdir())
    except OSError:
        return out
    for child in entries:
        try:
            if not (child / "project.json").is_file():
                continue
            out.append((child.name, peek_project(child)))
        except OSError:
            continue
    # Most recently touched first — the one you want is usually the last one
    # you worked in. A folder whose mtime cannot be read sorts last rather than
    # taking the whole list down with it.
    def _when(pair):
        try:
            return (root / pair[0]).stat().st_mtime
        except OSError:
            return 0.0
    out.sort(key=_when, reverse=True)
    return out


#: Returned when the person wants a NEW project rather than one in the list.
#: A distinct value, not None: "I want a new one" and "stop, I have changed my
#: mind" are different answers, and a Cancel that quietly means "make a new
#: project" is how a person ends up with a project they never asked for.
NEW_PROJECT = "\x00new"


def choose_project(parent: "QWidget | None", working_dir: "Path | str", *,
                   title: str = "", body: str = "",
                   accent: str = "") -> "str | None":
    """Show the list and return the chosen project's name.

    Returns the name, :data:`NEW_PROJECT` when the person wants a new one, or
    None when they cancelled. The caller answers "new" by asking for a name —
    which is how a new project is made everywhere else in ChromIQ, so there is
    still exactly one window for that question.
    """
    projects = list_projects(working_dir)
    if not projects:
        return None

    dlg = QDialog(parent)
    dlg.setWindowTitle(title or tr("Which project?"))
    dlg.setMinimumWidth(560)
    dlg.setWindowFlags(dlg.windowFlags()
                       & ~Qt.WindowType.WindowContextHelpButtonHint)
    text_color = dlg.palette().color(QPalette.ColorRole.WindowText).name()

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(20, 20, 20, 16)
    lay.setSpacing(12)

    heading = QLabel(title or tr("Which project?"), dlg)
    heading.setStyleSheet(
        f"font-size: 15px; font-weight: bold; color: {text_color};")
    heading.setWordWrap(True)
    lay.addWidget(heading)

    if body:
        info = QLabel(body, dlg)
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.PlainText)
        info.setStyleSheet(f"color: {text_color};")
        lay.addWidget(info)

    lst = QListWidget(dlg)
    for name, peek in projects:
        item = QListWidgetItem(f"{name}   —   {_holds_phrase(peek)}", lst)
        item.setData(Qt.ItemDataRole.UserRole, name)
    lst.setCurrentRow(0)
    # NO SIDEWAYS SCROLLING. A real project name can be 70 characters
    # ("Red-River-Paper-ColorMunki-_-Letter-2052p-10pages-Standard-Patch-Set-v25"),
    # and a horizontal scrollbar hid what each project HOLDS off the right-hand
    # edge — the one thing on the row that helps you choose. The name is elided
    # in the middle instead, which keeps both ends: the paper at the front and
    # the version at the back are what tell two of these apart.
    lst.setTextElideMode(Qt.TextElideMode.ElideMiddle)
    lst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    lst.setWordWrap(False)
    # HEIGHT IN ROWS, MEASURED — not in a guessed pixel constant. A first
    # version said `rows * 24`, and a row is 17 px here: the cap meant
    # seventeen rows rather than the twelve it claimed, and on a bigger UI font
    # (or another language, or a HiDPI setting) it would have meant six. Ask
    # the list how tall its own row is.
    _row_h = max(1, lst.sizeHintForRow(0))
    _frame = 2 * lst.frameWidth() + 4
    _rows = min(len(projects), _VISIBLE_ROWS)
    lst.setMinimumHeight(_rows * _row_h + _frame)
    # …AND A CEILING, so a long list cannot push the buttons off the bottom of
    # the screen where they cannot be clicked.
    lst.setMaximumHeight(_VISIBLE_ROWS * _row_h + _frame)
    lay.addWidget(lst)

    # A PLAIN ROW, NOT A QDialogButtonBox.
    #
    # A button box lays its buttons out BY ROLE, and on macOS that produced
    # "Make a new project instead · Cancel · Choose this project" — the action
    # last and Cancel wedged in the middle, which is the arrangement Basti has
    # ruled against twice. The order here is his: the thing you came to do
    # first, then the alternative, and **Cancel on the very right**.
    row = QHBoxLayout()
    row.setSpacing(8)
    ok = QPushButton(tr("Choose this project"), dlg)
    # THE APP'S OWN BUTTON STYLING, not the platform's. Every other dialog in
    # ChromIQ names its main button `primary` and has the tab's accent stamped
    # on it by `tint_dialog_primary`; a new dialog that skips both arrives in
    # bare macOS grey and looks like it belongs to a different program.
    ok.setObjectName("primary")
    ok.setDefault(True)
    new_btn = QPushButton(tr("Make a new project instead"), dlg)
    new_btn.setAutoDefault(False)
    cancel_btn = QPushButton(tr("Cancel"), dlg)
    cancel_btn.setAutoDefault(False)
    # EACH BUTTON AS WIDE AS ITS OWN WORDS, not an equal third of the row.
    # Equal stretch clipped the longest label to "ke a new project inste" —
    # `fit_button_width` is "the one place button widths are decided" (Knut,
    # #130) and exists because a button sizes itself before ButtonFontFilter
    # swaps it to a wider face. Stretch goes between the doing buttons and
    # Cancel, so Cancel sits hard right.
    from ui.widgets import fit_button_width
    for b in (ok, new_btn, cancel_btn):
        fit_button_width(b)
    row.addWidget(ok)
    row.addWidget(new_btn)
    row.addStretch(1)
    row.addWidget(cancel_btn)
    lay.addLayout(row)

    picked: list = [None]

    def _accept():
        item = lst.currentItem()
        picked[0] = (item.data(Qt.ItemDataRole.UserRole)
                     if item is not None else None)
        dlg.accept()

    if accent:
        from ui.widgets import tint_dialog_primary
        tint_dialog_primary(dlg, accent)
    ok.clicked.connect(_accept)
    cancel_btn.clicked.connect(dlg.reject)
    new_btn.clicked.connect(lambda: (picked.__setitem__(0, NEW_PROJECT),
                                     dlg.accept()))
    lst.itemDoubleClicked.connect(lambda _i: _accept())

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return picked[0]
