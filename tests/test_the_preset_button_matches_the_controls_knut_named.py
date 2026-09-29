"""The preset-verification button against the three things Knut asked for,
measured under THE APP'S OWN STYLESHEET.

Knut, #182, on beta 26:

    *"The button is still too tall, and not reduced in height as I previously
    very thoroughly gave examples how it should look. There is also still the
    frame overlapping with the bottom edge of the button, although I gave
    examples how it should look.. One more thing; Move the position of the
    button so that the left edge of the button is aligned with the left edge of
    the dropdown input box for the 'Select preset'."*

He had said all of it once already, naming the reference controls rather than
posting pictures: *"Use the button height similar to 'New Seed' or 'Reset to
Preset'"*, and *"make sure there is a distance between the bottom edge of the
button and the frame edge, as done for other frames, such as the
'Randomisation' or 'Layout' frames."*

WHY A SECOND FILE, WHEN ONE ALREADY GUARDS THIS BUTTON'S HEIGHT
---------------------------------------------------------------
Because the one that does went green the whole time.
``test_the_preset_button_is_small_fast_and_where_it_belongs.py`` builds the
real tab, shows it, and compares the button against a plain ``QPushButton`` --
but it never loads ``ui/styles.py``'s stylesheet, and that stylesheet is the
whole mechanism. Under it, ``QPushButton { padding: 6px 18px; min-height:
28px }`` folds into ``minimumSizeHint`` as 42 px and a layout honours a minimum
size hint over a fixed height, so ``setFixedHeight(22)`` did nothing at all.
Measured in a real window on 2026-09-20
(``scripts/drive_k26_preset_button_geometry.py``, ``button-before``):

    the preset-verification button   42 px      left edge  25 px
    "New seed"                       24 px
    "Reset to preset"                24 px
    "Select preset" combo                       left edge 116 px

    the Presets frame's last widget sits  -7 px above the frame's bottom edge
    the Randomisation frame's                10 px
    the Layout frame's                       10 px

A negative gap is the overlap Knut photographed: the group box's own bottom
line runs through the button. All three of his sentences were right, and two
commits had already claimed to answer two of them.

This is the same fault round 30 found on the reference-values buttons, one
window further on, and it is the same lesson: **a size guard has to lay the
widget out under the application's own stylesheet.** It styles the TAB, never
the application (CLAUDE.md: a ``qapp.setStyleSheet()`` in a test re-polishes
every widget the suite has alive and cost 29 s in one run). That measures the
same thing, because the rule being defeated is an application-wide
``QPushButton`` rule and it applies to a widget tree just the same.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt6.QtWidgets")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QSettings                        # noqa: E402
from PyQt6.QtWidgets import (QApplication, QGroupBox,             # noqa: E402
                             QPushButton)

from core.argyll_runner import ArgyllRunner                       # noqa: E402
from core.file_manager import FileManager, Project                # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION         # noqa: E402
from core.settings import AppSettings                             # noqa: E402
from ui.measurement_target_bar import (                           # noqa: E402
    MeasurementTargetController)
from ui.tabs.tab_chart import TabChart                            # noqa: E402


def _pump(qapp, n: int = 60) -> None:
    for _ in range(n):
        qapp.processEvents()


@pytest.fixture
def styled_verification_tab(qapp, tmp_path):
    """A real Create Chart tab, Manual mode, verification run, UNDER THE
    APP'S STYLESHEET and shown, because none of these numbers exist until
    a layout has run with that stylesheet in force."""
    from ui.light_styles import LIGHT_STYLESHEET

    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "s.ini"),
                             QSettings.Format.IniFormat)
    out = tmp_path / "ChromIQ"
    out.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(out))
    # The engine panel is what carries "New seed" and the preset bar.
    settings.set("use_chromiq_layout_engine", True)
    fm = FileManager(settings)
    Project.create(out / "K", "K").current_run().ensure_dir()
    fm.set_target_name("K")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)

    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    tab.setStyleSheet(LIGHT_STYLESHEET)
    tab.resize(620, 1000)
    tab.show()
    _pump(qapp)
    tab._manual_btn.click()
    _pump(qapp)
    tab._sync_preset_verify_visibility()
    _pump(qapp)
    yield tab
    tab.close()
    tab.deleteLater()
    _pump(qapp, 10)


def _plain_height(tab, qapp) -> int:
    """What a default button costs in this tree, re-derived, not remembered."""
    p = QPushButton("PLAIN", tab._preset_verify_btn.parentWidget())
    p.show()
    _pump(qapp, 20)
    h = p.height()
    p.setParent(None)
    p.deleteLater()
    _pump(qapp, 10)
    return h


def test_the_stylesheet_really_is_in_force(styled_verification_tab, qapp):
    """The guard that missed this measured a tree with no stylesheet in it.

    If this fails, every other assertion in the file is measuring a state no
    user meets, and that is worth saying out loud rather than going green.
    """
    tab = styled_verification_tab
    plain = _plain_height(tab, qapp)
    assert plain >= 36, (
        f"a default QPushButton in this tree is {plain} px. Under ChromIQ's "
        "own stylesheet it is 42 — so the stylesheet is not loaded here and "
        "this file is measuring nothing.")


def test_the_button_is_no_taller_than_the_controls_knut_named(
        styled_verification_tab, qapp):
    """"Use the button height similar to 'New Seed' or 'Reset to Preset'."

    Both of those measure 24 px on screen. The button was 42.
    """
    tab = styled_verification_tab
    tab._manual_preset_bar.setVisible(True)
    _pump(qapp)
    btn = tab._preset_verify_btn
    refs = {"New seed": tab._manual_layout_panel.new_seed_btn,
            "Reset to preset": tab._manual_preset_reset_btn,
            "Update preset": tab._manual_preset_update_btn,
            "Edit defaults": tab._manual_preset_edit_btn}
    heights = {k: v.height() for k, v in refs.items()}
    tallest = max(heights.values())
    # EVERY COMPARISON HERE IS A RELATION, NEVER A NUMBER. Three different
    # height measurements of this one button have lied in two days: one read
    # the source, one measured a widget that was never shown, and one measured
    # a shown widget with no stylesheet on it. A pixel count is only true of
    # the platform that produced it; "no taller than the control beside it" is
    # true everywhere, and it is also exactly what Knut asked for.
    assert btn.height() <= tallest, (
        f"the button is {btn.height()} px tall; the controls Knut named are "
        f"{heights}. setFixedHeight cannot shorten a button in this app — the "
        "stylesheet's QPushButton min-height wins. Use a per-widget "
        "stylesheet, as 'Reset to preset' does.")
    assert btn.height() < _plain_height(tab, qapp), (
        "the button is no shorter than a default button, which is what he "
        "called too tall")
    assert btn.height() <= tab._preset_combo.height(), (
        f"the button is {btn.height()} px and the 'Select preset' combo "
        f"directly above it in the same frame is {tab._preset_combo.height()}."
        " The button is the small control under the dropdown, not a taller "
        "one.")


def test_the_button_starts_where_the_preset_dropdown_starts(
        styled_verification_tab, qapp):
    """"the left edge of the button is aligned with the left edge of the
    dropdown input box for the 'Select preset'." To the pixel.

    Two independent QHBoxLayouts cannot do this: the button's row knows
    nothing about the width the label came out at, and the button sat 91 px to
    the left of the combo, flush with the label instead.
    """
    tab = styled_verification_tab
    btn, combo = tab._preset_verify_btn, tab._preset_combo
    bx = btn.mapTo(tab, QPoint(0, 0)).x()
    cx = combo.mapTo(tab, QPoint(0, 0)).x()
    assert bx == cx, (
        f"the button's left edge is at {bx} and the 'Select preset' combo's "
        f"is at {cx}, {bx - cx:+d} px out. They share a QGridLayout column so "
        "that this cannot drift with the label's width or the language.")


def test_the_button_does_not_overlap_the_presets_frame(
        styled_verification_tab, qapp):
    """"Make sure there is a distance between the bottom edge of the button
    and the frame edge, as done for other frames."

    The distance is compared with the two frames he named rather than with a
    number somebody liked: whatever Randomisation and Layout give their last
    widget, the Presets frame gives the button.
    """
    tab = styled_verification_tab
    btn = tab._preset_verify_btn
    grp = btn.parentWidget()
    while grp is not None and not isinstance(grp, QGroupBox):
        grp = grp.parentWidget()
    assert grp is not None and grp.title(), "the button is in no group box"

    bottom = btn.mapTo(grp, QPoint(0, btn.height())).y()
    gap = grp.height() - bottom
    assert gap > 0, (
        f"the button's bottom edge is {-gap} px BELOW the Presets frame's "
        "own bottom edge, so the frame line is drawn through the button. "
        "That is the overlap Knut reported twice.")

    named = {g.title(): g for g in tab.findChildren(QGroupBox)}
    others = {}
    for title in ("Randomisation", "Layout"):
        g = named.get(title)
        if g is None or not g.isVisibleTo(tab) or g.layout() is None:
            continue
        low = None
        for c in g.findChildren(QPushButton) + g.findChildren(object):
            if (not hasattr(c, "isWidgetType") or not c.isWidgetType()
                    or c.parentWidget() is not g or not c.isVisibleTo(g)):
                continue
            b = c.mapTo(g, QPoint(0, c.height())).y()
            low = b if low is None else max(low, b)
        if low is not None:
            others[title] = g.height() - low
    for title, other in others.items():
        assert gap >= other, (
            f"the Presets frame leaves {gap} px under its last widget and "
            f"{title} leaves {other}. He asked for the same distance as those "
            "frames, not less.")


def test_the_height_comes_from_a_per_widget_stylesheet(
        styled_verification_tab):
    """The MECHANISM, named, so the next round does not reach for the one
    that cannot work.

    ``setFixedHeight`` on a button in this app is a no-op the moment a layout
    asks for ``minimumSizeHint``; two commits shipped believing otherwise.
    """
    btn = styled_verification_tab._preset_verify_btn
    assert "min-height" in btn.styleSheet(), (
        "the button's height is not set by its own stylesheet. A fixed height "
        "cannot shrink it under the app's QPushButton rule — see this file's "
        "docstring.")
    assert btn.maximumHeight() > 100, (
        "the button carries a fixed/maximum height again. That is the call "
        "that did nothing twice; the per-widget stylesheet is what works.")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])
