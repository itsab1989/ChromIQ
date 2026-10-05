"""``build_profile()`` — the profile engine's front door (issue #122).

Turns a measured chart (``.ti3``) into a complete ICC v2 printer profile:
colorimetric A2B/B2A for any channel count, plus (when a source gamut is
given) distinct perceptual and saturation B2A tables, plus the ``gamt`` tag
ColorSync requires.

Option coverage mirrors colprof's behaviour for OUTPUT-class data, verified
against ``colprof.c`` / ``profout.c`` (ArgyllCMS 3.5.0) and against real
builds:

* table sizes follow ``-q``/``-b`` exactly (profout.c constants);
* ``-a``: output profiles are Lab or XYZ cLUTs — colprof errors on every
  matrix/gamma type for printer data ("Output profile can only be a cLUT
  algorithm") and the engine raises the same error;
* ``-r`` (avgdev) scales the fit smoothing; ``-V`` is a **no-op for output
  profiles in colprof itself** (colprof.c passes literal 1.0) and is
  likewise ignored here;
* ``-u``/``-ua``/``-uc`` error for output data in colprof; ``-u <scale>``
  scales the media white point; ``-R`` clips white Y ≤ 1 and negatives;
* ``-ni``/``-np`` disable the input curves, ``-no`` the output curves,
  ``-nc`` skips the embedded ``.ti3`` (targ/DevD/CIED);
* ``-Z`` sets the header attribute bits / default rendering intent;
* ``-A``/``-M`` become the dmnd/dmdd tags (colprof's device-ID tags).
"""
from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from workflow.profile_engine import b2a as b2a_mod
from workflow.profile_engine import icc_writer as icw
from workflow.profile_engine.forward_model import ForwardModel, fit_forward_model
from workflow.profile_engine.pcs import codec_for
from workflow.profile_engine.ti3_data import Ti3Measurement, read_ti3


class EngineError(RuntimeError):
    """A build failure with a user-facing message."""


# colprof's -q table-size contract (profout.c): quality index 0..3 = l/m/h/u.
_QUALITY_INDEX = {"l": 0, "m": 1, "h": 2, "u": 3}
_A2B_GRID_34 = {0: 5, 1: 9, 2: 17, 3: 23}       # 4+ device channels
_A2B_GRID_23 = {0: 9, 1: 17, 2: 33, 3: 45}      # 2-3 device channels
_A2B_ENTRIES = {0: 512, 1: 1024, 2: 2048, 3: 2048}
_B2A_GRID = {0: 9, 1: 17, 2: 33, 3: 45}
_B2A_ENTRIES = {0: 512, 1: 1024, 2: 2048, 3: 2048}

# Fit regularisation per A2B grid — tuned on the real fixtures so the
# self-fit lands in colprof's own band (~0.1–0.3 ΔE at the patches, i.e. the
# instrument-noise level; fitting tighter than the noise sharpens the inverse
# and blows up B2A round-trip errors — measured: max 11.8 → 2.3 by smoothing
# to parity). Roughly cubic in the grid spacing.
_FIT_LAMBDA_BY_GRID = {5: 0.02, 9: 0.03, 17: 0.04, 23: 0.08, 33: 0.15,
                       45: 0.4}

# ICC header deviceAttributes bits (ICC.1): bit0 transparency, bit1 matte,
# bit2 negative, bit3 black & white. colprof -Z t/m/n/b sets the same bits.
_Z_ATTR_BITS = {"t": 1 << 0, "m": 1 << 1, "n": 1 << 2, "b": 1 << 3}
_Z_INTENT = {"p": 0, "r": 1, "s": 2, "a": 3}

# colprof's own refusal for matrix/gamma types on printer data (colprof.c).
_CLUT_ONLY_MSG = ("Output profile can only be a cLUT algorithm — "
                  "matrix/gamma profile types apply to display and input "
                  "devices (Argyll colprof refuses them for printer "
                  "measurements too).")

# Issue #123 candidate tokens (dark-launched maximum-accuracy successors).
# Unknown tokens in CHROMIQ_ENGINE_NEXT are ignored with a log line.
ENGINE_CANDIDATE_TOKENS = frozenset(
    {"ucs", "joint-sep", "gp", "spectral", "render2", "gpfwd", "b2a33", "b2a33s", "a2bfine", "rgbpos",
     "no-b2a33s", "no-rgbpos", "no-v4prm",
     # Agent 15 (D-14 repair), read only together with "gpfwd":
     "gpwarp", "gpres", "gpclip", "gpsel", "gpkeep", "gplight", "gplight2", "gpdark", "gpsamp",
     # Agent 17 (research/pe-mustfix): column pin; F-09 v4 PRM black
     "a17-colpin", "v4prm",
     # Integration 2: the fin3 GP set as one switch (see GP_FIN3_TOKENS)
     "fin3", "no-fin3"})

# Research integration 1 (2026-10-04, orchestrator after Agent 13's design
# challenge, Validation/agent13-01): Maximum accuracy builds with these two
# of Agent 3's candidates ON by default. "b2a33s" = the B2A table at grid 33
# or finer with the refit samples scaled to it (held up in Agent 13's uneven
# printers, Ghostscript and lcms); "rgbpos" = mirrored ramp positioning
# curves for RGB devices. "no-b2a33s" / "no-rgbpos" switch one off again for
# research ablations. "gpfwd" and "a2bfine" (the GP layer) stay OFF: on
# uneven printers the GP made the B2A worse than b2a33s alone on 6/6
# builds, beyond the ink limit A2B p95 went from 2.4 to 11-25 dE00, and its
# highlight results depended on the chart. Fast and Bit-exact never read
# candidates.
# Integration 2 (D-19, 2026-10-05): "v4prm" ON too: the v4 container's
# perceptual/saturation tables follow ICC.1:2022 Table 16 (F-09); the v2
# file is untouched. "no-v4prm" switches it off for research.
ACCURATE_DEFAULT_TOKENS = frozenset({"b2a33s", "rgbpos", "v4prm"})


# Research integration 2 (2026-10-05): Agent 15's repaired GP layer
# (Findings/agent15-01 s11, "fin3"). It acts ONLY through the gpfwd branch,
# which gp_forward_applies() opens for ink devices of at most
# GP_FORWARD_MAX_INKS (4) inks with >= 75 patches per ink; on RGB and on
# 5+ inks every one of these tokens is inert. "fin3" asks for the whole set,
# "no-fin3" removes it. GP_FIN3_DEFAULT_ON: True since the safety-row
# verification (Validation/fin3-neutral-chroma-10seed.md: 80/80 builds, all
# 60 grey-axis rows TIE over 10 paired seeds, every non-zero difference in
# fin3's favour, no reversal) cleared D-17 2c. Still <= 4 inks only.
GP_FIN3_TOKENS = frozenset({"gpfwd", "gpsel", "gpwarp", "gpclip", "gplight2",
                            "gpdark", "a2bfine", "gpkeep"})
GP_FIN3_DEFAULT_ON = True


def accurate_candidates(tokens) -> frozenset:
    """The candidate set a Maximum accuracy build runs with: the requested
    tokens plus ACCURATE_DEFAULT_TOKENS (plus GP_FIN3_TOKENS when "fin3" is
    asked for or GP_FIN3_DEFAULT_ON), minus every "no-<token>"."""
    tokens = frozenset(tokens or ())
    off = {t[3:] for t in tokens if t.startswith("no-")}
    on = tokens | ACCURATE_DEFAULT_TOKENS
    if ("fin3" in tokens or GP_FIN3_DEFAULT_ON) and "fin3" not in off:
        on = on | GP_FIN3_TOKENS
    return frozenset(t for t in on
                     if not t.startswith("no-") and t != "fin3"
                     and t not in off)


def _process_ink_hues(meas) -> dict:
    """Measured hue of the C, M, Y solids (research token a14-ecgsep)."""
    out = {}
    lab = meas.lab_relative
    for i, letter in enumerate(meas.channel_letters[:3]):
        others = np.delete(meas.device, i, axis=1)
        solid = (meas.device[:, i] >= 0.85) & (others.max(1) <= 0.05)
        if solid.any():
            a, b = lab[solid, 1].mean(), lab[solid, 2].mean()
            out[letter] = float(np.degrees(np.arctan2(b, a)) % 360.0)
    return out or None


def candidates_from_env(env_value: str | None) -> frozenset:
    """Parse ``CHROMIQ_ENGINE_NEXT`` (comma-separated candidate tokens)."""
    if not env_value:
        return frozenset()
    return frozenset(t.strip() for t in env_value.split(",")
                     if t.strip() in ENGINE_CANDIDATE_TOKENS)


# Agent 3's GP forward model ("gpfwd", and "a2bfine", which only acts inside
# its projection) is for ink devices of AT MOST 4 inks (integration 1,
# 2026-10-04). On 5-7 inks it degrades the single-ink ramps (Agent 14
# interim: X5 ramp A2B median 1.2-1.8 dE00 against 0.1-0.4 with the shipped
# forward fit; the battery's multi-ink charts are 71-89 % all-inks-on patches,
# so E1 did not see it), and on 7 inks its 5^7 lattice adds nothing to the
# A2B and hurts the B2A (agent3-01 section 14). 5+ inks keep the shipped
# forward fit; "b2a33s" does not depend on the GP and still applies.
GP_FORWARD_MAX_INKS = 4


