#!/usr/bin/env python3
"""Grab, at REAL SIZE, every icon this branch changed -- and hash whole windows.

Two jobs, one app launch, because both need the same sandboxed window:

* ``icons`` -- a named grab of each mark the owner is looking at, saved one file
  per mark so a before tree and an after tree can be put side by side at the
  size he sees them. Nothing is scaled: an icon judged at 4x is not judged.
* ``hash``  -- sha256 of whole grabbed windows, so LIGHT AND DARK can be proved
  not to have moved. The pointer is parked and focus is dropped before every
  grab: a focus ring and a hovered widget have each been reported as a
  regression on this branch's predecessors, and neither was one.

Runs identically in this tree and in a ``git archive`` of master, which is what
makes the comparison mean anything.

    CHROMIQ_ICONS_MODE=neutral python scripts/prove_neutral_icons.py <outdir>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODE = os.environ.get("CHROMIQ_ICONS_MODE", "neutral")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else f"/tmp/icons-proof/{MODE}")
OUT.mkdir(parents=True, exist_ok=True)

INI = Path("/tmp/icons-agent.ini")
WORK = Path("/tmp/icons-agent-work")
PRESETS = Path("/tmp/icons-agent-presets")
WORK.mkdir(parents=True, exist_ok=True)
PRESETS.mkdir(parents=True, exist_ok=True)
INI.write_text(f"[General]\ncustom_output_path={WORK}\nappearance={MODE}\n",
               encoding="utf-8")
os.environ["CHROMIQ_SETTINGS_FILE"] = str(INI)
os.environ["CHROMIQ_PRESETS_DIR"] = str(PRESETS)
# A stable working directory: the Paths tab shows the one the driver was
# launched from, which differs between two trees and is not a theme difference.
os.chdir(str(WORK))

from PyQt6.QtCore import QPoint                                  # noqa: E402
from PyQt6.QtGui import QCursor                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget                # noqa: E402

app = QApplication(sys.argv[:1])
from main import WinButtonLayoutStyle                            # noqa: E402
app.setStyle(WinButtonLayoutStyle("Fusion"))
QCursor.setPos(QPoint(0, 0))          # park the pointer: no hover state anywhere

from core.settings import AppSettings                            # noqa: E402
s = AppSettings()
if str(INI) not in str(getattr(s, "_qs").fileName()):
    raise SystemExit("REFUSING TO RUN: settings are not the sandbox file")
s.set("custom_output_path", str(WORK))
s.set("appearance", MODE)

from ui.main_window import MainWindow                            # noqa: E402
from ui.theme import apply_appearance                            # noqa: E402

win = MainWindow(s)
apply_appearance(app, win, MODE)
win.resize(1500, 1000)
win.show()
for _ in range(120):
    app.processEvents()


def settle() -> None:
    fw = QApplication.focusWidget()
    if fw is not None:
        fw.clearFocus()                # a focus ring is not a theme difference
    for _ in range(40):
        app.processEvents()


def grab(name: str, w) -> None:
    if w is None:
        print(f"  MISSING {name}")
        return
    settle()
    pm = w.grab()
    pm.save(str(OUT / f"{name}.png"))
    print(f"  {name:34s} {pm.width()}x{pm.height()}")


def first(root, cls_name: str, n: int = 0):
    found = [c for c in root.findChildren(QWidget)
             if type(c).__name__ == cls_name and c.isVisible()]
    return found[n] if len(found) > n else None


tabs = win._tabs
mast = win._masthead

# ---- the four marks the owner named, each on its own -------------------
tabs.setCurrentIndex(1)
for _ in range(60):
    app.processEvents()
grab("01-open-project", getattr(mast, "_load_project_btn", None))
grab("02-open-chart-file", getattr(mast, "_load_ti2_btn", None))
grab("03-close-project", getattr(mast, "_close_project_btn", None))
grab("04-tools", getattr(mast, "_tools_btn", None))
grab("05-masthead-left-group", mast)

# ---- the two he did not name, on the same screenshot -------------------
grab("06-print-image-file", first(tabs.widget(1), "ImageFileButton"))
grab("07-print-reveal-folder", first(tabs.widget(1), "RevealFolderButton"))
beast = None
for gb in tabs.widget(1).findChildren(QWidget):
    if type(gb).__name__ == "QGroupBox" and gb.isVisible() and gb.height() < 160:
        txt = " ".join(l.text() for l in gb.findChildren(QWidget)
                       if hasattr(l, "text"))
        if "beast" in txt or "hungry" in txt:
            beast = gb
            break
grab("08-feed-the-beast-card", beast)

# ---- the rest of the family, so they can be judged together -----------
tabs.setCurrentIndex(0)
for _ in range(60):
    app.processEvents()
grab("09-chart-patch-grid", first(tabs.widget(0), "PatchGridButton"))
grab("10-chart-reveal-folder", first(tabs.widget(0), "RevealFolderButton"))
bar = None
for c in mast.findChildren(QWidget):
    if c.objectName() == "target_bar" and c.isVisible():
        bar = c
        break
grab("11-profile-run-bar", bar)
tabs.setCurrentIndex(3)
for _ in range(60):
    app.processEvents()
grab("12-measured-chart", first(tabs.widget(3), "MeasuredChartButton"))
tabs.setCurrentIndex(2)
for _ in range(60):
    app.processEvents()
grab("13-measure-header", first(tabs.widget(2), "TabHeader"))

# ---- whole windows, hashed --------------------------------------------
digests: dict = {}
for i in range(tabs.count()):
    tabs.setCurrentIndex(i)
    for _ in range(60):
        app.processEvents()
    settle()
    pm = win.grab()
    img = pm.toImage()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    digests[f"tab{i}"] = hashlib.sha256(bytes(ptr)).hexdigest()
    pm.save(str(OUT / f"window-tab{i}.png"))

(OUT / "hashes.json").write_text(json.dumps(digests, indent=1), encoding="utf-8")
print(f"[{MODE}] {len(digests)} window hashes -> {OUT/'hashes.json'}")
