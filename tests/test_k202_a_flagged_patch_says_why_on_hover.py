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
    assert tail[0] == "Red outline: a large difference"
    # beta 17: the patch error limit by its name, its value and its chart
    # type, and the strip test by its name (Knut 6082015002, 6084176226)
    assert " ".join(tail[1:5]) == (
        "ΔE*ab 61.2 reached the patch error limit (50.0, profiling charts "
        "with estimated colours), and it stands out from its strip (strip "
        "test).")
    assert "Either a misread, or a colour" in tail
    assert "it is real, keep it for the profile." in tail
    assert " ".join(tail[-2:]) == ("See Preferences ▸ Measurement for "
                                   "threshold values.")


@pytest.mark.parametrize("mode", ["expected", "measured"])
def test_the_reason_shows_in_every_view_mode(qapp, mode):
    rows = _rows(qapp, {"warn": True, "warn_de": 50.0, "fenced": False}, mode)
    assert "Red outline: a large difference" in rows
    assert "stands out from its strip" not in " ".join(rows)


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
    assert "A patch outlined in red has a large colour difference" in src[i:i + 2500]
    assert "A red outline is a reason to look, not proof of a mistake." in src


def test_the_card_and_the_help_name_the_tab_the_limit_is_on(qapp):
    """Review of d222fce0: both pointed at Preferences ▸ Beta, but the limit
    (with the reading-engine block it belongs to) moved to the Measurement tab
    on 2026-08-13. Asked of the dialog itself, so a later move is caught."""
    from PyQt6.QtWidgets import QLabel

    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.tabs.tab_measure import TabMeasure
    d = SettingsDialog(AppSettings(), None)
    try:
        label = next(w for w in d.findChildren(QLabel)
                     if w.text() == "<b>Patch error limit</b>")
        tab = None
        for i in range(d._tabs.count()):
            if d._tabs.widget(i).isAncestorOf(label):
                tab = d._tabs.tabText(i)
        assert tab, "the limit is on no tab"
    finally:
        d.deleteLater()
    rows = _rows(qapp, {"warn": True, "warn_de": 50.0})
    assert f"See Preferences ▸ {tab} for" in rows, rows
    help_src = inspect.getsource(TabMeasure)
    assert f"set in Preferences ▸ {tab} \"" in help_src


def test_the_sentences_are_separated_by_blank_lines(qapp):
    """Knut, #182 5960405382: "each sentence ... are cramped together, so a
    new-line between each sentence should be added"."""
    rows = _rows(qapp, {"warn": True, "warn_de": 50.0, "fenced": False})
    i = rows.index("Either a misread, or a colour")
    j = rows.index("Same value after a re-read:")
    assert rows[i - 1] == "" and rows[j - 1] == ""
    assert rows[rows.index("See Preferences ▸ Measurement for") - 1] == ""
