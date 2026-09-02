"""Engine wiring for the gammap port — builds the colprof-equivalent
perceptual mapper from the engine's own forward model plus the source
profile, with no colprof involved.

Composition (exactly profout.c's B2A gamut-mapping chain):

    map_lab(Lab_pcs) = Ap_dst.jab_to_lab( GammapMapper.map_lab(
                           Ap_src.lab_to_jab(Lab_pcs) ) )

Source gamut: Argyll's own ``iccgamut -ff -ir -pj -d10`` on the source
profile (identical geometry to what colprof feeds new_gammap; iccgamut
is an arm's-length utility like the rest of the workflow). Destination
gamut: a minimal temporary ICC is written from the engine's own forward
model (A2B only) and handed to the same ``iccgamut`` — the identical
gamut-construction code path colprof's ogam uses, with the model
standing in for the profile that doesn't exist yet.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from workflow.profile_engine.gammap_helper import (
    HelperUnavailable, gres_mapres_for_quality, is_available, run_gammap)
from workflow.profile_engine.gammap_port.cam02 import (Appearance,
                                                       lab_to_xyz)
from workflow.profile_engine.gammap_port.cusps import cusps_from_cloud
from workflow.profile_engine.gammap_port.gamio import read_gam
from workflow.profile_engine.gammap_port.gammap import GammapMapper
from workflow.profile_engine.gammap_port.gamutsurf import CENT
from core.proc_text import run_text


class PortUnavailable(RuntimeError):
    """The gammap port can't handle this configuration."""


def read_icc_wtpt(path: Path | str) -> np.ndarray:
    """Media white point (XYZ, Y 0..1) from an ICC profile's wtpt tag."""
    data = Path(path).read_bytes()
    ntags = struct.unpack(">I", data[128:132])[0]
    for i in range(ntags):
        off = 132 + 12 * i
        sig, toff, _size = struct.unpack(">4sII", data[off:off + 12])
        if sig == b"wtpt":
            x, y, z = struct.unpack(">iii", data[toff + 8:toff + 20])
            return np.array([x, y, z]) / 65536.0
    raise PortUnavailable(f"no wtpt tag in {path}")


def source_gam_jab(source_profile: Path | str, bin_dir: Path,
                   detail: float = 10.0):
    """Run iccgamut -pj on the source profile → parsed Jab GamFile."""
    src = Path(source_profile)
    if not src.exists():
        raise PortUnavailable(f"source profile not found: {src}")
    iccgamut = bin_dir / "iccgamut"
    if not iccgamut.exists():
        raise PortUnavailable("iccgamut not found")
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / ("src" + src.suffix)
        shutil.copy(src, work)
        r = run_text([str(iccgamut), "-ff", "-ir", "-pj",
                      f"-d{detail:g}", work.name],
                     capture_output=True, cwd=td)
        gam = work.with_suffix(".gam")
        if r.returncode != 0 or not gam.exists():
            raise PortUnavailable(
                f"iccgamut failed: {(r.stderr or r.stdout)[:160]}")
        return read_gam(gam)


def dest_gam_jab(model, paper_xyz: np.ndarray, bin_dir: Path,
                 color_rep: str = "", detail: float = 10.0):
    """Destination Jab gamut via a temporary model-only ICC + iccgamut.

    Writes a minimal profile (A2B from the forward model, wtpt = paper)
    and runs the same ``iccgamut -ff -ir -pj`` colprof's ogam geometry
    comes from — Argyll's own gamut construction on the engine's model.
    """
    from workflow.profile_engine import icc_writer as icw
    iccgamut = bin_dir / "iccgamut"
    if not iccgamut.exists():
        raise PortUnavailable("iccgamut not found")
    n = model.n_channels
    a2b = icw.make_mft2(
        n, 3, model.grid, icw.lab_to_u16(model.clut_lab()),
        in_tables=icw.curves_to_tables(model.curves, 2048),
        out_tables=np.tile(icw._identity_table(2048), (3, 1)))
    spec = icw.ProfileSpec(n_channels=n, description="chromiq-dest-gamut",
                           color_rep=color_rep,
                           wtpt=tuple(np.asarray(paper_xyz, float)))
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "dest.icc"
        icw.write_profile(work, spec, {"A2B0": a2b, "A2B1": "A2B0",
                                       "A2B2": "A2B0"})
        r = run_text([str(iccgamut), "-ff", "-ir", "-pj",
                      f"-d{detail:g}", work.name],
                     capture_output=True, cwd=td)
        gam = work.with_suffix(".gam")
        if r.returncode != 0 or not gam.exists():
            raise PortUnavailable(
                f"iccgamut (dest) failed: {(r.stderr or r.stdout)[:160]}")
        return read_gam(gam)


