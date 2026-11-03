"""THE FWA GATE: can brightener compensation (FWA, ``colprof``/``profcheck
-f``) be used for this ``.ti3``, and if not, why.

One question, asked in one place, by everything that could pass ``-f``:

* the Build Profile and Check & Refine tabs, which grey the FWA box and its
  illuminant with :attr:`FwaRefusal.reason` as their tooltip (they only grey:
  the tick stays, so saved settings and presets keep the user's choice) and
  leave ``-f`` out of the parameters they collect, command box included;
* the builders' floor, :func:`without_refused_fwa`, under ``colprof``
  (``workflow.profile_builder``), ``profcheck`` (``workflow.profcheck_runner``,
  before its N-channel route) and the ChromIQ engine
  (``workflow.engine_builder``), which drops ``-f`` (also one typed into the
  extra arguments) with :attr:`FwaRefusal.log_line` in the log, whichever
  door asked for it.

The reasons, each measured rather than assumed (ArgyllCMS 3.5.0,
2026-11-03, ``spec2cie -f`` and ``colprof -f`` on one real spectral ``.ti3``
with only the header changed; the probes and their output are kept in the
4.3.23 work folder, ``fwa_unify/argyll_probe``):

* **No spectra.** FWA compensation works on the spectrum of every patch. A
  file without ``SPECTRAL_BANDS`` stops ``colprof -f`` with "Input file
  doesn't contain keyword SPECTRAL_BANDS" (or "...field SPEC_380" when the
  keyword is there and the columns are not). A CR30 ``.ti3`` is colorimetric
  by design, and so is anything saved without spectra.
* **An instrument ArgyllCMS has no FWA lamp for.** ArgyllCMS finds the lamp by
  ``TARGET_INSTRUMENT``, by an EXACT, case-sensitive match against its own
  name table (``spectro/insttypes.c``; "gretagmacbeth i1 pro", a trailing
  space or "X-Rite i1 Pro 3+" are all "Unrecognised"). Every name in that
  table was tried: :data:`ARGYLL_FWA_INSTRUMENTS` is exactly the set that
  passed. The ColorMunki family is in the table but stops with "Instrument
  doesn't have an FWA illuminent" (its white LED has no ultraviolet); every
  other name (the CR30, the i1iSis and the names i1Profiler gives, an earlier
  import's "i1Pro 3", "i1Profiler (unspecified)", a file with no name) stops
  with "Unrecognised target instrument" or "Can't find target instrument
  needed for FWA compensation".
* **The FD-9**, one of those unknown names, with its own text, because it
  measures under a condition chosen on the Measure tab: ``colprof -f`` stops with "Unrecognised target instrument 'Konica Minolta
  FD-9'" (ArgyllCMS 3.5.0, 2026-11-03, both spellings), while ``-i`` and
  ``-o`` work on the same file. Not behind the Beta switch: the refusal is
  ArgyllCMS's, and the file stays what it is after the Beta is turned off.
* **The measurement condition.** The model only fits readings taken under the
  instrument's own lamp, M0. A file that SAYS it is M1 or M2
  (``MEASUREMENT_CONDITION``, ``workflow.measurement_condition``) would have a
  glow corrected that is not there in the form the model assumes (measured on
  jctay's M2 readings: ``spec2cie -f`` moved them by 0.37 mean / 0.72 max
  dE76 for nothing). The Measure tab records the condition from chartread's
  ``-F`` (review round 1, S3), so a chartread M1/M2 is refused too. A
  chartread file that names no condition is judged as before; an i1Profiler
  import that names none is refused (S4), because i1Profiler exports M1 and
  M2 as readily as M0.

The header is read once, as bytes, up to the data (a chart made on a German
Windows is cp1252), and nothing is imported from the instrument's own
modules beyond the name check.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, replace
from pathlib import Path

from core.i18n import tr

#: How much of a file's head is read for the gate.
_HEAD_BYTES = 65536


@dataclass(frozen=True)
class FwaRefusal:
    """Why FWA compensation cannot be used for a measurement.

    *kind* is one of ``"fd9"`` (an FD-9 measurement), ``"no_spectra"``,
    ``"no_name"`` (the file names no instrument), ``"colormunki"`` (an
    instrument without an ultraviolet lamp), ``"reimport"`` (an import by an
    earlier ChromIQ that kept i1Profiler's name for an instrument ArgyllCMS
    knows under another), ``"instrument"`` (any other name ArgyllCMS has no
    FWA lamp for), ``"condition"`` (an M1/M2 measurement) or
    ``"import_condition"`` (an i1Profiler import that does not say which
    condition it holds); *instrument* and *condition* are what the file
    says."""
    kind: str
    instrument: "str | None" = None
    condition: "str | None" = None

    @property
    def reason(self) -> str:
        """The tooltip on the greyed FWA box and its illuminant."""
        if self.kind == "fd9":
            return _fd9_reason()
        if self.kind == "no_spectra":
            return _no_spectra_reason()
        if self.kind == "no_name":
            return _no_name_reason()
        if self.kind == "colormunki":
            return _colormunki_reason()
        if self.kind == "reimport":
            return _reimport_reason(self.instrument or "")
        if self.kind == "instrument":
            return _instrument_reason(self.instrument or "")
        if self.kind == "import_condition":
            return _import_condition_reason()
        return _condition_reason(self.condition or "")

    @property
    def log_line(self) -> str:
        """The ``[NOTE]`` line when ``-f`` was asked for and left out."""
        if self.kind == "fd9":
            return tr(
                "[NOTE] FWA compensation (-f) was left out: ArgyllCMS cannot "
                "apply it to FD-9 measurements, and the FD-9's own measurement "
                "condition (M0, M1 or M2) already decides how the brighteners "
                "in the paper were measured.")
        if self.kind == "no_spectra":
            return tr(
                "[NOTE] FWA compensation (-f) was left out: this measurement "
                "has no spectral readings, and FWA compensation works from "
                "the spectrum of every patch.")
        if self.kind == "no_name":
            return tr(
                "[NOTE] FWA compensation (-f) was left out: this measurement "
                "does not say which instrument took it, and ArgyllCMS needs "
                "that to apply FWA compensation.")
        if self.kind in ("colormunki", "reimport", "instrument"):
            return tr(
                "[NOTE] FWA compensation (-f) was left out: ArgyllCMS has no "
                "FWA data for the instrument this measurement names "
                "(“{instrument}”), so it would stop with an error."
            ).format(instrument=self.instrument or "")
        if self.kind == "import_condition":
            return tr(
                "[NOTE] FWA compensation (-f) was left out: this measurement "
                "was imported from i1Profiler and does not say which "
                "measurement condition it was measured under, and FWA "
                "compensation only fits readings taken under the "
                "instrument's own lamp (M0).")
        return tr(
            "[NOTE] Brightener compensation (FWA, -f) was left out: this "
            "measurement was taken under condition {condition}, and FWA "
            "compensation only fits readings taken under the instrument's own "
            "lamp (M0)."
        ).format(condition=self.condition or "")


#: The ``TARGET_INSTRUMENT`` values ArgyllCMS 3.5.0 applies ``-f`` to: every
#: name in its own instrument table (``strings spec2cie``) that
#: ``spec2cie -f D50`` accepted, measured 2026-11-03 (see the module text).
#: Matched exactly, as ArgyllCMS does.
ARGYLL_FWA_INSTRUMENTS = frozenset({
    "GretagMacbeth i1 Pro", "X-Rite i1 Pro", "Xrite i1 Pro",
    "X-Rite i1 Pro 2", "Xrite i1 Pro 2",
    "X-Rite i1 Pro 3", "Xrite i1 Pro 3",
    "GretagMacbeth SpectroScan", "GretagMacbeth SpectroScanT",
    "GretagMacbeth Spectrolino",
    "X-Rite DTP20", "X-Rite DTP22", "X-Rite DTP41", "X-Rite DTP51",
    "Xrite DTP20", "Xrite DTP22", "Xrite DTP41", "Xrite DTP51",
})


#: What the i1Profiler import writes when the file names no instrument
#: (``workflow.reference_convert._IMPORTED_INSTRUMENT_FALLBACK``).
_IMPORT_NAMES_NO_INSTRUMENT = "i1Profiler (unspecified)"
#: The keyword an i1Profiler import keeps i1Profiler's own instrument name
#: in (``workflow.reference_convert.I1P_INSTRUMENT_KEYWORD``): it marks the
#: file as an import.
_I1P_INSTRUMENT_KEYWORD = "CHROMIQ_I1P_INSTRUMENT"


def fwa_refusal(instrument: "str | None", *, has_spectral: bool = True,
                condition: "str | None" = None,
                i1p_import: bool = False) -> "FwaRefusal | None":
    """Whether FWA compensation can be used for a measurement whose header
    says *instrument* (``TARGET_INSTRUMENT``), *has_spectral*
    (``SPECTRAL_BANDS`` above 0) and *condition* (``MEASUREMENT_CONDITION``):
    None when it can, else the reason. When several hold, the one that
    helps most is named: the FD-9, no spectra, the instrument, the
    condition.

    None, and so nothing changed, for exactly the files ArgyllCMS applies
    ``-f`` to: a name in :data:`ARGYLL_FWA_INSTRUMENTS`, spectra, and no
    condition or M0.

    *i1p_import* says the file is an i1Profiler import (it carries
    ``CHROMIQ_I1P_INSTRUMENT``): such a file that names no condition is
    refused (review round 1, S4), because i1Profiler exports M1 and M2 as
    readily as M0, while a chartread file that names none was measured in
    the instrument's normal mode."""
    name = _unquote(instrument)
    cond = (str(condition).strip().upper() or None) if condition else None
    if name:
        from workflow.fd9.support import is_fd9_instrument_name
        if is_fd9_instrument_name(name):
            return FwaRefusal("fd9", name, cond)
    # AN IMPORT BY AN EARLIER CHROMIQ IS NAMED BEFORE "NO SPECTRA" (review
    # round 1, S2): 4.3.22 and older kept i1Profiler's name ("i1Pro 3") AND
    # left the spectra out, so "measure with an i1Pro" told the person to do
    # what they had done. Importing the .mxf again fixes both, and asks for
    # the condition.
    if name and _is_earlier_import_name(name):
        return FwaRefusal("reimport", name, cond)
    if not has_spectral:
        return FwaRefusal("no_spectra", name, cond)
    if not name or name == _IMPORT_NAMES_NO_INSTRUMENT:
        return FwaRefusal("no_name", name, cond)
    if name not in ARGYLL_FWA_INSTRUMENTS:
        if "colormunki" in name.lower():
            return FwaRefusal("colormunki", name, cond)
        return FwaRefusal("instrument", name, cond)
    if cond and cond != "M0":
        return FwaRefusal("condition", name, cond)
    if not cond and i1p_import:
        return FwaRefusal("import_condition", name, cond)
    return None


