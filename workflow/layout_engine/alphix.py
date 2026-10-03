"""ArgyllCMS's location-label grammar ("alphix"), ported exactly, and the checks
that keep a chart's strip and patch patterns readable.

WHY THIS EXISTS (forum report, 2026-10-03). A user typed the strip pattern
"0-9" into Create Chart and got a 14-strip chart that neither ArgyllCMS
chartread nor ChromIQ's own engine could read: "Bad location field value
'(null)' on patch 266". ChromIQ prints labels with its own simple rule
(:func:`permutation.make_labeller`: letters when the pattern contains "A-Z",
otherwise 1, 2, 3 ... without limit) and writes the pattern into the ``.ti2``
verbatim, while both readers parse the locations with ArgyllCMS's
``target/alphix.c``. By Argyll's rules "0-9" is ONE digit with the ten labels
0 to 9, so strip "10" does not exist.

So this module is a line-by-line port of ``alphix.c`` from ArgyllCMS 3.5.0
(``native/instlib/alphix.c`` is the same file): ``new_alphix`` (the grammar),
``torawix`` / ``fromanat`` (label <-> index), the cooked ranges after ";",
``find_start`` and ``patch_location_order`` (how chartread splits and sorts a
location). It is checked against the C file compiled into a harness
(``tests/data/alphix_argyll_table.json`` is frozen from it).

**ChromIQ now labels with it** (Knut, #182 5965589190: "use the rules defined
for the strip and patch patterns defined by ArgyllCMS"). :mod:`.labels` makes
every label of a new chart with this port, and reads labels back with it, so
the sheet, the ``.ti2`` and both readers agree for every pattern ArgyllCMS
accepts. :func:`check_patterns` refuses a pair the readers could not read back
(too few labels, halves that run together), and
:func:`chart_locations_problem` tells the Measure tab, before any reader
starts, whether ArgyllCMS can read a chart already printed. Charts printed
with ChromIQ's old rule keep their labels (:data:`labels.LEGACY`).

**Inputs the C side cannot survive are refused, not reproduced** (``strict``,
the default). ``ti2_writer`` writes ``STRIP_INDEX_PATTERN "{pattern}"`` without
escaping, so a ``"`` breaks the CGATS file; a range ending at character 127
loops for ever in C (``char c; c <= c2; c++``); a non-ASCII byte is a negative
``char``; a range bound longer than the digit count overruns a stack buffer
(``_tb[11]``) in printtarg, chartread and our helper; a digit with no symbols
(``9-0``) gives a pattern with no labels at all; and a pattern whose every digit
can be blank (``@-9``) makes the empty label ``""``, a location nobody can
read.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

#: The C side keeps indices in an ``int``.
_INT_MAX = 2_147_483_647
#: How many all-blank digit combinations the empty-label check will enumerate.
_BLANK_COMBINATIONS_CAP = 100_000


class PatternError(ValueError):
    """A pattern ArgyllCMS cannot use.

    ``kind`` is one of ``"chars"`` (a character outside printable ASCII, or a
    quotation mark), ``"empty"`` (no digit at all), ``"empty_digit"`` (a digit
    with no symbols), ``"range_start"``, ``"range_dash"``, ``"range_end"``,
    ``"range_order"``, ``"range_length"`` (a range bound longer than the
    pattern has digits), ``"too_many"`` (more labels than the C side can count)
    and ``"blank_label"`` (a label with no characters).
    """

    def __init__(self, kind: str, pattern: str, detail: str = "") -> None:
        self.kind = kind
        self.pattern = pattern
        self.detail = detail
        super().__init__(f"alphix: {kind} in {pattern!r}"
                         + (f" ({detail})" if detail else ""))


@dataclass
class _Digit:
    seq: list            # the symbols, in order
    z: bool              # '@' was used: a leading '0' is printed blank
    b: int = 1           # this digit's base


def _check_characters(pattern: str) -> None:
    for ch in pattern:
        o = ord(ch)
        if o < 32 or o > 126 or ch == '"':
            raise PatternError("chars", pattern, repr(ch))


class Alphix:
    """One ArgyllCMS index pattern, e.g. ``"A-Z, A-Z"`` or
    ``"0-9,@-9,@-9;1-999"``.

    :meth:`aix` gives the label of a (0-based, cooked) index, :meth:`nix` the
    index of a label, :meth:`maxlen` the number of labels -- the C object's
    ``aix``, ``nix`` and ``maxlen``.
    """

    def __init__(self, pattern: str, *, strict: bool = True) -> None:
        if strict:
            _check_characters(pattern)
        self.pattern = pattern
        p = pattern
        n = len(p)

        def at(k: int) -> str:              # C's pointer, NUL past the end
            return p[k] if k < n else "\0"

        i = 0
        digits: list[_Digit] = []
        # ---- for all digits -------------------------------------------------
        while True:
            if at(i) in ("\0", ";"):
                break
            seq: list[str] = []
            z = False
            while True:                     # for all symbols in this digit
                if at(i) in ("\0", ";", ","):
                    break
                if at(i + 1) == "-" and at(i + 2) not in ("\0", ";", ","):
                    c1, c2 = at(i), at(i + 2)
                    i += 3
                else:
                    c1 = c2 = at(i)
                    i += 1
                if c1 == "@":
                    c1, z = "0", True
                if c2 == "@":
                    c2, z = "0", True
                seq.extend(chr(o) for o in range(ord(c1), ord(c2) + 1))
            digits.append(_Digit(seq, z))
            if at(i) in ("\0", ";"):
                continue
            i += 1                          # skip the ','
        self.ds = digits
        self.nd = len(digits)
        if strict and self.nd == 0:
            raise PatternError("empty", pattern)
        if strict and any(not d.seq for d in digits):
            raise PatternError("empty_digit", pattern)

        # ---- the native maximum index count ---------------------------------
        rmct = 1
        for d in digits:
            d.b = rmct
            rmct *= len(d.seq)
        self.rmct = rmct
        if strict and rmct > _INT_MAX:
            raise PatternError("too_many", pattern)

        # ---- valid ranges ----------------------------------------------------
        #: (r0, r1, c0, c1): raw start/end and cooked start/end of each range
        self.rs: list[tuple[int, int, int, int]] = []
        if at(i) == ";":
            i += 1
            while True:
                if at(i) in ("\0", ";"):
                    break
                j = i
                while at(i) not in ("\0", "-", ","):
                    i += 1
                start = p[j:i]
                if len(start) > self.nd:
                    # C copies this into a fixed _tb[11] without a bound
                    # first; fromanat would then refuse it anyway.
                    raise PatternError("range_length", pattern, start)
                r0 = self._fromanat(start)
                if r0 < 0:
                    raise PatternError("range_start", pattern, start)
                if at(i) != "-":
                    raise PatternError("range_dash", pattern)
                i += 1
                j = i
                while at(i) not in ("\0", ","):
                    i += 1
                end = p[j:i]
                if len(end) > self.nd:
                    raise PatternError("range_length", pattern, end)
                r1 = self._fromanat(end)
                if r1 < 0:
                    raise PatternError("range_end", pattern, end)
                if r1 < r0:
                    raise PatternError("range_order", pattern)
                c0, c1 = 0, r1 - r0
                if self.rs:
                    ofs = self.rs[-1][3] + 1
                    c0, c1 = c0 + ofs, c1 + ofs
                self.rs.append((r0, r1, c0, c1))
                if at(i) in ("\0", ";"):
                    continue
                i += 1                      # skip the ','

        # ---- cooked actual range ---------------------------------------------
        self.cmct = self.rs[-1][3] + 1 if self.rs else self.rmct
        if strict and self._has_blank_label():
            raise PatternError("blank_label", pattern)

    # ---- the C object's methods ---------------------------------------------
    def maxlen(self) -> int:
        """How many labels the pattern makes (``alphix_maxlen``)."""
        return self.cmct

    def aix(self, ix: int) -> "str | None":
        """The label of cooked index *ix*, or None out of range."""
        ix = self._cookedtoraw(ix)
        if ix < 0:
            return None
        return self._torawix(ix)

    def nix(self, ax: str) -> int:
        """The cooked index of label *ax*, or -1."""
        rv = self._fromanat(ax)
        if rv < 0:
            return -1
        return self._rawtocooked(rv)

    # ---- internals, named after the C functions -----------------------------
    def _torawix(self, ix: int) -> "str | None":
        if ix < 0 or ix >= self.rmct:
            return None
        out: list[str] = []
        started = False
        for d in reversed(self.ds):
            k, ix = divmod(ix, d.b)
            c = d.seq[k]
            if d.z and not started and c == "0":
                c = " "
            if started or c != " ":
                out.append(d.seq[k])
                started = True
        return "".join(out)

    def _fromanat(self, ax: str) -> int:
        if len(ax) > self.nd:
            return -1
        tb = " " * (self.nd - len(ax)) + ax
        rv = 0
        for v, d in zip(tb, reversed(self.ds)):
            for k, c in enumerate(d.seq):
                if v == c or (d.z and v == " " and c == "0"):
                    rv += k * d.b
                    break
            else:
                return -1
        return rv

    def _cookedtoraw(self, ix: int) -> int:
        if not self.rs:
            return ix
        for r0, _r1, c0, c1 in self.rs:
            if c0 <= ix <= c1:
                return ix - c0 + r0
        return -1

    def _rawtocooked(self, ix: int) -> int:
        if not self.rs:
            return ix
        for r0, r1, c0, _c1 in self.rs:
            if r0 <= ix <= r1:
                return ix - r0 + c0
        return -1

    def _find_start(self, ax: str) -> int:
        """Index into *ax* where this pattern's (rightmost) label begins."""
        v = len(ax) - 1
        i = 0
        while v >= 0 and i < self.nd:
            if ax[v] not in self.ds[i].seq:
                break
            v -= 1
            i += 1
        return v + 1

    def _has_blank_label(self) -> bool:
        """Does any label in range come out as ``""``?

        torawix drops every leading symbol that is a space or an '@' zero, so a
        label is empty exactly when EVERY digit holds such a symbol.
        """
        choices = []
        for d in self.ds:
            ks = [k for k, c in enumerate(d.seq)
                  if c == " " or (d.z and c == "0")]
            if not ks:
                return False
            choices.append(ks)
        if math.prod(len(c) for c in choices) > _BLANK_COMBINATIONS_CAP:
            return True              # absurd; refuse rather than enumerate
        raws = [0]
        for d, ks in zip(self.ds, choices):
            raws = [r + k * d.b for r in raws for k in ks]
        return any(self._rawtocooked(r) >= 0 for r in raws)


