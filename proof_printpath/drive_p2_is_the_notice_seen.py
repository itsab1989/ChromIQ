#!/usr/bin/env python3
"""Is the "why it is greyed" notice actually ON SCREEN when the radio is greyed?

A control greyed without saying why is the shape this project has been fixing
all week. ``ui/tabs/tab_print.py`` does say why — in ``self._cm_notice``, a
sibling label BELOW the group box. The question this driver answers is whether
a user in that state can see the label without hunting for it: the radio and
the notice are measured in WINDOW coordinates against the window's own rect,
and the notice's ``visibleRegion()`` is asked whether any of it is painted.

Usage:
    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-printpath.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-printpath-presets
    python proof_printpath/drive_p2_is_the_notice_seen.py --out DIR
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

WORK = Path("/tmp/chromiq-printpath-p2b-work")
PROJECT = "Notice-Demo"
ARGYLL = Path("/Applications/Argyll/bin")


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def where(win, w) -> dict:
    tl = w.mapTo(win, QPoint(0, 0))
    vis = w.visibleRegion()
    return {
        "widget": type(w).__name__,
        "visible_to_the_window": bool(w.isVisible()),
        "x": tl.x(), "y": tl.y(), "w": w.width(), "h": w.height(),
        "bottom_y": tl.y() + w.height(),
        "window_height": win.height(),
        "inside_the_window": tl.y() + w.height() <= win.height(),
        "painted_area_px": int(vis.boundingRect().width()
                               * vis.boundingRect().height()),
        "painted_region_is_empty": bool(vis.isEmpty()),
        "own_area_px": w.width() * w.height(),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else ROOT / "proof_printpath" / "onscreen"
    out.mkdir(parents=True, exist_ok=True)
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"screen_locked": session_is_locked()}
    print(f"00 screen locked: {res['screen_locked']}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("argyll_bin_path", str(ARGYLL))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")

    from core.file_manager import Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    project = Project.create(WORK / PROJECT, PROJECT)
    run = project.current_run()
    run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    stage = WORK / "_stage"
    stage.mkdir()
    shutil.copy(ROOT / "demo-projects" / "Demo-Report-Matrix" / "runs" / "run1"
                / "verifications" / "Demo-Report-Matrix-verify.ti1",
                stage / "verify.ti1")
    subprocess.run([str(ARGYLL / "printtarg"), "-iCM", "-h", "-pA4", "-t300",
                    "verify"], cwd=str(stage), capture_output=True, timeout=300)
    made = sorted(stage.glob("verify*.tif"))
    ti2 = run.verify_chart_ti2
    shutil.copy(stage / "verify.ti2", ti2)
    page = run.verifications_dir / f"{run.verify_stem}_01.tif"
    shutil.copy(made[0], page)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    results = {}
    for label, size in (("the window at its default size", None),
                        ("a 1620x1060 window", (1620, 1060)),
                        ("a small 1280x800 window", (1280, 800))):
        if size:
            win.resize(*size)
        win.show()
        pump(app, 1200)
        win._file_mgr.set_target_name(PROJECT)
        win._target_ctl.set_profile_run("run1")
        win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
        tab = win._tab_print
        win._tabs.setCurrentWidget(tab)
        pump(app, 700)
        tab._current_ti2 = ti2
        tab.load_tiffs([page])
        tab._update_colour_row_visible()
        pump(app, 700)
        assert not tab._cm_through_rb.isEnabled(), \
            "this drive needs the greyed state"
        results[label] = {
            "window": [win.width(), win.height()],
            "the greyed radio": where(win, tab._cm_through_rb),
            "the notice that explains it": where(win, tab._cm_notice),
        }
        n = results[label]["the notice that explains it"]
        r = results[label]["the greyed radio"]
        print(f"{label}: window {win.width()}x{win.height()}")
        print(f"   radio  y {r['y']}..{r['bottom_y']}  painted "
              f"{r['painted_area_px']}/{r['own_area_px']} px")
        print(f"   notice y {n['y']}..{n['bottom_y']}  painted "
              f"{n['painted_area_px']}/{n['own_area_px']} px  "
              f"inside the window: {n['inside_the_window']}")

    res["measurements"] = results
    ok, why = capture_window(win, out / "p2_notice_on_screen.png")
    res["capture"] = {"ok": ok, "why_not": why}
    print(f"capture: {ok} {why}")
    (out / "p2_notice_visibility.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")
    print(f"wrote {out / 'p2_notice_visibility.json'}")
    win.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
