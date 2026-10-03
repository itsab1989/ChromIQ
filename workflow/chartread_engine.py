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


_CAPS_CACHE: "dict[tuple[str, int], frozenset]" = {}


def helper_caps(helper: "Path | None" = None) -> frozenset:
    """What this build of the helper can do, from ``--caps`` (cached per
    binary). An older helper has no such flag and answers with nothing."""
    try:
        p = Path(helper) if helper is not None else helper_path()
        key = (str(p), p.stat().st_mtime_ns)
    except (EngineUnavailable, OSError):
        return frozenset()
    if key in _CAPS_CACHE:
        return _CAPS_CACHE[key]
    caps: frozenset = frozenset()
    try:
        from core.proc_text import run_text
        # Budgeted for a loaded machine: the call is a fraction of a second
        # idle, and a helper that does not know the flag exits at once.
        res = run_text([str(p), "--caps"], capture_output=True, timeout=20)
        if res.returncode == 0:
            for line in (res.stdout or "").splitlines():
                line = line.strip()
                if line.startswith("{"):
                    try:
                        doc = json.loads(line)
                    except ValueError:
                        continue
                    caps = frozenset(str(c) for c in doc.get("caps", ()))
                    break
    except Exception as exc:   # noqa: BLE001 — no answer is "cannot"
        log.debug("could not ask the helper what it can do: %s", exc)
    _CAPS_CACHE[key] = caps
    return caps


def reads_legacy_labels(helper: "Path | None" = None) -> bool:
    """True when the helper reads a sheet printed with ChromIQ's labels from
    before 4.3.3-beta.7 as printed (Knut, #182 5965589190)."""
    return "legacy_labels" in helper_caps(helper)


def parse_engine_line(line: str) -> dict | None:
    """Decode one stdout line into an event dict, or None for prose.

    The helper starts every JSON object at column 0; anything else is
    chartread's ordinary console text (kept for the log window).
    """
    # A BEL ("\a", 0x07) is Argyll's beep on Linux and is not whitespace to
    # str.strip(). The engine writes every JSON line on its own line, so a BEL
    # cannot precede one today, but if it ever did the whole event would be
    # dropped (review P_review2_beta1): strip it here as well.
    s = line.strip().strip("\x07").strip()
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
