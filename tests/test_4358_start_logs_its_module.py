"""4.3.58 item 18: every START names the Measure module in the app log.

A tester's first START after each launch read with -S, no -T and M0, the next one
with M1 and -T 0.4, and nothing in the log said why. Driven on screen (4.3.56 and
4.3.57 alike): the tab opens on GUIDED at every launch, and Guided and Manual keep
their own suppress / tolerance / filter values, so a START pressed before switching
to Manual reads with Guided's set. Not a settings fault; the log just has to say
which module it was.
"""
from __future__ import annotations

import logging
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.settings import AppSettings                 # noqa: E402


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t._ti1_path = tmp_path / "chart.ti1"
    return t


@pytest.mark.parametrize("module", ["guided", "manual"])
def test_start_names_the_module_it_reads_with(tab, caplog, module):
    tab._switch_mode(module)
    with caplog.at_level(logging.INFO, logger="ui.tabs.tab_measure"):
        tab._collect_params()
    lines = [r.getMessage() for r in caplog.records
             if r.getMessage().startswith("measure start: module")]
    assert lines == [f"measure start: module {module}"]


def test_the_tab_opens_on_guided(tab):
    """The fact the item turned on: a new tab (= every launch) stands on Guided."""
    assert tab._current_mode() == "guided"
