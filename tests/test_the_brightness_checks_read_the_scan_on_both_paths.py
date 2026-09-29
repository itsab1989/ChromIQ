"""#182, 2026-09-13 — the two exposure checks were asking about the chart.

*Build profile with scanner or camera* has two modes. Untick **"Profile my
printer from this scan"** and ``scanin`` writes a ``.ti3`` whose ``RGB_*`` are
what the scanner saw. Tick it and ``scanin -c`` writes a ``.ti3`` whose
``RGB_*`` are **the CHART's printer device values** and whose ``XYZ_*`` are the
scan converted through a scanner profile.

``inspect_read`` counted clipped patches from that device column and
``highlight_level`` took the device value from the same place, so on the ticked
mode both were measuring the chart:

* **the clipped warning fired on every scan ever made on that path.** Every
  profiling chart is full of solids and paper by design. Measured on charts
  straight out of ``targen``: 61.0 % clipped at 210 patches, 49.2 at 396, 40.4
  at 800, 32.8 at 1500, against a 15 % limit. The number never moved with the
  scan, so the advice it gave — rescan with the automatic brightness off —
  could never change it;
* **the too-dark warning could never fire**, because a chart's paper patch is
  device 100 by construction. A genuinely dark scan went through in silence,
  and that is the one that quietly builds a bad printer profile.

Reproduced on the CR30 demo pack, whose two scans differ only in brightness:
**23.3 % clipped for both** on the ticked path (white 100.0 for both), against
0.0 % / white 96.3 and 37.9 % / white 99.8 on the unticked one. Same images,
same corners.

The fix is a second ``scanin -o`` pass over the same image
(:mod:`workflow.scan_device_values`), and what makes it the right one is that it
is not an approximation: ``val * 100 / 255`` reproduced the scanner path's own
``.ti3`` ``RGB_*`` to a maximum of **0.000024** over 396 patches. After it, the
ticked path reports 0.0 % / 96.3 and 37.9 % / 99.8 — the unticked path's own
numbers, to the decimal.

What this file pins, in order: that the scanner path is untouched; that the
printer path answers from the scan; that a values pass which cannot run leaves
the two checks **unmeasured** rather than falling back on the chart; and that
nobody compares ``clipped`` directly, since it is now ``None`` when unmeasured.
"""
from __future__ import annotations

import inspect
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import scan_device_values as sdv                # noqa: E402
from workflow.scan_read_check import (                        # noqa: E402
    CLIP_HIGH, HIGHLIGHT_CHART_MIN_DEVICE, NEAR_PAPER, ReadInspection,
    highlight_level, highlight_level_by_device, inspect_read,
)
from workflow.scanin_runner import (                          # noqa: E402
    VAL_FULL_SCALE, parse_val, scanin_values_args,
)


# --------------------------------------------------------------------------
# A chart of the shape every profiling chart has: paper, solids, and a ramp.
# The numbers below are the demo pack's own first rows.
def _chart(n_paper: int = 4, n_solid: int = 4, n_ramp: int = 12):
    rows = [(100.0, 100.0, 100.0)] * n_paper
    rows += [(0.0, 0.0, 0.0)] * n_solid
    # A cyan ramp: its STRONGEST channel is 100 on every row, which is why the
    # paper selector has to read the weakest one.
    rows += [(100.0 - 9.09 * (i + 1), 100.0, 100.0) for i in range(n_ramp)]
    return np.array(rows, dtype=float)


#: What a scanner reads off solid black ink, 0-100. Not 0: ink reflects, and a
#: model that returned 0 would put every solid on the bottom rail and report a
#: perfectly exposed scan as 30 % clipped. The CR30 demo pack's in-range scan
#: reads 0.0 % at BOTH rails, which is the behaviour this has to reproduce.
INK_FLOOR = 7.0


