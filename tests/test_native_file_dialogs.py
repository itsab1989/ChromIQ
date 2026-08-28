"""The "Use the operating system's file browser" setting (Windows-speed option).

Covers both halves: the shared dialog helpers honour the preference (native →
skip the DontUseNativeDialog option + our custom sidebar/preview), and the
Settings checkbox round-trips the value.
"""
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication, QFileDialog, QLabel  # noqa: E402

import ui.widgets as widgets  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _captured_dialog(qapp, monkeypatch, native: bool):
    """Drive open_file_dialog without ever showing a modal: force the preference,
    capture the QFileDialog, and stub exec() to cancel."""
    monkeypatch.setattr(widgets, "_prefer_native_dialogs", lambda: native)
    seen = {}
    orig_exec = QFileDialog.exec

    def _fake_exec(self):
        seen["dlg"] = self
        return QFileDialog.DialogCode.Rejected.value

    monkeypatch.setattr(QFileDialog, "exec", _fake_exec)
    try:
        widgets.open_file_dialog(None, "Pick", name_filter="Images (*.tif)",
                                 preview=True)
    finally:
        monkeypatch.setattr(QFileDialog, "exec", orig_exec)
    return seen["dlg"]


def test_native_pref_skips_dontusenative_option(qapp, monkeypatch):
    dlg = _captured_dialog(qapp, monkeypatch, native=True)
    assert not (dlg.options() & QFileDialog.Option.DontUseNativeDialog)
    # No injected preview pane in native mode.
    assert dlg.findChild(QLabel, "imagePreview") is None


def test_themed_pref_injects_preview_pane(qapp, monkeypatch):
    dlg = _captured_dialog(qapp, monkeypatch, native=False)
    # Themed mode with preview=True adds our image-preview QLabel.
    assert dlg.findChild(QLabel, "imagePreview") is not None


def test_themed_pref_sets_dontusenative_option(qapp, monkeypatch):
    dlg = _captured_dialog(qapp, monkeypatch, native=False)
    assert dlg.options() & QFileDialog.Option.DontUseNativeDialog


def test_preference_reads_setting(qapp, monkeypatch, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("core.settings.AppSettings", lambda: s)
    s.set("use_native_file_dialogs", True)
    assert widgets._prefer_native_dialogs() is True
    s.set("use_native_file_dialogs", False)
    assert widgets._prefer_native_dialogs() is False


def test_settings_checkbox_round_trips(qapp, tmp_path, monkeypatch):
    import core.preset_store as ps
    from pathlib import Path
    from unittest import mock
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    with mock.patch.object(ps, "presets_dir", lambda: Path(tmp_path)):
        dlg = SettingsDialog(s, None)
        try:
            assert dlg._native_files_check.isChecked() is False   # default
            dlg._native_files_check.setChecked(True)
            dlg._save_and_close()
        finally:
            dlg.deleteLater()
    assert s.get("use_native_file_dialogs") is True


# ---------------------------------------------------------------------------
# save_file_dialog: the PARENT it is given is the parent the dialog gets.
#
# 4.1.3-beta.16 introduced `parent = p.parent` inside save_file_dialog, which
# overwrote the QWidget argument with a Path, so `QFileDialog(parent, …)`
# raised `TypeError: argument 1 has unexpected type 'PosixPath'` for every
# caller that suggests a FILE NAME rather than a folder — all twelve of them.
# Every "Save as…" in the app was dead in a shipped release and no test noticed,
# because nothing anywhere called the real function: the two tests that touch
# it (test_measurement_report, test_profile_tools) patch it out entirely.
#
# These drive the real function with exec() stubbed, so they can never block a
# gate, and they check BOTH halves: the dialog is parented to the widget, and
# the start folder still falls back the way beta.16 intended.
# ---------------------------------------------------------------------------

def _captured_save_dialog(monkeypatch, parent, start_path: str):
    """Run the real save_file_dialog with exec() stubbed to Cancel.

    `_open_up_sidebar` is stubbed out as well: it defers its work onto a
    QTimer, and with exec() never entering an event loop that callback fires
    later — after the dialog has been collected — which surfaces as a
    "wrapped C/C++ object … has been deleted" traceback attributed to whichever
    test happens to be running then. It is the sidebar's animation, not the
    parenting these tests are about.
    """
    monkeypatch.setattr(widgets, "_open_up_sidebar", lambda *a, **k: None)
    seen = {}
    orig_exec = QFileDialog.exec

    def _fake_exec(self):
        seen["dlg"] = self
        return QFileDialog.DialogCode.Rejected.value

    monkeypatch.setattr(QFileDialog, "exec", _fake_exec)
    try:
        widgets.save_file_dialog(parent, "Save", "PDF (*.pdf)",
                                 start_path=start_path)
    finally:
        monkeypatch.setattr(QFileDialog, "exec", orig_exec)
    return seen["dlg"]


@pytest.mark.parametrize("native", [True, False])
def test_save_dialog_keeps_the_widget_parent_for_a_file_path(
        qapp, monkeypatch, tmp_path, native):
    """A full path with a file name — the branch that was fatal."""
    monkeypatch.setattr(widgets, "_prefer_native_dialogs", lambda: native)
    parent = QLabel("owner")
    dlg = _captured_save_dialog(monkeypatch, parent, str(tmp_path / "card.pdf"))
    assert dlg.parent() is parent
    assert dlg.directory().absolutePath() == str(tmp_path)


def test_save_dialog_keeps_the_widget_parent_for_a_directory(
        qapp, monkeypatch, tmp_path):
    """start_path naming an existing folder — the branch that always worked."""
    monkeypatch.setattr(widgets, "_prefer_native_dialogs", lambda: False)
    parent = QLabel("owner")
    dlg = _captured_save_dialog(monkeypatch, parent, str(tmp_path))
    assert dlg.parent() is parent


def test_save_dialog_accepts_no_parent(qapp, monkeypatch, tmp_path):
    """`save_card_pdf(wf, parent=None)` is a legal call; it must not raise."""
    monkeypatch.setattr(widgets, "_prefer_native_dialogs", lambda: False)
    dlg = _captured_save_dialog(monkeypatch, None, str(tmp_path / "x.pdf"))
    assert dlg.parent() is None


def test_save_dialog_falls_back_when_the_folder_does_not_exist(
        qapp, monkeypatch, tmp_path):
    """beta.16's own point: a start folder nothing ever creates is not a start
    folder. Keep that behaviour — and keep the widget parent through it."""
    monkeypatch.setattr(widgets, "_prefer_native_dialogs", lambda: False)
    monkeypatch.setattr(widgets, "_documents_dir", lambda: str(tmp_path))
    parent = QLabel("owner")
    missing = tmp_path / "nothing-here" / "readings.csv"
    dlg = _captured_save_dialog(monkeypatch, parent, str(missing))
    assert dlg.parent() is parent
    assert dlg.directory().absolutePath() == str(tmp_path)
