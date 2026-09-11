#!/usr/bin/env python3
"""Does a measurement ALREADY ON DISK on the 0..1 CIE scale reach a profile?

The 2026-09-11 measurement-import round put the hundredfold CIE-scale repair
inside ``finalize_converted_ti3``, which every CONVERT path calls. This driver
asks the question that round did not: the user who imported the same file
YESTERDAY has the broken ``.ti3`` sitting in her run folder. What does the app
say when she opens that project today and builds again?

Drives the REAL window, on screen, sandboxed settings/presets/working folder.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv-presets
    python scripts/drive_adversary_stale_cie_scale.py --out DIR [--tag before]
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

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                         # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

# THE REPORTER'S FILES ARE NOT IN THIS REPO AND HER FOLDER IS NOT ANYBODY'S.
# Point CHROMIQ_I1P_SAMPLES at a folder holding an i1Profiler measurement
# export; the driver says what it needs and stops if it is not there, rather
# than carrying somebody's desktop path around in the history.
SAMPLES = Path(os.environ.get("CHROMIQ_I1P_SAMPLES", "")) if os.environ.get(
    "CHROMIQ_I1P_SAMPLES") else None
WITH_XYZ = (SAMPLES / os.environ.get("CHROMIQ_I1P_WITH_XYZ", "")) if SAMPLES else None
PROJECT = "I1P-Import-Proof"
WORK = Path("/tmp/chromiq-adv-work")
ARGYLL = Path("/Applications/Argyll/bin")

modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app, shots: Path):
    seen = {"n": 0}

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
        info = getattr(w, "informativeText", None)
        if callable(info):
            try:
                text += "\n" + str(info())
            except Exception:
                pass
        seen["n"] += 1
        p = shots / f"modal-{seen['n']:02d}.png"
        ok, why = capture_window(w, p)
        modals.append({"title": title, "text": text[:800],
                       "shot": p.name if ok else None, "capture": why or "ok"})
        print(f"    !! modal {seen['n']}: {title!r} :: {text[:120]!r}")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(350)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def shot(win, path: Path, res: dict, key: str) -> None:
    ok, why = capture_window(win, path)
    res.setdefault("shots", {})[key] = path.name if ok else f"REFUSED: {why}"
    print(f"    shot {key}: {'ok' if ok else 'REFUSED ' + why}")


def white_lab(ti3: Path) -> dict:
    """The lightest patch of the file, as ChromIQ's own reader sees it."""
    from workflow.ti3_analysis import parse_ti3
    d = parse_ti3(ti3)
    i = max(range(len(d.xyz)), key=lambda k: d.xyz[k][1])
    x, y, z = (float(v) for v in d.xyz[i])
    t = y / 100.0
    f = t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    return {"xyz": [round(x, 5), round(y, 5), round(z, 5)],
            "L*": round(116 * f - 16, 2),
            "patches": int(d.n_patches)}


def make_the_file_she_has(run_dir: Path) -> Path:
    """txt2ti3 on her export, with NO finalise step: the file on her disk."""
    stage = WORK / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    src = stage / "her.txt"
    shutil.copy2(WITH_XYZ, src)
    subprocess.run([str(ARGYLL / "txt2ti3"), "-v", src.name, "her"],
                   cwd=stage, timeout=600, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = stage / "her.ti3"
    filed = run_dir / f"{PROJECT}.ti3"
    shutil.copy2(out, filed)
    return filed


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"tag": tag, "modals": modals,
                 "screen_locked": session_is_locked()}
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
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, work {WORK}")

    shutil.copytree(HER / PROJECT, WORK / PROJECT)
    run_dir = WORK / PROJECT / "runs" / "run1"
    filed = make_the_file_she_has(run_dir)
    res["on_disk"] = white_lab(filed)
    print(f"00 the .ti3 on her disk, lightest patch: {res['on_disk']}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1040)
    win.show()
    pump(app, 1800)
    install_modal_watchdog(app, shots)

    tab = win._tab_profile
    ctl = getattr(tab, "_target_ctl", None)
    fm = getattr(ctl, "_fm", None)
    if fm is not None:
        from ui.measurement_filing import open_the_project
        open_the_project(tab, fm, PROJECT, WORK / PROJECT)
        pump(app, 1200)

    # ---- R1: the Build Profile tab, loading the measurement that is there ----
    print("R1 Build Profile loads the measurement already in the run")
    n_modals = len(modals)
    tab.set_ti3_path(filed)
    pump(app, 1200)
    win.setCurrentTabByName = getattr(win, "setCurrentTabByName", None)
    try:
        win._tabs.setCurrentWidget(tab)
    except Exception:
        pass
    pump(app, 800)
    res["R1"] = {
        "file_label": tab._file_lbl.text(),
        "build_enabled": bool(tab._build_btn.isEnabled()),
        "build_tooltip": tab._build_btn.toolTip(),
        "windows_shown": modals[n_modals:],
    }
    print(f"    label    : {res['R1']['file_label']}")
    print(f"    enabled  : {res['R1']['build_enabled']}")
    print(f"    tooltip  : {res['R1']['build_tooltip']!r}")
    print(f"    windows  : {len(res['R1']['windows_shown'])}")
    shot(win, shots / f"{tag}-01-build-profile.png", res, "01-build-profile")

    # ---- R2: the Measurement Report on the same file -------------------------
    print("R2 the Measurement Report on the same measurement")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=filed)
    dlg.resize(1400, 960)
    dlg.show()
    pump(app, 2500)
    shot(dlg, shots / f"{tag}-02-report.png", res, "02-report")
    try:
        dlg._generate_btn.click()
    except Exception as exc:
        print(f"    generate click failed: {exc}")
    pump(app, 4000)
    shot(dlg, shots / f"{tag}-03-report-generated.png", res, "03-report-generated")
    txt = ""
    for attr in ("_summary", "_text", "_view"):
        w = getattr(dlg, attr, None)
        for m in ("toPlainText", "text"):
            f = getattr(w, m, None)
            if callable(f):
                try:
                    txt = str(f())
                    break
                except Exception:
                    pass
        if txt:
            break
    res["R2"] = {"report_text_head": txt[:1500]}
    dlg.close()
    pump(app, 400)

    (out / f"result-{tag}.json").write_text(json.dumps(res, indent=2),
                                            encoding="utf-8")
    print(f"\nwrote {out / f'result-{tag}.json'}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
