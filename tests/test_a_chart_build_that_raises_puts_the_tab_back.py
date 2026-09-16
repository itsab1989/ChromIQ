"""B8-223 — Generate Chart dies in silence and the button never comes back.

A DOOR CAN DECLINE BY RETURNING AND IT CAN STOP BY RAISING. Combined round 8
found that distinction at the measurement door; this is the same distinction at
the door a user meets first.

Both chart-build doors do the same thing in the same order: disable Generate
Chart, raise `_layout_owned_by_build`, and only then touch the filesystem —
naming the target, aligning the run, arming the verification snapshot, and
`FileManager.project()`, which mkdirs the project root and (through
`Project.load`) rewrites "Where are my files.txt" on every single load. Every
one of those can raise `OSError`. `_on_generate`'s own comment says *"Every
path out of this build re-enables the button, including the failures"*, which
is true of every `return` in it and of no exception at all: its `try` had no
handler, only a `finally` that forgets the §S4.7 gate answer.

DRIVEN ON SCREEN, combined round 9 (`A-result.json`, `B-result.json`,
`A8-what-the-person-is-left-with.png`), two independent ways into the same
state:

* the projects folder on a drive that is not mounted — `/Volumes` is
  root-owned `drwxr-xr-x`, so an ordinary `mkdir` under it is refused;
* the projects folder read-only, which is a locked folder, a share that
  dropped, or a disk mounted read-only.

Press Generate Chart and NOTHING happens: no window, not one line in the log
(`"log tail": ""`). Generate Chart is then greyed out for the rest of the
session — the photograph shows it greyed with Stop live beside it — and the
only way back is to restart ChromIQ.

The quieter half is worse. `_layout_owned_by_build` stays True, and the comment
beside every early return says what that costs: *"the next target the user
selects never receives its own settings, and the next write files the previous
run's values onto it (§4 S8)"*.

The sibling door already had this guard, in these words: `tab_profile._on_build`
wraps its launch in *"THE LOCK MUST COME BACK OFF IF THE BUILD NEVER STARTS …
leaving the user locked out of their own app with no way back but a restart"*.
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager                       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("language", "en")
    return TabChart(ArgyllRunner(s), FileManager(s), s)


# ---- the two doors both have the handler -------------------------------
def _handlers(fn) -> list[str]:
    """Every exception type the top-level `try` of *fn* handles."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    out: list[str] = []
    for node in ast.walk(tree.body[0]):
        if isinstance(node, ast.Try):
            for h in node.handlers:
                out.append(ast.unparse(h.type) if h.type else "bare")
    return out


@pytest.mark.parametrize("door", [TabChart._on_generate,
                                  TabChart._generate_from_ti1])
def test_each_build_door_handles_an_exception_that_escapes(door):
    """Not "does it have a try" — `_on_generate` always had one, with a
    `finally` that forgets an answer and no handler at all."""
    assert "OSError" in _handlers(door), (
        f"{door.__name__} still lets an OSError out of the build with the "
        "Generate button disabled behind it")


@pytest.mark.parametrize("door", [TabChart._on_generate,
                                  TabChart._generate_from_ti1])
def test_each_build_door_puts_the_tab_back_for_anything_else(door):
    """A fault this tab cannot diagnose gets no sentence about folders — but
    the unlock must still happen, and the fault must still reach the log.
    `tab_profile._on_build`'s shape: unlock, then re-raise."""
    src = inspect.getsource(door)
    assert "_the_chart_build_could_not_start_quietly" in src
    tail = src[src.index("_the_chart_build_could_not_start_quietly"):]
    assert "raise" in tail, "the fault is swallowed instead of re-raised"


def test_the_restore_puts_back_both_the_button_and_the_shield(tab):
    tab._generate_btn.setEnabled(False)
    tab._layout_owned_by_build = True
    tab._the_chart_build_could_not_start_quietly()
    assert tab._generate_btn.isEnabled(), "Generate Chart stayed greyed out"
    assert tab._layout_owned_by_build is False, (
        "the per-target shield stayed up, so the next target selected never "
        "receives its own settings (§4 S8)")


