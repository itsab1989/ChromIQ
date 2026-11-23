# SPDX-License-Identifier: GPL-3.0-or-later
"""Release 4.3.59: the version is the same everywhere. The pin moved here from
tests/test_4358_release_review.py."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_version_is_4359_everywhere():
    from core.version import APP_VERSION
    assert APP_VERSION == "4.3.59"
    assert "badge/version-4.3.59-" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"softwareVersion": "4.3.59"' in (ROOT / "docs/index.html").read_text(
        encoding="utf-8")
    certs = json.loads((ROOT / "data/preset_certificates.json").read_text(encoding="utf-8"))
    assert certs["code_version"].startswith("4.3.59/")
