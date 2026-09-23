"""Dialog shown when the user generates a chart under a new target name while a
previously-created target folder still exists on disk.

Every project lives in its own folder ``~/ChromIQ/<target-name>/`` (see
``core/file_manager.py``). Changing the Output name and pressing Generate again
would silently leave the first folder orphaned. This dialog makes the situation
explicit and offers three clearly-explained choices plus Cancel.

The dialog is purely a chooser — it performs no file operations. The caller
(``ui/tabs/tab_chart.py``) reads ``result_action()`` and carries out the move /
delete / nothing using ``FileManager`` / ``Project``.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from core.i18n import tr
from core.trash import trash_name


class TargetChangeAction(Enum):
    """What the user chose to do about the old target folder."""
    CANCEL = "cancel"   # dialog rejected — don't generate at all
    RENAME = "rename"   # move the old folder to the new name, then regenerate
    KEEP   = "keep"     # leave the old folder, create a fresh one under the new name
    DELETE = "delete"   # delete the old folder, create a fresh one under the new name


class TargetChangeDialog(QDialog):
    """Ask the user what to do with the existing target folder on a rename.

    Order is most-likely-intent / least-destructive first, destructive last:
    Rename → Keep both → Delete old. The default (highlighted) button is Rename,
    which is the usual reason someone changes the name after a first generate.
    """

    def __init__(
        self,
        old_name: str,
        new_name: str,
        old_root: Path,
        new_root: Path,
        parent: QWidget | None = None,
        *,
        folder_renamed: bool = False,
        built_profile: bool = False,
    ) -> None:
        super().__init__(parent)
        self._action = TargetChangeAction.CANCEL
        #: #182 K26: the project was OPENED from a folder whose name is not
        #: the name its files carry (a Finder duplicate, "X copy"), rather
        #: than renamed in the name field. Same window, two choices.
        self._folder_renamed = bool(folder_renamed)
        self._built_profile = bool(built_profile)
        self.setWindowTitle(tr("Rename Printer Profile"))
        self.setMinimumWidth(580)
        # Cap generously: the option titles embed the (variable-length) target
        # names, so the dialog must be able to grow wide enough to show them in
        # full — see the per-button setMinimumWidth in _option_button (#52).
        self.setMaximumWidth(1100)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui(old_name, new_name, old_root, new_root)

    # ------------------------------------------------------------------

    def _build_ui(
        self, old_name: str, new_name: str, old_root: Path, new_root: Path
    ) -> None:
        text_color = self.palette().color(QPalette.ColorRole.WindowText).name()
        muted = "#9a9a9a"

        outer = QVBoxLayout(self)
        if self._folder_renamed:
            self._build_folder_renamed_ui(outer, old_name, new_name, old_root,
                                          new_root, text_color, muted)
            return
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)

        heading = QLabel(
            tr("You already created the profile \"{old_name}\", and have now asked for one called \"{new_name}\".").format(old_name=old_name, new_name=new_name),
            self,
        )
        heading.setWordWrap(True)
        heading.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {text_color};"
        )
        outer.addWidget(heading)

        intro = QLabel(
            tr("Each profile is a separate folder on disk. Changing the name points "
            "ChromIQ at a different folder, so the work you already created would "
            "be left behind. What would you like to do?"),
            self,
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {text_color};")
        outer.addWidget(intro)

        # Show the two folders so the user can see exactly what is affected.
        paths = QLabel(
            tr("Existing:  {old}\nNew name:  {new}").format(
                old=old_root, new=new_root),
            self,
        )
        paths.setWordWrap(True)
        paths.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        paths.setStyleSheet(
            f"color: {muted}; font-family: Menlo, Consolas, 'Courier New', monospace; font-size: 12px;"
        )
        outer.addWidget(paths)

        outer.addWidget(self._divider())

        # --- the three choices, most-likely / least-destructive first ---
        outer.addWidget(
            self._option_button(
                tr('Rename the existing profile to "{new}"').format(new=new_name),
                tr('Recommended when you deliberately intended to change the profile '
                   'name. ChromIQ moves the existing folder to "{new}", keeping '
                   'everything inside it (calibration, any earlier runs), and then '
                   'regenerates the chart so the printed sheet and files carry the '
                   'new name. You end up with one profile, correctly named.\n\n'
                   'In the rare case that a file you added yourself already has the '
                   'name one of the renamed files needs, that file is kept and moved '
                   'aside with "_conflicted_at_renaming_procedure" added to its name, '
                   'so nothing is lost and the profile\'s own files still end up '
                   'correctly named.').format(new=new_name),
                TargetChangeAction.RENAME,
                primary=True,
            )
        )
        outer.addWidget(
            self._option_button(
                tr('Create "{new}" and keep "{old}"').format(new=new_name, old=old_name),
                tr('Safest option — nothing is deleted. ChromIQ creates a brand-new '
                   'profile for "{new}" and leaves the existing "{old}" '
                   'folder exactly as it is. You will have two separate profiles on '
                   'disk.').format(new=new_name, old=old_name),
                TargetChangeAction.KEEP,
            )
        )
        outer.addWidget(
            self._option_button(
                tr('Create "{new}" and delete "{old}"').format(new=new_name, old=old_name),
                tr('ChromIQ creates the new "{new}" profile and moves the old '
                   '"{old}" folder to your {trash} with everything inside it '
                   '(charts, measurements, profiles). You can put it back from '
                   'there until you empty it, and the space on your disk comes '
                   'back once you do.').format(new=new_name, old=old_name,
                                               trash=trash_name()),
                TargetChangeAction.DELETE,
                danger=True,
            )
        )

        outer.addWidget(self._divider())

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        cancel_btn = QPushButton(tr("Cancel"), self)
        cancel_btn.clicked.connect(self.reject)
        cancel_row.addWidget(cancel_btn)
        outer.addLayout(cancel_row)

    # ------------------------------------------------------------------

    def _build_folder_renamed_ui(self, outer, old_name: str, new_name: str,
                                 old_root: Path, new_root: Path,
                                 text_color: str, muted: str) -> None:
        """The same window for a project OPENED from a folder whose name is
        not the name its files carry (#182 K26, Knut 5792484060, Q5): *"the
        user should be given the option, with a popup window, to rename the
        project. This interface and function should already exist and just
        has to be modified a tiny bit to allow this case."*

        *old_name* is the name the files and project.json carry, *new_name*
        the name the project becomes (what the "Printer profile project
        name" field shows), *old_root* the folder as it is on disk. The
        heading and introduction are §M-PROPOSED (M-PROJECT-FOLDER-RENAMED).
        Keep both and Delete do not apply: there is one folder, and it is
        the project. "Leave it as it is" is the Cancel of this case."""
        from workflow.measurement_messages import M_PROJECT_FOLDER_RENAMED
        heading_text, intro_text = M_PROJECT_FOLDER_RENAMED.render(
            folder=old_root.name, name=old_name, new=new_name)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        heading = QLabel(heading_text, self)
        heading.setWordWrap(True)
        heading.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {text_color};")
        outer.addWidget(heading)
        intro = QLabel(intro_text, self)
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {text_color};")
        outer.addWidget(intro)
        paths = QLabel(
            tr("Existing:  {old}\nNew name:  {new}").format(
                old=old_root, new=new_root),
            self,
        )
        paths.setWordWrap(True)
        paths.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        paths.setStyleSheet(
            f"color: {muted}; font-family: Menlo, Consolas, 'Courier New', "
            "monospace; font-size: 12px;")
        outer.addWidget(paths)
        outer.addWidget(self._divider())
        rename_text = tr(
            'ChromIQ renames every file of this project that carries the name '
            '"{old}" so it carries "{new}", and the project with them. Nothing '
            'else in the folder is touched, and nothing is deleted.').format(
                old=old_name, new=new_name)
        if old_root.name != new_name:
            rename_text += " " + tr(
                'The folder becomes "{new}" as well, because a project folder '
                'has no spaces or other characters a file name cannot '
                'carry.').format(new=new_name)
        if self._built_profile:
            rename_text += "\n\n" + tr(
                'A profile already built keeps the name written inside it, '
                '"{old}", which is what ColorSync Utility and other programs '
                'show. Its file is renamed with the others.').format(
                    old=old_name)
        outer.addWidget(self._option_button(
            tr('Rename the project to "{new}"').format(new=new_name),
            rename_text, TargetChangeAction.RENAME, primary=True))
        outer.addWidget(self._option_button(
            tr("Leave it as it is"),
            tr('Nothing is changed. The project stays open, but ChromIQ does '
               'not find its files named "{old}" until they are '
               'renamed.').format(old=old_name),
            TargetChangeAction.CANCEL))

    def _divider(self) -> QFrame:
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def _option_button(
        self,
        title: str,
        description: str,
        action: TargetChangeAction,
        *,
        primary: bool = False,
        danger: bool = False,
    ) -> QWidget:
        """A full-width titled action button with an explanatory line beneath it."""
        text_color = self.palette().color(QPalette.ColorRole.WindowText).name()

        frame = QFrame(self)
        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        btn = QPushButton(title, frame)
        if primary:
            btn.setObjectName("primary")
            btn.setDefault(True)
        elif danger:
            btn.setObjectName("danger")
        # The title carries the target name(s); a long name (or a longer
        # translation) used to overflow the fixed width and clip at both ends
        # (#52). One shared helper decides every button's width, so this can
        # never drift from the rest of the app (Knut, #130 2026-07-26).
        from ui.widgets import fit_button_width
        fit_button_width(btn)
        btn.clicked.connect(lambda: self._choose(action))
        col.addWidget(btn)

        # Description uses the main text colour (not a muted grey) so the
        # explanation stays readable in light mode, where it carries the weight
        # of the choice. The smaller font keeps it visually secondary to the
        # bold button title above it.
        desc = QLabel(description, frame)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {text_color}; font-size: 12px;")
        desc.setMinimumWidth(520)
        col.addWidget(desc)
        return frame

    def _choose(self, action: TargetChangeAction) -> None:
        self._action = action
        self.accept()

    # ------------------------------------------------------------------

    def result_action(self) -> TargetChangeAction:
        """The choice the user made (CANCEL if the dialog was rejected)."""
        return self._action
