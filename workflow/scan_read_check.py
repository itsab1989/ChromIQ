"""Is the data about to become a scanner profile actually this chart, in full?

Review 5 (2026-09-03) found five ways the scanner window builds a profile from
data that is not what it says it is, with every indicator on screen green. They
are not five faults. They are one question the app never asks, and there is
exactly one artefact that can answer it: the ``.ti3`` scanin writes, whose every
row carries **what the scanner saw** (``RGB_*``) beside **what the reference
says that patch is** (``XYZ_*``), before colprof has run.

So this module asks the question once, from one parse, and the window turns the
answer into what the user reads.

Three things are measured, because no one of them can stand for the others:

**Coverage** — how many of the chart's patches are in the data at all. Review 5
case D: a reference file holding the first 48 rows of the target's own correct
288-row reference (a truncated download, a partial export, a maker's "short"
file). scanin keeps only the ids the reference names, so 240 patches were read
off the scan and thrown away, and the profile described the scanner from a sixth
of the sheet. Every other signal was green — including colprof's own self-check,
which scored **better** than the correct build (0.185/0.076 against 0.620/0.098),
because forty-eight points fit a matrix beautifully. Counting is the only thing
that sees this, which is why it is measured before the read (against the
reference the user picked) and again after it (against the rows that arrived).

**Agreement** — :func:`scan_reference_correlation`'s rank agreement between the
scan's luminance and the reference's Y. Already computed by the window, and
until now used only as a gate on whether to run a *further* check. It is the one
number that names a wrong reference or an upside-down scan.

**Clipping** — the share of patches sitting at the top or the bottom of the
device scale. Clipping is the one scan fault that cannot be profiled around: the
values are gone, not merely shifted, and the profile treats "as bright as this
scanner goes" as a measurement.

What each MISSES matters as much, and is the reason there are three:

* agreement misses coverage (case D reads +0.968 — the rows that survived are
  correct) and misses clipping (a 39 %-clipped scan reads +0.943, because
  clipping shifts values without reordering them);
* coverage misses a reference with the right count and the wrong values;
* clipping misses anything that stops short of a rail.

Pure functions, no Qt, no ArgyllCMS — the window supplies the paths and the
thresholds, and decides what to say.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.text_io import read_text


# --------------------------------------------------------------- CGATS ids
def _plain_id(sid: str) -> str:
    """``H01`` -> ``H1``. scanin zero-pads sample IDs on output and reference
    files do not, so every comparison here is made on the plain form.

    Kept in step with ``ui.dialogs.scanin_dialog._plain_id`` deliberately: a
    coverage check that normalised ids differently from the code that pairs
    them would report a mismatch the read does not have.
    """
    m = re.match(r"([A-Za-z]+)0*(\d+)$", sid)
    return (m.group(1) + m.group(2)) if m else sid


def _split_row(line: str) -> list[str]:
    """CGATS data row -> fields, keeping a quoted field in one piece."""
    return re.findall(r'"[^"]*"|\S+', line)


def reference_patch_ids(ref: Path) -> "set[str] | None":
    """The patch names a reference file gives colours for.

    Handles the three shapes ChromIQ accepts as a *direct* reference (see
    :mod:`workflow.reference_convert`): a ``.cie`` / ``.txt`` whose ``SAMPLE_ID``
    is the patch name, and a ``.ti3`` whose ``SAMPLE_ID`` is a row number and
    whose ``SAMPLE_LOC`` carries the name — the shape ``cxf2ti3`` and
    ``txt2ti3`` produce, so a converted reference reads correctly too.

    ``None`` when the file cannot be parsed as CGATS at all. **None means "do
    not judge"**, never "nothing matched": a reference this cannot read is a
    reference this must not accuse.
    """
    try:
        text = read_text(ref, lenient=True)
    except OSError:
        return None
    lines = text.splitlines()
    try:
        fs = next(i for i, l in enumerate(lines)
                  if l.strip().upper() == "BEGIN_DATA_FORMAT")
        fields = _split_row(lines[fs + 1])
        ds = next(i for i, l in enumerate(lines)
                  if l.strip().upper() == "BEGIN_DATA")
        de = next(i for i, l in enumerate(lines[ds:], ds)
                  if l.strip().upper() == "END_DATA")
    except (StopIteration, IndexError):
        return None
    upper = [f.upper() for f in fields]
    if "SAMPLE_LOC" in upper:
        col = upper.index("SAMPLE_LOC")
    elif "SAMPLE_ID" in upper:
        col = upper.index("SAMPLE_ID")
    else:
        return None
    out: set[str] = set()
    for line in lines[ds + 1:de]:
        row = _split_row(line)
        if len(row) > col:
            out.add(_plain_id(row[col].strip('"')))
    return out or None


def read_patch_ids(ti3: Path) -> "set[str] | None":
    """The patch names a scanin ``.ti3`` actually holds rows for."""
    return reference_patch_ids(ti3)


def number_of_sets(ti3: Path) -> "int | None":
    """The ``NUMBER_OF_SETS`` a CGATS file declares, or ``None``."""
    try:
        text = read_text(ti3, lenient=True)
    except OSError:
        return None
    m = re.search(r"^NUMBER_OF_SETS\s+(\d+)", text, re.M)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------ the findings
@dataclass(frozen=True)
class Coverage:
    """How much of the chart a reference file describes."""

    chart_patches: int
    reference_rows: int
    #: chart patches the reference names — the ones scanin will keep
    covered: int

    @property
    def missing(self) -> int:
        return max(0, self.chart_patches - self.covered)

    @property
    def fraction(self) -> float:
        return (self.covered / self.chart_patches) if self.chart_patches else 1.0

    def is_short(self, floor: float) -> bool:
        """True when the reference leaves out more of the chart than *floor*
        allows. A reference with MORE rows than the chart is not short — the
        extra rows simply go unused, and review 4 measured that building a
        perfect profile (peak 0.62, avg 0.098 on a 400-row reference for a
        288-patch target)."""
        return self.chart_patches > 0 and self.fraction < floor


def reference_coverage(ref: Path,
                       chart_ids: "set[str] | None") -> "Coverage | None":
    """Compare a reference file with the patches the chart's ``.cht`` reads.

    ``None`` when either side cannot be read — the check declines to judge
    rather than guessing, because the cost of a false accusation here is a user
    who learns to ignore the message that matters.
    """
    if not chart_ids:
        return None
    ref_ids = reference_patch_ids(ref)
    if ref_ids is None:
        return None
    return Coverage(chart_patches=len(chart_ids),
                    reference_rows=len(ref_ids),
                    covered=len(chart_ids & ref_ids))


@dataclass(frozen=True)
class ReadInspection:
    """What one page's read looks like, measured from its own ``.ti3``."""

    rows: int
    #: patches the page's chart geometry promised, when it could be read
    chart_patches: "int | None"
    #: rank agreement with the reference; ``None`` when it cannot be computed
    agreement: "float | None"
    #: share of patches sitting at the top / bottom of the device scale
    clipped_high: float
    clipped_low: float

    @property
    def covered_fraction(self) -> "float | None":
        if not self.chart_patches:
            return None
        return self.rows / self.chart_patches

    def is_short(self, floor: float) -> bool:
        f = self.covered_fraction
        return f is not None and f < floor

    @property
    def clipped(self) -> float:
        """The worse of the two rails. One number, because the message names
        which rail it is separately and a scan that clips both is not twice as
        wrong."""
        return max(self.clipped_high, self.clipped_low)


