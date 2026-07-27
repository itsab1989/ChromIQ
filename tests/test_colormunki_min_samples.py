"""#131 (Knut, 2026-07-27): the ColorMunki's minimum readings per patch is 23.

X-Rite's own figures imply about 34 readings per patch, and ChromIQ shipped 30.
Knut's practical tests read an 11-patch strip well in 5-6 seconds — 250 readings
for the strip, 23 for each patch — and the profiles built from those reads were
good. So 30 was holding users to a pace the instrument does not need.

The number is not just a default: it decides the "too fast" verdict, the advice
that follows a failed strip, and the closing line of the ColorMunki explanation.
All of those are asserted here against the one source of truth.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402

from core.measure_pace import (MODEL_DEFAULTS, _target_ms,   # noqa: E402
                               defaults_for, explanation_for)
from core.settings import SETTINGS_SCHEMA, AppSettings        # noqa: E402


def test_the_default_is_23():
    assert defaults_for("colormunki") == (50.0, 23)


def test_one_patch_must_last_460_ms():
    """23 readings at 50 per second. Knut's own arithmetic: 6.9 s ÷ 15."""
    assert _target_ms("colormunki") == 460


def test_the_explanation_carries_knuts_reasoning():
    _title, body = explanation_for("colormunki")
    for phrase in ("250 ÷ 11 = 23", "345", "approx. 7 seconds",
                   "very strict and limiting"):
        assert phrase in body, f"missing: {phrase}"


def test_the_explanation_states_the_rule_and_not_only_the_round_numbers():
    """Knut: the 5-and-7-second figures are approximations "for ease of
    understanding"; the limit itself is the calculation."""
    _title, body = explanation_for("colormunki")
    assert "15 × 23 = 345" in body and "345 ÷ 50 = 6.9 seconds" in body
    assert "approximations" in body
    assert "time each patch needs stays the same" in body


def test_the_closing_line_is_computed_not_written():
    """A changed default must never leave a stale sentence behind."""
    _title, body = explanation_for("colormunki")
    assert "at least 460 ms" in body
    assert "23 readings at 50 readings per second" in body


def test_no_other_instrument_moved():
    assert MODEL_DEFAULTS["i1pro"] == (100.0, 20)
    assert MODEL_DEFAULTS["i1pro2"] == (200.0, 20)
    assert MODEL_DEFAULTS["i1pro3"] == (400.0, 30)
    assert MODEL_DEFAULTS["i1pro3plus"] == (400.0, 60)
    assert MODEL_DEFAULTS["spectroscan"] == (250.0, None)


# ---- the migration ---------------------------------------------------------
def _settings(tmp_path, stored=None):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    if stored is not None:
        s._qs.setValue("pace_min_samples_colormunki", stored)
    return s


def test_a_stored_echo_of_the_old_default_is_dropped(tmp_path):
    """Preferences → Save writes every key, so anyone who ever opened that
    dialog carries a 30 that is only an echo of the old default."""
    s = _settings(tmp_path, 30)

    s.migrate()

    assert s._qs.value("pace_min_samples_colormunki", None) is None
    assert defaults_for("colormunki")[1] == 23


def test_a_value_the_user_chose_is_left_alone(tmp_path):
    """Someone who deliberately reads slowly keeps their own number."""
    s = _settings(tmp_path, 42)
    s.migrate()
    assert int(s._qs.value("pace_min_samples_colormunki")) == 42


def test_a_user_value_that_happens_to_be_low_is_also_kept(tmp_path):
    s = _settings(tmp_path, 15)
    s.migrate()
    assert int(s._qs.value("pace_min_samples_colormunki")) == 15


def test_a_fresh_install_needs_nothing(tmp_path):
    s = _settings(tmp_path)
    s.migrate()
    assert s._qs.value("pace_min_samples_colormunki", None) is None


def test_the_migration_runs_once(tmp_path):
    """A user who re-sets 30 AFTER the migration means it: schema is already
    current, so it must not be taken away a second time."""
    s = _settings(tmp_path, 30)
    s.migrate()
    s._qs.setValue("pace_min_samples_colormunki", 30)

    s.migrate()

    assert int(s._qs.value("pace_min_samples_colormunki")) == 30


def test_the_schema_was_bumped():
    assert SETTINGS_SCHEMA >= 14, "a changed default needs its own schema step"


