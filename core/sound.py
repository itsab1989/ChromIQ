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


# ---- keeping the audio device awake (#148) ---------------------------------
#
# Qt 6.10 rewrote QSoundEffect on top of a new real-time engine
# (qtmultimedia/src/multimedia/audio/qrtaudioengine.cpp) that parks the audio
# device between sounds:
#
#     m_sink.start(...); m_sink.suspend();          // starts asleep
#     void QRtAudioEngine::play(SharedVoice voice) {
#         if (m_voices.empty()) m_sink.resume();     // wake the device…
#         sendAppToRtCommand(PlayCommand{voice});    // …then queue the voice,
#     }                                              // rendered only once the
#                                                    // audio callback runs
#     // and when the last voice finishes:
#     if (m_voices.empty()) m_sink.suspend();
#
# So every single sound pays a device resume, and whatever is handed over while
# the hardware is still starting is lost. How long that takes is a property of
# the machine: on an Apple Silicon Mac it costs a few milliseconds, on a 2018
# Intel MacBook Pro roughly a quarter of a second. That was #148 — every sound
# shorter than the resume window was silent (tick, thump, ding, chime …), and
# longer ones lost their attack, which is what stops a bell sounding like a
# bell.
#
# The cure is to give the engine a voice that never ends, so ``m_voices`` is
# never empty and the device is never suspended. Then a real sound plays into an
# already-running stream and is heard whole, from its first sample.
#
# Two details matter:
#
# * **Per format.** The engine is pooled per (device, format), and
#   ``QSample`` keeps the .wav's own sample rate and channel count
#   (qsamplecache_p.cpp sets only the sample *format* to Float). A 44.1 kHz mono
#   keep-alive therefore holds open only the 44.1 kHz mono engine — which covers
#   the bundled pack, but not a user's own 48 kHz file. So one keep-alive is
#   started per distinct format actually in use.
# * **Not digital silence.** The clip carries a ±1 LSB dither (-90 dBFS, far
#   below anything a speaker can reproduce) and plays at a low volume rather
#   than at zero. Qt today skips the mixing loop for a muted voice but still
#   counts it as active; a clip that is genuinely non-zero keeps working even if
#   that ever changes.

#: how long the device is held after the last thing that could make a sound —
#: long enough to cover the windows a measurement raises as it finishes, and the
#: completion sound that follows them.
KEEP_AWAKE_LINGER_MS = 30_000

#: length of the looping keep-alive clip
_SILENCE_SECONDS = 0.5


def _silence_file(rate: int, channels: int) -> "Path | None":
    """A tiny looping near-silent .wav at *rate*/*channels*, created once and
    cached in the temp directory. ``None`` if it cannot be written."""
    import tempfile
    path = (Path(tempfile.gettempdir())
            / f"chromiq_keepalive_{rate}_{channels}.wav")
    try:
        if path.is_file() and path.stat().st_size > 44:
            return path
        import random
        import wave
        rnd = random.Random(0)                    # reproducible
        frames = int(rate * _SILENCE_SECONDS)
        data = bytearray()
        for _ in range(frames * channels):
            data += (rnd.choice((-1, 0, 1))).to_bytes(2, "little", signed=True)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(channels)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(data))
        return path
    except Exception as exc:      # noqa: BLE001 — never break a measurement
        log.debug("could not create the keep-alive clip: %s", exc)
        return None


def formats_in_use(settings) -> set:
    """The distinct ``(sample_rate, channels)`` of every sound currently
    selected. Files that cannot be read fall back to nothing rather than
    raising — a sound we cannot parse is one Qt cannot play either."""
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


