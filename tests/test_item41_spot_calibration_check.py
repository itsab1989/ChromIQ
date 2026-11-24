"""Item 41 (4.3.60): Read single patches says when a calibration was too weak.

ArgyllCMS accepts a white calibration taken with too little light (the
instrument not flat on its white tile): its white check compares the spectral
SHAPE only, normalised at 550 nm. Every reading of that session is then too
light by one factor. A tester's logs show it in 2 of 37 calibrations: a whole
session x1.08 to x1.12 too light, and a yellow read x1.33, then x1.62, then
"Sensor is saturated".

What is pinned here, with sessions built the way spotread -s prints them:

* a session scaled x1.11, x1.33 or x1.62 is caught, ONCE;
* a normal session is not, including a brightened paper read in M0 whose blue
  is well above 100 %;
* a saturated sensor is caught;
* the reading itself is never changed or dropped;
* the window offers "Calibrate again" (spotread's 'k', after leaving a misread
  prompt first) and a way on.

The physics behind the limit (band 530-700 nm, 102 %) is in
workflow/spot_calibration_check.py.
"""
from __future__ import annotations

import math
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox          # noqa: E402

from workflow.spot_read_manager import SpotReadManager, SpotReadParams  # noqa: E402

WL = [380.0 + 10.0 * i for i in range(36)]          # 380..730 nm, spotread's 36 bands


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- spectra a reflective print really gives (fractions) ------------------
def _smooth_step(wl, edge, width, low, high):
    return low + (high - low) / (1.0 + math.exp(-(wl - edge) / width))


def paper_m0(level=0.89, oba=0.30):
    """A brightened paper read in M0: flat at *level* above 500 nm, and its
    brightener's emission on top in the blue (peak at 440 nm)."""
    return [level - 0.25 * math.exp(-((w - 380) / 25.0) ** 2)
            + oba * math.exp(-((w - 440) / 22.0) ** 2) for w in WL]


def yellow():
    return [_smooth_step(w, 505, 12, 0.05, 0.84) for w in WL]


def red():
    return [_smooth_step(w, 595, 12, 0.05, 0.82) for w in WL]


def grey(level=0.45):
    return [level for _ in WL]


def black():
    return [0.025 for _ in WL]


def _y(spec):
    """Luminance on the 0..100 scale (a gaussian stand-in for ybar, centred
    at 555 nm: enough for a test, and the check only uses Y as a fallback)."""
    wts = [math.exp(-((w - 555) / 45.0) ** 2) for w in WL]
    return 100.0 * sum(s * k for s, k in zip(spec, wts)) / sum(wts)


def spotread_lines(spec, k=1.0):
    """What spotread -s prints for one reflective reading of *spec*, read
    after a calibration *k* times too weak (every value x k), in percent."""
    vals = [100.0 * v * k for v in spec]
    y = _y(spec) * k
    lstar = 116.0 * (y / 100.0) ** (1 / 3) - 16.0
    return [
        f"Spectrum from 380.000 to 730.000 nm in {len(WL)} steps",
        ", ".join(f"{v:g}" for v in vals),
        f"Peak value {max(vals):f} at (aprox.) 550.0 nm",
        f" Result is XYZ: {y * 0.96:f} {y:f} {y * 0.82:f}, D50 Lab: "
        f"{lstar:f} 0.000000 0.000000",
        "Hit ESC or Q to exit, instrument switch or any other key to take a reading: ",
    ]


SESSION = [paper_m0(), yellow(), red(), grey(), black(), grey(0.75), paper_m0()]
SESSION_BRIGHT_PAPER = [paper_m0(level=0.93, oba=0.35), yellow(), grey(), black()]


class _StubRunner:
    def __init__(self):
        self.writes: list[str] = []
        self.runs: list = []

    def write_stdin(self, text):
        self.writes.append(text)

    def run(self, tool, args, cwd, **kw):
        self.runs.append((tool, list(args), kw))

    def abort(self):
        pass

    @property
    def is_running(self):
        return False


