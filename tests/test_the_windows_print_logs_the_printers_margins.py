"""The Windows print route writes the printer's own unprintable margins into
the log (jctay, forum 149836: helper markers in the TIFF, missing on the
SELPHY print, with nothing on record about what the driver clips)."""
from __future__ import annotations

import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_the_margins_are_logged_in_millimetres(qapp, caplog):
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize
    from PyQt6.QtPrintSupport import QPrinter
    from ui.tabs.tab_print import TabPrint

    pr = QPrinter(QPrinter.PrinterMode.HighResolution)
    lay = QPageLayout(QPageSize(QPageSize.PageSizeId.A6),
                      QPageLayout.Orientation.Portrait,
                      QMarginsF(3, 4, 5, 6), QPageLayout.Unit.Millimeter,
                      QMarginsF(3, 4, 5, 6))
    pr.setPageLayout(lay)
    with caplog.at_level(logging.INFO, logger="ui.tabs.tab_print"):
        TabPrint._log_printer_margins(pr, 100 * 72 / 25.4, 148 * 72 / 25.4)
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "paper 100.0 x 148.0 mm" in text, text
    assert "cannot print within" in text


def test_a_printer_that_cannot_answer_never_stops_the_print(caplog):
    from ui.tabs.tab_print import TabPrint

    class Broken:
        def pageLayout(self):
            raise RuntimeError("no driver")
    TabPrint._log_printer_margins(Broken(), 0.0, 0.0)     # must not raise
