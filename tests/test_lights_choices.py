"""The two choices inside the i1Pro 2 and i1Pro 3 lights Beta (2026-11-13):
"what the lights show" (ready light only / ready light and result signals)
and "during a reading" (off / left on), both for the i1Pro 2 only.

The wire side is in tests/test_i1pro2_lights_modes.py. Here: the settings and
their one-time upgrade step, the helper's command line (both off = 4.3.33's,
byte for byte), the manager's handling of the new engine events, where
ChromIQ's result for a strip comes from, and the Preferences rows.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def test_defaults():
    from core.settings import DEFAULTS
    assert DEFAULTS["i1pro2_lights_beta"] is False
    assert DEFAULTS["i1pro2_lights_signals"] is True
    assert DEFAULTS["i1pro2_lights_during_reading"] is False


def _settings(tmp_path, values: dict, schema: int):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    for k, v in values.items():
        s._qs.setValue(k, v)
    return s


@pytest.mark.parametrize("stored", [True, "true"])
def test_a_4_3_33_user_with_the_lights_on_keeps_4_3_33s_lights(
        qapp, tmp_path, stored):
    s = _settings(tmp_path, {"i1pro2_lights_beta": stored}, 33)
    s.migrate()
    assert s.get("i1pro2_lights_signals") is False
    assert s.get("i1pro2_lights_during_reading") is False


@pytest.mark.parametrize("values", [{}, {"i1pro2_lights_beta": False},
                                    {"i1pro2_lights_beta": "false"}])
def test_anyone_else_gets_the_default_signals(qapp, tmp_path, values):
    s = _settings(tmp_path, values, 33)
    s.migrate()
    assert s.get("i1pro2_lights_signals") is True


def test_a_stored_choice_is_never_overwritten(qapp, tmp_path):
    s = _settings(tmp_path, {"i1pro2_lights_beta": True,
                             "i1pro2_lights_signals": True}, 33)
    s.migrate()
    assert s.get("i1pro2_lights_signals") is True


def test_the_upgrade_step_runs_once(qapp, tmp_path):
    """From schema 34 on, an absent key is the default again: switching the
    option on later, or a key that was never written, is not an upgrade."""
    s = _settings(tmp_path, {"i1pro2_lights_beta": True}, 34)
    s.migrate()
    assert s.get("i1pro2_lights_signals") is True


def test_the_upgrade_step_is_logged_as_written_not_dropped(qapp, tmp_path,
                                                          caplog):
    """4.3.34 review nit: the value is WRITTEN, so it is not listed under
    "dropped stale defaults", and migrate() does not return it as dropped."""
    import logging
    s = _settings(tmp_path, {"i1pro2_lights_beta": True}, 33)
    with caplog.at_level(logging.INFO, logger="core.settings"):
        dropped = s.migrate()
    assert not any("i1pro2_lights_signals" in d for d in dropped)
    lines = [r.getMessage() for r in caplog.records
             if "i1pro2_lights_signals" in r.getMessage()]
    assert len(lines) == 1 and "written: i1pro2_lights_signals = false" in lines[0]
    assert "dropped" not in lines[0]


def test_the_comment_does_not_call_firmware_634_a_gate():
    text = (ROOT / "core" / "settings.py").read_text(encoding="utf-8")
    i = text.index('"i1pro2_lights_signals":     True')
    block = " ".join(ln.strip().lstrip("#:").strip() for ln in
                     text[text.rindex("#: Inside that option", 0, i):i].splitlines())
    assert "no firmware is refused" in block
    assert "only (firmware 634" not in block


# ---------------------------------------------------------------------------
# The helper's command line
# ---------------------------------------------------------------------------
class _Runner:
    def __init__(self):
        self.calls, self.courtesy, self.stdin = [], [], []
        self.is_running = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((str(tool), list(args)))

    def set_kill_courtesy(self, line):
        self.courtesy.append(line)

    def write_stdin(self, text):
        self.stdin.append(text)


ALL_CAPS = {"i1pro2_lights", "i1pro3_lights", "lights_signals",
            "lights_during_reading"}


def _args(tmp_path, monkeypatch, *, lights, signals, reading, caps=ALL_CAPS):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps",
                        lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port",
                        lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights,
                      engine_lights_signals=signals,
                      engine_lights_during_reading=reading)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1]


@pytest.mark.parametrize("signals,reading", [(False, False), (True, False),
                                             (False, True), (True, True)])
def test_with_the_option_off_the_choices_change_nothing(
        qapp, tmp_path, monkeypatch, signals, reading):
    base = _args(tmp_path, monkeypatch, lights=False, signals=False,
                 reading=False)
    assert _args(tmp_path, monkeypatch, lights=False, signals=signals,
                 reading=reading) == base
    assert not any(a.startswith("--lights") or a == "--i1pro2-lights"
                   for a in base)


def test_both_choices_off_is_4_3_33s_command_line(qapp, tmp_path, monkeypatch):
    on = _args(tmp_path, monkeypatch, lights=True, signals=False, reading=False)
    assert on.count("--i1pro2-lights") == 1
    assert not any(a.startswith("--lights-") for a in on)


def test_each_choice_adds_exactly_its_flag(qapp, tmp_path, monkeypatch):
    base = _args(tmp_path, monkeypatch, lights=True, signals=False,
                 reading=False)
    sig = _args(tmp_path, monkeypatch, lights=True, signals=True,
                reading=False)
    rd = _args(tmp_path, monkeypatch, lights=True, signals=False, reading=True)
    assert [a for a in sig if a != "--lights-signals"] == base
    assert [a for a in rd if a != "--lights-during-reading"] == base


def test_a_helper_that_does_not_know_a_choice_is_not_given_it(
        qapp, tmp_path, monkeypatch):
    args = _args(tmp_path, monkeypatch, lights=True, signals=True,
                 reading=True, caps={"i1pro2_lights"})
    assert "--i1pro2-lights" in args
    assert not any(a.startswith("--lights-") for a in args)


def test_the_measure_tab_reads_both_choices_at_every_start():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    assert 'self._settings.get("i1pro2_lights_signals", True))' in src
    assert 'self._settings.get("i1pro2_lights_during_reading", False))' in src


# ---------------------------------------------------------------------------
# The manager: events and ChromIQ's result for a strip
# ---------------------------------------------------------------------------
def _manager():
    from workflow.measure_manager import MeasureManager
    runner = _Runner()
    return MeasureManager(runner), runner


@pytest.mark.parametrize("signals,reading,needles", [
    (False, "off", ["shows white while it waits"]),
    (True, "off", ["softly pulsing white", "green twice", "red twice",
                   "calibrates or measures, its lights are off"]),
    (False, "on", ["no off command before a", "dims its lights by",
                   "except the first reading after connecting"]),
    (True, "on", ["no off command before a", "green twice",
                  "While it calibrates, its lights are off"]),
])
def test_the_session_line_says_what_was_chosen(qapp, signals, reading, needles):
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro2",
         "signals": signals, "during_reading": reading,
         "firmware": -1}), lines.append)
    assert len(lines) == 1
    for n in needles:
        assert n in lines[0], n
    assert "—" not in lines[0]


@pytest.mark.parametrize("fw", [600, 634, 700])
def test_the_firmware_is_said_with_either_choice(qapp, fw):
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro2",
         "signals": True, "during_reading": "off", "firmware": fw}),
        lines.append)
    assert len(lines) == 2
    assert f"firmware {fw}." in lines[1] and "firmware 634" in lines[1]


def test_no_firmware_line_with_both_choices_off(qapp):
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro2",
         "signals": False, "during_reading": "off", "firmware": 634}),
        lines.append)
    assert len(lines) == 1


@pytest.mark.parametrize("sent,needle", [("green2", "green twice"),
                                         ("red2", "red twice"),
                                         ("pulse", None), ("off_slow", None),
                                         ("white", None), ("off_now", None)])
def test_each_sent_program(qapp, sent, needle):
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps({"event": "lights", "sent": sent}),
                          lines.append)
    if needle is None:
        assert lines == []
    else:
        assert len(lines) == 1 and needle in lines[0]
    assert m.lights_active is False      # never read as a session event


def test_unknown_off_keeps_the_marker(qapp):
    m, runner = _manager()
    lines = []
    m._handle_engine_line(json.dumps({"event": "lights", "state": "unknown"}),
                          lines.append)
    assert len(lines) == 1 and "unplug the instrument" in lines[0]
    assert m._lights_failed is True
    assert runner.courtesy == [None]


def _owed(m, n=7):
    m._handle_engine_line(json.dumps({"event": "lights_owed", "n": n}),
                          lambda _l: None)


def _results(runner):
    return [json.loads(t) for t in runner.stdin if "lights_result" in t]


def test_the_verdict_goes_out_once_with_the_strip_number(qapp):
    m, runner = _manager()
    _owed(m, 7)
    m.lights_strip_verdict(too_fast=False)
    m.lights_strip_verdict(too_fast=False)
    assert _results(runner) == [{"cmd": "lights_result", "n": "7",
                                 "result": "good"}]


def test_too_fast_is_red(qapp):
    m, runner = _manager()
    _owed(m, 3)
    m.lights_strip_verdict(too_fast=True)
    assert _results(runner) == [{"cmd": "lights_result", "n": "3",
                                 "result": "bad"}]


def test_nothing_is_sent_when_nothing_is_owed(qapp):
    """Stock chartread, the choice off, "I read strip B": the
    engine never says lights_owed, so the tab's verdict sends nothing."""
    m, runner = _manager()
    m.lights_strip_verdict(too_fast=False)
    assert _results(runner) == []


