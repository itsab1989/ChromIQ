# -*- coding: utf-8 -*-
"""Issue #182 round 4 — the "approved chart list" window, as a REAL PyQt6 window
built with ChromIQ's own widgets and painted through the style main.py:147
installs, so the sizes are the sizes a shipped window would have.

The rows are NOT invented: every one is a real bundled ChromIQ chart, checked by
`measure_preset_check_cost.py` against the criteria of PATCH-SET-CRITERIA.md.

NO ChromIQ source file is modified.
"""
import json, os, sys
from pathlib import Path
assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "sandbox the settings first"
sys.path.insert(0, str(Path(os.environ.get("CHROMIQ_REPO",
                                    "~/develop/ChromIQ")).expanduser()))

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QFrame, QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from main import WinButtonLayoutStyle

HERE = os.path.dirname(os.path.abspath(__file__))
app = QApplication(sys.argv)
app.setStyle(WinButtonLayoutStyle("Fusion"))

D = json.load(open(os.path.join(HERE, "preset-check-cost.json")))

# A readable label for a bundled chart, from its asset path.
def label(p):
    leaf = p.split("/")[-2]
    return leaf.replace("_", " ")

PICK = [
    "i1pro75/i1_w75_a4_1944p_3pages_portrait_w7_5mm",
    "i1pro75/i1_w75_a4_324p_1page_portrait_w7_5mm",
    "i1pro3/p3_a3_1008p_3pages_portrait_w16_0mm",
    "colormunki/cm_a4_84p_1page_portrait_w26_0mm_fast_reading_speed_hand_held",
    "colormunki/cm_a3_900p_2pages_portrait_w10_0mm_fast_reading_speed",
    "fulllayout/fls_i1pro_a4_1200p_3pages_portrait",
]
rows = []
for key in PICK:
    for p in D["per_preset"]:
        if key in p["path"]:
            rows.append(p)
            break

MET_CHROMIQ = 5          # A1..A5
def summarise(p):
    """(report types, tolerance sets, what is missing) for one chart."""
    got, missing = [], []
    if p["C1_patch_count"]:
        got.append(("ChromIQ Profile Check", 5, 5))
    n_iso = 0
    total_iso = 4        # substrate, solids, near-neutral avg, near-neutral max
    if p["C2_substrate"]:
        n_iso += 1
    else:
        missing.append("no bare-paper patch: add “Pure white & black”")
    if p["C4_six_solids"]:
        n_iso += 1
    else:
        missing.append("solids missing: add “3D RGB cube”, 3 steps or more")
    if p["C6_neutral_scale"] and p["C7_near_neutral_ring"]:
        n_iso += 2
    else:
        missing.append("no near-neutral scale: add “Near-neutral greys”, 1 ring")
    total_iso += 1
    if p["C8_ramps_30_70"]:
        n_iso += 1
    else:
        missing.append("no tone-ramp steps between 30 % and 70 %: "
                       "no generator makes these yet")
    got.append(("ISO 12647-8:2021 tolerance values", n_iso, total_iso))
    types = "Profiling · Verification" if p["patches"] >= 400 else "Verification"
    return types, got, missing


w = QWidget()
w.setWindowTitle("Charts that can serve each report type")
v = QVBoxLayout(w)
v.setContentsMargins(16, 14, 16, 14)
v.setSpacing(10)

h = QLabel("<b>Charts that can serve each report type</b>")
f = h.font(); f.setPointSizeF(f.pointSizeF() + 2); h.setFont(f)
v.addWidget(h)
sub = QLabel("Checked against the patch-set criteria. A chart may supply the "
             "measurements a tolerance set needs; no chart makes a print conform "
             "to a standard.")
sub.setWordWrap(True)
v.addWidget(sub)

t = QTableWidget(0, 5)
t.setHorizontalHeaderLabels(["Chart", "Patches", "Report types",
                             "Tolerance sets it can feed", "What is missing"])
t.verticalHeader().setVisible(False)
t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
t.setWordWrap(True)
for p in rows:
    types, got, missing = summarise(p)
    r = t.rowCount(); t.insertRow(r)
    t.setItem(r, 0, QTableWidgetItem(label(p["path"])))
    it = QTableWidgetItem(str(p["patches"])); it.setTextAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    t.setItem(r, 1, it)
    t.setItem(r, 2, QTableWidgetItem(types))
    t.setItem(r, 3, QTableWidgetItem("\n".join(
        f"{n}  ·  {a} of the {b} metrics ChromIQ can evaluate"
        for n, a, b in got)))
    t.setItem(r, 4, QTableWidgetItem("\n".join(missing) if missing else "–"))
t.resizeColumnsToContents()
t.resizeRowsToContents()
hh = t.horizontalHeader()
hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
v.addWidget(t)

note = QLabel("A tolerance set defines more criteria than ChromIQ evaluates; "
              "the metrics table says which, and why. And two criteria cannot "
              "be checked at all: which patches the ISO 12647-8 clause 5.2 "
              "control strip contains, and the outer-gamut patch list of "
              "Annex C. Both are in clauses ChromIQ does not hold, so they are "
              "shown as “not checked”, never as a failure.")
note.setWordWrap(True)
v.addWidget(note)

btns = QHBoxLayout(); btns.addStretch(1)
b1 = QPushButton("Re-check now"); b2 = QPushButton("Close")
btns.addWidget(b1); btns.addWidget(b2)
v.addLayout(btns)

w.resize(1400, 440)
w.show()
app.processEvents()
t.resizeRowsToContents()
app.processEvents()
out = os.path.join(HERE, "mock-approved-chart-list-EN.png")
w.grab().save(out)
print("wrote", out, w.width(), "x", w.height(),
      " table sizeHint:", t.sizeHint().width(), "x", t.sizeHint().height())
