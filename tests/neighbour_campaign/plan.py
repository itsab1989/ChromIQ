"""(4a) The plan for an ON-SCREEN run of one case, and the check of what the
real Measure tab drew against what the emulator expects.

    python -m tests.neighbour_campaign.plan CHART PRINTER FAULT [--seed N] [--cards LOC ...]
        -> cases/<case>/plan.json (+ .ti3, replay.txt, truth.json)
    python -m tests.neighbour_campaign.plan --compare <driver out dir>

The order a driver reads in is the order the plan says, so the emulator and
the app see the same readings in the same order:

1. every strip but the last, in reading order (a "Was a strip read twice?"
   question answered as the plan says, and when that is "Re-read", the strip
   at once again with its true colours);
2. every strip that has a red outline at that point, read again (the replay's
   ``f<strip>`` block: a misread gone, a print fault still there);
3. the last strip, which ends the measurement, so the closing window shows
   the summary of everything before it.

After each step the plan holds the outlines the emulator expects; the driver
writes the outlines the tab drew (``outlines.json``) and ``--compare`` lists
every difference. Hover cards are photographed for the plan's ``cards``: by
default each ground-truth patch that turns red, after the step it turns red
and after its strip is read again.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.neighbour_campaign.chart import load_chart
from tests.neighbour_campaign.common import CASES, CHARTS, neighbour_module
from tests.neighbour_campaign.judge import TabEmulator
from tests.neighbour_campaign.simulate import simulate, write_case


def make_plan(chart_name, printer, fault, seed=1, cards=None, buffer=10.0,
              max_cards=2) -> Path:
    c = load_chart(chart_name)
    if c.mode != "strip":
        raise SystemExit("the engine replay reads strips; a CR30 case runs in "
                         "the emulator only")
    case = simulate(c, printer, fault, seed)
    d = write_case(case)
    mod, commit = neighbour_module()
    emu = TabEmulator(c, buffer=buffer, nb_mod=mod)
    members = c.strip_members()
    rd = {loc: case.read_xyz[i] for i, loc in enumerate(c.locs)}
    rr = {loc: case.reread_xyz[i] for i, loc in enumerate(c.locs)}
    wrong = case.fault.startswith("wrong_strip") and case.notes.get("strip")
    steps, expected = [], []

    def snap():
        o = emu.outlines()
        expected.append({"red": sorted(l for l, v in o.items() if v == "red"),
                         "yellow": sorted(l for l, v in o.items() if v != "red")})

    def read(s, again=False, why=""):
        vals = {c.locs[i]: (rr if again else rd)[c.locs[i]] for i in members[s]}
        found = emu.read_strip(s, vals)
        step = {"strip": s, "as": f"f{s}" if again else None, "why": why}
        if found is not None:
            real = s == wrong
            step["read_twice"] = {"like": found.like,
                                  "choice": "reread" if real else "keep"}
            emu.read_twice_log.append((s, found.like, step["read_twice"]["choice"]))
        steps.append(step)
        snap()
        if found is not None and s == wrong:
            read(s, True, "re-read asked by Was a strip read twice?")

    order = c.strip_order
    for s in order[:-1]:
        read(s)
    red_now = set(expected[-1]["red"]) if expected else set()
    for s in order[:-1]:
        if any(c.strips[c.index()[l]] == s for l in red_now):
            read(s, True, "re-read: a red outline in it")
    read(order[-1], why="last strip: ends the measurement")
    aff = set(case.affected)
    if cards is None:
        cards = []
        for k, e in enumerate(expected):
            for l in e["red"]:
                if l in aff and l not in cards:
                    cards.append(l)
        cards = cards[:max_cards]
    photos = []
    for loc in cards:
        s = c.strips[c.index()[loc]]
        first = next((k for k, e in enumerate(expected) if loc in e["red"]), None)
        again = next((k for k, st in enumerate(steps)
                      if st["strip"] == s and st["as"]), None)
        if first is not None:
            photos.append({"after_step": first, "loc": loc, "name": f"red-{loc}"})
        if again is not None:
            photos.append({"after_step": again, "loc": loc,
                           "name": f"after-reread-{loc}"})
    info = json.loads((CHARTS / chart_name / "chart.json").read_text())
    plan = {"case": case.name, "chart": chart_name, "printer": printer,
            "fault": fault, "seed": seed, "buffer": buffer,
            "nb_commit": commit, "project": info["project"],
            "project_dir": str(CHARTS / chart_name / info["project"]),
            "replay": str(d / "replay.txt"), "affected": case.affected,
            "notes": case.notes, "steps": steps, "expected": expected,
            "photos": photos, "summary_expected": emu.summary_facts(),
            "read_twice_expected": emu.read_twice_log}
    (d / "plan.json").write_text(json.dumps(plan, indent=1))
    return d / "plan.json"


def compare(out_dir: Path) -> int:
    got = json.loads((out_dir / "outlines.json").read_text())
    plan = json.loads((out_dir / "plan.json").read_text())
    diffs = 0
    for k, (e, g) in enumerate(zip(plan["expected"], got["steps"])):
        for kind in ("red", "yellow"):
            a, b = set(e[kind]), set(g[kind])
            if a != b:
                diffs += 1
                print(f"step {k} ({plan['steps'][k]['strip']}"
                      f"{' again' if plan['steps'][k]['as'] else ''}) {kind}: "
                      f"expected only {sorted(a - b)}, app only {sorted(b - a)}")
    if len(got["steps"]) != len(plan["expected"]):
        diffs += 1
        print(f"steps: plan {len(plan['expected'])}, app {len(got['steps'])}")
    s_exp, s_got = plan["summary_expected"], got.get("summary")
    if (s_exp or {}).get("red") != (s_got or {}).get("red") or \
            (s_exp or {}).get("kept") != (s_got or {}).get("kept"):
        diffs += 1
        print(f"summary facts: expected {s_exp}, app {s_got}")
    print(f"{len(got['steps'])} steps compared, {diffs} differences")
    return 1 if diffs else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chart", nargs="?")
    ap.add_argument("printer", nargs="?")
    ap.add_argument("fault", nargs="?")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--cards", nargs="*")
    ap.add_argument("--compare", type=Path)
    a = ap.parse_args(argv)
    if a.compare:
        return compare(a.compare)
    print(make_plan(a.chart, a.printer, a.fault, a.seed, a.cards))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
