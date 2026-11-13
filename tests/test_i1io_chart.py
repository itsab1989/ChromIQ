"""THE i1iO TABLE CHART (Beta): strips along the arm, readable by position,
and named so the Measure tab knows it.

Basti, 2026-11-13: an "i1iO" entry in Create Chart that makes a chart with
ChromIQ's own layout engine ("we have absolute freedom when it comes to
creating charts"), and ``.ti2`` files that carry the instrument name. What
is held here:

* the geometry: a portrait page laid across the table, the engine's strips
  down its long side (= along the arm); every patch, every strip's run-in
  and run-out and every aiming mark lies on the sheet, nothing touches a
  mark, and the capacity is the geometry's own;
* the marks are where the side file says, in the order the person aims;
* the files: ``TARGET_INSTRUMENT "X-Rite i1iO"``, the declared keywords, the
  side file, and every patch of the side file at the place the ``.strips.json``
  draws it, so the measuring step can drive the arm from the side file alone;
* separated (CMYK) charts carry the marks in the black ink only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _ti1(path: Path, n: int, rep: str = "RGB") -> Path:
    fields = {"RGB": ["RGB_R", "RGB_G", "RGB_B"],
              "CMYK": ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]}[rep]
    rows = []
    for i in range(n):
        dev = [((i * (7 + 3 * k)) % 101) * 1.0 for k in range(len(fields))]
        rows.append(f"{i + 1} " + " ".join(f"{v:.4f}" for v in dev)
                    + " 50.0 50.0 50.0")
    path.write_text(
        "CTI1\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        f'COLOR_REP "{rep}"\n\n'
        f"NUMBER_OF_FIELDS {len(fields) + 4}\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID " + " ".join(fields) + " XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def _build(tmp_path, n, paper="A4", rep="RGB", **kw):
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path / "c.ti1", n, rep)
    result = chart.build_chart(ti1, tmp_path / "c", instrument="IO2",
                               paper=paper, dpi=150, **kw)
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    return result, side


@pytest.mark.parametrize("paper,kw,count", [
    ("A4", {}, 504), ("A4", {"spacer_mode": "bw"}, 504),
    ("A4", {"spacer_mode": "none"}, 546),
    ("A4", {"spacer_mode": "none", "draw_indicators": False,
            "row_indicators": False}, 567),
    ("Letter", {}, 462), ("Letter", {"spacer_mode": "none"}, 504),
    ("Letter", {"spacer_mode": "none", "draw_indicators": False,
                "row_indicators": False}, 525)])
def test_the_capacity_is_the_geometrys_own(paper, kw, count):
    """Per sheet: A4 504 with the default contrast spacers (546 without, 567
    with no spacers and no labels), Letter 462 (504, 525). Computed from the
    patch size, the spacers and the smallest safe margins of `table_facts`,
    not looked up."""
    from workflow.layout_engine import geometry, instruments, papers
    g = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper, **kw})
    w, h = papers.dimensions_mm(paper)
    assert geometry.patches_per_sheet(g, w, h) == count
    assert (g.pwid, g.plen) == (8.0, 10.0)


def test_whatever_a_recipe_asks_for_the_i1io_keeps_its_own_layout():
    """A clip border, helper markers, edge spacers, an area-first layout or
    margins below the safe minimum change nothing; a patch size is kept
    inside the table's limits (engine terms: width across a strip, height
    along it)."""
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    plain = geometry.patches_per_sheet(instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4"}), w, h)
    noisy = geometry.patches_per_sheet(instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "margins": (3, 3, 3, 3),
         "helper_markers": True, "edge_spacers": True,
         "layout_mode": "area_first", "clip_content_mode": "notes",
         "clip_band": 26.0}), w, h)
    assert noisy == plain
    for asked, got in (((6.0, 6.0), (7.0, 8.9)), ((30.0, 30.0), (20.0, 20.0)),
                       ((9.0, 12.0), (9.0, 12.0))):
        g = instruments.geom_from_build_kwargs(
            {"instrument": "IO2", "paper": "A4", "patch_w": asked[0],
             "patch_h": asked[1]})
        assert (g.pwid, g.plen) == got


@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("n", [1, 37, 504, 1300])
def test_every_patch_run_and_mark_is_on_the_sheet_and_clear(tmp_path, paper,
                                                            n):
    from workflow.i1io import table_facts as F
    from workflow.i1io.chart import mark_zone, marks
    result, side = _build(tmp_path, n, paper)
    w, h = side["paper_mm"]
    assert w < h and h <= F.REACH_MM.value[0] and w <= F.REACH_MM.value[1]
    zones = [mark_zone(m) for m in marks(w, h)]
    seen = 0
    for page in side["pages"]:
        for strip in page["strips"]:
            y0, y1 = strip["run_mm"]
            assert y0 >= F.RUN_EDGE_MM.value - 1e-6
            assert y1 <= h - F.RUN_EDGE_MM.value + 1e-6
            centres = [p["centre_mm"] for p in strip["patches"]]
            assert all(abs(c[0] - strip["x_mm"]) < 1e-6 for c in centres)
            assert centres[0][1] - 5.0 - y0 == pytest.approx(F.RUN_MM.value)
            run = (strip["x_mm"] - 4.0, y0, strip["x_mm"] + 4.0, y1)
            for z in zones:
                assert not (run[0] < z[2] and z[0] < run[2]
                            and run[1] < z[3] and z[1] < run[3])
            seen += len(centres)
    assert seen == result.layout.total_patches


def test_the_marks_are_in_the_order_the_person_aims(tmp_path):
    """On the table (the sheet a quarter turn clockwise) 1 is top-left, 2
    bottom-left, 3 bottom-right; on the page bottom-left, bottom-right and
    top-right."""
    from workflow.i1io.table_facts import MARK_INSET_MM
    _, side = _build(tmp_path, 50)
    w, h = side["paper_mm"]
    i = MARK_INSET_MM.value
    got = [(m["number"], m["corner_on_table"], m["centre_mm"])
           for m in side["marks_mm"]]
    assert got == [(1, "top-left", [i, h - i]),
                   (2, "bottom-left", [w - i, h - i]),
                   (3, "bottom-right", [w - i, i])]


def test_the_marks_are_printed_where_the_side_file_says(tmp_path):
    from PIL import Image
    result, side = _build(tmp_path, 50)
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    s = 150 / 25.4
    for m in side["marks_mm"]:
        cx, cy = m["centre_mm"]
        for dx, dy in ((0, 0), (2.8, 0), (-2.8, 0), (0, 2.8), (0, -2.8)):
            assert img[round((cy + dy) * s), round((cx + dx) * s)] < 100
    corner = img[: round(20 * s), : round(20 * s)]
    assert corner.min() > 200          # the page's top-left: no mark


def test_the_ti2_names_the_family_and_the_table_and_round_trips(tmp_path):
    from ui.ti2_loader import read_target_instrument
    from workflow.i1io.support import chart_names_i1io, is_i1io_instrument_name
    result, side = _build(tmp_path, 40)
    text = result.ti2_path.read_text(encoding="utf-8")
    assert 'TARGET_INSTRUMENT "X-Rite i1iO"' in text
    assert 'KEYWORD "CHROMIQ_I1IO_LAYOUT"\nCHROMIQ_I1IO_LAYOUT "1"' in text
    assert 'KEYWORD "CHROMIQ_I1IO_TABLE"\nCHROMIQ_I1IO_TABLE "i1iO 2"' in text
    assert read_target_instrument(result.ti2_path) == "X-Rite i1iO"
    assert chart_names_i1io(result.ti2_path) is True
    assert (side["table_model"], side["head_model"]) == ("i1iO 2", "i1Pro 2")
    for name in ("X-Rite i1iO", "x-rite i1io", '"X-Rite i1iO"', "i1iO",
                 "X-Rite i1iO 3", "GretagMacbeth i1iO"):
        assert is_i1io_instrument_name(name)
    for name in ("GretagMacbeth i1 Pro", "i1iSis", "X-Rite i1iSis 2", "",
                 None, "i1io2x", "i1iO 2", "X-Rite i1iO2"):
        assert not is_i1io_instrument_name(name)


def test_every_strip_is_lettered_and_its_patches_numbered(tmp_path):
    """The engine's own naming, as on every ChromIQ chart: the line the arm
    scans is a strip with a letter, patches along it numbered from its
    start; small charts are few strips, not many short ones."""
    import re
    result, side = _build(tmp_path, 1056)
    for page in side["pages"]:
        for strip in page["strips"]:
            locs = [p["loc"] for p in strip["patches"]]
            letter = re.match(r"[A-Z]+", locs[0]).group(0)
            assert locs == [f"{letter}{i}" for i in range(1, len(locs) + 1)]
    text = result.ti2_path.read_text(encoding="utf-8")
    assert 'STEPS_IN_PASS "24"' in text
    small, side2 = _build(tmp_path / "s" if (tmp_path / "s").mkdir() is None
                          else tmp_path, 100)
    assert len(side2["pages"][0]["strips"]) == 5      # 100 = 4 x 24 + 4


def test_the_side_file_and_the_strips_json_agree_patch_for_patch(tmp_path):
    result, side = _build(tmp_path, 300)
    strips = json.loads((tmp_path / "c.strips.json").read_text(encoding="utf-8"))
    s = strips["dpi"] / 25.4
    rects = {(r["page"], r["loc"]): r for r in strips["patches"]}
    ids = {}
    for line in result.ti2_path.read_text(encoding="utf-8").split(
            "BEGIN_DATA\n", 1)[1].splitlines():
        if line.startswith("END_DATA"):
            break
        tok = line.split()
        ids[tok[1].strip('"')] = int(tok[0])
    for page in side["pages"]:
        for strip in page["strips"]:
            for p in strip["patches"]:
                r = rects[(page["page"] - 1, p["loc"])]
                cx, cy = p["centre_mm"]
                assert abs((r["x"] + r["w"] / 2) / s - cx) < 0.5
                assert abs((r["y"] + r["h"] / 2) / s - cy) < 0.5
                assert ids[p["loc"]] == p["sample_id"]


@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("kw", [{}, {"spacer_mode": "bw"},
                                {"spacer_mode": "none"}])
def test_no_ink_on_a_scan_line_outside_the_patches(tmp_path, paper, kw):
    """Basti, 2026-11-13: the instrument reads all through the run-in and the
    run-out, so nothing may be printed there (the spacers sit BETWEEN the
    patches, never at a strip's ends). Measured on the printed raster: every
    pixel of every run, over the strip's full width, is paper white."""
    from PIL import Image
    result, side = _build(tmp_path, 504, paper, **kw)
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    s = 150 / 25.4
    for strip in side["pages"][0]["strips"]:
        y0, y1 = strip["run_mm"]
        x = strip["x_mm"]
        first = strip["patches"][0]["centre_mm"][1] - 5.0
        last = strip["patches"][-1]["centre_mm"][1] + 5.0
        left, right = round((x - 4.0) * s) + 1, round((x + 4.0) * s) - 1
        for a, b in ((y0, first), (last, y1)):
            band = img[round(a * s) + 1:round(b * s) - 1, left:right]
            assert band.size and band.min() >= 250, (x, a, b)


def test_a_chart_of_several_sheets_has_marks_and_a_page_on_each(tmp_path):
    from PIL import Image
    result, side = _build(tmp_path, 700)
    assert result.layout.pages == 2 and len(result.tiff_paths) == 2
    s = 150 / 25.4
    for tif in result.tiff_paths:
        img = np.asarray(Image.open(tif).convert("L"))
        for m in side["marks_mm"]:
            cx, cy = m["centre_mm"]
            assert img[round(cy * s), round(cx * s)] < 100


def test_a_cmyk_chart_carries_the_marks_in_black_ink_only(tmp_path):
    import tifffile
    result, side = _build(tmp_path, 60, rep="CMYK")
    arr = tifffile.imread(str(result.tiff_paths[0]))
    s = 150 / 25.4
    cx, cy = side["marks_mm"][0]["centre_mm"]
    px = arr[round(cy * s), round(cx * s)]
    assert px[3] > 200 and max(px[:3]) == 0


def test_a_landscape_or_oversized_sheet_is_refused():
    from workflow.i1io.chart import I1ioSheetRefused, sheet_size
    with pytest.raises(I1ioSheetRefused):
        sheet_size("A4R")
    with pytest.raises(I1ioSheetRefused):
        sheet_size("A3")
    assert sheet_size("A4") == (210.0, 297.0)


def test_the_pdf_carries_the_marks_too(tmp_path):
    import fitz
    result, side = _build(tmp_path, 40, export_pdf=True)
    with fitz.open(result.pdf_path) as pdf:
        pix = pdf[0].get_pixmap(dpi=100)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)[..., :3].mean(axis=2)
    s = 100 / 25.4
    for m in side["marks_mm"]:
        cx, cy = m["centre_mm"]
        assert img[round(cy * s), round(cx * s)] < 120


