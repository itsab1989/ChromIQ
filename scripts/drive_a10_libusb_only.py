#!/usr/bin/env python3
r"""A10 — drive the real driver window ON SCREEN and photograph what it says.

    set CHROMIQ_SETTINGS_FILE=...  &&  python scripts\drive_a10_libusb_only.py

WHAT THIS DOES NOT DO: it never installs, removes or rebinds a driver.
`install_winusb` and `launch_zadig` are replaced with stubs that RAISE, so
nothing here can reach the installer even by accident, and no button that would
start one is ever clicked. The one shot taken against the real machine
(`01-real-*`) only READS the registry, through the same `enumerate_connected()`
the app uses.

WHY IT STAGES A DEVICE FOR MOST SHOTS. The instrument on this bench is bound to
libusb0 and works, so the branches this change is about — "the driver is not
installed", the Zadig steps, the two Zadig outcomes — are unreachable from the
real state. The staged devices go in through `attached_devices()`, the real
function, fed a faked registry read: the same code path, different input.

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

OUT = Path(r"C:\Users\sebas\Desktop\windows-only\staging\A10_shots")
OUT.mkdir(parents=True, exist_ok=True)

from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog                  # noqa: E402

import core.usb_driver_installer as udi                            # noqa: E402
import core.resource_path as rp                                    # noqa: E402
from core import i18n                                              # noqa: E402


# --- nothing here may touch a driver ---------------------------------------
def _refuse(*a, **k):
    raise AssertionError("the driver harness tried to reach the installer")


udi.install_winusb = _refuse
udi.launch_zadig = _refuse


def _entry(vid, pid, instance, service):
    return (f"VID_{vid.upper()}&PID_{pid.upper()}", [(instance, service)])


def _staged(service: str):
    """A staged i1Studio bound to *service*, through the real predicate."""
    entries = [_entry("0765", "6008", "7&3b74c78&0&1", service)]
    present = {r"USB\VID_0765&PID_6008\7&3B74C78&0&1"}
    return udi.attached_devices(entries, present)


def _shot(widget, name: str):
    pm = widget.grab()
    dpr = pm.devicePixelRatio() or 1.0
    path = OUT / f"{name}.png"
    ok = pm.save(str(path))
    print(f"  {'ok ' if ok else 'FAIL'} {path.name:<34} "
          f"{pm.width()}x{pm.height()} px  dpr={dpr}  "
          f"logical={widget.width()}x{widget.height()}")
    if dpr < 1.5:
        print("       ! dpr below 1.5 — is this really the 200 % display?")


class Grab:
    """Photograph each modal as it appears, then close it. Never clicks a
    button that could start anything."""

    def __init__(self, *names):
        self._names = list(names)
        self._seen = set()
        self.t = QTimer()
        self.t.setInterval(120)
        self.t.timeout.connect(self._tick)
        self.ticks = 0

    def _tick(self):
        self.ticks += 1
        w = QApplication.activeModalWidget()
        if w is None:
            if self.ticks > 200:
                self.t.stop()
            return
        if id(w) in self._seen:
            return
        self._seen.add(id(w))
        QApplication.processEvents()
        if self._names:
            _shot(w, self._names.pop(0))
        if isinstance(w, QDialog):
            w.done(0)
        else:
            w.close()


def _outcome_window(dlg, text, extra_button, name):
    """Photograph `_driver_notice` — the outcome window — without pressing
    anything that acts."""
    g = Grab(name)
    g.t.start()
    dlg._driver_notice("Driver Installation", text, extra_button)
    g.t.stop()


class _Settings:
    """A settings object that is never written back — the real preferences are
    also sandboxed by CHROMIQ_SETTINGS_FILE, so this is belt and braces."""

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


def run(lang: str) -> None:
    i18n.set_language(lang)
    from ui.dialogs.settings_dialog import (SettingsDialog, usb_install_outcome)

    dlg = SettingsDialog(_Settings())
    dlg.show()
    QApplication.processEvents()

    print(f"\n=== {lang} ===")

    # 1. THE REAL MACHINE, READ ONLY. The i1Studio on this bench is bound to
    #    libusb0, so the tightened predicate must still call it driven.
    real = udi.enumerate_connected()
    print(f"  real enumerate_connected(): "
          f"{[(d.name, d.has_winusb) for d in real]}")
    g = Grab(f"01-real-instrument-{lang}")
    g.t.start()
    dlg._show_usb_installer()
    g.t.stop()

    # 2. THE HEADLINE. A user who followed ChromIQ's OWN old Zadig
    #    instructions: service WinUSB, Argyll blind, and master said "✓".
    winusb = _staged("WinUSB")
    print(f"  staged WinUSB -> has_winusb={[d.has_winusb for d in winusb]}"
          "   (False is the fix)")
    udi.enumerate_connected = lambda: winusb
    rp.resource_path = lambda p: (Path(__file__)          # pretend wdi is here
                                  if "wdi_simple" in p else Path("/nonexistent"))
    g = Grab(f"02-winusb-user-{lang}")
    g.t.start()
    dlg._show_usb_installer()
    g.t.stop()

    # 3. The same device with no wdi-simple: the numbered Zadig steps.
    rp.resource_path = lambda p: Path("/nonexistent")
    g = Grab(f"03-zadig-steps-{lang}")
    g.t.start()
    dlg._show_usb_installer()
    g.t.stop()

    # 4 & 5. The two outcome windows that used to open Zadig in silence.
    text, offer = usb_install_outcome(
        wdi_available=True, ran_ok=True,
        still_unbound_names=["X-Rite i1 Studio"], zadig_status=None,
        driver_was_missing=True, target_names=["X-Rite i1 Studio"])
    _outcome_window(dlg, text, i18n.tr("Try Zadig") if offer else None,
                    f"04-did-not-bind-{lang}")

    text, offer = usb_install_outcome(
        wdi_available=True, ran_ok=False, still_unbound_names=[],
        zadig_status=None, driver_was_missing=True,
        target_names=["X-Rite i1 Studio"])
    _outcome_window(dlg, text, i18n.tr("Try Zadig") if offer else None,
                    f"05-install-failed-{lang}")

    dlg.close()
    QApplication.processEvents()


def _app_as_shipped():
    """The QApplication `main()` builds, not a bare one.

    CLAUDE.md's first rule about this suite: every size, rect and pixel comes
    out of the STYLE, and `main.py` paints through
    `WinButtonLayoutStyle("Fusion")` on every platform. A driver that skips
    that photographs QWindows11Style and proves something about a build nobody
    ships. The bundled fonts and the composite event filter go in for the same
    reason — `ButtonFontFilter` resizes button text, which is exactly what a
    screenshot of a button shows.
    """
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
    app._a10_filter = CompositeAppFilter(app)
    app.installEventFilter(app._a10_filter)
    return app


def main() -> int:
    app = _app_as_shipped()
    print(f"style={app.style().objectName()!r}")
    scr = app.primaryScreen()
    print(f"screen {scr.size().width()}x{scr.size().height()} "
          f"dpr={scr.devicePixelRatio()}  platform={app.platformName()}")
    fresh_enum = udi.enumerate_connected
    fresh_rp = rp.resource_path
    for lang in ("en", "de"):
        udi.enumerate_connected = fresh_enum
        rp.resource_path = fresh_rp
        run(lang)
    i18n.set_language("en")
    print(f"\nshots in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
