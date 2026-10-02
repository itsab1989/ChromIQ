"""Which patches a re-read confirmed, kept with the measurement (#182 K4).

Knut, #182 5959352118: *"the information on which patches were re-measured
and confirmed as not to be misreadings are remembered after a measurement is
stopped, which must anyway be remembered for the Check & Refine function"*.
Sebastian approved storing it (5959447807).

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
        "F4":  {"kind": "learned", "like": "A23"}}}

Only ``confirmed`` entries are references (a re-read agreed with the reading
before it). ``learned`` entries are kept for the preview and for anyone reading
the file; they are judged again from the references every time, so they are
never loaded back as references.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA = 1
SUFFIX = ".confirmed.json"
KIND_CONFIRMED = "confirmed"
KIND_LEARNED = "learned"
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


def _clean_patches(patches: dict) -> dict:
    out: dict = {}
    for loc, entry in (patches or {}).items():
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        if kind == KIND_CONFIRMED:
            out[str(loc)] = {
                "kind": KIND_CONFIRMED,
                "de": round(float(entry.get("de", 0.0)), 2),
                "prev_de": (None if entry.get("prev_de") is None
                            else round(float(entry["prev_de"]), 2)),
                "exp_lab": [round(float(v), 4) for v in entry.get("exp_lab", [])[:3]],
                "meas_lab": [round(float(v), 4) for v in entry.get("meas_lab", [])[:3]],
                "shift": [round(float(v), 4) for v in entry.get("shift", [])[:3]],
                "standout": (None if entry.get("standout") is None
                             else round(float(entry["standout"]), 3)),
            }
        elif kind == KIND_LEARNED:
            out[str(loc)] = {"kind": KIND_LEARNED, "like": str(entry.get("like", ""))}
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
    """The patch locations a re-read CONFIRMED for this measurement.

    Validated against the file's hash: an empty set when there is no memory or
    it belongs to a different version of the ``.ti3``. Only confirmed patches,
    never learned ones: Check & Refine may leave out what a re-read proved, not
    what a rule guessed.
    """
    data = load(ti3_path)
    if not data:
        return set()
    return {loc for loc, e in data["patches"].items()
            if e.get("kind") == KIND_CONFIRMED}


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
