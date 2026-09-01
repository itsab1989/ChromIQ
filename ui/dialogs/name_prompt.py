"""Ask for a project name — the one place that question is asked.

Before this existed the question was asked in three different ways. Two of them
still live in the loaders and have DRIFTED apart: one rejects `:` and sanitises
what it hands back, the other accepts it and returns the raw text; one offers an
"Overwrite" that deletes a folder outright, the other a "Replace" that archives
it. Two dialogs, the same word, opposite consequences for somebody's work.

So this module asks for a NAME and nothing else. It validates the SHAPE of what
was typed — empty, characters a folder cannot hold, something that leaves
nothing usable behind — and stops there.

It never DECIDES anything about a collision, never offers to replace anything,
and never reads the disk itself. It will SAY that a name is already taken, but
only because the caller hands it an `exists` callback to ask; the module has no
idea how that question is answered. §S4.7 in Create Chart owns the decision,
with three real outcomes and knowledge of the run picker; a second, weaker
version of that question inside this dialog would let one person answer it two
ways.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import tr
from ui.styles import SPEC_MAGENTA
from ui.tooltip_button import TooltipButton

#: Characters a folder name cannot hold on the platforms ChromIQ ships for.
#: Kept as data so the message and the check can never disagree.
FORBIDDEN = r'/\:*?"<>|'

#: Names Windows reserves for devices. They are refused on every platform, not
#: only on Windows: ChromIQ projects are copied between machines and shared, and
#: a folder that cannot be created on one of them is a trap the person springs
#: later, on somebody else's computer. The extension is irrelevant to Windows —
#: `CON.txt` is reserved too — so the stem is what is checked.
RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{i}" for i in range(1, 10)]
    + [f"LPT{i}" for i in range(1, 10)]
)


def folder_name(text: str) -> str:
    """The folder ChromIQ will actually create for *text*.

    Shown live under the field, because the name typed and the folder made are
    not always the same string and the differences are silent: spaces become
    hyphens, and anything outside letters, digits, hyphen and dot is dropped —
    so "🎨🎨1" becomes "1" and an accented name typed in one Unicode form is
    stored in another. Telling the person what they are about to get is
    cheaper than explaining it afterwards.
    """
    from core.file_manager import FileManager
    return FileManager._sanitise(FileManager.strip_workfile_ext(text or ""))


def _tooltip_body() -> str:
    return tr(
        "This name follows the whole job. It becomes the folder inside your "
        "ChromIQ folder, it is printed on the chart itself so you can tell two "
        "printed sheets apart months later, and it becomes the name of the ICC "
        "profile your other programs will show in their profile lists.\n\n"
        "Put in what you will want to recognise later: the printer, the paper, "
        "and, if you use more than one, the ink set. For example "
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
        return tr("A folder name cannot contain / \\ : * ? \" < > or |. Please "
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
    # A LEADING DOT MAKES A FOLDER THAT HIDES ITSELF, and "where are my files?"
    # must always have an answer. The sanitiser drops it silently, so the person
    # would get a differently-named folder without being told.
    if name.startswith("."):
        return tr("A name cannot start with a dot, because that makes a folder "
                  "your computer hides. Please start with a letter or a number.")
    # JUDGE THE FOLDER, NOT ONLY WHAT WAS TYPED. `validate` reads the typed
    # string while the filesystem sees what `_sanitise` makes of it, and the two
    # differ: "CON!" passes a check on the typed name and then creates a folder
    # called "CON".
    if (name.split(".")[0].upper() in RESERVED
            or folder_name(name).split(".")[0].upper() in RESERVED):
        return tr("“{name}” is a name Windows keeps for itself, so a folder "
                  "cannot be called that. Please choose another one.").format(
                      name=name)
    return None



def _centre_on_parent(dlg) -> None:
    """Open over the window that asked, not in the corner of the screen.

    A dialog is placed the moment it is shown, and both of these windows are
    RESIZED after that -- to the height their own words need. Qt does not move
    a window it has already placed, so the finished dialog sat wherever the
    smaller one had been put: hard against the top-left of the display, half
    off the app (Basti, screenshot, beta 5). Centring explicitly, after the
    final size is known, is the only order that survives a resize.
    """
    from PyQt6.QtWidgets import QApplication
    parent = dlg.parentWidget()
    host = parent.window() if parent is not None else None
    try:
        area = (host.frameGeometry() if host is not None and host.isVisible()
                else (dlg.screen() or QApplication.primaryScreen()).availableGeometry())
        frame = dlg.frameGeometry()
        frame.moveCenter(area.center())
        dlg.move(frame.topLeft())
    except Exception:          # noqa: BLE001 — never fail to open a window
        pass


def _wear_the_tab_accent(dlg, accent: str) -> None:
    """Focus ring and list selection in the accent of the tab that asked.

    The application stylesheet paints both from one global blue
    (`ui/light_styles.ACCENT_BLUE`), which is right for the main window's own
    inputs and wrong here: these dialogs are handed the accent of the tab that
    opened them, tint their primary button with it, and then drew a blue ring
    around the name field and a blue bar across the chosen project (Basti,
    screenshots, 2026-09-01). Stamped on the DIALOG so nothing outside it is
    touched, and only when an accent was actually given.
    """
    if not accent:
        return
    try:
        r, g, b = (int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16))
    except (ValueError, IndexError):
        return
    # Dark text on the accent, the same rule `tint_dialog_primary` uses: these
    # accents are all light enough that white on them fails to read.
    on_accent = "#0a0a0a" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "#ffffff"
    dlg.setStyleSheet((dlg.styleSheet() or "") + f"""
        QLineEdit:focus, QComboBox:focus {{ border-color: {accent}; }}
        QListWidget {{ selection-background-color: {accent};
                       selection-color: {on_accent}; }}
        QListWidget::item:selected {{ background: {accent}; color: {on_accent}; }}
    """)

def ask_for_project_name(parent: QWidget | None, *, prefill: str = "",
                         body: str | None = None,
                         exists=None, accent: str = "") -> str | None:
    """Ask for the project name and return it, or None if the user cancelled.

    The caller is expected to CARRY ON with the returned name rather than send
    the user away to type it somewhere else: the dialog this replaced explained
    the fix, closed, and left the person to repeat the action they had just
    taken.

    *exists* is an optional callback ``(name) -> bool`` answering whether that
    name already belongs to a project. Passed IN rather than looked up here, so
    this module keeps its promise never to touch the disk — and so the dialog
    and the line under the main window's name box answer from one piece of
    code instead of two that drift.
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
    # THE SAME ACCENT AS THE BUTTON BESIDE IT. `TooltipButton` falls back to a
    # CLASS attribute that the main window rewrites on every tab change, so
    # this ⓘ wore whichever tab had last been visited: opened from Build
    # Profile it came out magenta beside a cyan Continue button (Basti,
    # 2026-08-31). The dialog already knows its accent; it just never handed
    # it over.
    row.addWidget(TooltipButton(tr("Choosing a project name"),
                                _tooltip_body(), dlg,
                                color=accent or None), 0)
    lay.addLayout(row)

    # WHAT THE FOLDER WILL ACTUALLY BE CALLED, but only when that differs from
    # what was typed. Shown then and only then, the same way the main window's
    # "you already have a project with this name" line appears only when it
    # applies: a line that is always there is furniture, and a line that appears
    # is a signal. Spaces become hyphens and anything unusual is dropped, so
    # this is where somebody finds out that "🎨🎨1" makes a folder called "1"
    # — before it happens, rather than in the Finder afterwards.
    # ALREADY-EXISTS NOTICE. Ordinary text colour, not the error red: this is
    # not a refusal and it never blocks Continue. §S4.7 still owns the DECISION
    # — which is why this says only what is there, and nothing about what will
    # happen next.
    exists_lbl = QLabel("", dlg)
    exists_lbl.setWordWrap(True)
    exists_lbl.setTextFormat(Qt.TextFormat.PlainText)
    # THE SAME ACCENT AS THE LINE UNDER THE NAME BOX (Basti, 2026-08-31). It is
    # the same sentence about the same fact, so it must not arrive in a
    # different colour depending on which window the person is looking at.
    exists_lbl.setStyleSheet(f"color: {SPEC_MAGENTA}; font-size: 11px;")
    lay.addWidget(exists_lbl)

    folder_lbl = QLabel("", dlg)
    folder_lbl.setWordWrap(True)
    folder_lbl.setTextFormat(Qt.TextFormat.PlainText)
    folder_lbl.setStyleSheet(f"color: {text_color};")
    lay.addWidget(folder_lbl)

    err = QLabel("", dlg)
    err.setWordWrap(True)
    err.setStyleSheet("color: #e05555;")
    lay.addWidget(err)

    # A PLAIN ROW, NOT A QDialogButtonBox. A button box lays out BY ROLE, and
    # on macOS that puts Cancel on the LEFT — Basti's rule is that Cancel is
    # always on the very right, with the thing you came to do first.
    row = QHBoxLayout()
    row.setSpacing(8)
    ok = QPushButton(tr("Continue"), dlg)
    ok.setObjectName("primary")      # the app's styling, not the platform's
    ok.setDefault(True)
    cancel_btn = QPushButton(tr("Cancel"), dlg)
    cancel_btn.setAutoDefault(False)
    # Each button as wide as its own words — `fit_button_width` is "the one
    # place button widths are decided" (Knut, #130), and a button that sizes
    # itself before ButtonFontFilter swaps the face paints a clipped label.
    from ui.widgets import fit_button_width
    for b in (ok, cancel_btn):
        fit_button_width(b)
    row.addStretch(1)
    row.addWidget(ok)
    row.addWidget(cancel_btn)
    lay.addLayout(row)

    def _revalidate(*_a) -> None:
        typed = edit.text().strip()
        why = validate(edit.text())
        # SAY NOTHING ABOUT AN EMPTY BOX. The field starts empty, and greeting
        # somebody with an error for not having typed yet reads as a telling-off.
        err.setText("" if (why is None or not typed) else why)
        ok.setEnabled(why is None)
        made = folder_name(typed) if (typed and why is None) else ""
        folder_lbl.setText(
            tr("Your files will be in a folder called “{folder}”.").format(
                folder=made) if made and made != typed else "")
        _known = False
        if exists is not None and typed and why is None:
            try:
                _known = bool(exists(typed))
            except Exception:      # noqa: BLE001 — a notice may never block
                _known = False
        exists_lbl.setText(
            tr("You already have a project with this name.") if _known else "")

    if accent:
        from ui.widgets import tint_dialog_primary
        tint_dialog_primary(dlg, accent)
        _wear_the_tab_accent(dlg, accent)
    edit.textChanged.connect(_revalidate)
    ok.clicked.connect(dlg.accept)
    cancel_btn.clicked.connect(dlg.reject)
    _revalidate()
    edit.setFocus()

    # OPEN AT THE HEIGHT THE WORDS ACTUALLY NEED, not the one computed for a
    # width the window may not get. A word-wrapped QLabel's height is only
    # valid at the width it was measured for, so on a display too narrow for
    # this dialog's natural 679 px the body kept the height of the wider
    # layout and the text was simply cut off -- measured at 560 px, where the
    # first and last paragraphs were sliced through the middle with nothing
    # to say anything was missing. `pin_min_height` is the project's existing
    # answer to this (three tool dialogs already use it); it pins each
    # wrapping label to its true heightForWidth, then floors the dialog so it
    # can never be dragged short enough to overlap either.
    from ui.dialog_sizing import pin_min_height
    # The same floor rule as the project picker beside it: 560 is a number that
    # fits English, and a dialog may not be draggable into a state where its
    # own buttons overlap. Cheap here (two short buttons) and consistent.
    from ui.dialogs.project_picker import _width_the_buttons_need
    _need_w = _width_the_buttons_need(row, dlg)
    dlg.setMinimumWidth(_need_w)
    pin_min_height(dlg, min_width=_need_w,
                   wrap_labels=(heading, info, exists_lbl, folder_lbl, err),
                   inner_margins=lay.contentsMargins(), resize_width=True)
    _centre_on_parent(dlg)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return edit.text().strip() or None
