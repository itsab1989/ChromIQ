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

THE APP SHAPE (2026-11-10). The engine is ONE switch in Preferences > Beta
(``profile_engine_beta``), off by default. Off is stock colprof. On is the
engine's Maximum accuracy build, always: the Fast / Bit-exact / Maximum
accuracy picker is gone, and this module is the only place that says
``gammap_mode = "accurate"`` for the app. Around the build it also

* ignores the engine's development variables in a packaged app
  (``core/engine_env.py``),
* stops the build when ArgyllCMS colprof cannot give the engine its
  reference rendering, so the caller can build with colprof instead
  (:class:`ColprofReferenceFailed`); the engine's own untuned rendering is
  never used silently,
* keeps the engine's internal switch names out of the window's log while
  recording them for ``chromiq.log`` and the run's ``meta.json``
  (:class:`EngineLines`).
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

#: The one engine mode the app builds with (D-27).
ENGINE_MODE = "accurate"

#: Preferences > Beta, the black option: stored value -> BuildSettings value.
BLACK_DEPTHS = ("neutral", "deepest")


def engine_switch_on(settings) -> bool:
    """Preferences > Beta: is the new profile engine switched on?"""
    try:
        return bool(settings.get("profile_engine_beta", False))
    except Exception:      # noqa: BLE001 - an unreadable store is "off"
        return False


def colprof_comparison_setting(settings) -> bool:
    """Preferences > Beta, the option under the switch, as stored: on by
    default, and an unreadable or unknown value reads as the default."""
    try:
        raw = settings.get("profile_engine_colprof_comparison", True)
    except Exception:      # noqa: BLE001
        return True
    if isinstance(raw, str):
        return raw.strip().lower() not in ("false", "0", "no", "off")
    return True if raw is None else bool(raw)


def colprof_comparison_wanted(settings) -> bool:
    """Does colprof build its own profile beside an engine build? Only ever
    true while the switch is on (`colprof_comparison_setting`)."""
    return engine_switch_on(settings) and colprof_comparison_setting(settings)


def black_depth_setting(settings) -> str:
    """The stored black option as a ``BuildSettings.black_depth`` value; any
    value this build does not know is read as the default, Neutral."""
    try:
        raw = str(settings.get("profile_engine_black_depth", "neutral"))
    except Exception:      # noqa: BLE001
        raw = "neutral"
    raw = raw.strip().lower()
    return raw if raw in BLACK_DEPTHS else "neutral"

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
    # "uR" is `-u -R`: the -R half is fine on output data, the -u half is the
    # one colprof refuses, so it refuses the pair for the same reason and with
    # the same words. The scanner window strips white-point handling in printer
    # mode (`effective_adv_vals`), so this is the belt behind that brace.
    "uR": "Input auto WP scale mode isn't applicable to an output device",
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
        hue_rendering=params.hue_rendering or "argyll",
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


def choose_builder(settings, params: "ProfileParams") -> tuple[str, str]:
    """Which builder makes the profile for *params* under the current
    Preferences: ``("engine", why)``, ``("colprof", why)`` or
    ``("blocked", "")`` (a multi-ink measurement with the engine off, which
    colprof cannot build). *why* is a finished log line, or ``""``.

    The ONE place this is decided, so the Build Profile tab, its command box
    and any other window that builds a printer profile give the same answer.
    """
    on = engine_switch_on(settings)
    if is_multi_ink(params.ti3_path):
        if on:
            return "engine", tr(
                "[INFO] Multi-ink measurement — Argyll colprof can't "
                "build these, using the ChromIQ engine.")
        return "blocked", ""
    if not on:
        return "colprof", ""
    ok, why = engine_support(params)
    if ok:
        return "engine", ""
    return "colprof", tr(
        "[INFO] This build needs Argyll colprof because of: {what}. "
        "Building with colprof.").format(what=why)


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


#: BuildSettings fields that are not build parameters: a callback and the
#: header timestamp.
_NOT_PARAMETERS = frozenset({"progress", "timestamp"})


def build_settings_summary(settings) -> str:
    """Every parameter of an engine build, as one log line's worth of text.

    THE PROFILE BUILD WROTE NOTHING TO chromiq.log. Knut's beta 5 log shows
    two builds as nothing but *"archived test.icc"* and, two and a half
    minutes later, the applause sound (#182, 2026-10-03), so the question
    "which settings built this profile?" had no answer in the log at all. A
    colprof build logs its whole command line; the engine now logs its whole
    settings object, every field, defaults included, so nothing has to be
    inferred from what is missing.
    """
    from dataclasses import fields
    parts = []
    for f in fields(settings):
        if f.name in _NOT_PARAMETERS:
            continue
        parts.append(f"{f.name}={getattr(settings, f.name)!r}")
    return " ".join(parts)


