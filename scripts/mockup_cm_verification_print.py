#!/usr/bin/env python3
"""Mockups for colour-managed verification printing (#130).

Sebastian asked what the proposal would look like at every spot it touches.
These are drawn with the **real ChromIQ widgets and the real stylesheet**, so
what they show is what the app would render — not a drawing of it.

Four spots:

  cm_1_print.png       Print Chart, the new row, shown only for a verification
  cm_2_info.png        the ⓘ window behind that row (the real _InfoDialog)
  cm_3_report.png      the line the report gains, so a ΔE is interpretable
  cm_4_no_profile.png  the same row when the run has no profile to print through

Committed rather than thrown away, because a mockup that cannot be re-run is a
mockup that cannot be corrected — the #133 panel had to be redrawn from scratch
to fix one wrong number.

    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/mockup_cm_verification_print.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                        # noqa: E402
from PyQt6.QtWidgets import (                                      # noqa: E402
    QApplication, QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from ui import styles                                              # noqa: E402
from ui.tooltip_button import InfoDialog, TooltipButton            # noqa: E402

OUT = ROOT / "docs" / "mockups" / "cm130"

INTENT_HELP_TITLE = "Printing this chart through your profile"
INTENT_HELP_BODY = (
    "A verification asks a simple question: does your printer really produce "
    "the colours your profile promises?\n\n"
    "To ask it properly the chart has to be printed the way your profile says "
    "those colours should be printed. ChromIQ works out the exact ink amounts "
    "your profile predicts for every patch, and prints those — so the sheet "
    "that comes out is your profile's own prediction, made physical. Measuring "
    "it then tells you how close the prediction was.\n\n"
    "Print it raw instead — the chart's own numbers go to the printer "
    "untouched, with no profile involved. That measures the printer and paper "
    "as they are, which is what a profiling chart needs, but it cannot tell "
    "you anything about how good your profile is.\n\n"
    "Either way ChromIQ does the colour work itself and sends the printer a "
    "finished sheet, with the driver's colour management switched off. You "
    "never have to set anything in the print dialog, and nothing between "
    "ChromIQ and the paper changes the colours.\n\n"
    "Whichever you choose is written on the report, because two prints made "
    "different ways are not comparable.\n\n"
    "Default: print through this run's profile."
)


def _row(parent, label, control, tip_title, tip_body, accent):
    row = QWidget(parent)
    lay = QHBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    text = QLabel(label, row)
    text.setMinimumWidth(150)
    text.setStyleSheet("background:transparent;")
    lay.addWidget(text)
    lay.addWidget(control, 1)
    TooltipButton.ACCENT = accent
    lay.addWidget(TooltipButton(tip_title, tip_body, row))
    return row


def _shell(title_text, accent):
    panel = QWidget()
    panel.setObjectName("mockupPanel")
    panel.setFixedWidth(780)
    outer = QVBoxLayout(panel)
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(12)
    eyebrow = QLabel(title_text, panel)
    eyebrow.setStyleSheet(
        f"color:{accent};font-weight:700;letter-spacing:1px;background:transparent;")
    outer.addWidget(eyebrow)
    return panel, outer


def _finish(panel, name):
    panel.setStyleSheet(panel.styleSheet() +
                        f"\n#mockupPanel{{background:{styles.BG_DARK};}}")
    panel.adjustSize()
    OUT.mkdir(parents=True, exist_ok=True)
    panel.grab().save(str(OUT / name))
    print(f"  wrote {name}  {panel.width()}x{panel.height()}")


def print_row(no_profile: bool = False) -> QWidget:
    """Print Chart ▸ the new row, in the Print tab's amber."""
    A = styles.SPEC_AMBER
    panel, outer = _shell("PRINT CHART · VERIFICATION", A)

    cap = QLabel("Shown only while <b>Run type</b> is Verification.", panel)
    cap.setStyleSheet(f"color:{styles.TEXT_DIM};background:transparent;")
    outer.addWidget(cap)

    group = QGroupBox("How this chart is printed", panel)
    gl = QVBoxLayout(group)
    gl.setContentsMargins(14, 16, 14, 14)
    gl.setSpacing(10)

    choice = QWidget(group)
    cl = QHBoxLayout(choice)
    cl.setContentsMargins(0, 0, 0, 0)
    cl.setSpacing(18)
    through = QRadioButton("Through this run's profile", choice)
    raw = QRadioButton("Raw — no profile applied", choice)
    through.setChecked(not no_profile)
    raw.setChecked(no_profile)
    if no_profile:
        through.setEnabled(False)
    cl.addWidget(through)
    cl.addWidget(raw)
    cl.addStretch(1)
    gl.addWidget(_row(group, "Colour", choice,
                      INTENT_HELP_TITLE, INTENT_HELP_BODY, A))

    intent = QComboBox(group)
    intent.setMinimumHeight(30)
    intent.addItems(["Relative colorimetric (recommended)",
                     "Absolute colorimetric",
                     "Perceptual", "Saturation"])
    intent.setEnabled(not no_profile)
    gl.addWidget(_row(group, "Rendering intent", intent,
                      "Which rendering intent to print with",
                      "Rendering intent decides what happens to colours your "
                      "printer cannot reach.\n\nRelative colorimetric keeps "
                      "every colour it can reach exactly right and pulls the "
                      "rest to the nearest it can manage — the usual choice "
                      "for checking a profile.\n\nAbsolute colorimetric does "
                      "the same but also reproduces the paper white of the "
                      "profile, so a warm paper shows up as an error. Use it "
                      "when you are matching an external absolute "
                      "reference.\n\nThe intent is written on the report, "
                      "because a ΔE means nothing without it.\n\n"
                      "Default: relative colorimetric.", A))
    outer.addWidget(group)

    info = QLabel(panel)
    info.setObjectName("warning")        # amber — the Print tab's own accent
    info.setWordWrap(True)
    if no_profile:
        info.setText(
            "<b>This run has no finished profile yet</b>, so there is nothing "
            "to print through. You can still print the sheet raw, but "
            "measuring it will not tell you how accurate a profile is.<br>"
            "To get there: set <b>Run type</b> to <b>Profiling</b>, measure "
            "the profiling chart, and build the profile on the Build Profile "
            "tab.")
    else:
        info.setText(
            "ChromIQ works out the ink amounts your profile predicts and "
            "prints those. The printer's own colour management stays switched "
            "off, so nothing between here and the paper changes the "
            "colours.<br>The finished sheets are kept in this verification's "
            "<b>cache</b> folder.")
    outer.addWidget(info)

    btn = QPushButton("Print", panel)
    btn.setMinimumHeight(40)
    btn.setStyleSheet(
        f"QPushButton{{background:{A};color:#101010;font-weight:700;"
        "border:none;border-radius:6px;padding:10px;}")
    outer.addWidget(btn)
    return panel


