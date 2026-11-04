"""4.3.25, the owner's second round of FD-9 feedback, Manual's layout panel:

* F1: no long FD-9 note box over the panel; "FD-9 on" is a plain flag, not
  the existence of a label;
* F2: EVERY input the FD-9 does not read is greyed, line and text boxes too
  (strip and patch patterns, sheet text), the greyed pattern
  boxes show the FD-9's real patterns, and leaving the FD-9 gives back
  exactly what was there;
* F3: a pattern typed for another instrument does not hold Generate off for
  the FD-9.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import pytest


@pytest.fixture
def panel(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _choose(panel, inst):
    panel.instr.setCurrentIndex(panel.instr.findData(inst))


def test_no_note_box_and_a_plain_flag(panel):
    from PyQt6.QtWidgets import QLabel
    assert panel._fd9_support is True
    assert not hasattr(panel, "fd9_notice")
    _choose(panel, "FD9")
    long_labels = [lb.text() for lb in panel.findChildren(QLabel)
                   if lb.isVisibleTo(panel) and "FD-9" in lb.text()]
    assert long_labels == []


def test_the_flag_is_off_with_the_beta_off(qapp, qtbot):
    from workflow.fd9 import support
    support.set_enabled_for_this_process(False)
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    assert p._fd9_support is False and p.instr.findData("FD9") < 0


def _inputs_in_dead_groups(panel):
    """Every input widget inside a QGroupBox that is not one of the FD-9's
    live groups, found here independently of the panel's own list."""
    from PyQt6.QtWidgets import (QAbstractButton, QAbstractSpinBox,
                                 QComboBox, QGroupBox, QLineEdit,
                                 QPlainTextEdit, QTextEdit)
    from core.i18n import tr
    from ui.tooltip_button import TooltipButton
    live = {tr(t) for t in panel._FD9_LIVE_GROUPS}
    keep = set(map(id, panel._fd9_live_controls()))
    out = []
    for w in panel.findChildren((QAbstractSpinBox, QAbstractButton,
                                 QComboBox, QLineEdit, QPlainTextEdit,
                                 QTextEdit)):
        if isinstance(w, TooltipButton) or id(w) in keep:
            continue
        if isinstance(w, QLineEdit) and isinstance(
                w.parentWidget(), (QAbstractSpinBox, QComboBox)):
            continue
        groups, p = [], w.parentWidget()
        while p is not None and p is not panel:
            if isinstance(p, QGroupBox):
                groups.append(p.title())
            p = p.parentWidget()
        if groups and not any(g in live for g in groups):
            out.append(w)
    return out


def test_every_input_in_a_group_the_fd9_does_not_read_is_greyed(panel):
    from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit
    from ui.dialogs.layout_options_panel import fd9_greyed_reason
    _choose(panel, "FD9")
    dead = _inputs_in_dead_groups(panel)
    kinds = {type(w).__name__ for w in dead}
    assert any(isinstance(w, QLineEdit) for w in dead), kinds
    still = [(type(w).__name__, w.objectName()) for w in dead if w.isEnabled()]
    assert still == []
    for w in dead:
        assert w.toolTip() == fd9_greyed_reason()
    for name in ("strip_pat", "patch_pat", "chart_text", "clip_side",
                 "clip_flip_180"):
        box = getattr(panel, name)
        assert not box.isEnabled(), name
    # What the FD-9 reads stays live: patch size, the gaps, the resolution,
    # and its clip border's switch (F12; its text box follows the switch).
    for c in panel._fd9_live_controls():
        if c is not panel.clip_text:
            assert c.isEnabled(), c.objectName()
    assert isinstance(panel.clip_text, QPlainTextEdit)


def test_the_greyed_boxes_show_the_fd9s_patterns_and_come_back(panel):
    from workflow.layout_engine.permutation import (DEFAULT_PATCH_PATTERN,
                                                    DEFAULT_STRIP_PATTERN)
    _choose(panel, "i1")
    panel.strip_pat.setText("A-H")
    panel.patch_pat.setText("1-9")
    panel.chart_text.setText("my sheet {project}")
    panel.clip_image_path.setText("/tmp/logo.png")
    before = {n: getattr(panel, n).text() for n in
              ("strip_pat", "patch_pat", "chart_text", "clip_image_path")}
    tips = {n: getattr(panel, n).toolTip() for n in before}
    _choose(panel, "FD9")
    assert panel.strip_pat.text() == DEFAULT_STRIP_PATTERN
    assert panel.patch_pat.text() == DEFAULT_PATCH_PATTERN
    assert panel.chart_text.text() == ""
    # The image path is the FD-9 clip border's own (F12), so it is kept.
    assert panel.clip_image_path.text() == "/tmp/logo.png"
    r = panel.get_recipe()
    assert (r.strip_pattern, r.patch_pattern, r.chart_text) == (
        DEFAULT_STRIP_PATTERN, DEFAULT_PATCH_PATTERN, "")
    _choose(panel, "i1")
    assert {n: getattr(panel, n).text() for n in before} == before
    assert {n: getattr(panel, n).isEnabled() for n in before} == dict.fromkeys(
        before, True)
    assert {n: getattr(panel, n).toolTip() for n in before} == tips


