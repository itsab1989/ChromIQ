"""Every row of the limits window explains itself, and says how it is detected.

Knut, 2026-09-14:

    In report limits window (Edit limits button) the first column is a name for
    each metric. Right aligned to the end of each metric name, add an info help
    icon, where each help icon describes the metric for that line and details
    the conditions used to detect if a chart contains the patches needed to
    assess and judge this metric. If any metric is missing a detection method
    for checking if a chart used for verification contains needed patches, then
    this detection method must be determined and specified.

So this file holds three things together:

1. **every row has both halves**, enforced in `Row.__post_init__` so a row
   cannot be added without them, and asserted here so the enforcement itself
   cannot be quietly removed;
2. **the window really shows them**, one icon per row, at the right edge of the
   name column;
3. **the detection sentence agrees with the code that does the detecting.**
   That is the half a document cannot keep true on its own: the numbers in the
   sentences (eight grey steps, twelve device units, three ramp steps, twenty
   patches) are read back out of `measurement_report`'s own constants, so
   changing a threshold without changing what the window promises turns this
   file red.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402

from workflow import compliance_sets as cs                      # noqa: E402


# ------------------------------------------------------------- the data
def test_every_row_says_what_it_measures():
    assert len(cs.ROWS) == 30, "the table changed size; check the help text too"
    for row in cs.ROWS:
        assert row.blurb, row.id
        assert row.blurb[0].isupper(), row.id
        assert row.blurb.rstrip().endswith("."), row.id


def test_every_row_that_can_be_judged_says_how_it_is_detected():
    """An `unmeasurable` row has nothing to detect and its `note` says why; any
    other row must name its condition.

    MUTATION: drop `detect=` from one row and `Row.__post_init__` refuses to
    build the table at all, which is the point of putting it there.
    """
    for row in cs.ROWS:
        if row.status == "unmeasurable":
            assert row.note and not row.detect, row.id
        else:
            assert row.detect, row.id


def test_the_assertion_in_the_row_itself_is_still_there():
    """The guard that makes the two above unnecessary, pinned so that removing
    it is a deliberate act."""
    import dataclasses
    with pytest.raises(AssertionError):
        dataclasses.replace(cs.ROWS[0], blurb="")


# ------------------------------------ the sentences agree with the code
def test_the_grey_condition_quotes_the_real_thresholds():
    """*"at least eight distinct steps ... reaching white at one end and black
    at the other"*, and one unit of spread.

    MUTATION: change `GREY_MIN_LEVELS` and this goes red, because the window
    would be promising a condition the report does not apply.
    """
    from workflow import measurement_report as mr
    text = next(r.detect for r in cs.ROWS
                if r.id == "grey_balance_neutral_ramp_avg")
    assert mr.GREY_MIN_LEVELS == 8 and "eight" in text
    assert mr.GREY_SPREAD_TOL == 1.0 and "one unit" in text
    assert mr.GREY_LIGHTEST_MIN == 90.0 and mr.GREY_DARKEST_MAX == 10.0
    assert "white" in text and "black" in text


def test_the_corner_condition_quotes_the_real_tolerance():
    """*"within 12 device units"*.

    MUTATION: change `CORNER_PRESENT_TOL` and this goes red.
    """
    from workflow import measurement_report as mr
    assert mr.CORNER_PRESENT_TOL == 12.0
    for rid in ("solids_de00_max", "cmy_solids_dhab_max"):
        text = next(r.detect for r in cs.ROWS if r.id == rid)
        assert "12 device units" in text, rid


def test_the_ramp_condition_quotes_the_real_thresholds():
    """*"at least three distinct steps between 30 % and 70 % ... spanning at
    least twenty points"*."""
    from workflow import measurement_report as mr
    text = next(r.detect for r in cs.ROWS if r.id == "ramps_30_70_dl_max")
    assert mr.RAMP_MIN_STEPS == 3 and "three distinct steps" in text
    assert mr.RAMP_MIN_SPAN == 20 and "twenty points" in text
    assert mr.RAMP_TV_LOW == 30 and "30 %" in text
    assert mr.RAMP_TV_HIGH == 70 and "70 %" in text


