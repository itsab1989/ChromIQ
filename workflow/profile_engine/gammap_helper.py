"""Bridge to the bundled ``chromiq-gammap`` native helper (bit-exact Argyll).

The helper runs ArgyllCMS's *actual* gamut mapper (``new_gammap`` / ``domap``)
on a destination colour shell. For <=4-ink devices the shell is the iccgamut
``.gam`` colprof itself would feed the mapper (byte-identical); for CMY+N the
shell is built from a Jab point cloud via Argyll's own ``gamut->expand`` — the
only route, since colprof's ICC ink separation refuses >4 inks. Either way the
gamut-mapping maths is literally Argyll's.

This is the "Bit-exact (Argyll's engine)" side of the Build-Profile gamut-
mapping mode. It is invoked arm's-length via a subprocess, exactly like the
colprof / iccgamut calls elsewhere in the workflow, so the AGPL helper stays a
separate program. When the binary is missing or fails, callers fall back to the
Python fast mapper — a build must never hard-fail because the helper is absent.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary, resource_path

log = get_logger(__name__)

# colprof's gamut-map resolution / gamut-surface feature resolution, keyed by
# output quality (profile/profout.c: oquality 3/2/1/0). gres is the iccgamut
# -d detail; mapres is new_gammap's rspl resolution.
_GRES_MAPRES = {
    "u": (7.0, 49),
    "h": (8.0, 39),
    "m": (10.0, 29),
    "l": (12.0, 19),
}


class HelperUnavailable(RuntimeError):
    """The bundled bit-exact helper is missing, unrunnable, or failed."""


def gres_mapres_for_quality(quality: str) -> tuple[float, int]:
    """(gamut-surface gres, gamut-map mapres) for a colprof -q letter."""
    return _GRES_MAPRES.get((quality or "m")[:1], _GRES_MAPRES["m"])


def helper_path() -> Path:
    """Locate the bundled ``chromiq-gammap`` binary.

    Search order: ``$CHROMIQ_GAMMAP`` override (dev/testing), then the
    bundled ``native/`` location resolved for both source and frozen runs.
    """
    override = os.environ.get("CHROMIQ_GAMMAP")
    if override:
        p = Path(override)
        if p.exists():
            return p
        raise HelperUnavailable(f"$CHROMIQ_GAMMAP points at a missing file: {p}")
    p = resource_path("native/" + argyll_binary("chromiq-gammap"))
    if not p.exists():
        raise HelperUnavailable(f"bit-exact helper not found at {p}")
    _ensure_executable(p)
    return p


def _ensure_executable(p: Path) -> None:
    """Best-effort +x — PyInstaller may bundle the helper without the exec
    bit; the extracted copy lives in a writable temp dir, so restore it."""
    if os.name == "nt":
        return
    try:
        if not os.access(p, os.X_OK):
            os.chmod(p, os.stat(p).st_mode | 0o111)
    except OSError as exc:
        log.debug("could not chmod helper %s: %s", p, exc)


def is_available() -> bool:
    """True if the helper binary can be located (cheap existence check)."""
    try:
        helper_path()
        return True
    except HelperUnavailable:
        return False


def run_gammap(query_jab: np.ndarray, *, src_gam: Path | str, intent: str,
               mapres: int, wp_jab=None, bp_jab=None,
               dst_gam: Path | str | None = None,
               dst_cloud_jab: np.ndarray | None = None) -> np.ndarray:
    """Map ``query_jab`` (N×3 CIECAM02 Jab) through Argyll's gamut mapper.

    Exactly one of ``dst_gam`` (a .gam file, <=4 ink) or ``dst_cloud_jab``
    (a boundary point cloud, CMY+N) must be given. ``wp_jab``/``bp_jab`` are
    required with a cloud and override the .gam's white/black otherwise.

    Returns the mapped N×3 Jab lattice in query order. Raises
    :class:`HelperUnavailable` on any failure (missing binary, non-zero exit,
    truncated output).
    """
    exe = helper_path()
    q = np.atleast_2d(np.asarray(query_jab, float))
    if q.shape[1] != 3:
        raise HelperUnavailable(f"query must be N×3, got {q.shape}")
    if (dst_gam is None) == (dst_cloud_jab is None):
        raise HelperUnavailable("exactly one of dst_gam / dst_cloud_jab")

    with tempfile.TemporaryDirectory(prefix="chromiq-gammap-") as td:
        tdp = Path(td)
        qf, of = tdp / "query.txt", tdp / "out.txt"
        np.savetxt(qf, q, fmt="%.9f")
        args = [str(exe), "--src", str(src_gam), "--intent", intent,
                "--mapres", str(int(mapres)),
                "--query", str(qf), "--out", str(of)]
        if dst_gam is not None:
            args += ["--dst-gam", str(dst_gam)]
        else:
            cf = tdp / "cloud.txt"
            np.savetxt(cf, np.atleast_2d(np.asarray(dst_cloud_jab, float)),
                       fmt="%.9f")
            args += ["--dst-cloud", str(cf)]
        if wp_jab is not None and bp_jab is not None:
            args += ["--wp", *[f"{v:.9f}" for v in np.ravel(wp_jab)[:3]],
                     "--bp", *[f"{v:.9f}" for v in np.ravel(bp_jab)[:3]]]
        try:
            r = run_text(args, capture_output=True)
        except OSError as exc:
            raise HelperUnavailable(f"could not run helper: {exc}") from exc
        if r.returncode != 0 or not of.exists():
            raise HelperUnavailable(
                f"helper failed ({r.returncode}): "
                f"{(r.stderr or r.stdout or '').strip()[:200]}")
        out = np.loadtxt(of, ndmin=2)
        if out.shape != q.shape:
            raise HelperUnavailable(
                f"helper returned {out.shape}, expected {q.shape}")
        return out
