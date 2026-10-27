"""Build Profile's .mxf/.txt import removes the folder it converted into
(review 4.3.17 r2, NIT-3).

`TabProfile._convert_for_import` converted into a bare `tempfile.mkdtemp()`,
no prefix and never removed, so every import left a folder behind. It is a
`chromiq-import-*` folder now, removed when the import is over whatever the
answer was, and nothing reads from it afterwards: a filed measurement is the
door's own copy in the project.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings

from core.file_manager import exports_subdir
from workflow import i1profiler_turned as T

from tests.test_i1profiler_turned_export import _chart
from tests.test_i1profiler_turned_import import _mxf_from_txf


def _temp_folders() -> set:
    return {p.name for p in Path(tempfile.gettempdir()).iterdir()
            if p.is_dir() and (p.name.startswith("chromiq-import-")
                               or p.name.startswith("tmp"))}


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_profile import TabProfile
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    work = tmp_path / "work"
    work.mkdir()
    s.set("custom_output_path", str(work))
    fm = FileManager(s)
    t = TabProfile(ArgyllRunner(s), s)
    t.set_target_controller(MeasurementTargetController(fm))
    (tmp_path / "outside").mkdir()
    src = _chart(tmp_path / "src", "Src", 350)
    T.write_turned_export(src, exports_subdir(src.parent), "Src")
    mxf = _mxf_from_txf(T.TurnedFiles(exports_subdir(src.parent), "Src").txf(
        "i1Pro 3"), tmp_path / "outside" / "m.mxf")
    monkeypatch.setattr("ui.tabs.tab_profile.open_file_dialog",
                        lambda *a, **k: str(mxf))
    shown = []
    monkeypatch.setattr("ui.tabs.tab_profile.InfoDialog",
                        lambda t_, b, *a, **k: (shown.append(t_), type(
                            "D", (), {"exec": lambda s: 0})())[1])
    t._shown = shown
    t._mxf = mxf
    t._work = work
    return t


@pytest.mark.parametrize("answer", [True, False], ids=["handled", "old-route"])
def test_the_folder_goes_whatever_the_door_answers(tab, monkeypatch, answer):
    before = _temp_folders()
    seen = {}

    def offer(measurement):
        seen["path"] = Path(measurement)
        seen["existed"] = Path(measurement).is_file()
        assert Path(measurement).parent.name.startswith("chromiq-import-")
        return answer
    monkeypatch.setattr(tab, "_offer_import_into_a_project", offer)
    monkeypatch.setattr(tab, "_import_i1profiler_cxf", lambda p: None)
    tab._on_load_ti3()
    assert seen["existed"]
    assert not seen["path"].parent.exists()
    assert _temp_folders() == before


def test_the_folder_goes_when_the_door_raises(tab, monkeypatch):
    before = _temp_folders()
    monkeypatch.setattr(tab, "_offer_import_into_a_project",
                        lambda m: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        tab._on_load_ti3()
    assert _temp_folders() == before


def test_the_folder_goes_when_the_conversion_fails(tab, monkeypatch):
    before = _temp_folders()
    tab._mxf.write_text("not a CxF file", encoding="utf-8")
    called = []
    monkeypatch.setattr(tab, "_offer_import_into_a_project",
                        lambda m: called.append(m))
    tab._on_load_ti3()
    assert called == [] and tab._shown
    assert _temp_folders() == before


@pytest.mark.parametrize("pick", ["cancel", "new"])
def test_the_real_door_files_its_own_copy_and_leaves_no_folder(
        tab, monkeypatch, pick):
    """Through the real filing door: Cancel at the list, or a new project.
    The filed copy is in the project and still readable once the folder has
    gone."""
    import ui.dialogs.name_prompt as name_prompt
    import ui.dialogs.project_picker as project_picker
    import ui.measurement_filing as mf
    before = _temp_folders()
    monkeypatch.setattr(project_picker, "choose_project",
                        lambda *a, **k: None if pick == "cancel"
                        else project_picker.NEW_PROJECT)
    monkeypatch.setattr(name_prompt, "ask_for_project_name",
                        lambda *a, **k: "Fresh")
    monkeypatch.setattr(mf, "InfoDialog", lambda *a, **k: type(
        "D", (), {"exec": lambda s: 0})())
    monkeypatch.setattr(mf, "only_you_can_confirm_the_chart",
                        lambda *a: True)
    monkeypatch.setattr("ui.ti2_loader._choice_dialog",
                        lambda *a, **k: "continue")
    filed = []
    monkeypatch.setattr(tab, "_adopt_filed_ti3", filed.append)
    tab._on_load_ti3()
    assert _temp_folders() == before
    if pick == "new":
        assert filed, "nothing was filed"
        f = Path(filed[0])
        assert tab._work in f.parents and f.is_file()
        assert "BEGIN_DATA" in f.read_text(encoding="utf-8")
    else:
        assert filed == []


def test_only_its_own_folder_is_removed():
    import inspect
    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._on_load_ti3)
    assert 'startswith("chromiq-import-")' in src
    assert 'prefix="chromiq-import-"' in inspect.getsource(
        TabProfile._convert_for_import)
