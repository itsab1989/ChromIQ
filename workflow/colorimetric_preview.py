"""Colorimetric on-screen preview of separated (multi-ink) chart TIFFs (#72 Tier D).

The engine's device-native TIFFs carry *ink values*; the default preview
composites them into an honest-but-approximate RGB picture. When the chart's
**device profile is known**, cctiff can render the true colours instead::

    cctiff -f T -i r <device profile> <Argyll ref/sRGB.icm> chart.tif preview.tif

(verified live in the issue's experiment rounds — a correct sRGB render of a
separated CMYK chart). This module wraps that: profile discovery from the
chart's sidecars, the conversion (injectable ``subprocess.run``, the
reference_convert.py house pattern), and an mtime-keyed cache so page flips
and re-renders don't re-run cctiff.

Callers show the result with a **"via profile"** badge; when no profile is
found (or cctiff fails) they fall back to the approximate composite and badge
it as such — nobody should judge ink balance from a naive composite (#72).
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary

log = get_logger(__name__)

_TIMEOUT_S = 120

# (tiff path, tiff mtime, profile path, profile mtime) → converted RGB TIFF.
_cache: dict[tuple[str, float, str, float], Path] = {}
_cache_dir: tempfile.TemporaryDirectory | None = None


def find_device_profile(tiff_path: str | Path) -> Path | None:
    """The device (preconditioning) profile recorded for a chart, if any.

    Looks, in order, for: the run folder's ``preconditioning.icc`` (the
    refinement workflow's standard artefact) and the chart's ``meta.json``
    creation recipe (``device.precond``, written by the New-patch-set dialog
    since #72). Returns the first existing candidate.
    """
    folder = Path(tiff_path).parent
    cand = folder / "preconditioning.icc"
    if cand.is_file():
        return cand
    meta = folder / "meta.json"
    if meta.is_file():
        try:
            import json
            data = json.loads(meta.read_text(encoding="utf-8"))
            recipe = (data.get("editor_recipe") or {}) if isinstance(data, dict) else {}
            precond = ((recipe.get("device") or {}).get("precond") or "")
            if precond and Path(precond).is_file():
                return Path(precond)
        except (OSError, ValueError):
            pass
    return None


def _srgb_ref(bin_dir: Path) -> Path | None:
    """Argyll's shipped sRGB profile (``ref/`` is a sibling of ``bin/``)."""
    ref = bin_dir.parent / "ref" / "sRGB.icm"
    return ref if ref.is_file() else None


def colorimetric_rgb_tiff(
    tiff_path: str | Path,
    profile: str | Path,
    bin_dir: str | Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Path | None:
    """Convert a separated chart TIFF to true-colour sRGB via cctiff.

    Returns the converted RGB TIFF's path (cached per source/profile mtime),
    or ``None`` when the conversion isn't possible (missing cctiff/sRGB ref,
    profile/channel mismatch, cctiff error) — callers fall back to the
    approximate composite. Never raises.
    """
    global _cache_dir
    tiff_path, profile, bin_dir = Path(tiff_path), Path(profile), Path(bin_dir)
    try:
        key = (str(tiff_path), tiff_path.stat().st_mtime,
               str(profile), profile.stat().st_mtime)
    except OSError:
        return None
    hit = _cache.get(key)
    if hit is not None and hit.is_file():
        return hit

    exe = bin_dir / argyll_binary("cctiff")
    srgb = _srgb_ref(bin_dir)
    if not exe.exists() or srgb is None:
        return None
    if _cache_dir is None:
        _cache_dir = tempfile.TemporaryDirectory(prefix="chromiq-colorimetric-")
    out = Path(_cache_dir.name) / f"{tiff_path.stem}-{len(_cache)}.tif"
    # -f T = TIFF out; -i r = relative colorimetric on both profiles — the
    # exact form verified in the issue's experiments.
    cmd = [str(exe), "-f", "T", "-i", "r", str(profile), "-i", "r", str(srgb),
           str(tiff_path), str(out)]
    try:
        r = run_text(cmd, runner=runner, capture_output=True, timeout=_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("cctiff colorimetric preview failed: %s", exc)
        return None
    if r.returncode != 0 or not out.is_file():
        log.info("cctiff colorimetric preview unavailable (%s): %s",
                 r.returncode, (r.stderr or r.stdout or "").strip()[:200])
        return None
    _cache[key] = out
    return out
