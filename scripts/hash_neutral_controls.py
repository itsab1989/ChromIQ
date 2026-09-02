#!/usr/bin/env python3
"""Grab every control surface in ONE appearance and hash it.

    CHROMIQ_DRIVE_ONSCREEN=1 CHROMIQ_DRIVE_MODE=light \\
        python scripts/hash_neutral_controls.py <outdir>

Run it against the pre-change tree and against the post-change tree, in Light
and in Dark. Every hash must be identical: **Light and Dark must not change at
all.** The controls in this territory are the ones a person touches constantly,
so a regression here is the most visible kind there is.

Same sandbox discipline as the census driver, and the same window list, so the
two records line up grab for grab.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# RUN FROM A FIXED DIRECTORY. One field on the Paths tab falls back to
# the working directory, so a hash taken in the pre-change TREE and one
# taken in the post-change tree differ by the tree's own name — a
# difference in where the driver was launched, not in what the app paints.
os.chdir(os.environ.get('CHROMIQ_HASH_CWD', '/tmp'))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/nctrl.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/nctrl-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/nctrl-work"))
MODE = os.environ.get("CHROMIQ_DRIVE_MODE", "light")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else f"/tmp/nctrl-hash-{MODE}")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import Qt                                      # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox, # noqa: E402
                             QTabWidget)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def sha(pixmap) -> str:
    img = pixmap.toImage()
    b = img.bits()
    b.setsize(img.sizeInBytes())
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


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
    opened = Path(settings._qs.fileName())
    if opened != SETTINGS_INI:
        raise SystemExit(f"REFUSING TO RUN: settings escaped the sandbox: {opened}")
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", MODE)

    QDialog.exec = lambda self: 1                        # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                    # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance

    # PARK THE POINTER. A checkbox under the cursor wears
    # `QCheckBox::indicator:hover { border-color: <tab accent> }`, so where the
    # mouse happens to be sitting lands in the hash — one run differed from
    # another by 292 pixels of pink border, which looks exactly like a
    # regression and is the physical mouse. Move it to the corner of the screen
    # so every run is driven from the same state.
    from PyQt6.QtGui import QCursor, QGuiApplication as _QGA
    _scr = _QGA.primaryScreen()
    if _scr is not None:
        _g = _scr.availableGeometry()
        QCursor.setPos(_g.right() - 2, _g.bottom() - 2)

    win = MainWindow(settings)
    win.resize(1340, 940)
    win.show()
    if ONSCREEN:
        win.raise_(); win.activateWindow()
    pump(app, 1500)
    apply_appearance(app, win, MODE)
    pump(app, 900)

    rec: dict = {}

    def take(name: str, widget) -> None:
        fn = getattr(widget, "set_appearance", None)
        if callable(fn):
            try:
                fn(MODE)
            except Exception:                            # noqa: BLE001
                pass
        pump(app, 250)
        pm = widget.grab()
        if pm.isNull() or pm.width() <= 0:
            rec[name] = "ungrabbable"
            return
        pm.save(str(OUT / f"{name}.png"))
        rec[name] = sha(pm)
        print(f"  {name:38s} {rec[name]}")

    tabs = win._tabs
    tabs.setCurrentIndex(0)
    pump(app, 800)
    chart = win._tab_chart
    take("10-create-chart-guided", chart)
    for attr in ("_mode_manual_btn", "_manual_btn", "_btn_manual"):
        btn = getattr(chart, attr, None)
        if btn is not None:
            btn.click(); break
    pump(app, 900)
    take("11-create-chart-manual", chart)
    panel = getattr(chart, "_manual_layout_panel", None)
    if panel is not None:
        take("12-layout-options-panel", panel)

    from ui.tools_popup import ToolsPopup
    tp = ToolsPopup(win); tp.set_appearance(MODE)
    tp.resize(tp.sizeHint()); tp.show(); pump(app, 400)
    take("20-tools-popup", tp)
    tp.hide(); tp.setParent(None); tp.deleteLater()

    from ui.builtin_preset_popup import BuiltinPresetButton
    bb = BuiltinPresetButton(win); bb.set_appearance(MODE)
    bb.resize(bb.sizeHint()); bb.show(); pump(app, 300)
    take("21-builtin-preset-button", bb)
    bb.hide(); bb.setParent(None); bb.deleteLater()

    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(settings, win)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.resize(980, 760); dlg.show(); pump(app, 900)
    take("30-preferences", dlg)
    inner = next(iter(dlg.findChildren(QTabWidget)), None)
    if inner is not None:
        for i in range(inner.count()):
            inner.setCurrentIndex(i)
            pump(app, 500)
            lbl = inner.tabText(i).strip().lower().replace(" ", "-").replace("&", "and")
            take(f"31-prefs-{i:02d}-{lbl}", dlg)
    combo = getattr(dlg, "_appearance_combo", None)
    if combo is not None:
        combo.showPopup(); pump(app, 500)
        take("32-appearance-combo-popup", combo.view().window())
        combo.hidePopup(); pump(app, 200)
    dlg.close(); dlg.setParent(None); dlg.deleteLater(); pump(app, 400)

    from ui.dialogs import tools_dialogs as td
    runner = getattr(win, "_runner", None)
    for name, cls, needs_runner in (
        ("40-average", td.AverageMeasurementsDialog, False),
        ("41-merge", td.MergeMeasurementsDialog, False),
        ("42-ti1-to-i1p", td.Ti1ToI1ProfilerDialog, False),
        ("43-i1p-to-ti3", td.I1ProfilerToTi3Dialog, True),
        ("44-i1p-to-ti1", td.I1ProfilerToTi1Dialog, False),
        ("45-verify-reference", td.VerifyAgainstReferenceDialog, True),
        ("46-verify-profile", td.VerifyProfileDialog, True),
    ):
        try:
            d = cls(runner, settings, win) if needs_runner else cls(settings, win)
        except Exception as exc:                          # noqa: BLE001
            print(f"  {name}: {exc}")
            continue
        d.setWindowModality(Qt.WindowModality.NonModal)
        d.resize(760, 620); d.show(); pump(app, 700)
        take(name, d)
        d.close(); d.setParent(None); d.deleteLater(); pump(app, 250)

    from ui.dialogs.welcome_dialog import WelcomeDialog
    wd = WelcomeDialog(settings, win, initial_mode=MODE)
    wd.setWindowModality(Qt.WindowModality.NonModal)
    wd.resize(900, 700); wd.show(); pump(app, 900)
    take("50-welcome", wd)
    wd.close(); wd.setParent(None); wd.deleteLater(); pump(app, 300)

    from ui.dialogs.preflight_dialog import PreflightDialog
    pf = PreflightDialog([("Printer", "Canon PRO-300"), ("Paper size", "A4")],
                         warnings=["Colour management could not be switched off"],
                         pages=2, parent=win)
    pf.setWindowModality(Qt.WindowModality.NonModal)
    pf.show(); pump(app, 500)
    take("51-preflight", pf)
    pf.close(); pf.setParent(None); pf.deleteLater()

    (OUT / "hashes.json").write_text(json.dumps(rec, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n{len(rec)} grabs -> {OUT / 'hashes.json'}")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