def mesh_from_cloud(cloud: np.ndarray, nh: int = 36, nb: int = 18):
    """Triangulated star-shaped surface from a boundary cloud: max radius
    per (hue × inclination) bin about Argyll's gamut centre, on a UV
    sphere with proper pole caps. Returns (verts, tris)."""
    rel = cloud - CENT[None, :]
    r = np.linalg.norm(rel, axis=1)
    incl = np.arccos(np.clip(rel[:, 0] / np.maximum(r, 1e-9), -1, 1))
    hue = np.arctan2(rel[:, 2], rel[:, 1]) % (2 * np.pi)
    hb = np.minimum((hue / (2 * np.pi) * nh).astype(int), nh - 1)
    bb = np.minimum((incl / np.pi * nb).astype(int), nb - 1)
    tab = np.zeros((nh, nb))
    np.maximum.at(tab, (hb, bb), r)
    # fill empty bins from hue neighbours, then light hue smoothing
    for b in range(nb):
        col = tab[:, b]
        if (col == 0).any():
            good = col > 0
            if not good.any():
                col[:] = tab[tab > 0].min() if (tab > 0).any() else 1.0
            else:
                idx = np.arange(nh)
                col[~good] = np.interp(idx[~good], idx[good], col[good],
                                       period=nh)
        tab[:, b] = col
    tab = (tab + np.roll(tab, 1, 0) + np.roll(tab, -1, 0)) / 3.0

    verts = [CENT + np.array([r, 0.0, 0.0])
             for r in (tab[:, 0].mean(),)]          # top pole (L high)
    for j in range(nb):
        th = np.pi * (j + 0.5) / nb
        for i in range(nh):
            ph = 2 * np.pi * (i + 0.5) / nh
            rad = tab[i, j]
            verts.append(CENT + rad * np.array([np.cos(th),
                                                np.sin(th) * np.cos(ph),
                                                np.sin(th) * np.sin(ph)]))
    verts.append(CENT - np.array([tab[:, -1].mean(), 0.0, 0.0]))
    verts = np.array(verts)
    tris = []
    last = len(verts) - 1
    for i in range(nh):
        tris.append([0, 1 + i, 1 + (i + 1) % nh])
        base = 1 + (nb - 1) * nh
        tris.append([last, base + (i + 1) % nh, base + i])
    for j in range(nb - 1):
        r0, r1 = 1 + j * nh, 1 + (j + 1) * nh
        for i in range(nh):
            i2 = (i + 1) % nh
            tris.append([r0 + i, r1 + i, r1 + i2])
            tris.append([r0 + i, r1 + i2, r0 + i2])
    return verts, np.array(tris)


class PortMapper:
    """colprof-equivalent perceptual mapper built from the port."""

    def __init__(self, gm: GammapMapper, ap_src: Appearance,
                 ap_dst: Appearance) -> None:
        self._gm = gm
        self._src = ap_src
        self._dst = ap_dst

    def map_lab(self, lab: np.ndarray) -> np.ndarray:
        jab = self._src.lab_to_jab(np.atleast_2d(np.asarray(lab, float)))
        return self._dst.jab_to_lab(self._gm.map_lab(jab))


