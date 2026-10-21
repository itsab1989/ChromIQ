"""K2 (Knut, 2026-10-20): "Name the installed copy after the description".

What he met: run 1 was installed with the tick OFF, so the copy kept the
project's file name (``Printer_ET-8550_ChromIQ_i1Pro2.icc``) while its desc
said ``...-Brilliant_Supreme_Matte_..._2026.10.19``; run 2's Install then found
that file ("A profile with this name is already installed"). Every run of a
project has the same file name, so with the tick off that is bound to happen.

Measured on screen (report K2): the tick is ONE install preference shared by
every run (it neither leaked nor reset between run1/run2/run3, the box simply
read the one setting); it was OFF for a new user; and an ``.icm`` profile
installed under its description became an ``.icc`` file.

Now: ON by default (a stored choice is kept), and the installed copy keeps
the source's extension. With the tick on, the file name and the desc inside
both follow the Profile description field, for .icc and .icm alike.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from workflow import profile_builder as PB

ICC = (Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
       / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26.icc")
DESC = "Printer_ET-8550_ChromIQ_i1Pro2-Brilliant_Supreme_Matte_230gsm_Media-EM_HighQ_1944p_2026.10.19"


class _Settings(dict):
    def get(self, key, default=None):          # noqa: A003
        return dict.get(self, key, default)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    d = tmp_path / "ColorSync"
    monkeypatch.setattr(PB, "_profile_dir", lambda: d)
    return d


def test_the_tick_is_on_for_a_new_user(tmp_path):
    from core.settings import DEFAULTS, AppSettings
    assert DEFAULTS["install_named_by_description"] is True
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "fresh.ini"), QSettings.Format.IniFormat)
    assert s.get("install_named_by_description") is True
    # a setting store that knows nothing of the key names the copy too
    assert PB.installed_profile_name(DESC, _Settings()) == DESC


def test_a_choice_to_untick_is_kept(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "kept.ini"), QSettings.Format.IniFormat)
    s.set("install_named_by_description", False)
    s2 = AppSettings()
    s2._qs = QSettings(str(tmp_path / "kept.ini"), QSettings.Format.IniFormat)
    assert s2.get("install_named_by_description") is False
    assert PB.installed_profile_name(DESC, s2) is None


@pytest.mark.parametrize("ext", [".icc", ".icm", ".ICM"])
def test_file_name_and_description_follow_the_field(installed, tmp_path, ext):
    from workflow.icc_info import read_icc
    src = tmp_path / f"Printer_ET-8550_ChromIQ_i1Pro2{ext}"
    shutil.copy2(ICC, src)
    name = PB.installed_profile_name(DESC, _Settings(
        install_named_by_description=True))
    planned = PB.install_destination(src, name)
    assert planned.name == DESC + ext, planned.name
    dest = PB.install_profile_file(src, name, description=DESC)
    assert dest == planned and dest.exists()
    assert read_icc(dest).description == DESC
    # the project's own file is untouched
    assert src.read_bytes() == ICC.read_bytes()


def test_the_plain_copy_still_keeps_its_name_and_extension(installed, tmp_path):
    src = tmp_path / "Printer_ET-8550_ChromIQ_i1Pro2.icm"
    shutil.copy2(ICC, src)
    assert PB.install_destination(src, None).name == src.name


def test_the_box_reads_the_one_setting_on_both_modes(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "tab.ini"), QSettings.Format.IniFormat)
    tab = TabProfile(ArgyllRunner(s), s)
    assert tab._install_name_cb.isChecked() and tab._m_install_name_cb.isChecked()
    tab._install_name_cb.setChecked(False)
    assert not tab._m_install_name_cb.isChecked()
    assert s.get("install_named_by_description") is False
    # not a per-run setting: the Build Profile store never carries it
    assert "install_named_by_description" not in tab._m_collect_preset_data()
    assert "install_named_by_description" not in tab._collect_guided_profile_fields()
    tab.deleteLater()


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance()
