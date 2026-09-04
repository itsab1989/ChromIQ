"""B8-01 and B8-03 — the two ways this window said a bad profile was a good one.

Beta 8, 2026-09-04. Both are the same shape as review 5's five findings and are
worse than any of them, because in both the app does not merely stay silent: it
prints a number that says the profile is FINE and then says "Install it as your
scanner's input profile."

**B8-01 — an under-exposed scan.** Every guard the window had is
scale-invariant, and an exposure slip is pure scale. Measured on Knut's own Wolf
Faust sheet, darkened 30 % and read through the same ``scanin -F`` corners so
exposure was the only variable:

===================  ==========  ==========  ==========  ===================
what                 coverage    agreement   clipped     true error, ΔE avg
===================  ==========  ==========  ==========  ===================
his scan             288/288     +0.9839     5.2 %       1.93
the same, ×0.70      288/288     +0.9838     5.2 %       **21.70**
the same, ×0.18      288/288     +0.9838     5.9 %       **177.91** (peak 335.7)
===================  ==========  ==========  ==========  ===================

Not one of the three moves. colprof's own self-check does not move either — 1.93
→ 2.59 across the whole ladder, against limits of 30 and 12 — because it is
computed against the same dark data. So the build is silent from end to end.

**B8-03 — a self-check with no floor and no NaN guard.** Two degenerate
references, both built on Knut's correct scan:

* every ``SAMPLE_ID`` rewritten to ``A1`` → one row → ``peak err = 0.007339,
  avg err = 0.007339``, a better mark than any correct build in this suite, and
  the log ends "Install it as your scanner's input profile";
* every value rewritten to ``0.00`` → 288 rows of one colour → colprof's Powell
  fit reports ``residual error = nan``, the profile's white point is ``nan nan
  nan``, and the fit line reads ``peak err = 0.000000, avg err = nan`` — which
  ``_PROFCHECK_RE`` could not match, so the check never saw it at all.

The thresholds are the contestable part, so the readings they were chosen
against are in this file rather than in a report nobody re-runs — a default
moved without re-measuring fails here.
"""
from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.settings import DEFAULTS                      # noqa: E402
from workflow import measurement_messages as M          # noqa: E402
from workflow.scan_read_check import (                  # noqa: E402
    HIGHLIGHT_REFERENCE_MIN_Y, ReadInspection, fit_support, highlight_level,
    inspect_read,
)


