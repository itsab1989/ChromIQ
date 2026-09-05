"""Qt adapter for the ChromIQ profile engine (#122) — Build-Profile side.

Wraps :func:`workflow.profile_engine.build_profile` in a ``QThread`` with the
same call surface the colprof :class:`~workflow.profile_builder.ProfileBuilder`
offers (``build(params, on_line, on_finish)`` + ``expected_icc_path``), so
``tab_profile`` can route a build to either engine without special-casing the
UI flow. The engine runs in-process — the worker thread keeps the UI alive
during the numeric fit.

Coverage: the engine handles **every build the Build-Profile tab can
request** — every option maps onto the engine's implementation, and options
that are *errors* in colprof for printer measurements (matrix profile
types, the input-profile white-point modes) produce the same errors here.
Only two things still route to colprof, both named in the log: a hand-typed
extra command-line flag the parser doesn't know, and a gamut-source file
that can't be read as an RGB/CMYK profile.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QThread, pyqtSignal

from core.i18n import tr
from core.logger import get_logger
from core.text_io import read_text
from workflow.profile_engine import BuildSettings

if TYPE_CHECKING:
    from workflow.profile_builder import ProfileParams

log = get_logger(__name__)

# Device representations colprof itself accepts (profout.c) — everything
# else (CMYKOG, CMYKcm, …) is engine-only territory.
_COLPROF_REPS = {"RGB", "iRGB", "CMYK", "CMY", "K", "W", "GRAY"}


def ti3_device_rep(ti3_path: Path | str) -> str:
    """The device part of the file's COLOR_REP (``""`` when unreadable)."""
    try:
        head = read_text(Path(ti3_path), lenient=True)[:8000]
    except OSError:
        return ""
    m = re.search(r'^COLOR_REP\s+"([^"]+)"', head, re.M)
    return m.group(1).split("_")[0] if m else ""


def is_multi_ink(ti3_path: Path | str) -> bool:
    rep = ti3_device_rep(ti3_path)
    return bool(rep) and rep not in _COLPROF_REPS


# colprof's own errors for input-profile options on output data (colprof.c).
_WP_MODE_ERRORS = {
    "u": "Input auto WP scale mode isn't applicable to an output device",
    "ua": "Force absolute colorimetric isn't applicable to an output device",
    "uc": "Input cLUT clipping above WP mode isn't applicable to an output "
          "device",
}


class ExtraArgsError(ValueError):
    """An extra command-line flag the engine parser doesn't know."""