def test_the_worst_five_condition_quotes_the_real_population_size():
    """The twenty-patch rule, and that the count is the GRADED population.

    The sentence says "at least twenty patches counted" and names the
    within-gamut subset, because that is what the code tests: `high = a[k:]`
    with `k = ceil(0.95 n)` is empty for every n below 20.
    """
    import math
    text = next(r.detect for r in cs.ROWS if r.id == "worst5_de00_avg")
    assert "twenty patches" in text and "inside the gamut" in text
    assert all(math.ceil(n * 0.95) >= n for n in range(1, 20))
    assert math.ceil(20 * 0.95) < 20


@pytest.mark.parametrize("rid", ["substrate_de00_max", "solids_de00_max",
                                 "cmy_solids_dhab_max"])
def test_the_reference_rows_say_where_the_reference_comes_from(rid):
    """MEASURED while mapping this table: those three rows produced
    `needs_reference_file` in 80 of 80 saved reports in the demo package,
    because the sidecar they need is written only by the profile-gamut chart
    module. A help icon that did not say so would send a reader looking for
    patches that are already on the chart."""
    text = next(r.detect for r in cs.ROWS if r.id == rid)
    assert "colorimetric reference" in text
    assert "profile's gamut" in text


#: The five rows that had no detection method until B8-397. Knut approved all
#: three S2w proposals on 2026-09-18 and they are built, so NOTHING in this
#: table is left in the `unknown` status any more.
_THE_FIVE = ("control_strip_de00_avg", "control_strip_de00_max",
             "control_strip_de00_p95", "outer_gamut_226_de00_avg",
             "surface_gamut_de00_avg")


def test_no_row_is_left_without_a_detection_method():
    """*"If any metric is missing a detection method ... then this detection
    method must be determined and specified."*

    Five were. They are the three control-strip rows and the two gamut
    populations, and their icons said plainly that ChromIQ did not judge them.
    Knut approved the three S2w proposals on 2026-09-18 (B8-397), so each of
    them now names a condition ChromIQ really applies.

    MUTATION: put any of the five back to `status="unknown"` and this goes red.
    """
    assert [r.id for r in cs.ROWS if r.status == "unknown"] == []
    for rid in _THE_FIVE:
        row = cs.ROW_BY_ID[rid]
        assert row.status == "build", rid
        assert row.detect and row.remedy, rid
        # …AND THE OLD SENTENCES ARE GONE. Each of the five used to say the row
        # was never judged; leaving one of those beside a row that now carries
        # a verdict would be the window contradicting the table next to it.
        for dead in ("does not judge this row", "never judged",
                     "stays empty in every limit set",
                     "does not hold that list"):
            assert dead not in row.detect, f"{rid} still says {dead!r}"


def test_the_control_strip_condition_quotes_the_real_thresholds():
    """*"at least 8 ... The 95th percentile needs 20"*, read back out of
    `measurement_report`'s own constants.

    MUTATION: change `CONTROL_STRIP_MIN` or `CONTROL_STRIP_P95_MIN` and this
    goes red, because the icon would be promising a condition the report does
    not apply.
    """
    import math
    from workflow import measurement_report as mr
    text = cs.ROW_BY_ID["control_strip_de00_avg"].detect
    assert mr.CONTROL_STRIP_MIN == 8
    assert f"least {mr.CONTROL_STRIP_MIN} are needed" in text
    assert mr.CONTROL_STRIP_P95_MIN == 20
    assert f"95th percentile needs {mr.CONTROL_STRIP_P95_MIN}" in text
    # …and the REASON the second number is 20, which the sentence states: the
    # nearest rank ceil(0.95 k) is k itself for every k below twenty, so the
    # row would repeat the largest.
    assert all(math.ceil(k * 0.95) >= k for k in range(1, mr.CONTROL_STRIP_P95_MIN))
    assert math.ceil(mr.CONTROL_STRIP_P95_MIN * 0.95) < mr.CONTROL_STRIP_P95_MIN
    assert mr.CONTROL_STRIP_SIDECAR == ".control-strip.json"
    assert mr.CONTROL_STRIP_SIDECAR in text
    assert mr.CONTROL_STRIP_KEYWORD in text


