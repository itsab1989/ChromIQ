"""#131 Phase 2: judging how fast the instrument is being swiped, from the
patch events alone. Driven with a synthetic clock so every branch is exact."""
from __future__ import annotations

import pytest

from core.measure_pace import (PaceConfig, PaceTracker, StripPace,
                               strip_pace_message)


def _read(tracker: PaceTracker, start: float, interval: float, n: int):
    """Read *n* patches at a steady *interval*, returning the last timestamp."""
    tracker.strip_started(start)
    t = start
    out = []
    for _ in range(n):
        t += interval
        out.append(tracker.patch_completed(t))
    return t, out


# ---- the sample-count derivation -----------------------------------------
def test_samples_are_derived_from_time_and_rate():
    """Knut's method: seconds per patch × samples per second."""
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)
    assert cfg.samples_for(0.10) == 20
    assert cfg.samples_for(0.02) == 4
    # 8 samples at 200 Hz is 40 ms, so that is the shortest acceptable patch
    assert cfg.target_seconds == pytest.approx(0.04)


def test_no_sample_count_is_claimed_when_the_rate_is_unknown():
    """With no rate configured the pace is judged in time alone — the estimate
    is None rather than a number we cannot stand behind."""
    cfg = PaceConfig(sample_hz=0.0, min_patch_seconds=0.10)
    assert cfg.knows_rate is False
    assert cfg.samples_for(0.5) is None
    assert cfg.target_seconds == pytest.approx(0.10)


# ---- per-patch judgement --------------------------------------------------
def test_first_patch_of_a_strip_has_no_interval():
    t = PaceTracker(PaceConfig(sample_hz=200.0))
    t.strip_started(0.0)
    assert t.patch_completed(0.5) is None        # nothing to compare against


def test_a_fast_patch_is_flagged_and_a_slow_one_is_not():
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)      # target 40 ms
    t = PaceTracker(cfg)
    t.strip_started(0.0)
    t.patch_completed(0.10)
    fast = t.patch_completed(0.12)               # 20 ms
    slow = t.patch_completed(0.32)               # 200 ms
    assert fast.too_fast is True and fast.est_samples == 4
    assert slow.too_fast is False and slow.est_samples == 40


def test_a_pause_is_not_mistaken_for_a_slow_patch():
    """The user stopping mid-strip must not flatter the average."""
    t = PaceTracker(PaceConfig(sample_hz=200.0))
    t.strip_started(0.0)
    t.patch_completed(0.1)
    assert t.patch_completed(30.0) is None       # a 30 s gap is a pause
    summary = t.strip_finished()
    assert summary.mean_seconds == 0.0           # the pause was not counted


# ---- strip judgement ------------------------------------------------------
def test_a_fast_strip_is_reported_as_too_fast():
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)      # target 40 ms
    t = PaceTracker(cfg)
    end, _ = _read(t, 0.0, 0.02, 10)             # 20 ms per patch
    pace = t.strip_finished(end)
    assert pace.too_fast is True and pace.marginal is False
    assert pace.patches == 10 and pace.est_samples == 4   # 10 patches read
    assert pace.elapsed == pytest.approx(0.2, abs=1e-6)


def test_a_comfortable_strip_says_nothing():
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)
    t = PaceTracker(cfg)
    end, _ = _read(t, 0.0, 0.20, 10)             # 200 ms per patch
    pace = t.strip_finished(end)
    assert pace.too_fast is False and pace.marginal is False
    assert strip_pace_message(pace, cfg) == ""


def test_a_marginal_strip_is_flagged_separately():
    """It passed, but only just — the case Argyll never warns about."""
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)      # target 40 ms
    t = PaceTracker(cfg)
    end, _ = _read(t, 0.0, 0.045, 10)            # 45 ms: over, but close
    pace = t.strip_finished(end)
    assert pace.too_fast is False and pace.marginal is True


def test_too_few_patches_to_judge():
    """A two-patch strip says nothing — the first interval is the lead-in."""
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)
    t = PaceTracker(cfg)
    end, _ = _read(t, 0.0, 0.001, 2)
    pace = t.strip_finished(end)
    assert pace.too_fast is False and pace.marginal is False


