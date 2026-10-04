"""Collapse a runaway stream of identical tool lines (beta 10, Knut's beta-8 logs).

Knut unplugged the instrument during a measurement. Argyll's USB layer
(``native/instlib/usbio_ox.c``) then printed
``icoms_usb_transaction: ReadPipeAsync failed with 0xe00002c0`` about two
thousand times a second until the run was stopped, and every one of those lines
went into ChromIQ's log TWICE (``core.argyll_runner``'s ``[argyll]`` line and the
Measure tab's mirror of its panel): some 255,000 lines in one minute, which
rotated every earlier line of the session out of the five log files.

This gate sits where the tool's output enters ChromIQ, so the log file, the log
panel and every parser see the same thing:

* a line is shown as before, and so are its first ``SHOW`` identical repeats
  inside one burst, so nothing that reacts to a line (the disconnection window,
  "asked again" counts) sees anything different from before;
* later repeats in the burst are counted, not shown. A summary line refers to the
  line shown above and gives the count: at most one per ``SUMMARY_EVERY`` seconds while the burst
  goes on, so the flood is capped at a line every few seconds and the panel is
  never silent long enough for the keystroke watchdog to think the tool hung;
  and a last one when the burst ends (another line, ``BURST_GAP`` of quiet
  via :meth:`RepeatGate.idle`, or the end of the run). The summary does
  not quote the line, so no parser counts it as one more of it, and a single
  hidden repeat is passed on as itself rather than as "1 more time";
* a burst is identical lines less than ``BURST_GAP`` seconds apart. A line that
  comes back after a pause (a prompt asked again after the user pressed a key)
  starts a new burst and is always shown;
* engine events (JSON lines, ``{`` after an optional BEL) are the helper's
  protocol and always pass untouched;
* only EXACT repeats are collapsed. Lines that differ, even only in a number
  (profcheck's per-patch lines, colprof's progress), are data somebody parses,
  and are never dropped.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Callable

#: Identical lines shown per burst before counting starts (the first and three
#: repeats, as the PTY reader always allowed).
SHOW = 4
#: Seconds between two identical lines that still belong to one burst.
BURST_GAP = 2.0
#: While a burst goes on, at most one summary per this many seconds. Below the
#: Measure tab's 12 s keystroke watchdog, so it never mistakes a flood for a hang.
SUMMARY_EVERY = 5.0
#: How many different lines are tracked at once: a flood that alternates
#: between a few lines is collapsed too.
TRACK = 8


def is_engine_event(line: str) -> bool:
    return line.lstrip("\x07 \t").startswith("{")


#: Every summary starts with this and ends with :data:`SUMMARY_END`.
SUMMARY_MARK = "[ChromIQ: the "
SUMMARY_END = ", not shown]"


def is_summary(line: str) -> bool:
    return line.startswith(SUMMARY_MARK) and line.endswith(SUMMARY_END)


def summary_line(count: int, lines: int = 1) -> str:
    """The line that stands for *count* (two or more) hidden repeats of the
    *lines* line(s) shown just before. It does NOT quote the line (beta-10
    review): every parser of tool output searches the lines it is handed
    (``measure_manager._USB_ERROR_RE`` looks for "ReadPipeAsync failed"
    anywhere in a line), so a summary quoting it was counted as one more of
    it; and hiding the quote from the parsers (a joiner between every two
    characters) made the log unsearchable and put invisible characters into
    every copy of it. The line itself was shown, word for word, ``SHOW``
    times just above. A single hidden repeat is passed on as the line
    itself instead ("came 1 more time" was the first thing a flood showed)."""
    if lines == 1:
        return f"{SUMMARY_MARK}line shown above came {count} more times{SUMMARY_END}"
    return (f"{SUMMARY_MARK}{lines} lines shown above came {count} more times "
            f"between them{SUMMARY_END}")


class _Burst:
    __slots__ = ("seen", "last", "hidden")

    def __init__(self, now: float) -> None:
        self.seen = 1
        self.last = now
        self.hidden = 0


class RepeatGate:
    """Feed it every line in order; it returns the lines to pass on."""

    def __init__(self, clock: "Callable[[], float]" = time.monotonic) -> None:
        self._clock = clock
        self._bursts: "OrderedDict[str, _Burst]" = OrderedDict()
        self._last_summary = clock()
        self.hidden_total = 0

    def _summaries(self, lines) -> "list[str]":
        counted = []
        for line in lines:
            b = self._bursts.get(line)
            if b is not None and b.hidden:
                counted.append((line, b.hidden))
                b.hidden = 0
        if all(n == 1 for _ln, n in counted):
            # One hidden repeat is cheaper said as itself, and exact.
            return [ln for ln, _n in counted]
        # Lines reported together (a flood alternating between two lines)
        # share one summary: it cannot quote them, so it cannot tell them
        # apart either.
        return [summary_line(sum(n for _ln, n in counted), len(counted))]

    def _expire(self, now: float, keep: "str | None") -> "list[str]":
        gone = [ln for ln, b in self._bursts.items()
                if ln != keep and now - b.last > BURST_GAP]
        out = self._summaries(gone)
        for ln in gone:
            del self._bursts[ln]
        return out

    def feed(self, line: str) -> "list[str]":
        now = self._clock()
        if is_engine_event(line):
            return self._expire(now, None) + [line]
        out = self._expire(now, line)
        b = self._bursts.get(line)
        if b is not None and now - b.last > BURST_GAP:
            out += self._summaries([line])
            del self._bursts[line]
            b = None
        if b is None:
            # Another line: the bursts it interrupts report what they hid.
            out += self._summaries(list(self._bursts))
            # A NEW LINE ENDS EVERY REPEAT THAT IS NOT YET A FLOOD. Ordinary
            # output repeats a few lines between new ones: colprof's blank
            # lines, targen's "Re-seeding", chartread's strip menu reprinted
            # for every 'f' of a quick navigation. Counted across the new
            # lines, they were hidden after the fourth time in every normal
            # run. A flood never prints new lines, so a line already past
            # SHOW stays collapsed, and a flood of two alternating lines is
            # still caught: after the second line, neither is new.
            for other in self._bursts.values():
                if other.seen <= SHOW:
                    other.seen = 1
            self._bursts[line] = _Burst(now)
            while len(self._bursts) > TRACK:
                old, _b = next(iter(self._bursts.items()))
                out += self._summaries([old])
                del self._bursts[old]
            out.append(line)
            return out
        b.last = now
        b.seen += 1
        if b.seen <= SHOW:
            out.append(line)
            return out
        if b.hidden == 0 and not any(o.hidden for o in self._bursts.values()):
            # Counting starts now: the first summary of it is SUMMARY_EVERY
            # away, not due at once because the run was quiet for a while
            # (the "came 1 more time" just before "came 109996 more times").
            self._last_summary = max(self._last_summary, now)
        b.hidden += 1
        self.hidden_total += 1
        if now - self._last_summary >= SUMMARY_EVERY:
            self._last_summary = now
            out += self._summaries(list(self._bursts))
        return out

    def is_flood_prefix(self, fragment: str) -> bool:
        """Is *fragment* (a read that ended mid-line) the start of the line
        being collapsed right now? A pipe read ends wherever the buffer did,
        so a flood arrives cut into a whole line plus pieces, and the pieces
        (all different) would each pass as new lines. The reader holds such a
        piece back for the next read instead. Only for a line already past
        ``SHOW``: a prompt (no newline) that is not flooding is never held."""
        if not fragment:
            return False
        return any(b.seen > SHOW and ln.startswith(fragment)
                   for ln, b in self._bursts.items())

    def pending(self) -> bool:
        """Is any repeat counted and not yet reported?"""
        return any(b.hidden for b in self._bursts.values())

    def idle(self) -> "list[str]":
        """The tool has printed nothing for a while: report every burst that
        has been quiet longer than ``BURST_GAP``, so a flood that ends because
        the tool goes quiet is summed up then, not when the next line (maybe
        minutes later) arrives. Readers call it when a read times out."""
        return self._expire(self._clock(), None)

    def flush(self) -> "list[str]":
        """The run ended: report whatever is still being counted."""
        out = self._summaries(list(self._bursts))
        self._bursts.clear()
        return out
