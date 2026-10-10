"""Which outline a just-measured patch gets in the live preview (#182).

Two rulings live here, both approved on #182:

**A. Two limits, chosen by the chart** (Sebastian 5956560815 approving
proposal A of 5956305908; Knut 5956552085: *"the preferences --> measurement
should have two values, one for each of the two cases"*). A chart's expected
colours are either ArgyllCMS's rough estimate (most charts: targen had no
profile of the printer) or, when targen was given a profile, accurate enough
that targen marks the chart ``ACCURATE_EXPECTED_VALUES "true"``. ArgyllCMS's
own chartread warns at ΔE 95 for the first kind and ΔE 30 for the second
(``WERR_TH`` / ``ACC_WERR_TH``, ``native/chartread_helper/chromiq_chartread.c``),
so those were the two defaults; beta 11 lowered the second to 20 (Knut
5983470377). The chart file decides which one applies. A third limit, default
10, is for a verification judged against its profile's prediction (beta 11,
Knut 5983470377): it applies whatever the chart file says.

**B. Yellow** (Sebastian 5956560815 approving proposal B; Knut 5956831467).
A red patch that is read again and comes back with the same colour is not a
misread: it is a colour this printer and paper cannot reach. It is drawn
yellow and is no longer something to re-read.

**B2. Learning, within a colour range** (Knut 5956831467: *"if those patches
have larger error than those previously flagged for the same color range,
then one should assume that these errors are not a misread and automatically
flag these patches with yellow"*; the ranges and the count of three, #182 k10:
posted in 5961078418, confirmed by Knut 5961180259 and by Sebastian).

1. **The colour range.** Every patch belongs to one of 12 ranges: a grey
   when its chroma is under 8 (dark under L* 35, mid to under 70, light from
   70), otherwise its hue sector (``HUE_SECTORS``), with pink/rose as what is
   left over. WHICH colour is classified is decided per chart (Knut
   5963411325, approving questions 1 to 3 of 5963152271):

   * an RGB chart (its ``.ti2`` device columns are RGB, charts made from a
     profile included): the patch's DEVICE RGB read as sRGB through ArgyllCMS
     targen's own no-profile estimate (:func:`targen_estimate_xyz`), against
     that estimate's own white, so a range means the same on every printer
     (:func:`chart_device_ranges`; 0..255 values are brought to 0..100, and a
     chart carrying a calibration reads its ``.ti1``);
   * any other chart: its EXPECTED colour against the chart's own white (the
     ``.ti2``'s ``APPROX_WHITE_POINT``, D50 without one), so a chart's greys
     come out as greys.

   Blue runs from 240° to 325°: purple/violet (315° to 325°) was merged
   into it in beta 11 (Knut 5983470377, answer 4); before that the
   blue/purple edge had moved from 310° to 315° (pure sRGB blue sits at
   306°, and its most saturated tints were split between blue and purple).
   Magenta (325° to 345°) stays. The yellow-green/green edge stays 130°.
2. **Confirmed by similar patches** (Knut 5979886227, variant B of the
   k22 challenge; awaiting confirmation). Two FLAGGED patches confirm each
   other, as a re-read does, when they were read in DIFFERENT strips, their
   expected colours are less than ``PEER_EXPECTED_DE`` (ΔE*ab 6, D50) apart
   and their errors (measured minus expected) agree within ``PEER_SHIFT_DE``
   (ΔE*ab 10). Different strips, because one strip is one pass of the
   reader: a smudge or a slipped strip can make several patches of ONE strip
   wrong alike, never patches read in two passes. Peers are worked out
   afresh from the raw readings on hand at every judgement, so the current
   limit decides them and a learned patch can never confirm anything.
3. **A range learns** once ``RANGE_CONFIRMATIONS`` (3) of its patches are
   confirmed, by a re-read or by similar patches, in any mix. There is no
   spacing between them any more (it was ΔE 6, Knut 5963411325): similar
   patches lie closer than ΔE 6 by definition, so a spacing would count every
   group of them as one, which is what Knut 5979886227 calls wrong.
4. **Then** a later, or EARLIER, red patch of that range is drawn yellow when,
   against a confirmed patch of the same range:

   * **the same kind of error, as large or larger**: its measured-minus-expected
     shift points the same way (it strays at most ``SHIFT_TOLERANCE_DE``, ΔE
     10, sideways from the confirmed patch's shift) and reaches at least as far
     (no more than ΔE 10 shorter along it). A printer that cannot reach a
     colour falls short of it in one direction, and further the more vivid the
     colour asked for; a misread lands anywhere. **The size half is waived**
     when the patch's MEASURED colour lands within ``LANDING_DE`` (ΔE*ab 15)
     of that confirmed patch's MEASURED colour (Knut 5982600086, approving
     5982339631): a printer that cannot reach a colour lands its readings at
     the same place, its limit, however far apart the colours asked for are,
     so a shorter error that lands there is the same limit; a misread lands
     somewhere else;
   * **it does not stand out from its strip much more** than the confirmed
     patch did from its own: its ΔE above its strip's median is at most
     ``STANDOUT_MARGIN_DE`` (ΔE 10) more than the confirmed patch's was. This
     is what keeps a smudge or a slipped reading red even in a range where
     real differences are known. Patch by patch there is no strip, and the
     first condition is the rule.

   The verdict names the closest such confirmed patch by expected colour, ties
   by location. A patch that is like none of them stays red, and its verdict
   carries WHICH test ruled it out and the numbers (``Verdict.misfit``, for
   the hover card; Knut 5982206917). ``PATCH_SIZE_TEST`` switches the "as
   large or larger" half off entirely; Knut kept it (5982600086) with the
   landing waiver above. :meth:`FlagJudge.rejudge`, asked once per batch, judges every
   flagged patch again, so a range that learns turns its earlier red patches
   yellow and one that loses a confirmation turns them red again. A confirmed
   patch stays yellow either way.

Only confirmed patches (a re-read, or similar patches) are references; a
patch that was itself judged LEARNED never is, so the rule cannot drift from
one patch to the next. A re-read confirmation is a fact about two readings:
the limit decides whether it is shown, never whether it exists, so it is
dropped only by a LIVE reading that is clean or a different colour, never by
a repaint from the file.

**B3. A re-read is compared with every earlier reading** (Knut, #182
6045500910, beta 12; :meth:`FlagJudge.judge`). For a patch red by the limit:
a re-read the same as ANY earlier flagged reading of it (within
SAME_READING_DE) is yellow; past the limit again and like none of them, red
and *unsettled* (the card says the readings disagree and asks for one more);
under the limit after any reading past it, green (at once, or as soon as the
neighbour check stops flagging it).

**Kept with the measurement (#182 K4, Sebastian 5959447807).** The re-read
references are saved beside the ``.ti3`` (``workflow/confirmed_patches.py``)
and loaded back when that measurement is shown again or resumed; a FRESH read starts with
none, because it replaces the readings they were confirmed against.

MEASURED ON KNUT'S REAL CHARTS, re-measured for beta 11's merge of purple
into blue (``2026-10-04_beta11/limits/purple_into_blue_replay.py`` and its
``.out`` in that session's report; copies of his projects): every strip read
once with the strip test on, then every patch still red re-read in reading
order and coming back the same, the judge re-judging after each. Before
(purple 315° to 325°) -> after (blue 240° to 325°), re-read / learned:

* beta-3 run1, 648 patches (24 change range, purple to blue): limit 95, 10
  red, 3 / 7 both ways; limit 60, 49 red, 14 / 35 -> 12 / 37; limit 50, 61
  red, 16 / 45 -> 14 / 47;
* beta-8 HP CLJ5550 run1, 1944 patches (82 change range): limit 95, 18 red,
  3 / 15 both ways; limit 60, 109 red, 16 / 93 -> 12 / 97; limit 50, 129
  red, 20 / 109 -> 15 / 114;
* beta-8 run4, 324 patches (7 change range): limit 60, 23 red, 11 / 12 ->
  9 / 14; limit 50, 31 red, 12 / 19 -> 10 / 21;
* in every case no patch stays red at the end; the merge only saves
  re-reads, because the former purple patches now learn from the blues
  (the injected-misread trials were not run again for the merge);
* the shift and stand-out conditions are the ones measured against simulated
  misreads before the ranges (0 of 430 flagged reached yellow at 95, 4 of
  1,449 at 50, against 32 without the stand-out condition).
"""
from __future__ import annotations

