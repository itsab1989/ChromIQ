#!/usr/bin/env python3
"""Live verification of the in-app CR30 Bluetooth report (final beta-3 review).

Runs the REAL app on screen and the REAL tool three times: save-accepted,
save-accepted again (accumulation check), and save-cancelled. The owner's CR30
is switched off, so this exercises the no-candidates branch — the one a Windows
user will actually read this week. The scan, worker thread, message boxes and
report are all real; the ONLY things driven are button clicks on the real
boxes (by ROLE, language-independent) and `QFileDialog.getSaveFileName`, which
is replaced because a native save sheet cannot be driven and must never be
left waiting.

Sandboxing as scripts/drive_50_beta3_gate.py: plist backed up and compared,
core.settings.QSettings redirected to a sandbox .ini, CHROMIQ_PRESETS_DIR and
custom_output_path sandboxed, ~/ChromIQ untouched.
"""
from __future__ import annotations
import hashlib, os, shutil, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SANDBOX = Path("/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/"
               "79c89ec2-11d6-4bdc-93a1-f4dcdc3c108d/scratchpad/sandbox52")
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QSettings, QTimer                    # noqa: E402
from PyQt6.QtGui import QFontDatabase                         # noqa: E402
from PyQt6.QtWidgets import (QApplication, QFileDialog,       # noqa: E402
                             QMessageBox)
from core.resource_path import resource_path                  # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
PLIST_BACKUP = SANDBOX / "plist.backup"
OUT = Path.home() / "Desktop" / "cr30-bluetooth-tool-verify"
INI = SANDBOX / "settings.ini"
WORK = SANDBOX / "ChromIQ"
LOG: list = []


def say(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s); print(s, flush=True)


def guard_in():
    if REAL_PLIST.exists():
        shutil.copy2(REAL_PLIST, PLIST_BACKUP)
        return hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()[:16]
    return None


def guard_out(before):
    if before is None:
        return
    now = (hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()[:16]
           if REAL_PLIST.exists() else "GONE")
    if now != before:
        shutil.copy2(PLIST_BACKUP, REAL_PLIST)
        say(f"!! plist CHANGED ({before} -> {now}) -- RESTORED from backup")
    else:
        say(f"plist untouched (sha {now})")


def make_settings():
    import core.settings as CS
    if not INI.exists() and REAL_PLIST.exists():
        src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
        dst = QSettings(str(INI), QSettings.Format.IniFormat)
        for k in src.allKeys():
            dst.setValue(k, src.value(k))
        dst.sync()
    CS.QSettings = lambda *a, **k: QSettings(str(INI), QSettings.Format.IniFormat)
    s = CS.AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(WORK))
    s.set("restore_last_session", False)
    return s


def ini_value(key):
    qs = QSettings(str(INI), QSettings.Format.IniFormat)
    qs.sync()
    return qs.value(key)


class ModalClicker:
    """Clicks the real boxes by ROLE. Records everything it sees."""

    def __init__(self, app):
        self.app = app
        self.seen: list[str] = []
        self.shots = 0
        self.repair_offered = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(250)

    def tick(self):
        w = self.app.activeModalWidget()
        if not isinstance(w, QMessageBox):
            return
        # Mark the WIDGET, not its id(): Python reuses freed addresses, and
        # an id() set silently ignored run 2's fresh intro box in the first
        # attempt — leaving a modal waiting, the exact thing forbidden.
        if w.property("drive52_clicked"):
            return
        roles = {w.buttonRole(b) for b in w.buttons()}
        title, text = w.windowTitle(), w.text()
        OUT.mkdir(parents=True, exist_ok=True)
        self.shots += 1
        w.grab().save(str(OUT / f"dialog_{self.shots:02d}.png"))
        R = QMessageBox.ButtonRole
        if R.DestructiveRole in roles:
            # THE REPAIR OFFER. Must not appear with the instrument off.
            self.repair_offered = True
            self.seen.append(f"REPAIR OFFERED: {title!r} / {text!r}")
            target = next(b for b in w.buttons()
                          if w.buttonRole(b) == R.RejectRole)
        elif R.AcceptRole in roles:
            self.seen.append(f"intro: {title!r} / {text!r}")
            target = next(b for b in w.buttons()
                          if w.buttonRole(b) == R.AcceptRole)
        else:
            self.seen.append(f"info: {title!r} / {text!r} / "
                             f"{w.informativeText()[:180]!r}")
            target = w.buttons()[0]
        w.setProperty("drive52_clicked", True)
        self.seen.append(f"  -> clicked {target.text()!r}")
        QTimer.singleShot(400, target.click)


