#!/usr/bin/env python3
"""Challenge round 4 for the Measure tab's profiling import: the roads rounds
1 to 3 did not take.

Round 3 came back clean on the journey it drives, which is the moment to stop
driving that journey and attack something else. Five different ones here:

1. the **CGATS .txt** route, through the real ArgyllCMS txt2ti3, rather than
   the `.ti3` that passes through untouched;
2. a **partial** measurement (§I.10: filed, not refused, and BOTH counts said);
3. the **"New run"** guard, pressed from the IMPORT button rather than Start;
4. the project **reopened** after an import, which is the state a person
   actually comes back to;
5. the whole panel in **German**, because a translation that does not exist
   leaves English on a German screen and a placeholder mismatch throws.

Same rules as round 3: on screen, sandboxed before `core` is imported, every
window photographed, every modal recorded and closed rather than left standing.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

SANDBOX = Path(tempfile.mkdtemp(prefix="chromiq-profiling-import-r4-"))
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SHOTS = Path.home() / "Desktop" / "ChromIQ-beta18-proof" / "profiling-import"
SHOTS.mkdir(parents=True, exist_ok=True)

import scripts.onscreen_capture as onscreen_capture

RESULT: dict = {"sandbox": str(SANDBOX), "steps": [], "captures": [],
                "findings": [], "modals": []}
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


def arm_the_modal_watchdog(app):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

    def _look():
        w = QApplication.activeModalWidget()
        if w is None:
            return
        text = ((w.text() or "") + "\n" + (w.informativeText() or "")
                if isinstance(w, QMessageBox)
                else "\n".join(l.text() for l in w.findChildren(QLabel)
                               if l.text())[:1500])
        MODALS.append({"title": w.windowTitle(), "text": text,
                       "buttons": [b.text() for b in w.findChildren(QPushButton)]})
        print(f"[MODAL] {w.windowTitle()!r}: {text[:300]}", flush=True)
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
    # The project folder IS the project name, so rename the artefacts with it.
    for run in (dst / "runs").glob("run*"):
        for f in list(run.iterdir()):
            if f.is_file() and f.name.startswith("Demo-Report-Matrix"):
                f.rename(run / f.name.replace("Demo-Report-Matrix", name))
    manifest = dst / "project.json"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("Demo-Report-Matrix", name),
        encoding="utf-8")
    return dst


def as_i1profiler_txt(ti3: Path, out: Path, keep: int | None = None) -> Path:
    """The same readings written the way an i1Profiler CGATS export writes
    them, so the import has to run the REAL txt2ti3 to get at them.

    RGB back on the 0..255 scale i1Profiler uses, an INSTRUMENTATION header and
    a CREATED date in i1Profiler's own format, and Lab rather than XYZ. `keep`
    truncates it, which is how a person who stopped part way through comes
    back.
    """
    rows, fmt, in_data = [], [], False
    for ln in ti3.read_text(encoding="utf-8").splitlines():
        t = ln.strip()
        if t == "BEGIN_DATA_FORMAT":
            in_data = "fmt"
            continue
        if t == "END_DATA_FORMAT":
            in_data = False
            continue
        if t == "BEGIN_DATA":
            in_data = "data"
            continue
        if t == "END_DATA":
            in_data = False
            continue
        if in_data == "fmt":
            fmt = t.split()
        elif in_data == "data" and t:
            rows.append(t.split())
    col = {n: i for i, n in enumerate(fmt)}
    need = ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
    assert all(n in col for n in need), fmt
    if keep is not None:
        rows = rows[:keep]
    lines = ['CGATS.17', 'ORIGINATOR "X-Rite i1Profiler"',
             'DESCRIPTOR "Measurement"',
             'CREATED "September 14, 2026"',
             'INSTRUMENTATION "i1Pro 2"',
             'MEASUREMENT_SOURCE "Illumination=D50 ObserverAngle=2"',
             '', 'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
             'SampleID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z',
             'END_DATA_FORMAT', '',
             f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    for i, r in enumerate(rows, 1):
        rgb = [float(r[col[c]]) * 255.0 / 100.0 for c in ("RGB_R", "RGB_G", "RGB_B")]
        xyz = [float(r[col[c]]) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        lines.append(f"{i} " + " ".join(f"{v:.4f}" for v in rgb + xyz))
    lines += ["END_DATA", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def patches_in(path: Path) -> int:
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip().upper().startswith("NUMBER_OF_SETS"):
            return int(ln.split()[1])
    return -1


def main() -> int:
    from PyQt6.QtWidgets import QApplication

    proj_dir = stage("Import-Txt")
    run1 = proj_dir / "runs" / "run1"
    real_ti3 = run1 / "Import-Txt.ti3"
    outside = SANDBOX / "from-i1profiler"
    outside.mkdir()
    whole_txt = as_i1profiler_txt(real_ti3, outside / "i1Profiler export.txt")
    part_txt = as_i1profiler_txt(real_ti3, outside / "stopped part way.txt",
                                 keep=64)
    real_ti3.unlink()
    for icc in run1.glob("*.icc"):
        icc.unlink()
    say("staged", {"project": str(proj_dir),
                   "whole export": str(whole_txt),
                   "rows in it": patches_in(whole_txt),
                   "partial export rows": patches_in(part_txt)})

    from core.settings import AppSettings
    from core.measurement_target import RUN_TYPE_PROFILING
    from ui.main_window import MainWindow
    from ui.styles import WinButtonLayoutStyle

    app = QApplication.instance() or QApplication(sys.argv)
    try:
        app.setStyle(WinButtonLayoutStyle("Fusion"))
    except Exception:                         # noqa: BLE001
        pass
    watchdog = arm_the_modal_watchdog(app)

    s = AppSettings()
    s.set("custom_output_path", str(SANDBOX / "projects"))
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
    win._file_mgr.set_target_name("Import-Txt")
    win._target_bar.refresh()
    ctl.set_run_type(RUN_TYPE_PROFILING)

    # ---- 3. the "New run" guard, from the IMPORT button --------------------
    ctl.set_profile_run("")
    tab.set_ti1_path(run1 / "Import-Txt.ti2")
    win._tabs.setCurrentWidget(tab)
    tab._switch_mode("import")
    for _ in range(40):
        app.processEvents()
    tab._import_path = whole_txt
    tab._update_import_panel()
    for _ in range(20):
        app.processEvents()
    before = len(MODALS)
    said: list = []
    import ui.tabs.tab_measure as tm
    real_inform = tm.inform
    tm.inform = lambda parent, title, body: said.append(title)
    tab._on_import_measurement()
    for _ in range(40):
        app.processEvents()
    tm.inform = real_inform
    say("IMPORT pressed with the bar on 'New run'", {
        "explained": said or [m["title"] for m in MODALS[before:]],
        "nothing written": not (run1 / "Import-Txt.ti3").exists()})
    if not said and len(MODALS) == before:
        finding("pressing Import Measurement with the bar on 'New run' said "
                "nothing at all")
    shoot(win, "r4-01-new-run-guard")

    # ---- 1. the real txt2ti3 route -----------------------------------------
    ctl.set_profile_run("run1")
    for _ in range(30):
        app.processEvents()
    done: list = []
    tab._show_import_done_profiling = lambda r, d: done.append((r.id, d))
    tab._import_path = whole_txt
    tab._update_import_panel()
    for _ in range(20):
        app.processEvents()
    panel = tab._import_box_body.text()
    say("the panel on a .txt export", {
        "calls it a CGATS text export": "CGATS text export" in panel,
        "names txt2ti3": "txt2ti3" in panel})
    shoot(win, "r4-02-txt-export-chosen")
    tab._on_import_measurement()
    for _ in range(60):
        app.processEvents()
    time.sleep(0.4)
    filed = run1 / "Import-Txt.ti3"
    say("the .txt import, through the real txt2ti3", {
        "filed": filed.exists(),
        "patches": patches_in(filed) if filed.exists() else -1,
        "instrument kept": ("i1Pro 2" in filed.read_text(encoding="utf-8", errors="replace")
                            if filed.exists() else None),
        "measured date kept": ("CHROMIQ_MEASURED" in
                               filed.read_text(encoding="utf-8", errors="replace")
                               if filed.exists() else None),
        "done": done})
    if not filed.exists():
        finding("the CGATS .txt route filed nothing, so the format i1Profiler "
                "actually exports cannot be imported here")
    elif patches_in(filed) != 210:
        finding(f"the .txt route filed {patches_in(filed)} patches of 210")
    shoot(win, "r4-03-after-the-txt-import")

    # ---- 2. a partial measurement (§I.10) ----------------------------------
    partial_said: list = []
    import ui.measurement_filing as mf
    real_say = mf.say_what_was_filed
    real_ask = mf.ask_to_make_a_new_run
    mf.ask_to_make_a_new_run = lambda p, pr, r: True

    def _watch_partial(parent, f):
        from workflow.measurement_import import assess
        from ui.measurement_filing import chart_the_copy_will_be_judged_against
        chart = chart_the_copy_will_be_judged_against(Path(f))
        v = assess(Path(f), chart)
        partial_said.append({"partial": v.partial, "chart": v.n_chart,
                             "measured": v.n_measured})

    mf.say_what_was_filed = _watch_partial
    tab._import_path = part_txt
    tab._update_import_panel()
    for _ in range(20):
        app.processEvents()
    shoot(win, "r4-04-partial-chosen")
    tab._on_import_measurement()
    for _ in range(60):
        app.processEvents()
    time.sleep(0.4)
    mf.say_what_was_filed = real_say
    mf.ask_to_make_a_new_run = real_ask
    proj = ctl.project_or_none()
    where = done[-1][1] if done else None
    say("a partial measurement (§I.10)", {
        "filed": bool(where) and Path(where).exists(),
        "notice": partial_said,
        "runs now": [r.id for r in proj.all_runs()],
        "run 1 still 210": patches_in(filed) if filed.exists() else -1})
    if not partial_said or not partial_said[-1]["partial"]:
        finding("a partial import was filed without the person being told it "
                "is partial, or was refused")
    elif partial_said[-1]["chart"] != 210 or partial_said[-1]["measured"] != 64:
        finding(f"the partial notice states {partial_said[-1]}, not 64 of 210")
    shoot(win, "r4-05-after-the-partial")

    # ---- 4. reopen the project ---------------------------------------------
    win._file_mgr.set_target_name("Import-Txt")
    win._target_bar.refresh()
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run1")
    tab.set_ti1_path(run1 / "Import-Txt.ti2")
    modal_before = len(MODALS)
    win._tabs.setCurrentWidget(tab)
    for _ in range(60):
        app.processEvents()
    time.sleep(0.8)
    for _ in range(60):
        app.processEvents()
    tab._switch_mode("import")
    for _ in range(30):
        app.processEvents()
    reopened = tab._import_box_body.text()
    say("reopening the project after an import", {
        "IMPORT still offered": tab._import_btn.isVisible(),
        "panel warns the run is full":
            "already holds a measurement" in reopened,
        "windows raised on the way back":
            [m["title"] for m in MODALS[modal_before:]]})
    if "already holds a measurement" not in reopened:
        finding("after reopening, the panel no longer warns that the run "
                "already holds a measurement, so the duplicate is a surprise")
    shoot(win, "r4-06-reopened")

    # ---- 5. German ----------------------------------------------------------
    from core import i18n
    try:
        i18n.set_language("de")
    except Exception as exc:                  # noqa: BLE001
        finding(f"could not switch the app to German: {exc}")
    else:
        tab._update_import_panel()
        for _ in range(20):
            app.processEvents()
        de_panel = tab._import_box_body.text()
        de_help = tab._import_help_body(verifying=False)
        from workflow import measurement_messages as M
        de_title, de_body = M.M_IMPORT_DONE_PROFILING.render(
            run=i18n.tr("Run {n}").format(n=1), folder="/x/runs/run1")
        say("the new strings in German", {
            "panel is German": "Messung" in de_panel,
            "help is German": "Messung" in de_help,
            "done window is German": "Messung" in de_body,
            "nothing left in English":
                "It will be filed" not in de_panel
                and "Use this when" not in de_help,
        })
        (SHOTS / "r4-german-strings.txt").write_text(
            de_panel + "\n\n----\n\n" + de_help + "\n\n----\n\n"
            + de_title + "\n" + de_body, encoding="utf-8")
        if "It will be filed" in de_panel or "Use this when" in de_help:
            finding("English text is left on a German screen in the IMPORT "
                    "module")
        shoot(win, "r4-07-german")
        i18n.set_language("en")
        tab._update_import_panel()

    RESULT["modals"] = MODALS
    say("windows the watchdog met", [m["title"] for m in MODALS])
    (SHOTS / "drive-round4.json").write_text(
        json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
    print("\n=== ROUND 4 FINDINGS ===", flush=True)
    for f in RESULT["findings"] or ["none"]:
        print(" -", f, flush=True)
    win.close()
    for _ in range(20):
        app.processEvents()
    return 1 if RESULT["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
