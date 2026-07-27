"""#131 (Knut, 2026-07-26): each engine's help must show, side by side, what
that engine gives you and what the ArgyllCMS original does not.

The tables are the answer to "which of these should I switch on?", so they are
pinned here — including the two honest rows, since those are the ones a future
edit is most likely to quietly drop.
"""
from __future__ import annotations

import pathlib

SETTINGS = (pathlib.Path(__file__).resolve().parents[1]
            / "ui" / "dialogs" / "settings_dialog.py").read_text()
TAB_CHART = (pathlib.Path(__file__).resolve().parents[1]
             / "ui" / "tabs" / "tab_chart.py").read_text()


def test_the_reading_engine_help_compares_it_with_chartread():
    """Grouped lists rather than columns: a plain-text info window uses a
    proportional font, so aligned columns wrap into nonsense (Knut saw exactly
    that). The two groups carry the same information without needing to line
    up."""
    assert "Only with the ChromIQ engine:" in SETTINGS
    assert "The same either way:" in SETTINGS
    for item in ("saved after every strip", "the reading time for every strip",
                 "read too fast", "the measured values themselves"):
        assert item in SETTINGS, item


def test_the_reading_help_says_why_pace_needs_the_engine():
    """The limitation has to travel with the table, or the missing rows look
    arbitrary rather than physical."""
    assert "the exact moment the instrument fires" in SETTINGS
    assert "picking the instrument up" in SETTINGS


def test_the_reading_help_admits_the_beeps_cannot_be_silenced_on_the_old_path():
    """Knut hit this himself: on the separate chartread you may hear its beeps
    as well as your chosen sounds, and nothing can stop that."""
    assert "offers no way to" in SETTINGS and "turn that off" in SETTINGS


def test_the_layout_engine_help_compares_it_with_printtarg():
    assert "Only with the ChromIQ engine:" in TAB_CHART
    assert "The same either way:" in TAB_CHART
    for item in ("more patches on every sheet", "you choose the patch size",
                 "a clip border to cut along", "multi-ink (CMY+N) charts"):
        assert item in TAB_CHART, item


def test_the_layout_help_says_the_result_is_equally_valid():
    """A comparison table must not imply the old path produces worse data."""
    assert "reads and profiles in exactly" in TAB_CHART
