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
  (``RunMeta.profile_build["colorimetry"]``, `record_for_build`), with the
  profile file's size and SHA-256, so the record is only ever read for the
  very file it was written for (`fingerprint`); a calibrated copy
  (applycal) and colprof's comparison profile are recorded beside it under
  ``"derived"`` (`record_derived`);
* a check of that profile reads them back (`built_colorimetry`) and compares
  them with its own (`differences`), only for a measurement with spectral
  readings: without them none of the three changes a number;
* a profile that records nothing (built before this, imported, a loose
  file) is UNKNOWN, and the check behaves exactly as before.

FWA: a plain ``-f`` simulates the ``-i`` illuminant, not D50. Measured with
ArgyllCMS 3.5.0 colprof on the repo's spectral test file (issue 217 review,
and again for this module): "-i D65 -f" fits exactly like "-i D65 -fD65"
and not like "-i D65 -fD50"; "-i A -f -i D65" like "-i D65 -f" (the -f
illuminant is settled after every argument is read); "-fD65 -f" like
"-fD65" (a later plain -f keeps the name); "-f D65" (two arguments) like
"-fD65"; "-o 1964_10 -o 2015_2" like "-o 2015_2" (the last one wins). The
Build tab's "Same as illuminant (-i)" says the same; so does the engine
(`profile_engine/spectral.py`: ``fwa_illum or illuminant``).

These four values are the whole list. colprof's other options shape the
fit (quality, smoothing, gamut, intents, black generation) or the tags, not
the CIE values the profile is fitted to; the readings themselves (the M0/M1/M2
condition file) are followed by the check already (`readings_from`).
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, replace
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: The key in ``RunMeta.profile_build`` (`Run.record_profile_build`).
RECORD_KEY = "colorimetry"

#: ArgyllCMS's own defaults, the same for colprof and profcheck (their usage
#: texts, 3.5.0): observer 1931 2 degree, illuminant D50. "-f" without a name
#: simulates the -i illuminant (see the module text).
DEFAULT_OBSERVER = "1931_2"
DEFAULT_ILLUMINANT = "D50"

#: The record's key for colour-settings records of profiles made FROM the
#: run's profile (calibrated.icc) or beside it (the colprof comparison).
DERIVED_KEY = "derived"


def is_file_value(value) -> bool:
    """A value that names a file (a ``.sp`` illuminant, a ``.cmf`` observer)
    rather than one of ArgyllCMS's names. The check's controls cannot carry
    one, and its path is never written anywhere (privacy rule)."""
    v = str(value or "").strip()
    return bool(v) and ("/" in v or "\\" in v
                        or v.lower().endswith((".sp", ".cmf")))


def _shown(value) -> str:
    """A value as it may be written down: a file by its name only."""
    v = str(value or "").strip()
    return Path(v.replace("\\", "/")).name if is_file_value(v) else v


def fingerprint(path) -> dict:
    """``{"profile_size", "profile_sha256"}`` of a profile file, {} when it
    cannot be read. As the confirmed-patches file pins its .ti3."""
    import hashlib
    try:
        data = Path(path).read_bytes()
    except OSError:
        return {}
    return {"profile_size": len(data),
            "profile_sha256": hashlib.sha256(data).hexdigest()}


@dataclass(frozen=True)
class Colorimetry:
    """The three colour settings, in ArgyllCMS's terms ("" = its default)."""
    observer: str = DEFAULT_OBSERVER
    illuminant: str = DEFAULT_ILLUMINANT
    fwa: bool = False
    #: "" = simulate the -i illuminant, as ArgyllCMS reads a plain -f
    fwa_illum: str = ""

    def normalised(self) -> "Colorimetry":
        obs = str(self.observer or "").strip() or DEFAULT_OBSERVER
        ill = str(self.illuminant or "").strip() or DEFAULT_ILLUMINANT
        fwa = bool(self.fwa)
        fi = (str(self.fwa_illum or "").strip() or ill) if fwa else ""
        return Colorimetry(obs, ill, fwa, fi)

    @property
    def files(self) -> "tuple[str, ...]":
        """The values that name a file, by file name."""
        n = self.normalised()
        vals = [n.observer, n.illuminant] + ([n.fwa_illum] if n.fwa else [])
        return tuple(dict.fromkeys(_shown(v) for v in vals
                                   if is_file_value(v)))

    @property
    def is_default(self) -> bool:
        return self.normalised() == Colorimetry()

    def as_record(self) -> dict:
        """File values by their NAME only (privacy rule), marked
        ``"files"``: such a record can be described, not reproduced."""
        n = self.normalised()
        rec = {"observer": _shown(n.observer),
               "illuminant": _shown(n.illuminant),
               "fwa": n.fwa, "fwa_illum": _shown(n.fwa_illum)}
        if self.files:
            rec["files"] = list(self.files)
        return rec

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
        fwa = f"on, simulating {_shown(n.fwa_illum)}" if n.fwa else "off"
        return (f"observer {_shown(n.observer)}, illuminant "
                f"{_shown(n.illuminant)}, FWA compensation {fwa}")


