"""Release notes a user can scan.

Knut, beta.139: *"the release note must give a great overview of all added
features, and the list of bugfixes must be shown in a comprehensive manner so
that users can recognise if a bug they have been annoyed by has been fixed."*
"""
from __future__ import annotations

import pytest

from scripts.release_notes import build, split_sections, _versions


BODY = """
### New

- A thing that did not exist before.

### Fixed

- **Strips failed over and over.** Because of a cause nobody would search for.
- **A window stayed on screen.** Also fixed.
"""


def test_the_sections_are_separated():
    got = split_sections(BODY.splitlines())
    assert any("did not exist" in ln for ln in got["new"])
    assert any("Strips failed" in ln for ln in got["fixed"])
    assert not any("did not exist" in ln for ln in got["fixed"])


def test_an_old_entry_without_headings_still_renders():
    """Every entry written before this existed is a bare list of fixes; it must
    not vanish from its own release note."""
    got = split_sections(["- Something was fixed.", "- So was this."])
    assert len(got["fixed"]) == 2
    assert got["new"] == []


def test_the_note_opens_with_a_summary(monkeypatch):
    import scripts.release_notes as rn

    monkeypatch.setattr(rn, "_versions", lambda: [("v9.9.9", BODY.splitlines())])
    note = rn.build(["v9.9.9"], "v9.9.9")
    head = note.splitlines()[2]
    assert "1 new or changed thing" in head, head
    assert "2 fixed problems" in head, head


def test_several_versions_fold_into_one_note(monkeypatch):
    """What a 4.0.0 announcement needs after a hundred betas."""
    import scripts.release_notes as rn

    other = "### Fixed\n\n- A third fix.\n"
    monkeypatch.setattr(rn, "_versions", lambda: [
        ("v9.9.9", BODY.splitlines()),
        ("v9.9.8", other.splitlines()),
    ])
    note = rn.build(["v9.9.9", "v9.9.8"], "ChromIQ 9.9")
    assert "Everything from v9.9.8 … v9.9.9" in note
    assert "3 fixed problems" in note
    assert "A third fix." in note


def test_a_missing_version_is_an_error_not_an_empty_note(monkeypatch):
    import scripts.release_notes as rn

    monkeypatch.setattr(rn, "_versions", lambda: [])
    with pytest.raises(SystemExit):
        rn.build(["v0.0.0"], "nothing")


# ---- the real CHANGELOG --------------------------------------------------
def test_the_current_release_renders_every_section_it_actually_has():
    """The real CHANGELOG's newest entry renders, with each section it has.

    This used to demand "What's new" and "Fixed" from every release, which held
    only for as long as every release happened to have both. A release that
    fixes things and changes nothing else is a normal release — beta.142 was
    one — and a test that forces a "New" heading is a test that asks for an
    invented feature entry. What matters is that nothing in the changelog is
    dropped on the way to the note, so that is what is checked; that the
    renderer can produce all three headings is covered by the synthetic
    fixtures above, where a body with all three can be written on purpose.
    """
    import re

    from core.version import APP_VERSION
    import scripts.release_notes as rn

    body = "\n".join(dict(
        (v, lines) for v, lines in rn._versions())[f"v{APP_VERSION}"])
    note = build([f"v{APP_VERSION}"], f"v{APP_VERSION}")

    # Driven from the renderer's own table, never a copy of it. A hand-written
    # list here is what let "### Documentation" be written, reviewed and then
    # rendered as nothing: the test did not know the section existed either.
    rendered = {md: pretty for _key, md, pretty in rn.SECTIONS}
    names = "|".join(re.escape(md) for md in rendered)
    present = set(re.findall(rf"^### ({names})\s*$", body, re.M))
    assert present, f"v{APP_VERSION} has no sections at all in the CHANGELOG"
    for section in present:
        assert rendered[section] in note, (
            f"the CHANGELOG's “{section}” section is missing from the "
            f"generated note for v{APP_VERSION}"
        )
    assert "in this release." in note.splitlines()[2]


def test_the_workflow_uses_the_generator():
    from pathlib import Path

    wf = Path(__file__).resolve().parents[1] / ".github/workflows/build-release.yml"
    text = wf.read_text(encoding="utf-8")
    assert "scripts/release_notes.py --tag" in text
    # …and still falls back, so a note is never empty.
    assert "awk" in text
