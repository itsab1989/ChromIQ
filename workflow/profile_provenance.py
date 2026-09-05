"""Was this profile built from this measurement?

Check & Refine runs ``profcheck`` — and §6c of
``docs/design/unified_measurement_management.md`` says exactly what that
compares: *"a profile against **the data it was built from**"*. The grade,
the ΔE figures and the list of strips to re-measure are all read as statements
about the profile, and they only mean that when the pairing is true.

**The pairing can quietly stop being true, and the Check & Refine flow is the
place it happens.** Guided refinement re-reads a strip with ``chartread -r``,
which rewrites the run's ``.ti3`` in place. Nothing rebuilds the profile — the
window that follows offers to *open* the Build Profile tab and says in its own
tooltip that the profile is not built yet. So the run can sit with a
measurement that is newer than its profile, and both the session restore
(``ui/main_window.py``) and Check & Refine's own ``_auto_fill_icc`` will hand
that pair to profcheck without a word.

Measured on the owner's own 924-patch chart (agent BF, 2026-09-05): re-reading
28 strips at *the same reading quality* and rebuilding takes the average ΔE
from 0.770 to 0.753 — an improvement. Re-reading the same strips at the same
quality and **not** rebuilding takes it from 0.770 to 0.835, and the peak from
5.99 to 10.23. Same readings, opposite verdicts, and nothing on screen says
which of the two happened.

**How it is settled, rather than guessed.** ArgyllCMS ``colprof`` embeds the
whole ``.ti3`` it was built from in the profile's ``targ`` tag (ChromIQ's own
engine does the same — ``workflow/engine_builder.py``, ``embed_ti3``). So the
profile carries its own source data and the question needs no timestamps:
extract ``targ`` and look for the measurement's rows in it.

**Why a SUBSET and not equality.** A refinement build feeds colprof
``merged.ti3`` — the fresh chart plus the pre-conditioning measurement,
concatenated by ``average -m`` — so ``merged.icc``'s ``targ`` legitimately
holds *more* rows than the ``<stem>.ti3`` Check & Refine works from. Requiring
equality would call every merged run stale. The honest question is the weaker
one: **is every patch of this measurement present in the profile's source data,
with the value it has now?**

Nothing here decides what to show; it answers the question and lets the caller
say so. It never raises: an unreadable profile, a missing tag (``colprof -n``)
or an unparseable file all come back as UNKNOWN, which says nothing.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: How far two CIE readings of one patch may differ and still be "the same
#: reading". The .ti3 is written with six decimals and the tag holds the file
#: byte for byte, so a genuine match is exact; this only absorbs a reformat.
CIE_EPSILON = 1e-4


class Provenance(Enum):
    """What can be said about a (profile, measurement) pair."""

    #: The profile's source data contains every patch of this measurement,
    #: unchanged. profcheck's figures mean what they are read to mean.
    BUILT_FROM_THIS = "built_from_this"
    #: The profile's source data is missing patches of this measurement, or
    #: holds different readings for them. The profile was not built from the
    #: measurement it is about to be judged against.
    NOT_BUILT_FROM_THIS = "not_built_from_this"
    #: No answer: no 'targ' tag, an unreadable file, no CIE fields to compare.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProvenanceResult:
    verdict: Provenance
    #: Patches of the measurement whose reading differs from the profile's copy.
    changed: int = 0
    #: Patches of the measurement that the profile's source data does not hold.
    missing: int = 0
    #: Patches compared in total.
    total: int = 0
    #: Why the answer is UNKNOWN, for the log. Never shown to the user.
    reason: str = ""

    @property
    def stale(self) -> bool:
        return self.verdict is Provenance.NOT_BUILT_FROM_THIS

    @property
    def differing(self) -> int:
        return self.changed + self.missing


# ---------------------------------------------------------------- ICC 'targ'
def embedded_ti3(icc_path: Path | str) -> str | None:
    """The ``.ti3`` text embedded in *icc_path*'s ``targ`` tag, or None.

    Parsed here rather than shelled out to ``extractttag`` for the same reason
    ``icc_info`` parses the header itself: the check runs on the UI thread
    before a profcheck and must not depend on the Argyll path being set, nor
    cost a process. ``targ`` is an ICC ``textType``: signature(4) 'text' ·
    reserved(4) · NUL-terminated ASCII.
    """
    try:
        data = Path(icc_path).read_bytes()
    except OSError as exc:
        log.debug("provenance: cannot read %s: %s", icc_path, exc)
        return None
    try:
        count = struct.unpack_from(">I", data, 128)[0]
        for i in range(count):
            base = 132 + i * 12
            if base + 12 > len(data):
                break
            if data[base:base + 4] != b"targ":
                continue
            offset, size = struct.unpack_from(">II", data, base + 4)
            if offset + 8 > len(data) or size < 8:
                return None
            if data[offset:offset + 4] != b"text":
                return None
            raw = data[offset + 8:offset + min(size, len(data) - offset)]
            return raw.split(b"\x00", 1)[0].decode("latin-1")
    except (struct.error, IndexError, UnicodeDecodeError) as exc:
        log.debug("provenance: cannot parse %s: %s", icc_path, exc)
        return None
    return None


# ---------------------------------------------------------------- CGATS rows
_CIE_FIELDS = (("XYZ_X", "XYZ_Y", "XYZ_Z"), ("LAB_L", "LAB_A", "LAB_B"))


def _readings(text: str) -> dict[str, list[tuple[float, float, float]]] | None:
    """{patch key: CIE triple} for one CGATS text, or None when it has none.

    The key is ``SAMPLE_LOC`` when the file has one and ``SAMPLE_ID``
    otherwise — the same identity chartread itself resumes by
    (``spectro/chartread.c``, which matches resumed rows on ``SAMPLE_LOC``).
    """
    lines = text.splitlines()
    fields: list[str] = []
    in_fmt = in_data = False
    rows: list[list[str]] = []
    for ln in lines:
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            in_fmt = True
        elif s == "END_DATA_FORMAT":
            in_fmt = False
        elif s == "BEGIN_DATA":
            in_data = True
        elif s == "END_DATA":
            in_data = False
        elif in_fmt:
            fields += s.split()
        elif in_data and s:
            rows.append(s.split())
    if not fields or not rows:
        return None
    ix = {name: i for i, name in enumerate(fields)}
    cie = next((trio for trio in _CIE_FIELDS if all(f in ix for f in trio)), None)
    if cie is None:
        return None
    key_field = "SAMPLE_LOC" if "SAMPLE_LOC" in ix else "SAMPLE_ID"
    if key_field not in ix:
        return None
    out: dict[str, list[tuple[float, float, float]]] = {}
    for r in rows:
        try:
            key = r[ix[key_field]].strip('"')
            #: A LIST, BECAUSE A MERGED FILE REPEATS EVERY LOCATION.
            #
            # `average -m` concatenates two charts' rows, and both start their
            # locations at "A1" — so `merged.ti3` holds two different readings
            # under that one key. A plain dict keeps the last, which is the
            # PRE-CONDITIONING chart's, and every patch of the fresh
            # measurement then looks changed: measured on a real merge, 240 of
            # 240 "changed" for a profile that was built from exactly that data.
            out.setdefault(key, []).append(
                tuple(float(r[ix[f]]) for f in cie))          # type: ignore[arg-type]
        except (IndexError, ValueError):
            continue
    return out or None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="latin-1")
    except OSError as exc:
        log.debug("provenance: cannot read %s: %s", path, exc)
        return None


# ---------------------------------------------------------------- the answer
def check(icc_path: Path | str, ti3_path: Path | str) -> ProvenanceResult:
    """Was *icc_path* built from the data now in *ti3_path*?

    Never raises. UNKNOWN whenever the question cannot be answered — a profile
    built with ``colprof -n``, a file that will not parse, a measurement with
    no CIE columns. Saying nothing is the only safe answer there: this check
    exists to stop a misleading figure being believed, never to invent one.
    """
    tag = embedded_ti3(icc_path)
    if tag is None:
        return ProvenanceResult(Provenance.UNKNOWN,
                                reason="the profile carries no copy of its source data")
    source = _readings(tag)
    if source is None:
        return ProvenanceResult(Provenance.UNKNOWN,
                                reason="the profile's source data has no readable CIE values")
    text = _read(Path(ti3_path))
    if text is None:
        return ProvenanceResult(Provenance.UNKNOWN,
                                reason="the measurement could not be read")
    mine = _readings(text)
    if mine is None:
        return ProvenanceResult(Provenance.UNKNOWN,
                                reason="the measurement has no readable CIE values")

    changed = missing = 0
    for key, values in mine.items():
        theirs = source.get(key)
        if not theirs:
            missing += len(values)
            continue
        for value in values:
            if not any(all(abs(a - b) <= CIE_EPSILON for a, b in zip(value, t))
                       for t in theirs):
                changed += 1
    verdict = (Provenance.BUILT_FROM_THIS if not (changed or missing)
               else Provenance.NOT_BUILT_FROM_THIS)
    return ProvenanceResult(verdict, changed=changed, missing=missing,
                            total=sum(len(v) for v in mine.values()))
