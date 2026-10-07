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

NOTHING OF IT STAYS ON DISK (beta 12). The converted page used to live in a
temporary folder kept for the whole session and removed at quit, so a crash or
a Force Quit left it behind. Now cctiff writes into a folder that exists only
for the duration of the call; the result is read into memory and the folder
removed at once. The folder carries the process id, so one left by a ChromIQ
killed in the middle of a call is recognised and swept by the next one, as the
RGB preview does (``workflow/print_preview.py``).

Callers show the result with a **"via profile"** badge; when no profile is
found (or cctiff fails) they fall back to the approximate composite and badge
it as such — nobody should judge ink balance from a naive composite (#72).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections import OrderedDict
from pathlib import Path
from typing import Callable

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary

log = get_logger(__name__)

_TIMEOUT_S = 120

# (tiff path, tiff mtime, profile path, profile mtime) → the converted
# pages, as RGB images in memory. The most recent few only: the preview keeps
# its own rendered pages, this saves a second cctiff run on a re-render.
_cache: "OrderedDict[tuple[str, float, str, float], tuple]" = OrderedDict()
_CACHE_PAGES = 6

#: cctiff's folder for one call, named after the process that made it.
_TMP_PREFIX = "chromiq-colorimetric-"
_swept = False


def _tmp_prefix() -> str:
    return f"{_TMP_PREFIX}{os.getpid()}-"


def _sweep_orphans(root: "Path | None" = None) -> None:
    """Once per process: remove this module's folders left by a ChromIQ that
    no longer runs. Only ``chromiq-colorimetric-<pid>-*`` in the temporary
    folder, only when that process is gone."""
    global _swept
    if _swept and root is None:
        return
    _swept = True
    from workflow.print_preview import _pid_alive
    base = Path(root or tempfile.gettempdir())
    try:
        found = list(base.glob(_TMP_PREFIX + "*"))
    except OSError:
        return
    for d in found:
        pid = d.name[len(_TMP_PREFIX):].split("-", 1)[0]
        if not d.is_dir() or d.is_symlink() or not pid.isdigit() \
                or _pid_alive(int(pid)):
            continue
        shutil.rmtree(d, ignore_errors=True)


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


def colorimetric_rgb_frames(
    tiff_path: str | Path,
    profile: str | Path,
    bin_dir: str | Path,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> "tuple | None":
    """Convert a separated chart TIFF to true-colour sRGB via cctiff.

    Returns its pages as RGB ``PIL.Image`` objects in memory (cached per
    source/profile mtime), or ``None`` when the conversion isn't possible
    (missing cctiff/sRGB ref, profile/channel mismatch, cctiff error):
    callers fall back to the approximate composite. Never raises, and leaves
    no file behind.
    """
    tiff_path, profile, bin_dir = Path(tiff_path), Path(profile), Path(bin_dir)
    try:
        key = (str(tiff_path), tiff_path.stat().st_mtime,
               str(profile), profile.stat().st_mtime)
    except OSError:
        return None
    hit = _cache.get(key)
    if hit is not None:
        _cache.move_to_end(key)
        return hit

    exe = bin_dir / argyll_binary("cctiff")
    srgb = _srgb_ref(bin_dir)
    if not exe.exists() or srgb is None:
        return None
    _sweep_orphans()
    try:
        tmp = tempfile.mkdtemp(prefix=_tmp_prefix())
    except OSError as exc:
        log.warning("cctiff colorimetric preview: no temporary folder: %s", exc)
        return None
    try:
        out = Path(tmp) / f"{tiff_path.stem}.tif"
        # -f T = TIFF out; -i r = relative colorimetric on both profiles — the
        # exact form verified in the issue's experiments.
        cmd = [str(exe), "-f", "T", "-i", "r", str(profile), "-i", "r",
               str(srgb), str(tiff_path), str(out)]
        try:
            r = run_text(cmd, runner=runner, capture_output=True,
                         timeout=_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("cctiff colorimetric preview failed: %s", exc)
            return None
        if r.returncode != 0 or not out.is_file():
            log.info("cctiff colorimetric preview unavailable (%s): %s",
                     r.returncode, (r.stderr or r.stdout or "").strip()[:200])
            return None
        frames = _read_frames(out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not frames:
        return None
    _cache[key] = frames
    while len(_cache) > _CACHE_PAGES:
        _cache.popitem(last=False)
    return frames


def _read_frames(path: Path) -> tuple:
    """Every page of *path* as an RGB image fully in memory (the file is
    removed right after)."""
    try:
        from PIL import Image
        frames = []
        with Image.open(path) as im:
            i = 0
            while True:
                try:
                    im.seek(i)
                except EOFError:
                    break
                frames.append(im.convert("RGB"))     # a copy, loaded now
                i += 1
        return tuple(frames)
    except Exception as exc:  # noqa: BLE001 — a preview upgrade is best-effort
        log.info("cctiff colorimetric preview unreadable: %s", exc)
        return ()


def colorimetric_rgb_frame(tiff_path, profile, bin_dir, frame: int = 0,
                           runner=subprocess.run):
    """Page *frame* of :func:`colorimetric_rgb_frames` (the first page when
    the file has fewer), or ``None``."""
    frames = colorimetric_rgb_frames(tiff_path, profile, bin_dir, runner)
    if not frames:
        return None
    return frames[frame if 0 <= frame < len(frames) else 0]
