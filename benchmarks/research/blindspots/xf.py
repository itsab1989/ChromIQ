"""Agent 23: colour transforms the way applications run them, any intent.

The battery's ``cmm`` module reads the colorimetric tables (A2B1 / B2A1)
only. Applications also convert through the perceptual and saturation
intents, with black point compensation, from an RGB working space, at 8 or
16 bits with lcms's own pre-calculated grid. This module does all of that,
through real CMM code (lcms2 bundled with Pillow, Argyll icclu, Apple
ColorSync), and imports no engine code.

    lcms(src, dst, rows, intent, bpc=False, bits=0, optimise=False)
        src/dst: "lab" (D50, v4 Lab), "srgb" (lcms built-in), or a profile
        path; bits 0 = double, 8 or 16 = integer formats (what applications
        use); optimise=True = lcms default flags (pre-calculated grid)
    icclu(path, rows, direction, intent)  Argyll: "f" A2B, "b" B2A,
        "if" inverse A2B; intent p r s a
    colorsync(src, dst, rows, intent)  Quartz, one call per colour

Device values are 0..1 everywhere (0 = no ink for ink devices; RGB: 1 =
white), Lab is D50.
"""
from __future__ import annotations

import ctypes
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

from benchmarks.research import cmm

ARGYLL = "/Applications/Argyll/bin"
INTENTS = {"p": 0, "r": 1, "s": 2, "a": 3}
BPC = 0x2000
NOOPT = 0x0100
NOCACHE = 0x0040


@lru_cache(maxsize=None)
def _lib():
    lib = cmm._lcms()
    lib.cmsCreate_sRGBProfile.restype = ctypes.c_void_p
    lib.cmsCreate_sRGBProfile.argtypes = []
    lib.cmsCreateTransform.restype = ctypes.c_void_p
    lib.cmsDetectBlackPoint.restype = ctypes.c_int
    return lib


class _Prof:
    def __init__(self, spec):
        lib = _lib()
        self.spec = spec
        if spec == "lab":
            self.h = lib.cmsCreateLab4Profile(None)
            self.n, self.additive, self.kind = 3, False, "lab"
        elif spec == "srgb":
            self.h = lib.cmsCreate_sRGBProfile()
            self.n, self.additive, self.kind = 3, True, "dev"
        else:
            self.h = lib.cmsOpenProfileFromFile(str(spec).encode(), b"r")
            if not self.h:
                raise RuntimeError(f"lcms cannot open {spec}")
            self.n, self.additive = cmm._profile_n(Path(spec))
            self.kind = "dev"

    def fmt(self, bits: int) -> tuple[int, float]:
        if self.kind == "lab":
            pt = 10
        elif self.additive:
            pt = 4
        else:
            pt = {3: 5, 4: 6}.get(self.n, 14 + self.n)
        if bits == 0:
            scale = 1.0 if (self.kind == "lab" or self.additive) else 100.0
            return (1 << 22) | (pt << 16) | (self.n << 3), scale
        return (pt << 16) | (self.n << 3) | (2 if bits == 16 else 1), 0.0

    def close(self):
        _lib().cmsCloseProfile(self.h)


def _enc(rows, prof: _Prof, bits: int):
    if bits == 0:
        _, s = prof.fmt(0)
        return np.ascontiguousarray(rows * s, np.float64)
    top = 65535 if bits == 16 else 255
    if prof.kind == "lab":
        if bits == 16:
            e = np.stack([rows[:, 0] * 655.35, (rows[:, 1] + 128) * 257,
                          (rows[:, 2] + 128) * 257], 1)
        else:
            e = np.stack([rows[:, 0] * 2.55, rows[:, 1] + 128, rows[:, 2] + 128], 1)
    else:
        e = np.clip(rows, 0, 1) * top
    return np.ascontiguousarray(np.round(np.clip(e, 0, top)),
                                np.uint16 if bits == 16 else np.uint8)


def _dec(arr, prof: _Prof, bits: int):
    if bits == 0:
        _, s = prof.fmt(0)
        return arr / s
    a = arr.astype(float)
    if prof.kind == "lab":
        if bits == 16:
            return np.stack([a[:, 0] / 655.35, a[:, 1] / 257 - 128, a[:, 2] / 257 - 128], 1)
        return np.stack([a[:, 0] / 2.55, a[:, 1] - 128, a[:, 2] - 128], 1)
    return a / (65535 if bits == 16 else 255)


