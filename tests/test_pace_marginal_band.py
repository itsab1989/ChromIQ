"""#149 (Knut): "close to the limit" was being said far too often.

    *"The message close to limit comes also when I am not at all close to the
    limit. The typical message is 'Close to the limit - 521 ms per patch -
    roughly 26 readings (aim for 400 ms or more)'. 521 is more than 30% above
    400. This is too far away from the limit to say that it is close."*

He was reading a real constant: the band was a fixed ``target * 1.35``. For his
ColorMunki (50 Hz x 20 samples = a 400 ms limit) that put the amber band at
400-540 ms, so 521 ms landed inside it. It is now the user's own percentage,
default 10%, which puts the band at 400-440 ms and reports his 521 ms as the
good speed it was.

He also asked for the whole-strip figure, because milliseconds per patch are
not something a person can feel:

    *"the actual limit relatable is the limit for a full strip, which is the
    'per patch limit' multiplied by 'the number of patches per strip'."*

and, reviewing the proposed wording, for that clause to stay short — *"there is
no need mentioning how many patches a strip has, as it is visible in the
preview"* — with one decimal and "sec." rather than "seconds".
"""
from __future__ import annotations

import pytest

from core.measure_pace import (PaceConfig, PaceTracker, StripPace,
                               measured_phrase, strip_limit_fact,
                               strip_limit_phrase, strip_pace_message)

# Knut's instrument: 50 samples per second, 20 needed per patch -> 400 ms.
CM = PaceConfig(min_samples=20, sample_hz=50.0)
PATCHES = 15


def _strip(ms_per_patch: float, cfg: PaceConfig = CM, patches: int = PATCHES):
    return PaceTracker(cfg).strip_timed(
        seconds=ms_per_patch / 1000 * patches, patches=patches)


# --- the band ---------------------------------------------------------------

def test_the_reported_case_is_no_longer_called_close():
    """521 ms against a 400 ms limit — the exact number from the report."""
    assert _strip(521).marginal is False


def test_a_strip_inside_the_band_is_still_called_close():
    """The feature must not be neutered — 420 ms is genuinely close to 400."""
    p = _strip(420)
    assert p.too_fast is False and p.marginal is True


def test_the_edges_of_the_band():
    """400-440 ms at the 10% default: the limit itself is in, 440 is out."""
    assert _strip(400).too_fast is False
    assert _strip(400).marginal is True
    assert _strip(439).marginal is True
    assert _strip(441).marginal is False


def test_a_strip_under_the_limit_is_too_fast_not_merely_close():
    p = _strip(399)
    assert p.too_fast is True and p.marginal is False


def test_the_band_follows_the_setting():
    wide = PaceConfig(min_samples=20, sample_hz=50.0, marginal_percent=35.0)
    assert _strip(521, wide).marginal is True, "35% is the old behaviour"
    narrow = PaceConfig(min_samples=20, sample_hz=50.0, marginal_percent=5.0)
    assert _strip(430, narrow).marginal is False


def test_zero_percent_means_only_warn_about_genuinely_too_fast():
    off = PaceConfig(min_samples=20, sample_hz=50.0, marginal_percent=0.0)
    assert _strip(401, off).marginal is False
    assert _strip(399, off).too_fast is True


def test_a_negative_percentage_cannot_invert_the_band():
    """Defensive: a stored nonsense value must not make marginal_seconds fall
    below the limit, which would mark a passing strip as close and too fast at
    once."""
    odd = PaceConfig(min_samples=20, sample_hz=50.0, marginal_percent=-50.0)
    assert odd.marginal_seconds >= odd.target_seconds


# --- the whole-strip figure -------------------------------------------------

def test_the_strip_limit_is_the_patch_limit_times_the_patches():
    assert CM.strip_target_seconds(15) == pytest.approx(6.0)
    assert CM.strip_target_seconds(11) == pytest.approx(4.4), \
        "Knut's own worked example: 11 patches x 400 ms = 4.4 sec."


def test_an_unknown_strip_length_claims_no_strip_figure():
    assert CM.strip_target_seconds(0) is None
    assert CM.strip_target_seconds(None) is None


def test_the_limit_phrase_is_short_and_one_decimal():
    """His review: keep it terse, one decimal, "sec." not "seconds", and do not
    repeat the patch count that the preview already shows."""
    got = strip_limit_phrase(CM, 15)
    assert got == "400 ms or more per patch — 6.0 sec. or more per strip"
    assert "15-patch" not in got and "seconds" not in got


def test_the_limit_phrase_drops_the_strip_half_when_the_length_is_unknown():
    assert strip_limit_phrase(CM, 0) == "400 ms or more per patch"


def test_a_good_strip_states_the_limit_rather_than_instructing():
    """"Aim for 400 ms" reads oddly at someone already doing better."""
    got = strip_limit_fact(CM, 15)
    assert got == "The limit is 400 ms per patch — 6.0 sec. per strip"
    assert "Aim" not in got


# --- what the reader is told ------------------------------------------------

def test_the_measured_phrase_names_the_readings_when_the_rate_is_known():
    p = StripPace(patches=15, mean_seconds=0.415, est_samples=20)
    assert measured_phrase(p) == "415 ms per patch, roughly 20 readings each"


def test_the_measured_phrase_claims_no_readings_without_a_rate():
    """ChromIQ never invents a sampling rate, so it never implies a count."""
    p = StripPace(patches=15, mean_seconds=0.415, est_samples=None)
    assert measured_phrase(p) == "415 ms per patch"
    assert "readings" not in measured_phrase(p)


def test_the_summary_carries_the_strip_limit_too():
    msg = strip_pace_message(_strip(310), CM)
    assert "6.0 sec. or more per strip" in msg
    assert "That strip was read quickly" in msg


def test_a_good_strip_produces_no_summary_sentence():
    """The summary appears only for a strip worth mentioning."""
    assert strip_pace_message(_strip(800), CM) == ""


def test_no_message_uses_a_bracketed_plural():
    """House rule — counts get real words, never "(s)"."""
    for ms in (310, 420, 800):
        assert "(s)" not in strip_pace_message(_strip(ms), CM)
