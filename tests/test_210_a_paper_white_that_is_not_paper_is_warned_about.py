"""#210: a Measurement Report whose paper white is not a reading of the paper.

The forum user's SELPHY report took paper white from patch 7D at L* 43, a*
50, b* 43 (an orange): strip 7 had been read one patch out. Basti: warn
clearly, which patch, its values, why it looks wrong, and keep going; coloured
papers must still work.

The rule (`measurement_report.paper_white_doubt`): ink only darkens paper, so
the patch printed with no ink is the lightest reading of its sheet whatever
the paper's colour. Another reading more than PAPER_WHITE_DOUBT_DL (8 L*)
lighter puts it in doubt.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M          # noqa: E402
from workflow import measurement_report as MR           # noqa: E402

LOCS = ["A1", "A2", "A3", "A4"]


def test_the_threshold_is_documented_and_eight():
    assert MR.PAPER_WHITE_DOUBT_DL == 8.0


def test_the_forum_users_paper_white_is_doubted():
    lab = [(43.36, 50.21, 43.06),    # 7D, the misread paper patch
           (94.0, 3.3, 12.2),        # a reading of the bare paper elsewhere
           (25.0, 16.3, -29.7), (61.9, 48.0, 29.9)]
    d = MR.paper_white_doubt(lab, 0, LOCS)
    assert d == {"lighter_loc": "A2", "lighter_L": 94.0, "dl": 50.64}


def test_a_white_paper_read_well_is_not_doubted():
    lab = [(95.2, 0.4, -3.1), (95.6, 0.2, -2.0), (40.0, 30.0, 10.0),
           (10.0, 0.0, 0.0)]
    # a pale patch a little lighter than the paper (noise, a fluorescent
    # paper): within the 8 L*
    assert MR.paper_white_doubt(lab, 0, LOCS) is None


def test_a_coloured_paper_is_not_doubted():
    """A strongly coloured paper (yellow, L* 82, b* 60): every patch carries
    its colour and none is lighter, so nothing is said."""
    lab = [(82.0, -4.0, 60.0), (70.0, 10.0, 55.0), (50.0, 30.0, 40.0),
           (20.0, 5.0, 10.0)]
    assert MR.paper_white_doubt(lab, 0, LOCS) is None


def test_no_paper_patch_no_doubt():
    assert MR.paper_white_doubt([(50.0, 0.0, 0.0)], None, LOCS[:1]) is None


def _report(doubt=True):
    r = {"paper_white": {"loc": "7D", "lab": [43.36, 50.21, 43.06],
                         "hex": "#b63921"},
         "max_black": {"loc": "6G", "lab": [13.88, 0.8, -2.0],
                       "hex": "#22232a"}}
    if doubt:
        r["paper_white_doubt"] = {"lighter_loc": "15B", "lighter_L": 94.3,
                                  "dl": 50.94}
    return r


def test_the_report_says_which_patch_its_values_and_why(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    out = MeasurementReportDialog._paper_white_doubt_html(_report())
    head, body = M.M_REPORT_PAPER_WHITE_DOUBT.render(
        loc="7D", L="43.4", a="50.2", b="43.1", lighter_loc="15B",
        lighter_L="94.3", dl="50.9")
    assert head in out
    for bit in ("7D", "L* 43.4, a* 50.2, b* 43.1", "15B", "94.3", "50.9",
                "Ink can only make paper darker"):
        assert bit in out, bit


def test_no_doubt_no_warning(qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    assert MeasurementReportDialog._paper_white_doubt_html(
        _report(doubt=False)) == ""


def test_measurement_facts_records_it(tmp_path):
    """End to end through the one function the report and its saved record
    share: a .ti3 whose paper patch (RGB 100,100,100) reads orange."""
    ti3 = tmp_path / "m.ti3"
    rows = [("1", "A1", 100, 100, 100, 30.7, 17.6, 2.3),     # paper, misread
            ("2", "A2", 50, 50, 50, 20.0, 21.0, 18.0),
            ("3", "A3", 0, 0, 0, 1.0, 1.0, 1.0),
            ("4", "A4", 90, 90, 90, 80.0, 84.0, 70.0)]       # L* ~93.5
    ti3.write_text(
        "CTI3\n\nDESCRIPTOR \"x\"\nCOLOR_REP \"RGB_XYZ\"\n\n"
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 4\nBEGIN_DATA\n"
        + "".join(f'{a} "{b}" {c} {d} {e} {f} {g} {h}\n'
                  for a, b, c, d, e, f, g, h in rows)
        + "END_DATA\n", encoding="utf-8")
    facts = MR.measurement_facts(ti3)
    assert facts["paper_white"]["loc"] == "A1"
    assert facts["paper_white_doubt"]["lighter_loc"] == "A4"
