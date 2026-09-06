"""A widget's visibility was load-bearing state, and it went dark for months.

`Ti2RelayoutDialog._engine_active()` decides three things: which renderer draws
the preview, which renderer writes a "Save As" deliverable, and whether the
printtarg pass runs at all. Until this branch it ended

    return (self._engine_panel_grp is not None
            and not self._engine_panel_grp.isHidden()
            and self._spec is not None)

i.e. it asked a QGroupBox whether it was showing and read that as *is this an
engine chart*. Commit `72c54d1f` (2026-06-29, "#93: editor - hide the
layout-editing panels") then made `_refresh_engine_panel_visible` hide that
group unconditionally, in the belief that a hidden widget is inert. Its message
says the chart "renders and saves unchanged through the edit->apply round-trip",
and the edit->apply round trip really is unchanged, because that path hands back
only the `.ti1`.

What went with it, MEASURED by agent CK in the real app on a real i1Pro ENGINE
chart saved from this window:

    NUMBER_OF_SETS      525  ->  528
    PASSES_IN_STRIPS2    21  ->   24
    STEPS_IN_PASS        25  ->   22
    channels.json    present -> ABSENT

— a different chart, with three extra printtarg fill patches, a different grid,
and no engine sidecar. For a CR30 that sidecar is not decoration:
`measure_manager.py:481` and `:1587` and the ChromIQ chartread fork read the
chart's own recorded layout.

And it is why Knut could not open the window at all. With the predicate stuck
False, `_regenerate` ran printtarg on every open of an RGB chart — including a
CR30 chart, which printtarg has no `-i` for.

So this file pins the predicate to the thing it MEANS, and pins that an engine
chart never reaches printtarg from this window.
"""
from __future__ import annotations

import inspect
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                            # noqa: E402
from PyQt6.QtWidgets import QApplication                      # noqa: E402

import ui.dialogs.ti2_relayout_dialog as M                    # noqa: E402
from core.argyll_runner import ArgyllRunner                   # noqa: E402
from core.settings import AppSettings                         # noqa: E402
from workflow import ti2_relayout as R                        # noqa: E402

_REAL_REGENERATE_AT_IMPORT = M.Ti2RelayoutDialog._regenerate


#: `tests/conftest.py::_no_real_editor_render` replaces
#: `Ti2RelayoutDialog._regenerate` with a no-op for EVERY test in the suite, so
#: no test can accidentally shell out to printtarg. That stub is exactly the
#: thing this file needs to bypass: the question here is what `_regenerate`
#: itself does. Bound at import time, before the (monkeypatch-based, per-test)
#: stub is installed, so this is the shipped method and not a copy of it.
def _ti2(instrument: str) -> str:
    return f'''CTI2

ORIGINATOR "test"
TARGET_INSTRUMENT "{instrument}"
COLOR_REP "iRGB"
PAPER_SIZE "210.0x297.0"
APPROX_WHITE_POINT "95.1 100.0 108.8"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8
2 "A2" 0.0 0.0 0.0 0.0 0.0 0.0
3 "A3" 100.0 0.0 0.0 41.2 21.3 1.9
END_DATA
'''


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings():
    s = AppSettings()
    s._qs = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      "chromiq-test", "editor-engine-active")
    s._qs.clear()
    return s


def _engine_chart(tmp_path, instrument="CR30", target='CR30'):
    """A .ti2 with the engine sidecar a ChromIQ-built chart carries."""
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_ti2(target), encoding="utf-8")
    (tmp_path / "chart.channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "seed": 7,
                   "recipe": {"instrument": instrument, "paper": "A4"}},
    }), encoding="utf-8")
    return ti2


def _printtarg_chart(tmp_path):
    """The same chart with NO sidecar, i.e. a printtarg chart off disk."""
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(_ti2("GretagMacbeth i1 Pro"), encoding="utf-8")
    return ti2


def _editor(monkeypatch, settings=None):
    s = settings or _settings()
    ed = M.Ti2RelayoutDialog(ArgyllRunner(s), s)
    return ed


# ---------------------------------------------------------------------------
# 1. the predicate tests the thing it means
# ---------------------------------------------------------------------------
def test_engine_active_does_not_read_a_widgets_visibility():
    """The class of bug, read off the source.

    A predicate about the DOCUMENT must not be answered by a control's
    appearance: `#93` hid the control and the document's meaning changed with
    it, silently, for two months.
    """
    src = inspect.getsource(M.Ti2RelayoutDialog._engine_active)
    body = src.split('"""')[-1]      # skip the docstring, which quotes the bug
    for banned in ("isHidden", "isVisible", "_engine_panel_grp"):
        assert banned not in body, (
            f"_engine_active is answering from {banned} again — that is the "
            f"defect, not the fix")


