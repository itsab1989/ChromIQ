"""d01 challenge: four independent ColorSync entry points, plus Argyll/lcms references.

Paths (all relative colorimetric):
  cgcolor  : CGColorCreateCopyByMatchingToColorSpace (agent 7's path)
  bitmap   : draw a 16-bit CGImage into a CGBitmapContext whose colour space is the
             destination profile (what Preview / cgpdftoraster / CG drawing do)
  cstrans  : ColorSyncTransformCreate + ColorSyncTransformConvert (ColorSync CMM API),
             32-bit float in and out
  sips     : `sips -M profile relative` on a 16-bit TIFF (ImageIO/ColorSync)
Colours enter as sRGB (the app case) or as Generic XYZ (exact PCS targets, no Lab
colour space involved, so no Lab range question). A2B is read out into Generic XYZ.
"""
import ctypes, ctypes.util, subprocess, sys, tempfile, os
from pathlib import Path
import numpy as np
import objc, Quartz as Q
W = "/Users/Basti/develop/ProfileEngineResearch/Experiments/agent24/score"
sys.path.insert(0, W)
from benchmarks.research import cmm, colour   # noqa: E402

D50 = np.array([0.9642, 1.0, 0.8249])
REL = Q.kCGRenderingIntentRelativeColorimetric
SRGB = Q.CGColorSpaceCreateWithName(Q.kCGColorSpaceSRGB)
XYZS = Q.CGColorSpaceCreateWithName(Q.kCGColorSpaceGenericXYZ)
SCR = Path(__file__).parent / "work"; SCR.mkdir(exist_ok=True)

def space(p):
    d = Path(p).read_bytes(); return Q.CGColorSpaceCreateWithICCData(Q.CFDataCreate(None, d, len(d)))

def nch(sp): return Q.CGColorSpaceGetNumberOfComponents(sp)

def xyz2lab(x):
    f = lambda t: np.where(t > (6/29)**3, np.cbrt(t), t/(3*(6/29)**2) + 4/29)
    fx, fy, fz = (f(x[:, i]/D50[i]) for i in range(3))
    return np.column_stack([116*fy-16, 500*(fx-fy), 200*(fy-fz)])

def lab2xyz(l):
    fy = (l[:, 0]+16)/116; fx = fy + l[:, 1]/500; fz = fy - l[:, 2]/200
    fi = lambda t: np.where(t > 6/29, t**3, 3*(6/29)**2*(t-4/29))
    return np.column_stack([fi(fx), fi(fy), fi(fz)]) * D50

# ---------- path 1: CGColor
def cgcolor(src_sp, dst_sp, rows):
    n = nch(dst_sp); out = []
    for r in rows:
        m = Q.CGColorCreateCopyByMatchingToColorSpace(dst_sp, REL, Q.CGColorCreate(src_sp, [float(v) for v in r] + [1.0]), None)
        c = Q.CGColorGetComponents(m); out.append([c[i] for i in range(n)])
    return np.array(out)

# ---------- path 2: CGBitmapContext (float 32, so no 8-bit quantisation)
def _img(src_sp, rows):
    n = rows.shape[1]; buf = np.ascontiguousarray(rows, dtype="<f4").tobytes()
    prov = Q.CGDataProviderCreateWithData(None, buf, len(buf), None)
    info = Q.kCGBitmapFloatComponents | Q.kCGBitmapByteOrder32Little | Q.kCGImageAlphaNone
    return Q.CGImageCreate(len(rows), 1, 32, 32 * n, 4 * n * len(rows), src_sp, info, prov, None, False, REL), buf

def bitmap(src_sp, dst_sp, rows):
    """float 32 bitmap; RGB destinations need a skipped 4th slot (CG's supported formats)."""
    rows = np.asarray(rows, float); img, keep = _img(src_sp, rows); n = nch(dst_sp)
    slots = 4 if n == 3 else n
    alpha = Q.kCGImageAlphaNoneSkipLast if n == 3 else Q.kCGImageAlphaNone
    info = Q.kCGBitmapFloatComponents | Q.kCGBitmapByteOrder32Little | alpha
    buf = bytearray(4 * slots * len(rows))
    ctx = Q.CGBitmapContextCreate(buf, len(rows), 1, 32, 4 * slots * len(rows), dst_sp, info)
    assert ctx is not None, "no bitmap context"
    Q.CGContextSetRenderingIntent(ctx, REL); Q.CGContextSetInterpolationQuality(ctx, Q.kCGInterpolationNone)
    Q.CGContextSetBlendMode(ctx, Q.kCGBlendModeCopy)
    Q.CGContextDrawImage(ctx, Q.CGRectMake(0, 0, len(rows), 1), img)
    Q.CGContextFlush(ctx)
    return np.frombuffer(bytes(buf), "<f4").reshape(len(rows), slots)[:, :n].astype(float)

