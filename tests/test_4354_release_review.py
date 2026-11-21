# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.54: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits of
both branches must stand under "Known issues": nothing of the table changes and nothing of the
dual scan fix has run on real hardware; a sheet off by a whole patch is not seen; the UV pass of a
dual row is placed by timing alone; more rows are read again; unrecorded speeds inside the
recorded range. v4.3.53 and everything below it stay as released. The version pin moved here
from tests/test_4353_release_review.py."""
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


def _known() -> str:
    import release_notes as rn
    return rn.build(["v4.3.54"], "v4.3.54").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4354_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.54")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.54") < changelog.index("## v4.3.53")
    assert changelog.count("## v4.3.54") == 1
    assert "—" not in "\n".join(_entry("v4.3.54"))


def test_the_released_entries_are_unchanged():
    try:
        old = subprocess.run(["git", "show", "v4.3.53:CHANGELOG.md"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    except Exception:      # noqa: BLE001 - no git here (a source package): nothing to compare
        pytest.skip("git is not available")
    if old.returncode != 0:
        pytest.skip("the tag v4.3.53 is not in this clone")
    now = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert now.endswith(old.stdout[old.stdout.index("## v4.3.53"):])


def test_the_known_issues_say_what_is_not_proven():
    k = " ".join(_known().split())
    assert "Nothing of the i1iO table changes in this version has run on a real table" in k
    assert "the dual scan fix has not run on a real instrument" in k
    assert "off by a whole patch" in k
    assert "is still placed by timing alone" in k
    assert "More rows are read again than before" in k
    assert "that were never recorded" in k
    assert "compare it once with one at 1.00" in k


def test_the_entry_thanks_the_reporter_and_names_the_fixes():
    text = " ".join(" ".join(_entry("v4.3.54")).split())
    assert "Thanks to joshuaziff for the report and the app log (GitHub issue 217)" in text
    assert "1 to 2 mm" in text and "checked against its own readings" in text
    assert "Rest patch by patch" in text and "only for M1 or M2" in text
    assert "CHROMIQ_ROW_SPEED" in text


def test_the_entry_names_things_as_the_app_shows_them():
    import inspect
    from ui.dialogs import settings_dialog as SD
    from ui import i1io_table_window as W
    text = "\n".join(_entry("v4.3.54"))
    src = inspect.getsource(SD)
    for label in ("Row speed", "When the dual scan runs", "only for M1 or M2",
                  "Spectral filter type (-F)"):
        assert label in text or label.lower() in text.lower(), label
    assert "Row speed:" in src and "only for M1 or M2" in " ".join(
        (ROOT / "core/settings.py").read_text(encoding="utf-8").split()) + src
    assert "Rest patch by patch" in inspect.getsource(W)


# The version pin moved to tests/test_4355_release_review.py with the 4.3.55 bump.


def test_readme_and_site_say_what_4354_changes_and_that_it_ran_only_simulated():
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").replace(">", " ").split())
    site = " ".join((ROOT / "docs/index.html").read_text(encoding="utf-8").split())
    assert "New in 4.3.54: every row read in one move is checked against its own" in readme
    assert "New in 4.3.54: a dual scan starts also in a run" in readme
    assert "This fix has not run on a real instrument yet." in readme
    assert "New in 4.3.54: every row read in one move is checked" in site
    assert "this fix has not run on a real instrument yet" in site
