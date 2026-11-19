# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.49: the CHANGELOG entry is the published release note (`scripts/release_notes.py`).

Every `###` heading must be one the script renders as its own section, and the honest limits of
both beta options must stand under "Known issues": nothing of the dual scan on real hardware, the
table only up to the calibration and the first aiming, its changes from one owner's run and a
simulated table, the end of the arm's travel, the way back before the homing as ChromIQ's own
order, the unknown table state at START, a strip with M0 only, and -H refused. The 4.3.48 known
issue about Continue Measurement is gone from this entry."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tests.test_4347_release_review import _entry  # noqa: E402


def _known() -> str:
    import release_notes as rn
    return rn.build(["v4.3.49"], "v4.3.49").split("### ⚠️ Known issues", 1)[1]


def test_every_heading_of_the_4349_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.49")
             if ln.startswith("### ")]
    assert heads == ["New", "Changed", "Fixed", "Known issues"], heads
    assert all(h.lower() in known for h in heads)
    lead = [ln for ln in _entry("v4.3.49") if ln.strip()][0]
    assert lead.startswith("**For everyone updating from 4.3.48: ")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.index("## v4.3.49") < changelog.index("## v4.3.48")
    assert "## Unreleased" not in changelog.split("## v4.3.48", 1)[0]
    assert "—" not in "\n".join(_entry("v4.3.49"))


def test_the_known_issues_say_what_is_not_proven():
    k = _known()
    assert "No part of the dual scan has run on a real instrument or a real table yet" in k
    assert "only the white calibration and the first aiming have run on a real table" in k
    assert "first real run of one owner" in k and "simulated table only" in k
    # the reviewed known-issue wording for the table's front (known_issue_final.txt)
    assert "the head can run gently into the end of its travel once, by at most 5 mm" in k
    assert "Nobody has yet seen what a real table does at that moment" in k
    assert "switch the table off at its power switch" in k
    assert "not one recorded from i1Profiler" in k
    assert "An unknown state of the table at START" in k and "START MEASUREMENT" in k
    assert "has M0 only until it is read again with both" in k
    assert "High resolution spectral mode (-H)" in k
    # 4.3.48's limit is gone: Continue Measurement now takes M1 and M2 up again
    assert "cannot be taken up again" not in "\n".join(_entry("v4.3.49"))


def test_the_entry_names_things_as_the_app_shows_them():
    from workflow import measurement_messages as M
    text = "\n".join(_entry("v4.3.49"))
    # (M-I1IO-DRIVE-FRONT: the 4.3.49 entry names that release's page title, "Part of this sheet
    # lies further forward than usual"; 4.3.50 rewrote the page, its notes name the new one)
    assert "Part of this sheet lies further forward than usual" in text
    for msg in (M.M_I1IO_DRIVE_FRONT_END, M.M_DUAL_CAL_AGAIN):
        assert msg.title in text, msg.id
    assert M.M_DUAL_PASS_HELD.render(strip="C", reason="")[0] in text
    assert M.M_DUAL_CONTINUE_FILL.render(strips="strips C, D", resume="", start="")[0] in text
    assert M.M_DUAL_FILL_OFFER.render(strips="strips C, D", resume="", start="")[0] in text
    for s in ("Bring the arm home", "End measurement", "Refine / resume existing measurement (-r)",
              "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan (beta)"):
        assert s in text, s


def test_the_version_is_4349_everywhere():
    from core.version import APP_VERSION
    assert APP_VERSION == "4.3.49"
    assert "badge/version-4.3.49-" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"softwareVersion": "4.3.49"' in (ROOT / "docs/index.html").read_text(
        encoding="utf-8")
    import json
    certs = json.loads((ROOT / "data/preset_certificates.json").read_text(encoding="utf-8"))
    assert certs["code_version"].startswith("4.3.49/")


def test_readme_no_longer_says_continue_cannot_take_m1_m2_back():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "cannot be taken up\n> again with Continue Measurement" not in readme
    assert "New in 4.3.49" in readme
