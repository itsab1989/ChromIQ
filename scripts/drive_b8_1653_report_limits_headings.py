#!/usr/bin/env python3
"""B8-1653 on screen: the Report Limits column headings keep to their columns.

Opens Report Limits non-modally in the given language, records for each column
heading its width and the width of its longest word in the bold font it is
shown in, checks that no heading runs past the left edge of the next one, and
photographs the window.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1653_report_limits_headings.py <out> <lang>
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
    from PyQt6.QtGui import QFont, QFontMetrics
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    yield 600
    dlg = ThresholdsDialog(d.win._settings, d.win)
    dlg.show()
    yield 1500
    g = dlg._head_grid
    heads = []
    for ci in range(2, g.columnCount()):
        item = g.itemAtPosition(0, ci)
        if item is None or item.widget() is None:
            continue
        hdr = item.widget()
        if not hdr.isVisible():
            continue
        bold = QFont(hdr.font())
        bold.setBold(True)
        fm = QFontMetrics(bold)
        longest = max((fm.horizontalAdvance(w) for w in hdr.text().split()),
                      default=0)
        heads.append({"text": hdr.text(), "x": hdr.x(), "width": hdr.width(),
                      "longest_word": longest,
                      "word_fits": longest <= hdr.contentsRect().width()})
    rec["headings"] = heads
    rec["all_words_fit"] = all(h["word_fits"] for h in heads)
    d.shot(dlg, "01-report-limits")
    dlg.close()
    yield 400


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    d = Drive(out, projects=[], language=lang, appearance="dark")
    rc = d.run(script)
    (out / "record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