def _is_earlier_import_name(name: str) -> bool:
    """Whether *name* is i1Profiler's own name for an instrument ArgyllCMS
    knows under another ("i1Pro 3"), as imports by 4.3.22 and older wrote
    it. i1Profiler's names carry no maker; a misspelt ArgyllCMS name
    ("gretagmacbeth i1 pro") is not an import."""
    if name in ARGYLL_FWA_INSTRUMENTS:
        return False
    if name.lower().startswith(("gretagmacbeth", "x-rite", "xrite")):
        return False
    from workflow.reference_convert import argyll_instrument_name
    return argyll_instrument_name(name) in ARGYLL_FWA_INSTRUMENTS


@dataclass(frozen=True)
class _Header:
    instrument: "str | None"
    condition: "str | None"
    has_spectral: bool
    i1p_import: bool = False


def _unquote(value: "str | None") -> "str | None":
    if value is None:
        return None
    v = str(value).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1].strip()
    return v


_KW_RE = re.compile(r"^[ \t]*([A-Z_][A-Z0-9_]*)[ \t]+(.*?)[ \t]*$")


def _read_header(path) -> "_Header | None":
    """The gate's keywords from the head of the file at *path*, or None when
    there is no file to read."""
    if not path:
        return None
    try:
        p = Path(path)
        if not p.is_file():
            return None
        with open(p, "rb") as fh:
            head = fh.read(_HEAD_BYTES)
    except (OSError, TypeError, ValueError):
        return None
    # Bytes decoded as latin-1: every byte maps to one character, so a
    # cp1252 header never fails; the names compared are ASCII.
    text = head.split(b"BEGIN_DATA_FORMAT", 1)[0].decode("latin-1")
    found: dict[str, str] = {}
    for raw in text.splitlines():
        m = _KW_RE.match(raw)
        if not m:
            continue
        key = m.group(1)
        if key in ("TARGET_INSTRUMENT", "MEASUREMENT_CONDITION",
                   "SPECTRAL_BANDS", _I1P_INSTRUMENT_KEYWORD) \
                and key not in found:
            found[key] = _unquote(m.group(2)) or ""
    try:
        bands = int(found.get("SPECTRAL_BANDS") or 0)
    except ValueError:
        bands = 0
    return _Header(found.get("TARGET_INSTRUMENT"),
                   found.get("MEASUREMENT_CONDITION"), bands > 0,
                   _I1P_INSTRUMENT_KEYWORD in found)


