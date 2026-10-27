"""Review 4.3.18 r1 of the turned i1Profiler export: the order checked by
GEOMETRY, a reading followed to the patch it was physically read from, orders
that fit the same file in more than one way, and orders in both places a
chart's turned files may be.

* N-2: the order is checked against patch centres turned on the page and
  ranked, never against ``layout["strips"]``, which is what ``plan_for`` itself
  reads; and an import is checked against where each reading was PHYSICALLY
  taken (every patch of the printed sheet gives its own spectrum, keyed by its
  location), which a pairing that merely agrees on device values cannot fake.
* SF-1: a chart that repeats its colours can agree with two orders ChromIQ
  wrote for it on every patch (or with its own order and a turned one). The
  first match used to win and put every reading on the wrong patch; such a
  file is now refused, and nothing is filed. Orders that agree and put every
  reading on the SAME patch are one pairing, and still pair.
* N-1: an order beside the chart (the TI2 layout editor writes there) and one
  in ``exports/`` (Create Chart) are both orders ChromIQ wrote for the chart.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                        # noqa: E402
from workflow.measurement_import import (                          # noqa: E402
    assess, complete_from_turned_order, straight_or_turned_reason,
    turned_ambiguous_reason)
from workflow.reference_convert import cxf_measurement_to_ti3       # noqa: E402
from workflow.ti3_analysis import parse_ti3                         # noqa: E402

from tests.test_i1profiler_turned_export import _chart              # noqa: E402
from tests.test_i1profiler_turned_import import _NS, _mxf_from_txf  # noqa: E402
from tests.test_i1profiler_turned_4317_files import _write_as_4317  # noqa: E402


# ---------------------------------------------------------------------------
# Geometry, independent of plan_for
# ---------------------------------------------------------------------------

def _layout(ti2: Path) -> dict:
    return json.loads(ti2.with_name(f"{ti2.stem}.channels.json")
                      .read_text(encoding="utf-8"))["layout"]


def _physical_rows(ti2: Path, turn: str) -> "list[list[str]]":
    """The sheet's patches as i1Profiler rows, from the patch rectangles only:
    every centre turned a quarter turn on its page, rows ranked top to bottom
    (sheet 1 first), each row ranked left to right."""
    lay = _layout(ti2)
    pats = lay["patches"]
    W = max(p["x"] + p["w"] for p in pats) + 500      # any constant ranks
    H = max(p["y"] + p["h"] for p in pats) + 500
    turned = []
    for p in pats:
        cx, cy = p["x"] + p["w"] / 2.0, p["y"] + p["h"] / 2.0
        # clockwise: the left edge goes to the top, the top edge to the right
        nx, ny = (H - cy, cx) if turn == T.CLOCKWISE else (cy, W - cx)
        turned.append((p.get("page", 0), ny, nx, p["loc"]))
    keys = sorted({(pg, round(ny)) for pg, ny, _nx, _l in turned})
    rows: "list[list]" = [[] for _ in keys]
    for pg, ny, nx, loc in turned:
        rows[keys.index((pg, round(ny)))].append((nx, loc))
    return [[loc for _x, loc in sorted(r)] for r in rows]


def _physical_order(ti2: Path, turn: str) -> "list[str]":
    """Entry j of i1Profiler's list sits at column j // R, row j % R."""
    rows = _physical_rows(ti2, turn)
    R, C = len(rows), len(rows[0])
    assert all(len(r) == C for r in rows)
    return [rows[j % R][j // R] for j in range(R * C)]


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    d = tmp_path_factory.mktemp("geo")
    return {
        "a4": _chart(d / "a4", "A4", 350),
        "two": _chart(d / "two", "Two", 600),
        "clip_right": _chart(d / "cr", "Cr", 350, clip_side="right"),
        "no_clip": _chart(d / "nc", "Nc", 350, clip_border=False),
        "small_7": _chart(d / "s7", "S7", 300, paper="4x6", patch_w_mm=8.0,
                          patch_h_mm=7.0),
        "small_25": _chart(d / "s25", "S25", 120, paper="4x6",
                           patch_w_mm=8.0, patch_h_mm=25.0),
        "landscape": _chart(d / "ls", "Ls", 350, paper="A4R"),
    }


@pytest.mark.parametrize("key", ["a4", "two", "clip_right", "no_clip",
                                 "small_7", "small_25", "landscape"])
def test_the_order_is_the_turned_sheet_ranked_by_patch_centres(charts, key):
    """N-2: the order ``plan_for`` writes, for the turn it chooses AND for the
    other one, is exactly the patches of the turned sheet read row by row,
    found by turning every patch centre and ranking them: no use of
    ``layout["strips"]``, its order or its page grouping."""
    ti2 = charts[key]
    plan = T.plan_for(ti2)
    assert plan.qualifies, plan.reasons or plan.family_reasons
    for turn in (T.CLOCKWISE, T.ANTICLOCKWISE):
        p = T.plan_for(ti2, turn=turn)
        assert [loc for _s, loc, _v in p.order] == _physical_order(ti2, turn), \
            (key, turn)
    want = T.ANTICLOCKWISE if key == "clip_right" else T.CLOCKWISE
    assert plan.turn == want


# ---------------------------------------------------------------------------
# A reading followed to the patch it was physically read from
# ---------------------------------------------------------------------------

def _spectrum_of_place(k: int) -> list:
    """A reflectance only the patch at place *k* of the sheet gives."""
    a, b = k % 31, k // 31                  # distinct pair per place
    return [round(0.05 + 0.9 * (a / 30.0 if i < 18 else b / 40.0), 5)
            for i in range(36)]


def _mxf_read_on_the_sheet(txf: Path, out: Path, read_at: "list[str]",
                           place: dict) -> Path:
    """An i1Profiler measurement as a person makes it: entry j carries the
    .txf's own device values (i1Profiler writes them, whatever was read) and
    the spectrum of the patch the instrument was physically over,
    ``read_at[j]``."""
    text = txf.read_text(encoding="utf-8")
    objs = re.findall(r'(<cc:Object ObjectType="Target".*?</cc:Object>)',
                      text, flags=re.S)
    rgb = [tuple(int(v) for v in re.findall(r"<cc:[RGB]>(\d+)</cc:[RGB]>", o))
           for o in objs]
    assert len(rgb) == len(read_at)
    targets, meas = [], []
    for k, ((r, g, b), loc) in enumerate(zip(rgb, read_at), 1):
        targets.append(
            f'<cc:Object ObjectType="Target" Name="Target{k}" Id="c{k}">'
            f'<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="Unknown">'
            f"<cc:R>{r}</cc:R><cc:G>{g}</cc:G><cc:B>{b}</cc:B>"
            "</cc:ColorRGB></cc:DeviceColorValues></cc:Object>")
        sp = " ".join(str(v) for v in _spectrum_of_place(place[loc]))
        meas.append(
            f'<cc:Object ObjectType="M0_Measurement" Name="M0_Measurement{k}" '
            f'Id="m{k}"><cc:ColorValues><cc:ReflectanceSpectrum '
            f'StartWL="380">{sp}</cc:ReflectanceSpectrum></cc:ColorValues>'
            "</cc:Object>")
    out.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><cc:CxF xmlns:cc="{_NS}">'
        "<cc:Resources><cc:ObjectCollection>" + "".join(targets + meas)
        + "</cc:ObjectCollection></cc:Resources></cc:CxF>", encoding="utf-8")
    return out


def _xyz_by(ti3: Path, key: str) -> dict:
    d = parse_ti3(ti3)
    names = d.sample_locs if key == "loc" else d.sample_ids
    return {str(n).strip('"'): tuple(np.round(x, 3))
            for n, x in zip(names, d.xyz)}


@pytest.mark.parametrize("key", ["a4", "two", "clip_right", "small_25"])
def test_every_reading_lands_on_the_patch_it_was_read_from(charts, key,
                                                           tmp_path):
    """N-2: the sheet is laid down turned the way the note says and read row
    by row; each reading is the spectrum of the patch under the instrument.
    After the import every row of the filed copy must carry the spectrum of
    ITS OWN SAMPLE_LOC, which only holds if the pairing follows the paper."""
    src = charts[key]
    folder = tmp_path / key
    folder.mkdir()
    for p in src.parent.glob(f"{src.stem}*"):
        if p.is_file():
            (folder / p.name).write_bytes(p.read_bytes())
    ti2 = folder / src.name
    out = exports_subdir(folder)
    res = T.write_turned_export(ti2, out, src.stem)
    assert not res.skipped
    plan = T.plan_for(ti2)
    locs = sorted(p["loc"] for p in _layout(ti2)["patches"])
    place = {loc: k for k, loc in enumerate(locs)}
    read_at = _physical_order(ti2, plan.turn)          # what the paper gives
    txf = T.TurnedFiles(out, src.stem).txf("i1Pro 3")
    mxf = _mxf_read_on_the_sheet(txf, tmp_path / "m.mxf", read_at, place)
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "m.ti3")
    # what the instrument saw at each place, before any pairing: entry j
    # (i1Profiler's SAMPLE_ID j + 1) was read over the patch read_at[j]
    seen = _xyz_by(ti3, "id")
    at_place = {read_at[j]: seen[str(j + 1)] for j in range(len(read_at))}
    assert len(set(at_place.values())) == len(locs)      # all distinct
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, ti2) == len(locs)
    got = _xyz_by(ti3, "loc")
    assert set(got) == set(locs)
    wrong = [loc for loc in locs if got[loc] != at_place[loc]]
    assert not wrong, f"{len(wrong)} of {len(locs)} readings misplaced"
    # and the chart's own SAMPLE_ID goes with each SAMPLE_LOC
    d = parse_ti3(ti3)
    chart = {loc: sid for sid, loc, _v in plan.order}
    assert all(chart[str(l).strip('"')] == str(i).strip('"')
               for i, l in zip(d.sample_ids, d.sample_locs))


