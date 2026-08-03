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
    """**A** — how many patches the chart has, or ``None`` if it cannot be read."""
    if ti2_path is None or not Path(ti2_path).is_file():
        return None
    counts = count_sets(ti2_path)
    if counts is None:
        return None
    claimed, held = counts
    # The .ti2's own body is authoritative over its header for the same reason
    # the .ti3's is: the rows are the thing, the header is a claim about them.
    return held if held else claimed


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
    if expected is not None and held > expected:
        return Ti3Facts(Ti3State.MISMATCHED, claimed, held, expected)
    if expected is not None and held < expected:
        return Ti3Facts(Ti3State.PARTIAL, claimed, held, expected)
    if expected is not None:
        return Ti3Facts(Ti3State.COMPLETE, claimed, held, expected)
    # No chart to compare against: readings exist, and that is all we know.
    return Ti3Facts(Ti3State.PARTIAL, claimed, held, None)


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
