"""The misread tests' parameters, per chart type (#182, beta 17).

Knut's rulings on #182, built here:

* **The chart types** (6078174421, 6082015002: "Names for the tests,
  limits, chart types are all good"): *Profiling charts with estimated
  colours*, *Profiling charts made with a pre-conditioning profile*,
  *Verification charts* (printed through the profile, or filled From Profile
  Gamut) and *Calibration charts*.
* **Every parameter is visible and configurable**, per chart type
  (6082015002: "All the parameters in the shown table should be
  configurable, for all chart types and 2 test types"), in one table in
  Preferences ▸ Measurement (6084176226: "The mockup table version looks
  good").
* **The defaults** (6083412660 point 3, approved in 6084176226 and, for the
  radius, 6085694445: "I revert back to previous solution with the
  colour-neighbour radius parameter, and setting that threshold to 30 for
  calibration charts"):

  ======================  =========  ================  ============  ===========
  parameter               estimated  pre-conditioning  verification  calibration
  ======================  =========  ================  ============  ===========
  Patch error limit       95         20                5             95
  Strip test              on         on                off           on
  Neighbour limit         10         5                 3             10
  Colour-neighbour radius 15         30                30            30
  Same-reading tolerance  3, one value for every chart type
  ======================  =========  ================  ============  ===========

  The verification patch error limit of 5 is Knut's approval in 6070058549
  ("Lower ... from 10 to 5?" "Yes, I agree"); the strip test's own box for
  verification charts, off by default, is 6084176226. All values are ΔE*ab
  (CIE76, L*a*b* D50), the colour difference the patch cards show.

Which chart type a measurement is, is decided by the chart, never chosen
(:func:`chart_kind`): a calibration chart lives in the project's ``cal``
folder; a verification is judged against its profile's prediction
(``workflow/verify_expected.py``); a chart whose file carries
``ACCURATE_EXPECTED_VALUES`` was made with a pre-conditioning profile; every
other chart has estimated colours. A verification sheet that falls back to
the chart's own estimate (10.8 point 2 of the specification: a profile built
under another light, or made after the sheet was printed) is judged as the
profiling chart its file describes, as before.

Pure logic: no Qt.
"""
from __future__ import annotations

#: The four chart types, in the order of the Preferences table's columns.
ESTIMATED = "estimated"
ACCURATE = "accurate"
VERIFICATION = "verification"
CALIBRATION = "calibration"
KINDS = (ESTIMATED, ACCURATE, VERIFICATION, CALIBRATION)

#: The columns' names (Knut 6078174421 and 6082015002), wrapped in tr() by
#: the callers.
KIND_NAMES = {
    ESTIMATED: "Profiling charts with estimated colours",
    ACCURATE: "Profiling charts made with a pre-conditioning profile",
    VERIFICATION: "Verification charts",
    CALIBRATION: "Calibration charts",
}

# --- Patch error limit ------------------------------------------------------
#: The keys of the estimated, pre-conditioning and verification limits are the
#: ones beta 11 introduced, so a user's value is read where it always was;
#: the verification one ("prediction") is only judged against the profile's
#: prediction. The calibration limit is new in beta 17: until then a
#: calibration chart took the estimated-chart limit.
PATCH_ERROR_LIMIT_KEYS = {
    ESTIMATED: "patch_read_warn_de_estimated",
    ACCURATE: "patch_read_warn_de_accurate",
    VERIFICATION: "patch_read_warn_de_prediction",
    CALIBRATION: "patch_read_warn_de_calibration",
}
PATCH_ERROR_LIMIT_DEFAULTS = {ESTIMATED: 95.0, ACCURATE: 20.0,
                              VERIFICATION: 5.0, CALIBRATION: 95.0}
PATCH_ERROR_LIMIT_RANGE = (1.0, 200.0)

# --- Strip test -------------------------------------------------------------
#: One switch per chart type (beta 17). Replaces the one
#: "patch_warn_outlier_fence", which ruled every chart but a verification
#: judged against its profile (there it was always off, Knut 5964384250).
STRIP_TEST_KEYS = {k: f"patch_strip_test_{k}" for k in KINDS}
STRIP_TEST_DEFAULTS = {ESTIMATED: True, ACCURATE: True, VERIFICATION: False,
                       CALIBRATION: True}