def test_the_tracker_resets_between_strips():
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)
    t = PaceTracker(cfg)
    end, _ = _read(t, 0.0, 0.02, 8)
    assert t.strip_finished(end).too_fast is True
    end2, _ = _read(t, 100.0, 0.20, 8)
    second = t.strip_finished(end2)
    assert second.too_fast is False, "the previous strip must not carry over"


# ---- wording --------------------------------------------------------------
def test_message_names_the_sample_estimate_only_when_the_rate_is_known():
    fast = StripPace(patches=10, mean_seconds=0.02, est_samples=4, too_fast=True)
    with_rate = strip_pace_message(fast, PaceConfig(min_samples=8, sample_hz=200.0))
    assert "20 ms per patch" in with_rate and "4 samples" in with_rate
    assert "40 ms" in with_rate, "it states the target too"

    blind = StripPace(patches=10, mean_seconds=0.02, est_samples=None, too_fast=True)
    without = strip_pace_message(blind, PaceConfig(sample_hz=0.0,
                                                  min_patch_seconds=0.10))
    assert "20 ms per patch" in without
    assert "sample" not in without, "no sample count may be implied"


def test_marginal_message_is_gentler_than_the_too_fast_one():
    cfg = PaceConfig(min_samples=8, sample_hz=200.0)
    marginal = StripPace(patches=10, mean_seconds=0.045, est_samples=9,
                         marginal=True)
    text = strip_pace_message(marginal, cfg)
    assert "close to the limit" in text
    assert "read twice" in text or "twice" in text


# ---- per-model rates and thresholds (Knut, #131 2026-07-26) ---------------
@pytest.mark.parametrize("argyll_name,expected", [
    ("X-Rite i1 Pro3+", "i1pro3plus"),
    ("X-Rite i1 Pro3", "i1pro3"),
    ("X-Rite i1 Pro2", "i1pro2"),
    ("GretagMacbeth i1 Pro", "i1pro"),
    ("X-Rite ColorMunki", "colormunki"),
    ("X-Rite i1Studio", "colormunki"),
    ("GretagMacbeth SpectroScan", "spectroscan"),
    ("Some Other Device", None),
    ("", None),
])
def test_argyll_names_map_to_models(argyll_name, expected):
    """The "+" and the generations must not collapse into one another."""
    from core.measure_pace import model_key
    assert model_key(argyll_name) == expected


def test_an_unknown_instrument_assumes_the_slowest_i1pro():
    """Knut's rule, precisely: when the model cannot be determined, assume the
    slowest rate of the i1Pro group. Guessing a FASTER instrument than the one
    connected would let a too-quick swipe pass unremarked, which is the failure
    that costs a re-read."""
    from core.measure_pace import MODEL_DEFAULTS, defaults_for
    hz, min_samples = defaults_for(None)
    i1pro_group = [MODEL_DEFAULTS[k][0] for k in ("i1pro", "i1pro2", "i1pro3")]
    assert hz == min(i1pro_group) == 100.0
    assert min_samples is not None, "an unknown instrument still gets a warning"


def test_the_spectroscan_has_no_threshold():
    """A motorised table places the head on each patch — there is no swipe."""
    from core.measure_pace import defaults_for
    _hz, min_samples = defaults_for("spectroscan")
    assert min_samples is None


@pytest.mark.parametrize("key,expected_ms", [
    ("i1pro", 200),        # 100 Hz, 20 samples
    ("i1pro2", 100),       # 200 Hz, 20 samples — Knut derived ~103 ms
    ("i1pro3", 75),        # 400 Hz, 30 samples — Knut derived ~76 ms
    ("i1pro3plus", 150),   # 400 Hz, 60 samples
    ("colormunki", 600),   # 50 Hz, 30 samples
])
def test_each_models_target_matches_the_derivation(key, expected_ms):
    from core.measure_pace import PaceConfig, defaults_for
    hz, min_samples = defaults_for(key)
    cfg = PaceConfig(min_samples=min_samples, sample_hz=hz)
    assert round(cfg.target_seconds * 1000) == expected_ms


def test_the_ranges_are_the_ones_specified():
    from core.measure_pace import MIN_SAMPLES_RANGE, SAMPLE_HZ_RANGE
    assert SAMPLE_HZ_RANGE == (10.0, 500.0)
    assert MIN_SAMPLES_RANGE == (10, 100)


