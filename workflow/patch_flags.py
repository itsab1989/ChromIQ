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

1. **The colour range.** Every patch belongs to one of 13 ranges, from its
   EXPECTED colour classified against the chart's own white (the ``.ti2``'s
   ``APPROX_WHITE_POINT``, D50 without one), so a chart's greys come out as
   greys: a grey when its chroma is under 8 (dark under L* 35, mid to under
   70, light from 70), otherwise its hue sector (``HUE_SECTORS``), with
   pink/rose as what is left over.
2. **A range learns** once three of its CONFIRMED patches lie pairwise at
   least ``RANGE_SPACING_DE`` (ΔE*ab 6, expected colours, D50) apart; the
   largest such set is counted exactly (:func:`spaced_count`). Learned
   patches never count; a confirmed patch read clean drops out.
3. **Then** a later, or EARLIER, red patch of that range is drawn yellow when,
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

Only patches confirmed by a re-read are references; a patch that was itself
judged yellow never is, so the rule cannot drift from one patch to the next.

**Kept with the measurement (#182 K4, Sebastian 5959447807).** The references
are saved beside the ``.ti3`` (``workflow/confirmed_patches.py``) and loaded
back when that measurement is shown again or resumed; a FRESH read starts with
none, because it replaces the readings they were confirmed against.

MEASURED ON KNUT'S REAL CHART (beta 3 run1, 648 patches, i1Pro 2, estimated
expected colours, chart white D65), ``AP_colour_ranges/knut_colour_ranges_measure.py``
of that session's report (the earlier thresholds: ``AF_impl_flag_limits/
flag_rule_knut_data.py``):

* at the default 95, 10 patches are flagged: nine blue and O9 (hue 311°)
  purple. Re-reading every red patch in reading order, the blue range has
  three confirmations ΔE 6 apart only once U16, the last of them, is confirmed
  (every spaced triple among the blues includes U16), so all ten are re-read
  and none is learned. With a 315° blue/purple edge O9 would be blue and U16
  learned; the edge stays at the approved 310°;
* at the old limit 50 (61 flagged with the strip test), 19 are re-read and 42
  are learned;
* the shift and stand-out conditions are the ones measured against simulated
  misreads before the ranges (0 of 430 flagged reached yellow at 95, 4 of
  1,449 at 50, against 32 without the stand-out condition).
