"""If ChromIQ ships somebody's data, the app itself has to name them.

#182 F3. Fogra's grant permits redistribution inside software **provided the
data is unchanged and Fogra is identified as the source**. Eleven Fogra files
shipped on 2026-09-10. The naming lived in `data/reference_sets/LICENSE` and
`README.md`, which do travel inside the bundle, and in nothing a user could
reach from the running app: `grep -rn "Fogra" ui/` returned zero.

So this file ties the two together. The condition is not "a file exists
somewhere"; it is that the source is named where the data is used. Every test
here fails if the data ships and the credit does not.

It is written to stay true for a rights holder nobody has heard of yet: nothing
below spells "Fogra". The names come from the same `SOURCE.json` the loader
reads, so a second data set from a second holder is covered the day it lands.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent


def _sources():
    from ui.licences import reference_data_sources
    return reference_data_sources()


def test_something_is_actually_bundled_or_this_file_proves_nothing():
    """The control. If no reference data ships, every test below is vacuously
    true and somebody should know that rather than read green ticks."""
    from workflow.reference_sets import available
    if not available():
        pytest.skip("no reference data ships, so there is no credit to check")
    assert _sources(), "data ships and names no rights holder at all"


def test_the_running_app_names_every_rights_holder(qapp):
    """THE CONDITION ITSELF, checked on the built page rather than on a string
    in a module.

    MUTATION: drop the reference-data group from `_build_licences_tab` and this
    goes red.
    """
    from workflow.reference_sets import available
    if not available():
        pytest.skip("no reference data ships")
    from core.settings import AppSettings
    from PyQt6.QtWidgets import QLabel
    from ui.dialogs.settings_dialog import SettingsDialog

    dlg = SettingsDialog(AppSettings(), None)
    try:
        shown = " ".join(w.text() for w in dlg.findChildren(QLabel) if w.text())
        for who in _sources():
            assert who in shown, (
                f"{who!r} ships data inside ChromIQ and is named nowhere a "
                f"user can see")
    finally:
        dlg.close()


def test_the_app_also_quotes_the_terms_verbatim(qapp):
    """A name without the terms is half the grant.

    MUTATION: drop the terms from the page and this goes red.
    """
    from workflow.reference_sets import available
    if not available():
        pytest.skip("no reference data ships")
    from core.settings import AppSettings
    from PyQt6.QtWidgets import QLabel
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.licences import reference_data_terms

    dlg = SettingsDialog(AppSettings(), None)
    try:
        shown = " ".join(w.text() for w in dlg.findChildren(QLabel) if w.text())
        for _who, terms in reference_data_terms():
            assert terms in shown, "the grant is named but not quoted"
    finally:
        dlg.close()


def test_no_catalogue_carries_a_TRANSLATED_grant():
    """A translated quotation of a grant is not that grant, and the failure
    mode is quiet: wrapping the terms in `tr()` changes nothing visible while
    no catalogue has the key, and starts rewriting a rights holder's own words
    the day somebody translates it. That is why this is checked against the
    catalogues rather than against the rendered page: the mutation that matters
    is invisible on screen.

    MUTATION: add the grant to `data/i18n/de.json` with any German text and
    this goes red.
    """
    import json
    from workflow.reference_sets import available
    if not available():
        pytest.skip("no reference data ships")
    from ui.licences import reference_data_terms
    grants = [t for _who, t in reference_data_terms()]
    assert grants
    for cat in sorted((ROOT / "data" / "i18n").glob("*.json")):
        doc = json.loads(cat.read_text(encoding="utf-8"))
        for g in grants:
            assert g not in doc, (
                f"{cat.name} carries a translation of a rights holder's grant; "
                f"the grant is what they wrote, not a rendering of it")


def test_the_page_says_naming_a_set_is_not_a_certification(qapp):
    """The other half of the same grant, and the promise made in writing to a
    rights holder: ChromIQ never says a print conforms to anything."""
    from workflow.reference_sets import available
    if not available():
        pytest.skip("no reference data ships")
    from core.settings import AppSettings
    from PyQt6.QtWidgets import QLabel
    from ui.dialogs.settings_dialog import SettingsDialog

    dlg = SettingsDialog(AppSettings(), None)
    try:
        shown = " ".join(w.text() for w in dlg.findChildren(QLabel) if w.text())
        assert "certification" in shown.lower()
    finally:
        dlg.close()


def test_the_licence_files_TRAVEL(qapp):
    """A page that shows a file the build did not ship is an empty page.

    `ChromIQ.spec` had neither `LICENSE` nor `THIRD-PARTY-NOTICES.md` in its
    `datas`, so a user who installed the .dmg had neither.

    MUTATION: remove either line from the spec and this goes red.
    """
    spec = (ROOT / "ChromIQ.spec").read_text(encoding="utf-8")
    datas = spec[spec.index("datas=["):spec.index("]", spec.index("datas=["))]
    for name in ("LICENSE", "THIRD-PARTY-NOTICES.md"):
        assert re.search(rf"\(\s*'{re.escape(name)}'", datas), \
            f"{name} is not bundled, so the Licences page cannot show it"


def test_the_page_shows_both_files_when_they_are_there(qapp):
    from ui.licences import notices_markdown, own_licence_text
    assert len(own_licence_text()) > 1000, "ChromIQ's own licence is not readable"
    assert len(notices_markdown()) > 1000, "the notices file is not readable"


def test_the_notices_file_does_not_deny_what_ships():
    """IT DID. The notices file said "Reference data — none. ChromIQ
    deliberately ships no characterization dataset (no FOGRA …)" for a day
    after eleven Fogra files landed in the bundle. A notices file that denies
    what is in the bundle is worse than no notices file.

    MUTATION: put the word back and this goes red.
    """
    from workflow.reference_sets import available
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    i = text.find("**Reference data**")
    assert i >= 0, "the notices file no longer has a reference-data entry"
    entry = text[i:i + 400]
    if available():
        assert "— none" not in entry and "none." not in entry.split("\n")[0], \
            "the notices file says no reference data ships, and some does"
        for who in _sources():
            head = who.split()[0]
            assert head in text, f"{who} ships and the notices never name them"
    else:
        assert "none" in entry.lower()


def test_nothing_here_spells_the_rights_holders_name():
    """This file must keep working for a holder nobody has heard of yet. The
    names come from `SOURCE.json`, which is what the loader reads, so a second
    data set from a second holder is covered the day it lands.

    MUTATION: hard-code a holder's name above and this goes red.
    """
    import io
    import tokenize

    me = Path(__file__).read_text(encoding="utf-8")
    # The CODE, not the prose. Docstrings here name the holder on purpose,
    # because the history is what makes the file readable; what must not name
    # one is anything the tests actually compare against.
    code = []
    for tok in tokenize.generate_tokens(io.StringIO(me).readline):
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        code.append(tok.string)
    body = " ".join(code)
    for known in ("Fogra", "FOGRA"):
        assert known not in body, \
            f"{known!r} is spelled in the code; the check is about one holder"


# ---------------------------------------------------------------------------
# …and only the NOTICE half of the file reaches the product
# ---------------------------------------------------------------------------
def _headings() -> "list[str]":
    from ui.licences import _section_name
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    return [_section_name(l) for l in text.splitlines() if l.startswith("## ")]


def test_every_section_is_classified_as_notice_or_record():
    """THE GUARD. Add a section to the notices file and this fails until
    somebody decides whether users see it.

    Without it the next section is published or withheld by whichever default
    happens to apply, which is exactly how the project's own audit record came
    to be rendered in Preferences: 23,690 characters, including a statement
    that an attribution obligation is currently unmet and a contributor's
    private message quoted with its date. Found by an adversarial round
    reading the page back, not by anyone choosing it.

    MUTATION: add a heading to the notices file and this goes red.
    """
    from ui.licences import NOTICE_SECTIONS, RECORD_SECTIONS
    both = set(NOTICE_SECTIONS) | set(RECORD_SECTIONS)
    assert not (set(NOTICE_SECTIONS) & set(RECORD_SECTIONS)), \
        "a section is in both lists; decide which"
    found = set(_headings())
    assert found == both, (
        f"unclassified sections (a user would see them or not by accident): "
        f"{sorted(found - both)}   |   listed but gone: {sorted(both - found)}")
    for name, why in RECORD_SECTIONS.items():
        assert len(why) > 20, f"{name} is withheld with no reason given"


def test_the_page_shows_the_notices_and_not_the_record():
    """MUTATION: render the whole file and this goes red."""
    from ui.licences import NOTICE_SECTIONS, RECORD_SECTIONS, notices_markdown
    shown = notices_markdown()
    assert shown, "nothing is rendered at all"
    for name in NOTICE_SECTIONS:
        assert f"## {name}" in shown, f"{name} is a notice and is missing"
    for name in RECORD_SECTIONS:
        assert f"## {name}" not in shown, f"{name} is the project's record"


def test_no_private_message_is_quoted_in_a_file_that_ships():
    """A contributor's own words, with a date, inside the application binary.

    The permission is what the file has to record; the wording is in the
    project's history. The rule it falls under is older than this feature: no
    personal data, and no customer's or contributor's private material,
    published anywhere.

    MUTATION: put the quotation back and this goes red.
    """
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    i = text.find("Permission to ship them is")
    assert i >= 0, "the permission itself is no longer recorded"
    para = text[i:i + 400]
    assert "Hopefully" not in para, "the private message is quoted again"
    assert "given in writing" in para, "the permission lost its provenance"


def test_the_page_points_at_nothing_it_does_not_contain():
    """A link into a section the page no longer renders.

    Four of them, all inside kept sections, and the worst two mattered: one
    stated a licence conflict and sent the reader to the resolution, which is
    not on the page; another admitted missing dependency notices and pointed at
    the list of open items, also not on the page. Clicking is harmless and the
    reader is left with the problem and no answer.

    MUTATION: put any `](#…)` link back into a kept section and this goes red.
    """
    import re
    from ui.licences import notices_markdown
    shown = notices_markdown()
    dead = [m.group(0) for m in re.finditer(r"\]\(#[a-z0-9-]+\)", shown)]
    assert not dead, (
        f"the page links to sections it does not contain: {dead}")


def test_the_page_does_not_end_on_a_rule():
    """The last kept section is followed by the separator that divided it from
    a section nobody renders, so the document closed on a horizontal line with
    nothing under it.

    MUTATION: stop trimming the trailing rule and this goes red.
    """
    from ui.licences import notices_markdown
    shown = notices_markdown().rstrip()
    assert shown, "nothing is rendered"
    assert not shown.endswith("---"), "the page ends on a rule and no content"
    assert not shown.endswith("*"), "the page ends mid-emphasis"


#: What the project's own RECORD sounds like, as SHAPES rather than sentences.
#:
#: A phrase list was tried first and defeated itself: a fourth adversarial
#: round measured it and found four of its seven phrases matching nothing at
#: all, because the sentences they were written for had been removed. A list of
#: quotations from text that no longer exists is decoration, not a guard.
#:
#: These are shapes a NOTICE never has and a record always does. A notice says
#: who owns a file and on what terms. It does not speak in the first person
#: about this project, and it does not stamp a decision with a date.
_RECORD_SHAPES = (
    (r"\bwe (were|are|have|had|did|do)\b", "the project talking about itself"),
    (r"\bour own\b", "the project talking about itself"),
    (r"\b(this|an earlier) (assistant|session)\b", "who wrote it, and when"),
    (r"\bdecided\b[^.]{0,20}\d{4}-\d{2}-\d{2}",
     "a decision stamped with its date"),
    (r"\buntil \d{4}-\d{2}-\d{2}\b", "what was true before a date"),
    (r"\bused to (say|be|read)\b", "what this file used to say"),
    (r"\bweighed (below|above)\b", "a pointer into a section nobody renders"),
    # …AND THE THIRD PERSON, which is how most of this repo writes about
    # itself and which the list could not see at all. A fifth adversarial
    # round measured the coverage of the shapes that replaced the phrase list
    # and found three of the original seven no longer caught, and "the owner
    # decided on 2026-09-06" defeating the dated-decision shape with one word.
    (r"\ban? (adversarial|challenge|review) round\b",
     "the project narrating its own review"),
    (r"\b(quoted|recorded|written) here (word for word|until|before)\b",
     "a note about editing this file"),
    (r"\bworse than no\b", "the project arguing with itself"),
    (r"\bnobody (has|had|noticed|came back)\b",
     "the project's own account of what was missed"),
)


def test_the_page_carries_no_note_about_the_project_itself():
    """SECTION HEADINGS WERE NOT ENOUGH, AND TWO ROUNDS ASSUMED THEY WERE.

    The notice/record split is per `## ` heading, so paragraphs of the
    project's own record survived INSIDE kept sections and rendered to users in
    both languages: a note about removing a contributor's private message, a
    commit SHA with a line about what this file used to say, a sentence
    admitting an obligation had been met nowhere a user could look, and a
    decision stamped with its date and the person who made it. Two adversarial
    rounds found them, one after the other.

    MUTATION: put any of those sentences back and this goes red.
    """
    import re as _re
    from ui.licences import notices_markdown
    shown = notices_markdown().lower()
    assert shown, "nothing is rendered"
    found = [(pat, why) for pat, why in _RECORD_SHAPES
             if _re.search(pat, shown)]
    assert not found, (
        "the page carries the project's own record, not a notice: "
        + "; ".join(f"{why} ({pat})" for pat, why in found))


def test_the_check_can_see_each_shape_it_looks_for():
    """THE CONTROL, one sample per shape.

    A pattern list that matches nothing would pass for ever, and the list it
    replaced did exactly that. These samples live here rather than in the
    notices file, so the guard does not need bad text to be kept around in
    order to stay honest.
    """
    import re as _re
    samples = (
        "we were not compliant with that agreement",
        "this is our own work and nothing else",
        "written by this assistant in an earlier pass",
        "licence: agplv3, the owner decided on 2026-09-06",
        "until 2026-09-11 it was met nowhere a user could look",
        "this entry used to read none",
        "not an aggregation argument of the kind weighed below",
        "an adversarial round read the page back and found three paragraphs",
        "his message was quoted here word for word until this morning",
        "a notices file that denies the bundle is worse than no notices file",
        "nobody came back to update the numbers",
    )
    assert len(samples) == len(_RECORD_SHAPES)
    for sample, (pat, _why) in zip(samples, _RECORD_SHAPES):
        assert _re.search(pat, sample), f"{pat} does not match {sample!r}"
