"""K33-8 (B8-999): "Sort by" in "Which presets can be used for verification?".

Knut, #182 5817191535: to the right of "Show only the presets made for
verification", a "Sort by" pulldown; the default is today's order, named for
what it really is; a second choice puts the presets answering the most
metrics first; presets stay grouped under their group names and are sorted
within each group.

Today's order was measured, not assumed: it is the Create Chart Preset
pulldown's own order (`BUILTIN_PRESET_GROUPS`, then your own presets
alphabetically), which is not alphabetical.

Pinned, each with the mutation that turns it red:

* the default is the pulldown order and the list reads exactly as before
  (MUTATION: sort by label in `_sorted_members` for the default);
* "Most metrics answered first" sorts each group by answered count, ties
  keep the pulldown order, and no preset leaves its group (MUTATION: sort the
  whole list across groups, or reverse the key);
* the pulldown sits in the row of the tick box, right of it (MUTATION: add it
  to the row of the two other pulldowns).
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication

from core.i18n import tr
from core.settings import AppSettings
from ui.dialogs import preset_verification_dialog as PVD
from ui.tabs.tab_chart import verification_preset_rows


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def rows(qapp, tmp_path_factory):
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path_factory.mktemp("s") / "s.ini"),
                             QSettings.Format.IniFormat)
    return verification_preset_rows(settings)


def _open(qapp, rows):
    dlg = PVD.PresetVerificationDialog(list(rows), None, None)
    dlg.show()
    qapp.processEvents()
    return dlg


def _groups(dlg):
    out = []
    for i in range(dlg._tree.topLevelItemCount()):
        top = dlg._tree.topLevelItem(i)
        if not top.childCount():
            continue
        out.append((top.text(0), [top.child(j).data(0, Qt.ItemDataRole.UserRole)
                                  for j in range(top.childCount())]))
    return out


def test_the_default_is_the_pulldown_order_and_the_list_is_unchanged(qapp, rows):
    dlg = _open(qapp, rows)
    try:
        assert dlg._sort_combo.itemData(0) == PVD.SORT_PULLDOWN
        assert dlg.current_sort() == PVD.SORT_PULLDOWN
        assert dlg._sort_combo.itemText(0) == tr("Preset pulldown order")
        shown = [r.label for _g, members in _groups(dlg) for r in members]
        assert shown == [r.label for r in rows], (
            "the default order is no longer the order the rows arrive in")
        # and that order is not alphabetical, which is why it is named for
        # what it is
        first_group = _groups(dlg)[0][1]
        labels = [r.label for r in first_group]
        assert labels != sorted(labels, key=str.lower)
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()


@pytest.mark.parametrize("only_star", [False, True],
                         ids=["all presets", "only made for verification"])
def test_most_answered_sorts_within_each_group(qapp, rows, only_star):
    """Knut, #182 5817448879: Sort by must work the same whether "Show only
    the presets made for verification" is ticked or not. Both states run the
    same checks (MUTATION: sort only the unfiltered list)."""
    dlg = _open(qapp, rows)
    try:
        dlg._only_star.setChecked(only_star)
        qapp.processEvents()
        before = _groups(dlg)
        if only_star:
            assert all(r.starred for _g, m in before for r in m)
        dlg._sort_combo.setCurrentIndex(
            dlg._sort_combo.findData(PVD.SORT_MOST_ANSWERED))
        qapp.processEvents()
        after = _groups(dlg)
        assert [g for g, _m in after] == [g for g, _m in before], (
            "the groups moved; sorting is within each group only")
        moved = False
        for (g, old), (_g, new) in zip(before, after):
            assert {r.label for r in old} == {r.label for r in new}, g

            def n(r):
                a = r.assessment
                return len(a.answered) if a.checked else -1
            counts = [n(r) for r in new]
            assert counts == sorted(counts, reverse=True), (g, counts)
            # ties keep the pulldown order
            pos = {r.label: i for i, r in enumerate(old)}
            for a, b in zip(new, new[1:]):
                if n(a) == n(b):
                    assert pos[a.label] < pos[b.label], (g, a.label, b.label)
            moved = moved or [r.label for r in old] != [r.label for r in new]
        assert moved, "no group changed order, so this proves nothing"
        # back to the default gives the original order again
        dlg._sort_combo.setCurrentIndex(0)
        qapp.processEvents()
        assert [[r.label for r in m] for _g, m in _groups(dlg)] == \
            [[r.label for r in m] for _g, m in before]
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()


def test_the_pulldown_sits_right_of_the_tick_box(qapp, rows):
    dlg = _open(qapp, rows)
    try:
        star = dlg._only_star
        combo = dlg._sort_combo
        assert star.parentWidget() is combo.parentWidget()
        star_top = star.mapTo(dlg, star.rect().topLeft())
        combo_top = combo.mapTo(dlg, combo.rect().topLeft())
        assert combo_top.x() > star_top.x() + star.width()
        assert abs(star.mapTo(dlg, star.rect().center()).y()
                   - combo.mapTo(dlg, combo.rect().center()).y()) <= 6
    finally:
        dlg.close()
        dlg.deleteLater()
        QApplication.processEvents()