class ArgyllHelperMapper:
    """Bit-exact mapper: Argyll's real gamut mapper via the native helper.

    Holds the source/destination gamuts as files/clouds and shells out to
    ``chromiq-gammap`` for the Jab→Jab map, with the CIECAM02 conversions on
    either side done in Python (identical framing to :class:`PortMapper`).
    """

    # Every map_lab call is a helper subprocess that rebuilds new_gammap —
    # callers that would query repeatedly (the -nI inversion) should fit a
    # surrogate to one node evaluation instead.
    expensive_map = True

    def __init__(self, *, src_gam: Path, intent: str, mapres: int,
                 ap_src: Appearance, ap_dst: Appearance,
                 wp_jab, bp_jab, dst_gam: Path | None,
                 dst_cloud_jab, td) -> None:
        self._src_gam = src_gam
        self._intent = intent
        self._mapres = mapres
        self._ap_src = ap_src
        self._ap_dst = ap_dst
        self._wp_jab = wp_jab
        self._bp_jab = bp_jab
        self._dst_gam = dst_gam
        self._dst_cloud = dst_cloud_jab
        self._td = td            # keep the TemporaryDirectory alive

    def map_lab(self, lab: np.ndarray) -> np.ndarray:
        jab = self._ap_src.lab_to_jab(np.atleast_2d(np.asarray(lab, float)))
        out = run_gammap(jab, src_gam=self._src_gam, intent=self._intent,
                         mapres=self._mapres, wp_jab=self._wp_jab,
                         bp_jab=self._bp_jab, dst_gam=self._dst_gam,
                         dst_cloud_jab=self._dst_cloud)
        return self._ap_dst.jab_to_lab(out)


def _iccgamut_to(path: Path, work_icc: Path, bin_dir: Path,
                 detail: float) -> Path:
    """Run ``iccgamut -ff -ir -pj -d<detail>`` on ``work_icc`` → persistent
    ``.gam`` at ``path``. Raises :class:`PortUnavailable` on failure."""
    iccgamut = bin_dir / "iccgamut"
    if not iccgamut.exists():
        raise PortUnavailable("iccgamut not found")
    r = run_text([str(iccgamut), "-ff", "-ir", "-pj",
                  f"-d{detail:g}", work_icc.name],
                 capture_output=True, cwd=work_icc.parent)
    gam = work_icc.with_suffix(".gam")
    if r.returncode != 0 or not gam.exists():
        raise PortUnavailable(
            f"iccgamut failed: {(r.stderr or r.stdout)[:160]}")
    if gam != path:
        shutil.move(str(gam), str(path))
    return path


