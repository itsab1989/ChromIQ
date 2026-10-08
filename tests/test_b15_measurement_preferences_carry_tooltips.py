"""Beta 15 text pass (Basti, 2026-10-08: every user-facing text "friendly,
complete, easy to understand, and correct"): in Preferences ▸ Measurement both
checkboxes carry their full help as a tooltip, and both neighbour-check buffers
carry one on their label AND on their box.

Until then the neighbour check's checkbox said only "Checked again after each
strip ..." and the two buffer fields said nothing at all on hover.
"""
from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

from core.i18n import tr


def _dialog(tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return SettingsDialog(s, None)


def _label(dlg, text: str) -> QLabel:
    hits = [w for w in dlg.findChildren(QLabel) if w.text() == text]
    assert len(hits) == 1, (text, len(hits))
    return hits[0]


def test_both_checkboxes_carry_their_full_help(qapp, tmp_path):
    from ui.dialogs import settings_dialog as sd
    dlg = _dialog(tmp_path)
    try:
        assert dlg._patch_fence_check.toolTip() == \
            tr(sd.STRIP_TEST_HELP).replace("**", "")
        assert dlg._patch_neighbour_check.toolTip() == \
            tr(sd.NEIGHBOUR_CHECK_HELP).replace("**", "")
        assert "**" not in dlg._patch_neighbour_check.toolTip()
    finally:
        dlg.close()


def test_both_buffers_carry_a_tooltip_on_label_and_box(qapp, tmp_path):
    from ui.dialogs import settings_dialog as sd
    dlg = _dialog(tmp_path)
    try:
        acc = tr(sd.NB_BUFFER_ACCURATE_TIP)
        est = tr(sd.NB_BUFFER_ESTIMATED_TIP)
        assert acc and est and acc != est
        assert dlg._patch_neighbour_acc_spin.toolTip() == acc
        assert dlg._patch_neighbour_spin.toolTip() == est
        assert _label(dlg, tr("Buffer on a chart made with a pre-conditioning "
                              "profile:")).toolTip() == acc
        assert _label(dlg, tr("Buffer on a chart with estimated colours (most "
                              "charts):")).toolTip() == est
    finally:
        dlg.close()


def test_the_buffer_tooltips_state_the_rule_and_the_defaults():
    """The words follow workflow/neighbour_check.py: the buffer is compared
    with the MEDIAN excess, and it is one of two conditions (the patch must
    also be the one that is off), so the check "can" outline, not "does"."""
    from ui.dialogs import settings_dialog as sd
    from workflow import neighbour_check as N
    for tip, default in ((sd.NB_BUFFER_ACCURATE_TIP, N.BUFFER_ACCURATE_DE),
                         (sd.NB_BUFFER_ESTIMATED_TIP, N.BUFFER_DE)):
        assert "the middle value over the patches compared" in tip
        assert "can give it a red outline" in tip
        assert f"Default {default:g} ΔE." in tip
        assert "—" not in tip
    assert "pre-conditioning profile" in sd.NB_BUFFER_ACCURATE_TIP
    assert "estimated colours (most charts)" in sd.NB_BUFFER_ESTIMATED_TIP


def test_a_tooltip_reused_while_shown_is_fitted_to_its_new_text(qapp):
    """Pointing straight from the neighbour check's long help to a buffer
    field, Qt reuses the tooltip still on screen and sends no Show, so the
    box kept the long help's size (measured on screen: 460 x 565 around four
    lines). TooltipWrapFilter refits on the move a reuse sends."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QToolTip, QWidget
    from ui.widgets import CompositeAppFilter
    filt = CompositeAppFilter(qapp)
    qapp.installEventFilter(filt)
    w = QWidget()
    w.resize(200, 100)
    w.show()
    QTest.qWait(200)
    try:
        long_text = " ".join(["A long tooltip sentence that wraps."] * 40)
        short_text = " ".join(["Short, but still wrapping text."] * 4)
        QToolTip.showText(w.mapToGlobal(QPoint(10, 10)), long_text, w)
        QTest.qWait(300)

        def tip():
            return next(t for t in QApplication.topLevelWidgets()
                        if t.metaObject().className() == "QTipLabel"
                        and t.isVisible())
        tall = tip().height()
        QToolTip.showText(w.mapToGlobal(QPoint(60, 40)), short_text, w)
        QTest.qWait(300)
        t = tip()
        assert t.text() == short_text
        assert t.height() < tall / 3, (t.height(), tall)
        assert t.height() == t.heightForWidth(t.width())
    finally:
        QToolTip.hideText()
        qapp.removeEventFilter(filt)
        w.close()
