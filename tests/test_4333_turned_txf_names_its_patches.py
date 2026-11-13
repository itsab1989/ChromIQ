"""The turned i1Profiler chart names its patches (4.3.33).

Forum, jctay, 2026-11-13: the turned ``.txf`` gave i1Profiler no patch names,
so tools that read i1Profiler's ``.mxf`` (ScanDeltaE, PatchTool) could show
only i1Profiler's grid cell (``P1R7C8``) where the sheet says ``7G``. Basti:
*"yes add the labels in 4.3.33"*.

Every Target of a turned ``.txf`` now carries a Location collection in
i1Profiler's own shape:

* ``SampleName`` = the chart's own name of that patch, as printed;
* ``SampleID`` = 1..N in list order, NOT the chart's SAMPLE_ID, because the
  turned pairing (``turned_match``) reads a measured SAMPLE_ID as the list
  position;
* ``Column`` / ``Row`` / ``Page`` = the cell i1Profiler itself gives that
  entry on one page (it ignores them on load and lays the chart out itself).

The import does not change: a measurement whose objects carry the names files
exactly as one without them. The plain patch sets and the Tools ``.pwxf``
stay without names, because there i1Profiler prints its own labels.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                        # noqa: E402
from workflow import i1profiler_turned as T                         # noqa: E402
from workflow.i1profiler_export import (                            # noqa: E402
    Target, WorkflowOptions, export_from_ti1, i1p_location, parse_ti1,
    write_pwxf)
from workflow.measurement_import import (assess,                    # noqa: E402
                                         complete_from_turned_order)
from workflow.reference_convert import cxf_measurement_to_ti3        # noqa: E402

from tests.test_4326_cxf_references_are_defined import (            # noqa: E402
    _assert_all_defined)
from tests.test_i1profiler_export import RGB_TI1, _write             # noqa: E402
from tests.test_i1profiler_turned_export import (                   # noqa: E402
    _chart, _geometry, _strips_of)
from tests.test_i1profiler_turned_grid_check import _mxf            # noqa: E402

CC = "{http://colorexchangeformat.com/CxF3-core}"
FIVE = ["Column", "Page", "Row", "SampleID", "SampleName"]


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    d = tmp_path_factory.mktemp("named")
    return {
        # left clip border (the default): turned CLOCKWISE; 350 patches at 24
        # per strip, so 10 fill-up patches
        "clockwise": _chart(d / "cw", "Cw", 350),
        # clip border on the right: turned ANTICLOCKWISE
        "anticlockwise": _chart(d / "ccw", "Ccw", 350, clip_side="right"),
        # the other label pattern, numbered strips with lettered places
        # ("1A", as on jctay's chart)
        "swapped": _chart(d / "sw", "Sw", 350,
                          strip_pattern="0-9,@-9,@-9;1-999",
                          patch_pattern="A-Z, A-Z"),
        # two sheets
        "two": _chart(d / "two", "Two", 600),
    }


def _written(ti2: Path) -> T.TurnedFiles:
    files = T.TurnedFiles(exports_subdir(ti2.parent), ti2.stem)
    if not files.txf("i1Pro 3").is_file():
        res = T.write_turned_export(ti2, exports_subdir(ti2.parent), ti2.stem)
        assert not res.skipped
    return files


def _locations(txf: Path) -> "list[list[tuple[str, str]]]":
    """Every Target's Location tags, in file order, as (name, value)."""
    root = ET.parse(txf).getroot()      # also proves the file is well-formed
    out = []
    for obj in root.iter(f"{CC}Object"):
        if obj.get("ObjectType") != "Target":
            continue
        cols = [tc for tc in obj.findall(f"{CC}TagCollection")
                if tc.get("Name") == "Location"]
        assert len(cols) == 1, f"{obj.get('Name')}: {len(cols)} Location"
        out.append([(t.get("Name"), t.get("Value"))
                    for t in cols[0].findall(f"{CC}Tag")])
    return out


