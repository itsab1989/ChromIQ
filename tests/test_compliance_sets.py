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
from tests.helpers.iso_files import shipped_limits, use_empty_shipped_iso

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

def test_chromiq_default_is_knuts_2_2_2_3_3_and_the_grey_rows_are_ordinary():
    f = factory_limits("chromiq_default")
    assert [f[r].number for r in cs.OLD_AVG_ROWS] == [2.0, 2.0, 2.0]
    assert [f[r].number for r in cs.OLD_MAX_ROWS] == [3.0, 3.0]
    assert all(f[r].kind == "value" for r in cs.OLD_AVG_ROWS + cs.OLD_MAX_ROWS)
    # THE GREY PAIR KEEPS ITS NUMBERS AND LOSES ITS BRACKET. Knut, 2026-09-21:
    # *"Remove them, so a bracket only ever appears where a standard is
    # involved, and ChromIQ's own sets have requirements and nothing else."*
    g = f["grey_balance_neutral_ramp_avg"], f["grey_balance_neutral_ramp_max"]
    assert (g[0].kind, g[0].number, g[1].kind, g[1].number) == ("value", 1.5, "value", 3.0)


def test_no_shipped_set_marks_any_row_a_recommendation():
    """The consequence of the same ruling, stated once for every set.

    After it, the ONLY source of a should-limit is a licence holder's own ISO
    values file or a row a user marks in an editable Custom column -- so a
    green suite proves nothing about the note path, and the note is driven on
    screen instead. This test is the other half: it fails the day a bracket
    creeps back into a set ChromIQ ships.

    MUTATION: put `Limit.should` back on one grey row and this goes red.
    """
    offenders = {sid: sorted(r for r, l in factory_limits(sid).items()
                             if l.is_should)
                 for sid in cs.SET_IDS}
    assert not any(offenders.values()), offenders


def test_tight_is_half_and_quick_is_double_on_the_five_de00_rows():
    d, t, q = (factory_limits(s) for s in ("chromiq_default", "chromiq_tight", "chromiq_quick"))
    for rid in cs.OLD_AVG_ROWS + cs.OLD_MAX_ROWS:
        assert t[rid].number == pytest.approx(d[rid].number / 2)
        assert q[rid].number == pytest.approx(d[rid].number * 2)


def test_chromiq_sets_define_no_limit_on_the_standards_only_rows():
    f = factory_limits("chromiq_default")
    # …and that is still true of the five rows B8-397 made computable: ChromIQ
    # default's own numbers are Knut's K4 ruling and he did not extend them.
    # They are limited in the two Custom columns, which is where he asked for
    # "a value that can be tested against" for every measurable metric.
    # `uniformity_sd` left this list on 2026-09-23: Knut ruled a method for
    # the two evenness rows and 1.5 on the pairwise one in ChromIQ's own sets
    # (B8-814), so ChromIQ default limits it now.
    for rid in ("substrate_de00_max", "control_strip_de00_avg",
                "outer_gamut_226_de00_avg", "surface_gamut_de00_avg"):
        assert f[rid].kind == "none", rid
    # `macro_uniformity_score` LEFT THIS LIST ON 2026-09-24, and not because
    # ChromIQ default limits it: it is a row ChromIQ cannot measure, and such
    # a row reads ✕ in EVERY set now, ChromIQ's own included (Knut, #182
    # 5815435713, B8-979). "–" would say "no limit on a row ChromIQ judges".
    assert f["macro_uniformity_score"].kind == "unmeasurable"


