"""The scanner profile's file name and the description inside it — beta 8, B8-13.

Knut, beta.7: with "Profile description (-D)" left EMPTY and a scan called
``ScannedIT8LSTarget01.tif`` he got the file
``ScannedIT8LSTarget01-p1s1-scanner.icc`` and the embedded description
``ScannedIT8LSTarget01 scanner``. *"They should at least be the same."*

Reproduced in the real window (AGENT-I, 2026-09-03), and the divergence is
bigger than the report: with ``-D`` FILLED the ``-p1s1-scanner`` segment does not
appear in the file name at all. Which of two naming schemes a user got depended
on whether one text box was empty.

| ``-D`` | ICC written | description inside it |
|---|---|---|
| empty (before) | ``ScannedIT8LSTarget01-p1s1-scanner.icc`` | ``ScannedIT8LSTarget01 scanner`` |
| filled (before) | ``<what was typed>.icc`` | ``<what was typed>`` |

Two code sites in `ui/dialogs/scanin_dialog.py` started from the same
``base.name`` and then went their own ways: the ``.ti3`` scanin was told to write
(colprof names the ``.icc`` after it) and the ``desc`` handed to colprof.

``p`` is a page and ``s`` a shot — one of several scans of one page, used when
averaging. With one page and one shot it is always literally ``p1s1``, it
disambiguates nothing, and it appears in no tooltip, help text or log line. It
now stays where it does its job and is gone where it never did.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication      # noqa: E402

from tests.test_scanin_dialog import _FakeSettings, _dialog, _it8   # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("b813-out")


def _standard_dialog(_app, _out_dir, tmp_path, scan_name):
    if _it8() is None:
        pytest.skip("Argyll ref/ not present")
    dlg = _dialog(_app, _out_dir)
    dlg._mode_standard.setChecked(True)
    dlg._set_std_targets([_it8()])
    ref = tmp_path / "ref.txt"
    ref.write_text("x", encoding="utf-8")
    dlg._std_ref = ref
    scan = tmp_path / scan_name
    scan.write_bytes(b"II*\0")
    dlg._cur_shot()["path"] = scan
    dlg._cur_shot()["corners"] = [(0, 0), (9, 0), (9, 9), (0, 9)]
    dlg._run_job = lambda i: None
    return dlg, scan


def test_one_scan_of_one_page_writes_no_p1s1_anywhere(_app, _out_dir, tmp_path):
    dlg, scan = _standard_dialog(_app, _out_dir, tmp_path,
                                 "ScannedIT8LSTarget01.tif")
    try:
        dlg._execute()
        read = dlg._jobs[0]["params"].out_ti3
        assert read.name == "ScannedIT8LSTarget01 scanner.ti3", read.name
        assert "p1s1" not in read.name
    finally:
        dlg.deleteLater()


def test_the_file_and_the_description_are_the_same_string(_app, _out_dir,
                                                          tmp_path):
    """What colprof is handed is what ends up inside the profile."""
    dlg, scan = _standard_dialog(_app, _out_dir, tmp_path,
                                 "ScannedIT8LSTarget01.tif")
    try:
        base = scan.parent / scan.stem
        default = dlg._default_profile_name(base)
        assert default == "ScannedIT8LSTarget01 scanner"
        combined = scan.parent / f"{default}.ti3"
        combined.write_text("CTI3\n", encoding="utf-8")
        ti3, desc = dlg._apply_profile_name(combined, default)
        # colprof writes <ti3 stem>.icc, so this IS the file name.
        assert ti3.stem == desc == default
    finally:
        dlg.deleteLater()


def test_several_shots_keep_the_suffix_that_disambiguates_them(_app, _out_dir,
                                                               tmp_path):
    """Two scans of one page still get separate reads — that is what p/s is for."""
    dlg, scan = _standard_dialog(_app, _out_dir, tmp_path, "T.tif")
    try:
        second = tmp_path / "T2.tif"
        second.write_bytes(b"II*\0")
        dlg._add_shot()
        dlg._cur_shot()["path"] = second
        dlg._cur_shot()["corners"] = [(0, 0), (9, 0), (9, 9), (0, 9)]
        dlg._execute()
        reads = [j["params"].out_ti3.name for j in dlg._jobs
                 if j["kind"] == "scanin"]
        assert reads == ["T-p1s1-scanner.ti3", "T-p1s2-scanner.ti3"], reads
        # …and the profile they feed still carries one name.
        assert dlg._default_profile_name(scan.parent / scan.stem) == "T scanner"
    finally:
        dlg.deleteLater()


def test_a_typed_name_still_wins(_app, _out_dir, tmp_path):
    dlg = _dialog(_app, _out_dir)
    try:
        src = tmp_path / "whatever.ti3"
        src.write_text("CTI3\n", encoding="utf-8")
        dlg._prof_name.setText("Epson ET-8550 scanner")
        ti3, desc = dlg._apply_profile_name(src, "whatever scanner")
        assert ti3.name == "Epson ET-8550 scanner.ti3"
        assert desc == "Epson ET-8550 scanner"
    finally:
        dlg.deleteLater()


def test_the_default_name_is_filesystem_safe(_app, _out_dir):
    """A scan file name can carry a character the stem must not."""
    dlg = _dialog(_app, _out_dir)
    try:
        got = dlg._default_profile_name(Path("/x") / 'we:ird"scan')
        for ch in ':"/\\|?*':
            assert ch not in got, got
        assert got.endswith("scanner")
    finally:
        dlg.deleteLater()


def test_a_profile_about_to_be_replaced_is_still_archived_under_the_new_name(
        _app, _out_dir, tmp_path):
    """NEVER DESTROY USER WORK. The stem the archiver protects has to be the
    stem the build is about to write, or a rebuild would overwrite a profile
    the user may already have installed.

    The read here is ``T-p1-avg.ti3`` — the real shape when a page was scanned
    twice and averaged — precisely because its stem is NOT the profile's name.
    Reading the stem off the ``.ti3``, which is what the archiver did before,
    would look for ``T-p1-avg.icc``, find nothing, archive nothing, and let
    colprof write straight over ``T scanner.icc``."""
    dlg = _dialog(_app, _out_dir)
    try:
        folder = tmp_path / "run"
        folder.mkdir()
        read = folder / "T-p1-avg.ti3"
        read.write_text("CTI3\n", encoding="utf-8")
        doomed = folder / "T scanner.icc"
        doomed.write_bytes(b"x" * 2000)
        dest = dlg._archive_previous_profile(read, "T scanner")
        assert dest is not None and dest.is_dir(), \
            "nothing was archived, so the build is about to overwrite in place"
        assert not doomed.exists(), \
            "the profile being replaced was left to be overwritten"
        assert (dest / "T scanner.icc").is_file()
        assert read.is_file(), "this build's own input must not be archived"
    finally:
        dlg.deleteLater()
