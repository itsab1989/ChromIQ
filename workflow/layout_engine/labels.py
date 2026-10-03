"""The one place a chart's strip and patch LABELS are made and read back.

Forum report, 2026-10-03, and Knut's ruling the same day (#182 5965589190):
*"it shall be possible to switch the running number and alphabetic labels, and
use the rules defined for the strip and patch patterns defined by ArgyllCMS."*

So ChromIQ labels a NEW chart exactly as ArgyllCMS's printtarg would, from the
two patterns, with the grammar ported in :mod:`.alphix` (rule ``"argyll"``).
Every chart printed before that carries the labels of ChromIQ's old rule
(``"legacy"``: letters A, B ... AA when the pattern contains "A-Z", otherwise
1, 2, 3 ... without limit). For the two DEFAULT patterns the two rules give
the same labels over Argyll's whole range, so nearly every chart in existence
reads the same either way; only a chart made with another pattern differs, and
it keeps the labels it was printed with.

Which rule a stored chart was made with is read from the chart itself
(:func:`labels_for_chart`): its SAMPLE_LOCs are compared with the grid each rule
gives its patterns, so nothing has to have been recorded at the time.

Code that needs to know which strip or patch a location names asks a
:class:`ChartLabels` (``split``, ``strip_index``), never a regular expression:
a numeric strip ("12") followed by a letter patch ("C") is "12C", and "A1"
could be strip 0 patch 0 or, under other patterns, strip 26 patch 1.
"""
from __future__ import annotations

import functools
import re
from pathlib import Path

from . import alphix

ARGYLL = "argyll"
LEGACY = "legacy"

DEFAULT_STRIP_PATTERN = "A-Z, A-Z"
DEFAULT_PATCH_PATTERN = "0-9,@-9,@-9;1-999"


# ---- ChromIQ's old rule, kept for charts printed with it --------------------
def alpha_label(n: int) -> str:
    """1-based spreadsheet-column label: 1→A, 26→Z, 27→AA, 52→AZ, 53→BA …"""
    if n < 1:
        raise ValueError("alpha_label is 1-based")
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(ord("A") + rem) + out
    return out


def alpha_index(label: str) -> int:
    """0-based inverse of :func:`alpha_label`; -1 for anything else."""
    if not label or not label.isalpha() or not label.isascii():
        return -1
    idx = 0
    for c in label.upper():
        idx = idx * 26 + (ord(c) - ord("A") + 1)
    return idx - 1


def legacy_is_alpha(pattern: str) -> bool:
    return "A-Z" in (pattern or "").upper()


def legacy_labeller(pattern: str):
    """ChromIQ's labels before 4.3.3-beta.7, 1-based: letters when the pattern
    contains "A-Z", otherwise decimal counting from 1."""
    if legacy_is_alpha(pattern):
        return alpha_label
    return lambda n: str(n)


# ---- Argyll's rule ----------------------------------------------------------
@functools.lru_cache(maxsize=256)
def _alphix(pattern: str) -> "alphix.Alphix | None":
    try:
        return alphix.Alphix(pattern)
    except alphix.PatternError:
        return None


def argyll_labeller(pattern: str):
    """1-based labels exactly as ArgyllCMS makes them; ``""`` past the last
    label. A pattern ArgyllCMS cannot read at all (a box half typed) falls
    back to the old rule, so a width probe or a preview never fails on it:
    no chart is ever BUILT from such a pattern (``alphix.check_patterns``)."""
    a = _alphix(pattern)
    if a is None:
        return legacy_labeller(pattern)

    def label(n: int) -> str:
        if n < 1:
            raise ValueError("labels are 1-based")
        v = a.aix(n - 1)
        return v if v is not None else ""
    return label


def make_labeller(pattern: str, rule: str = ARGYLL):
    """A 1-based ``int -> str`` labeller for *pattern* under *rule*."""
    if rule == LEGACY:
        return legacy_labeller(pattern)
    return argyll_labeller(pattern)


