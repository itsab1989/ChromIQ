"""#130 (Knut, 2026-07-27): "Replace only the chart" on the load button.

His ruling, in his words: *"(b) it is a convenience, but can also be used as a
repair tool. The user should be warned of the consequences in relation to the
measurements not matching, unless the ti1 file imported is matching the
measurements (cannot be automatically verified, thus user judgement is
needed)."*

So the option exists, it leaves the rest of the run standing, and it says
plainly what it cannot check. When the patch set brought its chart-settings file
along, those settings are applied so the sheet comes out as it was laid out —
which is what makes it usable as a repair tool at all.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager, Project   # noqa: E402
from core.settings import AppSettings                # noqa: E402
from ui.tabs.tab_chart import ti1_sidecar            # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- the sidecar ----------------------------------------------------------
def test_a_patch_set_that_brought_its_settings_is_recognised(tmp_path):
    ti1 = tmp_path / "chart.ti1"; ti1.write_text("CTI1", encoding="utf-8")
    side = tmp_path / "chart.channels.json"; side.write_text("{}", encoding="utf-8")
    assert ti1_sidecar(ti1) == side


def test_a_bare_patch_set_has_none(tmp_path):
    ti1 = tmp_path / "chart.ti1"; ti1.write_text("CTI1", encoding="utf-8")
    assert ti1_sidecar(ti1) is None


def test_nothing_at_all_is_safe():
    assert ti1_sidecar(None) is None


# ---- the option is offered ------------------------------------------------
def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _offered(tab, tmp_path, monkeypatch, src):
    """The choices the destination dialog puts in front of the user."""
    seen = {}

    def _fake(parent, title, intro, choices):
        seen["choices"] = choices
        return None                     # Cancel — we only want the offer
    monkeypatch.setattr("ui.ti2_loader._choice_dialog", _fake)
    tab._ti1_load_destination(src)
    return seen.get("choices", [])


def _project(tab, tmp_path, with_measurement=True, name="P"):
    from ui.measurement_target_bar import MeasurementTargetController
    root = tmp_path / "out"; root.mkdir(parents=True, exist_ok=True)
    proj = Project.create(root / name, name)
    run = proj.current_run(); run.ensure_dir()
    if with_measurement:
        (run.dir / f"{run.stem}.ti3").write_text("MEASUREMENT", encoding="utf-8")
    tab._file_mgr.set_target_name(name)
    ctl = MeasurementTargetController(tab._file_mgr)
    ctl.set_profile_run(run.id)
    tab.set_target_controller(ctl)
    return proj, run


def test_the_fourth_option_is_offered_when_a_run_would_be_displaced(
        qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    _project(tab, tmp_path)
    src = tmp_path / "chart.ti1"; src.write_text("CTI1", encoding="utf-8")

    keys = [c[2] for c in _offered(tab, tmp_path, monkeypatch, src)]

    assert "into_chart" in keys, keys
    assert keys.index("into_chart") > keys.index("into_replace"), \
        "the safe options come first; this one needs a deliberate choice"


def test_it_warns_that_the_match_cannot_be_checked(qapp, tmp_path, monkeypatch):
    """Knut's condition: the user must be warned, because only a person can
    judge whether the incoming patches match the measurement."""
    tab = _tab(tmp_path)
    _project(tab, tmp_path)
    src = tmp_path / "chart.ti1"; src.write_text("CTI1", encoding="utf-8")

    desc = dict((c[2], c[1]) for c in
                _offered(tab, tmp_path, monkeypatch, src))["into_chart"]

    assert "cannot" in desc and "check" in desc
    assert "measurement" in desc
    assert "old/" in desc, "say what does NOT happen, too"


def test_the_text_says_whether_the_settings_file_came_with_it(
        qapp, tmp_path, monkeypatch):
    """With the file, the sheet is laid out exactly as it was; without it, only
    the patches are replaced — a real difference, so it is stated."""
    tab = _tab(tmp_path)
    _project(tab, tmp_path)

    bare = tmp_path / "bare.ti1"; bare.write_text("CTI1", encoding="utf-8")
    d1 = dict((c[2], c[1]) for c in
              _offered(tab, tmp_path, monkeypatch, bare))["into_chart"]
    assert "No chart settings file" in d1

    full = tmp_path / "full.ti1"; full.write_text("CTI1", encoding="utf-8")
    (tmp_path / "full.channels.json").write_text("{}", encoding="utf-8")
    d2 = dict((c[2], c[1]) for c in
              _offered(tab, tmp_path, monkeypatch, full))["into_chart"]
    assert "found beside it" in d2


# ---- what it actually does ------------------------------------------------
def test_it_keeps_the_run_and_the_other_options_do_not():
    """The one line that separates this option from Replace."""
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_load_ti1)
    assert 'chart_only = dest == "into_chart"' in src
    assert "keep_results=chart_only" in src
    # Replace still archives; the new option must not reach that call.
    assert "_archive_run_for_replace()" in src
    assert src.index("_archive_run_for_replace()") < src.index("chart_only =")


def test_the_settings_file_is_applied_when_there_is_one():
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_load_ti1)
    assert "_apply_loaded_chart_settings(sidecar)" in src


def test_applying_the_settings_restores_the_seed(qapp, tmp_path):
    """The reason it can serve as a repair tool: same recipe, same seed, same
    sheet — see tests/test_restored_chart_is_the_same_chart.py."""
    tab = _tab(tmp_path)
    side = tmp_path / "c.channels.json"
    side.write_text(json.dumps({"layout": {
        "engine": "chromiq", "seed": 314159,
        "recipe": {"instrument": "CM", "paper": "A4", "randomize": True,
                   "seed": None, "patch_w_mm": 8.0, "patch_h_mm": 8.0},
    }}), encoding="utf-8")

    assert tab._apply_loaded_chart_settings(side) is True
    assert tab._manual_layout_panel.get_recipe().seed == 314159


def test_a_damaged_settings_file_does_not_block_the_load(qapp, tmp_path):
    tab = _tab(tmp_path)
    side = tmp_path / "c.channels.json"
    side.write_text("{ not json", encoding="utf-8")
    assert tab._apply_loaded_chart_settings(side) is False


def test_a_run_with_nothing_in_it_is_not_offered_the_choice(
        qapp, tmp_path, monkeypatch):
    """Nothing to preserve, so the question does not arise — the plain
    add-to-project dialog is shown instead."""
    tab = _tab(tmp_path)
    _project(tab, tmp_path, with_measurement=False, name="Q")
    tab._target_ctl.set_profile_run("")   # New run — nothing exists yet
    src = tmp_path / "chart.ti1"; src.write_text("CTI1", encoding="utf-8")

    keys = [c[2] for c in _offered(tab, tmp_path, monkeypatch, src)]

    assert "into_chart" not in keys, keys
