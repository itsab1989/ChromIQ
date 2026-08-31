"""Import an i1Profiler measurement .txt into the working folder.

i1Profiler can read charts ChromIQ exports (see ``workflow/i1profiler_export``)
and write back a measurement .txt. That file isn't an Argyll .ti3, so before the
Build-Profile tab can use it we place it in a per-profile subfolder and let the
caller run Argyll's ``txt2ti3`` to produce the .ti3.

This mirrors ``ui/ti2_loader`` — same working-folder detection and copy/rename
dialogs — but for the single-file case (just the .txt), so the ti2 chart-loading
logic stays untouched. The generic working-folder helpers are reused from there.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from workflow.chart_import import ReplaceFailed
from typing import TYPE_CHECKING

from ui.ti2_loader import _project_root_for, _resolve_working_dir
from core.i18n import tr
from core.logger import get_logger

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget
    from core.settings import AppSettings

log = get_logger(__name__)




def is_self_collision(working_dir, name: str, path) -> bool:
    """Would replacing ``working_dir/name`` destroy the file being imported?

    One line, because the logic lives in `core.file_manager.dir_holds` — both
    loaders had their own copy and both were wrong the same way, which is how
    replacing a project deleted the project, its profile AND the file being
    imported.

    Module level, not a closure inside the dialog, so that it can be driven
    without building a window: the test that guards this used to grep the
    module for the word "dir_holds", and a loader that had stopped calling it
    still passed, because the name survived in a docstring.
    """
    from core.file_manager import dir_holds
    return dir_holds(working_dir / name, path)


def _say_the_replace_failed(parent, folder, reason) -> None:
    """Show M-PROJECT-REPLACE-FAILED — the promise that nothing is deleted,
    when it could not be kept.

    "Replace it" promises everything is moved into the project's own `old/`
    folder. When that move cannot be made — a read-only folder, a share that
    has gone away, a file another program holds open — `_archive_project_contents`
    puts back whatever it had moved and raises. Until now the raise reached
    nothing but `chromiq.log`: driven through a real button with the excepthook
    `main.py` installs, the window never appeared, the tab log said nothing, and
    the app looked idle. The copy functions take no widget, so this is said at
    the layer that has one.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    title, body = M.M_PROJECT_REPLACE_FAILED.render(folder=str(folder),
                                                    reason=str(reason))
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()


def _say_where_the_old_project_went(parent, name, dest) -> None:
    """M-IMPORT-REPLACED-KEPT — "Nothing is deleted" is only true if the person
    can find it again.

    Report 10, finding 9: nothing anywhere recorded where a replaced project had
    gone — no window, no log line, not even a line in the tab's log. The
    catalogue entry existed for a round with no call site, which is worse than
    not having it: the specification then describes a promise the app does not
    keep. Shown from here because the `_copy_*` functions take no widget.
    """
    from PyQt6.QtWidgets import QMessageBox
    from workflow import measurement_messages as M
    title, body = M.M_IMPORT_REPLACED_KEPT.render(name=name,
                                                  folder=str(dest / "old"))
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(title)
    box.setInformativeText(body)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.exec()

def resolve_txt(
    parent: "QWidget",
    txt_path: Path,
    settings: "AppSettings",
) -> tuple[Path, str] | None:
    """Decide where an i1Profiler measurement .txt should live before conversion.

    Returns ``(txt_to_convert, base_name)`` — the .txt path to feed ``txt2ti3``
    and the base name to use for the resulting .ti3 — or ``None`` if the user
    cancelled. The .txt is either used in place (when already inside a working
    sub-folder and the user chose "Continue") or copied, renamed, into a fresh
    ``<working_dir>/<name>/`` sub-folder.
    """
    # THE PROMISE THAT NOTHING IS DELETED, KEPT OR EXPLAINED.
    try:
        working_dir = _resolve_working_dir(settings)
        if _project_root_for(txt_path, working_dir) is not None:
            return _handle_inside(parent, txt_path, working_dir)
        return _handle_outside(parent, txt_path, working_dir)
    except ReplaceFailed as exc:
        # ONLY a failed archive. Any other OSError is a different fault and
        # must not be reported as "the existing project could not be moved
        # aside — nothing has been changed", which would be false.
        _say_the_replace_failed(parent, exc.folder, exc.reason)
        return None

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _handle_outside(
    parent: "QWidget",
    txt_path: Path,
    working_dir: Path,
) -> tuple[Path, str] | None:
    result = _ask_profile_name(parent, txt_path, working_dir)
    if result is None:
        return None
    name, overwrite = result
    out = _copy_txt(txt_path, working_dir, name, overwrite=overwrite)
    if overwrite:
        _say_where_the_old_project_went(parent, name, working_dir / name)
    return out


