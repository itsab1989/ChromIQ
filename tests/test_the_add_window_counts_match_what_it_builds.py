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


def test_a_multi_ink_total_says_it_is_an_estimate(qapp, tmp_path):
    """On an RGB chart the Total is replaced by the real built number a moment
    later. On a multi-ink one it cannot be: state 2 would shell targen on every
    keystroke and state 3 xicclu, so the line stays an estimate. Round 11 read
    "Total: 30" against a build of 29, with nothing saying so.

    MUTATION: drop the "≈" from the Total and this goes red.
    """
    # The ADD window has no Device box (it extends a chart whose colourspace
    # is fixed), so the New Patch Set window is where a multi-ink state can be
    # reached at all.
    new = _NewChartDialog(tmp_path, _FakeSettings())
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


# ---------------------------------------------------------------------------
# 9. B8-346 F2/F3/F4 — round 12 swept all fifteen rows in fourteen contexts, in
#    both windows, with and without "Ensure unique colours" and with and
#    without existing patches: 1,344 cases, 26 of them wrong. Three shapes.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("row,spin,value", [
    ("cube", "cube_n", 8),
    ("edges", "edges_n", 5),
    ("corners", "corners_edge", 3),
    ("neutral", "neutral_n", 8),
])
def test_a_tip_owners_promise_survives_the_white_black_row(qapp, row, spin,
                                                           value):
    """B8-346 F3: with "Pure white & black" on and a chart that already holds
    pure white and black, every tip-owner row promised two patches too few (the
    cube 510 where the chart grew by 512, Saturated edges 18 against 20,
    Gamut-corner emphasis 54 against 56, the Neutral grey ramp 14 against 16).

    The estimate assumed a ticked tip owner supplies the white and black the
    anchors would add, so the anchors add nothing. **"Ensure unique colours"
    takes them straight back**: `enforce_min_distance` runs with the existing
    chart seeded, so the owner's own white and black are pushed OFF pure white
    and black to clear the chart's, `count_white_black` then finds none in the
    program, and the two anchors go in after all.

    MUTATION, proven to land: drop the `_white_black_additions` de-dup branch
    and go back to `white_black_count(n, sets_have, sets_have)`.
    """
    dlg = _AddPatchesDialog(_FakeSettings(),
                            existing_patches=_chart_with_white_and_black())
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_unique.setChecked(True)
    dlg._gen_whiteblack.setChecked(True)
    getattr(dlg, f"_gen_{spin}").setValue(value)
    cb = getattr(dlg, f"_gen_{row}")
    label = getattr(dlg, f"_gen_{row}_count")

    cb.setChecked(False)
    dlg._update_gen_counts()
    promised = _row_number(label)
    without = len(dlg._build_generated_program())
    cb.setChecked(True)
    dlg._update_gen_counts()
    with_ = len(dlg._build_generated_program())
    grew = with_ - without
    assert grew > 0
    assert promised == grew, (
        f"the greyed {row} row promises {promised} and ticking it adds {grew}")
    dlg.deleteLater()


def test_the_fill_row_does_not_make_every_other_row_read_zero(qapp):
    """B8-346 F2: a row's number is what that row contributes, and "Fill
    remaining gaps" absorbs it.

    The promise is the difference two whole estimates make, and with a fill
    target the second estimate is pinned to the target, so the difference is
    zero BY CONSTRUCTION. Round 12 photographed it: with the fill row ticked,
    all fourteen colour-set rows read "0 patches" where the cube read 512. Both
    estimates now leave the fill out, so the rows say what they add and the
    fill row's own number falls by the same amount, which is how the window
    shows that the total is pinned.

    MUTATION, proven to land: take `with_fill=False` off either call.
    """
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=[])
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_unique.setChecked(True)
    dlg._gen_cube.setChecked(False)
    dlg._gen_cube_n.setValue(8)
    dlg._gen_fill.setChecked(True)
    dlg._gen_fill_to.setValue(1000)
    dlg._update_gen_counts()
    promised = _row_number(dlg._gen_cube_count)
    fill_before = _row_number(dlg._gen_fill_count)
    assert promised == 512, (
        f"the cube row promises {promised} with the fill row on; it adds 512")
    dlg._gen_cube.setChecked(True)
    dlg._update_gen_counts()
    fill_after = _row_number(dlg._gen_fill_count)
    # ...and the window adds up: what the cube took, the fill gave back.
    assert fill_before - fill_after == 512, (
        f"the fill row went from {fill_before} to {fill_after}; the cube it "
        "made room for is 512 patches")
    dlg.deleteLater()


