"""Measurement sound feedback (#131, Phase 1).

A small, low-latency sound layer for the Measure tab. Short ``.wav`` clips are
played with ``QSoundEffect`` (pre-loaded into memory, so they fire at the exact
event with no disk-load delay — unlike ``QMediaPlayer``, which buffers).

Design (confirmed with Knut on #131):

* **Folder-driven choices.** Sounds live under a *sounds folder* with three
  sub-folders — ``measurement-events/``, ``slow-down/`` and ``task-complete/``.
  The choice list for each event is simply the ``.wav`` files present in its
  sub-folder (filename stem → list entry), always with ``OFF`` on top. ChromIQ
  ships a synthesised CC0 default pack under ``assets/sounds/``; the user can
  point Preferences → Paths at their own folder to extend or replace it.
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

    # -- lifecycle ----------------------------------------------------------
    def enabled(self) -> bool:
        return bool(self._settings.get("sound_enabled", False))

    def arm(self) -> None:
        """Pre-load every selected sound into memory before a measurement, so
        the first play of each isn't delayed by a disk read. A no-op (and a
        quiet one) when sounds are disabled."""
        self._in_measurement = True
        if not self.enabled():
            return
        self._preload(ALL_EVENTS)

    def disarm(self) -> None:
        """Leave measurement mode. Completion sounds may still play afterwards
        (they pre-load on demand)."""
        self._in_measurement = False

    def _preload(self, events) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QSoundEffect
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
    def play(self, event: str) -> None:
        """Play *event*'s sound now, if sounds are on, a file is selected, and
        the event is allowed in the current context (only completion sounds play
        when no measurement is running). Safe to call from signal handlers."""
        if not self.enabled():
            return
        if not self._in_measurement and event not in OUTSIDE_MEASUREMENT_EVENTS:
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