def fit_gammap_argyll_mappers(model, meas, source_gamut: Path | str,
                              settings, bin_dir: Path, progress=None, *,
                              is_additive: bool = True,
                              ink_limit: float | None = None) -> dict:
    """Bit-exact B2A0/B2A2 mappers backed by Argyll's real gamut mapper.

    <=4-ink: destination is the iccgamut ``.gam`` colprof itself would map
    (byte-identical). CMY+N: destination is Argyll's own ``expand`` of the
    engine model's Jab surface cloud. Raises :class:`HelperUnavailable` when
    the native binary is absent so callers fall back to the fast mapper.
    """
    if not is_available():
        raise HelperUnavailable("bit-exact helper binary not bundled")

    _mode = ("maximum accuracy"
             if getattr(settings, "gammap_mode", "") == "accurate"
             else "bit-exact")
    gres, mapres = gres_mapres_for_quality(getattr(settings, "quality", "m"))
    if progress:
        progress(f"Gamut mapping ({_mode}): reading the source colour "
                 "space…")

    # Persistent working dir shared by both intents; kept alive on the mappers.
    td = tempfile.TemporaryDirectory(prefix="chromiq-gammap-job-")
    tdp = Path(td.name)

    src = Path(source_gamut)
    if not src.exists():
        raise PortUnavailable(f"source profile not found: {src}")
    work_src = tdp / ("src" + src.suffix)
    shutil.copy(src, work_src)
    src_gam = _iccgamut_to(tdp / "src.gam", work_src, bin_dir, gres)

    src_white_xyz = read_icc_wtpt(source_gamut)
    ap_src = Appearance(src_white_xyz)

    white_lab = model.predict(np.ones((1, model.n_channels))
                              if is_additive
                              else np.zeros((1, model.n_channels)))[0]
    black_lab = model.predict(np.zeros((1, model.n_channels))
                              if is_additive
                              else np.ones((1, model.n_channels)))[0]
    paper_xyz = lab_to_xyz(white_lab[None, :])[0]
    ap_dst = Appearance(paper_xyz)
    wp_jab = ap_dst.lab_to_jab(white_lab[None, :])[0]
    bp_jab = ap_dst.lab_to_jab(black_lab[None, :])[0]

    from workflow.profile_engine.gamut_map import destination_surface_lab
    dense = getattr(settings, "gammap_mode", "") == "accurate"

    def _dest_cloud():
        """Destination shell sampled from the model — the same thing colprof's
        own get_gamut does, and the only route for CMY+N."""
        if progress:
            progress(f"Gamut mapping ({_mode}): meshing the printer's "
                     "colour shell…")
        dst_lab = destination_surface_lab(model, mesh=33, ink_limit=ink_limit,
                                          is_additive=is_additive,
                                          dense=dense)
        if dense and meas is not None and hasattr(meas, "lab_relative"):
            # Measured patches are ground truth — Argyll's expand() keeps
            # whichever points lie outermost.
            dst_lab = np.vstack([dst_lab, meas.lab_relative])
        return ap_dst.lab_to_jab(dst_lab)

    dst_gam: Path | None = None
    dst_cloud_jab = None
    if model.n_channels <= 4:
        # <=4 ink: prefer the iccgamut .gam colprof itself would map (byte-
        # identical geometry). iccgamut builds a forward gamut fine for RGB,
        # but for 4-channel devices xicc needs an inverse the A2B-only temp
        # profile doesn't have ("Unable to locate usable conversion") — so on
        # any iccgamut failure, fall back to the model-sampled cloud.
        if progress:
            progress(f"Gamut mapping ({_mode}): building the destination "
                     "gamut…")
        from workflow.profile_engine import icc_writer as icw
        n = model.n_channels
        a2b = icw.make_mft2(
            n, 3, model.grid, icw.lab_to_u16(model.clut_lab()),
            in_tables=icw.curves_to_tables(model.curves, 2048),
            out_tables=np.tile(icw._identity_table(2048), (3, 1)))
        spec = icw.ProfileSpec(n_channels=n, description="chromiq-dest-gamut",
                               color_rep=getattr(meas, "color_rep", ""),
                               wtpt=tuple(np.asarray(paper_xyz, float)))
        work_dst = tdp / "dest.icc"
        icw.write_profile(work_dst, spec, {"A2B0": a2b, "A2B1": "A2B0",
                                           "A2B2": "A2B0"})
        try:
            dst_gam = _iccgamut_to(tdp / "dest.gam", work_dst, bin_dir, gres)
        except PortUnavailable:
            dst_cloud_jab = _dest_cloud()
    else:
        dst_cloud_jab = _dest_cloud()

    # For a .gam destination the iccgamut file already carries the profile's
    # white/black (exactly colprof's), so leave it untouched; only the cloud
    # path needs explicit wp/bp.
    map_wp = None if dst_gam is not None else wp_jab
    map_bp = None if dst_gam is not None else bp_jab

    def _mk(intent: str) -> ArgyllHelperMapper:
        return ArgyllHelperMapper(
            src_gam=src_gam, intent=intent, mapres=mapres, ap_src=ap_src,
            ap_dst=ap_dst, wp_jab=map_wp, bp_jab=map_bp, dst_gam=dst_gam,
            dst_cloud_jab=dst_cloud_jab, td=td)

    return {"B2A0": _mk("p"), "B2A2": _mk("s")}