def _manager(monkeypatch, mode="reflective"):
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    runner = _StubRunner()
    mgr = SpotReadManager(runner)
    got = {"suspect": [], "readings": [], "ended": []}
    mgr.calibration_suspect.connect(lambda v: got["suspect"].append(v))
    mgr.reading_ready.connect(lambda x, l: got["readings"].append((x, l)))
    mgr.session_ended.connect(lambda c: got["ended"].append(c))
    mgr.start(SpotReadParams(mode=mode), lambda _l: None)
    return mgr, runner, got


def _feed(mgr, lines):
    for ln in lines:
        mgr._handle_line(ln, lambda _l: None)


def _read_session(mgr, specs, k=1.0):
    for s in specs:
        _feed(mgr, spotread_lines(s, k))


def _calibrate(mgr):
    _feed(mgr, ["Doing a calibration",
                "Place the instrument on its reflective white reference S/N 1,",
                " and then hit any key to continue,",
                "Calibration complete",
                "Hit ESC or Q to exit, instrument switch or any other key to take a reading: "])


# ---- 1. the command line ---------------------------------------------------
def test_a_reflective_session_asks_for_the_spectrum(qapp):
    m = SpotReadManager.__new__(SpotReadManager)
    assert "-s" in SpotReadManager._build_args(m, SpotReadParams())


@pytest.mark.parametrize("mode", ["emissive", "ambient"])
def test_an_emissive_session_does_not(qapp, mode):
    m = SpotReadManager.__new__(SpotReadManager)
    assert "-s" not in SpotReadManager._build_args(m, SpotReadParams(mode=mode))


def test_a_users_own_spectrum_flag_is_not_doubled(qapp):
    m = SpotReadManager.__new__(SpotReadManager)
    args = SpotReadManager._build_args(m, SpotReadParams(extra_args="-S"))
    assert "-s" not in args and args.count("-S") == 1


def test_an_instrument_without_spectra_starts_again_without_it(qapp, monkeypatch):
    mgr, runner, got = _manager(monkeypatch)
    assert "-s" in runner.runs[0][1]
    _feed(mgr, ["Need spectral information for custom illuminant or observer",
                "and instrument doesn't support it"])
    runner.runs[0][2]["on_finish"](-1)
    QApplication.processEvents()
    assert got["ended"] == [], "the refused start must not end the session"
    assert len(runner.runs) == 2 and "-s" not in runner.runs[1][1]


# ---- 2. a weak calibration is caught, once ---------------------------------
@pytest.mark.parametrize("k", [1.33, 1.62])
def test_a_session_too_light_is_caught_once(qapp, monkeypatch, k):
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, SESSION, k)
    assert len(got["suspect"]) == 1, got["suspect"]
    assert got["suspect"][0].reason == "too_light"
    assert len(got["readings"]) == len(SESSION)


def test_the_tester_x1_11_session_is_caught_on_a_bright_paper(qapp, monkeypatch):
    """x1.11 is caught as soon as a patch whose band reflectance is above
    about 92 % is read: a bright paper (93 %) reads 103 %."""
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, SESSION_BRIGHT_PAPER, 1.11)
    assert len(got["suspect"]) == 1


def test_x1_11_on_a_paper_of_89_percent_is_beyond_the_check(qapp, monkeypatch):
    """The honest limit, pinned so nobody believes otherwise: 89 % x 1.11 is
    99 %, which a well calibrated bright paper can read too. The Calibration
    Complete tip (read the bare paper first) is what covers this case."""
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, SESSION, 1.11)
    assert got["suspect"] == []


def test_the_reading_reaches_the_list_unchanged(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch)
    lines = spotread_lines(yellow(), 1.62)
    _feed(mgr, lines)
    y = float(lines[3].split("XYZ:")[1].split()[1])
    assert got["readings"][0][0][1] == pytest.approx(y)
    assert len(got["suspect"]) == 1


