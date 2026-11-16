"""The patch set editor's readout and two of its texts (4.3.42, the i1iSis
showcase findings of 2026-11-15).

F1: the readout beside the source buttons called an i1iSis chart "-ii1"
(printtarg's flag for the i1Pro), and at the window's normal size it was
clipped to nothing (Ignored width policy in a full row), so it was seen only
as hover text. It now has its own row, and names the instrument a loaded
chart FILE was laid out for, by name.

N2: "Ensure unique colours" said no patch is printed twice, while "Pure
white & black: each 2" prints white and black twice on purpose. Both are
true now: the copies are named as the one exception.

N3 (not changed): the fill's "pages" unit stays hidden. Pages are Create
Chart's (#93), and the editor's page capacity is worked out from its hidden
placeholder layout (i1Pro or ColorMunki on A4, `_engine_cap_per_page`), not
from the layout Create Chart will use, so for an i1iSis chart it would be
wrong.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings  # noqa: E402


def _ti2(path, instrument):
    rows = "\n".join(f'{i + 1} "A{i + 1}" {i * 10.0:.1f} 50.0 50.0 1 1 1'
                     for i in range(8))
    path.write_text(
        'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ layout engine"\n'
        f'TARGET_INSTRUMENT "{instrument}"\nCOLOR_REP "iRGB"\n'
        'PAPER_SIZE "210.0x297.0"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\n\nNUMBER_OF_SETS 8\nBEGIN_DATA\n' + rows
        + "\nEND_DATA\n", encoding="latin-1")
    return path


def _dialog(tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    return Ti2RelayoutDialog(ArgyllRunner(s), s, None)


def test_the_instrument_of_an_isis_chart_is_the_isis(tmp_path):
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    from workflow.ti2_relayout import ChartSpec
    isis = _ti2(tmp_path / "isis.ti2", "X-Rite i1iSis")
    spec = ChartSpec.from_ti2(isis)
    assert spec.instrument_flag == "i1"            # why it read "-ii1"
    assert Ti2RelayoutDialog._instrument_of_chart(isis, spec) == "i1iSis"
    i1 = _ti2(tmp_path / "i1.ti2", "X-Rite i1Pro")
    assert Ti2RelayoutDialog._instrument_of_chart(
        i1, ChartSpec.from_ti2(i1)) == "i1Pro / i1Pro 2 / i1Pro 3"
    odd = _ti2(tmp_path / "odd.ti2", "Some Other Reader")
    assert Ti2RelayoutDialog._instrument_of_chart(
        odd, ChartSpec.from_ti2(odd)) == "Some Other Reader"


def test_the_readout_names_the_instrument_and_has_room(qapp, tmp_path):
    from workflow.ti2_relayout import ChartSpec
    dlg = _dialog(tmp_path)
    try:
        isis = _ti2(tmp_path / "isis.ti2", "X-Rite i1iSis")
        dlg._spec = ChartSpec.from_ti2(isis)
        dlg._chart_note = "Loaded isis.ti2"
        dlg._readout_instrument = dlg._instrument_of_chart(isis, dlg._spec)
        dlg._refresh_info()
        text = dlg._info.text()
        assert text.startswith("Loaded isis.ti2: ")
        assert "laid out for the i1iSis on A4" in text
        assert "-i" not in text and "—" not in text
        dlg._readout_instrument = ""                 # a patch set made here
        dlg._refresh_info()
        assert "laid out" not in dlg._info.text()
        # its own row, so it is not squeezed to nothing at the normal size
        dlg.resize(1280, 820)
        dlg.show()
        qapp.processEvents()
        assert dlg._info.width() > 600, dlg._info.width()
        assert dlg._info.isVisible()
    finally:
        dlg.hide()
        dlg.dispose()


def test_ensure_unique_colours_names_the_white_and_black_copies(qapp, tmp_path):
    from ui.dialogs import ti2_relayout_dialog as M
    help_text = " ".join(M._GEN_SETS_HELP.split())
    assert ("The copies of pure white and black that 'Pure white & black' "
            "adds are the one exception") in help_text
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "n.ini"), QSettings.Format.IniFormat)
    dlg = M._NewChartDialog(s, None)
    try:
        tip = dlg._gen_unique.toolTip()
        assert "so no colour is printed twice, except the copies of pure white" in tip
        assert "no patch is printed twice." not in tip
    finally:
        dlg.deleteLater()
