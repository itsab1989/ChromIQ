#!/usr/bin/env python3
"""AGENT DF: does Tools ▸ Build profile with scanner or camera sit still?

Basti, beta 9:

    *"when switching the radio for 'create profile using' the window's size
    changes sometimes a bit, things jump around a bit."*

This opens the real window on the real screen, drags it to a height a user
would actually have, presses the radio, and photographs the result. It prints
the pixel figures alongside, so the picture and the number come from the same
run.

SANDBOX THE SETTINGS FIRST. This builds a real `AppSettings`, which IS the
user's preferences store:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-df.ini
    python scripts/drive_scanner_window_steadiness.py <tag> [language]

`<tag>` names the run ("before" / "after") and prefixes every file it writes.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

assert os.environ.get("CHROMIQ_SETTINGS_FILE"), \
    "SANDBOX THE SETTINGS FIRST: export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-df.ini"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TAG = sys.argv[1] if len(sys.argv) > 1 else "after"
LANG = sys.argv[2] if len(sys.argv) > 2 else "en"
OUT = Path("/Users/Basti/Desktop/beta 9/scanner-window-steadiness")
OUT.mkdir(parents=True, exist_ok=True)

try:                                   # same import order main.py uses
    import PyQt6.QtWebEngineWidgets    # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QRect, Qt                             # noqa: E402
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap       # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from main import WinButtonLayoutStyle                          # noqa: E402
app.setStyle(WinButtonLayoutStyle("Fusion"))                   # what ships

from core.i18n import set_language, current_language           # noqa: E402
set_language(LANG)
assert current_language() == LANG, f"the {LANG!r} catalogue did not load"

LOG: list[str] = []


def say(s: str = "") -> None:
    print(s, flush=True)
    LOG.append(str(s))


def settle(seconds: float = 0.6) -> None:
    app.processEvents()
    time.sleep(seconds)
    app.processEvents()


from core.settings import AppSettings                          # noqa: E402
from core.argyll_runner import ArgyllRunner                    # noqa: E402

settings = AppSettings()
say(f"settings store   : {settings._qs.fileName()}")
assert "chromiq-df" in settings._qs.fileName(), "NOT SANDBOXED - stopping"

from ui.theme import apply_appearance                          # noqa: E402
apply_appearance(app, settings, settings.get("appearance", "auto"))

from ui.dialogs.scanin_dialog import ScannerProfileDialog      # noqa: E402

runner = ArgyllRunner(settings)
dlg = ScannerProfileDialog(runner, settings)
dlg.show()
dlg.raise_()
dlg.activateWindow()
settle(1.4)

WINDOW_H = 700          # a user who has made the window shorter than it opens


def pane_shot(name: str) -> Path:
    """The SETTINGS AREA only, which is where both faults live.

    The scroll bar is left at the top in every shot, so a y read off the
    picture is the same y this script prints. A shot that scrolled would be a
    different picture of a window that had not moved.
    """
    dlg.raise_()
    dlg.activateWindow()
    dlg._scroll.verticalScrollBar().setValue(0)
    settle(0.8)
    vp = dlg._scroll.viewport()
    pix = dlg.grab(QRect(vp.mapTo(dlg, vp.rect().topLeft()), vp.size()))
    path = OUT / f"{TAG}-{LANG}-{name}.png"
    pix.save(str(path))
    say(f"   [screenshot] {path.name}  {pix.width()}x{pix.height()}")
    return path


def whole_shot(name: str) -> Path:
    dlg.raise_()
    dlg.activateWindow()
    settle(0.8)
    path = OUT / f"{TAG}-{LANG}-{name}.png"
    dlg.grab().save(str(path))
    say(f"   [screenshot] {path.name}")
    return path


def anchors() -> dict:
    content = dlg._scroll.widget()
    out = {}
    for label, w in (("source radio 1", dlg._mode_chromiq),
                     ("source radio 2", dlg._mode_standard),
                     ("scenario radio 1",
                      list(dlg._scenario_radios.values())[0]),
                     ("scenario radio 3",
                      list(dlg._scenario_radios.values())[2])):
        out[label] = w.mapTo(content, w.rect().topLeft()).y()
    return out


say("=" * 74)
say(f"AGENT DF - scanner window steadiness, run {TAG!r}, language {LANG!r}")
say("=" * 74)
say(f"window opens at  : {dlg.width()} x {dlg.height()}, floor "
    f"{dlg.minimumWidth()} x {dlg.minimumHeight()}")
say(f"left pane width  : {dlg._left_pane_w.width()}")

# ---------------------------------------------------------------------------
# PART ONE: the controls, at the height the window OPENS at, so the whole
# settings area is in frame and a reader can see what moves.
# ---------------------------------------------------------------------------
dlg._mode_chromiq.setChecked(True)
dlg._printer_cb.setChecked(False)
settle(1.0)
open_h = dlg.height()
say("")
say(f"PART ONE, at the height the window opens at ({open_h} px)")
p1_was = anchors()
for k, v in p1_was.items():
    say(f"   {k:<18} y={v}")
pane_shot("11-tall-source-chart")
dlg._mode_standard.setChecked(True)
settle(1.2)
p1_now = anchors()
say("   after clicking 'A standard target I own':")
for k, v in p1_now.items():
    say(f"   {k:<18} y={v}   ({v - p1_was[k]:+d} px)")
pane_shot("12-tall-source-standard")
dlg._mode_chromiq.setChecked(True)
settle(0.8)

# ---------------------------------------------------------------------------
# PART TWO: the window itself, from a height a user has chosen.
# ---------------------------------------------------------------------------
dlg.resize(dlg.width(), WINDOW_H)
settle(1.0)

was_h, was = dlg.height(), anchors()
say("")
say(f"A. 'A chart I made in ChromIQ', window dragged to {WINDOW_H} px")
say(f"   window height {was_h}")
for k, v in was.items():
    say(f"   {k:<18} y={v}")
pane_shot("01-source-chart")
whole_shot("01w-source-chart")

dlg._mode_standard.setChecked(True)
settle(1.2)
now_h, now = dlg.height(), anchors()
say("")
say("B. after clicking 'A standard target I own (IT8, ColorChecker…)'")
say(f"   window height {now_h}   ({now_h - was_h:+d} px)")
for k, v in now.items():
    say(f"   {k:<18} y={v}   ({v - was[k]:+d} px)")
pane_shot("02-source-standard")
whole_shot("02w-source-standard")

# …and back, so a reader can see it is not a one-way settle.
dlg._mode_chromiq.setChecked(True)
settle(1.0)
back_h, back = dlg.height(), anchors()
say("")
say("C. back to 'A chart I made in ChromIQ'")
say(f"   window height {back_h}   ({back_h - was_h:+d} px against A)")
for k, v in back.items():
    say(f"   {k:<18} y={v}   ({v - was[k]:+d} px against A)")

# The usage-scenario radios, the other group.
keys = list(dlg._scenario_radios)
dlg._scenario_radios[keys[0]].setChecked(True)
settle(1.0)
s_was_h, s_was = dlg.height(), anchors()
pane_shot("03-scenario-everyday")
dlg._scenario_radios[keys[2]].setChecked(True)
settle(1.2)
s_now_h, s_now = dlg.height(), anchors()
say("")
say("D. usage scenario: everyday -> 'A profile for my printer'")
say(f"   window height {s_was_h} -> {s_now_h}   ({s_now_h - s_was_h:+d} px)")
for k, v in s_now.items():
    say(f"   {k:<18} y={v}   ({v - s_was[k]:+d} px)")
pane_shot("04-scenario-printer")

dlg._scenario_radios[keys[0]].setChecked(True)
settle(0.8)

say("")
say("VERDICT")
moved = [f"{k} {was[k]}->{now[k]}" for k in was if was[k] != now[k]]
say(f"  source radio click : window {now_h - was_h:+d} px, "
    + ("controls steady" if not moved else "MOVED " + "; ".join(moved)))
p1moved = [f"{k} {p1_was[k]}->{p1_now[k]}"
           for k in p1_was if p1_was[k] != p1_now[k]]
say(f"  at the opening height: "
    + ("controls steady" if not p1moved else "MOVED " + "; ".join(p1moved)))
smoved = [f"{k} {s_was[k]}->{s_now[k]}" for k in s_was if s_was[k] != s_now[k]]
say(f"  scenario click     : window {s_now_h - s_was_h:+d} px, "
    + ("controls steady" if not smoved else "MOVED " + "; ".join(smoved)))

(OUT / f"{TAG}-{LANG}-log.txt").write_text("\n".join(LOG) + "\n",
                                           encoding="utf-8")
say("")
say(f"log written to {OUT / f'{TAG}-{LANG}-log.txt'}")
dlg.close()
