"""K2 (Basti, 2026-10-21): "X.icm" and "X.icc" are ONE profile name.

Installing X.icc while X.icm is installed (or the other way round) asks
through the same window as a same-extension clash (M-PROFILE-INSTALL-REPLACE),
and Replace leaves ONE profile of that name: the new file is written and the
other one removed. Cancel changes nothing.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                 # noqa: E402

from workflow import profile_builder as PB              # noqa: E402

REPO = Path(__file__).resolve().parent.parent
V2 = REPO / "demo-projects" / "Demo-Report-Matrix" / "runs" / "run1" / \
    "Demo-Report-Matrix.icc"


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def installed(tmp_path, monkeypatch):
    d = tmp_path / "ColorSync-sandbox"
    d.mkdir()
    monkeypatch.setattr(PB, "_profile_dir", lambda: d)
    return d


def _answer(monkeypatch, which, name=None):
    from ui import install_profile as IP
    cls = IP._install_name_dialog_class()
    shown = []

    def _exec(dlg):
        if name is not None:
            dlg.name_edit.setText(name)
        shown.append((dlg.ok_btn.text(), dlg.note.text()))
        (dlg.cancel_btn if which == "Cancel" else dlg.ok_btn).click()
        return 0
    monkeypatch.setattr(cls, "exec", _exec)
    return shown


NOTE = ("The profile installed under this name is {other}. Replace removes it "
        "and installs this profile as {name} instead, so only one profile of "
        "this name stays installed.")


@pytest.mark.parametrize("have,new", [("icm", "icc"), ("icc", "icm")])
def test_the_other_extension_asks_and_replace_leaves_one(
        qapp, tmp_path, installed, monkeypatch, have, new):
    from ui.install_profile import ask_install_path
    (installed / f"Knut Baryta.{have}").write_bytes(b"old")
    src = tmp_path / f"Knut Baryta.{new}"
    shutil.copy2(V2, src)
    shown = _answer(monkeypatch, "Replace")
    planned = PB.install_destination(src, None)
    chosen = ask_install_path(None, planned)
    assert chosen == installed / f"Knut Baryta.{new}"
    assert shown == [("Replace", NOTE.format(other=f"Knut Baryta.{have}",
                                             name=f"Knut Baryta.{new}"))]
    PB.install_profile_file(src, None, dest_name=chosen.name)
    assert sorted(p.name for p in installed.iterdir()) == [f"Knut Baryta.{new}"]
    assert (installed / f"Knut Baryta.{new}").read_bytes() == V2.read_bytes()


def test_cancel_changes_nothing(qapp, tmp_path, installed, monkeypatch):
    from ui.install_profile import ask_install_path
    (installed / "P.icm").write_bytes(b"old")
    shown = _answer(monkeypatch, "Cancel")
    assert ask_install_path(None, installed / "P.icc") is None
    assert len(shown) == 1
    assert [p.name for p in installed.iterdir()] == ["P.icm"]


def test_case_does_not_tell_the_names_apart(qapp, installed, monkeypatch):
    from ui.install_profile import ask_install_path
    (installed / "profile.ICM").write_bytes(b"old")
    shown = _answer(monkeypatch, "Replace")
    assert ask_install_path(None, installed / "Profile.icc") == installed / "Profile.icc"
    assert shown and "profile.ICM" in shown[0][1]


def test_a_typed_name_installed_with_the_other_extension_says_so(
        qapp, installed, monkeypatch):
    from ui.install_profile import ask_install_path
    (installed / "P.icc").write_bytes(b"old")
    (installed / "Other.icm").write_bytes(b"other")
    shown = _answer(monkeypatch, "Replace", name="Other")
    assert ask_install_path(None, installed / "P.icc") == installed / "Other.icc"
    assert shown[0] == ("Replace", NOTE.format(other="Other.icm", name="Other.icc"))


def test_no_twin_no_window_and_nothing_else_removed(qapp, tmp_path, installed,
                                                    monkeypatch):
    from ui.install_profile import ask_install_path
    for n in ("P2.icm", "P.icc.bak", "P.txt", "Q.icm"):
        (installed / n).write_bytes(b"x")
    shown = _answer(monkeypatch, "Cancel")
    assert ask_install_path(None, installed / "P.icc") == installed / "P.icc"
    assert shown == []
    src = tmp_path / "P.icc"
    shutil.copy2(V2, src)
    PB.install_profile_file(src, None)
    assert sorted(p.name for p in installed.iterdir()) == [
        "P.icc", "P.icc.bak", "P.txt", "P2.icm", "Q.icm"]


def test_the_installed_file_itself_is_never_a_twin(installed):
    f = installed / "Profile.icc"
    f.write_bytes(b"x")
    assert PB.installed_twins(f) == []
    assert PB.remove_installed_twins(f) == []
    assert f.exists()


def test_a_twin_that_cannot_be_removed_never_fails_the_install(
        tmp_path, installed, monkeypatch):
    (installed / "P.icm").write_bytes(b"old")
    src = tmp_path / "P.icc"
    shutil.copy2(V2, src)
    real = Path.unlink

    def _refuse(self, *a, **k):
        if self.name == "P.icm":
            raise PermissionError("in use")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "unlink", _refuse)
    assert PB.install_profile_file(src, None) == installed / "P.icc"
    assert (installed / "P.icc").exists() and (installed / "P.icm").exists()


def test_the_scanner_window_removes_the_twin_too():
    import inspect
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._install_profile)
    assert "remove_installed_twins(dest)" in src
