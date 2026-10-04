"""A campaign chart as the simulator needs it: every patch with its location,
strip, device RGB, ESTIMATED expected colour (the ``.ti2``'s XYZ, which is
what the engine judges against) and where it sits on the page (mm)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tests.neighbour_campaign.common import (CHARTS, patch_no, strip_key,
                                             strip_of)


def read_cgats(path: Path):
    """``(fields, rows, keywords)`` of a CGATS file; rows are lists of str."""
    fields, rows, kw = [], [], {}
    in_fmt = in_data = False
    for ln in Path(path).read_text(errors="replace").splitlines():
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True
        elif s == "END_DATA_FORMAT":
            in_fmt = False
        elif in_fmt:
            fields += s.split()
        elif s == "BEGIN_DATA":
            in_data = True
        elif s == "END_DATA":
            in_data = False
        elif in_data and s:
            rows.append(s.replace('"', "").split())
        elif s and not in_data and " " in s:
            k, _, v = s.partition(" ")
            kw[k] = v.strip().strip('"')
    return fields, rows, kw


@dataclass
class Chart:
    name: str
    instrument: str
    hexagons: bool
    run_dir: Path
    stem: str
    locs: list            # reading order
    strips: list          # strip label per patch
    strip_order: list     # strip labels in reading order
    rgb: np.ndarray       # [N,3] 0..100
    exp_xyz: np.ndarray   # [N,3] 0..100, the .ti2's estimate
    page: np.ndarray      # [N]
    cx: np.ndarray        # [N] mm, patch centre
    cy: np.ndarray
    w: np.ndarray         # [N] mm
    h: np.ndarray
    paper_mm: tuple

    @property
    def n(self) -> int:
        return len(self.locs)

    @property
    def mode(self) -> str:
        """How it is read: "strip" (i1Pro) or "patch" (CR30, patch by patch)."""
        return "patch" if self.instrument == "CR30" else "strip"

    @property
    def ti2(self) -> Path:
        return self.run_dir / f"{self.stem}.ti2"

    def index(self) -> dict:
        return {loc: i for i, loc in enumerate(self.locs)}

    def strip_members(self) -> dict:
        out: dict = {}
        for i, s in enumerate(self.strips):
            out.setdefault(s, []).append(i)
        return out


def load_chart(name: str) -> Chart:
    info = json.loads((CHARTS / name / "chart.json").read_text())
    run = CHARTS / info["run_dir"]
    stem = info["stem"]
    fields, rows, _kw = read_cgats(run / f"{stem}.ti2")
    ix = {f: i for i, f in enumerate(fields)}
    by_loc = {}
    for r in rows:
        loc = r[ix["SAMPLE_LOC"]]
        by_loc[loc] = ([float(r[ix[f]]) for f in ("RGB_R", "RGB_G", "RGB_B")],
                       [float(r[ix[f]]) for f in ("XYZ_X", "XYZ_Y", "XYZ_Z")])
    layout = json.loads((run / f"{stem}.channels.json").read_text())["layout"]
    dpi = float(layout.get("dpi", 300))
    mm = 25.4 / dpi
    geo = {p["loc"]: p for p in layout["patches"]}
    locs = sorted(by_loc, key=lambda l: (strip_key(strip_of(l)), patch_no(l)))
    strips = [strip_of(l) for l in locs]
    order = sorted(set(strips), key=strip_key)
    g = [geo[l] for l in locs]
    return Chart(
        name=name, instrument=info["instrument"], hexagons=bool(info["hex"]),
        run_dir=run, stem=stem, locs=locs, strips=strips, strip_order=order,
        rgb=np.array([by_loc[l][0] for l in locs]),
        exp_xyz=np.array([by_loc[l][1] for l in locs]),
        page=np.array([p["page"] for p in g]),
        cx=np.array([(p["x"] + p["w"] / 2) * mm for p in g]),
        cy=np.array([(p["y"] + p["h"] / 2) * mm for p in g]),
        w=np.array([p["w"] * mm for p in g]),
        h=np.array([p["h"] * mm for p in g]),
        paper_mm=tuple(layout.get("paper_mm", (210.0, 297.0))))


def list_charts() -> list:
    idx = CHARTS / "charts.json"
    return list(json.loads(idx.read_text())) if idx.exists() else []
