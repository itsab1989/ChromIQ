"""Keep a Beta instrument's stored Create Chart values while its Beta is OFF.

Written for the first Beta instrument (reviews r2 S1, r3 R3-1 and r4 R4-1 of
its pull request) and shared since the i1iO table became a second one
(2026-11-13), so both follow ONE set of carry rules. The rules, in short (the
full reasoning is in the first instrument's own carry function, whose
behaviour this is, unchanged):

* with the Beta off the tab shows a fallback instrument, which is not the
  user's choice, so the target's stored values for the Beta instrument are put
  back over it when the target is written;
* only a value still as it was on screen right after the load, and never one
  the user has had written (*own*);
* the other values of a block come back only while its instrument does;
* nothing with the Beta on (*on*), and nothing without a snapshot.

This module names no instrument: each Beta passes its own code and keys.
"""
from __future__ import annotations

from typing import Any, Callable


def _names(code: str, value: Any) -> bool:
    return str(value or "") == code


def target_names(code: str, stored_params: "dict | None",
                 stored_ui: "dict | None") -> bool:
    """True when a target's stored Create Chart block names *code*."""
    params = stored_params if isinstance(stored_params, dict) else {}
    if _names(code, (params.get("printtarg-i") or {}).get("value")):
        return True
    ui = stored_ui if isinstance(stored_ui, dict) else {}
    return any(isinstance(ui.get(b), dict) and _names(code, ui[b].get("instrument"))
               for b in ("guided", "engine_recipe"))


def carry_chart_keys(code: str, on: bool, wanted: "dict | None",
                     ui_state: "dict | None", stored_params: "dict | None",
                     stored_ui: "dict | None", screen_at_load: "tuple | None",
                     own: "set | None", *, param_keys: tuple,
                     guided_keys: tuple, recipe_keys: tuple) -> set:
    """Put the stored *code* Create Chart values back into *wanted* and
    *ui_state* (in place) while that instrument's Beta is off (*on* False).
    Returns the keys this write files as the user's."""
    users: set = set()
    if on:
        return users
    if not (isinstance(screen_at_load, tuple) and len(screen_at_load) == 2):
        return users
    own = own if isinstance(own, (set, frozenset)) else set()
    loaded_params, loaded_ui = screen_at_load
    loaded_params = loaded_params if isinstance(loaded_params, dict) else {}
    loaded_ui = loaded_ui if isinstance(loaded_ui, dict) else {}
    _missing = object()

    def _split(where, keys, was, now, at_load):
        """(carried, changed) for one block: carried while unchanged and
        not the user's, and only while its instrument is carried too."""
        carried, changed = set(), set()
        for key in keys:
            if key not in was:
                continue
            if (where, key) in own:
                changed.add(key)
            elif now.get(key, _missing) == at_load.get(key, _missing):
                carried.add(key)
            else:
                changed.add(key)
        instrument = "printtarg-i" if where == "params" else "instrument"
        if instrument not in carried:
            changed |= carried
            carried = set()
        return carried, changed

    params = stored_params if isinstance(stored_params, dict) else {}
    if isinstance(wanted, dict) and _names(code, 
            (params.get("printtarg-i") or {}).get("value")):
        carried, changed = _split("params", param_keys, params, wanted,
                                  loaded_params)
        for key in carried:
            wanted[key] = params[key]
        users |= {("params", key) for key in changed}
    ui = stored_ui if isinstance(stored_ui, dict) else {}
    if not isinstance(ui_state, dict):
        return users
    for block, keys in (("guided", guided_keys),
                        ("engine_recipe", recipe_keys)):
        was = ui.get(block)
        now = ui_state.get(block)
        if not (isinstance(was, dict) and _names(code, was.get("instrument"))):
            continue
        if not isinstance(now, dict):
            continue
        at_load = loaded_ui.get(block)
        at_load = at_load if isinstance(at_load, dict) else {}
        carried, changed = _split(block, keys, was, now, at_load)
        users |= {(block, key) for key in changed}
        if not carried:
            continue
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
    return users


class OffSnapshot:
    """A Beta instrument's target as the Beta-off tab opened it.

    *screen* is what the tab showed right after the load, *stored* the
    target's Create Chart blocks as ``meta.json`` held them then, and *own*
    the keys since written as the user's (never carried again). A subclass
    names its instrument (:meth:`carry`) and how to tell its chart
    (:meth:`chart_names`)."""

    __slots__ = ("screen", "stored", "own")

    def __init__(self, screen_params, screen_ui, stored_params, stored_ui):
        import copy
        self.screen = (copy.deepcopy(screen_params), copy.deepcopy(screen_ui))
        self.stored = (copy.deepcopy(stored_params), copy.deepcopy(stored_ui))
        self.own: set = set()

    def carry(self, wanted: "dict | None", ui_state: "dict | None") -> set:
        raise NotImplementedError

    def chart_names(self, path: Any) -> "bool | None":
        raise NotImplementedError

    def written(self, users: set) -> None:
        """The write that carried went to disk: its user keys are theirs."""
        self.own |= set(users or ())
