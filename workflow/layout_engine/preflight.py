"""Pre-flight checks — "will this chart read correctly?".

Two layers:

* **Headless checks** (no ArgyllCMS needed), shown in Preferences > Chart
  Layout under the patch count: the patch-size reliability floor and the
  width of the strip letters. These protect Design priority #1.
* An optional **Argyll-backed round-trip** (``fakeread`` → ``colprof``) for
  CI/dev to confirm the ``.ti2`` is structurally sound end to end.

The headless layer is Qt-free and unit-testable; the round-trip is skipped when
the binaries aren't present.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .geometry import Layout
from .instruments import Geom
from core.proc_text import run_text
from core.resource_path import argyll_tool_path

# Smallest reliable patch edge (printtarg enforces 6 mm). A printer/ink-spread
# allowance can raise this per the issue's reliability-floor requirement.
MIN_PATCH_MM = 6.0


@dataclass
class PreflightReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


#: The patch-size error, one full sentence per way the chart's patch size is
#: decided (review 4.3.19 r2, SF-A). Until r2 it always said to choose a
#: larger "Patch scale", which changes nothing with "Prioritise chart area"
#: (`presets.build_kwargs` forces pscale 1.0 there and the row is hidden) or
#: for a patch size typed in (`instruments.build`: patch_w/patch_h replace the
#: scaled size). Each names the control that really makes the patches larger,
#: by the label Preferences > Chart Layout shows for it.
#: Each is one whole literal, so that `scripts/i18n_extract.py` sees it as a
#: key (it reads ``tr(NAME)`` of a module-level string constant).
SMALL_AREA_GRID = (
    "The patches are {size} mm, smaller than the {floor} mm an "
    "instrument needs to read a patch reliably, so it may misread them. "
    "To make them larger, choose fewer “{strips}” or fewer “{rows}”: "
    "each patch then gets more room on the page.")
SMALL_AREA_WIDTH = (
    "The patches are {size} mm, smaller than the {floor} mm an "
    "instrument needs to read a patch reliably, so it may misread them. "
    "To make them larger, choose a larger “{min_width}” or a larger "
    "“{min_height}”.")
SMALL_TYPED = (
    "The patches are {size} mm, smaller than the {floor} mm an "
    "instrument needs to read a patch reliably, so it may misread them. "
    "You typed this patch size in, so “{patch_scale}” does not change "
    "it. To make the patches larger, type a larger “{patch_size}”.")
SMALL_TYPED_AND_SCALE = (
    "The patches are {size} mm, smaller than the {floor} mm an "
    "instrument needs to read a patch reliably, so it may misread them. "
    "To make them larger, type a larger “{patch_size}” for the side you "
    "typed in, and choose a larger “{patch_scale}” for the side you left "
    "empty.")
SMALL_SCALE = (
    "The patches are {size} mm, smaller than the {floor} mm an "
    "instrument needs to read a patch reliably, so it may misread them. "
    "To make them larger, choose a larger “{patch_scale}”.")
#: The full English keys, as the catalogues hold them.
SMALL_PATCH_TEXTS = (SMALL_AREA_GRID, SMALL_AREA_WIDTH, SMALL_TYPED,
                     SMALL_TYPED_AND_SCALE, SMALL_SCALE)


def small_patch_case(recipe, geom: Geom, floor: float) -> str:
    """Which of :data:`SMALL_PATCH_TEXTS` fits how *recipe* sizes its patches
    (the English key).

    *recipe* is a `LayoutRecipe` (or anything with its ``layout_mode``,
    ``area_method``, ``patch_w_mm`` and ``patch_h_mm``); None means the
    instrument's own size times "Patch scale". A typed width sets the strip
    width (``pwid``) and a typed height the length along it (``plen``), as in
    `instruments.build`; a side left empty is the scaled one."""
    if recipe is not None and getattr(recipe, "layout_mode", "") == "area_first":
        if getattr(recipe, "area_method", "by_width") == "by_grid":
            return SMALL_AREA_GRID
        return SMALL_AREA_WIDTH
    typed_w = bool(recipe is not None and getattr(recipe, "patch_w_mm", 0))
    typed_h = bool(recipe is not None and getattr(recipe, "patch_h_mm", 0))
    small = [typed for typed, mm in ((typed_w, geom.pwid), (typed_h, geom.plen))
             if mm < floor - 1e-6]
    if small and all(small):
        return SMALL_TYPED
    if any(small):
        return SMALL_TYPED_AND_SCALE
    return SMALL_SCALE


def _translated_small_patch_text(key: str) -> str:
    """*key* in the person's language, by an explicit ``tr(NAME)`` per text so
    the extractor and the stale-key check see every one."""
    from core.i18n import tr
    if key == SMALL_AREA_GRID:
        return tr(SMALL_AREA_GRID)
    if key == SMALL_AREA_WIDTH:
        return tr(SMALL_AREA_WIDTH)
    if key == SMALL_TYPED:
        return tr(SMALL_TYPED)
    if key == SMALL_TYPED_AND_SCALE:
        return tr(SMALL_TYPED_AND_SCALE)
    return tr(SMALL_SCALE)


def check(geom: Geom, layout: Layout, *,
          min_patch_mm: float = MIN_PATCH_MM, recipe=None) -> PreflightReport:
    """Headless readability checks for a built layout.

    Its one caller in the app is Preferences > Chart Layout, which shows
    ``errors`` and ``warnings`` under the patch count, so they are translated.
    ``info`` is shown nowhere and stays English. *recipe* is the recipe the
    layout was built from; it decides which control the patch-size error
    names (:func:`small_patch_case`).

    THE LOW-CONTRAST WARNING THAT WAS HERE IS GONE (review 4.3.19 r1, N7). It
    took the strips from a ``low_contrast_passes`` argument that no caller in
    the app ever passed, so it could not be shown, and it was English with a
    hand-built plural. The note a person sees is the Create Chart log line
    (`chart_creator._low_contrast_log_line`, from
    `contrast.drawn_low_contrast_passes`)."""
    from core.i18n import tr
    rep = PreflightReport()

    smallest = min(geom.plen, geom.pwid)
    if smallest < min_patch_mm - 1e-6:
        rep.add_error(_translated_small_patch_text(
            small_patch_case(recipe, geom, min_patch_mm)).format(
            size=f"{smallest:.1f}", floor=f"{min_patch_mm:.1f}",
            strips=tr("Strips (columns)"),
            rows=tr("Patches per strip (rows)"),
            min_width=tr("Minimum patch width"),
            min_height=tr("Minimum patch height"),
            patch_size=tr("Patch size"),
            patch_scale=tr("Patch scale")))

    rep.info.append(
        f"{layout.steps_in_pass} patches/pass × {layout.passes} pass(es), "
        f"{layout.total_patches} patches (incl. {layout.padding} padding), "
        f"{layout.pages} page(s)"
    )
    return rep


def indicator_width_warning(geom, dpi: int, *, font: str = "JetBrains Mono",
                            size_mm: float = 0.0, show: bool = True) -> str | None:
    """Warn if a strip indicator could be wider than its strip.

    Measures the widest realistic two-uppercase-letter label (e.g. "WW") in the
    chosen font/size and compares it to the strip (patch) width.  A label wider
    than the strip would overlap neighbouring strips.
    """
    if not show:
        return None
    from . import raster
    mm2px = dpi / 25.4
    eff_mm = raster.effective_indicator_size_mm(geom, dpi, font, size_mm)
    f = raster._font(max(6, round(eff_mm * mm2px)), font)
    try:
        widest_char = max(f.getlength(c) for c in
                          "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    except Exception:
        return None
    pair_mm = (widest_char * 2) / mm2px
    if pair_mm > geom.pwid + 0.1:
        from core.i18n import tr
        return tr("The strip letters may be wider than a strip: two letters "
                  "can take about {pair} mm, and a strip is {strip} mm wide, "
                  "so a two-letter strip name could run into the next strip. "
                  "Choose a smaller size for the strip letters.").format(
                      pair=f"{pair_mm:.1f}", strip=f"{geom.pwid:.1f}")
    return None


# --------------------------------------------------------------------------
# Optional Argyll-backed round-trip (CI / dev)
# --------------------------------------------------------------------------

@dataclass
class RoundTripResult:
    ok: bool
    avg_de: float | None = None
    peak_de: float | None = None
    message: str = ""


def _bin(name: str, argyll_bin: str | None) -> str | None:
    if argyll_bin:
        p = argyll_tool_path(argyll_bin, name)
        return str(p) if p.exists() else None
    return shutil.which(name)


def roundtrip_available(argyll_bin: str | None = None) -> bool:
    return all(_bin(n, argyll_bin) for n in ("fakeread", "colprof"))


def validate_roundtrip(ti2_path: str | Path, profile_icc: str | Path,
                       argyll_bin: str | None = None) -> RoundTripResult:
    """``fakeread`` the ``.ti2`` through *profile_icc* then ``colprof``; report ΔE.

    Confirms the ``.ti2`` is a valid measurement target the toolchain accepts.
    """
    fakeread = _bin("fakeread", argyll_bin)
    colprof = _bin("colprof", argyll_bin)
    if not (fakeread and colprof):
        return RoundTripResult(False, message="ArgyllCMS fakeread/colprof not found")

    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "preflight"
        shutil.copy(ti2_path, stem.with_suffix(".ti2"))
        fr = run_text([fakeread, str(profile_icc), str(stem)],
                      capture_output=True)
        if not stem.with_suffix(".ti3").exists():
            return RoundTripResult(False, message=f"fakeread failed: {fr.stderr.strip()}")
        cp = run_text([colprof, "-v", "-qm", str(stem)],
                      capture_output=True)
        out = cp.stdout + cp.stderr
        m = re.search(r"peak err\s*=\s*([\d.]+),\s*avg err\s*=\s*([\d.]+)", out)
        if not m:
            return RoundTripResult(False, message="colprof produced no error report")
        peak, avg = float(m.group(1)), float(m.group(2))
        return RoundTripResult(True, avg_de=avg, peak_de=peak,
                               message=f"round-trip avg ΔE {avg:.2f}, peak {peak:.2f}")
