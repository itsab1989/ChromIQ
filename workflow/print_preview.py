"""The chart preview shows the sheet as it will print (#182, beta 12).

Knut, 6045500910 answer 4: *"preview should always look as paper would look
printed, assuming normal printing path, as Sebastian said."* Basti,
6045468325: *"as soon as those settings are locked in for a verification run
I think showing the softproofed version makes sense. Maybe the tiff preview
could show a little indicator that gives this information without being a
distraction."*

A chart page TIFF holds the numbers sent to the printer. Painted as screen
RGB they are not what the paper shows (FINDINGS J of the beta-12 diagnosis:
L* 4.8 brighter on average on Basti's run2 chart). This module decides, for
one page, what the normal printing path does to it, and renders that:

* **a profiling chart** prints raw. With the run's profile built, the page is
  shown through that profile; before it, as device values, and the indicator
  says so;
* **a verification chart printed raw** (a FROM PROFILE GAMUT chart is always
  raw, §3.1a; a regular chart when Raw is chosen) is shown through the run's
  profile;
* **a verification chart printed through the profile** is converted exactly
  as the print converts it (the recorded source profile and intent, the
  cctiff arguments of :func:`workflow.verification_print.
  convert_pages_through_profile`) and the result shown through the profile.

Which way a verification chart prints: its print record once it has been
printed (and the record is newer than the page), else the Colour row's choice
(the Print Chart tab passes its live radios; the other tabs read the target's
stored choice, or the same history-aware default the Print tab starts from).

The screen end is relative colorimetric to Argyll's ``sRGB.icm``, as the
CMYK preview's "True colours" render already is: the paper is shown as the
screen's white, the colours as they sit relative to it.

Nothing here changes what is printed. Process model: ``subprocess.run`` with
an injectable runner and a ``timeout=``; results cached per page, profile and
chain, so a chart is soft-proofed once.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.logger import get_logger

log = get_logger(__name__)

#: What the preview shows.
KIND_RAW = "raw"            # the page's values, through the run's profile
KIND_THROUGH = "through"    # converted as the print converts it, then shown
KIND_DEVICE = "device"      # the page's values as screen colours (no profile)

#: Why a page is shown as device values.
WHY_NO_PROFILE = "no_profile"
WHY_CALIBRATED = "calibrated"      # the page holds calibrated pixels (-K)
WHY_FAILED = "failed"              # ArgyllCMS could not convert it

_TIMEOUT_S = 120

_cache: "dict[tuple, Path]" = {}
_failed: "set[tuple]" = set()
_cache_dir: "tempfile.TemporaryDirectory | None" = None


@dataclass(frozen=True)
class PreviewPlan:
    """How one chart page is to be shown."""
    kind: str
    profile: "Path | None" = None
    intent: str = ""                 # the print's own intent (through)
    source_profile: str = ""         # the print's source profile (through)
    printed: bool = False            # decided by a print record
    why: str = ""                    # for KIND_DEVICE


@dataclass(frozen=True)
class _Chart:
    run_dir: Path
    ti2: Path
    verification: bool
    record_from: "Path | None"       # a .ti3 path whose print record applies


def _page_stem(tiff: Path) -> str:
    """The chart stem of a page TIFF (``<stem>.tif`` or ``<stem>_01.tif``)."""
    stem = tiff.stem
    base = stem.rstrip("0123456789")
    if base != stem and base.endswith(("_", "-")):
        return base[:-1]
    return stem


def chart_of_page(tiff: "str | Path") -> "_Chart | None":
    """Which run's chart *tiff* is a page of, or None (a calibration chart,
    a chart opened from elsewhere, a page in a temporary folder)."""
    from core.file_manager import VERIFICATIONS_DIRNAME
    RUNS_DIRNAME = "runs"            # Project.runs_root
    tiff = Path(tiff)
    d = tiff.parent
    stem = (tiff.stem if (d / f"{tiff.stem}.ti2").is_file()
            else _page_stem(tiff))
    try:
        if d.name == VERIFICATIONS_DIRNAME and d.parent.parent.name == RUNS_DIRNAME:
            ti2 = d / f"{stem}.ti2"
            return _Chart(d.parent, ti2, True, d / f"{stem}.ti3")
        # a dated verification's own snapshot: verifications/<date>/chart/
        if (d.name == "chart" and d.parent.parent.name == VERIFICATIONS_DIRNAME
                and d.parents[2].parent.name == RUNS_DIRNAME):
            ti2 = d / f"{stem}.ti2"
            return _Chart(d.parents[2], ti2, True, d.parent / f"{stem}.ti3")
        if d.parent.name == RUNS_DIRNAME:
            return _Chart(d, d / f"{stem}.ti2", False, None)
    except IndexError:
        return None
    return None


def _record_is_for_this_page(rec: dict, tiff: Path) -> bool:
    """A print record describes this page only if the page existed when it
    was printed: a chart generated again since is a new chart."""
    try:
        printed = datetime.fromisoformat(str(rec.get("printed_at") or ""))
        made = datetime.fromtimestamp(tiff.stat().st_mtime)
    except (OSError, ValueError, TypeError):
        return False
    return printed >= made.replace(microsecond=0)


def _stored_colour(run_dir: Path) -> "tuple[str, str]":
    """The verification target's stored Colour and intent, or ``("", "")``."""
    meta = run_dir / "verifications" / "meta.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        ps = data.get("print_settings") or {}
        return str(ps.get("colour") or ""), str(ps.get("intent") or "")
    except (OSError, ValueError, AttributeError):
        return "", ""


