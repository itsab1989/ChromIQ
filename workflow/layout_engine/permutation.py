"""Reproducible patch-location shuffle + strip/patch index labels.

printtarg keeps its patch *data* in canonical order and only permutes which
sheet *location* each patch lands on, reproducibly from a single seed
(``RANDOM_START``).  ChromIQ owns both the raster and the ``.ti2``, so it needs
its own reproducible permutation rather than Argyll's exact LFSR — Python's
``random.Random`` (Mersenne Twister) is deterministic across platforms and
versions, so the same seed always yields the same layout.

Index labels follow Argyll's odometer: ``A…Z, AA…AZ, BA…BZ`` for alphabetic
patterns (the spreadsheet-column scheme the user described), decimal counting
for numeric patterns.  ``SAMPLE_LOC`` = strip label + patch label, with
``INDEX_ORDER = STRIP_THEN_PATCH``.
"""
from __future__ import annotations

import random

DEFAULT_STRIP_PATTERN = "A-Z, A-Z"
DEFAULT_PATCH_PATTERN = "0-9,@-9,@-9;1-999"

# THE LABELS LIVE IN `labels`, AND FOLLOW ARGYLLCMS (forum report and Knut's
# ruling, #182 5965589190, 2026-10-03). These names stay so every caller keeps
# working; `rule="legacy"` reproduces a chart printed before 4.3.3-beta.7.
from .labels import (ARGYLL, LEGACY, alpha_label,  # noqa: E402,F401
                     legacy_labeller)
from .labels import make_labeller as _make_labeller  # noqa: E402


def make_labeller(pattern: str, rule: str = ARGYLL):
    """Return a 1-based ``int -> str`` labeller for an Argyll index *pattern*.

    ArgyllCMS's own grammar (:mod:`.alphix`), so the sheet, the ``.ti2`` and
    both readers agree for every pattern ArgyllCMS accepts. ``rule="legacy"``
    is ChromIQ's rule before beta 7 (letters when the pattern contains "A-Z",
    otherwise 1, 2, 3 ...), which a redraw of a chart printed with it needs.
    For the two default patterns both rules give the same labels.
    """
    return _make_labeller(pattern, rule)


def location_label(slot: int, steps_in_pass: int,
                   strip_pattern: str = DEFAULT_STRIP_PATTERN,
                   patch_pattern: str = DEFAULT_PATCH_PATTERN,
                   rule: str = ARGYLL) -> str:
    """Label for grid *slot* (0-based, STRIP_THEN_PATCH order).

    Strip = ``slot // steps_in_pass``, position in pass = ``slot % steps_in_pass``.
    """
    if steps_in_pass < 1:
        raise ValueError("steps_in_pass must be >= 1")
    strip_idx, patch_idx = divmod(slot, steps_in_pass)
    strip = make_labeller(strip_pattern, rule)(strip_idx + 1)
    patch = make_labeller(patch_pattern, rule)(patch_idx + 1)
    return f"{strip}{patch}"


def pick_seed(rng: random.Random | None = None) -> int:
    """A fresh full-range seed to show the user after randomising."""
    r = rng or random
    return r.randint(0, 2_147_483_647)


def location_permutation(n: int, seed: int, randomize: bool = True) -> list[int]:
    """Map canonical patch index → sheet slot.

    With *randomize* False this is the identity (A1, A2, A3 … like printtarg
    ``-r``).  With it True the slots are shuffled reproducibly from *seed*.
    """
    slots = list(range(n))
    if randomize:
        random.Random(seed).shuffle(slots)
    return slots


def preview(total: int, steps_in_pass: int,
            strip_pattern: str = DEFAULT_STRIP_PATTERN,
            patch_pattern: str = DEFAULT_PATCH_PATTERN,
            count: int = 12) -> tuple[list[str], str]:
    """First *count* location labels and the last one — for the UI live preview.

    These are the canonical (unshuffled) slot labels, i.e. exactly what gets
    printed and what chartread announces.
    """
    labels = [
        location_label(k, steps_in_pass, strip_pattern, patch_pattern)
        for k in range(total)
    ]
    return labels[:count], (labels[-1] if labels else "")
