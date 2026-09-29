#!/usr/bin/env python3
"""K51 (Knut, #182 5846167083, analysis 3): the verification star under
rule (4) with his modifications. Driven ON SCREEN, on any tree, so the same
steps run before and after the change.

    CHROMIQ_DEMO_PACK=<pack> CHROMIQ_TREE=<tree> \\
        python drive_k51_star.py <out> <en|de>

The project Report-Limits-Every-Metric is opened, Run type Verification and
run1 chosen on the bar, Create Chart put in Manual, and "Which presets can be
used for verification?" opened with its own button; Report type Any, Judged
against All metrics. Once every preset is laid out:

* the window is photographed at the top, where the ★ line says what the star
  means;
* "Show only the presets made for verification" is ticked and the list is
  photographed group by group;
* the i1Pro 3 Plus presets A4-308p-2pages and A4-154p-1page are selected in
  turn and the window photographed with the detail pane.

Every preset's star, pages and patches as the window shows them are recorded
(``<lang>-stars.json``).

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

K36.DEADLINE_S = 1200
PROJECT = "Report-Limits-Every-Metric"
PICK = ("A4-308p-2pages-Portrait-w16.0mm", "A4-154p-1page-Portrait-w16.0mm")


def _items(dlg):
    from PyQt6.QtCore import Qt
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            child = head.child(j)
            r = child.data(0, Qt.ItemDataRole.UserRole)
            if r is not None:
                yield head, child, r


def _pane(dlg) -> "list[str]":
    out = []
    for i in range(dlg._detail_layout.count()):
        w = dlg._detail_layout.itemAt(i).widget()
        if w is not None and hasattr(w, "text"):
            out.append(w.text())
    return out


def script(lang):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "tree": TREE, "mode": "ON SCREEN"})
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
        any_type = dlg._type_combo.findData("any_report_type")
        if any_type >= 0:
            dlg._type_combo.setCurrentIndex(any_type)
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData("all_metrics"))
        yield 1500
        t0 = time.monotonic()
        while dlg.waiting_count() and time.monotonic() - t0 < 300:
            yield 1000
        rec["still_laying_out"] = dlg.waiting_count()
        d.note(f"{dlg.waiting_count()} presets still being laid out")
        yield 1500
        from PyQt6.QtWidgets import QAbstractItemView, QLabel
        star_lines = [w.text() for w in dlg.findChildren(QLabel)
                      if w.text().startswith("★")]
        rec["star_line"] = star_lines
        dlg._tree.scrollToTop()
        yield 600
        d.shot(dlg, f"{lang}-01-window-top")
        rec["stars"] = [{"group": h.text(0), "preset": r.label,
                         "patches": r.patches, "pages": r.pages,
                         "starred": bool(r.starred)}
                        for h, _c, r in _items(dlg) if not r.is_current_chart]
        # -- only the starred ones, group by group
        dlg._only_star.setChecked(True)
        yield 2000
        heads = [dlg._tree.topLevelItem(i)
                 for i in range(dlg._tree.topLevelItemCount())]
        rec["starred_shown"] = {}
        for k, head in enumerate(heads, 1):
            head.setExpanded(True)
            rec["starred_shown"][head.text(0)] = [
                head.child(j).text(0) for j in range(head.childCount())]
            dlg._tree.scrollToItem(
                head, QAbstractItemView.ScrollHint.PositionAtTop)
            yield 900
            d.shot(dlg, f"{lang}-02-only-starred-{k:02d}")
        dlg._only_star.setChecked(False)
        yield 2000
        rec["picked"] = {}
        for k, want in enumerate(PICK, 1):
            hit = next(((c, r) for h, c, r in _items(dlg)
                        if r.label == want and "3 Plus" in h.text(0)), None)
            if hit is None:
                d.note(f"   {want}: not in the list")
                continue
            item, r = hit
            dlg._tree.scrollToItem(
                item, QAbstractItemView.ScrollHint.PositionAtCenter)
            dlg._tree.setCurrentItem(item)
            yield 1200
            rec["picked"][want] = {"starred": bool(r.starred),
                                   "pane": _pane(dlg)}
            d.shot(dlg, f"{lang}-03-i1pro3plus-{k}")
        dlg.reject()
        yield 1500
        (d.out / f"{lang}-stars.json").write_text(
            json.dumps({k: rec.get(k) for k in
                        ("star_line", "still_laying_out", "stars",
                         "starred_shown", "picked")},
                       indent=2, ensure_ascii=False), encoding="utf-8")
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
