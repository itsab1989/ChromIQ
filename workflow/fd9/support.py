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


def chart_names_fd9(path: Any) -> "bool | None":
    """Whether the chart file at *path* names the FD-9 in its
    ``TARGET_INSTRUMENT`` (either spelling, see :func:`is_fd9_instrument_name`).

    None when there is no chart file to ask. Never raises: a file that cannot
    be read is not an FD-9 chart. Only the header BYTES are read (a chart made
    on a German Windows is cp1252), and nothing else from ``workflow.fd9`` is
    imported, so the off app loads no FD-9 code for it (review r3 R3-1).
    Asked only while the Beta is off AND the target's stored settings name the
    FD-9, so a 4.3.21 target never has its chart read for this."""
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
            value = line[17:].strip().decode("latin-1")
            return is_fd9_instrument_name(value)
    return False


def target_names_fd9(stored_params: "dict | None",
                     stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names the FD-9."""
    params = stored_params if isinstance(stored_params, dict) else {}
    if _names_fd9((params.get("printtarg-i") or {}).get("value")):
        return True
    ui = stored_ui if isinstance(stored_ui, dict) else {}
    return any(isinstance(ui.get(b), dict) and _names_fd9(ui[b].get("instrument"))
               for b in ("guided", "engine_recipe"))


def carry_fd9_chart_keys(wanted: "dict | None", ui_state: "dict | None",
                         stored_params: "dict | None",
                         stored_ui: "dict | None",
                         screen_at_load: "tuple | None" = None) -> None:
    """Put the stored FD-9 Create Chart values back into *wanted* and
    *ui_state* (in place) while FD-9 support is OFF (review r2 S1, narrowed
    in review r3 R3-1).

    The Create Chart counterpart of ``measure_settings.carry_fd9_keys``. A
    target whose chart was made for the FD-9 with the Beta on keeps its FD-9
    instrument, sheet, pages, margins and gap when it is opened with the Beta
    off: the tab shows the i1Pro instead, as 4.3.21 would, but that is the
    app's fallback and not the user's choice, so it is never filed into the
    target. With nothing else changed the write is then skipped altogether
    and ``meta.json`` stays byte-identical.

    *screen_at_load* is ``(wanted, ui_state)`` as the tab showed them right
    after it opened this target with the Beta off. A key is carried ONLY while
    its value on screen is still that one: a value the user changed is the
    user's and is written as it is (R3-1: a paper or page count picked with
    the Beta off used to be thrown away without a word). Without a snapshot
    nothing is carried; the caller passes None once the target's chart is no
    longer an FD-9 chart or the user has generated into it, so ``meta.json``
    then describes the chart that is really there. With the Beta on this does
    nothing: the tab writes its own FD-9 values, as before."""
    if fd9_enabled():
        return
    if not (isinstance(screen_at_load, tuple) and len(screen_at_load) == 2):
        return
    loaded_params, loaded_ui = screen_at_load
    loaded_params = loaded_params if isinstance(loaded_params, dict) else {}
    loaded_ui = loaded_ui if isinstance(loaded_ui, dict) else {}
    _missing = object()
    params = stored_params if isinstance(stored_params, dict) else {}
    if isinstance(wanted, dict) and _names_fd9(
            (params.get("printtarg-i") or {}).get("value")):
        for key in CHART_PARAM_KEYS:
            if key in params and (wanted.get(key, _missing)
                                  == loaded_params.get(key, _missing)):
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
        at_load = loaded_ui.get(block)
        at_load = at_load if isinstance(at_load, dict) else {}
        carried = {key for key in keys
                   if key in was and now.get(key, _missing)
                   == at_load.get(key, _missing)}
        # In the STORED order, so a block written again (the user switched
        # Guided/Manual and back, say) comes out byte for byte as it was.
        ordered = {}
        for key in was:
            if key in carried:
                ordered[key] = was[key]
            elif key in now:
                ordered[key] = now[key]
        for key in now:
            if key not in ordered and key not in carried:
                ordered[key] = now[key]
        ui_state[block] = ordered
