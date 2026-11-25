"""WHERE A STORED CHART MAY SEND THE ARM (safety review of the new i1iO chart layout, 25 Nov 2026):
B2, a page whose run ends more than 20 mm beyond its corner patches keeps its crosses; S3, START
refuses a chart file with a place off its page or a page larger than the table, also a chart of one
piece, and takes every chart ChromIQ stored."""
from __future__ import annotations

import json

import pytest

from workflow import measurement_messages as M
from workflow.i1io import chart as C
from workflow.i1io import pieces as P


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(folder, n=300, **kw):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    k = {"instrument": "IO2", "paper": "A4", "dpi": 60, "seed": 1, "chart_date": "x",
         "i1io_limits": 2}
    k.update(kw)
    r = chart.build_chart(_ti1(folder / "c.ti1", n), folder / "c", **k)
    side = folder / "c.i1io.json"
    return r, side, json.loads(side.read_text(encoding="utf-8"))


def _beyond(page):
    ys = [a["page_mm"][1] for a in page["aim_points"]]
    return max(max(min(ys) - st["run_mm"][0], st["run_mm"][1] - max(ys))
               for st in page["strips"])


@pytest.mark.parametrize("along,kept", [(10.0, False), (20.0, False), (20.1, True), (30.0, True),
                                        (60.0, True)])
def test_long_patches_keep_the_crosses_and_it_is_said(tmp_path, along, kept):
    n = {10.0: 528, 60.0: 60}.get(along, 400)
    r, side, doc = _build(tmp_path, n, patch_h=along, i1io_crosses=False)
    full = doc["pages"][0]
    assert full["aim"] == ("crosses" if kept else "corner patches")
    assert (M._I1IO_LONG_KEEPS_CROSSES in r.notes) == kept
    assert M._I1IO_LONG_KEEPS_CROSSES not in r.warnings
    for page in doc["pages"]:
        if page["aim"] != "crosses":
            assert _beyond(page) <= 20.0 + 1e-6
    P.check_places(tmp_path / "c.ti2")
    _s, notes = C.preview_checks({
        "instrument": "IO2", "paper": "A4", "dpi": 60, "patch_h": along, "i1io_limits": 2,
        "i1io_crosses": False, "area_target_count": n})
    assert (M._I1IO_LONG_KEEPS_CROSSES in notes) == kept


def test_long_patches_without_room_for_crosses_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "crosses_fit", lambda *a, **k: False)
    with pytest.raises(C.I1ioSheetRefused) as e:
        _build(tmp_path, 100, patch_h=30.0, i1io_crosses=False)
    assert "more than 20 mm past the patches you aim at" in str(e.value)


def _bad(doc, how):
    page = doc["pages"][0]
    if how == "patches 100 mm off":
        for st in page["strips"]:
            for q in st["patches"]:
                q["centre_mm"][1] -= 300
    elif how == "one patch off":
        page["strips"][-1]["patches"][-1]["centre_mm"][0] = doc["paper_mm"][0] + 1.0
    elif how == "a run end off":
        page["strips"][0]["run_mm"][0] = -1.0
    elif how == "a run off across":
        page["strips"][0]["x_mm"] = -3.0
    elif how == "an aim off":
        page["aim_points"][2]["page_mm"][1] = doc["paper_mm"][1] + 2.0
    elif how == "an aim nan":
        page["aim_points"][1]["page_mm"][0] = float("nan")
    elif how == "a page too long":
        doc["paper_mm"][1] = 321.0
    elif how == "a page too wide":
        doc["paper_mm"][0] = 231.0
    elif how == "a page of nan":
        doc["paper_mm"][0] = float("nan")
    elif how == "no page size":
        del doc["paper_mm"]
    elif how == "text":
        page["strips"][0]["patches"][0]["centre_mm"] = ["a", "b"]
    elif how == "a strip without its run":
        del page["strips"][3]["run_mm"]
    elif how == "no pages":
        doc["pages"] = None
    elif how == "corner patches inside":
        for a in page["aim_points"]:
            a["page_mm"][1] = min(max(a["page_mm"][1], 60.0), 240.0)
    return doc


HOW = ["patches 100 mm off", "one patch off", "a run end off", "a run off across", "an aim off",
       "an aim nan", "a page too long", "a page too wide", "a page of nan", "no page size", "text",
       "no pages", "corner patches inside", "a strip without its run"]


@pytest.mark.parametrize("how", HOW)
def test_a_place_off_the_page_is_refused(tmp_path, how):
    _r, side, doc = _build(tmp_path, 500, i1io_crosses=False)
    ti2 = tmp_path / "c.ti2"
    P.check_places(ti2)
    side.write_text(json.dumps(_bad(doc, how)), encoding="utf-8")
    with pytest.raises(P.PieceRecordError):
        P.check_places(ti2)