# ---------------------------------------------------------------------------
# SF-1: more than one order fits
# ---------------------------------------------------------------------------

def _recolour(ti2: Path, colour_of_loc: dict) -> None:
    """Give the chart's patches new device values, by location."""
    lines = ti2.read_text(encoding="utf-8").splitlines()
    out, data, fields = [], False, []
    for ln in lines:
        s = ln.strip()
        if s.startswith("SAMPLE_ID") and not fields:
            fields = s.split()
        if s == "BEGIN_DATA":
            data = True
            out.append(ln)
            continue
        if s == "END_DATA":
            data = False
        if data and s:
            parts = s.split()
            loc = parts[fields.index("SAMPLE_LOC")].strip('"')
            for c, v in zip("RGB", colour_of_loc[loc]):
                parts[fields.index(f"RGB_{c}")] = f"{v:.5f}"
            ln = " ".join(parts)
        out.append(ln)
    ti2.write_text("\n".join(out) + "\n", encoding="utf-8")


def _half_turn_symmetric_chart(folder: Path) -> Path:
    """A chart whose colours read the same in both quarter turns: every patch
    has the colour of the patch the other turn's order puts in its place
    (the sheet's colours are symmetric under half a turn). Its own order by
    SAMPLE_ID still differs from both turned ones."""
    ti2 = _chart(folder, "Sym", 350)
    cw = [loc for _s, loc, _v in T.plan_for(ti2, turn=T.CLOCKWISE).order]
    acw = [loc for _s, loc, _v in T.plan_for(ti2, turn=T.ANTICLOCKWISE).order]
    parent = {loc: loc for loc in cw}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b in zip(cw, acw):
        parent[root(a)] = root(b)
    classes = sorted({root(x) for x in cw})
    rnd = np.random.default_rng(7)
    colour = {c: tuple(rnd.uniform(0, 100, 3)) for c in classes}
    _recolour(ti2, {loc: colour[root(loc)] for loc in cw})
    return ti2


