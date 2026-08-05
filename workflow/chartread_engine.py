"""ChromIQ chart-reading engine (issue #126) — helper discovery + protocol.

The heavy lifting lives in the bundled ``chromiq-chartread`` binary, a fork
of ArgyllCMS chartread with a JSON event/command protocol, per-strip
autosave, direct strip jumps and fixed-order recognition. This module
locates the binary and decodes its event stream; `MeasureManager` drives it
through the ordinary ArgyllRunner (plain pipes — no PTY needed).

With the Settings option on "Argyll chartread" nothing in here is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from core.logger import get_logger
from core.resource_path import argyll_binary, resource_path

log = get_logger(__name__)


class EngineUnavailable(RuntimeError):
    """The bundled chart-reading engine is missing or unrunnable."""


def helper_path() -> Path:
    """Locate the bundled ``chromiq-chartread`` binary.

    Search order: ``$CHROMIQ_CHARTREAD`` override (dev/testing), the local
    CMake build tree (source checkouts), then the bundled ``native/``
    location for frozen runs.
    """
    override = os.environ.get("CHROMIQ_CHARTREAD")
    if override:
        p = Path(override)
        if p.exists():
            return p
        raise EngineUnavailable(f"$CHROMIQ_CHARTREAD points at a missing file: {p}")

    dev = Path(__file__).resolve().parents[1] / "native" / "chartread_helper" \
        / "build" / argyll_binary("chromiq-chartread")
    if dev.exists():
        return dev

    p = resource_path("native/" + argyll_binary("chromiq-chartread"))
    if not p.exists():
        raise EngineUnavailable(f"chart-reading engine not found at {p}")
    _ensure_executable(p)
    return p


def _ensure_executable(p: Path) -> None:
    if os.name == "nt":
        return
    try:
        if not os.access(p, os.X_OK):
            os.chmod(p, os.stat(p).st_mode | 0o111)
    except OSError as exc:
        log.debug("could not chmod helper %s: %s", p, exc)


def is_available() -> bool:
    """True if the engine binary can be located (cheap existence check)."""
    try:
        helper_path()
        return True
    except EngineUnavailable:
        return False


def parse_engine_line(line: str) -> dict | None:
    """Decode one stdout line into an event dict, or None for prose.

    The helper starts every JSON object at column 0; anything else is
    chartread's ordinary console text (kept for the log window).
    """
    s = line.strip()
    if not s.startswith("{"):
        return None
    try:
        ev = json.loads(s)
    except json.JSONDecodeError:
        log.warning("engine: undecodable event line: %.120s", s)
        return None
    return ev if isinstance(ev, dict) and "event" in ev else None


# Keystroke → command translation. The engine understands the same key
# semantics as chartread's console — this map keeps MeasureManager's
# existing send_key('f'|'\r'|…) call sites working unchanged when the
# engine is active.
KEY_TO_COMMAND: dict[str, dict] = {
    "\r": {"cmd": "ok"},           # Return: accept / "any key" prompts
    "f":  {"cmd": "forward"},
    "b":  {"cmd": "back"},
    "n":  {"cmd": "next_unread"},  # doubles as 'no' — same key in chartread
    # "Hit Return to use it anyway, ANY OTHER KEY to retry" (chartread.c:1855).
    # The failure and warning windows spell that "any other key" as a space, and
    # the keyboard forwarder passes a real space through unchanged — so on stock
    # chartread both retry. Neither was mapped here, so on the engine they went
    # nowhere and the prompt stayed open with the instrument waiting.
    #
    # Knut, beta.138, after "Wrong Strip Read" → Retry: *"The instrument now
    # stopped responding (no button press reacting and no sound), so I cannot
    # measure strips anymore."* His log ends on ChromIQ's own watchdog line,
    # "No response from chartread after sending a key".
    " ":  {"cmd": "retry"},
    "r":  {"cmd": "retry"},
    "d":  {"cmd": "done"},
    "y":  {"cmd": "yes"},
    "s":  {"cmd": "skip"},
    "q":  {"cmd": "quit"},
    "\x1b": {"cmd": "quit"},
}


#: Keys that move ten units at a time. chartread implements them itself
#: ('F' → incflag 2, 'B' → −2, chartread.c:2319-2327); the ChromIQ helper's
#: command vocabulary has only single steps, so ten of those are sent instead —
#: the same movement, without waiting on a helper rebuild. Knut, beta.135:
#: *"'F' move forward 10, and 'B; to move back 10 does not work at all"*, and
#: his log names the reason: "engine: no command mapping for key 'F'".
KEY_TO_REPEATED_COMMAND: dict[str, tuple[dict, int]] = {
    "F": ({"cmd": "forward"}, 10),
    "B": ({"cmd": "back"}, 10),
}


def command_for_key(key: str) -> dict | None:
    return KEY_TO_COMMAND.get(key)


def repeated_command_for_key(key: str) -> "tuple[dict, int] | None":
    """(command, how many times) for a key that moves in tens, or None."""
    return KEY_TO_REPEATED_COMMAND.get(key)
