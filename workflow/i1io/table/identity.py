# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""THE ROW IDENTITY CHECK (the new i1iO chart layout, 25 Nov 2026): does a row look like itself?

WHY. The row placement check (``placement.py``) looks at edges and times. A row one whole patch off
its place has edges exactly where they belong, and a sheet of another chart with the same grid has
too: both were accepted, with patches 66 to 77 dE00 wrong, and a row read patch by patch has no
check of its place at all beyond the arm's arrival. This check looks at the COLOURS and at nothing
else: the row's measured colours against the chart's own expected ones by RANK correlation, so it
needs no profile, no paper and no printer.

THE SCORES (Spearman, the mean over L*, and a* / b* where the measured ones spread by SPREAD_AB or
more, 10th to 90th percentile):

* OWN: the row against itself;
* SHIFTED: the row against itself moved by one and by two patches, either way (the best);
* OTHER: the row against the neighbour rows and the same row of the other pages (the best; it only
  names what lies there, it decides nothing).

JUDGED only when all hold: at least MIN_PATCHES patches; the expected L* spread by MIN_SPREAD_L or
more; at least MIN_DIFFERENT_L different expected L* (to 2 units); at most half of the row of one
colour (padding); the expected row does not resemble itself shifted (at most SELF_MAX). Not a
calibration chart (the caller says so). A row read in part (Refine, Continue) is judged on the
patches that were read, at their own places; a shift counts only pairs inside that part. Anything
else: not judged, and why, in the logs, never silently.

WHAT IT DECIDES (the thresholds are fixed):

* ``shifted`` (THE VETO): the best SHIFTED is at least VETO_SCORE and beats OWN by VETO_MARGIN: the
  row lies one or two patches off. It is refused, always; no answer switches this off;
