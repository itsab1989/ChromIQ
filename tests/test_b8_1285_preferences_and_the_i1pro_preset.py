"""B8-1284, B8-1285, B8-1286: Preferences and the i1Pro Chart Defaults preset;
B8-1287: a "Save as Defaults" recipe for another instrument; B8-1288: the
panel's i1Pro 3 Plus reaching printtarg's -i.

THE RULE (beta 44 challenge round 3, findings 1 and 2):

(a) Closing Preferences pushes the i1Pro chart defaults into Manual ONLY when
    the preset was changed and confirmed with OK. Cancel, or OK with nothing
    changed, touches nothing, and no other instrument is ever touched by it.
    It used to call ``_apply_instrument_default_margin()`` on every close, which
    moved any "house" margin or scale a person had typed to the instrument's own
    (B8-1284: 5 of 5 cells on screen, every instrument).
(b) A changed preset applies to both modes now AND after a restart: when the
    saved Manual instrument is the i1Pro, the saved -m / -a are carried to the
    new preset by the same rule the live fields follow (a value that is one of
    the house values moves, a custom one stays). Without it the stored -m / -a
    won at the next start (B8-1280's ``saved=`` rule) while Guided used the
    preset, so the two modes disagreed (B8-1285).
(c) Otherwise B8-1280 / B8-1281 hold: a saved flag comes back as saved.

B8-1287, as corrected by B8-1290 to B8-1292 (beta 44 challenge round 4):
with the engine off, "Save as Defaults" stores what ticking the engine on
would show (the panel converted from printtarg's rows, every engine-only
option kept), so a restart with the engine on shows the session's tick; the
placeholder earlier betas stored is read as no recipe; a recipe for another
instrument or paper keeps its options and takes Manual's instrument and
paper. The rest of that rule is guarded in
tests/test_b8_1290_one_rule_for_the_saved_layout_recipe.py.

MUTATIONS (see ~/Desktop/ChromIQ-beta44-proof/fixes-3/mutations.txt).
"""
from __future__ import annotations

import os
from unittest import mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog               # noqa: E402

from ui.tabs import tab_chart as TC                             # noqa: E402

ACCEPTED = QDialog.DialogCode.Accepted
REJECTED = QDialog.DialogCode.Rejected


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


def _seed(s, instr, engine=False, mode="manual"):
    for k, v in {"chart_instrument": instr, "chart_mode": mode,
                 "manual_printtarg_-i_l": instr,
                 "use_chromiq_layout_engine": engine}.items():
        s.set(k, v)


def _set_ma(t, m, a):
    t._manual_m_pw.set_value(m)
    t._manual_m_pw.set_user_enabled(True)
    t._manual_a_pw.set_value(a)
    t._manual_a_pw.set_user_enabled(True)


def _ma(t):
    return (int(t._manual_m_pw.get_raw_value()),
            round(float(t._manual_a_pw.get_raw_value()), 3))


def _fake_dialog(choose, result):
    """Preferences as far as this rule sees it: OK writes the chosen preset
    (``_save_and_close``), Cancel writes nothing."""
    class _Dlg:
        def __init__(self, settings, *_a, **_k):
            self._s = settings
            self._tabs = None

        def exec(self):
            if result == ACCEPTED and choose is not None:
                self._s.set("i1pro_default_preset", choose)
            return result
    return _Dlg


def _close_preferences(qapp, t, s, choose=None, result=ACCEPTED):
    """MainWindow._open_settings, the real method, on a window that is only a
    Create Chart tab; every other listener is a stand-in."""
    import ui.main_window as MW
    win = mock.MagicMock()
    win._settings = s
    win._tab_chart = t
    with mock.patch.object(MW, "SettingsDialog", _fake_dialog(choose, result)):
        MW.MainWindow._open_settings(win)
    qapp.processEvents()


# (a) -------------------------------------------------------------------------

# the challenge round's table (b8-1284-prefs), its custom pair the control
_B8_1284 = [("CM", 10, 1.0, ACCEPTED), ("CM", 10, 1.0, REJECTED),
            ("CM", 6, 0.95, ACCEPTED), ("i1", 6, 1.0, REJECTED),
            ("i1", 6, 1.0, ACCEPTED), ("isis", 10, 1.0, REJECTED),
            ("SS", 10, 0.95, ACCEPTED), ("p3", 10, 0.95, ACCEPTED),
            ("i1", 12, 0.85, REJECTED), ("i1", 10, 0.95, ACCEPTED)]


