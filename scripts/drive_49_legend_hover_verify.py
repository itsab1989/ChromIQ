#!/usr/bin/env python3
"""Adversarial on-screen verification of the legend hover-hide (29c1a7c6).

Drives the REAL ChromIQ window: real Create Chart tab, real Measure tab, real
TiffPreview, real Qt mouse events delivered through the window's own hit test.
Nothing about the hover behaviour is re-implemented here.

SAFETY
  * ~/Library/Preferences/com.chromiq.ChromIQ.plist copied aside and compared.
  * core.settings.QSettings replaced so every AppSettings() lands in a sandbox.
  * CHROMIQ_PRESETS_DIR sandboxed; custom_output_path sandboxed; ~/ChromIQ
    is never written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SANDBOX = Path(os.environ.get(
    "CR30_49_SANDBOX",
    "/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/"
    "79c89ec2-11d6-4bdc-93a1-f4dcdc3c108d/scratchpad/sandbox49"))
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, QRect, QSettings, Qt   # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase           # noqa: E402
from PyQt6.QtTest import QTest                          # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,     # noqa: E402
                             QMessageBox)

from core.resource_path import resource_path            # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
PLIST_BACKUP = SANDBOX / "com.chromiq.ChromIQ.plist.backup"
SHOTS = Path.home() / "Desktop" / "cr30-legend-hover-verify"
WORK = SANDBOX / "ChromIQ"
INI = SANDBOX / "settings.ini"

LOG: list = []


def say(*a):
    s = " ".join(str(x) for x in a)
    LOG.append(s)
    print(s, flush=True)


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def shot(w, name, note=""):
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    w.grab().save(str(p))
    say(f"    saved {p.name}   {note}")
    return p


def crop(w, box, name, factor=3, note=""):
    SHOTS.mkdir(parents=True, exist_ok=True)
    im = w.grab().toImage()
    dpr = im.devicePixelRatio() or 1.0
    x, y, ww, hh = [int(v * dpr) for v in box]
    x = max(0, x); y = max(0, y)
    ww = min(ww, im.width() - x); hh = min(hh, im.height() - y)
    sub = im.copy(QRect(x, y, ww, hh))
    big = sub.scaled(sub.width() * factor, sub.height() * factor,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.FastTransformation)
    p = SHOTS / f"{name}.png"
    big.save(str(p))
    say(f"    saved {p.name}  (crop {box} of {w.__class__.__name__} x{factor}, dpr={dpr}) {note}")
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
    import core.settings as CS
    if not INI.exists() and REAL_PLIST.exists():
        src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
        dst = QSettings(str(INI), QSettings.Format.IniFormat)
        for k in src.allKeys():
            dst.setValue(k, src.value(k))
        dst.sync()

    def _sandboxed(*a, **k):
        return QSettings(str(INI), QSettings.Format.IniFormat)

    CS.QSettings = _sandboxed
    s = CS.AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    s.set("custom_output_path", str(WORK))
    s.set("restore_last_session", False)
    return s


# ------------------------------------------------------------------ charts
LEFT_MM, TOP_MM, RIGHT_MM, BOTTOM_MM = 5.0, 6.0, 5.0, 12.0


def chart_facts(ti2: Path):
    ch = ti2.with_suffix(".channels.json")
    lay = json.loads(ch.read_text())["layout"]
    dpi = float(lay.get("dpi") or 0)
    pats = [p for p in lay["patches"] if p.get("page") == 0]
    npages = 1 + max((p.get("page", 0) for p in lay["patches"]), default=0)
    f = {"ti2": ti2, "ti1": ti2.with_suffix(".ti1"), "channels": ch,
         "dpi": dpi, "n": len(lay["patches"]), "n0": len(pats),
         "pages": npages, "layout": lay, "name": ti2.stem}
    say(f"    [{ti2.stem}] {f['n']} patches, {npages} page(s), dpi={dpi:.0f}")
    return f


def build_chart(app, win, tab, name, *, instrument="i1", shape=None,
                layout_mode=None, margins=None, patches=None, dpi=None):
    out = WORK / name
    cand = sorted(out.glob("runs/run*/*.ti2"))
    if cand and cand[-1].with_suffix(".channels.json").is_file():
        say(f"    [{name}] reusing the chart already built in this sandbox")
        return chart_facts(cand[-1])

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
        pump(app, 400)
    mm = margins or (LEFT_MM, TOP_MM, RIGHT_MM, BOTTOM_MM)
    for key, val in (("l", mm[0]), ("t", mm[1]), ("r", mm[2]), ("b", mm[3])):
        pnl.margins[key].setValue(val)
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
    say(f"    [{name}] instr={pnl.instr.currentData()} "
        f"margins l/t/r/b={[pnl.margins[k].value() for k in 'ltrb']} "
        f"dpi={pnl.dpi.value()}")
    tab._margin_ti2 = None
    tab._on_generate()
    for _ in range(400):
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
                    "\n        ".join(w.toPlainText().splitlines()[-20:]))
                break
        return None
    pump(app, 2000)
    return chart_facts(Path(ti2))


def write_ti3(facts):
    """A .ti3 beside the chart, built by the PROJECT'S OWN demo generator from
    the chart's REAL .ti2 (scripts/make_demo_projects.py::_ti3_from_ti2).
    The numbers are synthesised -- no instrument is touched -- but the chart,
    the geometry and every code path from here on are the real ones."""
    from scripts.make_demo_projects import _ti3_from_ti2
    ti3 = facts["ti2"].with_suffix(".ti3")
    if not ti3.exists():
        ti3.write_text(_ti3_from_ti2(facts["ti2"], drift=1.6))
    say(f"    .ti3 beside the chart: {ti3.name} "
        f"({len(ti3.read_text().splitlines())} lines)")
    return ti3


def load_measured(app, win, facts, *, tick_overlay=True):
    """Load the chart into the REAL Measure tab and turn the overlay on the way
    a user does: engine selected, then tick 'Show overlay from existing
    measurement'."""
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 400)
    mt.set_ti1_path(facts["ti2"])
    pump(app, 2500)
    say(f"    engine selected = {mt._engine_selected()}   "
        f"overlay box visible = {not mt._m_overlay_cb.isHidden()}")
    if tick_overlay:
        cb = (mt._overlay_cb if mt._current_mode() == "guided"
              else mt._m_overlay_cb)
        cb.setChecked(True)
        pump(app, 1200)
    pv = mt._preview
    say(f"    overlay pages={sorted(pv._patch_overlay)} "
        f"items(page0)={len(pv._patch_overlay.get(0, []))} "
        f"stripe_rects={len(pv._stripe_rects)} legend={pv._legend_rect}")
    return mt


# ------------------------------------------------------------------ probes
class RepaintCounter:
    """Counts real _repaint_label calls without touching source."""

    def __init__(self, pv):
        self.pv = pv
        self.n = 0
        self._orig = pv._repaint_label

        def wrapped():
            self.n += 1
            return self._orig()
        pv._repaint_label = wrapped

    def reset(self):
        self.n = 0
        return self

    def restore(self):
        try:
            del self.pv._repaint_label
        except Exception:
            self.pv._repaint_label = self._orig


def label_to_window(pv, pt: QPoint) -> QPoint:
    return pv._img_label.mapTo(pv.window(), pt)


def move_to_label(app, pv, pt: QPoint, settle=90):
    """Deliver a REAL Qt mouse move through the top-level window's own hit
    test, at a point given in _img_label coordinates.

    macOS delivers its own Enter/Leave asynchronously around a synthesised
    move, and a stray Leave clears `_legend_pointer`; resend once so the widget
    really believes the pointer is where this call put it."""
    QTest.mouseMove(pv.window(), label_to_window(pv, pt))
    pump(app, settle)
    for _ in range(3):
        if pv._legend_pointer is not None:
            break
        QTest.mouseMove(pv.window(), label_to_window(pv, pt + QPoint(1, 0)))
        pump(app, 30)
        QTest.mouseMove(pv.window(), label_to_window(pv, pt))
        pump(app, 60)


def settle_fade(app, pv, extra=60, limit=1500):
    """Let the chip's fade animation finish, then a little more."""
    end = time.monotonic() + limit / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        a = getattr(pv, "_legend_fade", None)
        from PyQt6.QtCore import QAbstractAnimation
        if a is None or a.state() != QAbstractAnimation.State.Running:
            break
        time.sleep(0.005)
    pump(app, extra)


def chip_visible_now(pv, app) -> bool:
    """Is the chip PAINTED right now?

    Decided by DIFFERENCE, not by absolute darkness: the chip can sit over dark
    patches, where a 'count the dark pixels' test says yes whether or not the
    chip is there. So: grab as-is, force the opacity to 0 and grab again, then
    put the opacity back exactly as it was. A frame that changes inside the
    chip's rectangle had a chip in it.
    """
    pump(app, 30)
    r = pv._legend_rect
    if r is None or pv._paint_geom is None or pv._legend_geom is None:
        return False
    _s, ox, oy = pv._paint_geom
    lox, loy = pv._legend_geom
    box = r.translated(int(ox - lox), int(oy - loy))
    a = pv._img_label.grab().toImage()
    saved = pv._legend_opacity
    if saved <= 0.01:
        return False
    pv._legend_opacity = 0.0
    pv._repaint_label()
    pump(app, 25)
    b = pv._img_label.grab().toImage()
    pv._legend_opacity = saved
    pv._repaint_label()
    pump(app, 25)
    dpr = a.devicePixelRatio() or 1.0
    n = 0
    for yy in range(box.top() + 2, box.bottom() - 1, 2):
        for xx in range(box.left() + 2, box.right() - 1, 3):
            px, py = int(xx * dpr), int(yy * dpr)
            if 0 <= px < a.width() and 0 <= py < a.height():
                if a.pixelColor(px, py) != b.pixelColor(px, py):
                    n += 1
    return n > 20