def test_the_gamut_population_conditions_quote_the_real_thresholds():
    """The cube-surface tolerance, the ten, the quarter and the twenty.

    MUTATION: change `SURFACE_GAMUT_TOL`, `SURFACE_GAMUT_MIN`,
    `OUTER_GAMUT_FRACTION` or `OUTER_GAMUT_MIN` and this goes red.
    """
    from workflow import measurement_report as mr
    surf = cs.ROW_BY_ID["surface_gamut_de00_avg"].detect
    assert mr.SURFACE_GAMUT_TOL == 2.0
    assert f"within {mr.SURFACE_GAMUT_TOL} of 0 or of 100" in surf
    assert mr.SURFACE_GAMUT_MIN == 10
    assert f"at least {mr.SURFACE_GAMUT_MIN} of them" in surf
    outer = cs.ROW_BY_ID["outer_gamut_226_de00_avg"].detect
    assert mr.OUTER_GAMUT_FRACTION == 0.25 and "top quarter" in outer
    assert mr.OUTER_GAMUT_MIN == 20
    assert f"at least {mr.OUTER_GAMUT_MIN} patches" in outer
    # The "roughly 80" the sentence quotes is the quartile rule applied
    # backwards, not a number of its own.
    assert str(int(mr.OUTER_GAMUT_MIN / mr.OUTER_GAMUT_FRACTION)) in outer


def test_the_heading_over_the_two_gamut_rows_no_longer_names_a_standard():
    """Knut, 2026-09-18: *"I have already proposed to change the heading from
    'Selected patches of the standard's chart' to 'Selected patches of the
    chart'."*

    It is the half that made those two rows a specification question rather
    than a fault: ChromIQ's own definition of a population under a heading
    that calls it the standard's is the attributing-coverage-to-a-standard
    mistake `compliance_sets.py` records being made twice already.

    MUTATION: put "standard's" back in the heading and this goes red.
    """
    heading = cs.GROUP_LABELS["selected"]
    assert heading == "Selected patches of the chart"
    assert "standard" not in heading.lower()
    assert {r.id for r in cs.rows_in_group("selected")} >= {
        "outer_gamut_226_de00_avg", "surface_gamut_de00_avg"}


