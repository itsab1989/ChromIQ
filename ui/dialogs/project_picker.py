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
#: The person would rather ChromIQ worked on the file where it lies, filing
#: nothing. Offered only where the caller asks for it — see
#: `docs/design/import_doors_amendment.md` §2.
IN_PLACE = "\x00in-place"



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


#: The narrowest the space between the doing buttons and Cancel may become.
#: Cancel ends a journey and the others continue it, so they must never read as
#: one group of three.
_CANCEL_GAP = 24


def _width_the_buttons_need(row, dlg, floor: int = 560) -> int:
    """The narrowest the dialog may be before its buttons collide.

    `setMinimumWidth(560)` was a number that happens to fit English. In German
    "Stattdessen neues Projekt anlegen" runs 38 px wider than the space left
    for it and Cancel was drawn over its last word — measured at the dialog's
    own minimum width. The buttons have already been sized to their own words
    by `fit_button_width`, so the row can simply be asked how much it needs.
    """
    try:
        # `fit_button_width` states its answer as `setMinimumWidth`, and the
        # size hint does not yet carry it — reading the hint alone returned
        # 560 for a row that needed 570 and the overlap stayed.
        need = sum(max(w.sizeHint().width(), w.minimumWidth())
                   for w in (row.itemAt(i).widget() for i in range(row.count()))
                   if w is not None)
        need += row.spacing() * max(0, row.count() - 1)
        need += _CANCEL_GAP                 # the floor added above
        m = dlg.layout().contentsMargins()
        return max(floor, need + m.left() + m.right() + 24)
    except Exception:          # noqa: BLE001 — never fail to open a window
        return floor


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

