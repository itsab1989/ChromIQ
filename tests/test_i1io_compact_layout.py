"""CHART LAYOUT: STANDARD OR COMPACT (the new i1iO chart layout, 25 November 2026), in Guided and in
Manual, checked through the FILES Generate writes and the job's own plan, not through constants; and
"Row speed" that never acts silently on a chart of short patches."""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _i1io_baseline as base
from workflow.i1io import chart as C
from workflow.i1io import table_facts as F


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _side(folder):
    return json.loads((folder / "chart.i1io.json").read_text(encoding="utf-8"))


def _slots(folder):
    return [(q["loc"], q["sample_id"]) for pg in _side(folder)["pages"]
            for st in pg["strips"] for q in st["patches"]]


def _guided(paper, layout):
    return {"door": "guided", "paper": paper, "count": "page", "rep": "RGB",
            "recipe": {}, "params": {"i1io_layout": layout}}


def _manual(paper, **recipe):
    return {"door": "manual", "paper": paper, "count": "page", "rep": "RGB",
            "recipe": recipe, "params": {}}


@pytest.mark.parametrize("paper,count", (("A4", 638), ("Letter", 621)))
def test_compact_in_guided_and_manual_writes_the_same_compact_chart(tmp_path, paper, count):
    base.build_case("g", _guided(paper, "compact"), tmp_path / "g")
    along, across, spacer = C.layout_sizes("compact")
    base.build_case("m", _manual(paper, patch_h_mm=along, patch_w_mm=across,
                                 spacer_width_mm=spacer), tmp_path / "m")
    for d in ("g", "m"):
        side = _side(tmp_path / d)
        assert side["patch_mm"] == [8.0, 8.0] and side["spacer_mm"] == 1.0
        assert sum(len(st["patches"]) for st in side["pages"][0]["strips"]) == count
        assert len(side["pages"]) == 1
    # the same seed puts the same patch in the same slot, whichever door
    assert _slots(tmp_path / "g") == _slots(tmp_path / "m")
    # and what was chosen is in the chart's own record
    rec = json.loads((tmp_path / "g" / "chart.channels.json").read_text(
        encoding="utf-8"))["layout"]["recipe"]
    assert (rec["patch_h_mm"], rec["patch_w_mm"], rec["spacer_width_mm"],
            rec["i1io_limits"]) == (8.0, 8.0, 1.0, 2)


@pytest.mark.parametrize("layout", ("", "standard"))
def test_standard_is_the_chart_it_always_was(tmp_path, layout):
    base.build_case("g", _guided("A4", layout), tmp_path / "g")
    stored = json.loads((base.Path(__file__).parent / "data"
                         / "i1io_baseline_4365.json").read_text(
        encoding="utf-8"))["cases"]["guided_A4"]
    for f in base.GEOMETRY_FILES:
        assert base.digest(tmp_path / "g" / f, fonts=False) == stored[f], f


def test_the_layouts_are_named_by_their_numbers():
    assert C.layout_named(10, 8, 1) == C.layout_named(0, 0, 0) == "standard"
    assert C.layout_named(8, 8, 1) == "compact"
    for odd in ((8, 8, 0.75), (9, 8, 1), (8, 7.5, 1)):
        assert C.layout_named(*odd) == ""
    assert C.layout_kwargs("standard") == {} == C.layout_kwargs("")


# ---- Manual ------------------------------------------------------------------

