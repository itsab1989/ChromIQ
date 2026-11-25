"""Item 63: an i1iSis measurement of a chart laid out WITHOUT Randomise goes
through the same checks as one of a randomised chart (the i1iSis chart Beta).

i1Profiler copies the device values of its test chart into the measurement, so
with Randomise off (the order file is the chart's own numbering) the ordinary
check by SAMPLE_ID passes whatever was read, and the page, grid and colour
checks were never reached: a two-page measurement with the pages swapped or
page 1 twice, and a sheet fed half round or read one column off, were filed.

Charts are the app's own engine's; readings are synthetic (a printer that is
not targen's estimate, drift over the sheet, noise).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import i1p_forward as F          # noqa: E402


def _random(n, seed=3):
    r = np.random.default_rng(seed)
    return [tuple(r.uniform(0, 100, 3)) for _ in range(n)]


def _grid(k):
    v = np.linspace(0, 100, k)
    return [(r, g, b) for r in v for g in v for b in v]


def _ramps(k, chans):
    of = {"R": lambda x: (x, 0, 0), "G": lambda x: (0, x, 0),
          "B": lambda x: (0, 0, x), "K": lambda x: (x, x, x)}
    return [of[c](x) for c in chans for x in np.linspace(0, 100, k)]


def _light(rgbs):
    return sorted(rgbs, key=lambda v: .3 * v[0] + .59 * v[1] + .11 * v[2])


CHARTS = {
    "random900": _random(900), "random24": _random(24), "pages": _random(1100),
    "random60": _random(60), "sorted": _light(_random(528)),
    "grid9": _grid(9), "grid6": _grid(6), "cal": _ramps(32, "RGB"),
    "ramps": _ramps(24, "RGBK"), "grey": _ramps(100, "K"),
    "even": [(60.0, 60.0, 60.0)] * 400, "tiny": _random(10),
    "few": _random(18),
    "three": [(80, 80, 80), (40, 50, 60), (20, 20, 20)] * 40,
    "refine": _grid(3) + _random(150, 8),
}


class Chart:
    def __init__(self, folder, rgbs, randomize=False):
        from workflow.isis import export as X
        from workflow.layout_engine.chart import build_chart
        folder.mkdir(parents=True, exist_ok=True)
        ti1 = F.write_ti1(folder / "c.ti1", rgbs)
        build_chart(ti1, folder / "c", instrument="XRISIS", paper="A4",
                    dpi=72, seed=7, randomize=randomize)
        self.ti2 = folder / "c.ti2"
        self.rgbs = rgbs
        self.folder = folder
        res = X.write_isis_export(self.ti2, folder / "exports", "c")
        self.order_file = res.order
        doc = json.loads(res.order.read_text(encoding="utf-8"))
        self.ids = [int(e["sample_id"]) for e in doc["order"]]
        self.n, self.R, self.C = len(self.ids), doc["rows"], doc["columns"]
        self.P = doc["pages"]

    def cell(self, f):
        """p[j]: the entry whose patch is really read at entry j."""
        out = []
        for j in range(self.n):
            c, r = divmod(j, self.R)
            r2, c2 = f(r, c)
            k = c2 * self.R + r2
            ok = 0 <= r2 < self.R and 0 <= c2 < self.C and k < self.n
            out.append(k if ok else j)
        return out

    def ways(self):
        R, C, n = self.R, self.C, self.n
        w = {"half turn": self.cell(lambda r, c: (R - 1 - r, C - 1 - c)),
             "one column off": [(j + R) % n for j in range(n)],
             "one row off": self.cell(lambda r, c: ((r + 1) % R, c)),
             "mirrored": self.cell(lambda r, c: (r, C - 1 - c)),
             "backwards": list(range(n))[::-1],
             "another sheet": list(np.random.default_rng(4).permutation(n))}
        if n == R * C:
            w["rows and columns swapped"] = [
                (j % C) * R + j // C for j in range(n)]
        return w

    def measure(self, path, read_of=None, printer=None, seed=1, drift=2.0,
                ids=None, keep=None, header=""):
        rng = np.random.default_rng(seed)
        pr = F.InkPrinter(**F.PRINTERS[printer]) if printer else None
        if pr is None:
            clean = np.array([F.printer_lab(v, None, 0) for v in self.rgbs])
        else:
            clean = F._spectra_lab(np.array([pr.spectrum(v)
                                             for v in self.rgbs]))
        read_of = list(read_of) if read_of is not None else range(self.n)
        d = drift * np.outer(np.linspace(-.5, .5, self.n),
                             rng.normal(0, 1, 3) / 1.7)
        rows = []
        for j in range(self.n):
            if keep is not None and not keep(j):
                continue
            dev = self.rgbs[self.ids[j] - 1]
            lab = clean[self.ids[read_of[j]] - 1] + d[j] + rng.normal(0, .5, 3)
            x, y, z = F._lab_to_xyz_d50(lab)
            sid = ids(j) if ids else str(j + 1)
            rows.append(f'{sid} "{sid}" {dev[0]:.4f} {dev[1]:.4f} '
                        f'{dev[2]:.4f} {x:.4f} {y:.4f} {z:.4f}')
        path.write_text(
            'CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ"\n'
            'COLOR_REP "iRGB_XYZ"\n' + header +
            '\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC '
            'RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n'
            f'NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n' + "\n".join(rows)
            + "\nEND_DATA\n", encoding="utf-8")
        return path


@pytest.fixture(scope="module")
def beta():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


@pytest.fixture(scope="module")
def charts(beta, tmp_path_factory):
    root, made = tmp_path_factory.mktemp("isis-off"), {}

    def get(name, randomize=False) -> Chart:
        key = (name, randomize)
        if key not in made:
            made[key] = Chart(root / f"{name}-{randomize}", CHARTS[name],
                              randomize)
        return made[key]
    return get


def _assess(ti3, chart, **kw):
    from workflow.measurement_import import assess
    return assess(ti3, chart.ti2, **kw)


def test_the_charts_are_what_the_fault_needs(charts):
    """Randomise off: the order is the chart's own numbering. That is all
    Randomise decides about the import."""
    c = charts("pages")
    assert c.ids == list(range(1, 1101)) and c.P == 2
    assert charts("random900").P == 1
    r = charts("random60", True)
    assert r.ids != sorted(r.ids)


# ---- several pages ---------------------------------------------------------

@pytest.mark.parametrize("case", ["right", "swapped", "twice", "missing"])
def test_several_pages_are_refused_in_words(charts, tmp_path, case):
    c = charts("pages")
    k = c.R * c.C
    f = {"right": lambda j: j, "missing": lambda j: j,
         "swapped": lambda j: (j + k if j + k < c.n else j) if j < k
         else j - k,
         "twice": lambda j: j if j < k else j - k}[case]
    keep = (lambda j: j < k) if case == "missing" else None
    v = _assess(c.measure(tmp_path / "m.ti3", map(f, range(c.n)), keep=keep),
                c)
    assert not v.ok and "i1iSis chart with 2 pages" in v.reason, v.reason


# ---- one page, read wrongly --------------------------------------------------

@pytest.mark.parametrize("way", [
    "half turn", "one column off", "one row off", "mirrored", "backwards",
    "another sheet", "rows and columns swapped"])
@pytest.mark.parametrize("name", ["random60", "sorted", "grid6", "refine",
                                  "grid9"])
def test_a_sheet_read_the_wrong_way_is_refused(charts, tmp_path, name, way):
    from workflow import measurement_messages as MM
    c = charts(name)
    w = c.ways()
    if way not in w:
        pytest.skip("the grid is not full")
    for printer in (None, "low-gamut"):
        v = _assess(c.measure(tmp_path / "m.ti3", w[way], printer), c)
        assert not v.ok and v.reason == MM.isis_colours_reason(), (
            printer, v.isis_ask_why, v.reason)


def test_the_two_one_page_cases_of_the_study(charts, tmp_path):
    from workflow import measurement_messages as MM
    c = charts("random900")
    for way in ("half turn", "one column off"):
        v = _assess(c.measure(tmp_path / "m.ti3", c.ways()[way]), c)
        assert not v.ok and v.reason == MM.isis_colours_reason(), way


def test_one_row_read_one_column_off_is_refused(charts, tmp_path):
    """What the judge of randomised charts finds row by row."""
    from workflow import measurement_messages as MM
    c = charts("random900")
    p = c.cell(lambda r, k: (r, k + 1) if r == 5 else (r, k))
    v = _assess(c.measure(tmp_path / "m.ti3", p), c)
    assert not v.ok and v.reason == MM.isis_colours_reason()


@pytest.mark.parametrize("name", ["cal", "ramps", "grey", "even", "tiny",
                                  "few"])
def test_what_cannot_be_told_apart_is_never_filed_in_silence(
        charts, tmp_path, name):
    """Ramps, one colour, ten patches: some wrong readings look right. Every
    one of them is refused or asked about."""
    c = charts(name)
    seen = set()
    for way, p in c.ways().items():
        if [c.rgbs[c.ids[k] - 1] for k in p] == [
                c.rgbs[i - 1] for i in c.ids] and name != "even":
            continue                     # the same patches: nothing is wrong
        v = _assess(c.measure(tmp_path / "m.ti3", p), c)
        assert not v.ok or v.isis_ask_why, (way, "filed in silence")
        seen.add(v.ok)
    if name in ("even", "tiny", "few"):
        assert seen == {True}            # asked, never refused


# ---- never a right one ---------------------------------------------------------

PRINTERS = [None, *F.PRINTERS]


@pytest.mark.parametrize("name", [k for k in CHARTS if k != "pages"])
def test_a_right_measurement_is_never_refused(charts, tmp_path, name):
    c = charts(name)
    for i, printer in enumerate(PRINTERS if c.n < 600 else PRINTERS[::3]):
        for drift in (1.0, 3.0):
            v = _assess(c.measure(tmp_path / "m.ti3", None, printer, seed=i,
                                  drift=drift), c)
            assert v.ok, (printer, drift, v.reason)
            assert not v.turned_order and not v.partial


@pytest.mark.parametrize("name", ["random900", "random60", "sorted", "grid6",
                                  "refine"])
def test_a_right_measurement_that_can_be_checked_is_not_asked_about(
        charts, tmp_path, name):
    c = charts(name)
    for printer in (None, "matte", "glossy"):
        v = _assess(c.measure(tmp_path / "m.ti3", None, printer), c)
        assert v.ok and not v.isis_ask_why, (printer, v.isis_ask_why)


@pytest.mark.parametrize("white", [None, 8, 5])
def test_a_row_of_equal_patches_is_not_taken_for_a_slipped_row(
        charts, tmp_path, white):
    """A row that is white all along (or but for a few patches) fits its
    neighbours as well as itself: that says nothing about the sheet."""
    probe = charts("random60")
    rgbs = list(CHARTS["random900"][:560])
    from workflow.isis.chart import split
    C, R, P = split(560, 28, 36)
    assert (P, probe.P) == (1, 1)
    c0 = Chart(tmp_path / "a", rgbs)
    for j in range(560):
        col, row = divmod(j, c0.R)
        if row == 3 and (white is None or col >= white):
            rgbs[j] = (100.0, 100.0, 100.0)
    c = Chart(tmp_path / "b", rgbs)
    for seed, printer in enumerate(PRINTERS):
        v = _assess(c.measure(tmp_path / "m.ti3", None, printer, seed=seed),
                    c)
        assert v.ok, (printer, v.reason)
    for way in ("half turn", "one column off", "one row off"):
        assert not _assess(c.measure(tmp_path / "m.ti3", c.ways()[way]),
                           c).ok, way


# ---- the rest of the chain -------------------------------------------------------

def test_part_of_the_sheet_is_refused(charts, tmp_path):
    c = charts("random60")
    v = _assess(c.measure(tmp_path / "m.ti3", keep=lambda j: j < 30), c)
    assert not v.ok and "30 of the 60 patches" in v.reason
    assert "turned" not in v.reason
    # the same patch twice: the number of rows is right, the patches are not
    v = _assess(c.measure(tmp_path / "m.ti3",
                          ids=lambda j: "1" if j == 0 else "2" if j == 1
                          else str(j + 1) if j != 5 else "5"), c)
    assert not v.ok, "patch 5 twice, patch 6 missing"


def test_ids_that_are_not_i1profilers_numbers_are_judged_by_position(
        charts, tmp_path):
    from workflow import measurement_messages as MM
    c = charts("random60")
    ok = _assess(c.measure(tmp_path / "m.ti3", ids=lambda j: f"P{j + 1}"), c)
    assert ok.ok and not ok.isis_ask_why
    v = _assess(c.measure(tmp_path / "m.ti3", c.ways()["half turn"],
                          ids=lambda j: f"P{j + 1}"), c)
    assert not v.ok and v.reason == MM.isis_colours_reason()


def test_the_order_of_the_rows_in_the_file_does_not_matter(charts, tmp_path):
    c = charts("random60")
    p = c.measure(tmp_path / "m.ti3")
    lines = p.read_text(encoding="utf-8").splitlines()
    a, b = lines.index("BEGIN_DATA") + 1, lines.index("END_DATA")
    lines[a:b] = lines[a:b][::-1]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = _assess(p, c)
    assert v.ok and not v.isis_ask_why, v.reason
    g = charts("grid6")
    for way in ("one row off", "one column off"):
        p = g.measure(tmp_path / "g.ti3", g.ways()[way])
        lines = p.read_text(encoding="utf-8").splitlines()
        a, b = lines.index("BEGIN_DATA") + 1, lines.index("END_DATA")
        np.random.default_rng(6).shuffle(part := lines[a:b])
        lines[a:b] = part
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert not _assess(p, g).ok, way


def test_the_grid_i1profiler_records_is_checked(charts, tmp_path):
    from workflow.reference_convert import cxf_measurement_to_ti3
    c = charts("grid6")                     # its colours cannot clear a grid
    rng = np.random.default_rng(2)
    rd = [(j % c.R, j // c.R, F.printer_lab(c.rgbs[i - 1], rng, .5))
          for j, i in enumerate(c.ids)]
    cells = [(r, k) for r, k, _ in rd]
    good = F.write_cmxf(tmp_path / "g.mxf", rd, columns=c.C, rows=c.R,
                        pages_attr="0", target_cells=cells)
    cells[0], cells[7] = cells[7], cells[0]
    bad = F.write_cmxf(tmp_path / "b.mxf", rd, columns=c.C, rows=c.R,
                       pages_attr="0", target_cells=cells)
    other = F.write_cmxf(tmp_path / "o.mxf", rd, columns=c.C + 1, rows=c.R,
                         pages_attr="1", target_cells=None)
    assert cxf_measurement_to_ti3(good, tmp_path / "x.ti3")
    ti3 = c.measure(tmp_path / "m.ti3")
    assert _assess(ti3, c, source=good).ok
    v = _assess(ti3, c, source=bad)
    assert not v.ok and f"2 of its {c.n} patches" in v.reason, v.reason
    assert not _assess(ti3, c, source=other).ok


def test_without_the_order_file_the_side_file_is_enough(charts, tmp_path):
    from workflow import measurement_messages as MM
    from workflow.measurement_import import assess
    import shutil
    c = charts("random60")
    shutil.copytree(c.folder, tmp_path / "c")
    shutil.rmtree(tmp_path / "c" / "exports")
    ti2 = tmp_path / "c" / "c.ti2"
    assert assess(c.measure(tmp_path / "m.ti3"), ti2).ok
    v = assess(c.measure(tmp_path / "m.ti3", c.ways()["half turn"]), ti2)
    assert not v.ok and v.reason == MM.isis_colours_reason()
    (tmp_path / "c" / "c.isis.json").unlink()
    v = assess(c.measure(tmp_path / "m.ti3"), ti2)
    assert not v.ok and "c.isis.json" in v.reason, v.reason


def _order_doc(chart, tmp_path, change):
    """A copy of *chart* whose order file *change* has been at."""
    import shutil
    shutil.copytree(chart.folder, tmp_path / "copy")
    p = tmp_path / "copy" / "exports" / chart.order_file.name
    doc = json.loads(p.read_text(encoding="utf-8"))
    change(doc)
    p.write_text(json.dumps(doc), encoding="utf-8")
    return tmp_path / "copy" / "c.ti2"


@pytest.mark.parametrize("randomize", [False, True])
def test_an_order_file_cut_short_is_not_believed(charts, tmp_path, randomize):
    """Review 63, S1: 50 entries of 900, the chart's own checksum."""
    from workflow import measurement_messages as MM
    from workflow.i1profiler_turned import turned_order_for
    from workflow.measurement_import import (assess,
                                             complete_from_turned_order)
    c = charts("random900", randomize)

    def cut(doc):
        doc["order"] = doc["order"][:50]
    ti2 = _order_doc(c, tmp_path, cut)
    ti3 = c.measure(tmp_path / "m.ti3")
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order is randomize, v.reason
    assert len(turned_order_for(ti2).sample_ids) == 900
    if randomize:
        assert complete_from_turned_order(ti3, ti2) == 900
    v = assess(c.measure(tmp_path / "n.ti3", c.ways()["half turn"]), ti2)
    assert not v.ok and v.reason == MM.isis_colours_reason()
    (tmp_path / "copy" / "c.isis.json").unlink()      # nothing to go by now
    assert turned_order_for(ti2) is None
    v = assess(c.measure(tmp_path / "o.ti3"), ti2)
    assert not v.ok
    if not randomize:
        assert "c.isis.json" in v.reason


