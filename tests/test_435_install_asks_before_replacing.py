"""Installing a profile over one of the same file name, and renaming a profile
after it was built (#182, Knut 6102031563, answer 3).

    "Yes. Ask if user wants to replace existing or cancel to rename the
    profile before trying to install it again. Giving a new name to the
    profile, after a profile is built, should still rename that profile file
    name (and the profile description field inside the ICC profile (if
    selected the option that the description is same as file name), when
    clicking the install button."

* Every Install button asks ``ui.install_profile.confirm_replace`` with the
  file it would write, before writing it: Build Profile, Apply Calibration,
  Check & Refine's "Install Profile As Is" and the scanner window.
* The question's words (M-PROFILE-INSTALL-REPLACE) wait in §M-PROPOSED, so
  the window is not shown until they are approved and an Install replaces as
  it always has. Once approved: Replace installs, Cancel installs nothing.
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
from PyQt6.QtWidgets import QApplication, QMessageBox    # noqa: E402

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


@pytest.fixture
def approved(monkeypatch):
    """The question as it will be once its words are approved."""
    monkeypatch.setattr(M, "M_PROFILE_INSTALL_REPLACE", dataclasses.replace(
        M.M_PROFILE_INSTALL_REPLACE, approved=True))


def _answer(monkeypatch, which):
    """Answer the window with *which* ("Replace" / "Cancel"); returns the
    list of windows shown."""
    shown = []

    def _exec(box):
        shown.append(box.objectName())
        for b in box.buttons():
            if b.text().replace("&", "") == which:
                b.click()
                return 0
        raise AssertionError([b.text() for b in box.buttons()])
    monkeypatch.setattr(QMessageBox, "exec", _exec)
    return shown


def _desc(path: Path) -> str:
    from workflow.icc_info import read_icc
    return read_icc(path).description


# ---- the question -----------------------------------------------------------

def test_the_question_waits_for_approval():
    msg = M.CATALOGUE["M-PROFILE-INSTALL-REPLACE"]
    assert not msg.approved
    title, body = msg.render(path="/x/Profile.icc")
    assert title == "A profile with this name is already installed"
    assert body == ("/x/Profile.icc is already in your profile folder.\n\n"
                    "Replace it with this profile, or cancel and give this "
                    "profile another name before you install it.")


def test_until_approved_nothing_is_asked_and_it_replaces(qapp, tmp_path,
                                                         monkeypatch):
    from ui.install_profile import confirm_replace
    shown = _answer(monkeypatch, "Cancel")
    dest = tmp_path / "P.icc"
    assert confirm_replace(None, dest) is True        # nothing there
    dest.write_bytes(b"old")
    assert confirm_replace(None, dest) is True        # today's behaviour
    assert shown == []


def test_once_approved_replace_and_cancel(qapp, tmp_path, monkeypatch,
                                          approved):
    from ui.install_profile import confirm_replace
    dest = tmp_path / "P.icc"
    shown = _answer(monkeypatch, "Cancel")
    assert confirm_replace(None, dest) is True and shown == []
    dest.write_bytes(b"old")
    assert confirm_replace(None, dest) is False
    assert shown == ["profile_install_replace"]
    _answer(monkeypatch, "Replace")
    assert confirm_replace(None, dest) is True


def test_every_install_button_asks_first():
    """The four Install buttons: each asks with the file it would write,
    before it writes."""
    from ui.dialogs import scanin_dialog
    from ui.tabs import tab_check_refine, tab_profile
    src = inspect.getsource(tab_profile.TabProfile._on_install)
    assert src.index("_may_install_over") < src.index("install_profile(")
    src = inspect.getsource(
        tab_profile.TabProfile._show_applycal_result_dialog)
    assert src.index("_may_install_over(icc_path, name, fallback)") < \
        src.index("install_profile(")
    src = inspect.getsource(tab_check_refine)
    assert src.index("confirm_replace(dlg, install_destination(") < \
        src.index("dest = install_profile_file(icc, name,")
    src = inspect.getsource(scanin_dialog.ScannerProfileDialog._install_profile)
    assert src.index("confirm_replace(") < src.index("shutil.copy2(")


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


def test_cancel_installs_nothing(build_tab, installed, monkeypatch, approved):
    tab, _s, icc = build_tab
    installed.mkdir(parents=True)
    old = installed / icc.name
    old.write_bytes(b"the profile installed before")
    shown = _answer(monkeypatch, "Cancel")
    tab._on_install()
    assert shown == ["profile_install_replace"]
    assert old.read_bytes() == b"the profile installed before"
    _answer(monkeypatch, "Replace")
    tab._on_install()
    assert old.read_bytes() == icc.read_bytes()


def test_today_it_replaces_without_a_window(build_tab, installed,
                                            monkeypatch):
    tab, _s, icc = build_tab
    installed.mkdir(parents=True)
    (installed / icc.name).write_bytes(b"old")
    shown = _answer(monkeypatch, "Cancel")
    tab._on_install()
    assert shown == []
    assert (installed / icc.name).read_bytes() == icc.read_bytes()


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