@pytest.mark.parametrize("instr,m,a,result", _B8_1284)
def test_closing_preferences_with_nothing_changed_moves_nothing(
        qapp, store, instr, m, a, result):
    _seed(store, instr)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        _set_ma(t, m, a)
        _close_preferences(qapp, t, store, choose=None, result=result)
        assert _ma(t) == (m, a), (
            f"{instr} -m {m} -a {a}: Preferences closed with nothing changed "
            f"moved it to {_ma(t)}")
    finally:
        _close(qapp, t)


def test_a_preset_chosen_and_then_cancelled_moves_nothing(qapp, store):
    _seed(store, "i1")
    t = _session(qapp, store)
    try:
        _set_ma(t, 10, 0.95)
        _close_preferences(qapp, t, store, choose="m6_a1.0", result=REJECTED)
        assert store.get("i1pro_default_preset") == "m10_a0.95"
        assert _ma(t) == (10, 0.95)
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("old,m,a,new,want", [
    ("m10_a0.95", 10, 0.95, "m6_a1.0", (6, 1.0)),   # the preset's own values
    ("m10_a0.95", 10, 0.95, "m10_a1.0", (10, 1.0)),
    ("m6_a1.0", 6, 1.0, "m10_a0.95", (10, 0.95)),
    ("m10_a1.0", 6, 0.95, "m6_a1.0", (6, 1.0)),     # a house value (the help)
    ("m10_a0.95", 12, 0.85, "m6_a1.0", (12, 0.85)),  # a custom pair stays
])
def test_a_changed_preset_reaches_manual_on_the_i1pro(
        qapp, store, old, m, a, new, want):
    _seed(store, "i1")
    store.set("i1pro_default_preset", old)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        _set_ma(t, m, a)
        _close_preferences(qapp, t, store, choose=new, result=ACCEPTED)
        assert _ma(t) == want
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("instr", ["p3", "CM", "SS", "isis"])
def test_a_changed_preset_never_touches_another_instrument(qapp, store, instr):
    _seed(store, instr)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        _set_ma(t, 10, 0.95)
        _close_preferences(qapp, t, store, choose="m6_a1.0", result=ACCEPTED)
        assert _ma(t) == (10, 0.95)
    finally:
        _close(qapp, t)


def test_the_layout_defaults_button_follows_the_same_rule(qapp, store):
    """Create Chart's "Edit layout defaults" opens the same Preferences."""
    import ui.dialogs.settings_dialog as SD
    _seed(store, "i1")
    t = _session(qapp, store)
    try:
        _set_ma(t, 6, 1.0)
        with mock.patch.object(SD, "SettingsDialog",
                               _fake_dialog(None, ACCEPTED)):
            t._edit_layout_defaults()
        assert _ma(t) == (6, 1.0)
        _set_ma(t, 10, 0.95)
        with mock.patch.object(SD, "SettingsDialog",
                               _fake_dialog("m6_a1.0", ACCEPTED)):
            t._edit_layout_defaults()
        assert _ma(t) == (6, 1.0)
    finally:
        _close(qapp, t)


# (b) -------------------------------------------------------------------------

def _save(qapp, s, instr, m, a):
    _seed(s, instr)
    t = _session(qapp, s)
    try:
        t._manual_btn.click()
        _set_ma(t, m, a)
        t._on_save_defaults()
        _close_preferences(qapp, t, s, choose="m6_a1.0", result=ACCEPTED)
        return _ma(t)
    finally:
        _close(qapp, t)


def _restart(qapp, s):
    t = _session(qapp, s)
    try:
        guided = t._collect_guided()
        return _ma(t), t._manual_instr_pw.get_raw_value(), guided
    finally:
        _close(qapp, t)


def test_a_changed_preset_survives_a_saved_session(qapp, store):
    """Finding 1: saved on the preset's values, preset changed, restart."""
    now = _save(qapp, store, "i1", 10, 0.95)
    assert now == (6, 1.0)
    back, instr, guided = _restart(qapp, store)
    assert instr == "i1"
    assert back == (6, 1.0), f"Manual came back {back} after the preset change"
    assert (guided.margin_mm, guided.patch_scale) == (6, 1.0)


def test_a_saved_custom_pair_survives_a_preset_change(qapp, store):
    _save(qapp, store, "i1", 12, 0.85)
    back, _, _ = _restart(qapp, store)
    assert back == (12, 0.85)


@pytest.mark.parametrize("instr", ["p3", "CM", "SS", "isis"])
def test_a_preset_change_leaves_another_instruments_save(qapp, store, instr):
    _save(qapp, store, instr, 10, 0.95)
    back, got, _ = _restart(qapp, store)
    assert (got, back) == (instr, (10, 0.95))


# (c) -------------------------------------------------------------------------