# ---- reading labels back ----------------------------------------------------
class ChartLabels:
    """A chart's strip and patch labels: made, and read back.

    Indices are 0-based. *n_strips* (every page together) and *steps* (patches
    in a strip) are only needed to read the old rule's labels where its two
    halves cannot be told apart by their characters (both letters, or both
    digits).
    """

    def __init__(self, strip_pattern: str = DEFAULT_STRIP_PATTERN,
                 patch_pattern: str = DEFAULT_PATCH_PATTERN, *,
                 rule: str = ARGYLL, ixord: int = 0, n_strips: int = 0,
                 steps: int = 0) -> None:
        self.strip_pattern = strip_pattern or DEFAULT_STRIP_PATTERN
        self.patch_pattern = patch_pattern or DEFAULT_PATCH_PATTERN
        self.ixord = 1 if ixord else 0
        self.n_strips = max(0, int(n_strips or 0))
        self.steps = max(0, int(steps or 0))
        sa, pa = _alphix(self.strip_pattern), _alphix(self.patch_pattern)
        # Argyll's rule needs both patterns readable; a chart whose pattern
        # Argyll refuses can only have been labelled by the old rule.
        self.rule = rule if (rule == LEGACY or (sa and pa)) else LEGACY
        self._sa, self._pa = sa, pa
        self._legacy_grid: "dict[str, tuple[int, int]] | None" = None

    # -- making --
    def strip(self, i: int) -> "str | None":
        if i < 0:
            return None
        if self.rule == LEGACY:
            return legacy_labeller(self.strip_pattern)(i + 1)
        return self._sa.aix(i)

    def patch(self, p: int) -> "str | None":
        if p < 0:
            return None
        if self.rule == LEGACY:
            return legacy_labeller(self.patch_pattern)(p + 1)
        return self._pa.aix(p)

    def location(self, s: int, p: int) -> "str | None":
        sl, pl = self.strip(s), self.patch(p)
        if sl is None or pl is None:
            return None
        return sl + pl if self.ixord == 0 else pl + sl

    # -- reading --
    def strip_index(self, label: str) -> int:
        """0-based index of a strip label, or -1."""
        label = (label or "").strip()
        if not label:
            return -1
        if self.rule == LEGACY:
            if legacy_is_alpha(self.strip_pattern):
                return alpha_index(label)
            return int(label) - 1 if label.isdigit() and int(label) > 0 else -1
        return self._sa.nix(label)

    def patch_index(self, label: str) -> int:
        """0-based index of a patch label within its strip, or -1."""
        label = (label or "").strip()
        if not label:
            return -1
        if self.rule == LEGACY:
            if legacy_is_alpha(self.patch_pattern):
                return alpha_index(label)
            return int(label) - 1 if label.isdigit() and int(label) > 0 else -1
        return self._pa.nix(label)

    def split(self, loc: str) -> "tuple[int, int] | None":
        """(strip, patch) of location *loc*, 0-based, or None."""
        loc = (loc or "").strip()
        if not loc:
            return None
        if self.rule == ARGYLL:
            o = alphix.patch_location_order(self._sa, self._pa, self.ixord, loc)
            if o < 0:
                return None
            return divmod(o, self._pa.cmct)
        return self._legacy_split(loc)

    def strip_of(self, loc: str) -> "str | None":
        """The strip LABEL a location belongs to, as the chart prints it."""
        sp = self.split(loc)
        return self.strip(sp[0]) if sp is not None else None

    def _legacy_split(self, loc: str) -> "tuple[int, int] | None":
        s_alpha = legacy_is_alpha(self.strip_pattern)
        p_alpha = legacy_is_alpha(self.patch_pattern)
        if s_alpha != p_alpha:
            first = r"[A-Za-z]+" if s_alpha else r"\d+"
            second = r"\d+" if s_alpha else r"[A-Za-z]+"
            if self.ixord:
                first, second = second, first
            m = re.fullmatch(f"({first})({second})", loc)
            if not m:
                return None
            a, b = m.group(1), m.group(2)
            sl, pl = (a, b) if self.ixord == 0 else (b, a)
            s, p = self.strip_index(sl), self.patch_index(pl)
            if s < 0 or p < 0:
                return None
            return s, p
        # Both halves the same kind: only the grid can tell them apart, and a
        # label the grid makes twice ("1" + "11" and "11" + "1") is nobody's.
        if self._legacy_grid is None:
            grid: dict = {}
            for s in range(self.n_strips):
                for p in range(self.steps):
                    loc_sp = self.location(s, p)
                    grid[loc_sp] = None if loc_sp in grid else (s, p)
            self._legacy_grid = grid
        return self._legacy_grid.get(loc)


# ---- which rule made a stored chart -----------------------------------------
_KW_RE = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s+"([^"]*)"\s*$')


def read_chart_text(text: str) -> "tuple[dict, list[str]]":
    """Keywords and SAMPLE_LOC values of the first CGATS table in *text*."""
    kw: dict = {}
    fields: list[str] = []
    locs: list[str] = []
    state = "head"
    for raw in text.splitlines():
        line = raw.strip()
        if state in ("head", "between"):
            if state == "head" and line == "BEGIN_DATA_FORMAT":
                state = "format"
                continue
            if state == "between" and line == "BEGIN_DATA":
                state = "data"
                continue
            m = _KW_RE.match(raw)
            if m and m.group(1) not in kw:
                kw[m.group(1)] = m.group(2)
        elif state == "format":
            if line == "END_DATA_FORMAT":
                state = "between"
                continue
            fields.extend(line.split())
        elif state == "data":
            if line == "END_DATA":
                break
            if not line or "SAMPLE_LOC" not in fields:
                continue
            toks = re.findall(r'"[^"]*"|\S+', line)
            k = fields.index("SAMPLE_LOC")
            if k < len(toks):
                locs.append(toks[k].strip('"'))
    return kw, locs


def _chart_counts(kw: dict, n_locs: int) -> "tuple[int, int]":
    try:
        steps = int(kw.get("STEPS_IN_PASS", "0") or 0)
    except ValueError:
        steps = 0
    try:
        n_strips = sum(int(x) for x in
                       kw.get("PASSES_IN_STRIPS2", "").split(",") if x.strip())
    except ValueError:
        n_strips = 0
    if n_strips <= 0 and steps > 0:
        n_strips = (n_locs + steps - 1) // steps
    return n_strips, steps


