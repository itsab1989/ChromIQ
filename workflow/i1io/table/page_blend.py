# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""THE PAGE BLEND CHECK ON THE TABLE (4.3.69, item 76): does the page lie where it was aimed?

WHY. The opening is 4.5 mm round and a row is 8 mm across, so 1.75 mm are left on each side. A sheet
that lies a few millimetres ACROSS the rows from where its marks were aimed is read partly on the
neighbouring row: at 3.5 mm a third of the opening (36 %) lies there. The aim checks do not see
it: the triangle of a sheet moved after the aims, or aimed off by the same amount at every mark, has
its shape, and one mark 3.5 mm off across a 275 mm side turns it by 0.73 degrees, under the
1 degree limit. Neither does any check of a row: the placement check measures along the row, and
the identity check compares ranks, which a part-patch blend keeps (own score at least 0.59 at
3.5 mm on the owner's real pages, every row "ok", readings 15 dE76 off in the median, 35 at p95).

WHAT. The i1Profiler import's own neighbour-strip check (``measure_chart.blend_share``,
unchanged, its limit ``BLEND_LIMIT`` 0.12) over the rows of the page read SO FAR on the present
aims: the largest share of a neighbouring row's colour in a row's readings. Measured on the owner's
real pages (25 and 26 Nov 2026; numbers only, kept privately): right pages never above 0.030 after
any row; a sheet 3.5 mm across above the limit after row 2 to 5 (0.24 to 0.35 on the whole page),
3.0 mm after row 3 to 9, one mark aimed 3.5 mm off after row 2 to 3. 2.5 mm (a share of 0.11,
readings 4.6 dE76 off in the median) is not found.

NOT JUDGED (said in the logs): no expected colours (a calibration chart, an ink set without them),
fewer than two complete neighbouring rows, rows whose neighbours differ by less than
``measure_chart.BLEND_MIN_DIFF`` (the function skips them by itself). Nothing here is sent to the
table; numpy only through ``measure_chart``.
"""
from __future__ import annotations

#: THE SHIP SWITCH (no user option): False turns the check off.
PAGE_BLEND_CHECK = True
#: the reason of the rows it drops (the row identity check's family: nothing of them is kept)
REASON = "page_not_where_aimed"


def limit() -> float:
    import workflow.i1io.measure_chart as mc
    return float(mc.BLEND_LIMIT)


def _runs(rows: "list[int]") -> "list[list[int]]":
    out: "list[list[int]]" = []
    for r in sorted(set(rows)):
        if out and r == out[-1][-1] + 1:
            out[-1].append(r)
        else:
            out.append([r])
    return out


def judge(rows: "dict[int, list[str]]", measured: "dict[str, tuple]",
          expected: "dict[str, tuple]") -> dict:
    """The verdict on the rows read so far of one page. *rows*: ``{row index: locations in the
    row's order}`` of the rows read on the present aims; *measured*: ``{location: Lab}``;
    *expected*: the chart's ``{location: Lab}``. Returns ``{"judged", "why", "share", "row",
    "rows", "beside"}`` (row: 0-based, the row where the share is largest). Never raises."""
    out = {"judged": False, "why": "", "share": None, "row": None, "rows": len(rows),
           "beside": False}
    try:
        if not PAGE_BLEND_CHECK:
            out["why"] = "switched off"
            return out
        if not expected:
            out["why"] = "the chart names no expected colours"
            return out
        full = [r for r, locs in rows.items()
                if locs and all(q in measured and q in expected for q in locs)]
        best, at, judged = None, None, False
        for run in _runs(full):
            if len(run) < 2:
                continue
            n = len(rows[run[0]])
            run = [r for r in run if len(rows[r]) == n]
            if len(run) < 2:
                continue
            import numpy as np
            import workflow.i1io.measure_chart as mc
            E, M = [], []
            for c in range(n):                      # the import's order: column by column
                for r in run:
                    q = rows[r][c]
                    E.append(expected[q])
                    M.append(measured[q])
            share, row = mc.blend_share(np.array(E, float), np.array(M, float), len(run), n)
            judged = True
            if best is None or share > best:
                best, at = float(share), (run[row] if row is not None else None)
        if not judged:
            out["why"] = "fewer than two complete neighbouring rows"
            return out
        out.update(judged=True, share=best, row=at, beside=best > limit())
    except Exception as exc:      # noqa: BLE001 - never a reason to lose a row
        out.update(judged=False, beside=False, why=f"could not be judged ({type(exc).__name__})")
    return out


def summary(v: dict) -> str:
    """One line for the detailed table log and the app log."""
    if not v["judged"]:
        return f"page blend check: not judged: {v['why']}"
    row = "" if v["row"] is None else f" (largest at row {v['row'] + 1})"
    if v["beside"]:
        return (f"page blend check: THE ROWS HOLD THEIR NEIGHBOURS' COLOURS, share "
                f"{v['share']:.2f} over {v['rows']} rows{row}, limit {limit():.2f}: the sheet lies "
                "across from where it was aimed")
    return f"page blend check: share {v['share']:.2f} over {v['rows']} rows{row}, limit " \
           f"{limit():.2f}"
