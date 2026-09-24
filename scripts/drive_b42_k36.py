#!/usr/bin/env python3
"""B42, Knut #182 5820871320 (K36), driven ON SCREEN.

    python scripts/drive_b42_k36.py <out> <en|de> [k1,k1s,k2,k3,k4,kp,kv]

Runs on any tree (``CHROMIQ_TREE``), so the same script photographs the tree
before the change and the one after it. Settings, presets and the output
folder are sandboxed by `userdrive`, which also FORCES the repository's ISO
values file. Projects are copies of ``CHROMIQ_DEMO_PACK``; the pack itself is
never written.

Scenes:

  k1   Report-Limits-Report-Types, run1, Verification: "New report…", every
       date ticked. Report type "Contract proof check (ISO 12647-7)" chosen
       the way a user chooses it; what "Judged against" then shows, and the
       "Judged against" list opened (each entry: enabled or greyed, and its
       tooltip). Then "Judged against" is put on ChromIQ default (refused on
       the tree after the change) and Generate report pressed: on the tree
       before the change that writes a report of the old pair, which the
       after drive then opens.
  k1s  The same project, opened on the report k1 wrote (after drive, with
       ``CHROMIQ_DEMO_PACK`` pointing at the before drive's projects): shown
       as saved, Generate greyed with its reason; an ISO set chosen; Generate
       pressed; the Update / Create New question photographed and cancelled.
  k2   Report-Limits-Report-Types, Run type Calibration (calibration options
       on in the sandbox): the Report type list and the Judged against list.
  k3   Help: the Dictionary help card at "Profile run", "Verification run",
       "Calibration run" and the Run type entry; and a report's Report Scope.
  k4   Report-Limits-Strip-And-Gamut, run4 (no paper patch): the Paper white
       line and its numbered note.
  kp   Preferences, Reports: an ISO type chosen as the default, then Report
       limits… with the "Default for new reports" row.
  kv   Create Chart, Verification: "Which presets can be used for
       verification?", Contract proof check chosen, Judged against opened.

**NOBODY HAS TO CLICK.** A watchdog answers any window this drive did not
expect (Cancel / Close / No / OK, in English or German) after three seconds,
records its text and photographs it; a deadline ends the run after twenty
minutes whatever happens.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import DEMO_PACK, Drive                         # noqa: E402

DEADLINE_S = 1200
OURS = {"MeasurementReportDialog", "ThresholdsDialog", "_InfoDialog",
        "SettingsDialog", "PresetVerificationDialog", "WelcomeDialog"}
EXPECTED: "set[str]" = set()
TYPES = "Report-Limits-Report-Types"
NO_PAPER = "Report-Limits-Strip-And-Gamut"
ISO7 = "t6_contract_proof"


def _install_watchdog(d, rec):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QAbstractButton, QApplication
    started = time.monotonic()
    seen: dict = {}

    def tick():
        if time.monotonic() - started > DEADLINE_S:
            d.note("WATCHDOG: deadline reached, quitting")
            rec["deadline_hit"] = True
            QApplication.instance().quit()
            return
        m = QApplication.activeModalWidget()
        if (m is None or not m.isVisible() or type(m).__name__ in OURS
                or type(m).__name__ in EXPECTED):
            seen.clear()
            return
        first = seen.setdefault(id(m), time.monotonic())
        if time.monotonic() - first < 3:
            return
        seen.pop(id(m), None)
        said = d.modal_text(m)
        n = len(rec.setdefault("watchdog", [])) + 1
        try:
            from onscreen_capture import capture_window
            capture_window(m, d.shots / f"watchdog-{n:02d}.png")
        except Exception:                                  # noqa: BLE001
            pass
        clicked = None
        for word in ("Cancel", "Abbrechen", "Close", "Schließen", "No",
                     "Nein", "OK"):
            for b in m.findChildren(QAbstractButton):
                if b.isVisible() and b.text().replace("&", "") == word:
                    clicked = word
                    b.click()
                    break
            if clicked:
                break
        if clicked is None:
            m.close()
            clicked = "(closed)"
        rec["watchdog"].append({"class": type(m).__name__, "text": said,
                                "clicked": clicked})
        d.note(f"   [watchdog] {type(m).__name__}: "
               f"{said[:160].replace(chr(10), ' / ')!r} -> {clicked}")

    dog = QTimer()
    dog.timeout.connect(tick)
    dog.start(500)
    d._k36_dog = dog


def _wait(d, cls, tries=60):
    for _ in range(tries):
        w = d.top_dialog(cls)
        if w is not None:
            return w
        d.pump(250)
    return None


def _view_text(dlg) -> str:
    from PyQt6.QtWidgets import QTextBrowser, QTextEdit
    for v in dlg.findChildren((QTextBrowser, QTextEdit)):
        if v.isVisible() and len(v.toPlainText()) > 200:
            return v.toPlainText()
    return ""


def _scroll_to(dlg, text: str) -> bool:
    from PyQt6.QtGui import QTextCursor
    from PyQt6.QtWidgets import QTextBrowser, QTextEdit
    for v in dlg.findChildren((QTextBrowser, QTextEdit)):
        if not v.isVisible() or len(v.toPlainText()) < 200:
            continue
        v.moveCursor(QTextCursor.MoveOperation.Start)
        if v.find(text):
            v.ensureCursorVisible()
            sb = v.verticalScrollBar()
            sb.setValue(min(sb.maximum(), sb.value() + v.height() // 3))
            return True
    return False


def _choose(combo, data) -> bool:
    """Choose an entry the way a user does: the pulldown's own index, then
    its `activated` signal. A greyed entry cannot be clicked by a user, so it
    is not chosen here either."""
    i = combo.findData(data)
    if i < 0:
        return False
    item = combo.model().item(i) if hasattr(combo.model(), "item") else None
    if item is not None and not item.isEnabled():
        return False
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    return True


def _combo_state(combo) -> list:
    from PyQt6.QtCore import Qt
    out = []
    m = combo.model()
    for i in range(combo.count()):
        item = m.item(i) if hasattr(m, "item") else None
        out.append({"text": combo.itemText(i), "data": combo.itemData(i),
                    "enabled": bool(item.isEnabled()) if item else None,
                    "tooltip": combo.itemData(
                        i, Qt.ItemDataRole.ToolTipRole) or ""})
    return out


def _popup_shot(d, combo, name, tries=3):
    for attempt in range(tries):
        combo.showPopup()
        d.pump(1500 + 800 * attempt)
        ok = d.shot(combo.view(), name)
        combo.hidePopup()
        d.pump(500)
        if ok:
            return True
    return False


def _new_report_everything(d, dlg):
    dlg._saved_combo.setCurrentIndex(0)
    d.pump(1200)
    dlg._select_all_btn.click()
    d.pump(1500)


def _generate_state(dlg) -> dict:
    why = getattr(dlg, "_generate_why", None)
    return {"enabled": dlg._generate_btn.isEnabled(),
            "tooltip": dlg._generate_btn.toolTip(),
            "why_line": why.text() if why is not None else None,
            "type": dlg._type_combo.currentData(),
            "type_text": dlg._type_combo.currentText(),
            "set": dlg._set_combo.currentData(),
            "set_text": dlg._set_combo.currentText(),
            "type_enabled": dlg._type_combo.isEnabled(),
            "set_enabled": dlg._set_combo.isEnabled()}


def script_for(language: str, scenes: "list[str]"):
    def script(d):
        rec = d.record
        rec.update({"language": language, "scenes": scenes,
                    "mode": "ON SCREEN", "pack": str(DEMO_PACK)})
        tag = language
        from core.i18n import tr
        from workflow import compliance_sets as cs
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        d.note(f"ISO file in use: {cs.iso_data_path_text()}")
        _install_watchdog(d, rec)

        # ------------------------------------------------------------ K1
        if "k1" in scenes:
            d.open_project(TYPES)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                _new_report_everything(d, dlg)
                yield 800
                rec["k1_open"] = _generate_state(dlg)
                d.shot(dlg, f"{tag}-k1-01-new-report")
                ok = _choose(dlg._type_combo, ISO7)
                yield 2000
                rec["k1_after_type"] = _generate_state(dlg)
                rec["k1_after_type"]["chosen"] = ok
                d.note("   K1 after choosing Contract proof check: "
                       + json.dumps(rec["k1_after_type"], ensure_ascii=False))
                d.shot(dlg, f"{tag}-k1-02-contract-proof-chosen")
                rec["k1_set_list"] = _combo_state(dlg._set_combo)
                for x in rec["k1_set_list"]:
                    d.note(f"   K1 set {x['data']}: enabled={x['enabled']} "
                           f"tip={x['tooltip'][:90]!r}")
                _popup_shot(d, dlg._set_combo,
                            f"{tag}-k1-03-judged-against-open")
                yield 500
                # the old pair: ChromIQ default beside Contract proof check
                ok = _choose(dlg._set_combo, "chromiq_default")
                yield 1500
                rec["k1_default_chosen"] = ok
                rec["k1_after_default"] = _generate_state(dlg)
                d.note(f"   K1 ChromIQ default chosen: {ok}; "
                       + json.dumps(rec["k1_after_default"],
                                    ensure_ascii=False))
                d.shot(dlg, f"{tag}-k1-04-chromiq-default-tried")
                if dlg._generate_btn.isEnabled() and ok:
                    EXPECTED.add("QMessageBox")
                    d.later(dlg._generate_btn.click)
                    yield 1200
                    said = d.answer("Create New" if language == "en"
                                    else "Neu erstellen",
                                    f"{tag}-k1-05-generate-asks",
                                    within_ms=4000)
                    EXPECTED.discard("QMessageBox")
                    rec["k1_generate_question"] = said
                    yield 3500
                    reps = sorted(str(p.relative_to(d.work)) for p in
                                  (d.work / TYPES).rglob("report_*.json")
                                  if "old" not in p.parts)
                    rec["k1_reports_after"] = reps
                    d.shot(dlg, f"{tag}-k1-06-generated")
                dlg.close()
                yield 1500

        # ----------------------------------------------------------- K1s
        if "k1s" in scenes:
            d.open_project(TYPES)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                # the report of the old pair: the one whose document says
                # Contract proof check and ChromIQ default
                pick = None
                docs = {e["key"]: e for e in dlg._saved_documents(
                    dlg._run_ctx.run if dlg._run_ctx else None)}
                for i in range(dlg._saved_combo.count()):
                    key = dlg._saved_combo.itemData(i)
                    doc = (docs.get(key) or {}).get("doc") or {}
                    comp = doc.get("compliance") or {}
                    if doc.get("type") == ISO7 and \
                            comp.get("set_id") == "chromiq_default":
                        pick = i
                        break
                rec["k1s_picked"] = (dlg._saved_combo.itemText(pick)
                                     if pick is not None else None)
                if pick is not None:
                    dlg._saved_combo.setCurrentIndex(pick)
                    yield 3000
                rec["k1s_opened"] = _generate_state(dlg)
                d.note("   K1s opened: " + json.dumps(rec["k1s_opened"],
                                                       ensure_ascii=False))
                d.shot(dlg, f"{tag}-k1s-01-saved-old-pair")
                _popup_shot(d, dlg._set_combo,
                            f"{tag}-k1s-02-judged-against-open")
                ok = _choose(dlg._set_combo, "iso_12647_7")
                yield 2000
                rec["k1s_iso_set"] = _generate_state(dlg)
                rec["k1s_iso_set"]["chosen"] = ok
                d.note("   K1s ISO set: " + json.dumps(rec["k1s_iso_set"],
                                                       ensure_ascii=False))
                d.shot(dlg, f"{tag}-k1s-03-iso-set-chosen")
                if dlg._generate_btn.isEnabled():
                    EXPECTED.add("QMessageBox")
                    d.later(dlg._generate_btn.click)
                    yield 1200
                    said = d.answer("Cancel" if language == "en"
                                    else "Abbrechen",
                                    f"{tag}-k1s-04-update-or-new",
                                    within_ms=5000)
                    EXPECTED.discard("QMessageBox")
                    rec["k1s_question"] = said
                    yield 1500
                dlg.close()
                yield 1500

        # ------------------------------------------------------------ K2
        if "k2" in scenes:
            d.settings.set("calibration_mode", True)
            d.win._apply_calibration_mode()      # what Preferences' Save does
            yield 1000
            d.open_project(TYPES)
            from core import measurement_target as MT
            b = d.bar
            i = b._type_combo.findData(MT.RUN_TYPE_CALIBRATION)
            rec["k2_calibration_in_bar"] = i >= 0
            if i >= 0:
                b._type_combo.setCurrentIndex(i)
                b._type_combo.activated.emit(i)
            yield 1500
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                rec["k2_kind"] = dlg._window_kind()
                rec["k2_type_list"] = _combo_state(dlg._type_combo)
                rec["k2_set_list"] = _combo_state(dlg._set_combo)
                for x in rec["k2_type_list"]:
                    d.note(f"   K2 type {x['data']}: enabled={x['enabled']} "
                           f"tip={x['tooltip'][:100]!r}")
                d.shot(dlg, f"{tag}-k2-01-calibration-report")
                _popup_shot(d, dlg._type_combo, f"{tag}-k2-02-type-open")
                _popup_shot(d, dlg._set_combo, f"{tag}-k2-03-set-open")
                dlg.close()
                yield 1500
            d.settings.set("calibration_mode", False)
            d.win._apply_calibration_mode()

        # ------------------------------------------------------------ K3
        if "k3" in scenes:
            from PyQt6.QtWidgets import QLabel, QScrollArea
            from ui.dialogs.welcome_dialog import WelcomeDialog
            wd = WelcomeDialog(d.settings, None, "light")
            wd.resize(1180, 900)
            wd.show()
            wd.raise_()
            yield 1500
            wd._on_card_clicked("glossary")
            yield 2000
            rec["k3_terms"] = {}
            for term in ("Profile run", "Verification run", "Calibration run",
                         "Run type (Calibration / Profiling / Verification)"):
                lab = next((l for l in wd.findChildren(QLabel)
                            if l.isVisible() and l.text().strip() == tr(term)),
                           None)
                if lab is None:
                    rec["k3_terms"][term] = None
                    d.note(f"   K3 no label for {term!r}")
                    continue
                area = None
                p = lab.parent()
                while p is not None:
                    if isinstance(p, QScrollArea):
                        area = p
                        break
                    p = p.parent()
                if area is not None:
                    area.ensureWidgetVisible(lab, 0, 40)
                    sb = area.verticalScrollBar()
                    sb.setValue(min(sb.maximum(),
                                    lab.mapTo(area.widget(),
                                              lab.rect().topLeft()).y() - 40))
                yield 800
                slug = term.split(" (")[0].lower().replace(" ", "-")
                d.shot(wd, f"{tag}-k3-01-dictionary-{slug}")
                from ui.dialogs.welcome_dialog import GLOSSARY
                rec["k3_terms"][term] = dict(GLOSSARY).get(tr(term))
            wd.close()
            yield 800
            # a report's Report Scope
            d.open_project(TYPES)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                _new_report_everything(d, dlg)
                yield 1500
                text = _view_text(dlg)
                i = text.find(tr("Report Scope"))
                rec["k3_scope_text"] = text[i:i + 700] if i >= 0 else None
                d.note(f"   K3 scope: {rec['k3_scope_text']!r}"[:500])
                _scroll_to(dlg, tr("Date range:"))
                yield 1200
                d.shot(dlg, f"{tag}-k3-02-report-scope")
                dlg.close()
                yield 1500

        # ------------------------------------------------------------ K4
        if "k4" in scenes:
            d.open_project(NO_PAPER)
            d.set_bar(run="run4", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                _new_report_everything(d, dlg)
                if not dlg._detail_check.isChecked():
                    dlg._detail_check.setChecked(True)
                yield 2500
                text = _view_text(dlg)
                j = text.find(tr("Notes on the verdicts above:"))
                rec["k4_notes_text"] = text[j:j + 1200] if j >= 0 else None
                d.note(f"   K4 notes: {rec['k4_notes_text']!r}"[:600])
                _scroll_to(dlg, tr("Paper white and darkest black (L*)"))
                yield 1200
                d.shot(dlg, f"{tag}-k4-01-paper-white-line")
                _scroll_to(dlg, tr("Notes on the verdicts above:"))
                yield 1200
                d.shot(dlg, f"{tag}-k4-02-notes")
                dlg.close()
                yield 1500

        # ------------------------------------------------------------ KP
        if "kp" in scenes:
            d.settings.set("compliance_default_set", "chromiq_default")
            d.later(d.win._open_settings)
            yield 2500
            sd = _wait(d, "SettingsDialog")
            if sd is not None:
                from PyQt6.QtWidgets import QTabWidget
                combo = sd._report_type_default_combo
                w = combo
                while w is not None:
                    parent = w.parent()
                    if isinstance(parent, QTabWidget) or (
                            parent is not None
                            and isinstance(parent.parent(), QTabWidget)):
                        tw = parent if isinstance(parent, QTabWidget) \
                            else parent.parent()
                        for k in range(tw.count()):
                            if tw.widget(k).isAncestorOf(combo):
                                tw.setCurrentIndex(k)
                        break
                    w = parent
                yield 1200
                ok = _choose(combo, "t5_validation_print")
                yield 800
                buf = getattr(sd, "_compliance_buffer", {}) or {}
                rec["kp_default_set_after_type"] = buf.get("default_set")
                d.note(f"   KP type chosen {ok}; buffered default set "
                       f"{buf.get('default_set')!r}")
                d.shot(sd, f"{tag}-kp-01-preferences-type")
                d.later(sd._report_limits_btn.click)
                yield 3000
                td = _wait(d, "ThresholdsDialog")
                if td is not None:
                    rec["kp_default_radios"] = {
                        k: {"enabled": rb.isEnabled(),
                            "checked": rb.isChecked(),
                            "tip": rb.toolTip()}
                        for k, rb in td._default_radios.items()}
                    d.note("   KP radios: " + json.dumps(
                        {k: (v["enabled"], v["checked"]) for k, v in
                         rec["kp_default_radios"].items()}))
                    d.shot(td, f"{tag}-kp-02-report-limits")
                    td.reject()
                    d._modal_closed()
                    yield 1500
                sd.reject()
                d._modal_closed()
                yield 1500

        # ------------------------------------------------------------ KV
        if "kv" in scenes:
            d.open_project(TYPES)
            d.set_bar(run="run1", run_type="Verification")
            yield 1500
            d.goto_tab("chart")
            yield 1000
            d.later(d.win._tab_chart._open_preset_verification_window)
            yield 4000
            pv = _wait(d, "PresetVerificationDialog", tries=120)
            if pv is not None:
                rec["kv_open"] = {"type": pv.current_type(),
                                  "set": pv.current_set()}
                i = pv._type_combo.findData(ISO7)
                pv._type_combo.setCurrentIndex(i)
                yield 2500
                rec["kv_after_type"] = {"type": pv.current_type(),
                                        "set": pv.current_set(),
                                        "set_list": _combo_state(pv._set_combo)}
                d.note("   KV after type: " + json.dumps(
                    {k: v for k, v in rec["kv_after_type"].items()
                     if k != "set_list"}))
                d.shot(pv, f"{tag}-kv-01-contract-proof")
                _popup_shot(d, pv._set_combo, f"{tag}-kv-02-judged-against-open")
                pv.reject()
                d._modal_closed()
                yield 1500
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    scenes = (sys.argv[3] if len(sys.argv) > 3
              else "k1,k2,k3,k4,kp,kv").split(",")
    projects = [p for p in (TYPES, NO_PAPER) if (DEMO_PACK / p).is_dir()]
    d = Drive(out, projects=projects, language=language)
    rc = d.run(script_for(language, scenes))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
