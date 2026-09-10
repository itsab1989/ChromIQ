"""Reference sets for the Measurement Report (#182): the aim colours of a named
printing condition, and the rules for what they may and may not judge.

A **reference set** is a table of aim colours: what a patch was supposed to look
like. It is not a limit set. :mod:`workflow.compliance_sets` owns the limits,
the numbers a value is judged against; this module owns the aims. Merging the
two would let a rights holder's name sit over the word PASS, and that is the
one thing the Fogra grant forbids.

**Fogra's condition, met by construction rather than by wording.** Fogra's terms
of use, https://fogra.org/en/downloads/work-tools/characterisation-data as read
on 2026-09-10, permit free redistribution inside commercial software *"provided
that the data are distributed unmodified and Fogra is identified as the
source"*, and add that the FOGRAxx designation *"may be used solely to identify
the respective reference data. Such use does not imply certification, approval
or endorsement by Fogra."* So:

* :func:`available` refuses a data file that has no entry in ``SOURCE.json``, or
  whose entry names no source and no terms. A set with no credit cannot reach
  the screen, so no future addition can arrive without one;
* the credit travels with the set as :attr:`ReferenceSet.credit_line`, which is
  a required part of every place a set is shown;
* nothing here produces a verdict word. A reference supplies aims; the verdict
  comes from a ChromIQ limit set, so PASS is always under ChromIQ's name.

**And the honest limit of what these files can judge.** ChromIQ profiles RGB
printers; every bundled set describes a CMYK printing condition. The two have no
patch in common except the paper, because one's device values are R, G, B and
the other's are C, M, Y, K. :func:`can_fill` therefore allows the substrate row
and refuses the two solids rows, rather than warning about them: pairing a
printer's most saturated cyan with a 100 % cyan offset solid because both are
called C is pairing two things because their labels rhyme.

The full comparison, every row, needs a chart whose patches were produced FROM a
set's aims through the profile under test. That is a proof, ChromIQ has the
machinery for it (``workflow/gamut_target.py`` and the colorimetric-reference
path at ``workflow/measurement_report.py:535``), and it is not wired to these
files yet.

No Qt in here, on the pattern of :mod:`workflow.compliance_sets`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.i18n import tr
from core.resource_path import resource_path

log = logging.getLogger(__name__)

#: The folder the bundled sets live in, and the provenance file that gates them.
DATA_DIR = "data/reference_sets/fogra"
SOURCE_FILE = "SOURCE.json"

#: The rows of the Report limits table a reference set can fill, and whether a
#: set whose device space differs from the chart's may fill them. The keys are
#: row ids of :mod:`workflow.compliance_sets`.
#:
#: ``"any"``     the row compares a property of the PAPER, which does not
#:               belong to the printing process, so a CMYK reference may fill
#:               it on an RGB sheet;
#: ``"same"``    the row compares patches, so it needs the reference and the
#:               chart to be the same device space AND the chart to have been
#:               built from the reference (:func:`can_fill` refuses it until
#:               that exists).
ROW_PAIRING: "dict[str, str]" = {
    "substrate_de00_max": "any",
    "solids_de00_max": "same",
    "cmy_solids_dhab_max": "same",
}

#: Why a row is refused. English source; the report window turns these into
#: sentences through :func:`refusal_text`.
REFUSE_CROSS_SPACE = "cross_space"
REFUSE_NOT_A_PAPER = "not_a_paper"
REFUSE_NEEDS_BUILT_CHART = "needs_built_chart"
REFUSE_UNKNOWN_ROW = "unknown_row"

#: The sentences, English source (the i18n extractor sweeps this dict).
REFUSAL_REASONS: "dict[str, str]" = {
    REFUSE_CROSS_SPACE:
        "This reference describes a CMYK printing condition. The solid colours "
        "of your sheet are your printer's own inks, so there is nothing here "
        "to compare them with.",
    REFUSE_NOT_A_PAPER:
        "This reference is a colour exchange space, not a real paper, so there "
        "is no paper colour to compare yours against.",
    REFUSE_NEEDS_BUILT_CHART:
        "This row needs a chart built from this reference's own colours. Your "
        "sheet was printed from its own chart, so the patches have no partner "
        "in the reference.",
    REFUSE_UNKNOWN_ROW:
        "This version of ChromIQ has no way to fill this row from a reference.",
}

#: The groups the chooser shows, in order. English source.
GROUP_LABELS: "dict[str, str]" = {
    "coated": "Coated commercial print",
    "uncoated": "Uncoated commercial print",
    "laminated": "Laminated",
    "magazine": "Magazine",
    "newspaper": "Newspaper",
    "metal": "Metal",
}
GROUP_ORDER: "tuple[str, ...]" = tuple(GROUP_LABELS)


# ---------------------------------------------------------------------------
# One reference set
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReferenceSet:
    id: str                      # "FOGRA51"
    label: str                   # English source; display through tr()
    group: str
    blurb: str                   # English source; one sentence for the chooser
    source: str                  # the rights holder, verbatim. REQUIRED
    terms: str                   # the terms they stated, verbatim. REQUIRED
    url: str
    path: Path
    patches: int
    device_space: str            # "CMYK" | "RGB"
    filter: str                  # "M1" | "" when the file does not say
    paper_lab: "tuple[float, float, float] | None"
    is_real_paper: bool
    sha256: str
    #: Whether the bytes on this machine are still the ones ``SOURCE.json``
    #: records. False does NOT hide the set; see :func:`available`.
    verified: bool = True

    @property
    def credit_line(self) -> str:
        """The credit, which is a required part of every place this set is
        shown. Two sentences: who the data belongs to, and that naming it is
        not a certification. Never a tooltip.

        A set whose file no longer matches gets a third sentence and loses the
        claim that it IS the source's data, because that is the claim ChromIQ
        can no longer make about it. See :func:`available`.
        """
        # THE NAME IS TRIMMED ONLY WHERE THE TEMPLATE PUTS A STOP BACK.
        # "Fogra Forschungsinstitut für Medientechnologien e.V." ends in a full
        # stop of its own, so the first template's added one read "e.V..",
        # twice per line, in the sentence Fogra's permission requires. Dropping
        # it there is right, because the sentence supplies its own.
        #
        # It is WRONG anywhere else, and the third sentence went through both
        # wrong shapes before this one. With the name in a possessive it
        # printed "e.V's"; with the name last it printed "e.V.." again from the
        # sentence's own stop; and the German, which puts the name in the
        # middle, lost the abbreviation's period altogether. A rights holder's
        # legal name is not ours to abbreviate differently in a sentence their
        # permission requires, so that sentence takes the name UNTOUCHED and is
        # worded, in every language, so that something always follows it.
        _trimmed = self.source[:-1] if self.source.endswith(".") else self.source
        line = tr("Reference data: {name}, {source}. Naming this set says what "
                  "your measurement was compared against. It is not a "
                  "certification, approval or endorsement by {source}."
                  ).format(name=self.id, source=_trimmed)
        if not self.verified:
            line += " " + tr(
                "ChromIQ cannot present this file as original data from "
                "{source}, because it no longer matches the file that shipped."
            ).format(source=self.source)
        return line

    @property
    def display_label(self) -> str:
        """``Coated commercial print, current (FOGRA51)``: the vocabulary of
        what somebody has in front of them, with the set's name in the row and
        never as the row."""
        return tr("{label} ({name})").format(label=tr(self.label),
                                             name=self.id)


# ---------------------------------------------------------------------------
# Loading, and the credit gate
# ---------------------------------------------------------------------------
_cache: "list[ReferenceSet] | None" = None


def _data_dir() -> Path:
    return resource_path(DATA_DIR)


def reset_cache() -> None:
    """For tests that swap the data folder."""
    global _cache
    _cache = None


def _entry_is_credited(entry: Any) -> bool:
    """A set with no source and no terms is not offered. This is the gate that
    makes the Fogra credit condition structural: a data file added without its
    provenance simply does not appear."""
    return (isinstance(entry, dict)
            and bool(str(entry.get("source") or "").strip())
            and bool(str(entry.get("terms") or "").strip()))


def available() -> "list[ReferenceSet]":
    """Every bundled reference set that is complete, credited and readable.

    A file that is missing, uncredited or malformed is logged and skipped, and
    never silently half-loaded.
    """
    global _cache
    if _cache is not None:
        return _cache
    folder = _data_dir()
    out: "list[ReferenceSet]" = []
    try:
        doc = json.loads((folder / SOURCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("reference sets: %s unreadable (%s); none offered",
                    folder / SOURCE_FILE, exc)
        _cache = out
        return out
    for set_id, entry in sorted((doc.get("sets") or {}).items()):
        if not _entry_is_credited(entry):
            log.warning("reference set %s has no source and terms; not offered "
                        "(data/reference_sets/README.md says why)", set_id)
            continue
        path = folder / str(entry.get("file") or "")
        if not path.is_file():
            log.warning("reference set %s: %s is missing; not offered",
                        set_id, path.name)
            continue
        group = str(entry.get("group") or "")
        if group not in GROUP_LABELS:
            log.warning("reference set %s: unknown group %r; not offered",
                        set_id, group)
            continue
        lab = entry.get("paper_lab")
        paper = (tuple(float(v) for v in lab)
                 if isinstance(lab, (list, tuple)) and len(lab) == 3 else None)
        candidate = ReferenceSet(
            id=set_id,
            label=str(entry.get("label") or set_id),
            group=group,
            blurb=str(entry.get("blurb") or ""),
            source=str(entry["source"]).strip(),
            terms=str(entry["terms"]).strip(),
            url=str(entry.get("url") or ""),
            path=path,
            patches=int(entry.get("patches") or 0),
            device_space=str(entry.get("device_space") or "").upper(),
            filter=str(entry.get("filter") or ""),
            paper_lab=paper,
            is_real_paper=bool(entry.get("is_real_paper", True)),
            sha256=str(entry.get("sha256") or ""),
        )
        # A CHANGED FILE IS QUALIFIED, NOT HIDDEN, and the first version of
        # this got that backwards.
        #
        # It dropped the set, treating a hash mismatch as a breach of Fogra's
        # permission. That reasoning does not hold. Their condition is on
        # DISTRIBUTION, which happened when the bundle was built, and the gate
        # is where it is checked. By the time this runs the file is sitting on
        # a user's disk, where a mismatch means a truncated download, a
        # re-signed bundle, an antivirus rewrite or a sync tool touching line
        # endings. The answer to that is not to make a printing condition
        # vanish with no explanation the user can see.
        #
        # What ChromIQ genuinely cannot do with a changed file is present it as
        # the source's own data, which is the ICC's condition recorded in
        # `data/compliance_sets/README.md` and is the honest shape here too. So
        # the set stays, and `credit_line` says the file no longer matches.
        #
        # The two conditions above are NOT the same event and used to be
        # treated as one: no recorded credit is a packaging bug that can never
        # reach a user, and changed bytes are a condition of the machine in
        # front of you.
        _ok = verify_unmodified(candidate)
        if not _ok:
            log.warning("reference set %s: %s does not match the sha256 in %s; "
                        "still offered, with its credit qualified, because the "
                        "file is on the user's disk and this says nothing about "
                        "how it was distributed", set_id, path.name, SOURCE_FILE)
        out.append(replace(candidate, verified=_ok))
    out.sort(key=lambda s: (GROUP_ORDER.index(s.group), s.id))
    _cache = out
    return out


def by_id(set_id: "str | None") -> "ReferenceSet | None":
    for s in available():
        if s.id == set_id:
            return s
    return None


def grouped() -> "list[tuple[str, list[ReferenceSet]]]":
    """``[(group_id, sets)]`` in the chooser's order, empty groups omitted."""
    out = []
    for g in GROUP_ORDER:
        members = [s for s in available() if s.group == g]
        if members:
            out.append((g, members))
    return out


