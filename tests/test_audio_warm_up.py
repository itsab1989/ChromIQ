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

Measured here with cold plays six seconds apart, one play each: ``tick`` (8 ms)
went from weak to clearly better, ``thump`` (120 ms) was unaffected either way —
this machine's window is only a few milliseconds.

**Knut then measured the window itself, on the hardware where it is severe, and
settled which end is lost.** With a first, too-short warm-up in place:

    *"'bell', 'ding-hi', 'ding', 'chime', 'buzz', 'bump' are cut off, so only a
    faint ending is heard."*

Only the ending survives, so it is the BEGINNING that goes — head truncation,
not tail. And the size falls out of which clips survived: ``bump`` (140 ms) was
only just audible, *"cut off closest to the sound's end, so a very small tick is
heard"*, while ``thump`` (120 ms), ``click`` (12 ms) and ``tick`` (8 ms) were
silent altogether. So roughly 120-140 ms was being swallowed, and he proposed a
startup time "about the length of the bump sound (maybe rounding up to a nice
number)". :data:`core.sound.WARMUP_LEAD_MS` is that, doubled.

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
    """Sounds on, and the warm-up ON — because it is now OFF by default.

    Switching it on here is deliberate: the tests below are about what the
    warm-up does WHEN ASKED FOR. That it is not asked for unless the user says
    so is the subject of its own section at the end of this file, which is the
    more important property of the two.
    """

    def __init__(self, **kw):
        self._d = {"sound_enabled": True, "sound_warm_up_device": True}
        self._d.update(kw)

    def get(self, k, d=None): return self._d.get(k, d)
    def set(self, k, v): self._d[k] = v


@pytest.fixture
def played(monkeypatch):
    """Record the clips a warm-up starts, without touching real audio.

    The warm-up clips are cached module-wide — deliberately, because building
    one costs an asynchronous load and a warm-up that is still loading is a
    warm-up that does not warm. The cache therefore has to be cleared between
    tests, or one test's recorder keeps catching the next test's plays.
    """
    monkeypatch.setattr(snd, "_WARMUP_EFFECTS", {})
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


def test_the_warm_up_clip_is_built_once_and_reused(played, monkeypatch):
    """``setSource`` is asynchronous, so a warm-up built at the moment it is
    needed is still loading when the real sound is due — which is exactly why
    the first attempt at this left Knut's short sounds cut off. Building them
    ahead of time is the point, so they must not be rebuilt on every play."""
    s = _Settings()
    snd.preload_warm_up(s)
    built = dict(snd._WARMUP_EFFECTS)
    assert built, "preloading built nothing"
    assert not played, "preloading must not make a sound"
    snd.warm_up_audio(s)
    snd.warm_up_audio(s)
    assert snd._WARMUP_EFFECTS == built, "the clips were rebuilt instead of reused"
    assert len(played) == 2 * len(built), "each warm-up should play each clip once"


def test_the_lead_time_covers_the_measured_window():
    """Knut measured roughly 120-140 ms being swallowed: ``bump`` (140 ms) only
    just audible, ``thump`` (120 ms) silent. The lead has to clear that with
    room to spare on hardware we cannot test."""
    assert snd.WARMUP_LEAD_MS >= 280, snd.WARMUP_LEAD_MS


def test_the_warm_up_outlasts_the_lead():
    """The clip must still be playing when the real sound starts, so the device
    is continuously busy across the join and cannot doze in between."""
    assert snd._WARMUP_SECONDS * 1000 > snd.WARMUP_LEAD_MS


# --- and it does nothing at all unless the user asks (#148, round three) -----
#
# Knut, on the beta carrying the warm-up: *"No sounds what so ever … you have
# messed up the sounds for all events, all messages, all measurements, button
# click on instrument, and all sounds in preferences sounds tab."* The version
# without it worked. It runs in exactly the two places he reports dead — arming
# a measurement, and every press of Play in Preferences — and it is the only
# audio change between the two versions.
#
# Twice now a change meant to make the first sound louder has instead made every
# sound disappear on his machine, and neither could be reproduced on any machine
# here. So the rule these tests hold the code to is blunt: by default ChromIQ
# does not touch the audio device before playing a sound. A fix for "too quiet"
# must never be able to produce "silent".


def _plain():
    """Settings as a real user has them: sounds on, nothing else asked for."""
    s = _Settings()
    s.set("sound_warm_up_device", False)
    return s


def test_the_warm_up_is_off_by_default():
    from core.settings import DEFAULTS
    assert DEFAULTS["sound_warm_up_device"] is False


def test_nothing_is_played_when_it_was_not_asked_for(played):
    snd.warm_up_audio(_plain())
    assert not played, "the warm-up ran without being switched on"


def test_nothing_is_even_built_when_it_was_not_asked_for(played):
    """Not just inaudible — no QSoundEffect against the device at all. The point
    of the default is that nothing touches the hardware."""
    snd.preload_warm_up(_plain())
    assert snd._WARMUP_EFFECTS == {}
    assert not played


def test_arming_a_measurement_touches_nothing_by_default(played):
    m = snd.SoundManager(_plain())
    m._preload = lambda events: None
    m.arm()
    assert not played, "arming warmed the device although nobody asked it to"


def test_a_missing_setting_means_off():
    """An older settings file has no such key. It must read as off, not as on —
    the default has to fail safe."""
    class _Bare:
        def get(self, k, d=None): return d
    assert snd.warm_up_enabled(_Bare()) is False


def test_a_broken_settings_object_means_off():
    class _Boom:
        def get(self, k, d=None): raise RuntimeError("no settings")
    assert snd.warm_up_enabled(_Boom()) is False


def test_switching_it_on_brings_it_back(played):
    """It is still there for anyone who wants it — the fault it addresses is
    real on some hardware, it just must not be the default."""
    snd.warm_up_audio(_Settings())          # the fixture switches it on
    assert played
