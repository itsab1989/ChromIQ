"""Challenge 3 of beta 42: what the report window says while Generate is
greyed, what the ISO report types say now that their values ship, and the
measurement list's tick boxes on a dark page (register B8-1031, B8-1034,
B8-1037).

* B8-1034. With a profiling sheet ticked beside verifications Generate is
  greyed, and the red line still said *"Click 'Generate report'"*; the greyed
  Report type, Judged against and "Show detailed data" kept their ordinary
  tooltips, so nothing on them said why they would not open.
* B8-1031. The ISO heading and lines said *"a printing condition you
  supply"*, while the values ship with ChromIQ.
* B8-1037. The list's unticked boxes were drawn by Fusion from the palette,
  nearly invisible on the dark page.

Photographed on screen by ``scripts/drive_b42_c3_fixes.py``.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_c2_the_page_changes_only_with_generate import (  # noqa: E402
    _add, _ticks, _window)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _tick_the_sheet(dlg, qapp, before, on=True):
    from PyQt6.QtCore import Qt
    for i, (kind, _si, key) in enumerate(dlg._list_rows):
        if kind == "run" and key not in before:
            dlg._profile_list.item(i).setCheckState(
                Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
    qapp.processEvents()


def test_the_red_line_never_asks_for_a_greyed_button(
        tmp_path, qapp, monkeypatch):
    """MUTATION, proved to land: `_word_the_stale_line` always writes the
    live sentence (red). (Its second call, from `_sync_type_combo`, is a
    belt to `_show_stale_banner`'s: removed alone, this stays green, because
    every path measured here also passes the banner.)"""
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        before = _ticks(dlg)
        _add(dlg, qapp, monkeypatch, run.measurement_ti3)
        _tick_the_sheet(dlg, qapp, before)
        assert not dlg._generate_btn.isEnabled()
        assert dlg._stale_label.isVisible()
        text = dlg._stale_label.text()
        assert "Click" not in text, text
        assert "unavailable until the reason shown above" in text, text
        # and the reason IS shown above it
        assert dlg._generate_why.isVisible() and dlg._generate_why.text()
        from PyQt6.QtCore import QPoint
        why_y = dlg._generate_why.mapTo(dlg, QPoint(0, 0)).y()
        line_y = dlg._stale_label.mapTo(dlg, QPoint(0, 0)).y()
        assert why_y < line_y, ("the reason is not above the line",
                                why_y, line_y)
        # un-greyed: the line asks for the press again
        _tick_the_sheet(dlg, qapp, before, on=False)
        assert dlg._generate_btn.isEnabled()
        if dlg._stale_label.isVisible():
            assert "Click “Generate report”" in dlg._stale_label.text()
    finally:
        dlg.close()


def test_a_greyed_setting_says_why_and_gets_its_own_tooltip_back(
        tmp_path, qapp, monkeypatch):
    """MUTATION, proved to land: drop the `_say_why_greyed` call in
    `_grey_what_cannot_help` (red: ordinary tooltip on a greyed pulldown).
    Never restoring `_OWN_TIP` stays green on this path, because the sync
    pass writes both pulldowns' own tooltips again before un-greying them;
    the restore covers a pass that does not."""
    dlg, run, _vs = _window(tmp_path, qapp)
    try:
        own = {n: getattr(dlg, n).toolTip()
               for n in ("_type_combo", "_set_combo")}
        before = _ticks(dlg)
        _add(dlg, qapp, monkeypatch, run.measurement_ti3)
        _tick_the_sheet(dlg, qapp, before)
        why = dlg._generate_why.text()
        for w in (dlg._type_combo, dlg._set_combo, dlg._detail_check):
            assert not w.isEnabled()
            tip = w.toolTip()
            assert tip.startswith("Greyed, because no report can be "
                                  "generated now."), (w, tip)
            assert " ".join(why.split()) in " ".join(tip.split()), (
                w, "the tooltip does not give the reason")
            assert max(len(line) for line in tip.splitlines()) <= 80, (
                "a one-line tooltip runs across the screen")
        _tick_the_sheet(dlg, qapp, before, on=False)
        assert dlg._generate_btn.isEnabled()
        for n, tip in own.items():
            w = getattr(dlg, n)
            assert w.isEnabled()
            assert not w.toolTip().startswith("Greyed"), (n, w.toolTip())
            assert w.toolTip() == tip, (n, "its own tooltip did not come back")
        assert not dlg._detail_check.toolTip().startswith("Greyed")
    finally:
        dlg.close()


def test_the_iso_types_do_not_say_the_user_supplies_the_values():
    """MUTATION, proved to land: the old heading back (red)."""
    from workflow.measurement_report import (REPORT_TYPE_ISO_7,
                                             REPORT_TYPE_ISO_8,
                                             REPORT_TYPE_MENU,
                                             REPORT_TYPE_MENU_HEADING)
    from core.i18n import tr  # noqa: F401  (the catalogue must know them)
    import json
    from pathlib import Path
    de = json.loads((Path(__file__).resolve().parent.parent / "data" / "i18n"
                     / "de.json").read_text(encoding="utf-8"))
    texts = [REPORT_TYPE_MENU_HEADING] + [
        blurb for tid, _n, blurb, _b in REPORT_TYPE_MENU
        if tid in (REPORT_TYPE_ISO_7, REPORT_TYPE_ISO_8)]
    for t in texts:
        assert "supply" not in t and "you" not in t.lower().split(), t
        assert de.get(t) and de[t] != t, ("no German by hand for", t)
        assert "angegeben" not in de[t], de[t]
    blurbs = dict((tid, b) for tid, _n, b, _x in REPORT_TYPE_MENU)
    assert "ISO 12647-8" in blurbs[REPORT_TYPE_ISO_8]
    assert "ISO 12647-7" in blurbs[REPORT_TYPE_ISO_7]
    for b in texts:
        low = b.lower()
        assert "conform" not in low and "certif" not in low, b


@pytest.mark.parametrize("mode", ["dark", "neutral"])
def test_the_lists_tick_boxes_are_drawn_visibly(tmp_path, qapp, mode):
    """The list's indicator is styled with an edge that stands off its
    ground in dark and neutral, and a ticked box carries a tick image.

    MUTATION, proved to land: drop `_list_tick_box_qss` from the list's style
    sheet (red in both modes)."""
    from PyQt6.QtGui import QColor
    dlg, _run, _vs = _window(tmp_path, qapp, sheet=False)
    try:
        dlg._settings.set("appearance", mode)
        qss = dlg._list_tick_box_qss()
        assert "QListWidget::indicator" in dlg._profile_list.styleSheet()
        import re
        edge = re.search(r"::indicator \{[^}]*border: 1px solid (#[0-9a-f]{6})",
                         qss).group(1)
        ground = re.search(r"::indicator \{[^}]*background: (#[0-9a-f]{6})",
                           qss).group(1)
        a, b = QColor(edge), QColor(ground)
        assert abs(a.lightness() - b.lightness()) >= 80, (mode, edge, ground)
        assert "list_tick_" in qss and "image: url(" in qss
        img = re.search(r"image: url\(([^)]+)\)", qss).group(1)
        assert os.path.exists(img), img
    finally:
        dlg.close()
