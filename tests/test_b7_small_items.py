"""4.3.5 beta 7, three small items left over from beta 6.

a. Build Profile's file notes ("No file selected", the chosen measurement)
   were #909090 on every appearance: 2.71:1 on Light's ground, measured on
   screen in the beta 6 regression review. They take a grey per appearance.
b. The calibration loader converted an i1Profiler export and then failed to
   SAVE it beside the export, and said it could not READ the file:
   M-CONVERT-NOT-SAVED.
c. The converter's "txt2ti3.exe: exit code N" detail was English in every
   language.
"""
from __future__ import annotations

import subprocess
import types
from pathlib import Path

import pytest

import core.i18n as i18n
from tests.test_209_argyll_tool_paths_carry_the_windows_suffix import (  # noqa: F401
    _i1profiler_txt, fake_argyll, windows)


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ---- a. the file notes' grey ------------------------------------------------
def test_the_file_note_is_readable_on_every_appearance():
    from ui import light_styles as L, neutral_styles as N, styles as D
    from ui.tabs.tab_profile import _note_ink
    grounds = {"light": ("#eeece8", L.LM_BG_PANEL, L.LM_BG_SURFACE),
               "dark": (D.BG_PANEL, D.BG_DARK),
               "neutral": (N.NM_BG_PANEL, N.NM_BG_SURFACE)}
    for mode, bgs in grounds.items():
        ink = _note_ink(mode)
        for bg in bgs:
            assert _contrast(ink, bg) >= 4.5, (mode, ink, bg, _contrast(ink, bg))


def test_no_fixed_909090_on_the_build_profile_file_notes():
    src = (Path(__file__).resolve().parent.parent / "ui" / "tabs" /
           "tab_profile.py").read_text(encoding="utf-8")
    assert "_paint_note(self._file_lbl)" in src
    assert "_paint_note(self._pc_ti3_lbl)" in src
    assert "self._file_lbl.setStyleSheet(\"color: #909090" not in src
    assert "self._pc_ti3_lbl.setStyleSheet(\"color: #909090" not in src


def test_a_theme_change_repaints_the_note(qapp):
    from PyQt6.QtWidgets import QLabel
    from ui.tabs.tab_profile import TabProfile, _note_ink, _paint_note
    lbl, path = QLabel("No file selected"), QLabel("/a/b.ti3")
    _paint_note(lbl, "dark")
    path.setStyleSheet("font-size: 11px;")
    me = types.SimpleNamespace(_file_lbl=lbl, _pc_ti3_lbl=path)
    TabProfile.set_appearance(me, "light")
    assert _note_ink("light") in lbl.styleSheet()
    assert "color" not in path.styleSheet(), "a loaded path keeps the text ink"


# ---- b. a failed save is not a failed read --------------------------------
def test_a_failed_save_says_so(tmp_path, monkeypatch, qapp):
    import shutil
    import ui.tabs.tab_profile as tp
    import workflow.reference_convert as rc
    from workflow import measurement_messages as M
    src = tmp_path / "cal.txt"
    src.write_text("x", encoding="utf-8")
    converted = tmp_path / "out.ti3"
    converted.write_text("CTI3\n", encoding="utf-8")
    monkeypatch.setattr(rc, "convert_i1profiler_measurement",
                        lambda s, a, o: converted)

    def no_room(a, b, *k, **kw):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(shutil, "copy2", no_room)
    shown = []

    class _Dlg:
        def __init__(self, title, body, parent=None, **kw):
            shown.append((title, body))

        def exec(self):
            return 0
    monkeypatch.setattr(tp, "InfoDialog", _Dlg)
    me = types.SimpleNamespace(_settings={"argyll_bin_path": "/nowhere"},
                               _pc_log=None)
    assert tp.TabProfile._convert_calibration_measurement(me, src) is None
    title, body = shown[0]
    assert title == M.M_CONVERT_NOT_SAVED.title
    assert "could not read" not in body
    assert "cal.ti3" in body and str(tmp_path) in body
    assert "Permission denied" in body


# ---- c. the exit-code detail is translated -------------------------------
@pytest.fixture
def german():
    before = i18n.current_language()
    i18n.set_language("de")
    yield
    i18n.set_language(before or "en")


def test_the_exit_code_detail_speaks_german(windows, german, tmp_path,
                                            monkeypatch):
    import workflow.reference_convert as rc

    def silent_failure(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 3, "", "")
    real = rc.run_text
    monkeypatch.setattr(rc, "run_text",
                        lambda cmd, runner=None, **kw: real(
                            cmd, runner=silent_failure, **kw))
    with pytest.raises(rc.ReferenceConvertError) as e:
        rc.convert_i1profiler_measurement(_i1profiler_txt(tmp_path), windows,
                                          tmp_path / "out")
    assert str(e.value).endswith("txt2ti3.exe: Exit-Code 3"), str(e.value)
