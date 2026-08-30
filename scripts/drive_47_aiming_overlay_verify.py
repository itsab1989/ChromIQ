#!/usr/bin/env python3
"""Adversarial on-screen verification of the CR30 aiming overlay (6b879c6e).

Drives the REAL ChromIQ window: builds real charts with the real Create Chart
tab, loads them into the real Measure tab, arms a patch through the tab's own
`_on_patch_ready`, and photographs the real `TiffPreview`. Nothing about the
overlay is re-implemented here -- the only thing faked is the instrument, which
is not touched (constraint).

SAFETY
  * `~/Library/Preferences/com.chromiq.ChromIQ.plist` is copied aside on entry
    and compared byte-for-byte on exit.
  * `core.settings.QSettings` is replaced so EVERY `AppSettings()` anywhere in
    the app lands in the sandbox .ini, not the plist.
  * `CHROMIQ_PRESETS_DIR` points at the sandbox, so preset writes stay there.
  * `custom_output_path` is a sandbox folder; ~/ChromIQ is never written.

    python scripts/drive_47_aiming_overlay_verify.py --phases A
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SANDBOX = Path(os.environ.get(
    "CR30_47_SANDBOX",
    "/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/"
    "79c89ec2-11d6-4bdc-93a1-f4dcdc3c108d/scratchpad/sandbox47"))
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, QRect, QSettings, Qt   # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase           # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,     # noqa: E402
                             QMessageBox)

from core.resource_path import resource_path            # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
PLIST_BACKUP = SANDBOX / "com.chromiq.ChromIQ.plist.backup"
SHOTS = Path.home() / "Desktop" / "cr30-aiming-overlay-proof"
WORK = SANDBOX / "ChromIQ"
INI = SANDBOX / "settings.ini"

LEFT_MM, TOP_MM, RIGHT_MM, BOTTOM_MM = 1.0, 6.0, 2.0, 1.0


def say(*a):
    print(*a, flush=True)


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    w.grab().save(str(p))
    say(f"    saved {p.name}")
    return p


def crop_widget(w, box, name):
    """Grab the widget, crop, and save at 3x so a dash is judgeable."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    im = w.grab().toImage()
    dpr = im.devicePixelRatio() or 1.0
    x, y, ww, hh = [int(v * dpr) for v in box]
    sub = im.copy(QRect(x, y, ww, hh))
    big = sub.scaled(sub.width() * 3, sub.height() * 3,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    p = SHOTS / f"{name}.png"
    big.save(str(p))
    say(f"    saved {p.name}  (crop {box} of {w.__class__.__name__}, x3, dpr={dpr})")
    return p


# ------------------------------------------------------------------ safety
def guard_plist_in():
    if REAL_PLIST.exists():
        shutil.copy2(REAL_PLIST, PLIST_BACKUP)
        h = hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()[:16]
        say(f"    plist backed up -> {PLIST_BACKUP} (sha {h})")
        return h
    say("    no plist to back up")
    return None


def guard_plist_out(before):
    if before is None:
        return
    if not REAL_PLIST.exists():
        shutil.copy2(PLIST_BACKUP, REAL_PLIST)
        say("    plist was REMOVED -- restored from backup")
        return
    now = hashlib.sha256(REAL_PLIST.read_bytes()).hexdigest()[:16]
    if now != before:
        shutil.copy2(PLIST_BACKUP, REAL_PLIST)
        say(f"    !! plist CHANGED ({before} -> {now}) -- restored from backup")
    else:
        say(f"    plist untouched (sha {now})")


def make_settings():
    """A sandboxed AppSettings, and every future AppSettings() sandboxed too."""
    import core.settings as CS
    if not INI.exists() and REAL_PLIST.exists():
        src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
        dst = QSettings(str(INI), QSettings.Format.IniFormat)
        for k in src.allKeys():
            dst.setValue(k, src.value(k))
        dst.sync()

    def _sandboxed(*a, **k):
        return QSettings(str(INI), QSettings.Format.IniFormat)

    CS.QSettings = _sandboxed          # every AppSettings() from now on
    s = CS.AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(WORK))
    s.set("restore_last_session", False)
    return s


# ------------------------------------------------------------------ charts
def build_chart(app, win, tab, name, *, instrument="CR30", shape="hex",
                layout_mode="area_first", patch_mm=None, dpi=300,
                patches=None):
    """Build a REAL chart through the REAL Create Chart tab. Returns facts."""
    out = WORK / name
    ti2_cached = None
    if out.is_dir():
        for r in sorted(out.glob("runs/run*/*.ti2")):
            ti2_cached = r
    if ti2_cached and ti2_cached.with_suffix(".channels.json").is_file():
        say(f"    [{name}] reusing the chart already built in the sandbox")
        return chart_facts(ti2_cached)

    from ui.tabs.tab_chart import TabChart
    TabChart._prompt_target_name = lambda self, *a, **k: name
    win._tabs.setCurrentWidget(tab)
    pump(app, 400)
    tab._user_switch_mode("manual")
    pump(app, 600)
    tab._target_name_edit.setText(name)
    pnl = tab._manual_layout_panel
    i = pnl.instr.findData(instrument)
    assert i >= 0, f"{instrument} not offered"
    pnl.instr.setCurrentIndex(i)
    pump(app, 700)
    if shape is not None:
        j = pnl.mode.findData(shape)
        if j >= 0:
            pnl.mode.setCurrentIndex(j)
    pump(app, 300)
    if layout_mode is not None:
        k = pnl.layout_mode.findData(layout_mode)
        if k >= 0:
            pnl.layout_mode.setCurrentIndex(k)
    pump(app, 500)
    for key, val in (("t", TOP_MM), ("r", RIGHT_MM),
                     ("b", BOTTOM_MM), ("l", LEFT_MM)):
        pnl.margins[key].setValue(val)
    if patch_mm is not None:
        pnl.patch_x.setValue(patch_mm)
        pnl.patch_y.setValue(patch_mm)
    if dpi is not None:
        pnl.dpi.setValue(int(dpi))
    if patches is not None:
        cb = getattr(tab, "_manual_auto_patches_check", None)
        if cb is not None:
            cb.setChecked(False)
        pw = getattr(tab, "_manual_f_pw", None)
        if pw is not None:
            pw._control.setValue(int(patches))
    pump(app, 600)
    say(f"    [{name}] instr={pnl.instr.currentData()} shape={pnl.mode.currentData()} "
        f"layout={pnl.layout_mode.currentData()} dpi={pnl.dpi.value()} "
        f"patch={pnl.patch_x.value()}x{pnl.patch_y.value()} mm")
    tab._margin_ti2 = None
    say(f"    [{name}] target field = {tab._target_name_edit.text()!r}; "
        f"generate enabled = "
        f"{getattr(tab, '_generate_btn', None) and tab._generate_btn.isEnabled()}")
    tab._on_generate()
    for _ in range(300):
        pump(app, 500)
        if getattr(tab, "_margin_ti2", None):
            break
    ti2 = getattr(tab, "_margin_ti2", None)
    if not ti2:
        say(f"    [{name}] DID NOT BUILD")
        for attr in ("_log", "_manual_log", "_log_widget"):
            w = getattr(tab, attr, None)
            if w is not None and hasattr(w, "toPlainText"):
                say("      log tail:\n        " +
                    "\n        ".join(w.toPlainText().splitlines()[-25:]))
                break
        return None
    pump(app, 2000)
    return chart_facts(Path(ti2))