def _printed_names(ti2: Path, turn: str, plan) -> "list[str]":
    """The name printed on the patch at each i1Profiler entry, worked out from
    the sheet's own geometry and NOT from the plan's order: entry j is row
    j % R, column j // R; clockwise, row r is the r-th strip from strip A and
    a row runs from the strip's last patch; anticlockwise, strips from the
    last and each strip from its label end."""
    strips, by_strip = _strips_of(_geometry(ti2))
    rows = []
    for pg in sorted({s["page"] for s in strips}):
        idx = [i for i, s in enumerate(strips) if s["page"] == pg]
        rows += idx if turn == T.CLOCKWISE else list(reversed(idx))
    names = []
    for j in range(plan.rows * plan.columns):
        c, r = divmod(j, plan.rows)
        strip = by_strip[rows[r]]
        place = plan.columns - 1 - c if turn == T.CLOCKWISE else c
        names.append(strip[place]["loc"])
    return names


def _ti2_locs(ti2: Path) -> "dict[str, str]":
    """SAMPLE_ID -> SAMPLE_LOC, straight from the chart file."""
    lines = ti2.read_text(encoding="utf-8").splitlines()
    body = lines[[ln.strip() for ln in lines].index("BEGIN_DATA") + 1:
                 [ln.strip() for ln in lines].index("END_DATA")]
    return {ln.split()[0]: ln.split()[1].strip('"')
            for ln in body if ln.strip()}


# ---------------------------------------------------------------------------

@pytest.mark.parametrize("family", ["i1Pro 2", "i1Pro 3"])
def test_every_patch_of_both_family_files_carries_the_five_tags(charts,
                                                                family):
    """i1Profiler's own shape: Column, Page, Row, SampleID, SampleName, in
    that order, Column/Row/Page the cell i1Profiler gives the entry on one
    page; the file stays a valid CxF that defines what it names."""
    ti2 = charts["clockwise"]
    plan = T.plan_for(ti2)
    txf = _written(ti2).txf(family)
    locs = _locations(txf)
    assert len(locs) == len(plan.order) == plan.rows * plan.columns
    for j, tags in enumerate(locs):
        assert [k for k, _v in tags] == FIVE, tags
        d = dict(tags)
        page, row, col = i1p_location(j, plan.rows, [plan.rows])
        assert (d["Column"], d["Page"], d["Row"]) == (str(col), "1",
                                                      str(row))
        assert d["SampleName"]
    _assert_all_defined(txf)


@pytest.mark.parametrize("key, turn", [
    ("clockwise", T.CLOCKWISE),
    ("anticlockwise", T.ANTICLOCKWISE),
    ("swapped", T.CLOCKWISE),
    ("two", T.CLOCKWISE),
])
def test_the_names_are_the_ones_printed_on_the_sheet(charts, key, turn):
    ti2 = charts[key]
    plan = T.plan_for(ti2)
    assert plan.turn == turn
    names = [dict(t)["SampleName"]
             for t in _locations(_written(ti2).txf("i1Pro 3"))]
    assert names == _printed_names(ti2, turn, plan)
    # every patch of the chart once, the fill-up patches among them
    ti2_locs = _ti2_locs(ti2)
    assert sorted(names) == sorted(ti2_locs.values())
    if key == "swapped":
        assert all(re.fullmatch(r"\d+[A-Z]+", n) for n in names), names[:5]
    else:
        assert all(re.fullmatch(r"[A-Z]+\d+", n) for n in names), names[:5]


def test_the_fill_up_patches_carry_their_own_names(charts):
    ti2 = charts["clockwise"]
    plan = T.plan_for(ti2)
    names = [dict(t)["SampleName"]
             for t in _locations(_written(ti2).txf("i1Pro 3"))]
    ti2_locs = _ti2_locs(ti2)
    fillers = [str(sid) for sid in range(351, 361)]
    assert len(plan.order) == 360
    for j, (sid, loc, _v) in enumerate(plan.order):
        if str(sid) in fillers:
            assert names[j] == loc == ti2_locs[str(sid)]
    assert sum(1 for sid, _l, _v in plan.order if str(sid) in fillers) == 10


@pytest.mark.parametrize("key", ["clockwise", "anticlockwise", "swapped"])
def test_the_ids_run_1_to_n_in_list_order_not_the_charts_own(charts, key):
    """``turned_match`` reads a measured SAMPLE_ID as the list position, so the
    id is the entry number, never the chart's SAMPLE_ID."""
    ti2 = charts[key]
    plan = T.plan_for(ti2)
    ids = [dict(t)["SampleID"]
           for t in _locations(_written(ti2).txf("i1Pro 3"))]
    assert ids == [str(j) for j in range(1, len(plan.order) + 1)]
    assert ids != [str(sid) for sid, _l, _v in plan.order]


