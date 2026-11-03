"""THE ONE SWITCH FOR FD-9 SUPPORT (Preferences > Beta).

FD-9 support was written and contributed by lessbones (PR #213). It is a beta
and it is OFF by default, and with it off ChromIQ must behave exactly as 4.3.21
did: no FD-9 in any list, no FD-9 panel on the Measure tab, no chart file read
to find out whether it is an FD-9 chart, and no new key in any target's
``meta.json``. Every FD-9 hook in shared code asks :func:`fd9_enabled` first,
and ``tests/test_fd9_off_changes_nothing.py`` fails on a hook that does not.

**Restart to apply.** The instrument lists are built once, when the window is
built, so a live switch would leave half the app on the old answer. The value
is therefore read ONCE per process (``main()`` latches it before the window is
built) and Preferences shows the usual "Takes effect after you restart
ChromIQ." beside the box while the stored value differs from the running one.
"""

from __future__ import annotations

from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "fd9_support_beta"

#: Every spelling of the FD-9 a chart or measurement file can carry in
#: ``TARGET_INSTRUMENT``. ChromIQ writes the first; the second is what charts
#: made before the Beta switch (lessbones' own) carry, and still opens.
TARGET_INSTRUMENT_NAMES: "tuple[str, ...]" = ("Konica Minolta FD-9", "FD-9")

#: The name ChromIQ writes into a new FD-9 ``.ti2`` / ``.ti3``.
TARGET_INSTRUMENT = TARGET_INSTRUMENT_NAMES[0]

_latched: "bool | None" = None


def stored_value(settings: Any) -> bool:
    """What Preferences holds now (it may differ from the running value)."""
    try:
        return bool(settings.get(SETTING, False))
    except Exception:  # noqa: BLE001 — a broken store means "off"
        return False


def latch_from(settings: Any) -> bool:
    """Fix the running value from *settings*. Called once by ``main()``."""
    global _latched
    _latched = stored_value(settings)
    return _latched


def fd9_enabled() -> bool:
    """True when FD-9 support is on for THIS run of ChromIQ.

    Read once and then kept (restart-to-apply). Cheap: no file is read after
    the first call, and none at all for a chart."""
    global _latched
    if _latched is None:
        try:
            from core.settings import AppSettings
            _latched = stored_value(AppSettings())
        except Exception:  # noqa: BLE001
            _latched = False
    return _latched


def set_enabled_for_this_process(value: "bool | None") -> None:
    """Tests and drivers only: set the running value (None = read again)."""
    global _latched
    _latched = None if value is None else bool(value)


def is_fd9_instrument_name(name: "str | None") -> bool:
    """True for a ``TARGET_INSTRUMENT`` value that names the FD-9: either
    spelling, in any letter case, with or without the quotes CGATS puts
    around it (review r1 minor: a chart edited by hand or written by another
    tool says "fd-9" or 'FD-9' just as well)."""
    text = str(name or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text.casefold() in {n.casefold() for n in TARGET_INSTRUMENT_NAMES}
