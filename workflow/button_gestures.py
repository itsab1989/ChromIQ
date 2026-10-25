"""Instrument button shortcuts: a double or triple press of the button.

Basti, 2026-10-25, after jctay's forum post 149841 ("can an i1Pro detect a
double-click?"). Preferences ▸ Measurement ▸ *Instrument button shortcuts*,
OFF by default. When it is off, nothing in here reaches the engine and every
measurement runs exactly as before.

The ENGINE does the counting (``native/chartread_helper``: ``--gestures
<wait ms>:<counts>``), because only the engine sees the presses that fall
inside the short scan a quick tap starts; the GUI only maps a recognised group
to one of the commands the reader already has (``back``, ``forward``,
``next_unread``) or to a pause, and says what happened.

This module is the one place that knows:

* which settings exist and what an unknown stored value means;
* which instruments can do it (the i1Pro line and the ColorMunki family);
* what to pass to the engine;
* the words: combobox labels and the Measure tab's status line.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.i18n import decimal_text, tr

#: The actions, in the order the comboboxes offer them.
ACTIONS: "tuple[str, ...]" = ("none", "back", "forward", "next_unread", "pause")

#: The engine command each moving action sends from its hold.
ACTION_COMMAND = {"back": "back", "forward": "forward",
                  "next_unread": "next_unread"}

#: "Wait for further presses", in milliseconds.
WAIT_MIN_MS = 300
WAIT_MAX_MS = 1500
WAIT_DEFAULT_MS = 600
WAIT_STEP_MS = 50

#: Instrument families (``ui.ti2_loader.instrument_family``) whose driver
#: reports every press of the button, which is what makes this possible:
#: the i1Pro, i1Pro 2, i1Pro 3 and 3 Plus, and the ColorMunki / i1Studio /
#: ColorChecker Studio. The engine checks the connected model again itself
#: (``cq_button_retry_ok``), so a wrong guess here can only grey the
#: Preferences section out, never make an instrument do it.
SUPPORTED_FAMILIES = frozenset({"i1pro", "colormunki"})


def action_label(action: str) -> str:
    """The combobox entry for *action*. Short, for 13 languages, and right
    in both reading modes: one option acts on a strip when strips are read
    and on a patch patch by patch (Basti, 2026-10-25)."""
    return {
        "none": tr("Nothing"),
        "back": tr("One strip / patch back"),
        "forward": tr("One strip / patch forward"),
        "next_unread": tr("Next unread strip / patch"),
        "pause": tr("Pause / continue"),
    }.get(action, tr("Nothing"))


@dataclass(frozen=True)
class GestureConfig:
    enabled: bool = False
    double: str = "back"
    triple: str = "next_unread"
    wait_ms: int = WAIT_DEFAULT_MS

    def action_for(self, presses: int) -> str:
        if presses == 2:
            return self.double
        if presses == 3:
            return self.triple
        return "none"

    @property
    def counts(self) -> str:
        """The press counts that have an action, for the engine ("23")."""
        return "".join(str(n) for n in (2, 3) if self.action_for(n) != "none")

    @property
    def active(self) -> bool:
        """On, and at least one press count does something."""
        return bool(self.enabled and self.counts)


def _action(value, default: str) -> str:
    v = str(value or "").strip()
    return v if v in ACTIONS else default


def clamp_wait(ms) -> int:
    try:
        v = int(round(float(ms)))
    except (TypeError, ValueError):
        return WAIT_DEFAULT_MS
    return max(WAIT_MIN_MS, min(WAIT_MAX_MS, v))


def config_from(settings) -> GestureConfig:
    """The four settings, every one of them checked: an old settings file
    has none of them and loads as OFF; a value this version does not know
    reads as "Nothing" (never as a move)."""
    get = settings.get
    return GestureConfig(
        enabled=bool(get("button_gestures_enabled", False)),
        double=_action(get("button_gesture_double", "back"), "none"),
        triple=_action(get("button_gesture_triple", "next_unread"), "none"),
        wait_ms=clamp_wait(get("button_gesture_wait_ms", WAIT_DEFAULT_MS)),
    )


def engine_args(cfg: GestureConfig) -> "list[str]":
    """What the engine is started with: nothing at all when it is off (or no
    press count has an action), so an engine started for a user who never
    switched this on is the same engine, with the same command line, as
    before."""
    if not cfg.active:
        return []
    return ["--gestures", f"{cfg.wait_ms}:{cfg.counts}"]


def supported(family: "str | None") -> "bool | None":
    """True for the i1Pro line and the ColorMunki family, False for every
    other known instrument (CR30, SpectroScan, DTP, i1iSis), None when the
    instrument is not known yet."""
    if family is None:
        return None
    return family in SUPPORTED_FAMILIES


def family_of(name: "str | None") -> "str | None":
    """The family of a model name or chart instrument code, or None."""
    if not name:
        return None
    try:
        from ui.ti2_loader import instrument_family
        fam = instrument_family(name)
    except Exception:          # noqa: BLE001 - a guess, never a failure
        fam = None
    if fam is not None:
        return fam
    code = str(name).strip()
    return {"i1": "i1pro", "p3": "i1pro", "3p": "i1pro", "CM": "colormunki",
            "cm": "colormunki", "SS": "spectroscan", "ss": "spectroscan",
            "CR30": "cr30"}.get(code, "other" if code else None)


# ---------------------------------------------------------------------------
# The words
# ---------------------------------------------------------------------------

def press_name(presses: int) -> str:
    """ "Single press", "Double press", "Triple press", "4 presses"."""
    if presses == 1:
        return tr("Single press")
    if presses == 2:
        return tr("Double press")
    if presses == 3:
        return tr("Triple press")
    return tr("{n} presses").format(n=presses)


def gaps_text(gaps_ms) -> str:
    """The time between the presses of a group, as the reader writes
    numbers: "0.31 s, 0.29 s"."""
    return ", ".join(tr("{secs} s").format(secs=decimal_text(g / 1000.0, 2))
                     for g in (gaps_ms or []))


def moved_text(presses: int, action: str, unit: str, label: str,
               unread: "bool | None" = None) -> str:
    """The Measure tab's status line once the reader has moved:
    "Double press: back to strip C" / "... back to patch C5". *unread* is
    whether the strip or patch it landed on has no reading yet: "the next
    one not yet read" is said only when that is true (with everything read,
    "next unread" can only move on)."""
    from workflow import measurement_messages as M
    who = press_name(presses)
    if action == "next_unread" and unread is False:
        action = "forward"
    if unit == "patch":
        key = {"back": M._GESTURE_BACK_PATCH,
               "forward": M._GESTURE_FORWARD_PATCH,
               "next_unread": M._GESTURE_NEXT_PATCH}[action]
    else:
        key = {"back": M._GESTURE_BACK_STRIP,
               "forward": M._GESTURE_FORWARD_STRIP,
               "next_unread": M._GESTURE_NEXT_STRIP}[action]
    return tr(key).format(press=who, label=label)
