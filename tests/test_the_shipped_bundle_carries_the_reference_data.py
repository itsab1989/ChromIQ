"""The reference data must work from a FROZEN BUNDLE, not just this checkout.

Sebastian, 2026-09-20: *"all of this must work in the bundled releases users can
download from github on all supported operating systems."*

Everything proved about the Fogra reference sets so far was measured by running
from the repository, where `resource_path` falls back to the project root and
every file is simply there. A downloaded `.dmg`, `.exe` or AppImage resolves the
same call into PyInstaller's extraction directory, and two different faults live
in that gap:

* **The read.** `workflow.reference_sets` opens `data/reference_sets/fogra`
  through `resource_path`, so a build that does not carry that folder finds no
  sets and says nothing. `tests/test_the_three_specs_bundle_the_same_data.py`
  already proves all three specs name the folder; what it cannot prove is that
  the path the loader builds out of `sys._MEIPASS` lands on it. These tests do,
  by staging an extraction directory and pointing `_MEIPASS` at it.

* **The write, which is the worse one.** `sys._MEIPASS` is a TEMPORARY
  directory. A onefile build extracts it on launch and deletes it on exit, so a
  user's own Fogra file written anywhere inside it is gone at the next start,
  and the window would say "your copy" until the app was closed. The user's
  folder must resolve somewhere the operating system keeps, and must keep
  resolving there while frozen.

Neither test needs PyInstaller, so both run on every platform in the ordinary
gate, which is the only way Windows and Linux are covered at all from here.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def frozen(tmp_path, monkeypatch):
    """A staged extraction directory, with `sys._MEIPASS` pointing at it.

    Only what a spec declares is copied, and it is copied to the destination
    the spec declares, so the layout under test is the shipped one and not this
    repository's.
    """
    meipass = tmp_path / "meipass"
    shutil.copytree(ROOT / "data" / "reference_sets",
                    meipass / "data" / "reference_sets")
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    from workflow import reference_sets as RS
    RS.reset_cache()
    yield meipass
    RS.reset_cache()


def test_a_frozen_build_finds_the_reference_sets_it_ships(frozen):
    """The eleven sets load out of the extraction directory, intact.

    `verify_unmodified` is the interesting half. Fogra's permission to
    redistribute is conditional on the data travelling unmodified, so a build
    whose copy does not match the sha256 in `SOURCE.json` is a build we may not
    ship, and the check has to be possible from inside the bundle: that means
    `SOURCE.json` must travel too, which a folder-level `datas` entry gives and
    a file-by-file one would be able to miss.

    MUTATION, proven to land: make `resource_path` ignore `sys._MEIPASS` and
    every set comes back rooted in the checkout, failing the containment check.
    """
    from workflow import reference_sets as RS

    sets = RS.bundled()
    assert len(sets) == 11, f"a frozen build found {len(sets)} sets, not 11"
    for s in sets:
        assert str(s.path).startswith(str(frozen)), (
            f"{s.id} was read from {s.path}, which is outside the bundle: the "
            "test is measuring this checkout and proves nothing about a build")
        assert s.path.is_file(), f"{s.id} names a file the bundle does not hold"
        assert RS.verify_unmodified(s), (
            f"{s.id} does not match the sha256 SOURCE.json records for it, so "
            "this build alters data we are only allowed to pass on unchanged")


def test_a_frozen_build_can_read_the_aims_out_of_its_own_copy(frozen):
    """Finding the file is not the same as being able to use it.

    A bundle can carry a file that the loader then cannot parse, most obviously
    when a packaging step rewrites line endings: every Fogra file measured here
    is CRLF, and a build tool that normalises text would leave the file present,
    the sha256 wrong, and `BEGIN_DATA` unfindable.

    MUTATION, proven to land: truncate the staged FOGRA51 file to its header and
    the aim count goes to zero.
    """
    from workflow import reference_sets as RS

    s = RS.by_id("FOGRA51")
    assert s is not None, "a frozen build does not know FOGRA51"
    aims = RS.read_aims(s)
    assert len(aims) > 50, (
        f"FOGRA51 yielded {len(aims)} aim colours from the bundle; the Media "
        "Wedge 3 subset holds 72")


def test_a_users_own_file_is_never_written_inside_the_bundle(frozen):
    """`sys._MEIPASS` is temporary. Anything kept there is lost on restart.

    This is the fault that would not show up in any session: the user installs
    a newer Fogra file, the window says "your copy", every verification that
    evening uses it, and the next launch silently reverts to what shipped.

    MUTATION, proven to land: point `reference_sets_dir` at
    `resource_path("data/reference_sets/user")` and this goes red.
    """
    from core.platform_paths import compliance_dir, reference_sets_dir
    from workflow import reference_sets as RS

    for name, where in (("reference_sets_dir", reference_sets_dir()),
                        ("compliance_dir", compliance_dir()),
                        ("user_dir", RS.user_dir())):
        assert not str(where.resolve()).startswith(str(frozen.resolve())), (
            f"{name} resolves to {where}, inside the extraction directory a "
            "frozen build deletes when it exits")


def test_the_users_folder_is_a_place_each_operating_system_keeps(monkeypatch,
                                                                 tmp_path):
    """And it is the platform's own configuration location on all three.

    Read here rather than taken on trust, because this is the half of
    Sebastian's requirement that cannot be driven from a Mac: Windows and Linux
    only ever get the answer a test gives them.

    MUTATION, proven to land: return `Path.home() / ".chromiq"` unconditionally
    from `presets_dir` and two of the three branches go red.
    """
    import core.platform_paths as PP

    monkeypatch.delenv("CHROMIQ_PRESETS_DIR", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    cases = (
        ("windows", {"APPDATA": str(home / "AppData" / "Roaming")},
         home / "AppData" / "Roaming" / "ChromIQ"),
        ("macos", {}, home / "Library" / "Preferences" / "ChromIQ"),
        ("linux", {"XDG_CONFIG_HOME": str(home / ".config")},
         home / ".config" / "ChromIQ"),
    )
    for platform, env, expected in cases:
        monkeypatch.setattr(PP, "is_windows", lambda p=platform: p == "windows")
        monkeypatch.setattr(PP, "is_macos", lambda p=platform: p == "macos")
        for k in ("APPDATA", "XDG_CONFIG_HOME"):
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        got = PP.reference_sets_dir()
        assert got == expected / "reference_sets", (
            f"on {platform} a user's own reference files would go to {got}")