def patch_location(saix: Alphix, paix: Alphix, ixord: int, six: int,
                   pix: int) -> "str | None":
    """Argyll's location of strip *six*, patch *pix* (``patch_location``)."""
    sl = saix.aix(six)
    if sl is None:
        return None
    pl = paix.aix(pix)
    if pl is None:
        return None
    return sl + pl if ixord == 0 else pl + sl


def patch_location_order(saix: Alphix, paix: Alphix, ixord: int,
                         ax: str) -> int:
    """The sort key chartread gives location *ax*, or -1 when it cannot
    parse it (``patch_location_order``): strip * patches + patch."""
    if ixord == 0:
        lh, rh = saix, paix
    else:
        rh, lh = saix, paix
    v = rh._find_start(ax)
    if v == len(ax):
        return -1
    ri = rh.nix(ax[v:])
    li = lh.nix(ax[:v])
    if ri < 0 or li < 0:
        return -1
    if ixord == 0:
        return li * rh.cmct + ri
    return ri * lh.cmct + li


# ===========================================================================
# Create Chart: may this pattern pair be used for a new layout?
# ===========================================================================

@dataclass(frozen=True)
class PatternProblem:
    """Why a pattern pair cannot be used. ``field`` is ``"strip"``,
    ``"patch"`` or ``""`` (both, or neither in particular); ``reason`` is one
    plain sentence for the user."""
    field: str
    reason: str


