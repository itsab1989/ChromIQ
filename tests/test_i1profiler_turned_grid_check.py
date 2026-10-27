"""The way back from the turned i1Profiler chart checks i1Profiler's GRID
(4.3.19, §I.14; Basti 2026-10-27: "if it is a bug fix it").

i1Profiler writes the device values of its ``.txf`` into every measurement,
so they repeat the patch list whatever grid it laid that list out on. If it
made one column more than the order file names (25 x R for a chart of R
strips of 24, the "rows merge" of a wrong device family), every row was read
on other physical patches, and the import used to call the file verified
(study 2026-10-27, ``prototype/way_back.py`` case B). An ``.mxf`` records the
grid (``NumberPatchColumns/Rows/Pages``) and every patch's Location, so the
import now compares those with the order and refuses a mismatch. Location is
a check only: pairing is still by order plus device values.

Also here: i1Profiler's fill rule itself (one grid, column-first, then the
rows shared out over pages), which ``write_pwxf(emit_locations=True)`` used to
get wrong for more than one page.
"""
from __future__ import annotations

import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                        # noqa: E402
from workflow.i1profiler_export import (                           # noqa: E402
    Target, WorkflowOptions, i1p_location, i1p_page_rows, write_pwxf)
from workflow.measurement_import import (assess,                   # noqa: E402
                                         complete_from_turned_order)
from workflow.reference_convert import (                           # noqa: E402
    I1P_GRID_KEYWORD, cxf_measurement_to_ti3, i1p_grid_of)

from tests.test_i1profiler_turned_export import _chart              # noqa: E402
from tests.test_i1profiler_turned_import import (                   # noqa: E402
    _spectrum, _xyz_by_sid)
from tests.test_i1profiler_turned_4317_files import (               # noqa: E402
    _write_as_4317)

_NS = "http://colorexchangeformat.com/CxF3-core"
_XRP = "http://www.xrite.com/products/prism"


def _rgbs(txf: Path) -> list:
    text = txf.read_text(encoding="utf-8")
    objs = re.findall(r'(<cc:Object ObjectType="Target".*?</cc:Object>)',
                      text, flags=re.S)
    return [tuple(int(v) for v in re.findall(r"<cc:[RGB]>(\d+)</cc:[RGB]>", o))
            for o in objs]


def _loc_xml(cell) -> str:
    if cell is None:
        return ""
    page, row, col = cell
    return ('<cc:TagCollection Name="Location">'
            f'<cc:Tag Name="Column" Value="{col}"/>'
            f'<cc:Tag Name="Page" Value="{page}"/>'
            f'<cc:Tag Name="Row" Value="{row}"/>'
            '<cc:Tag Name="SampleID" Value="-1"/>'
            '<cc:Tag Name="SampleName" Value=""/></cc:TagCollection>')


def _mxf(txf: Path, out: Path, *, columns: int, pages: int = 1,
         locations: "str" = "rule", swap: "tuple | None" = None,
         attributes: bool = True) -> Path:
    """An .mxf shaped like i1Profiler's own (X-Rite's RGB_default-i1Pro.mxf):
    Target objects in patch-list order with the device values of *txf*,
    M0/M1/M2 measurement objects index-aligned, and the CustomAttributes with
    the grid i1Profiler made: *columns* columns, its rows shared out over
    *pages* pages. *locations*: "rule" (the cell i1Profiler's fill rule
    gives), "none" (no Location tags). *swap* exchanges the Locations of two
    entries (the readings and device values stay where they are)."""
    rgb = _rgbs(txf)
    n = len(rgb)
    rows_total = -(-n // columns)
    per_page = i1p_page_rows(rows_total, pages)
    cells = [i1p_location(j, rows_total, per_page) for j in range(n)]
    if swap is not None:
        a, b = swap
        cells[a], cells[b] = cells[b], cells[a]
    if locations == "none":
        cells = [None] * n
    objs, k = [], 0
    for mode in ("M0", "M1", "M2"):
        for j, (r, g, b) in enumerate(rgb):
            k += 1
            sp = " ".join(str(v) for v in _spectrum(r, g, b))
            objs.append(
                f'<cc:Object ObjectType="{mode}_Measurement" '
                f'Name="{mode}_Measurement{j + 1}" Id="c{k}"><cc:ColorValues>'
                f'<cc:ReflectanceSpectrum StartWL="380">{sp}'
                f"</cc:ReflectanceSpectrum></cc:ColorValues>"
                f"{_loc_xml(cells[j])}</cc:Object>")
    for j, (r, g, b) in enumerate(rgb):
        k += 1
        objs.append(
            f'<cc:Object ObjectType="Target" Name="Target{j + 1}" Id="c{k}">'
            '<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="Unknown">'
            f"<cc:R>{r}</cc:R><cc:G>{g}</cc:G><cc:B>{b}</cc:B></cc:ColorRGB>"
            f"</cc:DeviceColorValues>{_loc_xml(cells[j])}</cc:Object>")
    attrs = ""
    if attributes:
        attrs = (f'<cc:CustomResources><xrp:Prism xmlns:xrp="{_XRP}" '
                 'release="2.0"><xrp:CustomAttributes MeasurementDevice='
                 f'"i1Pro 3" NumberPatchColumns="{columns}" '
                 f'NumberPatchPages="{pages}" NumberPatchRows="{per_page[0]}" '
                 f'numberCorePatches="{n}"/></xrp:Prism></cc:CustomResources>')
    out.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><cc:CxF xmlns:cc="{_NS}">'
        "<cc:Resources><cc:ObjectCollection>" + "".join(objs)
        + "</cc:ObjectCollection></cc:Resources>" + attrs + "</cc:CxF>",
        encoding="utf-8")
    return out