def _apply_extra_args(extra: str, s: BuildSettings) -> None:
    """Fold hand-typed colprof flags into the BuildSettings.

    Every documented colprof flag the Build tab could also set through its
    widgets is accepted; anything unknown raises — the caller then routes
    that build through colprof itself, naming the flag.
    """
    toks = shlex.split(extra)
    i = 0

    def val(tok: str, prefix: str) -> str:
        nonlocal i
        if len(tok) > len(prefix):
            return tok[len(prefix):]
        i += 1
        if i >= len(toks):
            raise ExtraArgsError(tok)
        return toks[i]

    while i < len(toks):
        t = toks[i]
        if t == "-v":
            pass
        elif t.startswith("-l"):
            s.ink_limit = float(val(t, "-l"))
        elif t.startswith("-L"):
            # colprof: -L klimit = BLACK ink limit (0-100 %), not the total.
            s.black_ink_limit = float(val(t, "-L"))
        elif t.startswith("-r"):
            s.smoothing = float(val(t, "-r"))
        elif t.startswith("-V"):
            val(t, "-V")                    # no-op for output class (source)
        elif t.startswith("-q"):
            s.quality = val(t, "-q")
        elif t.startswith("-b"):
            if len(t) > 2:
                s.b2a_quality = t[2:]
            elif i + 1 < len(toks) and toks[i + 1] in tuple("lmhunfsLMHUN"):
                i += 1
                s.b2a_quality = toks[i]
            else:
                s.b2a_quality = "l"         # bare -b = low (colprof.c)
        elif t.startswith("-a"):
            s.algorithm = val(t, "-a")
        elif t.startswith("-k") or t.startswith("-K"):
            s.k_locus = t.startswith("-K")
            rule = val(t, t[:2])
            if rule not in ("z", "h", "x", "r", "p"):
                raise ExtraArgsError(t)
            s.k_rule = rule
            if rule == "p":            # five curve values follow
                if i + 5 >= len(toks):
                    raise ExtraArgsError(t)
                try:
                    s.k_curve_params = tuple(
                        float(toks[i + j]) for j in range(1, 6))
                except ValueError as exc:
                    raise ExtraArgsError(t) from exc
                i += 5
        elif t == "-ni" or t == "-np":
            s.no_input_shaper = True
        elif t == "-no":
            s.no_output_shaper = True
        elif t == "-nc":
            s.embed_ti3 = False
        elif t == "-nP":
            s.perc_src_colorimetric = True
        elif t == "-nS":
            s.sat_src_colorimetric = True
        elif t == "-nI":
            s.inverse_gamut_a2b = True
        elif t.startswith("-i"):
            s.illuminant = val(t, "-i")
        elif t.startswith("-o"):
            s.observer = val(t, "-o")
        elif t.startswith("-f"):
            s.fwa = True
            if len(t) > 2:
                s.fwa_illum = t[2:]
        elif t.startswith("-c"):
            s.src_viewing = val(t, "-c")
        elif t.startswith("-d"):
            s.dst_viewing = val(t, "-d")
        elif t.startswith("-t"):
            s.perc_intent = val(t, "-t")
        elif t.startswith("-T"):
            s.sat_intent = val(t, "-T")
        elif t.startswith("-Z"):
            z = val(t, "-Z")
            if z in ("p", "r", "s", "a"):
                s.z_default_intent = z
            else:
                s.z_attributes += z
        elif t.startswith("-A"):
            s.manufacturer = val(t, "-A")
        elif t.startswith("-M"):
            s.model = val(t, "-M")
        elif t.startswith("-C"):
            s.copyright = val(t, "-C")
        elif t.startswith("-D"):
            s.description = val(t, "-D")
        elif t.startswith("-s") or t.startswith("-S"):
            s.sat_gamut = t.startswith("-S")
            s.source_gamut = val(t, t[:2])
        elif t == "-R":
            s.clip_primaries = True
        elif t.startswith("-u"):
            # colprof 3.5.0 refuses every -u form on printer data
            # ("Input auto WP scale mode isn't applicable to an output
            # device" — run 2026-09-04 with -u 1.1 and -u1.1); the engine
            # gives the same answer instead of quietly scaling the white.
            raise ValueError(_WP_MODE_ERRORS["u"])
        else:
            raise ExtraArgsError(t)
        i += 1


def settings_from_params(params: "ProfileParams") -> BuildSettings:
    """Map the tab's ProfileParams onto engine BuildSettings (full surface).

    Raises :class:`ExtraArgsError` for unknown extra flags and
    :class:`workflow.profile_engine.EngineError`-style ValueError for
    combinations colprof itself refuses on printer data — the caller shows
    those as build errors, exactly like a colprof run would.
    """
    if params.wp_mode in _WP_MODE_ERRORS:
        raise ValueError(_WP_MODE_ERRORS[params.wp_mode])
    _ = params.dark_emphasis   # -V: no-op for output-class data — colprof
    #                            itself passes literal 1.0 (colprof.c)
    s = BuildSettings(
        quality=params.quality or "m",
        b2a_quality=params.b2a_quality or "",
        algorithm=params.algorithm or "l",
        description=params.description or None,
        copyright=params.copyright or "Created with ChromIQ",
        manufacturer=params.manufacturer or "ChromIQ",
        model=params.model or params.description or "",
        smoothing=params.smoothing,
        no_input_shaper=params.no_input_shaper or params.no_grid_pos,
        no_output_shaper=params.no_output_shaper,
        embed_ti3=not params.no_embedded_data,
        clip_primaries=params.clip_primaries,
        wp_scale=(params.wp_scale
                  if params.wp_mode == "scale" and params.wp_scale > 0
                  else None),
        k_rule=params.k_rule,
        k_locus=params.k_locus,
        k_curve_params=((params.k_stle, params.k_stpo, params.k_enpo,
                         params.k_enle, params.k_shape)
                        if params.k_rule == "p" else None),
        spectral_physics=params.spectral_physics,
        icc_version=params.icc_version or "2",
        noise_model=params.noise_model,
        render_style=params.render_style or "argyll",
        z_attributes="".join(filter(None, [
            params.z_surface, params.z_media_type, params.z_polarity,
            params.z_color_mode])),
        z_default_intent=params.z_default_intent,
        source_gamut=params.gamut_src or params.gamut_sat_src or None,
        sat_gamut=bool(params.gamut_sat_src),      # -S; -s = perceptual only
        perc_src_colorimetric=params.no_perc_gamut,
        sat_src_colorimetric=params.no_sat_gamut,
        inverse_gamut_a2b=params.inv_gamut_map,
        perc_intent=params.perc_intent,
        sat_intent=params.sat_intent,
        src_viewing=params.src_viewing_cond,
        dst_viewing=params.dst_viewing_cond,
        illuminant=params.illuminant,
        observer=params.observer,
        fwa=params.fwa_enabled,
        fwa_illum=params.fwa_illum,
    )
    if params.extra_args.strip():
        _apply_extra_args(params.extra_args, s)
    return s


