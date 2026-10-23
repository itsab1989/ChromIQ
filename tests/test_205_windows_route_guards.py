"""#205 review, finding 10: the guards a mutation run could remove with every
test still green (07_review/mutate_out.txt), now each held by a test; and
findings 6 and 7 (a chart ChromIQ cannot read is not "Windows did not
accept the print job"; "&" in a printer name is not a mnemonic).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                       # noqa: E402

from core.settings import AppSettings                    # noqa: E402
from workflow import win_spooler                          # noqa: E402
from tests.test_205_windows_direct_print import (         # noqa: E402,F401
    _FakeDialog, _FakePainter, _FakePrinter, _rgb_tiff, dialog_route, _REAL_PRINT_NATIVE_QT)


def _tab(tmp_path):
    from ui.tabs.tab_print import TabPrint
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "g.ini"), QSettings.Format.IniFormat)
    return TabPrint(s)


# ---- the macOS-only questions stay macOS-only ---------------------------------
def test_the_like_preview_question_is_never_asked_off_macos(qapp, tmp_path, monkeypatch):
    from ui.tabs import tab_print as tp
    from workflow import ppd_color as forms
    tab = _tab(tmp_path)
    monkeypatch.setattr(tab, "_ps_form_stored", lambda: forms.POSTSCRIPT_AS_MACOS)
    monkeypatch.setattr(tab, "_is_postscript_queue", lambda p: True)
    monkeypatch.setattr(tp, "is_macos", lambda: True)
    assert tab._direct_print_needs_like_preview_question("Q") is True
    monkeypatch.setattr(tp, "is_macos", lambda: False)
    assert tab._direct_print_needs_like_preview_question("Q") is False


def test_the_windows_route_never_gets_a_paper_profile_row(qapp, tmp_path, monkeypatch):
    """A Canon/Epson-style paper profile is a CUPS job feature; the raw route
    carries none, whatever the PPD looks like."""
    from ui.tabs.tab_print import TabPrint
    from workflow import measurement_messages as MM
    from workflow.cups_printer import CupsRawPrinter
    from workflow.win_raw_printer import WindowsRawPrinter

    class _PP:
        label = "Canon Photo Paper Pro Luster"
        known, is_default = True, True

        class rule:
            own_colour_off_needs_paper_profile = False

    monkeypatch.setattr(CupsRawPrinter, "_reference_paper_profile",
                        staticmethod(lambda tiff, cfg: _PP()))

    class _Self:
        _printer = WindowsRawPrinter()
    rows = TabPrint._colour_rows(_Self(), "Q", {}, tmp_path / "x.tif")
    assert [r[0] for r in rows] == [MM._PRINT_ROW_COLOUR]

    class _Mac:
        _printer = CupsRawPrinter()
    rows = TabPrint._colour_rows(_Mac(), "Q", {}, tmp_path / "x.tif")
    assert MM._PRINT_ROW_PAPER_PROFILE in [r[0] for r in rows]


# ---- a chart a little larger than the paper (jctay 149803, 4.3.10) ----------
@pytest.mark.parametrize("over, margin, prints", [
    (1.015, True, True),     # 1.5 % over, wide white margins: 100 %, no question
    (1.015, False, False),   # 1.5 % over, ink to the edge: M-PRINT-CHART-CUT
    (1.03, True, False)])    # more than 5 mm over: M-PRINT-WIN-DIALOG-TOO-BIG
def test_a_chart_a_little_larger_than_the_paper(dialog_route, tmp_path, over,
                                                 margin, prints):
    """Until 4.3.10 a 2 % slack printed any chart up to 2 % larger, centred,
    whatever was cut. Now only empty margin may be left off (workflow.overhang),
    and the chart is never shrunk."""
    import tifffile
    tab, events = dialog_route
    w_px = int(round(595 * over / 72 * 300))
    h_px = int(round(842 * over / 72 * 300))
    arr = np.full((h_px, w_px, 3), 255, np.uint8)
    inset = int(25 / 25.4 * 300) if margin else 0          # 25 mm of white
    arr[inset:h_px - inset, inset:w_px - inset] = (10, 200, 30)
    tiff = tmp_path / "c.tif"
    tifffile.imwrite(str(tiff), arr, photometric="rgb", resolution=(300, 300),
                     resolutionunit=2)
    # an i1Pro chart (10 mm of white kept around its patches); a chart whose
    # instrument is unknown keeps the most any instrument needs
    (tmp_path / "c.ti2").write_text('CTI2\nTARGET_INSTRUMENT "X-Rite i1 Pro"\n',
                                    encoding="utf-8")
    tab._print_native_qt([(tiff, 0)])
    assert bool(_FakePainter.draws) is prints
    assert events[-1] == ("record", prints)
    if prints:
        (_t, _r, _x, _y, w, h, _iw), = _FakePainter.draws
        assert w == pytest.approx(w_px * 2) and h == pytest.approx(h_px * 2)
    else:
        from workflow import measurement_messages as MM
        refused = [e for e in events if e[0] == "refused"]
        want = (MM.M_PRINT_CHART_CUT.title if over < 1.02
                else MM.M_PRINT_WIN_DIALOG_TOO_BIG.title)
        assert refused and refused[0][1] == want


# ---- the spooler ----------------------------------------------------------------
def test_a_job_being_deleted_is_not_stuck(monkeypatch):
    J = win_spooler.JobFacts
    monkeypatch.setattr(win_spooler, "jobs", lambda p: [
        J(1, "a", "RAW", win_spooler.JOB_STATUS_ERROR, "", 1),
        J(2, "b", "RAW", win_spooler.JOB_STATUS_ERROR | win_spooler.JOB_STATUS_DELETING, "", 1),
        J(3, "c", "RAW", win_spooler.JOB_STATUS_PAUSED | win_spooler.JOB_STATUS_DELETED, "", 1),
        J(4, "d", "RAW", 0, "", 1),
    ])
    assert win_spooler.stuck_jobs("Q") == [1]


def test_the_windows_printer_list_comes_from_the_spooler(monkeypatch):
    from workflow import print_manager as pm
    monkeypatch.setattr(pm.sys, "platform", "win32")
    monkeypatch.setattr(pm, "CUPS_AVAILABLE", False)
    monkeypatch.setattr(win_spooler, "list_printers", lambda: ["zeta", "Alpha", "beta"])
    assert pm.PrintModule().detect_printers() == ["Alpha", "beta", "zeta"]
    monkeypatch.setattr(pm, "CUPS_AVAILABLE", True)       # a fake CUPS keeps CUPS
    assert pm._windows_spooler() is False


def test_the_ppd_of_a_windows_queue_is_its_drivers(monkeypatch):
    from workflow import ppd_color
    monkeypatch.setattr(ppd_color.sys, "platform", "win32")
    monkeypatch.setattr(win_spooler, "ppd_path", lambda q: r"C:\drv\%s.ppd" % q)
    assert ppd_color.ppd_path_for_queue("Q") == r"C:\drv\Q.ppd"


# ---- finding 6: ChromIQ's own failure is said as ChromIQ's ----------------------
def test_a_chart_that_cannot_be_read_is_not_a_spooler_refusal(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from ui.tabs import tab_print as tp
    from workflow.cups_printer import PrintConfig
    from workflow.win_raw_printer import WindowsRawPrinter
    bad = tmp_path / "broken.tif"
    bad.write_bytes(b"not a tiff")
    pr = WindowsRawPrinter()
    monkeypatch.setattr(win_spooler, "submit", lambda *a, **k: pytest.fail("submitted"))
    codes = []
    pr.print_job_ps(bad, PrintConfig("Q"), on_finish=codes.append)
    assert codes == [-1] and pr.last_error_is_chart and pr.last_chart_name == "broken.tif"
    tab = _tab(tmp_path)
    tab._printer = pr
    monkeypatch.setattr(tp, "is_windows", lambda: True)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda parent, title, body: shown.append((title, body))))
    monkeypatch.setattr(tab, "_show_print_refusal",
                        lambda *a: pytest.fail("shown as a spooler refusal"))
    tab._on_print_done(-1)
    assert shown and "broken.tif" in shown[0][1]


# ---- finding 7: "&" in a printer name on a button --------------------------------
def test_an_ampersand_in_a_printer_name_is_no_mnemonic(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    tab = _tab(tmp_path)
    seen = []

    def _exec(box):
        seen.extend(b.text() for b in box.buttons())
        return 0
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    assert tab._confirm_other_printer("Office Inkjet", "HP & Co Laser") is False
    assert "Print on HP && Co Laser" in seen


# ---- regression review of the review's fixes: two minor notes ------------------
def test_a_ppd_that_includes_itself_is_read_once(tmp_path):
    from workflow.win_raw_printer import read_ppd
    a = tmp_path / "a.ppd"
    b = tmp_path / "b.ppd"
    a.write_text('*PPD-Adobe: "4.3"\n*Include: "b.ppd"\n*Include: "a.ppd"\n*A: "1"\n',
                 encoding="latin-1")
    b.write_text('*B: "2"\n*Include: "a.ppd"\n', encoding="latin-1")
    text = read_ppd(a)
    assert text.count('*A: "1"') == 1 and text.count('*B: "2"') == 1


def test_the_failure_window_names_the_chart_not_a_temporary_page(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from ui.tabs import tab_print as tp
    from workflow.win_raw_printer import WindowsRawPrinter
    tab = _tab(tmp_path)
    pr = WindowsRawPrinter()
    pr.last_error, pr.last_error_is_chart, pr.last_chart_name = "boom", True, "tmpab12cd.tif"
    tab._printer = pr
    tab._page_name_for_messages = "WinPrint-RGB_02.tif"
    monkeypatch.setattr(tp, "is_windows", lambda: True)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical",
                        staticmethod(lambda parent, title, body: shown.append(body)))
    tab._on_print_done(-1)
    assert "WinPrint-RGB_02.tif" in shown[0] and "tmpab12cd" not in shown[0]
