"""Are chart / measure / build-profile / print settings kept INDIVIDUAL
between runs, a verification and the calibration? — Knut, 2026-08-11:

    "Did you find in your testing that all the chart settings, measure
    settings and print profile tab settings changed and were kept individual
    between runs / calibration / verification run types? That is the backbone
    of the whole feature between runs. Then there is bound to be bugs there."

This is the on-screen driver the test plan names
(``docs/design/per_target_settings_test_plan.md`` §1): the REAL app, real
styling, driven the way a person would. For every target it visits every
storing tab, mutates EVERY parameter the tab's own registry yields (nothing
hand-picked — spec §1 S1.1), files it by leaving the tab, and then proves:

  I1   revisiting each target shows ITS OWN values on every tab — twice,
       in a different visiting order each round (the §2.0 backbone)
  I2   a marker value imprinted on one target appears in NO other target's
       store file on disk (test-plan A5)
  I3   the §2.1 hazard: edit, switch away WITHOUT saving, switch back —
       the edit was filed to the target it belongs to, not the next one
  I4   a target with nothing stored opens on defaults, never on the
       previous target's values (spec §4 S4/S5)

    python -u scripts/drive_per_target_settings.py
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HARD_STOP_S = 600


def _arm_hard_stop() -> None:
    def _die() -> None:
        print(f"\n!! hard stop after {HARD_STOP_S}s — the app blocked",
              flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    t = threading.Timer(HARD_STOP_S, _die)
    t.daemon = True
    t.start()


_arm_hard_stop()

FINDINGS: list[tuple[str, bool, str]] = []


def check(step: str, ok: bool, detail: str = "") -> bool:
    FINDINGS.append((step, ok, detail))
    print(f"  {'OK  ' if ok else 'FAIL'} {step}")
    if detail and not ok:
        print(f"         {detail}")
    return ok


def note(step: str, detail: str = "") -> None:
    FINDINGS.append((step, True, detail))
    print(f"  ..   {step}" + (f"\n         {detail}" if detail else ""))


def _find_subject() -> "Path | None":
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob("*/Demo-Full-RGB")):
        if (cand / "cal").is_dir() and (cand / "project.json").is_file():
            return cand
    return None


# ---------------------------------------------------------------------------
# Value mutation — deterministic per (target-seed, key), validated by readback
# ---------------------------------------------------------------------------

def _mutate_value(v, seed: int, salt: int):
    if isinstance(v, bool):
        return (seed + salt) % 2 == 0
    if isinstance(v, int):
        return max(0, (v % 7) + 2 + seed * 3 + (salt % 3))
    if isinstance(v, float):
        return round(max(0.0, (v % 3.0) + 0.25 * (seed + 1) + 0.05 * (salt % 4)), 2)
    if isinstance(v, str):
        # Strings are often combo entries where only listed values stick;
        # the readback after apply decides what the target's fingerprint
        # actually is, so an unaccepted write is simply not part of it.
        return v
    return v


def _mutate_record(rec, seed: int, salt: int):
    # Build Profile's preset pair stores flat {key: value}; the other tabs
    # store {"enabled": …, "value": …} records. Handle both.
    if not isinstance(rec, dict):
        return _mutate_value(rec, seed, salt)
    out = dict(rec)
    if "repeats" in out and isinstance(out["repeats"], list) and out["repeats"]:
        reps = [dict(r) for r in out["repeats"]]
        r0 = reps[0]
        if "value" in r0:
            r0["value"] = _mutate_value(r0["value"], seed, salt)
        if "enabled" in r0:
            r0["enabled"] = True
        out["repeats"] = reps
        return out
    if "enabled" in out:
        out["enabled"] = (seed + salt) % 3 != 0     # both states get exercised
    if "value" in out:
        out["value"] = _mutate_value(out["value"], seed, salt)
    return out


def main() -> int:      # noqa: PLR0915, PLR0912
    src = _find_subject()
    if src is None:
        print("No cached Demo-Full-RGB. Run the test suite once to build it.")
        return 2
    work = Path(tempfile.mkdtemp(prefix="per-target-drive-"))
    shutil.copytree(src, work / src.name)
    print(f"subject: {work / src.name}")

    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass
    from PyQt6.QtCore import QSettings as _QS
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
    ini = Path(tempfile.mkdtemp()) / "drive.ini"
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(work))
    s.set("calibration_mode", True)
    apply_appearance(app, None, "light")

    from core.measurement_target import (RUN_TYPE_CALIBRATION,
                                         RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)
    from ui.main_window import MainWindow
    w = MainWindow(s)
    apply_appearance(app, w, "light")
    w.resize(1700, 1050)
    w.show()

    def settle(n=40):
        for _ in range(n):
            app.processEvents()

    # ---- modal watchdog ---------------------------------------------------
    # "This chart already has a measurement" (and any other modal) stops a
    # driver dead — Sebastian: "this window always stops your tests. even in
    # the past". Cancel is the button that changes nothing, so the drive
    # keeps measuring what the app does, not what the dialog did.
    from PyQt6.QtCore import QTimer
    dismissed: list[str] = []

    def _dismiss_modal() -> None:
        m = app.activeModalWidget()
        if m is not None and m.isVisible():
            dismissed.append(m.windowTitle())
            print(f"  [modal] cancelled: {m.windowTitle()!r}", flush=True)
            m.reject()

    _watchdog = QTimer()
    _watchdog.timeout.connect(_dismiss_modal)
    _watchdog.start(150)

    settle(80)
    ctl = w._target_bar._ctl
    w._file_mgr.set_target_name("Demo-Full-RGB")
    w._target_bar.refresh()
    settle()

    proj = w._file_mgr.project()
    runs = [r.id for r in proj.all_runs()]
    print(f"runs in the project: {runs}")
    if len(runs) < 2:
        print("need at least two runs")
        return 2
    run_a, run_b = runs[0], runs[1]

    # The four targets Knut names: two profiling runs, a verification, and
    # the calibration.
    TARGETS = [
        ("run-A profiling",   RUN_TYPE_PROFILING,    run_a),
        ("run-B profiling",   RUN_TYPE_PROFILING,    run_b),
        ("run-A verification", RUN_TYPE_VERIFICATION, run_a),
        ("calibration",       RUN_TYPE_CALIBRATION,  None),
    ]

    TABS = [("Create Chart", w._tab_chart),
            ("Measure", w._tab_measure),
            ("Build Profile", w._tab_profile),
            ("Print Chart", w._tab_print)]

    def select(run_type, run_id) -> None:
        """Switch the bar the way its handlers do — MainWindow's own
        write-then-load wiring runs, exactly as for a user's click."""
        ctl.set_run_type(run_type)
        if run_id is not None:
            ctl.set_profile_run(run_id)
        settle()

    def activate(tab) -> None:
        w._tabs.setCurrentWidget(tab)
        settle()

    # ---- per-tab adapters: (snapshot, apply) on the SCREEN ----------------
    from workflow import measure_settings as ms
    from workflow import per_target_settings as pts

    def chart_snap():
        return pts.snapshot(w._tab_chart)

    def chart_apply(data):
        pts.apply(w._tab_chart, data)

    def measure_snap():
        return ms.snapshot(w._tab_measure)

    def measure_apply(data):
        ms.apply(w._tab_measure, data)

    def profile_snap():
        return w._tab_profile._m_collect_preset_data()

    def profile_apply(data):
        w._tab_profile._m_apply_preset_data(data)

    def print_snap():
        t = w._tab_print
        return {"colour": t._cm_user_colour or "",
                "intent": t._cm_selected_intent(),
                "route": "external" if t._cm_route_ext_rb.isChecked()
                else "chromiq"}

    ADAPTERS = {"Create Chart": (chart_snap, chart_apply),
                "Measure": (measure_snap, measure_apply),
                "Build Profile": (profile_snap, profile_apply),
                "Print Chart": (print_snap, None)}

    # ------------------------------------------------------------ Phase 1
    print("\n=== Phase 1 — imprint distinct values on every target ===")
    expected: dict[str, dict[str, dict]] = {}
    VOLATILE: dict[str, set] = {}
    for seed, (tname, rt, rid) in enumerate(TARGETS):
        print(f"\n-- target: {tname}")
        select(rt, rid)
        expected[tname] = {}
        for tab_name, tab in TABS:
            activate(tab)
            snap_fn, apply_fn = ADAPTERS[tab_name]
            if apply_fn is None:
                # Print Chart stores only the Colour/intent/route trio, and
                # parts of it can be forced by the chart on this target —
                # record what the screen holds rather than trying to steer it.
                expected[tname][tab_name] = snap_fn()
                note(f"{tname} / {tab_name}: recorded as-is "
                     f"({expected[tname][tab_name]})")
                continue
            base = snap_fn()
            if not base:
                note(f"{tname} / {tab_name}: EMPTY snapshot — nothing to "
                     "imprint (worth knowing)")
                expected[tname][tab_name] = {}
                continue
            mutated = {k: _mutate_record(rec, seed, salt)
                       for salt, (k, rec) in enumerate(sorted(base.items()))}
            apply_fn(mutated)
            settle(80)
            got = snap_fn()          # what the screen actually accepted
            # Same-target round trip: leave the tab (files it) and come back
            # (loads it) WITHOUT any target switch. A key that does not
            # survive this is recomputed by the tab itself (Auto patch count
            # recalculates targen -f from the layout) — it cannot carry a
            # cross-target verdict and is excluded, but listed.
            activate(TABS[(TABS.index((tab_name, tab)) + 1) % len(TABS)][1])
            activate(tab)
            got2 = snap_fn()
            unstable = {k for k in set(got) | set(got2)
                        if got.get(k) != got2.get(k)}
            if unstable:
                VOLATILE.setdefault(tab_name, set()).update(unstable)
                note(f"{tname} / {tab_name}: {sorted(unstable)} are "
                     "recomputed by the tab itself — excluded from verdicts")
            expected[tname][tab_name] = got2
            changed = sum(1 for k in base if got2.get(k) != base[k])
            note(f"{tname} / {tab_name}: {len(base)} parameters, "
                 f"{changed} visibly changed by the imprint")
        # leaving the last tab files it; go somewhere neutral to fire W6
        activate(w._tab_check_refine if hasattr(w, "_tab_check_refine")
                 else TABS[0][1])

    # ------------------------------------------------------------ Phase 2
    print("\n=== Phase 2 — every target shows ITS OWN values (two rounds) ===")
    orders = [TARGETS, list(reversed(TARGETS))]
    for rnd, order in enumerate(orders, start=1):
        for tname, rt, rid in order:
            select(rt, rid)
            for tab_name, tab in TABS:
                activate(tab)
                snap_fn, _ = ADAPTERS[tab_name]
                got = snap_fn()
                want = expected[tname][tab_name]
                skip = VOLATILE.get(tab_name, set())
                diffs = {k for k in set(got) | set(want)
                         if k not in skip and got.get(k) != want.get(k)}
                check(f"round {rnd}: {tname} / {tab_name} shows its own "
                      f"values", not diffs,
                      f"{len(diffs)} of {len(want)} differ: "
                      f"{sorted(list(diffs))[:6]}"
                      + (f" e.g. got {got.get(sorted(diffs)[0])!r} want "
                         f"{want.get(sorted(diffs)[0])!r}" if diffs else ""))

    # cross-target distinctness: the imprints must actually differ, or the
    # round above proves nothing
    for i in range(len(TARGETS)):
        for j in range(i + 1, len(TARGETS)):
            a, b = TARGETS[i][0], TARGETS[j][0]
            for tab_name, _tab in TABS[:3]:
                ea, eb = expected[a][tab_name], expected[b][tab_name]
                if ea and eb:
                    check(f"imprints differ: {a} vs {b} / {tab_name}",
                          ea != eb, "identical imprints — sweep too weak")

    # ------------------------------------------------------------ Phase 3
    print("\n=== Phase 3 — where each section actually lives on disk ===")
    # Parse the stores properly (the naive substring scan of the first run
    # false-alarmed on coincidental values). The interesting question after
    # phase 2 is structural: WHICH file holds each target's sections.
    stores = {"run-A profiling": work / src.name / "runs" / run_a / "meta.json",
              "run-B profiling": work / src.name / "runs" / run_b / "meta.json",
              "calibration": work / src.name / "cal" / "meta.json"}
    skip_chart = VOLATILE.get("Create Chart", set())
    for tname, jf in stores.items():
        if not jf.is_file():
            check(f"{tname}: {jf.relative_to(work)} exists", False, "missing")
            continue
        body = json.loads(jf.read_text())
        chart = body.get("create_chart_settings") or {}
        want = expected[tname]["Create Chart"]
        diffs = {k for k in set(chart) | set(want)
                 if k not in skip_chart and chart.get(k) != want.get(k)}
        check(f"{tname}: meta.json create_chart_settings == its imprint",
              not diffs, f"{len(diffs)} differ: {sorted(diffs)[:8]}")
    # F1 (fixed 2026-08-11): the verification's sections live in their OWN file
    ver_store = work / src.name / "runs" / run_a / "verifications" / "meta.json"
    if ver_store.is_file():
        vbody = json.loads(ver_store.read_text())
        vchart = vbody.get("create_chart_settings") or {}
        want = expected["run-A verification"]["Create Chart"]
        diffs = {k for k in set(vchart) | set(want)
                 if k not in skip_chart and vchart.get(k) != want.get(k)}
        check("run-A verification: verifications/meta.json == its imprint "
              "(own store, F1)", not diffs,
              f"{len(diffs)} differ: {sorted(diffs)[:8]}")
    else:
        check("run-A verification has its own store file (F1)", False,
              f"{ver_store.relative_to(work)} missing")

    # ------------------------------------------------------------ Phase 4
    print("\n=== Phase 4 — the §2.1 hazard: edit, switch away, switch back ===")
    # Use a row the tab does not recompute (targen -f is rewritten by Auto
    # patch count, which made the first version of this check unreadable).
    select(RUN_TYPE_PROFILING, run_a)
    activate(w._tab_chart)

    def stable_row():
        skip = VOLATILE.get("Create Chart", set())
        for pw in w._tab_chart._manual_widgets.get("printtarg", []):
            if f"printtarg{pw.flag}" in skip:
                continue
            v = pw.get_raw_value()
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return pw
        raise AssertionError("no stable numeric printtarg row")

    row = stable_row()
    row_flag = row.flag
    old_val = row.get_raw_value()
    # A spin row keeps only values its step allows (printtarg -t steps by
    # 50) — write the candidate and use what the widget actually accepted.
    row.set_value((old_val or 0) + 50)
    settle()
    probe_val = row.get_raw_value()
    if probe_val == old_val:
        row.set_value(max(0, (old_val or 0) - 50))
        settle()
        probe_val = row.get_raw_value()
    select(RUN_TYPE_PROFILING, run_b)          # no explicit save in between
    activate(w._tab_chart)
    got_b = next(pw for pw in w._tab_chart._manual_widgets["printtarg"]
                 if pw.flag == row_flag).get_raw_value()
    check(f"run-B did NOT inherit run-A's unsaved edit (printtarg {row_flag})",
          got_b != probe_val, f"run-B shows {got_b}")
    select(RUN_TYPE_PROFILING, run_a)
    activate(w._tab_chart)
    got_a = next(pw for pw in w._tab_chart._manual_widgets["printtarg"]
                 if pw.flag == row_flag).get_raw_value()
    check(f"run-A's edit was filed to run-A (write-then-load, §2.1, "
          f"printtarg {row_flag})",
          got_a == probe_val, f"run-A shows {got_a}, want {probe_val}")

    # ------------------------------------------------------------ Phase 5
    print("\n=== Phase 5 — a target with nothing stored opens on defaults ===")
    ver_b_meta = None
    select(RUN_TYPE_VERIFICATION, run_b)       # never imprinted above
    activate(w._tab_measure)
    got = measure_snap()
    same_as_a = got == expected["run-A profiling"]["Measure"]
    same_as_ver_a = got == expected["run-A verification"]["Measure"]
    check("run-B verification (nothing stored) is NOT run-A's values",
          not same_as_a and not same_as_ver_a,
          "a fresh target opened on another target's values (S4/S5 broken)")

    # ------------------------------------------------------------ summary
    print("\n=== summary ===")
    fails = [f for f in FINDINGS if not f[1]]
    print(f"{len(FINDINGS)} checks, {len(fails)} failed")
    for step, _ok, detail in fails:
        print(f"  FAIL {step}\n       {detail}")
    w.close()
    settle()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
