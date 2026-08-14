"""Measurement sound feedback (#131, Phase 1).

A small, low-latency sound layer for the Measure tab. Short ``.wav`` clips are
played with ``QSoundEffect`` (pre-loaded into memory, so they fire at the exact
event with no disk-load delay — unlike ``QMediaPlayer``, which buffers).

Design (confirmed with Knut on #131):

* **Folder-driven choices.** Sounds live under a *sounds folder* with three
  sub-folders — ``measurement-events/``, ``slow-down/`` and ``task-complete/``.
  The choice list for each event is simply the ``.wav`` files present in its
  sub-folder (filename stem → list entry), always with ``OFF`` on top. ChromIQ
  ships a freely reusable default pack under ``assets/sounds/`` — synthesised by
  ``scripts/make_default_sounds.py`` except for the applause, which is a CC0
  recording (see ``assets/sounds/CREDITS.md``); the user can point
  Preferences → Paths at their own folder to extend or replace it.
* **Per-event selection** is stored in settings (``sound_choice_<event>``); a
  master ``sound_enabled`` switch (the Measure-tab checkbox) turns the whole
  layer on or off.
* **Only completion sounds may play outside a measurement.** During a
  measurement every event may sound; when no measurement is running only the two
  *task-complete* events (measurement finished, profile built) are allowed — the
  manager enforces this so a stray signal can never make noise at rest.

This module is Qt-dependent (``QSoundEffect``) but otherwise self-contained; the
UI wires signals to :meth:`SoundManager.play`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from core.resource_path import resource_path

log = logging.getLogger(__name__)

OFF = "OFF"

# QtMultimedia is imported lazily and defensively: on a packaged build where the
# multimedia plugin somehow didn't ship (or on a Linux box with no audio server
# available at import time), the whole sound layer must degrade to a silent
# no-op — it must NEVER raise into the measurement or profile-build flow. The
# result is cached so we probe the import only once.
_QSOUND_EFFECT = ...          # ... = "not probed yet"; None = unavailable


def _sound_effect_cls():
    """The ``QSoundEffect`` class, or ``None`` when audio isn't available in
    this build/environment. Probed once, then cached.

    **The garbage collector is held off for the duration of the import**, and
    that is not a micro-optimisation. Importing QtMultimedia allocates enough to
    trip a collection, and if a Qt widget happens to be waiting to be collected
    at that moment, its C++ destructor re-enters Python — an event filter, a
    resize handler — while the interpreter is in the middle of building the new
    module. That crashed a test worker outright (segfault in ``sipQWidget::
    eventFilter`` under ``gc_collect_main``, #131, 2026-08-03), and it can
    happen in the app too: this probe runs when the user ticks the sound box,
    which is exactly the moment after a dialog they just closed is due for
    collection. The import is short, so nothing is lost by deferring the sweep.
    """
    global _QSOUND_EFFECT
    if _QSOUND_EFFECT is ...:
        import gc
        was_enabled = gc.isenabled()
        gc.disable()
        try:
            from PyQt6.QtMultimedia import QSoundEffect
            _QSOUND_EFFECT = QSoundEffect
        except Exception as exc:      # noqa: BLE001 — ImportError or plugin error
            log.warning("Measurement sounds disabled — QtMultimedia "
                        "unavailable: %s", exc)
            _QSOUND_EFFECT = None
        finally:
            if was_enabled:
                gc.enable()
    return _QSOUND_EFFECT


def audio_available() -> bool:
    """True when this build/environment can play sounds at all."""
    return _sound_effect_cls() is not None

# ---- event keys (also the settings-key suffixes) ---------------------------
PATCH_OK = "patch_ok"
PATCH_OUT_OF_TOL = "patch_out_of_tol"
STRIP_OK = "strip_ok"
STRIP_FAIL = "strip_fail"
INSTRUMENT_ERROR = "instrument_error"
SLOW_DOWN = "slow_down"
MEASUREMENT_FINISHED = "measurement_finished"
PROFILE_BUILT = "profile_built"

MEASUREMENT_EVENTS = [PATCH_OK, PATCH_OUT_OF_TOL, STRIP_OK, STRIP_FAIL,
                      INSTRUMENT_ERROR]
SLOW_DOWN_EVENTS = [SLOW_DOWN]
TASK_COMPLETE_EVENTS = [MEASUREMENT_FINISHED, PROFILE_BUILT]
ALL_EVENTS = MEASUREMENT_EVENTS + SLOW_DOWN_EVENTS + TASK_COMPLETE_EVENTS

#: events that are allowed to play when no measurement is running
OUTSIDE_MEASUREMENT_EVENTS = frozenset(TASK_COMPLETE_EVENTS)

#: which sub-folder an event's choices come from
SUBFOLDER_OF = {
    **{e: "measurement-events" for e in MEASUREMENT_EVENTS},
    **{e: "slow-down" for e in SLOW_DOWN_EVENTS},
    **{e: "task-complete" for e in TASK_COMPLETE_EVENTS},
}
SUBFOLDERS = ("measurement-events", "slow-down", "task-complete")

#: default sound (filename stem) for each event
DEFAULT_CHOICE = {
    PATCH_OK: "tick",
    PATCH_OUT_OF_TOL: "thump",
    STRIP_OK: "bell",
    STRIP_FAIL: "failure",
    INSTRUMENT_ERROR: "error",
    SLOW_DOWN: "slowdown",
    MEASUREMENT_FINISHED: "drumroll",
    PROFILE_BUILT: "trumpet",
}


def _setting_key(event: str) -> str:
    return f"sound_choice_{event}"


# ---- waking the audio device once, before it is needed (#148) --------------
#
# What the fault actually is, measured rather than assumed. Playing the same
# clip several times a second apart, only the FIRST was quiet:
#
#     *"the very first one was pretty quiet. then they became louder and better
#     to hear for me … the repetitions were the same to my ear."*
#
# So this is a COLD START, not a per-sound cost. Qt 6.10's QRtAudioEngine
# suspends the audio device when the last voice ends, but the hardware itself
# stays warm for a while afterwards — which is why a sound that follows another
# within a second or so is fine, and why the first sound after a silence loses
# its opening. During a measurement the per-patch cues come every half second or
# so and keep each other alive; the one that suffers is the first.
#
# The cure is therefore to make sure the first real sound is never the cold one:
# play a single inaudible clip in advance and let the real cue follow into an
# already-running device.
#
# **This clip ends.** That is the whole safety argument, and it is the
# difference between this and the version that had to be withdrawn. That one
# held a voice that never ended, which pinned one CoreAudio stream open for the
# life of the app; on an external USB device that stream could die with no way
# back and every later sound went into it — *"After your fix not a single sound
# is playing."* A warm-up that finishes is just an ordinary short sound. If it
# fails, or the device ignores it, the worst case is that nothing is gained —
# never that something is lost.

#: How long the inaudible warm-up clip runs. Long enough to span a device
#: start-up, short enough that nothing waits on it.
_WARMUP_SECONDS = 0.30


def _warmup_file(rate: int, channels: int) -> "Path | None":
    """A tiny near-silent ``.wav`` at *rate*/*channels*, written once and cached
    in the temp directory. ``None`` if it cannot be written.

    Not digital silence: it carries a ±1 LSB dither (-90 dBFS, far below what
    any speaker can reproduce) so it travels the normal mixing path rather than
    a "this voice is muted" shortcut.
    """
    import tempfile
    path = (Path(tempfile.gettempdir())
            / f"chromiq_warmup_{rate}_{channels}.wav")
    try:
        if path.is_file() and path.stat().st_size > 44:
            return path
        import random
        import wave
        rnd = random.Random(0)                    # reproducible
        n = int(rate * _WARMUP_SECONDS) * channels
        data = bytearray()
        for _ in range(n):
            data += rnd.choice((-1, 0, 1)).to_bytes(2, "little", signed=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(data))
        return path
    except Exception as exc:      # noqa: BLE001 — never break a measurement
        log.debug("could not create the warm-up clip: %s", exc)
        return None


def formats_in_use(settings) -> set:
    """The distinct ``(sample_rate, channels)`` of every sound currently
    selected.

    Qt pools its audio engine per (device, format) and keeps each ``.wav``'s own
    rate and channel count, so a 44.1 kHz warm-up wakes only the 44.1 kHz
    engine. The bundled pack is uniformly 44.1 kHz mono, but a user's own file
    may be anything, so each format in use is warmed.
    """
    import wave
    out: set = set()
    for event in ALL_EVENTS:
        path = resolve_file(settings, event)
        if path is None:
            continue
        try:
            with wave.open(str(path)) as w:
                out.add((w.getframerate(), w.getnchannels()))
        except Exception:         # noqa: BLE001 — an unreadable/odd .wav
            continue
    return out


def warm_up_audio(settings) -> None:
    """Wake the audio device now, so the next real sound is not the cold one.

    Fire and forget: each clip plays once and finishes, and the effects are
    dropped as soon as they have been started. Safe to call at any time, and
    safe to call when there is no audio at all.
    """
    cls = _sound_effect_cls()
    if cls is None:                       # no audio in this build/environment
        return
    try:
        from PyQt6.QtCore import QTimer, QUrl
        held = []
        for rate, channels in formats_in_use(settings):
            path = _warmup_file(rate, channels)
            if path is None:
                continue
            eff = cls()
            eff.setSource(QUrl.fromLocalFile(str(path)))
            eff.setVolume(0.02)
            eff.play()
            held.append(eff)
        if not held:
            return
        # Keep them referenced until the clip has certainly finished, then let
        # them go — a QSoundEffect collected mid-play would stop the very sound
        # that is doing the waking.
        QTimer.singleShot(int(_WARMUP_SECONDS * 1000) + 1500,
                          lambda _h=held: _h.clear())
    except Exception as exc:      # noqa: BLE001 — a warm-up must never break a read
        log.debug("could not warm the audio device: %s", exc)


# ---- why there is no "keep the audio device awake" here (#148) -------------
#
# Qt 6.10 rewrote QSoundEffect onto QRtAudioEngine, which suspends the audio
# device the moment the last voice finishes and resumes it for the next sound
# (qtmultimedia/src/multimedia/audio/qrtaudioengine.cpp). Every sound therefore
# pays a device start-up, and whatever is handed over while the hardware is
# still starting is lost — which is why the short cues went missing entirely.
#
# ChromIQ briefly countered that with an inaudible voice that never ended, so
# `m_voices` was never empty and the device was never suspended. It worked on
# an Apple Silicon Mac's built-in speakers, and was a disaster on the reporter's
# machine: *"After your fix not a single sound is playing. Not even those that
# previously played fine."*
#
# The reason is structural rather than a detail that could be patched. Qt's
# engine registry holds only weak references, so an engine — and its CoreAudio
# stream — lives exactly as long as some effect holds it. A permanent voice
# pins one stream open for the life of the app, and because `m_voices` is never
# empty the sink is never re-resumed either. On an external USB audio device,
# the kind that power-saves, drops out or renegotiates its sample rate, that
# single long-lived stream can die with no way back, and every later sound goes
# into it. A transient per-sound cost had been turned into a permanent
# dependency on one stream staying healthy, which is the worse bargain.
#
# So: not this way. Do not reintroduce a permanently-playing voice without
# testing on an external USB audio interface, not only built-in speakers.


def bundled_sounds_root() -> Path:
    """The shipped default pack (``assets/sounds``)."""
    return resource_path("assets/sounds")


def sounds_root(settings) -> Path:
    """The active sounds folder: the user's Preferences → Paths folder when set
    and present, otherwise the bundled default pack."""
    custom = (settings.get("sound_folder", "") or "").strip()
    if custom:
        p = Path(custom).expanduser()
        if p.is_dir():
            return p
    return bundled_sounds_root()


def list_choices(settings, event: str) -> list[str]:
    """``["OFF", <stem>, …]`` for *event* — OFF plus every ``.wav`` in the
    event's sub-folder, case-insensitively sorted. Files from the bundled pack
    and the user's folder are merged, so a user folder adds to (rather than
    hides) the defaults."""
    stems: set[str] = set()
    sub = SUBFOLDER_OF[event]
    for root in {bundled_sounds_root(), sounds_root(settings)}:
        d = root / sub
        if d.is_dir():
            stems.update(p.stem for p in d.glob("*.wav"))
    return [OFF] + sorted(stems, key=str.lower)


def choice_for(settings, event: str) -> str:
    """The selected sound stem for *event* (or OFF). Falls back to the default
    when unset, and to OFF if the default file isn't available."""
    val = settings.get(_setting_key(event), None)
    if val is None:
        val = DEFAULT_CHOICE.get(event, OFF)
    if val == OFF:
        return OFF
    if val in list_choices(settings, event):
        return val
    return OFF


def file_for_stem(settings, event: str, stem: str) -> "Path | None":
    """The ``.wav`` for a specific *stem* in *event*'s sub-folder (or ``None``).
    Used to audition a not-yet-saved dropdown choice. Prefers the user's folder,
    then the bundled pack."""
    if not stem or stem == OFF:
        return None
    sub = SUBFOLDER_OF[event]
    for root in (sounds_root(settings), bundled_sounds_root()):
        cand = root / sub / f"{stem}.wav"
        if cand.is_file():
            return cand
    return None


def resolve_file(settings, event: str) -> "Path | None":
    """The ``.wav`` path for *event*'s current selection, or ``None`` (OFF /
    missing). Prefers the user's folder, then the bundled pack."""
    stem = choice_for(settings, event)
    if stem == OFF:
        return None
    sub = SUBFOLDER_OF[event]
    for root in (sounds_root(settings), bundled_sounds_root()):
        cand = root / sub / f"{stem}.wav"
        if cand.is_file():
            return cand
    return None


class SoundManager:
    """Pre-loads and plays the measurement sounds. One instance is shared by the
    Measure tab and the Build-Profile completion. Cheap to construct; it only
    touches audio when :meth:`arm` or :meth:`play` is called."""

    def __init__(self, settings) -> None:
        self._settings = settings
        self._effects: dict[str, object] = {}     # event -> QSoundEffect
        self._in_measurement = False
        #: ChromIQ's own reading engine silences ArgyllCMS's built-in beeps, so
        #: our sounds are the only ones heard. Stock ArgyllCMS chartread has no
        #: flag to silence them, so on that path the user hears Argyll's beep
        #: whatever we do — and adding ours on top means two sounds for one
        #: event. Knut's ruling (#131, 2026-07-27): "the ChromIQ sounds should
        #: not at all be wired or used for stock argyllcms chartread".
        self._reading_engine = True

    # -- lifecycle ----------------------------------------------------------
    def enabled(self) -> bool:
        return bool(self._settings.get("sound_enabled", False))

    def arm(self, *, reading_engine: bool = True) -> None:
        """Pre-load every selected sound into memory before a measurement, so
        the first play of each isn't delayed by a disk read. A no-op (and a
        quiet one) when sounds are disabled.

        ``reading_engine`` says whether this measurement runs on ChromIQ's own
        engine. On stock ArgyllCMS chartread it is False and no measurement
        sound is played at all — see :attr:`_reading_engine`.
        """
        self._in_measurement = True
        self._reading_engine = bool(reading_engine)
        if not self.enabled():
            return
        self._preload(ALL_EVENTS)
        # Pre-loading puts the SAMPLES in memory; it does nothing about the
        # DEVICE, which is asleep until something wakes it and swallows the
        # opening of whatever wakes it. Arming happens well before the first
        # patch is read, so waking it here means the first tick lands in a
        # running device — and the ticks that follow keep it awake themselves
        # (#148). One clip, played once.
        warm_up_audio(self._settings)

    def disarm(self) -> None:
        """Leave measurement mode. Completion sounds may still play afterwards
        (they pre-load on demand)."""
        self._in_measurement = False

    def _preload(self, events) -> None:
        cls = _sound_effect_cls()
        if cls is None:                          # no audio in this build/env
            return
        from PyQt6.QtCore import QUrl
        QSoundEffect = cls
        for event in events:
            path = resolve_file(self._settings, event)
            if path is None:
                self._effects.pop(event, None)
                continue
            eff = self._effects.get(event)
            want = QUrl.fromLocalFile(str(path))
            if isinstance(eff, QSoundEffect) and eff.source() == want:
                continue                          # already loaded this file
            eff = QSoundEffect()
            eff.setSource(want)
            eff.setVolume(0.85)
            self._effects[event] = eff

    # -- playback -----------------------------------------------------------
    def play_window(self, event: str) -> None:
        """Sound a WINDOW ChromIQ is opening, whether or not a read is running.

        Knut, #130 2026-07-28: *"when starting a measurement without the
        colormunki connected, the window 'No instrument Found' comes, but
        without any sound."* The cue was in the right place and still silent —
        :meth:`play` drops anything that is not a completion sound once the
        measurement is over, and the instrument windows are raised **after** the
        process exits, by which time :meth:`disarm` has already run.

        A window is ChromIQ's own interface, not part of the reading, so the
        at-rest gate does not apply to it — the same reasoning that already
        exempts the completion sounds. ArgyllCMS does not beep for ChromIQ's
        windows either, so there is nothing to double here.

        Everything else still holds: the master switch, and a sound the user has
        set to "Off".
        """
        if not self.enabled():
            return
        try:
            eff = self._effects.get(event)
            if eff is None:
                self._preload([event])
                eff = self._effects.get(event)
            if eff is not None:
                eff.play()
        except Exception as exc:      # noqa: BLE001 — audio must never break a window
            log.debug("could not play window sound %s: %s", event, exc)

    def play(self, event: str) -> None:
        """Play *event*'s sound now, if sounds are on, a file is selected, and
        the event is allowed in the current context (only completion sounds play
        when no measurement is running). Safe to call from signal handlers."""
        if not self.enabled():
            return
        if not self._in_measurement and event not in OUTSIDE_MEASUREMENT_EVENTS:
            return
        # Stock ArgyllCMS chartread beeps for itself and cannot be silenced, so
        # ChromIQ stays quiet there rather than doubling every event (Knut,
        # #131 2026-07-27). Completion sounds belong to ChromIQ's own workflow,
        # not to the reading, so they are unaffected.
        if (self._in_measurement and not self._reading_engine
                and event not in OUTSIDE_MEASUREMENT_EVENTS):
            return
        try:
            eff = self._effects.get(event)
            if eff is None:
                self._preload([event])
                eff = self._effects.get(event)
            if eff is not None:
                eff.play()
        except Exception as exc:      # noqa: BLE001 — audio must never break a read
            log.warning("Sound play failed for %s: %s", event, exc)