def test_it_speaks_again_after_the_next_calibration_only(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, SESSION, 1.33)
    _read_session(mgr, SESSION, 1.33)
    assert len(got["suspect"]) == 1
    _calibrate(mgr)
    _read_session(mgr, SESSION, 1.0)
    assert len(got["suspect"]) == 1, "a good calibration must stay quiet"
    _calibrate(mgr)
    _read_session(mgr, SESSION, 1.62)
    assert len(got["suspect"]) == 2


# ---- 3. a normal session is not ---------------------------------------------
def test_a_normal_session_is_quiet(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, SESSION + SESSION_BRIGHT_PAPER)
    assert got["suspect"] == []


def test_a_brightened_paper_in_m0_is_quiet(qapp, monkeypatch):
    """A strongly brightened paper in M0 reads far above 100 % in the blue
    (here 128 % at 440 nm): the brightener's emission, not a weak calibration.
    The band starts at 530 nm, past it."""
    spec = paper_m0(level=0.94, oba=0.42)
    assert max(spec) > 1.25
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, [spec, spec])
    assert got["suspect"] == []


def test_an_emissive_reading_is_never_judged(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch, mode="emissive")
    _feed(mgr, [" Result is XYZ: 180.0 200.0 150.0, D50 Lab: 130.0 0.0 0.0"])
    assert got["suspect"] == []


def test_without_a_spectrum_y_is_judged(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch)
    _feed(mgr, [" Result is XYZ: 95.0 99.0 80.0, D50 Lab: 99.6 0.0 0.0"])
    assert got["suspect"] == []
    _feed(mgr, [" Result is XYZ: 104.0 108.0 88.0, D50 Lab: 103.0 0.0 0.0"])
    assert len(got["suspect"]) == 1


# ---- 4. saturation ---------------------------------------------------------
def test_a_saturated_sensor_is_caught_once(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch)
    _read_session(mgr, [yellow()], 1.0)
    _feed(mgr, ["", "Spot read failed due to misread (Sensor is saturated)",
                "Hit Esc or Q to give up, any other key to retry:"])
    assert [v.reason for v in got["suspect"]] == ["saturated"]
    _read_session(mgr, [yellow()], 1.62)
    _feed(mgr, ["Spot read failed due to misread (Sensor is saturated)"])
    assert len(got["suspect"]) == 1


def test_an_ordinary_misread_is_not_a_calibration_fault(qapp, monkeypatch):
    mgr, _r, got = _manager(monkeypatch)
    _feed(mgr, ["Spot read failed due to misread (Inconsistent readings)"])
    assert got["suspect"] == []


# ---- 5. the window ---------------------------------------------------------
from ui.dialogs.spot_read_dialog import SpotReadDialog         # noqa: E402


class _Answering(SpotReadDialog):
    answer = ""

    def _ask(self, box: QMessageBox):
        self.asked.append((box.text(), box.informativeText(),
                           [b.text() for b in box.buttons()]))
        for b in box.buttons():
            if b.text().replace("&", "") == self.answer:
                return b
        return None


def _dialog(monkeypatch, answer):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    s = AppSettings()
    d = _Answering(ArgyllRunner(s), s)
    d.asked = []
    d.answer = answer
    sent: list[str] = []
    monkeypatch.setattr(d._manager._runner, "write_stdin", sent.append)
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    monkeypatch.setattr(d._manager._runner, "run", lambda *a, **k: None)
    d._manager.start(SpotReadParams(), lambda _l: None)
    return d, sent


def test_calibrate_again_sends_the_calibration_key(qapp, monkeypatch):
    d, sent = _dialog(monkeypatch, "Calibrate again")
    _read_session(d._manager, [yellow()], 1.62)
    assert len(d.asked) == 1
    title, body, buttons = d.asked[0]
    assert "lighter than a print can be" in title
    assert "flat on its white tile" in body
    assert buttons == ["Calibrate again", "Carry on measuring"]
    assert sent == ["k"]
    assert len(d._readings) == 1, "the reading stays in the list"
    d.deleteLater()


