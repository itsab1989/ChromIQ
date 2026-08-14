"""#148: wake the audio device once, before the first real sound needs it.

**What the fault actually is.** Playing one clip several times, a second apart,
only the FIRST was quiet:

    *"the very first one was pretty quiet. then they became louder and better to
    hear for me … the repetitions were the same to my ear."*

So it is a cold start. Qt 6.10's QRtAudioEngine suspends the audio device when
the last voice ends, but the hardware stays warm for a while afterwards — which
is why a sound following another within a second is fine, and why the first
after a silence loses its opening. During a measurement the per-patch cues keep
each other alive; the one that suffers is the first.

Measured with cold plays six seconds apart, one play each:

===== ============ ===================================
Clip  As today     Warmed 200 ms beforehand
===== ============ ===================================
tick  weak         clearly better
thump unchanged    unchanged (120 ms already survives)
===== ============ ===================================

**Why this is safe, where the previous attempt was not.** The withdrawn fix held
a voice that never ended, pinning one CoreAudio stream open for the life of the
app; on an external USB device that stream could die with no way back and take
every later sound with it. A warm-up that *finishes* is an ordinary short sound.
The worst case is that nothing is gained — never that something is lost. That
property is what these tests guard.
"""
from __future__ import annotations

import inspect
import os
import wave

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.sound as snd                              # noqa: E402


class _Settings:
    def __init__(self, **kw):
        self._d = {"sound_enabled": True}
        self._d.update(kw)

    def get(self, k, d=None): return self._d.get(k, d)
    def set(self, k, v): self._d[k] = v


@pytest.fixture
def played(monkeypatch):
    """Record the clips a warm-up starts, without touching real audio."""
    starts: list = []

    class _Eff:
        def __init__(self, *a, **kw):
            self.source = None
            self.volume = 1.0
            self.loops = 1

        def setSource(self, url): self.source = url
        def setVolume(self, v): self.volume = v
        def setLoopCount(self, n): self.loops = n
        def play(self): starts.append(self)
        def stop(self): pass

    monkeypatch.setattr(snd, "_sound_effect_cls", lambda: _Eff)
    return starts


# --- it wakes the device ----------------------------------------------------

def test_warming_plays_a_clip(played):
    snd.warm_up_audio(_Settings())
    assert played, "nothing was played, so the device was never woken"


def test_the_warm_up_is_inaudible(played):
    snd.warm_up_audio(_Settings())
    assert all(e.volume <= 0.05 for e in played), (
        "the user must not hear the warm-up itself")


def test_the_warm_up_clip_ends(played):
    """THE safety property. A clip that never ends pins the audio stream open
    for the life of the app, which is what silenced the reporter's machine."""
    assert all(e.loops == 1 for e in played), (
        "a looping warm-up would recreate the withdrawn fix (#148)")


def test_arming_a_measurement_warms_the_device(played):
    """The first per-patch tick must not be the one that pays for waking the
    device — arming happens well before the first patch is read."""
    m = snd.SoundManager(_Settings())
    m._preload = lambda events: None
    m.arm()
    assert played


def test_sounds_switched_off_never_touches_the_device(played):
    m = snd.SoundManager(_Settings(sound_enabled=False))
    m._preload = lambda events: None
    m.arm()
    assert not played


# --- every format in use ----------------------------------------------------

def test_a_user_sound_in_another_format_is_also_warmed(played, tmp_path):
    """Qt pools its engine per (device, format) and keeps each .wav's own rate,
    so a 44.1 kHz warm-up wakes only the 44.1 kHz engine."""
    root = tmp_path / "sounds"
    (root / "measurement-events").mkdir(parents=True)
    odd = root / "measurement-events" / "mine.wav"
    with wave.open(str(odd), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48_000)
        w.writeframes(b"\0\0" * 4_800)

    s = _Settings(sound_folder=str(root))
    s.set(f"sound_choice_{snd.PATCH_OK}", "mine")
    for e in snd.ALL_EVENTS:
        if e != snd.PATCH_OK:
            s.set(f"sound_choice_{e}", snd.OFF)

    assert (48_000, 2) in snd.formats_in_use(s)
    snd.warm_up_audio(s)
    assert played, "a user sound in another format got no warm-up"


def test_the_warm_up_clip_matches_the_format_it_is_made_for():
    p = snd._warmup_file(48_000, 2)
    assert p is not None
    with wave.open(str(p)) as w:
        assert (w.getframerate(), w.getnchannels()) == (48_000, 2)
        assert w.getnframes() > 0


def test_formats_in_use_survives_an_unreadable_file(tmp_path):
    """A bad .wav in the user's folder must not take the measurement down."""
    root = tmp_path / "sounds"
    (root / "measurement-events").mkdir(parents=True)
    (root / "measurement-events" / "broken.wav").write_bytes(b"not a wav")
    s = _Settings(sound_folder=str(root))
    s.set(f"sound_choice_{snd.PATCH_OK}", "broken")
    snd.formats_in_use(s)          # must not raise


# --- it can never make things worse -----------------------------------------

def test_no_audio_backend_is_a_silent_no_op(monkeypatch):
    monkeypatch.setattr(snd, "_sound_effect_cls", lambda: None)
    snd.warm_up_audio(_Settings())          # must not raise


def test_every_sound_off_warms_nothing(played):
    """Nothing selected means nothing will ever play, so there is nothing to
    wake the device for."""
    s = _Settings()
    for e in snd.ALL_EVENTS:
        s.set(f"sound_choice_{e}", snd.OFF)
    snd.warm_up_audio(s)
    assert not played


def test_a_failing_warm_up_does_not_raise(monkeypatch):
    """It sits on the measurement path; it must never be able to break a read."""
    class _Boom:
        def __init__(self, *a, **kw): raise RuntimeError("no audio today")
    monkeypatch.setattr(snd, "_sound_effect_cls", lambda: _Boom)
    snd.warm_up_audio(_Settings())          # must not raise


def test_no_permanent_voice_anywhere_in_the_module():
    """Belt and braces alongside tests/test_no_permanent_audio_voice.py."""
    assert "Infinite" not in inspect.getsource(snd)