def fwa_refusal_for_file(path) -> "FwaRefusal | None":
    """:func:`fwa_refusal` for the measurement at *path*. None for no path or
    a file that is not there (nothing loaded: nothing to refuse)."""
    h = _read_header(path)
    if h is None:
        return None
    return fwa_refusal(h.instrument, has_spectral=h.has_spectral,
                       condition=h.condition, i1p_import=h.i1p_import)


def drop_fwa(params) -> bool:
    """Take FWA compensation out of a colprof / profcheck parameter object, in
    place: the ``fwa_enabled`` switch, and any ``-f`` typed into the extra
    arguments. True when anything was removed."""
    dropped = False
    if getattr(params, "fwa_enabled", False):
        params.fwa_enabled = False
        dropped = True
    extra = getattr(params, "extra_args", "") or ""
    if extra.strip():
        try:
            toks = shlex.split(extra)
        except ValueError:      # unbalanced quotes: left as typed
            toks = None
        if toks is not None:
            # "-f", "-fD50" and the separate form "-f D50" (ArgyllCMS takes
            # both), whose value would otherwise be left behind as a stray
            # argument.
            kept = []
            skip_value = False
            for t in toks:
                if skip_value:
                    skip_value = False
                    if not t.startswith("-"):
                        continue
                if t.startswith("-f"):
                    skip_value = t == "-f"
                    continue
                kept.append(t)
            if len(kept) != len(toks):
                params.extra_args = shlex.join(kept)
                dropped = True
    return dropped