def test_no_row_promises_a_reason_code_that_does_not_exist():
    """The detection sentences are prose, and the report answers with codes.
    Every code the report can produce must have a sentence, or a row can be
    withheld for a reason nobody can read."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    import inspect
    src = inspect.getsource(MeasurementReportDialog._reason_sentence)
    from workflow import measurement_report as mr
    codes = [v for k, v in vars(mr).items()
             if k.startswith("REASON_") and isinstance(v, str)]
    assert codes, "the report has no reason codes at all any more"
    for code in codes:
        assert f'"{code}"' in src, f"no sentence for the reason code {code!r}"


# ------------------------------------------------------- the window shows them
@pytest.fixture
def dlg(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    d = ThresholdsDialog(AppSettings(), None)
    d.show()
    qapp.processEvents()
    yield d
    d.close()


def test_the_window_carries_one_icon_per_row(dlg, qapp):
    """MUTATION: drop the TooltipButton from `_build_rows` and this goes red."""
    from ui.tooltip_button import TooltipButton
    icons = dlg.findChildren(TooltipButton)
    assert len(icons) >= len(cs.ROWS), (
        f"{len(icons)} info icons for {len(cs.ROWS)} rows")
    titles = {b.windowTitle() or "" for b in icons}
    del titles                       # the title lives in the button's own state


def test_each_icon_carries_both_halves(dlg, qapp):
    """The description and the condition, in that order, for every row."""
    from core.i18n import tr
    for row in cs.ROWS:
        help_text = dlg._row_help(row)
        assert tr(row.blurb) in help_text, row.id
        if row.detect:
            assert tr(row.detect) in help_text, row.id
            assert help_text.index(tr(row.blurb)) < help_text.index(
                tr(row.detect)), row.id
        else:
            assert tr(row.note) in help_text, row.id


def test_the_icon_sits_at_the_right_edge_of_the_name_column(dlg, qapp):
    """*"Right aligned to the end of each metric name"*: the icons line up in a
    column of their own rather than following the ragged edge of the text.

    **WHAT MAKES THIS RED, measured rather than assumed.** An adversary round
    removed `_h.addStretch(1)` and this test stayed green: a `QLabel`'s
    Preferred size policy already absorbs the slack, so the icons line up
    without the stretch. The claim that the stretch is what holds them there
    was written and never executed. What DOES turn this red is putting the
    icon in a grid column of its own, or giving the label an Expanding policy,
    or dropping the icon entirely (which the test above catches first). The
    stretch stays because it says the intent out loud.
    """
    from ui.tooltip_button import TooltipButton
    dlg.resize(1200, 900)
    qapp.processEvents()
    xs, rows = [], 0
    for i in range(dlg._grid.count()):
        item = dlg._grid.itemAt(i)
        w = item.widget() if item else None
        if w is None or isinstance(w, TooltipButton):
            continue
        kids = w.findChildren(TooltipButton)
        if len(kids) == 1 and dlg._grid.getItemPosition(i)[1] == 0:
            rows += 1
            xs.append(kids[0].pos().x())
    assert rows == len(cs.ROWS), (
        f"{rows} rows carry an icon in the name column, of {len(cs.ROWS)}")
    assert len(set(xs)) == 1, (
        f"the icons sit at {sorted(set(xs))[:6]}; they must line up")
    assert xs[0] > 0, "the icons sit at the left edge of the name column"


# ------------------------------- the sentences may not overstate the code
#: Every condition the code's eligibility really depends on, and the words the
#: icon must use to say it. **This is the half that was missing**: the first
#: version of this file pinned the NUMBERS in the sentences and nothing about
#: the CLAIMS, and an adversary round proved it by rewriting one detection
#: sentence to *"ChromIQ judges this row on absolutely every chart, always,
#: with no conditions whatsoever"* and watching all fifteen tests pass. Four
#: real overstatements were found in the same round and are pinned below.
_MUST_SAY = {
    # F1: `row_values` takes `max(solid)` over the corners it FOUND, so any one
    # of the four is enough and the row is not about all four.
    "solids_de00_max": (["one or more", "worst of the corners"],
                        ["each of the four"]),
    "cmy_solids_dhab_max": (["one or more", "worst of the corners"],
                            ["each of the"]),
    # F2 and F3: `grey_balance_block` and `ramps_block` both withhold the row
    # when the patches carry no reference values, AFTER every geometric
    # condition is satisfied.
    "grey_balance_neutral_ramp_avg": (["reference values"], []),
    "grey_balance_neutral_ramp_max": (["reference values"], []),
    "ramps_30_70_dl_max": (["reference values"], []),
    # F4: `is_graded_sheet` is False for a run's own profiling chart, which is
    # 23 of the 80 saved reports in the demo package.
    "all_de00_avg": (["VERIFICATION", "profiling"], ["any chart it built"]),
    "worst5_de00_avg": (["verification"], []),
    # F8: `block["levels"]` counts the bare-paper patch; only the STATISTIC
    # excludes it, and paper alone can satisfy the white end.
    "grey_balance_neutral_ramp_avg2": None,
}


def test_no_detection_sentence_promises_more_than_the_code_does():
    """Each of these was a real overstatement, found by an adversary round
    reading the sentences against the functions that do the detecting.

    MUTATION: put any one of the old sentences back and this goes red.
    """
    for rid, spec in _MUST_SAY.items():
        if spec is None:
            continue
        must, must_not = spec
        text = next((r.detect for r in cs.ROWS if r.id == rid), None)
        assert text, rid
        for phrase in must:
            assert phrase in text, f"{rid}: the icon never says {phrase!r}"
        for phrase in must_not:
            assert phrase not in text, (
                f"{rid}: the icon still claims {phrase!r}, which the code does "
                f"not do")


def test_the_grey_sentence_tells_the_truth_about_bare_paper():
    """`grey_balance_block` counts the bare-paper patch toward the eight steps
    and lets it satisfy the white end on its own; only the STATISTIC excludes
    it. The first sentence said flatly "bare paper is left out of the figure",
    which a reader would take as "it does not count".
    """
    text = next(r.detect for r in cs.ROWS
                if r.id == "grey_balance_neutral_ramp_avg")
    assert "counts as one of those steps" in text
    assert "left out of the figure itself" in text


def test_the_solids_sentence_names_the_composite_black():
    """`CUBE_CORNERS["K"]` is (0, 0, 0) on the device cube, which on an RGB
    printer is all three inks at full, not a black-ink solid."""
    from workflow.measurement_report import CUBE_CORNERS
    assert dict(CUBE_CORNERS)["K"] == (0.0, 0.0, 0.0)
    text = next(r.detect for r in cs.ROWS if r.id == "solids_de00_max")
    assert "composite black" in text


def test_the_worst_five_sentence_has_a_singular_form():
    """A twenty-patch sheet with nineteen colours outside the gamut reaches
    n = 1, and "1 of them fall" is not English. CLAUDE.md: count-bearing
    messages get explicit singular and plural variants, never "(s)".

    MUTATION: drop either singular branch and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import _small_sample_sentence
    one_in = _small_sample_sentence({"patches": 20,
                                     "gamut_split": {"de00_in": {"n": 1}}})
    assert "one of them falls" in one_in, one_in
    assert " 1 of them fall " not in one_in
    many = _small_sample_sentence({"patches": 20,
                                   "gamut_split": {"de00_in": {"n": 18}}})
    assert "18 of them fall inside" in many, many
    alone = _small_sample_sentence({"patches": 1, "de00": {"n": 1}})
    assert "one patch" in alone and "1 patches" not in alone, alone