def _scan_of(chart: np.ndarray, exposure: float) -> np.ndarray:
    """What a scanner returns for that chart at a given exposure, 0-100.

    Paper lands at ``100 * exposure`` — that is what setting an exposure means
    — and everything else in proportion above the ink floor. Clipped at both
    ends, the way a real device is.
    """
    reflect = INK_FLOOR + (100.0 - INK_FLOOR) * (chart / 100.0)
    return np.clip(reflect * exposure, 0.0, 100.0)


# ============================ the arguments ===============================
def test_the_values_pass_asks_for_only_the_image_and_the_cht():
    """``scanin -o input.tif recog.cht`` — no reference, no pbase, no ICC.

    That is the whole reason this pass is safe to add to a build: it cannot
    read or write the measurement the build depends on. ``scanin -r``, the
    obvious alternative, REPLACES the device values in ``pbase.ti2``/``.ti3``.
    """
    args = scanin_values_args(Path("/s/scan.tif"), Path("/s/p.cht"), "v.val",
                              corners=[(1, 2), (3, 4), (5, 6), (7, 8)])
    assert "-o" in args
    assert "-c" not in args and "-ca" not in args and "-r" not in args
    assert args[-2:] == ["/s/scan.tif", "/s/p.cht"]
    assert args[args.index("-F") + 1] == "1,2,3,4,5,6,7,8"


def test_the_values_pass_always_names_its_own_output_file():
    """Without ``-O`` scanin writes ``<input>.val`` BESIDE THE INPUT IMAGE,
    which on this path is the folder the user keeps their scans in. Measured
    2026-09-13: the first attempt put a ``.val`` straight into the demo pack's
    ``scan/`` directory."""
    for corners in (None, [(1, 2), (3, 4), (5, 6), (7, 8)]):
        args = scanin_values_args(Path("/s/scan.tif"), Path("/s/p.cht"),
                                  "v.val", corners=corners)
        assert "-O" in args, "the values pass must never write beside the scan"
        assert args[args.index("-O") + 1] == "v.val"


def test_the_values_pass_drops_perspective_under_corners():
    """The same rule the two paths beside it follow: ``-p`` is dead work under
    ``-F`` and aborts 23.3 % of honeycomb reads. See the long note in
    ``scanin_args``."""
    with_corners = scanin_values_args(Path("/a.tif"), Path("/b.cht"), "v.val",
                                      corners=[(1, 2), (3, 4), (5, 6), (7, 8)])
    without = scanin_values_args(Path("/a.tif"), Path("/b.cht"), "v.val")
    assert "-p" not in with_corners
    assert "-p" in without


# ============================== the parser ================================
_VAL = """VALS

DESCRIPTOR "Argyll Calibration raster values"

NUMBER_OF_FIELDS 4
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B
END_DATA_FORMAT

NUMBER_OF_SETS 3
BEGIN_DATA
A01 255.0000 255.0000 255.0000
A2 127.5000 0.000000 63.75000
B10 21.54342 21.56466 21.58487
END_DATA
"""


def test_a_val_file_is_read_onto_the_scale_a_ti3_states(tmp_path):
    """``.val`` holds raw raster values 0-255; a ``.ti3`` states the same
    numbers as a percentage. Measured 2026-09-13 rather than assumed: an 8-bit
    scan and the same scan as 16-bit (every sample x257) produced byte-identical
    ``.val`` files, and ``val * 100 / 255`` reproduced the scanner path's own
    ``.ti3`` ``RGB_*`` to 0.000024 over 396 patches."""
    p = tmp_path / "v.val"
    p.write_text(_VAL, encoding="utf-8")
    got = parse_val(p)
    assert VAL_FULL_SCALE == 255.0
    assert got["A1"] == pytest.approx((100.0, 100.0, 100.0))
    assert got["A2"] == pytest.approx((50.0, 0.0, 25.0))
    assert got["B10"] == pytest.approx((8.4484, 8.4567, 8.4646), abs=1e-3)