def test_two_orders_that_both_fit_and_disagree_are_refused(tmp_path):
    """SF-1. 4.3.17's anticlockwise order and 4.3.18's clockwise one both
    agree with a measurement of this chart on every patch, and would put the
    readings on different patches. Refused with its own reason, through the
    real import; nothing is filed. The reviewer's probe filed 96 of 96
    readings on the wrong patch."""
    ti2 = _half_turn_symmetric_chart(tmp_path / "proj")
    old = _write_as_4317(ti2, "Sym")
    old_txf = tmp_path / "old.txf"
    old_txf.write_bytes(old.txf("i1Pro 3").read_bytes())
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "Sym")
    order = T.turned_order_for(ti2)
    assert order.turn == T.CLOCKWISE and len(order.earlier) == 1
    for name, txf in (("old", old_txf), ("new", old.txf("i1Pro 3"))):
        mxf = _mxf_from_txf(txf, tmp_path / f"{name}.mxf")
        ti3 = cxf_measurement_to_ti3(mxf, tmp_path / f"{name}.ti3")
        m = T.turned_match(parse_ti3(ti3), ti2)
        assert m.applies and m.ambiguous and not m.verified, name
        assert len(m.fitting) == 2
        before = ti3.read_bytes()
        v = assess(ti3, ti2)
        assert not v.ok and not v.turned_order
        assert v.reason == turned_ambiguous_reason()
        assert complete_from_turned_order(ti3, ti2) == 0
        assert ti3.read_bytes() == before


def test_a_uniform_chart_read_on_the_turned_chart_is_not_filed_straight(
        tmp_path):
    """SF-1, the other half. Every patch the same colour (an evenness sheet):
    the file agrees with the chart by SAMPLE_ID AND with the turned order,
    and the two put the readings on different patches. It used to be filed
    by SAMPLE_ID, with every reading of the turned sheet on the wrong patch."""
    ti2 = _chart(tmp_path / "proj", "Even", 120)
    _recolour(ti2, {p["loc"]: (50.0, 50.0, 50.0)
                    for p in _layout(ti2)["patches"]})
    files = T.TurnedFiles(exports_subdir(ti2.parent), "Even")
    T.write_turned_export(ti2, files.folder, "Even")
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "m.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "m.ti3")
    v = assess(ti3, ti2)
    assert not v.ok and v.reason == straight_or_turned_reason()


