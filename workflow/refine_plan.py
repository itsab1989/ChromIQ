"""Which strips Check & Refine offers for re-measuring, and why (#182).

The rules Knut approved on 2026-10-03 (#182 5963903650, on the pictures in
5963737221; rulings 5963360295 and 5960926048 before them):

* **Refinement is always offered** when at least one patch is above the user's
  limit. The old rule "more than three quarters of the strips are flagged, so
  start over" is gone: on a 648-patch chart one patch in six above 2.0 flags
  nearly every strip, and Knut's Good profile (run2) was told "24 of 24 strips,
  start over" with no way to refine.
* **Starting over is advised only when more than half of all patches are above
  the limit**, and even then refinement stays available.
* Two lists, worst first:

  1. "Re-measure these strips first": a strip with a patch that **stands out
     clearly** from the rest of this check (robust outlier: above the median
     plus 6 x 1.4826 x the median absolute deviation of this check's patch
     errors), or a patch that **looks partly read as its neighbour** (its
     measured colour lies on the line between what the profile expects for it
     and what the neighbour measured, an unsteady swipe);
  2. the remaining strips with a patch above the limit.

* A patch a re-read already **confirmed** (the yellow ones, the run's
  ``.confirmed.json``) is not offered again.
* Re-reads are not judged against the previous profile (Knut 5963360295 Q2).

The outlier bar is relative to each check, never a fixed number (Knut's
question 4 in 5963903650, answered in 5963916503): a noisy laser printer gets
a higher bar, a clean inkjet a lower one.

Everything here is pure: no Qt, no files. The window and the saved report both
render from a :class:`RefinePlan`, so they cannot say different things.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from core.strip_utils import letter_to_idx

#: Robust outlier: median + OUTLIER_K x MAD_SCALE x MAD.
OUTLIER_K = 6.0
#: Scales the median absolute deviation to a standard deviation for ordinary
#: (normal) scatter.
MAD_SCALE = 1.4826
#: When more than half of the errors are identical the MAD is 0 and every patch
#: above the median would "stand out". The mean absolute deviation, scaled the
#: same way for normal scatter, takes its place then.
MEAN_AD_SCALE = 1.2533

#: Advise starting over above this share of all patches (strictly greater).
START_OVER_SHARE = 0.5

#: "Partly read as its neighbour": the neighbour must differ from the patch's
#: expected colour by at least this much (Lab), or a mix cannot be told apart.
BLEND_MIN_NEIGHBOUR = 8.0
#: How much of the neighbour is mixed in. At least 15 %: a looser bar flagged
#: Knut's run2 L5 as "partly like L6", and his re-read read L5 the same.
BLEND_T = (0.15, 0.92)
#: How far off the line the measured colour may lie, as a share of the error.
BLEND_MAX_OFF = 0.25

#: profcheck -v2: "[de] n @ LOC: <device> -> <profile Lab> should be <measured Lab>"
_PATCH_LINE = re.compile(
    r"^\s*\[([\d.]+)\]\s+\d+\s+@\s+([A-Za-z0-9]+):\s+[^>]*->\s+"
    r"(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+should be\s+"
    r"(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*$")
_LOC = re.compile(r"^([A-Za-z]+)(\d+)$")
#: The beginnings of every line profcheck prints, so a fragment can be told
#: from a line of its own.
_LINE_STARTS = re.compile(
    r"^\s*(\[[\d.]|No of test patches|Profile check complete|Warning|Error|"
    r"profcheck|Diag|Usage|\[OK\]|\[ERROR\]|\[WARNING\])")


def mend_split_lines(text: str) -> str:
    """Put back together a profcheck line the capture cut in two.

    `ArgyllRunner` emits whatever a pipe read ended on at once, newline or not,
    because Argyll's prompts end without one and must be seen. So a long
    profcheck line can arrive as two "lines". Knut's own run2 report
    (Quality_Check_6, beta 5) holds one::

        [0.047433] 162 @ B26: 0.80000000 0.400000
        00 1.00000000 -> 51.564012 21.834236 -27.948463 should be 51.60 ...

    and the prototype saw W26 cut the same way on screen. Read as two lines,
    B26 is lost to the check. A line is joined to the one before when the one
    before is an unfinished patch or summary line and this one does not begin
    like any line profcheck prints.
    """
    out: "list[str]" = []
    for line in text.splitlines():
        if out and not _LINE_STARTS.match(line) and (
                _unfinished(out[-1])
                or (_is_result_line(out[-1]) and _CONTINUES.match(line))):
            out[-1] += line
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


#: A fragment that can only be the rest of a number: a cut inside the last
#: value leaves a line that looks finished ("... -7") before it ("385683").
#: No line profcheck prints begins with a digit or a point.
_CONTINUES = re.compile(r"^[0-9.]")


def _is_result_line(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("[") or s.startswith("Profile check complete")


def _unfinished(line: str) -> bool:
    s = line.lstrip()
    if s.startswith("["):
        return _PATCH_LINE.match(line) is None or not line.rstrip()[-1:].isdigit()
    if s.startswith("Profile check complete"):
        return "avg." not in s or not s.rstrip()[-1:].isdigit()
    return False


@dataclass
class Patch:
    """One patch of the check: its location, error and (when printed) colours."""
    loc: str
    de: float
    strip: str
    pos: "int | None" = None
    pred: "tuple[float, float, float] | None" = None   # what the profile predicts
    meas: "tuple[float, float, float] | None" = None   # what was measured


def _split_loc(loc: str) -> "tuple[str, int | None]":
    m = _LOC.match(loc)
    if m:
        return m.group(1).upper(), int(m.group(2))
    letters = re.match(r"^([A-Za-z]+)", loc)
    return (letters.group(1).upper() if letters else loc.upper()), None


def parse_patches(log_text: str,
                  patch_errors: "list[tuple[str, float]] | None" = None
                  ) -> "list[Patch]":
    """Every patch of a profcheck -v2 output, split lines mended first.

    *patch_errors* (``ProfcheckResult.patch_errors``) is the fallback for a
    patch whose colours could not be read: the rules that need only the error
    still apply to it.
    """
    out: "dict[str, Patch]" = {}
    for line in mend_split_lines(log_text or "").splitlines():
        m = _PATCH_LINE.match(line)
        if not m:
            continue
        loc = m.group(2)
        strip, pos = _split_loc(loc)
        v = [float(x) for x in m.groups()[2:]]
        out[loc] = Patch(loc, float(m.group(1)), strip, pos,
                         (v[0], v[1], v[2]), (v[3], v[4], v[5]))
    for loc, de in patch_errors or ():
        if loc not in out:
            strip, pos = _split_loc(loc)
            out[loc] = Patch(loc, float(de), strip, pos)
    return list(out.values())


def _median(xs: "list[float]") -> float:
    s = sorted(xs)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def outlier_limit(des: "list[float]") -> float:
    """The error above which a patch "stands out clearly" in this check.

    Median plus six robust spreads. When the MAD is 0 (more than half of the
    errors identical), the scaled mean absolute deviation is the spread; when
    that is 0 too, every error is the same and nothing stands out.
    """
    if not des:
        return math.inf
    med = _median(des)
    spread = MAD_SCALE * _median([abs(d - med) for d in des])
    if spread <= 0:
        spread = MEAN_AD_SCALE * sum(abs(d - med) for d in des) / len(des)
    if spread <= 0:
        return math.inf
    return med + OUTLIER_K * spread


def blend_partner(p: Patch, by_loc: "dict[str, Patch]") -> str:
    """The neighbour *p* looks partly read as, or "".

    Its measured colour lies on the line from what the profile predicts for it
    towards what the neighbour measured: between 15 % and 92 % of the way, and
    no further off that line than a quarter of its error.
    """
    if p.pred is None or p.meas is None or p.pos is None:
        return ""
    e = [m - q for m, q in zip(p.meas, p.pred)]
    e_len = math.sqrt(sum(x * x for x in e))
    if e_len <= 0:
        return ""
    best = ("", math.inf)
    for npos in (p.pos - 1, p.pos + 1):
        n = by_loc.get(f"{p.strip}{npos}")
        if n is None or n.meas is None:
            continue
        d = [m - q for m, q in zip(n.meas, p.pred)]
        dd = sum(x * x for x in d)
        if dd < BLEND_MIN_NEIGHBOUR ** 2:
            continue
        t = sum(a * b for a, b in zip(e, d)) / dd
        if not BLEND_T[0] <= t <= BLEND_T[1]:
            continue
        off = math.sqrt(sum((a - t * b) ** 2 for a, b in zip(e, d)))
        if off <= BLEND_MAX_OFF * e_len and off < best[1]:
            best = (n.loc, off)
    return best[0]


#: Why a strip is offered.
OUTLIER, BLEND, OVER = "outlier", "blend", "over"


@dataclass
class StripAdvice:
    strip: str
    kind: str                 # OUTLIER | BLEND | OVER
    patch: str                # the patch the reason is about
    de: float                 # that patch's error
    n_over: int               # this strip's patches above the limit (not confirmed)
    neighbour: str = ""       # for BLEND


@dataclass
class RefinePlan:
    threshold: float
    n_total: int
    n_over: int
    outlier_limit: float
    start_over: bool
    de_name: str = "ΔE"
    first: "list[StripAdvice]" = field(default_factory=list)
    rest: "list[StripAdvice]" = field(default_factory=list)
    confirmed_skipped: "list[str]" = field(default_factory=list)

    @property
    def offered(self) -> "list[StripAdvice]":
        return self.first + self.rest

    @property
    def pct_over(self) -> int:
        return round(100 * self.n_over / max(1, self.n_total))

    @property
    def has_choice(self) -> bool:
        """Both lists hold strips, so the user picks which to re-measure."""
        return bool(self.first) and bool(self.rest)

    def chosen(self, first_only: bool = True) -> "list[tuple[str, float]]":
        """(strip, worst error) to re-measure, in CHART order (A, B, C ...).

        The default (Knut, 5963903650 Q3) is the strips listed first; with no
        first list, every strip above the limit.
        """
        picked = self.first if (first_only and self.first) else self.offered
        return sorted(((a.strip, a.de) for a in picked),
                      key=lambda x: letter_to_idx(x[0]))


def recommends_start_over(n_above: int, n_total: int) -> bool:
    """More than half of ALL patches above the limit (strictly greater)."""
    return n_total > 0 and n_above / n_total > START_OVER_SHARE


def build_plan(patches: "list[Patch]", threshold: float,
               confirmed: "set[str] | frozenset[str]" = frozenset(),
               de_name: str = "ΔE") -> RefinePlan:
    """Decide what the result window offers. See the module docstring."""
    des = [p.de for p in patches]
    limit = outlier_limit(des)
    n_over = sum(1 for p in patches if p.de > threshold)
    plan = RefinePlan(threshold, len(patches), n_over, limit,
                      recommends_start_over(n_over, len(patches)), de_name)
    by_loc = {p.loc: p for p in patches}
    strips: "dict[str, list[Patch]]" = {}
    for p in patches:
        if p.de <= threshold:
            continue
        if p.loc in confirmed:
            plan.confirmed_skipped.append(p.loc)
            continue
        strips.setdefault(p.strip, []).append(p)
    for strip, over in strips.items():
        over.sort(key=lambda p: p.de, reverse=True)
        worst = over[0]
        advice = None
        for p in over:                          # worst first within the strip
            partner = blend_partner(p, by_loc)
            if partner:
                advice = StripAdvice(strip, BLEND, p.loc, p.de, len(over),
                                     partner)
                break
        # A clear outlier that is the strip's worst patch is the stronger
        # reason to give, even when a smaller patch also looks blended.
        if worst.de > limit and (advice is None or advice.patch != worst.loc):
            advice = StripAdvice(strip, OUTLIER, worst.loc, worst.de, len(over))
        if advice is None:
            advice = StripAdvice(strip, OVER, worst.loc, worst.de, len(over))
        (plan.rest if advice.kind == OVER else plan.first).append(advice)
    plan.first.sort(key=lambda a: (-a.de, letter_to_idx(a.strip)))
    plan.rest.sort(key=lambda a: (-a.de, letter_to_idx(a.strip)))
    plan.confirmed_skipped.sort(
        key=lambda loc: (letter_to_idx(_split_loc(loc)[0]),
                         _split_loc(loc)[1] or 0))
    return plan


#: profcheck's own name for the formula, in its summary line.
_FORMULA_IN_SUMMARY = (("CIEDE2000", "ΔE00"), ("CIE94", "ΔE94"))
_FORMULA_FLAG = {"-k": "ΔE00", "-c": "ΔE94", "": "ΔE76"}


def de_name_for(log_text: str, de_formula: str = "") -> str:
    """The name every number in the window carries: ΔE00, ΔE94 or ΔE76.

    profcheck's summary line says which formula it used ("errors(CIEDE2000)"),
    which is the truth of the check that ran; the flag it was given is the
    fallback when there is no summary to read.
    """
    m = re.search(r"Profile check complete, errors\s*\(([^)]*)\)", log_text or "")
    if m:
        for key, name in _FORMULA_IN_SUMMARY:
            if key in m.group(1):
                return name
        return "ΔE76"
    if "Profile check complete, errors:" in (log_text or ""):
        return "ΔE76"
    return _FORMULA_FLAG.get(de_formula or "", "ΔE76")


# ---------------------------------------------------------------------------
# The words, once, for the window and the saved report alike
# ---------------------------------------------------------------------------

@dataclass
class PlanText:
    """Every line the result window shows, translated, in the order shown.

    Rich text (``<b>``) where the window bolds a lead-in; the report strips the
    tags. Empty strings and lists mean "not shown".
    """
    numbers: str = ""
    over: str = ""
    start_over: str = ""
    first_head: str = ""
    first_rows: "list[tuple[str, str]]" = field(default_factory=list)
    rest_head: str = ""
    rest_items: "list[str]" = field(default_factory=list)
    confirmed: str = ""
    choice_first: str = ""
    choice_all: str = ""
    order: str = ""


def rest_item(a: StripAdvice, de: str = "") -> str:
    """"H  ΔE00 4.98 (20)": the strip, its worst patch's error under the
    formula's name (one formula, named on every number), how many above."""
    name = f"{de} " if de else ""
    return f"{a.strip:<2} {name}{a.de:4.2f} ({a.n_over})"