def accuracy_mode_label(gammap_mode: str) -> str:
    """The Preferences → Beta → Accuracy wording for a mode token, so every
    window that names the builder names the mode too (B-06)."""
    return {"accurate": tr("Maximum accuracy"), "argyll": tr("Bit-exact"),
            }.get(str(gammap_mode), tr("Fast"))


def choose_builder(settings, params: "ProfileParams") -> tuple[str, str]:
    """Which builder a window should use for ``params`` under the current
    Preferences: ``("engine", "")`` or ``("colprof", why)``.

    The same decision the Build Profile tab makes (`_resolve_engine`), for
    any window that builds a printer profile — the scanner/camera tool used
    to ignore the Beta switch entirely and always ran colprof (B-26):
    multi-ink → engine; beta off → colprof; Bit-exact on ≤ 4 inks → colprof
    itself (identical to Argyll); Fast/Maximum accuracy → the engine unless
    :func:`engine_support` names something only colprof has.
    """
    beta = bool(settings.get("profile_engine_beta", False))
    if is_multi_ink(params.ti3_path):
        return ("engine", "") if beta else ("colprof", tr(
            "the ChromIQ profile engine is switched off"))
    if not beta:
        return "colprof", ""
    if str(settings.get("gammap_mode", "fast")) == "argyll":
        return "colprof", tr("Bit-exact on a standard (≤4-ink) measurement "
                             "is Argyll colprof itself")
    ok, why = engine_support(params)
    return ("engine", "") if ok else ("colprof", why)


def engine_support(params: "ProfileParams") -> tuple[bool, str]:
    """Can the engine run this exact build?

    Returns ``(supported, reason)``. After the full-coverage round only two
    cases still route to colprof: an unknown hand-typed extra flag, and a
    gamut-source profile the live sampler can't read. Everything else either
    runs on the engine or fails with the same error colprof gives.
    """
    try:
        s = settings_from_params(params)
    except ExtraArgsError as exc:
        return False, tr(
            "the extra colprof option {flag}").format(flag=exc)
    except ValueError:
        return True, ""      # colprof-identical error — engine handles it
    gamut_source = s.source_gamut
    if gamut_source:
        from workflow.profile_engine.gamut_map import (
            GamutSourceError, source_surface_from_profile)
        try:
            source_surface_from_profile(gamut_source, mesh=5)
        except GamutSourceError as exc:
            return False, tr(
                "this gamut source profile ({reason})").format(reason=exc)
    return True, ""


