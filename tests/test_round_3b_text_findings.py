"""Round 3B (user-facing text and the demo pack, on screen in EN and DE),
2026-09-23: the behaviour behind two of its tooltip findings, pinned. The
wording findings (F3, F7, F15-F17) are text and are held by the i18n guards;
F5 is in `test_a_verification_report_says_what_it_judges.py`.

F9  the no-run tooltip on Generate replaced the several-places one when a
    profile run was loaded beside the loose file, and said removing entries
    could not help, when removing the loose entry is exactly what does;
F11 after Clear List the limit controls still spoke of "this measurement".
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _loose_window(tmp_path):
    from tests.test_report_window_limit_controls import (_colours, _dialog,
                                                         _ramp, _settings,
                                                         _write_ti3)
    dl = tmp_path / "Downloads"
    dl.mkdir()
    ti3 = _write_ti3(dl / "x.ti3", _ramp(16) + _colours())
    return _dialog(_settings(tmp_path), ti3)


def test_a_loose_file_beside_a_run_gives_the_several_places_reason(tmp_path,
                                                                   qapp):
    """F9. MUTATION: drop `and not several` and Generate says "not part of a
    profile run" with a run loaded beside it: red."""
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    _s, _fm, _ctl, run = _verify_env(tmp_path / "proj")
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = _loose_window(tmp_path)
    try:
        dlg._add_source(v.measurement_ti3)
        qapp.processEvents()
        assert dlg._several_runs(), "the fixture did not load two places"
        tip = dlg._generate_btn.toolTip()
        assert "more than one place" in tip, tip
        assert "not part of a profile run" not in tip, tip
    finally:
        dlg.deleteLater()


def test_with_nothing_loaded_the_limit_controls_say_so(tmp_path, qapp):
    """F11. MUTATION: drop the `not self._sources` branch and the tooltip
    speaks of "this measurement" over an empty window: red."""
    dlg = _loose_window(tmp_path)
    try:
        dlg._on_clear_list()
        qapp.processEvents()
        tips = {dlg._set_combo.toolTip(), dlg._limits_btn.toolTip()}
        assert any("No measurement is loaded yet." in t for t in tips), tips
        assert not any("This measurement" in t for t in tips), tips
    finally:
        dlg.deleteLater()
