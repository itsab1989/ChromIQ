"""The Homebrew tap update the release workflow runs (scripts/update_homebrew_tap.py).

A plain ``brew install --cask chromiq`` must never get a beta, beta users must
never be left behind a newer stable release, and no cask may ever move back
to an older version. The casks under tests/data/homebrew_tap are copies of
the tap's own (github.com/itsab1989/homebrew-chromiq), so a change to their
layout that the script can no longer rewrite fails here first.
"""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "data" / "homebrew_tap"
_spec = importlib.util.spec_from_file_location(
    "update_homebrew_tap", ROOT / "scripts" / "update_homebrew_tap.py")
tap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tap)

ARM = "a" * 64
INTEL = "b" * 64
TAGS = ["v4.3.2", "4.3.2", "v4.3.3-beta.16", "v4.3.3-beta.2", "v4.3.3",
        "v4.3.3-rc.1", "v4.4.0-alpha", "v10.0.0", "garbage", "v4.3.3+build.5"]


def test_the_version_order_is_the_updaters():
    from core.updater import _parse_version, _is_prerelease
    for t in TAGS:
        assert tap.parse_version(t) == _parse_version(t), t
        assert tap.is_prerelease(t) == _is_prerelease(t), t


@pytest.mark.parametrize("tag, stable, beta, expected", [
    ("v4.3.3-beta.17", "4.3.2", "4.3.3-beta.16", ["chromiq@beta"]),
    ("v4.3.3", "4.3.2", "4.3.3-beta.16", ["chromiq", "chromiq@beta"]),
    # a hotfix of the stable line while a newer beta is out: beta stays
    ("v4.3.2.1", "4.3.2", "4.3.3-beta.16", ["chromiq"]),
    # a re-run, or an older tag: nothing moves back
    ("v4.3.3-beta.16", "4.3.2", "4.3.3-beta.16", []),
    ("v4.3.1", "4.3.2", "4.3.3-beta.16", []),
    # a beta never reaches the stable cask, even if far newer
    ("v5.0.0-beta.1", "4.3.2", "4.3.3-beta.16", ["chromiq@beta"]),
])
def test_which_casks_a_release_moves(tag, stable, beta, expected):
    assert tap.casks_to_update(tag, stable, beta) == expected


def _tap(tmp_path: Path) -> Path:
    (tmp_path / "Casks").mkdir()
    for f in DATA.glob("*.rb"):
        shutil.copy(f, tmp_path / "Casks" / f.name)
    return tmp_path


def test_a_beta_release_rewrites_only_the_beta_cask(tmp_path):
    t = _tap(tmp_path)
    before = (t / "Casks" / "chromiq.rb").read_text()
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9-beta.1",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    assert (t / "Casks" / "chromiq.rb").read_text() == before
    beta = (t / "Casks" / "chromiq@beta.rb").read_text()
    assert 'version "9.9.9-beta.1"' in beta
    assert f'sha256 arm:   "{ARM}"' in beta and f'intel: "{INTEL}"' in beta


def test_a_stable_release_rewrites_both_casks(tmp_path):
    t = _tap(tmp_path)
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    for name in ("chromiq.rb", "chromiq@beta.rb"):
        text = (t / "Casks" / name).read_text()
        assert 'version "9.9.9"' in text
        assert ARM in text and INTEL in text
        # nothing but the version and the two checksums changed
        orig = (DATA / name).read_text()
        assert len(text.splitlines()) == len(orig.splitlines())


@pytest.mark.parametrize("bad", ["", "abc", "A" * 64, "g" * 64])
def test_a_bad_checksum_is_refused(tmp_path, bad):
    t = _tap(tmp_path)
    with pytest.raises(SystemExit):
        tap.main(["--tap", str(t), "--tag", "v9.9.9",
                  "--arm-sha", bad, "--intel-sha", INTEL])


def test_the_casks_keep_their_safeguards():
    stable = (DATA / "chromiq.rb").read_text()
    beta = (DATA / "chromiq@beta.rb").read_text()
    assert 'conflicts_with cask: "chromiq@beta"' in stable
    assert 'conflicts_with cask: "chromiq"' in beta
    assert "strategy :github_latest" in stable  # stable cask: no pre-releases
    for text in (stable, beta):
        assert 'depends_on formula: "argyll-cms"' in text
        assert "com.apple.quarantine" in text
        # zap never touches the user's projects
        zap = text.split("zap trash:", 1)[1]
        assert "~/ChromIQ\"" not in zap and "~/ChromIQ/" not in zap


def test_the_release_workflow_updates_the_tap_after_every_macos_build():
    wf = (ROOT / ".github" / "workflows" / "build-release.yml").read_text()
    job = wf.split("\n  homebrew:\n", 1)[1]
    assert "needs: build" in job
    assert "!inputs.dry_run" in job
    assert "scripts/update_homebrew_tap.py" in job
    assert "secrets.HOMEBREW_TAP_DEPLOY_KEY" in job