# ---------------------------------------------------------------------------
# What a build used
# ---------------------------------------------------------------------------

def _overlay_extra_args(c: Colorimetry, extra: str) -> Colorimetry:
    """The hand-typed extra arguments win, as they do on colprof's command
    line (they come after the tab's own; the base name follows them, so a
    value after the last flag is still that flag's). As colprof reads them
    (measured, see the module text): ``-i X`` / ``-iX`` and ``-o X`` /
    ``-oX``, the last one wins; ``-f`` switches FWA on and keeps any name
    given before; ``-fX`` / ``-f X`` names the simulated illuminant."""
    try:
        toks = shlex.split(extra or "")
    except ValueError:
        return c
    obs, ill, fwa, fi = c.observer, c.illuminant, c.fwa, c.fwa_illum
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        value_next = nxt is not None and not nxt.startswith("-")
        if t in ("-i", "-o", "-f") and value_next:
            if t == "-i":
                ill = nxt
            elif t == "-o":
                obs = nxt
            else:
                fwa, fi = True, nxt
            i += 2
            continue
        if t.startswith("-i") and len(t) > 2:
            ill = t[2:]
        elif t.startswith("-o") and len(t) > 2:
            obs = t[2:]
        elif t == "-f":
            fwa = True
        elif t.startswith("-f"):
            fwa, fi = True, t[2:]
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


def stamp(path) -> "int | None":
    """A file's modification time in nanoseconds, None when it is absent."""
    try:
        return Path(path).stat().st_mtime_ns
    except (OSError, TypeError, ValueError):
        return None


#: A file system's clock may lag the process's by a little.
_CLOCK_SLACK_NS = 2_000_000_000


def written_since(path, before: "int | None", started_ns: int) -> bool:
    """Whether *path* was written by the tool run that started at
    *started_ns* (`time.time_ns()`), its stamp before that run being
    *before* (`stamp`): it exists, its stamp changed, and it is not older
    than the run (verification V1: a tool that REPORTS a path is not one
    that wrote it)."""
    now = stamp(path)
    return (now is not None and now != before
            and now >= started_ns - _CLOCK_SLACK_NS)


def record_derived(out_icc, colorimetry: "Colorimetry | None",
                   source: str = "") -> bool:
    """Record the colour settings of a profile made from or beside the run's
    own (applycal's calibrated.icc keeps its source's settings; colprof's
    comparison profile is built with the same ones), with its fingerprint,
    under ``profile_build["derived"][<name>]``. Only inside a run, never
    raises; a later build replaces the whole record and drops these."""
    if colorimetry is None:
        return False
    try:
        from core.file_manager import Run
        out = Path(out_icc)
        run = Run.for_dir(out.parent)
        if not run.meta_path.is_file():
            return False
        fp = fingerprint(out)
        if not fp:
            return False
        meta = run.load_meta()
        rec = dict(getattr(meta, "profile_build", None) or {})
        derived = dict(rec.get(DERIVED_KEY) or {})
        derived[out.name] = {RECORD_KEY: colorimetry.as_record(),
                             "from": _shown(source), **fp}
        rec[DERIVED_KEY] = derived
        meta.profile_build = rec
        run.save_meta(meta)
        return True
    except Exception:      # noqa: BLE001 - a record never fails its tool
        log.warning("could not record the colour settings of %s", out_icc,
                    exc_info=True)
        return False


def from_check_params(params) -> Colorimetry:
    """What a check passes to profcheck (`ProfcheckParams`)."""
    return Colorimetry(params.observer or "", params.illum or "",
                       bool(params.fwa_enabled), params.fwa_illum or "")


# ---------------------------------------------------------------------------
# What a profile was built with
# ---------------------------------------------------------------------------

#: Why a profile's colour settings are not known (`Built.reason`).
UNKNOWN_NO_RECORD = "no_record"        # no run, or the run records no build
UNKNOWN_OLD = "old"                    # recorded before the settings were
UNKNOWN_OTHER_FILE = "other_file"      # the record is about another file
UNKNOWN_CHANGED = "changed"            # this file is not the one recorded
UNKNOWN_FILES = "files"                # built with a .sp / .cmf file


@dataclass(frozen=True)
class Built:
    """The answer of `built_colorimetry`: *colorimetry* None = unknown, and
    *why* then says why in English for the app log, *reason* is one of the
    ``UNKNOWN_*`` codes, *other* the file the record is about
    (`UNKNOWN_OTHER_FILE`) and *files* the file names (`UNKNOWN_FILES`)."""
    colorimetry: "Colorimetry | None"
    why: str = ""
    reason: str = ""
    other: str = ""
    files: "tuple[str, ...]" = ()

    @property
    def known(self) -> bool:
        return self.colorimetry is not None

    def for_log(self) -> str:
        return (self.colorimetry.for_log() if self.colorimetry is not None
                else f"unknown ({self.why})")


