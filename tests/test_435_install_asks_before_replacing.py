"""Installing a profile over one of the same file name, and renaming a profile
after it was built (#182, Knut 6102031563, answer 3).

    "Yes. Ask if user wants to replace existing or cancel to rename the
    profile before trying to install it again. Giving a new name to the
    profile, after a profile is built, should still rename that profile file
    name (and the profile description field inside the ICC profile (if
    selected the option that the description is same as file name), when
    clicking the install button."

* Every Install button asks ``ui.install_profile.ask_install_path`` with the
  file it would write, before writing it: Build Profile, Apply Calibration,
  Check & Refine's "Install Profile As Is" and the scanner window.
* The window is Basti's design (2026-10-11, M-PROFILE-INSTALL-REPLACE
  approved): an editable name, Replace while it is unchanged, Install once
  it is edited (Replace again when that name is installed too), Cancel
  installs nothing. Only the installed copy takes the new name.
* With "Name the installed copy after the description" ticked, the copy is
  named after the description as it reads when Install is clicked, and its
  ``desc`` tag says the same; the project's own file is never touched.
"""
from __future__ import annotations

import dataclasses
import inspect
import os
import shutil
import struct
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                       # noqa: E402
from PyQt6.QtWidgets import QApplication                 # noqa: E402

from workflow import measurement_messages as M          # noqa: E402
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
    monkeypatch.setattr(PB, "_profile_dir", lambda: d)
    return d



def _answer(monkeypatch, which, name=None):
    """Answer the install window: optionally type *name* into its field,
    then press *which* ("Replace" / "Install" / "Cancel"). Returns what each
    window showed before the press: (button text, note, button enabled)."""
    from ui import install_profile as IP
    cls = IP._install_name_dialog_class()
    shown = []

    def _exec(dlg):
        if name is not None:
            dlg.name_edit.setText(name)
        shown.append((dlg.ok_btn.text(), dlg.note.text(), dlg.ok_btn.isEnabled()))
        if which == "Cancel":
            dlg.cancel_btn.click()
        else:
            assert dlg.ok_btn.text() == which, dlg.ok_btn.text()
            dlg.ok_btn.click()
        return 0
    monkeypatch.setattr(cls, "exec", _exec)
    return shown


def _desc(path: Path) -> str:
    from workflow.icc_info import read_icc
    return read_icc(path).description


# ---- the window (Basti's design, 2026-10-11) ----------------------------------

def test_the_window_is_approved_in_basti_s_words():
    msg = M.CATALOGUE["M-PROFILE-INSTALL-REPLACE"]
    assert msg.approved
    title, body = msg.render()
    assert title == "A profile with this name is already installed"
    assert body == ("Keep the name to replace the installed profile, or give "
                    "this profile another name.")


def test_nothing_installed_nothing_asked(qapp, tmp_path, monkeypatch):
    from ui.install_profile import ask_install_path
    shown = _answer(monkeypatch, "Cancel")
    dest = tmp_path / "P.icc"
    assert ask_install_path(None, dest) == dest
    assert shown == []


def test_keeping_the_name_replaces(qapp, tmp_path, monkeypatch):
    from ui.install_profile import ask_install_path
    dest = tmp_path / "P.icc"
    dest.write_bytes(b"old")
    shown = _answer(monkeypatch, "Replace")
    assert ask_install_path(None, dest) == dest
    assert shown == [("Replace", "", True)]


def test_a_new_name_installs_beside_it_and_keeps_the_extension(
        qapp, tmp_path, monkeypatch):
    from ui.install_profile import ask_install_path
    dest = tmp_path / "P.icm"
    dest.write_bytes(b"old")
    shown = _answer(monkeypatch, "Install", name="Müller Baryta 310 v2")
    assert ask_install_path(None, dest) == tmp_path / "Müller Baryta 310 v2.icm"
    assert shown == [("Install", "", True)]


def test_a_new_name_that_is_installed_too_says_so_and_replaces(
        qapp, tmp_path, monkeypatch):
    from ui.install_profile import ask_install_path
    dest = tmp_path / "P.icc"
    dest.write_bytes(b"old")
    (tmp_path / "Other.icc").write_bytes(b"other")
    shown = _answer(monkeypatch, "Replace", name="Other")
    assert ask_install_path(None, dest) == tmp_path / "Other.icc"
    assert shown[0][1] == ("A profile named Other.icc is installed too. "
                           "Replace overwrites it.")


