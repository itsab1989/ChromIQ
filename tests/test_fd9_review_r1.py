"""The Konica Minolta FD-9 Beta (PR #213, written and contributed by lessbones),
review round 1: one regression test per finding, each failing before its fix.

* F1  a stopped FD-9 result waiting for its end window keeps the chart file
      where it is, and never takes over another chart's Stop or quit;
* F2  a verification's stored chart set aside at Start is not put back while
      the FD-9 reads, and is put back when the FD-9 attempt ends unfiled;
* F4  a missing layout file or session folder is not "could not reach the
      FD-9"; the driver's own "sensor model version" refusal gets its window;
* F5  the FD-9's greying of the layout panel survives a recipe load and the
      panel's own rules;
* F6  with the Beta off, a target's stored FD-9 keys pass through unchanged
      and its meta.json is not rewritten for them;
* F7  another window holding the instrument is said FIRST, in
      M-INSTRUMENT-BUSY;
* the FD-9's name in a chart in any letter case and quoting;
* the user-facing words: the marks are around the patch area, and the version
  checked is the measuring sensor's, not the FD-9's firmware;
* the older native resume path checks the sensor version before anything
  moves (driver audit, section 4).

F3 (stale FD-9 settings with the Beta off) is in
`tests/test_fd9_off_changes_nothing.py`, whose child process builds the real
window from such settings.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
from tests.test_fd9_beta_option import (  # noqa: F401
    _plain_chart,
    fd9_chart,
    tab,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _past_the_preflight(tab, monkeypatch):
    for name in ("_blocked_by_new_run", "_blocked_by_missing_chart_file"):
        monkeypatch.setattr(tab, name, lambda: False)
    monkeypatch.setattr(tab, "_blocked_by_a_misfitting_measurement",
                        lambda params=None: False)
    monkeypatch.setattr(tab, "_verification_guard", lambda: None)
    monkeypatch.setattr(tab, "_confirm_replacing_measurement", lambda: True)


# ---- F1 ----------------------------------------------------------------------
def test_a_waiting_fd9_result_keeps_the_chart_and_never_owns_another_chart(
        tab, fd9_chart, tmp_path):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert tab._file_grp.isEnabled()
    # What `_fd9_result` leaves after a stop answered "Keep measuring".
    tab._fd9_pending = {"chart": str(fd9_chart), "session": "",
                        "staged": str(tmp_path / "x.ti3")}
    tab._fd9_restore_controls()
    assert not tab._file_grp.isEnabled(), (
        "another chart could be loaded over an FD-9 result still waiting for "
        "its end window")
    assert tab.a_measurement_is_running()

    # Should a chart change all the same (another route than the file group),
    # the result belongs to ITS chart, not to the one now loaded.
    plain = _plain_chart(tmp_path)
    tab.set_ti1_path(plain.with_suffix(".ti1"))
    assert not tab.a_measurement_is_running()
    routed = []
    tab._stop_fd9_measurement = lambda: routed.append("fd9")
    tab._confirm_end_of_session = lambda how: None
    tab._on_stop()
    assert routed == [], "a normal chart's Stop went to the FD-9"
    assert tab._readings_before_session() == 0

    # Settling the result gives the file group back.
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._fd9_pending = None
    tab._fd9_restore_controls()
    assert tab._file_grp.isEnabled()


def test_a_discard_after_a_failure_gives_the_chart_file_back(tab, fd9_chart,
                                                             tmp_path):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._fd9_pending = {"chart": str(fd9_chart), "session": "",
                        "staged": str(tmp_path / "x.ti3")}
    tab._fd9_choice = "discard"
    tab._fd9_failed("Operator stopped the FD9 session", True)
    assert tab._fd9_pending is None
    assert tab._file_grp.isEnabled()


# ---- F2 ----------------------------------------------------------------------
def test_the_stored_chart_waits_for_the_fd9_and_comes_back_after_it(
        tab, fd9_chart, monkeypatch, qtbot):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._settings.set("fd9_host", "10.0.0.9")
    put_back = []
    import workflow.verify_chart_snapshot as v
    monkeypatch.setattr(v, "put_back_stored_chart",
                        lambda *a: put_back.append(a))
    _past_the_preflight(tab, monkeypatch)

    def snap():
        tab._replaced_chart = SimpleNamespace(verification="V", set_aside="S")
        return True

    monkeypatch.setattr(tab, "_snapshot_verification_chart", snap)
    import threading
    import ui.fd9_measurement as fm
    gate = threading.Event()

    def slow(*a, **k):
        gate.wait(10)
        raise RuntimeError("Capture failed; evidence preserved: something")

    monkeypatch.setattr(fm, "_measure_chart", slow)
    tab._on_start()
    try:
        assert tab._fd9_live
        assert put_back == [], (
            "the stored chart was put back while the FD-9 still measures")
    finally:
        gate.set()
    qtbot.waitUntil(lambda: not tab._fd9_live, timeout=10000)
    tab._fd9_job.wait(5000)
    assert put_back == [("V", "S")], (
        "an FD-9 attempt that filed nothing must put the stored chart back")
    assert tab._replaced_chart is None


def test_a_waiting_result_keeps_the_record_until_it_is_settled(tab, fd9_chart,
                                                               monkeypatch):
    put_back = []
    import workflow.verify_chart_snapshot as v
    monkeypatch.setattr(v, "put_back_stored_chart",
                        lambda *a: put_back.append(a))
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._replaced_chart = SimpleNamespace(verification="V", set_aside="S")
    tab._fd9_pending = {"chart": str(fd9_chart), "session": "", "staged": ""}
    tab._settle_the_replaced_chart()
    assert put_back == [], "Resume may still file into that date"
    monkeypatch.setattr(tab, "_confirm_end_of_session", lambda how: "discard")
    tab._fd9_end_prompt(tab.END_STOP)
    assert put_back == [("V", "S")]


# ---- F4 ----------------------------------------------------------------------
def test_a_missing_layout_file_is_not_called_a_connection_problem(
        tab, fd9_chart, fd9_windows, monkeypatch):
    fd9_chart.with_suffix(".fd9.json").unlink()
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._settings.set("fd9_host", "10.0.0.9")
    _past_the_preflight(tab, monkeypatch)
    tab._on_start()
    assert [w[0] for w in fd9_windows] == ["M-FD9-FAILED"]


@pytest.mark.parametrize("error,kind", [
    (FileNotFoundError(2, "No such file or directory", "x.fd9.json"), "failed"),
    (PermissionError(13, "Permission denied", "fd9-sessions"), "failed"),
    (FileExistsError(17, "File exists", "fd9-sessions/abc"), "failed"),
    (ConnectionRefusedError(61, "Connection refused"), "connection"),
    (TimeoutError("timed out"), "connection"),
    (OSError(65, "No route to host"), "connection"),
    (RuntimeError("Capture failed; evidence preserved: [Errno 61] Connection "
                  "refused"), "connection"),
    (RuntimeError("Capture failed; evidence preserved: [Errno 2] No such "
                  "file or directory: 'scan.pgm'"), "failed"),
    (RuntimeError("Capture failed; evidence preserved: Sensor model version "
                  "is not supported; no memory reads sent"), "firmware"),
])
def test_an_exception_is_put_in_the_window_its_type_belongs_to(error, kind):
    from ui.fd9_measurement import fd9_exception_kind
    assert fd9_exception_kind(error) == kind


def test_the_drivers_version_refusal_gets_the_version_window(tab, fd9_windows):
    """The vendored driver's words (instrument_model.py) never matched the
    old keyword, so this window could not appear."""
    tab._fd9_explain_error(
        "Capture failed; evidence preserved: Sensor model version is not "
        "supported; no memory reads sent")
    assert [w[0] for w in fd9_windows] == ["M-FD9-WRONG-FIRMWARE"]


def test_a_worker_failure_carries_the_kind_of_its_exception(qtbot, tmp_path):
    from ui.fd9_measurement import FD9Job

    def broken(*a, **k):
        raise FileNotFoundError(2, "No such file or directory", "x.fd9.json")

    job = FD9Job(tmp_path / "c.ti2", None, tmp_path, None, action=broken)
    with qtbot.waitSignal(job.failed, timeout=5000) as got:
        job.start()
    job.wait(5000)
    assert got.args[2] == "failed"


# ---- F5 ----------------------------------------------------------------------
def test_the_fd9_greying_survives_a_recipe_load_and_the_panels_rules(qapp):
    from PyQt6.QtWidgets import QAbstractButton, QAbstractSpinBox, QComboBox
    from ui.dialogs.layout_options_panel import (LayoutOptionsPanel,
                                                 fd9_greyed_reason)
    from workflow.layout_engine.presets import LayoutRecipe
    p = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    try:
        before = {c: c.isEnabled() for c in p._fd9_greyable_controls()}
        p.instr.setCurrentIndex(p.instr.findData("FD9"))
        why = fd9_greyed_reason()
        greyed = list(p._fd9_greyable_controls())
        assert greyed and all(not c.isEnabled() for c in greyed)
        for variant in (dict(use_instrument_margins=False,
                             layout_mode="area_first"),
                        dict(use_instrument_margins=True)):
            p.set_recipe(LayoutRecipe(instrument="FD9", paper="A4",
                                      patch_w_mm=10, **variant))
            live = [c for c in p._fd9_greyable_controls() if c.isEnabled()]
            assert live == [], (
                f"set_recipe({variant}) gave back {len(live)} control(s)")
        # One of the panel's own rules, run while the FD-9 is selected.
        p._sync_instr_margins()
        assert p.clip_width.isEnabled() is False
        assert p.clip_width.toolTip() == why
        # Leaving the FD-9 puts back what the panel's rules want.
        p.instr.setCurrentIndex(p.instr.findData("i1"))
        left = [c for c in p.findChildren(
            (QAbstractSpinBox, QAbstractButton, QComboBox))
            if c.toolTip() == why]
        assert left == []
        assert p.clip_width.isEnabled() == before.get(p.clip_width, True)
    finally:
        p.deleteLater()


# ---- F6 ----------------------------------------------------------------------
class _Store:
    def __init__(self, folder, stored):
        self.dir = folder
        self.id = "run1"
        self.meta = SimpleNamespace(measure_settings=stored)
        self.saved = []

    def load_meta(self):
        return self.meta

    def save_meta(self, meta):
        self.saved.append(dict(meta.measure_settings))


@pytest.fixture
def off_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    from workflow.fd9 import support
    before = support._latched
    support.set_enabled_for_this_process(False)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "off.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()
    t.deleteLater()
    support._latched = before


def test_with_the_beta_off_stored_fd9_keys_pass_through_unchanged(off_tab,
                                                                  tmp_path):
    from workflow.measure_settings import apply, snapshot
    assert not off_tab._fd9_on()
    stored = dict(snapshot(off_tab))
    stored["fd9_condition"] = {"enabled": True, "value": "M2"}
    stored["fd9_resume"] = {"enabled": True, "value": True}
    stored["fd9_research"] = {"enabled": True, "value": False}
    store = _Store(tmp_path, dict(stored))
    apply(off_tab, dict(stored))
    assert off_tab.save_target_settings(store) is False
    assert store.saved == [], "meta.json was rewritten for the FD-9's keys"
    # A real change is still written, and the FD-9's keys go with it.
    off_tab._measure_written_cache().clear()
    store.meta.measure_settings = {k: v for k, v in stored.items()
                                   if k != "fd9_condition"} | {
        "fd9_condition": stored["fd9_condition"]}
    first = next(k for k in stored if not k.startswith("fd9"))
    store.meta.measure_settings[first] = {"enabled": False, "value": "x"}
    assert off_tab.save_target_settings(store) is True
    written = store.saved[-1]
    for key in ("fd9_condition", "fd9_resume", "fd9_research"):
        assert written[key] == stored[key], key


def test_with_the_beta_on_the_tab_writes_its_own_fd9_keys(tab, fd9_chart):
    from workflow.measure_settings import carry_fd9_keys
    wanted = {"a": {"enabled": True}}
    stored = {"fd9_condition": {"enabled": True, "value": "M0"}}
    assert carry_fd9_keys(tab, wanted, stored) is wanted


# ---- F7 ----------------------------------------------------------------------
def test_an_instrument_held_elsewhere_is_said_first_in_the_busy_window(
        tab, fd9_chart, fd9_windows, monkeypatch):
    from core import instrument_lease
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._settings.set("fd9_host", "10.0.0.9")
    asked = []
    _past_the_preflight(tab, monkeypatch)
    monkeypatch.setattr(tab, "_confirm_replacing_measurement",
                        lambda: asked.append("§5") or True)
    monkeypatch.setattr(tab, "_snapshot_verification_chart",
                        lambda: asked.append("snapshot") or True)
    monkeypatch.setattr(tab, "_instrument_busy_window",
                        lambda where: asked.append(("busy", where)))
    class Other:
        pass

    other = Other()
    assert instrument_lease.acquire(other, "Read single patches")
    try:
        tab._on_start()
    finally:
        instrument_lease.release(other)
    assert asked == [("busy", "Read single patches")]
    assert fd9_windows == [] and not tab._fd9_live


# ---- the FD-9's name ---------------------------------------------------------
@pytest.mark.parametrize("raw", ['"fd-9"', "FD-9", '"Konica Minolta FD-9" ',
                                 "'FD-9'", '"KONICA MINOLTA FD-9"',
                                 '"konica minolta fd-9"'])
def test_the_fd9_is_recognised_in_any_case_and_quoting(tmp_path, raw):
    import workflow.fd9.measurement as m
    from workflow.fd9.support import is_fd9_instrument_name
    p = tmp_path / "c.ti2"
    p.write_text(f"CTI2\nTARGET_INSTRUMENT {raw}\nBEGIN_DATA_FORMAT\n",
                 encoding="utf-8")
    m._IS_FD9_CACHE.clear()
    assert m.is_fd9_chart(p)
    assert is_fd9_instrument_name(raw)


@pytest.mark.parametrize("raw", ['"FD-90"', '"i1 Pro FD-9 clone"', '"FD-9\'',
                                 '"GretagMacbeth i1 Pro"'])
def test_other_names_are_still_not_the_fd9(tmp_path, raw):
    import workflow.fd9.measurement as m
    from workflow.fd9.support import is_fd9_instrument_name
    p = tmp_path / "c.ti2"
    p.write_text(f"CTI2\nTARGET_INSTRUMENT {raw}\nBEGIN_DATA_FORMAT\n",
                 encoding="utf-8")
    m._IS_FD9_CACHE.clear()
    assert not m.is_fd9_chart(p)
    assert not is_fd9_instrument_name(raw)


# ---- the words ---------------------------------------------------------------
def _fd9_user_texts():
    from ui.dialogs.layout_options_panel import fd9_greyed_reason
    from ui.fd9_measurement import setup_note
    from ui.tabs.tab_chart import fd9_instrument_bullet
    from workflow import measurement_messages as M
    texts = {"setup": setup_note(), "bullet": fd9_instrument_bullet(),
             "greyed": fd9_greyed_reason()}
    for name in dir(M):
        if name.startswith("M_FD9_"):
            msg = getattr(M, name)
            texts[msg.id] = msg.title + "\n" + msg.body
    return texts


def test_the_marks_are_around_the_patch_area_not_in_the_corners():
    for where, text in _fd9_user_texts().items():
        assert "corners" not in text, where


def test_the_version_checked_is_the_sensors_not_the_firmware():
    texts = _fd9_user_texts()
    for where, text in texts.items():
        assert "firmware 1.0.0.2" not in text, where
    assert "sensor" in texts["M-FD9-WRONG-FIRMWARE"]
    assert "measuring sensor" in texts["setup"]


def test_the_beta_info_names_the_sensor_version(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.tooltip_button import TooltipButton
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "b.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        tips = [b for b in dlg.findChildren(TooltipButton)
                if b._title == "Konica Minolta FD-9 support (beta)"]
        body = tips[0]._body
        assert "measuring sensor reports the version 1.0.0.2" in body
        assert "firmware 1.0.0.2" not in body
        assert "corners" not in body
    finally:
        dlg.deleteLater()


# ---- the older native resume path (driver audit, section 4) -------------------
def test_the_older_native_resume_path_checks_the_sensor_version_first(
        tmp_path, monkeypatch):
    from workflow.fd9.chart import build_chart
    from workflow.fd9.independent import CaptureFailed, capture_layout
    from tests.test_fd9_beta_option import _ti1
    import fd9_independent
    from fd9_independent.motion import Phase
    from fd9_independent.protocol import ProtocolError

    src = _ti1(tmp_path, "RGB", ("R", "G", "B"),
               [[i * 10 % 101, i * 20 % 101, i * 30 % 101] for i in range(24)])
    chart = build_chart(src, tmp_path / "fd9chart", paper="A4", dpi=100,
                        seed=7).ti2_path
    events = []

    class Instrument:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def close(self):
            events.append("close")

        def factory_characterization(self):
            events.append("factory")
            return SimpleNamespace(verified_sections_sha256="a" * 64)

        def save_transcript(self, *a):
            pass

    class Acquisition:
        def __init__(self, *a, **k):
            self.phase = Phase.NEW
            self.raw_samples = []
            self.native_samples = []
            self.completed_native_rows = 0
            self.calibration = b""

        def begin_loading(self):
            events.append("loading")

    def refuse(cls, instrument, **k):
        events.append("model")
        raise ProtocolError(
            "Sensor model version is not supported; no memory reads sent")

    monkeypatch.setattr(fd9_independent, "Instrument", Instrument)
    monkeypatch.setattr("fd9_independent.native_motion.NativeAcquisition",
                        Acquisition)
    monkeypatch.setattr("fd9_independent.instrument_model.InstrumentModel.read",
                        classmethod(refuse))
    with pytest.raises(CaptureFailed, match="Sensor model version"):
        capture_layout(None, chart.with_suffix(".fd9.json"), tmp_path / "s",
                       "test-host", allow_experimental=True,
                       native_factory=True, factory_row_sequencing=False,
                       expected_factory_sha256="a" * 64)
    assert events == ["model", "close"], (
        "the older path must refuse an unknown sensor before anything else")
