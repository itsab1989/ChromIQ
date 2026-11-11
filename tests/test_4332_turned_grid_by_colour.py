"""4.3.32, feature B (forum report 2026-11-10; Basti 2026-11-11 "do both"):
a measurement of the turned i1Profiler chart on ANOTHER GRID is judged by its
colours (`workflow/turned_colour_check.py`, option 2 of
``ChromIQ-work/2026-11-10_jctay/analysis.md``).

Pinned here, on real readings (`tests/data/turned_colour_check/`: the
tester's ColorChecker 24 and 624-patch measurements, each saved again on
other grids by i1Profiler, and 300 patches of a real PRO-300 set; plus the
suite's own ET-8550 verification reading):
* every one of the tester's re-saved files is cleared;
* every deliberately wrong version of every real file is refused: shifted by
  one patch either way and by one strip, turned half a turn, mirrored both
  ways, rows and columns swapped, each strip slipped by one patch on its own,
  and the readings the file's own grid would have given if the chart had
  really been measured on it;
* small charts, charts sorted by colour, charts of very similar colours and
  charts with few distinct colours cannot tell, whatever their readings;
* randomised charts of every size from the real sets: never a wrong version
  cleared, over several random layouts;
* the thresholds keep their evidence (a change to one is a decision).
End to end through the import: `tests/test_4329_jctay_comma_strips_grid.py`
and `tests/test_i1profiler_turned_grid_check.py`, and below for the CC24.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import turned_colour_check as C                      # noqa: E402

DATA = Path(__file__).parent / "data" / "turned_colour_check"


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _em(rgb, xyz):
    return C.expected_lab_rgb(rgb), C.measured_lab(xyz)


def _wrong_versions(n: int, rows: int, cols: int,
                    file_grids=()) -> "dict[str, np.ndarray]":
    """Entry j holds the reading of patch q[j]: every deliberately wrong
    arrangement the brief names, as full permutations."""
    idx = np.arange(n)
    r, c = idx % rows, idx // rows
    out = {"shifted +1": np.roll(idx, -1), "shifted -1": np.roll(idx, 1)}
    if n == rows * cols:
        out["shifted one strip"] = np.roll(idx, -rows)
        out["turned half a turn"] = (cols - 1 - c) * rows + (rows - 1 - r)
        out["mirrored along the strips"] = (cols - 1 - c) * rows + r
        out["mirrored across the strips"] = c * rows + (rows - 1 - r)
        out["rows and columns swapped"] = np.array(
            [(j % cols) * rows + (j // cols) for j in range(n)])
        strips = range(rows) if rows <= 12 else sorted(
            {0, 1, rows // 3, rows // 2, rows - 2, rows - 1})
        for s in strips:
            q = idx.copy()
            js = [k * rows + s for k in range(cols)]
            q[js] = np.roll(np.array(js), -1)
            out[f"strip {s + 1} slipped by one patch"] = q
    for fc, *_ in file_grids:
        for name, p in C._file_grid_arrangements(n, rows, cols, fc).items():
            if (p == idx).mean() < 0.5:
                out[f"measured on the file's grid ({name})"] = np.where(
                    p >= 0, p, np.roll(idx, 7))
    return out


# ---- the tester's files ----------------------------------------------------

@pytest.mark.parametrize("name", ["jctay_cc24.json", "jctay_624.json"])
def test_every_re_saved_file_of_the_tester_is_cleared(name):
    d = _load(name)
    E, M = _em(d["rgb"], d["xyz"])
    for cols, _rows, _pages in d["file_grids"]:
        j = C.judge(E, M, d["order_rows"], d["order_columns"], cols)
        assert j.agrees, (name, cols, j.log_text())
        assert j.score >= C.ACCEPT_FROM


@pytest.mark.parametrize("name", ["jctay_cc24.json", "jctay_624.json"])
def test_every_wrong_version_of_the_testers_files_is_refused(name):
    d = _load(name)
    E, M = _em(d["rgb"], d["xyz"])
    rows, cols = d["order_rows"], d["order_columns"]
    wrong = _wrong_versions(len(E), rows, cols, d["file_grids"])
    assert len(wrong) >= 10
    for what, q in wrong.items():
        for fc, *_ in d["file_grids"]:
            j = C.judge(E, M[q], rows, cols, fc)
            assert not j.agrees, (name, what, fc, j.log_text())


def test_a_slipped_strip_is_named_as_the_strip():
    d = _load("jctay_624.json")
    E, M = _em(d["rgb"], d["xyz"])
    rows, cols = d["order_rows"], d["order_columns"]
    q = np.arange(len(E))
    js = [k * rows + 20 for k in range(cols)]
    q[js] = np.roll(np.array(js), -1)
    j = C.judge(E, M[q], rows, cols, 4)
    assert j.verdict == C.DISAGREE and j.why == "strip-wrong" and j.strip == 20
    # the whole-chart score alone would have let it through
    assert j.score >= C.ACCEPT_FROM


# ---- the real measurement sets, randomised and sorted ---------------------

def _sets():
    from workflow.ti3_analysis import parse_ti3
    p = _load("pro300_300.json")
    et = parse_ti3(Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
                   / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")
    return {"PRO-300": _em(p["rgb"], p["xyz"]),
            "ET-8550": _em(np.asarray(et.rgb), np.asarray(et.xyz))}


SETS = None


def _set(name):
    global SETS
    if SETS is None:
        SETS = _sets()
    return SETS[name]


def _laid_out(E, M, rows, cols, order):
    """Patches *order* placed along the printed strips (strip by strip, patch
    by patch), as a chart laid out in that order would be."""
    seq = [c * rows + r for r in range(rows) for c in range(cols)]
    ent = np.empty(len(order), int)
    ent[seq] = order
    return E[ent], M[ent]


@pytest.mark.parametrize("set_name", ["PRO-300", "ET-8550"])
@pytest.mark.parametrize("size, cols", [(24, 6), (48, 8), (96, 12),
                                        (288, 12)])
def test_randomised_charts_never_clear_a_wrong_version(set_name, size, cols):
    E0, M0 = _set(set_name)
    rows = size // cols
    cleared = 0
    for seed in (1, 2, 3):
        pick = np.random.default_rng(seed).choice(len(E0), size,
                                                  replace=False)
        E, M = E0[pick], M0[pick]
        right = C.judge(E, M, rows, cols, cols + 1)
        assert right.verdict != C.DISAGREE, right.log_text()
        cleared += right.agrees
        for what, q in _wrong_versions(size, rows, cols,
                                       [(cols + 1,), (cols - 1,)]).items():
            j = C.judge(E, M[q], rows, cols, cols + 1)
            assert not j.agrees, (set_name, size, seed, what, j.log_text())
    if size >= 48:
        assert cleared >= 2, "right readings of a randomised chart are cleared"


def _nearest_chain(E):
    left = list(range(len(E)))
    cur = int(np.argmax(E[:, 0]))
    out = [cur]
    left.remove(cur)
    while left:
        d = np.linalg.norm(E[left] - E[cur], axis=1)
        cur = left[int(np.argmin(d))]
        out.append(cur)
        left.remove(cur)
    return np.array(out)


SORTS = {
    "by nearest colour": _nearest_chain,
    "by lightness": lambda E: np.lexsort((E[:, 2], E[:, 1], E[:, 0])),
    "by hue angle": lambda E: np.argsort(
        np.degrees(np.arctan2(E[:, 2], E[:, 1])) % 360, kind="mergesort"),
}


@pytest.mark.parametrize("sort", sorted(SORTS))
@pytest.mark.parametrize("size, cols", [(24, 6), (96, 12), (288, 12)])
def test_charts_sorted_by_colour_cannot_tell(sort, size, cols):
    E0, M0 = _set("PRO-300")
    rows = size // cols
    for seed in (1, 2):
        pick = np.random.default_rng(seed).choice(len(E0), size,
                                                  replace=False)
        E, M = _laid_out(E0[pick], M0[pick], rows, cols,
                         SORTS[sort](E0[pick]))
        right = C.judge(E, M, rows, cols, cols + 1)
        assert right.verdict == C.UNSURE and right.why == "neighbours", \
            (sort, size, seed, right.log_text())
        for what, q in _wrong_versions(size, rows, cols).items():
            assert not C.judge(E, M[q], rows, cols, cols + 1).agrees, what


# ---- charts that cannot tell, whatever their readings --------------------

def test_a_small_chart_cannot_tell():
    E0, M0 = _set("PRO-300")
    j = C.judge(E0[:16], M0[:16], 4, 4, 5)
    assert j.verdict == C.UNSURE and j.why == "few-patches"
    assert C.MIN_PATCHES == 20


def test_very_similar_colours_cannot_tell():
    """Forty greens a few ΔE apart: a reading one patch away would match."""
    rng = np.random.default_rng(4)
    rgb = np.column_stack([rng.uniform(20, 30, 40), rng.uniform(60, 75, 40),
                           rng.uniform(20, 30, 40)])
    E = C.expected_lab_rgb(rgb)
    j = C.judge(E, E + rng.normal(0, 0.5, E.shape), 5, 8, 9)
    assert j.verdict == C.UNSURE and j.why == "similar", j.log_text()


def test_few_distinct_colours_cannot_tell():
    """Six colours, each printed eight times."""
    E0, M0 = _set("PRO-300")
    six = np.repeat(np.arange(6), 8)
    np.random.default_rng(5).shuffle(six)
    j = C.judge(E0[six], M0[six], 6, 8, 9)
    assert j.verdict == C.UNSURE and j.why == "similar", j.log_text()


def test_a_grey_ramp_cannot_tell():
    g = np.linspace(0, 100, 48)
    E = C.expected_lab_rgb(np.column_stack([g, g, g]))
    j = C.judge(E, E, 6, 8, 9)
    assert j.verdict == C.UNSURE and j.why == "similar", j.log_text()


def test_short_strips_cannot_tell():
    E0, M0 = _set("PRO-300")
    j = C.judge(E0[:48], M0[:48], 24, 2, 3)
    assert j.verdict == C.UNSURE and j.why == "short-strips"


def test_no_expected_colours_cannot_tell():
    E0, M0 = _set("PRO-300")
    E = E0[:48].copy()
    E[3, 0] = np.nan
    assert C.judge(E, M0[:48], 6, 8, 9).why == "no-colours"


# ---- the thresholds and their evidence -----------------------------------

def test_the_thresholds_are_the_evidenced_ones():
    """A change to any of these is a decision: re-measure
    (`ChromIQ-work/2026-11-11_4332_features/tools/judge_eval.py`) and
    rewrite the evidence in `turned_colour_check`'s comments with it."""
    assert (C.ACCEPT_FROM, C.DISAGREE_BELOW, C.MIN_LEAD) == (0.75, 0.40, 0.30)
    assert (C.STRIP_CLEAR, C.STRIP_WRONG) == (0.50, 1.00)
    assert (C.MIN_NEIGHBOUR_RATIO, C.MIN_CHANNEL_NEIGHBOUR_RATIO) == (0.70,
                                                                      0.25)
    assert C.MAX_SELF_LIKENESS == 0.30
    assert (C.MIN_PATCHES, C.MIN_DISTINCT, C.MIN_STRIP_PATCHES) == (20, 16, 3)
    # the "cannot tell" band between a clear no and a clear yes is wide
    assert C.ACCEPT_FROM - C.DISAGREE_BELOW >= 0.3


