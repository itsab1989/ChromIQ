"""(1b) Profiles for the two chart kinds the first run did not have.

    python -m tests.neighbour_campaign.profiles     # profiles, pc charts, predictions

* **A pre-conditioning profile per printer**: colprof (``-qm``) from a
  simulated CLEAN read of the 210-patch chart on that printer, as a user's
  first rough profile is. From it, charts MADE FROM A PROFILE
  (``targen -c``, ``ACCURATE_EXPECTED_VALUES``): ``pc-<printer>-i1-0200``,
  ``-i1-1000`` and ``-i1-4200``, small, medium and large. Their expected
  colours are the rough profile's prediction, so they are close to the
  print but not equal to it (the rough profile's own error).
* **A run profile per printer**: colprof from a simulated clean read of the
  2016-patch chart, the profile a verification is judged against. Its
  forward table (``xicclu -ff -ia``, absolute, as
  ``workflow/verify_expected.py`` asks it) is the "prediction" of every patch
  of a verification chart printed raw: :func:`predicted_xyz`.

Everything goes under ``<campaign>/fixtures/profiles`` and ``charts``.
"""
from __future__ import annotations

import json

import numpy as np

from tests.neighbour_campaign.chart import Chart, load_chart
from tests.neighbour_campaign.common import CAMPAIGN, CHARTS, argyll, run_tool
from tests.neighbour_campaign.printers import PRINTER_PLAN, write_rgb_ti3

PROFILES = CAMPAIGN / "fixtures" / "profiles"
#: The chart a profile is built from, and the seed of its clean read.
ROUGH_FROM, RUN_FROM = ("i1-0200", 101), ("i1-2000", 102)
PC_SIZES = {"i1-0200": ("i1", 200, False), "i1-1000": ("i1", 1000, False),
            "i1-4200": ("i1", 4200, False)}


def pc_name(printer: str, size: str) -> str:
    return f"pc-{printer}-{size}"


def _profile(printer: str, src: tuple, role: str) -> "object":
    from tests.neighbour_campaign.simulate import simulate
    PROFILES.mkdir(parents=True, exist_ok=True)
    icc = PROFILES / f"{printer}-{role}.icc"
    if icc.exists():
        return icc
    chart, seed = src
    case = simulate(chart, printer, "none", seed)
    stem = f"{printer}-{role}"
    write_rgb_ti3(PROFILES / f"{stem}.ti3", case.chart.rgb, case.read_xyz,
                  descriptor=f"clean simulated read of {chart} on {printer}")
    run_tool([argyll("colprof"), "-v0", "-qm", "-D",
              f"{printer} {role} (simulated, {chart})", stem],
             cwd=PROFILES, timeout=1800)
    return icc


def rough_profile(printer: str):
    return _profile(printer, ROUGH_FROM, "precond")


def run_profile(printer: str):
    return _profile(printer, RUN_FROM, "run")


def xicclu_forward(icc, rgb100: np.ndarray) -> np.ndarray:
    """XYZ 0..100 of device RGB 0..100 through *icc*'s forward table,
    absolute colorimetric (as verify_expected's ``forward_xyz``)."""
    text = "\n".join(f"{r / 100:.6f} {g / 100:.6f} {b / 100:.6f}"
                     for r, g, b in rgb100) + "\n"
    out = run_tool([argyll("xicclu"), "-v0", "-ff", "-ia", "-pX", str(icc)],
                   stdin_text=text, timeout=600)
    vals = np.array([[float(v) for v in ln.split()[:3]]
                     for ln in out.splitlines() if ln.strip()])
    if vals[:, 1].max() <= 2.0:
        vals = vals * 100.0
    return vals


def predicted_xyz(chart: "Chart | str", printer: str) -> np.ndarray:
    """The run profile's prediction of every patch of *chart* (printed raw)."""
    c = chart if isinstance(chart, Chart) else load_chart(chart)
    path = PROFILES / f"pred-{c.name}-{printer}.npy"
    if path.exists():
        return np.load(path)
    vals = xicclu_forward(run_profile(printer), c.rgb)
    np.save(path, vals)
    return vals


def build_all() -> dict:
    from tests.neighbour_campaign.make_charts import build_one
    out = {}
    for printer in PRINTER_PLAN:
        rough_profile(printer)
        run_profile(printer)
        for size, spec in PC_SIZES.items():
            name = pc_name(printer, size)
            info = build_one(name, plan={name: spec},
                             precond_icc=rough_profile(printer), printer=printer)
            out[name] = info
            print(json.dumps(info))
    idx = CHARTS / "charts.json"
    old = json.loads(idx.read_text()) if idx.exists() else {}
    old.update(out)
    idx.write_text(json.dumps(old, indent=1))
    return out


if __name__ == "__main__":
    build_all()