# --------------------------------------------------------------------------
# Every reading measured for B8-01, both directions. The good rows are the
# harder half: a check that cries wolf on a legitimate scan is worse than the
# silence it replaces, because the same user then clicks past the real one.
#
# "level" is the shipped measure — the median of the largest device channel
# over the patches the reference calls near-white. Every row came off
# `scanin`, through the app's own `cht_with_patchbox_fiducials` +
# `cht_with_sample_area(0.6)` rewrites, at the same `-F` corners within a group.
#
#     (what it is,                                   level,  must warn)
MEASURED_LEVELS = [
    # --- Knut's own ten sheets, his scanner, his two targets ---------------
    ("real: Wolf Faust sheet 1",                      79.82,  False),
    ("real: Wolf Faust sheet 2",                      79.43,  False),
    ("real: Wolf Faust sheet 3",                      77.69,  False),
    ("real: Wolf Faust sheet 4",                      79.52,  False),
    ("real: Wolf Faust sheet 5",                      79.46,  False),
    ("real: LaserSoft sheet 1",                       74.81,  False),
    ("real: LaserSoft sheet 2",                       75.39,  False),
    ("real: LaserSoft sheet 3",                       75.03,  False),
    ("real: LaserSoft sheet 4",                       73.29,  False),
    ("real: LaserSoft sheet 5",                       72.92,  False),
    # --- re-read here from his two full-resolution scans ------------------
    ("re-read: Wolf Faust, 2078 px",                  79.77,  False),
    ("re-read: Wolf Faust, 693 px (his own size)",    79.78,  False),
    ("re-read: LaserSoft, 2094 px",                   74.84,  False),
    # --- legitimate variations of those scans -----------------------------
    ("a gamma-1.8 scanner",                           75.85,  False),
    ("a gamma-2.6 scanner",                           76.64,  False),
    ("matte paper, blacks lifted 8 %",                79.77,  False),
    ("a transparency tone scale, anchored at Dmin",   78.60,  False),
    ("a harsh transparency tone scale",               69.57,  False),
    ("a warm cast (1.00, 0.86, 0.62)",                79.05,  False),
    ("a cool cast (0.66, 0.88, 1.00)",                78.90,  False),
    ("a scanner running 12 % hot",                    83.86,  False),
    # --- the app's own demo scan, extremes of all 25 targets ---------------
    ("demo: ColorChecker (the lowest of 25)",         80.96,  False),
    ("demo: Hutchcolor (the highest of 25)",          94.34,  False),
    # --- another agent's good images, re-read here -------------------------
    ("agent B's good scan",                           79.91,  False),
    ("agent B's 16-bit scan",                         79.91,  False),
    ("agent B's JPEG q12 scan",                       79.60,  False),
    ("agent B's 400 px scan",                         79.98,  False),

    # --- deliberate under-exposure ----------------------------------------
    # x0.85 is -0.47 stop and is NOT caught: 67.84 sits 1.7 points under the
    # harshest legitimate case above and no threshold can separate them. That
    # profile is 9.5 dE out, which is not free — but a window that fires on a
    # legitimate scan is worse, because the same user then clicks past x0.70.
    ("x0.85 (-0.47 stop) — deliberately let through", 67.84,  False),
    ("x0.70 (-1.15 stops), Wolf Faust: 21.70 dE",     55.85,  True),
    ("x0.70 (-1.15 stops), LaserSoft: 18.69 dE",      52.43,  True),
    ("agent B's x0.70 file, re-read here",            55.70,  True),
    ("x0.55, Wolf Faust: 40.44 dE",                   43.91,  True),
    ("x0.45, Wolf Faust: 56.96 dE",                   35.87,  True),
    ("x0.45, LaserSoft: 49.53 dE",                    33.71,  True),
    ("agent B's x0.45 file, re-read here",            35.70,  True),
    ("x0.30, Wolf Faust: 97.42 dE",                   23.93,  True),
    ("x0.18, Wolf Faust: 177.91 dE",                  14.47,  True),
]


@pytest.mark.parametrize("label,level,must_warn", MEASURED_LEVELS,
                         ids=[r[0] for r in MEASURED_LEVELS])
def test_the_shipped_floor_matches_every_level_measured(label, level, must_warn):
    got = ReadInspection(rows=288, agreement=0.98, clipped_high=0.0,
                         clipped_low=0.05, highlight=level, support=288)
    fired = got.underexposed(DEFAULTS["scanner_min_highlight"])
    assert fired is must_warn, (
        f"{label}: level {level:.2f} — the shipped floor "
        f"({DEFAULTS['scanner_min_highlight']}) "
        f"{'warns' if fired else 'stays quiet'}, and this read "
        f"{'must be caught' if must_warn else 'is legitimate'}")


def test_the_floor_keeps_a_real_margin_under_the_worst_legitimate_scan():
    """A constant with no measured provenance guards nothing. 69.57 is the
    lowest reading any legitimate scan produced across 64 of them; 72.92 is the
    lowest that came off real hardware (Knut's LaserSoft sheet 5)."""
    worst_legit = min(l for _n, l, warn in MEASURED_LEVELS if not warn)
    assert worst_legit == pytest.approx(67.84)          # the x0.85 row
    worst_real = min(l for n, l, warn in MEASURED_LEVELS
                     if not warn and n.startswith("real:"))
    assert worst_real == pytest.approx(72.92)
    floor = DEFAULTS["scanner_min_highlight"]
    assert floor <= worst_real - 12.0, (
        "the floor must clear the worst reading real hardware produced by a "
        "wide margin, or it will fire on somebody's ordinary scan")
    assert floor >= 50.0, (
        "and it must still catch x0.70 on the LaserSoft target, which reads "
        "52.43 and is 18.7 dE out")


