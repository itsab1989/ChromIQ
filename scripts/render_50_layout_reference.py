#!/usr/bin/env python3
"""Build one FIXED engine chart and hash the result, so the same build can be
run from two commits and compared byte for byte.

Imports only workflow.layout_engine, so it runs unchanged inside a git worktree
of an older commit.

    python scripts/render_50_layout_reference.py <out_dir> <chart.ti1> <case>

cases:  guided_i1   guided_cr30   area_cr30_hex   area_i1   patchfirst_tinyleft
"""
from __future__ import annotations
import hashlib, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SEED = 1234567

# Guided: exactly what workflow/chart_creator._engine_build_kwargs builds for a
# Guided chart -- note it never sets layout_mode, so the engine default
# (patch_first) applies. Guided has no margin boxes: one `border`.
CASES = {
    "guided_i1": dict(instrument="i1", paper="A4", dpi=300, randomize=True,
                      spacer_on=True, spacer_mode="colored", bit16=False,
                      pscale=1.0, sscale=1.0, border=10.0, nolimit=False,
                      edge_spacers=True),
    "guided_cr30": dict(instrument="CR30", paper="A4", dpi=300, randomize=True,
                        spacer_on=False, spacer_mode="none", bit16=False,
                        pscale=1.0, sscale=1.0, border=6.0, nolimit=False),
    "guided_cm": dict(instrument="CM", paper="A4", dpi=300, randomize=True,
                      spacer_on=True, spacer_mode="colored", bit16=False,
                      pscale=1.0, sscale=1.0, border=6.0, nolimit=False,
                      edge_spacers=True),
    # Basti's own case: area-first, CR30, hex, margins T6 R2 B1 L1
    "area_cr30_hex": dict(instrument="CR30", paper="A4", dpi=300,
                          randomize=True, hflag=True, spacer_on=False,
                          spacer_mode="none", layout_mode="area_first",
                          area_method="by_grid", area_cols=26, area_rows=44,
                          area_ratio=1.0, margins=(1.0, 6.0, 2.0, 1.0),
                          border=1.0, nolimit=True),
    "area_i1": dict(instrument="i1", paper="A4", dpi=300, randomize=True,
                    spacer_on=True, spacer_mode="colored", edge_spacers=True,
                    layout_mode="area_first", area_method="by_width",
                    margins=(1.0, 6.0, 2.0, 1.0), border=1.0),
    # patch-first with a left margin far too small for the row band: the case
    # where the new max(0, ...) clamp in raster.py could bite a NON-area chart
    "patchfirst_tinyleft": dict(instrument="i1", paper="A4", dpi=300,
                                randomize=True, spacer_on=True,
                                spacer_mode="colored", edge_spacers=True,
                                margins=(0.0, 6.0, 2.0, 1.0), border=0.0),
}


def main() -> int:
    out_dir = Path(sys.argv[1]); out_dir.mkdir(parents=True, exist_ok=True)
    ti1 = Path(sys.argv[2])
    case = sys.argv[3]
    kw = dict(CASES[case])
    from workflow.layout_engine import chart
    base = out_dir / case
    try:
        res = chart.build_chart(ti1, base, seed=SEED, **kw)
    except TypeError as exc:                 # an older tree lacks a kwarg
        print(f"{case}: BUILD KWARG MISMATCH: {exc}")
        return 2
    except Exception as exc:                 # noqa: BLE001
        print(f"{case}: BUILD FAILED: {type(exc).__name__}: {exc}")
        return 3
    out = {"case": case, "seed": res.seed,
           "patches_per_page": res.layout.patches_per_page,
           "steps_in_pass": res.layout.steps_in_pass,
           "pages": len(res.tiff_paths or [])}
    ch = base.with_suffix(".channels.json")
    if ch.is_file():
        lay = json.loads(ch.read_text())["layout"]
        pats = [p for p in lay["patches"] if p.get("page", 0) == 0]
        dpi = float(lay.get("dpi") or 300)
        pats.sort(key=lambda p: (p["x"], p["y"]))
        out["n_patches"] = len(lay["patches"])
        out["first_patch_x_mm"] = round(pats[0]["x"] * 25.4 / dpi, 3)
        out["first_patch_y_mm"] = round(pats[0]["y"] * 25.4 / dpi, 3)
        out["patch_w_mm"] = round(pats[0]["w"] * 25.4 / dpi, 3)
        out["patch_h_mm"] = round(pats[0]["h"] * 25.4 / dpi, 3)
        out["last_patch_right_mm"] = round(
            max(p["x"] + p["w"] for p in pats) * 25.4 / dpi, 3)
        out["layout_sha"] = hashlib.sha256(
            json.dumps(lay, sort_keys=True).encode()).hexdigest()[:16]
    for i, t in enumerate(res.tiff_paths or []):
        out[f"tiff{i}_sha"] = hashlib.sha256(Path(t).read_bytes()).hexdigest()[:16]
        out[f"tiff{i}_bytes"] = Path(t).stat().st_size
    print(json.dumps(out, sort_keys=True))
    (out_dir / f"{case}.facts.json").write_text(json.dumps(out, sort_keys=True,
                                                           indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
