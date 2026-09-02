"""`set_appearance` takes three: no component folds a third appearance away.

Sixteen components opened with

    self._mode = "light" if mode == "light" else "dark"

which reads like validation and is not. It is a *fold*: it has room for two
answers and files everything else under Dark. A third appearance broadcast by
``apply_appearance`` would have reached all twenty-one ``set_appearance``
implementations correctly and sixteen of them would have repainted themselves
Dark — a light-grey window with a dark masthead, a dark tab bar, a dark tool
popup and a dark TIFF preview.

Every test here CALLS the real component. When this file was written the third
appearance was registered in ``ui.theme.CONCRETE_APPEARANCES`` for the duration
of a test and removed again, because only the plumbing existed. **Neutral now
ships** (``ui/neutral_styles.py``), so the fixture no longer simulates it — it
asserts it is really there and the mutation is performed with the shipped
appearance. The tests are otherwise unchanged: what they prove is still that no
component folds a third answer away.

APPEARANCE IS SET BY HANDING A COMPONENT A MODE, NEVER BY ``apply_appearance``.
An app-wide ``setStyleSheet`` in a test re-polishes every widget the suite has
alive, and under xdist it crashed the worker whenever a theme suite shared a
process with another (CLAUDE.md, and the fix/theme-is-asked-not-guessed run).
Nothing here needs it: these components read the mode they are handed.
"""
from __future__ import annotations

import pathlib
import re

import pytest
from PyQt6.QtWidgets import (QApplication, QScrollArea, QTabWidget, QWidget)

import ui.theme as theme

#: The name a third appearance would be broadcast under. Registered per test
#: and removed again — nothing in ``ui/`` knows it.
THIRD = "neutral"

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def third():
    """The third concrete appearance — now a shipped one, not a simulated one.

    This used to monkeypatch ``CONCRETE_APPEARANCES`` and ``_DARK_GROUND`` for
    the duration of each test. Neutral is registered for real now, so the
    fixture's job is to say so: if either registration is ever removed, every
    test that takes this fixture fails here with the reason, rather than
    failing far away with a component "folding" an appearance that no longer
    exists.
    """
    assert THIRD in theme.CONCRETE_APPEARANCES, (
        f"{THIRD!r} is not a concrete appearance any more")
    assert theme.has_dark_ground(THIRD) is False, (
        f"{THIRD!r} lost its light _DARK_GROUND row")
    return THIRD


# ======================================================================
# 1. accept_mode — the door itself
# ======================================================================

def _old_fold(mode):
    """The expression this change removed, kept here as the reference."""
    return "light" if mode == "light" else "dark"


@pytest.mark.parametrize("value", [
    "light", "dark",                     # the two the app broadcasts
    "auto", "", "Light", "DARK", "lite", None, 0, 5, ("light",),
])
def test_accept_mode_answers_exactly_as_the_old_fold_did(value):
    """No behaviour change today: it must agree with the fold on every input.

    This is the whole risk of the change — these are the paths that repaint the
    entire interface — so the equivalence is asserted against the removed
    expression itself, not against a remembered description of it.
    """
    assert theme.accept_mode(value) == _old_fold(value)


def test_accept_mode_carries_a_third_appearance_once_it_is_registered(third):
    assert theme.accept_mode(THIRD) == THIRD
    # …and the two that ship are untouched by its presence.
    assert theme.accept_mode("light") == "light"
    assert theme.accept_mode("dark") == "dark"


def test_accept_mode_still_refuses_a_name_that_is_not_an_appearance():
    """The fold's defensive purpose is kept; only its ceiling is removed.

    ``THIRD`` used to be the example here, because it was not yet registered.
    It ships now, so the example is a name that never will be.
    """
    assert "chartreuse" not in theme.CONCRETE_APPEARANCES
    assert theme.accept_mode("chartreuse") == theme.APPEARANCE_DARK
    assert theme.accept_mode("auto", default="light") == "light"


# ======================================================================
# 2. has_dark_ground — the genuinely two-answer sites
# ======================================================================

