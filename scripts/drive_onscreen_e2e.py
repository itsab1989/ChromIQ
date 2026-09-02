"""End-to-end ON-SCREEN run of the real ChromIQ app (Sebastian, #130 2026-07-29).

    source .venv/bin/activate
    python scripts/drive_onscreen_e2e.py      # screenshots + report in ~/chromiq-e2e

A real window opens; nothing is measured and no project is touched.

Mirrors main.py's setup exactly — the vendored fonts, the Fusion style with the
Windows button layout, and above all the ButtonFontFilter, because the whole
button-clipping saga was about a font swap that only happens at polish, and
polish only happens on a real screen.

Every step writes a stage line and a screenshot, so a hang is locatable and the
result is evidence rather than a claim.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)          # a REAL screen, not offscreen
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get("CHROMIQ_E2E_OUT", Path.home() / "chromiq-e2e"))
OUT.mkdir(exist_ok=True)
STAGES = OUT / "stages.txt"
STAGES.write_text("", encoding="utf-8")


def stage(text: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {text}\n"
    with STAGES.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line.rstrip(), flush=True)


import PyQt6.QtWebEngineWidgets  # noqa: F401,E402  — before QApplication
from PyQt6.QtCore import QRect, QTimer  # noqa: E402
from PyQt6.QtGui import QFont, QFontDatabase, QFontMetrics  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,  # noqa: E402
                             QPushButton)

from core.resource_path import resource_path            # noqa: E402
from core.settings import AppSettings                   # noqa: E402
from ui.widgets import ButtonFontFilter                 # noqa: E402
from ui.styles import WinButtonLayoutStyle    # noqa: E402

stage("imports done")

app = QApplication(sys.argv)
app.setApplicationName("ChromIQ")
app.setOrganizationName("ChromIQ")
try:
    for font_path in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_path))
except Exception:
    pass
app.setStyle(WinButtonLayoutStyle("Fusion"))
_filter = ButtonFontFilter(app)
app.installEventFilter(_filter)
stage(f"QApplication up, platform={app.platformName()}")


def pump(seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(widget, name: str) -> None:
    pump(0.35)
    widget.grab().save(str(OUT / f"{name}.png"))
    stage(f"screenshot {name}.png")


def painted_width(btn: QPushButton) -> int:
    """What the button's text will actually take, in the font it is painted in.

    The WIDEST LINE, not the whole string. A label written over two lines is
    drawn as two lines, so measuring "Save as\nDefaults" end to end asks for the
    width of "SAVE ASDEFAULTS" and reports a perfectly good button as clipped —
    which is exactly what this script did on its second run. It is the same rule
    fit_button_width applies, and the two must agree or the check is worthless.
    """
    text = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    if btn.font().capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    fm = QFontMetrics(btn.font())
    return max(fm.horizontalAdvance(line) for line in text.split("\n"))


REPORT: list[str] = []


def check_overlap(window, label: str) -> None:
    """Do any two visible buttons sit on top of one another?

    A DIFFERENT question from "is each button wide enough", and the one nobody
    asked until Sebastian read it off the screenshots (#130, 2026-07-29). Print
    Chart overlapped in three places and Measure in one while every button was
    individually wide enough for its text.
    """
    btns = [b for b in window.findChildren(QPushButton)
            if b.isVisible() and b.text().strip()]
    hits = []
    for i in range(len(btns)):
        for j in range(i + 1, len(btns)):
            a = QRect(btns[i].mapTo(window, btns[i].rect().topLeft()),
                      btns[i].size())
            b = QRect(btns[j].mapTo(window, btns[j].rect().topLeft()),
                      btns[j].size())
            if a.intersects(b):
                hits.append(f"{btns[i].text()!r} over {btns[j].text()!r} by "
                            f"{a.intersected(b).width()}px")
    if hits:
        REPORT.append(f"OVERLAP in {label}: " + "; ".join(hits))
        stage(f"!! {len(hits)} overlapping pair(s) in {label}")
    else:
        REPORT.append(f"OK {label}: no buttons overlap")


def check_buttons(window, label: str) -> None:
    """THE check that could never be done offscreen: measure every button
    against the font it is really painted in, after polish."""
    bad = []
    for btn in window.findChildren(QPushButton):
        if not btn.isVisible() or not btn.text().strip():
            continue
        need = painted_width(btn)
        have = btn.width()
        if have < need:
            bad.append(f"{btn.text()!r}: {have}px painted into {need}px needed")
    if bad:
        REPORT.append(f"CLIPPED in {label}: " + "; ".join(bad))
        stage(f"!! {len(bad)} clipped button(s) in {label}")
    else:
        n = sum(1 for b in window.findChildren(QPushButton)
                if b.isVisible() and b.text().strip())
        REPORT.append(f"OK {label}: {n} visible buttons, none clipped")
        stage(f"ok {label}: {n} buttons all wide enough")


settings = AppSettings()
settings.migrate()

from ui.main_window import MainWindow            # noqa: E402
from ui.theme import apply_appearance            # noqa: E402

stage("building MainWindow")
win = MainWindow(settings)
apply_appearance(app, win, settings.get("appearance", "auto"))
win.resize(1400, 900)
win.show()
stage("MainWindow.show() returned")
pump(1.2)
stage(f"MainWindow visible={win.isVisible()} size={win.width()}x{win.height()}")
shot(win, "01_main_window")
check_buttons(win, "main window")
check_overlap(win, "main window")

# ---- every tab, on screen -------------------------------------------------
tabs = win.tabs if hasattr(win, "tabs") else None
if tabs is None:
    from PyQt6.QtWidgets import QTabWidget
    cands = [t for t in win.findChildren(QTabWidget) if t.count() >= 4]
    tabs = cands[0] if cands else None
if tabs is not None:
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        pump(0.5)
        name = tabs.tabText(i).replace(" ", "_").replace("&", "")
        shot(win, f"02_tab_{i}_{name}")
        check_buttons(win, f"tab “{tabs.tabText(i)}”")
        check_overlap(win, f"tab “{tabs.tabText(i)}”")
else:
    REPORT.append("could not find the tab widget")

# ---- Preferences → Measurement: the beta.92 column -----------------------
stage("opening Preferences")
from ui.dialogs.settings_dialog import SettingsDialog     # noqa: E402
dlg = SettingsDialog(settings, win)
dlg.resize(1150, 860)
dlg.show()
pump(0.8)
from PyQt6.QtWidgets import QTabWidget                    # noqa: E402
inner = dlg.findChildren(QTabWidget)
if inner:
    tw = inner[0]
    for i in range(tw.count()):
        if tw.tabText(i) == "Measurement":
            tw.setCurrentIndex(i)
pump(0.6)
shot(dlg, "03_preferences_measurement")
check_buttons(dlg, "Preferences")
check_overlap(dlg, "Preferences")
rows = []
for key in ("i1pro", "i1pro2", "i1pro3", "i1pro3plus", "colormunki", "spectroscan"):
    rows.append(f"{key}: patches={dlg._pace_patches[key].text()} "
                f"min={dlg._pace_min[key].text()} "
                f"speed={dlg._pace_estimate[key].text()}")
REPORT.append("Preferences → Measurement rows (on screen): " + " | ".join(rows))
# the boxes must not be clipped either
from PyQt6.QtWidgets import QAbstractSpinBox               # noqa: E402
narrow = [b.objectName() or b.text() for b in dlg.findChildren(QAbstractSpinBox)
          if b.isVisible() and b.width() < b.sizeHint().width()]
REPORT.append(f"spin boxes narrower than their hint: {len(narrow)}")
dlg.close()
pump(0.4)

# ---- a NATIVE alert, the window the clipping saga was really about -------
stage("opening a native-style alert with the longest destructive label")
import core.run_delete as rd                               # noqa: E402
from ui.widgets import fit_message_box_buttons             # noqa: E402
plan = rd.DeletePlan(kind=rd.KIND_RUN, run_id="run4", project_name="P",
                     lands_on="run4")
box = QMessageBox(win)
box.setIcon(QMessageBox.Icon.NoIcon)
box.setWindowTitle(rd.title_for(plan))
box.setText(rd.title_for(plan))
box.setInformativeText(rd.message_for(plan))
kill = box.addButton(rd.confirm_label(plan), QMessageBox.ButtonRole.DestructiveRole)
box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
fit_message_box_buttons(box)
box.show()
pump(0.9)
shot(box, "04_delete_alert")
for b in box.buttons():
    need, have = painted_width(b), b.width()
    mark = "OK " if have >= need else "CLIPPED "
    REPORT.append(f"{mark}alert button {b.text()!r}: {have}px vs {need}px needed "
                  f"(font {b.font().family()}, caps="
                  f"{b.font().capitalization() == QFont.Capitalization.AllUppercase})")
box.close()
pump(0.3)

# ---- the restore-window wording from beta.93 -----------------------------
stage("opening the restored-chart window (beta.93 wording)")
import workflow.verify_chart_snapshot as vcs               # noqa: E402
for order, number, tag in ((vcs.ORDER_FIXED, "1916078606", "fixed"),
                           (vcs.ORDER_SHUFFLED, "1916078606", "shuffled")):
    b = QMessageBox(win)
    b.setIcon(QMessageBox.Icon.NoIcon)
    b.setWindowTitle("Chart restored — the pages need rebuilding")
    b.setText("Chart restored — the pages need rebuilding")
    b.setInformativeText(vcs.regeneration_message(order, number))
    b.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
    fit_message_box_buttons(b)
    b.show()
    pump(0.8)
    shot(b, f"05_restore_{tag}")
    for btn in b.buttons():
        need, have = painted_width(btn), btn.width()
        REPORT.append(("OK " if have >= need else "CLIPPED ")
                      + f"restore/{tag} button {btn.text()!r}: {have} vs {need}")
    b.close()
    pump(0.3)

# ---- the existing-measurement offer (beta.92 trigger) --------------------
stage("checking the Measure tab's offer wiring on screen")
try:
    measure = None
    for i in range(tabs.count()):
        if "Measure" in tabs.tabText(i):
            tabs.setCurrentIndex(i)
            measure = tabs.widget(i)
    pump(0.6)
    if measure is not None:
        REPORT.append(f"Measure tab on screen: visible={measure.isVisible()}, "
                      f"offer queued flag exists="
                      f"{hasattr(measure, '_offer_queued')}")
        shot(win, "06_measure_tab")
        check_buttons(win, "Measure tab (on screen)")
except Exception as exc:                       # noqa: BLE001
    REPORT.append(f"measure-tab check failed: {exc}")

stage("closing")
win.close()
pump(0.4)
(OUT / "report.txt").write_text("\n".join(REPORT) + "\n", encoding="utf-8")
stage("REPORT WRITTEN")
print("\n===== REPORT =====")
for line in REPORT:
    print(line)
QTimer.singleShot(200, app.quit)
app.exec()
stage("event loop exited cleanly")