def wants_fwa(params) -> bool:
    """Whether *params* ask for ``-f``: the switch, or one typed into the
    extra arguments."""
    return bool(getattr(params, "fwa_enabled", False)) or "-f" in (
        getattr(params, "extra_args", "") or "")


def without_refused_fwa(params, keywords_from=None):
    """*params* without FWA compensation when the gate refuses it for their
    measurement, as ``(params, refusal_or_None)``: the refusal when something
    was dropped, else None. A copy is returned when anything is dropped, so
    the caller's object is left as it was. *keywords_from* is the fresh
    measurement a merge still to be made will copy its keywords from: when it
    is given and there, it is asked FIRST, because *params*' own
    ``merged.ti3`` may be a stale one from an earlier build (the command box
    would then show no ``-f`` while the build passes it, or the other way
    round). Without it, *params*' own measurement is asked."""
    if not wants_fwa(params):
        return params, None
    if keywords_from is not None and Path(keywords_from).is_file():
        asked = keywords_from
    else:
        asked = getattr(params, "ti3_path", None)
    refusal = fwa_refusal_for_file(asked)
    if refusal is None:
        return params, None
    copy = replace(params)
    return (copy, refusal) if drop_fwa(copy) else (params, None)


# ---------------------------------------------------------------------------
# The texts
# ---------------------------------------------------------------------------

def _fd9_reason() -> str:
    return tr(
        "FWA compensation is not available for FD-9 measurements.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light. FWA compensation in ArgyllCMS estimates that "
        "effect from the light inside the instrument that took the readings, "
        "and it only knows that light for the instruments it supports itself. "
        "The FD-9 is not one of them, so ArgyllCMS would stop with an error "
        "instead of building your profile or checking it.\n\n"
        "With the FD-9 you choose how the brighteners are measured before "
        "you measure, on the Measure tab (with FD-9 support on in "
        "Preferences → Beta): M0, M1 or M2. M1 is like daylight (D50) with "
        "its ultraviolet, so your readings already include the glow of the "
        "brighteners as it looks in D50 daylight. That is what FWA "
        "compensation estimates when it is set to D50, which is the default. "
        "M2 leaves the ultraviolet out, so the brighteners do not glow. To "
        "change it, measure the chart again with the other condition.\n\n"
        "The illuminant and observer options still work with FD-9 "
        "measurements.")


def _condition_reason(condition: str) -> str:
    return tr(
        "Brightener compensation (FWA) is not available for this "
        "measurement, because it was measured under condition {condition}.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation works out that glow from the lamp inside the instrument, "
        "so it only fits readings taken under that lamp: condition M0.\n\n"
        "M1 readings already include the glow as daylight (D50) shows it, and "
        "M2 readings leave the ultraviolet out, so the brighteners do not glow "
        "at all. Applying FWA compensation to either would correct something "
        "that is not there.\n\n"
        "To use FWA compensation, import the M0 readings of the same "
        "measurement (i1Profiler saves all of its conditions in one .mxf "
        "file), or measure the chart in M0."
    ).format(condition=condition)