def chart_facts(ti2: Path):
    ch = ti2.with_suffix(".channels.json")
    lay = json.loads(ch.read_text())["layout"]
    dpi = float(lay.get("dpi") or 0)
    pats = [p for p in lay["patches"] if p.get("page") == 0]
    w_mm = pats[0]["w"] * 25.4 / dpi if dpi else 0
    h_mm = pats[0]["h"] * 25.4 / dpi if dpi else 0
    npages = 1 + max((p.get("page", 0) for p in lay["patches"]), default=0)
    f = {"ti2": ti2, "ti1": ti2.with_suffix(".ti1"), "channels": ch,
         "dpi": dpi, "n": len(lay["patches"]), "n0": len(pats),
         "w_px": pats[0]["w"], "h_px": pats[0]["h"],
         "w_mm": w_mm, "h_mm": h_mm, "pages": npages, "layout": lay}
    say(f"    [{ti2.parent.parent.parent.name}] {f['n']} patches, {npages} page(s), "
        f"dpi={dpi:.0f}, patch={w_mm:.2f}x{h_mm:.2f} mm "
        f"({f['w_px']}x{f['h_px']} px)")
    return f


# ------------------------------------------------------------------ measure
def load_into_measure(app, win, facts, *, use_ti1=False):
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 500)
    path = facts["ti1"] if use_ti1 else facts["ti2"]
    mt.set_ti1_path(path)
    pump(app, 2500)
    return mt


def arm_patch(app, mt, loc=None):
    """Arm a patch through the tab's OWN spot-mode entry point."""
    boxes = mt._patch_boxes
    if not boxes or not boxes[0]:
        say("    no patch geometry -- cannot arm")
        return None
    if loc is None:
        # THE PATCH NEAREST THE MIDDLE OF THE SHEET, so the circle has real
        # neighbours on every side -- a patch in row 1 would put half the
        # circle on the column-label band and prove nothing about crowding.
        d = boxes[0]
        xs = [b.center().x() for b in d.values()]
        ys = [b.center().y() for b in d.values()]
        mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        loc = min(d, key=lambda k: (d[k].center().x() - mx) ** 2
                  + (d[k].center().y() - my) ** 2)
    mt._on_patch_ready({"loc": loc})
    pump(app, 700)
    pv = mt._preview
    say(f"    armed {loc}: preview box={pv._active_patch_box} "
        f"page={pv._active_patch_page} aim={pv._aim_overlay} "
        f"body_px={pv._aim_body_px:.1f} ap_px={pv._aim_aperture_px:.1f}")
    return loc


def aim_row_state(mt):
    out = {}
    for p in ("g", "m"):
        cb = getattr(mt, f"_{p}_aim_help", None)
        tip = getattr(mt, f"_{p}_aim_help_tip", None)
        # isVisible() is False for ANY widget on the non-current stack page,
        # which would confound "hidden by the rule" with "hidden module".
        # isHidden() reports the widget's OWN explicit setVisible state.
        out[p] = {
            "shown": (not cb.isHidden()) if cb is not None else None,
            "checked": cb.isChecked() if cb is not None else None,
            "tip_shown": (not tip.isHidden()) if tip is not None else None,
        }
    return out


def group_height(app, mt, prefix):
    """Height of the Live-preview group with the module actually on screen."""
    was = mt._current_mode()
    mt._switch_mode("guided" if prefix == "g" else "manual")
    pump(app, 500)
    grp = getattr(mt, f"_{prefix}_view_grp", None)
    h = None
    if grp is not None:
        grp.layout().activate()
        pump(app, 200)
        h = grp.height()
    mt._switch_mode(was)
    pump(app, 300)
    return h


# ------------------------------------------------------------------ phases
def phase_A(app, win, tabc, charts):
    """Build the real charts once; everything else reuses them."""
    say("\nPHASE A - build the real charts")
    charts["hex"] = build_chart(app, win, tabc, "cr30-aim-hex",
                                shape="hex", layout_mode="area_first")
    charts["rect"] = build_chart(app, win, tabc, "cr30-aim-rect",
                                 shape="flat", layout_mode="area_first")
    charts["i1"] = build_chart(app, win, tabc, "i1-strip-chart",
                               instrument="i1", shape=None, layout_mode=None)
    return charts


