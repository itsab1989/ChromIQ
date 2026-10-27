"""Review 4.3.18 r2 of the turned i1Profiler export.

* SF-B: the "fits straight and turned" refusal (r1, SF-1) also refused a
  genuine chartread measurement of a uniform chart that has turned files, and
  told the person, who HAD measured in ChromIQ, to measure in ChromIQ. A file
  that says it was read from the sheet as printed (ORIGINATOR "Argyll
  chartread", or ChromIQ's own turned-pairing keyword) is filed by SAMPLE_ID
  as before; anything else, including both ways an i1Profiler measurement
  arrives (converted from .mxf: "ChromIQ"; converted from CGATS .txt by
  txt2ti3: "Argyll txt2ti3"), is still asked and refused when it fits both.
* NIT5: a copy (Duplicate run, a new project from a chart folder) carried the
  order file of one place only, so an earlier order kept beside the original
  chart was lost: the copy paired and refused differently from the original.
* NIT4: the ambiguity refusal no longer says "the one beside it now".
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project, exports_subdir             # noqa: E402
from workflow import i1profiler_turned as T                       # noqa: E402
from workflow.measurement_import import (                         # noqa: E402
    assess, read_from_the_sheet_as_printed, straight_or_turned_reason,
    turned_ambiguous_reason)
from workflow.reference_convert import cxf_measurement_to_ti3      # noqa: E402

from tests.test_i1profiler_turned_export import _chart             # noqa: E402
from tests.test_i1profiler_turned_import import _mxf_from_txf      # noqa: E402
from tests.test_i1profiler_turned_review_4318 import (             # noqa: E402
    _half_turn_symmetric_chart, _layout, _recolour)


def _straight_ti3(ti2: Path, out: Path, originator: "str | None",
                  extra: "list[str] | None" = None) -> Path:
    """A measurement in the chart's own order, as chartread writes one: the
    .ti2's rows with XYZ added, under *originator*."""
    out_lines, fields, data = [], None, False
    for ln in ti2.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s.startswith("CTI2"):
            out_lines.append("CTI3")
            out_lines.extend(extra or [])
            continue
        if s.startswith("ORIGINATOR"):
            if originator is not None:
                out_lines.append(f'ORIGINATOR "{originator}"')
            continue
        if s.startswith("NUMBER_OF_FIELDS"):
            out_lines.append(f"NUMBER_OF_FIELDS {int(s.split()[1]) + 3}")
            continue
        if fields is None and s.startswith("SAMPLE_ID"):
            fields = s.split()
            out_lines.append(s + " XYZ_X XYZ_Y XYZ_Z")
            continue
        if s == "BEGIN_DATA":
            data = True
            out_lines.append(ln)
            continue
        if s == "END_DATA":
            data = False
        if data and s:
            out_lines.append(s + " 20.0 21.0 22.0")
            continue
        out_lines.append(ln)
    out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return out


@pytest.fixture()
def uniform(tmp_path):
    ti2 = _chart(tmp_path / "proj", "Even", 120)
    _recolour(ti2, {p["loc"]: (50.0, 50.0, 50.0)
                    for p in _layout(ti2)["patches"]})
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "Even")
    assert T.turned_order_for(ti2) is not None
    return ti2


# ---------------------------------------------------------------------------
# SF-B
# ---------------------------------------------------------------------------

def test_a_chartread_measurement_of_a_uniform_chart_is_filed(uniform,
                                                             tmp_path):
    ti3 = _straight_ti3(uniform, tmp_path / "cr.ti3", "Argyll chartread")
    assert read_from_the_sheet_as_printed(ti3)
    v = assess(ti3, uniform)
    assert v.ok and not v.turned_order, v.reason


def test_a_file_chromiq_already_paired_through_the_turned_order_is_filed(
        uniform, tmp_path):
    ti3 = _straight_ti3(uniform, tmp_path / "p.ti3", "ChromIQ", extra=[
        f'KEYWORD "{T.TURNED_KEYWORD}"', f'{T.TURNED_KEYWORD} "x.json"'])
    assert read_from_the_sheet_as_printed(ti3)
    assert assess(ti3, uniform).ok


@pytest.mark.parametrize("originator", ["ChromIQ", "Argyll txt2ti3",
                                        "X-Rite i1Profiler", None])
def test_a_file_that_cannot_say_where_it_was_read_is_still_refused(
        uniform, tmp_path, originator):
    """In doubt it is refused: the two ways an i1Profiler measurement
    arrives, a third-party originator, and none at all."""
    ti3 = _straight_ti3(uniform, tmp_path / "x.ti3", originator)
    assert not read_from_the_sheet_as_printed(ti3)
    v = assess(ti3, uniform)
    assert not v.ok and v.reason == straight_or_turned_reason()


def test_the_i1profiler_measurement_of_the_turned_chart_is_still_refused(
        uniform, tmp_path):
    files = T.TurnedFiles(exports_subdir(uniform.parent), "Even")
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "m.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "m.ti3")
    assert not read_from_the_sheet_as_printed(ti3)
    v = assess(ti3, uniform)
    assert not v.ok and v.reason == straight_or_turned_reason()


def test_an_unreadable_file_is_cannot_tell(tmp_path):
    assert not read_from_the_sheet_as_printed(tmp_path / "missing.ti3")


def test_the_refusal_says_a_chromiq_measurement_is_recognised():
    text = straight_or_turned_reason()
    assert "chartread" in text and "measure this sheet in ChromIQ" in text
    assert "—" not in text


def test_nit4_the_ambiguity_refusal_has_no_unclear_place():
    text = turned_ambiguous_reason()
    assert "beside it now" not in text
    assert "the one it wrote last" in text


