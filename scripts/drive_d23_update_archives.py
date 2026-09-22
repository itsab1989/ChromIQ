#!/usr/bin/env python3
"""D23 on the Update path, driven as a user on Report-Limits-Threshold-Series.

Tools > Measurement Report on run1 (Verification), tick "Show detailed data
for each run" (a changed setting), Generate report, answer Update. Then, on
the sandbox copy's disk: every report file the press rewrote must have its
PREVIOUS bytes under reports/old/<stamp>/, and the log must name the archive.

    python scripts/drive_d23_update_archives.py <out-dir>
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _snapshot(root: Path) -> dict:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("reports/report_*.json")}


def script(d):
    root = d.work / NAME
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    before = _snapshot(root)
    olds_before = len(list(root.rglob("reports/old/*/report_*.json")))
    d.note(f"live report files before: {len(before)}; archived copies: "
           f"{olds_before}")
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"report window open: {dlg is not None}")
    d.note(f"report shown: {dlg._saved_combo.currentText()!r}")
    from PyQt6.QtWidgets import QCheckBox, QPushButton
    box = next(c for c in dlg.findChildren(QCheckBox)
               if c.text().startswith("Show detailed data"))
    box.click()
    yield 1200
    d.shot(dlg, "01-setting-changed")
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    d.later(gen.click)
    yield 300
    d.answer("update", name="02-update-or-new")
    # POLL THE DISK, do not guess how long the press takes: the first version
    # of this driver slept 4 s, read the disk before the write had landed and
    # reported "0 files rewritten" beside a log line naming the archive.
    import time as _t
    t0 = _t.monotonic()
    after = _snapshot(root)
    while _t.monotonic() - t0 < 20 and after == before:
        yield 250
        after = _snapshot(root)
    d.note(f"disk changed after {_t.monotonic() - t0:.1f} s")
    changed = [p for p in before if p in after and before[p] != after[p]]
    kept = 0
    missing = []
    for p in changed:
        old_hash = before[p]
        if any(hashlib.sha256(c.read_bytes()).hexdigest() == old_hash
               for c in (p.parent / "old").glob(f"*/{p.name}")):
            kept += 1
        else:
            missing.append(str(p.relative_to(root)))
    d.note(f"files rewritten by Update: {len(changed)}")
    d.note(f"   of those, previous content kept in old/: {kept}")
    d.note(f"   NOT kept: {missing}")
    d.note(f"new live files (should be 0 for an Update): "
           f"{len([p for p in after if p not in before])}")
    d.record.update(rewritten=len(changed), kept=kept, not_kept=missing)
    d.shot(dlg, "03-after-update")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    arch = [ln for ln in d.record.get("log_warnings_and_errors", [])]
    sys.exit(rc or (0 if d.record.get("rewritten") and not
                    d.record.get("not_kept") else 1))