@pytest.fixture
def panel(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    p.show()
    p.instr.setCurrentIndex(p.instr.findData("IO2"))
    return p


def _pick(panel, name):
    k = panel.i1io_layout.findData(name)
    panel.i1io_layout.setCurrentIndex(k)
    panel.i1io_layout.activated.emit(k)


def test_manuals_choice_fills_the_boxes_and_shows_custom_when_they_are_edited(panel):
    assert panel.i1io_layout.isEnabled()
    assert panel.i1io_layout.currentData() == "standard"
    assert not panel._i1io_layout_note.isVisibleTo(panel)
    _pick(panel, "compact")
    assert (panel.patch_x.value(), panel.patch_y.value(),
            panel.spacer_width.value()) == (8.0, 8.0, 1.0)
    assert panel._i1io_layout_note.isVisibleTo(panel)
    kw = panel.get_recipe().build_kwargs()
    assert (kw["patch_h"], kw["patch_w"]) == (8.0, 8.0)
    panel.patch_y.setValue(9.0)
    assert panel.i1io_layout.currentData() == ""
    assert panel.i1io_layout.currentText() == "Custom"
    assert not panel._i1io_layout_note.isVisibleTo(panel)
    assert not panel.i1io_layout.model().item(2).isEnabled()
    _pick(panel, "standard")
    assert (panel.patch_y.value(), panel.patch_x.value()) == (10.0, 8.0)
    # a recipe shows the layout its numbers are
    from dataclasses import replace
    panel.set_recipe(replace(panel.get_recipe(), patch_h_mm=8.0, patch_w_mm=8.0))
    assert panel.i1io_layout.currentData() == "compact"


def test_a_layout_is_shown_only_with_its_spacers(panel):
    """The help says a layout prints coloured spacers and no gaps: without
    them the box says Custom, and choosing the layout brings them back."""
    for spoil in (lambda: panel.spacer_mode.setCurrentIndex(
                      panel.spacer_mode.findData("none")),
                  lambda: panel.spacer_mode.setCurrentIndex(
                      panel.spacer_mode.findData("bw")),
                  lambda: panel.strip_gap.setValue(0.5),
                  lambda: panel.inter_patch.setValue(0.5)):
        _pick(panel, "compact")
        assert panel.i1io_layout.currentData() == "compact"
        spoil()
        assert panel.i1io_layout.currentData() == ""
        assert not panel._i1io_layout_note.isVisibleTo(panel)
        _pick(panel, "compact")
        assert panel.spacer_mode.currentData() == "colored"
        assert panel.strip_gap.value() == panel.inter_patch.value() == 0.0


def test_manuals_choice_is_there_for_the_i1io_only(panel):
    assert panel.i1io_layout.isVisibleTo(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    assert not panel.i1io_layout.isVisibleTo(panel)
    assert not panel._i1io_layout_note.isVisibleTo(panel)


def test_with_the_beta_off_the_choice_is_not_built(qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.i1io import support
    support.set_enabled_for_this_process(False)
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    assert p.i1io_layout is None


# ---- Guided ------------------------------------------------------------------

@pytest.fixture
def chart_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    from core.file_manager import FileManager
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    yield t
    t.close()
    t.deleteLater()


def _to_io2(tab):
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("IO2"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))


def test_guideds_choice_counts_builds_and_is_kept(chart_tab):
    tab = chart_tab
    _to_io2(tab)
    box = tab._i1io_layout_combo
    assert [box.itemData(i) for i in range(box.count())] == ["standard", "compact"]
    assert box.currentData() == "standard" and box.isEnabled()
    assert tab._collect_guided().i1io_layout == "standard"
    assert "i1io_layout" not in tab._shared_get("guided")
    assert tab._engine_capacity("IO2", "A4", dd=False, td=False, eff_lb=True, nsl=False,
                                pscale=1.0, margin=6) == 528
    tab._set_guided_i1io_layout("compact")
    assert tab._engine_capacity("IO2", "A4", dd=False, td=False, eff_lb=True, nsl=False,
                                pscale=1.0, margin=6) == 638
    params = tab._collect_guided()
    assert params.i1io_layout == "compact"
    kw = tab._creator._engine_build_kwargs(params)
    assert (kw["patch_h"], kw["patch_w"], kw["spacer_width"]) == (8.0, 8.0, 1.0)
    assert not tab._i1io_layout_note.isHidden()
    assert "8" in tab._engine_info_line("IO2", "A4", 300, dd=False, td=False, eff_lb=True,
                                        nsl=False, pscale=1.0, margin=6)
    # the target's own row
    row = tab._shared_get("guided")
    assert row["i1io_layout"] == "compact"
    tab._set_guided_i1io_layout("standard")
    tab._shared_set("guided", "i1io_layout", row["i1io_layout"])
    assert box.currentData() == "compact"
    # another instrument: hidden, and no row of its carries the key
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    assert box.isHidden() and tab._i1io_layout_note.isHidden()
    assert "i1io_layout" not in tab._shared_get("guided")
    assert tab._collect_guided().i1io_layout == ""


def test_the_carry_rule_knows_the_key():
    from workflow.i1io import support
    assert "i1io_layout" in support.CHART_GUIDED_KEYS


# ---- the job's own plan, and Row speed ----------------------------------------

def _compact_chart(tmp_path, **kw):
    from tests.i1io_table import bed_sim as B
    kw = {"patch_h": 8.0, "patch_w": 8.0, "spacer_width": 1.0, "i1io_limits": 2, **kw}
    return B.build_chart(tmp_path, count=58, **kw)


def test_the_jobs_own_plan_of_a_compact_row(tmp_path):
    from tests.i1io_table import bed_sim as B
    from tests.i1io_table import job_harness as H
    from tests.i1io_table.test_job_reading import read_page, ready_to_read
    from workflow.i1io.table import spot as sp
    ch = _compact_chart(tmp_path)
    assert ch.sheet["patch_mm"] == [8.0, 8.0]
    job, sim, helper, run = B.bed_job(tmp_path, ch, B.Bed(ch.laid()), ask_after_each_step=False)
    assert job.set_options(["-v", "-c", "1", "chart"]).ok
    p = H.Person(job, sim)
    ready_to_read(job, p)
    plan = sp.plan_strip_row(job.sheet, 0, 0, job.alignment, job._table.front_y)
    assert plan.scan.speed == 61
    assert sp.strip_windows_ok(plan.scan) >= sp.STRIP_MIN_READINGS
    rows = read_page(job, p)
    assert all(r.ok and r.detail["row_kind"] == "strip" for r in rows)


def test_the_factor_is_decided_for_short_patches_only():
    from ui import i1io_table_window as W
    for along, factor, used in ((8.0, 1.95, 1.0), (9.4, 1.05, 1.0), (9.5, 1.95, 1.95),
                                (10.0, 1.95, 1.95), (8.0, 1.0, 1.0), (8.0, 0.8, 0.8)):
        got, note = W.row_speed_for({"patch_mm": [8.0, along]}, factor)
        assert got == used and bool(note) == (used != factor), (along, factor)
    assert "1.95" in W.row_speed_for({"patch_mm": [8.0, 8.0]}, 1.95)[1]
    # (safety review N1: a chart that names no patch length is never read faster)
    assert W.row_speed_for({}, 1.95) == (1.0, "") and W.row_speed_for({}, 0.8) == (0.8, "")


def test_the_row_speed_note_is_about_rows_in_one_scan_only(qtbot, monkeypatch, tmp_path):
    """Patch by patch, or with the dual scan, nothing is read at "Row speed": no note."""
    from types import SimpleNamespace as NS
    from tests.i1io_table import bed_sim as B
    from tests.i1io_table.test_window import open_window
    from ui import i1io_table_window as W
    at = W.TableMeasureWindow._rows_at_row_speed
    assert at(NS(_dual=None, job=NS(row_kind="strip")))
    assert not at(NS(_dual=None, job=NS(row_kind="spot")))
    assert not at(NS(_dual=object(), job=NS(row_kind="strip")))
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 0)
    ch = _compact_chart(tmp_path, patch_h=8.0)
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "w.ini"), QSettings.Format.IniFormat)
    s.set(W.ROW_SPEED_KEY, 1.95)
    win, sim, run, p, saved, fin = open_window(
        qtbot, monkeypatch, tmp_path, s, sheet=ch.sheet,
        sim=B.bed_window_sim(ch, B.Bed(ch.laid()), real_table=False), run=ch.run,
        args=["-v", "-p", "-c", "1", str(ch.run.chart_ti2)[:-4]], guided=True)
    p.drive_until("prepare")
    assert win._row_speed_said() == "" and "Row speed" not in win._text.text()
    assert "Row speed" not in win.guidance_bar_text()
    assert win.job.row_speed_factor == 1.0


