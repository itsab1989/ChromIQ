#!/usr/bin/env python3
"""Round 27b: Knut's declaration rule on a PROFILING chart, through the doors.

B8-409 measured the rule on the verification chart and fixed the profiling
half of it (`.control-strip.json` added to
`workflow.chart_slot.PROFILING_CHART_SUFFIXES`) — but its own on-screen driver
only ever set Run type = Verification, so the half that was BROKEN was the half
nothing photographed. And it reached for `_snapshot_verification_chart()` and
`core.run_delete` directly, which are the helpers, not the doors.

This drives the doors, on a profiling run:

1. a user writes a control-strip declaration beside the run's chart (ChromIQ
   does not write one there itself: `workflow.control_strip` is scoped to the
   verification chart, and the Measurement Report's own help text tells a user
   to drop the sidecar beside whatever chart the measurement is paired with);
2. a measurement is brought in through the Measure tab's **IMPORT** button,
   which is the door that takes the ``runs/runN/chart/`` snapshot;
3. the live chart and the live declaration are both replaced, as a regenerate
   would replace them, and the **Restore Used Chart** button in the profile-run
   bar is PRESSED, its modal answered by clicking its own button;
4. the run is removed through the bar's **Delete** button, its modal answered
   the same way.

Every window photographed twice, pixel-identical, by window id.

    python scripts/adv27b_the_declaration_on_a_profiling_chart.py <out-dir>
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
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                # noqa: E402
from PyQt6.QtWidgets import QDialog, QMessageBox               # noqa: E402

from adv27b_the_preset_button import app_like_main, pump        # noqa: E402
from drive_182_preset_verification_window import twice          # noqa: E402

WORK = Path("/tmp/chromiq-r27b/work-cs")
NAME = "R27b-Strip"
SIDECAR = ".control-strip.json"


def listing(d: Path) -> "list[str]":
    if not d.exists():
        return ["(no folder)"]
    return [("d " if p.is_dir() else "- ") + str(p.relative_to(d))
            for p in sorted(d.rglob("*"))] or ["(empty)"]


def stage(dst: Path) -> Path:
    shutil.copytree(ROOT / "demo-projects" / "Demo-Report-Matrix", dst)
    for run in (dst / "runs").glob("run*"):
        for f in list(run.rglob("*")):
            if f.is_file() and f.name.startswith("Demo-Report-Matrix"):
                f.rename(f.parent / f.name.replace("Demo-Report-Matrix", NAME))
    m = dst / "project.json"
    m.write_text(m.read_text(encoding="utf-8")
                 .replace("Demo-Report-Matrix", NAME), encoding="utf-8")
    return dst


def answer_modal(app, wanted: str, tries: int = 60) -> str:
    """Click the button whose text holds *wanted* in whatever modal is up."""
    for _ in range(tries):
        w = app.activeModalWidget()
        if isinstance(w, QMessageBox):
            for b in w.buttons():
                if wanted.lower() in b.text().replace("&", "").lower():
                    b.click()
                    return f"clicked “{b.text()}”"
            names = [b.text() for b in w.buttons()]
            w.reject()
            return f"no “{wanted}” among {names}; rejected"
        if isinstance(w, QDialog):
            w.accept()
            return "a dialog was accepted"
        app.processEvents()
        time.sleep(0.05)
    return "no modal appeared"


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/ChromIQ-beta23-proof/round-27b-chart")
    shots = out / "shots-strip"
    shots.mkdir(parents=True, exist_ok=True)
    assert "/tmp/" in os.environ.get("CHROMIQ_SETTINGS_FILE", ""), "SANDBOX"
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    log: "list[str]" = []
    verdicts: "dict[str, bool]" = {}

    def say(x=""):
        print(x, flush=True)
        log.append(x)

    app = app_like_main()
    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    s.set("argyll_bin_path", "/Applications/Argyll/bin")
    proj_dir = stage(WORK / NAME)

    from core.measurement_target import RUN_TYPE_PROFILING
    from ui.main_window import MainWindow
    from workflow import control_strip as CS

    win = MainWindow(s)
    win.resize(1500, 1020)
    win.show()
    pump(app, 1400)
    win._file_mgr.open_project_at(proj_dir)
    win._target_ctl.changed.emit()
    pump(app, 800)
    ctl = win._target_ctl
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run1")
    pump(app, 800)

    say("# round 27b — the declaration on a PROFILING chart, through the doors")
    say("")
    say(f"driven {time.strftime('%Y-%m-%d %H:%M:%S')}")
    say(f"project: {proj_dir}")
    say("mode   : ON SCREEN, a real window, capture_window by id")
    say("")

    proj = win._file_mgr.project()
    run = proj.run("run1")
    chart = run.chart_ti2
    decl = CS.declaration_path(chart)

    # ---- 1. the user writes a declaration beside the profiling chart ------
    say("## 1. a declaration beside the PROFILING chart")
    res = CS.declare_for_chart(chart)
    say(f"    declare_for_chart({chart.name}) -> {res.outcome}")
    say(f"    {decl.name} on disk: {decl.is_file()}")
    verdicts["a profiling chart can carry a declaration"] = decl.is_file()
    if not decl.is_file():
        say("    STOPPING: nothing to follow")
        return 1
    live_bytes = decl.read_bytes()
    doc = json.loads(live_bytes)
    say(f"    it names {len(doc['sample_ids'])} patches")

    # AND: is it seen as part of the chart at all?
    from workflow.chart_slot import slot_for
    slot = slot_for(run)
    names = [p.name for p in slot.live_files()]
    verdicts["the slot counts it as a chart file"] = decl.name in names
    say(f"    the run's chart slot counts it as a chart file: "
        f"{decl.name in names}")
    say(f"    the slot's live files: {names}")

    # ---- 2. the IMPORT door takes the chart/ snapshot ---------------------
    say("")
    say("## 2. Measure -> IMPORT, which is the door that snapshots the chart")
    ti3 = run.measurement_ti3
    src = WORK / "imported.ti3"
    shutil.copyfile(ti3, src)
    ti3.unlink(missing_ok=True)      # so the import has somewhere to land
    snap = run.dir / "chart"
    if snap.exists():
        shutil.rmtree(snap)
    tab_m = win._tab_measure
    win._tabs.setCurrentWidget(tab_m)
    pump(app, 800)
    tab_m.set_ti1_path(chart)
    tab_m._switch_mode("import")
    pump(app, 800)
    tab_m._import_path = src
    tab_m._update_import_panel()
    pump(app, 600)
    ok, why, d = twice(app, win, shots / "s1-import-chosen.png")
    say(f"    photograph s1-import-chosen.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")
    clicks: "list[str]" = []
    QTimer.singleShot(500, lambda: clicks.append(answer_modal(app, "OK")))
    tab_m._import_go_btn.click()
    pump(app, 3000)
    for _ in range(4):
        if app.activeModalWidget() is not None:
            clicks.append(answer_modal(app, "OK"))
        pump(app, 500)
    say(f"    modal(s): {clicks}")
    say("")
    say("### runs/run1/chart/ after the import")
    for line in listing(snap):
        say("    " + line)
    stored = snap / decl.name
    got = stored.is_file() and stored.read_bytes() == live_bytes
    verdicts["the import's chart/ snapshot carries the declaration"] = got
    say("")
    say(f"    {decl.name} in chart/: {stored.is_file()}   byte-identical: "
        f"{stored.is_file() and stored.read_bytes() == live_bytes}")
    ok, why, d = twice(app, win, shots / "s2-after-the-import.png")
    say(f"    photograph s2-after-the-import.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")

    # ---- 3. Restore Used Chart, PRESSED ----------------------------------
    say("")
    say("## 3. the live chart is replaced, and Restore Used Chart is pressed")
    decl.write_text(json.dumps(
        {"name": "a LATER chart's strip", "sample_ids": ["999"],
         "generator": "not ChromIQ"}, indent=2) + "\n", encoding="utf-8")
    chart.write_text(chart.read_text(encoding="utf-8", errors="ignore")
                     + "\nKEYWORD \"R27B_MARK\"\n", encoding="utf-8")
    ctl.changed.emit()
    pump(app, 1200)
    bar = win._target_bar
    btn = getattr(bar, "_restore_btn", None)
    say(f"    the Restore Used Chart button is enabled: "
        f"{bool(btn is not None and btn.isEnabled())}")
    say(f"    the live declaration now names: "
        f"{json.loads(decl.read_text(encoding='utf-8'))['sample_ids']}")
    ok, why, d = twice(app, win, shots / "s3-restore-enabled.png")
    say(f"    photograph s3-restore-enabled.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")
    clicks2: "list[str]" = []
    QTimer.singleShot(500, lambda: clicks2.append(
        answer_modal(app, "Restore")))
    if btn is not None:
        btn.click()
    pump(app, 2500)
    for _ in range(4):
        if app.activeModalWidget() is not None:
            clicks2.append(answer_modal(app, "OK"))
        pump(app, 600)
    say(f"    modal(s): {clicks2}")
    back = decl.read_bytes() if decl.is_file() else b""
    same = back == live_bytes
    verdicts["Restore Used Chart put the chart's own declaration back"] = same
    say(f"    the declaration after the restore is byte-identical to the "
        f"snapshot's: {same}")
    if not same and decl.is_file():
        say(f"    it now names: "
            f"{json.loads(decl.read_text(encoding='utf-8')).get('sample_ids')}")
    say(f"    the chart itself came back without the mark: "
        f"{'R27B_MARK' not in chart.read_text(encoding='utf-8', errors='ignore')}")
    ok, why, d = twice(app, win, shots / "s4-after-the-restore.png")
    say(f"    photograph s4-after-the-restore.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")

    # ---- 4. Delete, PRESSED ----------------------------------------------
    say("")
    say("## 4. Delete, pressed in the profile-run bar")
    before = sorted(p.relative_to(proj_dir)
                    for p in proj_dir.rglob("*" + SIDECAR))
    say(f"    declarations in the project before: {[str(p) for p in before]}")
    dbtn = getattr(bar, "_delete_btn", None)
    say(f"    the Delete button is enabled: "
        f"{bool(dbtn is not None and dbtn.isEnabled())}")
    clicks3: "list[str]" = []
    QTimer.singleShot(500, lambda: clicks3.append(answer_modal(app, "Delete")))
    if dbtn is not None:
        dbtn.click()
    pump(app, 2500)
    for _ in range(5):
        if app.activeModalWidget() is not None:
            clicks3.append(answer_modal(app, "OK"))
        pump(app, 600)
    say(f"    modal(s): {clicks3}")
    after = sorted(p.relative_to(proj_dir)
                   for p in proj_dir.rglob("*" + SIDECAR))
    say(f"    declarations in the project after : {[str(p) for p in after]}")
    verdicts["Delete took the run's declarations with it"] = (
        not any(str(p).startswith("runs/run1") for p in after))
    ok, why, d = twice(app, win, shots / "s5-after-the-delete.png")
    say(f"    photograph s5-after-the-delete.png: "
        f"{'kept' if ok else 'REFUSED: ' + why} (differ by {d} %)")

    say("")
    say("## verdicts")
    say("")
    for k, v in verdicts.items():
        say(f"    {'PASS' if v else 'FAIL'}  {k}")
    (out / "profiling-declaration.md").write_text("\n".join(log) + "\n",
                                                  encoding="utf-8")
    (out / "profiling-declaration.json").write_text(
        json.dumps(verdicts, indent=2), encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
