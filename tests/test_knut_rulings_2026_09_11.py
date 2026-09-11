"""Knut's three answers of 2026-09-11 13:35 on #182.

**1. The custom paper size carries its unit.** *"you forgot the mm in the custom
paper size in the name, as used in the presets given. The generator should thus
give the name, as your example given here, 'i1Pro-100x150mm-600p-4pages-
Portrait.'"*

**2. A square page is Square.** *"when both Custom size boxes are the same, say
'Square' instead of Portrait or Landscape."* That closes the one case his
2026-09-10 ruling left open, where the name carried no orientation word at all.

**3. Every built-in preset carries the fixed-seed tag, and it is OFF.** *"since
there is a new tag stored in the chart's json file about the 'Use a fixed seed'
box, can you add programmatically this tag for all built in presets and define
the 'Use a fixed seed' box as OFF? All the built in presets should have 'Use a
fixed seed' OFF as default when loaded. We would like NOT to do this manually
for all presets. All seed numbers stored in the presets should be as they are
today."*

**4. And one thing he confirmed rather than changed** — with "Randomise patch
order" off, the tick is REMEMBERED: *"Remembering is good."* Nothing was built
for it; these cases exist so it cannot quietly stop being true.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager            # noqa: E402
from core.settings import AppSettings                # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _panel():
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel()


# =====================================================================
# 1. the millimetres
# =====================================================================
@pytest.mark.parametrize("paper, token", [
    ("100x150", "100x150mm"),
    ("130x180", "130x180mm"),
    ("250x150", "250x150mm"),
    ("20.5x30", "20.5x30mm"),      # the spin boxes can be given decimals
])
def test_a_custom_size_carries_its_millimetres(paper, token):
    from data.patch_db import paper_name_token
    assert paper_name_token(paper) == token


@pytest.mark.parametrize("code, token", [
    ("4x6", "4x6in"),        # 4 x 6 INCHES, not 4 x 6 millimetres
    ("11x17", "Tabloid"),    # likewise: an inch designation with a name
    ("483x329", "A3Plus"),   # a millimetre pair the table already names
    ("203x254", "8x10in"),
    ("A4", "A4"),
])
def test_a_named_paper_never_grows_a_millimetre_suffix(code, token):
    """The rule is about the size the user TYPES in the Custom boxes. Every code
    the paper table names resolves through its label, so the two inch sizes that
    happen to look like a millimetre pair cannot be mistaken for one."""
    from data.patch_db import paper_name_token
    assert paper_name_token(code) == token


def test_the_suggested_name_reads_exactly_as_he_wrote_it(qapp, tmp_path):
    """His own example: ``i1Pro-100x150mm-600p-4pages-Portrait``. Driven through
    the real Custom size boxes, with the patch count and pages forced so the
    whole shape of the name is on the assertion rather than just the paper."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    panel = tab._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(100)
    panel.custom_h.setValue(150)
    tab._manual_pages_spin.setValue(4)
    tab._loaded_ti1_patch_count = lambda: 600
    assert tab._suggest_target_name() == "i1Pro-100x150mm-600p-4pages-Portrait"


# =====================================================================
# 2. the square page
# =====================================================================
@pytest.mark.parametrize("w, h, word", [
    (100, 150, "Portrait"),
    (150, 100, "Landscape"),
    (200, 200, "Square"),
    (1.0, 1.0, "Square"),
])
def test_orientation_word(w, h, word):
    from data.patch_db import orientation_word
    assert orientation_word(w, h) == word


