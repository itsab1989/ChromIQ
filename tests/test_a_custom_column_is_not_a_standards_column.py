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
           "published tolerance values and nothing else" in g
    assert "An editable column named after a standard starts from those " \
           "supplied figures where there are any and from ChromIQ's own " \
           "numbers where there are none" in g


def test_every_clause_of_the_guide_survives_a_licence_holder(tmp_path, qapp):
    """THIS PARAGRAPH HAS BEEN WRONG THREE TIMES, EACH TIME IN A NEW DIRECTION.

    1. "The columns named after a standard hold that standard's published
       tolerance values": false of the two Custom columns.
    2. "A read-only column named after a standard holds that standard's
       published tolerance values": false of the read-only ones as ChromIQ
       ships, because the data file is empty by design.
    3. "those columns are empty, and cannot be chosen unless you hold the
       standard and supply its figures yourself": false in the one state the
       second correction was written to cover. The sixth adversarial round set
       `CHROMIQ_COMPLIANCE_ISO_FILE` and measured the two columns carrying 7
       and 5 numbers, both offered in the pulldown, with the guide inside that
       very report still calling them empty. The paragraph is the same bytes in
       every state, because `_how_to_read_html` never asks what the file holds.
       The second clause had an exception of its own: a run BOUND to an ISO set
       carries that choice to a machine holding no figures at all.

    So the paragraph may not assert emptiness or selectability outright. What
    it says now is conditional, and this test pins the condition rather than
    the sentence.
    """
    g = _guide(tmp_path)
    # The two absolute claims, by their own words.
    assert "those columns are empty" not in g
    assert "cannot be chosen" not in g
    # What replaced them: a condition, not a state.
    assert "such a column is empty unless a licence holder has supplied its " \
           "figures" in g


def test_the_guide_is_true_whether_or_not_the_figures_are_supplied(tmp_path,
                                                                   qapp,
                                                                   monkeypatch):
    """The paragraph is state-independent, so it has to be true in both states.

    Driven here by actually supplying figures the way a licence holder does,
    and checking that what the guide claims still holds.
    """
    import json

    import workflow.compliance_sets as C
    supplied = tmp_path / "iso.json"
    supplied.write_text(json.dumps({
        "iso_12647_7": {"all_de00_avg": 2.5, "substrate_de00_max": 3.0},
        "iso_12647_8": {"all_de00_avg": 4.0},
    }), encoding="utf-8")
    monkeypatch.setenv("CHROMIQ_COMPLIANCE_ISO_FILE", str(supplied))
    monkeypatch.setattr(C, "_iso_cache", None, raising=False)
    monkeypatch.setattr(C, "_iso_problems", [], raising=False)
    try:
        ro = C.effective_limits("iso_12647_7", None)
        assert [r for r in ro.values() if r.is_numeric], (
            "the premise: supplying figures fills the read-only column")
        # "An editable column ... starts from those supplied figures where
        # there are any": the Custom column must take the SUPPLIED number.
        cu = C.factory_limits("custom_iso_12647_7")
        assert cu["all_de00_avg"].is_numeric
        assert abs(cu["all_de00_avg"].number - 2.5) < 1e-9, (
            "the Custom column did not start from the supplied figure, so the "
            "guide's clause about it is false")
        # "...and from ChromIQ's own numbers where there are none": a row the
        # file said nothing about still carries a placeholder.
        assert cu["all_de00_max"].is_numeric
    finally:
        C._iso_cache = None
        C._iso_problems = []


def test_the_two_read_only_columns_really_do_ship_empty(tmp_path, qapp):
    """The sentence above is only true while this is. If ChromIQ ever ships
    those numbers, this fails and the sentence is the thing to rewrite."""
    from workflow.compliance_sets import effective_limits
    for sid in ("iso_12647_7", "iso_12647_8"):
        lims = effective_limits(sid, None)
        assert lims, sid
        assert not [l for l in lims.values() if l.is_numeric], (
            f"{sid} now carries published numbers, so the report's guide must "
            "stop saying ChromIQ ships none of them")


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


def test_the_custom_blurbs_name_both_places_the_numbers_come_from():
    """The blurb said "The starting numbers are ChromIQ's own, not ISO
    12647-7:2016's" and "The two editable columns start from the same
    numbers". Both are true only while the data file is empty.
    `factory_limits` takes ChromIQ's placeholders only where the file supplied
    no number, so with figures supplied custom-7 starts from the 12647-7 block
    and custom-8 from the 12647-8 block, and the two are not the same numbers.
    """
    from workflow.compliance_sets import SET_BY_ID
    for sid, std in (("custom_iso_12647_7", "ISO 12647-7:2016"),
                     ("custom_iso_12647_8", "ISO 12647-8:2021")):
        blurb = SET_BY_ID[sid].blurb
        assert f"published figures of {std}" in blurb, sid
        assert "where a licence holder has supplied them" in blurb, sid
        assert "ChromIQ's own numbers where nobody has" in blurb, sid
        assert "yours to change" in blurb, sid
        # the two claims that were false in the supplied state
        assert "not " + std + "'s" not in blurb, sid
        assert "start from the same numbers" not in blurb, sid


def test_the_custom_blurbs_claim_nothing_about_which_rows_a_standard_limits():
    """The blurb said "The rows ISO 12647-7:2016 writes a limit over", and
    that was false in both directions.

    Measured on the shipped data: four of the eleven rows that carry a number
    are rows that standard writes no limit over, one of them belonging to the
    other standard's structure, and fifteen of the twenty-two it does write a
    limit over are empty. Attributing coverage to a standard it does not have
    is the same class of claim as denying coverage it does, and the app's own
    rule is that ChromIQ makes neither.
    """
    from workflow.compliance_sets import SET_BY_ID
    for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
        blurb = SET_BY_ID[sid].blurb
        assert "writes a limit over" not in blurb, sid
        assert "The rows ISO" not in blurb, sid


def test_the_two_custom_columns_start_identical_only_while_the_file_is_empty():
    """They do, as ChromIQ ships, and the blurb no longer says so BECAUSE that
    stops being true the moment a licence holder supplies figures. Pinned here
    as the fact it is, not as a promise the text makes."""
    from workflow.compliance_sets import effective_limits, limit_bearing
    a = limit_bearing(effective_limits("custom_iso_12647_7", None))
    b = limit_bearing(effective_limits("custom_iso_12647_8", None))
    assert set(a) == set(b)