@pytest.mark.parametrize("randomize", [False, True])
@pytest.mark.parametrize("side", [True, False])
def test_an_order_file_with_the_wrong_page_count_is_not_believed(
        charts, tmp_path, randomize, side):
    from workflow.measurement_import import assess
    c = charts("pages", randomize)

    def one(doc):
        doc["pages"] = 1
    ti2 = _order_doc(c, tmp_path, one)
    if not side:
        (tmp_path / "copy" / "c.isis.json").unlink()
    v = assess(c.measure(tmp_path / "m.ti3"), ti2)
    assert not v.ok
    if side:
        assert "i1iSis chart with 2 pages" in v.reason, v.reason


def test_an_order_file_that_says_another_grid_or_kind_is_not_believed(
        charts, tmp_path):
    from workflow.i1profiler_turned import turned_order_for
    from workflow.measurement_import import _isis_order_for, assess
    c = charts("random60")

    def grid(doc):
        doc["rows"], doc["columns"] = 1, 60
    ti2 = _order_doc(c, tmp_path / "g", grid)
    assert (_isis_order_for(ti2).rows, turned_order_for(ti2).rows) == (
        c.R, c.R)

    def kind(doc):
        doc["kind"], doc["pages"] = "", 1
    p = charts("pages")
    ti2 = _order_doc(p, tmp_path / "k", kind)
    v = assess(p.measure(tmp_path / "m.ti3"), ti2)
    assert not v.ok and "i1iSis chart with 2 pages" in v.reason, v.reason