def test_orders_that_fit_and_agree_are_one_pairing(tmp_path):
    """The same order in BOTH places (exports/ and beside the chart): two
    fitting orders, one pairing. It pairs as before."""
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    out = exports_subdir(ti2.parent)
    T.write_turned_export(ti2, out, "Proj")
    files = T.TurnedFiles(out, "Proj")
    beside = T.TurnedFiles(ti2.parent, "Proj")
    beside.order.write_bytes(files.order.read_bytes())
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "m.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "m.ti3")
    m = T.turned_match(parse_ti3(ti3), ti2)
    assert m.verified and not m.ambiguous
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order, v.reason


def test_an_ordinary_measurement_of_a_chart_with_a_turned_order_still_files(
        tmp_path):
    """Option-on chart, ordinary colours: a measurement in the chart's own
    order fits only by SAMPLE_ID and is filed exactly as before."""
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    files = T.TurnedFiles(exports_subdir(ti2.parent), "Proj")
    T.write_turned_export(ti2, files.folder, "Proj")
    sids = [sid for sid, _l, _v in T.plan_for(ti2).order]
    rank = sorted(range(len(sids)), key=lambda j: int(sids[j]))
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "m.mxf", rows=rank)
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "m.ti3")
    v = assess(ti3, ti2)
    assert v.ok and not v.turned_order, v.reason


# ---------------------------------------------------------------------------
# N-1: both places
# ---------------------------------------------------------------------------

def test_an_order_beside_the_chart_is_kept_and_read_with_the_one_in_exports(
        tmp_path):
    """4.3.17's order written BESIDE the chart (where the TI2 layout editor
    writes), the 4.3.18 export into exports/: the old order is kept as an
    earlier one, both are read, and a measurement from the old .txf pairs."""
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    old = _write_as_4317(ti2, "Proj")
    beside = T.TurnedFiles(ti2.parent, "Proj")
    for p in old.all():
        if p.is_file():
            (beside.folder / p.name).write_bytes(p.read_bytes())
            p.unlink()
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "Proj")
    doc = json.loads(T.TurnedFiles(exports_subdir(ti2.parent), "Proj").order
                     .read_text(encoding="utf-8"))
    assert [e["turn"] for e in doc["earlier_orders"]] == [T.ANTICLOCKWISE]
    assert doc["earlier_orders"][0]["version"] == 1
    order = T.turned_order_for(ti2)
    assert order.turn == T.CLOCKWISE
    assert [e.turn for e in order.earlier] == [T.ANTICLOCKWISE]
    mxf = _mxf_from_txf(beside.txf("i1Pro 3"), tmp_path / "old.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "old.ti3")
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order, v.reason


def test_turned_order_for_merges_both_places_without_repeats(tmp_path):
    """An order in exports/ and another beside the chart, for the same chart:
    one order in force (exports/), the other an earlier one, none twice."""
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    out = exports_subdir(ti2.parent)
    T.write_turned_export(ti2, out, "Proj")               # clockwise
    beside = T.TurnedFiles(ti2.parent, "Proj")
    plan = T.plan_for(ti2, turn=T.ANTICLOCKWISE)
    doc = T._order_doc(plan, ti2)
    beside.order.write_text(json.dumps(doc), encoding="utf-8")
    order = T.turned_order_for(ti2)
    assert order.path.parent == out and order.turn == T.CLOCKWISE
    assert [e.turn for e in order.earlier] == [T.ANTICLOCKWISE]
    # the same order in both places adds nothing
    beside.order.write_bytes(T.TurnedFiles(out, "Proj").order.read_bytes())
    assert T.turned_order_for(ti2).earlier == ()


# ---------------------------------------------------------------------------
# SF-4: the note says the files were written again
# ---------------------------------------------------------------------------

def test_the_note_says_when_the_files_were_written_again(tmp_path):
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    out = exports_subdir(ti2.parent)
    T.write_turned_export(ti2, out, "Proj")
    note = T.TurnedFiles(out, "Proj").note.read_text(encoding="utf-8")
    assert "written again" not in note
    _write_as_4317(ti2, "Proj")
    T.write_turned_export(ti2, out, "Proj")
    note = T.TurnedFiles(out, "Proj").note.read_text(encoding="utf-8")
    assert "written again" in note
    assert re.search(r"\bturn the sheet a quarter turn CLOCKWISE\b", note)
    assert "load the file from this folder again" in note
