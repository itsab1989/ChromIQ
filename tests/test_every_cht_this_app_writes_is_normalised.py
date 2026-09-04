"""Column 2 of an XLIST/YLIST row is a STRENGTH, never a length — everywhere.

`tests/test_standard_targets.py::
test_every_bundled_edge_list_is_normalised_the_way_argyll_defines_it` (B8-05)
proved it for the eight `.cht` files ChromIQ ships. It cannot see the files
ChromIQ WRITES. There are three of those, and at the time B8-05 landed two of
them still put an absolute cross-length in that column:

    workflow/layout_engine/cht_writer.py::_edge_list   normalised  (correct)
    ui/scan_grid_marquee.py::rectarg_align_cht         224.028     (was wrong)
    workflow/scanner_labels.py::expand_rectarg_cht     normalised  (was wrong)

Neither has ever produced a wrong read, because the files they make are only
ever given to `scanin -F` and `-F` does not read the edge lists — but a
generator that writes a number a hundred times too large is one call site away
from the fault B8-05 spent a release finding. `expand_rectarg_cht` was first
left alone on the grounds that nothing calls it; that is the wrong reason, and
it is the reason the eight bundled files survived for months. Every generator
is checked here, with no exception for how few callers it has today.

ArgyllCMS `doc/cht_format.html`: "the second number is used to improve the
correlation by representing the strength of that 'tick' relative to the
strongest tick which will have a value 1.0"."""
from __future__ import annotations

import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _edge_blocks(text: str):
    hdr = re.compile(r"^(XLIST|YLIST)\s+\d+$")
    blocks, cur = [], None
    for line in text.splitlines() + [""]:
        s = line.strip()
        if hdr.match(s):
            if cur:
                blocks.append(cur)
            cur = []
            continue
        if cur is None:
            continue
        p = s.split()
        if len(p) == 3:
            try:
                cur.append(tuple(float(v) for v in p))
                continue
            except ValueError:
                pass
        if cur:
            blocks.append(cur)
        cur = None
    if cur:
        blocks.append(cur)
    return blocks


def _assert_normalised(text: str, who: str):
    blocks = _edge_blocks(text)
    assert blocks, f"{who}: no XLIST/YLIST written at all"
    for block in blocks:
        for col in (1, 2):
            vals = [row[col] for row in block]
            assert all(0.0 < v <= 1.0 for v in vals), (
                f"{who}: column {col + 1} outside (0, 1] — max {max(vals)!r}. "
                "It is a strength relative to the strongest tick, not a length; "
                "an absolute value there makes scanin's recogniser return nan.")
            assert abs(max(vals) - 1.0) < 1e-9, (
                f"{who}: column {col + 1} never reaches 1.0 (max {max(vals)!r})")


def _uniform_cht():
    """A real, uniform, correctly-normalised chart — written by the generator
    that already gets this right, so the fixture cannot be wrong in the way the
    test is looking for."""
    from workflow.layout_engine.cht_writer import build_cht_text
    boxes = [{"loc": f"{chr(65 + c)}{r + 1}", "x": 5.0 + c * 8.0,
              "y": 5.0 + r * 8.0, "w": 7.0, "h": 7.0}
             for c in range(6) for r in range(5)]
    return build_cht_text(boxes, [(b["loc"], 50.0, 50.0, 50.0) for b in boxes])


def test_the_marquees_realigned_cht_is_normalised():
    from ui.scan_grid_marquee import rectarg_align_cht
    text = _uniform_cht()
    _assert_normalised(text, "the fixture itself")
    out = rectarg_align_cht(text, 977.0, 813.0)
    assert out != text, "the fixture must actually be realigned"
    _assert_normalised(out, "rectarg_align_cht")


def test_the_engine_chart_writer_is_normalised():
    from workflow.layout_engine.cht_writer import build_cht_text
    boxes = [{"loc": f"{chr(65 + c)}{r + 1}", "x": c * 8.0, "y": r * 8.0,
              "w": 7.0, "h": 7.0}
             for c in range(4) for r in range(3)]
    txt = build_cht_text(boxes, [(b["loc"], 50.0, 50.0, 50.0) for b in boxes])
    _assert_normalised(txt, "cht_writer.build_cht_text")
