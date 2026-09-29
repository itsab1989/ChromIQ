#!/usr/bin/env python3
"""Challenge round 5: the path this change was NOT supposed to touch.

Adding the profiling door meant lifting the verification one out of
`_on_import_measurement` into a method of its own. That path was confirmed on
hardware by Sebastian on 2026-08-10 — a real ColorMunki measurement imported
through the module, *"done, import worked and the messages were good"* — so a
refactor that altered it by one line would be the most expensive fault in this
change, and the only honest way to know is to drive it.

Three attacks:

1. the whole **verification** import, on screen, end to end: the dated folder,
   the chart snapshot, the `CHROMIQ_VERIFICATION` stamp, and the run's own
   profiling measurement left exactly where it was;
2. the same module met by a **calibration** run, which §I.9 says still cannot
   import, with the module left rather than stranded;
3. the app started **in German from the first line**, so the panel is judged
   the way a German user meets it rather than after a mid-session switch the
   app does not support.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

SANDBOX = Path(tempfile.mkdtemp(prefix="chromiq-profiling-import-r5-"))
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SHOTS = Path.home() / "Desktop" / "ChromIQ-beta18-proof" / "profiling-import"
SHOTS.mkdir(parents=True, exist_ok=True)

import scripts.onscreen_capture as onscreen_capture

RESULT: dict = {"sandbox": str(SANDBOX), "steps": [], "findings": [],
                "captures": []}
MODALS: list = []


def say(step, detail=None):
    print(f"[STEP] {step}" + (f"  {detail}" if detail is not None else ""),
          flush=True)
    RESULT["steps"].append({"step": step, "detail": detail})


def finding(text):
    print(f"[FINDING] {text}", flush=True)
    RESULT["findings"].append(text)


def shoot(win, name):
    path = SHOTS / f"{name}.png"
    ok, why = onscreen_capture.capture_window(win, path)
    RESULT["captures"].append({"name": name, "ok": ok, "why": why})
    print(f"[SHOT] {name}: {'OK' if ok else 'REFUSED — ' + why}", flush=True)


def arm(app):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

    def _look():
        w = QApplication.activeModalWidget()
        if w is None:
            return
        text = ((w.text() or "") + "\n" + (w.informativeText() or "")
                if isinstance(w, QMessageBox)
                else "\n".join(l.text() for l in w.findChildren(QLabel)
                               if l.text())[:1200])
        MODALS.append({"title": w.windowTitle(), "text": text,
                       "buttons": [b.text() for b in w.findChildren(QPushButton)]})
        print(f"[MODAL] {w.windowTitle()!r}: {text[:250]}", flush=True)
        w.reject() if hasattr(w, "reject") else w.close()
        w.close()

    t = QTimer()
    t.timeout.connect(_look)
    t.start(400)
    return t


def stage(name: str) -> Path:
    root = SANDBOX / "projects"
    root.mkdir(parents=True, exist_ok=True)
    dst = root / name
    shutil.copytree(REPO / "demo-projects" / "Demo-Report-Matrix", dst)
    for run in (dst / "runs").glob("run*"):
        for f in list(run.iterdir()):
            if f.is_file() and f.name.startswith("Demo-Report-Matrix"):
                f.rename(run / f.name.replace("Demo-Report-Matrix", name))
    m = dst / "project.json"
    m.write_text(m.read_text(encoding="utf-8")
                 .replace("Demo-Report-Matrix", name), encoding="utf-8")
    return dst


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    # GERMAN FROM THE FIRST LINE, the way a German user's app starts. Round 4
    # switched mid-session and the static labels stayed English, which is the
    # app's own restart-to-apply rule and not a fault — but it is also not a
    # test of anything, so this one starts there.
    lang = os.environ.get("CHROMIQ_DRIVE_LANG", "en")

    proj = stage("Import-Verify")
    run1 = proj / "runs" / "run1"
    say("staged", {"project": str(proj), "language": lang})

    from core.settings import AppSettings
    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    from ui.styles import WinButtonLayoutStyle

    s = AppSettings()
    s.set("custom_output_path", str(SANDBOX / "projects"))
    s.set("language", lang)
    if lang != "en":
        from core import i18n
        i18n.set_language(lang)

    app = QApplication.instance() or QApplication(sys.argv)
    try:
        app.setStyle(WinButtonLayoutStyle("Fusion"))
    except Exception:                         # noqa: BLE001
        pass
    # KEPT IN A NAME. A QTimer nobody holds is collected the moment `arm`
    # returns, and the watchdog then silently does nothing — which is how
    # round 6 came to sit on a modal for four minutes while its own log said
    # the watchdog had met no windows at all.
    _watchdog = arm(app)

    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    for _ in range(60):
        app.processEvents()
    time.sleep(1.0)
    for _ in range(40):
        app.processEvents()

    tab = win._tab_measure
    ctl = win._target_ctl
    win._file_mgr.set_target_name("Import-Verify")
    win._target_bar.refresh()

    # The run must look like one a verification belongs to: a built profile, a
    # verification chart, and its own profiling measurement already in place —
    # the thing a verification import must not disturb.
    profiling_ti3 = run1 / "Import-Verify.ti3"
    profiling_before = profiling_ti3.read_bytes()
    icc = run1 / "Import-Verify.icc"
    verify_ti2 = None
    try:
        from core.file_manager import Run
        r = Run.for_dir(run1)
        verify_ti2 = r.verify_chart_ti2
        verify_ti2.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run1 / "Import-Verify.ti2", verify_ti2)
    except Exception as exc:                  # noqa: BLE001
        finding(f"could not stage the verification chart: {exc}")
        return 1
    # …and the measurement the person "made in i1Profiler" of THAT chart.
    outside = SANDBOX / "from-i1profiler"
    outside.mkdir()
    mine = outside / "Verification read on the i1iO.ti3"
    shutil.copy2(profiling_ti3, mine)
    say("staged the verification", {
        "profile": icc.is_file(),
        "verify chart": str(verify_ti2),
        "run's own measurement": profiling_ti3.is_file()})

    # ---- 1. the verification import, unchanged -----------------------------
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    tab.set_ti1_path(verify_ti2)
    win._tabs.setCurrentWidget(tab)
    for _ in range(40):
        app.processEvents()
    say("IMPORT in a verification run", {
        "button there": tab._import_btn.isVisible()})
    tab._switch_mode("import")
    for _ in range(30):
        app.processEvents()
    panel = tab._import_box_body.text()
    say("the verification panel still speaks about verifications", {
        "says verification": "erifi" in panel or "erifizier" in panel,
        "names the verify chart": Path(verify_ti2).name in panel})
    if not ("erifi" in panel or "erifizier" in panel):
        finding("the verification panel stopped speaking about verifications, "
                "which the profiling split was not supposed to touch")
    shoot(win, f"r5-01-verification-panel-{lang}")

    done: list = []
    tab._show_import_done = lambda v, dst: done.append((v.id, dst))
    tab._ask_how_printed = lambda ti3: done.append(("asked how printed", ti3))
    tab._import_path = mine
    tab._update_import_panel()
    for _ in range(20):
        app.processEvents()
    tab._on_import_measurement()
    for _ in range(60):
        app.processEvents()
    time.sleep(0.4)

    from core.file_manager import Run as _Run
    r = _Run.for_dir(run1)
    dated = sorted(p for p in r.verifications_dir.glob("*") if p.is_dir())
    filed = None
    for d in dated:
        hits = list(d.glob("*.ti3"))
        if hits:
            filed = hits[0]
    say("the verification import", {
        "dated folders": [d.name for d in dated],
        "filed": str(filed) if filed else None,
        "stamped CHROMIQ_VERIFICATION":
            ("CHROMIQ_VERIFICATION" in filed.read_text(encoding="utf-8", errors="replace")
             if filed else None),
        # IN `chart/`, WHICH IS WHERE IT GOES. The first version of this probe
        # looked in the dated folder itself, found nothing and filed a fault
        # about a snapshot that was there all along, one directory down beside
        # every shipped one. Measure where the thing lives.
        "chart snapshot beside it":
            bool(filed) and bool(list((filed.parent / "chart").glob("*.ti2"))),
        "how-printed asked": any(d[0] == "asked how printed" for d in done),
        "the run's own measurement untouched":
            profiling_ti3.read_bytes() == profiling_before,
        "the run's profile untouched": icc.is_file(),
        "done window": [d for d in done if d[0] != "asked how printed"],
    })
    if filed is None:
        finding("the verification import filed nothing; the path Sebastian "
                "confirmed on hardware is broken")
    else:
        if "CHROMIQ_VERIFICATION" not in filed.read_text(encoding="utf-8", errors="replace"):
            finding("the verification import no longer stamps "
                    "CHROMIQ_VERIFICATION, so Build Profile would build from it")
        if not list((filed.parent / "chart").glob("*.ti2")):
            finding("no chart snapshot was stored with the verification, so "
                    "the result stops being interpretable if the chart changes")
    if profiling_ti3.read_bytes() != profiling_before:
        finding("a verification import changed the run's own profiling "
                "measurement")
    shoot(win, f"r5-02-after-the-verification-import-{lang}")

    # ---- 2. a calibration run ----------------------------------------------
    try:
        ctl.set_calibration_allowed(True)
    except Exception:                         # noqa: BLE001
        pass
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab._switch_mode("import")
    for _ in range(30):
        app.processEvents()
    in_import = tab._stack.currentIndex() == 2
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    for _ in range(40):
        app.processEvents()
    say("a calibration run", {
        "was in the module first": in_import,
        "run type really is calibration": ctl.target.is_calibration(),
        "button hidden": not tab._import_btn.isVisible(),
        "module left": tab._stack.currentIndex() != 2})
    if ctl.target.is_calibration() and tab._import_btn.isVisible():
        finding("the IMPORT button is offered for a calibration run, which "
                "§I.9 forbids because a calibration has no safe way to "
                "displace what is already there")
    if ctl.target.is_calibration() and tab._stack.currentIndex() == 2:
        finding("the IMPORT module was left on screen for a calibration run, "
                "with nowhere to file into")
    shoot(win, f"r5-03-calibration-{lang}")

    RESULT["modals"] = MODALS
    say("windows the watchdog met", [m["title"] for m in MODALS])
    (SHOTS / f"drive-round5-{lang}.json").write_text(
        json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
    print("\n=== ROUND 5 FINDINGS ===", flush=True)
    for f in RESULT["findings"] or ["none"]:
        print(" -", f, flush=True)
    win.close()
    for _ in range(20):
        app.processEvents()
    return 1 if RESULT["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
