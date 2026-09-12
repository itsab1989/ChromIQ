"""The guide must not tell a reader that a "Custom ISO …" column holds that
standard's published tolerance values. It does not: it starts from ChromIQ's
own numbers, because the published ones are not ChromIQ's to ship.

The sentence this pins used to read "The columns named after a standard hold
that standard's published tolerance values applied to the chart you printed".
That is true of the two read-only ISO columns and false of the two Custom ones,
and a reader holding a report headed "Custom ISO 12647-7" was being told the
figures behind it came from ISO. It is the same fault shape as a column that
checked nothing and said PASS: nothing claimed anything, the claim was made by
the arrangement.

What must survive the correction is the cap. Both kinds of column are applied
to the chart the user printed rather than to the standard's own chart and
control strip, so the Overall of either reads COND at best, and
`applies_a_standard` answers True for both.
"""
from __future__ import annotations

import html as _html

import pytest

from tests.test_import_measurement_module import _verify_env


@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _guide(tmp_path):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, fm, ctl, run = _verify_env(tmp_path)
    dlg = MeasurementReportDialog(s, None)
    try:
        return _html.unescape(dlg._how_to_read_html())
    finally:
        dlg.deleteLater()


def test_the_guide_separates_a_published_column_from_a_custom_one(tmp_path,
                                                                  qapp):
    g = _guide(tmp_path)
    assert "read-only column named after a standard holds that standard's " \
           "published tolerance values" in g
    assert "An editable column named after a standard starts from " \
           "ChromIQ's own numbers, not that standard's" in g


def test_the_guide_never_says_a_custom_column_holds_published_values(tmp_path,
                                                                     qapp):
    """The exact wording that was wrong, and the shape of it.

    A sentence saying "columns named after a standard hold that standard's
    published tolerance values" covers the Custom columns by name, because
    "Custom ISO 12647-7" is named after a standard.
    """
    g = _guide(tmp_path)
    assert "The columns named after a standard hold that standard's" not in g


def test_the_cap_survives_the_correction(tmp_path, qapp):
    g = _guide(tmp_path)
    assert "chart you printed" in g
    assert "control strip" in g
    assert "their Overall reads COND at best" in g


def test_both_kinds_still_count_as_applying_a_standard():
    """The correction is about where the numbers came FROM. What caps the
    verdict is what they are applied TO, and that is unchanged for all four."""
    from workflow.compliance_sets import applies_a_standard
    for sid in ("iso_12647_7", "iso_12647_8",
                "custom_iso_12647_7", "custom_iso_12647_8"):
        assert applies_a_standard(sid), sid
    assert not applies_a_standard("chromiq_default")


def test_the_custom_blurbs_say_whose_numbers_they_start_from():
    from workflow.compliance_sets import SET_BY_ID
    for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
        blurb = SET_BY_ID[sid].blurb
        assert "ChromIQ's own numbers" in blurb, sid
        assert "yours to change" in blurb, sid
