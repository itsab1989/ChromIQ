"""The "Some limits cannot be checked" strip is shortened to its OWN text
area, so its "…" is drawn whole (challenge 2 of beta 42, #7; B8-1006).

It was elided to the WINDOW's width less 60 px, which is wider than the
strip's text area (the label less its 10 px padding and 1 px border a side):
measured on screen at 820 px, a 758 px line in a 754 px text area, and the
"…" came out as one dot (crop-narrow-strip-end.png).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_shortened_strip_fits_inside_its_box_at_every_width(
        tmp_path, qapp):
    """MUTATION, proved to land: shorten to the old `width` (the window's
    width less 60) instead of `min(width, self._strip_text_width())` (the
    line overruns its box)."""
    from PyQt6.QtGui import QFontMetrics
    import ui.dialogs.measurement_report_dialog as mrd
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, _run, vs = _messy_project(tmp_path, dates=1)
    dlg = mrd.MeasurementReportDialog(s, None,
                                      initial_ti3=vs[-1].measurement_ti3)
    dlg.show()
    qapp.processEvents()
    full = ("Some limits cannot be checked on this chart:\n"
            + "\n".join(f"• Row number {k} with a long name: why not" for k
                        in range(12)))
    try:
        seen = []
        for w in (1700, 1234, 1000, 900, 820, 760):
            dlg.resize(w, dlg.height())
            qapp.processEvents()
            dlg._set_strip(full)
            qapp.processEvents()
            qapp.processEvents()
            lab = dlg._mismatch
            assert lab.isVisible()
            if lab.wordWrap():
                continue
            text = lab.text()
            assert text.endswith("…"), text[-20:]
            fm = QFontMetrics(lab.font())
            room = lab.width() - 2 * dlg._STRIP_SIDE_PX
            seen.append((w, fm.horizontalAdvance(text), room))
            assert fm.horizontalAdvance(text) <= room, (
                w, "the strip's line is wider than its box, so its '…' is "
                "cut", fm.horizontalAdvance(text), room)
        assert seen, "no width shortened the strip; the test proves nothing"
    finally:
        dlg.close()
