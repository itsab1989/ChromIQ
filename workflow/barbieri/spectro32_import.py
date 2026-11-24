"""Bringing back a Spectro32 measurement of a Barbieri Spectro 100xy chart
(the Barbieri Beta, step 2: the IMPORT module of the Measure tab).

WHAT SPECTRO32 SAVES. Barbieri's program for the 100xy writes one set of text
files per run, each name starting with the run's name (an owner's real run of
896 patches, issue 215; read as data only):

* ``<run>_measurements.txt``: a header ``ReadingNumber Spec_380 ... Spec_780
  X Y Z x y L a b u v Dens_...`` and one tab-separated line per reading,
  numbered from 1;
* ``<run>_VAL.txt``: the same values without the number column, under a
  header of wavelengths, the template's name and Spectro32's colour setting
  (``D50  2``);
* ``<run>_spectrum.txt``: the 41 spectral values only, one line per reading;
* ``<run>_XYZ.txt``, ``<run>_LAB.txt``, ``<run>_DENS.txt``: colour values
  only, with the same short header.

The spectra are fractions (a perfect white is 1.0), 41 bands from 380 to
780 nm in 10 nm steps; X, Y, Z are on the 0 to 100 scale. Nothing in the
files names a patch: **the reading order is the only link** between a reading
and its patch.

HOW A READING FINDS ITS PATCH. By its position in the file, through the
chart's side file ``<stem>.barbieri.json`` (`workflow.barbieri.chart`), which
holds every page's patch names in the order the table reads them (row by row
from the top, each row from the left, never back and forth). The side file
is tied to the chart by the ``.ti2``'s SHA-256. Never by colour (§I.9).

THE SAFETY NET. The colours only decide whether the file is filed, never where
a reading goes. Nothing is ever corrected:

1. the file is read strictly: 41 bands, a number in every place (a failed
   reading is refused, never filled in), readings numbered 1, 2, 3 without a
   gap, spectra on Spectro32's 0 to 1 scale;
2. the count must be the page's cell count exactly, and a chart of several
   pages needs one file per page, each matched to its page by its colours;
3. the arrangement: the chart's expected colours (the ``.ti2``'s XYZ) are
   fitted to the readings for the sheet as it should lie and for the
   arrangements a person can make by mistake (mirrored, upside down, turned
   half round, aimed one patch off in any direction). On the owner's real
   chart the right arrangement left 0.15 of the readings' spread, every wrong
   one 0.98 to 1.0. A clearly better wrong arrangement is refused and named;
4. where the fit cannot tell (a sorted chart), the check patches at the
   corners decide (`chart.check_order`: the darkest patch at A1, the most
   colourful at the aim patch, the lightest at the lower left); where they
   cannot either, the person is ASKED (§I.17), never filed in silence;
5. the colours are computed from the spectra as ArgyllCMS computes them
   (D50, 1931 2 degree, `workflow.argyll_colorimetry`) and compared with the
   XYZ / Lab Spectro32 saved: on the owner's 896 readings they agree to
   0.014 dE76 at most. Another Spectro32 colour setting is recognised and only
   said; a disagreement nothing explains is asked about.

TRANSMISSION. ArgyllCMS's chartread writes a transmission reading exactly as
a reflection reading (`spectro/chartread.c` 3.5.0 adds no keyword for it):
the spectral transmittance in percent and its XYZ under D50 with a perfect
transmitter at Y = 100. So does this module; the side file's opening says
which it was, and the filed copy records it in ``CHROMIQ_BARBIERI_MODE``.

PROVENANCE. The reading of Spectro32's files follows the converter
``barbieri_to_ti3.py`` 1.1 by LVTguru (archive "Barbieri-to-TI3-1.1", the
same file in "Barbieri-Chart-Tools-1.0"; issue 215 of the ChromIQ repository,
offered for use under ChromIQ's GPL-3.0 licence in the comment of 2026-11-18).
Adapted from it, reviewed like contributor code and rewritten in this
module's own terms: the header handling of ``read_measurements`` (the
``ReadingNumber`` / ``Spec_380`` / bare wavelength headers, the colour-setting
line before the first row, the template name line of a ``_VAL.txt``), the
rule that reading numbers run from 1 without a gap, the ``.ti2`` locations as
column letters and row numbers, the refusal of spectra above 2 on the fraction
scale, and the fraction-to-percent scaling of the spectra. Not taken: his
optional orders (column, reversed, serpentine), his copying of Spectro32's XYZ
(ChromIQ computes it from the spectra), his refusal of other colour settings
(the spectra do not depend on them) and his file chooser.

Off = unchanged: this module is imported only when the Barbieri Beta is on,
the run's chart is a Barbieri chart with its side file, and the picked file
is a Spectro32 file (`route_applies`, `looks_like_spectro32`).
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from core.logger import get_logger

log = get_logger(__name__)

#: Spectro32's bands (the owner's files; the 2002 to 2004 datasheets give
#: 380 to 780 nm).
WAVELENGTHS = tuple(range(380, 781, 10))
BANDS = len(WAVELENGTHS)

#: Header keyword of a filed copy: which side file and order paired it.
PAIRED_KEYWORD = "CHROMIQ_PAIRED_BY_BARBIERI_ORDER"
#: Header keyword of a filed copy: reflection or transmission (the opening).
MODE_KEYWORD = "CHROMIQ_BARBIERI_MODE"
#: Header keyword: the opening (`chart_facts.Head.key`).
HEAD_KEYWORD = "CHROMIQ_BARBIERI_HEAD"
#: How the XYZ was computed (as `reference_convert.XYZ_METHOD_ARGYLL`).
XYZ_METHOD = "ArgyllCMS xspect, D50, 1931 2 degree, 1 nm"

#: Spectro32 writes fractions; a value above this is on another scale (the
#: owner's converter's own limit: a fluorescent white reads a little above
#: 1, never near 2).
SCALE_LIMIT = 2.0
#: A spectral value below this is not noise around a black patch (his
#: darkest reading: 0.027) but a failed reading or an edited file.
NEGATIVE_LIMIT = -0.05

#: The XYZ cross-check. Spectro32's own colours agreed with ArgyllCMS's
#: method on the owner's 896 readings to 0.0044 dE76 on average and 0.014 at
#: most (2026-11-24); a different but valid integration of 10 nm data (10 nm
#: sums against 1 nm Lagrange) differs by up to 0.15 (argyll_colorimetry's
#: own measurement). 0.5 keeps three times that; every wrong setting
#: measured on the same readings is far above it (D50 / 10 degree 4.6 dE76
#: median, D65 / 2 degree 12.9, spectra shifted by one band 6.6).
XYZ_AGREE_DE = 0.5
#: Spectro32 colour settings recognised when its colours disagree with D50 /
#: 2 degree (ArgyllCMS's names).
OTHER_SETTINGS = (("D65", "1931_2"), ("D50", "1964_10"), ("D65", "1964_10"),
                  ("A", "1931_2"), ("C", "1931_2"), ("A", "1964_10"),
                  ("C", "1964_10"))

#: The arrangement check (the fit of expected colours to the readings).
#: Medians of the residual divided by the readings' spread, measured on the
#: owner's real chart (`probe/fit_probe.py`): the sheet as it lay 0.15, every
#: mirrored, flipped, turned or shifted arrangement 0.98 to 1.0. The i1iO
#: import uses the same three numbers (`workflow.i1io.measure_chart`).
FIT_RATIO = 0.6
FIT_ABSURD = 0.5
QUADRATIC_FROM = 64
#: Two arrangements whose expected colours differ by less than this (median
#: dE76 over the cells that move) cannot be told apart by the fit.
SELF_MAP_DE = 3.0
#: The check patches: each is PREDICTED from an affine map fitted on the
#: other patches, and an arrangement is ruled out when its prediction error
#: at the check patches is at least CHECK_RATIO times the straight one's and
#: at least CHECK_MIN_DE. Measured on engine charts of 120, 300 and 896
#: patches read through the tests' synthetic printer (2026-11-24): the sheet
#: as it lay 11.9 to 13.3 dE76 (the affine map's reach to the extremes),
#: mirrored or upside down 34.4 to 47.5.
CHECK_RATIO = 2.0
CHECK_MIN_DE = 15.0

#: The arrangements, in the order a refusal names them first.
ARRANGEMENTS = ("mirrored", "upside-down", "turned", "right", "left", "up",
                "down")


class Spectro32Refused(ValueError):
    """A file that cannot be filed; ``code`` and ``kw`` name the reason
    (`measurement_messages.barbieri_import_reason`)."""

    def __init__(self, code: str, **kw):
        super().__init__(code)
        self.code = code
        self.kw = kw

    def reason(self) -> str:
        from workflow import measurement_messages as MM
        return MM.barbieri_import_reason(self.code, **self.kw)


# ---------------------------------------------------------------------------
# the route
# ---------------------------------------------------------------------------

def route_applies(chart_ti2) -> bool:
    """True when the Barbieri Beta is on and *chart_ti2* is a Barbieri chart
    with its side file. Reads the switch first: with the Beta off nothing is
    opened at all."""
    if chart_ti2 is None:
        return False
    from workflow.barbieri import support
    if not support.barbieri_enabled():
        return False
    if support.chart_names_barbieri(chart_ti2) is not True:
        return False
    return support.side_file_for(chart_ti2).is_file()


def page_count(chart_ti2) -> int:
    """The pages of a Barbieri chart (its side file), 0 when unknown."""
    from workflow.barbieri import support
    doc = support.read_side_file(chart_ti2) or {}
    return len(doc.get("pages_detail") or [])


# ---------------------------------------------------------------------------
# reading a file
# ---------------------------------------------------------------------------

_SETTING_RE = re.compile(r"^(D\d\d|A|C|E|F\d{1,2})\s+(2|10)$", re.I)
_NUMBER_RE = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")
_COLOUR_ONLY_HEADS = ("lab", "xyz", "xyz100", "density")


@dataclass
class S32File:
    """One Spectro32 file, read."""
    path: Path
    kind: str                      # "measurements" | "val" | "spectrum"
    spectra: np.ndarray            # (n, 41) fractions
    xyz: "np.ndarray | None" = None    # Spectro32's own, Y = 100
    lab: "np.ndarray | None" = None
    setting: "tuple[str, str] | None" = None   # ("D50", "2")
    template: str = ""
    sha256: str = ""
    decimal_comma: bool = False
    companions: "list[str]" = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(self.spectra.shape[0])

    @property
    def name(self) -> str:
        return self.path.name


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _split(line: str) -> "list[str]":
    line = line.strip("\r\n")
    if "\t" in line:
        return [t.strip() for t in line.strip().split("\t") if t.strip() != ""]
    return line.split()


def _is_number(tok: str) -> bool:
    return bool(_NUMBER_RE.match(tok))


def _wavelength(name: str) -> "int | None":
    m = re.fullmatch(r"(?:spec_?)?(\d{3})(?:\.0+)?", name.strip(), re.I)
    return int(m.group(1)) if m else None


def looks_like_spectro32(path) -> bool:
    """A cheap look at the first lines: a Spectro32 measurement, VAL,
    spectrum or colour file. Never raises."""
    try:
        with open(path, "rb") as fh:
            head = _decode(fh.read(4096))
    except (OSError, TypeError, ValueError):
        return False
    lines = [ln for ln in head.splitlines() if ln.strip()]
    if not lines:
        return False
    first = _split(lines[0])
    if not first:
        return False
    if first[0].lower() == "readingnumber":
        return True
    if _wavelength(first[0]) == 380 and len(first) >= BANDS:
        return True
    if lines[0].strip().lower() in _COLOUR_ONLY_HEADS or \
            lines[0].strip().lower().startswith("density values"):
        return True
    # a bare spectrum file: 41 numbers on each of its first lines
    return all(len(_split(ln)) == BANDS and all(_is_number(t) for t in
                                                 _split(ln))
               for ln in lines[:3])


def _num(tok: str, *, reading: int, column: str, name: str,
         commas: list) -> float:
    t = tok.strip()
    if _NUMBER_RE.match(t):
        if "," in t:
            commas.append(1)
            t = t.replace(",", ".")
        v = float(t)
        if math.isfinite(v):
            return v
    raise Spectro32Refused("failed-value", name=name, reading=reading,
                           column=column, text=tok.strip()[:24])


def read_file(path) -> S32File:
    """Read one Spectro32 file strictly; :class:`Spectro32Refused` with the
    reason when it cannot be used."""
    path = Path(path)
    name = path.name
    try:
        data = path.read_bytes()
    except OSError:
        raise Spectro32Refused("not-spectro32", name=name) from None
    text = _decode(data)
    lines = text.splitlines()
    nonblank = [(i, ln) for i, ln in enumerate(lines, 1) if ln.strip()]
    if not nonblank:
        raise Spectro32Refused("empty", name=name)
    first_no, first = nonblank[0]
    head = _split(first)
    low = first.strip().lower()
    if low in _COLOUR_ONLY_HEADS or low.startswith("density values"):
        raise Spectro32Refused("colours-only", name=name)
    kind = ""
    columns: "list[str]" = []
    if head and head[0].lower() == "readingnumber":
        kind, columns = "measurements", head
    elif head and _wavelength(head[0]) == 380:
        kind, columns = "val", ["ReadingNumber"] + head
    elif head and all(_is_number(t) for t in head):
        kind = "spectrum"
    else:
        raise Spectro32Refused("not-spectro32", name=name)

    commas: list = []
    setting = None
    template = ""
    rows: "list[list[str]]" = []
    row_lines: "list[int]" = []
    body = nonblank if kind == "spectrum" else nonblank[1:]
    for line_no, ln in body:
        parts = _split(ln)
        if kind != "spectrum" and not rows and len(parts) < 5:
            # the template's name and the colour setting above the rows
            m = _SETTING_RE.match(ln.strip())
            if m:
                setting = (m.group(1).upper(), m.group(2))
            elif not template:
                template = ln.strip()[:120]
            continue
        rows.append(parts)
        row_lines.append(line_no)
    if not rows:
        raise Spectro32Refused("empty", name=name)

    # which column is which
    if kind == "spectrum":
        width = len(rows[0])
        spec_idx = list(range(width))
        if width != BANDS:
            raise Spectro32Refused("bands", name=name, count=width)
        xyz_idx = lab_idx = None
        num_idx = None
        expected = width
    else:
        nm = [_wavelength(c) for c in columns]
        spec_idx = [i for i, w in enumerate(nm) if w is not None]
        got = [nm[i] for i in spec_idx]
        if tuple(got) != WAVELENGTHS:
            raise Spectro32Refused("bands", name=name, count=len(got))
        upper = [c.strip() for c in columns]

        def find(*names):
            idx = [upper.index(n) if n in upper else None for n in names]
            return None if any(i is None for i in idx) else idx
        xyz_idx = find("X", "Y", "Z")
        lab_idx = find("L", "a", "b")
        num_idx = 0 if kind == "measurements" else None
        expected = len(columns) - (1 if kind == "val" else 0)
        if kind == "val":
            # no number column in the rows: shift the indices
            spec_idx = [i - 1 for i in spec_idx]
            xyz_idx = [i - 1 for i in xyz_idx] if xyz_idx else None
            lab_idx = [i - 1 for i in lab_idx] if lab_idx else None

    spectra, xyz, lab = [], [], []
    for k, (parts, line_no) in enumerate(zip(rows, row_lines), 1):
        if len(parts) != expected:
            raise Spectro32Refused("row-shape", name=name, line=line_no)
        if num_idx is not None:
            got = _num(parts[num_idx], reading=k, column="ReadingNumber",
                       name=name, commas=commas)
            if got != k:
                raise Spectro32Refused("numbering", name=name,
                                       previous=k - 1, reading=_shown(got))
        sp = [_num(parts[i], reading=k, column=f"{WAVELENGTHS[j]} nm",
                   name=name, commas=commas)
              for j, i in enumerate(spec_idx)]
        spectra.append(sp)
        if xyz_idx:
            xyz.append([_num(parts[i], reading=k, column=c, name=name,
                             commas=commas)
                        for i, c in zip(xyz_idx, "XYZ")])
        if lab_idx:
            lab.append([_num(parts[i], reading=k, column=c, name=name,
                             commas=commas)
                        for i, c in zip(lab_idx, ("L", "a", "b"))])
    spectra = np.asarray(spectra, dtype=float)
    top = float(spectra.max())
    if top > SCALE_LIMIT:
        raise Spectro32Refused("scale", name=name, top=_shown(top))
    low_at = np.argwhere(spectra < NEGATIVE_LIMIT)
    if len(low_at):
        r, c = low_at[0]
        raise Spectro32Refused("negative", name=name, reading=int(r) + 1,
                               value=_shown(float(spectra[r, c])))
    return S32File(
        path=path, kind=kind, spectra=spectra,
        xyz=np.asarray(xyz, dtype=float) if xyz else None,
        lab=np.asarray(lab, dtype=float) if lab else None,
        setting=setting, template=template,
        sha256=hashlib.sha256(data).hexdigest(),
        decimal_comma=bool(commas))


def _shown(v) -> str:
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:.4g}"


def _companion(path: Path, suffix: str) -> "Path | None":
    """The file of the same run with another ending (``_VAL.txt``,
    ``_XYZ.txt``, ``_LAB.txt``), matched without regard to case."""
    m = re.search(r"_(measurements|val|spectrum|xyz|lab|dens)\.txt$",
                  path.name, re.I)
    if not m:
        return None
    want = (path.name[:m.start()] + suffix).lower()
    try:
        for cand in path.parent.iterdir():
            if cand.name.lower() == want and cand.is_file() and cand != path:
                return cand
    except OSError:
        return None
    return None


def _read_colour_file(path: Path, n: int) -> "tuple[np.ndarray | None, tuple | None]":
    """Spectro32's ``_XYZ.txt`` / ``_LAB.txt``: three numbers per line under
    a short header; (values, setting) or (None, None) when unusable."""
    try:
        text = _decode(path.read_bytes())
    except OSError:
        return None, None
    setting, vals = None, []
    for ln in text.splitlines()[1:]:
        s = ln.strip()
        if not s:
            continue
        m = _SETTING_RE.match(s)
        if m and not vals:
            setting = (m.group(1).upper(), m.group(2))
            continue
        parts = _split(s)
        if len(parts) != 3 or not all(_is_number(p) for p in parts):
            if not vals:
                continue        # the template's name
            return None, setting
        vals.append([float(p.replace(",", ".")) for p in parts])
    if len(vals) != n:
        return None, setting
    return np.asarray(vals, dtype=float), setting


def read_with_companions(path) -> S32File:
    """:func:`read_file`, plus what the same run's other files add: the
    colour setting (from ``_VAL.txt`` / ``_XYZ.txt`` / ``_LAB.txt``) and,
    for a spectrum-only file, Spectro32's own XYZ or Lab to check against."""
    f = read_file(path)
    for suffix in ("_VAL.txt", "_XYZ.txt", "_LAB.txt"):
        other = _companion(f.path, suffix)
        if other is None:
            continue
        if suffix == "_VAL.txt":
            try:
                v = read_file(other)
            except Spectro32Refused:
                continue
            f.companions.append(other.name)
            if f.setting is None:
                f.setting = v.setting
            if not f.template:
                f.template = v.template
            if f.xyz is None and v.xyz is not None and v.n == f.n:
                f.xyz = v.xyz
            if f.lab is None and v.lab is not None and v.n == f.n:
                f.lab = v.lab
            continue
        vals, setting = _read_colour_file(other, f.n)
        if vals is None and setting is None:
            continue
        f.companions.append(other.name)
        if f.setting is None:
            f.setting = setting
        if suffix == "_XYZ.txt" and f.xyz is None:
            f.xyz = vals
        if suffix == "_LAB.txt" and f.lab is None:
            f.lab = vals
    return f


