"""Extract CIE standard tables from ArgyllCMS 3.5.0 ``xicc/xspect.c`` (Agent 6).

Why: the benchmark's ground truth must not use the engine's own spectral
code or tables (agent 2, E4/E4b: the engine sums at the instrument's 10 nm
bands, and a referee that shares that function cannot see its error). These
are the CIE standard tables (CIE 15; illuminants at 5 nm, the 1931 2 degree
observer at 1 nm) as Argyll carries them. Run once; the JSON is committed.

    python -m benchmarks.research.extract_cie_tables /path/to/Argyll_V3.5.0_orig
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WANT = {"il_A": "A", "il_D50": "D50", "il_D65": "D65", "il_F5": "F5",
        "il_F8": "F8", "il_F10": "F10"}


def _block(src: str, name: str) -> str:
    m = re.search(r"static xspect " + re.escape(name) + r"(\[3\])?\s*=\s*\{", src)
    if not m:
        raise KeyError(name)
    depth, i = 1, m.end()
    while depth:
        c = src[i]
        depth += c == "{"
        depth -= c == "}"
        i += 1
    return src[m.end():i - 1]


def _nums(text: str) -> list[float]:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)]


def _spect(body: str) -> dict:
    head, _, vals = body.partition("{")
    h = _nums(head)
    n, lo, hi = int(h[0]), h[1], h[2]
    v = _nums(vals)[:n]
    if len(v) != n:
        raise ValueError(f"expected {n} values, got {len(v)}")
    return {"lo": lo, "hi": hi, "vals": v}


def main(argyll_root: str) -> None:
    src = (Path(argyll_root) / "xicc" / "xspect.c").read_text(encoding="utf-8", errors="replace")
    out = {"source": "ArgyllCMS 3.5.0 xicc/xspect.c (CIE 15 standard tables)",
           "illuminants": {}, "observers": {}}
    for cname, key in WANT.items():
        out["illuminants"][key] = _spect(_block(src, cname))
    ob = _block(src, "ob_CIE_1931_2")
    parts = re.findall(r"\{([^{}]*\{[^{}]*\})", ob)
    xyz = [_spect(p) for p in parts[:3]]
    out["observers"]["1931_2"] = {"lo": xyz[0]["lo"], "hi": xyz[0]["hi"],
                                  "x": xyz[0]["vals"], "y": xyz[1]["vals"],
                                  "z": xyz[2]["vals"]}
    dst = Path(__file__).parent / "data" / "cie_tables.json"
    dst.write_text(json.dumps(out), encoding="utf-8")
    for k, v in out["illuminants"].items():
        print(k, v["lo"], v["hi"], len(v["vals"]))
    o = out["observers"]["1931_2"]
    print("1931_2", o["lo"], o["hi"], len(o["x"]), sum(o["y"]))


if __name__ == "__main__":
    main(sys.argv[1])