def labels_from_text(text: str) -> ChartLabels:
    """The :class:`ChartLabels` a chart file's text was labelled with."""
    kw, locs = read_chart_text(text)
    return labels_from_keywords(kw, locs)


def labels_from_keywords(kw: dict, locs: "list[str]") -> ChartLabels:
    strip_pat = kw.get("STRIP_INDEX_PATTERN") or DEFAULT_STRIP_PATTERN
    patch_pat = kw.get("PATCH_INDEX_PATTERN") or DEFAULT_PATCH_PATTERN
    ixord = 1 if kw.get("INDEX_ORDER") == "PATCH_THEN_STRIP" else 0
    n_strips, steps = _chart_counts(kw, len(locs))
    common = dict(ixord=ixord, n_strips=n_strips, steps=steps)
    argyll = ChartLabels(strip_pat, patch_pat, rule=ARGYLL, **common)
    if argyll.rule == ARGYLL and _fits(argyll, locs):
        return argyll
    legacy = ChartLabels(strip_pat, patch_pat, rule=LEGACY, **common)
    if locs and _fits(legacy, locs):
        return legacy
    # Neither grid: a chart from elsewhere. ArgyllCMS's own reading is the
    # one every reader applies to it.
    return argyll if argyll.rule == ARGYLL else legacy


def _fits(cl: ChartLabels, locs: "list[str]") -> bool:
    for loc in locs:
        sp = cl.split(loc)
        if sp is None or cl.location(*sp) != loc:
            return False
        s, p = sp
        if (cl.n_strips and s >= cl.n_strips) or (cl.steps and p >= cl.steps):
            return False
    return True


@functools.lru_cache(maxsize=64)
def _labels_cached(path: str, mtime_ns: int, size: int) -> ChartLabels:
    from core.text_io import read_text
    return labels_from_text(read_text(Path(path), lenient=True))


def labels_for_chart(ti2: "str | Path | None") -> ChartLabels:
    """The labels of the chart file *ti2* (or the default labels, when there
    is no readable file)."""
    try:
        p = Path(ti2) if ti2 else None
        if p is None or not p.is_file():
            return ChartLabels()
        st = p.stat()
        return _labels_cached(str(p), st.st_mtime_ns, st.st_size)
    except Exception:          # noqa: BLE001 — labels never block a caller
        return ChartLabels()


def labels_for_measurement(ti3: "str | Path | None") -> ChartLabels:
    """The labels of the chart a measurement was read from: the ``.ti2`` with
    the same stem beside it, else the only ``.ti2`` in its folder. A ``.ti3``
    carries locations but not the patterns that made them."""
    try:
        p = Path(ti3) if ti3 else None
        if p is None:
            return ChartLabels()
        same = p.with_suffix(".ti2")
        if same.is_file():
            return labels_for_chart(same)
        found = sorted(p.parent.glob("*.ti2")) if p.parent.is_dir() else []
        if len(found) == 1:
            return labels_for_chart(found[0])
    except Exception:          # noqa: BLE001
        pass
    return ChartLabels()


def location_key(cl: ChartLabels, loc: str) -> "tuple[int, int] | None":
    """(strip, patch) of *loc* when *cl* explains it exactly, else None."""
    sp = cl.split(loc)
    if sp is None or cl.location(*sp) != (loc or "").strip():
        return None
    return sp


def legacy_reading(ti2: "str | Path | None") -> "ChartLabels | None":
    """The old rule's labels for a chart ChromIQ printed with them, when they
    explain every location of the chart exactly; else None.

    That is the reading ChromIQ's engine applies to such a sheet, so a None
    here means no reader at all can measure it."""
    try:
        from core.text_io import read_text
        kw, locs = read_chart_text(read_text(Path(ti2), lenient=True))
    except Exception:          # noqa: BLE001
        return None
    if not locs or not str(kw.get("ORIGINATOR", "")).startswith("ChromIQ"):
        return None
    n_strips, steps = _chart_counts(kw, len(locs))
    cl = ChartLabels(kw.get("STRIP_INDEX_PATTERN") or DEFAULT_STRIP_PATTERN,
                     kw.get("PATCH_INDEX_PATTERN") or DEFAULT_PATCH_PATTERN,
                     rule=LEGACY,
                     ixord=1 if kw.get("INDEX_ORDER") == "PATCH_THEN_STRIP" else 0,
                     n_strips=n_strips, steps=steps)
    if not _fits(cl, locs) or len({cl.split(x) for x in locs}) != len(locs):
        return None
    return cl


def label_rule_of_chart(ti2: "str | Path | None") -> str:
    """``"legacy"`` for a chart printed with ChromIQ's old rule, else
    ``"argyll"``. A redraw of a stored chart passes this to the build, so the
    sheet that comes back carries the labels the measurement was made with."""
    return labels_for_chart(ti2).rule
