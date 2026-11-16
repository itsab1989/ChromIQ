"""The margin tolerance's decision (native/chartread_helper/chromiq_margin.c),
compiled on its own and called through ctypes, so the tests run the SAME C
code the helper runs (no Python copy of the rule)."""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "native" / "chartread_helper" / "chromiq_margin.c"
MAXC = 128
WHY = {"Not enough patches": 1, "Too many patches": 2,
       "Swipe didn't start and end on the media": 3}
WP = np.array([96.42, 100.0, 82.49])


class Cands(ctypes.Structure):
    _fields_ = [("n", ctypes.c_int),
                ("ss", ctypes.c_int * MAXC),
                ("no", ctypes.c_int * MAXC),
                ("lab", (ctypes.c_double * 3) * MAXC),
                ("steps", ctypes.c_double * MAXC),
                ("flags", ctypes.c_int * MAXC),
                ("p0", ctypes.c_double * MAXC),
                ("net", ctypes.c_double),
                ("back", ctypes.c_double),
                ("skipped", ctypes.c_int)]


class Chart(ctypes.Structure):
    _fields_ = [("rows", ctypes.c_int), ("npatch", ctypes.c_int),
                ("lab", ctypes.POINTER(ctypes.c_double)), ("exp", ctypes.c_int)]


class Result(ctypes.Structure):
    _fields_ = [("accept", ctypes.c_int), ("rule", ctypes.c_char),
                ("sel", ctypes.c_int * MAXC),
                ("left_start", ctypes.c_int), ("left_end", ctypes.c_int),
                ("standing", ctypes.c_int), ("leader", ctypes.c_int),
                ("dir", ctypes.c_int), ("fit", ctypes.c_double),
                ("rival", ctypes.c_double), ("why", ctypes.c_char * 128),
                ("why_m", ctypes.c_char * 128), ("why_l", ctypes.c_char * 128)]


_LIB = None


def lib():
    """The compiled rule (built once per process); None without a compiler."""
    global _LIB
    if _LIB is not None:
        return _LIB
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None or sys.platform == "win32":
        return None
    out = Path(tempfile.mkdtemp(prefix="chromiq-margin-")) / "libcqm.so"
    subprocess.run([cc, "-O2", "-shared", "-fPIC", "-o", str(out), str(SRC), "-lm"],
                   check=True, capture_output=True, timeout=120)
    L = ctypes.CDLL(str(out))
    L.cqm_decide.argtypes = [ctypes.POINTER(Cands), ctypes.POINTER(Chart),
                             ctypes.c_int, ctypes.POINTER(Result)]
    L.cqm_decide.restype = ctypes.c_int
    L.cqm_xyz2lab.argtypes = [ctypes.POINTER(ctypes.c_double * 3),
                              ctypes.POINTER(ctypes.c_double * 3)]
    _LIB = L
    return L


def xyz2lab(X):
    """numpy twin of cqm_xyz2lab (checked against it in the tests)."""
    v = np.asarray(X, float) / WP
    f = np.where(v > 0.008856, np.cbrt(v), 7.787 * v + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def band_lab(v):
    """A 3-band trace value (0..1 per band) as Lab: the bands used as XYZ
    relative to D50 white. CIE scale, not a CIE colour."""
    return xyz2lab(np.asarray(v, float) * WP)


def ruler_of(steps, p0=None):
    """(p0, net, back) for SIGNED segment travels, as the helper computes them
    from the ruler: without p0 the segments follow on one from another; back =
    the most the position falls back against the net direction, over the
    segments' ends (the helper measures it over every ruler step)."""
    st = np.asarray(steps, float)
    if p0 is None:
        p0 = np.r_[0.0, np.cumsum(st)[:-1]]
    p0 = np.asarray(p0, float)
    path = np.ravel(np.c_[p0, p0 + st])
    net = path[-1] - path[0]
    x = path * (1 if net >= 0 else -1)
    back = float((np.maximum.accumulate(x) - x).max())
    return p0, float(net), back


def decide(lab, steps, no, chart_lab, exp, why, flags=None, ss=None,
           p0=None, net=None, back=None, skipped=0) -> dict:
    """lab: (n,3) candidates in swipe order; chart_lab: (rows,N,3); steps:
    each segment's SIGNED ruler travel (positive = the strip's direction
    unless net says otherwise). p0 / net / back default to ruler_of(steps)."""
    L = lib()
    c = Cands()
    n = len(lab)
    c.n = n
    p0d, netd, backd = ruler_of(steps, p0)
    c.net = netd if net is None else float(net)
    c.back = backd if back is None else float(back)
    c.skipped = int(skipped)
    for i in range(n):
        c.ss[i] = int(ss[i]) if ss is not None else i * 10
        c.no[i] = int(no[i])
        c.steps[i] = float(steps[i])
        c.p0[i] = float(p0d[i])
        c.flags[i] = int(flags[i]) if flags is not None else 0
        for k in range(3):
            c.lab[i][k] = float(lab[i][k])
    arr = np.ascontiguousarray(chart_lab, dtype=np.float64)
    ch = Chart(arr.shape[0], arr.shape[1],
               arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), int(exp))
    r = Result()
    L.cqm_decide(ctypes.byref(c), ctypes.byref(ch), int(why), ctypes.byref(r))
    N = arr.shape[1]
    return {"accept": bool(r.accept), "rule": r.rule.decode() if r.rule else "",
            "sel": list(r.sel[:N]) if r.accept else [], "dir": r.dir,
            "left_start": r.left_start, "left_end": r.left_end,
            "standing": r.standing, "fit": r.fit, "rival": r.rival,
            "why": r.why.decode(), "why_m": r.why_m.decode(),
            "why_l": r.why_l.decode()}


if os.environ.get("CQM_SELFTEST"):
    print(lib())
