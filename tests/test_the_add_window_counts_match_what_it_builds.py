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


# ---------------------------------------------------------------------------
# 6. Round 10's own findings: the promise beside an UNTICKED row was wrong on
#    two more rows, a hidden unit could decide a visible number, and one of the
#    guards above passed its own mutation.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("row,spin,value", [
    ("corners", "corners_edge", 3),
    ("spirals", "spirals_end", 4),
])
def test_the_greyed_promise_is_what_ticking_the_row_adds(qapp, row, spin, value):
    """`_corners_need_tips` and `_spirals_need_tips` answer the BUILDER's
    question, which begins with the row being ticked. Asking them for the count
    beside an UNTICKED row answered "it owns no tips" and dropped the eight
    (resp. six) corners: measured by round 10, the corner row promised 72 and
    added 80.

    MUTATION: drop `assume_on=True` from either counter and this goes red.
    """
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=[])
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    cb = getattr(dlg, f"_gen_{row}")
    getattr(dlg, f"_gen_{spin}").setValue(value)
    label = getattr(dlg, f"_gen_{row}_count")

    cb.setChecked(False)
    dlg._update_gen_counts()
    promised = _row_number(label)
    without = len(dlg._build_generated_program())
    cb.setChecked(True)
    dlg._update_gen_counts()
    shown = _row_number(label)
    with_ = len(dlg._build_generated_program())
    assert with_ - without > 0
    assert promised == with_ - without, (
        f"the greyed {row} row promises {promised} and ticking it adds "
        f"{with_ - without}")
    assert shown == with_ - without
    dlg.deleteLater()


def test_a_hidden_unit_cannot_decide_the_fill_target(qapp):
    """#93 took "fill to pages" out of the window and left the widgets hidden,
    while `fill_unit_pages` stayed in every persisted state. Round 10 measured
    a restored True: the visible box read 1000 patches and the chart came out
    with 1,364.

    MUTATION: drop the `isHidden()` guard from `_sync_fill_unit` and this goes
    red.
    """
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=[])
    dlg._add_mode_gen.setChecked(True)
    # A PAGE HAS TO HAVE A CAPACITY for the trap to spring: with no engine the
    # pages unit falls back to the patches spin on its own and the test would
    # pass against the fault.
    dlg._engine_cap_per_page = lambda: 682
    dlg._gen_fill_to.setValue(1000)
    dlg._gen_fill_pages.setValue(2)
    dlg._gen_fill_unit_pages.setChecked(True)
    dlg._update_gen_counts()
    assert dlg._effective_fill_target() == 1000, (
        "a unit the window does not show decided the number it does show")
    dlg.deleteLater()


def test_the_fill_row_shows_what_the_fill_really_added(qapp):
    """The other half of B8-323, which the first guards did not ask: the fill
    row's number has to come from the build too.

    MUTATION: drop `self._built_row_counts["fill"] = len(topup)` and this goes
    red. Round 10 found that mutation surviving the guards as they stood.
    """
    existing = _chart_with_white_and_black()
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_unique.setChecked(True)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)
    dlg._gen_whiteblack_n.setValue(2)
    dlg._gen_whiteblack.setChecked(True)
    target = len(existing) + 200
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(target)
    dlg._do_push_live_preview()
    built = dlg._build_generated_program()
    added = len(existing) + len(built)
    assert added == target, (added, target)
    # the row must name the fill's OWN share of that, which is the target less
    # the chart and everything the other sets contributed
    others = len(built) - int(dlg._built_row_counts.get("fill", -1))
    assert _row_number(dlg._gen_fill_count) == len(built) - others
    assert _row_number(dlg._gen_fill_count) == dlg._built_row_counts["fill"]
    dlg.deleteLater()


def test_the_from_image_row_marks_its_number_as_a_request(qapp):
    """A picture is asked for N representative colours and gives what it has:
    round 10 loaded a two-colour picture with the spin at 24 and the row read
    "24 patches" while the build appended 2. The Even-coverage row has carried
    "≈" for this since #72; so does this one.

    MUTATION: drop the "≈ " prefix and this goes red.
    """
    import numpy as np
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=[])
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_image.setChecked(True)
    dlg._gen_image_n.setValue(24)
    # a two-colour picture
    dlg._gen_image_px = np.array([[[255, 0, 0], [0, 0, 255]]] * 8,
                                 dtype=np.uint8)
    dlg._update_gen_counts()
    text = dlg._gen_image_count.text()
    assert text.startswith("≈"), (
        f"the From image row reads {text!r} as if it were exact")
    dlg.deleteLater()


@pytest.mark.parametrize("first,second", [
    (a, b) for a in ("cube", "edges", "corners", "spirals")
    for b in ("cube", "edges", "corners", "spirals") if a != b])
def test_the_promise_holds_when_another_tip_owner_is_already_on(qapp, first,
                                                                second):
    """The sets are not independent: the eight gamut tips belong to the highest
    ticked owner in the chain, so ticking one row changes ANOTHER row's number.

    Round 11 measured 6 of these 12 pairs wrong on the shipped build: with
    Saturated edges on, the 3D cube row promised 125 patches and the chart grew
    by 423.

    MUTATION: go back to the per-row counter for an unticked row (drop
    `_estimate_additions(assume=cb)`) and half of these go red.
    """
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=[])
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    getattr(dlg, f"_gen_{first}").setChecked(True)
    dlg._update_gen_counts()
    label = getattr(dlg, f"_gen_{second}_count")
    promised = _row_number(label)
    before = len(dlg._build_generated_program())
    getattr(dlg, f"_gen_{second}").setChecked(True)
    dlg._update_gen_counts()
    after = len(dlg._build_generated_program())
    assert promised == after - before, (
        f"with {first} on, the {second} row promises {promised} and ticking "
        f"it adds {after - before}")
    dlg.deleteLater()


def test_a_multi_ink_total_says_it_is_an_estimate(qapp):
    """On an RGB chart the Total is replaced by the real built number a moment
    later. On a multi-ink one it cannot be: state 2 would shell targen on every
    keystroke and state 3 xicclu, so the line stays an estimate. Round 11 read
    "Total: 30" against a build of 29, with nothing saying so.

    MUTATION: drop the "≈" from the Total and this goes red.
    """
    # The ADD window has no Device box (it extends a chart whose colourspace
    # is fixed), so the New Patch Set window is where a multi-ink state can be
    # reached at all.
    import tempfile
    from pathlib import Path
    new = _NewChartDialog(Path(tempfile.mkdtemp()), _FakeSettings())
    try:
        new._mode_generate.setChecked(True)
        new._update_gen_counts()
        assert not new._gen_total.text().startswith("≈"), (
            "an RGB total is exact and must not be marked as an estimate")
        ix = new._device_type.findData("cmyk")
        if ix < 0:
            ix = next((i for i in range(new._device_type.count())
                       if new._device_type.itemData(i) not in (None, "rgb")), -1)
        if ix < 0:
            pytest.skip("this build offers no multi-ink device type")
        new._device_type.setCurrentIndex(ix)
        qapp.processEvents()
        new._update_gen_counts()
        assert new._nch_state() != 1
        assert new._gen_total.text().startswith("≈"), (
            f"the multi-ink total reads {new._gen_total.text()!r} as if it "
            f"were exact")
    finally:
        new.deleteLater()
