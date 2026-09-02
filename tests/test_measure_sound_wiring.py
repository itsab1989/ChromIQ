"""#131 Phase 1: the Measure tab wires the measurement-manager signals to the
right sound events, and the master checkbox persists sound_enabled."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

import core.sound as snd                   # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Emitting a manager signal also fires the tab's real UI handlers (some of
    which open modal dialogs — e.g. instrument disconnected). Make every dialog
    non-blocking so the tests exercise only the sound wiring."""
    from PyQt6.QtWidgets import QDialog, QMessageBox
    monkeypatch.setattr(QDialog, "exec", lambda self: 0, raising=False)
    for name in ("exec", "warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, name,
                            staticmethod(lambda *a, **k: 0), raising=False)


class _Settings:
    def __init__(self, d=None):
        self._d = dict(d or {})

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _make_tab():
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings({"sound_enabled": True, "patch_read_warn_de": 10.0})
    tab = TabMeasure(ArgyllRunner(s), s)
    played: list = []
    # Record BOTH entry points. A window's cue goes through play_window(),
    # which is deliberately not subject to the at-rest gate — patching only
    # play() made this double miss it entirely (2026-07-28). The newer
    # test_window_sounds_actually_play.py records at the effect instead, which
    # is why it does not have this problem.
    tab._sound.play = lambda e: played.append(e)
    tab._sound.play_window = lambda e: played.append(e)
    tab._sound._in_measurement = True                  # pretend a read is live
    return tab, played


def test_patch_sound_routes_by_delta_e():
    tab, played = _make_tab()
    tab._on_patch_sound({"de": 2.0})                   # under warn → OK
    tab._on_patch_sound({"de": 25.0})                  # over warn → looks off
    tab._on_patch_sound({"de": None})                  # unknown → OK
    assert played == [snd.PATCH_OK, snd.PATCH_OUT_OF_TOL, snd.PATCH_OK]


def test_strip_and_error_signals_make_sound():
    tab, played = _make_tab()
    tab._manager.strip_measured.emit({"strip": "A"})
    tab._manager.strip_error.emit("read failed")
    assert played == [snd.STRIP_OK, snd.STRIP_FAIL]


def test_a_disconnect_sounds_at_once():
    """REVERSED by Knut on 2026-07-29, and worth recording both ways.

    The completion audit of 2026-07-28 made this signal silent: it does not open
    a window when it fires, so sounding then put the sound seconds ahead of the
    window it belonged to. He has since ruled the other way — *"the instrument
    sound appearing immediately, and then the instrument error window appearing
    when the error run ends, but then keep the sound also when the window
    appears"* — because hearing at once that something is wrong is worth more
    than the sound and the window arriving together.

    So: a sound now, a window later, and a sound with it. What is NOT restored
    is one sound per log line — see test_a_stream_of_errors_sounds_once.
    """
    tab, played = _make_tab()
    tab._manager.instrument_disconnected.emit()
    assert played == [snd.INSTRUMENT_ERROR]
    assert tab._instrument_disconnected is True, "the flag must still be set"


def test_the_window_that_flag_raises_does_sound():
    """The other half: when that window is finally built, it cues itself."""
    tab, played = _make_tab()
    tab._cue_window("INSTRUMENT_ERROR")
    assert played == [snd.INSTRUMENT_ERROR]


def test_slow_down_text_maps_to_slow_down_sound():
    tab, played = _make_tab()
    tab._on_strip_error_sound("Not enough samples per patch - Slow Down!")
    assert played == [snd.SLOW_DOWN]


