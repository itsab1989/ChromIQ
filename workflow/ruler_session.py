"""One measurement session of the ruler check (Preferences > Beta,
2026-11-14; stage 1, CHECK ONLY), between the engine's events and the
Measure tab. No Qt here, so every rule is testable on its own.

The engine (chromiq-chartread --ruler) says once whether the ruler is in use
(``{"event":"ruler",...}``) and then, for every strip, sends the driver's
record (``{"event":"ruler_strip",...}``) BEFORE that strip's ``strip_read`` or
error. This class

* turns the record into figures (``workflow.ruler_check``) and log lines;
* when the strip's ``strip_read`` follows, decides whether to ASK (only an
  accepted strip, only with usable ruler data, and never when the engine's
  own safety net already flags the strip: the manager passes that in);
* writes the diagnostics file after every strip.

It never changes a reading, a patch assignment or the order of events: the
manager only adds a ``ruler`` summary to the strip_read event it passes on.
"""
from __future__ import annotations

import logging
import statistics
import time
from pathlib import Path
from typing import Optional

from core.i18n import tr
from workflow import ruler_check as rc
from workflow import ruler_diagnostics as rd

log = logging.getLogger(__name__)

NAMES = {"i1pro2": "i1Pro 2", "i1pro3": "i1Pro 3"}


def _num(x: float, digits: int = 0) -> str:
    from core.i18n import decimal_text
    return decimal_text(x, digits) if digits else str(int(round(x)))


