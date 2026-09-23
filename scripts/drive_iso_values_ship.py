#!/usr/bin/env python3
"""#182 S-2 (§23): the ISO 12647 values PREPARED to ship, driven ON SCREEN.

    python scripts/drive_iso_values_ship.py <out> <en|de> <repo|fake8>

``repo``   the repository's own `data/compliance_sets/iso12647.json`, as it
           is (both sets empty until the owner's go-ahead): what a user of
           this build sees.
``fake8``  a file of MADE-UP placeholder numbers (9.87 on every row ISO
           12647-8 limits, ISO 12647-7 empty) stood in for the SHIPPED file,
           the way `tests/test_iso_values_ship_as_values_only.py` does it:
           the variable is forced at it and `compliance_sets._bundled_iso_path`
           answers it, so ChromIQ treats it as what it ships, not as a licence
           holder's. No value of either standard is used anywhere in this
           driver; the placeholders are not the standard's.

Photographed, in real windows: Preferences > Reports; the Report limits
window (top, the notes at its foot, the masthead help); Reference values; the
Measurement Report's "Judged against" and "Report type" pulldowns; and in the
``fake8`` pass a report generated against "ISO 12647-8:2021 values" with the
window's own "Show limits…".

`userdrive.Drive` sandboxes the settings and presets and FORCES the
repository's ISO file before anything is imported; the fake pass then points
it at the placeholder file, never at the licence holder's.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

PROJECT = "Report-Limits-Threshold-Series"
FAKE = 9.87


def install_fake_shipped(out: Path) -> Path:
    from workflow import compliance_sets as cs
    import os
    doc = {"_readme": "FAKE placeholder numbers for an on-screen drive; "
                      "not a standard's values.",
           "iso_12647_7": {},
           "iso_12647_8": {r: FAKE for r in cs._ISO_ROWS["iso_12647_8"]}}
    f = out / "fake-shipped-iso12647.json"
    f.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    os.environ[cs.ISO_DATA_ENV] = str(f)
    cs._bundled_iso_path = lambda: f
    cs.reset_iso_cache()
    return f


def script_for(mode: str, language: str):
    def script(d):
        from PyQt6.QtWidgets import QLabel
        from core.i18n import tr
        from workflow import compliance_sets as cs
        rec = d.record
        rec.update({"language": language, "mode": "ON SCREEN",
                    "iso_pass": mode, "checks": []})
        tag = f"{mode}-{language}"

        def check(what, ok, detail=""):
            rec["checks"].append({"what": what, "ok": bool(ok),
                                  "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        cs.reset_iso_cache()
        shipped = cs.shipped_iso_sets()
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        rec["shipped_iso_sets"] = list(shipped)
        d.note(f"[{tag}] ISO file in use: {cs.iso_data_path_text()}; "
               f"ships: {shipped}")
        check("the pass is in the state it names",
              shipped == (("iso_12647_8",) if mode == "fake8" else ()),
              repr(shipped))

        # ---- Preferences > Reports > Report limits ------------------------
        d.later(d.win._open_settings)
        yield 3000
        sd = d.top_dialog("SettingsDialog")
        check("Preferences opened", sd is not None)
        if sd is None:
            return
        for i in range(sd._tabs.count()):
            if sd._tabs.tabText(i).replace("&", "") == tr("Reports"):
                sd._tabs.setCurrentIndex(i)
        yield 900
        d.shot(sd, f"{tag}-01-preferences-reports")

        d.later(sd._report_limits_btn.click)
        yield 3500
        td = d.top_dialog("ThresholdsDialog")
        check("Report limits opened from Preferences", td is not None)
        if td is None:
            return
        d.shot(td, f"{tag}-02-report-limits-top")
        from ui.dialogs.thresholds_dialog import _columns_paragraph
        para = _columns_paragraph()
        notes = td._notes_text()
        rec["columns_paragraph"] = para
        rec["notes"] = notes
        # how many numeric cells each read-only ISO column draws (a count,
        # not a value)
        for sid in ("iso_12647_7", "iso_12647_8"):
            n = len(cs.limit_bearing(cs.effective_limits(sid, None)))
            rec[f"{sid}_numeric_cells"] = n
            want = len([r for r in cs._ISO_ROWS[sid]
                        if cs.ROW_BY_ID[r].status in ("now", "build", "ref")]) \
                if sid in shipped else 0
            check(f"{sid}: numeric cells", n == want, f"{n} (want {want})")
        for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
            c = cs.custom_default_counts(sid)
            rec[f"{sid}_sources"] = c
            check(f"{sid} starts from Knut's figures and ChromIQ's",
                  c["supplied"] == 0 and c["industry"] > 0, repr(c))
            lb = cs.limit_bearing(cs.factory_limits(sid))
            check(f"{sid} holds no placeholder", not any(
                l.number == FAKE for l in lb.values()))
        if mode == "fake8":
            check("the paragraph says the -8 column ships",
                  "which ship with ChromIQ" in para or "die ChromIQ mitliefert" in para)
            check("the paragraph says the -7 column is empty",
                  " is empty" in para or " ist leer" in para)
            check("no 'no permission' sentence", tr(
                "The two ISO columns are read-only and hold a standard's "
                "published values, which ChromIQ has no permission to include: "
                "they are empty here, and every cell in them reads ? or ✕, until "
                "you supply that standard's figures with “Reference "
                "values…” below.") not in para)
        else:
            check("the shipping-empty sentence is shown", tr(
                "The two ISO columns are read-only and hold a standard's "
                "published values, which ChromIQ has no permission to include: "
                "they are empty here, and every cell in them reads ? or ✕, until "
                "you supply that standard's figures with “Reference "
                "values…” below.") in para)
        sb = td._scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
        yield 900
        d.shot(td, f"{tag}-03-report-limits-notes")
        sb.setValue(0)
        yield 400

        from ui.tooltip_button import TooltipButton
        btns = [b for b in td.findChildren(TooltipButton)
                if b.isVisible()]
        head_btn = min(btns, key=lambda b: b.mapTo(td, b.rect().topLeft()).y()) \
            if btns else None
        if head_btn is not None:
            d.later(head_btn.click)
            yield 2000
            info = d.top_dialog("_InfoDialog")
            if info is not None:
                d.shot(info, f"{tag}-04-report-limits-help")
                info.close()
                d._modal_closed()
            yield 1200

        d.later(td._iso_values_btn.click)
        yield 2500
        rv = d.top_dialog("ReferenceValuesDialog")
        check("Reference values opened", rv is not None)
        if rv is not None:
            d.shot(rv, f"{tag}-05-reference-values")
            rec["reference_values_text"] = [
                w.text() for w in rv.findChildren(QLabel) if w.text()][:6]
            rv.close()
            d._modal_closed()
        yield 1500
        td.reject()
        d._modal_closed()
        yield 1500
        sd.reject()                      # Cancel: nothing is written
        d._modal_closed()
        yield 2000

        # ---- the Measurement Report ----------------------------------------
        d.open_project(PROJECT)
        d.set_bar(run_type="verification", run="run3")
        yield 900
        d.launch_tool("measurement_report")
        dlg = None
        for _ in range(60):
            yield 250
            dlg = d.top_dialog("MeasurementReportDialog")
            if dlg is not None:
                break
        check("Measurement Report opened", dlg is not None)
        if dlg is None:
            return
        yield 2500
        combo = dlg._set_combo
        entries = [combo.itemData(i) for i in range(combo.count())]
        rec["judged_against_entries"] = entries
        check("ISO 12647-8 is a choice exactly when it ships",
              ("iso_12647_8" in entries) == ("iso_12647_8" in shipped),
              repr(entries))
        check("ISO 12647-7 is not a choice", "iso_12647_7" not in entries)
        # A POPUP IS NOT PHOTOGRAPHED: measured, `capture_window` finds no
        # window of its own for a combo's list and the rectangle fallback
        # proves it is a picture of what is behind. The entries are recorded
        # from the pulldown itself instead, and the window is photographed.
        d.shot(dlg, f"{tag}-06-report-window")
        from workflow.measurement_report import (REPORT_TYPE_ISO_7,
                                                 REPORT_TYPE_ISO_8)
        why7 = dlg._not_built_line(REPORT_TYPE_ISO_7)
        why8 = dlg._not_built_line(REPORT_TYPE_ISO_8)
        rec["iso_type_reasons"] = {"7": why7, "8": why8}
        paywall = tr("Not available yet: the figures this report judges "
                     "against are published in a standard ChromIQ may not "
                     "include.")
        check("-7 type still names the figures", why7 == paywall, why7)
        check("-8 type names the figures only while they do not ship",
              (why8 == paywall) == ("iso_12647_8" not in shipped), why8)
        rec["report_type_entries"] = [
            (dlg._type_combo.itemText(i), dlg._type_combo.itemData(
                i, 3)) for i in range(dlg._type_combo.count())]

        if mode == "fake8":
            i = combo.findData("iso_12647_8")
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            yield 2000
            d.shot(dlg, f"{tag}-08-judged-against-iso-12647-8")
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            yield 1500
            i = combo.findData("iso_12647_8")
            if combo.currentIndex() != i:
                combo.setCurrentIndex(i)
                combo.activated.emit(i)
                yield 1500
            d.later(dlg._generate_btn.click)
            said = None
            yield 1500
            m = d.modal()
            if m is not None and m is not dlg:
                said = d.answer("new", name=f"{tag}-09-generate-question")
                yield 1500
            yield 6000
            rec["generate_question"] = said
            d.shot(dlg, f"{tag}-10-report-judged-against-iso-12647-8")
            text = dlg._view.toPlainText()
            label8 = tr(cs.SET_BY_ID["iso_12647_8"].label)
            check("the report names the ISO 12647-8 set", label8 in text,
                  label8)
            view = dlg._view
            c = view.document().find(tr("Report Results"))
            if not c.isNull():
                view.setTextCursor(c)
                view.ensureCursorVisible()
                yield 900
                d.shot(dlg, f"{tag}-11-report-results")
            d.later(dlg._limits_btn.click)
            yield 3000
            m = d.modal()
            if m is not None and m is not dlg:
                d.shot(m, f"{tag}-12-show-limits-from-the-report")
                m.close()
                d._modal_closed()
            yield 1500
        dlg.close()
        yield 1500
    return script


def main() -> int:
    out, language, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    assert mode in ("repo", "fake8"), mode
    out = out / f"{mode}-{language}"
    d = Drive(out, projects=[PROJECT], language=language)
    if mode == "fake8":
        f = install_fake_shipped(d.out)
        d.note(f"fake shipped file (placeholders only): {f}")
    return d.run(script_for(mode, language))


if __name__ == "__main__":
    raise SystemExit(main())