@pytest.fixture()
def turned_chart(tmp_path):
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    res = T.write_turned_export(ti2, exports_subdir(ti2.parent), "Proj")
    assert not res.skipped
    files = T.TurnedFiles(exports_subdir(ti2.parent), "Proj")
    return ti2, files, T.plan_for(ti2)


def _import(mxf: Path, ti2: Path):
    ti3 = cxf_measurement_to_ti3(mxf, mxf.with_suffix(".ti3"))
    return ti3, assess(ti3, ti2)


# ---- A: the grid the note names -----------------------------------------

def test_a_measured_on_the_planned_grid_imports_as_before(turned_chart,
                                                          tmp_path):
    ti2, files, plan = turned_chart
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "a.mxf", columns=plan.columns)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert g is not None and (g.columns, g.rows, g.pages) == (
        plan.columns, plan.rows, 1)
    assert g.located == g.patches == len(plan.order) and g.misplaced == 0
    assert v.ok and v.turned_order, v.reason
    # paired by the order, every reading on the patch the grid-less file of
    # the same readings puts it on
    plain = cxf_measurement_to_ti3(
        _mxf(files.txf("i1Pro 3"), tmp_path / "p.mxf", columns=plan.columns,
             locations="none", attributes=False), tmp_path / "p.ti3")
    assert i1p_grid_of(plain) is None
    assert complete_from_turned_order(ti3, ti2) == len(plan.order)
    assert complete_from_turned_order(plain, ti2) == len(plan.order)
    assert _xyz_by_sid(ti3) == _xyz_by_sid(plain)


# ---- B: one column more, the device values still agree ------------------

def test_b_one_column_more_is_refused_although_the_device_values_agree(
        turned_chart, tmp_path):
    ti2, files, plan = turned_chart
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "b.mxf",
               columns=plan.columns + 1)
    ti3, v = _import(mxf, ti2)
    # the device values alone would have said "verified": that is the bug
    from workflow.ti3_analysis import parse_ti3
    m = T.turned_match(parse_ti3(ti3), ti2)
    assert m.applies and m.verified and not m.partial
    assert not v.ok and not v.turned_order
    assert "laid that chart out on a different grid" in v.reason
    rows_b = -(-len(plan.order) // (plan.columns + 1))
    assert (f"columns: {plan.columns}, rows: {plan.rows}, pages: 1"
            in v.reason)
    assert (f"columns: {plan.columns + 1}, rows: {rows_b}, pages: 1"
            in v.reason)
    assert "step 5" in v.reason and ".mxf" in v.reason
    assert "—" not in v.reason
    # no door can pair it either: the copy is left exactly as it was
    copy = tmp_path / "copy.ti3"
    shutil.copy2(ti3, copy)
    before = copy.read_bytes()
    assert complete_from_turned_order(copy, ti2) == 0
    assert copy.read_bytes() == before


def test_patches_in_other_cells_of_the_right_grid_are_refused(turned_chart,
                                                              tmp_path):
    ti2, files, plan = turned_chart
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "s.mxf", columns=plan.columns,
               swap=(0, plan.rows))
    ti3, v = _import(mxf, ti2)
    assert i1p_grid_of(ti3).misplaced == 2
    assert not v.ok and not v.turned_order
    assert (f"does not give 2 of its {len(plan.order)} patches the place"
            in v.reason)
    assert complete_from_turned_order(ti3, ti2) == 0


