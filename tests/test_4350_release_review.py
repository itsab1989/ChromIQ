# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.50: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits must
stand under "Known issues": ONE complete page on a real i1iO 2 (patch by patch, 4.3.49) and one
homing after a stop; rows, the dual scan on the table, a second page, the homing from the front
and the end of travel not run on a real table; the aiming mode left on by an arm left out; the
tester's two real dual scans (M1 and M2 not checked against a reference); what the strip shift
check cannot do. The version pin moved here from tests/test_4349_release_review.py."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tests.test_4347_release_review import _entry  # noqa: E402


def _known() -> str:
    import release_notes as rn
    return rn.build(["v4.3.50"], "v4.3.50").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4350_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.50")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    lead = [ln for ln in _entry("v4.3.50") if ln.strip()][0]
    assert lead.startswith("**For everyone updating from 4.3.49: ")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.50") < changelog.index("## v4.3.49")
    assert "## Unreleased" not in changelog.split("## v4.3.49", 1)[0]
    assert "—" not in "\n".join(_entry("v4.3.50"))


def test_the_known_issues_say_what_is_not_proven():
    k = _known()
    assert "A real i1iO 2 table has read one complete page so far" in k
    assert "patch by patch" in k and "has worked once on a real table" in k
    for s in ("reading in rows", "the dual scan on the table", "a second page",
              "bringing the arm home from the front of the table", "the end of the arm's travel"):
        assert s in k, s
    assert "the table stays in its aiming mode" in k
    assert "should bring it home, but no recording shows it" in k
    assert "press End measurement in ChromIQ first" in k
    assert "M1 and M2 have not yet been checked against a reference" in k
    assert "cannot find every shifted strip" in k
    assert "Keep it keeps the reading" in k


def test_the_entry_names_things_as_the_app_shows_them():
    from core.i18n import tr  # noqa: F401
    from workflow import measurement_messages as M
    text = "\n".join(_entry("v4.3.50"))
    # (4.3.56 gave STILL-AIMING a new title, for answers that do not agree; the title 4.3.50 named,
    # "The table is still in its aiming mode", is now REPAIR-AT-START's, the page START shows then)
    for msg in (M.M_I1IO_DRIVE_HOME_AT_END, M.M_I1IO_DRIVE_FRONT, M.M_I1IO_DRIVE_FRONT_STOPPED,
                M.M_I1IO_DRIVE_REPAIR_AT_START, M.M_I1IO_DRIVE_CONSENT):
        assert msg.title in text, msg.id
    assert M.M_I1IO_DRIVE_ROW_M0_ONLY.title.format(row="5") in text
    assert M.M_STRIP_ENDS_SHIFTED_LATE.title.format(strip="A") in text
    assert M.M_STRIP_END_PAPER_LATE.title.format(strip="A") in text
    for s in ("Bring the arm home, my hands are away", "Not now", "Save and stop",
              "Discard and stop", "Go forward carefully, my hands are away",
              "I will move the sheet", "Re-measure this strip", "Keep it", "End measurement",
              "Warn me if a strip looks misaligned", "Strip may be misaligned"):
        assert s in text, s


# The version pin moved to tests/test_4351_release_review.py with the 4.3.51 bump.


def test_readme_and_site_no_longer_say_no_chart_was_read_on_a_real_table():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # The site (docs/index.html) is a feature overview since 2026-11-24 and
    # carries no "New in" history; tests/test_the_site_is_a_feature_overview.py pins that.
    assert "has not yet read a chart on a real one" not in readme
    assert "New in 4.3.50" in readme
    assert "all or none" not in readme
