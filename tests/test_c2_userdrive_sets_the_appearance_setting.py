"""`userdrive.Drive(appearance=...)` sets the appearance SETTING, not only the
palette (challenge 2 of beta 42, #8; B8-1007).

The Measurement Report picks its page, strip and graph colours from the
`appearance` setting. The harness applied the palette and the style sheet and
left the setting at whatever the sandbox held, so a "dark" drive photographed
a light report page inside a dark window: every dark or neutral report
photograph taken through `userdrive` was of a state no user can reach.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def userdrive():
    saved = os.environ.get("QT_QPA_PLATFORM")
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        mod = importlib.import_module("userdrive")
    finally:
        sys.path.remove(str(ROOT / "scripts"))
        if saved is not None:
            os.environ["QT_QPA_PLATFORM"] = saved
    return mod


@pytest.mark.parametrize("look", ["dark", "neutral", "light"])
def test_the_drive_writes_the_appearance_it_paints(userdrive, qapp, tmp_path,
                                                   monkeypatch, look):
    """MUTATION, proved to land: drop the `settings.set("appearance", …)`
    line from `Drive.__init__` (the setting stays at the sandbox's own)."""
    from PyQt6.QtWidgets import QWidget
    import core.i18n
    import core.logger
    import ui.main_window
    import ui.theme
    applied = []

    class _Window(QWidget):
        def __init__(self, settings):
            super().__init__()
            self.settings_seen = settings.get("appearance", "")

    # Nothing global moves: no style sheet on the application (CLAUDE.md),
    # no language, no log file, no sandbox variables for the next test.
    monkeypatch.setattr(userdrive, "_sandbox", lambda out: None)
    monkeypatch.setattr(ui.theme, "apply_appearance",
                        lambda app, win, setting: applied.append(
                            (win is not None, setting)) or setting)
    monkeypatch.setattr(ui.main_window, "MainWindow", _Window)
    monkeypatch.setattr(core.i18n, "set_language", lambda code: None)
    monkeypatch.setattr(core.i18n, "install_qt_translator", lambda app: None)
    monkeypatch.setattr(core.logger, "configure_logging", lambda *a, **k: None)
    monkeypatch.setattr(core.logger, "_log_path",
                        lambda *a, **k: tmp_path / "log.txt")
    monkeypatch.setattr(userdrive.Drive, "pump", lambda self, ms=300: None)
    import types
    from PyQt6.QtWidgets import QApplication
    monkeypatch.setitem(sys.modules, "scripts.capture_screens",
                        types.SimpleNamespace(build_app=QApplication.instance))
    from core.settings import AppSettings
    store = AppSettings()
    held = {k: store.get(k, "") for k in ("appearance", "custom_output_path",
                                          "argyll_bin_path", "language")}
    store.set("appearance", "auto")
    d = userdrive.Drive(tmp_path / "out", language="en", appearance=look)
    try:
        assert d.settings.get("appearance", "") == look
        assert d.win.settings_seen == look, (
            "the window was built before the setting was written")
        assert applied == [(False, look), (True, look)], applied
    finally:
        d.win.close()
        for k, v in held.items():         # the worker's sandbox, as it was
            store.set(k, v)
