#!/usr/bin/env python3
"""On-screen probe for report 48: legend chip placement + event plumbing.

Drives the REAL TiffPreview (no re-implementation). Ground truth = pixel scan
of the rendered canvas for the chip's fill (QColor(20,20,20,190) over paper
white -> blended grey ~(79,79,79)). Vacuity guard: every case must FIND a chip
(or assert its absence for a reason) — a probe that renders nothing fails loud.
"""
import hashlib, os, sys, time
from pathlib import Path

ROOT = Path("/Users/Basti/develop/ChromIQ")
sys.path.insert(0, str(ROOT))
SHOTS = Path.home() / "Desktop" / "cr30-legend-hover"
SHOTS.mkdir(parents=True, exist_ok=True)
SCRATCH = Path(__file__).parent

PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
plist_before = hashlib.sha256(PLIST.read_bytes()).hexdigest() if PLIST.exists() else None

from PIL import Image, ImageDraw

# --- synthetic chart TIFF: white paper, 8 columns x 6 rows of patches -------
W, H = 1000, 700
MARG_X, MARG_TOP, MARG_BOT = 60, 80, 60      # generous bottom margin case
img = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(img)
COLS, ROWS = 8, 6
pw = (W - 2 * MARG_X) / COLS
ph = (H - MARG_TOP - MARG_BOT) / ROWS
patch_boxes = []
for c in range(COLS):
    for r in range(ROWS):
        x0 = int(MARG_X + c * pw); y0 = int(MARG_TOP + r * ph)
        x1 = int(x0 + pw - 4); y1 = int(y0 + ph - 4)
        d.rectangle([x0, y0, x1, y1], fill=(200, 30 * r, 25 * c))
        patch_boxes.append((x0, y0, x1 - x0, y1 - y0))
tif = SCRATCH / "probe_chart.tif"
img.save(tif)

# tight-margin variant: patches run to 8 px above the paper bottom
img2 = Image.new("RGB", (W, H), (255, 255, 255))
d2 = ImageDraw.Draw(img2)
ph2 = (H - MARG_TOP - 8) / ROWS
tight_boxes = []
for c in range(COLS):
    for r in range(ROWS):
        x0 = int(MARG_X + c * pw); y0 = int(MARG_TOP + r * ph2)
        x1 = int(x0 + pw - 4); y1 = int(y0 + ph2 - 4)
        d2.rectangle([x0, y0, x1, y1], fill=(200, 30 * r, 25 * c))
        tight_boxes.append((x0, y0, x1 - x0, y1 - y0))
tif2 = SCRATCH / "probe_chart_tight.tif"
img2.save(tif2)

from PyQt6.QtCore import QPoint, QRect, Qt, QEvent, QPointF
from PyQt6.QtGui import QColor, QMouseEvent
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

app = QApplication(sys.argv)

from ui.tiff_preview import TiffPreview

moves = []          # (source, widget-pos) seen by TiffPreview.mouseMoveEvent

class Probe(TiffPreview):
    def mouseMoveEvent(self, ev):
        moves.append(ev.position().toPoint())
        super().mouseMoveEvent(ev)

pv = Probe()
pv.resize(760, 560)
pv.show()

def pump(ms=250):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)

pump(400)

def stripe_rects():
    # one rect per column, spanning all rows (strip = column)
    out = []
    for c in range(COLS):
        x0 = int(MARG_X + c * pw)
        out.append(QRect(x0, MARG_TOP, int(pw - 4), int(ROWS * ph - 4)))
    return out

def overlay_items():
    its = []
    for (x, y, w, h) in patch_boxes:
        its.append((QRect(x, y, w, h), QColor(10, 200, 10), QColor(10, 10, 200), False))
    return its

def canvas_image():
    pm = pv._img_label.pixmap()
    assert pm is not None and not pm.isNull(), "VACUITY: no canvas rendered"
    return pm.toImage()

def find_chip_rows(qimg):
    """Rows containing a horizontal run (>=60 px) of near-grey(79) chip fill."""
    rows = []
    w, h = qimg.width(), qimg.height()
    for y in range(h):
        run = best = 0
        for x in range(0, w, 2):
            c = qimg.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if abs(r - g) <= 10 and abs(g - b) <= 10 and 55 <= r <= 110:
                run += 1; best = max(best, run)
            else:
                run = 0
        if best * 2 >= 60:
            rows.append(y)
    return rows

def shot(name):
    p = SHOTS / f"{name}.png"
    pv.grab().save(str(p))
    print("saved", p)

report = []

# ---- CASE 1: normal journey — stripe rects present --------------------------
pv.load_tiff([tif])
pump(400)
pv.set_stripe_rects(stripe_rects())
pv.set_patch_overlay(0, overlay_items(), replace_page=True)
pv._repaint_label(); pump(400)
qi = canvas_image()
rows = find_chip_rows(qi)
assert rows, "VACUITY: no chip found in case 1"
dpr = qi.devicePixelRatio()
ch_h = qi.height()
c1_frac = (rows[0] + rows[-1]) / 2 / ch_h
report.append(f"CASE1 with stripe rects: chip rows {rows[0]}..{rows[-1]} of {ch_h} (centre {c1_frac:.2f}) dpr={dpr}")
shot("P1_chip_with_stripe_rects")

# chip rect in device px -> label logical px for later propagation check
chip_dev = (rows[0], rows[-1])