@pytest.mark.parametrize("mode", ["light", "dark", "auto", "", None])
def test_has_dark_ground_agrees_with_the_title_bars_old_expression(mode):
    """macOS offers Aqua and DarkAqua and no third; the ANSWER must not change.

    The removed line was
    ``b"NSAppearanceNameAqua" if mode == "light" else b"NSAppearanceNameDarkAqua"``.
    """
    old = b"NSAppearanceNameAqua" if mode == "light" else b"NSAppearanceNameDarkAqua"
    new = (b"NSAppearanceNameDarkAqua" if theme.has_dark_ground(mode)
           else b"NSAppearanceNameAqua")
    assert new == old


def test_has_dark_ground_gives_a_light_grey_third_appearance_the_light_answer(third):
    """The point of the table: `mode == "light"` would have said DarkAqua."""
    assert theme.has_dark_ground(THIRD) is False
    assert ("light" == THIRD) is False          # what the old expression asked


def test_every_concrete_appearance_declares_a_ground():
    """A shipped appearance that forgets to declare its ground is treated as
    dark, which for a light theme is the silent wrong answer. Fail here first."""
    missing = [m for m in theme.CONCRETE_APPEARANCES
               if m not in theme._DARK_GROUND]
    assert missing == [], f"no _DARK_GROUND row for {missing}"


# ======================================================================
# 3. THE TABLE — every component that takes an appearance
# ======================================================================
# Each entry builds the REAL component and hands it a mode the way the app
# does. `attr` is where the component keeps what it was handed; None means the
# component deliberately keeps nothing (its set_appearance is a no-op).

def _tools_popup():
    from ui.tools_popup import ToolsPopup
    return ToolsPopup(), "set_appearance"


def _builtin_preset_popup():
    from ui.builtin_preset_popup import BuiltinPresetPopup
    return BuiltinPresetPopup([("i1Pro", [("TC9.18", "tc918")])]), "set_appearance"


def _builtin_preset_button():
    from ui.builtin_preset_popup import BuiltinPresetButton
    return BuiltinPresetButton(), "set_appearance"


def _margin_inspector():
    from ui.margin_inspector_panel import MarginInspectorPanel
    return MarginInspectorPanel(), "set_appearance"


def _masthead():
    from ui.masthead_header import MastheadHeader
    return MastheadHeader(), "set_appearance"


def _spectrum_tab_bar():
    from ui.spectrum_tab_bar import SpectrumTabBar
    return SpectrumTabBar(), "set_appearance"


def _tiff_preview():
    from ui.tiff_preview import TiffPreview
    return TiffPreview(), "set_appearance"


def _patch_info_tile():
    from ui.tiff_preview import _PatchInfoTile
    return _PatchInfoTile(QWidget()), "set_theme"


def _fade_scroll_area():
    from ui.fade_scroll import FadeScrollArea
    return FadeScrollArea(), "set_appearance"


def _edge_fades():
    from ui.fade_scroll import attach_edge_fades
    area = QScrollArea()
    fades = attach_edge_fades(area)
    fades._keep_area_alive = area          # the wrapper does not own it
    return fades, "set_appearance"


def _gamut_panel():
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.gamut_panel import GamutPanel
    st = AppSettings()
    return GamutPanel(ArgyllRunner(st), st, None), "set_appearance"


def _workflow_icon():
    from ui.dialogs.welcome_dialog import WorkflowIcon
    return WorkflowIcon("chart"), "set_appearance"


def _workflow_card():
    from ui.dialogs.welcome_dialog import WORKFLOWS, WorkflowCard
    return WorkflowCard(WORKFLOWS[0]), "set_appearance"


def _welcome_dialog():
    from core.settings import AppSettings
    from ui.dialogs.welcome_dialog import WelcomeDialog
    return WelcomeDialog(AppSettings(), None, "dark"), "set_appearance"


def _tab_measure():
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    st = AppSettings()
    return TabMeasure(ArgyllRunner(st), st, None), "set_appearance"


def _tab_print():
    from core.settings import AppSettings
    from ui.tabs.tab_print import TabPrint
    return TabPrint(AppSettings(), None), "set_appearance"


def _patch_grid_button():
    from ui.widgets import PatchGridButton
    return PatchGridButton("#56d6a5"), "set_appearance"


def _stacked_pages_button():
    from ui.widgets import StackedPagesButton
    return StackedPagesButton("#56d6a5"), "set_appearance"


def _strip_read_button():
    from ui.widgets import StripReadButton
    return StripReadButton("#56d6a5"), "set_appearance"