OLD_STRIP_TEST_KEY = "patch_warn_outlier_fence"

# --- Neighbour check --------------------------------------------------------
#: The neighbour check's own switch (k44, Knut 6060201176), one for every
#: chart type: the table shows it left of the test's name.
NEIGHBOUR_CHECK_KEY = "patch_neighbour_check"
NEIGHBOUR_LIMIT_KEYS = {k: f"patch_neighbour_limit_{k}" for k in KINDS}
NEIGHBOUR_LIMIT_DEFAULTS = {ESTIMATED: 10.0, ACCURATE: 5.0,
                            VERIFICATION: 3.0, CALIBRATION: 10.0}
NEIGHBOUR_LIMIT_RANGE = (0.5, 50.0)
#: The keys beta 11 to 16 kept the neighbour check's threshold under (then
#: called a "buffer"); the beta-17 migration carries a changed value over.
OLD_NEIGHBOUR_KEYS = {ESTIMATED: "patch_neighbour_buffer_de",
                      ACCURATE: "patch_neighbour_buffer_de_accurate"}
OLD_NEIGHBOUR_DEFAULTS = {ESTIMATED: 10.0, ACCURATE: 5.0}
NEIGHBOUR_RADIUS_KEYS = {k: f"patch_neighbour_radius_{k}" for k in KINDS}
NEIGHBOUR_RADIUS_DEFAULTS = {ESTIMATED: 15.0, ACCURATE: 30.0,
                             VERIFICATION: 30.0, CALIBRATION: 30.0}
NEIGHBOUR_RADIUS_RANGE = (1.0, 100.0)

# --- Same-reading tolerance -------------------------------------------------
#: Two readings of one patch this close (ΔE*ab between the two MEASURED
#: colours) are the same colour: a re-read that agrees turns red yellow, one
#: that does not can turn it green. One value for every chart type (Knut
#: 6082015002: "common for all and configurable").
SAME_READING_KEY = "patch_same_reading_de"
SAME_READING_DEFAULT = 3.0
SAME_READING_RANGE = (0.5, 20.0)


def default_settings() -> dict:
    """Every key of this module with its default, for ``core.settings``."""
    out: dict = {}
    for k in KINDS:
        out[PATCH_ERROR_LIMIT_KEYS[k]] = PATCH_ERROR_LIMIT_DEFAULTS[k]
        out[STRIP_TEST_KEYS[k]] = STRIP_TEST_DEFAULTS[k]
        out[NEIGHBOUR_LIMIT_KEYS[k]] = NEIGHBOUR_LIMIT_DEFAULTS[k]
        out[NEIGHBOUR_RADIUS_KEYS[k]] = NEIGHBOUR_RADIUS_DEFAULTS[k]
    out[NEIGHBOUR_CHECK_KEY] = True
    out[SAME_READING_KEY] = SAME_READING_DEFAULT
    return out


def _kind(kind: str) -> str:
    return kind if kind in KINDS else ESTIMATED


def _number(settings, key: str, default: float, rng) -> float:
    try:
        v = float(settings.get(key, default))
    except (TypeError, ValueError, AttributeError):
        return default
    if v != v:                                   # NaN
        return default
    return min(rng[1], max(rng[0], v))


def _flag(settings, key: str, default: bool) -> bool:
    try:
        v = settings.get(key, default)
    except Exception:      # noqa: BLE001 — a setting is never worth a crash
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def patch_error_limit(settings, kind: str) -> float:
    """The Patch error limit for *kind* (ΔE*ab)."""
    k = _kind(kind)
    return _number(settings, PATCH_ERROR_LIMIT_KEYS[k],
                   PATCH_ERROR_LIMIT_DEFAULTS[k], PATCH_ERROR_LIMIT_RANGE)


def strip_test_on(settings, kind: str) -> bool:
    """Is the Strip test on for *kind*?"""
    k = _kind(kind)
    return _flag(settings, STRIP_TEST_KEYS[k], STRIP_TEST_DEFAULTS[k])


