"""Agent 24, C-L1: lut16 A2B L output table 0..FF00 with the CLUT L* rescaled x65535/65280.

    python l1_probe.py <profile.icc> <out.json> [--write <variant.icc>]

Builds the L1 variant of a profile post hoc (every A2Bx lut16 with a Lab PCS; output tables
re-sampled so the spec meaning is unchanged: out'(v) = out(v * 65280 / 65535)), then reads both
files' A2B1 with Argyll icclu, littleCMS and ColorSync (ColorSyncTransformConvert into Generic XYZ)
on: paper white, the neutral axis (device values from Argyll's B2A1 of L* 0..100, a*=b*=0) and 400
random device values (inks scaled to the TAC). Reference = Argyll on the profile as built. Also
counts CLUT nodes with L* > 100 (the values L1 must clip)."""
import json
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import cslib as C                         # noqa: E402
from icchelp import tags_of, write  # noqa: E402
from benchmarks.research import colour     # noqa: E402

K = 65535 / 65280


def parse_mft2(b):
    nin, nout, g = b[8], b[9], b[10]
    ni, no = struct.unpack(">HH", b[48:52])
    o = 52
    it = np.frombuffer(b, ">u2", nin * ni, o).reshape(nin, ni).astype(float); o += 2 * nin * ni
    cl = np.frombuffer(b, ">u2", g ** nin * nout, o).reshape(-1, nout).astype(float); o += 2 * g ** nin * nout
    ot = np.frombuffer(b, ">u2", nout * no, o).reshape(nout, no).astype(float)
    return nin, nout, g, it, cl, ot


def mft2(src, it, cl, ot):
    u = lambda a: struct.pack(">%dH" % a.size, *np.round(np.clip(a, 0, 65535)).astype(int).reshape(-1))
    return src[:48] + struct.pack(">HH", it.shape[1], ot.shape[1]) + u(it) + u(cl) + u(ot)


def l1_tag(b):
    nin, nout, g, it, cl, ot = parse_mft2(b)
    over = int((cl[:, 0] > 65280).sum())
    lmax = float(cl[:, 0].max() / 65280 * 100)
    cl = cl.copy()
    cl[:, 0] = np.clip(np.round(cl[:, 0] * K), 0, 65535)
    x = np.linspace(0, 65535, ot.shape[1])
    ot = ot.copy()
    ot[0] = np.interp(x / K, x, ot[0])
    return mft2(b, it, cl, ot), over, lmax


def _lab_l1():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "lab_l1", Path(__file__).resolve().parents[1] / "tree/workflow/profile_engine/lab_l1.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


VARIANT = "scale"


def make_l1(src: Path, dst: Path):
    d = src.read_bytes()
    assert d[20:24] == b"Lab ", "PCS must be Lab"
    out, info = [], {}
    for s, b in tags_of(d):
        if s.startswith("A2B") and b[:4] == b"mft2":
            _, over, lmax = l1_tag(b)
            b = (_lab_l1().encode_a2b_l1b if VARIANT == "b" else _lab_l1().encode_a2b_l1)(b)
            info[s] = {"clut_L_over_100": over, "clut_L_max": lmax}
        out.append((s, b))
    write(dst, d, out)
    return info


def iccref_a2b(prof, dev):
    """ICC reference implementation (iccDEV IccProfLib 2.3.2.3, Homebrew) A2B1, tetrahedral."""
    import subprocess, tempfile
    sig = Path(prof).read_bytes()[16:20].decode("latin-1")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=Path(__file__).parent / "out") as f:
        f.write(f"'{sig}' ; Data Format\nicEncodeUnitFloat ; Encoding\n\n")
        f.write("\n".join(" ".join(f"{v:.6f}" for v in r) for r in dev) + "\n")
    r = subprocess.run(["iccApplyNamedCmm", f.name, "0:6", "1", str(prof), "1"],
                       capture_output=True, text=True, timeout=600)
    Path(f.name).unlink()
    rows = [ln.split(";")[0].split() for ln in r.stdout.splitlines()
            if ";" in ln and ln.split(";")[0].strip()
            and ln.split(";")[0].split()[0].lstrip("-").replace(".", "", 1).isdigit()]
    out = np.array([[float(x) for x in rw[:3]] for rw in rows])
    if out.shape != (len(dev), 3):
        raise RuntimeError(f"iccref returned {out.shape}: {r.stdout[-300:]}{r.stderr[-300:]}")
    return out


