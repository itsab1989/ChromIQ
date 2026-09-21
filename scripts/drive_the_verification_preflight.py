#!/usr/bin/env python3
"""Drive Knut's verification pre-flight and the presets window's first line,
ON SCREEN, in a real window, and photograph what a user would see.

#182, 2026-09-21. Two things that share one check:

* the Measure tab's pre-flight popup, which must appear on **both** of his
  triggers and on **none** of the states where a precondition is broken;
* the "Current chart layout in Create Chart tab" line at the top of "Which
  presets can be used for verification".

What this driver does NOT do is swallow the windows it is here to photograph.
`QMessageBox.exec` and `PresetVerificationDialog.exec` are replaced with a
function that SHOWS the real window the app built, photographs it with
`onscreen_capture.capture_window` (never `widget.grab()`), and then closes it.
Nothing blocks, so nobody has to click anything, and every picture is of a
window the application opened by itself.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-popup/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-popup/presets
    export CHROMIQ_COMPLIANCE_ISO_FILE=$PWD/data/compliance_sets/iso12647.json
    python scripts/drive_the_verification_preflight.py <out-dir>

`CHROMIQ_COMPLIANCE_ISO_FILE` is not optional on a developer machine: this
host carries a licence holder's real ISO 12647 values in
`~/Library/Preferences/ChromIQ/compliance/iso12647.json`, and a driver that
picked those up would photograph limit columns no user of a shipped ChromIQ
has, and put paid-standard content into a proof folder. Pointing it at the
repository's own (empty) file is what makes these pictures the SHIPPED state.
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

ROOT = Path(os.environ.get("CHROMIQ_TREE")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

#: A shipped chart that holds all eight cube corners, used as the ordinary
#: verification chart. Nothing about the pre-flight needs those corners; it is
#: simply a real chart with a real patch set.
ORDINARY_CHART = ROOT / "assets/charts/pharmacist/rgb/colormunki/a4/tc300/tc300.ti1"

#: Where a FROM PROFILE GAMUT chart and its colorimetric reference are taken
#: from, so the gamut half of the proof is a chart the application really
#: built rather than one this script invented. Overridable.
DEMO_PACK = Path(os.environ.get(
    "CHROMIQ_DEMO_PACK", "/private/tmp/chromiq-k3/ChromIQ-Report-Limit-Demos"))

PREFLIGHT_TITLE = "Before you measure this verification chart"

_state: dict = {"shot": None, "seen": [], "photos": [], "app": None,
                "shots_dir": None}


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def capture_settled(win, name: str, tries: int = 4) -> dict:
    """Two consecutive photographs that agree pixel for pixel, or say so."""
    from onscreen_capture import capture_window
    app = _state["app"]
    shots: Path = _state["shots_dir"]
    first, second = shots / f"{name}.png", shots / f"{name}-again.png"
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 900)
        ok, why = capture_window(win, first)
        pump(app, 900)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            second.unlink(missing_ok=True)
            rec = {"photographed": True, "settled": True, "attempts": n,
                   "file": first.name, "why": ""}
            _state["photos"].append(rec)
            return rec
    rec = {"photographed": bool(ok and ok2), "settled": False,
           "attempts": tries, "file": first.name, "why": why}
    _state["photos"].append(rec)
    return rec


# ---------------------------------------------------------------------------
# The windows, shown for real and photographed rather than swallowed
# ---------------------------------------------------------------------------
def install_window_capture(app) -> None:
    """Replace two `exec` calls with show-photograph-close.

    **NOT A BLANKET `QDialog.exec` PATCH.** One of those swallows every
    question the app asks, including the ones a run is supposed to answer, and
    it would swallow the very window this driver exists to photograph. These
    two are named.
    """
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QDialog, QMessageBox

    from ui.dialogs.preset_verification_dialog import PresetVerificationDialog

    def _show_and_shoot(self, result):
        # **IDENTIFIED BY WHAT IT SAYS, NOT BY ITS TITLE BAR.** macOS draws no
        # title on a QMessageBox (B8-615), so `windowTitle()` is not what the
        # user sees and keying on it made the first run of this driver report
        # "the pre-flight did not appear" beside a photograph of the
        # pre-flight.
        said = ""
        try:
            said = self.text()
        except Exception:                              # noqa: BLE001
            said = ""
        title = self.windowTitle()
        _state["seen"].append(
            PREFLIGHT_TITLE if PREFLIGHT_TITLE in (said or "")
            else (title or f"<untitled {type(self).__name__}>"))
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.show()
        self.raise_()
        self.activateWindow()
        pump(app, 900)
        name = _state["shot"]
        if name:
            capture_settled(self, name)
            _state["shot"] = None
        self.close()
        pump(app, 200)
        return result

    QMessageBox.exec = lambda self: _show_and_shoot(
        self, QMessageBox.StandardButton.Ok)
    PresetVerificationDialog.exec = lambda self: _show_and_shoot(self, 0)
    # **AND EVERY OTHER MODAL, OR THE RUN STOPS DEAD.** Measured: putting a
    # real `.ti3` beside the chart to break precondition 3 makes the Measure
    # tab open "This chart already has a measurement", a plain `QDialog` with
    # its own `exec()`. The driver sat on it until it was killed, which is the
    # failure this project already has a note about: a driver that blocks on a
    # modal gets clicked by a human, and everything after that point is their
    # run and not a measurement.
    #
    # It is REJECTED, not accepted: a window this driver did not come to
    # answer must change nothing. And it is recorded in `windows_seen` either
    # way, so no window goes by in silence.
    QDialog.exec = lambda self: _show_and_shoot(
        self, int(QDialog.DialogCode.Rejected))


# ---------------------------------------------------------------------------
# The project the run is driven on
# ---------------------------------------------------------------------------
def _find_gamut_chart() -> "tuple[Path, Path] | None":
    """(chart .ti2, its -reference.ti3) from the demo pack, or None."""
    if not DEMO_PACK.is_dir():
        return None
    for ref in sorted(DEMO_PACK.glob("*/runs/*/verifications/*-reference.ti3")):
        ti2 = ref.with_name(ref.name.replace("-reference.ti3", ".ti2"))
        if ti2.is_file():
            return ti2, ref
    return None


def build_project(work: Path, name: str) -> dict:
    """Three runs, so every state the pre-flight cares about is one click away.

    * run1 — an ORDINARY verification chart, never measured. The pre-flight is
      owed here.
    * run2 — a FROM PROFILE GAMUT chart with its colorimetric reference,
      never measured. Owed here too, and the window says something different.
    * run3 — no chart at all. Never owed, and the presets window's first line
      has to say so.
    """
    from core.file_manager import Project
    root = work / name
    if root.exists():
        shutil.rmtree(root)
    proj = Project.create(root, name)
    facts: dict = {"project": name, "root": str(root)}

    for rid in ("run1", "run2", "run3"):
        while not proj.has_run(rid):
            proj.new_run()
    for rid in ("run1", "run2", "run3"):
        proj.run(rid).ensure_dir()

    # **THE STEM AND THE SHEETS ARE BOTH LOAD-BEARING, and getting either
    # wrong costs a whole run.** `Run.verify_chart_ti2` is
    # `verifications/<project>-verify.ti2`, not `<project>.ti2`, and
    # `TabChart._resolve_target_chart` returns a chart only when the `.ti2`
    # AND its page TIFFs are on disk. A fixture missing either is a run where
    # Create Chart never hands the Measure tab a chart at all, and the
    # pre-flight is then correctly withheld for a reason that has nothing to
    # do with what is being tested. The first run of this driver did exactly
    # that and photographed nothing.

    # run1: an ordinary chart, filed as this run's verification chart.
    run1 = proj.run("run1")
    vdir = run1.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    stem1 = run1.verify_stem
    shutil.copy2(ORDINARY_CHART, vdir / f"{stem1}.ti2")
    shutil.copy2(ORDINARY_CHART, vdir / f"{stem1}.ti1")
    _page(vdir / f"{stem1}_01.tif")
    facts["run1_chart"] = str(vdir / f"{stem1}.ti2")

    # run2: a real FROM PROFILE GAMUT chart, reference and all.
    found = _find_gamut_chart()
    run2 = proj.run("run2")
    vdir2 = run2.verifications_dir
    vdir2.mkdir(parents=True, exist_ok=True)
    stem2 = run2.verify_stem
    if found is not None:
        ti2, ref = found
        shutil.copy2(ti2, vdir2 / f"{stem2}.ti2")
        shutil.copy2(ref, vdir2 / f"{stem2}-reference.ti3")
        facts["run2_chart"] = str(vdir2 / f"{stem2}.ti2")
        facts["run2_reference_from"] = str(ref)
    else:
        # Say so rather than quietly proving the ordinary case twice.
        shutil.copy2(ORDINARY_CHART, vdir2 / f"{stem2}.ti2")
        facts["run2_chart"] = str(vdir2 / f"{stem2}.ti2")
        facts["run2_reference_from"] = ("NOT FOUND: no demo pack at "
                                        f"{DEMO_PACK}, so run2 is ORDINARY")
    _page(vdir2 / f"{stem2}_01.tif")
    # run3 keeps no chart at all.
    return facts


def _page(path: Path) -> None:
    """One small real TIFF, so a chart counts as laid out."""
    from PIL import Image
    Image.new("RGB", (64, 64), (255, 255, 255)).save(path)


# ---------------------------------------------------------------------------
# The drive
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    args = ap.parse_args(argv)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("CHROMIQ_COMPLIANCE_ISO_FILE"), \
        "POINT THE ISO FILE AT THE REPOSITORY'S OWN, OR THIS PHOTOGRAPHS A " \
        "LICENCE HOLDER'S VALUES"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"

    out = Path(args.out).resolve()
    shots = out / "photographs"
    shots.mkdir(parents=True, exist_ok=True)
    _state["shots_dir"] = shots

    from PyQt6.QtWidgets import QApplication
    from onscreen_capture import session_is_locked
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    _state["app"] = app
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    settings = AppSettings()
    work = out / "projects"
    work.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(work))
    settings.set("argyll_bin_path", "/Applications/Argyll/bin")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    record: dict = {
        "mode": "ON SCREEN",
        "tree": str(ROOT),
        "head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=30,
                               encoding="utf-8", errors="replace").stdout.strip(),
        "iso_file_forced": os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"],
        "screen_locked_at_start": session_is_locked(),
        "steps": [],
    }

    # NOT "Preflight-Demo". The disk check below looks for the word "preflight"
    # in the project's own files, and a project NAMED that makes its own
    # manifest a false positive: the first run of this driver reported
    # `project.json` as carrying the tick and it was carrying the project name.
    name = "Verify-Check-Demo"
    record["facts"] = build_project(work, name)

    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    record["window_on_screen"] = bool(win.isVisible())
    record["window_size"] = f"{win.frameGeometry().width()}x{win.frameGeometry().height()}"

    install_window_capture(app)

    fm = getattr(win, "_file_mgr", None)
    tab_measure = win._tab_measure
    tab_chart = win._tab_chart
    ctl = tab_measure._target_ctl
    if fm is not None:
        fm.set_target_name(name)
    pump(app, 900)

    def step(label: str, shot: "str | None", body) -> dict:
        before = len(_state["seen"])
        _state["shot"] = shot
        body()
        pump(app, 1600)
        seen = _state["seen"][before:]
        fired = [t for t in seen if t == PREFLIGHT_TITLE]
        _state["shot"] = None
        # **A NEGATIVE NEEDS A PHOTOGRAPH TOO.** "The window did not open" is
        # a claim, and the picture that backs it is the MAIN WINDOW in that
        # state with nothing over it. Without this the proof folder holds
        # pictures of every case where the popup appears and nothing at all
        # for the cases Knut actually asked to be tested.
        if not fired and shot:
            capture_settled(win, shot)
        rec = {"step": label, "pre_flight_appeared": bool(fired),
               "windows_seen": seen, "shot": shot}
        record["steps"].append(rec)
        print(f"  {label}: pre-flight={'YES' if fired else 'no'} {seen}",
              flush=True)
        return rec

    def goto(tab):
        win._tabs.setCurrentWidget(tab)

    # -- TRIGGER 1: clicking the Measure tab ----------------------------
    goto(tab_chart)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    pump(app, 1400)
    step("T1 clicking the Measure tab, run1, ordinary chart, unmeasured",
         "01-trigger-clicking-the-measure-tab", lambda: goto(tab_measure))

    # -- TRIGGER 2: switching Profile run WHILE standing on Measure -----
    # The tab never leaves the screen, so `showEvent` does not fire at all.
    step("T2 switching Profile run to run2 while standing on Measure "
         "(FROM PROFILE GAMUT chart)",
         "02-trigger-switching-profile-run",
         lambda: ctl.set_profile_run("run2"))

    # -- the four preconditions, broken ONE AT A TIME --------------------
    def back_to_a_good_state(run="run1"):
        goto(tab_chart)
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
        ctl.set_profile_run(run)
        tab_measure._preflight_silenced.clear()
        pump(app, 900)

    back_to_a_good_state()
    step("P1 broken: Run type is Profiling, not Verification",
         "03-not-shown-run-type-is-profiling",
         lambda: (ctl.set_run_type(RUN_TYPE_PROFILING), goto(tab_measure)))

    back_to_a_good_state("run3")
    step("P2 broken: run3 has no chart at all",
         "04-not-shown-no-chart", lambda: goto(tab_measure))

    # P3: a real measurement beside the chart.
    proj_root = Path(record["facts"]["root"])
    chart1 = Path(record["facts"]["run1_chart"])
    shutil.copy2(ORDINARY_CHART, chart1.with_suffix(".ti3"))
    back_to_a_good_state()
    step("P3 broken: a measurement (.ti3) with readings sits beside the chart",
         "05-not-shown-already-measured", lambda: goto(tab_measure))
    chart1.with_suffix(".ti3").unlink(missing_ok=True)

    # P4: a measurement in progress.
    back_to_a_good_state()
    real = type(tab_measure).a_measurement_is_running
    type(tab_measure).a_measurement_is_running = lambda self: True
    step("P4 broken: a measurement is running",
         "06-not-shown-measurement-running", lambda: goto(tab_measure))
    type(tab_measure).a_measurement_is_running = real

    # The tick: per run, this session only.
    back_to_a_good_state()
    scope = tab_measure._preflight_scope()
    before_tick = _disk_snapshot(proj_root, settings)
    tab_measure._preflight_silenced.add(scope)
    step(f"TICK: silenced for {scope}, so it does not come back",
         "07-not-shown-after-the-tick", lambda: goto(tab_measure))
    record["tick_scope"] = list(scope) if scope else None
    record["tick_changed_on_disk"] = _diff(
        before_tick, _disk_snapshot(proj_root, settings))

    # …and the same tick does not silence another run.
    step("TICK: run2 is a different profile run, so it still asks",
         "08-the-tick-is-per-run", lambda: ctl.set_profile_run("run2"))
    tab_measure._preflight_silenced.clear()

    # -- the presets window's first line ---------------------------------
    back_to_a_good_state("run1")
    goto(tab_chart)
    pump(app, 1200)
    _state["shot"] = "09-presets-window-current-chart-selected"
    tab_chart._open_preset_verification_window()
    pump(app, 1200)
    record["steps"].append({"step": "presets window, run1's chart",
                            "shot": "09-presets-window-current-chart-selected"})

    back_to_a_good_state("run2")
    goto(tab_chart)
    pump(app, 1200)
    _state["shot"] = "10-presets-window-from-profile-gamut-chart"
    tab_chart._open_preset_verification_window()
    pump(app, 1200)
    record["steps"].append({"step": "presets window, run2's gamut chart",
                            "shot": "10-presets-window-from-profile-gamut-chart"})

    back_to_a_good_state("run3")
    goto(tab_chart)
    pump(app, 1200)
    _state["shot"] = "11-presets-window-no-chart"
    tab_chart._open_preset_verification_window()
    pump(app, 1200)
    record["steps"].append({"step": "presets window, run3 has no chart",
                            "shot": "11-presets-window-no-chart"})

    # -- what the pre-flight would SAY, in text, for the record ----------
    back_to_a_good_state("run1")
    record["text"] = _preflight_text(tab_measure, ctl, "run1")
    back_to_a_good_state("run2")
    record["text_gamut"] = _preflight_text(tab_measure, ctl, "run2")

    record["photographs"] = _state["photos"]
    win.close()
    pump(app, 400)
    (out / "run.json").write_text(json.dumps(record, indent=2),
                                  encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items()
                      if k not in ("text", "text_gamut")}, indent=2))
    return 0


def _disk_snapshot(root: Path, settings) -> dict:
    """Every byte the tick could possibly be written into, hashed.

    **NOT A SEARCH FOR THE WORD "preflight".** The first version of this check
    did that and reported the settings file as carrying the tick: it was
    carrying a `session_target_name` left on disk by an EARLIER run of this
    driver, because QSettings had not yet flushed the current one. A probe
    that finds its answer somewhere else is worth nothing. What is measured
    instead is the thing that matters: does ticking the box change ANYTHING on
    disk?
    """
    import hashlib
    out: dict = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            try:
                out[str(p.relative_to(root))] = hashlib.sha256(
                    p.read_bytes()).hexdigest()[:16]
            except OSError:
                continue
    sfile = Path(settings._qs.fileName())
    settings._qs.sync()
    if sfile.is_file():
        out["<settings.ini>"] = hashlib.sha256(
            sfile.read_bytes()).hexdigest()[:16]
    return out


def _diff(before: dict, after: dict) -> dict:
    changed = sorted(k for k in set(before) | set(after)
                     if before.get(k) != after.get(k))
    return {"files_that_changed": changed,
            "unchanged": len(set(before) & set(after)) - len(changed)}


def _preflight_text(tab_measure, ctl, run_id: str) -> dict:
    from workflow import preset_eligibility as PE
    try:
        row = tab_measure._preflight_chart_row()
        type_id, set_id, overrides = tab_measure._preflight_selection()
        row.assessment = PE.assess(row.chart, type_id, set_id, overrides)
        title, text = tab_measure._verification_preflight_message(row)
        return {"run": run_id, "due": tab_measure._verification_preflight_due(),
                "report_type": type_id, "limit_set": set_id,
                "from_profile_gamut": row.from_profile_gamut,
                "answered": len(row.assessment.answered),
                "asked": len(row.assessment.asked),
                "title": title, "text": text}
    except Exception as exc:                               # noqa: BLE001
        return {"run": run_id, "error": repr(exc)}


if __name__ == "__main__":
    raise SystemExit(main())
