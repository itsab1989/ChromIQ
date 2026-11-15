"""The two guards the import design of 2026-11-14 adds to the one-page i1iSis
import (the i1iSis chart Beta), §I.17 point 8.

G1: the device values of an i1iSis measurement prove which test chart
i1Profiler used, not how the sheet went in, so its colours are judged too: a
chart that can tell and does not agree is refused (also "cannot tell" for a
reason the readings give, challenge C2); a chart that cannot tell is filed as
before.

G2: a CxF whose NumberPatchPages is "0" carries no grid keyword in the
converted copy, so the grid check was skipped; the grid is read from the
picked file with "0" taken as one page.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import i1p_forward as F          # noqa: E402

R, C = 6, 10                                 # 60 patches


@dataclass(frozen=True)
class Order:
    sample_ids: tuple
    locs: tuple
    rows: int = R
    columns: int = C
    kind: str = "isis"
    pages: int = 1
    path: Path = Path("c-i1profiler-isis.order.json")


def _chart(tmp: Path, rgbs) -> Path:
    rows = [f'{i + 1} "L{i + 1}" {r:.4f} {g:.4f} {b:.4f} 0 0 0'
            for i, (r, g, b) in enumerate(rgbs)]
    ti2 = tmp / "c.ti2"
    ti2.write_text(
        'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ layout engine"\n'
        'COLOR_REP "RGB"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\n\n'
        f'NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n' + "\n".join(rows)
        + "\nEND_DATA\n")
    return ti2


def _measurement(tmp: Path, rgbs, order: Order, read_of) -> Path:
    """Entry j: SAMPLE_ID j+1, the .txf's device values (the order's patch),
    the colour of the patch physically read (*read_of(j)* -> 0-based)."""
    rng = np.random.default_rng(1)
    rows = []
    for j, sid in enumerate(order.sample_ids):
        dev = rgbs[sid - 1]
        lab = F.printer_lab(rgbs[order.sample_ids[read_of(j)] - 1], rng, 0.6)
        x, y, z = F._lab_to_xyz_d50(lab)
        rows.append(f'{j + 1} "{j + 1}" {dev[0]:.4f} {dev[1]:.4f} '
                    f'{dev[2]:.4f} {x:.4f} {y:.4f} {z:.4f}')
    ti3 = tmp / "m.ti3"
    ti3.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ"\nCOLOR_REP "iRGB_XYZ"'
        '\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC '
        'RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n'
        f'NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n' + "\n".join(rows)
        + "\nEND_DATA\n")
    return ti3


@pytest.fixture
def isis(monkeypatch, tmp_path):
    """A one-page i1iSis order for a 60-patch chart, `turned_match` answering
    with it (the order file mechanism is the branch's own, tested there)."""
    import workflow.i1profiler_turned as T
    rng = np.random.default_rng(7)

    def make(rgbs):
        ti2 = _chart(tmp_path, rgbs)
        perm = tuple(int(x) + 1 for x in rng.permutation(len(rgbs)))
        order = Order(perm, tuple(f"L{s}" for s in perm))

        def match(measured, chart):
            return T.TurnedMatch(applies=True, verified=True, order=order,
                                 compared=len(perm), fitting=(order,))
        monkeypatch.setattr(T, "turned_match", match)
        return ti2, order
    return make


def _random(n=60, seed=3):
    r = np.random.default_rng(seed)
    return [tuple(r.uniform(0, 100, 3)) for _ in range(n)]


def test_g1_a_right_measurement_is_filed(isis, tmp_path):
    from workflow.measurement_import import assess
    rgbs = _random()
    ti2, order = isis(rgbs)
    v = assess(_measurement(tmp_path, rgbs, order, lambda j: j), ti2)
    assert v.ok and v.turned_order, v.reason


def test_g1_a_sheet_fed_the_wrong_way_round_is_refused(isis, tmp_path):
    from workflow import measurement_messages as MM
    from workflow.measurement_import import assess
    rgbs = _random()
    ti2, order = isis(rgbs)

    def turned(j):
        r, c = j % R, j // R
        return (C - 1 - c) * R + (R - 1 - r)
    v = assess(_measurement(tmp_path, rgbs, order, turned), ti2)
    assert not v.ok and v.reason == MM.isis_colours_reason()


def test_g1_cannot_tell_on_a_chart_that_could_is_refused(isis, tmp_path,
                                                         monkeypatch):
    """C2: "between" (the readings, not the chart, leave it open) refuses."""
    from workflow import measurement_messages as MM
    from workflow.measurement_import import assess
    import workflow.turned_colour_check as TC
    rgbs = _random()
    ti2, order = isis(rgbs)
    monkeypatch.setattr(TC, "judge_turned_measurement",
                        lambda *a, **k: TC.ColourJudgement(
                            TC.UNSURE, "between", 0.6, 60))
    v = assess(_measurement(tmp_path, rgbs, order, lambda j: j), ti2)
    assert not v.ok and v.reason == MM.isis_colours_reason()


def test_g1_a_chart_that_cannot_tell_is_filed_as_before(isis, tmp_path):
    from workflow.measurement_import import assess
    greys = [(v, v, v) for v in np.linspace(0, 100, 60)]
    ti2, order = isis(greys)
    v = assess(_measurement(tmp_path, greys, order, lambda j: j), ti2)
    assert v.ok and v.turned_order, v.reason


def _cxf(tmp, rgbs, order, pages_attr, swap=False) -> Path:
    rng = np.random.default_rng(2)
    rd = []
    for j, sid in enumerate(order.sample_ids):
        rd.append((j % R, j // R, F.printer_lab(rgbs[sid - 1], rng, 0.5)))
    cells = [(r, c) for r, c, _ in rd]
    if swap:
        cells[0], cells[7] = cells[7], cells[0]
    return F.write_cmxf(tmp / "m.mxf", rd, columns=C, rows=R,
                        pages_attr=pages_attr, target_cells=cells)


def test_g2_pages_zero_is_read_as_one_page(isis, tmp_path):
    from workflow.i1profiler_turned import isis_grid_from_source
    from workflow.reference_convert import cxf_measurement_to_ti3, i1p_grid_of
    rgbs = _random()
    _ti2, order = isis(rgbs)
    src = _cxf(tmp_path, rgbs, order, "0")
    conv = cxf_measurement_to_ti3(src, tmp_path / "conv.ti3")
    assert i1p_grid_of(conv) is None              # the converter, unchanged
    g = isis_grid_from_source(src)
    assert (g.columns, g.rows, g.pages, g.located) == (C, R, 1, R * C)


def test_g2_misplaced_patches_are_no_longer_skipped(isis, tmp_path):
    from workflow.measurement_import import assess
    rgbs = _random()
    ti2, order = isis(rgbs)
    src = _cxf(tmp_path, rgbs, order, "0", swap=True)
    ti3 = _measurement(tmp_path, rgbs, order, lambda j: j)
    # without the picked file (4.3.37's call) the grid is not checked
    assert assess(ti3, ti2).ok
    v = assess(ti3, ti2, source=src)
    assert not v.ok and "2 of its 60 patches" in v.reason, v.reason
