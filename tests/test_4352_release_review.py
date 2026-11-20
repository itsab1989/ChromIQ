# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.52: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits must
stand under "Known issues": the table's START with the arm out and the unguided measurement have
run only on a simulated table; the blue light and its 0.37 s wait, and any wait after a light
change below 2.1 s, have not been tried on a real i1Pro 2, with the worst case and the way to
switch the blue light off by its real label. v4.3.51 and everything below it stay as released.
The version pin moved here from tests/test_4351_release_review.py."""
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
    return rn.build(["v4.3.52"], "v4.3.52").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4352_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.52")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.52") < changelog.index("## v4.3.51")
    assert changelog.count("## v4.3.52") == 1
    assert "—" not in "\n".join(_entry("v4.3.52"))


def test_the_released_entries_are_unchanged():
    try:
        old = subprocess.run(["git", "show", "v4.3.51:CHANGELOG.md"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    except Exception:      # noqa: BLE001 - no git here (a source package): nothing to compare
        pytest.skip("git is not available")
    if old.returncode != 0:
        pytest.skip("the tag v4.3.51 is not in this clone")
    now = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert now.endswith(old.stdout[old.stdout.index("## v4.3.51"):])


def test_the_known_issues_say_what_is_not_proven():
    k = _known()
    assert "None of the table's new START behaviour has run on a real table with the arm out" in k
    assert "“Guided, step by step measurement” off has not run on a real table yet" in k
    assert "0.37 s wait after it have not been tried on a real instrument" in k
    assert "M1 and M2 then stop for the rest of that measurement, and M0 is still measured" in k
    assert "shorter than 2.1 s has not been tried with ChromIQ on a real i1Pro 2" in k
    for s in ("reading in rows", "the dual scan on the table", "a second page",
              "the end of the arm's travel"):
        assert s in k, s


def test_the_entry_names_things_as_the_app_shows_them():
    from core.i18n import tr  # noqa: F401 - the labels below are English source strings
    import inspect
    from ui.dialogs import settings_dialog as SD
    from workflow import measurement_messages as M
    text = "\n".join(_entry("v4.3.52"))
    src = inspect.getsource(SD)
    for label in ("What the lights show:", "Ready light and result signals (green / red)",
                  "Ready light; the instrument's own green / red (i1Pro 3)",
                  "i1Pro 2, wait after a light change:", "Guided, step by step measurement",
                  "Keep the table's detailed log"):
        assert label.rstrip(":") in text, label
        assert label in src, label
    assert M.M_I1IO_DRIVE_HOME_AT_START.title in text
    assert M.M_DUAL_PASS_TWO_UNREAD.title.format(strip="A") in text
    for s in ("Bring the arm home, my hands are away", "Not now", "X-Rite i1iO support",
              "Play sounds during measurement", "Patch-by-patch mode (-p)"):
        assert s in text, s


def test_the_version_is_4352_everywhere():
    from core.version import APP_VERSION
    assert APP_VERSION == "4.3.52"
    assert "badge/version-4.3.52-" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"softwareVersion": "4.3.52"' in (ROOT / "docs/index.html").read_text(
        encoding="utf-8")
    certs = json.loads((ROOT / "data/preset_certificates.json").read_text(encoding="utf-8"))
    assert certs["code_version"].startswith("4.3.52/")


def test_readme_and_site_say_what_4352_changes_and_that_it_ran_only_simulated():
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").replace(">", " ").split())
    site = " ".join((ROOT / "docs/index.html").read_text(encoding="utf-8").split())
    assert readme.count("New in 4.3.52") == 2 and site.count("New in 4.3.52") == 2
    assert "has run on a real table yet" in readme.split("New in 4.3.52", 1)[1][:700]
    assert "have not been tried on a real instrument yet" in readme.split("New in 4.3.52")[2][:500]
    assert "neither has run on a real table yet" in site.split("New in 4.3.52", 1)[1][:400]
    assert "not been tried on a real instrument yet" in site.split("New in 4.3.52")[2][:400]
