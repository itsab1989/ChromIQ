"""THE one place that decides what order ChromIQ shows names in.

Every list of names a person reads — a file dialog, a project picker, a preset
combo, a run list, a generated report — orders itself through `name_sort_key`.
There is deliberately no second rule anywhere.

WHY THIS MODULE EXISTS. Both of the obvious orderings are wrong:

* Python's `sorted()` and Qt's `QSortFilterProxyModel` compare byte by byte, so
  every capital sorts before every lowercase letter. A project folder listed as
  "CR30-Test, Canon-X, ChromIQ-Y, Knut-Z, Zebra" and then, far below, "apple,
  chart, cmyk, knut, test". It was not unsorted — it was two alphabets, one
  after the other (Basti, 2026-09-02). macOS sorts case-insensitively everywhere
  else the person looks.
* A plain `casefold()` compare fixes the case but loses the numbers, and this
  app's working folder is literally `runs/run1/, run2/, …`. Past ten runs a
  `casefold()` sort lists "run1, run10, run11, run2". `QFileSystemModel` gets
  this right (it uses `QCollator` with numeric mode), so a proxy that sorts by
  `casefold()` is *worse* than the model it replaced.

So the rule is: case-insensitive AND numeric-aware, which is what an unproxied
Qt file dialog already shows and therefore what the rest of the app must match.

NO Qt IMPORT. `workflow/` builds reports and exports with no `QApplication`
alive, and they must order names identically to the UI. `QCollator` would also
have to be wrapped in `cmp_to_key` at every call site, and it silently ignores
`setNumericMode(True)` under `QLocale.c()` — a quiet platform-dependent
difference is exactly what this module exists to remove.
"""
from __future__ import annotations

import re

__all__ = ["name_sort_key", "sort_names", "compare_names"]

_DIGITS = re.compile(r"(\d+)")


def name_sort_key(name: str) -> tuple:
    """The key ChromIQ orders names by: case-insensitive, numeric-aware.

    ``sorted(names, key=name_sort_key)`` gives
    ``Alpha, apple, Beta, chart, run1, run2, run10`` — the order the person
    expects and the order an unproxied Qt file dialog already shows.

    EVERY ELEMENT CARRIES ITS KIND. A digit run compares as an `int` and a
    text run as a `casefold()`ed `str`; the moment one name has a number where
    another has a letter, comparing them directly raises `TypeError` and takes
    a file dialog or a report down with it. Tagging each element with `0` for
    numbers and `1` for text makes the comparison total — numbers before text
    at the same position, which is also what `QCollator` does. A test folder
    can pass by luck without this; a user's will not.

    The raw name is appended as the last element so that names differing only
    in case (``Beta.icc`` / ``beta.ti3``, ``knut`` / ``Knut-Z``) get a stable,
    deterministic order instead of an arbitrary one.
    """
    parts: list[tuple[int, int, str]] = []
    for tok in _DIGITS.split(name):
        if not tok:
            continue
        if tok.isdigit():
            parts.append((0, int(tok), ""))
        else:
            parts.append((1, 0, tok.casefold()))
    return (tuple(parts), name)


def sort_names(names, *, key=None) -> list:
    """Sort an iterable into ChromIQ's name order.

    ``key`` extracts the name from each item, for sorting objects by a name
    they carry: ``sort_names(paths, key=lambda p: p.name)``.
    """
    if key is None:
        return sorted(names, key=name_sort_key)
    return sorted(names, key=lambda item: name_sort_key(key(item)))


def compare_names(a: str, b: str) -> int:
    """`-1` / `0` / `1`, for Qt's `lessThan` and anything else wanting a cmp."""
    ka, kb = name_sort_key(a), name_sort_key(b)
    return -1 if ka < kb else (1 if ka > kb else 0)
