#!/usr/bin/env python3
r"""A11 — drive the real driver window ON SCREEN and read the certificate text.

    set CHROMIQ_SETTINGS_FILE=...  &&  python scripts\drive_a11_certificate_text.py

WHAT THIS DOES NOT DO: it never installs, removes or rebinds a driver, and it
never touches a certificate store. `install_winusb` and `launch_zadig` are
replaced with stubs that RAISE, so nothing here can reach the installer even by
accident, and `Install Driver` is never clicked. The only button this harness
presses is `What this changes…`, which opens a read-only window.

WHY IT STAGES A DEVICE. The instrument on this bench is bound to libusb0 and
works, so the branch the certificate disclosure lives in — "the driver is not
installed" — is unreachable from the real state. The staged device goes in
through `attached_devices()`, the real function, fed a faked registry read: the
same code path, different input. The real machine is still photographed first,
to show that a working user is shown no certificate paragraph at all.

DPI. Screenshots are `QWidget.grab()`, which renders through Qt at the widget's
own devicePixelRatio. A GDI `VirtualScreen` + `CopyFromScreen` capture returns
the top-left quarter at 200 % scaling and has already produced one withdrawn
finding on this machine. Each saved file's pixel size and dpr are printed so the
capture can be checked rather than trusted.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    sys.exit("refusing to run offscreen — the whole point is the real screen")
if not os.environ.get("CHROMIQ_SETTINGS_FILE"):
    sys.exit("set CHROMIQ_SETTINGS_FILE first (CLAUDE.md): a driver that does "
             "not is writing into the preferences the owner works in")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path(r"C:\Users\sebas\Desktop\windows-only\staging\A11_shots")
OUT.mkdir(parents=True, exist_ok=True)

from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,                # noqa: E402
                             QPushButton)

import core.usb_driver_installer as udi                            # noqa: E402
import core.resource_path as rp                                    # noqa: E402
from core import i18n                                              # noqa: E402


def _refuse(*a, **k):
    raise AssertionError("the driver harness tried to reach the installer")


udi.install_winusb = _refuse
udi.launch_zadig = _refuse


def _entry(vid, pid, instance, service):
    return (f"VID_{vid.upper()}&PID_{pid.upper()}", [(instance, service)])


def _staged(service: str):
    entries = [_entry("0765", "6008", "7&3b74c78&0&1", service)]
    present = {r"USB\VID_0765&PID_6008\7&3B74C78&0&1"}
    return udi.attached_devices(entries, present)


def _shot(widget, name: str):
    pm = widget.grab()
    dpr = pm.devicePixelRatio() or 1.0
    path = OUT / f"{name}.png"
    ok = pm.save(str(path))
    print(f"  {'ok ' if ok else 'FAIL'} {path.name:<38} "
          f"{pm.width()}x{pm.height()} px  dpr={dpr}  "
          f"logical={widget.width()}x{widget.height()}")
    if dpr < 1.5:
        print("       ! dpr below 1.5 — is this really the 200 % display?")
    return pm


def _clipped(widget) -> "list[str]":
    """Every button in *widget* whose width is less than it asks for.

    The reason the shots are taken at all: a long disclosure in twelve
    languages can only fail by clipping, and a screenshot proves nothing if
    nobody measures it.
    """
    bad = []
    for b in widget.findChildren(QPushButton):
        if b.isVisible() and b.width() < b.sizeHint().width():
            bad.append(f"{b.text()!r} {b.width()}px wants "
                       f"{b.sizeHint().width()}px")
    return bad


class Walk:
    """Photograph each modal as it appears and act on it, in a fixed script.

    Each step is ``(shot_name_or_None, action)`` where action is ``"cert"``
    (press the certificate button) or ``"close"``.
    """

    def __init__(self, *steps):
        self.steps = list(steps)
        # STRONG references, not ids. `_show_usb_installer` is a `while True:`
        # that DESTROYS its dialog and builds a new one each pass, and CPython
        # hands the new object the address the old one just freed — so an
        # id()-keyed "already seen" set marks the REBUILT window as seen, never
        # acts on it, and the harness sits in front of an open modal for ever.
        # Measured: the first run of this script hung exactly there, after the
        # certificate notice closed and the driver window came back. Holding
        # the widget alive makes id reuse impossible.
        self._seen: "list" = []
        self.notes: "list[str]" = []
        self.t = QTimer()
        self.t.setInterval(120)
        self.t.timeout.connect(self._tick)
        self.ticks = 0

    def _tick(self):
        self.ticks += 1
        w = QApplication.activeModalWidget()
        if w is None:
            if self.ticks > 250:
                self.t.stop()
            return
        if any(s is w for s in self._seen):
            return
        self._seen.append(w)
        QApplication.processEvents()
        if not self.steps:
            w.done(0) if isinstance(w, QDialog) else w.close()
            return
        name, action = self.steps.pop(0)
        if name:
            _shot(w, name)
            for bad in _clipped(w):
                self.notes.append(f"CLIPPED in {name}: {bad}")
        if action == "cert":
            want = i18n.tr("What this changes…")
            hit = [b for b in w.findChildren(QPushButton) if b.text() == want]
            if not hit:
                self.notes.append(
                    f"NO CERT BUTTON in {name}: "
                    f"{[b.text() for b in w.findChildren(QPushButton)]}")
                w.done(0)
                return
            self.notes.append(f"pressed {hit[0].text()!r}")
            hit[0].click()
            return
        w.done(0) if isinstance(w, QDialog) else w.close()


class _Settings:
    def __init__(self):
        from core.settings import DEFAULTS
        self._s = dict(DEFAULTS)

    def get(self, k, d=None):
        return self._s.get(k, d)

    def set(self, k, v):
        self._s[k] = v

    def migrate(self):
        pass

    def reset_to_defaults(self):
        pass


def run(lang: str) -> "list[str]":
    i18n.set_language(lang)
    from ui.dialogs.settings_dialog import SettingsDialog

    dlg = SettingsDialog(_Settings())
    dlg.show()
    QApplication.processEvents()
    notes: "list[str]" = []
    print(f"\n=== {lang} ===")

    # 1. THE REAL MACHINE, READ ONLY. Bound to libusb0, so nothing is about to
    #    be installed and the certificate paragraph must NOT appear.
    real = udi.enumerate_connected()
    print(f"  real enumerate_connected(): "
          f"{[(d.name, d.has_winusb) for d in real]}")
    w = Walk((f"01-real-installed-{lang}", "close"))
    w.t.start()
    dlg._show_usb_installer()
    w.t.stop()
    notes += w.notes

    # 2. THE DISCLOSURE, with wdi-simple present: the install paragraph, the
    #    certificate paragraph under it, and both buttons.
    staged = _staged("WinUSB")
    print(f"  staged WinUSB -> has_winusb={[d.has_winusb for d in staged]}")
    udi.enumerate_connected = lambda: staged
    rp.resource_path = lambda p: (Path(__file__)
                                  if "wdi_simple" in p else Path("/nonexistent"))
    w = Walk((f"02-install-with-certificate-{lang}", "cert"),
             (f"03-certificate-notice-{lang}", "close"),
             (None, "close"))
    w.t.start()
    dlg._show_usb_installer()
    w.t.stop()
    notes += w.notes

    # 3. …and WITHOUT wdi-simple: the Zadig steps, which install the same
    #    certificate through libwdi's own front end and must disclose it too.
    rp.resource_path = lambda p: Path("/nonexistent")
    w = Walk((f"04-zadig-with-certificate-{lang}", "cert"),
             (f"05-certificate-notice-from-zadig-{lang}", "close"),
             (None, "close"))
    w.t.start()
    dlg._show_usb_installer()
    w.t.stop()
    notes += w.notes

    dlg.close()
    QApplication.processEvents()
    return notes


def _app_as_shipped():
    """The QApplication `main()` builds, not a bare one — CLAUDE.md's rule."""
    from PyQt6.QtGui import QFontDatabase
    from core.resource_path import resource_path as _rp0
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import CompositeAppFilter

    app = QApplication.instance() or QApplication(sys.argv)
    try:
        for f in _rp0("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(f))
    except Exception:
        pass
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app._a11_filter = CompositeAppFilter(app)
    app.installEventFilter(app._a11_filter)
    return app


def main() -> int:
    app = _app_as_shipped()
    print(f"style={app.style().objectName()!r}")
    scr = app.primaryScreen()
    print(f"screen {scr.size().width()}x{scr.size().height()} "
          f"dpr={scr.devicePixelRatio()}  platform={app.platformName()}")
    fresh_enum = udi.enumerate_connected
    fresh_rp = rp.resource_path
    notes: "list[str]" = []
    for lang in (os.environ.get("A11_LANGS") or "en,de").split(","):
        udi.enumerate_connected = fresh_enum
        rp.resource_path = fresh_rp
        notes += [f"[{lang}] {n}" for n in run(lang.strip())]
    print("\n--- notes ---")
    for n in notes:
        print(" ", n)
    bad = [n for n in notes if "CLIPPED" in n or "NO CERT BUTTON" in n]
    print(f"\n{'FAIL' if bad else 'ok'}: {len(bad)} clipping/wiring problems")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