def _measured_chart_button():
    from ui.widgets import MeasuredChartButton
    return MeasuredChartButton("#56d6a5"), "set_appearance"


def _reveal_folder_button():
    from ui.widgets import RevealFolderButton
    return RevealFolderButton("#56d6a5"), "set_appearance"


def _image_file_button():
    from ui.widgets import ImageFileButton
    return ImageFileButton("#56d6a5"), "set_appearance"


# --- the four the Index rule added ------------------------------------
# None of them stores a mode. They repaint, and read the live appearance at
# paint time — which is the right shape for a widget whose only theme-dependent
# decision is "one accent value or five hues", and which is why they are all
# `attr=None` below: a component that invents a `_mode` it never consults is a
# second copy of the answer waiting to go stale.

def _tab_header():
    from ui.tab_header import TabHeader
    return TabHeader("STEP 01", "Title", "#56d6a5"), "set_appearance"


def _spectrum_stripe():
    from ui.tab_header import SpectrumStripe
    return SpectrumStripe(), "set_appearance"


def _gradient_overlay():
    from PyQt6.QtWidgets import QWidget as _W
    from ui.gradient_overlay import GradientOverlay
    host = _W()
    overlay = GradientOverlay("#56d6a5", parent=host)
    # The host owns the overlay; without a reference it is garbage-collected
    # and takes its child with it before the test can call anything on it.
    overlay._test_host = host
    return overlay, "set_appearance"


def _tooltip_button():
    from ui.tooltip_button import TooltipButton
    return TooltipButton("t", "b"), "set_appearance"


#: (name, builder, attribute the mode lands in or None for a no-op component)
COMPONENTS = [
    ("ToolsPopup",           _tools_popup,           "_mode"),
    ("BuiltinPresetPopup",   _builtin_preset_popup,  "_mode"),
    ("BuiltinPresetButton",  _builtin_preset_button, None),
    ("MarginInspectorPanel", _margin_inspector,      "_mode"),
    ("MastheadHeader",       _masthead,              "_mode"),
    ("SpectrumTabBar",       _spectrum_tab_bar,      "_mode"),
    ("TiffPreview",          _tiff_preview,          "_mode"),
    ("_PatchInfoTile",       _patch_info_tile,       "_mode"),
    ("FadeScrollArea",       _fade_scroll_area,      "_mode"),
    ("EdgeFades",            _edge_fades,            "_mode"),
    ("GamutPanel",           _gamut_panel,           "_mode"),
    ("WorkflowIcon",         _workflow_icon,         "_mode"),
    ("WorkflowCard",         _workflow_card,         "_mode"),
    ("WelcomeDialog",        _welcome_dialog,        "_mode"),
    ("TabMeasure",           _tab_measure,           "_mode"),
    ("TabPrint",             _tab_print,             "_mode"),
    ("PatchGridButton",      _patch_grid_button,     None),
    ("StackedPagesButton",   _stacked_pages_button,  None),
    ("StripReadButton",      _strip_read_button,     None),
    ("MeasuredChartButton",  _measured_chart_button, None),
    ("RevealFolderButton",   _reveal_folder_button,  None),
    ("ImageFileButton",      _image_file_button,     None),
    ("TabHeader",            _tab_header,            None),
    ("SpectrumStripe",       _spectrum_stripe,       None),
    ("GradientOverlay",      _gradient_overlay,      None),
    ("TooltipButton",        _tooltip_button,        None),
]

_IDS = [c[0] for c in COMPONENTS]


@pytest.mark.parametrize("name,build,attr", COMPONENTS, ids=_IDS)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_light_and_dark_still_land_where_they_always_did(app, name, build,
                                                         attr, mode):
    """The regression guard. These are the paths that repaint everything."""
    obj, method = build()
    getattr(obj, method)(mode)
    if attr is None:
        assert not hasattr(obj, "_mode"), (
            f"{name}.set_appearance is a no-op and must invent no mode")
    else:
        assert getattr(obj, attr) == mode


@pytest.mark.parametrize("name,build,attr", COMPONENTS, ids=_IDS)
def test_a_third_appearance_survives_the_door(app, third, name, build, attr):
    """THE MUTATION. Before the change every `_mode` entry here answered
    'dark' — the fold. A component that still folds fails this test and only
    this test; nothing else in the suite would notice."""
    obj, method = build()
    getattr(obj, method)(THIRD)
    if attr is None:
        assert not hasattr(obj, "_mode")
    else:
        assert getattr(obj, attr) == THIRD, (
            f"{name} folded {THIRD!r} into {getattr(obj, attr)!r}")


