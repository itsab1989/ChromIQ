"""The folder guide and the Dictionary must know what the report work added.

Knut, issue #182, 2026-09-20: *"The changes in measurement report tool also
has changes in files and folders used (FOGRA, metrics, limits, reference
files, etc.), which must be added to the 'Where are my files?' help card, for
both the structure overview and the files used per tool or function sections.
The new file created for charts in verification runs must also be added … The
'Dictionary and terminology' help card needs to be updated with all the new
terms used in the measurement report, for the verification and standards, the
FOGRA related tools."*

**EVERY PATH BELOW IS READ OUT OF THE CODE THAT CREATES IT**, never typed into
this file. A guide that is checked against a hand-written list drifts the
moment the code renames something, and says nothing about whether it was ever
right. `core.platform_paths`, `workflow.compliance_sets`,
`workflow.reference_sets` and `workflow.control_strip` are the four modules
that own these names, so they are the four this test asks.

The Dictionary half is narrower on purpose. A test that demanded an entry for
every string in the report window would be a chore that gets suppressed; what
it pins instead is the vocabulary a reader CANNOT work the report out without:
the five verdict words, the two words for "the numbers" and "the aims", and
the fact that every headword actually explains something.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


def _guide_text() -> str:
    """Everything the card and the project's own text file put on a page."""
    from ui.file_guide import (_features, _folders, _rows, file_guide_body,
                               tree_rows)
    parts = [file_guide_body()]
    parts += [f"{a} {b} {c}" for a, b, c in _features()]
    parts += [f"{a} {b}" for a, b in _folders()]
    parts += [f"{name} {meaning}" for _drawn, name, meaning in tree_rows()]
    for _title, rows in _rows():
        parts += [f"{f} {folder} {desc} {origin}" for f, folder, desc, origin in rows]
    return " ".join(parts)


def _tree_text() -> str:
    """The structure overview ONLY, which Knut asked for by name."""
    from ui.file_guide import tree_rows
    return " ".join(f"{name} {meaning}" for _d, name, meaning in tree_rows())


def _feature_text() -> str:
    """The per-tool section ONLY, the other half of the same request."""
    from ui.file_guide import _features
    return " ".join(f"{a} {b} {c}" for a, b, c in _features())


# ------------------------------------------------- the structure overview
def test_the_structure_overview_names_the_app_level_folders():
    """`compliance/` and `reference_sets/` live outside every project.

    Names taken from `core.platform_paths`, which is what creates them.
    """
    from core.platform_paths import compliance_dir, reference_sets_dir

    tree = _tree_text()
    for folder in (compliance_dir().name, reference_sets_dir().name):
        assert f"{folder}/" in tree, (
            f"the structure overview does not draw {folder}/, so a user has "
            f"no way to find the file they are told to put there")


def test_the_structure_overview_names_the_files_inside_them():
    from workflow import compliance_sets as CS
    from workflow import reference_sets as RS

    tree = _tree_text()
    assert CS.ISO_USER_FILE in tree, (
        f"the file a licence holder supplies ({CS.ISO_USER_FILE}) is not in "
        f"the diagram")
    assert RS.USER_RECORD_FILE in tree, (
        f"the record of every supplied reference file "
        f"({RS.USER_RECORD_FILE}) is not in the diagram")


