#!/usr/bin/env python3
"""Redraw ``docs/mockups/acc133/acc_1_panel.png`` — the #133 Create Chart panel.

The first version of this mockup was drawn by a throwaway script, so when its
sheet count turned out to be wrong there was nothing to correct: the image had
to be reproduced from scratch. This file exists so that never happens again.

Two things it fixes, both verified against the code rather than assumed:

* **The sheet count.** The original said "4 sheets on A4 with your i1Pro" for
  1 042 colours. That came from a capacity of 682 patches per sheet, which
  ``data/patch_db.py`` holds for ``("i1", False, "11x17")`` — not for A4. At
  the capacity ChromIQ actually offers for i1Pro on A4 (483 patches per sheet,
  at the 10 mm default margin ``INSTRUMENT_DEFAULT_MARGIN`` gives the i1Pro),
  1 050 patches is **3 sheets**. The number is computed here, not typed, so it
  cannot drift from the database again.
* **The eight cube corners.** §9a became a requirement after the original was
  drawn: they are added to every chart unconditionally, outside the gamut
  filter. They are patches on paper, so they belong in the count line the user
  reads before committing sheets.

Run with the app's real stylesheet so the result is the real widget set:

    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/mockup_acc133_panel.py

Writes the PNG and prints the numbers it used.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                        # noqa: E402
from PyQt6.QtWidgets import (                                      # noqa: E402
    QApplication, QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ui import styles                                              # noqa: E402
from ui.tooltip_button import TooltipButton                        # noqa: E402

OUT = ROOT / "docs" / "mockups" / "acc133" / "acc_1_panel.png"

#: The panel's worked example. The master-set size and the in-gamut count are
#: illustrative; the capacity and the sheet count are derived below.
SET_SIZE = 1500
IN_GAMUT = 1042
INSTRUMENT, PAPER = "i1", "A4"


def sheet_count() -> "tuple[int, int, int]":
    """``(patches, per_sheet, sheets)`` for the example, from the real database.

    The corners are added to the printed total because §9a puts them in every
    chart this module builds, outside the gamut filter.
    """
    from data.patch_db import INSTRUMENT_DEFAULT_MARGIN, query_patches
    from workflow.measurement_report import CUBE_CORNERS

    margin = INSTRUMENT_DEFAULT_MARGIN.get(INSTRUMENT, 6)
    per_sheet = query_patches(INSTRUMENT, PAPER, False, True, margin, 1.0,
                              False, False)
    if not per_sheet:
        raise SystemExit(
            f"patch_db has no capacity for {INSTRUMENT}/{PAPER} — the mockup "
            "must not invent one")
    patches = IN_GAMUT + len(CUBE_CORNERS)
    return patches, int(per_sheet), math.ceil(patches / per_sheet)


def _row(parent: QWidget, label: str, control: QWidget, title: str,
         body: str) -> QWidget:
    """One option row: label, control, ⓘ in the tab's accent colour."""
    row = QWidget(parent)
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    text = QLabel(label, row)
    text.setMinimumWidth(210)
    text.setStyleSheet("background:transparent;")
    lay.addWidget(text)
    lay.addWidget(control, 1)
    lay.addWidget(TooltipButton(title, body, row))
    return row