# ---- grid attributes, no Locations --------------------------------------

def test_grid_attributes_without_locations_are_judged_by_the_grid(
        turned_chart, tmp_path):
    ti2, files, plan = turned_chart
    ok = _mxf(files.txf("i1Pro 3"), tmp_path / "ok.mxf", columns=plan.columns,
              locations="none")
    ti3, v = _import(ok, ti2)
    g = i1p_grid_of(ti3)
    assert g.located == 0 and g.misplaced == 0
    assert v.ok and v.turned_order, v.reason
    bad = _mxf(files.txf("i1Pro 3"), tmp_path / "bad.mxf",
               columns=plan.columns + 1, locations="none")
    _ti3, v = _import(bad, ti2)
    assert not v.ok and "different grid" in v.reason


# ---- the grid split over pages ------------------------------------------

def test_the_planned_grid_split_over_two_pages_is_refused(turned_chart,
                                                          tmp_path):
    """The .txf asks for ONE tall page. i1Profiler shares rows out over its
    pages (i1p_grid's model), which no longer matches ChromIQ's sheets; the
    file's own Locations follow that split and are read as such."""
    ti2, files, plan = turned_chart
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "two.mxf",
               columns=plan.columns, pages=2)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.pages, g.misplaced, g.located) == (2, 0, len(plan.order))
    assert g.rows == -(-plan.rows // 2)
    assert not v.ok and "pages: 2" in v.reason


# ---- review 4.3.19 r1, SF-1: only the PAGES differ ----------------------

@pytest.fixture()
def chart_360(tmp_path):
    """The reviewer's case: 360 patches, 15 strips of 24 (the order asks for
    24 x 15 on one page), which i1Profiler cut over 3 pages of 5 rows."""
    ti2 = _chart(tmp_path / "p360", "P360", 360)
    res = T.write_turned_export(ti2, exports_subdir(ti2.parent), "P360")
    assert not res.skipped
    plan = T.plan_for(ti2)
    assert (plan.columns, plan.rows) == (24, 15)
    return ti2, T.TurnedFiles(exports_subdir(ti2.parent), "P360"), plan


def test_360_patches_on_3_pages_is_refused_without_claiming_the_rows_missed(
        chart_360, tmp_path):
    ti2, files, plan = chart_360
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "three.mxf",
               columns=24, pages=3)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.columns, g.rows, g.pages) == (24, 5, 3)     # "rows: 5" = page 1
    assert not v.ok                     # still refused: step 5 says stop
    r = v.reason
    assert ("i1Profiler kept the 24 columns that the how-to note for this "
            "chart names, but it cut the chart over 3 pages") in r
    assert "columns: 24, rows: 15, pages: 1" in r            # the note's grid
    assert "columns: 24, pages: 3, rows on its first page: 5" in r
    assert "numbered its rows page by page" in r
    # Not the claim the review found false for this case:
    assert "did not line up with the strips" not in r
    assert "were taken on other patches" not in r
    assert "rows: 5" not in r
    assert r.endswith("import that file")


def test_other_columns_on_several_pages_name_the_first_pages_rows(chart_360,
                                                                   tmp_path):
    ti2, files, plan = chart_360
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "wide.mxf",
               columns=25, pages=3)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.columns, g.pages) == (25, 3)
    assert not v.ok
    assert (f"columns: 25, pages: 3, rows on its first page: {g.rows}"
            in v.reason)
    assert "did not line up with the strips" in v.reason
    assert "kept the" not in v.reason


def test_the_three_grid_reasons_are_chosen_by_columns_and_pages():
    from workflow import measurement_messages as M
    one = M.turned_grid_differs_reason(24, 15, 25, 15, 1)
    paged = M.turned_grid_differs_reason(24, 15, 25, 5, 3)
    pages = M.turned_grid_differs_reason(24, 15, 24, 5, 3)
    assert "columns: 25, rows: 15, pages: 1" in one
    assert "rows on its first page: 5" in paged
    assert "did not line up" in one and "did not line up" in paged
    assert "cut the chart over 3 pages" in pages
    assert "did not line up" not in pages
    for text in (one, paged, pages):
        assert "{" not in text and "—" not in text


# ---- a measurement of 4.3.17's anticlockwise .txf -------------------------