def true_chip_bbox(pv, app):
    """The chip's on-screen rectangle, measured by DIFFERENCE between a frame
    drawn at full opacity and one drawn at zero. Independent of every mapping
    in the code under test."""
    saved = pv._legend_opacity
    pv._legend_opacity = 1.0
    pv._repaint_label()
    pump(app, 60)
    a = pv._img_label.grab().toImage()
    pv._legend_opacity = 0.0
    pv._repaint_label()
    pump(app, 60)
    b = pv._img_label.grab().toImage()
    pv._legend_opacity = saved
    pv._repaint_label()
    pump(app, 40)
    dpr = a.devicePixelRatio() or 1.0
    xs, ys = [], []
    for y in range(a.height()):
        for x in range(a.width()):
            if a.pixelColor(x, y) != b.pixelColor(x, y):
                xs.append(x); ys.append(y)
    if not xs:
        return None, dpr
    return QRect(int(min(xs) / dpr), int(min(ys) / dpr),
                 int((max(xs) - min(xs) + 1) / dpr),
                 int((max(ys) - min(ys) + 1) / dpr)), dpr


def label_rect(pv):
    """The remembered legend rect translated into _img_label coordinates."""
    if pv._legend_rect is None or pv._paint_geom is None or pv._legend_geom is None:
        return None
    _s, ox, oy = pv._paint_geom
    lox, loy = pv._legend_geom
    return pv._legend_rect.translated(int(ox - lox), int(oy - loy))


# ------------------------------------------------------------------ phases
def phase_A(app, win, tabc, charts):
    """Build the real charts once."""
    say("\nPHASE A - build real charts in the real Create Chart tab")
    charts["i1"] = build_chart(app, win, tabc, "legend-i1-strip",
                               instrument="i1")
    for f in charts.values():
        if f:
            write_ti3(f)
    return charts


def phase_B(app, win, charts):
    """SEE IT: before / during / after, on the real Measure tab."""
    say("\nPHASE B - see it: chip, real pointer on it, pointer off it")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    if pv._legend_rect is None:
        say("    !! no legend chip -- the rest of B proves nothing")
        return None
    lab = label_rect(pv)
    say(f"    legend rect (canvas) {pv._legend_rect}  geom={pv._legend_geom}")
    say(f"    paint_geom {pv._paint_geom}  -> label coords {lab}")
    true_r, dpr = true_chip_bbox(pv, app)
    say(f"    MEASURED from pixels {true_r}  dpr={dpr}")
    if true_r is not None:
        say(f"    mapping error l/t/r/b = {true_r.left()-lab.left()}, "
            f"{true_r.top()-lab.top()}, {true_r.right()-lab.right()}, "
            f"{true_r.bottom()-lab.bottom()} px")

    box = (lab.x() - 24, lab.y() - 34, lab.width() + 48, lab.height() + 68)

    move_to_label(app, pv, QPoint(lab.center().x(), max(2, lab.top() - 240)))
    settle_fade(app, pv)
    say(f"    B1 pointer far above: ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.3f} "
        f"painted={chip_visible_now(pv, app)}")
    shot(win, "B1_window_chip_visible", "whole window; real pointer far from the chip")
    crop(pv._img_label, box, "B2_chip_visible_x3")

    move_to_label(app, pv, lab.center())
    settle_fade(app, pv)
    say(f"    B3 pointer ON the chip: ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.3f} "
        f"painted={chip_visible_now(pv, app)}")
    shot(win, "B3_window_chip_hidden", "whole window; real pointer resting on the chip")
    crop(pv._img_label, box, "B4_chip_hidden_x3")

    move_to_label(app, pv, QPoint(lab.center().x(), max(2, lab.top() - 240)))
    settle_fade(app, pv)
    say(f"    B5 pointer away again: hidden={pv._legend_hidden} "
        f"opacity={pv._legend_opacity:.3f} painted={chip_visible_now(pv, app)}")
    crop(pv._img_label, box, "B5_chip_back_x3")

    # mid-fade frames, so the fade itself is on record
    move_to_label(app, pv, lab.center(), settle=0)
    for i, ms in enumerate((25, 55, 90)):
        pump(app, ms if i == 0 else ms - (25, 55, 90)[i - 1])
        crop(pv._img_label, box, f"B6_{i}_fade_at_{ms}ms",
             note=f"opacity={pv._legend_opacity:.2f}")
    settle_fade(app, pv)

    QTest.mouseMove(win, QPoint(20, 20))
    pump(app, 400)
    settle_fade(app, pv)
    say(f"    B7 pointer out of the preview entirely: ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.3f} "
        f"painted={chip_visible_now(pv, app)}")
    return mt


def sweep(app, pv, pts, label, rc):
    """Walk `pts` (label coords) one step at a time; record the painted state
    and the opacity after each step has settled."""
    move_to_label(app, pv, QPoint(*pts[0]), settle=150)
    settle_fade(app, pv)
    rc.reset()
    seq, ops = [], []
    for (x, y) in pts:
        move_to_label(app, pv, QPoint(x, y), settle=30)
        settle_fade(app, pv, extra=25, limit=600)
        seq.append(1 if chip_visible_now(pv, app) else 0)
        ops.append(pv._legend_opacity)
    toggles = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
    say(f"    {label:11s}: {''.join(str(v) for v in seq)}  "
        f"toggles={toggles} repaints={rc.n}")
    say(f"                 opacity {' '.join(f'{o:.2f}' for o in ops)}")
    return seq, toggles, rc.n


def phase_C(app, win, charts):
    """FLICKER: approach each edge one pixel at a time, in and out."""
    say("\nPHASE C - the flicker sweep, 1 px at a time, all four edges")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    lab = label_rect(pv)
    true_r, dpr = true_chip_bbox(pv, app)
    say(f"    remembered rect (label coords) = {lab}")
    say(f"    MEASURED rect from pixels      = {true_r}   dpr={dpr}")
    rc = RepaintCounter(pv)
    out = {}
    N = 12
    edges = {
        "top":    [(lab.center().x(), lab.top() - N + i) for i in range(2 * N)],
        "bottom": [(lab.center().x(), lab.bottom() + N - i) for i in range(2 * N)],
        "left":   [(lab.left() - N + i, lab.center().y()) for i in range(2 * N)],
        "right":  [(lab.right() + N - i, lab.center().y()) for i in range(2 * N)],
    }
    for edge, pts in edges.items():
        out[edge + "_in"] = sweep(app, pv, pts, edge + " in", rc)
        out[edge + "_out"] = sweep(app, pv, list(reversed(pts)), edge + " out", rc)

    say("    C2  sit still ON the chip for 2 s")
    move_to_label(app, pv, lab.center(), settle=200)
    settle_fade(app, pv)
    rc.reset()
    pump(app, 2000)
    say(f"        repaints while stationary on the chip = {rc.n} "
        f"opacity={pv._legend_opacity:.3f} painted={chip_visible_now(pv, app)}")

    say("    C3  wiggle INSIDE the chip's footprint, 40 moves")
    rc.reset()
    states = []
    for i in range(40):
        q = QPoint(lab.left() + 6 + (i * 3) % max(1, lab.width() - 12),
                   lab.top() + 3 + (i % max(1, lab.height() - 6)))
        move_to_label(app, pv, q, settle=25)
        states.append(1 if chip_visible_now(pv, app) else 0)
    say(f"        painted = {''.join(str(s) for s in states)} repaints={rc.n} "
        f"opacity={pv._legend_opacity:.3f}")

    say("    C4  SAW the edge fast, 120 crossings (the segfault the fade note "
        "warns about)")
    rc.reset()
    for i in range(120):
        y = lab.top() - 4 if i % 2 == 0 else lab.top() + 4
        QTest.mouseMove(pv.window(),
                        label_to_window(pv, QPoint(lab.center().x(), y)))
        app.processEvents()
    pump(app, 500)
    settle_fade(app, pv)
    say(f"        survived; repaints={rc.n} opacity={pv._legend_opacity:.3f} "
        f"hidden={pv._legend_hidden} painted={chip_visible_now(pv, app)}")
    rc.restore()
    return out


