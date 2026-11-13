"""THE ONE SWITCH FOR i1iO TABLE SUPPORT (Preferences > Beta).

The X-Rite i1iO is a motorised table that carries an i1Pro over a chart. This
first step only MAKES charts for it: ChromIQ sends nothing to any table. The
switch is OFF by default, and with it off ChromIQ must behave exactly as 4.3.32
did: no i1iO in any list, no i1iO code loaded, no chart file read to find out
whether it is an i1iO chart, and no new key in any target's ``meta.json``.
Every i1iO hook in shared code asks :func:`i1io_enabled` first, and
``tests/test_i1io_off_changes_nothing.py`` fails on a hook that does not.

**Restart to apply**, like the other instrument Betas: the instrument
lists are built once, so the value is read ONCE per process (``main()`` latches
it before the window is built).

**Names.** The Create Chart entry is generation-specific (``IO2``: an i1iO 2
with an i1Pro 2, the only pair we have data for); the chart FILES carry the
family name ``"X-Rite i1iO"`` and record the table generation and the head
separately (the ``.ti2`` keyword ``CHROMIQ_I1IO_TABLE`` and the side file), so
a later i1iO / i1iO 3 entry never renames a file already written.
"""

from __future__ import annotations

from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "i1io_support_beta"

#: The Create Chart instrument code of the one supported pair.
CODE = "IO2"

#: Every Create Chart code that is an i1iO entry (one today).
CODES: "frozenset[str]" = frozenset({CODE})

#: The family name every i1iO chart carries in ``TARGET_INSTRUMENT``.
TARGET_INSTRUMENT = "X-Rite i1iO"

#: What this entry records as the table and the head.
TABLE_MODEL = "i1iO 2"
HEAD_MODEL = "i1Pro 2"

_latched: "bool | None" = None


def stored_value(settings: Any) -> bool:
    """What Preferences holds now (it may differ from the running value)."""
    try:
        return bool(settings.get(SETTING, False))
    except Exception:  # noqa: BLE001 - a broken store means "off"
        return False


def latch_from(settings: Any) -> bool:
    """Fix the running value from *settings*. Called once by ``main()``."""
    global _latched
    _latched = stored_value(settings)
    return _latched


def i1io_enabled() -> bool:
    """True when i1iO support is on for THIS run of ChromIQ (read once)."""
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


def is_i1io_code(code: Any) -> bool:
    """True for a Create Chart instrument code that is an i1iO entry."""
    return str(code or "") in CODES


def is_i1io_instrument_name(name: "str | None") -> bool:
    """True for a ``TARGET_INSTRUMENT`` value naming the i1iO family, in any
    letter case, with or without the quotes CGATS puts around it. Any
    generation ("X-Rite i1iO 2", "i1iO 3") counts as the family."""
    text = str(name or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    folded = text.casefold()
    for prefix in ("x-rite ", "xrite ", "gretagmacbeth "):
        if folded.startswith(prefix):
            folded = folded[len(prefix):].strip()
            break
    return folded == "i1io" or folded.startswith("i1io ")


def chart_names_i1io(path: Any) -> "bool | None":
    """Whether the chart file at *path* names the i1iO in ``TARGET_INSTRUMENT``.

    None when there is no chart file. Never raises: a file that cannot be read
    is not an i1iO chart. Only the header BYTES are read (a chart made on a
    German Windows is cp1252)."""
    from pathlib import Path
    try:
        p = Path(path)
        if not p.is_file():
            return None
        with open(p, "rb") as f:
            head = f.read(65536)
    except (OSError, TypeError, ValueError):
        return None if path is None else False
    head = head.split(b"BEGIN_DATA_FORMAT", 1)[0]
    for raw in head.splitlines():
        line = raw.strip()
        if line[:17].upper() == b"TARGET_INSTRUMENT" and (
                len(line) == 17 or line[17:18] in (b" ", b"\t")):
            return is_i1io_instrument_name(line[17:].strip().decode("latin-1"))
    return False


# ---- a target made with the Beta on, opened with it off --------------------
#
# The same carry rules as the other Beta instrument (`workflow.beta_chart_
# carry`): with the switch off the tab shows the instrument it falls back to,
# which is not the user's choice, so the target's stored i1iO values are put
# back over it when the target is written, and an untouched project's
# `meta.json` stays byte-identical.

CHART_PARAM_KEYS = ("printtarg-i", "printtarg-p")
CHART_GUIDED_KEYS = ("instrument", "paper", "pages")
CHART_RECIPE_KEYS = ("instrument", "paper", "border", "margin_top",
                     "margin_right", "margin_bottom", "margin_left",
                     "use_instrument_margins", "patch_w_mm", "patch_h_mm",
                     "layout_mode")


def target_names_i1io(stored_params: "dict | None",
                      stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names an i1iO entry."""
    from workflow.beta_chart_carry import target_names
    return any(target_names(code, stored_params, stored_ui) for code in CODES)


def carry_i1io_chart_keys(wanted, ui_state, stored_params, stored_ui,
                          screen_at_load=None, own=None) -> set:
    """`workflow.beta_chart_carry.carry_chart_keys` for the i1iO."""
    from workflow.beta_chart_carry import carry_chart_keys
    users: set = set()
    for code in sorted(CODES):
        users |= carry_chart_keys(code, i1io_enabled(), wanted, ui_state,
                                  stored_params, stored_ui, screen_at_load,
                                  own, param_keys=CHART_PARAM_KEYS,
                                  guided_keys=CHART_GUIDED_KEYS,
                                  recipe_keys=CHART_RECIPE_KEYS)
    return users


def off_snapshot(screen_params, screen_ui, stored_params, stored_ui):
    """An i1iO target as the switch-off tab opened it."""
    from workflow.beta_chart_carry import OffSnapshot

    class I1ioOffSnapshot(OffSnapshot):
        __slots__ = ()

        def carry(self, wanted, ui_state):
            return carry_i1io_chart_keys(wanted, ui_state, self.stored[0],
                                         self.stored[1], self.screen, self.own)

        def chart_names(self, path):
            return chart_names_i1io(path)

    return I1ioOffSnapshot(screen_params, screen_ui, stored_params, stored_ui)
