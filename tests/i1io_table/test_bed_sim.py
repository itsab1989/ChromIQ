"""BedSim reads what LIES on the table (the harness of the new chart layout's tests): laid right it
gives the chart's printed colours, shifted it gives the neighbours', an uncut sheet gives the other
piece's, another chart gives that chart's. Through the app's own job, strips and patch by patch."""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_reading import read_page, ready_to_read
from workflow.i1io.table import measurement as ms

STRIP = ["-v", "-c", "1", "chart"]
SPOT = ["-v", "-c", "1", "-p", "chart"]


def read_all(tmp_path, chart, bed, opts, aims=None, rows=None):
    """Read the chart on *bed*; ``{loc: (X, Y, Z)}`` of every accepted patch."""
    job, sim, helper, run = B.bed_job(tmp_path, chart, bed, aims=aims,
                                      ask_after_each_step=False)
    # the bed itself is tested here: the row identity check would refuse what lies wrong
    job.expected_lab, job.expected_why = None, "the bed's own test"
    assert job.set_options(opts).ok
    p = H.Person(job, sim)
    ready_to_read(job, p)
    if rows is None:
        assert all(r.ok for r in read_page(job, p))
    else:
        for _k in range(rows):
            assert p.drive(job.read_row()).ok
    out = {}
    for q in sorted(job.diag.folder.rglob("*" + ms.ROW_RECORD_SUFFIX)):
        for a in json.loads(q.read_text(encoding="utf-8"))["accepted"]:
            out[a["loc"]] = a["xyz"]
    job.close()
    assert not sim.violations
    return out


def nominal_aims(chart):
    return B.Bed(chart.laid()).aims(chart.sheet)


def off(got, want):
    """dE00 of XYZ against a spectrum, through a flat grey stand-in (XYZ straight to Lab)."""
    from workflow.profile_engine.metrics import delta_e_2000
    w = np.array([96.42, 100.0, 82.49])

    def lab(xyz):
        r = np.asarray(xyz, float) / w
        f = np.where(r > 216 / 24389, np.cbrt(r), (24389 / 27 * r + 16) / 116)
        return np.array([[116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])]])
    return float(delta_e_2000(lab(got), lab(B.xyz_of(want)))[0])


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    return B.build_chart(tmp_path_factory.mktemp("bed"), count=48)


@pytest.mark.parametrize("opts", (STRIP, SPOT), ids=("strips", "patch by patch"))
def test_a_sheet_laid_right_reads_its_own_colours(tmp_path, opts):
    ch = B.build_chart(tmp_path, count=48)
    got = read_all(tmp_path, ch, B.Bed(ch.laid()), opts)
    truth = B.values_of(ch)
    assert set(got) == set(truth) and len(got) == 48
    assert max(off(got[k], truth[k]) for k in truth) < 0.6


def test_a_sheet_shifted_and_turned_is_followed_by_the_aims(tmp_path):
    """The person aims at the marks where they lie, so a sheet laid askew still reads right."""
    ch = B.build_chart(tmp_path, count=48)
    bed = B.Bed(ch.laid(), shift_mm=(-3.0, 4.0), turn_deg=0.8)
    got = read_all(tmp_path, ch, bed, STRIP)
    truth = B.values_of(ch)
    assert max(off(got[k], truth[k]) for k in truth) < 0.8


@pytest.mark.parametrize("opts", (STRIP, SPOT), ids=("strips", "patch by patch"))
def test_a_bed_one_pitch_off_reads_the_neighbour_patches(tmp_path, opts):
    """The aims at the nominal places, the sheet one patch (11 mm) further along: every patch is
    its left neighbour's colour (and the first one paper)."""
    ch = B.build_chart(tmp_path, count=48)
    aims = nominal_aims(ch)
    got = read_all(tmp_path, ch, B.Bed(ch.laid(), shift_mm=(11.0, 0.0)), opts, aims=aims, rows=1)
    truth = B.values_of(ch)
    for k in range(2, 25):
        assert off(got[f"A{k}"], truth[f"A{k - 1}"]) < 0.8, k
    assert off(got["A1"], [B.PAPER_R] * 36) < 0.8


def test_another_chart_reads_that_charts_colours(tmp_path):
    ch = B.build_chart(tmp_path, count=48)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(48, seed=99), seed=9)
    got = read_all(tmp_path, ch, B.Bed(other.laid()), STRIP, rows=1)
    theirs, mine = B.values_of(other), B.values_of(ch)
    assert max(off(got[k], theirs[k]) for k in got) < 0.6
    assert max(off(got[k], mine[k]) for k in got) > 20


