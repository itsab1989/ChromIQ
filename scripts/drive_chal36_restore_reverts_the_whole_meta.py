#!/usr/bin/env python3
"""Challenge round 36: Restore Used Chart reverts the run's WHOLE meta.json.

ON SCREEN. A real window, `scripts.onscreen_capture.capture_window`, two frames,
no ``widget.grab()`` and no ``QT_QPA_PLATFORM=offscreen``.

THE RULE IT BREAKS. `docs/design/per_run_description.md` §4, "Restore Used
Chart, the rules, exactly as specified", says the **Description field is
untouched** in all four of T4.1-T4.4, and T4.6 is an on-screen test of that.

THE SHAPE. `restore_slot` archives a side file before replacing it, but only
when that file is in `slot.live_files()` -- and for `slot_for_run` /
`slot_for_calibration` that list is filtered by `PROFILING_CHART_SUFFIXES`,
which does not contain `meta.json`. So `side_replaced` is always empty on those
two slots: nothing is archived, nothing is stashed, and the copy loop writes the
snapshot's `meta.json` straight over the live one. Every field written since the
measurement started goes with it, the run's frozen #182 limit set included.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal36/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal36/presets
    .venv/bin/python scripts/drive_chal36_restore_reverts_the_whole_meta.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)            # a real, on-screen platform
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The owner's machine holds a licence holder's real ISO tolerances. Forced, so
# no proof folder can carry a paid standard's numbers.
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    ROOT / "data" / "compliance_sets" / "iso12647.json")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/chromiq-chal36/settings.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/chromiq-chal36/presets")

OUT = Path(os.environ.get("CHAL36_OUT") or
           str(Path.home() / "Desktop" / "ChromIQ-beta30-proof"
               / "challenge-round-36"))

AS_MEASURED = "Hahnemuehle Photo Rag, as the chart was measured"
THE_KEEPER = "Canson Baryta 310, re-papered 22 Sept, THIS IS THE KEEPER"

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
    """Photograph the REAL window twice; the frames must match below the bar.

    Focus is dropped first: a focused ``QLineEdit`` blinks its text cursor, and
    two frames of a blinking caret are never identical however long they settle.
    """
    from PyQt6.QtWidgets import QApplication

    from scripts.onscreen_capture import capture_window
    OUT.mkdir(parents=True, exist_ok=True)
    fw = QApplication.focusWidget()
    if fw is not None:
        fw.clearFocus()
    pump(1500)
    a, b = OUT / f"{name}.png", OUT / f"{name}__frame2.png"

    def _try(path):
        why = "not attempted"
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
    work = Path(tempfile.mkdtemp(prefix="chal36-restore-"))
    shutil.copytree(src, work / src.name)
    note(f"subject: {work / src.name}   (a COPY; ~/ChromIQ is never touched)")

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
    run_id = [r.id for r in proj.all_runs()][0]
    run = proj.run(run_id)
    note(f"target: {src.name} / {run_id}")

    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run(run_id)
    tab._on_target_changed()
    pump(700)

    desc = tab._manual_run_desc_edit

    # ---- 1. the state the chart was measured in --------------------------
    desc.setText(AS_MEASURED)
    tab._save_target_text()
    pump(400)

    from workflow.chart_slot import slot_for_run
    from workflow.verify_chart_snapshot import restore_slot, snapshot_slot
    slot = slot_for_run(run)
    snapshot_slot(slot)                    # what starting a measurement does
    note(f"\nchart copied to {slot.snapshot_dir.name}/ : "
         f"{sorted(p.name for p in slot.snapshot_dir.iterdir())}")

    # ---- 2. the user works on ------------------------------------------
    from workflow.run_compliance import bind_run, run_limits
    bind_run(run, "chromiq_default", {})   # the run's first verification (D20)
    desc.setText(THE_KEEPER)
    tab._save_target_text()
    pump(600)
    tab._on_target_changed()
    pump(600)

    rl = run_limits(run, {})
    on_disk = json.loads((run.dir / "meta.json").read_text(encoding="utf-8"))
    note("\nBEFORE the press:")
    note(f"  Description on screen : {desc.text()!r}")
    note(f"  description on disk   : {on_disk.get('description')!r}")
    note(f"  run bound to a set    : {rl.bound}  ({len(rl.limits)} rows, "
         f"set {rl.set_id})")
    note(f"  compliance_bound_at   : {on_disk.get('compliance_bound_at')!r}")
    shot(w, "chal36-01-before-restore", pump)

    # ---- 3. Restore Used Chart, through the bar's own handler ------------
    note("\n--- pressing Restore Used Chart ---")
    result = ctl.restore_used_chart()
    note(f"  restore error: {result.error!r}" if result is not None
         else "  restore returned None")
    w._on_verify_chart_restored()          # the app's own listener
    pump(1500)

    rl2 = run_limits(run, {})
    after = json.loads((run.dir / "meta.json").read_text(encoding="utf-8"))
    note("\nAFTER the press:")
    note(f"  Description on screen : {desc.text()!r}")
    note(f"  description on disk   : {after.get('description')!r}")
    note(f"  run bound to a set    : {rl2.bound}  ({len(rl2.limits)} rows)")
    note(f"  compliance_bound_at   : {after.get('compliance_bound_at')!r}")
    lost = sorted(k for k in on_disk
                  if on_disk.get(k) not in (None, "", {}, [])
                  and after.get(k) != on_disk.get(k))
    note(f"  fields the press reverted: {lost}")
    old = run.dir / "old"
    note("  an archived copy in old/ : " + (
        str(sorted(str(p.relative_to(run.dir)) for p in old.rglob('meta.json')))
        if old.exists() else "old/ does not exist"))
    shot(w, "chal36-02-after-restore", pump)

    note("")
    note("SPEC: docs/design/per_run_description.md section 4, T4.1-T4.4 -- "
         "\"Description field: untouched\" in every row.")
    note(f"SCREEN: {desc.text()!r}")
    note(f"VERDICT: the Description on screen changed: "
         f"{desc.text() != THE_KEEPER}")

    (OUT / "driver-restore-reverts-meta.txt").write_text(
        "\n".join(NOTES) + "\n", encoding="utf-8")
    w.close()
    pump(400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
