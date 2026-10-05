"""Agent 10b: what each on-screen build shows (log naming its option, the
profile's tags vs the same project's default build). Light: tag reads and
Argyll xicclu lookups only.

    python analyse_onscreen.py run > run/analysis.md
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "tree")]
from benchmarks.research.options import tag_facts, lut_identity  # noqa: E402

RUN = HERE / sys.argv[1]
R = json.loads((RUN / "result.json").read_text())

# what a log line naming the option would contain (case-insensitive)
NAMES = {
    "meta": r"manufacturer|copyright|media|attribute|default intent|embed",
    "ax": r"\bxyz\b|algorithm", "qm": r"quality|grid 1[57]|grid 17",
    "bh": r"b2a.*(quality|grid 45|high)", "bn": r"b2a.*(none|skip)|-bn|\bnone\b",
    "r2": r"smoothing|noise level|-r\b", "r025": r"smoothing|-r\b",
    "V2": r"dark|-V\b|emphasis", "iD65": r"illuminant|D65", "iD65M2": r"illuminant|D65M2",
    "iF8": r"illuminant|F8", "o1964": r"observer|1964",
    "kx": r"black generation|-k|maximum black|black ink rule|\bGCR\b",
    "kz": r"black generation|-k|no black", "kr": r"black generation|-k|ramp",
    "kp": r"black generation|-k|curve", "Kx": r"proportional|-K|locus",
    "gnone": r"gamut source|no gamut|colorimetric only|perceptual",
    "gs": r"gamut source|perceptual only|-s\b|saturation table",
    "ni": r"input (shaper|curve)|-ni", "no": r"output (shaper|curve)|-no",
    "np": r"grid position|-np", "v4": r"version 4|v4", "noise": r"noise",
    "physics": r"physic|spectral model", "bijective": r"bijective|render",
    "tpa": r"intent|appearance|-t\b|pa\b", "Tms": r"saturation intent|-T\b|ms\b",
    "cd": r"viewing", "nP-cmyksrc": r"colorimetric source|-nP|cmyk.icm",
    "nI": r"inverse|-nI", "f": r"fwa|whitener|brightener", "default": r".",
}


def key(label):
    return label.split("-", 1)[1]


def main():
    rows = R["builds"]
    base = {}
    for r in rows:
        if key(r["label"]) == "default" and r.get("icc"):
            base[(r["project"], r["engine_on"])] = r["icc"]
    print(f"# On-screen builds ({R['mode']}), {len(rows)} builds\n")
    print("| build | engine | params ok | profile | s | log names the option? | "
          "LUTs vs project default | header / tags |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        lab = r["label"]
        k = key(lab)
        logp = RUN / "logs" / f"{lab}.log"
        text = logp.read_text() if logp.exists() else ""
        pat = NAMES.get(k)
        named = "-"
        if pat and k != "default":
            hits = [ln for ln in text.splitlines() if re.search(pat, ln, re.I)
                    and "Candidate pipeline" not in ln and "moved to" not in ln]
            named = ("yes: " + hits[0][:90].replace("|", "/")) if hits else "NO"
        facts = ""
        lut = "-"
        if r.get("icc"):
            f = tag_facts(r["icc"])
            h = f["header"]
            a = f["luts"].get("A2B1") or f["luts"].get("A2B0") or {}
            b = f["luts"].get("B2A1") or f["luts"].get("B2A0") or {}
            facts = (f"v{h['version']} {h['pcs']} attr {h['attributes_hex']} intent "
                     f"{h['intent']} grids {a.get('grid')}/{b.get('grid')} "
                     f"desc {f['text'].get('desc', '')!r} cprt {f['text'].get('cprt', '')!r} "
                     f"targ {'targ' in f['tags']} aliases {f['aliases']}")
            bp = base.get((r["project"], r["engine_on"]))
            if bp and bp != r["icc"]:
                d = [t for t, same in lut_identity(bp, r["icc"]).items() if not same]
                lut = "identical" if not d else ",".join(d)
        print(f"| {lab} | {'on' if r['engine_on'] else 'off'} | "
              f"{'ok' if not r['params_mismatch'] else r['params_mismatch']} | "
              f"{'built' if r.get('icc') else 'NOT built'} | {r.get('seconds')} | {named} | "
              f"{lut} | {facts} |")
    print("\n## Engine off/on round trip\n")
    print("```\n" + json.dumps({k: v for k, v in R.get("toggle", {}).items() if k != "set"},
                               indent=1, default=str) + "\n```")
    print(f"\nGroups visible: {json.dumps(R.get('groups'))}")
    print(f"\nPop-ups: {len(R.get('popups', []))}, unexpected: {R.get('unexpected_popups')}")


main()
