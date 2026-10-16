#!/usr/bin/env python3
"""Demo data that triggers every combination of the two misread tests
(#182, 4.3.5 beta 8, UMM 10.12), for the on-screen verifier
``scripts/drive_b8_matrix.py``.

    python scripts/b8_matrix_demo.py <out folder>     # writes the charts

Knut, #182 6196667833: *"Make sure all combination of messages, errors and
neighbour check combinations are verified using demo data on screen on the
app, where the demo data is designed to catch every single combination"*.

THE CHART. One RGB chart made by ChromIQ's own layout engine
(``workflow.layout_engine.chart.build_chart``): ten strips A to J of 21
patches. Every strip holds the same slots, so a slot names a group of
patches whose EXPECTED colours lie close together (within a few ΔE*ab) and
whose device RGB puts them in one colour range:

=========  =====================  ==========  ==================================
slot       group                  range       what it is for
=========  =====================  ==========  ==================================
1, 2       G-a  L*65 a*-45 b*35   green       the patches under test and their
                                              clean neighbours
3          G-b  G-a + b*10        green       a second neighbourhood within
                                              the radius of G-a (row 21, 13)
4, 5       G2   L*30 a*-30 b*20   green       far from G: teaches the range
6, 7       B    L*40 a*10 b*-45   blue        a second group
8          X    next to G-a       yellow-green another range, same colour
9          E    L*40..70 a*20 b*40 orange     the radius edges: A=E0,
                                              B=+15.00, C=+15.01, D=+30.00,
                                              E=+30.01 (L*)
10, 11     R    L*50 a*55 b*35    red         the reopen scenario
12..21     fillers (greys, cyan, magenta, yellow), far from every group
=========  =====================  ==========  ==================================

The groups are more than 30 apart (the largest Colour-neighbour radius), so
patches of different groups never meet in the neighbour check or as
similar patches. Readings are the expected colour plus an ERROR vector in
L*a*b* (D50, the tab's own ``icc_info.xyz_to_lab``); the ΔE*ab handed over is
that vector's length, so every threshold is hit exactly.

THE SCENARIOS (:func:`scenarios`). Each is one measurement session of its
own, read strip by strip (or patch by patch) through the engine's signals,
with the expected outline and card of each patch it checks, taken from the
specification (UMM 10.12, its 35-row table, and §M). Nothing here decides a
verdict: the app does, on screen.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STRIPS = "ABCDEFGHIJ"
PER_STRIP = 21

D50 = (0.96422, 1.0, 0.82521)       # workflow.icc_info._D50


# ---- colour helpers (the tab's own white) ------------------------------------
def _finv(t: float) -> float:
    return t ** 3 if t ** 3 > 216.0 / 24389.0 else (116.0 * t - 16.0) / (24389.0 / 27.0)


def lab_to_xyz100(lab) -> tuple:
    L, a, b = (float(v) for v in lab)
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0
    return tuple(_finv(f) * w * 100.0 for f, w in zip((fx, fy, fz), D50))


def xyz100_to_lab(xyz) -> tuple:
    from workflow.icc_info import xyz_to_lab
    return xyz_to_lab(tuple(float(v) / 100.0 for v in xyz[:3]))


def add(a, b):
    return tuple(float(x) + float(y) for x, y in zip(a, b))


def norm(v) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v))


# ---- the chart design ------------------------------------------------------------
CENTRES = {
    "G": ((65.0, -45.0, 35.0), "green"),
    "G2": ((30.0, -30.0, 20.0), "green"),
    "B": ((40.0, 10.0, -45.0), "blue"),
    "X": ((65.0, -45.0, 35.0), "yellow_green"),
    "E": ((40.0, 20.0, 40.0), "orange"),
    "R": ((50.0, 55.0, 35.0), "red"),
    "GL": ((95.0, 0.0, 0.0), "grey_light"),
    "GD": ((12.0, 0.0, 0.0), "grey_dark"),
    "C": ((70.0, -30.0, -40.0), "cyan"),
    "M": ((55.0, 70.0, -30.0), "magenta"),
    "Y": ((88.0, -5.0, 80.0), "yellow"),
}
#: slot (1..21) -> (group, sub-slot)
SLOTS = {1: ("G", 0), 2: ("G", 1), 3: ("Gb", 0), 4: ("G2", 0), 5: ("G2", 1),
         6: ("B", 0), 7: ("B", 1), 8: ("X", 0), 9: ("E", 0), 10: ("R", 0),
         11: ("R", 1), 12: ("GL", 0), 13: ("GL", 1), 14: ("GD", 0),
         15: ("GD", 1), 16: ("C", 0), 17: ("C", 1), 18: ("M", 0),
         19: ("M", 1), 20: ("Y", 0), 21: ("Y", 1)}
#: The radius edges, column 9 (L* added to E0), per strip.
E_OFFSETS = {"A": 0.0, "B": 15.0, "C": 15.01, "D": 30.0, "E": 30.01,
             "F": 0.6, "G": 1.2, "H": 1.8, "I": 2.4, "J": 3.0}


def strip_offset(i: int) -> tuple:
    """A small offset per strip, so no two patches share an expected colour:
    L* -2.4..2.4, a* -0.9 / 0.9."""
    return (((i % 5) - 2) * 1.2, ((i // 5) * 2 - 1) * 0.9, 0.0)


def expected_lab(loc: str) -> tuple:
    """The designed expected L*a*b* of a location (before the file rounds it)."""
    s, n = loc[0], int(loc[1:])
    i = STRIPS.index(s)
    group, k = SLOTS[n]
    if group == "E":
        c = CENTRES["E"][0]
        return (c[0] + E_OFFSETS[s], c[1], c[2])
    if group == "Gb":
        base = add(CENTRES["G"][0], (0.0, 0.0, 10.0))
    elif group == "X":
        base = add(CENTRES["G"][0], (0.3, 0.3, 0.6))
    else:
        base = CENTRES[group][0]
    off = strip_offset(i)
    if group in ("GL", "GD", "C", "M", "Y"):
        off = tuple(v / 2.0 for v in off)
    return add(add(base, off), (0.0, 0.0, 0.5 * k))


def range_wanted(loc: str) -> str:
    group = SLOTS[int(loc[1:])][0]
    return CENTRES["G" if group == "Gb" else group][1]


def _rgb_for(lab, rng) -> tuple:
    """Device RGB (0..100) whose targen estimate is nearest *lab* while its
    colour range (``chart_device_ranges``' rule) is *rng*."""
    from workflow.patch_flags import colour_range_of_rgb, targen_estimate_xyz
    best, best_d = None, 1e9
    steps = [x * 2.5 for x in range(41)]
    for r in steps:
        for g in steps:
            for b in steps:
                rgb = (r, g, b)
                x = targen_estimate_xyz(rgb)
                d = norm(tuple(p - q for p, q in zip(
                    xyz100_to_lab(tuple(v * 100.0 for v in x)), lab)))
                if d < best_d and colour_range_of_rgb(rgb) == rng:
                    best, best_d = rgb, d
    return best


def all_locs() -> "list[str]":
    return [f"{s}{n}" for s in STRIPS for n in range(1, PER_STRIP + 1)]


def write_ti1(path: Path) -> None:
    rgb_cache: dict = {}
    lines = ['CTI1   ', '',
             'DESCRIPTOR "Argyll Calibration Target chart information 1"',
             'ORIGINATOR "ChromIQ b8 matrix demo (scripts/b8_matrix_demo.py)"',
             'APPROX_WHITE_POINT "95.106486 100.000000 108.844025"',
             'COLOR_REP "RGB"', '', 'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
             'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ',
             'END_DATA_FORMAT', '', f'NUMBER_OF_SETS {len(all_locs())}',
             'BEGIN_DATA']
    for i, loc in enumerate(all_locs()):
        group = SLOTS[int(loc[1:])][0]
        key = "G" if group == "Gb" else group
        if key not in rgb_cache:
            rgb_cache[key] = _rgb_for(CENTRES[key][0], CENTRES[key][1])
        rgb = rgb_cache[key]
        xyz = lab_to_xyz100(expected_lab(loc))
        lines.append(f"{i + 1} " + " ".join(f"{v:.5f}" for v in rgb) + " "
                     + " ".join(f"{v:.6f}" for v in xyz) + " ")
    lines.append("END_DATA")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def read_ti2_xyz(ti2: Path) -> "dict[str, tuple]":
    from workflow import printer_calibration as pc
    fields, rows, _kw = pc.read_table(ti2)
    out = {}
    for sid, row in rows.items():
        out[str(row.get("SAMPLE_LOC", sid)).strip('"')] = tuple(
            float(row[f]) for f in ("XYZ_X", "XYZ_Y", "XYZ_Z"))
    return out


def build_charts(out: Path) -> dict:
    """The chart, once per chart type: ``estimated/`` (the plain chart),
    ``accurate/`` (its .ti2 says ACCURATE_EXPECTED_VALUES), ``cal/`` (a
    calibration chart is the one in a project's cal folder). A verification
    is the plain chart judged against a prediction (the driver's
    LiveExpected). Returns ``{kind: ti2 path}``."""
    from workflow.layout_engine.chart import build_chart
    from workflow.patch_flags import chart_device_ranges
    base_dir = out / "estimated"
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir(parents=True)
    stem = base_dir / "b8-matrix"
    write_ti1(stem.with_suffix(".ti1"))
    build_chart(stem.with_suffix(".ti1"), stem, instrument="i1", paper="A4",
                randomize=False, seed=1, project="b8-matrix")
    ti2 = stem.with_suffix(".ti2")
    ranges = chart_device_ranges(ti2)
    bad = {loc: (ranges.get(loc), range_wanted(loc)) for loc in all_locs()
           if ranges.get(loc) != range_wanted(loc)}
    assert not bad, f"colour ranges not as designed: {bad}"
    charts = {"estimated": ti2}
    for kind, folder in (("accurate", "accurate"), ("calibration", "cal")):
        d = out / folder
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(base_dir, d)
        charts[kind] = d / ti2.name
    acc = charts["accurate"]
    text = acc.read_text(encoding="latin-1")
    text = text.replace('COLOR_REP "RGB"',
                        'COLOR_REP "RGB"\nACCURATE_EXPECTED_VALUES "true"', 1)
    acc.write_text(text, encoding="latin-1")
    charts["verification"] = ti2
    return charts


# ---- the readings ------------------------------------------------------------
U = (0.0, 0.0, 20.0)          # past the limit of 15 (ΔE*ab 20.00)
V = (0.0, 0.0, 10.0)          # under it, a neighbour suspect among clean ones


def noise(loc: str) -> tuple:
    """A clean reading's small error, the same every time for a location."""
    h = sum(ord(c) * (i + 3) for i, c in enumerate(loc))
    return (((h % 7) - 3) * 0.08, (((h // 7) % 7) - 3) * 0.08,
            (((h // 49) % 7) - 3) * 0.08)


def again(err) -> tuple:
    """The same colour read again (0.41 away, within the tolerance of 3)."""
    return add(err, (0.3, 0.2, -0.2))


def clean(*locs) -> dict:
    return {loc: noise(loc) for loc in locs}


def e(x=0.0, y=0.0, z=0.0) -> tuple:
    return (float(x), float(y), float(z))


# ---- the expected cards, in the words of workflow/measurement_messages -----------
NUM = "\x00NUM\x00"           # any ΔE*ab figure (the neighbour check's own)


def ab(v) -> str:
    return NUM if v is None else f"ΔE*ab {float(v):.2f}"


KIND_KEY = {"estimated": "_CARD_KIND_ESTIMATED",
            "accurate": "_CARD_KIND_ACCURATE",
            "verification": "_CARD_KIND_VERIFICATION",
            "calibration": "_CARD_KIND_CALIBRATION"}


def M(name: str, **kw) -> str:
    from workflow import measurement_messages as mm
    return getattr(mm, name).format(**kw)


def kind_phrase(kind: str) -> str:
    return M(KIND_KEY[kind])


def fmt_locs(locs) -> str:
    locs = list(locs)
    return ", ".join(locs[:3]) + ("…" if len(locs) > 3 else "")


def one_stop(text: str) -> str:
    return text.replace("….", "…")


LIKE = "\x00LIKE:"


def like_re(like) -> str:
    """The confirmed patch a learned patch is judged like: the closest of
    its range's confirmed patches that it is like (an implementation choice
    the specification leaves open), so any of *like* is accepted."""
    if isinstance(like, str):
        return like
    return LIKE + "|".join(like) + "\x00"


def DE(err) -> float:
    """The ΔE*ab of a reading with this error, at two decimals."""
    return round(norm(err) + 1e-9, 2)


class Ctx:
    """What a scenario's cards depend on: chart type, limits, kind of read."""

    def __init__(self, kind="estimated", pe=15.0, nb=7.0, mode="profiling"):
        self.kind, self.pe, self.nb, self.mode = kind, pe, nb, mode

    # -- the pieces the specification names --
    def limit(self, loc, de, fenced=False):
        return M("_CARDP_LIMIT_FENCED" if fenced else "_CARDP_LIMIT",
                 de=ab(de), limit=ab(self.pe), kind=kind_phrase(self.kind),
                 loc=loc)

    def limit_yellow(self, loc, de):
        return M("_CARDP_LIMIT_YELLOW", de=ab(de), limit=ab(self.pe),
                 kind=kind_phrase(self.kind), loc=loc)

    def nb_text(self, name, loc):
        return M(name, d=NUM, n=NUM, limit=ab(self.nb),
                 kind=kind_phrase(self.kind), loc=loc)

    def real_lines(self, loc):
        if self.mode == "later":
            out = [M("_CARD_LATER_PROFILE_YELLOW_1") + " "
                   + M("_CARD_LATER_PROFILE_YELLOW_2")]
        elif self.mode == "verify":
            out = [" ".join(M(f"_CARD_VERIFY_YELLOW_{i}") for i in (1, 2, 3, 4))]
        else:
            out = ["A real difference this printer and paper cannot reach, "
                   "not a misread.", "Keep it for the profile."]
        return out + [M("_CARD_YELLOW_NO_NEED", loc=loc)]

    def red_ending(self, loc):
        if self.mode == "later":
            return [" ".join(M(f"_CARD_LATER_PROFILE_{i}", loc=loc)
                             for i in range(1, 7)),
                    "Same value after a re-read:",
                    M("_CARD_LATER_PROFILE_SAME_1") + " "
                    + M("_CARD_LATER_PROFILE_SAME_2")]
        if self.mode == "verify":
            first = " ".join(M(f"_CARD_VERIFY_RED_{i}") for i in (1, 2, 3))
            same = M("_CARD_VERIFY_SAME_1") + " " + M("_CARD_VERIFY_SAME_2")
        else:
            first = ("Either a misread, or a colour this printer and paper "
                     "cannot reach.")
            same = "it is real, keep it for the profile."
        return [first, M("_CARD_RED_READ_AGAIN", loc=loc),
                "Same value after a re-read:", same]

    def same_line(self):
        if self.mode == "verify":
            return M("_CARD_VERIFY_SAME_1") + " " + M("_CARD_VERIFY_SAME_2")
        if self.mode == "later":
            return (M("_CARD_LATER_PROFILE_SAME_1") + " "
                    + M("_CARD_LATER_PROFILE_SAME_2"))
        return "it is real, keep it for the profile."

    @staticmethod
    def range_block(rng, k, locs, learned_line=True):
        from workflow import measurement_messages as mm
        out = [M("_CARD_RANGE", range=mm.RANGE_NAMES[rng])]
        if k >= 3 and learned_line:
            out.append(M("_CARD_RANGE_CONFIRMED_LEARNED"))
        elif k >= 1:
            out.append(M("_CARD_RANGE_SO_FAR", k=k))
        if locs and k < 3:
            out.append(one_stop(M("_CARD_RANGE_SAME", locs=fmt_locs(locs))))
        return out

    # -- the rows of 10.12.5 --
    def row2(self, loc, de, rng="green", k=0, locs=(), fenced=False):
        return ([M("_CARDP_LIMIT_HEAD"), self.limit(loc, de, fenced)]
                + self.range_block(rng, k, locs) + self.red_ending(loc))

    def row3(self, loc, de, prevs, nb=False):
        prevs = list(prevs)
        out = [M("_CARD_UNSETTLED_HEAD"),
               M("_CARDP_UNSETTLED_DE_ONE" if len(prevs) <= 1
                 else "_CARDP_UNSETTLED_DE", loc=loc, de=ab(de),
                 prevs=", ".join(ab(x) for x in prevs))]
        if nb:
            out.append(self.nb_text("_CARDP_NB_ALSO", loc))
        out += [M("_CARDP_UNSETTLED_TWO" if len(prevs) <= 1
                  else "_CARDP_UNSETTLED_MANY", n=len(prevs) + 1,
                  limit=ab(self.pe), kind=kind_phrase(self.kind)),
                M("_CARD_UNSETTLED_3", loc=loc) + " " + M("_CARD_UNSETTLED_4")]
        return out

    def row4(self, loc, de, prev, rng="green", k=1, locs=(), nb=False,
             pe=True):
        out = ["Yellow outline: confirmed by a re-read",
               M("_CARDP_CONFIRMED", loc=loc, de=ab(de), prev=ab(prev))]
        if pe:
            out.append(self.limit_yellow(loc, de))
        if nb:
            out.append(self.nb_text("_CARDP_NB_YELLOW", loc))
        out += self.real_lines(loc)
        if rng:
            out += self.range_block(rng, k, locs)
        return out

    def row5(self, loc, de, peers, rng="green", k=2, locs=(), nb_peers=()):
        out = [M("_CARD_PEER_1"),
               one_stop(M("_CARD_PEER_2_ONE" if len(peers) == 1
                          else "_CARD_PEER_2", locs=fmt_locs(peers))),
               self.limit_yellow(loc, de)]
        if nb_peers:
            out += [one_stop(M("_CARDS_NB_PEER_ONE" if len(nb_peers) == 1
                               else "_CARDS_NB_PEER", locs=fmt_locs(nb_peers))),
                    self.nb_text("_CARDP_NB_YELLOW", loc)]
        return out + self.real_lines(loc) + self.range_block(rng, k, locs)

    def row6(self, loc, de, like, locs, rng="green", nb_peers=(),
             landed=False):
        from workflow import measurement_messages as mm
        out = [f"Yellow outline: judged like patch {like_re(like)}",
               self.limit_yellow(loc, de)]
        if nb_peers:
            out += [one_stop(M("_CARDS_NB_PEER_ONE" if len(nb_peers) == 1
                               else "_CARDS_NB_PEER", locs=fmt_locs(nb_peers))),
                    self.nb_text("_CARDP_NB_YELLOW", loc)]
        out += [M("_CARD_RANGE", range=mm.RANGE_NAMES[rng]),
                one_stop(M("_CARD_RANGE_SAME", locs=fmt_locs(locs))),
                M("_CARD_RANGE_LEARNED_1") + " " + M("_CARD_RANGE_LEARNED_2")]
        if landed:
            out.append(M("_CARD_RANGE_LANDED_1") + " " + M("_CARD_RANGE_LANDED_2"))
        out += [M("_CARD_VERIFY_LEARNED" if self.mode == "verify"
                  else "_CARD_RANGE_LEARNED_3") + " "
                + M("_CARD_RANGE_LEARNED_4", loc=loc),
                M("_CARD_YELLOW_NO_NEED", loc=loc)]
        return out

    def row7(self, loc, prev):
        return [M("_CARD_GREEN_HEAD"),
                M("_CARDP_GREEN_LIMIT", de=ab(prev), loc=loc),
                M("_CARD_GREEN_END")]

    def row8(self, loc):
        out = [self.nb_text("_CARDP_NB_RED", loc),
               M("_CARD_NB_MISREAD_S", loc=loc)]
        if self.mode == "later":
            out.append(" ".join(M(f"_CARD_LATER_PROFILE_{i}") for i in (2, 3, 4)))
        return out + [M("_CARDS_NB_REREAD", loc=loc),
                      "Same value after a re-read:", self.same_line()]

    def row9(self, loc, de, prev):
        return (["Yellow outline: confirmed by a re-read",
                 M("_CARDP_CONFIRMED", loc=loc, de=ab(de), prev=ab(prev)),
                 self.nb_text("_CARDP_NB_YELLOW", loc)]
                + self.real_lines(loc))

    def row10(self, loc, nb_peers, n8=False):
        out = [M("_CARD_PEER_1"),
               one_stop(M("_CARDS_NB_PEER_ONE" if len(nb_peers) == 1
                          else "_CARDS_NB_PEER", locs=fmt_locs(nb_peers))),
               self.nb_text("_CARDP_NB_YELLOW", loc)]
        if n8:
            out.append(M("_CARDS_PE_CORRECTED"))
        return out + self.real_lines(loc)

    def row11(self, loc, prev):
        return [M("_CARD_GREEN_HEAD"), M("_CARDP_GREEN_NB", de=ab(prev), loc=loc),
                M("_CARD_GREEN_END")]

    def row12(self, loc, de, rng="green", k=0, locs=()):
        return ([M("_CARDP_LIMIT_HEAD"), self.limit(loc, de),
                 self.nb_text("_CARDP_NB_ALSO", loc)]
                + self.range_block(rng, k, locs)
                # N2 without its first sentence: the red ending asks for
                # the re-read (Basti, 2026-10-16, item 10)
                + [M("_CARDS_NB_REREAD_OTHERS")] + self.red_ending(loc))

    def row13(self, loc, de, nb_peers, rng="green", k=0, locs=()):
        return ([M("_CARDP_LIMIT_HEAD"), self.limit(loc, de),
                 M("_CARDS_NB_PEER_PE_RED", loc=loc, locs=fmt_locs(nb_peers))]
                + self.range_block(rng, k, locs) + self.red_ending(loc))

    def row21(self, loc, peers=(), like=""):
        if like:
            n3 = M("_CARDS_PE_LEARNED_NB_RED", loc=loc, like=like_re(like))
        else:
            n3 = one_stop(M("_CARDS_PE_PEER_NB_RED_ONE" if len(peers) == 1
                            else "_CARDS_PE_PEER_NB_RED", loc=loc,
                            locs=fmt_locs(peers)))
        return ([M("_CARDP_LIMIT_HEAD"), n3,
                 self.nb_text("_CARDP_NB_ALSO", loc),
                 M("_CARDS_NB_REREAD_OTHERS")] + self.red_ending(loc))


#: Sentences that must be on no card since beta 8 (UMM 10.12).
GONE = ["can turn patch", "not similar patches or its colour range",
        "Read alike in other strips"]
#: Never on a card that has no outline.
OUTLINE_WORDS = ["Red outline", "Yellow outline", "Green outline"]


def chk(case, loc, outline, card=None, absent=(), pe="", nb="", note=""):
    """One expectation: *outline* red / yellow / green / none, *card* the
    sentences in order, *absent* what must not be on it; *pe* / *nb* the
    intended input (each test triggered or not on the last reading:
    "y" / "n" / "" not checked)."""
    absent = list(absent)
    if card is not None and M("_CARDS_NB_REREAD_OTHERS") in card:
        # rows 12, 21, 22: the whole N2 must not be there too, or the card
        # says "Read patch … again" twice (Basti, 2026-10-16, item 10)
        absent.append(M("_CARDS_NB_REREAD", loc=loc))
    return {"case": case, "loc": loc, "outline": outline,
            "card": None if card is None else list(card),
            "absent": list(absent),
            "pe": pe, "nb": nb, "note": note}


def S(sid, title, steps, checks, *, kind="estimated", pe=15.0, nb=7.0,
      radius=None, tol=3.0, strip_test=False, nb_on=True, mode="profiling",
      pbp=False, disk=False, summary=None, after=None, photo=True):
    return {"id": sid, "title": title, "steps": steps, "checks": checks,
            "kind": kind, "pe": pe, "nb": nb,
            "radius": (15.0 if kind == "estimated" else 30.0)
            if radius is None else radius,
            "tol": tol, "strip_test": strip_test, "nb_on": nb_on, "mode": mode,
            "pbp": pbp, "disk": disk, "summary": summary, "after": after or [],
            "photo": photo}


def scenarios() -> "list[dict]":  # noqa: C901 — a table, one entry per case
    c = Ctx()
    L = []
    LIM = M("_CARDP_LIMIT_HEAD")
    RANGE = "Colour range:"
    NBR = "Similar patches read in other strips"      # N2
    YEL = "Yellow outline"
    RED_ = "Red outline"

    # ---- row 1: nothing triggered ---------------------------------------------
    L.append(S("S01", "row 1: under the limit, not a suspect", [
        ("strip", "A", {"A1": e(z=5)}), ("strip", "C", {"C1": e(z=3.5)}),
        ("strip", "D", {"D1": e(z=4)})],
        [chk(1, "A1", "none", [], OUTLINE_WORDS, pe="n", nb="n")]))
    # ---- row 2 --------------------------------------------------------------
    L.append(S("S02", "row 2: past the limit alone, range 0 of 3", [
        ("strip", "A", {"A1": U})],
        [chk(2, "A1", "red", c.row2("A1", 20), [YEL, "of 3 confirmations"],
             pe="y", nb="n")]))
    L.append(S("S02b", "row 2 with 1 of 3 (A4 confirmed); row 4", [
        ("strip", "A", {"A4": U}), ("strip", "C", {"C1": U}),
        ("strip", "A", {"A4": again(U)})],
        [chk(2, "C1", "red", c.row2("C1", 20, k=1, locs=["A4"]), [YEL],
             pe="y", nb="n"),
         chk(4, "A4", "yellow", c.row4("A4", DE(again(U)), 20.0, k=1, locs=["A4"]),
             [RED_], pe="y", nb="n")]))
    L.append(S("S02c", "row 2 with 2 of 3 (A4, B4 confirmed)", [
        ("strip", "A", {"A4": U}), ("strip", "B", {"B4": e(y=1, z=20)}),
        ("strip", "C", {"C1": U}),
        ("strip", "A", {"A4": again(U)}),
        ("strip", "B", {"B4": again(e(y=1, z=20))})],
        [chk(2, "C1", "red", c.row2("C1", 20, k=2, locs=["A4", "B4"]), [YEL],
             pe="y", nb="n")]))
    # B4 is alike A4 (errors 1.00 apart) but G2 patches of strips A and B are
    # within the radius: they are similar patches before the re-reads.
    L.append(S("S02d", "row 2 in a learned range: off in another way", [
        ("strip", "A", {"A4": U}), ("strip", "B", {"B5": U}),
        ("strip", "C", {"C4": U}),
        ("strip", "E", {"E1": e(y=20)})],
        [chk(2, "E1", "red",
             [LIM, c.limit("E1", 20), M("_CARD_RANGE", range="green"),
              M("_CARD_RANGE_RED_LEARNED_1"), "points another way"]
             + c.red_ending("E1"), [YEL], pe="y", nb="n"),
         chk(5, "A4", "yellow",
             c.row5("A4", 20, ["B5", "C4"], k=3, locs=[]), [RED_],
             pe="y", nb="n",
             note="three similar patches teach the range (12.1: a peer "
                  "counts towards the three confirmations)")]))
    # ---- row 3: readings disagree -------------------------------------------
    L.append(S("S03", "row 3: re-read past the limit, unlike the first", [
        ("strip", "A", {"A1": U}), ("strip", "A", {"A1": e(z=-20)})],
        [chk(3, "A1", "red", c.row3("A1", 20, [20]), [YEL, LIM], pe="y",
             nb="n")]))
    L.append(S("S03b", "row 3, three readings that disagree; then a 4th like "
               "the 1st (T2: same as ANY earlier reading)", [
        ("strip", "A", {"A1": U}), ("strip", "A", {"A1": e(z=-20)}),
        ("strip", "A", {"A1": e(y=20)}), ("check", "3-many"),
        ("strip", "A", {"A1": again(U)})],
        [chk(3, "A1", "red", c.row3("A1", 20, [20, 20]), [YEL], pe="y",
             nb="n", note="at step 'check 3-many'"),
         chk(4, "A1", "yellow", c.row4("A1", DE(again(U)), 20, k=1, locs=["A1"]),
             [RED_], pe="y", nb="n")]))
    # ---- row 5: similar patches, the patch error limit -----------------------
    L.append(S("S05", "row 5: one similar patch (other strip)", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=0.5))})],
        [chk(5, "A1", "yellow", c.row5("A1", 20, ["B1"], k=2,
                                       locs=["A1", "B1"]),
             [RED_, NBR], pe="y", nb="n"),
         chk(5, "B1", "yellow", c.row5("B1", 20.01, ["A1"], k=2,
                                       locs=["A1", "B1"]),
             [RED_], pe="y", nb="n")]))
    L.append(S("S05b", "row 5: four similar patches (first three then …)", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=0.5))}),
        ("strip", "C", {"C1": add(U, e(y=0.5))}),
        ("strip", "D", {"D1": add(U, e(x=-0.5))}),
        ("strip", "E", {"E1": add(U, e(y=-0.5))})],
        [chk(5, "A1", "yellow", c.row5("A1", 20, ["B1", "C1", "D1", "E1"],
                                       k=3, locs=[]), [RED_], pe="y", nb="n")]))
    L.append(S("S05c", "row 5: two similar patches", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=0.5))}),
        ("strip", "C", {"C1": add(U, e(y=0.5))})],
        [chk(5, "A1", "yellow", c.row5("A1", 20, ["B1", "C1"], k=3, locs=[]),
             [RED_], pe="y", nb="n")]))
    # ---- row 6: learned ------------------------------------------------------
    learn_by_reread = [
        ("strip", "A", {"A4": U}), ("strip", "A", {"A4": again(U)}),
        ("strip", "C", {"C5": e(x=8, z=20)}),
        ("strip", "C", {"C5": again(e(x=8, z=20))}),
        ("strip", "G", {"G4": e(x=-8, z=20)}),
        ("strip", "G", {"G4": again(e(x=-8, z=20))})]
    # A4, C5, G4: errors 8 apart, so not similar patches of each other; each
    # confirmed by its own re-read.
    L.append(S("S06", "row 6: learned (range taught by three re-reads)",
               learn_by_reread + [("strip", "E", {"E1": e(z=24)})],
               [chk(6, "E1", "yellow", c.row6("E1", 24, ["A4", "C5", "G4"],
                                              ["A4", "C5", "G4"]),
                    [RED_], pe="y", nb="n")]))
    L.append(S("S06b", "row 6: range taught by similar patches", [
        ("strip", "A", {"A4": U}), ("strip", "B", {"B5": U}),
        ("strip", "C", {"C4": U}), ("strip", "E", {"E1": e(z=24)})],
        [chk(6, "E1", "yellow", c.row6("E1", 24, ["A4", "B5", "C4"], ["A4", "B5", "C4"]),
             [RED_], pe="y", nb="n")]))
    L.append(S("S06c", "range threshold: 2 confirmations do not teach", [
        ("strip", "A", {"A4": U}), ("strip", "A", {"A4": again(U)}),
        ("strip", "C", {"C5": e(x=8, z=20)}),
        ("strip", "C", {"C5": again(e(x=8, z=20))}),
        ("strip", "E", {"E1": e(z=24)})],
        [chk(2, "E1", "red", c.row2("E1", 24, k=2, locs=["A4", "C5"]),
             [YEL], pe="y", nb="n")]))
    L.append(S("S06d", "row 6, the size test's waiver (landed)", [
        ("strip", "A", {"A1": e(z=30)}), ("strip", "B", {"B1": e(x=8, z=30)}),
        ("strip", "C", {"C1": e(x=-8, z=30)}),
        ("strip", "A", {"A1": again(e(z=30))}),
        ("strip", "B", {"B1": again(e(x=8, z=30))}),
        ("strip", "C", {"C1": again(e(x=-8, z=30))}),
        ("strip", "E", {"E2": e(z=18)})],
        [chk(6, "E2", "yellow", c.row6("E2", 18, ["A1", "B1", "C1"], ["A1", "B1", "C1"],
                                       landed=True), [RED_], pe="y", nb="n")]))
    # ---- row 7 ---------------------------------------------------------------
    L.append(S("S07", "row 7: re-read under the limit", [
        ("strip", "A", {"A1": U}), ("strip", "A", {"A1": noise("A1")})],
        [chk(7, "A1", "green", c.row7("A1", 20), [RED_, YEL], pe="n",
             nb="n")]))
    # ---- the neighbour check -------------------------------------------------
    nbrs = clean("C1", "D1", "E1", "F1")
    L.append(S("S08", "row 8: a neighbour suspect", [
        ("strip", "A", {"A1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]})],
        [chk(8, "A1", "red", c.row8("A1"), [YEL, LIM, RANGE], pe="n", nb="y")],
        summary=["_SUM_NB_RED_ONE:A1"]))
    L.append(S("S09", "row 9: neighbour suspect, its re-read the same", [
        ("strip", "A", {"A1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": again(V)})],
        [chk(9, "A1", "yellow", c.row9("A1", DE(again(V)), 10),
             [RED_, "would be red for being", RANGE], pe="n", nb="y",
             note="12.5 row 9 names no range block")],
        summary=["_SUM_NB_NONE", "_SUM_NB_KEPT_ONE"]))
    L.append(S("S10", "row 10: two neighbour suspects alike, other strips", [
        ("strip", "A", {"A1": V}), ("strip", "J", {"J1": add(V, e(x=0.5))}),
        ("strip", "C", {"C1": nbrs["C1"]}), ("strip", "D", {"D1": nbrs["D1"]}),
        ("strip", "B", clean("B1", "B2")), ("strip", "G", clean("G1", "G2")),
        ("strip", "I", clean("I1", "I2"))],
        [chk(10, "A1", "yellow", c.row10("A1", ["J1"]), [RED_, RANGE, LIM],
             pe="n", nb="y"),
         chk(10, "J1", "yellow", c.row10("J1", ["A1"]), [RED_, RANGE],
             pe="n", nb="y")],
        summary=["_SUM_NB_NONE"]))
    L.append(S("S10b", "row 10: two similar patches (plural)", [
        ("strip", "A", {"A1": V}), ("strip", "E", {"E1": add(V, e(x=0.5))}),
        ("strip", "J", {"J1": add(V, e(y=0.5))}),
        ("strip", "B", clean("B1", "B2")), ("strip", "C", clean("C1", "C2")),
        ("strip", "D", clean("D1", "D2")), ("strip", "F", clean("F1", "F2")),
        ("strip", "G", clean("G1", "G2")), ("strip", "H", clean("H1", "H2")),
        ("strip", "I", clean("I1", "I2"))],
        [chk(10, "A1", "yellow", c.row10("A1", ["E1", "J1"]), [RED_, RANGE],
             pe="n", nb="y")]))
    L.append(S("S11", "row 11: neighbour suspect, re-read clean", [
        ("strip", "A", {"A1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": noise("A1")})],
        [chk(11, "A1", "green", c.row11("A1", 10), [RED_, YEL], pe="n",
             nb="n")]))
    # ---- both tests ----------------------------------------------------------
    L.append(S("S12", "row 12: past the limit and a suspect", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]})],
        [chk(12, "A1", "red", c.row12("A1", 20), [YEL], pe="y", nb="y")],
        summary=["_SUM_NB_RED_ONE:A1"]))
    L.append(S("S12b", "row 12 with 1 of 3 confirmations in the range", [
        ("strip", "B", {"B4": U}), ("strip", "B", {"B4": again(U)}),
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]})],
        [chk(12, "A1", "red", c.row12("A1", 20, k=1, locs=["B4"]), [YEL],
             pe="y", nb="y")]))
    L.append(S("S13", "row 13: P past the limit + suspect; Q suspect only, "
               "alike", [
        ("strip", "A", {"A1": e(z=16.5)}), ("strip", "J", {"J1": e(z=14.0)}),
        ("strip", "C", {"C1": nbrs["C1"]}), ("strip", "D", {"D1": nbrs["D1"]}),
        ("strip", "B", clean("B1", "B2")), ("strip", "G", clean("G1", "G2")),
        ("strip", "I", clean("I1", "I2"))],
        [chk(13, "A1", "red", c.row13("A1", 16.5, ["J1"]), [YEL], pe="y",
             nb="y"),
         chk(10, "J1", "yellow", c.row10("J1", ["A1"]), [RED_, RANGE],
             pe="n", nb="y")],
        summary=["_SUM_NB_NONE"]))
    L.append(S("S14", "row 14: first NB only, re-read past the limit and no "
               "longer a suspect (the neighbours changed before)", [
        ("strip", "A", {"A1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("check", "first suspect"),
        ("strip", "B", {"B1": e(z=14), "B2": e(z=14)}),
        ("strip", "F", {"F1": e(z=14), "F2": e(z=14)}),
        ("strip", "A", {"A1": U, "A2": e(z=14)})],
        [chk(8, "A1", "red", c.row8("A1"), [YEL], pe="n", nb="y",
             note="at step 'first suspect'"),
         chk(14, "A1", "red", c.row2("A1", 20), [YEL, "Neighbour check.)"],
             pe="y", nb="n")]))
    L.append(S("S15", "row 15: readings disagree, still a suspect", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": e(y=20)})],
        [chk(15, "A1", "red", c.row3("A1", 20, [20], nb=True), [YEL],
             pe="y", nb="y")]))
    nb10 = {loc: e(z=10) for loc in ("C1", "D1", "E1", "F1")}
    L.append(S("S16", "row 16: readings disagree, no longer a suspect", [
        ("strip", "C", {"C1": nb10["C1"]}), ("strip", "D", {"D1": nb10["D1"]}),
        ("strip", "E", {"E1": nb10["E1"]}), ("strip", "A", {"A1": U}),
        ("check", "first both"), ("strip", "A", {"A1": e(y=16)})],
        [chk(12, "A1", "red", c.row12("A1", 20), [YEL], pe="y", nb="y",
             note="at step 'first both'"),
         chk(16, "A1", "red", c.row3("A1", 16, [20]), [YEL, "Neighbour check.)"],
             pe="y", nb="n")]))
    L.append(S("S17", "row 17 (impossible): an unsettled suspect is no similar "
               "patch, and nobody's peer", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": e(y=20)}),
        ("strip", "J", {"J1": add(e(y=20), e(x=0.5))}),
        ("strip", "G", clean("G1", "G2")), ("strip", "I", clean("I1", "I2"))],
        [chk(17, "A1", "red", c.row3("A1", 20, [20], nb=True),
             [YEL, NBR, "read in another strip"], pe="y", nb="y"),
         chk(17, "J1", "red", c.row12("J1", 20.01), [YEL, "another strip"],
             pe="y", nb="y")]))
    L.append(S("S18", "row 18: one re-read confirms both tests", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": again(U)})],
        [chk(18, "A1", "yellow", c.row4("A1", DE(again(U)), 20, k=1, locs=["A1"],
                                        nb=True), [RED_], pe="y", nb="y")],
        summary=["_SUM_NB_NONE", "_SUM_NB_KEPT_ONE"]))
    gb14 = {loc: e(z=14) for loc in ("C3", "D3", "E3")}
    L.append(S("S21", "row 21: PE confirmed by a similar patch, NB red", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"], "C3": gb14["C3"]}),
        ("strip", "D", {"D1": nbrs["D1"], "D3": gb14["D3"]}),
        ("strip", "E", {"E1": nbrs["E1"], "E3": gb14["E3"]}),
        ("strip", "B", {"B3": add(U, e(x=0.5))})],
        [chk(21, "A1", "red", c.row21("A1", ["B3"]),
             [YEL, "That is more than the patch error limit", RANGE],
             pe="y", nb="y"),
         chk(21, "B3", "red", c.row2("B3", 20.01, k=1, locs=["A1"]),
             [YEL, "read in another strip"], pe="y", nb="n",
             note="Q: P is in doubt (NB red), so never Q's similar patch; "
                  "P teaches the range (12.1)")],
        summary=["_SUM_NB_RED_ONE:A1"]))
    L.append(S("S21b", "row 21 with two similar patches", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"], "C3": gb14["C3"]}),
        ("strip", "D", {"D1": nbrs["D1"], "D3": gb14["D3"]}),
        ("strip", "E", {"E1": nbrs["E1"], "E3": gb14["E3"]}),
        ("strip", "B", {"B3": add(U, e(x=0.5))}),
        ("strip", "F", {"F3": add(U, e(y=0.5))})],
        [chk(21, "A1", "red", c.row21("A1", ["B3", "F3"]), [YEL, RANGE],
             pe="y", nb="y")]))
    L.append(S("S22", "row 22: PE learned, NB red", learn_by_reread + [
        ("strip", "E", {"E1": e(z=24)}), ("strip", "F", clean("F1", "F2")),
        ("strip", "H", clean("H1", "H2")), ("strip", "I", clean("I1"))],
        [chk(22, "E1", "red", c.row21("E1", like=["A4", "C5", "G4"]), [YEL, RANGE],
             pe="y", nb="y")]))
    L.append(S("S23", "row 23: both tests confirmed by similar patches", [
        ("strip", "A", {"A1": U}), ("strip", "J", {"J1": add(U, e(x=0.5))}),
        ("strip", "C", {"C1": nbrs["C1"]}), ("strip", "D", {"D1": nbrs["D1"]}),
        ("strip", "B", clean("B1", "B2")), ("strip", "G", clean("G1", "G2")),
        ("strip", "I", clean("I1", "I2"))],
        [chk(23, "A1", "yellow", c.row5("A1", 20, ["J1"], k=2,
                                        locs=["A1", "J1"], nb_peers=["J1"]),
             [RED_], pe="y", nb="y")],
        summary=["_SUM_NB_NONE"]))
    L.append(S("S24", "row 24: PE learned, NB confirmed by a similar patch",
               learn_by_reread + [
        ("strip", "E", {"E1": e(z=17)}), ("strip", "J", {"J1": e(z=14.5)}),
        ("strip", "F", clean("F1", "F2")), ("strip", "H", clean("H1", "H2")),
        ("strip", "I", clean("I1", "I2")), ("strip", "D", clean("D1", "D2"))],
        [chk(24, "E1", "yellow", c.row6("E1", 17, ["A4", "C5", "G4"], ["A4", "C5", "G4"],
                                        nb_peers=["J1"]), [RED_],
             pe="y", nb="y")]))
    L.append(S("S25", "row 25: PE similar patch, NB corrected (neighbours "
               "changed)", [
        ("strip", "A", {"A1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}),
        ("strip", "B", {"B1": e(z=14), "B2": e(z=14)}),
        ("strip", "F", {"F1": e(z=14), "F2": e(z=14)}),
        ("strip", "A", {"A1": U, "A2": e(z=14)}),
        ("strip", "G", {"G3": add(U, e(x=0.5))}),
        ("strip", "H", {"H3": e(z=14), "H1": e(z=14)})],
        [chk(25, "A1", "yellow", c.row5("A1", 20, ["G3"], k=2,
                                        locs=["A1", "G3"]), [RED_],
             pe="y", nb="n")]))
    L.append(S("S26", "row 26: PE learned, NB corrected (neighbours changed)",
               learn_by_reread + [
        ("strip", "E", {"E1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "H", clean("H1")), ("check", "first suspect"),
        ("strip", "D", {"D1": e(z=11), "D2": e(z=11)}),
        ("strip", "J", {"J1": e(z=11), "J2": e(z=11)}),
        ("strip", "E", {"E1": e(z=17)})],
        [chk(8, "E1", "red", c.row8("E1"), [YEL], pe="n", nb="y",
             note="at step 'first suspect'"),
         chk(26, "E1", "yellow", c.row6("E1", 17, ["A4", "C5", "G4"],
                                        ["A4", "C5", "G4"]),
             [RED_, "Neighbour check.)"], pe="y", nb="n")]))
    L.append(S("S27", "row 27: re-read under the limit, still a suspect", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": e(z=12)})],
        [chk(27, "A1", "red", c.row8("A1"),
             [YEL, M("_CARDS_PE_CORRECTED")], pe="n", nb="y")]))
    L.append(S("S28", "row 28: as 27, and a suspect alike in another strip", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "B", clean("B1", "B2")),
        ("strip", "G", clean("G1", "G2")), ("strip", "I", clean("I1", "I2")),
        ("strip", "A", {"A1": e(z=12)}),
        ("strip", "J", {"J1": e(x=0.5, z=12)})],
        [chk(28, "A1", "yellow", c.row10("A1", ["J1"], n8=True), [RED_],
             pe="n", nb="y")]))
    L.append(S("S29", "row 29: re-read under the limit, within T of the "
               "first, still a suspect", [
        ("strip", "A", {"A1": e(z=16)}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": e(z=14)})],
        [chk(29, "A1", "yellow", c.row9("A1", 14, 16), [RED_], pe="n",
             nb="y")]))
    L.append(S("S30", "row 30: both corrected by one re-read", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": noise("A1")})],
        [chk(30, "A1", "green", c.row11("A1", 20), [RED_, YEL], pe="n",
             nb="n")]))
    L.append(S("S31", "row 31: suspect re-read to another colour, still a "
               "suspect; then the neighbours change", [
        ("strip", "A", {"A1": V}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]}),
        ("strip", "A", {"A1": e(y=10)}), ("check", "pending"),
        ("strip", "B", {"B1": e(y=8), "B2": e(y=8)}),
        ("strip", "F", {"F1": e(y=8), "F2": e(y=8)})],
        [chk(31, "A1", "red", c.row8("A1"), [YEL], pe="n", nb="y",
             note="at step 'pending'"),
         chk(31, "A1", "green", c.row11("A1", 10), [RED_, YEL], pe="n",
             nb="n", note="the pending green (10.10) once not a suspect")]))
    L.append(S("S32", "row 32: Y-re, then a later strip makes it a suspect", [
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "A", {"A1": again(U)}), ("check", "before"),
        ("strip", "D", {"D1": nbrs["D1"]})],
        [chk(4, "A1", "yellow", c.row4("A1", DE(again(U)), 20, k=1, locs=["A1"]),
             [RED_, "Neighbour check.)"], pe="y", nb="n",
             note="at step 'before' (one neighbour: not judged)"),
         chk(32, "A1", "yellow", c.row4("A1", DE(again(U)), 20, k=1, locs=["A1"],
                                        nb=True),
             [RED_], pe="y", nb="y")]))
    L.append(S("S33", "row 33: the only similar patch read again differently", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=0.5))}),
        ("check", "peer"), ("strip", "B", {"B1": e(y=20)})],
        [chk(5, "A1", "yellow", c.row5("A1", 20, ["B1"], k=2,
                                       locs=["A1", "B1"]), [RED_], pe="y",
             nb="n", note="at step 'peer'"),
         chk(33, "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n")]))
    L.append(S("S33b", "row 33: the only similar patch re-read clean", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=0.5))}),
        ("strip", "B", {"B1": noise("B1")})],
        [chk(33, "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n"),
         chk(7, "B1", "green", c.row7("B1", 20.01), [RED_], pe="n", nb="n")]))
    L.append(S("S34", "row 34: the neighbour check switched off", [
        ("strip", "A", {"A1": V, "A2": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]})],
        [chk(34, "A1", "none", [], OUTLINE_WORDS, pe="n", nb="n"),
         chk(34, "A2", "red", c.row2("A2", 20), [YEL, "Neighbour check.)"],
             pe="y", nb="n")], nb_on=False, summary=["(none)"]))
    # ---- 35: closed and opened again -----------------------------------------
    L.append(S("S35", "row 35: every state, closed and opened again from disk", [
        ("strip", "A", {"A4": U, "A1": U}),
        ("strip", "B", {"B6": U}), ("strip", "C", {"C6": add(U, e(x=0.5))}),
        ("strip", "D", {"D9": U}),
        ("strip", "E", {"E10": V}), ("strip", "F", clean("F10")),
        ("strip", "G", clean("G10")), ("strip", "H", clean("H10")),
        ("strip", "A", {"A4": again(U), "A1": e(y=20)}),
        ("strip", "D", {"D9": noise("D9")}),
        ("strip", "I", {"I11": e(y=10)}), ("strip", "J", clean("J10", "J11")),
        ("strip", "I", {"I11": again(e(y=10))})],
        [chk(4, "A4", "yellow", c.row4("A4", DE(again(U)), 20, k=1, locs=["A4"]),
             [RED_], pe="y", nb="n"),
         chk(3, "A1", "red", c.row3("A1", 20, [20]), [YEL], pe="y", nb="n"),
         chk(5, "B6", "yellow", c.row5("B6", 20, ["C6"], rng="blue", k=2,
                                       locs=["B6", "C6"]), [RED_],
             pe="y", nb="n"),
         chk(7, "D9", "green", c.row7("D9", 20), [RED_], pe="n", nb="n"),
         chk(8, "E10", "red", c.row8("E10"), [YEL], pe="n", nb="y"),
         chk(9, "I11", "yellow", c.row9("I11", DE(again(e(y=10))), 10), [RED_], pe="n",
             nb="y")],
        disk=True, after=[("reopen",)],
        summary=["_SUM_NB_RED_ONE:E10", "_SUM_NB_KEPT_ONE"]))

    # ---- edge cases ------------------------------------------------------------
    L.append(S("E01", "same strip never confirms (patch error limit)", [
        ("strip", "A", {"A1": U, "A2": add(U, e(x=0.5))})],
        [chk("E01", "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n")]))
    L.append(S("E02", "same strip never confirms (neighbour check)", [
        ("strip", "A", {"A1": V, "A2": add(V, e(x=0.5))}),
        ("strip", "C", clean("C1", "C2")), ("strip", "D", clean("D1", "D2")),
        ("strip", "E", clean("E1", "E2")), ("strip", "B", clean("B1", "B2"))],
        [chk("E02", "A1", "red", c.row8("A1"), [YEL], pe="n", nb="y"),
         chk("E02", "A2", "red", c.row8("A2"), [YEL], pe="n", nb="y")],
        summary=["_SUM_NB_RED:2:A1, A2"]))
    L.append(S("E03", "another colour range never confirms", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B8": add(U, e(x=0.5))})],
        [chk("E03", "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n"),
         chk("E03", "B8", "red", c.row2("B8", 20.01, rng="yellow_green"),
             [YEL], pe="y", nb="n")]))
    for kind in ("estimated", "accurate", "verification", "calibration"):
        r = 15.0 if kind == "estimated" else 30.0
        mode = "verify" if kind == "verification" else "profiling"
        ck = Ctx(kind=kind, mode=mode)
        inside, outside = ("B9", "C9") if r == 15.0 else ("D9", "E9")
        L.append(S(f"E04-{kind}-in", f"radius {r:g} exactly ({kind}): similar",
                   [("strip", "A", {"A9": U}),
                    ("strip", inside[0], {inside: U})],
                   [chk("E04", "A9", "yellow",
                        ck.row5("A9", 20, [inside], rng="orange", k=2,
                                locs=["A9", inside]), [RED_], pe="y", nb="n")],
                   kind=kind, mode=mode))
        L.append(S(f"E04-{kind}-out", f"radius {r:g} + 0.01 ({kind}): not",
                   [("strip", "A", {"A9": U}),
                    ("strip", outside[0], {outside: U})],
                   [chk("E04", "A9", "red", ck.row2("A9", 20, rng="orange"),
                        [YEL], pe="y", nb="n")], kind=kind, mode=mode))
    L.append(S("E05-in", "errors exactly the tolerance (3.00) apart", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=3.0))})],
        [chk("E05", "A1", "yellow", c.row5("A1", 20, ["B1"], k=2,
                                           locs=["A1", "B1"]), [RED_],
             pe="y", nb="n")]))
    L.append(S("E05-out", "errors 3.01 apart", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=3.01))})],
        [chk("E05", "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n")]))
    L.append(S("E06", "errors of the same size, another direction", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": e(y=20)})],
        [chk("E06", "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n"),
         chk("E06", "B1", "red", c.row2("B1", 20), [YEL], pe="y", nb="n")]))
    L.append(S("E07-tol", "Preferences: the tolerance lowered re-judges "
               "(from disk)", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=2.5))})],
        [chk("E07", "A1", "yellow", c.row5("A1", 20, ["B1"], k=2,
                                           locs=["A1", "B1"]), [RED_],
             pe="y", nb="n", note="in the session, tolerance 3")],
        disk=True, after=[("end",), ("set", "tol", 2.0), ("refresh",),
                          ("expect", chk("E07", "A1", "red",
                                         c.row2("A1", 20), [YEL],
                                         note="after Preferences: tolerance "
                                              "2, judged again from disk")),
                          ("set", "tol", 3.0), ("refresh",),
                          ("expect", chk("E07", "A1", "yellow",
                                         c.row5("A1", 20, ["B1"], k=2,
                                                locs=["A1", "B1"]), [RED_],
                                         note="tolerance back to 3"))]))
    L.append(S("E07-radius", "Preferences: the radius lowered re-judges "
               "(from disk)", [
        ("strip", "A", {"A9": U}), ("strip", "B", {"B9": U})],
        [chk("E07", "A9", "yellow", c.row5("A9", 20, ["B9"], rng="orange",
                                           k=2, locs=["A9", "B9"]),
             [RED_], pe="y", nb="n", note="radius 15")],
        disk=True, after=[("end",), ("set", "radius", 14.99), ("refresh",),
                          ("expect", chk("E07", "A9", "red",
                                         c.row2("A9", 20, rng="orange"), [YEL],
                                         note="radius 14.99 (15.00 apart)"))]))
    L.append(S("E07-live", "Preferences changed DURING a session: tolerance "
               "lowered, then the next strip", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B1": add(U, e(x=2.5))}),
        ("set", "tol", 2.0), ("refresh",), ("check", "right after"),
        ("strip", "H", {"H12": noise("H12")})],
        [chk("E07", "A1", "yellow", c.row5("A1", 20, ["B1"], k=2,
                                           locs=["A1", "B1"]), [RED_],
             pe="y", nb="n",
             note="at 'right after' Preferences OK, in the session: "
                  "unchanged until the next strip (Basti, 2026-10-16, "
                  "item 11; UMM 10.12)"),
         chk("E07", "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n",
             note="after the next strip")]))
    L.append(S("E07-limit", "Preferences: limit raised hides a Y-re, lowered "
               "brings it back; a lowered limit makes similar patches", [
        ("strip", "A", {"A4": U}), ("strip", "A", {"A4": again(U)}),
        ("strip", "C", {"C1": e(z=13)}), ("strip", "D", {"D1": e(x=1, z=13)})],
        [chk(4, "A4", "yellow", c.row4("A4", DE(again(U)), 20, k=1, locs=["A4"]),
             [RED_], pe="y", nb="n")],
        disk=True, after=[
            ("end",), ("set", "pe", 25.0), ("refresh",),
            ("expect", chk("E07", "A4", "none", [], OUTLINE_WORDS,
                           note="limit 25: not flagged, Y-re kept hidden")),
            ("set", "pe", 15.0), ("refresh",),
            ("expect", chk("E07", "A4", "yellow",
                           c.row4("A4", DE(again(U)), 20, k=1, locs=["A4"]), [RED_],
                           note="limit back to 15: yellow again (10.3b)")),
            ("set", "pe", 12.0), ("refresh",),
            ("expect", chk("E07", "C1", "yellow",
                           Ctx(pe=12.0).row5("C1", 13, ["D1"], k=3, locs=[]),
                           [RED_], note="limit 12: C1 and D1 past it, alike "
                                        "(T5)"))]))
    L.append(S("E08", "the neighbour check compares with its own strip", [
        ("strip", "A", {"A1": V, "A2": noise("A2")}),
        ("strip", "C", {"C3": noise("C3")})],
        [chk("E08", "A1", "red", ["The 2 patches most similar to patch A1"]
             + c.row8("A1"), [YEL], pe="n", nb="y",
             note="its neighbours: A2 (same strip) and C3")]))
    L.append(S("E09", "closing window: a suspect confirmed by similar "
               "patches is in neither line", [
        ("strip", "A", {"A1": V}), ("strip", "J", {"J1": add(V, e(x=0.5))}),
        ("strip", "E", {"E1": e(y=10)}), ("strip", "F", {"F1": e(x=10)}),
        ("strip", "C", {"C1": nbrs["C1"]}), ("strip", "D", {"D1": nbrs["D1"]}),
        ("strip", "B", clean("B1", "B2")), ("strip", "G", clean("G1", "G2")),
        ("strip", "I", clean("I1", "I2")), ("strip", "H", clean("H1", "H2")),
        ("strip", "B", {"B6": U}),
        ("strip", "F", {"F1": again(e(x=10))})],
        [chk(10, "A1", "yellow", c.row10("A1", ["J1"]), [RED_], nb="y"),
         chk(9, "F1", "yellow", None, [RED_], nb="y"),
         chk(2, "B6", "red", None, [YEL], pe="y", nb="n")],
        summary=["_SUM_NB_RED_ONE:E1", "_SUM_NB_KEPT_ONE"], after=[("window",)]))
    L.append(S("E09b", "closing window: plural lines", [
        ("strip", "A", {"A1": V}), ("strip", "E", {"E1": e(y=10)}),
        ("strip", "J", {"J2": e(x=10)}), ("strip", "F", {"F2": e(x=-10)}),
        ("strip", "C", clean("C1", "C2")), ("strip", "D", clean("D1", "D2")),
        ("strip", "B", clean("B1", "B2")), ("strip", "G", clean("G1", "G2")),
        ("strip", "I", clean("I1", "I2")), ("strip", "H", clean("H1", "H2")),
        ("strip", "J", {"J2": again(e(x=10))}),
        ("strip", "F", {"F2": again(e(x=-10))})],
        [chk(8, "A1", "red", None, [YEL], nb="y"),
         chk(9, "J2", "yellow", None, [RED_], nb="y")],
        summary=["_SUM_NB_RED:2:A1, E1", "_SUM_NB_KEPT:2"], after=[("window",)]))
    L.append(S("E09c", "closing window: nothing checked", [
        ("strip", "A", {"A1": U})], [chk(2, "A1", "red", None, [YEL])],
        summary=["_SUM_NB_NONE_CHECKED:1"]))
    L.append(S("E13", "a suspect confirmed by its own re-read IS a similar "
               "patch for the limit (point 6)", [
        ("strip", "C", {"C1": e(z=14)}), ("strip", "D", {"D1": e(z=14)}),
        ("strip", "E", {"E1": e(z=14)}),
        ("strip", "F", {"F3": noise("F3")}), ("strip", "G", {"G3": noise("G3")}),
        ("strip", "H", {"H3": noise("H3")}),
        ("strip", "A", {"A1": U}), ("strip", "B", {"B3": add(U, e(x=0.5))}),
        ("check", "Q red"), ("strip", "B", {"B3": again(add(U, e(x=0.5)))})],
        [chk(2, "A1", "red", c.row2("A1", 20), [YEL], pe="y", nb="n",
             note="at 'Q red': B3 is held red by the neighbour check"),
         chk(5, "A1", "yellow", c.row5("A1", 20, ["B3"], k=2,
                                       locs=["A1", "B3"]), [RED_],
             pe="y", nb="n")]))
    L.append(S("E14", "the limit itself: 15.00 is not past it, 15.01 is", [
        ("strip", "A", {"A9": e(z=15.0)}), ("strip", "F", {"F6": e(z=15.01)})],
        [chk("E14", "A9", "none", [], OUTLINE_WORDS, pe="n", nb="n"),
         chk("E14", "F6", "red", c.row2("F6", 15.01, rng="blue"), [YEL],
             pe="y", nb="n")]))
    fill = {f"A{n}": e(z=1.0 + 0.2 * n) for n in range(12, 22)}
    L.append(S("E15", "strip test on: past the limit and its strip's fence", [
        ("strip", "A", dict(fill, A1=U))],
        [chk("E15", "A1", "red", c.row2("A1", 20, fenced=True), [YEL],
             pe="y", nb="n")], strip_test=True))
    fill2 = {f"A{n}": e(z=v) for n, v in zip(range(12, 22),
                                             (16, 17, 18, 19, 21, 22, 23, 16,
                                              17, 18))}
    L.append(S("E15b", "strip test on: past the limit, inside its strip's "
               "fence", [("strip", "A", dict(fill2, A1=U))],
               [chk("E15", "A1", "none", [], OUTLINE_WORDS, pe="n", nb="n")],
               strip_test=True))
    # ---- patch by patch ------------------------------------------------------
    pc = Ctx()
    L.append(S("P05", "patch by patch: row 5 (strip labels decide)", [
        ("patch", "A1", U), ("patch", "B1", add(U, e(x=0.5)))],
        [chk(5, "A1", "yellow", pc.row5("A1", 20, ["B1"], k=2,
                                        locs=["A1", "B1"])
             + [M("_CARD_LATER_PATCH_S")], [RED_], pe="y", nb="n")],
        pbp=True))
    L.append(S("P01", "patch by patch: same strip label never confirms", [
        ("patch", "A1", U), ("patch", "A2", add(U, e(x=0.5)))],
        [chk("E01", "A1", "red", pc.row2("A1", 20)
             + [M("_CARD_LATER_PATCH_S")], [YEL], pe="y", nb="n")], pbp=True))
    L.append(S("P04", "patch by patch: rows 4 and 7", [
        ("patch", "A1", U), ("patch", "A1", again(U)), ("patch", "B4", U),
        ("patch", "B4", noise("B4"))],
        [chk(4, "A1", "yellow", pc.row4("A1", DE(again(U)), 20, k=1, locs=["A1"]),
             [RED_], pe="y", nb="n"),
         chk(7, "B4", "green", pc.row7("B4", 20), [RED_], pe="n", nb="n")],
        pbp=True))
    L.append(S("P08", "patch by patch: rows 8 and 10", [
        ("patch", "A1", V), ("patch", "C1", nbrs["C1"]),
        ("patch", "D1", nbrs["D1"]), ("patch", "B1", noise("B1")),
        ("patch", "B2", noise("B2")), ("patch", "G1", noise("G1")),
        ("patch", "G2", noise("G2")), ("patch", "I1", noise("I1")),
        ("patch", "I2", noise("I2")), ("check", "row 8"),
        ("patch", "J1", add(V, e(x=0.5)))],
        [chk(8, "A1", "red", pc.row8("A1") + [M("_CARD_LATER_PATCH_S")],
             [YEL], pe="n", nb="y", note="at 'row 8'"),
         chk(10, "A1", "yellow", pc.row10("A1", ["J1"])
             + [M("_CARD_LATER_PATCH_S")], [RED_], pe="n", nb="y")],
        pbp=True))
    # ---- the other chart types and Knut's verification settings ---------------
    vk = Ctx(kind="verification", mode="verify")
    L.append(S("V02", "verification (15 / 7 / 30 / 3): rows 2 and 8", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B4": V}),
        ("strip", "C", clean("C4")), ("strip", "D", clean("D4")),
        ("strip", "E", clean("E4"))],
        [chk(2, "A1", "red", vk.row2("A1", 20), [YEL], pe="y", nb="n"),
         chk(8, "B4", "red", vk.row8("B4"), [YEL], pe="n", nb="y")],
        kind="verification", mode="verify",
        summary=["_SUM_NB_RED_ONE_VERIFY:B4"], after=[("window",)]))
    L.append(S("V05", "verification: rows 5, 6 (learned) and 12", [
        ("strip", "A", {"A6": U}), ("strip", "B", {"B7": U}),
        ("strip", "C", {"C6": U}), ("strip", "E", {"E7": e(z=24)}),
        ("strip", "A", {"A1": U}), ("strip", "C", {"C1": nbrs["C1"]}),
        ("strip", "D", {"D1": nbrs["D1"]}), ("strip", "E", {"E1": nbrs["E1"]})],
        [chk(5, "A6", "yellow", vk.row5("A6", 20, ["B7", "C6"], rng="blue",
                                        k=3, locs=[]), [RED_], pe="y", nb="n",
             note="E7 (24) is 4 from them: not similar; learned"),
         chk(6, "E7", "yellow", vk.row6("E7", 24, ["A6", "B7", "C6"], ["A6", "B7", "C6"],
                                        rng="blue"), [RED_], pe="y"),
         chk(12, "A1", "red", vk.row12("A1", 20), [YEL], pe="y", nb="y")],
        kind="verification", mode="verify"))
    for kind in ("accurate", "calibration"):
        ck = Ctx(kind=kind)
        L.append(S(f"K-{kind}", f"{kind} chart: rows 2 and 8 name its limits", [
            ("strip", "A", {"A1": U}), ("strip", "B", {"B4": V}),
            ("strip", "C", clean("C4")), ("strip", "D", clean("D4")),
            ("strip", "E", clean("E4"))],
            [chk(2, "A1", "red", ck.row2("A1", 20), [YEL], pe="y", nb="n"),
             chk(8, "B4", "red", ck.row8("B4"), [YEL], pe="n", nb="y")],
            kind=kind))
    lt = Ctx(mode="later")
    L.append(S("L02", "verification whose profile is newer (judged against "
               "the estimate): rows 2, 4, 8", [
        ("strip", "A", {"A1": U}), ("strip", "B", {"B4": V}),
        ("strip", "C", {"C4": noise("C4"), "C9": U}),
        ("strip", "D", clean("D4")), ("strip", "E", clean("E4")),
        ("strip", "C", {"C4": noise("C4"), "C9": again(U)})],
        [chk(2, "A1", "red", lt.row2("A1", 20), [YEL], pe="y", nb="n"),
         chk(8, "B4", "red", lt.row8("B4"), [YEL], pe="n", nb="y"),
         chk(4, "C9", "yellow", lt.row4("C9", DE(again(U)), 20, rng="orange", k=1,
                                        locs=["C9"]), [RED_], pe="y")],
        mode="later"))
    # ---- light and dark --------------------------------------------------------
    L.append(S("D-light", "appearance light: red, yellow (re-read, similar, "
               "learned) and green outlines", learn_by_reread + [
        ("strip", "E", {"E1": e(z=24)}), ("strip", "B", {"B6": U}),
        ("strip", "C", {"C6": add(U, e(x=0.5))}), ("strip", "D", {"D9": U}),
        ("strip", "D", {"D9": noise("D9")}), ("strip", "H", {"H10": U})],
        [chk(6, "E1", "yellow", None, [RED_]), chk(5, "B6", "yellow", None),
         chk(7, "D9", "green", None), chk(2, "H10", "red", None),
         chk(4, "A4", "yellow", None)]))
    d = dict(L[-1])
    d["id"], d["title"] = "D-dark", d["title"].replace("light", "dark")
    d["appearance"] = "dark"
    L.append(d)
    return L


def main() -> int:
    out = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (
        ROOT / "build" / "b8_matrix_demo")
    charts = build_charts(out)
    print(json.dumps({k: str(v) for k, v in charts.items()}, indent=1))
    print(len(scenarios()), "scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
