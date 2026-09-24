"""Preferences > Reports: the three report-title boxes start at one left
edge (B8-980).

Knut, #182 5815501486 (2026-09-24): *"In Preferences --> Reports tab, frame
'Default measurement report title....': The three input boxes' left edges
should be aligned to the left edge of the 'Verification measurement runs'
input box. This makes the boxes look more orderly."*

Measured on screen before the change: the boxes started at 224, 243 and 216 px
in English and 202, 209 and 208 px in German, each wherever its own label
ended. The labels now share one grid column as wide as the longest of them,
so in every language the boxes share one edge, and in English that edge is the
"Verification measurement runs" box's, the one Knut named. The on-screen proof
is `scripts/drive_b42_x_and_prefs.py`; this reads the same geometry offscreen,
in every shipped language, because a longer label in one of them is exactly
where such an edge would drift.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QPoint, QSettings                # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel          # noqa: E402

from core import i18n                                      # noqa: E402
from tests.helpers.languages import shipped_languages     # noqa: E402

EDITS = ("_report_title_prof_edit", "_report_title_verify_edit",
         "_report_title_cal_edit")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _prefs(qapp, tmp_path, lang):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    sd = SettingsDialog(st, None)
    edit = getattr(sd, EDITS[0])
    for i in range(sd._tabs.count()):
        if sd._tabs.widget(i).isAncestorOf(edit):
            sd._tabs.setCurrentIndex(i)
            break
    sd.show()
    qapp.processEvents()
    return sd


def _lefts(sd):
    return [getattr(sd, a).mapTo(sd, QPoint(0, 0)).x() for a in EDITS]


@pytest.mark.parametrize("lang", shipped_languages())
def test_the_three_boxes_share_one_left_edge(qapp, tmp_path, lang):
    """MUTATION: put each label and box back in a row of their own and this
    goes red in every language."""
    before = i18n.current_language()
    i18n.set_language(lang)
    try:
        sd = _prefs(qapp, tmp_path, lang)
        try:
            for width in (sd.width(), sd.width() + 400, 1):
                sd.resize(width, sd.height())
                qapp.processEvents()
                lefts = _lefts(sd)
                assert len(set(lefts)) == 1, (lang, sd.width(), lefts)
                # …and each box keeps room to type in
                assert min(getattr(sd, a).width() for a in EDITS) >= 150, (
                    lang, sd.width())
                # the edge is where the LONGEST label ends, so no label is cut
                # and none runs under its box
                for a in EDITS:
                    edit = getattr(sd, a)
                    lab = next(w for w in sd.findChildren(QLabel)
                               if w.buddy() is edit)
                    assert lab.width() >= lab.sizeHint().width(), (
                        lang, lab.text(), "cut")
                    assert (lab.mapTo(sd, QPoint(0, 0)).x() + lab.width()
                            <= edit.mapTo(sd, QPoint(0, 0)).x()), (
                        lang, lab.text(), "under its box")
        finally:
            sd.hide()
            sd.deleteLater()
    finally:
        i18n.set_language(before or "en")


def test_in_english_the_edge_is_the_verification_boxs(qapp, tmp_path):
    """Knut named the box to align to; in English its label is the longest,
    so the shared edge is the one it already had, not a new one to the left
    that would cut its label."""
    before = i18n.current_language()
    i18n.set_language("en")
    sd = _prefs(qapp, tmp_path, "en")
    try:
        verify = sd._report_title_verify_edit
        lab = next(w for w in sd.findChildren(QLabel)
                   if w.buddy() is verify)
        assert lab.text() == "Verification measurement runs:"
        right_of_label = lab.mapTo(sd, QPoint(0, 0)).x() + lab.width()
        assert lab.width() >= lab.sizeHint().width(), "the label is cut"
        assert verify.mapTo(sd, QPoint(0, 0)).x() >= right_of_label
        assert len(set(_lefts(sd))) == 1
    finally:
        sd.hide()
        sd.deleteLater()
        i18n.set_language(before or "en")
