"""Beta 8 fixes from Knut's beta 7 testing (#182).

1. 5973222284: ⌘Q did not quit ChromIQ. Quit now has its own binding (⌘Q on
   macOS, Ctrl+Q elsewhere, plus Alt+F4 on Windows), listed on the keyboard
   card per platform, and it goes through the window's close.
2. 5973449121: ChromIQ once could not be closed, and the log said nothing.
   Every way out of `closeEvent` now writes a line, a failing step can no
   longer keep the window open, and a modal window is named as it opens (a
   click on the close button behind one is dropped by Qt itself).
3. 5973177088: Profile Description in Guided and Manual are one value, and
   emptying either always gives the automatic name back.
4. 5971383600: the Calibration complete window at the START of a resumed
   measurement lists every key, the same list as the window after K.
5. 5969949735: "No instrument found" says only what is true when no
   instrument is connected at all.
"""
from __future__ import annotations

import inspect
import logging
import sys

import pytest


# ---- 1. the quit shortcut ---------------------------------------------------
def test_quit_has_one_binding_in_the_registry():
    from ui.keyboard_help import BINDINGS
    assert BINDINGS["quit"] == "Ctrl+Q"          # ⌘Q on macOS, Ctrl+Q elsewhere


@pytest.mark.parametrize("plat", ["darwin", "win32", "linux"])
def test_the_card_names_quit_in_each_platforms_words(qapp, plat):
    from ui.keyboard_help import keys_for, quit_keys
    got = quit_keys(plat)
    assert keys_for("quit") in got
    if plat == "win32":
        assert "F4" in got, "Windows' own Alt+F4 is missing from the card"
    else:
        assert "F4" not in got


def test_the_card_and_the_printed_card_list_quit(qapp):
    from ui import help_card_print
    from ui.keyboard_help import keyboard_shortcuts_html, quit_keys
    html = keyboard_shortcuts_html()
    assert "Quit ChromIQ" in html and quit_keys() in html
    # The printed card is built from the same HTML (no second copy to drift).
    assert "keyboard_shortcuts_html()" in inspect.getsource(help_card_print)


