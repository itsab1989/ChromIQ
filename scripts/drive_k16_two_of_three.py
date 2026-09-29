#!/usr/bin/env python3
"""K16 (Knut, beta 34): 2 of 3 measurements ticked, Generate, Create New, and
the new report was flagged "One date" with the ticks collapsed to one.

Driven as a user on Report-Limits-Threshold-Series: Profiling, run1, Tools >
Measurement Report, untick one of the three profiling measurements, Generate
report, answer "Create New". Recorded: the new entry's name in "Report shown",
the saved document's scope and member count on disk, and the ticks after.

    python scripts/drive_k16_two_of_three.py <out-dir>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _docs(root: Path) -> dict:
    out = {}
    for p in root.glob("runs/*/reports/report_*.json"):
        try:
            out[str(p.relative_to(root))] = json.loads(p.read_text("utf-8"))
        except Exception:                                  # noqa: BLE001
            pass
    return out


def _ticked(dlg) -> list:
    from PyQt6.QtCore import Qt
    rows = []
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key is not None:
            it = dlg._profile_list.item(i)
            rows.append((it.text(), it.checkState() == Qt.CheckState.Checked))
    return rows


def script(d):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QPushButton
    root = d.work / NAME
    d.open_project(NAME)
    d.set_bar(run_type="Profiling", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"report window open: {dlg is not None}")
    d.pick(dlg._saved_combo, "new report")
    yield 1500
    rows = _ticked(dlg)
    d.note(f"list rows (text, ticked): {rows}")
    # untick the LAST ticked row, the way a user clicks one box
    idx = [i for i, (k, _s, key) in enumerate(dlg._list_rows)
           if k == "run" and key is not None]
    dlg._profile_list.item(idx[-1]).setCheckState(Qt.CheckState.Unchecked)
    yield 1500
    d.note(f"after unticking one: {_ticked(dlg)}")
    d.shot(dlg, "01-two-of-three-ticked")
    before = set(_docs(root))
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    d.later(gen.click)
    yield 300
    d.answer("create new", name="02-question", within_ms=4000)
    t0 = time.monotonic()
    while time.monotonic() - t0 < 20 and set(_docs(root)) == before:
        yield 250
    new = {k: v for k, v in _docs(root).items() if k not in before}
    d.note(f"new report files: {list(new)}")
    for k, v in new.items():
        doc = v.get("document") or {}
        d.note(f"   {k}: scope={doc.get('scope')!r} "
               f"members={len(doc.get('measurements') or [])} "
               f"type={doc.get('type')!r}")
    yield 1500
    d.note(f"Report shown: {dlg._saved_combo.currentText()!r}")
    d.note(f"ticks after: {_ticked(dlg)}")
    d.record.update(new={k: (v.get('document') or {}) for k, v in new.items()},
                    shown=dlg._saved_combo.currentText(), ticks=_ticked(dlg))
    d.shot(dlg, "03-after-create-new")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    sys.exit(d.run(script))