def test_a_strip_the_engine_flagged_is_red_before_any_window(qapp):
    m, runner = _manager()
    _owed(m, 4)
    seen = []
    m.strip_measured.connect(lambda ev: seen.append(_results(runner)))
    m._handle_engine_line(json.dumps(
        {"event": "strip_read", "strip": "A", "misaligned": 1,
         "patches": []}), lambda _l: None)
    # red went out before the tab heard of the strip
    assert seen and seen[0] == [{"cmd": "lights_result", "n": "4",
                                 "result": "bad"}]
    m.lights_strip_verdict(too_fast=False)       # the tab's cue: nothing more
    assert len(_results(runner)) == 1


def test_the_strip_cue_gives_the_verdict_even_with_sounds_off():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    body = src[src.index("    def _play_strip_cue(self, *, too_fast: bool)"):]
    body = body[:body.index("\n    def ")]
    assert body.index("lights_strip_verdict") < body.index(
        'if getattr(self, "_sound", None) is None:')


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------
@pytest.fixture
def dialog(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    yield dlg, s
    dlg.deleteLater()


def test_the_rows_are_greyed_until_the_lights_are_on(dialog):
    dlg, _s = dialog
    assert dlg._lights_signals_combo.isEnabled() is False
    assert dlg._lights_reading_combo.isEnabled() is False
    assert dlg._lights_signals_combo.currentData() is True
    assert dlg._lights_reading_combo.currentData() is False
    dlg._i1pro2_lights_check.setChecked(True)
    assert dlg._lights_signals_combo.isEnabled() is True
    assert dlg._lights_reading_combo.isEnabled() is True


def test_the_items_say_which_is_4_3_33(dialog):
    dlg, _s = dialog
    sig = [dlg._lights_signals_combo.itemText(i) for i in range(2)]
    rd = [dlg._lights_reading_combo.itemText(i) for i in range(2)]
    assert "4.3.33" in sig[0] and "green / red" in sig[1]
    assert "4.3.33" in rd[0] and "i1Profiler" in rd[1]
    # 2026-11-14: both choices apply to the i1Pro 2 and the i1Pro 3, so the
    # labels name no instrument; item 0 says what it means on an i1Pro 2.
    assert dlg._lights_signals_label.text() == "What the lights show:"
    assert dlg._lights_reading_label.text() == "During a reading:"
    assert "i1Pro 2: ready light only" in sig[0]
    for t in sig + rd:
        assert "—" not in t


def test_both_choices_are_saved(dialog):
    dlg, s = dialog
    dlg._i1pro2_lights_check.setChecked(True)
    dlg._lights_signals_combo.setCurrentIndex(0)
    dlg._lights_reading_combo.setCurrentIndex(1)
    dlg._save_and_close()
    assert s.get("i1pro2_lights_signals") is False
    assert s.get("i1pro2_lights_during_reading") is True


# ---------------------------------------------------------------------------
# The i1Pro 3 (2026-11-14): the same two choices, its own words
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("signals,reading,needles,absent", [
    (False, "off", ["green twice after every reading the instrument took",
                    "whether ChromIQ accepts it is shown on screen",
                    "calibrates or measures, its lights are off"],
     ["ChromIQ accepted"]),
    (True, "off", ["slowly blinking white", "green twice when ChromIQ "
                   "accepted it", "red twice", "calibrates or measures, its "
                   "lights are off"], ["no off command"]),
    (False, "on", ["no off command before a", "switches its lights off by "
                   "itself", "green twice, and red twice when it could not "
                   "take one", "While it calibrates, its lights are off"],
     ["ChromIQ accepted", "except the first reading"]),
    (True, "on", ["no off command before a", "green twice when ChromIQ "
                  "accepted it", "While it calibrates, its lights are off"],
     ["except the first reading"]),
])
def test_the_i1pro3_session_line_says_what_was_chosen(qapp, signals, reading,
                                                      needles, absent):
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro3",
         "signals": signals, "during_reading": reading, "firmware": -1}),
        lines.append)
    assert len(lines) == 1 and "i1Pro 3" in lines[0]
    for n in needles:
        assert n in lines[0], n
    for n in absent:
        assert n not in lines[0], n
    assert "\u2014" not in lines[0]


