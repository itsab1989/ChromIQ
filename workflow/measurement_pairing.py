"""Pairing a measurement that carries no device values with the chart it is a
measurement OF, by the NAME printed beside each patch.

WHAT THIS IS FOR. i1Profiler's measure tool reads a chart it did not generate.
It therefore has no colour space to express device values in, and — as a user
verifying a profile put it on 2026-09-11 — *"it also won't let you select RGB
data to be included in the export"*. Its CGATS export is ``SAMPLE_ID``,
``SAMPLE_NAME`` and the spectral curve. ``txt2ti3`` converts that without
complaint ("No device values found - hope that's OK!"); ChromIQ then refused it
with **"No device RGB columns, only RGB charts are supported"**, about a
measurement of its own chart, taken on an i1iO, covering every patch.

WHAT THE PAIRING IS REALLY KEYED ON, AND WHAT IT SHOULD BE.

* The report, and the check in front of it, pair a measurement with its chart by
  ``SAMPLE_ID`` (:func:`workflow.measurement_report.verify_patch_identity`), and
  then use the DEVICE VALUES as the witness that the pairing is right.
* For a file like hers ``SAMPLE_ID`` is only i1Profiler's reading order, which
  is not the chart's order at all: ChromIQ's ``.ti2`` numbers its rows in the
  ``.ti1``'s canonical order and shuffles only the LOCATION each one lands on
  (``layout_engine/ti2_writer``). Her ids run 1, 2, 3 down the reading; the
  chart's run 1, 2, 3 down the design. Pairing those two would hand every
  reading to the wrong patch.
* Her ``SAMPLE_NAME``s are ``A1 … T21``, which are exactly the 420
  ``SAMPLE_LOC`` labels the chart printed on the sheet — the same label,
  because that is what the person aimed the instrument at. So the key is
  **SAMPLE_LOC**: an exact, printed, chart-issued name, not a colour.

THIS IS NOT THE REPAIR THAT WAS REJECTED. §I of
``unified_measurement_management.md`` forbids re-pairing a measurement by
matching device values, because the check that would validate such a repair is
the very quantity the repair minimises, so it reports "verified" either way.
Nothing here looks at a colour. A name either is one of the chart's locations or
it is not, every name must be, and no name may be used twice; a measurement of
somebody else's chart fails that outright.

WHAT IT THEN DOES is what ``chartread`` does: it writes the chart's own device
values and the chart's own ``SAMPLE_ID`` beside each reading, in the chart's
order. The result is an ordinary ChromIQ ``.ti3`` — the report, the overlay and
``colprof`` all read it without knowing where it came from — and the file says
so in its own header (``CHROMIQ_DEVICE_FROM_CHART``), so nobody later mistakes
a value the chart supplied for a value the instrument measured.

THE ORDER OF THE TWO ACTS MATTERS. The name check runs BEFORE the device values
are written. Afterwards ``verify_patch_identity`` would compare the chart's
device values with a copy of themselves and answer "verified" whatever had
happened — the same self-validating trap that sank the rejected repair.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from core.text_io import read_text

#: Header keyword stamped on a measurement whose device columns were supplied by
#: the chart rather than measured. It is a `KEYWORD`-declared CGATS keyword, so
#: every ArgyllCMS tool still parses the file.
DEVICE_FROM_CHART_KEYWORD = "CHROMIQ_DEVICE_FROM_CHART"


@dataclass(frozen=True)
class NameMatch:
    """How a device-less measurement's patch names line up with a chart's.

    *ok* False means the two are not the same chart. *missing* names chart
    locations nobody measured (a partial read); *unknown* names measured
    patches this chart does not have, which is the refusal.
    """
    ok: bool
    reason: str = ""
    matched: int = 0
    n_chart: int = 0
    n_measured: int = 0
    unknown: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    duplicated: list[str] = field(default_factory=list)


_BEGIN_RE = re.compile(r"^\s*BEGIN_DATA\s*$", re.MULTILINE)
_END_RE = re.compile(r"^\s*END_DATA\s*$", re.MULTILINE)
_FMT_RE = re.compile(r"^\s*BEGIN_DATA_FORMAT\s*$", re.MULTILINE)


def _first_table(text: str) -> "tuple[list[str], list[str]] | None":
    """``(fields, data lines)`` of a CGATS file's FIRST table, or None.

    The first table is the one a measurement lives in; a ``.ti1`` carries two
    more reference tables after it.
    """
    mf = _FMT_RE.search(text)
    mb = _BEGIN_RE.search(text)
    if mf is None or mb is None:
        return None
    fields = text[mf.end():].lstrip("\n").splitlines()[0].split()
    me = _END_RE.search(text, mb.end())
    body = text[mb.end():me.start() if me else len(text)]
    return fields, [ln for ln in body.splitlines() if ln.strip()]


def _locs(fields: "list[str]", rows: "list[str]") -> "list[str]":
    """The ``SAMPLE_LOC`` of every row, unquoted; ``[]`` when there is none."""
    if "SAMPLE_LOC" not in fields:
        return []
    i = fields.index("SAMPLE_LOC")
    out = []
    for ln in rows:
        parts = ln.split()
        out.append(parts[i].strip('"') if i < len(parts) else "")
    return out


def chart_locations(ti2_path: "str | Path") -> "list[str]":
    """Every ``SAMPLE_LOC`` the chart printed, in the chart's own row order."""
    try:
        text = read_text(Path(ti2_path), lenient=True)
    except OSError:
        return []
    t = _first_table(text)
    return _locs(*t) if t else []