def lcms(src, dst, rows, intent: str = "r", bpc: bool = False, bits: int = 0,
         optimise: bool = False) -> np.ndarray:
    lib = _lib()
    rows = np.atleast_2d(np.asarray(rows, float))
    ps, pd = _Prof(src), _Prof(dst)
    try:
        fs, _ = ps.fmt(bits)
        fd, _ = pd.fmt(bits)
        flags = (BPC if bpc else 0) | (0 if optimise else NOOPT | NOCACHE)
        t = lib.cmsCreateTransform(ps.h, fs, pd.h, fd, INTENTS[intent], flags)
        if not t:
            raise RuntimeError(f"lcms: no transform {src} -> {dst} intent {intent}")
        s = _enc(rows, ps, bits)
        if bits == 0:
            out = np.zeros((len(rows), pd.n))
        else:
            out = np.zeros((len(rows), pd.n), np.uint16 if bits == 16 else np.uint8)
        lib.cmsDoTransform(ctypes.c_void_p(t), s.ctypes.data, out.ctypes.data, len(rows))
        lib.cmsDeleteTransform(ctypes.c_void_p(t))
        return _dec(out, pd, bits)
    finally:
        ps.close()
        pd.close()


def icclu(path, rows, direction: str = "b", intent: str = "r") -> np.ndarray:
    rows = np.atleast_2d(np.asarray(rows, float))
    n, _ = cmm._profile_n(Path(path))
    n_out = n if direction == "b" else (1 if direction == "g" else 3)
    inp = "\n".join(" ".join(f"{v:.7f}" for v in r) for r in rows) + "\n"
    out = subprocess.run([f"{ARGYLL}/icclu", "-v0", f"-f{direction}", f"-i{intent}",
                          "-pl", str(path)], input=inp, capture_output=True, text=True,
                         encoding="utf-8", timeout=1800, check=True).stdout
    arr = np.array([[float(x) for x in ln.split()[:n_out]]
                    for ln in out.splitlines() if ln.strip()])
    if arr.shape != (len(rows), n_out):
        raise RuntimeError(f"icclu returned {arr.shape}")
    return arr


_CS_INTENT = {"p": 1, "r": 2, "s": 4, "a": 3}


def colorsync(src, dst, rows, intent: str = "r") -> np.ndarray:
    """Quartz CGColor matching. src/dst: "lab" or a profile path."""
    import Quartz as Q
    intent_map = {"p": Q.kCGRenderingIntentPerceptual,
                  "r": Q.kCGRenderingIntentRelativeColorimetric,
                  "s": Q.kCGRenderingIntentSaturation,
                  "a": Q.kCGRenderingIntentAbsoluteColorimetric}

    def space(spec):
        if spec == "lab":
            return Q.CGColorSpaceCreateLab([0.9642, 1.0, 0.8249], [0, 0, 0],
                                           list(cmm.QUARTZ_LAB_RANGE)), 3
        if spec == "srgb":
            sp = Q.CGColorSpaceCreateWithName(Q.kCGColorSpaceSRGB)
            return sp, 3
        data = Path(spec).read_bytes()
        sp = Q.CGColorSpaceCreateWithICCData(Q.CFDataCreate(None, data, len(data)))
        return sp, Q.CGColorSpaceGetNumberOfComponents(sp)
    s, _ = space(src)
    d, nd = space(dst)
    rows = np.atleast_2d(np.asarray(rows, float))
    out = np.empty((len(rows), nd))
    for i, r in enumerate(rows):
        c = Q.CGColorCreate(s, [float(v) for v in r] + [1.0])
        m = Q.CGColorCreateCopyByMatchingToColorSpace(d, intent_map[intent], c, None)
        comps = Q.CGColorGetComponents(m)
        out[i] = [comps[k] for k in range(nd)]
    return out


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB 0..1 -> D50 Lab (lcms, relative colorimetric, float)."""
    return lcms("srgb", "lab", rgb, "r")


def adobe_to_lab(rgb: np.ndarray) -> np.ndarray:
    from benchmarks.research import run
    return lcms(run.SOURCE_GAMUT, "lab", rgb, "r")
