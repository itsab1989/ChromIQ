"""The CR30 honeycomb demo pack must carry its measurements and show BOTH
endings, and prove it did.

``scripts/make_cr30_hex_demo.py`` builds a two-page CR30 honeycomb, scans of
both pages, three measurements read off those scans, and a second rendering of
page 1 that keeps tripping "Part of this scan has no colour left in it".

The pack has already been shipped once WITHOUT the measurements, and that broke
it for the two things it is mainly used for: **Create scanner or camera target**
takes a chart's ``.ti3`` and nothing else will do, and a one-page chart writes a
single ``.cht`` and never exercises the per-page naming. Both are guarded here
so the pack cannot lose them a second time.

What is guarded here:

* the generator REFUSES a pack whose scans do not straddle
  ``scanner_max_clipped`` with room to spare, rather than writing it anyway;
* it refuses one whose three reads are not really a ladder of noise, because
  three equally noisy files give averaging nothing to remove;
* it refuses to put a chart's patch positions on a measurement of a DIFFERENT
  chart, which is the one way restoring that column could go wrong quietly;
* the pack it does write carries every file the pack shipped on v4.3.0-beta.3
  carried, and its ``.ti3`` really does drive the scanner-target window;
* the sheet the two scans are rendered from leaves headroom at both ends, and
  the automatic-brightness stretch takes the top one away and leaves the
  bottom alone, so the pair differs in one property and one only;
* a chart pixel lands where the generator says it lands once the sheet has
  been resampled and turned. That one is not theory: the first version mapped
  chart pixels straight through the rotation and forgot the resample, and both
  reads came back ranking -0.04 against their own reference while still
  reporting a plausible clipped share;
* the README quotes the numbers the pack measured, rather than numbers
  somebody typed.

The end-to-end build is one test, guarded on ArgyllCMS being installed. It
costs a `targen` and two `scanin` runs, a couple of seconds in total.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PIL")
pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import make_cr30_hex_demo as gen              # noqa: E402
from workflow.scan_read_check import CLIP_HIGH, CLIP_LOW   # noqa: E402

ARGYLL = gen.ARGYLL
needs_argyll = pytest.mark.skipif(
    not (ARGYLL / "targen").is_file() or not (ARGYLL / "scanin").is_file(),
    reason="ArgyllCMS targen/scanin not installed")

CAP = 0.15

#: EVERY FILE THE PACK SHIPPED ON v4.3.0-beta.3 CARRIED, plus what the newer
#: one added. The list is written out rather than globbed, because the fault
#: this pack was reported for was a build that quietly stopped writing three of
#: them and a glob would have been just as happy.
#:
#: The beta.3 pack held: the chart's .ti1/.ti2/.channels.json, both page TIFFs,
#: a .ti3 beside the chart, three measurements for averaging, and one scan per
#: page. Nothing in that list may go missing again.
EXPECTED_FILES = (
    "chart/testHex.ti1",
    "chart/testHex.ti2",
    "chart/testHex.channels.json",
    "chart/testHex_01.tif",
    "chart/testHex_02.tif",
    "chart/testHex.ti3",
    "measurements/read1-clean.ti3",
    "measurements/read2-noisy.ti3",
    "measurements/read3-noisier.ti3",
    "scan/testHex_01-scan.tif",
    "scan/testHex_02-scan.tif",
    "scan/testHex_01-scan-out-of-scale.tif",
    "README.md",
    "measured.json",
)


# --------------------------------------------------- the refusal, on its own
def test_a_pack_whose_good_scan_would_be_stopped_is_refused():
    """The in-range scan is the one the README promises will run to the end."""
    faults = gen.clipping_faults(good=CAP + 0.01, bad=CAP + 0.20, cap=CAP)
    assert faults, ("a scan reading over the limit was accepted as the one "
                    "that goes all the way through")
    assert "in-range" in faults[0]


def test_a_pack_whose_good_scan_only_just_squeaks_under_is_refused():
    """Room to spare, not a squeak past. A pack that sits a decimal place from
    the limit stops demonstrating anything the next time the limit moves."""
    assert gen.clipping_faults(good=CAP - 0.001, bad=CAP + 0.20, cap=CAP)


def test_a_pack_whose_warning_scan_would_not_warn_is_refused():
    faults = gen.clipping_faults(good=0.0, bad=CAP - 0.01, cap=CAP)
    assert faults, ("a scan reading under the limit was accepted as the one "
                    "that trips the warning")
    assert "out-of-scale" in faults[0]


def test_a_pack_whose_warning_scan_only_just_scrapes_over_is_refused():
    assert gen.clipping_faults(good=0.0, bad=CAP + 0.001, cap=CAP)


def test_the_pair_this_pack_actually_builds_is_accepted():
    """The guard has to let the real thing through, or it is only a way of
    never shipping."""
    assert gen.clipping_faults(good=0.0, bad=0.288, cap=CAP) == []


# ------------------------------------------------- the noise ladder, refused
def _ladder(a, b, c):
    return {name: v for (name, _sd, _seed), v in zip(gen.READS, (a, b, c))}


def test_three_equally_noisy_reads_are_refused():
    """The averaging demo's whole claim. Three files that measure the same
    thing leave averaging with nothing to remove."""
    faults = gen.noise_faults(_ladder(0.04, 0.04, 0.04))
    assert len(faults) == 2, faults
    assert "read2-noisy" in faults[0] and "read3-noisier" in faults[1]


def test_a_ladder_that_goes_the_wrong_way_is_refused():
    assert gen.noise_faults(_ladder(0.26, 0.13, 0.04))


def test_a_ladder_that_barely_rises_is_refused():
    """Room to spare, not a whisker. A pack whose steps sit inside the
    measurement's own scatter stops demonstrating anything the next time the
    renderer changes."""
    step = gen.NOISE_RATIO - 0.05
    assert gen.noise_faults(_ladder(0.04, 0.04 * step, 0.04 * step * step))


def test_the_ladder_this_pack_actually_builds_is_accepted():
    """The guard has to let the real thing through, or it is only a way of
    never shipping. These are the numbers the pack measured."""
    assert gen.noise_faults(_ladder(0.0388, 0.1344, 0.2629)) == []


# --------------------------------------- putting the patch positions back on
def _cgats(path, fields, rows):
    path.write_text(
        "CTI3\n\nDESCRIPTOR \"t\"\n\n"
        f"NUMBER_OF_FIELDS {len(fields)}\nBEGIN_DATA_FORMAT\n"
        + " ".join(fields) + "\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
        + "\n".join(" ".join(str(c) for c in r) for r in rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


_XYZ = ("XYZ_X", "XYZ_Y", "XYZ_Z")
_RGB = ("RGB_R", "RGB_G", "RGB_B")


def test_the_chart_s_patch_positions_are_put_back_on_the_measurement(tmp_path):
    ti2 = _cgats(tmp_path / "c.ti2", ("SAMPLE_ID", "SAMPLE_LOC") + _RGB + _XYZ,
                 [(1, '"A1"', 100.0, 100.0, 100.0, 95.0, 100.0, 108.0),
                  (2, '"B7"', 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)])
    ti3 = _cgats(tmp_path / "c.ti3", ("SAMPLE_ID",) + _RGB + _XYZ,
                 [(1, 100.0, 100.0, 100.0, 87.1, 91.7, 99.9),
                  (2, 0.0, 0.0, 0.0, 0.7, 0.8, 0.8)])
    gen.add_sample_loc(ti3, ti2)
    _lines, fields, _slice, rows = gen._table(ti3)
    assert fields[:2] == ["SAMPLE_ID", "SAMPLE_LOC"], fields
    assert [r[1] for r in rows] == ['"A1"', '"B7"']
    # and the colour is untouched: only the position column was added
    assert [r[-3:] for r in rows] == [["87.1", "91.7", "99.9"],
                                      ["0.7", "0.8", "0.8"]]


def test_positions_from_a_different_chart_are_refused_rather_than_pasted_on(tmp_path):
    """The one way this could go wrong quietly. Pairing by SAMPLE_ID onto the
    wrong chart would put a real position on the wrong patch and every file
    downstream would look fine."""
    ti2 = _cgats(tmp_path / "c.ti2", ("SAMPLE_ID", "SAMPLE_LOC") + _RGB + _XYZ,
                 [(1, '"A1"', 100.0, 100.0, 100.0, 95.0, 100.0, 108.0)])
    ti3 = _cgats(tmp_path / "c.ti3", ("SAMPLE_ID",) + _RGB + _XYZ,
                 [(1, 50.0, 25.0, 75.0, 40.0, 30.0, 50.0)])
    with pytest.raises(SystemExit) as exc:
        gen.add_sample_loc(ti3, ti2)
    assert "not the same chart" in str(exc.value) or "wrong patch" in str(exc.value)


def test_a_measurement_holding_a_patch_the_chart_lacks_is_refused(tmp_path):
    ti2 = _cgats(tmp_path / "c.ti2", ("SAMPLE_ID", "SAMPLE_LOC") + _RGB + _XYZ,
                 [(1, '"A1"', 100.0, 100.0, 100.0, 95.0, 100.0, 108.0)])
    ti3 = _cgats(tmp_path / "c.ti3", ("SAMPLE_ID",) + _RGB + _XYZ,
                 [(1, 100.0, 100.0, 100.0, 87.0, 91.0, 99.0),
                  (9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)])
    with pytest.raises(SystemExit):
        gen.add_sample_loc(ti3, ti2)


def test_a_measurement_that_already_names_its_positions_is_left_alone(tmp_path):
    ti2 = _cgats(tmp_path / "c.ti2", ("SAMPLE_ID", "SAMPLE_LOC") + _RGB + _XYZ,
                 [(1, '"A1"', 100.0, 100.0, 100.0, 95.0, 100.0, 108.0)])
    ti3 = _cgats(tmp_path / "c.ti3", ("SAMPLE_ID", "SAMPLE_LOC") + _RGB + _XYZ,
                 [(1, '"Z9"', 100.0, 100.0, 100.0, 87.0, 91.0, 99.0)])
    before = ti3.read_text(encoding="utf-8")
    gen.add_sample_loc(ti3, ti2)
    assert ti3.read_text(encoding="utf-8") == before


# ------------------------------------------------- the sheet and the stretch
def _two_ended_sheet(tmp_path):
    """A chart page with nothing on it but the two extremes: device 0 on the
    left, device 255 on the right. It is the only part of a chart the clipping
    check can see."""
    from PIL import Image
    import numpy as np
    a = np.zeros((240, 240, 3), dtype="uint8")
    a[:, 120:, :] = 255
    p = tmp_path / "ends.tif"
    Image.fromarray(a).save(p, dpi=(gen.CHART_DPI, gen.CHART_DPI))
    return gen._sheet(p)


def _ends(sheet):
    """The two blocks, on the 0-100 scale a ``.ti3`` carries."""
    import numpy as np
    a = np.asarray(sheet, dtype=float)
    h, w = a.shape[:2]
    q, m = w // 4, h // 2
    dark = a[m - 20:m + 20, q - 20:q + 20].reshape(-1, 3).mean(axis=0)
    light = a[m - 20:m + 20, 3 * q - 20:3 * q + 20].reshape(-1, 3).mean(axis=0)
    return dark * 100.0 / 255.0, light * 100.0 / 255.0


def test_the_printed_sheet_leaves_headroom_at_both_ends(tmp_path):
    """The in-range scan is this sheet. A patch the chart asks for at 0 % or
    100 % of a channel must come back well inside both rails."""
    dark, light = _ends(_two_ended_sheet(tmp_path))
    assert min(dark) > CLIP_LOW + 2.0, (
        f"device black reads {dark} on the 0-100 scale, at or beside the "
        f"bottom rail ({CLIP_LOW})")
    assert max(light) < CLIP_HIGH - 2.0, (
        f"device white reads {light} on the 0-100 scale, at or beside the top "
        f"rail ({CLIP_HIGH})")
    assert max(light) > 85.0, (
        f"device white reads {max(light):.1f}; a scan exposed for its target "
        f"puts it just under the top, and below 60 the window says the scan "
        f"came out too dark instead")


def test_the_automatic_brightness_takes_the_top_headroom_away(tmp_path):
    """The out-of-scale scan is the same sheet through this one function."""
    dark, light = _ends(gen._auto_brightness(_two_ended_sheet(tmp_path)))
    assert max(light) >= CLIP_HIGH, (
        f"device white reads {max(light):.1f} after the stretch, still under "
        f"the top rail ({CLIP_HIGH}); the pack's warning scan would not warn")


def test_the_automatic_brightness_leaves_the_bottom_alone(tmp_path):
    """One property, one difference. A scan that ran out of scale at both ends
    would have the message counting two faults in one number, and the reader
    could not tell which one they were looking at."""
    dark, _light = _ends(gen._auto_brightness(_two_ended_sheet(tmp_path)))
    assert min(dark) > CLIP_LOW + 2.0, (
        f"device black reads {dark} after the stretch, at or beside the "
        f"bottom rail; the two scans now differ in two things")


# ------------------------------------------------------- where a pixel lands
def test_a_chart_pixel_lands_where_the_generator_says_it_lands():
    """``_forward`` must be the true inverse of the affine the image is
    actually transformed by, not a second opinion about it.

    Measured against PIL rather than against a repeat of the same arithmetic:
    one bright pixel is put on a black sheet, the sheet is transformed with the
    very coefficients :func:`_rotation` hands the renderer, and the bright spot
    is looked for where :func:`_forward` said it would be.
    """
    from PIL import Image
    import numpy as np
    w = h = 400
    for x, y in ((40, 60), (350, 90), (200, 380)):
        a = np.zeros((h, w), dtype="uint8")
        a[y, x] = 255
        coeffs, size = gen._rotation(w, h)
        out = Image.fromarray(a).transform(size, Image.Transform.AFFINE,
                                           coeffs,
                                           resample=Image.Resampling.NEAREST)
        got = np.asarray(out)
        assert got.max() > 0, "the bright pixel fell off the transformed sheet"
        fy, fx = np.unravel_index(int(np.argmax(got)), got.shape)
        px, py = gen._forward(x, y, w, h)
        assert abs(px - fx) <= 1.5 and abs(py - fy) <= 1.5, (
            f"the generator puts chart pixel ({x}, {y}) at "
            f"({px:.1f}, {py:.1f}); the image puts it at ({fx}, {fy})")


def test_the_corners_are_read_from_the_charts_own_cht():
    """Not recomputed from the recipe. The ``F`` line of the patch-box copy IS
    the patch bounding box, and it is what the reader drags onto."""
    cht = ("BOXES 1\n"
           "  F _ _ 10.00 20.00 110.00 20.00 110.00 220.00 10.00 220.00\n"
           "  X A1 A1 _ _ 10.00 10.00 10.00 20.00 0 0\n")
    w, h = 1000, 1400
    corners = gen.scan_corners(cht, w, h)
    assert len(corners) == 4
    px = gen.CHART_DPI / 25.4
    sw, sh = gen._scan_size(w, h)
    expect = [gen._forward(x * px * sw / w, y * px * sh / h, sw, sh)
              for x, y in ((10.0, 20.0), (110.0, 20.0),
                           (110.0, 220.0), (10.0, 220.0))]
    for got, want in zip(corners, expect):
        assert abs(got[0] - want[0]) < 1e-6 and abs(got[1] - want[1]) < 1e-6


def test_a_cht_with_no_fiducial_line_is_refused_rather_than_guessed_at():
    with pytest.raises(SystemExit):
        gen.scan_corners("BOXES 1\n  X A1 A1 _ _ 1 1 1 1 0 0\n", 100, 100)


# ------------------------------------------------------------- the whole pack
@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One real build for the whole file. It is a `targen` and two `scanin`
    runs; building it once per test would be three of each for the same
    answer."""
    into = tmp_path_factory.mktemp("cr30demo")
    r = subprocess.run([sys.executable,
                        str(ROOT / "scripts" / "make_cr30_hex_demo.py"),
                        str(into)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=900)
    assert r.returncode == 0, (
        f"the generator refused to write the pack:\n{r.stdout}\n{r.stderr}")
    return into


@needs_argyll
def test_the_pack_builds_and_both_claims_hold(built):
    """The end-to-end claim: build the pack for real and read back what it
    measured of its own two scans."""
    tmp_path = built
    pack = tmp_path / gen.PACK
    measured = json.loads((pack / "measured.json").read_text(encoding="utf-8"))
    cap = measured["scanner_max_clipped"]
    margin = measured["margin"]
    assert measured["in_range_clipped"] < cap - margin, (
        f"the in-range scan reads {measured['in_range_clipped'] * 100:.1f} % "
        f"clipped against a {cap * 100:.0f} % limit")
    assert measured["out_of_scale_clipped"] > cap + margin, (
        f"the out-of-scale scan reads "
        f"{measured['out_of_scale_clipped'] * 100:.1f} % clipped against a "
        f"{cap * 100:.0f} % limit")
    for name in EXPECTED_FILES:
        assert (pack / name).is_file(), f"the pack has no {name}"
    assert not list(tmp_path.glob("_*build*")), (
        "the generator left its working folder behind")


@needs_argyll
def test_the_readme_quotes_the_numbers_the_pack_measured(built):
    """A README that types its own numbers is a README that goes stale without
    anybody noticing. Every figure in the two paragraphs that matter is read
    back out of the text and checked against the measurement."""
    pack = built / gen.PACK
    measured = json.loads((pack / "measured.json").read_text(encoding="utf-8"))
    text = (pack / "README.md").read_text(encoding="utf-8")
    for key in ("in_range_clipped", "out_of_scale_clipped"):
        assert f"**{measured[key] * 100:.1f} %**" in text, (
            f"the README does not quote the {key} it measured "
            f"({measured[key] * 100:.1f} %)")
    assert f"{measured['patches']}-patch" in text
    assert f"stops at {measured['sample_area'] * 100:.0f} %" in text


@needs_argyll
def test_the_readme_describes_the_printer_path_it_measured(built):
    """The pack tells the reader which way into the window looks at the scan,
    and that sentence is written from what that path actually did here.

    On the "Profile my printer from this scan" path the window reads through
    `scanin -c`, whose `.ti3` carries the CHART's device values where the
    scan's own would be. It used to count the end-of-scale share off that
    column, so the figure was a property of the chart and came out the same for
    both files; the window now reads the scan's own values back with a second
    `scanin -o` pass, and the two files separate. The README is generated from
    whichever of those the measurement shows, so it cannot go on describing an
    app that has changed -- which is what this test checks, in both directions.
    """
    pack = built / gen.PACK
    measured = json.loads((pack / "measured.json").read_text(encoding="utf-8"))
    good_p = measured["in_range_clipped_printer_path"]
    bad_p = measured["out_of_scale_clipped_printer_path"]
    if good_p is None or bad_p is None:
        pytest.skip("no scanner ICC to walk the printer path with")
    text = (pack / "README.md").read_text(encoding="utf-8")
    same = abs(good_p - bad_p) < 0.005
    assert ("the same figure for both" in text) is same, (
        f"the printer path measured {good_p * 100:.1f} % and "
        f"{bad_p * 100:.1f} %, and the README says the opposite")
    assert f"**{good_p * 100:.0f} %**" in text or f"{good_p * 100:.0f} %" in text


@needs_argyll
def test_both_paths_agree_about_this_pack(built):
    """The finding the pack was built to reproduce, now pinned FIXED.

    This test used to be its opposite, ``test_the_two_paths_do_not_agree_about
    _this_pack``, and it said: *"if this ever goes red because the printer path
    has learned to look at the scan, that is good news [...] read the message,
    then delete this test."* It has, so it was. What replaces it is the same
    question asked the other way round, because the property is worth keeping.

    Both ways into the scanner window must tell these two scans apart, and they
    must agree, because it is one image either way. Ticking *"Profile my printer
    from this scan"* changes what the ``.ti3`` holds, not what the scanner did:
    the window now reads the scan's own device values back with a second
    ``scanin -o`` pass (:mod:`workflow.scan_device_values`) instead of counting
    the chart's solids and calling them the scan's.

    Measured 2026-09-13 on this pack, page 1: the in-range scan reads 0.0 % at
    an end of the scale on both paths and the out-of-scale one 37.9 % on both,
    against **23.3 % for both scans** on the printer path before the fix.
    """
    measured = json.loads((built / gen.PACK / "measured.json")
                          .read_text(encoding="utf-8"))
    good_p = measured["in_range_clipped_printer_path"]
    bad_p = measured["out_of_scale_clipped_printer_path"]
    if good_p is None:
        pytest.skip("no scanner ICC to walk the printer path with")
    good_s = measured["in_range_clipped"]
    bad_s = measured["out_of_scale_clipped"]
    assert good_s != bad_s, (
        "the read-the-scan path no longer tells the two scans apart, which is "
        "the whole pack")
    assert abs(good_p - bad_p) >= 0.005, (
        f"the printer path reports {good_p * 100:.1f} % for the in-range scan "
        f"and {bad_p * 100:.1f} % for the out-of-scale one, which is the same "
        f"figure for both. That is the fault this pack was built to show: the "
        f"clipped share is being counted off the CHART's device values instead "
        f"of the scan's. See workflow/scan_device_values.py.")
    # And they agree, patch for patch, because the two passes read the same
    # boxes of the same image: `val * 100 / 255` reproduces the scanner path's
    # own `.ti3` RGB to 2.4e-5, so anything beyond rounding here means the
    # values pass ran over different corners or a different `.cht`.
    for tag, printer, scanner in (("in-range", good_p, good_s),
                                  ("out-of-scale", bad_p, bad_s)):
        assert abs(printer - scanner) < 0.005, (
            f"the {tag} scan reads {printer * 100:.1f} % clipped with the "
            f"printer box ticked and {scanner * 100:.1f} % with it unticked. "
            f"It is one image; the two passes must agree.")


@needs_argyll
def test_the_chart_is_a_two_page_cr30_honeycomb(built):
    """What the pack is FOR. A demo built for another instrument, another
    paper, or a grid of squares would not be the thing that was asked for, and
    a ONE-page one writes a single ``.cht`` and never shows the per-page
    naming, which is half of what the pack was reported for."""
    pack = built / gen.PACK
    doc = json.loads((pack / "chart" / "testHex.channels.json")
                     .read_text(encoding="utf-8"))
    layout = doc["layout"]
    recipe = layout["recipe"]
    assert recipe["instrument"] == "CR30", recipe["instrument"]
    assert recipe["paper"] == "A4", recipe["paper"]
    assert recipe["hflag"] and recipe["hex_flat_top"], recipe
    assert {int(p.get("page", 0)) for p in layout["patches"]} == {0, 1}, (
        "the chart is not on two pages, so it writes one .cht and the "
        "per-page naming goes untested")
    assert len(layout["patches"]) == gen.PATCHES


@needs_argyll
def test_the_shipped_measurement_drives_the_scanner_target_window(built):
    """The fault Knut reported, guarded end to end.

    "Create scanner or camera target" takes a chart's ``.ti3`` and nothing else
    will do. The pack shipped without one, so the window could not be driven at
    all. This runs the window's own worker on the pack's own files and requires
    one ``.cht`` per page and a ``.cie`` covering every patch.
    """
    import shutil
    from workflow.scanin_target import build_scanin_target_from_paths
    pack = built / gen.PACK
    cold = built / "cold"
    cold.mkdir(exist_ok=True)
    for name in ("testHex.ti3", "testHex.channels.json", "testHex.ti2"):
        shutil.copy2(pack / "chart" / name, cold / name)
    res = build_scanin_target_from_paths(cold / "testHex.channels.json",
                                         cold / "testHex.ti3", cold / "testHex")
    assert len(res.cht_paths) == gen.EXPECT_PAGES, (
        f"the window wrote {len(res.cht_paths)} .cht file(s) for a "
        f"{gen.EXPECT_PAGES}-page chart")
    assert [p.name for p in res.cht_paths] == ["testHex_01.cht",
                                               "testHex_02.cht"]
    assert res.n_patches == gen.PATCHES
    assert res.cie_path.is_file()


@needs_argyll
def test_the_shipped_measurement_names_its_patch_positions(built):
    """Not merely present: usable. ``scanin -c`` writes a ``.ti3`` that numbers
    its patches 1, 2, 3 and the scanner-target window refuses one of those by
    name. The generator puts the chart's own ``SAMPLE_LOC`` column back, and a
    pack that stopped doing it would ship a measurement the window turns away.
    """
    text = ((built / gen.PACK / "chart" / "testHex.ti3")
            .read_text(encoding="utf-8"))
    fmt = [l for l in text.splitlines() if l.startswith("SAMPLE_ID")]
    assert fmt and "SAMPLE_LOC" in fmt[0], (
        f"the shipped measurement's fields are {fmt}, with no SAMPLE_LOC, so "
        f"Create scanner or camera target will refuse it")


@needs_argyll
def test_the_three_reads_really_are_a_ladder_of_noise(built):
    """Three measurements that do not differ give averaging nothing to remove,
    and a reader who follows the README watches a feature appear to do
    nothing."""
    measured = json.loads((built / gen.PACK / "measured.json")
                          .read_text(encoding="utf-8"))
    noise = measured["noise"]
    names = [n for n, _sd, _seed in gen.READS]
    values = [noise[n] for n in names]
    assert values == sorted(values), (
        f"the three reads carry {values} of noise, which is not a ladder")
    for lo, hi in zip(values, values[1:]):
        assert hi > lo * measured["noise_ratio"], (
            f"{hi:.4f} is not {measured['noise_ratio']:g} times {lo:.4f}")
