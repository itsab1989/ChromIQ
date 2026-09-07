# -*- coding: utf-8 -*-
"""Round 5, issue #182, agent DD. Two mockups of the big tolerance table, one per
shape Knut asked about on 2026-09-06 (his restated question 6):

  A  one row serves several columns: a metric ChromIQ computes and a standard
     also limits is ONE row, grouped by the patches it is written over.
  B  This chart, all patches listed separately from the standards' metrics.

Both are real PyQt6 windows built with ChromIQ's own spin box and painted through
the style main.py installs. Settings are sandboxed. ISO limits are masked as
"•,••" as in every picture posted on this issue (decision S2 / Sebastian's Q2 is
open). NO ChromIQ source file is modified.
"""
import os, sys
assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "sandbox the settings first"
sys.path.insert(0, os.path.expanduser(os.environ.get("CHROMIQ_REPO", "~/develop/ChromIQ")))
sys.path.insert(0, os.path.join(os.path.expanduser(
    os.environ.get("CHROMIQ_RESEARCH", "~/develop/ChromIQ-research")),
    "issue-182/08-defaults-table"))
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGridLayout, QPushButton, QScrollArea, QCheckBox, QFrame)
from PyQt6.QtCore import Qt
from main import WinButtonLayoutStyle
import matrix
# round 4 corrected round 3's reach for these rows: uniformity is unbuilt, not impossible;
# gloss and fluorescence are declarations; repeatability is a protocol.
for _rid in ('U1','U2','U3','U4','R1','R2','S3','S4'):
    matrix.REACH[_rid] = ('buildable', matrix.REACH[_rid][1])
from build_mockups_names import SHORT as _SHORT, UNIT
SHORT = {k: v.replace(' \u2014 ', ', ') for k, v in _SHORT.items()}

OUT = os.path.dirname(os.path.abspath(__file__))
app = QApplication(sys.argv)
app.setStyle(WinButtonLayoutStyle("Fusion"))
from ui.widgets import NoScrollDoubleSpinBox

CHROMIQ = {
    "chromiq_default": {"C1": 2.0, "C2": 2.0, "C3": 2.0, "C4": 3.0, "C5": 3.0},
    "chromiq_tight":   {"C1": 1.0, "C2": 1.0, "C3": 1.0, "C4": 1.5, "C5": 1.5},
    "chromiq_quick":   {"C1": 4.0, "C2": 4.0, "C3": 4.0, "C4": 6.0, "C5": 6.0},
}
COLS = [("chromiq_default", "ChromIQ default", "edit"),
        ("chromiq_tight",   "ChromIQ tight",   "edit"),
        ("chromiq_quick",   "Quick check",     "edit"),
        ("iso12647_7",      "ISO 12647-7:2016", "ro"),
        ("iso12647_8",      "ISO 12647-8:2021", "ro"),
        ("custom_7",        "Custom ISO 12647-7", "edit"),
        ("custom_8",        "Custom ISO 12647-8", "edit")]
MASK = "•,••"

def ink(w, colour, extra=""):
    w.setStyleSheet(f"color:{colour};{extra}"); return w

def rows_by_group(order, rows):
    out = []
    for g in order:
        rr = [r for r in rows if r[0] == g]
        if rr: out.append((g, rr))
    return out

# --- the rows, in the two shapes ------------------------------------------------
BASE = [(g, rid, SHORT[rid], unit, cells) for (g, rid, name, unit, cells) in matrix.ROWS]
ORDER_B = []
for g, *_ in BASE:
    if g not in ORDER_B: ORDER_B.append(g)
# B: as in round 3 -- ChromIQ's five rows in their own group at the bottom.
SHAPE_B = [(("This chart, all patches" if g == "This chart, all patches" else g), rid, n, u, c)
           for (g, rid, n, u, c) in BASE]
ORDER_B = [("This chart, all patches" if g == "This chart, all patches" else g) for g in ORDER_B]

