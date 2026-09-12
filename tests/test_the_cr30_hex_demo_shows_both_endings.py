"""The CR30 honeycomb demo pack must show BOTH endings, and prove it did.

``scripts/make_cr30_hex_demo.py`` builds one CR30 honeycomb and two scans of
it: one that goes all the way through, and one that keeps tripping "Part of
this scan has no colour left in it". Those two sentences are the whole pack.
A reader opens it having been told what they are about to see, so a pack that
has quietly stopped showing it is worse than no pack at all: it teaches them
that the warning is noise.

What is guarded here:

* the generator REFUSES a pack whose scans do not straddle
  ``scanner_max_clipped`` with room to spare, rather than writing it anyway;
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
    for name in ("chart/CR30HexDemo.tif", "chart/CR30HexDemo.ti1",
                 "chart/CR30HexDemo.ti2", "chart/CR30HexDemo.channels.json",
                 "scan/CR30HexDemo-scan-1-in-range.tif",
                 "scan/CR30HexDemo-scan-2-out-of-scale.tif", "README.md"):
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
    scan's own would be, so the end-of-scale figure is a property of the chart
    and is the same for both files. That is true of the app as it stands and
    may not always be; the README is generated from the measurement either way,
    so it cannot go on describing an app that has changed.
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
def test_the_two_paths_do_not_agree_about_this_pack(built):
    """The finding the pack exists to reproduce, pinned so it cannot quietly
    change without somebody reading this file.

    The scan-reading path separates the two scans; the printer path does not.
    If this ever goes red because the printer path has learned to look at the
    scan, that is good news and the README's paragraph will already have
    rewritten itself. Read the message, then delete this test.
    """
    measured = json.loads((built / gen.PACK / "measured.json")
                          .read_text(encoding="utf-8"))
    if measured["in_range_clipped_printer_path"] is None:
        pytest.skip("no scanner ICC to walk the printer path with")
    assert measured["in_range_clipped"] != measured["out_of_scale_clipped"], (
        "the read-the-scan path no longer tells the two scans apart, which is "
        "the whole pack")
    assert (abs(measured["in_range_clipped_printer_path"]
                - measured["out_of_scale_clipped_printer_path"]) < 0.005), (
        "the printer path now tells the two scans apart. That is the fault in "
        "`scan_read_check` being fixed. Re-read the pack's README paragraph "
        "and this file's docstring, then remove this test.")


@needs_argyll
def test_the_chart_is_a_one_page_cr30_honeycomb(built):
    """What the pack is FOR. A demo built for another instrument, another
    paper, or a grid of squares would not be the thing that was asked for."""
    pack = built / gen.PACK
    doc = json.loads((pack / "chart" / "CR30HexDemo.channels.json")
                     .read_text(encoding="utf-8"))
    layout = doc["layout"]
    recipe = layout["recipe"]
    assert recipe["instrument"] == "CR30", recipe["instrument"]
    assert recipe["paper"] == "A4", recipe["paper"]
    assert recipe["hflag"] and recipe["hex_flat_top"], recipe
    assert {int(p.get("page", 0)) for p in layout["patches"]} == {0}, (
        "the chart spilled onto a second sheet")
    assert len(layout["patches"]) == gen.one_page_capacity(), (
        "the chart does not fill the sheet")
