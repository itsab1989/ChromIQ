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
    # a re-run of the tag the cask is at: its checksums are rewritten (a
    # re-run rebuilds the DMGs), the other cask is left alone
    ("v4.3.3-beta.16", "4.3.2", "4.3.3-beta.16", ["chromiq@beta"]),
    ("v4.3.2", "4.3.2", "4.3.3-beta.16", ["chromiq"]),
    ("v4.3.3", "4.3.3", "4.3.3", ["chromiq", "chromiq@beta"]),
    # an older tag: nothing moves back
    ("v4.3.1", "4.3.2", "4.3.3-beta.16", []),
    ("v4.3.3-beta.15", "4.3.2", "4.3.3-beta.16", []),
    ("v4.3.3-beta.17", "4.3.3", "4.3.3", []),
    ("v4.3.3-rc.1", "4.3.2", "4.3.3-beta.16", ["chromiq@beta"]),
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
    before = (t / "Casks" / "chromiq.rb").read_text(encoding="utf-8")
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9-beta.1",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    assert (t / "Casks" / "chromiq.rb").read_text(encoding="utf-8") == before
    beta = (t / "Casks" / "chromiq@beta.rb").read_text(encoding="utf-8")
    assert 'version "9.9.9-beta.1"' in beta
    assert f'sha256 arm:   "{ARM}"' in beta and f'intel: "{INTEL}"' in beta


def test_a_stable_release_rewrites_both_casks(tmp_path):
    t = _tap(tmp_path)
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    for name in ("chromiq.rb", "chromiq@beta.rb"):
        text = (t / "Casks" / name).read_text(encoding="utf-8")
        assert 'version "9.9.9"' in text
        assert ARM in text and INTEL in text
        # nothing but the version, the two checksums and the url changed
        orig = (DATA / name).read_text(encoding="utf-8")
        assert len(text.splitlines()) == len(orig.splitlines())