def test_the_restore_stops_the_slow_chart_watchdog(tab):
    """`_on_generate` arms it one statement above the hand-over, so a launch
    that raises left it running and the "this chart is taking a long time"
    window arrived for a build that never began."""
    tab._slow_watchdog.start(60_000)
    assert tab._slow_watchdog.isActive()
    tab._the_chart_build_could_not_start_quietly()
    assert not tab._slow_watchdog.isActive()


# ---- the behaviour, through the real door ------------------------------
def _press_generate_with_an_unwritable_projects_folder(tab, monkeypatch,
                                                       windows):
    from ui.tooltip_button import InfoDialog

    monkeypatch.setattr(
        InfoDialog, "exec",
        lambda self: windows.append((self.windowTitle(), self)) or 0)
    # The state the drive measured, reduced to its one mechanism: the project
    # root cannot be made. `/Volumes` refuses it because it is root-owned; a
    # read-only folder refuses it because it is read-only.
    import core.file_manager as fm
    monkeypatch.setattr(
        fm.Project, "create_or_load",
        staticmethod(lambda *a, **k: (_ for _ in ()).throw(
            PermissionError(13, "Permission denied"))))
    tab._manual_target_name_edit.setText("B8223")
    tab._generate_btn.setEnabled(True)
    tab._layout_owned_by_build = False
    tab._on_generate()


def test_generate_says_so_and_comes_back(tab, qapp, monkeypatch):
    windows: list = []
    _press_generate_with_an_unwritable_projects_folder(tab, monkeypatch, windows)
    qapp.processEvents()

    assert windows, (
        "ChromIQ said nothing at all — no window, and the log tail on screen "
        "was empty")
    assert tab._generate_btn.isEnabled(), (
        "Generate Chart is greyed out with no build running: the tab is dead "
        "until ChromIQ is restarted")
    assert tab._layout_owned_by_build is False


def test_the_window_names_the_reason_and_ends_with_a_lever(tab, qapp,
                                                          monkeypatch):
    """A message is a promise: it must name what went wrong and end with
    something the person can actually do."""
    from PyQt6.QtWidgets import QLabel
    windows: list = []
    _press_generate_with_an_unwritable_projects_folder(tab, monkeypatch, windows)
    qapp.processEvents()
    title, dlg = windows[-1]
    text = title + " " + " ".join(w.text() for w in dlg.findChildren(QLabel))
    assert "could not write" in title.lower()
    assert "Permission denied" in text, (
        "the window does not say what the operating system said")
    assert "Preferences" in text, (
        "the window names no way to put it right")


def test_the_live_preview_is_put_back_without_a_window(tab, qapp, monkeypatch):
    """§4 forbids the auto-update preview from opening a window on every turn
    of a knob. It must still put the button and the shield back."""
    from ui.tooltip_button import InfoDialog
    windows: list = []
    monkeypatch.setattr(InfoDialog, "exec",
                        lambda self: windows.append(self.windowTitle()) or 0)
    tab._generate_btn.setEnabled(False)
    tab._layout_owned_by_build = True
    tab._the_chart_build_could_not_start(
        PermissionError(13, "Permission denied"), quiet=True)
    qapp.processEvents()
    assert windows == [], "the live preview opened a modal"
    assert tab._generate_btn.isEnabled()
    assert tab._layout_owned_by_build is False


def test_the_message_is_one_the_catalogues_carry(tab):
    """No new title: the key the import door already uses, translated into all
    twelve languages. The body is new and was translated with it."""
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    body = ("ChromIQ could not write into your projects folder, so this chart "
            "was not made.\n\nThe reason: {reason}.\n\nThis usually means the "
            "folder is read-only, the disk is full, or it lives on a drive or "
            "share that is no longer connected. Check the folder ChromIQ "
            "writes to in Preferences, then press Generate Chart again.")
    title = "ChromIQ could not write into that project"
    src = inspect.getsource(TabChart._the_chart_build_could_not_start)
    assert "could not write into that project" in src, src[-900:]
    assert "so this " in src and "chart was not made" in src
    for cat in sorted((root / "data" / "i18n").glob("*.json")):
        d = json.loads(cat.read_text(encoding="utf-8"))
        assert title in d, f"{cat.stem} has no translation for the title"
        assert body in d, f"{cat.stem} has no translation for the body"
        assert "{reason}" in d[body], f"{cat.stem} dropped the placeholder"
