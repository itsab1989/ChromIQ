"""Argyll's own CIECAM02 forward transform (XYZ -> Jab), ported from ArgyllCMS
3.5.0 xicc/cam02.c (set_view, XYZ_to_cam, bluelin_fwd), for the research
token a51-colprofedge (Agent 51, ProfileEngineResearch Findings/agent51-01).

colprof clips out-of-gamut colours of the colorimetric B2A to the nearest
printable colour in THIS space (profile/profout.c USE_CAM_CLIP_OPT,
xicc/xlut.c icxLuLut_init_clut_camclip). It is not textbook CIECAM02:
Argyll adds flare / glare, compresses cone responses that would go below
zero ("ENABLE_COMPR": imaginary and very dark saturated colours, which
textbook CIECAM02 sends to absurd chroma), limits the ab scale ratio
("ENABLE_DDL"), straight-line extensions of the non-linearity, a blue hue
angle limit and blue linearisation, and a reduced Helmholtz-Kohlrausch
lightness lift. The B2A grid holds such colours at every dark, saturated
node, so the plain CIECAM02 of ``cam02.py`` cannot stand in for it there
(measured: a node at L* 9.4, C* 47 clips to L* 47 / C* 71 in textbook
CIECAM02, to L* 25 / C* 32 in Argyll, where colprof's own table has it).

Forward only (the clip needs distances, never the inverse). Input: XYZ with
the reference white's Y = 1. Constants and the order of operations follow
cam02.c line by line; no partial mid-tone adaptation (colprof's default).
"""
from __future__ import annotations

import numpy as np

# cam02.c defines (3.5.0)
_BC_WHMINY = 0.2
_BC_RANGE = (0.01, 0.01, 0.01)
_BC_MAXRANGE = 0.13
_BC_LIMIT = 0.7
_BLUE_BL_MAX = 0.9
_BLUE_BL_POW = 3.5
_NLDLIMIT = 0.00001
_NLDICEPT = -0.18
_NLULIMIT = 1e5
_DDLLIMIT = 0.55
_DDULIMIT = 0.34
_SSMINCJ = 0.005
_JLIMIT = 0.005
_HKLIMIT = 0.7
_HHKR_MUL = 0.25
_BLUELIN = (210.0, 330.0, 50.0, 80.0, 140.0, 0.60)   # h0, h1, C0, C10, C11, amount

_SURROUND = {"average": (0.69, 1.0, 1.0), "dim": (0.59, 0.95, 0.9),
             "dark": (0.525, 0.8, 0.8)}               # C, Nc, F (set_view)

_MCAT02 = np.array([[0.7328, 0.4296, -0.1624],
                    [-0.7036, 1.6975, 0.0061],
                    [0.0, 0.0, 1.0]])
_MHPE_FROM_CAT = np.array([[0.7409744840453773, 0.2180245944753982, 0.0410009214792244],
                           [0.2853532916858801, 0.6242015741188157, 0.0904451341953042],
                           [-0.0096276087384294, -0.0056980312161134, 1.0153256399545427]])