def test_several_pages_are_refused_without_the_order_file(charts, tmp_path):
    import shutil

    from workflow.measurement_import import assess
    c = charts("pages")
    shutil.copytree(c.folder, tmp_path / "c")
    shutil.rmtree(tmp_path / "c" / "exports")
    v = assess(c.measure(tmp_path / "m.ti3"), tmp_path / "c" / "c.ti2")
    assert not v.ok and "i1iSis chart with 2 pages" in v.reason, v.reason


def test_part_of_a_randomised_chart_says_so_truly(charts, tmp_path):
    c = charts("random60", True)
    v = _assess(c.measure(tmp_path / "m.ti3", keep=lambda j: j < 30), c)
    assert not v.ok and "30 of the 60 patches of this i1iSis" in v.reason
    assert "turned" not in v.reason


def test_readings_that_follow_the_chart_only_loosely_are_asked_about():
    """Fits no wrong way better, but the whole is between the two limits."""
    from workflow.isis import import_check as IC
    from workflow.turned_colour_check import expected_lab_rgb
    E = expected_lab_rgb(CHARTS["sorted"])
    M = E + np.random.default_rng(2).normal(0, E.std(axis=0) * 1.1, E.shape)
    v = IC.compare(E, M, 24, 22)
    assert (v.verdict, v.why) == (IC.CANNOT, "whole"), v


