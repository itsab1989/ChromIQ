"""A cube corner the chart has no patch at borrows nothing from the patch
nearest to it — B8-290.

**THE FAULT, REPORTED ON A DEMO PROJECT AND REPRODUCED FROM ITS OWN SAVED
REPORT.** `measurement_report.build_report` finds each of the eight cube
corners by taking the NEAREST patch in device RGB and then asks whether that
patch is really at the corner (`CORNER_PRESENT_TOL`, 12 device units). When it
is not, the entry is marked ``present: False`` and the Report Scope warns that
the corner is missing — but every other field on the entry still described the
stand-in, and three surfaces printed them as the corner's own:

* the per-run **Cube corners** table drew the stand-in's measured colour, the
  stand-in's reference colour and the stand-in's ΔE00 beside the word
  "(missing)", and named the stand-in's patch number;
* the side-by-side **comparison** table carried the same ΔE00 with no
  "(missing)" mark anywhere to warn with;
* the **trend** chart plotted it as that ink's drift over time.

On the reported sheet Red and Blue both resolved to patch 14, a neutral grey,
so one grey patch answered for two inks with the same ΔE00 of 2.46, and Cyan
resolved to a green patch. The corner block in :data:`_REPORTED` is that
project's own, copied out of the report it wrote.

**WHAT IS NOT WRONG, AND IT MATTERS.** The compliance rows in
`measurement_report.row_values` already gate every corner on ``present``, so no
judged number and no verdict word was ever taken from a stand-in. This is a
reporting fault on three display surfaces, which is why it can be fixed here
rather than in the builder — and fixing it at the reading end repairs every
report already on disk, where the stand-in's fields are written into the JSON.

**THE REMEDY IS THE DESIGN AUTHORITY'S OWN**, 2026-09-17: *"When the colors are
missing, the expected should still show the ideal cube colour, the measured and
the DeltaE columns could show only a dash to indicate it is not present or
measured. The '(missing)' in first column is good as indication."* The patch
NUMBER goes too, which is one step past his words and is said so in B8-290: it
is the same stand-in making the same claim, and it was what made one patch
visibly answer for two corners.
"""
from __future__ import annotations

import copy
import html as _html
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_report as mr             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


#: The eight corner entries out of the reported project's own saved report,
#: verbatim but for the long float tails. Red and Blue share patch 14 and its
#: ΔE00 of 2.46; Cyan is a green patch at 20.
_REPORTED: "list[dict]" = [
    {"name": "W", "loc": "1", "rgb": [100.0, 100.0, 100.0],
     "lab": [100.0, -0.0, 0.03], "hex": "#ebffff", "present": True,
     "expected_lab": [100.0, 0.11, 0.03], "expected_hex": "#ffffff",
     "de": 0.17},
    {"name": "K", "loc": "5", "rgb": [0.0, 0.0, 0.0],
     "lab": [9.02, 0.43, 0.28], "hex": "#171a1f", "present": True,
     "expected_lab": [9.02, 1.95, 1.25], "expected_hex": "#1d1918",
     "de": 2.27},
    {"name": "R", "loc": "14", "rgb": [33.3, 33.3, 33.3],
     "lab": [37.84, -1.15, -0.6], "hex": "#4f5b69", "present": False,
     "expected_lab": [37.84, 0.43, 0.25], "expected_hex": "#5a5959",
     "de": 2.46},
    {"name": "G", "loc": "19", "rgb": [0.0, 100.0, 0.0],
     "lab": [87.82, -81.72, 80.91], "hex": "#00ff3b", "present": True,
     "expected_lab": [87.96, -77.85, 79.05], "expected_hex": "#1dff18",
     "de": 0.8},
    {"name": "B", "loc": "14", "rgb": [33.3, 33.3, 33.3],
     "lab": [37.84, -1.15, -0.6], "hex": "#4f5b69", "present": False,
     "expected_lab": [37.84, 0.43, 0.25], "expected_hex": "#5a5959",
     "de": 2.46},
    {"name": "C", "loc": "20", "rgb": [33.8, 87.9, 43.7],
     "lab": [80.21, -59.29, 43.59], "hex": "#2ce387", "present": False,
     "expected_lab": [80.22, -55.28, 42.45], "expected_hex": "#5be172",
     "de": 1.1},
    {"name": "M", "loc": "17", "rgb": [100.0, 0.0, 100.0],
     "lab": [60.47, 97.21, -60.44], "hex": "#f508ff", "present": True,
     "expected_lab": [60.81, 91.87, -59.45], "expected_hex": "#ff19ff",
     "de": 1.1},
    {"name": "Y", "loc": "18", "rgb": [100.0, 100.0, 0.0],
     "lab": [97.48, -17.18, 92.23], "hex": "#f6ff42", "present": True,
     "expected_lab": [97.63, -15.47, 91.48], "expected_hex": "#ffff18",
     "de": 0.8},
]