def test_the_structure_overview_draws_the_report_archive():
    """`verifications/<date>/reports/old/` — where a report goes before a
    run's limits are unlocked and its reports recalculated."""
    from ui.file_guide import tree_rows

    rows = list(tree_rows())
    depths = [len(d) // 3 for d, _n, _m in rows]
    seen = False
    for i, (_drawn, name, _meaning) in enumerate(rows):
        if name == "reports/" and depths[i] == 5:
            seen = any(rows[j][1] == "old/" and depths[j] == 6
                       for j in range(i + 1, len(rows)))
    assert seen, (
        "a dated check's reports/ folder has no old/ under it in the "
        "diagram, so the archive-then-recalculate rule is invisible")


# --------------------------------------------------- the per-tool section
def test_the_per_tool_section_covers_the_report_and_its_two_windows():
    text = _feature_text()
    for door in ("Measurement report", "Report limits", "Reference values"):
        assert door in text, (
            f"the per-tool section names no entry for {door!r}, so its files "
            f"are not accounted for anywhere")


def test_the_per_tool_section_names_the_files_those_windows_write():
    from core.platform_paths import compliance_dir, reference_sets_dir
    from workflow import compliance_sets as CS
    from workflow import reference_sets as RS

    text = _feature_text()
    assert f"{compliance_dir().name}/{CS.ISO_USER_FILE}" in text
    assert f"{reference_sets_dir().name}/" in text
    assert RS.USER_RECORD_FILE in text


# ------------------------- the file a verification chart writes and nothing
# ------------------------- else does
def test_the_guide_names_the_control_strip_declaration():
    """Knut's *"new file created for charts in verification runs"*.

    `workflow.control_strip` writes it beside a verification chart and beside
    nothing else, and it is what lets a report fill the three control-strip
    rows instead of marking them N-A.
    """
    from workflow.measurement_report import CONTROL_STRIP_SIDECAR

    text = _guide_text()
    assert CONTROL_STRIP_SIDECAR in text, (
        f"the guide never mentions {CONTROL_STRIP_SIDECAR}, the one file a "
        f"verification chart writes that a profiling chart does not")
    assert CONTROL_STRIP_SIDECAR in _feature_text(), (
        "it is not in the per-tool section either, so nothing says which "
        "action creates it")


def test_the_guide_names_the_colorimetric_reference_and_the_print_record():
    """The two other files a verification sheet's report reads.

    Both stems come from `workflow.verification_print`, so a rename there
    fails this rather than silently ageing the card.
    """
    from pathlib import Path

    from workflow.verification_print import (colorimetric_reference_for,
                                             print_record_path)

    ref = colorimetric_reference_for(Path("STEM.ti2")).name.replace("STEM", "")
    rec = print_record_path(Path("STEM.ti2")).name.replace("STEM", "")
    text = _guide_text()
    assert ref in text, f"the guide never mentions the {ref} reference file"
    assert rec in text, f"the guide never mentions the {rec} print record"


# ------------------------------------------------------------ the Dictionary
def _glossary():
    from ui.dialogs.welcome_dialog import GLOSSARY
    return list(GLOSSARY)


def test_the_dictionary_defines_every_verdict_word_in_one_place():
    """The five words a reader meets in the Report Results table.

    Taken from `workflow.compliance_sets`, so retiring or adding one fails
    here rather than leaving the card describing a word the app no longer
    prints (or missing one it started printing).
    """
    from workflow import compliance_sets as CS

    words = [CS.PASS, CS.FAIL, CS.COND, CS.INFO, CS.N_A]
    # THE BODY, NOT THE HEADWORD. A headword that merely LISTS the five words
    # explains none of them, and matching on "headword plus body" let exactly
    # that pass: the mutation that replaced "COND" with "CONDITIONAL" in the
    # explanation left the list in the title and the check stayed green.
    # WHOLE WORDS. "COND" is a prefix of "CONDITIONAL", so a substring test
    # reported an entry that had stopped using the word the app prints.
    import re

    def says(body: str, word: str) -> bool:
        return re.search(rf"(?<![A-Za-z-]){re.escape(word)}(?![A-Za-z])",
                         body) is not None

    entry = next((b for _t, b in _glossary()
                  if all(says(b, w) for w in words)), None)
    assert entry is not None, (
        f"no Dictionary entry EXPLAINS all of {words} in its body; a reader "
        "who meets one of them in a report has nowhere to look it up")


@pytest.mark.parametrize("term", [
    "Measurement Report", "Limit set", "Report type", "Reference set",
    # K31: "Bound" and "Locked" left with the run lock; the idea that
    # replaces them has its own headword.
    "Characterisation data", "Aim values", "Graded", "A report's limit set",
    "Control strip", "Grey ramp", "Cube corners", "ISO 12647",
    "FOGRA", "Report limits", "Reference values", "Overall",
])
def test_the_dictionary_has_a_headword_for(term):
    """One entry per idea the Measurement Report puts in front of a user.

    Matched on the START of a headword rather than on equality, because the
    card spells several of them with a parenthetical gloss.
    """
    terms = [t for t, _b in _glossary()]
    assert any(t.lower().startswith(term.lower()) or f"{term.lower()} " in
               t.lower() or term.lower() in t.lower() for t in terms), (
        f"the Dictionary has no entry for {term!r}")


def test_no_dictionary_entry_is_a_stub_or_a_duplicate():
    entries = _glossary()
    terms = [t for t, _b in entries]
    dupes = sorted({t for t in terms if terms.count(t) > 1})
    assert not dupes, f"duplicate headwords: {dupes}"
    thin = [t for t, b in entries if len(b) < 60]
    assert not thin, (
        "these entries are too short to explain anything, which is worse "
        f"than having none: {thin}")


def test_the_new_entries_were_appended_and_did_not_displace_the_first_eight():
    """`test_help_card_printing.test_the_glossary_prints_its_terms` asserts on
    ``GLOSSARY[:8]`` in SOURCE order, and the card sorts alphabetically at
    render time, so a new term belongs at the END of the list and nowhere
    else. This says so out loud, where the next person adding one will see it.
    """
    first_eight = [t for t, _b in _glossary()[:8]]
    assert first_eight[0] == ".cht file", (
        "the head of GLOSSARY moved; a sibling test pins GLOSSARY[:8] by "
        "position, so inserting at the front silently changes what it checks")


@pytest.mark.parametrize("term", ["Bound", "Locked", "Unlock"])
def test_the_dictionary_no_longer_explains_the_run_lock(term):
    """K31 (Knut, 5801677743 and 5801750910): the run lock and "Unlock this
    run's limits" are gone, so no Dictionary headword may still define them.

    MUTATION: put the glossary's "Bound (a run's limits)" or "Locked / Unlock
    this run's limits" entry back and this goes red."""
    terms = [t for t, _b in _glossary()]
    assert not any(t.lower().startswith(term.lower()) or
                   f"/ {term.lower()}" in t.lower() for t in terms), terms