def phase_D(app, win, charts):
    """BREAK THE MAPPING: resize, pages, margins, narrow pane, dpr."""
    say("\nPHASE D - break the coordinate mapping")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview

    def check(tag, shots=False):
        pump(app, 400)
        lab = label_rect(pv)
        if lab is None:
            say(f"    {tag:34s} NO CHIP (legend_rect={pv._legend_rect})")
            return None
        true_r, dpr = true_chip_bbox(pv, app)
        if true_r is None:
            say(f"    {tag:34s} chip rect {lab} but NOTHING drawn")
            return None
        err = (true_r.left() - lab.left(), true_r.top() - lab.top(),
               true_r.right() - lab.right(), true_r.bottom() - lab.bottom())
        # does the real pointer hide it at the MEASURED centre?
        move_to_label(app, pv, true_r.center(), settle=60)
        settle_fade(app, pv)
        on = not chip_visible_now(pv, app)
        # …and 6 px outside the measured rect, must NOT hide it
        move_to_label(app, pv, QPoint(true_r.center().x(), true_r.top() - 8),
                      settle=60)
        settle_fade(app, pv)
        off = chip_visible_now(pv, app)
        say(f"    {tag:34s} rect={lab} measured={true_r} err={err} "
            f"hides-on-centre={on} stays-when-8px-above={off} dpr={dpr}")
        if shots:
            crop(pv._img_label,
                 (lab.x() - 20, lab.y() - 26, lab.width() + 40, lab.height() + 52),
                 f"D_{tag.replace(' ', '_').replace('/', '-')}")
        return err, on, off

    check("D1 default 1500x1000")
    for w, h in ((1100, 760), (900, 620), (1900, 1100), (700, 900)):
        win.resize(w, h)
        pump(app, 900)
        check(f"D2 window {w}x{h}")
    win.resize(1500, 1000)
    pump(app, 800)

    say("    D3 a NARROW pane (the elision fix)")
    for w in (760, 660, 600, 560):
        win.resize(w, 900)
        pump(app, 900)
        r = check(f"D3 window {w}x900", shots=True)
    win.resize(1500, 1000)
    pump(app, 900)

    say("    D4 a MULTI-PAGE chart, switching pages")
    mt2 = load_measured(app, win, charts["multi"])
    pv = mt2._preview
    say(f"        pages={len(pv._pages) if hasattr(pv, '_pages') else '?'} "
        f"current={pv._current} overlay pages={sorted(pv._patch_overlay)}")
    for pg in range(3):
        pv.show_page(pg)
        pump(app, 900)
        check(f"D4 page {pg + 1}")
    say("    D4b hover the chip on page 1, then switch page WITHOUT moving")
    lab = label_rect(pv)
    if lab is not None:
        pv.show_page(0)
        pump(app, 700)
        lab = label_rect(pv)
        move_to_label(app, pv, lab.center(), settle=120)
        settle_fade(app, pv)
        say(f"        on page 1, on the chip: hidden={pv._legend_hidden} "
            f"opacity={pv._legend_opacity:.2f} painted={chip_visible_now(pv, app)}")
        pv.show_page(1)
        pump(app, 900)
        settle_fade(app, pv)
        lab2 = label_rect(pv)
        inside = lab2.contains(pv._legend_pointer) if lab2 else None
        say(f"        after page 2: chip={lab2} pointer={pv._legend_pointer} "
            f"pointer-inside-chip={inside} hidden={pv._legend_hidden} "
            f"opacity={pv._legend_opacity:.2f} "
            f"painted={chip_visible_now(pv, app)}")
        crop(pv._img_label,
             (lab2.x() - 20, lab2.y() - 26, lab2.width() + 40, lab2.height() + 52),
             "D4b_page_switched_while_hovering")

    say("    D5 a chart with a 1 mm bottom margin (chip lands ON the patches)")
    mt3 = load_measured(app, win, charts["tight"])
    pv = mt3._preview
    check("D5 tight bottom margin", shots=True)
    lab = label_rect(pv)
    if lab is not None:
        move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 240),
                      settle=100)
        settle_fade(app, pv)
        crop(pv._img_label,
             (lab.x() - 20, lab.y() - 60, lab.width() + 40, lab.height() + 90),
             "D5a_tight_chip_over_patches")
        move_to_label(app, pv, lab.center(), settle=100)
        settle_fade(app, pv)
        crop(pv._img_label,
             (lab.x() - 20, lab.y() - 60, lab.width() + 40, lab.height() + 90),
             "D5b_tight_chip_hidden_patches_visible")
    say(f"    D6 devicePixelRatio of the preview = {pv.devicePixelRatioF()}")
    return None


def phase_E(app, win, charts):
    """The two fixes."""
    say("\nPHASE E - the two fixes")

    say("  E1 (a) is an empty _stripe_rects with overlay items REACHABLE?")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    say(f"      normal load: stripe_rects={len(pv._stripe_rects)} "
        f"page_stripe_rects={[len(x) for x in mt._page_stripe_rects]} "
        f"items={len(pv._patch_overlay.get(0, []))}")
    facts = charts["i1"]
    # The commit names three routes. Try the one the UI can actually take:
    # a sidecar whose page count does not match the loaded TIFFs.
    ch = facts["channels"]
    good = ch.read_text()
    d = json.loads(good)
    for pt in d["layout"]["patches"]:
        pt["page"] = pt.get("page", 0) + 1        # claim page 2 of a 1-page tif
    ch.write_text(json.dumps(d))
    try:
        mt = load_measured(app, win, facts)
        pv = mt._preview
        say(f"      sidecar page-count mismatch: stripe_rects="
            f"{len(pv._stripe_rects)} boxes={[len(b) for b in mt._patch_boxes]} "
            f"items={len(pv._patch_overlay.get(0, []))} legend={pv._legend_rect}")
    finally:
        ch.write_text(good)

    say("  E1b the SYNTHETIC form of the same state, on the real widget")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    lab_before = label_rect(pv)
    items = list(pv._patch_overlay.get(0, []))
    pv.set_stripe_rects([])
    pv._repaint_label()
    pump(app, 400)
    lab_after = label_rect(pv)
    say(f"      with strips  : {lab_before}")
    say(f"      strips empty : {lab_after}   (label h={pv._img_label.height()})")
    if lab_after is not None:
        bottoms = max(r.y() + r.height() for r, _e, _m, _w in items)
        _s, _ox, oy = pv._paint_geom
        say(f"      lowest patch bottom on screen = {oy + bottoms * _s:.0f}; "
            f"chip top = {lab_after.top()}")
        crop(pv._img_label,
             (lab_after.x() - 20, lab_after.y() - 40, lab_after.width() + 40,
              lab_after.height() + 70), "E1b_no_strip_geometry_chip_at_bottom")

    say("  E2 (b) does a chart swap still show the previous chart's patches?")
    mt = load_measured(app, win, charts["rect"])
    pv = mt._preview
    say(f"      chart 1 (rect): items={len(pv._patch_overlay.get(0, []))}")
    n_before = len(pv._patch_overlay.get(0, []))
    # a chart with NO measurement, loaded the way the tab does it
    plain = charts["tiny"]
    ti3 = plain["ti2"].with_suffix(".ti3")
    moved = ti3.with_suffix(".ti3.aside")
    if ti3.exists():
        shutil.move(ti3, moved)
    try:
        mt.set_ti1_path(plain["ti2"])
        pump(app, 2500)
        say(f"      chart 2 (tiny, unmeasured): items="
            f"{len(pv._patch_overlay.get(0, []))} legend={pv._legend_rect} "
            f"overlay box visible={not mt._m_overlay_cb.isHidden()}")
        shot(pv._img_label, "E2_second_chart_no_stale_patches",
             "chart 2 has no measurement: no colours from chart 1 may appear")
    finally:
        if moved.exists():
            shutil.move(moved, ti3)
    return None