def neighbour_check_on(settings) -> bool:
    """Is the Neighbour check switched on? (one switch, every chart type)"""
    return _flag(settings, NEIGHBOUR_CHECK_KEY, True)


def neighbour_limit(settings, kind: str) -> float:
    """The Neighbour limit for *kind* (ΔE*ab)."""
    k = _kind(kind)
    return _number(settings, NEIGHBOUR_LIMIT_KEYS[k],
                   NEIGHBOUR_LIMIT_DEFAULTS[k], NEIGHBOUR_LIMIT_RANGE)


def neighbour_radius(settings, kind: str) -> float:
    """The Colour-neighbour radius for *kind* (ΔE*ab)."""
    k = _kind(kind)
    return _number(settings, NEIGHBOUR_RADIUS_KEYS[k],
                   NEIGHBOUR_RADIUS_DEFAULTS[k], NEIGHBOUR_RADIUS_RANGE)


def same_reading_tolerance(settings) -> float:
    """The Same-reading tolerance (ΔE*ab), common to every chart type."""
    return _number(settings, SAME_READING_KEY, SAME_READING_DEFAULT,
                   SAME_READING_RANGE)


def chart_kind(*, calibration: bool, predicted: bool, accurate: bool) -> str:
    """Which chart type the measurement on screen is: a calibration chart
    first, then a verification judged against its profile's prediction,
    then a chart made with a pre-conditioning profile, else one with
    estimated colours."""
    if calibration:
        return CALIBRATION
    if predicted:
        return VERIFICATION
    if accurate:
        return ACCURATE
    return ESTIMATED


# --- Comparing with a threshold: at one decimal (Knut, #182 6094941512) ------
#
# Knut, on beta 17: patch B3 turned red at ΔE 3.0 with the neighbour limit at
# 3.0. "This is ON the error threshold of 3.0, which should not be red,
# because errors shall happen if ABOVE the threshold ... the values being
# compared with the threshold is rounded to the closest value with one
# decimal (0.1 steps). This principle should apply for all measurement
# thresholds and tests (as defined in preferences -> measurement tab)".
#
# So every test of Preferences ▸ Measurement compares the value AS THE
# CARDS SHOW IT, with one decimal, against the threshold with one decimal:
#
# * a value is flagged only when it is ABOVE the threshold (:func:`above`):
#   the Patch error limit, the Neighbour limit, the Strip test's fence;
# * a value counts as inside when it is not above it (:func:`within`): the
#   Colour-neighbour radius ("within the radius") and the Same-reading
#   tolerance ("the same reading"), so 3.0 at a tolerance of 3.0 is the
#   same reading and 3.1 is not.
#
# THE ROUNDING IS THE CARDS' OWN: Python's ``f"{v:.1f}"``, which every card
# line that names a limit uses. It rounds the exact value of the float to the
# nearest tenth (an exact half, such as 0.25 which a float holds exactly,
# goes to the even tenth: 0.2), so the figure a card prints is, character for
# character, the figure that was compared.


def one_decimal(value) -> float:
    """*value* rounded to one decimal exactly as the patch cards print it
    (``f"{value:.1f}"``)."""
    return float(f"{float(value):.1f}")


def above(value, threshold) -> bool:
    """Is *value* above *threshold*, both taken at one decimal? ON the
    threshold is not above it: 3.0 at 3.0 is not, 3.1 is."""
    return one_decimal(value) > one_decimal(threshold)


def within(value, threshold) -> bool:
    """Is *value* inside *threshold* (not above it), both at one decimal?
    For a radius and a tolerance: 3.0 at 3.0 is inside, 3.1 is not."""
    return not above(value, threshold)


def within_array(values, threshold):
    """:func:`within` for a numpy array, elementwise and with the same
    rounding: values more than 0.1 away from the threshold are decided at
    once, the few near it by :func:`within` itself."""
    import numpy as np
    t = one_decimal(threshold)
    v = np.asarray(values, dtype=float)
    out = v < t - 0.1
    near = ~out & (v < t + 0.1)
    for idx in zip(*np.nonzero(near)):
        out[idx] = within(float(v[idx]), t)
    return out