# A: merge. F1 (all patches, average) merges into C1; F2 (95th percentile) into C5.
# The merged group is named for the population, and sits where the
# characterization-chart group sat. F3/F3b/F4 stay in a group of their own.
MERGED_GROUP = "All patches of the measured chart"
SHAPE_A, ORDER_A = [], []
for (g, rid, n, u, c) in BASE:
    if rid in ("F1", "F2"):
        continue
    if g == "This chart, all patches":
        continue
    if g == "Characterization chart":
        if MERGED_GROUP not in ORDER_A:
            ORDER_A.append(MERGED_GROUP)
            f1 = next(r for r in BASE if r[1] == "F1"); f2 = next(r for r in BASE if r[1] == "F2")
            cq = {r[1]: r for r in BASE if r[0] == "This chart, all patches"}
            def merged(cid, iso_row):
                cells = dict(cq[cid][4]); cells["iso12647_7"] = iso_row[4]["iso12647_7"]; cells["iso12647_8"] = iso_row[4]["iso12647_8"]
                return cells
            SHAPE_A += [
                (MERGED_GROUP, "C1", "Average ΔE00 ¹", "dE00", merged("C1", f1)),
                (MERGED_GROUP, "C2", "Average ΔE00, best 95 % of patches", "dE00", cq["C2"][4]),
                (MERGED_GROUP, "C3", "Average ΔE00, worst 5 % of patches", "dE00", cq["C3"][4]),
                (MERGED_GROUP, "C4", "Maximum ΔE00 ²", "dE00", cq["C4"][4]),
                (MERGED_GROUP, "C5", "95th percentile ΔE00 ¹ ³", "dE00", merged("C5", f2)),
            ]
        g2 = "Characterization chart, selected patches"
        if g2 not in ORDER_A: ORDER_A.append(g2)
        SHAPE_A.append((g2, rid, n, u, c)); continue
    if g not in ORDER_A: ORDER_A.append(g)
    SHAPE_A.append((g, rid, n, u, c))

