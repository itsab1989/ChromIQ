"""The GitHub test-suite workflow runs only when someone starts it.

Basti, 2026-10-04: "for now i want the test runs to be something that is only
triggered manually by me or when i tell you though. no runs everytime you cut
a release". A push, tag or pull_request trigger added to
`.github/workflows/tests.yml` would start a paid run on every release.
"""
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "tests.yml"


def _triggers():
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    # YAML 1.1 reads the bare key `on` as the boolean True.
    on = doc.get("on", doc.get(True))
    return set(on) if isinstance(on, dict) else {on}


def test_the_only_trigger_is_a_manual_start():
    assert _triggers() == {"workflow_dispatch"}


def test_the_job_reports_pytests_own_exit_code():
    text = WF.read_text(encoding="utf-8")
    assert "rc=$?" in text and "exit $rc" in text
    assert "pytest $SLOW $ENGINE -n auto" in text


def test_the_heavy_engine_tier_is_off_unless_asked_for():
    """Basti, 2026-11-11: the engine is beta and off by default, so a
    hand-started run leaves its heavy tier (--runengine) out unless the
    engine input is ticked."""
    inputs = yaml.safe_load(WF.read_text(encoding="utf-8"))[True][
        "workflow_dispatch"]["inputs"]
    assert inputs["engine"]["type"] == "boolean"
    assert inputs["engine"]["default"] is False
    text = WF.read_text(encoding="utf-8")
    assert text.count("then ENGINE=--runengine; else ENGINE=; fi") == 3