def test_the_judgement_does_not_pair_anything():
    """The colours only decide; the readings stay in the order's pairing.
    The module offers no function that returns a pairing or a permutation
    to be applied."""
    import inspect
    names = [n for n, f in inspect.getmembers(C, inspect.isfunction)
             if f.__module__ == C.__name__]
    assert not [n for n in names if "pair" in n or "reorder" in n], names


# ---- end to end: the tester's CC24 through the real import -------------

@pytest.fixture(scope="module")
def cc24_chart(tmp_path_factory):
    """A ChromIQ chart of the CC24's device values, 4 strips of 6, whose
    turned order entry j carries the device value of the tester's entry j
    (the analysis's `repro24.py`, here from the fixture)."""
    from core.file_manager import exports_subdir
    from workflow import i1profiler_turned as T
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    d = _load("jctay_cc24.json")
    folder = tmp_path_factory.mktemp("cc24") / "CC24"
    folder.mkdir()
    rgb = d["rgb"]
    lines = ["CTI1", "", 'DESCRIPTOR "cc24"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rgb)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rgb, 1):
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f} 50 50 50")
    lines += ["END_DATA", ""]
    ti1 = folder / "CC24.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")
    res, used = build_from_recipe(ti1, folder / "CC24", LayoutRecipe(
        instrument="i1", layout_mode="patch_first", spacer_mode="none",
        seed=1001, patch_w_mm=12.0, patch_h_mm=16.0, max_strip_mm=97.0))
    strips = folder / "CC24.strips.json"
    lay = json.loads(strips.read_text(encoding="utf-8"))
    lay.update(engine="chromiq", engine_version=1, seed=res.seed,
               recipe=used.to_dict())
    (folder / "CC24.channels.json").write_text(json.dumps({"layout": lay}),
                                               encoding="utf-8")
    strips.unlink()
    ti2 = folder / "CC24.ti2"
    plan = T.plan_for(ti2)
    assert (plan.rows, plan.columns) == (4, 6)
    # entry j of the order gets the tester's entry j device value
    want = {sid: rgb[j] for j, (sid, _l, _v) in enumerate(plan.order)}
    text = ti2.read_text(encoding="utf-8").splitlines()
    fields, out, state = [], [], "head"
    for ln in text:
        s = ln.strip()
        if state == "head" and s == "BEGIN_DATA_FORMAT":
            state = "fmt"
        elif state == "fmt":
            if s == "END_DATA_FORMAT":
                state = "head2"
            else:
                fields += s.split()
        elif state == "head2" and s == "BEGIN_DATA":
            state = "data"
            out.append(ln)
            continue
        elif state == "data":
            if s == "END_DATA":
                state = "tail"
            else:
                parts = s.split()
                sid = parts[fields.index("SAMPLE_ID")]
                for ch, v in zip("RGB", want[sid]):
                    parts[fields.index(f"RGB_{ch}")] = f"{v:.6f}"
                ln = " ".join(parts)
        out.append(ln)
    ti2.write_text("\n".join(out) + "\n", encoding="utf-8")
    assert not T.write_turned_export(ti2, exports_subdir(folder), "CC24").skipped
    return ti2, d