#: Device value (0-100) at or above which a patch has hit the top of the scale,
#: and at or below which it has hit the bottom. Not 100/0 exactly: an 8-bit
#: scan quantises to 255ths (0.392 apart), and a patch pinned at 255 in one
#: channel averages a shade under 100 once scanin means the sample box over
#: noise. Measured on review 4's material: every legitimate scan sits at 0.0 %
#: with these limits, and the over-exposed one at 39.2 %.
CLIP_HIGH = 99.5
CLIP_LOW = 0.5


def inspect_read(ti3: Path, chart_patches: "int | None",
                 agreement: "float | None") -> "ReadInspection | None":
    """Measure one page's read. *agreement* is passed in rather than recomputed
    because the window already has it — this module does not import Qt and the
    correlation lives beside the code that uses it for the alignment ladder.

    ``None`` when the ``.ti3`` cannot be parsed. Nothing here raises: a sanity
    check that can stop a build is worse than no sanity check.
    """
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        t = parse_ti3(ti3)
    except (OSError, Ti3ParseError, ValueError):
        return None
    if t.rgb is None or len(t.rgb) == 0:
        return None
    n = len(t.rgb)
    hi = int((t.rgb.max(axis=1) >= CLIP_HIGH).sum())
    lo = int((t.rgb.min(axis=1) <= CLIP_LOW).sum())
    return ReadInspection(rows=n, chart_patches=chart_patches,
                          agreement=agreement,
                          clipped_high=hi / n, clipped_low=lo / n)
