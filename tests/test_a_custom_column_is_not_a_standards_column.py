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

What must survive the correction is the CAVEAT. Both kinds of column are
applied to the chart the user printed rather than to the standard's own chart
and control strip, and `applies_a_standard` answers True for both.

It was the CAP until 2026-09-22: such a column's Overall read COND at best, and
that word was half of what stopped a green PASS under a standard's name
standing unqualified. Knut retired it that day, so the sentence about what the
values are applied to is now the whole of it, and this file asks for that
sentence where it used to ask for the word.
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
        # A report judged against a standard's set: since R2 of beta 39 (#2)
        # the paragraph about such a column is printed only there.
        return _html.unescape(dlg._how_to_read_html(standard=True))
    finally:
        dlg.deleteLater()


def test_the_guide_separates_a_published_column_from_a_custom_one(tmp_path,
                                                                  qapp):
    g = _guide(tmp_path)
    # K18 (Knut, 2026-09-23): the report may reach a customer, so it no
    # longer explains where ChromIQ gets a column's numbers (licensing,
    # supplied figures, "yours to change"). What it keeps is the one claim
    # true of both kinds in every state: a column named after a standard may
    # not hold that standard's published values.
    # R2 of beta 39 (#2): "may differ" was false of a read-only ISO column
    # once §23 ships its values; what is true of both kinds is what they were
    # applied to.
    assert "is judged against its limit set's limits" in g
    assert "may differ from the standard's published values" not in g
    assert "holds that standard's published tolerance values" not in g


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
    # What replaced them, since K18 (2026-09-23): a claim that is true
    # whether or not figures were supplied, and names no ChromIQ mechanism.
    assert "applied to the values measured on the printed test chart" in g
    assert "licence holder" not in g


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
        # Since 2026-09-24 (Knut, #182 5815346140, B8-978) a Custom column
        # never takes a supplied figure: it is an alternative to the standard
        # and starts from the industry defaults whatever file is present.
        cu = C.factory_limits("custom_iso_12647_7")
        assert cu["all_de00_avg"] == C.custom_defaults("iso_12647_7")["all_de00_avg"], (
            "the Custom column took the supplied figure; it must start from "
            "the industry defaults")
        # "...and from ChromIQ's own numbers where there are none": a row the
        # file said nothing about still carries a placeholder.
        assert cu["all_de00_max"].is_numeric
    finally:
        C._iso_cache = None
        C._iso_problems = []


def test_the_two_read_only_columns_hold_numbers_only_where_they_ship(tmp_path,
                                                                   qapp):
    """A read-only column carries numbers exactly when its set ships.

    This used to assert that both columns ship empty, and to say that the day
    ChromIQ ships the numbers the sentence above is the thing to rewrite. That
    day is prepared (#182 S-2, §23), and the guide's sentence was rewritten
    for it in K18: "may differ from the standard's published values" is true
    in both states, which `test_every_clause_of_the_guide_survives_a_licence_
    holder` pins. What is left to hold is the link between the file and the
    column.
    """
    import json

    from workflow import compliance_sets as C
    from workflow.compliance_sets import effective_limits
    doc = json.loads(C.resource_path(C.ISO_DATA_FILE).read_text(encoding="utf-8"))
    for sid in ("iso_12647_7", "iso_12647_8"):
        lims = effective_limits(sid, None)
        assert lims, sid
        numeric = [l for l in lims.values() if l.is_numeric]
        assert bool(numeric) == bool(doc[sid]), (
            f"{sid}: the shipped file {'carries' if doc[sid] else 'leaves empty'} "
            f"that set, and its read-only column has {len(numeric)} numbers")


def test_the_guide_never_says_a_custom_column_holds_published_values(tmp_path,
                                                                     qapp):
    """The exact wording that was wrong, and the shape of it.

    A sentence saying "columns named after a standard hold that standard's
    published tolerance values" covers the Custom columns by name, because
    "Custom ISO 12647-7" is named after a standard.
    """
    g = _guide(tmp_path)
    assert "The columns named after a standard hold that standard's" not in g


