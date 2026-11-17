"""Fix round 10, part 2: the open points the owner wants closed in this release.

a. Refinement strips: the Measure tab passes the patches to read again to the job; the job reads
   only those and the Save replaces exactly their readings.
c. The tab's strip detection on an i1iO chart ("Strip detection failed: list index out of
   range").
d. The Measure tab's options for a table chart: only those with no meaning are greyed, each with
   its reason; the rest reach the job.
Against the simulated table and helper: no USB, no instrument."""
from __future__ import annotations

import pytest

from tests.i1io_table.test_fix10_review10 import _person
from tests.i1io_table.test_window_in_the_measure_tab import (beta, start, tab,  # noqa: F401
                                                             table_run)
from workflow.measurement_state import Ti3State, classify


def _measure_whole_chart(tab, run, monkeypatch, qtbot):
    sim = start(tab, run, monkeypatch)
    p = _person(tab._table_window, sim, qtbot)
    p.drive_until("end_of_session")
    p.press("Save and stop")
    p.drive_until(("home_offered", "done"))
    if p.page() == "home_offered":
        p.press("Leave it there")
    p.press("Close")
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    return sim


def _rows_by_loc(path):
    from workflow.i1io.table.measurement import _rows_by_loc
    fields, rows, _t = _rows_by_loc(path)
    return fields, rows


# ---- a. refinement strips ------------------------------------------------------------------------

def _start_refining(tab, run, monkeypatch, strips, patches):
    """START with Refine / resume and "Refinement strips file" ticked and the quality check's
    list loaded (strips, and patches when the list names them), as Check & Refine leaves it."""
    import ui.i1io_table_window as W
    from tests.i1io_table.window_sim import WindowSim
    sim = WindowSim()
    monkeypatch.setattr(W, "JOB_FACTORY", sim.factory)
    monkeypatch.setattr(W, "USB_STATUS", lambda: (True, ""))
    monkeypatch.setattr(tab, "_maybe_offer_existing_overlay", lambda: None)
    tab.set_ti1_path(run.artefact(".ti1"))
    tab.show()
    tab._strip_list = list(strips)
    tab._refine_patch_list = list(patches)
    mode = tab._current_mode()
    resume = tab._resume_cb if mode == "guided" else tab._m_resume_cb
    refine = tab._refine_cb if mode == "guided" else tab._m_refine_cb
    for cb in (resume, refine):
        cb.setVisible(True)
        cb.setEnabled(True)
        cb.setChecked(True)
    tab._on_start()
    return sim


@pytest.mark.parametrize("by", ["strips", "patches"])
def test_a_a_refinement_reads_only_the_listed_patches_and_replaces_only_them(
        tab, beta, tmp_path, monkeypatch, qtbot, by):
    from PyQt6.QtWidgets import QMessageBox
    from tests.i1io_table.test_job_reading import small_sheet
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(
        (self.windowTitle(), self.text()[:200])) or 0)
    run, sheet = table_run(tmp_path, small_sheet([4, 4, 4]))
    _measure_whole_chart(tab, run, monkeypatch, qtbot)
    fields, before = _rows_by_loc(run.measurement_ti3)
    want = ({"B1", "B3"} if by == "patches"
            else {q["loc"] for q in sheet["pages"][0]["strips"][1]["patches"]})
    sim = _start_refining(tab, run, monkeypatch, ["B"],
                          ["B1", "B3"] if by == "patches" else [])
    win = tab._table_window
    assert win is not None, shown
    p = _person(win, sim, qtbot)
    job = sim.jobs[0]
    assert job.only_locs == want and job._resume_base is not None
    assert p.page() == "prepare"
    from workflow import measurement_messages as M
    assert M.M_I1IO_DRIVE_REFINE.render(n=len(want))[1] in win._text.text()
    read = []
    win.progress.connect(lambda ev: read.append(ev["loc"]) if ev.get("event") == "patch_read"
                         else None)
    p.drive_until("end_of_session")
    assert set(read) == want                                      # only those were read
    p.press("Save and stop")
    _f, after = _rows_by_loc(run.measurement_ti3)
    assert set(after) == set(before)
    changed = {loc for loc in before if before[loc] != after[loc]}
    assert changed <= want                                        # nothing else touched
    # the session's own readings are exactly those patches (the simulated instrument reads
    # the same value again, so the file's numbers need not change)
    import json as _json
    sdir = run.i1io_table_session_dir(job.stamp)
    recs = [_json.loads(f.read_text()) for f in sdir.glob("*/*.row.json")]
    assert {a["loc"] for r in recs for a in r.get("accepted", [])} == want
    assert classify(run.measurement_ti3, run.chart_ti2).state is Ti3State.COMPLETE
    assert "Your profile has not changed yet" in tab._log.toPlainText()


