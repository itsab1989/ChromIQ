"""Building the scanin command line + error parsing for the scanner roundtrip
(#98). No Argyll binary is invoked."""
from pathlib import Path

import pytest

from workflow.scanin_runner import ScaninParams, ScaninRunner, scanin_args


def test_auto_args_no_fiducials(tmp_path):
    args = scanin_args(tmp_path / "scan.tif", tmp_path / "c.cht",
                       tmp_path / "c.cie", corners=None)
    assert "-F" not in args
    assert args[-3:] == [str(tmp_path / "scan.tif"), str(tmp_path / "c.cht"),
                         str(tmp_path / "c.cie")]
    assert "-p" in args and "-v" in args


def test_the_corners_replace_the_perspective_search(tmp_path):
    """`-p` is dropped once the four corners are given, and only then.

    `-F` does not skip recognition: scanin still runs calc_lines ->
    calc_perspective -> calc_rotation before it looks at the corners, and the
    rotation it computes is never read on that path. `calc_perspective`
    optimises to minimise the variance of the detected line angles, which on a
    honeycomb — angles at 0 and +/-30 degrees — collapses the acceptance window
    and makes calc_rotation abort with "N consistent lines is not enough".
    Measured: 23.3 % of hexagonal reads failed with `-p`, 0 % without, and the
    values are bit-identical across 42 conditions including genuine keystone,
    lens distortion and Argyll's own standard targets — because the homography
    fitted to the four corners IS the perspective correction.
    """
    corners = [(10.0, 20.0), (200.0, 22.0), (198.0, 300.0), (12.0, 298.0)]
    with_corners = scanin_args(tmp_path / "s.tif", tmp_path / "c.cht",
                               tmp_path / "c.cie", corners=corners)
    assert "-p" not in with_corners, "the corners already carry the perspective"
    assert "-F" in with_corners
    # …and the auto path, which has no corners, still needs it
    auto = scanin_args(tmp_path / "s.tif", tmp_path / "c.cht",
                       tmp_path / "c.cie", corners=None)
    assert "-p" in auto

    from workflow.scanin_runner import scanin_printer_args
    pr = scanin_printer_args(tmp_path / "s.tif", tmp_path / "c.cht",
                             tmp_path / "p.icc", tmp_path / "base",
                             corners=corners)
    assert "-p" not in pr, "the printer path takes the same rule"


def test_manual_fiducial_formatting(tmp_path):
    corners = [(10.0, 20.0), (200.0, 22.0), (198.0, 300.0), (12.0, 298.0)]
    args = scanin_args(tmp_path / "s.tif", tmp_path / "c.cht", tmp_path / "c.cie",
                       corners=corners)
    i = args.index("-F")
    assert args[i + 1] == "10,20,200,22,198,300,12,298"   # x1,y1..x4,y4, TL→BL


def test_diag_adds_flag_and_trailing_path(tmp_path):
    diag = tmp_path / "diag.tif"
    args = scanin_args(tmp_path / "s.tif", tmp_path / "c.cht", tmp_path / "c.cie",
                       diag=diag)
    # `o` = "diag - sample box outlines" (ArgyllCMS `scanin --help`). Without it
    # the diagnostic draws NO boundary: the only visible edge is the
    # colour-vs-greyscale step at the sample area, and the patch edge the user
    # must judge it against is invisible on a third of edges — a picture with
    # nothing in it to be aligned with. Knut read a correct placement as
    # "clearly misaligned" from exactly that image.
    assert "-dipon" in args
    assert args[-1] == str(diag)          # diag is the trailing positional
    # cht/cie still precede the diag image
    assert args[-2] == str(tmp_path / "c.cie")


def test_bad_corner_count_raises(tmp_path):
    with pytest.raises(ValueError):
        scanin_args(tmp_path / "s.tif", tmp_path / "c.cht", tmp_path / "c.cie",
                    corners=[(0, 0), (1, 1)])


def test_out_ti3_never_collides_with_printer_profile(tmp_path):
    # Even if the scan is named exactly like the chart and sits in the run
    # folder, the scanner .ti3 gets a distinct -scanner name (never <stem>.ti3).
    p = ScaninParams(tmp_path / "MyChart.tif", tmp_path / "c.cht", tmp_path / "c.cie")
    assert p.out_ti3 == tmp_path / "MyChart-scanner.ti3"
    assert p.out_ti3 != tmp_path / "MyChart.ti3"
    # scanin gets -O with that name so it writes there, not the default
    args = ScaninRunner(runner=None)._build_args(p)
    assert "-O" in args and args[args.index("-O") + 1] == "MyChart-scanner.ti3"


def test_error_parsing_recognition_and_depth():
    r = ScaninRunner(runner=None)
    r._scan_line("Scanin failed with code 0x5, no reference located")
    r._scan_line("TIFF Input file 'x.tif' must be 8 or 16 bits/channel")
    keys = [k for k, _ in r._matched_errors]
    assert "recognition_failed" in keys and "bit_depth" in keys
    # the friendly text for the first failure mentions re-placing the corners
    key, msg = r.primary_failure()
    assert key == "recognition_failed" and "corners" in msg.lower()