def test_a_greyed_out_row_shows_its_own_size_not_zero(qapp):
    """B8-346 F4: on a CMYK chart the RGB rows are greyed by the device-state
    gating, and a greyed row cannot contribute, so "what would ticking this
    add" is zero however big the set is. Every one of them read "0 patches"
    where the cube read 512 and Skin tones 144.

    A row the device state has switched off shows its own size, struck through,
    which is what it showed before the difference basis existed.

    MUTATION, proven to land: go back to
    `if not (cb.isChecked() and cb.isEnabled())`.
    """
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=[])
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    # exactly what the gating leaves behind: still ticked, so returning to RGB
    # restores it, but greyed out and contributing nothing.
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube.setEnabled(False)
    dlg._gen_skin.setChecked(False)
    dlg._gen_skin.setEnabled(False)
    dlg._update_gen_counts()
    assert _row_number(dlg._gen_cube_count) == 512, dlg._gen_cube_count.text()
    assert _row_number(dlg._gen_skin_count) == 144, dlg._gen_skin_count.text()
    dlg.deleteLater()


def test_both_bottom_lines_are_written_from_one_number(qapp):
    """B8-341 / R14-F7: with the 3D cube unfolded on a multi-ink chart, the
    Lab-cloud path rewrote the Total from the build it had just done and never
    touched "Chart after adding", so the window could state a total and a
    resulting chart size that do not add up.

    The two are views of one count now, and this pins that: whatever number the
    Total is written from, the line below it is the chart plus that number.

    MUTATION, proven to land: set `_gen_total` alone in `_set_total_labels`.
    """
    existing = _chart_with_white_and_black()
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    for n in (0, 7, 512):
        dlg._set_total_labels(n)
        total = _row_number(dlg._gen_total)
        after = _row_number(dlg._gen_after_total)
        assert total == n, (n, dlg._gen_total.text())
        assert after == len(existing) + n, (
            f'the Total says {total} and "Chart after adding" says {after} on '
            f'a chart of {len(existing)}: the two do not add up')
    dlg.deleteLater()


def test_the_lab_cloud_path_writes_both_bottom_lines(qapp, monkeypatch):
    """R15-F1: the guard above calls `_set_total_labels` directly and never
    reaches `_push_lab_cloud`, which is where B8-341 lived. Round 15 restored
    the fault verbatim, one line, and the WHOLE everyday tier stayed green:
    16,506 passed. A guard that only its own mutation can redden guards
    nothing.

    So this one drives the state-3 path itself. `forward_lab` is the only part
    that needs a profile and a subprocess, and it is replaced by a stub that
    returns a known number of points; everything else is the real method.

    MUTATION, proven to land: put `self._gen_total.setText(...)` back in place
    of `self._set_total_labels(...)` in `_push_lab_cloud`.
    """
    existing = _chart_with_white_and_black()
    dlg = _AddPatchesDialog(_FakeSettings(), existing_patches=existing)
    dlg._add_mode_gen.setChecked(True)
    _sets_off(dlg)
    dlg._gen_cube.setChecked(True)
    dlg._gen_cube_n.setValue(4)

    # State 3 is "multi-ink with a preconditioning profile that matches", and
    # the cloud only runs with the cube unfolded.
    monkeypatch.setattr(type(dlg), "_nch_state", lambda self: 3)
    monkeypatch.setattr(type(dlg), "_gen_sets_active", lambda self: True)
    dlg._cube_shown = True
    dlg._nch_cube_hidden = False

    made = {}

    class _Panel:
        def set_lab_cloud(self, labs, colors):
            made["n"] = len(labs)

        def set_program(self, *a, **k):
            pass

    dlg._cube_panel = _Panel()
    n_points = 40
    monkeypatch.setattr(
        "workflow.xicclu_runner.forward_lab",
        lambda program, precond, bin_dir: [(50.0, 0.0, 0.0)] * n_points)
    monkeypatch.setattr(type(dlg), "_build_generated_program",
                        lambda self: [(50.0, 50.0, 50.0)] * n_points)
    dlg._precond_path = "unused-by-the-stub"
    dlg._bin_dir = ""
    dlg._extra_inks = []

    dlg._do_push_live_preview()
    assert made.get("n") == n_points, (
        "the Lab-cloud path did not run, so this test proves nothing")
    total = _row_number(dlg._gen_total)
    after = _row_number(dlg._gen_after_total)
    assert total == n_points, dlg._gen_total.text()
    assert after == len(existing) + n_points, (
        f'the 3D-cube path left "Chart after adding" at {after} while the '
        f'Total says {total} on a chart of {len(existing)}')
    dlg.deleteLater()
