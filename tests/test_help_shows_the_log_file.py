"""A9 (4.3.50): the help card's text says "the log (Help → Show the log file) has the
details"; that entry now exists: the Help window (the "?" button, F1) has a
"Show the log file" button that shows chromiq.log in the file manager, selected where
the system can, on each platform's own path."""
from __future__ import annotations

from pathlib import Path

from core.reveal_file import reveal_command, reveal_file


def test_each_platform_gets_its_own_command(tmp_path):
    f = tmp_path / "chromiq.log"
    f.write_text("x", encoding="utf-8")
    assert reveal_command(f, "darwin") == ["open", "-R", str(f)]
    assert reveal_command(f, "win32") == ["explorer", f"/select,{f}"]
    assert reveal_command(f, "linux") == ["xdg-open", str(tmp_path)]
    missing = tmp_path / "logs" / "chromiq.log"
    assert reveal_command(missing, "darwin") == ["open", str(missing.parent)]
    assert reveal_command(missing, "win32") == ["explorer", str(missing.parent)]


def test_reveal_never_raises_and_makes_the_folder(tmp_path):
    ran = []
    target = tmp_path / "new" / "chromiq.log"
    assert reveal_file(target, "linux", runner=lambda cmd, **kw: ran.append(cmd))
    assert ran == [["xdg-open", str(target.parent)]] and target.parent.is_dir()

    def boom(*a, **k):
        raise OSError("no file manager")
    assert reveal_file(target, "linux", runner=boom) is False


def test_the_help_window_has_the_button_and_it_shows_the_log(qapp, monkeypatch, tmp_path):
    from core.settings import AppSettings
    from ui.dialogs import welcome_dialog as wd
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    shown = []
    import core.reveal_file as rf
    monkeypatch.setattr(rf, "reveal_file", lambda p, *a, **k: shown.append(Path(p)) or True)
    dlg = wd.WelcomeDialog(AppSettings())
    try:
        btn = dlg.findChild(wd.QPushButton, "help_show_log_file")
        assert btn is not None and btn.text() == "Show the log file"
        assert "chromiq.log" in btn.toolTip()
        btn.click()
        from core.platform_paths import log_dir
        assert shown == [log_dir() / "chromiq.log"]
    finally:
        dlg.deleteLater()


def test_the_help_text_names_the_button_by_its_label():
    import inspect
    from ui.dialogs import welcome_dialog as wd
    src = inspect.getsource(wd)
    assert "Help → Show the log file" in src and 'tr("Show the log file")' in src
