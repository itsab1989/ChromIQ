"""Regression tests for Knut's follow-ups: #59 preset overwrite, #60 Add total,
#45 editor→Create-Chart settings transfer, #62 Save & apply suggested name."""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit  # noqa: E402

import workflow.ti2_relayout as R  # noqa: E402
from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    # These tests exercise the printtarg path explicitly — since 4.0.0
    # the ChromIQ layout engine is the Manual default (schema 18), so
    # the mode under test is pinned rather than inherited.
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


# --- #59: overwrite prompt fires for custom-vs-custom -----------------------

def test_save_over_custom_preset_asks_overwrite(qapp, settings, monkeypatch):
    from ui.tabs.tab_chart import TabChart
    settings.set("create_chart_auto_suffix", False)   # test match logic, not suffix
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    presets = {"Alpha": {"auto_run": False, "attached_ti1": False},
               "Beta":  {"auto_run": False, "attached_ti1": False}}
    t._save_presets_to_settings(presets)
    t._populate_preset_combo(presets, select_name="Alpha")

    asked = []
    monkeypatch.setattr(t, "_confirm_overwrite_preset",
                        lambda n: (asked.append(n), False)[1])

    def fake_exec(self):
        for le in self.findChildren(QLineEdit):
            le.setText("Beta")          # collide with the other custom preset
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    t._on_preset_save()
    assert asked == ["Beta"]            # custom-vs-custom collision is caught


def test_save_with_invisible_char_still_matches(qapp, settings, monkeypatch):
    # #59: a name pasted with a zero-width space looked identical but didn't
    # match, so no overwrite prompt fired and a duplicate was created. The name
    # is now normalised (control/format chars dropped) before comparing.
    from ui.tabs.tab_chart import TabChart, _clean_preset_name
    assert _clean_preset_name("MyChart​") == "MyChart"
    settings.set("create_chart_auto_suffix", False)  # test the match logic, not the suffix
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._save_presets_to_settings({"MyChart": {"auto_run": True, "attached_ti1": False}})
    asked = []
    monkeypatch.setattr(t, "_confirm_overwrite_preset",
                        lambda n: (asked.append(n), False)[1])

    def fake_exec(self):
        for le in self.findChildren(QLineEdit):
            le.setText("MyChart​")     # trailing zero-width space
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    t._on_preset_save()
    assert asked == ["MyChart"]


def test_punctuation_variants_are_distinct_names(qapp, settings, monkeypatch):
    # #59 (Knut): dots, underscores and hyphens are meaning-bearing — a dot and
    # an underscore name must stay DISTINCT (not collapsed), so saving one when
    # the other exists does NOT prompt to overwrite. The dot-vs-underscore
    # duplicate is prevented at the source (the editor keeps dots) instead.
    from ui.tabs.tab_chart import TabChart, _preset_match_key
    assert _preset_match_key("A3-w11.5mm") != _preset_match_key("A3-w11_5mm")
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._save_presets_to_settings({"A3-w11.5mm": {"auto_run": True, "attached_ti1": False}})
    asked = []
    monkeypatch.setattr(t, "_confirm_overwrite_preset",
                        lambda n: (asked.append(n), False)[1])

    def fake_exec(self):
        for le in self.findChildren(QLineEdit):
            le.setText("A3-w11_5mm")               # a genuinely different name
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    t._on_preset_save()
    assert asked == []                              # distinct → no overwrite prompt


def test_editor_save_as_name_keeps_dots(qapp, settings, monkeypatch):
    # #59 / #70: the editor's Save As (chart-layout export) must keep dots (so
    # "w11.5mm" stays dotted), not force underscores. (The profile name is no
    # longer asked for here — it lives in the Create Chart tab.)
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    from PyQt6.QtWidgets import QDialog, QLineEdit
    d = Ti2RelayoutDialog(ArgyllRunner(settings), settings)

    def fake_exec(self):
        for le in self.findChildren(QLineEdit):
            le.setText("Epson-A3-w11.5mm-Portrait")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    name, _location = d._prompt_save_as_name()
    assert name == "Epson-A3-w11.5mm-Portrait"   # dot preserved