def test_the_component_table_covers_every_appearance_taking_method():
    """A new `set_appearance` that is not in the table above is a hole.

    Scans the source rather than the running app: a component nothing has
    constructed yet still has to carry a third appearance.
    """
    import ast
    found = set()
    for path in sorted((ROOT / "ui").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for body in node.body:
                if (isinstance(body, ast.FunctionDef)
                        and body.name in ("set_appearance", "set_theme")):
                    found.add(node.name)
    assert found - set(_IDS) == set(), (
        f"components take an appearance but are not in COMPONENTS: "
        f"{sorted(found - set(_IDS))}")


# ======================================================================
# 4. The two sites that are not a `set_appearance`
# ======================================================================

def test_patch_cube_panel_keeps_the_appearance_it_was_constructed_with(app,
                                                                       third):
    """It took its appearance in the constructor and threw the NAME away —
    `_THEME.get(mode, _THEME["dark"])` left nothing to tell a third appearance
    from a genuine Dark."""
    from ui.patch_cube_panel import PatchCubePanel
    assert PatchCubePanel(mode=THIRD)._mode == THIRD
    assert PatchCubePanel(mode="light")._mode == "light"
    assert PatchCubePanel(mode="dark")._mode == "dark"
    # …and now that `_THEME` has a third entry, it paints its OWN well rather
    # than Dark's. Keeping the name is what made that entry reachable.
    from ui.neutral_styles import NM_BG_VIEWER
    assert PatchCubePanel(mode=THIRD)._theme["bg"] == NM_BG_VIEWER
    assert PatchCubePanel(mode="dark")._theme["bg"] == "#111111"


def test_the_per_tab_style_cache_tells_a_third_appearance_from_dark(app, third):
    """The cache key was `"light" if is_light else "dark"`, so a third
    appearance collided with Dark's entry and switching between them would be a
    cache HIT — skipping the restyle a theme switch exists to perform."""
    from ui.main_window import MainWindow

    class _Stub:
        def __init__(self, mode):
            self._title_bar_mode = mode
            self._styled_tab_theme: dict[int, str] = {}
            self._tabs = QTabWidget()
            self._tabs.addTab(QWidget(), "one")

    stub = _Stub("dark")
    MainWindow._apply_tab_widget_styling(stub, 0)
    assert stub._styled_tab_theme[0] == "dark"

    stub._title_bar_mode = THIRD
    MainWindow._apply_tab_widget_styling(stub, 0)
    assert stub._styled_tab_theme[0] == THIRD, (
        "a third appearance shared Dark's cache entry")

    light = _Stub("light")
    MainWindow._apply_tab_widget_styling(light, 0)
    assert light._styled_tab_theme[0] == "light"


def test_the_native_title_bar_asks_which_ground_not_which_name(app):
    """The macOS title bar cannot be observed from a test — under the offscreen
    platform ``_apply_title_bar`` returns before it touches Cocoa, and on a real
    window it writes nothing this process can read back. So the site is checked
    at the source: it must ask :func:`has_dark_ground`, and it must not decide
    by comparing the mode to ``"light"`` — a light-grey appearance is not named
    "light" and would be given a black title bar over a light window."""
    import inspect

    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow._apply_title_bar)
    body = "\n".join(line for line in src.splitlines()
                     if not line.strip().startswith("#"))
    assert "has_dark_ground(mode)" in body
    assert 'mode == "light"' not in body


# ======================================================================
# 5. The fold must not come back
# ======================================================================

_FOLD = re.compile(r'"light"\s+if\s+.*?\s+else\s+"dark"'
                   r'|"dark"\s+if\s+.*?\s+else\s+"light"')


def test_no_module_folds_an_appearance_into_two_values_any_more():
    """Source guard. The fold is easy to write again and invisible in review:
    it looks like a default. `ui/theme.py` quotes it in a docstring, which is
    where the explanation lives."""
    offenders = []
    for path in sorted((ROOT / "ui").rglob("*.py")):
        if path.name == "theme.py":
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if _FOLD.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    assert offenders == [], "\n".join(offenders)
