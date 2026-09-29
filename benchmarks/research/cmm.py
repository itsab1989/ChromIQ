"""Read a profile the way colour management systems read it (Agent 6).

There is no single "real CMM" (agent 1, Findings/agent1-04; agent 2,
Reports/agent2-04). Every profile is therefore scored through each readout
separately, and each gets its own column:

* ``argyll``     ArgyllCMS icclib via ``icclu`` (A2B simplex, B2A multilinear)
* ``lcms``       littleCMS 2 (the copy bundled with Pillow), float formats,
                 cmsFLAGS_NOOPTIMIZE so the tables are read as written
                 (A2B tetrahedral for 3 inputs, linear-over-tetrahedral for 4+,
                 B2A trilinear)
* ``colorsync``  Apple ColorSync through Quartz ``CGColorCreateCopyByMatchingTo
                 ColorSpace`` (relative colorimetric, D50 Lab space); agent 1
                 measured it reads lut16 Lab with the v4 encoding. Slow (one
                 call per colour), so it runs on a subsample.
* ``multilinear`` the September battery's own reader (benchmarks/iccread.py),
                 kept only as a continuity column.

All functions: ``a2b(path, device01) -> Lab`` and ``b2a(path, lab) -> device01``,
relative colorimetric (A2B1 / B2A1).
"""
from __future__ import annotations

import ctypes
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

ICCLU = "/Applications/Argyll/bin/icclu"
READERS = ("argyll", "lcms", "colorsync", "multilinear")


# --- Argyll -----------------------------------------------------------------
def _xicclu(path: Path, direction: str, rows: np.ndarray, n_out: int,
            argyll_bin: str | None = None) -> np.ndarray:
    # icclu, not xicclu: identical numbers on <= 4 inks (checked), and
    # xicclu refuses > 4 inks even forward ("rev_set_lchw can't handle di").
    exe = str(Path(argyll_bin) / "icclu") if argyll_bin else ICCLU
    inp = "\n".join(" ".join(f"{v:.7f}" for v in r) for r in rows) + "\n"
    out = subprocess.run([exe, "-v0", f"-f{direction}", "-ir", "-pl", str(path)],
                         input=inp, capture_output=True, text=True,
                         timeout=900, check=True).stdout
    arr = np.array([[float(x) for x in ln.split()[:n_out]]
                    for ln in out.splitlines() if ln.strip()])
    if arr.shape != (len(rows), n_out):
        raise RuntimeError(f"xicclu returned {arr.shape} for {len(rows)} rows")
    return arr


# --- littleCMS ----------------------------------------------------------------
@lru_cache(maxsize=None)
def _lcms():
    import PIL
    cands = sorted(Path(PIL.__file__).parent.joinpath(".dylibs").glob("liblcms2*"))
    lib = ctypes.CDLL(str(cands[0]))
    lib.cmsOpenProfileFromFile.restype = ctypes.c_void_p
    lib.cmsOpenProfileFromFile.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.cmsCreateLab4Profile.restype = ctypes.c_void_p
    lib.cmsCreateLab4Profile.argtypes = [ctypes.c_void_p]
    lib.cmsCreateTransform.restype = ctypes.c_void_p
    lib.cmsCreateTransform.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.c_void_p, ctypes.c_uint32,
                                       ctypes.c_uint32, ctypes.c_uint32]
    lib.cmsDoTransform.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_uint32]
    lib.cmsDeleteTransform.argtypes = [ctypes.c_void_p]
    lib.cmsCloseProfile.argtypes = [ctypes.c_void_p]
    lib.cmsGetColorSpace.argtypes = [ctypes.c_void_p]
    lib.cmsGetColorSpace.restype = ctypes.c_uint32
    return lib


_PT = {3: 4, 4: 6}                     # RGB, CMYK; n >= 5 -> PT_MCHn
_NOOPT, _NOCACHE = 0x0100, 0x0040


def _fmt(pt: int, ch: int) -> int:
    return (1 << 22) | (pt << 16) | (ch << 3)        # FLOAT_SH | COLORSPACE | CHANNELS


def _dev_fmt(n: int, additive: bool) -> tuple[int, float]:
    if n == 3 and additive:
        return _fmt(4, 3), 1.0
    if n == 3:
        return _fmt(5, 3), 100.0                     # PT_CMY, ink space 0..100
    if n == 4:
        return _fmt(6, 4), 100.0
    return _fmt(14 + n, n), 100.0                    # PT_MCH5 = 19 ... ink space


def _profile_n(path: Path) -> tuple[int, bool]:
    data = Path(path).read_bytes()[16:20]
    table = {b"RGB ": (3, True), b"CMY ": (3, False), b"CMYK": (4, False)}
    if data in table:
        return table[data]
    return int(data[:1], 16) if data[1:] == b"CLR" else int(data[:1]), False


