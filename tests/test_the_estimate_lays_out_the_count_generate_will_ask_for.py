"""The "estimate" column must describe the chart GENERATE would make next.

The panel's own help says so: *"estimate - what the settings you have right now
would produce if you generate."* Basti: *"at some point the estimate number for
patches under chart layout information did not match anymore what i actually
got. after playing around a bit."*

MEASURED ON SCREEN (cocoa, i1Pro, A4 portrait, ChromIQ layout engine, "Auto
patch count" UNTICKED), three stages in a row, each one "set the controls, read
the estimate, press Generate, read the result":

    controls                     estimate said        build gave
    area-first, -f 400           525, 25x21, 1 page   418, 22x19, 1 page
    area-first, -f 900           425,     -, 1 page   900, 25x21, 2 pages
    area-first, 9 mm, -f 400     920,     -, 3 pages  418, 22x19, 1 page

Two independent faults, and both are pinned here:

1. **The count.** With "Auto patch count" off, Generate passes the targen -f
   value straight through, so THAT is the count the estimate must lay out. It
   used the patch count of the chart already in the preview instead, so the
   panel described the previous build for ever after: -f 900 was promised as
   425 on one page (the 420-patch chart before it, padded) while the build made
   900 on two.
2. **The size.** Area-first sizes the patch FROM the count, and the count
   reaches the engine as ``area_target_count``. The estimate did not pass it,
   so it sized a capacity fill of minimum-width patches (8.33 x 8.56 mm, 525 to
   a sheet) for a build that would make 9.23 x 9.82 mm patches, 418 to a sheet.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

GRID_ROWS = 24


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, *, area_first=True):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", True)
    s.set("layout_info_show", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._manual_btn.setChecked(True)
    tab._manual_engine_check.setChecked(True)
    tab._manual_auto_patches_check.setChecked(False)
    from workflow.layout_engine.presets import LayoutRecipe
    base = tab._manual_layout_panel.get_recipe()
    tab._manual_layout_panel.set_recipe(LayoutRecipe(**{
        **base.__dict__,
        "instrument": "i1", "paper": "A4", "dpi": 200,
        "layout_mode": "area_first" if area_first else "patch_first",
        "area_method": "by_width", "area_cols": 0, "area_rows": 0,
        "area_min_patch_mm": 0.0, "layout_explicit": True,
    }))
    return tab


def _set_f(tab, n: int) -> None:
    tab._manual_f_pw._control.setValue(n)


def _chart_on_screen(tab, tmp_path: Path, n: int, name: str) -> None:
    """Put a chart of *n* patches in the preview, through the door every
    finished build comes through."""
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    strips = math.ceil(n / GRID_ROWS)
    ti2 = d / f"{name}.ti2"
    ti2.write_text(
        'CTI2\n\nDESCRIPTOR "test"\nORIGINATOR "ChromIQ layout engine"\n'
        'TARGET_INSTRUMENT "i1"\nPAPER_SIZE "210.0x297.0"\n'
        f'STEPS_IN_PASS "{GRID_ROWS}"\nPASSES_IN_STRIPS2 "{strips}"\n'
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G\nEND_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    (d / f"{name}.ti1").write_text(
        f'CTI1\n\nNUMBER_OF_SETS {n}\nBEGIN_DATA\nEND_DATA\n', encoding="utf-8")
    tif = d / f"{name}.tif"
    tif.write_bytes(b"II*\x00")
    tab._set_margin_chart([tif], ti2)


def _est(tab, key):
    return tab._layout_info_panel._estimate_labels[key].text()


def _engine_layout(tab, count: int, *, with_target: bool):
    """What the engine would lay out for *count* patches, with and without the
    area_target_count the build passes. The two differ in area-first, which is
    the whole point of the second fault."""
    from workflow.layout_engine import geometry, instruments, papers
    r = tab._current_layout_recipe()
    kw = r.build_kwargs()
    if with_target:
        kw["area_target_count"] = count
    geom = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm(r.paper)
    return geometry.compute(geom, w_mm, h_mm, count)


# ---------------------------------------------------------------------------
# 1. the count
# ---------------------------------------------------------------------------

def test_the_targen_f_value_is_what_generate_will_ask_for(qapp, tmp_path):
    tab = _tab(tmp_path)
    _set_f(tab, 400)
    assert tab._targen_patch_count() == 400
    tab._manual_auto_patches_check.setChecked(True)
    assert tab._targen_patch_count() is None, (
        "with Auto patch count on the count is a capacity fill, not the box")


def test_the_f_value_beats_the_chart_already_on_screen(qapp, tmp_path):
    """The reported fault, at its source. A 900-patch chart in the preview and
    -f 400 in the box: Generate would build 400, so the estimate must say 400."""
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 900, "c900")
    _set_f(tab, 400)
    assert tab._onscreen_patch_total() == 900, "the preview really holds 900"
    assert tab._estimate_patch_total() == 400, (
        "the estimate was laying out the chart on screen, one build behind")


def test_the_estimate_total_follows_the_f_box_not_the_preview(qapp, tmp_path):
    """End to end through the panel: the number a person reads."""
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 900, "p900")
    _set_f(tab, 400)
    tab._refresh_layout_estimate()
    expected = _engine_layout(tab, 400, with_target=True)
    assert _est(tab, "total") == str(expected.total_patches)
    assert _est(tab, "pages") == str(expected.pages)
    # And the on-screen column still reports the chart that IS on screen.
    assert tab._layout_info_panel._actual_labels["total"].text() == "900"


def test_a_changed_f_value_moves_the_estimate(qapp, tmp_path):
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 420, "p420")
    _set_f(tab, 400)
    tab._refresh_layout_estimate()
    small = (_est(tab, "total"), _est(tab, "pages"))
    _set_f(tab, 900)
    tab._refresh_layout_estimate()
    big = (_est(tab, "total"), _est(tab, "pages"))
    assert small != big, "the estimate ignored the patch count the user typed"
    assert int(big[0]) > int(small[0])


def test_an_f_of_zero_falls_back_to_the_chart_on_screen(qapp, tmp_path):
    """-f 0 is the app's "not pinned here" default, so it is not an answer and
    the chart in the preview still stands in."""
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 192, "z192")
    _set_f(tab, 0)
    assert tab._targen_patch_count() is None
    assert tab._estimate_patch_total() == 192


def test_an_armed_patch_set_still_wins(qapp, tmp_path):
    """A preset's attached .ti1 is the file Generate will lay out verbatim, so
    it outranks the -f box as well as the preview."""
    tab = _tab(tmp_path)
    _chart_on_screen(tab, tmp_path, 192, "a192")
    _set_f(tab, 400)
    armed = tmp_path / "armed.ti1"
    armed.write_text("CTI1\n\nNUMBER_OF_SETS 360\nBEGIN_DATA\nEND_DATA\n",
                     encoding="utf-8")
    tab._preset_ti1_path = armed
    tab._preset_ti1_targen_sig = tab._targen_signature()
    assert tab._estimate_patch_total() == 360


# ---------------------------------------------------------------------------
# 2. the size
# ---------------------------------------------------------------------------

def test_area_first_sizes_the_patch_from_the_count(qapp, tmp_path):
    """Area-first grows the patches so exactly the requested count fills the
    sheet. The estimate must hand the engine that count, or it reports a
    capacity fill of minimum-width patches instead."""
    tab = _tab(tmp_path, area_first=True)
    _set_f(tab, 400)
    with_target = _engine_layout(tab, 400, with_target=True)
    without = _engine_layout(tab, 400, with_target=False)
    assert with_target.total_patches != without.total_patches, (
        "this instrument/paper cannot tell the two apart, so the test would "
        "pass without proving anything")
    tab._refresh_layout_estimate()
    assert _est(tab, "total") == str(with_target.total_patches)
    assert _est(tab, "rows") == str(with_target.steps_in_pass)


def test_patch_first_is_unaffected_by_the_target_count(qapp, tmp_path):
    """area_target_count only steers area-first sizing. Patch-first sets the
    patch size from the scale, so injecting the key must change nothing."""
    tab = _tab(tmp_path, area_first=False)
    _set_f(tab, 400)
    a = _engine_layout(tab, 400, with_target=True)
    b = _engine_layout(tab, 400, with_target=False)
    assert (a.total_patches, a.pages, a.steps_in_pass) == (
        b.total_patches, b.pages, b.steps_in_pass)
    tab._refresh_layout_estimate()
    assert _est(tab, "total") == str(a.total_patches)


def test_unticking_auto_puts_the_patch_count_back(qapp, tmp_path):
    """TWO CLICKS LEFT THE APP IN A STATE THE USER COULD NOT SEE.

    Ticking "Auto patch count" sets the -f box to 0, because a QSpinBox shows
    its "Auto" placeholder only at its minimum. Unticking cleared the
    placeholder and left the 0. So tick, untick, and -f is 0 with Auto off:
    nothing on screen says a count was lost, and the box reads 0, which is the
    app's "not pinned" value rather than a number anybody chose.

    A challenge round drove what follows: the estimate promised 418 patches and
    Generate built 16, and with a patch set attached Generate refused outright
    while the estimate promised 90.

    MUTATION: stop remembering the value, or stop restoring it, and this goes
    red.
    """
    tab = _tab(tmp_path)
    _set_f(tab, 400)
    spin = tab._manual_f_pw._control
    assert spin.value() == 400, "the premise failed"

    tab._on_auto_patches_toggled(True)
    assert spin.value() == 0, (
        "Auto no longer zeroes the box, so this test is measuring nothing")

    tab._on_auto_patches_toggled(False)
    assert spin.value() == 400, (
        "unticking Auto left the patch count at 0, a state the user never "
        "chose and cannot see")


def test_a_zero_typed_on_purpose_is_still_left_alone(qapp, tmp_path):
    """The restore must not invent a count for a user who really did type 0.

    THE ORDER IS THE WHOLE TEST, and a first version of it had none. Starting
    at 0 leaves nothing recorded, so it passed whether the code was right or
    wrong: a mutation that only records non-zero values left it green. The
    sequence that matters is the one a challenge round drove, where an EARLIER
    value is sitting in the record waiting to be reinstated.

    MUTATION: guard the recording with `if spin.value()` and this goes red,
    because the 777 comes back over the 0.
    """
    tab = _tab(tmp_path)
    spin = tab._manual_f_pw._control

    # 1. a real count, carried away by Auto and correctly put back
    _set_f(tab, 777)
    tab._on_auto_patches_toggled(True)
    tab._on_auto_patches_toggled(False)
    assert spin.value() == 777, "the premise failed: the restore does not work"

    # 2. …and now 0 on purpose, with 777 still in the record
    _set_f(tab, 0)
    tab._on_auto_patches_toggled(True)
    tab._on_auto_patches_toggled(False)
    assert spin.value() == 0, (
        "a count the user had deliberately cleared was replaced by an older "
        f"one: {spin.value()}")


def test_no_count_pinned_means_the_headline_says_so(qapp, tmp_path):
    """B1: ONE UNTICK PROMISED 105 PATCHES AND BUILT 14.

    A challenge round opened the app on Basti's own saved preferences, where
    "Auto patch count" is on and the -f box therefore reads 0, and unticked it
    once. Nothing had carried a value away this session, so -f stayed 0 with
    Auto off. The panel promised 105 patches over one page; Generate wrote a
    chart of 14.

    0 is the parameter's own default and means "not pinned here", so with Auto
    off nobody has said how many patches to make and targen falls back to its
    own minimum. That number is targen's business, not this panel's, and
    printing the sheet's capacity instead is a promise the build breaks.

    MUTATION: drop `_count_is_unpredictable` from the headline and this goes
    red.
    """
    tab = _tab(tmp_path)
    _set_f(tab, 0)
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)

    assert tab._count_is_unpredictable() is True, "the premise failed"

    tab._update_patch_count()
    assert tab._predicted_patch_count is None, (
        "the panel put a number on a chart whose size nobody has set")
    assert "?" in tab._patch_count_lbl.text(), tab._patch_count_lbl.text()


def test_a_pinned_count_is_still_predictable(qapp, tmp_path):
    """The other direction, or the fix would silence a headline that is right.

    MUTATION: return True unconditionally and this goes red.
    """
    tab = _tab(tmp_path)
    _set_f(tab, 400)
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    assert tab._count_is_unpredictable() is False

    # …and with Auto ON the capacity estimate is the honest answer again
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(True)
    assert tab._count_is_unpredictable() is False


def test_arming_a_patch_set_refreshes_the_headline(qapp, tmp_path, monkeypatch):
    """B3: THE ARITHMETIC WAS RIGHT AND NOTHING CALLED IT.

    Arming a set is the moment it starts deciding the count. A challenge round
    loaded a 420-patch honeycomb in Guided and the panel stayed on the previous
    chart's 345 over one page until the Pages box was touched, after which it
    was right at every page count. In Manual every preset click showed the
    PREVIOUS preset's number.

    The shipped tests could not see it, because each one sets
    `_preset_ti1_path` by hand and then calls `_update_patch_count()` by hand.
    This asserts the gesture does the calling.

    MUTATION: remove the call from the arming site and this goes red.
    """
    tab = _tab(tmp_path)
    called: list = []
    monkeypatch.setattr(type(tab), "_update_patch_count",
                        lambda self: called.append(1))

    armed = tmp_path / "armed.ti1"
    # Not a targen file: `_rebind_patch_set_from_run` returns early for those,
    # because a targen set is rebuilt rather than re-attached.
    armed.write_text('CTI1\n\nORIGINATOR "ChromIQ patch editor"\n'
                     'NUMBER_OF_SETS 420\nBEGIN_DATA\nEND_DATA\n',
                     encoding="utf-8")
    tab._rebind_patch_set_from_run(armed)

    assert tab._preset_ti1_path == armed, "the premise failed: nothing was armed"

    assert called, (
        "arming a patch set left the headline showing the previous chart's "
        "count until something else happened to refresh it")