def plan_for_page(tiff: "str | Path", *, selected_colour: "str | None" = None,
                  selected_intent: "str | None" = None,
                  bin_dir: "str | Path | None" = None) -> "PreviewPlan | None":
    """How *tiff* is shown, or None when it is not a run's chart page.

    *selected_colour* / *selected_intent*: the Print Chart tab's live Colour
    row, which is what the next print will do; it outranks the print record
    there. Never raises."""
    try:
        return _plan(Path(tiff), selected_colour, selected_intent, bin_dir)
    except Exception:      # noqa: BLE001 — a preview is never worth a crash
        log.debug("print preview plan failed for %s", tiff, exc_info=True)
        return None


def _plan(tiff, selected_colour, selected_intent, bin_dir):
    from core.file_manager import Run
    from workflow import printer_calibration as pc
    from workflow import verification_print as vp
    chart = chart_of_page(tiff)
    if chart is None:
        return None
    run = Run.for_dir(chart.run_dir)
    profile = Path(run.built_profile_icc())
    if not profile.is_file():
        return PreviewPlan(KIND_DEVICE, why=WHY_NO_PROFILE)
    mode = pc.calibration_mode_of(chart.ti2) if chart.ti2.is_file() else pc.MODE_OFF
    if mode in (pc.MODE_APPLY, pc.MODE_OLD_ENGINE_APPLY, pc.MODE_UNKNOWN):
        # The page's pixels carry the printer calibration (printtarg -K):
        # the profile describes the values BEFORE it, so it cannot be applied
        # to these pixels honestly.
        return PreviewPlan(KIND_DEVICE, profile=profile, why=WHY_CALIBRATED)
    if not chart.verification:
        return PreviewPlan(KIND_RAW, profile=profile)

    # A FROM PROFILE GAMUT chart is already in the printer's values and is
    # always printed raw (§3.1a).
    if vp.chart_conversion_state(chart.ti2) != vp.STATE_REGULAR:
        rec = vp.read_print_record(chart.record_from) if chart.record_from else None
        printed = bool(isinstance(rec, dict)
                       and vp.record_answers_how_printed(rec)
                       and _record_is_for_this_page(rec, tiff))
        return PreviewPlan(KIND_RAW, profile=profile, printed=printed)

    colour, intent, source, printed = "", "", "", False
    if selected_colour in (vp.COLOUR_RAW, vp.COLOUR_THROUGH):
        colour, intent = selected_colour, selected_intent or ""
    else:
        rec = vp.read_print_record(chart.record_from) if chart.record_from else None
        if (isinstance(rec, dict) and str(rec.get("printed_at") or "").strip()
                and rec.get("colour") in (vp.COLOUR_RAW, vp.COLOUR_THROUGH)
                and _record_is_for_this_page(rec, tiff)):
            colour, intent = rec["colour"], str(rec.get("intent") or "")
            source = str(rec.get("source_profile") or "")
            printed = True
        else:
            colour, intent = _stored_colour(chart.run_dir)
            if colour not in (vp.COLOUR_RAW, vp.COLOUR_THROUGH):
                colour = vp.default_colour_for_run(run)
    if colour == vp.COLOUR_RAW:
        return PreviewPlan(KIND_RAW, profile=profile, printed=printed)
    if bin_dir is not None:
        source = vp.recorded_source_profile(source, bin_dir)
    return PreviewPlan(KIND_THROUGH, profile=profile,
                       intent=intent or vp.DEFAULT_INTENT,
                       source_profile=source, printed=printed)


