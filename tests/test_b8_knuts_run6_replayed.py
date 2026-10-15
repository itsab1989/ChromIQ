"""Knut's run 6, replayed through the judging (#182, 4.3.5 beta 8).

His verification of 2026-10-14 (``tests/data/knut_run6``, from his
``chromiq.log``: every strip the engine reported, with the run profile's
prediction as the expected colours, as ``workflow.verify_expected`` works
them out). The session as the log shows it: strip A read at patch error
limit 5 / neighbour limit 5, then resumed at 15 / 7, strip A painted from the
file and read again, and strips B to L.

Knut, #182 6196599132, approving the rule recommended in 6188066945: *"In
run 6 it turns C18, E27, F27 and F2 yellow by similar patches and C27 and E22
yellow through their range (green then has more than 3 confirmations); I27
and I11 stay red (same strip)."* Asserted here at his 15 / 7, and at the
neighbour limit 5 he moved to later (where I27 and I11 also stand out).

The glue is the Measure tab's own order of calls (``_neighbour_feed`` ->
``_judge_with_neighbours`` -> ``FlagJudge.judge``, then ``_neighbour_rejudge``
and ``rejudge``); the rules are the product's modules. The same replay runs
in the real window on screen in ``scripts/drive_b8_run6_similar_patches.py``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import patch_flags as pf
from workflow.icc_info import xyz_to_lab
from workflow.misread_settings import above
from workflow.neighbour_check import NeighbourCheck

DATA = Path(__file__).resolve().parent / "data" / "knut_run6" / \
    "run6_verification.json"
RADIUS = 30.0          # verification charts' colour-neighbour radius
SAME = 3.0


def _strip_of(loc: str) -> str:
    return "".join(c for c in loc if c.isalpha())


def _lab(xyz):
    return xyz_to_lab(tuple(float(v) / 100.0 for v in xyz[:3]))


class _Replay:
    """The tab's judging glue, strip by strip, strip test off (a
    verification chart's default)."""

    def __init__(self, data, limit, nb_limit):
        self.limit = float(limit)
        self.judge = pf.FlagJudge(white=data["white"],
                                  device_ranges=data["device_ranges"],
                                  same_reading_de=SAME, peer_radius=RADIUS)
        self.nc = NeighbourCheck(radius=RADIUS, limit=nb_limit)
        self.inputs: dict = {}
        self.verdicts: dict = {}

    def _judge(self, loc, warn, f, live):
        exp_lab, meas_lab, de = self.inputs[loc]
        sus = f is not None and f.suspect
        self.verdicts[loc] = self.judge.judge(
            loc, exp_lab, meas_lab, de, warn or sus, live=live,
            strip=_strip_of(loc), reread_only=sus, limit=self.limit,
            warn=warn)

    def strip(self, patches, live=True):
        for p in patches:
            self.nc.set_reading(p["loc"], p["exyz"], p["xyz"],
                                _strip_of(p["loc"]))
        changed = self.nc.evaluate()
        for loc, f in self.nc.updated().items():
            if f.suspect:
                changed.setdefault(loc, f)
        done = set()
        for p in patches:
            loc = p["loc"]
            self.inputs[loc] = (_lab(p["exyz"]), _lab(p["xyz"]), float(p["de"]))
            self._judge(loc, above(p["de"], self.limit), self.nc.finding(loc),
                        live)
            done.add(loc)
        for loc, f in changed.items():
            if loc in done or loc not in self.inputs:
                continue
            self._judge(loc, above(self.inputs[loc][2], self.limit), f, False)
        self.verdicts.update(self.judge.rejudge())

    def colour(self, loc) -> str:
        f = self.verdicts[loc].flag
        if f is True:
            return "red"
        if f is False:
            return "none"
        return {pf.FLAG_CONFIRMED: "yellow (confirmed)",
                pf.FLAG_LEARNED: "yellow (learned)",
                pf.FLAG_CORRECTED: "green"}[f]

    def tally(self) -> dict:
        out: dict = {}
        for loc in self.verdicts:
            c = self.colour(loc)
            out[c] = out.get(c, 0) + 1
        return out


def _session(limit, nb_limit):
    data = json.loads(DATA.read_text(encoding="utf-8"))
    ev = data["events"]
    first = _Replay(data, 5.0, 5.0)          # the session that read strip A
    first.strip(ev[0]["patches"])
    memory = first.judge.export()
    tab = _Replay(data, limit, nb_limit)     # resumed at Knut's 15 / 7
    tab.judge.load(memory)
    tab.strip(ev[0]["patches"], live=False)  # strip A painted from the file
    for e in ev[1:]:                         # A read again, then B to L
        tab.strip(e["patches"])
    return tab


@pytest.fixture(scope="module")
def at_15_7():
    return _session(15.0, 7.0)


@pytest.mark.parametrize("loc", ["C18", "E27", "F27", "F2"])
def test_yellow_by_similar_patches(at_15_7, loc):
    v = at_15_7.verdicts[loc]
    assert at_15_7.colour(loc) == "yellow (confirmed)", loc
    assert v.pe_state == pf.STATE_PEER and v.peer_locs
    assert v.prev_de is None                   # nobody read it again
    # every similar patch: another strip, the same (green) range
    for q in v.peer_locs:
        assert _strip_of(q) != _strip_of(loc)
        assert at_15_7.verdicts[q].colour_range == v.colour_range == "green"


@pytest.mark.parametrize("loc", ["C27", "E22"])
def test_yellow_through_their_colour_range(at_15_7, loc):
    v = at_15_7.verdicts[loc]
    assert at_15_7.colour(loc) == "yellow (learned)"
    assert v.colour_range == "green" and v.range_k == 3 and v.like_loc


@pytest.mark.parametrize("loc", ["I27", "I11"])
def test_i27_and_i11_stay_red(at_15_7, loc):
    v = at_15_7.verdicts[loc]
    assert at_15_7.colour(loc) == "red"
    assert v.pe_state == pf.STATE_RED and v.peer_locs == ()


def test_i27_and_i11_are_of_one_strip_so_never_each_others(at_15_7):
    j = at_15_7.judge
    assert _strip_of("I27") == _strip_of("I11") == "I"
    assert "I11" not in j._raw[pf.TEST_PE].get("I27", ())


def test_a1_and_a22_are_confirmed_by_their_re_read(at_15_7):
    for loc in ("A1", "A22"):
        v = at_15_7.verdicts[loc]
        assert v.flag == pf.FLAG_CONFIRMED and v.prev_de is not None


def test_at_neighbour_limit_5_i27_and_i11_stand_out_too():
    tab = _session(15.0, 5.0)
    for loc in ("I27", "I11"):
        v = tab.verdicts[loc]
        assert tab.colour(loc) == "red"
        assert (v.pe_state, v.nb_state) == (pf.STATE_RED, pf.STATE_RED)
    for loc in ("C18", "E27", "F27", "F2"):
        assert tab.colour(loc) == "yellow (confirmed)", loc
    for loc in ("C27", "E22"):
        assert tab.colour(loc) == "yellow (learned)", loc


def test_the_whole_sheet_at_15_7(at_15_7):
    """The counts Knut asked for (6191537939: "What is the change in the
    fault statistics with this rule?"): beta 7 drew 81 red, 8 confirmed, 18
    learned of the 324 (the b7b analysis, ``out/run6_variants.json``)."""
    t = at_15_7.tally()
    assert sum(t.values()) == 324
    assert t.get("red", 0) == 21
    assert t.get("yellow (confirmed)", 0) == 50
    assert t.get("yellow (learned)", 0) == 36
