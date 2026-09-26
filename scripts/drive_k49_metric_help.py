#!/usr/bin/env python3
"""Knut, #182 5841606710 (2026-09-26): the metric help says how the rows of a
family relate ("Maximum ΔE00, lowest 95 % (P95)" can never be higher than
"Maximum ΔE00, all patches"), and both Custom columns put 4.50 on the
maximum. Driven ON SCREEN:

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k49_metric_help.py <out> <en|de>

The Report limits window is opened from the Measurement Report window's own
"Edit limits…" button's class on the demo project, shown (never exec'd), and
photographed with the Custom columns in view; then the help of four rows is
shown in the same info window the (i) icon opens, built and shown the way
`TooltipButton` builds it, and photographed. No modal is opened, so nothing
can wait for a click; a watchdog cancels anything unexpected.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

PROJECT = "Report-Limits-Every-Metric"
SHOW = ("all_de00_p95", "all_de00_max", "control_strip_de00_p95",
        "grey_balance_neutral_ramp_avg")


def script(lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN"})
        K36._install_watchdog(d, rec)
        yield 500
        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="verification")
        d.pump(1200)
        from core.i18n import tr
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        from ui.tooltip_button import _InfoDialog
        from workflow import compliance_sets as cs
        td = ThresholdsDialog(d.settings, d.win)
        td.resize(1500, 1000)
        td.show()
        td.raise_()
        yield 2500
        d.shot(td, f"{lang}-01-report-limits")
        rec["custom_max"] = {p: str(cs.custom_defaults(p)["all_de00_max"])
                             for p in ("iso_12647_7", "iso_12647_8")}
        rec["help"] = {}
        for k, rid in enumerate(SHOW, 2):
            row = cs.ROW_BY_ID[rid]
            body = td._row_help(row)
            rec["help"][rid] = body
            dlg = _InfoDialog(tr(row.label), body, td, 460)
            dlg.show()
            dlg.raise_()
            yield 1500
            d.shot(dlg, f"{lang}-{k:02d}-help-{rid}")
            dlg.close()
            yield 400
        td.close()
        yield 800
        (d.out / f"{lang}-help.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang = sys.argv[2]
    d = Drive(out, projects=[PROJECT], language=lang)
    rc = d.run(script(lang))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
