"""What ChromIQ ships that somebody else wrote, and on what terms.

#182 F3. This module exists because a licence that nobody can read is not a
credit. Eleven Fogra characterisation files ship inside the application, and
Fogra's grant is conditional: the data must travel unmodified **and Fogra must
be identified as the source**. Until this page existed the only statements of
that lived in `data/reference_sets/LICENSE` and `THIRD-PARTY-NOTICES.md`, and
`grep -rn "Fogra" ui/` returned nothing at all: a user could not reach either
from inside the app.

**Nothing here restates a licence.** Every line is read from the file that
actually ships, so the page cannot drift from the bundle:

* the reference-data credits come from `workflow.reference_sets`, whose
  `SOURCE.json` gate already refuses a data file with no source and no terms;
* everything else comes from `THIRD-PARTY-NOTICES.md`, which has its own test
  (`test_every_bundled_asset_says_on_what_terms_it_is_here.py`) keeping it
  honest about what is in the tree.

The licence TEXTS stay in the language their owners wrote them in. A translated
quotation of a grant is not that grant. The page's own sentences are translated
as usual.
"""
from __future__ import annotations

from pathlib import Path

from core.logger import get_logger
from core.resource_path import resource_path

log = get_logger(__name__)

#: The two files that say what ChromIQ's own licence is and what it ships.
#: They live at the project root, and `ChromIQ.spec` bundles them, or this page
#: would be empty in every build a user actually installs.
LICENCE_FILE = "LICENSE"
NOTICES_FILE = "THIRD-PARTY-NOTICES.md"


def _read(name: str) -> str:
    try:
        return resource_path(name).read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("licence file %s could not be read: %s", name, exc)
        return ""


def own_licence_text() -> str:
    """ChromIQ's own licence, verbatim, or "" when it did not travel."""
    return _read(LICENCE_FILE)


#: Which sections of `THIRD-PARTY-NOTICES.md` belong in the PRODUCT, and which
#: are the project's own record. Every heading in that file must be in exactly
#: one of these, and a test says so, because a section added later would
#: otherwise arrive in front of users with nobody deciding that it should.
#:
#: THE FILE IS TWO DOCUMENTS WEARING ONE NAME. Most of it is a notice: who owns
#: a bundled file and on what terms, which is what a user is entitled to read
#: and what the Fogra grant requires be readable. The rest is an internal audit
#: record: a past non-compliance and its remedy, a list of obligations still
#: open, a legal argument about GPLv3 aggregation, a contributor's private
#: message quoted with its date, and notes about which decisions were whose.
#:
#: Shipping the first is the point. Shipping the second was an accident of
#: rendering the whole file, found by an adversarial round reading 23,690
#: characters back off the page, and it is not a decision this code should make
#: on anybody's behalf. The file itself is unchanged and still ships inside the
#: bundle; only what the WINDOW renders is chosen here.
NOTICE_SECTIONS: "tuple[str, ...]" = (
    "The rule",
    "Colour profiles",
    "Fonts",
    "Vendored JavaScript",
    "Sounds",
    "Test image",
    "Scanner target recognition files",
    "Argyll-derived helpers",
    "ChromIQ's own",
)

#: The project's own record, and why each is not in the product.
RECORD_SECTIONS: "dict[str, str]" = {
    "A word on GPLv3 and aggregation":
        "a legal argument about our own licensing, not a notice about "
        "anybody's file",
    "The Adobe profile (removed)":
        "the history of a file that no longer ships, including a statement "
        "that we were once not compliant",
    "Still open":
        "obligations this project has not met yet. A licence page that "
        "publishes its own open items in the product is a different document "
        "from one that names rights holders, and that is not this code's "
        "decision to make",
}


def _section_name(heading: str) -> str:
    """The part of a `## …` heading before its file path, trimmed."""
    return heading.lstrip("#").split("\u2014")[0].strip()


def notices_markdown() -> str:
    """The NOTICE half of `THIRD-PARTY-NOTICES.md`: who owns what ChromIQ
    ships and on what terms, and nothing about the project's own record.

    Returns "" when the file did not travel with the build.
    """
    raw = _read(NOTICES_FILE)
    if not raw:
        return raw
    out: "list[str]" = []
    # THE INTRO IS NOT A NOTICE EITHER. It opens on the story of a file that no
    # longer ships and the sentence "We were not compliant", which belongs in
    # the project's record and not on a page a user opens to find out who owns
    # the fonts. The page writes its own lead; rendering starts at the first
    # section heading.
    keep = False
    for line in raw.splitlines(keepends=True):
        if line.startswith("## "):
            keep = _section_name(line) in NOTICE_SECTIONS
        if keep:
            out.append(line)
    return "".join(out)


def reference_data_credits() -> "list[str]":
    """One credit line per bundled reference set, in the order they are offered.

    THIS IS THE CONDITION, NOT A COURTESY. `ReferenceSet.credit_line` names the
    rights holder and says in the same breath that naming a set is not a
    certification, because the grant requires both. An empty list means no
    reference data ships, which is its own honest answer.
    """
    try:
        from workflow.reference_sets import available
        return [s.credit_line for s in available()]
    except Exception as exc:            # noqa: BLE001 — a page, not a workflow
        log.warning("reference-set credits could not be read: %s", exc)
        return []


def reference_data_sources() -> "list[str]":
    """The rights holders behind the bundled reference data, deduplicated and
    in the order they first appear. Used where one name is wanted rather than
    eleven sentences."""
    out: "list[str]" = []
    try:
        from workflow.reference_sets import available
        for s in available():
            if s.source and s.source not in out:
                out.append(s.source)
    except Exception as exc:            # noqa: BLE001
        log.warning("reference-set sources could not be read: %s", exc)
    return out


def reference_data_terms() -> "list[tuple[str, str]]":
    """``(source, terms)`` for each distinct rights holder, verbatim in their
    own words. One entry per holder, not per file: eleven copies of the same
    paragraph is not a licence page, it is a wall."""
    seen: "dict[str, str]" = {}
    try:
        from workflow.reference_sets import available
        for s in available():
            if s.source and s.source not in seen:
                seen[s.source] = s.terms
    except Exception as exc:            # noqa: BLE001
        log.warning("reference-set terms could not be read: %s", exc)
    return list(seen.items())


def bundled_licence_files() -> "list[Path]":
    """Licence files that travel inside the bundle and can be revealed.

    Only the ones that are actually there: a Reveal button pointing at a file
    the build did not ship is worse than no button.
    """
    out: "list[Path]" = []
    for name in (LICENCE_FILE, NOTICES_FILE,
                 "assets/fonts/OFL.txt",
                 "data/reference_sets/LICENSE",
                 "data/compliance_sets/LICENSE"):
        p = resource_path(name)
        try:
            if p.is_file():
                out.append(p)
        except OSError:
            continue
    return out