* ``ask``: OWN under ASK_BELOW, or the measured L* spread by less than BLANK_SPREAD_L (blank paper
  or the bed: the ranks of its noise say nothing, and one row in twenty would pass by chance;
  a judged row's expected L* always spread by MIN_SPREAD_L or more): these are not the colours of this row. The person is asked, at most
  once per page, whether the right piece lies on the table;
* ``ok`` otherwise.

Independent of the placement check: it reads no edges and no times; the two share the readings, the
aims and the chart. It does not see a shift of less than a patch, rows of under MIN_PATCHES patches,
calibration charts, rows of few colours, ink sets without expected colours.

Measured before it was built on recorded rows of a real table (kept privately): right rows never
refused and never asked, every row of a wrong sheet asked, every row moved by one patch refused. Standard library and this package only; nothing here is sent to the table.
"""
from __future__ import annotations

import math

#: THE SHIP SWITCH (no user option): False turns the check off.
ROW_IDENTITY_CHECK = True

MIN_PATCHES = 12
MIN_SPREAD_L = 20.0
MIN_DIFFERENT_L = 8
SELF_MAX = 0.5
SPREAD_AB = 8.0
SHIFTS = (-2, -1, 1, 2)
VETO_SCORE = 0.6
VETO_MARGIN = 0.25
ASK_BELOW = 0.5
#: a measured row whose L* spread by less than this is blank paper or the bed, whatever its ranks
BLANK_SPREAD_L = 5.0
#: fewer pairs than this say nothing about a shift (a row read in scattered parts)
MIN_PAIRS = 8
#: another row is named as what lies there only from this score
NAME_OTHER_FROM = 0.6

#: the reasons of a dropped row (strips, patch by patch, and the person's "End")
REASON_STRIP = "strip_row_not_in_its_place"
REASON_SPOT = "row_not_in_its_place"
REASON_ENDED = "row_not_of_this_piece"
#: 4.3.69 (item 76, ``page_blend.py``): the rows of a page hold their neighbours' colours: the sheet
#: lies across from where it was aimed; every row of the page read on those aims is dropped
REASON_PAGE = "page_not_where_aimed"
#: every reason a row is dropped for by this check (nothing of it may be kept)
REASONS = (REASON_STRIP, REASON_SPOT, REASON_ENDED, REASON_PAGE)


def _ranks(v: "list[float]") -> "list[float]":
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        r = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def spearman(a: "list[float]", b: "list[float]") -> float:
    """The rank correlation of two lists (equal values share their rank); 0 without a spread."""
    n = len(a)
    if n < 2 or n != len(b):
        return 0.0
    ra, rb = _ranks(a), _ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    saa = sum((x - ma) ** 2 for x in ra)
    sbb = sum((y - mb) ** 2 for y in rb)
    if saa <= 0 or sbb <= 0:
        return 0.0
    return sab / math.sqrt(saa * sbb)


def _percentile(v: "list[float]", q: float) -> float:
    s = sorted(v)
    pos = (len(s) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _spread(v: "list[float]") -> float:
    return _percentile(v, 90.0) - _percentile(v, 10.0)


def _channels(measured: "list[tuple]") -> "list[int]":
    return [0] + [c for c in (1, 2) if _spread([m[c] for m in measured]) >= SPREAD_AB]


def _score(measured: dict, expected: dict, shift: int, channels) -> "float | None":
    """The measured colour at position i against the expected one at i + shift, over the
    positions both have; None with too few pairs (MIN_PAIRS) to say anything."""
    pairs = [(measured[i], expected[i + shift]) for i in sorted(measured) if i + shift in expected]
    if len(pairs) < MIN_PAIRS:
        return None
    return sum(spearman([m[c] for m, _e in pairs], [e[c] for _m, e in pairs])
               for c in channels) / len(channels)


def why_not_judged(expected: dict) -> str:
    """Why a row with these expected colours ({position: Lab}) is not judged; "" when it is."""
    n = len(expected)
    if n < MIN_PATCHES:
        return f"{n} patches, fewer than {MIN_PATCHES}"
    cols = [expected[i] for i in sorted(expected)]
    L = [c[0] for c in cols]
    spread = _spread(L)
    if spread < MIN_SPREAD_L:
        return f"the expected lightness spreads by {spread:.0f}, less than {MIN_SPREAD_L:.0f}"
    different = len({int(round(v / 2.0)) for v in L})
    if different < MIN_DIFFERENT_L:
        return f"{different} different expected lightnesses, fewer than {MIN_DIFFERENT_L}"
    alike = max(sum(1 for d in cols if all(abs(a - b) < 1e-6 for a, b in zip(c, d)))
                for c in cols)
    if alike > n / 2.0:
        return f"{alike} of its {n} patches are one colour"
    ch = _channels(cols)
    self_ = max((s for s in (_score(expected, expected, k, ch) for k in SHIFTS)
                 if s is not None), default=0.0)
    if self_ > SELF_MAX:
        return f"the row resembles itself shifted ({self_:.2f})"
    return ""


def judge(measured: "dict[str, tuple]", row: "list[str]", expected: "dict[str, tuple]",
          others: "list[tuple[object, list[str]]] | None" = None) -> dict:
    """The verdict on one row. *measured*: ``{location: Lab}`` of what was read; *row*: every
    location of the row in the chart's order; *expected*: the chart's ``{location: Lab}``;
    *others*: ``[(what, locations in order)]`` of rows that may lie there instead. Never raises:
    a failure is "not judged" with its reason. Returns ``{"judged", "why", "verdict", "own",
    "shifted", "shift", "self", "patches", "other", "other_score"}``."""
    out = {"judged": False, "why": "", "verdict": None, "own": None, "shifted": None,
           "shift": None, "patches": len(measured), "other": None, "other_score": None}
    try:
        if not ROW_IDENTITY_CHECK:
            out["why"] = "switched off"
            return out
        if not expected:
            out["why"] = "the chart names no expected colours"
            return out
        pos = {loc: i for i, loc in enumerate(row)}
        m = {pos[loc]: lab for loc, lab in measured.items()
             if loc in pos and all(math.isfinite(v) for v in lab)}
        e = {i: expected[row[i]] for i in m if row[i] in expected}
        if len(e) < len(m):
            out["why"] = "a patch of the row has no expected colour"
            return out
        out["patches"] = len(m)
        why = why_not_judged(e)
        if why:
            out["why"] = why
            return out
        ch = _channels([m[i] for i in sorted(m)])
        own = _score(m, e, 0, ch)
        best, at = None, None
        for k in SHIFTS:
            s = _score(m, e, k, ch)
            if s is not None and (best is None or s > best):
                best, at = s, k
        other, oscore = None, None
        for what, locs in others or []:
            o = {i: expected[locs[i]] for i in m if i < len(locs) and locs[i] in expected}
            if len(o) < MIN_PAIRS:
                continue
            s = _score(m, o, 0, ch)
            if s is not None and (oscore is None or s > oscore):
                other, oscore = what, s
        out.update(judged=True, own=own, shifted=best, shift=at, other_score=oscore)
        if _spread([m[i][0] for i in m]) < BLANK_SPREAD_L:
            # nothing is printed there: neither itself, nor itself shifted, nor another row
            out["blank"] = True
            out["verdict"] = "ask"
            return out
        if oscore is not None and oscore >= NAME_OTHER_FROM and (own is None or oscore > own):
            out["other"] = other
        if best is not None and best >= VETO_SCORE and best - own >= VETO_MARGIN:
            out["verdict"] = "shifted"
        elif own < ASK_BELOW:
            out["verdict"] = "ask"
        else:
            out["verdict"] = "ok"
    except Exception as exc:      # noqa: BLE001 - never a reason to lose a row
        out.update(judged=False, verdict=None, why=f"could not be judged ({type(exc).__name__})")
    return out


def record(v: dict) -> dict:
    """What a row's record and the logs keep of the verdict: scores, never a colour."""
    def r(x):
        return None if x is None else round(float(x), 3)
    return {"judged": v["judged"], "why": v["why"], "verdict": v["verdict"], "own": r(v["own"]),
            "shifted": r(v["shifted"]), "shift": v["shift"], "patches": v["patches"],
            "other": v["other"], "other_score": r(v["other_score"])}


def summary(v: dict) -> str:
    """One line for the detailed table log and the app log."""
    if not v["judged"]:
        return f"row identity: not judged: {v['why']}"

    def n(x):
        return "none" if x is None else f"{x:.2f}"
    words = {"ok": "the row looks like itself",
             "shifted": "THE ROW LOOKS LIKE ITSELF "
                        f"{abs(v['shift'] or 0)} PATCH(ES) OFF, refused",
             "ask": "THESE ARE NOT THE COLOURS OF THIS ROW"}[v["verdict"]]
    tail = f"; it looks like {v['other']}" if v["other"] else ""
    if v.get("blank"):
        tail = "; one lightness throughout, as blank paper"
    return (f"row identity: {words} (own {n(v['own'])}, shifted {n(v['shifted'])} at "
            f"{v['shift']}, other {n(v['other_score'])}, {v['patches']} patches){tail}")
