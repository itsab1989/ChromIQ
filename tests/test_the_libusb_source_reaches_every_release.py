"""The LGPL source offer for the bundled libusb reaches every release.

Review of 4.3.58-a: the note lived only in the macOS job's "create release"
template, but the Linux and Windows jobs create the same release from their
own templates and won that race on v4.3.55, v4.3.56 and v4.3.57, so the note
never appeared. And both macOS legs uploaded the tarball with --clobber
(delete, then upload), which can collide and fail a leg before its DMG and
Homebrew uploads. These tests keep ONE step, on ONE leg, after the uploads,
that attaches the tarball and adds the note only when it is missing.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
TARBALL = "libusb-1.0.30.tar.bz2"
SHA = "fea36f34f9156400209595e300840767ab1a385ede1dc7ee893015aea9c6dbaf"


def _steps():
    d = yaml.safe_load((WF / "build-release.yml").read_text(encoding="utf-8"))
    return d["jobs"]["build"]["steps"]


def test_the_tarball_is_checked_against_its_sha_before_any_upload():
    steps = _steps()
    names = [s.get("name", "") for s in steps]
    fetch = next(i for i, s in enumerate(steps)
                 if SHA in s.get("run", "") and "shasum -a 256 -c" in s["run"])
    first_upload = next(i for i, s in enumerate(steps)
                        if "gh release upload" in s.get("run", ""))
    create = names.index("Create GitHub Release (if not exists)")
    assert fetch < create < first_upload


def test_exactly_one_step_on_one_leg_uploads_it_after_the_dmgs():
    steps = _steps()
    up = [i for i, s in enumerate(steps)
          if "gh release upload" in s.get("run", "")
          and ("LIBUSB_TARBALL" in s["run"] or TARBALL in s["run"])]
    assert len(up) == 1, "the libusb tarball must be uploaded from one step"
    step = steps[up[0]]
    assert "matrix.arch == 'universal2'" in step["if"]
    assert "!inputs.dry_run" in step["if"]
    dmg = next(i for i, s in enumerate(steps) if s.get("name") == "Upload DMG(s) to release")
    assert up[0] > dmg, "it must run after the DMG and Homebrew uploads"
    assert TARBALL not in steps[dmg]["run"]


def test_the_note_is_added_whoever_created_the_release_and_only_once():
    step = next(s for s in _steps()
                if "gh release edit" in s.get("run", ""))
    run = step["run"]
    assert "gh release view" in run and "--json body" in run
    assert 'grep -qF "Source of libusb (LGPL)"' in run
    assert "--notes-file" in run
    assert "ChromIQ includes libusb 1.0.30" in run
    # "now" would read wrong from the next release on.
    assert "now includes" not in (WF / "build-release.yml").read_text(encoding="utf-8")


def test_no_create_template_carries_its_own_copy_of_the_note():
    for wf in ("build-release.yml", "build-linux.yml", "build-windows.yml"):
        text = (WF / wf).read_text(encoding="utf-8")
        assert text.count("Source of libusb (LGPL)") == (2 if wf == "build-release.yml" else 0), wf