# ---- the ⓘ explanations (Knut, #131 2026-07-26) ---------------------------
@pytest.mark.parametrize("key", ["i1pro", "i1pro2", "i1pro3", "i1pro3plus",
                                 "colormunki", "spectroscan"])
def test_every_instrument_explains_its_own_defaults(key):
    """Each instrument gets a title and a body, and the body carries the
    reasoning rather than restating the number."""
    from core.measure_pace import explanation_for
    title, body = explanation_for(key)
    assert title and len(body) > 200, f"{key} needs a real explanation"


@pytest.mark.parametrize("key,rate", [("i1pro", "100"), ("i1pro2", "200"),
                                      ("i1pro3", "400"), ("i1pro3plus", "400"),
                                      ("colormunki", "50")])
def test_the_explanation_states_the_rate_it_ships_with(key, rate):
    from core.measure_pace import explanation_for
    _title, body = explanation_for(key)
    assert rate in body, f"{key}'s explanation should name its {rate} Hz rate"


@pytest.mark.parametrize("key", ["i1pro", "i1pro2", "i1pro3", "i1pro3plus",
                                 "colormunki"])
def test_the_explanation_ends_with_the_time_the_defaults_imply(key):
    """The closing line is computed from MODEL_DEFAULTS, so changing a default
    changes the text — no stale explanation can survive."""
    from core.measure_pace import MODEL_DEFAULTS, _target_ms, explanation_for
    _title, body = explanation_for(key)
    assert f"{_target_ms(key)} ms" in body
    assert f"{MODEL_DEFAULTS[key][1]} readings" in body


def test_the_spectroscan_explains_why_it_has_no_threshold():
    from core.measure_pace import explanation_for
    _title, body = explanation_for("spectroscan")
    assert "motorised" in body and "Off" in body
    assert "ms" not in body, "there is no target time when the threshold is Off"


def test_an_unknown_instrument_still_explains_the_fallback():
    from core.measure_pace import explanation_for
    _title, body = explanation_for("something-else")
    assert "slowest" in body


# ---- strip-scanning instruments (Knut, #131 2026-07-26) -------------------
def test_a_strip_is_judged_from_its_scan_time_and_patch_count():
    """The path a strip-scanning instrument really takes: the whole strip comes
    back at once, so the mean is all there is — and it is exactly what Knut's
    thresholds were derived from."""
    from core.measure_pace import PaceConfig, PaceTracker
    cfg = PaceConfig(min_samples=30, sample_hz=50.0)     # ColorMunki: 600 ms
    t = PaceTracker(cfg)

    fast = t.strip_timed(seconds=3.0, patches=11)        # 273 ms per patch
    assert fast.too_fast is True and fast.patches == 11
    assert fast.est_samples == 14                        # 0.273 s × 50 Hz

    fine = t.strip_timed(seconds=9.0, patches=11)        # 818 ms per patch
    assert fine.too_fast is False and fine.marginal is False
    assert fine.elapsed == pytest.approx(9.0)


def test_a_strip_read_only_just_fast_enough_is_marginal():
    from core.measure_pace import PaceConfig, PaceTracker
    cfg = PaceConfig(min_samples=20, sample_hz=200.0)    # i1Pro 2: 100 ms
    pace = PaceTracker(cfg).strip_timed(seconds=3.2, patches=29)  # 110 ms
    assert pace.too_fast is False and pace.marginal is True


def test_a_strip_with_no_patches_or_no_time_says_nothing():
    """Defensive: a malformed strip event must not produce a verdict."""
    from core.measure_pace import PaceConfig, PaceTracker, strip_pace_message
    cfg = PaceConfig(min_samples=20, sample_hz=200.0)
    t = PaceTracker(cfg)
    for pace in (t.strip_timed(0.0, 29), t.strip_timed(3.0, 0)):
        assert pace.too_fast is False and pace.marginal is False
        assert strip_pace_message(pace, cfg) == ""


