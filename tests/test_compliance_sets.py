"""The limit-set model of the Measurement Report (#182): rows, sets, factory
values, overrides, the five verdict words and the column summary.

No Qt. Everything here is what `workflow/compliance_sets.py` promises to the
report code, the Measure tab, the settings migration and the two windows.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import workflow.compliance_sets as cs
from workflow.compliance_sets import (COND, FAIL, INFO, N_A, PASS, Limit,
                                      effective_limits, factory_limits,
                                      is_edited, legacy_pair, limit_bearing,
                                      limit_text, limits_from_json,
                                      limits_to_json, row_verdict,
                                      selectable_set_ids, set_summary)

ROOT = Path(__file__).resolve().parent.parent


# ---- rows and sets ---------------------------------------------------------

def test_every_row_has_a_group_a_status_and_a_unique_id():
    ids = [r.id for r in cs.ROWS]
    assert len(ids) == len(set(ids))
    for r in cs.ROWS:
        assert r.status in cs.ROW_STATUSES
        assert r.group in cs.GROUP_LABELS
        assert re.fullmatch(r"[a-z0-9_]+", r.id), r.id
        if r.status == "unmeasurable":
            assert r.note, f"{r.id}: an unmeasurable row must say why"


def test_the_five_chromiq_statistics_keep_their_old_report_keys():
    """The trend series and every saved report read avg_all / avg_low95 /
    avg_high5 / max_all / max_low95; the rows map onto exactly those."""
    keys = {r.metric_key for r in cs.ROWS if r.metric_key}
    assert keys == {"avg_all", "avg_low95", "avg_high5", "max_all", "max_low95"}
    assert set(cs.OLD_AVG_ROWS) | set(cs.OLD_MAX_ROWS) == {
        r.id for r in cs.ROWS if r.metric_key}


def test_seven_sets_in_knuts_order_and_the_iso_sets_are_read_only():
    assert cs.SET_IDS == ("chromiq_default", "chromiq_tight", "chromiq_quick",
                          "iso_12647_7", "iso_12647_8",
                          "custom_iso_12647_7", "custom_iso_12647_8")
    for s in cs.SETS:
        assert s.editable == (s.kind != "iso"), s.id
        if s.kind == "custom":
            assert s.parent in cs.SET_BY_ID and cs.SET_BY_ID[s.parent].kind == "iso"


def test_no_user_facing_label_carries_an_em_dash():
    texts = [r.label for r in cs.ROWS] + [r.note for r in cs.ROWS] \
        + [s.label for s in cs.SETS] + [s.blurb for s in cs.SETS] \
        + list(cs.GROUP_LABELS.values())
    assert not [t for t in texts if "—" in t]


# ---- factory values ---------------------------------------------------------

def test_chromiq_default_is_knuts_2_2_2_3_3_and_the_grey_rows_are_should_rows():
    f = factory_limits("chromiq_default")
    assert [f[r].number for r in cs.OLD_AVG_ROWS] == [2.0, 2.0, 2.0]
    assert [f[r].number for r in cs.OLD_MAX_ROWS] == [3.0, 3.0]
    assert all(f[r].kind == "value" for r in cs.OLD_AVG_ROWS + cs.OLD_MAX_ROWS)
    g = f["grey_balance_neutral_ramp_avg"], f["grey_balance_neutral_ramp_max"]
    assert (g[0].kind, g[0].number, g[1].kind, g[1].number) == ("should", 1.5, "should", 3.0)


def test_tight_is_half_and_quick_is_double_on_the_five_de00_rows():
    d, t, q = (factory_limits(s) for s in ("chromiq_default", "chromiq_tight", "chromiq_quick"))
    for rid in cs.OLD_AVG_ROWS + cs.OLD_MAX_ROWS:
        assert t[rid].number == pytest.approx(d[rid].number / 2)
        assert q[rid].number == pytest.approx(d[rid].number * 2)


def test_chromiq_sets_define_no_limit_on_the_standards_only_rows():
    f = factory_limits("chromiq_default")
    for rid in ("substrate_de00_max", "control_strip_de00_avg",
                "outer_gamut_226_de00_avg", "uniformity_sd"):
        assert f[rid].kind == "none", rid


def test_the_shipped_iso_data_file_is_empty_so_every_iso_cell_reads_a_question_mark():
    """#182 S-2 is open: the numbers of a paid standard are not in the repo.
    A row the standard limits reads ?, a row it does not reads –, and a row
    ChromIQ cannot measure reads ✕ whatever the standard says."""
    doc = json.loads((ROOT / cs.ISO_DATA_FILE).read_text(encoding="utf-8"))
    assert doc["iso_12647_7"] == {} and doc["iso_12647_8"] == {}
    cs.reset_iso_cache()
    f7 = factory_limits("iso_12647_7")
    assert f7["all_de00_avg"].kind == "unknown"
    assert f7["best95_de00_avg"].kind == "none"          # -7 has no such row
    assert f7["substrate_gloss_class"].kind == "unmeasurable"
    f8 = factory_limits("iso_12647_8")
    assert f8["control_strip_de00_max"].kind == "none"   # -8 uses the 95th percentile
    assert f8["control_strip_de00_p95"].kind == "unknown"
    # The two READ-ONLY ISO columns still hold nothing, so neither is offered.
    #
    # THE TWO CUSTOM COLUMNS ARE, AND THAT IS NEW, 2026-09-11. This line used
    # to assert that none of the four ISO-derived sets was offered, because a
    # Custom set inherited its parent's empty cells and therefore had no
    # limit-bearing row (CH-11). Knut ruled the other way: *"the table columns
    # for 'Custom ISO 12647-7' and 'Custom ISO 12647-8' should have selection
    # boxes for all metrics that ChromIQ can check, because it is a custom
    # threshold set […] make sure the metrics have a value that can be tested
    # against."* They now start from ChromIQ's OWN numbers
    # (`_CUSTOM_PLACEHOLDER`), which is why they are selectable; no ISO figure
    # is involved, and the two read-only columns are unchanged.
    assert selectable_set_ids({}) == ["chromiq_default", "chromiq_tight",
                                      "chromiq_quick", "custom_iso_12647_7",
                                      "custom_iso_12647_8"]


def test_a_filled_data_file_lights_the_iso_cells(tmp_path, monkeypatch):
    p = tmp_path / "iso.json"
    p.write_text(json.dumps({"iso_12647_8": {"all_de00_avg": 9.9,
                                             "ramps_30_70_dl_max": [1.0, "should"],
                                             "not_a_row": 1.0}}), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
    cs.reset_iso_cache()
    try:
        f = factory_limits("iso_12647_8")
        assert f["all_de00_avg"] == Limit.value(9.9)
        assert f["ramps_30_70_dl_max"] == Limit.should(1.0)
        assert f["all_de00_p95"].kind == "unknown"       # still not supplied
        assert "not_a_row" not in f
        # the Custom child starts from the parent's numbers
        assert factory_limits("custom_iso_12647_8")["all_de00_avg"] == Limit.value(9.9)
        assert "iso_12647_8" in selectable_set_ids({})
        assert "custom_iso_12647_8" in selectable_set_ids({})
    finally:
        cs.reset_iso_cache()


def test_an_unreadable_data_file_degrades_to_question_marks(tmp_path, monkeypatch):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
    cs.reset_iso_cache()
    try:
        assert factory_limits("iso_12647_7")["all_de00_avg"].kind == "unknown"
    finally:
        cs.reset_iso_cache()


def test_the_bundle_ships_the_data_folder():
    """ALL THREE platforms, because for two of them it did not.

    Windows and Linux shipped without the folder until 2026-09-10. There was no
    error a user could see: `_load_iso_numbers` catches the OSError and logs
    "unreadable", so every cell read `?` exactly as it does on macOS, where the
    file is present and empty. A question mark meaning "we have not licensed
    this number" and a question mark meaning "the file is not in your build"
    looked identical, and the day any number IS licensed the two platforms
    would have kept showing the old answer.
    """
    for spec_name in ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"):
        spec = (ROOT / spec_name).read_text(encoding="utf-8")
        assert "('data/compliance_sets', 'data/compliance_sets')" in spec, (
            f"{spec_name} does not bundle data/compliance_sets")


# ---- limits: JSON, text, overrides -------------------------------------------

@pytest.mark.parametrize("raw, kind, number", [
    (2.0, "value", 2.0), (3, "value", 3.0), ([2.0, "should"], "should", 2.0),
    ([2.0], "value", 2.0), (None, "none", None), ("?", "unknown", None),
    ("x", "unmeasurable", None), ("2,5", "value", 2.5), ("junk", "unknown", None),
    (True, "unknown", None), (float("nan"), "unknown", None), ({}, "unknown", None),
])
def test_limit_from_json_is_tolerant(raw, kind, number):
    lim = Limit.from_json(raw)
    assert lim.kind == kind and lim.number == number


def test_limit_round_trips_through_json():
    for lim in (Limit.value(2.0), Limit.should(1.5), Limit.none(), Limit.unknown(),
                Limit.unmeasurable()):
        assert Limit.from_json(json.loads(json.dumps(lim.to_json()))) == lim


def test_limit_text_uses_a_decimal_point_and_brackets_for_a_should():
    assert limit_text(Limit.value(2.0)) == "2.0"
    assert limit_text(Limit.value(0.75)) == "0.75"
    assert limit_text(Limit.should(2.0)) == "(2.0)"
    assert limit_text(Limit.none()) == "–"
    assert limit_text(Limit.unknown()) == "?"
    assert limit_text(Limit.unmeasurable()) == "✕"


def test_overrides_apply_to_editable_sets_only_and_keep_a_should_a_should():
    ov = {"chromiq_default": {"all_de00_avg": 2.7,
                              "grey_balance_neutral_ramp_avg": 2.0,
                              "all_de00_max": None,          # "no limit"
                              "all_de00_p95": 0.0,           # the spin box's –
                              "uniformity_sd": 1.0,          # cannot be overridden
                              "no_such_row": 1.0},
          "iso_12647_7": {"all_de00_avg": 1.0}}
    e = effective_limits("chromiq_default", ov)
    assert e["all_de00_avg"] == Limit.value(2.7)
    assert e["grey_balance_neutral_ramp_avg"] == Limit.should(2.0)
    assert e["all_de00_max"].kind == "none"
    assert e["all_de00_p95"].kind == "none"
    assert e["uniformity_sd"].kind == "none"
    assert effective_limits("iso_12647_7", ov)["all_de00_avg"].kind == "unknown"
    # garbage shapes never raise
    assert effective_limits("chromiq_default", {"chromiq_default": "x"}) == \
        factory_limits("chromiq_default")
    assert effective_limits("chromiq_default", None) == factory_limits("chromiq_default")


def test_limit_bearing_rows_are_numeric_and_computable():
    lb = limit_bearing(factory_limits("chromiq_default"))
    assert set(lb) == set(cs.OLD_AVG_ROWS) | set(cs.OLD_MAX_ROWS) | {
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max"}
    # an unmeasurable row with a value must never be judged
    assert not limit_bearing({"uniformity_sd": Limit.value(0.5)})


def test_a_runs_copy_round_trips_and_keeps_unknown_future_rows():
    copy = limits_to_json(factory_limits("chromiq_tight"))
    copy["a_row_from_the_future"] = 4.2
    back = limits_from_json(json.loads(json.dumps(copy)))
    assert back["all_de00_avg"] == Limit.value(1.0)
    assert back["a_row_from_the_future"] == Limit.value(4.2)
    assert limits_from_json(None) == {} and limits_from_json("junk") == {}


def test_edited_is_derived_by_comparison_not_by_a_flag():
    base = factory_limits("chromiq_default")
    assert not is_edited(base, "chromiq_default", {})
    changed = dict(base); changed["all_de00_avg"] = Limit.value(2.7)
    assert is_edited(changed, "chromiq_default", {})
    # the same 2.7 stored as a Preferences override is NOT an edit
    assert not is_edited(changed, "chromiq_default", {"chromiq_default": {"all_de00_avg": 2.7}})
    # a historical set id can never be "edited"
    assert not is_edited(changed, "gone_set", {})


def test_legacy_pair_reads_the_all_patch_rows():
    assert legacy_pair(factory_limits("chromiq_default")) == (2.0, 3.0)
    assert legacy_pair(factory_limits("chromiq_tight")) == (1.0, 1.5)
    assert legacy_pair({}) == (2.0, 3.0)


def test_set_label_marks_a_set_that_no_longer_exists():
    assert cs.set_label("chromiq_default") == "ChromIQ default (recommended)"
    assert cs.set_label("gone", "Old name") == "Old name (historical)"
    assert cs.set_label("gone") == "gone (historical)"


# ---- the words ---------------------------------------------------------------

def test_row_verdict_every_case_of_the_spec():
    shall, should = Limit.value(2.0), Limit.should(2.0)
    assert row_verdict(shall, 1.9, True) == PASS
    assert row_verdict(shall, 2.0, True) == PASS                    # at the limit
    assert row_verdict(shall, 2.0000000001, True) == PASS           # float dust
    assert row_verdict(shall, 2.1, True) == FAIL
    assert row_verdict(should, 2.1, True) == COND                   # recommended, exceeded
    assert row_verdict(should, 1.0, True) == PASS
    assert row_verdict(shall, None, True) == N_A                    # chart cannot supply it
    assert row_verdict(shall, 9.9, False) == INFO                   # drift check / profiling
    assert row_verdict(Limit.none(), 5.0, True) == INFO             # no limit, value shown
    assert row_verdict(Limit.none(), None, True) is None            # blank, not INFO (CH-20)
    assert row_verdict(Limit.unknown(), 1.0, True) is None          # not a row
    assert row_verdict(Limit.unmeasurable(), 1.0, True) is None


def _rows(*pairs):
    return [(lim, w) for lim, w in pairs]


def test_summary_with_no_limit_bearing_row_is_n_a_never_pass():
    """CH-21: an emptied Custom column must not summarise PASS for ever."""
    s = set_summary(_rows((Limit.none(), INFO), (Limit.unknown(), None)),
                    set_is_iso=False, graded=True)
    assert s.word == N_A and s.total == 0
    assert "defines no limits" in s.reason


def test_a_column_where_NOTHING_was_checked_is_never_PASS():
    """FOUND BUILDING T3, 2026-09-11, and reachable in the shipped report too.

    A column whose limit-bearing rows are all N-A, and where every one of them
    is a RECOMMENDATION rather than a requirement, fell through every clause to
    PASS. The sentence it printed says "Every value this limit set requires was
    checked and is within its limit", with nothing checked at all.

    T3, "Grey and tone check", shows the two bracketed grey-balance rows and
    nothing else, so it lands in that state on the first chart without an
    8-step grey ramp, which is most of them. A three-patch measurement reaches
    it in the full report.

    A verdict is a statement about measured values, and with none measured
    there is no statement to make.

    MUTATION: drop the `checked == 0` clause and this goes red.
    """
    sh = Limit.should(1.5)
    s = set_summary(_rows((sh, N_A), (sh, N_A)), set_is_iso=False, graded=True)
    assert s.word == N_A, f"{s.word}: a column claimed PASS having checked nothing"
    assert s.checked == 0 and s.total == 2 and s.not_computed == 2
    assert "nothing to judge" in s.reason
    assert "was checked" not in s.reason

    # …and the control: one row actually checked, and PASS is right again.
    v = Limit.value(1.5)
    ok = set_summary(_rows((sh, N_A), (v, PASS)), set_is_iso=False, graded=True)
    assert ok.word == PASS and ok.checked == 1


def test_summary_words_in_order_of_precedence():
    v = Limit.value(2.0); sh = Limit.should(1.5)
    assert set_summary(_rows((v, PASS), (v, FAIL)), set_is_iso=False, graded=True).word == FAIL
    assert set_summary(_rows((v, PASS), (v, FAIL)), set_is_iso=False, graded=False).word == INFO
    assert set_summary(_rows((v, PASS), (v, PASS)), set_is_iso=True, graded=True).word == COND
    assert set_summary(_rows((v, PASS), (sh, COND)), set_is_iso=False, graded=True).word == COND
    assert set_summary(_rows((v, PASS), (v, N_A)), set_is_iso=False, graded=True).word == COND
    # an N-A on a SHOULD row does not demote a ChromIQ set (CH-9)
    s = set_summary(_rows((v, PASS), (v, PASS), (sh, N_A)), set_is_iso=False, graded=True)
    assert s.word == PASS and s.not_computed == 1 and s.checked == 2 and s.total == 3


def test_summary_sentences_never_name_a_standard_or_conformance():
    for word_rows, iso in ((_rows((Limit.value(1.0), FAIL)), True),
                           (_rows((Limit.value(1.0), PASS)), True),
                           (_rows((Limit.value(1.0), PASS)), False)):
        txt = cs.summary_text(set_summary(word_rows, set_is_iso=iso, graded=True))
        assert "conform" not in txt.lower()
        assert "ISO" not in txt
        assert "{" not in txt                       # every placeholder filled


# ---------------------------------------------------------------------------
# The two Custom columns arrive usable, with ChromIQ's own numbers (Knut, W7)
# ---------------------------------------------------------------------------
# 2026-09-11: *"the table columns for 'Custom ISO 12647-7' and 'Custom ISO
# 12647-8' should have selection boxes for all metrics that ChromIQ can check
# […] This applies also to the report limits window in Preferences ==> Reports
# tab. Thus, make sure the metrics have a value that can be tested against."*
# Before this every cell of both columns read ? or –, so nothing was ever
# judged through them, and neither was selectable at all.

CUSTOM_SETS = ("custom_iso_12647_7", "custom_iso_12647_8")
MEASURABLE = tuple(r.id for r in cs.ROWS if r.status in ("now", "build", "ref"))


def test_every_measurable_row_of_a_custom_set_can_be_judged():
    cs.reset_iso_cache()
    for sid in CUSTOM_SETS:
        f = factory_limits(sid)
        missing = [rid for rid in MEASURABLE if not f[rid].is_numeric]
        assert not missing, (
            f"{sid} has no limit on {missing}; a Custom set whose rows read "
            "? or - judges nothing, which is what Knut reported")
        # …and the set is therefore offerable at all (CH-11)
        assert cs.limit_bearing(f)


def test_a_placeholder_never_reaches_a_row_chromiq_cannot_measure():
    """The guarded-write check on the door this opens.

    A number on an `unmeasurable` row would claim ChromIQ tests something it
    cannot; a number on an `unknown` row would be a limit nothing is ever
    compared with, because ChromIQ does not know which patches that row is
    about. Both stay exactly as they were.
    """
    for rid in cs._CUSTOM_PLACEHOLDER:
        assert cs.ROW_BY_ID[rid].status in ("now", "build", "ref"), rid
    cs.reset_iso_cache()
    for sid in CUSTOM_SETS:
        f = factory_limits(sid)
        for row in cs.ROWS:
            if row.status == "unmeasurable":
                assert f[row.id].kind in ("unmeasurable", "none"), row.id
            elif row.status == "unknown":
                assert f[row.id].kind in ("unknown", "none"), row.id


def test_no_placeholder_is_anybody_elses_published_figure():
    """The numbers are ChromIQ default's own, and only those.

    The owner's standing rule on #182 is that no value of ISO 12647-7 or
    ISO 12647-8 goes into the code, and Knut agreed the placeholders need not
    resemble them: *"even if they are not same as those standards (that is not
    relevant for testing the metrics)"*. Pinning the SOURCE of every number,
    rather than the numbers themselves, is what stops one drifting toward a
    real tolerance later because it "looks more realistic".

    **AND THE ALLOWLIST HAD TO BE THE ONE THE RULE NAMES.** It was built from
    ALL THREE ChromIQ tables, so it admitted 1.0, 4.0, 6.0 and 7.0 as well: seven
    numbers where the rule beside `_CUSTOM_PLACEHOLDER` says *"Only ChromIQ
    default's own three numbers are used: 1.5, 2.0 and 3.0"*. A placeholder
    could be moved from 3.0 to 1.0 or from 2.0 to 4.0 and this test would not
    notice, which is precisely the drift it exists to stop, and the grip was
    loose in the direction that matters: a number nobody can trace back to a
    ChromIQ figure is a number somebody has to argue is not a standard's.
    Tight and Quick are HALF and DOUBLE of default, derived from it and not
    limits anybody would reach for on another row.

    MUTATION: set `cmy_solids_dhab_max` to 4.0 (a Quick check number) or
    `substrate_de00_max` to 1.0 (a tight one) and this goes red. Both passed
    before, against the old allowlist.
    """
    allowed = {round(float(lim.number), 6)
               for lim in cs._CHROMIQ_FACTORY["chromiq_default"].values()
               if lim.is_numeric}
    assert allowed, "ChromIQ default's own factory numbers could not be read"
    for rid, lim in cs._CUSTOM_PLACEHOLDER.items():
        assert lim.is_numeric, rid
        assert round(float(lim.number), 6) in allowed, (
            f"{rid} = {lim.number} is not one of ChromIQ default's own numbers "
            f"{sorted(allowed)}. Every placeholder must be traceable to a "
            "ChromIQ figure, never to a standard's.")


def test_the_read_only_iso_columns_are_untouched_by_the_placeholders():
    cs.reset_iso_cache()
    for sid in ("iso_12647_7", "iso_12647_8"):
        f = factory_limits(sid)
        assert not any(lim.is_numeric for lim in f.values()), (
            f"{sid} acquired a number. The read-only columns hold the "
            "standard's own values and ship with none of them.")
        assert not cs.limit_bearing(f)


def test_a_licence_holders_own_file_wins_over_the_placeholder(tmp_path, monkeypatch):
    """A tester who owns the standard still starts from THEIR numbers."""
    p = tmp_path / "iso.json"
    p.write_text(json.dumps({"iso_12647_8": {"all_de00_avg": 9.9}}),
                 encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
    cs.reset_iso_cache()
    try:
        f = factory_limits("custom_iso_12647_8")
        assert f["all_de00_avg"] == Limit.value(9.9), \
            "the placeholder overwrote a number the user's own file supplied"
        # a row their file did not answer still gets ChromIQ's own number
        assert f["all_de00_p95"] == cs._CUSTOM_PLACEHOLDER["all_de00_p95"]
    finally:
        monkeypatch.delenv(cs.ISO_DATA_ENV, raising=False)
        cs.reset_iso_cache()


def test_factory_limits_refuses_a_placeholder_on_an_unmeasurable_row(monkeypatch):
    """The SECOND lock, isolated, because defence in depth that no test can
    reach is decoration.

    The test above pins the table's contents; this one pins that
    `factory_limits` would refuse a bad entry even if somebody added one. A
    mutation that removes the status check has to be able to fail something.
    """
    bad = dict(cs._CUSTOM_PLACEHOLDER)
    bad["control_strip_de00_avg"] = Limit.value(3.0)     # status "unknown"
    bad["light_fastness"] = Limit.value(3.0)             # status "unmeasurable"
    monkeypatch.setattr(cs, "_CUSTOM_PLACEHOLDER", bad)
    cs.reset_iso_cache()
    f = factory_limits("custom_iso_12647_7")
    assert f["control_strip_de00_avg"].kind == "unknown", (
        "a placeholder reached a row ChromIQ cannot compute; the column would "
        "carry a limit nothing is ever compared with")
    assert f["light_fastness"].kind == "unmeasurable"
