"""Is the sheet that was just measured the sheet that was expected?

Review of #214, M4: the FD-9 finds four symmetric marks and the declared
grid, so a sheet turned round (180 degrees) or another page of the same chart
with the same grid is measured as if it were the right one, and a complete,
wrong measurement would be filed. Nothing printed on the sheet can tell them
apart, and no device command is added for it.

What can tell them apart is the readings themselves. Every FD-9 chart's .ti2
carries the colour each patch should have (``XYZ_Y``, the engine's aim). After
a sheet is read, its measured lightness pattern is compared, by rank
correlation, with the pattern each hypothesis predicts at the measured
positions:

* the expected page the right way round;
* the expected page turned round (position (r, c) holds the patch printed at
  (R-1-r, C-1-c));
* every other page of the chart with the same grid, both ways round.

THE CHECK IS CONSERVATIVE BY DESIGN: it says something only when the expected
hypothesis fits badly AND another one fits well AND by a wide margin, and it
stays quiet when it cannot decide: too few patches, too little contrast
(a dark-only or a light-only chart), or a hypothesis whose prediction is
almost the same as the expected one (a chart that looks the same turned
round, or two identical pages). A normal read correlates well with its own
page, so it can never trip it.
"""
from __future__ import annotations

import math

#: Fewer patches than this and the check says nothing.
MIN_PATCHES = 24
#: Lightness range (L*) the measured and the predicted pattern must both span.
MIN_SPREAD_L = 15.0
#: The expected hypothesis must fit no better than this...
EXPECTED_AT_MOST = 0.4
#: ...another one at least this well...
OTHER_AT_LEAST = 0.8
#: ...and by at least this much.
MARGIN = 0.4
#: A hypothesis that predicts nearly the expected pattern cannot be told
#: apart from it, so it is not considered.
INDISTINGUISHABLE = 0.9


#: Why the check said nothing (`check_sheet` returns one of these, or None
#: when it compared and found the sheet right). Logged once per sheet, so a
#: quiet check is never read as a passed one (review r1 L2).
SKIP_FEW = "too few patches"
SKIP_FLAT_READINGS = "the readings have too little contrast"
SKIP_NO_AIMS = "the chart has no usable expected colours"
SKIP_LOOKS_ALIKE = "no other sheet or turn would look different"
#: The line the worker reports; `ui.fd9_measurement._progress_line` puts it
#: into the user's words.
SKIPPED_LINE = "Sheet check skipped: "


class SheetMismatch(ValueError):
    """The readings fit another sheet, or the expected sheet turned round,
    clearly better than the expected sheet. ``kind`` is ``"turned"`` or
    ``"wrong_sheet"``; pages are numbered from 1."""

    def __init__(self, kind, page, found, pages, expected_fit, found_fit,
                 turned=None):
        self.kind, self.page, self.found, self.pages = kind, page, found, pages
        self.expected_fit, self.found_fit = expected_fit, found_fit
        #: whether the best fit is the found page TURNED ROUND (always for
        #: "turned"; either way for "wrong_sheet"), so that a sheet can be
        #: filed where it belongs (4.3.25, F7)
        self.turned = (kind == "turned") if turned is None else bool(turned)
        what = (f"page {page} turned round" if kind == "turned"
                else f"page {found}")
        super().__init__(
            f"Sheet check: the readings fit {what} (rank correlation "
            f"{found_fit:.2f}) much better than page {page} of {pages} "
            f"(rank correlation {expected_fit:.2f}); not filed")

    def window_kind(self) -> str:
        """The kind string the Measure tab maps to its window
        (`ui.fd9_measurement.fd9_exception_kind`)."""
        return f"{self.kind}:{self.page}:{self.found}:{self.pages}"


def _lightness(y):
    t = max(float(y), 0.0) / 100.0
    f = t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f - 16


def _ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0
        i = j + 1
    return ranks


def spearman(a, b):
    """Rank correlation of two equally long sequences; 0 when either is
    constant."""
    ra, rb = _ranks(list(a)), _ranks(list(b))
    n = len(ra)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra)
    vb = sum((y - mb) ** 2 for y in rb)
    if va <= 0 or vb <= 0:
        return 0.0
    return cov / math.sqrt(va * vb)


def _spread(values):
    return max(values) - min(values) if values else 0.0