# ---------------------------------------------------------------------------
# colours
# ---------------------------------------------------------------------------

def spectra_xyz(spectra: np.ndarray, illuminant: str = "D50",
                observer: str = "1931_2") -> np.ndarray:
    from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
    return spectra_to_xyz_like_argyll(spectra, WAVELENGTHS,
                                      illuminant=illuminant,
                                      observer=observer, percent=False)


def white_xyz(illuminant: str = "D50", observer: str = "1931_2"):
    from workflow.argyll_colorimetry import white_xyz_like_argyll
    return white_xyz_like_argyll(illuminant, observer)


def xyz_to_lab(xyz, white) -> np.ndarray:
    t = np.asarray(xyz, dtype=float) / np.asarray(white, dtype=float)
    e = 216.0 / 24389.0
    f = np.where(t > e, np.cbrt(np.clip(t, e, None)),
                 (24389.0 / 27.0 * t + 16.0) / 116.0)
    return np.stack([116.0 * f[..., 1] - 16.0,
                     500.0 * (f[..., 0] - f[..., 1]),
                     200.0 * (f[..., 1] - f[..., 2])], axis=-1)


_OBSERVER_WORDS = {"1931_2": "2", "1964_10": "10"}


@dataclass
class XyzCheck:
    """Spectro32's own colours against the spectra."""
    available: bool
    agree: bool = True
    median: float = 0.0
    largest: float = 0.0
    other_setting: "tuple[str, str] | None" = None   # ("D65", "10")
    source: str = ""              # "XYZ" or "Lab"