def test_a_padded_val_id_pairs_with_an_unpadded_chart_id(tmp_path):
    """``A01`` in the ``.val`` and ``A1`` in the ``.ti2`` are one patch. Two
    different normalisations would mispair every padded id, silently."""
    p = tmp_path / "v.val"
    p.write_text(_VAL, encoding="utf-8")
    assert "A1" in parse_val(p) and "A01" not in parse_val(p)


@pytest.mark.parametrize("text", [
    "", "not cgats at all\n",
    "BEGIN_DATA_FORMAT\nSAMPLE_ID XYZ_X\nEND_DATA_FORMAT\n",
    "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"
    "BEGIN_DATA\nEND_DATA\n",
])
def test_an_unusable_val_file_is_none_and_never_an_empty_answer(tmp_path, text):
    """``None`` means "do not judge". A ``{}`` would read as "no patches
    clipped", which is the one answer this must never invent."""
    p = tmp_path / "v.val"
    p.write_text(text, encoding="utf-8")
    assert parse_val(p) is None


def test_a_missing_val_file_is_none(tmp_path):
    assert parse_val(tmp_path / "nope.val") is None


# ===================== the printer-path highlight =========================
def test_the_paper_selector_reads_the_weakest_channel_not_the_strongest():
    """The whole reason :data:`NEAR_PAPER` is applied to ``min`` and not
    ``max``. On a printer chart the paper patch has no ink in ANY channel; the
    demo pack's A9 is (90.9, 100, 100), a cyan tint whose STRONGEST channel is
    also 100. Selecting on the max takes the entire cyan ramp and calls it
    white, and the ramp is dark in the scan, so the measure would report a
    dark scan for a perfect one."""
    chart = _chart()
    scan = _scan_of(chart, 0.96)
    got = highlight_level_by_device(scan, chart)
    # Only the four paper rows may be selected: 100 * 0.96.
    assert got == pytest.approx(96.0, abs=0.01)
    # If the max channel had been used, the cyan ramp would join in and drag
    # the median down. Prove that is a real difference and not a coincidence.
    strongest = chart.max(axis=1)
    assert (strongest >= NEAR_PAPER * strongest.max()).sum() > 4, (
        "this fixture no longer distinguishes the two selectors")


@pytest.mark.parametrize("exposure,expect", [
    (1.00, 100.0), (0.96, 96.0), (0.85, 85.0), (0.70, 70.0),
    (0.45, 45.0), (0.18, 18.0),
])
def test_the_printer_path_highlight_follows_the_exposure(exposure, expect):
    """The check that could never fire. It must move with the scan and with
    nothing else: the chart is identical on every row here."""
    chart = _chart()
    got = highlight_level_by_device(_scan_of(chart, exposure), chart)
    assert got == pytest.approx(expect, abs=0.01)
    assert ReadInspection(rows=20, agreement=None, clipped_high=0.0,
                          clipped_low=0.0, highlight=got,
                          support=20).underexposed(60.0) is (expect < 60.0)


def test_the_two_paths_measure_the_same_scan_the_same_way():
    """A printer chart selected by device value and a scanner target selected
    by reference Y must land on the same number for one scan, because the
    measure is the same measure. Measured for real on the demo pack: 96.3 and
    96.3, then 99.8 and 99.8."""
    chart = _chart()
    scan = _scan_of(chart, 0.93)
    # The reference a scanner target would carry: Y tracking the chart.
    y = chart.mean(axis=1)
    xyz = np.stack([y * 0.95, y, y * 1.09], axis=1)
    assert highlight_level_by_device(scan, chart) == pytest.approx(
        highlight_level(scan, xyz), abs=0.01)