# --------------------------------------------------------------------------
# Why THIS measure and not a cheaper one. Three were built, measured on the
# same 74 reads, and thrown away. Each disproof is its own test, because each
# fails for its own reason and a single rule would flatten that.
#
# The yardstick throughout is HEADROOM: the gap between the worst LEGITIMATE
# reading a measure produced and the reading it must still catch — x0.70, which
# is 21.7 dE out on Wolf Faust and 18.7 dE out on LaserSoft. Negative headroom
# means a floor would have to accuse a legitimate scan before it caught that one.
SHIPPED_WORST_LEGITIMATE = 69.57      # a harsh transparency tone scale
SHIPPED_AT_X070 = 55.85               # Wolf Faust


def _headroom(worst_legit: float, at_x070: float) -> float:
    return (worst_legit - at_x070) / at_x070


def test_the_shipped_measure_has_real_headroom():
    assert _headroom(SHIPPED_WORST_LEGITIMATE, SHIPPED_AT_X070) > 0.20


def test_the_mean_device_level_is_inverted_by_a_transparency():
    """A transparency's tone scale puts far more of the sheet in the shadows,
    so its mean is genuinely low without its exposure being wrong: 25.85, where
    a scan darkened to -1.15 stops reads 27.27. **The legitimate scan is the
    darker of the two**, so no floor on the mean can separate them."""
    assert _headroom(25.85, 27.27) < 0


def test_the_black_patch_level_is_inverted_twice_over():
    """Two ways at once. Under-exposure pushes blacks DOWN, so the measure has
    to alarm when the black is low — and the same transparency reads 1.38 there,
    below the x0.70 scan's 5.04 and level with the x0.18 scan's 1.29, which is
    the worst read in the whole set. Read the other way round, as "the black has
    lifted", it alarms hardest on matte paper (14.52), which is not a fault at
    all."""
    assert _headroom(1.38, 5.04) < 0                  # alarming on low black
    assert 14.52 > 5.04                               # alarming on high black


def test_the_white_patch_luminance_is_moved_by_a_cast_that_is_not_exposure():
    """Luminance survives x0.70 (66.28 against 55.11) and fails where it
    matters: a cool cast of (0.66, 0.88, 1.00) costs 12.4 points of the same
    headroom for a reason that has nothing to do with level, and drops the
    legitimate scan to 66.24 — BELOW a genuinely under-exposed x0.85 at 66.92.
    The largest channel of those same patches reads 78.90 and 67.28: a cast
    moves the other channels, never the one the exposure was set by."""
    def lum(rgb):
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    # measured, median over the near-white patches of each read
    good = [79.05, 78.56, 78.90]
    cool = [52.16, 69.15, 78.90]          # the same sheet, a cool cast
    x085 = [67.28, 66.79, 67.13]          # the same sheet, -0.47 stop
    assert lum(cool) == pytest.approx(66.24, abs=0.05)
    assert lum(x085) == pytest.approx(66.92, abs=0.05)
    assert lum(cool) < lum(x085), (
        "luminance ranks a legitimate cast as darker than a genuinely "
        "under-exposed scan")
    assert max(cool) == pytest.approx(max(good), rel=0.01)
    assert max(x085) < 0.90 * max(good)