def xyz_check(f: S32File) -> XyzCheck:
    """Compare Spectro32's saved XYZ (or Lab) with the colours of the
    spectra, under D50 / 2 degree first, then under the settings Spectro32
    could have been set to."""
    if f.xyz is None and f.lab is None:
        return XyzCheck(False)

    def against(illum, obs):
        w = white_xyz(illum, obs)
        mine = xyz_to_lab(spectra_xyz(f.spectra, illum, obs), w)
        theirs = f.lab if f.lab is not None else xyz_to_lab(f.xyz, w)
        d = np.linalg.norm(mine - theirs, axis=1)
        return float(np.median(d)), float(d.max())

    med, big = against("D50", "1931_2")
    src = "Lab" if f.lab is not None else "XYZ"
    if big <= XYZ_AGREE_DE:
        return XyzCheck(True, True, med, big, None, src)
    for illum, obs in OTHER_SETTINGS:
        m2, b2 = against(illum, obs)
        if b2 <= XYZ_AGREE_DE:
            return XyzCheck(True, True, med, big,
                            (illum, _OBSERVER_WORDS[obs]), src)
    return XyzCheck(True, False, med, big, None, src)


# ---------------------------------------------------------------------------
# the chart
# ---------------------------------------------------------------------------

@dataclass
class ChartFacts:
    fields: "list[str]"
    rows: "list[list[str]]"          # the .ti2's data lines, split
    loc_index: "dict[str, int]"       # SAMPLE_LOC -> row
    device_fields: "list[str]"
    color_rep: str
    keywords: "dict[str, str]"
    expected_lab: "np.ndarray | None"  # per .ti2 row


