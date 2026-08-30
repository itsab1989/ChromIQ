"""Ask for a project name — the one place that question is asked.

Before this existed the question was asked in three different ways. Two of them
still live in the loaders and have DRIFTED apart: one rejects `:` and sanitises
what it hands back, the other accepts it and returns the raw text; one offers an
"Overwrite" that deletes a folder outright, the other a "Replace" that archives
it. Two dialogs, the same word, opposite consequences for somebody's work.

So this module asks for a NAME and nothing else. It validates the SHAPE of what
was typed — empty, characters a folder cannot hold, something that leaves
nothing usable behind — and stops there. It never asks about collisions, never
offers to replace anything and never touches the disk. §S4.7 in Create Chart
already owns "that name is a project you already have", with three real
outcomes and knowledge of the run picker; a second, weaker version of that
question inside this dialog would let one person answer it two ways.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout,
    QWidget,
)

from core.i18n import tr
from ui.tooltip_button import TooltipButton

#: Characters a folder name cannot hold on the platforms ChromIQ ships for.
#: Kept as data so the message and the check can never disagree.
FORBIDDEN = r'/\:*?"<>|'


def _tooltip_body() -> str:
    return tr(
        "This name follows the whole job. It becomes the folder inside your "
        "ChromIQ folder, it is printed on the chart itself so you can tell two "
        "printed sheets apart months later, and it becomes the name of the ICC "
        "profile your other programs will show in their profile lists.\n\n"
        "Put in what you will want to recognise later: the printer, the paper, "
        "and — if you use more than one — the ink set. For example "
        "“Canon PRO-300 Hahnemuehle Photo Rag 308” or “Epson P900 Baryta "
        "Gloss”.\n\n"
        "Leave out the date and the number of patches. ChromIQ records both by "
        "itself, and a date in the name only makes the folder look out of date "
        "later.\n\n"
        "You can use letters, numbers, spaces, hyphens and full stops. Spaces "
        "become hyphens in the folder name. The characters / \\ : * ? \" < > | "
        "cannot be used, because a folder cannot contain them.\n\n"
        "Nothing here is permanent. Rename the project whenever you like and "
        "ChromIQ offers to move the folder, the chart files and the profile "
        "with it."
    )


def validate(text: str) -> str | None:
    """The reason *text* cannot be used as a project name, or None if it can.

    SHAPE ONLY — see the module docstring. Nothing here reads the disk.
    """
    name = (text or "").strip()
    if not name:
        return tr("Type a name to continue.")
    if any(c in name for c in FORBIDDEN):
        return tr("A folder name cannot contain / \\ : * ? \" < > | — please "
                  "use letters, numbers, spaces or hyphens instead.")
    # A name made only of punctuation passes the check above and then sanitises
    # away to nothing, at which point `FileManager._sanitise` substitutes
    # "session" and the build quietly lands in a folder nobody chose. Asking for
    # one letter or number now is cheaper than that surprise later. Checked
    # here rather than by calling the sanitiser, so this stays a statement about
    # what the USER typed and cannot drift with the sanitiser's fallbacks.
    # A FOLDER NAME HAS A LENGTH LIMIT, AND FAILING LATE IS EXPENSIVE.
    # macOS and most Linux filesystems cap a single name at 255 BYTES; a 250
    # character name passed validation, reached `mkdir`, died with Errno 63
    # ("File name too long") and left a half-built project on disk. Bytes, not
    # characters — one emoji is four of them. 120 leaves generous room for the
    # suffixes ChromIQ appends to files inside the folder.
    if len(name.encode("utf-8")) > 120:
        return tr("That name is too long for a folder. Please shorten it to "
                  "about 120 characters or fewer.")
    if not any(ch.isalnum() for ch in name):
        return tr("That name has no letters or numbers in it, so ChromIQ "
                  "cannot make a folder from it. Please add some.")
    return None


def ask_for_project_name(parent: QWidget | None, *, prefill: str = "",
                         body: str | None = None) -> str | None:
    """Ask for the project name and return it, or None if the user cancelled.

    The caller is expected to CARRY ON with the returned name rather than send
    the user away to type it somewhere else: the dialog this replaced explained
    the fix, closed, and left the person to repeat the action they had just
    taken.
    """
    title = tr("Give this project a name")
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(560)
    dlg.setWindowFlags(dlg.windowFlags()
                       & ~Qt.WindowType.WindowContextHelpButtonHint)
    text_color = dlg.palette().color(QPalette.ColorRole.WindowText).name()

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(20, 20, 20, 16)
    lay.setSpacing(12)

    heading = QLabel(title, dlg)
    heading.setStyleSheet(
        f"font-size: 15px; font-weight: bold; color: {text_color};")
    heading.setWordWrap(True)
    lay.addWidget(heading)

    info = QLabel(body or tr(
        "Before ChromIQ can make your chart it needs a name for the project. "
        "The name is used for everything this project produces: the folder "
        "that holds all the files, the name printed on the chart itself, and "
        "the finished ICC profile.\n\n"
        "Type the name below and click “Continue”. A name that says which "
        "printer and paper this is for works best, for example “Canon PRO-300 "
        "Baryta Gloss”. You can change it later, and ChromIQ will offer to "
        "rename the folder for you."), dlg)
    info.setWordWrap(True)
    info.setTextFormat(Qt.TextFormat.PlainText)
    info.setStyleSheet(f"color: {text_color};")
    lay.addWidget(info)

    row = QHBoxLayout()
    row.setSpacing(6)
    edit = QLineEdit(dlg)
    edit.setPlaceholderText(tr("e.g. Canon PRO-300 Baryta Gloss"))
    edit.setText(prefill or "")
    edit.selectAll()
    row.addWidget(edit, 1)
    row.addWidget(TooltipButton(tr("Choosing a project name"),
                                _tooltip_body(), dlg), 0)
    lay.addLayout(row)

    err = QLabel("", dlg)
    err.setWordWrap(True)
    err.setStyleSheet("color: #e05555;")
    lay.addWidget(err)

    box = QDialogButtonBox(dlg)
    ok = box.addButton(tr("Continue"), QDialogButtonBox.ButtonRole.AcceptRole)
    box.addButton(tr("Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
    ok.setDefault(True)
    lay.addWidget(box)

    def _revalidate(*_a) -> None:
        why = validate(edit.text())
        # SAY NOTHING ABOUT AN EMPTY BOX. The field starts empty, and greeting
        # somebody with an error for not having typed yet reads as a telling-off.
        err.setText("" if (why is None or not edit.text().strip()) else why)
        ok.setEnabled(why is None)

    edit.textChanged.connect(_revalidate)
    box.accepted.connect(dlg.accept)
    box.rejected.connect(dlg.reject)
    _revalidate()
    edit.setFocus()

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return edit.text().strip() or None
