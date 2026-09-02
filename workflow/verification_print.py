"""Printing a verification chart *through* its profile (#130, feature A).

Specification: ``docs/design/verification_printing_and_target.md`` §3–§5.

A verification grades a finished profile, but the chart ChromIQ printed for it
carried the chart's raw numbers — so the measurement described the printer,
never the profile. This module converts the chart's page TIFFs through the
run's own profile with Argyll's ``cctiff`` (sRGB → printer device, §3.2 A7);
the converted sheets then go down the **unchanged raw print path**, exactly as
Argyll's own verification loop does (``refine.html``: the chart file is
converted through the profile and the converted file is printed).

Three jobs live here, because they are three faces of one fact:

* :func:`convert_pages_through_profile` — the conversion itself (A7–A12).
* :func:`chart_conversion_state` — which kind of verification chart is loaded
  (§3.1a): a chart whose colours were already converted at *build* time by
  #133's module must print **raw**, or the profile is applied twice and the
  damage is invisible afterwards.
* :func:`write_print_record` / :func:`read_print_record` — what was actually
  done at print time (A15–A18), so a measurement's figures can be interpreted
  months later: through the profile or raw, which intent, which profile file
  (and its modification time), and whether ChromIQ printed the sheet at all.

Process model: ``subprocess.run`` with an injectable ``runner`` (the
``xicclu_runner`` house pattern) — one process per page, **never** the
ArgyllRunner QProcess singleton, and always with a ``timeout=``.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary

log = get_logger(__name__)

#: Rendering intents offered on the Print Chart tab, in display order, mapped
#: to cctiff's own ``-i`` letters. The default is relative colorimetric — the
#: usual choice for judging a profile on its own paper (§11 Q4).
INTENTS: "tuple[tuple[str, str], ...]" = (
    ("relative", "r"),
    ("absolute", "a"),
    ("perceptual", "p"),
    ("saturation", "s"),
)
DEFAULT_INTENT = "relative"

#: The two "Colour" row values (§4), stored and recorded under these names.
COLOUR_THROUGH = "through-profile"
COLOUR_RAW = "raw"

#: The two "Route" row values (§4).
ROUTE_CHROMIQ = "chromiq"
ROUTE_EXTERNAL = "external"

#: How long one page may take. ``cctiff -p`` on a 16-bit A3 page is seconds,
#: not minutes; ten minutes means something is wedged, and a subprocess with
#: no timeout has already cost this project a 2.5-hour hang.
_TIMEOUT_S = 600


def intent_letter(intent: str) -> str:
    """cctiff's ``-i`` letter for a stored intent name (defaults to relative)."""
    for name, letter in INTENTS:
        if intent == name or intent == letter:
            return letter
    return "r"


class VerificationPrintError(RuntimeError):
    """A conversion that could not run or did not finish.

    ``message_id`` names the §M message the caller shows — ``M-CM-NO-CCTIFF``
    when the tool is missing (A10), ``M-CM-CONVERT-FAILED`` when a page failed
    (A11/A12). ``page`` / ``total`` / ``reason`` fill its placeholders.
    """

    def __init__(self, message_id: str, reason: str = "",
                 page: int = 0, total: int = 0) -> None:
        super().__init__(reason or message_id)
        self.message_id = message_id
        self.reason = reason
        self.page = page
        self.total = total


def source_profile_path(bin_dir: "str | Path") -> str:
    """The sRGB source profile for the conversion (§3.2 A9).

    The chart's design values are *read as sRGB* everywhere else in ChromIQ
    (the measurement report's ``design`` reference), so the conversion must
    start from the same definition or the sheet would be the profile's answer
    to a different question. Argyll's ``ref/sRGB.icm`` first, then ChromIQ's
    bundled copy — through the shared resolver (A0.3).
    """
    from core.argyll_detect import find_ref_profile
    return find_ref_profile(bin_dir, ("sRGB.icm",))