#: The stand-in fields that must never reach a missing corner's row.
_STANDIN_MEASURED_HEX = "#4f5b69"      # the grey patch 14 came back as
_STANDIN_EXPECTED_HEX = "#5a5959"      # what patch 14 was asked for
_STANDIN_CYAN_HEX = "#2ce387"          # the green patch 20 came back as


def _report(corners=None) -> dict:
    return {
        "schema": mr.REPORT_SCHEMA, "created": "2026-12-01T10:00:00",
        "chart": "P-verify", "patches": 24, "reference_source": "design",
        "corners": copy.deepcopy(_REPORTED if corners is None else corners),
    }


def _dialog(tmp_path, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return MeasurementReportDialog(s, None)


def _corner_rows(detail: str) -> "dict[str, str]":
    """``{corner label: that row's HTML}`` out of the cube-corners table."""
    i = detail.find("Cube corners (ΔE00)")
    assert i > 0, "the cube-corners table is not in this report"
    body = detail[i:]
    end = body.find("</table>")
    assert end > 0
    out: "dict[str, str]" = {}
    for row in body[:end].split("<tr")[1:]:
        for label in ("White", "Black", "Red", "Green", "Blue", "Cyan",
                      "Magenta", "Yellow"):
            if f"<td>{label} " in row or f"<td>{label}<" in row:
                out[label] = row
                break
    return out


# --------------------------------------------------------------- the table


def test_a_missing_corner_shows_the_ideal_colour_and_no_measurement(
        qapp, tmp_path):
    """Red, Blue and Cyan: the ideal ink under Expected, dashes for the rest."""
    dlg = _dialog(tmp_path, qapp)
    try:
        rows = _corner_rows(dlg._run_detail_html(_report()))
    finally:
        dlg.deleteLater()
    for label, ideal in (("Red", "#ff0000"), ("Blue", "#0000ff"),
                         ("Cyan", "#00ffff")):
        row = rows[label]
        assert "(missing)" in row, label
        assert ideal in row.lower(), (
            f"{label} must show its IDEAL cube colour under Expected; "
            f"the row is {row}")
        # Neither the stand-in's measurement nor the stand-in's reference.
        for borrowed in (_STANDIN_MEASURED_HEX, _STANDIN_EXPECTED_HEX,
                         _STANDIN_CYAN_HEX):
            assert borrowed not in row.lower(), (
                f"{label} still carries the stand-in patch's colour "
                f"{borrowed}: {row}")
        # And no ΔE00, which on the reported sheet was 2.46 twice and 1.10.
        for borrowed_de in ("2.46", "1.10", "1.1<"):
            assert borrowed_de not in row, (
                f"{label} still carries a ΔE00 of a patch it does not have: "
                f"{row}")
        assert _html.unescape(row).count("—") >= 2, (
            f"{label} must dash BOTH Measured and ΔE00: {row}")


def test_a_missing_corner_names_no_patch_number(qapp, tmp_path):
    """One patch answering for two corners is what made this visible."""
    dlg = _dialog(tmp_path, qapp)
    try:
        rows = _corner_rows(dlg._run_detail_html(_report()))
    finally:
        dlg.deleteLater()
    for label in ("Red", "Blue", "Cyan"):
        assert "(14)" not in rows[label] and "(20)" not in rows[label], (
            f"{label} is missing, so it has no patch to name: {rows[label]}")


def test_a_present_corner_keeps_its_swatches_and_its_delta_e(qapp, tmp_path):
    """THE FIX MUST NOT BLANK THE FIVE CORNERS THE SHEET REALLY CARRIES."""
    dlg = _dialog(tmp_path, qapp)
    try:
        rows = _corner_rows(dlg._run_detail_html(_report()))
    finally:
        dlg.deleteLater()
    for label, meas, exp, de in (("White", "#ebffff", "#ffffff", "0.17"),
                                 ("Black", "#171a1f", "#1d1918", "2.27"),
                                 ("Green", "#00ff3b", "#1dff18", "0.80"),
                                 ("Magenta", "#f508ff", "#ff19ff", "1.10"),
                                 ("Yellow", "#f6ff42", "#ffff18", "0.80")):
        row = rows[label].lower()
        assert "(missing)" not in row
        assert meas in row and exp in row, label
        assert de in rows[label], f"{label} lost its ΔE00: {rows[label]}"


def test_the_ideal_swatch_follows_the_cube_corner_table(qapp, tmp_path):
    """The eight ideals are DERIVED, so the two tables cannot drift apart."""
    from ui.dialogs.measurement_report_dialog import _corner_ideal_hex
    want = {"W": "#ffffff", "K": "#000000", "R": "#ff0000", "G": "#00ff00",
            "B": "#0000ff", "C": "#00ffff", "M": "#ff00ff", "Y": "#ffff00"}
    for name, rgb in mr.CUBE_CORNERS:
        assert _corner_ideal_hex(name) == want[name], name
        # …and it really is that corner's own device value, read as sRGB.
        assert _corner_ideal_hex(name) == "#" + "".join(
            f"{int(round(v * 255.0 / 100.0)):02x}" for v in rgb)
    assert _corner_ideal_hex("nope") == ""


# ---------------------------------------------------- the comparison table


def test_the_comparison_table_dashes_a_missing_corner(qapp, tmp_path):
    """That table has no "(missing)" mark, so a borrowed number is unmarked."""
    dlg = _dialog(tmp_path, qapp)
    try:
        table = _html.unescape(dlg._comparison_table_html([_report()]))
    finally:
        dlg.deleteLater()
    assert "Cyan" in table, "the comparison table did not render its corners"
    # 2.46 is patch 14's, quoted twice for Red and Blue; 1.10 is Magenta's own
    # and must survive, so only the pair that belongs to nobody is counted.
    assert "2.46" not in table, (
        "the comparison table still carries the stand-in patch's ΔE00")


def test_the_comparison_table_keeps_a_present_corner(qapp, tmp_path):
    dlg = _dialog(tmp_path, qapp)
    try:
        table = _html.unescape(dlg._comparison_table_html([_report()]))
    finally:
        dlg.deleteLater()
    for de in ("0.17", "2.27", "0.80", "1.10"):
        assert de in table, f"a present corner lost its ΔE00 ({de})"


# ------------------------------------------------------------- the trend


def test_the_trend_never_plots_a_corner_the_chart_has_no_patch_at():
    """Red and Blue would otherwise draw the SAME line, from one grey patch."""
    pts = mr.report_trend([_report()])
    assert pts, "the trend produced no point at all"
    corners = pts[0].get("corners") or {}
    assert set(corners) == {"W", "K", "G", "M", "Y"}, (
        f"the trend plots a corner the chart has no patch at: {sorted(corners)}")
    assert corners["W"] == 0.17 and corners["K"] == 2.27


def test_the_trend_keeps_a_report_whose_corners_are_all_present():
    allp = [dict(c, present=True) for c in _REPORTED]
    pts = mr.report_trend([_report(allp)])
    assert set((pts[0].get("corners") or {})) == set("WKRGBCMY")


def test_an_older_report_without_the_present_flag_is_not_silently_dropped():
    """`present` absent = an older report: keep plotting it, as before."""
    old = [{k: v for k, v in c.items() if k != "present"} for c in _REPORTED]
    pts = mr.report_trend([_report(old)])
    assert set((pts[0].get("corners") or {})) == set("WKRGBCMY")


def test_an_older_report_without_the_present_flag_still_draws_its_swatches(
        qapp, tmp_path):
    old = [{k: v for k, v in c.items() if k != "present"} for c in _REPORTED]
    dlg = _dialog(tmp_path, qapp)
    try:
        rows = _corner_rows(dlg._run_detail_html(_report(old)))
    finally:
        dlg.deleteLater()
    assert "(missing)" not in "".join(rows.values())
    assert _STANDIN_MEASURED_HEX in rows["Red"].lower()


# ------------------------------------------------- what was NEVER affected


def test_no_judged_row_ever_took_a_number_from_a_stand_in():
    """The compliance rows already gated on `present`, and still do.

    Written as a check rather than a comment because it is the reason this
    fault is a reporting one: had `row_values` been reading the stand-in, a
    verdict word would have been wrong and the fix would not have belonged in
    the report window at all.
    """
    rep = _report()
    rep["reference_source"] = "colorimetric"
    vals = mr.row_values(rep)
    # Cyan is the missing one of C/M/Y/K here, so the solids row must be the
    # worst of the three that ARE present (K 2.27, M 1.10, Y 0.80) and must
    # not have taken Cyan's borrowed 1.10 from patch 20.
    solids = vals.get("solids_de00_max")
    assert solids and solids["value"] == 2.27, solids
    hue = vals.get("cmy_solids_dhab_max")
    assert hue and hue["value"] is not None
    # …and with every corner of that group gone the row withholds itself.
    gone = [dict(c, present=(c["name"] in ("W", "G"))) for c in _REPORTED]
    v2 = mr.row_values(_report(gone) | {"reference_source": "colorimetric"})
    assert (v2.get("solids_de00_max") or {}).get("value") is None
