#!/usr/bin/env python3
"""B42, Knut #182 5814820283: "All metrics" in "Which presets can be used for
verification?", driven ON SCREEN.

    python scripts/drive_b42_all_metrics.py <out> <en|de>

Opens the demo pack's Report-Limits-Every-Limit-Set, run1, Verification, in
the real app (`userdrive.Drive`, which sandboxes the settings and presets and
FORCES the repository's ISO file), opens the presets window from Create Chart
and photographs:

  01  the window as it opens (which "Judged against" entry, the count line,
      the current chart's "Metrics answered")
  02  the "Judged against" pulldown open
  03  a preset selected, its detail pane
  04  the same preset under ChromIQ default, where the count is smaller
  05  the window closed on ChromIQ default and OPENED AGAIN: which entry it
      opens on (the rule is: All metrics every time, nothing remembered)

It runs on any tree (CHROMIQ_TREE), so the same script photographs HEAD
before the change and the tree after it; what it expects is only checked when
the tree has the option.

**NOBODY HAS TO CLICK.** A watchdog answers every question the app asks while
this runs (the auto-update-preview question included): it records the text,
photographs the window and presses its No / Cancel / reject button. A second
timer ends the whole run after five minutes whatever happens.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

PROJECT = "Report-Limits-Every-Limit-Set"
DEADLINE_MS = 300_000


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

    class Watchdog(QObject):
        """Answers any modal this drive did not open itself."""
        OURS = {"PresetVerificationDialog"}

        def __init__(self):
            super().__init__(QApplication.instance())
            self.answered = []
            self._t = QTimer(self)
            self._t.setInterval(400)
            self._t.timeout.connect(self.tick)
            self._t.start()
            self._end = QTimer(self)
            self._end.setSingleShot(True)
            self._end.timeout.connect(self.deadline)
            self._end.start(DEADLINE_MS)

        def tick(self):
            w = QApplication.activeModalWidget()
            if w is None or not w.isVisible():
                return
            if type(w).__name__ in self.OURS:
                return
            text = d.modal_text(w)
            n = len(self.answered) + 1
            try:
                from onscreen_capture import capture_window
                capture_window(w, d.shots / f"watchdog-{n:02d}.png")
            except Exception:                              # noqa: BLE001
                pass
            clicked = None
            if isinstance(w, QMessageBox):
                pick = None
                for b in w.buttons():
                    role = w.buttonRole(b)
                    if role in (QMessageBox.ButtonRole.RejectRole,
                                QMessageBox.ButtonRole.NoRole):
                        pick = b
                        break
                pick = pick or w.escapeButton() or w.defaultButton() or (
                    w.buttons()[0] if w.buttons() else None)
                if pick is not None:
                    clicked = pick.text()
                    pick.click()
                else:
                    w.reject()
                    clicked = "(reject)"
            elif isinstance(w, QDialog):
                w.reject()
                clicked = "(reject)"
            self.answered.append({"class": type(w).__name__, "text": text,
                                  "clicked": clicked})
            d.record.setdefault("watchdog", []).append(self.answered[-1])
            d.note(f"   [watchdog] {type(w).__name__}: "
                   f"{text[:160].replace(chr(10), ' / ')!r} -> {clicked}")

        def deadline(self):
            d.note("DEADLINE: the drive ran past five minutes and was ended")
            d.record["deadline_hit"] = True
            d._flush()
            QApplication.instance().quit()

    d._watchdog = Watchdog()


def _row_item(pv, want):
    from PyQt6.QtCore import Qt
    for i in range(pv._tree.topLevelItemCount()):
        top = pv._tree.topLevelItem(i)
        items = [top] + [top.child(j) for j in range(top.childCount())]
        for it in items:
            row = it.data(0, Qt.ItemDataRole.UserRole)
            if row is not None and want(row):
                return it, row
    return None, None


def _state(pv) -> dict:
    """What the window shows, read off its own widgets."""
    from PyQt6.QtCore import Qt
    cur, _row = _row_item(pv, lambda r: r.is_current_chart)
    first, frow = _row_item(pv, lambda r: not r.is_current_chart
                            and r.chart is not None)
    return {
        "judged_against_entries": [pv._set_combo.itemText(i)
                                   for i in range(pv._set_combo.count())],
        "judged_against_data": [pv._set_combo.itemData(i)
                                for i in range(pv._set_combo.count())],
        "judged_against_shown": pv._set_combo.currentText(),
        "judged_against_id": pv.current_set(),
        "report_type_shown": pv._type_combo.currentText(),
        "report_type_id": pv.current_type(),
        "asked_line": pv._asked_label.text(),
        "figures_line": pv._figures.text(),
        "header": [pv._tree.headerItem().text(c) for c in range(4)],
        "current_chart_answered": cur.text(3) if cur is not None else None,
        "first_preset": frow.label if frow is not None else None,
        "first_preset_answered": first.text(3) if first is not None else None,
    }


def script_for(language: str):
    def script(d):
        from PyQt6.QtWidgets import QApplication
        rec = d.record
        rec.update({"language": language, "mode": "ON SCREEN", "checks": []})
        tag = language

        def check(what, ok, detail=""):
            rec["checks"].append({"what": what, "ok": bool(ok),
                                  "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        from workflow import compliance_sets as cs
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        d.note(f"ISO file in use: {cs.iso_data_path_text()}")
        _install_watchdog(d)

        d.goto_tab("chart")
        tab = d.win._tab_chart
        d.open_project(PROJECT)
        d.set_bar(run="run1", run_type="Verification")
        yield 1500
        if tab._mode_name() != "manual":
            tab._manual_btn.click()
            yield 1500

        d.later(tab._open_preset_verification_window)
        yield 7000
        pv = d.top_dialog("PresetVerificationDialog")
        check("presets window opened", pv is not None)
        if pv is None:
            return
        s1 = _state(pv)
        rec["opened"] = s1
        d.note("opened: " + json.dumps(s1, ensure_ascii=False))
        has_all = "all_metrics" in s1["judged_against_data"]
        rec["tree_has_all_metrics"] = has_all
        # on the current chart, pinned so the photograph shows its pane
        cur, _r = _row_item(pv, lambda r: r.is_current_chart)
        if cur is not None:
            pv._tree.setCurrentItem(cur)
            yield 800
        d.shot(pv, f"{tag}-01-opened")

        # the pulldown, open
        pv._set_combo.showPopup()
        yield 1200
        if not d.shot(pv._set_combo.view(), f"{tag}-02-judged-against-open"):
            # a popup that has just been drawn can still be fading in
            pv._set_combo.hidePopup()
            yield 800
            pv._set_combo.showPopup()
            yield 2500
            d.shot(pv._set_combo.view(), f"{tag}-02-judged-against-open")
        pv._set_combo.hidePopup()
        yield 600

        # a preset, selected
        it, row = _row_item(pv, lambda r: not r.is_current_chart
                            and r.chart is not None and r.builtin
                            and r.relayoutable)
        if it is not None:
            pv._tree.setCurrentItem(it)
            pv._tree.scrollToItem(it)
            yield 1200
            rec["preset_under_opening"] = {"label": row.label,
                                           "answered": it.text(3)}
            d.shot(pv, f"{tag}-03-preset-under-opening-choice")

            # the same preset under ChromIQ default
            pv._set_combo.setCurrentIndex(
                pv._set_combo.findData("chromiq_default"))
            yield 2500
            it2, _row2 = _row_item(pv, lambda r: r.label == row.label)
            if it2 is not None:
                pv._tree.setCurrentItem(it2)
                pv._tree.scrollToItem(it2)
                yield 1000
            rec["preset_under_chromiq_default"] = {
                "label": row.label,
                "answered": it2.text(3) if it2 is not None else None,
                "asked_line": pv._asked_label.text()}
            d.shot(pv, f"{tag}-04-same-preset-chromiq-default")

        # close ON ChromIQ default, and open again
        pv.reject()
        d._modal_closed()
        yield 2000
        d.later(tab._open_preset_verification_window)
        yield 7000
        pv2 = d.top_dialog("PresetVerificationDialog")
        check("presets window opened again", pv2 is not None)
        if pv2 is None:
            return
        s2 = _state(pv2)
        rec["reopened"] = s2
        d.note("reopened: " + json.dumps(s2, ensure_ascii=False))
        if not d.shot(pv2, f"{tag}-05-reopened-after-closing-on-chromiq-"
                      f"default"):
            # a window that has just appeared can still be settling
            yield 2500
            d.shot(pv2, f"{tag}-05-reopened-after-closing-on-chromiq-default")

        if has_all:
            from workflow import preset_eligibility as PE
            import re
            n_all = len(PE.rows_asked(s1["report_type_id"], "all_metrics"))
            rec["all_metrics_total"] = n_all
            check("the window opens on All metrics",
                  s1["judged_against_id"] == "all_metrics")
            check("it is the first entry",
                  s1["judged_against_data"][0] == "all_metrics")
            check("it opens on All metrics again after closing on another "
                  "set", s2["judged_against_id"] == "all_metrics")
            nums = re.findall(r"\d+", s1["current_chart_answered"] or "")
            check(f"the current chart's total is every metric ({n_all})",
                  bool(nums) and int(nums[-1]) == n_all,
                  repr(s1["current_chart_answered"]))
        pv2.reject()
        d._modal_closed()
        yield 1500
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    d = Drive(out, projects=[PROJECT], language=language)
    rc = d.run(script_for(language))
    bad = [c for c in d.record.get("checks", []) if not c["ok"]]
    print(f"rc={rc} checks={len(d.record.get('checks', []))} failed={len(bad)}")
    return rc or (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
