"""A read-only cell of the Report limits table paints on the same line as the
spin boxes beside it.

B8-572 (carried in as B8-556). `ThresholdsDialog._make_cell`, the non-editable
branch, called::

    lab.setAlignment(Qt.AlignmentFlag.AlignRight)

`setAlignment` REPLACES the whole alignment rather than adding to it, and
`AlignRight` carries no vertical bit, so Qt fell back to the default for a
label, which is top. Every read-only cell -- a number, `–`, `?`, `✕` and a
bracketed value -- therefore sat above the spin boxes in its own row.

**THIS FILE DOES NOT READ THE ALIGNMENT FLAG, AND THAT IS THE POINT.** Three
guards on this project have asserted a flag and been believed while the pixels
said otherwise. What is measured here is the INK: each cell is painted into an
image and the vertical centre of the glyphs it actually draws is compared with
the centre of its own rectangle.

It is a companion to the photograph, not a replacement for it. The on-screen
measurement lives in `scripts/drive_b8570_the_verdict_ruling.py` and its proof
folder; that one measures a real window through the window server, where the
before/after was taken. This one is what fails in CI the day somebody writes
`setAlignment(AlignRight)` again.

MUTATION PROVEN TO LAND: drop `| Qt.AlignmentFlag.AlignVCenter` from
`_make_cell` and the first two tests below go red. The third does not and is
not meant to: it exists to stop the other two passing on an empty table, so it
is about what is DRAWN and not about where the ink sits.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import Qt                                   # noqa: E402
from PyQt6.QtCore import QSettings                            # noqa: E402
from PyQt6.QtGui import QImage, QPainter                      # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDoubleSpinBox,    # noqa: E402
                             QLabel)

from core.settings import AppSettings                         # noqa: E402
from workflow import compliance_sets as cs                    # noqa: E402

#: the row this suite marks, and the one it gives a plain number to, so that a
#: read-only cell of EVERY kind is on screen at once. Both numbers are ChromIQ
#: default's own; no figure from any standard appears here.
MARKED = "grey_balance_neutral_ramp_max"
NUMBERED = "control_strip_de00_avg"

#: BOTH THRESHOLDS ARE MEASURED, not chosen. With the fault in place the worst
#: read-only cell's ink centre sits at **0.318** of its own height and the worst
#: label-to-spin-box drift is **0.159**; fixed, they are **0.500** and
#: **0.068**. The two numbers below sit between those pairs with room on each
#: side, so neither a passing build nor the fault is anywhere near the edge.
#:
#: The first cut used 0.33 and 0.18, which were guessed: 0.33 caught the fault
#: by 0.012 and 0.18 missed it altogether, so two of the three tests here
#: passed with the bug in the tree and the docstring claimed all three failed.
MIN_INK_CENTRE = 0.40
MAX_PAIR_DRIFT = 0.10


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dlg(qapp, tmp_path, monkeypatch):
    f = tmp_path / "iso12647.json"
    f.write_text(json.dumps({"iso_12647_7": {MARKED: [3.0, "should"],
                                             NUMBERED: 2.0},
                             "iso_12647_8": {}}), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(f))
    cs.reset_iso_cache()
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    d = ThresholdsDialog(s, None)
    d.resize(1500, 980)
    yield d
    d.deleteLater()
    cs.reset_iso_cache()


def _ink_centre(w) -> "float | None":
    """Where the glyphs this widget paints sit, as a fraction of its height.

    0.0 is the top edge, 1.0 the bottom, 0.5 dead centre. Painted into an image
    of the widget's own size, so nothing outside the widget can contribute.
    """
    if w.width() < 2 or w.height() < 2:
        return None
    img = QImage(w.width(), w.height(), QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    w.render(p, flags=w.RenderFlag.DrawChildren)
    p.end()
    rows = []
    for y in range(img.height()):
        for x in range(img.width()):
            px = img.pixel(y and x or x, y)
            r, g, b = (px >> 16) & 255, (px >> 8) & 255, px & 255
            # anything clearly darker than the ground is glyph ink
            if r + g + b < 3 * 200:
                rows.append(y)
                break
    if not rows:
        return None
    return ((rows[0] + rows[-1]) / 2.0) / float(w.height())


def _pairs(dlg):
    """(row id, kind, the read-only cell, a spin box in the same row)."""
    by_row: dict = {}
    for (col, rid), w in dlg._cells.items():
        lim = dlg._limits_of(col).get(rid)
        kind = "none" if lim is None else ("should" if lim.is_should
                                           else lim.kind)
        by_row.setdefault(rid, []).append((kind, w))
    out = []
    for rid, cells in by_row.items():
        spins = [w for _k, w in cells if isinstance(w, QDoubleSpinBox)]
        if not spins:
            continue
        for kind, w in cells:
            if isinstance(w, QLabel):
                out.append((rid, kind, w, spins[0]))
    return out


def test_every_read_only_cell_paints_near_the_middle_of_its_own_cell(dlg):
    """The fault, stated directly: the text sat at the TOP of the cell."""
    high = []
    for rid, kind, lab, _sb in _pairs(dlg):
        c = _ink_centre(lab)
        if c is None:
            continue
        if c < MIN_INK_CENTRE:
            high.append((rid, kind, lab.text(), round(c, 3)))
    assert not high, (
        f"read-only cells whose ink centre is above {MIN_INK_CENTRE} of their "
        f"own height: {high[:8]}")


def test_a_read_only_cell_and_a_spin_box_in_one_row_share_a_line(dlg):
    """The comparison a reader actually makes, across the row."""
    off = []
    for rid, kind, lab, sb in _pairs(dlg):
        a, b = _ink_centre(lab), _ink_centre(sb)
        if a is None or b is None:
            continue
        if abs(a - b) > MAX_PAIR_DRIFT:
            off.append((rid, kind, lab.text(), round(a, 3), round(b, 3)))
    assert not off, (
        "a read-only cell and the spin box beside it do not share a line: "
        f"{off[:8]}")


def test_all_five_cell_kinds_are_actually_on_screen_here(dlg):
    """Guard the guard: the two tests above would pass vacuously if the window
    happened to draw no read-only cells at all, and four of the five kinds only
    exist when a values file supplies numbers.

    `value` is a plain number in a read-only column, `should` a bracketed one,
    and both arrive from the fixture's hand-marked file -- which is the only
    source of either, since Knut's ruling of 2026-09-21 took the last
    recommendation out of ChromIQ's own sets.
    """
    kinds = {k for _r, k, w, _s in _pairs(dlg) if _ink_centre(w) is not None}
    # `unmeasurable` rows have no spin box anywhere in them, so they never pair
    for want in ("value", "should", "none", "unknown"):
        assert want in kinds, (want, sorted(kinds))
    # …and the fifth kind, checked without a pair
    crosses = [w for (c, r), w in dlg._cells.items()
               if isinstance(w, QLabel) and w.text() == "✕"]
    assert crosses, "no unmeasurable cell was drawn"
    centres = [c for c in (_ink_centre(w) for w in crosses) if c is not None]
    assert centres and min(centres) >= MIN_INK_CENTRE, (
        f"✕ cells sit high: {sorted(centres)[:5]}")