def test_an_iso_set_the_shipped_file_leaves_empty_reads_a_question_mark(monkeypatch):
    """#182 S-2, §23: each set of the shipped file is EMPTY or COMPLETE, and
    `tests/test_iso_values_ship_as_values_only.py` holds it to that. This test
    reads whichever sets the file leaves empty (both of them until the owner's
    go-ahead) and pins what an empty set looks like: a row the standard limits
    reads ?, a row it does not reads –, and a row ChromIQ cannot measure reads
    ✕ whatever the standard says. A set that ships is pinned there instead."""
    doc = json.loads((ROOT / cs.ISO_DATA_FILE).read_text(encoding="utf-8"))
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(ROOT / cs.ISO_DATA_FILE))
    cs.reset_iso_cache()
    # the unmeasurable and the not-limited rows read the same in both states
    f7 = factory_limits("iso_12647_7")
    assert f7["best95_de00_avg"].kind == "none"          # -7 has no such row
    assert f7["substrate_gloss_class"].kind == "unmeasurable"
    f8 = factory_limits("iso_12647_8")
    assert f8["control_strip_de00_max"].kind == "none"   # -8 uses the 95th percentile
    if not doc["iso_12647_7"]:
        assert f7["all_de00_avg"].kind == "unknown"
    if not doc["iso_12647_8"]:
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
    # against."* They now start from Knut's researched industry figures and
    # ChromIQ's own numbers (`custom_defaults`), which is why they are
    # selectable; no ISO figure is involved, and the two read-only columns
    # are unchanged.
    #
    # A SET THAT SHIPS IS A CHOICE, and one the file leaves empty is not.
    shipped = [s for s in ("iso_12647_7", "iso_12647_8") if doc[s]]
    assert selectable_set_ids({}) == ["chromiq_default", "chromiq_tight",
                                      "chromiq_quick", *shipped,
                                      "custom_iso_12647_7",
                                      "custom_iso_12647_8"]
    cs.reset_iso_cache()


def _users_file(tmp_path, monkeypatch):
    p = tmp_path / "iso.json"
    p.write_text(json.dumps({"iso_12647_8": {"all_de00_avg": 9.9,
                                             "ramps_30_70_dl_max": [1.0, "should"],
                                             "not_a_row": 1.0}}), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
    cs.reset_iso_cache()
    return p


def test_a_filled_data_file_lights_the_iso_cells(tmp_path, monkeypatch):
    """A licence holder's file lights the cells it answers, keeps a should a
    should, drops a row id ChromIQ does not know, and a row it leaves out
    reads ? when nothing ships underneath.

    THE EMPTY SHIPPED STATE IS MADE BY FIXTURE (#182 S-2, §23): the
    repository's file ships both sets now, so over it an unanswered row reads
    the shipped figure, which the next test pins. Red on its mutation: make
    `_load_iso_numbers` ignore the variable, or read a [n, "should"] pair as a
    plain value, and this fails.
    """
    ground = tmp_path / "ground"
    ground.mkdir()
    use_empty_shipped_iso(ground, monkeypatch)
    _users_file(tmp_path, monkeypatch)
    try:
        f = factory_limits("iso_12647_8")
        assert f["all_de00_avg"] == Limit.value(9.9)
        assert f["ramps_30_70_dl_max"] == Limit.should(1.0)
        assert f["all_de00_p95"].kind == "unknown"       # still not supplied
        assert "not_a_row" not in f
        # the Custom child does NOT copy the parent: it starts from the
        # industry defaults (Knut, #182 5815346140)
        assert factory_limits("custom_iso_12647_8")["all_de00_avg"] == \
            cs.custom_defaults("iso_12647_8")["all_de00_avg"]
        assert "iso_12647_8" in selectable_set_ids({})
        assert "custom_iso_12647_8" in selectable_set_ids({})
    finally:
        cs.reset_iso_cache()


def test_a_users_file_is_laid_over_the_shipped_values(tmp_path, monkeypatch):
    """The same file over the REPOSITORY'S shipped values (§23): the user's
    number wins its row and a row they leave out keeps the shipped figure.
    The expected figure is read from the data file, never written here. Red
    on its mutation: read the user's file INSTEAD of laying it over the
    shipped one, and all_de00_p95 reads ?.
    """
    shipped = shipped_limits("iso_12647_8")
    assert "all_de00_p95" in shipped, "the repository ships ISO 12647-8"
    _users_file(tmp_path, monkeypatch)
    try:
        f = factory_limits("iso_12647_8")
        assert f["all_de00_avg"] == Limit.value(9.9)
        assert f["all_de00_p95"] == shipped["all_de00_p95"]
    finally:
        cs.reset_iso_cache()


def test_an_unreadable_data_file_degrades_to_question_marks(tmp_path, monkeypatch):
    """A user's file that is not JSON contributes nothing. Over nothing
    shipped every cell reads ?; over the repository's shipped values the
    shipped figure stands, because a broken file cannot blank it. Red on its
    mutation: let a parse error raise, or let it replace the shipped ground.
    """
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    shipped = shipped_limits("iso_12647_7")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
    cs.reset_iso_cache()
    try:
        assert factory_limits("iso_12647_7")["all_de00_avg"] == \
            shipped["all_de00_avg"]
        ground = tmp_path / "ground"
        ground.mkdir()
        use_empty_shipped_iso(ground, monkeypatch)
        monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
        cs.reset_iso_cache()
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
                              "macro_uniformity_score": 1.0,  # cannot be overridden
                              "no_such_row": 1.0},
          "iso_12647_7": {"all_de00_avg": 1.0}}
    e = effective_limits("chromiq_default", ov)
    assert e["all_de00_avg"] == Limit.value(2.7)
    # NO SHIPPED SET MARKS A ROW A RECOMMENDATION ANY MORE (Knut, 2026-09-21),
    # so the kind-preserving half of this rule is exercised by
    # test_an_override_keeps_a_licence_holders_should_a_should below, against
    # the one source of a should-limit that is left. Here the grey row is an
    # ordinary limit and an override keeps it one.
    assert e["grey_balance_neutral_ramp_avg"] == Limit.value(2.0)
    assert e["all_de00_max"].kind == "none"
    assert e["all_de00_p95"].kind == "none"
    # The override on a row ChromIQ cannot measure is still ignored; the row
    # reads ✕ as it does in every set (B8-979), never the 1.0, never "–".
    assert e["macro_uniformity_score"].kind == "unmeasurable"
    # A READ-ONLY SET TAKES NO OVERRIDE: it keeps exactly its factory cell,
    # which since #182 S-2 is the shipped figure (and ? where nothing ships).
    # The precondition keeps the check honest: were the shipped figure the
    # override's own 1.0, an applied override would pass unseen.
    iso7 = factory_limits("iso_12647_7")["all_de00_avg"]
    assert iso7 != Limit.value(1.0)
    assert effective_limits("iso_12647_7", ov)["all_de00_avg"] == iso7
    # garbage shapes never raise
    assert effective_limits("chromiq_default", {"chromiq_default": "x"}) == \
        factory_limits("chromiq_default")
    assert effective_limits("chromiq_default", None) == factory_limits("chromiq_default")