def convert_pages_through_profile(
    pages: "Sequence[Path]",
    profile: Path,
    intent: str,
    out_dir: Path,
    *,
    bin_dir: "str | Path",
    source_profile: "str | Path | None" = None,
    runner: "Callable[..., subprocess.CompletedProcess]" = subprocess.run,
    on_page: "Callable[[int, int], None] | None" = None,
) -> "dict[Path, Path]":
    """Convert chart page TIFFs through *profile*; return ``{source: converted}``.

    All pages are converted before anything is returned, so a failure on page
    3 of 4 prints nothing (§3.2 A11 — "stop, name the page, print nothing").
    Output files keep their names inside *out_dir*, which the caller points at
    the verification cache folder — documented as always safe to delete (A8).

    Raises :class:`VerificationPrintError` with the §M message id when the
    tool is missing (A10), a page fails (A11), or the profile is unusable
    (A12 — cctiff's own error text is passed through as the reason).
    """
    pages = [Path(p) for p in pages]
    total = len(pages)
    if not total:
        return {}
    exe = Path(bin_dir) / argyll_binary("cctiff")
    if not exe.exists():
        raise VerificationPrintError("M-CM-NO-CCTIFF",
                                     f"cctiff not found in {bin_dir}")
    src = str(source_profile or "") or source_profile_path(bin_dir)
    if not src or not Path(src).exists():
        raise VerificationPrintError(
            "M-CM-CONVERT-FAILED",
            "no sRGB source profile was found beside ArgyllCMS or inside "
            "ChromIQ", page=1, total=total)
    if not Path(profile).exists():
        raise VerificationPrintError(
            "M-CM-CONVERT-FAILED",
            f"the profile file is missing: {profile}", page=1, total=total)

    from workflow.cctiff_apply import _CCTIFF_ERROR_PATTERNS, convert_args
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    letter = intent_letter(intent)
    converted: "dict[Path, Path]" = {}
    for n, page in enumerate(pages, start=1):
        if on_page is not None:
            on_page(n, total)
        out_path = out_dir / page.name
        cmd = [str(exe), *convert_args(Path(src), Path(profile), page,
                                       out_path, intent=letter)]
        log.info("verification print conversion: %s", " ".join(cmd))
        try:
            r = run_text(cmd, runner=runner, capture_output=True,
                         timeout=_TIMEOUT_S)
        except subprocess.TimeoutExpired as exc:
            raise VerificationPrintError(
                "M-CM-CONVERT-FAILED",
                f"cctiff did not finish within {_TIMEOUT_S} seconds",
                page=n, total=total) from exc
        except OSError as exc:
            raise VerificationPrintError(
                "M-CM-CONVERT-FAILED", str(exc), page=n, total=total) from exc
        output = (r.stdout or "") + "\n" + (r.stderr or "")
        if r.returncode != 0 or not out_path.exists():
            reason = ""
            for pattern, _key, fmt in _CCTIFF_ERROR_PATTERNS:
                m = pattern.search(output)
                if m:
                    reason = fmt.format(*(g or "" for g in m.groups()))
                    break
            if not reason:
                lines = [l for l in output.splitlines() if l.strip()]
                reason = lines[-1].strip() if lines else \
                    f"cctiff exited with code {r.returncode}"
            raise VerificationPrintError("M-CM-CONVERT-FAILED", reason,
                                         page=n, total=total)
        converted[page] = out_path
    return converted


# ---------------------------------------------------------------------------
# §3.1a — which kind of verification chart is loaded
# ---------------------------------------------------------------------------

#: chart_conversion_state() answers:
STATE_REGULAR = "regular"                  # §3.1b — both options live
STATE_CONVERTED = "converted"              # §3.1a A3a — force Raw, disable through
STATE_CONVERTED_REF_MISSING = "converted-reference-missing"   # A3c — same, and say so


def colorimetric_reference_for(ti2_path: Path) -> Path:
    """Where a chart's stored colorimetric reference lives: beside the chart,
    stem-coupled — ``<stem>-reference.ti3``. #133's FROM PROFILE GAMUT module
    will *write* this file; feature A only ever *reads* it. Its presence is
    the marker that the chart's device values were already converted through
    the profile at build time (§3.1a: one fact, one file, so the report's
    reference and the Print tab's Raw lock cannot drift apart)."""
    ti2_path = Path(ti2_path)
    return ti2_path.with_name(f"{ti2_path.stem}-reference.ti3")


def chart_conversion_state(ti2_path: "Path | None") -> str:
    """Whether the loaded chart already carries the profile's conversion.

    * :data:`STATE_CONVERTED` — the colorimetric reference sits beside the
      chart (A3a): force Raw and disable "through the profile".
    * :data:`STATE_CONVERTED_REF_MISSING` — the chart's ``.channels.json``
      claims a colorimetric reference but the file is gone (A3c): treated
      exactly like A3a, because refusing to convert is always the safe
      direction, and the notice says the file is missing.
    * :data:`STATE_REGULAR` — everything else (§3.1b): both options offered.
    """
    if ti2_path is None:
        return STATE_REGULAR
    ti2_path = Path(ti2_path)
    if colorimetric_reference_for(ti2_path).is_file():
        return STATE_CONVERTED
    sidecar = ti2_path.with_name(f"{ti2_path.stem}.channels.json")
    if sidecar.is_file():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if data.get("colorimetric_reference"):
            return STATE_CONVERTED_REF_MISSING
    return STATE_REGULAR


# ---------------------------------------------------------------------------
# A15–A18 — the record that makes a number interpretable
# ---------------------------------------------------------------------------

