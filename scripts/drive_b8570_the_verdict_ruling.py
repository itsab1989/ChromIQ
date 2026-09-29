#!/usr/bin/env python3
"""B8-570 — Knut's verdict ruling, DRIVEN ON SCREEN in a real window.

Knut retired COND as a row word on 2026-09-21, took every should-limit out of
ChromIQ's own set definitions, and asked for a legend line and a per-metric
reference note in its place. The consequence he and Basti both named on the
issue is the reason this driver exists rather than a test:

    "after this, no bracket will appear anywhere by default … So I will drive
     it through a hand-marked should-limit in one of the editable Custom
     columns, which touches no real standard value, and show you that rather
     than a passing test."

So a green suite proves nothing about the note path. This photographs it.

WHAT IT PHOTOGRAPHS
  1. the Report limits window as it SHIPS: no bracket anywhere, the legend
     line, and the corrected columns paragraph (B8-571);
  2. the same window with ONE row hand-marked "should" in Custom ISO 12647-7,
     showing the bracket, the raised ⁴ on the metric's name, and the fourth
     note under the table;
  3. a Measurement Report whose verdict cell carries the note's number and
     whose note list carries the note (Knut's "in the report text also a
     number on the metric name, pointing to a note in the report text");
  4. B8-556: the painted BASELINES of all five read-only cell kinds against
     the spin boxes beside them, before and after, measured from the pixels
     rather than read off the alignment flag.

THE ISO VALUES FILE IS FORCED TO THE REPOSITORY'S OWN EMPTY ONE. This machine
carries a licence holder's real ISO 12647 figures at
~/Library/Preferences/ChromIQ/compliance/iso12647.json, which `_iso_data_path`
prefers over the shipped file. A driver that did not force this would
photograph populated ISO columns no user of a shipped ChromIQ has, and put a
paid standard's content into a proof folder.

Never sets QT_QPA_PLATFORM. It is a driver, not a test.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cond/settings.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-cond/presets \
        python scripts/drive_b8570_the_verdict_ruling.py <out-dir>
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
assert "QT_QPA_PLATFORM" not in os.environ, "a driver must not go offscreen"

# THE SHIPPED, EMPTY VALUES FILE -- see the module docstring.
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    ROOT / "data" / "compliance_sets" / "iso12647.json")

from PyQt6.QtGui import QImage                                   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QDoubleSpinBox,  # noqa: E402
                             QLabel, QMessageBox)
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
report: dict = {}


def pump(app, ms=400):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shoot(win, name: str) -> dict:
    """Two frames, and how far apart they are.

    THE WINDOW IS NOT WHOLLY STATIC AND SAYING SO IS BETTER THAN PRETENDING.
    A focused `QDoubleSpinBox` blinks a text caret, so two frames a third of a
    second apart can differ by a few pixels of one cell with nothing whatever
    having changed. An earlier version of this driver asserted pixel identity
    and got True or False depending on the phase of that blink, which is a coin
    toss reported as evidence.

    So both frames are kept when they differ, the fraction of differing pixels
    is measured, and the caller decides. Anything at or below a small fraction
    of one per cent is the caret; a real repaint moves far more than that.
    """
    a = OUT / f"{name}.png"
    b = OUT / f"{name}__again.png"
    ok1, why1 = capture_window(win, a)
    pump(QApplication.instance(), 350)
    ok2, why2 = capture_window(win, b)
    out = {"file": a.name, "ok": bool(ok1 and ok2)}
    if not ok1 or not ok2:
        out["why"] = why1 or why2
        return out
    ia, ib = QImage(str(a)), QImage(str(b))
    out["size"] = [ia.width(), ia.height()]
    if ia.size() != ib.size():
        out["two_frames_identical"] = False
        out["differing_pixels_pct"] = None
        return out
    ia = ia.convertToFormat(QImage.Format.Format_RGB32)
    ib = ib.convertToFormat(QImage.Format.Format_RGB32)
    same = ia == ib
    out["two_frames_identical"] = bool(same)
    if same:
        out["differing_pixels_pct"] = 0.0
        b.unlink(missing_ok=True)
        return out
    # COUNT THE BODY SEPARATELY FROM THE TITLE BAR, because on macOS they mean
    # completely different things and the whole-frame figure is misleading.
    #
    # MEASURED: every photograph this driver takes differs between its two
    # frames by about 2.6 % of the whole picture and by **0.000 % below the
    # title bar**. The difference is entirely macOS flipping the window's
    # ACTIVE-STATE rendering between the two captures: the traffic lights go
    # from coloured to grey and the title text dims. Nothing the app draws
    # moves. A driver that reported only the whole-frame number would keep
    # saying "the two frames are not identical" about a window that is
    # perfectly still, which is how a real repaint would come to be ignored.
    dy = int(round(frame_offset_dy(win, ia)))
    body_diff = body_total = whole = 0
    xs, ys = [], []
    for y in range(0, ia.height(), 2):
        for x in range(0, ia.width(), 2):
            same = ia.pixel(x, y) == ib.pixel(x, y)
            if not same:
                whole += 1
                xs.append(x); ys.append(y)
            if y >= dy:
                body_total += 1
                if not same:
                    body_diff += 1
    total = (ia.height() // 2 + 1) * (ia.width() // 2 + 1)
    out["differing_pixels_pct"] = round(100.0 * whole / max(1, total), 4)
    out["differing_pixels_pct_below_the_title_bar"] = round(
        100.0 * body_diff / max(1, body_total), 4)
    out["the_window_body_is_still"] = body_diff == 0
    if xs:
        out["differing_region"] = [min(xs), min(ys), max(xs), max(ys)]
    return out


def frame_offset_dy(win, img: QImage) -> float:
    """How far below the picture's top edge the window's CLIENT area starts."""
    fg, g = win.frameGeometry(), win.geometry()
    return (g.y() - fg.y()) * (img.width() / max(1, fg.width()))


# --------------------------------------------------------------- B8-556
def _ink_rows(img: QImage, x0: int, x1: int, y0: int, y1: int) -> "list[int]":
    """Which SCREEN rows of a band carry glyph ink, measured, not asserted.

    A cell's text colour and its ground differ; "ink" is any pixel far enough
    from the band's own most common colour. The band is a widget's rectangle
    in DEVICE pixels, which is what a photograph of a 2x window has.
    """
    from collections import Counter
    c = Counter()
    for y in range(y0, y1):
        for x in range(x0, x1):
            c[img.pixel(x, y) & 0xFFFFFF] += 1
    if not c:
        return []
    ground = c.most_common(1)[0][0]
    gr, gg, gb = (ground >> 16) & 255, (ground >> 8) & 255, ground & 255
    rows = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            p = img.pixel(x, y)
            r, g, b = (p >> 16) & 255, (p >> 8) & 255, p & 255
            if abs(r - gr) + abs(g - gg) + abs(b - gb) > 90:
                rows.append(y)
                break
    return rows


def frame_offset(dlg, img: QImage) -> "tuple[float, float, float]":
    """``(dx, dy, dpr)`` mapping a widget point in *dlg* coordinates to a pixel
    of *img*.

    THE PHOTOGRAPH HAS THE TITLE BAR IN IT AND THE FIRST CUT OF THIS DRIVER DID
    NOT. `capture_window` returns the window's own buffer through
    `CGWindowListCreateImage`, which is the FRAME: title bar included. A widget
    point is in CLIENT coordinates, so mapping it with nothing but the device
    ratio samples a band one row too high, silently, for every cell. That is
    what made a correctly placed "2,00" cell read as having no ink in it at
    all, and it is the same class of mistake as the viewport clamp before it:
    a measurement that is wrong in a way the numbers do not announce.

    `frameGeometry` minus `geometry` is the margin the picture carries.
    """
    fg, g = dlg.frameGeometry(), dlg.geometry()
    dpr = img.width() / max(1, fg.width())
    return ((g.x() - fg.x()) * dpr, (g.y() - fg.y()) * dpr, dpr)


def measure_cell_baselines(dlg, img: QImage, dpr: float) -> dict:
    """B8-556, measured as a PAIR per row: the label's ink against the spin
    box's ink, in the same row, in device pixels off the photograph.

    WHY PAIRED AND NOT ABSOLUTE. A first cut compared each cell's ink centre
    with the centre of its own rectangle and produced spreads of 27 px, which
    is not a measurement of anything: rows scrolled out of the viewport map to
    coordinates outside the picture, and clamping them silently sampled
    whatever was at the edge. The fault is "the label sits higher than the spin
    box BESIDE IT", so that is the comparison: two cells of one row, both
    wholly inside the scroll viewport, their ink centres subtracted.

    THE FLAG IS NEVER READ. Three guards on this project have asserted
    `alignment()` and been believed while the pixels said otherwise.
    """
    from workflow.compliance_sets import ROW_BY_ID
    dx, dy, dpr = frame_offset(dlg, img)
    vp = dlg._scroll.viewport()
    vtl = vp.mapTo(dlg, vp.rect().topLeft())
    vx0, vy0 = vtl.x(), vtl.y()
    vx1, vy1 = vx0 + vp.width(), vy0 + vp.height()

    def band(w):
        """A widget's ink band in DEVICE pixels, or None if not fully visible."""
        tl = w.mapTo(dlg, w.rect().topLeft())
        x0, y0 = tl.x(), tl.y()
        x1, y1 = x0 + w.width(), y0 + w.height()
        if x0 < vx0 or y0 < vy0 or x1 > vx1 or y1 > vy1:
            return None                       # scrolled out: not photographed
        px = lambda v: int(round(v * dpr + dx))
        py = lambda v: int(round(v * dpr + dy))
        if px(x1) > img.width() or py(y1) > img.height():
            return None
        ink = _ink_rows(img, px(x0), px(x1), py(y0), py(y1))
        if not ink:
            return None
        return {"top": ink[0], "bottom": ink[-1],
                "centre": (ink[0] + ink[-1]) / 2.0,
                "cell_top": py(y0), "cell_bottom": py(y1)}

    # group the cells by ROW, and note each one's kind
    by_row: dict = {}
    for (col, rid), w in dlg._cells.items():
        if not w.isVisible():
            continue
        lim = dlg._limits_of(col).get(rid)
        kind = "none" if lim is None else (
            "should" if lim.is_should else lim.kind)
        by_row.setdefault(rid, []).append((col, kind, w))

    pairs, per_kind = [], {}
    for rid, cells in by_row.items():
        spins = [(c, k, w) for c, k, w in cells
                 if isinstance(w, QDoubleSpinBox)]
        labels = [(c, k, w) for c, k, w in cells if isinstance(w, QLabel)]
        if not spins or not labels:
            continue
        sb = band(spins[0][2])
        if sb is None:
            continue
        for col, kind, w in labels:
            lb = band(w)
            if lb is None:
                continue
            pairs.append({
                "row": rid,
                "label": ROW_BY_ID[rid].label if rid in ROW_BY_ID else rid,
                "read_only_column": col,
                "kind": kind,
                "cell_text": w.text(),
                "spin_column": spins[0][0],
                # NEGATIVE = the read-only cell's ink sits HIGHER than the
                # spin box's, which is the fault B8-556 names.
                "label_minus_spin_px": round(lb["centre"] - sb["centre"], 1),
            })
            per_kind.setdefault(kind, []).append(lb["centre"] - sb["centre"])

    summary = {}
    for k, v in per_kind.items():
        summary[k] = {"n": len(v), "min": round(min(v), 1),
                      "max": round(max(v), 1),
                      "mean": round(sum(v) / len(v), 1)}
    worst = max((abs(p["label_minus_spin_px"]) for p in pairs), default=0.0)

    # AND AN ABSOLUTE MEASUREMENT BESIDE IT, because two of the five cell kinds
    # cannot be paired: an `unmeasurable` row (✕) has no spin box anywhere in
    # it, every column being read-only there. This is the ink centre against
    # the cell's OWN rectangle centre, which is meaningful now that the band is
    # clipped to the viewport rather than clamped to the picture's edge.
    absolute: dict = {}
    for rid, cells in by_row.items():
        for col, kind, w in cells:
            b = band(w)
            if b is None:
                continue
            off = b["centre"] - (b["cell_top"] + b["cell_bottom"]) / 2.0
            absolute.setdefault(
                kind + "/" + ("spin" if isinstance(w, QDoubleSpinBox)
                              else "label"), []).append(round(off, 1))
    abs_summary = {k: {"n": len(v), "min": min(v), "max": max(v),
                       "mean": round(sum(v) / len(v), 1)}
                   for k, v in absolute.items()}
    return {"pairs_measured": len(pairs),
            "worst_abs_offset_px": round(worst, 1),
            "by_kind": summary,
            "absolute_ink_offset_by_kind": abs_summary,
            "device_pixel_ratio": dpr,
            "pairs": sorted(pairs, key=lambda p: -abs(p["label_minus_spin_px"]))}


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    from ui.theme import apply_appearance
    from workflow import compliance_sets as cs

    settings = AppSettings()
    import tempfile
    work = tempfile.mkdtemp(prefix="chromiq-b8570-")
    settings.set("custom_output_path", work)
    settings.set("appearance", "light")
    assert settings.get("custom_output_path", "") == work, "SANDBOX FAILED"
    apply_appearance(app, None, "light")

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    report["locked_at_start"] = session_is_locked()
    report["iso_file_forced"] = os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"]
    report["iso_file_in_use"] = str(cs._iso_data_path())
    report["iso_file_is_the_users_own"] = cs._is_the_users_own_file()
    report["judged_rows_per_set"] = {
        sid: len(cs.limit_bearing(cs.factory_limits(sid)))
        for sid in cs.SET_IDS}
    report["should_rows_per_set_as_shipped"] = {
        sid: sorted(r for r, l in cs.factory_limits(sid).items() if l.is_should)
        for sid in cs.SET_IDS}

    from ui.dialogs import thresholds_dialog as td

    # ---------------------------------------------------------- 1. as it ships
    dlg = td.ThresholdsDialog(settings, None)
    dlg.setWindowTitle("B8-570 — Report limits, as shipped")
    dlg.resize(1500, 980)
    dlg.show()
    pump(app, 1200)
    dlg.setFocus()            # off the spin boxes: a focused one blinks a caret
    pump(app, 400)
    print(f"ON SCREEN: visible={dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
          flush=True)
    report["shipped"] = {
        "photo": shoot(dlg, "01-limits-as-shipped"),
        "legend_and_notes": dlg._notes_text(),
        "columns_paragraph": td._columns_paragraph(),
        "any_row_marked_recommended": dlg._any_row_is_recommended(),
        "labels_carrying_a_marker": [
            rid for rid, lab in dlg._row_labels.items()
            if td.ThresholdsDialog.RECOMMENDED_MARK in lab.text()],
        "cells_drawn_with_a_bracket": [
            f"{c}/{r}" for (c, r), w in dlg._cells.items()
            if isinstance(w, QLabel) and w.text().startswith("(")
            or isinstance(w, QDoubleSpinBox) and w.prefix() == "("],
    }

    # -- B8-556, BEFORE the fix is visible: photograph and measure baselines
    img = QImage(str(OUT / "01-limits-as-shipped.png"))
    dx, dy, dpr = frame_offset(dlg, img)
    report["photo_mapping"] = {
        "device_pixel_ratio": round(dpr, 3),
        "frame_offset_px": [round(dx, 1), round(dy, 1)],
        "note": "the picture is the window FRAME; dy is the title bar",
    }
    report["shipped"]["cell_baselines"] = measure_cell_baselines(dlg, img, dpr)

    # ------------------------------------------- 2. a hand-marked should-limit
    #
    # THE ONE SOURCE OF A SHOULD-LIMIT THAT IS LEFT. Knut's point 5 took the
    # last one out of ChromIQ's own sets, so this is exactly the route Basti
    # described to him: a row marked "should" in an editable Custom column,
    # which touches no real standard value. It is written the way a licence
    # holder's file writes one -- `[number, "should"]` -- through the same
    # loader, so the path photographed is the shipping path and not a fixture.
    marked = Path(work) / "iso12647-hand-marked.json"
    _MARKED_ROWS = {
        # one RECOMMENDATION, for the note path …
        "grey_balance_neutral_ramp_max": [3.0, "should"],
        # … and one ORDINARY number, so that a read-only cell of kind "value"
        # exists on screen for B8-556 to measure. Both are ChromIQ default's
        # own figures; neither is from any standard.
        "control_strip_de00_avg": 2.0,
    }
    marked.write_text(json.dumps({
        "_readme": "B8-570 DRIVER FIXTURE. Not a standard's values: both "
                   "numbers are ChromIQ default's own, written here only so "
                   "the note path and the five cell kinds can be shown.",
        "iso_12647_7": _MARKED_ROWS,
        "iso_12647_8": {},
    }), encoding="utf-8")
    os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(marked)
    cs.reset_iso_cache()
    report["hand_marked_file"] = marked.name
    report["hand_marked_limit"] = {
        sid: str(cs.factory_limits(sid).get("grey_balance_neutral_ramp_max"))
        for sid in ("iso_12647_7", "custom_iso_12647_7", "chromiq_default")}

    dlg.close()
    pump(app, 300)
    dlg2 = td.ThresholdsDialog(AppSettings(), None)
    dlg2.setWindowTitle("B8-570 — a hand-marked recommendation")
    dlg2.resize(1500, 980)
    dlg2.show()
    pump(app, 1200)
    dlg2.setFocus()
    pump(app, 400)
    report["hand_marked"] = {
        "photo": shoot(dlg2, "02-limits-hand-marked-should"),
        "legend_and_notes": dlg2._notes_text(),
        "any_row_marked_recommended": dlg2._any_row_is_recommended(),
        "labels_carrying_a_marker": [
            rid for rid, lab in dlg2._row_labels.items()
            if td.ThresholdsDialog.RECOMMENDED_MARK in lab.text()],
        "the_marked_label_reads": next(
            (lab.text() for rid, lab in dlg2._row_labels.items()
             if rid == "grey_balance_neutral_ramp_max"), "?"),
        "cells_drawn_with_a_bracket": sorted(
            f"{c}/{r}" for (c, r), w in dlg2._cells.items()
            if (isinstance(w, QLabel) and w.text().startswith("("))
            or (isinstance(w, QDoubleSpinBox) and w.prefix() == "(")),
        "tooltip_of_the_marked_label": next(
            (lab.toolTip() for rid, lab in dlg2._row_labels.items()
             if rid == "grey_balance_neutral_ramp_max"), "?"),
    }
    img2 = QImage(str(OUT / "02-limits-hand-marked-should.png"))
    report["hand_marked"]["cell_baselines"] = measure_cell_baselines(
        dlg2, img2, dpr)
    # A NAMED SPOT CHECK ON THE FIFTH KIND, so "not measured" can be explained
    # rather than shrugged at.
    spot = {}
    for key in (("iso_12647_7", "control_strip_de00_avg"),
                ("iso_12647_7", "grey_balance_neutral_ramp_max")):
        w = dlg2._cells.get(key)
        if w is None:
            spot["/".join(key)] = "no such cell"
            continue
        tl = w.mapTo(dlg2, w.rect().topLeft())
        vp = dlg2._scroll.viewport()
        vtl = vp.mapTo(dlg2, vp.rect().topLeft())
        spot["/".join(key)] = {
            "type": type(w).__name__,
            "text": getattr(w, "text", lambda: "")(),
            "visible": w.isVisible(),
            "rect": [tl.x(), tl.y(), tl.x() + w.width(), tl.y() + w.height()],
            "viewport": [vtl.x(), vtl.y(), vtl.x() + vp.width(),
                         vtl.y() + vp.height()],
            "kind": str(dlg2._limits_of(key[0]).get(key[1])),
        }
    report["hand_marked"]["spot_check"] = spot

    # ------------------------------- the FIFTH cell kind, which needs a scroll
    #
    # B8-556 asks about all five read-only cell kinds and four of them are in
    # the first screenful: "–", "?", "✕" and a bracketed value. A read-only
    # PLAIN NUMBER only exists in a read-only ISO column that has one, and the
    # row the fixture gives a number to (`all_de00_max`) sits below the fold.
    # A cell outside the viewport is not in the photograph, and measuring it
    # anyway is exactly the mistake the first cut of this driver made.
    # So the window is scrolled to it and photographed again.
    bar = dlg2._scroll.verticalScrollBar()
    target = dlg2._cells.get(("iso_12647_7", "control_strip_de00_avg"))
    if target is not None:
        y = target.mapTo(dlg2._scroll.widget(), target.rect().topLeft()).y()
        # PUT IT 120 px BELOW THE TOP EDGE, not at the centre: centring a row
        # that is already near the top clamps the bar to 0 and moves nothing,
        # which left this very row clipped by the viewport edge and unmeasured.
        bar.setValue(max(0, min(bar.maximum(), y - 120)))
        pump(app, 1800)          # the edge fades animate; let them settle
        shot = shoot(dlg2, "03-limits-scrolled-to-a-read-only-number")
        img3 = QImage(str(OUT / "03-limits-scrolled-to-a-read-only-number.png"))
        report["scrolled"] = {
            "photo": shot,
            "the_read_only_number_reads": target.text(),
            "cell_baselines": measure_cell_baselines(dlg2, img3, dpr),
        }

    # ------------------------------------------------- 3. the same in a REPORT
    from workflow import measurement_report as mr
    from workflow.measurement_report import (note_label, note_numbers_for,
                                             numbered_notes)
    # A REAL REPORT OFF A REAL .ti3, not a hand-built dict: `judge` reads what
    # `build_report` writes, and a fixture shaped by hand would prove that the
    # fixture agrees with the code rather than that the code works.
    lim = cs.factory_limits("custom_iso_12647_7")
    sys.path.insert(0, str(ROOT / "tests"))
    from test_report_judging import _colours, _ramp, _write_ti3
    # A 5.0 a* cast on step 8 of an 16-step ramp: the same measurement the
    # judging tests use, which puts the grey MAXIMUM over 3.0 and leaves the
    # average under it -- so one marked row FAILS and everything else passes.
    ti3 = _write_ti3(Path(work) / "b8570.ti3",
                     _ramp(16) + _colours(), cast={8: (5.0, 0.0)})
    rep = mr.build_report(ti3)
    rows = mr.judge(rep, lim)
    marked_rows = [r for r in rows
                   if mr.NOTE_RECOMMENDED_LIMIT in (r.get("notes") or ())]
    nums = numbered_notes(rows)
    report["report_text"] = {
        "rows_judged": len(rows),
        "rows_carrying_the_note": [r["row_id"] for r in marked_rows],
        "note_numbering": [[n, c, rs] for (n, c, rs) in nums],
        "markers_on_the_marked_row": [
            note_label(n) for n in note_numbers_for(marked_rows[0], nums)
        ] if marked_rows else [],
        "word_on_the_marked_row": (marked_rows[0]["word"]
                                   if marked_rows else None),
    }

    report["the_note_text"] = td._recommended_note_text()

    # ------------------------------------------- 4. the REAL report window
    #
    # Knut asked for the note "in the report text also", so the report is
    # opened for real rather than rendered to a string. No demo pack and no
    # ArgyllCMS: a Project with one run and one dated verification carrying the
    # measurement built above is all the report needs, and it is the same
    # `MeasurementReportDialog` the app opens.
    dlg2.close()
    pump(app, 400)
    from core.file_manager import FileManager, Project
    from workflow import run_compliance as rc

    proj_dir = Path(work) / "B8-570-Recommended-Metric"
    proj = Project.create(proj_dir, "B8-570-Recommended-Metric")
    prun = proj.current_run()
    prun.ensure_dir()
    # bound to the column that carries the hand-marked recommendation
    rc.bind_run(prun, "custom_iso_12647_7", {})
    ver = prun.new_verification()
    ver.ensure_dir()
    ver.measurement_ti3.write_text(Path(ti3).read_text(encoding="utf-8"),
                                   encoding="utf-8")
    settings.set("custom_output_path", str(work))
    fm = FileManager(settings)
    fm.set_target_name(proj_dir.name)

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    rep_dlg = MeasurementReportDialog(settings, None,
                                      initial_ti3=ver.measurement_ti3)
    rep_dlg.setWindowTitle("B8-570 — the note in the report text")
    rep_dlg.resize(1500, 1000)
    rep_dlg.show()
    rep_dlg.setFocus()
    pump(app, 2500)
    print(f"REPORT ON SCREEN: visible={rep_dlg.isVisible()} "
          f"{rep_dlg.frameGeometry().width()}x{rep_dlg.frameGeometry().height()}",
          flush=True)

    # GENERATE THE REPORT FIRST. The window opens on a preview that says "No
    # report has been generated yet"; the verdict grid and the numbered notes
    # only exist in a generated document, so photographing before pressing this
    # is photographing the wrong page. Pressed, not called: the button is what
    # a user has.
    entry0: dict = {}
    entry0["generate_enabled"] = rep_dlg._generate_btn.isEnabled()
    if rep_dlg._generate_btn.isEnabled():
        rep_dlg._generate_btn.click()
        pump(app, 3000)
    entry0["report_shown"] = rep_dlg._report_combo.currentText() \
        if hasattr(rep_dlg, "_report_combo") else "?"

    # SCROLL THE DOCUMENT TO THE THING BEING PHOTOGRAPHED. The report opens at
    # its own top, which is a paragraph about scope; the verdict grid and the
    # numbered notes under it are several screens down, and a photograph of the
    # wrong part of a document is not evidence about the right part.
    entry: dict = dict(entry0)
    from PyQt6.QtGui import QTextCursor, QTextDocument
    view = rep_dlg._view
    # AIM AT THE ROW, NOT AT THE SECTION. The document viewport in this window
    # is about 230 px tall, so "scroll to the Notes heading and back off" lands
    # wherever the clamp puts it. The grey row carrying the marker is what this
    # photograph is of, so that is what is searched for: its FIRST occurrence
    # is the verdict grid.
    view.moveCursor(QTextCursor.MoveOperation.Start)
    # PAST THE GUIDE FIRST. "Grey balance of the grey ramp, largest" also
    # appears in the "How to read this report" section above the grid, and
    # searching from the top lands there.
    view.find("Report Results", QTextDocument.FindFlag(0))
    found = view.find("Grey balance of the grey ramp, largest",
                      QTextDocument.FindFlag(0))
    entry["scrolled_to_the_notes"] = bool(found)
    if found:
        bar = view.verticalScrollBar()
        bar.setValue(min(bar.maximum(), max(0, bar.value() - 60)))
    # drop the selection highlight, or the photograph shows a blue bar
    cur = view.textCursor()
    cur.clearSelection()
    view.setTextCursor(cur)
    pump(app, 1200)
    entry["photo"] = shoot(rep_dlg, "04-report-verdict-grid")
    # …AND THE NOTE LIST ITSELF, which begins where that photograph ends. Two
    # pictures because the grid and its notes do not fit one screenful, and a
    # crop of one is not evidence of the other.
    bar = view.verticalScrollBar()
    view.moveCursor(QTextCursor.MoveOperation.Start)
    entry["found_the_note_list"] = bool(
        view.find("Notes on the verdicts above", QTextDocument.FindFlag(0)))
    bar.setValue(min(bar.maximum(), max(0, bar.value() + 120)))
    cur2 = view.textCursor(); cur2.clearSelection(); view.setTextCursor(cur2)
    pump(app, 1200)
    entry["photo_notes"] = shoot(rep_dlg, "05-report-the-numbered-notes")
    runs_shown = rep_dlg._runs_for_report()
    entry["runs_in_the_report"] = len(runs_shown)
    if runs_shown:
        vrows, _rec = rep_dlg._verdict_rows(runs_shown[0])
        marked = [r for r in vrows
                  if mr.NOTE_RECOMMENDED_LIMIT in (r.get("notes") or ())]
        entry["rows_carrying_the_note"] = [r["row_id"] for r in marked]
        entry["word_on_those_rows"] = [r["word"] for r in marked]
        entry["numbered_notes_in_the_window"] = [
            [n, where, sentence[:90]]
            for (n, where, sentence) in rep_dlg._numbered_notes(runs_shown)]
        html_ = rep_dlg._report_results_html(runs_shown)
        # the MARKER beside the verdict, and the ITEM under the table
        entry["marker_appears_in_the_table_html"] = (
            "<sup" in html_ and "2)" in html_)
        entry["note_sentence_in_the_html"] = (
            "recommended rather than required" in html_
            or "recommended rather than required"
            in "".join(x[2] for x in rep_dlg._numbered_notes(runs_shown)))
    report["report_window"] = entry
    rep_dlg.close()
    pump(app, 300)
    (OUT / "driver-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