def build_result_summary(res, seconds: float) -> str:
    """The finished engine build, as one log line."""
    return (
        f"engine build finished in {seconds:.1f} s: {res.icc_path} "
        f"({res.n_channels} channels, {res.color_rep}, A2B grid {res.a2b_grid}, "
        f"B2A grid {res.b2a_grid}); fit at the measured patches "
        f"median {res.fit_median_de:.2f} / 95% {res.fit_p95_de:.2f} \u0394E76, "
        f"median {res.fit_median_de00:.2f} / 95% {res.fit_p95_de00:.2f} \u0394E00; "
        f"B2A in-gamut median {res.b2a_ingamut_median_de:.2f} \u0394E; "
        f"out of gamut {100 * res.oog_fraction:.1f}%; "
        f"likely misreads {len(res.outlier_rows)}; "
        f"perceptual/saturation from a gamut source: {res.perceptual_distinct}")


class ColprofReferenceFailed(RuntimeError):
    """ArgyllCMS colprof could not give the engine its reference rendering.

    Every engine build of an RGB, CMY or CMYK measurement runs colprof once
    and matches its perceptual and saturation rendering. When that run
    fails the engine would carry on with a rendering of its own that nobody
    has tuned or judged, so the app stops the build here instead and the
    caller builds with colprof (which then reports its own trouble)."""


#: The engine's line when its colprof reference is not available.
_OWN_RENDERING = re.compile(r"^Using the engine's own rendering \((.*)\)\.$",
                            re.S)
#: The engine's list of the switches a build runs with.
_SWITCHES_ON = re.compile(r"^Candidate pipeline active: (.*?)\.?$", re.S)
#: The engine's report on the Deepest black option.
_DEEPEST = re.compile(
    r"^Colorimetric table: deepest black \S+ \(research a88: printer black "
    r"L\* (?P<kl>-?[\d.]+) a\* (?P<ka>-?[\d.]+) b\* (?P<kb>-?[\d.]+); "
    r"darkest printable neutral (?:none|L\* (?P<nl>-?[\d.]+) a\* "
    r"(?P<na>-?[\d.]+) b\* (?P<nb>-?[\d.]+)); (?P<nodes>\d+) nodes"
    r"(?P<idle>, not needed)?\)\.$")
#: The engine's lines about "Keep the original hue" (hue_keep.py): one per
#: table it re-solved, or one saying it did nothing on this device.
_HUE_KEPT = re.compile(
    r"^Hue-kept rendering \(x1-huekeep(?:, (?P<tag>B2A\d))?\): "
    r"(?P<rest>.*)$", re.S)
#: The percentage / remaining-time head the engine puts before a line.
_HEAD = re.compile(r"^(\d+%(?: · [^·]*)?) · (.*)$", re.S)
#: A numbered internal switch name (a84-warmblack, a25-oog, a88).
_NUMBERED_SWITCH = re.compile(r"\ba\d{2,3}[a-z]?(?:-[a-z0-9]+)*\b")
_INTERNAL_WORDS = re.compile(r"\bresearch\b|\bagent\s*\d", re.I)
#: Switch names that are also plain words: never taken for a switch.
_PLAIN_WORDS = frozenset({"spectral", "gp", "ucs"})


