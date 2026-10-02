"""An inspection is never offered a folder nobody may write to (P-INS-1).

Review P_review2_beta1, 2026-10-02: "Inspect a profile" on a profile inside a
printer driver's bundle (``/Library/Printers/<maker>/…/Contents/Resources``,
owned by root) is outside any ChromIQ project, so the save chooser opened in
that folder and every Save failed with the error banner. Such a folder now gets
the fallback the ColorSync folders already had: the user's ChromIQ folder.

And both Inspect windows' button says what it saves, an inspection (P-INS-3):
it read "Save report…", which is the Measurement Report's word.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from ui.inspection_save import save_inspection

REPO = Path(__file__).resolve().parent.parent


def _ask_recorder(seen: dict):
    def ask(_parent, _title, _filter, *, start_path, extra_paths=()):
        seen["start"] = Path(start_path)
        return ""                       # cancel: only the offer is under test
    return ask


def _save(src: Path, fallback: Path) -> Path:
    seen: dict = {}
    save_inspection(None, src, "Profile inspection", "head", ["body"],
                    dialog_title="t", subject_line="s",
                    ask=_ask_recorder(seen), fallback_dir=fallback)
    return seen["start"].parent


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0,
                    reason="needs POSIX permissions and a non-root user")
def test_an_unwritable_folder_outside_a_project_falls_back(tmp_path):
    bundle = tmp_path / "Printers" / "EPSON" / "Resources"
    bundle.mkdir(parents=True)
    icc = bundle / "Epson-Pro.icc"
    icc.write_bytes(b"not really a profile")
    home = tmp_path / "ChromIQ"
    home.mkdir()
    bundle.chmod(stat.S_IRUSR | stat.S_IXUSR)       # r-x: like root's folder
    try:
        assert _save(icc, home) == home
        assert sorted(p.name for p in bundle.iterdir()) == ["Epson-Pro.icc"]
    finally:
        bundle.chmod(stat.S_IRWXU)


def test_a_writable_folder_outside_a_project_is_still_used(tmp_path):
    """The rule from Knut (#182 5944210498) is unchanged: beside the file."""
    folder = tmp_path / "Downloads"
    folder.mkdir()
    icc = folder / "mine.icc"
    icc.write_bytes(b"x")
    home = tmp_path / "ChromIQ"
    home.mkdir()
    assert _save(icc, home) == folder


@pytest.mark.parametrize("dialog", ["profile_info_dialog.py", "ti3_info_dialog.py"])
def test_the_inspect_button_says_inspection(dialog):
    src = (REPO / "ui" / "dialogs" / dialog).read_text(encoding="utf-8")
    assert 'QPushButton(tr("Save inspection…"), self)' in src
    assert 'tr("Save report…")' not in src
