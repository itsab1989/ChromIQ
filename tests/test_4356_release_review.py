# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.56: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

The whole release is the i1iO table beta: every Save ends with the homing, START repairs a table
left in its aiming mode, the recorded way home. Every `###` heading must render as its own
section; "Known issues" must say that nothing of it has run on a real table, list what a real
table still has to show, name the two cases ChromIQ cannot solve by itself and what it shows then,
and keep the unexplained 4.3.54 row error. The entry must not promise that i1Profiler is never
needed. v4.3.55 and everything below it stay as released. The version pin moved here from
tests/test_4355_release_review.py."""
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
    return " ".join(rn.build(["v4.3.56"], "v4.3.56").split("### ⚠️ Known issues", 1)[1].split())


def test_every_heading_of_the_4356_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.56")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.56") < changelog.index("## v4.3.55")
    assert changelog.count("## v4.3.56") == 1
    assert "—" not in "\n".join(_entry("v4.3.56"))


def test_the_released_entries_are_unchanged():
    try:
        old = subprocess.run(["git", "show", "v4.3.55:CHANGELOG.md"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    except Exception:      # noqa: BLE001 - no git here (a source package): nothing to compare
        pytest.skip("git is not available")
    if old.returncode != 0:
        pytest.skip("the tag v4.3.55 is not in this clone")
    now = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert now.endswith(old.stdout[old.stdout.index("## v4.3.55"):])


def test_the_known_issues_say_what_is_not_proven():
    k = _known()
    assert "Nothing of this version has run on a real table yet" in k
    assert "whether that mode survives every switching off and on" in k
    assert "Two cases remain that ChromIQ cannot solve by itself" in k
    assert "send us the log" in k and "do not force the arm by hand" in k
    assert "is not explained yet" in k


def test_the_entry_states_an_aim_not_a_promise():
    text = _flat(_entry("v4.3.56"))
    assert "The aim is that you never need X-Rite's software" in text
    assert "never need i1Profiler" not in text and "never needs i1Profiler" not in text
    assert "Nothing else changes in this version" in text


def test_the_entry_names_things_as_the_app_shows_them():
    import inspect
    from ui import i1io_table_window as W
    from workflow import measurement_messages as MM
    text = _flat(_entry("v4.3.56"))
    src = inspect.getsource(W)
    for label in ("Leave it there", "Try to bring the arm home", "End measurement", "Not now"):
        assert label in text, label
    for label in ("Leave it there", "Try to bring the arm home", "End measurement"):
        assert label in src, label
    assert "Not now" in MM.M_I1IO_DRIVE_REPAIR_AT_START.body


def test_the_version_is_4356_everywhere():
    from core.version import APP_VERSION
    assert APP_VERSION == "4.3.56"
    assert "badge/version-4.3.56-" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"softwareVersion": "4.3.56"' in (ROOT / "docs/index.html").read_text(
        encoding="utf-8")
    certs = json.loads((ROOT / "data/preset_certificates.json").read_text(encoding="utf-8"))
    assert certs["code_version"].startswith("4.3.56/")


def test_readme_and_site_say_what_4356_changes_and_that_it_ran_only_simulated():
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").replace(">", " ").split())
    site = " ".join((ROOT / "docs/index.html").read_text(encoding="utf-8").split())
    assert "cannot start a new measurement on it until the arm is home" not in readme
    assert "New in 4.3.56: a measurement that replaced an earlier one" in readme
    assert "This has run only on a simulated table." in readme
    assert "New in 4.3.56: a table left in its aiming mode is put right at the next START" in site
    assert "this has run only on a simulated table" in site