def test_an_uncut_sheet_reads_the_second_piece_where_it_lies(tmp_path):
    """Two pieces on one sheet, laid uncut with the SECOND where the first belongs."""
    ch = B.build_chart(tmp_path, count=48)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(48, seed=99), seed=9)
    a, b = ch.laid(), other.laid()
    n = min(a.pixels.shape[0], b.pixels.shape[0])
    sheet = B.Laid(np.concatenate([a.pixels[:n], b.pixels[:n]], axis=1), a.w + b.w, a.h)
    # the sheet's corner lies one piece further back, so the second piece is under the arm
    bed = B.Bed(sheet, origin=(B.ORIGIN[0], B.ORIGIN[1] - 10.0 * a.w))
    got = read_all(tmp_path, ch, bed, STRIP, aims=nominal_aims(ch), rows=1)
    theirs = B.values_of(other)
    assert max(off(got[k], theirs[k]) for k in got) < 0.8
    # and the first piece now covers the table's white tile
    # (what is printed there, here made black, and never the tile)
    x, y = bed.page_of(1102, 32)
    assert 0 < x < a.w and 0 < y < a.h
    ix, iy = int(x * sheet.sx), int(y * sheet.sy)
    black = sheet.pixels.copy()
    black[iy - 30:iy + 30, ix - 30:ix + 30] = 0
    over = B.Bed(B.Laid(black, sheet.w, sheet.h), origin=bed.origin)
    assert over.true_spectrum(1102, 32) == pytest.approx([B.BLACK_R] * 36)
    nothing = B.Bed(a)                    # laid as a piece, the tile is bare
    assert nothing.true_spectrum(1102, 32) == [B.RS.REST_TILE] * 36


def test_the_readings_never_come_from_the_charts_file(tmp_path):
    """The .ti2's expected colours replaced by nonsense: the readings stay the sheet's."""
    ch = B.build_chart(tmp_path, count=48, xyz=lambda c: (50.0, 50.0, 50.0))
    got = read_all(tmp_path, ch, B.Bed(ch.laid()), STRIP, rows=1)
    truth = B.values_of(ch)
    assert max(off(got[k], truth[k]) for k in got) < 0.6


def test_the_opening_is_a_circle_of_45_mm(chart):
    """Half on black, half on paper: half the light; 1.5 mm into the black, the circle's part over
    the line (about 11 %), not none of it."""
    px = np.zeros((200, 400, 3), np.uint8)
    px[:, 200:] = 255
    laid = B.Laid(px, 40.0, 20.0)
    assert abs(float(laid.seen(20.0, 10.0)[0]) - 0.5) < 0.02
    assert float(laid.seen(17.7, 10.0)[0]) == 0.0
    assert float(laid.seen(22.3, 10.0)[0]) == 1.0
    r = B.APERTURE_MM / 2.0
    part = math.acos(1.5 / r) / math.pi - 1.5 * math.sqrt(r * r - 1.5 * 1.5) / (math.pi * r * r)
    assert 0.08 < part < 0.14
    assert abs(float(laid.seen(18.5, 10.0)[0]) - part) < 0.02
    assert abs(float(laid.seen(21.0, 10.0)[0]) - (1.0 - float(laid.seen(19.0, 10.0)[0]))) < 0.03
    assert 0.6 < float(laid.seen(21.0, 10.0)[0]) < 0.95


def test_a_turned_sheet_lies_turned(chart):
    """The sheet turned by 2 degrees clockwise as it lies: a point 100 mm from its middle moves by
    100 x sin 2 = 3.49 mm, and what is read there is what lies there."""
    laid = chart.laid()
    flat, bed = B.Bed(laid), B.Bed(laid, turn_deg=2.0)
    page = (laid.w / 2.0, laid.h / 2.0 - 100.0)           # 100 mm to the right as it lies
    (x0, y0), (x1, y1) = flat.table_of(page), bed.table_of(page)
    assert (y1 - y0) / 10.0 == pytest.approx(100 * math.sin(math.radians(2.0)), abs=0.01)
    assert (x1 - x0) / 10.0 == pytest.approx(100 * (1 - math.cos(math.radians(2.0))), abs=0.01)
    for q in ((20.0, 30.0), page, (laid.w - 12.0, laid.h - 40.0)):
        assert bed.page_of(*bed.table_of(q)) == pytest.approx(q, abs=1e-6)
        assert bed.true_spectrum(*bed.table_of(q)) == pytest.approx(
            flat.true_spectrum(*flat.table_of(q)), abs=1e-9)
    # nominal aims on a turned sheet do not read the sheet's own places
    far = (laid.w / 2.0, 30.0)
    assert bed.page_of(*flat.table_of(far)) != pytest.approx(far, abs=2.0)


def test_a_piece_cut_out_of_a_sheet_is_that_piece(tmp_path, chart):
    """Two pages side by side on one sheet, cut: each piece reads as the page it was."""
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(48, seed=99), seed=9)
    a, b = chart.laid(), other.laid()
    n = min(a.pixels.shape[0], b.pixels.shape[0])
    sheet = B.Laid(np.concatenate([a.pixels[:n], b.pixels[:n]], axis=1), a.w + b.w, a.h)
    one, two = sheet.cut(0.0, 0.0, a.w, a.h), sheet.cut(a.w, 0.0, a.w + b.w, b.h)
    assert (one.w, one.h, two.w) == (a.w, a.h, b.w)
    assert np.array_equal(one.pixels, a.pixels[:n]) and np.array_equal(two.pixels, b.pixels[:n])
    assert one.seen(a.w + 5.0, 50.0) is None            # nothing beside the piece
    got = read_all(tmp_path, chart, B.Bed(one), STRIP, aims=nominal_aims(chart), rows=1)
    truth = B.values_of(chart)
    assert max(off(got[k], truth[k]) for k in got) < 0.8