def _switch_names_in(msg: str) -> list[str]:
    """Internal switch names a line of the engine mentions."""
    found = set(_NUMBERED_SWITCH.findall(msg))
    try:
        from workflow.profile_engine.builder import (ENGINE_CANDIDATE_TOKENS,
                                                     GP_FIN3_TOKENS)
        known = (set(ENGINE_CANDIDATE_TOKENS) | set(GP_FIN3_TOKENS)) \
            - _PLAIN_WORDS
    except Exception:      # noqa: BLE001 - the names are a nicety
        known = set()
    words = set(re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", msg))
    found |= {t for t in known if not t.startswith("no-") and t in words}
    return sorted(found)


def _plain_reason(raw: str) -> str:
    """Why the colprof reference run failed, without the engine's own name
    for that run ("oracle"): what is left is ArgyllCMS's message or a plain
    English phrase, which is what the user is shown as {reason}."""
    text = re.sub(r"^\s*colprof oracle failed:\s*", "", raw or "").strip()
    if not text:
        return "colprof ended with an error"
    if re.search(r"oracle", text, re.I) or _NUMBERED_SWITCH.search(text):
        return "the result of the colprof run could not be read"
    return text


class EngineLines:
    """Turns the engine's own progress lines into what the window shows,
    and keeps what a later diagnosis needs.

    The engine reports in its developers' words: many lines name an internal
    switch ("... (research a70-edgesmooth)"). None of that belongs in front
    of a user, and all of it is exactly what is needed to build a reported
    profile again. So a line that names a switch is NOT shown; it goes to
    ``chromiq.log`` and into :meth:`record` (for the run's ``meta.json``).
    Two lines are replaced by a sentence of the app's own: the Deepest black
    report, and the missing colprof reference on a multi-ink build.

    On an RGB / CMY / CMYK build the missing colprof reference ends the
    build: :meth:`__call__` raises :class:`ColprofReferenceFailed` from then
    on, on whichever engine thread reports next.
    """

    def __init__(self, emit: Callable[[str], None], *,
                 multi_ink: bool = False) -> None:
        self._emit = emit
        self._multi_ink = multi_ink
        self.switches_on: list[str] = []
        self.reported: list[dict] = []
        self.reference_failed: str = ""
        self.dark_end: dict | None = None

    def __call__(self, raw: str) -> None:
        if self.reference_failed:
            raise ColprofReferenceFailed(self.reference_failed)
        m = _HEAD.match(raw)
        head, msg = (m.group(1), m.group(2)) if m else ("", raw)
        shown = self._present(msg)
        if self.reference_failed:
            raise ColprofReferenceFailed(self.reference_failed)
        if shown is None:
            log.info("[engine] %s", msg)       # kept for diagnosis
            return
        log.debug("[engine] %s", msg)
        self._emit(f"{head} · {shown}" if head else shown)

    def _present(self, msg: str) -> "str | None":
        m = _SWITCHES_ON.match(msg)
        if m:
            self.switches_on = sorted(
                t.strip() for t in m.group(1).split(",") if t.strip())
            return None
        m = _OWN_RENDERING.match(msg)
        if m:
            if not self._multi_ink:
                self.reference_failed = _plain_reason(m.group(1))
                return None
            return tr(
                "[WARNING] ChromIQ could not run ArgyllCMS colprof for the "
                "reference it normally uses for the black and the rendering "
                "of a multi-ink profile ({reason}). The profile is still "
                "being built, but without that reference, so please check "
                "it with a test print. To get the reference back, check the "
                "ArgyllCMS folder in Preferences and build "
                "again.").format(reason=_plain_reason(m.group(1)))
        m = _DEEPEST.match(msg)
        if m:
            self.reported.append({"switch": "a88-black-deepest", "line": msg})
            return self._deepest_line(m)
        m = _HUE_KEPT.match(msg)
        if m:
            self.reported.append({"switch": "x1-huekeep", "line": msg})
            return self._hue_kept_line(m)
        names = _switch_names_in(msg)
        if names or _INTERNAL_WORDS.search(msg):
            for name in names or ["(unnamed)"]:
                self.reported.append({"switch": name, "line": msg})
            return None
        return msg

    @staticmethod
    def _hue_kept_line(m) -> "str | None":
        """The engine's "Hue-kept rendering" lines in the app's words; a
        form this does not know stays in chromiq.log only."""
        tag, rest = m.group("tag"), m.group("rest")
        if tag == "B2A0":
            return tr(
                "Keep the original hue: the Perceptual table was built so "
                "that colours the printer cannot reach keep the hue of the "
                "original colour.")
        if tag == "B2A2":
            return tr(
                "Keep the original hue: the Saturation table was built so "
                "that colours the printer cannot reach keep the hue of the "
                "original colour.")
        if tag is None and "RGB printers only" in rest:
            return tr(
                "Keep the original hue: this option works for RGB printers "
                "only for now, so it changed nothing in this profile. The "
                "profile is the same as with the option off.")
        if tag is None and "Lab connection space" in rest:
            return tr(
                "Keep the original hue: this profile does not use L*a*b* as "
                "its connection space, so the option changed nothing in it. "
                "The profile is the same as with the option off.")
        return None

    def _deepest_line(self, m) -> str:
        black = {"l": m.group("kl"), "a": m.group("ka"), "b": m.group("kb")}
        self.dark_end = {
            "printer_black_lab": [float(black[k]) for k in "lab"],
            "darkest_neutral_lab": (
                None if m.group("nl") is None else
                [float(m.group(k)) for k in ("nl", "na", "nb")]),
            "changed_the_table": not m.group("idle"),
        }
        if m.group("nl") is None:
            return tr(
                "Deepest black: your printer's black measures L* {kl}, "
                "a* {ka}, b* {kb}. ChromIQ found no darker neutral grey to "
                "compare it with, so nothing was changed: this profile is "
                "the same as with Neutral.").format(
                    kl=black["l"], ka=black["a"], kb=black["b"])
        if m.group("idle"):
            return tr(
                "Deepest black: nothing to change on this printer. Its "
                "black (L* {kl}, a* {ka}, b* {kb}) is practically as "
                "neutral and as dark as the darkest neutral grey it can "
                "print (L* {nl}, a* {na}, b* {nb}), so this profile is the "
                "same as with Neutral.").format(
                    kl=black["l"], ka=black["a"], kb=black["b"],
                    nl=m.group("nl"), na=m.group("na"), nb=m.group("nb"))
        return tr(
            "Deepest black: the Relative and Absolute Colorimetric table "
            "now takes the darkest shadows all the way down to your "
            "printer's own black (L* {kl}, a* {ka}, b* {kb}), instead of "
            "keeping them at the darkest neutral grey the printer can print "
            "(L* {nl}, a* {na}, b* {nb}) for as long as possible. Use this "
            "profile with black point compensation switched on in the "
            "program you print from: without it, the darkest few steps "
            "print as the same black.").format(
                kl=black["l"], ka=black["a"], kb=black["b"],
                nl=m.group("nl"), na=m.group("na"), nb=m.group("nb"))

    def record(self, settings) -> dict:
        """What ``meta.json`` keeps about this engine build."""
        return {
            "builder": "engine",
            "engine_mode": ENGINE_MODE,
            "black_depth": str(getattr(settings, "black_depth", "neutral")),
            "hue_rendering": str(getattr(settings, "hue_rendering",
                                         "argyll")),
            "settings": build_settings_summary(settings),
            "switches_on": list(self.switches_on),
            "switches_reported": list(self.reported),
            "dark_end": self.dark_end,
        }


class _EngineThread(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(int, str)

    def __init__(self, ti3_path: Path, out_path: Path, settings, parent=None):
        super().__init__(parent)
        # numpy's OpenBLAS needs more than a QThread's 512 KiB (Knut #182
        # 5956290893: Bus error in numpy.linalg.solve). core/thread_stack.py
        from core.thread_stack import roomy
        roomy(self)
        self._ti3 = ti3_path
        self._out = out_path
        self._settings = settings
        #: Into chromiq.log as well as the tab's box, the way every Argyll
        #: tool's output reaches it; `line.emit` is queued across threads.
        self.lines = EngineLines(self.line.emit,
                                 multi_ink=is_multi_ink(ti3_path))
        #: What meta.json keeps about the build; filled when it succeeds.
        self.record: dict = {}
        #: Why colprof's reference was not available, when that ended it.
        self.reference_failed: str = ""

    def _drop_what_was_written(self) -> None:
        """A build stopped part way leaves no half profile behind."""
        for p in (self._out, self._out.with_name(self._out.stem + "-v4.icc")):
            try:
                if p.is_file():
                    p.unlink()
            except OSError:
                log.warning("could not remove %s", p, exc_info=True)

    def run(self) -> None:  # noqa: D102 — QThread worker
        import time
        from workflow.profile_engine import build_profile

        self._settings.progress = self.lines
        t0 = time.monotonic()
        try:
            res = build_profile(self._ti3, self._out, self._settings)
            if self.lines.reference_failed:
                # Said on a thread whose error the engine did not pass on.
                raise ColprofReferenceFailed(self.lines.reference_failed)
        except ColprofReferenceFailed as exc:
            log.warning("engine build stopped after %.1f s: colprof could "
                        "not give its reference rendering (%s)",
                        time.monotonic() - t0, exc)
            self._drop_what_was_written()
            self.reference_failed = str(exc) or "colprof"
            self.done.emit(1, "")
            return
        except Exception as exc:            # noqa: BLE001 — surfaced to UI
            if self.lines.reference_failed:
                # The stop surfaced as another error on the way out.
                log.warning("engine build stopped: colprof could not give "
                            "its reference rendering (%s)",
                            self.lines.reference_failed, exc_info=True)
                self._drop_what_was_written()
                self.reference_failed = self.lines.reference_failed
                self.done.emit(1, "")
                return
            log.exception("engine build failed after %.1f s",
                          time.monotonic() - t0)
            self.done.emit(1, str(exc))
            return
        log.info(build_result_summary(res, time.monotonic() - t0))
        self.record = self.lines.record(self._settings)
        self.record["seconds"] = round(time.monotonic() - t0, 1)
        log.info("engine build switches on: %s",
                 ", ".join(self.record["switches_on"]) or "(none reported)")
        log.info("engine build switches that reported: %s",
                 ", ".join(sorted({r["switch"] for r in
                                   self.record["switches_reported"]}))
                 or "(none)")
        self.line.emit(tr(
            "Model fit at the measured patches: median {med:.2f} ΔE, "
            "95% {p95:.2f} ΔE.").format(med=res.fit_median_de,
                                        p95=res.fit_p95_de))
        if res.perceptual_distinct:
            self.line.emit(tr(
                "Perceptual and saturation tables built from the gamut "
                "source."))
        self.done.emit(0, "")


class EngineProfileBuilder:
    """ProfileBuilder-compatible front end for the in-process engine."""

    #: Every builder with a live thread — the Build Profile tab's and the
    #: scanner tool's alike — so the quit guard asks for any of them
    #: (reviewer R13: a build started from the scanner tool got no question).
    _RUNNING: set = set()

    @classmethod
    def any_running(cls) -> bool:
        return any(b.is_running for b in list(cls._RUNNING))

    def __init__(self, settings=None) -> None:
        self._thread: _EngineThread | None = None
        self._last_error: str = ""
        self._app_settings = settings
        #: Set when the last build stopped because colprof could not give
        #: its reference rendering: the caller builds with colprof instead.
        self.reference_failed: str = ""
        #: What meta.json keeps about the last successful build.
        self.last_record: dict = {}

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
        # The engine copies the measurement to colprof for its gamut-mapping
        # oracle, so a damaged calibration table is put right here as well.
        from workflow.cal_repair import repair_embedded_cal
        repair_embedded_cal(params.ti3_path)
        # THE FWA GATE (`workflow.fwa_gate`), as colprof's floor does.
        from workflow.fwa_gate import without_refused_fwa
        params, refusal = without_refused_fwa(params)
        if refusal is not None:
            on_line(refusal.log_line)
        self.reference_failed = ""
        self.last_record = {}
        # A packaged app ignores the engine's development variables; main()
        # did this at start-up, and this is the door every build passes.
        from core.engine_env import (ignore_engine_overrides_when_frozen,
                                     is_frozen)
        ignore_engine_overrides_when_frozen()
        try:
            settings = settings_from_params(params)
            # The app builds with ONE engine mode (D-27).
            settings.gammap_mode = ENGINE_MODE
            # The engine's own default thread count; no setting for it.
            settings.engine_workers = 0
            if self._app_settings is not None:
                settings.argyll_bin = self._app_settings.get(
                    "argyll_bin_path", "/Applications/Argyll/bin")
                settings.black_depth = black_depth_setting(self._app_settings)
            if not is_frozen():
                # #123: dark-launched candidate pipeline, for development
                # only, from the environment. Never in a packaged app.
                import os
                from workflow.profile_engine.builder import \
                    candidates_from_env
                settings.engine_candidates = candidates_from_env(
                    os.environ.get("CHROMIQ_ENGINE_NEXT"))
                if settings.engine_candidates:
                    log.info("engine development switches from the "
                             "environment: %s",
                             ", ".join(sorted(settings.engine_candidates)))
        except (ExtraArgsError, ValueError) as exc:
            self._last_error = str(exc)
            on_line(tr("[ERROR] {msg}").format(msg=exc))
            on_finish(1)
            return
        out = self.expected_icc_path(params)
        log.info("engine build: %s -> %s  [%s]", params.ti3_path, out,
                 build_settings_summary(settings))
        self._last_error = ""
        self._thread = t = _EngineThread(params.ti3_path, out, settings)
        t.line.connect(on_line)

        def _finished(code: int, err: str) -> None:
            self._last_error = err
            self.reference_failed = t.reference_failed
            self.last_record = dict(t.record)
            if err:
                on_line(tr("[ERROR] {msg}").format(msg=err))
            on_finish(code)

        def _released() -> None:
            """Drop our reference only once the thread has really stopped."""
            self._thread = None
            EngineProfileBuilder._RUNNING.discard(self)

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
        on_line(tr("Building with the ChromIQ profile engine (beta)…"))
        EngineProfileBuilder._RUNNING.add(self)
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
