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

The reasons, each measured rather than assumed:

* **The instrument ArgyllCMS cannot place.** ArgyllCMS models the brighteners'
  glow from the lamp of the instrument that took the readings and finds that
  lamp by ``TARGET_INSTRUMENT``. The Konica Minolta FD-9 is not one it knows:
  ``colprof -f`` stops with "Unrecognised target instrument 'Konica Minolta
  FD-9'" (ArgyllCMS 3.5.0, 2026-11-03, both spellings), while ``-i`` and
  ``-o`` work on the same file. Not behind the Beta switch: the refusal is
  ArgyllCMS's, and the file stays what it is after the Beta is turned off.
* **The measurement condition.** The model only fits readings taken under the
  instrument's own lamp, M0. A file that SAYS it is M1 or M2
  (``MEASUREMENT_CONDITION``, ``workflow.measurement_condition``) would have a
  glow corrected that is not there in the form the model assumes (measured on
  jctay's M2 readings: ``spec2cie -f`` moved them by 0.37 mean / 0.72 max
  dE76 for nothing). A file that names no condition is judged as before.

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

    *kind* is one of ``"fd9"`` (an FD-9 measurement) or ``"condition"`` (an
    M1/M2 measurement); *instrument* and *condition* are what the file
    says."""
    kind: str
    instrument: "str | None" = None
    condition: "str | None" = None

    @property
    def reason(self) -> str:
        """The tooltip on the greyed FWA box and its illuminant."""
        if self.kind == "fd9":
            return _fd9_reason()
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
        return tr(
            "[NOTE] Brightener compensation (FWA, -f) was left out: this "
            "measurement was taken under condition {condition}, and FWA "
            "compensation only fits readings taken under the instrument's own "
            "lamp (M0)."
        ).format(condition=self.condition or "")


def fwa_refusal(instrument: "str | None", *,
                condition: "str | None" = None) -> "FwaRefusal | None":
    """Whether FWA compensation can be used for a measurement whose header
    says *instrument* (``TARGET_INSTRUMENT``) and *condition*
    (``MEASUREMENT_CONDITION``): None when it can, else the reason."""
    name = _unquote(instrument)
    cond = (str(condition).strip().upper() or None) if condition else None
    if name:
        from workflow.fd9.support import is_fd9_instrument_name
        if is_fd9_instrument_name(name):
            return FwaRefusal("fd9", name, cond)
    if cond and cond != "M0":
        return FwaRefusal("condition", name, cond)
    return None


@dataclass(frozen=True)
class _Header:
    instrument: "str | None"
    condition: "str | None"


def _unquote(value: "str | None") -> "str | None":
    if value is None:
        return None
    v = str(value).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1].strip()
    return v


_KW_RE = re.compile(rb"^[ \t]*([A-Z_][A-Z0-9_]*)[ \t]+(.*?)[ \t]*$")


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
    head = head.split(b"BEGIN_DATA_FORMAT", 1)[0]
    found: dict[str, str] = {}
    for raw in head.splitlines():
        m = _KW_RE.match(raw)
        if not m:
            continue
        key = m.group(1).decode("ascii", "replace")
        if key in ("TARGET_INSTRUMENT", "MEASUREMENT_CONDITION") \
                and key not in found:
            found[key] = _unquote(m.group(2).decode("latin-1")) or ""
    return _Header(found.get("TARGET_INSTRUMENT"),
                   found.get("MEASUREMENT_CONDITION"))


def fwa_refusal_for_file(path) -> "FwaRefusal | None":
    """:func:`fwa_refusal` for the measurement at *path*. None for no path or
    a file that is not there (nothing loaded: nothing to refuse)."""
    h = _read_header(path)
    if h is None:
        return None
    return fwa_refusal(h.instrument, condition=h.condition)


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
