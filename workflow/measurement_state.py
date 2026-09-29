"""What state a measurement file is in, and what a session did to it.

The decision half of *Unified Measurement Management* — see
``docs/design/unified_measurement_management.md`` §3, agreed on issue #130.
Deliberately free of Qt and of any file-manager knowledge: it reads CGATS files
and returns findings, so every row of the specification's §3a and §3b tables can
be tested as arithmetic rather than through a window.

**The one fact behind all of it** (§0): ArgyllCMS ``chartread`` holds its
readings in memory and writes the ``.ti3`` only on a clean exit. So the file on
disk after a session is the only evidence of what happened, and it has to be
read carefully — three numbers, not one:

* **A** — ``NUMBER_OF_SETS`` in the ``.ti2``: how many patches the chart HAS.
* **B** — ``NUMBER_OF_SETS`` in the ``.ti3``: how many the file CLAIMS.
* **C** — rows between ``BEGIN_DATA`` and ``END_DATA``: how many it HOLDS.

A fourth number, **C₀**, is C measured *before* a session starts. Knut supplied
it (#130, 2026-08-03) and it is what makes a session's own result measurable:
``C - C₀`` is exactly how many patches this session added. Without it a resume
that destroyed its own input is undetectable — the end state alone cannot tell
"read nothing" from "lost everything".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

_SETS_RE = re.compile(r"^\s*NUMBER_OF_SETS\s+(\d+)", re.MULTILINE | re.IGNORECASE)


class Ti3State(Enum):
    """Every state a measurement file can be in — specification §3a."""

    ABSENT = "absent"
    """No file at all. Normal for a fresh run."""

    NO_DATA_BLOCK = "no_data_block"
    """A header, but no ``BEGIN_DATA``/``END_DATA`` at all. Knut named this one
    (#130, 2026-08-03); it reads as "no measurements", exactly like EMPTY."""

    EMPTY = "empty"
    """``BEGIN_DATA`` is there and holds no rows. Nothing was saved."""

    MISMATCHED = "mismatched"
    """The header and the body disagree (``B != C``), or the file holds more
    readings than the chart has patches (``C > A``). ChromIQ can see that two
    numbers disagree; it cannot see WHY, so nothing here calls the file
    damaged."""

    PARTIAL = "partial"
    """``0 < C < A``. Expected after a session that ended early."""

    COMPLETE = "complete"
    """``C == A``. Every patch of the chart has a reading."""

    UNREADABLE = "unreadable"
    """The file exists and could not be read. A different problem from empty,
    and must never be mistaken for it."""


@dataclass(frozen=True)
class Ti3Facts:
    """What is actually in a measurement file, with nothing inferred."""

    state: Ti3State
    claimed: "int | None" = None      # B
    held: "int | None" = None         # C
    expected: "int | None" = None     # A, from the .ti2

    @property
    def has_readings(self) -> bool:
        return bool(self.held)

    @property
    def can_resume(self) -> bool:
        """Only a partial file may be resumed.

        A MISMATCHED file must never be offered: resuming into a mismatch would
        write readings against patch positions that may not be the ones on the
        paper (§5, M-TI3-MISMATCH).
        """
        return self.state is Ti3State.PARTIAL


def count_sets(path: "Path | str") -> "tuple[int | None, int | None] | None":
    """``(claimed, held)`` for a CGATS file, or ``None`` when it cannot be read.

    *claimed* is the header's ``NUMBER_OF_SETS`` and is ``None`` when the file
    has none; *held* is the number of data rows and is ``None`` when the file
    has no ``BEGIN_DATA`` block at all — which is not the same as zero rows, and
    the caller is entitled to tell them apart.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    m = _SETS_RE.search(text)
    claimed = int(m.group(1)) if m else None

    # Split on the keyword rather than parsing line by line: a CGATS file may
    # carry several tables, and it is the FIRST data block that a measurement
    # lives in. END_DATA closes it; anything after belongs to another table.
    parts = re.split(r"^\s*BEGIN_DATA\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(parts) < 2:
        return claimed, None

    body = re.split(r"^\s*END_DATA\s*$", parts[1], maxsplit=1,
                    flags=re.MULTILINE)[0]
    held = sum(1 for ln in body.splitlines() if ln.strip())
    return claimed, held


def expected_patches(ti2_path: "Path | str | None") -> "int | None":
    """**A** — how many patches the chart has, or ``None`` if it cannot be read.

    PADDING ROWS ARE NOT PATCHES. A ``printtarg`` sheet is filled out to a whole
    number of strips with rows whose ``SAMPLE_ID`` is ``0``; they are never
    printed as readable patches and chartread never writes a reading for one.
    Counting them made every complete measurement of such a chart look partial:
    a real 1,155-row chart on this machine carries three of them, and a 1,173-row
    one carries thirteen. The Measure tab's progress was already right, because
    the helper's own "all done" excludes them — it was this second, independent
    count that disagreed, and it told the user their finished measurement was
    "1,152 of 1,155" and advised them to go back and resume.

    THE LINE THAT USED TO STAND HERE — "charts from ChromIQ's own layout engine
    have no padding" — IS FALSE, and a user met the consequence on 2026-09-11.
    The engine pads exactly as printtarg does (``layout_engine/ti2_writer``
    appends ``layout.padding`` copies of the media patch), it simply numbers
    those rows ``SAMPLE_ID`` 4001, 4002 … like any other, so the ``SAMPLE_ID``
    0 rule cannot see them. Her chart: 4,000 designed, 4,014 in the ``.ti2``,
    the last 14 rows paper white. A complete 4,000-patch measurement of it was
    labelled "4000 of 4014 patches measured" and filed as partial. See
    :func:`_engine_fill_up_rows`.
    """
    if ti2_path is None or not Path(ti2_path).is_file():
        return None
    counts = count_sets(ti2_path)
    if counts is None:
        return None
    claimed, held = counts
    padding = _padding_rows(ti2_path)
    if held:
        # The .ti2's own body is authoritative over its header for the same
        # reason the .ti3's is: the rows are the thing, the header is a claim
        # about them.
        return max(0, held - padding)
    return max(0, claimed - padding) if claimed is not None else None


def sheet_patches(ti2_path: "Path | str | None") -> "int | None":
    """How many patches the chart actually PRINTS, or ``None`` if unreadable.

    :func:`expected_patches` is the DESIGN — how many patches were asked for,
    and the number a measurement is judged complete against. This is the SHEET:
    every square the instrument passes over, the fill-up rows of the last strip
    included. The two differ by the padding, and both are real:

    * a person reading the sheet in ChromIQ, or aiming an i1iO at it in
      i1Profiler, reads what is PRINTED, so a complete measurement of her chart
      holds the sheet count;
    * the chart was DESIGNED with fewer, and that is what "the whole chart was
      measured" has to mean, because the fill-up rows are copies of the media
      patch and were never part of the target.

    Counting only the design made a complete 420-patch measurement of a
    408-patch chart read as "a measurement of a different chart" and refused it
    (a user verifying a profile, 2026-09-11). Counting only the sheet had
    already made the mirror mistake the day before, and called a complete
    measurement partial. A measurement between the two numbers covers the whole
    design; above the sheet it is a measurement of something else.
    """
    if ti2_path is None or not Path(ti2_path).is_file():
        return None
    counts = count_sets(ti2_path)
    if counts is None:
        return None
    claimed, held = counts
    if held:
        return held
    return claimed


def _padding_rows(path: "Path | str") -> int:
    """Rows the chart adds to fill its last strip, which are not patches.

    TWO LAYOUT ENGINES PAD, NOT ONE.

    * ``printtarg`` marks its fill-up rows by giving them ``SAMPLE_ID`` 0.
    * ChromIQ's own layout engine appends copies of the media patch with
      ordinary sequential ids, so nothing in the row says what it is. That is
      what :func:`_engine_fill_up_rows` reads instead.
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    parts = re.split(r"^\s*BEGIN_DATA\s*$", text, maxsplit=1, flags=re.MULTILINE)
    if len(parts) < 2:
        return 0
    body = re.split(r"^\s*END_DATA\s*$", parts[1], maxsplit=1,
                    flags=re.MULTILINE)[0]
    n = 0
    for ln in body.splitlines():
        fields = ln.split()
        if fields and fields[0] == "0":
            n += 1
    return n or _engine_fill_up_rows(path, text, body)


_ENGINE_ORIGINATOR_RE = re.compile(
    r'^\s*ORIGINATOR\s+"?ChromIQ layout engine', re.MULTILINE | re.IGNORECASE)
_STEPS_RE = re.compile(r'^\s*STEPS_IN_PASS\s+"?(\d+)', re.MULTILINE | re.IGNORECASE)


def _engine_fill_up_rows(path: "Path | str", text: str, body: str) -> int:
    """How many trailing rows of a ChromIQ-layout-engine ``.ti2`` are fill-up.

    THE ANSWER IS IN THE ``.ti1``, NOT IN A GUESS. The engine lays the chart out
    from the run's ``.ti1`` and appends ``[media] * layout.padding`` after the
    designed patches, so the designed count is the ``.ti1``'s own first table
    and the difference is the fill-up — exact, not a heuristic. A trailing-white
    scan on its own would over-count whenever the design's own last patch is
    paper white, and the design is randomised, so that happens.

    Three guards, because a stale or unrelated ``.ti1`` must never be allowed to
    shrink a chart's patch count and turn a partial measurement into a complete
    one:

    * the ``.ti2`` must say it came from the engine (``ORIGINATOR``);
    * the surplus must be smaller than one strip — that is all padding can ever
      be (``geometry.py``: ``padding = pprow - lpprow``, one pass at most);
    * the trailing rows must all be the SAME patch, which is what appending one
      media colour that many times produces.

    0 when any of that does not hold, which reads as "this chart has no fill-up"
    and leaves the old count exactly as it was.
    """
    if not _ENGINE_ORIGINATOR_RE.search(text):
        return 0
    rows = [ln.split() for ln in body.splitlines() if ln.strip()]
    if not rows:
        return 0
    try:
        ti1 = Path(path).with_suffix(".ti1")
        designed_text = ti1.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    # The FIRST table of a .ti1 is the patch set; targen writes two reference
    # tables after it (see workflow/i1profiler_import.read_first_cgats_table).
    m = _SETS_RE.search(designed_text)
    if m is None:
        return 0
    surplus = len(rows) - int(m.group(1))
    steps = _STEPS_RE.search(text)
    limit = int(steps.group(1)) if steps else 0
    if surplus <= 0 or not limit or surplus >= limit:
        return 0
    tail = rows[-surplus:]
    # Column 0 is SAMPLE_ID and column 1 SAMPLE_LOC; both differ per row by
    # construction. Everything after them is the patch itself.
    if any(r[2:] != tail[0][2:] for r in tail):
        return 0
    return surplus


def classify(ti3_path: "Path | str | None",
             ti2_path: "Path | str | None" = None) -> Ti3Facts:
    """Which row of specification §3a this measurement file is on."""
    if ti3_path is None or not Path(ti3_path).is_file():
        return Ti3Facts(Ti3State.ABSENT, expected=expected_patches(ti2_path))

    counts = count_sets(ti3_path)
    expected = expected_patches(ti2_path)
    if counts is None:
        return Ti3Facts(Ti3State.UNREADABLE, expected=expected)

    claimed, held = counts
    if held is None:
        return Ti3Facts(Ti3State.NO_DATA_BLOCK, claimed, None, expected)
    if held == 0:
        return Ti3Facts(Ti3State.EMPTY, claimed, 0, expected)
    if claimed is not None and claimed != held:
        return Ti3Facts(Ti3State.MISMATCHED, claimed, held, expected)
    # ABOVE THE SHEET, NOT ABOVE THE DESIGN. A chart whose last strip is filled
    # out is read patch by patch including those fill-up rows, so a complete
    # measurement of a 408-patch design printed on a 420-square sheet holds 420
    # — and judging that against 408 called it a measurement of a different
    # chart. `sheet_patches` is the number of squares; `expected_patches` the
    # number the design asked for. Only past the sheet is it another chart.
    sheet = sheet_patches(ti2_path)
    if sheet is not None and held > sheet:
        return Ti3Facts(Ti3State.MISMATCHED, claimed, held, expected)
    if sheet is None and expected is not None and held > expected:
        return Ti3Facts(Ti3State.MISMATCHED, claimed, held, expected)
    if expected is not None and held < expected:
        return Ti3Facts(Ti3State.PARTIAL, claimed, held, expected)
    if expected is not None:
        return Ti3Facts(Ti3State.COMPLETE, claimed, held, expected)
    # No chart to compare against: readings exist, and that is all we know.
    return Ti3Facts(Ti3State.PARTIAL, claimed, held, None)


def can_resume(ti3_path: "Path | str | None",
               ti2_path: "Path | str | None" = None) -> bool:
    """Whether ``chartread -r`` has anything to resume from — specification §3a/§5.

    **Only a file with at least one readable reading can be resumed.** The model
    is explicit about every other case:

    * *"No `.ti3` at all … nothing measured yet | normal for a fresh run; C₀ = 0"*,
      and §5's first row pairs "None" with **no warning** — so the measurement
      simply starts.
    * A header-only or empty file *"holds no measurements — treat as empty"*.
    * A corrupt file (``B ≠ C``) is to be **"never offer[ed] for resume"**.
    * And §3a is explicit that all of these give ``C₀ = 0``: *"When the `.ti3`
      present at the start of a measurement is corrupt or empty … there is
      nothing in it to resume from and nothing to lose by measuring again, and it
      is treated exactly as 'no measurement'."*

    ChromIQ was sending ``-r`` on the strength of the checkbox alone, so a run
    whose measurement had been replaced or never made was started in resume mode
    against a file that was not there. chartread refuses outright —
    ``Unable to read chart being resumed … Unable to open file`` — and the
    fallback to stock chartread kept the flag and failed the same way, which is
    what Knut's log shows at 19:09 (#148). His ruling: *"The action when a ti3
    file is not existing or is corrupt or empty is defined by the design
    specification and the unified measurement management model. Make sure this
    is handled accordingly."*

    So the tick is honoured whenever it can be, and quietly ignored when there is
    nothing behind it — which is what §5's "no warning" row asks for. Nothing is
    lost either way: resuming from nothing and starting fresh are the same
    measurement.
    """
    facts = classify(ti3_path, ti2_path)
    return facts.state in (Ti3State.PARTIAL, Ti3State.COMPLETE)


def has_any_readings(ti3_path: "Path | str | None") -> bool:
    """Whether the file holds at least one reading — the RESCUE test, not §3a's.

    **Deliberately weaker than :func:`can_resume`, and the difference matters.**
    They answer two different questions:

    * `can_resume` answers *"the user ticked Refine / resume — should ChromIQ act
      on it?"*, and follows §3a strictly: a corrupt file (``B ≠ C``) is *"never
      offer[ed] for resume"*, because resuming into a mismatch would write
      readings against patch positions that may not be the ones on the paper.
    * This one answers *"the instrument just died mid-chart — is there anything
      worth saving?"* (#134). Here a refusal **throws away measured strips**,
      which is the one outcome the whole rescue exists to prevent. So it declines
      only when it is certain there is nothing: no file, an empty one, a
      header-only one, or one that cannot be parsed at all.

    Tightening this to `can_resume` looked tidy and was wrong: it would have made
    a damaged autosave — precisely the case a crash is most likely to leave —
    the one case where the readings are silently abandoned.
    """
    facts = classify(ti3_path, None)
    return facts.state not in (Ti3State.ABSENT, Ti3State.EMPTY,
                               Ti3State.NO_DATA_BLOCK, Ti3State.UNREADABLE)


class SessionVerdict(Enum):
    """What to do with what a session left behind — specification §3b."""

    KEEP = "keep"
    """The file is sound; leave it and say what was added."""

    DELETE_AND_RESTORE = "delete_and_restore"
    """Nothing was saved. Put the archived copy back."""

    RESTORE_AND_KEEP_BOTH = "restore_and_keep_both"
    """Readings went BACKWARDS. Put the archived copy back and keep the new
    file beside it, because something went wrong and neither may be thrown
    away."""

    NOTHING_TO_DO = "nothing_to_do"
    """No file before, no file after."""


def judge_session(before: "int | None", after: "int | None",
                  *, resumed: bool) -> SessionVerdict:
    """Compare C₀ with C — specification §3b.

    *before* and *after* are reading counts; ``None`` means "no file". This is
    the check that catches the failure Knut described: a resume that starts with
    ten patches and ends with none has destroyed its own input, and no
    examination of the end state alone can see it.
    """
    b = before or 0
    a = after or 0
    if a == 0:
        return SessionVerdict.DELETE_AND_RESTORE if b > 0 \
            else SessionVerdict.NOTHING_TO_DO
    if resumed and b > 0 and a < b:
        return SessionVerdict.RESTORE_AND_KEEP_BOTH
    return SessionVerdict.KEEP


def added_by_session(before: "int | None", after: "int | None") -> int:
    """How many readings this session contributed. Never negative — a negative
    result means something went wrong, which :func:`judge_session` reports as a
    verdict rather than as a number."""
    return max(0, (after or 0) - (before or 0))


# ---------------------------------------------------------------------------
# Measurement progress (#153, Knut)
# ---------------------------------------------------------------------------
#: Which measurement states may show a progress bar at all.
#:
#: Knut asked for the same validity rules the rest of ChromIQ uses: *"If no ti3
#: file, or an empty or corrupted ti3 file (using same rules as for checking if
#: ti3 is valid on other features), then no progress bar is shown."*
#:
#: MISMATCHED is deliberately excluded even though it holds readings. When the
#: header and the body disagree, ChromIQ refuses to resume the file
#: (:attr:`Ti3Facts.can_resume`), and a bar reading "73%" beside a refusal to
#: continue would be telling the user two different things about one file.
PROGRESS_STATES = frozenset({Ti3State.PARTIAL, Ti3State.COMPLETE})


def progress_percent(measured: "int | None",
                     total: "int | None") -> "float | None":
    """How far a measurement has got, 0-100, or ``None`` when it cannot be said.

    ``None`` means "draw no bar" — the caller still shows ``Progress: 0.0%``,
    which is what Knut asked for: the label is always there, the coloured bar
    only appears once there is something true to draw.

    Clamped to 100: a session that re-reads a patch already counted in the file
    it resumed from can momentarily count one patch twice, and a bar that reads
    101% would be a worse lie than one that sits at 100 until the file is read
    again and settles it.
    """
    if not total or total <= 0 or measured is None or measured < 0:
        return None
    return min(100.0, measured / total * 100.0)


def progress_from_files(ti3_path: "Path | str | None",
                        ti2_path: "Path | str | None") -> "float | None":
    """The progress a run's files describe, or ``None`` for no bar.

    Used when the Measure tab opens, so a part-finished measurement is picked
    up where it was left. During a live measurement the files are NOT the
    truth — ArgyllCMS writes the ``.ti3`` only when a session ends cleanly — so
    the tab counts patches as they are reported instead, and comes back to this
    once the session is over.
    """
    facts = classify(ti3_path, ti2_path)
    if facts.state not in PROGRESS_STATES:
        return None
    return progress_percent(facts.held, facts.expected)