class PatternRefused(ValueError):
    """A new layout refused for its patterns; ``str()`` is the reason."""

    def __init__(self, problem: PatternProblem) -> None:
        self.problem = problem
        super().__init__(problem.reason)


def _field_name(field: str) -> str:
    from core.i18n import tr
    return tr("Strip pattern") if field == "strip" else tr("Patch pattern")


def describe_pattern_error(field: str, err: PatternError) -> str:
    """One sentence for a pattern the grammar refuses."""
    from core.i18n import tr
    name = _field_name(field)
    if err.kind == "chars":
        return tr("“{field}” contains a character ArgyllCMS cannot read. Use "
                  "only letters, digits and the symbols on a standard "
                  "keyboard, and no quotation marks.").format(field=name)
    if err.kind == "blank_label":
        return tr("“{pattern}” in “{field}” gives one label no characters at "
                  "all, so that location could not be read.").format(
                      pattern=err.pattern, field=name)
    return tr("ArgyllCMS cannot read “{pattern}” in “{field}”. The help "
              "beside the box explains how a pattern is written.").format(
                  pattern=err.pattern, field=name)


def parse_problem(field: str, pattern: str) -> "PatternProblem | None":
    """The grammar check alone, for a field being typed into: no chart size
    is needed, so the panel can colour the box on every keystroke."""
    try:
        Alphix(pattern)
    except PatternError as err:
        return PatternProblem(field, describe_pattern_error(field, err))
    return None


