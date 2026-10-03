"""The speed hint never says "165 ms ... aim for 165 ms" (review K_review_beta1).

Both numbers used to be rounded to the nearest millisecond, so a strip 0.4 ms
under a limit of 165.3 ms read "Too fast · 165 ms per patch ... Aim for 165 ms
or more". Now a too-fast strip is shown rounded down and the limit to aim for
rounded up, so the shown number is always strictly below the shown limit; a
good strip is shown rounded up against the limit rounded down."""
from __future__ import annotations

import re

import pytest

from core.measure_pace import (PaceConfig, StripPace, measured_phrase,
                               strip_limit_fact, strip_limit_phrase)


def _first_int(text: str) -> int:
    return int(re.search(r"(\d+) ms", text).group(1))


def _configs():
    for hz in (100.0, 133.0, 200.0, 333.0, 400.0):
        for n in (7, 20, 24, 33, 55, 66):
            yield PaceConfig(min_samples=n, sample_hz=hz)


@pytest.mark.parametrize("delta_ms", [-0.01, -0.4, -0.6, -1.0, -3.3])
def test_a_too_fast_strip_shows_a_number_below_the_limit(delta_ms):
    for cfg in _configs():
        mean = cfg.target_seconds + delta_ms / 1000.0
        pace = StripPace(patches=21, mean_seconds=mean, too_fast=True)
        shown = _first_int(measured_phrase(pace))
        aim = _first_int(strip_limit_phrase(cfg, 21))
        assert shown < aim, (cfg, mean, shown, aim)


@pytest.mark.parametrize("delta_ms", [0.0, 0.01, 0.4, 0.6, 2.0])
def test_a_good_strip_never_shows_a_number_below_the_limit(delta_ms):
    for cfg in _configs():
        mean = cfg.target_seconds + delta_ms / 1000.0
        pace = StripPace(patches=21, mean_seconds=mean)
        shown = _first_int(measured_phrase(pace))
        limit = _first_int(strip_limit_fact(cfg, 21))
        assert shown >= limit, (cfg, mean, shown, limit)


def test_an_exact_limit_is_not_moved_by_float_noise():
    cfg = PaceConfig(min_samples=24, sample_hz=200.0)       # exactly 120 ms
    assert _first_int(strip_limit_phrase(cfg, 21)) == 120
    assert _first_int(strip_limit_fact(cfg, 21)) == 120