def test_a_filed_measurement_of_chartread_is_not_asked(charts, tmp_path):
    c = charts("even")
    p = c.measure(tmp_path / "m.ti3")
    p.write_text(p.read_text(encoding="utf-8").replace(
        'ORIGINATOR "ChromIQ"', 'ORIGINATOR "Argyll chartread"'),
        encoding="utf-8")
    v = _assess(p, c)
    assert v.ok and not v.isis_ask_why


def test_a_randomised_chart_is_judged_as_before(charts, tmp_path):
    """The other branch: paired through the order, refused the same way, and
    "cannot tell" still files without a question."""
    c = charts("random60", True)
    v = _assess(c.measure(tmp_path / "m.ti3"), c)
    assert v.ok and v.turned_order and not v.isis_ask_why
    v = _assess(c.measure(tmp_path / "m.ti3", c.ways()["half turn"]), c)
    assert not v.ok
    t = charts("tiny", True)
    v = _assess(t.measure(tmp_path / "m.ti3"), t)
    assert v.ok and not v.isis_ask_why
    # the same chart's readings already in the chart's own order: filed
    inv = {i: j for j, i in enumerate(c.ids)}
    p = c.measure(tmp_path / "m.ti3", ids=lambda j: str(c.ids[j]))
    assert inv and _assess(p, c).ok
    b = charts("pages", True)
    p = b.measure(tmp_path / "m.ti3", ids=lambda j: str(b.ids[j]))
    v = _assess(p, b)
    assert v.ok, v.reason                # as before: in the chart's own order
    assert not _assess(b.measure(tmp_path / "n.ti3"), b).ok