def test_an_engine_chart_makes_the_engine_active(qapp, tmp_path, monkeypatch):
    ed = _editor(monkeypatch)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    monkeypatch.setattr(ed, "_do_engine_preview", lambda *a, **k: None)
    assert ed._load_chart_from(_engine_chart(tmp_path)) is True
    assert ed._engine_recipe is not None
    assert ed._loaded_printtarg_chart is False
    assert ed._engine_active() is True
    ed.deleteLater()


def test_a_printtarg_chart_off_disk_keeps_printtarg(qapp, tmp_path, monkeypatch):
    """The other half, and the reason the fix is not "always use the engine".

    A chart that came from printtarg keeps its real, no-clip layout. Getting
    this wrong would silently re-lay every foreign chart the editor is handed.
    """
    ed = _editor(monkeypatch)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    assert ed._load_chart_from(_printtarg_chart(tmp_path)) is True
    assert ed._engine_recipe is None
    assert ed._loaded_printtarg_chart is True
    assert ed._engine_active() is False
    ed.deleteLater()


def test_a_multi_ink_chart_is_engine_only_whatever_else_is_true(qapp,
                                                                tmp_path,
                                                                monkeypatch):
    """#72 decision 0, unchanged: `R.regenerate` hard-fails on non-RGB."""
    ed = _editor(monkeypatch)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    assert ed._load_chart_from(_printtarg_chart(tmp_path)) is True
    ed._spec.color_rep = "iCMYK"
    assert ed._engine_active() is True
    ed.deleteLater()


# ---------------------------------------------------------------------------
# 2. an engine chart never reaches printtarg from this window
# ---------------------------------------------------------------------------
def test_opening_a_cr30_chart_never_spawns_printtarg(qapp, tmp_path,
                                                     monkeypatch):
    """Knut's crash, at the point it is now stopped.

    `run_text` FAILS the test if it is called, so this cannot pass by the
    process merely failing somewhere else.
    """
    def _no(*a, **k):
        raise AssertionError("printtarg was spawned for an engine chart")
    monkeypatch.setattr(R, "run_text", _no)

    ed = _editor(monkeypatch)
    engine_calls = []
    monkeypatch.setattr(ed, "_do_engine_preview",
                        lambda *a, **k: engine_calls.append(1))
    assert ed._load_chart_from(_engine_chart(tmp_path)) is True
    assert ed._regenerate is not _REAL_REGENERATE_AT_IMPORT, (
        "the suite-wide _regenerate stub is gone, so this test is no longer "
        "bypassing anything and the assertion below proves nothing")
    _REAL_REGENERATE_AT_IMPORT(ed, save_to=None)
    qapp.processEvents()
    assert engine_calls, "the engine preview was never asked to draw it"
    ed.deleteLater()


def test_save_as_on_an_engine_chart_goes_to_the_engine_writer(qapp, tmp_path,
                                                              monkeypatch):
    """525 -> 528 patches, 21x25 -> 24x22 strips, channels.json gone.

    This is the dispatch that never fired. The engine writer itself is a real
    Argyll build and is proved on screen; what is pinned here is that the
    printtarg writer is not what "Save As" reaches for.
    """
    ed = _editor(monkeypatch)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    assert ed._load_chart_from(_engine_chart(tmp_path)) is True
    went = []
    monkeypatch.setattr(ed, "_write_engine_chart_into",
                        lambda target, name: went.append((target, name)) or "ok")
    monkeypatch.setattr(R, "regenerate", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("the printtarg relayout was used for an engine chart")))
    out = tmp_path / "out"
    assert ed._write_chart_into(out, "out") == "ok"
    assert went, "the engine writer was never called"
    ed.deleteLater()


def test_the_suggested_name_still_counts_pages_for_an_engine_chart(
        qapp, tmp_path, monkeypatch):
    """Dropping the printtarg pass dropped `self._regen`, and the Save-As
    default name took its page count from it. The engine knows its own pages."""
    ed = _editor(monkeypatch)
    monkeypatch.setattr(ed, "_regenerate", lambda **k: None)
    monkeypatch.setattr(ed, "_do_engine_preview", lambda *a, **k: None)
    assert ed._load_chart_from(_engine_chart(tmp_path)) is True
    ed._engine_tiffs = [tmp_path / "p1.tif", tmp_path / "p2.tif"]
    assert "2pages" in ed._suggest_chart_name()
    ed._engine_tiffs = [tmp_path / "p1.tif"]
    assert "1page" in ed._suggest_chart_name()
    ed.deleteLater()


