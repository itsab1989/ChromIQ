#!/usr/bin/env python3
"""Challenge round 34b: two runs the window calls the same set, one document.

CLAUDE.md: on screen is the default. No ``QT_QPA_PLATFORM=offscreen`` here, no
``widget.grab()``; every picture comes from
``scripts.onscreen_capture.capture_window``, twice, and the two frames have to
match below the title bar.

THE STATE THIS BUILDS is the one a real user upgrading to beta 30 is in:

* ``run1`` was bound by an older ChromIQ. Its stored copy of ChromIQ default
  has 30 rows and carries the grey pair as ``should`` limits.
* ``run4`` holds the same measurements and is bound by THIS build. Its copy has
  32 rows (the two repeatability rows of 2026-09-21) and the grey pair as
  ordinary values (the same 2026-09-21 ruling).

Nobody edited anything. ``compliance_sets.is_edited`` says so, and the window
prints "ChromIQ default (recommended)" with no "(edited)" for both. The
question this driver asks is what the DOCUMENT does with the two together.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal34b/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal34b/presets
    .venv/bin/python scripts/drive_chal34b_the_yardstick_split.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)          # a real, on-screen platform
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The owner's machine holds a licence holder's real ISO tolerances in
# ~/Library/Preferences/ChromIQ/compliance/. Forced here, never left to a
# shell, so no proof folder can end up carrying a paid standard's numbers.
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    ROOT / "data" / "compliance_sets" / "iso12647.json")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE",
                      "/tmp/chromiq-chal34b/settings.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/chromiq-chal34b/presets")

from core.settings import AppSettings                            # noqa: E402
from scripts.capture_screens import build_app, pump              # noqa: E402
from scripts.onscreen_capture import capture_window              # noqa: E402
from ui.theme import apply_appearance                            # noqa: E402

SRC = Path("/tmp/chromiq-b29r/out/Report-Limits-Threshold-Series")
DST = Path("/tmp/chromiq-chal34b/proj/Report-Limits-Threshold-Series")
OUT = Path(os.environ.get("CHAL34B_OUT") or
           str(Path.home() / "Desktop" / "ChromIQ-beta30-proof"
               / "challenge-round-34b"))

NOTES: list[str] = []


def note(line: str) -> None:
    print(line)
    NOTES.append(line)


def shot(win, name: str) -> bool:
    """Photograph the real window twice; the frames must match below the bar."""
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
    TITLE_BAR_PX = 60
    same = a.read_bytes() == b.read_bytes()
    if not same:
        from PyQt6.QtGui import QImage
        ia, ib = QImage(str(a)), QImage(str(b))
        if not ia.isNull() and ia.size() == ib.size():
            same = all(ia.pixel(x, y) == ib.pixel(x, y)
                       for y in range(TITLE_BAR_PX, ia.height(), 2)
                       for x in range(0, ia.width(), 2))
            if same:
                note("  identical below the title bar (window-server repaint "
                     "above it only)")
    if same:
        b.unlink(missing_ok=True)
    note(f"  shot {name}.png  two frames identical: {same}")
    return same


# ---------------------------------------------------------------------------
def build_the_project() -> None:
    if DST.exists():
        shutil.rmtree(DST)
    DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, DST)
    shutil.copytree(DST / "runs" / "run1", DST / "runs" / "run4")
    meta = DST / "runs" / "run4" / "meta.json"
    m = json.loads(meta.read_text(encoding="utf-8"))
    m["run_id"] = "run4"
    for k in ("compliance_set_id", "compliance_set_label",
              "compliance_thresholds", "compliance_bound_at"):
        m.pop(k, None)
    meta.write_text(json.dumps(m, indent=2), encoding="utf-8")
    # a run bound today has no report saved by the older build
    for p in (DST / "runs" / "run4").rglob("report_*.json"):
        p.unlink()
    from core.file_manager import Run
    from workflow.run_compliance import bind_run
    bind_run(Run.for_dir(DST / "runs" / "run4"), "chromiq_default", None)


def text_of(dlg) -> str:
    return dlg._view.toPlainText() if hasattr(dlg, "_view") else ""


def covers_sentence(txt: str) -> str:
    for line in txt.splitlines():
        if "covers" in line and "measurement" in line:
            return line.strip()
    return "(no 'covers' sentence in the document)"


def main() -> int:
    if not SRC.is_dir():
        note(f"demo pack missing: {SRC}")
        return 1
    build_the_project()

    app = build_app()
    settings = AppSettings()
    apply_appearance(app, None, "dark")

    from core.file_manager import Run
    from workflow.run_compliance import run_limits
    from workflow.measurement_report import yardstick_key
    from workflow import compliance_sets as cs

    l1 = run_limits(Run.for_dir(DST / "runs" / "run1"), None)
    l4 = run_limits(Run.for_dir(DST / "runs" / "run4"), None)
    note("THE TWO RUNS, as the app itself describes them")
    note(f"  run1: set={l1.set_id} label={l1.set_label!r} "
         f"rows={len(l1.limits)} edited={l1.edited}")
    note(f"  run4: set={l4.set_id} label={l4.set_label!r} "
         f"rows={len(l4.limits)} edited={l4.edited}")
    shared = sorted(set(l1.limits) & set(l4.limits))
    note(f"  rows only run4 defines: "
         f"{sorted(set(l4.limits) - set(l1.limits))}")
    note(f"  rows both define whose stored JSON differs: "
         f"{[k for k in shared if l1.limits[k] != l4.limits[k]]}")
    note(f"  yardstick_key calls them one set: "
         f"{yardstick_key({'set_id': l1.set_id, 'thresholds': cs.limits_to_json(l1.limits)}) == yardstick_key({'set_id': l4.set_id, 'thresholds': cs.limits_to_json(l4.limits)})}")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings)
    dlg.resize(1280, 1400)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(900)

    picks: list[Path] = []
    for run in ("run1", "run4"):
        vd = sorted((DST / "runs" / run / "verifications").glob("20*_*"))
        for v in vd[:3]:
            ti3 = next(iter(sorted(v.glob("*.ti3"))), None)
            if ti3 is not None:
                picks.append(ti3)
    note(f"\nloading {len(picks)} measurements, three from each run")
    for p in picks:
        dlg._append_source(p, origin=p)
    dlg._rebuild_from_sources()
    pump(2500)

    lst = dlg._profile_list
    from PyQt6.QtCore import Qt
    ticked = sum(1 for i in range(lst.count())
                 if lst.item(i).checkState() == Qt.CheckState.Checked)
    note(f"  rows in the list: {lst.count()}, ticked: {ticked}")

    runs = dlg._runs_for_report() if hasattr(dlg, "_runs_for_report") else []
    kept, dropped = dlg._one_limit_set(
        [r for r in dlg._history] if hasattr(dlg, "_history") else [])
    note(f"  _one_limit_set over the loaded history: kept {len(kept)}, "
         f"left out {len(dropped)}")

    txt = text_of(dlg)
    note(f"  the document's own sentence: {covers_sentence(txt)}")
    for line in txt.splitlines():
        if "Judged against" in line:
            note(f"  head line: {line.strip()}")
            break
    shot(dlg, "01_two_runs_one_document")

    (OUT / "driver-log.txt").write_text("\n".join(NOTES) + "\n",
                                        encoding="utf-8")
    (OUT / "document.txt").write_text(txt, encoding="utf-8")
    print("\n" + "=" * 62 + "\nSUMMARY\n" + "=" * 62)
    print("\n".join(NOTES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
