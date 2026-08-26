"""Guided never shows the "markers not on this sheet yet" overlay.

Sebastian, 2026-08-26: *"in guided when a chart is created it shows a red
overlay with markers and the text 'markers not on this chart yet - press
generate Chart' — however in guided we don't have the marker options so the user
can't reach it there … so this overlay is confusing in guided and wrong."*

The marker controls live only in the Manual layout panel, but the setting behind
them is GLOBAL and written from that one place. Guided read it anyway, compared
it against the sheet, and drew the accent-colour overlay with a caption naming a
control the user cannot reach in that mode.

Worse, the caption could not be obeyed. `_engine_build_kwargs` never asks for
markers, so every Guided recipe records `helper_markers: false`; pressing
Generate Chart rebuilt the same markerless sheet and the pending state was
permanent.

Present since be85d7e5 (2026-06-30) and merely invisible until #170: while
`chart_left_clip_info` dropped Guided onto printtarg, that path records no
layout, so no overlay was drawn at all.

In Guided the sheet is the only truth — show what it carries, never a proposal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _tab_with_chart(qapp, tmp_path, *, markers_on_sheet: bool):
    """A tab holding a real engine chart, built with or without markers."""
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)

    preset = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    rec = LayoutRecipe.from_dict(preset.layout_recipe)
    rec.helper_markers = markers_on_sheet
    rec.helper_marker_edge_mm = 2.0
    rec.helper_marker_len_mm = 4.0
    rec.helper_marker_per_patch = 3
    res, _ = build_from_recipe(resource_path(preset.ti1_asset),
                               tmp_path / "chart", rec)
    tab._margin_tiffs = list(res.tiff_paths)
    tab._margin_ti2 = Path(res.ti2_path)
    Path(res.ti2_path).with_suffix(".channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "recipe": rec.to_dict(),
                   "seed": res.seed}}), encoding="utf-8")

    # The Manual controls ASK for markers — this is the state that used to leak
    # into Guided. A Guided chart must ignore them entirely.
    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_edge.setValue(8.0)
    lp.helper_marker_len.setValue(9.0)
    lp.helper_marker_per_patch.setValue(6)
    return tab


def test_guided_draws_nothing_when_the_sheet_has_no_markers(qapp, tmp_path):
    """The reported bug. A Guided sheet carries no markers, so nothing is drawn
    and no caption appears — regardless of what the hidden Manual controls say.
    """
    tab = _tab_with_chart(qapp, tmp_path, markers_on_sheet=False)
    tab._switch_mode("guided")
    assert tab._helper_marker_lines_frac() is None, (
        "Guided drew a marker overlay for a sheet that carries no markers — "
        "the caption names a control Guided does not have, and pressing "
        "Generate Chart rebuilds the same markerless sheet")


def test_guided_shows_the_sheets_own_markers_and_never_a_proposal(qapp, tmp_path):
    """If a Guided sheet DOES carry markers, they are shown as printed fact."""
    tab = _tab_with_chart(qapp, tmp_path, markers_on_sheet=True)
    tab._switch_mode("guided")
    got = tab._helper_marker_lines_frac()
    assert got is not None, "the sheet's own markers were not drawn"
    lines, pending = got
    assert lines, "no marker lines produced for a sheet that has them"
    assert pending is False, (
        "Guided claimed the overlay was a proposal — there is no control there "
        "to make one with")


def test_manual_still_proposes(qapp, tmp_path):
    """THE CONTROL. Without this, "always return None" would pass the tests above.

    Manual is where the overlay earns its keep: the controls ask for 6 markers
    per patch and the sheet carries 3, so the overlay must be drawn AND flagged.
    """
    tab = _tab_with_chart(qapp, tmp_path, markers_on_sheet=True)
    tab._switch_mode("manual")
    got = tab._helper_marker_lines_frac()
    assert got is not None, "Manual stopped drawing the overlay entirely"
    lines, pending = got
    assert lines
    assert pending is True, (
        "Manual no longer says the overlay is a proposal — that is the whole "
        "point of it (#164)")
