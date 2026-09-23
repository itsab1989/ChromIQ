"""#182 K31, metrics, names and texts (beta 40).

Knut, #182 5801677743, answering our 5798697107:

* section 3, evenness: *"Both texts approved."* A line "How evenness was
  judged" shown only when an evenness row is in the report, and the new help
  text of both evenness rows (B8-900);
* section 4, the 30 to 70 % tone ramp: *"Implement rule A, update all relevant
  text and help text relevant. And update the demo project package to test the
  requirements for this metric with the new rule."* (B8-901);
* section 5, every metric name: *"Use version 1 everywhere and implement your
  recommendations."* (B8-902, B8-903);
* section 6, within and beyond the gamut: *"Agreed, do as recommended."*
  (B8-904);
* section 7, FROM PROFILE GAMUT and the grey rows: *"Implement option (a) On a
  FROM PROFILE GAMUT chart, use the chart's neutral AIMS as its grey steps."*
  (B8-905).

Every test names the mutation it was proved red against.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from core.i18n import tr                                       # noqa: E402
from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402
from workflow.compliance_sets import (ROW_BY_ID, ROWS,          # noqa: E402
                                      effective_limits)
import ui.dialogs.measurement_report_dialog as mrd             # noqa: E402
import ui.dialogs.preset_verification_dialog as PVD            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FPG = ROOT / "tests" / "fixtures" / "charts" / "fpg_k31"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _open(tmp_path, qapp):
    from tests.test_trend_graphs_for_judged_metrics import _open as o
    return o(tmp_path, qapp, effective_limits("chromiq_default", {}))


def _text(body_html: str) -> str:
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", " ", body_html))


# ---------------------------------------------------------------------------
# section 5: version 1 names (B8-902)
# ---------------------------------------------------------------------------
#: Version 1 of 5798697107 section 5, word for word, for every row it renamed.
VERSION_1 = {
    "substrate_de00_max": "ΔE00, paper white against the reference paper",
    "substrate_overprinted_de00_max":
        "ΔE00, overprinted proofing paper against the production paper",
    "solids_de00_max": "Maximum ΔE00, solid colours",
    "cmy_solids_dhab_max": "Maximum ΔH*ab, cyan, magenta and yellow solids",
    "spot_solids_de00_max": "Maximum ΔE00, spot colours",
    "control_strip_de00_avg": "Average ΔE00, control strip",
    "control_strip_de00_max": "Maximum ΔE00, control strip",
    "control_strip_de00_p95":
        "Maximum ΔE00, control strip, lowest 95 % (95th percentile)",
    "grey_balance_neutral_ramp_avg": "Average ΔCh, grey balance of the grey ramp",
    "grey_balance_neutral_ramp_max": "Maximum ΔCh, grey balance of the grey ramp",
    "outer_gamut_226_de00_avg": "Average ΔE00, outer-gamut patches",
    "surface_gamut_de00_avg": "Average ΔE00, surface-gamut patches",
    "ramps_30_70_dl_max": "Maximum ΔL*, single-colour ramps 30 % to 70 %",
    "repeat_patches_de00_max": "Maximum ΔE00, repeat patches on one sheet",
    "repeat_measurement_de00_max": "Maximum ΔE00, the same chart measured again",
    "uniformity_sd": "Maximum ΔE00, between two of the nine sheet areas",
    "uniformity_de00_max_from_mean":
        "Maximum ΔE00, one sheet area against the whole sheet",
    "repeatability_de00_max": "Maximum ΔE00, print to print and day to day",
    "permanence_de00_max": "Maximum ΔE00, permanence in storage",
    "fading_24h_de00_max": "Maximum ΔE00, fading in the dark, first 24 hours",
    # the five confirmed ones and the ones version 1 keeps
    "all_de00_avg": "Average ΔE00, all patches",
    "all_de00_max": "Maximum ΔE00, all patches",
    "substrate_gloss_class": "Gloss class of the paper",
    "light_fastness": "Light fastness",
}


def test_every_row_carries_its_version_1_name():
    """MUTATION, proven red: put "Solid colours, largest difference" back as
    the label of `solids_de00_max` in `compliance_sets.ROWS`."""
    for rid, name in VERSION_1.items():
        assert ROW_BY_ID[rid].label == name, rid


def test_a_name_says_maximum_never_largest_and_carries_its_unit():
    """"One word for one thing" and "the unit is inside every name".

    MUTATION, proven red: label `ramps_30_70_dl_max` "Maximum lightness
    difference, single-colour ramps 30 % to 70 %" (no unit)."""
    for r in ROWS:
        assert "largest" not in r.label.lower(), r.id
        if r.unit:
            assert r.unit in r.label, (r.id, r.label)


