"""Tests for the .ti2 instrument-detection helpers used by auto -B selection.

The Measure tab decides whether to disable bidirectional strip recognition
(chartread -B) from the chart's TARGET_INSTRUMENT. Verified against real files:
the i1 Pro family (i1 Pro / Pro 2 / Pro 3 / Pro 3+) is all tagged
"GretagMacbeth i1 Pro" and reads both directions; the ColorMunki (and its
i1Studio rebrand) is tagged "X-Rite ColorMunki" and reads one direction only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ui.ti2_loader import (
    KNOWN_INSTRUMENTS,
    _copy_files,
    _copy_ti3_only,
    _project_root_for,
    _related_files,
    disable_bidir_for_instrument,
    force_bidir_for_instrument,
    has_spectral_data,
    instrument_label,
    is_colormunki,
    is_i1pro,
    is_randomized,
    is_spectroscan,
    read_target_instrument,
)


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "chart.ti2"
    p.write_text(body, encoding="utf-8")
    return p


def test_read_target_instrument_i1pro(tmp_path: Path) -> None:
    p = _write(tmp_path, 'CTI2\nKEYWORD "TARGET_INSTRUMENT"\nTARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n')
    assert read_target_instrument(p) == "GretagMacbeth i1 Pro"


def test_read_target_instrument_colormunki(tmp_path: Path) -> None:
    p = _write(tmp_path, 'TARGET_INSTRUMENT "X-Rite ColorMunki"\n')
    assert read_target_instrument(p) == "X-Rite ColorMunki"


def test_read_target_instrument_missing_keyword(tmp_path: Path) -> None:
    p = _write(tmp_path, "CTI2\nNUMBER_OF_SETS 100\n")
    assert read_target_instrument(p) is None


def test_read_target_instrument_missing_file(tmp_path: Path) -> None:
    assert read_target_instrument(tmp_path / "nope.ti2") is None


@pytest.mark.parametrize(
    "name",
    [
        "GretagMacbeth i1 Pro",   # i1 Pro / Pro 2 / Pro 3 / Pro 3+
        "X-Rite i1 Pro 3",        # robust to alternate spellings
        "X-Rite ColorMunki",      # now left on the Argyll default, not forced -B
        "ColorMunki Photo",
        "GretagMacbeth SpectroScan",
        None,                     # unknown / no file -> Argyll default
        "",
    ],
)
def test_disable_bidir_for_instrument(name) -> None:
    # No instrument auto-selects -B any more; the ColorMunki now falls back to
    # the Argyll default like everything else (Auto can still be overridden by
    # picking "Bidirectional disabled" manually).
    assert disable_bidir_for_instrument(name) is False


@pytest.mark.parametrize(
    "name, expected",
    [
        ("X-Rite ColorMunki", True),
        ("colormunki photo", True),        # case-insensitive substring match
        ("GretagMacbeth i1 Pro", False),
        ("GretagMacbeth SpectroScan", False),
        (None, False),
        ("", False),
    ],
)
def test_is_colormunki(name, expected) -> None:
    assert is_colormunki(name) is expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("GretagMacbeth SpectroScan", True),
        ("spectroscan", True),             # case-insensitive substring match
        ("X-Rite ColorMunki", False),
        ("GretagMacbeth i1 Pro", False),
        (None, False),
        ("", False),
    ],
)
def test_is_spectroscan(name, expected) -> None:
    assert is_spectroscan(name) is expected


def test_disable_bidir_never_auto_selected() -> None:
    # The Auto toggle never disables bidirectional reading on its own — even
    # for the ColorMunki, which now stays on the Argyll default.
    for name in (*KNOWN_INSTRUMENTS, None, "", "Unknown device"):
        assert disable_bidir_for_instrument(name) is False


@pytest.mark.parametrize(
    "name, expected",
    [
        ("GretagMacbeth i1 Pro", True),    # i1 Pro / Pro 2 / Pro 3 / Pro 3+
        ("X-Rite i1 Pro 3", True),         # robust to alternate spellings
        ("i1pro2", True),                  # no-space spelling
        ("X-Rite ColorMunki", False),
        ("GretagMacbeth SpectroScan", False),
        (None, False),
        ("", False),
    ],
)
def test_is_i1pro(name, expected) -> None:
    assert is_i1pro(name) is expected


@pytest.mark.parametrize(
    "name, expected",
    [
        ("GretagMacbeth i1 Pro", True),    # i1 Pro family forces bidir (-b)
        ("X-Rite i1 Pro 3", True),
        ("X-Rite ColorMunki", False),      # one direction only -> never force
        ("GretagMacbeth SpectroScan", False),
        (None, False),
        ("", False),
    ],
)
def test_force_bidir_for_instrument(name, expected) -> None:
    assert force_bidir_for_instrument(name) is expected


def test_force_and_disable_bidir_mutually_exclusive() -> None:
    # -b and -B can never both apply to the same instrument: chartread treats
    # them as mutually exclusive, so the two detectors must never both be True.
    for name in (*KNOWN_INSTRUMENTS, None, "", "Unknown device", "i1pro3"):
        assert not (force_bidir_for_instrument(name) and disable_bidir_for_instrument(name))


def test_force_bidir_delegates_to_is_i1pro() -> None:
    for name in (*KNOWN_INSTRUMENTS, None, "", "Unknown device"):
        assert force_bidir_for_instrument(name) is is_i1pro(name)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("X-Rite ColorMunki", "ColorMunki / i1Studio / CCStudio"),
        ("ColorMunki Photo", "ColorMunki / i1Studio / CCStudio"),
        ("GretagMacbeth i1 Pro", "i1Pro / i1Pro2 / i1Pro3(+)"),
        ("X-Rite i1Pro3", "i1Pro / i1Pro2 / i1Pro3(+)"),
        # SpectroScan and unknowns are shown unchanged.
        ("GretagMacbeth SpectroScan", "GretagMacbeth SpectroScan"),
        ("Some Other Device", "Some Other Device"),
        (None, None),
        ("", None),
    ],
)
def test_instrument_label(name, expected) -> None:
    assert instrument_label(name) == expected


def test_known_instruments_registry() -> None:
    assert KNOWN_INSTRUMENTS == (
        "X-Rite ColorMunki",
        "GretagMacbeth i1 Pro",
        "GretagMacbeth SpectroScan",
        # #159: the CR30 is ChromIQ's own — stock ArgyllCMS chartread does not
        # know this name and refuses the chart, which is why
        # TabMeasure._blocked_by_stock_chartread_for_cr30 exists.
        "CR30",
    )


def test_read_target_instrument_works_on_ti3(tmp_path: Path) -> None:
    p = tmp_path / "measured.ti3"
    p.write_text('CTI3\nTARGET_INSTRUMENT "GretagMacbeth SpectroScan"\n', encoding="utf-8")
    assert read_target_instrument(p) == "GretagMacbeth SpectroScan"


def test_is_randomized_random_start(tmp_path: Path) -> None:
    p = _write(tmp_path, 'CTI2\nRANDOM_START "7"\nBEGIN_DATA\n')
    assert is_randomized(p) is True


def test_is_randomized_chart_id(tmp_path: Path) -> None:
    # printtarg -r writes CHART_ID instead of RANDOM_START → fixed order.
    p = _write(tmp_path, 'CTI2\nCHART_ID "2"\nBEGIN_DATA\n')
    assert is_randomized(p) is False


def test_is_randomized_missing_file_defaults_true(tmp_path: Path) -> None:
    # A missing/unreadable file is treated as randomised so callers don't warn.
    assert is_randomized(tmp_path / "nope.ti2") is True


def test_has_spectral_data_present(tmp_path: Path) -> None:
    p = _write(tmp_path, 'CTI3\nSPECTRAL_BANDS "36"\nSPECTRAL_START_NM "380.0"\n')
    assert has_spectral_data(p) is True


def test_has_spectral_data_absent(tmp_path: Path) -> None:
    p = _write(tmp_path, "CTI3\nNUMBER_OF_SETS 100\n")
    assert has_spectral_data(p) is False


def test_has_spectral_data_zero_bands(tmp_path: Path) -> None:
    p = _write(tmp_path, 'CTI3\nSPECTRAL_BANDS "0"\n')
    assert has_spectral_data(p) is False


def test_has_spectral_data_missing_file(tmp_path: Path) -> None:
    assert has_spectral_data(tmp_path / "nope.ti3") is False


def test_related_files_dedupes_case_insensitive_glob(tmp_path: Path) -> None:
    """A single chart TIFF must appear once when loading an existing target.

    Regression guard for forum #148275's "Page 1/2 and 2/2 (same)" symptom:
    pathlib.Path.glob is case-insensitive on Windows, so the prior code's
    sorted([*glob('*.tif'), *glob('*.TIF'), *glob('*.tiff')]) returned the
    same file two or three times, doubling the page count in the preview.
    (On case-sensitive filesystems this passes trivially; it bites on Windows,
    which is where the bug was reported.)
    """
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text('TARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n', encoding="utf-8")
    (tmp_path / "chart.tif").write_bytes(b"II*\x00")  # one-page chart

    _, tiffs = _related_files(ti2)

    assert len(tiffs) == 1, f"expected 1 TIFF, got {len(tiffs)}: {tiffs}"
    resolved = [p.resolve() for p in tiffs]
    assert len(resolved) == len(set(resolved)), f"duplicate paths returned: {tiffs}"


def test_related_files_finds_tiff_extension(tmp_path: Path) -> None:
    """The dedup must not drop the legitimate .tiff extension variant."""
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    (tmp_path / "chart.tiff").write_bytes(b"II*\x00")

    _, tiffs = _related_files(ti2)

    assert [p.name for p in tiffs] == ["chart.tiff"]


# ---------------------------------------------------------------------------
# Importing external charts → per-run project layout
# ---------------------------------------------------------------------------

def test_copy_files_builds_project_layout(tmp_path: Path) -> None:
    """Importing an external .ti2 must produce a real project, not flat files.

    runs/run1/chart.* + project.json, with the originals renamed to the
    canonical chart stem (see docs/dev_folder_layout.md).
    """
    src = tmp_path / "external"
    src.mkdir()
    (src / "MyOldChart.ti2").write_text("CTI2\n")
    (src / "MyOldChart.ti1").write_text("CTI1\n")
    (src / "MyOldChart_01.tif").write_bytes(b"II*\x00")
    (src / "MyOldChart_02.tif").write_bytes(b"II*\x00")
    (src / "MyOldChart.ti3").write_text("CTI3\n")
    (src / "MyOldChart.cht").write_text("cht\n")
    (src / "MyOldChart.channels.json").write_text('{"ink_channels": ["r","g","b"]}')

    _, tiffs = _related_files(src / "MyOldChart.ti2")
    working_dir = tmp_path / "ChromIQ"
    new_ti2, new_tiffs = _copy_files(
        src / "MyOldChart.ti2", src / "MyOldChart.ti1", tiffs,
        working_dir, "Imported",
    )

    proj = working_dir / "Imported"
    run1 = proj / "runs" / "run1"
    assert (proj / "project.json").is_file()
    # Files take the project-name stem ("Imported" here).
    assert new_ti2 == run1 / "Imported.ti2"
    assert (run1 / "Imported.ti2").is_file()
    assert (run1 / "Imported.ti1").is_file()
    assert (run1 / "Imported.ti3").is_file()        # measurement
    assert (run1 / "Imported.cht").is_file()
    assert (run1 / "Imported.channels.json").is_file()
    assert [p.name for p in new_tiffs] == ["Imported_01.tif", "Imported_02.tif"]
    # No flat <name>.ti2 left at the project root.
    assert not (proj / "Imported.ti2").exists() or (proj / "Imported.ti2").parent == run1


def test_copy_files_imports_icc_under_project_stem(tmp_path: Path) -> None:
    src = tmp_path / "external"
    src.mkdir()
    (src / "old.ti2").write_text("CTI2\n")
    (src / "old.icc").write_text("ICC\n")

    working_dir = tmp_path / "ChromIQ"
    _copy_files(src / "old.ti2", None, [], working_dir, "Imported")

    assert (working_dir / "Imported" / "runs" / "run1" / "Imported.icc").read_text() == "ICC\n"


def test_copy_files_sanitises_spaces_in_project_name(tmp_path: Path) -> None:
    """Importing with a spaced name yields a hyphenated project folder and
    chart stem, matching what the Generate-Chart path does."""
    src = tmp_path / "external"
    src.mkdir()
    (src / "old.ti2").write_text("CTI2\n")

    working_dir = tmp_path / "ChromIQ"
    new_ti2, _ = _copy_files(src / "old.ti2", None, [], working_dir, "printer test file")

    proj = working_dir / "printer-test-file"
    assert proj.is_dir() and not (working_dir / "printer test file").exists()
    assert new_ti2 == proj / "runs" / "run1" / "printer-test-file.ti2"


def test_project_root_for_recognises_structured_chart(tmp_path: Path) -> None:
    """A chart already inside a project run folder is 'inside' (no re-import)."""
    from core.file_manager import Project
    working_dir = tmp_path / "ChromIQ"
    proj = Project.create(working_dir / "Existing", "Existing")
    chart_ti2 = proj.current_run().chart_ti2
    chart_ti2.parent.mkdir(parents=True, exist_ok=True)
    chart_ti2.write_text("CTI2\n")

    assert _project_root_for(chart_ti2, working_dir) == working_dir / "Existing"


def test_project_root_for_rejects_external_file(tmp_path: Path) -> None:
    working_dir = tmp_path / "ChromIQ"
    working_dir.mkdir()
    external = tmp_path / "somewhere" / "chart.ti2"
    external.parent.mkdir(parents=True)
    external.write_text("CTI2\n")

    assert _project_root_for(external, working_dir) is None


def test_project_root_for_rejects_folder_without_manifest(tmp_path: Path) -> None:
    """A first-level folder without project.json (e.g. a legacy flat folder)
    is not treated as a project."""
    working_dir = tmp_path / "ChromIQ"
    legacy = working_dir / "LegacyFlat"
    legacy.mkdir(parents=True)
    (legacy / "LegacyFlat.ti2").write_text("CTI2\n")

    assert _project_root_for(legacy / "LegacyFlat.ti2", working_dir) is None


# ---------------------------------------------------------------------------
# Importing external .ti3s — measurement-only path
# ---------------------------------------------------------------------------

def test_copy_ti3_only_builds_project_layout(tmp_path: Path) -> None:
    """Importing a bare .ti3 creates a project shell with the measurement
    under runs/run1/<stem>.ti3 + the README."""
    src = tmp_path / "external"
    src.mkdir()
    ti3 = src / "stray.ti3"
    ti3.write_text("CTI3\n")
    (src / "stray.icc").write_text("ICC\n")        # sibling profile carries over

    working_dir = tmp_path / "ChromIQ"
    new_ti3 = _copy_ti3_only(ti3, working_dir, "Imported")

    proj = working_dir / "Imported"
    run1 = proj / "runs" / "run1"
    assert (proj / "project.json").is_file()
    assert (proj / "Where are my files.txt").is_file()
    assert new_ti3 == run1 / "Imported.ti3"
    assert new_ti3.read_text() == "CTI3\n"
    assert (run1 / "Imported.icc").read_text() == "ICC\n"


def test_copy_ti3_only_sanitises_project_name(tmp_path: Path) -> None:
    src = tmp_path / "external"
    src.mkdir()
    (src / "x.ti3").write_text("CTI3\n")

    working_dir = tmp_path / "ChromIQ"
    new_ti3 = _copy_ti3_only(src / "x.ti3", working_dir, "printer test file")

    assert (working_dir / "printer-test-file" / "runs" / "run1" / "printer-test-file.ti3").exists()
    assert new_ti3.name == "printer-test-file.ti3"
