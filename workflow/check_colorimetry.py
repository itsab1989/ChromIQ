"""Which colour settings a profile was built with, and whether a check of it
uses the same (issue 217, 2026-11-21).

THE FAULT THIS EXISTS FOR. ArgyllCMS profcheck works the colours of a
measurement out again from its spectral readings with ITS OWN observer
(``-o``), illuminant (``-i``) and FWA compensation (``-f``), exactly as
colprof did when it fitted the profile. Check & Refine took those three from
its own controls (default 1931 2 degree, D50, no FWA), whatever Build Profile
had used. A tester built with the 2015 2 degree observer, and the check
compared that profile with 1931 2 degree colours: 1.63 average / 6.14
largest instead of 0.34 / 2.4, and Guided Refinement sent him to re-read
five good strips three times. Nothing said so.

So:

* every build records the three, as they reached colprof or the engine
  (``RunMeta.profile_build["colorimetry"]``, `record_for_build`);
* a check of that profile reads them back (`built_colorimetry`) and compares
  them with its own (`differences`), only for a measurement with spectral
  readings: without them none of the three changes a number;
* a profile that records nothing (built before this, imported, a loose
  file) is UNKNOWN, and the check behaves exactly as before.

These four values are the whole list. colprof's other options shape the
fit (quality, smoothing, gamut, intents, black generation) or the tags, not
the CIE values the profile is fitted to; the readings themselves (the M0/M1/M2
condition file) are followed by the check already (`readings_from`).
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: The key in ``RunMeta.profile_build`` (`Run.record_profile_build`).
RECORD_KEY = "colorimetry"

#: ArgyllCMS's own defaults, the same for colprof and profcheck (their usage
#: texts, 3.5.0): observer 1931 2 degree, illuminant D50, and "-f" without a
#: name simulates D50 ("D50 (def.)").
DEFAULT_OBSERVER = "1931_2"
DEFAULT_ILLUMINANT = "D50"
DEFAULT_FWA_ILLUMINANT = "D50"

#: A profile file may be written a little after the record's clock is read;
#: one modified later than this after its record was replaced by something
#: else (a copy, an import), and its record no longer describes it.
_RECORD_SLACK_S = 120.0


@dataclass(frozen=True)
class Colorimetry:
    """The three colour settings, in ArgyllCMS's terms ("" = its default)."""
    observer: str = DEFAULT_OBSERVER
    illuminant: str = DEFAULT_ILLUMINANT
    fwa: bool = False
    fwa_illum: str = DEFAULT_FWA_ILLUMINANT

    def normalised(self) -> "Colorimetry":
        obs = str(self.observer or "").strip() or DEFAULT_OBSERVER
        ill = str(self.illuminant or "").strip() or DEFAULT_ILLUMINANT
        fwa = bool(self.fwa)
        fi = (str(self.fwa_illum or "").strip() or DEFAULT_FWA_ILLUMINANT
              ) if fwa else DEFAULT_FWA_ILLUMINANT
        return Colorimetry(obs, ill, fwa, fi)

    @property
    def is_default(self) -> bool:
        return self.normalised() == Colorimetry()

    def as_record(self) -> dict:
        n = self.normalised()
        return {"observer": n.observer, "illuminant": n.illuminant,
                "fwa": n.fwa, "fwa_illum": n.fwa_illum if n.fwa else ""}

    @classmethod
    def from_record(cls, rec) -> "Colorimetry | None":
        if not isinstance(rec, dict):
            return None
        try:
            return cls(str(rec.get("observer") or ""),
                       str(rec.get("illuminant") or ""),
                       bool(rec.get("fwa")),
                       str(rec.get("fwa_illum") or "")).normalised()
        except Exception:      # noqa: BLE001 - a damaged record is no record
            return None

    def for_log(self) -> str:
        """One English line for the app log."""
        n = self.normalised()
        fwa = f"on ({n.fwa_illum})" if n.fwa else "off"
        return (f"observer {n.observer}, illuminant {n.illuminant}, "
                f"FWA compensation {fwa}")


# ---------------------------------------------------------------------------
# What a build used
# ---------------------------------------------------------------------------

