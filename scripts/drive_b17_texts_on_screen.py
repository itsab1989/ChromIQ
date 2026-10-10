#!/usr/bin/env python3
"""Beta 17: the new texts photographed in REAL windows (#182).

    CHROMIQ_SETTINGS_FILE=<report>/run/texts.ini \\
        python scripts/drive_b17_texts_on_screen.py <out> [en|de ...]

Preferences ▸ Measurement's misread table at the size the dialog opens at,
its four help windows; "Which presets can be used for verification?" with its
footer and its new help window; the Print Chart help with the plain-paper
paragraph. Each picture is the window's own buffer
(``onscreen_capture.capture_window``), taken without raising or activating it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass


def pump(app, ms):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this driver opens windows"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    langs = sys.argv[2:] or ["en", "de"]
    from capture_screens import build_app
    from onscreen_capture import capture_window
    app = build_app()
    from core.i18n import install_qt_translator, set_language
    from core.settings import AppSettings
    from ui.theme import apply_appearance
    s = AppSettings()
    s.set("appearance", "light")
    s.set("show_welcome", False)
    apply_appearance(app, None, "light")
    facts = {}
    for lang in langs:
        s.set("language", lang)
        set_language(lang)
        install_qt_translator(app)
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(s, None)
        tabs = dlg._tabs
        i = next(i for i in range(tabs.count())
                 if tabs.widget(i).isAncestorOf(dlg._misread_table))
        tabs.setCurrentIndex(i)
        dlg.show()
        pump(app, 1500)
        page = tabs.widget(i)
        y = dlg._misread_table.mapTo(page.widget(),
                                     dlg._misread_table.rect().topLeft()).y()
        page.verticalScrollBar().setValue(max(0, y - 140))
        pump(app, 700)
        t = dlg._misread_table
        facts[f"prefs_{lang}"] = {
            "dialog": [dlg.width(), dlg.height()],
            "table": [t.width(), t.height()],
            "table_minimum_width": t.minimumSizeHint().width(),
            "page_viewport_width": page.viewport().width(),
            "horizontal_scroll": page.horizontalScrollBar().maximum(),
            "spin_text_fits": all(
                sp.fontMetrics().horizontalAdvance(sp.text()) + 30 <= sp.width()
                for sp in list(dlg._patch_limit_spins.values())
                + list(dlg._neighbour_radius_spins.values())),
        }
        ok, why = capture_window(dlg, out / f"prefs_measurement_table_{lang}.png")
        facts[f"prefs_{lang}"]["photo"] = [ok, why]
        # the four help windows
        from ui.tooltip_button import TooltipButton, _InfoDialog
        for n, btn in enumerate(t.findChildren(TooltipButton), 1):
            info = _InfoDialog(btn._title if hasattr(btn, "_title") else "",
                               btn.dialog_body(), dlg, 640)
            info.setModal(False)
            info.show()
            pump(app, 900)
            capture_window(info, out / f"prefs_help_{n}_{lang}.png")
            info.close()
            pump(app, 200)
        dlg.close()
        pump(app, 300)
        # 13" screen: the same dialog squeezed to a 1280 x 800 work area
        dlg = SettingsDialog(s, None)
        tabs = dlg._tabs
        tabs.setCurrentIndex(i)
        dlg.resize(1240, 760)
        dlg.show()
        pump(app, 1200)
        page = tabs.widget(i)
        page.verticalScrollBar().setValue(max(0, dlg._misread_table.mapTo(
            page.widget(), dlg._misread_table.rect().topLeft()).y() - 60))
        pump(app, 600)
        facts[f"prefs_13in_{lang}"] = {
            "dialog": [dlg.width(), dlg.height()],
            "table": [dlg._misread_table.width(),
                      dlg._misread_table.minimumSizeHint().width()],
            "horizontal_scroll": page.horizontalScrollBar().maximum()}
        capture_window(dlg, out / f"prefs_measurement_table_13inch_{lang}.png")
        dlg.close()
        pump(app, 300)
        # the presets window
        from ui.dialogs.preset_verification_dialog import (
            PresetVerificationDialog)
        from ui.tabs.tab_chart import verification_preset_rows
        pv = PresetVerificationDialog(verification_preset_rows(s), None, None,
                                      background=True)
        pv.show()
        pump(app, 4000)
        pv._fill_figures()
        pump(app, 300)
        facts[f"presets_footer_{lang}"] = pv._figures.text()
        capture_window(pv, out / f"presets_window_{lang}.png")
        info = _InfoDialog(pv._own_colours_help._title,
                           pv._own_colours_help.dialog_body(), pv, 640)
        info.setModal(False)
        info.show()
        pump(app, 900)
        capture_window(info, out / f"presets_help_own_colours_{lang}.png")
        info.close()
        pv.close()
        pump(app, 300)
        # the Print Chart help
        from ui.tabs import tab_print as tp
        title, body = tp.TabPrint._compute_print_tooltip(
            type("T", (), {"_settings": s})())
        info = _InfoDialog(title, body, None, 640)
        info.setModal(False)
        info.show()
        pump(app, 900)
        capture_window(info, out / f"print_chart_help_{lang}.png")
        info.close()
        pump(app, 300)
    (out / "texts_on_screen.json").write_text(json.dumps(facts, indent=1,
                                                         ensure_ascii=False),
                                              encoding="utf-8")
    print(json.dumps(facts, indent=1, ensure_ascii=False))
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
