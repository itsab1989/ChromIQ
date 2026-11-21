# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""From the table job's readings to the run's measurement (build step 7, no UI).

NO SECOND WRITER OF VALUES. Every value in the result was written by ArgyllCMS's own chartread
writer inside ChromIQ's helper: the job reads each row with the helper's patch-by-patch reading
over a small chart of that row (``reader.SpotReader``), and the helper saves that row's ``.ti3``
exactly as it does when a person measures by hand (the Measure tab's options -S -H -A -l -L -n
are the helper's own flags). What this module does is what the i1Profiler import does with a
device-less measurement, with the import's own functions:

1. the rows the JOB accepted (its per-row record: plausible, on target, saved value equal to
   the reading's event) are taken from the helper's row files, the placeholder device columns of
   the row chart are left out (the chart's real ones come in step 3), the last accepted reading
   of a patch wins (0.5.0 combined the same way);
2. ``measurement_pairing.match_by_name`` against the run's chart (every patch named by the
   chart, none twice), as the import checks BEFORE device values are written;
3. ``measurement_pairing.attach_device_values_from_chart`` (the import's own step): the chart's
   order, the chart's SAMPLE_ID and device values, ``CHROMIQ_DEVICE_FROM_CHART`` in the header;
4. ``measurement_state.classify`` decides COMPLETE or PARTIAL by location, as for any measurement.

A session that did not read every patch therefore can never look complete: the patches nobody
read are simply not in the file (``0 < C < A``, the PARTIAL state every part of the app knows,
and the state chartread's own resume works from). The result is written into the SESSION folder
(``Run.i1io_table_measurement``); it reaches ``Run.measurement_ti3`` only by :func:`file_into_run`,
which the job calls on the person's Save, never on Discard.

A later session completes a partial: it reads only the patches the run's measurement lacks
(``measurement_state.unread_locations``), and its assembly starts from the run's partial
measurement (``base_ti3``), whose rows count as the oldest readings.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

#: the declared keyword that says the measurement was read by the table (the spec's PROPOSAL,
#: ``i1io_table_support.md``, "Proposed for the measuring step": awaiting confirmation)
TABLE_KEYWORD = "MEASUREMENT_TABLE"
TABLE_VALUE = "i1iO 2"
#: a reading's event XYZ (4 decimals) and the value the helper saved for it must agree
XYZ_ABS_TOLERANCE = 0.0006
ROW_RECORD_SUFFIX = ".row.json"
#: D-4b: declared in a measurement whose white was scaled to the table's stored tile values
WHITE_KEYWORD = "CHROMIQ_TABLE_WHITE"
WHITE_STORED = "table's stored white tile values"
#: written into a session folder by Discard: its readings are never used again (the same name
#: as core.file_manager.I1IO_TABLE_DISCARDED; a test pins it)
DISCARDED = "discarded.json"
#: written into a session folder when its measurement was saved (I1IO_TABLE_SESSION_RESULT)
SESSION_RESULT = "session_result.json"
#: review 8, S-4: written into every session folder that goes into a Save BEFORE the run's file
#: changes (the checksum of the measurement being filed); see session_end.filed_into
FILING = "filing.json"


class Refused(Exception):
    def __init__(self, reason: str, **detail):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


@dataclass(frozen=True)
class Assembly:
    state: str                       # complete, partial, empty, refused
    reason: str = ""
    path: "Path | None" = None
    read: int = 0
    expected: "int | None" = None
    unread: "tuple[str, ...]" = ()
    rejected: "tuple[tuple[str, str], ...]" = ()     # (loc, reason) left out of the file
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"state": self.state, "reason": self.reason, "read": self.read,
                "expected": self.expected, "unread": list(self.unread),
                "rejected": [list(r) for r in self.rejected], "detail": self.detail,
                "file": self.path.name if self.path is not None else None}


def _table(text: str):
    from workflow.measurement_pairing import _first_table
    return _first_table(text)


def _device_free(fields: "list[str]") -> "list[int]":
    """The columns a measurement keeps: SAMPLE_ID, SAMPLE_LOC and what was measured (the same
    rule ``attach_device_values_from_chart`` uses to tell device columns)."""
    keep = []
    for i, f in enumerate(fields):
        if f in ("SAMPLE_ID", "SAMPLE_LOC") or f.startswith(("XYZ_", "LAB_", "SPEC_", "STDEV_",
                                                            "D_")):
            keep.append(i)
    return keep


#: the i1Pro 2's spectral bands in its standard resolution (380 to 730 nm in 10 nm steps)
STANDARD_BANDS = 36


def fields_shape(path) -> "dict | None":
    """What a measurement file holds (review 9, S-2): XYZ, L*a*b*, spectral, as booleans; None
    when the file cannot be read as a table with locations. Used to refuse an option that would
    make new readings unlike the ones a session builds on."""
    try:
        fields, _rows, _text = _rows_by_loc(Path(path))
    except (Refused, OSError, ValueError):
        return None
    bands = sum(1 for f in fields if f.startswith("SPEC_"))
    return {"xyz": "XYZ_X" in fields, "lab": "LAB_L" in fields, "spectral": bands > 0,
            # the i1Pro 2 saves 36 bands (380 to 730 nm, 10 nm); more is its high resolution
            "high_res": bands > STANDARD_BANDS}


def white_of(path) -> "str | None":
    """Review 14, M-2: the white reference a measurement file was made with: "stored" (it
    declares the table's stored white tile values), "own" (it does not), None when it cannot be
    read. The same rule the assembly applies to a base file."""
    try:
        from core.text_io import read_text
        text = read_text(Path(path), lenient=True)
    except (OSError, ValueError):
        return None
    if not text:
        return None
    return "stored" if re.search(r'^' + WHITE_KEYWORD + r'\s', text, re.M) else "own"


def _rows_by_loc(path: Path) -> "tuple[list[str], dict[str, list[str]], str]":
    from core.text_io import read_text
    text = read_text(path, lenient=True)
    t = _table(text)
    if t is None:
        raise Refused("reader_file_without_a_table", file=path.name)
    fields, rows = t
    if "SAMPLE_LOC" not in fields:
        raise Refused("reader_file_without_locations", file=path.name)
    li = fields.index("SAMPLE_LOC")
    out = {}
    for ln in rows:
        parts = ln.split()
        if len(parts) < len(fields):
            continue
        out[parts[li].strip('"')] = parts
    return fields, out, text


def device_values_by_loc(chart_ti2) -> "dict[str, tuple]":
    """4.3.54 (the row placement check): each location's device values in the chart (the
    columns a measurement does NOT keep, the same rule as ``_device_free``). Empty when the
    chart cannot be read: then no row counts as a row of identical patches."""
    try:
        fields, rows, _text = _rows_by_loc(Path(chart_ti2))
    except (Refused, OSError, ValueError, TypeError):
        return {}
    keep = set(_device_free(fields))
    dev = [i for i in range(len(fields)) if i not in keep]
    if not dev:
        return {}
    return {loc: tuple(parts[i] for i in dev) for loc, parts in rows.items()}


def _xyz_agrees(fields, parts, xyz) -> bool:
    if not all(k in fields for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")) or xyz is None:
        return True                   # -l saves Lab instead: nothing to compare
    try:
        got = [float(parts[fields.index(k)]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
    except (ValueError, IndexError):
        return False
    return all(math.isfinite(g) and abs(g - float(w)) <= XYZ_ABS_TOLERANCE + 1e-6 * abs(g)
               for g, w in zip(got, xyz))


def row_records(session_dirs) -> "list[tuple[Path, dict]]":
    """Every row record of the sessions, in reading order (sessions oldest first, then the
    job's own sequence number)."""
    out = []
    for k, sdir in enumerate(session_dirs):
        sdir = Path(sdir)
        if (sdir / DISCARDED).is_file():
            continue                   # the person discarded that session: never used
        for f in sorted(sdir.glob("*/*" + ROW_RECORD_SUFFIX)):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append((f, dict(rec, _session=k)))
    out.sort(key=lambda fr: (fr[1]["_session"], int(fr[1].get("seq", 0))))
    return out


def assemble(session_dirs, chart_ti2, out_ti3, base_ti3=None, cond: "str | None" = None
             ) -> Assembly:
    """The measurement of these sessions (and the run's earlier partial *base_ti3*), written to
    *out_ti3*. Never raises for a refusal: the result says it, and nothing is written then.

    *cond* ("M1" / "M2", the i1Pro 2 dual scan on the table): see :func:`_assemble_condition`."""
    if cond is not None:
        return _assemble_condition(session_dirs, chart_ti2, out_ti3, base_ti3, cond)
    from workflow.measurement_pairing import attach_device_values_from_chart, match_by_name
    from workflow.measurement_state import Ti3State, classify, unread_locations
    out_ti3 = Path(out_ti3)
    chart_ti2 = Path(chart_ti2)
    fields = None
    head = None
    rows: "dict[str, list[str]]" = {}
    rejected = []
    white = None                     # "own" / "stored": every row of a measurement alike
    try:
        if base_ti3 is not None and Path(base_ti3).is_file():
            bf, brows, btext = _rows_by_loc(Path(base_ti3))
            white = "stored" if re.search(r'^' + WHITE_KEYWORD + r'\s', btext, re.M) else "own"
            keep = _device_free(bf)
            fields = [bf[i] for i in keep]
            head = btext
            for loc, parts in brows.items():
                rows[loc] = [parts[i] for i in keep]
        for f, rec in row_records(session_dirs):
            name = rec.get("reader_ti3")
            accepted = rec.get("accepted") or []
            if not name or not accepted:
                for a in accepted:
                    rejected.append((a.get("loc", ""), "reader_saved_nothing"))
                continue
            path = f.parent / name
            if not path.is_file():
                for a in accepted:
                    rejected.append((a.get("loc", ""), "reader_saved_nothing"))
                continue
            rf, rrows, rtext = _rows_by_loc(path)
            keep = _device_free(rf)
            flds = [rf[i] for i in keep]
            if fields is None:
                fields, head = flds, rtext
            elif flds != fields:
                raise Refused("readings_with_different_fields", file=name)
            scale = rec.get("white_scale")
            kind = "stored" if scale else "own"
            if white is None:
                white = kind
            elif white != kind:
                raise Refused("readings_with_different_white_references", file=name)
            for a in accepted:
                loc = a.get("loc", "")
                parts = rrows.get(loc)
                if parts is None:
                    rejected.append((loc, "reader_saved_nothing"))
                    continue
                if not _xyz_agrees(rf, parts, a.get("xyz")):
                    rejected.append((loc, "saved_value_differs_from_the_reading"))
                    continue
                row = [parts[i] for i in keep]
                rows[loc] = _scaled(fields, row, scale) if scale else row
    except Refused as exc:
        return Assembly("refused", exc.reason, detail=exc.detail)
    if not rows:
        return Assembly("empty", "nothing_read", rejected=tuple(rejected))
    text = _write_device_free(head, fields, rows, white == "stored")
    out_ti3.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_ti3.with_name(out_ti3.name + ".part")
    tmp.write_text(text, encoding="utf-8")
    m = match_by_name(tmp, chart_ti2)
    if not m.ok:
        os.replace(tmp, out_ti3.with_name(out_ti3.name + ".refused"))
        return Assembly("refused", "readings_do_not_name_this_chart",
                        detail={"unknown": m.unknown[:20], "duplicated": m.duplicated[:20]})
    n = attach_device_values_from_chart(tmp, chart_ti2)
    if n != len(rows):
        os.replace(tmp, out_ti3.with_name(out_ti3.name + ".refused"))
        return Assembly("refused", "device_values_not_attached", detail={"written": n,
                                                                          "rows": len(rows)})
    os.replace(tmp, out_ti3)
    facts = classify(out_ti3, chart_ti2)
    unread = unread_locations(out_ti3, chart_ti2)
    state = {Ti3State.COMPLETE: "complete", Ti3State.PARTIAL: "partial"}.get(facts.state)
    if state is None:
        return Assembly("refused", f"measurement_{facts.state.value}", path=out_ti3,
                        read=len(rows), expected=facts.expected)
    return Assembly(state, "", out_ti3, len(rows), facts.expected,
                    tuple(sorted(unread or ())), tuple(rejected))


def m0_sources(session_dirs, base_ti3=None) -> "dict[str, tuple]":
    """4.3.50: where each patch's M0 row of :func:`assemble` comes from, by the SAME rules (the
    base's rows the oldest, then every accepted reading in reading order whose saved value is
    the reading's; the last one wins): ``("base",)`` or ``("row", <record file>, <record>)``.
    The M0 assembly must have succeeded (its refusals are not repeated here)."""
    src: "dict[str, tuple]" = {}
    if base_ti3 is not None and Path(base_ti3).is_file():
        _bf, brows, _bt = _rows_by_loc(Path(base_ti3))
        for loc in brows:
            src[loc] = ("base",)
    for f, rec in row_records(session_dirs):
        name = rec.get("reader_ti3")
        accepted = rec.get("accepted") or []
        if not name or not accepted:
            continue
        path = f.parent / name
        if not path.is_file():
            continue
        rf, rrows, _rt = _rows_by_loc(path)
        for a in accepted:
            loc = a.get("loc", "")
            parts = rrows.get(loc)
            if parts is None or not _xyz_agrees(rf, parts, a.get("xyz")):
                continue
            src[loc] = ("row", f, rec)
    return src


def base_condition_file(base_ti3, cond: str) -> "Path | None":
    """The file holding the *cond* readings of the run's measurement a session completes: its
    complete pair when in step, else its PARTIAL pair when in step (``<hash>-Mx.partial.ti3``,
    the patches that have all three; the others are M0 only), else None (no patch of the base
    has *cond*)."""
    import workflow.i1pro3_conditions as ic
    bc = ic.condition_file(base_ti3, cond)
    if bc is not None and Path(bc) != Path(base_ti3):
        return Path(bc)
    part = ic.partial_sibling_path(base_ti3, cond)
    if part is not None and ic.sibling_in_step(base_ti3, part):
        return Path(part)
    return None


def _assemble_condition(session_dirs, chart_ti2, out_ti3, base_ti3, cond: str) -> Assembly:
    """4.3.50 (Basti's rule of 19 Nov 2026, as by hand): the *cond* ("M1" / "M2") file of the
    measurement :func:`assemble` makes of the same sessions and base. EVERY patch takes its
    *cond* row from the SAME reading its M0 row comes from (:func:`m0_sources`): that row
    record's own file of this condition, or the base's condition file (complete or partial pair,
    :func:`base_condition_file`). A patch whose M0 reading has no *cond* value is left out of
    this file and named in ``detail["m0_only"]``: it is M0 only, and every other patch keeps its
    *cond*. M1 and M2 are never taken from another reading than the main file's.

    State "complete" / "partial" as for any measurement (of the chart), "empty" when no patch
    has *cond*, "refused" when a file cannot be used (its fields, its white)."""
    from workflow.measurement_pairing import attach_device_values_from_chart, match_by_name
    from workflow.measurement_state import Ti3State, classify, unread_locations
    out_ti3 = Path(out_ti3)
    chart_ti2 = Path(chart_ti2)
    fields = None
    head = None
    rows: "dict[str, list[str]]" = {}
    m0_only: "list[str]" = []
    white = None
    try:
        src = m0_sources(session_dirs, base_ti3)
        base_rows: "dict[str, list[str]]" = {}
        base_fields = None
        if any(v[0] == "base" for v in src.values()):
            bc = base_condition_file(base_ti3, cond)
            btext_main = Path(base_ti3).read_text(encoding="utf-8", errors="replace")
            white = ("stored" if re.search(r'^' + WHITE_KEYWORD + r'\s', btext_main, re.M)
                     else "own")
            if bc is not None:
                bf, brows, btext = _rows_by_loc(bc)
                keep = _device_free(bf)
                base_fields = [bf[i] for i in keep]
                fields, head = base_fields, btext
                base_rows = {loc: [parts[i] for i in keep] for loc, parts in brows.items()}
        files: "dict[Path, tuple]" = {}
        for loc in src:
            kind = src[loc]
            if kind[0] == "base":
                if loc in base_rows:
                    rows[loc] = base_rows[loc]
                else:
                    m0_only.append(loc)
                continue
            f, rec = kind[1], kind[2]
            name = (rec.get("conditions") or {}).get(cond)
            if not name:
                m0_only.append(loc)
                continue
            path = f.parent / name
            if path not in files:
                if not path.is_file():
                    files[path] = None
                else:
                    rf, rrows, rtext = _rows_by_loc(path)
                    keep = _device_free(rf)
                    files[path] = ([rf[i] for i in keep], rrows, keep, rtext)
            got = files[path]
            if got is None or loc not in got[1]:
                m0_only.append(loc)
                continue
            flds, rrows, keep, rtext = got
            if fields is None:
                fields, head = flds, rtext
            elif flds != fields:
                raise Refused("readings_with_different_fields", file=name)
            scale = rec.get("white_scale")
            kind_w = "stored" if scale else "own"
            if white is None:
                white = kind_w
            elif white != kind_w:
                raise Refused("readings_with_different_white_references", file=name)
            row = [rrows[loc][i] for i in keep]
            rows[loc] = _scaled(fields, row, scale) if scale else row
    except Refused as exc:
        return Assembly("refused", exc.reason, detail=exc.detail)
    detail = {"condition": cond, "m0_only": sorted(set(m0_only))}
    if not rows:
        return Assembly("empty", "nothing_read", detail=detail)
    text = _write_device_free(head, fields, rows, white == "stored")
    out_ti3.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_ti3.with_name(out_ti3.name + ".part")
    tmp.write_text(text, encoding="utf-8")
    m = match_by_name(tmp, chart_ti2)
    if not m.ok:
        os.replace(tmp, out_ti3.with_name(out_ti3.name + ".refused"))
        return Assembly("refused", "readings_do_not_name_this_chart",
                        detail=dict(detail, unknown=m.unknown[:20],
                                    duplicated=m.duplicated[:20]))
    n = attach_device_values_from_chart(tmp, chart_ti2)
    if n != len(rows):
        os.replace(tmp, out_ti3.with_name(out_ti3.name + ".refused"))
        return Assembly("refused", "device_values_not_attached",
                        detail=dict(detail, written=n, rows=len(rows)))
    os.replace(tmp, out_ti3)
    facts = classify(out_ti3, chart_ti2)
    unread = unread_locations(out_ti3, chart_ti2)
    state = {Ti3State.COMPLETE: "complete", Ti3State.PARTIAL: "partial"}.get(facts.state)
    if state is None:
        return Assembly("refused", f"measurement_{facts.state.value}", path=out_ti3,
                        read=len(rows), expected=facts.expected, detail=detail)
    return Assembly(state, "", out_ti3, len(rows), facts.expected,
                    tuple(sorted(unread or ())), (), detail)


def keep_only(src_ti3, locs, out_ti3) -> int:
    """4.3.50: *src_ti3* with only the rows of *locs* (its own order, its header as it is),
    written to *out_ti3* (atomically); returns how many rows were kept. The partial pair of a
    measurement holds exactly the patches that have all three conditions."""
    from core.text_io import read_text
    text = read_text(Path(src_ti3), lenient=True)
    fields = text.split("BEGIN_DATA_FORMAT", 1)[1].split("END_DATA_FORMAT", 1)[0].split()
    li = fields.index("SAMPLE_LOC")
    head, rest = text.split("\nBEGIN_DATA\n", 1)
    data, tail = rest.split("\nEND_DATA", 1)
    want = set(locs)
    kept = []
    for ln in data.splitlines():
        tok = ln.split()
        if len(tok) == len(fields) and tok[li].strip('"') in want:
            kept.append(ln)
    head = re.sub(r"(?m)^NUMBER_OF_SETS\s+\d+\s*$", f"NUMBER_OF_SETS {len(kept)}", head)
    out = Path(out_ti3)
    tmp = out.with_name(out.name + ".part")
    tmp.write_text(head + "\nBEGIN_DATA\n" + "\n".join(kept) + "\nEND_DATA" + tail,
                   encoding="utf-8")
    os.replace(tmp, out)
    return len(kept)


def _scaled(fields, row, scale) -> "list[str]":
    """D-4b: one row with its spectrum scaled per band to the table's stored white (factors on
    380-730 nm at 10 nm, interpolated for other bands) and its XYZ / L*a*b* computed again
    from that spectrum the way ArgyllCMS's chartread does (D50, 2 degree observer)."""
    from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
    from . import spot as sp
    from .strip import lab_d50
    spec = [(i, float(f[5:])) for i, f in enumerate(fields) if f.startswith("SPEC_")]
    if not spec:
        raise Refused("stored_white_needs_spectral_values")
    out = list(row)
    vals = []
    for i, wl in spec:
        v = float(row[i]) * sp.factor_at(scale, wl)
        out[i] = f"{v:.5f}"
        vals.append(v)
    xyz = [float(c) for c in spectra_to_xyz_like_argyll([vals], [wl for _i, wl in spec],
                                                       illuminant="D50", observer="1931_2",
                                                       percent=True)[0]]
    for k, v in zip(("XYZ_X", "XYZ_Y", "XYZ_Z"), xyz):
        if k in fields:
            out[fields.index(k)] = f"{v:.6f}"
    if "LAB_L" in fields:
        for k, v in zip(("LAB_L", "LAB_A", "LAB_B"), lab_d50(xyz)):
            if k in fields:
                out[fields.index(k)] = f"{v:.6f}"
    return out


def _write_device_free(head_text: str, fields, rows, stored_white: bool = False) -> str:
    out = []
    for ln in head_text.splitlines():
        s = ln.strip()
        if s.startswith("NUMBER_OF_FIELDS"):
            break
        if re.match(r'^KEYWORD\s+"(CHROMIQ_DEVICE_FROM_CHART|' + TABLE_KEYWORD + '|'
                    + WHITE_KEYWORD + ')"', s):
            continue
        if re.match(r'^(CHROMIQ_DEVICE_FROM_CHART|' + TABLE_KEYWORD + '|' + WHITE_KEYWORD
                    + r'|COLOR_REP)\s', s):
            continue
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    at = 1 if out and out[0].strip().startswith("CTI3") else 0
    out[at:at] = [f'KEYWORD "{TABLE_KEYWORD}"', f'{TABLE_KEYWORD} "{TABLE_VALUE}"']
    if stored_white:
        out[at + 2:at + 2] = [f'KEYWORD "{WHITE_KEYWORD}"', f'{WHITE_KEYWORD} "{WHITE_STORED}"']
    body = [" ".join(r) for r in rows.values()]
    return ("\n".join(out) + "\n\n" + f"NUMBER_OF_FIELDS {len(fields)}\nBEGIN_DATA_FORMAT\n"
            + " ".join(fields) + " \nEND_DATA_FORMAT\n\n"
            + f"NUMBER_OF_SETS {len(body)}\nBEGIN_DATA\n" + "\n".join(body)
            + "\nEND_DATA\n")


def file_into_run(assembly: Assembly, run, may_replace: "Path | None" = None) -> str:
    """The person's Save: the assembled measurement becomes ``Run.measurement_ti3`` (one atomic
    replace, read-only files too). Returns "" or the refusal id. A run that already holds a
    measurement keeps it unless it is the partial this session completed (*may_replace*): any
    other existing measurement is archived by the measurement window's own rules (step 8), not
    here."""
    from core.file_manager import replace_read_only_too
    if assembly.state not in ("complete", "partial") or assembly.path is None:
        return "nothing_to_file"
    dest = Path(run.measurement_ti3)
    if dest.exists():
        if may_replace is None or Path(may_replace).resolve() != dest.resolve():
            return "run_has_a_measurement_already"
    # review 9, NOTE: the copy is made in the SESSION folder (beside the assembled file, on the
    # same disk as the run's file, so the replace stays one atomic step): a copy cut off by a
    # full disk leaves nothing in the run's own folder, and the next Save overwrites it
    tmp = Path(assembly.path).with_name(dest.name + ".table-part")
    shutil.copyfile(str(assembly.path), str(tmp))
    replace_read_only_too(tmp, dest)
    return ""
