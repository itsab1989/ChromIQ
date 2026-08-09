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
  cm_5_reconciled.png  the whole reconciled section: Colour + Intent + Route,
                       which supersedes the two-row proposal in #133 section 8
  cm_6_already.png     a chart from #133's module, which already has the profile
                       applied: the option is DISABLED, not merely deselected
  cm_7_raw_chosen.png  the mirror case -- a REGULAR verification chart with raw
                       chosen. Nothing is disabled: raw is a different question,
                       not an error, so the notice names the question

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

from ui.tabs.tab_print import (                                    # noqa: E402
    _CM_COLOUR_HELP_BODY as INTENT_HELP_BODY,
    _CM_COLOUR_HELP_TITLE as INTENT_HELP_TITLE,
    _CM_INTENT_HELP_BODY,
    _CM_INTENT_HELP_TITLE,
    _CM_NOTICE_ALREADY_CONVERTED,
    _CM_NOTICE_NO_PROFILE,
    _CM_NOTICE_RAW_CHOSEN,
    _CM_NOTICE_THROUGH,
    _CM_ROUTE_HELP_BODY,
    _CM_ROUTE_HELP_TITLE,
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
    through = QRadioButton("Through the profile", choice)
    raw = QRadioButton("Raw — no profile", choice)
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
                      _CM_INTENT_HELP_TITLE, _CM_INTENT_HELP_BODY, A))
    outer.addWidget(group)

    info = QLabel(panel)
    info.setObjectName("warning")        # amber — the Print tab's own accent
    info.setWordWrap(True)
    info.setText(_CM_NOTICE_NO_PROFILE if no_profile else _CM_NOTICE_THROUGH)
    outer.addWidget(info)

    btn = QPushButton("Print", panel)
    btn.setMinimumHeight(40)
    btn.setStyleSheet(
        f"QPushButton{{background:{A};color:#101010;font-weight:700;"
        "border:none;border-radius:6px;padding:10px;}")
    outer.addWidget(btn)
    return panel


def reconciled_section() -> QWidget:
    """The full Print Chart section of the plan's section 4.

    #133 section 8 proposed Route and "Recorded on the report"; feature A
    proposes Colour and Rendering intent. Four rows from two documents would be
    incoherent, so this is the reconciliation: three rows, and the recording
    becomes a consequence rather than a fourth control.
    """
    A = styles.SPEC_AMBER
    panel, outer = _shell("PRINT CHART · THE RECONCILED SECTION", A)

    cap = QLabel(
        "<b>Colour</b> and <b>Rendering intent</b> appear only for a "
        "verification. <b>Route</b> is shown for every chart.", panel)
    cap.setWordWrap(True)
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
    a = QRadioButton("Through the profile", choice)
    a.setChecked(True)
    b = QRadioButton("Raw — no profile", choice)
    cl.addWidget(a)
    cl.addWidget(b)
    cl.addStretch(1)
    gl.addWidget(_row(group, "Colour", choice,
                      INTENT_HELP_TITLE, INTENT_HELP_BODY, A))

    intent = QComboBox(group)
    intent.setMinimumHeight(30)
    intent.addItems(["Relative colorimetric (recommended)",
                     "Absolute colorimetric", "Perceptual", "Saturation"])
    gl.addWidget(_row(group, "Rendering intent", intent,
                      "Which rendering intent to print with",
                      "See the Dictionary entry for rendering intent.", A))

    route = QWidget(group)
    rl = QHBoxLayout(route)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(18)
    here = QRadioButton("Print here", route)
    here.setChecked(True)
    away = QRadioButton("In another application", route)
    rl.addWidget(here)
    rl.addWidget(away)
    rl.addStretch(1)
    gl.addWidget(_row(group, "Route", route,
                      _CM_ROUTE_HELP_TITLE, _CM_ROUTE_HELP_BODY, A))
    outer.addWidget(group)

    rec = QLabel(panel)
    rec.setObjectName("warning")
    rec.setWordWrap(True)
    rec.setText(
        "<b>Recorded on the report automatically.</b> ChromIQ already knows "
        "both answers above, so it writes them onto the report itself rather "
        "than asking you a third time — how the sheet was prepared, and who "
        "printed it. Two verifications only compare with each other when both "
        "were made the same way.")
    outer.addWidget(rec)
    return panel