@pytest.mark.parametrize("m,a", [(6, 1.0), (10, 1.0), (6, 0.95)])
def test_without_a_preset_change_a_saved_pair_comes_back_as_saved(
        qapp, store, m, a):
    _seed(store, "i1")
    t = _session(qapp, store)
    try:
        _set_ma(t, m, a)
        t._on_save_defaults()
        _close_preferences(qapp, t, store, choose=None, result=ACCEPTED)
        _close_preferences(qapp, t, store, choose="m6_a1.0", result=REJECTED)
    finally:
        _close(qapp, t)
    back, _, _ = _restart(qapp, store)
    assert back == (m, a)


# B8-1287 ---------------------------------------------------------------------

def _save_engine_off(qapp, s, instr, paper):
    _seed(s, instr, engine=False)
    t = _session(qapp, s)
    try:
        t._manual_btn.click()
        pw = t._manual_paper_pw
        pw._custom_combo.setCurrentIndex(pw._custom_combo.findData(paper))
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    return s.get("manual_engine_recipe")


def _manual_panel(t):
    p = t._manual_layout_panel
    return (t._manual_instr_pw.get_raw_value(),
            t._manual_paper_pw.get_raw_value(),
            p.instr.currentData(), p.selection()[1])


def _engine_tick_in_the_saving_session(qapp, s, instr, paper):
    """Save with the engine off, then tick it on IN THAT SESSION: what the
    person would see. Returns (the stored recipe, the ticked panel's)."""
    _seed(s, instr, engine=False)
    t = _session(qapp, s)
    try:
        t._manual_btn.click()
        pw = t._manual_paper_pw
        pw._custom_combo.setCurrentIndex(pw._custom_combo.findData(paper))
        qapp.processEvents()
        t._on_save_defaults()
        stored = s.get("manual_engine_recipe")
        t._manual_engine_check.click()
        qapp.processEvents()
        ticked = t._manual_layout_panel.get_recipe().to_dict()
    finally:
        _close(qapp, t)
    return stored, ticked


_IGNORED = {"seed"}      # drawn per build, not a layout choice


@pytest.mark.parametrize("instr,paper", [("p3", "A4"), ("CM", "A4"),
                                         ("SS", "A4"), ("i1", "Letter"),
                                         ("CM", "Letter")])
def test_an_engine_off_save_opens_as_saved_with_the_engine_on(
        qapp, store, instr, paper):
    """Save with the engine off, turn it on (the box is stored at once),
    start again: Manual, the panel and -i / -p are the saved instrument and
    paper, and the panel is FIELD FOR FIELD what ticking the engine on in the
    saving session showed (B8-1292), never the 72 dpi placeholder."""
    stored, ticked = _engine_tick_in_the_saving_session(qapp, store, instr,
                                                        paper)
    assert stored is not None and not TC._is_unseen_panel_recipe(stored)
    store.set("use_chromiq_layout_engine", True)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        qapp.processEvents()
        assert _manual_panel(t) == (instr, paper, instr, paper)
        r = t._manual_layout_panel.get_recipe()
        assert r.dpi == 300, "the panel holds the placeholder (72 dpi)"
        back = r.to_dict()
        diff = {k: (ticked.get(k), back.get(k)) for k in ticked
                if k not in _IGNORED and ticked.get(k) != back.get(k)}
        assert not diff, f"the restart is not the session's tick: {diff}"
        t._guided_btn.click()
        qapp.processEvents()
        t._manual_btn.click()
        qapp.processEvents()
        assert _manual_panel(t) == (instr, paper, instr, paper)
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("instr,paper", [("p3", "A4"), ("CM", "Letter")])
def test_an_engine_off_save_then_the_engine_ticked_on(qapp, store, instr,
                                                      paper):
    _save_engine_off(qapp, store, instr, paper)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        qapp.processEvents()
        t._manual_engine_check.click()
        qapp.processEvents()
        assert _manual_panel(t) == (instr, paper, instr, paper)
    finally:
        _close(qapp, t)


def test_a_recipe_for_the_saved_instrument_is_still_restored(qapp, store):
    """B8-1228's rule is untouched: an engine-on save comes back verbatim,
    a knob only the recipe carries included."""
    _seed(store, "CM", engine=True)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        qapp.processEvents()
        p = t._manual_layout_panel
        p.instr.setCurrentIndex(p.instr.findData("CM"))
        qapp.processEvents()
        from dataclasses import replace
        r = replace(p.get_recipe(), border=9.5)
        t._set_engine_recipe(r)
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    assert store.get("manual_engine_recipe")["border"] == pytest.approx(9.5)
    t2 = _session(qapp, store)
    try:
        t2._manual_btn.click()
        qapp.processEvents()
        assert t2._manual_layout_panel.get_recipe().border == pytest.approx(9.5)
        assert _manual_panel(t2)[0] == _manual_panel(t2)[2] == "CM"
    finally:
        _close(qapp, t2)