def test_limit_bearing_rows_are_numeric_and_computable():
    lb = limit_bearing(factory_limits("chromiq_default"))
    assert set(lb) == set(cs.OLD_AVG_ROWS) | set(cs.OLD_MAX_ROWS) | {
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        # ChromIQ's own two repeatability rows. They are named here rather
        # than the set being loosened, because this assertion is the record of
        # exactly what ChromIQ default judges, and a row joining that list is
        # a deliberate act each time.
        "repeat_patches_de00_max", "repeat_measurement_de00_max",
        # the two evenness rows, Knut 2026-09-22 (B8-814)
        "uniformity_sd", "uniformity_de00_max_from_mean"}
    # an unmeasurable row with a value must never be judged
    assert not limit_bearing({"macro_uniformity_score": Limit.value(0.5)})


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
    # KNUT RETIRED COND AS A ROW WORD, 2026-09-21: *"all metrics being tested
    # against a threshold shows as FAIL or PASS (always, also for the
    # standards), and the COND term is retired, all tests that fail or pass are
    # handled equally"*. A recommendation is still a recommendation in the
    # DATA -- the bracket, `is_should` and the numbered note all survive -- and
    # the word it produces is now the ordinary one.
    #
    # MUTATION: restore `return COND if limit.is_should else FAIL` and the
    # first line below goes red.
    assert row_verdict(should, 2.1, True) == FAIL                   # recommended, exceeded
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
    # THE ISO CAP IS RETIRED (Knut, 2026-09-22): this line read `== COND`
    # until that day. The caveat it used to carry is now a note, and the
    # sentence beside the word still says the figures are applied to your
    # chart, which is asserted below rather than left to the word.
    _iso = set_summary(_rows((v, PASS), (v, PASS)), set_is_iso=True, graded=True)
    assert _iso.word == PASS
    # **A LITERAL, NOT THE DICT ENTRY** (adversary round 40c, finding 7). This
    # line read `== cs.SUMMARY_REASONS["iso"]` under a comment claiming it
    # asserted the sentence still says the figures are applied to your chart.
    # It asserted no such thing: it compared the returned string to the same
    # entry it came from, so deleting that clause from the sentence left it
    # green. A test that reads the constant it checks agrees with whatever the
    # code says.
    assert "not a test against that standard" in _iso.reason, _iso.reason
    assert _iso.reason is cs.SUMMARY_REASONS["iso"], "wrong branch taken"
    assert set_summary(_rows((v, PASS), (sh, COND)), set_is_iso=False, graded=True).word == COND
    # **AN N-A NEVER DEMOTES, WHATEVER ROW IT IS ON.** This line used to read
    # `== COND` for a REQUIRED row, which is the rule Knut replaced on
    # 2026-09-21: *"Not Applicable must not be counted as a fail, so the
    # overall verdict should show PASS, not COND, if all others pass … a
    # metric that is not applicable should not have verdict conditional
    # because COND does not indicate which of the verdicts cause the COND."*
    # See §15.6 of docs/design/measurement_report_limits.md.
    r = set_summary(_rows((v, PASS), (v, N_A)), set_is_iso=False, graded=True)
    assert r.word == PASS and r.not_computed == 1
    # …and the count is still reported beside the word, so nothing is hidden
    assert r.checked == 1 and r.total == 2
    # an N-A on a SHOULD row never demoted a ChromIQ set either (CH-9)
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