def test_every_graph_tab_carries_a_unit(tmp_path, qapp):
    """"Paper white, diff" and "Cube corners" had none.

    MUTATION, proven red: `addTab(self._trend_corners, tr("Cube corners"))`."""
    dlg = _open(tmp_path, qapp)
    try:
        t = dlg._trend_tabs
        names = [t.tabText(i) for i in range(t.count())]
        for n in names:
            assert re.search(r"\((ΔE00|ΔCh|ΔL\*|L\*|ΔH\*ab)\)", n), n
        assert "Paper white difference (ΔE00)" in names
        assert "Cube corners (ΔE00)" in names
        assert "Tone ramps 30 to 70 % (ΔL*)" in names
    finally:
        dlg.deleteLater()


def test_the_darkest_black_has_one_name(tmp_path, qapp):
    """Tab, legend and Overview say "Darkest black".

    MUTATION, proven red: the legend `tr("Black L*")` in `_trend_configs`."""
    dlg = _open(tmp_path, qapp)
    try:
        black = [c for c in dlg._trend_configs() if c[0] is dlg._trend_black][0]
        assert [m[0] for m in black[2]] == ["Darkest black L*"]
        overview = _text(dlg._comparison_table_html(dlg._runs_for_report()))
        assert "Darkest black L*" in overview
        assert not re.search(r"(?<!Darkest )\bBlack L\*", overview), overview
        assert "Standard deviation ΔE00, all patches" in overview
    finally:
        dlg.deleteLater()


def test_the_evenness_line_word_is_areas():
    """"Pairs" was the one unclear limit-line word.

    MUTATION, proven red: `tr("Pairs")` back in `_TREND_GROUPS`."""
    words = {rid: w() for _k, _t, rows in mrd._TREND_GROUPS
             for rid, w, _c in rows}
    assert words["uniformity_sd"] == "Areas"


# ---------------------------------------------------------------------------
# sections 5 and 6: "within gamut" on a split sheet, the Overview block (B8-904)
# ---------------------------------------------------------------------------
def test_the_within_gamut_names_are_exactly_the_split_rows():
    """The names that say "within gamut" are the rows judged on the
    within-gamut patches, no more, no fewer.

    MUTATION, proven red: drop `uniformity_sd` from `IN_GAMUT_LABELS`."""
    assert set(CS.IN_GAMUT_LABELS) == set(mrd.WITHIN_GAMUT_ROWS)
    for rid, name in CS.IN_GAMUT_LABELS.items():
        assert name.startswith(ROW_BY_ID[rid].label.split(" (")[0]), rid
        assert "within gamut" in name
        assert CS.row_name(rid, True) == name
        assert CS.row_name(rid, False) == ROW_BY_ID[rid].label
    assert CS.row_name("grey_balance_neutral_ramp_avg", True) == \
        ROW_BY_ID["grey_balance_neutral_ramp_avg"].label


def _split(runs):
    for r in runs:
        r["gamut_split"] = {"profile": "P.icc", "margin": "safe", "n_in": 30,
                            "n_out": 6,
                            "de00_in": dict(r.get("de00") or {}),
                            "de00_out": dict(r.get("de00") or {})}
    return runs


def test_a_split_report_names_the_judged_figures_within_gamut(tmp_path, qapp):
    """Report Results, How to read and the graph legend say "within gamut" on
    a document holding a split sheet, and not on one without.

    MUTATION, proven red: `split = False` in `MeasurementReportDialog._row_name`."""
    dlg = _open(tmp_path, qapp)
    try:
        runs = dlg._runs_for_report()
        plain = _text(dlg._report_results_html(runs))
        assert "all patches within gamut" not in plain
        runs = _split(runs)
        present = dlg._rows_the_results_show(runs)
        results = _text(dlg._report_results_html(runs, present))
        guide = _text(dlg._how_to_read_html(present))
        assert "Average ΔE00, all patches within gamut" in results
        assert "Maximum ΔE00, all patches within gamut" in guide
        detail = _text(dlg._run_detail_html(runs[0]))
        assert "Average ΔE00, all patches within gamut" in detail
    finally:
        dlg.deleteLater()


