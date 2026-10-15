"""M-ENGINE-FELL-BACK lists what stops working when ArgyllCMS takes over.

Knut, #182 6181524471 (2026-10-15): delete the sentence about doubled beeps,
and list what no longer works when stock chartread measures, *"based on
actually what happens in the code"*. Each point of the list rests on a fact
of the code; this file pins those facts, so a change that makes one of them
untrue fails here and sends whoever made it back to the message.

Proved on screen too (4.3.5 beta 7 builder, drive_engine_fell_back.py): the
real Measure tab through the real fallback, with a stand-in chartread.
"""
from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication

from workflow import measurement_messages as M
from workflow.measure_manager import MeasureManager, MeasureParams

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QCoreApplication.instance() or QCoreApplication(sys.argv)


# ---- the text --------------------------------------------------------------
def test_the_beeps_sentence_is_gone_and_the_list_is_there():
    body = M.M_ENGINE_FELL_BACK.body
    assert "double every one" not in body
    assert "—" not in body
    assert "{reason}" in body
    bullets = [ln for ln in body.split("\n") if ln.startswith("•")]
    assert len(bullets) == 7, bullets
    assert "progress" not in body, "stock chartread's reads are counted now"
    for word in ("sounds", "reading speed", "outlines", "read twice",
                 "saved only when", "wrong strip", "Calibrate"):
        assert word in body, word


def test_every_language_carries_the_new_text_and_not_the_old():
    for f in sorted((ROOT / "data" / "i18n").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        assert M.M_ENGINE_FELL_BACK.body in d, f.name
        text = d[M.M_ENGINE_FELL_BACK.body]
        assert text.count("•") == 7 and "{reason}" in text, f.name
        assert not [k for k in d if "double every one of them" in k], f.name


# ---- the facts behind it ---------------------------------------------------
class _Runner:
    def __init__(self):
        self.runs, self.writes = [], []

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.runs.append(dict(tool=str(tool), on_line=on_line,
                              on_finish=on_finish))

    def write_stdin(self, text):
        self.writes.append(text)

    def abort(self):
        pass


def _fallen_back(tmp_path):
    """The real fallback: the engine dies before any event, stock takes over."""
    runner = _Runner()
    mgr = MeasureManager(runner)
    mgr._guided_state = "disabled"
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("", encoding="utf-8")
    fell = []
    mgr.engine_fell_back.connect(fell.append)
    mgr.start(MeasureParams(ti1_path=ti1,
                            engine_helper=Path("/fake/chromiq-chartread")),
              lambda _l: None, lambda _c: None)
    runner.runs[0]["on_line"]("chromiq-chartread: Error - no instrument here")
    runner.runs[0]["on_finish"](1)
    assert fell and runner.runs[-1]["tool"] == "chartread"
    return mgr, runner


#: chartread 3.5.0's own console text (spectro/chartread.c 1539, 1854, 1887,
#: 1909): a menu, a strip read, the wrong-strip and unexpected-reading prompts.
STOCK_LINES = [
    "Ready to read strip pass A",
    " Strip read OK",
    "(Warning) Seem to have read strip pass B rather than A!",
    "There is at least one patch with an very unexpected response! "
    "(DeltaE 91.000000)",
    "Ready to read strip pass B",
]


def test_stock_chartread_feeds_none_of_the_engine_only_signals(tmp_path):
    mgr, runner = _fallen_back(tmp_path)
    assert not mgr.engine_active
    heard = {}
    for name in ("strip_measured", "patch_measured", "patch_ready",
                 "scan_started", "strip_read_twice", "readings_saved",
                 "wrong_strip", "unexpected_response", "session_map"):
        getattr(mgr, name).connect(
            lambda *a, n=name: heard.setdefault(n, []).append(a))
    for line in STOCK_LINES:
        runner.runs[-1]["on_line"](line)
    assert heard == {}
    # …and Calibrate on request is refused for it
    assert mgr.can_calibrate_on_request() is False


def test_the_wrong_strip_and_unexpected_prompts_raise_no_window_on_stock():
    """Stock chartread's own prompts reach the log only. The stock parser
    looks at "very unexpected response" for one thing, the count of a strip
    kept there (review of beta 7), and never raises its window."""
    src = inspect.getsource(MeasureManager._handle_line)
    assert not re.search(r"_WRONG_STRIP_RE\.(search|match|findall)", src)
    for sig in ("wrong_strip", "unexpected_response"):
        assert f"self.{sig}.emit" not in src, sig


def test_the_per_reading_sounds_are_dropped_on_stock_chartread():
    import core.sound as snd

    class _S(dict):
        def get(self, k, d=None):
            return {"sound_enabled": True}.get(k, d)

    m = snd.SoundManager(_S())
    m._in_measurement = True
    m._reading_engine = False
    played = []

    class _Eff:
        def play(self):
            played.append(1)
    for ev in (snd.PATCH_OK, snd.STRIP_OK, snd.SLOW_DOWN):
        m._effects[ev] = _Eff()
        m.play(ev)
    assert played == []


def test_the_tab_silences_its_sounds_on_both_fallbacks():
    from ui.tabs.tab_measure import TabMeasure as T
    for slot in (T._on_engine_fell_back, T._on_engine_fell_back_resumed):
        assert "_silence_for_stock_chartread()" in inspect.getsource(slot)
        assert slot.__doc__, "the docstring must be the first statement"


def test_the_preview_speed_and_progress_hang_on_engine_signals():
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure.TabMeasure._connect_manager_signals) \
        if hasattr(tab_measure.TabMeasure, "_connect_manager_signals") \
        else inspect.getsource(tab_measure)
    for slot, signal in (("_on_strip_measured", "strip_measured"),
                         ("_report_strip_pace", "strip_measured"),
                         ("_on_patch_measured", "patch_measured"),
                         ("_on_patch_ready", "patch_ready"),
                         ("_on_strip_read_twice", "strip_read_twice")):
        assert re.search(rf"{signal}\.connect\(\s*self\.{slot}\)", src), slot
    T = tab_measure.TabMeasure
    for guarded in (T._on_preview_strip_clicked, T._on_preview_patch_clicked,
                    T._set_autosave_banner):
        assert "engine_active" in inspect.getsource(guarded)