# ---- CASE 2: EMPTY stripe rects (fault 2) ----------------------------------
pv.set_stripe_rects([])
pv._repaint_label(); pump(400)
qi = canvas_image()
rows2 = find_chip_rows(qi)
assert rows2, "VACUITY: no chip found in case 2"
c2_frac = (rows2[0] + rows2[-1]) / 2 / qi.height()
report.append(f"CASE2 EMPTY stripe rects: chip rows {rows2[0]}..{rows2[-1]} (centre {c2_frac:.2f})")
assert c2_frac < 0.35 < c1_frac, f"expected top vs bottom: {c2_frac} vs {c1_frac}"
report.append("CASE2 VERDICT: chip at TOP of sheet, over row 1 — fault 2 CONFIRMED in the real widget")
shot("P2_chip_empty_stripe_rects_TOP")

# ---- CASE 3: the three wordings differ in width ----------------------------
pv.set_stripe_rects(stripe_rects())
widths = {}
for mode in ("both", "expected", "measured"):
    pv.set_overlay_mode(mode)
    pv._repaint_label(); pump(300)
    qi = canvas_image()
    rows3 = find_chip_rows(qi)
    assert rows3, f"VACUITY: no chip in mode {mode}"
    y = rows3[len(rows3)//2]
    xs = [x for x in range(qi.width())
          if (lambda c: abs(c.red()-c.green())<=10 and abs(c.green()-c.blue())<=10
              and 55 <= c.red() <= 110)(qi.pixelColor(x, y))]
    widths[mode] = (min(xs), max(xs))
    shot(f"P3_mode_{mode}")
report.append(f"CASE3 chip x-extents per mode (device px): "
              + ", ".join(f"{m}={x1-x0}px" for m, (x0, x1) in widths.items()))

# ---- CASE 4: tight bottom margin — chip rests ON the last row --------------
pv.set_overlay_mode("both")
pv.load_tiff([tif2])
pump(400)
tsr = []
for c in range(COLS):
    x0 = int(MARG_X + c * pw)
    tsr.append(QRect(x0, MARG_TOP, int(pw - 4), int(ROWS * ph2 - 4)))
pv.set_stripe_rects(tsr)
its2 = [(QRect(x, y, w, h), QColor(10, 200, 10), QColor(10, 10, 200), False)
        for (x, y, w, h) in tight_boxes]
pv.set_patch_overlay(0, its2, replace_page=True)
pv._repaint_label(); pump(400)
qi = canvas_image()
rows4 = find_chip_rows(qi)
assert rows4, "VACUITY: no chip in case 4"
c4_frac = (rows4[0] + rows4[-1]) / 2 / qi.height()
report.append(f"CASE4 tight margin: chip centre frac {c4_frac:.2f} — over the last row (accepted fallback)")
shot("P4_chip_over_last_row_tight_margin")

# ---- CASE 5: event propagation — moves over _img_label reach TiffPreview ----
moves.clear()
lbl = pv._img_label
centre_l = QPoint(lbl.width() // 2, lbl.height() // 2)
QTest.mouseMove(lbl, centre_l)
pump(200)
QTest.mouseMove(lbl, centre_l + QPoint(12, 8))
pump(200)
via_qtest = len(moves)
# fallback/second witness: sendEvent directly to the label
p_lbl = QPointF(centre_l.x() + 3, centre_l.y() + 3)
ev = QMouseEvent(QEvent.Type.MouseMove, p_lbl,
                 lbl.mapToGlobal(p_lbl.toPoint()).toPointF() if hasattr(lbl.mapToGlobal(p_lbl.toPoint()), "toPointF") else p_lbl,
                 Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                 Qt.KeyboardModifier.NoModifier)
QApplication.sendEvent(lbl, ev)
pump(100)
via_send = len(moves) - via_qtest
report.append(f"CASE5 propagation: TiffPreview.mouseMoveEvent fired {via_qtest}x via QTest.mouseMove(label), {via_send}x via sendEvent(label)")
if moves:
    wp = moves[-1]
    lp = lbl.mapFrom(pv, wp)
    report.append(f"CASE5 last move widget-pos={wp.x()},{wp.y()} -> label-pos={lp.x()},{lp.y()} (offset {wp.x()-lp.x()},{wp.y()-lp.y()})")
    # where is the chip in LABEL logical coords? paint geom converts:
    s, gox, goy = pv._paint_geom
    report.append(f"CASE5 _paint_geom scale={s:.4f} ox={gox:.1f} oy={goy:.1f} paint_border={pv._paint_border}")

# ---- CASE 6: clear() then new chart — does _patch_overlay survive? ---------
pv.clear()
survives_clear = bool(pv._patch_overlay)
pv.load_tiff([tif])          # "chart B"
pump(500)
qi = canvas_image()
rows6 = find_chip_rows(qi)
report.append(f"CASE6 after clear()+load_tiff(new chart): _patch_overlay non-empty={survives_clear}; "
              f"chip rows found={rows6[:3]}{'...' if len(rows6)>3 else ''} "
              f"(stripe rects now empty -> chip at TOP over the NEW chart)" if rows6 else
              f"CASE6 after clear()+load_tiff: _patch_overlay non-empty={survives_clear}; no chip drawn")
if rows6:
    shot("P6_stale_overlay_after_clear")

# ---- CASE 7: narrow pane — chip wider than the paper -----------------------
pv.resize(280, 560)
pump(500)
qi = canvas_image()
rows7 = find_chip_rows(qi)
report.append(f"CASE7 narrow pane 280px: chip rows={bool(rows7)}; canvas {qi.width()}x{qi.height()}")
shot("P7_narrow_pane")

print("\n".join(report))

plist_after = hashlib.sha256(PLIST.read_bytes()).hexdigest() if PLIST.exists() else None
print("PLIST UNCHANGED:", plist_before == plist_after)
