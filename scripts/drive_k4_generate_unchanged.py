#!/usr/bin/env python3
"""K4 (Knut, beta 34): Generate report on a selected report with no setting
changed created a new report without asking.

Driven as a user on Report-Limits-Threshold-Series: Verification, run1,
Tools > Measurement Report opens on the run's saved report; nothing is
touched; Generate report is pressed. The question must appear with the
headline "Nothing was changed for the selected report"; Update is clicked;
no new report file may appear, and the previous content must be in old/.

    python scripts/drive_k4_generate_unchanged.py <out-dir>
"""
from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _live(root):
    return {p: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("reports/report_*.json")}


def script(d):
    from PyQt6.QtWidgets import QPushButton
    root = d.work / NAME
    d.open_project(NAME)
    d.set_bar(run_type="Verification", run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.note(f"Report shown: {dlg._saved_combo.currentText()!r}")
    d.note(f"red 'settings changed' line visible: {dlg._stale_label.isVisible()}")
    before = _live(root)
    gen = next(b for b in dlg.findChildren(QPushButton)
               if b.text().replace("&", "").lower() == "generate report")
    d.later(gen.click)
    yield 300
    said = d.answer("update", name="01-the-question")
    d.record["question"] = said
    t0 = time.monotonic()
    after = _live(root)
    while time.monotonic() - t0 < 20 and after == before:
        yield 250
        after = _live(root)
    new = [str(p.relative_to(root)) for p in after if p not in before]
    changed = [p for p in before if p in after and before[p] != after[p]]
    kept = [p for p in changed
            if any(hashlib.sha256(c.read_bytes()).hexdigest() == before[p]
                   for c in (p.parent / "old").glob(f"*/{p.name}"))]
    d.note(f"new report files: {new}")
    d.note(f"rewritten: {len(changed)}, previous kept in old/: {len(kept)}")
    d.note(f"Report shown after: {dlg._saved_combo.currentText()!r}")
    d.record.update(new=new, rewritten=len(changed), kept=len(kept))
    d.shot(dlg, "02-after-update")
    dlg.close()
    yield 500


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    rc = d.run(script)
    q = d.record.get("question") or ""
    ok = (q.startswith("Nothing was changed for the selected report")
          and not d.record.get("new") and d.record.get("rewritten")
          and d.record.get("kept") == d.record.get("rewritten"))
    print("AS EXPECTED" if ok else "NOT AS EXPECTED")
    sys.exit(rc or (0 if ok else 1))