# --------------------------------------------- and it tells you what to do
def test_every_judgeable_row_names_a_lever():
    """Basti, 2026-09-14, asked whether these icons were as useful as the rest
    of the app's help. They were not: every other help text in ChromIQ ends
    with something to change, and these stopped at the diagnosis.

    Only rows that CAN be judged get one. On a row that needs a gloss meter
    there is nothing on the chart to change, and advice there would be
    invention.

    MUTATION: drop `remedy=` from any judgeable row and this goes red.
    """
    judgeable = [r for r in cs.ROWS
                 if r.status not in ("unmeasurable", "unknown")]
    # ELEVEN UNTIL 2026-09-18, sixteen since: B8-397 built the detection for
    # the three control-strip rows and the two gamut populations, so five rows
    # that had nothing to advise now do.
    assert len(judgeable) == 16, len(judgeable)
    for row in judgeable:
        assert row.remedy, f"{row.id} tells the reader nothing to do"
        assert len(row.remedy.split()) >= 25, (
            f"{row.id}'s advice is a stub: {row.remedy!r}")
    for row in cs.ROWS:
        if row.status in ("unmeasurable", "unknown"):
            assert not row.remedy, (
                f"{row.id} cannot be judged and still offers advice")


def test_the_lever_names_a_control_a_reader_can_find():
    """Advice that does not name a screen is not advice.

    MUTATION: replace any remedy with a sentence that names no part of the
    app and this goes red.
    """
    places = ("Create Chart", "FROM PROFILE GAMUT", "preset", "chart")
    for row in cs.ROWS:
        if not row.remedy:
            continue
        assert any(p.lower() in row.remedy.lower() for p in places), (
            f"{row.id}'s advice names nowhere to go: {row.remedy!r}")


def test_the_help_shows_the_lever_under_its_own_heading(qapp, tmp_path):
    from core.i18n import tr
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    d = ThresholdsDialog(AppSettings(), None)
    try:
        row = next(r for r in cs.ROWS if r.id == "grey_balance_neutral_ramp_avg")
        body = d._row_help(row)
        assert tr("What you can do about it") in body
        assert tr(row.remedy) in body
        assert body.index(tr(row.detect)) < body.index(tr(row.remedy)), (
            "the advice comes before the condition it is advice about")
        # …and a row with nothing to change says nothing rather than padding.
        none = d._row_help(next(r for r in cs.ROWS
                                if r.id == "permanence_de00_max"))
        assert tr("What you can do about it") not in none
    finally:
        d.close()


def test_no_help_text_talks_about_the_project_instead_of_the_product():
    """Three rows used to end "and that is a change still to be agreed", which
    is true between Knut and me and means nothing to a reader.

    MUTATION: put the phrase back and this goes red.
    """
    banned = ("still to be agreed", "to be agreed", "awaiting confirmation",
              "we have not", "Knut")
    for row in cs.ROWS:
        for text in (row.blurb, row.detect, row.remedy, row.note):
            for phrase in banned:
                assert phrase.lower() not in (text or "").lower(), (
                    f"{row.id} talks about the project: {phrase!r}")