def phase_B(app, win, charts):
    """The visibility rule."""
    say("\nPHASE B - the visibility rule")
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 600)

    say("  B1 no chart loaded (the window as it opens; nothing set yet)")
    say(f"      _ti1_path = {getattr(mt, '_ti1_path', 'MISSING')!r}  "
        f"_chart_is_cr30={mt._chart_is_cr30()}")
    st = aim_row_state(mt)
    h_none = (group_height(app, mt, "g"), group_height(app, mt, "m"))
    say(f"      {st}   view-group sizeHint h = {h_none}")
    shot(win, "B1_no_chart_row_hidden")
    shot(getattr(mt, "_m_view_grp"), "B1b_manual_live_preview_group_no_chart")

    say("  B2 a NON-CR30 chart (i1Pro, .ti2)")
    if charts.get("i1"):
        load_into_measure(app, win, charts["i1"])
        st = aim_row_state(mt)
        h_i1 = (group_height(app, mt, "g"), group_height(app, mt, "m"))
        say(f"      _chart_is_cr30={mt._chart_is_cr30()}  {st}   h = {h_i1}")
        shot(win, "B2_non_cr30_chart_row_hidden")
        shot(getattr(mt, "_m_view_grp"), "B2b_manual_live_preview_group_i1")

    say("  B3 a CR30 chart (.ti2)")
    load_into_measure(app, win, charts["hex"])
    st = aim_row_state(mt)
    h_cr = (group_height(app, mt, "g"), group_height(app, mt, "m"))
    say(f"      _chart_is_cr30={mt._chart_is_cr30()}  {st}   h = {h_cr}")
    cb = mt._g_aim_help
    say(f"      checkbox sizeHint h={cb.sizeHint().height()} "
        f"actual h={cb.height()}; the group's QVBoxLayout spacing="
        f"{mt._g_view_grp.layout().spacing()}")
    shot(win, "B3_cr30_chart_row_visible")
    shot(getattr(mt, "_m_view_grp"), "B3b_manual_live_preview_group_cr30")
    say(f"      THE HOLE TEST: group height cr30={h_cr} vs i1={h_i1} "
        f"vs none={h_none}")

    say("  B4 REOPEN TRAP - the tab handed the .ti1, as project open does")
    load_into_measure(app, win, charts["hex"], use_ti1=True)
    say(f"      _ti1_path={mt._ti1_path}")
    from ui.ti2_loader import read_target_instrument
    say(f"      direct read_target_instrument(.ti1) = "
        f"{read_target_instrument(mt._ti1_path)!r}  <- the trap")
    say(f"      _chart_is_cr30()                    = {mt._chart_is_cr30()}")
    say(f"      {aim_row_state(mt)}")
    shot(win, "B4_reopen_from_ti1_row_still_visible")

    say("  B5 switch back to the i1 chart, then to CR30 again")
    load_into_measure(app, win, charts["i1"])
    say(f"      after i1 : {aim_row_state(mt)}")
    load_into_measure(app, win, charts["hex"])
    say(f"      after cr30: {aim_row_state(mt)}")

    say("  B6 Guided <-> Manual")
    mt._switch_mode("guided")
    pump(app, 800)
    say(f"      guided : {aim_row_state(mt)}  mode={mt._current_mode()}")
    shot(win, "B6_guided_module_row_visible")
    mt._switch_mode("manual")
    pump(app, 800)
    say(f"      manual : {aim_row_state(mt)}  mode={mt._current_mode()}")

    say("  B7 the sidecar is MISSING")
    ch = charts["hex"]["channels"]
    bak = ch.with_suffix(".json.bak47")
    shutil.move(ch, bak)
    load_into_measure(app, win, charts["hex"])
    say(f"      is_cr30={mt._chart_is_cr30()} row={aim_row_state(mt)['m']}")
    say(f"      diameters = {mt._cr30_aim_diameters_px()}")
    arm_patch(app, mt)
    shot(win, "B7_sidecar_missing_no_circle")
    shutil.move(bak, ch)

    say("  B8 the sidecar is CORRUPT")
    good = ch.read_text()
    ch.write_text("{ this is not json ")
    load_into_measure(app, win, charts["hex"])
    say(f"      is_cr30={mt._chart_is_cr30()} row={aim_row_state(mt)['m']}")
    say(f"      diameters = {mt._cr30_aim_diameters_px()}")
    ch.write_text(good)

    say("  B9 the sidecar has NO dpi")
    d = json.loads(good)
    d["layout"].pop("dpi", None)
    ch.write_text(json.dumps(d))
    load_into_measure(app, win, charts["hex"])
    say(f"      diameters = {mt._cr30_aim_diameters_px()}")
    arm_patch(app, mt)
    pv = mt._preview
    say(f"      preview: aim={pv._aim_overlay} body={pv._aim_body_px}")
    shot(mt._preview, "B9_no_dpi_nothing_drawn")
    ch.write_text(good)
    return None


def phase_C(app, win, charts):
    """See it: the overlay on a real armed patch, hex and rectangular."""
    say("\nPHASE C - the overlay itself")
    mt = win._tab_measure
    for kind in ("hex", "rect"):
        f = charts.get(kind)
        if not f:
            continue
        load_into_measure(app, win, f)
        pv = mt._preview
        loc = arm_patch(app, mt)
        shot(win, f"C1_{kind}_full_window")
        shot(pv, f"C2_{kind}_preview_widget")
        # measured scale check
        s, ox, oy = pv._paint_geom
        box = pv._active_patch_box
        body_screen = pv._aim_body_px * s
        patch_screen = box.width() * s
        say(f"    [{kind}] s={s:.4f} patch={box.width()}x{box.height()} img-px "
            f"= {f['w_mm']:.2f} mm; body={pv._aim_body_px:.1f} img-px "
            f"= {pv._aim_body_px * 25.4 / f['dpi']:.2f} mm; "
            f"ratio body/patch = {pv._aim_body_px / box.width():.3f} "
            f"(expected {33.0 / f['w_mm']:.3f})")
        # zoom in so the dashes are judgeable at real size
        cx = int(box.center().x() * s + ox)
        cy = int(box.center().y() * s + oy)
        half = int(body_screen * 0.75)
        crop_widget(pv._img_label, (max(0, cx - half), max(0, cy - half),
                                    half * 2, half * 2),
                    f"C3_{kind}_closeup_x3")
        try:
            pv._apply_zoom(3.0, QPoint(cx, cy))
            pump(app, 1500)
            say(f"    zoom now {pv._zoom}")
            shot(pv, f"C4_{kind}_zoom3x")
            pv._apply_zoom(1.0 / 3.0, None)
            pump(app, 600)
        except Exception as e:      # noqa: BLE001
            say(f"    zoom failed: {e}")
    return None