def test_carry_on_sends_nothing(qapp, monkeypatch):
    d, sent = _dialog(monkeypatch, "Carry on measuring")
    _read_session(d._manager, [yellow(), paper_m0()], 1.62)
    assert len(d.asked) == 1 and sent == []
    assert len(d._readings) == 2
    d.deleteLater()


def test_after_a_saturation_the_retry_prompt_is_left_first(qapp, monkeypatch):
    """spotread waits at "any other key to retry" after a misread: Enter
    leaves it, and the calibration key goes at the ready prompt after."""
    d, sent = _dialog(monkeypatch, "Calibrate again")
    _feed(d._manager, ["Spot read failed due to misread (Sensor is saturated)",
                       "Hit Esc or Q to give up, any other key to retry:"])
    assert "more light than it can measure" in d.asked[0][0]
    assert sent == ["\r"]
    _feed(d._manager, ["Hit ESC or Q to exit, any other key to take a reading: "])
    assert sent == ["\r", "k"]
    d.deleteLater()


def test_the_calibration_complete_window_carries_the_tip(qapp):
    from ui.dialogs.spot_read_dialog import _calibration_tip_html
    assert "read the bare paper first" in _calibration_tip_html()
    import inspect
    assert "_calibration_tip_html()" in inspect.getsource(
        SpotReadDialog._on_calibration_finished)


# ---- 6. review fixes (4.3.60 item 41, fix round) ---------------------------
# S1: only spotread's -s refusal restarts, and only when -s was passed.
def _refuse(mgr, runner, lines):
    _feed(mgr, lines)
    runner.runs[-1][2]["on_finish"](-1)
    QApplication.processEvents()


_REFUSE_SPECTRUM = ["Need spectral information for custom illuminant or observer",
                    "and instrument doesn't support it"]


@pytest.mark.parametrize("mode,lines", [
    # a colorimeter (i1Display) with Mode set to Reflective
    ("reflective", ["Need reflection spot reading capability,",
                    "and instrument doesn't support it"]),
    # Emissive on a reflective-only instrument
    ("emissive", ["Need emissive spot capability",
                  "and instrument doesn't support it"]),
])
def test_another_refusal_ends_the_session_without_a_restart(qapp, monkeypatch,
                                                            mode, lines):
    mgr, runner, got = _manager(monkeypatch, mode=mode)
    _refuse(mgr, runner, lines)
    assert len(runner.runs) == 1, [r[1] for r in runner.runs]
    assert got["ended"] == [-1]


def test_an_ignored_option_note_is_not_a_refusal(qapp, monkeypatch):
    mgr, runner, got = _manager(monkeypatch)
    _feed(mgr, ["Requested high resolution mode (ignored)",
                "and instrument doesn't support it"])
    runner.runs[0][2]["on_finish"](0)
    QApplication.processEvents()
    assert len(runner.runs) == 1 and got["ended"] == [0]


def test_the_spectrum_refusal_restarts_once_only(qapp, monkeypatch):
    mgr, runner, got = _manager(monkeypatch)
    _refuse(mgr, runner, _REFUSE_SPECTRUM)
    assert len(runner.runs) == 2 and "-s" not in runner.runs[1][1]
    _refuse(mgr, runner, _REFUSE_SPECTRUM)       # cannot happen without -s
    assert len(runner.runs) == 2 and got["ended"] == [-1]


def test_no_restart_when_the_spectrum_was_not_asked_for(qapp, monkeypatch):
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    runner = _StubRunner()
    mgr = SpotReadManager(runner)
    ended = []
    mgr.session_ended.connect(ended.append)
    mgr.start(SpotReadParams(spectrum=False), lambda _l: None)
    _refuse(mgr, runner, _REFUSE_SPECTRUM)
    assert len(runner.runs) == 1 and ended == [-1]


def test_a_queued_restart_dies_with_the_window(qapp, monkeypatch):
    """N1: the restart is queued on a zero timer; a window closing in between
    must not leave a spotread nobody owns."""
    mgr, runner, got = _manager(monkeypatch)
    _feed(mgr, _REFUSE_SPECTRUM)
    runner.runs[0][2]["on_finish"](-1)
    runner.forget_run_callbacks = lambda: None
    mgr.detach()
    QApplication.processEvents()
    assert len(runner.runs) == 1