@pytest.mark.parametrize("recipe,manual,paper,fits", [
    ({"instrument": "i1", "paper": "A4"}, "i1", "A4", True),
    ({"instrument": "i1", "paper": "A4"}, "CM", "A4", False),
    ({"instrument": "i1", "paper": "A4"}, "i1", "Letter", False),
    ({"instrument": "p3", "paper": "A4"}, "p3", "A4", True),
    ({"instrument": "p3", "paper": "A4"}, "3p", "A4", True),
    ({"instrument": "CM", "paper": "A4"}, "SS", "A4", False),
    ({}, "CM", "Letter", True),
    # the i1iSis has no engine layout; the panel shows the i1Pro for it
    # (B8-1283, open), so an i1Pro recipe beside it is not a mismatch here
    ({"instrument": "i1", "paper": "329x483"}, "isis", "329x483", True)])
def test_which_recipe_is_for_what_manual_is_on(recipe, manual, paper, fits):
    assert TC._recipe_is_for(recipe, manual, paper) is fits


@pytest.mark.parametrize("instr", ["p3", "CM", "SS", "i1"])
def test_an_engine_off_save_stores_no_recipe_nobody_saw(qapp, store, instr):
    """The hidden panel, never shown, is not stored as it stood (B8-1287):
    what is stored is for the saved instrument and paper, at their
    resolution, not the 72 dpi placeholder (B8-1290)."""
    _seed(store, instr, engine=False)
    t = _session(qapp, store)
    try:
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    rec = store.get("manual_engine_recipe")
    assert not TC._is_unseen_panel_recipe(rec)
    assert (rec["instrument"], rec["paper"], rec["dpi"]) == (instr, "A4", 300)


def test_an_engine_off_save_keeps_what_the_engine_save_set(qapp, store):
    """An engine save's own options survive a later engine-off save on
    another instrument (B8-1291: beeb6e25 deleted the recipe)."""
    _seed(store, "CM", engine=True)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        qapp.processEvents()
        p = t._manual_layout_panel
        p.helper_markers_cb.setChecked(True)
        p.chart_text.setText("KEPT")
        p.chart_text.editingFinished.emit()
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    store.set("use_chromiq_layout_engine", False)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        t._manual_instr_pw.set_value("SS")
        qapp.processEvents()
        t._on_save_defaults()
    finally:
        _close(qapp, t)
    rec = store.get("manual_engine_recipe")
    assert rec["instrument"] == "SS"
    assert rec["helper_markers"] is True and rec["chart_text"] == "KEPT"


@pytest.mark.parametrize("code", ["p3", "CM", "SS", "CR30", "i1"])
def test_the_panels_instrument_reaches_printtarg(qapp, store, code):
    """B8-1288: the panel's i1Pro 3 Plus was mirrored as "3p", which -i does
    not offer, so -i stayed on the instrument before."""
    _seed(store, "i1", engine=True)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        qapp.processEvents()
        c = t._manual_layout_panel.instr
        c.setCurrentIndex(c.findData(code))
        qapp.processEvents()
        assert t._manual_instr_pw.get_raw_value() == code
    finally:
        _close(qapp, t)


@pytest.mark.parametrize("instr,paper", [("p3", "A4"), ("CM", "Letter"),
                                         ("SS", "A4")])
def test_a_store_written_before_the_fix_opens_on_its_instrument(
        qapp, store, instr, paper):
    """What earlier betas stored, and what stores out there hold now: the
    hidden panel's i1Pro / A4 / 72 dpi recipe beside another instrument. It
    is not restored: the panel opens on that instrument's layout preset and
    the saved paper is kept."""
    placeholder = {"instrument": "i1", "paper": "A4", "dpi": 72,
                   "use_instrument_margins": False, "margin_top": 0.0,
                   "margin_left": 0.0, "margin_right": 0.0,
                   "margin_bottom": 0.0}
    _seed(store, instr, engine=True)
    store.set("chart_paper", paper)
    store.set("manual_printtarg_-p_l", paper)
    store.set("manual_engine_recipe", placeholder)
    t = _session(qapp, store)
    try:
        t._manual_btn.click()
        qapp.processEvents()
        assert _manual_panel(t) == (instr, paper, instr, paper)
        r = t._manual_layout_panel.get_recipe()
        assert r.dpi == 300 and r.use_instrument_margins
    finally:
        _close(qapp, t)