def _srgb(bin_dir: Path) -> "Path | None":
    ref = Path(bin_dir).parent / "ref" / "sRGB.icm"
    if ref.is_file():
        return ref
    try:
        from workflow.verification_print import source_profile_path
        p = source_profile_path(bin_dir)
        return Path(p) if p and Path(p).is_file() else None
    except Exception:      # noqa: BLE001
        return None


def _stat_key(path: "Path | str") -> tuple:
    p = Path(path)
    st = p.stat()
    return (str(p), st.st_mtime_ns, st.st_size)


def softproof_page(tiff: "str | Path", plan: PreviewPlan, bin_dir: "str | Path",
                   *, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                   ) -> "Path | None":
    """The page rendered for the screen as it will print, an RGB TIFF, or
    None when it cannot be made (the caller then shows the device values and
    says so). Cached per page, profile and chain; a failure is remembered
    too, so a broken chain is not retried on every repaint. Never raises."""
    global _cache_dir
    if plan.kind not in (KIND_RAW, KIND_THROUGH) or plan.profile is None:
        return None
    tiff, bin_dir = Path(tiff), Path(bin_dir)
    try:
        key = (_stat_key(tiff), _stat_key(plan.profile), plan.kind, plan.intent,
               plan.source_profile, str(bin_dir))
    except OSError:
        return None
    hit = _cache.get(key)
    if hit is not None and hit.is_file():
        return hit
    if key in _failed:
        return None
    from core.proc_text import run_text
    from core.resource_path import argyll_binary
    from workflow.cctiff_apply import convert_args
    from workflow.verification_print import intent_letter
    exe = bin_dir / argyll_binary("cctiff")
    srgb = _srgb(bin_dir)
    if not exe.exists() or srgb is None:
        _failed.add(key)
        return None
    if _cache_dir is None:
        _cache_dir = tempfile.TemporaryDirectory(prefix="chromiq-print-preview-")
    tag = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:12]
    out = Path(_cache_dir.name) / f"{tiff.stem}-{tag}.tif"
    steps: "list[list[str]]" = []
    src = tiff
    if plan.kind == KIND_THROUGH:
        if not plan.source_profile or not Path(plan.source_profile).is_file():
            _failed.add(key)
            return None
        sent = Path(_cache_dir.name) / f"{tiff.stem}-{tag}-sent.tif"
        # exactly the print's own conversion (same arguments, same bit depth)
        steps.append([str(exe), *convert_args(
            Path(plan.source_profile), plan.profile, tiff, sent,
            verbose=False, intent=intent_letter(plan.intent))])
        src = sent
    steps.append([str(exe), "-f", "T", "-i", "r", str(plan.profile),
                  "-i", "r", str(srgb), str(src), str(out)])
    for cmd in steps:
        try:
            r = run_text(cmd, runner=runner, capture_output=True,
                         timeout=_TIMEOUT_S)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("print preview: cctiff did not finish: %s", exc)
            _failed.add(key)
            return None
        if r.returncode != 0:
            log.info("print preview unavailable (cctiff %s): %s", r.returncode,
                     ((r.stderr or "") + (r.stdout or "")).strip()[-200:])
            _failed.add(key)
            return None
    if not out.is_file():
        _failed.add(key)
        return None
    if plan.kind == KIND_THROUGH:
        try:
            Path(src).unlink()
        except OSError:
            pass
    _cache[key] = out
    log.info("print preview: %s shown %s through %s", tiff.name,
             "converted as printed and" if plan.kind == KIND_THROUGH else "raw,",
             plan.profile.name)
    return out


def clear_cache() -> None:
    """Forget every render (tests)."""
    _cache.clear()
    _failed.clear()
