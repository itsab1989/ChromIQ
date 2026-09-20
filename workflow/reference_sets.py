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
REFUSE_SUBSTRATE_UNKNOWN = "substrate_unknown"

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
    # A THIRD ANSWER, BECAUSE "no" AND "we were never told" ARE NOT THE SAME.
    # `REFUSE_NOT_A_PAPER` states a fact about the reference, and ChromIQ can
    # only state it about a set it ships, whose entry in SOURCE.json records
    # it. For a file the user supplied there is no such entry, and saying "this
    # is a colour exchange space" about a real paper would be a false sentence
    # in the place a reader goes to find out why a row is empty.
    REFUSE_SUBSTRATE_UNKNOWN:
        "You supplied this reference, and nothing in the file says whether it "
        "describes a real paper or a colour exchange space. ChromIQ leaves "
        "the paper row empty rather than filling it from a guess.",
}

#: The groups the chooser shows, in order. English source.
GROUP_LABELS: "dict[str, str]" = {
    "coated": "Coated commercial print",
    "uncoated": "Uncoated commercial print",
    "laminated": "Laminated",
    "magazine": "Magazine",
    "newspaper": "Newspaper",
    "metal": "Metal",
    # LAST, AND IT IS NOT A PRINTING CONDITION. Every group above says what
    # somebody is printing on. This one says where the file came from, because
    # for a set ChromIQ does not ship there is nothing else it honestly knows:
    # the user handed over a file, and the printing condition it describes is
    # written in the file's own header in the publisher's words, not in any
    # table here. Putting such a set under "Coated" would be ChromIQ deciding
    # something it was never told.
    "supplied": "Supplied by you",
}
GROUP_ORDER: "tuple[str, ...]" = tuple(GROUP_LABELS)

#: The group a user-supplied set lands in when ChromIQ ships no entry for it.
SUPPLIED_GROUP = "supplied"


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
    #: True, False, or **None for "nobody told ChromIQ"**. The third state is
    #: not tidiness: it exists because a user may supply a file for a set that
    #: ships no entry here, and :func:`can_fill` must then refuse the paper row
    #: without asserting anything about what the file describes.
    is_real_paper: "bool | None"
    sha256: str
    #: Whether the bytes on this machine are still the ones the RECORD for this
    #: set gives. For a bundled set the record is ``SOURCE.json``; for one the
    #: user supplied it is the sha256 taken at import. False does NOT hide the
    #: set; see :func:`available`.
    verified: bool = True

    # ------------------------------------------------------------------
    # Which archive this is, and where it came from
    # ------------------------------------------------------------------
    #: Fogra's own version and publication date for the archive the bundled
    #: file came out of, so the window can say WHICH copy is in force rather
    #: than only that one is. Empty for a set the user supplied, because
    #: ChromIQ was not told and must not invent one.
    archive_version: str = ""
    archive_published: str = ""

    #: **THE LINE BETWEEN WHAT CHROMIQ VOUCHES FOR AND WHAT IT MERELY HOLDS.**
    #: False for the files that ship, whose provenance is recorded in
    #: ``SOURCE.json`` and checked byte for byte. True for a file the user
    #: handed over, about which ChromIQ can honestly say only three things:
    #: when it arrived, what it was called, and what its sha256 was at that
    #: moment. It must never be presented as carrying the first kind of
    #: provenance, which is why :attr:`credit_line` says so in the same breath
    #: as the credit and :func:`bundled` exists for the licence page.
    supplied_by_user: bool = False
    #: ``YYYY-MM-DD`` the user supplied it, and the name the file had then.
    imported: str = ""
    original_filename: str = ""

    #: **WHAT THE FILE SAYS ABOUT ITSELF**, verbatim and unverified: its own
    #: ``FILE_DESCRIPTOR`` and its own ``CREATED``. Empty for a bundled set,
    #: whose version is the ARCHIVE's and is recorded in ``SOURCE.json``.
    #:
    #: These exist because "your copy, added 2026-09-20" answers the wrong
    #: question. Fogra's FOGRA61 is published as a beta today and will be
    #: published again as a release; both call themselves FOGRA61, both are
    #: stored under the same name, and the import date is a fact about the
    #: USER'S ACTION, not about the data. Nothing on screen distinguished the
    #: two, so a verification could be judged against beta aims by somebody who
    #: believed they had the final ones.
    #:
    #: They are facts about a FILE, so :func:`_wearing_the_shipped_metadata`
    #: leaves them alone, and they are printed as a QUOTATION of the file
    #: rather than as anything ChromIQ checked.
    file_descriptor: str = ""
    file_created: str = ""

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
        if self.supplied_by_user:
            # THE CLAIM CHROMIQ CANNOT MAKE ABOUT THIS FILE. Everything above
            # is about the printing condition and stays true: the aims are
            # Fogra's, and naming the set is still not a certification. What
            # changes is provenance. A bundled file's bytes are recorded in
            # SOURCE.json and checked against it, so ChromIQ can say it is the
            # file Fogra published. About a file handed to it on this machine
            # it can say only when it arrived and what it was called, and it
            # says exactly that rather than borrowing the other sentence's
            # authority by staying quiet.
            line += " " + tr(
                "You supplied this file on {date}, as {filename}. ChromIQ "
                "records what it received and does not vouch for where the "
                "file came from."
            ).format(date=self.imported or tr("an unknown date"),
                     filename=self.original_filename or tr("an unnamed file"))
            if not self.verified:
                line += " " + tr(
                    "It has also changed since you supplied it.")
        elif not self.verified:
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
        # A SET THE USER SUPPLIED THAT CHROMIQ SHIPS NOTHING FOR HAS NO
        # LABEL BUT THE ONE IN ITS OWN DESCRIPTOR, and Fogra's `FOGRA55.txt`
        # calls itself exactly "FOGRA55", so the template printed
        # "FOGRA55 (FOGRA55)". Measured challenge round 31 against Fogra's own
        # `Ref_FOGRA55.zip`. There is no vocabulary to lead with here, so the
        # name leads, once.
        label = tr(self.label)
        if not label or label == self.id:
            return self.id
        return tr("{label} ({name})").format(label=label, name=self.id)


