# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.55: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits
must stand under "Known issues": the dual scan changes were proven by replay and simulation
only, a strip that cannot be lined up gains nothing, the lamp wait was tested on one
instrument, the table is still unproven. The Fixed entry must say that only profiles built
with 4.3.55 have their colour settings known. v4.3.54 and everything below it stay as
released. The version pin moved here from tests/test_4354_release_review.py."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tests.test_4347_release_review import _entry  # noqa: E402


def _flat(lines) -> str:
    return " ".join(" ".join(lines).split())


def _known() -> str:
    import release_notes as rn
    return rn.build(["v4.3.55"], "v4.3.55").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4355_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.55")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.55") < changelog.index("## v4.3.54")
    assert changelog.count("## v4.3.55") == 1
    assert "—" not in "\n".join(_entry("v4.3.55"))


def test_the_released_entries_are_unchanged():
    try:
        old = subprocess.run(["git", "show", "v4.3.54:CHANGELOG.md"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    except Exception:      # noqa: BLE001 - no git here (a source package): nothing to compare
        pytest.skip("git is not available")
    if old.returncode != 0:
        pytest.skip("the tag v4.3.54 is not in this clone")
    now = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert now.endswith(old.stdout[old.stdout.index("## v4.3.54"):])


def test_the_known_issues_say_what_is_not_proven():
    k = " ".join(_known().split())
    assert "have not run on a real instrument in this form" in k
    assert "replaying recorded passes of one real i1Pro 2" in k
    assert "the strip is read as in 4.3.54" in k
    assert "tested on one tester's i1Pro 2 only" in k
    assert "has run on a real table yet" in k
    assert "still placed by timing alone" in k


def test_the_fix_says_which_profiles_it_reaches():
    text = _flat(_entry("v4.3.55"))
    assert "ChromIQ only knows the settings of a profile built with 4.3.55 or later" in text
    assert "check it again" in text
    assert "1.6 instead of 0.34" in text
    assert "about 1.7 times the recorded pace" in text and "about 1.05 times" in text
    assert "1.10 s" in text and "keeps 1.5 s" in text


def test_the_entry_names_things_as_the_app_shows_them():
    import inspect
    from ui.dialogs import settings_dialog as SD
    from ui.tabs import tab_check_refine as CR
    from ui.tabs import tab_profile as TP
    from workflow import measurement_messages as MM
    text = _flat(_entry("v4.3.55"))
    sd, cr, tp = inspect.getsource(SD), inspect.getsource(CR), inspect.getsource(TP)
    for label in ("X-Rite i1Pro (not the i1Pro 2): lamp wait before a reading (beta):",
                  "X-Rite i1Pro 2: lamp wait before a reading (beta):"):
        assert label in text and label in sd, label
    for label in ("Analyse Profile Quality", "Use the profile's settings",
                  "Check with my settings", "CIE Observer (-o)", "Illuminant (-i)"):
        assert label in text and label in cr, label
    for label in ("Remove calibration from profile  (-u)",
                  "Check calibration (no file written)  (-c)"):
        assert " ".join(label.split()) in text and label in tp, label
    assert MM.M_DUAL_PASS_TOO_FAST.title in text
    assert MM.M_DUAL_PASS_SHIFTED.title in text


# The version pin moved to tests/test_4356_release_review.py with the 4.3.56 bump.


def test_readme_and_site_say_what_4355_changes_and_that_it_ran_only_replayed():
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").replace(">", " ").split())
    site = " ".join((ROOT / "docs/index.html").read_text(encoding="utf-8").split())
    assert "New in 4.3.55: the second pass is lined up with the first" in readme
    assert "tested by replaying recorded passes, not yet on a real instrument" in readme
    assert "New in 4.3.55: the second pass is lined up with the first" in site
    assert "tested by replaying recorded passes, not yet on a real instrument" in site