class ArgyllCam02:
    """cam02.c XYZ_to_cam under fixed viewing conditions (vc_average etc.)."""

    def __init__(self, white=(0.9642, 1.0, 0.8249), La: float = 40.0, Yb: float = 0.2,
                 Yf: float = 0.0, Yg: float = 0.01, surround: str = "average",
                 hk: bool = True, hkscale: float = 1.0, bluelin: bool = True) -> None:
        w = np.asarray(white, float)
        C, Nc, F = _SURROUND[surround]
        Lv = La / {"average": 0.2, "dim": 0.1, "dark": 0.033}[surround]
        self.C, self.Nc, self.F = C, Nc, F
        self.hk, self.hkscale, self.bluelin = hk, hkscale, bluelin
        self.W = w
        Yb = max(Yb, 0.005)
        # flare + glare (glare colour = the white)
        fs = Yf * w + (Yg * La / Lv) * w
        self.Fsc = w[1] / (fs[1] + w[1])
        self.Fsxyz = fs * self.Fsc
        rgbW = _MCAT02 @ w
        D = F * (1.0 - np.exp((-La - 42.0) / 92.0) / 3.6)
        Drgb = D * (w[1] / rgbW) + 1.0 - D
        rgbcW = Drgb * rgbW
        self.rgbpW = _MHPE_FROM_CAT @ rgbcW
        self.cc = _MHPE_FROM_CAT @ np.diag(Drgb) @ _MCAT02
        self.n = Yb / w[1]
        self.nn = (1.64 - 0.29 ** self.n) ** 0.73
        k = 1.0 / (5.0 * La + 1.0)
        self.Fl = 0.2 * k ** 4 * 5.0 * La + 0.1 * (1.0 - k ** 4) ** 2 * (5.0 * La) ** (1.0 / 3.0)
        self.Nbb = self.Ncb = 0.725 * (1.0 / self.n) ** 0.2
        self.z = 1.48 + self.n ** 0.5
        rgbaW = self._nl_plain(self.rgbpW)
        self.Aw = (2.0 * rgbaW[0] + rgbaW[1] + rgbaW[2] / 20.0 - 0.305) * self.Nbb
        self.nldxval = self._nl_plain(np.array([_NLDLIMIT]))[0]
        self.nldxslope = (self.nldxval - 0.1) / (_NLDLIMIT - _NLDICEPT)
        self.nluxval = self._nl_plain(np.array([_NLULIMIT]))[0]
        t1 = self.Fl * _NLULIMIT
        t2 = t1 ** 0.42 + 27.13
        self.nluxslope = 0.42 * self.Fl * 400.0 * 27.13 / (t1 ** 0.58 * t2 * t2)
        self.lA = _JLIMIT ** (1.0 / (self.C * self.z)) * self.Aw

    def _nl_plain(self, v):
        tt = (self.Fl * np.asarray(v, float)) ** 0.42
        return 400.0 * tt / (tt + 27.13) + 0.1

    def _nl(self, v):
        lo = v < _NLDLIMIT
        hi = v > _NLULIMIT
        mid = self._nl_plain(np.clip(v, _NLDLIMIT, _NLULIMIT))
        out = np.where(lo, self.nldxval + self.nldxslope * (v - _NLDLIMIT), mid)
        return np.where(hi, self.nluxval + self.nluxslope * (v - _NLULIMIT), out)

    def xyz_to_jab(self, xyz: np.ndarray) -> np.ndarray:
        xyz = np.atleast_2d(np.asarray(xyz, float))
        x = self.Fsc * xyz + self.Fsxyz[None, :]
        rgbp = x @ self.cc.T
        # ENABLE_COMPR: compress rgbp toward a white of the same Y
        tt = np.maximum(x[:, 1], _BC_WHMINY)
        wrgb = self.rgbpW[None, :] * (tt / self.W[1])[:, None]
        for i in range(3):
            cvec = wrgb - rgbp
            ok = cvec[:, i] >= 1e-9
            cvn = cvec / np.where(ok, cvec[:, i], 1.0)[:, None]
            isec = rgbp - cvn * rgbp[:, i:i + 1]
            offs = np.linalg.norm(isec, axis=1) ** 0.85
            rng = np.minimum(_BC_RANGE[i] * offs, _BC_MAXRANGE)
            asym = rng - 0.2 * (rng + 0.01 * _BC_RANGE[i])
            cv = rgbp[:, i]
            need = ok & (cv < rng - 1e-12)
            if need.any():
                aa = 1.0 / np.where(need, rng - cv, 1.0)
                bb = 1.0 / np.where(need, rng - asym, 1.0)
                cd = np.minimum((rng - 1.0 / (aa + bb)) - cv, _BC_LIMIT)
                rgbp = rgbp + np.where(need, cd, 0.0)[:, None] * cvn
        # ENABLE_BLUE_ANGLE_FIX
        s3 = rgbp.sum(1)
        ss = np.where(s3 < 1e-9, 0.0, (rgbp[:, 2] / np.where(s3 < 1e-9, 1.0, s3) - 1.0 / 3.0) * 1.5)
        ss = np.where(ss > 0.0, _BLUE_BL_MAX * np.abs(ss) ** _BLUE_BL_POW, ss)
        ss = np.clip(ss, 0.0, 1.0)
        t = 0.5 * (rgbp[:, 0] + rgbp[:, 1])
        rgbp = rgbp.copy()
        rgbp[:, 0] = ss * t + (1.0 - ss) * rgbp[:, 0]
        rgbp[:, 1] = ss * t + (1.0 - ss) * rgbp[:, 1]
        rgba = self._nl(rgbp)
        ttA = 2.0 * rgba[:, 0] + rgba[:, 1] + rgba[:, 2] / 20.0
        A = (ttA - 0.305) * self.Nbb
        a = rgba[:, 0] - 12.0 / 11.0 * rgba[:, 1] + rgba[:, 2] / 11.0
        b = (rgba[:, 0] + rgba[:, 1] - 2.0 * rgba[:, 2]) / 9.0
        rS = np.maximum(np.hypot(a, b), np.finfo(float).eps)
        cz = self.C * self.z
        J = np.where(A >= 0.0, np.abs(A / self.Aw) ** cz, -np.abs(A / self.Aw) ** cz)   # SYMETRICJ
        cJ = np.where(A > 0.0, np.maximum(np.abs(A / self.Aw) ** cz, _SSMINCJ), _SSMINCJ)
        h = np.degrees(np.arctan2(b, a)) % 360.0
        e = 12500.0 / 13.0 * self.Nc * self.Ncb * (np.cos(np.radians(h) + 2.0) + 3.8)
        k1 = self.nn ** (1.0 / 0.9) * e * cJ ** (1.0 / 1.8) / rS ** (1.0 / 9.0)
        k2 = cJ ** (1.0 / cz) * self.Aw / self.Nbb + 0.305
        k3 = -11.0 / 23.0 * a - 108.0 / 23.0 * b
        k3 = np.maximum(k3, -k2 * _DDLLIMIT)                              # ENABLE_DDL
        k3 = np.minimum(k3, k2 * _DDULIMIT / (1.0 - _DDULIMIT))
        scale = (k1 / (k2 + k3)) ** 0.9
        ja, jb = a * scale, b * scale
        JJ = J
        if self.hk:
            Cc = np.hypot(ja, jb)
            kk = self.hkscale * _HHKR_MUL * Cc / 300.0 * np.sin(np.radians(np.abs(0.5 * (h - 90.0))))
            kk = np.where(kk > 1e-6, 1.0 / (1.0 / _HKLIMIT + 1.0 / np.maximum(kk, 1e-12)), kk)
            JJ = np.where(J < 1.0, J + (1.0 - np.maximum(J, 0.0)) * kk, J)
        jab = np.stack([100.0 * JJ, ja, jb], 1)
        if self.bluelin:
            jab = _bluelin_fwd(jab)
        return jab


