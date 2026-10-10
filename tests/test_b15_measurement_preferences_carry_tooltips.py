"""Preferences ▸ Measurement: every test and parameter of the misread table
carries its one-sentence description as a tooltip, on its name and on its
boxes (beta 17, Knut #182 6084176226: "The One-sentence description you made
for each parameter or test can be shown as tool-tip hovering the name";
the wording approved in 6085694445, the neighbour check's and the neighbour
limit's adjusted to the colour-neighbour radius). Beta 15 put the full help
on two checkboxes and gave two "buffer" fields a tooltip; both are gone.
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


TIPS = {
    "Patch error limit": "The largest ΔE*ab a patch may be from its expected "
                         "colour before it is outlined red.",
    "Strip test": "A patch past the patch error limit is outlined red only "
                  "if it also stands out from the other patches of its own "
                  "strip.",
    "Neighbour check": "Each patch is compared with the 2 to 4 read patches "
                       "nearest to it in expected colour within the "
                       "colour-neighbour radius, and outlined red if it is "
                       "clearly further from its expected colour than they "
                       "are.",
    "Neighbour limit": "How many ΔE*ab further from its expected colour than "
                       "the median of its 2 to 4 nearest patches a patch may "
                       "be.",
    "Same-reading tolerance": "The largest ΔE*ab between two readings of one "
                              "patch for a re-read to count as the same "
                              "colour.",
}


def test_the_tooltips_are_the_approved_sentences():
    from ui.dialogs import settings_dialog as sd
    assert sd.PATCH_ERROR_LIMIT_TIP == TIPS["Patch error limit"]
    assert sd.STRIP_TEST_TIP == TIPS["Strip test"]
    assert sd.NEIGHBOUR_CHECK_TIP == TIPS["Neighbour check"]
    assert sd.NEIGHBOUR_LIMIT_TIP == TIPS["Neighbour limit"]
    assert sd.SAME_READING_TIP == TIPS["Same-reading tolerance"]


def test_every_name_and_box_carries_its_tooltip(qapp, tmp_path):
    from ui.dialogs import settings_dialog as sd
    dlg = _dialog(tmp_path)
    try:
        names = {w.text().replace("<b>", "").replace("</b>", ""): w
                 for w in dlg._misread_table.findChildren(QLabel)}
        for name, tip in (
                (sd.PATCH_ERROR_LIMIT_NAME, sd.PATCH_ERROR_LIMIT_TIP),
                (sd.STRIP_TEST_NAME, sd.STRIP_TEST_TIP),
                (sd.NEIGHBOUR_CHECK_NAME, sd.NEIGHBOUR_CHECK_TIP),
                (sd.NEIGHBOUR_LIMIT_NAME, sd.NEIGHBOUR_LIMIT_TIP),
                (sd.NEIGHBOUR_RADIUS_NAME, sd.NEIGHBOUR_RADIUS_TIP),
                (sd.SAME_READING_NAME, sd.SAME_READING_TIP)):
            assert names[tr(name)].toolTip() == tr(tip), name
        for k in ("estimated", "accurate", "verification", "calibration"):
            assert dlg._patch_limit_spins[k].toolTip() == \
                tr(sd.PATCH_ERROR_LIMIT_TIP)
            assert dlg._strip_test_checks[k].toolTip() == tr(sd.STRIP_TEST_TIP)
            assert dlg._neighbour_limit_spins[k].toolTip() == \
                tr(sd.NEIGHBOUR_LIMIT_TIP)
            assert dlg._neighbour_radius_spins[k].toolTip() == \
                tr(sd.NEIGHBOUR_RADIUS_TIP)
        assert dlg._same_reading_spin.toolTip() == tr(sd.SAME_READING_TIP)
        assert dlg._patch_neighbour_check.toolTip() == \
            tr(sd.NEIGHBOUR_CHECK_TIP)
    finally:
        dlg.close()


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