def test_the_caveat_survives_the_correction(tmp_path, qapp):
    """It was `test_the_cap_survives_the_correction` until 2026-09-22.

    The correction this file is about rewrote where a Custom column's numbers
    come FROM. What it must not quietly take with it is the sentence about
    what they are applied TO, which was the reason the column was capped at
    COND. Knut retired the cap that day and the sentence is now the whole of
    the qualification, so the third assertion follows it rather than the word.
    """
    g = _guide(tmp_path)
    assert "printed test chart" in g       # K18: was "chart you printed"
    assert "control strip" in g
    assert "what that word does and does not mean" in g
    assert "would likely meet" not in g
    assert "COND at best" not in g, (
        "the retired ISO cap is being taught again by the report's guide")


def test_both_kinds_still_count_as_applying_a_standard():
    """The correction is about where the numbers came FROM. What earns the
    caveat is what they are applied TO, and that is unchanged for all four.
    Since the cap was retired this predicate decides whether the caveat note
    is printed at all, so it carries the whole promise rather than half."""
    from workflow.compliance_sets import applies_a_standard
    for sid in ("iso_12647_7", "iso_12647_8",
                "custom_iso_12647_7", "custom_iso_12647_8"):
        assert applies_a_standard(sid), sid
    assert not applies_a_standard("chromiq_default")


def test_the_custom_blurbs_name_every_place_the_numbers_come_from():
    """The blurb said "The starting numbers are ChromIQ's own, not ISO
    12647-7:2016's" and "The two editable columns start from the same
    numbers". Both are true only while the data file is empty.
    `factory_limits` takes ChromIQ's own defaults only where the file supplied
    no number, so with figures supplied custom-7 starts from the 12647-7 block
    and custom-8 from the 12647-8 block, and the two are not the same numbers.

    **AND THERE ARE THREE SOURCES NOW, NOT TWO.** Knut's researched industry
    figures became the Custom columns' starting values on 2026-09-21 (#182),
    and ChromIQ's own numbers stayed on the rows his research does not cover.
    A blurb naming two of the three is the same shape of half-truth the
    earlier three corrections were for, so all three are named and the
    sentence says plainly that neither of ours is the standard's.
    """
    from workflow.compliance_sets import SET_BY_ID
    for sid, std in (("custom_iso_12647_7", "ISO 12647-7:2016"),
                     ("custom_iso_12647_8", "ISO 12647-8:2021")):
        blurb = SET_BY_ID[sid].blurb
        # K33 (B8-998): since B8-978 no values file fills a Custom column,
        # so the blurb names the standard only as what it is an alternative
        # to, and no longer promises "the published figures ... where a
        # licence holder has supplied them".
        assert f"an alternative to {std}" in blurb, sid
        assert "licence holder" not in blurb, sid
        assert "researched from industry practice" in blurb, sid
        assert "ChromIQ's own" in blurb, sid
        # …and it says whose those two are NOT
        assert "neither of which is that standard's" in blurb, sid
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


def test_the_two_custom_columns_cover_the_same_rows_and_no_longer_the_same_numbers():
    """THEY WERE IDENTICAL AS ChromIQ SHIPPED, AND THEY ARE NOT ANY MORE.

    This test used to be called "start identical only while the file is
    empty", and with an empty file they did: one shared table put the same
    number on the same eighteen rows in both columns. Knut's researched
    figures (#182, 2026-09-21) are given PER COLUMN, following each standard's
    own structure, so the two columns now differ on some rows with the
    repository's own empty file in place, before any licence holder supplies
    anything.

    What is still true, and is the invariant worth pinning, is that both
    columns cover the same rows: Knut's 2026-09-11 ruling was that every
    metric ChromIQ can measure carries a limit in a Custom column, and that
    does not become "every metric one of the standards happens to limit".
    """
    from workflow.compliance_sets import effective_limits, limit_bearing
    a = limit_bearing(effective_limits("custom_iso_12647_7", None))
    b = limit_bearing(effective_limits("custom_iso_12647_8", None))
    assert set(a) == set(b)
    differing = sorted(rid for rid in a if a[rid] != b[rid])
    assert differing, (
        "the two Custom columns hold identical numbers on every row. Knut's "
        "researched figures are per column and differ between them, so this "
        "means they stopped being applied per column.")
