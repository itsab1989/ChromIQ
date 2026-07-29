"""#130 (2026-07-29): the release-tidying batch.

Sebastian: *"for whatever reason the latest 'stable' release currently is 'Beta-
period user-text audit — all 640 new strings'. How did that happen?"* — every
non-code helper release I published was created without the pre-release flag, so
GitHub handed the Latest badge to the newest of them instead of to v3.14.7. That
is fixed on GitHub itself; nothing in the code decides it.

Knut, two things to fix before release:

1. *"Every time I start the app it lands on Measure tab, which is always empty.
   This happens even if I quit the application in Create Chart tab… When
   starting fresh, it should always start in first tab."*
2. *"the frame 'profile verification' with the checkbox 'verification
   measurement (color-managed print)' is an obsolete function after we made the
   change to a unified file handling system… this frame, the checkbox, and the
   information icon can be removed totally from the code."*
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                      # noqa: E402
from PyQt6.QtWidgets import QApplication                # noqa: E402

from core.settings import DEFAULTS, SETTINGS_SCHEMA, AppSettings   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    """Widgets need one. Building a QWidget without it segfaults outright."""
    return QApplication.instance() or QApplication([])


# ---- 1. the tab a fresh start lands on ----------------------------------
def test_a_fresh_install_starts_on_the_first_tab():
    assert DEFAULTS["restore_last_tab"] is False


def test_the_default_change_reaches_people_who_have_saved_settings(tmp_path):
    """Preferences → Save writes every key, so a stored True is usually just an
    echo of the old default."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("restore_last_tab", True)

    s.migrate()

    assert s._qs.value("restore_last_tab", None) is None
    assert s.get("restore_last_tab") is False


def test_an_explicit_off_is_left_alone(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("restore_last_tab", False)
    s.migrate()
    assert s._qs.value("restore_last_tab", None) is not None


def test_the_schema_was_bumped():
    assert SETTINGS_SCHEMA >= 16, "a changed default needs its own schema step"


def test_the_setting_is_still_offered():
    """The feature is not removed — only its default changed. Anyone who wants
    ChromIQ to reopen where they left off ticks the box."""
    import ui.dialogs.settings_dialog as sd
    assert "restore_last_tab" in inspect.getsource(sd)


# ---- the reason it never worked: settings were never flushed -------------
def test_settings_can_be_flushed_to_disk(tmp_path):
    """ChromIQ leaves via os._exit, which skips the flush QSettings does when it
    is destroyed. Anything written in closeEvent could simply never land — which
    is why the app always reopened on whichever tab happened to be saved once."""
    path = tmp_path / "s.ini"
    s = AppSettings()
    s._qs = QSettings(str(path), QSettings.Format.IniFormat)
    s.set("active_tab", 4)
    s.sync()
    assert QSettings(str(path), QSettings.Format.IniFormat).value("active_tab") is not None


def test_the_window_flushes_on_close():
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.closeEvent)
    assert "self._settings.sync()" in src
    assert src.index('self._settings.set("active_tab"') < src.index("self._settings.sync()"), \
        "the flush must come after the writes"


def test_flushing_never_blocks_the_app_closing():
    assert "except Exception" in inspect.getsource(AppSettings.sync)


# ---- 2. the obsolete Profile verification frame is gone -----------------
def test_the_checkbox_and_its_frame_are_gone():
    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tm)
    for gone in ("_verify_cb", "_m_verify_cb", "_VERIFY_TIP_TITLE",
                 "_VERIFY_TIP_BODY", "_uncheck_verification"):
        assert gone not in src, f"{gone} is still in the Measure tab"


def test_the_run_type_is_now_the_only_switch():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._is_verification_run)
    assert "ctl.target.is_verification()" in src
    assert "isChecked" not in src


def test_a_verification_read_is_still_recognised(qapp, tmp_path):
    """Removing the checkbox must not remove the feature: a run whose Run type
    is Verification still reads as one."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    tab = TabMeasure(ArgyllRunner(s), s)
    assert tab._is_verification_run() is False      # no controller yet

    fm = FileManager(s)
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    tab.set_target_controller(ctl)
    assert tab._is_verification_run() is False
    ctl.set_run_type("verification")
    assert tab._is_verification_run() is True


def test_an_old_preset_carrying_the_dead_key_still_loads():
    """Presets saved before the removal carry "verify"; loading one must not
    raise looking for a widget that no longer exists."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert '"verify":     self._m_verify_cb.isChecked()' not in src
    assert 'data.get("verify"' not in src


def test_the_verification_completion_path_survives():
    """Only the duplicate control went. A verification read still gets its own
    completion window and its own file handling."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert "_finalize_verification" in src
    assert "Verification Measurement — All Strips Read" in src
