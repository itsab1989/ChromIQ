#!/usr/bin/env python3
"""B42, Knut #182 5815435713 and 5815501486, driven ON SCREEN.

    python scripts/drive_b42_x_and_prefs.py <out> <en|de>

1. Preferences > Reports, frame "Default measurement report title and file
   name": the left edges of the three input boxes, measured off the widgets
   and photographed, at the window's opening width and again narrow.
2. Preferences > Reports > Report limits: the cell of every row ChromIQ
   cannot measure, in every column, read off the window's own cells, the
   "Not evaluated by ChromIQ" group photographed, and the help text of
   "Maximum ΔE00, spot colours" opened and photographed.

It runs on any tree (CHROMIQ_TREE), so the same script photographs the tree
before the change and after it. `userdrive.Drive` sandboxes the settings and
presets and FORCES the repository's ISO file.

**NOBODY HAS TO CLICK.** A watchdog answers every question the drive did not
open itself (records the text, photographs it, presses No / Cancel / reject),
and a second timer ends the run after five minutes whatever happens.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

DEADLINE_MS = 300_000
HELP_ROW = "spot_solids_de00_max"


def _install_watchdog(d) -> None:
    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

    class Watchdog(QObject):
        """Answers any modal this drive did not open itself."""
        OURS = {"SettingsDialog", "ThresholdsDialog", "_InfoDialog"}

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
                    if w.buttonRole(b) in (QMessageBox.ButtonRole.RejectRole,
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


def _edges(sd) -> dict:
    """The three boxes' left edges and widths, in the dialog's coordinates."""
    from PyQt6.QtCore import QPoint
    out = {}
    for key, attr in (("profiling", "_report_title_prof_edit"),
                      ("verification", "_report_title_verify_edit"),
                      ("calibration", "_report_title_cal_edit")):
        w = getattr(sd, attr)
        p = w.mapTo(sd, QPoint(0, 0))
        out[key] = {"left": p.x(), "width": w.width(),
                    "right": p.x() + w.width()}
    return out


def _show_title_frame(sd) -> None:
    from PyQt6.QtWidgets import QScrollArea
    edit = sd._report_title_prof_edit
    for i in range(sd._tabs.count()):
        if sd._tabs.widget(i).isAncestorOf(edit):
            sd._tabs.setCurrentIndex(i)
            break
    p = edit.parentWidget()
    while p is not None and not isinstance(p, QScrollArea):
        p = p.parentWidget()
    if p is not None:
        p.ensureWidgetVisible(sd._report_title_cal_edit, 20, 60)


def script_for(language: str):
    def script(d):
        from PyQt6.QtWidgets import QApplication, QLabel
        from workflow import compliance_sets as cs
        rec = d.record
        rec.update({"language": language, "mode": "ON SCREEN", "checks": []})
        tag = language

        def check(what, ok, detail=""):
            rec["checks"].append({"what": what, "ok": bool(ok),
                                  "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        rec["iso_file_in_use"] = cs.iso_data_path_text()
        d.note(f"ISO file in use: {cs.iso_data_path_text()}")
        _install_watchdog(d)

        # -- 1. Preferences > Reports ---------------------------------------
        d.later(d.win._open_settings)
        yield 3500
        sd = d.top_dialog("SettingsDialog")
        check("Preferences opened", sd is not None)
        if sd is None:
            return
        _show_title_frame(sd)
        yield 1200
        wide = _edges(sd)
        rec["edges_opening_width"] = {"dialog_width": sd.width(), **wide}
        d.note("edges at opening width: " + json.dumps(rec["edges_opening_width"]))
        d.shot(sd, f"{tag}-01-prefs-reports-opening-width")
        lefts = {v["left"] for v in wide.values()}
        check("three boxes share one left edge (opening width)",
              len(lefts) == 1, str(sorted(lefts)))

        w0, h0 = sd.width(), sd.height()
        # AS NARROW AS THE WINDOW GOES: Qt clamps a resize to the dialog's
        # minimum, so asking for 1 px gives the narrowest a user can drag it.
        rec["dialog_minimum_width"] = sd.minimumWidth()
        sd.resize(1, h0)
        yield 1500
        _show_title_frame(sd)
        yield 800
        narrow = _edges(sd)
        rec["edges_narrow"] = {"dialog_width": sd.width(), **narrow}
        d.note("edges narrow: " + json.dumps(rec["edges_narrow"]))
        d.shot(sd, f"{tag}-02-prefs-reports-narrow")
        lefts = {v["left"] for v in narrow.values()}
        check("three boxes share one left edge (narrow)",
              len(lefts) == 1, str(sorted(lefts)))
        check("every box keeps a usable width when narrow (>= 120 px)",
              all(v["width"] >= 120 for v in narrow.values()),
              str({k: v["width"] for k, v in narrow.items()}))
        sd.resize(w0, h0)
        yield 1000

        # -- 2. Report limits --------------------------------------------------
        d.later(sd._open_report_limits)
        yield 4000
        td = d.top_dialog("ThresholdsDialog")
        check("Report limits opened", td is not None)
        if td is None:
            return
        td.resize(max(td.width(), 1400), max(td.height(), 900))
        yield 1200
        cols = []
        for (c, _rid) in td._cells:
            if c not in cols:
                cols.append(c)
        unm = [r for r in cs.ROWS if r.status == "unmeasurable"]
        table = {}
        for r in unm:
            table[r.id] = {}
            for c in cols:
                w = td._cells.get((c, r.id))
                if w is None:
                    continue
                txt = w.text() if isinstance(w, QLabel) else (
                    "spinbox:" + w.text())
                table[r.id][c] = {"text": txt, "visible": w.isVisible()}
        rec["unmeasurable_cells"] = table
        rec["columns"] = cols
        shown = [(rid, c, v["text"]) for rid, per in table.items()
                 for c, v in per.items() if v["visible"]]
        not_x = [s for s in shown if s[2] != "✕"]
        d.note(f"unmeasurable rows: {len(unm)}, visible cells: {len(shown)}, "
               f"not reading ✕: {len(not_x)}")
        for s in not_x:
            d.note(f"   not ✕: {s}")
        check("every visible cell of an unmeasurable row reads ✕",
              not not_x, f"{len(not_x)} of {len(shown)} do not")
        rec["legend"] = td._notes_text().split("\n")[0]

        # scroll the Not evaluated group into view and photograph it
        lab = td._row_labels.get("macro_uniformity_score")
        if lab is not None:
            td._scroll.ensureWidgetVisible(lab, 20, 400)
        yield 1200
        d.shot(td, f"{tag}-03-limits-not-evaluated-group")
        # and the rows above the group, the Paper group's three ✕ rows
        top = td._row_labels.get("substrate_gloss_class")
        if top is not None:
            td._scroll.ensureWidgetVisible(top, 20, 200)
        yield 1200
        d.shot(td, f"{tag}-04-limits-paper-group")

        # the help text of "Maximum ΔE00, spot colours"
        from ui.tooltip_button import TooltipButton
        row = cs.ROW_BY_ID[HELP_ROW]
        btn = None
        from core.i18n import tr
        for b in td.findChildren(TooltipButton):
            if getattr(b, "_title", None) == tr(row.label):
                btn = b
                break
        check("the spot-colours row has a help icon", btn is not None)
        if btn is not None:
            td._scroll.ensureWidgetVisible(btn, 20, 200)
            yield 600
            d.later(btn.click)
            yield 2500
            info = QApplication.activeModalWidget()
            if info is not None and type(info).__name__ == "_InfoDialog":
                rec["help_text"] = d.modal_text(info)
                d.note("help text: " + rec["help_text"].replace("\n", " / "))
                d.shot(info, f"{tag}-05-help-spot-colours")
                info.reject()
                d._modal_closed()
                yield 1200
            else:
                check("the help window opened", False,
                      type(info).__name__ if info else "none")
        td.reject()
        d._modal_closed()
        yield 1500
        sd.reject()                      # Cancel: nothing is written
        d._modal_closed()
        yield 1500
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    d = Drive(out, projects=[], language=language)
    rc = d.run(script_for(language))
    bad = [c for c in d.record.get("checks", []) if not c["ok"]]
    print(f"rc={rc} checks={len(d.record.get('checks', []))} failed={len(bad)}")
    return rc or (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