def main():
    global VARIANT
    if "--variant" in sys.argv:
        i = sys.argv.index("--variant")
        VARIANT = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    src, outj = Path(sys.argv[1]), Path(sys.argv[2])
    var = Path(sys.argv[sys.argv.index("--write") + 1]) if "--write" in sys.argv \
        else outj.with_suffix(".l1.icc")
    info = make_l1(src, var)
    d = src.read_bytes()
    n = {b"RGB ": 3, b"CMYK": 4, b"CMY ": 3}.get(d[16:20])
    if n is None:
        n = int(d[16:17].decode(), 16) if d[17:20] == b"CLR" else None
    additive = d[16:20] == b"RGB "
    rng = np.random.default_rng(31)
    if additive:
        white = np.ones((1, n))
        rnd = rng.uniform(0, 1, (400, n))
    else:
        white = np.zeros((1, n))
        rnd = rng.uniform(0, 1, (400, n))
        tac = 3.0
        s = rnd.sum(1, keepdims=True)
        rnd = np.where(s > tac, rnd * tac / s, rnd)
    Ls = np.arange(100.0, -0.01, -2.5)
    neutral_dev = np.clip(C.b2a_ref(src, np.column_stack([Ls, 0 * Ls, 0 * Ls]), "argyll"), 0, 1)
    dev = np.vstack([white, neutral_dev, rnd])
    ref = C.a2b_ref(src, dev, "argyll")
    res = {"profile": str(src), "n": n, "tags": info}

    def stats(e):
        return {"med": float(np.median(e)), "p95": float(np.percentile(e, 95)), "max": float(e.max())}
    labs = {}
    for name, p in (("L0", src), ("L1", var)):
        for rd in ("argyll", "lcms", "colorsync", "iccref"):
            try:
                if rd == "colorsync":
                    lab = C.xyz2lab(C.cstrans(str(p), "XYZ", dev, 3))
                elif rd == "iccref":
                    lab = iccref_a2b(p, dev)
                else:
                    lab = C.a2b_ref(p, dev, rd)
            except Exception as ex:   # noqa: BLE001
                res[f"{name}-{rd}"] = {"error": f"{type(ex).__name__}: {ex}"}
                continue
            labs[(name, rd)] = lab
            e = colour.de2000(lab, ref)
            nn = 1 + len(neutral_dev)
            res[f"{name}-{rd}"] = {"white_de": float(e[0]), "white_lab": lab[0].round(4).tolist(),
                                   "neutral": stats(e[1:nn]), "random": stats(e[nn:]),
                                   "all": stats(e), "mean_dL": float((lab - ref)[:, 0].mean())}
    for rd in ("argyll", "lcms", "colorsync", "iccref"):
        if ("L0", rd) in labs and ("L1", rd) in labs:
            e = colour.de2000(labs[("L1", rd)], labs[("L0", rd)])
            res[f"L1vsL0-{rd}"] = {"med": float(np.median(e)), "max": float(e.max())}
    # B2A untouched: every non-A2B tag byte-identical
    t0, t1 = dict(tags_of(d)), dict(tags_of(var.read_bytes()))
    res["non_a2b_identical"] = all(t1[s][:len(t0[s])] == t0[s] and not t1[s][len(t0[s]):].strip(b"\0")
                                   for s in t0 if not s.startswith("A2B"))
    outj.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: (v if not isinstance(v, dict) or "all" not in v else
                          {"white": round(v["white_de"], 4), "neu_med": round(v["neutral"]["med"], 4),
                           "rnd_med": round(v["random"]["med"], 4), "max": round(v["all"]["max"], 4)})
                      for k, v in res.items() if k not in ("profile",)}))


if __name__ == "__main__":
    main()