def gp_forward_applies(candidates, *, is_additive: bool, n_channels: int,
                       n_patches: int) -> bool:
    """True when the "gpfwd" candidate replaces the forward fit: an ink
    device (not RGB) of at most GP_FORWARD_MAX_INKS inks, with at least 75
    patches per ink."""
    return ("gpfwd" in candidates and not is_additive
            and 0 < n_channels <= GP_FORWARD_MAX_INKS
            and n_patches >= 75 * n_channels)


def _agent15_gp(meas, model, candidates, settings, lam, curve_rounds,
                use_ucs, de_fn):
    """Agent 15 (D-14 repair). "gpwarp" alone: the GP in the stiff fit's
    shaper coordinates. "gpsel": a held-out choice between the stiff fit
    (returns None: the table stays the stiff fit's), the raw GP, the warped
    GP and (with "gpres") a residual GP."""
    from workflow.profile_engine import gpsel
    from workflow.profile_engine.accuracy import fit_forward_model_accurate
    dev, lab, rw = meas.device, meas.lab_relative, meas.row_weights
    if "gpsel" not in candidates:
        return gpsel.fit_kind("warp", dev, lab, model, de_fn, rw)[0]
    # Agent 15 B1: the raw GP is not a contender (the held-out patches
    # cannot see its highlight-neutral failure on charts without light
    # patches, Agent 13 blocker 3); the choice is stiff vs warped GP
    # (+ the residual GP with "gpres").
    kinds = ("warp",) + (("res",) if "gpres" in candidates else ())
    full = {kd: gpsel.fit_kind(kd, dev, lab, model, de_fn, rw)
            for kd in kinds}

    def fit_stiff(d, l, w):
        return fit_forward_model_accurate(
            d, l, grid=model.grid, base_lam=lam, curve_rounds=curve_rounds,
            ucs=use_ucs, row_weights=w, positioning=curve_rounds > 0,
            additive=False)[0]

    winner, rep = gpsel.select(dev, lab, model, fit_stiff, de_fn, rw,
                               kinds=kinds,
                               full_hyper={kd: full[kd][1] for kd in kinds},
                               progress=lambda m: _emit(settings, m))
    parts = []
    for kd in ("stiff",) + kinds:
        r = rep[kd]
        parts.append(f"{kd} {r['mean']:.3f}/{r['p95']:.3f}"
                     + ("" if kd == "stiff" else
                        (" ok" if r["accepted"] else " no")))
    _emit(settings, "Printer model chosen on held-out patches of this chart "
                    f"({rep['n_heldout']} patches, mean/p95 dE00): "
                    + ", ".join(parts) + f" -> {winner}.")
    settings_log = getattr(settings, "_agent15_report", None)
    if isinstance(settings_log, dict):
        settings_log.update(rep)
    return None if winner == "stiff" else full[winner][0]


def _fit_lambda(grid: int) -> float:
    if grid in _FIT_LAMBDA_BY_GRID:
        return _FIT_LAMBDA_BY_GRID[grid]
    return max(0.005, 0.15 * ((grid - 1) / 32.0) ** 3)


@dataclass
class BuildSettings:
    quality: str = "m"                       # colprof -q (l/m/h/u)
    b2a_quality: str = ""                    # colprof -b; "" = same as -q
    algorithm: str = "l"                     # colprof -a: l or x (cLUT only)
    description: str | None = None           # default: the output file stem
    copyright: str = "Created with ChromIQ"
    manufacturer: str = ""                   # colprof -A → dmnd
    model: str = ""                          # colprof -M → dmdd
    ink_limit: float | None = None           # percent; None = from the .ti3
    black_ink_limit: float | None = None     # colprof -L, percent; None = .ti3
    smoothing: float = 0.5                   # colprof -r avgdev (percent)
    curve_rounds: int = 2
    no_input_shaper: bool = False            # colprof -ni / -np
    no_output_shaper: bool = False           # colprof -no
    embed_ti3: bool = True                   # False = colprof -nc
    wp_scale: float | None = None            # colprof -u <scale>
    clip_primaries: bool = False             # colprof -R
    # Black generation (colprof -k/-K): rule "z"/"h"/"x"/"r"/"p"; "" = the
    # default ramp. k_curve_params = (stle, stpo, enpo, enle, shape) for "p".
    # k_locus True = -K (proportion of the possible black range). Ignored
    # for devices without a K channel — exactly like colprof.
    k_rule: str = ""
    k_locus: bool = False
    k_curve_params: tuple | None = None
    z_attributes: str = ""                   # colprof -Z letters (m/t/n/b)
    z_default_intent: str = ""               # colprof -Z p/r/s/a
    # Gamut mapping (colprof -s/-S; ChromIQ passes ClayRGB by default, #121)
    source_gamut: Path | str | None = None
    # colprof -S (True: perceptual AND saturation tables are mapped) vs -s
    # (False: perceptual only; the saturation table aliases it — colprof.html)
    sat_gamut: bool = True
    perc_src_colorimetric: bool = False      # colprof -nP
    sat_src_colorimetric: bool = False       # colprof -nS
    inverse_gamut_a2b: bool = False          # colprof -nI
    perc_intent: str = ""                    # colprof -t
    sat_intent: str = ""                     # colprof -T
    src_viewing: str = ""                    # colprof -c
    dst_viewing: str = ""                    # colprof -d
    # Spectral computation (colprof -i/-o/-f) — needs SPEC_* data in the .ti3
    illuminant: str = ""
    observer: str = ""
    fwa: bool = False
    fwa_illum: str = ""
    # Argyll binaries directory — lets the mapped tables match colprof's
    # rendering exactly via the arm's-length oracle (gamut_map).
    argyll_bin: Path | str | None = None
    timestamp: datetime | None = None        # fixed → byte-reproducible
    progress: Callable[[str], None] | None = None
    # Gamut-mapping engine for the perceptual/saturation B2A tables:
    #   "fast"     — ChromIQ's built-in Python mapper (colprof's algorithm,
    #                validated against Argyll; a few seconds).
    #   "argyll"   — the bundled chromiq-gammap helper running Argyll's REAL
    #                gamut mapper (bit-exact; a little slower). Falls back to
    #                "fast" if the helper binary isn't present.
    #   "accurate" — bit-exact mapping PLUS the maximum-accuracy pipeline:
    #                duplicate-patch white/black averaging, cross-validated
    #                smoothing, outlier-robust fitting, boundary-aware
    #                inversion, measured extra-ink hues, Euclidean ink-limit
    #                projection, hue-preserving clipping and a denser
    #                multi-ink gamut shell. Slower; same option surface.
    gammap_mode: str = "fast"
    # Internal lever for the Python mapper: exact triangle geometry vs the
    # fast sampled-table surfaces. Retained for reference/fallback; not
    # exposed in the UI now that "argyll" is the accurate option.
    gammap_exact_geometry: bool = False
    # Issue #123: candidate improvements to the maximum-accuracy pipeline,
    # dark-launched behind tokens (see ENGINE_CANDIDATE_TOKENS). Hidden —
    # resolved from the CHROMIQ_ENGINE_NEXT environment variable, never
    # from the UI; the empty set is bit-for-bit the shipped accurate mode.
    # Only honoured when gammap_mode == "accurate".
    engine_candidates: frozenset = frozenset()
    # #123 W4, user-facing opt-in (Manual module, accurate mode only):
    # challenge the grid fit with the spectral YNSN physics model. Needs
    # SPEC_* data and an ink-count device; silently a no-op otherwise.
    # Measured on the battery: multi-ink A2B/B2A accuracy improves 20–36%
    # where it applies, at slightly reduced A2B↔B2A self-consistency —
    # hence opt-in rather than default until that tail is closed.
    spectral_physics: bool = False
    # #123 W6: ICC container version, "2" (classic v2.2, maximum
    # compatibility), "4" (v4.4 header, unicode metadata, profile ID) or
    # "both" (v2 to the normal path + a "-v4.icc" twin alongside).
    # The LUTs stay lut16Type — explicitly legal in v4, and the spec keeps
    # the legacy PCS encoding for them, so table bytes are identical.
    icc_version: str = "2"
    # #123 user option (accurate mode): noise-aware fitting behind a
    # held-out exam — the gp pipeline is only used when it clearly beats
    # the standard fit on this chart's held-out patches; otherwise the
    # build is the standard fit. Reporting extras (confidence map) come
    # along either way. Only-win-or-do-nothing by construction.
    noise_model: bool = False
    # #123 W5 user option (accurate mode): out-of-gamut rendering style
    # for the DEFAULT perceptual/saturation intents. "argyll" = matched
    # to ArgyllCMS (battle-tested); "bijective" = ChromIQ's CAM16-UCS
    # radial mapping (exact -nI inverse, much faster; how photos LOOK is
    # a taste question the user judges by printing).
    render_style: str = "argyll"
    # Accurate mode, opt-in: average exactly repeated patches before the fit
    # (each averaged row keeps its repeats' weight). It won on a chart whose
    # every patch was read three times (A-18), but on the synthetic battery,
    # whose charts repeat only white and black, it lost interior accuracy
    # (S2 A2B 0.220 → 0.241) and neutral-K smoothness (S5 0.13 → 0.38 → 0.15
    # weighted) — the robust loop's scale is estimated from fewer, cleaner
    # rows. Off until the battery says otherwise; ChromIQ's own averaging
    # feature (ti3_average) already averages whole reads before the engine.
    average_duplicates: bool = False


