"""4.3.26, review round 1: the FD-9 clip border follows a person's answer,
in Manual and in Guided, and nothing else.

M1. Guided has no clip-border setting for the FD-9, so (the owner's ruling)
    it always follows the FD-9's default, on with the Notes box, as Guided
    does for every other instrument: a Manual Off saved with Save as Defaults
    is Manual's. Manual's Save as Defaults now really stores the FD-9 recipe
    (it was retargeted to the i1Pro), so Manual keeps its Off.
M2. Manual's panel stored an explicit Off whenever it merely SHOWED the FD-9
    with the content "off" (part way through a load, or because choosing the
    FD-9 set the content and that change was taken for a person's answer),
    and loading that recipe marked it chosen for good. Only a person's
    answer is stored now, and a panel entering the FD-9 without one shows
    the default, so the panel and the build agree.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import pytest

from tests.test_fd9_4324_own_layout_values import _build, _tab


@pytest.fixture(autouse=True)
def _own_presets(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))


def _second_tab(settings, qtbot):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    qtbot.addWidget(tab)
    return tab


def _guided_fd9(tab):
    tab._user_switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("FD9"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    return tab._collect_guided()


def test_m1_guided_follows_the_default_and_has_the_clip_border(
        qapp, qtbot, tmp_path):
    tab, _ = _tab(tmp_path, qtbot)
    p = _guided_fd9(tab)
    kw = tab._creator._engine_kwargs(p)
    assert kw["fd9_clip_border"] in (None, True)
    assert kw.get("clip_content_mode", "notes") == "notes"
    layout = _build(tmp_path, tab._creator, p, "guided_default")
    assert "clip_border_mm" in layout


def test_m1_a_manual_off_saved_as_defaults_stays_manuals(
        qapp, qtbot, tmp_path):
    tab, settings = _tab(tmp_path, qtbot)
    tab._user_switch_mode("manual")
    if not tab._manual_panel_inited:         # as showing Manual's panel does
        tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel
    for combo, data in ((panel.instr, "FD9"), (panel.paper, "A4")):
        combo.setCurrentIndex(combo.findData(data))
    tab._refresh_manual_command_preview()    # the panel's choice into -i
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("off"))
    assert panel.get_recipe().fd9_clip_border is False
    tab._on_save_defaults()
    saved = settings.get("manual_engine_recipe")
    # Stored as the FD-9's recipe, with the answer (it was retargeted to
    # the i1Pro before, and the Off was lost).
    assert saved.get("instrument") == "FD9"
    assert saved.get("fd9_clip_border") is False

    # Manual, in a new window from the saved defaults: still Off.
    t2 = _second_tab(settings, qtbot)
    t2._user_switch_mode("manual")
    if not t2._manual_panel_inited:
        t2._init_manual_layout_panel()
    assert t2._manual_layout_panel.get_recipe().fd9_clip_border is False

    # Guided, in either window: the FD-9's default, with the Notes box.
    for t in (tab, t2):
        p = _guided_fd9(t)
        kw = t._creator._engine_kwargs(p)
        assert kw["fd9_clip_border"] is True
        assert kw["clip_content_mode"] == "notes"
        layout = _build(tmp_path, t._creator, p, f"guided_{id(t)}")
        assert "clip_border_mm" in layout


def test_m1_guided_ignores_a_loaded_fd9_layouts_clip_border(
        qapp, qtbot, tmp_path):
    from workflow.layout_engine.presets import default_recipe
    tab, _ = _tab(tmp_path, qtbot)
    r = default_recipe("FD9", "A4")
    r.fd9_clip_border = False
    tab._fd9_remember_guided(r)
    p = _guided_fd9(tab)
    assert tab._creator._engine_kwargs(p)["fd9_clip_border"] is True


def test_m2_entering_the_fd9_is_not_an_answer(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    panel.set_clip_enabled(False)          # the i1Pro showed Off
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    assert panel.clip_enabled() is True    # the FD-9's default, shown
    assert panel._fd9_clip_chosen is False
    assert panel.get_recipe().fd9_clip_border is None


def test_m2_a_panel_showing_off_mid_load_stores_no_answer(qapp, qtbot):
    """get_recipe asked while the panel shows the FD-9 with content "off"
    and nobody has answered (as part way through a load) stores None, and
    loading that recipe neither marks it chosen nor shows Off."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    was = panel._loading
    panel._loading = True                   # as inside set_recipe
    try:
        panel.set_clip_enabled(False)
    finally:
        panel._loading = was
    assert panel._fd9_clip_chosen is False
    r = panel.get_recipe()
    assert r.fd9_clip_border is None
    panel.set_recipe(r)
    assert panel._fd9_clip_chosen is False and panel.clip_enabled() is True


def test_m2_a_persons_off_is_still_stored_and_kept(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("FD9"))
    panel.clip_enable.setCurrentIndex(panel.clip_enable.findData("off"))
    r = panel.get_recipe()
    assert r.fd9_clip_border is False
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    panel.set_recipe(r)
    assert panel.clip_enabled() is False and panel._fd9_clip_chosen is True