_COPIED_KEYWORDS = ("SINGLE_DIM_STEPS", "COMP_GREY_STEPS", "MULTI_DIM_STEPS",
                    "FULL_SPREAD_PATCHES", "TOTAL_INK_LIMIT",
                    "FINAL_TOTAL_INK_LIMIT")


def _tokens(line: str) -> "list[str]":
    return re.findall(r'"[^"]*"|\S+', line)


def read_chart(chart_ti2) -> "ChartFacts | None":
    from core.text_io import read_text
    try:
        text = read_text(Path(chart_ti2), lenient=True)
    except OSError:
        return None
    kw: "dict[str, str]" = {}
    head = text.split("BEGIN_DATA_FORMAT", 1)[0]
    for ln in head.splitlines():
        t = _tokens(ln.strip())
        if len(t) >= 2 and re.fullmatch(r"[A-Z_][A-Z0-9_]*", t[0]):
            kw[t[0]] = " ".join(t[1:]).strip('"')
    m = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\n\s*END_DATA_FORMAT", text,
                  re.S)
    b = re.search(r"\nBEGIN_DATA\s*\n(.*?)\n\s*END_DATA", text, re.S)
    if not m or not b:
        return None
    fields = m.group(1).split()
    rows = [_tokens(ln) for ln in b.group(1).splitlines() if ln.strip()]
    if "SAMPLE_LOC" not in fields or "SAMPLE_ID" not in fields:
        return None
    li = fields.index("SAMPLE_LOC")
    loc_index = {}
    for i, r in enumerate(rows):
        if len(r) != len(fields):
            return None
        loc_index[r[li].strip('"')] = i
    skip = {"SAMPLE_ID", "SAMPLE_LOC", "XYZ_X", "XYZ_Y", "XYZ_Z", "LAB_L",
            "LAB_A", "LAB_B"}
    device = [f for f in fields if f not in skip]
    exp = None
    if all(f in fields for f in ("XYZ_X", "XYZ_Y", "XYZ_Z")):
        ix = [fields.index(f) for f in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
        try:
            xyz = np.asarray([[float(r[i]) for i in ix] for r in rows])
            white = [float(v) for v in kw.get("APPROX_WHITE_POINT",
                                              "").split()] or []
            if len(white) != 3 or min(white) <= 0:
                white = list(np.max(xyz, axis=0))
            if xyz.size and float(np.ptp(xyz[:, 1])) > 0:
                exp = xyz_to_lab(xyz, white)
        except (ValueError, IndexError):
            exp = None
    return ChartFacts(fields, rows, loc_index, device,
                      kw.get("COLOR_REP", ""), kw, exp)


# ---------------------------------------------------------------------------
# the arrangement check
# ---------------------------------------------------------------------------

def arrangement_cells(name: str, cols: int, rows: int) -> "list[int | None]":
    """For each reading k (reading order), the cell the head really read if
    the sheet lay as *name* says; None where it read outside the grid."""
    out: "list[int | None]" = []
    for k in range(cols * rows):
        c, r = k % cols, k // cols
        if name == "straight":
            cc, rr = c, r
        elif name == "mirrored":
            cc, rr = cols - 1 - c, r
        elif name == "upside-down":
            cc, rr = c, rows - 1 - r
        elif name == "turned":
            cc, rr = cols - 1 - c, rows - 1 - r
        elif name == "right":          # aimed one patch right of the aim
            cc, rr = c + 1, r
        elif name == "left":
            cc, rr = c - 1, r
        elif name == "up":             # aimed one patch above the aim
            cc, rr = c, r - 1
        elif name == "down":
            cc, rr = c, r + 1
        else:
            raise ValueError(name)
        out.append(rr * cols + cc if 0 <= cc < cols and 0 <= rr < rows
                   else None)
    return out


def _features(E: np.ndarray, quadratic: bool) -> np.ndarray:
    one = np.ones((len(E), 1))
    X = np.hstack([E, one])
    if quadratic:
        L, a, b = E[:, :1], E[:, 1:2], E[:, 2:3]
        X = np.hstack([X, L * L, a * a, b * b, L * a, L * b, a * b])
    return X


@dataclass
class Fit:
    rel: float
    check_res: "float | None"
    cells: int


def _fit(E, M, cells, check_cells: "list[int]", quadratic: bool,
         spread: float) -> "Fit | None":
    pairs = [(k, c) for k, c in enumerate(cells) if c is not None]
    if len(pairs) < 8:
        return None
    ks = np.array([k for k, _c in pairs])
    cs = np.array([c for _k, c in pairs])
    quad = quadratic and len(pairs) >= QUADRATIC_FROM
    X = _features(E[cs], quad)
    A, *_ = np.linalg.lstsq(X, M[ks], rcond=None)
    res = np.linalg.norm(X @ A - M[ks], axis=1)
    check = None
    if check_cells:
        # THE CHECK PATCHES ARE PREDICTED, NOT FITTED: the map is fitted
        # without them and asked what each should read. Fitted with them, a
        # quadratic map has the freedom to bend onto five extreme points
        # (measured on a sorted test field: a sheet upside down left 4 dE76
        # at the check patches fitted, 90 predicted).
        is_check = np.isin(cs, list(check_cells))
        if is_check.any() and (~is_check).sum() >= 8:
            # affine: a quadratic map extrapolates wildly to points off the
            # chart's own colours (184 dE76 on the right sheet of the test
            # field); an affine one stays within the printer's curvature
            Xo = _features(E[cs[~is_check]], False)
            Ao, *_ = np.linalg.lstsq(Xo, M[ks[~is_check]], rcond=None)
            Xc = _features(E[cs[is_check]], False)
            pred = np.linalg.norm(Xc @ Ao - M[ks[is_check]], axis=1)
            check = float(np.mean(pred))
    return Fit(float(np.median(res)) / max(spread, 1e-9), check, len(pairs))


@dataclass
class PageJudgement:
    status: str                     # "ok" | "refuse" | "ask"
    code: str = ""                  # refusal reason code
    how: str = ""                   # the arrangement named
    why: str = ""                   # the reason asked
    rel: float = float("nan")
    best_alt: str = ""
    best_alt_rel: float = float("nan")
    decided_by: str = ""            # "fit" | "check patches" | ""


def judge_page(E: "np.ndarray | None", M: np.ndarray, cols: int, rows: int,
               check_cells: "list[int]") -> PageJudgement:
    """Does reading k belong to cell k (the sheet as it should lie)?
    *E* the expected Lab per cell, *M* the measured Lab per reading, both
    in reading order; *check_cells* the cells holding check patches."""
    if E is None:
        return PageJudgement("ask", why="no-colours")
    n = cols * rows
    spread = float(np.median(np.linalg.norm(M - M.mean(axis=0), axis=1)))
    quad = n >= QUADRATIC_FROM
    straight = _fit(E, M, arrangement_cells("straight", cols, rows),
                    check_cells, quad, spread)
    if straight is None:
        return PageJudgement("ask", why="few")
    alts = []
    for name in ARRANGEMENTS:
        cells = arrangement_cells(name, cols, rows)
        moved = [(k, c) for k, c in enumerate(cells) if c is not None]
        if len(moved) < n * 0.5:
            continue
        if all(c == k for k, c in moved):
            continue                       # the same as straight (one row)
        f = _fit(E, M, cells, check_cells, quad, spread)
        if f is None:
            continue
        self_de = float(np.median([np.linalg.norm(E[k] - E[c])
                                   for k, c in moved if c != k] or [0.0]))
        alts.append((name, f, self_de))
    best = min(alts, key=lambda a: a[1].rel) if alts else None
    j = PageJudgement("ok", rel=straight.rel,
                      best_alt=best[0] if best else "",
                      best_alt_rel=best[1].rel if best else float("nan"))
    # an arrangement clearly better by the fit: refused and named (among
    # several that fit about equally, the one the check patches agree with)
    better = [(name, f) for name, f, _sd in alts
              if f.rel <= FIT_ABSURD and f.rel < FIT_RATIO * straight.rel]
    if better:
        top = min(f.rel for _n, f in better)
        near = [(n, f) for n, f in better if f.rel <= top / FIT_RATIO]
        name = min(near, key=lambda nf: (
            nf[1].check_res if nf[1].check_res is not None else 1e9,
            nf[1].rel))[0]
        j.status, j.code, j.how = "refuse", "arranged", name
        return j
    if straight.rel > FIT_ABSURD:
        j.status, j.code = "refuse", "other-chart"
        return j
    unclear = [(name, f, sd) for name, f, sd in alts
               if not (straight.rel < FIT_RATIO * f.rel and sd >= SELF_MAP_DE)
               ]
    if not unclear:
        j.decided_by = "fit"
        return j
    # the check patches decide what the fit cannot
    if straight.check_res is None:
        j.status, j.why = "ask", ("no-checks" if not check_cells
                                  else "similar")
        return j
    left, better = [], []
    for name, f, _sd in unclear:
        if f.check_res is None:
            left.append(name)
            continue
        if f.check_res >= max(CHECK_MIN_DE, CHECK_RATIO * straight.check_res):
            continue                      # ruled out
        if straight.check_res >= max(CHECK_MIN_DE,
                                     CHECK_RATIO * f.check_res):
            better.append((f.check_res, name))
            continue
        left.append(name)
    if better:
        j.status, j.code, j.how = "refuse", "arranged", min(better)[1]
        j.decided_by = "check patches"
        return j
    if left:
        j.status, j.why = "ask", "similar"
        return j
    j.decided_by = "check patches"
    return j


# ---------------------------------------------------------------------------
# the whole judgement
# ---------------------------------------------------------------------------

@dataclass
class PagePairing:
    page: int                       # 1-based
    file: S32File
    names: "list[str]"              # reading order of the page
    lab: np.ndarray                 # measured, D50 / 2
    xyz: np.ndarray
    judgement: PageJudgement
    xyz_check: XyzCheck
    cols: int = 0
    rows: int = 0


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    code: str = ""
    pages: "list[PagePairing]" = field(default_factory=list)
    ask_why: str = ""               # the colours cannot tell: ask
    xyz_ask: "XyzCheck | None" = None
    mode: str = "reflection"
    head: str = ""
    opening_mm: float = 0.0
    side_name: str = ""
    first: str = "A1"
    aim: str = ""
    n_cells: int = 0

    @property
    def settings_noted(self) -> "list[tuple[str, str]]":
        out = []
        for p in self.pages:
            s = p.xyz_check.other_setting
            if s and s not in out:
                out.append(s)
        return out


def _refused(exc: Spectro32Refused, **extra) -> Verdict:
    return Verdict(False, exc.reason(), exc.code, **extra)


def assess_files(paths, chart_ti2) -> Verdict:
    """Judge Spectro32 file(s) against a Barbieri chart. Nothing is written.
    A refusal carries the reason; ``ask_why`` / ``xyz_ask`` say what the
    person must be asked before :func:`write_ti3`."""
    from workflow.barbieri import support
    paths = [Path(p) for p in paths]
    side = support.side_file_for(chart_ti2)
    doc = support.read_side_file(chart_ti2)
    base = dict(side_name=side.name)
    try:
        if not doc:
            raise Spectro32Refused("side", side=side.name)
        try:
            digest = hashlib.sha256(Path(chart_ti2).read_bytes()).hexdigest()
        except OSError:
            digest = ""
        if not digest or doc.get("ti2_sha256") != digest:
            raise Spectro32Refused("side", side=side.name)
        pages = doc.get("pages_detail") or []
        facts = read_chart(chart_ti2)
        if not pages or facts is None or any(
                nm not in facts.loc_index
                for pg in pages for nm in pg.get("reading_order") or []):
            raise Spectro32Refused("side", side=side.name)
        if len(pages) == 1 and len(paths) > 1:
            raise Spectro32Refused("one-page", files=len(paths))
        if len(pages) > 1 and len(paths) != len(pages):
            raise Spectro32Refused(
                "pages-one" if len(paths) == 1 else "pages-many",
                pages=len(pages), files=len(paths))
        files = [read_with_companions(p) for p in paths]
    except Spectro32Refused as exc:
        return _refused(exc, **base)

    from workflow.barbieri import chart_facts as F
    head = F.HEADS.get(doc.get("head") or "", F.HEADS[F.DEFAULT_HEAD])
    first_pg = pages[0]
    verdict = Verdict(True, mode=head.mode, head=head.key,
                      opening_mm=head.aperture_mm, side_name=side.name,
                      first=first_pg.get("first_patch") or "A1",
                      aim=first_pg.get("aim_patch") or "",
                      n_cells=sum(int(p["columns"]) * int(p["rows"])
                                  for p in pages))

    def page_inputs(pg):
        names = list(pg.get("reading_order") or [])
        cols, rows = int(pg["columns"]), int(pg["rows"])
        E = None
        if facts.expected_lab is not None:
            E = facts.expected_lab[[facts.loc_index[n] for n in names]]
        checks = []
        pos = {n: i for i, n in enumerate(names)}
        if doc.get("check_patches_on", False):
            checks = [pos[c["patch"]] for c in pg.get("check_patches") or []
                      if c.get("patch") in pos]
        return names, cols, rows, E, checks

    measured = []
    for f in files:
        xyz = spectra_xyz(f.spectra)
        measured.append((xyz, xyz_to_lab(xyz, white_xyz())))

    # which file is which page
    assignment: "dict[int, int]" = {}
    try:
        if len(pages) == 1:
            pg = pages[0]
            cells = int(pg["columns"]) * int(pg["rows"])
            if files[0].n != cells:
                raise Spectro32Refused(
                    "count", name=files[0].name, page=1, cells=cells,
                    cols=int(pg["columns"]), rows=int(pg["rows"]),
                    got=files[0].n)
            assignment[0] = 0
        else:
            for fi, f in enumerate(files):
                fits = []
                for pi, pg in enumerate(pages):
                    names, cols, rows, E, _c = page_inputs(pg)
                    if f.n != cols * rows:
                        continue
                    if E is None:
                        fits.append((0.0, pi))
                        continue
                    M = measured[fi][1]
                    spread = float(np.median(np.linalg.norm(
                        M - M.mean(axis=0), axis=1)))
                    fit = _fit(E, M, arrangement_cells("straight", cols,
                                                       rows), [],
                               cols * rows >= QUADRATIC_FROM, spread)
                    fits.append((fit.rel if fit else 1.0, pi))
                if not fits:
                    pg = pages[0]
                    raise Spectro32Refused(
                        "count", name=f.name, page=1,
                        cells=int(pg["columns"]) * int(pg["rows"]),
                        cols=int(pg["columns"]), rows=int(pg["rows"]),
                        got=f.n)
                fits.sort()
                if len(fits) > 1 and not (
                        fits[0][0] < FIT_RATIO * fits[1][0]):
                    raise Spectro32Refused("which-page", name=f.name)
                pi = fits[0][1]
                if pi in assignment.values():
                    other = files[[k for k, v in assignment.items()
                                   if v == pi][0]].name
                    raise Spectro32Refused("same-page", name=f.name,
                                           other=other, page=pi + 1)
                assignment[fi] = pi
    except Spectro32Refused as exc:
        return _refused(exc, **base)

    for fi, pi in sorted(assignment.items(), key=lambda kv: kv[1]):
        f = files[fi]
        pg = pages[pi]
        names, cols, rows, E, checks = page_inputs(pg)
        xyz, lab = measured[fi]
        j = judge_page(E, lab, cols, rows, checks)
        xc = xyz_check(f)
        verdict.pages.append(PagePairing(pi + 1, f, names, lab, xyz, j, xc,
                                         cols, rows))
        if j.status == "refuse":
            if j.code == "arranged":
                exc = Spectro32Refused(
                    "aimed-" + j.how if j.how in ("right", "left", "up",
                                                  "down")
                    else "arranged-" + j.how,
                    name=f.name, first=pg.get("first_patch") or "A1",
                    aim=pg.get("aim_patch") or "")
            else:
                exc = Spectro32Refused("other-chart", name=f.name)
            v = _refused(exc, **base)
            v.pages = verdict.pages
            return v
        if j.status == "ask" and not verdict.ask_why:
            verdict.ask_why = j.why
        if xc.available and not xc.agree and verdict.xyz_ask is None:
            verdict.xyz_ask = xc
    return verdict


# ---------------------------------------------------------------------------
# writing the .ti3
# ---------------------------------------------------------------------------

def write_ti3(verdict: Verdict, chart_ti2, out_dir) -> Path:
    """The filed copy: every patch of the chart in the ``.ti2``'s own order,
    with its ``SAMPLE_ID``, ``SAMPLE_LOC`` and device values as the ``.ti2``
    writes them, the XYZ computed from the spectra (D50, 2 degree, as
    ArgyllCMS) and the 41 spectral values in percent, as chartread writes
    them."""
    if not verdict.ok or not verdict.pages:
        raise ValueError("only a verdict that passed is written")
    facts = read_chart(chart_ti2)
    if facts is None:
        raise ValueError("the chart cannot be read")
    by_row: "dict[int, tuple[np.ndarray, np.ndarray]]" = {}
    for p in verdict.pages:
        for k, nm in enumerate(p.names):
            by_row[facts.loc_index[nm]] = (p.xyz[k], p.file.spectra[k])
    fi = {f: i for i, f in enumerate(facts.fields)}
    rep = facts.color_rep or "RGB"
    first = verdict.pages[0].file
    when = date.fromtimestamp(first.path.stat().st_mtime).isoformat()
    spec_fields = [f"SPEC_{w}" for w in WAVELENGTHS]
    fields = (["SAMPLE_ID", "SAMPLE_LOC"] + facts.device_fields +
              ["XYZ_X", "XYZ_Y", "XYZ_Z"] + spec_fields)
    from workflow.barbieri import support
    lines = ["CTI3", "",
             'DESCRIPTOR "Spectro32 measurement of a Barbieri Spectro 100xy '
             'chart, paired by reading order"',
             'ORIGINATOR "ChromIQ"',
             f'CREATED "{date.today().isoformat()}"',
             'KEYWORD "TARGET_INSTRUMENT"',
             f'TARGET_INSTRUMENT "{support.TARGET_INSTRUMENT}"',
             'DEVICE_CLASS "OUTPUT"',
             f'COLOR_REP "{rep}_XYZ"',
             'INSTRUMENT_TYPE_SPECTRAL "YES"']
    for k in _COPIED_KEYWORDS:
        if k in facts.keywords:
            lines.append(f'{k} "{facts.keywords[k]}"')
    sources = ", ".join(f"page {p.page} {p.file.name} sha256 "
                        f"{p.file.sha256[:16]}" for p in verdict.pages)
    lines += ['KEYWORD "CHROMIQ_MEASURED"', f'CHROMIQ_MEASURED "{when}"',
              f'KEYWORD "{PAIRED_KEYWORD}"',
              f'{PAIRED_KEYWORD} "{verdict.side_name}; {sources}"',
              f'KEYWORD "{MODE_KEYWORD}"', f'{MODE_KEYWORD} "{verdict.mode}"',
              f'KEYWORD "{HEAD_KEYWORD}"', f'{HEAD_KEYWORD} "{verdict.head}"',
              'KEYWORD "CHROMIQ_XYZ_METHOD"',
              f'CHROMIQ_XYZ_METHOD "{XYZ_METHOD}"',
              f'SPECTRAL_BANDS "{BANDS}"',
              f'SPECTRAL_START_NM "{WAVELENGTHS[0]:.6f}"',
              f'SPECTRAL_END_NM "{WAVELENGTHS[-1]:.6f}"', "",
              f"NUMBER_OF_FIELDS {len(fields)}", "BEGIN_DATA_FORMAT",
              " ".join(fields), "END_DATA_FORMAT", ""]
    out_rows = []
    for i, r in enumerate(facts.rows):
        if i not in by_row:
            continue
        if r[fi["SAMPLE_ID"]].strip('"') == "0":
            continue                         # printtarg's padding: unread
        xyz, sp = by_row[i]
        dev = " ".join(r[fi[f]] for f in facts.device_fields)
        s = " ".join(f"{v * 100.0:.5f}" for v in sp)
        out_rows.append(
            f'{r[fi["SAMPLE_ID"]]} {r[fi["SAMPLE_LOC"]]} {dev} '
            f'{xyz[0]:.6f} {xyz[1]:.6f} {xyz[2]:.6f} {s}')
    lines += [f"NUMBER_OF_SETS {len(out_rows)}", "BEGIN_DATA", *out_rows,
              "END_DATA", ""]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(chart_ti2).name
    stem = stem[:-4] if stem.lower().endswith(".ti2") else stem
    out = out_dir / f"{stem}.spectro32.ti3"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def log_lines(verdict: Verdict) -> "list[str]":
    """What the app log keeps of an import (English, for a tester's log):
    every file with its checksum and setting, every page's checks with
    their numbers."""
    out = []
    for p in verdict.pages:
        f = p.file
        j = p.judgement
        xc = p.xyz_check
        out.append(
            f"Barbieri import: page {p.page} <- {f.name} ({f.kind}, "
            f"{f.n} readings, sha256 {f.sha256}; template line "
            f"{f.template!r}; Spectro32 setting "
            f"{' '.join(f.setting) if f.setting else 'not in the files'}; "
            f"companions {', '.join(f.companions) or 'none'}; decimal comma "
            f"{'yes' if f.decimal_comma else 'no'})")
        out.append(
            f"Barbieri import: page {p.page} grid {p.cols} x {p.rows}, "
            f"reading 1 = {p.names[0]}, reading {len(p.names)} = "
            f"{p.names[-1]}; arrangement {j.status} "
            f"(fit {j.rel:.3f} of the spread as printed, best other "
            f"{j.best_alt or '-'} {j.best_alt_rel:.3f}; decided by "
            f"{j.decided_by or '-'}{'; asked: ' + j.why if j.why else ''})")
        if xc.available:
            out.append(
                f"Barbieri import: page {p.page} Spectro32 {xc.source} "
                f"against the spectra (D50 / 2): median {xc.median:.4f}, "
                f"max {xc.largest:.4f} dE76; "
                + ("agree" if xc.agree and not xc.other_setting else
                   f"explained by {xc.other_setting[0]} / "
                   f"{xc.other_setting[1]} degree" if xc.agree else
                   "NOT explained"))
        else:
            out.append(f"Barbieri import: page {p.page} no Spectro32 XYZ "
                       "or Lab to compare with")
    out.append(f"Barbieri import: opening {verdict.head} ({verdict.mode}), "
               f"{verdict.n_cells} patches, side file {verdict.side_name}")
    return out