# ---------- path 3: ColorSync CMM API via ctypes
_cs = ctypes.CDLL("/System/Library/Frameworks/ColorSync.framework/ColorSync")
_cs.ColorSyncProfileCreate.restype = ctypes.c_void_p; _cs.ColorSyncProfileCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_cs.ColorSyncProfileCreateWithName.restype = ctypes.c_void_p; _cs.ColorSyncProfileCreateWithName.argtypes = [ctypes.c_void_p]
_cs.ColorSyncTransformCreate.restype = ctypes.c_void_p; _cs.ColorSyncTransformCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_cs.ColorSyncTransformConvert.restype = ctypes.c_bool
_cs.ColorSyncTransformConvert.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32, ctypes.c_size_t,
                                          ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32, ctypes.c_size_t, ctypes.c_void_p]
def _k(name): return objc.objc_object(c_void_p=ctypes.c_void_p(ctypes.c_void_p.in_dll(_cs, name).value))
K = {n: _k(n) for n in ("kColorSyncProfile", "kColorSyncRenderingIntent", "kColorSyncRenderingIntentRelative",
                         "kColorSyncTransformTag", "kColorSyncTransformDeviceToPCS", "kColorSyncTransformPCSToDevice",
                         "kColorSyncSRGBProfile", "kColorSyncGenericXYZProfile")}
def csprofile(p):
    p = {"sRGB": "/System/Library/ColorSync/Profiles/sRGB Profile.icc",
         "XYZ": "/System/Library/ColorSync/Profiles/Generic XYZ Profile.icc"}.get(p, p)
    if True:
        d = Path(p).read_bytes(); cf = Q.CFDataCreate(None, d, len(d))
        ptr = _cs.ColorSyncProfileCreate(objc.pyobjc_id(cf), None)
    assert ptr, p
    return objc.objc_object(c_void_p=ptr)
F32 = 7; LE32 = 2 << 12
def cstrans(src, dst, rows, nout):
    seq = [{K["kColorSyncProfile"]: csprofile(src), K["kColorSyncRenderingIntent"]: K["kColorSyncRenderingIntentRelative"],
            K["kColorSyncTransformTag"]: K["kColorSyncTransformDeviceToPCS"]},
           {K["kColorSyncProfile"]: csprofile(dst), K["kColorSyncRenderingIntent"]: K["kColorSyncRenderingIntentRelative"],
            K["kColorSyncTransformTag"]: K["kColorSyncTransformPCSToDevice"]}]
    from Foundation import NSArray, NSDictionary
    arr = NSArray.arrayWithArray_([NSDictionary.dictionaryWithDictionary_(d) for d in seq])
    t = _cs.ColorSyncTransformCreate(objc.pyobjc_id(arr), None); assert t, "transform"
    src_b = np.ascontiguousarray(rows, "<f4"); nin = src_b.shape[1]
    dst_b = np.zeros((len(rows), nout), "<f4")
    ok = _cs.ColorSyncTransformConvert(t, len(rows), 1, dst_b.ctypes.data, F32, LE32, 4 * nout * len(rows),
                                       src_b.ctypes.data, F32, LE32, 4 * nin * len(rows), None)
    assert ok, "convert"
    return dst_b.astype(float)

# ---------- path 4: sips on a 16-bit TIFF
def sips_srgb_to(dst_profile, rgb01):
    import tifffile
    with tempfile.TemporaryDirectory(dir=SCR) as td:
        a = np.round(np.clip(rgb01, 0, 1) * 65535).astype("<u2").reshape(1, len(rgb01), 3)
        src = Path(td) / "in.tif"; out = Path(td) / "out.tif"
        tifffile.imwrite(src, a, photometric="rgb", iccprofile=Path("/System/Library/ColorSync/Profiles/sRGB Profile.icc").read_bytes())
        r = subprocess.run(["sips", "-M", str(dst_profile), "relative", str(src), "--out", str(out)], capture_output=True, text=True, timeout=120, encoding="utf-8")
        assert out.exists(), r.stderr
        b = tifffile.imread(out)
        return b.reshape(len(rgb01), -1).astype(float) / (65535.0 if b.dtype == np.uint16 else 255.0), b.dtype, r.stdout + r.stderr

# ---------- references: Argyll icclu and littleCMS on the same PCS values
def b2a_ref(p, lab, reader="argyll"): return cmm.b2a(p, lab, reader)
def a2b_ref(p, dev, reader="argyll"): return cmm.a2b(p, dev, reader)
