#!/usr/bin/env python3
"""Knut's beta-2 hang, driven ON SCREEN in the real window (#182 6144104040).

Knut: after loading a project, switching the run type from profiling to
verification, or switching runs while in verification, ChromIQ 4.3.5-beta.2
hung for good. A fork on the window's thread waited on OpenBLAS while the
gamut-reach thread multiplied (core/blas_threads.py).

This driver loads a copy of a demo project with two profiled runs, then turns
the bar's own combo boxes: Profiling -> Verification, run1 <-> run2 in
verification, back to Profiling, over and over, on the Create Chart and Print
Chart tabs in turn. Every turn forgets the gamut reach the app has already
worked out (the tab's memo and gamut_target's caches), so each verification
choice starts the background question again, as a fresh profile does.

A hang cannot report itself, so faulthandler is armed for every turn: if a
turn takes longer than HANG_S the stacks of every thread go to
``<out>/hang-stacks.txt`` and the process exits 3.

    CHROMIQ_SETTINGS_FILE=<out>/settings.ini CHROMIQ_PRESETS_DIR=<out>/presets \\
    CHROMIQ_LOG_DIR=<out>/logs \\
        python scripts/drive_b3_run_type_switch_never_hangs.py <out> <turns> \\
            [--tree <repo>]

``--tree`` imports ChromIQ from another checkout (the before run). To drive
the numpy ChromIQ ships on macOS (OpenBLAS), put that numpy first on
PYTHONPATH; the development venv's numpy uses Accelerate and cannot hang.
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
import shutil
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("turns", type=int)
ap.add_argument("--tree", default=None)
ap.add_argument("--pause-ms", type=int, default=250)
ap.add_argument("--demo", default=None, help="the Demo-Full-RGB folder to copy")
args = ap.parse_args()

ROOT = Path(args.tree or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
OUT = Path(args.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "sandbox the settings first"
assert os.environ.get("CHROMIQ_PRESETS_DIR"), "sandbox the presets first"
assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"

# As main.py does, first: the tree decides whether OpenBLAS is pinned.
try:
    from core.blas_threads import pin_blas_threads
    pinned = pin_blas_threads()
except ImportError:
    pinned = None                      # a tree from before the fix

HANG_S = 90
PAUSE_MS = args.pause_ms
hang_file = open(OUT / "hang-stacks.txt", "w", encoding="utf-8")  # noqa: SIM115

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from capture_screens import build_app  # noqa: E402

app = build_app()
from core.settings import AppSettings  # noqa: E402
from ui.theme import apply_appearance  # noqa: E402

settings = AppSettings()
work = OUT / "projects"
if work.exists():
    shutil.rmtree(work)
work.mkdir(parents=True)
demo = Path(args.demo) if args.demo else None
if demo is None:
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    demo = sorted(cache.glob("*/Demo-Full-RGB"),
                  key=lambda p: p.stat().st_mtime)[-1]
shutil.copytree(demo, work / demo.name)
settings.set("custom_output_path", str(work))
settings.set("argyll_bin_path", "/Applications/Argyll/bin")
settings.set("restore_last_session", False)
settings.set("language", "en")
settings.set("appearance", "dark")
assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
apply_appearance(app, None, "dark")

QDialog.exec = lambda self: 1                     # type: ignore[assignment]
for m in ("warning", "critical", "information", "question"):
    setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore


def pump(ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


from ui.main_window import MainWindow  # noqa: E402

win = MainWindow(settings)
win.resize(1280, 800)
win.show()
app._chromiq_focus_give_back.give_back()
pump(2500)
win._file_mgr.set_target_name(demo.name)
win._target_bar.refresh()
pump(1500)

from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from workflow import gamut_target  # noqa: E402

bar = win._target_bar


def choose(combo, data) -> bool:
    for i in range(combo.count()):
        if combo.itemData(i) == data and combo.model().item(i).isEnabled():
            combo.setCurrentIndex(i)          # the slot a click reaches
            return True
    return False


def runs() -> list:
    # the run ids only: the last item ("\0new") makes a new run
    return [d for d in (bar._run_combo.itemData(i)
                        for i in range(bar._run_combo.count()))
            if isinstance(d, str) and not d.startswith("\0")]


record = {"tree": str(ROOT), "pinned": pinned, "mode": "ON SCREEN",
          "blas_threads": None, "turns_done": 0, "turns": args.turns,
          "runs": runs(), "reach_started": 0}
# Ask OpenBLAS with THIS checkout's probe, so the before tree is measured too.
import importlib.util  # noqa: E402

import numpy as np  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_probe", Path(__file__).resolve().parents[1] / "core" / "blas_threads.py")
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
np.ones((8, 8)) @ np.ones((8, 8))
record["blas_threads"] = _probe.blas_thread_count()
print(json.dumps(record), flush=True)

real_async = gamut_target.gamut_coverage_async


def counting_async(*a, **k):
    record["reach_started"] += 1
    return real_async(*a, **k)


gamut_target.gamut_coverage_async = counting_async
t0 = time.monotonic()
for turn in range(args.turns):
    faulthandler.dump_traceback_later(HANG_S, exit=True, file=hang_file)
    win._tabs.setCurrentIndex(turn % 2)          # Create Chart, Print Chart
    # forget every reach already worked out: each choice asks afresh
    win._tab_chart._gamut_coverage_cache.clear()
    gamut_target.clear_round_trip_cache()
    choose(bar._type_combo, RUN_TYPE_PROFILING)
    pump(300)
    rs = runs()
    choose(bar._run_combo, rs[turn % len(rs)])
    pump(200)
    choose(bar._type_combo, RUN_TYPE_VERIFICATION)
    pump(700)
    for r in rs + rs[::-1]:                       # switch runs in verification
        win._tab_chart._gamut_coverage_cache.clear()
        gamut_target.clear_round_trip_cache()
        choose(bar._run_combo, r)
        pump(PAUSE_MS)
    record["turns_done"] = turn + 1
    faulthandler.cancel_dump_traceback_later()
    if turn % 10 == 9:
        print(f"turn {turn + 1}: {time.monotonic() - t0:.0f} s", flush=True)

record["seconds"] = round(time.monotonic() - t0, 1)
try:
    from onscreen_capture import capture_window
    ok, why = capture_window(win, OUT / "after-the-turns.png")
    record["photo"] = str(OUT / "after-the-turns.png") if ok else why
except Exception as exc:                          # noqa: BLE001
    record["photo"] = repr(exc)
print("RESULT " + json.dumps(record), flush=True)
win.close()
pump(300)
os._exit(0)
