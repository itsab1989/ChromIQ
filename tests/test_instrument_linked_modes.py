"""#130 (Knut, 2026-07-28): Guided and Manual must show the same instrument.

His report against beta.79: *"After loading a project.json file in create chart
tab, the selected instrument from the project (this case Colormunki) was visible
in the manual mode, but the guided mode still held the default i1Pro
instrument."*

His rule: *"When loading project, or changing instrument, the instrument
selection shall always be the same for guided and for manual mode (linked both
ways)."*

The instrument is written by about a dozen paths — opening a project, a preset,
a prebuilt chart, a loaded patch set, the layout editor, the Guided→Manual
transfer. Mirroring inside each of them would have fixed the one he found and
left the next to be found by him too, so the two controls are **linked** and
every path is right by construction. These tests drive the real tab.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _guided(tab):
    return tab._instr_combo.currentData()


def _manual(tab):
    return tab._manual_get("printtarg", "-i", "")


def test_they_agree_before_anything_is_touched(tab):
    assert _guided(tab) == _manual(tab)


@pytest.mark.parametrize("code", ["CM", "i1", "SS"])
def test_setting_manual_moves_guided(qapp, tab, code):
    """His case: a project load writes the MANUAL value."""
    tab._set_manual_value("printtarg", "-i", code)
    qapp.processEvents()
    assert _manual(tab) == code
    assert _guided(tab) == code, "guided kept its old instrument"


@pytest.mark.parametrize("code", ["CM", "i1", "SS"])
def test_setting_guided_moves_manual(qapp, tab, code):
    """"…linked both ways."""
    i = tab._instr_combo.findData(code)
    assert i >= 0, f"guided should offer {code}"
    tab._instr_combo.setCurrentIndex(i)
    qapp.processEvents()
    assert _guided(tab) == code
    assert _manual(tab) == code, "manual kept its old instrument"


def test_knut_s_exact_case(qapp, tab):
    """Default i1Pro, then a project whose instrument is a ColorMunki."""
    assert _guided(tab) == "i1", "the default this report started from"
    tab._set_manual_value("printtarg", "-i", "CM")     # what a project load does
    qapp.processEvents()
    assert _guided(tab) == "CM", (
        "guided still held the default i1Pro — the bug he reported")


def test_the_link_does_not_bounce(qapp, tab):
    """Each control writing to the other could ping-pong forever. It settles,
    and it settles on the value that was set."""
    for code in ("CM", "SS", "i1", "CM"):
        tab._set_manual_value("printtarg", "-i", code)
        qapp.processEvents()
        assert _guided(tab) == _manual(tab) == code
    assert tab._syncing_instrument is False, "the guard was left latched on"


def test_an_instrument_guided_cannot_show_is_left_alone(qapp, tab):
    """Guided deliberately omits the external-workflow instruments (i1iSis),
    because their layout is recomputed by another program. Manual may still
    select one — guided must not be forced to a wrong value, and nothing may
    crash."""
    from workflow.chart_creator import EXTERNAL_INSTRUMENTS
    external = next(iter(EXTERNAL_INSTRUMENTS))
    assert tab._instr_combo.findData(external) < 0, "guided should not offer it"

    before = _guided(tab)
    tab._set_manual_value("printtarg", "-i", external)
    qapp.processEvents()

    assert _manual(tab) == external, "manual must keep what was asked for"
    assert _guided(tab) == before, "guided should have been left as it was"


def test_a_failure_to_mirror_never_blocks_the_write(tab):
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._link_instrument_controls)
    assert "except Exception" in src
    assert "finally:" in src, "the guard must be released even on failure"


def test_the_link_is_established_once_at_construction():
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._build_ui)
    assert "self._link_instrument_controls()" in src
    lines = [l.strip() for l in src.splitlines()]
    made = next(i for i, l in enumerate(lines)
                if "self._manual_panel = self._make_manual_panel()" in l)
    linked = next(i for i, l in enumerate(lines)
                  if "_link_instrument_controls()" in l)
    assert made < linked, "both panels have to exist before they can be linked"