@dataclass
class BuildResult:
    icc_path: Path
    n_channels: int
    color_rep: str
    a2b_grid: int
    b2a_grid: int
    fit_median_de: float
    fit_p95_de: float
    b2a_ingamut_median_de: float
    oog_fraction: float
    perceptual_distinct: bool
    model: ForwardModel
    measurement: Ti3Measurement
    # ΔE2000 companions to the ΔE76 fit statistics (perceptually weighted).
    fit_median_de00: float = 0.0
    fit_p95_de00: float = 0.0
    # colprof's own "Profile check complete, peak err = …, avg err = …" pair
    # (ΔE76 max and mean at the patches), so a window that watches for that
    # line — the scanner tool's misalignment check — reads the engine too.
    fit_max_de: float = 0.0
    fit_mean_de: float = 0.0
    # Patch rows flagged as likely misreads (accurate mode; 0-based).
    outlier_rows: tuple = ()


def _emit(settings: BuildSettings, msg: str) -> None:
    if settings.progress is not None:
        settings.progress(msg)


# Ordered build stages → target percentage. Each progress message is matched
# by prefix (messages may carry format args), and the reported percentage
# only ever moves forward, so the number is monotonic even if a stage is
# skipped. Gamut mapping and the saturation table dominate the run time, so
# they get the widest spans. Unmatched messages keep the current percentage.
_STAGE_PCT: list[tuple[str, int]] = [
    ("Reading the measurement", 2),
    ("Computing colorimetry", 4),
    ("Fitting the printer model", 8),
    ("Inverting the model", 14),
    ("Anchoring the rendering", 18),
    ("Writing the profile", 20),
    ("Building the perceptual and saturation", 24),
    ("Gamut mapping: reading the source", 26),
    ("Gamut mapping (bit-exact): reading the source", 26),
    ("Gamut mapping (maximum accuracy): reading the source", 26),
    ("Gamut mapping: measuring the printer", 30),
    ("Gamut mapping (bit-exact): building the destination", 30),
    ("Gamut mapping (maximum accuracy): building the destination", 30),
    ("Gamut mapping (bit-exact): meshing the printer", 30),
    ("Gamut mapping (maximum accuracy): meshing the printer", 30),
    ("Gamut mapping (bit-exact): rendering", 26),
    ("Gamut mapping (maximum accuracy): rendering", 26),
    ("Gamut mapping: preparing colour surfaces", 40),
    ("Gamut mapping: matching source colours", 46),
    ("Gamut mapping: smoothing", 54),
    ("Gamut mapping: fine-tuning", 62),
    # The oracle colprof run is the longest single stage of an accurate
    # ≤4-ink build (~40 of ~55 s on a 924-patch chart) and comes BEFORE the
    # final colour table: it used to be anchored at 78 %, after the table,
    # and sat there with "~20s left" for 45 s (B-08). The list is in time
    # order so sub-step fractions interpolate forwards. The remaining-time
    # estimate still cannot see inside colprof; it says so.
    ("Saturation table: matching colprof", 40),
    ("Saturation table: reusing", 40),
    ("Saturation table: fitting", 70),
    ("Gamut mapping: building the final colour table", 74),
]


class _PercentProgress:
    """Wraps the user's progress callback and prefixes each line with a
    monotonic percentage and, once the pace is readable, an estimated
    remaining time (``"42% · ~3 min left · …"``). The progress bar keeps
    its own pulse.

    Long stages report sub-steps as ``… k/n …`` fractions; those
    interpolate the percentage between the stage's anchor and the next
    one, so the number keeps moving during the minutes-long phases
    instead of sitting on the anchor value.

    The remaining-time estimate is elapsed·(100−p)/p, exponentially
    smoothed so single slow stages don't make it jump around; it only
    appears after 10 % / 3 s (earlier numbers are noise) and is rounded
    to friendly units — an estimate should read like one.
    """

    _FRACTION = re.compile(r"(\d+)\s*/\s*(\d+)")

    def __init__(self, inner, clock=None) -> None:
        import threading
        import time
        # Engine stages may report from pool threads (D-06): one line at a
        # time, so the percentage and the deadline stay consistent.
        self._lock = threading.Lock()
        self._inner = inner
        self._pct = 0.0
        self._clock = clock or time.monotonic
        self._t0 = self._clock()
        self._deadline: float | None = None
        self._paused_at: float | None = None

    def _eta_text(self) -> str:
        """The remaining-time estimate is a DEADLINE that only ever moves
        earlier. elapsed·(100−p)/p re-evaluated on every line grew whenever
        the percentage stalled on a long stage while the clock ran — the
        number went UP between lines (B-08; Basti saw it too). Now lines
        within a stage count down; a new stage may shorten the deadline,
        never lengthen it; and when a stage overruns, the log says so
        instead of printing a bigger number, then re-estimates."""
        now = self._clock()
        if self._paused_at is not None:
            # The colprof stage was not in the budget: the time it took is
            # added to the deadline and taken out of the pace, so the
            # estimate neither drains during it nor counts it afterwards
            # (the challenger's C5: "~20s" at 26 % with 47 s to go, then
            # "taking longer than estimated" on 27 lines).
            gap = now - self._paused_at
            self._paused_at = None
            self._t0 += gap
            if self._deadline is not None:
                self._deadline += gap
        elapsed = now - self._t0
        if self._pct >= 99.0:
            return "almost done"
        if self._pct < 10.0 or elapsed < 3.0:
            return ""
        raw = elapsed * (100.0 - self._pct) / max(self._pct, 1e-6)
        cand = now + raw
        if self._deadline is None or cand < self._deadline:
            self._deadline = cand
        secs = self._deadline - now
        if secs <= 0.0:
            self._deadline = cand
            return "taking longer than estimated"
        if secs < 5.0:
            return "almost done"
        if secs < 90.0:
            return f"~{int(round(secs / 10.0) * 10)}s left"
        return f"~{int(np.ceil(secs / 60.0))} min left"

    def __call__(self, msg: str) -> None:
        with self._lock:
            self._call(msg)

    def _call(self, msg: str) -> None:
        for i, (prefix, pct) in enumerate(_STAGE_PCT):
            if not msg.startswith(prefix):
                continue
            target = float(pct)
            m = self._FRACTION.search(msg[len(prefix):])
            if m and int(m.group(2)) > 0:
                nxt = _STAGE_PCT[i + 1][1] if i + 1 < len(_STAGE_PCT) else 100
                frac = min(int(m.group(1)), int(m.group(2))) / int(m.group(2))
                target = pct + (nxt - pct) * frac
            if target > self._pct:
                self._pct = target
            break
        if self._inner is not None:
            eta = self._eta_text()
            if msg.startswith("Saturation table: matching colprof"):
                eta = "colprof is running, its time is not counted"
                self._paused_at = self._clock()
            head = f"{self._pct:.0f}%" + (f" · {eta}" if eta else "")
            self._inner(f"{head} · {msg}")


def build_profile(ti3_path: Path | str, out_path: Path | str,
                  settings: BuildSettings | None = None) -> BuildResult:
    """Build an ICC printer profile from a measured chart.

    Wraps the build so every progress line is prefixed with a monotonic
    percentage; the original callback is restored afterwards.
    """
    settings = settings or BuildSettings()
    orig_progress = settings.progress
    settings.progress = _PercentProgress(orig_progress)
    started: list = []          # Argyll runs started ahead of need (D-06)
    from workflow.profile_engine import parallel
    scope = parallel.accurate_scope() if settings.gammap_mode == "accurate" \
        else contextlib.nullcontext()
    try:
        with scope:
            return _build_profile_impl(ti3_path, out_path, settings, started)
    finally:
        settings.progress = orig_progress
        for run in started:
            run.close()


def _will_use_colprof_oracle(meas: Ti3Measurement,
                             settings: BuildSettings) -> bool:
    """True when build_mapped_b2a will ask fit_colprof_mappers for the
    perceptual/saturation rendering: Maximum accuracy, a gamut source, a
    device colprof can build (<= 4 channels), Argyll's rendering (not the
    bijective one), and at least one intent that is gamut mapped."""
    from workflow.profile_engine.gamut_map import _COLORIMETRIC_INTENTS
    if settings.gammap_mode != "accurate" or settings.source_gamut is None:
        return False
    if not 0 < meas.n_channels <= 4 or settings.argyll_bin is None:
        return False
    render2 = (("render2" in settings.engine_candidates
                or settings.render_style == "bijective")
               and not settings.perc_intent and not settings.sat_intent)
    if render2:
        return False
    mapped = [settings.perc_intent] + ([settings.sat_intent]
                                       if settings.sat_gamut else [])
    return any(i not in _COLORIMETRIC_INTENTS for i in mapped)