def test_a_default_never_reaches_a_row_chromiq_cannot_measure():
    """The guarded-write check on the door this opens.

    A number on an `unmeasurable` row would claim ChromIQ tests something it
    cannot; a number on an `unknown` row would be a limit nothing is ever
    compared with, because ChromIQ does not know which patches that row is
    about. Both stay exactly as they were.

    AND KNUT'S OWN FILE IS THE REASON THIS MATTERS NOW. The figures he
    researched (#182, 2026-09-21) cover rows ChromIQ cannot judge today as
    well as rows it can; only the judgeable ones became defaults. A later
    round that sweeps the rest in "because they are in his file" is exactly
    what this stops.
    """
    for parent in cs.ISO_SET_IDS:
        for rid in cs.custom_defaults(parent):
            assert cs.ROW_BY_ID[rid].status in ("now", "build", "ref"), rid
    cs.reset_iso_cache()
    for sid in CUSTOM_SETS:
        f = factory_limits(sid)
        for row in cs.ROWS:
            if row.status == "unmeasurable":
                assert f[row.id].kind in ("unmeasurable", "none"), row.id
            elif row.status == "unknown":
                assert f[row.id].kind in ("unknown", "none"), row.id


def test_chromiqs_own_half_of_the_defaults_is_anybody_elses_published_figure():
    """The numbers ChromIQ supplies are ChromIQ default's own, and only those.

    The owner's standing rule on #182 is that no value of ISO 12647-7 or
    ISO 12647-8 goes into the code, and Knut agreed ChromIQ's own numbers need
    not resemble them: *"even if they are not same as those standards (that is
    not relevant for testing the metrics)"*. Pinning the SOURCE of every
    number, rather than the numbers themselves, is what stops one drifting
    toward a real tolerance later because it "looks more realistic".

    **AND THE ALLOWLIST HAD TO BE THE ONE THE RULE NAMES.** It was built from
    ALL THREE ChromIQ tables, so it admitted 1.0, 4.0, 6.0 and 7.0 as well: seven
    numbers where the rule beside `_CUSTOM_CHROMIQ_FILL` says *"Only ChromIQ
    default's own three numbers are used: 1.5, 2.0 and 3.0"*. A number
    could be moved from 3.0 to 1.0 or from 2.0 to 4.0 and this test would not
    notice, which is precisely the drift it exists to stop, and the grip was
    loose in the direction that matters: a number nobody can trace back to a
    ChromIQ figure is a number somebody has to argue is not a standard's.
    Tight and Quick are HALF and DOUBLE of default, derived from it and not
    limits anybody would reach for on another row.

    **IT GOVERNS `_CUSTOM_CHROMIQ_FILL` AND NOT THE WHOLE TABLE ANY MORE.**
    Knut's researched industry figures became the Custom columns' other half
    on 2026-09-21 and are deliberately NOT ChromIQ's three numbers; the test
    below is their guard. Widening this allowlist to admit them would have
    retired the rule for both halves at once, which is why there are two
    tests.

    MUTATION: set `cmy_solids_dhab_max` to 4.0 (a Quick check number) or
    `substrate_de00_max` to 1.0 (a tight one) and this goes red. Both passed
    before, against the old allowlist.
    """
    allowed = {round(float(lim.number), 6)
               for lim in cs._CHROMIQ_FACTORY["chromiq_default"].values()
               if lim.is_numeric}
    assert allowed, "ChromIQ default's own factory numbers could not be read"
    for rid, lim in cs._CUSTOM_CHROMIQ_FILL.items():
        assert lim.is_numeric, rid
        assert round(float(lim.number), 6) in allowed, (
            f"{rid} = {lim.number} is not one of ChromIQ default's own numbers "
            f"{sorted(allowed)}. Every number ChromIQ itself puts on a Custom "
            "column must be traceable to a ChromIQ figure, never to a "
            "standard's.")