def table_window(title, sub, order, rows, footnotes, shape_tag):
    win = QWidget(); win.setWindowTitle(title)
    v = QVBoxLayout(win); v.setContentsMargins(14, 14, 14, 14); v.setSpacing(8)
    h = QLabel(f"<b>Measurement Report Defaults</b>, {title}"); h.setStyleSheet("font-size:15px;")
    v.addWidget(h)
    s = QLabel(sub); s.setWordWrap(True); ink(s, "#606060", " font-size:11px;"); v.addWidget(s)

    # Knut's per-set checkboxes: which columns are shown. All on by default.
    cb_row = QHBoxLayout(); cb_row.addWidget(ink(QLabel("Show:"), "#404040", " font-weight:bold;"))
    for _, cname, _k in COLS:
        cb = QCheckBox(cname); cb.setChecked(True); cb_row.addWidget(cb)
    cb_row.addStretch(); v.addLayout(cb_row)

    body = QWidget(); g = QGridLayout(body); g.setHorizontalSpacing(14); g.setVerticalSpacing(3)
    for ci, txt in enumerate(["Metric", "ChromIQ", "Unit"]):
        l = QLabel(txt)
        if ci: l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        g.addWidget(ink(l, "#404040", " font-weight:bold;"), 0, ci)
    for ci, (_, cname, kind) in enumerate(COLS):
        l = QLabel(cname + ("" if kind == "edit" else "<br><span style='font-weight:normal;font-size:10px;color:#808080'>read-only</span>"))
        l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        g.addWidget(ink(l, "#404040", " font-weight:bold;"), 0, ci + 3)
    for ci, (_, cname, kind) in enumerate(COLS):
        if kind == "edit":
            b = QPushButton("Restore factory"); b.setFixedHeight(22); b.setStyleSheet("font-size:10px;")
            g.addWidget(b, 1, ci + 3)
    reach_glyph = {"now": ("●", "#1a7f37"), "buildable": ("○", "#8a6d00"),
                   "needs_class": ("○", "#8a6d00"), "needs_mode": ("✕", "#a03030"),
                   "never_here": ("✕", "#a03030")}
    r = 2; count = 0
    for gname, rr in rows_by_group(order, rows):
        gl = QLabel(gname.upper()); ink(gl, "#707070", " font-size:10px; font-weight:bold;")
        g.addWidget(gl, r, 0, 1, 3 + len(COLS)); r += 1
        for (_, rid, name, unit, cells) in rr:
            count += 1
            g.addWidget(QLabel("    " + name), r, 0)
            gy, col = reach_glyph[matrix.REACH[rid][0]]
            l = QLabel(gy); l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            g.addWidget(ink(l, col, " font-weight:bold;"), r, 1)
            u = QLabel(UNIT.get(unit, unit)); u.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            g.addWidget(ink(u, "#808080", " font-size:11px;"), r, 2)
            for ci, (cid, _, kind) in enumerate(COLS):
                src = cid if cid in cells else ("iso12647_7" if cid == "custom_7" else "iso12647_8")
                ckind = cells[src][0]
                if ckind == "unused":
                    l = QLabel("–"); l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                    g.addWidget(ink(l, "#b0b0b0"), r, ci + 3); continue
                if ckind == "unlicensed":
                    l = QLabel("?"); l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                    g.addWidget(ink(l, "#a06000", " font-weight:bold;"), r, ci + 3); continue
                if ckind == "req":
                    l = QLabel(str(cells[src][1])); l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                    g.addWidget(ink(l, "#202020", " font-size:11px;"), r, ci + 3); continue
                if kind == "edit":
                    sb = NoScrollDoubleSpinBox(); sb.setDecimals(2); sb.setRange(0.0, 1000.0)
                    sb.setFixedWidth(104)
                    if cid in CHROMIQ:
                        sb.setValue(CHROMIQ[cid][rid])
                        if UNIT.get(unit): sb.setSuffix(" " + UNIT[unit])
                    else:                       # a Custom column starts at its ISO parent's value
                        sb.setSpecialValueText(MASK); sb.setValue(0.0)
                    g.addWidget(sb, r, ci + 3)
                else:
                    l = QLabel(MASK); l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                    g.addWidget(ink(l, "#202020"), r, ci + 3)
            r += 1
    g.setColumnStretch(0, 1)
    sc = QScrollArea(); sc.setWidgetResizable(True); sc.setWidget(body); sc.setMinimumHeight(1000)
    v.addWidget(sc, 1)
    leg = QLabel(
        "<b>●</b> ChromIQ computes this today &nbsp; <b>○</b> ChromIQ could compute this, given the right chart "
        "and a reference &nbsp; <b>✕</b> ChromIQ has no way to measure this &nbsp; <b>–</b> this set defines no "
        "limit here &nbsp; <b>?</b> the limit is in a clause ChromIQ does not hold<br>"
        "ISO columns are read-only: the standard defines them. ISO values are masked in this picture only, "
        "pending Sebastian's ruling on showing them.<br>" + footnotes)
    leg.setWordWrap(True); ink(leg, "#505050", " font-size:11px;"); v.addWidget(leg)
    row = QHBoxLayout(); row.addStretch(); row.addWidget(QPushButton("CLOSE")); v.addLayout(row)
    win.resize(1440, 1290)
    return win, count

FOOT_A = ("¹ the standard writes this limit over the ISO 12642-2 chart (1 617 CMYK patches); ChromIQ applies it "
          "to all patches of the chart that was measured, and the report says so. &nbsp; "
          "² the standards set a maximum only over the control-strip patches (see that group), not over all "
          "patches. &nbsp; ³ one definition of the 95th percentile for every column (K9).")
FOOT_B = ("The two ISO rows 'All ISO 12642-2 patches' and ChromIQ's five rows are the same statistics over "
          "different populations; in this shape they never share a row.")

def shot(w, path):
    w.show(); app.processEvents(); app.processEvents()
    w.grab().save(path); print(f"{os.path.basename(path):48s} {w.width()} x {w.height()}"); w.hide()

wa, na = table_window("shape A, one row serves several columns",
    "Rows are grouped by the patches a limit is written over. A statistic ChromIQ computes and a standard also "
    "limits is one row, so the numbers can be read side by side.", ORDER_A, SHAPE_A, FOOT_A, "A")
wb, nb = table_window("shape B, ChromIQ's metrics listed separately",
    "The standards' rows and ChromIQ's rows are kept apart. ChromIQ's five metrics form their own group at the "
    "bottom, as in the round-3 picture.", ORDER_B, SHAPE_B, FOOT_B, "B")
print(f"rows: shape A = {na}, shape B = {nb}")
shot(wa, f"{OUT}/dd-shape-A-one-row-several-columns-EN.png")
shot(wb, f"{OUT}/dd-shape-B-separate-EN.png")
print("done")
