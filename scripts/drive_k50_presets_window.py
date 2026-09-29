#!/usr/bin/env python3
"""K50 (Knut, #182 5845519118, B8-1321): "Which presets can be used for
verification" groups the metrics that carry identical messages. Driven ON
SCREEN, on any tree, so the same steps run before and after the change.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k50_presets_window.py <out> <en|de>

The project Report-Limits-Every-Metric is opened, Run type Verification and
run1 chosen on the bar, Create Chart put in Manual, and the window opened with
its own button. Then, for "Judged against" ISO 12647-7 and All metrics:

* A: the first starred preset that cannot answer the two solid rows;
* B: the first preset that cannot answer both evenness rows for the same
  reason and with the same lever.

Each is selected in the list, the detail pane scrolled to "This chart cannot
answer", and the window photographed by its window id. The pane's lines are
recorded as shown (``<lang>-presets.json``).

**NOBODY HAS TO CLICK.** The window is opened through the tab's own button,
whose ``exec()`` runs on a queued call while this script keeps stepping; a
watchdog photographs and cancels any other window after three seconds; a
deadline ends the run whatever happens. Settings, presets and the output
folder are sandboxed by `userdrive.Drive`, and the ISO values file is forced
to the tree's own. The pack is copied, never written.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.append(HERE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 900
PROJECT = "Report-Limits-Every-Metric"
SETS = ("iso_12647_7", "all_metrics")
EVENNESS = ("uniformity_de00_max_from_mean", "uniformity_sd")


def _pane(dlg) -> "list[str]":
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text"):
            out.append(w.text())
    return out


def _items(dlg):
    from PyQt6.QtCore import Qt
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            child = head.child(j)
            r = child.data(0, Qt.ItemDataRole.UserRole)
            if r is not None:
                yield child, r


def _same_messages(rows_why, PVD, PE):
    """Whether every (row, reason) pair prints the same reason and lever."""
    said = {(PVD.reason_line(w), PE.row_remedy(r, w)) for r, w in rows_why}
    return len(said) == 1


def _pick(dlg, which):
    from ui.dialogs import preset_verification_dialog as PVD
    from workflow import preset_eligibility as PE
    for item, r in _items(dlg):
        if r.pending or not r.assessment.checked or r.is_current_chart:
            continue
        miss = dict(r.assessment.missing)
        if which == "A":
            solids = PE.gamut_only_rows()
            if r.starred and all(s in miss for s in solids) \
                    and _same_messages([(s, miss[s]) for s in solids], PVD, PE):
                return item, r
        else:
            if all(e in miss for e in EVENNESS) and _same_messages(
                    [(e, miss[e]) for e in EVENNESS], PVD, PE):
                return item, r
    return None, None


def script(lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN",
                    "cases": {}})
        K36._install_watchdog(d, rec)
        yield 500
        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="verification")
        d.goto_tab("chart")
        tab = d.win._tab_chart
        if not tab._manual_btn.isChecked():
            tab._manual_btn.click()
        yield 1500
        d.later(tab._preset_verify_btn.click)
        yield 5000
        dlg = K36._wait(d, "PresetVerificationDialog")
        if dlg is None:
            d.note("NO PRESETS WINDOW")
            rec["error"] = "no presets window"
            return
        dlg.resize(1250, 860)
        yield 1200
        from PyQt6.QtWidgets import QAbstractItemView
        chosen: dict = {}
        for sid in SETS:
            any_type = dlg._type_combo.findData("any_report_type")
            if any_type >= 0:
                dlg._type_combo.setCurrentIndex(any_type)
            dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(sid))
            yield 1500
            t0 = time.monotonic()
            while dlg.waiting_count() and time.monotonic() - t0 < 180:
                yield 1000
            d.note(f"{sid}: {dlg.waiting_count()} presets still being laid out")
            for which in ("A", "B"):
                item, r = None, None
                if which in chosen:
                    for it, rr in _items(dlg):
                        if rr.label == chosen[which]:
                            item, r = it, rr
                            break
                else:
                    item, r = _pick(dlg, which)
                if item is None:
                    d.note(f"   case {which}: no preset found under {sid}")
                    continue
                chosen[which] = r.label
                dlg._tree.scrollToItem(
                    item, QAbstractItemView.ScrollHint.PositionAtCenter)
                dlg._tree.setCurrentItem(item)
                yield 900
                # bring "This chart cannot answer" to the top of the pane
                from core.i18n import tr
                want = tr("This chart cannot answer")
                for i in range(dlg._detail_layout.count()):
                    w = dlg._detail_layout.itemAt(i).widget()
                    if w is not None and hasattr(w, "text") \
                            and w.text() == want:
                        # the heading at the top of the pane, so the
                        # groups under it are in the picture
                        dlg._detail_scroll.verticalScrollBar().setValue(
                            max(0, w.y() - 8))
                        break
                yield 900
                tag = f"{lang}-{sid}-{which}"
                rec["cases"][tag] = {
                    "set": dlg._set_combo.currentText(),
                    "type": dlg._type_combo.currentText(),
                    "preset": r.label,
                    "missing": [[rid, why] for rid, why in r.assessment.missing],
                    "pane": _pane(dlg),
                }
                d.shot(dlg, tag)
        dlg.reject()
        yield 1500
        (d.out / f"{lang}-presets.json").write_text(
            json.dumps(rec["cases"], indent=2, ensure_ascii=False),
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
