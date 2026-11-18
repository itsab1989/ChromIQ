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
* the instrument as every measurement records it (``TARGET_INSTRUMENT``):
  NO serial number and no instrument key in any measurement file. A refined
  factor is kept per instrument in the app's settings under a one-way key
  (:func:`instrument_key`), never in a file that is shared.

NEVER MIXED. A measurement started as a dual scan is continued only as a
dual scan, and the other way round (:func:`start_guard`, asked before START
like the table drive's white-reference rule; the engine refuses it a second
time, why ``"mixed"``). A dual reading is taken only after a dual
calibration made at the same exposure, and a change of reading mode in
either direction needs a new calibration (:func:`calibration_fits`).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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
WHITES = ("instrument", "table")

#: AppSettings key of the refined factors: {instrument_key: {"value", "when"}}
REFINED_SETTING = "i1pro2_dual_scale_refined"


@dataclass(frozen=True)
class DualRecord:
    dual: bool
    scale: "float | None" = None
    source: str = ""
    white: str = ""


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
                      (read_header_keyword(ti3, WHITE_KEYWORD) or "").strip())


def _has_readings(ti3: Path) -> bool:
    try:
        text = ti3.read_text(encoding="latin-1")
    except OSError:
        return False
    if "\nBEGIN_DATA\n" not in text.replace("\r", ""):
        return False
    block = text.replace("\r", "").split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    return any(ln.strip() for ln in block.splitlines())


def start_guard(main_ti3: "str | Path | None", dual: bool) -> "str | None":
    """Before START: None when this session may write into *main_ti3*, else
    the reason id ``"mixed_scan_kind"`` (a dual-scan session on single-scan
    readings, or a single-scan session on dual-scan readings). A file with
    no readings yet, or none at all, is never refused."""
    if not main_ti3:
        return None
    p = Path(main_ti3)
    if not p.is_file() or not _has_readings(p):
        return None
    return None if read_dual_record(p).dual == bool(dual) else "mixed_scan_kind"


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


def helper_args(choice: ScaleChoice, white: str = "instrument") -> "list[str]":
    """The engine's arguments for a dual-scan session (beside
    ``--condition-dir``, which the i1Pro 3 Beta's code already passes)."""
    if white not in WHITES:
        raise ValueError(white)
    if choice.source not in (STANDARD_SOURCE, REFINED_SOURCE):
        raise ValueError(choice.source)
    return ["--dual-scale", f"{choice.value:.4f}",
            "--dual-scale-source", choice.source, "--dual-white", white]


# ---------------------------------------------------------------------------
# The refined factor, per instrument (optional; only with i1Profiler)
# ---------------------------------------------------------------------------

def instrument_key(model: str, serial: str) -> str:
    """A one-way key for one instrument: the serial never leaves the
    instrument's own answer; settings hold only this."""
    raw = f"chromiq-dual-scan|{model.strip().lower()}|{serial.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


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
