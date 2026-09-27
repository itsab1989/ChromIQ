#!/usr/bin/env python3
"""K61 (Knut, #182 5851645723): "Which presets can be used for
verification", judged against ISO 12647-7, and the i1Pro presets of 648 and
783 patches on one page, which the window said have "too few patches in each
ninth of the page". Driven ON SCREEN, on any tree, so the same steps run
before and after the change.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k61_presets_evenness.py <out> <en|de> [set ...]

The project Report-Limits-Every-Metric is opened, Run type Verification and
run1 chosen on the bar, Create Chart put in Manual, and the window opened
with its own button. For each "Judged against" (default: ISO 12647-7 and
ChromIQ default), "Sort by" Most metrics, and each preset of the i1Pro group
with 648 or 783 patches on one page, the preset is selected, the pane
scrolled to "This chart cannot answer" (or to the top when nothing is
missing), and the window photographed by its window id. The pane's lines
are recorded as shown (``<lang>-presets.json``), with the highest "n of m"
any preset in the list reaches.

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

K36.DEADLINE_S = 1500
PROJECT = "Report-Limits-Every-Metric"
WANT = (648, 783)


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


def script(lang, sets):
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
        dlg.resize(1250, 900)
        yield 1200
        from PyQt6.QtWidgets import QAbstractItemView
        from core.i18n import tr
        for sid in sets:
            ft = dlg._type_combo.findData("t2_full_colour_check")
            if ft >= 0:
                dlg._type_combo.setCurrentIndex(ft)
            dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(sid))
            sort = getattr(dlg, "_sort_combo", None)
            if sort is not None and sort.count() > 1:
                sort.setCurrentIndex(sort.count() - 1)
            yield 1500
            t0 = time.monotonic()
            while dlg.waiting_count() and time.monotonic() - t0 < 300:
                yield 1000
            d.note(f"{sid}: {dlg.waiting_count()} presets still being laid out")
            best = max((len(r.assessment.answered) for _i, r in _items(dlg)
                        if r.assessment.checked), default=0)
            asked = max((len(r.assessment.asked) for _i, r in _items(dlg)
                         if r.assessment.checked), default=0)
            rec["cases"].setdefault(sid, {})["best"] = f"{best} of {asked}"
            picked = []
            for item, r in _items(dlg):
                if (r.builtin and r.pages == 1 and r.patches in WANT
                        and "i1Pro" in r.group and not r.pending):
                    picked.append((item, r))
            for k, (item, r) in enumerate(picked):
                dlg._tree.scrollToItem(
                    item, QAbstractItemView.ScrollHint.PositionAtCenter)
                dlg._tree.setCurrentItem(item)
                yield 1000
                # the first evenness metric's line, so its reason and lever
                # are in the picture; the heading when there is none
                from workflow import preset_eligibility as PE
                wants = ["✕  " + tr(PE.row_label(rid)) for rid in
                         ("uniformity_sd", "uniformity_de00_max_from_mean")]
                wants.append(tr("This chart cannot answer"))
                texts = {}
                for i in range(dlg._detail_layout.count()):
                    w = dlg._detail_layout.itemAt(i).widget()
                    if w is not None and hasattr(w, "text"):
                        texts.setdefault(w.text(), w)
                want = next((x for x in wants if x in texts), None)
                for i in range(dlg._detail_layout.count()):
                    w = dlg._detail_layout.itemAt(i).widget()
                    if w is not None and hasattr(w, "text") \
                            and w.text() == want:
                        dlg._detail_scroll.verticalScrollBar().setValue(
                            max(0, w.y() - 8))
                        break
                yield 900
                tag = f"{lang}-{sid}-{r.patches}-{k + 1}"
                rec["cases"][sid][tag] = {
                    "set": dlg._set_combo.currentText(),
                    "type": dlg._type_combo.currentText(),
                    "preset": r.label, "patches": r.patches,
                    "answered": len(r.assessment.answered),
                    "asked": len(r.assessment.asked),
                    "missing": [[rid, why]
                                for rid, why in r.assessment.missing],
                    "noise_counts": [list(x) for x in getattr(
                        r.assessment, "noise_counts", ())],
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
    sets = tuple(sys.argv[3:]) or ("iso_12647_7", "chromiq_default")
    d = Drive(out, projects=[PROJECT], language=lang)
    rc = d.run(script(lang, sets))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
