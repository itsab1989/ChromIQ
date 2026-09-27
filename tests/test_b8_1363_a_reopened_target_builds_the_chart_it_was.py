"""B8-1363: a target reopened after a restart builds the chart it was built as.

Round 9 of the beta 44 challenge (on screen): build with "Auto patch count"
ticked, restart, reopen the target, Generate. The i1Pro built 528 patches and
then 22; with the layout engine 525 and then 16 while the estimate said 525.
The tick was not stored per target (§1.2 of per_target_settings.md says it
is), the rows record -f as 0 while it is ticked, and the reopen left the box
off with -f 0: the fixed patches alone.

And a built-in preset (a bundled .ti1, targen skipped) reopened without its
patch set: Generate ran targen from the rows on screen and made ANOTHER 600
patches. The chart's sidecar now says whether its patch set was given.
"""
import json

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs import tab_chart as TC  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path, **prefs):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path / "out"))
    for k, v in prefs.items():
        s.set(k, v)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._manual_btn.setChecked(True)
    return tab


def _f(tab):
    return int(tab._manual_f_pw.get_raw_value())


def _auto(tab):
    return tab._manual_auto_patches_check.isChecked()


def _chart(tmp_path, sets, doc):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(f"CTI2\nNUMBER_OF_SETS {sets}\nBEGIN_DATA\nEND_DATA\n",
                   encoding="utf-8")
    (tmp_path / "c.channels.json").write_text(json.dumps(doc),
                                              encoding="utf-8")
    return ti2


def _reg(f):
    return {"targen-f": {"enabled": True, "value": f}}


# ---- the store ------------------------------------------------------------

