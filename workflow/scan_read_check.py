"""Is the data about to become a scanner profile actually this chart, in full?

Review 5 (2026-09-03) found five ways the scanner window builds a profile from
data that is not what it says it is, with every indicator on screen green. They
are not five faults. They are one question the app never asks, and there is
exactly one artefact that can answer it: the ``.ti3`` scanin writes, whose every
row carries **what the scanner saw** (``RGB_*``) beside **what the reference
says that patch is** (``XYZ_*``), before colprof has run.

So this module asks the question once, from one parse, and the window turns the
answer into what the user reads.

Five things are measured, because no one of them can stand for the others:

**Coverage** — how many of the chart's patches the reference names at all.
Review 5 case D: a reference file holding the first 48 rows of the target's own
correct 288-row reference (a truncated download, a partial export, a maker's
"short" file). scanin keeps only the ids the reference names, so 240 patches
were read off the scan and thrown away, and the profile described the scanner
from a sixth of the sheet. Every other signal was green — including colprof's
own self-check, which scored **better** than the correct build (0.185/0.076
against 0.620/0.098), because forty-eight points fit a matrix beautifully.
Counting is the only thing that sees this.

Coverage is asked of the **reference**, never of the read. A read that came back
short already has two messages of its own — scanin's "Not all sample values have
been filled" and `_sanitize_scanner_ti3`'s dropped-patch note — and a third
voice saying the same thing in different numbers would be noise. What neither of
those can see is a read that filled every sample it was ASKED about, because the
reference asked about a sixth of the chart. That is what this counts, and it can
be counted before a single patch is read.

**Agreement** — :func:`scan_reference_correlation`'s rank agreement between the
scan's luminance and the reference's Y. Already computed by the window, and
until now used only as a gate on whether to run a *further* check. It is the one
number that names a wrong reference or an upside-down scan.

**Clipping** — the share of patches sitting at the top or the bottom of the
device scale. Clipping is the one scan fault that cannot be profiled around: the
values are gone, not merely shifted, and the profile treats "as bright as this
scanner goes" as a measurement.

**Highlight level** (beta 8, B8-01) — where the chart's own white sits on the
device scale. Everything above is **scale-invariant**, and an exposure slip is
**pure scale**: darken every pixel of a good scan by 30 % and coverage is
unchanged, the rank agreement is unchanged to three decimals (+0.9839 against
+0.9838), and the clipped share does not move by one patch. Measured on Knut's
own Wolf Faust sheet, that scan builds a profile with **no warning of any kind**
and a true error of 21.7 ΔE against a correctly exposed read; at ×0.18 it is
177.9 ΔE and still silent. See :func:`highlight_level` for the measure and why
it is the max channel of the reference's near-white patches rather than anything
about the mean, the black or the range.

**Fit support** (beta 8, B8-03) — how many DISTINCT colours the reference gives
the profile to be fitted to. colprof's own self-check is computed against the
same rows it was fitted to, so it is smallest exactly when there is least to
fit: a reference whose every ``SAMPLE_ID`` reads ``A1`` leaves one row, scores
``peak err = 0.007339, avg err = 0.007339`` and is reported as a triumph; a
reference whose every value is ``0.00`` leaves 288 rows of one colour, sends
colprof's Powell fit to ``residual error = nan`` and lands a profile whose white
point is ``nan nan nan``, again with no warning. Counting the distinct colours
is what sees both, before colprof spends two minutes on the second one.

What each MISSES matters as much, and is the reason there are three:

* agreement misses coverage (case D reads +0.968 — the rows that survived are
  correct) and misses clipping (a 39 %-clipped scan reads +0.943, because
  clipping shifts values without reordering them);
* coverage misses a reference with the right count and the wrong values;
* clipping misses anything that stops short of a rail — including every
  under-exposure, which never reaches one;
* the highlight level misses everything that is not about level: it is
  deliberately blind to tone curve, colour cast, paper and medium, which is the
  only reason it can be trusted about level;
* fit support misses a reference with plenty of distinct colours and the wrong
  ones — that is agreement's job.

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
    #: rank agreement with the reference; ``None`` when it cannot be computed
    agreement: "float | None"
    #: share of patches sitting at the top / bottom of the device scale
    clipped_high: float
    clipped_low: float

    #: device level (0-100) of the chart's own near-white patches, or ``None``
    #: when the reference names nothing near white — see :func:`highlight_level`
    highlight: "float | None" = None
    #: distinct reference colours the profile would be fitted to
    support: int = 0

    def disagrees(self, floor: float) -> bool:
        """True when the read and the reference barely rank together. ``None``
        agreement is not a disagreement — it means the pairing could not be
        computed, and a check that cannot see must not accuse."""
        return self.agreement is not None and self.agreement < floor

    def underexposed(self, floor: float) -> bool:
        """True when the chart's own white did not get near the top of the
        device scale. ``None`` is not an accusation, for the same reason as
        above: it means the reference named no near-white patch to judge by."""
        return self.highlight is not None and self.highlight < floor

    def fit_is_unsupported(self, floor: int) -> bool:
        """True when the reference gives too few distinct colours for a profile
        to be determined at all — and therefore too few for colprof's own
        self-check to mean anything."""
        return 0 < self.support < floor

    @property
    def clipped(self) -> float:
        """The worse of the two rails, because the message names which rail it
        is separately and a scan that clips both is not twice as wrong."""
        return max(self.clipped_high, self.clipped_low)

    @property
    def clipped_at_top(self) -> bool:
        return self.clipped_high >= self.clipped_low


#: Device value (0-100) at or above which a patch has hit the top of the scale,
#: and at or below which it has hit the bottom. Not 100/0 exactly: an 8-bit
#: scan quantises to 255ths (0.392 apart), and a patch pinned at 255 in one
#: channel averages a shade under 100 once scanin means its sample box over
#: noise. Measured across 30 reads (review 4's material and review 5's exposure
#: sweep): every well-exposed scan sits at 0.0 % with these limits.
CLIP_HIGH = 99.5
CLIP_LOW = 0.5


#: A reference patch counts as "near white" when its Y is within this much of
#: the brightest patch the reference names. On an IT8 that is the top of the
#: greyscale plus the Dmin patch — 10 patches of 288 on Wolf Faust, 17 of 864 on
#: the ISO 12641-2; on a ColorChecker it is the single white patch. The median
#: over them is taken so one dust speck cannot decide the verdict.
NEAR_WHITE = 0.95

#: The reference must claim a near-white patch before :func:`highlight_level`
#: says anything. Y is relative luminance 0-100, so 60 is about L* 82 — light
#: grey. A chart whose brightest patch is darker than that is a low-key target,
#: and there is no exposure to judge against: measured on a deliberately dark
#: chart (every reference value scaled to 0.28 and the scan darkened to match)
#: the near-white level reads 44.1, which would be an accusation, and the
#: reference's own brightest patch reads Y = 22.97, which declines instead.
HIGHLIGHT_REFERENCE_MIN_Y = 60.0

#: The minimum number of DISTINCT reference colours a profile may be fitted to.
#: The smallest target ChromIQ or ArgyllCMS ships is ``MLG``, 21 patches, and it
#: builds cleanly (self-check 0.61/0.22); the two degenerate references measured
#: in beta 8 leave **one** distinct colour each. 10 sits under half the smallest
#: legitimate case and ten times the degenerate one.
MIN_FIT_SUPPORT = 10


def highlight_level(rgb, xyz) -> "float | None":
    """Where the chart's own white landed on the device scale, 0-100.

    **The measure.** Take the patches the REFERENCE calls near-white, and report
    the median of their largest device channel. ``None`` when the reference
    names no near-white patch (see :data:`HIGHLIGHT_REFERENCE_MIN_Y`).

    **Why this and not something else.** A properly exposed scan puts the
    chart's brightest patch near the top of the device scale, because that is
    what setting the exposure *means*; and it is the one statement about level
    that survives a change of scanner, because every encoding curve fixes white.
    Three cheaper-looking measures were built and thrown away on the material
    below, each by a legitimate scan that beat an under-exposed one:

    * **mean device level.** A transparency's tone scale reads 28.04 where a
      scan darkened to −1.2 stops reads 27.27. The legitimate one is darker.
    * **the black patch sitting far above 0.** Matte paper, blacks lifted 8 %,
      reads 14.52 where the same −1.2 stops reads 5.04 and ×0.18 reads 1.29 —
      the check is upside down, and the transparency (1.38) is darker than the
      ×0.18 scan.
    * **device luminance of the white patch** rather than its max channel. A
      cool cast (0.66, 0.88, 1.00) drops the luminance of Knut's own white patch
      to 66.28, BELOW a genuinely under-exposed ×0.85 scan at 66.88. The max
      channel of the same two reads 80.44 and 68.28 — a cast moves the other
      channels, never the one the exposure was set by.

    **The material.** 74 reads, all through ``scanin`` with the app's own
    ``.cht`` rewrites: Knut's ten real IT8 sheets on his own scanner (two
    targets); this session's re-reads of his two full-resolution scans, at full
    size and at the 693 px he actually had on screen; the app's own demo scan
    for all 25 bundled and ArgyllCMS targets; nine legitimate variations built
    from his scans (a gamma-1.8 scanner, a gamma-2.6 scanner, matte paper, a
    transparency tone scale anchored at the medium's Dmin, a warm cast, a cool
    cast, a scanner running 12 % hot, 16-bit, JPEG q12); and ten deliberate
    under-exposures on both targets, ×0.85 down to ×0.18.

    ===============================================  ==============
    what                                             this measure
    ===============================================  ==============
    Knut's ten real sheets                           72.92 – 79.82
    this session's re-reads of the same two scans    74.84, 79.77
    the app's own demos, 25 targets                  80.96 – 94.34
    the nine legitimate variations                   69.57 – 83.86
    ×0.85 (−0.47 stop)                               67.84
    ×0.70 (−1.15 stops)                              55.85  /  52.43
    ×0.45                                            35.87  /  33.71
    ×0.18                                            14.47
    ===============================================  ==============

    The lowest legitimate reading of all 64 is 69.57 — a deliberately harsh
    synthetic tone scale; the lowest from real hardware is Knut's LaserSoft
    sheet 05 at 72.92. The floor lives in ``scanner_min_highlight``
    (:mod:`core.settings`) at **60**, which is 9.6 points under the worst
    legitimate case measured and 12.9 under the worst real one.

    **What it deliberately does not catch.** ×0.85 at 67.84 sits 1.7 points
    under that harsh synthetic case, and no threshold can separate them. Half a
    stop therefore passes in silence, and it is not free: that profile is 9.5 ΔE
    out against a correct read. Crying wolf costs more — the same user then
    clicks past the ×0.70 window, which is 21.7 ΔE out.
    """
    import numpy as np
    rgb = np.asarray(rgb, dtype=float)
    xyz = np.asarray(xyz, dtype=float)
    if rgb.ndim != 2 or rgb.shape[0] == 0 or xyz.shape[0] != rgb.shape[0]:
        return None
    y = xyz[:, 1]
    good = np.isfinite(y) & np.isfinite(rgb).all(axis=1)
    if not good.any():
        return None
    y = np.where(good, y, -np.inf)
    ymax = float(y.max())
    if not np.isfinite(ymax) or ymax < HIGHLIGHT_REFERENCE_MIN_Y:
        return None
    sel = good & (y >= NEAR_WHITE * ymax)
    if not sel.any():
        return None
    return float(np.median(rgb[sel].max(axis=1)))


def fit_support(xyz) -> int:
    """How many DISTINCT colours the reference gives the fit.

    Rounded to three decimals, which is finer than any reference file states its
    values and coarse enough that float noise cannot invent a colour. Rows whose
    reference is not a finite number are not colours and are not counted.

    Measured: 21 on the smallest target anybody ships (``MLG``), 24 on a
    ColorChecker, 288 on Wolf Faust, 864 on the ISO 12641-2 — and **1** on both
    of beta 8's degenerate references, the one that renames every patch ``A1``
    and the one that sets every value to ``0.00``.
    """
    import numpy as np
    xyz = np.asarray(xyz, dtype=float)
    if xyz.ndim != 2 or xyz.shape[0] == 0:
        return 0
    xyz = xyz[np.isfinite(xyz).all(axis=1)]
    if xyz.shape[0] == 0:
        return 0
    return len({tuple(v) for v in np.round(xyz, 3)})


def inspect_read(ti3: Path,
                 agreement: "float | None") -> "ReadInspection | None":
    """Measure one page's read. *agreement* is passed in rather than recomputed
    because the window already has it — this module does not import Qt, and the
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
    return ReadInspection(rows=n, agreement=agreement,
                          clipped_high=hi / n, clipped_low=lo / n,
                          highlight=highlight_level(t.rgb, t.xyz),
                          support=fit_support(t.xyz))
