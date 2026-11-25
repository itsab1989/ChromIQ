"""Guided → Manual settings transfer (#79).

When a chart is generated in Guided mode and the user opens Manual, the Manual
panel is seeded with the same recipe so they can edit the settings used.
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

from tests._guided_chart_fixture import made_in_guided  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _manual(tab, tool, flag):
    for pw in tab._manual_widgets.get(tool, []):
        if pw.flag == flag:
            return pw.get_raw_value()
    return None


def test_transfer_copies_instrument_paper_pages_and_density(tab, tmp_path):
    # Configure Guided mode.
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("CM"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    tab._pages_spin.setValue(2)
    tab._dd_check.setChecked(True)
    tab._target_name_edit.setText("MyPrinter Glossy")

    made_in_guided(tab, tmp_path)
    assert tab._transfer_guided_to_manual() is True

    assert _manual(tab, "printtarg", "-i") == "CM"
    assert _manual(tab, "printtarg", "-p") == "A4"
    assert tab._manual_pages_spin.value() == 2
    assert bool(_manual(tab, "printtarg", "-h")) is True
    # Patch count mirrors Guided's Auto.
    assert tab._manual_auto_patches_check.isChecked() is True
    # Printer profile name carried over.
    assert tab._manual_target_name_edit.text().strip() == "MyPrinter Glossy"


def test_transfer_is_armed_only_after_guided_generate(tab, tmp_path):
    """The one-shot flag fires once on the guided→manual switch, then clears."""
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    made_in_guided(tab, tmp_path)

    tab._switch_mode("manual")
    assert tab._guided_transfer_pending is False
    assert _manual(tab, "printtarg", "-i") == "i1"


def test_no_transfer_without_arming(tab):
    """Switching modes without a fresh guided generate doesn't overwrite manual
    edits."""
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-p", "A3")
    tab._switch_mode("guided")
    tab._switch_mode("manual")          # flag not armed → no transfer
    assert _manual(tab, "printtarg", "-p") == "A3"


def test_switch_carries_instrument_paper_not_the_rest(tab):
    """A plain tab switch (no Generate) carries ONLY instrument + paper, so the
    tabs agree on the device; the rest (density etc.) waits for the post-Generate
    transfer (Knut #2). Snapshot/diff = only what changed moves."""
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("CM"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4R"))
    tab._dd_check.setChecked(True)
    tab._switch_mode("manual")
    assert _manual(tab, "printtarg", "-i") == "CM"     # device carries
    assert _manual(tab, "printtarg", "-p") == "A4R"
    assert bool(_manual(tab, "printtarg", "-h")) is False  # density does NOT
    # Manual→Guided also carries the device.
    tab._set_manual_value("printtarg", "-i", "p3")
    tab._switch_mode("guided")
    assert tab._instr_combo.currentData() == "p3"


def test_switch_does_not_clobber_unrepresentable_paper(tab):
    """A paper only Manual offers (A3 portrait, which Guided lacks) must survive a
    round-trip through Guided — it's never 'changed' there, so it can't clobber."""
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-p", "A3")
    tab._switch_mode("guided")          # Guided can't show A3 → keeps its own
    tab._switch_mode("manual")          # …so it can't overwrite Manual's A3
    assert _manual(tab, "printtarg", "-p") == "A3"


def test_engine_panel_follows_transfer(tab, tmp_path):
    """With the ChromIQ engine ON, a Manual chart is built from the layout panel,
    not the printtarg widgets — so a Guided→Manual transfer must also push the
    instrument/paper/pages into the panel, or the generated chart ignores them
    (Knut #9)."""
    tab._settings.set("use_chromiq_layout_engine", True)
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("CM"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4R"))
    tab._pages_spin.setValue(2)
    made_in_guided(tab, tmp_path / "1")
    tab._switch_mode("manual")
    panel = tab._manual_layout_panel
    assert panel.instr.currentData() == "CM"
    assert panel.paper.currentData() == "A4R"
    assert panel.pages.value() == 2
    r = panel.get_recipe()
    assert r.instrument == "CM" and r.paper == "A4R"


def test_engine_recipe_carries_clip_suppression_and_layout(tab, tmp_path):
    """Post-Generate transfer loads the FULL engine recipe Guided used (not just
    instrument/paper) — clip-border suppression, margins, scale, edge spacers —
    so Manual reproduces the chart instead of re-adding a clip border (Knut)."""
    tab._settings.set("use_chromiq_layout_engine", True)
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData("i1"))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData("A4"))
    tab._lb_check.setChecked(True)            # disable left border → suppress clip
    made_in_guided(tab, tmp_path / "2")
    tab._switch_mode("manual")
    r = tab._manual_layout_panel.get_recipe()
    assert r.clip_border is False             # suppressed, not re-added
    assert r.clip_content_mode == "off"
    assert r.edge_spacers is True             # guided brackets strips
    # keep the left border → clip comes back on
    tab._switch_mode("guided")
    tab._lb_check.setChecked(False)
    made_in_guided(tab, tmp_path / "3")
    tab._switch_mode("manual")
    r2 = tab._manual_layout_panel.get_recipe()
    assert r2.clip_border is True
    assert r2.clip_content_mode == "notes"


def test_engine_toggle_converts_settings_both_ways(tab):
    """Flipping the Manual engine toggle converts the shared layout settings
    across the two representations, so the layout isn't lost (Knut #3)."""
    from dataclasses import replace
    tab._settings.set("use_chromiq_layout_engine", False)
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-i", "i1")
    tab._set_manual_value("printtarg", "-p", "A4")
    tab._set_manual_value("printtarg", "-m", 8)
    tab._set_manual_value("printtarg", "-a", 0.9)
    tab._set_manual_value("printtarg", "-L", False)      # clip border ON
    tab._manual_engine_check.setChecked(True)            # OFF→ON
    r = tab._manual_layout_panel.get_recipe()
    assert r.instrument == "i1" and r.paper == "A4"
    assert r.margin_top == 8.0 and r.pscale == 0.9
    assert r.clip_border is True                          # -L off → clip on
    # change the panel, toggle off → printtarg widgets follow
    tab._manual_layout_panel.set_recipe(replace(
        r, paper="A4R", margin_top=12, margin_right=12, margin_bottom=12,
        margin_left=12, clip_border=False, pscale=1.1))
    tab._manual_engine_check.setChecked(False)           # ON→OFF
    assert _manual(tab, "printtarg", "-p") == "A4R"
    assert int(_manual(tab, "printtarg", "-m")) == 12
    assert bool(_manual(tab, "printtarg", "-L")) is True  # clip off → -L on


def test_engine_to_printtarg_transfers_all_fields(tab):
    """Engine ON→OFF writes every convertible field onto the printtarg widgets
    (Knut's full transfer spec: spacers, bit depth, compression, randomise/seed,
    resolution, patch scale)."""
    from dataclasses import replace
    tab._settings.set("use_chromiq_layout_engine", False)
    tab._switch_mode("manual")
    tab._manual_engine_check.setChecked(True)                # OFF→ON inits panel
    r = tab._manual_layout_panel.get_recipe()
    tab._manual_layout_panel.set_recipe(replace(
        r, instrument="i1", paper="329x483", pscale=0.85, dpi=297, bit16=True,
        compression="none", randomize=False, seed=None, spacer_mode="bw",
        margin_top=24, margin_right=24, margin_bottom=24, margin_left=24))
    tab._manual_engine_check.setChecked(False)               # ON→OFF
    assert _manual(tab, "printtarg", "-p") == "329x483"
    assert abs(float(_manual(tab, "printtarg", "-a")) - 0.85) < 1e-6
    assert int(_manual(tab, "printtarg", "-t")) == 297
    assert bool(tab._bit16_radio.isChecked()) is True        # 16-bit
    assert bool(_manual(tab, "printtarg", "-b")) is True     # B&W spacers
    assert bool(_manual(tab, "printtarg", "-n")) is False
    assert bool(_manual(tab, "printtarg", "-C")) is True     # compression none → -C
    assert bool(_manual(tab, "printtarg", "-r")) is True     # randomise off → -r on
    assert int(_manual(tab, "printtarg", "-m")) == 24


def test_engine_toggle_preserves_distinct_margins_roundtrip(tab):
    """Distinct engine margins must survive a toggle round-trip: printtarg has a
    single margin, so collapsing 4→1→4 would lose them. They are kept unless the
    user actually changes printtarg's margin while it's shown (Knut)."""
    from dataclasses import replace
    tab._settings.set("use_chromiq_layout_engine", False)
    tab._switch_mode("manual")
    tab._manual_engine_check.setChecked(True)                # OFF→ON
    r = tab._manual_layout_panel.get_recipe()
    tab._manual_layout_panel.set_recipe(replace(
        r, margin_top=24, margin_right=9, margin_bottom=9, margin_left=26))
    tab._manual_engine_check.setChecked(False)               # ON→OFF (no collapse)
    tab._manual_engine_check.setChecked(True)                # OFF→ON again
    r2 = tab._manual_layout_panel.get_recipe()
    assert (r2.margin_top, r2.margin_right, r2.margin_bottom, r2.margin_left) \
        == (24, 9, 9, 26)                                    # distinct values kept
    # But if the user changes printtarg's -m in between, that single value wins.
    tab._manual_engine_check.setChecked(False)
    tab._set_manual_value("printtarg", "-m", 7)
    tab._manual_engine_check.setChecked(True)
    r3 = tab._manual_layout_panel.get_recipe()
    assert (r3.margin_top, r3.margin_right, r3.margin_bottom, r3.margin_left) \
        == (7, 7, 7, 7)


def test_auto_preview_is_manual_only_and_persists(tab):
    """The auto-update-preview option is Manual-only (hidden + ignored in Guided)
    and its checkbox state is remembered (Knut)."""
    tab._switch_mode("guided")
    assert not tab._auto_preview_row_w.isVisibleTo(tab)
    tab._switch_mode("manual")
    assert tab._auto_preview_row_w.isVisibleTo(tab)
    # default off; toggling persists to settings
    assert tab._auto_preview_check.isChecked() is False
    tab._settings.set("auto_update_preview", True)
    # ignored in Guided even when on: scheduling is a no-op there
    tab._switch_mode("guided")
    tab._auto_preview_timer.stop()
    tab._maybe_schedule_auto_preview()
    assert not tab._auto_preview_timer.isActive()


def test_targen_auto_options_default_on(tab):
    """All four targen-basic Auto options default ON in Manual (Knut)."""
    tab._switch_mode("manual")
    assert tab._manual_auto_patches_check.isChecked() is True
    assert tab._manual_auto_grey_check.isChecked() is True
    assert tab._manual_auto_white_check.isChecked() is True
    assert tab._manual_auto_black_check.isChecked() is True