def test_a_red_pattern_keeps_its_own_tooltip_round_the_fd9(panel):
    from ui.dialogs.layout_options_panel import fd9_greyed_reason
    _choose(panel, "i1")
    own = panel.strip_pat.toolTip()
    panel.strip_pat.setText("A-Z;1-999")         # ArgyllCMS cannot read it
    reason = panel.strip_pat.toolTip()
    assert reason != own
    _choose(panel, "FD9")
    assert panel.strip_pat.toolTip() == fd9_greyed_reason()
    _choose(panel, "i1")
    assert panel.strip_pat.text() == "A-Z;1-999"
    assert panel.strip_pat.toolTip() == reason
    panel.strip_pat.setText("A-Z, A-Z")
    assert panel.strip_pat.toolTip() == own


def test_the_pattern_gate_ignores_the_fd9(qapp, qtbot, tmp_path, monkeypatch):
    """F3: a pattern ArgyllCMS cannot read, typed while another instrument
    was chosen, does not block Generate Chart for an FD-9 chart; back on the
    i1Pro the same pattern blocks again."""
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    tab._switch_mode("manual")
    p = tab._manual_layout_panel
    _choose(p, "i1")
    p.strip_pat.setText("A-Z;1-999")
    tab._refresh_manual_command_preview()
    assert tab._pattern_problem_now() is not None
    _choose(p, "FD9")
    tab._refresh_manual_command_preview()
    assert tab._pattern_problem_now() is None
    assert tab._pattern_problem is None
    _choose(p, "i1")
    tab._refresh_manual_command_preview()
    assert tab._pattern_problem_now() is not None


def test_the_fd9_clip_border_switch_is_offered_off_and_given_back(panel):
    """F12: the FD-9 has a clip border On/Off like the ColorMunki and the
    CR30, it starts on the FD-9's one default (off), On picks the Notes box
    like the other instruments, the recipe records the answer only when it
    differs from the default, and leaving gives the i1Pro its own back."""
    from workflow.fd9.furniture import FD9_CLIP_BORDER_DEFAULT
    _choose(panel, "i1")
    before = panel.clip_content_mode.currentData()
    _choose(panel, "FD9")
    assert panel.clip_enable.isVisibleTo(panel) and panel.clip_enable.isEnabled()
    assert panel.clip_enabled() is FD9_CLIP_BORDER_DEFAULT is False
    r = panel.get_recipe()
    assert r.fd9_clip_border is None
    assert (r.helper_markers, r.show_strip_indicators) == (False, False)
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("on"))
    assert panel.clip_content_mode.currentData() == "notes"
    assert panel.clip_text.isEnabled() is False      # the Notes box fills itself
    assert not panel.clip_side.isEnabled() and not panel.clip_flip_180.isEnabled()
    assert panel.clip_content_mode.isEnabled()
    r = panel.get_recipe()
    assert r.fd9_clip_border is True and r.clip_content_mode == "notes"
    _choose(panel, "i1")
    assert panel.clip_content_mode.currentData() == before
    panel.set_recipe(r)
    assert panel.instr.currentData() == "FD9" and panel.clip_enabled()


def test_a_recipe_from_before_the_switch_loads_with_the_default(panel):
    from workflow.layout_engine.presets import LayoutRecipe
    old = LayoutRecipe(instrument="FD9", paper="A4", clip_content_mode="notes")
    assert old.fd9_clip_border is None
    panel.set_recipe(old)
    assert panel.clip_enabled() is False


def test_the_fd9_clip_border_field_round_trips_and_stays_out_of_others():
    from workflow.layout_engine.presets import LayoutRecipe
    for value in (True, False):
        r = LayoutRecipe(instrument="FD9", paper="A4", fd9_clip_border=value)
        assert LayoutRecipe.from_dict(r.to_dict()).fd9_clip_border is value
    assert "fd9_clip_border" not in LayoutRecipe(
        instrument="FD9", paper="A4").to_dict()
    assert "fd9_clip_border" not in LayoutRecipe(
        instrument="i1", paper="A4", fd9_clip_border=True).to_dict()
