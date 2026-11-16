"""Make tests/data/margin_fixtures.json from a tester's ruler diagnostics files
(the margin tolerance Beta, 2026-11-16).

The diagnostics file of a strip holds the ruler code stream and a coarse
trace in three colour bands (each relative to its own maximum over the strip)
per reading, but never the spectra, so the candidate segments of a REFUSED
reading cannot be read from it. They are reconstructed here exactly as the
offline analysis of 2026-11-15 did: a re-implementation of ArgyllCMS's i1Pro 2
segmenter (i1pro_imp.c, i1pro_extract_patches_multimeas, the slope filter and
the 0.4 threshold) on the 3-band trace, each segment's trimmed average (2/3,
as ArgyllCMS trims) and its travel on the ruler. The colour of a segment is
the trace's three bands used as X, Y, Z relative to D50 white, so its "Lab" is
on the CIE Lab scale but is not a CIE colour (stated in every test using it).

Nothing personal goes into the fixture: no serial number (the files hold
none), no path, no name; the session is named by the file's time stamp.

    python3 scripts/make_margin_fixtures.py FILE.json [FILE.json ...]
    python3 scripts/make_margin_fixtures.py --charts DIR

The second form writes tests/data/margin_charts.json: the expected CIE Lab
(D50) of every full row of every .ti2 under DIR (the reader review's 28
charts), grouped by the letters of SAMPLE_LOC, for the constructed cases.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "tests" / "data" / "margin_fixtures.json"
CHARTS = OUT.with_name("margin_charts.json")
WP = np.array([96.42, 100.0, 82.49])


def xyz2lab(X):
    v = np.asarray(X, float) / WP
    f = np.where(v > 0.008856, np.cbrt(v), 7.787 * v + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def read_ti2_rows(p: Path):
    data, on, fmt = [], False, None
    for line in p.read_text(errors="replace").splitlines():
        if line.startswith("BEGIN_DATA_FORMAT"):
            on = "f"
            continue
        if on == "f":
            fmt = line.split()
            on = False
            continue
        if line.startswith("BEGIN_DATA"):
            on = True
            continue
        if line.startswith("END_DATA"):
            on = False
            continue
        if on:
            data.append(line.split())
    if not fmt or "XYZ_X" not in fmt or "SAMPLE_LOC" not in fmt:
        return None
    ix = [fmt.index(k) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    il = fmt.index("SAMPLE_LOC")
    rows = {}
    for r in data:
        m = re.match(r"([A-Za-z]+)(\d+)", r[il].strip('"'))
        if m:
            rows.setdefault(m.group(1), []).append(
                (int(m.group(2)), [float(r[i]) for i in ix]))
    L = [np.array([x for _, x in sorted(v)]) for v in rows.values()]
    if not L:
        return None
    n = max(len(x) for x in L)
    L = [x for x in L if len(x) == n]      # full rows only
    if len(L) < 3 or n < 6:
        return None
    return np.round(np.array([xyz2lab(x) for x in L]), 2).tolist()


def charts(d: Path) -> int:
    out = {}
    for p in sorted(d.rglob("*.ti2")):
        rows = read_ti2_rows(p)
        if rows is not None:
            out[str(p.relative_to(d))] = rows
    CHARTS.write_text(json.dumps({"about": "Expected CIE Lab (D50) per full row of "
                                  "the reader review's .ti2 charts "
                                  "(scripts/make_margin_fixtures.py --charts).",
                                  "charts": out}, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    print(CHARTS, len(out), "charts", CHARTS.stat().st_size, "bytes")
    return 0


def trace(rec) -> np.ndarray:
    return np.array(rec["trace"], float).reshape(-1, 3) / 1000.0


def positions(rec, n_readings):
    """Ruler position (signed steps) at each reading: reading = sample / clocks."""
    ch = rec.get("changes") or []
    gaps, codes = ch[0::2], ch[1::2]
    at = np.cumsum(gaps)
    clocks = rec.get("clocks") or 136
    order = {0: 0, 1: 1, 3: 2, 2: 3}
    prev = rec.get("first", 0)
    sgn = []
    for c in codes:
        dlt = (order[c] - order[prev]) % 4
        sgn.append(1 if dlt == 1 else (-1 if dlt == 3 else 0))
        prev = c
    cum = np.cumsum(np.array(sgn, int)) if sgn else np.zeros(0, int)
    rd = at / clocks
    idx = np.arange(n_readings)
    k = np.searchsorted(rd, idx, side="right")
    pos = np.where(k > 0, cum[np.maximum(k - 1, 0)] if len(cum) else 0, 0)
    return pos.astype(float), (cum[-1] if len(cum) else 0)


def segment(fraw, thresh=0.4):
    """ArgyllCMS's slope filter, normalisation and threshold (i1pro_imp.c)."""
    n, nfb = fraw.shape
    FW = 5
    slope = np.zeros(n)
    for i in range(FW - 1, n - FW):
        slopeth = 0.0
        for pp in range(2):
            acc = 0.0
            cnt = 0
            for j in range(nfb):
                sl = [fraw[i + k - FW + 1, j] - fraw[i + k - FW + 2, j]
                      for k in range(2 * FW - 1)]
                asl, dev = [], []
                for k in range(FW):
                    a = sum(sl[k:k + FW]) / FW
                    asl.append(a)
                    dev.append(sum((s - a) ** 2 for s in sl[k:k + FW]))
                bdev = min(dev)
                for k in range(FW):
                    dev[k] += abs(2.0 * k - (FW - 1.0)) / (FW - 1.0) * bdev
                kb = int(np.argmin(dev))
                basl = abs(asl[kb])
                if pp == 0:
                    acc += basl
                elif basl > slopeth:
                    acc += basl
                    cnt += 1
            if pp == 0:
                slopeth = acc / nfb
            else:
                slope[i] = acc / cnt if cnt else 0.0

    def norm(sl, mxf, mnf):
        mx, mn = 0.0, 1e38
        for i in range(4, n - 4):
            mx = max(mx, sl[i])
            mn = min(mn, sl[i - 2:i + 3].mean())
        mx *= mxf
        mn *= mnf
        return np.clip((sl - mn) / (mx - mn), 0, 1)

    slope = norm(slope, 0.5, 3.0)
    slope = norm(slope, 0.3, 3.0)
    pats = []
    i = 0
    while i < n - 1:
        if slope[i] > thresh:
            i += 1
            continue
        ss, no = i, 2
        i += 1
        while i < n - 1:
            if slope[i] > thresh:
                break
            no += 1
            i += 1
        pats.append([ss, no])
        i += 1
    return pats


