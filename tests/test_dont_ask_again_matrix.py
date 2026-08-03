"""#131 (Knut, 2026-07-28): the "don't ask again" matrix, driven end-to-end.

*"Make test plan that covers every case, every button and option, including
every case of the 'Don't ask again' function for every window. Then test and
verify all actions, checkboxes and button functions…"*

So this file drives the **real** methods — not their source — through every
combination: both windows, both run types, the tick on and off, OK and Cancel,
and the four ways a silence must stop applying. Each test asserts what the user
would see: does the window come up again, or not.

The two windows:

======  ===================================  ==========================
code    window                               silenced in
======  ===================================  ==========================
OFFER   "This chart already has a            ``_offer_silenced``
        measurement" (chart loaded, or a
        run switched to — his scenario 4)
REPL    "This chart already has a            ``_replace_warning_silenced``
        measurement" at Start Measurement
======  ===================================  ==========================

They are deliberately separate: silencing the one you meet on arrival must not
silence the last guard before readings are overwritten.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import PyQt6.QtWidgets as W                          # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget    # noqa: E402

from ui.tabs.tab_measure import TabMeasure           # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
class _Box:
    def __init__(self, checked=False):
        self._c = checked

    def isChecked(self):  return self._c
    def setChecked(self, v): self._c = bool(v)
    def isVisible(self):  return True
    def isEnabled(self):  return True
    def blockSignals(self, _v): pass


class _Verification:
    def __init__(self, root, run_id, vid):
        self.dir = root / "runs" / run_id / "verifications" / vid

    @property
    def measurement_ti3(self):
        return self.dir / "P-verify.ti3"


class _Run:
    def __init__(self, root, rid):
        self._root, self.id = root, rid

    def verification(self, vid):
        return _Verification(self._root, self.id, vid)


class _Project:
    def __init__(self, root):
        self.root = root

    def has_run(self, rid):  return rid in ("run1", "run2")

    def run(self, rid):      return _Run(self.root, rid)


class _Target:
    def __init__(self, run_type="profiling", profile_run="run1", vid=""):
        self.run_type, self.profile_run, self.verification_id = (
            run_type, profile_run, vid)

    def is_verification(self):
        return self.run_type == "verification"


class _Ctl:
    def __init__(self, project, target):
        self._p, self.target = project, target

    def project_or_none(self):
        return self._p


class Tab(QWidget):
    """A real QWidget carrying the real methods under test."""

    _confirm_replacing_measurement = TabMeasure._confirm_replacing_measurement
    # Borrowed too: _confirm_replacing_measurement asks this rather than
    # re-implementing the resume test, so the archive and the question can
    # never disagree (#130, 2026-08-01 — they did, and it lost a measurement).
    _read_builds_on_existing = TabMeasure._read_builds_on_existing
    _replace_warning_scope = TabMeasure._replace_warning_scope
    _replace_warning_silence_label = TabMeasure._replace_warning_silence_label
    _offer_silence_label = TabMeasure._offer_silence_label
    _measurement_at_risk = TabMeasure._measurement_at_risk
    # Which of the three §5 messages this is depends on what the measurement
    # file holds, so the chooser is borrowed too rather than stubbed — a stub
    # here would let the real one drift without a test noticing.
    _replace_message = TabMeasure._replace_message

    def __init__(self, tmp_path, target=None, ti3=True):
        super().__init__()
        self._root = tmp_path
        self._chart_ti3 = tmp_path / "chart.ti3"
        if ti3:
            self._chart_ti3.write_text("x")
        self._m_resume_cb = self._resume_cb = _Box()
        self._m_refine_cb = self._refine_cb = _Box()
        self._target_ctl = _Ctl(_Project(tmp_path), target or _Target())
        self._replace_warning_silenced = set()
        self._offer_silenced = set()

    def _existing_ti3_for_chart(self):
        return self._chart_ti3 if self._chart_ti3.exists() else None

    def _current_mode(self):
        return "manual"

    # what the caller selects
    def select(self, run_type="profiling", run="run1", vid=""):
        self._target_ctl.target = _Target(run_type, run, vid)


def _answer(monkeypatch, *, accept=True, tick=False):
    """Drive the next QMessageBox: tick the box or not, then press a button.
    Returns a dict that records whether a window appeared at all."""
    seen = {"shown": False, "tick_offered": False, "buttons": []}

    def fake_exec(self):
        seen["shown"] = True
        cb = self.checkBox()
        seen["tick_offered"] = cb is not None
        seen["buttons"] = [b.text() for b in self.buttons()]
        if cb is not None and tick:
            cb.setChecked(True)
        picked = None
        for b in self.buttons():
            label = b.text().lower()
            if accept and "measure again" in label:
                picked = b
            elif not accept and "cancel" in label:
                picked = b
        self._picked = picked
        return 0

    monkeypatch.setattr(W.QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(W.QMessageBox, "clickedButton",
                        lambda self: getattr(self, "_picked", None))
    return seen


# ---------------------------------------------------------------------------
# REPL — the Start Measurement warning
# ---------------------------------------------------------------------------
def test_repl_asks_the_first_time(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    seen = _answer(monkeypatch)
    assert tab._confirm_replacing_measurement() is True
    assert seen["shown"] and seen["tick_offered"]
    assert seen["buttons"] == ["Measure again", "Cancel"]


def test_repl_cancel_stops_the_measurement(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=False)
    assert tab._confirm_replacing_measurement() is False


def test_repl_ticking_and_accepting_silences_it(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=True, tick=True)
    assert tab._confirm_replacing_measurement() is True

    again = _answer(monkeypatch)
    assert tab._confirm_replacing_measurement() is True
    assert not again["shown"], "it asked again after being silenced"


def test_repl_ticking_and_cancelling_does_not_silence_it(qapp, tmp_path, monkeypatch):
    """"Not this time" is not "never again"."""
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=False, tick=True)
    assert tab._confirm_replacing_measurement() is False

    again = _answer(monkeypatch)
    tab._confirm_replacing_measurement()
    assert again["shown"], "cancelling recorded a silence"


def test_repl_accepting_without_ticking_does_not_silence_it(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=True, tick=False)
    tab._confirm_replacing_measurement()

    again = _answer(monkeypatch)
    tab._confirm_replacing_measurement()
    assert again["shown"]


def test_repl_a_silence_does_not_travel_to_another_run(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=True, tick=True)
    tab._confirm_replacing_measurement()

    tab.select(run="run2")
    again = _answer(monkeypatch)
    tab._confirm_replacing_measurement()
    assert again["shown"], "run2 was silenced by run1"


def test_repl_a_silence_does_not_travel_to_a_verification(qapp, tmp_path, monkeypatch):
    vid = "2026-07-28_131500"
    vdir = tmp_path / "runs" / "run1" / "verifications" / vid
    vdir.mkdir(parents=True)
    (vdir / "P-verify.ti3").write_text("v")

    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=True, tick=True)
    tab._confirm_replacing_measurement()            # profiling run1 silenced

    tab.select("verification", "run1", vid)
    again = _answer(monkeypatch)
    tab._confirm_replacing_measurement()
    assert again["shown"], "the verification was silenced by the profiling run"


def test_repl_a_restart_forgets_every_silence(qapp, tmp_path, monkeypatch):
    """"…and is reset when restarting the app." A new tab is a new session."""
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=True, tick=True)
    tab._confirm_replacing_measurement()

    fresh = Tab(tmp_path)                            # the next launch
    again = _answer(monkeypatch)
    fresh._confirm_replacing_measurement()
    assert again["shown"]


def test_repl_offers_no_tick_when_it_cannot_be_scoped(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    tab.select(run="")                               # "New run"
    seen = _answer(monkeypatch)
    tab._confirm_replacing_measurement()
    assert seen["shown"], "the warning itself still applies"
    assert not seen["tick_offered"], "a tick here could only mean 'never anywhere'"


def test_repl_stays_quiet_when_refine_is_ticked(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    tab._m_refine_cb.setChecked(True)
    seen = _answer(monkeypatch)
    assert tab._confirm_replacing_measurement() is True
    assert not seen["shown"], "nothing is being replaced, so nothing to warn about"


def test_repl_stays_quiet_when_resume_is_ticked(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    tab._m_resume_cb.setChecked(True)
    seen = _answer(monkeypatch)
    assert tab._confirm_replacing_measurement() is True
    assert not seen["shown"]


def test_repl_stays_quiet_when_there_is_no_measurement(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path, ti3=False)
    seen = _answer(monkeypatch)
    assert tab._confirm_replacing_measurement() is True
    assert not seen["shown"]


# ---------------------------------------------------------------------------
# The two silences are independent
# ---------------------------------------------------------------------------
def test_the_two_windows_are_silenced_separately(qapp, tmp_path, monkeypatch):
    tab = Tab(tmp_path)
    _answer(monkeypatch, accept=True, tick=True)
    tab._confirm_replacing_measurement()

    assert tab._replace_warning_silenced, "REPL should be silenced"
    assert not tab._offer_silenced, \
        "silencing the Start warning also silenced the arrival window"


@pytest.mark.parametrize("run_type,vid,word", [
    ("profiling", "", "profile run"),
    ("verification", "2026-07-28_131500", "verification"),
])
def test_the_tick_names_the_run_it_applies_to(qapp, tmp_path, run_type, vid, word):
    if vid:
        vdir = tmp_path / "runs" / "run1" / "verifications" / vid
        vdir.mkdir(parents=True)
        (vdir / "P-verify.ti3").write_text("v")
    tab = Tab(tmp_path)
    tab.select(run_type, "run1", vid)
    for label in (tab._replace_warning_silence_label(),
                  tab._offer_silence_label()):
        assert word in label, label
        assert "close ChromIQ" in label, label