def phase_F(app, win, charts):
    """Regressions: every other overlay, WITH the pointer on the chip."""
    say("\nPHASE F - the other overlays, with the pointer on the chip")
    mt = load_measured(app, win, charts["rect"])
    pv = mt._preview
    lab = label_rect(pv)
    if lab is None:
        say("    no chip; F cannot run")
        return
    boxes = mt._patch_boxes[0] if mt._patch_boxes else {}
    mid = None
    if boxes:
        xs = [b.center().x() for b in boxes.values()]
        ys = [b.center().y() for b in boxes.values()]
        mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        mid = min(boxes, key=lambda k: (boxes[k].center().x() - mx) ** 2
                  + (boxes[k].center().y() - my) ** 2)

    def snap(tag):
        pump(app, 300)
        return pv._img_label.grab().toImage()

    def differs(a, b):
        if a.size() != b.size():
            return -1
        n = 0
        for y in range(0, a.height(), 2):
            for x in range(0, a.width(), 2):
                if a.pixelColor(x, y) != b.pixelColor(x, y):
                    n += 1
        return n

    # baseline with the pointer AWAY
    move_to_label(app, pv, QPoint(lab.center().x(), max(2, lab.top() - 240)))
    settle_fade(app, pv)
    base_away = snap("away")

    features = []
    say("    F1 patch value tile (Show patch values on hover)")
    pv.set_show_patch_tile(True)
    pump(app, 200)
    if boxes and mid:
        _s, ox, oy = pv._paint_geom
        b = boxes[mid]
        pt = QPoint(int((b.center().x()) * _s + ox), int((b.center().y()) * _s + oy))
        move_to_label(app, pv, pt, settle=250)
        tile = getattr(pv, "_patch_tile", None)
        say(f"        tile shown over a patch = "
            f"{tile is not None and not tile.isHidden()}")
        shot(pv._img_label, "F1_patch_tile_over_patch")
    move_to_label(app, pv, lab.center(), settle=250)
    settle_fade(app, pv)
    tile = getattr(pv, "_patch_tile", None)
    say(f"        pointer on the CHIP: tile shown="
        f"{tile is not None and not tile.isHidden()} "
        f"chip painted={chip_visible_now(pv, app)}")
    shot(pv._img_label, "F2_pointer_on_chip_tile_state")
    pv.set_show_patch_tile(False)
    pump(app, 200)

    say("    F2 click-to-jump hover outline + strip hover frame")
    say(f"        patch_click_enabled={pv._patch_click_enabled} "
        f"stripe_click_enabled={pv._stripe_click_enabled} "
        f"hover_patch_loc={pv._hover_patch_loc!r} hover_stripe={pv._hover_stripe}")
    move_to_label(app, pv, lab.center(), settle=200)
    settle_fade(app, pv)
    say(f"        with the pointer on the chip: hover_patch_loc="
        f"{pv._hover_patch_loc!r} hover_stripe={pv._hover_stripe}")

    say("    F3 scan arrow band + bidirectional")
    pv.set_bidirectional(True)
    pv.highlight_stripe(0)
    pump(app, 400)
    lab_b = label_rect(pv)
    say(f"        bidir chip={lab_b} (was {lab})")
    shot(pv._img_label, "F3_bidir_arrow_and_chip")
    move_to_label(app, pv, lab_b.center(), settle=200)
    settle_fade(app, pv)
    shot(pv._img_label, "F3b_bidir_chip_hidden_arrow_still_there")
    say(f"        chip painted with pointer on it = {chip_visible_now(pv, app)}")
    pv.set_bidirectional(False)
    pv.highlight_stripe(-1)
    pump(app, 300)

    say("    F4 accent ring + CR30 aiming circles + warn rings")
    mt2 = load_measured(app, win, charts["hex"])
    pv2 = mt2._preview
    b2 = mt2._patch_boxes[0] if mt2._patch_boxes else {}
    if b2:
        xs = [b.center().x() for b in b2.values()]
        ys = [b.center().y() for b in b2.values()]
        mx, my = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        loc = min(b2, key=lambda k: (b2[k].center().x() - mx) ** 2
                  + (b2[k].center().y() - my) ** 2)
        mt2._on_patch_ready({"loc": loc})
        pump(app, 700)
        say(f"        armed {loc}: aim={pv2._aim_overlay} "
            f"body={pv2._aim_body_px:.1f} aperture={pv2._aim_aperture_px:.1f}")
        lab2 = label_rect(pv2)
        n_warn = sum(1 for _r, _e, _m, w in pv2._patch_overlay.get(0, []) if w)
        say(f"        warn-flagged patches on page 1 = {n_warn}")
        move_to_label(app, pv2, QPoint(lab2.center().x(), lab2.top() - 240),
                      settle=150)
        settle_fade(app, pv2)
        shot(pv2._img_label, "F4_hex_rings_chip_visible")
        move_to_label(app, pv2, lab2.center(), settle=150)
        settle_fade(app, pv2)
        shot(pv2._img_label, "F4b_hex_rings_chip_hidden")
        say(f"        chip painted with pointer on it = "
            f"{chip_visible_now(pv2, app)}")
    return None


def phase_G(app, win, charts):
    """Edge cases."""
    say("\nPHASE G - edge cases")
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 400)
    pv = mt._preview

    say("  G1 no chart at all")
    pv.clear()
    pump(app, 400)
    say(f"      legend_rect={pv._legend_rect} pixmap={pv._pixmap} "
        f"opacity={pv._legend_opacity}")

    say("  G2 a chart with NO measurement (no chip at all)")
    plain = charts["tiny"]
    ti3 = plain["ti2"].with_suffix(".ti3")
    moved = ti3.with_suffix(".ti3.aside")
    if ti3.exists():
        shutil.move(ti3, moved)
    try:
        mt.set_ti1_path(plain["ti2"])
        pump(app, 2500)
        say(f"      legend_rect={pv._legend_rect} "
            f"items={len(pv._patch_overlay.get(0, []))} "
            f"overlay box visible={not mt._m_overlay_cb.isHidden()}")
        shot(pv._img_label, "G2_unmeasured_chart_no_chip")
        say("      …and pointing where the chip WOULD be does nothing:")
        QTest.mouseMove(pv.window(),
                        label_to_window(pv, QPoint(pv._img_label.width() // 2,
                                                   pv._img_label.height() - 30)))
        pump(app, 300)
        say(f"      hidden={pv._legend_hidden} opacity={pv._legend_opacity}")
    finally:
        if moved.exists():
            shutil.move(moved, ti3)

    say("  G3 the three overlay-mode wordings")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    for mode in ("split", "expected", "measured"):
        pv.set_overlay_mode(mode)
        pump(app, 500)
        lab = label_rect(pv)
        true_r, _d = true_chip_bbox(pv, app)
        say(f"      {mode:9s} rect={lab} measured={true_r}")
        if lab:
            crop(pv._img_label,
                 (lab.x() - 14, lab.y() - 14, lab.width() + 28, lab.height() + 28),
                 f"G3_wording_{mode}")
            move_to_label(app, pv, lab.center(), settle=120)
            settle_fade(app, pv)
            say(f"                hides on hover = {not chip_visible_now(pv, app)}")
            move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 200),
                          settle=120)
            settle_fade(app, pv)
    pv.set_overlay_mode("split")
    pump(app, 300)

    say("  G4 window loses focus while hovering")
    lab = label_rect(pv)
    move_to_label(app, pv, lab.center(), settle=150)
    settle_fade(app, pv)
    say(f"      on the chip: painted={chip_visible_now(pv, app)}")
    win.setWindowState(Qt.WindowState.WindowMinimized)
    pump(app, 900)
    win.setWindowState(Qt.WindowState.WindowNoState)
    win.raise_(); win.activateWindow()
    pump(app, 1200)
    say(f"      after minimise/restore: ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.2f} "
        f"painted={chip_visible_now(pv, app)}")
    shot(win, "G4_after_minimise_restore")

    say("  G5 the widget is HIDDEN while the pointer is on the chip (tab switch)")
    lab = label_rect(pv)
    move_to_label(app, pv, lab.center(), settle=150)
    settle_fade(app, pv)
    say(f"      on the chip: opacity={pv._legend_opacity:.2f}")
    win._tabs.setCurrentWidget(win._tab_chart)
    pump(app, 800)
    win._tabs.setCurrentWidget(mt)
    pump(app, 1200)
    settle_fade(app, pv)
    say(f"      back on Measure: ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.2f} "
        f"painted={chip_visible_now(pv, app)}")
    shot(pv._img_label, "G5_after_tab_switch_back")

    say("  G6 keyboard-only: is there ANY non-mouse way to get the chip out "
        "of the way?")
    say(f"      focusPolicy={pv.focusPolicy()} "
        f"label focusPolicy={pv._img_label.focusPolicy()}")
    say("      (searched the class for a keyboard/menu route -- see the report)")
    return None


def phase_H(app, win, charts):
    """The state machine under fast movement -- the C4 desync."""
    say("\nPHASE H - the fade state machine under fast movement")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    lab = label_rect(pv)
    rc = RepaintCounter(pv)

    def state(tag):
        pump(app, 60)
        painted = chip_visible_now(pv, app)
        ok = (pv._legend_hidden != painted)
        say(f"      {tag:44s} hidden={pv._legend_hidden!s:5s} "
            f"opacity={pv._legend_opacity:.3f} painted={painted!s:5s} "
            f"{'OK' if ok else '*** DISAGREE ***'}")
        return ok

    say("  H1 a realistic FAST sweep across the chip (8 ms per move, ~1000 px/s)")
    bad = 0
    for trial in range(6):
        move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 40),
                      settle=200)
        settle_fade(app, pv)
        for y in range(lab.top() - 40, lab.bottom() + 40, 8):
            QTest.mouseMove(pv.window(),
                            label_to_window(pv, QPoint(lab.center().x(), y)))
            pump(app, 8)
        # end BELOW the chip -> must be visible
        pump(app, 400)
        settle_fade(app, pv)
        if not state(f"trial {trial}: swept THROUGH, ended below"):
            bad += 1
    say(f"      disagreements after a sweep-through: {bad}/6")

    say("  H2 sweep IN and STOP on the chip")
    bad = 0
    for trial in range(6):
        move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 60),
                      settle=200)
        settle_fade(app, pv)
        for y in range(lab.top() - 60, lab.center().y(), 6):
            QTest.mouseMove(pv.window(),
                            label_to_window(pv, QPoint(lab.center().x(), y)))
            pump(app, 6)
        pump(app, 500)
        settle_fade(app, pv)
        if not state(f"trial {trial}: swept in and stopped ON the chip"):
            bad += 1
    say(f"      disagreements after stopping on the chip: {bad}/6")

    say("  H3 the harness's own saw (no waiting at all) -- 120 crossings")
    for rep in range(3):
        for i in range(120):
            y = lab.top() - 4 if i % 2 == 0 else lab.top() + 6
            QTest.mouseMove(pv.window(),
                            label_to_window(pv, QPoint(lab.center().x(), y)))
            app.processEvents()
        pump(app, 600)
        settle_fade(app, pv)
        state(f"saw #{rep}: last move was INSIDE the chip")
        crop(pv._img_label,
             (lab.x() - 20, lab.y() - 26, lab.width() + 40, lab.height() + 52),
             f"H3_{rep}_after_fast_saw",
             note=f"pointer on the chip; opacity={pv._legend_opacity:.2f}")

    say("  H4 does it RECOVER? move out, then back in")
    move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 120), settle=300)
    settle_fade(app, pv)
    state("moved well clear")
    move_to_label(app, pv, lab.center(), settle=300)
    settle_fade(app, pv)
    state("moved back onto the chip")

    say("  H5 the chip is RE-PLACED while hidden and no longer under the pointer")
    move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 120), settle=250)
    settle_fade(app, pv)
    pv.set_overlay_mode("measured")     # the widest wording
    pump(app, 400)
    lab_w = label_rect(pv)
    move_to_label(app, pv, QPoint(lab_w.right() - 6, lab_w.center().y()),
                  settle=250)
    settle_fade(app, pv)
    state("on the wide chip's right end")
    pv.set_overlay_mode("split")        # 70 % narrower -- pointer now off it
    pump(app, 600)
    settle_fade(app, pv)
    lab_n = label_rect(pv)
    inside = lab_n.contains(pv._legend_pointer) if lab_n else None
    say(f"      narrow chip={lab_n} pointer={pv._legend_pointer} "
        f"pointer-inside={inside}")
    state("wording narrowed; the pointer is no longer on the chip")
    crop(pv._img_label,
         (lab_n.x() - 30, lab_n.y() - 26, lab_n.width() + 120, lab_n.height() + 52),
         "H5_chip_narrowed_out_from_under_the_pointer")

    say("  H6 clear() while the chip is hidden, then a new chart")
    lab = label_rect(pv)
    move_to_label(app, pv, lab.center(), settle=250)
    settle_fade(app, pv)
    state("hidden, about to clear()")
    pv.clear()
    pump(app, 300)
    say(f"      after clear(): ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.3f} "
        f"rect={pv._legend_rect}")
    mt2 = load_measured(app, win, charts["rect"])
    pv2 = mt2._preview
    pump(app, 600)
    say(f"      new chart loaded: same widget={pv2 is pv} rect={pv2._legend_rect} "
        f"opacity={pv2._legend_opacity:.3f} hidden={pv2._legend_hidden} "
        f"painted={chip_visible_now(pv2, app)}")
    lab2 = label_rect(pv2)
    if lab2:
        crop(pv2._img_label,
             (lab2.x() - 20, lab2.y() - 26, lab2.width() + 40, lab2.height() + 52),
             "H6_new_chart_after_clear_while_hidden",
             note=f"opacity={pv2._legend_opacity:.2f}")
    rc.restore()
    return None