def test_an_older_helpers_i1pro3_event_reads_as_both_choices_off(qapp):
    """A 4.3.34 helper said only "instrument": "i1pro3" and firmware -1."""
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro3"}),
        lines.append)
    assert len(lines) == 1
    assert "green twice after every reading the instrument took" in lines[0]


@pytest.mark.parametrize("fw,shown", [(123, "1.23"), (200, "2.00")])
def test_the_i1pro3_firmware_is_said_with_either_choice(qapp, fw, shown):
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro3",
         "signals": False, "during_reading": "on", "firmware": fw}),
        lines.append)
    assert len(lines) == 2
    assert f"firmware {shown}." in lines[1] and "634" not in lines[1]
    m2, _r2 = _manager()
    lines2 = []
    m2._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro3",
         "signals": False, "during_reading": "off", "firmware": fw}),
        lines2.append)
    assert len(lines2) == 1          # both off: as 4.3.34, no firmware line


@pytest.mark.parametrize("sent,needle", [("green2", "green twice"),
                                         ("red2", "red twice"),
                                         ("ready", None),
                                         ("instrument_green2", None),
                                         ("instrument_red2", None)])
def test_each_sent_i1pro3_pattern(qapp, sent, needle):
    """green2/red2 are ChromIQ's verdict (result signals); the driver's own
    verdict of "as in 4.3.33" goes to the app log only, as in 4.3.34."""
    m, _r = _manager()
    lines = []
    m._handle_engine_line(json.dumps({"event": "lights", "sent": sent}),
                          lines.append)
    if needle is None:
        assert lines == []
    else:
        assert len(lines) == 1 and needle in lines[0]


def test_unknown_off_on_an_i1pro3_promises_no_reminder(qapp):
    m, runner = _manager()
    lines = []
    m._handle_engine_line(json.dumps(
        {"event": "lights", "active": True, "instrument": "i1pro3"}),
        lambda _l: None)
    m._handle_engine_line(json.dumps({"event": "lights", "state": "unknown"}),
                          lines.append)
    assert len(lines) == 1 and "unplug it and plug it back in" in lines[0]
    assert "reminds you" not in lines[0]
    assert m._lights_failed is True and m._lights_marker_live is False
