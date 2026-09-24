#!/usr/bin/env python3
"""Challenge round 35: a per-target setting the stored blob has never heard of.

ON SCREEN. A real window, `scripts.onscreen_capture.capture_window`, two frames,
no ``widget.grab()`` and no ``QT_QPA_PLATFORM=offscreen``.

THE SHAPE. `workflow/per_target_settings.apply` writes only the keys the stored
blob HAS. `docs/design/per_target_settings.md` §7 names the risk in one
direction only -- *"A. A stored setting that no longer exists"* -- and the code
follows it: an unknown key is ignored. The mirror has no rule and no code: a
parameter added to `data/parameters.yaml` AFTER a target was written is absent
from that target's blob, so nothing writes it, and the widget keeps whatever the
target the user just LEFT put there.

Every project on disk was written before the next parameter is added, so this is
the state of every existing project on the day any parameter is added.

The subject is `targen -f`, the patch count: per-target, visible, numeric, and
not one of the six rows Run type = Calibration owns.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal35/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal35/presets
    .venv/bin/python scripts/drive_chal35_a_newer_row_leaks_between_targets.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)            # a real, on-screen platform
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The owner's machine holds a licence holder's real ISO tolerances. Forced, so
# no proof folder can carry a paid standard's numbers.
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    ROOT / "data" / "compliance_sets" / "iso12647.json")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/chromiq-chal35/settings.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/chromiq-chal35/presets")

OUT = Path(os.environ.get("CHAL35_OUT") or
           str(Path.home() / "Desktop" / "ChromIQ-beta30-proof"
               / "challenge-round-35"))

NOTES: list[str] = []


def note(line: str) -> None:
    print(line)
    NOTES.append(line)


def _find_subject() -> "Path | None":
    cache = Path(os.environ.get("TMPDIR", "/tmp")) / "chromiq-demo-projects-cache"
    for cand in sorted(cache.glob("*/Demo-Full-RGB")):
        if (cand / "project.json").is_file():
            return cand
    return None


def shot(win, name: str, pump) -> bool:
    """Photograph the REAL window twice; the frames must match below the bar."""
    from scripts.onscreen_capture import capture_window
    OUT.mkdir(parents=True, exist_ok=True)
    pump(1500)
    a, b = OUT / f"{name}.png", OUT / f"{name}__frame2.png"

    def _try(path):
        for _ in range(3):
            ok, why = capture_window(win, path, settle=1.2)
            if ok:
                return True, ""
            pump(700)
        return False, why

    ok, why = _try(a)
    if not ok:
        note(f"  CAPTURE REFUSED {name}: {why}")
        return False
    pump(1200)
    ok2, why2 = _try(b)
    if not ok2:
        note(f"  CAPTURE REFUSED {name} (2nd frame): {why2}")
        return False
    same = a.read_bytes() == b.read_bytes()
    if not same:
        from PyQt6.QtGui import QImage
        ia, ib = QImage(str(a)), QImage(str(b))
        if not ia.isNull() and ia.size() == ib.size():
            same = all(ia.pixel(x, y) == ib.pixel(x, y)
                       for y in range(60, ia.height(), 2)
                       for x in range(0, ia.width(), 2))
            if same:
                note("  identical below the title bar (title-bar repaint only)")
    if same:
        b.unlink(missing_ok=True)
    note(f"  shot {name}.png  two frames identical: {same}")
    return same


def main() -> int:
    src = _find_subject()
    if src is None:
        note("No cached Demo-Full-RGB. Run the test suite once to build it.")
        return 2
    work = Path(tempfile.mkdtemp(prefix="chromiq-chal35-pertarget-"))
    shutil.copytree(src, work / src.name)
    note(f"subject: {work / src.name}")

    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
    except ImportError:
        pass
    from PyQt6.QtCore import QSettings as _QS
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    app = QApplication.instance() or QApplication(sys.argv[:1])
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
    ini = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
    ini.parent.mkdir(parents=True, exist_ok=True)
    cs.QSettings = lambda *a, **k: _QS(str(ini), _QS.Format.IniFormat)
    s = cs.AppSettings()
    s.set("custom_output_path", str(work))     # SANDBOXED, never ~/ChromIQ
    apply_appearance(app, None, "light")

    from core.measurement_target import RUN_TYPE_PROFILING
    from ui.main_window import MainWindow
    w = MainWindow(s)
    apply_appearance(app, w, "light")
    w.resize(1500, 1000)
    w.show()
    w.raise_()
    w.activateWindow()

    import time

    def pump(ms=400):
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    pump(2500)
    tab, ctl = w._tab_chart, w._target_bar._ctl
    w._file_mgr.set_target_name(src.name)
    w._target_bar.refresh()
    pump(800)

    proj = w._file_mgr.project()
    runs = [r.id for r in proj.all_runs()]
    note(f"runs in the project: {runs}")
    if len(runs) < 2:
        note("need at least two runs")
        return 2
    run_a, run_b = runs[0], runs[1]

    def patch_row():
        for pw in tab._manual_widgets.get("targen", []):
            if pw.flag == "-f":
                return pw
        raise AssertionError("no targen -f row")

    def select(run_id):
        ctl.set_run_type(RUN_TYPE_PROFILING)
        ctl.set_profile_run(run_id)
        tab._on_target_changed()
        pump(700)

    # ---- both runs get a full stored blob, written by TODAY's build --------
    select(run_a)
    patch_row().set_value(111)
    tab.save_target_settings()
    pump(400)
    select(run_b)
    patch_row().set_value(222)
    tab.save_target_settings()
    pump(400)
    note(f"\n{run_a} stored 111, {run_b} stored 222 (both blobs complete)")

    # ---- the control: run B's OWN value comes back ------------------------
    select(run_a)
    got_a = patch_row().get_raw_value()
    select(run_b)
    got_b = patch_row().get_raw_value()
    note(f"  CONTROL  {run_a} -> {got_a}   then {run_b} -> {got_b}")
    control_ok = (got_a == 111 and got_b == 222)
    note(f"  CONTROL passes: {control_ok}")

    # ---- now make run B's blob predate the parameter ----------------------
    # Exactly what a build written before `targen -f` existed left on disk:
    # the key is simply not in the blob. Nothing else is touched.
    rb = proj.run(run_b)
    meta = rb.load_meta()
    blob = dict(meta.create_chart_settings or {})
    from workflow.per_target_settings import params_for
    key = next(p.key for p in params_for(tab) if p.tool == "targen" and p.flag == "-f")
    note(f"\nthe key removed from {run_b}'s stored blob: {key!r}")
    note(f"  keys before: {len(blob)}")
    blob.pop(key, None)
    note(f"  keys after : {len(blob)}")
    meta.create_chart_settings = blob
    rb.save_meta(meta)

    # ---- the measurement --------------------------------------------------
    select(run_a)
    patch_row().set_value(777)                 # a value that belongs to run A
    tab.save_target_settings()
    pump(500)
    left_with = patch_row().get_raw_value()
    note(f"\n{run_a} is left showing {left_with}")
    select(run_b)
    shown = patch_row().get_raw_value()
    note(f"{run_b} -- whose blob has never heard of this row -- now shows {shown}")

    leaked = (shown == 777)
    note("")
    if leaked:
        note("  FAULT: the value belongs to the target the user just LEFT.")
        note("  §4 S4/S5 say a target with nothing stored for a row opens on "
             "its defaults; a PARTIAL blob has no rule and takes the previous "
             "target's value instead.")
    else:
        note(f"  no leak: {run_b} shows {shown}, not {run_a}'s 777")

    # ---- and it reaches DISK on the next write ----------------------------
    tab.save_target_settings()
    pump(400)
    after = dict(proj.run(run_b).load_meta().create_chart_settings or {})
    filed = after.get(key)
    note(f"\nafter the ordinary write {run_b}'s stored blob holds "
         f"{key} = {json.dumps(filed)}")

    shot(w, "chal35-01-per-target-leak", pump)

    w.close()
    pump(400)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "driver-per-target-leak.txt").write_text("\n".join(NOTES) + "\n",
                                                    encoding="utf-8")
    print("\n" + "=" * 62 + "\nSUMMARY\n" + "=" * 62)
    print("\n".join(NOTES))
    return 1 if (leaked or not control_ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())