# Exact messages copied from Argyll 3.5.0 scanin/scanin.c, each mapped to the
# friendly bucket it should collapse into.
def _first_key(*lines):
    r = ScaninRunner(runner=None)
    for ln in lines:
        r._scan_line(ln)
    fail = r.primary_failure()
    return fail[0] if fail else None


def test_reference_damaged_messages():
    for ln in (
        "Input file 'chart.cie' isn't a CTI2 format file",
        "Input file 'chart.cie' doesn't contain at least one table",
        "Input file 'chart.cie' doesn't contain any data sets",
        "Input file 'chart.cie' doesn't contain keyword COLOR_REP",
        "Input file 'chart.cie' keyword COLOR_REP has unknown value",
        "Input file 'chart.cie' doesn't contain field SAMPLE_ID",
        "Input file 'chart.cie' Field SAMPLE_LOC is wrong type",
        "Couldn't find location 'A1' in 'chart.cie'",
        "Couldn't find sample 'A1' in 'chart.ti3'",
    ):
        assert _first_key(ln) == "reference_damaged", ln


def test_reference_mismatch_messages():
    for ln in (
        "Different number of patches in 'x.ti3' (10) to expected(12)",
        "'a.cie' and 'b.ti3' field id's don't match at patch 3",
        "'a.cie' and 'b.ti3' device values (1.0 2.0) don't match at patch 3 4",
        "File 'a.cie' has different device space to 'b.ti3'",
    ):
        assert _first_key(ln) == "reference_mismatch", ln


def test_reference_io_and_oom_messages():
    # A READ failure and a WRITE failure are two different problems, and they
    # used to share one message that named only the write one — "check the
    # files exist and the folder is writable" (beta 8, B8-17). A read error
    # names the file and repeats ArgyllCMS's own reason instead.
    assert _first_key("CGATS file 'x.cie' read error : unexpected EOF") \
        == "reference_unreadable"
    assert _first_key("Write error to 'out.ti3' : disk full") == "reference_io"
    assert _first_key("Unable to allocate scanrd object") == "out_of_memory"
    assert _first_key("Malloc failed!") == "out_of_memory"


# ---------------------------------------------------------------------------
# Legacy-intermediates tidy-up (#127, Knut's beta.5 report)
# ---------------------------------------------------------------------------

def test_tidy_legacy_intermediates_moves_debris_keeps_data(tmp_path):
    from workflow.scanin_runner import tidy_legacy_intermediates
    debris = ["x-printer-p3-aligned.cht", "x-printer-p3-aligned-patchbox.cht",
              "x-p3s1-aligned-patchbox.cht", "x-p3s1-aligned-patchbox-sample.cht",
              "x-patchbox.cht", "x-patchbox-sample.cht", "scan1-diag.tif",
              "SCAN2-DIAG.TIF"]
    data = ["x-printer.ti2", "x-printer.ti3", "x-scanner.ti3",
            "x-p1s1-scanner.ti3", "x-p1-avg.ti3", "chart.cht", "chart.cie",
            "myscan.tif"]
    for n in debris + data:
        (tmp_path / n).write_text("f", encoding="utf-8")
    moved = tidy_legacy_intermediates(tmp_path)
    assert sorted(p.name for p in moved) == sorted(debris)
    for n in debris:
        assert (tmp_path / "cache" / n).is_file()
        assert not (tmp_path / n).exists()
    for n in data:
        assert (tmp_path / n).is_file(), f"measurement data {n} was moved!"


def test_tidy_plain_sample_only_when_derived(tmp_path):
    """`<x>-sample.cht` moves only when its source `<x>.cht` sits beside it —
    a user's own chart merely ending in -sample is never touched."""
    from workflow.scanin_runner import tidy_legacy_intermediates
    (tmp_path / "chart.cht").write_text("src", encoding="utf-8")
    (tmp_path / "chart-sample.cht").write_text("derived", encoding="utf-8")      # → cache
    (tmp_path / "colour-sample.cht").write_text("user chart", encoding="utf-8")  # stays
    moved = tidy_legacy_intermediates(tmp_path)
    assert [p.name for p in moved] == ["chart-sample.cht"]
    assert (tmp_path / "colour-sample.cht").exists()


def test_tidy_conflict_drops_stale_duplicate(tmp_path):
    from workflow.scanin_runner import tidy_legacy_intermediates
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "a-patchbox.cht").write_text("fresh", encoding="utf-8")
    (tmp_path / "a-patchbox.cht").write_text("stale flat copy", encoding="utf-8")
    moved = tidy_legacy_intermediates(tmp_path)
    assert moved == []                                  # nothing newly moved
    assert not (tmp_path / "a-patchbox.cht").exists()   # stale dupe removed
    assert (tmp_path / "cache" / "a-patchbox.cht").read_text(encoding="utf-8") == "fresh"


def test_tidy_missing_folder_is_noop(tmp_path):
    from workflow.scanin_runner import tidy_legacy_intermediates
    assert tidy_legacy_intermediates(tmp_path / "nope") == []