#: The shape and contents of Knut's researched block, as delivered.
#:
#: A DIGEST, NOT THE NUMBERS. Restating nineteen figures here would make the
#: test a second copy that drifts from the first; a digest goes red on any
#: change to any of them and says so. If you changed them deliberately, print
#: the new digest with the snippet in the failure message and put it here in
#: the same commit that changes the table.
_INDUSTRY_DIGEST = \
    "3179a54b9dd6b7bf4ef9e146c5551e3911a40d55d5c79f6642ab91e15517e223"
#: (Changed 2026-09-25 on Knut's instruction, #182 5831473881: "For the three
#: mentioned above, use 3,00 for all of them." and the two control-strip rows
#: each column was given from the other, once: 5831783959 "this was not a
#: general rule, but a one time operation to set the new default values.")
#: And his evenness figures from the 2026-09-21 file, never read until
#: 5831860724: "I thought I gave you the default numbers".
#: (Changed 2026-09-24 on Knut's instruction, K33, #182 5816565326: his second
#: set of figures, added to both columns where a row took ChromIQ's own
#: number; where it would have replaced a figure of 2026-09-21 the earlier
#: one is kept. `test_knuts_k33_figures_fill_only_the_rows_that_took_ours`.)

#: Which rows Knut's research covers per column, from his file of 2026-09-21.
#: They differ between the columns because his file follows each standard's
#: own structure, and that difference is the thing a merge is most likely to
#: flatten by accident.
_INDUSTRY_ROWS = {
    "iso_12647_7": (
        "all_de00_avg", "all_de00_p95", "cmy_solids_dhab_max",
        "control_strip_de00_avg", "control_strip_de00_max",
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "outer_gamut_226_de00_avg", "solids_de00_max", "substrate_de00_max",
        # K33, 2026-09-24
        "best95_de00_avg", "worst5_de00_avg", "all_de00_max",
        "surface_gamut_de00_avg", "ramps_30_70_dl_max",
        # from -8, once (Knut, #182 5831473881 / 5831783959)
        "control_strip_de00_p95",
        # evenness, his file of 2026-09-21 (#182 5831860724)
        "uniformity_sd", "uniformity_de00_max_from_mean"),
    "iso_12647_8": (
        "all_de00_avg", "all_de00_p95", "control_strip_de00_avg",
        "control_strip_de00_p95", "grey_balance_neutral_ramp_avg",
        "grey_balance_neutral_ramp_max", "ramps_30_70_dl_max",
        "substrate_de00_max", "surface_gamut_de00_avg",
        # K33, 2026-09-24
        "solids_de00_max", "cmy_solids_dhab_max", "best95_de00_avg",
        "worst5_de00_avg", "all_de00_max", "outer_gamut_226_de00_avg",
        # from -7, once (Knut, #182 5831473881 / 5831783959)
        "control_strip_de00_max",
        # evenness, his file of 2026-09-21 (#182 5831860724)
        "uniformity_sd", "uniformity_de00_max_from_mean"),
}

#: Knut's K33 figures, #182 5816565326 (2026-09-24), by the row each of his
#: labels names ("Maximum deltaE00, solid colours" = 3,00 and so on), for
#: BOTH Custom columns.
_K33 = {"solids_de00_max": 3.0, "cmy_solids_dhab_max": 2.5,
        "best95_de00_avg": 2.0, "worst5_de00_avg": 2.0, "all_de00_max": 2.0,
        "outer_gamut_226_de00_avg": 2.5, "surface_gamut_de00_avg": 3.0,
        "ramps_30_70_dl_max": 2.0}
