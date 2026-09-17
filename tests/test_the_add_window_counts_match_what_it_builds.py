"""Knut's Patch Set editor batch (#182, 2026-09-17), all three faults.

He opened the editor's **Add** window on a 615-patch chart and found:

* *"the bottom last checkboxes overlap each other, above the total patches
  count. I cannot click on the 'Ensure unique colours..' checkbox."*
* *"the count for the 'Fill remaining gaps' is 0, even though the fill to value
  is larger than the total."*
* *"Clicking on Pure white & black, with each=2, shows a count of 2 on the
  right side, but the total number jumps from 567 to 571, which is also a bug
  in counting."*

The first was a grid collision; the other two were an ESTIMATE disagreeing with
the BUILD, and a target measured against a number the row never named.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog, _NewChartDialog
import workflow.patch_generators as G


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def get(self, *_a, **_k):
        return None

    def set(self, *_a, **_k):
        pass


def _chart_with_white_and_black():
    """A small chart that looks like one ChromIQ generated: it holds pure white
    and pure black, which is what makes the white/black row's estimate wrong."""
    patches = G.deduplicate(G.rgb_cube(4) + G.neutral_ramp(6))
    assert G.count_white_black(patches) == (1, 1)
    return patches


def _sets_off(dlg):
    for name in dlg._GEN_CHECKS:
        if name != "unique":
            getattr(dlg, f"_gen_{name}").setChecked(False)


# ---------------------------------------------------------------------------
# 1. The two bottom rows are not in the same grid cell, and the checkbox the
#    user could not click is the widget under its own centre.
# ---------------------------------------------------------------------------
def test_the_add_window_does_not_stack_two_widgets_in_one_cell(qapp):
    dlg = _AddPatchesDialog(_FakeSettings(),
                            existing_patches=_chart_with_white_and_black())
    grid = dlg._gen_unique.parentWidget().layout()
    cells = {}
    for i in range(grid.count()):
        w = grid.itemAt(i).widget()
        if w is None:
            continue
        r, c, rs, cs = grid.getItemPosition(i)
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                assert (rr, cc) not in cells, (
                    f"{w.objectName() or type(w).__name__} shares cell "
                    f"({rr}, {cc}) with {cells[(rr, cc)]}")
                cells[(rr, cc)] = w.objectName() or type(w).__name__
    dlg.deleteLater()


def test_the_unique_checkbox_is_the_widget_under_its_own_centre(qapp):
    """The geometric half of the same fault: a grid puts two widgets in one
    cell on top of each other, and the later one takes the mouse."""
    dlg = _AddPatchesDialog(_FakeSettings(),
                            existing_patches=_chart_with_white_and_black())
    dlg._add_mode_gen.setChecked(True)
    dlg._refresh_add_mode()
    dlg.show()
    qapp.processEvents()
    panel = dlg._gen_unique.parentWidget()
    panel.layout().activate()
    qapp.processEvents()
    uniq, after = dlg._gen_unique.geometry(), dlg._gen_after_total.geometry()
    assert not uniq.intersects(after), (
        f"'Ensure unique colours' {uniq} overlaps 'Chart after adding' {after}")
    hit = panel.childAt(uniq.center())
    assert hit is dlg._gen_unique, (
        f"the widget under the checkbox's own centre is {hit!r}")
    dlg.close()
    dlg.deleteLater()


# ---------------------------------------------------------------------------
# 2. The white/black row's number is what the build really adds.
# ---------------------------------------------------------------------------
def _row_number(label):
    import re
    m = re.search(r"([0-9]+)", label.text().replace(",", ""))
    return None if m is None else int(m.group(1))


def test_the_white_black_row_counts_what_the_build_adds(qapp):
    """On a chart that already holds white and black, 'Ensure unique colours'
    moves the cube's own tips clear of them, so they stop counting toward
    'each' and the full 2 x each is added. The estimate could not see that."""
    existing = _chart_with_white_and_black()
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_unique.setChecked(True)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)
    dlg._gen_whiteblack_n.setValue(2)

    dlg._gen_whiteblack.setChecked(False)
    dlg._do_push_live_preview()
    without = len(dlg._build_generated_program())
    promised = _row_number(dlg._gen_whiteblack_count)

    dlg._gen_whiteblack.setChecked(True)
    dlg._do_push_live_preview()
    with_ = len(dlg._build_generated_program())
    shown = _row_number(dlg._gen_whiteblack_count)

    assert with_ - without == 4, "the fixture no longer reproduces the case"
    assert shown == 4, f"the row shows {shown} while the build adds 4"
    assert promised == 4, (
        f"the greyed row promises {promised} while ticking it adds 4")
    dlg.deleteLater()