def test_confirm_overwrite_preset_runs(qapp, settings, monkeypatch):
    # Regression (#59): _confirm_overwrite_preset built a QMessageBox that wasn't
    # imported → NameError at runtime, so the prompt never showed even though the
    # match was found. Earlier tests monkeypatched this method and missed it.
    from PyQt6.QtWidgets import QMessageBox
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)   # don't block
    assert t._confirm_overwrite_preset("test") in (True, False)   # must not raise


def test_save_over_existing_name_calls_real_confirm(qapp, settings, monkeypatch):
    # End-to-end with the REAL confirm dialog (auto-cancelled): saving over an
    # existing preset reaches the prompt without crashing.
    from PyQt6.QtWidgets import QMessageBox, QDialog, QLineEdit
    from ui.tabs.tab_chart import TabChart
    settings.set("create_chart_auto_suffix", False)   # name the preset exactly "test"
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._save_presets_to_settings({"test": {"auto_run": True, "attached_ti1": False}})
    seen = {}
    monkeypatch.setattr(QMessageBox, "exec",
                        lambda self: seen.setdefault("shown", True) or 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: (
        [le.setText("test") for le in self.findChildren(QLineEdit)],
        QDialog.DialogCode.Accepted)[1])
    t._on_preset_save()
    assert seen.get("shown")    # the overwrite prompt actually appeared


def test_save_under_new_name_does_not_ask(qapp, settings, monkeypatch):
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._save_presets_to_settings({"Alpha": {"auto_run": False, "attached_ti1": False}})
    asked = []
    monkeypatch.setattr(t, "_confirm_overwrite_preset",
                        lambda n: (asked.append(n), True)[1])

    def fake_exec(self):
        for le in self.findChildren(QLineEdit):
            le.setText("BrandNew")
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", fake_exec)
    t._on_preset_save()
    assert asked == []                  # no collision → no prompt


# --- #60: Add-window total = existing + built program -----------------------

def test_add_total_is_additions_shown_always(qapp, settings):
    # Knut's #60 clarification: the Total is the additions the current set
    # selection produces (NOT the existing chart), shown even with generate off,
    # and it includes white/black + fill.
    from ui.dialogs.ti2_relayout_dialog import _AddPatchesDialog
    existing = [(float(i % 101), float((i * 7) % 101), float((i * 13) % 101))
                for i in range(460)]
    d = _AddPatchesDialog(settings=settings, existing_patches=existing)
    for cb in (d._gen_cube, d._gen_skin, d._gen_blues, d._gen_greens,
               d._gen_sunrises, d._gen_neutral, d._gen_nearneutral,
               d._gen_edges, d._gen_hs, d._gen_pastel, d._gen_image,
               d._gen_whiteblack, d._gen_fill):
        cb.setChecked(False)
    d._gen_cube.setChecked(True)
    d._gen_cube_n.setValue(5)

    def shown_total() -> int:
        d._update_gen_counts()
        d._do_push_live_preview()
        import re
        m = re.search(r"([\d,]+)", d._gen_total.text())
        return int(m.group(1).replace(",", ""))

    # Generate OFF → still shows the additions (not 0, not the existing 460).
    d._add_mode_single.setChecked(True)
    off = shown_total()
    assert off == len(d._build_generated_program())
    assert off > 0 and off != 460

    # Generate ON → the same additions (no existing patches folded in).
    d._add_mode_gen.setChecked(True)
    assert shown_total() == len(d._build_generated_program())

    # White/black + fill are included in the additions total.
    d._gen_whiteblack.setChecked(True)
    d._gen_fill.setChecked(True)
    d._gen_fill_to.setValue(900)
    assert shown_total() == len(d._build_generated_program())

    # The Add dialog also shows the resulting chart size (existing + additions).
    import re
    m = re.search(r"([\d,]+)", d._gen_after_total.text())
    after = int(m.group(1).replace(",", ""))
    assert after == 460 + len(d._build_generated_program())


# --- #45: editor TD chart keeps custom margin / patch scale -----------------

def test_td_chart_transfers_custom_margin_and_scale(qapp, settings):
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    # Triple density is ColorMunki-only; set the instrument so the row is live.
    t._set_manual_value("printtarg", "-i", "CM")
    opts = R.LayoutOptions(triple_density=True, margin_mm=6.0, patch_scale=1.06,
                           spacer_scale=1.0, double_density=False)
    t._seed_manual_printtarg_from_layout(opts)

    def val(flag):
        for pw in t._manual_widgets["printtarg"]:
            if pw.flag == flag:
                return pw.get_raw_value()
        return None
    assert t._manual_td_check.isChecked()          # TD preserved
    assert val("-m") == 6                           # not clobbered to TD's 5
    assert abs(float(val("-a")) - 1.06) < 0.001     # not clobbered to TD's 1.3