# S2a: a real way to calibrate again, in the window itself.
def test_the_window_has_a_calibrate_button(qapp, monkeypatch):
    d, sent = _dialog(monkeypatch, "Carry on measuring")
    assert not d._cal_btn.isEnabled(), "nothing to calibrate before a session"
    _feed(d._manager, ["Hit ESC or Q to exit, any other key to take a reading: "])
    assert d._cal_btn.isEnabled()
    d._cal_btn.click()
    assert sent == ["k"]
    assert not d._read_btn.isEnabled() and not d._cal_btn.isEnabled()
    d.deleteLater()


def test_the_calibrate_button_leaves_a_misread_prompt_first(qapp, monkeypatch):
    d, sent = _dialog(monkeypatch, "Carry on measuring")
    _feed(d._manager, ["Spot read failed due to misread (Inconsistent readings)",
                       "Hit Esc or Q to give up, any other key to retry:"])
    d._cal_btn.click()
    assert sent == ["\r"]
    _feed(d._manager, ["Hit ESC or Q to exit, any other key to take a reading: "])
    assert sent == ["\r", "k"]
    d.deleteLater()


def test_the_tip_names_the_calibrate_button(qapp):
    from workflow import measurement_messages as M
    from core.i18n import tr
    tip = M.M_SPOT_CAL_TIP.render()[1]
    assert tr("Calibrate") in tip
    assert "stop the session" not in tip, "no help with Skip initial calibration"


# S2b + N3: wording that fits every instrument and the Y fallback.
@pytest.mark.parametrize("msg", ["M_SPOT_CAL_TOO_LIGHT", "M_SPOT_CAL_SATURATED"])
def test_the_advice_fits_every_instrument(qapp, msg):
    from workflow import measurement_messages as M
    body = getattr(M, msg).render(percent="110")[1]
    assert "dial" in body and "white tile" in body
    assert "follow the calibration window" in body
    assert "hold the instrument flat" not in body


def test_the_number_is_not_tied_to_a_wavelength_range(qapp):
    from workflow import measurement_messages as M
    body = M.M_SPOT_CAL_TOO_LIGHT.render(percent="110")[1]
    assert "between green and red" not in body
    assert "perfect white surface" in body


# N2: a pending "Calibrate again" belongs to its own session.
def test_a_pending_recalibration_ends_with_the_session(qapp, monkeypatch):
    d, sent = _dialog(monkeypatch, "Calibrate again")
    _feed(d._manager, ["Spot read failed due to misread (Sensor is saturated)"])
    assert sent == ["\r"] and d._recalibrate_pending
    d._on_session_ended(1)
    assert not d._recalibrate_pending
    _feed(d._manager, ["Hit ESC or Q to exit, any other key to take a reading: "])
    assert sent == ["\r"], "an unasked calibration key"
    d.deleteLater()


# N4: the ready prompt that follows the reading does not hide the warning.
class _FeedsWhileOpen(_Answering):
    def _ask(self, box):
        self._manager._handle_line(
            "Hit ESC or Q to exit, any other key to take a reading: ",
            lambda _l: None)
        self.status_while_open = self._status.text()
        return super()._ask(box)


def test_the_status_keeps_the_warning_while_it_is_open(qapp, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    s = AppSettings()
    d = _FeedsWhileOpen(ArgyllRunner(s), s)
    d.asked, d.answer = [], "Carry on measuring"
    monkeypatch.setattr(d._manager._runner, "write_stdin", lambda t: None)
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    monkeypatch.setattr(d._manager._runner, "run", lambda *a, **k: None)
    d._manager.start(SpotReadParams(), lambda _l: None)
    _feed(d._manager, spotread_lines(yellow(), 1.62)[:4])
    assert "lighter than a print can be" in d.status_while_open
    assert d._status.text() == d._ready_text(), "put back after Carry on"
    d.deleteLater()
