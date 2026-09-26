"""B8-1295 to B8-1299: beta 44 challenge round 5, inside the one rule of
92317bd5 ("the recipe stored is the one the engine would show").

B8-1295 THE ONE PREDICATE. Whether Manual's chart is laid out by the layout
        panel is `_layout_panel_lays_out(-i, engine setting)`: the box ticked,
        or the CR30 (engine-only) whatever the box says. The frame, the build,
        the save, the restore, the tick, the per-target path and the p3
        repair all ask it. With the CR30 and the box unticked the save used to
        store a recipe converted from printtarg's hidden rows, the tick
        replaced the panel with them, the restart put -p on a passing A4 and
        the build took printtarg's rows instead of the panel on screen.
B8-1296 the p3 repair only while the panel is what is shown.
B8-1297 the tick after a restart keeps the four margins a real recipe for
        the same instrument and paper was saved with, as the session did.
B8-1298 EVERY placeholder shape the history wrote is recognised: ten, from
        v3.13.0-beta.7 to beta 43, each fixture a store its release wrote on
        screen (tests/data/b8_1298_placeholders/, fixes-5/old-stores).
B8-1299 a save made in Guided stores what Manual will show.

MUTATIONS: ~/Desktop/ChromIQ-beta44-proof/fixes-5/mutations.txt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402
from workflow.layout_engine.presets import (                    # noqa: E402
    SUPPORTED_INSTRUMENTS, LayoutRecipe, default_recipe)

DATA = Path(__file__).parent / "data" / "b8_1298_placeholders"
#: tag -> the release range whose shape that store is (the tag walk)
FIXTURES = {
    "v3.13.0-beta.9": "v3.13.0-beta.7 to v3.13.0-beta.9",
    "v3.13.0-beta.10": "v3.13.0-beta.10 to v3.13.0-beta.10",
    "v3.13.0-beta.13": "v3.13.0-beta.11 to v3.13.0-beta.13",
    "v3.13.0-beta.20": "v3.13.0-beta.14 to v3.13.0-beta.20",
    "v3.13.0-beta.22": "v3.13.0-beta.21 to v3.13.0-beta.22",
    "v3.13.9": "v3.13.0-beta.23 to v3.13.9",
    "v4.0.1": "v3.13.10 to v4.0.2-beta.1",
    "v4.1.1": "v4.0.2-beta.2 to v4.1.1",
    "v4.1.4": "v4.1.2-beta.1 to v4.1.5-beta.2",
    "v4.2.0": "v4.1.5-beta.3 to v4.3.0-beta.43 (a026e3e5)",
}


def _fixture(tag):
    return json.loads((DATA / f"{tag}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def store(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _session(qapp, s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    t = TC.TabChart(ArgyllRunner(s), FileManager(s), s)
    qapp.processEvents()
    return t


def _close(qapp, t):
    t.hide()
    t.deleteLater()
    qapp.processEvents()


def _seed(s, **kv):
    base = {"chart_mode": "manual"}
    base.update(kv)
    for k, v in base.items():
        s.set(k, v)


def _manual(qapp, t):
    if t._current_mode() != "manual":
        t._manual_btn.click()
        qapp.processEvents()
    p = t._manual_layout_panel
    r = p.get_recipe()
    return {"-i": t._manual_instr_pw.get_raw_value(),
            "-p": t._manual_paper_pw.get_raw_value(),
            "panel_instr": p.instr.currentData(), "panel_paper": p.selection()[1],
            "shown": bool(t._manual_layout_grp.isVisibleTo(t)),
            "dpi": r.dpi, "pscale": r.pscale, "sscale": r.sscale,
            "instr_margins": r.use_instrument_margins,
            "margins": [r.margin_top, r.margin_right, r.margin_bottom,
                        r.margin_left],
            "helper": r.helper_markers, "text": r.chart_text}


# ---------------------------------------------------------------------------
# B8-1298: every placeholder shape, and nothing else
# ---------------------------------------------------------------------------
def test_there_is_a_fixture_for_every_shape_in_the_table():
    ranges = {f"{a} to {b}" for a, b, _c, _n in TC._UNSEEN_PANEL_SHAPES}
    assert ranges == set(FIXTURES.values())
    assert sorted(p.stem for p in DATA.glob("*.json")) == sorted(FIXTURES)


@pytest.mark.parametrize("tag", sorted(FIXTURES))
def test_each_release_store_is_recognised_as_its_own_shape(tag):
    assert TC._unseen_panel_shape(_fixture(tag)) == FIXTURES[tag]


@pytest.mark.parametrize("tag", sorted(FIXTURES))
def test_each_is_recognised_as_an_ini_store_returns_it(tag):
    d = {k: ("" if v is None else str(v).lower() if isinstance(v, bool)
             else str(v) if isinstance(v, (int, float)) else v)
         for k, v in _fixture(tag).items()}
    assert TC._is_unseen_panel_recipe(d)


#: one field a person could have set, per shape: each makes it a real recipe
_ONE_OFF = [("dpi", 300), ("paper", "Letter"), ("instrument", "CM"),
            ("margin_top", 0.5), ("margin_left", 6.0), ("pscale", 0.95),
            ("sscale", 1.0), ("pscale", 1.0), ("border", 10.0),
            ("chart_text", "x"), ("clip_border_width_mm", 26.0),
            ("strip_gap_mm", 1.0), ("seed", 1234), ("area_ratio", 0.5),
            ("layout_mode", "patch_first"), ("helper_marker_edge_mm", 4.0)]


@pytest.mark.parametrize("tag", sorted(FIXTURES))
@pytest.mark.parametrize("field,value", _ONE_OFF)
def test_one_field_off_makes_any_shape_a_real_recipe(tag, field, value):
    d = _fixture(tag)
    if field not in d or d[field] == value:
        pytest.skip(f"{tag} did not write {field}={value!r} differently")
    d[field] = value
    assert not TC._is_unseen_panel_recipe(d), (tag, field, value)


@pytest.mark.parametrize("tag", ["v3.13.9", "v4.0.1", "v4.1.1", "v4.1.4"])
def test_a_field_that_range_never_wrote_makes_it_real(tag):
    """A 0.5 scale beside a field only v4.1.5-beta.7 on wrote is no store
    any release wrote: a hybrid is a real recipe."""
    d = dict(_fixture(tag), margins_explicit=False)
    assert not TC._is_unseen_panel_recipe(d)


def test_the_old_helper_marker_values_only_in_their_own_range():
    """1.0 / 3.0 is v4.0.2-beta.2 to v4.1.1's; beside the newer
    per-patch count (v4.1.2-beta.1 on) it is a real recipe."""
    d = dict(_fixture("v4.1.1"), helper_marker_per_patch=3)
    assert not TC._is_unseen_panel_recipe(d)


@pytest.mark.parametrize("instr", SUPPORTED_INSTRUMENTS)
@pytest.mark.parametrize("paper", ["A4", "A2", "Letter", "A3", "130x180"])
@pytest.mark.parametrize("scale", [0.5, 1.0])
def test_no_factory_layout_is_any_placeholder(instr, paper, scale):
    d = default_recipe(instr, paper).to_dict()
    d.update(pscale=scale, sscale=scale)
    assert not TC._is_unseen_panel_recipe(d)


def test_no_built_in_preset_is_any_placeholder():
    seen = 0
    for p in TC.KNUT_PRESETS_BY_KEY.values():
        rec = getattr(p, "layout_recipe", None)
        if rec:
            full = LayoutRecipe.from_dict(dict(rec)).to_dict()
            assert not TC._is_unseen_panel_recipe(full), p
            seen += 1
    assert seen > 0


@pytest.mark.parametrize("tag", ["v3.13.9", "v4.0.1", "v4.1.1", "v4.1.4"])
def test_a_half_scale_placeholder_store_opens_as_saved_with_the_engine_on(
        qapp, store, tag):
    """V6: a v4.1.4 store opened A4, 72 dpi, scale 0.5 with the engine on."""
    _seed(store, use_chromiq_layout_engine=True, chart_paper="Letter",
          **{"manual_printtarg_-i_l": "i1", "manual_printtarg_-p_l": "Letter",
             "manual_engine_recipe": _fixture(tag)})
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert (got["-p"], got["panel_paper"]) == ("Letter", "Letter")
    assert got["dpi"] == 300 and got["instr_margins"]
    assert (got["pscale"], got["sscale"]) == (1.0, 1.0)


def test_the_tick_does_not_carry_the_half_spacer_scale(qapp, store):
    """V8: ticking the engine on beside a v4.1.4 store kept sscale 0.5, and
    a save made it permanent."""
    _seed(store, use_chromiq_layout_engine=False, chart_paper="Letter",
          **{"manual_printtarg_-i_l": "i1", "manual_printtarg_-p_l": "Letter",
             "manual_engine_recipe": _fixture("v4.1.4")})
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        t._manual_engine_check.click()
        qapp.processEvents()
        got = _manual(qapp, t)
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    assert got["sscale"] == 1.0 and got["panel_paper"] == "Letter"
    assert float(store.get("manual_engine_recipe")["sscale"]) == 1.0


# ---------------------------------------------------------------------------
# B8-1295: the one predicate
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("instr,setting,want", [
    ("CR30", False, True), ("CR30", True, True), ("i1", True, True),
    ("i1", False, False), ("p3", False, False), ("isis", True, True),
    ("CM", False, False)])
def test_the_predicate(instr, setting, want):
    assert TC._layout_panel_lays_out(instr, setting) is want


def _cr30_unticked_session(qapp, store):
    _seed(store, use_chromiq_layout_engine=False, chart_instrument="CR30",
          **{"manual_printtarg_-i_l": "CR30"})
    t = _session(qapp, store)
    _manual(qapp, t)
    p = t._manual_layout_panel
    i = p.paper.findData("__custom__")
    p.paper.setCurrentIndex(i)
    p.paper.activated.emit(i)
    p.custom_w.setValue(250)
    p.custom_h.setValue(300)
    qapp.processEvents()
    p.use_instr_margins.setChecked(False)
    for k, v in zip("trbl", (11, 12, 13, 14)):
        p.margins[k].setValue(float(v))
        p.margins[k].editingFinished.emit()
    p.dpi.setValue(400)
    p.helper_markers_cb.setChecked(True)
    qapp.processEvents()
    return t


CR30_WANT = {"-p": "250x300", "panel_paper": "250x300", "dpi": 400,
             "margins": [11.0, 12.0, 13.0, 14.0], "helper": True}


def _sub(got):
    return {k: got[k] for k in CR30_WANT}


def test_the_cr30_with_the_box_unticked_saves_the_panel_on_screen(qapp, store):
    """P10: 300 dpi and 5 mm were stored beside a panel at 400 and 11..14."""
    t = _cr30_unticked_session(qapp, store)
    try:
        got = _manual(qapp, t)
        assert got["shown"] and not t._manual_engine_check.isChecked()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    assert _sub(got) == CR30_WANT
    rec = store.get("manual_engine_recipe")
    assert (int(rec["dpi"]), [float(rec[f"margin_{k}"]) for k in
                              ("top", "right", "bottom", "left")]) == (
        400, [11.0, 12.0, 13.0, 14.0])


def test_and_the_restart_shows_it_printtarg_paper_included(qapp, store):
    """P13 / P8: -p came back A4 beside the panel's 250 x 300."""
    t = _cr30_unticked_session(qapp, store)
    try:
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
        t._on_save_defaults()                 # saved again, untouched
    finally:
        _close(qapp, t)
    assert _sub(got) == CR30_WANT
    assert store.get("manual_printtarg_-p_l") == "250x300"
    assert store.get("manual_engine_recipe")["paper"] == "250x300"


