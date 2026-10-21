"""Which strips and patches a measurement is missing, before something is
built from it (Basti, 2026-10-21).

Knut's run 1 of 2026-10-20 ended with Save partial and strip V unread, and
the profile was built from 1917 of the chart's 1944 patches without a word on
screen. Build Profile now asks first (M-BUILD-INCOMPLETE): this module works
out what to name in that window, from the files alone, so it answers for a
measurement the app never watched being made.

"Missing" is the rule of UMM §3a (Knut, #182 6191934889): every square of the
chart, fill-up included, must have a reading; only printtarg's padding is left
out. When the two files cannot be compared by location, nothing is claimed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

_STRIP_LOC = re.compile(r"^([A-Za-z]+)(\d+)$")


@dataclass(frozen=True)
class StripGap:
    """One strip with patches that have no reading."""
    strip: str
    missing: int
    total: int


@dataclass(frozen=True)
class MissingReadings:
    """What a measurement lacks: ``missing`` of the chart's ``expected``
    patches, ``read`` have a reading, ``strips`` names them strip by strip in
    the chart's own order (empty when the patch names carry no strip)."""
    expected: int
    read: int
    missing: int
    strips: "list[StripGap]" = field(default_factory=list)


def _strip_of(loc: str) -> "str | None":
    m = _STRIP_LOC.match(loc.strip())
    return m.group(1) if m else None


def missing_readings(ti3_path: "Path | str | None",
                     ti2_path: "Path | str | None" = None
                     ) -> "MissingReadings | None":
    """The patches of the chart that *ti3_path* holds no reading for, or None
    when it holds them all, or when that cannot be told (no chart beside it, a
    file without patch names, a measurement of another chart). Never raises.
    """
    try:
        if ti3_path is None:
            return None
        ti3 = Path(ti3_path)
        ti2 = Path(ti2_path) if ti2_path is not None else ti3.with_suffix(".ti2")
        if not ti3.is_file() or not ti2.is_file():
            return None
        from workflow.measurement_pairing import chart_locations
        from workflow.measurement_state import (expected_patches,
                                                padding_locations,
                                                unread_locations)
        unread = unread_locations(ti3, ti2)
        if not unread:
            return None
        expected = expected_patches(ti2)
        if not expected:
            return None
        padding = padding_locations(ti2)
        per_strip: "dict[str, int]" = {}
        order: "list[str]" = []
        for loc in chart_locations(ti2):
            if loc in padding:
                continue
            s = _strip_of(loc)
            if s is None:
                continue
            if s not in per_strip:
                per_strip[s] = 0
                order.append(s)
            per_strip[s] += 1
        gaps: "dict[str, int]" = {}
        for loc in unread:
            s = _strip_of(loc)
            if s is not None:
                gaps[s] = gaps.get(s, 0) + 1
        # In the order the sheet prints them (A..Z, AA..), not the file's row
        # order, which a randomised chart shuffles.
        order.sort(key=lambda x: (len(x), x.upper()))
        strips = [StripGap(s, gaps[s], per_strip[s]) for s in order if s in gaps]
        missing = len(unread)
        return MissingReadings(expected=int(expected),
                               read=max(0, int(expected) - missing),
                               missing=missing, strips=strips)
    except Exception:      # noqa: BLE001 — a question, never a blocker
        log.warning("could not tell which patches %s is missing", ti3_path,
                    exc_info=True)
        return None


#: How many strips the window names one by one before it sums up the rest.
LISTED_STRIPS = 12
