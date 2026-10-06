"""Agent 24, F-05: score the perceptual and saturation intents of every arm.

    python score_f05.py <run> [--readers argyll,lcms,colorsync] [--intents p,s] [--ncq]

Per profile x reader x intent: Agent 9's gmq (M1-M11, end to end through the truth printer;
real sets through the published reference profile's A2B1 as a labelled proxy) and, with --ncq,
Agent 14's ncq (NC1-NC5) on the same intent. ColorSync is added as a gmq reader here
(Quartz CGColor matching with the perceptual / saturation intent; Lab range [-127.5, 127.5]).
Also writes the tag identity of every arm against the run's base arm (tags.json).
Output: runs/<run>/gmq/<stem>-<reader>-<intent>.json + .npz, ncq/<...>.json."""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np

H = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(H / "score"))
from benchmarks.research import cmm, gmq, ncq            # noqa: E402
from benchmarks.research.printers import build_printers  # noqa: E402

_ORIG = gmq.b2a_intent


def _cs_b2a(path, lab, intent):
    import Quartz as Q
    data = Path(path).read_bytes()
    prof = Q.CGColorSpaceCreateWithICCData(Q.CFDataCreate(None, data, len(data)))
    if prof is None:
        raise RuntimeError("ColorSync refused the profile")
    labsp = Q.CGColorSpaceCreateLab([0.9642, 1.0, 0.8249], [0, 0, 0], list(cmm.QUARTZ_LAB_RANGE))
    n = Q.CGColorSpaceGetNumberOfComponents(prof)
    it = {"p": Q.kCGRenderingIntentPerceptual, "s": Q.kCGRenderingIntentSaturation,
          "r": Q.kCGRenderingIntentRelativeColorimetric}[intent]
    out = np.empty((len(lab), n))
    for i, r in enumerate(lab):
        c = Q.CGColorCreate(labsp, [float(v) for v in r] + [1.0])
        m = Q.CGColorCreateCopyByMatchingToColorSpace(prof, it, c, None)
        comps = Q.CGColorGetComponents(m)
        out[i] = [comps[k] for k in range(n)]
    return np.clip(out, 0.0, 1.0)


def b2a_intent(path, lab, reader, intent, argyll_bin="/Applications/Argyll/bin"):
    if reader == "colorsync":
        return _cs_b2a(path, lab, intent)
    return _ORIG(path, lab, reader, intent, argyll_bin)


gmq.b2a_intent = b2a_intent

REAL = {"R-FOGRA55": ("Ref_FOGRA55", "CMYKOGV"), "R-APTEC7C": ("APTEC", "CMYKOGV")}


def tags(p: Path) -> dict:
    d = p.read_bytes()
    n = struct.unpack(">I", d[128:132])[0]
    out = {}
    for i in range(n):
        s = d[132 + 12 * i:136 + 12 * i].decode("latin-1")
        o, ln = struct.unpack(">II", d[136 + 12 * i:144 + 12 * i])
        out[s] = hashlib.sha256(d[o:o + ln]).hexdigest()[:16]
    return out


def printer_for(tag: str):
    if tag.startswith("R-"):
        from benchmarks.research import datasets as dsm
        from benchmarks.research.printers import split_letters
        name = "-".join(tag.split("-")[:2])
        ref = dsm.reference_icc(name)
        reader = "lcms" if Path(ref).read_bytes()[8] >= 4 else "argyll"
        pr = ncq.ProxyPrinter(f"icc:{ref}", split_letters("CMYKOGV"), 300.0)
        if reader == "lcms":                       # icclu refuses v4 mAB
            pr.lab_rel = lambda d, illuminant="D50", _r=ref: cmm.a2b(
                _r, np.clip(np.atleast_2d(np.asarray(d, float)), 0, 1), "lcms")
        return pr, name, f"icc:{ref}"
    pid = tag.split("-")[0]
    return build_printers()[pid], pid, None


def main():
    run = H / "f05" / "runs" / sys.argv[1]
    readers = (sys.argv[sys.argv.index("--readers") + 1] if "--readers" in sys.argv
               else "argyll,lcms,colorsync").split(",")
    intents = (sys.argv[sys.argv.index("--intents") + 1] if "--intents" in sys.argv
               else "p,s").split(",")
    want_ncq = "--ncq" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    tagf = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else None
    gdir, ndir = run / "gmq", run / "ncq"
    gdir.mkdir(exist_ok=True)
    ndir.mkdir(exist_ok=True)
    profs = sorted(p for p in (run / "profiles").glob("*.icc") if not p.stem.endswith("-v4"))
    # tag identity against the base arm
    tj = {}
    for p in profs:
        tag, arm = p.stem.rsplit("-", 1)
        base = run / "profiles" / f"{tag}-base.icc"
        if arm != "base" and base.exists():
            ta, tb = tags(base), tags(p)
            tj[p.stem] = sorted(s for s in set(ta) | set(tb) if ta.get(s) != tb.get(s))
            v4b, v4p = base.with_name(base.stem + "-v4.icc"), p.with_name(p.stem + "-v4.icc")
            if v4b.exists() and v4p.exists():
                ta, tb = tags(v4b), tags(v4p)
                tj[p.stem + "-v4"] = sorted(s for s in set(ta) | set(tb) if ta.get(s) != tb.get(s))
    (run / "tags.json").write_text(json.dumps(tj, indent=1), encoding="utf-8")
    gam_cache: dict = {}
    for p in profs:
        tag, arm = p.stem.rsplit("-", 1)
        if (only and arm not in only) or (tagf and tag != tagf):
            continue
        printer, pid, proxy = printer_for(tag)
        if pid not in gam_cache:
            gam_cache[pid] = gmq.TruthGamut(gmq.truth_cloud(printer))
        for rd in readers:
            if rd == "colorsync" and not cmm.colorsync_supported(str(p)):
                (gdir / f"{p.stem}-{rd}-unsupported.json").write_text("{}", encoding="utf-8")
                continue
            for it in intents:
                f = gdir / f"{p.stem}-{rd}-{it}.json"
                if not f.exists():
                    try:
                        res, pp = gmq.evaluate(p, printer, rd, it, gamut=gam_cache[pid])
                        res["truth"] = "proxy " + proxy if proxy else "printer"
                        np.savez_compressed(f.with_suffix(".npz"), **pp)
                    except Exception as ex:          # noqa: BLE001
                        res = {"error": f"{type(ex).__name__}: {ex}"}
                    f.write_text(json.dumps(res, indent=1), encoding="utf-8")
                    print(f"gmq {p.stem} {rd} {it}: C* {res.get('M1_neutral_C_mean')} "
                          f"rt {res.get('M11_rt_median')}", flush=True)
                fn = ndir / f"{p.stem}-{rd}-{it}.json"
                if want_ncq and not fn.exists():
                    try:
                        r = ncq.evaluate(p, pid, rd, it, "1,2,3,5",
                                         proxy=proxy, letters="CMYKOGV" if proxy else None,
                                         tac=300.0 if proxy else None) if proxy else \
                            ncq.evaluate(p, pid, rd, it, "1,2,3,5")
                        fn.write_text(json.dumps({"headline": ncq.headline(r)}, indent=1,
                                                 default=float), encoding="utf-8")
                    except Exception as ex:          # noqa: BLE001
                        fn.write_text(json.dumps({"error": f"{type(ex).__name__}: {ex}"}), encoding="utf-8")
                    print(f"ncq {p.stem} {rd} {it} done", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
