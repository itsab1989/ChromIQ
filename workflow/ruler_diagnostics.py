"""The ruler check's diagnostics file (Preferences > Beta, 2026-11-14).

One JSON file per measurement session, in the run's ``reports/``
(:meth:`core.file_manager.Run.ruler_diagnostics_path`), rewritten whole after
every strip (write to a temporary name, then replace), so a crash or a quit
never loses what was already read.

It is the main purpose of the Beta: real ruler data on ChromIQ's own chart
layouts, which a tester sends to the project. So it holds what the analysis
needs and nothing personal:

* IN: format and version, ChromIQ's version, the engine's build string,
  ArgyllCMS's version, the OS name and version, the instrument generation and
  its firmware, the provisional thresholds, the chart's strip geometry (patch
  count, patch length, pitch and span in mm when known), and per strip the
  engine's ruler record (the ruler code stream, counts, today's patch cut, a
  coarse brightness trace in three colour bands, each divided by its own
  maximum over the strip, which is usually the paper, so the rough colour of
  each patch relative to the paper CAN be seen from it) with ChromIQ's
  figures and verdict.
* NOT IN: a serial number (this code never reads one), calibration data,
  file paths, project, chart or user names.
"""
from __future__ import annotations

import json
import logging
import os
import platform
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

FORMAT = "chromiq-ruler-diagnostics"
VERSION = 1

#: Keys of the engine's ruler record copied into the file. Anything else the
#: engine might add is left out until it is reviewed for privacy.
RECORD_KEYS = ("instrument", "ended", "icom_err", "samples", "bytes",
               "readings", "clocks", "clock_s", "inttime", "first", "changes",
               "changes_dropped", "argyll_used", "cut_domain", "cut",
               "trace", "trace_domain", "result")

_MM_PER_INCH = 25.4


def strip_geometry(channels_json: "Path | str | None") -> "dict[str, dict]":
    """Per strip label: patch count, patch length, pitch and span in mm, from
    an engine chart's ``<stem>.channels.json``. ``{}`` for any other chart.

    The strip label is the patch location without its trailing number
    (``A1`` -> ``A``, ``AB12`` -> ``AB``); a strip runs down the page."""
    if not channels_json:
        return {}
    try:
        doc = json.loads(Path(channels_json).read_text(encoding="utf-8"))
        layout = doc["layout"]
        if layout.get("engine") != "chromiq":
            return {}
        dpi = float(layout.get("dpi") or 300) or 300.0
        rects = list(layout.get("patches") or [])
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    px = _MM_PER_INCH / dpi
    strips: "dict[str, list]" = {}
    for r in rects:
        try:
            loc = str(r["loc"])
            lab = loc.rstrip("0123456789")
            strips.setdefault(lab, []).append(
                (float(r["y"]), float(r["h"])))
        except (KeyError, TypeError, ValueError):
            continue
    out: "dict[str, dict]" = {}
    for lab, ps in strips.items():
        ps.sort()
        n = len(ps)
        if n < 1 or not lab:
            continue
        first, last = ps[0], ps[-1]
        span = (last[0] + last[1] - first[0]) * px
        pitch = ((last[0] - first[0]) / (n - 1) * px) if n > 1 else None
        out[lab] = {"patches": n,
                    "patch_length_mm": round(sum(h for _, h in ps) / n * px, 3),
                    "pitch_mm": round(pitch, 3) if pitch else None,
                    "span_mm": round(span, 3)}
    return out


def _os_text() -> str:
    try:
        if platform.system() == "Darwin":
            return "macOS " + (platform.mac_ver()[0] or "?")
        return f"{platform.system()} {platform.release()}"
    except Exception:      # noqa: BLE001
        return "?"


class Diagnostics:
    """One measurement session's file. Every method swallows its errors: a
    diagnostics file must never disturb a measurement."""

    def __init__(self, path: Path, *, instrument: str, firmware: "int | None",
                 helper_build: str = "", geometry: "dict | None" = None,
                 verification: bool = False, argyll: str = ""):
        from core.version import APP_VERSION as _v
        from workflow import ruler_check
        self.path = Path(path)
        self.doc = {
            "format": FORMAT, "version": VERSION,
            "chromiq": str(_v), "engine_build": helper_build,
            # the vendored ArgyllCMS's own version (ARGYLL_VERSION_STR),
            # as the engine reports it (review item 9)
            "argyllcms": argyll or None, "os": _os_text(),
            "instrument": instrument, "firmware": firmware,
            "measurement": "verification" if verification else "profiling",
            "thresholds": ruler_check.THRESHOLDS,
            "chart_geometry": geometry or {},
            "strips": [],
        }

    def add_strip(self, record: dict, *, strip: str, figures: dict,
                  verdict: str, extra: "dict | None" = None) -> None:
        try:
            entry = {"strip": strip, "verdict": verdict, "figures": figures,
                     "record": {k: record[k] for k in RECORD_KEYS
                                if k in record}}
            if extra:
                entry.update(extra)
            self.doc["strips"].append(entry)
            self.write()
        except Exception:      # noqa: BLE001
            log.warning("ruler diagnostics: could not add strip %s", strip,
                        exc_info=True)

    def note_answer(self, strip: str, answer: str) -> None:
        """The person's answer to the question about *strip* (last entry)."""
        try:
            for e in reversed(self.doc["strips"]):
                if e.get("strip") == strip:
                    e["answer"] = answer
                    break
            self.write()
        except Exception:      # noqa: BLE001
            log.warning("ruler diagnostics: could not note an answer",
                        exc_info=True)

    def write(self) -> Optional[Path]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".part")
            tmp.write_text(json.dumps(self.doc, ensure_ascii=True,
                                      separators=(",", ":")), "utf-8")
            os.replace(tmp, self.path)
            return self.path
        except OSError:
            log.warning("ruler diagnostics: could not write %s", self.path,
                        exc_info=True)
            return None
