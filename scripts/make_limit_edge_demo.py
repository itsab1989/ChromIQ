#!/usr/bin/env python3
"""Measurement data that lands EXACTLY on every misread limit, per chart type
(#182, Knut 6154440320, 4.3.5 beta 4).

    python scripts/make_limit_edge_demo.py [destination]   # default ./demo-projects

*"verify by test that each chart type is triggering on the correct limit by
setting all limits to unique levels and making demo project data with proper
measurement data that is designed to trigger exactly on each one of the
limits for each chart type and for each test method. Verify on-screen that the
hover text exactly corresponds to the measurements when not failing and when
failing the tests. Make sure the demo data is designed so that all variations
of faults are tested and all variations of hover-text cards on patches are
generated."*

WHAT IT WRITES: one project, ``Demo-Limit-Edges``, with a real chart for each
chart type (laid out by ChromIQ's own engine, ``scripts/make_misread_demo.py``
``_build``; no ArgyllCMS tool is run), and beside each chart
``<stem>.edges.json``: a simulated printer's readings of every patch, the
patches planted ON the limits, the re-reads the protocol replays, and what
every planted patch must show. The chart types:

=====================  =================================  ===================
folder                 chart                              judged with
=====================  =================================  ===================
``runs/run1``          profiling, estimated colours       estimated limits
``runs/run2``          profiling, pre-conditioning prof.  pre-conditioning
``verify-through``     verification, through the profile  verification
``verify-fpg``         verification, From Profile Gamut   verification
``verify-later``       verification whose profile was     estimated (spec A27,
                       made after the sheet was printed   A22/A23: the chart's
                                                          own estimate)
``cal``                calibration chart (7 ramps)        calibration
=====================  =================================  ===================

EVERY LIMIT IS UNIQUE (:data:`LIMITS`), so a card that names a number names
the chart type it came from, and a test that used another type's limit cannot
pass by coincidence.

THE PLANTED PATCHES, per chart (``plan`` in the json). "At two decimals" is
Knut's rule (#182 6102031563): a value is compared as the card prints it, and
flagged only ABOVE the threshold (5.00 at 5.00 is not, 5.01 is).

* Patch error limit, neighbour check OFF (pass A):
  ``pe_under`` limit - 0.01 (no outline), ``pe_on`` exactly the limit (no
  outline), ``pe_over`` limit + 0.01 (red);
  ``pe_unsettled`` and ``pe_green`` well past it (red), re-read later;
* Strip test (``fence_strip``: every patch of one strip read off together,
  past the patch error limit): ``fence_under`` the strip's Tukey fence - 0.01
  (no outline: it does not stand out), ``fence_over`` fence + 0.01 (red,
  "Strip test");
* similar patches (``peer_1``, ``peer_2``): two patches of different strips,
  expected less than ΔE*ab 6 apart, off the same way (yellow, confirmed by
  similar patches);
* a colour range that learns (``learn_1`` to ``learn_3`` confirmed by their
  re-reads, ``learn_4`` then yellow, judged like one of them);
* Neighbour check ON (pass B): ``nl_under`` / ``nl_on`` / ``nl_over``
  stand out from their neighbours by the Neighbour limit - 0.01 / exactly /
  + 0.01; ``nl_green`` well past it; ``nb_equal`` exactly as far off as its
  neighbours (the card's "does not stand out"), ``nb_closer`` read exactly
  (the card's "closer"), and ``nb_few``, a patch with fewer than 2 similar
  patches within the radius (the card's "Not compared"), where the chart has
  one;
* the re-reads (``rereads``): ``pe_over`` again, exactly the Same-reading
  tolerance away (yellow), ``pe_unsettled`` again, 0.01 beyond it and still
  past the limit (red, unsettled), ``pe_green`` and ``nl_green`` read
  correctly (green, by the limit and by the neighbour check), ``nl_over``
  read the same (yellow), ``learn_1`` to ``learn_3`` read the same.

Every number is checked here after the readings are rounded the way they are
stored, with this script's own implementation of the rules
(``make_misread_demo.four_steps``, :func:`fence`), never with the app's
judging code. ``expect`` holds, per planted patch and pass, the outline and
the figures its card must show.

:func:`design` is pure (no Qt, no files): ``tests/test_435b4_limit_edges.py``
runs it on a chart of its own and drives the Measure tab with it.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

NAME = "Demo-Limit-Edges"

#: Preferences ▸ Measurement for this demo: every value unique (two
#: decimals), the strip test on for every type.
LIMITS = {
    "estimated":    dict(pel=14.37, strip=True, nl=6.42, nr=17.30),
    "accurate":     dict(pel=11.83, strip=True, nl=4.76, nr=28.60),
    "verification": dict(pel=7.29,  strip=True, nl=3.18, nr=31.40),
    "calibration":  dict(pel=16.51, strip=True, nl=5.94, nr=26.20),
}
SAME_READING = 2.73
#: Which limits each demo chart is judged with (the app's chart type).
JUDGED_AS = {"estimated": "estimated", "accurate": "accurate",
             "verification": "verification",
             "verification_fpg": "verification",
             "verification_later": "estimated",
             "calibration": "calibration"}
KINDS = list(JUDGED_AS)
FOLDERS = {"estimated": "runs/run1", "accurate": "runs/run2",
           "verification": "verify-through", "verification_fpg": "verify-fpg",
           "verification_later": "verify-later", "calibration": "cal"}
#: The phrase the cards name the chart type with (M-PATCH-LIMIT).
KIND_PHRASE = {
    "estimated": "profiling charts with estimated colours",
    "accurate": "profiling charts made with a pre-conditioning profile",
    "verification": "verification charts",
    "calibration": "calibration charts",
}


def settings_values() -> dict:
    """The Preferences keys and values this demo is measured with."""
    from workflow import misread_settings as MS
    out = {}
    for k, v in LIMITS.items():
        out[MS.PATCH_ERROR_LIMIT_KEYS[k]] = v["pel"]
        out[MS.STRIP_TEST_KEYS[k]] = v["strip"]
        out[MS.NEIGHBOUR_LIMIT_KEYS[k]] = v["nl"]
        out[MS.NEIGHBOUR_RADIUS_KEYS[k]] = v["nr"]
    out[MS.SAME_READING_KEY] = SAME_READING
    out[MS.NEIGHBOUR_CHECK_KEY] = True
    return out


# ---- the rules, written apart from the app ----------------------------------
def r2(v: float) -> float:
    """At two decimals, as the cards print it."""
    return float(f"{float(v):.2f}")


def above(v, t) -> bool:
    return r2(v) > r2(t)


def fence(des) -> float:
    """Tukey's upper fence of a strip's ΔE*ab (Q3 + 1.5 IQR), 0 under 4."""
    if len(des) < 4:
        return 0.0
    s = sorted(des)

    def pct(p):
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)
    q1, q3 = pct(0.25), pct(0.75)
    return q3 + 1.5 * (q3 - q1)


def _lab(xyz100):
    from workflow.neighbour_check import engine_lab
    return engine_lab(xyz100)


def _xyz(lab_):
    from make_misread_demo import xyz
    return xyz(lab_)


def _stored(xyz100) -> list:
    """A reading as it is stored and sent (five decimals)."""
    return [round(float(v), 5) for v in xyz100]


def _de(a, b) -> float:
    return math.dist(a, b)


def _letter(loc: str) -> str:
    return "".join(c for c in loc if c.isalpha())


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


# ---- the design --------------------------------------------------------------
class _Design:
    def __init__(self, kind: str, patches: "list[dict]", ranges: dict,
                 seed: str):
        self.kind = kind
        self.lim = LIMITS[JUDGED_AS[kind]]
        self.patches = {p["loc"]: p for p in patches}
        self.order = [p["loc"] for p in patches]
        self.ranges = ranges
        self.rng = random.Random(seed)
        self.exp = {loc: _lab(p["exyz"]) for loc, p in self.patches.items()}
        self.strips: dict = {}
        for loc in self.order:
            self.strips.setdefault(_letter(loc), []).append(loc)
        # the simulated printer: close to the expected colours
        self.read = {loc: _stored(_xyz(tuple(v + self.rng.gauss(0.0, 0.12)
                                             for v in self.exp[loc])))
                     for loc in self.order}
        self.plan: dict = {}
        self.taken: set = set()

    # -- what a reading is ----------------------------------------------------
    def lab_of(self, loc, reading=None):
        return _lab(reading if reading is not None else self.read[loc])

    def err(self, loc, reading=None) -> float:
        return _de(self.lab_of(loc, reading), self.exp[loc])

    def event_de(self, loc, reading=None) -> float:
        """The ΔE the engine sends with the reading: two decimals."""
        from workflow.measurement_report import engine_patch_de
        return round(engine_patch_de(self.patches[loc]["exyz"],
                                     reading if reading is not None
                                     else self.read[loc]), 2)

    def at_error(self, loc, target: float, direction=None, base=None,
                 strict: bool = False):
        """A reading of *loc* whose stored ΔE*ab from its expected colour is
        *target*, along *direction* (a random one by default)."""
        e = self.exp[loc] if base is None else base
        for attempt in range(1 if strict else 40):
            # a direction the reading can go without leaving XYZ >= 0 (a
            # dark patch cannot be read darker than black); the one asked for
            # first, random ones after it
            u = _unit(direction if (direction and attempt == 0) else
                      [self.rng.gauss(0, 1) for _ in range(3)])
            t = target
            for _ in range(8):
                r = _stored(_xyz(tuple(c + t * x for c, x in zip(e, u))))
                got = self.err(loc, r) if base is None else _de(
                    self.lab_of(loc, r), base)
                if abs(got - target) < 2e-4:
                    return r
                t += target - got
        raise SystemExit(f"{self.kind}: {loc} cannot be read {target} off")

    def neighbours(self, loc, readings=None):
        """``(n, further, median, own, compared)`` by Knut's four steps."""
        from make_misread_demo import four_steps
        readings = readings or self.read
        meas = {x: _lab(r) for x, r in readings.items()}
        order = {x: i for i, x in enumerate(self.order)}
        n, fu = four_steps(loc, self.exp, meas, radius=self.lim["nr"],
                           order=order)
        return n, fu

    def nb_set(self, loc) -> list:
        from workflow.misread_settings import within
        me = self.exp[loc]
        order = {x: i for i, x in enumerate(self.order)}
        cand = sorted((_de(me, self.exp[o]), order[o], o) for o in self.order
                      if o != loc and within(_de(me, self.exp[o]),
                                             self.lim["nr"]))[:4]
        return [o for _d, _i, o in cand]

    def median_of(self, locs) -> float:
        errs = sorted(self.err(x) for x in locs)
        n = len(errs)
        return errs[n // 2] if n % 2 else (errs[n // 2 - 1] + errs[n // 2]) / 2

    # -- picking ----------------------------------------------------------------
    def pick(self, name, pred, *, far_from_taken: float = 0.0):
        locs = list(self.order)
        self.rng.shuffle(locs)
        for loc in locs:
            if loc in self.taken or _letter(loc) == self.plan.get("fence_strip"):
                continue
            if far_from_taken and any(
                    _de(self.exp[loc], self.exp[t]) < far_from_taken
                    for t in self.taken):
                continue
            if pred(loc):
                self.taken.add(loc)
                self.plan[name] = loc
                return loc
        raise SystemExit(f"{self.kind}: no patch fits {name}")

    def clean_set(self, loc) -> bool:
        """Its neighbours are all clean, unplanted patches, and it has 3 or
        4 of them."""
        s = self.nb_set(loc)
        return (len(s) >= 3 and not (set(s) & self.taken)
                and all(_letter(x) != self.plan.get("fence_strip") for x in s))

    # -- the plan ---------------------------------------------------------------
    def build(self) -> dict:
        pel, nl = self.lim["pel"], self.lim["nl"]
        strips = sorted(self.strips, key=lambda s: (len(s), s))
        # THE STRIP TEST: a long strip in the middle, read off together
        long = [s for s in strips if len(self.strips[s]) >= 12]
        fs = long[len(long) // 2]
        self.plan["fence_strip"] = fs
        base = pel + 3.0
        f_locs = self.strips[fs]
        offs = {}
        for i, loc in enumerate(f_locs):
            size = base + (i % 7) * 0.23
            offs[loc] = self.at_error(loc, size, direction=[1, 1, 1])
        for loc, r in offs.items():
            self.read[loc] = r
        # the two planted ones are the strip's two largest, so the fence is
        # the other patches' alone
        fu_loc, fo_loc = f_locs[1], f_locs[2]
        # …and never half a hundredth from a rounding edge: quartiles of
        # two-decimal values often end in 5 in the third decimal, and the
        # test is about the limit, not about how a float rounds
        others = [x for x in f_locs if x not in (fu_loc, fo_loc)]
        for nudge in range(60):
            des = [self.event_de(x) for x in others] + [99.0, 99.5]
            fn = fence(des) * 100.0
            if abs(fn - round(fn)) < 0.3:
                break
            x = others[nudge % len(others)]
            self.read[x] = self.at_error(x, self.event_de(x) + 0.01,
                                         direction=[1, 1, 1])
        self.plan["fence_under"], self.plan["fence_over"] = fu_loc, fo_loc
        for _ in range(4):
            des = [self.event_de(x) for x in f_locs]
            fn = r2(fence(des))
            self.read[fu_loc] = self.at_error(fu_loc, fn - 0.01,
                                              direction=[1, 1, 1])
            self.read[fo_loc] = self.at_error(fo_loc, fn + 0.01,
                                              direction=[1, 1, 1])
        self.taken.update(f_locs)
        # NEIGHBOUR EDGES first: they need clean neighbourhoods
        for name in ("nl_under", "nl_on", "nl_over", "nb_equal",
                     "nb_closer", "nl_green"):
            # the two read again in pass B, each in a strip of its own
            if name == "nl_green":
                self.pick(name, lambda x: self.clean_set(x) and _letter(x)
                          != _letter(self.plan["nl_over"]))
            else:
                self.pick(name, self.clean_set)
            for x in self.nb_set(self.plan[name]):
                self.taken.add(x)          # its neighbours stay clean
        for name, d in (("nl_under", -0.01), ("nl_on", 0.0), ("nl_over", 0.01)):
            loc = self.plan[name]
            med = self.median_of(self.nb_set(loc))
            self.read[loc] = self.at_error(loc, med + nl + d)
        loc = self.plan["nb_equal"]
        self.read[loc] = self.at_error(loc, self.median_of(self.nb_set(loc)))
        loc = self.plan["nb_closer"]
        self.read[loc] = _stored(self.patches[loc]["exyz"])
        loc = self.plan["nl_green"]
        med = self.median_of(self.nb_set(loc))
        self.read[loc] = self.at_error(loc, med + nl + 3.0)
        # A PATCH WITH FEWER THAN 2 SIMILAR ONES, where the chart has one
        few = [x for x in self.order if len(self.nb_set(x)) < 2
               and x not in self.taken]
        if few:
            self.plan["nb_few"] = few[0]
            self.taken.add(few[0])
        # THE COLOUR RANGE THAT LEARNS (Knut, #182 k10): three confirmed
        # patches of one range, then a fourth red one of it, off the same
        # way, is judged like them. Two of the three confirm each other as
        # similar patches (different strips, expected less than ΔE 6 apart,
        # off alike: ``peer_1``, ``peer_2``), the third by its own re-read
        # (``learn_1``); ``learn_4`` is the one judged like them. All four
        # are off by the same vector, which raises L* so a dark patch is
        # never read darker than black; ``learn_1`` and ``learn_4`` are more
        # than ΔE 7 from every other one, so they are nobody's similar patch.
        #
        # A STRIP IS READ WHOLE: re-reading a patch reads every patch of its
        # strip again with its last reading. So each patch read again in pass
        # A (``pe_over``, ``pe_unsettled``, ``pe_green``, ``learn_1``) has a
        # strip of its own, and ``learn_4``, which must never be re-read, has
        # one none of them is in.
        v = _unit([1.0, 0.25, -0.35])
        size = pel + 3.5

        def feasible(loc) -> bool:
            try:
                self.at_error(loc, size, direction=v, strict=True)
                return True
            except SystemExit:
                return False

        reread_strips: set = set()
        groups: dict = {}
        for loc in self.order:
            if loc in self.taken or _letter(loc) == fs or not feasible(loc):
                continue
            groups.setdefault(self.ranges.get(loc), []).append(loc)
        learn = None
        for rname, locs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            for i, a_ in enumerate(locs):
                for b_ in locs[i + 1:]:
                    if (_letter(a_) == _letter(b_)
                            or _de(self.exp[a_], self.exp[b_]) >= 5.0):
                        continue
                    rest = [x for x in locs if x not in (a_, b_) and all(
                        _de(self.exp[x], self.exp[y]) >= 7.0 for y in (a_, b_))]
                    for l1 in rest:
                        for l4 in rest:
                            if (l4 != l1 and _letter(l4) != _letter(l1)
                                    and _de(self.exp[l1], self.exp[l4]) >= 7.0):
                                learn = (rname, a_, b_, l1, l4)
                                break
                        if learn:
                            break
                    if learn:
                        break
                if learn:
                    break
            if learn:
                break
        if learn is None:
            raise SystemExit(f"{self.kind}: no colour range for learning")
        rname, p1, p2, l1, l4 = learn
        for name, loc in (("peer_1", p1), ("peer_2", p2), ("learn_1", l1),
                          ("learn_4", l4)):
            self.plan[name] = loc
            self.taken.add(loc)
            self.read[loc] = self.at_error(loc, size, direction=v, strict=True)
        reread_strips.add(_letter(l1))
        used_ranges = {rname}

        def own_strip(x) -> bool:
            return (_letter(x) not in reread_strips
                    and _letter(x) != _letter(l4))

        # the patch error limit's edges. pe_over's neighbours are clean too:
        # with the neighbour check on its card is red for both tests
        for name, d in (("pe_under", -0.01), ("pe_on", 0.0), ("pe_over", 0.01)):
            if name == "pe_over":
                pred = (lambda x: self.ranges.get(x) not in used_ranges
                        and own_strip(x) and self.clean_set(x))
            else:
                pred = (lambda x: self.ranges.get(x) not in used_ranges)
            loc = self.pick(name, pred, far_from_taken=7.0)
            if name == "pe_over":
                used_ranges.add(self.ranges.get(loc))
                reread_strips.add(_letter(loc))
                self.taken.update(self.nb_set(loc))
            self.read[loc] = self.at_error(loc, pel + d)
        for name in ("pe_unsettled", "pe_green"):
            loc = self.pick(name, lambda x: self.ranges.get(x) not in used_ranges
                            and own_strip(x), far_from_taken=7.0)
            reread_strips.add(_letter(loc))
            self.read[loc] = self.at_error(loc, pel + 6.0)
        # THE RE-READS
        rr = {}
        loc = self.plan["pe_over"]
        e_dir = [m - x for m, x in zip(self.lab_of(loc), self.exp[loc])]
        rr["pe_over_same"] = self.at_error(loc, SAME_READING, direction=e_dir,
                                           base=self.lab_of(loc))
        loc = self.plan["pe_unsettled"]
        e_dir = [m - x for m, x in zip(self.lab_of(loc), self.exp[loc])]
        rr["pe_unsettled_other"] = self.at_error(
            loc, SAME_READING + 0.01, direction=e_dir, base=self.lab_of(loc))
        rr["pe_green_good"] = _stored(_xyz(tuple(
            c + 0.1 for c in self.exp[self.plan["pe_green"]])))
        rr["nl_green_good"] = _stored(_xyz(tuple(
            c + 0.05 for c in self.exp[self.plan["nl_green"]])))
        loc = self.plan["nl_over"]
        e_dir = [m - x for m, x in zip(self.lab_of(loc), self.exp[loc])]
        rr["nl_over_same"] = self.at_error(loc, 0.4, direction=e_dir,
                                           base=self.lab_of(loc))
        loc = self.plan["learn_1"]
        e_dir = [m - x for m, x in zip(self.lab_of(loc), self.exp[loc])]
        rr["learn_1_same"] = self.at_error(loc, 0.4, direction=e_dir,
                                           base=self.lab_of(loc))
        self.rereads = rr
        return self.check()

    # -- what must be seen ------------------------------------------------------
    def check(self) -> dict:
        """Every planted figure, worked out again from the stored readings,
        and asserted to be the one it was designed to be."""
        pel, nl = self.lim["pel"], self.lim["nl"]
        p = self.plan
        facts = {}
        for name, loc in p.items():
            if not isinstance(loc, str) or name == "fence_strip":
                continue
            n, fu = self.neighbours(loc)
            facts[name] = {"loc": loc, "de": self.event_de(loc),
                           "err": self.err(loc), "n": n, "further": fu}
        f_des = [self.event_de(x) for x in self.strips[p["fence_strip"]]]
        fn = fence(f_des)
        facts["fence"] = {"strip": p["fence_strip"], "fence": round(fn, 4)}

        def want(cond, msg):
            if not cond:
                raise SystemExit(f"{self.kind}: {msg}")
        want(r2(facts["pe_under"]["de"]) == r2(pel - 0.01), "pe_under")
        want(r2(facts["pe_on"]["de"]) == r2(pel), "pe_on")
        want(r2(facts["pe_over"]["de"]) == r2(pel + 0.01), "pe_over")
        want(r2(facts["fence_under"]["de"]) == r2(fn) - 0.01
             or r2(facts["fence_under"]["de"]) == r2(r2(fn) - 0.01), "fence_under")
        want(r2(facts["fence_over"]["de"]) == r2(r2(fn) + 0.01), "fence_over")
        want(above(facts["fence_under"]["de"], pel), "fence_under past limit")
        for name, d in (("nl_under", -0.01), ("nl_on", 0.0), ("nl_over", 0.01)):
            got = facts[name]["further"]
            want(got is not None and r2(got) == r2(nl + d),
                 f"{name}: {got} for {r2(nl + d)}")
            want(not above(facts[name]["de"], pel), f"{name} under the limit")
        want(r2(facts["nb_equal"]["further"]) == 0.0, "nb_equal")
        want(above(facts["pe_over"]["further"], nl), "pe_over: both tests")
        want(facts["nb_closer"]["further"] < 0, "nb_closer")
        rr = self.rereads
        d_same = _de(self.lab_of(p["pe_over"]), _lab(rr["pe_over_same"]))
        want(r2(d_same) == SAME_READING, f"same reading {d_same}")
        d_other = _de(self.lab_of(p["pe_unsettled"]),
                      _lab(rr["pe_unsettled_other"]))
        want(r2(d_other) == r2(SAME_READING + 0.01), f"other reading {d_other}")
        want(above(self.err(p["pe_unsettled"], rr["pe_unsettled_other"]), pel),
             "the unsettled re-read is past the limit")
        facts["rereads"] = {"pe_over_same_apart": round(d_same, 4),
                            "pe_over_same_de": self.event_de(p["pe_over"],
                                                             rr["pe_over_same"]),
                            "pe_unsettled_other_apart": round(d_other, 4),
                            "pe_unsettled_other_de": self.event_de(
                                p["pe_unsettled"], rr["pe_unsettled_other"])}
        return facts


def design(kind: str, patches: "list[dict]", ranges: "dict | None" = None,
           seed: "str | None" = None) -> dict:
    """The scenario for *kind* on a chart of *patches* (``loc``, ``sid``,
    ``rgb`` 0..100, ``exyz`` 0..100, in reading order). *ranges* maps each
    location to its colour range (the app's own classification of the chart:
    ``patch_flags.colour_range_of_rgb`` for an RGB chart)."""
    if ranges is None:
        from workflow.patch_flags import colour_range_of_rgb
        ranges = {p["loc"]: colour_range_of_rgb(p["rgb"]) for p in patches}
    d = _Design(kind, patches, ranges, seed or f"edges-{kind}")
    facts = d.build()
    strips = sorted(d.strips, key=lambda s: (len(s), s))
    return {
        "kind": kind, "judged_as": JUDGED_AS[kind],
        "limits": dict(d.lim), "same_reading": SAME_READING,
        "kind_phrase": KIND_PHRASE[JUDGED_AS[kind]],
        "strips": strips, "strip_locs": d.strips,
        "plan": d.plan, "facts": facts,
        "patches": {loc: {"sid": p["sid"], "rgb": p["rgb"], "exyz": p["exyz"]}
                    for loc, p in d.patches.items()},
        "first": d.read, "rereads": d.rereads,
    }


# ---- the project ---------------------------------------------------------------
def _rgb_sets():
    """The patch sets: a profiling set (a 6-step cube and 108 more), a FROM
    PROFILE GAMUT set (the 8 cube corners and in-gamut colours) and a
    calibration set (7 ramps of 21 steps)."""
    r = random.Random(41)
    steps = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    prof = [(a, b, c) for a in steps for b in steps for c in steps]
    while len(prof) < 324:
        prof.append(tuple(round(r.uniform(0, 100), 1) for _ in range(3)))
    fpg = [(a, b, c) for a in (0, 100) for b in (0, 100) for c in (0, 100)]
    while len(fpg) < 240:
        fpg.append(tuple(round(r.uniform(8, 92), 1) for _ in range(3)))
    cal = []
    for i in range(21):
        v = i * 5.0
        cal += [(v, v, v), (v, 0.0, 0.0), (0.0, v, 0.0), (0.0, 0.0, v),
                (0.0, v, v), (v, 0.0, v), (v, v, 0.0)]
    return prof, fpg, cal


def build(dest: Path) -> Path:
    from make_demo_projects import _meta, _write_manifest
    from make_misread_demo import _build, _ti1_from_rgb, read_ti2, write_ti3
    root = dest / NAME
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    stem = NAME
    work = root / ".build"
    work.mkdir()
    prof, fpg, cal = _rgb_sets()
    _ti1_from_rgb(work / "prof.ti1", prof)
    _ti1_from_rgb(work / "fpg.ti1", fpg)
    _ti1_from_rgb(work / "cal.ti1", cal)
    charts = {"estimated": _build(root / FOLDERS["estimated"], stem,
                                  work / "prof.ti1", seed=17)}
    for kind in ("accurate", "verification", "verification_later"):
        d = root / FOLDERS[kind]
        d.mkdir(parents=True)
        for f in charts["estimated"].parent.glob(f"{stem}.*"):
            shutil.copy2(f, d / f.name)
        charts[kind] = d / f"{stem}.ti2"
    for ext in (".ti1", ".ti2"):
        p = root / FOLDERS["accurate"] / f"{stem}{ext}"
        txt = p.read_text(encoding="utf-8")
        p.write_text(txt.replace(
            "NUMBER_OF_FIELDS",
            'KEYWORD "ACCURATE_EXPECTED_VALUES"\n'
            'ACCURATE_EXPECTED_VALUES "true"\nNUMBER_OF_FIELDS', 1),
            encoding="utf-8")
    charts["verification_fpg"] = _build(root / FOLDERS["verification_fpg"],
                                        stem, work / "fpg.ti1", seed=23)
    charts["calibration"] = _build(root / FOLDERS["calibration"],
                                   f"{stem}-cal", work / "cal.ti1", seed=29)
    shutil.rmtree(work)
    for kind, ti2 in charts.items():
        patches = read_ti2(ti2)
        sc = design(kind, patches)
        sc["chart_rel"] = str(ti2.relative_to(root))
        ti2.with_suffix(".edges.json").write_text(json.dumps(sc, indent=1),
                                                  encoding="utf-8")
        write_ti3(ti2.with_suffix(".ti3"),
                  [{"sid": v["sid"], "loc": k, "rgb": v["rgb"]}
                   for k, v in sc["patches"].items()], sc["first"])
    _write_manifest(root, NAME, [
        {"id": "run1", "created_at": "2026-10-14T12:00:00", "parent": None},
        {"id": "run2", "created_at": "2026-10-14T12:30:00", "parent": "run1"},
    ], "run1", 3)
    _meta(root / "runs/run1", "run1", instrument="i1")
    _meta(root / "runs/run2", "run2", instrument="i1", parent_run="run1")
    (root / "settings.json").write_text(json.dumps(settings_values(), indent=1),
                                        encoding="utf-8")
    (root / "README.md").write_text(
        "# Demo-Limit-Edges\n\nMade by `scripts/make_limit_edge_demo.py` for "
        "Knut's beta-3 test (#182 6154440320). `settings.json` holds the "
        "unique limits of Preferences > Measurement it is measured with; "
        "each chart folder holds the chart, its first reading (`*.ti3`) and "
        "`*.edges.json`, the planted patches, their figures and the re-reads "
        "the on-screen protocol (`scripts/drive_b4_limit_edges.py`) "
        "replays.\n", encoding="utf-8")
    return root


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dest = Path(argv[0]) if argv else _HERE.parent / "demo-projects"
    root = build(dest)
    for f in sorted(root.rglob("*.edges.json")):
        sc = json.loads(f.read_text(encoding="utf-8"))
        fa = sc["facts"]
        print(f"{sc['kind']:20} judged as {sc['judged_as']:12} "
              f"PE {sc['limits']['pel']:.2f}: under {fa['pe_under']['de']:.2f} "
              f"on {fa['pe_on']['de']:.2f} over {fa['pe_over']['de']:.2f}; "
              f"NL {sc['limits']['nl']:.2f}: under {fa['nl_under']['further']:.4f} "
              f"on {fa['nl_on']['further']:.4f} over {fa['nl_over']['further']:.4f}; "
              f"fence {fa['fence']['fence']:.4f}: under "
              f"{fa['fence_under']['de']:.2f} over {fa['fence_over']['de']:.2f}"
              + ("; few " + sc["plan"]["nb_few"] if "nb_few" in sc["plan"] else ""))
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