def test_beta_off_and_other_instruments_are_untouched(charts, tmp_path):
    from workflow.isis import support
    c = charts("random60")
    p = c.measure(tmp_path / "m.ti3", c.ways()["half turn"])
    support.set_enabled_for_this_process(False)
    try:
        assert _assess(p, c).ok            # 4.3.37's import, unchanged
    finally:
        support.set_enabled_for_this_process(True)
    other = tmp_path / "o.ti2"
    other.write_text(c.ti2.read_text(encoding="utf-8").replace(
        "X-Rite i1iSis", "X-Rite i1Pro"), encoding="utf-8")
    from workflow.measurement_import import assess
    assert assess(p, other).ok


def test_why_it_cannot_tell(charts, tmp_path):
    for name, why in (("few", "few"), ("even", "similar"),
                      ("three", "similar"), ("grey", "way")):
        c = charts(name)
        v = _assess(c.measure(tmp_path / "m.ti3"), c)
        assert v.ok and v.isis_ask_why == why, (name, v.isis_ask_why)


def test_a_ramp_read_backwards_cannot_be_explained_away():
    """L* may be any RISING function of the expected L*, never a falling
    one; a* and b* may not turn right round."""
    from workflow.isis.import_check import _misfit, _rising
    x = np.linspace(0, 100, 40)
    E = np.stack([x, 0 * x, 0 * x], 1)
    M = np.stack([14 + .8 * x ** 1.5 / 10, 0 * x, 0 * x], 1)
    assert _misfit(E, M) < 1e-6 < 10 < _misfit(E, M[::-1])
    A = np.stack([0 * x, x - 50, 0 * x], 1)
    assert _misfit(A, .7 * A) < 1e-6 < 10 < _misfit(A, -.7 * A)
    assert np.allclose(_rising(np.array([1., 1., 2.]), np.array([0., 4., 3.])),
                       [2, 2, 3])


