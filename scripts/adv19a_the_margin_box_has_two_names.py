#!/usr/bin/env python3
"""Adversary 19a, in a REAL window.

F1  THE BOTTOM-TEXT WARNING NAMES A MARGIN BOX THAT DOES NOT EXIST IN SIX
    LANGUAGES.

    The change set replaced the two "raise Bottom" wordings with new keys and
    the twelve catalogues were re-translated. In it, no, pl, ru, sv and zh_CN
    the NEW translation of the quoted control name no longer matches the label
    that language's own "Margins (mm)" row carries -- and every one of the
    REMOVED strings had it right.

    zh_CN is the worst: the message says 「下」, which is the label of the "B"
    box in the same dialog, and the very next sentence of the same notice also
    says 「下」 meaning that other box.
"""
from __future__ import annotations

import json, os, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel,   # noqa: E402
                             QMessageBox)
sys.path.insert(0, str(ROOT / "scripts"))                      # noqa: E402
from onscreen_capture import capture_window                    # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    lang = sys.argv[2]
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)

    from core.i18n import set_language, tr
    set_language(lang)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix=f"chromiq-adv19a-{lang}-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)), ("language", lang),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True)):
        settings.set(k, v)
    assert settings.get("custom_output_path", "") == str(work)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1080)
    win.show(); win.raise_(); pump(app, 2500)
    onscreen = bool(win.isVisible())
    print(f"    [{lang}] window on screen: {onscreen}", flush=True)

    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText(f"adv19a-{lang}")
    pump(app, 600)
    panel = tab._manual_layout_panel
    if panel.instr.findData("i1") >= 0:
        panel.instr.setCurrentIndex(panel.instr.findData("i1")); pump(app, 900)
    if panel.paper.findData("A4") >= 0:
        panel.paper.setCurrentIndex(panel.paper.findData("A4")); pump(app, 600)
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    for k, v in (("t", 12.0), ("b", 12.0), ("l", 10.0), ("r", 10.0)):
        panel.margins[k].setValue(v)
    # a bottom line big enough to reach the patches, small enough that a rise
    # inside the box's 60 mm still clears it -> the "raise Bottom" branch
    panel.chart_text.setText("ChromIQ adversary 19")
    panel.stamp_command.setChecked(False)
    try: tab._manual_stamp_cmd_check.setChecked(False)
    except Exception: pass
    panel.chart_text_size.setValue(28.0)
    pump(app, 1500)

    # what the WINDOW calls the bottom margin box, read off the live widget
    wanted = tr("Bottom")
    labels = [w.text() for w in panel.findChildren(QLabel)
              if w.text().strip().rstrip(":") == wanted.rstrip(":")]
    notices = TabChart._engine_text_notes(tab)
    _all = list(notices[0]) + list(notices[1])
    bottom_notes = [m for m in _all if tr("Margins (mm):").rstrip(":") in m]
    res = {"lang": lang, "window_on_screen": onscreen,
           "window_bottom_label": wanted,
           "label_widgets_found": labels,
           "B_box_label": tr("B"),
           "margins_group": tr("Margins (mm):"),
           "notices": bottom_notes}
    print(f"    [{lang}] the window labels the box  : {wanted!r}", flush=True)
    print(f"    [{lang}] the same window labels 'B' : {tr('B')!r}", flush=True)
    for m in bottom_notes:
        print(f"    [{lang}] NOTICE: {m}", flush=True)
    (out / f"adv19a-{lang}.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    # bring the "Margins (mm)" row itself into the picture, so the label the
    # window carries and the name the message uses are one photograph apart.
    try:
        from PyQt6.QtWidgets import QScrollArea, QAbstractScrollArea
        sa = None
        w = panel.margins["b"]
        while w is not None:
            if isinstance(w, QAbstractScrollArea): sa = w; break
            w = w.parentWidget()
        if sa is not None:
            sa.ensureWidgetVisible(panel.margins["b"], 50, 200)
            pump(app, 700)
    except Exception as e:
        print("    scroll failed:", e)
    capture_window(win, out / f"F1-{lang}-the-box-has-two-names.png")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