def verify_unmodified(s: ReferenceSet) -> bool:
    """True when the file on disk is byte-for-byte the one ``SOURCE.json``
    records. Fogra's grant is conditional on unmodified redistribution, so this
    is checkable rather than asserted."""
    if not s.sha256:
        return False
    try:
        return hashlib.sha256(s.path.read_bytes()).hexdigest() == s.sha256
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Reading the aims
# ---------------------------------------------------------------------------
def read_aims(s: ReferenceSet) -> "dict[tuple[float, ...], tuple[float, float, float]]":
    """``{device tuple: (L, a, b)}`` from a CGATS / ISO 28178 file.

    **The data rows are counted, never taken from the header.** Fogra's own
    ``FOGRA43.txt`` declares ``NUMBER_OF_SETS 216`` over a data block of 1,617
    rows and ``NUMBER_OF_FIELDS 11`` over 48 fields (measured 2026-09-10), so a
    reader that trusts the header silently drops seven eighths of the file and
    then reports a confident number computed from the rest. Both descriptor
    spellings are accepted for the same reason: the modern files use
    ``FILE_DESCRIPTOR`` and the older ones ``DESCRIPTOR``.
    """
    try:
        text = s.path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        log.warning("reference set %s unreadable (%s)", s.id, exc)
        return {}
    m = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", text, re.S)
    if not m:
        return {}
    fields = m.group(1).split()
    m = re.search(r"^BEGIN_DATA[ \t]*$\r?\n(.*?)^END_DATA", text, re.S | re.M)
    if not m:
        return {}
    try:
        lab_idx = [fields.index(k) for k in ("LAB_L", "LAB_A", "LAB_B")]
    except ValueError:
        log.warning("reference set %s has no LAB columns", s.id)
        return {}
    dev_idx = [i for i, f in enumerate(fields)
               if f.startswith(("CMYK_", "RGB_", "PC7_"))]
    if not dev_idx:
        return {}
    out: dict = {}
    for line in m.group(1).splitlines():
        cells = line.split()
        if len(cells) < len(fields):
            continue
        try:
            dev = tuple(round(float(cells[i]), 4) for i in dev_idx)
            out[dev] = tuple(float(cells[i]) for i in lab_idx)
        except (ValueError, IndexError):
            continue
    return out