#: Where a K33 figure differs from his own figure of 2026-09-21 for that
#: column: the earlier one is kept, and the choice is put to him.
#: The three rows where his K33 figure and his 2026-09-21 research disagreed.
#: Kept at the earlier figure until Knut ruled, #182 5831473881 (2026-09-25):
#: "For the three mentioned above, use 3,00 for all of them."
_K33_KEPT_EARLIER = {("iso_12647_7", "solids_de00_max"): 3.0,
                     ("iso_12647_7", "outer_gamut_226_de00_avg"): 3.0,
                     ("iso_12647_8", "surface_gamut_de00_avg"): 3.0}


def test_knuts_k33_figures_fill_only_the_rows_that_took_ours():
    """K33: his eight figures reach both Custom columns as RESEARCHED figures,
    except where one would overwrite his own earlier research, which stays.

    Red on its mutations: drop a K33 row from either column (it falls back to
    ChromIQ's fill and the source check fails); let a K33 figure overwrite
    one of the three kept ones (the kept-earlier check fails).
    """
    for parent in cs.ISO_SET_IDS:
        src = cs.custom_default_sources(parent)
        lim = cs.custom_defaults(parent)
        for rid, number in _K33.items():
            assert src[rid] == "industry", (parent, rid)
            want = _K33_KEPT_EARLIER.get((parent, rid), number)
            assert lim[rid] == cs.Limit.value(want), (parent, rid, lim[rid])
    # After it, and after each column was given the other's figure where it
    # had none, once (Knut, #182 5831473881 and 5831783959), and his evenness
    # figures (5831860724), only two rows of each column start from
    # ChromIQ's own numbers: both repeatability rows, which neither set of his
    # figures covers.
    for parent in cs.ISO_SET_IDS:
        ours = sorted(r for r, s in cs.custom_default_sources(parent).items()
                      if s == "chromiq")
        assert len(ours) == 2, (parent, ours)


def test_the_researched_industry_figures_are_exactly_what_knut_delivered():
    """Knut's own figures, unchanged, and nobody else's.

    Knut, #182, 2026-09-21: *"I have filled in the json file with the
    threshold limits I have manually set, based on findings from research
    online of industry practice and reasoned limits from the industry, which
    are independently set by various actors in the industry, companies or
    communities, not based on ISO standard values. I would like these to be
    set as default for the two Custom ISO 12647 columns."*

    Two things are pinned, because two different accidents are possible. The
    ROW SETS, because the two columns take different rows and a careless merge
    would give both columns the same ones. The CONTENTS, by digest, because a
    value edited by hand in this table is a value nobody researched.

    The digest deliberately does not restate the figures: they are in
    `compliance_sets` and a second copy here would be a second thing to keep
    right.

    MUTATION PROVEN TO LAND: change any one figure and the digest assertion
    goes red; move a row from one column to the other and the row-set
    assertion goes red first.
    """
    import hashlib
    import json as _json

    for parent, rows in _INDUSTRY_ROWS.items():
        assert tuple(sorted(cs._CUSTOM_INDUSTRY[parent])) == tuple(sorted(rows)), (
            f"{parent}: the rows Knut's research covers changed. His file "
            "gives a figure per standard's own structure, so the two columns "
            "are not interchangeable.")
    assert set(cs._CUSTOM_INDUSTRY) == set(cs.ISO_SET_IDS)

    blob = _json.dumps(
        {p: {rid: [lim.kind, lim.number] for rid, lim in sorted(b.items())}
         for p, b in sorted(cs._CUSTOM_INDUSTRY.items())},
        sort_keys=True, separators=(",", ":"))
    got = hashlib.sha256(blob.encode()).hexdigest()
    assert got == _INDUSTRY_DIGEST, (
        f"the researched figures changed (digest {got}). They are Knut's, "
        "delivered on 2026-09-21; if you changed them on his instruction, "
        "put the new digest here in the same commit.")