class _AudioDeviceKeepAlive:
    """Holds the audio device open so short sounds are not swallowed while it
    wakes up. Shared by every :class:`SoundManager` and by the Preferences
    audition, and reference-counted so whichever finishes last releases it."""

    def __init__(self) -> None:
        self._effects: dict = {}          # (rate, channels) -> QSoundEffect
        self._holds = 0
        #: bumped on every hold and release, so a linger that is already in
        #: flight can tell whether it is still the current one. See
        #: :meth:`_stop_after_linger` for why this is a counter rather than a
        #: QTimer we keep hold of.
        self._generation = 0

    # -- reference counting -------------------------------------------------
    def hold(self, settings) -> None:
        """Take a reference and make sure the device is awake."""
        self._holds += 1
        self._generation += 1             # any pending linger is now stale
        self._start(settings)

    def release(self, *, linger_ms: int = KEEP_AWAKE_LINGER_MS) -> None:
        """Drop a reference. When the last one goes the device is released
        after *linger_ms*, so a sound that follows straight after (a window, a
        completion cue) still lands in a running stream."""
        self._holds = max(0, self._holds - 1)
        if self._holds:
            return
        if linger_ms <= 0:
            self._stop()
            return
        self._generation += 1
        generation = self._generation
        try:
            from PyQt6.QtCore import QTimer
            # A fire-and-forget single shot, deliberately: owning the QTimer
            # would mean dropping our last reference to it from inside its own
            # timeout handler, which destroys a QObject while its signal is
            # still being emitted. The generation counter does the same job
            # with nothing to destroy.
            QTimer.singleShot(linger_ms,
                              lambda: self._stop_after_linger(generation))
        except Exception:             # noqa: BLE001 — no event loop / no Qt
            self._stop()

    def _stop_after_linger(self, generation: int) -> None:
        """Release the device, unless someone took it again while we waited."""
        if generation != self._generation or self._holds:
            return
        self._stop()

    # -- the voices themselves ----------------------------------------------
    def _start(self, settings) -> None:
        cls = _sound_effect_cls()
        if cls is None:                   # no audio in this build/environment
            return
        try:
            from PyQt6.QtCore import QUrl
            for fmt in formats_in_use(settings):
                if fmt in self._effects:
                    continue
                path = _silence_file(*fmt)
                if path is None:
                    continue
                eff = cls()
                eff.setSource(QUrl.fromLocalFile(str(path)))
                eff.setLoopCount(cls.Loop.Infinite.value)
                eff.setVolume(0.02)
                eff.play()
                self._effects[fmt] = eff
        except Exception as exc:      # noqa: BLE001 — audio must never break a read
            log.debug("could not hold the audio device awake: %s", exc)

    def _stop(self) -> None:
        for eff in self._effects.values():
            try:
                eff.stop()
            except Exception:         # noqa: BLE001
                pass
        self._effects.clear()

    # -- for tests ----------------------------------------------------------
    def is_holding(self) -> bool:
        return bool(self._effects)


#: one keep-alive for the whole application — the audio device is one device,
#: however many SoundManagers happen to exist.
_KEEP_ALIVE = _AudioDeviceKeepAlive()


def hold_audio_device(settings) -> None:
    """Keep the audio device awake until a matching :func:`release_audio_device`
    — so a short sound is heard whole instead of being eaten by the device
    starting up (#148). Safe to call when there is no audio at all."""
    _KEEP_ALIVE.hold(settings)


def release_audio_device(*, linger_ms: int = KEEP_AWAKE_LINGER_MS) -> None:
    """Give back one :func:`hold_audio_device` reference."""
    _KEEP_ALIVE.release(linger_ms=linger_ms)


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
        #: whether this manager currently holds the audio device awake (#148).
        #: Tracked per manager so arm/disarm can be called in any order without
        #: unbalancing the shared reference count.
        self._holding = False

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
        # Hold the device open for the whole measurement. Pre-loading alone is
        # not enough: the sample is in memory, but the *device* still has to
        # wake for each sound, and the per-patch cues are far too short to
        # survive that (#148).
        if not self._holding:
            self._holding = True
            hold_audio_device(self._settings)

    def disarm(self) -> None:
        """Leave measurement mode. Completion sounds may still play afterwards
        (they pre-load on demand).

        The device is released only after :data:`KEEP_AWAKE_LINGER_MS`, because
        the measurement being over is exactly when the instrument windows are
        raised and the completion sound plays — all of which still need to be
        heard whole.
        """
        self._in_measurement = False
        if self._holding:
            self._holding = False
            release_audio_device()

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
