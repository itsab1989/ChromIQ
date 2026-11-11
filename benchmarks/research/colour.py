"""Referee colorimetry, independent of the engine (Agent 6).

Nothing here imports ``workflow.profile_engine``: the referee must not share
code with what it judges (agent 2, E4/E4b). Contents:

* 1 nm CIE 15 integration from the tables in ``data/cie_tables.json``
  (extracted from ArgyllCMS 3.5.0 ``xspect.c`` by ``extract_cie_tables``);
  5 nm illuminants linearly interpolated to 1 nm, 360-830 nm.
* Bradford media-white -> D50 adaptation and CIELAB against the ICC D50.
* CIEDE2000 (Sharma, Wu, Dalal 2005) and ITP Delta E (ITU-R BT.2124,
  via ICtCp from XYZ under D65 adaptation, absolute scale 100 cd/m2 white).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

D50 = np.array([96.42, 100.0, 82.49])           # ICC PCS white, Y = 100
BRADFORD = np.array([[0.8951, 0.2664, -0.1614],
                     [-0.7502, 1.7135, 0.0367],
                     [0.0389, -0.0685, 1.0296]])
LAM_1NM = np.arange(360.0, 830.0 + 1e-9, 1.0)


@lru_cache(maxsize=None)
def _tables() -> dict:
    return json.loads((Path(__file__).parent / "data" / "cie_tables.json")
                      .read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def weights(illuminant: str = "D50") -> np.ndarray:
    """(3, 471) 1 nm weights S*xbar etc., normalised so a perfect white has Y=100."""
    t = _tables()
    il = t["illuminants"][illuminant]
    src = np.linspace(il["lo"], il["hi"], len(il["vals"]))
    spd = np.interp(LAM_1NM, src, il["vals"])
    ob = t["observers"]["1931_2"]
    cmf = np.stack([ob["x"], ob["y"], ob["z"]])          # already 360..830 @1nm
    w = spd[None, :] * cmf
    return w * (100.0 / w[1].sum())


def xyz_from_reflectance_1nm(refl_1nm: np.ndarray, illuminant: str = "D50"
                             ) -> np.ndarray:
    """(N, 471) reflectance on LAM_1NM -> (N, 3) XYZ (Y=100 scale)."""
    return np.atleast_2d(refl_1nm) @ weights(illuminant).T


def white_of(illuminant: str) -> np.ndarray:
    return weights(illuminant).sum(1)


def bradford(xyz: np.ndarray, src_white: np.ndarray,
             dst_white: np.ndarray = D50) -> np.ndarray:
    cone = BRADFORD @ (np.atleast_2d(xyz).T)
    scale = (BRADFORD @ dst_white) / (BRADFORD @ np.asarray(src_white, float))
    return (np.linalg.inv(BRADFORD) @ (cone * scale[:, None])).T


def xyz_to_lab(xyz: np.ndarray, white: np.ndarray = D50) -> np.ndarray:
    r = np.atleast_2d(xyz) / white[None, :]
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0
    f = np.where(r > e, np.cbrt(np.maximum(r, 0.0)), (k * r + 16.0) / 116.0)
    return np.stack([116.0 * f[:, 1] - 16.0, 500.0 * (f[:, 0] - f[:, 1]),
                     200.0 * (f[:, 1] - f[:, 2])], 1)


def lab_to_xyz(lab: np.ndarray, white: np.ndarray = D50) -> np.ndarray:
    lab = np.atleast_2d(lab)
    fy = (lab[:, 0] + 16.0) / 116.0
    fx = fy + lab[:, 1] / 500.0
    fz = fy - lab[:, 2] / 200.0
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0

    def inv(f):
        f3 = f ** 3
        return np.where(f3 > e, f3, (116.0 * f - 16.0) / k)
    y = np.where(lab[:, 0] > k * e, fy ** 3, lab[:, 0] / k)
    return np.stack([inv(fx), y, inv(fz)], 1) * white[None, :]


def media_relative_lab(xyz: np.ndarray, media_white_xyz: np.ndarray) -> np.ndarray:
    """What an ICC relative-colorimetric table stores: media white -> D50 (Bradford)."""
    return xyz_to_lab(bradford(xyz, media_white_xyz, D50))


def de2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """CIEDE2000 (Sharma et al. 2005), vectorised."""
    lab1, lab2 = np.atleast_2d(lab1), np.atleast_2d(lab2)
    L1, a1, b1 = lab1.T
    L2, a2, b2 = lab2.T
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cb = (C1 + C2) / 2.0
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(C1p * C2p == 0, 0.0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2)
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    hsum = h1p + h2p
    hbp = np.where(np.abs(h1p - h2p) > 180,
                   np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2),
                   hsum / 2)
    hbp = np.where(C1p * C2p == 0, hsum, hbp)
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    dtheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                   + Rt * (dCp / Sc) * (dHp / Sh))


# --- ITP (ITU-R BT.2124) ---------------------------------------------------
_XYZ_TO_LMS = np.array([[0.3592, 0.6976, -0.0358],
                        [-0.1922, 1.1004, 0.0755],
                        [0.0070, 0.0749, 0.8434]])
_LMS_TO_ICTCP = np.array([[2048, 2048, 0], [6610, -13613, 7003],
                          [17933, -17390, -543]]) / 4096.0
D65 = np.array([95.047, 100.0, 108.883])


def _pq(y: np.ndarray) -> np.ndarray:
    m1, m2 = 2610 / 16384, 2523 / 4096 * 128
    c1, c2, c3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
    yp = np.clip(y / 10000.0, 0, None) ** m1
    return ((c1 + c2 * yp) / (1 + c3 * yp)) ** m2


def de_itp(lab1: np.ndarray, lab2: np.ndarray, white_nits: float = 100.0
           ) -> np.ndarray:
    """ITP Delta E (BT.2124) for relative Lab (D50) at a 100 cd/m2 white.
    Lab -> XYZ(D50) -> Bradford to D65 -> LMS -> PQ -> ICtCp; dE = 720 sqrt(dI^2 + (dT/2)^2... )."""
    def ictcp(lab):
        xyz = bradford(lab_to_xyz(lab), D50, D65) / 100.0 * white_nits
        lms = xyz @ _XYZ_TO_LMS.T
        return _pq(lms) @ _LMS_TO_ICTCP.T
    a, b = ictcp(lab1), ictcp(lab2)
    d = a - b
    return 720.0 * np.sqrt(d[:, 0] ** 2 + (0.5 * d[:, 1]) ** 2 + d[:, 2] ** 2)
