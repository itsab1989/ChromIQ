#!/usr/bin/env python3
"""AGENT-J step 1: enumerate every control of the scanner/camera window
FROM THE RUNNING APP (widget tree walk of the live dialog), in every mode."""
from __future__ import annotations
import os, sys, time, json
from pathlib import Path

ROOT = Path("/Users/Basti/develop/ChromIQ")
sys.path.insert(0, str(ROOT))
OUT = Path("/private/tmp/agentJ/out"); OUT.mkdir(parents=True, exist_ok=True)

try:
    import PyQt6.QtWebEngineWidgets  # noqa
except ImportError:
    pass
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (QApplication, QPushButton, QCheckBox, QRadioButton,
                             QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit,
                             QLabel, QToolButton, QSlider, QGroupBox, QTabWidget,
                             QPlainTextEdit, QTextEdit, QWidget)
from core.resource_path import resource_path

def pump(app, ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(); time.sleep(0.005)

INTERESTING = (QPushButton, QCheckBox, QRadioButton, QComboBox, QSpinBox,
               QDoubleSpinBox, QLineEdit, QToolButton, QSlider, QTabWidget)

def attrname(dlg, w):
    for k, v in vars(dlg).items():
        if v is w:
            return k
    return ""

def describe(dlg, w):
    d = {"class": type(w).__name__, "attr": attrname(dlg, w),
         "objectName": w.objectName(),
         "visible": w.isVisible(), "enabled": w.isEnabled()}
    try:
        d["text"] = w.text()
    except Exception:
        pass
    if isinstance(w, (QCheckBox, QRadioButton)):
        d["checked"] = w.isChecked()
    if isinstance(w, QPushButton):
        d["checkable"] = w.isCheckable()
        if w.isCheckable():
            d["checked"] = w.isChecked()
    if isinstance(w, QComboBox):
        d["count"] = w.count()
        d["current"] = w.currentText()
        d["items"] = [w.itemText(i) for i in range(min(w.count(), 40))]
        d["data"] = [w.itemData(i) for i in range(min(w.count(), 40))]
    if isinstance(w, (QSpinBox, QDoubleSpinBox)):
        d["value"] = w.value(); d["min"] = w.minimum(); d["max"] = w.maximum()
        d["suffix"] = w.suffix()
    if isinstance(w, QLineEdit):
        d["value"] = w.text(); d["placeholder"] = w.placeholderText()
    tt = w.toolTip()
    if tt:
        d["tooltip"] = tt[:400]
    return d

def walk(dlg, root):
    out = []
    for w in root.findChildren(QWidget):
        if isinstance(w, INTERESTING):
            out.append(describe(dlg, w))
    return out

def main():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    settings = AppSettings()
    settings.set("argyll_bin_path", "/Applications/Argyll/bin")
    runner = ArgyllRunner(settings)
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(runner, settings, None)
    dlg.show(); dlg.raise_(); pump(app, 1500)

    report = {}
    report["window_title"] = dlg.windowTitle()
    report["size"] = [dlg.width(), dlg.height()]
    # every python attribute that is a widget
    report["dialog_attrs"] = sorted(
        k for k, v in vars(dlg).items() if isinstance(v, QWidget))
    report["dialog_methods"] = sorted(
        m for m in dir(dlg) if m.startswith("_on_") or m.startswith("_pick")
        or m.startswith("_do_"))

    modes = {}
    for mode_attr in ("_mode_standard", "_mode_chromiq"):
        w = getattr(dlg, mode_attr, None)
        if w is None:
            modes[mode_attr] = "ABSENT"
            continue
        w.setChecked(True); pump(app, 900)
        modes[mode_attr] = {"label": w.text(), "controls": walk(dlg, dlg)}
    report["modes"] = modes
    (OUT / "enumeration.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print("modes present:", list(modes))
    print("attrs:", report["dialog_attrs"])
    dlg.close()
    return 0

sys.exit(main())