def measure_drawn_circle(pv, facts, app=None):
    """Measure the BODY circle actually on screen, in mm, from the pixels.

    NOT by hunting for the accent colour -- a real chart contains patches of
    that colour and the first attempt measured one of them (292 mm). Instead:
    render the SAME scene with the overlay OFF and ON and take the FARTHEST
    CHANGED pixel from the armed patch's centre. Every changed pixel IS the
    overlay, whatever colour the paper under it happens to be.
    """
    import numpy as np

    from PyQt6.QtGui import QImage

    def grab():
        im = pv._img_label.grab().toImage().convertToFormat(
            QImage.Format.Format_RGB32)
        w, h = im.width(), im.height()
        ptr = im.bits()
        ptr.setsize(im.sizeInBytes())
        arr = np.frombuffer(ptr, np.uint8).reshape(
            (h, im.bytesPerLine() // 4, 4))[:, :w, :3].astype(int).copy()
        return arr, im.devicePixelRatio() or 1.0

    was = pv._aim_overlay
    ap0, bd0 = pv._aim_aperture_px, pv._aim_body_px
    pv.set_aim_overlay(False, ap0, bd0)
    if app:
        pump(app, 600)
    off, dpr = grab()
    pv.set_aim_overlay(True, ap0, bd0)
    if app:
        pump(app, 600)
    on, _ = grab()
    pv.set_aim_overlay(was, ap0, bd0)
    if app:
        pump(app, 300)
    diff = (np.abs(on - off).max(axis=2) > 12)
    ys, xs = np.nonzero(diff)
    s, ox, oy = pv._paint_geom
    box = pv._active_patch_box
    cx = (box.center().x() * s + ox) * dpr
    cy = (box.center().y() * s + oy) * dpr
    if len(xs) == 0:
        say("    NOTHING CHANGED between overlay off and on")
        return 0.0
    r = np.hypot(xs - cx, ys - cy)
    best = float(r.max())
    say(f"    {len(xs)} pixels changed when the overlay came on")
    diam_dev = best * 2.0
    diam_logical = diam_dev / dpr
    diam_img = diam_logical / s
    diam_mm = diam_img * 25.4 / facts["dpi"]
    say(f"    MEASURED FROM THE PIXELS: farthest accent pixel {best:.1f} dev-px "
        f"-> diameter {diam_dev:.1f} dev-px = {diam_img:.1f} image-px "
        f"= {diam_mm:.2f} mm   (claimed 33.00 mm, dpr={dpr})")
    return diam_mm


def phase_D(app, win, tabc, charts):
    """The scale and the aperture rule."""
    say("\nPHASE D - the scale and the aperture rule")
    mt = win._tab_measure

    say("  D1 the 33 mm claim, measured off the screen (hex chart)")
    load_into_measure(app, win, charts["hex"])
    arm_patch(app, mt)
    pv = mt._preview
    d_mm = measure_drawn_circle(pv, charts["hex"], app)
    shot(pv, "D1_measured_33mm_circle")

    say("  D2 a chart built at a NON-300 dpi")
    charts["dpi600"] = build_chart(app, win, tabc, "cr30-aim-600dpi",
                                   shape="flat", layout_mode="area_first",
                                   dpi=600)
    if charts["dpi600"]:
        load_into_measure(app, win, charts["dpi600"])
        arm_patch(app, mt)
        ap, body = mt._cr30_aim_diameters_px()
        say(f"      dpi={charts['dpi600']['dpi']:.0f}  body={body:.1f} img-px "
            f"= {body * 25.4 / charts['dpi600']['dpi']:.2f} mm")
        measure_drawn_circle(mt._preview, charts["dpi600"], app)
        shot(win, "D2_600dpi_chart_overlay")

    say("  D3 patches SMALLER than the 4 mm aperture")
    charts["tiny"] = build_chart(app, win, tabc, "cr30-aim-tiny",
                                 shape="flat", layout_mode="patch_first",
                                 patch_mm=3.0, patches=120)
    if charts["tiny"]:
        f = charts["tiny"]
        load_into_measure(app, win, f)
        arm_patch(app, mt)
        pv = mt._preview
        ap, body = mt._cr30_aim_diameters_px()
        box = pv._active_patch_box
        say(f"      patch {f['w_mm']:.2f}x{f['h_mm']:.2f} mm "
            f"({box.width()}x{box.height()} img-px); aperture {ap:.1f} img-px "
            f"= {ap * 25.4 / f['dpi']:.2f} mm")
        say(f"      RULE: aperture >= min(patch) ? "
            f"{ap:.1f} >= {min(box.width(), box.height())} -> "
            f"{ap >= min(box.width(), box.height())}")
        s, ox, oy = pv._paint_geom
        say(f"      aperture radius ON SCREEN = {ap * s / 2.0:.2f} logical px "
            f"(the paint suppresses it below 4.0)")
        shot(win, "D3_tiny_patch_full_window")
        shot(pv, "D3b_tiny_patch_preview")
        cx = int(box.center().x() * s + ox)
        cy = int(box.center().y() * s + oy)
        half = int(pv._aim_body_px * s * 0.75) or 60
        crop_widget(pv._img_label, (max(0, cx - half), max(0, cy - half),
                                    half * 2, half * 2),
                    "D3c_tiny_patch_closeup_x3")
        try:
            pv._apply_zoom(6.0, QPoint(cx, cy))
            pump(app, 800)
            shot(pv, "D3d_tiny_patch_zoom6x_aperture_overflow")
            pv._apply_zoom(1.0 / 6.0, None)
            pump(app, 400)
        except Exception as e:      # noqa: BLE001
            say(f"      zoom failed: {e}")

    say("  D4 comfortably LARGER patches: the aperture circle must stay hidden")
    load_into_measure(app, win, charts["hex"])
    arm_patch(app, mt)
    pv = mt._preview
    box = pv._active_patch_box
    say(f"      aperture {pv._aim_aperture_px:.1f} vs min(patch) "
        f"{min(box.width(), box.height())} -> drawn? "
        f"{pv._aim_aperture_px >= min(box.width(), box.height())}")
    return None


def phase_E(app, win, settings, charts):
    """Persistence."""
    say("\nPHASE E - persistence")
    mt = win._tab_measure
    load_into_measure(app, win, charts["hex"])

    say("  E1 default state as built")
    say(f"      {aim_row_state(mt)}")

    say("  E2 the linked Guided/Manual pair")
    mt._m_aim_help.setChecked(True)
    pump(app, 200)
    mt._g_aim_help.setChecked(False)
    pump(app, 400)
    say(f"      set GUIDED off -> manual={mt._m_aim_help.isChecked()}")
    mt._m_aim_help.setChecked(True)
    pump(app, 400)
    say(f"      set MANUAL on  -> guided={mt._g_aim_help.isChecked()}")

    say("  E3 Save as Defaults with it OFF, then a fresh window")
    mt._switch_mode("manual")
    pump(app, 300)
    mt._m_aim_help.setChecked(False)
    pump(app, 300)
    mt._on_save_defaults()
    mt._switch_mode("guided")
    pump(app, 300)
    mt._on_save_defaults()
    pump(app, 400)
    say(f"      stored measure_aim_help={settings.get('measure_aim_help')!r} "
        f"manual2_aim_help={settings.get('manual2_aim_help')!r}")
    shot(win, "E3_toggled_off_before_restart")

    from ui.main_window import MainWindow
    win2 = MainWindow(settings)
    win2.show()
    pump(app, 2500)
    mt2 = win2._tab_measure
    win2._tabs.setCurrentWidget(mt2)
    pump(app, 600)
    load_into_measure(app, win2, charts["hex"])
    say(f"      AFTER RESTART: {aim_row_state(mt2)}")
    say(f"      preview aim_overlay = {mt2._preview._aim_overlay}")
    shot(win2, "E3b_after_restart_still_off")

    say("  E4 a FRESH install (an empty settings store)")
    import core.settings as CS
    fresh_ini = SANDBOX / "fresh.ini"
    if fresh_ini.exists():
        fresh_ini.unlink()
    old = CS.QSettings
    CS.QSettings = lambda *a, **k: QSettings(str(fresh_ini),
                                             QSettings.Format.IniFormat)
    fresh = CS.AppSettings()
    fresh.set("custom_output_path", str(WORK))
    fresh.set("restore_last_session", False)
    win3 = MainWindow(fresh)
    win3.show()
    pump(app, 2500)
    mt3 = win3._tab_measure
    win3._tabs.setCurrentWidget(mt3)
    pump(app, 500)
    load_into_measure(app, win3, charts["hex"])
    say(f"      FRESH INSTALL: {aim_row_state(mt3)}")
    shot(win3, "E4_fresh_install_on_by_default")
    win3.close()
    CS.QSettings = old
    pump(app, 400)

    say("  E5 preset round-trip")
    mt2._switch_mode("manual")
    pump(app, 300)
    mt2._m_aim_help.setChecked(False)
    data_off = mt2._m_collect_preset_data()
    mt2._m_aim_help.setChecked(True)
    data_on = mt2._m_collect_preset_data()
    say(f"      collected off={data_off.get('aim_help')} on={data_on.get('aim_help')}")
    mt2._m_apply_preset_data(data_off)
    say(f"      apply(off) -> {mt2._m_aim_help.isChecked()}")
    mt2._m_apply_preset_data(data_on)
    say(f"      apply(on)  -> {mt2._m_aim_help.isChecked()}")
    legacy = dict(data_on)
    legacy.pop("aim_help")
    mt2._m_aim_help.setChecked(False)
    mt2._m_apply_preset_data(legacy)
    say(f"      apply(a preset written BEFORE the feature) -> "
        f"{mt2._m_aim_help.isChecked()}  (must be True)")

    say("  E6 the per-target store")
    from workflow import measure_settings as MS
    mt2._m_aim_help.setChecked(False)
    mt2._g_aim_help.setChecked(False)
    snap = MS.snapshot(mt2)
    say(f"      snapshot aim_help_manual={snap.get('aim_help_manual')} "
        f"aim_help_guided={snap.get('aim_help_guided')}")
    mt2._m_aim_help.setChecked(True)
    mt2._g_aim_help.setChecked(True)
    unknown = MS.apply(mt2, snap)
    say(f"      apply -> manual={mt2._m_aim_help.isChecked()} "
        f"guided={mt2._g_aim_help.isChecked()} unknown={unknown}")
    say("      ...and a target STORED BEFORE the feature existed:")
    legacy_snap = {k: v for k, v in snap.items() if "aim_help" not in k}
    mt2._m_aim_help.setChecked(True)
    mt2._g_aim_help.setChecked(True)
    MS.apply(mt2, legacy_snap)
    say(f"      apply(legacy) -> manual={mt2._m_aim_help.isChecked()} "
        f"guided={mt2._g_aim_help.isChecked()}  "
        "(untouched = the previous target's value leaks in)")
    win2.close()
    pump(app, 400)
    return None


# ------------------------------------------------------------- regressions
def render_reference(outdir: Path):
    """Render the shared preview scene WITHOUT the aiming overlay.

    Runs identically on this tree and on a worktree at the parent commit, so a
    byte-for-byte identical PNG proves the overlay commit changed nothing about
    the warn rings, the accent ring, the hover outline or the strip outline.
    Uses only APIs that existed before the commit.
    """
    from PIL import Image
    from ui.tiff_preview import TiffPreview
    app = QApplication.instance() or QApplication(sys.argv[:1])
    ti2 = next(iter(sorted((WORK / "cr30-aim-hex").glob("runs/run*/*.ti2"))))
    lay = json.loads(ti2.with_suffix(".channels.json").read_text())["layout"]
    tif = (sorted(ti2.parent.glob(f"{ti2.stem}_01.tif"))
           or sorted(ti2.parent.glob(f"{ti2.stem}.tif")))[0]
    pats = [p for p in lay["patches"] if p.get("page") == 0]
    pv = TiffPreview()
    pv.resize(900, 1100)
    pv.load_tiff([tif])
    pump(app, 1200)
    pv._hex_zigzag = True
    im = Image.open(tif).convert("RGB")
    items = []
    boxes = {}
    for i, p in enumerate(pats):
        r = QRect(p["x"], p["y"], p["w"], p["h"])
        boxes[p["loc"]] = r
        c = QColor(*im.getpixel((p["x"] + p["w"] // 2, p["y"] + p["h"] // 2)))
        items.append((r, c, c, (i % 37) == 0))          # every 37th flagged
    pv.set_patch_overlay(0, items, replace_page=True)
    pv.set_page_patch_boxes({0: list(boxes.values())})
    pv.set_patch_click_enabled(True, [boxes])
    mid = list(boxes)[len(boxes) // 2]
    hov = list(boxes)[len(boxes) // 3]
    pv.highlight_patch(0, boxes[mid])
    pv._hover_patch_loc = hov
    pv.show()
    pump(app, 1200)
    outdir.mkdir(parents=True, exist_ok=True)
    pv.grab().save(str(outdir / "reference_scene.png"))
    say(f"    rendered {outdir / 'reference_scene.png'}")
    pv.close()


def phase_F(app, win, charts, tabc=None):
    """Regressions and paint cost."""
    say("\nPHASE F - regressions")
    if tabc is not None and "big" not in charts:
        charts["big"] = build_chart(app, win, tabc, "cr30-aim-1144",
                                    shape="hex", layout_mode="area_first",
                                    patches=1144)
    import subprocess
    here = SANDBOX / "render_now"
    render_reference(here)

    say("  F1 the same scene rendered on the PARENT commit (6b879c6e^)")
    wt = SANDBOX / "parent_tree"
    if not wt.exists():
        subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach",
                        str(wt), "6b879c6e^"], check=True,
                       capture_output=True)
    shutil.copy2(__file__, wt / "scripts" / Path(__file__).name)
    there = SANDBOX / "render_parent"
    env = dict(os.environ, CR30_47_SANDBOX=str(SANDBOX))
    r = subprocess.run([sys.executable,
                        str(wt / "scripts" / Path(__file__).name),
                        "--render-only", str(there)],
                       cwd=str(wt), env=env, capture_output=True, text=True)
    say("      " + (r.stdout or "").strip().replace("\n", "\n      "))
    if r.returncode != 0:
        say("      parent render FAILED:\n" + (r.stderr or "")[-2000:])
    else:
        a = (here / "reference_scene.png").read_bytes()
        b = (there / "reference_scene.png").read_bytes()
        say(f"      identical bytes: {a == b}  ({len(a)} vs {len(b)})")
        if a != b:
            from PIL import Image, ImageChops
            ia = Image.open(here / "reference_scene.png").convert("RGB")
            ib = Image.open(there / "reference_scene.png").convert("RGB")
            diff = ImageChops.difference(ia, ib)
            say(f"      bounding box of the difference: {diff.getbbox()}")
            diff.save(str(SHOTS / "F1_diff_vs_parent_commit.png"))
        shutil.copy2(here / "reference_scene.png",
                     SHOTS / "F1_scene_this_tree.png")
        shutil.copy2(there / "reference_scene.png",
                     SHOTS / "F1_scene_parent_commit.png")

    say("  F2 paint cost with the overlay ON vs OFF")
    mt = win._tab_measure
    big = charts.get("big") or charts["hex"]
    load_into_measure(app, win, big)
    mt._switch_mode("manual")
    pump(app, 300)
    mt._m_aim_help.setChecked(True)
    pump(app, 300)
    arm_patch(app, mt)
    pv = mt._preview
    ap0, bd0 = pv._aim_aperture_px or 47.2, pv._aim_body_px or 389.8
    say(f"      chart: {big['n']} patches over {big['pages']} pages; "
        f"page 0 shows {len(mt._patch_boxes[0])}")

    def timed(on):
        # _repaint_label is where the whole overlay is drawn; the widget's own
        # paintEvent only blits the finished pixmap, so timing repaint() would
        # have measured nothing.
        pv._aim_overlay = on
        pv._aim_aperture_px, pv._aim_body_px = ap0, bd0
        pv._repaint_label()
        t0 = time.perf_counter()
        for _ in range(30):
            pv._repaint_label()
        return (time.perf_counter() - t0) / 30 * 1000.0

    off = timed(False)
    on = timed(True)
    off2 = timed(False)
    say(f"      _repaint_label: overlay OFF {off:.1f} / {off2:.1f} ms, "
        f"ON {on:.1f} ms  (delta {on - (off + off2) / 2:+.2f} ms)")
    pv._aim_overlay = True
    pv._repaint_label()

    say("  F3 'Show only measured patches' ON")
    mt._switch_mode("manual")
    pump(app, 200)
    mt._m_only_measured.setChecked(True)
    pump(app, 600)
    shot(pv, "F3_only_measured_on")
    mt._m_only_measured.setChecked(False)
    pump(app, 400)

    say("  F4 a SMALL window - the Measure preview cannot zoom, so the only "
        "thing that shrinks the sheet is the pane")
    old = win.size()
    for w_, h_ in ((1200, 800), (1000, 700), (900, 620)):
        win.resize(w_, h_)
        pump(app, 900)
        s, _ox, _oy = pv._paint_geom
        box = pv._active_patch_box
        say(f"      window {w_}x{h_}: s={s:.4f}, patch "
            f"{box.width() * s:.1f} lp, body radius "
            f"{pv._aim_body_px * s / 2:.1f} lp, aperture radius "
            f"{pv._aim_aperture_px * s / 2:.2f} lp "
            f"-> aperture drawn? {pv._aim_aperture_px * s / 2 >= 4.0}")
    shot(pv, "F4_small_window")
    win.resize(old)
    pump(app, 800)

    say("  F5 multi-page: a page WITHOUT the armed patch")
    if big["pages"] > 1:
        pv.show_page(1)
        pump(app, 900)
        r, _dpr = overlay_only_pixels(pv, app)
        say(f"      page 2 of {big['pages']}: overlay pixels = {len(r)} "
            + ("(correct: nothing drawn)" if len(r) == 0 else "<- SOMETHING IS DRAWN"))
        shot(pv, "F5_other_page_nothing_drawn")
        pv.show_page(0)
        pump(app, 600)
    else:
        say("      this chart is one page")

    say("  F6 the TINY-patch chart in a smaller window: does the aperture "
        "warning survive?")
    tiny = charts.get("tiny")
    if tiny:
        for w_, h_ in ((1500, 1000), (1280, 860), (1100, 760)):
            win.resize(w_, h_)
            pump(app, 700)
            load_into_measure(app, win, tiny)
            mt._switch_mode("manual")
            mt._m_aim_help.setChecked(True)
            pump(app, 300)
            arm_patch(app, mt)
            pv2 = mt._preview
            s2, _o1, _o2 = pv2._paint_geom
            b2 = pv2._active_patch_box
            r, _d = overlay_only_pixels(pv2, app)
            near = r[r < b2.width() * s2]
            say(f"      window {w_}x{h_}: s={s2:.4f}, patch "
                f"{b2.width() * s2:.1f} lp, aperture radius "
                f"{pv2._aim_aperture_px * s2 / 2:.2f} lp -> overlay pixels "
                f"inside the patch width: {len(near)}")
            shot(pv2._img_label, f"F6_tiny_{w_}x{h_}")
        win.resize(1500, 1000)
        pump(app, 600)
    return None


# ------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="ABCDEF")
    ap.add_argument("--render-only", default="")
    args = ap.parse_args()

    if args.render_only:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setApplicationName("ChromIQ")
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
        from ui.styles import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)
        render_reference(Path(args.render_only))
        return 0

    phases = args.phases.upper()
    say("SAFETY")
    before = guard_plist_in()
    try:
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setApplicationName("ChromIQ")
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
        from ui.styles import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)
        settings = make_settings()
        say(f"    sandbox   : {SANDBOX}")
        say(f"    work root : {WORK}")
        say(f"    presets   : {os.environ['CHROMIQ_PRESETS_DIR']}")

        QDialog.exec = lambda self: 1                  # type: ignore[assignment]
        ASKED: list = []

        def _mb(kind, yes):
            def f(*a, **k):
                txt = " | ".join(str(x)[:200] for x in a[1:3])
                ASKED.append(f"{kind}: {txt}")
                say(f"      [dialog {kind}] {txt}")
                return yes
            return staticmethod(f)

        for m in ("warning", "critical", "information"):
            setattr(QMessageBox, m, _mb(m, 0))
        # A question is the app asking permission; the user driving this would
        # say yes, so say yes -- 0 is not Yes and silently cancelled a build.
        setattr(QMessageBox, "question",
                _mb("question", QMessageBox.StandardButton.Yes))
        from ui.main_window import MainWindow
        from ui.tabs.tab_chart import TabChart
        TabChart._confirm_displacing_results = lambda self, *a, **k: True

        win = MainWindow(settings)
        win.resize(1500, 1000)
        win.show()
        pump(app, 2500)
        tabc = win._tab_chart

        charts: dict = {}
        # Always resolve whatever is already on disk, so a later phase can run
        # alone.
        for key, name in (("hex", "cr30-aim-hex"), ("rect", "cr30-aim-rect"),
                          ("i1", "i1-strip-chart"), ("tiny", "cr30-aim-tiny"),
                          ("dpi600", "cr30-aim-600dpi"),
                          ("big", "cr30-aim-1144")):
            cand = sorted((WORK / name).glob("runs/run*/*.ti2"))
            if cand:
                charts[key] = chart_facts(cand[-1])

        if "A" in phases:
            phase_A(app, win, tabc, charts)
        if "B" in phases:
            phase_B(app, win, charts)
        if "C" in phases:
            phase_C(app, win, charts)
        if "D" in phases:
            phase_D(app, win, tabc, charts)
        if "E" in phases:
            phase_E(app, win, settings, charts)
        if "F" in phases:
            phase_F(app, win, charts, tabc)
        if "G" in phases:
            phase_G(app, win, charts)
        if "H" in phases:
            phase_H(app, win, charts)
        if "I" in phases:
            phase_I(app, win, charts)
        if "J" in phases:
            phase_J(app, win, charts)
        win.close()
        pump(app, 500)
    finally:
        say("\nSAFETY (exit)")
        guard_plist_out(before)
    say(f"\nscreenshots in {SHOTS}")
    return 0



def overlay_only_pixels(pv, app):
    """(radii in logical px of every pixel the overlay adds, dpr).

    Renders the identical scene with the aiming overlay off and on; every
    changed pixel IS the overlay. Colour-independent, so it cannot be fooled by
    a chart patch that happens to be the accent green.
    """
    import numpy as np
    from PyQt6.QtGui import QImage

    def grab():
        im = pv._img_label.grab().toImage().convertToFormat(
            QImage.Format.Format_RGB32)
        w, h = im.width(), im.height()
        ptr = im.bits()
        ptr.setsize(im.sizeInBytes())
        arr = np.frombuffer(ptr, np.uint8).reshape(
            (h, im.bytesPerLine() // 4, 4))[:, :w, :3].astype(int).copy()
        return arr, im.devicePixelRatio() or 1.0

    was, ap0, bd0 = pv._aim_overlay, pv._aim_aperture_px, pv._aim_body_px
    pv.set_aim_overlay(False, ap0, bd0)
    pump(app, 500)
    off, dpr = grab()
    pv.set_aim_overlay(True, ap0, bd0)
    pump(app, 500)
    on, _ = grab()
    pv.set_aim_overlay(was, ap0, bd0)
    pump(app, 300)
    d = (np.abs(on - off).max(axis=2) > 12)
    ys, xs = np.nonzero(d)
    s, ox, oy = pv._paint_geom
    b = pv._active_patch_box
    cx = (b.center().x() * s + ox) * dpr
    cy = (b.center().y() * s + oy) * dpr
    return np.hypot(xs - cx, ys - cy) / dpr, dpr


def phase_G(app, win, charts):
    """What the overlay ACTUALLY puts on the screen, pixel by pixel."""
    import numpy as np
    say("\nPHASE G - the overlay's own pixels, isolated by an on/off diff")
    mt = win._tab_measure
    for kind in ("hex", "tiny"):
        f = charts.get(kind)
        if not f:
            continue
        load_into_measure(app, win, f)
        arm_patch(app, mt)
        pv = mt._preview
        s, _ox, _oy = pv._paint_geom
        r, dpr = overlay_only_pixels(pv, app)
        box = pv._active_patch_box
        say(f"  [{kind}] patch {f['w_mm']:.2f} mm = "
            f"{box.width() * s:.1f} logical px; dpr={dpr}")
        say(f"      body radius expected {pv._aim_body_px * s / 2:.2f} lp, "
            f"aperture radius expected {pv._aim_aperture_px * s / 2:.2f} lp")
        say(f"      {len(r)} overlay pixels; radii "
            f"min {r.min():.2f} max {r.max():.2f} lp")
        hist, edges = np.histogram(r, bins=[0, 4, 8, 12, 16, 24, 32, 36, 38,
                                            40, 42, 50, 200])
        say("      radial histogram (logical px): " + ", ".join(
            f"{edges[i]:.0f}-{edges[i+1]:.0f}:{hist[i]}"
            for i in range(len(hist)) if hist[i]))
        outer = r[r > r.max() * 0.5]
        say(f"      body stroke: inner {outer.min():.2f} outer {outer.max():.2f} "
            f"-> centreline {(outer.min() + outer.max()) / 2:.2f} lp "
            f"= {(outer.min() + outer.max()) / s * 25.4 / f['dpi']:.2f} mm "
            "diameter  (claimed 33.00 mm)")
        near = r[r < box.width() * s]
        say(f"      pixels INSIDE the patch's own width: {len(near)}"
            + ("  <- the aperture circle is visible" if len(near) else
               "  <- NOTHING: the aperture circle is not on the screen"))
    return None


def crop_scaled(w, box, name, factor):
    SHOTS.mkdir(parents=True, exist_ok=True)
    im = w.grab().toImage()
    dpr = im.devicePixelRatio() or 1.0
    x, y, ww, hh = [int(v * dpr) for v in box]
    sub = im.copy(QRect(x, y, ww, hh))
    big = sub.scaled(sub.width() * factor, sub.height() * factor,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    p = SHOTS / f"{name}.png"
    big.save(str(p))
    say(f"    saved {p.name} (x{factor})")
    return p


def phase_H(app, win, charts):
    """High magnification: what the aperture warning really looks like."""
    say("\nPHASE H - the aperture warning at high magnification")
    mt = win._tab_measure
    for kind, half, fac in (("tiny", 26, 10), ("hex", 55, 5)):
        f = charts.get(kind)
        if not f:
            continue
        load_into_measure(app, win, f)
        arm_patch(app, mt)
        pv = mt._preview
        s, ox, oy = pv._paint_geom
        b = pv._active_patch_box
        cx = int(b.center().x() * s + ox)
        cy = int(b.center().y() * s + oy)
        say(f"  [{kind}] patch {b.width() * s:.1f} lp, accent ring "
            f"{'thin (small patch)' if min(b.width(), b.height()) * s < 24 else 'full'}"
            f", aperture radius {pv._aim_aperture_px * s / 2:.2f} lp")
        crop_scaled(pv._img_label, (cx - half, cy - half, half * 2, half * 2),
                    f"H1_{kind}_armed_patch_x{fac}", fac)
    return None


def phase_I(app, win, charts):
    """Side-by-side with the agreed mockup."""
    from PIL import Image
    say("\nPHASE I - side by side with docs/design/mockups/cr30/aiming-circle.png")
    mock = Image.open(ROOT / "docs/design/mockups/cr30/aiming-circle.png").convert("RGB")
    real = Image.open(SHOTS / "C3_hex_closeup_x3.png").convert("RGB")
    h = 900
    mock = mock.resize((int(mock.width * h / mock.height), h))
    real = real.resize((int(real.width * h / real.height), h))
    out = Image.new("RGB", (mock.width + real.width + 24, h), (245, 245, 245))
    out.paste(mock, (0, 0))
    out.paste(real, (mock.width + 24, 0))
    out.save(SHOTS / "I1_mockup_left_real_app_right.png")
    say(f"    saved I1_mockup_left_real_app_right.png ({out.size})")
    return None


def phase_J(app, win, charts):
    """Toggling the CHECKBOX itself, live, with a patch armed."""
    say("\nPHASE J - the checkbox drives the preview live")
    mt = win._tab_measure
    load_into_measure(app, win, charts["hex"])
    for mode, pfx in (("manual", "m"), ("guided", "g")):
        mt._switch_mode(mode)
        pump(app, 500)
        cb = getattr(mt, f"_{pfx}_aim_help")
        arm_patch(app, mt)
        pv = mt._preview
        cb.setChecked(True)
        pump(app, 600)
        on = pv._aim_overlay
        cb.setChecked(False)
        pump(app, 600)
        off = pv._aim_overlay
        r, _d = overlay_only_pixels(pv, app) if on else ([], 1)
        cb.setChecked(True)
        pump(app, 500)
        say(f"  [{mode}] ticked -> preview aim={on}; unticked -> aim={off}; "
            f"back on -> aim={pv._aim_overlay}")
        shot(pv._img_label, f"J1_{mode}_checkbox_on")
        cb.setChecked(False)
        pump(app, 700)
        shot(pv._img_label, f"J2_{mode}_checkbox_off")
        cb.setChecked(True)
        pump(app, 400)
    say("  ...and the INACTIVE module's mirror must not touch the preview")
    mt._switch_mode("guided")
    pump(app, 400)
    arm_patch(app, mt)
    mt._g_aim_help.setChecked(True)
    pump(app, 400)
    before = mt._preview._aim_overlay
    mt._m_aim_help.setChecked(False)      # mirrors into guided too (linked)
    pump(app, 600)
    say(f"      guided box now {mt._g_aim_help.isChecked()}, "
        f"preview aim {before} -> {mt._preview._aim_overlay}")
    return None

if __name__ == "__main__":
    raise SystemExit(main())