def _handle_inside(
    parent: "QWidget",
    txt_path: Path,
    working_dir: Path,
) -> tuple[Path, str] | None:
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("Load Measurement"))
    dlg.setMinimumWidth(460)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)

    lbl = QLabel(
        tr("<b>{name}</b> is already in your working folder.<br><br>"
           "What would you like to do?").format(name=txt_path.name),
        dlg,
    )
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    cont_desc = QLabel(
        tr("<i>Continue</i> — convert and use the measurement in this folder as-is — "
        "nothing will be copied or moved."),
        dlg,
    )
    cont_desc.setWordWrap(True)
    layout.addWidget(cont_desc)

    new_desc = QLabel(
        tr("<i>Use as base for a new profile</i> — copy the measurement to a new "
        "subfolder so you can build a separate ICC profile without overwriting "
        "the original."),
        dlg,
    )
    new_desc.setWordWrap(True)
    layout.addWidget(new_desc)

    btn_box    = QDialogButtonBox(dlg)
    cont_btn   = btn_box.addButton(tr("Continue"),                      QDialogButtonBox.ButtonRole.AcceptRole)
    new_btn    = btn_box.addButton(tr("Use as base for a new profile"), QDialogButtonBox.ButtonRole.ActionRole)
    cancel_btn = btn_box.addButton(tr("Cancel"),                        QDialogButtonBox.ButtonRole.RejectRole)
    layout.addWidget(btn_box)

    choice: list[str | None] = [None]

    def _on_continue() -> None:
        choice[0] = "continue"
        dlg.accept()

    def _on_new() -> None:
        choice[0] = "new"
        dlg.accept()

    cont_btn.clicked.connect(_on_continue)
    new_btn.clicked.connect(_on_new)
    cancel_btn.clicked.connect(dlg.reject)
    dlg.exec()

    if choice[0] == "continue":
        # Same load-time housekeeping as ti2_loader's continue branch (#127):
        # README backfill + v1→v2 folder migration; best-effort.
        root = _project_root_for(txt_path, working_dir)
        if root is not None:
            try:
                from core.file_manager import Project
                Project.load(root)
            except Exception:  # noqa: BLE001
                log.warning("in-place load: could not run project "
                            "housekeeping for %s", root, exc_info=True)
        return txt_path, txt_path.stem
    if choice[0] == "new":
        result = _ask_profile_name(parent, txt_path, working_dir)
        if result is None:
            return None
        name, overwrite = result
        out = _copy_txt(txt_path, working_dir, name, overwrite=overwrite)
        if overwrite:
            _say_where_the_old_project_went(parent, name, working_dir / name)
        return out
    return None


