"""Orchestrates colprof for ICC profile creation and installation."""
from __future__ import annotations

import os

import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core import icc_text
from core.logger import get_logger
from core.platform_paths import icc_install_dir

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)


#: Every letter colprof's ``-a`` accepts, and no other.
#:
#: ChromIQ offered **M**, "Matrix only (forced)", in both the Guided and the
#: Manual algorithm dropdown and in ``data/parameters.yaml``. colprof has no
#: ``M``: ``profile/colprof.c:599-631`` is a ``switch (na[0])`` with cases
#:
#:     l  L  x  X  Y  g  G  s  S  m
#:
#: and a ``default:`` that calls ``usage("Unknown argument '%c' to algorithm
#: flag -a")``. MEASURED against the 3.5.0 binary, one probe per ASCII letter:
#: those ten parse and every other letter, ``M`` included, exits 1.
#:
#: And it failed in SILENCE. ``_build_args`` below appends the letter verbatim,
#: no entry in ``_COLPROF_ERROR_PATTERNS`` matches "Unknown argument 'M' to
#: algorithm flag -a", and the Profile tab only opens a window when a pattern
#: matches or the FWA case fires — so the user got no profile, no dialog and one
#: line in a log. ``tests/test_printtarg_argument_vocabulary.py`` now pins every
#: letter the UI offers against this set.
COLPROF_ALGORITHMS = frozenset("lLxXYgGsSm")


#: …and that set is only HALF the rule. The missing half is what beta 11 left
#: behind: `-a` is parsed long before the measurement is read, so every one of
#: those ten letters parses, and the **DEVICE_CLASS in the .ti3** then decides
#: whether it can be used at all. READ-FROM-SOURCE, colprof.c 3.5.0:
#:
#: * ``OUTPUT`` (a printer), ``colprof.c:1244-1246``::
#:
#:       else if (ptype != prof_clutLab && ptype != prof_clutXYZ)
#:           error ("Output profile can only be a cLUT algorithm");
#:
#:   A printer profile is a cLUT or it is nothing.
#: * ``INPUT`` / ``EMISINPUT`` (a scanner or camera), ``colprof.c:1272-1287`` —
#:   every letter is accepted; ``X`` and ``Y`` *warn* ("-aX not applicable to
#:   input profile, using -ax") and fall back to ``x``.
#: * ``DISPLAY``, ``colprof.c:1296-1310`` — every letter, and the only branch
#:   that passes ``mtxtoo`` on to ``make_output_icc``, so it is the only place
#:   ``X`` and ``Y`` mean anything at all. ChromIQ profiles no displays.
#:
#: MEASURED against the 3.5.0 binary on real measurements of both classes
#: (a printer chart, Knut's scanner-measured printer chart, a scanned IT8) and
#: on a synthetic 300-patch chart: exactly the letters below build a profile,
#: and every other letter exits 1 having written nothing.
COLPROF_ALGORITHMS_BY_DEVICE_CLASS: "dict[str, frozenset[str]]" = {
    "OUTPUT":    frozenset("lLxXY"),
    "INPUT":     frozenset("lLxXYgGsSm"),
    "EMISINPUT": frozenset("lLxXYgGsSm"),
    "DISPLAY":   frozenset("lLxXYgGsSm"),
}

#: The ``-a`` letters ChromIQ OFFERS for a printer profile, and the reason the
#: list is two where colprof accepts five.
#:
#: ``X`` and ``Y`` are legal for an OUTPUT profile but inert in one: the OUTPUT
#: call site is ``make_output_icc(ptype, 0, …)`` (``colprof.c:1256``) with
#: ``mtxtoo`` a hard-coded literal ``0``, so the fallback matrix those two
#: letters exist to add is discarded before it is built. MEASURED, byte-comparing
#: three profiles built from one printer .ti3: ``x``, ``X`` and ``Y`` differ only
#: in the header creation time. colprof prints no warning about it either (the
#: INPUT branch does). An entry that silently makes the same file as the one
#: above it is a trap, and ChromIQ's label for ``X``, "XYZ cLUT + matrix",
#: promised a matrix the file does not contain.
OUTPUT_ALGORITHM_CHOICES = ("l", "x")