def test_the_scan_numbers_follow_from_the_recorded_timing():
    from workflow.i1io import table_facts as F
    design = F.SCAN_DESIGN_SPEED_MM_S.value
    fastest = max(F.SCAN_SPEEDS_MM_S.value)
    assert F.readings_per_patch(F.PATCH_ALONG_MM.value, design) >= \
        F.SCAN_SAFE_READINGS.value
    (alo, ahi), (clo, chi) = F.patch_limits_mm()
    assert alo >= F.min_patch_length_mm() and alo <= F.PATCH_ALONG_MM.value
    assert F.RUN_MM.value >= F.run_in_mm()
    clean = ((F.PATCH_ALONG_MM.value - F.APERTURE_MM.value)
             / (fastest * F.SCAN_READING_INTERVAL_S.value)) * 2 / 3
    assert clean > F.ARGYLL_MIN_SAMPLES.value
    assert clo == 7.0 and F.PATCH_ACROSS_MM.value >= clo


def test_the_logo_never_costs_a_patch(tmp_path):
    """Basti: the logo only where no patch could be. It is no layout input
    (the capacity is the geometry's own) and lies in the text column beside
    the strips, never over a patch or a run."""
    from workflow.layout_engine import geometry, instruments, papers
    for i, (paper, kw) in enumerate((("A4", {}), ("Letter", {}),
                                     ("A4", {"patch_w": 20.0, "patch_h": 20.0}),
                                     ("A4", {"margins": (40, 30, 15, 30)}))):
        d = tmp_path / str(i)
        d.mkdir()
        result, side = _build(d, 60, paper, **kw)
        g = instruments.geom_from_build_kwargs({"instrument": "IO2",
                                                "paper": paper, **kw})
        w, h = papers.dimensions_mm(paper)
        assert result.layout.patches_per_page == geometry.patches_per_sheet(g, w, h)
        box = side["pages"][0]["wordmark_mm"]
        assert box is not None
        for strip in side["pages"][0]["strips"]:
            run = (strip["x_mm"] - g.pwid / 2, strip["run_mm"][0],
                   strip["x_mm"] + g.pwid / 2, strip["run_mm"][1])
            assert not (box[0] < run[2] and run[0] < box[2]
                        and box[1] < run[3] and run[1] < box[3])


