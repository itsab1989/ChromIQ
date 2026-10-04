"""(2c) A simulated measurement: chart x printer x fault -> readings.

    python -m tests.neighbour_campaign.simulate CHART PRINTER FAULT [--seed N]

writes ``<campaign>/cases/<case>/``:

* ``<stem>.ti3``     the first pass as a .ti3 (what chartread would save)
* ``replay.txt``     the ChromIQ engine's ``--replay`` script: one block per
                     strip with the FIRST-PASS readings (faults in), then one
                     block ``f<strip>`` per strip with what a RE-READ gives
                     (a misread gone, a print fault still there), for
                     ``{"cmd":"swipe","as":"f<strip>"}``
* ``truth.json``     the ground truth: every affected patch, how and by how
                     much, the fault's notes, and each patch's numbers

The sheet: the printer profile's colour of each patch, the scatter of a
real print (0.6 ΔE rms), then the print fault. The reading: the sheet plus
the instrument's repeatability (0.1 ΔE), then the misread. A re-read is the
sheet read again (new repeatability noise, no misread).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass

import numpy as np

from tests.neighbour_campaign.chart import Chart, load_chart
from tests.neighbour_campaign.common import CASES
from tests.neighbour_campaign.faults import FAULTS, Ctx
from tests.neighbour_campaign.printers import load as load_printer
from tests.neighbour_campaign.printers import print_noise, write_rgb_ti3

PRINT_NOISE_DE = 0.6
INSTR_NOISE_DE = 0.1


@dataclass
class Case:
    name: str
    chart: Chart
    printer: str
    fault: str
    seed: int
    print_xyz: np.ndarray
    read_xyz: np.ndarray      # first pass
    reread_xyz: np.ndarray    # a re-read of every patch
    affected: dict
    notes: dict
    target: str               # "reading" | "print"

    @property
    def mode(self) -> str:
        return self.chart.mode


def case_name(chart: str, printer: str, fault: str, seed: int) -> str:
    return f"{chart}__{printer}__{fault}__s{seed}"


def simulate(chart, printer: str, fault: str, seed: int = 1) -> Case:
    c = chart if isinstance(chart, Chart) else load_chart(chart)
    f = FAULTS[fault]
    if c.mode not in f.modes:
        raise ValueError(f"{fault} does not apply to a {c.mode} chart")
    h = int(hashlib.sha1(f"{c.name}|{printer}|{fault}|{seed}".encode())
            .hexdigest()[:8], 16)
    rng = np.random.default_rng(h)
    pr = load_printer(printer)
    clean = pr.xyz(c.rgb)
    sheet = print_noise(clean, rng, PRINT_NOISE_DE)
    ctx = Ctx(chart=c, printer=pr, rng=rng, clean_xyz=clean,
              print_xyz=sheet.copy(), read_xyz=sheet.copy(),
              instr_noise=INSTR_NOISE_DE)
    if f.target == "print":
        res = f.apply(ctx)
        ctx.read_xyz = ctx.noisy(ctx.print_xyz)
    else:
        ctx.read_xyz = ctx.noisy(ctx.print_xyz)
        res = f.apply(ctx)
    reread = ctx.noisy(ctx.print_xyz)
    return Case(name=case_name(c.name, printer, fault, seed), chart=c,
                printer=printer, fault=fault, seed=seed,
                print_xyz=ctx.print_xyz, read_xyz=ctx.read_xyz,
                reread_xyz=reread, affected=res.affected, notes=res.notes,
                target=f.target)


def replay_text(case: Case) -> str:
    c = case.chart
    members = c.strip_members()
    steps = max(len(v) for v in members.values())
    out = [f"# ChromIQ neighbour campaign: {case.name}",
           f"# blocks f<strip> are what a re-read gives", f"PATCHES {steps}"]
    for prefix, arr in (("", case.read_xyz), ("f", case.reread_xyz)):
        for s in c.strip_order:
            out.append(f"STRIP {prefix}{s}")
            for i in members[s]:
                out.append(" ".join(f"{max(0.0, v):.4f}" for v in arr[i]))
    if len(c.strip_order) * 2 > 512:
        raise ValueError("more than 512 replay blocks")
    return "\n".join(out) + "\n"


def write_case(case: Case, root=None) -> "object":
    d = (root or CASES) / case.name
    d.mkdir(parents=True, exist_ok=True)
    c = case.chart
    write_rgb_ti3(d / f"{c.stem}.ti3", c.rgb, case.read_xyz, locs=c.locs,
                  descriptor=f"simulated: {case.name}",
                  instrument="X-Rite CR30" if c.instrument == "CR30"
                  else "GretagMacbeth i1 Pro")
    if c.mode == "strip":
        (d / "replay.txt").write_text(replay_text(case))
    truth = {"case": case.name, "chart": c.name, "printer": case.printer,
             "fault": case.fault, "target": case.target, "seed": case.seed,
             "affected": case.affected, "notes": case.notes,
             "patches": {loc: {"strip": c.strips[i],
                               "rgb": [round(v, 3) for v in c.rgb[i]],
                               "expected": [round(v, 4) for v in c.exp_xyz[i]],
                               "sheet": [round(v, 4) for v in case.print_xyz[i]],
                               "read": [round(v, 4) for v in case.read_xyz[i]],
                               "reread": [round(v, 4) for v in case.reread_xyz[i]]}
                         for i, loc in enumerate(c.locs)}}
    (d / "truth.json").write_text(json.dumps(truth))
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chart")
    ap.add_argument("printer")
    ap.add_argument("fault")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    case = simulate(a.chart, a.printer, a.fault, a.seed)
    d = write_case(case)
    print(d)
    print(json.dumps({"affected": len(case.affected), "notes": case.notes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
