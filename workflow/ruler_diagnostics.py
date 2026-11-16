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
* PER ACCEPTED STRIP, the direction check (revision 2, ChromIQ 4.3.40):
  ``direction_question`` (the window was shown), ``direction_agrees`` (the
  ruler's direction times the saved order agrees with the reference;
  before 4.3.40 the reference was the first strip not saved reversed, since
  then it is the one the question uses), ``direction_reference`` (+1 / -1,
  that reference: the majority of the recent votes, or before there is one
  the earlier votes when they all agree; null when there is none),
  ``direction_votes_before`` (the recent votes the majority was taken
  over), ``direction_colours`` (only when the ruler disagreed: the strip's
  own row scored as saved and turned round, ``saved_de``, ``turned_de``,
  ``mirror_de``, ``better_share`` and the ``verdict`` "saved", "other" or
  "unsure"), ``direction_confirmed_by_colours`` (the colours vouched for
  the saved order, so no window was shown and the log says so) and
  ``voted`` (this reading counted towards the reference at once),
  ``direction_restarted`` (4.3.42: this strip confirmed a turn, its ruler
  disagreeing with the reference while its colours vouched, and the
  reference started again from it) and
  ``vote_waits_for`` (the questions whose answer this reading's vote waits
  for: "read_twice" is cast on Keep, "ruler_direction" on Continue Anyway
  only; empty when it voted at once or casts no vote, for example after a
  question about its order).
