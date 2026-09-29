"""B8-1290 to B8-1294: ONE rule for the layout recipe "Save as Defaults" keeps.

Beta 44 challenge round 4 (``~/Desktop/ChromIQ-beta44-proof/challenge-4``)
found beeb6e25's B8-1287 wrong in four ways; the rule that replaces it:

SAVE   the recipe stored is the one the engine would show for what was saved.
       Engine on: the panel as it is (brought to -i / -p if a Guided change
       has not reached it). Engine off: exactly what ticking the engine on
       shows, the panel converted from printtarg's rows
       (`_printtarg_as_engine_recipe`), every engine-only option kept.
READ   the placeholder earlier betas stored for a panel nobody saw (i1Pro,
       A4, 72 dpi, no margins) is no recipe: the panel opens as a clean start
       on the saved instrument and paper does (B8-1290). A real recipe for
       the instrument and paper Manual is on is taken as it is; any other
       keeps its options and takes Manual's instrument and paper (B8-1291),
       judged against the TARGET's -i / -p when a target is opened.
HEAL   a beta-43 store whose -i lost the i1Pro 3 Plus to B8-1288 (recipe p3,
       chart_instrument p3, -i something else) opens on the p3 (B8-1292).
PRESET a changed i1Pro Chart Defaults preset moves only the preset's own
       values, as its help says; a hand-typed -m 5 stays (B8-1293).

The placeholder in tests/data/b8_1290_beta43_placeholder_recipe.json is the
one a026e3e5 wrote on screen (fixes-4/old-stores).

MUTATIONS: ~/Desktop/ChromIQ-beta44-proof/fixes-4/mutations.txt.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog               # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402
from workflow.layout_engine.presets import (                    # noqa: E402
    SUPPORTED_INSTRUMENTS, LayoutRecipe, default_recipe)

PLACEHOLDER = json.loads(
    (Path(__file__).parent / "data" / "b8_1290_beta43_placeholder_recipe.json")
    .read_text(encoding="utf-8"))


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
            "guided_instr": t._instr_combo.currentData(),
            "dpi": r.dpi, "instr_margins": r.use_instrument_margins,
            "helper": r.helper_markers, "text": r.chart_text}


# ---------------------------------------------------------------------------
# (c) the placeholder, recognised by its exact signature, and only it
# ---------------------------------------------------------------------------
def test_the_beta43_placeholder_is_recognised():
    assert TC._is_unseen_panel_recipe(PLACEHOLDER)


def test_it_is_recognised_whatever_the_label_style_preferences():
    """The ten label-style fields are overlaid from Preferences at save."""
    d = dict(PLACEHOLDER, indicator_font="Inter", indicator_size_mm=3.5,
             underline_mode="under", strip_label_offset_mm=1.0)
    assert TC._is_unseen_panel_recipe(d)


def test_it_is_recognised_as_an_ini_store_returns_it():
    """An INI file keeps no types (B8-1282)."""
    d = {k: ("" if v is None else str(v).lower() if isinstance(v, bool)
             else str(v) if isinstance(v, (int, float)) else v)
         for k, v in PLACEHOLDER.items()}
    assert TC._is_unseen_panel_recipe(d)


def test_an_older_beta_without_the_newer_fields_is_recognised():
    d = {k: v for k, v in PLACEHOLDER.items()
         if k not in ("margins_explicit", "align_explicit", "hex_flat_top",
                      "seed_fixed", "layout_explicit")}
    assert TC._is_unseen_panel_recipe(d)


@pytest.mark.parametrize("field,value", [
    ("dpi", 73), ("dpi", 300), ("margin_top", 0.5), ("margin_left", 6.0),
    ("use_instrument_margins", True), ("instrument", "CM"), ("paper", "Letter"),
    ("helper_markers", True), ("chart_text", "x"), ("clip_text", "x"),
    ("clip_border_width_mm", 26.0), ("clip_content_mode", "notes"),
    ("chart_text_font", "Inter"), ("margins_explicit", True),
    ("layout_explicit", True), ("area_ratio", 0.0), ("strip_gap_mm", 1.0),
    ("seed", 1234)])
def test_one_field_a_person_set_makes_it_a_real_recipe(field, value):
    d = dict(PLACEHOLDER)
    d[field] = value
    assert not TC._is_unseen_panel_recipe(d)


def test_a_field_the_placeholder_never_had_makes_it_a_real_recipe():
    assert not TC._is_unseen_panel_recipe(dict(PLACEHOLDER, a_newer_field=1))


@pytest.mark.parametrize("missing", TC._UNSEEN_PANEL_CORE)
def test_the_core_fields_must_be_there(missing):
    d = {k: v for k, v in PLACEHOLDER.items() if k != missing}
    assert not TC._is_unseen_panel_recipe(d)


@pytest.mark.parametrize("instr", SUPPORTED_INSTRUMENTS)
@pytest.mark.parametrize("paper", ["A4", "A4R", "Letter", "LetterR", "A3",
                                   "329x483", "130x180"])
def test_no_factory_layout_is_the_placeholder(instr, paper):
    assert not TC._is_unseen_panel_recipe(default_recipe(instr, paper).to_dict())


def test_no_built_in_preset_is_the_placeholder():
    seen = 0
    for p in TC.KNUT_PRESETS_BY_KEY.values():
        rec = getattr(p, "layout_recipe", None)
        if rec:
            full = LayoutRecipe.from_dict(dict(rec)).to_dict()
            assert not TC._is_unseen_panel_recipe(full), p
            seen += 1
    assert seen > 0


def test_the_nearest_recipe_a_person_can_make_is_not_the_placeholder(
        qapp, store):
    """i1Pro, A4, 72 dpi, instrument margins off, four margins typed 0: the
    panel as a person leaves it, saved, and back after a restart as saved."""
    _seed(store, use_chromiq_layout_engine=True)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        p = t._manual_layout_panel
        p.dpi.setValue(72)
        p.use_instr_margins.setChecked(False)
        for k in "trbl":
            p.margins[k].setValue(0.0)
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    rec = store.get("manual_engine_recipe")
    assert (rec["dpi"], rec["margin_top"], rec["use_instrument_margins"]) == (
        72, 0.0, False)
    assert not TC._is_unseen_panel_recipe(rec)
    t = _session(qapp, store)
    try:
        r = t._manual_layout_panel.get_recipe()
        _manual(qapp, t)
        r = t._manual_layout_panel.get_recipe()
        assert (r.dpi, r.margin_top, r.use_instrument_margins) == (72, 0.0,
                                                                   False)
    finally:
        _close(qapp, t)


# ---------------------------------------------------------------------------
# F1: a beta-43 placeholder store opens as the saved instrument and paper
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("instr,paper", [("i1", "Letter"), ("isis", "329x483"),
                                         ("CM", "A4"), ("i1", "A4")])
def test_a_placeholder_store_opens_on_what_was_saved(qapp, store, instr, paper):
    _seed(store, use_chromiq_layout_engine=True, chart_instrument=instr,
          chart_paper=paper, **{"manual_printtarg_-i_l": instr,
                                "manual_printtarg_-p_l": paper,
                                "manual_engine_recipe": dict(PLACEHOLDER)})
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
        assert got["-p"] == paper
        assert got["panel_paper"] == paper
        assert got["dpi"] == 300 and got["instr_margins"], got
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    rec = store.get("manual_engine_recipe")
    assert rec["paper"] == paper and rec["dpi"] == 300, \
        "saving again kept the placeholder"


# ---------------------------------------------------------------------------
# F2 / (a) / (b): an engine-off save keeps the options, restart == tick
# ---------------------------------------------------------------------------
def test_engine_only_options_survive_an_engine_off_save_on_another_instrument(
        qapp, store):
    _seed(store, use_chromiq_layout_engine=True)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        p = t._manual_layout_panel
        p.helper_markers_cb.setChecked(True)
        p.chart_text.setText("ENGINE NOTE")
        p.chart_text.editingFinished.emit()
        qapp.processEvents()
        t._on_save_defaults()
        t._manual_engine_check.click()            # engine off
        qapp.processEvents()
        t._manual_instr_pw.set_value("CM")
        qapp.processEvents()
        t._on_save_defaults()
        t._manual_engine_check.click()            # ticked on, same session
        qapp.processEvents()
        ticked = t._manual_layout_panel.get_recipe().to_dict()
    finally:
        _close(qapp, t)
    assert ticked["helper_markers"] and ticked["chart_text"] == "ENGINE NOTE"
    t = _session(qapp, store)                     # engine on at the start
    try:
        got = _manual(qapp, t)
        back = t._manual_layout_panel.get_recipe().to_dict()
    finally:
        _close(qapp, t)
    assert got["-i"] == got["panel_instr"] == "CM"
    diff = {k: (ticked[k], back.get(k)) for k in ticked
            if k != "seed" and ticked[k] != back.get(k)}
    assert not diff, f"the restart is not what the session showed: {diff}"


def test_a_beta43_recipe_for_another_instrument_keeps_its_options(qapp, store):
    """C3/C4: the old code kept the i1Pro recipe beside an engine-off -i CM."""
    old = default_recipe("i1", "A4").to_dict()
    old.update(helper_markers=True, chart_text="OLD NOTE")
    _seed(store, use_chromiq_layout_engine=True, chart_instrument="CM",
          **{"manual_printtarg_-i_l": "CM", "manual_printtarg_-p_l": "A4",
             "manual_engine_recipe": old})
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert (got["-i"], got["panel_instr"]) == ("CM", "CM")
    assert got["helper"] and got["text"] == "OLD NOTE"


# ---------------------------------------------------------------------------
# F3: the pre-B8-1288 p3 store
# ---------------------------------------------------------------------------
def _p3_store(s, chart_instrument="p3"):
    rec = default_recipe("p3", "A4").to_dict()
    rec.update(dpi=600, helper_markers=True)
    _seed(s, use_chromiq_layout_engine=True, chart_instrument=chart_instrument,
          **{"manual_printtarg_-i_l": "i1", "manual_printtarg_-p_l": "A4",
             "manual_printtarg_-m_l": 10, "manual_printtarg_-a_l": 0.95,
             "manual_engine_recipe": rec})


def test_the_p3_a_beta43_store_lost_from_minus_i_comes_back(qapp, store):
    _p3_store(store)
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
        ma = (int(t._manual_m_pw.get_raw_value()),
              round(float(t._manual_a_pw.get_raw_value()), 2))
    finally:
        _close(qapp, t)
    assert (got["-i"], got["panel_instr"], got["guided_instr"]) == ("p3",) * 3
    assert got["dpi"] == 600 and got["helper"]
    assert ma == (10, 0.95), "the saved -m / -a moved (B8-1281)"


def test_the_heal_needs_guided_to_say_p3_too(qapp, store):
    """Control: with chart_instrument i1 nothing proves the recipe was on
    screen, so -i stays as saved and the recipe is brought to it."""
    _p3_store(store, chart_instrument="i1")
    t = _session(qapp, store)
    try:
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert (got["-i"], got["panel_instr"]) == ("i1", "i1")
    assert got["helper"] and got["dpi"] == 600, "the recipe's options went"


# ---------------------------------------------------------------------------
# F4: only the preset's own values move
# ---------------------------------------------------------------------------
def test_a_changed_preset_leaves_a_hand_typed_5_on_the_i1pro(qapp, store):
    from unittest import mock
    import ui.main_window as MW
    _seed(store, use_chromiq_layout_engine=False)
    t = _session(qapp, store)
    try:
        _manual(qapp, t)
        t._manual_m_pw.set_value(5)
        t._manual_m_pw.set_user_enabled(True)
        t._manual_a_pw.set_value(0.95)
        t._on_save_defaults()

        class _Dlg:
            def __init__(self, settings, *_a, **_k):
                self._s = settings
                self._tabs = None

            def exec(self):
                self._s.set("i1pro_default_preset", "m10_a1.0")
                return QDialog.DialogCode.Accepted
        win = mock.MagicMock()
        win._settings = store
        win._tab_chart = t
        with mock.patch.object(MW, "SettingsDialog", _Dlg):
            MW.MainWindow._open_settings(win)
        qapp.processEvents()
        live = (int(t._manual_m_pw.get_raw_value()),
                round(float(t._manual_a_pw.get_raw_value()), 2))
    finally:
        _close(qapp, t)
    assert live == (5, 1.0)
    assert int(store.get("manual_printtarg_-m_l")) == 5
    assert float(store.get("manual_printtarg_-a_l")) == pytest.approx(1.0)


def test_a_switch_of_instrument_still_moves_the_cr30s_5():
    """The instrument-switch rule keeps every instrument's own default."""
    assert 5 in TC._house_margins()
    assert 5 not in TC._i1pro_preset_margins()


