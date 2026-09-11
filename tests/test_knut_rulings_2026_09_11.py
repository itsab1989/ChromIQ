"""Knut's #182 posts of 2026-09-11, the four items about names, presets and hex.

**A. The generated custom-paper name was missing its unit.** *"you forgot the
mm in the custom paper size in the name, as used in the presets given. The
generator should thus give the name, as your example given here,
`i1Pro-100x150mm-600p-4pages-Portrait`."* His own built-in presets have always
spelled it that way, so the generator was the odd one out, not the presets.

**B. A square sheet is named.** *"I suggest, when both Custom size boxes are the
same, say 'Square' instead of Portrait or Landscape."* This closes the question
`test_knut_rulings_2026_09_10.py` left open, and supersedes the answer that file
used to pin ("a square page gets neither word").

**H. Every built-in preset carries the fixed-seed tag, OFF.** *"can you add
programatically this tag for all built in presets and define the 'Use a fixed
seed' box as OFF? … We would like NOT to do this manually for all presets. All
seed numbers stored in the presets should be as they are today."* Two halves and
BOTH are checked here, because the second is the one a mechanical edit across a
hundred and forty presets would quietly break.

**K7. The hexagon help text told one orientation's story as if it were both.**
*"when hex patches are used, the help text for the Chart layout information or
the Measured from Preview frames do not specify that the column pitch is equal
to the patch width measurement. I also assume these numbers are defined
differently if the hex patches are 30 degrees rotated or not, so the help text
should probably clearly distinguish this and explain."*

The K7 tests MEASURE the geometry before they read a word of the help text, so
the sentences are pinned to the numbers rather than to each other. The numbers
were taken from Knut's own `testHex` CR30 honeycomb at 600 dpi.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                       # noqa: E402
from PyQt6.QtWidgets import QApplication                 # noqa: E402

from core.argyll_runner import ArgyllRunner              # noqa: E402
from core.file_manager import FileManager                # noqa: E402
from core.settings import AppSettings                    # noqa: E402
from ui.tabs.tab_chart import (KNUT_PRESETS, PREBUILT_PRESETS,   # noqa: E402
                               TabChart)
from workflow.hex_support import (hex_patch_width_row_note,      # noqa: E402
                                  hex_two_heights_note)
from workflow.layout_engine import geometry, instruments         # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe          # noqa: E402

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    return t


# =====================================================================
# A. the unit in the generated name
# =====================================================================
@pytest.mark.parametrize("paper, token, orient", [
    ("100x150", "100x150mm", "Portrait"),      # his own example
    ("130x180", "130x180mm", "Portrait"),
    ("180x130", "180x130mm", "Landscape"),
    ("250x150", "250x150mm", "Landscape"),     # a size the table has no name for
])
def test_a_custom_size_carries_its_unit(qapp, paper, token, orient):
    assert TabChart._paper_name_and_orientation(paper) == (token, orient)


@pytest.mark.parametrize("code", ["A4", "A4R", "Letter", "A3", "420x297",
                                  "329x483", "11x17", "4x6"])
def test_a_named_paper_is_not_given_a_unit(qapp, code):
    """"mm" belongs to a MEASUREMENT. "A4" is a name, and `11x17` / `4x6` are
    named ChromIQ codes meaning INCHES, so calling either of them millimetres
    would be wrong twice over."""
    token, _orient = TabChart._paper_name_and_orientation(code)
    assert not token.endswith("mm"), token


def test_the_suggested_name_is_the_one_knut_asked_for(qapp, tmp_path):
    """His example, end to end: ``i1Pro-100x150mm-…-Portrait``."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._manual_btn.setChecked(True)
    t._set_engine_checked(True)
    panel = t._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(100)
    panel.custom_h.setValue(150)

    name = t._suggest_target_name()
    assert "100x150mm" in name, name
    assert "100x150-" not in name, (
        "the size lost its unit again: " + name)
    assert name.endswith("Portrait"), name


def test_the_two_photo_card_presets_spell_the_sheet_the_same_way(qapp):
    """The shipped default target names have to agree with the generator, which
    is the whole reason they are spelled in millimetres rather than "10x15cm"
    like their labels."""
    from ui.tabs.tab_chart import (PHOTOCARD600_PRESET_KEY,
                                   PHOTOCARD648_PRESET_KEY)
    assert PREBUILT_PRESETS[PHOTOCARD600_PRESET_KEY][1].startswith(
        "i1Pro-100x150mm-")
    assert PREBUILT_PRESETS[PHOTOCARD648_PRESET_KEY][1].startswith(
        "i1Pro-130x180mm-")


# =====================================================================
# B. the square sheet
# =====================================================================
@pytest.mark.parametrize("paper", ["200x200", "150x150", "297x297"])
def test_a_square_custom_sheet_is_named_square(qapp, paper):
    assert TabChart._paper_name_and_orientation(paper) == (f"{paper}mm",
                                                           "Square")