def _ti3(path: Path, d: dict, q, grid) -> Path:
    cols, rows, pages = grid
    n = len(d["rgb"])
    lines = ["CTI3", "", 'DESCRIPTOR "Measurement data converted from '
             'i1Profiler CxF"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "CHROMIQ_I1P_GRID"',
             f'CHROMIQ_I1P_GRID "columns={cols} rows={rows} pages={pages} '
             f'patches={n} located={n} misplaced=0"',
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "iRGB_XYZ"', "",
             "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for j in range(n):
        r, g, b = d["rgb"][j]
        x, y, z = d["xyz"][int(q[j])]
        lines.append(f'{j + 1} "{j + 1}" {r:.4f} {g:.4f} {b:.4f} '
                     f"{x:.4f} {y:.4f} {z:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_the_cc24_through_the_import(cc24_chart, tmp_path, caplog):
    from workflow.i1profiler_turned import colour_check_fields
    from workflow.measurement_import import (assess,
                                             complete_from_turned_order)
    ti2, d = cc24_chart
    n = len(d["rgb"])
    for grid in d["file_grids"]:
        ti3 = _ti3(tmp_path / f"ok{grid[0]}.ti3", d, np.arange(n), grid)
        with caplog.at_level("INFO"):
            v = assess(ti3, ti2)
        assert v.ok and v.turned_order, (grid, v.reason)
        assert any("the colours of the turned measurement on another grid"
                   in r.getMessage() and "agree" in r.getMessage()
                   for r in caplog.records)
        assert complete_from_turned_order(ti3, ti2) == n
        assert colour_check_fields(ti3)["columns"] == str(grid[0])
    for what, q in _wrong_versions(n, 4, 6, d["file_grids"]).items():
        ti3 = _ti3(tmp_path / "bad.ti3", d, q, d["file_grids"][0])
        v = assess(ti3, ti2)
        assert not v.ok, what
        assert "So ChromIQ compared the colours" in v.reason, what
        before = ti3.read_bytes()
        assert complete_from_turned_order(ti3, ti2) == 0
        assert ti3.read_bytes() == before