def test_every_custom_default_comes_from_one_of_the_two_named_sources():
    """No third source can appear without a name.

    `custom_default_sources` is what the Report limits window's description is
    generated from, so a row that is in neither table, or in both under two
    names, would make that sentence wrong rather than merely incomplete.
    """
    for parent in cs.ISO_SET_IDS:
        defaults = cs.custom_defaults(parent)
        sources = cs.custom_default_sources(parent)
        assert set(defaults) == set(sources)
        assert set(sources.values()) <= {"industry", "chromiq"}
        for rid, src in sources.items():
            in_industry = rid in cs._CUSTOM_INDUSTRY[parent]
            assert (src == "industry") == in_industry, rid
            expect = (cs._CUSTOM_INDUSTRY[parent][rid] if in_industry
                      else cs._CUSTOM_CHROMIQ_FILL[rid])
            assert defaults[rid] == expect, rid
        # every measurable row still has a limit, whichever source gave it
        assert set(defaults) == set(MEASURABLE)


def test_a_custom_columns_counts_add_up_to_what_it_judges():
    """The counts the window's sentence is built from are the table's own.

    `custom_default_counts` is the only thing standing between "this column
    holds researched figures" and a sentence nobody re-measured, so it may not
    be a tally kept by hand: industry + chromiq + supplied has to equal the
    rows the column is actually judged on.
    """
    cs.reset_iso_cache()
    for sid in CUSTOM_SETS:
        c = cs.custom_default_counts(sid)
        assert c["industry"] + c["chromiq"] + c["supplied"] == c["total"]
        assert c["total"] == len(cs.limit_bearing(factory_limits(sid)))
        assert c["industry"] > 0, (
            f"{sid} starts from no researched figure; Knut asked for them to "
            "be the defaults of BOTH Custom columns")
    # a set that is not a Custom one has nothing to attribute
    for sid in ("chromiq_default", "iso_12647_7"):
        assert cs.custom_default_counts(sid) == {
            "industry": 0, "chromiq": 0, "supplied": 0, "total": 0}


def test_the_read_only_iso_columns_are_untouched_by_the_placeholders(
        tmp_path, monkeypatch):
    """The Custom columns' starting numbers (Knut's researched figures and
    ChromIQ's own) never reach the two READ-ONLY ISO columns. Those hold
    exactly what the shipped file gives them: every number there is the
    file's own figure for that row (read from the file, not written here),
    and over an EMPTY shipped file, made by fixture, they hold no number at
    all. Red on its mutation: let `factory_limits` fill a read-only set from
    `custom_defaults`, and a row the file leaves out, or the empty state,
    acquires a number.
    """
    from tests.helpers.iso_files import use_repo_iso
    use_repo_iso(monkeypatch)
    try:
        for sid in ("iso_12647_7", "iso_12647_8"):
            shipped = shipped_limits(sid)
            for rid, lim in factory_limits(sid).items():
                if lim.is_numeric:
                    assert shipped.get(rid) == lim, (
                        f"{sid}.{rid} holds {lim}, which is not the shipped "
                        "file's figure for that row")
        use_empty_shipped_iso(tmp_path, monkeypatch)
        for sid in ("iso_12647_7", "iso_12647_8"):
            f = factory_limits(sid)
            assert not any(lim.is_numeric for lim in f.values()), (
                f"{sid} acquired a number over an empty shipped file. The "
                "read-only columns hold the standard's own values only.")
            assert not cs.limit_bearing(f)
    finally:
        cs.reset_iso_cache()