def check_patterns(strip_pat: str, patch_pat: str, n_strips: int,
                   steps: int) -> "PatternProblem | None":
    """None when both readers can read a NEW chart labelled with this pair;
    otherwise the first reason they cannot, in one sentence.

    *n_strips* counts the strips of EVERY page (both sides number strips
    continuously across pages); *steps* is the patches in a strip
    (``STEPS_IN_PASS``). ArgyllCMS's own rules, nothing else (Knut, #182
    5965589190: letters or numbers on either side, as ArgyllCMS allows):

    * both patterns parse, and are safe for the C side (see :class:`Alphix`);
    * each has a label for every strip / every patch of a strip
      (printtarg refuses the chart otherwise: "strip index %d out of range");
    * every location ``strip label + patch label`` comes back through
      ``patch_location_order`` as its own strip and patch, which is how
      chartread splits and sorts them. Two numeric halves ("1" + "11" and
      "11" + "1") or two letter halves of more than one character cannot be
      told apart, and a randomised chart would be read into the wrong patches.
    """
    from core.i18n import count_phrase, tr

    alph = {}
    for field, pattern in (("strip", strip_pat), ("patch", patch_pat)):
        try:
            alph[field] = Alphix(pattern)
        except PatternError as err:
            return PatternProblem(field, describe_pattern_error(field, err))
    sa, pa = alph["strip"], alph["patch"]
    n_strips = max(0, int(n_strips))
    steps = max(0, int(steps))

    if sa.cmct < n_strips:
        return PatternProblem("strip", tr(
            "“{pattern}” in “{field}” makes only {labels}, and this chart has "
            "{needed}.").format(
                pattern=strip_pat, field=_field_name("strip"),
                labels=count_phrase(sa.cmct, tr("1 label"), tr("{n} labels")),
                needed=count_phrase(n_strips, tr("1 strip"),
                                    tr("{n} strips"))))
    if pa.cmct < steps:
        return PatternProblem("patch", tr(
            "“{pattern}” in “{field}” makes only {labels}, and each strip of "
            "this chart holds {needed}.").format(
                pattern=patch_pat, field=_field_name("patch"),
                labels=count_phrase(pa.cmct, tr("1 label"), tr("{n} labels")),
                needed=count_phrase(steps, tr("1 patch"), tr("{n} patches"))))

    plabels = [pa.aix(p) for p in range(steps)]
    for s in range(n_strips):
        sl = sa.aix(s)
        for p, pl in enumerate(plabels):
            loc = sl + pl
            if patch_location_order(sa, pa, 0, loc) != s * pa.cmct + p:
                return PatternProblem("", tr(
                    "ArgyllCMS cannot tell where the strip label ends and the "
                    "patch label begins in “{loc}”, so the chart could not be "
                    "read correctly.").format(loc=loc))
    return None


