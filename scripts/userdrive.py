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
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)          # a real, on-screen platform
ROOT = Path(os.environ.get("CHROMIQ_TREE")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DEMO_PACK = Path(os.environ.get(
    "CHROMIQ_DEMO_PACK", "/private/tmp/chromiq-k3/ChromIQ-Report-Limit-Demos"))


def _sandbox(out: Path) -> None:
    sb = out / "sandbox"
    (sb / "presets").mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CHROMIQ_SETTINGS_FILE", str(sb / "settings.ini"))
    os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(sb / "presets"))
    # FORCED, never setdefault: a caller's shell must not be able to point
    # this at the licence holder's file.
    os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
        ROOT / "data" / "compliance_sets" / "iso12647.json")


class Drive:
    def __init__(self, out, projects=(), language: str = "en",
                 appearance: str = "light", size=(1500, 1000)):
        self.out = Path(out).resolve()
        self.shots = self.out / "photographs"
        self.shots.mkdir(parents=True, exist_ok=True)
        _sandbox(self.out)
        self.notes: list[str] = []
        self.record: dict = {"mode": "ON SCREEN", "tree": str(ROOT),
                             "steps": [], "modals": [], "photos": []}

        from core.logger import _log_path, configure_logging
        configure_logging()
        self._log = _log_path()
        self._log_offset = self._log.stat().st_size if self._log.exists() else 0

        from scripts.capture_screens import build_app
        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance() or build_app()
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
        assert self.settings.get("custom_output_path", "") == str(self.work), \
            "SANDBOX FAILED"

        from ui.main_window import MainWindow
        from ui.theme import apply_appearance
        apply_appearance(self.app, None, appearance)
        self.win = MainWindow(self.settings)
        self.win.resize(*size)
        self.win.show()
        self.win.raise_()
        self.win.activateWindow()
        self.pump(2500)
        self.record["window_on_screen"] = bool(self.win.isVisible())

    # -- time ---------------------------------------------------------------
    def pump(self, ms: int = 300) -> None:
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
        self.pump(700)
        ok, why = capture_window(win, path)
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
        # The project picker is a native file dialog, which no driver can
        # operate; this is the call its accept handler makes.
        self.win._file_mgr.set_target_name(name)
        self.pump(900)

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
            assert self.pick(b._type_combo, run_type), f"no run type {run_type}"
            self.pump(700)
        if run is not None:
            label = run.replace("run", "Run ") if run.startswith("run") else run
            assert self.pick(b._run_combo, label), f"no profile run {run}"
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
        from PyQt6.QtWidgets import QAbstractButton
        end = time.monotonic() + within_ms / 1000.0
        w = None
        while time.monotonic() < end:
            self.pump(100)
            w = self.modal()
            if w is not None and w.isVisible():
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
        choice = next((b for b in buttons
                       if button_text.lower() in b.text().replace("&", "")
                       .lower()), None)
        self.record["modals"].append({
            "appeared": True, "class": type(w).__name__, "text": said,
            "buttons": [b.text() for b in buttons], "clicked":
            choice.text() if choice else None, "name": name})
        self.note(f"   [modal] {type(w).__name__}: "
                  f"{said[:160].replace(chr(10), ' / ')!r} -> "
                  f"{choice.text() if choice else 'NO SUCH BUTTON'}")
        if choice is None:
            w.reject() if hasattr(w, "reject") else w.close()
        else:
            choice.click()
        self.pump(600)
        return said

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
        self.pump(600)
        return str(p) in chosen

    # -- running -----------------------------------------------------------
    def run(self, script) -> int:
        """Step the generator from the event loop until it ends."""
        from PyQt6.QtCore import QTimer
        gen = script(self)
        state = {"rc": 0}

        def step():
            try:
                wait = next(gen)
            except StopIteration:
                self.app.quit()
                return
            except Exception:                              # noqa: BLE001
                self.note("DRIVER ERROR\n" + traceback.format_exc())
                state["rc"] = 2
                self.app.quit()
                return
            QTimer.singleShot(int(wait or 0), step)

        QTimer.singleShot(0, step)
        self.app.exec()
        self.finish()
        return state["rc"]

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
        self.record["log_lines"] = len(text.splitlines())
        self.record["log_warnings_and_errors"] = bad
        self.note(f"log: {len(text.splitlines())} lines during the drive, "
                  f"{len(bad)} warning/error lines")
        for ln in bad[:40]:
            self.note(f"   LOG {ln}")
        self._flush()
        try:
            self.win.close()
        except Exception:                                  # noqa: BLE001
            pass