def _overlay_extra_args(c: Colorimetry, extra: str) -> Colorimetry:
    """The hand-typed extra arguments win, as they do on colprof's command
    line (they come after the tab's own) and in the engine
    (`engine_builder._apply_extra_args`)."""
    try:
        toks = shlex.split(extra or "")
    except ValueError:
        return c
    obs, ill, fwa, fi = c.observer, c.illuminant, c.fwa, c.fwa_illum
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if t in ("-i", "-o") and nxt is not None and not nxt.startswith("-"):
            if t == "-i":
                ill = nxt
            else:
                obs = nxt
            i += 2
            continue
        if t.startswith("-i") and len(t) > 2:
            ill = t[2:]
        elif t.startswith("-o") and len(t) > 2:
            obs = t[2:]
        elif t.startswith("-f"):
            fwa = True
            fi = t[2:]
        i += 1
    return Colorimetry(obs, ill, fwa, fi)


def from_profile_params(params) -> Colorimetry:
    """What a Build Profile build passes on (`ProfileParams`), after the FWA
    gate (`workflow.fwa_gate.without_refused_fwa`, the same call both
    builders make) and with the extra arguments laid over it."""
    p = params
    try:
        from workflow.fwa_gate import without_refused_fwa
        p, _ = without_refused_fwa(params)
    except Exception:      # noqa: BLE001 - the settings as given, then
        p = params
    c = Colorimetry(getattr(p, "observer", "") or "",
                    getattr(p, "illuminant", "") or "",
                    bool(getattr(p, "fwa_enabled", False)),
                    getattr(p, "fwa_illum", "") or "")
    return _overlay_extra_args(c, getattr(p, "extra_args", "") or "")


def record_for_build(params) -> dict:
    """``{RECORD_KEY: {...}}`` for `Run.record_profile_build`."""
    return {RECORD_KEY: from_profile_params(params).as_record()}


def from_check_params(params) -> Colorimetry:
    """What a check passes to profcheck (`ProfcheckParams`)."""
    return Colorimetry(params.observer or "", params.illum or "",
                       bool(params.fwa_enabled), params.fwa_illum or "")


# ---------------------------------------------------------------------------
# What a profile was built with
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Built:
    """The answer of `built_colorimetry`: *colorimetry* None = unknown, and
    *why* then says why in English for the app log."""
    colorimetry: "Colorimetry | None"
    why: str = ""

    @property
    def known(self) -> bool:
        return self.colorimetry is not None

    def for_log(self) -> str:
        return (self.colorimetry.for_log() if self.colorimetry is not None
                else f"unknown ({self.why})")


def _parse_at(text) -> "float | None":
    try:
        return datetime.fromisoformat(str(text).strip()).timestamp()
    except (TypeError, ValueError):
        return None


def built_colorimetry(icc_path) -> Built:
    """The colour settings *icc_path* was built with, read from the record of
    the run it lies in. Unknown unless that run's last build record names
    this very file, carries the settings, and is not older than the file."""
    if not icc_path:
        return Built(None, "no profile")
    icc = Path(icc_path)
    try:
        from core.file_manager import Run
        run = Run.for_dir(icc.parent)
        if not run.meta_path.is_file():
            return Built(None, "the profile is not in a ChromIQ run folder")
        rec = dict(getattr(run.load_meta(), "profile_build", None) or {})
    except Exception as exc:      # noqa: BLE001 - not knowing is an answer
        return Built(None, f"the run's record could not be read: {exc}")
    if not rec:
        return Built(None, "the run records no profile build")
    if str(rec.get("profile") or "") != icc.name:
        return Built(None, f"the run's last build made {rec.get('profile')!r}, "
                           f"not this file")
    col = Colorimetry.from_record(rec.get(RECORD_KEY))
    if col is None:
        return Built(None, "built before ChromIQ recorded the colour settings")
    at = _parse_at(rec.get("at"))
    try:
        mtime = icc.stat().st_mtime
    except OSError:
        return Built(None, "the profile cannot be read")
    if at is not None and mtime > at + _RECORD_SLACK_S:
        return Built(None, "the profile was changed after its build was "
                           "recorded")
    return Built(col)