import functools
import math
import re
from dataclasses import dataclass
from pathlib import Path

from workflow.icc_info import xyz_to_lab

#: The estimated-chart default is ArgyllCMS chartread's own WERR_TH. The
#: made-from-a-profile default was its ACC_WERR_TH (30) until beta 11, when it
#: became 20 (Knut, #182 5983470377, answer 2: "If your tests indicate 20,
#: then use it"; the replay of 5983075893 recommended 20).
ESTIMATED_DEFAULT_DE = 95.0
ACCURATE_DEFAULT_DE = 20.0
ESTIMATED_KEY = "patch_read_warn_de_estimated"
ACCURATE_KEY = "patch_read_warn_de_accurate"
#: A VERIFICATION judged against the run profile's prediction
#: (workflow/verify_expected.py) has its own limit (Knut, #182 5983470377,
#: answer 1: "own threshold row"), default ΔE 5 since beta 17 (Knut
#: 6070058549: "Lower ... from 10 to 5?" "Yes, I agree"). Used exactly when
#: the expected colours are the profile's prediction, whatever the chart file
#: says. Its strip test has its own box, off by default (6084176226).
PREDICTION_DEFAULT_DE = 5.0
PREDICTION_KEY = "patch_read_warn_de_prediction"

#: Two readings of one patch this close (ΔE*ab between the two MEASURED
#: colours) are the same reading. The default of the Same-reading tolerance
#: (configurable since beta 17, ``workflow/misread_settings.py``). Stricter than comparing the two ΔE values,
#: which could agree while the colours do not; it implies they agree within 3.
SAME_READING_DE = 3.0
#: The learning rule's "off in the same way" numbers; see the module text.
SHIFT_TOLERANCE_DE = 10.0
STANDOUT_MARGIN_DE = 10.0
#: The "as large or larger" half of "the same kind of error" (no more than
#: SHIFT_TOLERANCE_DE shorter along the confirmed patch's error). Knut KEPT
#: it (#182 5982600086, "Ok" to 5982339631), waived by LANDING_DE below.
#: Setting this False would drop it: the rule stops applying it, and the
#: hover card's "smaller" reason (Verdict.misfit) can no longer come up.
PATCH_SIZE_TEST = True
#: The size test's waiver (Knut 5982600086, approving 5982339631): a patch
#: whose MEASURED L*a*b* lands within this (ΔE*ab, D50) of a confirmed
#: patch's MEASURED L*a*b* need not be as large or larger than it. Measured
#: on Knut's 1944-patch run1: at limit 60 red 4 -> 0 (O7, J25, BG5, Y27), at
#: 50 10 -> 3, at 40 19 -> 6, and no injected misread more turned yellow in
#: any of six fault cases; ΔE 20 gave the same numbers, 15 is the stricter.
LANDING_DE = 15.0

#: Verdict.misfit's test names: why a red patch of a LEARNED range is not like
#: its confirmed patches (Knut 5982206917, answer 1 of 5982058944).
MISFIT_SIDEWAYS = "sideways"     # its error points another way
MISFIT_SMALLER = "smaller"       # its error is shorter (PATCH_SIZE_TEST)
MISFIT_STANDOUT = "standout"     # it stands out from its strip more

#: THE COLOUR RANGES (#182 5961078418, confirmed by Knut 5961180259 and by
#: Sebastian). A patch's EXPECTED colour, classified against the chart's own
#: white: a grey when its chroma is under 8 (split by lightness at L* 35 and
#: 70), otherwise by hue angle. Pink/rose (345° to 15°) is what is left over.
GREY_CHROMA = 8.0
GREY_DARK_L = 35.0
GREY_LIGHT_L = 70.0
HUE_SECTORS = (
    (15.0, 50.0, "red"),
    (50.0, 75.0, "orange"),
    (75.0, 110.0, "yellow"),
    (110.0, 130.0, "yellow_green"),
    (130.0, 165.0, "green"),
    (165.0, 240.0, "cyan"),
    # Purple/violet (315° to 325°) is merged into blue (beta 11, Knut #182
    # 5983470377, answer 4: "Merge purple into blue?" "Yes"); magenta stays.
    (240.0, 325.0, "blue"),
    (325.0, 345.0, "magenta"),
)
RANGES = ("grey_dark", "grey_mid", "grey_light", "pink") + tuple(
    name for _lo, _hi, name in HUE_SECTORS)
#: A range learns once this many of its patches are confirmed, by a re-read
#: or by similar patches, in any mix (Knut 5979886227: no spacing).
RANGE_CONFIRMATIONS = 3
#: Peer confirmation (Knut 5979886227): two flagged patches of DIFFERENT
#: strips whose expected colours are less than this apart (ΔE*ab, D50)...
PEER_EXPECTED_DE = 6.0
#: ...and whose errors (measured - expected) agree within this, the learning
#: rule's own "off in the same way" tolerance.
PEER_SHIFT_DE = SHIFT_TOLERANCE_DE

#: ArgyllCMS's D50, XYZ with Y = 1 (``workflow/icc_info.py``).
D50_WHITE = (0.96422, 1.0, 0.82521)

#: What the preview draws. ``False``/``True`` keep their old meaning (no
#: outline / red), so every caller that only asks "is it flagged?" still works;
#: the two yellow kinds are ints the preview tells apart.
FLAG_NONE = False
FLAG_RED = True
FLAG_CONFIRMED = 2
FLAG_LEARNED = 3
#: GREEN: a patch that was red (the limit or the neighbour check) and whose
#: LIVE re-read fits now (Knut, #182 5984277558, "Ok" to 5984237879): the
#: misread was corrected. Drawn green; never a reference for anything.
FLAG_CORRECTED = 4

_WHITE_RE = re.compile(r'^\s*APPROX_WHITE_POINT\s+"?([^"\n]*)"?\s*$',
                       re.IGNORECASE | re.MULTILINE)
_ACCURATE_RE = re.compile(r'^\s*ACCURATE_EXPECTED_VALUES\s+"?\s*true\s*"?\s*$',
                          re.IGNORECASE | re.MULTILINE)


def is_corrected(flag) -> bool:
    """True for the green outline of a corrected misread."""
    return (not isinstance(flag, bool) and isinstance(flag, int)
            and flag == FLAG_CORRECTED)


def is_yellow(flag) -> bool:
    """True for the two yellow kinds (and never for ``True``, which is red)."""
    return (not isinstance(flag, bool) and isinstance(flag, int)
            and flag in (FLAG_CONFIRMED, FLAG_LEARNED))


