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
    assert "Engine   chartread" in SETTINGS
    for row in ("Saved after every strip", "Reading time for each strip",
                "Too-fast warning and advice", "Identical measured values"):
        assert row in SETTINGS, row


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
    assert "Engine   printtarg" in TAB_CHART
    for row in ("Patches per sheet", "Choose the patch size",
                "Clip border for cutting", "Multi-ink (CMY+N) charts"):
        assert row in TAB_CHART, row


def test_the_layout_help_says_the_result_is_equally_valid():
    """A comparison table must not imply the old path produces worse data."""
    assert "reads and profiles in exactly" in TAB_CHART