def default_colour_for_run(run) -> str:
    """The Colour default for a target with nothing stored (§11 Q3 / §5 A3.1).

    * A run with **no** verification history defaults to *through the
      profile* — the honest check, on from the start for new work.
    * A run that **has** history keeps the method that history used, so an
      existing trend does not silently change meaning: the last print record
      beside the shared verify chart decides, and a history with no record at
      all predates feature A — every such sheet was printed raw, so raw it
      stays until the user chooses otherwise.
    """
    try:
        history = run.verifications()
    except Exception:      # noqa: BLE001 — a default must never raise
        return COLOUR_THROUGH
    if not history:
        return COLOUR_THROUGH
    try:
        rec_path = print_record_path(run.verify_chart_ti2)
        if rec_path.is_file():
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            if rec.get("colour") in (COLOUR_THROUGH, COLOUR_RAW):
                return rec["colour"]
    except (OSError, ValueError):
        pass
    return COLOUR_RAW


def print_record_path(ti2_path: Path) -> Path:
    """The print record lives beside the chart it describes, stem-coupled:
    ``<stem>.print.json`` — the same placement rule as ``.channels.json``."""
    ti2_path = Path(ti2_path)
    return ti2_path.with_name(f"{ti2_path.stem}.print.json")


def write_print_record(ti2_path: Path, *, colour: str, intent: str,
                       profile: "Path | None", route: str,
                       source_profile: str = "") -> "Path | None":
    """Record how the sheet was produced (A15–A18). Returns the path, or None
    when the record could not be written (never raises — a failed record must
    not stop a print job that is already correct)."""
    rec: dict = {
        "printed_at": datetime.now().isoformat(timespec="seconds"),
        "colour": colour,                                     # A15
        "intent": intent if colour == COLOUR_THROUGH else "", # A16
        "route": route,                                       # A18
        "source_profile": str(source_profile or ""),
    }
    if profile is not None and colour == COLOUR_THROUGH:      # A17
        profile = Path(profile)
        rec["profile"] = profile.name
        rec["profile_path"] = str(profile)
        try:
            rec["profile_mtime"] = datetime.fromtimestamp(
                profile.stat().st_mtime).isoformat(timespec="seconds")
        except OSError:
            rec["profile_mtime"] = ""
    path = print_record_path(ti2_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    except OSError:
        log.warning("could not write the print record %s", path, exc_info=True)
        return None
    log.info("print record written: %s (%s, %s, %s)", path.name,
             rec["colour"], rec["intent"] or "-", rec["route"])
    return path


def record_answers_how_printed(rec: "dict | None") -> bool:
    """True when a print record actually answers "how was this sheet made?".

    The Measure tab skips the M-HOW-PRINTED question when it finds a record,
    on the reasoning that ChromIQ printed the sheet and therefore knows. That
    is only sound for a record that says two things, and a bare
    ``read_print_record(...) is not None`` checks neither:

    * **what was done** — a ``colour`` this module recognises. An empty
      object, a truncated file re-read as ``{}``, or a record with no
      ``colour`` is not an answer; it silenced the question and put nothing
      into the report, so the sheet was judged with neither a stated
      provenance nor a chance to state one.
    * **that it was done** — a ``printed_at`` (a print that happened) or a
      ``recorded`` marker (the person answered this very question at measure
      time; ``_ask_how_printed`` writes that kind and deliberately carries no
      ``printed_at``, because it does not know the print time).

    Anything else, the question is asked. That is the safe direction: being
    asked and answering "Not sure" changes nothing, while not being asked
    silently decides which yardstick every ΔE00 in the report is measured
    against (R6 F5).
    """
    if not isinstance(rec, dict):
        return False
    if rec.get("colour") not in (COLOUR_RAW, COLOUR_THROUGH):
        return False
    return bool(str(rec.get("printed_at") or "").strip()
                or str(rec.get("recorded") or "").strip())


def read_print_record(ti3_path: Path) -> "dict | None":
    """The print record for a measured verification ``.ti3``, or None.

    Mirrors ``measurement_report._find_reference_ti2``'s walk: the record may
    sit beside the ``.ti3``, in the dated verification's own ``chart/``
    snapshot, or one level up beside the shared verify chart
    (``verifications/<stem>.print.json``) — **in that order**. The snapshot
    outranks the live record: the shared record describes the LAST print of
    the chart, and after a later print the other way a dated measurement's
    report claimed the wrong method (found live, 2026-08-10: the RAW sheet's
    report said "through-profile" the moment the THROUGH sheet was printed).
    """
    ti3_path = Path(ti3_path)
    stem = ti3_path.stem
    for cand in (ti3_path.with_name(f"{stem}.print.json"),
                 ti3_path.parent / "chart" / f"{stem}.print.json",
                 ti3_path.parent.parent / f"{stem}.print.json"):
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                return data
    return None
