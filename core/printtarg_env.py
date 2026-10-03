"""The environment printtarg runs in, so that a seeded chart is laid out the
same way every time (flk1, 2026-10-02).

**printtarg READS MEMORY IT NEVER WROTE, AND THE LAYOUT DEPENDS ON IT.**
ArgyllCMS 3.5.0, ``target/printtarg.c``: the patch array is
``cols = malloc(sizeof(col) * (npat + MAXPPROW))`` and the loop that fills it
never sets ``cols[i].media``. The strip-layout optimiser then asks
``setup_spacer`` for ``cretm && (pp->media || cp->media)`` on every pair it
weighs (``cretm`` is on for the ColorMunki, the i1Pro and the other strip
readers), so a patch whose garbage happens to be non-zero is scored as if it
were the paper. Different garbage, different simulated-annealing path,
different chart: with ``-R 182`` on the same ``.ti1`` patch 1 landed on B15,
G3 or D3.

Measured on this Mac (macOS 27, Homebrew Argyll 3.5.0 arm64), 120 patches on
A4 for a ColorMunki, patch 1's location per build:

* 8 x 100 builds with 20 CPU hogs, environment as it comes: B15 647, G3 126,
  D3 27. 48 builds 16 at a time, no hogs: 2 to 6 of 48 off B15 every time.
* the same with ``MallocLargeCache=0``: B15 800 of 800; 48 of 48, three times.
* a probe that interposes ``malloc`` and zero-fills ONLY the one block of
  ``(120 + 500) * 456 = 282,720`` bytes, i.e. ``cols``: B15 240 of 240. A
  probe that fills every block with 0x5A instead: D3 10 of 10.

The block is big enough to come from macOS malloc's large allocator, which
keeps freed large blocks in a cache and hands them out again with their old
contents; whether a given run gets a recycled block or fresh, zeroed pages
depends on the timing of the run, which is why the gate (a loaded machine)
saw it and a test run alone did not. ``MallocLargeCache=0`` turns that cache
off, so the block is always fresh pages, zero-filled by the kernel:
``media`` reads 0 for every test patch, which is also the value Argyll means
(only the paper colour sets it). It prints nothing and changes nothing else.

Only macOS is covered, because only macOS is measured. Linux (glibc) and
Windows have their own allocators and are NOT known to be deterministic here.

Every printtarg ChromIQ starts that can randomise a layout goes through
:func:`printtarg_env`: the Create Chart run (``ArgyllRunner``), the presets
window's behind-the-scenes layout (the page it judges is the page Generate
prints), and the demo pack generator (``make_report_limit_demos.run``). The
scanner ``.cht`` capture gets it too, for consistency only: its geometry does
not depend on the patch order. ``ti2_relayout`` always passes ``-r``, which
skips the optimiser that reads the garbage.
``tests/test_flk1_printtarg_lays_out_the_same_every_time.py`` holds them to it.
"""
from __future__ import annotations

import os
import sys
from typing import Mapping

#: what printtarg needs on macOS, see the module docstring
DARWIN_PRINTTARG_ENV: "dict[str, str]" = {"MallocLargeCache": "0"}


def printtarg_env_additions(platform: "str | None" = None) -> "dict[str, str]":
    """The variables to add to printtarg's environment on *platform*
    (``sys.platform`` by default). Empty where nothing is measured."""
    platform = sys.platform if platform is None else platform
    return dict(DARWIN_PRINTTARG_ENV) if platform == "darwin" else {}


def printtarg_env(base: "Mapping[str, str] | None" = None) -> "dict[str, str]":
    """A full environment for a printtarg subprocess: *base* (this process's
    own environment by default) with the serial-scan exclusion every Argyll
    tool gets (:func:`core.argyll_env.argyll_env`) and
    :func:`printtarg_env_additions` on top."""
    from core.argyll_env import argyll_env
    env = argyll_env(base, phantoms=False)
    env.update(printtarg_env_additions())
    return env


def is_printtarg(tool: "str | os.PathLike[str]") -> bool:
    """True for ``printtarg``, ``printtarg.exe`` or a path to either."""
    name = os.path.basename(os.fspath(tool)).lower()
    return name in ("printtarg", "printtarg.exe")
