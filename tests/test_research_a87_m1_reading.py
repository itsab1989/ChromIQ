"""Research Agent 87: the M1 reading of the weighed tally vs colprof (stats3 --m1-reading).

Two things the one-sided no-regression reading gets wrong when the comparison is colprof vs the engine:
* bpc_lift and black_gap have their ideal at 0 and can go either side; "lower is better" on the signed number
  scored a black printed BELOW the black point, or colprof's rel. col. black lifted ABOVE its own perceptual
  black, as a win. ABS_KEYS are scored as |value|.
* with no seed run in the battery, an unconfirmed WORSE* counted as a loss while an unconfirmed BETTER* was never
  a win. symmetric_single_build reads the two alike.
The default (no flag) is unchanged."""
from benchmarks.research import stats3


def _results(qa, qb):
    def ds(q, engine):
        return {"name": "R-Toy", "variant": "base", "n_channels": 3, "color_rep": "RGB", "role": "real",
                "info": {"chart": None}, "profiles": {engine: {"oogq": {"q": q}}}}
    return {"datasets": [ds(qa, "colprof")]}, {"datasets": [ds(qb, "accurate")]}


def _rows(qa, qb, abs_keys=()):
    ra, rb = _results(qa, qb)
    rows = stats3.property_rows(ra, rb, "colprof", "accurate", abs_keys)
    return stats3.decide_properties(rows, "colprof", "accurate", None)


def test_signed_lift_rewards_a_black_below_the_black_point_and_abs_does_not():
    # colprof's wedge bottom prints 13 L* below its black point, the engine's 1 L* above
    signed = {r["endpoint"]: r for r in _rows({"bpc_lift_r": -13.0}, {"bpc_lift_r": 1.0})}
    assert signed["q.bpc_lift_r"]["verdict"] == "WORSE*"
    fixed = {r["endpoint"]: r for r in _rows({"bpc_lift_r": -13.0}, {"bpc_lift_r": 1.0}, stats3.ABS_KEYS)}
    assert fixed["q.bpc_lift_r"]["verdict"] == "BETTER*"
    assert fixed["q.bpc_lift_r"]["a"] == 13.0


def test_black_gap_is_scored_as_distance_from_zero():
    fixed = {r["endpoint"]: r for r in _rows({"black_gap_p": -3.1}, {"black_gap_p": 0.0}, stats3.ABS_KEYS)}
    assert fixed["q.black_gap_p"]["verdict"] == "BETTER*"
    signed = {r["endpoint"]: r for r in _rows({"black_gap_p": -3.1}, {"black_gap_p": 0.0})}
    assert signed["q.black_gap_p"]["verdict"] == "WORSE*"


def test_symmetric_single_build_counts_an_unconfirmed_better_as_a_win():
    rows = _rows({"bpc_sep_min_r": 0.1, "bpc_wedge_de_r": 0.5}, {"bpc_sep_min_r": 0.9, "bpc_wedge_de_r": 0.5})
    assert {r["endpoint"]: r["verdict"] for r in rows} == {"q.bpc_sep_min_r": "BETTER*", "q.bpc_wedge_de_r": "TIE"}
    one_sided = stats3.weighed_adoption(rows, None, [])
    two_sided = stats3.weighed_adoption(rows, None, [], symmetric_single_build=True)
    assert (one_sided["wins"], one_sided["losses"]) == (0, 0)
    assert (two_sided["wins"], two_sided["losses"]) == (1, 0)


def test_default_reading_is_unchanged():
    rows = _rows({"bpc_lift_r": 0.2, "bpc_sep_min_r": 0.9}, {"bpc_lift_r": 2.0, "bpc_sep_min_r": 0.1})
    w = stats3.weighed_adoption(rows, None, [])
    assert (w["wins"], w["losses"]) == (0, 2)
    assert stats3.weighed_adoption(rows, None, [], symmetric_single_build=True)["losses"] == 2
