#!/usr/bin/env python3
"""P1 - on-screen reproduction: does the build output pane fight the reader?

A user verifying a profile, beta 4, 2026-09-11:

    "if you scroll up the output pane while its calculating, it forces it back
     down to the bottom every time the % goes up."

This drives the REAL ChromIQ window, on screen, against a sandboxed settings
file, a sandboxed presets folder and a sandboxed working folder, runs a REAL
``colprof`` build on a real ``.ti3``, scrolls the Build Profile tab's output
pane to the TOP while the build is running, and then samples the pane's scroll
bar until the build finishes.

What it records, per sample: the scroll bar's value, its maximum, the block
count of the document, and whether an append happened since the last sample.
A pane that "fights you" shows value == maximum on every sample after an
append; a pane that leaves the view alone keeps the value the driver parked it
at.

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-printpath.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-printpath-presets
    python proof_printpath/drive_p1_output_pane_scroll.py --out DIR --tag before
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

WORK = Path("/tmp/chromiq-printpath-work")
PROJECT = "Demo-Report-Matrix"
SRC = ROOT / "demo-projects" / PROJECT

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def install_modal_watchdog(app):
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        modals.append({"title": title, "text": text[:400]})
        print(f"    !! modal: {title!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(300)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def run_one(app, tab, log, sb, *, park_at_top: bool, icc: Path) -> dict:
    """One real colprof build, with the view parked where the caller says."""
    if icc.exists():
        icc.unlink()
    log.clear()
    pump(app, 300)
    state = {"blocks": log.blockCount(), "t0": time.time(),
             "parked": False, "park_t": None, "park_value": None}
    samples: list[dict] = []

    def sample(note: str = "") -> None:
        b = log.blockCount()
        samples.append({
            "t": round(time.time() - state["t0"], 3),
            "value": sb.value(), "maximum": sb.maximum(),
            "blocks": b, "appended": b != state["blocks"], "note": note,
        })
        state["blocks"] = b

    tab._build_btn.click()
    pump(app, 150)
    deadline = time.time() + 180
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
        sample()
        if park_at_top and not state["parked"] and sb.maximum() > 3:
            sb.setValue(0)
            app.processEvents()
            state["parked"] = True
            state["park_t"] = samples[-1]["t"]
            state["park_value"] = sb.value()
            sample("PARKED AT TOP")
            print(f"    parked at the top: value={sb.value()} "
                  f"max={sb.maximum()}")
        done = (not tab._runner.is_running and tab._build_btn.isEnabled()
                and len(samples) > 20)
        if done and (state["parked"] or not park_at_top):
            break
    pump(app, 900)
    sample("BUILD FINISHED")

    park_t = state["park_t"] if state["park_t"] is not None else -1.0
    after = [s for s in samples if s["t"] > park_t and s["note"] == ""]
    appends_after = sum(1 for s in after if s["appended"])
    at_bottom_after = sum(1 for s in after
                          if s["maximum"] > 0 and s["value"] >= s["maximum"])
    return {
        "park_at_top": park_at_top,
        "parked": state["parked"],
        "park_value_right_after_parking": state["park_value"],
        "samples": samples,
        "appends_after_park": appends_after,
        "samples_after_park": len(after),
        "samples_at_bottom_after_park": at_bottom_after,
        "final_value": sb.value(),
        "final_maximum": sb.maximum(),
        "final_blocks": log.blockCount(),
        "icc_written": icc.exists(),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-printpath-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"tag": tag, "screen_locked": locked, "modals": modals}
    print(f"00 screen locked: {locked}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}")

    dst = WORK / PROJECT
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)
    ti3 = dst / "runs" / "run1" / f"{PROJECT}.ti3"
    assert ti3.exists(), ti3
    icc = ti3.with_suffix(".icc")
    print(f"00 staged {dst}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    pump(app, 1500)
    install_modal_watchdog(app)

    tab = win._tab_profile
    win._tabs.setCurrentWidget(tab)
    pump(app, 800)

    tab.set_ti3_path(ti3)
    pump(app, 900)
    res["ti3_on_tab"] = str(getattr(tab, "_ti3_path", ""))

    log = tab._log
    sb = log.verticalScrollBar()
    res["log_object_name"] = log.objectName()
    res["log_class"] = type(log).__name__
    print(f"01 pane class {res['log_class']!r} objectName "
          f"{res['log_object_name']!r}")

    print("02 build 1 - the reader scrolls to the TOP mid-build")
    res["parked_at_top"] = run_one(app, tab, log, sb,
                                   park_at_top=True, icc=icc)
    a = res["parked_at_top"]
    print(f"    {a['appends_after_park']} appends after parking; "
          f"{a['samples_at_bottom_after_park']}/{a['samples_after_park']} "
          f"samples sat at the bottom; final value={a['final_value']} "
          f"max={a['final_maximum']}")

    ok, why = capture_window(win, out / f"{tag}_parked_at_top.png")
    res["capture_parked_ok"] = ok
    res["capture_parked_why_not"] = why
    print(f"    capture: {ok} {why}")

    print("03 build 2 - the reader leaves the view AT THE BOTTOM")
    res["left_at_bottom"] = run_one(app, tab, log, sb,
                                    park_at_top=False, icc=icc)
    b = res["left_at_bottom"]
    print(f"    final value={b['final_value']} max={b['final_maximum']}")

    res["pane_fought_the_reader"] = bool(
        a["parked"] and a["appends_after_park"] > 0
        and a["final_maximum"] > 0
        and a["final_value"] >= a["final_maximum"])
    res["followed_the_tail_when_at_bottom"] = bool(
        b["final_maximum"] > 0 and b["final_value"] >= b["final_maximum"])
    print(f"04 VERDICT pane_fought_the_reader = "
          f"{res['pane_fought_the_reader']}")
    print(f"04 VERDICT followed_the_tail_when_at_bottom = "
          f"{res['followed_the_tail_when_at_bottom']}")

    ok, why = capture_window(win, out / f"{tag}_left_at_bottom.png")
    res["capture_bottom_ok"] = ok
    res["capture_bottom_why_not"] = why

    (out / f"{tag}_p1_result.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")
    print(f"05 wrote {out / (tag + '_p1_result.json')}")

    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