# --- #62 follow-up: live, locked descriptive suffix -------------------------

def test_profile_name_field_is_plain(qapp, settings):
    # #70 (Knut's model): the Create Chart name is a plain *printer-profile* name
    # — no descriptive prefix is glued onto it. It starts as the manual default
    # and whatever the user types is taken verbatim.
    from ui.widgets import PrefixLockedLineEdit
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)

    t._switch_mode("guided")
    f = t._target_name_edit
    assert isinstance(f, PrefixLockedLineEdit)
    assert not f.text().startswith("i1Pro-")       # no descriptive prefix
    f.setText("Canon_Pro1000_Baryta")
    t._refresh_name_prefix()                        # must not re-glue a prefix
    assert f.text() == "Canon_Pro1000_Baryta"


def test_preset_does_not_overwrite_typed_profile_name(qapp, settings):
    # #70 (the conceptual fix): selecting/seeding a preset is a chart-LAYOUT
    # choice and must never overwrite a profile name the user already typed.
    from ui.tabs.tab_chart import TabChart, KNUT_PRESETS_BY_KEY
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    f = t._manual_target_name_edit
    f.setText("MyCanonProfile")                     # the user's chosen name
    key = next(k for k, p in KNUT_PRESETS_BY_KEY.items()
               if p.slug == "fls_i1pro_a4_484p_1page_portrait")
    t._knut_active, t._knut_active_key = True, key
    t._seed_knut_preset(key, KNUT_PRESETS_BY_KEY[key].default_target_name)
    assert f.text() == "MyCanonProfile"             # untouched by the preset


def test_preset_seeds_name_only_when_field_empty(qapp, settings):
    # #70: when the name field is empty, a seeded preset supplies a sensible
    # fallback so the folder isn't created nameless.
    from ui.tabs.tab_chart import TabChart, KNUT_PRESETS_BY_KEY
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    f = t._manual_target_name_edit
    f.setText("")                                   # nothing typed yet
    key = next(k for k, p in KNUT_PRESETS_BY_KEY.items()
               if p.slug == "fls_i1pro_a4_484p_1page_portrait")
    t._knut_active, t._knut_active_key = True, key
    default = KNUT_PRESETS_BY_KEY[key].default_target_name
    t._seed_knut_preset(key, default)
    assert f.text() == default                       # fallback seeded


def test_sortable_builtin_name_normalisation():
    # #68 #3: instrument leads; "-wXmm" and the colour-set name move to the tail.
    from ui.tabs.tab_chart import _sortable_builtin_name, KNUT_SUFFIX
    assert _sortable_builtin_name(
        "i1Pro", "A4-1168p-2pages-w7.5mm-Portrait" + KNUT_SUFFIX, KNUT_SUFFIX
    ) == "i1Pro-A4-1168p-2pages-Portrait-w7.5mm-TC9.18+Spyderprint Grays"
    # No width token, different family suffix.
    assert _sortable_builtin_name(
        "ColorMunki", "A3-1575p-3pages-Portrait · Full layout setup", " · Full layout setup"
    ) == "ColorMunki-A3-1575p-3pages-Portrait-Full layout setup"


def test_create_chart_suggest_includes_patches_and_orientation(qapp, settings, tmp_path):
    # #62 (Knut): the Create Chart Suggest-name must include the patch count
    # (predicted in guided, the loaded .ti1's count in manual) and the page
    # orientation (from the paper selection), not just instrument-paper-pages.
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)

    # Guided: A3 landscape (420x297), 3 pages, predicted 1575 patches.
    t._switch_mode("guided")
    t._instr_combo.setCurrentIndex(max(0, t._instr_combo.findData("CM")))
    t._paper_combo.setCurrentIndex(max(0, t._paper_combo.findData("420x297")))
    t._pages_spin.setValue(3)
    t._predicted_patch_count = 1575
    assert t._suggest_target_name() == "ColorMunki-A3-1575p-3pages-Landscape"

    # Manual: a loaded preset .ti1 supplies the count; paper A4 → Portrait.
    t._switch_mode("manual")
    ti1 = tmp_path / "set.ti1"
    ti1.write_text("NUMBER_OF_SETS 484\n")
    t._preset_ti1_path = ti1
    t._set_manual_value("printtarg", "-i", "i1")
    t._set_manual_value("printtarg", "-p", "A4")
    if t._manual_pages_spin is not None:
        t._manual_pages_spin.setValue(1)
    assert t._suggest_target_name() == "i1Pro-A4-484p-1page-Portrait"


