#!/usr/bin/env python3
"""Drive ChromIQ ON SCREEN the way a user does, and read the log afterwards.

Basti, 2026-09-22: verification is *"driving the real app on screen like a
real user would ... and check the log to make sure everything is working as
intended"*, not judging from code and gates. This is the shared harness for
that, so each driver is a short script of clicks rather than a new copy of the
same plumbing.

**NOTHING IS PATCHED OUT OF THE APP.** Earlier drivers replaced
`QMessageBox.exec` / `QDialog.exec` so a modal could not block them. That
photographs a window the app built, but it also answers every question with
whatever the patch returns, which is not what a user does. Here the script is
a GENERATOR stepped by a `QTimer`, so the application's own `exec()` calls run
for real and the script keeps going inside them: it sees the modal, photographs
it with `onscreen_capture.capture_window`, and clicks the button a user would.

    from userdrive import Drive
    d = Drive(out_dir, projects=["Report-Limits-Threshold-Series"])
    def script(d):
        d.open_project("Report-Limits-Threshold-Series")
        d.set_bar(run="run1", run_type="Verification")
        yield 800
        d.launch_tool("measurement_report")     # the real exec(), non-blocking
        yield 2500
        dlg = d.top_dialog("MeasurementReportDialog")
        d.shot(dlg, "01-open")
    d.run(script)

Sandboxing is enforced, not requested: the settings file, the presets folder
and the ISO file (a licence holder's real values live on this machine and must
never reach a proof folder) are set here before anything is imported.

**A DRIVE ALWAYS ENDS, AND ENDS WITH NOTHING LEFT ON SCREEN (4.3.11).** Four
drivers in one day (2026-10-23) left a ChromIQ window hanging on Basti's
screen, each fixed only in its own script. The harness now does it for all:

* a script that RAISES ends the run: the traceback goes into the notes, every
  window is photographed and closed, the app quits, and :meth:`Drive.run`
  returns 2 (non-zero, so ``sys.exit(rc)`` says so);
* every run has a HARD TIME LIMIT (``time_limit_s``, default 600 s, or
  ``CHROMIQ_DRIVE_TIME_LIMIT``): when it is up the open windows are
  photographed and the run ends cleanly with 3. A last-resort thread ends the
  process 90 s later if the GUI thread is wedged and could not do that;
* a :class:`onscreen_capture.PopupWatchdog` runs from the start (``d.dog``):
  an unscripted question is dismissed safely after 15 s, an unclaimed working
  window after 20 s. :meth:`top_dialog` claims the window it returns;
* an exception in one of the APP's slots is logged (as in main()) and makes
  the run 4 instead of 0: the app did something wrong while being driven;
* nothing the app hands to another application (a PDF to Preview, a folder to
  Finder, a link to the browser) is opened: it is recorded in
  ``opened-elsewhere.txt`` (``capture_screens.build_app``);
* :meth:`answer` and :meth:`click` find a button by its ENGLISH label in any
  language (``tr()`` of it, or Qt's own translation of a standard button).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)          # a real, on-screen platform
ROOT = Path(os.environ.get("CHROMIQ_TREE")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

#: The demo pack a drive copies its projects from. The pack rebuilt for K15
#: (2026-09-22) is kept on the Desktop proof tree, because /private/tmp is
#: swept nightly; the older build is the fallback.
_NEW_PACK = (Path.home() / "Desktop" / "ChromIQ-beta36-proof" / "demo-pack"
             / "ChromIQ-Report-Limit-Demos")
DEMO_PACK = Path(os.environ.get(
    "CHROMIQ_DEMO_PACK",
    str(_NEW_PACK if _NEW_PACK.is_dir()
        else Path("/private/tmp/chromiq-k3/ChromIQ-Report-Limit-Demos"))))


def _sandbox(out: Path) -> None:
    sb = out / "sandbox"
    (sb / "presets").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CHROMIQ_SETTINGS_FILE", str(sb / "settings.ini"))
    os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(sb / "presets"))
    # FORCED, never setdefault: a caller's shell must not be able to point
    # this at the licence holder's file.
    os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
        ROOT / "data" / "compliance_sets" / "iso12647.json")


#: Return codes of :meth:`Drive.run`.
RC_OK, RC_SCRIPT_RAISED, RC_TIME_LIMIT, RC_APP_RAISED = 0, 2, 3, 4
#: Default hard limit for one drive, in seconds.
DEFAULT_TIME_LIMIT_S = 600.0
#: How long after the time limit the last-resort thread ends the process.
HARD_KILL_AFTER_S = 90.0


def _time_limit(value) -> float:
    if value is not None:
        return float(value)
    env = os.environ.get("CHROMIQ_DRIVE_TIME_LIMIT", "").strip()
    try:
        return float(env) if env else DEFAULT_TIME_LIMIT_S
    except ValueError:
        return DEFAULT_TIME_LIMIT_S


class Drive:
    # Class defaults, so a harness built with __new__ (the suite does) ends
    # the same way.
    time_limit_s: float = DEFAULT_TIME_LIMIT_S
    _ending = False
    _rc = RC_OK
    dog = None
    win = None
    _external_at_start = 0
    _uncaught_at_start = 0

    def __init__(self, out, projects=(), language: str = "en",
                 appearance: str = "light", size=(1500, 1000), *,
                 time_limit_s: "float | None" = None,
                 popup_policy: str = "dismiss", watchdog: bool = True):
        self.out = Path(out).resolve()
        self.time_limit_s = _time_limit(time_limit_s)
        self._ending = False
        self._rc = RC_OK
        self.shots = self.out / "photographs"
        self.shots.mkdir(parents=True, exist_ok=True)
        _sandbox(self.out)
        self.notes: list[str] = []
        #: Set when this step has just closed a modal (a button clicked, a
        #: file chooser accepted); cleared when the next step starts. While it
        #: is set, `pump` does NOT call processEvents: see `_modal_closed`.
        self._closed_a_modal = False
        self.record: dict = {"mode": "ON SCREEN", "tree": str(ROOT),
                             "steps": [], "modals": [], "photos": []}

        from core.logger import _log_path, configure_logging
        configure_logging()
        self._log = _log_path()
        self._log_offset = self._log.stat().st_size if self._log.exists() else 0

        from scripts.capture_screens import build_app
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance() or build_app()
        import onscreen_capture
        # Recorded in THIS drive's folder too (build_app blocked the openers).
        if os.environ.get("CHROMIQ_DRIVER_ALLOW_EXTERNAL_APPS") != "1":
            onscreen_capture.block_external_apps(
                self.out / "opened-elsewhere.txt")
        self._external_at_start = len(onscreen_capture.EXTERNAL_OPENS)
        self._uncaught_at_start = len(self._uncaught())
        #: The drive's own pop-up watchdog, running before the first window.
        self.dog = None
        if watchdog:
            # 15 s FOR A QUESTION, NOT THE WATCHDOG'S 1.5: the drive's own
            # steps answer questions (answer() waits up to 6 s, a step may
            # photograph first), and the dog is the net under them, not a
            # competitor. Measured on the first cut: it pressed Escape on
            # "Re-measurement Complete" before the step could photograph it.
            self.dog = onscreen_capture.PopupWatchdog(
                self.out, policy=popup_policy, photograph=True,
                grace_s=15.0, window_grace_s=20.0,
                log=self._dog_line).start()
        from core.settings import AppSettings
        self.settings = AppSettings()
        self.work = self.out / "projects"
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        for name in projects:
            shutil.copytree(DEMO_PACK / name, self.work / name)
        self.settings.set("custom_output_path", str(self.work))
        self.settings.set("argyll_bin_path", "/Applications/Argyll/bin")
        self.settings.set("language", language)
        # THE SETTING ALONE TRANSLATES NOTHING (round B, 2026-09-22): main.py
        # loads the catalogue and Qt's own translator at start-up, so a drive
        # asked for "de" came out in English until this did the same.
        try:
            from core.i18n import install_qt_translator, set_language
            set_language(language)
            install_qt_translator(self.app)
        except Exception as exc:                          # noqa: BLE001
            print(f"could not switch the UI language to {language}: {exc}")
        assert self.settings.get("custom_output_path", "") == str(self.work), \
            "SANDBOX FAILED"

        # **THE APPEARANCE IS A SETTING, NOT ONLY A PALETTE (challenge 2 of
        # beta 42, #8).** The palette and the style sheet alone left
        # `appearance` at whatever the sandbox held, and every window that
        # picks its own colours reads the SETTING (the Measurement Report's
        # page, its strip, its graphs): a "dark" drive photographed a light
        # report on a dark window. Written first, then applied as main.py
        # applies it, before and after the window exists.
        self.settings.set("appearance", appearance)
        assert self.settings.get("appearance", "") == appearance, \
            "the appearance setting did not take"
        from ui.main_window import MainWindow
        from ui.theme import apply_appearance
        apply_appearance(self.app, None, appearance)
        self.win = MainWindow(self.settings)
        apply_appearance(self.app, self.win, appearance)
        self.win.resize(*size)
        self.win.show()
        # No raise_()/activateWindow(): the capture reads the window's own
        # buffer behind other windows, and pulling ChromIQ to the front took
        # Basti's keyboard while he typed (CLAUDE.md). Hand it straight back.
        focus = getattr(self.app, "_chromiq_focus_give_back", None)
        if focus is not None:
            focus.give_back()
        self.pump(2500)
        self.record["window_on_screen"] = bool(self.win.isVisible())

    def _dog_line(self, line: str) -> None:
        print(line, flush=True)
        self.notes.append(line)

    @staticmethod
    def _uncaught() -> list:
        mod = sys.modules.get("scripts.capture_screens") or sys.modules.get(
            "capture_screens")
        return list(getattr(mod, "UNCAUGHT", []) or [])

    # -- time ---------------------------------------------------------------
    def pump(self, ms: int = 300) -> None:
        if self._closed_a_modal:
            # A MODAL WAS JUST CLOSED IN THIS STEP. Its exec() is on the stack
            # under this call and can only return once this step returns to
            # it; pumping here is what left "Save report as PDF" waiting two
            # minutes for the report window to close (beta 38, B8-831). The
            # wait the caller wanted happens on its next `yield` instead.
            return
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)

    # -- notes and photographs ---------------------------------------------
    def note(self, line: str) -> None:
        print(line, flush=True)
        self.notes.append(line)
        self._flush()

    def shot(self, widget, name: str) -> bool:
        """A photograph of the WINDOW `widget` lives in, by window id."""
        from onscreen_capture import capture_window
        win = widget.window() if widget is not None else self.win
        path = self.shots / f"{name}.png"
        if self._closed_a_modal:
            # capture_window pumps the loop too (see `_modal_closed`)
            self.record["photos"].append({"file": path.name, "ok": False,
                                          "why": "a modal was closed in this "
                                          "step; yield before photographing"})
            self.note(f"   [photo] {path.name}: SKIPPED, a modal was closed "
                      f"in this step (yield first)")
            return False
        self.pump(700)
        # NEVER THE RECTANGLE ROUTE (4.3.11), for any window: it needs the
        # window in front, which takes Basti's keyboard, and proves itself by
        # HIDING it, which ends a dialog's exec() as Rejected. A failed
        # window-id capture is recorded as a failed photograph.
        ok, why = capture_window(win, path, allow_hide=False)
        self.record["photos"].append({"file": path.name, "ok": ok, "why": why,
                                      "window": type(win).__name__})
        self.note(f"   [photo] {path.name}: {'ok' if ok else 'FAILED ' + why}")
        return ok

    def _flush(self) -> None:
        (self.out / "driver-notes.txt").write_text(
            "\n".join(self.notes) + "\n", encoding="utf-8")
        (self.out / "driver-report.json").write_text(
            json.dumps(self.record, indent=2, default=str), encoding="utf-8")

    # -- the user's controls -----------------------------------------------
    @property
    def bar(self):
        from ui.measurement_target_bar import MeasurementTargetBar
        return self.win.findChild(MeasurementTargetBar)

    @property
    def ctl(self):
        return self.win._tab_measure._target_ctl

    def open_project(self, name: str) -> None:
        """Open a project the way Load does: `TabChart.open_project_manifest`,
        the WHOLE open (schema announcement, state resets, chart display),
        which is what the masthead's Load button calls once its file dialog
        has a project.json. The first cut of this set the target name only,
        which is not what the app does: the bar's run pulldown never filled
        and a drive standing on Profiling found no runs at all (K16).

        Queued, so a question the open asks runs as a real modal."""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.win._tab_chart.open_project_manifest(
            self.work / name / "project.json"))
        self.pump(900)
        # WAIT FOR THE BAR TO SHOW THE PROJECT'S RUNS. Measured: straight after
        # the name is set the run pulldown can still hold only "New run", and
        # a drive that picks a run then finds nothing (K16's first drive).
        combo = self.bar._run_combo
        t0 = time.monotonic()
        while time.monotonic() - t0 < 10 and combo.count() <= 1:
            self.pump(200)
        self.note(f"project {name!r} open; run pulldown after "
                  f"{time.monotonic() - t0:.1f} s: "
                  f"{[combo.itemText(i) for i in range(combo.count())]}")

    @staticmethod
    def pick(combo, text: str) -> bool:
        """Choose the entry whose visible text contains `text` (case-blind),
        the way a user picks from a pulldown."""
        for i in range(combo.count()):
            if text.lower() in combo.itemText(i).lower():
                combo.setCurrentIndex(i)
                combo.activated.emit(i)
                return True
        return False

    def set_bar(self, run: "str | None" = None, run_type: "str | None" = None,
                verification: "str | None" = None) -> None:
        b = self.bar
        if run_type is not None:
            # BY ITS STORED VALUE, so a drive in German still finds
            # "Verifizierung" (the first German drive failed on the label).
            from core import measurement_target as MT
            data = {"profiling": MT.RUN_TYPE_PROFILING,
                    "verification": MT.RUN_TYPE_VERIFICATION}.get(
                        run_type.lower())
            idx = b._type_combo.findData(data) if data is not None else -1
            if idx >= 0:
                b._type_combo.setCurrentIndex(idx)
                b._type_combo.activated.emit(idx)
            else:
                assert self.pick(b._type_combo, run_type), \
                    f"no run type {run_type}"
            self.pump(700)
        if run is not None:
            combo = b._run_combo
            for _ in range(20):                 # the bar refills after a type
                idx = combo.findData(run)       # change; wait for the run
                if idx >= 0:
                    break
                self.pump(150)
            assert idx >= 0, (f"no profile run {run}: "
                              f"{[combo.itemText(i) for i in range(combo.count())]}")
            combo.setCurrentIndex(idx)
            combo.activated.emit(idx)
            self.pump(700)
        if verification is not None:
            assert self.pick(b._verify_combo, verification), \
                f"no verification {verification}"
            self.pump(700)

    def goto_tab(self, key: str) -> None:
        idx = {"chart": 0, "print": 1, "measure": 2, "profile": 3,
               "check": 4}[key]
        self.win._tabs.setCurrentIndex(idx)
        self.pump(900)

    def launch_tool(self, key: str) -> None:
        """What the Tools menu entry does, including its blocking exec(),
        queued so the script keeps running inside it."""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.win._launch_tool(key))

    def later(self, fn) -> None:
        """Run `fn` on the next turn: for anything that opens a modal."""
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, fn)

    def top_dialog(self, cls_name: str):
        from PyQt6.QtWidgets import QApplication
        for w in QApplication.topLevelWidgets():
            if type(w).__name__ == cls_name and w.isVisible():
                # a window the drive is working IN is never a question
                self._known_windows = getattr(self, "_known_windows", set())
                self._known_windows.add(id(w))
                if getattr(self, "dog", None) is not None:
                    self.dog.claim(w)
                return w
        return None

    def modal(self):
        from PyQt6.QtWidgets import QApplication
        return QApplication.activeModalWidget()

    def modal_text(self, w) -> str:
        from PyQt6.QtWidgets import QLabel
        bits = []
        try:
            bits.append(w.text())
        except Exception:                                  # noqa: BLE001
            pass
        for lab in w.findChildren(QLabel):
            if lab.isVisible() and lab.text():
                bits.append(lab.text())
        return "\n".join(b for b in bits if b)

    def answer(self, button_text: str, name: str | None = None,
               within_ms: int = 6000) -> "str | None":
        """Wait for a modal, photograph it, record what it says, and click the
        button whose text contains `button_text`. Returns its text, or None if
        no modal came (which is recorded too)."""
        from PyQt6.QtWidgets import QAbstractButton, QApplication
        # ONLY A WINDOW THAT WAS NOT ALREADY UP. The report window is itself a
        # modal dialog, so "the active modal" is IT whenever no question
        # comes: the first cut took the report window for the question, found
        # no such button and rejected it (K16's drive). Whatever was visible
        # before this call is excluded, and nothing is ever rejected.
        already = {id(w) for w in QApplication.topLevelWidgets()
                   if w.isVisible() and w is not self.modal()} | set(
            getattr(self, "_known_windows", set()))
        end = time.monotonic() + within_ms / 1000.0
        w = None
        while time.monotonic() < end:
            self.pump(100)
            w = self.modal()
            if w is not None and w.isVisible() and id(w) not in already:
                break
            w = None
        if w is None:
            self.record["modals"].append({"expected": button_text,
                                          "appeared": False, "name": name})
            self.note(f"   [modal] none appeared (wanted to click "
                      f"{button_text!r})")
            return None
        self.pump(600)
        said = self.modal_text(w)
        if name:
            self.shot(w, name)
        buttons = [b for b in w.findChildren(QAbstractButton)
                   if b.isVisible() and b.text()]
        # IN ANY LANGUAGE: "Cancel" finds "Abbrechen" in a German drive.
        from onscreen_capture import find_button
        choice = find_button(w, button_text, exact=False)
        self.record["modals"].append({
            "appeared": True, "class": type(w).__name__, "text": said,
            "buttons": [b.text() for b in buttons], "clicked":
            choice.text() if choice else None, "name": name})
        self.note(f"   [modal] {type(w).__name__}: "
                  f"{said[:160].replace(chr(10), ' / ')!r} -> "
                  f"{choice.text() if choice else 'NO SUCH BUTTON'}")
        if choice is not None:
            choice.click()
            self._modal_closed()
        return said

    def button(self, widget, english: str, exact: bool = False):
        """The visible button in *widget* labelled *english*, in whatever
        language the drive runs in (``tr()`` of the label, or Qt's own
        translation of a standard button). None when there is none."""
        from onscreen_capture import find_button
        return find_button(widget, english, exact=exact)

    def click(self, widget, english: str, exact: bool = False) -> bool:
        """Click the button labelled *english* in *widget*, in any language.
        From inside a modal, the click is queued, so this step returns to the
        modal's loop before it acts (see `_modal_closed`)."""
        from PyQt6.QtCore import QTimer
        b = self.button(widget, english, exact=exact)
        self.note(f"   [click] {english!r} -> "
                  f"{b.text() if b is not None else 'NO SUCH BUTTON'}")
        if b is None:
            return False
        QTimer.singleShot(0, b.click)
        return True

    def answer_file(self, path, name: str | None = None,
                    within_ms: int = 6000) -> bool:
        """Wait for ChromIQ's own file dialog and pick *path* in it, the way a
        user types a name into its box and presses Open. (The OS-native
        dialog cannot be driven; ChromIQ uses its own unless Preferences say
        otherwise, and a sandboxed settings file does not say so.)"""
        from PyQt6.QtWidgets import QFileDialog
        end = time.monotonic() + within_ms / 1000.0
        w = None
        while time.monotonic() < end:
            self.pump(100)
            m = self.modal()
            if isinstance(m, QFileDialog):
                w = m
                break
        if w is None:
            self.note(f"   [file dialog] none appeared (wanted {path})")
            return False
        self.pump(500)
        if name:
            self.shot(w, name)
        from PyQt6.QtWidgets import QLineEdit
        p = Path(path)
        # TYPED INTO THE NAME BOX, the way a user pastes a path. The first cut
        # called `setDirectory` + `selectFile(name)`; the directory listing
        # arrives asynchronously, `selectedFiles()` came back without the file,
        # and the app was handed nothing (K17's first drive: "loaded runs: 1").
        w.setDirectory(str(p.parent))
        self.pump(800)
        box = w.findChild(QLineEdit, "fileNameEdit")
        if box is not None:
            box.setText(str(p))
        else:
            w.selectFile(str(p))
        self.pump(400)
        chosen = list(w.selectedFiles())
        self.note(f"   [file dialog] {w.windowTitle()!r} -> {p}; the dialog "
                  f"reports selected: {chosen}")
        w.accept()
        self._modal_closed()
        return str(p) in chosen

    def _modal_closed(self) -> None:
        """A modal was just answered from inside its own exec(). Return to it.

        **NOTHING MAY CALL processEvents() BETWEEN HERE AND THE NEXT `yield`.**
        This step runs as a timer callback INSIDE the modal's exec() loop.
        `accept()` asks that loop to exit, and on macOS (the cocoa event
        dispatcher) a processEvents() call made on top of it before it gets
        control back can swallow the wake-up: the dialog is hidden, its result
        is Accepted, and its exec() does not return until something else
        interrupts the dispatcher. Measured on screen, beta 38 (B8-831): the
        file chooser of "Save report as PDF" sat in exec() for two minutes,
        every timer still firing inside it, and returned only when the drive
        closed the report window, so the PDF was written then. A standalone
        probe (`scripts/probe_dialog_exit_after_reentrant_pump.py`, plain Qt,
        no ChromIQ) gives the same: accept-and-return 0.02 s in 6 of 6;
        accept-then-pump stuck in 2 of 6; a queued accept fired inside the pump
        stuck in 6 of 6.

        A user's click is delivered by the modal's own loop and never has a
        processEvents() on top of it, so this is a property of the drivers.
        """
        self._closed_a_modal = True

    def read_file_dialog(self, name: str | None = None,
                         within_ms: int = 6000) -> "dict | None":
        """Wait for ChromIQ's own file dialog, record the folder it OPENED in
        and the name it offers, photograph it, and cancel it (as a user who
        only looks). Returns {"dir", "selected", "title"} or None."""
        from PyQt6.QtWidgets import QFileDialog, QLineEdit
        end = time.monotonic() + within_ms / 1000.0
        w = None
        while time.monotonic() < end:
            self.pump(100)
            m = self.modal()
            if isinstance(m, QFileDialog):
                w = m
                break
        if w is None:
            self.note("   [file dialog] none appeared")
            return None
        self.pump(700)
        box = w.findChild(QLineEdit, "fileNameEdit")
        info = {"dir": w.directory().absolutePath(),
                "selected": list(w.selectedFiles()),
                "name_box": box.text() if box is not None else None,
                "title": w.windowTitle()}
        if name:
            self.shot(w, name)
        self.note(f"   [file dialog] {info['title']!r} opened in "
                  f"{info['dir']} offering {info['name_box']!r}")
        w.reject()
        self.pump(500)
        return info

    # -- running -----------------------------------------------------------
    def run(self, script) -> int:
        """Step the generator from the event loop until it ends, raises, or
        runs out of time; then close every window and return the verdict
        (RC_OK 0, RC_SCRIPT_RAISED 2, RC_TIME_LIMIT 3, RC_APP_RAISED 4)."""
        from PyQt6.QtCore import QTimer
        gen = script(self)
        self.record["time_limit_s"] = self.time_limit_s

        def step():
            if self._ending:
                return
            self._closed_a_modal = False
            try:
                wait = next(gen)
            except StopIteration:
                self.end(RC_OK, "the script finished")
                return
            except Exception:                              # noqa: BLE001
                self.note("DRIVER ERROR\n" + traceback.format_exc())
                self.end(RC_SCRIPT_RAISED, "the script raised (traceback "
                         "above)")
                return
            if not self._ending:
                QTimer.singleShot(int(wait or 0), step)

        def out_of_time():
            self.end(RC_TIME_LIMIT, f"the time limit of "
                     f"{self.time_limit_s:.0f} s was reached")

        # A LAST RESORT FOR A WEDGED GUI THREAD. Everything above runs on the
        # event loop; if a native call never returns, nothing there can end
        # the run, and the window would stay on Basti's screen. This thread
        # ends the process instead (os._exit stops the helper first).
        def hard_stop():
            try:
                self.note(f"DRIVE KILLED: still running "
                          f"{HARD_KILL_AFTER_S:.0f} s after the time limit")
            finally:
                os._exit(RC_TIME_LIMIT)

        self._limit_timer = QTimer()
        self._limit_timer.setSingleShot(True)
        self._limit_timer.timeout.connect(out_of_time)
        self._limit_timer.start(int(self.time_limit_s * 1000))
        killer = threading.Timer(self.time_limit_s + HARD_KILL_AFTER_S,
                                 hard_stop)
        killer.daemon = True
        killer.start()
        QTimer.singleShot(0, step)
        try:
            self.app.exec()
        finally:
            killer.cancel()
            self._limit_timer.stop()
        self.finish()
        return self._rc

    # -- ending --------------------------------------------------------------
    def end(self, rc: int, why: str) -> None:
        """End the drive from inside the event loop: photograph what is open
        (unless the script finished), close every window, then leave every
        event loop. Safe to call from any step, and only the first call
        counts. Runs as three timer turns, so nothing pumps on top of a modal
        this step may just have closed."""
        from PyQt6.QtCore import QTimer
        if self._ending:
            return
        self._ending = True
        self._rc = rc
        self.record["ended"] = {"rc": rc, "why": why}
        self.note(f"DRIVE ENDING ({rc}): {why}")
        self._end_photo = rc != RC_OK
        QTimer.singleShot(0, self._end_close_dialogs)

    def _main_window(self) -> list:
        """The main window as a list, empty when there is no real one."""
        from PyQt6.QtWidgets import QWidget
        return [self.win] if isinstance(self.win, QWidget) else []

    def _open_windows(self) -> list:
        from PyQt6.QtWidgets import QApplication
        return [w for w in QApplication.topLevelWidgets()
                if w.isVisible() and w is not self.win]

    def _end_close_dialogs(self) -> None:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QDialog
        from onscreen_capture import capture_window
        if self._end_photo:
            for i, w in enumerate(self._main_window() + self._open_windows()):
                path = self.shots / f"zz-at-end-{i:02d}.png"
                try:
                    ok, why = capture_window(w, path, allow_hide=False)
                except Exception as exc:                   # noqa: BLE001
                    ok, why = False, str(exc)
                self.record["photos"].append({"file": path.name, "ok": ok,
                                              "why": why, "at_end": True})
                self.note(f"   [photo at end] {path.name} "
                          f"({w.windowTitle()!r}): "
                          f"{'ok' if ok else 'FAILED ' + why}")
        # The innermost modal first: rejecting it returns to the one below.
        todo = []
        top = QApplication.activeModalWidget()
        if top is not None:
            todo.append(top)
        todo += [w for w in reversed(self._open_windows()) if w not in todo]
        for w in todo:
            self.note(f"   [end] closing {type(w).__name__} "
                      f"{w.windowTitle()!r}")
            if isinstance(w, QDialog):
                w.reject()
            else:
                w.close()
        QTimer.singleShot(1500, self._end_close_main)

    def _end_close_main(self) -> None:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QDialog
        for w in self._open_windows():
            # reject() was refused (a window that asks first, and the
            # watchdog answered Cancel): done() hides it without asking
            self.note(f"   [end] still open, ending: {type(w).__name__} "
                      f"{w.windowTitle()!r}")
            if isinstance(w, QDialog):
                w.done(QDialog.DialogCode.Rejected.value)
            else:
                w.hide()
        try:
            for w in self._main_window():
                if w.isVisible():
                    w.close()         # its questions are answered by the dog
        except Exception:                                  # noqa: BLE001
            self.note("   [end] closing the main window raised:\n"
                      + traceback.format_exc())
        QTimer.singleShot(3000, self._end_leave)

    def _end_leave(self) -> None:
        for w in self._main_window() + self._open_windows():
            try:
                if w.isVisible():
                    self.note(f"   [end] hiding {type(w).__name__} "
                              f"{w.windowTitle()!r}")
                    w.hide()
            except RuntimeError:
                pass
        # exit(), NOT quit(): QGuiApplication.quit() asks every window to
        # close first and gives up if one refuses, which is how a window
        # stayed up. exit() leaves every running event loop, nested modal
        # loops included, and makes a new exec() return at once.
        self.app.exit(self._rc)

    def finish(self) -> None:
        """Save everything the log said while this drive ran, and flag the
        lines a reader must look at."""
        text = ""
        try:
            with open(self._log, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._log_offset)
                text = f.read()
        except OSError as exc:
            text = f"(could not read {self._log}: {exc})"
        (self.out / "chromiq-log-during-drive.txt").write_text(
            text, encoding="utf-8")
        # The sandbox notice is this harness announcing itself, not a fault.
        bad = [ln for ln in text.splitlines()
               if ("[WARNING]" in ln or "[ERROR]" in ln or "[CRITICAL]" in ln
                   or "Traceback" in ln) and "Settings SANDBOXED" not in ln]
        import onscreen_capture
        elsewhere = onscreen_capture.EXTERNAL_OPENS[self._external_at_start:]
        self.record["opened_elsewhere"] = elsewhere
        for what in elsewhere:
            self.note(f"   NOT OPENED in another app: {what}")
        uncaught = self._uncaught()[self._uncaught_at_start:]
        self.record["app_exceptions"] = uncaught
        if uncaught:
            self.note(f"THE APP RAISED {len(uncaught)} exception(s) during "
                      f"the drive; the first:\n{uncaught[0]}")
            if self._rc == RC_OK:
                self._rc = RC_APP_RAISED
        if getattr(self, "dog", None) is not None:
            self.dog.stop()
            self.record["popups"] = self.dog.events
        self.record["rc"] = self._rc
        self.record["log_lines"] = len(text.splitlines())
        self.record["log_warnings_and_errors"] = bad
        self.note(f"log: {len(text.splitlines())} lines during the drive, "
                  f"{len(bad)} warning/error lines")
        for ln in bad[:40]:
            self.note(f"   LOG {ln}")
        self._flush()
        try:
            # closed in the loop by `end`; never ask anything out here, where
            # no event loop runs and a question would wait for ever
            for w in self._main_window():
                if w.isVisible():
                    w.hide()
        except Exception:                                  # noqa: BLE001
            pass
