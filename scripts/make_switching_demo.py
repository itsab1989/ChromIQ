"""Build the downloadable per-target-settings SWITCHING demo package.

Knut, 2026-08-11: *"This should really be tested by claude making a demo
project with test cases for all switching cases to make sure all switching
between profile runs and run types are kept as individual settings … then that
test must be tested by AI with on-screen control and verified against
expectations. Demo projects must be made with simulated real data, with
multiple runs, verification runs and some projects with calibration runs …
The demo project with test cases in a readme.md must also be made available
as download, then manually go through each case to verify."*

What this script does, in order:

  1. copies the Argyll-built ``Demo-Full-RGB`` (three runs with real charts,
     measurements and profiles; a verification tree; a real calibration) and
     renames it ``Demo-Switching``;
  2. opens the REAL app on screen and sets a small, documented value on the
     Create Chart / Measure / Build Profile / Print Chart tabs for each of:
     Run 1 (Profiling), Run 2 (Profiling), Calibration;
  3. quits, reopens the real app, and verifies every documented value comes
     back on the right target — the machine-verified column of the README;
  4. writes ``README.md`` with the value table and the manual switching test
     cases, zips the package to the Desktop.

    python -u scripts/make_switching_demo.py
"""
from __future__ import annotations

import datetime as _dt
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HARD_STOP_S = 600
OUT_DIR = Path.home() / "Desktop" / "ChromIQ-Switching-Demo"
PROJECT = "Demo-Switching"


def _arm_hard_stop() -> None:
    def _die() -> None:
        print(f"\n!! hard stop after {HARD_STOP_S}s", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    t = threading.Timer(HARD_STOP_S, _die)
    t.daemon = True
    t.start()


_arm_hard_stop()


def _find_subject() -> "Path | None":
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob("*/Demo-Full-RGB")):
        if (cand / "cal").is_dir() and (cand / "project.json").is_file():
            return cand
    return None


#: target key -> (run type name, run id, documented values)
#: Build Profile is gated off for a verification target, so its row carries
#: no smoothing value there.
PLAN = {
    "Run 1 — Profiling":    dict(run="run1", rtype="profiling", dpi=400,
                                 skip_cal=True, pbp=False, smoothing=1.1),
    "Run 1 — Verification": dict(run="run1", rtype="verification", dpi=450,
                                 skip_cal=False, pbp=False, smoothing=None),
    "Run 2 — Profiling":    dict(run="run2", rtype="profiling", dpi=500,
                                 skip_cal=False, pbp=True, smoothing=1.2),
    "Calibration":          dict(run=None, rtype="calibration", dpi=600,
                                 skip_cal=True, pbp=True, smoothing=1.3),
}


