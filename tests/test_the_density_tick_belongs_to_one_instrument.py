"""One checkbox, three meanings, and a tick that used to carry between them.

`_dd_check` in Create Chart → Guided is not one option shown for several
instruments. It is THREE options sharing a widget, relabelled by
`_update_dd_visibility`:

    ColorMunki    "Double density"    printtarg -h, REQUIRES the physical rig
    CR30          "Hexagon patches"   #159, and it really does change the chart
    SpectroScan   "Hexagon patches"
    i1Pro / 3Plus hidden              -h means nothing to a strip reader

Nothing remembered which of those a tick belonged to, so it simply stayed where
it was. Basti, 2026-09-08, reported a CR30 chart whose panel came back saying
"ColorMunki, double density"; chasing it turned up the worse half, proven on
screen before this fix:

    CR30 + hexagons ON  ->  switch to ColorMunki  ->  "Double density" TICKED

Double density is the one that needs the rig accessory. Its own tooltip says the
instrument "will misread" without it. So a chart the user cannot measure, from a
control they never touched for that instrument.

The reverse was a quieter loss, and it broke a CONFIRMED rule:
`docs/design/per_target_settings.md` §4c **D-2** (confirmed by Basti,
2026-09-02) says an instrument change *"may not overwrite a value they have
chosen"*. A deliberate ColorMunki tick was force-unchecked on the way to an
i1Pro and never restored.

Both go away with per-instrument memory, which is what these pin. The i1/p3
branch still force-unchecks the WIDGET, because -h must not reach printtarg for
a strip reader; what must survive that is the remembered value.
"""
from __future__ import annotations

import os

import pytest
from PyQt6.QtCore import QSettings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.argyll_runner import ArgyllRunner                    # noqa: E402
from core.file_manager import FileManager                      # noqa: E402
from core.settings import AppSettings                          # noqa: E402
from ui.tabs.tab_chart import TabChart                         # noqa: E402


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._user_switch_mode("guided")
    return t


def _pick(tab, code: str) -> None:
    """Change the instrument the way a person changes it."""
    i = tab._instr_combo.findData(code)
    assert i >= 0, f"{code} is not offered in Guided"
    tab._instr_combo.setCurrentIndex(i)
    tab._instr_combo.currentIndexChanged.emit(i)


def _state(tab) -> tuple[bool, bool, str]:
    """`isHidden()`, NOT `isVisible()`.

    The tab is never shown in a test, so `isVisible()` is False for every
    widget in it and an "is it hidden?" assertion written that way passes no
    matter what the code does. `isHidden()` answers the question actually being
    asked: did `_update_dd_visibility` call `setVisible(False)` on this widget?
    """
    return (not tab._dd_check.isHidden(), tab._dd_check.isChecked(),
            tab._dd_check.text())


# ---------------------------------------------------------------------------
# what the widget IS
# ---------------------------------------------------------------------------
def test_the_one_checkbox_is_relabelled_per_instrument(tab):
    """If this ever collapses to one label, the whole premise below is gone."""
    labels = {}
    for code in ("CM", "CR30", "SS"):
        _pick(tab, code)
        vis, _chk, text = _state(tab)
        assert vis, f"{code}: the option is hidden"
        labels[code] = text
    assert labels["CM"] != labels["CR30"], \
        "ColorMunki and CR30 now share a label, so one of them is being lied to"
    assert "exagon" in labels["CR30"] and "exagon" in labels["SS"]


def test_a_strip_reader_still_hides_and_unticks_the_widget(tab):
    """-h must not reach printtarg for an i1Pro. The WIDGET is cleared; what
    the user chose for another instrument is remembered elsewhere."""
    _pick(tab, "CM")
    tab._dd_check.setChecked(True)
    _pick(tab, "i1")
    vis, chk, _ = _state(tab)
    assert vis is False and chk is False


# ---------------------------------------------------------------------------
# the leak
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("frm,to", [("CR30", "CM"), ("SS", "CM"),
                                    ("CM", "CR30"), ("CM", "SS")])
def test_a_tick_does_not_carry_into_an_option_that_means_something_else(
        tab, frm, to):
    _pick(tab, frm)
    tab._dd_check.setChecked(True)
    _pick(tab, to)
    _vis, chk, label = _state(tab)
    assert chk is False, (
        f"a tick made for {frm} arrived on {to} as {label!r}, which the user "
        "never asked for"
    )


def test_the_worst_case_by_name_hexagons_never_become_rig_double_density(tab):
    """The one that costs a sheet of paper and a measurement."""
    _pick(tab, "CR30")
    tab._dd_check.setChecked(True)
    assert "exagon" in tab._dd_check.text()
    _pick(tab, "CM")
    assert tab._dd_check.text() == "Double density"
    assert tab._dd_check.isChecked() is False
    assert tab._shared_get("guided")["double_density"] is False, \
        "the run would be built, and stored, as rig double density"


# ---------------------------------------------------------------------------
# the loss (design spec §4c, D-2)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("visited", ["i1", "p3", "CR30", "SS"])
def test_a_deliberate_colormunki_tick_survives_a_look_at_another_instrument(
        tab, visited):
    _pick(tab, "CM")
    tab._dd_check.setChecked(True)
    _pick(tab, visited)
    _pick(tab, "CM")
    assert tab._dd_check.isChecked() is True, (
        f"glancing at {visited} threw away a value the person chose by hand "
        "(per_target_settings.md §4c D-2)"
    )


@pytest.mark.parametrize("code", ["CR30", "SS"])
def test_a_deliberate_hexagon_tick_survives_the_same_round_trip(tab, code):
    _pick(tab, code)
    tab._dd_check.setChecked(True)
    _pick(tab, "i1")
    _pick(tab, code)
    assert tab._dd_check.isChecked() is True


def test_each_family_keeps_its_own_answer_at_the_same_time(tab):
    """Not one remembered bit shared by three options: three separate answers."""
    _pick(tab, "CM")
    tab._dd_check.setChecked(True)
    _pick(tab, "CR30")
    tab._dd_check.setChecked(False)
    _pick(tab, "SS")
    tab._dd_check.setChecked(True)
    for code, want in (("CM", True), ("CR30", False), ("SS", True)):
        _pick(tab, code)
        assert tab._dd_check.isChecked() is want, f"{code} lost its own answer"


def test_an_untouched_instrument_starts_off(tab):
    """D-1: a default may set a value nobody has chosen. Nobody has chosen one
    for an instrument they have never visited, so it starts unticked."""
    _pick(tab, "CR30")
    assert tab._dd_check.isChecked() is False
