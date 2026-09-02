#!/usr/bin/env python3
"""The three faults the owner reported by eye — pictured and MEASURED.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/prove_neutral_control_faults.py <outdir>

1. **Preferences checkboxes are backwards.** Finds a ticked-and-enabled box and
   a ticked-and-disabled one in the same window, crops both, and reports the
   mean lightness of each indicator. "Enabled reads as ON, disabled recedes"
   is then a number: the enabled indicator must be DARKER than the disabled
   one on this light-grey ground, and the disabled one must carry no fill.
2. **Create Chart → Guided, the estimated-patches section.** Crops the
   Calculated Patches group and reports the ink of its largest glyphs.
3. **Combobox hover overlay.** Opens a real combo popup — its own top-level
   window, which `combo.grab()` cannot see — and reports the highlight colour
   and whether it carries a hue.

Run against the pre-change tree and the post-change tree; the numbers are the
proof and the crops are the picture.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if not os.environ.get("CHROMIQ_DRIVE_ONSCREEN"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/nctrl.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/nctrl-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/nctrl-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/nctrl-faults")
MODE = os.environ.get("CHROMIQ_DRIVE_MODE", "neutral")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, Qt                               # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase                     # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog,    # noqa: E402
                             QMessageBox, QTabWidget)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def census(pm, top: int = 6) -> dict:
    img = pm.toImage()
    c: Counter = Counter()
    for y in range(img.height()):
        for x in range(img.width()):
            col = img.pixelColor(x, y)
            if col.alpha() < 8:
                continue
            c[col.name()] += 1
    total = sum(c.values()) or 1
    hued = sum(n for h, n in c.items()
               if max(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))
               - min(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)) > 6)
    return {
        "top": [[h, round(100 * n / total, 1)] for h, n in c.most_common(top)],
        "hued_pct": round(100 * hued / total, 2),
        "mean_lightness": round(sum(QColor(h).lightness() * n
                                    for h, n in c.items()) / total, 1),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))

    from core.settings import AppSettings
    settings = AppSettings()
    if Path(settings._qs.fileName()) != SETTINGS_INI:
        raise SystemExit("REFUSING TO RUN: settings escaped the sandbox")
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", MODE)

    QDialog.exec = lambda self: 1                        # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                    # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    win = MainWindow(settings)
    win.resize(1340, 940)
    win.show()
    pump(app, 1500)
    apply_appearance(app, win, MODE)
    pump(app, 900)

    out: dict = {"mode": MODE}

    # ---- fault 2 first: the Calculated Patches group -------------------
    chart = win._tab_chart
    win._tabs.setCurrentIndex(0)
    pump(app, 700)
    lbl = getattr(chart, "_patch_count_lbl", None)
    if lbl is not None:
        grp = lbl.parentWidget()
        while grp is not None and type(grp).__name__ not in ("QGroupBox",
                                                             "CollapsibleGroupBox"):
            grp = grp.parentWidget()
        target = grp if grp is not None else lbl
        pm = target.grab()
        pm.save(str(OUT / "fault2-estimated-patches.png"))
        out["fault2_estimated_patches"] = census(pm, 8)
        pm2 = lbl.grab()
        pm2.save(str(OUT / "fault2-the-number-alone.png"))
        out["fault2_the_number_alone"] = census(pm2, 8)

    # ---- fault 1: Preferences checkboxes -------------------------------
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(settings, win)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.resize(980, 760)
    dlg.show()
    pump(app, 900)
    boxes = [b for b in dlg.findChildren(QCheckBox) if b.isVisible()]
    on_enabled = next((b for b in boxes if b.isChecked() and b.isEnabled()), None)
    on_disabled = next((b for b in boxes if b.isChecked() and not b.isEnabled()), None)
    # A checked+disabled box is state-dependent; make one deterministically.
    if on_disabled is None and boxes:
        cand = next((b for b in boxes if b is not on_enabled), None)
        if cand is not None:
            cand.setChecked(True)
            cand.setEnabled(False)
            pump(app, 300)
            on_disabled = cand
    for tag, box in (("enabled", on_enabled), ("disabled", on_disabled)):
        if box is None:
            continue
        pm = box.grab()
        pm.save(str(OUT / f"fault1-checkbox-{tag}.png"))
        # The indicator alone: Qt draws it at the left of the widget.
        ind = pm.copy(0, max(0, (pm.height() - 18) // 2), 18, 18)
        ind.save(str(OUT / f"fault1-indicator-{tag}.png"))
        out[f"fault1_{tag}"] = {"label": box.text(), **census(ind, 5)}
    dlg_shot = dlg.grab()
    dlg_shot.save(str(OUT / "fault1-preferences-window.png"))
    out["fault1_window"] = census(dlg_shot, 8)

    # ---- fault 3: the combobox popup, its own top-level window ---------
    combo = getattr(dlg, "_appearance_combo", None)
    if combo is not None:
        combo.showPopup()
        pump(app, 600)
        view = combo.view()
        top = view.window()
        # Put the highlight on a row that is NOT the current one, so the
        # overlay is what we are looking at rather than the selection.
        try:
            idx = view.model().index(min(1, view.model().rowCount() - 1), 0)
            view.setCurrentIndex(idx)
        except Exception:                                 # noqa: BLE001
            pass
        pump(app, 400)
        pm = top.grab()
        pm.save(str(OUT / "fault3-combo-popup.png"))
        out["fault3_combo_popup"] = census(pm, 8)
        combo.hidePopup()
        pump(app, 200)
    dlg.close(); dlg.setParent(None); dlg.deleteLater()
    pump(app, 300)

    # ---- fault 3b: a TOOL dialog's combo popup -------------------------
    # Preferences deliberately passes no popup accent, so its dropdown was
    # never the coloured one. A tool dialog hands `neutral_controls_qss` its
    # OWN accent for the hovered row — that is the overlay the owner meant.
    from PyQt6.QtWidgets import QComboBox
    from ui.dialogs import tools_dialogs as _td
    runner = getattr(win, "_runner", None)
    tool = tcombo = None
    for _cls, _needs in ((_td.Ti1ToI1ProfilerDialog, False),
                         (_td.VerifyProfileDialog, True),
                         (_td.VerifyAgainstReferenceDialog, True),
                         (_td.AverageMeasurementsDialog, False)):
        try:
            cand = _cls(runner, settings, win) if _needs else _cls(settings, win)
        except Exception:                                 # noqa: BLE001
            continue
        cand.setWindowModality(Qt.WindowModality.NonModal)
        cand.resize(760, 620)
        cand.show()
        pump(app, 800)
        found = next((c for c in cand.findChildren(QComboBox)
                      if c.isVisible() and c.count() > 1), None)
        if found is not None:
            tool, tcombo = cand, found
            out["fault3b_dialog"] = type(cand).__name__
            break
        cand.close(); cand.setParent(None); cand.deleteLater()
        pump(app, 200)
    if tcombo is not None:
        tcombo.showPopup()
        pump(app, 600)
        tview = tcombo.view()
        try:
            tview.setCurrentIndex(tview.model().index(
                min(1, tview.model().rowCount() - 1), 0))
        except Exception:                                 # noqa: BLE001
            pass
        pump(app, 400)
        pm = tview.window().grab()
        pm.save(str(OUT / "fault3b-tool-combo-popup.png"))
        out["fault3b_tool_combo_popup"] = census(pm, 8)
        tcombo.hidePopup()
        pump(app, 200)
    if tool is not None:
        tool.close(); tool.setParent(None); tool.deleteLater()
        pump(app, 300)

    (OUT / "faults.json").write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
