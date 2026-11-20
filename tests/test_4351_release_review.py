# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.51: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits must
stand under "Known issues": no START case with the arm out has run on a real table; the try was
never recorded at a start; whether the arm moves by hand on a switched-off table is not known;
where ChromIQ still needs i1Profiler 3.8.6 or older (3.8.7 and newer no longer work with the
i1iO 2) or the power switch; what stays from 4.3.50. The version pin moved here from
tests/test_4350_release_review.py."""
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
    return rn.build(["v4.3.51"], "v4.3.51").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4351_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.51")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    lead = [ln for ln in _entry("v4.3.51") if ln.strip()][0]
    assert lead.startswith("**For everyone updating from 4.3.50: ")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.51") < changelog.index("## v4.3.50")
    assert "## Unreleased" not in changelog.split("## v4.3.50", 1)[0]
    assert "—" not in "\n".join(_entry("v4.3.51"))


def test_the_known_issues_say_what_is_not_proven():
    k = _known()
    assert "None of the START cases with the arm out has run on a real table" in k
    assert "has never been recorded at a start" in k
    assert "Whether the arm can be pushed by hand while the table is switched off is not known" in k
    assert "i1Profiler 3.8.7 and newer no longer work with the i1iO 2" in k
    assert "the power switch comes first" in k and "just switched on with the arm out" in k
    assert "left in its aiming mode" in k
    for s in ("reading in rows", "the dual scan on the table", "a second page",
              "the end of the arm's travel", "contains a space"):
        assert s in k, s


def test_the_entry_names_things_as_the_app_shows_them():
    from workflow import measurement_messages as M
    text = "\n".join(_entry("v4.3.51"))
    for msg in (M.M_I1IO_DRIVE_ARM_OUT_TRY, M.M_I1IO_DRIVE_HOME_TRY_FAILED,
                M.M_I1IO_DRIVE_STILL_AIMING, M.M_I1IO_DRIVE_COLD, M.M_I1IO_DRIVE_FRONT):
        assert msg.title in text, msg.id
    for s in ("Bring the arm home", "End measurement", "START MEASUREMENT", "The arm is out",
              "Show the log file", "← Back", "Log file:", "X-Rite i1iO support",
              "Go forward carefully, my hands are away", "I will move the sheet"):
        assert s in text, s
    # the 4.3.50 statement is corrected, not repeated
    assert "there is no diagnostics file of that run" in text


def test_the_version_is_4351_everywhere():
    from core.version import APP_VERSION
    assert APP_VERSION == "4.3.51"
    assert "badge/version-4.3.51-" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"softwareVersion": "4.3.51"' in (ROOT / "docs/index.html").read_text(
        encoding="utf-8")
    certs = json.loads((ROOT / "data/preset_certificates.json").read_text(encoding="utf-8"))
    assert certs["code_version"].startswith("4.3.51/")


def test_readme_and_site_say_what_4351_changes_and_that_it_ran_only_simulated():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    site = (ROOT / "docs/index.html").read_text(encoding="utf-8")
    assert "New in 4.3.51" in readme and "New in 4.3.51" in site
    assert "None of this has run on\n>   a real table yet" in readme
    assert "has run only on a simulated table" in site.split("New in 4.3.51", 1)[1][:400]
