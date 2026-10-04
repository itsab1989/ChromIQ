"""(1) Real ChromIQ charts for the campaign, small to the largest.

    python -m tests.neighbour_campaign.make_charts [--only NAME ...] [--force]

Each chart is made the way Guided makes an RGB profiling chart: ArgyllCMS
``targen -d2 -f<N> -e4 -B4 -G`` (Guided's defaults, ``ChartCreator.
_build_targen_args``), laid out by ChromIQ's own engine
(:func:`workflow.layout_engine.chart.build_chart`) with Guided's engine
keywords (``ChartCreator._engine_build_kwargs``: randomised, edge spacers and
the notes clip band for an i1Pro; patch-first, no spacers and hexagons for a
CR30 honeycomb), and the ``channels.json`` sidecar the app writes, exactly as
``scripts/make_demo_projects._chart_files`` folds it. So the chart's patch
order, strips, locations, padding and estimated expected colours (the
``.ti2``'s XYZ) are what a user's chart has.

Every chart is wrapped in a ChromIQ project (``project.json`` + ``runs/run1``)
so the on-screen driver can open it. Output: ``<campaign>/fixtures/charts/<name>/``
plus ``charts.json`` (name, instrument, patches, pages, strips).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime

from tests.neighbour_campaign.common import (CHARTS, REPO, argyll, run_tool,
                                             strip_of)

sys.path.insert(0, str(REPO / "scripts"))

#: name -> (instrument, patches, hex). i1Pro strip charts from 80 to 4200;
#: CR30 square spot grids and honeycombs (read patch by patch).
CHARTS_PLAN = {
    "i1-0080": ("i1", 80, False),
    "i1-0200": ("i1", 200, False),
    "i1-0500": ("i1", 500, False),
    "i1-1000": ("i1", 1000, False),
    "i1-2000": ("i1", 2000, False),
    "i1-4200": ("i1", 4200, False),
    "cr30-spot-0080": ("CR30", 80, False),
    "cr30-spot-0500": ("CR30", 500, False),
    "cr30-hex-0200": ("CR30", 200, True),
    "cr30-hex-1000": ("CR30", 1000, True),
}


def guided_kwargs(instrument: str, hexagons: bool) -> dict:
    """Guided's engine keywords (ChartCreator._engine_build_kwargs)."""
    kw = dict(instrument=instrument, paper="A4", dpi=300, randomize=True,
              spacer_on=True, spacer_mode="colored", side_stamp=True)
    if instrument in ("i1", "p3", "CM"):
        kw["edge_spacers"] = True
    if instrument in ("i1", "p3"):
        kw["nolpcbord"] = False
        kw["clip_content_mode"] = "notes"
    if instrument == "CR30":
        kw.update(layout_mode="patch_first", hflag=bool(hexagons),
                  spacer_on=False, spacer_mode="none",
                  hex_flat_top=bool(hexagons))
    return kw


def project_name(name: str) -> str:
    return "NC-" + name


def build_one(name: str, force: bool = False) -> dict:
    from workflow.layout_engine.chart import build_chart
    from workflow.layout_engine.presets import LayoutRecipe

    instrument, patches, hexagons = CHARTS_PLAN[name]
    pname = project_name(name)
    proj = CHARTS / name / pname
    run = proj / "runs" / "run1"
    info_path = CHARTS / name / "chart.json"
    if info_path.exists() and not force:
        return json.loads(info_path.read_text())
    if (CHARTS / name).exists():
        shutil.rmtree(CHARTS / name)
    run.mkdir(parents=True)
    t0 = time.monotonic()
    run_tool([argyll("targen"), "-v0", "-d2", f"-f{patches}", "-e4", "-B4",
              "-G", pname], cwd=run, timeout=1800)
    t_targen = time.monotonic() - t0
    kw = guided_kwargs(instrument, hexagons)
    base = run / pname
    result = build_chart(base.with_suffix(".ti1"), base, **kw)
    sidecar = run / f"{pname}.channels.json"
    strips = run / f"{pname}.strips.json"
    doc = {"channels": ["r", "g", "b"]}
    layout = json.loads(strips.read_text()) if strips.exists() else {}
    layout.update(engine="chromiq", engine_version=1,
                  seed=getattr(result, "seed", 0),
                  color_rep=getattr(result, "color_rep", "RGB"),
                  recipe=LayoutRecipe.from_build_kwargs(kw).to_dict(),
                  margins_chosen_by_user=False)
    doc["layout"] = layout
    sidecar.write_text(json.dumps(doc))
    strips.unlink(missing_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    (proj / "project.json").write_text(json.dumps({
        "schema_version": 3, "created_at": now, "target_name": pname,
        "current_run": "run1", "runs": ["run1"]}, indent=2))
    (run / "meta.json").write_text(json.dumps({
        "run_id": "run1", "created_at": now, "parent_run": None,
        "instrument": instrument, "paper": "A4", "status": "in_progress",
        "run_type": "profiling"}, indent=2))
    pages = sorted({p["page"] for p in layout.get("patches", [])})
    info = {"name": name, "project": pname, "instrument": instrument,
            "hex": hexagons, "patches_asked": patches,
            "slots": len(layout.get("patches", [])), "pages": len(pages),
            "strips": len({strip_of(p["loc"]) for p in layout.get("patches", [])}),
            "targen_s": round(t_targen, 1),
            "run_dir": str(run.relative_to(CHARTS)), "stem": pname}
    info_path.write_text(json.dumps(info, indent=1))
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    CHARTS.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in CHARTS_PLAN:
        if a.only and name not in a.only:
            continue
        info = build_one(name, a.force)
        out[name] = info
        print(json.dumps(info))
    idx = CHARTS / "charts.json"
    old = json.loads(idx.read_text()) if idx.exists() else {}
    old.update(out)
    idx.write_text(json.dumps(old, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
