"""Create Chart's big number ends in a mark, like every other tab's headline.

Each tab closes its headline with one piece of punctuation in that tab's own
spectrum colour, italic:

    Print          "Feed the beast!"   amber    tab_print.py:552
    Measure        "Keep calm!"        green    tab_measure.py:1578
    Build Profile  "Ready to build?"   cyan     tab_profile.py:490
    Check & Refine "Are you nervous?"  violet   tab_check_refine.py:380

Create Chart is the first tab, its colour is magenta, and its headline — the
calculated patch count — was the only one that just stopped (Basti, 2026-08-27).

It reads well in both themes for different reasons. In DARK the number is
already `SPEC_MAGENTA` (`ui/styles.py`), so the italic is what marks the "!"
out. In LIGHT the number is `LM_TEXT_MAIN` (`ui/light_styles.py`), so the
magenta mark is a true accent against neutral text — the same shape as the
sibling headlines.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t.resize(1180, 980)
    t._switch_mode("guided")
    t.show()
    qapp.processEvents()
    return t


def test_a_real_count_ends_in_an_exclamation_mark(tab, qapp):
    from ui.styles import SPEC_MAGENTA

    tab._update_patch_count()
    qapp.processEvents()
    text = tab._patch_count_lbl.text()
    assert text.rstrip().endswith("</span>"), f"no mark on the count: {text!r}"
    assert "!" in text and SPEC_MAGENTA in text, (
        f"the mark is not in the tab's accent colour: {text!r}")
    assert "italic" in text


def test_an_unknown_count_keeps_its_question_mark_and_gains_the_accent(tab):
    from ui.styles import SPEC_MAGENTA

    tab._patch_count_lbl.setText(tab._count_with_accent("", mark="?"))
    text = tab._patch_count_lbl.text()
    assert "?" in text and SPEC_MAGENTA in text and "!" not in text


def test_the_label_renders_markup_rather_than_printing_it(tab):
    """The placeholder "—" carries no tags, and Qt's auto-detection would flip
    the label back to plain text — which would print the raw <span> at 56 px."""
    from PyQt6.QtCore import Qt

    assert tab._patch_count_lbl.textFormat() == Qt.TextFormat.RichText


def test_the_number_is_escaped_before_it_is_rendered(tab):
    """A label that renders markup must never be handed unescaped text. The
    count is built from an int today; this is the guard for the day it is not.
    """
    out = tab._count_with_accent("<b>7</b>")
    assert "&lt;b&gt;7&lt;/b&gt;" in out
    assert "<b>" not in out.split("<span")[0]


def test_every_tab_headline_carries_its_own_accent_colour(qapp):
    """The pattern this joins, asserted so nobody quietly drops one — or gives
    two tabs the same colour."""
    import inspect

    from ui import styles

    wanted = {
        "ui.tabs.tab_print": styles.SPEC_AMBER,
        "ui.tabs.tab_measure": styles.SPEC_GREEN,
        "ui.tabs.tab_profile": styles.SPEC_CYAN,
        "ui.tabs.tab_check_refine": styles.SPEC_VIOLET,
        "ui.tabs.tab_chart": styles.SPEC_MAGENTA,
    }
    for name, colour in wanted.items():
        mod = __import__(name, fromlist=["_"])
        src = inspect.getsource(mod)
        assert 'font-style: italic;' in src, f"{name} has no accented headline"
        const = [k for k, v in vars(styles).items()
                 if k.startswith("SPEC_") and v == colour][0]
        assert const in src, f"{name} should use {const} for its headline mark"
    assert len(set(wanted.values())) == len(wanted), "two tabs share a colour"
