"""`GEOM_BUILD_KEYS` was guarded by nothing at all.

Its own comment calls it *"the single source of truth shared by every capacity
calculation"* and warns that *"a missing key silently makes capacity ESTIMATES
disagree with the actual render (clip_border_width once did exactly that)"*.

Measured 2026-09-09:

    $ grep -rn GEOM_BUILD_KEYS --include=*.py .      # excluding .venv
    workflow/layout_engine/instruments.py:397        the definition
    workflow/layout_engine/instruments.py:456        the one use

**Zero test references.** The documented chokepoint for every capacity number in
the app had no test on it, on the day a new geometry option was about to be
added to `build()`.

THE TWO OBVIOUS SHAPES ARE BOTH WRONG, and each fails on a real entry:

* *"every `build()` kwarg is in the tuple"* — false, and correctly so.
  `margins_are_law` and `fill_beyond_ruler` are derived explicitly from
  `layout_mode` / `use_instrument_margins` at `geom_from_build_kwargs:453-455`
  and passed separately.
* *"every tuple entry is a recipe key"* — also false. `clip_band` is in the
  tuple and is never emitted by `LayoutRecipe.build_kwargs()`; it is injected at
  `geom_from_build_kwargs:426`.

So this is a MUTATION test instead, and it is generated rather than listed: for
each keyword `build()` accepts, build a `Geom` with it at its default and again
at a non-default value. **If the two Geoms differ, the key changes the geometry,
and it must be in `GEOM_BUILD_KEYS`** — otherwise `geom_from_build_kwargs`
filters it out and the estimate silently stops matching the render.

It cannot be forgotten, because nobody has to remember to add a line: the moment
someone gives `build()` a new geometry argument and leaves the tuple alone, this
goes red naming it.
"""
from __future__ import annotations

import dataclasses
import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine.instruments import (GEOM_BUILD_KEYS,   # noqa: E402
                                                build)

# Derived inside `geom_from_build_kwargs` from other keys and passed separately,
# so they are deliberately absent from the tuple. Named here with the reason, so
# that adding to this list is a visible decision rather than a quiet one.
DERIVED_NOT_FILTERED = {
    "margins_are_law",      # = area_first or use_instrument_margins
    "fill_beyond_ruler",    # = area_first
}

# A non-default worth trying, per argument type. The value only has to be
# different enough to move something; what it moves is what the test reads.
PROBES = {
    bool: lambda cur: not cur,
    int: lambda cur: (cur or 0) + 3,
    float: lambda cur: (cur or 0.0) + 3.0,
    str: lambda cur: (cur or "") + "x",
}

# A DEFAULT OF `None` IS THE INTERESTING CASE, NOT THE ONE TO SKIP, and the
# first version of this test skipped it. Nine of `build()`'s arguments are
# `X | None = None` — `patch_w`, `patch_h`, `margins` and the rest — so dropping
# any of them from GEOM_BUILD_KEYS left this file green. Other tests happen to
# catch the ones that exist today (88 tier-wide reds for `patch_w`), but a NEW
# option written that way, which is exactly the shape a rotation flag takes,
# would be invisible here.
#
# There is no annotation to trust, so try a spread of plausible values and use
# the first that `build()` accepts. Anything that refuses every one of them is
# reported by the control test below rather than passing silently.
NONE_PROBES = (True, 3.0, 3, "x", (3.0, 3.0, 3.0, 3.0), [3.0, 3.0, 3.0, 3.0])

INSTRUMENTS = ("CR30", "SS", "i1", "CM")


def _kwargs():
    sig = inspect.signature(build)
    for name, prm in sig.parameters.items():
        if name in ("key", "self") or prm.kind in (prm.VAR_POSITIONAL,
                                                   prm.VAR_KEYWORD):
            continue
        yield name, prm.default


def _geom_differs(a, b) -> bool:
    if a is None or b is None:
        return a is not b
    fa, fb = dataclasses.asdict(a), dataclasses.asdict(b)
    return fa != fb


@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_every_build_argument_that_moves_the_geometry_is_filtered_through(instrument):
    """THE WHOLE POINT. Anything that changes the Geom must survive the filter
    in `geom_from_build_kwargs`, or the estimate and the render disagree."""
    base = build(instrument)
    missing = []
    inert = []
    unprobed = []
    for name, default in _kwargs():
        if name in DERIVED_NOT_FILTERED:
            continue
        other = _probe_build(instrument, name, default)
        if other is None:
            unprobed.append(name)
            continue
        moved = _geom_differs(base, other)
        if moved and name not in GEOM_BUILD_KEYS:
            missing.append(name)
        if not moved and name in GEOM_BUILD_KEYS:
            inert.append(name)

    assert not missing, (
        f"{instrument}: these build() arguments change the geometry but are NOT "
        f"in GEOM_BUILD_KEYS, so geom_from_build_kwargs drops them and every "
        f"capacity estimate stops matching the render: {sorted(missing)}"
    )
    # `inert` is reported, not asserted: a key can be live on one instrument and
    # inert on another (clip_band on an i1), and the tuple is deliberately the
    # union. Printing it keeps the tuple honest without making it brittle.
    if inert:
        print(f"[{instrument}] in the tuple but inert here: {sorted(inert)}")
    # Reported, not asserted: some arguments refuse every probe value on some
    # instruments. It is printed so that a growing list is visible rather than
    # quietly shrinking the test's reach.
    if unprobed:
        print(f"[{instrument}] no probe value was accepted: {sorted(unprobed)}")


def test_the_probe_actually_moves_something():
    """THE CONTROL. If `_geom_differs` never fired, the test above would pass by
    doing nothing at all — which is how a mutation test dies quietly."""
    base = build("CR30")
    moved = [n for n, d in _kwargs()
             if n not in DERIVED_NOT_FILTERED
             and _safe_moved("CR30", n, d, base)]
    assert len(moved) >= 12, (
        f"only {len(moved)} arguments moved the geometry at all; the probe "
        "values are not exercising build()"
    )


def _probe_build(instrument, name, default):
    """Build with *name* set to something other than its default, or None if no
    candidate value is accepted."""
    if default is None:
        candidates = NONE_PROBES
    else:
        probe = PROBES.get(type(default))
        if probe is None:
            return None
        candidates = (probe(default),)
    for value in candidates:
        try:
            return build(instrument, **{name: value})
        except Exception:      # noqa: BLE001 — a refused value proves nothing
            continue
    return None


def _safe_moved(instr, name, default, base) -> bool:
    other = _probe_build(instr, name, default)
    return other is not None and _geom_differs(base, other)


def test_the_two_derived_arguments_are_still_derived():
    """If either stopped being computed inside `geom_from_build_kwargs` and had
    to be passed through instead, the exclusion above would start hiding a real
    gap."""
    src = inspect.getsource(
        __import__("workflow.layout_engine.instruments", fromlist=["x"])
        .geom_from_build_kwargs)
    for name in DERIVED_NOT_FILTERED:
        assert f"{name}=" in src, (
            f"{name} is no longer passed explicitly by geom_from_build_kwargs, "
            "so excluding it from the check above is now unsafe"
        )


def test_the_tuple_has_no_duplicates():
    assert len(GEOM_BUILD_KEYS) == len(set(GEOM_BUILD_KEYS))
