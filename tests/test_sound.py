"""#131 Phase 1: the measurement-sound core — folder-driven choice lists,
selection resolution, and the outside-measurement gate. Playback itself
(QSoundEffect) needs an audio backend, so we assert the manager's decisions
(what it would play) rather than actual audio output."""
from __future__ import annotations

import os
import wave

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.sound as S  # noqa: E402


class _Settings:
    def __init__(self, d=None):
        self._d = dict(d or {})

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _wav(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (np.zeros(441) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        w.writeframes(data.tobytes())


def test_bundled_pack_has_every_default():
    """Every event's default sound is present in the shipped pack."""
    s = _Settings()
    for event, stem in S.DEFAULT_CHOICE.items():
        assert stem in S.list_choices(s, event), f"{event} default {stem} missing"
        assert S.resolve_file(s, event) is not None


def _samples(path):
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(float)


def _zero_crossing_rate(s):
    return float(np.mean(np.diff(np.signbit(s)) != 0))


@pytest.mark.parametrize("stem", ["drumroll", "applause"])
def test_percussive_completion_sounds_are_struck_not_hiss(stem):
    """#131 (Knut): the drumroll and applause were synthesised as flat white
    noise, so they sounded like static rather than drum strokes and clapping.
    They are now built from individual strokes/claps — guard both properties:
    a low zero-crossing rate (energy is not spread over the whole spectrum) and
    several distinct onsets (discrete events, not one continuous wash)."""
    from core.resource_path import resource_path
    s = _samples(resource_path("assets/sounds/task-complete") / f"{stem}.wav")
    assert _zero_crossing_rate(s) < 0.35, "still reads as broadband noise"
    win = 441                                    # 10 ms envelope
    env = np.abs(s[:len(s) // win * win].reshape(-1, win)).max(axis=1)
    peaks = ((env[1:-1] > env[:-2]) & (env[1:-1] >= env[2:])
             & (env[1:-1] > 0.25 * env.max())).sum()
    assert peaks >= 8, f"only {peaks} onsets — not a sequence of hits"
    assert np.abs(s).max() < 32767, "must not clip"


def test_choice_lists_start_with_off_and_are_sorted():
    s = _Settings()
    for event in S.ALL_EVENTS:
        choices = S.list_choices(s, event)
        assert choices[0] == S.OFF
        assert choices[1:] == sorted(choices[1:], key=str.lower)


def test_off_selection_resolves_to_none():
    s = _Settings({S._setting_key(S.PATCH_OK): S.OFF})
    assert S.choice_for(s, S.PATCH_OK) == S.OFF
    assert S.resolve_file(s, S.PATCH_OK) is None


def test_unknown_selection_falls_back_to_off():
    s = _Settings({S._setting_key(S.STRIP_OK): "does-not-exist"})
    assert S.choice_for(s, S.STRIP_OK) == S.OFF


def test_user_folder_merges_with_bundled(tmp_path):
    _wav(tmp_path / "measurement-events" / "myclick.wav")
    s = _Settings({"sound_folder": str(tmp_path)})
    choices = S.list_choices(s, S.PATCH_OK)
    assert "myclick" in choices           # user file
    assert "tick" in choices              # bundled default still present
    # A user-selected custom file resolves into the user folder.
    s.set(S._setting_key(S.PATCH_OK), "myclick")
    assert S.resolve_file(s, S.PATCH_OK) == tmp_path / "measurement-events" / "myclick.wav"


def test_missing_user_folder_falls_back_to_bundled(tmp_path):
    s = _Settings({"sound_folder": str(tmp_path / "nope")})
    assert S.sounds_root(s) == S.bundled_sounds_root()


def test_play_gate_blocks_non_completion_outside_measurement():
    """Only completion sounds are allowed when no measurement is running."""
    played = []
    s = _Settings({"sound_enabled": True})
    mgr = S.SoundManager(s)
    # Stub the actual effect so we record intent without an audio backend.
    mgr.play = mgr.play  # keep bound
    mgr._effects = {e: type("E", (), {"play": (lambda self, e=e: played.append(e))})()
                    for e in S.ALL_EVENTS}

    # Not in a measurement: patch/strip events are suppressed…
    mgr._in_measurement = False
    mgr.play(S.PATCH_OK)
    mgr.play(S.STRIP_FAIL)
    assert played == []
    # …but completion sounds are allowed.
    mgr.play(S.MEASUREMENT_FINISHED)
    mgr.play(S.PROFILE_BUILT)
    assert played == [S.MEASUREMENT_FINISHED, S.PROFILE_BUILT]


def test_play_does_nothing_when_disabled():
    played = []
    s = _Settings({"sound_enabled": False})
    mgr = S.SoundManager(s)
    mgr._in_measurement = True
    mgr._effects = {S.PATCH_OK: type("E", (), {"play": lambda self: played.append(1)})()}
    mgr.play(S.PATCH_OK)
    assert played == []


def test_in_measurement_allows_all_events():
    played = []
    s = _Settings({"sound_enabled": True})
    mgr = S.SoundManager(s)
    mgr._in_measurement = True
    mgr._effects = {e: type("E", (), {"play": (lambda self, e=e: played.append(e))})()
                    for e in S.ALL_EVENTS}
    for e in S.ALL_EVENTS:
        mgr.play(e)
    assert set(played) == set(S.ALL_EVENTS)


def test_degrades_silently_without_audio_backend(monkeypatch):
    """If QtMultimedia is unavailable, arm()/play() must no-op, never raise —
    a missing multimedia plugin in a bundle can't break a measurement."""
    monkeypatch.setattr(S, "_QSOUND_EFFECT", None)   # force 'unavailable'
    assert S.audio_available() is False
    s = _Settings({"sound_enabled": True})
    mgr = S.SoundManager(s)
    mgr.arm()                 # would preload — must be a quiet no-op
    mgr._in_measurement = True
    mgr.play(S.PATCH_OK)      # must not raise
    mgr.play(S.MEASUREMENT_FINISHED)
    assert mgr._effects == {}
