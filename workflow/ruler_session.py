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
                 verification: bool = False, condition: "str | None" = None,
                 lights: "bool | None" = None):
        self.ti1_path = Path(ti1_path) if ti1_path else None
        self.helper_build = helper_build
        #: 4.3.37: the measurement condition the person chose (the -F of this
        #: read: "M0", "M1", "M2", "M3"), or None without -F (the
        #: instrument's normal mode), for the diagnostics file.
        self.condition = condition
        #: R4: where the condition came from ("chosen", "instrument default")
        self.condition_source = "chosen" if condition else None
        self.verification = verification
        #: 2026-11-16: whether the i1Pro 2 / i1Pro 3 lights Beta was on, for
        #: the diagnostics file (its quiet time may hold a trigger back)
        self.lights = lights
        self.active = False
        self.gen = ""
        self.firmware: "int | None" = None
        self.diag: "rd.Diagnostics | None" = None
        self.geometry: "dict[str, dict]" = {}
        self.pending: "tuple[str, dict, rc.StripFigures] | None" = None
        self.derived: "list[float]" = []         # mm per step, accepted strips
        self.pitch_steps: "list[float]" = []     # session pitch (no geometry)
        #: 4.3.37 (the i1Pro 3): the way the ruler says the instrument moved
        #: on each accepted strip, turned round where the strip was FILED
        #: back to front ("reversed"), so that every strip read and filed
        #: correctly votes the same way, in whichever direction it was
        #: scanned. "Forward" is the majority of these, never strip 1 alone.
        #: The swipe direction cancels out of that product, so what a vote
        #: really records is how the SHEET (or the ruler) lay under the
        #: instrument (pharmacist, 2026-11-15).
        #: 4.3.40: one vote per strip, keyed by its name, in the order cast
        #: (a later reading of the same strip replaces its vote and moves to
        #: the end), so a re-read never leaves a stale vote behind; and only
        #: from a reading nothing was asked about (F3).
        self._votes: "dict[str, int]" = {}
        #: Votes waiting for an answer (review of 4.3.40, MINOR-1/3): strip
        #: -> (vote, the questions whose "keep" answer still has to come).
        self._pending_votes: "dict[str, tuple[int, set]]" = {}
        #: 4.3.42: a CONFIRMED TURN restarts the reference. When a strip's
        #: ruler disagrees with the reference and its own colours vouch for
        #: the order it was saved in, the sheet (or the ruler) was turned:
        #: the reference then starts again from that strip's way round
        #: (``_turn_sign``), and only the votes cast since (``_since_turn``)
        #: count, so the next strips are compared at once instead of waiting
        #: for the old votes to be outvoted (pharmacist, 2026-11-15: four
        #: strips with no reference after a quick turn back).
        self._turn_sign = 0
        self._since_turn: "dict[str, int]" = {}
        #: Second look, MINOR-A: there was a majority, and whether the loss
        #: of it has been said in the log (once per loss).
        self._had_majority = False
        self._loss_said = False
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
                stem.parent / (stem.name + ".channels.json"),
                stem.parent / (stem.name + ".ti2"))
            try:
                from core.file_manager import Run
                stamp = time.strftime("%Y%m%d-%H%M%S")
                path = Run.for_dir(self.ti1_path.parent).ruler_diagnostics_path(
                    stamp)
                self.diag = rd.Diagnostics(
                    path, instrument=self.gen, firmware=self.firmware,
                    helper_build=self.helper_build, geometry=self.geometry,
                    condition=self.condition,
                    condition_source=self.condition_source,
                    verification=self.verification, argyll=self.argyll)
                # revision 3 (2026-11-16), additive
                self.diag.doc["i1pro2_lights_beta"] = self.lights
                self.diag.doc["margin_tolerance"] = str(
                    ev.get("margin_tolerance") or "not asked")
                self.diag.write()
            except Exception:      # noqa: BLE001 - never stop a measurement
                log.warning("ruler: no diagnostics file", exc_info=True)
                self.diag = None
            if self.diag is not None:
                # A8 (4.3.50): its own try (S1): a log line can never switch
                # the diagnostics off
                try:
                    from workflow.measure_log import written as _written
                    _written("ruler diagnostics", path)
                except Exception:      # noqa: BLE001
                    pass
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
        mt = str(ev.get("margin_tolerance") or "")
        if mt == "on":
            lines.append(tr(
                "Margin tolerance (beta): on for this i1Pro 2. When ArgyllCMS "
                "refuses a strip only because the white paper margin at one "
                "end was counted as a patch, or because the reading began "
                "without white paper before the first patch, ChromIQ checks "
                "the strip's colours and the ruler, and keeps the reading "
                "when they clearly show the whole strip. This log says so "
                "for every strip it keeps."))
        elif mt == "not_i1pro2":
            lines.append(tr(
                "Margin tolerance (beta): this option works with the X-Rite "
                "i1Pro 2 only, so it is not used for this instrument. "
                "Strips are read exactly as without it."))
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
        margin = rec.get("margin")
        if isinstance(margin, dict) and margin.get("accepted"):
            lines.insert(0, self._margin_line(strip, margin))
        elif isinstance(margin, dict):
            log.info("margin tolerance: strip %s stays refused (%s)", strip,
                     margin.get("why"))
        if result == "read":
            self.pending = (strip, rec, f)
        else:
            # A strip the reader refused (it could not find the patches) is
            # the most useful case for the ruler work (4.3.37): filed with the
            # driver's own reason, same privacy as every other entry.
            self._write(rec, strip, f, "refused",
                        {"refused_because": str(rec.get("reason") or "")
                         or result})
        return lines

    def on_strip_read(self, ev: dict, *, other_question: bool,
                      other_questions: "list[str] | None" = None
                      ) -> "dict | None":
        """The accepted strip's ``strip_read``. Returns the summary the
        manager adds to the event as ``ev["ruler"]``, or None when this strip
        has no record. *other_question*: the engine's net, ChromIQ's slip
        check or read-twice already ask about it (they win)."""
        strip = str(ev.get("strip") or "").strip()
        # This reading replaces whatever the strip's earlier reading voted
        # (4.3.40, F3), with or without a ruler record of its own.
        self._drop_vote(strip)
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
        # 4.3.37: the ruler and the filing disagree about the direction: the
        # strip was most likely saved back to front. 4.3.38: for the i1Pro 2
        # as well. The question uses only the sign of the net count and the
        # session's majority, never a step size, and the i1Pro 2's encoder
        # gives that sign the same way (its one real strip in a tester's log,
        # 2026-11-14: 339 transitions, none illegal, net -339 = the travel).
        filed_sign = (-f.sign if ev.get("reversed") else f.sign) \
            if f.usable and f.sign else 0
        majority = self._majority_direction()
        window = self._recent()
        lost_line = None
        if majority:
            self._had_majority, self._loss_said = True, False
        elif self._had_majority and not self._loss_said:
            self._loss_said = True
            lost_line = self._lost_line()
        # 4.3.42: right after a confirmed turn, the strip is held against
        # the old reference as well, for as long as it still stands, so that
        # restarting never lets through what the old one would have asked
        old = self._old_majority()
        refs = [x for x in (majority, old) if x]
        disagrees = bool(
            self.gen in NAMES and not ask and not other_question
            and filed_sign and refs and any(filed_sign != x for x in refs)
            and patches >= rc.MIN_PATCHES_FOR_QUESTION)
        # 4.3.40 (pharmacist, 2026-11-15): a disagreement is what a TURNED
        # SHEET (or ruler) looks like as much as a strip saved back to front.
        # Asked only when the strip's own colours cannot vouch for the order
        # it was saved in (`slipped_strip.own_row_direction`); when they
        # clearly do, one calm line in the log instead of a window, and the
        # strip votes, so the reference follows the new way round.
        colours = None
        if disagrees:
            from workflow.slipped_strip import own_row_direction
            colours = own_row_direction(ev.get("patches") or [])
        vouched = bool(disagrees and colours is not None
                       and colours.verdict == "saved")
        ask_direction = disagrees and not vouched
        # learn from the strips that look right
        if f.usable and followed and not ask:
            if pitch_cut and pitch_mm:
                self.derived.append(pitch_mm / pitch_cut)
            if pitch_cut:
                self.pitch_steps.append(pitch_cut)
        # F3 (4.3.40, review MINOR-1/3): a strip votes unless the question
        # it got puts its ORDER in doubt. The ruler's coverage question, a
        # slip that is not back to front and the engine's net concern where
        # the patches are, not which way round: they vote at once. "Was a
        # strip read twice?" and this direction question vote once the
        # person keeps the reading ("keep", "Continue Anyway": the person has
        # said what happened, so after a turned sheet on a chart whose strips
        # cannot vouch the reference still follows). A strip ChromIQ thinks
        # was saved back to front never votes. A re-read replaces the strip's
        # vote (dropped above); "Re-read" / "Re-measure" casts none.
        reference = majority or self._early_reference()
        names = set(other_questions or ())
        if other_question and not names:
            names = {"unknown"}
        wait = set()
        if ask_direction and colours is not None \
                and colours.verdict == "other":
            # second look, MINOR-B: the colours point to back to front
            # (M-STRIP-RULER-DIRECTION-COLOURS): no answer votes
            names = names | {"colours_say_back_to_front"}
        elif ask_direction:
            wait.add("ruler_direction")
        if "read_twice" in names:
            wait.add("read_twice")
        blocked = bool(names & self.ORDER_QUESTIONS)
        voted = bool(filed_sign and not blocked and not wait)
        restarted = bool(vouched and voted)
        if restarted:
            # 4.3.42: a confirmed turn; the reference starts again here
            self._turn_sign = filed_sign
            self._since_turn = {}
        if voted:
            self._cast_vote(strip, filed_sign)
        elif filed_sign and not blocked:
            self._pending_votes[strip] = (filed_sign, wait)
        log_lines: "list[str]" = [lost_line] if lost_line else []
        if vouched:
            log_lines.append(self._turned_note(strip))
        elif filed_sign and reference and filed_sign == reference \
                and not ask_direction and old in (0, filed_sign):
            # F4 (4.3.40): which way the instrument moved over the patches,
            # said only when the ruler and the saving agree against the same
            # reference the question uses; decided here, where the saving is
            # known, never from the ruler alone.
            log_lines.append(self._direction_line(
                strip, bool(ev.get("reversed"))))
        mm_step = rc.mm_per_step(self.gen, derived)
        summary = {
            "strip": strip, "usable": f.usable, "ask": ask,
            "ask_direction": ask_direction,
            "travel_steps": f.travel_steps, "coverage_steps": coverage,
            "span_steps": span, "patches": patches,
            "mm_per_step": mm_step,
            "travel_mm": (f.travel_steps * mm_step) if mm_step else None,
            "span_mm": span_mm,
            "other_question": other_question,
            # 4.3.40: lines the manager writes into the log before the
            # strip's verdict (the direction, or the turned-sheet note)
            "log_lines": log_lines,
            "direction_confirmed_by_colours": vouched,
            # review MINOR-2: "other" = the colours point to back to front
            # (the window then says so); "unsure" or None = cannot tell
            "direction_colours_verdict": colours.verdict if colours else None,
        }
        # R5 (4.3.39): WHICH question this strip got, by name (the ruler's
        # own, or ChromIQ's: the engine's net, a slip or a strip filed back
        # to front, "Was a strip read twice?"); the answers are added as the
        # person gives them (note_question_answer).
        asked = list(other_questions or [])
        if ask:
            asked.append("ruler_not_covered")
        if ask_direction:
            asked.append("ruler_direction")
        extra = {"accepted": True, "reversed": bool(ev.get("reversed")),
                 "questions_asked": asked,
                 "derived_mm_per_step": (pitch_mm / pitch_cut)
                 if pitch_cut and pitch_mm else None,
                 "pitch_steps": pitch_cut, "coverage_steps": coverage,
                 "followed": followed, "span_steps_used": span,
                 "question": ask, "other_question": other_question,
                 "direction_question": ask_direction,
                 # 4.3.40 (F4): against the reference the question uses
                 # (the majority of the recent votes; before there is one,
                 # the earlier votes when they all agree), no longer the
                 # first strip that was not saved reversed
                 "direction_agrees": (filed_sign == reference)
                 if filed_sign and reference else None,
                 # 4.3.40, additive (revision 2 of the file):
                 "direction_reference": reference or None,
                 "direction_votes_before": window,
                 "direction_colours": colours.as_dict() if colours else None,
                 "direction_confirmed_by_colours": vouched,
                 # 4.3.42, additive: this strip restarted the reference
                 "direction_restarted": restarted,
                 "voted": voted,
                 # review of 4.3.40: the questions whose "keep" answer this
                 # reading's vote still waits for (cast then, see "answers")
                 "vote_waits_for": sorted(
                     self._pending_votes[strip][1])
                 if strip in self._pending_votes else []}
        self._write(rec, strip, f, "asked" if (ask or ask_direction)
                    else "accepted", extra)
        return summary

    #: The fewest accepted strips whose directions make a majority, and the
    #: share the majority must hold (4.3.37).
    DIRECTION_MIN_VOTES = 3
    DIRECTION_SHARE = 0.75
    #: 4.3.40: the majority is taken over the most RECENT votes only, so
    #: that after a turned sheet (or ruler) it follows the new way round
    #: within a strip or two. Over every vote of the session, 26 strips read
    #: one way held the majority for nine strips read the other way, each
    #: of them noted or asked, and then none at all (pharmacist's page 3,
    #: replay). Every vote in the window is a strip the ruler and the saving
    #: agreed on, or one whose colours vouched for it (F3): a strip ChromIQ
    #: asked about never votes, so a run of real back-to-front strips cannot
    #: move it. In a session read one way round every vote is the same and
    #: the window changes nothing.
    DIRECTION_RECENT = 5

    @property
    def direction_votes(self) -> "list[int]":
        """Every vote of this session, oldest first (one per strip)."""
        return list(self._votes.values())

    def _recent(self) -> "list[int]":
        votes = self._since_turn if self._turn_sign else self._votes
        return list(votes.values())[-self.DIRECTION_RECENT:]

    def _cast_vote(self, strip: str, sign: int) -> None:
        """One vote, at the end (a strip's earlier vote is replaced)."""
        self._votes.pop(strip, None)
        self._votes[strip] = sign
        if self._turn_sign:
            self._since_turn.pop(strip, None)
            self._since_turn[strip] = sign

    def _drop_vote(self, strip: str) -> None:
        self._votes.pop(strip, None)
        self._pending_votes.pop(strip, None)
        self._since_turn.pop(strip, None)

    def forget(self, strip: str) -> None:
        """A strip's reading was replaced outside a ``strip_read`` ("I read
        strip B", a strip turned round): its vote no longer describes the
        reading in the file (F3)."""
        self._drop_vote(str(strip or "").strip())

    def _early_reference(self) -> int:
        """Before there is a majority (fewer than DIRECTION_MIN_VOTES), the
        earlier votes when they all agree, for the log line only (the
        question waits for a majority)."""
        v = self.direction_votes
        if v and len(v) < self.DIRECTION_MIN_VOTES and len(set(v)) == 1:
            return v[0]
        return 0

    def _old_majority(self) -> int:
        """4.3.42: while a restarted reference is young, the majority the
        session would have without the restart (over every vote); else 0.

        Young means: the votes since the confirmed turn do not yet hold a
        majority of their own. Counting votes alone is not enough (review
        B1): after a one-strip turn and the turn back, three votes since the
        turn read +, -, - and hold no majority, while the session's last
        five do, and a ramp strip saved back to front then had no reference
        at all where 4.3.41 asked about it."""
        if not self._turn_sign:
            return 0
        since = list(self._since_turn.values())
        if len(since) >= self.DIRECTION_MIN_VOTES and self._majority_of(
                since[-self.DIRECTION_RECENT:]):
            return 0
        return self._majority_of(
            list(self._votes.values())[-self.DIRECTION_RECENT:])

    def _majority_direction(self) -> int:
        """+1 / -1: the direction most of the recent accepted strips agree
        on, or 0 when there are too few or no clear majority."""
        v = self._recent()
        if len(v) < self.DIRECTION_MIN_VOTES and self._turn_sign:
            # 4.3.42: right after a confirmed turn, the strip that showed it
            # is the reference until enough votes are cast since, for as
            # long as every one of them agrees with it
            if v and all(x == self._turn_sign for x in v):
                return self._turn_sign
            return 0
        return self._majority_of(v)

    def _majority_of(self, v: "list[int]") -> int:
        if len(v) < self.DIRECTION_MIN_VOTES:
            return 0
        plus = sum(1 for x in v if x > 0)
        if plus >= self.DIRECTION_SHARE * len(v):
            return 1
        if len(v) - plus >= self.DIRECTION_SHARE * len(v):
            return -1
        return 0

    #: Questions that put a strip's ORDER in doubt: no vote from it.
    ORDER_QUESTIONS = frozenset({"back_to_front", "unknown",
                                 "colours_say_back_to_front"})
    #: Answers that keep the reading, and answers that discard it.
    KEEP_ANSWERS = frozenset({"continue", "keep", "closed"})
    DISCARD_ANSWERS = frozenset({"reread", "remeasure", "was_like", "turn",
                                 "stop"})

    def _answered(self, strip: str, question: str, answer: str) -> None:
        strip = str(strip or "").strip()
        if answer in self.DISCARD_ANSWERS:
            self._drop_vote(strip)
            return
        p = self._pending_votes.get(strip)
        if p is None:
            return
        if question == "ruler_direction" and answer != "continue":
            # second look, MINOR-B: Escape or the title-bar X on the
            # direction window keeps the reading (as Continue Anyway, the
            # exit spec) but the person has not said what happened: no vote
            self._pending_votes.pop(strip, None)
            return
        if answer not in self.KEEP_ANSWERS:
            return
        vote, wait = p
        wait.discard(question)
        if not wait:
            del self._pending_votes[strip]
            self._cast_vote(strip, vote)

    def note_answer(self, strip: str, answer: str) -> None:
        """The answer to the ruler's own window (coverage or direction)."""
        self._answered(strip, "ruler_direction", answer)
        if self.diag is not None:
            self.diag.note_answer(strip, answer)
            self.diag.note_question_answer(strip, "ruler", answer)

    def note_question_answer(self, strip: str, question: str,
                             answer: str) -> None:
        """R5: the person's *answer* to *question* about *strip*."""
        self._answered(strip, question, answer)
        if self.diag is not None:
            self.diag.note_question_answer(strip, question, answer)

    def set_default_condition(self, condition: "str | None") -> None:
        """R4 (4.3.39): without -F, the condition the instrument's normal
        mode measures under, where it is known (M0), else None; the file
        then says where its condition came from."""
        if self.condition_source == "chosen":
            return                    # the person's -F choice stands
        self.condition = condition
        self.condition_source = "instrument default" if condition else None
        if self.diag is not None:
            self.diag.set_condition(condition, "instrument default"
                                    if condition else None)

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

    @staticmethod
    def _margin_line(strip: str, m: dict) -> str:
        """The one calm line for a strip the margin tolerance kept: what was
        left out, at which end, and why that was safe."""
        start = int(m.get("left_start") or 0)
        end = int(m.get("left_end") or 0)
        if m.get("rule") == "L":
            what = tr("The reading began right on the first patch, without "
                      "white paper before it. ChromIQ kept that first patch "
                      "as part of the strip.")
        elif start and end:
            what = tr("The white paper margin at both ends of the swipe had "
                      "been counted as a patch. ChromIQ left both out.")
        elif start:
            what = tr("The white paper margin at the start of the swipe had "
                      "been counted as a patch. ChromIQ left it out.")
        elif end:
            what = tr("The white paper margin at the end of the swipe had "
                      "been counted as a patch. ChromIQ left it out.")
        else:
            what = tr("ArgyllCMS's patch finder could not settle on the "
                      "patches, although the ruler shows each of them in "
                      "turn.")
        # "as a whole": the rule compares the mean over the row (and over
        # each half), not every single patch (review 2026-11-16, MAJOR-1)
        return tr(
            "Strip {strip}, margin tolerance (beta): ArgyllCMS refused this "
            "reading (“{reason}”). {what} The reading was kept because the "
            "strip as a whole matches the colours expected for strip {strip} "
            "clearly better than those of any other strip, of any shifted "
            "position or of the reverse direction, and it was then checked "
            "like every other strip.").format(strip=strip,
                             # ArgyllCMS's own words, as this language
                             # shows them everywhere else (the (i) help, the
                             # misread window); an unknown one stays as sent
                             # (re-check NIT-R2)
                             reason=tr(str(m.get("refused_because") or "")),
                             what=what)

    def _direction_line(self, strip: str, reversed_: bool) -> str:
        # A DIRECTION, NOT A VERDICT (review of 4.3.35): "it went from the
        # first patch to the last" read as "it covered every patch", right
        # before a question saying that it did not. Only the way it moved.
        # 4.3.40 (F4): its own line, written once the saving is known, and
        # only when the ruler and the saving agree (`on_strip_read`); then
        # the way it moved over the patches is the way it was saved.
        if not reversed_:
            return tr("Ruler (beta), strip {strip}: the instrument moved in "
                      "the reading direction, from the first patch towards "
                      "the last.").format(strip=strip)
        return tr("Ruler (beta), strip {strip}: the instrument moved against "
                  "the reading direction, from the last patch towards the "
                  "first.").format(strip=strip)

    def _lost_line(self) -> str:
        """Second look of 4.3.40, MINOR-A: the recent strips no longer agree
        on how the sheet lies (a turn in progress, or answers that point
        both ways): said once, until they agree again."""
        return tr("Ruler (beta): the last strips do not agree about which way "
                  "round the sheet lies, so for the moment the ruler check "
                  "has no clear picture of it. It will not ask about the "
                  "direction again until a few more strips agree. Your "
                  "readings are not affected by this.")

    def _turned_note(self, strip: str) -> str:
        """4.3.40: the ruler disagrees with the earlier strips, the colours
        vouch for the saved order: no window, this line."""
        return tr("Ruler (beta), strip {strip}: the ruler saw this strip the "
                  "other way round compared with the strips before it. That "
                  "is what it looks like when the sheet or the ruler has been "
                  "turned round. The colours of this strip clearly show that "
                  "its readings were saved the right way round, so there is "
                  "nothing you need to do.").format(strip=strip)

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