def measurement_locations(ti3_path: "str | Path") -> "list[str]":
    """Every ``SAMPLE_LOC`` the measurement carries, in the file's own order."""
    return chart_locations(ti3_path)


def match_by_name(ti3_path: "str | Path", ti2_path: "str | Path") -> NameMatch:
    """Does every patch in *ti3_path* name a patch of the chart *ti2_path*?

    Three ways it can be no, and each is a different sentence for the user:
    the file carries no names at all; it names patches this chart does not have;
    it names one patch twice. Fewer names than the chart is NOT a no — a person
    may read part of a sheet and come back (§I.10).
    """
    chart = chart_locations(ti2_path)
    got = measurement_locations(ti3_path)
    if not chart:
        return NameMatch(False, "the chart file carries no patch names",
                         n_measured=len(got))
    if not got:
        return NameMatch(False, "the measurement carries no patch names",
                         n_chart=len(chart))
    known = set(chart)
    unknown = sorted({loc for loc in got if loc not in known})
    seen: dict[str, int] = {}
    for loc in got:
        seen[loc] = seen.get(loc, 0) + 1
    duplicated = sorted(loc for loc, n in seen.items() if n > 1)
    missing = sorted(loc for loc in known if loc not in seen)
    if unknown:
        return NameMatch(False, "", n_chart=len(chart), n_measured=len(got),
                         unknown=unknown, missing=missing,
                         duplicated=duplicated,
                         matched=len(got) - sum(seen[u] for u in unknown))
    if duplicated:
        return NameMatch(False, "", n_chart=len(chart), n_measured=len(got),
                         duplicated=duplicated, missing=missing,
                         matched=len(got))
    return NameMatch(True, "", matched=len(got), n_chart=len(chart),
                     n_measured=len(got), missing=missing)