def test_the_same_name_in_another_case_is_the_same_file(qapp, tmp_path,
                                                        monkeypatch):
    from ui.install_profile import ask_install_path
    dest = tmp_path / "Profile.icc"
    dest.write_bytes(b"old")
    shown = _answer(monkeypatch, "Replace", name="PROFILE")
    ask_install_path(None, dest)
    assert shown[0][0] == "Replace"


def test_cancel_installs_nothing_in_the_window(qapp, tmp_path, monkeypatch):
    from ui.install_profile import ask_install_path
    dest = tmp_path / "P.icc"
    dest.write_bytes(b"old")
    _answer(monkeypatch, "Cancel", name="Something")
    assert ask_install_path(None, dest) is None


@pytest.mark.parametrize("name, ok", [
    ("", False), ("   ", False), ("a/b", False), ("a:b", False),
    ("a\\b", False), ('a"b', False), (".hidden", False), ("x" * 101, False),
    ("x" * 100, True), ("Müller Барита 光沢", True), ("RR ColorJet v5", True)])
def test_names_are_checked(name, ok):
    from ui.install_profile import name_problem
    assert (name_problem(name) is None) is ok


def test_an_unusable_name_turns_the_button_off(qapp, tmp_path, monkeypatch):
    from ui.install_profile import ask_install_path
    dest = tmp_path / "P.icc"
    dest.write_bytes(b"old")
    shown = _answer(monkeypatch, "Cancel", name="a/b")
    ask_install_path(None, dest)
    assert shown[0][2] is False and "cannot contain" in shown[0][1]


def test_replace_is_the_default_and_the_field_holds_the_name(qapp, tmp_path):
    from ui.install_profile import InstallNameDialog
    dest = tmp_path / "P.icc"
    dest.write_bytes(b"old")
    dlg = InstallNameDialog(None, dest)
    assert dlg.ok_btn.isDefault() and dlg.ok_btn.text() == "Replace"
    assert dlg.name_edit.text() == "P"


def test_every_install_button_asks_first():
    """The four Install buttons: each asks with the file it would write,
    before it writes, and writes the file it is answered."""
    from ui.dialogs import scanin_dialog
    from ui.tabs import tab_check_refine, tab_profile
    src = inspect.getsource(tab_profile.TabProfile._install_with_name_check)
    assert src.index("ask_install_path(self, planned)") < src.index("install_profile(")
    assert "dest_name=dest.name" in src
    for fn in (tab_profile.TabProfile._on_install,
               tab_profile.TabProfile._show_applycal_result_dialog):
        assert "_install_with_name_check(" in inspect.getsource(fn)
    src = inspect.getsource(tab_check_refine)
    assert src.index("chosen = ask_install_path(dlg, planned)") < \
        src.index("dest = install_profile_file(")
    assert "dest_name=chosen.name" in src
    src = inspect.getsource(scanin_dialog.ScannerProfileDialog._install_profile)
    assert src.index("ask_install_path(") < src.index("shutil.copy2(")


# ---- Build Profile, on its own tab -------------------------------------------

@pytest.fixture
def build_tab(qapp, tmp_path, monkeypatch, installed):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    tab = TabProfile(ArgyllRunner(s), s)
    run = tmp_path / "proj" / "runs" / "run1"
    run.mkdir(parents=True)
    icc = run / "Demo-Report-Matrix.icc"
    shutil.copy2(V2, icc)
    tab.set_icc_path(icc)
    return tab, s, icc




def test_cancel_installs_nothing(build_tab, installed, monkeypatch):
    tab, _s, icc = build_tab
    installed.mkdir(parents=True)
    old = installed / icc.name
    old.write_bytes(b"the profile installed before")
    _answer(monkeypatch, "Cancel")
    tab._on_install()
    assert old.read_bytes() == b"the profile installed before"
    assert sorted(p.name for p in installed.iterdir()) == [icc.name]
    _answer(monkeypatch, "Replace")
    tab._on_install()
    assert old.read_bytes() == icc.read_bytes()