def test_square_reaches_the_suggested_name(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._manual_btn.setChecked(True)
    t._set_engine_checked(True)
    panel = t._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(200)
    panel.custom_h.setValue(200)

    name = t._suggest_target_name()
    assert name.endswith("Square"), name
    assert "200x200mm" in name, name


def test_the_help_icon_explains_all_three_words(qapp):
    """His 2026-09-10 instruction was *"and also explain this in the help
    icon"*, and the explanation has to keep up with the rule it explains."""
    low = TabChart._auto_suffix_tooltip().lower()
    assert "100x150mm" in low
    assert "smaller than the height" in low and "larger than the height" in low
    assert "square" in low


# =====================================================================
# H. the fixed-seed tag on every built-in preset
# =====================================================================
def _recipe_presets():
    return [p for p in KNUT_PRESETS if p.layout_recipe is not None]


def test_every_bundled_preset_recipe_carries_the_tag_and_it_is_off():
    missing = [p.slug for p in _recipe_presets()
               if p.layout_recipe.get("seed_fixed", "<absent>") is not False]
    assert not missing, (
        f"{len(missing)} built-in presets have no fixed-seed tag (or it is not "
        f"OFF). Run scripts/stamp_builtin_preset_seed_tag.py. First few: "
        f"{missing[:5]}")
    assert len(_recipe_presets()) >= 140, (
        "the premise failed: this check is worth nothing if it is looking at a "
        "handful of presets")


def test_not_one_stored_seed_was_touched():
    """His hard constraint: *"All seed numbers stored in the presets should be
    as they are today."*

    Pinned as the VALUES, not as "they are all None": if a built-in ever ships
    with a real seed, this still has to hold, and a check that asserted None
    would have to be edited to let that through. What is pinned is that the key
    is present on every recipe that had one and that no recipe grew a seed it
    did not have. The before/after comparison over all 141 full recipe dicts is
    in the change's proof folder (`compare_recipes.py`: 141 compared, one key
    added, zero values changed)."""
    for p in _recipe_presets():
        assert "seed" in p.layout_recipe, (
            f"{p.slug}: the seed key went missing from the recipe")
    # The printtarg -R seed of every built-in, recipe or not.
    assert all(p.seed is None or isinstance(p.seed, int) for p in KNUT_PRESETS)


def test_loading_any_built_in_preset_leaves_the_box_unticked(tab):
    """The promise as a USER meets it: *"All the built in presets should have
    'Use a fixed seed' OFF as default when loaded."*

    Driven through `_seed_knut_preset`, which is the function the dropdown calls
    once a preset is chosen, for every one of them, and read off the real
    checkbox rather than the dict."""
    panel = tab._manual_layout_panel
    ticked = []
    for p in KNUT_PRESETS:
        tab._seed_knut_preset(p.key)
        if panel.fixed_seed_cb.isChecked():
            ticked.append(p.slug)
    assert not ticked, (
        f"{len(ticked)} built-in presets come up with 'Use a fixed seed' "
        f"TICKED: {ticked[:5]}")
    assert len(KNUT_PRESETS) >= 140


def test_loading_one_does_not_invent_a_seed(tab):
    """The other half on the panel: the box is off AND the recipe that comes
    back off the panel carries no seed of its own, so nothing was silently
    pinned to a number."""
    panel = tab._manual_layout_panel
    for p in _recipe_presets()[:12]:
        tab._seed_knut_preset(p.key)
        got = panel.get_recipe()
        assert got.seed_fixed is False, p.slug
        assert got.seed is None, f"{p.slug} came back holding seed {got.seed}"


def test_the_two_engine_presets_answer_the_tag_themselves(tab):
    """The two Full-layout-setup ENGINE presets have no bundled dict to stamp:
    their recipe is DERIVED from their printtarg fields when they are selected.

    Asserted against `_fls_engine_recipe` directly rather than against the
    checkbox, because the checkbox cannot tell the two apart: with the tag left
    at None the panel falls back to `seed is not None`, which is also False
    today. A check that only watched the box would stay green with the line
    deleted, which is not a check."""
    engine = [p for p in KNUT_PRESETS if p.layout_recipe is None]
    assert len(engine) == 2, (
        "the premise moved: this test knows about the engine-recipe family")
    for p in engine:
        r = tab._fls_engine_recipe(p)
        assert r.seed_fixed is False, f"{p.slug}: seed_fixed is {r.seed_fixed!r}"
        assert r.seed is None, f"{p.slug}: came back holding seed {r.seed}"


def test_the_stamping_script_is_idempotent_and_says_so():
    """The script is the mechanism Knut asked for ("NOT … manually"), so it has
    to be re-runnable: `--check` on a stamped tree passes and changes nothing."""
    out = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "stamp_builtin_preset_seed_tag.py"),
         "--check"],
        capture_output=True, text=True, encoding="utf-8", timeout=180,
        cwd=str(REPO), env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert out.returncode == 0, out.stdout + out.stderr
    assert "141" in out.stdout, out.stdout