def attach_device_values_from_chart(ti3_path: "str | Path",
                                    ti2_path: "str | Path") -> int:
    """Write the chart's device columns and ``SAMPLE_ID`` into *ti3_path*.

    Rewrites the file IN PLACE, in the chart's own row order, and returns how
    many rows were written. Returns 0 and leaves the file untouched when the
    names do not match (call :func:`match_by_name` first and say why), when the
    measurement already carries device values, or when the chart's device
    columns cannot be read.

    **THE SAMPLE_ID IS THE CHART'S OWN WHERE THE CHART HAS ONE.** It used to be
    written as the chart's ROW INDEX, ``ci + 1``, which is the same number only
    while a ``.ti2``'s ``SAMPLE_ID`` column runs 1..N in file order. That is
    true of every chart ChromIQ generates and is not guaranteed of one imported
    from somewhere else, so on such a chart the sentence above named a column
    the file did not get. It is taken from the chart now, and the index is the
    fallback for a chart that has no ``SAMPLE_ID`` at all.

    The index also remains the fallback when the chart's own ids are not unique
    across the chart, because an id is what a later reader uses to name a row
    and two rows that answer to one name are worse than a renumbering. The
    index is not renumbered to close the gaps a partial measurement leaves: the
    ids then run with holes, and a hole is the truth about which of the chart's
    patches were measured.
    """
    ti3_path, ti2_path = Path(ti3_path), Path(ti2_path)
    try:
        mtext = read_text(ti3_path, lenient=True)
        ctext = read_text(ti2_path, lenient=True)
    except OSError:
        return 0
    mt, ct = _first_table(mtext), _first_table(ctext)
    if mt is None or ct is None:
        return 0
    mfields, mrows = mt
    cfields, crows = ct
    from workflow.ti3_analysis import _has_device_columns
    if _has_device_columns(mfields):
        return 0
    dev_cols = [i for i, f in enumerate(cfields)
                if f not in ("SAMPLE_ID", "SAMPLE_LOC", "SAMPLE_NAME", "INDEX")
                and not f.startswith(("XYZ_", "LAB_", "SPEC_", "STDEV_", "D_"))]
    if not dev_cols:
        return 0
    dev_names = [cfields[i] for i in dev_cols]
    # The chart's own ids, when it has a column of them and they name one row
    # each. `None` means "use the row index", which is what this always did.
    csid_i = cfields.index("SAMPLE_ID") if "SAMPLE_ID" in cfields else None
    chart_ids: "list[str] | None" = None
    if csid_i is not None:
        try:
            ids = [r.split()[csid_i].strip('"') for r in crows]
        except IndexError:
            ids = []
        if ids and len(set(ids)) == len(ids) and all(ids):
            chart_ids = ids
    clocs = _locs(cfields, crows)
    mlocs = _locs(mfields, mrows)
    if not clocs or not mlocs:
        return 0
    by_loc = {loc: i for i, loc in enumerate(mlocs)}
    if len(by_loc) != len(mlocs):
        return 0                      # a name used twice; match_by_name refuses

    # SAMPLE_ID is rewritten, so it must not also survive as a data column.
    sid_i = mfields.index("SAMPLE_ID") if "SAMPLE_ID" in mfields else None
    loc_i = mfields.index("SAMPLE_LOC")
    keep = [i for i in range(len(mfields)) if i not in (sid_i, loc_i)]

    out_fields = ["SAMPLE_ID", "SAMPLE_LOC", *dev_names,
                  *(mfields[i] for i in keep)]
    out_rows: list[str] = []
    written = 0
    for ci, loc in enumerate(clocs):
        mi = by_loc.get(loc)
        if mi is None:
            continue                  # a patch nobody measured: §I.10's partial
        mparts = mrows[mi].split()
        cparts = crows[ci].split()
        dev = [cparts[i] for i in dev_cols]
        sid = chart_ids[ci] if chart_ids is not None else str(ci + 1)
        out_rows.append(" ".join([sid, f'"{loc}"', *dev,
                                  *(mparts[i] for i in keep)]))
        written += 1
    if not written:
        return 0

    lines = mtext.splitlines()
    out: list[str] = []
    state = "head"
    for ln in lines:
        s = ln.strip()
        if state == "head":
            if s == "BEGIN_DATA_FORMAT":
                out.append(ln)
                out.append(" ".join(out_fields) + " ")
                state = "in_format"
                continue
            if s.startswith("NUMBER_OF_FIELDS"):
                out.append(f"NUMBER_OF_FIELDS {len(out_fields)}")
                continue
            if s.startswith("NUMBER_OF_SETS"):
                out.append(f"NUMBER_OF_SETS {written}")
                continue
            out.append(ln)
            continue
        if state == "in_format":
            if s == "END_DATA_FORMAT":
                out.append(ln)
                state = "between"
            continue
        if state == "between":
            if s.startswith("NUMBER_OF_SETS"):
                out.append(f"NUMBER_OF_SETS {written}")
                continue
            if s == "BEGIN_DATA":
                out.append(ln)
                out.extend(out_rows)
                state = "in_data"
                continue
            out.append(ln)
            continue
        if state == "in_data":
            if s == "END_DATA":
                out.append(ln)
                state = "tail"
            continue
        out.append(ln)

    # The header must say where the device values came from, and it must say it
    # in a way ArgyllCMS still parses.
    at = 1 if out and out[0].strip().startswith("CTI3") else 0
    if DEVICE_FROM_CHART_KEYWORD not in mtext:
        out[at:at] = [f'KEYWORD "{DEVICE_FROM_CHART_KEYWORD}"',
                      f'{DEVICE_FROM_CHART_KEYWORD} "{Path(ti2_path).name}"']
    # COLOR_REP now has a device half, because the file now has device columns.
    rep = _color_rep(ctext)
    if rep:
        out = [ln for ln in out if not ln.strip().startswith("COLOR_REP")]
        out[at:at] = [f'COLOR_REP "{rep}_XYZ"']
    ti3_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return written


def _color_rep(chart_text: str) -> str:
    m = re.search(r'^\s*COLOR_REP\s+"?([A-Za-z0-9]+)', chart_text, re.MULTILINE)
    return m.group(1) if m else ""


def device_came_from_chart(ti3_path: "str | Path") -> str:
    """The chart that supplied this measurement's device values, or ``""``."""
    try:
        text = read_text(Path(ti3_path), lenient=True)
    except OSError:
        return ""
    m = re.search(rf'^\s*{DEVICE_FROM_CHART_KEYWORD}\s+"?([^"\n]+)"?',
                  text, re.MULTILINE)
    return m.group(1).strip() if m else ""
