"""The calibration measurement's path is readable in the Light theme.

4.3.5 beta 6 combined review: Build Profile with Run type = Calibration showed
the chosen ``.ti3`` in ``#e6e6e6``, the Dark theme's text colour, on every
theme, so in Light the path was near-white on white. The label now carries no
colour of its own and takes the appearance's text colour from the stylesheet.
"""
from __future__ import annotations

import inspect
import types
from pathlib import Path

from PyQt6.QtWidgets import QLabel

from ui.tabs.tab_profile import TabProfile


def test_the_path_label_has_no_colour_of_its_own(qapp):
    stub = types.SimpleNamespace(_pc_ti3_lbl=QLabel())
    TabProfile._pc_show_ti3_path(stub, Path("/x/cal.ti3"))
    assert stub._pc_ti3_lbl.text() == str(Path("/x/cal.ti3"))
    assert "color" not in stub._pc_ti3_lbl.styleSheet()


def test_no_calibration_path_is_painted_the_dark_themes_text_colour():
    src = inspect.getsource(TabProfile)
    assert '_pc_ti3_lbl.setStyleSheet("color: #e6e6e6' not in src