"""
from __future__ import annotations

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
    (240.0, 310.0, "blue"),
    (310.0, 325.0, "purple"),
    (325.0, 345.0, "magenta"),
)
RANGES = ("grey_dark", "grey_mid", "grey_light", "pink") + tuple(
    name for _lo, _hi, name in HUE_SECTORS)
#: A range learns once this many of its confirmed patches lie pairwise at
#: least RANGE_SPACING_DE apart (expected colours, ΔE*ab, D50).
RANGE_CONFIRMATIONS = 3
RANGE_SPACING_DE = 6.0

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


@dataclass
class _Reference:
    """A patch confirmed by a re-read: what later patches are judged against."""
    loc: str
    exp_lab: tuple
    meas_lab: tuple
    shift: tuple
    de: float
    prev_de: float
    standout: "float | None"


@dataclass
class Verdict:
    flag: object                  # FLAG_NONE / FLAG_RED / FLAG_CONFIRMED / FLAG_LEARNED
    prev_de: "float | None" = None   # CONFIRMED: the reading it agreed with
    like_loc: str = ""               # LEARNED: the confirmed patch it was judged like
    colour_range: str = ""           # flagged: the patch's colour range (RANGES)
    range_k: int = 0                 # flagged: spaced confirmations in it, 0..3
    range_locs: tuple = ()           # flagged: the confirmed patches in it, sorted


def _sub(a, b):
    return tuple(float(x) - float(y) for x, y in zip(a[:3], b[:3]))


def _norm(v) -> float:
    return math.sqrt(sum(x * x for x in v))


def spaced_count(exp_labs, cap: int = RANGE_CONFIRMATIONS,
                 spacing: float = RANGE_SPACING_DE) -> int:
    """The size of the LARGEST set of these colours that lie pairwise at least
    *spacing* apart (ΔE*ab), counted up to *cap*. Exact, not greedy: a greedy
    pick can take a middle colour that is close to two others which are far
    enough from each other, and then count 2 where 3 exist."""
    pts = [tuple(float(v) for v in p[:3]) for p in exp_labs]
    if not pts or cap <= 0:
        return 0
    n = len(pts)
    far = [[_norm(_sub(pts[i], pts[j])) >= spacing for j in range(n)]
           for i in range(n)]

    def grow(chosen: list, start: int) -> int:
        best = len(chosen)
        if best >= cap:
            return best
        for c in range(start, n):
            if all(far[c][o] for o in chosen):
                best = max(best, grow(chosen + [c], c + 1))
                if best >= cap:
                    return best
        return best

    return grow([], 0)


class FlagJudge:
    """Remembers one measurement session's readings and decides each outline.

    The tab owns one, resets it when a session starts, asks :meth:`judge` for
    every patch it draws and :meth:`rejudge` once per batch of patches. Pure
    logic: no Qt, so the rule is tested on its own.

    *white* is the chart's own white (XYZ, Y = 1) that the colour ranges are
    classified against. It is sticky: :meth:`reset` without a white keeps the
    one it has, so a reset can never fall back to D50 behind the caller's back.
    """

    def __init__(self, white=None) -> None:
        self._white = D50_WHITE
        self.reset(white)

    @property
    def white(self) -> tuple:
        return self._white

    def set_white(self, white) -> None:
        """Take the chart's white without forgetting anything."""
        if white:
            self._white = tuple(float(v) for v in white[:3])
            self._ranges = {}
            self._refs_changed()

    def reset(self, white=None) -> None:
        if white:
            self._white = tuple(float(v) for v in white[:3])
        self._last: "dict[str, _Reading]" = {}
        self._refs: "dict[str, _Reference]" = {}
        #: loc -> the last verdict given for it (flagged readings only).
        self._verdicts: "dict[str, Verdict]" = {}
        #: loc -> colour range, and range -> (k, confirmed locs).
        self._ranges: "dict[str, str]" = {}
        self._status_cache: "dict[str, tuple]" = {}

    @property
    def confirmed(self) -> "list[str]":
        return sorted(self._refs)

    # ---- the colour ranges ---------------------------------------------------
    def range_of(self, loc: str, exp_lab) -> str:
        loc = str(loc)
        r = self._ranges.get(loc)
        if r is None:
            r = self._ranges[loc] = colour_range(exp_lab, self._white)
        return r

    def _refs_changed(self) -> None:
        self._status_cache = {}

    def range_status(self, rng: str) -> "tuple[int, tuple]":
        """``(k, locs)`` for colour range *rng*: the largest number of its
        confirmed patches spaced at least ΔE 6 apart (0..3), and every
        confirmed patch in it, in reading order."""
        hit = self._status_cache.get(rng)
        if hit is None:
            refs = sorted((r for r in self._refs.values()
                           if self.range_of(r.loc, r.exp_lab) == rng),
                          key=lambda r: _loc_key(r.loc))
            hit = (spaced_count([r.exp_lab for r in refs]),
                   tuple(r.loc for r in refs))
            self._status_cache[rng] = hit
        return hit

    def range_learned(self, rng: str) -> bool:
        return self.range_status(rng)[0] >= RANGE_CONFIRMATIONS

    # ---- the memory file -----------------------------------------------------
    def export(self) -> dict:
        """The memory in the schema of ``workflow/confirmed_patches.py``."""
        out: dict = {}
        for loc, ref in self._refs.items():
            out[loc] = {"kind": "confirmed", "de": ref.de, "prev_de": ref.prev_de,
                        "exp_lab": list(ref.exp_lab),
                        "meas_lab": list(ref.meas_lab),
                        "shift": list(ref.shift), "standout": ref.standout}
        for loc, v in self._verdicts.items():
            if (not isinstance(v.flag, bool) and v.flag == FLAG_LEARNED
                    and loc not in out and v.like_loc in self._refs):
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
            self._last[loc] = _Reading(meas_lab, de, True, exp_lab, so)
            self._ranges.pop(loc, None)
            n += 1
        self._refs_changed()
        return n

    # ---- the rule ------------------------------------------------------------
    def _like(self, rng, exp_lab, shift, standout) -> "_Reference | None":
        """The confirmed patch of range *rng* whose error this one is like:
        the closest by expected colour (ΔE*ab, D50), ties by location."""
        best = None
        best_key = None
        for ref in self._refs.values():
            if self.range_of(ref.loc, ref.exp_lab) != rng:
                continue
            n = _norm(ref.shift)
            if n <= 0.0:
                continue
            u = tuple(v / n for v in ref.shift)
            along = sum(a * b for a, b in zip(shift, u))
            side = _norm(tuple(s - along * v for s, v in zip(shift, u)))
            if side > SHIFT_TOLERANCE_DE or along < n - SHIFT_TOLERANCE_DE:
                continue
            if (standout is not None and ref.standout is not None
                    and standout > ref.standout + STANDOUT_MARGIN_DE):
                continue
            key = (_norm(_sub(exp_lab, ref.exp_lab)), _loc_key(ref.loc))
            if best_key is None or key < best_key:
                best, best_key = ref, key
        return best

    def _verdict(self, loc: str, rd: _Reading) -> Verdict:
        """The verdict for a FLAGGED reading, as the references stand now."""
        rng = self.range_of(loc, rd.exp_lab)
        k, locs = self.range_status(rng)
        own = self._refs.get(loc)
        if own is not None:
            # Confirmed stays yellow, whether its range has learned or not.
            return Verdict(FLAG_CONFIRMED, prev_de=own.prev_de,
                           colour_range=rng, range_k=k, range_locs=locs)
        if k >= RANGE_CONFIRMATIONS:
            ref = self._like(rng, rd.exp_lab, _sub(rd.meas_lab, rd.exp_lab),
                             rd.standout)
            if ref is not None:
                return Verdict(FLAG_LEARNED, like_loc=ref.loc,
                               colour_range=rng, range_k=k, range_locs=locs)
        return Verdict(FLAG_RED, colour_range=rng, range_k=k, range_locs=locs)

    def judge(self, loc: str, exp_lab, meas_lab, de: float, flagged: bool,
              *, standout: "float | None" = None, live: bool = True) -> Verdict:
        """The outline for this reading of *loc*, as things stand now.

        *flagged* is the red rule's answer (past the limit and, reading strips
        with the strip test on, an outlier of its strip). *standout* is the
        patch's ΔE above its strip's median, or None without a strip. *live*
        is False for readings repainted from the file: they are remembered as
        the previous reading, but a file read twice is not a second reading,
        so only a live reading can confirm.

        A confirmation (or the loss of one) can change OTHER patches' verdicts
        too; the caller asks :meth:`rejudge` once the whole batch is judged.
        """
        loc = str(loc)
        de = float(de)
        meas_lab = tuple(float(v) for v in meas_lab[:3])
        exp_lab = tuple(float(v) for v in exp_lab[:3])
        prev = self._last.get(loc)
        rd = _Reading(meas_lab, de, bool(flagged), exp_lab,
                      None if standout is None else float(standout))
        self._last[loc] = rd
        self._ranges.pop(loc, None)      # classified from this expected colour
        own = self._refs.get(loc)
        if not flagged:
            # Read clean now: whatever was confirmed about it no longer holds.
            if self._refs.pop(loc, None) is not None:
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
        elif own is not None:
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
        (its range no longer has three spaced confirmations, or no confirmed
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
