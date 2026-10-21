"""D1 (2026-10-21): every open / save / choose-folder dialog in the app goes
through the four helpers in ``ui/widgets.py``, so Preferences > Behaviour >
"Use the operating system's file browser" reaches all of them (Main window,
every tab, Preferences, and every Tools-menu tool).

The pink / magenta screen of manual FAQ Q.06 (29a9e75a9, 2026-04-20) was fixed
by giving every QFileDialog ``DontUseNativeDialog``; the option that came later
is OFF by default, so that fix is still what every user gets unless they ask
for the native panels. Driven on screen with the option ON on macOS 27 (report
D1): 24 native panels, one of them during a live measurement, none pink.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIRS = ("ui", "core", "workflow")
HELPERS = ("open_file_dialog", "open_files_dialog", "save_file_dialog",
           "open_dir_dialog")
STATIC = {"getOpenFileName", "getOpenFileNames", "getSaveFileName",
          "getExistingDirectory", "getOpenFileUrl", "getOpenFileUrls",
          "getSaveFileUrl", "getExistingDirectoryUrl"}


def _app_files():
    for d in APP_DIRS:
        yield from (ROOT / d).rglob("*.py")
    yield ROOT / "main.py"


def test_no_file_dialog_is_built_outside_the_helpers():
    offenders = []
    for f in _app_files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "QFileDialog" \
                    and f.name != "widgets.py":
                offenders.append(f"{f.relative_to(ROOT)}:{node.lineno} QFileDialog(...)")
            if isinstance(fn, ast.Attribute) and fn.attr in STATIC:
                offenders.append(f"{f.relative_to(ROOT)}:{node.lineno} .{fn.attr}()")
    assert not offenders, (
        "a file dialog that does not go through ui/widgets.py ignores the "
        "native-dialog option (and the FAQ Q.06 default): " + ", ".join(offenders))


def test_every_helper_reads_the_option_and_defaults_to_chromiqs_own():
    from core.settings import DEFAULTS
    from ui import widgets as W
    assert DEFAULTS["use_native_file_dialogs"] is False
    for name in HELPERS:
        src = inspect.getsource(getattr(W, name))
        assert "_prefer_native_dialogs()" in src, name
        assert "DontUseNativeDialog" in src, name


def test_every_tool_is_in_the_on_screen_sample():
    """The D1 driver opened a file dialog of each key below; a new tool is a
    new dialog to check on screen."""
    from ui.dialogs.tools_dialogs import TOOL_DIALOG_KEYS
    assert set(TOOL_DIALOG_KEYS) == {
        "spot_read", "ti2_relayout", "average", "merge", "ti1_to_i1p",
        "i1p_to_ti3", "i1p_to_ti1", "verify", "verify_profile", "profile_info",
        "ti3_info", "measurement_report", "softproof", "device_link",
        "devicelink_apply", "scanner_target", "scanner_profile", "translate"}
