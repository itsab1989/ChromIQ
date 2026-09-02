"""Perf: the per-tab stylesheet is a pure function of (index, theme), so a
revisit for the same theme skips the ~30 ms style re-polish. These lock the
no-regression contract: a revisit doesn't re-style, a theme switch does, and the
global TooltipButton.ACCENT (read by dialogs opened later) still updates on every
call regardless of the cache."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def win(qapp, tmp_path_factory, monkeypatch):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    # THROUGH `monkeypatch`, NOT BY ASSIGNMENT. This used to be a bare
    # `MainWindow._apply_title_bar = lambda ...` and it was never put back — a
    # class-level patch that outlives the module and follows the process into
    # whatever file xdist schedules next. `test_set_appearance_takes_three.py`
    # reads that method's SOURCE to check it asks `has_dark_ground`, and got
    # the lambda: a green check turned red for a reason that had nothing to do
    # with the code under test, whenever the two files shared a worker.
    monkeypatch.setattr(MainWindow, "_apply_title_bar",
                        lambda self, mode: None, raising=False)
    tmp = tmp_path_factory.mktemp("style")
    s = AppSettings()
    s._qs = QSettings(str(tmp / "t.ini"), QSettings.Format.IniFormat)
    s.set("restore_last_session", False)
    w = MainWindow(s)
    w.show()
    qapp.processEvents()
    return w


def test_startup_styles_every_tab_for_current_theme(win):
    assert set(win._styled_tab_theme) == set(range(win._tabs.count()))
    assert set(win._styled_tab_theme.values()) <= {"light", "dark"}


def test_revisit_is_cached_but_accent_still_updates(win):
    from ui.styles import TAB_COLORS
    from ui.tooltip_button import TooltipButton

    snap = dict(win._styled_tab_theme)          # all tabs styled at startup
    win._apply_tab_widget_styling(0)            # revisit same tab+theme
    win._apply_tab_widget_styling(2)
    assert win._styled_tab_theme == snap        # no re-style happened
    assert TooltipButton.ACCENT == TAB_COLORS[2]  # ACCENT still refreshed


def test_reapplies_when_cache_missing(win):
    win._styled_tab_theme.pop(1, None)          # simulate an unstyled tab
    win._apply_tab_widget_styling(1)
    assert 1 in win._styled_tab_theme           # re-applied + re-cached


def test_theme_switch_reapplies_all_tabs(win):
    new = "light" if win._title_bar_mode == "dark" else "dark"
    win.apply_theme(new)
    assert win._title_bar_mode == new
    assert set(win._styled_tab_theme) == set(range(win._tabs.count()))
    assert all(v == new for v in win._styled_tab_theme.values())


def test_applying_a_light_theme_restyles_every_tab(win):
    """Basti, on a real launch: "on launch the styling in create chart tab is not
    correct. switching between modules does not help, switching to another tab
    and back fixes it."

    `_apply_tab_widget_styling` caches on (index, mode). While `_title_bar_mode`
    was hard-coded "dark" this pass was always a cache MISS in light mode, so
    every tab was genuinely re-styled — and that second pass is load-bearing:
    `apply_theme` turns the group boxes' `autoFillBackground` ON in light mode
    and the per-tab stylesheet two statements later repolishes it back OFF.
    Seeding the mode correctly turned the miss into a hit, the re-style stopped,
    and Create Chart came up wrong until the user switched tabs.

    Rendered comparison put a number on it: without the clear, light mode
    differs from master over 21% of the window; dark is pixel-identical either
    way, which is why the clear is for the PALE grounds only.

    It used to be spelled `if mode == "light"`, and this test asserted that
    literal. The condition that was meant all along is *does this appearance
    paint a pale ground* — the fight is with the group boxes' surface, and
    Neutral now has one too, so it needs the same second pass. Dark still never
    enters it and still keeps its ~264 ms. Asserted as behaviour rather than as
    a spelling: what matters is which appearances clear, not how the branch is
    written.
    """
    import inspect
    from ui.main_window import MainWindow
    from ui.theme import CONCRETE_APPEARANCES, has_dark_ground
    src = inspect.getsource(MainWindow.apply_theme)
    head = src.split("_log_weight", 1)[0]
    assert "_styled_tab_theme.clear()" in head, (
        "applying a theme must forget what was styled at construction, or the "
        "tabs keep the stylesheet from before the theme was known")
    assert 'mode == "light"' not in head, (
        "the clear is not about the NAME 'light' — a light-grey appearance "
        "paints group-box surfaces too and needs the same second pass")

    # Watch the thing the clear exists to cause: does applying the SAME
    # appearance a second time actually re-set the tab's stylesheet? A poisoned
    # cache entry would not tell them apart — a miss rewrites the entry with or
    # without the clear — so the sheet itself is the observable.
    tab0 = win._tabs.widget(0)
    calls: list = []
    _orig_set = tab0.setStyleSheet
    tab0.setStyleSheet = lambda qss: (calls.append(qss), _orig_set(qss))[1]

    for mode in CONCRETE_APPEARANCES:
        win.apply_theme(mode)
        calls.clear()
        win.apply_theme(mode)          # same appearance, straight after
        cleared = bool(calls)
        if has_dark_ground(mode):
            assert not cleared, (
                f"{mode} paints a dark ground and is pixel-identical with and "
                f"without the clear; clearing costs ~264 ms of every launch")
        else:
            assert cleared, (
                f"{mode} paints a pale ground, so its group-box surfaces are "
                f"repolished away by the per-tab stylesheet unless every tab "
                f"is re-styled")