def choose_project(parent: "QWidget | None", working_dir: "Path | str", *,
                   title: str = "", body: str = "",
                   accent: str = "",
                   offer_in_place: bool = False) -> "str | None":
    """Show the list and return the chosen project's name.

    Returns the name, :data:`NEW_PROJECT` when the person wants a new one, or
    None when they cancelled. The caller answers "new" by asking for a name —
    which is how a new project is made everywhere else in ChromIQ, so there is
    still exactly one window for that question.
    """
    projects = list_projects(working_dir)
    if not projects and not offer_in_place:
        return None
    # …BUT AN EMPTY FOLDER STILL HAS TO OFFER THE THIRD ANSWER. With no
    # projects yet this returned before drawing anything, so a new user could
    # never reach "Just check it where it is" — the whole point of which is
    # that you do not have to make a project first (challenge round,
    # 2026-09-01). The list is simply empty and the two answers that do not
    # need it still stand.

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

    info = None            # …there may be no body at all; see pin_min_height
    if body:
        info = QLabel(body, dlg)
        info.setWordWrap(True)
        info.setTextFormat(Qt.TextFormat.PlainText)
        info.setStyleSheet(f"color: {text_color};")
        lay.addWidget(info)

    lst = QListWidget(dlg)
    for name, peek in projects:
        item = QListWidgetItem(f"{name}   ·   {_holds_phrase(peek)}", lst)
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
    # AN EMPTY LIST HAS NO ROW TO MEASURE. `sizeHintForRow(0)` returns -1 with
    # nothing in it, so `max(1, …)` gave a one-pixel row and the whole box came
    # out 18 px tall: a sliver that reads as a broken text field, under a
    # sentence telling you to choose from it. Fall back to the font's own line
    # height, and say in the box itself that there is nothing to choose yet.
    _row_h = lst.sizeHintForRow(0)
    if _row_h <= 0:
        _row_h = lst.fontMetrics().height() + 8
    _frame = 2 * lst.frameWidth() + 4
    _rows = min(len(projects), _VISIBLE_ROWS) if projects else 3
    lst.setMinimumHeight(_rows * _row_h + _frame)
    if not projects:
        _none = QListWidgetItem(
            tr("You have no projects yet. Make one, or check the file where "
               "it is."))
        _none.setFlags(Qt.ItemFlag.NoItemFlags)
        lst.addItem(_none)
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
    # NOT THE DEFAULT WHEN THERE IS NOTHING TO CHOOSE. With an empty folder
    # "Choose this project" has no row behind it: pressing Return dismissed the
    # window and returned None, which the caller reads as Cancel. The first
    # answer that can actually do something takes the default instead.
    ok.setEnabled(bool(projects))
    ok.setDefault(bool(projects))
    ok.setAutoDefault(bool(projects))
    new_btn = QPushButton(tr("Make a new project instead"), dlg)
    new_btn.setAutoDefault(not projects)
    new_btn.setDefault(not projects)
    # THE IN-PLACE ANSWER SITS AFTER THE FILING ANSWERS, never first and never
    # the default (§2.4 of the amendment): filing is what keeps the work
    # together, and the easy path must not be the one that loses the history.
    place_btn = None
    if offer_in_place:
        place_btn = QPushButton(tr("Just check it where it is"), dlg)
        place_btn.setAutoDefault(False)
    cancel_btn = QPushButton(tr("Cancel"), dlg)
    cancel_btn.setAutoDefault(False)
    # EACH BUTTON AS WIDE AS ITS OWN WORDS, not an equal third of the row.
    # Equal stretch clipped the longest label to "ke a new project inste" —
    # `fit_button_width` is "the one place button widths are decided" (Knut,
    # #130) and exists because a button sizes itself before ButtonFontFilter
    # swaps it to a wider face. Stretch goes between the doing buttons and
    # Cancel, so Cancel sits hard right.
    from ui.widgets import fit_button_width
    for b in (ok, new_btn, place_btn, cancel_btn):
        if b is not None:
            fit_button_width(b)
    row.addWidget(ok)
    row.addWidget(new_btn)
    if place_btn is not None:
        row.addWidget(place_btn)
    # A FLOOR UNDER THE GAP, not only a stretch. `addStretch(1)` collapses to
    # nothing when the row is tighter than its buttons want, and Cancel then
    # sits flush against "Make a new project instead" — reported from a real
    # window (Basti, 2026-09-02) which I could not reproduce at any width down
    # to 570 px, so the trigger is something about that session rather than the
    # arithmetic. A fixed minimum makes it impossible to reach whatever the
    # cause was: the two groups can never be closer than this, and the stretch
    # still pushes Cancel hard right whenever there is room.
    row.addSpacing(_CANCEL_GAP)
    row.addStretch(1)
    row.addWidget(cancel_btn)
    lay.addLayout(row)

    picked: list = [None]

    def _accept():
        item = lst.currentItem()
        picked[0] = (item.data(Qt.ItemDataRole.UserRole)
                     if item is not None else None)
        dlg.accept()

    # THE SAME SIZING RULE AS THE NAME BOX BESIDE IT (see name_prompt): open
    # at the height these words need at THIS width, and never be shorter than
    # the layout's own floor.
    from ui.dialog_sizing import pin_min_height
    # THE FLOOR ITSELF, not just the opening width. `pin_min_height` resizes
    # the dialog, but `setMinimumWidth(560)` above still says how narrow it may
    # be dragged — and at 560 the German buttons overlap by 10 px, with Cancel
    # drawn over the last word of "Stattdessen neues Projekt anlegen".
    _need_w = _width_the_buttons_need(row, dlg)
    dlg.setMinimumWidth(_need_w)
    pin_min_height(dlg, min_width=_need_w,
                   wrap_labels=tuple(w for w in (heading, info) if w is not None),
                   inner_margins=lay.contentsMargins(), resize_width=True)
    _centre_on_parent(dlg)

    if accent:
        from ui.widgets import tint_dialog_primary
        tint_dialog_primary(dlg, accent)
        _wear_the_tab_accent(dlg, accent)
    ok.clicked.connect(_accept)
    cancel_btn.clicked.connect(dlg.reject)
    if place_btn is not None:
        place_btn.clicked.connect(lambda: (picked.__setitem__(0, IN_PLACE),
                                           dlg.accept()))
    new_btn.clicked.connect(lambda: (picked.__setitem__(0, NEW_PROJECT),
                                     dlg.accept()))
    lst.itemDoubleClicked.connect(lambda _i: _accept())

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return picked[0]
