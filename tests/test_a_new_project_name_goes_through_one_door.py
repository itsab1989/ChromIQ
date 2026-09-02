"""A name no filesystem will take is refused where it is typed, on every route.

WHAT WENT WRONG
    `FileManager._sanitise` caps no length and passes the Windows reserved
    device names through, and it is right not to: it is also the function that
    RESOLVES a folder that already exists, so a rule applied there would move
    somebody's project (Basti's ruling, pinned name by name in
    `test_project_name_keeps_its_accents.py`). The rules therefore live at the
    door — `ui.dialogs.name_prompt.validate` caps at 120 UTF-8 bytes, refuses
    `CON`/`PRN`/`COM1`…, refuses a leading dot, and refuses a name with no
    letters or digits in it.

    Three routes did not go through that door.

    * The `.ti2` import dialog and the `.txt` import dialog each carried their
      own four-line `_validate` — the two copies `ui/dialogs/name_prompt`'s own
      module docstring says have "DRIFTED apart". Worse, both were handed the
      already-SANITISED name, which no longer contains a forbidden character, so
      they passed everything. Driven through the real dialogs: a 250-character
      name and `CON` were both accepted
      (`review/FIX-NAMES/evidence/BEFORE-f2-doors.txt`).

    * Typing a new name into the Create Chart name box and tabbing away goes to
      `_maybe_rename_on_edit`, which had no check at all. Driven on a real
      project of nine files: renaming to a 250-character name MOVED the whole
      folder, then died with Errno 63 on the first page bitmap, and the caller's
      `except OSError` answered by "creating fresh instead" — the app carried on
      with an empty project while the real one sat under a folder unreachable by
      name (`review/FIX-NAMES/evidence/BEFORE-f2-rename.txt`).

    Generating a chart was already guarded: `TabChart._name_needs_asking` runs
    `validate` on all four build routes.

THE FIX
    All three now ask the same question of the same function, with the wording
    that was already approved for it. No new sentence reaches a user.

WHAT THESE TESTS PROVE
    That each dialog refuses the three shapes and accepts an ordinary name —
    driven through the real widgets, not by re-checking the rule; that the
    rename route leaves the project exactly where it was and says why; and that
    `_sanitise` still leaves every folder that already exists alone, which is
    the reason the rules are at the door in the first place.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel, QLineEdit,
                             QPushButton, QWidget)

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager, Project
from core.settings import AppSettings
from ui.dialogs.name_prompt import validate

#: The three shapes that used to get through, and one that must still not be
#: touched.
REFUSED = ["A" * 250, "CON", "prn.txt", ".hidden", "..."]
ACCEPTED = ["Canon-Pro300", "Müller-Prüfdruck", "Epson P900 Baryta Gloss"]


def _drive(open_dialog, typed: str):
    """Type *typed* into the dialog the callable opens and click its accept
    button. Returns (what the dialog returned, the message it left on screen).

    Drives the REAL widgets: nothing about the rule is re-implemented here, only
    the click. A dialog that stays up is a refusal, and its own label is read
    back so the test cannot pass on a refusal for the wrong reason.
    """
    app = QApplication.instance()
    seen: dict = {}

    def act():
        for w in app.topLevelWidgets():
            if not (isinstance(w, QDialog) and w.isVisible()):
                continue
            edits = w.findChildren(QLineEdit)
            if not edits:
                continue
            edits[0].setText(typed)
            app.processEvents()
            for b in w.findChildren(QPushButton):
                if (b.isVisible() and b.isEnabled()
                        and b.text().strip().lower() not in ("cancel", "go back")):
                    b.click()
                    break
            app.processEvents()
            if w.isVisible():
                msgs = [l.text() for l in w.findChildren(QLabel)
                        if l.text() and l.isVisible() and len(l.text()) < 400]
                seen["refusal"] = msgs[-1] if msgs else "(no message)"
                w.reject()
            return
        seen["refusal"] = "(no dialog appeared)"
        for w in app.topLevelWidgets():          # never leave one running
            if isinstance(w, QDialog) and w.isVisible():
                w.reject()

    QTimer.singleShot(0, act)
    # A second shot, so a dialog that somehow survives the first cannot hang the
    # suite on its own event loop.
    QTimer.singleShot(3000, lambda: [w.reject() for w in app.topLevelWidgets()
                                     if isinstance(w, QDialog) and w.isVisible()])
    return open_dialog(), seen.get("refusal")


@pytest.fixture
def import_source(tmp_path):
    work = tmp_path / "out"
    work.mkdir()
    ti2 = tmp_path / "source.ti2"
    ti2.write_text("CTI2\nNUMBER_OF_SETS 4\n", encoding="utf-8")
    txt = tmp_path / "source.txt"
    txt.write_text("hello\n", encoding="utf-8")
    return work, ti2, txt


# ---------------------------------------------------------------------------
# The two import dialogs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typed", REFUSED)
def test_the_ti2_import_dialog_refuses_an_impossible_name(qapp, import_source,
                                                          typed):
    from ui import ti2_loader
    work, ti2, _txt = import_source
    parent = QWidget()
    got, refusal = _drive(
        lambda: ti2_loader._ask_profile_name(parent, ti2, None, [], work), typed)
    assert got is None, got
    assert refusal == validate(typed), refusal


@pytest.mark.parametrize("typed", ACCEPTED)
def test_the_ti2_import_dialog_still_takes_an_ordinary_name(qapp,
                                                            import_source,
                                                            typed):
    """The half that matters more: nothing new is refused."""
    from ui import ti2_loader
    work, ti2, _txt = import_source
    parent = QWidget()
    got, _refusal = _drive(
        lambda: ti2_loader._ask_profile_name(parent, ti2, None, [], work), typed)
    assert got is not None and got[0] == FileManager._sanitise(typed), got


@pytest.mark.parametrize("typed", REFUSED)
def test_the_txt_import_dialog_refuses_an_impossible_name(qapp, import_source,
                                                          typed):
    from ui import txt_loader
    work, _ti2, txt = import_source
    parent = QWidget()
    got, refusal = _drive(
        lambda: txt_loader._ask_profile_name(parent, txt, work), typed)
    assert got is None, got
    assert refusal == validate(typed), refusal


@pytest.mark.parametrize("typed", ACCEPTED)
def test_the_txt_import_dialog_still_takes_an_ordinary_name(qapp,
                                                            import_source,
                                                            typed):
    from ui import txt_loader
    work, _ti2, txt = import_source
    parent = QWidget()
    got, _refusal = _drive(
        lambda: txt_loader._ask_profile_name(parent, txt, work), typed)
    assert got is not None and got[0] == FileManager._sanitise(typed), got


# ---------------------------------------------------------------------------
# The "Copy project" dialog — the FOURTH door, found by a challenge round
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typed", REFUSED + ["bad:name"])
def test_the_copy_project_dialog_refuses_an_impossible_name(qapp,
                                                            import_source,
                                                            typed):
    """`ui/ti2_loader._ask_project_name` is a fourth name box, in the same file
    as one of the three above, and it was missed. It knew only "empty" and
    "already taken" — looser even than the four-line checks the loaders used to
    carry, since it did not refuse a forbidden character either.

    It matters because of what its three callers do with the answer:
    A1b "Copy the whole project in" and File > Open Project on an outside
    project both hand it to `chart_import.copy_whole_project`, and Load patch
    set > new project hands it to `FileManager.start_new_project`. A
    250-character name makes a folder whose first page bitmap is 257 bytes and
    dies with Errno 63; `CON` makes a folder Windows cannot open.
    """
    from ui import ti2_loader
    work, _ti2, _txt = import_source
    parent = QWidget()
    got, refusal = _drive(
        lambda: ti2_loader._ask_project_name(parent, "Src", work), typed)
    assert got is None, got
    assert refusal == validate(typed), refusal


@pytest.mark.parametrize("typed", ACCEPTED)
def test_the_copy_project_dialog_still_takes_an_ordinary_name(qapp,
                                                              import_source,
                                                              typed):
    from ui import ti2_loader
    work, _ti2, _txt = import_source
    parent = QWidget()
    got, _refusal = _drive(
        lambda: ti2_loader._ask_project_name(parent, "Src", work), typed)
    assert got is not None and got[0] == typed, got


# ---------------------------------------------------------------------------
# The rename route
# ---------------------------------------------------------------------------

@pytest.fixture
def chart_tab(qapp, tmp_path):
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path))
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _project_with_files(tmp_path, name: str, built: bool = True) -> Project:
    """A project with real files in it. *built* adds the `.icc`, which makes the
    rename chooser refuse on its own grounds (the ICC's description is baked in)
    — so the test that watches the chooser being REACHED leaves it out."""
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run()
    exts = (".ti1", ".ti2", ".ti3", ".icc") if built else (".ti1", ".ti2", ".ti3")
    for ext in exts:
        (run.dir / f"{name}{ext}").write_text("x", encoding="utf-8")
    for i in (1, 2, 3):
        (run.dir / f"{name}_{i:02d}.tif").write_text("x", encoding="utf-8")
    proj.save_manifest()
    return proj


@pytest.mark.parametrize("typed", ["A" * 250, "CON"])
def test_renaming_a_project_to_an_impossible_name_moves_nothing(chart_tab,
                                                                tmp_path,
                                                                typed):
    """The destructive one. Nine files, a folder that moved and could not be
    finished, and an `except OSError` that carried on with a fresh project."""
    proj = _project_with_files(tmp_path, "Start")
    before = sorted(p.name for p in proj.current_run().dir.iterdir())
    chart_tab._last_target_name = "Start"
    chart_tab._file_mgr.set_target_name("Start")

    edit = QLineEdit()
    edit.setText(typed)
    hint = QLabel()
    chart_tab._maybe_rename_on_edit(edit, hint)

    assert proj.root.is_dir(), "the project folder moved"
    assert sorted(p.name for p in proj.current_run().dir.iterdir()) == before
    assert not (tmp_path / FileManager._sanitise(typed)).exists()
    assert hint.isVisible() or hint.text(), "refused in silence"
    assert hint.text() == validate(typed)


def test_renaming_to_an_ordinary_name_is_not_affected(chart_tab, tmp_path,
                                                      monkeypatch):
    """The guard must not swallow a rename somebody meant."""
    _project_with_files(tmp_path, "Start", built=False)
    chart_tab._last_target_name = "Start"
    chart_tab._file_mgr.set_target_name("Start")
    reached: list = []
    monkeypatch.setattr(chart_tab, "_handle_target_rename",
                        lambda n: reached.append(n) or True)
    edit = QLineEdit()
    edit.setText("Canon-Pro300")
    chart_tab._maybe_rename_on_edit(edit, QLabel())
    assert reached == ["Canon-Pro300"], reached


# ---------------------------------------------------------------------------
# The build route was already guarded — pinned so it stays that way
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typed", REFUSED)
def test_generating_a_chart_still_stops_to_ask(chart_tab, typed):
    assert chart_tab._name_needs_asking(typed) is True


@pytest.mark.parametrize("typed", ACCEPTED)
def test_generating_a_chart_does_not_stop_for_an_ordinary_name(chart_tab,
                                                               typed):
    assert chart_tab._name_needs_asking(typed, target_name="x") is False


# ---------------------------------------------------------------------------
# …and why the rules are at the door and not in the sanitiser
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("existing", ["CON", "A" * 250, "Mu_ller", "Müller"])
def test_a_folder_that_already_exists_is_still_a_fixed_point(tmp_path,
                                                             existing):
    """The reason `_sanitise` must NOT hold these rules. `open_project_at`
    derives the target name from the folder's own name and `working_dir`
    re-cleans it to decide the project is where it says it is, so a length cap
    or a device-name rule there would make an existing project unreachable.

    Basti's ruling, already pinned in `test_project_name_keeps_its_accents.py`;
    repeated here because this file is where somebody will next be tempted to
    move the rules inwards.
    """
    assert FileManager._sanitise(existing) == existing
    root = tmp_path / existing
    Project.create(root, existing)
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    fm.open_project_at(root)
    assert fm.working_dir() == root
    assert fm.has_project()
