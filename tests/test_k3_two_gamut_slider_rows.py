"""K3 (Knut 2026-10-20; built as Basti approved, 2026-10-21): the gamut panel's
Combined view has ONE row of sliders per profile, under the PROFILE A /
COMBINED / PROFILE B buttons:

    A  Opacity [slider] 100 %   Sat. [slider] 100 %
    B  Opacity [slider]  50 %   Sat. [slider] 100 %

The old single row acted on profile B only, so a B inside an opaque A stayed
hidden whatever it was set to. A starts at 100 % and is not touched on the
page until it is moved; B keeps its old defaults.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def panel(qtbot):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.gamut_panel import GamutPanel
    st = AppSettings()
    p = GamutPanel(ArgyllRunner(st), st, None)
    qtbot.addWidget(p)
    return p


class _Page:
    def __init__(self):
        self.js = []

    def runJavaScript(self, js, *a):
        self.js.append(js)


class _View:
    def __init__(self):
        self._page = _Page()

    def page(self):
        return self._page


def test_two_rows_with_their_defaults(panel):
    assert panel._a_opacity_slider.value() == 100
    assert panel._a_sat_slider.value() == 100
    assert panel._opacity_slider.value() == 50
    assert panel._sat_slider.value() == 100
    assert panel._a_letter.text() == "A" and panel._b_letter.text() == "B"
    assert panel._a_opacity_label.text() == "100%"
    assert panel._opacity_label.text() == "50%"


def test_the_rows_sit_under_the_buttons(panel, qtbot):
    panel.resize(640, 700)
    panel.show()
    panel._view_toggle_row.setVisible(True)
    panel._compare_controls.setVisible(True)
    qtbot.waitExposed(panel)
    btn = panel._view_combined_btn
    btn_bottom = btn.mapTo(panel, btn.rect().bottomLeft()).y()
    a_top = panel._a_opacity_slider.mapTo(panel, panel._a_opacity_slider.rect().topLeft()).y()
    b_top = panel._opacity_slider.mapTo(panel, panel._opacity_slider.rect().topLeft()).y()
    assert btn_bottom < a_top < b_top


def test_the_rows_belong_to_the_combined_view(panel, monkeypatch):
    monkeypatch.setattr(panel, "_load_html", lambda *_a: None)
    panel._on_view_primary()
    assert panel._compare_controls.isHidden()
    panel._on_view_combined()
    assert not panel._compare_controls.isHidden()
    panel._on_view_compare()
    assert panel._compare_controls.isHidden()


def test_moving_a_drives_profile_a_on_the_page(panel):
    view = _View()
    panel._web_view = view
    panel._view_combined_btn.setChecked(True)
    panel._a_opacity_slider.setValue(30)
    js = view.page().js[-1]
    assert "window._chromiqPrimaryOpacity=0.70" in js
    assert "window._chromiqPrimarySat=1.00" in js and "_chromiqApplyPrimary()" in js
    panel._a_sat_slider.setValue(0)
    assert "window._chromiqPrimarySat=0.00" in view.page().js[-1]
    assert panel._a_opacity_label.text() == "30%"
    # B still drives the compare gamut, and only it.
    panel._opacity_slider.setValue(80)
    assert "_chromiqCompareOpacity=0.20" in view.page().js[-1]
    assert "_chromiqPrimary" not in view.page().js[-1]
    panel._web_view = None


def test_an_untouched_a_leaves_the_page_as_it_was(panel):
    view = _View()
    panel._web_view = view
    panel._view_combined_btn.setChecked(True)
    panel._on_page_loaded(True)
    assert not any("_chromiqPrimary" in j for j in view.page().js)
    panel._a_opacity_slider.blockSignals(True)
    panel._a_opacity_slider.setValue(40)
    panel._a_opacity_slider.blockSignals(False)
    view.page().js.clear()
    panel._on_page_loaded(True)        # a reloaded scene gets A's look back
    assert any("_chromiqPrimaryOpacity=0.60" in j for j in view.page().js)
    panel._web_view = None


def test_the_letters_carry_each_profile_s_colour(panel):
    for mode in ("light", "dark"):
        panel.set_appearance(mode)
        a, b = panel.letter_colours()
        assert a != b
        assert a in panel._a_letter.styleSheet() and b in panel._b_letter.styleSheet()
        assert a in panel._LETTER_COLOURS[mode]
    panel.set_appearance("neutral")
    a, b = panel.letter_colours()
    assert a == b, "Neutral tells A from B by the letter, never by a hue"


def test_every_slider_says_which_profile_it_changes(panel):
    for sl, who in ((panel._a_opacity_slider, "profile A"), (panel._a_sat_slider, "profile A"),
                    (panel._opacity_slider, "profile B"), (panel._sat_slider, "profile B")):
        assert sl.toolTip().startswith("How ") and who in sl.toolTip()


def test_save_as_defaults_keeps_a_too(panel):
    panel._a_opacity_slider.setValue(60)
    panel._a_sat_slider.setValue(20)
    panel._on_save_defaults()
    assert panel._settings.get("gamut_primary_opacity") == 60
    assert panel._settings.get("gamut_primary_sat") == 20