def already_converted() -> QWidget:
    """Print Chart when the loaded chart already carries the profile (§3.1a).

    A #133 FROM PROFILE GAMUT chart was converted with xicclu when it was made,
    so converting again would print different colours from the ones being
    tested -- silently. The option is disabled rather than defaulted, following
    the pattern Knut chose for the Build Profile tab in a verification run.
    """
    A = styles.SPEC_AMBER
    panel, outer = _shell("PRINT CHART · A CHART THAT IS ALREADY CONVERTED", A)

    cap = QLabel(
        "Shown when the loaded chart carries stored colorimetric targets — "
        "i.e. it came from the <b>From profile gamut</b> module.", panel)
    cap.setWordWrap(True)
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
    through = QRadioButton("Through the profile", choice)
    through.setEnabled(False)
    # Short enough not to elide: the notice below carries the explanation.
    raw = QRadioButton("Raw — already converted", choice)
    raw.setChecked(True)
    cl.addWidget(through)
    cl.addWidget(raw)
    cl.addStretch(1)
    gl.addWidget(_row(group, "Colour", choice,
                      "Printing a chart that already has your profile applied",
                      "This chart was built by asking your profile which ink "
                      "amounts produce each of the colours being tested, so "
                      "the sheet is already your profile\u2019s own "
                      "prediction.\n\nThere is nothing left to convert, which "
                      "is why the other choice is switched off. Applying the "
                      "profile a second time would print different colours "
                      "from the ones being tested, and nothing afterwards "
                      "could tell that it had happened.\n\nPrint as usual.",
                      A))

    intent = QComboBox(group)
    intent.setMinimumHeight(30)
    intent.addItems(["Relative colorimetric (recommended)"])
    intent.setEnabled(False)
    gl.addWidget(_row(group, "Rendering intent", intent,
                      "Not used for this chart",
                      "The rendering intent was chosen when this chart was "
                      "created, and is stored with it. Nothing is converted "
                      "at print time, so there is nothing to choose here.", A))
    outer.addWidget(group)

    info = QLabel(panel)
    info.setObjectName("warning")
    info.setWordWrap(True)
    info.setText(_CM_NOTICE_ALREADY_CONVERTED)
    outer.addWidget(info)
    return panel


def raw_chosen() -> QWidget:
    """A regular verification chart with "raw" selected (§3.1b).

    The mirror of cm_6, and deliberately NOT symmetric with it. Printing a
    regular verification chart raw is a legitimate drift check, not an error, so
    nothing is disabled -- the notice explains which question the sheet will
    answer instead of forbidding the choice.
    """
    A = styles.SPEC_AMBER
    panel, outer = _shell("PRINT CHART · A REGULAR VERIFICATION, PRINTED RAW", A)

    cap = QLabel(
        "Nothing is disabled here. Printing raw answers a different question — "
        "it is not a mistake.", panel)
    cap.setWordWrap(True)
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
    through = QRadioButton("Through the profile", choice)
    raw = QRadioButton("Raw — no profile", choice)
    raw.setChecked(True)
    cl.addWidget(through)
    cl.addWidget(raw)
    cl.addStretch(1)
    gl.addWidget(_row(group, "Colour", choice,
                      INTENT_HELP_TITLE, INTENT_HELP_BODY, A))

    intent = QComboBox(group)
    intent.setMinimumHeight(30)
    intent.addItems(["Relative colorimetric (recommended)"])
    intent.setEnabled(False)
    gl.addWidget(_row(group, "Rendering intent", intent,
                      "Not used when printing raw",
                      "No profile is applied when printing raw, so there is no "
                      "rendering intent to choose. Pick \u201cThrough this "
                      "run\u2019s profile\u201d above to use one.", A))
    outer.addWidget(group)

    info = QLabel(panel)
    info.setObjectName("warning")
    info.setWordWrap(True)
    info.setText(_CM_NOTICE_RAW_CHOSEN)
    outer.addWidget(info)
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
    _finish(reconciled_section(), "cm_5_reconciled.png", styles.SPEC_AMBER)
    _finish(already_converted(), "cm_6_already.png", styles.SPEC_AMBER)
    _finish(raw_chosen(), "cm_7_raw_chosen.png", styles.SPEC_AMBER)
    print(f"\nall seven written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