def phase_I(app, win, charts):
    """The two state-machine faults, isolated and given a user journey."""
    say("\nPHASE I - isolating the two faults")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    lab = label_rect(pv)

    def report(tag):
        pump(app, 60)
        painted = chip_visible_now(pv, app)
        l = label_rect(pv)
        on_chip = l.contains(pv._legend_pointer) if (
            l is not None and pv._legend_pointer is not None) else None
        wrong = (on_chip is not None) and (painted == on_chip)
        say(f"      {tag:52s} pointer-on-chip={on_chip!s:5s} "
            f"painted={painted!s:5s} hidden={pv._legend_hidden!s:5s} "
            f"opacity={pv._legend_opacity:.3f} "
            f"{'*** WRONG ***' if wrong else 'ok'}")
        return wrong

    say("  I1 FLICK OFF AND STRAIGHT BACK ON, at a range of dwell times")
    say("     (the fade is %d ms; _start_legend_fade returns early when the "
        "opacity already equals the new target)" % pv.LEGEND_FADE_MS)
    outside = QPoint(lab.center().x(), lab.top() - 10)
    bad = []
    for dwell in (0, 2, 5, 8, 12, 18, 25, 40, 60, 90, 140):
        # settle well clear first, then ON the chip -- a full recovery cycle,
        # because the previous iteration may have left the state machine stuck
        move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 200),
                      settle=250)
        settle_fade(app, pv)
        move_to_label(app, pv, lab.center(), settle=250)
        settle_fade(app, pv)
        if chip_visible_now(pv, app):
            say(f"      dwell {dwell:3d}: SETUP still shows the chip -- the "
                "previous iteration left it stuck; doing a second cycle")
            move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 200),
                          settle=250)
            settle_fade(app, pv)
            move_to_label(app, pv, lab.center(), settle=250)
            settle_fade(app, pv)
        # flick out …
        QTest.mouseMove(pv.window(), label_to_window(pv, outside))
        pump(app, max(1, dwell))
        # … and straight back in
        QTest.mouseMove(pv.window(), label_to_window(pv, lab.center()))
        pump(app, 500)
        settle_fade(app, pv)
        w = report(f"dwell {dwell:3d} ms off the chip, then back on")
        if w:
            bad.append(dwell)
            crop(pv._img_label,
                 (lab.x() - 20, lab.y() - 26, lab.width() + 40, lab.height() + 52),
                 f"I1_flick_dwell_{dwell}ms_chip_still_there",
                 note="pointer IS on the chip and the chip is still drawn")
    say(f"      dwell times that leave the chip visible under the pointer: {bad}")

    say("  I2 the same, driven at the state machine to show the mechanism")
    for dwell in (0, 3, 6, 10, 20):
        move_to_label(app, pv, QPoint(lab.center().x(), lab.top() - 200),
                      settle=250)
        settle_fade(app, pv)
        move_to_label(app, pv, lab.center(), settle=250)
        settle_fade(app, pv)
        pv._apply_legend_pointer(QPoint(outside))
        pump(app, dwell)
        op_at_switch = pv._legend_opacity
        pv._apply_legend_pointer(QPoint(lab.center()))
        anim = pv._legend_fade
        say(f"      dwell {dwell:3d}: opacity when re-entering = "
            f"{op_at_switch:.4f}; guard 'abs(op-0)<0.01' -> "
            f"{abs(op_at_switch) < 0.01}; animation end value now "
            f"{anim.endValue() if anim else None}")
        pump(app, 500)
        settle_fade(app, pv)
        report(f"          settled")

    say("  I3 THE WINDOW IS RESIZED WHILE THE POINTER RESTS ON THE CHIP")
    say("     (a tiling shortcut, full-screen, or Cmd-drag: the pointer never "
        "leaves the preview, so there is no leaveEvent)")
    win.resize(1500, 1000)
    pump(app, 700)
    lab = label_rect(pv)
    move_to_label(app, pv, QPoint(lab.right() - 8, lab.center().y()), settle=250)
    settle_fade(app, pv)
    report("on the chip's right end, before the resize")
    crop(pv._img_label,
         (lab.x() - 20, lab.y() - 26, lab.width() + 60, lab.height() + 52),
         "I3a_before_resize_chip_hidden")
    win.resize(1050, 1000)             # no mouse event at all
    pump(app, 1200)
    settle_fade(app, pv)
    lab2 = label_rect(pv)
    say(f"      chip moved {lab} -> {lab2}; pointer still {pv._legend_pointer}")
    w = report("after the resize, pointer no longer on the chip")
    if lab2:
        crop(pv._img_label,
             (max(0, lab2.x() - 20), lab2.y() - 26, lab2.width() + 60,
              lab2.height() + 52),
             "I3b_after_resize_chip_missing",
             note="the pointer is NOT on the chip and the chip is gone")
    say("      …and does it come back on its own? 3 s, no mouse:")
    pump(app, 3000)
    report("3 s later, still no mouse movement")
    say("      …and does moving the pointer (still off the chip) bring it back?")
    move_to_label(app, pv, QPoint(20, 20), settle=300)
    settle_fade(app, pv)
    report("pointer moved elsewhere in the preview")
    win.resize(1500, 1000)
    pump(app, 800)

    say("  I4 the same shape, via a PAGE SWITCH with no pointer movement")
    mt2 = load_measured(app, win, charts["multi"])
    pv2 = mt2._preview
    pv2.show_page(0)
    pump(app, 900)
    l0 = label_rect(pv2)
    if l0 is not None:
        QTest.mouseMove(pv2.window(), label_to_window(pv2, l0.center()))
        pump(app, 300)
        settle_fade(app, pv2)
        say(f"      page 1, on the chip: painted={chip_visible_now(pv2, app)} "
            f"opacity={pv2._legend_opacity:.2f}")
        pv2.show_page(1)               # no mouse event
        pump(app, 1200)
        settle_fade(app, pv2)
        l1 = label_rect(pv2)
        on = l1.contains(pv2._legend_pointer) if l1 else None
        say(f"      page 2: chip={l1} pointer={pv2._legend_pointer} "
            f"pointer-on-chip={on} painted={chip_visible_now(pv2, app)} "
            f"opacity={pv2._legend_opacity:.2f}")
    return None


def opacity_trace(app, pv, ms, step=4):
    """Sample _legend_opacity every `step` ms for `ms`, running the loop."""
    out = []
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        out.append((round((time.monotonic() * 1000) % 100000, 1),
                    pv._legend_opacity))
        time.sleep(step / 1000.0)
    return out


