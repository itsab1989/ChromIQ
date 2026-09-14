#!/usr/bin/env python3
"""Knut's three bottom-text alignments, driven in the REAL Create Chart tab.

Knut, 2026-09-14, first asking for left-alignment and then, the same hour, for
all three with a control to pick between them::

    1. Left margin (default): this is the new option mentioned above, where any
       of the two bottom text types are left adjusted against the left margin.
    2. Centre of available space: This is the alignment type already in the
       design on beta 13.
    3. Centre between left and right margin: This type is new, where the centre
       alignment is set between the patch area left margin and right margin.

    Leave side-limit detection as it is designed. […] Please make this change.
    Test it thoroughly, that all alignment options result in the correct
    behaviour on screen, tested on presets for each instrument type.

So this walks **one engine preset per instrument group** in the built-in
dropdown, and for each of them sets the new "Alignment" pulldown through all
three options and measures **where the ink actually lands**, once for the
custom Sheet text and once for the layout stamp, each with the other switched
off so exactly one line is drawn.

Every claim is checked against the rule it is supposed to follow, computed from
`text_edge_fit` on the geometry the sheet is really laid out with:

* Left margin        -> the ink starts at `bottom_text_anchor_mm`;
* Centre of available space -> the ink is centred on the midpoint of
  `bottom_text_bounds_mm`;
* Centre between margins    -> the ink is centred on `bottom_text_centre_mm`.

**THE INK, NOT THE PREDICTION.** Asking the panel for its prediction and then
asking a second function whether the prediction is right is the panel agreeing
with itself; a prediction can only be checked against a rendered page.

**THE GEOMETRY IS PINNED AND SO IS THE SEED.** The off-pass keeps `chart_text`
at a single SPACE (truthy, so `nlines` stays 1 and a space draws nothing), and
both renders share a fixed seed. The first run of this driver skipped the seed
and reported the text starting at 15.49 mm at every margin, which was the top
of the patch block: the two renders had different patch colours and the diff
was the whole chart.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-align.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-align-presets \\
        python scripts/drive_182_bottom_text_alignment.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

#: Asymmetric on purpose. With equal margins the patch area's midpoint and the
#: midpoint of the two side bounds coincide, so options 2 and 3 land in the
#: same place and a run that only used the default margins would report both
#: as correct whatever the code did.
LEFT_MM, RIGHT_MM = 25.0, 8.0
TEXT = "Canon PRO-300 / Photo Rag 308 / no colour management"
SEED = 123456789


def reveal(app, w) -> str:
    """Bring *w* into view so a photograph can show it, and say what was done.

    **A COLLAPSED GROUP CANNOT BE SCROLLED TO.** `ensureWidgetVisible` moves a
    scroll area to a widget that has a size; a widget inside a collapsed
    `ui.widgets.CollapsibleGroupBox` has none, and the call is a no-op. Four
    photographs in a row on 2026-09-13 were of the wrong part of the window for
    exactly that reason, and a fifth guessed `setExpanded` where the API is
    `set_collapsed`.
    """
    from PyQt6.QtWidgets import QScrollArea
    steps = []
    node = w
    while node is not None:
        if hasattr(node, "set_collapsed"):
            try:
                if node.is_collapsed() if hasattr(node, "is_collapsed") else True:
                    node.set_collapsed(False)
                    steps.append(f"expanded {type(node).__name__}")
            except Exception as exc:                          # noqa: BLE001
                steps.append(f"could not expand {type(node).__name__}: {exc}")
        node = node.parentWidget()
    pump(app, 500)
    node, area = w, None
    while node is not None:
        if isinstance(node, QScrollArea):
            area = node
            break
        node = node.parentWidget()
    if area is not None:
        area.ensureWidgetVisible(w, 40, 120)
        steps.append("scrolled")
    pump(app, 700)
    steps.append("visible" if w.visibleRegion().boundingRect().height() > 0
                 else "STILL NOT VISIBLE")
    return ", ".join(steps)


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def line_ink_mm(recipe, ti1: Path, tag: str, *, which: str) -> "dict | None":
    """Where ONE bottom line's ink lands, in mm from the left page edge.

    *which* is "text" (the custom Sheet text, stamp off) or "stamp" (the layout
    summary, Sheet text empty). Exactly one line is drawn in both renders of
    each pair, so `nlines` is 1 throughout and nothing but that line moves.
    """
    from dataclasses import replace

    import numpy as np
    from PIL import Image

    from workflow.layout_engine.chart import build_from_recipe

    def _render(r, suffix):
        base = Path(tempfile.mkdtemp(prefix=f"align-{tag}-{suffix}-"))
        res, used = build_from_recipe(str(ti1), str(base / "s"), r)
        page = sorted(base.glob("s*.tif"))[0]
        return np.asarray(Image.open(page).convert("L")).astype(np.int16), res, used

    base_r = replace(recipe, randomize=True, seed_fixed=True, seed=SEED)
    if which == "text":
        on_r = replace(base_r, stamp_command=False, chart_text=TEXT)
    else:
        on_r = replace(base_r, stamp_command=True, chart_text="")
    off_r = replace(base_r, stamp_command=False, chart_text=" ")
    on, res, used = _render(on_r, "on")
    off, _r2, _u2 = _render(off_r, "off")
    if on.shape != off.shape:
        return {"error": "the geometry moved between the two renders"}
    diff = np.abs(on - off) > 30
    cols = np.where(diff.any(axis=0))[0]
    rows = np.where(diff.any(axis=1))[0]
    if cols.size == 0:
        return None
    dpi = float(getattr(recipe, "dpi", 300) or 300)
    mm = lambda px: round(float(px) * 25.4 / dpi, 2)            # noqa: E731
    return {"ink_left_mm": mm(int(cols[0])),
            "ink_right_mm": mm(int(cols[-1]) + 1),
            "ink_width_mm": mm(int(cols[-1]) + 1 - int(cols[0])),
            "ink_top_mm": mm(int(rows[0])),
            "paper_w_mm": mm(on.shape[1]),
            "patches": res.layout.total_patches, "seed": used.seed}


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-align-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    from ui.theme import apply_appearance
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments, papers, raster
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)
    combo = tab._preset_combo
    panel = tab._manual_layout_panel

    rows: list = []
    photos: list = []
    for gi, (instr, entries) in enumerate(BUILTIN_PRESET_GROUPS, 1):
        # ONE ENGINE PRESET PER INSTRUMENT GROUP. Some entries in a group are
        # printtarg presets, where none of this furniture exists at all
        # (`_engine_text_notes` returns at its first line), so the first entry
        # that actually switches the engine on is the one to drive.
        pick = None
        for n, (label, _o, key) in enumerate(entries, 1):
            if combo.findData(key) < 0:
                continue
            if tab._manual_target_name_edit is not None:
                tab._manual_target_name_edit.setText(f"Align{gi}x{n}")
            pump(app, 150)
            combo.setCurrentIndex(combo.findData(key))
            combo.activated.emit(combo.findData(key))
            pump(app, 1100)
            if bool(settings.get("use_chromiq_layout_engine", False)):
                pick = (label, key)
                break
        if pick is None:
            print(f"    {instr}: no engine preset in the dropdown, skipped",
                  flush=True)
            rows.append({"instrument": instr, "skipped": "no engine preset"})
            continue
        ti1_path = None
        for _attr in ("_preset_ti1_path", "_builtin_ti1_path"):
            _v = getattr(tab, _attr, None)
            if _v and Path(_v).is_file():
                ti1_path = Path(_v)
                break
        if ti1_path is None:
            _ti2 = getattr(tab, "_margin_ti2", None)
            _cand = Path(str(_ti2)).with_suffix(".ti1") if _ti2 else None
            if _cand is not None and _cand.is_file():
                ti1_path = _cand
        if ti1_path is None:
            print(f"    {instr}: no .ti1 to render from, skipped", flush=True)
            rows.append({"instrument": instr, "skipped": "no ti1"})
            continue
        for _ in range(300):
            pump(app, 120)
            if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
                break
        pump(app, 600)
        # TYPED MARGINS, or the instrument's own minimums overwrite them, and
        # the two centres would coincide again.
        if panel.use_instr_margins.isChecked():
            panel.use_instr_margins.setChecked(False)
            pump(app, 400)
        panel.margins["l"].setValue(LEFT_MM)
        panel.margins["r"].setValue(RIGHT_MM)
        pump(app, 500)
        print(f"    {instr}: {pick[0][:60]}", flush=True)

        for align in tef.BOTTOM_TEXT_ALIGNMENTS:
            # THE WIDGET THE PERSON TOUCHES, not `set_recipe`, which is the app
            # filling the panel and deliberately skips the refresh a real
            # gesture causes.
            _i = panel.chart_text_align.findData(align)
            assert _i >= 0, f"no {align!r} row in the Alignment pulldown"
            panel.chart_text_align.setCurrentIndex(_i)
            panel.chart_text.setText(TEXT)
            panel.stamp_command.setChecked(True)
            pump(app, 700)
            tab._update_margin_inspector()
            pump(app, 700)
            r = panel.get_recipe()
            assert str(r.chart_text_align) == align, (
                f"the panel says {r.chart_text_align!r}, the pulldown says "
                f"{align!r}")
            kw = r.build_kwargs()
            geom = raster.apply_furniture_reserves(
                instruments.geom_from_build_kwargs(kw), kw)
            pw = float(papers.dimensions_mm(r.paper)[0])
            common = dict(clip_border_mm=(float(geom.lbord + geom.border)
                                          if geom.lbord > 0 else 0.0),
                          clip_side=str(getattr(geom, "clip_side", "left")
                                        or "left"),
                          margin_left_mm=float(geom.margin_l or 0.0),
                          margin_right_mm=float(geom.margin_r or 0.0))
            edge = float(getattr(geom, "text_edge_clip_mm", 0.0) or 0.0)
            pos = (pw, edge, bool(r.helper_markers),
                   float(r.helper_marker_edge_mm or 0.0),
                   float(r.helper_marker_len_mm or 0.0),
                   bool(getattr(r, "helper_markers_sides", True)))
            lo, hi = tef.bottom_text_bounds_mm(*pos, **common)
            anchor = tef.bottom_text_anchor_mm(*pos, **common)
            centre = tef.bottom_text_centre_mm(
                pw, float(geom.margin_l or 0.0), float(geom.margin_r or 0.0))
            tag = f"{gi}-{align}"
            ink_text = line_ink_mm(r, ti1_path, tag + "-t", which="text")
            ink_stamp = line_ink_mm(r, ti1_path, tag + "-s", which="stamp")
            said = [m for m in TabChart._engine_text_notes(tab)[1]
                    if "along the bottom is too wide" in m]
            row = {
                "instrument": instr, "preset": pick[0], "align": align,
                "paper": r.paper, "paper_w_mm": round(pw, 2),
                "geom_margin_l_mm": round(float(geom.margin_l or 0.0), 2),
                "geom_margin_r_mm": round(float(geom.margin_r or 0.0), 2),
                "bound_left_mm": round(lo, 2), "bound_right_mm": round(hi, 2),
                "anchor_mm": round(anchor, 2),
                "bounds_centre_mm": round((lo + hi) / 2.0, 2),
                "patch_centre_mm": round(centre, 2),
                "text_ink": ink_text, "stamp_ink": ink_stamp,
                "panel_said": said,
            }
            for key, ink in (("text", ink_text), ("stamp", ink_stamp)):
                if not (ink and "ink_left_mm" in ink):
                    row[f"{key}_follows_the_rule"] = None
                    continue
                mid = (ink["ink_left_mm"] + ink["ink_right_mm"]) / 2.0
                w = ink["ink_width_mm"]
                # A LINE THE PAPER CUT OFF CANNOT BE MEASURED FOR WIDTH, and
                # its rule is a different one: an over-long line is anchored at
                # the left bound rather than centred out over both. On the
                # i1Pro 100x150 mm preset the layout stamp really is longer
                # than the 71 mm the sheet has, the panel warns about it, and
                # the first run of this driver read the clamp as a fault.
                clipped = ink["ink_right_mm"] >= ink["paper_w_mm"] - 0.3
                row[f"{key}_clipped_by_the_paper"] = bool(clipped)
                # LONGHAND, from the MEASURED width, so this is not
                # `bottom_text_start_mm` being asked to check itself.
                if align == tef.BOTTOM_TEXT_LEFT_MARGIN:
                    want = anchor
                elif align == tef.BOTTOM_TEXT_CENTRE_AVAILABLE:
                    want = lo if clipped else max(lo, (lo + hi) / 2.0 - w / 2.0)
                else:
                    want = lo if clipped else max(lo, centre - w / 2.0)
                ok = abs(ink["ink_left_mm"] - want) < 1.0
                row[f"{key}_follows_the_rule"] = bool(ok)
                row[f"{key}_expected_start_mm"] = round(want, 2)
                row[f"{key}_mid_mm"] = round(mid, 2)
                # A LINE THAT CLAMPS CANNOT SHOW ITS ALIGNMENT. Both centred
                # options put an over-long line at the left bound, so on a
                # sheet where the line fills its room they land in the same
                # place. That is the clamp doing its job, and the verdict below
                # has to know the difference between that and an option that
                # does nothing.
                row[f"{key}_clamped_at_the_bound"] = bool(
                    align != tef.BOTTOM_TEXT_LEFT_MARGIN
                    and ink["ink_left_mm"] <= lo + 0.6)
                # …and it never begins inside a side limit, whichever it is.
                row[f"{key}_clears_the_left_bound"] = bool(
                    ink["ink_left_mm"] >= lo - 0.6)
            rows.append(row)
            print(f"      {align:<16} bounds=({lo:.2f},{hi:.2f}) "
                  f"anchor={anchor:.2f} patch_centre={centre:.2f} "
                  f"text@{(ink_text or {}).get('ink_left_mm')} "
                  f"mid={row.get('text_mid_mm')} "
                  f"ok={row.get('text_follows_the_rule')}/"
                  f"{row.get('stamp_follows_the_rule')} warn={len(said)}",
                  flush=True)

        # ONE PHOTOGRAPH PER INSTRUMENT, with the pulldown ACTUALLY on screen.
        how = reveal(app, panel.chart_text_align)
        print(f"      reveal: {how}", flush=True)
        shot = out / f"{gi:02d}-{instr.split(' /')[0].replace(' ', '-')}.png"
        ok, why = capture_window(win, shot)
        photos.append(shot.name if ok else f"REFUSED: {why}")
        print(f"      photo: {'ok' if ok else 'REFUSED: ' + str(why)}",
              flush=True)

    real = [r for r in rows if "align" in r]
    verdicts = {
        "every instrument group was driven": not [r for r in rows
                                                  if r.get("skipped")],
        "all three alignments were driven on each": len(real) == 3 * len(
            {r["instrument"] for r in real}),
        "every line follows the rule its alignment names": all(
            r.get("text_follows_the_rule") and r.get("stamp_follows_the_rule")
            for r in real),
        # Only where BOTH lines fit: two lines of different lengths share a
        # left edge on the left-margin alignment and on an over-long clamp, and
        # deliberately do not on a centred one, where each is centred on its
        # own (that is what "text can equally expand to both sides" asks for).
        "the two lines share a left edge when left-aligned": all(
            abs((r["text_ink"] or {}).get("ink_left_mm", -1)
                - (r["stamp_ink"] or {}).get("ink_left_mm", -2)) < 0.6
            for r in real
            if r["align"] == "left_margin"
            and r.get("text_ink") and r.get("stamp_ink")),
        "no line begins inside a side limit": all(
            r.get("text_clears_the_left_bound")
            and r.get("stamp_clears_the_left_bound") for r in real),
        # …on the sheets where all three CAN differ. Where a centred line is
        # wide enough to clamp at the left bound it lands in the same place
        # under both centred options, and that is the clamp doing its job
        # rather than an option being inert.
        "the three alignments are not the same placement": all(
            len({round((r["text_ink"] or {}).get("ink_left_mm", 0), 1)
                 for r in real if r["instrument"] == instr}) == 3
            for instr in {r["instrument"] for r in real}
            - {r["instrument"] for r in real
               if r.get("text_clamped_at_the_bound")
               or r.get("text_clipped_by_the_paper")}),
        "a sheet with room shows three different placements": bool(
            {r["instrument"] for r in real} - {
                r["instrument"] for r in real
                if r.get("text_clamped_at_the_bound")
                or r.get("text_clipped_by_the_paper")}),
    }
    (out / "bottom-text-alignment.json").write_text(
        json.dumps({"left_margin_mm": LEFT_MM, "right_margin_mm": RIGHT_MM,
                    "photos": photos, "rows": rows, "verdicts": verdicts},
                   indent=2), encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    win.close()
    pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
