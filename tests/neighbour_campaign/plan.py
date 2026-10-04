"""(4a) The plan for an ON-SCREEN run of one case, and the check of what the
real Measure tab drew against what the emulator expects.

    python -m tests.neighbour_campaign.plan CHART PRINTER FAULT [--seed N] [--cards LOC ...]
        -> cases/<case>/plan.json (+ .ti3, replay.txt, truth.json)
    python -m tests.neighbour_campaign.plan --compare <driver out dir>

CHART may be ``v:<chart>``: the chart measured as a VERIFICATION, judged
against the printer's run profile's prediction (limit 10, no strip fence, no
neighbour check, no misread summary). A ``pc-*`` chart is a chart made from a
pre-conditioning profile (limit 20, neighbour check on).

The order a driver reads in is the order the plan says, so the emulator and
the app see the same readings in the same order:

1. every strip but the last, in reading order (a "Was a strip read twice?"
   question answered as the plan says, and when that is "Re-read", the strip
   at once again with its true colours);
2. every strip that has a red outline at that point, read again (the replay's
   ``f<strip>`` block: a misread gone, a print fault still there);
3. the last strip, which ends the measurement, so the closing window shows
   the summary of everything before it.

After each step the plan holds the outlines the emulator expects (red,
yellow, green); the driver writes the outlines the tab drew
(``outlines.json``) and ``--compare`` lists every difference, the closing
window's misread lines included. Hover cards are photographed for the plan's
``cards``: by default up to three patches that turn red (a misread, a print
fault, a false red; the neighbour check's and the limit's both where the case
has them), after the step each turns red and after its strip is read again.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tests.neighbour_campaign.chart import load_chart
from tests.neighbour_campaign.common import CHARTS, REPO, neighbour_module
from tests.neighbour_campaign.judge import TabEmulator
from tests.neighbour_campaign.run_campaign import chart_kind
from tests.neighbour_campaign.simulate import simulate, write_case


def _german():
    cat = json.loads((REPO / "data" / "i18n" / "de.json").read_text())
    return lambda s: cat.get(s) or s


def make_plan(chart_name, printer, fault, seed=1, cards=None, buffer=10.0,
              max_cards=3) -> Path:
    kind, base = chart_kind(chart_name)
    c = load_chart(base)
    if c.mode != "strip":
        raise SystemExit("the engine replay reads strips; a CR30 case runs in "
                         "the emulator only")
    case = simulate(c, printer, fault, seed)
    case.name = (f"v-{case.name}" if kind == "verification" else case.name)
    d = write_case(case)
    mod, commit = neighbour_module()
    exp = None
    profile = None
    if kind == "verification":
        from tests.neighbour_campaign.profiles import predicted_xyz, run_profile
        exp = predicted_xyz(c, printer)
        profile = str(run_profile(printer))
        # The run's own profiling measurement (a clean read), so the run is
        # a finished one with a measurement and a profile.
        from tests.neighbour_campaign.printers import write_rgb_ti3
        clean = simulate(c, printer, "none", 77)
        write_rgb_ti3(d / "profiling.ti3", c.rgb, clean.read_xyz, locs=c.locs,
                      descriptor="clean simulated profiling read")
    emu = TabEmulator(c, kind=kind, buffer=buffer, nb_mod=mod, expected_xyz=exp)
    members = c.strip_members()
    rd = {loc: case.read_xyz[i] for i, loc in enumerate(c.locs)}
    rr = {loc: case.reread_xyz[i] for i, loc in enumerate(c.locs)}
    wrong = case.fault.startswith("wrong_strip") and case.notes.get("strip")
    steps, expected, reasons = [], [], []

    def snap():
        o = emu.outlines()
        expected.append({
            "red": sorted(l for l, v in o.items() if v == "red"),
            "yellow": sorted(l for l, v in o.items() if v.startswith("yellow")),
            "green": sorted(l for l, v in o.items() if v == "green")})
        reasons.append({l: emu.red_reason(l) for l, v in o.items() if v == "red"})

    def read(s, again=False, why=""):
        vals = {c.locs[i]: (rr if again else rd)[c.locs[i]] for i in members[s]}
        found = emu.read_strip(s, vals)
        step = {"strip": s, "as": f"f{s}" if again else None, "why": why}
        real = found is not None and s == wrong
        if found is not None:
            step["read_twice"] = {"like": found.like,
                                  "choice": "reread" if real else "keep"}
            emu.read_twice_log.append((s, found.like, step["read_twice"]["choice"]))
            if real:
                emu.set_aside(s)
            else:
                emu.keep(s)
        steps.append(step)
        snap()
        if real:
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
        cards, seen_reason = [], set()
        firsts = []
        for k, e in enumerate(expected):
            for l in e["red"]:
                if l not in [x for x, _ in firsts]:
                    firsts.append((l, reasons[k].get(l, "")))
        # one per reason first (neighbour, limit, both), misreads first
        for want_aff in (True, False):
            for l, why in firsts:
                if (l in aff) == want_aff and why not in seen_reason \
                        and len(cards) < max_cards:
                    cards.append(l)
                    seen_reason.add(why)
        for l, _ in firsts:
            if len(cards) >= max_cards:
                break
            if l not in cards:
                cards.append(l)
    photos = []
    for loc in cards:
        s = c.strips[c.index()[loc]]
        first = next((k for k, e in enumerate(expected) if loc in e["red"]), None)
        again = next((k for k, st in enumerate(steps)
                      if st["strip"] == s and st["as"] and first is not None
                      and k > first), None)
        if first is not None:
            photos.append({"after_step": first, "loc": loc, "name": f"red-{loc}"})
        if again is not None:
            photos.append({"after_step": again, "loc": loc,
                           "name": f"after-reread-{loc}"})
    info = json.loads((CHARTS / base / "chart.json").read_text())
    plan = {"case": case.name, "chart": chart_name, "base": base, "kind": kind,
            "printer": printer, "fault": fault, "seed": seed, "buffer": buffer,
            "limit": emu.limit, "nb_commit": commit, "project": info["project"],
            "stem": info["stem"], "patches": c.n,
            "project_dir": str(CHARTS / base / info["project"]),
            "run_profile": profile,
            "profiling_ti3": str(d / "profiling.ti3") if profile else None,
            "replay": str(d / "replay.txt"), "affected": case.affected,
            "notes": case.notes, "steps": steps, "expected": expected,
            "reasons": reasons, "photos": photos,
            "summary_expected": emu.summary_facts(),
            "summary_text_expected": {
                "en": emu.misread_summary(),
                "de": emu.misread_summary(tr=_german())},
            "read_twice_expected": emu.read_twice_log}
    (d / "plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False))
    return d / "plan.json"


def compare(out_dir: Path) -> int:
    got = json.loads((out_dir / "outlines.json").read_text())
    plan = json.loads((out_dir / "plan.json").read_text())
    lang = got.get("lang", "en")
    diffs = 0
    lines = []
    for k, (e, g) in enumerate(zip(plan["expected"], got["steps"])):
        for kind in ("red", "yellow", "green"):
            a, b = set(e.get(kind, [])), set(g.get(kind, []))
            if a != b:
                diffs += 1
                lines.append(f"step {k} ({plan['steps'][k]['strip']}"
                             f"{' again' if plan['steps'][k]['as'] else ''}) {kind}: "
                             f"expected only {sorted(a - b)}, app only {sorted(b - a)}")
    if len(got["steps"]) != len(plan["expected"]):
        diffs += 1
        lines.append(f"steps: plan {len(plan['expected'])}, app {len(got['steps'])}")
    s_exp, s_got = plan["summary_expected"], got.get("summary")
    if (s_exp or {}).get("red") != (s_got or {}).get("red") or \
            (s_exp or {}).get("kept") != (s_got or {}).get("kept"):
        diffs += 1
        lines.append(f"summary facts: expected {s_exp}, app {s_got}")
    t_exp = plan["summary_text_expected"][lang]
    t_got = got.get("misread_summary", "")
    # Asked AFTER the session ended, the tab no longer adds the "Strip read
    # twice" lines (that check watches a live session only); the closing
    # window, checked below, carries them.
    twice = ("Strip read twice", "Streifen doppelt", "Streifen, die doppelt")
    t_exp_after = "\n".join(x for x in t_exp.split("\n")
                            if not x.startswith(twice))
    if t_exp_after != "\n".join(x for x in t_got.split("\n")
                                if not x.startswith(twice)):
        diffs += 1
        lines.append(f"misread summary text: expected {t_exp!r}, app {t_got!r}")
    # The closing window must carry those lines (or none, for a verification).
    closing = [w for w in json.loads((out_dir / "windows.json").read_text())
               if w.get("closing")]
    if closing:
        text = closing[-1]["text"]
        for ln in [x for x in t_exp.split("\n") if x]:
            if ln not in text:
                diffs += 1
                lines.append(f"closing window lacks {ln!r}")
        if plan["kind"] == "verification":
            for word in ("Neighbour check", "Nachbar", "Strip read twice",
                         "corrected by a re-read"):
                if word in text:
                    diffs += 1
                    lines.append(f"verification's closing window has {word!r}")
    else:
        diffs += 1
        lines.append("no closing window recorded")
    lines.append(f"{len(got['steps'])} steps compared, {diffs} differences")
    print("\n".join(lines))
    (out_dir / "compare.txt").write_text("\n".join(lines) + "\n")
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