def _with_names(mxf: Path, names: "list[str]", out: Path) -> Path:
    """The same .mxf with every object's SampleID/SampleName filled in, as
    i1Profiler writes them when the .txf named its patches."""
    def fill(m: "re.Match") -> str:
        obj = m.group(0)
        j = int(re.search(r'Name="(?:Target|M\d_Measurement)(\d+)"',
                          obj).group(1))
        obj = obj.replace('<cc:Tag Name="SampleID" Value="-1"/>',
                          f'<cc:Tag Name="SampleID" Value="{j}"/>')
        return obj.replace('<cc:Tag Name="SampleName" Value=""/>',
                           f'<cc:Tag Name="SampleName" '
                           f'Value="{names[j - 1]}"/>')
    text = mxf.read_text(encoding="utf-8")
    named = re.sub(r"<cc:Object .*?</cc:Object>", fill, text, flags=re.S)
    assert named.count('Value="-1"') == 0 and named != text
    out.write_text(named, encoding="utf-8")
    return out


def _filed(mxf: Path, ti2: Path) -> str:
    ti3 = cxf_measurement_to_ti3(mxf, mxf.with_suffix(".ti3"))
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, ti2) == len(T.plan_for(ti2).order)
    lines = ti3.read_text(encoding="utf-8").splitlines()
    # the date the file was written is the only thing allowed to differ
    return "\n".join(ln for ln in lines if not ln.startswith("CREATED"))


@pytest.mark.parametrize("pages", [1, 3])
def test_a_measurement_carrying_the_names_files_exactly_as_one_without(
        charts, tmp_path, pages):
    ti2 = charts["clockwise"]
    plan = T.plan_for(ti2)
    txf = _written(ti2).txf("i1Pro 3")
    names = [dict(t)["SampleName"] for t in _locations(txf)]
    plain = _mxf(txf, tmp_path / "plain.mxf", columns=plan.columns,
                 pages=pages)
    named = _with_names(plain, names, tmp_path / "named.mxf")
    assert _filed(named, ti2) == _filed(plain, ti2)


def test_the_plain_exports_and_the_tools_pwxf_stay_without_names(tmp_path):
    """There i1Profiler prints its own chart with its own labels, so ChromIQ's
    names would be wrong names: no Location at all, as before."""
    ti1 = _write(tmp_path, "rgb.ti1", RGB_TI1)
    txt, pxf = export_from_ti1(ti1, tmp_path)
    for f in (txt, pxf):
        assert "SampleName" not in f.read_text(encoding="utf-8")
    pwxf = tmp_path / "tools.pwxf"
    write_pwxf(parse_ti1(ti1), pwxf, "tools", WorkflowOptions())
    assert "TagCollection" not in pwxf.read_text(encoding="utf-8")
    # asked for cells without names, the probe scripts' way: i1Profiler's own
    # "no name" values, exactly as before
    probe = tmp_path / "probe.pwxf"
    write_pwxf(parse_ti1(ti1), probe, "probe",
               WorkflowOptions(columns=4, emit_locations=True))
    assert {dict(t)["SampleID"] for t in _locations(probe)} == {"-1"}
    assert {dict(t)["SampleName"] for t in _locations(probe)} == {""}


def test_a_name_is_escaped_and_the_count_must_match(tmp_path):
    rows = [(i, {"R": 10.0 * i, "G": 0.0, "B": 0.0}) for i in range(1, 4)]
    tgt = Target("iRGB", "RGB", ["R", "G", "B"], rows)
    out = tmp_path / "esc.txf"
    write_pwxf(tgt, out, "t", WorkflowOptions(columns=3, pages=1),
               sample_names=['A&1', 'B"2', "C<3"])
    assert [dict(t)["SampleName"] for t in _locations(out)] == [
        'A&1', 'B"2', "C<3"]
    with pytest.raises(ValueError):
        write_pwxf(tgt, out, "t", WorkflowOptions(columns=3),
                   sample_names=["A1"])