def _build_profile_impl(ti3_path: Path | str, out_path: Path | str,
                        settings: BuildSettings,
                        started: list | None = None) -> BuildResult:
    started = [] if started is None else started
    if settings.quality not in _QUALITY_INDEX:
        raise EngineError(f"Unknown quality {settings.quality!r} "
                          "(expected one of l, m, h, u).")
    if settings.algorithm not in ("l", "x"):
        raise EngineError(_CLUT_ONLY_MSG)
    q = _QUALITY_INDEX[settings.quality]
    qb = _QUALITY_INDEX.get(settings.b2a_quality, q)
    if (settings.gammap_mode == "accurate"
            and ({"b2a33", "b2a33s"}
                 & accurate_candidates(settings.engine_candidates))):
        # Agent 3 candidate: the B2A table resolution, not the inversion,
        # sets most of the B2A error (B1/bh-*: S3 B2A median 0.394 at grid
        # 17 -> 0.171 at grid 33, same build otherwise). At least grid 33.
        qb = max(qb, 2)
    # Accurate mode gets the shadow-resolving shaped XYZ-PCS layout; the
    # parity modes keep colprof's identity layout.
    codec = codec_for(settings.algorithm,
                      accurate=settings.gammap_mode == "accurate",
                      entries=_B2A_ENTRIES[qb])

    _emit(settings, "Reading the measurement…")
    meas = read_ti3(ti3_path)
    n = meas.n_channels
    if not 1 <= n <= 15:
        raise EngineError(f"{n} device channels — outside the ICC range.")
    if n == 1:
        # Not a parity gap: shipping colprof rejects grayscale output data
        # too — its mono support sits behind #ifdef IMP_MONO and is not
        # compiled in ("unhandled color representation", verified live).
        raise EngineError(
            "Single-channel (grayscale) measurements can't be built into a "
            "profile — Argyll colprof doesn't support these either.")

    if settings.illuminant or settings.observer or settings.fwa:
        from workflow.profile_engine.spectral import apply_spectral
        _emit(settings, "Computing colorimetry from the spectral data…")
        apply_spectral(meas, illuminant=settings.illuminant,
                       observer=settings.observer, fwa=settings.fwa,
                       fwa_illum=settings.fwa_illum)

    if settings.clip_primaries:
        # colprof -R: white Y restricted to ≤ 1.0, values clipped positive.
        meas.xyz = np.clip(meas.xyz, 0.0, None)
        _invalidate_bases(meas)
        wy = meas.media_white_xyz[1]
        if wy > 100.0:
            meas.xyz = meas.xyz * (100.0 / wy)
            _invalidate_bases(meas)
    # colprof -u <scale> is applied to the FITTED white below (as xfit.c
    # does), not to one measured row: scaling a single duplicate white
    # patch was then out-voted by its unscaled twins when the white index
    # was recomputed (fast) or averaged away (accurate) — measured 2026-09-04.

    _sanity_gates(meas, settings)
    accurate = settings.gammap_mode == "accurate"
    oracle_run = None
    if _will_use_colprof_oracle(meas, settings):
        # D-06: colprof reads only the .ti3 and the settings, so the oracle
        # starts NOW and runs beside the fit and the inversion instead of
        # after them; build_mapped_b2a collects it. Same bytes either way.
        from workflow.profile_engine.gamut_map import start_colprof_oracle
        oracle_run = start_colprof_oracle(
            meas, settings.source_gamut, settings, settings.argyll_bin,
            codec.node_lab(_B2A_GRID[qb]))
        if oracle_run is not None:
            started.append(oracle_run)
    if accurate and settings.average_duplicates and not settings.noise_model:
        groups, removed = meas.collapse_duplicates()
        if groups:
            _emit(settings, f"Averaged {groups} repeated patch(es) "
                            f"({removed} extra readings) before the fit.")
    # #123 candidates only ever modify the maximum-accuracy pipeline.
    candidates = accurate_candidates(settings.engine_candidates) \
        if accurate else frozenset()
    if accurate:
        # Maximum-accuracy mode: unbiased media white/black from duplicate
        # patches (after the -R/-u mutations above), measured extra-ink hues.
        meas.average_endpoints()
    extra_hues = meas.extra_ink_hues() if accurate else None
    b2a_mod.ECG_SEPARATION["on"] = bool({"a14-ecgsep", "a14-ecgsep2"} & set(candidates))
    b2a_mod.ECG_SEPARATION["sector"] = "a14-ecgsep2" in candidates
    if b2a_mod.ECG_SEPARATION["on"]:
        b2a_mod.ECG_SEPARATION["cmy_hues"] = _process_ink_hues(meas)
    # Measured black L* anchors the GCR locus in accurate mode (shadow-
    # banding fix) and any explicit -k/-K curve (Argyll normalises its
    # inking curve over the profile's own L range); None keeps the parity
    # locus.
    black_l = float(meas.lab_relative[meas.black_index, 0]) \
        if (accurate or settings.k_rule) else None
    k_gen = None
    if settings.k_rule:
        k_gen = {"rule": settings.k_rule,
                 "params": settings.k_curve_params,
                 "locus": settings.k_locus}

    a2b_grid = (_A2B_GRID_34 if n >= 4 else _A2B_GRID_23)[q]
    b2a_grid = _B2A_GRID[qb]
    # Keep very high-dimensional grids inside sane memory: grid**n nodes.
    asked_grid = a2b_grid
    while a2b_grid ** n > 2_000_000 and a2b_grid > 3:
        a2b_grid -= 2
    if a2b_grid != asked_grid:
        # 6 inks: High and Ultra both land on grid 11 (A-21); say so, or the
        # user pays 25 minutes for a quality step that changed nothing.
        _emit(settings, f"Colour table grid reduced from {asked_grid} to "
                        f"{a2b_grid} per axis: {n} ink channels at this "
                        f"quality would need {asked_grid ** n:,} nodes. "
                        f"Higher quality settings give the same table here.")

    _emit(settings, f"Fitting the printer model ({len(meas.device)} patches, "
                    f"grid {a2b_grid})…")
    # colprof -r: reading average deviation (default 0.5%); the smoothing
    # weight scales with its square (rspl semantics — more measurement noise
    # wants proportionally-squared more smoothing).
    lam = _fit_lambda(a2b_grid) * (max(settings.smoothing, 0.01) / 0.5) ** 2
    curve_rounds = 0 if settings.no_input_shaper else settings.curve_rounds
    outliers = np.array([], dtype=int)
    use_ucs = "ucs" in candidates
    if candidates:
        _emit(settings, "Candidate pipeline active: "
                        f"{', '.join(sorted(candidates))}.")
    _noise_winner = None
    if accurate and settings.noise_model and "gp" not in candidates:
        # #123 user option: noise-aware fitting behind a held-out exam —
        # only used when it clearly beats the standard fit on THIS chart
        # (the env token "gp" still forces it, for the benchmark harness).
        from workflow.profile_engine.accuracy import \
            fit_forward_model_accurate_challenged
        model, outliers, _lam_used, _noise_winner = \
            fit_forward_model_accurate_challenged(
                meas.device, meas.lab_relative, grid=a2b_grid,
                base_lam=lam, curve_rounds=curve_rounds, ucs=use_ucs,
                progress=lambda m: _emit(settings, m),
                row_weights=meas.row_weights,
                positioning=not meas.is_additive and curve_rounds > 0)
    elif accurate:
        from workflow.profile_engine.accuracy import fit_forward_model_accurate
        model, outliers, _lam_used = fit_forward_model_accurate(
            meas.device, meas.lab_relative, grid=a2b_grid, base_lam=lam,
            curve_rounds=curve_rounds, ucs=use_ucs,
            gp="gp" in candidates,
            progress=lambda m: _emit(settings, m),
            row_weights=meas.row_weights,
            # Ink devices: shaper curves start from the chart's own
            # single-ink ramps (research agent5-03, item 1 cause D).
            # Agent 3 "rgbpos": the same, mirrored, for RGB devices.
            positioning=((not meas.is_additive or "rgbpos" in candidates)
                         and curve_rounds > 0),
            additive=meas.is_additive)
        if len(outliers):
            # Name the patches the way the SHEET names them (SAMPLE_LOC):
            # "rows 757, 811" only coincided with the printed IDs on a
            # targen chart; on an imported or merged chart a data-row
            # number sends the user to the wrong patch.
            ids = ", ".join(meas.patch_label(int(i)) for i in outliers[:8])
            more = "" if len(outliers) <= 8 else f" (+{len(outliers) - 8})"
            _emit(settings,
                  f"{len(outliers)} patch(es) disagree strongly with the "
                  f"model and were down-weighted — {ids}{more}. "
                  f"Consider remeasuring them.")
    else:
        model = fit_forward_model(meas.device, meas.lab_relative,
                                  grid=a2b_grid, lam=lam,
                                  curve_rounds=curve_rounds)
    # Integration 2: the GP layer (fin3, default for <= 4 inks) follows the
    # forward fit whichever way it was made, unless the noise-aware fit WON
    # on this chart. Before, it sat inside the standard-fit branch, so
    # switching the noise option on silently dropped the GP even where the
    # noise handling stood aside (test_noise_option_stands_aside_on_clean_chart:
    # a clean chart must build identically with and without the option).
    if accurate and _noise_winner != "noise":
        if ("gpfwd" in candidates and not meas.is_additive and n > 4):
            _emit(settings, "Gaussian process forward model: not used for "
                            "5 or more inks (the forward fit is kept).")
        if gp_forward_applies(candidates, is_additive=meas.is_additive,
                              n_channels=n, n_patches=len(meas.device)):
            # Not below 75 patches per ink: at 150 patches on 4 inks the
            # marginal likelihood picks a near-interpolating optimum on 1 of
            # 3 S3 charts (p95 10.9 dE00 vs the grid's 2.4; agent 3, F0g/F0h,
            # development set); at 300 it never did.
            # Agent 3 candidate: GP forward model (ARD Matern 5/2, marginal
            # likelihood, Huber), projected onto the same lattice and curves
            # under the CMMs' kernels. Outlier naming stays the grid fit's.
            from workflow.profile_engine import gpfwd
            from workflow.profile_engine.metrics import delta_e_2000 as _de
            _emit(settings, "Fitting the printer model: Gaussian process…")
            if not ({"gpwarp", "gpsel"} & candidates):
                gpm = gpfwd.fit_gp_forward(meas.device, meas.lab_relative, _de,
                                           row_weights=meas.row_weights,
                                           ref_pred=model.predict(meas.device))
            else:
                gpm = _agent15_gp(meas, model, candidates, settings, lam,
                                  curve_rounds, use_ucs, _de)
            if gpm is not None and "gpclip" in candidates:
                from workflow.profile_engine import gpsel
                gpm = gpsel.Tapered(
                    gpm, model, float(meas.device.sum(1).max()),
                    light=(gpsel.light_scale(meas.device)
                           * (2.0 if "gplight2" in candidates else 1.0)
                           if {"gplight", "gplight2"} & candidates
                           else None),
                    dark=(15.0, 30.0) if "gpdark" in candidates else None)
            # anchor_rel 0.1: every node weakly pulled to the GP's own value
            # there, so the projection has ONE solution the solver reaches
            # (X5: without it 26,374 nodes moved > 1 LSB between solvers,
            # up to 12,200 LSB; with it <= 0.4 LSB; accuracy unchanged,
            # agent 3 P1-projection-stability*.txt).
            if gpm is not None:
                model = gpfwd.project_to_table(
                    gpm, model, lam, fine="a2bfine" in candidates,
                    anchor_rel=0.1, keep_curves="gpkeep" in candidates,
                    shaped_samples="gpsamp" in candidates)
                a2b_grid = model.grid
    if "spectral" in candidates or (accurate and settings.spectral_physics):
        # #123 W4: challenge the grid with the YNSN physics hybrid — the
        # standard model stays unless the physics wins on held-out
        # patches (silently inapplicable without SPEC data / on RGB).
        from workflow.profile_engine.spectral_model import \
            fit_spectral_hybrid
        challenge = fit_spectral_hybrid(
            meas, model, base_lam=lam,
            progress=lambda m: _emit(settings, m))
        if challenge is not None:
            model, verdict = challenge
            _emit(settings, verdict)
        elif settings.spectral_physics:
            # A ticked option that leaves no trace looks broken (B-11).
            why = ("this is an RGB-driver chart (the inks are hidden)"
                   if meas.is_additive else
                   "the chart has no spectral data" if meas.spectral is None
                   else "the chart is too small for a held-out check")
            _emit(settings, f"Spectral physics model: not applicable — {why}. "
                            f"Standard model kept.")
    # THE PAPER WHITE IS PINNED TO THE PCS WHITE. A least-squares surface
    # passes near the white patches, not through them: on a real 924-patch
    # chart the fitted device white came out at L* 99.76 (fast) / 99.94
    # (accurate), so relative-colorimetric B2A sent L*=100 to RGB ≈ 0.996 —
    # ink in every paper-white area of a print. Argyll re-adapts the whole
    # grid so device white lands exactly on D50 (xfit.c, "White point fine
    # tune") and records that FITTED white as the profile's white point;
    # this does the same, and applies -u to that white.
    wtpt_abs = _pin_media_white(model, meas, settings)
    fit_res = np.linalg.norm(model.predict(meas.device) - meas.lab_relative,
                             axis=1)

    _emit(settings, f"Inverting the model (B2A grid {b2a_grid})…")
    user_limit = settings.ink_limit is not None
    ink_limit = settings.ink_limit if user_limit else meas.ink_limit
    if ink_limit is not None and not meas.is_additive:
        # A stamped limit above anything the chart printed sends the
        # inversion 69 % beyond the measured ink range (A-16: 400 % stamped,
        # 280 % printed, B2A asking 349 %). The chart's own maximum is the
        # only ink range the model has seen — so a STAMPED limit is capped
        # there; a limit the user typed is theirs to keep, with the same
        # warning colprof gives (reviewer R8, colprof.c: it warns and keeps
        # the user's value; for a stamp it uses the stamp minus 10 %).
        printed_max = float(meas.device.sum(1).max() * 100.0)
        if ink_limit > printed_max + 0.5:
            if user_limit:
                _emit(settings, f"WARNING: your total ink limit {ink_limit:g}% "
                                f"is above the most ink any chart patch "
                                f"carries ({printed_max:.0f}%) — the model "
                                f"extrapolates beyond what was measured "
                                f"there. Kept as you asked.")
            else:
                _emit(settings, f"Total ink limit {ink_limit:g}% (stamped on "
                                f"the chart) is above the most ink any chart "
                                f"patch carries ({printed_max:.0f}%) — using "
                                f"{printed_max:.0f}%, the range the chart "
                                f"actually measured (colprof would use the "
                                f"stamp minus 10%).")
                ink_limit = printed_max
    # colprof -L / BLACK_INK_LIMIT: a ceiling on the K channel alone. Used
    # to be folded into the TOTAL limit by the extra-options parser (a
    # hand-typed "-L 90" capped all inks at 90 %) — found 2026-09-04.
    channel_max = _channel_ceilings(meas, settings)
    if channel_max is not None:
        k_pct = float(channel_max[meas.channel_letters.index("K")] * 100.0)
        _emit(settings, f"Black ink limited to {k_pct:g}%.")
    # Multi-ink: anchor the neutral rendering + K separation in colprof's
    # behaviour via a synthetic CMYK proxy (colprof can build THAT).
    # D-06 (agent 8): the perceptual/saturation tables need the final model
    # (fixed from here on), the gamut source and the oracle, but neither the
    # colorimetric inversion nor (on the helper / port / oracle paths) the
    # multi-ink anchor. They are built on a background thread beside the
    # anchor and the colorimetric inversion; the anchor reaches the one
    # fallback mapper that reads it through a callable that waits for it.
    # Every table is the same computation as before, so the same bytes.
    mapped_bg = None
    anchor_box: dict = {}
    # Research token "a9-ownmap" (agent9-01, with a9-blackpin) maps onto the
    # colorimetric table's neutral black (axis["black"], device_black), which
    # exists only after the colorimetric inversion below. Started early, the
    # background build would not have it and would quietly recompute or skip
    # it, so with that token the mapped tables are built afterwards, as on
    # the branch where the token was measured (integration 1 decision).
    if (accurate and settings.source_gamut is not None
            and "a9-ownmap" not in candidates):
        import threading
        from workflow.profile_engine import parallel
        if parallel.worker_count() > 1:
            anchor_ready = threading.Event()

            def _anchor_value():
                anchor_ready.wait()
                return anchor_box.get("anchor")

            def _mapped():
                from workflow.profile_engine.gamut_map import build_mapped_b2a
                _emit(settings, "Building the perceptual and saturation "
                                "tables…")
                return build_mapped_b2a(
                    model, meas, b2a_grid, Path(settings.source_gamut),
                    channel_letters=meas.channel_letters,
                    is_additive=meas.is_additive, ink_limit=ink_limit,
                    entries=_B2A_ENTRIES[qb], codec=codec, settings=settings,
                    a2b_grid=a2b_grid, a2b_entries=_A2B_ENTRIES[q],
                    anchor=_anchor_value, channel_max=channel_max,
                    oracle_run=oracle_run)

            mapped_bg = parallel.Background(_mapped)

            class _Release:
                """Build ending early: free the waiting anchor, then join,
                so no engine thread outlives build_profile."""
                def close(self) -> None:
                    anchor_ready.set()
                    mapped_bg.join()
            started.append(_Release())
            anchor_box["ready"] = anchor_ready
    anchor = None
    # Research D-08 item (a), agent9-01 section 2: Maximum accuracy can
    # replace the colprof proxy with the engine's own N-ink rule (tokens
    # "a9-locus": no anchor, the 4-ink accurate rule for every ink count;
    # "a9-kcurve": colprof's K target curve computed by the engine).
    own_rule = accurate and n >= 5 and (
        "a9-locus" in candidates or "a9-kcurve" in candidates)
    if own_rule and "a9-kcurve" in candidates:
        ls = np.linspace(0.0, 100.0, 201)
        params = (settings.k_curve_params if settings.k_rule == "p"
                  and settings.k_curve_params else
                  b2a_mod.K_RULE_PARAMS.get(settings.k_rule or "r",
                                            b2a_mod.K_RULE_PARAMS["r"]))
        anchor = {"l_axis": ls, "k_curve": b2a_mod.argyll_k_curve(
            ls, params=params,
            l_min=max(float(black_l), 2.0) if black_l is not None else 5.0)}
        _emit(settings, "Black generation: the engine's own N-ink rule "
                        "(no colprof proxy).")
    elif own_rule:
        _emit(settings, "Black generation: the engine's own N-ink rule "
                        "(no colprof proxy).")
    if n >= 5 and settings.argyll_bin is not None and not own_rule:
        from workflow.profile_engine.gamut_map import (OracleUnavailable,
                                                       fit_multiink_anchor)
        try:
            anchor = fit_multiink_anchor(
                model, meas, settings.source_gamut or "", settings,
                settings.argyll_bin, settings.progress)
        except OracleUnavailable as exc:
            _emit(settings, f"Using the engine's own rendering ({exc}).")
    if mapped_bg is not None:
        anchor_box["anchor"] = anchor
        anchor_box["ready"].set()
    node_lab = codec.node_lab(b2a_grid)
    # Maximum accuracy separates the COLORIMETRIC table with its own K
    # policy (late GCR locus + the neutral-axis walk), not with the CMYK
    # proxy's colprof K curve: on the battery's 6-7 ink printers that prior
    # made the relative B2A worse on every printer (X5 median 0.958 without
    # it vs 1.366 with it, X7 1.359 vs 1.872, X8 0.822 vs 1.349; research
    # agent5-03 item 5). The proxy anchor still shapes the perceptual and
    # saturation tables (build_mapped_b2a below). Costs ink: section 6.
    k_prior_col = None if accurate else anchor
    if (accurate and not meas.is_additive and n >= 4
            and ("a9-nramp" in candidates or "a9-nramps" in candidates)
            and "K" in meas.channel_letters):
        # Research agent9-01 6.2: colprof's default black rule (-kr ramp,
        # engine port) as the K target for the NEUTRALS only, faded out with
        # chroma; chromatic colours keep the late-GCR locus. The deep neutral
        # black then needs no CMY-for-spot-ink swap at the ink limit (the
        # P7 TV excess), without the proxy's global K prior that cost B2A
        # accuracy (agent5-03 5.3).
        _ls = np.linspace(0.0, 100.0, 201)
        _params = (settings.k_curve_params if settings.k_rule == "p"
                   and settings.k_curve_params else
                   b2a_mod.K_RULE_PARAMS.get(settings.k_rule or "r",
                                             b2a_mod.K_RULE_PARAMS["r"]))
        if "a9-nramps" in candidates and not settings.k_rule:
            # shadow-only ramp: no K above 40 % of the way to the black
            # (light greys stay K-free, as the locus has them), full K at
            # the black (colprof -kp 0 0.4 1 1 1).
            _params = (0.0, 0.4, 1.0, 1.0, 1.0)
        k_prior_col = {"l_axis": _ls, "k_curve": b2a_mod.argyll_k_curve(
            _ls, params=_params,
            l_min=max(float(black_l), 2.0) if black_l is not None else 5.0),
            "neutral_only": True}
    mono_axis = None
    if (accurate and not meas.is_additive and n >= 4
            and "a9-monok" in candidates and "K" in meas.channel_letters):
        # Research agent9-01 6.2: walk the neutral axis first (forward to
        # the neutral black, then back up with no ink allowed to rise and
        # fall), and let its K curve steer the NEUTRAL part of every
        # inversion so the column and its neighbours agree.
        _emit(settings, "Inverting the model: a monotone neutral axis…")
        _ax_kw = dict(channel_letters=meas.channel_letters,
                      is_additive=meas.is_additive, ink_limit=ink_limit,
                      accurate=accurate, extra_hues=extra_hues,
                      black_l=black_l, k_gen=k_gen, ucs=use_ucs,
                      channel_max=channel_max)
        _fwd = b2a_mod.neutral_axis(model, **_ax_kw)
        mono_axis = b2a_mod.monotone_neutral_axis(model, _fwd, **_ax_kw)
        if mono_axis.get("black") is not None:
            ki = meas.channel_letters.index("K")
            _l = np.asarray(mono_axis["l"])[::-1]
            _k = np.asarray(mono_axis["dev"])[::-1, ki].copy()
            _k[_l < mono_axis["l_black"]] = mono_axis["black"][ki]
            k_prior_col = {"l_axis": _l, "k_curve": _k,
                           "neutral_only": True}
    axis = None
    if accurate and not meas.is_additive and n >= 4:
        # The neutral axis solved once by continuation from paper white,
        # put on the B2A neutral column, with everything darker than the
        # neutral black clipped along the axis (research agent5-03 item 5:
        # a neutral black, monotone neutral ramp, for any channel count).
        # Solved BEFORE the per-node inversion (it does not depend on it):
        # when the walk had to be re-routed to reach a deeper neutral black
        # (research agent17-01 item 1, a printer whose dark end lightens),
        # the near-neutral nodes must follow the same K, so the axis's K
        # curve becomes their neutral K prior.
        _emit(settings, "Inverting the model: following the neutral axis…")
        axis = mono_axis if mono_axis is not None else b2a_mod.neutral_axis(
            model, channel_letters=meas.channel_letters,
            is_additive=meas.is_additive, ink_limit=ink_limit,
            k_prior=k_prior_col, accurate=accurate, extra_hues=extra_hues,
            black_l=black_l, k_gen=k_gen, ucs=use_ucs,
            channel_max=channel_max)
        if "a9-monoblack" in candidates:
            axis = b2a_mod.monotone_black(model, axis)
        if axis.get("deep_black") and "K" in meas.channel_letters:
            ki = meas.channel_letters.index("K")
            okx = np.asarray(axis["ok"], bool)
            _l = np.asarray(axis["l"])[okx][::-1]
            _k = np.asarray(axis["dev"])[okx][::-1, ki].copy()
            _d = np.asarray(axis["dev"])[okx][::-1]
            _l = np.concatenate([[0.0], _l])
            _k = np.concatenate([[axis["black"][ki]], _k])
            _d = np.vstack([np.asarray(axis["black"])[None, :], _d])
            k_prior_col = {"l_axis": _l, "k_curve": _k, "dev_curve": _d,
                           "neutral_only": True}
            _emit(settings, f"The deepest neutral black needs black ink "
                            f"earlier (L* {axis['walk_l_black']:.1f} -> "
                            f"{axis['l_black']:.1f}).")
    dev_clut, residual = b2a_mod.build_b2a_clut(
        model, b2a_grid, channel_letters=meas.channel_letters,
        is_additive=meas.is_additive, ink_limit=ink_limit,
        node_lab=node_lab, k_prior=k_prior_col, accurate=accurate,
        extra_hues=extra_hues, black_l=black_l, k_gen=k_gen,
        ucs=use_ucs, channel_max=channel_max,
        progress=lambda m: _emit(settings, m))
    fixed_nodes = None
    if axis is not None:
        fixed_nodes = b2a_mod.apply_neutral_axis(
            dev_clut, node_lab, axis, model,
            channel_letters=meas.channel_letters,
            is_additive=meas.is_additive, ink_limit=ink_limit,
            k_prior=k_prior_col, accurate=accurate, extra_hues=extra_hues,
            black_l=black_l, k_gen=k_gen, ucs=use_ucs,
            channel_max=channel_max)
        if axis.get("l_black") is not None:
            _emit(settings, f"Neutral black under the ink limits: "
                            f"L* {axis['l_black']:.1f}.")
    # refine_b2a_clut returns *curve-space* values — written straight into
    # the CLUT, with the inverse shaper curves as B2A output tables.
    if n > 3 and "joint-sep" in candidates:
        # #123 W2: re-solve the whole separation field as one global
        # optimisation (smoothness in the objective, TAC by projection),
        # warm-started from the per-node result above.
        from workflow.profile_engine.joint_sep import joint_separation
        prior, prior_w = b2a_mod.ink_priors(
            node_lab, n, channel_letters=meas.channel_letters,
            k_prior=k_prior_col, k_gen=k_gen, accurate=accurate,
            extra_hues=extra_hues, black_l=black_l)
        gn_view = None
        if use_ucs:
            from workflow.profile_engine.b2a import _UcsView
            from workflow.profile_engine.ucs import print_ucs
            gn_view = _UcsView(model, print_ucs())
        dev_joint = joint_separation(
            model, node_lab, dev_clut, residual, b2a_grid,
            ink_limit=None if meas.is_additive else ink_limit,
            prior=prior, prior_w=prior_w, gn_model=gn_view,
            progress=lambda m: _emit(settings, m))
        dev_clut_shaped = np.clip(model.shape_device(dev_joint), 0.0, 1.0)
    else:
        dev_clut_shaped = b2a_mod.refine_b2a_clut(
            model, dev_clut, residual, b2a_grid,
            ink_limit=ink_limit, is_additive=meas.is_additive,
            channel_letters=meas.channel_letters,
            node_lab=node_lab, lab_to01=codec.lab_to01, k_prior=k_prior_col,
            accurate=accurate, extra_hues=extra_hues, black_l=black_l,
            k_gen=k_gen, ucs=use_ucs, channel_max=channel_max,
            fixed_nodes=fixed_nodes,
            progress=lambda m: _emit(settings, m),
            # Agent 3 "b2a33s": keep the refit's exact inverse samples per
            # B2A node constant (30,000 were sized for grid 17; at grid 33
            # the n>3 path had 10,000 samples for 35,937 nodes).
            **({"samples": int(30000 * (b2a_grid / 17.0) ** 3)}
               if "b2a33s" in candidates else {}))
    if ("a17-colpin" in candidates and fixed_nodes is not None
            and len(fixed_nodes)):
        # Research agent17-01 section 3 (token, not default): the smoothing
        # refit holds the neutral column only by a weight-4 anchor, and
        # next to the black it gives way: X3, node L* 6.25 moved from the
        # axis's K 0.94 to 0.85 and prints L* 7.5-7.8 instead of 6.25, so
        # every CMM with black point compensation (Ghostscript's default)
        # prints the source black 1.9 L* light. Put the column back exactly.
        dev_clut_shaped = dev_clut_shaped.copy()
        dev_clut_shaped[fixed_nodes] = model.shape_device(
            dev_clut[fixed_nodes])
    if channel_max is not None:
        # The smooth refit is a least-squares field over samples that all
        # respect the ceiling; between them it can overshoot (measured: K
        # 0.65 for a 60 % limit). Nodes are what the CMM interpolates, so a
        # ceiling on the nodes is a ceiling on the table. Curve space here.
        top = model.shape_device(channel_max[None, :])
        dev_clut_shaped = np.minimum(dev_clut_shaped, top)
    # The B2A half of the white pin (see _pin_media_white for the A2B half),
    # and the black corner: L*=0 → the chart's deepest measured black.
    dev_clut_shaped = b2a_mod.pin_white_node(dev_clut_shaped, node_lab,
                                             meas.is_additive)
    if meas.is_additive:
        device_black = np.zeros(n)
    else:
        # Ink devices: the per-node inversion's OWN answer for the black
        # corner respects the ink policy (K locus, TAC, priors); the darkest
        # measured patch is an arbitrary ink mix and made the neutral K
        # curve jump at the bottom (battery S5: TV excess 0.10 → 0.38).
        black_node = int(np.argmin(np.linalg.norm(node_lab, axis=1)))
        device_black = dev_clut[black_node].copy()
    if channel_max is not None:
        device_black = np.minimum(device_black, channel_max)
    dev_clut_shaped = b2a_mod.pin_black_node(
        dev_clut_shaped, node_lab,
        model.shape_device(device_black[None, :])[0])
    in_gamut = residual <= 1.0

    _emit(settings, "Writing the profile…")
    entries_a2b = _A2B_ENTRIES[q]
    entries_b2a = _B2A_ENTRIES[qb]
    a2b = icw.make_mft2(
        n, 3, a2b_grid, codec.encode(model.clut_lab()),
        in_tables=icw.curves_to_tables(model.curves, entries_a2b),
        out_tables=np.tile(icw._identity_table(entries_a2b), (3, 1)))
    # B2A/gamt input tables come from the codec: identity for Lab and the
    # parity XYZ layout, cube-root-shaped for accurate XYZ (the node targets
    # above were laid out through the same codec, so grid and curves agree).
    b2a_in = codec.b2a_in_tables(entries_b2a)
    if settings.no_output_shaper:
        b2a_col = icw.make_mft2(
            3, n, b2a_grid,
            icw.device_to_u16(model.unshape_device(dev_clut_shaped)),
            in_tables=b2a_in,
            out_tables=np.tile(icw._identity_table(entries_b2a), (n, 1)))
    else:
        inv = b2a_mod.inverse_curves(model.curves)
        b2a_col = icw.make_mft2(
            3, n, b2a_grid, icw.device_to_u16(dev_clut_shaped),
            in_tables=b2a_in,
            out_tables=icw.curves_to_tables(inv, entries_b2a))
    # ICC.1 §9.2.29: gamt is 0 for an in-gamut PCS colour. The inversion's
    # clamp distance is a continuous residual (0.3–0.9 ΔE on converged
    # near-boundary nodes) and it leaked onto two thirds of the printable
    # interior (A-08); nodes the build itself calls in-gamut write 0.
    # ICC.1 §9.2.29: gamt is 0 for an in-gamut colour. The table is
    # interpolated across cells 16 ΔE wide (a/b at grid 17), so a node's
    # value leaks into the cell around it: with the raw clamp distance two
    # thirds of the printable interior read non-zero (A-08), and with a
    # 3 ΔE node tolerance a band 5–10 ΔE INSIDE the surface still did
    # (reviewer R10). colprof's tag behaves as if it subtracted a margin of
    # a few ΔE from the distance (86 % zeros 2 ΔE inside, 59 % zeros 2 ΔE
    # outside); a 6 ΔE margin here shrinks the leak to what a soft-proof
    # warning can live with — measured on battery S1 at -qm: printable
    # interior exactly 0 for 86 % (was 32 %), every point 5 ΔE inside the
    # true surface under 1 ΔE, and 96 % of points 5 ΔE outside still
    # non-zero. The distance far outside is understated by the margin.
    # …and the margin fades out again beyond 12 ΔE, so a colour far outside
    # keeps its true distance (a soft-proof reads the magnitude; understating
    # it by 6 was the price of the margin until Basti asked for better).
    knee = np.clip((residual - 6.0) / 6.0, 0.0, 1.0)      # 0 at 6, 1 at 12
    gamt_dist = np.maximum(residual - 6.0 * (1.0 - knee), 0.0)
    gamt = icw.make_mft2(
        3, 1, b2a_grid,
        (np.clip(gamt_dist, 0, 128)[:, None] / 128 * 0xFFFF).round(),
        in_tables=codec.b2a_in_tables(256))

    # The colorimetric tables own the bytes; the other intents alias them
    # (colprof's default A2B0/1/2 are byte-identical — verified) and mapped
    # builds replace the aliases without ever touching the colorimetric data.
    luts: dict[str, bytes | str] = {
        "A2B1": a2b, "A2B0": "A2B1", "A2B2": "A2B1",
        "B2A1": b2a_col, "gamt": gamt,
    }
    perceptual_distinct = False
    if mapped_bg is not None:
        mapped = mapped_bg.result()
        luts.update(mapped)
        perceptual_distinct = "B2A0" in mapped
    elif settings.source_gamut is not None:
        from workflow.profile_engine.gamut_map import build_mapped_b2a
        _emit(settings, "Building the perceptual and saturation tables…")
        mapped = build_mapped_b2a(
            model, meas, b2a_grid, Path(settings.source_gamut),
            channel_letters=meas.channel_letters,
            is_additive=meas.is_additive, ink_limit=ink_limit,
            entries=entries_b2a, codec=codec, settings=settings,
            a2b_grid=a2b_grid, a2b_entries=entries_a2b, anchor=anchor,
            channel_max=channel_max, oracle_run=oracle_run,
            neutral_black_dev=(axis or {}).get("black"),
            black_dev_shaped=model.shape_device(device_black[None, :])[0])
        luts.update(mapped)
        perceptual_distinct = "B2A0" in mapped
    if "B2A0" not in luts:
        luts["B2A0"] = "B2A1"
    if "B2A2" not in luts:
        luts["B2A2"] = "B2A1"

    out = Path(out_path)
    attributes = 0
    for letter in settings.z_attributes:
        attributes |= _Z_ATTR_BITS.get(letter, 0)
    spec = icw.ProfileSpec(
        n_channels=n,
        color_rep=meas.color_rep,
        description=settings.description or out.stem,
        copyright=settings.copyright,
        manufacturer=settings.manufacturer,
        model=settings.model,
        wtpt=tuple(wtpt_abs / 100.0),
        bkpt=tuple(meas.black_xyz / 100.0),
        targ=meas.text if settings.embed_ti3 else None,
        pcs=codec.signature,
        rendering_intent=_Z_INTENT.get(settings.z_default_intent, 1),
        attributes=attributes,
        timestamp=settings.timestamp,
        version=(4, 4) if str(settings.icc_version) == "4" else (2, 2),
    )
    v4_extra, v4_wtpt = _v4_adaptation(meas, settings, wtpt_abs)
    luts_v4 = luts
    if (accurate and "v4prm" in candidates
            and str(settings.icc_version) in ("4", "both")):
        # ICC.1:2022 6.3.4.3 / Table 16: a v4 CMM takes the perceptual (and,
        # in lcms, the saturation) PCS black to be the perceptual reference
        # medium's, so the v4 container's intent 0/2 tables are referred to
        # it; the v2 file keeps its bytes (research agent17-01 item 2, F-09).
        # Maximum accuracy only (D-15): Fast and Bit-exact stay frozen
        # comparison columns, their v4 container keeps the v2 tables.
        # Integration 2: token "v4prm", ON by default (D-19, after
        # Validation/f09-decision.md): ColorSync and Argyll do no PRM black
        # handling and merge the darkest sRGB levels into black, as they do
        # for every X-Rite v4 profile; Mac users are pointed at the v2 file.
        from workflow.profile_engine.v4_prm import v4_luts
        luts_v4 = v4_luts(luts, codec.signature,
                          model.predict(device_black[None, :])[0])
    if str(settings.icc_version) == "4":
        from dataclasses import replace
        spec = replace(spec, wtpt=v4_wtpt)
        icw.write_profile(out, spec, luts_v4, extra_tags=v4_extra)
    else:
        icw.write_profile(out, spec, luts)
    if str(settings.icc_version) == "both":
        # One build, two containers: the main path stays v2 (what the
        # rest of the workflow installs), the v4 twin lands alongside it
        # with a self-explaining name. Same colorimetric LUT bytes in both;
        # the perceptual and saturation tables are PRM-referred in the twin.
        from dataclasses import replace
        twin = out.with_name(out.stem + "-v4.icc")
        # Its own name: two entries called the same thing in a profile
        # menu cannot be told apart (critic N12).
        icw.write_profile(twin, replace(spec, version=(4, 4), wtpt=v4_wtpt,
                                        description=spec.description + " (v4)"),
                          luts_v4, extra_tags=v4_extra)
        _emit(settings, f"Also wrote the ICC v4 twin: {twin.name}")

    gam_res = residual[in_gamut]
    from workflow.profile_engine.metrics import delta_e_2000
    fit_res00 = delta_e_2000(model.predict(meas.device), meas.lab_relative)
    if accurate:
        _emit(settings, f"Model fit (perceptual ΔE2000): median "
                        f"{float(np.median(fit_res00)):.2f}, 95% "
                        f"{float(np.percentile(fit_res00, 95)):.2f}.")
    # A-16: a junk scanner chart built with fit median 5.1 / p95 14.5 and
    # installed like any other. Numbers alone draw no verdict. A chart read
    # by a scanner or camera (no TARGET_INSTRUMENT stamp — scanin writes
    # none) legitimately fits at 2–4 ΔE2000 (reviewer R7), so its bar is 4.
    spectro = bool(meas.keywords.get("TARGET_INSTRUMENT"))
    bar = 2.0 if spectro else 4.0
    if float(np.median(fit_res00)) > bar:
        _emit(settings, "WARNING: the model fits this measurement poorly "
                        f"(median {float(np.median(fit_res00)):.1f} ΔE2000 at "
                        "the patches; a spectrophotometer chart fits under "
                        "1, a scanner- or camera-measured chart under 4). "
                        "The measurement may be damaged, mis-aligned or from "
                        "an instrument that did not read colour — check it "
                        "before trusting this profile.")
    if "gp" in candidates or (accurate and settings.noise_model):
        from workflow.profile_engine.gp import uncertainty_lines
        for line in uncertainty_lines(meas.lab_relative, fit_res00):
            _emit(settings, line)
    return BuildResult(
        icc_path=out, n_channels=n, color_rep=meas.color_rep,
        a2b_grid=a2b_grid, b2a_grid=b2a_grid,
        fit_median_de=float(np.median(fit_res)),
        fit_p95_de=float(np.percentile(fit_res, 95)),
        b2a_ingamut_median_de=float(np.median(gam_res)) if len(gam_res) else 0.0,
        oog_fraction=float(1.0 - in_gamut.mean()),
        perceptual_distinct=perceptual_distinct,
        model=model, measurement=meas,
        fit_median_de00=float(np.median(fit_res00)),
        fit_p95_de00=float(np.percentile(fit_res00, 95)),
        # "peak err" over the patches the model was asked to fit: the robust
        # loop deliberately leaves the misreads it names unfitted, and their
        # residual doubled the peak the scanner tool judges (reviewer R13).
        fit_max_de=float(np.delete(fit_res, outliers).max()
                         if len(outliers) < len(fit_res) else fit_res.max()),
        fit_mean_de=float(np.delete(fit_res, outliers).mean()
                          if len(outliers) < len(fit_res) else fit_res.mean()),
        outlier_rows=tuple(int(i) for i in outliers))


