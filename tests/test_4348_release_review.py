# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.48: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section (an unknown one is copied
into the section above it: v4.3.46's "Honest limits" rendered inside "Changed"), and the honest
limits of the dual scan must stand under "Known issues", not among the changes."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tests.test_4347_release_review import _entry  # noqa: E402


def test_every_heading_of_the_4348_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.48")
             if ln.startswith("### ")]
    # the table branch's entries (merged 2026-11-19) came in under Changed
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    note = rn.build(["v4.3.48"], "v4.3.48")
    known_part = note.split("### ⚠️ Known issues", 1)[1]
    assert "No part of the dual scan has run on a real instrument or a real table yet" \
        in known_part
    assert "Continue Measurement" in known_part and "ruler" in known_part
    # the merge of fix/4.3.48-table-home: its honest limits in the same list
    assert "offered only in the recorded cases" in known_part
    assert "NOT offered for a free arm at the place where the aiming starts" in known_part
    assert "The automatic second move to a patch is not itself recorded" in known_part
    assert "Neither the homing after a stop nor the second move has run on a real table yet" \
        in known_part
    changelog = (Path(__file__).resolve().parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased" not in changelog.split("## v4.3.47", 1)[0]
    assert "—" not in "\n".join(_entry("v4.3.48"))


def test_the_entry_names_the_options_as_the_app_shows_them():
    from workflow.dual_scan import session
    text = "\n".join(_entry("v4.3.48"))
    assert session.parent_label() + " (beta)" in text
    assert session.switch_label() in text
    assert "Which instrument do you measure with?" in text
    assert "Instrument for the dual scan:" in text


# The version pin moved to tests/test_4349_release_review.py with the 4.3.49 bump.
