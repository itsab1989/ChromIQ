"""Beta 12, Basti #182 6001610646 item 2: "Strip Read Quickly" is not raised
for a strip that missed the limit by a hair.

His strip AD (2026-10-05, ColorMunki/i1Studio, 20 readings at 50 Hz = 400 ms
a patch): 28 patches in 11.2 s, 398 ms a patch, and the Re-read / Continue
window came up. The time is the computer's clock between the ready beep and
the strip's arrival, both delivered through the engine's thread, a pipe and
the event queue, so a 2 % tolerance (8 ms a patch here) absorbs that error.
Inside it the strip is still reported "close to the limit".
"""
from __future__ import annotations

from core.measure_pace import PaceConfig, PaceTracker, strip_pace_message

CM = PaceConfig(min_samples=20, sample_hz=50.0)


def _strip(seconds, patches=28, cfg=CM):
    return PaceTracker(cfg).strip_timed(seconds=seconds, patches=patches)


def test_bastis_strip_ad_is_close_to_the_limit_not_too_fast():
    p = _strip(28 * 0.398)
    assert p.too_fast is False
    assert p.marginal is True
    msg = strip_pace_message(p, CM)
    assert "close to the limit" in msg and "398 ms" in msg


def test_the_tolerance_is_two_percent_of_the_limit():
    assert abs(CM.too_fast_seconds - 0.392) < 1e-12
    assert _strip(28 * 0.392).too_fast is False
    assert _strip(28 * 0.3919).too_fast is True
    # A clearly fast strip is still caught.
    assert _strip(28 * 0.350).too_fast is True


def test_the_tolerance_scales_with_the_instruments_own_limit():
    i1pro2 = PaceConfig(min_samples=23, sample_hz=200.0)   # 115 ms a patch
    assert abs(i1pro2.too_fast_seconds - 0.115 * 0.98) < 1e-12
    assert _strip(15 * 0.114, 15, i1pro2).too_fast is False
    assert _strip(15 * 0.112, 15, i1pro2).too_fast is True


def test_per_patch_judgement_uses_the_same_tolerance():
    t = PaceTracker(CM)
    t.strip_started(0.0)
    t.patch_completed(0.0)
    assert t.patch_completed(0.395).too_fast is False
    assert t.patch_completed(0.395 + 0.380).too_fast is True