def plan_text(plan: RefinePlan, avg: "float | None",
              peak: "float | None") -> PlanText:
    """The window's lines for *plan* (M-CR-STRIPS, M-CR-START-OVER)."""
    from core.i18n import tr
    from workflow import measurement_messages as mm
    de, limit = plan.de_name, plan.threshold
    t = PlanText()
    if avg is not None:
        t.numbers = tr(mm._CR_NUMBERS).format(
            de=de, avg=avg, peak=peak if peak is not None else avg)
    if plan.n_over == 0:
        t.over = tr(mm._CR_OVER_NONE).format(de=de, limit=limit)
    elif plan.n_over == 1:
        t.over = tr(mm._CR_OVER_ONE).format(total=plan.n_total, de=de,
                                            limit=limit)
    else:
        t.over = tr(mm._CR_OVER_MANY).format(
            n=plan.n_over, total=plan.n_total, pct=plan.pct_over, de=de,
            limit=limit)
    if plan.start_over:
        t.start_over = tr(mm._CR_START_OVER).format(
            n=plan.n_over, total=plan.n_total, pct=plan.pct_over)
    if plan.first:
        t.first_head = tr(mm._CR_FIRST_HEAD)
        for a in plan.first:
            if a.kind == BLEND:
                why = tr(mm._CR_WHY_BLEND).format(
                    patch=a.patch, de=de, value=a.de, neighbour=a.neighbour,
                    strip=a.strip)
            else:
                why = tr(mm._CR_WHY_OUTLIER).format(patch=a.patch, de=de,
                                                    value=a.de)
            if a.n_over > 1:
                why += " " + tr(mm._CR_N_IN_STRIP).format(n=a.n_over)
            t.first_rows.append((tr(mm._CR_STRIP).format(strip=a.strip), why))
    if plan.rest:
        n = len(plan.rest)
        if plan.first:
            head = mm._CR_REST_HEAD_MORE_ONE if n == 1 else mm._CR_REST_HEAD_MORE_MANY
        else:
            head = mm._CR_REST_HEAD_ONE if n == 1 else mm._CR_REST_HEAD_MANY
        t.rest_head = tr(head).format(n=n, de=de, limit=limit)
        t.rest_items = [rest_item(a, de) for a in plan.rest]
    if plan.confirmed_skipped:
        key = (mm._CR_CONFIRMED_ONE if len(plan.confirmed_skipped) == 1
               else mm._CR_CONFIRMED_MANY)
        t.confirmed = tr(key).format(patches=", ".join(plan.confirmed_skipped))
    if plan.has_choice:
        n1 = len(plan.first)
        t.choice_first = (tr(mm._CR_CHOICE_FIRST_ONE) if n1 == 1 else
                          tr(mm._CR_CHOICE_FIRST_MANY).format(n=n1))
        t.choice_all = tr(mm._CR_CHOICE_ALL).format(n=len(plan.offered))
    if plan.offered:
        t.order = tr(mm._CR_ORDER)
    return t