def phase_J(app, win, charts):
    """The fade, driven at the STATE MACHINE -- no cursor, so nothing a human
    does with the mouse can contaminate it."""
    say("\nPHASE J - the fade, cursor-free (_apply_legend_pointer)")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    lab = label_rect(pv)
    say(f"    chip (label coords) = {lab}  fade = {pv.LEGEND_FADE_MS} ms")

    def reset(app, pv):
        """Put the chip back to fully visible, whatever state it is in."""
        pv._legend_fade and pv._legend_fade.stop()
        pv._legend_opacity = 1.0
        pv._legend_hidden = False
        pv._legend_pointer = None
        pv._repaint_label()
        pump(app, 80)

    say("  J1 SLOW APPROACH, 1 px at a time, each of the four edges")
    say("     (flicker now = the opacity turning round; it must not oscillate)")
    N = 14
    edges = {
        "top":    [QPoint(lab.center().x(), lab.top() - N + i) for i in range(2 * N)],
        "bottom": [QPoint(lab.center().x(), lab.bottom() + N - i) for i in range(2 * N)],
        "left":   [QPoint(lab.left() - N + i, lab.center().y()) for i in range(2 * N)],
        "right":  [QPoint(lab.right() + N - i, lab.center().y()) for i in range(2 * N)],
    }
    for edge, pts in edges.items():
        for direction, seq in (("in", pts), ("out", list(reversed(pts)))):
            reset(app, pv)
            if direction == "out":       # start hidden
                pv._apply_legend_pointer(seq[0])
                pump(app, 400)
            ops, starts = [], 0
            prev_end = pv._legend_fade.endValue() if pv._legend_fade else None
            for q in seq:
                pv._apply_legend_pointer(q)
                e = pv._legend_fade.endValue() if pv._legend_fade else None
                if e != prev_end:
                    starts += 1
                    prev_end = e
                pump(app, 260)           # > the 110 ms fade
                ops.append(pv._legend_opacity)
            turns = sum(1 for a, b in zip(ops, ops[1:]) if abs(a - b) > 0.5)
            say(f"    {edge:6s} {direction:3s}: "
                f"{' '.join(f'{o:.1f}' for o in ops)}")
            say(f"              turn-rounds={turns} (1 = clean) "
                f"fade-retargets={starts}")

    say("  J2 THE SEGFAULT ATTACK: reverse inside the running animation")
    reset(app, pv)
    inside, outside = lab.center(), QPoint(lab.center().x(), lab.top() - 10)
    for burst, gap in ((400, 0), (400, 2), (400, 5), (200, 12), (200, 30)):
        for i in range(burst):
            pv._apply_legend_pointer(inside if i % 2 == 0 else outside)
            app.processEvents()
            if gap:
                time.sleep(gap / 1000.0)
        pump(app, 400)
        say(f"      survived {burst} reversals at {gap} ms: "
            f"opacity={pv._legend_opacity:.3f} hidden={pv._legend_hidden} "
            f"anim={pv._legend_fade}")
    say("      …and reversing from INSIDE the valueChanged callback itself")
    reset(app, pv)
    depth = {"n": 0}
    orig = pv._on_legend_fade_step

    def reentrant(value):
        orig(value)
        depth["n"] += 1
        if depth["n"] < 60:
            pv._apply_legend_pointer(outside if depth["n"] % 2 else inside)
    pv._on_legend_fade_step = reentrant
    try:
        pv._legend_fade.valueChanged.disconnect()
        pv._legend_fade.valueChanged.connect(reentrant)
    except Exception as e:      # noqa: BLE001
        say(f"      (could not rewire the signal: {e})")
    pv._apply_legend_pointer(inside)
    pump(app, 1500)
    say(f"      survived {depth['n']} re-entrant reversals; "
        f"opacity={pv._legend_opacity:.3f}")
    try:
        pv._legend_fade.valueChanged.disconnect()
        pv._legend_fade.valueChanged.connect(pv._on_legend_fade_step)
    except Exception:
        pass
    del pv._on_legend_fade_step

    say("  J3 REVERSING FROM A SETTLED STATE (the guard's blind spot)")
    for tag, settle_ms in (("settled (opacity exactly 0)", 500),
                           ("mid-fade (opacity strictly between)", 40)):
        reset(app, pv)
        pv._apply_legend_pointer(inside)
        pump(app, settle_ms)
        op0 = pv._legend_opacity
        pv._apply_legend_pointer(outside)      # leave
        pump(app, 3)
        op1 = pv._legend_opacity
        end1 = pv._legend_fade.endValue()
        pv._apply_legend_pointer(inside)       # straight back on
        end2 = pv._legend_fade.endValue()
        guard = abs(pv._legend_opacity - 0.0) < 0.01
        pump(app, 600)
        say(f"      {tag}")
        say(f"        opacity at leave={op0:.4f} -> {op1:.4f}; "
            f"anim end after leave={end1}; guard skipped the re-hide="
            f"{guard}; anim end after re-enter={end2}")
        say(f"        SETTLED: opacity={pv._legend_opacity:.3f} "
            f"hidden={pv._legend_hidden} painted={chip_visible_now(pv, app)} "
            f"-> {'*** WRONG: the chip is drawn under the pointer ***' if pv._legend_opacity > 0.5 else 'ok'}")

    say("  J4 does the WRONG state recover on the next move?")
    # leave it in the broken state, then move around the chip
    reset(app, pv)
    pv._apply_legend_pointer(inside)
    pump(app, 500)
    pv._apply_legend_pointer(outside)
    pump(app, 3)
    pv._apply_legend_pointer(inside)
    pump(app, 600)
    say(f"      broken state: opacity={pv._legend_opacity:.3f} "
        f"hidden={pv._legend_hidden}")
    for q, tag in ((QPoint(inside.x() + 4, inside.y()), "nudge, still ON the chip"),
                   (QPoint(inside.x() + 8, inside.y()), "nudge again, still ON"),
                   (outside, "move OFF the chip"),
                   (inside, "move back ON the chip")):
        pv._apply_legend_pointer(q)
        pump(app, 500)
        say(f"        {tag:28s} opacity={pv._legend_opacity:.3f} "
            f"hidden={pv._legend_hidden}")

    say("  J5 how long does the fade ACTUALLY take, and what shape?")
    reset(app, pv)
    t0 = time.monotonic()
    pv._apply_legend_pointer(inside)
    tr = opacity_trace(app, pv, 400, step=3)
    first = next((i for i, (_t, v) in enumerate(tr) if v < 0.999), None)
    last = next((i for i, (_t, v) in enumerate(tr) if v < 0.005), None)
    say(f"      samples: {' '.join(f'{v:.2f}' for _t, v in tr[:40])}")
    if first is not None and last is not None:
        say(f"      first movement at sample {first}, fully gone at {last} "
            f"(~{(last - first) * 3} ms of visible movement, "
            f"{last * 3} ms after the pointer arrived)")
    reset(app, pv)
    return None


def phase_K(app, win, charts):
    """The one thing that needs a REAL cursor: the label mapping. Guarded, so a
    move that never arrived cannot be mistaken for a chip that refused."""
    say("\nPHASE K - the mapping, with a real cursor and a delivery guard")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview

    def guarded_move(pt, tag):
        pv._legend_pointer = None
        for attempt in range(6):
            QTest.mouseMove(pv.window(), label_to_window(pv, pt))
            pump(app, 120)
            got = pv._legend_pointer
            if got is not None and abs(got.x() - pt.x()) <= 2 \
                    and abs(got.y() - pt.y()) <= 2:
                return got
        say(f"      !! move NOT DELIVERED for {tag}: sent {pt} got "
            f"{pv._legend_pointer}; active={win.isActiveWindow()} "
            f"-- RESULT DISCARDED")
        return None

    def check(tag):
        lab = label_rect(pv)
        if lab is None:
            say(f"    {tag}: no chip")
            return
        true_r, dpr = true_chip_bbox(pv, app)
        if true_r is None:
            say(f"    {tag}: chip rect {lab} but nothing drawn")
            return
        err = (true_r.left() - lab.left(), true_r.top() - lab.top(),
               true_r.right() - lab.right(), true_r.bottom() - lab.bottom())
        got = guarded_move(true_r.center(), tag + " centre")
        on = None
        if got is not None:
            settle_fade(app, pv)
            on = not chip_visible_now(pv, app)
        pv._legend_fade and pv._legend_fade.stop()
        pv._legend_opacity = 1.0
        pv._legend_hidden = False
        pv._repaint_label()
        got2 = guarded_move(QPoint(true_r.center().x(), true_r.top() - 10),
                            tag + " 10px above")
        off = None
        if got2 is not None:
            settle_fade(app, pv)
            off = chip_visible_now(pv, app)
        say(f"    {tag:30s} rect={lab} measured={true_r} err={err} dpr={dpr} "
            f"hides-at-centre={on} stays-10px-above={off} "
            f"active={win.isActiveWindow()}")

    win.raise_(); win.activateWindow()
    pump(app, 600)
    check("K1 1500x1000")
    for w, h in ((1100, 760), (900, 620), (1900, 1100)):
        win.resize(w, h)
        pump(app, 900)
        check(f"K2 {w}x{h}")
    win.resize(1500, 1000)
    pump(app, 800)
    mt2 = load_measured(app, win, charts["multi"])
    pv = mt2._preview
    for pg in range(3):
        pv.show_page(pg)
        pump(app, 900)
        check(f"K3 multipage page {pg + 1}")
    return None