@pytest.fixture
def win(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("restore_last_session", False)
    s.set("show_welcome_dialog", False)
    w = MainWindow(s)
    yield w
    w._closing = True               # do not run the real close-down twice
    w.deleteLater()


def test_the_window_owns_an_application_wide_quit_action(win):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QKeySequence
    act = win._quit_action
    assert act in win.actions()
    assert act.shortcut() == QKeySequence("Ctrl+Q")
    assert act.shortcutContext() == Qt.ShortcutContext.ApplicationShortcut


def test_quitting_asks_every_window_to_close(win, qapp, monkeypatch):
    """The same door as the app menu's Quit: closeAllWindows, which closes
    an open modal window first and then the main window via closeEvent."""
    from PyQt6.QtWidgets import QApplication
    calls = []
    monkeypatch.setattr(QApplication, "closeAllWindows",
                        staticmethod(lambda: calls.append(1)))
    win._quit_action.trigger()
    qapp.processEvents()
    assert calls == [1]


# ---- 2. a close always closes, and always says so ---------------------------
def _close(win):
    from PyQt6.QtGui import QCloseEvent
    ev = QCloseEvent()
    win.closeEvent(ev)
    return ev


def test_a_close_cancelled_by_the_measurement_is_logged(win, monkeypatch, caplog):
    monkeypatch.setattr(win, "_ask_before_quitting_on_a_measurement",
                        lambda: False)
    with caplog.at_level(logging.INFO, logger="ui.main_window"):
        ev = _close(win)
    assert not ev.isAccepted()
    assert win._closing is False, "a refused close must not block the next one"
    assert "close cancelled" in caplog.text


def test_a_broken_quit_question_does_not_trap_the_user(win, monkeypatch):
    def boom():
        raise RuntimeError("guard failed")
    monkeypatch.setattr(win, "_ask_before_quitting_on_a_measurement", boom)
    monkeypatch.setattr(win, "_close_down", lambda ev: ev.accept())
    assert _close(win).isAccepted()


def test_a_failing_close_down_step_still_closes(win, monkeypatch, caplog):
    monkeypatch.setattr(win, "_ask_before_quitting_on_a_measurement",
                        lambda: True)

    def boom(ev):
        raise RuntimeError("shutdown step failed")
    monkeypatch.setattr(win, "_close_down", boom)
    with caplog.at_level(logging.INFO, logger="ui.main_window"):
        ev = _close(win)
    assert ev.isAccepted()
    assert "closing anyway" in caplog.text


def test_a_second_close_while_closing_is_logged(win, caplog):
    win._closing = True
    with caplog.at_level(logging.INFO, logger="ui.main_window"):
        ev = _close(win)
    assert not ev.isAccepted()
    assert "already closing" in caplog.text


def test_a_modal_window_is_named_in_the_log(qapp, caplog):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtWidgets import QDialog
    from ui.widgets import DialogFocusFilter
    dlg = QDialog()
    dlg.setWindowTitle("Some question")
    dlg.setModal(True)
    with caplog.at_level(logging.INFO, logger="ui.widgets"):
        DialogFocusFilter().eventFilter(dlg, QEvent(QEvent.Type.Show))
    assert "modal window shown" in caplog.text and "Some question" in caplog.text
    dlg.deleteLater()


# ---- 3. Guided and Manual share Profile Description -------------------------
@pytest.fixture
def ptab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_profile import TabProfile

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            return super().get(key, default)

    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("Desc-Project")
    project = fm.project()
    ctl = MeasurementTargetController(fm)
    widget = TabProfile(ArgyllRunner(st), st, None)
    widget.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    run = project.run("run1")
    meta = run.load_meta()
    meta.description = "gloss"
    run.save_meta(meta)
    widget._apply_profile_description_default()
    yield widget, run
    widget.deleteLater()


def _type(edit, text):
    edit.setText(text)
    edit.textEdited.emit(text)


def test_guided_and_manual_show_one_description(ptab):
    w, _run = ptab
    _type(w._desc_edit, "My Own Name")
    assert w._m_desc_edit.text() == "My Own Name"
    _type(w._m_desc_edit, "Another")
    assert w._desc_edit.text() == "Another"


def test_emptying_guided_gives_both_the_default(ptab):
    """Knut: delete in Guided, the default came back there and not in Manual."""
    w, run = ptab
    _type(w._desc_edit, "My Own Name")
    _type(w._desc_edit, "")
    assert w._desc_edit.text() == "Desc-Project-gloss"
    assert w._m_desc_edit.text() == "Desc-Project-gloss"
    assert run.load_meta().profile_description == ""


def test_emptying_manual_when_nothing_was_stored_gives_the_default(ptab):
    """Knut: deleting in Manual did not restore the default, because the run
    had no override stored and the code returned before refilling."""
    w, run = ptab
    assert run.load_meta().profile_description == ""
    _type(w._m_desc_edit, "")
    assert w._m_desc_edit.text() == "Desc-Project-gloss"
    assert w._desc_edit.text() == "Desc-Project-gloss"


def test_the_header_tags_are_shared_too(ptab):
    w, _run = ptab
    w._mfr_check.setChecked(True)
    w._mfr_edit.setText("Epson")
    assert w._m_mfr_check.isChecked() and w._m_mfr_edit.text() == "Epson"
    w._m_copy_edit.setText("(c) me")
    assert w._copy_edit.text() == "(c) me"


def _store_profile_settings(w, run, drop=(), **over):
    """Write a target's stored Build Profile settings as a pre-beta-8 build
    could have left them: Guided and Manual header fields independent."""
    data = {**w._m_collect_preset_data(), **w._collect_guided_profile_fields()}
    data.update(over)
    for k in drop:
        data.pop(k, None)
    meta = run.load_meta()
    meta.profile_settings = data
    run.save_meta(meta)


def test_a_manual_header_tag_stored_alone_survives_the_load(ptab):
    """Review of beta 8: Manual's stored copyright must not be wiped by an
    empty Guided one that is applied after it (and then saved over it)."""
    w, run = ptab
    _store_profile_settings(w, run, copy_enabled=True, copy="(c) Manual",
                            g_copy_enabled=False, g_copy="")
    assert w.load_target_settings()
    assert w._m_copy_check.isChecked() and w._m_copy_edit.text() == "(c) Manual"
    assert w._copy_check.isChecked() and w._copy_edit.text() == "(c) Manual"


def test_a_guided_header_tag_stored_alone_survives_the_load(ptab):
    w, run = ptab
    _store_profile_settings(w, run, mfr_enabled=False, mfr="",
                            g_mfr_enabled=True, g_mfr="Epson")
    assert w.load_target_settings()
    assert w._m_mfr_edit.text() == "Epson" and w._mfr_edit.text() == "Epson"
    assert w._m_mfr_check.isChecked() and w._mfr_check.isChecked()


def test_a_store_without_guided_keys_takes_manuals_value(ptab):
    """A store older than Guided's own keys leaves Guided showing whatever
    was on screen before; that must not override Manual's stored value."""
    w, run = ptab
    w._model_check.setChecked(True)
    w._model_edit.setText("left over from another target")
    _store_profile_settings(w, run, drop=("g_model", "g_model_enabled"),
                            model_enabled=True, model="P900")
    assert w.load_target_settings()
    assert w._model_edit.text() == "P900" and w._m_model_edit.text() == "P900"


def test_typing_after_a_load_is_mirrored_again(ptab):
    w, run = ptab
    _store_profile_settings(w, run, copy="(c) A", g_copy="(c) B")
    assert w.load_target_settings()
    w._m_copy_edit.setText("(c) typed")
    assert w._copy_edit.text() == "(c) typed"


# ---- 4. the Calibration complete window at the start ------------------------
@pytest.fixture
def mtab(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    st = AppSettings()
    t = TabMeasure(ArgyllRunner(st), st)
    t._manager._engine_active = True
    yield t
    t.deleteLater()


def _labels(dlg):
    from PyQt6.QtWidgets import QLabel
    return [lb.text() for lb in dlg.findChildren(QLabel)]


@pytest.mark.parametrize("engine", [True, False])
def test_the_resume_window_lists_the_same_keys_as_the_k_window(mtab, monkeypatch,
                                                                engine):
    got = {}
    monkeypatch.setattr(mtab, "_exec_measurement_window",
                        lambda dlg: got.setdefault("dlg", dlg))
    mtab._manager._engine_active = engine
    mtab._spot_session = False
    mtab._guided_refinement_active = False
    mtab._resume_active = True
    mtab._on_calibration_done()
    labels = _labels(got["dlg"])
    for key, desc in mtab._strip_key_rows():
        assert key in labels and desc in labels, (key, desc)
    assert ("K" in labels) is engine
    # The two loose dim lines are gone.
    assert not any("jumps to the next unread strip" in t for t in labels)
    assert not any(t.startswith("K: calibrate") for t in labels)
    assert got["dlg"].findChild(object, "calibration_key_list") is not None


def test_the_k_window_and_the_start_window_agree(mtab, monkeypatch):
    got = []
    monkeypatch.setattr(mtab, "_exec_measurement_window", got.append)
    mtab._spot_session = False
    mtab._guided_refinement_active = False
    mtab._resume_active = True
    mtab._on_calibration_done()
    mtab._show_requested_calibration_done()
    start, after_k = (set(_labels(d)) for d in got)
    keys = {k for k, _ in mtab._strip_key_rows()}
    assert keys <= start and keys <= after_k


# ---- 5. no instrument connected at all ---------------------------------------
def test_the_none_variant_says_nothing_untrue():
    from workflow import measurement_messages as M
    title, body = M.M_NO_INSTRUMENT_NONE.render()
    assert "replied" not in body and "Faster" not in body
    assert "—" not in title + body
    assert "Start again" in body
    # approved by Knut, #182 5979780372 ("all are ok")
    assert M.CATALOGUE["M-NO-INSTRUMENT-NONE"].approved


def test_a_refused_start_records_the_port(qapp, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from core import instrument_port
    from workflow.measure_manager import MeasureManager
    monkeypatch.setattr(instrument_port, "refused_port",
                        lambda tool, args: "/dev/cu.Bluetooth-Incoming-Port")
    m = MeasureManager(ArgyllRunner(AppSettings()))
    assert m._refuse_system_port("chartread", ["-c1"], lambda c: None) is True
    assert m.start_refused_port == "/dev/cu.Bluetooth-Incoming-Port"


@pytest.mark.parametrize("refused,fast,expected", [
    ("/dev/cu.Bluetooth-Incoming-Port", True, "M-NO-INSTRUMENT-NONE"),
    ("/dev/cu.Bluetooth-Incoming-Port", False, "M-NO-INSTRUMENT-NONE"),
    (None, True, "M-NO-INSTRUMENT-FAST"),
    (None, False, "M-NO-INSTRUMENT"),
])
def test_the_window_picks_its_text(mtab, monkeypatch, refused, fast, expected):
    from workflow import measurement_messages as M
    shown = {}
    monkeypatch.setattr(mtab, "_exec_measurement_window",
                        lambda box: shown.setdefault("box", box))
    monkeypatch.setattr(mtab, "_cue_window", lambda *_: None)
    mtab._manager.start_refused_port = refused
    mtab._settings.set("fast_instrument_connect", fast)
    mtab._no_instrument_shown = False
    mtab._show_no_instrument_window()
    box = shown["box"]
    want_title, want_body = M.CATALOGUE[expected].render(
        n=mtab._NO_INSTRUMENT_DELAY_S)
    assert box.text() == want_title          # (macOS ignores a box title)
    assert box.informativeText() == want_body
    has_switch = any("faster" in b.text().lower() for b in box.buttons())
    assert has_switch is (expected == "M-NO-INSTRUMENT-FAST")


# ---- 6. -K needs Apply Calibration afterwards, -I must not have it ----------
def test_the_calibration_help_tells_k_users_to_apply_the_calibration():
    """ArgyllCMS doc/Scenarios.html: with printtarg -K "colprof does NOT apply
    the calibration curves to the resulting ICC profile"; a printer that
    cannot calibrate gets them through applycal. The help said the opposite:
    no Apply Calibration "if you baked it into the patch values"."""
    from ui.tabs import tab_profile
    body = tab_profile._TOOLTIP_BODY_CAL
    assert "baked it into the patch values" not in body
    step6 = body[body.index("6. APPLY THE CALIBRATION"):]
    k = step6[step6.index("You chose -K"):step6.index("You chose -I")]
    i = step6[step6.index("You chose -I"):]
    assert "click Apply Calibration" in k
    assert "do NOT click Apply Calibration" in i
    assert "—" not in body


def test_the_k_and_i_tooltips_say_what_to_do_after_the_build():
    import yaml
    from pathlib import Path
    data = yaml.safe_load((Path(__file__).resolve().parent.parent / "data" /
                           "parameters.yaml").read_text(encoding="utf-8"))
    flat = {}

    def walk(o):
        if isinstance(o, dict):
            if o.get("flag") in ("-K", "-I") and "tooltip_body" in o \
                    and "Calibration" in str(o.get("name", "")):
                flat[o["flag"]] = o["tooltip_body"]
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    assert "click Apply Calibration" in flat["-K"]
    assert "Do not click Apply Calibration" in flat["-I"]
    assert "colprof\n        can reference it" not in flat["-K"]


def test_the_after_build_windows_say_when_to_apply(qapp):
    from ui.tabs import tab_profile
    src = inspect.getsource(tab_profile)
    assert "colprof will reference the .cal when building the profile" not in src
    assert "Do NOT do it when the chart was made with" in src


@pytest.mark.parametrize("which", ["_desc_edit", "_m_desc_edit"])
def test_emptying_by_real_key_presses_gives_both_the_default(ptab, which):
    """Typed, not set: Qt sends `textEdited` before that edit's `textChanged`,
    and copying the stale `textChanged("")` across emptied both fields again
    (found on screen, beta 8)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    w, _run = ptab
    edit = getattr(w, which)
    edit.selectAll()
    QTest.keyClicks(edit, "Mine")
    assert w._desc_edit.text() == w._m_desc_edit.text() == "Mine"
    edit.selectAll()
    QTest.keyClick(edit, Qt.Key.Key_Backspace)
    assert w._desc_edit.text() == "Desc-Project-gloss"
    assert w._m_desc_edit.text() == "Desc-Project-gloss"


# ---- 7. randomisation is greyed for a calibration chart ---------------------
def test_the_randomise_box_is_greyed_for_calibration_and_keeps_its_tick(qapp):
    """Forum (ajaytanna, beta 7): "Randomise" looked live with Run type
    Calibration, but a calibration chart is always laid out in order
    (calibration_run_type.md §4.2). Greyed, with the reason as its tooltip; the tick is the
    profiling runs' own and is never changed."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    p.randomize_cb.setChecked(True)
    p.fixed_seed_cb.setChecked(True)
    p.set_order_locked(True)
    assert not p.randomize_cb.isEnabled()
    assert not p.fixed_seed_cb.isEnabled() and not p.seed_spin.isEnabled()
    assert "always printed in order" in p.randomize_cb.toolTip()
    assert p.randomize_cb.isChecked() and p.fixed_seed_cb.isChecked()
    assert p.get_recipe().randomize is True, "the stored setting changed"
    p.set_order_locked(False)
    assert p.randomize_cb.isEnabled() and p.fixed_seed_cb.isEnabled()
    assert p.randomize_cb.toolTip() == ""
    p.deleteLater()


def test_the_chart_tab_locks_both_order_controls(qapp):
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QWidget
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.tabs.tab_chart import TabChart
    panel = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    row = QWidget()
    row.flag = "-r"
    state = {"cal": True}
    fake = SimpleNamespace(_calibration_selected=lambda: state["cal"],
                           _manual_layout_panel=panel,
                           _manual_widgets={"printtarg": [row]})
    TabChart._sync_order_lock(fake)
    assert not panel.randomize_cb.isEnabled() and not row.isEnabled()
    state["cal"] = False
    TabChart._sync_order_lock(fake)
    assert panel.randomize_cb.isEnabled() and row.isEnabled()
    panel.deleteLater()
    row.deleteLater()


def test_the_lock_follows_the_run_type():
    from ui.tabs import tab_chart
    assert "controller.changed.connect(self._sync_order_lock)" in \
        inspect.getsource(tab_chart.TabChart)