def test_a_licence_holders_own_file_never_fills_a_custom_column(tmp_path, monkeypatch):
    """The Custom columns are alternatives to the standards, never copies.

    Knut, #182 5815346140 (2026-09-24): *"they should no longer be copies
    from the ISO 12647-7 and ISO 12647-8 limit sets, but rather alternative
    limit sets to the standards. Set the default limits for Custom ISO
    12647-7 and Custom ISO 12647-8 to the industry limits previously
    decided."* A user's own values file lights the read-only column and
    nothing in the Custom one. Red on its mutation: let `factory_limits`
    keep a user's number on a Custom row again, and 9.9 comes back.
    """
    p = tmp_path / "iso.json"
    p.write_text(json.dumps({"iso_12647_8": {"all_de00_avg": 9.9},
                             "iso_12647_7": {"all_de00_avg": 9.9}}),
                 encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(p))
    cs.reset_iso_cache()
    try:
        assert factory_limits("iso_12647_8")["all_de00_avg"] == Limit.value(9.9)
        for parent in ("iso_12647_7", "iso_12647_8"):
            f = cs.limit_bearing(factory_limits("custom_" + parent))
            want = {rid: lim for rid, lim in cs.custom_defaults(parent).items()
                    if cs.ROW_BY_ID[rid].status in ("now", "build", "ref")}
            assert f == want, parent
            for rid, lim in cs._CUSTOM_INDUSTRY[parent].items():
                assert f[rid] == lim, (parent, rid)
            assert cs.custom_default_counts("custom_" + parent)["supplied"] == 0
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
    # NO SHIPPED ROW IS `unknown` ANY MORE (B8-397 gave the last five of them a
    # detection method), so the row that stands for "ChromIQ does not know
    # which patches this is about" has to be built here. The lock is what is
    # under test, not which row happens to trip it, and a lock no test can
    # reach is decoration.
    ghost = cs.Row("ghost_unknown_row", "selected", "A row nobody can compute",
                   "ΔE00", "unknown",
                   blurb="A row whose population ChromIQ does not know.",
                   detect="ChromIQ does not know which patches this is about.")
    monkeypatch.setitem(cs.ROW_BY_ID, ghost.id, ghost)
    monkeypatch.setattr(cs, "ROWS", cs.ROWS + (ghost,))
    monkeypatch.setitem(cs._ISO_ROWS, "iso_12647_7",
                        cs._ISO_ROWS["iso_12647_7"] + (ghost.id,))
    bad = dict(cs._CUSTOM_CHROMIQ_FILL)
    bad[ghost.id] = Limit.value(3.0)                     # status "unknown"
    bad["light_fastness"] = Limit.value(3.0)             # status "unmeasurable"
    monkeypatch.setattr(cs, "_CUSTOM_CHROMIQ_FILL", bad)
    cs.reset_iso_cache()
    f = factory_limits("custom_iso_12647_7")
    assert f[ghost.id].kind == "unknown", (
        "a placeholder reached a row ChromIQ cannot compute; the column would "
        "carry a limit nothing is ever compared with")
    assert f["light_fastness"].kind == "unmeasurable"


def test_the_iso_template_gives_everything_except_the_numbers():
    """What a licence holder gets, and what ChromIQ may never put in it.

    Knut asked for the standards' limits *"in a table, and in the same sequence
    of the metrics in the Report Limits window"*. The numbers cannot come from
    us: this repository published those tables once by accident already, and
    DIN answered in writing on 2026-09-18 that putting them into software is
    licensed at 50 % of the standard's purchase price.

    So the template carries the STRUCTURE, which has been in the open in
    `_ISO_ROWS` since the sets existed, and every value is null. This guard is
    here because the file is one careless commit away from being the thing that
    caused the trouble last time: **if any value in it is ever a number, this
    test goes red.**
    """
    doc = json.loads(cs.iso_values_template())
    order = {r.id: i for i, r in enumerate(cs.ROWS)}

    for sid in ("iso_12647_7", "iso_12647_8"):
        rows = doc[sid]
        assert rows, f"{sid} lists no rows at all"
        assert all(v is None for v in rows.values()), (
            f"{sid} carries a NUMBER. ChromIQ may not ship the values of a "
            f"paid standard: {[k for k, v in rows.items() if v is not None]}")
        seq = [order[r] for r in rows]
        assert seq == sorted(seq), (
            f"{sid} is not in the Report limits window's order, which is the "
            f"one thing the template was asked for")
        assert set(rows) == {r for r in cs._ISO_ROWS[sid] if r in order}

    # and it says how to use it, because a template nobody can act on is a file
    assert "CHROMIQ_COMPLIANCE_ISO_FILE" in doc["_readme"]
    # every row is named in words, so it can be filled in without reading code
    assert set(doc["_rows"]) >= set(doc["iso_12647_7"]) | set(doc["iso_12647_8"])


def test_one_set_at_a_time_is_offered_too():
    doc = json.loads(cs.iso_values_template("iso_12647_8"))
    assert "iso_12647_8" in doc and "iso_12647_7" not in doc