class RulerSession:
    def __init__(self, *, ti1_path: "Path | None", helper_build: str = "",
                 verification: bool = False):
        self.ti1_path = Path(ti1_path) if ti1_path else None
        self.helper_build = helper_build
        self.verification = verification
        self.active = False
        self.gen = ""
        self.firmware: "int | None" = None
        self.diag: "rd.Diagnostics | None" = None
        self.geometry: "dict[str, dict]" = {}
        self.pending: "tuple[str, dict, rc.StripFigures] | None" = None
        self.derived: "list[float]" = []         # mm per step, accepted strips
        self.pitch_steps: "list[float]" = []     # session pitch (no geometry)
        self.forward_sign = 0
        self.said: "set[str]" = set()
        self.argyll = ""

    #: Accepted strips needed before this session trusts a step size it
    #: worked out itself (the i1Pro 2; review item 6, 2026-11-14), and before
    #: any distance is shown in mm on that instrument.
    STRIPS_FOR_STEP = 3

    def derived_step(self) -> "float | None":
        """The i1Pro 2 step size (mm) this session worked out, once it has
        STRIPS_FOR_STEP accepted strips to work it out from."""
        if len(self.derived) < self.STRIPS_FOR_STEP:
            return None
        return statistics.median(self.derived)

    # ---- the session ---------------------------------------------------
    def diagnostics_path(self) -> "Path | None":
        return self.diag.path if self.diag is not None else None

    def on_session(self, ev: dict) -> "list[str]":
        """The engine's ``ruler`` event: the opening line(s)."""
        self.active = bool(ev.get("active"))
        self.gen = str(ev.get("instrument") or "")
        why = str(ev.get("why") or "")
        if not self.active:
            if why == "sensor":
                return [tr("Ruler (beta): this i1Pro 2 does not report a ruler "
                           "sensor, so the ruler check is not used. The "
                           "measurement runs exactly as it does without the "
                           "option.")]
            if why == "mode":
                return [tr("Ruler (beta): the ruler check works only when "
                           "strips are read by hand. This measurement is "
                           "read another way, so it runs exactly as it does "
                           "without the option.")]
            return [tr("Ruler (beta): the ruler check works with the X-Rite "
                       "i1Pro 2 and i1Pro 3 only. This instrument is measured "
                       "exactly as it is without the option.")]
        self.argyll = str(ev.get("argyll") or "")
        try:
            self.firmware = int(ev.get("firmware"))
        except (TypeError, ValueError):
            self.firmware = None
        if self.ti1_path is not None:
            stem = self.ti1_path.with_suffix("")
            self.geometry = rd.strip_geometry(
                stem.parent / (stem.name + ".channels.json"))
            try:
                from core.file_manager import Run
                stamp = time.strftime("%Y%m%d-%H%M%S")
                path = Run.for_dir(self.ti1_path.parent).ruler_diagnostics_path(
                    stamp)
                self.diag = rd.Diagnostics(
                    path, instrument=self.gen, firmware=self.firmware,
                    helper_build=self.helper_build, geometry=self.geometry,
                    verification=self.verification, argyll=self.argyll)
                self.diag.write()
            except Exception:      # noqa: BLE001 - never stop a measurement
                log.warning("ruler: no diagnostics file", exc_info=True)
                self.diag = None
        lines = [tr("Ruler (beta): the ruler check is on for this {instrument} "
                    "(firmware {firmware}). After each strip ChromIQ shows how "
                    "far, which way and how fast the instrument moved along the "
                    "ruler. Your readings are not changed by this.").format(
                        instrument=NAMES.get(self.gen, self.gen),
                        firmware=self.firmware if self.firmware is not None
                        else "?")]
        if self.diag is not None:
            lines.append(tr("Ruler (beta): the diagnostics for this measurement "
                            "are saved in this file: {path}").format(
                                path=str(self.diag.path)))
        return lines

    def on_end(self) -> "list[str]":
        """The measurement is over: where the file is, and how to send it."""
        self.flush()
        if not self.active or self.diag is None or not self.diag.doc["strips"]:
            return []
        return [tr("Ruler (beta): the diagnostics for this measurement are in "
                   "{path}. If you would like to help us make the ruler check "
                   "better, please attach this file in the ChromIQ forum "
                   "thread or on GitHub. Besides how the instrument moved, "
                   "it holds a coarse brightness trace in three colour bands, "
                   "relative to the paper, from which the rough colour of each "
                   "patch can be seen; it holds no serial number, no "
                   "calibration data, no file paths and no names.").format(
                       path=str(self.diag.path))]

    # ---- one strip -----------------------------------------------------
    def flush(self) -> None:
        """A record whose strip_read never came (the engine refused the strip
        after the reading, e.g. a wrong strip): into the file as it is."""
        if self.pending is None:
            return
        strip, rec, f = self.pending
        self.pending = None
        self._write(rec, strip, f, "no_strip_read")

    def on_strip(self, rec: dict) -> "list[str]":
        """The engine's ``ruler_strip``: figures and the log line(s)."""
        self.flush()
        strip = str(rec.get("strip") or "?")
        f = rc.figures(rec)
        lines: "list[str]" = []
        if rec.get("given_up") and "given_up" not in self.said:
            self.said.add("given_up")
            lines.append(self._given_up_line(str(rec.get("giveup") or "")))
        result = str(rec.get("result") or "")
        if f.why_not == "no_ruler":
            if "no_ruler" not in self.said:
                self.said.add("no_ruler")
                lines.append(tr(
                    "Ruler (beta): no ruler was seen under the instrument while "
                    "strip {strip} was read, so the strip was read the usual "
                    "way. That is fine: the ruler check simply had nothing to "
                    "look at. ChromIQ will not mention this again during this "
                    "measurement.").format(strip=strip))
            log.info("ruler: strip %s, no ruler seen (%d changes)", strip,
                     f.transitions)
        elif not f.usable:
            if not rec.get("given_up"):
                lines.append(tr(
                    "Ruler (beta), strip {strip}: the ruler data for this strip "
                    "was incomplete, so the strip was checked the usual way "
                    "only.").format(strip=strip))
            log.info("ruler: strip %s not usable (%s): samples %s, expected "
                     "%s, illegal %d, ended %s", strip, f.why_not,
                     rec.get("samples"), f.expected_samples, f.illegal,
                     rec.get("ended"))
        else:
            self._unit_line = ""
            line = self._motion_line(strip, rec, f)
            if self._unit_line:
                lines.append(self._unit_line)
            lines.append(line)
        if result == "read":
            self.pending = (strip, rec, f)
        else:
            self._write(rec, strip, f, "refused")
        return lines

    def on_strip_read(self, ev: dict, *, other_question: bool) -> "dict | None":
        """The accepted strip's ``strip_read``. Returns the summary the
        manager adds to the event as ``ev["ruler"]``, or None when this strip
        has no record. *other_question*: the engine's net, ChromIQ's slip
        check or read-twice already ask about it (they win)."""
        strip = str(ev.get("strip") or "").strip()
        if self.pending is None or self.pending[0] != strip:
            self.flush()
            return None
        _strip, rec, f = self.pending
        self.pending = None
        patches = len(ev.get("patches") or []) if isinstance(
            ev.get("patches"), list) else 0
        geo = self.geometry.get(strip) or {}
        span_mm = geo.get("span_mm")
        pitch_mm = geo.get("pitch_mm")
        coverage, followed = rc.cut_coverage(rec)
        pitch_cut = rc.cut_pitch_steps(rec)
        derived = self.derived_step()
        session_pitch = (statistics.median(self.pitch_steps)
                         if len(self.pitch_steps)
                         >= rc.MIN_STRIPS_FOR_SESSION_PITCH else None)
        # The question needs a trustworthy step size (challenger m6): the
        # i1Pro 2 only once this session derived one, the i1Pro 3 has
        # ArgyllCMS's own.
        can_ask = f.usable and patches >= rc.MIN_PATCHES_FOR_QUESTION
        span = pitch = None
        if self.gen == "i1pro2":
            if span_mm and derived:
                span = rc.span_steps("i1pro2", span_mm, derived_mm_per_step=derived)
                pitch = pitch_mm / (derived * rc.DERIVED_MARGIN) if pitch_mm else None
            elif not span_mm and session_pitch:
                span, pitch = session_pitch * patches, session_pitch
        else:
            if span_mm:
                span = rc.span_steps(self.gen, span_mm)
                pitch = (pitch_mm / rc.MM_PER_STEP_UPPER[self.gen]
                         if pitch_mm else None)
            elif session_pitch:
                span, pitch = session_pitch * patches, session_pitch
        ask = bool(can_ask and not other_question and rc.not_covered(
            f, span, pitch=pitch, patches=patches, coverage=coverage,
            followed=followed))
        # learn from the strips that look right
        if f.usable and followed and not ask:
            if pitch_cut and pitch_mm:
                self.derived.append(pitch_mm / pitch_cut)
            if pitch_cut:
                self.pitch_steps.append(pitch_cut)
            if not self.forward_sign and not ev.get("reversed") and f.sign:
                self.forward_sign = f.sign
        mm_step = rc.mm_per_step(self.gen, derived)
        summary = {
            "strip": strip, "usable": f.usable, "ask": ask,
            "travel_steps": f.travel_steps, "coverage_steps": coverage,
            "span_steps": span, "patches": patches,
            "mm_per_step": mm_step,
            "travel_mm": (f.travel_steps * mm_step) if mm_step else None,
            "span_mm": span_mm,
            "other_question": other_question,
        }
        extra = {"accepted": True, "reversed": bool(ev.get("reversed")),
                 "derived_mm_per_step": (pitch_mm / pitch_cut)
                 if pitch_cut and pitch_mm else None,
                 "pitch_steps": pitch_cut, "coverage_steps": coverage,
                 "followed": followed, "span_steps_used": span,
                 "question": ask, "other_question": other_question,
                 "direction_agrees": (f.sign == self.forward_sign) !=
                 bool(ev.get("reversed")) if self.forward_sign and f.sign
                 else None}
        self._write(rec, strip, f, "asked" if ask else "accepted", extra)
        return summary

    def note_answer(self, strip: str, answer: str) -> None:
        if self.diag is not None:
            self.diag.note_answer(strip, answer)

    # ---- helpers -------------------------------------------------------
    def _write(self, rec, strip, f, verdict, extra=None) -> None:
        if self.diag is None:
            return
        figs = {k: getattr(f, k) for k in (
            "seen", "pairs", "usable", "why_not", "transitions", "illegal",
            "travel_steps", "net_steps", "sign", "motion_s", "mean_steps_s",
            "peak_steps_s", "expected_samples")}
        e = {"geometry": self.geometry.get(strip),
             "given_up": bool(rec.get("given_up")),
             "giveup": rec.get("giveup"),
             "stream_did_not_end": bool(rec.get("stream_did_not_end"))}
        e.update(extra or {})
        self.diag.add_strip(rec, strip=strip, figures=figs, verdict=verdict,
                            extra=e)

    def _direction(self, f) -> str:
        if not self.forward_sign or not f.sign:
            return ""
        # A DIRECTION, NOT A VERDICT (review of 4.3.35): "it went from the
        # first patch to the last" read as "it covered every patch", right
        # before a question saying that it did not. Only the way it moved.
        if f.sign == self.forward_sign:
            return " " + tr("It moved in the reading direction, from the first "
                            "patch towards the last.")
        return " " + tr("It moved against the reading direction, from the last "
                        "patch towards the first.")

    def _motion_line(self, strip: str, rec: dict, f) -> str:
        mm = rc.mm_per_step(self.gen, self.derived_step())
        prefix = ""
        if mm and self.gen == "i1pro2" and "mm_now" not in self.said:
            # Never switch units silently (review item 9).
            self.said.add("mm_now")
            prefix = tr("Ruler (beta): from now on the distances are shown in "
                        "mm. After three strips, ChromIQ has worked out how "
                        "long one ruler step is on this i1Pro 2: about {mm} "
                        "mm.").format(mm=_num(mm, 2))
        # THE WHOLE STROKE AND THE PART OVER THE PATCHES (review of 4.3.35).
        # The figure here is the whole movement; the ruler question counts
        # only the part between the first and the last patch reading
        # (`rc.cut_coverage`, the same number `on_strip_read` hands it). Shown
        # side by side, "105 mm" here and "only about 90 mm" in the question
        # read as a contradiction, so the line names both when it has both.
        over, _followed = rc.cut_coverage(rec)
        over = over or None     # as the question: no coverage -> the travel
        if mm and over is not None:
            text = tr("Ruler (beta), strip {strip}: the instrument moved {dist} "
                      "mm along the ruler in all, about {over} mm of it over "
                      "the patches, at about {avg} mm per second on average "
                      "and {peak} mm per second at its fastest.").format(
                          strip=strip, dist=_num(f.travel_steps * mm),
                          over=_num(over * mm),
                          avg=_num(f.mean_steps_s * mm),
                          peak=_num(f.peak_steps_s * mm))
        elif mm:
            text = tr("Ruler (beta), strip {strip}: the instrument moved {dist} "
                      "mm along the ruler, at about {avg} mm per second on "
                      "average and {peak} mm per second at its fastest.").format(
                          strip=strip, dist=_num(f.travel_steps * mm),
                          avg=_num(f.mean_steps_s * mm),
                          peak=_num(f.peak_steps_s * mm))
        elif over is not None:
            text = tr("Ruler (beta), strip {strip}: the instrument moved {dist} "
                      "ruler steps in all, about {over} of them over the "
                      "patches, at about {avg} steps per second on average "
                      "and {peak} at its fastest. How long one ruler step is "
                      "on this instrument is not known yet, so the figures "
                      "are in steps.").format(
                          strip=strip, dist=_num(f.travel_steps),
                          over=_num(over),
                          avg=_num(f.mean_steps_s), peak=_num(f.peak_steps_s))
        else:
            text = tr("Ruler (beta), strip {strip}: the instrument moved {dist} "
                      "ruler steps, at about {avg} steps per second on average "
                      "and {peak} at its fastest. How long one ruler step is "
                      "on this instrument is not known yet, so the figures "
                      "are in steps.").format(
                          strip=strip, dist=_num(f.travel_steps),
                          avg=_num(f.mean_steps_s), peak=_num(f.peak_steps_s))
        text += self._direction(f)
        self._unit_line = prefix
        if self.gen == "i1pro3" and not rec.get("argyll_used"):
            text += " " + tr("ArgyllCMS did not use the ruler to place the "
                             "patches of this strip and placed them by time "
                             "instead, as it does without a ruler.")
        return text

    def _given_up_line(self, why: str) -> str:
        reasons = {
            "stream_did_not_end": tr("the ruler signal did not end by itself "
                                     "after a strip"),
            "error": tr("the ruler signal could not be read"),
            "no_data": tr("the instrument sent no ruler signal"),
            "measurement_failed": tr("a reading failed while the ruler was in "
                                     "use"),
            "rate": tr("the readings arrived at an unexpected rate while the "
                       "ruler was in use"),
            "timeout": tr("the ruler signal stopped arriving"),
            "not_started": tr("the ruler could not be started"),
        }
        return tr("Ruler (beta): ChromIQ has stopped using the instrument's "
                  "ruler for the rest of this measurement, because {reason}. "
                  "Your readings are not affected: every strip is read "
                  "exactly as it is without the ruler. The diagnostics file "
                  "records what happened, so please send it to us if you "
                  "can.").format(reason=reasons.get(why, tr(
                      "something unexpected happened with the ruler signal")))