def fit_gammap_port_mappers(model, meas, source_gamut: Path | str,
                            settings, argyll_bin: Path | str | None,
                            progress=None, *, is_additive: bool = True,
                            ink_limit: float | None = None) -> dict:
    """The shipping mapper: ported gammap on Jab gamuts (B2A0).

    Currently covers the default perceptual intent (colprof "p" — the
    default when no -t is given). Other -t/-T codes and the saturation
    table fall through to the oracle/family paths.
    """
    if getattr(settings, "perc_intent", "") not in ("", "p"):
        raise PortUnavailable(
            f"-t{settings.perc_intent} not covered by the port yet")
    if getattr(settings, "src_viewing", "") or getattr(
            settings, "dst_viewing", ""):
        raise PortUnavailable("-c/-d viewing overrides not covered yet")
    if getattr(settings, "perc_src_colorimetric", False):
        raise PortUnavailable("-nP not covered by the port yet")

    bin_dir = Path(argyll_bin) if argyll_bin else Path(
        "/Applications/Argyll/bin")

    # Bit-exact mode: run Argyll's real gamut mapper via the native helper
    # (handles RGB/CMYK and CMY+N). If the binary isn't bundled, fall through
    # to the fast Python mapper below — a build never fails for a missing
    # helper. Maximum-accuracy mode uses the same bit-exact mapping.
    if getattr(settings, "gammap_mode", "fast") in ("argyll", "accurate"):
        try:
            return fit_gammap_argyll_mappers(
                model, meas, source_gamut, settings, bin_dir, progress,
                is_additive=is_additive, ink_limit=ink_limit)
        except HelperUnavailable as exc:
            if progress:
                progress(f"Bit-exact Argyll helper unavailable ({exc}); "
                         "using the fast built-in mapper.")

    # exact triangle geometry (most faithful, slower) vs sampled-table
    # surfaces (near-identical, fast) — retained internal lever, default fast
    exact = bool(getattr(settings, "gammap_exact_geometry", False))
    if progress:
        progress("Gamut mapping: reading the source colour space…")

    src = source_gam_jab(source_gamut, bin_dir)
    src_white_xyz = read_icc_wtpt(source_gamut)
    ap_src = Appearance(src_white_xyz)
    if progress:
        progress("Gamut mapping: measuring the printer's colour range…")

    # destination: Argyll's own gamut construction on a temp model ICC
    # (n ≤ 4 — Argyll's lookup machinery refuses more channels); for
    # multi-ink models the engine meshes its own model cloud in Jab —
    # there is no colprof geometry for +N, the model IS the gamut
    white_lab = model.predict(np.ones((1, model.n_channels))
                              if is_additive
                              else np.zeros((1, model.n_channels)))[0]
    black_lab = model.predict(np.zeros((1, model.n_channels))
                              if is_additive
                              else np.ones((1, model.n_channels)))[0]
    paper_xyz = lab_to_xyz(white_lab[None, :])[0]
    ap_dst = Appearance(paper_xyz)
    if model.n_channels <= 4:
        dst = dest_gam_jab(model, paper_xyz, bin_dir,
                           color_rep=getattr(meas, "color_rep", ""))
    else:
        from workflow.profile_engine.gamut_map import (
            destination_surface_lab)
        from workflow.profile_engine.gammap_port.gamio import GamFile
        dst_lab = destination_surface_lab(
            model, mesh=33, ink_limit=ink_limit, is_additive=is_additive,
            dense=getattr(settings, "gammap_mode", "") == "accurate")
        if getattr(settings, "gammap_mode", "") == "accurate" \
                and meas is not None and hasattr(meas, "lab_relative"):
            dst_lab = np.vstack([dst_lab, meas.lab_relative])
        dst_jab = ap_dst.lab_to_jab(dst_lab)
        dverts, dtris = mesh_from_cloud(dst_jab, nh=48, nb=24)
        d_cusps = cusps_from_cloud(dst_jab)
        if d_cusps is None:
            raise PortUnavailable("multi-ink cusps not resolvable")
        d_wp = ap_dst.lab_to_jab(white_lab[None, :])[0]
        d_bp = ap_dst.lab_to_jab(black_lab[None, :])[0]
        dst = GamFile(vertices=dverts, triangles=dtris, white=d_wp,
                      black=d_bp, cs_white=d_wp, cs_black=d_bp,
                      cusps=d_cusps)

    surf_cache: dict = {}      # dest/psrc shared across intents
    gm = GammapMapper(src.vertices, src.triangles, src.cs_white,
                      src.cs_black, src.cusps, dst.vertices,
                      dst.triangles, dst.cs_white, dst.cs_black,
                      dst.cusps, intent="p", dst_gam_wp=dst.white,
                      dst_gam_bp=dst.black, progress=progress,
                      surf_cache=surf_cache, exact_geometry=exact)
    out = {"B2A0": PortMapper(gm, ap_src, ap_dst)}

    # Saturation table. For RGB/CMYK we leave B2A2 to the colprof-matched
    # oracle (colprof-exact). For multi-ink there IS no colprof oracle, so
    # the ported saturation mapper is the best available — far better than
    # the closed-form family it would otherwise fall back to. (The
    # saturation port currently reproduces Argyll's own map to ~0.65 ΔE
    # vs 0.34 for perceptual; the extra parity work is tracked in #45.)
    if model.n_channels > 4:
        if progress:
            progress("Gamut mapping: building the saturation table…")
        gms = GammapMapper(src.vertices, src.triangles, src.cs_white,
                           src.cs_black, src.cusps, dst.vertices,
                           dst.triangles, dst.cs_white, dst.cs_black,
                           dst.cusps, intent="s", dst_gam_wp=dst.white,
                           dst_gam_bp=dst.black, surf_cache=surf_cache,
                           exact_geometry=exact)
        out["B2A2"] = PortMapper(gms, ap_src, ap_dst)
    return out
