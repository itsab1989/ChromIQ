#!/usr/bin/env python3
"""K17 (Knut, beta 34): Verification, measurements from two runs ticked, and
the report type could not be chosen at all.

Driven as a user on Report-Limits-Threshold-Series: Verification, run1,
Tools > Measurement Report, "Add profile's measurements..." picking one of
run2's dated measurements, then choose "Grey and tone check". Recorded: which
controls are enabled, Generate's tooltip, the type the page is built as, and
that neither run's meta.json changed on disk.

    python scripts/drive_k17_two_runs_type.py <out-dir>
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _meta(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.glob("runs/run*/*.json"))}


def script(d):
    root = d.work / NAME
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"report window open: {dlg is not None}")
    from PyQt6.QtWidgets import QPushButton
    add = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower().startswith("add profile"))
    run2_ti3 = sorted((root / "runs/run2/verifications").glob("*/*.ti3"))[0]
    # WHAT THE APP DID WITH THE FILE, recorded rather than guessed.
    _orig_append = dlg._append_source
    def _traced(ti3, origin=None):
        try:
            got = _orig_append(ti3, origin=origin)
        except Exception as exc:                          # noqa: BLE001
            d.note(f"   [trace] _append_source({ti3}) RAISED {exc!r}")
            raise
        d.note(f"   [trace] _append_source({Path(ti3).name}) -> {got}; "
               f"sources now {len(dlg._sources)}")
        return got
    dlg._append_source = _traced
    import ui.dialogs.measurement_report_dialog as _M
    _orig_ofd = _M.open_files_dialog
    def _ofd(*a, **k):
        got = _orig_ofd(*a, **k)
        d.note(f"   [trace] open_files_dialog returned {got}")
        return got
    _M.open_files_dialog = _ofd
    d.later(add.click)
    yield 300
    d.answer_file(run2_ti3, name="01-add-run2-measurement")
    import time as _t
    t0 = _t.monotonic()
    while _t.monotonic() - t0 < 20 and len(dlg._distinct_run_dirs()) < 2:
        yield 250
    d.note(f"second run loaded after {_t.monotonic() - t0:.1f} s")
    yield 1500
    d.note(f"loaded runs: {len(dlg._distinct_run_dirs())}; ticked rows: "
           f"{len(dlg._runs_for_report())}; several: {dlg._several_runs()}")
    d.note(f"type pulldown enabled: {dlg._type_combo.isEnabled()}; "
           f"Generate enabled: {dlg._generate_btn.isEnabled()}")
    d.note(f"Generate tooltip: {dlg._generate_btn.toolTip()!r}")
    d.record.update(type_enabled=dlg._type_combo.isEnabled(),
                    generate_tip=dlg._generate_btn.toolTip())
    d.shot(dlg, "02-two-runs-ticked")
    before = _meta(root)
    ok = d.pick(dlg._type_combo, "grey and tone")
    yield 2500
    d.note(f"picked Grey and tone check: {ok}; page built as: "
           f"{dlg._report_type_now()}")
    after = _meta(root)
    d.note(f"meta.json files changed on disk: "
           f"{[k for k in before if before[k] != after.get(k)]}")
    d.record.update(type_now=dlg._report_type_now(),
                    meta_changed=[k for k in before if before[k] != after.get(k)])
    d.shot(dlg, "03-grey-and-tone-chosen")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    sys.exit(d.run(script))