def _sanity_gates(meas: Ti3Measurement, settings: BuildSettings) -> None:
    """Refuse a measurement that cannot describe a printer.

    A stuck-instrument chart (every patch ≈ the same colour) built in 1.4 s
    with "fit median 0.03" and a profile that mapped every colour to paper
    white (A-16). The lightness range between the chart's white and its
    darkest patch is the one number no printer chart can fake."""
    lab = meas.lab_relative
    span = float(lab[meas.white_index, 0] - lab[meas.black_index, 0])
    if span < 10.0:
        raise EngineError(
            f"This measurement cannot describe a printer: its brightest and "
            f"darkest patches are only {span:.1f} L* apart (a printed chart "
            f"spans 70 or more). The instrument may have been stuck or "
            f"mis-aimed, or the wrong file was chosen — re-measure the chart "
            f"before building a profile.")


def _v4_adaptation(meas: Ti3Measurement, settings: BuildSettings,
                   wtpt_abs: np.ndarray):
    """ICC v4 needs ``chad`` and a D50-adapted ``wtpt`` when the measurement
    was computed for an illuminant other than D50 (ICC.1 §8.2, §9.2.36).
    Returns ``(extra_tags, wtpt_v4)``; the v2 file keeps colprof's raw
    illuminant-relative white (parity), the v4 file gets the adapted one."""
    illum = (settings.illuminant or "D50").upper().replace("M2", "")
    if illum == "D50" or meas.wavelengths is None:
        return [], tuple(wtpt_abs / 100.0)
    from workflow.profile_engine.icc_writer import BRADFORD, make_sf32
    from workflow.profile_engine.spectral import spectra_to_xyz
    from workflow.profile_engine.ti3_data import D50_XYZ100
    ill = spectra_to_xyz(np.ones((1, len(meas.wavelengths))),
                         meas.wavelengths,
                         illuminant=settings.illuminant)[0]
    cone_ill = BRADFORD @ (ill / 100.0)
    cone_d50 = BRADFORD @ (D50_XYZ100 / 100.0)
    m = np.linalg.inv(BRADFORD) @ np.diag(cone_d50 / cone_ill) @ BRADFORD
    return [(b"chad", make_sf32(m))], tuple((m @ wtpt_abs) / 100.0)