# ---------------------------------------------------------------------------
# per-target: the saved recipe is judged against the TARGET
# ---------------------------------------------------------------------------
def _defaults_cm_with_markers(qapp, s):
    _seed(s, use_chromiq_layout_engine=True)
    t = _session(qapp, s)
    try:
        _manual(qapp, t)
        p = t._manual_layout_panel
        p.instr.setCurrentIndex(p.instr.findData("CM"))
        qapp.processEvents()
        p.helper_markers_cb.setChecked(True)
        p.chart_text.setText("DEFAULTS CM")
        p.chart_text.editingFinished.emit()
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)


def _target_record(instr, paper, recipe=None):
    rec = {"mode": "manual", "engine_on": True,
           "guided": {"instrument": instr, "paper": paper, "pages": 1,
                      "double_density": False, "triple_density": False,
                      "left_border": False, "no_strip_limit": False,
                      "precond": ""}}
    if recipe is not None:
        rec["engine_recipe"] = recipe
    return rec


@pytest.mark.parametrize("instr,paper", [("CR30", "Letter"), ("CM", "Letter"),
                                         ("SS", "A4")])
@pytest.mark.parametrize("placeholder", [False, True])
def test_a_target_without_a_recipe_keeps_its_instrument_and_paper(
        qapp, store, instr, paper, placeholder):
    _defaults_cm_with_markers(qapp, store)
    t = _session(qapp, store)
    try:
        t._manual_instr_pw.set_value(instr)       # the target's own rows
        t._manual_paper_pw.set_value(paper)
        t._apply_ui_state(_target_record(
            instr, paper, copy.deepcopy(PLACEHOLDER) if placeholder else None))
        qapp.processEvents()
        got = _manual(qapp, t)
    finally:
        _close(qapp, t)
    assert (got["-i"], got["panel_instr"], got["guided_instr"]) == (instr,) * 3
    assert (got["-p"], got["panel_paper"]) == (paper, paper)
    assert got["dpi"] == 300
    assert got["helper"] and got["text"] == "DEFAULTS CM", \
        "the saved defaults' own options did not reach the target (§4 S4)"
