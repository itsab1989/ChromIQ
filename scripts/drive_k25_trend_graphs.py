#!/usr/bin/env python3
"""#182 K25, the trend graphs explain themselves, driven ON SCREEN.

    CHROMIQ_DEMO_PACK=<report-limit demo pack> \\
        python scripts/drive_k25_trend_graphs.py <out-dir> limits
    CHROMIQ_DEMO_PACK=<folder with Report-Limits-Red-X and -Evenness> \\
        python scripts/drive_k25_trend_graphs.py <out-dir> redx [de]

limits:
    L1  Every-Limit-Set run10, every date, Generate: every shown tab
        photographed (units in every legend), each word's tooltip recorded,
        one hovered with the real pointer and its tooltip photographed; PDF.
    L2  Threshold-Series run1, every date: the same, and which words were
        moved inside the plot or along their line (the collision rule).
redx:
    R1  Red-X run1, all seven dates: the red x at the floor, at one
        neighbour's height and at the mean of two; a red x hovered; PDF.
    R2  only B, D, E ticked: B has no neighbour with a point, so the floor.
    R3  C ticked as well: B moves up to C's height.
    R4  Report-Limits-Evenness run1 as it ships: its noisy last date; PDF.
    R5  one date ticked: the "at least two measurements" text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from userdrive import Drive                                   # noqa: E402

LIMITS = ("Report-Limits-Threshold-Series", "Report-Limits-Every-Limit-Set")
REDX = ("Report-Limits-Red-X", "Report-Limits-Evenness")


def tabs(dlg) -> list:
    t = dlg._trend_tabs
    return [(t.tabText(i), t.isTabVisible(i)) for i in range(t.count())]


def chart_info(chart) -> dict:
    """What a chart shows: legend, lines with their notes, red x, words."""
    return {
        "legend": [m[0] for m in chart._metrics],
        "dates": [str(p.get("created"))[:16] for p in chart._series],
        "y_range": [round(v, 3) for v in chart._y_range()]
        if len(chart._series) >= 2 else None,
        "lines": [(v, w, n) for v, w, _c, n in chart._lines()],
        "red_x": [{"date": chart._date_label(i), "metric": k,
                   "height": (round(v, 3) if v is not None else "FLOOR"),
                   "tooltip": t} for k, i, v, t in chart.withheld_marks()],
        "hits": [{"rect": [round(r.left(), 1), round(r.top(), 1),
                           round(r.width(), 1), round(r.height(), 1)],
                  "text": t} for r, t in chart._hits],
        "pdf_key": [t for _k, _c, t in chart.descriptions()],
    }


def render_pdf(pdf: Path, out: Path) -> list:
    from PyQt6.QtCore import QSize
    from PyQt6.QtPdf import QPdfDocument
    doc = QPdfDocument(None)
    doc.load(str(pdf))
    pages = []
    for i in range(doc.pageCount()):
        sz = doc.pagePointSize(i)
        img = doc.render(i, QSize(int(sz.width() * 2), int(sz.height() * 2)))
        p = out / f"{pdf.stem}-page{i + 1:02d}.png"
        img.save(str(p))
        pages.append(p.name)
    return pages


def pdf_text(pdf: Path) -> str:
    from PyQt6.QtPdf import QPdfDocument
    doc = QPdfDocument(None)
    doc.load(str(pdf))
    return "\n".join(doc.getAllText(i).text() for i in range(doc.pageCount()))


def script_for(which):
    def script(d):
        rec = d.record
        rec["scenarios"] = {}

        def open_window(project, run, run_type="Verification"):
            d.open_project(project)
            d.set_bar(run_type=run_type, run=run)
            d.launch_tool("measurement_report")

        def tick(dlg, dates):
            """Tick exactly the rows whose text holds one of *dates*
            (``None`` ticks every row), as a user's clicks would."""
            from PyQt6.QtCore import Qt
            lst = dlg._profile_list
            for i in range(lst.count()):
                it = lst.item(i)
                if not (it.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                on = dates is None or any(x in it.text() for x in dates)
                it.setCheckState(Qt.CheckState.Checked if on
                                 else Qt.CheckState.Unchecked)
                d.pump(150)

        def generate(dlg, dates=None):
            dlg._saved_combo.setCurrentIndex(0)          # New report...
            d.pump(1200)
            tick(dlg, dates)
            d.pump(800)
            # QUEUED: a question Generate asks runs its own exec(), and the
            # next step answers it from inside that loop.
            d.later(dlg._generate_btn.click)
            yield 400
            d.answer("New", name=None, within_ms=2500)
            # WAIT FOR THE GRAPHS, not for a guess: they are redrawn from the
            # ticked dates when the page is.
            from PyQt6.QtCore import Qt
            lst = dlg._profile_list
            want = sum(1 for i in range(lst.count())
                       if lst.item(i).flags() & Qt.ItemFlag.ItemIsUserCheckable
                       and lst.item(i).checkState() == Qt.CheckState.Checked)
            for _ in range(90):
                yield 1000
                if len(getattr(dlg, "_trend_series", []) or []) == want:
                    break
            d.note(f"   generated: {want} dates ticked, "
                   f"{len(getattr(dlg, '_trend_series', []) or [])} in the "
                   f"trend series")
            yield 1500

        def state(dlg, tag, what):
            t = dlg._trend_tabs
            s = {"what": what, "tabs": tabs(dlg), "charts": {}}
            charts = [dlg._trend_de, dlg._trend_white, dlg._trend_black,
                      dlg._trend_corners] + list(dlg._trend_groups.values())
            for c in charts:
                i = t.indexOf(c)
                if t.isTabVisible(i):
                    t.setCurrentIndex(i)
                    d.pump(300)                 # painted, so hits are real
                    s["charts"][t.tabText(i)] = chart_info(c)
            t.setCurrentIndex(0)
            rec["scenarios"][tag] = s
            d.note(f"{tag}: {what}")
            d.note("   tabs: " + ", ".join(
                f"{n}{'' if v else ' [HIDDEN]'}" for n, v in s["tabs"]))
            for n, info in s["charts"].items():
                d.note(f"   [{n}] legend: {info['legend']}")
                for v, w, note in info["lines"]:
                    d.note(f"      line {w} at {v}: {note!r}")
                for x in info["red_x"]:
                    d.note(f"      RED X {x['date']} height {x['height']}: "
                           f"{x['tooltip']!r}")
                inside = [h for h in info["hits"] if h["rect"][0] >= 40.0
                          and not h["text"].startswith("20")]
                for h in inside:
                    d.note(f"      word INSIDE the plot at x={h['rect'][0]}"
                           f" (left end is 44): {h['text'][:40]!r}")
            return s

        def photograph(dlg, tag, only=None):
            t = dlg._trend_tabs
            for i in range(t.count()):
                if not t.isTabVisible(i):
                    continue
                name = t.tabText(i)
                if only and not any(o in name for o in only):
                    continue
                t.setCurrentIndex(i)
                safe = "".join(ch if ch.isalnum() else "-" for ch in name)
                d.shot(dlg, f"{tag}-{i:02d}-{safe.strip('-')}")
            t.setCurrentIndex(0)

        def hover(dlg, chart, match, tag):
            """Point at the first painted thing whose text starts with
            *match*, with the REAL pointer, and photograph the tooltip."""
            from PyQt6.QtCore import QPoint
            from PyQt6.QtWidgets import QApplication, QToolTip
            t = dlg._trend_tabs
            t.setCurrentIndex(t.indexOf(chart))
            d.pump(600)
            hit = next(((r, x) for r, x in chart._hits if x.startswith(match)),
                       None)
            if hit is None:
                d.note(f"   HOVER {tag}: nothing painted starts with {match!r}")
                return
            rect, text = hit
            g = chart.mapToGlobal(rect.center().toPoint())
            how = "real pointer (Quartz mouse-moved event)"
            try:
                import Quartz
                for dx in (-6, -3, 0):
                    pt = Quartz.CGPointMake(g.x() + dx, g.y())
                    Quartz.CGWarpMouseCursorPosition(pt)
                    ev = Quartz.CGEventCreateMouseEvent(
                        None, Quartz.kCGEventMouseMoved, pt,
                        Quartz.kCGMouseButtonLeft)
                    Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
                    d.pump(120)
            except Exception as exc:                        # noqa: BLE001
                how = f"no pointer ({exc}); "
            d.pump(1600)
            shown = QToolTip.text() if QToolTip.isVisible() else ""
            if not shown:
                # The pointer did not reach the window (another window over
                # it, or no events for a background process): ask the chart
                # the way Qt asks it, and SAY so.
                from PyQt6.QtCore import QEvent
                from PyQt6.QtGui import QHelpEvent
                lp = rect.center().toPoint()
                QApplication.sendEvent(chart, QHelpEvent(
                    QEvent.Type.ToolTip, lp, chart.mapToGlobal(lp)))
                d.pump(500)
                shown = QToolTip.text() if QToolTip.isVisible() else ""
                how += " -> fell back to a QHelpEvent at the same point"
            # PyQt wraps Qt's private QTipLabel as a plain QLabel: ask Qt.
            tip = next((w for w in QApplication.topLevelWidgets()
                        if w.metaObject().className() == "QTipLabel"
                        and w.isVisible()), None)
            try:
                ok = d.shot(tip, f"{tag}-tooltip-window") if tip else False
            except RuntimeError as exc:     # the tip closed while we waited
                ok = False
                d.note(f"   tooltip window closed before its photograph: {exc}")
            d.shot(dlg, f"{tag}-with-tooltip")
            import html as _html
            import re as _re
            shown = _html.unescape(_re.sub(r"<[^>]+>", "", shown))
            rec["scenarios"].setdefault("tooltips", []).append(
                {"tag": tag, "how": how, "expected": text, "shown": shown,
                 "match": shown == text, "tooltip_window_photographed": ok})
            d.note(f"   HOVER {tag} ({how}): shown={shown!r} "
                   f"match={shown == text}")
            QToolTip.hideText()
            # and on to the Save button, the way a user's pointer leaves the
            # graph to click it
            try:
                import Quartz
                b = dlg._pdf_btn.mapToGlobal(dlg._pdf_btn.rect().center())
                pt = Quartz.CGPointMake(b.x(), b.y())
                Quartz.CGWarpMouseCursorPosition(pt)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap,
                                   Quartz.CGEventCreateMouseEvent(
                                       None, Quartz.kCGEventMouseMoved, pt,
                                       Quartz.kCGMouseButtonLeft))
            except Exception:                               # noqa: BLE001
                pass
            d.pump(600)

        def save_pdf(dlg, name):
            target = d.out / "pdf" / f"{name}.pdf"
            target.parent.mkdir(parents=True, exist_ok=True)
            d.later(dlg._pdf_btn.click)
            yield 1500
            ok = d.answer_file(target, name=f"{name}-save-dialog")
            # WAIT FOR THE FILE ITSELF. The report window is modal, so "a
            # modal that is not the file dialog" is true at once, and the
            # first cut moved on and re-ticked the list while the export was
            # still being written: the PDF described the NEXT scenario.
            for _ in range(120):
                yield 1000
                if target.exists():
                    break
            yield 3000
            written = target.exists()
            d.note(f"   PDF {target.name}: "
                   f"{'written' if written else 'NOT WRITTEN'} (dialog ok={ok})")
            if written:
                pages_dir = d.out / "pdf-pages"
                pages_dir.mkdir(exist_ok=True)
                pages = render_pdf(target, pages_dir)
                txt = pdf_text(target)
                (pages_dir / f"{name}.txt").write_text(txt, encoding="utf-8")
                d.note(f"   PDF pages rendered: {pages}")
                rec["scenarios"].setdefault("pdfs", []).append(
                    {"pdf": str(target), "pages": pages})
            # the PDF viewer the app opens is not ours to close; the window
            # stays in front of it for the next photograph
            dlg.raise_()

        if which == "limits":
            open_window(LIMITS[1], "run10")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            yield from generate(dlg)
            yield 500
            state(dlg, "L1", "Every-Limit-Set run10, every date, Generate")
            photograph(dlg, "L1")
            hover(dlg, dlg._trend_de, "Max (", "L1-accuracy-Max")
            vis = [c for c in dlg._trend_groups.values()
                   if dlg._trend_tabs.isTabVisible(dlg._trend_tabs.indexOf(c))]
            if vis:
                w = vis[0]._lines()[0][1] if vis[0]._lines() else ""
                hover(dlg, vis[0], w + " (", "L1-judged-tab-" + w)
            yield from save_pdf(dlg, "L1-every-limit-set-run10")
            dlg.close()
            yield 1000

            open_window(LIMITS[0], "run1")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            yield from generate(dlg)
            yield 500
            state(dlg, "L2", "Threshold-Series run1, every date, Generate")
            photograph(dlg, "L2")
            yield from save_pdf(dlg, "L2-threshold-series-run1")
            dlg.close()
            yield 1000

        if which == "redx":
            open_window(REDX[0], "run1")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            yield from generate(dlg)
            yield 500
            state(dlg, "R1", "Red-X run1, all seven dates: A B noisy, C even, "
                  "D noisy, E drift, F one area, G noisy")
            photograph(dlg, "R1", only=("Evenness",))
            ev = dlg._trend_groups["evenness"]
            marks = ev.withheld_marks()
            # THE POINTER BEFORE ANY PDF: the PDF viewer the export opens sits
            # in front of the window afterwards, and a pointer over it gives
            # the chart no tooltip. And NO PDF right after the pointer: twice
            # the export was then not written until the drive had moved on to
            # other dates, so it described R5. R1's PDF is saved at the end,
            # from the same seven dates generated again.
            if marks:
                d_lab = ev._date_label(marks[-1][1])
                hover(dlg, ev, d_lab, "R1-red-x")
            yield from save_pdf(dlg, "R1-red-x-all-dates-after-hover")

            yield from generate(dlg, ["2026-11-09", "2026-11-23", "2026-11-30"])
            yield 500
            state(dlg, "R2", "only B (noisy), D (noisy), E (drift): B's only "
                  "neighbour D is withheld too, so B sits on the floor")
            photograph(dlg, "R2", only=("Evenness",))

            yield from generate(dlg, ["2026-11-09", "2026-11-16", "2026-11-23",
                           "2026-11-30"])
            yield 500
            state(dlg, "R3", "C (even) ticked as well: B now has a "
                  "neighbour with a point and moves up to C's height")
            photograph(dlg, "R3", only=("Evenness", "Repeatability"))

            yield from generate(dlg, ["2026-11-16"])
            yield 500
            state(dlg, "R5", "one date ticked (C): the graphs say a trend "
                  "needs at least two measurements")
            photograph(dlg, "R5", only=("Colour accuracy", "Evenness"))

            yield from generate(dlg)
            yield 500
            state(dlg, "R1b", "all seven dates again, for R1's PDF")
            yield from save_pdf(dlg, "R1-red-x-all-dates")
            dlg.close()
            yield 1000

            open_window(REDX[1], "run1")
            yield 5000
            dlg = d.top_dialog("MeasurementReportDialog")
            yield from generate(dlg)
            yield 500
            state(dlg, "R4", "Report-Limits-Evenness run1 as it ships: even, "
                  "drift, one area, noisy (the last date withheld)")
            photograph(dlg, "R4", only=("Evenness",))
            yield from save_pdf(dlg, "R4-evenness-demo-run1")
            dlg.close()
            yield 1000
        yield 500
    return script


if __name__ == "__main__":
    which = sys.argv[2] if len(sys.argv) > 2 else "limits"
    lang = sys.argv[3] if len(sys.argv) > 3 else "en"
    d = Drive(Path(sys.argv[1]),
              projects=list(REDX) if which == "redx" else list(LIMITS),
              language=lang)
    rc = d.run(script_for(which))
    print(json.dumps({k: v for k, v in d.record.get("scenarios", {}).items()
                      if k in ("tooltips", "pdfs")}, indent=1, default=str))
    sys.exit(rc)
