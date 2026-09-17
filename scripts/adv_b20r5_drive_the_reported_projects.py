#!/usr/bin/env python3
"""Round 5: drive the REAL ChromIQ window over copies of four reported projects.

A real window, photographed with onscreen_capture.capture_window. The disk is
listed before and after every open, and the UI is asked what it holds.
"""
import os, shutil, sys, time, json
from pathlib import Path

REPO = Path("/Users/Basti/develop/ChromIQ")
PROOF = Path.home() / "Desktop/ChromIQ-beta20-proof/combined-round-5"
WORK = Path("/tmp/b20r5-drive")

os.environ["CHROMIQ_SETTINGS_FILE"] = "/tmp/chromiq-b20r5.ini"
os.environ["CHROMIQ_PRESETS_DIR"]   = "/tmp/chromiq-b20r5-presets"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

SRC = Path("/tmp/b20r5-src/orig")
CASES = {
    "A_no_manifest_with_reports": SRC / "A-1168-old",
    "B_stamped_v2_flat":          SRC / "B-900",
    "C_no_manifest_10_pages":     SRC / "C-2060",
    "D_bare_four_files":          SRC / "D-1168-flat",
}

def listing(root: Path):
    out = []
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        out.append(("DIR  " if p.is_dir() else f"{p.stat().st_size:>10} ") + rel)
    return out

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
    win = MainWindow(s)
    win.resize(1560, 1020)
    win.show()
    for _ in range(50):
        app.processEvents(); time.sleep(0.02)

    rep = ["# Combined round 5 - on screen, over copies of four reported projects",
           "", f"working folder (sandboxed): {WORK}", ""]
    shots = []

    for tag, srcdir in CASES.items():
        src = next(p for p in srcdir.iterdir() if p.is_dir())
        dest = WORK / src.name
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(src, dest)
        before = listing(dest)

        rep += [f"\n## {tag}", f"folder: {src.name}", "",
                "### disk BEFORE the app opened it"] + ["    " + l for l in before]

        # what the app says about the folder without touching it
        pk = fmmod.peek_project(dest)
        rep += ["", "### peek_project BEFORE (the 'already exists' guard's source)",
                f"    exists={pk.exists} run={pk.run_id} chart={pk.chart} "
                f"measurement={pk.measurement} profile={pk.profile} "
                f"holds_anything={any(r.holds_anything for r in pk.runs) if pk.runs else None}"]

        fm = win._file_mgr
        fm.open_project_at(dest)
        proj = fm.project()
        win._target_ctl.changed.emit()
        for _ in range(40):
            app.processEvents(); time.sleep(0.02)

        after = listing(dest)
        rep += ["", "### disk AFTER the app opened it"] + ["    " + l for l in after]

        b = {l.split(" ", 1)[-1].strip() for l in before}
        a = {l.split(" ", 1)[-1].strip() for l in after}
        leftbehind = sorted(x for x in b & a if "/" not in x and (dest / x).is_file())
        rep += ["", "### still loose at the project root after the conversion",
                *(f"    {x}" for x in leftbehind)] or [""]

        run = proj.current_run()
        rep += ["", "### what the app now holds",
                f"    current run          : {run.id}",
                f"    chart .ti2           : {run.chart_ti2.is_file()}",
                f"    measurement .ti3     : {run.measurement_ti3.is_file()}",
                f"    profile .icc         : {run.profile_icc.is_file()}",
                f"    schema_version       : {json.loads((dest/'project.json').read_text(encoding='utf-8'))['schema_version']}"]

        pk2 = fmmod.peek_project(dest)
        rep += ["", "### peek_project AFTER",
                f"    exists={pk2.exists} run={pk2.run_id} chart={pk2.chart} "
                f"measurement={pk2.measurement} profile={pk2.profile}"]

        # THE GUARD: type the name into Create Chart and ask whether it fires
        tabc = win._tab_chart
        try:
            on_disk = tabc._name_is_a_project_on_disk(src.name)
        except Exception as e:
            on_disk = f"RAISED {e}"
        rep += ["", "### the 'this name is already a project' guard",
                f"    _name_is_a_project_on_disk({src.name[:40]}...) = {on_disk}"]

        win._tabs.setCurrentIndex(0)
        for _ in range(30):
            app.processEvents(); time.sleep(0.02)
        shot = PROOF / "shots" / f"{tag}.png"
        ok, why = capture_window(win, shot)
        shots.append((tag, ok, why, shot))
        rep += ["", "### photograph", f"    captured={ok}" + ("" if ok else f"  REFUSED: {why}"),
                f"    {shot if ok else '(none kept)'}"]

    # ---- does peek_project really run on every keystroke? -----------------
    calls = [0]
    real = fmmod.peek_project
    def spy(root):
        calls[0] += 1
        return real(root)
    fmmod.peek_project = spy
    try:
        import ui.tabs.tab_chart as tc
        if hasattr(tc, "peek_project"):
            tc.peek_project = spy
        box = win._tab_chart._target_name_edit if hasattr(win._tab_chart, "_target_name_edit") else None
        if box is None:
            for attr in dir(win._tab_chart):
                o = getattr(win._tab_chart, attr, None)
                if o.__class__.__name__ == "QLineEdit" and "name" in attr.lower():
                    box = o; break
        typed_note = "no name box found"
        if box is not None:
            box.clear()
            for ch in "Printer_HP":
                box.setText(box.text() + ch)
                app.processEvents()
            typed_note = (f"box={box.objectName() or type(box).__name__}; "
                          f"10 characters typed -> peek_project called {calls[0]} time(s)")
    finally:
        fmmod.peek_project = real
    rep += ["", "## is peek_project really asked on every keystroke?", f"    {typed_note}"]

    win.close(); app.processEvents()
    (PROOF / "onscreen-round5.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))
    print("\nSHOTS:", shots)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