def main() -> int:
    before = guard_in()
    ticks: list[float] = []
    try:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setApplicationName("ChromIQ")
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
        from ui.styles import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)
        settings = make_settings()
        say(f"sandbox {SANDBOX}")
        say(f"remembered address in sandbox before: {ini_value('cr30_ble_address')!r}")

        from ui.main_window import MainWindow
        win = MainWindow(settings)
        win.resize(1500, 950)
        win.show(); win.raise_(); win.activateWindow()
        end = time.monotonic() + 2.0
        while time.monotonic() < end:
            app.processEvents(); time.sleep(0.005)

        # the Tools popup really offers the entry (screenshot for the record)
        win._open_tools_menu()
        end = time.monotonic() + 0.8
        while time.monotonic() < end:
            app.processEvents(); time.sleep(0.005)
        from ui.tools_popup import ToolsPopup
        pops = [x for x in app.topLevelWidgets() if isinstance(x, ToolsPopup)]
        OUT.mkdir(parents=True, exist_ok=True)
        if pops:
            pops[0].grab().save(str(OUT / "tools_popup.png"))
            say("tools popup screenshotted (entry visible to a real user)")
            pops[0].close()

        clicker = ModalClicker(app)

        # responsiveness probe: a GUI-thread timer; gaps show stalls
        hb = QTimer(); hb.timeout.connect(lambda: ticks.append(time.monotonic()))
        hb.start(100)

        # mid-scan: move the window and switch a tab THROUGH the event queue
        moved = {}
        def poke():
            moved["before_tab"] = win._tabs.currentIndex()
            win.move(win.x() + 60, win.y() + 30)
            win._tabs.setCurrentIndex((win._tabs.currentIndex() + 1)
                                      % win._tabs.count())
            app.processEvents()
            moved["after_tab"] = win._tabs.currentIndex()
            moved["repainted"] = True
            win.grab().save(str(OUT / "mid_scan_window.png"))
            os.system(f"/usr/sbin/screencapture -x '{OUT}/mid_scan_screen.png' "
                      ">/dev/null 2>&1")

        results = {}

        def run_once(tag, save_path):
            if save_path is None:
                QFileDialog.getSaveFileName = staticmethod(
                    lambda *a, **k: ("", ""))
                say(f"[{tag}] save dialog will be CANCELLED")
            else:
                QFileDialog.getSaveFileName = staticmethod(
                    lambda *a, **k: (str(save_path), "Text files (*.txt)"))
                say(f"[{tag}] save dialog will accept -> {save_path}")
            QTimer.singleShot(12000, poke)
            t0 = time.monotonic()
            win._run_cr30_bluetooth_report()
            dt = time.monotonic() - t0
            leftover = [t for t in threading.enumerate()
                        if "cr30-bluetooth-report" in t.name]
            results[tag] = dt
            say(f"[{tag}] completed in {dt:.1f} s; leftover worker threads: "
                f"{len(leftover)}")

        import argparse
        ap = argparse.ArgumentParser(); ap.add_argument("--skip-run1", action="store_true")
        ap.add_argument("--probe-exclude-input", action="store_true")
        args, _ = ap.parse_known_args()
        if args.probe_exclude_input:
            probe_exclude_input(app, win, say, OUT)
            say(f"repair offered: {clicker.repair_offered}")
            say(f"remembered address after: {ini_value('cr30_ble_address')!r}")
            for s in clicker.seen:
                say("  " + s)
            win.close()
            end = time.monotonic() + 1.0
            while time.monotonic() < end:
                app.processEvents(); time.sleep(0.005)
            return 0
        if not args.skip_run1:
            ticks.clear()
            run_once("run1", OUT / "in_app_run1.txt")
            gaps = [b - a for a, b in zip(ticks, ticks[1:])]
            say(f"[run1] GUI heartbeat during run: {len(ticks)} ticks, "
                f"max gap {max(gaps)*1000:.0f} ms" if gaps else "no ticks!")
            say(f"[run1] mid-scan poke: {moved}")

        moved.clear(); ticks.clear()
        run_once("run2", OUT / "in_app_run2.txt")
        gaps = [b - a for a, b in zip(ticks, ticks[1:])]
        say(f"[run2] GUI heartbeat: max gap {max(gaps)*1000:.0f} ms"
            if gaps else "no ticks!")

        moved.clear()
        run_once("run3_cancel", None)
        kept = Path.home() / "Desktop" / "cr30-bluetooth-report.txt"
        say(f"[run3] cancel-path file kept at default: exists={kept.exists()}")
        if kept.exists():
            shutil.move(str(kept), str(OUT / "in_app_run3_cancelled_save.txt"))
            say("[run3] moved into the verify folder")

        say(f"repair offered at any point: {clicker.repair_offered}")
        say(f"remembered address in sandbox after: {ini_value('cr30_ble_address')!r}")
        for s in clicker.seen:
            say("  " + s)

        win.close()
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            app.processEvents(); time.sleep(0.005)
    finally:
        guard_out(before)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "driver_log.txt").write_text("\n".join(LOG))
    return 0




