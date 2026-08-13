"""#148: short sounds must not be swallowed by the audio device waking up.

The bug, in one sentence: Qt 6.10 rewrote ``QSoundEffect`` onto an engine
(``qrtaudioengine.cpp``) that suspends the audio device the moment the last
voice finishes and resumes it for the next sound — so every sound pays a device
start-up, and anything shorter than that is never heard. On the reporter's 2018
Intel Mac that window was about a quarter of a second, which silenced eight of
the twenty sounds in the pack outright (``tick`` is 8 ms) and stripped the
attack off the rest.

The cure is a voice that never ends, so ``m_voices`` is never empty and the
device is never suspended.

**What these tests can and cannot prove.** They cannot prove a sound came out of
a speaker — no test can, on a machine with no loopback device. What they prove
is the invariant the fix rests on: *whenever ChromIQ is in a state where a sound
could play, the device is being held awake*, and the holds are balanced so it is
released again afterwards. The speaker end was confirmed by ear
(#148, 2026-08-14): ``tick`` went from "very quiet" to "clear" with the hold in
place.
"""
from __future__ import annotations

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
def keeper(monkeypatch):
    """A fresh keep-alive whose voices are recorded instead of played, so the
    reference counting and the linger can be tested without audio hardware."""
    started: list = []

    class _Eff:
        def __init__(self, *a, **kw):
            self.playing = False
            self.loops = 1
            self.volume = 1.0
            self.source = None

        class Loop:
            Infinite = type("E", (), {"value": -2})()

        def setSource(self, url): self.source = url
        def setLoopCount(self, n): self.loops = n
        def setVolume(self, v): self.volume = v
        def play(self): self.playing = True; started.append(self)
        def stop(self): self.playing = False

    _Eff.Loop = _Eff.Loop
    monkeypatch.setattr(snd, "_sound_effect_cls", lambda: _Eff)
    k = snd._AudioDeviceKeepAlive()
    monkeypatch.setattr(snd, "_KEEP_ALIVE", k)
    k.started = started
    return k


# --- the invariant ----------------------------------------------------------

def test_arming_a_measurement_holds_the_device_awake(keeper):
    """The per-patch cues are the shortest sounds in the app, so the device has
    to be awake before the first patch, not after it."""
    m = snd.SoundManager(_Settings())
    m._preload = lambda events: None
    assert not keeper.is_holding()
    m.arm()
    assert keeper.is_holding(), "the device was left asleep during a measurement"


def test_the_keepalive_voice_loops_for_ever(keeper):
    """A voice that ends lets the engine suspend the device again — which is
    the whole bug. It must loop, not play once."""
    snd.hold_audio_device(_Settings())
    assert keeper.started, "no keep-alive voice was started"
    eff = keeper.started[0]
    assert eff.playing
    assert eff.loops == -2, "the keep-alive must loop for ever"
    assert eff.volume <= 0.05, "the keep-alive must be inaudible"


def test_sounds_switched_off_never_touches_the_audio_device(keeper):
    """With the master switch off ChromIQ makes no sound, so it has no business
    holding the audio device open."""
    m = snd.SoundManager(_Settings(sound_enabled=False))
    m.arm()
    assert not keeper.is_holding()


# --- balance ----------------------------------------------------------------

def test_disarm_lingers_rather_than_releasing_at_once(keeper):
    """The instrument windows and the completion sound come *after* the read
    ends. Releasing the device on disarm would clip exactly those."""
    m = snd.SoundManager(_Settings())
    m._preload = lambda events: None
    m.arm()
    m.disarm()
    assert keeper.is_holding(), "the device was dropped before the run-out sounds"
    keeper.release(linger_ms=0)          # what the timer eventually does
    assert not keeper.is_holding()


def test_two_holders_do_not_release_each_other(keeper):
    """The Measure tab and a profile build can overlap. The device must survive
    until the last of them is done."""
    s = _Settings()
    snd.hold_audio_device(s)
    snd.hold_audio_device(s)
    snd.release_audio_device(linger_ms=0)
    assert keeper.is_holding(), "one holder released another holder's device"
    snd.release_audio_device(linger_ms=0)
    assert not keeper.is_holding()


def test_a_hold_during_the_linger_cancels_it(keeper):
    """Measurement ends, a build starts inside the 30 s linger. The linger must
    not then fire and pull the device out from under the build.

    This is why the linger is a generation counter and not a QTimer we own:
    cancelling by dropping our reference to the timer would destroy it from
    inside its own timeout handler.
    """
    s = _Settings()
    snd.hold_audio_device(s)
    snd.release_audio_device(linger_ms=60_000)   # linger now in flight
    snd.hold_audio_device(s)                     # someone takes it again
    keeper._stop_after_linger(1)                 # the stale linger fires
    assert keeper.is_holding(), "a stale linger released a live hold"


def test_arming_twice_takes_only_one_hold(keeper):
    """arm() is reached from more than one place; a double arm followed by one
    disarm must not strand the device open for ever."""
    m = snd.SoundManager(_Settings())
    m._preload = lambda events: None
    m.arm()
    m.arm()
    m.disarm()
    keeper.release(linger_ms=0)
    assert not keeper.is_holding()


# --- every format in use, not just ours -------------------------------------

def test_a_user_sound_in_another_format_is_also_covered(keeper, tmp_path,
                                                        monkeypatch):
    """Qt pools its audio engine per (device, format) and keeps each .wav's own
    sample rate, so a 44.1 kHz keep-alive holds open only the 44.1 kHz engine.
    A user's own 48 kHz file would otherwise still be clipped."""
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
    snd.hold_audio_device(s)
    assert (48_000, 2) in keeper._effects, (
        "a user sound in another format got no keep-alive, so its engine "
        "still suspends between sounds")


def test_formats_in_use_survives_an_unreadable_file(tmp_path):
    """A sound we cannot parse is one Qt cannot play either — it must be
    skipped, never raised, or a bad file in the user's folder would take the
    measurement down with it."""
    root = tmp_path / "sounds"
    (root / "measurement-events").mkdir(parents=True)
    (root / "measurement-events" / "broken.wav").write_bytes(b"not a wav")
    s = _Settings(sound_folder=str(root))
    s.set(f"sound_choice_{snd.PATCH_OK}", "broken")
    snd.formats_in_use(s)          # must not raise


def test_no_audio_backend_is_a_silent_no_op(monkeypatch):
    """On a build with no QtMultimedia the whole layer degrades to nothing —
    holding the device included."""
    monkeypatch.setattr(snd, "_sound_effect_cls", lambda: None)
    k = snd._AudioDeviceKeepAlive()
    monkeypatch.setattr(snd, "_KEEP_ALIVE", k)
    snd.hold_audio_device(_Settings())        # must not raise
    assert not k.is_holding()


def test_the_keepalive_clip_matches_the_format_it_is_made_for():
    """The clip only holds open the engine whose format it shares, so it has to
    be written at exactly the requested rate and channel count."""
    p = snd._silence_file(48_000, 2)
    assert p is not None
    with wave.open(str(p)) as w:
        assert (w.getframerate(), w.getnchannels()) == (48_000, 2)
        assert w.getnframes() > 0