@pytest.mark.parametrize("tick", [True, False])
def test_a_name_typed_in_the_window_names_the_installed_copy_only(
        build_tab, installed, monkeypatch, tick):
    """Basti, 2026-10-11: only the INSTALLED copy takes the new name; with
    the tick, its description follows it."""
    tab, s, icc = build_tab
    s.set("install_named_by_description", tick)
    tab._desc_edit.setText("Demo-Report-Matrix")
    tab._m_desc_edit.setText("Demo-Report-Matrix")
    installed.mkdir(parents=True)
    (installed / "Demo-Report-Matrix.icc").write_bytes(b"installed earlier")
    before = icc.read_bytes()
    _answer(monkeypatch, "Install", name="Demo v2")
    tab._on_install()
    new = installed / "Demo v2.icc"
    assert new.is_file()
    assert (installed / "Demo-Report-Matrix.icc").read_bytes() == b"installed earlier"
    assert _desc(new) == ("Demo v2" if tick else "Demo-Report-Matrix")
    assert icc.read_bytes() == before and icc.name == "Demo-Report-Matrix.icc"


@pytest.mark.parametrize("mode", ["guided", "manual"])
def test_a_profile_renamed_after_the_build_installs_under_its_new_name(
        build_tab, installed, monkeypatch, mode):
    """Built as "Demo-Report-Matrix", renamed in the description field
    afterwards, ticked "Name the installed copy after the description": the
    installed copy's file AND its description carry the new name. The
    project's own file keeps its name and its description."""
    tab, s, icc = build_tab
    s.set("install_named_by_description", True)
    monkeypatch.setattr(tab, "_current_mode", lambda: mode)
    edit = tab._desc_edit if mode == "guided" else tab._m_desc_edit
    edit.setText("Müller Baryta 310 v2")
    before = icc.read_bytes()
    tab._on_install()
    dest = installed / "Müller Baryta 310 v2.icc"
    assert dest.is_file()
    assert _desc(dest) == "Müller Baryta 310 v2"
    assert icc.read_bytes() == before
    assert _desc(icc) == "Demo-Report-Matrix"


def test_without_the_tick_the_copy_is_the_project_file(build_tab, installed,
                                                       monkeypatch):
    tab, s, icc = build_tab
    s.set("install_named_by_description", False)
    tab._desc_edit.setText("Something else")
    tab._m_desc_edit.setText("Something else")
    tab._on_install()
    dest = installed / icc.name
    assert dest.read_bytes() == icc.read_bytes()


# ---- the description tag itself ---------------------------------------------

def test_set_description_rewrites_only_the_desc_tag():
    from core.icc_text import set_description
    from workflow.icc_info import read_icc
    data = V2.read_bytes()
    out = set_description(data, "Renamed profile")
    assert out != data and struct.unpack(">I", out[:4])[0] == len(out)

    def tags(b):
        n = struct.unpack(">I", b[128:132])[0]
        return {b[132 + 12 * i:136 + 12 * i]:
                b[struct.unpack(">I", b[136 + 12 * i:140 + 12 * i])[0]:][
                    :struct.unpack(">I", b[140 + 12 * i:144 + 12 * i])[0]]
                for i in range(n)}
    a, b = tags(data), tags(out)
    assert set(a) == set(b)
    for sig in a:
        if sig != b"desc":
            assert a[sig] == b[sig], sig
    p = Path(os.environ.get("TMPDIR", "/tmp"))
    assert set_description(out, "Renamed profile") is out    # already says it
    assert set_description(data, "  ") is data
    assert set_description(b"not a profile", "x") == b"not a profile"
    import tempfile
    with tempfile.TemporaryDirectory(dir=p) as d:
        f = Path(d) / "x.icc"
        f.write_bytes(out)
        assert read_icc(f).description == "Renamed profile"


def test_set_description_on_a_v4_profile_keeps_mluc():
    from core.icc_text import _mluc, set_description
    data = bytearray(V2.read_bytes())
    # Make it a v4 profile whose desc is an mluc tag, as ChromIQ's own
    # engine writes one.
    data[8:12] = bytes((4, 0x40, 0, 0))
    n = struct.unpack(">I", data[128:132])[0]
    for i in range(n):
        if data[132 + 12 * i:136 + 12 * i] == b"desc":
            blob = _mluc("Old name")
            off = len(data)
            data += blob
            struct.pack_into(">II", data, 136 + 12 * i, off, len(blob))
    struct.pack_into(">I", data, 0, len(data))
    out = set_description(bytes(data), "New name")
    for i in range(n):
        if out[132 + 12 * i:136 + 12 * i] == b"desc":
            off, size = struct.unpack(">II", out[136 + 12 * i:144 + 12 * i])
            assert out[off:off + size] == _mluc("New name")
