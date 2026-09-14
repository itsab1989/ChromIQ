#!/usr/bin/env python3
"""ADVERSARY 15 — READ three of the new help icons on a real screen.

Opens the REAL Report limits window, then builds the SAME `_InfoDialog` the
click builds (`TooltipButton._show_dialog`) and SHOWS it instead of `exec`-ing
it, so nothing blocks, and photographs it. The widget, the title and the body
are the ones a user gets.

    CHROMIQ_SETTINGS_FILE=... CHROMIQ_PRESETS_DIR=... \
        python scripts/adversary15_read_the_icons_on_screen.py <out-dir> [lang]
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
assert "QT_QPA_PLATFORM" not in os.environ, "a driver must not go offscreen"

from PyQt6.QtWidgets import QApplication                      # noqa: E402
from onscreen_capture import capture_window                   # noqa: E402

SHOW = ("solids_de00_max", "cmy_solids_dhab_max",
        "grey_balance_neutral_ramp_avg", "ramps_30_70_dl_max",
        "all_de00_avg", "worst5_de00_avg", "substrate_gloss_class")


def pump(app, ms=350):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core import i18n; i18n.set_language(lang)
    from core.settings import AppSettings
    import tempfile
    s = AppSettings(); s.set("custom_output_path", tempfile.mkdtemp(prefix="chromiq-adv15-out-"))
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.tooltip_button import TooltipButton, _InfoDialog
    from workflow.compliance_sets import ROW_BY_ID

    win = ThresholdsDialog(AppSettings(), None)
    win.setWindowTitle(f"ADV15 limits — {lang}")
    win.resize(1500, 950); win.show(); pump(app, 800)

    by_title = {}
    for b in win.findChildren(TooltipButton):
        by_title.setdefault(b._title, b)

    for rid in SHOW:
        row = ROW_BY_ID[rid]
        btn = by_title.get(i18n.tr(row.label))
        if btn is None:
            print(f"  !! no icon found for {rid}"); continue
        dlg = _InfoDialog(btn._title, btn.dialog_body(), win, btn._min_width)
        dlg.setWindowTitle(f"ADV15 {rid} — {lang}")
        dlg.show(); pump(app, 700)
        ok, why = capture_window(dlg, out / f"help-{lang}-{rid}.png")
        print(f"  {rid:32s} photo={'ok' if ok else 'FAILED: ' + why}")
        print("      body:", btn.dialog_body().replace("\n", " | ")[:400])
        dlg.close(); pump(app, 150)
    win.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