def test_rounding_and_charts_without_places_are_taken(tmp_path):
    _r, side, doc = _build(tmp_path, 500)
    doc["pages"][0]["strips"][0]["run_mm"][0] = -0.4
    doc["paper_mm"][1] += 0.3
    side.write_text(json.dumps(doc), encoding="utf-8")
    P.check_places(tmp_path / "c.ti2")
    doc["pages"][0].pop("aim_points")         # (the job has words of its own for that)
    side.write_text(json.dumps(doc), encoding="utf-8")
    P.check_places(tmp_path / "c.ti2")
    side.unlink()
    P.check_places(tmp_path / "c.ti2")


@pytest.mark.parametrize("kw", [
    {}, {"paper": "Letter"}, {"paper": "230x320"}, {"paper": "60x297"}, {"paper": "4x6"},
    {"paper": "127x178"}, {"paper": "A3"}, {"paper": "A2"}, {"paper": "329x483"},
    {"patch_w": 5.5, "patch_h": 5.5}, {"patch_w": 8.0, "patch_h": 8.0},
    {"offset_y": -20.0}, {"offset_y": 20.0}, {"margins": (0, 0, 0, 0)},
    {"i1io_crosses": False}, {"i1io_crosses": False, "offset_y": -12.0},
    {"i1io_crosses": False, "patch_h": 20.0}, {"spacer_mode": "none"}, {"edge_spacers": True}])
def test_every_chart_chromiq_builds_is_taken(tmp_path, kw):
    if kw.get("paper") in ("4x6", "127x178"):
        kw = {**kw, "paper": {"4x6": "102x152", "127x178": "127x178"}[kw["paper"]]}
    _build(tmp_path, 200, **kw)
    P.record_of(tmp_path / "c.ti2")
    P.check_places(tmp_path / "c.ti2")


def test_start_says_it_for_a_chart_of_one_piece(qtbot, tmp_path, monkeypatch):
    """The window of START, for a one-piece chart whose file was changed; nothing else is asked
    of a sound one."""
    from ui.tabs.tab_measure import TabMeasure
    from PyQt6.QtWidgets import QMessageBox, QWidget
    _r, side, doc = _build(tmp_path, 300)
    said = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: said.append(
        (box.text(), box.informativeText())) or 0)
    me = QWidget()
    qtbot.addWidget(me)
    ask = TabMeasure._blocked_by_the_pieces_record
    assert ask(me, tmp_path / "c.ti2") is False and said == []
    side.write_text(json.dumps(_bad(doc, "patches 100 mm off")), encoding="utf-8")
    assert ask(me, tmp_path / "c.ti2") is True
    assert said == [M.M_I1IO_PIECES_RECORD.render()]


# ---- S5, S6: the words --------------------------------------------------------------------------

def test_a_piece_without_crosses_is_laid_by_its_first_patch():
    from types import SimpleNamespace
    from ui import i1io_table_window as W

    def words(target):
        me = SimpleNamespace(job=SimpleNamespace(page=1), _sheet={"pages": [
            {"aim_points": [{"target": "cross"}]}, {"aim_points": [{"target": target}] * 3}]})
        return next(v for v in vars(W).values()
                    if hasattr(v, "_corner_text"))._corner_text(me)
    cross, patch = words("cross"), words("patch")
    assert cross == "mark 1 at the top left"
    assert patch == "its first strip at the top and patch 1 of it at the top left"
    # the print note's own words
    assert patch.replace("strip at", "strip is at") in M._I1IO_PRINT_LAY_PATCHES
    for m in (M.M_I1IO_DRIVE_PREPARE_PIECES, M.M_I1IO_DRIVE_SHEET_LAID_PIECE,
              M.M_I1IO_DRIVE_PREPARE, M.M_I1IO_DRIVE_SHEET_LAID):
        for n in (1, 4):
            kw = {"page": 2, "pages": n} if "{pages}" in m.body else {"page": 2}
            body = m.render(corner=patch, **kw)[1]
            assert patch in body and "mark 1" not in body and "{" not in body
            assert "mark 1 at the top left" in m.render(corner=cross, **kw)[1]


def test_the_texts_say_what_a_real_table_has_seen():
    """A sheet in pieces: still a simulated table only. Compact: its rows have been read on one
    real table, without the dual scan (item 71; "a simulated table only" until 4.3.66)."""
    assert "a simulated table only, not on a real one" in M._I1IO_PIECES_INFO
    assert "simulated" not in M._I1IO_COMPACT_INFO
    assert "read on one real table so far, without the dual scan" in M._I1IO_COMPACT_INFO


def test_nothing_promises_a_piece_larger_than_a4_or_letter():
    from workflow.i1io import table_facts as F
    assert F.LARGE_PIECES is False
