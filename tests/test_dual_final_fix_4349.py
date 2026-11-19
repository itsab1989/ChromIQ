"""4.3.49, the independent review of the kept conditions
(``2026-11-19_dual_continue_review/review_continue.txt``): its SHOULD items.

SHOULD-1  A dual measurement with NO M1 / M2 at all (lost to a save failure,
          ended in 4.3.48, imported, replaced, or averaged) was told "the other
          strips keep their M1 and M2" and promised completion by Continue,
          also when it was an average. Now: a sentence that says it has M0
          only, and an average is not offered Continue at all.
SHOULD-3  Tests for claims nothing guarded: the Beta switch in ``_fill_main``
          with a partial pair on disk, and the "fill-only guide ends as an
          ordinary read" flag.
SHOULD-4  The fill note promised all three conditions whatever instrument
          would read: now it follows what is known before the read.

The files are written by hand here (the engine's own files are proved by the
replay tests in ``test_conditions_kept_4349.py``); the header keywords and the
pair names are the engine's.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow import i1pro3_conditions as ic


def tr_(s):
    from core.i18n import tr
    return tr(s)


def _ti3(path: Path, locs, *, dual=True, cond="M0", of=None, value=1.0):
    head = ['CTI3', 'KEYWORD "MEASUREMENT_CONDITION"',
            f'MEASUREMENT_CONDITION "{cond}"']
    if dual:
        head += ['KEYWORD "CHROMIQ_DUAL_SCAN"', 'CHROMIQ_DUAL_SCAN "i1pro2"']
    else:
        head += ['TARGET_INSTRUMENT "X-Rite i1Pro 3"']
    if of:
        head += ['KEYWORD "CHROMIQ_CONDITION_OF"', f'CHROMIQ_CONDITION_OF "{of}"']
    rows = [f'"{loc}" {value + i / 100:.4f}' for i, loc in enumerate(locs)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(head + [
        'BEGIN_DATA_FORMAT', 'SAMPLE_LOC XYZ_X', 'END_DATA_FORMAT',
        f'NUMBER_OF_SETS {len(locs)}', 'BEGIN_DATA'] + rows + ['END_DATA', '']),
        encoding="latin-1")
    return path


def _run(tmp: Path) -> Path:
    """A run folder laid out as the app's (<project>/runs/run1/<project>.ti3)."""
    d = tmp / "Proj" / "runs" / "run1"
    d.mkdir(parents=True)
    return d / "Proj.ti3"


def _partial_pair(main: Path, locs, m2_locs=None):
    key = ic.data_block_hash(main)
    for cond, ls in (("M1", locs), ("M2", m2_locs if m2_locs is not None
                                    else locs)):
        p = ic.partial_sibling_path(main, cond)
        _ti3(p, ls, cond=cond, of=key, value=2.0)


# ================================================== SHOULD-1, Build Profile

def test_a_dual_measurement_without_any_pair_is_not_told_others_keep_theirs(
        tmp_path):
    main = _ti3(_run(tmp_path), ["A1", "A2", "B1", "B2"])
    assert ic.no_pair_kept(main) is True
    why = ic.no_file_reason(main)
    assert "keep their" not in why
    assert why == tr_(
        "This dual scan has M0 only: no M1 and M2 belong to its "
        "readings as they are now. They could not be kept during the "
        "measurement, or the readings were changed afterwards (for "
        "example imported or replaced). To add them, go to the "
        "Measure tab, tick “Refine / resume existing measurement "
        "(-r)” and press Continue Measurement, with the dual scan "
        "still switched on: ChromIQ takes you back to {strips} for a "
        "new reading with both passes. Until then this measurement "
        "can be built from M0 only.").format(
            strips=tr_("strips {names}").format(names="A, B"))
    # and the Build Profile row says the same
    m1 = [c for c in ic.choices_for(main) if c.cond == "M1"][0]
    assert not m1.usable and m1.reason == why


def test_a_partial_pair_still_says_the_other_strips_keep_theirs_in_chart_order(
        tmp_path):
    """N-8: named in chart order ("strips C, D"), not file order."""
    main = _ti3(_run(tmp_path), ["A1", "B1", "D1", "C1"])
    _partial_pair(main, ["A1", "B1"])
    assert ic.no_pair_kept(main) is False
    why = ic.no_file_reason(main)
    assert "The other strips keep their M1 and M2" in why
    assert tr_("strips {names}").format(names="C, D") in why