def has_spectral(ti3_path) -> bool:
    """Whether a measurement carries spectral readings (``SPECTRAL_BANDS``).
    Without them profcheck and colprof use the file's own CIE values and the
    three settings change nothing."""
    try:
        from core.text_io import read_text
        head = read_text(Path(ti3_path), lenient=True)[:20000]
    except (OSError, TypeError, ValueError):
        return False
    return re.search(r"^\s*SPECTRAL_BANDS\b", head, re.M) is not None


def differences(built: Colorimetry, check: Colorimetry) -> "list[str]":
    """Which of ``observer`` / ``illuminant`` / ``fwa`` differ, normalised
    (so "" and "1931_2" are the same observer)."""
    a, b = built.normalised(), check.normalised()
    out = []
    if a.observer != b.observer:
        out.append("observer")
    if a.illuminant != b.illuminant:
        out.append("illuminant")
    if a.fwa != b.fwa or (a.fwa and a.fwa_illum != b.fwa_illum):
        out.append("fwa")
    return out


def apply_to_check(params, built: Colorimetry):
    """*params* (`ProfcheckParams`) with the profile's own colour settings."""
    n = built.normalised()
    return replace(params, observer=n.observer, illum=n.illuminant,
                   fwa_enabled=n.fwa, fwa_illum=n.fwa_illum)


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------

_OBSERVER_NAMES = {
    "1931_2": "CIE 1931 2°",
    "1964_10": "CIE 1964 10°",
    "2015_2": "CIE 2015 2°",
    "2015_10": "CIE 2015 10°",
    "shaw": "Shaw & Fairchild",
}


def describe(c: Colorimetry) -> str:
    """One translated line: "observer CIE 2015 2°, illuminant D50, FWA
    compensation off"."""
    from core.i18n import tr
    n = c.normalised()
    fwa = (tr("on, simulating {illuminant}").format(illuminant=n.fwa_illum)
           if n.fwa else tr("off"))
    return tr("observer {observer}, illuminant {illuminant}, FWA "
              "compensation {fwa}").format(
        observer=_OBSERVER_NAMES.get(n.observer, n.observer),
        illuminant=n.illuminant, fwa=fwa)


def check_log_line(built: Built, check: Colorimetry, *, spectral: bool,
                   mismatch: bool, choice: str = "",
                   tab: "Colorimetry | None" = None) -> str:
    """The app log's line for one check (owner's ask (a), 2026-11-21): what
    the profile was built with, what the check used, and, when they
    differed, that the warning was shown and what was chosen."""
    parts = [f"profile built with: {built.for_log()}"]
    if tab is not None and tab.normalised() != check.normalised():
        parts.append(f"tab set to: {tab.for_log()}")
    parts.append(f"check uses: {check.for_log()}")
    if not spectral:
        parts.append("the measurement has no spectral readings, so these "
                     "settings change no number")
    elif mismatch:
        parts.append(f"they differ: warning shown, chosen: {choice or '-'}")
    elif built.known:
        parts.append("they match")
    return "Check colour settings: " + "; ".join(parts)


def follow_profile(params, where: str):
    """``(params, note)`` for a check that has no colour controls of its own
    (Tools ▸ Verify profile, Inspect a measurement against a profile): the
    profile's recorded settings when they are known and the measurement has
    spectral readings, else *params* unchanged. *note* is one translated
    line for the window's log when the settings were changed ("" else); the
    app log gets `check_log_line` either way, starting with *where*."""
    try:
        built = built_colorimetry(params.icc_path)
        spectral = has_spectral(params.readings_from or params.ti3_path)
    except Exception:      # noqa: BLE001 - never stop a check over this
        log.debug("colour settings not compared", exc_info=True)
        return params, ""
    note = ""
    if (spectral and built.known
            and differences(built.colorimetry, from_check_params(params))):
        params = apply_to_check(params, built.colorimetry)
        from core.i18n import tr
        note = tr("This profile was built with {settings}, so the check uses "
                  "the same settings.").format(
                      settings=describe(built.colorimetry))
    log.info("%s: %s", where, check_log_line(
        built, from_check_params(params), spectral=spectral, mismatch=False))
    return params, note
