#!/usr/bin/env python3
"""#209, second half, on screen: the converter's reason in the user's language,
and a calibration's i1Profiler export loaded with ArgyllCMS's Windows names.

The same ONE simulation as ``drive_209_txt_import_with_windows_tool_names.py``:
the real macOS ArgyllCMS programs are copied under their Windows names
(``txt2ti3.exe``, ...) and ``core.resource_path.argyll_binary`` is patched IN
THIS DRIVER ONLY to add ``.exe``. Everything else is the real app: the real
main window with the shipped stylesheet (``apply_appearance``, light, as in the
reporter's screenshot), the chosen language loaded the way ``main()`` loads it,
real windows photographed by window id, real Argyll conversions and printcal on
a demo project staged in the report folder. Settings are sandboxed.

Phase 1, ``txt2ti3.exe`` genuinely missing from the folder (the reporter's
situation before the #209 fix, now produced honestly):

1. a PROFILING run, Measure tab > Import of an i1Profiler ``.txt``;
2. Build Profile > "Load measurement data" of the same ``.txt``;
3. Build Profile with Run type = Calibration, the header's loader, of the
   calibration chart's ``.txt``;
4. Build Profile > "Load measurement data" of a damaged ``.mxf`` (the CxF
   reasons need no ArgyllCMS at all);
5. Build Profile's txt2ti3 failure window (M-CONVERT-TXT-NOT-MEASUREMENT),
   opened by calling its method with a txt2ti3 error line, because reaching it
   for real needs txt2ti3 to succeed once and fail the second time.

Phase 2, ``txt2ti3.exe`` put back:

6. Run type = Calibration, the header's loader, the calibration ``.txt``:
   converted beside the export, loaded, printcal run on it.

    python scripts/drive_209_converter_errors_in_the_users_language.py \\
        --out <report> --lang ru
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True, help="report folder")
ap.add_argument("--lang", default="ru")
ARGS = ap.parse_args()

TREE = Path(__file__).resolve().parent.parent
OUT = Path(ARGS.out).expanduser().resolve()
SHOTS = OUT / f"shots-{ARGS.lang}"
SANDBOX = OUT / f"sandbox-{ARGS.lang}"
REAL_ARGYLL = Path("/Applications/Argyll/bin")
WIN_ARGYLL = SANDBOX / "argyll-win" / "bin"
TOOLS = ("txt2ti3", "spec2cie", "cxf2ti3", "colprof", "targen", "printtarg",
         "chartread", "printcal", "applycal", "profcheck", "iccgamut",
         "viewgam", "xicclu", "icclu", "cctiff", "fakeread", "average",
         "iccdump", "spotread")

if SANDBOX.exists():
    shutil.rmtree(SANDBOX)
SANDBOX.mkdir(parents=True)
if SHOTS.exists():
    shutil.rmtree(SHOTS)
SHOTS.mkdir(parents=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(TREE / "scripts"))
sys.path.insert(0, str(TREE))

import core.resource_path as _rp                                  # noqa: E402

_rp.argyll_binary = lambda name: name + ".exe"

RESULT: dict = {"lang": ARGS.lang, "steps": [], "findings": []}


def say(step, detail=None):
    print(f"[STEP] {step}" + (f"  {detail}" if detail is not None else ""),
          flush=True)
    RESULT["steps"].append({"step": step, "detail": detail})


def windows_named_argyll(without=("txt2ti3",)) -> Path:
    WIN_ARGYLL.mkdir(parents=True, exist_ok=True)
    for t in TOOLS:
        src, dst = REAL_ARGYLL / t, WIN_ARGYLL / f"{t}.exe"
        if t in without:
            dst.unlink(missing_ok=True)
        elif src.exists() and not dst.exists():
            shutil.copy2(src.resolve(), dst)
    ref = WIN_ARGYLL.parent / "ref"
    if not ref.exists():
        ref.symlink_to((REAL_ARGYLL.parent / "ref").resolve())
    return WIN_ARGYLL


def fakeread(icc: Path, chart_ti1: Path, out_dir: Path, stem: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(chart_ti1, out_dir / f"{stem}.ti1")
    r = subprocess.run([str(REAL_ARGYLL / "fakeread"), str(icc), stem],
                       cwd=out_dir, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr
    return out_dir / f"{stem}.ti3"


def as_i1profiler_txt(ti3: Path, out: Path) -> Path:
    rows, fmt, mode = [], [], None
    for ln in ti3.read_text(encoding="utf-8").splitlines():
        t = ln.strip()
        if t in ("BEGIN_DATA_FORMAT", "BEGIN_DATA"):
            mode = t
            continue
        if t in ("END_DATA_FORMAT", "END_DATA"):
            mode = None
            continue
        if mode == "BEGIN_DATA_FORMAT":
            fmt = t.split()
        elif mode == "BEGIN_DATA" and t:
            rows.append(t.split())
    col = {n: i for i, n in enumerate(fmt)}
    dev = [c for c in ("RGB_R", "RGB_G", "RGB_B") if c in col]
    lines = ['CGATS.17', 'ORIGINATOR "X-Rite i1Profiler"',
             'DESCRIPTOR "Measurement"', 'CREATED "October 15, 2026"',
             'INSTRUMENTATION "i1Pro 2"',
             'MEASUREMENT_SOURCE "Illumination=D50 ObserverAngle=2"', '',
             f'NUMBER_OF_FIELDS {1 + len(dev) + 3}', 'BEGIN_DATA_FORMAT',
             "SampleID " + " ".join(dev) + " XYZ_X XYZ_Y XYZ_Z",
             'END_DATA_FORMAT', '', f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    for i, r in enumerate(rows, 1):
        d = [float(r[col[c]]) * 255.0 / 100.0 for c in dev]
        xyz = [float(r[col[c]]) for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        lines.append(f"{i} " + " ".join(f"{v:.4f}" for v in d + xyz))
    lines += ["END_DATA", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    argyll = windows_named_argyll(without=("txt2ti3",))
    import make_demo_projects as mdp
    root = SANDBOX / "projects"
    root.mkdir()
    mdp.build_full(root)
    proj = root / "Demo-Full-RGB"
    stem = proj.name
    r1, r3 = proj / "runs" / "run1", proj / "runs" / "run3"
    outside = SANDBOX / "из i1Profiler"
    work = SANDBOX / "fakeread"
    prof_txt = as_i1profiler_txt(
        fakeread(r1 / f"{stem}.icc", r3 / f"{stem}.ti1", work, "profiling"),
        outside / "полны.txt")
    cal_txt = as_i1profiler_txt(
        fakeread(r1 / f"{stem}.icc", proj / "cal" / f"{stem}-cal.ti1", work,
                 "cal"),
        outside / "калибровка.txt")
    bad_mxf = outside / "повреждён.mxf"
    bad_mxf.write_text("<?xml version='1.0'?><cc:CxF xmlns:cc='x'>",
                       encoding="utf-8")
    say("staged", {"argyll (Windows names)": str(argyll),
                   "txt2ti3.exe present": (argyll / "txt2ti3.exe").exists(),
                   "files": sorted(p.name for p in argyll.iterdir())})

    from capture_screens import build_app
    from onscreen_capture import PopupWatchdog, capture_window
    app = build_app()
    # As main() does: the catalogue, the display name through tr, Qt's own
    # strings, and the stylesheet before and after the window is built.
    from core.i18n import install_qt_translator, set_language, tr
    set_language(ARGS.lang)
    app.setApplicationDisplayName(tr("ChromIQ — Printer Profiling"))
    install_qt_translator(app)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    def pump(seconds: float = 0.5) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)

    def shoot(w, name: str) -> None:
        ok, why = capture_window(w, SHOTS / f"{name}.png")
        say(f"photograph {name}", "OK" if ok else f"REFUSED: {why}")
        if not ok:
            RESULT["findings"].append(f"{name}: no photograph ({why})")

    dog = PopupWatchdog(SHOTS, photograph=True, dismiss_windows=True,
                        grace_s=2.5)
    dog.start()

    from core.settings import AppSettings
    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING)
    from ui.main_window import MainWindow
    s = AppSettings()
    s.set("custom_output_path", str(proj.parent))
    s.set("argyll_bin_path", str(argyll))
    s.set("calibration_mode", True)
    s.set("language", ARGS.lang)
    win = MainWindow(s)
    apply_appearance(app, win, "light")
    win.resize(1500, 1000)
    win.show()
    if hasattr(app, "_chromiq_focus_give_back"):
        app._chromiq_focus_give_back.give_back()
    pump(2.0)
    ctl = win._target_ctl
    win._file_mgr.set_target_name(stem)
    win._target_bar.refresh()
    pump(1.0)

    def popups_since(before: int) -> list:
        return [{"title": e.get("title"), "text": e.get("text"),
                 "buttons": e.get("buttons")}
                for e in dog.events[before:]]

    def wait_for_popups(before: int, seconds: float = 6.0) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and len(dog.events) == before:
            pump(0.1)
        pump(3.5)          # photographed at first sight, then dismissed

    # ---- 1: Measure tab import -------------------------------------------
    tab = win._tab_measure
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run3")
    pump(1.0)
    win._tabs.setCurrentWidget(tab)
    pump(0.6)
    tab._switch_mode("import")
    pump(0.4)
    import ui.tabs.tab_measure as tm
    real = tm.open_file_dialog
    tm.open_file_dialog = lambda *a, **k: str(prof_txt)
    try:
        tab._on_import_browse()
    finally:
        tm.open_file_dialog = real
    pump(0.6)
    shoot(win, "01-measure-import-chosen")
    before = len(dog.events)
    tab._import_go_btn.click()
    wait_for_popups(before)
    say("1 Measure tab > Import, txt2ti3.exe missing", popups_since(before))

    # ---- 2 + 4: Build Profile > Load measurement data ---------------------
    prof = win._tab_profile
    win._tabs.setCurrentWidget(prof)
    pump(0.8)
    import ui.tabs.tab_profile as tp
    for name, path in (("02-build-profile-load-txt", prof_txt),
                       ("04-build-profile-load-damaged-mxf", bad_mxf)):
        real = tp.open_file_dialog
        tp.open_file_dialog = lambda *a, _p=path, **k: str(_p)
        before = len(dog.events)
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, prof._on_load_ti3)
            wait_for_popups(before)
        finally:
            tp.open_file_dialog = real
        say(f"{name}", popups_since(before))
        shoot(win, name + "-after")

    # ---- 3: calibration loader, tool missing -----------------------------
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    pump(1.0)
    win._tabs.setCurrentWidget(prof)
    pump(0.8)

    def calibration_load(path: Path, name: str) -> list:
        real = tp.open_file_dialog
        tp.open_file_dialog = lambda *a, **k: str(path)
        before = len(dog.events)
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, prof._on_load_ti3)
            wait_for_popups(before, seconds=4.0)
        finally:
            tp.open_file_dialog = real
        got = popups_since(before)
        say(name, {"windows": got,
                   "loaded": str(getattr(prof, "_cal_ti3_path", None))})
        shoot(win, name + "-after")
        return got

    calibration_load(cal_txt, "03-calibration-load-txt-tool-missing")

    # ---- 5: Build Profile's txt2ti3 failure window ------------------------
    before = len(dog.events)
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(0, lambda: prof._show_txt_import_error(
        "txt2ti3: Error - No patches found in 'полны.txt'"))
    wait_for_popups(before)
    say("05 Build Profile txt2ti3 failure window (method called)",
        popups_since(before))

    # ---- 6: calibration loader, tool present ------------------------------
    windows_named_argyll(without=())
    say("txt2ti3.exe put back", (argyll / "txt2ti3.exe").exists())
    for p in outside.glob("калибровка*.ti3"):
        p.unlink()
    cal_before = sorted(p.name for p in (proj / "cal").iterdir())
    calibration_load(cal_txt, "06-calibration-load-txt")
    loaded = getattr(prof, "_cal_ti3_path", None)
    # A second load of the same export must not overwrite the first .ti3
    # (beta 6 review): it lands as <stem>-2.ti3, and cal/ is left alone.
    calibration_load(cal_txt, "06b-calibration-load-txt-again")
    say("06b second load beside the first, cal/ untouched",
        {"loaded": str(getattr(prof, "_cal_ti3_path", None)),
         "beside": sorted(p.name for p in outside.iterdir()),
         "cal/ unchanged": cal_before == sorted(
             p.name for p in (proj / "cal").iterdir())})
    say("06 converted beside the export",
        {"loaded": str(loaded),
         "beside": sorted(p.name for p in outside.iterdir()),
         "log": prof._pc_log.toPlainText().splitlines()[-3:]})
    if loaded and Path(loaded).exists():
        prof._pc_run_btn.click()
        for _ in range(300):
            pump(0.1)
            if not win._runner.is_running:
                break
        pump(3.5)
        say("06 printcal on the converted .ti3",
            {"log tail": prof._pc_log.toPlainText().splitlines()[-4:],
             "beside": sorted(p.name for p in outside.iterdir())})
        shoot(win, "06-calibration-printcal-done")
    else:
        RESULT["findings"].append("calibration .txt was not loaded")

    dog.stop()
    RESULT["popups"] = dog.events
    (SHOTS / "result.json").write_text(json.dumps(RESULT, indent=2,
                                                  default=str,
                                                  ensure_ascii=False),
                                       encoding="utf-8")
    win.close()
    pump(0.5)
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
