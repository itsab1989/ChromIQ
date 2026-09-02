"""Perceptual / saturation gamut mapping for the profile engine (P4, #122).

Builds distinct B2A0 (perceptual) and B2A2 (saturation) tables when a source
gamut is given — the engine's counterpart of colprof's ``-S``.

The v1 mapping is the measured closed-form family from the issue-#122
prototypes (validated against colprof's realized perceptual behaviour on the
trusted ET-8550 profile):

* neutral-axis luminance-range compression ``L' = L + L_bk·(1 − L/100)^1.38``
  (exponent fitted to the measured colprof curve; black gains density, the
  highlights stay put);
* per-hue-sector radial compression toward a focal point on the neutral
  axis blended toward the destination cusp: colours inside the knee are
  untouched, out-of-gamut colours land just inside the surface (smooth tanh
  knee — no hard clip);
* saturation intent = the same map with a shorter protected core and a mild
  chroma push (colprof's saturation table is likewise a boosted perceptual).

Honesty note (in the issue, agreed with Basti): this family measures ≈4.5 ΔE
median against colprof's own mapping — inside the band professional tools
disagree with each other (5.2 median, measured), but not colprof-exact. The
engine therefore ships these intents as *approximate*; the colorimetric
tables remain authoritative. Full gammap-style guide-vector parity is the
documented P4 follow-up.

Source gamuts are computed live from whatever profile is given — like
colprof, the engine doesn't care which source you throw at it. ClayRGB /
Adobe RGB and sRGB take an exact analytic fast path; every other RGB or
CMYK profile (ProPhoto, Display P3, a printer profile, v2 or v4) is sampled
through littleCMS. ICC v4 works here even though the Argyll tools can't
read it.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from workflow.profile_engine import b2a as b2a_mod
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.forward_model import ForwardModel
from workflow.profile_engine.ti3_data import Ti3Measurement, xyz_to_lab
from core.proc_text import run_text

# Bradford D65→D50 adaptation (both analytic sources are D65-white).
_MB = np.array([[0.8951, 0.2664, -0.1614],
                [-0.7502, 1.7135, 0.0367],
                [0.0389, -0.0685, 1.0296]])
_D65 = np.array([0.95047, 1.0, 1.08883])
_D50 = np.array([0.9642, 1.0, 0.8249])
_AD = np.linalg.inv(_MB) @ np.diag((_MB @ _D50) / (_MB @ _D65)) @ _MB

# Published primaries; gamma per spec (sRGB piecewise, Adobe 563/256).
_PRIMARIES = {
    "adobe": (np.array([[0.64, 0.33], [0.21, 0.71], [0.15, 0.06]]), "adobe"),
    "srgb": (np.array([[0.64, 0.33], [0.30, 0.60], [0.15, 0.06]]), "srgb"),
}

NH, NP = 48, 24          # hue × elevation bins for the radial tables


class GamutSourceError(ValueError):
    """The gamut-source profile could not be read (user-facing message)."""


def source_kind(path: Path | str) -> str | None:
    """Analytic fast path for the two sources ChromIQ recommends (#121).

    Exact primaries, no quantisation, no profile I/O. Anything else returns
    ``None`` and is sampled live from the actual profile — the engine, like
    colprof, doesn't care which source you throw at it.
    """
    name = Path(path).stem.lower()
    if "clay" in name or "adobe" in name:
        return "adobe"
    if "srgb" in name:
        return "srgb"
    return None


def source_surface_from_profile(path: Path | str, mesh: int = 33,
                                intent: int = 1) -> np.ndarray:
    """Source-gamut boundary cloud in Lab, computed live from any ICC.

    The device-cube boundary is mapped through the profile with littleCMS
    (PIL ``ImageCms``) — which, unlike the Argyll tools, also reads ICC v4
    (Display P3, i1Profiler output, …). RGB and CMYK sources are supported.
    The 8-bit LAB transform quantises to ≈0.5 ΔE — irrelevant for a gamut
    surface that only feeds binned radial maxima.
    """
    kind = source_kind(path)
    if kind is not None:
        return source_surface_lab(kind, mesh)
    p = Path(path)
    if not p.is_file():
        raise GamutSourceError(
            f"Gamut source profile not found: {p}")
    try:
        from PIL import Image, ImageCms
        prof = ImageCms.getOpenProfile(str(p))
        space = (prof.profile.xcolor_space or "").strip()
    except Exception as exc:
        raise GamutSourceError(
            f"'{p.name}' could not be read as an ICC profile "
            f"({exc}).") from exc
    if space not in ("RGB", "CMYK"):
        raise GamutSourceError(
            f"'{p.name}' is a {space or 'non-device'} profile — gamut "
            "sources must be RGB or CMYK.")
    n = 3 if space == "RGB" else 4
    if n == 3:
        u = np.linspace(0.0, 1.0, mesh)
        faces = []
        for ax in range(3):
            for val in (0.0, 1.0):
                g = np.zeros((mesh, mesh, 3))
                a, b = [i for i in range(3) if i != ax]
                g[:, :, ax] = val
                g[:, :, a] = u[:, None]
                g[:, :, b] = u[None, :]
                faces.append(g.reshape(-1, 3))
        dev = np.vstack(faces)
    else:
        rng = np.random.default_rng(17)
        m = 12000
        dev = rng.uniform(0.0, 1.0, (m, 4))
        dev[np.arange(m), rng.integers(0, 4, m)] = \
            rng.integers(0, 2, m).astype(float)
    try:
        lab_prof = ImageCms.createProfile("LAB")
        # intent: 0 perceptual / 1 rel col / 2 saturation — colprof samples
        # the source through the matching intent per table (-nP/-nS switch
        # to colorimetric); matrix-only profiles are intent-invariant.
        tf = ImageCms.buildTransform(prof, lab_prof, space, "LAB",
                                     renderingIntent=intent)
        dev8 = np.clip(dev * 255.0, 0, 255).round().astype(np.uint8)
        img = Image.merge(space, [
            Image.fromarray(dev8[:, c].reshape(-1, 1), "L")
            for c in range(n)])
        out = ImageCms.applyTransform(img, tf)
        chans = [np.asarray(ch, dtype=float).reshape(-1)
                 for ch in out.split()]
    except Exception as exc:
        raise GamutSourceError(
            f"'{p.name}' could not be sampled as a gamut source "
            f"({exc}).") from exc
    return np.stack([chans[0] * 100.0 / 255.0,
                     chans[1] - 128.0,
                     chans[2] - 128.0], 1)


def _rgb_to_xyz_matrix(xy: np.ndarray) -> np.ndarray:
    w = np.array([0.3127, 0.3290])
    xr = np.stack([xy[:, 0] / xy[:, 1], np.ones(3),
                   (1 - xy[:, 0] - xy[:, 1]) / xy[:, 1]], 0)
    s = np.linalg.solve(xr, np.array([w[0] / w[1], 1.0,
                                      (1 - w[0] - w[1]) / w[1]]))
    return xr * s[None, :]


def source_surface_lab(kind: str, mesh: int = 33) -> np.ndarray:
    """Source-gamut boundary cloud in Lab(D50) — analytic primaries."""
    xy, gamma = _PRIMARIES[kind]
    m = _rgb_to_xyz_matrix(xy)
    u = np.linspace(0.0, 1.0, mesh)
    faces = []
    for ax in range(3):
        for val in (0.0, 1.0):
            g = np.zeros((mesh, mesh, 3))
            a, b = [i for i in range(3) if i != ax]
            g[:, :, ax] = val
            g[:, :, a] = u[:, None]
            g[:, :, b] = u[None, :]
            faces.append(g.reshape(-1, 3))
    rgb = np.vstack(faces)
    if gamma == "srgb":
        lin = np.where(rgb <= 0.04045, rgb / 12.92,
                       ((rgb + 0.055) / 1.055) ** 2.4)
    else:
        lin = rgb ** (563.0 / 256.0)
    xyz = (_AD @ (m @ lin.T)).T * 100.0
    return xyz_to_lab(xyz)


def destination_surface_lab(model: ForwardModel, mesh: int = 33,
                            ink_limit: float | None = None,
                            is_additive: bool = True,
                            dense: bool = False) -> np.ndarray:
    """Destination boundary cloud: the mapped device-cube boundary (the
    verified surface construction; for n > 3 the boundary image is a superset
    seed — segmented maxima below pick the true outer shell).

    ``dense`` (maximum-accuracy mode): a 20k sample of an n ≥ 5 cube
    boundary is thin — under-sampled shell bins underestimate the radius
    and the mapping then over-compresses, throwing away chroma the printer
    can deliver. ``model.predict`` is vectorised, so a 10× denser cloud
    costs almost nothing.
    """
    n = model.n_channels
    rng = np.random.default_rng(11)
    if n <= 3:
        u = np.linspace(0.0, 1.0, mesh)
        faces = []
        for ax in range(n):
            for val in (0.0, 1.0):
                g = np.zeros((mesh, mesh, n))
                a, b = [i for i in range(n) if i != ax][:2]
                g[:, :, ax] = val
                g[:, :, a] = u[:, None]
                g[:, :, b] = u[None, :]
                faces.append(g.reshape(-1, n))
        dev = np.vstack(faces)
    else:
        # High-dimensional cube boundary: dense random face samples.
        m = 200_000 if dense else 20000
        dev = rng.uniform(0.0, 1.0, (m, n))
        dev[np.arange(m), rng.integers(0, n, m)] = \
            rng.integers(0, 2, m).astype(float)
    if ink_limit is not None and not is_additive:
        total = dev.sum(1)
        over = total > ink_limit / 100.0
        dev[over] *= (ink_limit / 100.0 / total[over])[:, None]
    return model.predict(dev)


def _radial_tables(cloud: np.ndarray, cusp_l: np.ndarray
                   ) -> np.ndarray:
    """(NH, NP) max radius per hue sector / elevation from the focal point."""
    tab = np.zeros((NH, NP))
    h = np.degrees(np.arctan2(cloud[:, 2], cloud[:, 1])) % 360.0
    chroma = np.hypot(cloud[:, 1], cloud[:, 2])
    for hb in range(NH):
        centre = (hb + 0.5) * 360.0 / NH
        m = np.abs(((h - centre + 180.0) % 360.0) - 180.0) <= 360.0 / NH * 1.5
        if not m.any():
            continue
        pl = cloud[m]
        dl = pl[:, 0] - cusp_l[hb]
        phi = np.arctan2(chroma[m], dl)
        r = np.hypot(chroma[m], dl)
        pb = np.clip((phi / np.pi * NP).astype(int), 0, NP - 1)
        np.maximum.at(tab[hb], pb, r)
    # fill empty bins from neighbours, then smooth over hue (window 3)
    for hb in range(NH):
        for pb in range(NP):
            if tab[hb, pb] == 0:
                nb = [tab[hb, q] for q in (pb - 1, pb + 1)
                      if 0 <= q < NP and tab[hb, q] > 0]
                tab[hb, pb] = max(nb) if nb else tab[hb].max()
    tab[:] = (tab + np.roll(tab, 1, 0) + np.roll(tab, -1, 0)) / 3.0
    return tab


class GamutMapper:
    """Closed-form Lab→Lab mapping from a source to a destination gamut."""

    def __init__(self, src_cloud: np.ndarray, dst_cloud: np.ndarray, *,
                 knee: float = 0.62, sharp: float = 1.5,
                 l_exp: float = 1.38, cusp_blend: float = 0.7,
                 chroma_boost: float = 1.0,
                 neutral_table: dict | None = None):
        self.knee = knee
        self.sharp = sharp
        self.l_exp = l_exp
        self.cusp_blend = cusp_blend
        self.chroma_boost = chroma_boost
        # Optional colprof-anchored neutral rendering (fit_multiink_anchor):
        # replaces the analytic tone curve and adds colprof's near-black cast.
        self.neutral_table = neutral_table
        h = np.degrees(np.arctan2(dst_cloud[:, 2], dst_cloud[:, 1])) % 360.0
        chroma = np.hypot(dst_cloud[:, 1], dst_cloud[:, 2])
        self.cusp_l = np.full(NH, 50.0)
        for hb in range(NH):
            centre = (hb + 0.5) * 360.0 / NH
            m = np.abs(((h - centre + 180.0) % 360.0) - 180.0) <= 360.0 / NH
            if m.any():
                self.cusp_l[hb] = dst_cloud[m][chroma[m].argmax(), 0]
        neut = chroma < 8.0
        self.l_black = float(dst_cloud[neut][:, 0].min()) if neut.any() else 5.0
        self.l_white = float(dst_cloud[neut][:, 0].max()) if neut.any() else 100.0
        self.tab_dst = _radial_tables(dst_cloud, self.cusp_l)
        self.tab_src = np.maximum(_radial_tables(src_cloud, self.cusp_l),
                                  self.tab_dst)

    def map_lab(self, lab: np.ndarray) -> np.ndarray:
        """(N,3) Lab → mapped Lab (vectorised)."""
        L = lab[:, 0]
        a = lab[:, 1]
        b = lab[:, 2]
        if self.neutral_table is not None:
            # colprof's measured tone reproduction (CMYK proxy oracle).
            nt = self.neutral_table
            l1 = np.interp(L, nt["l_axis"], nt["neutral_lab"][:, 0])
        else:
            # luminance-range compression (measured colprof family)
            l1 = L + self.l_black \
                * np.clip(1.0 - L / 100.0, 0.0, 1.0) ** self.l_exp
            l1 = np.minimum(l1, 100.0)
        chroma = np.hypot(a, b) * self.chroma_boost
        h = np.degrees(np.arctan2(b, a)) % 360.0
        hb = np.clip((h / 360.0 * NH).astype(int), 0, NH - 1)
        # focal point: neutral axis at a blend of own L and the cusp L
        focal = (self.cusp_blend * self.cusp_l[hb]
                 + (1.0 - self.cusp_blend) * np.clip(l1, self.l_black, 100.0))
        dl = l1 - focal
        phi = np.arctan2(chroma, dl)
        r = np.hypot(chroma, dl)
        pb = np.clip((phi / np.pi * NP).astype(int), 0, NP - 1)
        rb_dst = self.tab_dst[hb, pb]
        rb_src = np.maximum(self.tab_src[hb, pb], rb_dst)
        t = np.divide(r, rb_dst, out=np.zeros_like(r), where=rb_dst > 0)
        smax = np.divide(rb_src, rb_dst, out=np.ones_like(rb_dst),
                         where=rb_dst > 0)
        # smooth tanh knee: identity below the knee, compress above
        uu = (t - self.knee) / np.maximum(smax - self.knee, 1e-6)
        t2 = np.where(
            t <= self.knee, t,
            self.knee + (1.0 - self.knee)
            * np.tanh(np.clip(uu, 0.0, None) * self.sharp)
            / np.tanh(self.sharp))
        r2 = t2 * rb_dst
        out = np.empty_like(lab)
        out[:, 0] = focal + r2 * np.cos(phi)
        cn = r2 * np.sin(phi)
        out[:, 1] = cn * np.cos(np.radians(h))
        out[:, 2] = cn * np.sin(np.radians(h))
        neutral = chroma < 1e-6
        out[neutral, 0] = l1[neutral]
        out[neutral, 1:] = lab[neutral, 1:] * 1.0
        if self.neutral_table is not None:
            # colprof's near-neutral colour cast, fading out by chroma 20.
            nt = self.neutral_table
            w = np.clip(1.0 - chroma / 20.0, 0.0, 1.0)
            out[:, 1] += w * np.interp(L, nt["l_axis"],
                                       nt["neutral_lab"][:, 1])
            out[:, 2] += w * np.interp(L, nt["l_axis"],
                                       nt["neutral_lab"][:, 2])
        return out


# colprof -t/-T gamut-mapping intent presets. The colorimetric-family codes
# (r, rl, a, aw, al) are exact by construction — a colorimetric "mapping" is
# the identity, so those tables alias the colorimetric B2A (verified in
# colprof output: its default A2B0/A2B1/A2B2 are byte-identical the same
# way). The perceptual/saturation-family codes tune the measured mapping
# family; the appearance codes (pa, aa) run the mapping in CIECAM02 Jab.
_INTENT_PRESETS: dict[str, dict] = {
    "": {},                                       # default perceptual
    "p": {},
    "lp": {"cusp_blend": 0.3},                    # luminance-preserving
    "ms": {"knee": 0.50, "chroma_boost": 1.03},   # moderate saturation
    "s": {"knee": 0.45, "chroma_boost": 1.06},    # enhanced saturation
    "pa": {"jab": True},                          # perceptual appearance
    "aa": {"jab": True, "absolute": True},        # absolute appearance
}
_COLORIMETRIC_INTENTS = {"r", "rl", "a", "aw", "al"}
_SAT_DEFAULT = {"knee": 0.45, "chroma_boost": 1.06}


def _mapper_for(intent: str, default_kw: dict, src: np.ndarray,
                dst: np.ndarray, settings) -> "GamutMapper | None":
    """A mapper for a -t/-T intent code; None = alias the colorimetric B2A."""
    if intent in _COLORIMETRIC_INTENTS:
        return None
    kw = dict(_INTENT_PRESETS.get(intent, default_kw or {}))
    if not kw and default_kw:
        kw = dict(default_kw)
    jab = kw.pop("jab", False)
    kw.pop("absolute", False)
    if settings is not None and (settings.src_viewing or settings.dst_viewing):
        jab = True
    if jab:
        from workflow.profile_engine.cam02 import DEFAULT_VC, VIEWING_PRESETS
        vc_s = VIEWING_PRESETS.get(getattr(settings, "src_viewing", ""),
                                   DEFAULT_VC)
        vc_d = VIEWING_PRESETS.get(getattr(settings, "dst_viewing", ""),
                                   DEFAULT_VC)
        return JabGamutMapper(src, dst, vc_s, vc_d, **kw)
    return GamutMapper(src, dst, **kw)


class JabGamutMapper:
    """The same radial mapping run in CIECAM02 Jab under viewing conditions.

    Source colours are taken to appearance space under the *source* viewing
    conditions, mapped between the Jab gamut surfaces, and brought back
    under the *destination* conditions — the appearance-match construction
    colprof's CAM-based mapping uses. The CAM code is round-trip gated at
    construction (inverse must reproduce XYZ to < 1e-4).
    """

    def __init__(self, src_lab: np.ndarray, dst_lab: np.ndarray,
                 vc_src, vc_dst, **mapper_kw) -> None:
        from workflow.profile_engine.cam02 import Cam02
        from workflow.profile_engine.ti3_data import lab_to_xyz
        self._cam_s = Cam02(vc_src)
        self._cam_d = Cam02(vc_dst)
        probe = np.array([[50.0, 20.0, -30.0], [80.0, 0.0, 0.0],
                          [20.0, 40.0, 30.0]])
        err = self._cam_d.roundtrip_error(lab_to_xyz(probe))
        if err > 1e-4:
            raise RuntimeError(f"CAM02 inverse round-trip failed ({err})")
        src_jab = self._cam_s.xyz_to_jab(lab_to_xyz(src_lab))
        dst_jab = self._cam_d.xyz_to_jab(lab_to_xyz(dst_lab))
        self._inner = GamutMapper(src_jab, dst_jab, **mapper_kw)

    def map_lab(self, lab: np.ndarray) -> np.ndarray:
        from workflow.profile_engine.ti3_data import lab_to_xyz, xyz_to_lab
        jab = self._cam_s.xyz_to_jab(lab_to_xyz(lab))
        mapped = self._inner.map_lab(jab)
        return xyz_to_lab(np.clip(self._cam_d.jab_to_xyz(mapped),
                                  0.0, None))


class WarpMapper:
    """A smooth displacement-field map fitted to sampled (Lab → Lab) pairs.

    The proven parity architecture (issue #122, iteration 4): a 13³ grid of
    Lab displacements, least-squares fitted with the maths-A machinery,
    reproduces colprof's own perceptual mapping to held-out median 0.23 ΔE —
    *below* colprof's build-to-build noise (0.50).
    """

    def __init__(self, train_lab: np.ndarray, target_lab: np.ndarray,
                 grid: int = 13, lam: float = 0.005,
                 row_weights: np.ndarray | None = None) -> None:
        from workflow.profile_engine.forward_model import (_grid_solve,
                                                           _interp_weights)
        self._grid = grid
        lo = train_lab.min(0) - 1.0
        hi = train_lab.max(0) + 1.0
        self._lo, self._hi = lo, hi
        w, cols = _interp_weights(self._to01(train_lab), grid, 3)
        y = target_lab - train_lab
        if row_weights is not None:
            sw = np.sqrt(np.asarray(row_weights, float))[:, None]
            w = w * sw
            y = y * sw
        self._nodes = _grid_solve(w, cols, y, grid, 3, lam, 1200)

    def _to01(self, lab: np.ndarray) -> np.ndarray:
        return np.clip((lab - self._lo[None, :])
                       / (self._hi - self._lo)[None, :], 0.0, 1.0)

    def map_lab(self, lab: np.ndarray) -> np.ndarray:
        from workflow.profile_engine.forward_model import _interp_weights
        w, cols = _interp_weights(self._to01(lab), self._grid, 3)
        return lab + (w[:, :, None] * self._nodes[cols]).sum(1)


class OracleUnavailable(RuntimeError):
    """colprof can't provide the mapping oracle for this build."""


def _k_args(settings) -> list[str]:
    """colprof -k/-K arguments matching the build's black-generation rule,
    so oracle and proxy runs separate exactly like the requested build."""
    rule = getattr(settings, "k_rule", "")
    if not rule:
        return []
    args = [("-K" if getattr(settings, "k_locus", False) else "-k") + rule]
    if rule == "p":
        params = getattr(settings, "k_curve_params", None) or             (0.0, 0.1, 0.9, 1.0, 1.0)
        args += [f"{v:g}" for v in params]
    return args


# In-process cache for the colprof oracle: a full colprof build per engine
# build is the dominant cost of the ≤4-channel saturation table, and the
# iterate-on-settings workflow rebuilds the same measurement repeatedly.
# Keyed on the measurement file identity + every setting that reaches the
# oracle run; holds the fitted mappers (plain numpy state, no temp files).
_ORACLE_CACHE: dict[tuple, dict] = {}
_ORACLE_CACHE_MAX = 4


def _oracle_cache_key(meas: Ti3Measurement, source_gamut, settings,
                      node_lab: np.ndarray | None) -> tuple | None:
    try:
        st = Path(meas.path).stat()
    except OSError:
        return None
    node_key = None if node_lab is None else (
        node_lab.shape[0], round(float(node_lab.sum()), 3))
    return (str(meas.path), st.st_mtime_ns, st.st_size, str(source_gamut),
            getattr(settings, "quality", ""),
            getattr(settings, "perc_intent", ""),
            getattr(settings, "sat_intent", ""),
            getattr(settings, "src_viewing", ""),
            getattr(settings, "dst_viewing", ""),
            getattr(settings, "perc_src_colorimetric", False),
            getattr(settings, "sat_src_colorimetric", False),
            getattr(settings, "illuminant", ""),
            getattr(settings, "observer", ""),
            getattr(settings, "fwa", False),
            getattr(settings, "fwa_illum", ""),
            getattr(settings, "k_rule", ""),
            getattr(settings, "k_locus", False),
            getattr(settings, "k_curve_params", None),
            node_key)


def fit_colprof_mappers(meas: Ti3Measurement, source_gamut: Path | str,
                        settings, argyll_bin: Path | str | None,
                        progress=None,
                        node_lab: np.ndarray | None = None) -> dict:
    """Colprof-matched perceptual/saturation mappers (arm's-length oracle).

    Runs Argyll colprof as a subprocess on the same measurement with the
    same gamut/intent/viewing flags, samples the *realized* perceptual and
    saturation mappings of the resulting profile at ~1600 real source
    colours, and fits :class:`WarpMapper` to each. The engine's rendering
    then matches colprof's within colprof's own build-to-build variation —
    using only program output, the same arm's-length relationship ChromIQ
    has always had with the Argyll tools.

    Raises :class:`OracleUnavailable` when colprof can't build this
    measurement (multi-ink data, missing binaries) — callers fall back to
    the engine's own closed-form mapping family.
    """
    import shutil
    import subprocess
    import tempfile

    bin_dir = Path(argyll_bin) if argyll_bin else Path(
        "/Applications/Argyll/bin")
    colprof = bin_dir / "colprof"
    xicclu = bin_dir / "xicclu"
    if not colprof.exists() or not xicclu.exists():
        raise OracleUnavailable("Argyll binaries not found")
    if meas.device_rep not in ("RGB", "CMY", "CMYK"):
        raise OracleUnavailable(
            f"colprof can't build {meas.device_rep} measurements")

    cache_key = _oracle_cache_key(meas, source_gamut, settings, node_lab)
    if cache_key is not None and cache_key in _ORACLE_CACHE:
        if progress:
            progress("Saturation table: reusing the colprof rendering "
                     "matched earlier in this session.")
        return _ORACLE_CACHE[cache_key]

    if progress:
        progress("Saturation table: matching colprof's rendering "
                     "(this runs Argyll colprof once in the background)…")
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "oracle"
        shutil.copy(meas.path, base.with_suffix(".ti3"))
        q = settings.quality if settings.quality in ("l", "m", "h") else "h"
        args = [str(colprof), f"-q{q}"]
        # Same source/intent/viewing surface the engine build was asked for.
        flag = "-s" if (getattr(settings, "perc_src_colorimetric", False)
                        and getattr(settings, "sat_src_colorimetric", False)
                        ) else "-S"
        args += [flag, str(source_gamut)]
        if getattr(settings, "perc_intent", ""):
            args.append(f"-t{settings.perc_intent}")
        if getattr(settings, "sat_intent", ""):
            args.append(f"-T{settings.sat_intent}")
        if getattr(settings, "src_viewing", ""):
            args.append(f"-c{settings.src_viewing}")
        if getattr(settings, "dst_viewing", ""):
            args.append(f"-d{settings.dst_viewing}")
        if getattr(settings, "perc_src_colorimetric", False):
            args.append("-nP")
        if getattr(settings, "sat_src_colorimetric", False):
            args.append("-nS")
        if getattr(settings, "illuminant", ""):
            args += ["-i", settings.illuminant]
        if getattr(settings, "observer", ""):
            args += ["-o", settings.observer]
        if getattr(settings, "fwa", False):
            args.append(f"-f{settings.fwa_illum}" if settings.fwa_illum
                        else "-f")
        args += _k_args(settings)
        r = run_text(args + [str(base)], capture_output=True)
        icc = base.with_suffix(".icc")
        if r.returncode != 0 or not icc.exists():
            raise OracleUnavailable(
                f"colprof oracle failed: {(r.stderr or r.stdout)[:200]}")

        # Real source colours: random source-device values through the
        # source profile (never random Lab — impossible colours), plus a
        # neutral ramp so the tone curve is nailed down.
        rng = np.random.default_rng(7)
        src_cloud = source_surface_from_profile(source_gamut, mesh=9)
        interior = _source_interior_lab(source_gamut, rng, 1400)
        neutral = np.stack([np.linspace(0.0, 100.0, 64),
                            np.zeros(64), np.zeros(64)], 1)
        train = np.vstack([interior, src_cloud, neutral])

        def realized(intent: str) -> np.ndarray:
            inp = "\n".join(f"{a:.4f} {b:.4f} {c:.4f}" for a, b, c in train)
            r1 = run_text([str(xicclu), "-fb", f"-i{intent}", "-pl",
                           str(icc)], input=inp, capture_output=True)
            dev = [" ".join(ln.rsplit("->", 1)[1].split()[:meas.n_channels])
                   for ln in r1.stdout.splitlines() if "->" in ln]
            r2 = run_text([str(xicclu), "-ff", "-ir", "-pl", str(icc)],
                          input="\n".join(dev), capture_output=True)
            out = np.array([[float(v) for v in
                             ln.rsplit("->", 1)[1].split()[:3]]
                            for ln in r2.stdout.splitlines() if "->" in ln])
            if len(out) != len(train):
                raise OracleUnavailable("oracle sampling failed")
            return out

        if progress:
            progress("Saturation table: fitting the matched rendering…")
        out = {"B2A0": WarpMapper(train, realized("p")),
               "B2A2": WarpMapper(train, realized("s"))}
        # Exact node targets: sample colprof's realized mapping AT the CLUT
        # nodes the profile will carry — the tables then reproduce colprof's
        # values up to quantisation, and the warp only serves smooth
        # inversion (-nI) and off-node queries.
        if node_lab is not None:
            for tag, intent in (("B2A0", "p"), ("B2A2", "s")):
                out[tag] = _ExactNodeMapper(node_lab, _realized_at(
                    xicclu, icc, node_lab, intent, meas.n_channels),
                    out[tag])
        if cache_key is not None:
            while len(_ORACLE_CACHE) >= _ORACLE_CACHE_MAX:
                _ORACLE_CACHE.pop(next(iter(_ORACLE_CACHE)))
            _ORACLE_CACHE[cache_key] = out
        return out


def _realized_at(xicclu: Path, icc: Path, lab: np.ndarray, intent: str,
                 n_channels: int) -> np.ndarray:
    import subprocess
    inp = "\n".join(f"{a:.4f} {b:.4f} {c:.4f}" for a, b, c in lab)
    r1 = run_text([str(xicclu), "-fb", f"-i{intent}", "-pl", str(icc)],
                  input=inp, capture_output=True)
    dev = [" ".join(ln.rsplit("->", 1)[1].split()[:n_channels])
           for ln in r1.stdout.splitlines() if "->" in ln]
    r2 = run_text([str(xicclu), "-ff", "-ir", "-pl", str(icc)],
                  input="\n".join(dev), capture_output=True)
    out = np.array([[float(v) for v in ln.rsplit("->", 1)[1].split()[:3]]
                    for ln in r2.stdout.splitlines() if "->" in ln])
    if len(out) != len(lab):
        raise OracleUnavailable("node sampling failed")
    return out


class _ExactNodeMapper:
    """colprof's realized mapping sampled exactly at the CLUT nodes; the
    fitted warp answers everything off-node (the -nI inverse, probes)."""

    def __init__(self, node_lab: np.ndarray, node_mapped: np.ndarray,
                 warp: WarpMapper) -> None:
        self._node_lab = node_lab
        self._node_mapped = node_mapped
        self._warp = warp

    def map_lab(self, lab: np.ndarray) -> np.ndarray:
        if lab is self._node_lab or (
                lab.shape == self._node_lab.shape
                and np.array_equal(lab, self._node_lab)):
            return self._node_mapped
        return self._warp.map_lab(lab)


def _source_interior_lab(source_gamut: Path | str, rng, n: int) -> np.ndarray:
    """Random interior colours of the source space, in Lab."""
    kind = source_kind(source_gamut)
    dev = rng.uniform(0.0, 1.0, (n, 3))
    if kind is not None:
        xy, gamma = _PRIMARIES[kind]
        m = _rgb_to_xyz_matrix(xy)
        if gamma == "srgb":
            lin = np.where(dev <= 0.04045, dev / 12.92,
                           ((dev + 0.055) / 1.055) ** 2.4)
        else:
            lin = dev ** (563.0 / 256.0)
        return xyz_to_lab((_AD @ (m @ lin.T)).T * 100.0)
    from PIL import Image, ImageCms
    prof = ImageCms.getOpenProfile(str(source_gamut))
    space = (prof.profile.xcolor_space or "RGB").strip()
    nch = 4 if space == "CMYK" else 3
    dev = rng.uniform(0.0, 1.0, (n, nch))
    lab_prof = ImageCms.createProfile("LAB")
    tf = ImageCms.buildTransform(prof, lab_prof, space, "LAB",
                                 renderingIntent=1)
    dev8 = np.clip(dev * 255.0, 0, 255).round().astype(np.uint8)
    img = Image.merge(space, [Image.fromarray(dev8[:, c].reshape(-1, 1), "L")
                              for c in range(nch)])
    chans = [np.asarray(ch, dtype=float).reshape(-1)
             for ch in ImageCms.applyTransform(img, tf).split()]
    return np.stack([chans[0] * 100.0 / 255.0, chans[1] - 128.0,
                     chans[2] - 128.0], 1)


def fit_multiink_anchor(model: ForwardModel, meas: Ti3Measurement,
                        source_gamut: Path | str, settings,
                        argyll_bin: Path | str | None,
                        progress=None) -> dict:
    """Anchor a +N mapping in colprof's behaviour via a CMYK proxy oracle.

    colprof cannot build multi-ink profiles, so there is no direct
    reference — but the engine's fitted model can synthesise the printer's
    CMYK-only behaviour (extra inks at zero), which colprof *can* build.
    From that proxy we take exactly what transfers:

    * the **neutral rendering** — colprof's tone-curve compression including
      its deliberate near-black colour cast (where the closed-form family
      deviated most, ~3 ΔE); returned as a sampled L→Lab table;
    * the **K-separation behaviour** — colprof's black usage along the
      neutral axis, to which the engine's K-locus prior is refitted.

    The chroma compression against the *extra-ink* gamut shell stays the
    engine's own — that part of the gamut colprof has never seen.
    """
    import shutil
    import subprocess
    import tempfile

    bin_dir = Path(argyll_bin) if argyll_bin else Path(
        "/Applications/Argyll/bin")
    colprof = bin_dir / "colprof"
    xicclu = bin_dir / "xicclu"
    if not colprof.exists() or not xicclu.exists():
        raise OracleUnavailable("Argyll binaries not found")
    if model.n_channels < 5:
        raise OracleUnavailable("proxy anchor is for multi-ink models")

    if progress:
        progress("Anchoring the rendering in colprof's behaviour "
                 "(CMYK proxy build)…")
    # Synthetic CMYK measurement from the fitted model, extras at zero.
    g = np.linspace(0.0, 1.0, 5)
    cmyk = np.stack(np.meshgrid(g, g, g, g, indexing="ij"), -1).reshape(-1, 4)
    dev = np.zeros((len(cmyk), model.n_channels))
    dev[:, :4] = cmyk
    limit = meas.ink_limit
    if limit is not None:
        total = dev.sum(1)
        over = total > limit / 100.0
        dev[over] *= (limit / 100.0 / total[over])[:, None]
    lab = model.predict(dev)
    from workflow.profile_engine.ti3_data import lab_to_xyz
    xyz = lab_to_xyz(lab)
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "proxy"
        lines = ["CTI3", "", 'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "CMYK_XYZ"']
        if limit is not None:
            lines.append(f'TOTAL_INK_LIMIT "{limit:.0f}"')
        lines += ["NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
                  "SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z",
                  "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(cmyk)}",
                  "BEGIN_DATA"]
        for i, (d4, x) in enumerate(zip(cmyk, xyz)):
            lines.append(f"{i + 1} "
                         + " ".join(f"{v * 100:.3f}" for v in d4) + " "
                         + " ".join(f"{v:.4f}" for v in x))
        lines.append("END_DATA")
        base.with_suffix(".ti3").write_text("\n".join(lines), encoding="utf-8")
        r = run_text([str(colprof), "-qm", "-S", str(source_gamut),
                      *_k_args(settings), str(base)],
                     capture_output=True)
        icc = base.with_suffix(".icc")
        if r.returncode != 0 or not icc.exists():
            raise OracleUnavailable(
                f"proxy colprof failed: {(r.stderr or r.stdout)[:200]}")

        # Neutral rendering table: realized perceptual along the L axis.
        ls = np.linspace(0.0, 100.0, 41)
        inp = "\n".join(f"{v:.3f} 0 0" for v in ls)
        r1 = run_text([str(xicclu), "-fb", "-ip", "-pl", str(icc)],
                      input=inp, capture_output=True)
        dev4 = [ln.rsplit("->", 1)[1].split()[:4]
                for ln in r1.stdout.splitlines() if "->" in ln]
        r2 = run_text([str(xicclu), "-ff", "-ir", "-pl", str(icc)],
                      input="\n".join(" ".join(d) for d in dev4),
                      capture_output=True)
        neutral = np.array([[float(v) for v in ln.rsplit("->", 1)[1]
                             .split()[:3]]
                            for ln in r2.stdout.splitlines() if "->" in ln])
        if len(neutral) != len(ls):
            raise OracleUnavailable("proxy neutral sampling failed")
        # K behaviour along the same axis (device K of the proxy's B2A).
        k_curve = np.array([float(d[3]) for d in dev4])
        return {"l_axis": ls, "neutral_lab": neutral, "k_curve": k_curve}


def invert_mapping(mapper, mapped_lab: np.ndarray, iters: int = 20
                   ) -> np.ndarray:
    """Numeric inverse of a gamut map (colprof -nI: the perceptual A2B gets
    the inverse mapping applied so A2B0∘B2A0 ≈ identity in gamut).

    Damped fixed-point iteration — the map is a contraction near identity
    in the protected core and monotone along its rays, so this converges
    for the in-gamut colours the A2B actually carries.
    """
    lab0 = mapped_lab.copy()
    for _ in range(iters):
        err = mapped_lab - mapper.map_lab(lab0)
        lab0 = lab0 + 0.7 * err
        if np.abs(err).max() < 1e-3:
            break
    return lab0


def build_mapped_b2a(model: ForwardModel, meas: Ti3Measurement, grid: int,
                     source_gamut: Path, *, channel_letters: list[str],
                     is_additive: bool, ink_limit: float | None,
                     entries: int, codec=None, settings=None,
                     a2b_grid: int | None = None,
                     a2b_entries: int | None = None,
                     anchor: dict | None = None) -> dict:
    """Mapped tables per intent → dict of mft2 tags/aliases for the writer.

    Returns entries for ``B2A0``/``B2A2`` (bytes or the alias string
    ``"B2A1"``) and, with colprof's ``-nI``, inverse-mapped ``A2B0``/``A2B2``.
    """
    from workflow.profile_engine.pcs import LabPcs
    codec = codec or LabPcs
    accurate = getattr(settings, "gammap_mode", "") == "accurate"
    extra_hues = None
    black_l = None
    if accurate and meas is not None and hasattr(meas, "extra_ink_hues"):
        extra_hues = meas.extra_ink_hues() or None
        black_l = float(meas.lab_relative[meas.black_index, 0])
    k_gen = None
    if getattr(settings, "k_rule", ""):
        k_gen = {"rule": settings.k_rule,
                 "params": getattr(settings, "k_curve_params", None),
                 "locus": getattr(settings, "k_locus", False)}
        if black_l is None and meas is not None \
                and hasattr(meas, "lab_relative"):
            black_l = float(meas.lab_relative[meas.black_index, 0])
    # colprof default computes the source surface through the source
    # profile's perceptual/saturation intent per table; -nP/-nS switch that
    # table's source to the colorimetric intent (xicc: noptop/nostos).
    perc_int = 1 if getattr(settings, "perc_src_colorimetric", False) else 0
    sat_int = 1 if getattr(settings, "sat_src_colorimetric", False) else 2
    dst = destination_surface_lab(model, ink_limit=ink_limit,
                                  is_additive=is_additive, dense=accurate)
    if accurate and meas is not None and hasattr(meas, "lab_relative"):
        # The measured patches are ground truth — they carry no model error,
        # and solid-ink/boundary patches can reach past the fitted shell.
        # The radial-maximum binning keeps whichever is outermost.
        dst = np.vstack([dst, meas.lab_relative])
    node_lab = codec.node_lab(grid)
    inv_curves = b2a_mod.inverse_curves(model.curves)
    out: dict[str, bytes | str] = {}
    mappers: dict[str, object] = {}
    mapped_by_tag: dict[str, np.ndarray] = {}

    # First choice: the ported gammap — colprof's own gamut-mapping
    # algorithm running natively in the engine (Jab appearance space,
    # validated 0.34 median against Argyll's own map; no colprof run).
    # Second: the arm's-length colprof oracle (for intents/options the
    # port doesn't cover yet). Last: the engine's closed-form family
    # (multi-ink data or no Argyll binaries at all).
    progress = getattr(settings, "progress", None) if settings else None
    oracle: dict[str, object] = {}
    # Bit-exact mode on <=4-ink devices: colprof itself CAN build these, so the
    # most faithful "Argyll's engine" result is real colprof — the oracle reads
    # colprof's own B2A tables, whereas the native helper re-inverts with the
    # engine's model and so only approximates them. The helper is reserved for
    # CMY+N, where colprof refuses. Fast mode always uses the Python mapper.
    # Maximum-accuracy mode renders through the same bit-exact route.
    _n = getattr(model, "n_channels", 0) if model is not None else 0
    _bitexact_le4 = (getattr(settings, "gammap_mode", "fast")
                     in ("argyll", "accurate") and 0 < _n <= 4)
    # #123 W5 (candidate "render2"): the bijective CAM16-UCS radial
    # mapper replaces the Argyll-matched rendering for the DEFAULT
    # perceptual/saturation intents — explicit -t/-T selections keep the
    # Argyll behaviour. No oracle/port fitting needed at all then.
    render2 = (accurate
               and ("render2" in getattr(settings, "engine_candidates",
                                         frozenset())
                    or getattr(settings, "render_style", "argyll")
                    == "bijective")
               and not getattr(settings, "perc_intent", "")
               and not getattr(settings, "sat_intent", ""))
    if render2 and progress:
        progress("Gamut mapping (maximum accuracy): bijective CAM16-UCS "
                 "rendering intents (candidate).")
    if settings is not None and model is not None and not _bitexact_le4 \
            and not render2:
        try:
            from workflow.profile_engine.gammap_port.wire import (
                PortUnavailable, fit_gammap_port_mappers)
            oracle = fit_gammap_port_mappers(
                model, meas, source_gamut, settings,
                getattr(settings, "argyll_bin", None), progress,
                is_additive=is_additive, ink_limit=ink_limit)
        except Exception as exc:                      # noqa: BLE001
            if progress:
                progress(f"Ported gammap unavailable ({exc}) — "
                         "matching colprof's rendering instead.")
    elif _bitexact_le4 and progress:
        progress("Gamut mapping (maximum accuracy): rendering intents "
                 "matched to ArgyllCMS colprof."
                 if accurate else
                 "Gamut mapping (bit-exact): rendering with ArgyllCMS "
                 "colprof directly.")
    if settings is not None and meas is not None and not render2 and (
            "B2A0" not in oracle or "B2A2" not in oracle):
        try:
            cp = fit_colprof_mappers(
                meas, source_gamut, settings,
                getattr(settings, "argyll_bin", None), progress,
                node_lab=node_lab)
            for tag, m in cp.items():
                oracle.setdefault(tag, m)
        except OracleUnavailable as exc:
            if progress:
                progress(f"Using the engine's own rendering ({exc}).")

    for tag, intent, s_int, default_kw in (
            ("B2A0", getattr(settings, "perc_intent", ""), perc_int, {}),
            ("B2A2", getattr(settings, "sat_intent", ""), sat_int,
             _SAT_DEFAULT)):
        if intent in _COLORIMETRIC_INTENTS:
            out[tag] = "B2A1"          # colorimetric-family intent: exact
            continue
        mapper = oracle.get(tag)
        if render2:
            from workflow.profile_engine.render2 import RadialUcsMapper
            src = source_surface_from_profile(source_gamut, intent=s_int)
            mapper = RadialUcsMapper(src, dst,
                                     "p" if tag == "B2A0" else "s")
        elif mapper is None:
            src = source_surface_from_profile(source_gamut, intent=s_int)
            mapper = _mapper_for(intent, default_kw, src, dst, settings)
            if anchor is not None and isinstance(mapper, GamutMapper):
                # +N: colprof-anchored neutral rendering (CMYK proxy).
                mapper.neutral_table = anchor
        if mapper is None:
            out[tag] = "B2A1"
            continue
        mappers[tag] = mapper
        if progress is not None and getattr(mapper, "expensive_map", False):
            # The helper rebuilds Argyll's new_gammap per call (~20 s).
            progress(f"Gamut mapping: matching source colours "
                     f"({'1' if tag == 'B2A0' else '2'}/2, Argyll's "
                     f"mapper)…")
        mapped = mapper.map_lab(node_lab)
        mapped_by_tag[tag] = mapped
        # Mapped targets land inside (or at) the gamut surface, so per-node
        # inversion converges everywhere — the boundary-cell kink that makes
        # the colorimetric table need a global refit doesn't arise here.
        dev, _residual = b2a_mod.invert_to_device(
            model, mapped, channel_letters=channel_letters,
            is_additive=is_additive, ink_limit=ink_limit,
            accurate=accurate, extra_hues=extra_hues, black_l=black_l,
            k_gen=k_gen,
            ucs=accurate and "ucs" in getattr(settings, "engine_candidates",
                                              frozenset()),
            progress=progress,
            progress_label="Gamut mapping: building the final colour table")
        shaped = model.shape_device(dev)
        out[tag] = icw.make_mft2(
            3, model.n_channels, grid, icw.device_to_u16(shaped),
            in_tables=codec.b2a_in_tables(entries),
            out_tables=icw.curves_to_tables(inv_curves, entries))

    if getattr(settings, "inverse_gamut_a2b", False) and mappers \
            and a2b_grid is not None:
        # colprof -nI: perceptual/saturation A2B tables carry the INVERSE
        # gamut mapping, so table pairs round-trip to identity in gamut.
        n = model.n_channels
        for a2b_tag, b2a_tag in (("A2B0", "B2A0"), ("A2B2", "B2A2")):
            mapper = mappers.get(b2a_tag)
            if mapper is None:
                continue
            if hasattr(mapper, "unmap_lab"):
                # render2: the radial map has a closed-form inverse —
                # A2B0/2 = exact algebra, no fixed-point iteration.
                inv_lab = mapper.unmap_lab(model.clut_lab())
                out[a2b_tag] = icw.make_mft2(
                    n, 3, a2b_grid, codec.encode(inv_lab),
                    in_tables=icw.curves_to_tables(
                        model.curves, a2b_entries or entries),
                    out_tables=np.tile(
                        icw._identity_table(a2b_entries or entries),
                        (3, 1)))
                continue
            if getattr(mapper, "expensive_map", False) \
                    and b2a_tag in mapped_by_tag:
                # The bit-exact helper rebuilds Argyll's new_gammap on every
                # call; the fixed-point inversion below would run it ~20
                # times per intent. A displacement warp fitted to the node
                # mapping already computed answers the inverse queries at
                # the same fidelity the inversion itself has.
                mapper = WarpMapper(node_lab, mapped_by_tag[b2a_tag])
            inv_lab = invert_mapping(mapper, model.clut_lab())
            out[a2b_tag] = icw.make_mft2(
                n, 3, a2b_grid, codec.encode(inv_lab),
                in_tables=icw.curves_to_tables(model.curves,
                                               a2b_entries or entries),
                out_tables=np.tile(icw._identity_table(a2b_entries or entries),
                                   (3, 1)))
    return out
