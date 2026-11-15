"""4.3.37: Refine / resume and "High resolution spectral mode (-H)".

A tester re-read strips P to T of a measurement whose 270 readings had been
taken without -H, with -H ticked. The reader only compares the spectra when it
writes the file (chartread.c `save_ti3`: "The resumed spectral type seems to
have changed!"), so the strips were measured, then the engine stopped; the app
called that a lost connection and continued on stock chartread, which stopped
the same way at the end. The re-read strips were lost.

Now (workflow/resume_resolution.py, TabMeasure._blocked_by_a_resume_resolution):

* Start compares the resolution of the measurement being continued with the
  one this read would give, BEFORE anything is measured, and asks
  (M-RESUME-RESOLUTION): measure as the measurement was taken, for this
  session only, or Cancel;
* both directions (a file with -H continued without it, and the reverse);
* an instrument without a high-resolution mode is never asked about;
* the engine's exit with that sentence is never a lost connection and never
  a reason to fall back (MeasureManager), proved with the REAL helper.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.settings import AppSettings                 # noqa: E402
from workflow import measurement_messages as M        # noqa: E402
from workflow import resume_resolution as rr          # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "helpers"))


def _ti3(path: Path, bands: int, start: float, end: float) -> Path:
    path.write_text(
        'CTI3\n\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n'
        f'SPECTRAL_BANDS "{bands}"\nSPECTRAL_START_NM "{start:f}"\n'
        f'SPECTRAL_END_NM "{end:f}"\n\nNUMBER_OF_FIELDS 2\n'
        "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 A1\nEND_DATA\n", encoding="latin-1")
    return path


STD = (36, 380.0, 730.0)          # Argyll's standard mode, 10 nm
HIGH = (106, 380.0, 730.0)        # its high-resolution mode, 3.333 nm


# ---------------------------------------------------------------------------
# The check
# ---------------------------------------------------------------------------
def test_reads_the_resolution_from_the_header(tmp_path):
    std = rr.read_resolution(_ti3(tmp_path / "s.ti3", *STD))
    high = rr.read_resolution(_ti3(tmp_path / "h.ti3", *HIGH))
    assert std.step_nm == pytest.approx(10.0) and not std.high
    assert high.step_nm == pytest.approx(3.333, abs=0.01) and high.high


@pytest.mark.parametrize("file_res,args,expect", [
    (STD, "-H", (False, True)),           # the tester's case
    (HIGH, "", (True, False)),            # the reverse
    (STD, "", None),
    (HIGH, "-H -T 0.7", None),
])
def test_a_mismatch_in_either_direction(tmp_path, file_res, args, expect):
    ti3 = _ti3(tmp_path / "m.ti3", *file_res)
    mm = rr.resume_mismatch(ti3, args, "X-Rite i1 Pro 2")
    if expect is None:
        assert mm is None
    else:
        assert (mm.file_high, mm.read_high) == expect


@pytest.mark.parametrize("instrument", ["X-Rite i1 Pro 2", "GretagMacbeth i1 Pro",
                                        "X-Rite i1 Pro 3", "X-Rite ColorMunki"])
def test_every_high_resolution_instrument_is_asked(tmp_path, instrument):
    assert rr.resume_mismatch(_ti3(tmp_path / "m.ti3", *STD), "-H",
                              instrument) is not None


@pytest.mark.parametrize("instrument", ["X-Rite DTP20", "Spectrolino",
                                        "X-Rite i1 iSis", "Barbieri Spectro LFP"])
def test_an_instrument_that_ignores_minus_h_is_never_asked(tmp_path, instrument):
    assert rr.resume_mismatch(_ti3(tmp_path / "m.ti3", *STD), "-H",
                              instrument) is None


def test_no_spectra_or_no_file_is_not_asked(tmp_path):
    p = tmp_path / "x.ti3"
    p.write_text("CTI3\nBEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\n",
                 encoding="latin-1")
    assert rr.resume_mismatch(p, "-H", "X-Rite i1 Pro 2") is None
    assert rr.resume_mismatch(None, "-H", "X-Rite i1 Pro 2") is None
    assert rr.resume_mismatch(tmp_path / "missing.ti3", "-H", None) is None


def test_the_session_override_adds_or_removes_only_minus_h():
    assert rr.with_highres("-H -T 0.7", False) == "-T 0.7"
    assert rr.with_highres("-T 0.7", True) == "-T 0.7 -H"
    assert rr.with_highres("-H", True) == "-H"


# ---------------------------------------------------------------------------
# The message and the window
# ---------------------------------------------------------------------------
def test_the_message_is_proposed_and_says_what_and_why():
    assert M.M_RESUME_RESOLUTION.id in M.PROPOSED
    title, body = M.M_RESUME_RESOLUTION.render(
        before="in standard resolution", now="in high resolution",
        option="High resolution spectral mode (-H)", box="Refine / resume")
    assert "another spectral resolution" in title
    assert "the strips you read now would be lost" in body
    assert "Measure in standard resolution" in body
    assert "This applies to this measurement only" in body
    assert "Nothing has been measured or changed yet." in body
    assert "—" not in title + body


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.tabs.tab_measure import TabMeasure
    t = TabMeasure(ArgyllRunner(s), s)
    t._detected_instrument = "X-Rite i1 Pro 2"
    return t


def _answer(monkeypatch, which: str):
    from PyQt6.QtWidgets import QMessageBox
    seen = {}

    def run(box):
        seen["title"] = box.windowTitle()
        seen["text"] = box.informativeText()
        seen["buttons"] = [b.text() for b in box.buttons()]
        for b in box.buttons():
            if (which == "go" and b is box.defaultButton()) or \
                    (which == "cancel" and b is box.escapeButton()):
                b.click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", run)
    return seen


def _with_highres_ticked(tab, monkeypatch, on: bool, ti3: Path):
    from workflow.measure_manager import MeasureParams
    monkeypatch.setattr(tab, "_measurement_to_continue", lambda: ti3)
    fake = MeasureParams(ti1_path=ti3.with_suffix(".ti1"),
                         extra_args="-H" if on else "")
    monkeypatch.setattr(tab, "_collect_guided", lambda: fake)
    monkeypatch.setattr(tab, "_collect_manual", lambda: fake)


def test_cancel_starts_nothing(tab, monkeypatch, tmp_path):
    _with_highres_ticked(tab, monkeypatch, True, _ti3(tmp_path / "c.ti3", *STD))
    seen = _answer(monkeypatch, "cancel")
    tab._session_highres = None
    assert tab._blocked_by_a_resume_resolution() is True
    assert seen["buttons"] == ["Measure in standard resolution", "Cancel"]
    assert tab._session_highres is None
    assert "Measurement not started" in tab._log.toPlainText()


def test_measure_as_before_is_for_this_session_only(tab, monkeypatch, tmp_path):
    _with_highres_ticked(tab, monkeypatch, True, _ti3(tmp_path / "c.ti3", *STD))
    _answer(monkeypatch, "go")
    before = tab._settings.get("chartread.highres") if hasattr(
        tab._settings, "get") else None
    tab._session_highres = None
    assert tab._blocked_by_a_resume_resolution() is False
    assert tab._session_highres is False          # measure without -H
    assert (tab._settings.get("chartread.highres") if hasattr(
        tab._settings, "get") else None) == before


def test_the_reverse_offers_high_resolution(tab, monkeypatch, tmp_path):
    _with_highres_ticked(tab, monkeypatch, False, _ti3(tmp_path / "c.ti3", *HIGH))
    seen = _answer(monkeypatch, "go")
    tab._session_highres = None
    assert tab._blocked_by_a_resume_resolution() is False
    assert seen["buttons"][0] == "Measure in high resolution"
    assert tab._session_highres is True


def test_start_asks_before_anything_is_archived_and_applies_the_choice():
    src = (Path(__file__).resolve().parent.parent / "ui" / "tabs" /
           "tab_measure.py").read_text(encoding="utf-8")
    start = src[src.index("    def _on_start(self) -> None:"):]
    i_cond = start.index("self._blocked_by_a_differing_condition()")
    i_res = start.index("self._blocked_by_a_resume_resolution()")
    i_params = start.index("params = self._collect_params()")
    i_apply = start.index("params.extra_args = with_highres(params.extra_args, _hr)")
    i_archive = start.index("self._confirm_replacing_measurement()")
    assert i_cond < i_res < i_params < i_apply < i_archive


# ---------------------------------------------------------------------------
# The engine's exit with that sentence
# ---------------------------------------------------------------------------
def _manager():
    from workflow.measure_manager import MeasureManager
    s = AppSettings()
    return MeasureManager(ArgyllRunner(s))


def test_never_a_lost_connection_and_never_a_fallback(qapp):
    m = _manager()
    m._engine_active = True
    m._engine_fatal = "communication problem"     # an earlier failure
    m._engine_progress = True
    m._handle_engine_line(
        "chromiq-chartread: Error - The resumed spectral type seems to have "
        "changed!", lambda _l: None)
    assert m._resume_spectral_changed is True
    assert m._engine_should_resume_fallback(1) is False
    m._engine_progress = False
    assert m._engine_should_fall_back(1) is False
    assert "spectral resolution" in m._engine_failure_reason()
    assert "communication" not in m._engine_failure_reason()


def _spectral_ti3(src: Path, dst: Path) -> None:
    """*src* (a .ti3 without spectra) with 36 standard bands added, as a
    measurement taken by a spectral instrument in standard mode."""
    text = src.read_text(encoding="latin-1")
    head, rest = text.split("BEGIN_DATA_FORMAT", 1)
    fmt, data = rest.split("END_DATA_FORMAT", 1)
    names = " ".join(f"SPEC_{380 + 10 * i}" for i in range(36))
    head += ('SPECTRAL_BANDS "36"\nSPECTRAL_START_NM "380.000000"\n'
             'SPECTRAL_END_NM "730.000000"\n')
    nfields = len(fmt.split()) + 36
    head = re.sub(r"NUMBER_OF_FIELDS \d+", f"NUMBER_OF_FIELDS {nfields}", head)
    pre, body = data.split("BEGIN_DATA", 1)
    rows, post = body.split("END_DATA", 1)
    rows = "\n".join((ln + " " + " ".join(["50.0"] * 36)) if ln.strip() else ln
                     for ln in rows.split("\n"))
    dst.write_text(head + "BEGIN_DATA_FORMAT" + fmt.rstrip() + " " + names
                   + "\nEND_DATA_FORMAT" + pre + "BEGIN_DATA" + rows
                   + "END_DATA" + post, encoding="latin-1")


def test_the_real_helper_stops_only_when_it_writes(tmp_path):
    """The mechanism that lost the strips, with the real chromiq-chartread:
    a resume onto spectral readings with readings of another spectral type is
    measured, and the reader stops only when it writes the file. The app's
    manager then names it and does not fall back."""
    from replay_tools import HELPER, ReplaySession, write_replay_script
    if not HELPER.exists():
        pytest.skip("chromiq-chartread helper not built")
    from test_chartread_engine import _make_chart, _quit
    base = _make_chart(tmp_path, randomised=False)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    s = ReplaySession(base, replay)              # strip A, then quit
    s.wait_event("strip_ready")
    s.send(cmd="swipe")
    s.wait_event("saved")
    _quit(s)
    ti3 = base.with_suffix(".ti3")
    assert ti3.exists()
    _spectral_ti3(ti3, ti3)                      # A as a spectral reading
    s2 = ReplaySession(base, replay, extra_args=["-r"])
    ev = s2.wait_event("session_start")
    assert [(x["strip"], x["read"]) for x in ev["strips"]] == [
        ("A", True), ("B", False)]
    s2.wait_event("strip_ready")
    s2.send(cmd="swipe")                         # B is measured...
    try:
        code = s2.finish(timeout=15)             # ...and the write stops it
    except AssertionError:
        code = None
    text = "\n".join(s2.raw_lines)
    assert rr.SPECTRAL_CHANGED_RE.search(text), text[-1500:]
    assert code not in (0,)
    m = _manager()
    m._engine_active = True
    m._engine_progress = True
    m._engine_fatal = "communication problem"
    for ln in s2.raw_lines:
        m._handle_engine_line(ln, lambda _l: None)
    assert m._engine_should_resume_fallback(code or 1) is False


# ---------------------------------------------------------------------------
# M4: high resolution, continued with an instrument without it
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("args", ["", "-H"])
def test_a_high_resolution_file_with_an_instrument_without_it(tmp_path, args):
    mm = rr.resume_mismatch(_ti3(tmp_path / "h.ti3", *HIGH), args,
                            "X-Rite DTP20")
    assert mm is not None and mm.instrument_cannot and mm.file_high


def test_that_window_offers_cancel_only_and_starts_nothing(tab, monkeypatch,
                                                            tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    _with_highres_ticked(tab, monkeypatch, False,
                         _ti3(tmp_path / "c.ti3", *HIGH))
    tab._detected_instrument = "X-Rite DTP20"
    seen = {}

    def run(box):
        seen["name"] = box.objectName()
        seen["buttons"] = [b.text() for b in box.buttons()]
        seen["text"] = box.informativeText()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", run)
    tab._session_highres = None
    assert tab._blocked_by_a_resume_resolution() is True
    assert seen["name"] == "resume_resolution_instrument_window"
    assert seen["buttons"] == ["Cancel"]
    assert "X-Rite DTP20" in seen["text"]
    assert tab._session_highres is None
    assert M.M_RESUME_RESOLUTION_INSTRUMENT.id in M.PROPOSED