def report_line() -> QWidget:
    """The line the report gains, in the report window's own green."""
    G = styles.SPEC_GREEN
    panel, outer = _shell("MEASUREMENT REPORT · VERIFICATION", G)

    box = QGroupBox("How this verification was produced", panel)
    bl = QVBoxLayout(box)
    bl.setContentsMargins(14, 16, 14, 14)
    bl.setSpacing(6)
    for k, v in (("Printed", "through this run's profile · relative colorimetric"),
                 ("Colour management at the printer", "off (ChromIQ applied the profile)"),
                 ("Reference", "the profile's own prediction for each patch"),
                 ("Formula · illuminant", "CIEDE2000 · D50, 2°")):
        r = QWidget(box)
        rl = QHBoxLayout(r)
        rl.setContentsMargins(0, 0, 0, 0)
        a = QLabel(k, r)
        a.setMinimumWidth(230)
        a.setStyleSheet(f"color:{styles.TEXT_DIM};background:transparent;")
        b = QLabel(v, r)
        b.setStyleSheet("background:transparent;")
        rl.addWidget(a)
        rl.addWidget(b, 1)
        bl.addWidget(r)
    outer.addWidget(box)

    head = QLabel(panel)
    head.setObjectName("info")
    head.setWordWrap(True)
    head.setStyleSheet(
        f"QLabel#info{{background:#0b1f18;color:{G};border:1px solid {G};"
        "border-radius:4px;padding:6px 10px;}")
    head.setText("<b>Average ΔE00 0.46</b> · worst 10% 0.94 · maximum 2.61<br>"
                 "1 050 patches · 8 cube corners reported separately")
    outer.addWidget(head)

    note = QLabel(
        "Two verifications are only comparable when both lines above match.",
        panel)
    note.setWordWrap(True)
    note.setStyleSheet(f"color:{styles.TEXT_DIM};background:transparent;")
    outer.addWidget(note)
    return panel


def info_window(app) -> None:
    """The real ⓘ window, grabbed as the app would draw it."""
    TooltipButton.ACCENT = styles.SPEC_AMBER
    dlg = InfoDialog(INTENT_HELP_TITLE, INTENT_HELP_BODY, None, 520)
    dlg.adjustSize()
    for _ in range(10):
        app.processEvents()
    OUT.mkdir(parents=True, exist_ok=True)
    dlg.grab().save(str(OUT / "cm_2_info.png"))
    print(f"  wrote cm_2_info.png  {dlg.width()}x{dlg.height()}")
    dlg.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))
    app.setPalette(styles.make_dark_palette())
    app.setStyleSheet(styles.APP_STYLESHEET)

    _finish(print_row(False), "cm_1_print.png")
    info_window(app)
    _finish(report_line(), "cm_3_report.png")
    _finish(print_row(True), "cm_4_no_profile.png")
    print(f"\nall four written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