#: Where a stored letter goes when it is no longer offered for a printer.
#: ``X``/``Y``/``L`` are aliases of a letter that IS offered and produce the
#: identical file, so those projects build exactly what they built before.
#: ``g G s S m`` never built anything at all, so they land on colprof's own
#: default for an output profile, ``l`` (``colprof.c:1243``).
_OUTPUT_ALGORITHM_FALLBACK = {"L": "l", "X": "x", "Y": "x",
                              "g": "l", "G": "l", "s": "l", "S": "l", "m": "l"}


def output_algorithm(letter: "str | None") -> "tuple[str, bool]":
    """Coerce a stored ``-a`` letter to one ChromIQ offers for a PRINTER.

    Returns ``(letter, changed)``. ``changed`` is True only when the stored
    letter was one this app no longer offers, which is the caller's cue to
    SAY SO: a setting that quietly means something else is the failure mode
    this whole change exists to remove.
    """
    # `isinstance`, NOT `letter or ""`. A stored setting is whatever the file
    # holds, and a damaged or hand-edited meta.json / preset .json can hold a
    # number or a list there. `7 or ""` is 7, and `7.strip()` is an
    # AttributeError raised from the FIRST line of `_m_apply_preset_data` —
    # which abandons the other 42 settings in the same dict and leaves the
    # previous target's Build Profile settings on screen. Measured, agent CV.
    # Before this release the same value simply missed `findData` and was
    # ignored, so treating a non-string as "nothing stored" restores that.
    letter = (letter if isinstance(letter, str) else "").strip()
    if letter in OUTPUT_ALGORITHM_CHOICES:
        return letter, False
    if letter in _OUTPUT_ALGORITHM_FALLBACK:
        return _OUTPUT_ALGORITHM_FALLBACK[letter], True
    return OUTPUT_ALGORITHM_CHOICES[0], bool(letter)


# Errors that colprof can print when it fails. Each entry pairs a regex that
# captures the dynamic part of the message (filename, value, etc.) with a
# (key, friendly_template) tuple. The key lets the UI choose a bespoke dialog
# (e.g. the FWA-instrument one) instead of the generic failure dialog.
# References point to lines in Argyll 3.5.0 spectro/profile/colprof.c.
_COLPROF_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L673 / L720 — illuminant type mismatch
    (re.compile(r"(?:Target|CIE) illuminant '([^']+)' is wrong measurement type"),
     "illum_type",
     "The illuminant '{0}' isn't compatible with the reference data in your "
     ".ti3 file. Pick a different illuminant in Build Profile → Color Science, "
     "or clear the field to use the default."),
    # L1015 — FWA enabled without viewer/illuminant
    (re.compile(r"FWA compensation only works when viewer and/or illuminant selected"),
     "fwa_needs_illum",
     "FWA compensation requires you to also set a viewing condition and/or "
     "illuminant in Build Profile → Color Science. Either pick one of those, "
     "or disable FWA Compensation."),
    # L1246 — the algorithm is not one an OUTPUT (printer) profile can use.
    # colprof refuses -ag/-aG/-as/-aS/-am for a printer measurement outright,
    # before it reads a single patch, and until now nothing here matched that
    # line: no profile, no window, one line in a log. ChromIQ no longer offers
    # those letters for a printer, so a user should never see this; it is here
    # because the class of failure must never be silent again, and a stored
    # setting, a preset or a hand-typed extra argument can still reach it.
    (re.compile(r"Output profile can only be a cLUT algorithm"),
     "algo_not_clut",
     "A printer profile has to be a lookup table, and the algorithm this "
     "build asked for is not one.\n\nSet Algorithm to \"Lab cLUT\" or "
     "\"XYZ cLUT\" in Build Profile and build again. ArgyllCMS supports the "
     "gamma, shaper and matrix algorithms only for scanners, cameras and "
     "displays, never for a printer."),
    # L1048 — input .ti3 unreadable / corrupt
    (re.compile(r"CGATS file read error\s*:\s*(.+)$"),
     "ti3_read",
     "The measurement file (.ti3) could not be read.\n\nArgyll reported: {0}\n\n"
     "Make sure the file isn't open in another app, hasn't been edited by hand, "
     "and was generated by ChromIQ's Measure step."),
    # L1087 — empty / wrong .ti3
    (re.compile(r"Neither CIE nor spectral data found in file '([^']+)'"),
     "ti3_empty",
     "The measurement file doesn't contain any XYZ/Lab or spectral readings.\n\n"
     "File: {0}\n\nIt looks like the file wasn't fully written by chartread, or "
     "you selected a chart definition (.ti1/.ti2) instead of the measured .ti3."),
    # Emitted from icc/colprof when the .ti3 was measured with a non-UV instrument
    # but FWA was requested. The string is checked verbatim (typo and all) — it
    # matches the Argyll output literally.
    (re.compile(r"doesn't have an FWA illuminent", re.IGNORECASE),
     "fwa_no_uv",
     ""),  # handled by a bespoke dialog (_show_fwa_instrument_error)
]