class _EngineThread(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(int, str)

    def __init__(self, ti3_path: Path, out_path: Path, settings, parent=None):
        super().__init__(parent)
        self._ti3 = ti3_path
        self._out = out_path
        self._settings = settings

    def run(self) -> None:  # noqa: D102 — QThread worker
        from workflow.profile_engine import build_profile
        self._settings.progress = self.line.emit   # queued across threads
        try:
            res = build_profile(self._ti3, self._out, self._settings)
        except Exception as exc:            # noqa: BLE001 — surfaced to UI
            log.exception("engine build failed")
            self.done.emit(1, str(exc))
            return
        self.line.emit(tr(
            "Model fit at the measured patches: median {med:.2f} ΔE, "
            "95% {p95:.2f} ΔE.").format(med=res.fit_median_de,
                                        p95=res.fit_p95_de))
        # colprof's fit-check line, verbatim in shape: the scanner tool's
        # misalignment verdict (#108) is built on it, and it now builds
        # printer profiles through this engine as well.
        self.line.emit(f"Profile check complete, peak err = "
                       f"{res.fit_max_de:.6f}, avg err = "
                       f"{res.fit_mean_de:.6f}")
        if res.perceptual_distinct:
            self.line.emit(tr(
                "Perceptual and saturation tables built from the gamut "
                "source."))
        self.done.emit(0, "")


class EngineProfileBuilder:
    """ProfileBuilder-compatible front end for the in-process engine."""

    def __init__(self, settings=None) -> None:
        self._thread: _EngineThread | None = None
        self._last_error: str = ""
        self._app_settings = settings

    @property
    def is_running(self) -> bool:
        t = self._thread
        if t is None:
            return False
        try:
            return t.isRunning()
        except RuntimeError:      # C++ side already deleted (deleteLater)
            self._thread = None
            return False

    def expected_icc_path(self, params: "ProfileParams") -> Path:
        base = params.ti3_path
        return base.with_suffix(".icc")

    def build(self, params: "ProfileParams",
              on_line: Callable[[str], None],
              on_finish: Callable[[int], None]) -> None:
        try:
            settings = settings_from_params(params)
            if self._app_settings is not None:
                settings.argyll_bin = self._app_settings.get(
                    "argyll_bin_path", "/Applications/Argyll/bin")
                settings.gammap_mode = str(
                    self._app_settings.get("gammap_mode", "fast"))
            if settings.gammap_mode == "accurate":
                # #123: dark-launched candidate pipeline, env-only.
                import os
                from workflow.profile_engine.builder import \
                    candidates_from_env
                settings.engine_candidates = candidates_from_env(
                    os.environ.get("CHROMIQ_ENGINE_NEXT"))
                if settings.engine_candidates:
                    on_line(tr("Engine candidates active: {names}").format(
                        names=", ".join(sorted(settings.engine_candidates))))
        except (ExtraArgsError, ValueError) as exc:
            self._last_error = str(exc)
            on_line(tr("[ERROR] {msg}").format(msg=exc))
            on_finish(1)
            return
        out = self.expected_icc_path(params)
        self._last_error = ""
        self._thread = t = _EngineThread(params.ti3_path, out, settings)
        t.line.connect(on_line)

        def _finished(code: int, err: str) -> None:
            self._last_error = err
            if err:
                on_line(tr("[ERROR] {msg}").format(msg=err))
            on_finish(code)

        def _released() -> None:
            """Drop our reference only once the thread has really stopped."""
            self._thread = None

        t.done.connect(_finished)
        # ``done`` is emitted from inside the thread's run(), so the QThread is
        # still running when _finished executes. Clearing self._thread there
        # dropped the last Python reference to a LIVE QThread, and if the
        # garbage collector reclaimed it before the thread stopped, Qt aborted
        # the process — an intermittent hard crash that took out a release gate
        # twice, and could equally have killed the app at the end of a real
        # profile build. The reference is released on ``finished`` instead,
        # which Qt emits after run() has returned.
        t.finished.connect(_released)
        t.finished.connect(t.deleteLater)
        on_line(tr("Building with the ChromIQ profile engine (beta) — "
                   "{mode}…").format(mode=accuracy_mode_label(
                       settings.gammap_mode)))
        t.start()

    # ProfileBuilder-parity helpers the finish path may consult ------------
    def primary_failure(self) -> tuple[str, str] | None:
        return ("engine", self._last_error) if self._last_error else None

    def last_output(self) -> str:
        """What the colprof builder returns as the tool's raw output; the
        engine has no separate stream, so its last error stands in."""
        return self._last_error

    def captured_warnings(self) -> list[tuple[str, str]]:
        return []