def test_loaded_ti1_patch_count_for_builtin_presets(qapp, settings):
    # #62 follow-up (Knut): a BUILT-IN preset's bundled .ti1 must also feed the
    # patch count — it doesn't use _preset_ti1_path (that's for user presets), so
    # _builtin_ti1_path must supply it. Reproduces "manual mode built-in shows no
    # 960p in the suggested name".
    import re
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import (
        TabChart, KNUT_PRESETS_BY_KEY, PREBUILT_PRESETS,
    )
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)

    # A Knut preset (bundled per-preset .ti1).
    key, preset = next(iter(KNUT_PRESETS_BY_KEY.items()))
    t._builtin_ti1_path = resource_path(preset.ti1_asset)
    expect = int(re.search(r"NUMBER_OF_SETS\s+(\d+)",
                           t._builtin_ti1_path.read_text("latin-1", "ignore")).group(1))
    assert t._loaded_ti1_patch_count() == expect

    # A prebuilt-files preset (bundled <stem>.ti1).
    pkey, (stem, _name) = next(iter(PREBUILT_PRESETS.items()))
    assert t._builtin_ti1_asset(pkey) == stem + ".ti1"
    t._builtin_ti1_path = resource_path(stem + ".ti1")
    assert t._loaded_ti1_patch_count() and t._loaded_ti1_patch_count() > 0


def test_comparable_presets_lists_ti1_backed(qapp, settings):
    # #66: the "Compare with profile" list is built dynamically from presets
    # that have a .ti1 — built-ins now, and any user preset that bundled one.
    from pathlib import Path
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    groups = t.comparable_presets()
    assert groups, "built-in ti1 presets should be listed"
    for group_label, items in groups:               # grouped by instrument
        assert group_label and items
        for label, path in items:
            assert label and Path(path).is_file() and str(path).endswith(".ti1")


def test_suggested_name_from_settings(qapp, settings):
    from ui.dialogs.ti2_relayout_dialog import Ti2RelayoutDialog
    d = Ti2RelayoutDialog(ArgyllRunner(settings), settings)
    spec = R.ChartSpec.new(instrument_flag="i1", paper_flag="A4")
    spec.paper_mm = (297.0, 210.0)                  # landscape
    d._set_chart(spec, [(50.0, 50.0, 50.0)] * 480, "New chart")
    assert d._suggest_chart_name() == "i1Pro-A4-480p-Landscape"
    # Placeholder basename → use the suggestion; a real target name wins.
    assert d._default_apply_name() == "i1Pro-A4-480p-Landscape"
    d._basename = "Canon_Pro300_Baryta"
    assert d._default_apply_name() == "Canon_Pro300_Baryta"


# --- #73: name page-count uses the real chart, not a locked Pages control ----

def test_name_uses_real_page_count_when_pages_locked(qapp, settings, monkeypatch):
    """A preset/.ti1 layout that printtarg split across 2 sheets must produce a
    "…2pages…" name even though the (greyed) Pages control still reads 1."""
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._manual_pages_spin.setValue(1)
    t._manual_pages_spin.setEnabled(False)        # fixed-layout: control locked
    monkeypatch.setattr(t, "_loaded_ti1_patch_count", lambda: 1224)
    monkeypatch.setattr(t._preview, "page_count", lambda: 2)   # really 2 sheets
    assert "2pages" in t._suggest_target_name()


def test_name_trusts_editable_pages_control(qapp, settings, monkeypatch):
    """When the Pages control is editable (plain targen), its value is trusted
    even if a stale preview reports a different count."""
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("manual")
    t._manual_pages_spin.setValue(1)
    t._manual_pages_spin.setEnabled(True)
    monkeypatch.setattr(t, "_loaded_ti1_patch_count", lambda: 480)
    monkeypatch.setattr(t._preview, "page_count", lambda: 2)
    name = t._suggest_target_name()
    assert "1page" in name and "2pages" not in name