# Warnings that don't terminate colprof but the user may want to know about.
_COLPROF_WARNING_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L1018 — intent override only works with srcprof
    (re.compile(r"-t perceptual intent override only works if -s srcprof or -S srcprof is used"),
     "perc_intent_orphan",
     "The perceptual intent override (-t) was ignored because no source profile "
     "(-s / -S) was set."),
    # L1021
    (re.compile(r"-T saturation intent override only works if -S srcprof is used"),
     "sat_intent_orphan",
     "The saturation intent override (-T) was ignored because no source "
     "profile (-S) was set."),
    # L1030
    (re.compile(r"No gamut mapping called for, so -P will produce nothing"),
     "no_gamut_map",
     "Gamut mapping wasn't requested, so -P (gamut preview) produced no output."),
    # L1033
    (re.compile(r"-g srcgam will do nothing without -s srcprof or -S srcprof"),
     "srcgam_orphan",
     "The -g srcgam option was ignored because no source profile was set."),
    # L1066
    (re.compile(r"-i illuminant ignored for emissive reference type"),
     "illum_ignored_emissive",
     "Illuminant setting was ignored — this measurement was made in emissive mode."),
    # L1068
    (re.compile(r"-f FWA compensation ignored for emissive reference type"),
     "fwa_ignored_emissive",
     "FWA compensation was ignored — this measurement was made in emissive mode."),
    # L1150 — over-limit ink budget vs original chart
    (re.compile(r"Ink limit is greater than original chart!\s*\(([\d.]+)%\s*>\s*([\d.]+)%\)"),
     "ink_limit_over",
     "Your ink limit ({0}%) exceeds the maximum measured in the chart ({1}%). "
     "The profile may extrapolate beyond what your printer actually does."),
    # L1168 — black ink limit over chart
    (re.compile(r"Black ink limit greater than original chart!\s*\((\d+)%\s*>\s*(\d+)%\)"),
     "kink_limit_over",
     "Your black ink limit ({0}%) exceeds the maximum measured in the chart ({1}%)."),
    # L1279 / L1281
    (re.compile(r"-a([XY]) not applicable to input profile, using -ax"),
     "input_profile_alg",
     "Algorithm -a{0} isn't applicable to input profiles — colprof fell back to -ax."),
]


def _profile_dir() -> Path:
    return icc_install_dir()


