#!/usr/bin/env python3
"""P2 — what does a user have to have done for "Through the profile" to work?

Her question, beta 4, 2026-09-11:

    "First I'm trying printing the verification through ChromIQ. How would I get
     'Through the Profile' to be enabled?"

This drives the REAL ChromIQ window on screen, on a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder, and walks the control
through EVERY state the code can put it in, recording for each one:

  * is the Colour row even on screen?
  * is "Through the profile" enabled, and which option is selected?
  * does the window SAY why, and in what words?
  * does the radio itself carry a tooltip that would explain it?

The four states, from ``ui/tabs/tab_print.py::_update_colour_row_visible``:

  S1  Run type = Profiling, chart loaded          -> row hidden entirely
  S2  Run type = Verification, no profile in run  -> disabled, notice S7
  S3  Run type = Verification, profile in run     -> ENABLED
  S4  Run type = Verification, the chart carries a colorimetric reference
                                                  -> forced Raw, disabled

Usage:
    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-printpath.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-printpath-presets
    python proof_printpath/drive_p2_through_the_profile.py --out DIR
"""
from __future__ import annotations

import json
import os
import re
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

WORK = Path("/tmp/chromiq-printpath-p2-work")
PROJECT = "Verify-Demo"
ARGYLL = Path("/Applications/Argyll/bin")

ENABLED = "'Through the profile' enabled"
SELECTED = "'Through the profile' selected"
GROUP = "the group 'How this chart is printed' is on screen"

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


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def snapshot(tab, name: str, did: str) -> dict:
    row = tab._cm_colour_row
    through = tab._cm_through_rb
    raw = tab._cm_raw_rb
    return {
        "state": name,
        "what the user has done": did,
        "the group 'How this chart is printed' is on screen":
            bool(tab._cm_grp.isVisibleTo(tab)),
        "the Colour row is on screen": bool(row.isVisibleTo(tab)),
        "'Through the profile' enabled": bool(through.isEnabled()),
        "'Through the profile' selected": bool(through.isChecked()),
        "the other option reads": raw.text(),
        "the other option is selected": bool(raw.isChecked()),
        "rendering intent enabled": bool(tab._cm_intent_combo.isEnabled()),
        "what a print would actually do": tab._cm_selected_colour(),
        "the radio's own tooltip": through.toolTip(),
        "the notice under the group": plain(tab._cm_notice.text()),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else ROOT / "proof_printpath" / "onscreen"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked": locked, "modals": modals, "states": []}
    print(f"00 screen locked: {locked}")

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
    settings.set("use_native_print_dialog", False)
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}")

    # -- a real project with a real verification chart page ----------------
    from core.file_manager import Project
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    project = Project.create(WORK / PROJECT, PROJECT)
    run = project.current_run()
    run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)

    # The real printtarg output for a real chart, so the page on the tab is the
    # page ChromIQ files under verifications/ and not a picture of one.
    stage = WORK / "_stage"
    stage.mkdir()
    shutil.copy(ROOT / "demo-projects" / "Demo-Report-Matrix" / "runs" / "run1"
                / "verifications" / "Demo-Report-Matrix-verify.ti1",
                stage / "verify.ti1")
    import subprocess
    subprocess.run([str(ARGYLL / "printtarg"), "-iCM", "-h", "-pA4", "-t300",
                    "verify"], cwd=str(stage), capture_output=True, timeout=300)
    made = sorted(stage.glob("verify*.tif"))
    assert made, "printtarg wrote no page"
    ti2 = run.verify_chart_ti2
    shutil.copy(stage / "verify.ti2", ti2)
    page = run.verifications_dir / f"{run.verify_stem}_01.tif"
    shutil.copy(made[0], page)
    print(f"00 staged a real verification chart: {ti2.name}, {page.name}")
    res["chart_ti2"] = str(ti2)
    res["chart_page"] = str(page)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    pump(app, 1500)
    install_modal_watchdog(app)

    ctl = win._target_ctl
    ctl.set_target_name(PROJECT) if hasattr(ctl, "set_target_name") else None
    win._file_mgr.set_target_name(PROJECT)
    ctl.set_profile_run("run1")
    pump(app, 600)

    tab = win._tab_print
    win._tabs.setCurrentWidget(tab)
    pump(app, 700)
    tab._current_ti2 = ti2
    tab.load_tiffs([page])
    pump(app, 700)

    # -- S1: a profiling run ------------------------------------------------
    ctl.set_run_type(RUN_TYPE_PROFILING)
    pump(app, 600)
    tab._update_colour_row_visible()
    pump(app, 300)
    s = snapshot(tab, "S1", "opened a chart on a PROFILING run")
    res["states"].append(s)
    print(f"S1 row on screen: {s['the Colour row is on screen']}  "
          f"through enabled: {s[ENABLED]}")

    # -- S2: a verification run with NO built profile ----------------------
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 700)
    tab._update_colour_row_visible()
    pump(app, 300)
    res["run_profile_path"] = str(run.built_profile_icc())
    res["run_profile_exists_in_S2"] = run.built_profile_icc().exists()
    s = snapshot(tab, "S2", "switched Run type to Verification, but this run "
                            "has never built a profile")
    res["states"].append(s)
    print(f"S2 through enabled: {s[ENABLED]}  "
          f"notice: {s['the notice under the group'][:90]}")
    ok, why = capture_window(win, out / "p2_S2_no_profile.png")
    res["capture_S2"] = {"ok": ok, "why_not": why}

    # -- S3: the same run, now with a built profile ------------------------
    srgb = ARGYLL.parent / "ref" / "sRGB.icm"
    assert srgb.exists(), srgb
    shutil.copy(srgb, run.profile_icc)          # what colprof would have left
    tab._update_colour_row_visible()
    pump(app, 400)
    s = snapshot(tab, "S3", "built a profile in this run (a .icc now sits in "
                            "the run folder)")
    res["states"].append(s)
    print(f"S3 through enabled: {s[ENABLED]}  selected: {s[SELECTED]}")
    ok, why = capture_window(win, out / "p2_S3_enabled.png")
    res["capture_S3"] = {"ok": ok, "why_not": why}

    # -- S4: a chart whose colours were converted when it was made ---------
    from workflow import verification_print as vp
    vp.colorimetric_reference_for(ti2).write_text("CTI3\n", encoding="utf-8")
    tab._update_colour_row_visible()
    pump(app, 400)
    s = snapshot(tab, "S4", "loaded a chart built by the From Profile Gamut "
                            "module, whose colours already went through the "
                            "profile")
    res["states"].append(s)
    print(f"S4 through enabled: {s[ENABLED]}  "
          f"the other option reads: {s['the other option reads']!r}")
    ok, why = capture_window(win, out / "p2_S4_already_converted.png")
    res["capture_S4"] = {"ok": ok, "why_not": why}
    vp.colorimetric_reference_for(ti2).unlink()

    # -- S5: no chart at all ------------------------------------------------
    tab._update_colour_row_visible()
    pump(app, 300)
    tab._tiff_pages = []
    tab._update_colour_row_visible()
    pump(app, 300)
    s = snapshot(tab, "S5", "a verification run with no chart generated yet")
    res["states"].append(s)
    print(f"S5 group on screen: {s[GROUP]}")

    (out / "p2_through_the_profile.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out / 'p2_through_the_profile.json'}")

    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