def test_the_overview_block_is_within_and_beyond_together(tmp_path, qapp):
    """MUTATION, proven red: `tr("All patches together")` back in
    `_comparison_table_html`."""
    dlg = _open(tmp_path, qapp)
    try:
        overview = _text(dlg._comparison_table_html(
            _split(dlg._runs_for_report())))
        assert "Within and beyond the gamut together" in overview
        assert "All patches together" not in overview
        assert "Beyond the profile's gamut" in overview
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# section 3: evenness (B8-900)
# ---------------------------------------------------------------------------
APPROVED_LINE = ("from the readings as the instrument took them, by comparing "
                 "the nine areas of this sheet with each other.")
APPROVED_HELP = (
    "Which readings are used. Evenness compares the nine areas of this one "
    "sheet with each other, so it uses the readings exactly as the "
    "instrument took them. How the sheet was colour-managed does not matter "
    "here: a colour that prints differently in one corner than in another is "
    "a fault of the printer or the paper either way.\n\n"
    "Some sheets are printed with an intent that makes the paper the white, "
    "and on those the colour accuracy figures are worked out relative to the "
    "paper. On such a sheet ChromIQ moves every aim colour onto the paper by "
    "the same amount instead. The paper's own tint then does not count as "
    "unevenness, and because every aim moves by the same amount, no area of "
    "the page can come out different from another because of it.")


def test_both_evenness_help_icons_carry_the_approved_text():
    """MUTATION, proven red: restore the old "The readings are taken as
    measured, whatever rendering intent ..." paragraph in `_D_EVENNESS`."""
    for rid in ("uniformity_sd", "uniformity_de00_max_from_mean"):
        assert APPROVED_HELP in ROW_BY_ID[rid].detect, rid
        assert "The readings are taken as measured" not in ROW_BY_ID[rid].detect


def _printing(dlg, monkeypatch, row_ids):
    monkeypatch.setattr(dlg, "_verdict_rows", lambda r: (
        [{"row_id": rid, "word": "PASS"} for rid in row_ids], False))
    r = {"is_verification": True, "yardstick": "media-relative",
         "printing": {"colour": "through-profile", "intent": "relative"}}
    return _text(dlg._printing_block_html(r))


def test_the_evenness_line_is_there_only_with_an_evenness_row(
        tmp_path, qapp, monkeypatch):
    """"A separate line, shown only when an evenness row is in the report, so
    it is always true."

    MUTATION, proven red: `if True:` for
    `if MeasurementReportDialog._evenness_row_is_in_report(self, r):`
    in `_printing_block_html` (the line appears without an evenness row)."""
    dlg = _open(tmp_path, qapp)
    try:
        with_it = _printing(dlg, monkeypatch, ["uniformity_sd", "all_de00_avg"])
        assert "How evenness was judged" in with_it
        assert APPROVED_LINE in with_it
        # the colours line beside it is unchanged
        assert "relative to this sheet's own paper white" in with_it
        without = _printing(dlg, monkeypatch, ["all_de00_avg"])
        assert "How evenness was judged" not in without
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# section 4: rule A on the 30 to 70 % ramp (B8-901)
# ---------------------------------------------------------------------------
def _cyan_ramp_block(tone_values):
    """A chart whose only 30 to 70 % ramp is the cyan axis at *tone_values*."""
    rgb = [(100.0 - tv, 100.0, 100.0) for tv in tone_values]
    rgb += [(0.0, 50.0, 20.0), (80.0, 10.0, 40.0)]      # not on any ramp
    ids = [str(i + 1) for i in range(len(rgb))]
    lab = [(50.0, 0.0, 0.0)] * len(rgb)
    ref = {sid: (50.0, 0.0, 0.0) for sid in ids}
    return MR.ramps_block(np.asarray(rgb), lab, ref, ids)


def test_bunched_mid_tones_are_refused_and_named():
    """40, 59.4 and 60: three steps and a span of 20, which passed until K31.

    MUTATION, proven red: remove the `pick_even_grey_steps` call from
    `ramps_block` (the block is eligible again)."""
    b = _cyan_ramp_block((40.0, 59.4, 60.0))
    assert not b["eligible"]
    assert b["reason"] == MR.REASON_RAMP_STEPS_BUNCHED
    assert b["missing_level"] == 50.0
    assert b["bunched_axis"] == "R"