# ---------------------------------------------------------------------------
# NIT5: a copy pairs and refuses exactly like the original
# ---------------------------------------------------------------------------

def _earlier_only_beside(ti2: Path, stem: str) -> None:
    """The clockwise export in exports/, then 4.3.17's anticlockwise order
    (version 1) beside the chart, written AFTER it, so the exports/ file does
    not hold it: only `turned_order_for`'s merge of both places knows it."""
    T.write_turned_export(ti2, exports_subdir(ti2.parent), stem)
    beside = T.TurnedFiles(ti2.parent, stem)
    plan = T.plan_for(ti2, turn=T.ANTICLOCKWISE)
    for fam in plan.families:
        T._write_txf(plan, fam, beside.txf(fam), f"{stem}-turned")
    doc = T._order_doc(plan, ti2)
    doc["version"] = 1
    doc.pop("turn")
    beside.order.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    exp = json.loads(T.TurnedFiles(exports_subdir(ti2.parent), stem)
                     .order.read_text(encoding="utf-8"))
    assert not exp.get("earlier_orders")
    order = T.turned_order_for(ti2)
    assert order.turn == T.CLOCKWISE and len(order.earlier) == 1


def _candidates(ti2: Path) -> list:
    o = T.turned_order_for(ti2)
    return [(c.turn, tuple(c.sample_ids)) for c in o.candidates()]


def _verdicts(ti2: Path, txfs: "list[Path]", tmp: Path) -> list:
    out = []
    for k, txf in enumerate(txfs):
        mxf = _mxf_from_txf(txf, tmp / f"v{k}.mxf")
        v = assess(cxf_measurement_to_ti3(mxf, tmp / f"v{k}.ti3"), ti2)
        out.append((v.ok, v.turned_order, v.reason))
    return out


def _txfs(ti2: Path, stem: str) -> "list[Path]":
    """The clockwise .txf and the 4.3.17 anticlockwise one, kept outside the
    project so both doors can be measured with them."""
    keep = ti2.parent.parent / "keep"
    keep.mkdir(exist_ok=True)
    out = []
    for name, files in (("cw", T.TurnedFiles(exports_subdir(ti2.parent),
                                             stem)),
                        ("acw", T.TurnedFiles(ti2.parent, stem))):
        dst = keep / f"{name}.txf"
        shutil.copy2(files.txf("i1Pro 3"), dst)
        out.append(dst)
    return out


def _source_run(tmp_path: Path, src_ti2: Path, symmetric: bool):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    for f in src_ti2.parent.iterdir():
        if f.is_file() and f.name.startswith(src_ti2.stem + "."):
            shutil.copy2(f, run.dir / (run.stem + f.name[len(src_ti2.stem):]))
    _earlier_only_beside(run.chart_ti2, run.stem)
    return proj, run


@pytest.mark.parametrize("symmetric", [False, True],
                         ids=["ordinary", "half-turn-symmetric"])
def test_a_duplicated_run_pairs_and_refuses_like_the_original(tmp_path,
                                                              symmetric):
    src = (_half_turn_symmetric_chart(tmp_path / "src") if symmetric
           else _chart(tmp_path / "src", "Sym", 350))
    proj, run = _source_run(tmp_path, src, symmetric)
    txfs = _txfs(run.chart_ti2, run.stem)
    before = _verdicts(run.chart_ti2, txfs, tmp_path)
    if symmetric:
        assert before == [(False, False, turned_ambiguous_reason())] * 2
    else:
        assert all(ok and turned for ok, turned, _r in before), before
    dup = proj.duplicate_run(run, ("chart",))
    assert _candidates(dup.chart_ti2) == _candidates(run.chart_ti2)
    assert _verdicts(dup.chart_ti2, txfs, tmp_path) == before


@pytest.mark.parametrize("symmetric", [False, True],
                         ids=["ordinary", "half-turn-symmetric"])
def test_a_new_project_from_a_chart_folder_pairs_like_the_original(
        tmp_path, symmetric):
    from ui.ti2_loader import _copy_files
    ti2 = (_half_turn_symmetric_chart(tmp_path / "loose") if symmetric
           else _chart(tmp_path / "loose", "Sym", 350))
    _earlier_only_beside(ti2, ti2.stem)
    txfs = _txfs(ti2, ti2.stem)
    before = _verdicts(ti2, txfs, tmp_path)
    new_ti2, _tiffs = _copy_files(ti2, ti2.with_suffix(".ti1"), [],
                                  tmp_path / "work", "Fresh")
    assert _candidates(new_ti2) == _candidates(ti2)
    assert _verdicts(new_ti2, txfs, tmp_path) == before
    # a version 1 earlier order is written into a version 2 file, turn named
    doc = json.loads(T.TurnedFiles(exports_subdir(new_ti2.parent), "Fresh")
                     .order.read_text(encoding="utf-8"))
    assert doc["version"] == T.ORDER_VERSION
    assert [e["turn"] for e in doc["earlier_orders"]] == [T.ANTICLOCKWISE]


def test_without_an_earlier_order_the_copy_is_the_file_itself(tmp_path):
    from ui.ti2_loader import _copy_files
    ti2 = _chart(tmp_path / "loose", "One", 350)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "One")
    src_order = T.TurnedFiles(exports_subdir(ti2.parent), "One").order
    new_ti2, _ = _copy_files(ti2, ti2.with_suffix(".ti1"), [],
                             tmp_path / "work", "Fresh")
    dst_order = T.TurnedFiles(exports_subdir(new_ti2.parent), "Fresh").order
    assert dst_order.read_bytes() == src_order.read_bytes()