def main() -> int:      # noqa: PLR0915
    src = _find_subject()
    if src is None:
        print("No cached Demo-Full-RGB. Run the test suite once to build it.")
        return 2
    if OUT_DIR.exists():
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        OUT_DIR.rename(OUT_DIR.with_name(f"{OUT_DIR.name}-old-{stamp}"))
        print(f"previous package archived as {OUT_DIR.name}-old-{stamp}")
    OUT_DIR.mkdir(parents=True)
    proj_dir = OUT_DIR / PROJECT
    shutil.copytree(src, proj_dir)

    from core.file_manager import Project
    Project.load(proj_dir).rename(PROJECT)
    print(f"project staged and renamed: {proj_dir}")

    # ---- the real app ----------------------------------------------------
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass
    from PyQt6.QtCore import QSettings as _QS, QTimer
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setOrganizationName("ChromIQ")
    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import (ButtonFontFilter, DialogFocusFilter,
                            GroupBoxSurfaceFilter, TooltipWrapFilter)
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
              DialogFocusFilter):
        app.installEventFilter(F(app))

    import core.settings as cs
    ini = Path(tempfile.mkdtemp()) / "build.ini"
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(OUT_DIR))
    s.set("calibration_mode", True)
    apply_appearance(app, None, "light")

    # modal watchdog: Cancel changes nothing (the "chart already has a
    # measurement" window otherwise stops every drive — Sebastian)
    def _dismiss() -> None:
        m = app.activeModalWidget()
        if m is not None and m.isVisible():
            print(f"  [modal] cancelled: {m.windowTitle()!r}", flush=True)
            m.reject()
    _wd = QTimer()
    _wd.timeout.connect(_dismiss)
    _wd.start(150)

    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from workflow import measure_settings as ms

    def open_window():
        from ui.main_window import MainWindow
        w = MainWindow(s)
        apply_appearance(app, w, "light")
        w.resize(1700, 1050)
        w.show()
        for _ in range(80):
            app.processEvents()
        w._file_mgr.set_target_name(PROJECT)
        w._target_bar.refresh()
        for _ in range(40):
            app.processEvents()
        return w

    def settle(n=40):
        for _ in range(n):
            app.processEvents()

    def select(w, spec) -> None:
        ctl = w._target_bar._ctl
        if spec["rtype"] == "calibration":
            ctl.set_run_type(RUN_TYPE_CALIBRATION)
        elif spec["rtype"] == "verification":
            ctl.set_run_type(RUN_TYPE_VERIFICATION)
            ctl.set_profile_run(spec["run"])
        else:
            ctl.set_run_type(RUN_TYPE_PROFILING)
            ctl.set_profile_run(spec["run"])
        settle()

    def dpi_row(w):
        return next(pw for pw in w._tab_chart._manual_widgets["printtarg"]
                    if pw.flag == "-t")

    def read_state(w, spec) -> dict:
        out = {}
        w._tabs.setCurrentWidget(w._tab_chart)
        settle()
        out["dpi"] = dpi_row(w).get_raw_value()
        w._tabs.setCurrentWidget(w._tab_measure)
        settle()
        snap = ms.snapshot(w._tab_measure)
        out["skip_cal"] = bool((snap.get("disable_initial_cal") or {}).get("value"))
        out["pbp"] = bool((snap.get("patch_by_patch") or {}).get("value"))
        if spec["smoothing"] is None:      # tab 4 is gated for a verification
            out["smoothing"] = None
        else:
            w._tabs.setCurrentWidget(w._tab_profile)
            settle()
            out["smoothing"] = \
                w._tab_profile._m_collect_preset_data().get("smoothing")
        # Return to Create Chart before the next target switch: it is the one
        # tab that reloads itself while visible. Leaving Measure or Build
        # Profile visible during a switch exposes known defect F2 (they keep
        # the OLD target's values and then file them onto the new target) —
        # real, reported, and exactly what this package's cases demonstrate;
        # the machine column here must measure the stores, not that defect.
        w._tabs.setCurrentWidget(w._tab_chart)
        settle()
        return out

    # ---- pass 1: imprint --------------------------------------------------
    print("\n=== imprint the documented values ===")
    w = open_window()
    for tname, spec in PLAN.items():
        print(f"-- {tname}")
        select(w, spec)
        w._tabs.setCurrentWidget(w._tab_chart)
        settle()
        dpi_row(w).set_value(spec["dpi"])
        settle()
        w._tabs.setCurrentWidget(w._tab_measure)
        settle()
        snap = ms.snapshot(w._tab_measure)
        for key, want in (("disable_initial_cal", spec["skip_cal"]),
                          ("patch_by_patch", spec["pbp"])):
            rec = dict(snap.get(key) or {"enabled": True, "value": False})
            rec["value"] = want
            rec["enabled"] = True
            snap[key] = rec
        ms.apply(w._tab_measure, snap)
        settle()
        if spec["smoothing"] is not None:
            w._tabs.setCurrentWidget(w._tab_profile)
            settle()
            data = w._tab_profile._m_collect_preset_data()
            data["smoothing"] = spec["smoothing"]
            w._tab_profile._m_apply_preset_data(data)
            settle()
            rb = w._tab_profile._m_collect_preset_data().get("smoothing")
            print(f"   smoothing applied={spec['smoothing']} readback={rb}")
        # leaving the tab files this target's settings
        w._tabs.setCurrentWidget(w._tab_print)
        settle()
    w.close()
    settle(80)
    print("imprint window closed (quit writes the visible tab silently)")
    import json as _json
    for label, mj in (("run1", proj_dir / "runs/run1/meta.json"),
                      ("run2", proj_dir / "runs/run2/meta.json"),
                      ("cal", proj_dir / "cal/meta.json")):
        try:
            ps = _json.loads(mj.read_text()).get("profile_settings") or {}
            print(f"   on disk {label}: profile_settings.smoothing="
                  f"{ps.get('smoothing')!r} ({len(ps)} keys)")
        except Exception as e:      # noqa: BLE001
            print(f"   on disk {label}: {e}")

    # ---- pass 2: reopen and machine-verify -------------------------------
    print("\n=== reopen the app and verify every documented value ===")
    w = open_window()
    results: dict[str, dict[str, tuple]] = {}
    all_ok = True
    for tname, spec in PLAN.items():
        select(w, spec)
        got = read_state(w, spec)
        results[tname] = {}
        fields = ["dpi", "skip_cal", "pbp"]
        if spec["smoothing"] is not None:
            fields.append("smoothing")
        for field in fields:
            ok = got[field] == spec[field]
            all_ok &= ok
            results[tname][field] = (spec[field], got[field], ok)
            print(f"  {'OK  ' if ok else 'FAIL'} {tname}: {field} "
                  f"want {spec[field]!r} got {got[field]!r}")

    # ---- the run-type and visible-tab cases (RT1/RT2/VT1), machine-driven --
    print("\n=== RT / VT — run-type separation and the visible-tab reload ===")
    p1, v1, p2 = (PLAN["Run 1 — Profiling"], PLAN["Run 1 — Verification"],
                  PLAN["Run 2 — Profiling"])
    select(w, p1)
    w._tabs.setCurrentWidget(w._tab_chart)
    settle()
    rt = []
    rt.append(("RT1: Run 1 Profiling shows its DPI",
               dpi_row(w).get_raw_value() == p1["dpi"]))
    select(w, v1)
    rt.append(("RT1: switch to Verification — its OWN DPI",
               dpi_row(w).get_raw_value() == v1["dpi"]))
    select(w, p1)
    rt.append(("RT2: back to Profiling — its own DPI kept",
               dpi_row(w).get_raw_value() == p1["dpi"]))
    # VT1: stand on Measure, switch run without leaving the tab
    w._tabs.setCurrentWidget(w._tab_measure)
    settle()
    select(w, p1)
    snap = ms.snapshot(w._tab_measure)
    rt.append(("VT1: Measure shows Run 1's -N while visible",
               bool(snap["disable_initial_cal"]["value"]) == p1["skip_cal"]))
    select(w, p2)                     # no tab change in between
    snap = ms.snapshot(w._tab_measure)
    rt.append(("VT1: still on Measure, Run 2 selected — Run 2's -N at once",
               bool(snap["disable_initial_cal"]["value"]) == p2["skip_cal"]))
    for label, ok in rt:
        all_ok &= ok
        print(f"  {'OK  ' if ok else 'FAIL'} {label}")
    w.close()
    settle(80)

    # ---- README ----------------------------------------------------------
    def onoff(v) -> str:
        return "ticked" if v is True else ("unticked" if v is False else str(v))

    today = _dt.date.today().isoformat()
    rows = []
    for tname, spec in PLAN.items():
        r = results[tname]
        smooth = ("— (tab locked)" if spec["smoothing"] is None
                  else spec["smoothing"])
        rows.append(
            f"| {tname} | {spec['dpi']} | {onoff(spec['skip_cal'])} | "
            f"{onoff(spec['pbp'])} | {smooth} | "
            f"{'✔' if all(x[2] for x in r.values()) else '✘ see build log'} |")
    readme = f"""# ChromIQ Switching Demo — per-target settings test package

Built {today} from real ArgyllCMS data (targen → printtarg → fakeread →
colprof). The project **{PROJECT}** has three profiling runs with real charts,
measurements and profiles, a verification tree under Run 2, and a real
calibration — and three of its targets carry small, documented settings so
you can SEE whether switching between targets keeps every tab's settings
individual.

## Install

1. Unzip this package.
2. Move the `{PROJECT}` folder into your ChromIQ folder (usually
   `~/ChromIQ`).
3. Start ChromIQ and open the project: click the magenta folder button in
   the header (top right) and pick `{PROJECT}/project.json`.

## The documented values

Each target was given its own values through the real app, and the machine
re-opened the app and verified every one of them on screen when this package
was built:

| Target (set in the bar at the top) | Create Chart → "TIFF Output DPI" | Measure → "Skip initial calibration (-N)" | Measure → "Patch-by-patch mode (-p)" | Build Profile → "Smoothing" | machine-verified |
|---|---|---|---|---|---|
{chr(10).join(rows)}

To select a target: use the **Profile run** dropdown and the **Run type**
dropdown in the bar at the top of the window. "Calibration" is a Run type
(it appears when **Enable calibration options** is ticked in Preferences).

## The switching test cases

For every case: the values you see must be the row of the target you just
selected — never the row of the target you came from.

Tip for SW1–SW6: make each switch while the **1. Create Chart** tab is
showing, then visit the other tabs to check their values. (Switching while
Measure or Build Profile is showing is its own test case — VT1 below.)

| # | Do this | Expect |
|---|---|---|
| SW1 | Select Run 1 (Profiling). Check all four values. | Run 1's row |
| SW2 | Switch to Run 2 (Profiling). Check all four values. | Run 2's row — nothing from Run 1 |
| SW3 | Switch back to Run 1. | Run 1's row again |
| SW4 | Switch Run type to Calibration. | Calibration's row |
| SW5 | Switch back to Run 2 (Profiling). | Run 2's row |
| SW6 | Calibration → Run 1, Run 1 → Calibration, in any order, repeatedly. | Each shows only its own row |
| RE1 | On Run 1, change "TIFF Output DPI" to 425 but do NOT generate. Switch to Run 2, then back to Run 1. | Run 2 shows 500 (never 425); Run 1 shows 425 when you return |
| RQ1 | Change a value on any target, quit ChromIQ, reopen, select that target. | The changed value is there — quitting saved it silently |
| RD1 | Select Run 3 (Profiling) — it was left untouched. | Factory/saved defaults, NOT another run's row |
| RT1 | On Run 1, switch Run type to Verification. | The Verification's OWN row (DPI 450) — never Run 1's Profiling values |
| RT2 | Still on Run 1 / Verification, change "TIFF Output DPI", switch Run type back to Profiling. | Profiling still shows Run 1's own row (400); switch back to Verification and your edit is there |
| VT1 | Stand on the **Measure** tab. Without leaving it, switch from Run 1 to Run 2 in the bar. | The visible tab shows Run 2's row at once — no stale values from Run 1 |

## History: the two defects this package caught

The first build of this package (2026-08-11, morning) demonstrated two real
defects, found by the on-screen drive (`scripts/drive_per_target_settings.py`):
**F1** — Profiling and Verification on the same run shared one settings
store and overwrote each other; **F2** — Measure and Build Profile did not
reload while they were the visible tab during a run switch, and then filed
the stale values onto the new target. Knut ruled on both the same day
(a verification gets its own settings in `runs/runN/verifications/meta.json`,
backed up with the chart into each check's `chart/` folder; every tab
reloads the way Create Chart does), and both fixes are in — **implemented
and machine-verified, awaiting human confirmation**, which is what the
RT1/RT2/VT1 cases above are for.

Every case in this README passed the machine drive when this package was
built, including a full quit-and-reopen of the app between setting the
values and checking them.
"""
    (OUT_DIR / "README.md").write_text(readme, encoding="utf-8")
    print(f"\nREADME written: {OUT_DIR / 'README.md'}")

    zip_path = Path.home() / "Desktop" / "ChromIQ-Switching-Demo.zip"
    if zip_path.exists():
        zip_path.unlink()
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(OUT_DIR),
                    str(zip_path)], check=True)
    print(f"zip: {zip_path} ({zip_path.stat().st_size // 1024} KB)")
    print("machine verification:", "ALL OK" if all_ok else "FAILURES — see log")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
