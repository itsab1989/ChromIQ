#!/usr/bin/env python3
"""B8-1650 on screen: the Output labels of Create Chart fit their text.

Opens Create Chart in the given language, in Guided and then Manual, and for
each mode records the width of the "Printer profile project name:" column
against the width its text needs in the font it is shown in. Photographs both.

    CHROMIQ_LOG_DIR=<sandbox> python scripts/drive_b8_1650_output_labels_fit.py <out> <lang>
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


def _measure(fitter):
    lbl = fitter._anchor
    fm = lbl.fontMetrics()
    need = fm.horizontalAdvance(lbl.text())
    return {"text": lbl.text(), "width": lbl.width(),
            "text_needs": need, "font_px": lbl.font().pixelSize(),
            "font_pt": lbl.font().pointSizeF(),
            "width_before_the_fit": fitter._floor,
            "text_fitted_before": need <= fitter._floor - lbl.contentsMargins().left() - lbl.contentsMargins().right() - 2 * lbl.margin(),
            "fits": need <= lbl.contentsRect().width()}


def script(d):
    rec = d.record
    assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
    K36._install_watchdog(d, rec)
    yield 600
    d.goto_tab("chart")
    tab = d.win._tab_chart
    yield 1000
    tab._user_switch_mode("guided")
    yield 800
    rec["guided"] = _measure(tab._guided_label_fitter)
    d.shot(d.win, "01-guided-output")
    tab._user_switch_mode("manual")
    yield 1000
    rec["manual"] = _measure(tab._manual_label_fitter)
    d.shot(d.win, "02-manual-output")
    yield 300


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
