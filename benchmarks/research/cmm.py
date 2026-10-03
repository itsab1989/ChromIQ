"""Read a profile the way colour management systems read it (Agent 6).

There is no single "real CMM" (agent 1, Findings/agent1-04; agent 2,
Reports/agent2-04). Every profile is therefore scored through each readout
separately, and each gets its own column. The argyll, lcms and colorsync
columns ARE the real CMMs (the profile bytes go through their code), so each
reads with whatever kernel that CMM picks for that profile; ``KERNELS``
records what that is, measured by :mod:`kernels` and pinned by
``tests/test_benchmarks_research_kernels.py`` (v2, flaw 7):

| reader | A2B, 3 inks (RGB/CMY) | A2B, 4 inks (CMYK) | A2B, 5-8 inks (nCLR) | B2A (Lab PCS) |
|---|---|---|---|---|
| ``argyll`` (icclu) | simplex | simplex | N-linear (multilinear) | N-linear (trilinear) |
| ``lcms`` (2.x) | tetrahedral (= 3-D simplex) | linear in ink 1 over tetrahedral | linear over the first n-3 inks, tetrahedral in the last 3 | trilinear |
| ``colorsync`` | multilinear | multilinear | multilinear, when it loads | multilinear |
| ``multilinear`` | multilinear | multilinear | multilinear | multilinear |

ColorSync crashes the process (segfault in Quartz) on some multi-ink
profiles; v1 saw it on every engine 6- and 7-ink build, the v2 probe sees it
on ``MCH6`` and ``5CLR`` random tables but not on ``6CLR``/``7CLR`` ones, so
it is decided per profile in a child process (``colorsync_supported``).
Argyll's choice is ``icmPeClut_choose_alg`` (icc/icc_xf.c:1373): simplex for
RGB/CMY/CMYK/MCH6 input signatures; the engine writes 5-8 inks as ``nCLR``,
for which Argyll falls back to N-linear (agent 7 T6, re-measured here). A
profile labelled ``MCH6`` would be read simplex. So "the battery reads
multilinearly while CMMs read simplex" is true only for 3 and 4 inks in
Argyll and lcms; for 6 and 7 inks the multilinear column IS Argyll's kernel.

* ``argyll``     ArgyllCMS icclib via ``icclu``
* ``lcms``       littleCMS 2 (the copy bundled with Pillow), float formats,
                 cmsFLAGS_NOOPTIMIZE so the tables are read as written
* ``colorsync``  Apple ColorSync through Quartz ``CGColorCreateCopyByMatchingTo
                 ColorSpace`` (relative colorimetric, D50 Lab space). Slow
                 (one call per colour), so it runs on a subsample. The Quartz
                 Lab space is built with the a*/b* range [-127.5, 127.5]
                 (v2, flaw 4): v1 used [-128, 127], which reads every colour
                 0.5 low in a* and b* (orchestrator O1: sRGB white -> a* = b*
                 = -0.500; exactly 0 with a symmetric range). ColorSync does
                 scale lut16 Lab L* by about 0.39 % (v4-style L*; agent 7 T4).
* ``multilinear`` the September battery's own reader (benchmarks/iccread.py),
                 a continuity column; it is also the kernel of ColorSync and
                 of Argyll for nCLR profiles.

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
# Quartz Lab colour space a*/b* range. Symmetric, or white reads a*=b*=-0.5.
QUARTZ_LAB_RANGE = [-127.5, 127.5, -127.5, 127.5]
QUARTZ_LAB_RANGE_V1 = [-128, 127, -128, 127]       # v1, wrong; re-derivation only

KERNELS = {
    "argyll": {"a2b3": "simplex", "a2b4": "simplex", "a2bN": "multilinear",
               "b2a": "multilinear"},
    "lcms": {"a2b3": "simplex", "a2b4": "lcms-linear-over-tetrahedral",
             "a2bN": "lcms-linear-over-tetrahedral", "b2a": "multilinear"},
    "colorsync": {"a2b3": "multilinear", "a2b4": "multilinear", "a2bN": "multilinear",
                  "b2a": "multilinear"},
    "multilinear": {"a2b3": "multilinear", "a2b4": "multilinear",
                    "a2bN": "multilinear", "b2a": "multilinear"},
}


def kernel_of(reader: str, n_inks: int, direction: str = "a2b") -> str | None:
    """The interpolation kernel ``reader`` uses on an engine profile with
    ``n_inks`` device channels (nCLR signature for 5+)."""
    if direction == "b2a":
        return KERNELS[reader]["b2a"]
    return KERNELS[reader]["a2b3" if n_inks == 3 else "a2b4" if n_inks == 4 else "a2bN"]


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
    if data[:3] == b"MCH":                       # MCH5..MCHF
        return int(data[3:4], 16), False
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


def _colorsync(path: Path, rows: np.ndarray, forward: bool,
               lab_range: list | None = None) -> np.ndarray:
    import Quartz as Q
    data = Path(path).read_bytes()
    prof = Q.CGColorSpaceCreateWithICCData(Q.CFDataCreate(None, data, len(data)))
    if prof is None:
        raise RuntimeError("ColorSync refused the profile")
    lab = Q.CGColorSpaceCreateLab([0.9642, 1.0, 0.8249], [0, 0, 0],
                                  list(lab_range or QUARTZ_LAB_RANGE))
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


def _cs_range(reader: str) -> list:
    # "colorsync-v1range" re-derives what v1 published (wrong range); never
    # a column of a new benchmark.
    return QUARTZ_LAB_RANGE_V1 if reader == "colorsync-v1range" else QUARTZ_LAB_RANGE


# --- public -------------------------------------------------------------------
def a2b(path: Path | str, device01: np.ndarray, reader: str) -> np.ndarray:
    path = Path(path)
    device01 = np.atleast_2d(np.asarray(device01, float))
    if reader == "argyll":
        return _xicclu(path, "f", device01, 3)
    if reader == "lcms":
        return _lcms_run(path, device01, True)
    if reader in ("colorsync", "colorsync-v1range"):
        if not colorsync_supported(str(path)):
            raise ColorSyncUnsupported("ColorSync crashes on this profile (process fault)")
        return _colorsync(path, device01, True, _cs_range(reader))
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
    if reader in ("colorsync", "colorsync-v1range"):
        if not colorsync_supported(str(path)):
            raise ColorSyncUnsupported("ColorSync crashes on this profile (process fault)")
        return np.clip(_colorsync(path, lab, False, _cs_range(reader)), 0.0, 1.0)
    if reader == "multilinear":
        from benchmarks.iccread import IccProfile
        return IccProfile(path).b2a_device(lab)
    raise KeyError(reader)
