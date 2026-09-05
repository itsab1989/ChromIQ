"""UI-side fixes from the Maximum-accuracy challenge (Agent B, 2026-09-05).

* B-18: the four engine-only Manual rows (and the black-generation rows)
  leaked from one run into a fresh run — ``_restore_defaults`` never reset
  them, so the previous run's values were written into the new run's
  ``meta.json`` as if chosen.
* B-06: the progress-bar label named the builder but never the mode; Guided
  has no engine rows, so nothing told a Guided user that "Maximum accuracy"
  built the profile.
* B-09/B-20: a plain rebuild into the same run overwrote the previous
  profile (and its v4 twin) in place, no ``old/``, no line in the log.
* B-26: the scanner/camera tool's printer-profile build ignored Preferences
  → Beta and always ran colprof; it now asks the same chooser the tab does.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.engine_builder import accuracy_mode_label, choose_builder
from workflow.profile_builder import ProfileParams


def _tab(tmp_path, **prefs):
    from tests.test_engine_v2_options import _tab as make
    return make(tmp_path, **prefs)


def test_restore_defaults_resets_the_engine_and_black_generation_rows(tmp_path, qtbot):
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    tab._m_spectral_cb.setChecked(True)
    tab._m_iccver_combo.setCurrentIndex(tab._m_iccver_combo.findData("both"))
    tab._m_noise_cb.setChecked(True)
    tab._m_render_combo.setCurrentIndex(tab._m_render_combo.findData("bijective"))
    tab._m_kgen_combo.setCurrentIndex(tab._m_kgen_combo.findData("p"))
    tab._m_kgen_spins["stpo"].setValue(0.4)
    tab._restore_defaults()
    assert tab._m_spectral_cb.isChecked() is False
    assert tab._m_iccver_combo.currentData() == "2"
    assert tab._m_noise_cb.isChecked() is False
    assert tab._m_render_combo.currentData() == "argyll"
    assert (tab._m_kgen_combo.currentData() or "") == ""
    assert tab._m_kgen_spins["stpo"].value() == pytest.approx(0.1)


def test_accuracy_mode_label_names_every_mode():
    assert accuracy_mode_label("accurate") == "Maximum accuracy"
    assert accuracy_mode_label("argyll") == "Bit-exact"
    assert accuracy_mode_label("fast") == "Fast"
    assert accuracy_mode_label("") == "Fast"


def test_engine_rows_have_their_own_heading(tmp_path, qtbot):
    from PyQt6.QtWidgets import QLabel
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    heads = [w for w in tab._m_engine_rows_widget.findChildren(QLabel)
             if w.objectName() == "engine_rows_heading"]
    assert heads and "Maximum accuracy" in heads[0].text()


def _rgb_ti3(path: Path) -> Path:
    from tests.test_profile_engine import write_synth_ti3
    return write_synth_ti3(path, "iRGB", ["RGB_R", "RGB_G", "RGB_B"], True)


def test_choose_builder_follows_the_beta_switch(tmp_path):
    ti3 = _rgb_ti3(tmp_path / "s.ti3")
    params = ProfileParams(ti3_path=ti3)

    class S(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    assert choose_builder(S(), params) == ("colprof", "")
    assert choose_builder(S(profile_engine_beta=True, gammap_mode="fast"),
                          params) == ("engine", "")
    assert choose_builder(S(profile_engine_beta=True, gammap_mode="accurate"),
                          params) == ("engine", "")
    which, why = choose_builder(S(profile_engine_beta=True,
                                  gammap_mode="argyll"), params)
    assert which == "colprof" and "colprof itself" in why
    which, why = choose_builder(S(profile_engine_beta=True, gammap_mode="accurate"),
                                ProfileParams(ti3_path=ti3, extra_args="-g x.gam"))
    assert which == "colprof" and "-g" in why


def test_scanner_tool_builds_the_printer_profile_with_the_chosen_builder(tmp_path):
    """The dialog hands back an EngineProfileBuilder when Preferences say
    engine, and its colprof builder otherwise — behaviour, not source text
    (reviewer R18: the text assertion passed with the chooser forced to
    colprof)."""
    from ui.dialogs import scanin_dialog
    from workflow.engine_builder import EngineProfileBuilder

    class S(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

    class Log:
        def __init__(self):
            self.lines = []

        def appendPlainText(self, t):
            self.lines.append(t)

    class Stand:                      # the method only reads these three
        pass

    dlg = Stand()
    dlg._profiler = object()
    dlg._log = Log()
    choose = scanin_dialog.ScannerProfileDialog._printer_profile_builder
    params = ProfileParams(ti3_path=_rgb_ti3(tmp_path / "s.ti3"))
    dlg._settings = S()
    assert choose(dlg, params) is dlg._profiler
    dlg._settings = S(profile_engine_beta=True, gammap_mode="accurate")
    b = choose(dlg, params)
    assert isinstance(b, EngineProfileBuilder) and dlg._engine_profiler is b
    dlg._settings = S(profile_engine_beta=True, gammap_mode="argyll")
    assert choose(dlg, params) is dlg._profiler
    assert any("Building with Argyll colprof" in ln for ln in dlg._log.lines)
    # The sanitiser still runs before any builder sees the file.
    import inspect
    build_src = inspect.getsource(scanin_dialog.ScannerProfileDialog._build_printer_profile)
    assert build_src.index("_sanitize_scanner_ti3") < build_src.index(
        "_printer_profile_builder(params)")


def test_rebuild_archives_the_previous_profile_and_its_twin(tmp_path, qtbot):
    from core.file_manager import Project
    tab = _tab(tmp_path, profile_engine_beta=True, gammap_mode="accurate")
    qtbot.addWidget(tab)
    root = Path(tab._settings.get("custom_output_path")) / "Arch"
    proj = Project.create(root, "Arch")
    run = proj.current_run()
    ti3 = _rgb_ti3(run.measurement_ti3)
    icc = ti3.with_suffix(".icc")
    twin = icc.with_name(icc.stem + "-v4.icc")
    icc.write_bytes(b"old profile bytes " * 100)
    twin.write_bytes(b"old twin bytes " * 100)
    tab._settings.set("target_name", "Arch")
    tab.set_ti3_path(ti3, propagate=False)
    tab._archive_previous_build(ProfileParams(ti3_path=ti3))
    assert not icc.exists() and not twin.exists()
    old = run.dir / "old"
    moved = sorted(p.name for p in old.rglob("*.icc"))
    assert moved == ["Arch-v4.icc", "Arch.icc"], moved
    assert "The previous profile was moved to" in tab._log.toPlainText()
    # A build that fails puts them back (reviewer R14: a failed rebuild used
    # to leave the run with NO profile).
    tab._restore_archived_build()
    assert icc.exists() and twin.exists()
    assert not list(old.rglob("*.icc"))
    assert "put back" in tab._log.toPlainText()
    # …and only once: a second call is a no-op.
    tab._restore_archived_build()
    assert icc.exists()


def test_quit_guard_sees_every_engine_builder():
    from workflow.engine_builder import EngineProfileBuilder

    class Fake(EngineProfileBuilder):
        def __init__(self, running):
            self._running = running
            self._thread = None
            self._last_error = ""
            self._app_settings = None

        @property
        def is_running(self):
            return self._running

    EngineProfileBuilder._RUNNING.clear()
    assert not EngineProfileBuilder.any_running()
    b = Fake(True)
    EngineProfileBuilder._RUNNING.add(b)
    assert EngineProfileBuilder.any_running()
    b._running = False
    assert not EngineProfileBuilder.any_running()
    EngineProfileBuilder._RUNNING.discard(b)