def test_an_averaged_dual_measurement_is_not_offered_continue(tmp_path):
    """An average of reads that have no M1 and M2: Continue would replace
    the averaged readings of every strip it reads, so it is not offered;
    the reason says what does give M1 and M2."""
    main = _ti3(_run(tmp_path), ["A1", "B1", "C1"])
    for n in (1, 2):
        _ti3(main.parent / "reads" / f"read{n}.ti3", ["A1", "B1", "C1"])
    assert ic.averaged_read_count(main) == 2
    assert ic.m0_only_locs(main) == []
    assert ic.no_pair_kept(main) is False
    why = ic.no_file_reason(main)
    assert why == tr_(
        "This measurement is the average of {n} reads and has M0 "
        "only: M1 and M2 are averaged only when every read has them. "
        "Continue Measurement does not complete an average, because "
        "it would replace the averaged readings of every strip it "
        "reads with a single reading. For M1 and M2, measure the "
        "chart again with the dual scan switched on, each time you "
        "measure a read to average, so that every read has them."
        ).format(n=2)
    m1 = [c for c in ic.choices_for(main) if c.cond == "M1"][0]
    assert m1.reason == why


def test_a_read_kept_for_averaging_is_not_itself_an_average(tmp_path):
    main = _ti3(_run(tmp_path), ["A1"])
    r1 = _ti3(main.parent / "reads" / "read1.ti3", ["A1"])
    _ti3(main.parent / "reads" / "read2.ti3", ["A1"])
    assert ic.averaged_read_count(r1) == 0
    assert ic.averaged_read_count(main) == 2


# ================================================== the Measure tab's note