def test_measure_finished_plays_completion(monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QDialog
    # measure_finished also drives report-save / scanner-target slots that may
    # open dialogs — make any dialog non-blocking so we test only sound wiring.
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab, played = _make_tab()
    ti3 = tmp_path / "x.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    tab.measure_finished.emit(ti3)
    assert snd.MEASUREMENT_FINISHED in played


def test_checkbox_persists_enabled():
    tab, _ = _make_tab()
    tab._sound_cb.setChecked(False)
    assert tab._settings.get("sound_enabled") is False
    tab._sound_cb.setChecked(True)
    assert tab._settings.get("sound_enabled") is True


def test_the_audio_probe_holds_off_the_collector():
    """#131, 2026-08-03: a gate worker segfaulted inside the first QtMultimedia
    import — a collection ran mid-import and a widget's C++ destructor re-entered
    Python. The probe now defers the sweep across the import.
    """
    import gc
    import inspect

    from core import sound

    src = inspect.getsource(sound._sound_effect_cls)
    assert "gc.disable()" in src and "gc.enable()" in src
    assert "finally:" in src, "the collector must come back even if the import raises"

    # …and it really does come back.
    sound._QSOUND_EFFECT = ...
    was = gc.isenabled()
    try:
        gc.enable()
        sound._sound_effect_cls()
        assert gc.isenabled(), "the collector was left switched off"
    finally:
        if not was:
            gc.disable()


def test_the_probe_leaves_the_collector_off_if_it_was_off():
    """Never switch the collector ON behind the caller's back either."""
    import gc

    from core import sound

    sound._QSOUND_EFFECT = ...
    was = gc.isenabled()
    try:
        gc.disable()
        sound._sound_effect_cls()
        assert not gc.isenabled()
    finally:
        if was:
            gc.enable()


# ---- the switch is engine-only, from the first frame ---------------------
# Knut, beta.128: *"'Play sounds during measurements' was not hidden when
# starting up ChromIQ with the stock argyllcms chartread engine."* ChromIQ stays
# quiet on stock chartread — Argyll beeps for itself there and cannot be
# silenced, so ours would only double it — and the switch is hidden to say so.
# It was hidden by refresh_engine_visibility(), which nothing called until
# Preferences had been opened and closed, so a session that started with the
# engine off showed a switch that did nothing.
@pytest.mark.parametrize("engine,visible", [("argyll", False), ("chromiq", True)])
def test_the_sound_switch_matches_the_engine_at_startup(engine, visible):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings({"sound_enabled": True, "chartread_engine": engine})
    tab = TabMeasure(ArgyllRunner(s), s)
    assert tab._sound_cb.isHidden() is (not visible)
    assert tab._sound_tip.isHidden() is (not visible)


def test_hiding_the_switch_does_not_silence_the_windows():
    """Hidden is not off — unlike the overlay boxes beside it.

    The same switch is the master for ChromIQ's own WINDOW sounds, and those
    do play on stock chartread (Knut, #130 2026-07-28: the "No instrument
    Found" window arriving in silence was a bug). The per-patch and per-strip
    sounds are held back for stock chartread inside Sound.play(), which is
    where that rule belongs — not here.
    """
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings({"sound_enabled": True, "chartread_engine": "argyll"})
    tab = TabMeasure(ArgyllRunner(s), s)
    assert tab._sound_cb.isHidden() is True
    assert s.get("sound_enabled") is True, \
        "hiding the control must not turn window sounds off"


# ---- one strip, one signal — and it used to die on the way ---------------
def test_a_strip_read_reaches_the_tab(monkeypatch):
    """Knut, beta.133, engine + strip mode: no completion sound, no pace figure,
    no "read too fast" window, no overlay — four symptoms, one line.

    ``ev["patches"]`` is the LIST of patches, and the handler did
    ``int(ev.get("patches") or 1)``. That raises, one statement before
    ``strip_measured.emit`` — so every strip died there. His log carries the
    traceback once per strip::

        TypeError: int() argument must be … not 'list'
    """
    tab, played = _make_tab()
    ev = {"event": "strip_read", "strip": "B", "worst_de": 1.2,
          "patches": [{"id": str(i), "loc": f"B{i}", "de": 0.5}
                      for i in range(1, 16)]}

    tab._manager._engine_active = True
    tab._manager._handle_engine_line(__import__("json").dumps(ev),
                                     lambda _l: None)

    assert snd.STRIP_OK in played or snd.SLOW_DOWN in played, \
        "the strip made no sound at all"
    assert tab._manager.readings_this_session == 15, \
        "the patches in the strip must be counted, not int()-ed"


# ---- switching the master on mid-measurement must not silence it ---------
def test_turning_sounds_on_while_measuring_keeps_them_on():
    """Knut, beta.133: *"Enabling of 'Play sounds during measurement' does NOT
    enable the sounds when measuring. Error sound comes on Reading Failure
    window, but when clicking instrument button the sound is no longer
    present."*

    The handler armed the clips and then disarmed — "preload only; not in a
    measurement yet" — which is true before a read and false during one.
    Sound.play() drops everything but completion and window sounds when
    disarmed, which is exactly the shape of what he heard.
    """
    tab, played = _make_tab()
    tab._settings.set("chartread_engine", "chromiq")
    tab._session_live = True
    tab._sound._in_measurement = False           # as if it had been off

    tab._on_sound_toggled(True)

    assert tab._sound._in_measurement is True, \
        "the running measurement was left disarmed"
    tab._on_patch_sound({"de": 1.0})
    assert played == [snd.PATCH_OK]


def test_turning_sounds_on_outside_a_measurement_only_preloads():
    tab, _played = _make_tab()
    tab._session_live = False
    tab._sound._in_measurement = False
    tab._on_sound_toggled(True)
    assert tab._sound._in_measurement is False


@pytest.mark.parametrize("engine,wanted", [("chromiq", True), ("argyll", False)])
def test_the_engine_flag_is_compared_not_cast(engine, wanted):
    """`bool("argyll")` is True. The flag decides whether ChromIQ makes any
    measurement sound at all — on stock chartread it must not, because Argyll
    beeps for itself and cannot be silenced."""
    tab, _played = _make_tab()
    tab._settings.set("chartread_engine", engine)
    assert tab._engine_wanted() is wanted


# ---- Guided and Manual show the same settings ---------------------------
# Knut, beta.138: *"When enabling 'Refine / resume existing measurement' or
# 'Suppress warning messages' in Guided mode, the same checkboxes in Manual mode
# do not follow. 'Show overlay...' checkbox does follow in both directions …
# They all shall be linked between Guided mode and Manual mode."*
@pytest.mark.parametrize("guided,manual", [
    ("_resume_cb", "_m_resume_cb"),
    ("_suppress_cb", "_m_suppress_cb"),
    ("_g_only_measured", "_m_only_measured"),
    ("_g_patch_tile", "_m_patch_tile"),
    # "Show overlay" is deliberately NOT here: it was already linked, by
    # _on_overlay_toggled → _sync_overlay_checkboxes, and ticking it without a
    # measurement on disk opens a window. tests/test_knut_beta134_overlay.py
    # covers that pair.
])
def test_the_paired_checkboxes_follow_each_other(guided, manual):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure

    s = _Settings({"chartread_engine": "chromiq"})
    tab = TabMeasure(ArgyllRunner(s), s)
    a, b = getattr(tab, guided, None), getattr(tab, manual, None)
    assert a is not None and b is not None, f"{guided}/{manual} not built"

    start = b.isChecked()
    a.setChecked(not start)
    assert b.isChecked() is (not start), "Guided did not reach Manual"
    b.setChecked(start)
    assert a.isChecked() is start, "Manual did not reach Guided"


def test_the_tolerance_follows_too():
    """Built from one table into two lists, so it is matched by key rather
    than by attribute name."""
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure

    s = _Settings({"chartread_engine": "chromiq"})
    tab = TabMeasure(ArgyllRunner(s), s)
    g = {o.key: o for o in tab._chartread_opts}["tolerance"]
    m = {o.key: o for o in tab._m_chartread_opts}["tolerance"]

    g.widget.setValue(3.5)
    assert m.widget.value() == 3.5
    m.widget.setValue(1.5)
    assert g.widget.value() == 1.5
