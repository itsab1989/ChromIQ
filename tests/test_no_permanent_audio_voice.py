"""#148: ChromIQ must not hold the audio device open with a permanent voice.

Qt 6.10 rewrote ``QSoundEffect`` onto ``QRtAudioEngine``, which suspends the
audio device the moment the last voice finishes and resumes it for the next
sound. Every sound therefore pays a device start-up, and anything shorter than
that start-up is never heard — which is the fault Knut reported.

ChromIQ briefly answered that with an inaudible voice that never ended, so
``m_voices`` was never empty and the device was never suspended. On an Apple
Silicon Mac's built-in speakers it worked. On Knut's machine, whose output is an
external speaker on a USB-C hub, it was far worse than the original bug:

    *"After your fix not a single sound is playing. Not even those that
    previously played fine."*

The reason is structural. Qt's engine registry holds only **weak** references,
so an engine — and its CoreAudio stream — lives exactly as long as some effect
holds it. A permanent voice pins one stream open for the life of the app, and
because ``m_voices`` is never empty the sink is never re-resumed either. An
external USB audio device power-saves, drops out and renegotiates its sample
rate; when that single long-lived stream dies there is no way back, and every
later sound goes into it.

This test exists so the idea is not quietly reintroduced by someone reading the
original analysis and thinking it sound. It was sound about the *cause* and
wrong about the *cure*.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import core.sound as snd                              # noqa: E402


def test_no_infinite_loop_voice_is_started():
    """``setLoopCount(Infinite)`` on a silent clip is the shape of the bug."""
    src = inspect.getsource(snd)
    assert "Infinite" not in src, (
        "a permanently-looping voice pins one CoreAudio stream open for the "
        "life of the app; on an external USB device that stream can die with "
        "no way back and silence everything (#148)")


def test_no_module_level_device_hold_api():
    """The hold/release pair is gone, not merely unused."""
    for name in ("hold_audio_device", "release_audio_device",
                 "_AudioDeviceKeepAlive", "_KEEP_ALIVE"):
        assert not hasattr(snd, name), f"{name} came back (#148)"


def test_arming_a_measurement_does_not_touch_the_device():
    """arm() pre-loads samples and nothing more. Pre-loading is memory-only and
    safe; holding the device open is what broke the reporter's audio."""
    src = inspect.getsource(snd.SoundManager.arm)
    assert "hold_audio_device" not in src
    assert "_preload" in src, "arm must still pre-load the samples"


def test_the_reason_is_written_down_where_the_next_person_will_look():
    """A bare removal invites the same fix again — the note has to survive."""
    src = inspect.getsource(snd)
    assert "USB" in src and "#148" in src, (
        "the note explaining why a permanent voice is not the answer must stay "
        "in core/sound.py")