def test_a_4317_anticlockwise_order_is_checked_by_its_grid_too(tmp_path):
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    files = _write_as_4317(ti2, "Proj")
    order = T.turned_order_for(ti2)
    assert order.version == 1 and order.turn == T.ANTICLOCKWISE
    plan = T.plan_for(ti2, turn=T.ANTICLOCKWISE)
    assert (order.rows, order.columns) == (plan.rows, plan.columns)
    good = _mxf(files.txf("i1Pro 3"), tmp_path / "old.mxf",
                columns=plan.columns)
    _ti3, v = _import(good, ti2)
    assert v.ok and v.turned_order, v.reason
    bad = _mxf(files.txf("i1Pro 3"), tmp_path / "old_b.mxf",
               columns=plan.columns + 1)
    _ti3, v = _import(bad, ti2)
    assert not v.ok and "different grid" in v.reason


def test_an_earlier_order_kept_after_a_rewrite_shares_the_charts_grid(
        tmp_path):
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    files = _write_as_4317(ti2, "Proj")
    old_txf = tmp_path / "old.txf"
    shutil.copy2(files.txf("i1Pro 3"), old_txf)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "Proj")
    order = T.turned_order_for(ti2)
    assert order.turn == T.CLOCKWISE and order.earlier
    assert all((e.rows, e.columns) == (order.rows, order.columns)
               for e in order.earlier)
    plan = T.plan_for(ti2)
    _ti3, v = _import(_mxf(old_txf, tmp_path / "e.mxf",
                           columns=plan.columns), ti2)
    assert v.ok and v.turned_order, v.reason
    _ti3, v = _import(_mxf(old_txf, tmp_path / "e_b.mxf",
                           columns=plan.columns + 1), ti2)
    assert not v.ok and "different grid" in v.reason


# ---- files that are not turned measurements, or carry no grid -----------

def test_an_order_file_without_a_grid_is_judged_as_before(turned_chart,
                                                          tmp_path):
    import json
    ti2, files, plan = turned_chart
    doc = json.loads(files.order.read_text(encoding="utf-8"))
    doc.pop("rows")
    doc.pop("columns")
    files.order.write_text(json.dumps(doc), encoding="utf-8")
    _ti3, v = _import(_mxf(files.txf("i1Pro 3"), tmp_path / "x.mxf",
                           columns=plan.columns + 1), ti2)
    assert v.ok and v.turned_order, v.reason


def test_an_ordinary_measurement_with_a_grid_is_judged_as_before(tmp_path):
    """No turned order beside the chart: the grid is recorded in the
    converted file and changes nothing."""
    ti2 = _chart(tmp_path / "plain", "Plain", 350)
    plan = T.plan_for(ti2)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    txf = scratch / "plain.txf"
    T._write_txf(plan, "i1Pro 3", txf, "plain")
    # the same patches in the chart's own SAMPLE_ID order (an ordinary,
    # straight measurement), with a grid that is not the turned one
    text = txf.read_text(encoding="utf-8")
    objs = re.findall(r'(<cc:Object ObjectType="Target".*?</cc:Object>)',
                      text, flags=re.S)
    rank = sorted(range(len(plan.order)), key=lambda j: int(plan.order[j][0]))
    head = text[:text.index(objs[0])]
    rest = text[text.rindex(objs[-1]) + len(objs[-1]):]
    reordered = scratch / "reordered.txf"
    reordered.write_text(head + "".join(objs[j] for j in rank) + rest,
                         encoding="utf-8")
    assert T.turned_order_for(ti2) is None
    mxf = _mxf(reordered, tmp_path / "plain.mxf", columns=plan.columns + 3)
    ti3, v = _import(mxf, ti2)
    assert i1p_grid_of(ti3) is not None
    assert v.ok and not v.turned_order, v.reason


def test_a_cgats_export_carries_no_grid_and_pairs_as_before(turned_chart,
                                                            tmp_path):
    from tests.test_i1profiler_turned_import import (_i1p_cgats_export,
                                                     _txt2ti3_dir)
    from workflow.reference_convert import convert_i1profiler_measurement
    ti2, files, plan = turned_chart
    txt = _i1p_cgats_export(ti2, files, tmp_path / "turned.txt", rgb=True)
    ti3 = convert_i1profiler_measurement(txt, _txt2ti3_dir(), tmp_path / "c")
    assert i1p_grid_of(ti3) is None
    assert I1P_GRID_KEYWORD not in ti3.read_text(encoding="utf-8")
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order, v.reason


# ---- the message --------------------------------------------------------

