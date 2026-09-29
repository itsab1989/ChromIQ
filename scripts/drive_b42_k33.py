#!/usr/bin/env python3
"""B42, Knut #182 5816565326 (K33), driven ON SCREEN.

    python scripts/drive_b42_k33.py <out> <en|de> [presets,report,sweep]

Runs on any tree (``CHROMIQ_TREE``), so the same script photographs the tree
before the change and the one after it. It records what the windows SHOW,
read off their own widgets, and photographs each by window id
(`userdrive.Drive.shot`). Settings, presets and the output folder are
sandboxed by `userdrive`, which also FORCES the repository's ISO values file.

Scenes:

  presets  Create Chart > "Which presets can be used for verification?" on
           Report-Limits-Every-Limit-Set, run1, Verification: the intro
           sentence, both pulldowns (open), the count line, and the current
           chart's "Metrics answered" under every report type x limit set.
  report   the Measurement Report window on the same run: the Report type
           pulldown (open, with each entry's enabled flag and tooltip), the
           "Judged against" help window (its size), the Report type help, and
           Edit limits... with its title help.
  sweep    every project of the demo pack, every profile run, Run type
           Verification: which report types the window offers, and what the
           greyed ones say.

**NOBODY HAS TO CLICK.** A watchdog answers any window this drive did not
open itself (Cancel / Close / No, in English or German) after three seconds,
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

PROJECT = "Report-Limits-Every-Limit-Set"
DEADLINE_S = 1200
OURS = {"MeasurementReportDialog", "PresetVerificationDialog",
        "ThresholdsDialog", "_InfoDialog"}


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
        if m is None or not m.isVisible() or type(m).__name__ in OURS:
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
    d._k33_dog = dog


def _wait(d, cls, tries=60):
    for _ in range(tries):
        w = d.top_dialog(cls)
        if w is not None:
            return w
        d.pump(250)
    return None


def _combo_items(combo) -> list:
    from PyQt6.QtCore import Qt
    out = []
    model = combo.model()
    for i in range(combo.count()):
        item = model.item(i) if hasattr(model, "item") else None
        out.append({
            "text": combo.itemText(i),
            "data": combo.itemData(i),
            "enabled": bool(item.isEnabled()) if item is not None else None,
            "tooltip": combo.itemData(i, Qt.ItemDataRole.ToolTipRole) or "",
        })
    return out


def _current_answered(pv) -> "str | None":
    from PyQt6.QtCore import Qt
    for i in range(pv._tree.topLevelItemCount()):
        it = pv._tree.topLevelItem(i)
        row = it.data(0, Qt.ItemDataRole.UserRole)
        if row is not None and getattr(row, "is_current_chart", False):
            return it.text(3)
    return None


def _info_dialog_of(d, dlg, title, name, rec_key, rec):
    """Click the ⓘ whose title is *title*, photograph its window, record its
    size, close it."""
    from ui.tooltip_button import TooltipButton
    btn = next((b for b in dlg.findChildren(TooltipButton)
                if b._title == title), None)
    if btn is None:
        rec[rec_key] = {"found": False}
        d.note(f"   no ⓘ titled {title!r}")
        return
    d.later(btn.click)
    yield 1500
    info = _wait(d, "_InfoDialog", 20)
    if info is None:
        rec[rec_key] = {"found": True, "opened": False}
        return
    scr = info.screen().availableGeometry()
    from PyQt6.QtWidgets import QScrollArea
    sa = info.findChild(QScrollArea)
    sb = sa.verticalScrollBar() if sa is not None else None
    rec[rec_key + "_scroll"] = ({"maximum": sb.maximum(),
                                 "page": sb.pageStep()} if sb else None)
    rec[rec_key] = {"found": True, "opened": True,
                    "width": info.width(), "height": info.height(),
                    "screen_available": [scr.width(), scr.height()],
                    "body_chars": len(btn.dialog_body())}
    d.note(f"   {title!r} help: {info.width()} x {info.height()} px "
           f"(screen {scr.width()} x {scr.height()})")
    d.shot(info, name)
    info.accept()
    d._modal_closed()
    yield 1200


def script_for(language: str, scenes: "list[str]"):
    def script(d):
        from PyQt6.QtCore import Qt
        rec = d.record
        rec.update({"language": language, "scenes": scenes,
                    "mode": "ON SCREEN"})
        tag = language
        from core.i18n import tr
        from workflow import compliance_sets as cs
        rec["iso_file_in_use"] = cs.iso_data_path_text()
        d.note(f"ISO file in use: {cs.iso_data_path_text()}")
        _install_watchdog(d, rec)

        if "presets" in scenes:
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
            pv = _wait(d, "PresetVerificationDialog")
            if pv is not None:
                from PyQt6.QtWidgets import QLabel
                intro = next((lab.text() for lab in pv.findChildren(QLabel)
                              if lab.objectName() == "info"), "")
                st = {"intro": intro,
                      "report_types": _combo_items(pv._type_combo),
                      "judged_against": _combo_items(pv._set_combo),
                      "type_shown": pv._type_combo.currentText(),
                      "set_shown": pv._set_combo.currentText(),
                      "asked_line": pv._asked_label.text(),
                      "figures_line": pv._figures.text(),
                      "current_chart_answered": _current_answered(pv)}
                rec["presets_opened"] = st
                d.note("presets opened: " + json.dumps(
                    {k: st[k] for k in ("type_shown", "set_shown",
                                        "asked_line",
                                        "current_chart_answered")},
                    ensure_ascii=False))
                d.shot(pv, f"{tag}-01-presets-opened")
                pv._type_combo.showPopup()
                yield 1500
                d.shot(pv._type_combo.view(), f"{tag}-02-presets-report-type-open")
                pv._type_combo.hidePopup()
                yield 600
                # K33-8: "Sort by", when the tree has it
                sort = getattr(pv, "_sort_combo", None)
                rec["has_sort"] = sort is not None
                if sort is not None:
                    from PyQt6.QtCore import Qt as _Qt

                    def order():
                        out = []
                        for i in range(pv._tree.topLevelItemCount()):
                            top = pv._tree.topLevelItem(i)
                            if top.childCount():
                                out.append([top.text(0)] + [
                                    f"{top.child(j).text(0)} | "
                                    f"{top.child(j).text(3)}"
                                    for j in range(min(8, top.childCount()))])
                        return out
                    rec["sort_items"] = _combo_items(sort)
                    rec["order_default"] = order()
                    for attempt in range(3):
                        sort.showPopup()
                        yield 1500 + 1000 * attempt
                        ok = d.shot(sort.view(), f"{tag}-02b-sort-by-open")
                        sort.hidePopup()
                        yield 600
                        if ok:
                            break
                    sort.setCurrentIndex(1)
                    yield 1500
                    rec["order_most_answered"] = order()
                    # the first group whose order changed, shown at the top
                    changed = next((i for i, (a, b) in enumerate(
                        zip(rec["order_default"], rec["order_most_answered"]))
                        if a != b), 0)
                    rec["sort_changed_group"] = rec["order_default"][changed][0]

                    def show_group():
                        from PyQt6.QtWidgets import QAbstractItemView
                        n = 0
                        for i in range(pv._tree.topLevelItemCount()):
                            top = pv._tree.topLevelItem(i)
                            if top.childCount():
                                if n == changed:
                                    pv._tree.scrollToItem(
                                        top, QAbstractItemView.ScrollHint
                                        .PositionAtTop)
                                    return
                                n += 1
                    show_group()
                    yield 800
                    d.shot(pv, f"{tag}-02c-sorted-most-answered")
                    sort.setCurrentIndex(0)
                    yield 1200
                    show_group()
                    yield 800
                    d.shot(pv, f"{tag}-02d-same-group-pulldown-order")
                # every type x set: the current chart's answer and the line
                grid = []
                for ti in range(pv._type_combo.count()):
                    pv._type_combo.setCurrentIndex(ti)
                    for si in range(pv._set_combo.count()):
                        pv._set_combo.setCurrentIndex(si)
                        d.pump(150)
                        grid.append({"type": pv._type_combo.currentText(),
                                     "set": pv._set_combo.currentText(),
                                     "current_chart": _current_answered(pv),
                                     "asked_line": pv._asked_label.text()})
                rec["presets_grid"] = grid
                pv._type_combo.setCurrentIndex(0)
                pv._set_combo.setCurrentIndex(0)
                yield 1500
                pv.reject()
                d._modal_closed()
                yield 1500

        if "report" in scenes:
            d.open_project(PROJECT)
            d.set_bar(run="run1", run_type="Verification")
            yield 1000
            d.launch_tool("measurement_report")
            yield 4000
            dlg = _wait(d, "MeasurementReportDialog")
            if dlg is not None:
                rec["report_types"] = _combo_items(dlg._type_combo)
                d.note("report types: " + json.dumps(
                    [(i["text"], i["enabled"]) for i in rec["report_types"]],
                    ensure_ascii=False))
                d.shot(dlg, f"{tag}-03-report-window")
                for attempt in range(3):
                    dlg._type_combo.showPopup()
                    yield 1500 + 1000 * attempt
                    ok = d.shot(dlg._type_combo.view(),
                                f"{tag}-04-report-type-open")
                    dlg._type_combo.hidePopup()
                    yield 600
                    if ok:
                        break
                yield from _info_dialog_of(d, dlg, tr("Judged against"),
                                           f"{tag}-05-judged-against-help",
                                           "judged_against_help", rec)
                yield from _info_dialog_of(d, dlg, tr("Report type"),
                                           f"{tag}-06-report-type-help",
                                           "report_type_help", rec)
                d.later(dlg._limits_btn.click)
                yield 3500
                lim = _wait(d, "ThresholdsDialog", 20)
                if lim is not None:
                    d.shot(lim, f"{tag}-07-report-limits")
                    yield from _info_dialog_of(
                        d, lim, tr("Report limits"),
                        f"{tag}-08-report-limits-help",
                        "report_limits_help", rec)
                    lim.reject()
                    d._modal_closed()
                    yield 1500
                rec["custom_limits"] = {
                    sid: {rid: cs.limit_text(l) for rid, l in
                          cs.limit_bearing(cs.factory_limits(sid)).items()}
                    for sid in ("custom_iso_12647_7", "custom_iso_12647_8")}
                rec["custom_counts"] = {
                    sid: cs.custom_default_counts(sid)
                    for sid in ("custom_iso_12647_7", "custom_iso_12647_8")}
                dlg.close()
                yield 1500

        if "sweep" in scenes:
            sweep = []
            for pdir in sorted(p for p in d.work.iterdir()
                               if (p / "project.json").is_file()):
                d.open_project(pdir.name)
                yield 1200
                b = d.bar
                from core import measurement_target as MT
                idx = b._type_combo.findData(MT.RUN_TYPE_VERIFICATION)
                if idx < 0:
                    sweep.append({"project": pdir.name,
                                  "note": "no Verification run type"})
                    continue
                b._type_combo.setCurrentIndex(idx)
                b._type_combo.activated.emit(idx)
                yield 900
                runs = [b._run_combo.itemData(i)
                        for i in range(b._run_combo.count())]
                runs = [r for r in runs if isinstance(r, str)
                        and r.startswith("run")]
                for run in runs:
                    d.set_bar(run_type="Verification", run=run)
                    yield 900
                    d.launch_tool("measurement_report")
                    yield 3500
                    dlg = _wait(d, "MeasurementReportDialog", 24)
                    if dlg is None:
                        sweep.append({"project": pdir.name, "run": run,
                                      "window": False})
                        continue
                    items = _combo_items(dlg._type_combo)
                    lst = dlg._profile_list
                    entry = {"project": pdir.name, "run": run,
                             "window": True,
                             "window_kind": dlg._window_kind(),
                             "list_rows": lst.count(),
                             "set": dlg._set_combo.currentText(),
                             "types": [(i["text"], i["enabled"],
                                        i["tooltip"]) for i in items
                                       if i["data"]]}
                    sweep.append(entry)
                    d.note(f"   {pdir.name} {run}: kind "
                           f"{entry['window_kind']}; " + "; ".join(
                               f"{t[0]}={'on' if t[1] else 'off'}"
                               for t in entry["types"]))
                    if pdir.name == PROJECT and run == "run1":
                        dlg._type_combo.showPopup()
                        yield 1200
                        d.shot(dlg._type_combo.view(),
                               f"{tag}-09-sweep-{pdir.name}-{run}-types")
                        dlg._type_combo.hidePopup()
                        yield 500
                    dlg.close()
                    yield 1200
            rec["sweep"] = sweep
    return script


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    scenes = (sys.argv[3] if len(sys.argv) > 3
              else "presets,report").split(",")
    projects = [PROJECT]
    if "sweep" in scenes:
        projects = sorted(p.name for p in DEMO_PACK.iterdir()
                          if (p / "project.json").is_file())
    d = Drive(out, projects=projects, language=language)
    rc = d.run(script_for(language, scenes))
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