def test_a_without_a_list_the_table_reads_the_whole_chart_and_refine_is_not_passed(
        tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    tab._strip_list = []
    tab._m_refine_cb.setChecked(True)
    sim = start(tab, run, monkeypatch)
    assert sim.jobs[0].only_locs is None


def test_a_two_starts_in_one_second_never_share_a_session_folder(tmp_path):
    from ui import i1io_table_window as W
    run, _sheet = table_run(tmp_path)
    assert W.unique_stamp(run, "20261117-100000") == "20261117-100000"
    run.i1io_table_session_dir("20261117-100000").mkdir(parents=True)
    assert W.unique_stamp(run, "20261117-100000") == "20261117-100000_2"
    run.i1io_table_session_dir("20261117-100000_2").mkdir(parents=True)
    assert W.unique_stamp(run, "20261117-100000") == "20261117-100000_3"


# ---- c. the tab's strip detection on an i1iO chart ----------------------------------------------

@pytest.fixture
def i1io_chart(tmp_path, beta):
    """A real i1iO 2 chart from ChromIQ's own layout engine, as Create Chart builds it."""
    import numpy as np
    from tests.i1p_forward import write_ti1
    from workflow.layout_engine import chart as engine
    rng = np.random.default_rng(17)
    ti1 = write_ti1(tmp_path / "c.ti1", [tuple(rng.uniform(0, 100, 3)) for _ in range(60)])
    engine.build_chart(ti1, tmp_path / "c", instrument="IO2", paper="A4", dpi=100, seed=5,
                       randomize=True)
    return tmp_path / "c.ti2"


def test_c_the_label_fallback_no_longer_raises_on_an_i1io_tiff(i1io_chart, caplog):
    import logging
    from ui.tabs import tab_measure as T
    with caplog.at_level(logging.DEBUG, logger="ui.tabs.tab_measure"):
        assert T._detect_stripe_rects(i1io_chart.with_suffix(".tif")) == []
    assert "Strip detection failed" not in caplog.text


def test_c_an_i1io_chart_gets_its_strips_from_its_own_geometry(tab, i1io_chart, caplog):
    import json
    import logging
    with caplog.at_level(logging.DEBUG):
        tab.set_ti1_path(i1io_chart)
    assert "Strip detection failed" not in caplog.text
    data = json.loads(i1io_chart.with_suffix(".strips.json").read_text(encoding="utf-8"))
    want = [(s["x"], s["y"], s["w"], s["h"]) for s in data["strips"] if s["page"] == 0]
    got = [(r.x(), r.y(), r.width(), r.height()) for r in tab._page_stripe_rects[0]]
    assert got == want and len(got) > 1


def test_c_with_the_beta_off_nothing_of_the_i1io_side_is_read(tab, i1io_chart, monkeypatch):
    import workflow.i1io.support as sup
    from ui.tabs import tab_measure as T
    sup.set_enabled_for_this_process(False)
    called = []
    monkeypatch.setattr(T, "strip_rects_from_strips_json",
                        lambda *a: called.append(1) or None)
    tab.set_ti1_path(i1io_chart)
    assert called == []


def test_c_one_label_cluster_on_another_chart_gives_no_rects_as_before(tmp_path):
    """The only change for every other chart: the case that raised and was caught (and
    returned []) returns [] without raising."""
    from PIL import Image, ImageDraw
    from ui.tabs import tab_measure as T
    img = Image.new("L", (800, 600), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([380, 20, 400, 32], fill=0)                 # one label
    d.rectangle([100, 60, 700, 560], fill=120)              # the patches
    f = tmp_path / "one.tif"
    img.save(f)
    assert T._detect_stripe_rects(f) == []


# ---- d. the options for a table chart --------------------------------------------------------

def _opt(tab, key, manual=True):
    opts = tab._m_chartread_opts if manual else tab._chartread_opts
    return next(o for o in opts if o.key == key)


def test_d_only_the_options_without_meaning_are_greyed_each_with_its_reason(
        tab, beta, tmp_path, monkeypatch, qtbot):
    run, sheet = table_run(tmp_path)
    tol = _opt(tab, "tolerance")
    tol.checkbox.setChecked(True)
    hr = _opt(tab, "highres")
    tab.set_ti1_path(run.artefact(".ti1"))
    dead = [tab._m_instr_spin, tab._instr_spin, tab._m_bidir_combo, tab._m_bidir_auto_cb,
            tol.checkbox, _opt(tab, "filter").checkbox]
    for w in dead:
        assert not w.isEnabled() and w.toolTip(), w
    assert "i1iO table" in tab._m_instr_spin.toolTip()
    # patch by patch: ticked and locked, with its own reason
    assert tab._m_pbp_cb.isChecked() and not tab._m_pbp_cb.isEnabled()
    assert "i1iO table" in tab._m_pbp_cb.toolTip()
    # what works stays open: -H, -N, -S, -A, -l/-L/-n, resume, the overlay
    for key in ("highres", "save_lab", "save_lab_and_xyz", "no_spectral", "xrga"):
        assert _opt(tab, key).checkbox.isEnabled(), key
    assert tab._m_resume_cb.isEnabled() or not tab._m_resume_cb.isVisible()
    # a greyed row is not sent; a working one is
    hr.checkbox.setChecked(True)
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    args = tab._manager._build_args(tab._collect_params())
    assert "-T" not in args and "-H" in args and "-p" in args
    # the table's first page lists nothing any more
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    p = _person(win, sim, qtbot)
    assert p.page() == "prepare" and "(-T)" not in win._text.text()


def test_d_another_chart_gets_every_option_back_as_it_was(tab, beta, tmp_path, monkeypatch):
    run, sheet = table_run(tmp_path)
    tol = _opt(tab, "tolerance")
    tol.checkbox.setChecked(True)
    tip = tab._m_instr_spin.toolTip()
    pbp_before = tab._m_pbp_cb.isChecked()
    tab.set_ti1_path(run.artefact(".ti1"))
    assert not tol.checkbox.isEnabled()
    other, _s = table_run(tmp_path / "other", side=False)      # an i1iO chart not driven
    tab.set_ti1_path(other.artefact(".ti1"))
    assert tol.checkbox.isEnabled() and tol.checkbox.isChecked() and not tol.suppressed
    assert tab._m_instr_spin.isEnabled() and tab._m_instr_spin.toolTip() == tip
    assert tab._m_pbp_cb.isEnabled() and tab._m_pbp_cb.isChecked() == pbp_before


def test_d_with_the_beta_off_no_option_is_greyed(tab, tmp_path, monkeypatch):
    import workflow.i1io.support as sup
    sup.set_enabled_for_this_process(False)
    try:
        run, sheet = table_run(tmp_path)
        tab.set_ti1_path(run.artefact(".ti1"))
        assert tab._m_instr_spin.isEnabled() and _opt(tab, "tolerance").checkbox.isEnabled()
        assert getattr(tab, "_table_options_snapshot", None) is None
    finally:
        sup.set_enabled_for_this_process(None)
