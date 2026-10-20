#!/usr/bin/env python3
"""#205 on screen, Windows: both print routes of the real app, photographed.

The real main window (as ``scripts/capture_screens.build_app`` builds it, with
the shipped style and filters), settings sandboxed (``CHROMIQ_SETTINGS_FILE``),
real Preferences, the real Print Chart tab, the real Windows print dialog
(``PrintDlgEx``, driven from a watcher thread: it photographs the dialog,
reads which printer is selected, and presses Print only when that printer is
a ``ChromIQ-Test`` file-port queue, else Cancel). Every window is photographed
by its own handle (``onscreen_capture_win.capture_hwnd``), behind other
windows, without raising anything.

Scenes (``RESULT.json`` lists what each one saw):

 1. The Print Chart tab as a fresh install opens it: the dialog route (the
    default), its notice and help.
 2. Preferences: "Use default Windows printer dialog" (ticked), its help, and
    "Confirm print settings before printing" greyed; untick it; OK.
 3. ChromIQ's own route, a PostScript printer (the Xerox Phaser 6360DN v3
    queue): its PPD's rows; A4, a media type, a tray; Print; the confirmation
    window; the status line; the job at the port byte for byte equal to what
    ``WindowsRawPrinter`` builds for the same choice.
 4. A printer that is not PostScript (the Epson v3 driver on a file port):
    the box; Print with an RGB chart opens the Windows dialog on THAT printer;
    Print there; the job reaches its file port.
 5. The same printer, a CMYK chart: M-PRINT-WIN-INKS-NOT-POSTSCRIPT.
 6. A spooler refusal: the queue paused... is not a refusal, so a queue that is
    deleted between listing and printing: M-PRINT-WIN-SPOOLER-FAILED.
 7. Preferences back to the dialog; the tab follows.
 8. The dialog route: a CMYK chart, refused before the dialog
    (M-PRINT-WIN-DIALOG-NOT-RGB).
 9. The dialog route: an A3 chart on the dialog's A4: M-PRINT-WIN-DIALOG-TOO-BIG.
10. The dialog route: an A4 chart on the XPS test queue, printed; the spooled
    XPS measured (size, placement, colour values).

usage: drive_205_windows_print.py --out REPORT_DIR [--lang en] [--texts-only]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--lang", default="en")
ap.add_argument("--texts-only", action="store_true",
                help="only the scenes that show new texts (for the other languages)")
ARGS = ap.parse_args()

TREE = Path(__file__).resolve().parent.parent
OUT = Path(ARGS.out).resolve()
SHOTS = OUT / f"shots-{ARGS.lang}"
SANDBOX = OUT / f"sandbox-{ARGS.lang}"
CHARTS_SRC = OUT.parent / "00_test_charts"
ARGYLL = r"C:\Users\sebas\Argyll\Argyll_V3.5.0\bin"
PS_QUEUE = "ChromIQ-Test Xerox Phaser 6360DN PPD v3"
NON_PS_QUEUE = "ChromIQ-Test Epson File"
XPS_QUEUE = "ChromIQ-Test XPS Class"
REAL_EPSON = "EPSON ET-8550 Series"

for d in (SANDBOX, SHOTS):
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)            # ON SCREEN, never offscreen
sys.path.insert(0, str(TREE / "scripts"))
sys.path.insert(0, str(TREE))

from core.freetype_bootstrap import ensure_freetype_library  # noqa: E402
ensure_freetype_library()

import capture_screens as cs                                  # noqa: E402
import onscreen_capture_win as ocw                            # noqa: E402
from PyQt6.QtCore import QTimer                               # noqa: E402
from PyQt6.QtTest import QTest                                # noqa: E402
from PyQt6.QtCore import Qt                                   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox,  # noqa: E402
                             QDialog, QLabel, QMessageBox, QPushButton)

RESULT: dict = {"mode": "ON SCREEN (real windows on the Windows desktop)",
                "lang": ARGS.lang, "tree": str(TREE), "scenes": [], "findings": []}
RESULT["head"] = subprocess.run(["git", "-C", str(TREE), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=30).stdout.strip()
RESULT["dirty"] = bool(subprocess.run(["git", "-C", str(TREE), "status", "--porcelain",
                                       "--untracked-files=no"],
                                      capture_output=True, text=True, timeout=30).stdout.strip())


def log(msg: str) -> None:
    print(msg, flush=True)
    with open(OUT / f"drive-{ARGS.lang}.log", "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def pump(ms: int) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.02)


def shot(widget_or_hwnd, name: str) -> str:
    path = SHOTS / f"{name}.png"
    if isinstance(widget_or_hwnd, int):
        how = ocw.capture_hwnd(widget_or_hwnd, path)
    else:
        QApplication.processEvents()
        how = ocw.capture_widget(widget_or_hwnd, path)
    log(f"  shot {name}: {how or 'NOTHING'}")
    if not how:
        RESULT["findings"].append(f"no picture for {name}")
    return path.name if how else ""


def scene(title: str) -> dict:
    s = {"scene": title, "shots": [], "facts": {}}
    RESULT["scenes"].append(s)
    log(f"== {title}")
    return s


def when_modal(fn, *, timeout_ms: int = 20000, not_this=None) -> None:
    """Run fn(modal) as soon as a new modal Qt window is up (while the code
    that opened it blocks in exec)."""
    start = time.monotonic()

    def tick():
        m = QApplication.activeModalWidget()
        if m is None:
            for w in QApplication.topLevelWidgets():
                if isinstance(w, QMessageBox) and w.isVisible():
                    m = w
                    break
        if m is not None and type(m).__name__ == "QPrintDialog":
            m = None                       # the native dialog: the watcher's
        if m is not None and (m is not_this or id(m) in _CLAIMED):
            m = None
        if m is not None and m.isVisible():
            _CLAIMED[id(m)] = m
            QTimer.singleShot(700, lambda: _run(m))
            return
        if (time.monotonic() - start) * 1000 > timeout_ms:
            RESULT["findings"].append("an expected window never opened")
            log("  !! an expected window never opened")
            return
        QTimer.singleShot(150, tick)

    def _run(m):
        try:
            fn(m)
        except Exception:  # noqa: BLE001
            RESULT["findings"].append(traceback.format_exc())
            log(traceback.format_exc())
            m.close()
    QTimer.singleShot(150, tick)


def box_text(m) -> dict:
    out = {"title": m.windowTitle()}
    if isinstance(m, QMessageBox):
        out["text"] = m.text()
        out["informative"] = m.informativeText()
        out["buttons"] = [b.text() for b in m.buttons()]
    return out


# --- the native Windows print dialog, from a watcher thread -------------------
UIA = str(TREE / "scripts" / "uia_print_dialog.ps1")


def uia(*args) -> str:
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", UIA, *args],
                       capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
    return r.stdout.strip()


class DialogWatcher(threading.Thread):
    """Waits for the Windows print dialog this app opens: the classic one
    (PrintDlgEx, in this process) or Windows 11's own (WinUI, its own window,
    read by UI Automation, ``scripts/uia_print_dialog.ps1``). Photographs it,
    records the printer it shows, chooses *choose* in it when given (as a
    user would), and presses Print only when the printer it finally shows is
    a ChromIQ-Test queue; otherwise Cancel."""

    def __init__(self, name: str, choose: "str | None" = None, press_print: bool = True):
        super().__init__(daemon=True)
        self.name, self.choose, self.press_print = name, choose, press_print
        self.seen: dict = {}

    def run(self):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            for hwnd, title in ocw.own_dialogs():
                if any(c[1] == "SysListView32" for c in ocw.children(hwnd)):
                    self._classic(hwnd, title)
                    return
            r = uia("-Action", "read", "-WaitSeconds", "1")
            if '"open":true' in r.replace(" ", ""):
                import json as _j
                self._modern(_j.loads(r))
                return
        self.seen = {"error": "no print dialog within 60 s"}

    def _classic(self, hwnd, title):
        time.sleep(1.5)
        sel = ocw.list_view_selection(hwnd)
        path = SHOTS / f"{self.name}.png"
        how = ocw.capture_hwnd(hwnd, path)
        printer = sel[0] if sel else ""
        self.seen = {"kind": "classic PrintDlgEx", "title": title, "printer_shown": printer,
                     "photo": path.name if how else ""}
        ok = self.press_print and printer.startswith("ChromIQ-Test") \
            and (self.choose is None or printer == self.choose)
        self.seen["pressed"] = "Print" if ok else "Cancel"
        ocw.press(hwnd, ocw.IDOK if ok else ocw.IDCANCEL)

    def _modern(self, info):
        import json as _j
        time.sleep(1.5)
        hwnd = int(info.get("hwnd") or 0)
        path = SHOTS / f"{self.name}.png"
        how = ocw.capture_hwnd(hwnd, path) if hwnd else ""
        self.seen = {"kind": "Windows 11 print dialog (WinUI)", "title": info.get("title"),
                     "printer_shown": info.get("printer"), "settings": info.get("settings"),
                     "app_may_change_settings": info.get("app_may_change_settings"),
                     "photo": path.name if how else ""}
        printer = info.get("printer") or ""
        if self.choose and printer != self.choose:
            self.seen["chose"] = uia("-Action", "select", "-Printer", self.choose)
            time.sleep(2.5)
            again = _j.loads(uia("-Action", "read", "-WaitSeconds", "3") or "{}")
            printer = again.get("printer") or ""
            self.seen["printer_after_choosing"] = printer
            path2 = SHOTS / f"{self.name}_after_choosing.png"
            if hwnd and ocw.capture_hwnd(hwnd, path2):
                self.seen["photo_after_choosing"] = path2.name
        ok = self.press_print and printer.startswith("ChromIQ-Test") and printer != REAL_EPSON
        self.seen["pressed"] = "Print" if ok else "Cancel"
        uia("-Action", "print" if ok else "cancel")


def set_default_printer(name: str) -> None:
    import ctypes
    ctypes.WinDLL("winspool.drv").SetDefaultPrinterW(name)


def port_of(queue: str) -> Path:
    from workflow import win_spooler
    api = win_spooler._api()
    with win_spooler._Printer(queue) as h:
        buf = win_spooler._two_call(api.ws.GetPrinterW, h, 2)
    return Path(api.PRINTER_INFO_2.from_buffer(buf).pPortName)


def wait_port(port: Path, before: float, timeout: float = 60) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pump(300)
        if port.exists() and port.stat().st_mtime > before and port.stat().st_size > 0:
            pump(800)
            return True
    return False


#: one project per chart, its run1 holding the chart as ChromIQ files it (the
#: project's stem), so the bar points at a run that HAS a chart: a chart
#: loaded while the bar says "New run" is refused by the app, rightly (the
#: first run of this driver did that and photographed the refusal)
PROJECTS = {"rgb": "WinPrint-RGB", "cmyk": "WinPrint-CMYK", "rgb_a3": "WinPrint-A3"}


def stage_projects(root: Path) -> dict:
    from core.file_manager import Project
    out = {}
    for chart, name in PROJECTS.items():
        proj = Project.create(root / name, name)
        run = proj.current_run()
        run.ensure_dir()
        ti2 = Path(run.chart_ti2)
        for ext in (".ti1", ".ti2", ".tif"):
            src = CHARTS_SRC / f"{chart}{ext}"
            if src.exists():
                shutil.copy2(src, ti2.with_suffix(ext))
        out[chart] = (name, run.id, ti2)
    return out


_CLAIMED: dict = {}          # id -> the window, kept so the id is never reused


def watchdog_tick() -> None:
    """Every modal Qt window that no scene handler claimed within 6 s is a
    FINDING: photographed, recorded, closed. The driver never hangs on one,
    and never passes one silently."""
    now = time.monotonic()
    cands = []
    m = QApplication.activeModalWidget()
    if m is not None:
        cands.append(m)
    cands += [w for w in QApplication.topLevelWidgets()
              if isinstance(w, QMessageBox) and w.isVisible()]
    for w in cands:
        if type(w).__name__ == "QPrintDialog" or id(w) in _CLAIMED or not w.isVisible():
            continue
        first = _SEEN.setdefault(id(w), (w, now))[1]
        if now - first < 6:
            continue
        n = len([f for f in RESULT["findings"] if f.startswith("UNEXPECTED")]) + 1
        info = box_text(w)
        RESULT["findings"].append(f"UNEXPECTED window {n}: {json.dumps(info, ensure_ascii=False)}")
        shot(w, f"zz_unexpected_{n}")
        _CLAIMED[id(w)] = w
        w.reject() if isinstance(w, QDialog) else w.close()


_SEEN: dict = {}


# ------------------------------------------------------------------------------
def main() -> int:
    from workflow import win_spooler
    default_before = win_spooler.default_printer()
    RESULT["default_printer_before"] = default_before
    app = cs.build_app()
    from core.settings import AppSettings
    settings = AppSettings()
    assert str(settings._qs.fileName()).lower().startswith(str(SANDBOX).lower().replace("\\", "/")) \
        or "sandbox" in settings._qs.fileName(), f"SANDBOX FAILED: {settings._qs.fileName()}"
    projects = SANDBOX / "projects"
    projects.mkdir()
    settings.set("custom_output_path", str(projects))
    settings.set("argyll_bin_path", ARGYLL)
    settings.set("language", ARGS.lang)
    settings.set("update_notify", False)
    settings.set("restore_last_session", False)
    settings.set("confirm_before_printing", True)
    from core.i18n import set_language
    set_language(ARGS.lang)
    RESULT["settings_file"] = settings._qs.fileName()
    RESULT["dialog_route_is_the_default"] = bool(settings.get("use_native_print_dialog", None))

    charts = stage_projects(projects)
    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(2500)
    focus = getattr(app, "_chromiq_focus_give_back", None)
    if focus is not None:
        try:
            focus.give_back()
        except Exception:  # noqa: BLE001
            pass
    RESULT["window_on_screen"] = bool(win.isVisible())
    dog = QTimer()
    dog.setInterval(500)
    dog.timeout.connect(watchdog_tick)
    dog.start()
    tab = win._tab_print
    tabs = win._tabs
    tabs.setCurrentWidget(tab)
    pump(1500)

    def load(name: str):
        """Select the chart's project and its run1 on the bar, as a user does."""
        pname, rid, ti2 = charts[name]
        fm = win._file_mgr
        fm.set_target_name(pname)
        pump(900)
        ctl = tab._target_ctl
        ctl.set_profile_run(rid)
        pump(1500)
        if tab._current_ti2 != ti2:
            tab._current_ti2 = None
            tab.apply_loaded_ti2(ti2)
            pump(1200)
        log(f"  target: {pname} / {ctl.target.profile_run}, chart {tab._current_ti2}")

    # 1 -------------------------------------------------------------------
    s = scene("1. Print Chart tab on a fresh install: the Windows dialog route")
    load("rgb")
    s["facts"]["use_native_print_dialog"] = settings.get("use_native_print_dialog")
    s["facts"]["notice"] = tab._warn_lbl.text()
    s["facts"]["help"] = tab._compute_print_tooltip()[1]
    s["facts"]["printer_rows_visible"] = tab._printer_grp.isVisible()
    s["shots"].append(shot(win, "01_print_tab_dialog_route"))

    # 2 -------------------------------------------------------------------
    s = scene("2. Preferences: the switch, its help, and switching to ChromIQ's own route")

    def in_prefs(dlg):
        chk = dlg._native_print_check
        s["facts"]["checkbox"] = chk.text()
        s["facts"]["ticked"] = chk.isChecked()
        s["facts"]["confirm_enabled_while_ticked"] = dlg._confirm_print_check.isEnabled()
        # bring the row into view inside the dialog (its own scroll area)
        from PyQt6.QtWidgets import QScrollArea
        p = chk.parent()
        while p is not None and not isinstance(p, QScrollArea):
            p = p.parent()
        if p is not None:
            p.ensureWidgetVisible(chk, 50, 200)
        # its Behaviour tab
        from PyQt6.QtWidgets import QTabWidget
        t = chk.parent()
        while t is not None and not isinstance(t, QTabWidget):
            t = t.parent()
        pump(600)
        s["shots"].append(shot(dlg, "02a_preferences_switch_ticked"))
        # the help of the switch
        from ui.tooltip_button import TooltipButton
        tips = [b for b in dlg.findChildren(TooltipButton)
                if getattr(b, "_title", None) == chk.text()]
        s["facts"]["help_button_found"] = bool(tips)
        if tips:
            def in_help(info):
                s["facts"]["help_window_title"] = info.windowTitle()
                s["shots"].append(shot(info, "02b_preferences_switch_help"))
                info.accept()
            when_modal(in_help, not_this=dlg)
            QTest.mouseClick(tips[0], Qt.MouseButton.LeftButton)
            pump(600)
        chk.setChecked(False)
        pump(500)
        s["facts"]["confirm_enabled_after_untick"] = dlg._confirm_print_check.isEnabled()
        s["shots"].append(shot(dlg, "02c_preferences_switch_unticked"))
        ok = next((b for b in dlg.findChildren(QPushButton)
                   if b.text().replace("&", "") in ("OK", "Ok")), None)
        if ok is not None:
            QTest.mouseClick(ok, Qt.MouseButton.LeftButton)
        else:
            dlg._save_and_close()

    when_modal(in_prefs)
    win._open_settings()
    pump(1500)
    s["facts"]["after_ok_use_native_print_dialog"] = settings.get("use_native_print_dialog")

    if ARGS.texts_only:
        _texts_only(win, tab, settings, charts, load)
        return _finish(app, default_before)

    # 3 -------------------------------------------------------------------
    s = scene("3. ChromIQ's own route, a PostScript printer")
    cb = tab._printer_combo
    tab.reload_printers() if hasattr(tab, "reload_printers") else None
    pump(1500)
    idx = cb.findData(PS_QUEUE)
    s["facts"]["listed_printers"] = [cb.itemData(i) for i in range(cb.count())][:80]
    cb.setCurrentIndex(idx)
    pump(2000)
    rows = {k: [c.itemText(i) for i in range(c.count())] for k, c in tab._option_combos.items()}
    s["facts"]["option_rows"] = {k: v[:8] for k, v in rows.items()}
    wanted = {"PageSize": "A4", "MediaType": None, "InputSlot": None}
    for key, _vals, c in list(tab._ordered_opts):
        if key not in wanted:
            continue
        i = c.findData(wanted[key]) if wanted[key] else (2 if c.count() > 2 else c.count() - 1)
        if i >= 0:
            c.setCurrentIndex(i)
            pump(500)
    chosen = {k: (c.currentData() or "") for k, c in tab._option_combos.items()}
    s["facts"]["chosen"] = chosen
    s["facts"]["notice"] = tab._warn_lbl.text()
    s["facts"]["help"] = tab._compute_print_tooltip()[1]
    s["shots"].append(shot(win, "03a_direct_route_postscript_printer"))
    port = port_of(PS_QUEUE)
    before = port.stat().st_mtime if port.exists() else 0
    confirm = {}

    def in_confirm(dlg):
        if type(dlg).__name__ != "PreflightDialog":
            RESULT["findings"].append(f"scene 3 expected the confirmation window, got {box_text(dlg)}")
            shot(dlg, "03b_NOT_the_confirmation")
            dlg.close()
            return
        confirm.update(box_text(dlg))
        lbls = [l.text() for l in dlg.findChildren(QLabel) if l.text()]
        confirm["labels"] = lbls[:40]
        s["shots"].append(shot(dlg, "03b_direct_route_confirmation"))
        dlg.accept()

    when_modal(in_confirm)
    tab._on_print_current()
    pump(1500)
    s["facts"]["confirmation"] = confirm
    s["facts"]["status"] = tab._status_lbl.text() if hasattr(tab, "_status_lbl") else ""
    arrived = wait_port(port, before)
    s["facts"]["job_at_port"] = arrived
    if arrived:
        from workflow.win_raw_printer import WindowsRawPrinter
        from workflow.cups_printer import PrintConfig
        opts, page = tab._compute_geometry(PS_QUEUE, chosen, tab._tiff_pages[0])[1], None
        cfg = tab._module.build_config(printer=PS_QUEUE, options=chosen)
        _o, page_pt, _m = tab._compute_geometry(PS_QUEUE, chosen, tab._tiff_pages[0])
        want = WindowsRawPrinter.job_bytes(tab._tiff_pages[0], cfg, page_size_pt=page_pt)
        got = port.read_bytes()
        s["facts"]["byte_identical_to_what_chromiq_builds"] = got == want
        s["facts"]["features_in_job"] = [ln for ln in got.decode("latin-1").splitlines()
                                         if ln.startswith("%%BeginFeature")]
        shutil.copy2(port, SHOTS / "03_port_file.prn")
    s["shots"].append(shot(win, "03c_direct_route_after_print"))

    # 4 -------------------------------------------------------------------
    s = scene("4. ChromIQ's own route, a printer that is not PostScript: an RGB chart")
    cb.setCurrentIndex(cb.findData(NON_PS_QUEUE))
    pump(1800)
    boxes = [l.text() for l in tab.findChildren(QLabel)
             if l.objectName() in ("airprintInfoTitle", "airprintInfoBody") and l.isVisible()]
    s["facts"]["box"] = boxes
    s["shots"].append(shot(win, "04a_direct_route_not_postscript_box"))
    port = port_of(NON_PS_QUEUE)
    before = port.stat().st_mtime if port.exists() else 0
    other = {}

    def in_other(m):
        other.update(box_text(m))
        s["shots"].append(shot(m, "04c_the_dialog_chose_another_printer"))
        btn = next((b for b in m.buttons() if m.buttonRole(b) == QMessageBox.ButtonRole.RejectRole), None)
        (btn.click() if btn is not None else m.reject())

    when_modal(in_other, timeout_ms=90000)
    watcher = DialogWatcher("04b_windows_dialog_on_its_own_printer", choose=None)
    watcher.start()
    tab._on_print_current()
    watcher.join(70)
    pump(1500)
    s["facts"]["dialog_first"] = watcher.seen
    s["facts"]["question_when_the_dialog_kept_its_own_printer"] = other
    watcher = DialogWatcher("04d_windows_dialog_printer_chosen", choose=NON_PS_QUEUE)
    watcher.start()
    tab._on_print_current()
    watcher.join(70)
    s["facts"]["dialog_second"] = watcher.seen
    s["facts"]["job_at_port"] = wait_port(port, before, 90)
    s["facts"]["port_bytes"] = port.stat().st_size if port.exists() else 0
    s["shots"].append(shot(win, "04c_after_the_dialog"))

    # 5 -------------------------------------------------------------------
    s = scene("5. The same printer, a CMYK chart: refused")
    load("cmyk")
    refusal = {}

    def in_refusal(m):
        refusal.update(box_text(m))
        s["shots"].append(shot(m, "05_refused_cmyk_on_a_printer_that_is_not_postscript"))
        m.accept() if isinstance(m, QDialog) else m.close()

    when_modal(in_refusal)
    tab._on_print_current()
    pump(1200)
    s["facts"]["window"] = refusal

    # 6 -------------------------------------------------------------------
    s = scene("6. The spooler refuses the job")
    load("rgb")
    cb.setCurrentIndex(cb.findData(PS_QUEUE))
    pump(1500)
    gone = "ChromIQ-Test gone"
    cb.addItem(gone, gone)              # a queue the spooler no longer has
    cb.setCurrentIndex(cb.findData(gone))
    pump(800)
    tab._windows_queue_takes_postscript = lambda p: True      # as it was when listed
    fail = {}

    def in_confirm2(dlg):
        s["shots"].append(shot(win, "06a_main_window_while_the_confirmation_is_open"))
        if isinstance(dlg, QMessageBox):
            fail.update(box_text(dlg))
            s["shots"].append(shot(dlg, "06_spooler_refused"))
            dlg.accept()
            return
        dlg.accept()
        when_modal(in_fail)

    def in_fail(m):
        fail.update(box_text(m))
        s["shots"].append(shot(m, "06_spooler_refused"))
        m.accept()

    tab._printer.is_printer_reachable = lambda name: True
    when_modal(in_confirm2)
    tab._on_print_current()
    pump(2500)
    del tab._windows_queue_takes_postscript
    del tab._printer.is_printer_reachable
    s["facts"]["window"] = fail
    cb.removeItem(cb.findData(gone))

    # 7 -------------------------------------------------------------------
    s = scene("7. Preferences: back to the Windows dialog")

    def back(dlg):
        dlg._native_print_check.setChecked(True)
        pump(400)
        ok = next((b for b in dlg.findChildren(QPushButton)
                   if b.text().replace("&", "") in ("OK", "Ok")), None)
        QTest.mouseClick(ok, Qt.MouseButton.LeftButton) if ok else dlg._save_and_close()

    when_modal(back)
    win._open_settings()
    pump(1500)
    s["facts"]["use_native_print_dialog"] = settings.get("use_native_print_dialog")
    s["facts"]["notice"] = tab._warn_lbl.text()
    s["shots"].append(shot(win, "07_print_tab_back_on_the_dialog_route"))

    # 8 -------------------------------------------------------------------
    s = scene("8. The dialog route: a CMYK chart is refused before the dialog")
    load("cmyk")
    refusal = {}
    when_modal(lambda m: (refusal.update(box_text(m)),
                          s["shots"].append(shot(m, "08_dialog_route_refuses_cmyk")),
                          m.close()))
    tab._on_print_current()
    pump(1200)
    s["facts"]["window"] = refusal
    s["facts"]["a_print_dialog_opened"] = bool(
        [h for h, _t in ocw.own_dialogs() if any(c[1] == "SysListView32" for c in ocw.children(h))])

    # 9 -------------------------------------------------------------------
    s = scene("9. The dialog route: an A3 chart on the dialog's A4 paper")
    set_default_printer(XPS_QUEUE)
    load("rgb_a3")
    big = {}
    when_modal(lambda m: (big.update(box_text(m)),
                          s["shots"].append(shot(m, "09b_dialog_route_chart_larger_than_paper")),
                          m.close()), timeout_ms=60000)
    watcher = DialogWatcher("09a_windows_print_dialog", choose=XPS_QUEUE)
    watcher.start()
    tab._on_print_current()
    watcher.join(45)
    pump(1500)
    s["facts"]["dialog"] = watcher.seen
    s["facts"]["window"] = big

    # 10 ------------------------------------------------------------------
    s = scene("10. The dialog route: an A4 chart at 100 % on the XPS test queue")
    load("rgb")
    port = port_of(XPS_QUEUE)
    before = port.stat().st_mtime if port.exists() else 0
    watcher = DialogWatcher("10a_windows_print_dialog_rgb", choose=XPS_QUEUE)
    watcher.start()
    tab._on_print_current()
    watcher.join(45)
    s["facts"]["dialog"] = watcher.seen
    s["facts"]["job_at_port"] = wait_port(port, before, 90)
    if s["facts"]["job_at_port"]:
        shutil.copy2(port, SHOTS / "10_spooled.oxps")
        s["facts"]["measured"] = _measure_xps(SHOTS / "10_spooled.oxps", tab._tiff_pages[0])
    s["shots"].append(shot(win, "10b_after_printing"))
    return _finish(app, default_before)