# ---- what the user is told when a strip is too fast -------------------------
@pytest.mark.parametrize("seconds,patches,too_fast", [
    (6.9, 15, False),      # 15 × 23 = 345 readings ÷ 50 — exactly the minimum
    (7.0, 15, False),      # comfortably over it
    (6.89, 15, True),      # a hair under: strictly, that is too fast
    (5.06, 11, False),     # 11 × 23 ÷ 50 — the same rule, a shorter strip
    (5.0, 11, True),       # 455 ms per patch — under 460, so it is remarked on
    (3.0, 15, True),       # 200 ms per patch — genuinely rushed
])
def test_the_limit_is_applied_strictly_by_calculation(seconds, patches,
                                                      too_fast):
    """Knut, 2026-07-27: "The limits shall always be used strictly according to
    the calculations, as before." The round 5-and-7-second figures in the help
    text are approximations for reading, not the rule."""
    from core.measure_pace import PaceConfig, PaceTracker
    cfg = PaceConfig(sample_hz=50.0, min_samples=23)
    tracker = PaceTracker(cfg)

    verdict = tracker.strip_timed(seconds, patches)

    assert verdict.too_fast is too_fast, verdict


def test_the_time_per_patch_does_not_depend_on_strip_length():
    """His correction of my question: the per-patch requirement stays at 460 ms;
    it is the strip TOTAL that grows with the number of patches."""
    from core.measure_pace import PaceConfig, PaceTracker
    cfg = PaceConfig(sample_hz=50.0, min_samples=23)
    tracker = PaceTracker(cfg)

    for patches in (8, 11, 15, 21, 30):
        exact = patches * 23 / 50.0            # the strip's own minimum
        assert not tracker.strip_timed(exact, patches).too_fast
        assert tracker.strip_timed(exact * 0.98, patches).too_fast
        # …and that minimum is simply 460 ms times the patch count.
        assert round(exact / patches, 6) == 0.46


def test_the_verdict_agrees_with_the_number_it_reports():
    """ChromIQ used to say "23 readings per patch" and call the same strip too
    fast in the next breath — 455 ms against a 460 ms target, while 23 reads as
    the minimum met. The limit stays strict (Knut); the reported estimate is
    rounded DOWN instead, because a patch with time for 22.7 readings got 22
    complete ones. Now the two never disagree."""
    from core.measure_pace import PaceConfig, PaceTracker
    tracker = PaceTracker(PaceConfig(sample_hz=50.0, min_samples=23))

    for seconds, patches in ((5.0, 11), (5.06, 11), (6.0, 11),
                             (6.89, 15), (6.9, 15), (9.0, 15)):
        v = tracker.strip_timed(seconds, patches)
        assert v.too_fast == (v.est_samples < 23), (seconds, patches, v)


def test_the_reported_estimate_never_flatters_the_reading():
    """22.7 readings is 22 complete ones — reporting 23 would claim the patch
    met a minimum it missed."""
    from core.measure_pace import PaceConfig
    cfg = PaceConfig(sample_hz=50.0, min_samples=23)
    assert cfg.samples_for(0.4545) == 22          # 22.7 → 22, not 23
    assert cfg.samples_for(0.46) == 23
    assert cfg.samples_for(0.9999) == 49


def test_a_genuinely_rushed_strip_is_still_caught():
    from core.measure_pace import PaceConfig, PaceTracker
    tracker = PaceTracker(PaceConfig(sample_hz=50.0, min_samples=23))
    v = tracker.strip_timed(4.0, 15)          # 267 ms per patch → 13 readings
    assert v.too_fast and v.est_samples == 13


def test_an_unknown_rate_still_judges_on_time():
    """No rate means no reading count to compare, so the time-based rule stays
    — it is the only honest one there."""
    from core.measure_pace import PaceConfig, PaceTracker
    tracker = PaceTracker(PaceConfig(sample_hz=0.0, min_patch_seconds=0.5))
    assert tracker.strip_timed(3.0, 15).too_fast          # 200 ms per patch
    assert not tracker.strip_timed(9.0, 15).too_fast      # 600 ms per patch


# ---- spacer width goes with reading speed (Knut, 2026-07-27) --------------
def test_the_explanation_covers_spacer_width():
    """His new section: a spacer can only be found if a reading lands inside
    it, so the width a chart needs follows from the readings-per-patch setting."""
    _title, body = explanation_for("colormunki")
    for phrase in ("SPACER WIDTH GOES WITH READING SPEED",
                   "230 ÷ 345 = 0.7 mm",
                   "0.8 to 0.9 mm",
                   "22 × 15 = 330",
                   "330 ÷ 50 = 6.6 seconds",
                   "262 ÷ 330 ≈ 0.8 mm",
                   "about 1 mm wide"):
        assert phrase in body, f"missing: {phrase}"


def test_the_spacer_arithmetic_is_the_arithmetic_the_app_uses():
    """The worked example must not drift from the model behind it."""
    from core.measure_pace import PaceConfig
    cfg = PaceConfig(sample_hz=50.0, min_samples=15)
    readings_per_strip = 22 * 15
    assert readings_per_strip == 330
    assert round(readings_per_strip / cfg.sample_hz, 1) == 6.6
    assert round(262 / readings_per_strip, 1) == 0.8
    # …and the 15-patch case the prose leads with.
    assert 15 * 23 == 345
    assert round(230 / 345, 1) == 0.7