def test_a_square_page_says_square_in_the_suggested_name(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    panel = tab._manual_layout_panel
    panel.paper.setCurrentIndex(panel.paper.findData("__custom__"))
    panel.custom_w.setValue(200)
    panel.custom_h.setValue(200)
    assert tab._suggest_target_name().endswith("-Square")


def test_both_name_generators_answer_a_square_sheet_the_same_way(qapp, settings):
    """THE EDITOR HAD ITS OWN COPY OF THE RULE AND IT DISAGREED.

    ``Ti2RelayoutDialog._suggest_chart_name`` read ``"Landscape" if w > h else
    "Portrait"``, so a square sheet was Portrait there and wordless in Create
    Chart. One name, two generators, two answers. Both now ask
    :func:`data.patch_db.orientation_word`."""
    import workflow.ti2_relayout as R
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    from ui.tabs.tab_chart import TabChart
    d = Ti2RelayoutDialog(ArgyllRunner(settings), settings)
    spec = R.ChartSpec.new(instrument_flag="i1", paper_flag="200x200")
    spec.paper_mm = (200.0, 200.0)
    d._set_chart(spec, [(50.0, 50.0, 50.0)] * 9, "x")
    editor = d._suggest_chart_name()
    _, chart_tab_word = TabChart._paper_name_and_orientation("200x200")
    assert editor.endswith("-Square"), editor
    assert chart_tab_word == "Square"


@pytest.mark.parametrize("marker, name", [
    ("100x150", "i1Pro-100x150mm-600p-4pages-Portrait by Pharmacist"),
    ("130x180", "i1Pro-130x180mm-648p-3pages-Portrait by Pharmacist"),
])
def test_the_two_custom_paper_builtins_are_named_by_their_own_rule(marker, name):
    """A BUILT-IN'S DEFAULT TARGET NAME IS THE NAME OF A FOLDER ON DISK, and it
    has to be the name the generator would produce for the same sheet, or the
    app disagrees with the rule its own help icon explains. These two read
    ``i1Pro-100x150-600p-4pages`` and ``i1Pro-130x180-648p-3pages`` until
    2026-09-11: no unit, and no orientation, on the only two bundled charts
    whose paper is a custom size. 100 < 150 and 130 < 180, so both are
    Portrait."""
    from ui.tabs.tab_chart import PREBUILT_PRESETS
    got = next(v[1] for v in PREBUILT_PRESETS.values() if marker in v[0])
    assert got == name


def test_every_custom_paper_builtin_agrees_with_the_generator():
    """The rule, not the two strings: any bundled chart filed under a
    ``<W>x<H>`` paper folder must carry that folder's generated paper token and
    orientation in its default target name. A twelfth photo-card size added next
    month is caught by this without anyone remembering to extend the case
    above."""
    import re
    from data.patch_db import orientation_word, paper_name_token
    from ui.tabs.tab_chart import PREBUILT_PRESETS
    seen = 0
    for stem, name in PREBUILT_PRESETS.values():
        folder = stem.split("/")[-3]
        m = re.fullmatch(r"(\d+)x(\d+)", folder)
        if not m:
            continue
        seen += 1
        token = paper_name_token(folder)
        word = orientation_word(float(m.group(1)), float(m.group(2)))
        assert f"-{token}-" in name, (name, token)
        assert f"-{word}" in name, (name, word)
    assert seen == 2, f"expected the two photo-card sheets, found {seen}"


def test_the_help_icon_explains_the_rule_it_implements(qapp, tmp_path):
    """Knut asked for the rule to be *"explained in the help icon"*, and then
    corrected the rule twice. The explanation has to move with it, or the window
    documents behaviour the app no longer has."""
    from ui.tabs.tab_chart import TabChart
    text = TabChart._auto_suffix_tooltip()
    assert "100x150mm" in text
    assert "Square" in text
    assert "millimetres" in text
    assert "gets neither word" not in text      # the superseded ruling


# =====================================================================
# 3. the fixed-seed tag on every built-in preset
# =====================================================================
def test_the_constant_says_off():
    from ui.tabs.tab_chart import BUILTIN_PRESET_SEED_FIXED
    assert BUILTIN_PRESET_SEED_FIXED is False


def test_set_fixed_seed_tag_does_not_touch_the_seed_number(qapp):
    """*"All seed numbers stored in the presets should be as they are today."*
    Only the tick moves."""
    p = _panel()
    p.randomize_cb.setChecked(True)
    p.fixed_seed_cb.setChecked(True)
    p.seed_spin.setValue(31337)
    p.set_fixed_seed_tag(False)
    assert p.fixed_seed_cb.isChecked() is False
    assert int(p.seed_spin.value()) == 31337          # untouched
    assert p.seed_spin.isEnabled() is False           # …and greyed with its tick
    assert p.get_recipe().seed_fixed is False         # the tag really moved
    assert p.get_recipe().seed is None                # …so no stale seed is applied


def test_set_fixed_seed_tag_is_silent(qapp):
    """A preset being loaded is not a person editing a setting: the live preview
    must not be asked to redraw from inside a preset selection. ``show_built_seed``
    is silent for the same reason."""
    p = _panel()
    p.randomize_cb.setChecked(True)
    p.fixed_seed_cb.setChecked(True)
    p._loading = False
    fired = []
    p.changed.connect(lambda *_a: fired.append(1))
    p.set_fixed_seed_tag(False)
    assert fired == [], "set_fixed_seed_tag emitted changed"


def test_a_builtin_recipe_is_tagged_off_even_when_it_carries_a_seed(qapp, tmp_path):
    """THE FALLBACK IS NOT THE ANSWER, AND THIS IS THE CASE THAT SHOWS IT.

    A recipe with ``seed_fixed=None`` means "written before the tag existed", and
    the panel then reads the tick off ``seed is not None``. No bundled preset
    carries a seed today, so leaving the tag out happens to look right — and a
    built-in added tomorrow WITH a seed would tick the box on load, which is the
    exact fault he reported on 2026-09-10. The tag is therefore forced."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    key = next(k for k, p in KNUT_PRESETS_BY_KEY.items()
               if p.layout_recipe is not None)
    preset = KNUT_PRESETS_BY_KEY[key]
    # A shipped preset, given a stored seed it does not have today.
    seeded = dict(preset.layout_recipe, seed=4242)
    import dataclasses
    KNUT_PRESETS_BY_KEY[key] = dataclasses.replace(preset, layout_recipe=seeded)
    try:
        tab._manual_layout_panel.fixed_seed_cb.setChecked(True)
        tab._seed_knut_preset(key)
        assert tab._manual_layout_panel.fixed_seed_cb.isChecked() is False
        # …and his other sentence: the number itself is still the preset's.
        assert int(tab._manual_layout_panel.seed_spin.value()) == 4242
    finally:
        KNUT_PRESETS_BY_KEY[key] = preset


def test_every_builtin_family_leaves_the_tick_off(qapp, tmp_path):
    """The four dispatch branches hand the layout panel very different things,
    and two of them hand it nothing at all. Driven on screen 2026-09-11, the
    eleven prebuilt-file "by Pharmacist" presets came back still ticked with the
    previous chart's seed still in the box. `_set_builtin_fixed_seed_off` runs
    after every branch."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    panel = tab._manual_layout_panel
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(True)
    panel.seed_spin.setValue(31337)
    tab._set_builtin_fixed_seed_off()
    assert panel.fixed_seed_cb.isChecked() is False
    assert int(panel.seed_spin.value()) == 31337


def test_the_untick_runs_after_the_dispatch_for_every_builtin(qapp):
    """The call has to sit on the shared path, not in one branch of it — that is
    what makes it cover the prebuilt-file presets, the TC9.18 built-in and the
    ColorMunki triple-density ones, none of which hand the panel a recipe."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_preset_selected)
    assert "_set_builtin_fixed_seed_off()" in src
    # …and before the branch returns, or it would never run.
    call = src.index("_set_builtin_fixed_seed_off()")
    locks = src.index("self._update_preset_locks()")
    assert call < locks


def test_selecting_a_prebuilt_file_preset_unticks_the_box(qapp, tmp_path, monkeypatch):
    """THE BRANCH THAT WAS ACTUALLY BROKEN, driven through the dropdown slot.

    The eleven "by Pharmacist" presets copy a pre-rendered chart and hand the
    layout panel nothing, so the box kept the previous chart's tick and the
    previous chart's number. The copy itself is stubbed out here (it opens
    project windows and writes files); what is being measured is the state the
    slot leaves behind, which is where the fault was."""
    tab = _tab(tmp_path)
    tab._manual_btn.setChecked(True)
    tab._set_engine_checked(True)
    from ui.tabs.tab_chart import PREBUILT_PRESETS
    key = next(iter(PREBUILT_PRESETS))
    idx = tab._preset_combo.findData(key)
    assert idx > 0, "the prebuilt preset is not in the dropdown"

    monkeypatch.setattr(type(tab), "_apply_prebuilt_preset",
                        lambda self, k, n=None: True)
    panel = tab._manual_layout_panel
    panel.randomize_cb.setChecked(True)
    panel.fixed_seed_cb.setChecked(True)
    panel.seed_spin.setValue(31337)

    tab._on_preset_selected(idx)

    assert panel.fixed_seed_cb.isChecked() is False
    assert int(panel.seed_spin.value()) == 31337
    assert panel.get_recipe().seed_fixed is False


def test_no_builtin_preset_recipe_hand_carries_the_tag():
    """*"We would like NOT to do this manually for all presets."* The tag comes
    from one constant applied by code; if it ever starts appearing inside the
    bundled dicts, this is the reminder that the mechanism was meant to make
    that unnecessary."""
    from ui.tabs.tab_chart import KNUT_PRESETS
    offenders = [p.slug for p in KNUT_PRESETS
                 if p.layout_recipe is not None and "seed_fixed" in p.layout_recipe]
    assert offenders == [], offenders


def test_a_user_preset_is_not_given_the_builtin_tag(qapp):
    """The ruling is about the BUILT-INS. A user preset still drops both the seed
    and the tag when it is saved (`PresetStore.set`), which leaves it at "no
    evidence" rather than an asserted OFF."""
    from workflow.layout_engine.presets import PresetStore
    st = PresetStore()
    st.set(LayoutRecipe(randomize=True, seed=4242, seed_fixed=True))
    got = next(iter(st.as_named_dict().values()))
    assert got["seed"] is None
    assert got["seed_fixed"] is None


# =====================================================================
# 4. "Remembering is good" — confirmed, and pinned
# =====================================================================
@pytest.mark.parametrize("start", [True, False])
def test_the_tick_survives_randomise_off_and_on_again(qapp, start):
    """Knut, 2026-09-11: *"Remembering is good."* Switching "Randomise patch
    order" off greys the tick; it does not clear it, and switching randomising
    back on returns it exactly as it was left."""
    p = _panel()
    p.randomize_cb.setChecked(True)
    p.fixed_seed_cb.setChecked(start)
    p.seed_spin.setValue(4242)

    p.randomize_cb.setChecked(False)
    assert p.fixed_seed_cb.isEnabled() is False, "the tick should be greyed"
    assert p.fixed_seed_cb.isChecked() is start, "…but not cleared"
    assert p.get_recipe().seed_fixed is start, "…and the tag records it"

    p.randomize_cb.setChecked(True)
    assert p.fixed_seed_cb.isChecked() is start
    assert int(p.seed_spin.value()) == 4242