def test_the_target_record_carries_the_tick(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    assert tab._collect_ui_state()["auto"] == {"patches": True}
    tab._manual_auto_patches_check.setChecked(False)
    assert tab._collect_ui_state()["auto"] == {"patches": False}
    tab.deleteLater()


@pytest.mark.parametrize("stored", [True, False])
def test_loading_the_record_puts_the_tick_back(qapp, tmp_path, stored):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(not stored)
    tab._apply_ui_state({"auto": {"patches": stored}})
    assert _auto(tab) is stored
    # -f follows the tick: greyed "Auto" (0) with it on, live with it off
    assert tab._manual_f_pw._control.isEnabled() is (not stored)
    tab.deleteLater()


@pytest.mark.parametrize("saved", [True, False])
def test_a_record_without_the_tick_opens_on_the_saved_default(qapp, tmp_path,
                                                              saved):
    """§4 S4: absent means neutral, never the previous run's tick."""
    tab = _tab(tmp_path, manual_auto_patches=saved)
    tab._manual_auto_patches_check.setChecked(not saved)
    tab._apply_ui_state({})
    assert _auto(tab) is saved
    tab.deleteLater()


@pytest.mark.parametrize("on", [True, False])
def test_a_partial_record_says_nothing_about_the_box(qapp, tmp_path, on):
    """Only an EMPTY record (nothing stored) opens on the default; a record
    that predates the tick is given one from its -f by the target load."""
    tab = _tab(tmp_path, manual_auto_patches=not on)
    tab._manual_auto_patches_check.setChecked(on)
    tab._apply_ui_state({"stamp": True})
    assert _auto(tab) is on
    tab.deleteLater()


def test_calibration_keeps_the_box_off(qapp, tmp_path):
    """Run type = Calibration holds the box off and disabled; a load does
    not tick it (its knobs run before the load and put it back after)."""
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    tab._apply_calibration_knobs(True)
    tab._apply_ui_state({"auto": {"patches": True}})
    assert _auto(tab) is False
    tab._apply_calibration_knobs(False)
    assert _auto(tab) is True
    tab.deleteLater()


@pytest.mark.parametrize("reg, ui, want", [
    (_reg(0), {}, True),                     # stored before B8-1363, Auto on
    (_reg(300), {}, False),                  # a typed count
    (_reg(0), {"auto": {"patches": False}}, False),   # its own tick wins
    ({}, {}, None),                          # nothing to read it from
])
def test_an_older_record_is_read_from_its_count(reg, ui, want):
    out = TC._with_auto_patches_derived(ui, reg)
    assert (out.get("auto") or {}).get("patches") is want


class _Meta:
    def __init__(self, reg, ui):
        self.create_chart_settings = reg
        self.create_chart_ui = ui


class _Store:
    def __init__(self, tmp_path, reg, ui):
        self.dir = tmp_path
        self._meta = _Meta(reg, ui)

    def load_meta(self):
        return self._meta


def test_the_target_load_puts_auto_back_for_an_older_record(qapp, tmp_path):
    """The load that clobbered the chart's pin: the store held -f 0 and no
    tick, the screen had the box off, so -f 0 with Auto off was built."""
    tab = _tab(tmp_path)
    reg = TC_snapshot_with_f(tab, 0)
    tab._manual_auto_patches_check.setChecked(False)
    tab._target_settings_store = lambda: _Store(tmp_path, reg, {"mode": "manual"})
    assert tab.load_target_settings() is True
    assert _auto(tab) is True
    tab.deleteLater()


def TC_snapshot_with_f(tab, f):
    from workflow.per_target_settings import snapshot
    reg = snapshot(tab)
    reg["targen-f"] = {"enabled": True, "value": f}
    return reg


# ---- the chart ------------------------------------------------------------

def test_a_chart_built_with_auto_reopens_with_auto(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(False)
    ti2 = _chart(tmp_path, 528, {"auto_patches": True,
                                 "create_chart_settings": _reg(0)})
    tab._restore_chart_settings(ti2)
    assert _auto(tab) is True
    assert _f(tab) == 0          # not pinned to 528, and not -f 0 with it off
    tab.deleteLater()


def test_a_typed_count_comes_back_as_typed_not_as_the_padded_total(
        qapp, tmp_path):
    """printtarg pads to whole strips: 300 typed can be 308 on the sheet, and
    targen -f308 is another patch set."""
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti2 = _chart(tmp_path, 308, {"auto_patches": False,
                                 "create_chart_settings": _reg(300)})
    tab._restore_chart_settings(ti2)
    assert _auto(tab) is False
    assert _f(tab) == 300
    tab.deleteLater()


def test_an_older_chart_is_read_from_its_count(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(False)
    ti2 = _chart(tmp_path, 528, {"create_chart_settings": _reg(0)})
    tab._restore_chart_settings(ti2)
    assert _auto(tab) is True
    tab.deleteLater()


def test_a_chart_that_cannot_say_is_pinned_as_before(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti2 = _chart(tmp_path, 546, {"chart_notes": "x"})
    tab._restore_chart_settings(ti2)
    assert _auto(tab) is False and _f(tab) == 546
    tab.deleteLater()


def test_the_sidecar_records_the_tick_and_a_given_patch_set(tmp_path):
    from workflow.chart_creator import ChartCreator, ChartParams

    class _S:
        def get(self, key, default=None):
            return default

    cc = ChartCreator(None, None, _S())
    cc._write_channel_sidecar(tmp_path, "a", ChartParams(
        auto_patches=True, patch_set_given=True))
    doc = json.loads((tmp_path / "a.channels.json").read_text(encoding="utf-8"))
    assert doc["auto_patches"] is True and doc["patch_set_given"] is True
    cc._write_channel_sidecar(tmp_path, "b", ChartParams())
    doc = json.loads((tmp_path / "b.channels.json").read_text(encoding="utf-8"))
    assert "auto_patches" not in doc and "patch_set_given" not in doc


def test_generate_collects_the_tick(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    assert tab._collect_params().auto_patches is True
    tab._manual_auto_patches_check.setChecked(False)
    assert tab._collect_params().auto_patches is False
    tab.deleteLater()


@pytest.mark.parametrize("given, bound", [(True, True), (False, False)])
def test_a_given_patch_set_is_bound_again_although_targen_wrote_it(
        qapp, tmp_path, given, bound):
    tab = _tab(tmp_path)
    ti1 = tmp_path / "c.ti1"
    ti1.write_text('CTI1\nORIGINATOR "Argyll targen"\nNUMBER_OF_SETS 600\n',
                   encoding="utf-8")
    tab._preset_ti1_path = None
    tab._rebind_patch_set_from_run(ti1, given=given)
    assert (tab._preset_ti1_path == ti1) is bound
    tab.deleteLater()


def test_an_older_chart_on_a_bundled_targen_set_is_bound_by_its_file(
        qapp, tmp_path):
    """Red River's locked 2052-patch set says "Argyll targen"; a chart built
    from it before the sidecar recorded `patch_set_given` is recognised by
    its bytes, and an edited copy is not."""
    import shutil
    from core.resource_path import resource_path
    src = resource_path(
        "assets/charts/redriver/rgb/standard_patch_set_v25/chart.ti1")
    ti1 = tmp_path / "run.ti1"
    shutil.copy2(src, ti1)
    assert TC._is_a_bundled_targen_patch_set(ti1)
    tab = _tab(tmp_path)
    tab._preset_ti1_path = None
    tab._rebind_patch_set_from_run(ti1, given=False)
    assert tab._preset_ti1_path == ti1
    ti1.write_bytes(ti1.read_bytes() + b"\n")
    assert not TC._is_a_bundled_targen_patch_set(ti1)
    tab.deleteLater()


def test_the_restore_reads_whether_the_patch_set_was_given(qapp, tmp_path):
    tab = _tab(tmp_path)
    ti2 = _chart(tmp_path, 600, {"patch_set_given": True,
                                 "auto_patches": False,
                                 "create_chart_settings": _reg(600)})
    tab._restore_chart_settings(ti2)
    assert tab._restored_patch_set_given is True
    ti2 = _chart(tmp_path, 600, {"create_chart_settings": _reg(600)})
    tab._restore_chart_settings(ti2)
    assert tab._restored_patch_set_given is False
    tab.deleteLater()


# ---- the layout the target stored -----------------------------------------

def test_restoring_the_stored_module_does_not_push_minus_p_into_the_panel(
        qapp, tmp_path):
    """The built-in preset's 100 x 150 came back on A4 after a restart: the
    target's stored module (Manual) was put back through `_switch_mode`,
    whose Guided-to-Manual carry pushed -p (A4) into the layout panel over
    the recipe the same load had just set."""
    from workflow.layout_engine.presets import LayoutRecipe
    tab = _tab(tmp_path, use_chromiq_layout_engine=True)
    tab._switch_mode("guided")
    rec = LayoutRecipe(instrument="i1", paper="100x150", dpi=200).to_dict()
    tab._apply_ui_state({"mode": "manual", "engine_on": True,
                         "engine_recipe": rec,
                         "guided": {"instrument": "i1", "paper": "A4"}})
    assert tab._mode_name() == "manual"
    assert tab._manual_layout_panel.get_recipe().paper == "100x150"
    tab.deleteLater()


def test_a_person_crossing_over_still_carries_the_paper(qapp, tmp_path):
    """Control: the carry itself is untouched for a real module change."""
    tab = _tab(tmp_path)
    tab._switch_mode("guided")
    i = tab._paper_combo.findData("Letter")
    assert i >= 0
    tab._paper_combo.setCurrentIndex(i)
    tab._user_switch_mode("manual")
    assert tab._manual_get("printtarg", "-p", None) == "Letter"
    tab.deleteLater()


def test_both_patch_set_routes_say_the_set_was_given():
    """`_generate_from_ti1` (built-ins, presets with a .ti1, the live
    preview of such a chart) and the loaded patch set record it."""
    import inspect
    src = inspect.getsource(TabChart._generate_from_ti1)
    assert ("params.patch_set_given = (not preview) or "
            "self._ti1_preset_active()") in src
    src = inspect.getsource(TabChart)
    assert "params.patch_set_given = True       # a loaded patch set" in src
