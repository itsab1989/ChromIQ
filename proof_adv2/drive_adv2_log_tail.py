#!/usr/bin/env python3
"""ON SCREEN: does the Create Chart output pane still drag a scrolled-up reader?

Round 3 (`b397ffbf`) gave nine log panes `TailFollowLog`, whose promise is
"the view follows the newest line only while it is already showing the newest
line".  This drives the REAL ChromIQ window, on screen, and asks the real
`TabChart._set_progress_line` the question the reporter asked:

    "if you scroll up the output pane while it's calculating, it forces it back
     down to the bottom every time the % goes up."

Sandbox the settings, the presets and the working folder before running.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase          # noqa: E402
from PyQt6.QtWidgets import QApplication       # noqa: E402

from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv2-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    work = Path(os.environ["CHROMIQ_ADV2_WORK"])
    work.mkdir(parents=True, exist_ok=True)

    res: dict = {"tag": tag, "screen_locked": session_is_locked(),
                 "mode": "on screen (cocoa), real MainWindow"}
    print("00 screen locked:", res["screen_locked"])

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    pump(app, 2000)

    tab = win._tab_chart
    win._tabs.setCurrentWidget(tab)
    pump(app, 900)

    log = tab._log
    sb = log.verticalScrollBar()

    # 1) The pane fills with output while the reader watches the tail, exactly
    #    as it does while a chart is being generated.
    for i in range(200):
        log.appendPlainText(f"Generating chart, step {i}")
    pump(app, 400)
    res["filled"] = {"value": sb.value(), "maximum": sb.maximum(),
                     "following": log.is_following_tail()}
    print("01 filled:", res["filled"])

    # 2) targen starts seeding, so the live percentage line appears.
    tab._progress_line_active = False
    tab._on_log_line("Added 10/1000")
    pump(app, 300)
    res["after_first_percentage"] = {
        "value": sb.value(), "maximum": sb.maximum(),
        "following": log.is_following_tail(),
        "last_line": log.toPlainText().rsplit("\n", 1)[-1]}
    print("02 first %:", res["after_first_percentage"])

    # 3) The reader scrolls up to read something further back.
    sb.setValue(0)
    pump(app, 400)
    res["reader_scrolled_up"] = {"value": sb.value(), "maximum": sb.maximum(),
                                 "following": log.is_following_tail()}
    print("03 reader scrolled to the top:", res["reader_scrolled_up"])
    ok, why = capture_window(win, shots / f"{tag}-01-reader-at-top.png")
    res.setdefault("shots", {})["01-reader-at-top"] = \
        f"{tag}-01-reader-at-top.png" if ok else f"REFUSED: {why}"
    print("    shot:", "ok" if ok else "REFUSED " + (why or ""))

    # 4) The percentage ticks up, through the real method.
    steps = []
    for pct in (20, 30, 40):
        tab._on_log_line(f"Added {pct * 10}/1000")
        pump(app, 250)
        steps.append({"pct": pct, "value": sb.value(), "maximum": sb.maximum()})
        print(f"04 after {pct}%: value={sb.value()} max={sb.maximum()}")
    res["percentage_ticks"] = steps
    ok, why = capture_window(win, shots / f"{tag}-02-after-ticks.png")
    res.setdefault("shots", {})["02-after-ticks"] = \
        f"{tag}-02-after-ticks.png" if ok else f"REFUSED: {why}"
    print("    shot:", "ok" if ok else "REFUSED " + (why or ""))

    dragged = steps[-1]["value"] > 0
    res["verdict"] = ("THE READER WAS DRAGGED DOWN: parked at 0, now at "
                      f"{steps[-1]['value']} of {steps[-1]['maximum']}"
                      if dragged else
                      "the reader stayed where they were parked")
    print("05", res["verdict"])

    (out / f"{tag}-log-tail.json").write_text(json.dumps(res, indent=2),
                                              encoding="utf-8")
    win.close()
    pump(app, 400)
    return 1 if dragged else 0


if __name__ == "__main__":
    sys.exit(main())