* THE MARGIN TOLERANCE (revision 3, Beta, 2026-11-16): per strip the
  engine's ``record.margin``, only for a strip ArgyllCMS refused while the
  tolerance was on. Refused: ``tried``, ``accepted`` false, ``why`` (the
  rules' own words, "M: ...; L: ..."), ``segments``, ``back``, ``rules``
  (the rule set's version). Kept: ``rule`` ("M" margin at an end, "L" no
  white leader), ``left_start`` / ``left_end`` (white pieces left out at each
  end), ``standing`` (pieces the ruler left out), ``leader``, ``fit`` (mean
  dE76 of the kept patches to the expected strip), ``rival`` (the best
  alternative: another strip, a shifted position or the other direction),
  ``refused_because`` (ArgyllCMS's reason), ``rules``, and (engine
  2026-11-16d) ``travel``: ``net`` and ``back`` (ruler steps; ``back_limit``
  the most it may fall back), ``median_segment`` (steps), ``pitch`` (rule
  0b's patch pitch, steps), ``span`` (first kept patch centre to the last,
  steps), ``largest_step`` (the largest centre-to-centre step, in pitches;
  ``largest_step_limit`` the most allowed), ``kept_steps`` and
  ``kept_readings`` (each kept patch's ruler travel in the strip's direction
  and its readings, in swipe order); and ``ratios``: ``fit_to_rival`` and
  ``halves_worst`` (the worst share of either half against its
  alternatives), each kept only at ``limit`` or below, and ``fit_limit``.
  ``margin_summary``, at the top of the file (written whenever the
  tolerance was asked for or any strip carries a ``margin``), gathers them so
  a kept or a refused strip is found at once: ``tried``, ``kept``,
  ``refused``, ``refused_by_reason`` (the ``why`` with every number written
  as "#", and how often), ``kept_strips`` (per kept strip its ``strip``, its
  ``entry`` in ``strips``, the entry's ``verdict``, the rule, what was left
  out, the reason ArgyllCMS gave, ``fit``, ``rival``, ``fit_to_rival``,
  ``halves_worst``, ``largest_step`` and ``back``) and ``refused_strips``
  (``strip``, ``entry``, ``why``).
* NOT IN: a serial number (this code never reads one), calibration data,
  file paths, project, chart or user names.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

FORMAT = "chromiq-ruler-diagnostics"
VERSION = 1
#: Additive revisions of version 1 (a reader of an older revision only meets
#: keys it does not know): 2 = ChromIQ 4.3.40, the direction fields below;
#: 3 = the margin tolerance (Beta, 2026-11-16): the record's "margin" (what
#: the tolerance decided for a strip ArgyllCMS refused) and
#: "trigger_wait_ms" (how long the i1Pro 2 lights' quiet time held the
#: trigger back), and the file's "i1pro2_lights_beta", "margin_tolerance" and
#: "margin_summary" (at the top; see the module text).
REVISION = 3

#: Keys of the engine's ruler record copied into the file. Anything else the
#: engine might add is left out until it is reviewed for privacy.
RECORD_KEYS = ("instrument", "ended", "icom_err", "samples", "bytes",
               "readings", "clocks", "clock_s", "inttime", "first", "changes",
               "changes_dropped", "argyll_used", "cut_domain", "cut",
               "trace", "trace_domain", "result",
               # revision 3: numbers and fixed words only (no names, no paths)
               "trigger_wait_ms", "margin")

_MM_PER_INCH = 25.4


def strip_geometry(channels_json: "Path | str | None",
                   ti2: "Path | str | None" = None) -> "dict[str, dict]":
    """Per strip label: patch count, patch length, pitch and span in mm, from
    an engine chart's ``<stem>.channels.json``. ``{}`` for any other chart.

    The strip label is the one the chart prints, through the chart's own
    label scheme (``labels_for_chart(ti2).strip_of``): ``A1`` -> ``A`` on a
    chart with letter strips, ``9I`` -> ``9`` on ChromIQ's engine charts with
    number strips and letter patches (4.3.37: the old rule, the location
    without its trailing digits, made every patch of such a chart a strip of
    its own). Without a readable .ti2, or for a location the scheme does not
    know, the old rule. A strip runs down the page."""
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
    labels = None
    if ti2:
        try:
            from workflow.layout_engine.labels import labels_for_chart
            labels = labels_for_chart(ti2)
        except Exception:      # noqa: BLE001 - the old rule then
            labels = None
    strips: "dict[str, list]" = {}
    for r in rects:
        try:
            loc = str(r["loc"])
            lab = (labels.strip_of(loc) if labels is not None else None) \
                or loc.rstrip("0123456789")
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


_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def margin_summary(doc: dict) -> "dict | None":
    """The margin tolerance's decisions in *doc*, for the top of the file;
    None when the tolerance was not asked for and no strip carries a
    ``margin`` (the file then stays as it was)."""
    kept: "list[dict]" = []
    refused: "list[dict]" = []
    by_reason: "dict[str, int]" = {}
    for i, e in enumerate(doc.get("strips") or []):
        m = (e.get("record") or {}).get("margin")
        if not isinstance(m, dict):
            continue
        if m.get("accepted"):
            t = m.get("travel") if isinstance(m.get("travel"), dict) else {}
            r = m.get("ratios") if isinstance(m.get("ratios"), dict) else {}
            kept.append({
                "strip": e.get("strip"), "entry": i,
                "verdict": e.get("verdict"), "rule": m.get("rule"),
                "left_start": m.get("left_start"),
                "left_end": m.get("left_end"),
                "refused_because": m.get("refused_because"),
                "fit": m.get("fit"), "rival": m.get("rival"),
                "fit_to_rival": r.get("fit_to_rival"),
                "halves_worst": r.get("halves_worst"),
                "largest_step": t.get("largest_step"),
                "back": m.get("back")})
        else:
            why = str(m.get("why") or "")
            refused.append({"strip": e.get("strip"), "entry": i, "why": why})
            key = _NUMBER.sub("#", why) or "?"
            by_reason[key] = by_reason.get(key, 0) + 1
    if not kept and not refused and doc.get("margin_tolerance") in (
            None, "not asked"):
        return None
    return {"tried": len(kept) + len(refused), "kept": len(kept),
            "refused": len(refused),
            "refused_by_reason": dict(sorted(by_reason.items(),
                                             key=lambda kv: -kv[1])),
            "kept_strips": kept, "refused_strips": refused}


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
                 verification: bool = False, argyll: str = "",
                 condition: "str | None" = None,
                 condition_source: "str | None" = None):
        from core.version import APP_VERSION as _v
        from workflow import ruler_check
        self.path = Path(path)
        self.doc = {
            "format": FORMAT, "version": VERSION, "revision": REVISION,
            "chromiq": str(_v), "engine_build": helper_build,
            # the vendored ArgyllCMS's own version (ARGYLL_VERSION_STR),
            # as the engine reports it (review item 9)
            "argyllcms": argyll or None, "os": _os_text(),
            "instrument": instrument, "firmware": firmware,
            "measurement": "verification" if verification else "profiling",
            # 4.3.37: the condition chosen with -F (M0 / M1 / M2 / M3), or
            # null without -F: the instrument's normal mode
            "measurement_condition": condition,
            # 4.3.39 (R4): "chosen" (-F), "instrument default" (the
            # instrument's normal mode, where it is known), or null
            "measurement_condition_source": condition_source or (
                "chosen" if condition else None),
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

    def set_condition(self, condition: "str | None",
                      source: "str | None") -> None:
        """R4: the measurement condition learnt after the file was begun."""
        try:
            self.doc["measurement_condition"] = condition
            self.doc["measurement_condition_source"] = source
            self.write()
        except Exception:      # noqa: BLE001
            log.warning("ruler diagnostics: could not note the condition",
                        exc_info=True)

    def note_question_answer(self, strip: str, question: str,
                             answer: str) -> None:
        """R5 (4.3.39): one {"question", "answer"} more on the strip's last
        entry, in the order they were given."""
        try:
            for e in reversed(self.doc["strips"]):
                if e.get("strip") == strip:
                    e.setdefault("answers", []).append(
                        {"question": str(question), "answer": str(answer)})
                    break
            self.write()
        except Exception:      # noqa: BLE001
            log.warning("ruler diagnostics: could not note an answer",
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

    def _ordered(self) -> dict:
        """The doc as written: the margin tolerance's summary, when there is
        one, right after format, version and revision (revision 3)."""
        summary = margin_summary(self.doc)
        if summary is None:
            return self.doc
        out = {k: self.doc[k] for k in ("format", "version", "revision")
               if k in self.doc}
        out["margin_summary"] = summary
        for k, v in self.doc.items():
            if k not in out and k != "margin_summary":
                out[k] = v
        return out

    def write(self) -> Optional[Path]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".part")
            tmp.write_text(json.dumps(self._ordered(), ensure_ascii=True,
                                      separators=(",", ":")), "utf-8")
            os.replace(tmp, self.path)
            return self.path
        except OSError:
            log.warning("ruler diagnostics: could not write %s", self.path,
                        exc_info=True)
            return None
