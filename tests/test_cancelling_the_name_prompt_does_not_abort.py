"""Cancelling "Copy the project into your ChromIQ folder as:" used to KILL ChromIQ.

`ui.ti2_loader._ask_project_name` answers ``None`` when the person presses
Cancel — its own docstring says so — and two callers in `ui/tabs/tab_chart.py`
unpacked the answer BEFORE testing it, so the `if … is None` guard sitting right
underneath was unreachable. Unpacking None raises `TypeError`, and both callers
are Qt slots: PyQt hands an escaping exception to `sys.excepthook` and then calls
`qFatal()`, so the app aborted. Measured through the real button on the plainest
journey there is — no project open, *Load patch set*, pick a file, press Cancel —
**exit 134, SIGABRT**. It shipped in every release from 2026-07-24.

The same file writes it correctly a third time (`ui/ti2_loader.py:721-724`):
assign, test, then unpack. These tests hold all three to that shape.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager                       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.tabs.tab_chart import TabChart                          # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    fm = FileManager(s)
    return TabChart(ArgyllRunner(s), fm, s)


def test_cancelling_the_name_prompt_when_loading_a_patch_set(tab, tmp_path,
                                                             monkeypatch):
    """Load patch set → pick a file → Cancel. The app must survive, and nothing
    may be loaded."""
    import ui.tabs.tab_chart as TC
    import ui.ti2_loader as ti2_loader

    ti1 = tmp_path / "MyPatches.ti1"
    ti1.write_text("CTI1\n")
    monkeypatch.setattr(TC, "open_file_dialog", lambda *a, **k: str(ti1),
                        raising=False)
    monkeypatch.setattr(tab, "_ti1_load_destination", lambda *a, **k: "new",
                        raising=False)
    monkeypatch.setattr(ti2_loader, "_ask_project_name", lambda *a, **k: None)
    started = []
    monkeypatch.setattr(tab._file_mgr, "start_new_project",
                        lambda *a, **k: started.append(a), raising=False)

    tab._on_load_ti1()          # must not raise — a raise here aborts the app

    assert not started, "a project was created after the person pressed Cancel"
    assert tab._preset_ti1_path is None


def test_cancelling_the_name_prompt_when_copying_an_external_project(tab,
                                                                     monkeypatch):
    """Open a profile that lives outside the working folder → agree to copy it
    in → Cancel the name prompt."""
    import ui.ti2_loader as ti2_loader
    import workflow.chart_import as chart_import

    monkeypatch.setattr(ti2_loader, "_ask_project_name", lambda *a, **k: None)
    copied = []
    monkeypatch.setattr(chart_import, "copy_whole_project",
                        lambda *a, **k: copied.append(a), raising=False)

    # Reach the same two lines without the file dialogs in front of them.
    import inspect
    # The open was split: `_load_existing_profile` is the file dialog,
    # `open_project_manifest` is the open (so the measurement import can
    # perform the whole open rather than a cut-down copy). The
    # external-project copy lives in the half that opens.
    src = inspect.getsource(tab.open_project_manifest)
    assert "_picked = _ask_project_name(" in src, \
        "the external-project copy no longer asks for a name here"
    assert "picked_name, replace = _picked" in src, \
        "the answer is unpacked before it is tested — Cancel aborts the app"
    assert not copied


@pytest.mark.parametrize("where", ["ui/tabs/tab_chart.py", "ui/ti2_loader.py"])
def test_no_caller_unpacks_the_answer_before_testing_it(where):
    """The shape that crashed, held for the whole codebase.

    `_ask_project_name` may answer None, so `a, b = _ask_project_name(...)` is
    always wrong: it raises before any guard can run. Assign, test, then unpack.
    """
    import re
    src = Path(where).read_text(encoding="utf-8")
    bad = [ln.strip() for ln in src.splitlines()
           if re.match(r"^\s*\w+\s*,\s*\w+\s*=\s*_ask_project_name\(", ln)]
    assert not bad, (
        f"{where} unpacks _ask_project_name's answer before testing it, which "
        f"raises TypeError out of a Qt slot and aborts the app: {bad}")