def paper_lab(s: ReferenceSet) -> "tuple[float, float, float] | None":
    """The reference paper's L*a*b*: the patch with every channel at zero.

    Read from the file rather than from ``SOURCE.json`` so that the number
    ChromIQ shows is the number Fogra published, even if the metadata drifts.
    """
    aims = read_aims(s)
    for dev, lab in aims.items():
        if all(abs(v) < 1e-9 for v in dev):
            return lab
    return s.paper_lab


def substrate_de00(s: ReferenceSet,
                   measured_paper_lab: "tuple[float, float, float] | None"
                   ) -> "float | None":
    """ΔE00 between the measured paper white and the reference paper, or None.

    This is the one row a CMYK reference can honestly fill on an RGB sheet: a
    paper's colour is a property of the paper, not of the process that will be
    printed on it, and both numbers are a measurement of bare stock.
    """
    if measured_paper_lab is None or not s.is_real_paper:
        return None
    ref = paper_lab(s)
    if ref is None:
        return None
    from workflow.ti3_analysis import ciede2000
    return float(ciede2000(tuple(measured_paper_lab), tuple(ref)))


# ---------------------------------------------------------------------------
# What a set may judge on a given chart
# ---------------------------------------------------------------------------
def can_fill(row_id: str, s: ReferenceSet, chart_device_space: str,
             chart_built_from_reference: bool = False
             ) -> "tuple[bool, str | None]":
    """``(allowed, refusal reason)`` for one row of the Report limits table.

    The refusal is the point of this function. A partial comparison that
    presents itself as a whole one is exactly the fault the Fogra grant's
    no-endorsement clause exists to prevent, so a row that cannot be filled is
    refused with a reason a reader can act on, never filled with a number
    computed from unrelated inputs.
    """
    pairing = ROW_PAIRING.get(row_id)
    if pairing is None:
        return False, REFUSE_UNKNOWN_ROW
    if pairing == "any":
        if not s.is_real_paper:
            return False, REFUSE_NOT_A_PAPER
        return True, None
    # pairing == "same": the row compares patches, not paper
    if chart_built_from_reference:
        return True, None
    if (s.device_space or "").upper() != (chart_device_space or "").upper():
        return False, REFUSE_CROSS_SPACE
    return False, REFUSE_NEEDS_BUILT_CHART


def refusal_text(reason: "str | None") -> str:
    """The refusal as a sentence, translated. Empty for no refusal."""
    if not reason:
        return ""
    return tr(REFUSAL_REASONS.get(reason, REFUSAL_REASONS[REFUSE_UNKNOWN_ROW]))


def coverage_text(found: int, total: int) -> str:
    """How much of a reference the sheet actually carried. ChromIQ never uses
    part of a set silently."""
    if total <= 0:
        return ""
    if found <= 0:
        return tr("Your sheet has no patch in common with this reference, so "
                  "nothing was compared. Choose a reference that matches how "
                  "the sheet was printed.")
    if found == 1:
        return tr("1 aim colour from this reference was found on your sheet, "
                  "of {total}. The rows below that could not be filled say so."
                  ).format(total=total)
    return tr("{found} aim colours from this reference were found on your "
              "sheet, of {total}. The rows below that could not be filled say "
              "so.").format(found=found, total=total)
