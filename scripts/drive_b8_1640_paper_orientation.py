#!/usr/bin/env python3
"""B8-1640 on screen: the Create Chart paper list in another language.

Opens Create Chart, photographs the window with the paper list closed and then
open, and records every row's text and the code it carries as its data. The
orientation word is the language's; the data stays the paper code.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1640_paper_orientation.py <out> <lang>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 300


def script(d):
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    yield 600
    d.goto_tab("chart")
    tab = d.win._tab_chart
    yield 1000
    combo = tab._paper_combo
    rec["rows"] = [{"text": combo.itemText(i), "data": combo.itemData(i)}
                   for i in range(combo.count())]
    rec["current"] = {"text": combo.currentText(), "data": combo.currentData()}
    d.shot(d.win, "01-create-chart-paper-closed")
    combo.showPopup()
    yield 900
    d.shot(combo.view(), "02-create-chart-paper-list-open")
    combo.hidePopup()
    yield 400


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    d = Drive(out, projects=[], language=lang, appearance="light")
    rc = d.run(script)
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
