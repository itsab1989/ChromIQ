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
from ui.dialogs.tools_dialogs import neutral_controls_qss          # noqa: E402
from ui.tooltip_button import InfoDialog, TooltipButton            # noqa: E402

OUT = ROOT / "docs" / "mockups" / "cm130"

INTENT_HELP_TITLE = "Printing this chart through your profile"
INTENT_HELP_BODY = (
    "This decides how the colours on this sheet are worked out before it is "
    "printed — and it is the setting that makes a verification mean "
    "something.\n\n"
    "What a verification is for. When you built your profile, you taught "
    "ChromIQ how your printer and this paper behave together. A verification "
    "asks the follow-up question: does the printer still do what the profile "
    "says it does? Ink settles, paper batches differ, printheads age — so it "
    "is worth checking, and worth checking the same way every time.\n\n"
    "Through this run's profile (recommended). ChromIQ looks up, for every "
    "single patch on the sheet, the exact amount of each ink your profile "
    "predicts will produce that colour. Those amounts are what gets printed. "
    "So the sheet coming out of your printer is your profile's own prediction, "
    "made real — and when you measure it, the difference between what was "
    "promised and what landed on the paper is exactly the number you are "
    "looking for. Pick this one unless you have a particular reason not to.\n\n"
    "Raw — no profile applied. The chart's own numbers go to the printer "
    "untouched, with no profile involved anywhere. This is the right way to "
    "print a chart you are going to build a profile from, because it shows "
    "the printer's raw behaviour. It is the wrong way to check a profile, "
    "because no profile took part — the measurement would describe your "
    "printer, not the profile you wanted to test.\n\n"
    "You do not have to change anything in the print dialog. Whichever you "
    "choose, ChromIQ does all of the colour work itself and hands the printer "
    "a finished sheet, with the printer's own colour adjustment switched off. "
    "That is deliberate: if the printer driver also tried to adjust the "
    "colours, they would be converted twice, the sheet would be wrong, and "
    "nothing afterwards could tell that it had happened.\n\n"
    "Your choice is written onto the report next to the results, because two "
    "sheets printed different ways cannot be compared with each other — and "
    "six months from now, nobody remembers which way a sheet was printed.\n\n"
    "Default: through this run\u2019s profile."
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


def _finish(panel, name, accent=None):
    extra = neutral_controls_qss(accent) if accent else ""
    panel.setStyleSheet(panel.styleSheet() + extra +
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
                      "Your printer cannot make every colour that exists — no "
                      "printer can. Rendering intent is the rule for what "
                      "happens to the colours it cannot reach.\n\n"
                      "Relative colorimetric (recommended). Every colour your "
                      "printer can actually make is reproduced exactly, and "
                      "the few it cannot reach are moved to the closest colour "
                      "it can manage. Paper white is treated as white. This is "
                      "the usual choice for checking a profile, because it "
                      "asks \u201cdid you hit the colours you could hit?\u201d "
                      "without punishing the printer for the ones nobody could "
                      "print.\n\n"
                      "Absolute colorimetric. The same, except that the "
                      "paper\u2019s own shade counts too. If your paper is "
                      "slightly warm or slightly blue, that shows up as an "
                      "error on every patch, so the numbers come out higher. "
                      "Choose this when you have to match figures somebody "
                      "else produced this way, or when the exact paper white "
                      "matters to you.\n\n"
                      "Perceptual and Saturation are meant for photographs and "
                      "graphics rather than for measurement. They deliberately "
                      "shift colours to look pleasing, which is the opposite "
                      "of what a measurement wants, so they are here for "
                      "completeness rather than for everyday use.\n\n"
                      "Whichever you pick is written on the report, because a "
                      "colour difference means nothing unless you know how it "
                      "was produced.\n\n"
                      "Default: relative colorimetric.", A))
    outer.addWidget(group)

    info = QLabel(panel)
    info.setObjectName("warning")        # amber — the Print tab's own accent
    info.setWordWrap(True)
    if no_profile:
        info.setText(
            "<b>There is no finished profile in this run yet</b>, so there is "
            "nothing for ChromIQ to print through. You can still print this "
            "sheet raw and measure it — but the result would describe your "
            "printer, not a profile, so it cannot tell you how accurate a "
            "profile is.<br><br>"
            "To get there: set <b>Run type</b> to <b>Profiling</b>, then "
            "create, print and measure the profiling chart as usual, and "
            "build the profile on the <b>Build Profile</b> tab. Come back "
            "here afterwards and this option will be waiting for you.")
    else:
        info.setText(
            "ChromIQ will work out the ink amounts your profile predicts for "
            "every patch and print exactly those, so the sheet is your "
            "profile\u2019s own prediction made real. The printer\u2019s own "
            "colour adjustment stays switched off, so nothing between here "
            "and the paper changes the colours.<br><br>"
            "You do not need to change any colour setting in the print "
            "dialog. The finished sheets are kept in this "
            "verification\u2019s <b>cache</b> folder, which is always safe "
            "to delete.")
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

    _finish(print_row(False), "cm_1_print.png", styles.SPEC_AMBER)
    info_window(app)
    _finish(report_line(), "cm_3_report.png", styles.SPEC_GREEN)
    _finish(print_row(True), "cm_4_no_profile.png", styles.SPEC_AMBER)
    print(f"\nall four written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