# ---- classifying WHY a strip failed (Knut, #131 2026-07-26) ---------------
# The messages are ArgyllCMS's own, taken from the driver's interp_error table.
# The wording is identical for the ColorMunki, i1Pro, i1Pro 2 and i1Pro 3.
@pytest.mark.parametrize("detail,expected", [
    ("Not enough samples per patch - Slow Down!", "too_fast"),
    ("Reading is too short",                      "too_fast"),
    ("Not enough patches",                        "too_fast"),
    ("Too many patches",                          "too_slow"),
    ("Swipe didn't start and end on the media",   "other"),
    ("Light level is too low",                    "other"),
    ("Reading is inconsistent",                   "other"),
    ("",                                          "other"),
])
def test_argylls_own_wording_decides_the_verdict(detail, expected):
    from core.measure_pace import failure_kind
    assert failure_kind(detail) == expected


def test_too_many_patches_is_never_called_too_fast():
    """The advice would be exactly backwards: extra transitions mean the swipe
    hesitated, not that it hurried."""
    from core.measure_pace import PaceConfig, failure_advice
    advice = failure_advice("Too many patches", PaceConfig(min_samples=20,
                                                           sample_hz=200.0))
    assert "hesitated" in advice or "wavered" in advice
    # It must not carry the slow-down instruction. (Checking for the words
    # "too quick" alone would be wrong — the sentence legitimately says the
    # swipe wavered "rather than being too quick".)
    assert "Aim for at least" not in advice


def test_the_advice_quotes_the_thresholds_currently_set():
    """Knut: nothing in these messages may be static — change a threshold in
    Preferences and what the user is told changes with it."""
    from core.measure_pace import PaceConfig, failure_advice
    lenient = failure_advice("Not enough patches",
                             PaceConfig(min_samples=20, sample_hz=200.0))
    strict = failure_advice("Not enough patches",
                            PaceConfig(min_samples=60, sample_hz=200.0))
    assert "100 ms" in lenient and "20 readings" in lenient
    assert "300 ms" in strict and "60 readings" in strict
    assert lenient != strict


def test_the_advice_makes_no_sample_claim_without_a_rate():
    from core.measure_pace import PaceConfig, failure_advice
    advice = failure_advice("Reading is too short",
                            PaceConfig(sample_hz=0.0, min_patch_seconds=0.2))
    assert "200 ms" in advice
    assert "readings per second" not in advice


# ---- the end-of-measurement summary (Knut, #131 2026-07-26) --------------
def test_the_summary_reports_total_average_fastest_and_slowest():
    from core.measure_pace import session_summary
    times = {"A": (9.0, True), "B": (6.0, True), "C": (12.0, True)}
    text = session_summary(times, total_seconds=3725)      # 1 h 2 m 5 s
    assert "01:02:05" in text
    assert "average 9.0 s" in text
    assert "fastest 6.0 s" in text and "slowest 12.0 s" in text
    assert "over 3 strips" in text


def test_worst_means_fastest_and_is_listed_in_order():
    """The shortest times are the risky ones — that is what "worst" means for
    reading pace."""
    from core.measure_pace import session_summary
    times = {c: (float(i), True) for i, c in enumerate("ABCDEFGHIJKLM", start=1)}
    text = session_summary(times, total_seconds=100)
    listed = text.rsplit(":", 1)[-1]
    assert listed.strip().startswith("A 1.0 s, B 2.0 s, C 3.0 s")
    assert "K 11.0 s" not in listed, "only the ten fastest are listed"
    assert listed.count(",") == 9, "ten entries"


def test_failed_strips_are_left_out_of_the_figures():
    """A failed scan produced nothing; averaging it in would misrepresent the
    strips that were actually read."""
    from core.measure_pace import session_summary
    times = {"A": (9.0, True), "B": (0.5, False), "C": (11.0, True)}
    text = session_summary(times, total_seconds=60)
    assert "average 10.0 s" in text
    assert "fastest 9.0 s" in text
    assert " B " not in text


def test_a_measurement_with_nothing_read_still_reports_its_time():
    from core.measure_pace import session_summary
    text = session_summary({}, total_seconds=95)
    assert "00:01:35" in text
    assert "average" not in text


def test_one_strip_is_described_in_the_singular():
    from core.measure_pace import session_summary
    text = session_summary({"A": (7.0, True)}, total_seconds=7)
    assert "over one strip" in text
    assert "strips" not in text.split("\n")[1]
