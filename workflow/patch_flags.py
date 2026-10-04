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
so those are the two defaults. The chart file decides which one applies.

**B. Yellow** (Sebastian 5956560815 approving proposal B; Knut 5956831467).
A red patch that is read again and comes back with the same colour is not a
misread: it is a colour this printer and paper cannot reach. It is drawn
yellow and is no longer something to re-read.

**B2. Learning, within a colour range** (Knut 5956831467: *"if those patches
have larger error than those previously flagged for the same color range,
then one should assume that these errors are not a misread and automatically
flag these patches with yellow"*; the ranges and the count of three, #182 k10:
posted in 5961078418, confirmed by Knut 5961180259 and by Sebastian).

1. **The colour range.** Every patch belongs to one of 13 ranges: a grey
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

   The blue/purple edge is 315° (it was 310°: pure sRGB blue sits at 306°,
   and its most saturated tints were split between blue and purple); the
   yellow-green/green edge stays 130°.
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
     colour asked for; a misread lands anywhere;
   * **it does not stand out from its strip much more** than the confirmed
     patch did from its own: its ΔE above its strip's median is at most
     ``STANDOUT_MARGIN_DE`` (ΔE 10) more than the confirmed patch's was. This
     is what keeps a smudge or a slipped reading red even in a range where
     real differences are known. Patch by patch there is no strip, and the
     first condition is the rule.

   The verdict names the closest such confirmed patch by expected colour, ties
   by location. :meth:`FlagJudge.rejudge`, asked once per batch, judges every
   flagged patch again, so a range that learns turns its earlier red patches
   yellow and one that loses a confirmation turns them red again. A confirmed
   patch stays yellow either way.

Only confirmed patches (a re-read, or similar patches) are references; a
patch that was itself judged LEARNED never is, so the rule cannot drift from
one patch to the next. A re-read confirmation is a fact about two readings:
the limit decides whether it is shown, never whether it exists, so it is
dropped only by a LIVE reading that is clean or a different colour, never by
a repaint from the file.

**Kept with the measurement (#182 K4, Sebastian 5959447807).** The re-read
references are saved beside the ``.ti3`` (``workflow/confirmed_patches.py``)
and loaded back when that measurement is shown again or resumed; a FRESH read starts with
none, because it replaces the readings they were confirmed against.

MEASURED ON KNUT'S REAL CHART (beta 3 run1, 648 patches, i1Pro 2, estimated
expected colours), replayed with every red patch re-read in reading order
(``2026-10-03_srgb_ranges/knut_srgb_ranges_replay.py`` of that session's
report; the earlier thresholds: ``AF_impl_flag_limits/flag_rule_knut_data.py``):

* at the default 95, 10 patches are flagged, all ten blue by their RGB
  numbers. O9 (RGB hue 311°) was purple under the 310° edge; now the triple
  A23, O9, U4 teaches the blue range before U16 is reached, so 9 are re-read
  and U16 is learned (before: 10 re-read, none learned);
* at the old limit 50 (61 flagged with the strip test), 18 are re-read and 43
  are learned (before: 19 and 42);
* 18 of the chart's 648 patches change range against the old rule, most of
  them purple to blue at the moved edge;
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

#: The ArgyllCMS thresholds the two defaults follow.
ESTIMATED_DEFAULT_DE = 95.0
ACCURATE_DEFAULT_DE = 30.0
ESTIMATED_KEY = "patch_read_warn_de_estimated"
ACCURATE_KEY = "patch_read_warn_de_accurate"

#: Two readings of one patch this close (ΔE*ab between the two MEASURED
#: colours) are the same reading. Stricter than comparing the two ΔE values,
#: which could agree while the colours do not; it implies they agree within 3.
SAME_READING_DE = 3.0
#: The learning rule's "off in the same way" numbers; see the module text.
SHIFT_TOLERANCE_DE = 10.0
STANDOUT_MARGIN_DE = 10.0

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
    (240.0, 315.0, "blue"),
    (315.0, 325.0, "purple"),
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

_WHITE_RE = re.compile(r'^\s*APPROX_WHITE_POINT\s+"?([^"\n]*)"?\s*$',
                       re.IGNORECASE | re.MULTILINE)
_ACCURATE_RE = re.compile(r'^\s*ACCURATE_EXPECTED_VALUES\s+"?\s*true\s*"?\s*$',
                          re.IGNORECASE | re.MULTILINE)


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


def warn_limit(settings, accurate: bool) -> float:
    """The user's limit for this kind of chart (Preferences ▸ Measurement)."""
    key, default = ((ACCURATE_KEY, ACCURATE_DEFAULT_DE) if accurate
                    else (ESTIMATED_KEY, ESTIMATED_DEFAULT_DE))
    try:
        return float(settings.get(key, default))
    except (TypeError, ValueError):
        return default


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