@pytest.mark.parametrize("go", [True, False])
def test_the_question_at_the_filing_doors(qapp, monkeypatch, go):
    from PyQt6.QtWidgets import QMessageBox

    import ui.measurement_filing as MF
    from workflow.measurement_import import ImportVerdict
    said = []

    def ex(box):
        said.append((box.text(), box.informativeText(),
                     box.defaultButton().text()))
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda b: next(
            x for x in b.buttons()
            if (b.buttonRole(x) == QMessageBox.ButtonRole.AcceptRole) is go))
    monkeypatch.setattr(QMessageBox, "exec", ex)
    v = ImportVerdict(True, isis_ask_why="whole")
    assert MF.only_you_can_confirm_the_chart(None, v, None) is go
    assert "only loosely" in said[0][1] and "{" not in said[0][1]
    assert said[0][2].replace("&", "") == "Cancel"
    assert MF.only_you_can_confirm_the_chart(None, ImportVerdict(True), None)
    assert len(said) == 1


def test_every_door_asks():
    """Both Measure doors and both filing doors put the question before
    anything is filed."""
    import inspect

    import ui.measurement_filing as MF
    from ui.tabs.tab_measure import TabMeasure as T
    for fn in (T._import_into_verification, T._import_into_profiling_run):
        src = inspect.getsource(fn)
        assert src.index("_isis_import_confirmed(verdict)") < src.index(
            "complete_from_chart(")
    assert "isis_ask_why" in inspect.getsource(
        MF.only_you_can_confirm_the_chart)
    assert inspect.getsource(MF).count("only_you_can_confirm_the_chart(parent")


@pytest.mark.parametrize("go", [True, False])
def test_the_question_on_the_measure_tab(monkeypatch, go):
    from workflow.measurement_import import ImportVerdict
    from ui.tabs.tab_measure import TabMeasure as T
    said = []

    class Tab:
        class _log:
            appendPlainText = staticmethod(said.append)

        def _ask_import_question(self, message, label, **kw):
            said.append(message.render(**kw))
            return go
    v = ImportVerdict(True, isis_ask_why="way")
    assert T._isis_import_confirmed(Tab(), v) is go
    title, body = said[0]
    assert "neighbouring patches" in body and "{" not in body
    assert len(said) == (1 if go else 2)
    said.clear()
    assert T._isis_import_confirmed(Tab(), ImportVerdict(True)) and not said
