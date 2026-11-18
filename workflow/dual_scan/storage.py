"""WHERE AN i1Pro 2 DUAL SCAN'S THREE CONDITIONS LIVE, AND WHAT IS RECORDED.

THE SAME FILES AS THE i1Pro 3 BETA, NOT A SECOND MECHANISM. The main file
``<stem>.ti3`` holds the lamp pass, M0, exactly as an ordinary i1Pro 2
reading. M1 and M2 are written by the chart-reading engine in the same
autosave into the run's ``conditions/<hash>-M1.ti3`` and ``-M2.ti3``, named by
the main file's readings (:func:`workflow.i1pro3_conditions.data_block_hash`),
with ``MEASUREMENT_CONDITION`` and ``CHROMIQ_CONDITION_OF``: exactly the form
"X-Rite i1Pro 3: keep M0, M1 and M2 from every scan" uses
(:mod:`workflow.i1pro3_conditions`, the helper's ``cq_cond_*``). So choosing a
condition in Build Profile, the reports, averaging, verifications and the
IMPORT comparisons work on them unchanged. The engine is asked for it with
``--condition-dir`` (as for the i1Pro 3) plus :func:`helper_args`.

WHAT EVERY FILE OF SUCH A MEASUREMENT RECORDS (main and both condition
files, header keywords written by the engine from the session's start):

* ``CHROMIQ_DUAL_SCAN "i1pro2"``: it was a dual scan;
* ``CHROMIQ_DUAL_SCALE "1.1560"`` and ``CHROMIQ_DUAL_SCALE_SOURCE
  "standard" | "refined"``: the glow factor used and where it came from
  (:mod:`workflow.dual_scan.scale`);
* ``CHROMIQ_DUAL_WHITE "instrument" | "table"``: the white reference (the
  i1Pro 2's own tile, or the i1iO 2 table's);
* ``CHROMIQ_DUAL_CHOSEN "M0" | "M1" | "M2"``: the condition the person
  chose in the Measure tab's filter row. The main file itself stays
  PHYSICALLY M0 (the lamp passes: the only condition that is true for every
  strip at every autosave and resume); Build Profile is pre-set to the
  choice once every strip has both passes (:func:`build_from_preset`);
* the instrument as every measurement records it (``TARGET_INSTRUMENT``):
  NO serial number and no instrument key in any measurement file. A refined
  factor is kept per instrument in the app's settings under a key made with
  a secret that is random per installation (:func:`instrument_key`), never
  in a file that is shared.

NEVER MIXED. A measurement started as a dual scan is continued only as a
dual scan, and the other way round, and only with the factor, its source and
the white reference it was started with (:func:`start_guard`, asked before
START like the table drive's white-reference rule: ``mixed_scan_kind`` /
``mixed_factor``; :func:`continuation_choice` gives the factor to continue
with). The engine refuses it a second time: a dual measurement continued as
a single scan or with another factor stops before anything is read (error
``mixed_scan_kind`` / ``mixed_factor``); a single-scan measurement continued
as a dual scan keeps going as M0 only (conditions ``why: "mixed"``).
Averaging follows the same rule (:func:`average_guard`). A dual reading is
taken only after a dual calibration made at the same exposure, and a change
of reading mode in either direction needs a new calibration
(:func:`calibration_fits`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workflow.dual_scan.scale import (
    REFINED_SOURCE, STANDARD_SOURCE, ScaleChoice)

#: the helper's capability word for keeping dual-scan conditions (step 1:
#: the arithmetic and the files; readings come only from the replay)
CAPABILITY = "i1pro2_dual_conditions"
#: the word a later helper will add when it can drive the UV LED of a real
#: i1Pro 2 (NEXT_STEPS.md). The app offers dual scan only with BOTH.
DEVICE_CAPABILITY = "i1pro2_dual_scan"

DUAL_KEYWORD = "CHROMIQ_DUAL_SCAN"
SCALE_KEYWORD = "CHROMIQ_DUAL_SCALE"
SOURCE_KEYWORD = "CHROMIQ_DUAL_SCALE_SOURCE"
WHITE_KEYWORD = "CHROMIQ_DUAL_WHITE"
CHOSEN_KEYWORD = "CHROMIQ_DUAL_CHOSEN"
WHITES = ("instrument", "table")
CHOICES = ("M0", "M1", "M2")

#: AppSettings key of the refined factors: {instrument_key: {"value", "when"}}
REFINED_SETTING = "i1pro2_dual_scale_refined"
#: AppSettings key of this installation's random secret for instrument keys
KEY_SECRET_SETTING = "i1pro2_dual_key_secret"


@dataclass(frozen=True)
class DualRecord:
    dual: bool
    scale: "float | None" = None
    source: str = ""
    white: str = ""
    #: the person's choice is a record, not part of the measurement's kind
    #: or factor: it may change between sittings and never mixes values
    chosen: str = field(default="", compare=False)

    def same_factor(self, other: "DualRecord") -> bool:
        """The same factor (to the 4 decimals the files hold), source and
        white reference."""
        if self.scale is None or other.scale is None:
            return False
        return (round(self.scale, 4) == round(other.scale, 4)
                and self.source == other.source and self.white == other.white)


def read_dual_record(ti3: "str | Path | None") -> DualRecord:
    """What a measurement file says about a dual scan (header only)."""
    from workflow.measurement_condition import read_header_keyword
    if not ti3 or not Path(ti3).is_file():
        return DualRecord(False)
    kind = (read_header_keyword(ti3, DUAL_KEYWORD) or "").strip()
    if not kind:
        return DualRecord(False)
    try:
        s = float((read_header_keyword(ti3, SCALE_KEYWORD) or "").strip())
    except ValueError:
        s = None
    return DualRecord(True, s,
                      (read_header_keyword(ti3, SOURCE_KEYWORD) or "").strip(),
                      (read_header_keyword(ti3, WHITE_KEYWORD) or "").strip(),
                      (read_header_keyword(ti3, CHOSEN_KEYWORD) or "").strip().upper())


def _has_readings(ti3: Path) -> bool:
    try:
        text = ti3.read_text(encoding="latin-1")
    except OSError:
        return False
    if "\nBEGIN_DATA\n" not in text.replace("\r", ""):
        return False
    block = text.replace("\r", "").split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    return any(ln.strip() for ln in block.splitlines())


def start_guard(main_ti3: "str | Path | None", dual: bool,
                choice: "ScaleChoice | None" = None,
                white: "str | None" = None) -> "str | None":
    """Before START: None when this session may write into *main_ti3*, else
    a reason id:

    * ``"mixed_scan_kind"``: a dual-scan session on single-scan readings, or
      a single-scan session on dual-scan readings;
    * ``"mixed_factor"``: a dual-scan session whose factor (*choice*: value
      and source) or *white* reference is not the one the measurement was
      started with (review of 2026-11-18, M1: one file, one factor). Use
      :func:`continuation_choice` to continue with the measurement's own.

    A file with no readings yet, or none at all, is never refused."""
    if not main_ti3:
        return None
    p = Path(main_ti3)
    if not p.is_file() or not _has_readings(p):
        return None
    rec = read_dual_record(p)
    if rec.dual != bool(dual):
        return "mixed_scan_kind"
    if dual and choice is not None:
        now = DualRecord(True, float(choice.value), choice.source,
                         white if white is not None else rec.white)
        if not rec.same_factor(now):
            return "mixed_factor"
    return None


def continuation_choice(main_ti3: "str | Path | None") -> "tuple[ScaleChoice, str] | None":
    """The factor and white reference a dual measurement was started with
    (what Continue Measurement must pass again), or None when *main_ti3* is
    not a dual measurement with readings or records no usable factor."""
    if not main_ti3 or not Path(main_ti3).is_file() or not _has_readings(Path(main_ti3)):
        return None
    rec = read_dual_record(main_ti3)
    if not rec.dual or rec.scale is None or rec.source not in (STANDARD_SOURCE, REFINED_SOURCE) \
            or rec.white not in WHITES:
        return None
    return ScaleChoice(rec.scale, rec.source), rec.white


def average_guard(reads: "list[str | Path]") -> "str | None":
    """Before averaging several reads of one run: None when they may be
    averaged in every condition, else ``"mixed_scan_kind"`` (dual and single
    reads together) or ``"mixed_factor"`` (dual reads made with different
    factors or white references). Averaging the main files (M0) is not
    affected: M0 does not depend on the factor; only the M1 / M2 averages
    are refused (:func:`workflow.i1pro3_conditions.average_conditions`)."""
    recs = [read_dual_record(r) for r in reads]
    if not recs or not any(r.dual for r in recs):
        return None
    if not all(r.dual for r in recs):
        return "mixed_scan_kind"
    first = recs[0]
    return None if all(first.same_factor(r) for r in recs[1:]) else "mixed_factor"


def calibration_fits(calibration_mode: "str | None", reading_mode: str, *,
                     calibration_clocks: "tuple[int | None, int | None]" = (None, None),
                     reading_clocks: "tuple[int | None, int | None]" = (None, None),
                     ) -> "str | None":
    """Whether a calibration may serve a reading. Modes: ``"single"`` (lamp
    only) and ``"dual"`` (lamp + the UV LED on the tile); clocks: (lamp, UV)
    integration. None = fits, else a reason id:

    * a dual reading after no calibration or a single-scan one:
      ``"no_dual_calibration"`` (i1Profiler's own b1 file: 15 % too bright);
    * any change of mode since the calibration, in either direction:
      ``"calibration_mode_changed"`` (calibrate again);
    * the same mode at another integration: ``"calibration_mismatch"``."""
    if reading_mode not in ("single", "dual"):
        raise ValueError(reading_mode)
    if reading_mode == "dual" and calibration_mode != "dual":
        return "no_dual_calibration"
    if calibration_mode is None:
        return None if reading_mode == "single" else "no_dual_calibration"
    if calibration_mode != reading_mode:
        return "calibration_mode_changed"
    for have, want in zip(reading_clocks, calibration_clocks):
        if have is not None and want is not None and int(have) != int(want):
            return "calibration_mismatch"
    return None


def helper_args(choice: ScaleChoice, white: str = "instrument",
                chosen: str = "M0") -> "list[str]":
    """The engine's arguments for a dual-scan session (beside
    ``--condition-dir``, which the i1Pro 3 Beta's code already passes).
    *chosen*: the Measure tab's filter row (recorded, never sent as -F)."""
    if white not in WHITES:
        raise ValueError(white)
    if choice.source not in (STANDARD_SOURCE, REFINED_SOURCE):
        raise ValueError(choice.source)
    c = str(chosen).upper()
    if c not in CHOICES:
        raise ValueError(chosen)
    return ["--dual-scale", f"{choice.value:.4f}",
            "--dual-scale-source", choice.source, "--dual-white", white,
            "--dual-chosen", c]


# ---------------------------------------------------------------------------
# The person's choice of condition (the main file stays M0)
# ---------------------------------------------------------------------------

def pass_record_of(main_ti3: "str | Path"):
    """The per-strip pass record of a dual measurement, or None."""
    from core.file_manager import Run
    from workflow.dual_scan.record import PassRecord
    p = Run.dual_pass_record(Path(main_ti3))
    if not p.is_file():
        return None
    try:
        return PassRecord.load(p)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def strips_without_second_pass(main_ti3: "str | Path") -> "list[str]":
    """The strips of a dual measurement whose UV pass is still due (from its
    pass record; empty when there is none or every strip has both)."""
    rec = pass_record_of(main_ti3)
    if rec is None:
        return []
    return [s for (s, which) in rec.missing() if which == "uv"]


def chosen_condition(main_ti3: "str | Path") -> str:
    """The condition the person chose for a dual measurement: the pass
    record's, else the files' header, else M0."""
    rec = pass_record_of(main_ti3)
    if rec is not None and rec.chosen in CHOICES:
        return rec.chosen
    c = read_dual_record(main_ti3).chosen
    return c if c in CHOICES else "M0"


def build_from_preset(main_ti3: "str | Path") -> "tuple[str, str]":
    """What Build Profile's "Build from" starts at for a dual measurement:
    ``(condition, reason)``. The chosen condition once its file is there and
    every strip has both passes; else ``("M0", <why the choice is not
    available yet>)`` with the sentence Build Profile shows beside it
    (:func:`workflow.i1pro3_conditions.no_file_reason`)."""
    from workflow import i1pro3_conditions as ic
    main = Path(main_ti3)
    want = chosen_condition(main)
    if want == "M0" or not read_dual_record(main).dual:
        return "M0", ""
    if not strips_without_second_pass(main) and ic.condition_file(main, want) is not None:
        return want, ""
    return "M0", ic.no_file_reason(main)


# ---------------------------------------------------------------------------
# The refined factor, per instrument (optional; only with i1Profiler)
# ---------------------------------------------------------------------------

def _key_secret(settings: Any) -> bytes:
    """This installation's random secret (made once, kept in the app's own
    settings; never in a measurement or project file)."""
    v = ""
    try:
        v = str(settings.get(KEY_SECRET_SETTING, "") or "")
    except Exception:  # noqa: BLE001 - a broken store: make a new one
        v = ""
    if len(v) != 64 or any(ch not in "0123456789abcdef" for ch in v):
        v = secrets.token_hex(32)
        settings.set(KEY_SECRET_SETTING, v)
    return bytes.fromhex(v)


def instrument_key(model: str, serial: str, settings: Any) -> str:
    """The key a refined factor is kept under for one instrument (review of
    2026-11-18, S4). An HMAC-SHA256 of the model and serial with a secret
    that is random per installation (:func:`_key_secret`): without that
    secret the key cannot be traced back to a serial (an i1Pro 2 serial is
    a short number, and a plain hash of it was reversed in seconds), and the
    same instrument has a different key on every installation. The serial
    itself is never stored."""
    raw = f"{model.strip().lower()}|{serial.strip()}".encode("utf-8")
    return hmac.new(_key_secret(settings), raw, hashlib.sha256).hexdigest()[:20]


def _refined(settings: Any) -> dict:
    try:
        v = settings.get(REFINED_SETTING, "") or ""
        d = json.loads(v) if isinstance(v, str) and v else (v if isinstance(v, dict) else {})
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001 - a broken store means "none"
        return {}


def scale_for(settings: Any, key: "str | None") -> ScaleChoice:
    """The factor to use for instrument *key*: its refined one when there is
    a sensible one, else the standard."""
    from workflow.dual_scan.model import check_scale
    from workflow.dual_scan.reasons import DualScanRefused
    rec = _refined(settings).get(key or "")
    if isinstance(rec, dict):
        try:
            return ScaleChoice(check_scale(rec.get("value")), REFINED_SOURCE)
        except DualScanRefused:
            pass
    return ScaleChoice.standard()


def store_refined(settings: Any, key: str, choice: ScaleChoice, when: str = "") -> None:
    if choice.source != REFINED_SOURCE:
        raise ValueError("only a refined factor is stored")
    d = _refined(settings)
    d[key] = {"value": round(float(choice.value), 4), "when": when}
    settings.set(REFINED_SETTING, json.dumps(d, sort_keys=True))


def forget_refined(settings: Any, key: str) -> None:
    d = _refined(settings)
    if d.pop(key, None) is not None:
        settings.set(REFINED_SETTING, json.dumps(d, sort_keys=True))
