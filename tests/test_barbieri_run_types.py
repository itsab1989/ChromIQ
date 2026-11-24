"""The Barbieri Spectro 100xy chart (Beta) in every run type, built for real
in the window: profiling, verification, calibration and a refinement run make
Barbieri charts as they do for every instrument, in their usual folders, each
with its side file, and the Measure tab answers Start with M-BARBIERI-STEPS.
Guided makes one too, with the opening it offers.

Real builds: targen from ArgyllCMS and the layout engine. Fakes for the rest.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.measurement_target import (RUN_TYPE_CALIBRATION,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)

_TARGEN = Path("/Applications/Argyll/bin/targen")
requires_argyll = pytest.mark.skipif(
    not _TARGEN.exists() and shutil.which("targen") is None,
    reason="ArgyllCMS targen is not installed here")


@pytest.fixture(autouse=True)
def barbieri_on():
    from workflow.barbieri import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    from core.settings import AppSettings
    from tests._cal_target_fixture import make_window, show_run
    qs = AppSettings()._qs
    kept = {k: qs.value(k) for k in qs.allKeys()}
    w = make_window(qapp, tmp_path)
    tc = w._tab_chart
    show_run(w, qapp, w._file_mgr.project().current_run().id)
    monkeypatch.setattr(type(tc), "_confirm_displacing_results",
                        lambda self, *a, **k: True)
    monkeypatch.setattr(type(tc), "_handle_target_rename",
                        lambda self, *a, **k: True)
    yield w
    w.close()
    for k in qs.allKeys():
        if k not in kept:
            qs.remove(k)
    for k, v in kept.items():
        qs.setValue(k, v)
    qs.sync()


def _pick(tc, qapp, code="B100XY"):
    tc._switch_mode("manual")
    tc._init_manual_layout_panel()
    p = tc._manual_layout_panel
    k = p.instr.findData(code)
    assert k >= 0, f"{code} is not offered in the layout panel"
    p.instr.setCurrentIndex(k)
    p.instr.activated.emit(k)
    qapp.processEvents()
    assert str(tc._manual_value("printtarg", "-i")) == code


def _generate(w, qapp, qtbot, expect):
    tc = w._tab_chart
    before = expect.stat().st_mtime_ns if expect.exists() else None

    side = expect.with_name(expect.name[:-4] + ".barbieri.json")

    def done():
        if w._runner.is_running or not tc._generate_btn.isEnabled():
            return False
        return (expect.exists() and expect.stat().st_mtime_ns != before
                and side.exists())
    tc._on_generate()
    qtbot.waitUntil(done, timeout=180_000)
    for _ in range(10):
        qapp.processEvents()


def _assert_a_barbieri_chart(ti2: Path) -> dict:
    assert ti2.is_file(), f"no chart at {ti2}"
    head = ti2.read_text(encoding="latin-1").split("BEGIN_DATA_FORMAT")[0]
    assert 'TARGET_INSTRUMENT "Barbieri Spectro 100xy"' in head
    assert 'CHROMIQ_BARBIERI_LAYOUT "1"' in head
    side = json.loads(ti2.with_name(ti2.name[:-4] + ".barbieri.json")
                      .read_text(encoding="utf-8"))
    for pg in side["pages_detail"]:
        assert pg["spectro32"].startswith("R0,0,")
        assert len(pg["reading_order"]) == pg["columns"] * pg["rows"]
    return side


def _measure_refuses(w, ti2, monkeypatch) -> "tuple[str, str]":
    tm = w._tab_measure
    shown = []
    monkeypatch.setattr(type(tm), "_i1io_window",
                        lambda self, t, b: shown.append((t, b)))
    tm._ti1_path = ti2
    assert tm._refused_as_a_barbieri_chart() is True
    assert len(shown) == 1
    return shown[0]


@requires_argyll
def test_profiling_and_verification_charts(win, qapp, qtbot, monkeypatch):
    w, tc = win, win._tab_chart
    run1 = w._file_mgr.project().current_run()
    _pick(tc, qapp)
    _generate(w, qapp, qtbot, run1.chart_ti2)
    side = _assert_a_barbieri_chart(run1.chart_ti2)
    assert side["patch_mm"] == [6.5, 6.5]
    assert side["pages_detail"][0]["grid_mm"][0] == pytest.approx(15.0)
    from workflow import measurement_messages as M
    title, body = _measure_refuses(w, run1.chart_ti2, monkeypatch)
    assert title == M.M_BARBIERI_STEPS.render(
        mode="", opening="", grid_lines="", aim="", first="", minutes=0,
        gateway_lines="", side="", orient="", aim_hint="")[0]
    pg = side["pages_detail"][0]
    assert pg["spectro32"] in body and pg["aim_patch"] in body
    assert "choose IMPORT on this tab" in body   # step 2: the import exists
    # the numbers beside the chart in the preview
    panel = getattr(tc, "_barbieri_numbers", None)
    assert panel is not None
    panel.show_chart(run1.chart_ti2)
    assert panel.isVisibleTo(tc)
    assert pg["spectro32"] in panel._body.text()

    w._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    qapp.processEvents()
    _pick(tc, qapp)
    vti2 = run1.verifications_dir / f"{run1.stem}-verify.ti2"
    _generate(w, qapp, qtbot, vti2)
    _assert_a_barbieri_chart(vti2)
    _assert_a_barbieri_chart(run1.chart_ti2)


@requires_argyll
def test_a_calibration_chart(win, qapp, qtbot):
    w, tc = win, win._tab_chart
    project = w._file_mgr.project()
    w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
    qapp.processEvents()
    _pick(tc, qapp)
    cal = project.calibration
    cti2 = cal.dir / f"{cal.stem}.ti2"
    _generate(w, qapp, qtbot, cti2)
    side = _assert_a_barbieri_chart(cti2)
    assert not project.current_run().chart_ti2.exists()
    assert side["pages"] >= 1


@requires_argyll
def test_a_refinement_run(win, qapp, qtbot):
    """A second run of the project (where refinement strips are made) builds
    its own Barbieri chart in its own folder."""
    w, tc = win, win._tab_chart
    project = w._file_mgr.project()
    run2 = project.new_run()
    from tests._cal_target_fixture import show_run
    show_run(w, qapp, run2.id)
    _pick(tc, qapp)
    _generate(w, qapp, qtbot, run2.chart_ti2)
    _assert_a_barbieri_chart(run2.chart_ti2)


@requires_argyll
def test_guided_makes_a_barbieri_chart_with_its_opening(win, qapp, qtbot):
    w, tc = win, win._tab_chart
    run1 = w._file_mgr.project().current_run()
    tc._switch_mode("guided")
    i = tc._instr_combo.findData("B100XY")
    assert i >= 0, "the Barbieri is not offered in Guided"
    tc._instr_combo.setCurrentIndex(i)
    qapp.processEvents()
    box = tc._barbieri_head_combo
    assert box.isVisibleTo(tc)
    # the 3 mm transmission opening: the 0.5 mm one fills an A4 sheet with
    # about 9800 patches of 1 mm, whose patch set takes targen long enough to
    # raise the "taking longer than usual" window on a loaded machine
    box.setCurrentIndex(box.findData("transmission-3"))
    qapp.processEvents()
    _generate(w, qapp, qtbot, run1.chart_ti2)
    side = _assert_a_barbieri_chart(run1.chart_ti2)
    assert side["head"] == "transmission-3"
    assert side["spectro32_mode"] == "MT"
    assert side["patch_mm"] == [6.5, 6.5]


def test_guided_greys_the_film_frames_without_the_page_beta(win, qapp):
    from workflow.page_output import support as po
    before = po._latched
    po.set_enabled_for_this_process(False)
    try:
        tc = win._tab_chart
        tc._switch_mode("guided")
        tc._instr_combo.setCurrentIndex(tc._instr_combo.findData("B100XY"))
        qapp.processEvents()
        box = tc._barbieri_head_combo
        box.setCurrentIndex(box.findData("transmission-0.5"))
        qapp.processEvents()
        from workflow.barbieri.chart import (GUIDED_FILM_SIZES,
                                             film_paper_code)
        combo = tc._paper_combo
        model = combo.model()
        for key in GUIDED_FILM_SIZES:
            i = combo.findData(film_paper_code(key))
            assert i >= 0
            item = model.item(i)
            assert not item.isEnabled()
            assert "Custom page size" in item.toolTip()
        assert model.item(combo.currentIndex()).isEnabled()
    finally:
        po._latched = before


def test_guided_restores_a_saved_large_film_frame(win, qapp):
    """Saved: Guided, 0.5 mm, the large film frame. Restored: the same paper,
    not the 35 mm frame (the opening decides the list, so it comes first)."""
    from workflow.page_output import support as po
    from workflow.barbieri.chart import film_paper_code
    before = po._latched
    po.set_enabled_for_this_process(True)
    try:
        tc = win._tab_chart
        s = tc._settings
        code = film_paper_code("film_large")
        s.set("chart_instrument", "B100XY")
        s.set("chart_barbieri_head", "transmission-0.5")
        s.set("chart_paper", code)
        # the combo on the factory opening, as at start-up
        tc._switch_mode("guided")
        box = tc._barbieri_head_combo
        box.setCurrentIndex(box.findData("reflection-3"))
        qapp.processEvents()
        tc._restore_defaults_impl()
        qapp.processEvents()
        assert box.currentData() == "transmission-0.5"
        assert tc._paper_combo.currentData() == code
    finally:
        po._latched = before