class _S(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def _fake(main: Path, resume: bool, settings, *, plan=None, decision=None):
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan import session as D
    f = SimpleNamespace(
        _settings=settings, _engine_selected=lambda: True,
        _selected_measurement_ti3=lambda: main,
        _strip_of=lambda loc: "".join(c for c in loc if c.isalpha()).upper(),
        _strip_index=lambda s: ord(s[0]) - 65,
        _measurement_to_continue=lambda: main if resume else None,
        _dual_plan_now=lambda: plan if plan is not None else D.Plan(True),
        _dual_model_decision=lambda fresh=False: decision)
    f._fill_main = lambda: TabMeasure._fill_main(f)
    f._fill_strips = lambda main=None: TabMeasure._fill_strips(f, main)
    f._fill_instrument = lambda m, d: TabMeasure._fill_instrument(f, m, d)
    return f


def _on():
    from workflow.dual_scan import session as D
    return _S({ic.SETTING: True, D.SETTING: True})


def test_the_measure_tab_says_m0_only_when_no_pair_is_kept(tmp_path, qapp):
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    main = _ti3(_run(tmp_path), ["A1", "B1"])
    names = tr_("strips {names}").format(names="A, B")
    res = _fake(main, True, _on())
    assert TabMeasure._fill_note_text(res) == \
        M.M_DUAL_CONTINUE_FILL_ALL.render(strips=names)
    off = _fake(main, False, _on())
    assert TabMeasure._fill_note_text(off) == M.M_DUAL_FILL_OFFER_ALL.render(
        strips=names, resume=tr_("Refine / resume existing measurement (-r)"),
        start=tr_("Continue Measurement"))
    for t, b in (TabMeasure._fill_note_text(res),
                 TabMeasure._fill_note_text(off)):
        assert "keep their" not in b


def test_the_measure_tab_offers_nothing_for_an_average(tmp_path, qapp):
    from ui.tabs.tab_measure import TabMeasure
    main = _ti3(_run(tmp_path), ["A1", "B1"])
    for n in (1, 2):
        _ti3(main.parent / "reads" / f"read{n}.ti3", ["A1", "B1"])
    assert TabMeasure._fill_note_text(_fake(main, True, _on())) == ("", "")
    assert TabMeasure._fill_note_text(_fake(main, False, _on())) == ("", "")


# ================================================== SHOULD-3 a: the switch

@pytest.mark.parametrize("dual_main", [True, False])
def test_the_beta_switch_off_offers_nothing_even_with_a_partial_pair(
        tmp_path, qapp, dual_main):
    """The reviewer removed the switch from `_fill_main` and 289 tests stayed
    green: the only test had no measurement on disk. Here a real partial
    pair is in step, so only the switch keeps the note away."""
    from ui.tabs.tab_measure import TabMeasure
    from workflow.dual_scan import session as D
    main = _ti3(_run(tmp_path), ["A1", "B1", "C1"], dual=dual_main)
    _partial_pair(main, ["A1"])
    assert ic.strips_of(ic.m0_only_locs(main)) == ["B", "C"]
    on = _S({ic.SETTING: True, D.SETTING: True})
    assert TabMeasure._fill_note_text(_fake(main, True, on))[0]   # the control
    for settings in (_S({}), _S({D.SETTING: True})):
        f = _fake(main, True, settings)
        assert TabMeasure._fill_main(f) is None
        assert TabMeasure._fill_note_text(f) == ("", "")
        f._fill_guided_strips = lambda listed: TabMeasure._fill_guided_strips(
            f, listed)
        assert TabMeasure._fill_guided_strips(f, ["D"]) == ["D"]


# ================================================== SHOULD-3 b: the flag

def _guide(active: bool, filled):
    from ui.tabs.tab_measure import TabMeasure
    f = SimpleNamespace(_guided_refinement_active=active,
                        _fill_only_guide=False, _fill_guided=[])
    f._fill_guided_strips = lambda listed: filled(listed)
    return f, (lambda strips, resuming=True, **kw: TabMeasure._plan_fill_guide(
        f, strips, resuming, SimpleNamespace(engine_helper="h", **kw)))


def test_a_guide_only_for_the_gaps_is_flagged_to_end_as_an_ordinary_read():
    """The reviewer forced the flag to False and every test stayed green."""
    f, plan = _guide(False, lambda listed: ["B", "C"])
    assert plan([]) == ["B", "C"]
    assert f._fill_only_guide is True
    assert f._guided_refinement_active is True and f._fill_guided == ["B", "C"]


def test_a_refinement_that_also_fills_stays_a_refinement():
    f, plan = _guide(True, lambda listed: sorted(set(listed) | {"B"}))
    assert plan(["D"]) == ["B", "D"]
    assert f._fill_only_guide is False and f._guided_refinement_active is True


def test_nothing_to_fill_changes_nothing():
    f, plan = _guide(False, lambda listed: listed)
    assert plan([]) == []
    assert f._fill_only_guide is False and f._guided_refinement_active is False
    f, plan = _guide(False, lambda listed: ["B"])
    assert plan([], resuming=False) == []
    assert plan([], patch_by_patch=True) == []
    assert f._fill_only_guide is False and f._guided_refinement_active is False


def test_start_plans_the_guide_through_the_tested_method():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    assert ("strips = self._plan_fill_guide(strips, resume_cb.isChecked(),"
            in src)
    assert "self._fill_only_guide = False" in src     # reset at every START


# ================================================== N-3: the engine's defences

def test_a_hand_edited_partial_pair_never_pairs_a_patch_with_one_condition(
        tmp_path, monkeypatch):
    """N-3 (cq_cond_resume: "a patch has all of them, or none"): a partial
    pair whose M1 and M2 hold different patches (edited by hand, or
    damaged). A patch with only one of them is M0 only after a Continue: it
    is in neither file and listed to be completed, never paired with half.

    What this cannot show, and why it is written down rather than forced:
    the normalisation sits in front of a second guard, the writer's own
    "only rows that have all conditions" (cq_cond_write_one), so removing it
    changes no file the engine writes; the reviewer's planted C6 stays green
    for that reason. The two other paths of N-3, cq_restore_row's clear when
    calloc failed (C3b) and cq_cond_write_one's row count check (C8), cannot
    be reached from outside the helper at all. Testing either would need a
    change to the C helper, which this round does not make."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "helpers"))
    from replay_tools import HELPER, ReplaySession
    if not HELPER.exists():
        pytest.skip("chromiq-chartread helper not built")
    import test_conditions_kept_4349 as K
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro3")
    base, rp = K._i1pro3_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    main = base.with_suffix(".ti3")
    with ReplaySession(base, rp, extra_args=K._a3(cdir)) as s:
        for _ in range(4):
            K._read(s)
        K._done(s)
    with ReplaySession(base, rp, extra_args=K._a3(cdir, resume=True)) as s:
        K._read(s, goto="B", m0=True)
        K._done(s)
    m2 = ic.partial_sibling_path(main, "M2")
    assert K._strips(K._locs(m2)) == ["A", "C", "D"]
    # the hand edit: D's rows leave the M2 file only
    text = m2.read_text(encoding="latin-1")
    lines = text.split("\n")
    fields = text.split("BEGIN_DATA_FORMAT")[1].split("END_DATA_FORMAT")[0]
    li = fields.split().index("SAMPLE_LOC")
    d_rows = [ln for ln in lines if len(ln.split()) == len(fields.split())
              and ln.split()[li].strip('"').startswith("D")]
    assert d_rows
    lines = [ln for ln in lines if ln not in d_rows]
    kept = len(K._locs(m2)) - len(d_rows)
    text = "\n".join(lines)
    import re
    text = re.sub(r"NUMBER_OF_SETS\s+\d+", f"NUMBER_OF_SETS {kept}", text)
    m2.write_text(text, encoding="latin-1")
    assert K._strips(ic.m0_only_locs(main)) == ["B", "D"]
    with ReplaySession(base, rp, extra_args=K._a3(cdir, resume=True)) as s:
        K._read(s, goto="C")
        K._done(s)
    for cond in ("M1", "M2"):
        p = ic.partial_sibling_path(main, cond)
        assert K._strips(K._locs(p)) == ["A", "C"], cond
    assert K._strips(ic.m0_only_locs(main)) == ["B", "D"]


# ================================================== SHOULD-4: the instrument

def _dec(family=None):
    from workflow.dual_scan import instrument_model as IM
    return IM.Decision(IM.ASK, "", family)


def test_the_dual_note_promises_nothing_when_another_instrument_is_expected(
        tmp_path, qapp):
    """The dual plan expects another instrument (USB or remembered): a dual
    measurement is then not continued at all (mixed_scan_kind), so the note
    says so instead of promising both passes."""
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    from workflow.dual_scan import session as D
    main = _ti3(_run(tmp_path), ["A1", "B1", "C1"])
    _partial_pair(main, ["A1"])
    names = tr_("strips {names}").format(names="B, C")
    other = D.Plan(False, why_not="other_instrument")
    for resume in (True, False):
        f = _fake(main, resume, _on(), plan=other)
        assert TabMeasure._fill_note_text(f) == M.M_DUAL_FILL_NOT_NOW.render(
            strips=names,
            resume=tr_("Refine / resume existing measurement (-r)"),
            where=D.where_label())
    # an i1Pro 2 expected, or not known (the question comes at START): the
    # plain note, as before
    for plan in (D.Plan(True), D.Plan(False, refusal="filter_not_dual")):
        f = _fake(main, True, _on(), plan=plan)
        assert TabMeasure._fill_note_text(f) == M.M_DUAL_CONTINUE_FILL.render(
            strips=names)


@pytest.mark.parametrize("family,remembered,expect", [
    ("i1pro3", {}, "plain"),
    ("i1pro_family", {}, "not_now"),
    ("other", {}, "not_now"),
    (None, {"dual_scan_instrument": "other",
            "dual_scan_instrument_name": "X-Rite i1Pro 3",
            "dual_scan_instrument_source": "reported"}, "plain"),
    (None, {"dual_scan_instrument": "other",
            "dual_scan_instrument_name": "X-Rite ColorMunki",
            "dual_scan_instrument_source": "reported"}, "not_now"),
    (None, {"dual_scan_instrument": "i1pro2",
            "dual_scan_instrument_source": "chosen"}, "not_now"),
    (None, {}, "plain"),
])
def test_the_i1pro3_note_follows_the_instrument_known_before_the_read(
        tmp_path, qapp, family, remembered, expect):
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M
    main = _ti3(_run(tmp_path), ["A1", "B1", "C1"], dual=False)
    _partial_pair(main, ["A1", "C1"])
    names = tr_("strip {names}").format(names="B")
    settings = _S({ic.SETTING: True, **remembered})
    f = _fake(main, True, settings, decision=_dec(family))
    got = TabMeasure._fill_note_text(f)
    if expect == "not_now":
        assert got == M.M_COND_FILL_NOT_NOW.render(
            strips=names, own="M0", first="M1", second="M2",
            resume=tr_("Refine / resume existing measurement (-r)"),
            start=tr_("Continue Measurement"))
    else:
        assert got == M.M_COND_CONTINUE_FILL.render(
            strips=names, own="M0", first="M1", second="M2")
        # and never an unconditional promise: it names what it needs
        assert "i1Pro 3" in M.M_COND_CONTINUE_FILL.body
        assert "i1Pro 3" in M.M_COND_FILL_OFFER.body