@dataclass
class ProfileParams:
    ti3_path: Path
    description: str = ""
    algorithm: str = "l"
    quality: str = "m"
    b2a_quality: str = ""
    smoothing: float = 0.5
    dark_emphasis: float = 1.0
    gamut_src: str = ""
    manufacturer: str = ""
    model: str = ""
    copyright: str = ""
    no_input_shaper: bool = False
    no_output_shaper: bool = False
    verbose: bool = False        # pass colprof -v (progress + errors visible)
    extra_args: str = ""
    # Color science
    illuminant: str = ""
    observer: str = ""
    fwa_enabled: bool = False
    fwa_illum: str = ""
    src_viewing_cond: str = ""
    dst_viewing_cond: str = ""
    # ICC media attributes & default intent (-Z)
    z_surface: str = ""        # "" = glossy (default), "m" = matte
    z_media_type: str = ""     # "" = reflective (default), "t" = transparent
    z_polarity: str = ""       # "" = positive (default), "n" = negative
    z_color_mode: str = ""     # "" = color (default), "b" = black & white
    z_default_intent: str = "" # "" = not set, "p"/"r"/"s"/"a"
    # Gamut mapping extended
    gamut_sat_src: str = ""
    no_perc_gamut: bool = False
    no_sat_gamut: bool = False
    inv_gamut_map: bool = False
    perc_intent: str = ""
    sat_intent: str = ""
    # Curve / embedding flags
    no_grid_pos: bool = False
    no_embedded_data: bool = False
    # Input-profile white-point handling (#121): wp_mode ∈ {"", "u", "uR", "ua",
    # "uc", "scale"} → nothing / -u / -u -R / -ua / -uc / -u <wp_scale>;
    # clip_primaries → -R on its own.
    #
    # "" stays "no flag" here, and stays this dataclass's default, because every
    # caller that is not the scanner window builds an OUTPUT profile, where the
    # -u family is not applicable at all. The scanner window's own default is
    # "uR" and lives in `ui/dialogs/scanner_colprof.WP_MODE_DEFAULT`.
    wp_mode: str = ""
    wp_scale: float = 0.0
    clip_primaries: bool = False
    # Black generation (-k/-K): rule ∈ {"", "z", "h", "x", "r", "p"} ("" =
    # colprof's default ramp, flag not passed). k_locus True = uppercase -K
    # (curve is the proportion of the possible black range, not the K value).
    # The five curve parameters are used only with rule "p".
    k_rule: str = ""
    k_locus: bool = False
    k_stle: float = 0.0
    k_stpo: float = 0.1
    k_enpo: float = 0.9
    k_enle: float = 1.0
    k_shape: float = 1.0
    # Engine-only options (#123) — no colprof flags exist for these; the
    # UI only offers them when the engine's maximum-accuracy mode is
    # active, so the colprof path never sees them set.
    spectral_physics: bool = False
    icc_version: str = "2"
    noise_model: bool = False
    render_style: str = "argyll"


