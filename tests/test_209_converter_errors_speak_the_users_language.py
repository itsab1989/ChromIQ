"""#209, the second half: the converter's reason reaches the user in their
language, and a calibration's i1Profiler export loads with Windows names.

The reporter's screenshot was a Russian window with one English paragraph in
it, and that paragraph was the reason: ``ReferenceConvertError`` carried a
hard-coded English sentence from ``workflow/reference_convert.py`` into every
window that shows it. Each reason is now a §M message (M-CONVERT-*), rendered
at raise time.

And the calibration door. With Run type = Calibration the Build Profile tab's
load button is printcal's input, and it took a ``.ti3`` only, so a calibration
chart measured in i1Profiler had to go through Tools > Convert first. It now
converts the export itself, through the same converter as every other door,
so ``txt2ti3.exe`` is found on Windows (the simulation is the one of
``test_209_argyll_tool_paths_carry_the_windows_suffix.py``).
"""
from __future__ import annotations

import ast
import types
from pathlib import Path

import pytest

import core.i18n as i18n
import core.resource_path as rp
from tests.test_209_argyll_tool_paths_carry_the_windows_suffix import (  # noqa: F401
    _i1profiler_txt, fake_argyll, windows)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def russian():
    before = i18n.current_language()
    i18n.set_language("ru")
    yield
    i18n.set_language(before or "en")


# --------------------------------------------------------------------------
# every reason is a catalogued message, rendered in the user's language
# --------------------------------------------------------------------------

def test_no_reason_is_written_in_the_converter_itself():
    """Every ``ReferenceConvertError`` raised in the converter comes from
    ``_failure(M.M_CONVERT_...)``: no English literal can be raised again."""
    src = (ROOT / "workflow" / "reference_convert.py").read_text(
        encoding="utf-8")
    raised = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            f = node.exc.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            raised.append((node.lineno, name, node.exc))
    assert raised
    for line, name, call in raised:
        assert name == "_failure", f"line {line} raises {name}(...)"
        msg = call.args[0]
        assert isinstance(msg, ast.Attribute) and \
            msg.attr.startswith("M_CONVERT_"), f"line {line}"


def test_the_missing_tool_reason_is_russian(windows, russian, tmp_path):
    from workflow.reference_convert import (ReferenceConvertError,
                                            convert_i1profiler_measurement)
    (windows / "txt2ti3.exe").unlink()
    with pytest.raises(ReferenceConvertError) as e:
        convert_i1profiler_measurement(_i1profiler_txt(tmp_path), windows,
                                       tmp_path / "out")
    exc = e.value
    assert exc.message_id == "M-CONVERT-TOOL-MISSING"
    assert "txt2ti3.exe" in str(exc)
    from workflow import measurement_messages as M
    english = M.M_CONVERT_TOOL_MISSING.body
    assert i18n.tr(english) != english, "no Russian for the message"
    assert str(exc) == i18n.tr(english).format(tool="txt2ti3.exe")
    assert exc.title == i18n.tr("The file could not be converted")
    assert not any("a" <= ch <= "z" for ch in exc.title.lower()), exc.title


def test_a_failing_tool_names_its_own_line_as_the_detail(windows, tmp_path,
                                                         monkeypatch):
    import subprocess
    import workflow.reference_convert as rc

    def fails(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "",
                                           "txt2ti3: Error - No patches\n")
    real = rc.run_text
    monkeypatch.setattr(rc, "run_text",
                        lambda cmd, runner=None, **kw: real(cmd, runner=fails,
                                                            **kw))
    with pytest.raises(rc.ReferenceConvertError) as e:
        rc.convert_i1profiler_measurement(_i1profiler_txt(tmp_path), windows,
                                          tmp_path / "out")
    assert e.value.message_id == "M-CONVERT-TOOL-FAILED"
    assert str(e.value).endswith("Details: txt2ti3: Error - No patches")


@pytest.mark.parametrize("lang", ["de", "es", "fr", "it", "ja", "nl", "no",
                                  "pl", "pt", "ru", "sv", "uk", "zh_CN"])
def test_every_converter_message_is_translated(lang):
    """In the catalogue itself: "Details: {detail}" is the same words in
    German and Dutch, so a lookup that returns the English proves nothing."""
    import json
    from workflow import measurement_messages as M
    cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json").read_text(
        encoding="utf-8"))
    texts = [M._CONVERT_DETAILS]
    for msg in M.CONVERT_MESSAGES:
        texts += [msg.title, msg.body]
    missing = [t[:60] for t in texts if not cat.get(t)]
    assert not missing, missing


# --------------------------------------------------------------------------
# the calibration door
# --------------------------------------------------------------------------

def _a_stub_profile_tab(windows):
    said, logged = [], []
    tab = types.SimpleNamespace(
        _settings={"argyll_bin_path": str(windows)},
        _pc_log=types.SimpleNamespace(appendPlainText=logged.append))
    return tab, said, logged


def test_a_calibration_txt_converts_on_windows(windows, fake_argyll,
                                               tmp_path, monkeypatch):
    from ui.tabs import tab_profile as tp
    monkeypatch.setattr(tp, "InfoDialog", lambda *a, **k: pytest.fail(
        f"a window opened: {a[:2]}"))
    tab, said, logged = _a_stub_profile_tab(windows)
    src = _i1profiler_txt(tmp_path)
    got = tp.TabProfile._convert_calibration_measurement(tab, src)
    assert got == src.parent / "полны.ti3" and got.is_file()
    assert fake_argyll.ran == ["txt2ti3.exe", "spec2cie.exe"]
    assert "XYZ_X" in got.read_text(encoding="utf-8")
    assert logged and src.name in logged[0]


def test_a_calibration_conversion_never_writes_over_a_file(windows,
                                                           fake_argyll,
                                                           tmp_path):
    from ui.tabs import tab_profile as tp
    tab, said, logged = _a_stub_profile_tab(windows)
    src = _i1profiler_txt(tmp_path)
    mine = src.parent / "полны.ti3"
    mine.write_text("the user's own file", encoding="utf-8")
    got = tp.TabProfile._convert_calibration_measurement(tab, src)
    assert got == src.parent / "полны-2.ti3" and got.is_file()
    assert mine.read_text(encoding="utf-8") == "the user's own file"


def test_before_the_fix_the_calibration_door_said_so_in_the_window(
        monkeypatch, windows, fake_argyll, tmp_path):
    """The stub is honest: with the bare tool name the same method opens the
    converter's window, with the §M headline and reason, and returns None."""
    monkeypatch.setattr(rp, "argyll_binary", lambda name: name)
    from ui.tabs import tab_profile as tp
    shown = []

    class _Dlg:
        def __init__(self, title, body, *a, **k):
            shown.append((title, body))

        def exec(self):
            return 0
    monkeypatch.setattr(tp, "InfoDialog", _Dlg)
    tab, said, logged = _a_stub_profile_tab(windows)
    assert tp.TabProfile._convert_calibration_measurement(
        tab, _i1profiler_txt(tmp_path)) is None
    assert len(shown) == 1
    assert shown[0][0] == "The file could not be converted"
    assert "(txt2ti3)" in shown[0][1]


def test_the_calibration_button_offers_i1profiler_files():
    import inspect
    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._pc_browse_ti3)
    assert "*.txt" in src and "*.mxf" in src
    assert "_convert_calibration_measurement" in src