def candidates(rec):
    t = trace(rec)
    n = len(t)
    p, net = positions(rec, n)
    out = []
    for ss, no in segment(t):
        nnn = (no * 2) // 3
        trim = (no - nnn + 1) // 2
        a, b = ss + trim, ss + trim + max(nnn, 1)
        v = t[a:b].mean(0)
        steps = abs(p[min(ss + no - 1, n - 1)] - p[ss])
        out.append([int(ss), int(no), float(steps)] + [round(float(x), 5) for x in v])
    return out, int(np.sign(net))


def cut_values(rec):
    t = trace(rec)
    cut = rec.get("cut") or []
    return [[round(float(x), 5) for x in t[a:a + b].mean(0)]
            for a, b in zip(cut[0::2], cut[1::2])]


def session(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    m = re.search(r"(\d{8}-\d{6})", path.name)
    key = m.group(1) if m else path.stem
    strips = []
    for s in d["strips"]:
        rec = s["record"]
        cands, sign = candidates(rec)
        strips.append({
            "strip": s["strip"],
            "verdict": s["verdict"],
            "refused_because": s.get("refused_because") or "",
            "reversed": bool(s.get("reversed")),
            "patches": (s.get("geometry") or {}).get("patches"),
            "ruler_sign": sign,
            "cut": rec.get("cut") or [],
            "cut_values": cut_values(rec),
            "candidates": cands,
        })
    return {"session": key, "chromiq": d.get("chromiq"), "instrument": d.get("instrument"),
            "strips": strips}


def main(argv):
    if len(argv) == 3 and argv[1] == "--charts":
        return charts(Path(argv[2]).expanduser())
    files = [Path(a).expanduser() for a in argv[1:]]
    if not files:
        print(__doc__)
        return 2
    doc = {
        "about": "Candidate segments reconstructed from three i1Pro 2 ruler "
                 "diagnostics files of one tester (public forum attachments, "
                 "2026-11-15) by scripts/make_margin_fixtures.py. Colours are "
                 "the 3-band trace used as XYZ (relative to D50 white), not CIE "
                 "colours. Candidate: [first reading, readings, ruler steps, "
                 "band0, band1, band2].",
        "sessions": [session(f) for f in files],
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(OUT, OUT.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