def test_margins_are_the_persons_but_never_below_the_safe_minimum():
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    for asked, count in (((3, 3, 3, 3), 504), ((40, 40, 40, 40), 304)):
        g = instruments.geom_from_build_kwargs(
            {"instrument": "IO2", "paper": "A4", "margins": asked})
        assert geometry.patches_per_sheet(g, w, h) == count


def test_every_number_has_a_source_and_a_confidence():
    from workflow.i1io import table_facts as F
    record = F.as_record()
    for name, fact in record.items():
        assert fact["source"], name
        assert fact["confidence"] in (F.VERIFIED, F.PUBLISHED, F.LIKELY,
                                      F.OURS), name


def test_a_patch_set_fills_the_pages_in_order(tmp_path):
    from workflow.layout_engine.ti1_reader import read_ti1
    result, side = _build(tmp_path, 1008)
    assert (result.layout.pages, result.layout.padding) == (2, 0)
    ti1 = read_ti1(tmp_path / "c.ti1")
    rows = {}
    for line in result.ti2_path.read_text(encoding="utf-8").split(
            "BEGIN_DATA\n", 1)[1].splitlines():
        if line.startswith("END_DATA"):
            break
        tok = line.split()
        rows[int(tok[0])] = [float(v) for v in tok[2:5]]
    for i, (dev, _xyz) in enumerate(ti1.patches, start=1):
        assert rows[i] == pytest.approx(list(dev), abs=1e-6)
    ids = sorted(p["sample_id"] for pg in side["pages"] for st in pg["strips"]
                 for p in st["patches"])
    assert ids == list(range(1, 1009))