def build() -> QWidget:
    patches, per_sheet, sheets = sheet_count()

    panel = QWidget()
    panel.setObjectName("mockupPanel")
    panel.setFixedWidth(620)
    outer = QVBoxLayout(panel)
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(12)

    # --- the module buttons, with this one selected -----------------------
    modes = QWidget(panel)
    mrow = QHBoxLayout(modes)
    mrow.setContentsMargins(0, 0, 0, 0)
    mrow.setSpacing(10)
    for name, on in (("GUIDED", False), ("MANUAL", False),
                     ("FROM PROFILE GAMUT", True)):
        b = QPushButton(name, modes)
        b.setCheckable(True)
        b.setChecked(on)
        b.setMinimumHeight(38)
        if on:
            b.setStyleSheet(
                f"QPushButton{{background:{styles.SPEC_MAGENTA};color:#101010;"
                "font-weight:700;border:none;border-radius:6px;padding:8px 14px;}")
        mrow.addWidget(b, 1)
    mrow.addWidget(TooltipButton(
        "Building a chart from this profile's gamut",
        "This module builds a verification chart out of colours chosen by the "
        "profile you have already made, instead of colours chosen by a patch "
        "generator.", modes))
    outer.addWidget(modes)

    caption = QLabel("Shown only while <b>Run type</b> is Verification.", panel)
    caption.setStyleSheet(f"color:{styles.TEXT_DIM};background:transparent;")
    outer.addWidget(caption)

    # --- the three options ------------------------------------------------
    group = QGroupBox("Reference colours", panel)
    gl = QVBoxLayout(group)
    gl.setContentsMargins(14, 16, 14, 14)
    gl.setSpacing(10)

    count = QSpinBox(group)
    count.setRange(50, 5000)
    count.setValue(SET_SIZE)
    # No group separator: it is locale-dependent, and on a German machine the
    # box rendered "1.500", which reads as a decimal to an English audience.
    count.setGroupSeparatorShown(False)
    gl.addWidget(_row(group, "Number of colours to test", count,
                      "How many colours to test",
                      "Sets how many reference colours ChromIQ asks the "
                      "profile to reproduce."))

    margin_box = QComboBox(group)
    margin_box.addItems(["Stay safely inside the printable range",
                         "Use the full printable range"])
    gl.addWidget(_row(group, "How close to the gamut edge", margin_box,
                      "How close to the gamut edge to go",
                      "Decides whether the test colours may sit right at the "
                      "limit of what your printer and paper can do."))

    white = QComboBox(group)
    white.addItems(["The paper's own white (media-relative)",
                    "A fixed absolute white (absolute colorimetric)"])
    gl.addWidget(_row(group, "Which white to compare against", white,
                      "Which white the comparison is measured from",
                      "Paper is never perfectly white, and this setting "
                      "decides whether that counts as an error."))
    outer.addWidget(group)

    # --- what it costs, before any paper is used --------------------------
    info = QLabel(panel)
    info.setObjectName("info")
    info.setWordWrap(True)
    info.setText(
        f"<b>{IN_GAMUT:,}</b> of <b>{SET_SIZE:,}</b> reference colours can be "
        "printed by this profile, and the 8 cube corners are always added."
        f"<br>That is <b>{patches:,} patches</b> — "
        f"<b>{sheets} sheets</b> on {PAPER} with your i1Pro."
        .replace(",", " "))
    outer.addWidget(info)

    rule = QFrame(panel)
    rule.setFrameShape(QFrame.Shape.HLine)
    rule.setStyleSheet(f"color:{styles.BORDER};")
    outer.addWidget(rule)

    below = QLabel(
        "Below this point the panel is the Manual module's, unchanged — the "
        "sheet layout section and every option in it. See the next screenshot.",
        panel)
    below.setWordWrap(True)
    below.setStyleSheet(f"color:{styles.TEXT_DIM};background:transparent;")
    outer.addWidget(below)

    gen = QPushButton("Generate verification chart", panel)
    gen.setMinimumHeight(40)
    gen.setStyleSheet(
        f"QPushButton{{background:{styles.SPEC_MAGENTA};color:#101010;"
        "font-weight:700;border:none;border-radius:6px;padding:10px;}")
    outer.addWidget(gen)
    return panel


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))
    app.setPalette(styles.make_dark_palette())
    app.setStyleSheet(styles.APP_STYLESHEET)
    TooltipButton.ACCENT = styles.SPEC_MAGENTA

    panel = build()
    panel.setStyleSheet(panel.styleSheet() +
                        f"\n#mockupPanel{{background:{styles.BG_DARK};}}")
    panel.adjustSize()
    panel.grab().save(str(OUT))

    patches, per_sheet, sheets = sheet_count()
    print(f"i1Pro / {PAPER}: {per_sheet} patches per sheet (patch_db, "
          f"10 mm default margin)")
    print(f"{IN_GAMUT} in gamut + 8 cube corners = {patches} patches "
          f"-> {sheets} sheets")
    print(f"wrote {OUT.relative_to(ROOT)}  {panel.size().width()}x"
          f"{panel.size().height()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