def strips_of(total_patches: int, steps: int) -> int:
    """Strips a chart of *total_patches* fills, across every page: the
    ``.ti2`` writer labels slot ``k`` as strip ``k // steps``."""
    steps = max(1, int(steps))
    return max(0, (int(total_patches) + steps - 1) // steps)


# ===========================================================================
# Measure: can the chart in the user's hand be read at all?
# ===========================================================================

_DEFAULT_STRIP = "A-Z, A-Z"            # chartread's own defaults
_DEFAULT_PATCH = "0-9,@-9,@-9;1-999"


def chart_locations_problem(ti2: "str | Path") -> "str | None":
    """None when chartread (stock or ChromIQ's) reads this chart's locations
    the way they are printed; otherwise a short reason.

    Mirrors ``chartread.c`` (and ``chromiq_chartread.c`` 3864-3889,
    4093-4117): the patterns are parsed (an error there ends the run), every
    ``SAMPLE_LOC`` gets ``patch_location_order``; a location that fails ends a
    RANDOMISED chart ("Bad location field value"), and an unrandomised one is
    read in file order. With every location parsed, the patches are sorted by
    that key, so two equal keys make the order a guess.

    A chart ChromIQ laid out is held to more, because its labels came from
    ChromIQ's own rule and not Argyll's: every location must be the label the
    patterns give its strip and patch, inside the chart's strips and steps.
    That catches the charts that parse and are read into the WRONG patches
    without any error (``A-Z, A-Z`` strips with ``A-Z`` patches past 26 steps,
    for one), and the ones whose prompts would name a strip the sheet does not
    show ("0-9" with five strips announces 0 to 4 for a sheet printed 1 to 5).
    A chart with the default patterns passes unchanged.
    """
    from core.i18n import tr
    from core.text_io import read_text

    try:
        text = read_text(Path(ti2), lenient=True)
    except Exception:          # noqa: BLE001 — unreadable is another guard's job
        return None
    from .labels import read_chart_text
    kw, locs = read_chart_text(text)
    if not locs:
        return None
    strip_pat = kw.get("STRIP_INDEX_PATTERN", _DEFAULT_STRIP)
    patch_pat = kw.get("PATCH_INDEX_PATTERN", _DEFAULT_PATCH)
    ixord = 1 if kw.get("INDEX_ORDER") == "PATCH_THEN_STRIP" else 0
    try:
        sa = Alphix(strip_pat)
        pa = Alphix(patch_pat)
    except PatternError:
        return tr("ArgyllCMS cannot read its strip pattern “{strip}” or its "
                  "patch pattern “{patch}”").format(strip=strip_pat,
                                                     patch=patch_pat)
    orders = [patch_location_order(sa, pa, ixord, loc) for loc in locs]
    randomised = "RANDOM_START" in kw
    chromiq = kw.get("ORIGINATOR", "").startswith("ChromIQ")

    if not chromiq:
        bad = [loc for loc, o in zip(locs, orders) if o < 0]
        if bad:
            if randomised:
                return tr("the location “{loc}” does not fit its strip and "
                          "patch patterns").format(loc=bad[0])
            return None                 # read in the order of the file
        seen: dict = {}
        for loc, o in zip(locs, orders):
            if o in seen:
                return tr("the locations “{a}” and “{b}” would be read as the "
                          "same patch").format(a=seen[o], b=loc)
            seen[o] = loc
        return None

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
        n_strips = strips_of(len(locs), steps)
    seen = {}
    for loc, o in zip(locs, orders):
        if o < 0:
            return tr("the location “{loc}” does not fit its strip and patch "
                      "patterns").format(loc=loc)
        s, p = divmod(o, pa.cmct)
        if (steps and p >= steps) or (n_strips and s >= n_strips) \
                or patch_location(sa, pa, ixord, s, p) != loc:
            return tr("the location “{loc}” printed on the sheet is not where "
                      "its strip and patch patterns put it").format(loc=loc)
        if o in seen:
            return tr("the locations “{a}” and “{b}” would be read as the "
                      "same patch").format(a=seen[o], b=loc)
        seen[o] = loc
    return None
