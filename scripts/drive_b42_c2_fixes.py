#!/usr/bin/env python3
"""Beta 42, the fixes for challenge round 2, driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<pack> python scripts/drive_b42_c2_fixes.py \
        <out> <en|de> <light|dark|neutral> scene...

Scenes: rewrite, tabs, layout, words, printing, strip.

Run it against any tree (CHROMIQ_TREE, default: this file's own), so the same
script photographs the "before" and the "after". A watchdog answers every
modal the script did not expect (photographed first) and a hard deadline
quits the app: nobody has to click.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

TREE = Path(os.environ.get("CHROMIQ_TREE",
                           str(Path(__file__).resolve().parents[1])))
sys.path.insert(0, str(TREE / "scripts"))
sys.path.insert(0, str(TREE))

EVEN = "Report-Limits-Evenness"
SET = "custom_iso_12647_7"
DEADLINE_S = 1500


def flat(s):
    return " ".join(str(s).split())


def script_for(scenes, lang, look):
    def script(d):
        from PyQt6.QtCore import Qt, QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox, QAbstractButton
        from PyQt6.QtTest import QTest
        from core.i18n import tr as L
        rec = d.record
        rec["found"] = {}
        rec["appearance_setting"] = d.settings.get("appearance", "")
        started = time.monotonic()
        expecting = {"on": False}
        seen = {}

        def watchdog():
            if time.monotonic() - started > DEADLINE_S:
                d.note("WATCHDOG: deadline, quitting")
                QApplication.instance().quit()
                return
            m = QApplication.activeModalWidget()
            if (m is None or not m.isVisible() or expecting["on"]
                    or type(m).__name__ == "MeasurementReportDialog"):
                seen.clear()
                return
            first = seen.setdefault(id(m), time.monotonic())
            if time.monotonic() - first < 8:
                return
            seen.pop(id(m), None)
            said = d.modal_text(m)
            d.note(f"WATCHDOG: unexpected {type(m).__name__}: {said[:300]!r}")
            rec.setdefault("watchdog", []).append(
                {"class": type(m).__name__, "text": said})
            for word in ("Cancel", "Abbrechen", "Close", "Schließen", "OK"):
                for b in m.findChildren(QAbstractButton):
                    if b.isVisible() and b.text().replace("&", "") == word:
                        b.click()
                        return
            m.close()

        if os.environ.get("C2_TRACE_MIN"):
            import ui.dialogs.measurement_report_dialog as _mrd
            _orig = _mrd._TrendChart.setMinimumHeight

            def _traced(chart, h):
                dl = chart.window()
                if h != chart.minimumHeight() and h < 150:
                    lab = getattr(dl, "_mismatch", None)
                    d.note(f"   [trace] chart min {chart.minimumHeight()} -> {h}; "
                           f"win {dl.width()}x{dl.height()} need "
                           f"{dl._layout_need() if hasattr(dl, '_layout_need') else '?'}"
                           f" cap {dl.maximumHeight()} strip wrap "
                           f"{lab.wordWrap() if lab else '?'} h "
                           f"{lab.height() if lab else '?'} view min "
                           f"{dl._view.minimumHeight() if hasattr(dl, '_view') else '?'}"
                           f" list rows {getattr(dl, '_list_rows_shown', '?')}")
                _orig(chart, h)
            _mrd._TrendChart.setMinimumHeight = _traced
            _need0 = _mrd.MeasurementReportDialog._layout_need
            _seen_need = {"n": 0}

            def _need_traced(dl):
                v = _need0(dl)
                if _seen_need["n"] < 3:
                    _seen_need["n"] += 1
                    lay = dl.layout()
                    parts = []

                    def walk(l, depth=0):
                        for i in range(l.count()):
                            it = l.itemAt(i)
                            w = it.widget()
                            nm = type(w).__name__ if w else ("L" if it.layout() else "S")
                            if w is not None and not w.isVisible() and not w.isVisibleTo(dl):
                                continue
                            parts.append(f"{'.'*depth}{nm}:{it.minimumSize().height()}/"
                                         f"{it.heightForWidth(700) if it.hasHeightForWidth() else '-'}")
                            if it.layout() is not None and depth < 1:
                                walk(it.layout(), depth + 1)
                    walk(lay)
                    d.note(f"   [need] {v} w {dl.width()} " + " ".join(parts))
                return v
            _mrd.MeasurementReportDialog._layout_need = _need_traced
            _show0 = _mrd.MeasurementReportDialog.showEvent

            def _show_traced(dl, ev):
                lab = dl._mismatch
                d.note(f"   [show] before: w {dl.width()} strip vis-to "
                       f"{lab.isVisibleTo(dl)} wrap {lab.wordWrap()} min/max "
                       f"{lab.minimumHeight()}/{lab.maximumHeight()} text "
                       f"{lab.text()[-25:]!r} need {_need0(dl)}")
                _show0(dl, ev)
                d.note(f"   [show] after: chart min {dl._trend_de.minimumHeight()} "
                       f"view min {dl._view.minimumHeight()} need {_need0(dl)} "
                       f"cap {dl.maximumHeight()}")
            _mrd.MeasurementReportDialog.showEvent = _show_traced

        dog = QTimer()
        dog.timeout.connect(watchdog)
        dog.start(500)
        rec["_dog"] = str(dog)

        def F(scene, key, val):
            rec["found"].setdefault(scene, {})[key] = val
            d.note(f"   [{scene}] {key}: {str(val)[:500]}")

        def wait_dialog(cls="MeasurementReportDialog"):
            for _ in range(80):
                dl = d.top_dialog(cls)
                if dl is not None:
                    return dl
                d.pump(250)
            return None

        def open_window(project, run_type, run=None):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run)
            d.pump(900)
            d.launch_tool("measurement_report")

        def choose(combo, data):
            i = combo.findData(data)
            if i < 0:
                return False
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            d.pump(1500)
            return True

        def page(dlg):
            return flat(dlg._view.toPlainText())

        def judged_line(dlg):
            t = page(dlg)
            key = L("Judged against")
            return t.split(key, 1)[1][:70] if key in t else None

        def ticks(dlg):
            out = {}
            for i, (kind, _si, key) in enumerate(dlg._list_rows):
                if kind == "run" and key:
                    it = dlg._profile_list.item(i)
                    out[it.text().strip()] = (it.checkState()
                                              == Qt.CheckState.Checked)
            return out

        def state(dlg):
            return {"red_line": dlg._stale_label.isVisible(),
                    "generate_enabled": dlg._generate_btn.isEnabled(),
                    "generate_tip": dlg._generate_btn.toolTip()[:160],
                    "report_shown": dlg._saved_combo.currentText(),
                    "set": dlg._set_combo.currentData(),
                    "judged_line": judged_line(dlg),
                    "heights": {"dialog": dlg.height(),
                                "tabs": dlg._trend_tabs.height(),
                                "tabs_min": dlg._trend_tabs.minimumSizeHint().height(),
                                "chart": dlg._trend_tabs.currentWidget().height(),
                                "view": dlg._view.height(),
                                "strip": dlg._mismatch.height()}}

        def add_file(dlg, path):
            expecting["on"] = True
            d.later(dlg._add_btn.click)
            yield 1500
            d.answer_file(path)
            expecting["on"] = False
            yield 4000

        def read_question(scene, name, key=Qt.Key.Key_Escape):
            m = None
            for _ in range(60):
                d.pump(100)
                m = QApplication.activeModalWidget()
                if isinstance(m, QMessageBox):
                    break
                m = None
            if m is None:
                F(scene, f"{name}-question", None)
                return None
            d.pump(600)
            d.shot(m, name)
            info = {"title": m.text(), "body": flat(m.informativeText())}
            F(scene, f"{name}-question", info)
            QTest.keyClick(m, key)
            d._modal_closed()
            return info

        def shoot_at(dlg, text, name):
            view = dlg._view
            c = view.document().find(text)
            if c.isNull():
                d.note(f"   (not on the page: {text!r})")
                return False
            from PyQt6.QtGui import QTextCursor
            plain = QTextCursor(c)
            plain.setPosition(c.selectionStart())
            view.setTextCursor(plain)
            sb = view.verticalScrollBar()
            sb.setValue(max(0, sb.value() + view.cursorRect(plain).top() - 30))
            d.pump(500)
            d.shot(dlg, name)
            return True

        def crop(name, widget, out_name, pad=4):
            """Cut *widget* out of the window photograph *name*: the photo is
            the frame (title bar included), so the content starts at the
            bottom minus the window's height."""
            try:
                from PyQt6.QtGui import QImage
                img = QImage(str(d.shots / f"{name}.png"))
                win = widget.window()
                dpr = img.height() / max(1, win.height() + 1)
                dpr = round(img.width() / max(1, win.width()))
                top = img.height() - win.height() * dpr
                tl = widget.mapTo(win, widget.rect().topLeft())
                r = (int((tl.x() - pad) * dpr), int(top + (tl.y() - pad) * dpr),
                     int((widget.width() + 2 * pad) * dpr),
                     int((widget.height() + 2 * pad) * dpr))
                part = img.copy(*r)
                part.save(str(d.shots / f"{out_name}.png"))
                return part
            except Exception:                            # noqa: BLE001
                d.note("crop failed\n" + traceback.format_exc())
                return None

        def ink(img, bg=None):
            """How far the darkest/lightest pixel of *img* is from its most
            common colour (its ground): the arrow's contrast, in 0..255."""
            if img is None or img.isNull():
                return None
            from collections import Counter
            px = []
            for y in range(img.height()):
                for x in range(img.width()):
                    c = img.pixelColor(x, y)
                    px.append((c.red(), c.green(), c.blue()))
            ground = Counter(px).most_common(1)[0][0]
            far = max(sum(abs(a - b) for a, b in zip(p, ground)) / 3
                      for p in px)
            return {"ground": ground, "max_contrast": round(far, 1)}

        def guard(fn):
            def run():
                try:
                    yield from fn()
                except Exception:                           # noqa: BLE001
                    d.note(f"SCENE ERROR in {fn.__name__}\n"
                           + traceback.format_exc())
                    rec.setdefault("scene_errors", []).append(
                        {fn.__name__: traceback.format_exc()})
                    for w in QApplication.topLevelWidgets():
                        if (type(w).__name__ == "MeasurementReportDialog"
                                and w.isVisible()):
                            w.close()
                    yield 1500
            return run

        # ==============================================================
        # 1. Nothing redraws the page without Generate (finding 1)
        # ==============================================================
        @guard
        def rewrite():
            sc = "rewrite"
            open_window(EVEN, "Verification", run="run4")
            yield 5000
            dlg = wait_dialog()
            dlg._view.verticalScrollBar().setValue(0)
            p0 = page(dlg)
            F(sc, "00-open", {**state(dlg), "ticks": ticks(dlg)})
            d.shot(dlg, f"{lang}-rw-00-open")
            sheet = d.work / EVEN / "runs" / "run1" / f"{EVEN}.ti3"
            yield from add_file(dlg, sheet)
            p1 = page(dlg)
            F(sc, "01-added-own-sheet-unticked",
              {**state(dlg), "ticks": ticks(dlg), "page_unchanged": p1 == p0})
            d.shot(dlg, f"{lang}-rw-01-added-sheet")
            choose(dlg._set_combo, "chromiq_tight")
            yield 2000
            p2 = page(dlg)
            F(sc, "02-set-changed-to-tight",
              {**state(dlg), "page_unchanged": p2 == p0})
            d.shot(dlg, f"{lang}-rw-02-set-changed")
            hit = None
            for i, (kind, si, key) in enumerate(dlg._list_rows):
                if kind == "source" and si > 0:
                    hit = i
            if hit is not None:
                dlg._profile_list.setCurrentRow(hit)
                d.pump(400)
                dlg._remove_btn.click()
                yield 3000
            p3 = page(dlg)
            F(sc, "03-sheet-removed", {**state(dlg), "page_unchanged": p3 == p0,
                                       "modified": dlg._settings_were_modified()})
            d.shot(dlg, f"{lang}-rw-03-removed")
            expecting["on"] = True
            d.later(dlg._generate_btn.click)
            yield 600
            read_question(sc, f"{lang}-rw-04", Qt.Key.Key_Escape)
            expecting["on"] = False
            yield 2000
            F(sc, "05-after-escape", {**state(dlg),
                                      "page_unchanged": page(dlg) == p0})
            dlg.close()
            yield 1500

            # B: the sheet TICKED beside the verification (Generate greyed by
            # the mixed kinds): a setting change keeps the page
            open_window(EVEN, "Verification", run="run4")
            yield 5000
            dlg = wait_dialog()
            dlg._view.verticalScrollBar().setValue(0)
            q0 = page(dlg)
            yield from add_file(dlg, sheet)
            for i, (kind, _si, key) in enumerate(dlg._list_rows):
                it = dlg._profile_list.item(i)
                if kind == "run" and it.checkState() != Qt.CheckState.Checked:
                    it.setCheckState(Qt.CheckState.Checked)
            d.pump(1500)
            F(sc, "10-sheet-ticked-mixed", {**state(dlg),
                                            "page_unchanged": page(dlg) == q0})
            d.shot(dlg, f"{lang}-rw-10-ticked-mixed")
            dlg._detail_check.toggle()
            d.pump(1500)
            choose(dlg._set_combo, "chromiq_tight")
            yield 1500
            F(sc, "11-greyed-detail-and-set-changed",
              {**state(dlg), "page_unchanged": page(dlg) == q0,
               "settings_live": [dlg._type_combo.isEnabled(),
                                 dlg._set_combo.isEnabled(),
                                 dlg._detail_check.isEnabled()]})
            d.shot(dlg, f"{lang}-rw-11-greyed-changed")
            dlg.close()
            yield 1500

            # C: Clear List, and a file measured again and added again
            open_window(EVEN, "Verification", run="run4")
            yield 5000
            dlg = wait_dialog()
            dlg._view.verticalScrollBar().setValue(0)
            c0 = page(dlg)
            own = Path(str(dlg._sources[0]["ti3"]))
            dlg._clear_btn.click()
            yield 2500
            F(sc, "20-cleared", {**state(dlg), "page_unchanged": page(dlg) == c0,
                                 "pdf_enabled": dlg._pdf_btn.isEnabled(),
                                 "rows": len(dlg._list_rows)})
            d.shot(dlg, f"{lang}-rw-20-cleared")
            dlg.close()
            yield 1500
            open_window(EVEN, "Verification", run="run4")
            yield 5000
            dlg = wait_dialog()
            dlg._view.verticalScrollBar().setValue(0)
            c0 = page(dlg)
            own = Path(str(dlg._sources[0]["ti3"]))
            # measured again in place: the same file, one value changed
            txt = own.read_text(encoding="utf-8").splitlines()
            import re as _re
            for i, line in enumerate(txt):
                if _re.match(r"^\s*\d+\s", line) and i > 20:
                    parts = line.split()
                    try:
                        parts[-1] = f"{float(parts[-1]) + 3.0:.5f}"
                    except ValueError:
                        continue
                    txt[i] = " ".join(parts)
                    break
            own.write_text("\n".join(txt) + "\n", encoding="utf-8")
            os.utime(own, None)
            yield from add_file(dlg, own)
            F(sc, "21-changed-file-added-again",
              {**state(dlg), "page_unchanged": page(dlg) == c0})
            d.shot(dlg, f"{lang}-rw-21-changed-file-readded")
            dlg.close()
            yield 1500

        # ==============================================================
        # The window every layout scene stands on: Evenness run1
        # Verification, every date ticked, Custom ISO 12647-7, generated
        # ==============================================================
        def big_report():
            open_window(EVEN, "Verification", run="run1")
            yield 5000
            dlg = wait_dialog()
            dlg._saved_combo.setCurrentIndex(0)
            dlg._saved_combo.activated.emit(0)
            d.pump(1500)
            dlg._select_all_btn.click()
            choose(dlg._set_combo, SET)
            d.later(dlg._generate_btn.click)
            yield 6000
            rec["_dlg"] = dlg

        # ==============================================================
        # 2. The tab bar's greyed arrow (finding 2)
        # ==============================================================
        @guard
        def tabs():
            sc = "tabs"
            yield from big_report()
            dlg = rec.pop("_dlg")
            bar = dlg._trend_tabs.tabBar()
            for wname, width in (("narrow", 820), ("wide", 1500)):
                dlg.resize(width, dlg.height())
                yield 1500
                for _ in range(15):
                    if not bar.peek_state()["arrows"][0]:
                        break
                    bar.scroll_left()
                d.pump(600)
                out = []
                for k in range(12):
                    ps = bar.peek_state()
                    name = f"{lang}-{look}-{wname}-tabs-{k:02d}"
                    d.shot(dlg, name)
                    crop(name, bar, f"{name}-bar")
                    lft = ink(crop(name, bar._left_btn, f"{name}-left", pad=0))
                    rgt = ink(crop(name, bar._right_btn, f"{name}-right",
                                   pad=0))
                    area = ps["area"]
                    drawn = sum(max(0, min(r, area - 1) - max(lo, 0) + 1)
                                for lo, r in (ps["rects"][i]
                                              for i in ps["visible"]))
                    out.append({"live": ps["arrows"],
                                "shown": {dlg._trend_tabs.tabText(i):
                                          round(v, 2)
                                          for i, v in ps["shown"].items()
                                          if v},
                                "clip": ps["clip"], "area": area,
                                "gap_px": (area - drawn
                                           if ps["arrows_shown"] else 0),
                                "title": dlg._trend_label.text(),
                                "left": lft, "right": rgt})
                    if not ps["arrows"][1]:
                        break
                    bar._right_btn.click()
                    d.pump(500)
                F(sc, f"arrows-{look}-{wname}", out)
            dlg.close()
            yield 1500

        # ==============================================================
        # 3. No horizontal scroll bar under the page (finding 3)
        # ==============================================================
        @guard
        def layout():
            sc = "layout"
            yield from big_report()
            dlg = rec.pop("_dlg")
            from PyQt6.QtGui import QTextTable

            def tables(frame):
                for f in frame.childFrames():
                    if isinstance(f, QTextTable):
                        yield f
                    yield from tables(f)

            def measure(tag):
                doc = dlg._view.document()
                head = doc.find(L("Overview of Measurement Metrics"))
                cols = [t.columns() - 1 for t in tables(doc.rootFrame())
                        if not head.isNull()
                        and t.firstPosition() > head.position()]
                hb = dlg._view.horizontalScrollBar()
                return {"win_w": dlg.width(),
                        "viewport": dlg._view.viewport().width(),
                        "doc_w": round(doc.size().width(), 2),
                        "hscroll_max": hb.maximum(),
                        "hscroll_visible": hb.isVisible(),
                        "dates_per_table": cols[:8]}
            for wname, width in (("wide", 1700), ("w1500", 1500),
                                 ("w1234", 1234), ("narrow", 820),
                                 ("minimum", 300)):
                dlg.resize(width, dlg.height())
                yield 2000
                F(sc, f"{wname}-after-resize", measure(wname))
                dlg._render()
                yield 1500
                F(sc, f"{wname}-redrawn", measure(wname))
                if wname in ("wide", "narrow"):
                    sb = dlg._view.verticalScrollBar()
                    sb.setValue(sb.maximum())
                    d.pump(500)
                    shoot_at(dlg, L("Overview of Measurement Metrics"),
                             f"{lang}-ly-{wname}-overview")
                    crop(f"{lang}-ly-{wname}-overview", dlg._view,
                         f"{lang}-ly-{wname}-view")
            dlg.close()
            yield 1500

        # ==============================================================
        # 4. The limit words stay beside their own line (finding 4)
        # ==============================================================
        @guard
        def words():
            sc = "words"
            yield from big_report()
            dlg = rec.pop("_dlg")
            for wname, width in (("wide", 1700), ("narrow", 820)):
                dlg.resize(width, dlg.height())
                yield 1500
                t = dlg._trend_tabs
                got = {}
                for i in range(t.count()):
                    if not t.isTabVisible(i):
                        continue
                    t.setCurrentIndex(i)
                    d.pump(600)
                    ch = t.widget(i)
                    boxes = getattr(ch, "_word_boxes", None) or []
                    lines = sorted(yy for _r, _w, yy in boxes)
                    rows = []
                    for r, where, yy in boxes:
                        cy = r.center().y()
                        between = [ly for ly in lines if ly != yy
                                   and min(cy, yy) < ly < max(cy, yy)]
                        rows.append({"where": where, "line_y": round(yy, 1),
                                     "word_cy": round(cy, 1),
                                     "another_line_between": bool(between)})
                    got[t.tabText(i)] = rows
                    if i == 0:
                        name = f"{lang}-wd-{wname}-colour-accuracy"
                        d.shot(dlg, name)
                        crop(name, ch, f"{name}-graph")
                F(sc, wname, got)
                F(sc, f"{wname}-state", state(dlg))
            dlg.close()
            yield 1500

        # ==============================================================
        # 5. The Printing record's graph sentence (finding 5)
        # ==============================================================
        @guard
        def printing():
            sc = "printing"
            from workflow.measurement_report import REPORT_TYPE_RECORD
            open_window(EVEN, "Profiling", run="run1")
            yield 5000
            dlg = wait_dialog()
            for label, one in (("all", False), ("one", True)):
                dlg._saved_combo.setCurrentIndex(0)
                dlg._saved_combo.activated.emit(0)
                d.pump(1500)
                choose(dlg._type_combo, REPORT_TYPE_RECORD)
                if one:
                    dlg._deselect_all_btn.click()
                    d.pump(800)
                    for i, (kind, _si, key) in enumerate(dlg._list_rows):
                        if kind == "run" and key:
                            dlg._profile_list.item(i).setCheckState(
                                Qt.CheckState.Checked)
                            break
                else:
                    dlg._select_all_btn.click()
                d.pump(1200)
                d.later(dlg._generate_btn.click)
                yield 6000
                txt = page(dlg)
                # the first words of the sentence, in the window's language
                start = L("This report is not graded, so it carries no graph "
                          "of a judged metric: each of those graphs is drawn "
                          "against its limit. The graphs it carries show "
                          "colour accuracy, paper white, darkest black and "
                          "the cube corners.")[:25]
                sent = (txt[txt.index(start):txt.index(start) + 400]
                        if start in txt else None)
                t = dlg._trend_tabs
                drawn = [t.tabText(i) for i in range(t.count())
                         if t.isTabVisible(i) and t.widget(i).has_trend()]
                F(sc, label, {"sentence": sent, "graphs_drawn": drawn,
                              **state(dlg)})
                shoot_at(dlg, start, f"{lang}-pr-{label}-sentence")
                d.shot(dlg, f"{lang}-pr-{label}-graphs")
            dlg.close()
            yield 1500

        # ==============================================================
        # 7. The strip's "…" is whole (finding 7)
        # ==============================================================
        @guard
        def strip():
            sc = "strip"
            yield from big_report()
            dlg = rec.pop("_dlg")
            for wname, width in (("narrow", 820), ("w1000", 1000),
                                 ("minimum", 300)):
                dlg.resize(width, dlg.height())
                yield 2000
                lab = dlg._mismatch
                from PyQt6.QtGui import QFontMetrics
                fm = QFontMetrics(lab.font())
                F(sc, wname + "-state", state(dlg))
                F(sc, wname, {"win_w": dlg.width(), "label_w": lab.width(),
                              "text_w": fm.horizontalAdvance(lab.text()),
                              "wrap": lab.wordWrap(),
                              "ends": lab.text()[-30:]})
                dlg._view.verticalScrollBar().setValue(0)
                name = f"{lang}-st-{wname}"
                d.shot(dlg, name)
                crop(name, lab, f"{name}-strip")
            dlg.close()
            yield 1500

        order = {"rewrite": rewrite, "tabs": tabs, "layout": layout,
                 "words": words, "printing": printing, "strip": strip}
        for s in scenes:
            d.note(f"==== scene {s} ({lang}, {look})")
            yield from order[s]()
        dog.stop()
        rec.pop("_dog", None)
        (d.out / "found.json").write_text(json.dumps(
            rec["found"], indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
    return script


def main():
    out = Path(sys.argv[1])
    lang, look = sys.argv[2], sys.argv[3]
    scenes = sys.argv[4:]
    from userdrive import Drive
    # The report page reads its colours from the SETTING. A tree whose
    # userdrive does not write it yet (the "before" tree) needs it here.
    from core.settings import AppSettings
    AppSettings().set("appearance", look)
    d = Drive(out, projects=[EVEN], language=lang, appearance=look)
    return d.run(script_for(scenes, lang, look))


if __name__ == "__main__":
    raise SystemExit(main())
