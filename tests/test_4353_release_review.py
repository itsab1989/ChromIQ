# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.53: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits must
stand under "Known issues": reading in rows and every other table change of this version have run
only on a simulated table; the right blue light alone was never recorded; any wait below its
default has not been tried on a real instrument. v4.3.52 and everything below it stay as released.
The version pin moved here from tests/test_4352_release_review.py."""
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
    return rn.build(["v4.3.53"], "v4.3.53").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4353_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.53")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.53") < changelog.index("## v4.3.52")
    assert changelog.count("## v4.3.53") == 1
    assert "—" not in "\n".join(_entry("v4.3.53"))


def test_the_released_entries_are_unchanged():
    try:
        old = subprocess.run(["git", "show", "v4.3.52:CHANGELOG.md"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    except Exception:      # noqa: BLE001 - no git here (a source package): nothing to compare
        pytest.skip("git is not available")
    if old.returncode != 0:
        pytest.skip("the tag v4.3.52 is not in this clone")
    now = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert now.endswith(old.stdout[old.stdout.index("## v4.3.52"):])


def test_the_known_issues_say_what_is_not_proven():
    k = _known()
    assert "Reading in rows has never been tried with ChromIQ on a real table" in k
    assert "None of the other table changes of this version has run on a real table" in k
    assert "The right blue light alone has not been seen in a recording of i1Profiler" in k
    assert "All 23 recorded first passes ran from left to right" in k
    assert "Any wait shorter than its default has not been tried with ChromIQ on a real" in k
    assert "at least 3, before 5" in k and "border that grows with the speed" in k
    assert "Where the table's arm really ends its travel is not known" in k


def test_the_entry_names_things_as_the_app_shows_them():
    import inspect
    from ui.dialogs import settings_dialog as SD
    text = "\n".join(_entry("v4.3.53"))
    src = inspect.getsource(SD)
    for label in ("i1Pro 2, wait after a light change:", "Dual scan, wait after the blue light:",
                  "Dual scan, blue light after the first pass:",
                  "X-Rite i1Pro and i1Pro 2: lamp wait before a reading (beta):",
                  "Guided, step by step measurement", "Ready light and result signals (green / red)"):
        assert label in text, label
        assert label in src, label


def test_the_version_is_4353_everywhere():
    from core.version import APP_VERSION
    assert APP_VERSION == "4.3.53"
    assert "badge/version-4.3.53-" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"softwareVersion": "4.3.53"' in (ROOT / "docs/index.html").read_text(
        encoding="utf-8")
    certs = json.loads((ROOT / "data/preset_certificates.json").read_text(encoding="utf-8"))
    assert certs["code_version"].startswith("4.3.53/")


def test_readme_and_site_say_what_4353_changes_and_that_it_ran_only_simulated():
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").replace(">", " ").split())
    site = " ".join((ROOT / "docs/index.html").read_text(encoding="utf-8").split())
    assert "New in 4.3.53: rows are read as rows wherever the chart lies" in readme
    assert "None of this has run on a real table yet." in readme
    assert "the blue light blinks on the side the second pass moves towards" in readme
    assert "New in 4.3.53: rows are read as rows wherever the chart lies" in site
    assert "not run on a real table yet" in site


def test_the_entry_says_the_speeds_the_border_allows_and_what_changes_with_the_betas_off():
    text = "\n".join(_entry("v4.3.53"))
    assert "ChromIQ's own charts are read at 168 mm/s" not in text
    assert "ChromIQ's own charts with 10 mm patches are read at 88 mm/s" in text
    assert "168 mm/s is used for patches of about 14 mm and longer" in text
    assert "except for one fix for every strip instrument" in text
    assert "An arm left free (after aiming) is brought home from wherever it is" in text
