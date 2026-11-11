"""Agent 25: perceptual / saturation rows of Agent 23's hunt (F-16, F-18):
H1 grey ramp (p, s, p app-8), H2 sRGB/Adobe ramps (p, s), H5 memory colours,
H4 tinted ramps (p, r).
    python -m benchmarks.research.oog25.evalp OUT NAME PROFILE RESULT.json"""
import json
import sys
from pathlib import Path


def summary(res):
    h1, h2 = res["H1"], res["H2"]
    ps = [v for k, v in h2.items() if k[-2:] in ("-p", "-s") and isinstance(v, dict)]
    out = {"greyP_swing": h1["p"]["l_swing"], "greyP_C": h1["p"]["chroma_max"],
           "greyS_swing": h1["s"]["l_swing"], "greyS_C": h1["s"]["chroma_max"],
           "greyPapp_swing": h1.get("p-app8", {}).get("l_swing"),
           "ramps_ps_rev": sum(v.get("l_rev", 0) for v in ps),
           "ramps_ps_swing": max(v.get("l_swing", 0) for v in ps),
           "ramps_ps_d2": max(v.get("d2_excess_max", 0) for v in ps)}
    if "H4" in res:
        out["tintP_rev"] = sum(v.get("l_rev", 0) for k, v in res["H4"].items()
                               if isinstance(v, dict) and k.endswith("-p"))
    return out


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from benchmarks.research.blindspots import hunt, hunt_run
    out, name, icc, dst = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve(), Path(sys.argv[4])
    ctx, truth = hunt_run.context(out, name, icc)
    res = {"truth": truth, "profile": str(icc), "H1": hunt.h1_grey(ctx),
           "H2": hunt.h2_colour_ramps(ctx), "H4": hunt.h4_tinted(ctx), "H5": hunt.h5_memory(ctx)}
    res["summary"] = summary(res)
    dst.write_text(json.dumps(hunt.jsonable(res), indent=1), encoding="utf-8")
    print(name, icc.name, json.dumps({k: (round(v, 2) if isinstance(v, float) else v)
                                      for k, v in res["summary"].items()}), flush=True)


if __name__ == "__main__":
    main()