def _header(path: Path) -> str:
    """The keyword block of a CGATS file: everything before its data."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = []
            for line in fh:
                if line.strip().startswith("BEGIN_DATA"):
                    break
                lines.append(line)
            return "".join(lines)
    except OSError:
        return ""


def chart_has_accurate_expected_values(chart: "str | Path | None") -> bool:
    """Does this chart say its expected colours are accurate?

    The ``.ti2`` decides, exactly as it does for ArgyllCMS chartread. printtarg
    copies the keyword from the ``.ti1``; ChromIQ's own layout engine does not
    (yet), so when the ``.ti2`` is silent the chart's ``.ti1`` beside it, the
    file targen wrote the keyword into, is asked as well.
    """
    if not chart:
        return False
    p = Path(chart)
    ti2 = p if p.suffix.lower() == ".ti2" else p.with_suffix(".ti2")
    if _ACCURATE_RE.search(_header(ti2)):
        return True
    return bool(_ACCURATE_RE.search(_header(ti2.with_suffix(".ti1"))))


def warn_limit(settings, accurate: bool, predicted: bool = False,
               calibration: bool = False) -> float:
    """The user's Patch error limit for this chart type (Preferences ▸
    Measurement): a calibration chart first, then a verification judged
    against its profile's prediction (*predicted*), then a chart made with
    a pre-conditioning profile (*accurate*), else a chart with estimated
    colours (``workflow.misread_settings.chart_kind``)."""
    from workflow.misread_settings import chart_kind, patch_error_limit
    return patch_error_limit(settings, chart_kind(
        calibration=calibration, predicted=predicted, accurate=accurate))


def chart_white(chart: "str | Path | None") -> tuple:
    """The chart's own white, as XYZ on a 0..1 scale (Y = 1).

    Read from the ``APPROX_WHITE_POINT`` keyword of the chart's ``.ti2``, the
    white its expected colours were computed against (printtarg writes D65
    for an RGB chart, whose design colours are sRGB). D50 when the keyword is
    missing, unparsable or has no positive Y, like
    ``measurement_report._design_xyz_is_d65``.
    """
    if chart:
        p = Path(chart)
        ti2 = p if p.suffix.lower() == ".ti2" else p.with_suffix(".ti2")
        m = _WHITE_RE.search(_header(ti2))
        if m:
            parts = m.group(1).replace(",", " ").split()
            if len(parts) == 3:
                try:
                    wp = tuple(float(v) / 100.0 for v in parts)
                except ValueError:
                    wp = None
                if wp is not None and all(math.isfinite(v) and v > 0
                                          for v in wp):
                    return wp
    return D50_WHITE


def _f_inv(t: float) -> float:
    return t ** 3 if t ** 3 > 216.0 / 24389.0 else (116.0 * t - 16.0) / (24389.0 / 27.0)


def _lab_d50_to_xyz(lab) -> tuple:
    """The inverse of ``icc_info.xyz_to_lab`` against D50 (XYZ 0..1)."""
    L, a, b = (float(v) for v in lab[:3])
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    return tuple(_f_inv(f) * w for f, w in zip((fx, fy, fz), D50_WHITE))


def colour_range_of_lab(lab) -> str:
    """Which of the 13 colour ranges an L*a*b* (against the chart's white)
    falls in. Greys first, by chroma; then the hue sector, with pink/rose as
    the remainder (345° to 15°), so a hue of exactly 360.0 (``-1e-17 % 360``)
    still lands somewhere."""
    L, a, b = (float(v) for v in lab[:3])
    if math.hypot(a, b) < GREY_CHROMA:
        if L < GREY_DARK_L:
            return "grey_dark"
        if L < GREY_LIGHT_L:
            return "grey_mid"
        return "grey_light"
    h = math.degrees(math.atan2(b, a)) % 360.0
    for lo, hi, name in HUE_SECTORS:
        if lo <= h < hi:
            return name
    return "pink"


def colour_range(exp_lab_d50, white=None) -> str:
    """The colour range of a patch whose EXPECTED colour is *exp_lab_d50*
    (the L*a*b* the tab works in, against D50), classified against the chart's
    own *white* so a chart's greys come out as greys."""
    white = tuple(white) if white else D50_WHITE
    return colour_range_of_lab(xyz_to_lab(_lab_d50_to_xyz(exp_lab_d50), white))


# ---- an RGB chart: the range from the patch's own RGB numbers (#182 k10) ------
#
# Knut 5963411325 approving 5963152271 (question 1). ArgyllCMS targen's own
# estimate for an RGB device with no profile, xicc/xcolorants.c
# icxColorantLu_to_XYZ (additive branch), 3.5.0: each channel decoded with the
# sRGB curve, summed over the sRGB primaries, normalised to Y = 1, then a flat
# black flare of 0.01 in X, Y and Z. Its white is the model's own (targen
# writes it as APPROX_WHITE_POINT 95.106486 100 108.844025), which is what the
# L*a*b* is taken against. Checked against a real targen 3.5.0 run
# (tests/data/targen350_rgb.ti1).
_TARGEN_PRIMARIES = ((0.412414, 0.212642, 0.019325),
                     (0.357618, 0.715136, 0.119207),
                     (0.180511, 0.072193, 0.950770))
_TARGEN_YNORM = 1.0 / (0.212642 + 0.715136 + 0.072193)
_TARGEN_FLARE = 0.01
RGB_FIELDS = ("RGB_R", "RGB_G", "RGB_B")


def _srgb_decode(v: float) -> float:
    """The sRGB curve as targen applies it (threshold 0.03928)."""
    v = min(max(float(v), 0.0), 1.0)
    return v / 12.92 if v <= 0.03928 else ((0.055 + v) / 1.055) ** 2.4


def targen_estimate_xyz(rgb100) -> tuple:
    """targen's no-profile estimate of device RGB 0..100, XYZ with Y = 1."""
    xyz = [0.0, 0.0, 0.0]
    for prim, v in zip(_TARGEN_PRIMARIES, rgb100[:3]):
        lin = _srgb_decode(float(v) / 100.0)
        for j in range(3):
            xyz[j] += lin * prim[j]
    return tuple(x * _TARGEN_YNORM * (1.0 - _TARGEN_FLARE) + _TARGEN_FLARE
                 for x in xyz)


#: The model's own white: the estimate of RGB 100 100 100.
TARGEN_WHITE = targen_estimate_xyz((100.0, 100.0, 100.0))


def colour_range_of_rgb(rgb100) -> str:
    """The colour range of device RGB 0..100, read as sRGB through targen's
    estimate and classified against that estimate's own white."""
    return colour_range_of_lab(xyz_to_lab(targen_estimate_xyz(rgb100),
                                          TARGEN_WHITE))


def chart_device_ranges(chart: "str | Path | None") -> "dict[str, str] | None":
    """``{loc: range}`` from the chart's device RGB, or None when the chart is
    not an RGB chart and its patches keep the expected-colour rule.

    Decided for the WHOLE chart, never patch by patch: the ``.ti2``'s device
    columns must be exactly RGB_R, RGB_G and RGB_B, and every row must parse,
    or the answer is None. Values on a 0..255 scale (any above 101) are
    brought to 0..100 for the whole chart. A chart that carries a printer
    calibration takes its device values from the ``.ti1`` beside it where it
    has the same SAMPLE_ID: a layout-engine chart printed with ``-K`` before
    4.3.3-beta.5 (62e26e4e) wrote CALIBRATED values into the ``.ti2``, every
    other chart has the ``.ti1``'s own values there anyway.
    """
    if not chart:
        return None
    from workflow import printer_calibration as pc
    p = Path(chart)
    ti2 = p if p.suffix.lower() == ".ti2" else p.with_suffix(".ti2")
    try:
        fields, rows, _kw = pc.read_table(ti2)
    except (OSError, ValueError):
        return None
    if tuple(sorted(pc.device_fields_of(fields))) != tuple(sorted(RGB_FIELDS)):
        return None
    ti1_rows: dict = {}
    if pc.has_embedded_cal(ti2):
        try:
            f1, r1, _ = pc.read_table(pc._ti1_for(ti2))
            if all(f in f1 for f in RGB_FIELDS):
                ti1_rows = r1
        except (OSError, ValueError):
            ti1_rows = {}
    loc_field = "SAMPLE_LOC" if "SAMPLE_LOC" in fields else "SAMPLE_ID"
    values: "list[tuple[str, tuple]]" = []
    for sid, row in rows.items():
        src = ti1_rows.get(sid) or row
        try:
            rgb = tuple(float(src[f]) for f in RGB_FIELDS)
        except (KeyError, TypeError, ValueError):
            return None
        if not all(math.isfinite(v) for v in rgb):
            return None
        values.append((str(row.get(loc_field, sid)), rgb))
    if not values:
        return None
    scale = (100.0 / 255.0) if max(max(v) for _l, v in values) > 101.0 else 1.0
    return {loc: colour_range_of_rgb(tuple(c * scale for c in rgb))
            for loc, rgb in values}


@functools.lru_cache(maxsize=8192)
def _loc_key(loc: str):
    """A natural sort key for a chart location: A9 before A10, Z before AA."""
    m = re.match(r"^([A-Za-z]*)(\d*)(.*)$", str(loc))
    letters, digits, rest = m.groups() if m else (str(loc), "", "")
    return (len(letters), letters.upper(), int(digits) if digits else -1, rest)


def sorted_locs(locs) -> "list[str]":
    """Chart locations in reading order (A9 before A10)."""
    return sorted((str(v) for v in locs), key=_loc_key)


@dataclass
class _Reading:
    meas_lab: tuple
    de: float
    flagged: bool
    exp_lab: tuple = (0.0, 0.0, 0.0)
    standout: "float | None" = None
    #: The strip it was read in; None or "" when unknown (a loaded memory),
    #: which can never make a peer.
    strip: "str | None" = None
    #: Red by the neighbour check (Knut, #182 5984174575: "The neighbour
    #: check needs a re-read to confirm"): only its own re-read with the same
    #: value turns it yellow; it is never a similar patch and never judged
    #: like a learned range.
    reread_only: bool = False
    #: Read again past the limit and like none of its earlier readings, which
    #: were past the limit too (Knut, #182 6045500910, (a) and (c)): one of
    #: them is a misread, so it is never a similar patch for another patch.
    unsettled: bool = False


@dataclass
class _Reference:
    """A confirmed patch: what later patches are judged against. Kept for a
    re-read confirmation; made afresh from the reading for a peer."""
    loc: str
    exp_lab: tuple
    meas_lab: tuple
    shift: tuple
    de: float
    prev_de: "float | None"
    standout: "float | None"


@dataclass(frozen=True)
class Misfit:
    """One test that ruled a red patch of a learned range out against some of
    its range's confirmed patches, with the numbers the card shows. Each pair
    is (lowest, highest) over the confirmed patches this test ruled out.

    * ``sideways``: *own* is how far this patch's error strays sideways from
      each one's error (more than SHIFT_TOLERANCE_DE); *ref* is unused.
    * ``smaller``: *own* is this patch's error measured along each one's
      error, *ref* their errors (ΔE*ab): it is more than SHIFT_TOLERANCE_DE
      shorter, and *land* how far its reading is from theirs (more than
      LANDING_DE, or the size test would have been waived).
    * ``standout``: *own* is this patch's ΔE above its strip's median (one
      value), *ref* theirs: it is more than STANDOUT_MARGIN_DE higher.
    """
    test: str
    own: tuple = (0.0, 0.0)
    ref: tuple = (0.0, 0.0)
    count: int = 0               # how many confirmed patches it ruled out
    total: int = 0               # of how many with an error to compare
    #: The narrowest margin by which this test failed against one of them
    #: (ΔE past its threshold): under 1, whole numbers could make the card
    #: read as a pass, so it shows one decimal.
    gap: float = 0.0
    land: tuple = (0.0, 0.0)     # ``smaller`` only: see above


@dataclass
class Verdict:
    flag: object                  # FLAG_NONE / FLAG_RED / FLAG_CONFIRMED / FLAG_LEARNED
    prev_de: "float | None" = None   # CONFIRMED by a re-read: the reading it agreed with
    peer_locs: tuple = ()            # CONFIRMED by similar patches: them, sorted
    like_loc: str = ""               # LEARNED: the confirmed patch it was judged like
    colour_range: str = ""           # flagged: the patch's colour range (RANGES)
    range_k: int = 0                 # flagged: confirmed patches in it, 0..3
    range_locs: tuple = ()           # flagged: the confirmed patches in it, sorted
    #: RED in a LEARNED range: the tests that ruled it out against its
    #: confirmed patches (Misfit, fewest that cover every one of them). The
    #: card names them; nothing else reads them.
    misfit: tuple = ()
    #: LEARNED only by the size test's waiver (LANDING_DE): its error is
    #: shorter than its like_loc's, but its reading landed where theirs did.
    landed: bool = False
    #: RED that only a re-read can clear: the neighbour check suspects it
    #: (Knut 5984174575), so similar patches and a learned range were not
    #: asked.
    reread_only: bool = False
    #: CORRECTED (green): the rule that flagged the first reading,
    #: "neighbour" (the neighbour check, alone or with the limit) or "limit";
    #: its ΔE is *prev_de*.
    corrected_by: str = ""
    #: RED, re-read and not settled (Knut, #182 6045500910, (a) and (c)): the
    #: ΔE of its earlier readings past the limit, in the order read; no
    #: earlier flagged reading is within SAME_READING_DE of this one. A
    #: reading that matches any of them turns it yellow; one under the limit
    #: turns it green.
    unsettled: tuple = ()


def _sub(a, b):
    return tuple(float(x) - float(y) for x, y in zip(a[:3], b[:3]))


def _norm(v) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cube(lab) -> tuple:
    """The PEER_EXPECTED_DE-wide cube an expected colour falls in: two colours
    less than PEER_EXPECTED_DE apart are always in the same or touching cubes."""
    if PEER_EXPECTED_DE <= 0.0:
        return (0, 0, 0)       # peers switched off: _are_peers refuses them all
    return tuple(math.floor(float(v) / PEER_EXPECTED_DE) for v in lab[:3])


def _are_peers(a: _Reading, b: _Reading) -> bool:
    """Do these two FLAGGED readings confirm each other (Knut 5979886227)?
    Different strips, expected colours less than PEER_EXPECTED_DE apart, and
    errors within PEER_SHIFT_DE of each other."""
    if not (a.flagged and b.flagged and a.strip and b.strip
            and a.strip != b.strip):
        return False
    if a.reread_only or b.reread_only:
        return False           # a neighbour suspect: re-read only (5984174575)
    if a.unsettled or b.unsettled:
        return False           # readings that disagree (6045500910)
    if _norm(_sub(a.exp_lab, b.exp_lab)) >= PEER_EXPECTED_DE:
        return False
    return _norm(_sub(_sub(a.meas_lab, a.exp_lab),
                      _sub(b.meas_lab, b.exp_lab))) <= PEER_SHIFT_DE


#: :meth:`FlagJudge.reset`'s "keep what you have".
_KEEP = object()


class FlagJudge:
    """Remembers one measurement session's readings and decides each outline.

    The tab owns one, resets it when a session starts, asks :meth:`judge` for
    every patch it draws and :meth:`rejudge` once per batch of patches. Pure
    logic: no Qt, so the rule is tested on its own.

    *white* is the chart's own white (XYZ, Y = 1) that the colour ranges are
    classified against. It is sticky: :meth:`reset` without a white keeps the
    one it has, so a reset can never fall back to D50 behind the caller's back.

    *device_ranges* is an RGB chart's ``{loc: range}`` from its device RGB
    (:func:`chart_device_ranges`), or None for a chart that keeps the
    expected-colour rule. Sticky like the white: :meth:`reset` keeps it
    unless it is given. While it is set every patch's range comes from it, and
    a location it does not hold has no range at all (it never learns and never
    teaches), so one judge never mixes the two classifications.
    """

    def __init__(self, white=None, device_ranges=None,
                 same_reading_de: float = SAME_READING_DE) -> None:
        self._white = D50_WHITE
        self._device_ranges: "dict[str, str] | None" = None
        #: The Same-reading tolerance (beta 17, Knut #182 6082015002: one
        #: value, configurable, common to every chart type).
        self.same_reading_de = float(same_reading_de)
        self.reset(white, device_ranges=device_ranges)

    def set_same_reading_de(self, value: float) -> None:
        """Take the user's Same-reading tolerance (Preferences ▸
        Measurement). It decides the next judgement; nothing already
        decided is undone."""
        self.same_reading_de = float(value)

    @property
    def white(self) -> tuple:
        return self._white

    @property
    def device_ranges(self) -> "dict[str, str] | None":
        return self._device_ranges

    def set_white(self, white) -> None:
        """Take the chart's white without forgetting anything."""
        if white:
            self._white = tuple(float(v) for v in white[:3])
            self._ranges = {}
            self._range_index = None
            self._refs_changed()

    def set_device_ranges(self, device_ranges) -> None:
        """Take the chart's device-RGB ranges (None: the expected-colour rule)
        without forgetting anything; every patch is classified again."""
        self._device_ranges = (None if device_ranges is None
                               else {str(k): str(v)
                                     for k, v in device_ranges.items()})
        self._ranges = {}
        self._range_index = None
        self._refs_changed()

    def reset(self, white=None, device_ranges=_KEEP) -> None:
        if white:
            self._white = tuple(float(v) for v in white[:3])
        if device_ranges is not _KEEP:
            self._device_ranges = (None if device_ranges is None
                                   else {str(k): str(v)
                                         for k, v in device_ranges.items()})
        self._last: "dict[str, _Reading]" = {}
        self._refs: "dict[str, _Reference]" = {}
        #: loc -> the last verdict given for it (flagged readings only).
        self._verdicts: "dict[str, Verdict]" = {}
        #: loc -> colour range, and range -> (k, confirmed locs).
        self._ranges: "dict[str, str]" = {}
        self._status_cache: "dict[str, tuple]" = {}
        #: The flagged readings, and which of them confirm each other
        #: (loc -> partner locs), kept up to date reading by reading.
        self._flagged: "set[str]" = set()
        self._peers: "dict[str, set]" = {}
        #: The flagged patches by expected colour, in cubes PEER_EXPECTED_DE
        #: wide, so a reading is tested only against the 27 cubes around it
        #: rather than every flagged patch (thousands, at a low limit).
        self._cubes: "dict[tuple, set]" = {}
        self._cube_of: "dict[str, tuple]" = {}
        #: range -> its flagged patches (None: built again when next asked).
        self._range_index: "dict[str, set] | None" = None
        self._indexed_as: "dict[str, str]" = {}
        #: loc -> (ΔE of the reading that was red, "neighbour" | "limit"):
        #: corrected by a live re-read that fits (Knut 5984277558). Never a
        #: reference; a later live reading that is flagged again ends it.
        self._corrected: "dict[str, tuple]" = {}
        #: loc -> (ΔE of the misread, "neighbour" | "limit", its measured
        #: L*a*b*): a LIVE re-read differed from a flagged reading by more
        #: than SAME_READING_DE while the patch was still flagged for another
        #: reason (the neighbour check had not cleared it yet). It turns
        #: green (``_corrected``) the moment the patch is judged not flagged,
        #: live or not (beta 12, #182 FINDINGS B1, the AA5 case).
        self._pending: "dict[str, tuple]" = {}
        #: loc -> every distinct reading of it this session, in the order
        #: read (the last one is ``_last``'s): a re-read is compared with ALL
        #: of them, not only the one straight before it (Knut, #182
        #: 6045500910: "if the third measurement is same as any of the two
        #: first, then it turns yellow"). A repaint of the same reading adds
        #: nothing; it brings the last one's flag up to date.
        self._history: "dict[str, list]" = {}
        #: loc -> the earlier readings' ΔE of a patch re-read past the limit
        #: like none of them (Verdict.unsettled).
        self._unsettled: "dict[str, tuple]" = {}
        #: Unsettled patches taken over from a stored memory (``load``): the
        #: first reading of them painted from the file stays unsettled.
        self._unsettled_loaded: "set[str]" = set()

    @property
    def corrected(self) -> "dict[str, tuple]":
        """``{loc: (first ΔE, "neighbour" | "limit")}``: misreads a re-read
        corrected (green), whether shown now or not."""
        return dict(self._corrected)

    @property
    def confirmed(self) -> "list[str]":
        """The patches a re-read confirmed (whether shown at this limit or not)."""
        return sorted(self._refs)

    def peers_of(self, loc: str) -> "list[str]":
        """The patches that confirm *loc* as similar patches, in reading order."""
        return sorted_locs(self._peers.get(str(loc), ()))

    # ---- the readings and their peers ----------------------------------------
    def _set_reading(self, loc: str, rd: _Reading,
                     was_range: "str | None" = None) -> None:
        """Remember *rd* as the last reading of *loc* and bring the peers up to
        date, testing only the flagged patches of nearly the same expected
        colour, so a whole chart repainted at a low limit stays cheap.

        Only the colour ranges this reading can change are counted again:
        *loc*'s (before and now) and those of the patches it stops or starts
        confirming (*was_range*: *loc*'s range before this reading)."""
        self._last[loc] = rd
        touched = {loc} | self._peers.get(loc, set())
        for other in self._peers.pop(loc, set()):
            partners = self._peers.get(other)
            if partners is not None:
                partners.discard(loc)
                if not partners:
                    del self._peers[other]
        if loc in self._flagged:
            self._flagged.discard(loc)
            cube = self._cube_of.pop(loc, None)
            if cube is not None:
                members = self._cubes.get(cube)
                if members is not None:
                    members.discard(loc)
                    if not members:
                        del self._cubes[cube]
        if rd.flagged:
            self._flagged.add(loc)
            cube = _cube(rd.exp_lab)
            self._cube_of[loc] = cube
            self._cubes.setdefault(cube, set()).add(loc)
            if rd.strip:
                mine = set()
                c0, c1, c2 = cube
                for d0 in (-1, 0, 1):
                    for d1 in (-1, 0, 1):
                        for d2 in (-1, 0, 1):
                            for other in self._cubes.get(
                                    (c0 + d0, c1 + d1, c2 + d2), ()):
                                if other != loc and _are_peers(
                                        rd, self._last[other]):
                                    mine.add(other)
                                    self._peers.setdefault(other, set()).add(loc)
                if mine:
                    self._peers[loc] = mine
                    touched |= mine
        if self._range_index is not None:
            old_rng = self._indexed_as.pop(loc, None)
            if old_rng is not None:
                self._range_index.get(old_rng, set()).discard(loc)
            if rd.flagged:
                rng_now = self.range_of(loc, rd.exp_lab)
                self._indexed_as[loc] = rng_now
                self._range_index.setdefault(rng_now, set()).add(loc)
        stale = {was_range} if was_range else set()
        for other in touched:
            o = self._last.get(other)
            if o is not None:
                stale.add(self.range_of(other, o.exp_lab))
        for rng in stale:
            self._status_cache.pop(rng, None)

    def _active_ref(self, loc: str) -> "_Reference | None":
        """*loc*'s re-read reference, while its last reading is flagged: a
        confirmation the current limit does not show teaches nothing."""
        ref = self._refs.get(loc)
        rd = self._last.get(loc)
        if ref is None or rd is None or not rd.flagged:
            return None
        return ref

    # ---- the colour ranges ---------------------------------------------------
    def range_of(self, loc: str, exp_lab) -> str:
        """The colour range of *loc*: from the chart's device RGB on an RGB
        chart ("" when the chart does not hold *loc*), otherwise from its
        expected colour against the chart's white."""
        loc = str(loc)
        if self._device_ranges is not None:
            return self._device_ranges.get(loc, "")
        r = self._ranges.get(loc)
        if r is None:
            r = self._ranges[loc] = colour_range(exp_lab, self._white)
        return r

    def _refs_changed(self) -> None:
        self._status_cache = {}

    def _range_refs(self, rng: str) -> "list[_Reference]":
        """Every confirmed patch of range *rng*, in reading order: its re-read
        references (shown at this limit) and its peer-confirmed patches, the
        latter made afresh from their readings."""
        if self._range_index is None:
            self._range_index, self._indexed_as = {}, {}
            for loc in self._flagged:
                r = self.range_of(loc, self._last[loc].exp_lab)
                self._indexed_as[loc] = r
                self._range_index.setdefault(r, set()).add(loc)
        out = []
        for loc in self._range_index.get(rng, ()):
            rd = self._last[loc]
            ref = self._active_ref(loc)
            if ref is None and loc in self._peers:
                ref = _Reference(loc=loc, exp_lab=rd.exp_lab,
                                 meas_lab=rd.meas_lab,
                                 shift=_sub(rd.meas_lab, rd.exp_lab),
                                 de=rd.de, prev_de=None, standout=rd.standout)
            if ref is not None:
                out.append(ref)
        out.sort(key=lambda r: _loc_key(r.loc))
        return out

    def _range_entry(self, rng: str) -> tuple:
        hit = self._status_cache.get(rng)
        if hit is None:
            refs = self._range_refs(rng)
            # Each reference's error length and direction, worked out once per
            # change rather than once per patch judged against it: with every
            # peer a reference, a chart of thousands of flagged patches made
            # _like the whole cost of a repaint (k22 review, measured).
            axes = []
            for r in refs:
                n = _norm(r.shift)
                if n > 0.0:
                    axes.append((r, n, tuple(v / n for v in r.shift)))
            hit = self._status_cache[rng] = (
                min(len(refs), RANGE_CONFIRMATIONS),
                tuple(r.loc for r in refs), refs, axes)
        return hit

    def range_status(self, rng: str) -> "tuple[int, tuple]":
        """``(k, locs)`` for colour range *rng*: how many of its patches are
        confirmed, by a re-read or by similar patches (0..3), and every
        confirmed patch in it, in reading order."""
        if not rng:
            return 0, ()                  # no range: never learns, never teaches
        k, locs, _refs, _axes = self._range_entry(rng)
        return k, locs

    def range_learned(self, rng: str) -> bool:
        return self.range_status(rng)[0] >= RANGE_CONFIRMATIONS

    # ---- the memory file -----------------------------------------------------
    def export(self) -> dict:
        """The memory in the schema of ``workflow/confirmed_patches.py``.

        Every re-read reference, shown at this limit or not (raising the
        limit does not lose a confirmation). Peers are written as ``peer``
        for the record (Check & Refine never reads it, Knut 5980560281), and
        never loaded back as references: they are worked out again from the
        readings."""
        out: dict = {}
        for loc, ref in self._refs.items():
            out[loc] = {"kind": "confirmed", "de": ref.de, "prev_de": ref.prev_de,
                        "exp_lab": list(ref.exp_lab),
                        "meas_lab": list(ref.meas_lab),
                        "shift": list(ref.shift), "standout": ref.standout}
        for loc, partners in self._peers.items():
            if loc not in out and partners:
                out[loc] = {"kind": "peer", "with": sorted_locs(partners)}
        for loc, v in self._verdicts.items():
            if (not isinstance(v.flag, bool) and v.flag == FLAG_LEARNED
                    and loc not in out and v.like_loc):
                out[loc] = {"kind": "learned", "like": v.like_loc}
        # GREEN (Knut 5984277558): remembered with the measurement and shown
        # again when it is opened; never loaded as a reference.
        for loc, (de, by) in self._corrected.items():
            rd = self._last.get(loc)
            if loc not in out and (rd is None or not rd.flagged):
                out[loc] = {"kind": "corrected", "de": de, "by": by}
        # RED, UNSETTLED (Knut 6045500910): kept with the measurement, with
        # its earlier flagged readings, so it is still red when opened again
        # and a later re-read can still match any of them.
        for loc, prevs in self._unsettled.items():
            rd = self._last.get(loc)
            hist = self._history.get(loc, [])
            if loc in out or rd is None or not rd.flagged or not hist:
                continue
            out[loc] = {"kind": "unsettled", "prevs": list(prevs),
                        "readings": [{"de": r.de, "meas_lab": list(r.meas_lab)}
                                     for r in hist[:-1] if r.flagged]}
        return out

    def load(self, patches: dict) -> int:
        """Take the CONFIRMED patches of a stored memory as references.

        Learned entries are not loaded: they are judged again from the
        references, so a stored guess can never become a reference (and a
        file written before the colour ranges may name, as ``like``, a patch
        of another range). Each confirmed patch is also remembered as the last
        reading of its patch, flagged, which is what it was. Returns how many
        were loaded.
        """
        n = 0
        for loc, e in (patches or {}).items():
            if isinstance(e, dict) and e.get("kind") == "corrected":
                # Green again when the measurement is opened (5984277558);
                # not a reference, so not counted.
                try:
                    self._corrected[str(loc)] = (
                        float(e.get("de", 0.0)),
                        "neighbour" if e.get("by") == "neighbour" else "limit")
                except (TypeError, ValueError):
                    pass
                continue
            if isinstance(e, dict) and e.get("kind") == "unsettled":
                # Red until a reading settles it (6045500910); its earlier
                # readings are the ones a re-read is compared with.
                try:
                    prevs = tuple(float(x) for x in e.get("prevs") or ())
                    readings = [
                        _Reading(tuple(float(v) for v in r["meas_lab"][:3]),
                                 float(r["de"]), True)
                        for r in e.get("readings") or ()]
                except (KeyError, TypeError, ValueError):
                    continue
                if prevs and readings:
                    self._unsettled[str(loc)] = prevs
                    self._unsettled_loaded.add(str(loc))
                    self._history[str(loc)] = readings
                continue
            if not isinstance(e, dict) or e.get("kind") != "confirmed":
                continue
            try:
                exp_lab = tuple(float(v) for v in e["exp_lab"][:3])
                meas_lab = tuple(float(v) for v in e["meas_lab"][:3])
                de = float(e.get("de", 0.0))
                prev = e.get("prev_de")
                prev = None if prev is None else float(prev)
                so = e.get("standout")
                so = None if so is None else float(so)
            except (KeyError, TypeError, ValueError):
                continue
            if len(exp_lab) != 3 or len(meas_lab) != 3:
                continue
            loc = str(loc)
            self._refs[loc] = _Reference(
                loc=loc, exp_lab=exp_lab, meas_lab=meas_lab,
                shift=_sub(meas_lab, exp_lab), de=de, prev_de=prev,
                standout=so)
            was = self._ranges.pop(loc, None)
            self._set_reading(loc, _Reading(meas_lab, de, True, exp_lab, so),
                              was)
            n += 1
        self._refs_changed()
        return n

    # ---- the rule ------------------------------------------------------------
    @staticmethod
    def _landing(ref, exp_lab, shift) -> float:
        """How far this patch's MEASURED colour (expected + shift) is from
        confirmed patch *ref*'s measured colour (ΔE*ab)."""
        m = ref.meas_lab
        return math.sqrt((exp_lab[0] + shift[0] - m[0]) ** 2
                         + (exp_lab[1] + shift[1] - m[1]) ** 2
                         + (exp_lab[2] + shift[2] - m[2]) ** 2)

    @staticmethod
    def _tests(ref, n, u, exp_lab, shift, standout):
        """The three "off in the same way" tests of one patch against one
        confirmed patch *ref* (its error length *n*, direction *u*):
        ``(side, along, land, failed)``, *land* how far its reading is from
        *ref*'s, *failed* a tuple of MISFIT_* names, empty when this patch
        is like it."""
        s0, s1, s2 = shift[0], shift[1], shift[2]
        along = s0 * u[0] + s1 * u[1] + s2 * u[2]
        side = math.sqrt((s0 - along * u[0]) ** 2 + (s1 - along * u[1]) ** 2
                         + (s2 - along * u[2]) ** 2)
        land = FlagJudge._landing(ref, exp_lab, shift)
        failed = []
        if side > SHIFT_TOLERANCE_DE:
            failed.append(MISFIT_SIDEWAYS)
        if (PATCH_SIZE_TEST and along < n - SHIFT_TOLERANCE_DE
                and land > LANDING_DE):
            failed.append(MISFIT_SMALLER)
        if (standout is not None and ref.standout is not None
                and standout > ref.standout + STANDOUT_MARGIN_DE):
            failed.append(MISFIT_STANDOUT)
        return side, along, land, tuple(failed)

    def _like(self, rng, exp_lab, shift, standout) -> "_Reference | None":
        """The confirmed patch of range *rng* whose error this one is like:
        the closest by expected colour (ΔE*ab, D50), ties by location."""
        return self._match(rng, exp_lab, shift, standout)[0]

    def _match(self, rng, exp_lab, shift, standout) -> tuple:
        """``(ref, landed)``: :meth:`_like`'s answer, and whether that patch
        passed the size test only by its waiver (its reading landed within
        LANDING_DE of *ref*'s, Knut 5982600086)."""
        best = None
        best_key = None
        best_landed = False
        s0, s1, s2 = shift[0], shift[1], shift[2]
        e0, e1, e2 = exp_lab[0], exp_lab[1], exp_lab[2]
        for ref, n, u in (self._range_entry(rng)[3] if rng else ()):
            along = s0 * u[0] + s1 * u[1] + s2 * u[2]
            landed = False
            if PATCH_SIZE_TEST and along < n - SHIFT_TOLERANCE_DE:
                if self._landing(ref, exp_lab, shift) > LANDING_DE:
                    continue
                landed = True
            side = math.sqrt((s0 - along * u[0]) ** 2 + (s1 - along * u[1]) ** 2
                             + (s2 - along * u[2]) ** 2)
            if side > SHIFT_TOLERANCE_DE:
                continue
            if (standout is not None and ref.standout is not None
                    and standout > ref.standout + STANDOUT_MARGIN_DE):
                continue
            x = ref.exp_lab
            dist = math.sqrt((e0 - x[0]) ** 2 + (e1 - x[1]) ** 2
                             + (e2 - x[2]) ** 2)
            # The location only breaks a tie, so it is only worked out for one.
            if (best_key is None or dist < best_key[0]
                    or (dist == best_key[0]
                        and _loc_key(ref.loc) < _loc_key(best.loc))):
                best, best_key, best_landed = ref, (dist,), landed
        return best, best_landed

    def _misfit(self, rng, exp_lab, shift, standout) -> tuple:
        """Why a patch :meth:`_like` found like none of range *rng*'s
        confirmed patches is red (Knut 5982206917): the fewest tests that
        between them rule out every confirmed patch, each with its numbers.

        Usually one test rules them all out. When it takes more, the test
        that rules out the most comes first; a tie goes to a test the closest
        confirmed patch (by expected colour, then location) failed, then to
        the order sideways, smaller, standout. Reporting only, never a
        verdict: :meth:`_like` alone decides the outline."""
        rows = []     # (dist, loc key, ref, side, along, n, failed, land)
        for ref, n, u in (self._range_entry(rng)[3] if rng else ()):
            side, along, land, failed = self._tests(ref, n, u, exp_lab, shift,
                                                    standout)
            if not failed:
                return ()                 # it is like this one: not red here
            dist = _norm(_sub(exp_lab, ref.exp_lab))
            rows.append((dist, _loc_key(ref.loc), ref, side, along, n, failed,
                         land))
        if not rows:
            return ()
        rows.sort(key=lambda r: (r[0], r[1]))
        closest = rows[0][6]
        order = (MISFIT_SIDEWAYS, MISFIT_SMALLER, MISFIT_STANDOUT)
        left = list(range(len(rows)))
        chosen = []
        while left:
            def score(t):
                return (-sum(1 for i in left if t in rows[i][6]),
                        0 if t in closest else 1, order.index(t))
            best = min((t for t in order
                        if any(t in rows[i][6] for i in left)), key=score)
            chosen.append(best)
            left = [i for i in left if best not in rows[i][6]]
        out = []
        for t in chosen:
            hit = [r for r in rows if t in r[6]]
            land = (0.0, 0.0)
            if t == MISFIT_SIDEWAYS:
                own = [r[3] for r in hit]
                ref = [0.0]
                gap = min(r[3] - SHIFT_TOLERANCE_DE for r in hit)
            elif t == MISFIT_SMALLER:
                own = [r[4] for r in hit]
                ref = [r[5] for r in hit]
                # It fails only when it is short AND lands elsewhere, so the
                # narrower of the two margins is how near it came to passing.
                gap = min(min(r[5] - SHIFT_TOLERANCE_DE - r[4],
                              r[7] - LANDING_DE) for r in hit)
                land = (min(r[7] for r in hit), max(r[7] for r in hit))
            else:
                own = [float(standout)]
                ref = [float(r[2].standout) for r in hit]
                gap = min(float(standout) - STANDOUT_MARGIN_DE - v for v in ref)
            out.append(Misfit(t, (min(own), max(own)), (min(ref), max(ref)),
                              len(hit), len(rows), gap, land))
        return tuple(out)

    def _verdict(self, loc: str, rd: _Reading) -> Verdict:
        """The verdict for a FLAGGED reading, as the references stand now."""
        rng = self.range_of(loc, rd.exp_lab)
        k, locs = self.range_status(rng)
        own = self._active_ref(loc)
        unsettled = self._unsettled.get(loc, ()) if own is None else ()
        if own is None and (rd.reread_only or unsettled):
            # A neighbour suspect: only its own re-read clears it (Knut,
            # #182 5984174575), whatever similar patches or its range say.
            # A re-read past the limit like none of its earlier readings
            # stays red until a reading settles it (Knut, #182 6045500910,
            # (a) and (c)): one of them is a misread, so neither similar
            # patches nor a learned range may vouch for it.
            return Verdict(FLAG_RED, colour_range=rng, range_k=k,
                           range_locs=locs, reread_only=rd.reread_only,
                           unsettled=unsettled)
        peers = tuple(self.peers_of(loc)) if own is None else ()
        if own is not None or peers:
            # Confirmed stays yellow, whether its range has learned or not.
            # A re-read is named first: it is the stronger proof.
            return Verdict(FLAG_CONFIRMED,
                           prev_de=None if own is None else own.prev_de,
                           peer_locs=peers,
                           colour_range=rng, range_k=k, range_locs=locs)
        if k >= RANGE_CONFIRMATIONS:
            ref, landed = self._match(rng, rd.exp_lab,
                                      _sub(rd.meas_lab, rd.exp_lab),
                                      rd.standout)
            if ref is not None:
                return Verdict(FLAG_LEARNED, like_loc=ref.loc,
                               colour_range=rng, range_k=k, range_locs=locs,
                               landed=landed)
            return Verdict(FLAG_RED, colour_range=rng, range_k=k,
                           range_locs=locs,
                           misfit=self._misfit(
                               rng, rd.exp_lab, _sub(rd.meas_lab, rd.exp_lab),
                               rd.standout))
        return Verdict(FLAG_RED, colour_range=rng, range_k=k, range_locs=locs)

    def judge(self, loc: str, exp_lab, meas_lab, de: float, flagged: bool,
              *, standout: "float | None" = None, live: bool = True,
              strip: "str | None" = None,
              reread_only: bool = False,
              limit: "float | None" = None) -> Verdict:
        """The outline for this reading of *loc*, as things stand now.

        *flagged* is the red rule's answer (past the limit and, reading strips
        with the strip test on, an outlier of its strip). *standout* is the
        patch's ΔE above its strip's median, or None without a strip. *live*
        is False for readings repainted from the file: they are remembered as
        the previous reading, but a file read twice is not a second reading,
        so only a live reading can confirm, and only a live reading can take
        a re-read confirmation away (a repaint at a higher limit only hides
        it). *strip* names the strip the patch was read in (the caller's
        ``_strip_of``): patches of different strips can confirm each other.
        *reread_only*: the neighbour check suspects it (Knut, #182
        5984174575), so only its own re-read with the same value turns it
        yellow; similar patches and a learned range apply only to the limit.
        *limit* is the ΔE the limit check flags at (the caller's
        ``_patch_warn_limit``); without it the two rules that speak of the
        limit itself ((a)/(c) and (d) below) are not applied.

        THE RE-READ RULES (Knut, #182 6045500910, for a patch red by the
        limit). A live re-read is compared with EVERY earlier reading of the
        patch this session, not only the one straight before it:

        * the same colour (within SAME_READING_DE) as any earlier flagged
          reading, and still flagged: yellow, confirmed by a re-read ((b),
          and a third reading that matches the first after a misread);
        * past the limit again, like none of the earlier flagged readings,
          one or more of which were past the limit too: red, *unsettled*
          ((a) and (c)), until a reading settles it;
        * under the limit after one or more readings past it: green, at once
          when nothing else flags it, else as soon as nothing does ((d)).

        A confirmation (or the loss of one) can change OTHER patches' verdicts
        too; the caller asks :meth:`rejudge` once the whole batch is judged.
        """
        loc = str(loc)
        de = float(de)
        meas_lab = tuple(float(v) for v in meas_lab[:3])
        exp_lab = tuple(float(v) for v in exp_lab[:3])
        prev = self._last.get(loc)
        hist = self._history.setdefault(loc, [])
        earlier = list(hist) if live else []
        if live and prev is not None and (not hist or hist[-1] is not prev):
            # A reading taken over from a stored memory (``load``) is the
            # previous reading too.
            earlier.append(prev)
        lim = None if limit is None else float(limit)
        # Every threshold at one decimal, as the cards print it: "past" is
        # ABOVE the limit, "the same" is not above the tolerance (Knut, #182
        # 6094941512).
        from workflow.misread_settings import above, within

        def same(a, b) -> bool:
            return within(_norm(_sub(a, b)), self.same_reading_de)

        def by_of(r) -> str:
            return "neighbour" if r.reread_only else "limit"

        def past(r) -> bool:
            return lim is not None and r.flagged and above(r.de, lim)

        # (a)/(c): past the limit again, and like none of the earlier flagged
        # readings, of which one or more were past the limit too.
        unsettled: tuple = ()
        if live and flagged and lim is not None and above(de, lim):
            red_before = [r for r in earlier if r.flagged]
            if (any(past(r) for r in red_before)
                    and not any(same(meas_lab, r.meas_lab)
                                for r in red_before)):
                unsettled = tuple(float(r.de) for r in red_before if past(r))
        rd = _Reading(meas_lab, de, bool(flagged), exp_lab,
                      None if standout is None else float(standout),
                      None if strip is None else str(strip),
                      bool(reread_only and flagged), bool(unsettled))
        if live:
            hist.append(rd)
            if unsettled:
                self._unsettled[loc] = unsettled
            else:
                self._unsettled.pop(loc, None)
        elif hist and same(meas_lab, hist[-1].meas_lab):
            # A repaint of the same reading: it only brings the flag up to
            # date (a later strip cleared the neighbour check, say).
            rd.unsettled = bool(hist[-1].unsettled and flagged)
            hist[-1] = rd
            if not rd.unsettled:
                self._unsettled.pop(loc, None)
        else:
            # A reading from the file (a measurement resumed or opened): the
            # previous reading a live re-read is compared with. Still
            # unsettled when the stored memory says so (``load``).
            hist.append(rd)
            if loc in self._unsettled_loaded and flagged:
                rd.unsettled = True
            else:
                self._unsettled.pop(loc, None)
            self._unsettled_loaded.discard(loc)
        if not live and rd.unsettled and lim is not None:
            # Judged again against the limit as it is NOW (raised in
            # Preferences, or the measurement opened under another one):
            # an earlier reading no longer past it does not make the patch
            # unsettled, and the card never says "both are past your limit"
            # of a reading that is not (review of beta 12).
            still = tuple(x for x in self._unsettled.get(loc, ())
                          if above(x, lim))
            if still:
                self._unsettled[loc] = still
            else:
                rd.unsettled = False
                self._unsettled.pop(loc, None)
        was = self._ranges.pop(loc, None)   # classified from this expected colour
        self._set_reading(loc, rd, was)
        own = self._refs.get(loc)

        # (d): the last earlier reading past the limit, when this one is
        # under it (Knut 6045500910: "if any of the previous measurements
        # were above the threshold").
        over = None
        if live and lim is not None and not above(de, lim):
            for r in reversed(earlier):
                if past(r):
                    over = r
                    break
        if not flagged:
            # GREEN (Knut, #182 5984277558): it was red, and this LIVE
            # reading fits. A repaint or a judgement from other readings is
            # not a re-read, so it never makes one; it keeps one made before.
            # A re-read that gives the SAME colour (within SAME_READING_DE)
            # corrected nothing when only the limit moved; one that falls
            # under the limit after a reading past it did (6045500910 (d)).
            pending = self._pending.pop(loc, None)
            if over is not None:
                self._corrected[loc] = (float(over.de), "limit")
            elif (live and prev is not None and prev.flagged
                    and not same(meas_lab, prev.meas_lab)):
                self._corrected[loc] = (float(prev.de), by_of(prev))
            elif pending is not None:
                # A live re-read already corrected the misread while another
                # reason still flagged the patch; that reason is gone now.
                self._corrected[loc] = (pending[0], pending[1])
            # Read clean now, LIVE: whatever was confirmed about it no longer
            # holds. A repaint from the file only hides it (the limit).
            if live and self._refs.pop(loc, None) is not None:
                self._refs_changed()
            self._verdicts.pop(loc, None)
            corr = self._corrected.get(loc)
            if corr is not None:
                return Verdict(FLAG_CORRECTED, prev_de=corr[0],
                               corrected_by=corr[1])
            return Verdict(FLAG_NONE)
        # The same colour as ANY earlier flagged reading (Knut 6045500910);
        # the latest such reading is the one it agrees with.
        match = None
        if flagged:
            for r in reversed(earlier):
                if r.flagged and same(meas_lab, r.meas_lab):
                    match = r
                    break
        if live:
            # Flagged again by a live reading: no longer corrected.
            self._corrected.pop(loc, None)
            pending = self._pending.get(loc)
            if pending is not None and same(meas_lab, pending[2]):
                # The misread came back: nothing was corrected.
                self._pending.pop(loc, None)
                pending = None
            if pending is None:
                if over is not None:
                    # Under the limit now, but still flagged (the neighbour
                    # check): green once nothing flags it (6045500910 (d)).
                    self._pending[loc] = (float(over.de), "limit",
                                          over.meas_lab)
                elif (match is None and prev is not None and prev.flagged
                        and not same(meas_lab, prev.meas_lab)):
                    # A re-read to a clearly different colour that is still
                    # flagged (say, the neighbour check still suspects it):
                    # it turns green once nothing flags it any more. Not
                    # when it repeats an earlier reading: then it confirms
                    # that one, and corrects nothing.
                    self._pending[loc] = (float(prev.de), by_of(prev),
                                          prev.meas_lab)
        if own is not None and same(meas_lab, own.meas_lab):
            pass                          # the same colour once more: confirmed
        else:
            if match is not None:
                self._refs[loc] = _Reference(
                    loc=loc, exp_lab=exp_lab, meas_lab=meas_lab,
                    shift=_sub(meas_lab, exp_lab), de=de, prev_de=match.de,
                    standout=rd.standout)
                self._refs_changed()
            elif live and own is not None:
                # Re-read to a clearly different colour: it is not confirmed now.
                self._refs.pop(loc, None)
                self._refs_changed()
        v = self._verdict(loc, rd)
        self._verdicts[loc] = v
        return v

    def rejudge(self) -> "dict[str, Verdict]":
        """Judge every flagged patch again against the references as they
        stand now; ``{loc: verdict}`` for each whose verdict changed.

        Both ways: red to learned (its range has just learned), learned to red
        (its range no longer has three confirmations, or no confirmed
        patch in it is like this one any more), another confirmed patch to be
        like, or a new count of confirmations for the card to show."""
        changed: "dict[str, Verdict]" = {}
        for loc, rd in self._last.items():
            if not rd.flagged:
                continue
            v = self._verdict(loc, rd)
            if self._verdicts.get(loc) != v:
                self._verdicts[loc] = v
                changed[loc] = v
        return changed