def _channel_ceilings(meas: Ti3Measurement,
                      settings: BuildSettings) -> np.ndarray | None:
    """Per-channel device ceilings for the inversion: 1.0 everywhere except
    a K channel under a black ink limit (settings -L, else the chart's
    BLACK_INK_LIMIT). None when no limit applies — additive devices, no K,
    or a limit ≥ 100 %."""
    if meas.is_additive or "K" not in meas.channel_letters:
        return None
    limit = settings.black_ink_limit
    if limit is None:
        limit = meas.black_ink_limit
    if limit is None or not (0.0 < limit < 100.0):
        return None
    top = np.ones(meas.n_channels)
    top[meas.channel_letters.index("K")] = limit / 100.0
    return top


def _pin_media_white(model: ForwardModel, meas: Ti3Measurement,
                     settings: BuildSettings) -> np.ndarray:
    """Re-adapt the fitted grid so device white maps exactly to D50, and
    return the profile's absolute media white (Y=100 scale).

    Argyll's ``xfit.c`` (XFIT_OUT_WP_REL) looks the device white up through
    the fitted model and re-adapts the WHOLE grid so it lands on D50. That
    global move costs interior accuracy by the white-fit error — measured on
    the synthetic battery: A2B median S2 0.241 → 0.318, S3 0.238 → 0.319 —
    so here the correction is LOCAL: the fitted white's error is added in
    full at the white corner and fades out below L* 60 and beyond chroma
    40, leaving the interior exactly as fitted. Device white sits on a grid
    CORNER (the shaper curves are pinned at 0 and 1), so that node becomes
    (100, 0, 0) exactly and the relative tables agree with the white-point
    tag, which is the fitted white expressed back in the measured basis.
    ``wp_scale`` (xfit semantics: grid ×1/scale, white ×scale) stays a global
    operation — colprof refuses it on printer data and the tab cannot reach
    it; kept for an input-class future.
    """
    from workflow.profile_engine.icc_writer import BRADFORD
    from workflow.profile_engine.ti3_data import (D50_XYZ100, lab_to_xyz,
                                                   xyz_to_lab)
    dev_white = np.full((1, meas.n_channels),
                        1.0 if meas.is_additive else 0.0)
    lab_w = model.predict(dev_white)
    xyz_w = lab_to_xyz(lab_w)[0]                      # D50-relative, Y≈100
    if not np.all(np.isfinite(xyz_w)) or xyz_w[1] <= 1.0:
        _emit(settings, "Paper white could not be anchored (the model's "
                        "white is not a usable colour); leaving the tables "
                        "unadapted.")
        return meas.media_white_xyz.copy()
    # Absolute white = the fitted white in the measured basis (before the
    # correction, so the absolute response of the profile is unchanged).
    wtpt_abs = meas.relative_to_absolute_xyz(xyz_w)[0]
    delta = np.array([100.0, 0.0, 0.0]) - lab_w[0]
    nodes = model.nodes
    l_w = np.clip((nodes[:, 0] - 60.0) / 40.0, 0.0, 1.0) ** 2
    c_w = np.clip(1.0 - np.hypot(nodes[:, 1], nodes[:, 2]) / 40.0, 0.0, 1.0)
    model.nodes = nodes + delta[None, :] * (l_w * c_w)[:, None]
    # The weights above are evaluated at each node's own fitted Lab, so the
    # corner's weight is ((L_w−60)/40)² < 1 and the pin fell short by
    # δ·(1−w) — 97.7 instead of 100 on a heavily smoothed matte chart
    # (reviewer R1). Device white IS the corner node: set it exactly.
    n_ch = meas.n_channels
    corner = np.ravel_multi_index(
        tuple([model.grid - 1 if meas.is_additive else 0] * n_ch),
        (model.grid,) * n_ch)
    model.nodes[corner] = np.array([100.0, 0.0, 0.0])
    scale = float(settings.wp_scale) if settings.wp_scale else 1.0
    if scale <= 0.0:
        scale = 1.0
    if scale != 1.0:
        model.nodes = xyz_to_lab(lab_to_xyz(model.nodes) / scale)
    wtpt_abs = wtpt_abs * scale
    corner = model.predict(dev_white)[0]
    _emit(settings, f"Paper white anchored: the model's white read L* "
                    f"{lab_w[0, 0]:.2f}, now {corner[0]:.2f} — the profile's "
                    f"white point is the fitted paper (Y {wtpt_abs[1]:.2f})"
                    + (f", scaled by {scale:g}." if scale != 1.0 else "."))
    return wtpt_abs


def _invalidate_bases(meas: Ti3Measurement) -> None:
    """Drop the cached colour bases after mutating ``meas.xyz``."""
    for attr in ("xyz_relative", "lab_relative", "lab_absolute",
                 "media_white_xyz", "white_index", "black_index",
                 "black_xyz"):
        meas.__dict__.pop(attr, None)
