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
