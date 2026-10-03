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

**B2. Learning** (Knut 5956831467: *"if those patches have larger error than
those previously flagged for the same color range, then one should assume that
these errors are not a misread and automatically flag these patches with
yellow"*). Once a patch has been confirmed yellow, a LATER flagged patch is
drawn yellow straight away when all three of these hold against a confirmed
patch:

1. **the same colour range**: its expected L*a*b* is within
   ``SIMILAR_COLOUR_DE`` (ΔE*ab 15) of the confirmed patch's expected L*a*b*;
2. **the same kind of error, as large or larger**: its measured-minus-expected
   shift points the same way (it strays at most ``SHIFT_TOLERANCE_DE``, ΔE 10,
   sideways from the confirmed patch's shift) and reaches at least as far
   (no more than ΔE 10 shorter along it). A printer that cannot reach a colour
   falls short of it in one direction, and further the more vivid the colour
   asked for; a misread lands anywhere;
3. **it does not stand out from its strip much more** than the confirmed patch
   did from its own: its ΔE above its strip's median is at most
   ``STANDOUT_MARGIN_DE`` (ΔE 10) more than the confirmed patch's was. This is
   what keeps a smudge or a slipped reading red even in a colour range where
   real differences are known: such a reading spikes far above its neighbours.
   Patch by patch there is no strip, and the first two conditions are the rule.

Only patches confirmed by a re-read are references; a patch that was itself
judged yellow never is, so the rule cannot drift from one patch to the next.

**Kept with the measurement (#182 K4, Sebastian 5959447807).** The references
are saved beside the ``.ti3`` (``workflow/confirmed_patches.py``) and loaded
back when that measurement is shown again or resumed; a FRESH read starts with
none, because it replaces the readings they were confirmed against.

THE THRESHOLDS WERE CHOSEN ON KNUT'S REAL CHART (beta 3 run1, 648 patches,
i1Pro 2, estimated expected colours) and the measurements are kept in
``AF_impl_flag_limits/flag_rule_knut_data.py`` of that session's report:

* at the new default 95, 10 patches are flagged; re-reading the first one
  (A17) and confirming it turns 8 of the other 9 yellow by this rule, and the
  9th (O9, a different colour range) stays red;
* at the old limit 50 (72 flagged, 61 with the strip test), confirming every
  red patch as it comes would leave 35 of the 61 to be judged yellow by the
  rule and 26 to be re-read;
* simulated misreads (one patch of a strip given a random other patch's
  colour, 3,000 trials) reached yellow 0 times in 430 flagged at limit 95 and
  4 times in 1,449 at limit 50, against 32 / 1,449 without condition 3. A
  15 → 20 colour range turned one more real patch yellow and no more
  misreads; 10 lost one. A sideways tolerance of 10 matches what Knut wrote
  ("shift vectors within ΔE 10").
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

#: The ArgyllCMS thresholds the two defaults follow.
ESTIMATED_DEFAULT_DE = 95.0
ACCURATE_DEFAULT_DE = 30.0
ESTIMATED_KEY = "patch_read_warn_de_estimated"
ACCURATE_KEY = "patch_read_warn_de_accurate"

#: Two readings of one patch this close (ΔE*ab between the two MEASURED
#: colours) are the same reading. Stricter than comparing the two ΔE values,
#: which could agree while the colours do not; it implies they agree within 3.
SAME_READING_DE = 3.0
#: The learning rule's three numbers; see the module text for where they come
#: from.
SIMILAR_COLOUR_DE = 15.0
SHIFT_TOLERANCE_DE = 10.0
STANDOUT_MARGIN_DE = 10.0

#: What the preview draws. ``False``/``True`` keep their old meaning (no
#: outline / red), so every caller that only asks "is it flagged?" still works;
#: the two yellow kinds are ints the preview tells apart.
FLAG_NONE = False
FLAG_RED = True
FLAG_CONFIRMED = 2
FLAG_LEARNED = 3

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


@dataclass
class _Reading:
    meas_lab: tuple
    de: float
    flagged: bool


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


def _sub(a, b):
    return tuple(float(x) - float(y) for x, y in zip(a[:3], b[:3]))


def _norm(v) -> float:
    return math.sqrt(sum(x * x for x in v))


class FlagJudge:
    """Remembers one measurement session's readings and decides each outline.

    The tab owns one, resets it when a session starts, and asks :meth:`judge`
    for every patch it draws. Pure logic: no Qt, so the rule is tested on
    its own.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._last: "dict[str, _Reading]" = {}
        self._refs: "dict[str, _Reference]" = {}
        #: loc -> the confirmed patch it was last judged like (for the file).
        self._learned: "dict[str, str]" = {}

    @property
    def confirmed(self) -> "list[str]":
        return sorted(self._refs)

    def export(self) -> dict:
        """The memory in the schema of ``workflow/confirmed_patches.py``."""
        out: dict = {}
        for loc, ref in self._refs.items():
            out[loc] = {"kind": "confirmed", "de": ref.de, "prev_de": ref.prev_de,
                        "exp_lab": list(ref.exp_lab),
                        "meas_lab": list(ref.meas_lab),
                        "shift": list(ref.shift), "standout": ref.standout}
        for loc, like in self._learned.items():
            if loc not in out and like in self._refs:
                out[loc] = {"kind": "learned", "like": like}
        return out

    def load(self, patches: dict) -> int:
        """Take the CONFIRMED patches of a stored memory as references.

        Learned entries are not loaded: they are judged again from the
        references, so a stored guess can never become a reference. Each
        confirmed patch is also remembered as the last reading of its patch,
        flagged, which is what it was. Returns how many were loaded.
        """
        n = 0
        for loc, e in (patches or {}).items():
            if not isinstance(e, dict) or e.get("kind") != "confirmed":
                continue
            try:
                exp_lab = tuple(float(v) for v in e["exp_lab"][:3])
                meas_lab = tuple(float(v) for v in e["meas_lab"][:3])
                de = float(e.get("de", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            if len(exp_lab) != 3 or len(meas_lab) != 3:
                continue
            prev = e.get("prev_de")
            so = e.get("standout")
            self._refs[str(loc)] = _Reference(
                loc=str(loc), exp_lab=exp_lab, meas_lab=meas_lab,
                shift=_sub(meas_lab, exp_lab), de=de,
                prev_de=None if prev is None else float(prev),
                standout=None if so is None else float(so))
            self._last[str(loc)] = _Reading(meas_lab, de, True)
            n += 1
        return n

    def _like(self, exp_lab, shift, standout) -> "_Reference | None":
        best = None
        best_d = None
        for ref in self._refs.values():
            d_col = _norm(_sub(exp_lab, ref.exp_lab))
            if d_col > SIMILAR_COLOUR_DE:
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
            if best_d is None or d_col < best_d:
                best, best_d = ref, d_col
        return best

    def judge(self, loc: str, exp_lab, meas_lab, de: float, flagged: bool,
              *, standout: "float | None" = None, live: bool = True) -> Verdict:
        """The outline for this reading of *loc*.

        *flagged* is the red rule's answer (past the limit and, reading strips
        with the strip test on, an outlier of its strip). *standout* is the
        patch's ΔE above its strip's median, or None without a strip. *live*
        is False for readings repainted from the file: they are remembered as
        the previous reading, but a file read twice is not a second reading,
        so only a live reading can confirm.
        """
        loc = str(loc)
        de = float(de)
        meas_lab = tuple(float(v) for v in meas_lab[:3])
        exp_lab = tuple(float(v) for v in exp_lab[:3])
        prev = self._last.get(loc)
        self._last[loc] = _Reading(meas_lab, de, bool(flagged))
        own = self._refs.get(loc)
        self._learned.pop(loc, None)
        if not flagged:
            # Read clean now: whatever was confirmed about it no longer holds.
            self._refs.pop(loc, None)
            return Verdict(FLAG_NONE)
        if own is not None and _norm(_sub(meas_lab, own.meas_lab)) <= SAME_READING_DE:
            return Verdict(FLAG_CONFIRMED, prev_de=own.prev_de)
        if (live and prev is not None and prev.flagged
                and _norm(_sub(meas_lab, prev.meas_lab)) <= SAME_READING_DE):
            self._refs[loc] = _Reference(
                loc=loc, exp_lab=exp_lab, meas_lab=meas_lab,
                shift=_sub(meas_lab, exp_lab), de=de, prev_de=prev.de,
                standout=standout)
            return Verdict(FLAG_CONFIRMED, prev_de=prev.de)
        if own is not None:
            # Re-read to a clearly different colour: it is not confirmed now.
            self._refs.pop(loc, None)
        ref = self._like(exp_lab, _sub(meas_lab, exp_lab), standout)
        if ref is not None:
            self._learned[loc] = ref.loc
            return Verdict(FLAG_LEARNED, like_loc=ref.loc)
        return Verdict(FLAG_RED)
