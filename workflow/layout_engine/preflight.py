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


def check(geom: Geom, layout: Layout, *,
          min_patch_mm: float = MIN_PATCH_MM) -> PreflightReport:
    """Headless readability checks for a built layout.

    Its one caller in the app is Preferences > Chart Layout, which shows
    ``errors`` and ``warnings`` under the patch count, so they are translated.
    ``info`` is shown nowhere and stays English.

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
        rep.add_error(tr(
            "The patches are {size} mm, smaller than the {floor} mm an "
            "instrument needs to read a patch reliably, so it may misread "
            "them. Choose a larger “{patch_scale}”, or a larger paper or "
            "instrument.").format(
                size=f"{smallest:.1f}", floor=f"{min_patch_mm:.1f}",
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
