#!/usr/bin/env python3
"""Combined round 6: confirm round 5's two fixes by DRIVING the real window.

Fix 1 is behavioural, so it is driven, not unit-tested: a project folder whose
own name collides with the project's own bookkeeping is copied, opened in a
REAL window, listed, and then OPENED A SECOND TIME, because the symptom round 5
fixed only appeared on the next load.
"""
import os, shutil, sys, time, json
from pathlib import Path

REPO = Path("/Users/Basti/develop/ChromIQ")
PROOF = Path.home() / "Desktop/ChromIQ-beta20-proof/combined-round-6"
WORK = Path("/tmp/b20r6-drive")

os.environ["CHROMIQ_SETTINGS_FILE"] = "/tmp/chromiq-b20r6.ini"
os.environ["CHROMIQ_PRESETS_DIR"]   = "/tmp/chromiq-b20r6-presets"
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))

NAMES = ["project", "project_1", "Where are my files", "runs"]

def listing(root: Path):
    return [("DIR  " if p.is_dir() else f"{p.stat().st_size:>8} ") + str(p.relative_to(root))
            for p in sorted(root.rglob("*"))]

def build_flat(root: Path, stem: str):
    root.mkdir(parents=True, exist_ok=True)
    for ext, body in ((".ti1","TI1\n"),(".ti2","TI2\n"),(".ti3","TI3 DATA\n"),
                      (".icc","ICCPROFILE"),(".cht","CHT\n"),(".ps","PS\n")):
        (root / f"{stem}{ext}").write_text(body * 3, encoding="utf-8")
    (root / f"{stem}_01.tif").write_bytes(b"TIFFDATA"*4)

def main():
    if WORK.exists(): shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    (PROOF / "shots").mkdir(parents=True, exist_ok=True)

    from PyQt6.QtWidgets import QApplication
    import main as chromiq_main
    from core.settings import AppSettings
    from ui.styles import WinButtonLayoutStyle
    import core.file_manager as fmmod
    from onscreen_capture import capture_window

    app = QApplication(sys.argv[:1])
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    sys.excepthook = chromiq_main._log_excepthook
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    assert str(WORK) in str(s.get("custom_output_path", "")), "SANDBOX FAILED"

    from ui.main_window import MainWindow
    win = MainWindow(s); win.resize(1560, 1020); win.show()
    for _ in range(50): app.processEvents(); time.sleep(0.02)

    rep = ["# Combined round 6 - ON SCREEN, real window, colliding project names",
           "", f"working folder (sandboxed): {WORK}",
           f"settings file              : {os.environ['CHROMIQ_SETTINGS_FILE']}", ""]
    verdicts = []

    for name in NAMES:
        dest = WORK / name
        build_flat(dest, name)
        before = listing(dest)
        rep += [f"\n## project folder named {name!r}", "", "### disk BEFORE the app opened it"] + \
               ["    " + l for l in before]

        fm = win._file_mgr
        fm.open_project_at(dest); win._target_ctl.changed.emit()
        for _ in range(40): app.processEvents(); time.sleep(0.02)
        after1 = listing(dest)
        rep += ["", "### disk after the FIRST open"] + ["    " + l for l in after1]

        # SECOND open - the reported symptom only appeared on the next load
        fm.open_project_at(dest); win._target_ctl.changed.emit()
        for _ in range(40): app.processEvents(); time.sleep(0.02)
        after2 = listing(dest)
        rep += ["", "### disk after the SECOND open"] + ["    " + l for l in after2]

        proj = fm.project(); run = proj.current_run()
        pk = fmmod.peek_project(dest)
        stray = [l for l in after2 if "project.json" in l and not l.strip().endswith("project.json")]
        stray += [l for l in after2 if "Where are my files.txt" in l and "/" in l]
        lost = [l.split(" ",1)[-1] for l in before
                if l.split(" ",1)[-1] not in {x.split(" ",1)[-1] for x in after2}
                and f"runs/run1/{l.split(' ',1)[-1]}" not in {x.split(' ',1)[-1] for x in after2}]
        ok = (not stray) and (not lost) and after1 == after2 and run.chart_ti2.is_file() \
             and run.measurement_ti3.is_file() and run.profile_icc.is_file()
        verdicts.append((name, ok))
        rep += ["", "### what the app holds, and what is stray",
                f"    current run        : {run.id}",
                f"    chart .ti2         : {run.chart_ti2.is_file()}",
                f"    measurement .ti3   : {run.measurement_ti3.is_file()}",
                f"    profile .icc       : {run.profile_icc.is_file()}",
                f"    schema_version     : {json.loads((dest/'project.json').read_text(encoding='utf-8'))['schema_version']}",
                f"    peek: exists={pk.exists} run={pk.run_id} chart={pk.chart} "
                f"meas={pk.measurement} profile={pk.profile}",
                f"    stray manifest/README inside a run : {stray or 'NONE'}",
                f"    files lost                          : {lost or 'NONE'}",
                f"    open#1 == open#2 on disk            : {after1 == after2}",
                f"    VERDICT: {'PASS' if ok else 'FAIL'}"]

        win._tabs.setCurrentIndex(0)
        for _ in range(30): app.processEvents(); time.sleep(0.02)
        shot = PROOF / "shots" / f"named-{name.replace(' ','-')}.png"
        cap_ok, why = capture_window(win, shot)
        rep += ["", "### photograph",
                f"    captured={cap_ok}" + ("" if cap_ok else f"  REFUSED: {why}"),
                f"    {shot if cap_ok else '(none kept)'}"]

    rep += ["", "## summary"] + [f"    {n!r}: {'PASS' if v else 'FAIL'}" for n, v in verdicts]
    win.close(); app.processEvents()
    (PROOF / "onscreen-round6.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))
    return 0 if all(v for _, v in verdicts) else 1

if __name__ == "__main__":
    raise SystemExit(main())