def _ask_profile_name(
    parent: "QWidget",
    txt_path: Path,
    working_dir: Path,
) -> tuple[str, bool] | None:
    """Ask the user for a profile name for an imported measurement .txt.

    Returns ``(name, overwrite)`` — ``overwrite=True`` means the user explicitly
    confirmed wiping an existing folder of the same name. Returns ``None`` if the
    user cancelled.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import (
        QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
    )

    dlg = QDialog(parent)
    dlg.setWindowTitle(tr("Choose a name for the profile"))
    dlg.setMinimumWidth(580)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(10)

    info = QLabel(
        tr("The i1Profiler measurement <b>{name}</b> will be copied into "
           "your working folder as a new profile set:<br><br>"
           "<pre>  • {name}</pre>"
           "It will be placed in:<br>"
           "<code>{target}/&lt;name&gt;/</code><br><br>"
           "Enter a name for the profile you want to create:").format(
            name=txt_path.name, target=working_dir),
        dlg,
    )
    info.setWordWrap(True)
    layout.addWidget(info)

    name_edit = QLineEdit(dlg)
    name_edit.setPlaceholderText(tr("e.g. Canon_ProGraf_Glossy_240g"))
    layout.addWidget(name_edit)

    error_lbl = QLabel("", dlg)
    error_lbl.setStyleSheet("color: #e05555;")
    error_lbl.setWordWrap(True)
    layout.addWidget(error_lbl)

    btn_row = QHBoxLayout()

    ok_btn = QPushButton(tr("OK"), dlg)
    ok_btn.setDefault(True)
    btn_row.addWidget(ok_btn)

    overwrite_btn = QPushButton(tr("Replace it"), dlg)
    overwrite_btn.setAutoDefault(False)
    overwrite_btn.setVisible(False)
    btn_row.addWidget(overwrite_btn)

    btn_row.addStretch(1)

    cancel_btn = QPushButton(tr("Cancel"), dlg)
    cancel_btn.setAutoDefault(False)
    cancel_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(cancel_btn)

    layout.addLayout(btn_row)

    result: dict = {"name": None, "overwrite": False}

    def _is_self_collision(name: str) -> bool:
        """True when the folder we would replace HOLDS the file being imported."""
        return is_self_collision(working_dir, name, txt_path)

    def _normalise(text: str) -> str:
        """Sanitise the typed name the same way set_target_name does (spaces→-,
        illegal chars→_), so the on-disk folder = the user-facing name."""
        from core.file_manager import FileManager
        cleaned = FileManager.strip_workfile_ext(text)
        return FileManager._sanitise(cleaned) if cleaned.strip() else ""

    def _validate(name: str) -> str | None:
        if not name:
            return "Please enter a name."
        if any(c in name for c in r'/\:*?"<>|'):
            return "Name contains invalid characters."
        return None

    def _on_name_changed(_text: str = "") -> None:
        name = _normalise(name_edit.text())
        collision = bool(name) and (working_dir / name).exists() and not _is_self_collision(name)
        if collision:
            error_lbl.setText(
                tr("“{name}” is already a project. Choose a different name, "
                   "or click “Replace it”.").format(name=name)
            )
            ok_btn.setVisible(False)
            overwrite_btn.setVisible(True)
        else:
            error_lbl.setText("")
            ok_btn.setVisible(True)
            overwrite_btn.setVisible(False)

    name_edit.textChanged.connect(_on_name_changed)

    def _on_accept() -> None:
        name = _normalise(name_edit.text())
        err = _validate(name)
        if err:
            error_lbl.setText(err)
            return
        if (working_dir / name).exists() and not _is_self_collision(name):
            _on_name_changed()
            return
        if _is_self_collision(name):
            error_lbl.setText(
                tr("That name points to the measurement's own folder. Pick a different name.")
            )
            return
        result["name"] = name
        result["overwrite"] = False
        dlg.accept()

    def _on_overwrite() -> None:
        name = _normalise(name_edit.text())
        err = _validate(name)
        if err:
            error_lbl.setText(err)
            return
        if _is_self_collision(name):
            error_lbl.setText(
                tr("That project holds the measurement you are importing, "
                   "so replacing it would take the file with it. Please pick "
                   "a different name.")
            )
            return
        dest = working_dir / name
        if not dest.exists():
            result["name"] = name
            result["overwrite"] = False
            dlg.accept()
            return
        # THE SECOND LOOK, IN THE WORDS §S4.7 USES.
        # It said "This will permanently delete", which was true when this ran
        # `shutil.rmtree` and is a lie now that it archives. Rendered from the
        # catalogue (M-IMPORT-REPLACE-CONFIRM) rather than written here, because
        # `test_message_catalogue.py`'s WINDOW_SOURCES is a (module, class,
        # method) allow-list that cannot express a module-level function — text
        # written straight into this file is invisible to every check we have.
        #
        # Built with QMessageBox() rather than the `.warning` STATIC: the static
        # runs its own C++ event loop, so a test that patches `QMessageBox.exec`
        # never reaches it and hangs on a real modal.
        from workflow import measurement_messages as M
        _title, _body = M.M_IMPORT_REPLACE_CONFIRM.render(
            name=name, folder=str(dest), subject=tr("the measurement"))
        _box = QMessageBox(dlg)
        _box.setIcon(QMessageBox.Icon.NoIcon)
        _box.setWindowTitle(_title)
        _box.setText(_title)
        _box.setInformativeText(_body)
        _yes = _box.addButton(tr("Replace it"),
                              QMessageBox.ButtonRole.DestructiveRole)
        _back = _box.addButton(tr("Go back"), QMessageBox.ButtonRole.RejectRole)
        _box.setDefaultButton(_back)     # Return must never be a replace
        # The house rules: fit each button to its words, and Cancel/Go back on
        # the far right (Basti, 2026-08-27; the clipping fault is Knut's #130).
        from ui.widgets import (fit_message_box_buttons,
                                spread_message_box_buttons)
        fit_message_box_buttons(_box)
        spread_message_box_buttons(_box, order=[_yes, _back])
        _box.exec()
        if _box.clickedButton() is _yes:
            result["name"] = name
            result["overwrite"] = True
            dlg.accept()

    ok_btn.clicked.connect(_on_accept)
    overwrite_btn.clicked.connect(_on_overwrite)

    QTimer.singleShot(0, name_edit.setFocus)
    if dlg.exec() == QDialog.DialogCode.Accepted and result["name"]:
        return result["name"], result["overwrite"]
    return None


def _copy_txt(
    txt_path: Path,
    working_dir: Path,
    new_name: str,
    overwrite: bool = False,
) -> tuple[Path, str]:
    """Import an i1Profiler .txt into a fresh project as run1's chart.

    Builds the per-run layout (see docs/dev_folder_layout.md): a project at
    ``working_dir/<new_name>/`` with the .txt placed at
    ``runs/run1/<new_name>.txt``. txt2ti3 then writes
    ``runs/run1/<new_name>.ti3`` — the canonical measurement under the
    project-name chart stem.

    Returns (txt path, base name to hand txt2ti3).
    """
    from core.file_manager import FileManager, Project

    # Defensive: dialog already sanitises, but enforce here for any caller.
    new_name = FileManager._sanitise(FileManager.strip_workfile_ext(new_name))

    dest = working_dir / new_name
    if overwrite and dest.exists():
        # ARCHIVE, NEVER DESTROY. §S4.7 of the measurement specification says a
        # replace "archive[s] the whole project into its `old/`", and T2.6 says
        # "nothing is ever deleted" — but these three import routes reached for
        # `shutil.rmtree`, which is not atomic: it removes what it can and
        # raises at the end, so one unwritable sub-folder left a project with
        # one file of six, `project.json` among the casualties, while the app
        # reported that nothing had changed (`core/trash.py` records the
        # measurement). Basti's ruling, 2026-08-31.
        #
        # Archiving into the SAME folder and then calling `Project.create` on it
        # is safe: `create` is `mkdir(exist_ok=True)` and removes nothing, so
        # the `old/` written here survives the new project being made on top.
        from workflow.chart_import import (ReplaceFailed,
                                            _archive_project_contents)
        try:
            _kept_at = _archive_project_contents(dest)
        except OSError as exc:
            raise ReplaceFailed(dest, exc) from exc
        log.info("replaced %s — everything it held is kept at %s", dest, _kept_at)

    proj = Project.create(dest, new_name)
    run  = proj.current_run()
    run.ensure_dir()

    # Place the .txt under the chart stem so txt2ti3's output stays paired
    # (Run.measurement_ti3 = <stem>.ti3 = <new_name>.ti3).
    new_txt = run.dir / f"{run.stem}.txt"
    shutil.copy2(txt_path, new_txt)
    return new_txt, run.stem