class ProfileBuilder:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner = runner
        self._last_log: str = ""
        # Captured (key, friendly_text) pairs as the tool runs.
        self._matched_errors: list[tuple[str, str]] = []
        self._matched_warnings: list[tuple[str, str]] = []

    # ------------------------------------------------------------------

    def build(
        self,
        params: ProfileParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        args = self._build_args(params)
        cwd  = params.ti3_path.parent
        log.info("colprof: %s  [cwd=%s]", " ".join(args), cwd)
        self._last_log = ""
        self._matched_errors = []
        self._matched_warnings = []

        def _accumulate(line: str) -> None:
            self._last_log += line + "\n"
            self._scan_line(line)
            on_line(line)

        def _finished(code: int) -> None:
            if code == 0:
                self._restore_accents(params)
            on_finish(code)

        self._runner.run(
            "colprof",
            args,
            cwd,
            on_line=_accumulate,
            on_finish=_finished,
        )

    def _restore_accents(self, params: ProfileParams) -> None:
        """Put the accents colprof dropped back into the finished profile.

        AN ACCENT IS PART OF THE NAME, and colprof throws it away: its ASCII
        converter substitutes ``'?'`` for every non-ASCII character
        (Argyll 3.5.0, ``icc/icc_util.c::icmUTF8toASCIIZSn``) and it never
        fills the Unicode field that the same tag provides
        (``profile/profout.c:1293`` sets only ``wo->desc``). A project called
        ``Müller-Prüfdruck`` therefore reaches the file as the literal bytes
        ``M?ller-Pr?fdruck``, which is what Windows — and macOS — then show.

        THIS TOUCHES THE FILE ARGYLL WROTE, so it is deliberately inert
        unless it is needed: when every name is already ASCII the profile is
        not even opened, and :func:`core.icc_text.repair_descriptions` only
        rewrites a tag whose stored ASCII is exactly Argyll's ``'?'`` spelling
        of the name we asked for. A failure here is logged and swallowed —
        a profile with a ``?`` in its name is a blemish; a profile that
        failed to build is not.
        """
        desc = params.description or params.ti3_path.stem
        names = {
            b"desc": desc,
            b"dmdd": params.model or desc,
            b"dmnd": params.manufacturer or "ChromIQ",
        }
        if all(name.isascii() for name in names.values()):
            return
        try:
            # THROUGH THE SYMLINK, NOT OVER IT. `os.replace` swaps the NAME it
            # is given, so pointed at a symlink it deletes the link and leaves
            # a regular file in its place: the real profile keeps `M?ller`,
            # every other consumer of it silently sees the old spelling, and
            # the user's link into ~/Library/ColorSync/Profiles or a shared
            # job folder is gone with no message. `write_bytes` wrote through
            # the link, so this was a regression the atomic fix introduced.
            path = Path(os.path.realpath(self.expected_icc_path(params)))
            data = path.read_bytes()
            repaired = icc_text.repair_descriptions(data, names)
            if repaired != data:
                # WRITTEN BESIDE IT, THEN SWAPPED IN. `write_bytes` truncates
                # the file and then fills it, so a crash, a power cut or a full
                # disk between those two moments leaves the person with a
                # truncated ICC — their finished profile, destroyed by a change
                # that only fixes how its NAME is spelled. `os.replace` is
                # atomic on POSIX and on Windows: either the old file or the
                # new one is there, never half of either. The temp file is a
                # sibling so the replace cannot cross a filesystem boundary,
                # and it is removed if anything goes wrong.
                #
                # A stale sibling from an earlier hard kill is overwritten
                # rather than tripping us up: nothing reads it, and its only
                # other outcome is to litter the run folder for ever.
                tmp = path.with_name(path.name + ".name-fix")
                try:
                    with open(tmp, "wb") as fh:
                        fh.write(repaired)
                        fh.flush()
                        # THE RENAME IS ATOMIC, THE DATA IS NOT YET THERE.
                        # `os.replace` orders the directory entry, not the
                        # blocks behind it; without this a power cut can land
                        # the new name on top of unwritten content, which is
                        # the exact scenario the swap exists to prevent.
                        os.fsync(fh.fileno())
                    # Mode, times, Finder flags and extended attributes belong
                    # to the user's file, not to our temp copy. A profile they
                    # made read-only must not come back writable, and a Finder
                    # comment or tag must survive a change to its name.
                    shutil.copystat(path, tmp)
                    os.replace(tmp, path)
                finally:
                    try:
                        tmp.unlink()
                    except OSError:
                        pass          # already replaced, which is the good case
                log.info("Restored non-ASCII profile name in %s", path.name)
        except Exception:                     # noqa: BLE001 — cosmetic only
            log.warning("Could not restore the profile's accented name",
                        exc_info=True)

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _COLPROF_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_errors.append((key, fmt.format(*m.groups()) if fmt else ""))
        for pattern, key, fmt in _COLPROF_WARNING_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_warnings.append((key, fmt.format(*m.groups())))

    def primary_failure(self) -> tuple[str, str] | None:
        """Return (key, friendly_message) of the first structured error, or
        None if no known error pattern was matched. The UI can pick a bespoke
        dialog by key (e.g. "fwa_no_uv") or fall back to a generic dialog."""
        return self._matched_errors[0] if self._matched_errors else None

    def last_output(self, n: int = 12) -> str:
        """The last *n* non-blank, non-progress lines colprof printed — shown when
        a build fails without a recognised error pattern, so the real reason
        (whatever colprof actually said) is never swallowed."""
        lines = [ln.rstrip() for ln in self._last_log.splitlines()
                 if ln.strip() and not ln.rstrip().endswith("%")]
        return "\n".join(lines[-n:])

    def captured_warnings(self) -> list[tuple[str, str]]:
        """Structured warnings captured during the most recent run."""
        return list(self._matched_warnings)

    def install_profile(self, icc_path: Path,
                        install_name: "str | None" = None) -> Path:
        """Copy .icc file to the system ICC profile folder. Returns the installed path.

        ``install_name`` (no extension) names the INSTALLED COPY only — Knut's
        "Profile file name same as description for installed copy" checkbox.
        The project's own file always keeps its name; an installed profile of
        the same name is replaced, which is the normal way to update one.
        """
        profile_dir = _profile_dir()
        try:
            profile_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            log.warning("Cannot create profile dir %s — elevation may be required", profile_dir)
            raise
        name = f"{install_name}.icc" if install_name else icc_path.name
        dest = profile_dir / name
        shutil.copy2(icc_path, dest)
        log.info("Profile installed: %s", dest)
        return dest

    def sanity_check(self, icc_path: Path, log_output: str = "") -> list[str]:
        """Return list of warning strings; empty = pass."""
        issues: list[str] = []

        if not icc_path.exists():
            issues.append("Profile file not found.")
            return issues

        size = icc_path.stat().st_size
        if size < 1000:
            issues.append(f"Profile is suspiciously small ({size} bytes).")
        if size > 20_000_000:
            issues.append(f"Profile is very large ({size / 1e6:.1f} MB). Check quality setting.")

        combined = log_output or self._last_log
        for pattern, msg in [
            (r"Warning.*out of gamut",    "Out-of-gamut warnings in measurements."),
            (r"Profile creation failed", "colprof reported a failure."),
        ]:
            if re.search(pattern, combined, re.IGNORECASE):
                issues.append(msg)

        # Surface the structured warnings captured live during the run too.
        for _key, friendly in self._matched_warnings:
            if friendly and friendly not in issues:
                issues.append(friendly)

        return issues

    def expected_icc_path(self, params: ProfileParams) -> Path:
        # colprof APPENDS the ICC extension to the basename it is handed (the
        # same basename _build_args passes in). For a normal name that equals
        # base.with_suffix(ext); but when the basename itself still carries a
        # dotted token — e.g. a stray ".icm" left in the target name, giving a
        # "<name>.icm.ti3" measurement file — colprof writes "<name>.icm.icc",
        # whereas with_suffix() would instead look for "<name>.icc". Check the
        # literal appended form first so such a profile is still found, then the
        # legacy replace form for plain names.
        base = params.ti3_path.with_suffix("")
        candidates: list[Path] = []
        for ext in (".icc", ".icm"):
            candidates.append(Path(str(base) + ext))   # what colprof actually writes
            candidates.append(base.with_suffix(ext))   # legacy / extension-free names
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return Path(str(base) + ".icc")

    # ------------------------------------------------------------------

    def _build_args(self, p: ProfileParams) -> list[str]:
        args: list[str] = []
        if p.verbose:
            args.append("-v")        # colprof prints progress + any error
        desc = p.description or p.ti3_path.stem
        args += ["-D", desc]
        args.append(f"-a{p.algorithm}")
        args.append(f"-q{p.quality}")
        if p.b2a_quality:
            args.append(f"-b{p.b2a_quality}")
        if abs(p.smoothing - 0.5) > 0.01:
            args += [f"-r{p.smoothing:.2f}"]
        if abs(p.dark_emphasis - 1.0) > 0.01:
            args += [f"-V{p.dark_emphasis:.1f}"]
        if p.gamut_src:
            args += ["-s", p.gamut_src]
        if p.k_rule:
            # -kz/-kh/-kx/-kr/-kp … (uppercase -K = locus variant); the five
            # curve values follow a "p" rule as separate arguments.
            args.append(("-K" if p.k_locus else "-k") + p.k_rule)
            if p.k_rule == "p":
                args += [f"{p.k_stle:g}", f"{p.k_stpo:g}", f"{p.k_enpo:g}",
                         f"{p.k_enle:g}", f"{p.k_shape:g}"]
        # Always stamp a manufacturer + model description so the profile is
        # self-identifying: colprof writes these as the 'dmnd'/'dmdd' device-ID
        # tags, which a device-link then copies into its profile-sequence ('pseq')
        # — otherwise that entry is left blank ("placeholder"). Falls back to
        # "ChromIQ" / the profile description when the caller hasn't set them.
        args += ["-A", p.manufacturer or "ChromIQ"]
        args += ["-M", p.model or desc]
        if p.copyright:
            # TRANSLITERATED, NOT LEFT TO COLPROF. The copyright goes into a
            # v2 `text` tag, which is ASCII by definition and has no Unicode
            # field to repair afterwards the way `desc` has — so this is the
            # only moment the accents can survive in any readable form.
            # "© 2026 Müller Druckerei" reaches the profile as
            # "(c) 2026 Mueller Druckerei" instead of "? 2026 M?ller Druckerei".
            # The engine path already did this; the two disagreed.
            args += ["-C", icc_text.ascii_fallback(p.copyright)]
        if p.illuminant:
            args += ["-i", p.illuminant]
        if p.observer:
            args += ["-o", p.observer]
        if p.src_viewing_cond:
            args.append(f"-c{p.src_viewing_cond}")
        if p.dst_viewing_cond:
            args.append(f"-d{p.dst_viewing_cond}")
        if p.fwa_enabled:
            args.append(f"-f{p.fwa_illum}" if p.fwa_illum else "-f")
        z_attrs = "".join(filter(None, [p.z_surface, p.z_media_type, p.z_polarity, p.z_color_mode]))
        if z_attrs:
            args += ["-Z", z_attrs]
        if p.z_default_intent:
            args += ["-Z", p.z_default_intent]
        if p.gamut_sat_src:
            args += ["-S", p.gamut_sat_src]
        if p.no_perc_gamut:
            args.append("-nP")
        if p.no_sat_gamut:
            args.append("-nS")
        if p.inv_gamut_map:
            args.append("-nI")
        if p.perc_intent:
            args.append(f"-t{p.perc_intent}")
        if p.sat_intent:
            args.append(f"-T{p.sat_intent}")
        if p.no_grid_pos:
            args.append("-np")
        if p.no_embedded_data:
            args.append("-nc")
        if p.no_input_shaper:
            args.append("-ni")
        if p.no_output_shaper:
            args.append("-no")
        # Input-profile white-point handling (-u / -ua / -uc / -u <scale>) and the
        # general primary clamp (-R). Mutually-exclusive -u modes (#121, Knut).
        if p.wp_mode in ("u", "uR"):
            args.append("-u")
        elif p.wp_mode == "ua":
            args.append("-ua")
        elif p.wp_mode == "uc":
            args.append("-uc")
        elif p.wp_mode == "scale" and p.wp_scale > 0:
            args += ["-u", f"{p.wp_scale:g}"]
        # -R, from either the "uR" white-point mode (which IS -u -R) or the
        # switch on its own — ONCE, however both arrive. colprof takes the flag
        # twice without complaining, but the command ChromIQ shows the user is
        # the command it runs, and "-u -R -R" is not a command anybody wrote.
        if p.clip_primaries or p.wp_mode == "uR":
            args.append("-R")
        if p.extra_args:
            args += shlex.split(p.extra_args)
        # Multi-ink charts (#72): the chart's TOTAL_INK_LIMIT rides the
        # .ti1 → .ti2 → .ti3 chain; prefill colprof's -l from it so the
        # finished profile never asks the printer for more ink than the chart
        # tested — unless the user already set -l/-L themselves. RGB
        # measurements never carry the keyword, so this is a no-op for them.
        if not any(a.startswith(("-l", "-L")) for a in args):
            limit = self._ti3_ink_limit(p.ti3_path)
            if limit is not None:
                args.append(f"-l{int(limit)}")
        # Base name without extension
        args.append(str(p.ti3_path.with_suffix("")))
        return args

    @staticmethod
    def _ti3_ink_limit(ti3_path: Path) -> float | None:
        """The measurement's ``TOTAL_INK_LIMIT`` (percent), or None (#72)."""
        try:
            text = Path(ti3_path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        m = re.search(r'^TOTAL_INK_LIMIT\s+"([\d.]+)"', text, re.MULTILINE)
        try:
            return float(m.group(1)) if m else None
        except ValueError:
            return None