def test_the_tick_on_the_cr30_does_not_replace_the_panel(qapp, store):
    """P3: the tick converted printtarg's hidden rows into the panel."""
    t = _cr30_unticked_session(qapp, store)
    try:
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        t._manual_engine_check.click()
        qapp.processEvents()
        on = _manual(qapp, t)
        t._manual_engine_check.click()
        qapp.processEvents()
        off = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert _sub(on) == CR30_WANT and _sub(off) == CR30_WANT


def test_the_build_takes_the_panel_on_screen(qapp, store):
    """What Generate builds, with the box unticked on the CR30."""
    t = _cr30_unticked_session(qapp, store)
    try:
        p = t._collect_manual()
    finally:
        _close(qapp, t)
    assert p.layout_recipe is not None
    assert (p.instrument, p.paper, p.tiff_dpi) == ("CR30", "250x300", 400)
    assert p.layout_recipe.margin_left == 14.0


def test_an_i1pro_with_the_box_unticked_is_still_printtarg(qapp, store):
    """Control: the predicate moves nothing for an instrument printtarg lays
    out."""
    _seed(store, use_chromiq_layout_engine=False)
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
        p = t._collect_manual()
    finally:
        _close(qapp, t)
    assert not got["shown"] and p.layout_recipe is None


# ---------------------------------------------------------------------------
# B8-1296: the p3 repair only while the panel is what is shown
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("engine,want_i", [(True, "p3"), (False, "i1")])
def test_the_p3_repair_needs_the_panel_on_screen(qapp, store, engine, want_i):
    rec = default_recipe("p3", "A4").to_dict()
    rec.update(dpi=600, helper_markers=True)
    _seed(store, use_chromiq_layout_engine=engine, chart_instrument="p3",
          **{"manual_printtarg_-i_l": "i1", "manual_printtarg_-p_l": "A4",
             "manual_printtarg_-m_l": 10, "manual_printtarg_-a_l": 0.95,
             "manual_engine_recipe": rec})
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
        ma = (int(t._manual_m_pw.get_raw_value()),
              round(float(t._manual_a_pw.get_raw_value()), 2))
    finally:
        _close(qapp, t)
    assert got["-i"] == want_i and ma == (10, 0.95)