def test_evenly_spaced_mid_tones_pass_and_the_tolerance_is_four_inclusive():
    """MUTATION, proven red: `RAMP_SPACING_TOL = 3.0`."""
    assert MR.RAMP_SPACING_TOL == MR.GREY_SPACING_TOL == 4.0
    assert _cyan_ramp_block((40.0, 50.0, 60.0))["eligible"]
    assert _cyan_ramp_block((40.0, 54.0, 60.0))["eligible"]
    assert not _cyan_ramp_block((40.0, 54.2, 60.0))["eligible"]
    # a longer ramp picks the steps that fit
    assert _cyan_ramp_block((30.0, 31.0, 40.0, 50.0, 60.0, 70.0))["eligible"]


def test_too_few_steps_is_still_no_ramp():
    """The count and the span are asked first, and keep their own reason.

    MUTATION, proven red: set `bunched` for every axis in `ramps_block`
    (a two-step ramp reads ramp_steps_bunched)."""
    assert _cyan_ramp_block((40.0, 60.0))["reason"] == MR.REASON_NO_RAMP
    assert _cyan_ramp_block((40.5, 50.0, 59.5))["reason"] == MR.REASON_NO_RAMP


def test_the_na_note_and_the_presets_window_name_the_bunching(tmp_path, qapp):
    """The note names the tone value no step is near, as the grey note does;
    the presets window files it as a patch shortfall.

    MUTATION, proven red: remove the "ramp_steps_bunched" entry from
    `_reason_sentence` (the note falls back to the generic sentence)."""
    dlg = _open(tmp_path, qapp)
    try:
        r = {"ramps_30_70": _cyan_ramp_block((40.0, 59.4, 60.0))}
        s = dlg._reason_sentence("ramp_steps_bunched", r)
        assert "tone value 50 %" in s and "within 4" in s, s
    finally:
        dlg.deleteLater()
    assert "30 % and 70 %" in PVD.reason_line(MR.REASON_RAMP_STEPS_BUNCHED)
    assert PE.is_patch_shortfall(MR.REASON_RAMP_STEPS_BUNCHED)


def test_the_help_icon_states_rule_a():
    """MUTATION, proven red: drop the spacing paragraph from `_D_RAMPS`."""
    row = ROW_BY_ID["ramps_30_70_dl_max"]
    assert "roughly evenly spaced" in row.detect
    assert "4 % of full scale" in row.detect
    assert "Single Channel Steps (-s)" in row.remedy
    assert "Grey Axis Steps (-g)" in row.remedy


def test_no_built_in_preset_loses_the_tone_row():
    """Measured before it was built: 185 of 185 answer under rule A.

    MUTATION, proven red: ask `pick_even_grey_steps` in `ramps_block` for
    ``n=8`` evenly spaced steps instead of `RAMP_MIN_STEPS` (every built-in
    ramp holds fewer than eight steps in the band and is refused). A tighter
    tolerance alone is NOT red: measured, every built-in ramp is spaced
    evenly to within 1 point."""
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    seen, lost = 0, []
    for _instr, entries in BUILTIN_PRESET_GROUPS:
        for _c, label, key in entries:
            a = TabChart._builtin_ti1_asset(key)
            c = resource_path(a) if a else None
            if not (c and c.is_file()):
                continue
            seen += 1
            v = PE.chart_row_values(c)["ramps_30_70_dl_max"]
            if v.get("value") is None:
                lost.append((label, v.get("reason")))
    assert seen >= 180, seen
    assert not lost, lost


# ---------------------------------------------------------------------------
# section 7: a FROM PROFILE GAMUT chart's neutral aims are its grey steps (B8-905)
# ---------------------------------------------------------------------------
def _fpg_copy(tmp_path, n):
    dst = tmp_path / f"c{n}"
    shutil.copytree(FPG / f"c{n}", dst)
    return dst / "FPG-verify.ti2"