@pytest.mark.parametrize("n,partial", [(504, False), (490, True)])
def test_the_i1profiler_route_of_the_notice_works_for_an_i1io_run(tmp_path,
                                                                  n, partial):
    """The run's i1Profiler patch-set files are written for an i1iO chart,
    and a measurement made in i1Profiler from them (patch-list order, device
    values) is accepted; a chart with fill-up patches reads as partial, as
    for any engine chart (fill-up counts, Knut's confirmed ruling)."""
    from workflow.chart_exports import write_sidecars
    from workflow.layout_engine.ti1_reader import read_ti1
    from workflow.measurement_import import assess
    result, _side = _build(tmp_path, n)
    exports = write_sidecars(tmp_path / "c.ti1", tmp_path / "exports", "c")
    names = sorted(p.name for p in exports)
    assert "c-i1profiler.txt" in names and "c-i1profiler.pxf" in names
    ti1 = read_ti1(tmp_path / "c.ti1")
    body = []
    for i, (dev, _xyz) in enumerate(ti1.patches, start=1):
        y = 5.0 + 0.9 * (dev[0] + dev[1] + dev[2]) / 3.0
        body.append(f'{i} "P{i}" ' + " ".join(f"{v:.4f}" for v in dev)
                    + f" {y * 0.95:.4f} {y:.4f} {y * 0.82:.4f}")
    m = tmp_path / "measured.ti3"
    m.write_text(
        'CTI3   \n\nDESCRIPTOR "i1Profiler export, converted"\n'
        'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(body)}\nBEGIN_DATA\n"
        + "\n".join(body) + "\nEND_DATA\n", encoding="utf-8")
    verdict = assess(m, result.ti2_path)
    assert verdict.ok, verdict
    assert verdict.partial is partial


def test_the_turned_i1profiler_option_says_why_an_i1io_chart_has_no_match(
        tmp_path):
    from workflow.i1profiler_turned import plan_for
    result, _ = _build(tmp_path, 60)
    strips = json.loads((tmp_path / "c.strips.json").read_text(encoding="utf-8"))
    strips["recipe"] = {"instrument": "IO2", "paper": "A4"}
    (tmp_path / "c.channels.json").write_text(json.dumps({"layout": strips}),
                                              encoding="utf-8")
    plan = plan_for(result.ti2_path)
    assert not plan.qualifies
    assert any("i1iO table" in r and "3.8.6" in r for r in plan.reasons), \
        plan.reasons
