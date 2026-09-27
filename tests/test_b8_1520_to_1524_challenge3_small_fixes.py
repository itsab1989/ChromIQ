"""The small items of beta 45 challenge round 3 (B8-1520, B8-1522 to B8-1524),
each held by a guard so it cannot come back unseen.

OFFSCREEN: data and settings checks; no window is involved.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _beta45() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = text.index("## v4.3.0-beta.45")
    return text[start:text.index("\n## ", start + 5)]


# ---- B8-1520: the Argyll path comes back after every test -------------------
_SEEN: dict = {}


def test_a_test_may_point_the_argyll_path_nowhere(tmp_path):
    """The first half: a test sets the path, as five files do."""
    from core.settings import AppSettings
    s = AppSettings()
    _SEEN["before"] = s.get("argyll_bin_path")
    s.set("argyll_bin_path", str(tmp_path / "a-folder-with-no-argyll"))
    assert s.get("argyll_bin_path").endswith("a-folder-with-no-argyll")


def test_the_next_test_gets_the_argyll_path_back():
    """The second half, in the same file on the same worker: the conftest's
    `_the_argyll_path_is_put_back` restored what the first test found.

    MUTATION, proven red: remove that fixture (this test then reads the
    "a-folder-with-no-argyll" the first one left)."""
    if "before" not in _SEEN:
        pytest.skip("runs after its first half")
    from core.settings import AppSettings
    assert AppSettings().get("argyll_bin_path") == _SEEN["before"]


# ---- B8-1522 and B8-1523: the changelog says what is true -------------------
def test_the_changelog_names_the_panel_the_white_and_black_counts_go_to():
    """The presets window shows no white or black count; the counts go to
    Create Chart's Manual White Patches and Black Patches (B8-1522)."""
    b45 = _beta45()
    assert "hold 9 white and 8 black patches" not in b45
    line = next(ln for ln in b45.splitlines() if "484-patch" in ln and "9 and 8" in ln)
    assert "White Patches and Black Patches in Create Chart's Manual settings" in line


def test_the_changelog_gives_the_cr30_width_it_prints():
    """Named w17.0mm, printed at 16.76 mm (B8-1523)."""
    b45 = _beta45()
    assert "the width it prints" not in b45
    assert "16.76 mm" in b45


# ---- B8-1524: the translation prompt carries the ** rule --------------------
def test_the_translation_prompt_explains_the_bold_marks():
    text = (ROOT / "scripts" / "i18n_agent" / "prompt_template.md").read_text(
        encoding="utf-8")
    line = next(ln for ln in text.splitlines() if '"**...**"' in ln)
    assert "bold lead-in" in line and "same number of marks" in line
    assert "leave the marks out" in line