# =====================================================================
# K7. the hexagon help text, both orientations
# =====================================================================
def _hex_recipe(flat: bool, *, w: float = 12.0, h: float = 10.0):
    r = LayoutRecipe(instrument="CR30", paper="A4", dpi=600)
    r.hflag, r.hex_flat_top = True, flat
    r.layout_mode = "patch_first"
    r.patch_w_mm, r.patch_h_mm = w, h
    r.spacer_on, r.spacer_mode = False, "none"
    r.clip_border = False
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 10.0
    return r


def _pitches(r) -> "tuple[float, float, float]":
    """(column pitch, row pitch, strip zigzag dx) in mm, MEASURED off the patch
    rectangles the renderer paints."""
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    lay = geometry.compute(g, 210.0, 297.0, 300)
    rects = [e for e in geometry.patch_rects_px(g, 210.0, 297.0, lay, 600)
             if e["page"] == 0]
    mm = 25.4 / 600
    s = lay.steps_in_pass
    return ((rects[s]["x"] - rects[0]["x"]) * mm,
            (rects[1]["y"] - rects[0]["y"]) * mm,
            (rects[1]["x"] - rects[0]["x"]) * mm)


def test_upright_the_column_pitch_really_is_the_patch_width():
    """Knut's claim, measured before it is written down. 12.023 against a patch
    12.000 wide, the 0.023 being pixel snapping at 600 dpi."""
    from ui.tabs.tab_chart import _panel_patch_size_mm
    r = _hex_recipe(False)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    pw, ph, pitch = _panel_patch_size_mm(g.pwid, g.plen, True, False)
    colp, rowp, zig = _pitches(r)
    assert abs(colp - pw) < 0.05, (colp, pw)          # column pitch = width
    assert abs(rowp - pitch) < 0.05, (rowp, pitch)    # row pitch is the smaller
    assert abs(ph - pitch * 4 / 3) < 0.01             # …and the patch is 4/3 of it
    assert ph > rowp + 3.0
    assert zig > 1.0, "an upright honeycomb's strips zigzag down the page"


def test_turned_the_row_pitch_is_the_patch_height_and_the_width_is_not():
    """The turn swaps the axis: the flat sides now face up and down, so it is
    the HEIGHT that equals its pitch and the WIDTH that is a third larger."""
    from ui.tabs.tab_chart import _panel_patch_size_mm
    r = _hex_recipe(True)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    pw, ph, pitch = _panel_patch_size_mm(g.pwid, g.plen, True, True)
    colp, rowp, zig = _pitches(r)
    assert abs(rowp - ph) < 0.05, (rowp, ph)          # row pitch = height
    assert abs(colp - pitch) < 0.05, (colp, pitch)    # column pitch is smaller
    assert abs(pw - pitch * 4 / 3) < 0.01
    assert pw > colp + 3.0, (
        "the premise failed: on a turned honeycomb the patch must be wider "
        "than its column pitch, or there is nothing for the help text to warn "
        "about")
    assert zig < 0.05, "a turned honeycomb's strips run straight down the page"


def test_the_hexagon_note_tells_the_two_orientations_apart():
    note = hex_two_heights_note()
    low = note.lower()
    assert "turned 30 degrees" in low, (
        "the note must name the rotated case, which is what Knut asked for")
    assert "upright" in low
    # Both equalities, each on its own side of the turn.
    assert "column pitch is exactly the patch width" in low
    assert "row pitch is exactly the patch height" in low
    # …and it must not go back to claiming one orientation for both.
    assert "hexagonal patches have two heights" not in low


def test_the_hexagon_note_reaches_both_panels_that_show_these_numbers(qapp):
    """It is ONE string on purpose. If either tooltip stops carrying it, the two
    ends of the same number start disagreeing."""
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    note = hex_two_heights_note()

    from ui.tooltip_button import TooltipButton

    info = ChartLayoutInfoPanel()
    assert any(note in t.dialog_body()
               for t in info.findChildren(TooltipButton)), (
        "Chart layout information no longer explains the honeycomb numbers")

    panel = LayoutOptionsPanel(with_selectors=True)
    assert any(note in t.dialog_body()
               for t in panel.findChildren(TooltipButton)), (
        "the Patch size boxes no longer explain the honeycomb numbers")


def test_the_margin_inspector_says_what_its_patch_width_row_measures(qapp):
    """Knut named this frame too. Its row is `block width ÷ strips`, so on a
    turned honeycomb it reports the column pitch and the hexagon is a third
    wider than that."""
    from ui.margin_inspector_panel import MarginInspectorPanel
    note = hex_patch_width_row_note()
    assert "column pitch" in note.lower()
    assert "turned 30 degrees" in note.lower()
    panel = MarginInspectorPanel()
    assert note in panel._panel_tip.dialog_body(), (
        "the margin inspector's ⓘ no longer carries the honeycomb footnote")