def _lcms_run(path: Path, rows: np.ndarray, forward: bool) -> np.ndarray:
    lib = _lcms()
    n, additive = _profile_n(path)
    dfmt, dscale = _dev_fmt(n, additive)
    lab_fmt = _fmt(10, 3)
    hp = lib.cmsOpenProfileFromFile(str(path).encode(), b"r")
    hl = lib.cmsCreateLab4Profile(None)
    if forward:
        t = lib.cmsCreateTransform(hp, dfmt, hl, lab_fmt, 1, _NOOPT | _NOCACHE)
        src = np.ascontiguousarray(rows * dscale, dtype=np.float64)
        dst = np.zeros((len(rows), 3))
    else:
        t = lib.cmsCreateTransform(hl, lab_fmt, hp, dfmt, 1, _NOOPT | _NOCACHE)
        src = np.ascontiguousarray(rows, dtype=np.float64)
        dst = np.zeros((len(rows), n))
    if not t:
        lib.cmsCloseProfile(hp)
        lib.cmsCloseProfile(hl)
        raise RuntimeError(f"lcms could not build a transform for {path}")
    lib.cmsDoTransform(t, src.ctypes.data, dst.ctypes.data, len(rows))
    lib.cmsDeleteTransform(t)
    lib.cmsCloseProfile(hp)
    lib.cmsCloseProfile(hl)
    return dst if forward else dst / dscale


# --- ColorSync ------------------------------------------------------------------
@lru_cache(maxsize=None)
def colorsync_supported(path: str) -> bool:
    """Probe in a child process: Quartz segfaults (not raises) on some
    profiles - measured on every 6- and 7-ink profile, 2026-09-29."""
    import sys
    code = ("import numpy as np, sys; sys.path.insert(0, %r); "
            "from benchmarks.research import cmm; "
            "cmm._colorsync(%r, np.array([[50.0, 0, 0]]), False); "
            "n = cmm._profile_n(__import__('pathlib').Path(%r))[0]; "
            "cmm._colorsync(%r, np.zeros((1, n)), True); print('OK')"
            % (str(Path(__file__).parents[2]), path, path, path))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=120)
    return r.returncode == 0 and "OK" in r.stdout


class ColorSyncUnsupported(RuntimeError):
    pass


def _colorsync(path: Path, rows: np.ndarray, forward: bool) -> np.ndarray:
    import Quartz as Q
    data = Path(path).read_bytes()
    prof = Q.CGColorSpaceCreateWithICCData(Q.CFDataCreate(None, data, len(data)))
    if prof is None:
        raise RuntimeError("ColorSync refused the profile")
    lab = Q.CGColorSpaceCreateLab([0.9642, 1.0, 0.8249], [0, 0, 0],
                                  [-128, 127, -128, 127])
    n = Q.CGColorSpaceGetNumberOfComponents(prof)
    src, dst, n_out = (prof, lab, 3) if forward else (lab, prof, n)
    out = np.empty((len(rows), n_out))
    for i, r in enumerate(rows):
        c = Q.CGColorCreate(src, [float(v) for v in r] + [1.0])
        m = Q.CGColorCreateCopyByMatchingToColorSpace(
            dst, Q.kCGRenderingIntentRelativeColorimetric, c, None)
        comps = Q.CGColorGetComponents(m)
        out[i] = [comps[k] for k in range(n_out)]
    return out


# --- public -------------------------------------------------------------------
def a2b(path: Path | str, device01: np.ndarray, reader: str) -> np.ndarray:
    path = Path(path)
    device01 = np.atleast_2d(np.asarray(device01, float))
    if reader == "argyll":
        return _xicclu(path, "f", device01, 3)
    if reader == "lcms":
        return _lcms_run(path, device01, True)
    if reader == "colorsync":
        if not colorsync_supported(str(path)):
            raise ColorSyncUnsupported("ColorSync crashes on this profile (process fault)")
        return _colorsync(path, device01, True)
    if reader == "multilinear":
        from benchmarks.iccread import IccProfile
        return IccProfile(path).a2b_lab(device01)
    raise KeyError(reader)


def b2a(path: Path | str, lab: np.ndarray, reader: str) -> np.ndarray:
    path = Path(path)
    lab = np.atleast_2d(np.asarray(lab, float))
    n, _ = _profile_n(path)
    if reader == "argyll":
        return np.clip(_xicclu(path, "b", lab, n), 0.0, 1.0)
    if reader == "lcms":
        return np.clip(_lcms_run(path, lab, False), 0.0, 1.0)
    if reader == "colorsync":
        if not colorsync_supported(str(path)):
            raise ColorSyncUnsupported("ColorSync crashes on this profile (process fault)")
        return np.clip(_colorsync(path, lab, False), 0.0, 1.0)
    if reader == "multilinear":
        from benchmarks.iccread import IccProfile
        return IccProfile(path).b2a_device(lab)
    raise KeyError(reader)
