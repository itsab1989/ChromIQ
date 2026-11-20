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
    assert reveal_command(f, "win32") == f'explorer /select,"{f}"'
    assert reveal_command(f, "linux") == ["xdg-open", str(tmp_path)]
    missing = tmp_path / "logs" / "chromiq.log"
    assert reveal_command(missing, "darwin") == ["open", str(missing.parent)]
    assert reveal_command(missing, "win32") == f'explorer "{missing.parent}"'


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
    assert "press “Show the " in src and 'tr("Show the log file")' in src
    # 4.3.51 release (the re-review, S5): on a help card the button is hidden, so the card's
    # print-failure text no longer says "Help → Show the log file"
    assert "Help → Show the log file" not in src


def test_the_print_failure_text_is_true_on_a_card_in_every_language(qapp, monkeypatch,
                                                                     tmp_path):
    """4.3.51 release (the re-review, S5): the card's print-failure text sends the person to the
    Help window's first page, where the button is shown (directly left of Close), and to
    Preferences → Paths, "Log file:", which always works; in every language, with the labels
    the app shows there."""
    import json
    from core.settings import AppSettings
    from ui.dialogs import welcome_dialog as wd
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    dlg = wd.WelcomeDialog(AppSettings())
    try:
        dlg._stack.setCurrentIndex(1)                    # a card
        assert dlg._log_btn.isHidden() and not dlg._back_btn.isHidden()
        dlg._stack.setCurrentIndex(0)                    # the first page
        assert not dlg._log_btn.isHidden()
    finally:
        dlg.deleteLater()
    key = next(k for k in json.loads((Path(wd.__file__).resolve().parents[2] / "data" /
                                      "i18n" / "de.json").read_text(encoding="utf-8"))
               if k.startswith("Something went wrong while preparing this help card"))
    assert "first page of this Help window" in key and "Preferences → Paths" in key
    assert "directly left of “Close”" in key and "Help → Show the log file" not in key
    i18n_dir = Path(wd.__file__).resolve().parents[2] / "data" / "i18n"
    for p in sorted(i18n_dir.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        text = d[key]
        for label in ("Show the log file", "Close", "Paths", "Log file:"):
            assert d[label].rstrip(" :：") in text, (p.stem, label)
        assert "→" in text and text.count(d["Show the log file"]) == 1, p.stem


def test_a_windows_path_with_a_space_is_quoted_round_the_path_only(tmp_path):
    """S7: the list form made Python quote "/select,<path>" as one argument when
    the account name has a space, and Explorer then opens Documents."""
    from core.reveal_file import reveal_command
    d = tmp_path / "Ann Lee"
    d.mkdir()
    f = d / "chromiq.log"
    f.write_text("x", encoding="utf-8")
    cmd = reveal_command(f, "win32")
    assert isinstance(cmd, str)
    assert cmd == f'explorer /select,"{f}"' and '"/select' not in cmd


def test_the_log_button_sits_directly_left_of_close_and_close_stays(qapp, monkeypatch, tmp_path):
    """The owner, 2026-11-20: "the show the log file button in the help window should be on the
    left next to the close button" and "close stays where it is". Close keeps its cell (the
    footer's right end), its size and its behaviour; the log button is the next button to its
    left in the same row, and it never becomes a default button (Enter, Esc as before)."""
    from core.settings import AppSettings
    from ui.dialogs import welcome_dialog as wd
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    dlg = wd.WelcomeDialog(AppSettings())
    try:
        dlg.resize(1800, 900)
        dlg.show()
        qapp.processEvents()
        log = dlg.findChild(wd.QPushButton, "help_show_log_file")
        close = dlg._close_btn
        assert log.parent() is close.parent() is dlg._footer_right
        lay = dlg._footer_right.layout()
        assert lay.indexOf(log) == lay.indexOf(close) - 1
        g_log, g_close = log.geometry(), close.geometry()
        assert g_log.top() == g_close.top() and g_log.right() < g_close.left()
        assert g_close.left() - g_log.right() <= lay.spacing() + 1
        # Close: the right end of the footer's right cell, as before
        assert g_close.right() == dlg._footer_right.width() - 1
        assert not log.autoDefault() and not log.isDefault()
        # and the left cell keeps only the start-up tick box
        assert dlg._footer_left.findChild(wd.QPushButton) is None
    finally:
        dlg.deleteLater()


def test_at_the_minimum_width_nothing_overlaps_and_close_keeps_its_margin(qapp, monkeypatch,
                                                                         tmp_path):
    from core.settings import AppSettings
    from ui.dialogs import welcome_dialog as wd
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    dlg = wd.WelcomeDialog(AppSettings())
    try:
        dlg.show()
        qapp.processEvents()
        dlg.resize(dlg.minimumWidth(), dlg.minimumHeight())
        qapp.processEvents()
        log, close = dlg._log_btn, dlg._close_btn
        assert log.isVisible()
        right = close.mapTo(dlg, close.rect().topRight()).x()
        left_edge = dlg._show_cb.mapTo(dlg, dlg._show_cb.rect().topLeft()).x()
        assert dlg.width() - 1 - right >= left_edge - 2       # the same margin both sides
        # and the support link on the window's centre line
        sup = dlg._support_btn
        centre = sup.mapTo(dlg, sup.rect().center()).x()
        assert abs(centre - dlg.width() / 2) <= 3
        assert log.mapTo(dlg, log.rect().topRight()).x() < close.mapTo(
            dlg, close.rect().topLeft()).x()
        for b in (log, close):
            assert b.width() >= b.sizeHint().width()
    finally:
        dlg.deleteLater()

