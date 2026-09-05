"""Shared on-screen harness for the profile-engine accuracy challenge.

Boots the REAL app (real style, fonts, event filters, MainWindow) against a
sandboxed settings store and a sandboxed working folder, creates projects
from copied measurements, and offers the few verbs every challenge driver
needs: open a project, switch the engine mode, press Build Profile, wait
for the build, take a screenshot, and answer modals WITHOUT hiding that a
modal was answered.

Safety (CLAUDE.md "Driving the app on screen — sandbox the settings FIRST"):

* ``core.settings.QSettings`` is redirected to a throw-away ``.ini`` BEFORE
  ``AppSettings()`` is built, so the user's real preferences are unreachable;
  ``CHROMIQ_SETTINGS_FILE`` is exported too, for any subprocess.
* ``custom_output_path`` points at the sandbox, never at ``~/ChromIQ``.
* ``CHROMIQ_PRESETS_DIR`` points at the sandbox.
* Measurements are COPIED in; nothing under ``~/ChromIQ`` is opened in place.

Usage from a driver::

    from scripts.engine_challenge.harness import Harness
    h = Harness(Path("~/Desktop/ChromIQ-engine-challenge/sandbox-x").expanduser())
    h.boot()                                   # real window on screen
    h.make_project("Real-924", CHART_924)      # run1/<name>.ti3 from a copy
    h.open_project("Real-924")
    h.enable_engine("accurate")                # settings level (no dialog)
    h.build()                                  # presses the real button
    h.wait_build_done(timeout=600)
    h.screenshot("after-build")
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Harness:
    def __init__(self, sandbox: Path, *, appearance: str = "light",
                 onscreen: bool = True, size=(1700, 1050),
                 language: str = "en") -> None:
        self.sandbox = Path(sandbox)
        #: UI language, applied exactly as main.py does (set_language before
        #: any widget exists, Qt's own translator after). Agent B, journey B9.
        self.language = language
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self.work = self.sandbox / "ChromIQ"          # custom_output_path
        self.work.mkdir(exist_ok=True)
        self.shots = self.sandbox / "screenshots"
        self.shots.mkdir(exist_ok=True)
        self.ini = self.sandbox / "settings.ini"
        self.presets = self.sandbox / "presets"
        self.presets.mkdir(exist_ok=True)
        self.appearance = appearance
        self.onscreen = onscreen
        self.size = size
        self.app = None
        self.win = None
        self.settings = None
        self.log_lines: list[str] = []
        self.modals_answered: list[tuple[str, str]] = []
        self._modal_timer = None

    # ------------------------------------------------------------ boot
    def boot(self):
        os.environ["CHROMIQ_SETTINGS_FILE"] = str(self.ini)
        os.environ["CHROMIQ_PRESETS_DIR"] = str(self.presets)
        if self.onscreen:
            os.environ["CHROMIQ_DRIVE_ONSCREEN"] = "1"
            os.environ.pop("QT_QPA_PLATFORM", None)
        else:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        try:
            import PyQt6.QtWebEngineWidgets  # noqa: F401
        except ImportError:
            pass
        from PyQt6.QtCore import QSettings as _QS
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtWidgets import QApplication

        from core.freetype_bootstrap import ensure_freetype_library
        ensure_freetype_library()
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setApplicationName("ChromIQ")
        app.setOrganizationName("ChromIQ")

        from core.resource_path import resource_path
        from ui.styles import WinButtonLayoutStyle
        from ui.theme import apply_appearance
        from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                                GroupBoxSurfaceFilter, TooltipWrapFilter)
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
        app.setStyle(WinButtonLayoutStyle("Fusion"))
        for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
                  DialogFocusFilter):
            app.installEventFilter(F(app))

        import core.settings as cs
        ini = self.ini
        cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
        s = cs.AppSettings()
        s.set("custom_output_path", str(self.work))
        s.set("argyll_bin_path", "/Applications/Argyll/bin")
        s.set("language", self.language)
        from core.i18n import install_qt_translator, set_language
        set_language(self.language)
        install_qt_translator(app)
        apply_appearance(app, None, self.appearance)

        from ui.main_window import MainWindow
        w = MainWindow(s)
        apply_appearance(app, w, self.appearance)
        w.resize(*self.size)
        w.show()
        if self.onscreen:
            w.raise_()
            w.activateWindow()
        self.app, self.win, self.settings = app, w, s
        self.pump(600)
        return app, w, s

    # ------------------------------------------------------------ verbs
    def pump(self, ms: int = 200) -> None:
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)

    def wait_until(self, pred: Callable[[], bool], timeout: float = 30.0,
                   what: str = "") -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred():
                return True
            self.pump(100)
        print(f"  !! timeout waiting for {what or pred}", flush=True)
        return False

    def make_project(self, name: str, ti3_src: Path, *,
                     extra: dict[str, Path] | None = None) -> Path:
        """Create ``<work>/<name>`` with run1/<name>.ti3 from a COPY."""
        from core.file_manager import Project
        root = self.work / name
        proj = Project.create(root, name)
        run = proj.current_run()
        dst = run.measurement_ti3
        shutil.copyfile(ti3_src, dst)
        for rel, src in (extra or {}).items():
            tgt = run.dir / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, tgt)
        return root

    def open_project(self, name: str, run: str = "run1") -> None:
        from core.measurement_target import RUN_TYPE_PROFILING
        fm = self.win._file_mgr
        fm.set_target_name(name)
        ctl = getattr(self.win._tab_measure, "_target_ctl", None)
        if ctl is not None:
            ctl.set_profile_run(run)
            ctl.set_run_type(RUN_TYPE_PROFILING)
        self.pump(400)

    def enable_engine(self, mode: str = "accurate", on: bool = True) -> None:
        """Settings-level switch (what Preferences → Beta writes)."""
        self.settings.set("profile_engine_beta", bool(on))
        self.settings.set("gammap_mode", mode)
        self.win._tab_profile._refresh_engine_rows()
        self.pump(100)

    def go_profile_tab(self, mode: str | None = None):
        prof = self.win._tab_profile
        self.win._tabs.setCurrentWidget(prof)
        self.pump(300)
        if mode:
            btn = {"guided": prof._guided_btn, "manual": prof._manual_btn}.get(mode)
            if btn is not None:
                btn.click()
                self.pump(300)
        return prof

    def load_measurement(self, ti3: Path) -> None:
        prof = self.go_profile_tab()
        prof.set_ti3_path(Path(ti3), propagate=False)
        self.pump(300)

    def build(self) -> None:
        """Press the REAL Build Profile button."""
        prof = self.go_profile_tab()
        self.log_lines.clear()
        prof._log.clear()
        prof._build_btn.click()
        self.pump(300)

    def wait_build_done(self, timeout: float = 900.0) -> bool:
        prof = self.win._tab_profile
        t0 = time.monotonic(); last = [0.0]

        def _done() -> bool:
            if time.monotonic() - last[0] > 10.0:
                last[0] = time.monotonic()
                dlg = self.app.activeModalWidget()
                tail = (prof._log.toPlainText().splitlines() or [""])[-1]
                print(f"  [wait {time.monotonic()-t0:4.0f}s] btn.enabled="
                      f"{prof._build_btn.isEnabled()} engine.running="
                      f"{self.win._tab_profile._engine_builder.is_running} "
                      f"modal={dlg.windowTitle() if dlg else None} "
                      f"last={tail[:90]!r}", flush=True)
            return prof._build_btn.isEnabled()
        ok = self.wait_until(_done, timeout, "build to finish")
        self.log_lines = prof._log.toPlainText().splitlines()
        return ok

    def build_log(self) -> str:
        return self.win._tab_profile._log.toPlainText()

    def screenshot(self, name: str, widget=None, *, screen: bool = False) -> Path:
        """Real pixels of the widget as the app paints it (``QWidget.grab``,
        real style, real fonts). ``screen=True`` additionally saves the whole
        screen through macOS ``screencapture`` (proves what is really on the
        display, dialogs included). ``QScreen.grabWindow`` is NOT used: on
        this macOS it blocks the process (measured 2026-09-04)."""
        import subprocess
        w = widget or self.win
        self.pump(150)
        stamp = time.strftime("%H%M%S")
        path = self.shots / f"{stamp}-{name}.png"
        w.grab().save(str(path))
        if screen and self.onscreen:
            try:
                subprocess.run(["screencapture", "-x",
                                str(self.shots / f"{stamp}-{name}-screen.png")],
                               timeout=15, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        return path

    # ------------------------------------------------------------ modals
    def arm_modal_watchdog(self, policy: Callable | None = None,
                           period_ms: int = 300) -> None:
        """Answer modal dialogs by ``policy(dialog) -> button|None``; every
        answer is RECORDED in ``modals_answered`` so a run can never pass as
        unassisted when a window was clicked away. Default policy: Cancel /
        Close / No — the button that changes nothing."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import (QAbstractButton, QDialogButtonBox,
                                     QMessageBox)

        def _default(dlg):
            if isinstance(dlg, QMessageBox):
                for role in (QMessageBox.ButtonRole.RejectRole,
                             QMessageBox.ButtonRole.NoRole):
                    for b in dlg.buttons():
                        if dlg.buttonRole(b) == role:
                            return b
                return dlg.buttons()[-1] if dlg.buttons() else None
            for box in dlg.findChildren(QDialogButtonBox):
                for b in box.buttons():
                    if box.buttonRole(b) in (
                            QDialogButtonBox.ButtonRole.RejectRole,):
                        return b
            # Plain QDialogs with hand-made buttons (the "profile built"
            # window is one): prefer the button that changes nothing.
            from PyQt6.QtWidgets import QPushButton
            btns = [b for b in dlg.findChildren(QPushButton)
                    if b.isVisible() and b.isEnabled()]
            for want in ("cancel", "done", "close", "no", "ok"):
                for b in btns:
                    if b.text().strip().lower().rstrip(".…") == want:
                        return b
            return btns[-1] if btns else None

        pol = policy or _default

        def _tick():
            dlg = self.app.activeModalWidget()
            if dlg is None:
                return
            btn = pol(dlg)
            if isinstance(btn, QAbstractButton):
                self.modals_answered.append(
                    (dlg.windowTitle(), btn.text()))
                print(f"  [modal] '{dlg.windowTitle()}' -> '{btn.text()}'",
                      flush=True)
                btn.click()

        t = QTimer()
        t.timeout.connect(_tick)
        t.start(period_ms)
        self._modal_timer = t

    def disarm_modal_watchdog(self) -> None:
        if self._modal_timer is not None:
            self._modal_timer.stop()
            self._modal_timer = None

    # ------------------------------------------------------------ teardown
    def close(self) -> None:
        self.disarm_modal_watchdog()
        if self.win is not None:
            self.win.close()
            self.pump(300)


def fresh_sandbox(prefix: str = "engine-challenge-") -> Path:
    base = Path.home() / "Desktop" / "ChromIQ-engine-challenge" / "sandboxes"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=base))
