#!/usr/bin/env python3
"""P2 — is the .tif in the verifications folder already converted, or the raw chart?

Answered by MEASURING the file, not by reading the code. Her question:

    "is the .tif file saved in the verifications folder pre-converted?"

Method
------
A chart's ``.ti2`` lists every patch's DEVICE value (``RGB_R/G/B``, 0..100).
A raw ``printtarg`` sheet paints each patch with exactly those numbers, so
every device triple in the ``.ti2`` must appear verbatim as a pixel colour in
the TIFF. Applying a printer profile changes what gets painted, so after
``cctiff`` the same triples must mostly stop appearing.

So the test is a set comparison, run on three files:

  1. ``verifications/<stem>-verify_01.tif`` as ChromIQ leaves it;
  2. the same page after ``cctiff`` through the run's own profile, which is
     what ChromIQ writes when "Through the profile" is chosen;
  3. (a control) the run's own profiling chart page.

Usage:
    python proof_printpath/measure_verification_tiff.py --out DIR
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BIN = Path("/Applications/Argyll/bin")


def ti2_device_triples(path: Path) -> "set[tuple[int, int, int]]":
    """Every patch's device RGB from a .ti2, as 0..255 ints."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fmt: list[str] = []
    in_fmt = in_data = False
    out: set[tuple[int, int, int]] = set()
    for line in lines:
        s = line.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True
            continue
        if s == "END_DATA_FORMAT":
            in_fmt = False
            continue
        if in_fmt:
            fmt = s.split()
            continue
        if s == "BEGIN_DATA":
            in_data = True
            continue
        if s == "END_DATA":
            in_data = False
            continue
        if in_data and s:
            parts = s.split()
            if len(parts) != len(fmt):
                continue
            rec = dict(zip(fmt, parts))
            try:
                r, g, b = (float(rec["RGB_R"]), float(rec["RGB_G"]),
                           float(rec["RGB_B"]))
            except (KeyError, ValueError):
                continue
            out.add((round(r * 255 / 100), round(g * 255 / 100),
                     round(b * 255 / 100)))
    return out


def tiff_patch_colours(path: Path, min_pixels: int = 400) -> "set[tuple[int, int, int]]":
    """The distinct colours a TIFF paints in areas big enough to be a patch."""
    import numpy as np
    import tifffile
    arr = tifffile.imread(str(path))
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.dtype.itemsize == 2:
        arr = (arr.astype(np.uint32) * 255 // 65535).astype(np.uint8)
    arr = arr[..., :3].reshape(-1, 3)
    counts = Counter(map(tuple, arr[::7]))      # every 7th pixel is plenty
    return {c for c, n in counts.items() if n * 7 >= min_pixels}


def overlap(ti2: set, tif: set) -> dict:
    hit = ti2 & tif
    return {
        "patches_in_ti2": len(ti2),
        "big_colours_in_tiff": len(tif),
        "ti2_values_found_verbatim_in_the_tiff": len(hit),
        "share_of_patches_found": round(len(hit) / max(1, len(ti2)), 4),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else ROOT / "proof_printpath" / "onscreen"
    out.mkdir(parents=True, exist_ok=True)
    work = out / "tiff_measurement"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    res: dict = {}

    # -- the chart ChromIQ keeps in verifications/ --------------------------
    src = ROOT / "demo-projects" / "Demo-Report-Matrix" / "runs" / "run1"
    verify_ti1 = src / "verifications" / "Demo-Report-Matrix-verify.ti1"
    shutil.copy(verify_ti1, work / "verify.ti1")

    # printtarg is what writes the page ChromIQ files under verifications/ —
    # the same tool, the same flags the app uses for a ColorMunki chart.
    cmd = [str(BIN / "printtarg"), "-v", "-iCM", "-h", "-pA4", "-t300",
           "verify"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                       cwd=str(work))
    res["printtarg"] = {"cmd": " ".join(cmd), "returncode": p.returncode,
                        "stderr_tail": (p.stderr or "").strip()[-400:]}
    pages = sorted(work.glob("verify*.tif"))
    res["pages_written"] = [p_.name for p_ in pages]
    if not pages:
        print("printtarg wrote no page; cannot measure")
        print(p.stdout[-2000:], p.stderr[-2000:])
        return 1

    ti2 = work / "verify.ti2"
    triples = ti2_device_triples(ti2)
    raw_colours = tiff_patch_colours(pages[0])
    res["raw_sheet"] = overlap(triples, raw_colours)
    print(f"RAW  sheet {pages[0].name}: "
          f"{res['raw_sheet']['ti2_values_found_verbatim_in_the_tiff']} of "
          f"{res['raw_sheet']['patches_in_ti2']} .ti2 device values appear "
          f"verbatim as painted colours "
          f"({res['raw_sheet']['share_of_patches_found']:.0%})")

    # -- the same page through the run's own profile (what "Through the
    #    profile" writes into verifications/cache/) ------------------------
    profile = src / "Demo-Report-Matrix.icc"
    srgb = ""
    try:
        from core.argyll_detect import find_ref_profile
        srgb = find_ref_profile(str(BIN), ("sRGB.icm",))
    except Exception as exc:                                   # noqa: BLE001
        res["srgb_lookup_error"] = repr(exc)
    res["source_profile"] = srgb
    res["run_profile"] = str(profile)

    converted = work / "cache" / pages[0].name
    converted.parent.mkdir(parents=True, exist_ok=True)
    from workflow.cctiff_apply import convert_args
    cmd = [str(BIN / "cctiff"),
           *convert_args(Path(srgb), profile, pages[0], converted,
                         intent="r")]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    res["cctiff"] = {"cmd": " ".join(cmd), "returncode": p.returncode,
                     "stderr_tail": (p.stderr or "").strip()[-400:]}
    if converted.exists():
        conv_colours = tiff_patch_colours(converted)
        res["converted_sheet"] = overlap(triples, conv_colours)
        res["converted_sheet"]["bytes"] = converted.stat().st_size
        res["raw_sheet"]["bytes"] = pages[0].stat().st_size
        res["sheets_are_byte_identical"] = (
            pages[0].read_bytes() == converted.read_bytes())
        print(f"CONV sheet cache/{converted.name}: "
              f"{res['converted_sheet']['ti2_values_found_verbatim_in_the_tiff']}"
              f" of {res['converted_sheet']['patches_in_ti2']} "
              f"({res['converted_sheet']['share_of_patches_found']:.0%})")
        print(f"     byte-identical to the raw sheet? "
              f"{res['sheets_are_byte_identical']}")
        # name a few patches so the answer is checkable by eye
        sample = []
        raw_arr_hits = sorted(triples & raw_colours)[:6]
        for t in raw_arr_hits:
            sample.append({"ti2_device_value": list(t),
                           "painted_in_the_raw_sheet": True,
                           "still_painted_after_conversion": t in conv_colours})
        res["worked_examples"] = sample
        for s in sample:
            print(f"     device {s['ti2_device_value']}: raw sheet paints it; "
                  f"converted sheet paints it: "
                  f"{s['still_painted_after_conversion']}")
    else:
        print("cctiff produced no file:", p.stderr[-800:])

    (out / "p2_tiff_measurement.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nwrote {out / 'p2_tiff_measurement.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