def built_colorimetry(icc_path) -> Built:
    """The colour settings *icc_path* was built with, read from the record of
    the run it lies in: the last build's (``profile`` names this file) or a
    derived profile's (``derived``). Unknown unless that record carries the
    settings and this file has exactly the size and SHA-256 recorded for it
    (no time window: a file put back from old/ or copied in is not the one
    the record describes)."""
    if not icc_path:
        return Built(None, "no profile", UNKNOWN_NO_RECORD)
    icc = Path(icc_path)
    try:
        from core.file_manager import Run
        run = Run.for_dir(icc.parent)
        if not run.meta_path.is_file():
            return Built(None, "the profile is not in a ChromIQ run folder",
                         UNKNOWN_NO_RECORD)
        rec = dict(getattr(run.load_meta(), "profile_build", None) or {})
    except Exception as exc:      # noqa: BLE001 - not knowing is an answer
        return Built(None, f"the run's record could not be read: {exc}",
                     UNKNOWN_NO_RECORD)
    if not rec:
        return Built(None, "the run records no profile build",
                     UNKNOWN_NO_RECORD)
    entry = None
    if str(rec.get("profile") or "") == icc.name:
        entry = rec
    else:
        d = (rec.get(DERIVED_KEY) or {}).get(icc.name)
        if isinstance(d, dict):
            entry = d
    if entry is None:
        other = _shown(rec.get("profile") or "")
        return Built(None, f"the run's record is about {other!r}, not this "
                           f"file", UNKNOWN_OTHER_FILE, other=other)
    raw = entry.get(RECORD_KEY)
    col = Colorimetry.from_record(raw)
    if col is None:
        return Built(None, "built before ChromIQ recorded the colour settings",
                     UNKNOWN_OLD)
    if not entry.get("profile_sha256"):
        # only this branch's first, never released, commit wrote such
        return Built(None, "the record does not identify the file (no size "
                           "or SHA-256)", UNKNOWN_OLD)
    fp = fingerprint(icc)
    if (not fp or entry.get("profile_sha256") != fp["profile_sha256"]
            or entry.get("profile_size") != fp["profile_size"]):
        return Built(None, "this file is not the one its build recorded "
                           "(size or SHA-256 differ)", UNKNOWN_CHANGED)
    files = tuple((raw or {}).get("files") or ())
    if files:
        return Built(None, "built with a spectral file the check cannot "
                           f"select ({', '.join(files)})", UNKNOWN_FILES,
                     files=files)
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
    """*params* (`ProfcheckParams`) with the profile's own colour settings.
    The FWA illuminant is passed by name (``-fD65`` for a build's plain
    ``-f`` with ``-i D65``), which profcheck reads exactly alike."""
    n = built.normalised()
    return replace(params, observer=n.observer, illum=n.illuminant,
                   fwa_enabled=n.fwa, fwa_illum=n.fwa_illum or n.illuminant)


def as_run(params):
    """*params* as profcheck will really receive them: after the FWA gate
    (`workflow.fwa_gate.without_refused_fwa`, which `ProfcheckRunner.run`
    applies too), so a log line never names an -f that is left out."""
    try:
        from workflow.fwa_gate import without_refused_fwa
        return without_refused_fwa(params)[0]
    except Exception:      # noqa: BLE001
        return params


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
    fwa = (tr("on, simulating {illuminant}").format(
               illuminant=_shown(n.fwa_illum)) if n.fwa else tr("off"))
    return tr("observer {observer}, illuminant {illuminant}, FWA "
              "compensation {fwa}").format(
        observer=_OBSERVER_NAMES.get(n.observer, _shown(n.observer)),
        illuminant=_shown(n.illuminant), fwa=fwa)


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
    elif built.known and differences(built.colorimetry, check):
        parts.append("FWA compensation left out: this measurement cannot "
                     "use it (FWA gate)")
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
        used = from_check_params(as_run(params))
        if differences(built.colorimetry, used):
            # the FWA gate leaves -f out for this measurement
            note = tr("This profile was built with {settings}. The check "
                      "uses {used}: FWA compensation is left out, because "
                      "this measurement cannot use it.").format(
                          settings=describe(built.colorimetry),
                          used=describe(used))
        else:
            note = tr("This profile was built with {settings}, so the check "
                      "uses the same settings.").format(
                          settings=describe(built.colorimetry))
    log.info("%s: %s", where, check_log_line(
        built, from_check_params(as_run(params)), spectral=spectral,
        mismatch=False))
    return params, note