def check_sheet(pages, page_index, design, measured):
    """Raise :class:`SheetMismatch` when the readings of page *page_index*
    clearly belong to another page or to the page turned round. Otherwise
    return None when the sheet was compared and fits, or one of the SKIP_*
    reasons when the check could not decide.

    *pages* are the chart's physical pages (each with ``rows`` of patches
    carrying ``id``), *design* maps a patch id to its .ti2 row (with
    ``XYZ_Y``), and *measured* holds the TI3 rows read from this sheet (with
    ``SAMPLE_ID`` and ``XYZ_Y``)."""
    page = pages[page_index]
    grid = [[p["id"] for p in row] for row in page["rows"]]
    shape = (len(grid), len(grid[0]) if grid else 0)
    where = {pid: (r, c) for r, row in enumerate(grid) for c, pid in enumerate(row)}
    positions, seen = [], []
    for record in measured:
        try:
            pid = int(record["SAMPLE_ID"])
            y = float(record["XYZ_Y"])
        except (KeyError, TypeError, ValueError):
            continue
        if pid in where and math.isfinite(y):
            positions.append(where[pid])
            seen.append(_lightness(y))
    if len(seen) < MIN_PATCHES:
        return SKIP_FEW
    if _spread(seen) < MIN_SPREAD_L:
        return SKIP_FLAT_READINGS

    def predicted(q, turned):
        ids = [[p["id"] for p in row] for row in pages[q]["rows"]]
        rows, cols = shape
        out = []
        for r, c in positions:
            pid = ids[rows - 1 - r][cols - 1 - c] if turned else ids[r][c]
            try:
                out.append(_lightness(float(design[pid]["XYZ_Y"])))
            except (KeyError, TypeError, ValueError):
                return None
        return out

    expected = predicted(page_index, False)
    if expected is None or _spread(expected) < MIN_SPREAD_L:
        return SKIP_NO_AIMS
    expected_fit = spearman(seen, expected)
    best = None
    for q, other in enumerate(pages):
        rows = [[p["id"] for p in row] for row in other["rows"]]
        if (len(rows), len(rows[0]) if rows else 0) != shape:
            continue
        for turned in (False, True):
            if q == page_index and not turned:
                continue
            guess = predicted(q, turned)
            if guess is None or _spread(guess) < MIN_SPREAD_L:
                continue
            # SIGNED (review r1 L3): only a pattern that looks the SAME is
            # indistinguishable. The exact reverse of the expected pattern
            # (a ramp chart turned round) is the easiest case to recognise.
            if spearman(guess, expected) >= INDISTINGUISHABLE:
                continue
            fit = spearman(seen, guess)
            if best is None or fit > best[0]:
                best = (fit, q, turned)
    if best is None:
        return SKIP_LOOKS_ALIKE
    fit, q, turned = best
    if (expected_fit <= EXPECTED_AT_MOST and fit >= OTHER_AT_LEAST
            and fit - expected_fit >= MARGIN):
        kind = "turned" if (q == page_index and turned) else "wrong_sheet"
        raise SheetMismatch(kind, page_index + 1, q + 1, len(pages),
                            round(expected_fit, 3), round(fit, 3),
                            turned=turned)
    return None


#: What a person can answer to a sheet check (4.3.25, F7), the way the strip
#: check asks (M-STRIP-READ-TWICE): measure the page again (the safe answer,
#: and what closing the window does), file the readings where they belong,
#: or keep them as read.
AGAIN = "again"
REFILE = "refile"
KEEP = "keep"

#: The provenance written per page into the .ti3 (`FD9_SHEET_CHECK_PAGE_<n>`):
#: how the check went and what the person chose. Values, not prose.
PROVENANCE_KEY = "FD9_SHEET_CHECK_PAGE_{page}"
MATCHED = "MATCHED"
NOT_CHECKED = "NOT_CHECKED"
TURNED_SAVED_TURNED = "TURNED_SAVED_TURNED_ROUND"
TURNED_KEPT = "TURNED_KEPT_AS_READ"
FROM_SHEET_ASKED_AS = "SAVED_FROM_SHEET_ASKED_AS_PAGE_{page}"
OTHER_PAGE_KEPT = "LOOKED_LIKE_PAGE_{found}_KEPT_AS_READ"


def refile(measured, pages, page_index, target_index, turned, design,
           locations):
    """The readings *measured* from the sheet asked for as page
    *page_index*, filed under the patches of page *target_index* (the same
    page for a sheet turned round), turned round when *turned*: the reading
    at grid position (r, c) belongs to the patch printed at (R-1-r, C-1-c).
    Every field that comes from the chart (the device values) is taken from
    the patch it now belongs to, so the .ti3 stays consistent with its
    chart. Only for a COMPLETE sheet (the caller checks)."""
    source = pages[page_index]["rows"]
    target = pages[target_index]["rows"]
    rows, cols = len(source), len(source[0])
    if (len(target), len(target[0])) != (rows, cols):
        raise ValueError("Pages of different shape cannot be refiled")
    where = {p["id"]: (r, c) for r, row in enumerate(source)
             for c, p in enumerate(row)}
    out = []
    for record in measured:
        r, c = where[int(record["SAMPLE_ID"])]
        if turned:
            r, c = rows - 1 - r, cols - 1 - c
        pid = target[r][c]["id"]
        new = dict(record)
        chart_row = design[pid]
        for field, value in chart_row.items():
            if field in new and not field.startswith(
                    ("XYZ_", "SPEC_", "LAB_", "SAMPLE_")):
                new[field] = value
        new["SAMPLE_ID"] = str(pid)
        new["SAMPLE_LOC"] = locations[pid]
        out.append(new)
    return out