def test_a_chart_with_no_paper_patch_declines_instead_of_accusing():
    """The analogue of :data:`HIGHLIGHT_REFERENCE_MIN_Y`. Page 2 of the CR30
    demo pack is a real instance: its whitest patch is (84.2, 90.0, 98.5), so
    there is no unprinted paper on that sheet and no exposure to judge by.
    Measuring its brightest TINT against a floor calibrated on white would
    warn about a sheet that is fine."""
    chart = np.array([[84.2, 90.0, 98.5], [50.0, 40.0, 30.0],
                      [10.0, 10.0, 10.0]], dtype=float)
    assert chart.min(axis=1).max() < HIGHLIGHT_CHART_MIN_DEVICE
    assert highlight_level_by_device(_scan_of(chart, 0.9), chart) is None


@pytest.mark.parametrize("scan,chart", [
    (None, _chart()), (_chart(), None), (None, None),
    (np.zeros((0, 3)), np.zeros((0, 3))),
    (_chart(), _chart()[:3]),                 # lengths disagree
])
def test_the_printer_path_highlight_declines_on_anything_it_cannot_pair(scan, chart):
    assert highlight_level_by_device(scan, chart) is None


# ======================= inspect_read, both modes =========================
def _ti3(tmp_path: Path, dev, xyz) -> Path:
    rows = "\n".join(
        f"{i + 1} {d[0]:.5f} {d[1]:.5f} {d[2]:.5f} "
        f"{x[0]:.5f} {x[1]:.5f} {x[2]:.5f}"
        for i, (d, x) in enumerate(zip(dev, xyz)))
    p = tmp_path / "m.ti3"
    p.write_text(
        'CTI3\n\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "iRGB_XYZ"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(dev)}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    return p


def test_the_scanner_path_is_not_changed_by_one_number(tmp_path):
    """The hard requirement. With ``scan`` left ``None`` every figure must be
    what it was before this change existed: that mode's ``.ti3`` already holds
    the scan's device values, and its thresholds were calibrated on 74 real
    reads."""
    chart = _chart()
    scan = _scan_of(chart, 0.96)
    y = chart.mean(axis=1)
    xyz = np.stack([y * 0.95, y, y * 1.09], axis=1)
    ti3 = _ti3(tmp_path, scan, xyz)          # scanner .ti3: RGB is the scan
    got = inspect_read(ti3, 0.98)
    assert got.measured_exposure
    assert got.clipped_high == pytest.approx(0.0)
    assert got.highlight == pytest.approx(96.0, abs=0.05)
    assert got.rows == len(chart)


def test_the_printer_path_answers_about_the_scan_and_not_the_chart(tmp_path):
    """The fault itself, in one assertion pair.

    The ``.ti3`` is the same on both rows: chart device values, and an ``XYZ_*``
    that tracks the scan. Only the exposure differs, and only the values pass
    can see it.
    """
    chart = _chart(n_paper=4, n_solid=4, n_ramp=12)
    ti3 = _ti3(tmp_path, chart, np.stack([chart.mean(axis=1)] * 3, axis=1))

    # Without the values pass the two checks have nothing of the scan.
    blind = inspect_read(ti3, 0.98, scan=sdv.ScanDeviceValues((), (), None))
    assert not blind.measured_exposure
    assert blind.clipped is None and blind.highlight is None

    # Three exposures of ONE sheet. The pack's two real states are the first
    # two: in-range reads 0.0 % clipped / white 96.3, out-of-scale 37.9 % /
    # 99.8. The third is the one nothing could ever see.
    ids = tuple(f"A{i + 1}" for i in range(len(chart)))
    seen = {}
    for tag, exposure in (("in-range", 0.96), ("over", 1.06), ("dark", 0.45)):
        dev = _scan_of(chart, exposure)
        seen[tag] = inspect_read(ti3, 0.98, scan=sdv.ScanDeviceValues(
            ids=ids, scan_rgb=tuple(map(tuple, dev)),
            chart_rgb=tuple(map(tuple, chart))))

    # The top rail is what exposure moves, and it now moves with it. This is
    # what makes the warning's advice ("rescan with the automatic brightness
    # off") able to change the number at all.
    assert seen["in-range"].clipped_high == pytest.approx(0.0)
    assert seen["over"].clipped_high > 0.15
    assert seen["dark"].clipped_high == pytest.approx(0.0)
    # So the clipped warning fires on the over-exposed sheet and on neither of
    # the others. Before this change it fired on all three, always.
    assert seen["over"].over_clipped(0.15)
    assert not seen["in-range"].over_clipped(0.15)

    # The too-dark check now fires, which it could never do before: the
    # chart's paper is device 100 by construction, so the old reading was
    # 100.0 whatever the scan did.
    assert seen["in-range"].highlight == pytest.approx(96.0, abs=0.05)
    assert seen["dark"].highlight == pytest.approx(45.0, abs=0.05)
    assert seen["dark"].underexposed(60.0)
    assert not seen["in-range"].underexposed(60.0)

    # And the figures the old code reported, from this same `.ti3`: one number
    # for every scan, over the limit, and a highlight pinned at 100.
    old = inspect_read(ti3, 0.98)
    assert old.clipped > 0.15, (
        "a chart-derived share is over the limit by construction: it counts "
        "the chart's own solids and paper")
    assert old.highlight == pytest.approx(100.0)
    for tag in ("in-range", "dark"):
        assert seen[tag].clipped != pytest.approx(old.clipped), (
            f"the {tag} scan still reports the chart's figure")


def test_a_values_pass_that_did_not_run_is_unmeasured_never_the_chart(tmp_path):
    """A second pass must not double a failure. It must also not quietly hand
    the checks the chart's numbers again, which is the fault, not a fallback."""
    chart = _chart()
    ti3 = _ti3(tmp_path, chart, np.stack([chart.mean(axis=1)] * 3, axis=1))
    for scan in (sdv.ScanDeviceValues((), (), None),
                 sdv.ScanDeviceValues(("A1",), ((1.0, 2.0),), None)):
        got = inspect_read(ti3, 0.9, scan=scan)
        assert got is not None, "the build must still work"
        assert not got.measured_exposure
        assert got.clipped is None and got.highlight is None
        assert got.rows == len(chart), "everything else is still measured"


def test_an_unmeasured_page_accuses_nobody_and_raises_nothing():
    """``None`` is not "clean" and it is not an exception either. Both matter:
    a page read as clean hides a bad scan, and a raise inside a sanity check
    would stop a build the check was only supposed to comment on."""
    unmeasured = ReadInspection(rows=10, agreement=0.9, clipped_high=None,
                                clipped_low=None, highlight=None, support=20)
    assert unmeasured.clipped is None
    assert unmeasured.over_clipped(0.15) is False
    assert unmeasured.over_clipped(0.0) is False
    assert unmeasured.underexposed(60.0) is False
    assert unmeasured.clipped_at_top is False
    assert not unmeasured.measured_exposure


def test_a_measured_page_still_accuses():
    """The other direction, so the test above cannot pass by the check being
    switched off altogether."""
    bad = ReadInspection(rows=10, agreement=0.9, clipped_high=0.38,
                         clipped_low=0.0, highlight=40.0, support=20)
    assert bad.over_clipped(0.15) is True
    assert bad.underexposed(60.0) is True
    assert bad.measured_exposure


# ==================== the window asks through over_clipped =================
def test_the_window_never_compares_clipped_with_an_operator():
    """``clipped`` is ``float | None`` now, so ``got.clipped > cap`` is a
    ``TypeError`` on an unmeasured page — inside a bare ``except Exception``
    that would swallow it and lose every finding for that sheet, silently.
    Every caller must ask through :meth:`ReadInspection.over_clipped`."""
    from ui.dialogs import scanin_dialog
    src = inspect.getsource(scanin_dialog)
    for bad in ("got.clipped >", "got.clipped <", ".clipped > cap"):
        assert bad not in src, (
            f"{bad!r} in scanin_dialog.py: ask through over_clipped(), which "
            f"declines on an unmeasured page instead of raising")
    assert src.count("over_clipped(") >= 2, (
        "both the build gate and the Check-alignment window must ask")


def test_both_read_check_call_sites_pass_the_values_pass():
    """The two places the five checks are implemented, twice, with different
    output shapes. A new source of data added to one and not the other is how
    they diverge — and the Check-alignment window is the one the user is told
    to press."""
    from ui.dialogs import scanin_dialog
    for name in ("_read_verdicts", "_check_read_is_this_chart"):
        src = inspect.getsource(getattr(scanin_dialog.ScannerProfileDialog, name))
        assert "scan=self._scan_device_values(" in src, (
            f"{name} calls inspect_read without the scan's own device values, "
            f"so on the printer path it is judging the chart")
        assert "_say_exposure_not_measured" in src, (
            f"{name} does not tell the user when the two exposure checks "
            f"could not run")


def test_the_values_pass_is_only_run_on_the_printer_path():
    """The scanner path's ``.ti3`` already holds the scan's device values.
    Running a second pass there would be 0.27 s per page of nothing."""
    from ui.dialogs import scanin_dialog
    src = inspect.getsource(
        scanin_dialog.ScannerProfileDialog._scan_device_values)
    assert 'if not getattr(params, "is_printer"' in src


# ========================= the runner, end to end ==========================
def test_a_failing_values_pass_returns_none_and_does_not_raise(tmp_path):
    """Every way it can fail means one thing to the caller: not measured."""
    assert sdv.measure_scan_device_values(
        Path("/nonexistent/scanin"), tmp_path / "s.tif", tmp_path / "c.cht",
        tmp_path / "out") is None


def test_a_values_pass_that_times_out_returns_none(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="scanin", timeout=1)
    monkeypatch.setattr(sdv, "run_text", _boom)
    assert sdv.measure_scan_device_values(
        Path("/bin/true"), tmp_path / "s.tif", tmp_path / "c.cht",
        tmp_path / "out") is None


def test_a_nonzero_exit_returns_none(tmp_path, monkeypatch):
    class _R:
        returncode = 1
        stdout = "Scanin failed with code 1"
        stderr = ""
    monkeypatch.setattr(sdv, "run_text", lambda *a, **k: _R())
    assert sdv.measure_scan_device_values(
        Path("/bin/true"), tmp_path / "s.tif", tmp_path / "c.cht",
        tmp_path / "out") is None


def test_the_timeout_is_generous_because_a_tight_one_is_a_phantom_red():
    """Measured at 0.27 s on a 10.1 MB scan. 2026-09-02 cost a release gate a
    red because a subprocess measured at 1.2 s idle was given 60 s and a
    saturated machine blew through it."""
    assert sdv.VALUES_TIMEOUT >= 300




# ==================== the chart pairing, driven for real ===================
_TI2_NO_XYZ = (
    'CTI2\n\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n'
    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
    'NUMBER_OF_SETS 2\nBEGIN_DATA\n1 "A1" 100.0 100.0 100.0\n'
    '2 "A2" 0.0 0.0 0.0\nEND_DATA\n')

_TI2_WITH_XYZ = (
    'CTI2\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
    "END_DATA_FORMAT\n\n"
    'NUMBER_OF_SETS 2\nBEGIN_DATA\n'
    '1 "A1" 100.0 100.0 100.0 95.1 100.0 108.8\n'
    '2 "A2" 0.0 0.0 0.0 1.0 1.0 1.0\nEND_DATA\n')

_VAL_TWO = ("VALS\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
            "NUMBER_OF_SETS 2\nBEGIN_DATA\n"
            "A1 255 255 255\n{second}\nEND_DATA\n")


def _fake_pass(tmp_path, val_body, ti2_text, out="out"):
    """Drive ``measure_scan_device_values`` with only the SUBPROCESS stubbed,
    so the parsing, the pairing and the guards all run for real.

    Faking the parse as well would be a fake that re-implements the code and
    then agrees with itself, which is exactly how the first version of the
    partial-pairing test below passed against a deliberate mutation.
    """
    import unittest.mock as mock
    val = tmp_path / out / "read-values.val"
    val.parent.mkdir(parents=True, exist_ok=True)
    val.write_text(val_body, encoding="utf-8")
    ti2 = None
    if ti2_text is not None:
        ti2 = tmp_path / f"{out}.ti2"
        ti2.write_text(ti2_text, encoding="utf-8")

    class _R:
        returncode = 0
        stdout = stderr = ""
    with mock.patch.object(sdv, "run_text", lambda *a, **k: _R()):
        return sdv.measure_scan_device_values(
            Path("/bin/true"), tmp_path / "s.tif", tmp_path / "c.cht",
            tmp_path / out, ti2=ti2)


def test_the_chart_pairs_even_when_its_ti2_carries_no_aim_colours(tmp_path):
    """A ``.ti2`` needs only ``SAMPLE_LOC`` and ``RGB_*`` to say which patch is
    paper.

    The first version of this code read the chart through ``parse_ti3``, which
    raises *"No XYZ, Lab or spectral columns in the measurement"* on a file
    that has none: right for a measurement, wrong for a chart. Found by
    mutation testing on 2026-09-13, and found only because the mutation was
    checked for having landed -- the test meant to guard the pairing handed it
    exactly such a file, so the helper returned ``None``, the mutation changed
    nothing, and the test passed by validating itself.
    """
    got = _fake_pass(tmp_path, _VAL_TWO.format(second="A2 26 26 26"),
                     _TI2_NO_XYZ)
    assert got is not None and got.chart_rgb is not None, (
        "a chart with no aim colours still says which patch is paper")
    assert got.chart_rgb[0] == pytest.approx((100.0, 100.0, 100.0))
    assert highlight_level_by_device(
        np.array(got.scan_rgb), np.array(got.chart_rgb)) == pytest.approx(
            100.0, abs=0.01)


def test_a_ti2_with_aim_colours_pairs_the_same_way(tmp_path):
    """The shape every chart ChromIQ writes actually has, so the test above
    cannot be passing on a shape nothing produces."""
    got = _fake_pass(tmp_path, _VAL_TWO.format(second="A2 26 26 26"),
                     _TI2_WITH_XYZ, out="out2")
    assert got is not None and got.chart_rgb is not None
    assert got.chart_rgb[0] == pytest.approx((100.0, 100.0, 100.0))


def test_a_partial_pairing_is_refused_rather_than_guessed(tmp_path):
    """The highlight check picks the chart's near-white patches. If the ids it
    would have picked are the missing ones, a partial join answers confidently
    about the wrong patches, so the chart side is dropped entirely and only the
    clipped share, which needs no chart at all, still answers."""
    got = _fake_pass(tmp_path, _VAL_TWO.format(second="Z9 10 10 10"),
                     _TI2_WITH_XYZ, out="out3")
    assert got is not None and len(got) == 2
    assert got.chart_rgb is None, "a partial pairing must not be used"
    assert got.scan_rgb[0] == pytest.approx((100.0, 100.0, 100.0)), (
        "the clipped share must survive a pairing that does not")


def test_an_empty_val_makes_the_whole_pass_decline(tmp_path):
    """scanin ran, exited 0, and found nothing. That is *not measured*, and it
    must come back as ``None`` rather than as a ``ScanDeviceValues`` holding no
    patches, which the checks would read as a page with nothing clipped."""
    empty = ("VALS\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
             "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
             "NUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n")
    assert _fake_pass(tmp_path, empty, _TI2_WITH_XYZ, out="e1") is None
    assert _fake_pass(tmp_path, "junk\n", _TI2_WITH_XYZ, out="e2") is None
