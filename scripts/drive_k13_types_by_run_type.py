#!/usr/bin/env python3
"""K13 (Knut, beta 34): which report types each run type offers.

Driven as a user on Report-Limits-Threshold-Series, twice: Profiling run1 and
Verification run1, each time Tools > Measurement Report, "New report...", and
the Report type pulldown opened and photographed. Recorded: every entry, and
whether it can be picked, and the tooltip of one greyed entry.

    python scripts/drive_k13_types_by_run_type.py <out-dir>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

NAME = "Report-Limits-Threshold-Series"


def _entries(dlg):
    from PyQt6.QtCore import Qt
    c, m = dlg._type_combo, dlg._type_combo.model()
    out = []
    for i in range(c.count()):
        if not c.itemData(i):
            continue
        out.append((c.itemText(i), bool(m.item(i).isEnabled()),
                    str(c.itemData(i, Qt.ItemDataRole.ToolTipRole) or "")))
    return out


def one(d, run_type, tag):
    d.set_bar(run_type=run_type, run="run1")
    yield 800
    d.launch_tool("measurement_report")
    yield 4000
    dlg = d.top_dialog("MeasurementReportDialog")
    d.pick(dlg._saved_combo, "new report")
    yield 1500
    ents = _entries(dlg)
    d.note(f"[{tag}] kind={dlg._window_kind()} current="
           f"{dlg._type_combo.currentText()!r}")
    for text, on, tip in ents:
        d.note(f"   {'PICKABLE' if on else 'greyed  '} {text}"
               + ("" if on else f"   tip: {tip[:110]!r}"))
    d.record[tag] = {"current": dlg._type_combo.currentText(),
                     "entries": ents}
    dlg._type_combo.showPopup()
    yield 900
    view = dlg._type_combo.view()
    d.shot(view, f"{tag}-pulldown-open")
    dlg._type_combo.hidePopup()
    yield 300
    d.shot(dlg, f"{tag}-window")
    dlg.close()
    yield 800


def script(d):
    d.open_project(NAME)
    yield from one(d, "Profiling", "A-profiling")
    yield from one(d, "Verification", "B-verification")


if __name__ == "__main__":
    d = Drive(Path(sys.argv[1]), projects=[NAME])
    sys.exit(d.run(script))