def _texts_only(win, tab, settings, charts, load):
    """The new texts in this language: notices, the box, the refusals."""
    s = scene("T. the new texts")
    cb = tab._printer_combo
    load("rgb")
    cb.setCurrentIndex(cb.findData(PS_QUEUE))
    pump(1500)
    s["shots"].append(shot(win, "T1_direct_route_postscript"))
    cb.setCurrentIndex(cb.findData(NON_PS_QUEUE))
    pump(1500)
    s["shots"].append(shot(win, "T2_direct_route_not_postscript_box"))
    load("cmyk")
    when_modal(lambda m: (s["shots"].append(shot(m, "T3_refused_cmyk_not_postscript")), m.close()))
    tab._on_print_current()
    pump(1200)

    def back(dlg):
        dlg._native_print_check.setChecked(True)
        pump(300)
        s["shots"].append(shot(dlg, "T4_preferences"))
        dlg._save_and_close()
    when_modal(back)
    win._open_settings()
    pump(1200)
    s["shots"].append(shot(win, "T5_dialog_route_notice"))
    when_modal(lambda m: (s["shots"].append(shot(m, "T6_dialog_route_refuses_cmyk")), m.close()))
    tab._on_print_current()
    pump(1200)
    from workflow import measurement_messages as MM
    from ui.tabs.tab_print import TabPrint
    for msg, kw, name in ((MM.M_PRINT_WIN_DIALOG_TOO_BIG, {"chart": "285 × 408 mm", "paper": "210 × 297 mm"}, "T7_too_big"),
                          (MM.M_PRINT_WIN_SPOOLER_FAILED, {"printer": "ChromIQ-Test", "reason": "(Windows)"}, "T8_spooler")):
        when_modal(lambda m, n=name: (s["shots"].append(shot(m, n)), m.close()))
        TabPrint._show_print_refusal(tab, *msg.render(**kw))
        pump(800)