def test_the_row_numbers_survive_a_cache_hit(qapp):
    """The build produces three things now, and the program cache keeps all
    three: a second window on the same settings must not put the estimate
    back on screen."""
    existing = _chart_with_white_and_black()
    for _ in range(2):
        dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
        dlg._add_mode_gen.setChecked(True)
        _sets_off(dlg)
        dlg._gen_unique.setChecked(True)
        dlg._gen_cube.setChecked(True)
        dlg._gen_cube_n.setValue(4)
        dlg._gen_whiteblack_n.setValue(2)
        dlg._gen_whiteblack.setChecked(True)
        dlg._do_push_live_preview()
        assert _row_number(dlg._gen_whiteblack_count) == 4
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 3. The fill row says what its target is measured against.
# ---------------------------------------------------------------------------
def test_the_fill_row_says_the_target_is_already_met(qapp):
    existing = _chart_with_white_and_black()
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(max(1, len(existing) - 10))
    dlg._update_gen_counts()
    assert "0" not in dlg._gen_fill_count.text()
    assert "target already met" in dlg._gen_fill_count.text()
    # Raise it above the chart and the row is a count again.
    dlg._gen_fill_to.setValue(len(existing) + 25)
    dlg._update_gen_counts()
    assert "25" in dlg._gen_fill_count.text()
    dlg.deleteLater()


def test_the_fill_row_names_the_chart_in_the_add_window(qapp):
    """'fill to: 615 patches' on a 615-patch chart reads as a bug; 'fill chart
    to: 615 patches in total' reads as what it is."""
    add = _AddPatchesDialog(_FakeSettings(),
                            existing_patches=_chart_with_white_and_black())
    assert add._gen_fill_prefix.text() == "fill chart to:"
    add.deleteLater()


def test_the_new_window_keeps_the_plain_fill_label(qapp, tmp_path):
    new = _NewChartDialog(tmp_path, _FakeSettings())
    assert new._gen_fill_prefix.text() == "fill to:"
    new.deleteLater()


# ---------------------------------------------------------------------------
# 4. The help text both windows show carries the two corrections.
# ---------------------------------------------------------------------------
def test_the_generator_help_explains_both_rows(qapp):
    from ui.dialogs.ti2_relayout_dialog import _ADD_TIP_INTRO, _GEN_SETS_HELP
    assert "target already met" in _GEN_SETS_HELP
    assert "size of the finished chart" in _GEN_SETS_HELP
    assert "no longer count toward 'each'" in _GEN_SETS_HELP
    assert "already holds patches" in _ADD_TIP_INTRO


# ---------------------------------------------------------------------------
# 5. The Add window can key its program cache at all. It could not: the key
#    read New-chart-only widgets, `_generator_cache_key` caught the
#    AttributeError and answered None, and a None key means never cache. Found
#    while proving fault 2 above, because the cache-hit path could not be
#    reached to test it.
# ---------------------------------------------------------------------------
def test_the_add_window_keys_and_reuses_its_program_cache(qapp):
    dlg = _AddPatchesDialog(_FakeSettings(),
                            existing_patches=_chart_with_white_and_black())
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)
    assert dlg._generator_cache_key() is not None, (
        "the Add window cannot key its cache, so it rebuilds the whole "
        "program on every keystroke")

    builds = []
    real = dlg._build_generated_program_uncached

    def counting():
        builds.append(1)
        return real()

    dlg._build_generated_program_uncached = counting
    first = dlg._build_generated_program()
    second = dlg._build_generated_program()
    assert first == second
    assert len(builds) == 1, f"the same settings were built {len(builds)} times"
    dlg.deleteLater()