def test_both_reasons_are_the_catalogues_and_end_with_the_way_out():
    from workflow import measurement_messages as M
    a = M.turned_grid_differs_reason(24, 21, 25, 21, 1)
    b = M.turned_grid_cells_differ_reason(24, 21, 3, 504)
    c = M.turned_grid_differs_reason(24, 21, 24, 7, 3)
    d = M.turned_grid_differs_reason(24, 21, 25, 7, 3)
    for text in (a, b, c, d):
        assert "{" not in text and "—" not in text
        assert text.startswith("this file is a measurement of the turned")
        assert text.endswith("import that file")
        assert "-i1profiler-turned-how-to.txt" in text
    assert not M.M_IMPORT_TURNED_GRID.approved
    for part in (M._TURNED_GRID_DIFFERS, M._TURNED_GRID_DIFFERS_PAGED,
                 M._TURNED_GRID_PAGES, M._TURNED_GRID_CELLS_DIFFER,
                 M._TURNED_GRID_WHAT_TO_DO):
        assert part in M.M_IMPORT_TURNED_GRID.body


# ---- i1Profiler's fill rule, and write_pwxf ------------------------------

def test_the_fill_rule_is_one_grid_column_first_then_pages():
    # 702 patches, 18 columns (pharmacist's 3-page file): 39 rows, 13 a page
    per = i1p_page_rows(39, 3)
    assert per == [13, 13, 13]
    assert i1p_location(0, 39, per) == (1, 0, 0)
    assert i1p_location(13, 39, per) == (2, 0, 0)     # page by page: (1, 0, 1)
    assert i1p_location(39, 39, per) == (1, 0, 1)
    assert i1p_location(701, 39, per) == (3, 12, 17)
    # 2033 in 30 columns (X-Rite's RGB_default-i1Pro.mxf): 68 rows, 23+23+22
    assert i1p_page_rows(68, 3) == [23, 23, 22]
    # rows the pages do not hold are an error, never a made-up cell
    with pytest.raises(ValueError):
        i1p_location(3, 4, [2, 1])


def _located_pwxf(path: Path) -> "list":
    root = ET.parse(path).getroot()
    out = []
    for o in root.iter(f"{{{_NS}}}Object"):
        tags = {t.get("Name"): t.get("Value")
                for tc in o.findall(f"{{{_NS}}}TagCollection")
                if tc.get("Name") == "Location"
                for t in tc.findall(f"{{{_NS}}}Tag")}
        out.append((int(tags["Page"]), int(tags["Row"]), int(tags["Column"]))
                   if "Page" in tags else None)
    return out


def test_write_pwxf_emits_the_cells_i1profiler_makes_on_three_pages(tmp_path):
    rows = [(i + 1, {"R": (i * 7) % 101, "G": (i * 3) % 101,
                     "B": (i * 11) % 101}) for i in range(702)]
    tgt = Target("iRGB", "RGB", ["R", "G", "B"], rows)
    out = tmp_path / "702.pwxf"
    write_pwxf(tgt, out, "t", WorkflowOptions(columns=18, rows=13, pages=3,
                                             emit_locations=True))
    got = _located_pwxf(out)
    per = i1p_page_rows(39, 3)
    assert got == [i1p_location(j, 39, per) for j in range(702)]
    # the converter reads its own fill rule back from it: nothing misplaced
    root = ET.parse(out).getroot()
    from workflow.reference_convert import _cxf_i1p_grid
    targets = list(root.iter(f"{{{_NS}}}Object"))
    g = _cxf_i1p_grid(root, targets)
    assert (g.columns, g.rows, g.pages, g.located, g.misplaced) == (
        18, 13, 3, 702, 0)


#: pharmacist's genuine i1Profiler 3.8.6 files and X-Rite's own .mxf, from
#: the 2026-10-27 study. Not in the repository (they are his files); these
#: tests run where they are on disk, and parse them only.
_STUDY = Path(os.environ.get(
    "CHROMIQ_PWXF_STUDY",
    str(Path.home() / "Desktop/ChromIQ-work/2026-10-27_pwxf_study")))
_GENUINE = sorted((_STUDY / "download").glob("zip*/*.pwxf")) + [
    p for p in [_STUDY / "xrite_samples" / "RGB_default-i1Pro.mxf"]
    if p.is_file()]


@pytest.mark.skipif(not _GENUINE, reason="the study's genuine files are not "
                    "on this machine")