def _no_spectra_reason() -> str:
    return tr(
        "FWA compensation is not available for this measurement, because it "
        "has no spectral readings.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation corrects for that glow by looking at the full spectrum "
        "of every patch, wavelength by wavelength. This measurement only "
        "holds colour values, for example because the instrument does not "
        "report spectra (the CR30 does not) or because the file was saved "
        "without them. So there is nothing for FWA compensation to work "
        "from, and ArgyllCMS would stop with an error instead of building "
        "your profile or checking it.\n\n"
        "To use FWA compensation, measure the chart with a spectrophotometer "
        "that saves spectral readings, such as an i1Pro.")


def _no_name_reason() -> str:
    return tr(
        "FWA compensation is not available for this measurement, because the "
        "file does not say which instrument took it.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation in ArgyllCMS works out that glow from the light inside "
        "the instrument that took the readings, and it finds that light by "
        "the instrument's name in the measurement file. Without a name, "
        "ArgyllCMS would stop with an error instead of building your profile "
        "or checking it.\n\n"
        "To use FWA compensation, measure the chart with an instrument "
        "ArgyllCMS knows the light of: the i1Pro family, the SpectroScan, "
        "the Spectrolino, or the DTP20, DTP22, DTP41 or DTP51.")


def _colormunki_reason() -> str:
    return tr(
        "FWA compensation is not available for measurements taken with a "
        "ColorMunki (also sold as i1Studio and ColorChecker Studio).\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation works out that glow from the light inside the "
        "instrument that took the readings. The ColorMunki lights the paper "
        "with a white LED that gives off no ultraviolet light, so the "
        "brighteners do not glow while it measures, and ArgyllCMS has nothing "
        "to work from: it would stop with an error instead of building your "
        "profile or checking it.\n\n"
        "Your readings show the paper as it looks under light without "
        "ultraviolet. To use FWA compensation, measure the chart with an "
        "instrument whose lamp gives off ultraviolet, such as an i1Pro.")


def _reimport_reason(instrument: str) -> str:
    return tr(
        "FWA compensation is not available for this measurement, because it "
        "was imported from i1Profiler by an earlier version of ChromIQ.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation in ArgyllCMS works out that glow from the spectrum of "
        "every patch and from the light inside the instrument that took the "
        "readings, which it finds by the instrument's name in the measurement "
        "file. The earlier import kept i1Profiler's name for the instrument, "
        "“{instrument}”, which ArgyllCMS does not know, and it may also have "
        "left the spectral readings out. With either, ArgyllCMS would stop "
        "with an error instead of building your profile or checking it.\n\n"
        "To use FWA compensation, import the i1Profiler file (.mxf or .cxf) "
        "again. ChromIQ now gives the instrument the name ArgyllCMS knows it "
        "by, keeps the spectral readings, and asks which measurement "
        "condition to import when the file holds more than one. Choose M0, "
        "because FWA compensation only works with those readings."
    ).format(instrument=instrument)


def _import_condition_reason() -> str:
    return tr(
        "FWA compensation is not available for this measurement, because it "
        "was imported from i1Profiler and the file does not say which "
        "measurement condition it was measured under.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation works out that glow from the lamp inside the "
        "instrument, so it only fits readings taken under that lamp: "
        "condition M0. i1Profiler can also save readings taken under M1 "
        "(like D50 daylight, glow included) and M2 (ultraviolet cut, no "
        "glow), and applying FWA compensation to those would correct "
        "something that is not there. Because this file does not say which "
        "one it holds, ChromIQ leaves FWA compensation off rather than "
        "guess.\n\n"
        "To use FWA compensation, import the i1Profiler .mxf or .cxf file of "
        "the same measurement and choose M0, or export the readings from "
        "i1Profiler again as M0.")


def _instrument_reason(instrument: str) -> str:
    return tr(
        "FWA compensation is not available for this measurement, because "
        "ArgyllCMS has no FWA data for the instrument it names: "
        "“{instrument}”.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation in ArgyllCMS works out that glow from the light inside "
        "the instrument that took the readings, and it finds that light by "
        "the instrument's name in the measurement file. It knows that light "
        "only for the i1Pro family, the SpectroScan, the Spectrolino and the "
        "DTP20, DTP22, DTP41 and DTP51. For any other instrument it would "
        "stop with an error instead of building your profile or checking "
        "it.\n\n"
        "To use FWA compensation, measure the chart with one of those "
        "instruments."
    ).format(instrument=instrument)
