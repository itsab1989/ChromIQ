#!/usr/bin/env python3
"""Open every CONTROL surface in Neutral and count the pixels that still carry a hue.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_neutral_controls.py <outdir>

Territory: the controls a person touches and the windows they open —
Preferences (every tab), the tool dialogs, the layout-options panel, the two
hand-painted popups, and the Create Chart panels.

Every window is grabbed and then walked with
``scripts.find_non_neutral_pixels.scan_widget``, which names the innermost
widget that painted each non-grey pixel. The number this prints is the finish
line: zero.

Sandboxed the same way ``drive_neutral_appearance.py`` is — the settings file,
the presets dir and ``custom_output_path`` are set BEFORE any ChromIQ import,
and the run refuses to start if the store it opened is not the sandbox.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/nctrl.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/nctrl-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/nctrl-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1
           else "/Users/Basti/Desktop/beta7/controls-proof/before")
MODE = os.environ.get("CHROMIQ_DRIVE_MODE", "neutral")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import Qt                                      # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

from scripts.find_non_neutral_pixels import scan_widget          # noqa: E402

#: Widget classes whose colour is the user's own data or another agent's job.
SKIP = ("TiffPreview", "GamutPanel", "PatchCubePanel", "ScanGridMarquee",
        "MastheadHeader", "SpectrumTabBar")


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _construct(cls, runner, settings, parent):
    """Build a dialog whatever argument order it takes.

    The tool windows are not uniform — some take ``(settings, parent)``, some
    ``(runner, settings, parent)``. Trying each in turn is what lets one driver
    open all of them; a dialog that matches none is reported, never skipped
    silently, because a window that quietly did not open measures zero.
    """
    from PyQt6.QtWidgets import QWidget as _QW
    for args in ((runner, settings, parent), (settings, parent), (parent,)):
        if any(a is None and not isinstance(a, _QW) for a in args[:-1]):
            if args[0] is None:
                continue
        try:
            return cls(*args)
        except TypeError:
            continue
        except Exception as exc:                          # noqa: BLE001
            print(f"    ({cls.__name__} raised {type(exc).__name__}: {exc})")
            return None
    return None


class Census:
    def __init__(self, outdir: Path):
        self.dir = outdir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.record: dict = {}

    def look(self, app, name: str, widget, skip=SKIP) -> int:
        fn = getattr(widget, "set_appearance", None)
        if callable(fn):
            try:
                fn(MODE)
            except Exception:                             # noqa: BLE001
                pass
        pump(app, 250)
        pm = widget.grab()
        if pm.isNull() or pm.width() <= 0:
            self.record[name] = {"error": "ungrabbable"}
            return 0
        pm.save(str(self.dir / f"{name}.png"))
        hits = scan_widget(widget, skip=skip)
        total = sum(h.pixels for h in hits)
        self.record[name] = {
            "total_non_neutral_px": total,
            "size": [pm.width(), pm.height()],
            "hits": [
                {"widget": h.widget, "object_name": h.object_name,
                 "px": h.pixels, "share_pct": round(h.share, 2),
                 "colours": [[c, n] for c, n in h.colours[:5]],
                 "path": h.path}
                for h in hits[:14]
            ],
        }
        print(f"  {name:38s} {total:7d} px  ({len(hits)} widgets)")
        return total


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    real_root = Path.home() / "ChromIQ"
    before_real = sum(1 for _ in real_root.rglob("*")) if real_root.exists() else 0

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
    print(f"settings store: {opened}")
    WORK.mkdir(parents=True, exist_ok=True)
    if str(settings.get("custom_output_path", "")) != str(WORK):
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
    if ONSCREEN:
        win.raise_(); win.activateWindow()
    pump(app, 1500)
    apply_appearance(app, win, MODE)
    pump(app, 900)

    c = Census(OUT)
    grand = 0

    # ---- Create Chart: the panels a person fills in ----------------------
    tabs = win._tabs
    tabs.setCurrentIndex(0)
    pump(app, 800)
    chart = win._tab_chart
    grand += c.look(app, "10-create-chart-guided", chart)
    # Manual mode, where the presets/layout panel lives
    for attr in ("_mode_manual_btn", "_manual_btn", "_btn_manual"):
        btn = getattr(chart, attr, None)
        if btn is not None:
            btn.click(); break
    pump(app, 900)
    grand += c.look(app, "11-create-chart-manual", chart)
    panel = getattr(chart, "_manual_layout_panel", None)
    if panel is not None:
        grand += c.look(app, "12-layout-options-panel", panel)

    # ---- The two hand-painted popups -------------------------------------
    from ui.tools_popup import ToolsPopup
    tp = ToolsPopup(win)
    tp.set_appearance(MODE)
    tp.resize(tp.sizeHint()); tp.show()
    pump(app, 400)
    grand += c.look(app, "20-tools-popup", tp)
    tp.hide(); tp.setParent(None); tp.deleteLater()

    try:
        from ui.builtin_preset_popup import BuiltinPresetButton
        bb = BuiltinPresetButton(win)
        bb.set_appearance(MODE)
        bb.resize(bb.sizeHint()); bb.show()
        pump(app, 300)
        grand += c.look(app, "21-builtin-preset-button", bb)
        bb.hide(); bb.setParent(None); bb.deleteLater()
    except Exception as exc:                              # noqa: BLE001
        print("  builtin preset button:", exc)

    pop = getattr(chart, "_builtin_popup", None)
    if pop is None:
        btn = getattr(chart, "_builtin_preset_btn", None)
        if btn is not None:
            btn.click()
            pump(app, 600)
            pop = getattr(chart, "_builtin_popup", None)
    if pop is not None and pop.isVisible():
        grand += c.look(app, "22-builtin-preset-popup", pop)
        pop.close()
    pump(app, 300)

    # ---- Preferences, every tab -------------------------------------------
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(settings, win)
    dlg.setWindowModality(Qt.WindowModality.NonModal)
    dlg.resize(980, 760)
    dlg.show()
    pump(app, 900)
    grand += c.look(app, "30-preferences", dlg)
    inner = None
    from PyQt6.QtWidgets import QTabWidget
    for tw in dlg.findChildren(QTabWidget):
        inner = tw
        break
    if inner is not None:
        for i in range(inner.count()):
            inner.setCurrentIndex(i)
            pump(app, 500)
            lbl = inner.tabText(i).strip().lower().replace(" ", "-").replace("&", "and")
            grand += c.look(app, f"31-prefs-{i:02d}-{lbl}", dlg)
    combo = getattr(dlg, "_appearance_combo", None)
    if combo is not None:
        combo.showPopup()
        pump(app, 500)
        view_win = combo.view().window()
        grand += c.look(app, "32-appearance-combo-popup", view_win)
        combo.hidePopup()
        pump(app, 200)
    dlg.close(); dlg.setParent(None); dlg.deleteLater()
    pump(app, 400)

    # ---- The tool dialogs --------------------------------------------------
    from ui.dialogs import tools_dialogs as td
    runner = getattr(win, "_runner", None)
    tool_classes = [
        ("40-average", td.AverageMeasurementsDialog),
        ("41-merge", td.MergeMeasurementsDialog),
        ("42-ti1-to-i1p", td.Ti1ToI1ProfilerDialog),
        ("43-i1p-to-ti3", td.I1ProfilerToTi3Dialog),
        ("44-i1p-to-ti1", td.I1ProfilerToTi1Dialog),
        ("45-verify-reference", td.VerifyAgainstReferenceDialog),
        ("46-verify-profile", td.VerifyProfileDialog),
    ]
    for name, cls in tool_classes:
        d = _construct(cls, runner, settings, win)
        if d is None:
            print(f"  {name}: could not construct")
            continue
        d.setWindowModality(Qt.WindowModality.NonModal)
        d.resize(760, 620)
        d.show()
        pump(app, 700)
        grand += c.look(app, name, d)
        d.close(); d.setParent(None); d.deleteLater()
        pump(app, 250)

    # ---- Other tool windows in the same family ----------------------------
    others = [
        ("50-ti3-info", "ui.dialogs.ti3_info_dialog", "Ti3InfoDialog"),
        ("51-profile-info", "ui.dialogs.profile_info_dialog", "ProfileInfoDialog"),
        ("52-spot-read", "ui.dialogs.spot_read_dialog", "SpotReadDialog"),
        ("53-devicelink", "ui.dialogs.devicelink_dialog", "DeviceLinkDialog"),
        ("54-devicelink-apply", "ui.dialogs.devicelink_apply_dialog", "DeviceLinkApplyDialog"),
        ("55-scanin-target", "ui.dialogs.scanin_target_dialog", "ScaninTargetDialog"),
        ("56-scanner-profile", "ui.dialogs.scanin_dialog", "ScannerProfileDialog"),
        ("57-translation", "ui.dialogs.translation_dialog", "TranslationDialog"),
        ("58-profile-info", "ui.dialogs.profile_info_dialog", "ProfileInfoDialog"),
        ("59-welcome", "ui.dialogs.welcome_dialog", "WelcomeDialog"),
        ("60-ti2-relayout", "ui.dialogs.ti2_relayout_dialog", "Ti2RelayoutDialog"),
    ]
    import importlib
    try:
        from ui.dialogs.preflight_dialog import PreflightDialog
        pf = PreflightDialog(
            [("Printer", "Canon PRO-300"), ("Paper size", "A4")],
            warnings=["Colour management could not be switched off"],
            pages=2, parent=win)
        pf.setWindowModality(Qt.WindowModality.NonModal)
        pf.show()
        pump(app, 500)
        grand_pf = c.look(app, "61-preflight", pf)
        pf.close(); pf.setParent(None); pf.deleteLater()
    except Exception as exc:                              # noqa: BLE001
        print("  61-preflight:", exc)
        grand_pf = 0
    for name, mod, cls_name in others:
        try:
            m = importlib.import_module(mod)
            cls = getattr(m, cls_name)
        except Exception as exc:                          # noqa: BLE001
            print(f"  {name}: SKIP ({type(exc).__name__}: {exc})")
            continue
        if cls_name == "WelcomeDialog":
            d = cls(settings, win, initial_mode=MODE)
        else:
            d = _construct(cls, runner, settings, win)
        if d is None:
            print(f"  {name}: SKIP (no constructor signature matched)")
            continue
        try:
            d.setWindowModality(Qt.WindowModality.NonModal)
            d.resize(820, 640)
            d.show()
            pump(app, 700)
            grand += c.look(app, name, d)
            d.close(); d.setParent(None); d.deleteLater()
        except Exception as exc:                          # noqa: BLE001
            print(f"  {name}: grab failed ({exc})")
        pump(app, 200)

    grand += grand_pf
    c.record["GRAND_TOTAL_non_neutral_px"] = grand
    (OUT / "census.json").write_text(json.dumps(c.record, indent=2, sort_keys=True))
    print(f"\nGRAND TOTAL non-neutral pixels: {grand}")
    print(f"wrote {OUT / 'census.json'}")

    win.close()
    pump(app, 400)
    after_real = sum(1 for _ in real_root.rglob("*")) if real_root.exists() else 0
    print(f"~/ChromIQ {before_real} -> {after_real}")
    return 0 if after_real == before_real else 2


if __name__ == "__main__":
    raise SystemExit(main())