# ---------------------------------------------------------------------------
# B8-1297: the tick after a restart shows what was saved
# ---------------------------------------------------------------------------
def test_four_margins_saved_with_the_engine_off_tick_back(qapp, store):
    """P6 / P7: 11 / 12 / 13 / 14 saved, then 10 / 10 / 10 / 10 on the tick."""
    _seed(store, use_chromiq_layout_engine=True)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        p = t._manual_layout_panel
        p.use_instr_margins.setChecked(False)
        for k, v in zip("trbl", (11, 12, 13, 14)):
            p.margins[k].setValue(float(v))
            p.margins[k].editingFinished.emit()
        qapp.processEvents()
        t._manual_engine_check.click()            # off
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    saved = store.get("manual_engine_recipe")
    assert float(saved["margin_left"]) == 14.0
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        t._manual_engine_check.click()            # on, after the restart
        qapp.processEvents()
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert got["margins"] == [11.0, 12.0, 13.0, 14.0]
    assert got["instr_margins"] is False


def test_a_moved_margin_still_collapses_to_minus_m(qapp, store):
    """Control: -m changed after the restart, so the tick takes it."""
    _seed(store, use_chromiq_layout_engine=True)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        p = t._manual_layout_panel
        p.use_instr_margins.setChecked(False)
        for k, v in zip("trbl", (11, 12, 13, 14)):
            p.margins[k].setValue(float(v))
            p.margins[k].editingFinished.emit()
        qapp.processEvents()
        t._manual_engine_check.click()
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        t._manual_m_pw.set_value(7)
        t._manual_m_pw.set_user_enabled(True)
        qapp.processEvents()
        t._manual_engine_check.click()
        qapp.processEvents()
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert got["margins"] == [7.0] * 4


# ---------------------------------------------------------------------------
# B8-1299: a save made in Guided stores what Manual will show
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("engine", [True, False])
def test_a_guided_only_save_comes_back_in_manual_as_the_session_showed(
        qapp, store, engine):
    _seed(store, use_chromiq_layout_engine=engine, chart_mode="guided")
    t = _session(qapp, store)
    try:
        for combo, code in ((t._instr_combo, "CM"), (t._paper_combo, "Letter")):
            i = combo.findData(code)
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            qapp.processEvents()
        t._on_save_defaults()
        session = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert store.get("manual_printtarg_-p_l") == "Letter"
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert (session["-i"], session["-p"]) == ("CM", "Letter")
    assert (got["-i"], got["-p"]) == ("CM", "Letter")
    if engine:
        assert got["panel_paper"] == "Letter"