# ---------------------------------------------------------------------------
# 3. and no tool's raw stderr reaches a modal from here (CK-3)
# ---------------------------------------------------------------------------
def test_every_call_that_can_receive_a_tool_dump_routes_it_through_the_window():
    """This window was the ONLY place in the app that showed an Argyll tool's
    stderr in a modal.

    THREE calls can receive one, and they are found by what they CALL rather
    than by name, so a fourth door added later is caught too:

      * the render worker's result, which is `R.regenerate`'s RuntimeError, and
      * both callers of `_write_chart_into`, which runs its own `R.regenerate`.

    The other `warn(..., str(exc))` calls in this module are left alone on
    purpose: they report a file the user picked that could not be read, where
    the exception IS one sentence and is the right thing to show. Narrowing to
    the tool paths is what makes this test about the defect rather than about
    the word "warn".
    """
    src = inspect.getsource(M.Ti2RelayoutDialog)
    lines = src.splitlines()
    sites = [i for i, ln in enumerate(lines)
             if "_write_chart_into(" in ln and "def " not in ln]
    sites += [i for i, ln in enumerate(lines)
              if "isinstance(result, Exception)" in ln]
    assert len(sites) >= 3, (
        f"only {len(sites)} tool-failure sites found — this test has gone "
        f"blind to the thing it guards")
    for i in sites:
        window = "\n".join(lines[i:i + 6])
        assert "_report_tool_failure" in window, (
            "a tool failure that does not go through the friendly window:\n"
            + window)
        assert "str(exc)" not in window and "str(result)" not in window, (
            "a raw exception is being shown again:\n" + window)


def test_the_failure_handler_quotes_one_line_and_logs_the_rest():
    src = inspect.getsource(M.Ti2RelayoutDialog._report_tool_failure)
    assert "match_printtarg_error" in src, \
        "the editor no longer consults the shared printtarg error table"
    assert "printtarg_said" in src, \
        "the editor no longer reduces the dump to its one useful line"
    assert "log.error" in src, "the full output is no longer logged"
    assert "InfoDialog" in src, \
        "the editor is not using the window that scrolls and caps itself"


# ---------------------------------------------------------------------------
# 4. the custom-paper spin boxes stay inside printtarg's own range (CK-8)
# ---------------------------------------------------------------------------
def test_the_custom_paper_spin_boxes_cannot_ask_for_a_page_printtarg_refuses():
    assert M._CUSTOM_PAPER_MAX_MM <= R.PRINTTARG_PAPER_MAX_MM, (
        f"the spin boxes offer up to {M._CUSTOM_PAPER_MAX_MM} mm and printtarg "
        f"refuses above {R.PRINTTARG_PAPER_MAX_MM} mm")
    assert M._CUSTOM_PAPER_MIN_MM >= R.PRINTTARG_PAPER_MIN_MM
    # …and every widget really uses it, rather than one of them keeping a
    # literal. Four spin boxes, two hidden groups; a literal in any of them is
    # the same defect in a smaller place.
    code = [ln for ln in inspect.getsource(M).splitlines()
            if not ln.lstrip().startswith("#")]
    assert not [ln for ln in code if "setRange(10, 9999)" in ln], (
        "a custom-paper spin box has a literal range again")
    assert sum("setRange(_CUSTOM_PAPER_MIN_MM, _CUSTOM_PAPER_MAX_MM)" in ln
               for ln in code) == 4, (
        "there are not four custom-paper spin boxes taking the shared range "
        "any more — one of them has been given its own number")
    R.check_printtarg_can_lay_out(
        "i1", f"{M._CUSTOM_PAPER_MAX_MM}x{M._CUSTOM_PAPER_MAX_MM}")


def test_the_failure_window_is_not_the_thing_that_fails(qapp, monkeypatch):
    """A window that reports a failure must not raise from inside itself.

    `ui.warning_sign.warn` already learned this and says so at length: it
    catches the constructor and falls back to a parentless box, because three
    suite scaffolds drive these paths with a stand-in `self`. Replacing `warn`
    with `InfoDialog` on the tool-failure paths inherited the duty and, at
    first, not the guard: `tests/test_editor_apply_leaves_no_temp_files.py`
    drives `_save_and_apply` on a `Ti2RelayoutDialog` built through `__new__`,
    and `QDialog.__init__(parent)` answers `RuntimeError: super-class
    __init__() ... was never called` — turning one failure into two.
    """
    from ui import tooltip_button

    built: list = []
    monkeypatch.setattr(tooltip_button._InfoDialog, "exec",
                        lambda self: built.append(self) or 0)

    bare = M.Ti2RelayoutDialog.__new__(M.Ti2RelayoutDialog)

    # The scaffold really is one a QDialog will not take as a parent, or this
    # test proves nothing about the fallback.
    with pytest.raises((TypeError, RuntimeError)):
        tooltip_button.InfoDialog("t", "b", bare)

    bare._report_tool_failure("Render failed", RuntimeError("boom"))
    assert built, "no window was shown at all"
    assert built[0].parent() is None, (
        "the fallback window kept the parent that could not take it")
