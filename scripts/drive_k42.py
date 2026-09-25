#!/usr/bin/env python3
"""#182 K42 (Knut on beta 42, 5832746557), driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_k42.py <out> <en|de> \\
        <light|dark|neutral> [tabs] [types] [gear]

scenes:
    tabs   K42-1: Report-Limits-Evenness run1 as Verification, New report,
           every date, Custom ISO 12647-7, Generate; the window narrowed so
           the graph tabs overflow; the tab bar at the left end and one step
           right, photographed, with the arrows' geometry in logical and
           device pixels and a magnified crop of the arrows.
    types  K42-2: the same measurements under each of the six report types
           (the one-page summary on one date), Custom ISO 12647-7 where the
           type allows it; where the PASS sentence stands in the window and
           in the saved PDF, and what follows it.
    gear   K42-3: the built-in presets window (the gear on Create Chart), its
           paragraphs.
    filter Knut 5833232475 (B8-1145): Create Chart on Manual A4 with a fresh
           settings file: the filter ON, every own preset listed (a Letter one
           too), only A4 built-ins, an arrow opened; the gear window's list
           with the box on and off, and its two help texts.

**A WATCHDOG ANSWERS WHAT THE SCRIPT DID NOT EXPECT.** Every 500 ms it looks
for a modal window that is not ours; one left up for 12 s is recorded and
closed with Cancel / Close / OK (English or German), or Escape. A hard
deadline quits the app. Basti never has to click.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

EVEN = "Report-Limits-Evenness"
SET = "custom_iso_12647_7"
DEADLINE_S = 900
PROOF = ("A PASS means that the measured values are inside these limits. It "
         "is not proof that the print meets the standard, and where these "
         "limits are wider than the standard's own it says nothing about the "
         "standard.")


def _flat(s: str) -> str:
    return " ".join(str(s).split())


def script_for(scenes, language, look):
    def script(d):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from core.i18n import tr as L
        rec = d.record
        rec.update({"language": language, "appearance": look, "checks": [],
                    "found": {}})
        tag = f"{language}-{look}"
        started = time.monotonic()
        expecting = {"on": False}
        seen_since: dict = {}

        def watchdog():
            if time.monotonic() - started > DEADLINE_S:
                d.note("WATCHDOG: deadline reached, quitting")
                QApplication.instance().quit()
                return
            m = QApplication.activeModalWidget()
            if (m is None or not m.isVisible() or expecting["on"]
                    or type(m).__name__ in ("MeasurementReportDialog",
                                            "BuiltinPresetsShownDialog")):
                seen_since.clear()
                return
            first = seen_since.setdefault(id(m), time.monotonic())
            if time.monotonic() - first < 12:
                return
            seen_since.pop(id(m), None)
            from PyQt6.QtWidgets import QAbstractButton
            said = d.modal_text(m)
            d.note(f"WATCHDOG: unexpected {type(m).__name__}: {said[:200]!r}")
            rec.setdefault("watchdog", []).append(
                {"class": type(m).__name__, "text": said})
            for word in ("Cancel", "Abbrechen", "Close", "Schließen", "OK"):
                for b in m.findChildren(QAbstractButton):
                    if b.isVisible() and b.text().replace("&", "") == word:
                        b.click()
                        return
            m.close()

        dog = QTimer()
        dog.timeout.connect(watchdog)
        dog.start(500)
        rec["_dog"] = str(dog)

        def check(what, ok, detail=""):
            rec["checks"].append({"what": what, "ok": bool(ok),
                                  "detail": detail})
            d.note(f"   {'OK  ' if ok else 'FAIL'} {what} {detail}")

        def wait_dialog(cls="MeasurementReportDialog"):
            for _ in range(80):
                dlg = d.top_dialog(cls)
                if dlg is not None:
                    return dlg
                d.pump(250)
            return None

        def open_report():
            d.open_project(EVEN)
            d.set_bar(run_type="Verification", run="run1")
            d.pump(900)
            d.launch_tool("measurement_report")

        def new_report(dlg):
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            d.pump(1500)

        def choose_set(dlg, set_id):
            i = dlg._set_combo.findData(set_id)
            if i < 0:
                return False
            dlg._set_combo.setCurrentIndex(i)
            dlg._set_combo.activated.emit(i)
            d.pump(1500)
            return True

        def choose_type(dlg, tid):
            c = dlg._type_combo
            i = c.findData(tid)
            if i < 0:
                return False
            c.setCurrentIndex(i)
            c.activated.emit(i)
            d.pump(1500)
            return c.currentData() == tid

        def tick_only_first(dlg):
            dlg._deselect_all_btn.click()
            d.pump(600)
            lw = dlg._profile_list
            from PyQt6.QtCore import Qt
            # the LAST dated measurement (a header row is not a date)
            rows = [i for i, r in enumerate(dlg._list_rows) if r[0] == "run"]
            if rows:
                lw.item(rows[-1]).setCheckState(Qt.CheckState.Checked)
            d.pump(800)

        def shoot_at(dlg, text, name):
            view = dlg._view
            c = view.document().find(text)
            if c.isNull():
                d.note(f"   (not on the page: {text[:60]!r})")
                return False
            from PyQt6.QtGui import QTextCursor
            plain = QTextCursor(c)
            plain.setPosition(c.selectionStart())
            view.setTextCursor(plain)
            sb = view.verticalScrollBar()
            sb.setValue(max(0, sb.value() + view.cursorRect(plain).top()
                            - view.viewport().height() // 2))
            d.pump(500)
            d.shot(dlg, name)
            return True

        def save_pdf(dlg, name):
            from drive_g12_notes import pdf_pages_text, render_pdf
            target = d.out / "pdf" / f"{name}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target.unlink()
            expecting["on"] = True
            d.later(dlg._pdf_btn.click)
            yield 1500
            d.answer_file(target, name=None)
            expecting["on"] = False
            for _ in range(120):
                yield 1000
                if target.exists():
                    break
            yield 2500
            text, pages = [], []
            if target.exists():
                pages_dir = d.out / "pdf-pages"
                pages_dir.mkdir(exist_ok=True)
                pages = render_pdf(target, pages_dir)
                text = pdf_pages_text(target)
            d.note(f"   PDF {target.name}: "
                   f"{'written' if target.exists() else 'NOT WRITTEN'}")
            return text, pages

        # ------------------------------------------------------------------
        if "tabs" in scenes:
            d.note(f"[tabs] {EVEN} run1, Verification, New report, Custom ISO")
            open_report()
            yield 4000
            dlg = wait_dialog()
            new_report(dlg)
            dlg._select_all_btn.click()
            d.pump(1500)
            choose_set(dlg, SET)
            d.later(dlg._generate_btn.click)
            yield 6000
            dlg.resize(900, dlg.height())
            yield 1500
            bar = dlg._trend_tabs.tabBar()
            ps = bar.peek_state() if hasattr(bar, "peek_state") else None
            from PyQt6.QtWidgets import QToolButton
            arrows = [b for b in bar.findChildren(QToolButton)
                      if b.isVisible()]
            dpr = dlg.devicePixelRatioF()
            geo = [{"x": b.x(), "y": b.y(), "w": b.width(), "h": b.height(),
                    "w_device_px": round(b.width() * dpr),
                    "enabled": b.isEnabled(),
                    "autoRaise": b.autoRaise(),
                    "objectName": b.objectName()} for b in arrows]
            found = {"bar_w": bar.width(), "bar_h": bar.height(),
                     "dpr": dpr, "arrows": geo,
                     "area": ps["area"] if ps else None,
                     "arrow_rects": ps.get("arrow_rects") if ps else None}
            rec["found"]["tabs"] = found
            d.note(f"   tab bar {bar.width()}x{bar.height()} at dpr {dpr}; "
                   f"arrows {[(g['w'], g['h']) for g in geo]} logical px")
            check("the tab bar overflows (arrows shown)", len(arrows) == 2,
                  repr(geo))
            for k, name in enumerate(("left-end", "one-step-right")):
                d.shot(dlg, f"{tag}-01-tabs-{name}")
                crop_arrows(d, dlg, bar, arrows, f"{tag}-01-tabs-{name}",
                            f"{tag}-02-arrows-{name}-x4")
                if k == 0 and ps is not None:
                    bar.scroll_right()
                    d.pump(700)
            dlg.close()
            yield 1500

        # ------------------------------------------------------------------
        if "types" in scenes:
            from workflow.measurement_report import REPORT_TYPES
            d.note(f"[types] {EVEN} run1, Verification, every report type")
            open_report()
            yield 4000
            dlg = wait_dialog()
            want = _flat(L(PROOF))
            types = {}
            for n, tid in enumerate(REPORT_TYPES):
                if tid.startswith("t4"):
                    # the Printing record is a profiling measurement's
                    # report (K13): a Profiling window
                    dlg.close()
                    yield 1500
                    d.set_bar(run_type="Profiling", run="run1")
                    d.pump(900)
                    d.launch_tool("measurement_report")
                    yield 4000
                    dlg = wait_dialog()
                new_report(dlg)
                if tid.startswith("t1"):
                    tick_only_first(dlg)
                else:
                    dlg._select_all_btn.click()
                    d.pump(1200)
                ok_type = choose_type(dlg, tid)
                ok_set = choose_set(dlg, SET)
                set_now = dlg._set_combo.currentData()
                d.later(dlg._generate_btn.click)
                yield 7000
                page = _flat(dlg._view.toPlainText())
                at = page.find(want)
                after = page[at + len(want):at + len(want) + 160] \
                    if at >= 0 else ""
                before = page[max(0, at - 160):at] if at >= 0 else ""
                info = {"type_chosen": ok_type,
                        "type_shown": dlg._type_combo.currentText(),
                        "set": set_now, "set_chosen": ok_set,
                        "window_has_it": at >= 0,
                        "window_ends_with_it": at >= 0 and page.rstrip()
                        .endswith(want),
                        "window_before": before, "window_after": after}
                name = f"{language}-{look}-t{n + 1}"
                if at >= 0:
                    shoot_at(dlg, L(PROOF)[:60], f"{name}-window")
                else:
                    d.shot(dlg, f"{name}-window-no-sentence")
                text, pages = yield from save_pdf(dlg, name)
                pdf_pages = [i + 1 for i, t in enumerate(text)
                             if want[:70] in _flat(t)]
                joined = _flat(" ".join(text))
                pat = joined.find(want[:70])
                info.update({"pdf_pages_with_it": pdf_pages,
                             "pdf_page_count": len(text),
                             "pdf_after": joined[pat + len(want):
                                                 pat + len(want) + 160]
                             if pat >= 0 else "",
                             "pdf_ends_with_it": pat >= 0 and joined.rstrip()
                             .endswith(want[-60:]),
                             "pdf_page_images": [pages[i - 1]
                                                 for i in pdf_pages]})
                types[tid] = info
                if tid.startswith("t4"):
                    dlg.close()
                    yield 1500
                    d.set_bar(run_type="Verification", run="run1")
                    d.pump(900)
                    d.launch_tool("measurement_report")
                    yield 4000
                    dlg = wait_dialog()
                d.note(f"   {tid}: window {'has' if at >= 0 else 'NO'} "
                       f"sentence; ends with it {info['window_ends_with_it']};"
                       f" PDF pages {pdf_pages}; after: {after[:80]!r}")
            rec["found"]["types"] = types
            t1 = types.get("t1_colour_summary", {})
            check("T1 window: the sentence is there",
                  t1.get("window_has_it"))
            check("T1 window: the page does not end with it",
                  not t1.get("window_ends_with_it"))
            check("T1 PDF: does not end with it",
                  not t1.get("pdf_ends_with_it"))
            for tid, info in types.items():
                if tid != "t1_colour_summary":
                    check(f"{tid}: does not end with the sentence",
                          not info["window_ends_with_it"]
                          and not info["pdf_ends_with_it"])
            dlg.close()
            yield 1500

        # ------------------------------------------------------------------
        if "gear" in scenes:
            d.goto_tab("chart")
            yield 1500
            tab = d.win._tab_chart
            d.later(tab._preset_shown_btn.click)
            yield 1800
            g = d.top_dialog("BuiltinPresetsShownDialog")
            check("the gear opens the window", g is not None)
            if g is not None:
                rec["found"]["gear_intro"] = g._intro.text()
                d.shot(g, f"{tag}-10-gear-window")
                g._close_btn.click()
                d._modal_closed()
                yield 1200

        # ------------------------------------------------------------------
        if "filter" in scenes:
            # Knut, 5833232475: ON by default, built-ins only, the arrow still
            # opens the rest of the paper's presets, the window's own list is
            # never filtered, and two help icons.
            from core import curated_presets as cp
            from PyQt6.QtCore import Qt
            d.goto_tab("chart")
            yield 1500
            tab = d.win._tab_chart
            tab._user_switch_mode("manual")
            yield 1200
            tab._set_manual_value("printtarg", "-p", "A4")
            yield 1200
            cb = tab._preset_combo
            view = cb.view()
            on = cp.paper_filter_on(d.settings)
            check("the filter is ON for a fresh settings file", on is True)

            def listed():
                return [(cb.itemText(r), cb.itemData(r),
                         cb.itemData(r, cb.GROUP_ROLE))
                        for r in range(cb.count()) if not view.isRowHidden(r)]

            from ui.tabs.tab_chart import builtin_preset_paper
            rows = listed()
            own = [t for t, k, g in rows if isinstance(k, str) and not g
                   and k in OWN_PRESETS]
            check("every own preset is listed on A4, a Letter one included",
                  sorted(own) == sorted(OWN_PRESETS), repr(own))
            built = [(k, builtin_preset_paper(k), g) for _t, k, g in rows
                     if isinstance(k, str) and g and not cp.is_more_row(k)]
            wrong = [x for x in built if x[1] != "A4"
                     and not str(x[2]).startswith("Scanner")]
            check("every built-in listed is on A4 (or Scanner)", not wrong,
                  repr(wrong[:4]))
            rec["found"]["filter_listed_on_A4"] = [t for t, _k, _g in rows]
            # B8-1146: the groups in the Instrument pulldown's order
            from data.patch_db import INSTRUMENT_LABELS
            heads = []
            for _t, _k, g in rows:
                if g and (not heads or heads[-1] != g):
                    heads.append(g)
            rec["found"]["pulldown_group_order"] = heads
            instr = [h for h in heads if h in INSTRUMENT_LABELS.values()]
            check("the pulldown's instrument groups follow the Instrument "
                  "pulldown", instr == [h for h in INSTRUMENT_LABELS.values()
                                        if h in instr], repr(heads))
            check("Scanner and Red River Paper last",
                  heads[-2:] == ["Scanner", "Red River Paper"]
                  or heads[-1:] == ["Red River Paper"], repr(heads[-2:]))
            instr_combo = tab._instr_combo
            rec["found"]["instrument_pulldown"] = [
                instr_combo.itemText(i) for i in range(instr_combo.count())]
            tab._open_builtin_preset_overlay()
            yield 1200
            pop = getattr(tab, "_builtin_preset_popup", None)
            if pop is not None:
                rec["found"]["overlay_group_order"] = [h for h, _e in
                                                       pop._groups]
                d.shot(pop, f"{tag}-25-builtin-presets-list")
                pop.close()
                yield 600
            cb.showPopup()
            yield 900
            view.scrollToTop()
            yield 500
            d.shot(view, f"{tag}-20-select-preset-A4-filter-on")
            cb.hidePopup()
            yield 500
            # open the first arrow that holds something
            more = [(r, cb.itemData(r, cb.MORE_ROLE),
                     cb.itemData(r, Qt.ItemDataRole.UserRole + 44))
                    for r in range(cb.count())
                    if cb.itemData(r, cb.MORE_ROLE)
                    and not view.isRowHidden(r)]
            check("an arrow is shown with the filter on", bool(more),
                  repr([(g, n) for _r, g, n in more][:6]))
            if more:
                row, group, n = more[0]
                before = {k for _t, k, _g in listed()}
                tab._open_preset_groups().add(group)
                tab._apply_preset_collapse()
                yield 600
                after = [(k, builtin_preset_paper(k)) for _t, k, g in listed()
                         if isinstance(k, str) and k not in before
                         and g == group]
                check(f"opening '{group}' shows its {n} other A4 presets",
                      len(after) == n and all(p == "A4" for _k, p in after),
                      repr(after[:4]))
                cb.showPopup()
                yield 900
                view.scrollTo(cb.model().index(row, 0))
                yield 500
                d.shot(view, f"{tag}-21-select-preset-arrow-opened")
                cb.hidePopup()
                yield 500
            d.later(tab._preset_shown_btn.click)
            yield 1800
            g = d.top_dialog("BuiltinPresetsShownDialog")
            check("the gear opens the window", g is not None)
            if g is not None:
                def tree_rows():
                    out = []
                    for i in range(g._tree.topLevelItemCount()):
                        it = g._tree.topLevelItem(i)
                        out += [it.child(j).text(0)
                                for j in range(it.childCount())
                                if not it.child(j).isHidden()]
                    return out
                from ui.tabs.tab_chart import BUILTIN_PRESET_KEYS
                r1 = tree_rows()
                rec["found"]["gear_group_order"] = [
                    g._tree.topLevelItem(i).text(0)
                    for i in range(g._tree.topLevelItemCount())]
                check("the window lists every built-in with the box on",
                      len(r1) == len(BUILTIN_PRESET_KEYS),
                      f"{len(r1)} of {len(BUILTIN_PRESET_KEYS)}")
                check("the box opens ticked", g._paper_filter.isChecked())
                rec["found"]["gear_intro_filter"] = g._intro.text()
                d.shot(g, f"{tag}-22-gear-box-on")
                g._paper_filter.setChecked(False)
                yield 500
                r2 = tree_rows()
                check("unticking the box changes nothing in the window",
                      r2 == r1)
                g._paper_filter.setChecked(True)
                yield 400
                for btn, name in ((g._help, "23-help-window"),
                                  (g._paper_filter_help, "24-help-box")):
                    expecting["on"] = True
                    d.later(btn.click)
                    yield 1500
                    m = QApplication.activeModalWidget()
                    ok = m is not None and m is not g
                    check(f"the {name} icon opens its text", ok)
                    if ok:
                        rec["found"][name] = d.modal_text(m)
                        d.shot(m, f"{tag}-{name}")
                        m.accept()
                        d._modal_closed()
                    expecting["on"] = False
                    yield 1000
                g._close_btn.click()
                d._modal_closed()
                yield 1200

        dog.stop()
        rec.pop("_dog", None)
        (d.out / "k42-found.json").write_text(
            json.dumps({k: rec.get(k) for k in ("checks", "found",
                                                 "language", "appearance",
                                                 "watchdog")},
                       indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
    return script


def crop_arrows(d, dlg, bar, arrows, photo, name) -> None:
    """A magnified crop of the photograph just taken around the arrows,
    placed from the window's own geometry (the photograph is the FRAME,
    title bar included)."""
    try:
        from PIL import Image
        img = Image.open(d.shots / f"{photo}.png")
        win = dlg.window()
        fg, gg = win.frameGeometry(), win.geometry()
        s = img.width / fg.width()
        left = min(b.mapTo(win, b.rect().topLeft()).x() for b in arrows)
        top = bar.mapTo(win, bar.rect().topLeft()).y()
        x0 = (gg.x() - fg.x() + left - 60) * s
        y0 = (gg.y() - fg.y() + top - 4) * s
        x1 = (gg.x() - fg.x() + bar.mapTo(win, bar.rect().topRight()).x()
              + 6) * s
        y1 = y0 + (bar.height() + 8) * s
        c = img.crop((int(x0), int(y0), int(x1), int(y1)))
        c = c.resize((c.width * 4, c.height * 4), Image.NEAREST)
        c.save(d.shots / f"{name}.png")
        d.note(f"   [crop] {name}.png")
    except Exception as exc:                               # noqa: BLE001
        d.note(f"   [crop] {name}: FAILED {exc}")


#: Own presets seeded into the SANDBOXED presets folder for the filter
#: scene: on A4 every one of them must be listed.
OWN_PRESETS = {"My A4 preset (driver)": {"printtarg_-p": "A4"},
               "My Letter preset (driver)": {"printtarg_-p": "Letter"},
               "My preset without a paper (driver)": {"auto_run": False}}


def _seed_own_presets() -> None:
    import os
    folder = Path(os.environ["CHROMIQ_PRESETS_DIR"]) / "Create Chart"
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in OWN_PRESETS.items():
        (folder / (name + ".json")).write_text(json.dumps({
            "chromiq_preset_version": 1, "tab": "create_chart",
            "name": name, "data": data}), encoding="utf-8")


def main() -> int:
    out = Path(sys.argv[1])
    language = sys.argv[2] if len(sys.argv) > 2 else "en"
    look = sys.argv[3] if len(sys.argv) > 3 else "light"
    scenes = tuple(sys.argv[4:]) or ("tabs", "types", "gear")
    if "filter" in scenes:
        _seed_own_presets()
    from userdrive import Drive
    d = Drive(out, projects=[EVEN], language=language, appearance=look)
    return d.run(script_for(scenes, language, look))


if __name__ == "__main__":
    raise SystemExit(main())