def test_the_device_rule_refuses_the_charts_of_challenge_a():
    """What challenge A found (F2): by device R = G = B the 400-patch chart's
    six lightest neutrals are not grey, and the ramp reads bunched. Kept so a
    reader sees what option (a) changes."""
    from workflow.ti3_analysis import parse_ti3
    d = parse_ti3(FPG / "c400" / "FPG-verify.ti2")
    rgb = MR._rgb_to_0_100(np.asarray(d.rgb, dtype=float))
    lab = [(50.0, 0.0, 0.0)] * len(d.sample_ids)
    b = MR.grey_balance_block(rgb, lab, {s: (50.0, 0.0, 0.0)
                                         for s in d.sample_ids}, d.sample_ids)
    assert b["reason"] == MR.REASON_GREY_STEPS_BUNCHED


@pytest.mark.parametrize("n", [100, 400])
def test_the_presets_window_answers_the_grey_rows_of_a_gamut_chart(tmp_path, n):
    """The current-chart line of "Which presets can be used for verification?"
    on the 100- and 400-patch charts of challenge A.

    MUTATION, proven red: `aims = None` in `preset_eligibility._perfect_print`."""
    chart = _fpg_copy(tmp_path, n)
    PE.clear_cache()
    v = PE.chart_row_values(chart)
    for rid in ("grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max"):
        assert v[rid].get("value") is not None, (n, rid, v[rid])
    gb = PE._perfect_print(chart)["grey_balance"]
    assert gb["source"] == "neutral_aims"
    assert len(gb["picked_levels"]) >= MR.GREY_MIN_LEVELS


def test_the_report_of_a_gamut_verification_answers_the_grey_rows(tmp_path):
    """Tester A's case, measured: a perfect print of the 400-patch chart (its
    own reference as the reading), filed beside its chart.

    MUTATION, proven red: `neutral_aims=None` in `build_report`'s call of
    `grey_balance_block` (both rows read grey_steps_bunched again)."""
    from workflow.ti3_analysis import mark_verification_ti3
    chart = _fpg_copy(tmp_path, 400)
    ti3 = chart.with_suffix(".ti3")
    shutil.copy2(chart.with_name("FPG-verify-reference.ti3"), ti3)
    marked = mark_verification_ti3(ti3)
    if marked != ti3:
        marked.replace(ti3)
    rep = MR.build_report(ti3)
    assert rep["reference_source"] == "colorimetric"
    gb = rep["grey_balance"]
    assert gb["source"] == "neutral_aims" and gb["eligible"], gb.get("reason")
    rows = MR.row_values(rep)
    for rid in ("grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max"):
        assert rows[rid].get("value") is not None, rows[rid]
    assert gb["max"] < 0.05     # the reading IS the aim


def _aim_block(aims, corners=()):
    ids = list(aims)
    rgb = np.asarray([(50.0, 50.0, 52.0)] * len(ids))    # never grey by device
    lab = [aims[s] for s in ids]
    return MR.grey_balance_block(rgb, lab, aims, ids, neutral_aims=aims,
                                 corner_ids=set(corners))


def _even_neutrals(lo, hi, n=8, start=1):
    return {str(start + k): (lo + k * (hi - lo) / (n - 1), 0.0, 0.0)
            for k in range(n)}


def test_the_corners_are_never_grey_steps():
    """The corners' reference is the ideal device corner, L* 100 and 0.

    MUTATION, proven red: drop `sid not in corners` from
    `_neutral_aim_grey_block` (the ideal corners become the ends and the
    ramp's own ends then fall short of them)."""
    aims = _even_neutrals(20.0, 92.0)
    aims.update({"90": (100.0, 0.0, 0.0), "91": (0.0, 0.0, 0.0),
                 "92": (60.0, 40.0, 10.0)})
    b = _aim_block(aims, corners=("90", "91"))
    assert b["eligible"], b["reason"]
    assert b["chart_darkest"] == 20.0 and b["chart_lightest"] == 92.0


def test_the_ends_are_the_charts_own_reach():
    """A matte paper whose darkest printable neutral is L* 18: the device rule's
    fixed "at most 10" would refuse every such chart.

    MUTATION, proven red: `min(levels) > GREY_DARKEST_MAX` for the black end
    in `_neutral_aim_grey_block`."""
    aims = _even_neutrals(18.0, 93.0)
    aims["50"] = (15.0, 30.0, 40.0)                     # a dark blue aim
    assert _aim_block(aims)["eligible"]
    aims["51"] = (5.0, 10.0, -20.0)                     # a far darker one
    assert _aim_block(aims)["reason"] == MR.REASON_NEUTRAL_AIMS_NO_BLACK