def phase_L(app, win, charts):
    """Reachability of the two fixes' preconditions, through the real tab."""
    say("\nPHASE L - are the two fixes' preconditions reachable?")
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 400)

    say("  L1 a sidecar with PATCHES but NO STRIPS")
    say("     (the shape workflow/grid_layout_from_render.derive_grid_layout "
        "returns -- it has no 'strips' key at all)")
    facts = charts["i1"]
    ch = facts["channels"]
    good = ch.read_text()
    d = json.loads(good)
    had = len(d["layout"].get("strips") or [])
    d["layout"].pop("strips", None)
    ch.write_text(json.dumps(d))
    try:
        mt2 = load_measured(app, win, facts)
        pv = mt2._preview
        say(f"      sidecar had {had} strips, now none")
        say(f"      -> preview stripe_rects={len(pv._stripe_rects)} "
            f"patch_boxes={[len(b) for b in mt2._patch_boxes]} "
            f"overlay items={len(pv._patch_overlay.get(0, []))}")
        lab = label_rect(pv)
        items = pv._patch_overlay.get(0, [])
        if lab is not None and items:
            _sc, _ox, oy = pv._paint_geom
            low = oy + max(r.y() + r.height() for r, *_ in items) * _sc
            say(f"      chip at y={lab.top()} of label h="
                f"{pv._img_label.height()}; lowest patch bottom={low:.0f}; "
                f"top of sheet={oy:.0f}")
            say(f"      VERDICT: chip is "
                f"{'BELOW the patches (the fix working)' if lab.top() >= low - 4 else 'ON the patches'}")
            crop(pv._img_label,
                 (max(0, lab.x() - 20), lab.y() - 40, lab.width() + 40,
                  lab.height() + 70), "L1_no_strips_sidecar_chip_below_patches")
            shot(pv._img_label, "L1b_no_strips_whole_sheet")
    finally:
        ch.write_text(good)

    say("  L2 clear() on the SAME chart -- the one route where "
        "_discard_stale_overlay bows out")
    mt3 = load_measured(app, win, charts["rect"])
    pv = mt3._preview
    n0 = len(pv._patch_overlay.get(0, []))
    ident_before = mt3._chart_identity()
    say(f"      overlay items before = {n0}; chart identity = "
        f"{ident_before[0].split('/')[-1] if ident_before else None}")
    # the tab's own no-TIFF branch, on the SAME chart
    tiffs_before = list(mt3._tiff_pages)
    hidden = []
    for t in tiffs_before:
        h = Path(str(t) + ".hidden49")
        shutil.move(t, h)
        hidden.append((h, t))
    try:
        mt3._try_load_tiffs(mt3._ti1_path)
        pump(app, 1200)
        say(f"      after _try_load_tiffs with the TIFF gone: items="
            f"{len(pv._patch_overlay.get(0, []))} "
            f"patch_info={len(pv._patch_info)} legend={pv._legend_rect} "
            f"(identity unchanged, so _discard_stale_overlay returns early: "
            f"{mt3._chart_identity() == ident_before})")
    finally:
        for h, t in hidden:
            shutil.move(h, t)
    mt3._try_load_tiffs(mt3._ti1_path)
    pump(app, 1500)
    say(f"      TIFF back: items={len(pv._patch_overlay.get(0, []))} "
        f"legend={pv._legend_rect}")
    shot(pv._img_label, "L2_after_clear_same_chart",
         "the TIFF was removed and restored; no readings may be painted")

    say("  L3 keyboard / touch")
    say(f"      TiffPreview focusPolicy={pv.focusPolicy()} "
        f"label={pv._img_label.focusPolicy()}")
    say(f"      attribute WA_AcceptTouchEvents={pv.testAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)}")
    say("      (a keyboard-only or touch user never generates a mouse move, so "
        "the chip can never be asked to move -- see the report)")
    return None


def phase_M(app, win, charts):
    """Edge cases, cursor-free (state driven through _apply_legend_pointer)."""
    say("\nPHASE M - edge cases, cursor-free")
    mt = win._tab_measure
    win._tabs.setCurrentWidget(mt)
    pump(app, 400)
    pv = mt._preview

    say("  M1 no chart at all")
    pv.clear()
    pump(app, 500)
    say(f"      legend_rect={pv._legend_rect} pixmap={pv._pixmap} "
        f"opacity={pv._legend_opacity} hidden={pv._legend_hidden}")
    pv._apply_legend_pointer(QPoint(300, 300))
    pump(app, 300)
    say(f"      pointing at the empty pane: hidden={pv._legend_hidden} "
        f"opacity={pv._legend_opacity}")
    shot(pv._img_label, "M1_no_chart")

    say("  M2 a chart with NO measurement")
    plain = charts["tiny"]
    ti3 = plain["ti2"].with_suffix(".ti3")
    moved = ti3.with_suffix(".ti3.aside")
    if ti3.exists():
        shutil.move(ti3, moved)
    try:
        mt.set_ti1_path(plain["ti2"])
        pump(app, 2500)
        say(f"      legend_rect={pv._legend_rect} "
            f"items={len(pv._patch_overlay.get(0, []))} "
            f"overlay box visible={not mt._m_overlay_cb.isHidden()}")
        shot(pv._img_label, "M2_unmeasured_chart_no_chip")
    finally:
        if moved.exists():
            shutil.move(moved, ti3)

    say("  M3 a chart whose patches run to the bottom edge (1 mm margin):")
    say("     the chip's FALLBACK position, resting on the last row")
    mt = load_measured(app, win, charts["tight"])
    pv = mt._preview
    lab = label_rect(pv)
    items = pv._patch_overlay.get(0, [])
    _sc, _ox, oy = pv._paint_geom
    low = oy + max(r.y() + r.height() for r, *_ in items) * _sc
    img_b = oy + pv._pixmap.height() * _sc
    say(f"      chip={lab}; lowest patch bottom={low:.0f}; "
        f"paper bottom={img_b:.0f}; chip sits "
        f"{'ON the last row' if lab.top() < low else 'in the bottom margin'}")
    box = (max(0, lab.x() - 20), lab.y() - 70, lab.width() + 40, lab.height() + 100)
    pv._legend_opacity = 1.0; pv._repaint_label(); pump(app, 200)
    crop(pv._img_label, box, "M3a_tight_margin_chip_over_patches",
         note="the complaint: the chip covers patches")
    pv._apply_legend_pointer(lab.center())
    pump(app, 500)
    crop(pv._img_label, box, "M3b_tight_margin_chip_hidden",
         note="pointing at it: the patches underneath are readable")
    pv._apply_legend_pointer(None)
    pump(app, 400)

    say("  M4 the three wordings, and their widths")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview
    for mode in ("split", "expected", "measured"):
        pv.set_overlay_mode(mode)
        pump(app, 500)
        l = label_rect(pv)
        say(f"      {mode:9s} chip={l}  width={l.width() if l else None}")
        if l:
            crop(pv._img_label,
                 (max(0, l.x() - 12), l.y() - 12, l.width() + 24, l.height() + 24),
                 f"M4_wording_{mode}")
            pv._apply_legend_pointer(l.center())
            pump(app, 400)
            say(f"                hides on hover: opacity={pv._legend_opacity:.2f}")
            pv._apply_legend_pointer(None)
            pump(app, 300)
    pv.set_overlay_mode("split")
    pump(app, 400)

    say("  M5 the widget is HIDDEN while the chip is hidden (a tab switch)")
    lab = label_rect(pv)
    pv._apply_legend_pointer(lab.center())
    pump(app, 400)
    say(f"      before: opacity={pv._legend_opacity:.2f} "
        f"hidden={pv._legend_hidden}")
    win._tabs.setCurrentWidget(win._tab_chart)
    pump(app, 900)
    win._tabs.setCurrentWidget(mt)
    pump(app, 1400)
    say(f"      back on Measure: ptr={pv._legend_pointer} "
        f"hidden={pv._legend_hidden} opacity={pv._legend_opacity:.2f}")
    shot(pv._img_label, "M5_after_tab_switch_back")

    say("  M6 minimise and restore while the chip is hidden")
    lab = label_rect(pv)
    pv._apply_legend_pointer(lab.center())
    pump(app, 400)
    win.setWindowState(Qt.WindowState.WindowMinimized)
    pump(app, 1000)
    win.setWindowState(Qt.WindowState.WindowNoState)
    win.raise_()
    pump(app, 1400)
    say(f"      after: ptr={pv._legend_pointer} hidden={pv._legend_hidden} "
        f"opacity={pv._legend_opacity:.2f}")
    shot(win, "M6_after_minimise_restore")

    say("  M7 what the whole window looks like, chip visible vs hidden")
    mt = load_measured(app, win, charts["tight"])
    pv = mt._preview
    pv._legend_opacity = 1.0
    pv._legend_hidden = False
    pv._legend_pointer = None
    pv._repaint_label()
    pump(app, 500)
    shot(win, "M7a_window_chip_visible")
    lab = label_rect(pv)
    pv._apply_legend_pointer(lab.center())
    pump(app, 500)
    shot(win, "M7b_window_chip_hidden")
    pv._apply_legend_pointer(None)
    pump(app, 400)
    return None


