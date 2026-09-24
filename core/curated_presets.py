"""Which BUILT-IN presets the Create Chart lists show straight away.

Knut, #182 5818659478 (2026-09-24): *"Users have complained that the current
numbers of presets are too many and they want the amount reduced. This would
though limit an advanced user to have larger charts available."* So nothing is
removed. Every built-in stays in the "Select preset" pulldown and in the
Built-in presets list; the ones that are not ticked wait under a collapsible
arrow placed after the last ticked preset of their group.

Two sources decide what is ticked, and the second always wins:

1. **What ChromIQ ships**, :data:`DEFAULTS_FILE`. A data file, not code, so the
   list Knut's users send back can replace it without touching a line of the
   app. ``scripts/make_preset_defaults.py`` writes it, from the beta rule
   (:func:`beta_selection`) or from a filled-in table.
2. **What this person chose** in the window behind the gear button, stored in
   the setting :data:`SETTING_KEY` as ``{preset key: shown}``.

**ONLY THE PERSON'S OWN DIFFERENCES ARE STORED, NEVER A COPY OF THE
DEFAULTS.** That is what lets a later release change the shipped list without
overwriting anyone: a preset whose box differs from the shipped list keeps the
person's answer, and every other preset follows whatever the release ships.
:func:`store_choices` records a preset exactly while its box differs from the
shipped default, and forgets it the moment the box agrees again (challenge 3
of beta 42, B8-1033): ticking the boxes back to the shipped list by hand left
all 62 of them stored as the person's own answers, so a later release's list
would never have reached that person. A person who opens the window and
closes it without changing anything stores nothing at all.

The key of a preset is its identity (``docs/dev_builtin_presets.md``: *"the
key, not the label, is the identity"*), so renaming a preset keeps both its
shipped default and a person's choice. A stored key that no longer exists is
ignored and kept, harmlessly, in case the preset comes back.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Iterable

from core.logger import get_logger

log = get_logger(__name__)

#: The shipped defaults, relative to the app's resources.
DEFAULTS_FILE = "data/preset_defaults.json"

#: The setting that holds the person's own choices, as a JSON object
#: ``{preset key: bool}``. Empty (the default) means "the shipped list".
SETTING_KEY = "builtin_presets_shown"

#: userData of the arrow row in the "Select preset" pulldown. The group's
#: heading follows the colon. It is not a preset key and never becomes one:
#: :meth:`TabChart._on_preset_selected` refuses it before anything else.
MORE_ROW_PREFIX = "__chromiq_more_presets__:"


def is_more_row(data: Any) -> bool:
    """True for the arrow row's userData, and for nothing a preset carries."""
    return isinstance(data, str) and data.startswith(MORE_ROW_PREFIX)


@lru_cache(maxsize=1)
def shipped_defaults() -> frozenset[str]:
    """The keys ChromIQ ships ticked, read once from :data:`DEFAULTS_FILE`.

    A missing or unreadable file answers "every preset shown" rather than
    "none shown", because an empty pulldown would look like a broken app while
    a long one is merely what every earlier beta did. The caller tells the two
    apart through :func:`defaults_available`.
    """
    from core.resource_path import resource_path
    try:
        doc = json.loads(resource_path(DEFAULTS_FILE).read_text(encoding="utf-8"))
        shown = doc.get("shown", {})
        return frozenset(str(k) for k in shown)
    except (OSError, ValueError, AttributeError, TypeError):
        log.warning("The shipped preset defaults could not be read; every "
                    "built-in preset is shown", exc_info=True)
        return frozenset()


def defaults_available() -> bool:
    return bool(shipped_defaults())


def parse_choices(raw: Any) -> dict[str, bool]:
    """Decode the stored choices; anything malformed is dropped, not raised."""
    if isinstance(raw, dict):
        doc = raw
    else:
        if not raw:
            return {}
        try:
            doc = json.loads(str(raw))
        except (ValueError, TypeError):
            log.warning("Corrupt %s setting, ignoring it", SETTING_KEY)
            return {}
    if not isinstance(doc, dict):
        return {}
    return {str(k): bool(v) for k, v in doc.items() if isinstance(v, bool)}


def user_choices(settings: Any) -> dict[str, bool]:
    try:
        return parse_choices(settings.get(SETTING_KEY, ""))
    except Exception:      # noqa: BLE001 — a settings fake without get()
        return {}


def is_shown_by_default(key: str) -> bool:
    defaults = shipped_defaults()
    return (key in defaults) if defaults else True