def test_a_neutral_aim_is_what_create_chart_calls_neutral():
    """`gamut_target.select_gamut_targets` picks its neutrals with
    ``hypot(a, b) < 1.0``; the report asks the same.

    MUTATION, proven red: `NEUTRAL_AIM_CHROMA_MAX = 2.0`."""
    assert MR.NEUTRAL_AIM_CHROMA_MAX == 1.0
    aims = _even_neutrals(5.0, 95.0)
    aims["4"] = (aims["4"][0], 0.7, 0.72)               # hypot 1.004
    b = _aim_block(aims)
    assert b["levels"] == 7 and b["reason"] == MR.REASON_TOO_FEW_NEUTRAL_AIMS


def test_bunched_aims_are_named_with_their_lightness(tmp_path, qapp):
    """MUTATION, proven red: remove the "neutral_aims_bunched" entry from
    `_reason_sentence`."""
    aims = {str(i + 1): (L, 0.0, 0.0) for i, L in
            enumerate((5.0, 90.0, 90.6, 91.2, 91.8, 92.4, 93.0, 93.6))}
    b = _aim_block(aims)
    assert b["reason"] == MR.REASON_NEUTRAL_AIMS_BUNCHED
    dlg = _open(tmp_path, qapp)
    try:
        s = dlg._reason_sentence("neutral_aims_bunched", {"grey_balance": b})
        assert "lightness L*" in s and "neutral aims" in s, s
    finally:
        dlg.deleteLater()


def test_the_lever_on_a_gamut_chart_is_a_larger_chart_not_grey_steps():
    """The presets window's advice for a gamut chart's grey rows.

    MUTATION, proven red: return `row.remedy` unconditionally from
    `compliance_sets.remedy_for`."""
    rid = "grey_balance_neutral_ramp_avg"
    for code in CS.GREY_AIM_REASONS:
        lever = PE.row_remedy(rid, code)
        assert "more patches" in lever and "add grey steps" not in lever
    assert "add grey steps" in PE.row_remedy(rid, MR.REASON_TOO_FEW_STEPS)
    assert "FROM PROFILE GAMUT" not in PE.row_remedy(rid,
                                                     MR.REASON_TOO_FEW_STEPS)


def test_the_two_spellings_of_the_aim_reasons_agree():
    """`compliance_sets` cannot import the report, so it spells them again.

    MUTATION, proven red: rename one entry of `GREY_AIM_REASONS`."""
    assert CS.GREY_AIM_REASONS == {
        MR.REASON_TOO_FEW_NEUTRAL_AIMS, MR.REASON_NEUTRAL_AIMS_BUNCHED,
        MR.REASON_NEUTRAL_AIMS_NO_WHITE, MR.REASON_NEUTRAL_AIMS_NO_BLACK}
    for code in CS.GREY_AIM_REASONS | {MR.REASON_RAMP_STEPS_BUNCHED}:
        assert code in PE.classified_reasons(), code
        assert PVD.reason_line(code) != tr(
            "ChromIQ cannot check this metric on this chart."), code


# ---------------------------------------------------------------------------
# German: report text addresses nobody (§19.1)
# ---------------------------------------------------------------------------
def test_the_german_report_texts_address_nobody():
    """Report text is written for a customer: no "du" in it (§19.1). The row
    names, the evenness line and the N-A sentences of K31 are report text.

    MUTATION, proven red: German "Wie du die Gleichmäßigkeit beurteilt hast"
    for "How evenness was judged"."""
    de = json.loads((ROOT / "data" / "i18n" / "de.json").read_text("utf-8"))
    keys = [r.label for r in ROWS] + list(CS.IN_GAMUT_LABELS.values()) + [
        "How evenness was judged", APPROVED_LINE,
        "Within and beyond the gamut together", "Darkest black L*",
        "Standard deviation ΔE00, all patches",
        "the neutral aims of the measured chart are bunched together: none "
        "lies within {tol} of the lightness L* {level}, and {n} roughly evenly "
        "spaced steps from its black to its white are needed"]
    for k in keys:
        assert k in de, k
        assert not re.search(r"\b(du|dein\w*|dich|dir)\b", de[k], re.I), (k, de[k])
