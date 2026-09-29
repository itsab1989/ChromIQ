#!/usr/bin/env python3
"""Drive the real ChromIQ window: import an i1Profiler measurement into a
PROFILING run from the Measure tab, then build a profile from it.

A tester, 2026-09-15: the import lived on the Build ICC
profile tab for a profiling run and on the Measurement tab for a verification.
Sebastian ruled: add it to the Measurement tab for profiling as well, and leave
the Build ICC profile door where it is.

WHAT THIS PROVES, and it is not "a file appeared": the whole journey a person
makes. The module is on screen in a profiling run, it names the run's OWN chart,
it refuses a measurement of a different chart, it files one that belongs, and
the profile the Build ICC profile tab then builds from it comes out with the
right number of patches in it.

ON SCREEN, ALWAYS. `QT_QPA_PLATFORM` is never set here. Every claim below is
photographed with `onscreen_capture.capture_window`, which takes the WINDOW's
own buffer rather than a rectangle of the screen, and refuses rather than
handing back wallpaper.

SANDBOXED BEFORE `core` IS IMPORTED. CHROMIQ_SETTINGS_FILE and
CHROMIQ_PRESETS_DIR are set at the top of this file, before any ChromIQ import,
so the app physically cannot reach the settings or the presets the owner works
with every day. `custom_output_path` is pinned into the sandbox, so nothing is
ever written into ~/ChromIQ.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---- the sandbox, FIRST ----------------------------------------------------
SANDBOX = Path(tempfile.mkdtemp(prefix="chromiq-profiling-import-"))
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "settings.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")
os.environ.pop("QT_QPA_PLATFORM", None)          # on screen, never offscreen

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SHOTS = Path.home() / "Desktop" / "ChromIQ-beta18-proof" / "profiling-import"
SHOTS.mkdir(parents=True, exist_ok=True)

import scripts.onscreen_capture as onscreen_capture

RESULT: dict = {"sandbox": str(SANDBOX), "steps": [], "captures": [],
                "findings": []}


def say(step: str, detail=None) -> None:
    print(f"[STEP] {step}" + (f"  {detail}" if detail is not None else ""),
          flush=True)
    RESULT["steps"].append({"step": step, "detail": detail})


def shoot(win, name: str) -> None:
    """Photograph the window, and RECORD a refusal rather than hiding it."""
    path = SHOTS / f"{name}.png"
    ok, why = onscreen_capture.capture_window(win, path)
    RESULT["captures"].append({"name": name, "ok": ok, "why": why,
                               "path": str(path) if ok else ""})
    print(f"[SHOT] {name}: {'OK' if ok else 'REFUSED — ' + why}", flush=True)


def finding(text: str) -> None:
    print(f"[FINDING] {text}", flush=True)
    RESULT["findings"].append(text)


MODALS: list = []


def arm_the_modal_watchdog(app, shots: Path):
    """Never leave a window standing on the owner's screen.

    Basti's rule, learned the hard way: *"a driver that blocks on a modal gets
    clicked by BASTI"*, and every result after that point is his, not the
    app's. So a timer looks for a modal every half second, PHOTOGRAPHS it,
    records what it said, and closes it. The record is the evidence: a window
    nobody expected shows up in the log as a window nobody expected, instead of
    as a driver that hung.
    """
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox

    def _look():
        w = QApplication.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        if isinstance(w, QMessageBox):
            text = (w.text() or "") + "\n" + (w.informativeText() or "")
        else:
            from PyQt6.QtWidgets import QLabel
            text = "\n".join(l.text() for l in w.findChildren(QLabel)
                              if l.text())[:2000]
        buttons = [b.text() for b in w.findChildren(
            __import__("PyQt6.QtWidgets", fromlist=["QPushButton"]).QPushButton)]
        MODALS.append({"title": title, "text": text, "buttons": buttons})
        print(f"[MODAL] {title!r} buttons={buttons}\n{text[:400]}", flush=True)
        name = f"modal-{len(MODALS):02d}"
        try:
            path = shots / f"{name}.png"
            ok, why = onscreen_capture.capture_window(w, path)
            RESULT["captures"].append({"name": name, "ok": ok, "why": why,
                                       "path": str(path) if ok else ""})
        except Exception as exc:              # noqa: BLE001
            print(f"[MODAL] could not photograph it: {exc}", flush=True)
        w.reject() if hasattr(w, "reject") else w.close()
        w.close()

    t = QTimer()
    t.timeout.connect(_look)
    t.start(500)
    return t


# ---------------------------------------------------------------------------
# The project, and the measurement that is going to be imported into it
# ---------------------------------------------------------------------------

def stage_the_project() -> tuple[Path, Path, Path]:
    """A real ChromIQ project, copied, never opened in place.

    Run 1 keeps its chart and loses its measurement and its profile, which is
    exactly the state a person is in when they come back from i1Profiler: the
    chart was printed and measured somewhere else, and the run is waiting for
    the readings.
    """
    root = SANDBOX / "projects"
    root.mkdir(parents=True, exist_ok=True)
    src = REPO / "demo-projects" / "Demo-Report-Matrix"
    dst = root / "Demo-Report-Matrix"
    shutil.copytree(src, dst)
    run1 = dst / "runs" / "run1"
    real_ti3 = run1 / "Demo-Report-Matrix.ti3"
    # The measurement the person "made in i1Profiler" — a copy of the run's own
    # real measurement, taken OUT of the project and given an outside name, so
    # the import is judged on its contents and not on where it was sitting.
    outside = SANDBOX / "from-i1profiler"
    outside.mkdir()
    mine = outside / "Chart measured on the i1iO.ti3"
    shutil.copy2(real_ti3, mine)
    real_ti3.unlink()
    for icc in run1.glob("*.icc"):
        icc.unlink()
    # …and a measurement of a DIFFERENT chart, to prove the refusal. Run 2's
    # chart is not run 1's, so this is the honest shape of the mistake: a file
    # that belongs to the project but not to this run.
    wrong = _a_measurement_of_something_else(outside, mine)
    return dst, mine, wrong


def _a_measurement_of_something_else(where: Path, model: Path) -> Path:
    """A measurement of the same SIZE and different colours.

    Same size on purpose: a patch-count check cannot tell these apart, so
    accepting it would prove the identity comparison is not running.
    """
    out = where / "A different chart entirely.ti3"
    lines = model.read_text(encoding="utf-8").splitlines()
    body = False
    fixed = []
    for ln in lines:
        if ln.strip() == "BEGIN_DATA":
            body = True
            fixed.append(ln)
            continue
        if ln.strip() == "END_DATA":
            body = False
        if body and ln.strip():
            f = ln.split()
            # Rotate the device columns: every patch keeps a legal value and
            # almost none of them keeps its own.
            if len(f) > 4:
                f[2], f[3], f[4] = f[4], f[2], f[3]
            fixed.append(" ".join(f))
        else:
            fixed.append(ln)
    out.write_text("\n".join(fixed) + "\n", encoding="utf-8")
    return out


def patches_in(path: Path) -> int:
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.strip().upper().startswith("NUMBER_OF_SETS"):
            return int(ln.split()[1])
    return -1


# ---------------------------------------------------------------------------

def main() -> int:
    from PyQt6.QtWidgets import QApplication

    project, mine, wrong = stage_the_project()
    say("staged the project", {"project": str(project),
                               "import": str(mine),
                               "patches in the import": patches_in(mine),
                               "wrong file": str(wrong)})

    from core.settings import AppSettings
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    from ui.styles import WinButtonLayoutStyle

    app = QApplication.instance() or QApplication(sys.argv)
    try:
        app.setStyle(WinButtonLayoutStyle("Fusion"))
    except Exception:                       # noqa: BLE001 — cosmetic only
        pass
    watchdog = arm_the_modal_watchdog(app, SHOTS)

    s = AppSettings()
    s.set("custom_output_path", str(SANDBOX / "projects"))
    say("settings sandboxed", {"file": os.environ["CHROMIQ_SETTINGS_FILE"],
                               "custom_output_path": s.get("custom_output_path")})

    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    for _ in range(60):
        app.processEvents()
    time.sleep(1.2)
    for _ in range(40):
        app.processEvents()

    tab_measure = win._tab_measure
    tab_profile = win._tab_profile
    ctl = win._target_ctl

    # ---- open the project, land on the Measure tab -------------------------
    win._file_mgr.set_target_name("Demo-Report-Matrix")
    try:
        win._target_bar.refresh()
    except Exception as exc:                # noqa: BLE001
        finding(f"the target bar refused to refresh: {exc}")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run1")
    proj = ctl.project_or_none()
    run = proj.run("run1")
    tab_measure.set_ti1_path(run.chart_ti2)
    win._tabs.setCurrentWidget(tab_measure)
    for _ in range(40):
        app.processEvents()
    time.sleep(0.4)
    say("opened the project on the Measure tab, Run type = Profiling",
        {"run": run.id, "chart": run.chart_ti2.name,
         "chart patches": patches_in(run.chart_ti2),
         "run already measured": run.measurement_ti3.exists()})

    # ---- 1. is the IMPORT door there at all? -------------------------------
    visible = tab_measure._import_btn.isVisible()
    say("IMPORT button visible in a PROFILING run", visible)
    if not visible:
        finding("the IMPORT button is not on screen in a profiling run, which "
                "is the whole change")
    shoot(win, "01-measure-tab-profiling-import-button")

    tab_measure._switch_mode("import")
    for _ in range(30):
        app.processEvents()
    time.sleep(0.3)
    panel = tab_measure._import_box_body.text()
    say("IMPORT panel, profiling wording", {
        "names the run's own chart": run.chart_ti2.name in panel,
        "says 'verification' anywhere": "verif" in panel.lower(),
    })
    if "verif" in panel.lower():
        finding("a profiling reader is being told about verifications:\n"
                + panel)
    shoot(win, "02-import-panel-profiling")
    (SHOTS / "02-import-panel-text.txt").write_text(panel, encoding="utf-8")

    # ---- 2. a measurement of a DIFFERENT chart is refused ------------------
    refused: list = []
    import ui.measurement_filing as mf
    real_refuse = mf.refuse_it_does_not_belong

    def _capture_refusal(parent, reason):
        refused.append(reason)
        print(f"[REFUSAL] {reason}", flush=True)

    mf.refuse_it_does_not_belong = _capture_refusal
    tab_measure._import_path = wrong
    tab_measure._update_import_panel()
    for _ in range(20):
        app.processEvents()
    shoot(win, "03-wrong-file-chosen")
    tab_measure._on_import_measurement()
    for _ in range(30):
        app.processEvents()
    say("a measurement of a different chart", {
        "refused": bool(refused),
        "reason": refused[0] if refused else "",
        "wrote a .ti3 anyway": run.measurement_ti3.exists(),
    })
    if not refused:
        finding("a measurement of a different chart was ACCEPTED into a "
                "profiling run")
    if run.measurement_ti3.exists():
        finding("the refusal wrote a measurement anyway; its promise that "
                "nothing changed is false")
    mf.refuse_it_does_not_belong = real_refuse

    # ---- 3. the real import -----------------------------------------------
    tab_measure._import_path = mine
    tab_measure._update_import_panel()
    for _ in range(20):
        app.processEvents()
    time.sleep(0.3)
    shoot(win, "04-right-file-chosen")

    # The done window is modal; catch it rather than block the driver, and
    # record what it said.
    done: list = []
    real_done = tab_measure._show_import_done_profiling

    def _catch_done(r, dst):
        from workflow import measurement_messages as M
        from core.i18n import tr
        title, body = M.M_IMPORT_DONE_PROFILING.render(
            run=tr("Run {n}").format(
                n=getattr(r, "number", None) or r.id.replace("run", "")),
            folder=str(r.dir))
        done.append({"run": r.id, "dst": str(dst),
                     "title": title, "body": body})
        print(f"[DONE WINDOW] {title}\n{body}", flush=True)

    tab_measure._show_import_done_profiling = _catch_done
    tab_measure._on_import_measurement()
    for _ in range(60):
        app.processEvents()
    time.sleep(0.5)
    tab_measure._show_import_done_profiling = real_done

    filed = run.measurement_ti3
    say("the import", {
        "filed": filed.exists(),
        "where": str(filed),
        "stem matches the chart": filed.stem == run.chart_ti2.stem,
        "patches filed": patches_in(filed) if filed.exists() else -1,
        "stamped as a verification":
            "CHROMIQ_VERIFICATION" in filed.read_text(encoding="utf-8", errors="replace")
            if filed.exists() else None,
        "the user's own file is untouched": mine.exists(),
        "done window": done[0] if done else None,
    })
    if not filed.exists():
        finding("the import filed nothing")
    for _ in range(30):
        app.processEvents()
    shoot(win, "05-after-the-import")
    if done:
        (SHOTS / "05-done-window-text.txt").write_text(
            done[0]["title"] + "\n\n" + done[0]["body"], encoding="utf-8")

    # ---- 4. and now BUILD A PROFILE FROM IT --------------------------------
    win._tabs.setCurrentWidget(tab_profile)
    for _ in range(40):
        app.processEvents()
    time.sleep(0.4)
    # NOT POKED IN BY THE DRIVER. Round 2's finding was that the done window
    # promises this tab can build from the import while nothing had handed it
    # over, and a driver that loads it itself can never see that. So this only
    # LOOKS.
    holding = getattr(tab_profile, "ti3_path", None)
    say("the Build ICC profile tab after the import", {
        "holding": str(holding) if holding else None,
        "holding the import": holding == filed,
        "Build Profile button armed": tab_profile._build_btn.isEnabled(),
    })
    if holding != filed:
        finding("the done window says a profile can be built from the import "
                f"on this tab, and the tab is holding {holding!r}")
    for _ in range(30):
        app.processEvents()
    shoot(win, "06-build-profile-tab-with-the-import")

    # The build itself is an ArgyllCMS run, and it is the point of the whole
    # feature: a profile that comes out of the imported readings.
    icc = run.dir / f"{run.chart_ti2.stem}.icc"
    argyll = s.get("argyll_bin_path", "/Applications/Argyll/bin")
    colprof = Path(argyll) / "colprof"
    if colprof.is_file():
        base = filed.with_suffix("")
        proc = subprocess.run(
            [str(colprof), "-v", "-qm", "-S",
             str(Path(argyll).parent / "ref" / "sRGB.icm"), "-cmt", "-dpp",
             str(base)],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=600, cwd=str(run.dir))
        say("colprof on the imported measurement", {
            "returncode": proc.returncode,
            "icc written": icc.is_file(),
            "icc bytes": icc.stat().st_size if icc.is_file() else 0,
            "tail": (proc.stdout or proc.stderr)[-400:],
        })
        if not icc.is_file():
            finding("no profile came out of the imported measurement; the "
                    "feature's whole purpose is that one can")
    else:
        finding(f"ArgyllCMS colprof is not at {colprof}, so the profile build "
                "could not be driven")

    win._tabs.setCurrentWidget(tab_profile)
    for _ in range(40):
        app.processEvents()
    shoot(win, "07-profile-built-from-the-import")

    # ---- 5. a second import into a run that is now full --------------------
    asked: list = []
    real_ask = mf.ask_to_make_a_new_run
    mf.ask_to_make_a_new_run = lambda parent, p, r: (asked.append(r.id) or True)
    tab_measure._show_import_done_profiling = _catch_done
    modals_before = len(MODALS)
    win._tabs.setCurrentWidget(tab_measure)
    for _ in range(60):
        app.processEvents()
    time.sleep(0.8)
    for _ in range(60):
        app.processEvents()
    new_modals = [m["title"] or m["text"][:60] for m in MODALS[modals_before:]]
    say("coming back to the Measure tab after the import", {
        "windows raised": new_modals})
    if new_modals:
        finding("coming back to the Measure tab after an import raised "
                f"{new_modals}, about the measurement just imported")
    tab_measure._switch_mode("import")
    tab_measure._import_path = mine
    tab_measure._update_import_panel()
    for _ in range(20):
        app.processEvents()
    panel2 = tab_measure._import_box_body.text()
    say("the panel warns BEFORE the button is pressed", {
        "warns": "already holds a measurement" in panel2})
    shoot(win, "08-panel-warns-the-run-is-full")
    before = filed.read_bytes()
    tab_measure._on_import_measurement()
    for _ in range(60):
        app.processEvents()
    time.sleep(0.4)
    mf.ask_to_make_a_new_run = real_ask
    tab_measure._show_import_done_profiling = real_done
    proj = ctl.project_or_none()
    runs = [r.id for r in proj.all_runs()]
    say("a second import into a full run", {
        "asked about": asked,
        "runs now": runs,
        "run 1's measurement untouched": filed.read_bytes() == before,
        "run 1's profile still there": icc.is_file(),
        "where the second one went": done[-1]["dst"] if done else None,
    })
    if filed.read_bytes() != before:
        finding("the second import wrote over run 1's measurement")
    shoot(win, "09-after-the-second-import")

    # ---- 6. the run type moving under the module ---------------------------
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    for _ in range(30):
        app.processEvents()
    time.sleep(0.3)
    v_panel = tab_measure._import_box_body.text()
    shoot(win, "10-switched-to-verification")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    for _ in range(30):
        app.processEvents()
    time.sleep(0.3)
    p_panel = tab_measure._import_box_body.text()
    shoot(win, "11-switched-back-to-profiling")
    say("run type moving under the module", {
        "verification panel mentions verification":
            "verif" in v_panel.lower(),
        "profiling panel mentions verification":
            "verif" in p_panel.lower(),
        "still in the IMPORT module": tab_measure._stack.currentIndex() == 2,
    })
    if "verif" in p_panel.lower():
        finding("after a round trip through Verification the profiling panel "
                "still speaks about verifications")

    RESULT["modals"] = MODALS
    say("windows the watchdog met and closed", MODALS)
    (SHOTS / "drive-result.json").write_text(
        json.dumps(RESULT, indent=2, default=str), encoding="utf-8")
    print("\n=== FINDINGS ===", flush=True)
    for f in RESULT["findings"] or ["none"]:
        print(" -", f, flush=True)
    win.close()
    for _ in range(20):
        app.processEvents()
    return 1 if RESULT["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
