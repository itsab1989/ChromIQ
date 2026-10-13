"""Knut, #182 6148467471: a small key to Show patch distribution (3D),
"Colours through the profile", saying what the grey skin, the lines and the
dots are, each beside a sample drawn as the plot draws it.

The words are M-HELP-COLOUR-VIEW-LEGEND, PROPOSED: until approved the view
must look exactly as in beta 2, so no key at all. Once approved it is shown
only in the colour view, in a strip above the plot (never over it, so it
cannot hide a patch), and never in the ink-amount cube.
"""
from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor                            # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from workflow import measurement_messages as MM           # noqa: E402
from workflow import patch_cube                           # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PROGRAM = [(10.0, 20.0, 30.0), (90.0, 10.0, 50.0), (50.0, 50.0, 50.0)]
LABS = [(40.0, 10.0, 20.0), (60.0, -30.0, 5.0), (50.0, 0.0, 0.0)]
COLOURS = [(200, 40, 40), (40, 180, 60), (128, 128, 128)]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def approved(monkeypatch):
    monkeypatch.setattr(MM, "M_HELP_COLOUR_VIEW_LEGEND", dataclasses.replace(
        MM.M_HELP_COLOUR_VIEW_LEGEND, approved=True))


def _dialog(**kw):
    from ui.dialogs.patch_cube_dialog import PatchCubeDialog
    return PatchCubeDialog(PROGRAM, colour_view=(LABS, COLOURS, None), **kw)


def test_the_key_is_proposed_and_hidden_until_approved(qapp):
    from ui.dialogs import patch_cube_dialog as d
    assert "M-HELP-COLOUR-VIEW-LEGEND" in MM.PROPOSED
    assert d._legend_lines() is None
    dlg = _dialog()
    assert dlg._legend is None
    dlg._view_combo.setCurrentIndex(1)
    assert not dlg.findChildren(d.ColourViewLegend), "beta 2's view, unchanged"
    dlg.done(0)


def test_once_approved_it_shows_only_in_the_colour_view(qapp, approved):
    from ui.dialogs import patch_cube_dialog as d
    dlg = _dialog()
    legend = dlg._legend
    assert isinstance(legend, d.ColourViewLegend)
    assert [lbl.text() for lbl in legend.labels] == \
        MM.M_HELP_COLOUR_VIEW_LEGEND.body.split("\n")
    assert [s.kind for s in legend.samples] == ["skin", "line", "dots"]
    assert not legend.isVisibleTo(dlg), "the ink-amount cube is the default"
    dlg._view_combo.setCurrentIndex(1)
    assert legend.isVisibleTo(dlg)
    dlg._view_combo.setCurrentIndex(0)
    assert not legend.isVisibleTo(dlg)
    dlg.done(0)


def test_it_sits_above_the_plot_never_over_it(qapp, approved):
    dlg = _dialog()
    lay = dlg.layout()
    assert dlg._legend.parentWidget() is dlg
    assert lay.indexOf(dlg._legend) == lay.indexOf(dlg._panel) - 1
    dlg.done(0)


def test_no_key_without_a_colour_view(qapp, approved):
    from ui.dialogs.patch_cube_dialog import ColourViewLegend, PatchCubeDialog
    plain = PatchCubeDialog(PROGRAM)
    assert plain._legend is None and not plain.findChildren(ColourViewLegend)
    plain.done(0)


@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
def test_the_samples_wear_the_plots_own_colours(qapp, approved, mode):
    from ui.dialogs.patch_cube_dialog import _blend
    dlg = _dialog(mode=mode)
    th = dlg._panel._theme
    for s in dlg._legend.samples:
        assert s._bg == QColor(th["bg"]) and s._fg == QColor(th["fg"])
    # the line sample is drawn at the opacity the lines are drawn at
    ridges = patch_cube.outline_traces(
        patch_cube.GamutOutline(edges=[[(50, 0, 0), (60, 1, 1)]],
                                vertices=[], faces=[]), fg=th["fg"])[0]
    assert ridges["opacity"] == patch_cube.LINE_OPACITY
    skin = _blend(QColor(th["fg"]), QColor(th["bg"]), patch_cube.SKIN_OPACITY)
    assert skin != QColor(th["bg"])
    dlg.done(0)


def test_every_language_has_the_three_lines():
    m = MM.M_HELP_COLOUR_VIEW_LEGEND
    files = sorted((REPO / "data" / "i18n").glob("*.json"))
    assert len(files) == 13
    for f in files:
        cat = json.loads(f.read_text(encoding="utf-8"))
        assert cat.get(m.title), f.name
        body = cat.get(m.body)
        assert body and len(body.split("\n")) == 3, f.name
        assert "—" not in body, f.name


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_each_sample_draws_its_own_item(qapp, approved, mode):
    """Beta 3's first build drew the patch dots in the skin's sample: the
    dots branch caught everything that was not a line."""
    from ui.dialogs.patch_cube_dialog import _blend
    dlg = _dialog(mode=mode)
    th = dlg._panel._theme
    fg, bg = QColor(th["fg"]), QColor(th["bg"])
    skin = _blend(fg, bg, 1 - (1 - patch_cube.SKIN_OPACITY) ** 2)
    line = _blend(fg, skin, patch_cube.LINE_OPACITY)
    want = {"skin": skin, "line": line,
            "dots": QColor(*dlg._legend.samples[2].DOTS[1])}
    for s in dlg._legend.samples:
        img = s.grab().toImage()
        mid = img.pixelColor(img.width() // 2, img.height() // 2)
        w = want[s.kind]
        assert max(abs(mid.red() - w.red()), abs(mid.green() - w.green()),
                   abs(mid.blue() - w.blue())) <= 6, (s.kind, mid.name(), w.name())
    dlg.done(0)
