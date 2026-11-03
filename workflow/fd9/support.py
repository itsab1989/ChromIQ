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


#: What makes a target's Create Chart settings the FD-9's (review r2 S1), per
#: place they are stored. With the Beta off the tab cannot show an FD-9, so
#: these are the values it would otherwise replace with the i1Pro it falls
#: back to. Everything else in the block is the user's, FD-9 or not.
CHART_PARAM_KEYS = ("printtarg-i", "printtarg-p")
CHART_GUIDED_KEYS = ("instrument", "paper", "pages")
CHART_RECIPE_KEYS = ("instrument", "paper", "border", "margin_top",
                     "margin_right", "margin_bottom", "margin_left",
                     "use_instrument_margins", "patch_w_mm", "patch_h_mm",
                     "fd9_gap_mm", "layout_mode")


def _names_fd9(value: Any) -> bool:
    return str(value or "") == "FD9"


def carry_fd9_chart_keys(wanted: "dict | None", ui_state: "dict | None",
                         stored_params: "dict | None",
                         stored_ui: "dict | None") -> None:
    """Put the stored FD-9 Create Chart values back into *wanted* and
    *ui_state* (in place) while FD-9 support is OFF (review r2 S1).

    The Create Chart counterpart of ``measure_settings.carry_fd9_keys``. A
    target whose chart was made for the FD-9 with the Beta on keeps its FD-9
    instrument, sheet, pages, margins and gap when it is opened with the Beta
    off: the tab shows the i1Pro instead, as 4.3.21 would, but that is the
    app's fallback and not the user's choice, so it is never filed into the
    target. With nothing else changed the write is then skipped altogether
    and ``meta.json`` stays byte-identical. With the Beta on this does
    nothing: the tab writes its own FD-9 values, as before."""
    if fd9_enabled():
        return
    params = stored_params if isinstance(stored_params, dict) else {}
    if isinstance(wanted, dict) and _names_fd9(
            (params.get("printtarg-i") or {}).get("value")):
        for key in CHART_PARAM_KEYS:
            if key in params:
                wanted[key] = params[key]
    ui = stored_ui if isinstance(stored_ui, dict) else {}
    if not isinstance(ui_state, dict):
        return
    for block, keys in (("guided", CHART_GUIDED_KEYS),
                        ("engine_recipe", CHART_RECIPE_KEYS)):
        was = ui.get(block)
        now = ui_state.get(block)
        if not (isinstance(was, dict) and _names_fd9(was.get("instrument"))):
            continue
        if not isinstance(now, dict):
            continue
        # In the STORED order, so a block written again (the user switched
        # Guided/Manual and back, say) comes out byte for byte as it was.
        ordered = {}
        for key in was:
            if key in keys:
                ordered[key] = was[key]
            elif key in now:
                ordered[key] = now[key]
        for key in now:
            if key not in ordered and key not in keys:
                ordered[key] = now[key]
        ui_state[block] = ordered