@dataclass
class Verdict:
    flag: object                  # FLAG_NONE / FLAG_RED / FLAG_CONFIRMED / FLAG_LEARNED
    prev_de: "float | None" = None   # CONFIRMED by a re-read: the reading it agreed with
    peer_locs: tuple = ()            # CONFIRMED by similar patches: them, sorted
    like_loc: str = ""               # LEARNED: the confirmed patch it was judged like
    colour_range: str = ""           # flagged: the patch's colour range (RANGES)
    range_k: int = 0                 # flagged: confirmed patches in it, 0..3
    range_locs: tuple = ()           # flagged: the confirmed patches in it, sorted


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

    def __init__(self, white=None, device_ranges=None) -> None:
        self._white = D50_WHITE
        self._device_ranges: "dict[str, str] | None" = None
        self.reset(white, device_ranges=device_ranges)

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
        for the record and for Check & Refine, and never loaded back as
        references: they are worked out again from the readings."""
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
    def _like(self, rng, exp_lab, shift, standout) -> "_Reference | None":
        """The confirmed patch of range *rng* whose error this one is like:
        the closest by expected colour (ΔE*ab, D50), ties by location."""
        best = None
        best_key = None
        s0, s1, s2 = shift[0], shift[1], shift[2]
        e0, e1, e2 = exp_lab[0], exp_lab[1], exp_lab[2]
        for ref, n, u in (self._range_entry(rng)[3] if rng else ()):
            along = s0 * u[0] + s1 * u[1] + s2 * u[2]
            if along < n - SHIFT_TOLERANCE_DE:
                continue
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
                best, best_key = ref, (dist,)
        return best

    def _verdict(self, loc: str, rd: _Reading) -> Verdict:
        """The verdict for a FLAGGED reading, as the references stand now."""
        rng = self.range_of(loc, rd.exp_lab)
        k, locs = self.range_status(rng)
        own = self._active_ref(loc)
        peers = tuple(self.peers_of(loc)) if own is None else ()
        if own is not None or peers:
            # Confirmed stays yellow, whether its range has learned or not.
            # A re-read is named first: it is the stronger proof.
            return Verdict(FLAG_CONFIRMED,
                           prev_de=None if own is None else own.prev_de,
                           peer_locs=peers,
                           colour_range=rng, range_k=k, range_locs=locs)
        if k >= RANGE_CONFIRMATIONS:
            ref = self._like(rng, rd.exp_lab, _sub(rd.meas_lab, rd.exp_lab),
                             rd.standout)
            if ref is not None:
                return Verdict(FLAG_LEARNED, like_loc=ref.loc,
                               colour_range=rng, range_k=k, range_locs=locs)
        return Verdict(FLAG_RED, colour_range=rng, range_k=k, range_locs=locs)

    def judge(self, loc: str, exp_lab, meas_lab, de: float, flagged: bool,
              *, standout: "float | None" = None, live: bool = True,
              strip: "str | None" = None) -> Verdict:
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

        A confirmation (or the loss of one) can change OTHER patches' verdicts
        too; the caller asks :meth:`rejudge` once the whole batch is judged.
        """
        loc = str(loc)
        de = float(de)
        meas_lab = tuple(float(v) for v in meas_lab[:3])
        exp_lab = tuple(float(v) for v in exp_lab[:3])
        prev = self._last.get(loc)
        rd = _Reading(meas_lab, de, bool(flagged), exp_lab,
                      None if standout is None else float(standout),
                      None if strip is None else str(strip))
        was = self._ranges.pop(loc, None)   # classified from this expected colour
        self._set_reading(loc, rd, was)
        own = self._refs.get(loc)
        if not flagged:
            # Read clean now, LIVE: whatever was confirmed about it no longer
            # holds. A repaint from the file only hides it (the limit).
            if live and self._refs.pop(loc, None) is not None:
                self._refs_changed()
            self._verdicts.pop(loc, None)
            return Verdict(FLAG_NONE)
        if (own is not None
                and _norm(_sub(meas_lab, own.meas_lab)) <= SAME_READING_DE):
            pass                          # the same colour once more: confirmed
        elif (live and prev is not None and prev.flagged
                and _norm(_sub(meas_lab, prev.meas_lab)) <= SAME_READING_DE):
            self._refs[loc] = _Reference(
                loc=loc, exp_lab=exp_lab, meas_lab=meas_lab,
                shift=_sub(meas_lab, exp_lab), de=de, prev_de=prev.de,
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