@pytest.mark.parametrize("path", _GENUINE, ids=lambda p: p.name[:24])
def test_write_pwxf_puts_every_patch_where_i1profiler_put_it(path, tmp_path):
    root = ET.parse(path).getroot()
    attrs = next(el for el in root.iter()
                 if el.tag.endswith("}CustomAttributes")
                 and el.get("NumberPatchColumns"))
    targets = [o for o in root.iter(f"{{{_NS}}}Object")
               if o.get("ObjectType") in (None, "Target")
               and o.find(f".//{{{_NS}}}ColorRGB") is not None]
    rows = []
    for i, o in enumerate(targets):
        c = o.find(f".//{{{_NS}}}ColorRGB")
        rows.append((i + 1, {k: int(c.find(f"{{{_NS}}}{k}").text) / 2.55
                             for k in "RGB"}))
    genuine = []
    for o in targets:
        tags = {t.get("Name"): t.get("Value")
                for tc in o.findall(f"{{{_NS}}}TagCollection")
                if tc.get("Name") == "Location"
                for t in tc.findall(f"{{{_NS}}}Tag")}
        genuine.append((int(tags["Page"]), int(tags["Row"]),
                        int(tags["Column"])))
    out = tmp_path / "again.pwxf"
    write_pwxf(Target("iRGB", "RGB", ["R", "G", "B"], rows), out, "t",
               WorkflowOptions(columns=int(attrs.get("NumberPatchColumns")),
                               rows=int(attrs.get("NumberPatchRows")),
                               pages=int(attrs.get("NumberPatchPages")),
                               emit_locations=True))
    mine = _located_pwxf(out)
    same = sum(a == b for a, b in zip(mine, genuine))
    assert len(mine) == len(genuine) and same == len(genuine), (
        f"{same} of {len(genuine)} in i1Profiler's cell")
    # and the import's reading of it finds every patch where its grid says
    from workflow.reference_convert import _cxf_i1p_grid
    g = _cxf_i1p_grid(root, targets)
    assert g.located == len(targets) and g.misplaced == 0


# ---- through the real doors ---------------------------------------------

from tests.test_i1profiler_turned_doors import (                    # noqa: E402
    _answer, _project, house, turned_source)                       # noqa: F401


def _bad_grid_mxf(src_ti2: Path, out: Path) -> Path:
    files = T.TurnedFiles(exports_subdir(src_ti2.parent), src_ti2.stem)
    plan = T.plan_for(src_ti2)
    return _mxf(files.txf("i1Pro 3"), out, columns=plan.columns + 1)


def test_build_profile_refuses_a_turned_mxf_read_on_another_grid(
        house, monkeypatch):
    win, work, proj, run, outside, (src_ti2, _m, _t, _truth) = house
    seen = _answer(monkeypatch, run_id="run1")
    import ui.tabs.tab_profile as tp
    loose = _bad_grid_mxf(src_ti2, outside / "wrong-grid.mxf")
    before_bytes = loose.read_bytes()
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    monkeypatch.setattr(tp, "open_file_dialog", lambda *a, **k: str(loose))
    win._tab_profile._on_load_ti3()
    assert len(seen["refused"]) == 1, seen
    assert "laid that chart out on a different grid" in seen["refused"][0]
    after = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    assert after == before, "a run was left behind by a refused import"
    assert loose.read_bytes() == before_bytes


def test_the_measure_tab_refuses_a_turned_mxf_read_on_another_grid(
        qapp, tmp_path, turned_source, monkeypatch):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.measurement_target import RUN_TYPE_PROFILING
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure
    src_ti2, _mxf_ok, _t, _truth = turned_source
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    proj, run = _project(tmp_path, "M", src_ti2, with_measurement=True)
    fm = FileManager(s)
    fm.set_target_name("M")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    seen = _answer(monkeypatch, project="M")
    monkeypatch.setattr(tab, "_show_import_done_profiling", lambda *a: None)
    monkeypatch.setattr(tab, "_say_on_screen",
                        lambda t, b: seen["info"].append((t, b)))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda *a: None)
    loose = _bad_grid_mxf(src_ti2, tmp_path / "wrong-grid.mxf")
    before = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    measured_before = run.measurement_ti3.read_bytes()
    tab._import_into_profiling_run(ctl, fm.project().run("run1"), loose)
    said = seen["refused"] + [b for _t, b in seen["info"]]
    assert any("laid that chart out on a different grid" in x for x in said), seen
    after = {p.name for p in proj.runs_root.iterdir() if p.is_dir()}
    assert after == before
    assert run.measurement_ti3.read_bytes() == measured_before