# --------------------------------------------------------------------------
def _ti3(rows: "list[tuple[str, tuple[float, float, float], tuple[float, float, float]]]") -> str:
    body = "\n".join(
        f'{sid} {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}'
        for sid, (r, g, b), (x, y, z) in rows)
    return ("CGATS.17\nDEVICE_CLASS \"INPUT\"\nNUMBER_OF_FIELDS 7\n"
            "BEGIN_DATA_FORMAT\n"
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
            "END_DATA_FORMAT\n"
            f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{body}\nEND_DATA\n")


def _chart(level: float, ref_white_y: float = 82.0, n: int = 40):
    """A read whose near-white patches sit at *level* on the device scale and
    whose remaining patches fall away below them."""
    rows = []
    for i in range(n):
        f = 1.0 - i / n
        rows.append((f"A{i + 1}", (level * f, level * f * 0.99, level * f * 0.98),
                     (ref_white_y * f * 0.95, ref_white_y * f, ref_white_y * f * 1.09)))
    return rows


def test_an_under_exposed_read_is_named_and_a_good_one_is_not(tmp_path):
    good = tmp_path / "good.ti3"; good.write_text(_ti3(_chart(79.8)), encoding="utf-8")
    dark = tmp_path / "dark.ti3"; dark.write_text(_ti3(_chart(55.9)), encoding="utf-8")
    g, d = inspect_read(good, 0.98), inspect_read(dark, 0.98)
    assert not g.underexposed(DEFAULTS["scanner_min_highlight"])
    assert d.underexposed(DEFAULTS["scanner_min_highlight"])


def test_the_three_older_guards_cannot_see_an_exposure_slip(tmp_path):
    """The measured heart of B8-01, proved on the mechanism rather than
    asserted: darken every device value and coverage, agreement and clipping
    are byte-identical, because all three are scale-invariant."""
    good = tmp_path / "good.ti3"; good.write_text(_ti3(_chart(79.8)), encoding="utf-8")
    dark = tmp_path / "dark.ti3"; dark.write_text(_ti3(_chart(79.8 * 0.70)), encoding="utf-8")
    g, d = inspect_read(good, 0.98), inspect_read(dark, 0.98)
    assert (g.rows, g.agreement, g.clipped_high, g.clipped_low) == \
           (d.rows, d.agreement, d.clipped_high, d.clipped_low)
    assert not g.underexposed(DEFAULTS["scanner_min_highlight"])
    assert d.underexposed(DEFAULTS["scanner_min_highlight"])


def test_a_low_key_target_is_declined_and_never_accused(tmp_path):
    """A chart whose brightest patch is not near white has no exposure to be
    judged against. Measured on a deliberately dark chart (every reference
    value scaled to 0.28, the scan darkened to match): the level reads 44.1,
    which would be an accusation, and the reference's own brightest patch reads
    Y = 22.97, so the check declines."""
    p = tmp_path / "lowkey.ti3"
    p.write_text(_ti3(_chart(44.1, ref_white_y=22.97)), encoding="utf-8")
    got = inspect_read(p, 0.98)
    assert got.highlight is None
    assert not got.underexposed(DEFAULTS["scanner_min_highlight"])
    assert HIGHLIGHT_REFERENCE_MIN_Y > 22.97


def test_a_cast_does_not_move_the_level_but_darkening_does(tmp_path):
    """The disproof of the luminance variant, driven through the shipped
    function rather than asserted about it. A cool cast of (0.66, 0.88, 1.00)
    on Knut's sheet must leave this measure where it was; the same sheet at
    ×0.85 must move it. If :func:`highlight_level` ever goes back to weighting
    the channels, the first half of this fails."""
    rows = _chart(79.8)
    rgb = [r for _s, r, _x in rows]
    xyz = [x for _s, _r, x in rows]
    straight = highlight_level(rgb, xyz)
    cast = highlight_level([[c * g for c, g in zip(r, (0.66, 0.88, 1.00))]
                            for r in rgb], xyz)
    darker = highlight_level([[c * 0.85 for c in r] for r in rgb], xyz)
    # measured on Knut's own sheet: the near-white median goes (79.05, 78.56,
    # 78.90) -> (52.16, 69.15, 78.90) under the cast, so the LARGEST channel
    # moves 0.19 %% while the luminance moves 12.45 points.
    assert cast == pytest.approx(straight, rel=0.03), (
        "a cast moves two channels and not the one the exposure was set by")
    assert darker < 0.90 * straight


def test_the_level_ignores_a_tone_curve_and_follows_the_exposure():
    """Gamma-1.8 and gamma-2.6 scanners read 75.85 and 76.64 on the same sheet
    that reads 79.77 — a 5 % spread — while a x0.70 exposure moves it 30 %.
    Every encoding curve fixes white; that is the whole reason this measure
    works and the mean does not."""
    rows = _chart(79.8)
    rgb = [r for _s, r, _x in rows]
    xyz = [x for _s, _r, x in rows]
    straight = highlight_level(rgb, xyz)
    gamma = highlight_level(
        [[100.0 * (c / 100.0) ** (2.2 / 1.8) for c in r] for r in rgb], xyz)
    darker = highlight_level([[c * 0.70 for c in r] for r in rgb], xyz)
    assert abs(gamma - straight) / straight < 0.10
    assert darker == pytest.approx(straight * 0.70, rel=1e-6)


# --------------------------------------------------------------------------
# B8-03
def test_a_reference_of_one_colour_cannot_support_a_profile(tmp_path):
    """Both degenerate references leave ONE distinct colour. The smallest
    target ChromIQ or ArgyllCMS ships is MLG at 21 patches, and it builds
    cleanly."""
    one = tmp_path / "one.ti3"
    one.write_text(_ti3([(f"A{i}", (40.0, 40.0, 40.0), (0.0, 0.0, 0.0))
                         for i in range(1, 289)]), encoding="utf-8")
    got = inspect_read(one, 0.98)
    assert got.support == 1
    assert got.fit_is_unsupported(DEFAULTS["scanner_min_fit_support"])
    real = tmp_path / "mlg.ti3"; real.write_text(_ti3(_chart(79.8, n=21)), encoding="utf-8")
    assert inspect_read(real, 0.98).support == 21
    assert not inspect_read(real, 0.98).fit_is_unsupported(
        DEFAULTS["scanner_min_fit_support"])


def test_the_support_floor_clears_the_smallest_target_anybody_ships():
    """MLG is 21 patches; a ColorChecker is 24. The floor must sit well under
    them and well over the degenerate 1."""
    assert 1 < DEFAULTS["scanner_min_fit_support"] <= 21 // 2


def test_an_error_floor_would_not_have_worked():
    """Recorded because it is the option a reader will reach for first. The
    app's OWN bundled ColorChecker demo builds at avg err 0.059311 — a
    legitimate, shipped case only eight times above the degenerate 0.007339,
    with a cLUT build on Knut's real read at 0.462295 in between. There is no
    constant between them with any margin, which is why the shipped guard
    counts colours instead."""
    degenerate, app_own_demo = 0.007339, 0.059311
    assert app_own_demo / degenerate < 10


def test_the_fit_line_is_read_even_when_colprof_answers_nan():
    """`_PROFCHECK_RE` matched digits and dots only, so the one line the check
    most needed to read was the one line it could not."""
    from ui.dialogs.scanin_dialog import _PROFCHECK_RE
    m = _PROFCHECK_RE.search(
        "Profile check complete, peak err = 0.000000, avg err = nan")
    assert m and math.isnan(float(m.group(2)))
    m2 = _PROFCHECK_RE.search(
        "Profile check complete, peak err = 15.142837, avg err = 1.925090")
    assert m2 and float(m2.group(1)) == pytest.approx(15.142837)


def test_the_three_new_findings_are_proposed_not_approved():
    """New user-facing wording goes to §M-PROPOSED first, and stays there until
    a human says otherwise (CLAUDE.md, and #130 beta.125)."""
    for mid in ("M-SCAN-DARK", "M-SCAN-FIT-UNSUPPORTED",
                "M-SCAN-SELFCHECK-UNUSABLE"):
        assert mid in M.PROPOSED
        assert not M.CATALOGUE[mid].approved


def test_every_new_message_renders_with_nothing_left_over():
    t, b = M.M_SCAN_DARK.render(pct="56 %")
    assert "{" not in t + b and "56 %" in b
    t, b = M.M_SCAN_FIT_UNSUPPORTED.render(support=1,
                                           ref_row="Target reference data")
    assert "{" not in t + b and "same colour for every patch" in b, b
    t, b = M.M_SCAN_FIT_UNSUPPORTED.render(support=4,
                                           ref_row="Target reference data")
    assert "{" not in t + b and "only 4 different colours" in b, b
    t, b = M.M_SCAN_SELFCHECK_UNUSABLE.render(raw="0, nan")
    assert "{" not in t + b and "nan" in b


# ==========================================================================
# The real window. The two findings above are only findings if the window
# actually raises them, and the self-check is only fixed if the log and the
# button both change.
# ==========================================================================
from PyQt6.QtWidgets import QApplication                # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("dark-scan-out")


class _FakeSettings:
    def __init__(self, out_dir, **overrides):
        self._store = {**DEFAULTS, **overrides}
        self._store["custom_output_path"] = str(out_dir)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def _dialog(_app, out_dir, **overrides):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    return ScannerProfileDialog(object(), _FakeSettings(out_dir, **overrides))


def _write_read(path, level, n=40, ref_white_y=82.0):
    path.write_text(_ti3(_chart(level, ref_white_y=ref_white_y, n=n)),
                    encoding="utf-8")
    return path


def test_the_window_names_a_dark_scan_and_says_nothing_about_a_good_one(
        _app, _out_dir, tmp_path):
    """`_check_read_is_this_chart` is the method that fills the pre-build
    warning window. Before beta 8 it had three findings and an under-exposed
    read produced none of them."""
    dlg = _dialog(_app, _out_dir)
    try:
        for level, expected in ((79.8, False), (55.9, True)):
            dlg._read_findings = []
            ti3 = _write_read(tmp_path / f"read{level}.ti3", level)
            dlg._check_read_is_this_chart(
                {"params": type("P", (), {"out_ti3": ti3, "is_printer": False,
                                          "cht": tmp_path / "absent.cht",
                                          "pbase": tmp_path / "b"})()})
            titles = [t for t, _b in dlg._read_findings]
            named = any(t == M.M_SCAN_DARK.title for t in titles)
            assert named is expected, (level, titles)
    finally:
        dlg.deleteLater()


def test_the_pre_build_verdict_lines_carry_the_same_two_findings(
        _app, _out_dir, tmp_path):
    """`_read_verdicts` is the Check-alignment window's copy of the same
    questions; the two must not drift apart."""
    dlg = _dialog(_app, _out_dir)
    try:
        dark = _write_read(tmp_path / "v_dark.ti3", 55.9)
        one = tmp_path / "v_one.ti3"
        one.write_text(_ti3([(f"A{i}", (40.0, 40.0, 40.0), (0.0, 0.0, 0.0))
                             for i in range(1, 41)]), encoding="utf-8")
        params = type("P", (), {"out_ti3": dark})()
        lines = dlg._read_verdicts(params, 0.98)
        assert any(M.M_SCAN_DARK.title in l for l in lines), lines
        params.out_ti3 = one
        lines = dlg._read_verdicts(params, 0.98)
        assert any(M.M_SCAN_FIT_UNSUPPORTED.title in l for l in lines), lines
    finally:
        dlg.deleteLater()


def test_a_self_check_that_is_not_a_number_warns_and_grades_the_button(
        _app, _out_dir):
    """The whole of B8-03's second half in one place: colprof answered `nan`,
    the check must see it, say so, and hand the caller a True so the button
    below stops saying "Install profile"."""
    dlg = _dialog(_app, _out_dir)
    try:
        assert dlg._selfcheck_verdict([(2.1, 0.3)]) is False
        assert dlg._selfcheck_verdict([(0.0, float("nan"))]) is True
        assert M.M_SCAN_SELFCHECK_UNUSABLE.title in dlg._log.toPlainText()
        dlg._offer_install(failed_selfcheck=True)
        assert dlg._install_btn.text() != "Install profile"
    finally:
        dlg.deleteLater()


def test_a_perfect_self_check_on_one_colour_is_still_caught_before_the_build(
        _app, _out_dir, tmp_path):
    """The one-patch profile scores 0.007339 — better than any correct build —
    so the self-check will never catch it and must not be asked to. What
    catches it is the count, before colprof runs at all."""
    dlg = _dialog(_app, _out_dir)
    try:
        assert dlg._selfcheck_verdict([(0.007339, 0.007339)]) is False, (
            "a floor on the error is not the fix; the app's own ColorChecker "
            "demo builds at 0.059311")
        dlg._read_findings = []
        one = tmp_path / "one_colour.ti3"
        one.write_text(_ti3([("A1", (40.0, 40.0, 40.0), (20.0, 20.0, 20.0))]),
                       encoding="utf-8")
        dlg._check_read_is_this_chart(
            {"params": type("P", (), {"out_ti3": one, "is_printer": False,
                                      "cht": tmp_path / "absent.cht",
                                      "pbase": tmp_path / "b"})()})
        assert any(t == M.M_SCAN_FIT_UNSUPPORTED.title
                   for t, _b in dlg._read_findings), dlg._read_findings
    finally:
        dlg.deleteLater()