def _bluelin_fwd(jab):
    h0, h1, c0, c10, c11, amt = _BLUELIN
    C = np.hypot(jab[:, 1], jab[:, 2])
    h = np.degrees(np.arctan2(jab[:, 2], jab[:, 1])) % 360.0
    sel = (h >= h0) & (h <= h1) & (C > c0)
    hh = (h - h0) / (h1 - h0)
    c1 = (1.0 - hh) * c10 + hh * c11
    gr = np.clip((C - c0) / np.where(sel, c1 - c0, 1.0), 0.0, 1.0)
    am = (1.0 - gr) + gr * amt
    hn = np.where(hh < 0.5, hh * am, 0.5 * am + (hh - 0.5) * (1.0 - 0.5 * am) / 0.5)
    h2 = np.where(sel, h0 + hn * (h1 - h0), h)
    out = jab.copy()
    out[:, 1] = C * np.cos(np.radians(h2))
    out[:, 2] = C * np.sin(np.radians(h2))
    return out


_DEFAULT = {}


def lab_to_jab(lab: np.ndarray, **vc) -> np.ndarray:
    """D50-relative Lab -> Argyll Jab (white D50, colprof's print defaults:
    La 40, Yb 0.2, average surround, no flare, 1 % glare)."""
    from workflow.profile_engine.ti3_data import lab_to_xyz
    key = tuple(sorted(vc.items()))
    if key not in _DEFAULT:
        _DEFAULT[key] = ArgyllCam02(**vc)
    xyz = lab_to_xyz(np.atleast_2d(np.asarray(lab, float))) / 100.0
    return _DEFAULT[key].xyz_to_jab(xyz)