@pytest.mark.parametrize("guided", (True, False), ids=("guided", "guidance off"))
def test_compact_at_195_sends_the_wire_of_100_and_says_it_first(qtbot, monkeypatch, tmp_path,
                                                               guided):
    from tests.i1io_table import bed_sim as B
    from tests.i1io_table.test_window import open_window
    from ui import i1io_table_window as W
    from workflow import measurement_messages as M
    monkeypatch.setattr(W, "HANDS_OFF_READY_MS", 0)     # (the person waits; tests/i1io_table)
    wires, said = {}, {}
    for factor, along in ((1.0, 8.0), (1.95, 8.0), (1.0, 10.0), (1.95, 10.0)):
        d = tmp_path / f"{factor}-{along}"
        ch = _compact_chart(d, patch_h=along) if along == 8.0 else B.build_chart(d, count=48)
        sim = B.bed_window_sim(ch, B.Bed(ch.laid()), real_table=False)
        from core.settings import AppSettings
        from PyQt6.QtCore import QSettings
        s = AppSettings()
        s._qs = QSettings(str(d / "w.ini"), QSettings.Format.IniFormat)
        s.set(W.ROW_SPEED_KEY, factor)
        notices, logged = [], []
        first = []
        win, sim, run, p, saved, fin = open_window(
            qtbot, monkeypatch, d, s, sheet=ch.sheet, sim=sim, run=ch.run,
            args=["-v", "-c", "1", str(ch.run.chart_ti2)[:-4]], guided=guided)
        win.notice.connect(notices.append)
        win.log_line.connect(logged.append)
        note = M.M_I1IO_ROW_SPEED_NOT_USED.render(factor="1.95", mm="8", from_mm="9.5")[1]
        if guided:
            p.drive_until("prepare")
            first = [note in win._text.text()]
            assert sim.sim.received == [] if sim.sim is not None else True
        page = p.drive_until(("end_of_session", "done"))
        if page == "end_of_session":
            p.press("Save and stop")
        if not guided:
            # the first page is not shown: the notice area keeps the sentence, also after a
            # countdown has used that area (seen on screen: it was gone with the first one)
            shown = [n for n in notices if win.guidance_notice_text() in n]
            assert win.countdowns_seen and shown
            assert [note in n for n in shown] == [factor != 1.0 and along == 8.0] * len(shown)
        wires[factor, along] = [ln for ln in sim.sim.received]
        said[factor, along] = (first, win._row_speed_note)
        assert win.job.row_speed_factor == (1.0 if along == 8.0 else factor)
        assert bool(win.job._table.row_speed_frame) == (factor != 1.0 and along == 10.0)
        assert s.get(W.ROW_SPEED_KEY) == factor            # the stored setting stays
        from workflow.ti3_provenance import read_row_speed
        mark = read_row_speed(run.measurement_ti3)
        assert bool(mark) == (factor != 1.0 and along == 10.0)
    assert wires[1.95, 8.0] == wires[1.0, 8.0]
    assert wires[1.95, 10.0] != wires[1.0, 10.0]
    assert said[1.95, 8.0][1] and not said[1.0, 8.0][1] and not said[1.95, 10.0][1]
    if guided:
        assert said[1.95, 8.0][0] == [True] and said[1.0, 8.0][0] == [False]


def test_the_number_the_rule_uses_is_the_charts_own():
    assert F.ROW_SPEED_FROM_MM.value == 9.5 == F.DUAL_ROW_FROM_MM.value
