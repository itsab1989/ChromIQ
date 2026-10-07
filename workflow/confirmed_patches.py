"""Which patches a re-read confirmed, kept with the measurement (#182 K4).

Knut, #182 5959352118: *"the information on which patches were re-measured
and confirmed as not to be misreadings are remembered after a measurement is
stopped, which must anyway be remembered for the Check & Refine function"*.
Sebastian approved storing it (5959447807). On 2026-10-04 (5980560281) Knut
ruled that Check & Refine is NOT influenced by it: see below.

The yellow outlines of ``workflow/patch_flags.py`` used to live only in the
Measure tab's memory, so they were gone the moment a session ended. This file
keeps them beside the measurement they describe::

    runs/run1/<stem>.ti3
    runs/run1/<stem>.confirmed.json
    runs/run1/verifications/<date>/<stem>-verify.confirmed.json

NO HYPHEN BEFORE ``confirmed``: a project rename carries every
``<stem>[-cal|-verify]…​.<ext>`` file along (``core/file_manager.py``, the
``tail_re`` of the rename), and ``.confirmed.json`` is such an extension.

The file is only believed while it describes THAT measurement: it records the
SHA-256 of the ``.ti3`` it was written for, and a file whose ``.ti3`` has
changed since (re-read by another tool, replaced, edited) is ignored rather
than applied to readings it never saw.

Schema 1::

    {"schema": 1, "ti3_sha256": "…", "mode": "strip" | "patch",
     "patches": {
        "A23": {"kind": "confirmed", "de": 103.2, "prev_de": 102.9,
                "exp_lab": [..], "meas_lab": [..], "shift": [..],
                "standout": 61.0 | null},
        "F4":  {"kind": "learned", "like": "A23"},
        "C7":  {"kind": "peer", "with": ["K2", "R9"]},
        "D2":  {"kind": "corrected", "de": 58.1, "by": "neighbour"},
        "J28": {"kind": "unsettled", "prevs": [120.3],
                "readings": [{"de": 120.3, "meas_lab": [..]}]}}}

``corrected`` (Knut, #182 5984277558): a patch that was red and whose live
re-read fits now, drawn green; the first reading's ΔE and the rule that
flagged it ("neighbour" or "limit"). Never loaded as a reference.

Only ``confirmed`` entries are references (a re-read agreed with the reading
before it). ``learned`` entries are kept for the preview and for anyone reading
the file; they are judged again from the references every time, so they are
never loaded back as references. ``peer`` entries (Knut, #182 5979886227) are
patches that similar patches of other strips confirmed, as the session judged
them: written for the record, and never loaded back either, because they are
worked out again from the readings and the limit.

CHECK & REFINE NEVER READS THIS FILE (Knut, #182 5980560281, 2026-10-04):
it checks the measurement through the built profile, and every high error it
finds feeds the refinement recommendations, whatever the Measure tab's red or
yellow outlines say. The file is the Measure tab's memory only.
`tests/test_check_refine_ignores_the_confirmed_patches_memory.py` keeps it so.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = 1
SUFFIX = ".confirmed.json"
KIND_CONFIRMED = "confirmed"
KIND_LEARNED = "learned"
KIND_PEER = "peer"
#: A misread a re-read corrected (green, Knut #182 5984277558): the first
#: reading's ΔE and the rule that flagged it. Never a reference.
KIND_CORRECTED = "corrected"
#: Read again past the limit, like none of its earlier readings (red, Knut
#: #182 6045500910): the earlier readings' ΔE past the limit (``prevs``) and
#: every earlier flagged reading (``readings``: ΔE and measured L*a*b*), so it
#: is red again when opened and a later re-read is compared with them.
KIND_UNSETTLED = "unsettled"

MODE_STRIP = "strip"
MODE_PATCH = "patch"


def confirmed_path(ti3_path: "str | Path") -> Path:
    """``<stem>.confirmed.json`` beside *ti3_path*."""
    p = Path(ti3_path)
    return p.with_name(p.stem + SUFFIX)


def ti3_sha256(ti3_path: "str | Path") -> "str | None":
    """The SHA-256 of the measurement file, or None when it cannot be read."""
    try:
        return hashlib.sha256(Path(ti3_path).read_bytes()).hexdigest()
    except OSError:
        return None


def _clean_entry(entry: dict) -> "dict | None":
    """One stored patch, checked; None when it is not one this code wrote.

    A file is only believed when its hash matches, but its CONTENTS are still
    whatever is on disk: a hand-edited or damaged file whose hash happens to
    match (or a ``.ti3`` and memory edited together) must be skipped entry by
    entry, never raise into the measurement it describes (review AN: a
    ``"de": "abc"`` made ``load``, ``confirmed_locations`` and the verification
    filing's ``carry`` raise ValueError)."""
    kind = entry.get("kind")
    if kind == KIND_LEARNED:
        return {"kind": KIND_LEARNED, "like": str(entry.get("like", ""))}
    if kind == KIND_PEER:
        with_ = entry.get("with", [])
        if not isinstance(with_, (list, tuple)):
            return None
        return {"kind": KIND_PEER, "with": [str(v) for v in with_]}
    if kind == KIND_CORRECTED:
        try:
            de = float(entry.get("de", 0.0))
        except (TypeError, ValueError):
            return None
        if de != de or de in (float("inf"), float("-inf")):
            return None
        by = "neighbour" if entry.get("by") == "neighbour" else "limit"
        return {"kind": KIND_CORRECTED, "de": round(de, 2), "by": by}
    if kind == KIND_UNSETTLED:
        try:
            prevs = [round(float(x), 2) for x in entry.get("prevs") or ()]
            readings = []
            for r in entry.get("readings") or ():
                lab = [round(float(x), 4) for x in r["meas_lab"][:3]]
                de = round(float(r["de"]), 2)
                if len(lab) != 3 or any(v != v or abs(v) == float("inf")
                                        for v in lab + [de]):
                    return None
                readings.append({"de": de, "meas_lab": lab})
        except (KeyError, TypeError, ValueError):
            return None
        if not prevs or not readings or any(
                v != v or abs(v) == float("inf") for v in prevs):
            return None
        return {"kind": KIND_UNSETTLED, "prevs": prevs, "readings": readings}
    if kind != KIND_CONFIRMED:
        return None

    def num(v, nd):
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            raise ValueError("not a finite number")
        return round(f, nd)

    def lab(key):
        v = entry.get(key, [])
        if not isinstance(v, (list, tuple)):
            raise TypeError(key)
        return [num(x, 4) for x in v[:3]]

    try:
        return {
            "kind": KIND_CONFIRMED,
            "de": num(entry.get("de", 0.0), 2),
            "prev_de": (None if entry.get("prev_de") is None
                        else num(entry["prev_de"], 2)),
            "exp_lab": lab("exp_lab"),
            "meas_lab": lab("meas_lab"),
            "shift": lab("shift"),
            "standout": (None if entry.get("standout") is None
                         else num(entry["standout"], 3)),
        }
    except (TypeError, ValueError):
        return None


def _clean_patches(patches: dict) -> dict:
    out: dict = {}
    if not isinstance(patches, dict):
        return out
    for loc, entry in patches.items():
        if not isinstance(entry, dict):
            continue
        clean = _clean_entry(entry)
        if clean is not None:
            out[str(loc)] = clean
    return out


def write(ti3_path: "str | Path", patches: dict, mode: str) -> "Path | None":
    """Write the memory for *ti3_path*, stamped with its current hash.

    Atomic (``write_json_atomically``): a crash leaves the previous file or the
    new one, never half of one. Returns the path written, or None when the
    folder is not writable. A measurement with nothing confirmed or learned
    still gets a file, so a stale one from an earlier state cannot survive.
    """
    from core.file_manager import write_json_atomically
    ti3_path = Path(ti3_path)
    payload = {
        "schema": SCHEMA,
        "ti3_sha256": ti3_sha256(ti3_path),
        "mode": MODE_PATCH if mode == MODE_PATCH else MODE_STRIP,
        "patches": _clean_patches(patches),
    }
    dst = confirmed_path(ti3_path)
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(dst, payload)
    except OSError:
        return None
    return dst


def read_raw(ti3_path: "str | Path") -> "dict | None":
    """The file as stored, without checking it against the measurement."""
    try:
        data = json.loads(confirmed_path(ti3_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return None
    return data


def load(ti3_path: "str | Path") -> "dict | None":
    """The memory for *ti3_path*, or None when there is none or it describes
    another version of the file (its ``ti3_sha256`` does not match)."""
    data = read_raw(ti3_path)
    if data is None:
        return None
    want = data.get("ti3_sha256")
    if not want or want != ti3_sha256(ti3_path):
        return None
    data["patches"] = _clean_patches(data.get("patches") or {})
    if data.get("mode") not in (MODE_STRIP, MODE_PATCH):
        data["mode"] = None
    return data


def confirmed_locations(ti3_path: "str | Path") -> "set[str]":
    """The patch locations the memory records as CONFIRMED for this
    measurement: by a re-read, or by similar patches (``peer``). Never learned
    ones.

    Validated against the file's hash: an empty set when there is no memory or
    it belongs to a different version of the ``.ti3``. For reading the record
    (tools, tests); Check & Refine must never call it (Knut, #182 5980560281).
    """
    data = load(ti3_path)
    if not data:
        return set()
    return {loc for loc, e in data["patches"].items()
            if e.get("kind") in (KIND_CONFIRMED, KIND_PEER)}


def carry(src_ti3: "str | Path", before_sha: "str | None",
          dst_ti3: "str | Path") -> "Path | None":
    """Carry the memory of *src_ti3* to *dst_ti3*, re-stamped for *dst*.

    For the places where ChromIQ itself renames, moves or rewrites a
    measurement (the verification marker, filing into a dated folder): the
    readings are the same, so what was confirmed about them still holds.
    *before_sha* is the hash *src_ti3* had while the memory described it, taken
    before the move or rewrite; only a memory written for exactly that file is
    carried. Call it once *dst_ti3* holds its final contents. *src*'s memory is
    removed, so it cannot be mistaken for the moved measurement's.
    """
    src_ti3, dst_ti3 = Path(src_ti3), Path(dst_ti3)
    data = read_raw(src_ti3)
    if data is None or not before_sha or data.get("ti3_sha256") != before_sha:
        return None
    out = write(dst_ti3, data.get("patches") or {}, data.get("mode") or MODE_STRIP)
    src_mem = confirmed_path(src_ti3)
    if out is not None and src_mem != out:
        try:
            src_mem.unlink()
        except OSError:
            pass
    return out
