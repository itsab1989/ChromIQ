"""K33 (B8-992, B8-993): the "Judged against" help window is wide, and it
says when each standard's sets are the right choice.

Knut, #182 5816565326: *"The help text window for Judged against is very
tall, so the window should be made wider. Also, I cannot find any
recommendation of what type of situation the ISO limit sets normally would be
used for."* Measured on screen before: 616 x 971 px on a 1728 x 1079 screen.

Pinned, each with the mutation that turns it red:

* both ⓘ of the report window's settings open at least 900 px wide
  (MUTATION: put `min_width=460` back on either);
* the "Judged against" help and the Report limits window's title help both
  carry the paragraph (MUTATION: drop it from either);
* the paragraph names contract proofs for ISO 12647-7, validation prints for
  ISO 12647-8, what the Custom and ChromIQ sets are for, and that ChromIQ
  never certifies (MUTATION: reword any of those away).
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from core.i18n import tr


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _buttons(tmp_path, qapp):
    from tests.test_the_report_type_pulldown_stores_on_the_run import _dialog
    from ui.tooltip_button import TooltipButton
    dlg, _run = _dialog(tmp_path, qapp)
    return dlg, {b._title: b for b in dlg.findChildren(TooltipButton)}


@pytest.mark.parametrize("title", ["Judged against", "Report type"])
def test_the_help_window_opens_wide(title, tmp_path, qapp):
    from ui.dialogs.measurement_report_dialog import JUDGED_AGAINST_HELP_WIDTH
    from ui.tooltip_button import _InfoDialog
    assert JUDGED_AGAINST_HELP_WIDTH >= 900
    dlg, buttons = _buttons(tmp_path, qapp)
    try:
        btn = buttons[tr(title)]
        assert btn._min_width == JUDGED_AGAINST_HELP_WIDTH
        info = _InfoDialog(btn._title, btn.dialog_body(), dlg, btn._min_width)
        try:
            assert info.width() >= 900, info.width()
        finally:
            info.close()
            info.deleteLater()
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()


def test_the_paragraph_is_in_both_helps(tmp_path, qapp):
    from ui.dialogs.measurement_report_dialog import _ISO_USE_HELP
    dlg, buttons = _buttons(tmp_path, qapp)
    try:
        assert tr(_ISO_USE_HELP) in buttons[tr("Judged against")].dialog_body()
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.tooltip_button import TooltipButton
    from core.settings import AppSettings
    lim = ThresholdsDialog(AppSettings())
    try:
        bodies = [b.dialog_body() for b in lim.findChildren(TooltipButton)
                  if b._title == tr("Report limits")]
        assert bodies and tr(_ISO_USE_HELP) in bodies[0]
    finally:
        lim.close()
        lim.deleteLater()
        QApplication.processEvents()


def test_the_paragraph_says_what_each_set_is_for_and_claims_nothing():
    from ui.dialogs.measurement_report_dialog import _ISO_USE_HELP as p
    assert "ISO 12647-7 is the standard for contract proofs" in p
    assert "ISO 12647-8 is the standard for validation prints" in p
    assert "less strictly than a contract proof" in p
    assert "Custom ISO sets are an alternative" in p
    assert "researched from industry practice" in p
    assert "ChromIQ's own sets are for your own printer" in p
    assert "does not certify" in p
    assert "—" not in p
    for word in ("conforms to ISO", "is compliant", "certified"):
        assert word not in p
