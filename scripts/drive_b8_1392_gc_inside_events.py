#!/usr/bin/env python3
"""B8-1392: does the APP collect garbage inside Qt's event delivery, and can
that crash it? ON SCREEN, real window, the app built as `main()` builds it.

    python scripts/drive_b8_1392_gc_inside_events.py OUT_DIR [--unguarded] [--rounds N]

Each round does what a person does with the Create Chart presets: opens the
"Select preset" pulldown and closes it, opens the Built-in presets list and
closes it, and applies a built-in preset (a new project name each time, so no
question is asked). Meanwhile every garbage collection is recorded: which
thread ran it, how many widgets it deleted, and whether it ran INSIDE Qt's
delivery of an event (an event filter or an event handler on the Python stack
when it started), which is the condition that crashed the gate.

``--unguarded`` puts CPython's automatic collector back (as the app was at
abc852a2) with a low threshold, so collections happen as often as a busy
session makes them. Without it the app runs as shipped after B8-1392.

Sandbox: userdrive's (settings, presets, output folder; the ISO file forced to
the repo's). A watchdog ends the process after --timeout seconds.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

_TREE = Path(os.environ.get("CHROMIQ_TREE")
             or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(_TREE / "scripts"))
sys.path.insert(0, str(_TREE))

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--unguarded", action="store_true")
ap.add_argument("--rounds", type=int, default=40)
ap.add_argument("--timeout", type=int, default=900)
ARGS = ap.parse_args()
OUT = Path(ARGS.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(OUT / "sandbox" / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(OUT / "sandbox" / "presets")
(OUT / "sandbox" / "presets").mkdir(parents=True, exist_ok=True)


def _watchdog():
    time.sleep(ARGS.timeout)
    (OUT / "WATCHDOG.txt").write_text(
        f"the drive did not finish in {ARGS.timeout} s\n", encoding="utf-8")
    os._exit(3)


threading.Thread(target=_watchdog, daemon=True).start()

from userdrive import Drive                                   # noqa: E402

STATS = {"collections": 0, "collections_off_gui_thread": 0,
         "collections_inside_event_delivery": 0,
         "widgets_deleted_inside_event_delivery": 0,
         "widgets_deleted_total": 0, "examples": []}
_START = {}
_HANDLERS = ("eventFilter", "event", "timerEvent", "paintEvent",
             "resizeEvent", "showEvent", "hideEvent", "mousePressEvent",
             "mouseReleaseEvent", "keyPressEvent", "changeEvent",
             "enterEvent", "leaveEvent", "moveEvent")


def _inside_event_delivery() -> str:
    """The name of the Python event handler on the stack, or ''."""
    try:
        f = sys._getframe(1)
    except ValueError:
        return ""
    while f is not None:
        if f.f_code.co_name in _HANDLERS and "self" in f.f_locals:
            return f"{type(f.f_locals['self']).__name__}.{f.f_code.co_name}"
        f = f.f_back
    return ""


def _gc_cb(phase, info):
    try:
        from PyQt6.QtWidgets import QApplication
        if phase == "start":
            _START["n"] = len(QApplication.allWidgets()) \
                if threading.current_thread() is threading.main_thread() else None
            _START["where"] = _inside_event_delivery()
            return
        STATS["collections"] += 1
        if threading.current_thread() is not threading.main_thread():
            STATS["collections_off_gui_thread"] += 1
            return
        before = _START.get("n")
        after = len(QApplication.allWidgets())
        gone = max(0, (before or after) - after)
        STATS["widgets_deleted_total"] += gone
        where = _START.get("where")
        if where:
            STATS["collections_inside_event_delivery"] += 1
            STATS["widgets_deleted_inside_event_delivery"] += gone
            if gone and len(STATS["examples"]) < 10:
                STATS["examples"].append(
                    {"handler": where, "widgets_deleted": gone,
                     "collected": info.get("collected")})
    except Exception:                                         # noqa: BLE001
        pass


def script(d):
    from PyQt6.QtWidgets import QApplication
    from core import gc_guard
    rec = d.record
    rec["mode"] = "ON SCREEN"
    rec["collector"] = ("UNGUARDED: CPython's automatic collector, threshold "
                        "200" if ARGS.unguarded else
                        "as shipped: GUI thread's collector (core/gc_guard.py)")
    if ARGS.unguarded:
        coll = getattr(gc_guard, "_COLLECTOR", None)
        if coll is not None:
            coll.timer.stop()
        gc.enable()
        gc.set_threshold(200, 10, 10)
    rec["gc_enabled_at_start"] = gc.isenabled()
    rec["collector_installed"] = gc_guard.installed()
    gc.callbacks.append(_gc_cb)
    d.goto_tab("chart")
    yield 1500
    tab = d.win._tab_chart
    tab._manual_btn.click()
    yield 1200
    d.shot(d.win, "00-create-chart-manual")
    cb = tab._preset_combo
    keys = ["__chromiq_abw702_builtin__", "__chromiq_tc918_builtin__",
            "__chromiq_munki324_builtin__", "__chromiq_abw702_builtin__"]
    keys = [k for k in keys if cb.findData(k) >= 0] or [cb.itemData(1)]
    rec["keys"] = keys
    rec["rounds"] = []
    t0 = time.monotonic()
    for i in range(ARGS.rounds):
        modal = QApplication.activeModalWidget()
        if modal is not None:
            d.note(f"round {i}: a modal was open ({type(modal).__name__}: "
                   f"{modal.windowTitle()!r}), rejected")
            modal.reject() if hasattr(modal, "reject") else modal.close()
            yield 400
        cb.showPopup()
        yield 350
        if i == 0:
            d.shot(cb.view(), "01-pulldown-open")
        cb.hidePopup()
        yield 150
        btn = tab._builtin_preset_btn
        btn.click()
        yield 350
        pop = getattr(tab, "_builtin_preset_popup", None)
        if i == 0 and pop is not None and pop.isVisible():
            d.shot(pop, "02-builtin-list-open")
        if pop is not None:
            pop.close()
        yield 150
        key = keys[i % len(keys)]
        ok = tab._apply_prebuilt_preset(key, f"GC-Drive-{i:03d}")
        yield 900
        rec["rounds"].append({"i": i, "key": key, "applied": bool(ok),
                              "t": round(time.monotonic() - t0, 1),
                              "widgets": len(QApplication.allWidgets())})
        if i % 10 == 0:
            d.note(f"round {i}: {key} applied={ok} "
                   f"widgets={len(QApplication.allWidgets())} "
                   f"gc={json.dumps({k: v for k, v in STATS.items() if k != 'examples'})}")
    d.shot(d.win, "03-after-all-rounds")
    gc.callbacks.remove(_gc_cb)
    rec["gc"] = STATS
    rec["survived"] = True
    d.note(f"SURVIVED {ARGS.rounds} rounds; gc: {json.dumps(STATS)}")
    (OUT / "gc-stats.json").write_text(json.dumps(STATS, indent=2),
                                       encoding="utf-8")


if __name__ == "__main__":
    import faulthandler
    faulthandler.enable(open(OUT / "faulthandler.txt", "w", encoding="utf-8"),
                        all_threads=True)
    try:
        d = Drive(OUT)
        rc = d.run(script)
    except Exception:                                         # noqa: BLE001
        (OUT / "DRIVER-ERROR.txt").write_text(traceback.format_exc(),
                                              encoding="utf-8")
        rc = 2
    os._exit(rc)