def probe_exclude_input(app, win, say, OUT):
    """Post REAL input events mid-scan; with ExcludeUserInputEvents none may
    be delivered while the scan runs. Direct method calls (the first probe's
    poke) are not user input and prove nothing here — these are queued
    QMouseEvents, the thing the flag exists to hold back."""
    import time
    from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt, QTimer
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtWidgets import QApplication, QFileDialog

    state = {}

    # REAL input, not QApplication.postEvent: ExcludeUserInputEvents filters
    # window-system input, and a Qt-posted synthetic QMouseEvent bypasses the
    # native queue entirely — the first probe "failed" on exactly that. A
    # CGEventPost click goes through the window server and arrives as a real
    # NSEvent, which is what the Cocoa dispatcher defers under the flag.
    import Quartz

    def click_at(widget, pos):
        g = widget.mapToGlobal(pos)
        pt = Quartz.CGPointMake(float(g.x()), float(g.y()))
        for etype in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
            ev = Quartz.CGEventCreateMouseEvent(None, etype, pt,
                                                Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def poke():
        state["tab_before"] = win._tabs.currentIndex()
        bar = win._tabs.tabBar()
        target = (state["tab_before"] + 1) % win._tabs.count()
        click_at(bar, bar.tabRect(target).center())
        tools = win._masthead.tools_button()
        if tools is not None:
            click_at(tools, QPoint(tools.width() // 2, tools.height() // 2))
        state["posted_at"] = time.monotonic()

    def check_mid():
        from ui.tools_popup import ToolsPopup
        state["tab_mid_scan"] = win._tabs.currentIndex()
        state["popup_mid_scan"] = any(isinstance(x, ToolsPopup) and x.isVisible()
                                      for x in app.topLevelWidgets())
        win.grab().save(str(OUT / "probe_mid_scan_window.png"))

    # POSITIVE CONTROL first: the same click, in the normal event loop, must
    # actually switch the tab — otherwise "nothing happened mid-scan" would
    # only prove the harness cannot click (no Accessibility permission, wrong
    # coordinates), not that the flag works.
    win.raise_(); win.activateWindow()
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.005)
    win._tabs.setCurrentIndex(0)
    bar = win._tabs.tabBar()
    click_at(bar, bar.tabRect(1).center())
    end = time.monotonic() + 1.5
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.005)
    state["positive_control_tab"] = win._tabs.currentIndex()
    say(f"[probe] positive control: real click on tab 1 -> current tab "
        f"{state['positive_control_tab']} (must be 1, else the probe is blind)")
    if state["positive_control_tab"] != 1:
        say("[probe] ABORT: the harness cannot deliver real clicks; "
            "nothing below would mean anything")
        return
    win._tabs.setCurrentIndex(0)
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.005)

    QTimer.singleShot(9000, poke)
    QTimer.singleShot(12000, check_mid)
    ticks = []
    hb = QTimer(); hb.timeout.connect(lambda: ticks.append(time.monotonic()))
    hb.start(100)

    QFileDialog.getSaveFileName = staticmethod(
        lambda *a, **k: (str(OUT / "in_app_probe_run.txt"), "t"))
    t0 = time.monotonic()
    win._run_cr30_bluetooth_report()
    dt = time.monotonic() - t0
    hb.stop()
    from ui.tools_popup import ToolsPopup
    end = time.monotonic() + 1.5
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.005)
    state["tab_after_run"] = win._tabs.currentIndex()
    state["popup_after_run"] = any(isinstance(x, ToolsPopup) and x.isVisible()
                                   for x in app.topLevelWidgets())
    gaps = [b - a for a, b in zip(ticks, ticks[1:])]
    say(f"[probe] run took {dt:.1f} s; heartbeat ticks {len(ticks)}, "
        f"max gap {max(gaps)*1000:.0f} ms" if gaps else "[probe] NO TICKS")
    say(f"[probe] mid-scan: tab {state.get('tab_before')} -> "
        f"{state.get('tab_mid_scan')} (must be unchanged); "
        f"tools popup visible: {state.get('popup_mid_scan')} (must be False)")
    say(f"[probe] after run: tab {state.get('tab_after_run')}; "
        f"tools popup visible: {state.get('popup_after_run')} "
        f"(deferred delivery is allowed once the scan is over)")
    for x in app.topLevelWidgets():
        if isinstance(x, ToolsPopup):
            x.close()


if __name__ == "__main__":
    raise SystemExit(main())