def mark_and_save(pv, box, ptr, name, note=""):
    """Grab the label, crop, draw a HARNESS-DRAWN crosshair where the pointer
    is, and save at 3x. The crosshair is added by this script, not by the app."""
    from PIL import Image, ImageDraw
    SHOTS.mkdir(parents=True, exist_ok=True)
    im = pv._img_label.grab().toImage()
    dpr = im.devicePixelRatio() or 1.0
    tmp = SHOTS / ("_tmp_" + name + ".png")
    im.save(str(tmp))
    pil = Image.open(tmp).convert("RGB")
    x, y, w, h = [int(v * dpr) for v in box]
    x = max(0, x); y = max(0, y)
    w = min(w, pil.width - x); h = min(h, pil.height - y)
    sub = pil.crop((x, y, x + w, y + h)).resize((w * 3, h * 3), Image.NEAREST)
    d = ImageDraw.Draw(sub)
    if ptr is not None:
        px = int((ptr.x() * dpr - x) * 3)
        py = int((ptr.y() * dpr - y) * 3)
        for wdt, col in ((11, (255, 255, 255)), (5, (255, 30, 30))):
            d.line([(px - 60, py), (px + 60, py)], fill=col, width=wdt)
            d.line([(px, py - 60), (px, py + 60)], fill=col, width=wdt)
        d.ellipse([px - 26, py - 26, px + 26, py + 26],
                  outline=(255, 255, 255), width=9)
        d.ellipse([px - 26, py - 26, px + 26, py + 26],
                  outline=(255, 30, 30), width=4)
    sub.save(SHOTS / f"{name}.png")
    tmp.unlink(missing_ok=True)
    say(f"    saved {name}.png   {note}")


def phase_N(app, win, charts):
    """Clean, CURSOR-FREE proof shots of the three faults."""
    say("\nPHASE N - proof shots of the faults, cursor-free")
    mt = load_measured(app, win, charts["i1"])
    pv = mt._preview

    def reset():
        if pv._legend_fade is not None:
            pv._legend_fade.stop()
        pv._legend_opacity = 1.0
        pv._legend_hidden = False
        pv._legend_pointer = None
        pv._repaint_label()
        pump(app, 150)

    lab = label_rect(pv)
    box = (max(0, lab.x() - 40), lab.y() - 40, lab.width() + 80, lab.height() + 80)

    say("  N0 the fade, frame by frame (cursor-free)")
    reset()
    mark_and_save(pv, box, None, "N0_0_fade_before", "opacity 1.00")
    pv._apply_legend_pointer(lab.center())
    t0 = time.monotonic()
    wanted = [0.85, 0.6, 0.35, 0.15, 0.0]
    i = 0
    while wanted and time.monotonic() - t0 < 1.0:
        app.processEvents()
        if pv._legend_opacity <= wanted[0]:
            i += 1
            mark_and_save(pv, box, lab.center(),
                          f"N0_{i}_fade_opacity_{pv._legend_opacity:.2f}"
                          .replace(".", "p", 1).replace("p", ".", 0),
                          f"{int((time.monotonic()-t0)*1000)} ms after the "
                          f"pointer arrived, opacity {pv._legend_opacity:.2f}")
            wanted.pop(0)
        time.sleep(0.002)
    reset()

    say("  N1 FAULT 1 -- flick off the chip and straight back on")
    inside = lab.center()
    outside = QPoint(lab.center().x(), lab.top() - 12)
    pv._apply_legend_pointer(inside)
    pump(app, 400)
    mark_and_save(pv, box, inside, "N1a_pointing_at_it_chip_gone",
                  f"correct: opacity {pv._legend_opacity:.2f}")
    pv._apply_legend_pointer(outside)
    pv._apply_legend_pointer(inside)
    pump(app, 600)
    mark_and_save(pv, box, inside, "N1b_FAULT_flicked_off_and_back_chip_returns",
                  f"FAULT: the pointer is on the chip and opacity is "
                  f"{pv._legend_opacity:.2f}")
    say(f"      opacity={pv._legend_opacity:.3f} hidden={pv._legend_hidden}")
    for tag in ("nudge on the chip", "nudge again"):
        pv._apply_legend_pointer(QPoint(inside.x() + 5, inside.y()))
        pump(app, 400)
        say(f"      {tag}: opacity={pv._legend_opacity:.3f}")
    mark_and_save(pv, box, QPoint(inside.x() + 5, inside.y()),
                  "N1c_FAULT_still_there_after_moving_within_the_chip",
                  f"opacity {pv._legend_opacity:.2f} -- it does not recover")
    reset()

    say("  N2 FAULT 2 -- the chip is re-placed out from under the pointer")
    win.resize(1500, 1000)
    pump(app, 800)
    lab = label_rect(pv)
    ptr = QPoint(lab.right() - 8, lab.center().y())
    pv._apply_legend_pointer(ptr)
    pump(app, 400)
    b0 = (max(0, lab.x() - 40), lab.y() - 40, lab.width() + 120, lab.height() + 80)
    mark_and_save(pv, b0, ptr, "N2a_before_resize_chip_hidden",
                  f"correct: opacity {pv._legend_opacity:.2f}")
    win.resize(1040, 1000)             # a tiling shortcut; no mouse event
    pump(app, 1200)
    lab2 = label_rect(pv)
    inside2 = lab2.contains(pv._legend_pointer)
    say(f"      chip {lab} -> {lab2}; pointer {pv._legend_pointer} "
        f"still on the chip = {inside2}; opacity={pv._legend_opacity:.3f}")
    b1 = (max(0, min(lab2.x(), ptr.x()) - 40), lab2.y() - 40,
          abs(ptr.x() - lab2.x()) + lab2.width() + 80, lab2.height() + 80)
    mark_and_save(pv, b1, pv._legend_pointer,
                  "N2b_FAULT_after_resize_chip_missing",
                  f"FAULT: the pointer is NOT on the chip and opacity is "
                  f"{pv._legend_opacity:.2f}")
    mark_and_save(pv, (0, lab2.top() - 260, pv._img_label.width(), 320),
                  pv._legend_pointer, "N2c_FAULT_after_resize_whole_width",
                  "the same frame across the whole sheet: the crosshair is "
                  "where the pointer is, and there is no chip anywhere")
    pump(app, 2500)
    say(f"      2.5 s later, still opacity={pv._legend_opacity:.3f}")
    win.resize(1500, 1000)
    pump(app, 800)
    reset()

    say("  N3 FAULT 3 -- clear() while hidden, then a new chart")
    lab = label_rect(pv)
    pv._apply_legend_pointer(lab.center())
    pump(app, 400)
    say(f"      hovering: opacity={pv._legend_opacity:.2f}")
    pv.clear()
    pump(app, 300)
    say(f"      after clear(): opacity={pv._legend_opacity:.2f} "
        f"hidden={pv._legend_hidden} pointer={pv._legend_pointer}")
    mt2 = load_measured(app, win, charts["rect"])
    pv2 = mt2._preview
    pump(app, 800)
    lab3 = label_rect(pv2)
    on = lab3.contains(pv2._legend_pointer) if (
        lab3 and pv2._legend_pointer) else False
    say(f"      new chart: chip={lab3} pointer={pv2._legend_pointer} "
        f"pointer-on-chip={on} opacity={pv2._legend_opacity:.3f}")
    if lab3:
        b3 = (max(0, lab3.x() - 40), lab3.y() - 40, lab3.width() + 80,
              lab3.height() + 80)
        mark_and_save(pv2, b3, pv2._legend_pointer,
                      "N3_FAULT_new_chart_has_no_legend",
                      f"FAULT: a different chart, nobody pointing at its chip, "
                      f"opacity {pv2._legend_opacity:.2f}")
        shot(win, "N3b_FAULT_new_chart_window",
             "the whole window: the new chart's legend is simply absent")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="ABC")
    args = ap.parse_args()
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

        def _mb(kind, yes):
            def f(*a, **k):
                txt = " | ".join(str(x)[:160] for x in a[1:3])
                say(f"      [dialog {kind}] {txt}")
                return yes
            return staticmethod(f)

        for m in ("warning", "critical", "information"):
            setattr(QMessageBox, m, _mb(m, 0))
        setattr(QMessageBox, "question",
                _mb("question", QMessageBox.StandardButton.Yes))
        from ui.main_window import MainWindow
        from ui.tabs.tab_chart import TabChart
        TabChart._confirm_displacing_results = lambda self, *a, **k: True

        win = MainWindow(settings)
        win.resize(1500, 1000)
        win.show()
        win.raise_()
        win.activateWindow()
        pump(app, 2500)
        tabc = win._tab_chart

        charts: dict = {}
        for key, name in (("i1", "legend-i1-strip"),
                          ("multi", "cr30-aim-1144"),
                          ("tight", "i1-strip-chart"),
                          ("hex", "cr30-aim-hex"),
                          ("rect", "cr30-aim-rect"),
                          ("tiny", "cr30-aim-tiny")):
            cand = sorted((WORK / name).glob("runs/run*/*.ti2"))
            if cand:
                charts[key] = chart_facts(cand[-1])
                write_ti3(charts[key])

        g = globals()
        for ch in phases:
            fn = g.get(f"phase_{ch}")
            if fn is None:
                continue
            if ch == "A":
                fn(app, win, tabc, charts)
            else:
                fn(app, win, charts)
        pump(app, 300)
        win.close()
        pump(app, 300)
    finally:
        guard_plist_out(before)
        (SANDBOX / "log.txt").write_text("\n".join(LOG))
        say(f"    transcript -> {SANDBOX / 'log.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