def test_a_rerun_with_rebuilt_dmgs_refreshes_the_checksums(tmp_path):
    t = _tap(tmp_path)
    beta_now = tap.cask_version((t / "Casks" / "chromiq@beta.rb").read_text(encoding="utf-8"))
    stable_before = (t / "Casks" / "chromiq.rb").read_text(encoding="utf-8")
    assert tap.main(["--tap", str(t), "--tag", f"v{beta_now}",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    beta = (t / "Casks" / "chromiq@beta.rb").read_text(encoding="utf-8")
    assert f'version "{beta_now}"' in beta and ARM in beta and INTEL in beta
    assert (t / "Casks" / "chromiq.rb").read_text(encoding="utf-8") == stable_before


def test_an_older_tag_changes_no_file(tmp_path):
    t = _tap(tmp_path)
    before = {f.name: f.read_text(encoding="utf-8") for f in (t / "Casks").iterdir()}
    assert tap.main(["--tap", str(t), "--tag", "v1.0.0",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    assert {f.name: f.read_text(encoding="utf-8") for f in (t / "Casks").iterdir()} == before


@pytest.mark.parametrize("tag", ["4.3.4", "garbage", "research-integration-6", ""])
def test_a_tag_the_casks_cannot_download_is_refused(tmp_path, tag):
    # the casks' url is .../download/v#{version}/...: no "v", no release
    t = _tap(tmp_path)
    with pytest.raises(SystemExit):
        tap.main(["--tap", str(t), "--tag", tag,
                  "--arm-sha", ARM, "--intel-sha", INTEL])


@pytest.mark.parametrize("bad", ["", "abc", "A" * 64, "g" * 64])
def test_a_bad_checksum_is_refused(tmp_path, bad):
    t = _tap(tmp_path)
    with pytest.raises(SystemExit):
        tap.main(["--tap", str(t), "--tag", "v9.9.9",
                  "--arm-sha", bad, "--intel-sha", INTEL])


def test_the_casks_keep_their_safeguards():
    stable = (DATA / "chromiq.rb").read_text(encoding="utf-8")
    beta = (DATA / "chromiq@beta.rb").read_text(encoding="utf-8")
    assert 'conflicts_with cask: "chromiq@beta"' in stable
    assert 'conflicts_with cask: "chromiq"' in beta
    assert "strategy :github_latest" in stable  # stable cask: no pre-releases
    # beta: the releases feed, which lists pre-releases and is not rate-limited
    # the way the anonymous GitHub API is on a shared CI address
    assert "releases.atom" in beta and "api.github.com" not in beta
    for text in (stable, beta):
        assert 'depends_on formula: "argyll-cms"' in text
        assert "com.apple.quarantine" in text
        # zap never touches the user's projects
        zap = text.split("zap trash:", 1)[1]
        assert "~/ChromIQ\"" not in zap and "~/ChromIQ/" not in zap


def test_the_release_workflow_updates_the_tap_after_every_macos_build():
    wf = (ROOT / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")
    job = wf.split("\n  homebrew:\n", 1)[1]
    assert "needs: build" in job
    assert "!inputs.dry_run" in job
    assert "scripts/update_homebrew_tap.py" in job
    assert "secrets.HOMEBREW_TAP_DEPLOY_KEY" in job
    # the script from the workflow's own commit: an older tag lacks it
    assert "ref: ${{ github.sha }}" in job
    # read-only token: the job writes to the tap only, with the deploy key
    assert "permissions:\n      contents: read" in job
    # a push lost to another release starts again from the tap as it is
    assert "for attempt in" in job and "reset -q --hard FETCH_HEAD" in job
    # the key is never echoed, and the host key is pinned
    assert "echo \"$DEPLOY_KEY" not in job and "set -x" not in job
    assert "StrictHostKeyChecking=yes" in job and "ssh-keyscan -t" not in job
    assert "rm -f ~/.ssh/tap_key" in job


def test_the_tap_job_downloads_the_dmgs_the_build_uploads():
    """The names the homebrew job downloads are the names the build uploads."""
    wf = (ROOT / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")
    build, job = wf.split("\n  homebrew:\n", 1)
    assert "artifact: ChromIQ-macOS-arm64.dmg" in build
    assert 'VERSIONED="${ART%.dmg}_${RELEASE_TAG}.dmg"' in build
    assert 'X86_VERSIONED="ChromIQ-macOS-x86_64_${RELEASE_TAG}.dmg"' in build
    # the Homebrew copy of each, which is the file the cask downloads
    assert '-p "ChromIQ-macOS-${a}_${RELEASE_TAG}_homebrew.dmg"' in job
    assert '/tmp/dmg/ChromIQ-macOS-arm64_${RELEASE_TAG}_homebrew.dmg' in job
    assert '/tmp/dmg/ChromIQ-macOS-x86_64_${RELEASE_TAG}_homebrew.dmg' in job
    assert '_${RELEASE_TAG}.dmg"' not in job
    assert "for a in arm64 x86_64" in job
    # and the casks the script writes ask for the same files
    for name in ("chromiq.rb", "chromiq@beta.rb"):
        cask = (DATA / name).read_text(encoding="utf-8")
        assert 'arch arm: "arm64", intel: "x86_64"' in cask
        written = tap.rewrite_cask(cask, "9.9.9", ARM, INTEL)
        assert "ChromIQ-macOS-#{arch}_v#{version}_homebrew.dmg" in written


def _upload_step(wf: str) -> str:
    return wf.split("- name: Upload DMG(s) to release", 1)[1].split("\n  homebrew:\n", 1)[0]


def test_the_build_uploads_a_homebrew_copy_of_both_dmgs_the_casks_use():
    """Same bytes under a second name: the checksum the tap carries holds."""
    wf = (ROOT / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")
    step = _upload_step(wf)
    assert ('for HB_SRC in "ChromIQ-macOS-arm64_${RELEASE_TAG}.dmg" '
            '"ChromIQ-macOS-x86_64_${RELEASE_TAG}.dmg"') in step
    assert 'HB_COPY="${HB_SRC%.dmg}_homebrew.dmg"' in step
    # a byte copy, never a rebuild or a second convert
    assert 'cp "$HB_SRC" "$HB_COPY"' in step
    assert 'gh release upload "$RELEASE_TAG" "$HB_COPY" --clobber' in step
    # the copies are made after both normal DMGs are in place
    assert step.index('mv "ChromIQ-macOS-x86_64.dmg"') < step.index("HB_SRC")
    # the universal DMG has no Homebrew copy: the casks never use it
    assert "universal_${RELEASE_TAG}_homebrew" not in wf


def test_the_casks_on_the_tap_stay_on_the_plain_names_until_a_new_release():
    """4.3.2 and 4.3.3-beta.16 have no _homebrew files: the tap's casks (the
    fixtures are copies of them) must still download the normal DMG."""
    for name in ("chromiq.rb", "chromiq@beta.rb"):
        cask = (DATA / name).read_text(encoding="utf-8")
        assert "ChromIQ-macOS-#{arch}_v#{version}.dmg" in cask
        assert "_homebrew" not in cask


def test_writing_a_new_version_moves_the_url_to_the_homebrew_copy(tmp_path):
    t = _tap(tmp_path)
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9",
                     "--arm-sha", ARM, "--intel-sha", INTEL]) == 0
    for name in ("chromiq.rb", "chromiq@beta.rb"):
        text = (t / "Casks" / name).read_text(encoding="utf-8")
        urls = [l.strip() for l in text.splitlines() if l.strip().startswith('url "https') and "/download/" in l]
        assert urls == ['url "https://github.com/itsab1989/ChromIQ/releases/download/'
                        'v#{version}/ChromIQ-macOS-#{arch}_v#{version}_homebrew.dmg"']
        # the livecheck url is not the download url and is left alone
        orig = (DATA / name).read_text(encoding="utf-8")
        assert text.count("url ") == orig.count("url ")


def test_a_cask_already_on_the_homebrew_copy_is_rewritten_unchanged(tmp_path):
    """The second release after the switch, and a re-run of the first."""
    t = _tap(tmp_path)
    args = ["--arm-sha", ARM, "--intel-sha", INTEL]
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9", *args]) == 0
    once = {f.name: f.read_text(encoding="utf-8") for f in (t / "Casks").iterdir()}
    assert tap.main(["--tap", str(t), "--tag", "v9.9.9", *args]) == 0
    assert {f.name: f.read_text(encoding="utf-8") for f in (t / "Casks").iterdir()} == once
    assert tap.main(["--tap", str(t), "--tag", "v9.9.10", *args]) == 0
    for text in ((t / "Casks" / n).read_text(encoding="utf-8") for n in once):
        assert text.count("_homebrew.dmg") == 1 and "_homebrew_homebrew" not in text


def test_a_cask_whose_url_the_script_does_not_know_is_refused():
    cask = (DATA / "chromiq.rb").read_text(encoding="utf-8")
    moved = cask.replace("ChromIQ-macOS-#{arch}_v#{version}.dmg",
                         "ChromIQ-#{arch}-#{version}.dmg")
    with pytest.raises(ValueError, match="url"):
        tap.rewrite_cask(moved, "9.9.9", ARM, INTEL)


def test_the_release_note_points_people_at_the_normal_dmg():
    wf = (ROOT / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")
    line = next(l for l in wf.splitlines() if "_homebrew.dmg`" in l and "printf" in l)
    assert "Homebrew downloads" in line and "normal DMG" in line
    assert "\u2014" not in line  # no em dash in new user-facing text
    # it is part of the note the release is created with
    notes = wf.split("} > /tmp/release_notes.txt", 1)[0]
    assert line in notes


@pytest.mark.parametrize("doc", [
    "README.md", "docs/index.html", ".github/workflows/build-release.yml"])
def test_the_homebrew_install_is_explained_where_people_look(doc):
    """README, the web page and the macOS release note name both casks."""
    text = (ROOT / doc).read_text(encoding="utf-8")
    assert "brew install --cask itsab1989/chromiq/chromiq\n" in text \
        or "brew install --cask itsab1989/chromiq/chromiq<" in text \
        or "brew install --cask itsab1989/chromiq/chromiq`" in text
    assert "brew install --cask itsab1989/chromiq/chromiq@beta" in text
    assert "brew.sh" in text


def test_the_readme_explains_switching_uninstalling_and_an_existing_app():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("#### Install with Homebrew", 1)[1].split("#### Install by hand", 1)[0]
    for needle in ("brew upgrade --cask chromiq",
                   "brew uninstall --cask chromiq@beta",
                   "brew uninstall --zap --cask chromiq",
                   "~/ChromIQ", "argyll-cms", "quarantine",
                   "already an App at", "--force"):
        assert needle in section, needle
    # the manual route is still there
    assert "ChromIQ-macOS-universal_<version>.dmg" in readme
