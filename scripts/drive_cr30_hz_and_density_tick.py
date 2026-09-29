#!/usr/bin/env python3
"""Drive the REAL window over both of Basti's 2026-09-08 reports.

    "in preferences under the measurement tab the cr30 is said to have 100Hz.
     I think you measured more like 3Hz and it is patch by patch only anyway"

    "the chart was made for the cr30. but in guided mode it shows colormunki
     with double density selected"

ON SCREEN, because that is where both were seen and where the fixes have to
hold. Offscreen would not show the de_DE decimal comma, would not prove a
widget is really hidden rather than merely un-shown, and would not photograph
anything anybody can check.

PART 1 — Preferences, Measurement, "Per instrument".
  The CR30's rate cell must state no rate at all, and a Save must stop writing
  one. A greyed spin box would not have done: a disabled QDoubleSpinBox still
  answers .value(), so the save loop would keep writing the key. The other six
  rows must be untouched, still editable, still whole numbers (raising decimals
  to express a sub-10 figure prints "100,00 Hz" on a German machine).

PART 2 — Create Chart, Guided, the one density checkbox.
  It is three options sharing a widget: "Double density" on a ColorMunki (which
  needs the physical rig), "Hexagon patches" on a CR30 and a SpectroScan, hidden
  on an i1Pro. A tick used to carry between those meanings, so hexagons chosen
  for a CR30 arrived on a ColorMunki as rig double density; and a deliberate
  ColorMunki tick was lost by glancing at an i1Pro. Each instrument now keeps
  its own answer.

Preferences are copied to a throwaway .ini and the ChromIQ root is a sandbox,
so nothing of the user's is touched. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cr30.ini \
        python scripts/drive_cr30_hz_and_density_tick.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QLocale, QSettings, Qt                 # noqa: E402
from PyQt6.QtTest import QTest                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QGroupBox,  # noqa: E402
                             QLabel, QListWidget, QMessageBox,
                             QScrollArea, QTabWidget)

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "cr30-hz-and-density"
RATE_ROWS = ("i1pro", "i1pro2", "i1pro3", "i1pro3plus", "colormunki",
             "spectroscan")


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    w.grab().save(str(SHOTS / f"{name}.png"))
    print(f"        saved {name}.png")


def _sandbox_settings():
    from core.settings import AppSettings
    sb = Path(tempfile.mkdtemp(prefix="chromiq-cr30-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sb / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    s = AppSettings()
    s._qs = dst
    work = sb / "ChromIQ"
    work.mkdir()
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)
    return s, sb


def part1(app) -> int:
    print("\n  PART 1 - Preferences, Measurement, Per instrument")
    s, sb = _sandbox_settings()
    # what an older build left behind, and what this must stop rewriting
    s.set("pace_sample_hz_cr30", 100.0)

    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(s, None)
    dlg._settings = s
    dlg.show()
    pump(app, 1800)
    for tw in dlg.findChildren(QTabWidget):
        for i in range(tw.count()):
            if "eas" in tw.tabText(i) or "Mess" in tw.tabText(i):
                tw.setCurrentIndex(i)
    for lw in dlg.findChildren(QListWidget):
        for i in range(lw.count()):
            if "eas" in lw.item(i).text() or "Mess" in lw.item(i).text():
                lw.setCurrentRow(i)
    pump(app, 1200)

    bad = 0
    print("        the table, read off the live widgets:")
    for key in RATE_ROWS + ("cr30",):
        box = dlg._pace_hz.get(key)
        if box is None:
            print(f"          {key:12} <no rate box>")
        else:
            print(f"          {key:12} {box.text()!r:<12} "
                  f"decimals={box.decimals()} min={box.minimum()}")
    if "cr30" in dlg._pace_hz:
        print("        >>> the CR30 has a rate box again"); bad += 1
    for key in RATE_ROWS:
        b = dlg._pace_hz.get(key)
        if b is None or not b.isEnabled() or b.decimals() != 0:
            print(f"        >>> {key} was changed as collateral"); bad += 1

    na = next((w for w in dlg.findChildren(QLabel) if w.text() in ("N/A", "—")),
              None)
    if na is None:
        print("        >>> no N/A cell found"); bad += 1
    else:
        for sa in dlg.findChildren(QScrollArea):
            try:
                sa.ensureWidgetVisible(na, 50, 220)
            except Exception:      # noqa: BLE001
                pass
        pump(app, 800)
        shot(dlg, "01-measurement-tab")
        grp = na.parent()
        while grp is not None and not isinstance(grp, QGroupBox):
            grp = grp.parent()
        if grp is not None:
            shot(grp, "02-per-instrument-table")

    s.set("pace_sample_hz_i1pro", 7.0)      # canary: proves the save ran
    s.set("pace_sample_hz_cr30", 3.18)      # below the box range: unholdable
    dlg._save_and_close()
    pump(app, 600)
    ran = s.get("pace_sample_hz_i1pro", None) != 7.0
    kept = abs(float(s.get("pace_sample_hz_cr30", 0)) - 3.18) < 1e-6
    print(f"        Save ran (canary overwritten): {ran}")
    print(f"        CR30 rate left alone by Save : {kept}")
    if not ran:
        print("        >>> the save never ran, so the line above proves nothing")
        bad += 1
    if not kept:
        print("        >>> the CR30 rate went through a spin box and was clamped")
        bad += 1
    return bad


def part2(app) -> int:
    print("\n  PART 2 - Create Chart, Guided, the density checkbox")
    s, sb = _sandbox_settings()
    QDialog.exec = lambda self: 1              # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("guided")
    pump(app, 1200)

    seen_activated: list[int] = []
    tab._instr_combo.activated.connect(seen_activated.append)

    def pick(code):
        """Choose an instrument THROUGH THE OPEN POPUP, with the keyboard.

        Not `setCurrentIndex`: that is what the APP does to itself, and the
        density memory deliberately does not restore on it. A person picking a
        row makes Qt emit `activated`, and this drives the real popup so that
        distinction is exercised rather than assumed.
        """
        i = tab._instr_combo.findData(code)
        before = len(seen_activated)
        combo = tab._instr_combo
        combo.showPopup()
        pump(app, 350)
        view = combo.view()
        view.setCurrentIndex(combo.model().index(i, 0))
        pump(app, 150)
        QTest.keyClick(view, Qt.Key.Key_Return)
        pump(app, 700)
        if combo.currentData() != code or len(seen_activated) == before:
            # Some styles close the popup without a key event; fall back to the
            # two signals a real selection emits, and say so.
            combo.hidePopup()
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            pump(app, 500)
            print(f"          (popup keyboard pick did not take for {code}; "
                  "used the signals a real selection emits)")

    def line(tag):
        print(f"          {tag:<28} instr={tab._instr_combo.currentData()!r:<7} "
              f"hidden={tab._dd_check.isHidden()!s:<5} "
              f"ticked={tab._dd_check.isChecked()!s:<5} "
              f"label={tab._dd_check.text()!r}")

    bad = 0
    print("        one widget, three options:")
    for code in ("CM", "CR30", "SS", "i1"):
        pick(code)
        line(f"picked {code}")

    print("        hexagons chosen for a CR30 must not arrive as rig density:")
    pick("CR30")
    tab._dd_check.setChecked(True)
    line("CR30, hexagons ON")
    shot(win, "03-cr30-hexagons-on")
    pick("CM")
    line("switched to ColorMunki")
    shot(win, "04-colormunki-clean")
    if tab._dd_check.isChecked():
        print("        >>> the tick carried into Double density"); bad += 1
    if tab._shared_get("guided")["double_density"]:
        print("        >>> and the run would be BUILT that way"); bad += 1

    print("        a deliberate ColorMunki tick must survive a glance away:")
    pick("CM")
    tab._dd_check.setChecked(True)
    line("CM, double density ON")
    pick("i1")
    line("glanced at i1Pro")
    pick("CM")
    line("back on ColorMunki")
    shot(win, "05-colormunki-tick-restored")
    if not tab._dd_check.isChecked():
        print("        >>> the deliberate tick was lost (spec 4c, D-2)"); bad += 1

    print("        and the CR30 still remembers its own answer:")
    pick("CR30")
    line("back on CR30")
    if not tab._dd_check.isChecked():
        print("        >>> the CR30 lost its hexagons"); bad += 1

    print(f"        activated fired {len(seen_activated)} times "
          "(a real selection, never an app-driven setCurrentIndex)")
    if not seen_activated:
        print("        >>> no user pick was ever registered"); bad += 1
    win.close()
    pump(app, 400)
    return bad


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    print(f"  locale {QLocale.system().name()}, decimal point "
          f"{QLocale.system().decimalPoint()!r}")
    bad = part1(app) + part2(app)
    print(f"\n  problems: {bad}")
    print(f"  screenshots in {SHOTS}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
