"""R3 (4.3.39): from the SECOND time the same strip is refused with the
driver's "Reading is inconsistent" in one measurement, the Strip Read Failed
window says what that usually means and what helps
(M-STRIP-FAILED-INCONSISTENT-AGAIN, proposed).

jctay (forum 150236), i1Pro 3, fixed-order chart: strip 12 was refused 15
times out of 15. The sentence is the driver's own, the same in the i1Pro /
i1Pro 2, i1Pro 3 and ColorMunki drivers (checked below against the vendored
sources). The window's promise that ChromIQ can finish that strip patch by
patch afterwards is proved on the replay instrument: a strip measurement with
one strip unread, then -p -r starts at that strip's first patch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from workflow import measurement_messages as M

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from test_b1_strip_read_failed_window import _open  # noqa: E402
import strip_nine_fixture as nine  # noqa: E402
from replay_tools import HELPER, ReplaySession  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
INCONS = "Reading is inconsistent"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    monkeypatch.setattr(type(t._manager), "engine_active",
                        property(lambda self: True))
    t._engine_read = {"11": True, "12": False, "13": False}
    t._current_strip_letter = "12"
    monkeypatch.setattr(t._manager, "send_key", lambda k: None)
    monkeypatch.setattr(t._manager, "skip_current_strip", lambda: None)
    monkeypatch.setattr(t, "_arm_key_watchdog", lambda: None)
    monkeypatch.setattr(t, "_on_strip_error_sound", lambda *_a: None)
    t._inconsistent_refusals = {}
    return t


AGAIN = "Strip 12 was refused again for the same reason"


def test_not_the_first_time(tab, monkeypatch):
    seen = _open(tab, monkeypatch, INCONS, False)
    assert "did not agree with each other" in seen["text"]
    assert AGAIN not in seen["text"]


def test_from_the_second_time_the_window_explains(tab, monkeypatch):
    _open(tab, monkeypatch, INCONS, False)
    seen = _open(tab, monkeypatch, INCONS, False)
    t = seen["text"]
    assert AGAIN in t
    assert "a very dark patch sits right next to a very light one" in t
    assert "Patch-by-patch mode" in t and "Refine / resume existing" in t
    assert "Skip Strip" in t
    # and every later time too
    seen = _open(tab, monkeypatch, INCONS, False)
    assert AGAIN in seen["text"]
    # the Measure log says it once
    assert tab._log.toPlainText().count(AGAIN) == 1


def test_per_strip_and_only_for_this_reason(tab, monkeypatch):
    _open(tab, monkeypatch, INCONS, False)
    tab._current_strip_letter = "13"
    seen = _open(tab, monkeypatch, INCONS, False)
    assert "refused again" not in seen["text"]          # 13's first
    tab._current_strip_letter = "12"
    seen = _open(tab, monkeypatch, "Too many patches", False)
    assert "refused again" not in seen["text"]
    seen = _open(tab, monkeypatch, "White calibration reading is inconsistent",
                 False)
    assert "refused again" not in seen["text"]
    seen = _open(tab, monkeypatch, INCONS, False)
    assert AGAIN in seen["text"]


def test_on_the_last_strip_it_names_save_partial(tab, monkeypatch):
    tab._engine_read = {"11": True, "12": False}
    _open(tab, monkeypatch, INCONS, False)
    seen = _open(tab, monkeypatch, INCONS, False)
    i = seen["text"].index("refused again")
    assert "(or Save Partial &amp; Quit when it is the last strip)" in \
        seen["text"][i:]


def test_a_new_measurement_counts_again():
    src = (REPO / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    start = src.index("self._session_live = True\n")
    assert "self._inconsistent_refusals = {}" in src[start:start + 600]


@pytest.mark.parametrize("src,const", [
    ("native/instlib/i1pro.c", "I1PRO_RD_READINCONS"),
    ("native/instlib/i1pro3.c", "I1PRO3_RD_READINCONS"),
    ("native/instlib/munki.c", "MUNKI_RD_READINCONS"),
])
def test_it_is_each_drivers_own_sentence(src, const):
    text = (REPO / src).read_text(encoding="latin-1")
    i = text.index(f"case {const}:")
    assert f'return "{INCONS}";' in text[i:i + 80]


def test_the_text_is_proposed_and_has_no_em_dash():
    assert M.M_STRIP_FAILED_INCONSISTENT_AGAIN.id in M.PROPOSED
    assert "—" not in M.M_STRIP_FAILED_INCONSISTENT_AGAIN.body


@pytest.mark.skipif(not HELPER.exists(), reason="chromiq-chartread helper not built")
def test_patch_by_patch_resume_starts_at_the_missing_strip(tmp_path):
    base = tmp_path / "nine"
    nine.write_chart(base)
    rep = nine.write_replay(tmp_path / "r.txt")
    with ReplaySession(base, rep, extra_args=["-S"]) as s:
        s.wait_event("strip_ready")
        for k in range(1, nine.STRIPS + 1):
            if k == 12:
                continue
            i = s.event_index()
            s.send(cmd="goto", strip=str(k))
            s.wait_event("strip_ready", after=i, strip=str(k))
            i = s.event_index()
            s.send(cmd="swipe")
            s.wait_event("saved", after=i)
        i = s.event_index()
        s.send(cmd="done")
        assert s.wait_event("unread_confirm", after=i)["loc"] == "12A"
        s.send(cmd="yes")
        s.wait_event("done", after=i)
    s2 = ReplaySession(base, rep, extra_args=["-S", "-p", "-r"])
    try:
        ev = s2.wait_event("spot_ready", timeout=10)
        assert (ev["loc"], ev["read"]) == ("12A", False)
    finally:
        s2.proc.kill()
        s2.finish()


def test_the_resume_sentence_says_what_the_engine_does():
    """Review of 4.3.39: -p -r STARTS at the missing patches, then steps on
    to patches already read; the text said ChromIQ asks only for them."""
    body = M.M_STRIP_FAILED_INCONSISTENT_AGAIN.body
    assert "asks only for" not in body
    assert "starts at the patches that are still missing" in body