def shown_keys(settings: Any, all_keys: Iterable[str]) -> set[str]:
    """The built-ins shown directly: the shipped list, then the person's own
    answers on top."""
    choices = user_choices(settings)
    out = set()
    for key in all_keys:
        if choices.get(key, is_shown_by_default(key)):
            out.add(key)
    return out


def choices_to_store(ticked: Iterable[str], all_keys: Iterable[str],
                     existing: dict[str, bool]) -> dict[str, bool]:
    """What :func:`store_choices` writes, without writing it (the rule above)."""
    ticked = set(ticked)
    out = dict(existing)
    for key in all_keys:
        state = key in ticked
        if state != is_shown_by_default(key):
            out[key] = state
        else:
            # The same as the shipped list is no answer of the person's.
            out.pop(key, None)
    # A key this build does not know is left alone, harmlessly, in case the
    # preset comes back.
    return out


def store_choices(settings: Any, ticked: Iterable[str],
                  all_keys: Iterable[str]) -> bool:
    """Record the window's boxes as the person's choice. Returns whether
    anything was written: nothing is, when what is stored already says it."""
    existing = user_choices(settings)
    out = choices_to_store(ticked, all_keys, existing)
    if out == existing:
        return False
    if out:
        settings.set(SETTING_KEY, json.dumps(out, sort_keys=True))
        return True
    # Nothing of the person's is left: no answer stored at all, exactly as
    # before the window was first opened.
    unset = getattr(settings, "unset", None)
    if callable(unset):
        unset(SETTING_KEY)
    else:
        settings.set(SETTING_KEY, "")
    return True


def split_group(entries: list, shown: set[str]) -> tuple[list, list]:
    """``(ticked, the rest)`` of one group's ``(combo, overlay, key)`` rows, each
    in the group's own order. The arrow goes between the two."""
    top = [e for e in entries if e[2] in shown]
    rest = [e for e in entries if e[2] not in shown]
    return top, rest


# ---------------------------------------------------------------------------
# The beta rule
# ---------------------------------------------------------------------------

#: How many presets the beta rule ticks per instrument group and paper size.
BETA_PER_PAPER = 4
#: Page counts the beta rule may tick: one to four sheets.
BETA_PAGES = (1, 4)


def beta_selection(facts: list[dict]) -> list[str]:
    """Knut's rule for the beta, #182 5818659478: *"pre-select 4 presets for
    each type of paper size and instrument, so that the 4 selected are between
    1 and 4 pages with different patch sizes, but skipping the smallest and the
    largest presets."*

    ``facts`` holds one dict per built-in: ``key``, ``group``, ``paper``,
    ``patches``, ``pages`` and ``width`` (patch width in mm, 0 when the chart
    does not say). Returned in the order given.

    Per (group, paper):

    1. Sort by patch count (then pages, then width, then key, so it is stable).
    2. When the paper has MORE than four presets, drop the one with the fewest
       patches and the one with the most. "Smallest" and "largest" are read as
       patch count, which is what a chart's size is to the person reading it.
       A paper with four or fewer keeps them all: dropping two of three would
       leave a paper with nothing shown.
    3. Keep the ones of one to four sheets.
    4. Four or fewer left: all of them. More: cut the list, still sorted by
       patch count, into four consecutive bands of near-equal length and take
       one per band, so the four spread from small to large. Inside a band the
       pick is the preset whose patch WIDTH is not yet among the picks (so the
       widths differ wherever the paper offers more than one), then the one
       nearest the band's middle.
    """
    by_cell: dict[tuple[str, str], list[dict]] = {}
    for f in facts:
        by_cell.setdefault((f["group"], f["paper"]), []).append(f)
    chosen: set[str] = set()
    for cell in by_cell.values():
        rows = sorted(cell, key=lambda f: (f["patches"], f["pages"],
                                           f.get("width") or 0.0, f["key"]))
        if len(rows) > BETA_PER_PAPER:
            rows = rows[1:-1]
        lo, hi = BETA_PAGES
        rows = [f for f in rows if lo <= f["pages"] <= hi]
        if len(rows) <= BETA_PER_PAPER:
            chosen.update(f["key"] for f in rows)
            continue
        n = len(rows)
        widths: set[float] = set()
        for b in range(BETA_PER_PAPER):
            start = (b * n) // BETA_PER_PAPER
            end = ((b + 1) * n) // BETA_PER_PAPER
            band = rows[start:end]
            mid = (len(band) - 1) / 2.0
            best = min(range(len(band)), key=lambda i: (
                (band[i].get("width") or 0.0) in widths, abs(i - mid), i))
            pick = band[best]
            widths.add(pick.get("width") or 0.0)
            chosen.add(pick["key"])
    return [f["key"] for f in facts if f["key"] in chosen]