# ---------------------------------------------------------------------------
# Loading, and the credit gate
# ---------------------------------------------------------------------------
_cache: "list[ReferenceSet] | None" = None
_bundled_cache: "list[ReferenceSet] | None" = None


def _data_dir() -> Path:
    return resource_path(DATA_DIR)


def reset_cache() -> None:
    """For tests that swap the data folder, and for every install or removal
    of a user's own copy."""
    global _cache, _bundled_cache
    _cache = None
    _bundled_cache = None


def _entry_is_credited(entry: Any) -> bool:
    """A set with no source and no terms is not offered. This is the gate that
    makes the Fogra credit condition structural: a data file added without its
    provenance simply does not appear."""
    return (isinstance(entry, dict)
            and bool(str(entry.get("source") or "").strip())
            and bool(str(entry.get("terms") or "").strip()))


def bundled() -> "list[ReferenceSet]":
    """Every reference set **that ships inside ChromIQ**, complete, credited
    and readable. Nothing the user supplied is in here.

    A file that is missing, uncredited or malformed is logged and skipped, and
    never silently half-loaded.

    **THIS IS THE LIST THE LICENCE PAGE USES**, and that is the whole reason it
    is a function of its own. The page's job is to state, accurately, what
    ChromIQ ships and on whose terms. Folding a file somebody dropped into
    their own folder into that statement would make the page claim provenance
    for a file ChromIQ has never checked against anything but its own import
    record. :func:`available` is the list for everything else.
    """
    global _bundled_cache
    if _bundled_cache is not None:
        return _bundled_cache
    folder = _data_dir()
    out: "list[ReferenceSet]" = []
    try:
        doc = json.loads((folder / SOURCE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("reference sets: %s unreadable (%s); none offered",
                    folder / SOURCE_FILE, exc)
        # NOT CACHED, AND THE DEAD LINE THAT USED TO SIT HERE IS GONE (B8-551).
        # It read `_cache = out`, which assigned a local this function throws
        # away: `bundled()` declares `global _bundled_cache` and not `_cache`.
        # Harmless, but since b7475572 there IS a module-level `_cache`, owned
        # by `available()`, so a reader checking whether an unreadable
        # SOURCE.json could hide a user's own supplied sets had to work out
        # that the statement does nothing before concluding that it cannot.
        # Leaving the result uncached is also the right behaviour on its own
        # terms: an unreadable SOURCE.json is a condition of the disk, and a
        # cached empty list would survive the file becoming readable again.
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
            archive_version=str(entry.get("archive_version") or ""),
            archive_published=str(entry.get("archive_published") or ""),
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
    out.sort(key=_chooser_order)
    _bundled_cache = out
    return out


def _chooser_order(s: ReferenceSet) -> tuple:
    return (GROUP_ORDER.index(s.group), s.id)


def available() -> "list[ReferenceSet]":
    """Every reference set ChromIQ can offer: the ones it ships, with the
    user's own copy preferred **per set** wherever there is one, plus any set
    the user supplied that ChromIQ ships no copy of at all.

    Sebastian, 2026-09-20: *"we could ship the most recent version and allow
    for a way to use newer values if they are released at some point in the
    future without relying on an update to ChromIQ for it."* So a set is a
    place, not a file: ChromIQ's copy stands in it until the user puts theirs
    there, and "Stop using it" empties the place again.

    ``FOGRA61`` is the case that stops this being a mere override mechanism. It
    is still beta in Fogra's archive and ChromIQ ships nothing for it, so it
    can only ever arrive from the user, and a design that could only REPLACE a
    shipped set would never be able to hold it.
    """
    global _cache
    if _cache is not None:
        return _cache
    mine = {s.id: s for s in bundled()}
    for supplied in _user_sets():
        shipped = mine.get(supplied.id)
        mine[supplied.id] = (supplied if shipped is None
                             else _wearing_the_shipped_metadata(supplied,
                                                                shipped))
    out = sorted(mine.values(), key=_chooser_order)
    _cache = out
    return out


def _wearing_the_shipped_metadata(supplied: ReferenceSet,
                                  shipped: ReferenceSet) -> ReferenceSet:
    """A newer file for a set ChromIQ already knows, keeping what ChromIQ knows
    about the CONDITION and nothing about the FILE.

    The split is the point. The label, the group, the one-sentence blurb and
    whether the condition is a real paper describe a printing condition, and a
    2027 revision of FOGRA51 is still coated commercial print: dropping them
    would file the user's own file under "Supplied by you" with a bare code for
    a name, which is worse for them in every way. The provenance fields go the
    other way entirely -- the path, the sha256, the archive version and date,
    and who supplied it are facts about a FILE, and every one of them now
    belongs to the file in front of us.
    """
    return replace(supplied,
                   label=shipped.label,
                   group=shipped.group,
                   blurb=shipped.blurb,
                   is_real_paper=shipped.is_real_paper)


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
# The user's own copies: a newer file, without a newer ChromIQ
# ---------------------------------------------------------------------------
#: The record of what the user supplied, kept in their own folder and
#: **deliberately not** in ``SOURCE.json``.
#:
#: Two records, because there are two different claims and only one of them is
#: ChromIQ's to make. ``SOURCE.json`` says "this is the file Fogra published,
#: here is its sha256, here is the archive it came out of", and a test checks
#: every byte of it on every run. This file says "on this date a person chose
#: this file, it was called that, and this was its sha256 at that moment", which
#: is everything ChromIQ witnessed and nothing more. Writing the second into the
#: first would quietly promote a download nobody checked into a bundled,
#: verified artefact, and the licence page reads the first.
USER_RECORD_FILE = "SUPPLIED.json"

#: How a set is recognised in a file name or a file's own descriptor. Fogra's
#: own spellings across the archive: ``FOGRA51_MW3_Subset``,
#: ``3D-DesignRGB_FOGRA61(beta)``, ``MW7C_Ref_FOGRA55_CMYKOGV``.
_SET_ID_RE = re.compile(r"FOGRA\s*[-_]?\s*(\d{2,3})", re.I)

#: What a supplied file may be called. A ``.zip`` is accepted because that is
#: the shape Fogra publishes: a user who downloads the characterisation data
#: gets an archive, and asking them to unpack it first is a step that exists
#: only for ChromIQ's convenience.
USER_FILE_SUFFIXES = (".txt", ".zip")

#: A ceiling on what is read out of a zip, so a hostile or merely silly archive
#: cannot be unpacked over somebody's disk. Fogra's own archive is 21 files and
#: under 2 MB; the largest single characterisation file in it is ~600 kB.
_ZIP_MAX_MEMBERS = 200
_ZIP_MAX_BYTES = 64 * 1024 * 1024

#: The same ceiling on a single file, and it was missing.
#:
#: The zip route refuses an archive that unpacks past `_ZIP_MAX_BYTES`; the
#: plain-file route read whatever it was given. Measured challenge round 31: a
#: 277 MB `.txt` was accepted, COPIED into the user's preferences folder, and
#: recorded as 8,640,000 patches, and every later `available()` re-hashes all
#: 277 MB of it. The ceiling is the same number because it is the same
#: question, and the largest file in Fogra's own archive is 435 kB.
_FILE_MAX_BYTES = _ZIP_MAX_BYTES


def _fogra(field: str) -> str:
    """Fogra's own name, terms or URL, taken from the file that ships.

    **THERE IS EXACTLY ONE COPY OF THE GRANT IN THIS TREE**, in
    ``fogra/SOURCE.json``, and this reads it rather than repeating it. A second
    copy in Python would be a quotation of somebody's licence that nothing
    keeps in step with the first, and the first is the one the licence page,
    the README and the test suite all check.

    Returns "" when the bundle did not travel, which makes the caller refuse to
    offer an uncredited set. That is the same answer :func:`bundled` gives for
    the same reason.
    """
    for s_ in bundled():
        value = str(getattr(s_, field, "") or "")
        if value:
            return value
    return ""


def user_dir() -> Path:
    """Where the user's own reference files live on this machine."""
    from core.platform_paths import reference_sets_dir

    return reference_sets_dir()


def _user_record_path() -> Path:
    return user_dir() / USER_RECORD_FILE


def user_record() -> "dict[str, dict]":
    """``{set_id: record}`` for every file the user supplied, or ``{}``."""
    try:
        doc = json.loads(_user_record_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sets = doc.get("sets") if isinstance(doc, dict) else None
    return sets if isinstance(sets, dict) else {}


def _write_user_record(sets: "dict[str, dict]") -> None:
    path = _user_record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "_readme": (
            "Reference data files YOU supplied, and what ChromIQ witnessed "
            "when you did. This is not ChromIQ's provenance record for the "
            "files it ships, which is data/reference_sets/fogra/SOURCE.json "
            "inside the application and is checked byte for byte. ChromIQ "
            "does not vouch for anything here; it records it."),
        "sets": sets,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _user_sets() -> "list[ReferenceSet]":
    """Every set the user supplied, as ``ReferenceSet`` objects.

    A record whose file has gone is skipped rather than offered: a chooser row
    that cannot be read is worse than no row, and the record is left alone so
    that the window can still say the file is missing if it ever needs to.
    """
    out: "list[ReferenceSet]" = []
    folder = user_dir()
    for set_id, rec in sorted(user_record().items()):
        if not isinstance(rec, dict):
            continue
        path = folder / str(rec.get("file") or "")
        if not path.is_file():
            log.warning("reference set %s: your own copy %s has gone; "
                        "ChromIQ is using what shipped", set_id, path.name)
            continue
        recorded = str(rec.get("sha256") or "")
        try:
            now = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        # THE CREDIT GATE APPLIES TO THE USER'S FILES TOO, and it has to: it is
        # a condition on the DATA, and the data is the same data. A record that
        # names no rights holder and no terms is not offered, exactly as a
        # bundled file with no `SOURCE.json` entry is not offered. In practice
        # the words come from the bundle, so the only way to reach this is a
        # build whose own provenance file did not travel -- in which case the
        # honest answer is to offer nothing rather than a set with no credit.
        source = str(rec.get("source") or _fogra("source")).strip()
        terms = str(rec.get("terms") or _fogra("terms")).strip()
        if not source or not terms:
            log.warning("your copy of %s has no source and terms recorded; "
                        "not offered (data/reference_sets/README.md says why)",
                        set_id)
            continue
        out.append(ReferenceSet(
            id=set_id,
            label=str(rec.get("label") or set_id),
            group=SUPPLIED_GROUP,
            blurb=str(rec.get("blurb") or ""),
            # THE CREDIT CONDITION FOLLOWS THE DATA, NOT THE BUNDLE. Fogra's
            # grant is a condition on the data, so a Fogra file the user
            # downloaded themselves is credited in exactly the same words as
            # one ChromIQ ships. What differs is provenance, and that is said
            # separately by `supplied_by_user`.
            source=source,
            terms=terms,
            url=str(rec.get("url") or _fogra("url")),
            path=path,
            patches=int(rec.get("patches") or 0),
            device_space=str(rec.get("device_space") or "").upper(),
            filter=str(rec.get("filter") or ""),
            paper_lab=None,
            is_real_paper=None,
            sha256=recorded,
            verified=bool(recorded) and now == recorded,
            supplied_by_user=True,
            imported=str(rec.get("imported") or ""),
            original_filename=str(rec.get("original_filename") or ""),
            file_descriptor=str(rec.get("file_descriptor") or ""),
            file_created=str(rec.get("file_created") or ""),
        ))
    return out


# ---------------------------------------------------------------------------
# Reading a file somebody handed us
# ---------------------------------------------------------------------------
def set_id_in(text: str) -> str:
    """``"FOGRA51"`` for any of Fogra's spellings of it, or ``""``."""
    m = _SET_ID_RE.search(text or "")
    return f"FOGRA{m.group(1)}" if m else ""


def inspect_file(path: Path) -> dict:
    """:func:`inspect_bytes` for a file on disk."""
    path = Path(path)
    return inspect_bytes(path.name, path.read_bytes())


def inspect_bytes(name: str, raw: bytes) -> dict:
    """What a candidate file is, or a :class:`ValueError` saying why not.

    **The refusal is the useful half.** A file that is silently installed and
    then turns out to hold nothing readable becomes a set that shows no aims
    and explains nothing, and the user has no way back to the moment they could
    have picked a different file. Everything this can check, it checks here,
    at the door.

    It takes BYTES rather than a path because the commonest way in is a member
    of a zip, and writing each member out to be inspected would mean a refused
    file had already been on disk.
    """
    # THE PROJECT'S OWN DECODER, AND THE NEWLINES IT TRANSLATES ARE THE POINT.
    # This path has BYTES, straight out of a zip member, so nothing has done
    # what text mode does. Every Fogra file measured on 2026-09-20 is CRLF, the
    # bundled FOGRA51 subset included, so untranslated the data block's own
    # `^BEGIN_DATA$` never matches and EVERY file a user supplies is refused as
    # "not a reference data file". `core.text_io` also names the codec rather
    # than assuming UTF-8 and papering over the rest with replacement
    # characters, which `tests/test_proc_text.py` bans by name.
    from core.text_io import decode_bytes

    text = decode_bytes(raw, what=name or "that file")
    fields, rows = _data_block(text)
    if not fields or not rows:
        raise ValueError(tr(
            "That file is not a reference data file. ChromIQ reads the CGATS "
            "and ISO 28178 files Fogra publishes, which hold a BEGIN_DATA "
            "block of aim colours."))
    if not all(k in fields for k in ("LAB_L", "LAB_A", "LAB_B")):
        raise ValueError(tr(
            "That file holds no CIELAB columns, so there are no aim colours "
            "in it for ChromIQ to compare a measurement against."))
    dev = [f for f in fields if "_" in f and not f.startswith("LAB_")
           and f.split("_", 1)[0] in _DEVICE_PREFIXES]
    if not dev:
        raise ValueError(tr(
            "That file holds no device columns, so ChromIQ cannot tell which "
            "printing device values its aim colours belong to."))
    descriptor = _header_value(text, "FILE_DESCRIPTOR") or \
        _header_value(text, "DESCRIPTOR")
    set_id = set_id_in(descriptor) or set_id_in(name)
    if not set_id:
        raise ValueError(tr(
            "ChromIQ cannot tell which reference set that file is. It looks "
            "for a name like FOGRA51 in the file's own description and in the "
            "file name, and found neither."))
    return {
        "set_id": set_id,
        "descriptor": descriptor,
        # the file's own name for itself, kept apart from `descriptor` so that
        # `_install_one` can put a CONDITION label in one field and a FILE fact
        # in the other without either being derived from the other later.
        "file_descriptor": descriptor,
        "patches": len(rows),
        "device_space": dev[0].split("_", 1)[0].upper(),
        "filter": _header_value(text, "FILTER"),
        "print_conditions": _header_value(text, "PRINT_CONDITIONS"),
        "created": _header_value(text, "CREATED"),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def install_user_file(src: "str | Path") -> "list[str]":
    """Copy the user's own reference file into ChromIQ's folder. Returns the
    set ids now in force from their copy, in the order they were found.

    It is COPIED, for the reason the ISO values are: the file a person has just
    downloaded is in Downloads, and a folder they tidy is not a place to keep
    something the app depends on.

    A ``.zip`` installs every member ChromIQ can read and says so. It does not
    fail on the ones it cannot -- Fogra's own archive carries a readme beside
    the data -- but it does fail when it could read NONE of them, because an
    archive that installs nothing and reports success is the shape of a feature
    that looks like it worked.
    """
    src = Path(src)
    if src.suffix.lower() == ".zip":
        return _install_zip(src)
    # THE SAME CEILING THE ZIP ROUTE HAS, ASKED BEFORE THE BYTES ARE READ.
    # `inspect_file` reads the whole file into memory and `_install_one` then
    # copies it, so a file refused after the read has already cost both.
    try:
        size = src.stat().st_size
    except OSError:
        size = 0
    if size > _FILE_MAX_BYTES:
        raise ValueError(tr(
            "That file is {size} MB, which is far larger than a set of "
            "reference data. ChromIQ has not read it."
        ).format(size=size // (1024 * 1024)))
    info = inspect_file(src)
    return [_install_one(src.name, src.read_bytes(), info)]


def _install_one(original_name: str, data: bytes, info: dict) -> str:
    from datetime import date

    set_id = info["set_id"]
    folder = user_dir()
    folder.mkdir(parents=True, exist_ok=True)
    # THE STORED NAME IS CHROMIQ'S, NOT THE USER'S. A file called
    # `../../something.txt` inside a zip, or one called `SUPPLIED.json`, must
    # not decide where anything lands or what it overwrites. The set id is
    # matched out of `_SET_ID_RE` and can only ever be FOGRA plus digits.
    dst = folder / f"{set_id}.txt"
    dst.write_bytes(data)
    rec = user_record()
    rec[set_id] = {
        "file": dst.name,
        "original_filename": Path(original_name).name,
        "imported": date.today().isoformat(),
        "sha256": info["sha256"],
        "patches": info["patches"],
        "device_space": info["device_space"],
        "filter": info.get("filter", ""),
        "label": info.get("descriptor") or set_id,
        "blurb": info.get("print_conditions", ""),
        # WHAT THE FILE SAYS ABOUT ITSELF, kept whether or not `label` is
        # later replaced by the shipped one. `created` was already being
        # returned by `inspect_bytes` and thrown away here, which is why the
        # window could say only when a file arrived and never which file it is.
        "file_descriptor": info.get("file_descriptor") or info.get("descriptor", ""),
        "file_created": info.get("created", ""),
        "source": _fogra("source"),
        "terms": _fogra("terms"),
        "url": _fogra("url"),
        "supplied_by_user": True,
    }
    _write_user_record(rec)
    reset_cache()
    return set_id


def _install_zip(src: Path) -> "list[str]":
    import zipfile

    installed: "list[str]" = []
    refused: "list[str]" = []
    try:
        with zipfile.ZipFile(src) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            if len(members) > _ZIP_MAX_MEMBERS:
                raise ValueError(tr(
                    "That archive holds {count} files, which is far more than "
                    "a set of reference data. ChromIQ has not opened it."
                ).format(count=len(members)))
            total = sum(m.file_size for m in members)
            if total > _ZIP_MAX_BYTES:
                raise ValueError(tr(
                    "That archive unpacks to more than ChromIQ will read from "
                    "one file. ChromIQ has not opened it."))
            for m in members:
                name = Path(m.filename).name
                if not name.lower().endswith(".txt"):
                    continue
                # A MEMBER CHROMIQ CANNOT UNPACK IS A REFUSAL, NOT A CRASH.
                # `zf.read` raises `RuntimeError` for an encrypted member and
                # `NotImplementedError` for a compression method it does not
                # have, and neither is an `OSError` or a `ValueError`, so both
                # went straight past the caller's handler. Measured challenge
                # round 31 on a `zip -P secret` archive and on one whose
                # method field was rewritten: two uncaught exceptions out of
                # the "Use a newer file…" button.
                try:
                    data = zf.read(m)
                except (RuntimeError, NotImplementedError) as exc:
                    refused.append(f"{name}: {exc}")
                    continue
                try:
                    info = inspect_bytes(name, data)
                except ValueError as exc:
                    refused.append(f"{name}: {exc}")
                    continue
                # ONE FILE PER SET, AND FOGRA'S OWN ARCHIVE IS WHY.
                # `FOGRA1_38.zip` holds `FOGRA11L.txt` (the full set) AND
                # `FOGRA11S.txt` (the subset); both name FOGRA11, both were
                # stored as `FOGRA11.txt`, and the second silently overwrote
                # the first. Sixteen of its sets are doubled that way, so the
                # confirmation said "your copies of these 45 sets" over 29
                # files and printed sixteen names twice. Measured challenge
                # round 31. The first member found for a set wins and is named
                # in the record; a later one is refused and SAYS which file it
                # lost to, rather than replacing it without a word.
                if info["set_id"] in installed:
                    refused.append(tr(
                        "{name}: this archive already gave ChromIQ a file for "
                        "{set_id}, so this one was not used."
                    ).format(name=name, set_id=info["set_id"]))
                    continue
                installed.append(_install_one(name, data, info))
    except zipfile.BadZipFile as exc:
        raise ValueError(tr("That file is not a readable archive: {error}")
                         .format(error=exc)) from exc
    if not installed:
        detail = refused[0] if refused else tr(
            "It holds no reference data file ChromIQ can read.")
        raise ValueError(tr("Nothing in that archive could be used. {detail}")
                         .format(detail=detail))
    return installed


def forget_user_set(set_id: str) -> bool:
    """Drop the user's own copy of one set. True when something was removed.

    What it goes back to is whatever ChromIQ ships for that set, and for a set
    ChromIQ ships nothing for, to the set not being offered at all. Nothing the
    user gave us is kept behind their back.
    """
    rec = user_record()
    entry = rec.pop(set_id, None)
    if entry is None:
        return False
    try:
        (user_dir() / str(entry.get("file") or "")).unlink(missing_ok=True)
    except OSError as exc:
        log.warning("could not remove your copy of %s: %s", set_id, exc)
    _write_user_record(rec)
    reset_cache()
    return True


def any_user_copy() -> bool:
    """True when there is at least one of the user's own files to remove."""
    return bool(_user_sets())


def in_force_line(s: ReferenceSet) -> str:
    """The sentence saying WHICH copy of one set is in force.

    **ONE IMPLEMENTATION, BECAUSE THERE USED TO BE TWO AND ONLY ONE OF THEM WAS
    ON SCREEN.** This built the sentences and nothing but a test ever called
    it; the Reference values window built the same three sentences again,
    inline. A guard on the function therefore proved nothing about the window,
    which is this project's own recorded way for a guard to lie.
    """
    if s.supplied_by_user:
        return tr("{name}: your copy, added {date}").format(
            name=s.id, date=s.imported or tr("an unknown date"))
    if s.archive_version and s.archive_published:
        return tr("{name}: ChromIQ's copy, archive {version} of {date}"
                  ).format(name=s.id, version=s.archive_version,
                           date=s.archive_published)
    return tr("{name}: ChromIQ's copy").format(name=s.id)


def what_the_file_says(s: ReferenceSet) -> str:
    """What a file the USER supplied says about ITSELF, or "" for a set that
    ships. A second line under :func:`in_force_line`, never folded into it.

    **BECAUSE "added 2026-09-20" ANSWERS THE WRONG QUESTION.** Sebastian asked
    for the copy in force to be named with its version and its date. For a
    bundled set that is the archive's, out of ``SOURCE.json``. For the user's,
    the only date in the line was the date of their own ACTION. Fogra's FOGRA61
    is published as a beta today and will be published again as a release; both
    call themselves FOGRA61, both are stored as ``FOGRA61.txt``, both replace
    the same record, and nothing on screen said which of them the numbers came
    from, so a verification could be judged against beta aims by somebody who
    believed they had the final ones.

    **AND IT IS A SEPARATE LINE FOR A LAYOUT REASON AS WELL AS AN HONESTY
    ONE.** Folded into the first sentence it made a line of 108 characters that
    wraps at any width this window has, and a wrapped row in this layout paints
    its second line across the row beneath it. Measured on screen, challenge
    round 31, in both languages. Two short lines each fit on one.

    It claims nothing. ChromIQ did not check this and does not say it did; it
    quotes the header, and a file whose header says neither gets a sentence
    saying exactly that rather than an empty quotation or an invented version.
    """
    if not s.supplied_by_user:
        return ""
    if s.file_descriptor and s.file_created:
        return tr('It calls itself "{descriptor}" and is dated {created}.'
                  ).format(descriptor=s.file_descriptor, created=s.file_created)
    if s.file_descriptor:
        return tr('It calls itself "{descriptor}" and carries no date of its '
                  'own.').format(descriptor=s.file_descriptor)
    if s.file_created:
        return tr("It is dated {created} and carries no name of its own."
                  ).format(created=s.file_created)
    return tr("The file does not say which version of {name} it is."
              ).format(name=s.id)


def in_window_order(sets: "list[ReferenceSet]") -> "list[ReferenceSet]":
    """The order the Reference values window lists sets in: by set NUMBER.

    `available()` orders by printing-condition group and then by id, which is
    right in a chooser, where the groups are labelled and carry the meaning.
    The values window shows no headings: it is a list of which copy of each set
    is in force. Photographed with Fogra's whole archive installed, that order
    read FOGRA39, 51, 47, 52, 56, 57, 45, 46, 42, 48, 60, 40, 41, which is not
    disorder but cannot be told from it, and somebody looking for the FOGRA61
    they have just added has to read all 23 lines (B8-554).

    It lives HERE rather than in the window because `in_force_lines` and the
    window must not be able to disagree: sorting in the window alone broke the
    guard that exists to keep them one implementation, which is exactly the
    coupling that guard was written for (B8-544).

    By the number and not the string, so a FOGRA9 would sort before a FOGRA60.
    """
    def _key(s: ReferenceSet) -> tuple:
        digits = "".join(c for c in s.id if c.isdigit())
        return (int(digits) if digits else 0, s.id)

    return sorted(sets, key=_key)


def in_force_lines() -> "list[str]":
    """One sentence per set saying WHICH copy is in force, in WINDOW order.

    The window's whole reason for existing beyond three buttons: a control can
    offer an action, and only a sentence can tell somebody what is true now.

    In `in_window_order`, not `available()`'s, and that is load-bearing: the
    window lists by set number and these sentences are what it lists. Sorting
    in the window alone put them out of step and reddened the guard that keeps
    the two one implementation, which is the fault that guard was written for.
    """
    return [in_force_line(s) for s in in_window_order(available())]


def in_force_report() -> "list[tuple[str, str]]":
    """``[(line, what the file says)]`` in WINDOW order, the second empty for
    a set that ships. The window's own source of truth."""
    return [(in_force_line(s), what_the_file_says(s))
            for s in in_window_order(available())]



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
    from core.text_io import read_text

    try:
        text = read_text(s.path, lenient=True)
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("reference set %s unreadable (%s)", s.id, exc)
        return {}
    fields, rows = _data_block(text)
    if not fields or not rows:
        return {}
    try:
        lab_idx = [fields.index(k) for k in ("LAB_L", "LAB_A", "LAB_B")]
    except ValueError:
        log.warning("reference set %s has no LAB columns", s.id)
        return {}
    dev_idx = _device_columns(fields)
    if not dev_idx:
        return {}
    out: dict = {}
    for cells in rows:
        if len(cells) < len(fields):
            continue
        try:
            dev = tuple(round(float(cells[i]), 4) for i in dev_idx)
            out[dev] = tuple(float(cells[i]) for i in lab_idx)
        except (ValueError, IndexError):
            continue
    return out


#: The device-column prefixes ChromIQ understands in a CGATS reference file.
#: ``nCLR`` is how the seven-colour sets spell theirs; ``RGB`` is how the
#: textile and 3D-DesignRGB exchange spaces spell theirs.
_DEVICE_PREFIXES = ("CMYK", "RGB", "PC7", "7CLR", "nCLR", "CMY")


def _device_columns(fields: "list[str]") -> "list[int]":
    return [i for i, f in enumerate(fields)
            if "_" in f and f.split("_", 1)[0].upper()
            in tuple(x.upper() for x in _DEVICE_PREFIXES)]


def _data_block(text: str) -> "tuple[list[str], list[list[str]]]":
    """``(field names, data rows)`` from a CGATS / ISO 28178 file.

    **The rows are counted, never taken from the header**, and the reason is
    measured rather than defensive: Fogra's own ``FOGRA43.txt`` declares
    ``NUMBER_OF_SETS 216`` over a data block of 1,617 rows and
    ``NUMBER_OF_FIELDS 11`` over 48 fields (2026-09-10). A reader that believes
    the header drops seven eighths of the file and then reports a confident
    number computed from the rest.
    """
    m = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", text, re.S)
    if not m:
        return [], []
    fields = m.group(1).split()
    m = re.search(r"^BEGIN_DATA[ \t]*$\r?\n(.*?)^END_DATA", text, re.S | re.M)
    if not m:
        return fields, []
    rows = [line.split() for line in m.group(1).splitlines() if line.split()]
    return fields, rows


def _header_value(text: str, keyword: str) -> str:
    """A CGATS header line's quoted value, or "" when it is not there."""
    m = re.search(rf"^{re.escape(keyword)}[ \t]+\"(.*?)\"\s*$",
                  text, re.M | re.S)
    return m.group(1).strip() if m else ""


def paper_lab(s: ReferenceSet) -> "tuple[float, float, float] | None":
    """The reference paper's L*a*b*: the patch with no ink on it.

    Read from the file rather than from ``SOURCE.json`` so that the number
    ChromIQ shows is the number Fogra published, even if the metadata drifts.

    **WHICH PATCH THAT IS DEPENDS ON THE SPACE, and every bundled set being
    CMYK hid it.** In a subtractive space no ink is every channel at zero. In
    an additive one it is every channel at its MAXIMUM, and zero is the black
    patch: Fogra publishes at least two RGB exchange sets (FOGRA58 textile and
    the FOGRA61 beta, ``3D-DesignRGB``), and either of them can now arrive as a
    file the user supplies. Reading zero there would have handed back
    ``L* 11`` as a paper white and every substrate figure computed from it
    would have been nonsense with no symptom but a large number.
    """
    aims = read_aims(s)
    if not aims:
        return s.paper_lab
    if (s.device_space or "").upper().startswith("RGB"):
        # the patch with every channel at ITS OWN column maximum
        top = tuple(max(dev[i] for dev in aims) for i in range(len(
            next(iter(aims)))))
        return aims.get(top, s.paper_lab)
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
        # THREE ANSWERS, NOT TWO. See REFUSE_SUBSTRATE_UNKNOWN: "this is an
        # exchange space" is a statement about the reference, and ChromIQ can
        # make it only about a set whose entry in SOURCE.json says so.
        if s.is_real_paper is None:
            return False, REFUSE_SUBSTRATE_UNKNOWN
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
