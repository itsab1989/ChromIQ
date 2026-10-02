"""A patch outlined in red says why, on the hover card and in the help
(Knut, #202 5951426710): "when measuring and some patches are highlighted with
a red rectangle ... this is not explained to the user ... maybe the hover-message
should include a clear message (at the bottom, separated from the Expected /
Measured and Lab value numbers) explaining why the patch is highlighted and the
measured value in relation to the error limit set in preferences ... The help
text for "Show patch values...." should explain this."
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _rows(qapp, info, mode="both"):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    base = {"loc": "B7", "exp_rgb": (200, 0, 0), "meas_rgb": (20, 200, 20),
            "exp_lab": (50, 70, 50), "meas_lab": (70, -60, 50), "de": 61.25}
    base.update(info)
    tile.set_content(base, mode)
    return [text for _sw, text in tile._rows]


def test_a_flagged_patch_explains_itself_at_the_bottom(qapp):
    rows = _rows(qapp, {"warn": True, "warn_de": 50.0, "fenced": True})
    i = next(i for i, r in enumerate(rows) if r.startswith("─"))
    assert i > next(i for i, r in enumerate(rows) if "ΔE*ab  61.25" in r)
    tail = rows[i + 1:]
    assert tail[0] == "Red outline: likely misread"
    assert tail[1] == "ΔE*ab 61.2 reached your limit 50.0"
    assert tail[2] == "and stands out from its strip"
    assert "Flag a patch" in tail[3]


@pytest.mark.parametrize("mode", ["expected", "measured"])
def test_the_reason_shows_in_every_view_mode(qapp, mode):
    rows = _rows(qapp, {"warn": True, "warn_de": 50.0, "fenced": False}, mode)
    assert "Red outline: likely misread" in rows
    assert "and stands out from its strip" not in rows


def test_an_unflagged_patch_says_nothing_extra(qapp):
    rows = _rows(qapp, {"warn": False, "warn_de": 50.0})
    assert not any(r.startswith("─") or "Red outline" in r for r in rows)


def test_every_reading_mode_hands_the_card_its_reason():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert src.count('"warn_de": warn_de') == 3


def test_the_help_explains_the_red_outline():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    i = src.index('tr("Show patch values on hover"),\n')
    assert "A patch outlined in red is one ChromIQ thinks" in src[i:i + 2500]