def _measure_xps(xps: Path, chart: Path) -> dict:
    import io
    import re
    import zipfile
    from workflow.page_geometry import read_tiff_dimensions_points
    z = zipfile.ZipFile(io.BytesIO(xps.read_bytes()))
    parts: dict = {}
    for n in z.namelist():
        pm = re.match(r"(.+)/\[(\d+)\](?:\.last)?\.piece$", n)
        if pm:
            parts.setdefault(pm.group(1), []).append((int(pm.group(2)), n))
        else:
            parts.setdefault(n, []).append((0, n))
    blobs = {k: b"".join(z.read(n) for _i, n in sorted(v)) for k, v in parts.items()}
    fp = blobs[[n for n in blobs if n.lower().endswith(".fpage")][0]].decode("utf-8", "replace")
    m = re.search(r'<FixedPage[^>]*Width="([\d.]+)"[^>]*Height="([\d.]+)"', fp)
    pw, ph = float(m.group(1)), float(m.group(2))
    ox = oy = 0.0
    for t in re.findall(r'RenderTransform="([^"]+)"', fp):
        a = [float(v) for v in t.split(",")]
        ox, oy = ox + a[4], oy + a[5]
    vps = [tuple(float(v) for v in g) for g in
           re.findall(r'Viewport="([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)"', fp)]
    x0 = min(ox + v[0] for v in vps)
    y0 = min(oy + v[1] for v in vps)
    x1 = max(ox + v[0] + v[2] for v in vps)
    y1 = max(oy + v[1] + v[3] for v in vps)
    mm = 25.4 / 96
    cw, ch = (v * 25.4 / 72 for v in read_tiff_dimensions_points(chart))
    return {"paper_mm": [round(pw * mm, 2), round(ph * mm, 2)],
            "chart_mm": [round(cw, 2), round(ch, 2)],
            "placed_mm": [round((x1 - x0) * mm, 2), round((y1 - y0) * mm, 2)],
            "at_mm": [round(x0 * mm, 2), round(y0 * mm, 2)],
            "scale_percent": [round(100 * (x1 - x0) * mm / cw, 3), round(100 * (y1 - y0) * mm / ch, 3)]}


def _finish(app, default_before) -> int:
    set_default_printer(default_before)
    from workflow import win_spooler
    RESULT["default_printer_after"] = win_spooler.default_printer()
    RESULT["real_epson_jobs"] = len(win_spooler.jobs(REAL_EPSON))
    (OUT / f"RESULT-{ARGS.lang}.json").write_text(json.dumps(RESULT, indent=1, ensure_ascii=False),
                                                 encoding="utf-8")
    log(f"done; findings: {len(RESULT['findings'])}")
    app.quit()
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:  # noqa: BLE001
        RESULT["findings"].append(traceback.format_exc())
        (OUT / f"RESULT-{ARGS.lang}.json").write_text(json.dumps(RESULT, indent=1, ensure_ascii=False),
                                                     encoding="utf-8")
        traceback.print_exc()
        rc = 1
    os._exit(rc)
