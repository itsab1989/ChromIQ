"""Round 4, issue #182 — Knut's clarified proposal, measured as a CHART question.

He is NOT deriving Lab from CMYK.  He asks: replace the dataset's CMYK columns
with RGB equivalents, leave the measured Lab untouched, and use the result
(a) in the 3D distribution plot, (b) as a patch set for charts to print.

(b) is the one that can be measured, so it is measured here: taken purely as a
set of device values with the Lab discarded, is the converted column a GOOD RGB
chart?  Compared against what ChromIQ would generate for the same patch count.

Read-only.
"""
import os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np

REPO = Path(os.environ.get("CHROMIQ_REPO", "~/develop/ChromIQ")).expanduser()
RES = Path(os.environ.get("CHROMIQ_RESEARCH", "~/develop/ChromIQ-research")).expanduser()
F51 = RES / "issue-182/02-challenge/fogra/Fogra Characterisation Data/x/FOGRA51.txt"
sys.path.insert(0, str(REPO))


def read_fogra(p):
    lines = p.read_text(errors="replace").splitlines()
    i0 = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    i1 = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    rows = [l.split() for l in lines[i0 + 1:i1] if l.strip()]
    cmyk = np.array([[float(r[j]) for j in (1, 2, 3, 4)] for r in rows])
    lab = np.array([[float(r[j]) for j in (5, 6, 7)] for r in rows])
    return cmyk, lab


def cmyk_to_rgb100(cmyk):
    """Knut's stated mapping, on the 0..100 scale ChromIQ uses:
    CMYK 0 0 0 0 -> RGB 100 100 100.  Textbook subtractive->additive."""
    c, m, y, k = (cmyk[:, i] / 100.0 for i in range(4))
    r = 100.0 * (1 - c) * (1 - k)
    g = 100.0 * (1 - m) * (1 - k)
    b = 100.0 * (1 - y) * (1 - k)
    return np.stack([r, g, b], axis=1)


def targen_rgb(n):
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "t"
        subprocess.run(["/Applications/Argyll/bin/targen", "-d2", "-G", f"-f{n}",
                        str(out)], check=True, capture_output=True, timeout=300)
        from workflow.ti3_analysis import parse_ti3
        return np.asarray(parse_ti3(out.with_suffix(".ti1")).rgb, float)


def describe(name, rgb):
    n = len(rgb)
    q = np.round(rgb, 4)
    uniq = len({tuple(r) for r in q})
    # nearest-neighbour distance (Euclidean, device units 0..100)
    d = np.sqrt(((rgb[:, None, :] - rgb[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1)
    # occupancy of an 8x8x8 grid over the cube
    idx = np.clip((rgb / 100.0 * 8).astype(int), 0, 7)
    cells = len({tuple(v) for v in idx})
    print(f"{name:<34} n={n:5d}  distinct={uniq:5d}  "
          f"duplicates={n - uniq:4d}  cells(8^3=512)={cells:3d}  "
          f"NN min={nn.min():5.2f} median={np.median(nn):5.2f}  "
          f"pairs closer than 2.0 = {(nn < 2.0).sum():4d}")
    return dict(n=n, uniq=uniq, cells=cells, nn_min=float(nn.min()),
                nn_med=float(np.median(nn)), close=int((nn < 2.0).sum()))


def main():
    cmyk, lab = read_fogra(F51)
    print(f"FOGRA51: {len(cmyk)} rows\n")
    rgb = cmyk_to_rgb100(cmyk)

    # How much of the collapse is the CONVERSION's doing, and how much did the
    # dataset already have?  IT8.7/4 repeats some control patches.
    from collections import Counter as _C
    nc = len(_C(tuple(np.round(r, 4)) for r in cmyk))
    nr = len(_C(tuple(np.round(r, 4)) for r in rgb))
    print(f"distinct CMYK values: {nc} of {len(cmyk)}  "
          f"(so {len(cmyk)-nc} rows are duplicates the dataset already had)")
    print(f"distinct RGB values : {nr} of {len(rgb)}  "
          f"(so {len(rgb)-nr} collisions, of which "
          f"{(len(rgb)-nr)-(len(cmyk)-nc)} are created by the conversion)\n")
    a = describe("FOGRA51 CMYK -> RGB (Knut's map)", rgb)
    b = describe("ChromIQ targen -d2 -G -f1617", targen_rgb(1617))

    print("\nWhat the duplicates are — the CMYK rows that collapse onto one RGB:")
    q = [tuple(np.round(r, 4)) for r in rgb]
    from collections import Counter
    for v, c in Counter(q).most_common(4):
        which = [i for i, x in enumerate(q) if x == v][:6]
        print(f"  RGB {v}  <- {c} different CMYK rows, e.g.")
        for i in which[:4]:
            print(f"      CMYK {cmyk[i].astype(int).tolist()}  measured Lab "
                  f"{lab[i][0]:6.2f} {lab[i][1]:7.2f} {lab[i][2]:7.2f}")
        # how far apart are those patches in REAL measured colour?
        sys.path.insert(0, str(REPO))
        from workflow.ti3_analysis import ciede2000
        ls = [tuple(lab[i]) for i in which]
        des = [ciede2000(ls[0], x) for x in ls[1:]]
        if des:
            print(f"      measured spread of those patches: "
                  f"{min(des):.2f} .. {max(des):.2f} dE00")
        # EVERY pair in the whole colliding group, not just the first six.
        allidx = [i for i, x in enumerate(q) if x == v]
        worst, pair = 0.0, None
        for ii in range(len(allidx)):
            for jj in range(ii + 1, len(allidx)):
                de = ciede2000(tuple(lab[allidx[ii]]), tuple(lab[allidx[jj]]))
                if de > worst:
                    worst, pair = de, (allidx[ii], allidx[jj])
        if pair:
            npairs = len(allidx) * (len(allidx) - 1) // 2
            print(f"      exhaustive over all {npairs} pairs of the {len(allidx)}: "
                  f"max {worst:.2f} dE00, between CMYK "
                  f"{cmyk[pair[0]].astype(int).tolist()} and "
                  f"{cmyk[pair[1]].astype(int).tolist()}")
        print()

    print("Neutral axis check — how many of the converted patches land on R=G=B:")
    onax = np.abs(rgb[:, 0] - rgb[:, 1]) + np.abs(rgb[:, 1] - rgb[:, 2])
    print(f"  within 1.0 device unit of the grey axis: {(onax <= 1.0).sum()} of {len(rgb)}")


if __name__ == "__main__":
    main()
