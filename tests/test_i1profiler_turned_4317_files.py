"""Turned i1Profiler files written by 4.3.17 (anticlockwise) after 4.3.18
turned the sheet the other way (Basti, 2026-10-27: the clip border belongs at
the top, so a left clip border means a clockwise quarter turn).

4.3.17's files are on users' disks: an order file of version 1, with no
``turn`` in it, beside the ``.txf`` the person may already have loaded in
i1Profiler. The rule these tests pin: such a measurement is never paired
wrongly, and it is paired correctly wherever ChromIQ still holds the order it
wrote for that exact chart, even after the files were written again for the
clockwise turn. A measurement whose device values follow no order ChromIQ
wrote for the chart is refused, as before.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                        # noqa: E402
from workflow.measurement_import import (assess,                   # noqa: E402
                                         complete_from_turned_order)
from workflow.reference_convert import cxf_measurement_to_ti3       # noqa: E402

from tests.test_i1profiler_turned_export import _chart              # noqa: E402
from tests.test_i1profiler_turned_import import (                   # noqa: E402
    _mxf_from_txf, _xyz_by_sid)


def _expected_xyz(ti2: Path, tmp: Path) -> dict:
    """What each CHART patch reads as: the same spectra written in the
    chart's own SAMPLE_ID order (the ordinary import), from a clockwise .txf
    written into a scratch folder of its own."""
    scratch = tmp / "expected"
    plan = T.plan_for(ti2, turn=T.CLOCKWISE)
    scratch.mkdir(exist_ok=True)
    txf = scratch / "cw.txf"
    T._write_txf(plan, "i1Pro 3", txf, "cw")
    sids = [sid for sid, _l, _v in plan.order]
    rank = sorted(range(len(sids)), key=lambda j: int(sids[j]))
    mxf = _mxf_from_txf(txf, scratch / "plain.mxf", rows=rank)
    return _xyz_by_sid(cxf_measurement_to_ti3(mxf, scratch / "plain.ti3"))


def _write_as_4317(ti2: Path, stem: str) -> T.TurnedFiles:
    """The export exactly as 4.3.17 left it: anticlockwise order and .txf,
    order file version 1 without a ``turn`` word."""
    out = exports_subdir(ti2.parent)
    out.mkdir(parents=True, exist_ok=True)
    files = T.TurnedFiles(out, stem)
    plan = T.plan_for(ti2, turn=T.ANTICLOCKWISE)
    for fam in plan.families:
        T._write_txf(plan, fam, files.txf(fam), f"{stem}-turned")
    doc = T._order_doc(plan, ti2)
    doc["version"] = 1
    doc.pop("turn")
    files.order.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return files


@pytest.fixture()
def chart(tmp_path):
    return _chart(tmp_path / "proj", "Proj", 350)


def _import(txf: Path, ti2: Path, tmp: Path, name: str):
    mxf = _mxf_from_txf(txf, tmp / f"{name}.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp / f"{name}.ti3")
    return ti3, assess(ti3, ti2)


def test_a_4317_order_file_is_read_and_pairs_exactly_as_before(chart, tmp_path):
    files = _write_as_4317(chart, "Proj")
    order = T.turned_order_for(chart)
    assert order is not None and order.turn == T.ANTICLOCKWISE
    ti3, v = _import(files.txf("i1Pro 3"), chart, tmp_path, "old")
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, chart) == 360
    assert _xyz_by_sid(ti3) == _expected_xyz(chart, tmp_path)


def test_writing_the_same_chart_again_keeps_4317s_order_as_an_earlier_one(
        chart, tmp_path):
    old = _write_as_4317(chart, "Proj")
    old_txf = tmp_path / "kept-by-i1profiler.txf"
    old_txf.write_bytes(old.txf("i1Pro 3").read_bytes())
    res = T.write_turned_export(chart, exports_subdir(chart.parent), "Proj")
    assert not res.skipped
    doc = json.loads(old.order.read_text(encoding="utf-8"))
    assert doc["version"] == 2 and doc["turn"] == T.CLOCKWISE
    assert [e["turn"] for e in doc["earlier_orders"]] == [T.ANTICLOCKWISE]
    order = T.turned_order_for(chart)
    assert order.turn == T.CLOCKWISE and len(order.earlier) == 1
    # a measurement made from the OLD .txf (say, the copy i1Profiler kept in
    # its assets folder) still lands on the right patches...
    ti3, v = _import(old_txf, chart, tmp_path, "old")
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, chart) == 360
    assert _xyz_by_sid(ti3) == _expected_xyz(chart, tmp_path)
    # ...and so does one from the new one
    ti3n, vn = _import(old.txf("i1Pro 3"), chart, tmp_path, "new")
    assert vn.ok and vn.turned_order, vn.reason
    assert complete_from_turned_order(ti3n, chart) == 360
    assert _xyz_by_sid(ti3n) == _expected_xyz(chart, tmp_path)


def test_writing_it_a_third_time_keeps_one_earlier_order_not_two(chart):
    _write_as_4317(chart, "Proj")
    out = exports_subdir(chart.parent)
    T.write_turned_export(chart, out, "Proj")
    T.write_turned_export(chart, out, "Proj")
    doc = json.loads(T.TurnedFiles(out, "Proj").order.read_text(encoding="utf-8"))
    assert len(doc["earlier_orders"]) == 1


def test_an_order_of_another_chart_is_not_kept(chart, tmp_path):
    """An earlier build of the same NAME is another sheet: its order goes."""
    other = _chart(tmp_path / "other", "Proj", 300)
    stale = _write_as_4317(other, "Proj")
    out = exports_subdir(chart.parent)
    for p in stale.all():
        if p.is_file():
            (out / p.name).parent.mkdir(parents=True, exist_ok=True)
            (out / p.name).write_bytes(p.read_bytes())
    T.write_turned_export(chart, out, "Proj")
    doc = json.loads(T.TurnedFiles(out, "Proj").order.read_text(encoding="utf-8"))
    assert "earlier_orders" not in doc


def test_a_file_that_follows_no_order_written_for_the_chart_is_refused(
        chart, tmp_path):
    """Device values in neither turn's order (two rows swapped in the file):
    refused with §I.5's sentence, as in 4.3.17."""
    old = _write_as_4317(chart, "Proj")
    T.write_turned_export(chart, exports_subdir(chart.parent), "Proj")
    plan = T.plan_for(chart)
    n, R = len(plan.order), plan.rows
    idx = list(range(n))
    for c in range(plan.columns):          # swap i1Profiler rows 1 and 2
        idx[c * R], idx[c * R + 1] = idx[c * R + 1], idx[c * R]
    mxf = _mxf_from_txf(old.txf("i1Pro 3"), tmp_path / "bad.mxf", rows=idx)
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "bad.ti3")
    v = assess(ti3, chart)
    assert not v.ok and not v.turned_order
    assert complete_from_turned_order(ti3, chart) == 0


def test_an_earlier_order_that_is_not_this_charts_patch_list_is_ignored(chart):
    _write_as_4317(chart, "Proj")
    out = exports_subdir(chart.parent)
    T.write_turned_export(chart, out, "Proj")
    path = T.TurnedFiles(out, "Proj").order
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["earlier_orders"][0]["order"] = doc["earlier_orders"][0]["order"][:-1]
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert T.turned_order_for(chart).earlier == ()
