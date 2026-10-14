"""Before an Install button copies a profile into the profile folder.

Knut, #182 6102031563, answer 3 ("Installing replaces an installed profile of
the same name without asking. Should ChromIQ ask first?"): "Yes. Ask if user
wants to replace existing or cancel to rename the profile before trying to
install it again."

Basti decided how (2026-10-11, M-PROFILE-INSTALL-REPLACE, approved): when a
profile of the same file name is installed, a window opens with the name in
an EDITABLE field. Left as it is, the button says **Replace** and overwrites
the installed profile; edited, it says **Install** and installs under the new
name; if that name is installed too the window says so and the button says
Replace again. **Cancel** installs nothing. Only the INSTALLED COPY takes the
new name: the profile in the project keeps its own (runs link to it).

Every Install button (Build Profile, Apply Calibration, Check & Refine's
"Install Profile As Is", the scanner window) asks :func:`ask_install_path`
with the file the install would write, before it writes anything, and writes
the file it answers.

The window's Replace / Install button is the default (Return) and Cancel is
what Escape and the close button mean. The person has just pressed Install,
and the field holds the name they will mostly keep or have just typed, so
Return confirms what they asked for, as every macOS "file exists, replace?"
sheet does; Cancel is one key away and is never the destructive choice.
"""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path

from core.i18n import tr

log = logging.getLogger(__name__)

#: The longest name the field accepts (the installed copy's stem), the same
#: cap ChromIQ puts on a name made from the description.
MAX_NAME = 100
#: Characters a file name may not contain on macOS or Windows (where the
#: same profile folder rules apply), so neither refuses the copy.
_FORBIDDEN = set('/\\:*?"<>|')


def name_problem(name: str) -> "str | None":
    """Why *name* cannot be an installed profile's file name, or None.
    Any letters are fine (accents, other scripts)."""
    stem = name.strip()
    if not stem:
        return tr("Type a name for the installed profile.")
    if any(ch in _FORBIDDEN for ch in stem) or any(
            unicodedata.category(ch) == "Cc" for ch in stem) or stem.startswith("."):
        return tr("A name cannot contain / \\ : * ? \" < > | or begin with a dot.")
    if len(stem) > MAX_NAME:
        return tr("A name can have at most {n} characters.").format(n=MAX_NAME)
    return None


def _same_file(a: Path, b: Path) -> bool:
    """True when *a* and *b* name the same file in the profile folder (case
    does not tell two files apart there on a Mac)."""
    return a.name.casefold() == b.name.casefold()


def _exists(p: Path) -> bool:
    try:
        return p.exists()
    except OSError:
        return False


def ask_install_path(parent, dest: "Path | str") -> "Path | None":
    """The file the install should write, or None when it is cancelled.

    Nothing of that name installed: *dest*, nothing asked. Otherwise the
    window (M-PROFILE-INSTALL-REPLACE): *dest* when its name is kept
    (Replace), the same folder and extension with the name typed (Install),
    None for Cancel."""
    dest = Path(dest)
    if not _exists(dest):
        return dest
    dlg = InstallNameDialog(parent, dest)
    chosen = dlg.ask()
    if chosen is None:
        log.info("%s is installed already: not installed (cancelled)", dest)
    elif _same_file(chosen, dest) or _exists(chosen):
        log.info("installed profile %s is replaced", chosen)
    else:
        log.info("%s is installed already: installed as %s instead", dest, chosen)
    return chosen


def InstallNameDialog(parent, dest: Path):  # noqa: N802 - a factory for the class below
    """The window, built lazily so importing this module needs no Qt."""
    return _install_name_dialog_class()(parent, dest)


_CLASS = None


def _install_name_dialog_class():
    global _CLASS
    if _CLASS is not None:
        return _CLASS
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                                 QLineEdit, QVBoxLayout)

    from workflow import measurement_messages as M

    class _InstallNameDialog(QDialog):
        """M-PROFILE-INSTALL-REPLACE: an editable name, Replace / Install,
        Cancel."""

        def __init__(self, parent, dest: Path):
            super().__init__(parent)
            self.setObjectName("profile_install_replace")
            self._dest = Path(dest)
            self._chosen: "Path | None" = None
            title, body = M.M_PROFILE_INSTALL_REPLACE.render()
            self.setWindowTitle(title)
            lay = QVBoxLayout(self)
            # Wrapped labels in a dialog that grows: fixed to the layout's
            # size, re-measured whenever the line under the field changes, so
            # no line is cut off (on screen, 2026-10-11).
            lay.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
            self.setMinimumWidth(480)
            head = QLabel(f"<b>{title}</b>", self)
            head.setTextFormat(Qt.TextFormat.RichText)
            head.setWordWrap(True)
            lay.addWidget(head)
            text = QLabel(body, self)
            text.setWordWrap(True)
            text.setMinimumWidth(460)
            lay.addWidget(text)
            row = QHBoxLayout()
            self.name_edit = QLineEdit(self._dest.stem, self)
            self.name_edit.setObjectName("install_name_edit")
            self.name_edit.setAccessibleName(tr("Name of the installed profile"))
            self.name_edit.setMinimumWidth(320)
            row.addWidget(self.name_edit, 1)
            row.addWidget(QLabel(self._dest.suffix, self))
            lay.addLayout(row)
            self.note = QLabel("", self)
            self.note.setObjectName("install_name_note")
            self.note.setWordWrap(True)
            self.note.setMinimumWidth(460)
            lay.addWidget(self.note)
            box = QDialogButtonBox(self)
            self.ok_btn = box.addButton(tr(M._INSTALL_REPLACE),
                                        QDialogButtonBox.ButtonRole.AcceptRole)
            self.ok_btn.setObjectName("install_ok")
            self.cancel_btn = box.addButton(tr("Cancel"),
                                            QDialogButtonBox.ButtonRole.RejectRole)
            self.ok_btn.setDefault(True)
            self.ok_btn.setAutoDefault(True)
            box.accepted.connect(self._accept)
            box.rejected.connect(self.reject)
            lay.addWidget(box)
            self.name_edit.textChanged.connect(self._update)
            self.name_edit.selectAll()
            self._update()

        def target(self) -> "Path | None":
            stem = self.name_edit.text().strip()
            if name_problem(stem):
                return None
            return self._dest.with_name(f"{stem}{self._dest.suffix}")

        def _update(self, *_a) -> None:
            problem = name_problem(self.name_edit.text())
            if problem:
                self.note.setText(problem)
                self.ok_btn.setText(tr(M._INSTALL_REPLACE))
                self.ok_btn.setEnabled(False)
                return
            self.ok_btn.setEnabled(True)
            t = self.target()
            if _same_file(t, self._dest):
                self.note.setText("")
                self.ok_btn.setText(tr(M._INSTALL_REPLACE))
            elif _exists(t):
                self.note.setText(tr(
                    "A profile named {name} is installed too. Replace "
                    "overwrites it.").format(name=t.name))
                self.ok_btn.setText(tr(M._INSTALL_REPLACE))
            else:
                self.note.setText("")
                self.ok_btn.setText(tr(M._INSTALL_INSTALL))

        def _accept(self) -> None:
            t = self.target()
            if t is None:
                return
            self._chosen = t
            self.accept()

        def ask(self) -> "Path | None":
            self._chosen = None
            self.exec()
            return self._chosen

    _CLASS = _InstallNameDialog
    return _CLASS
