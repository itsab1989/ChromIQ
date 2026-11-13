"""THE i1iO TABLE CHART (Beta): made for scanning along the rows, readable by
position, and named so the Measure tab knows it.

Basti, 2026-11-13: an "i1iO" entry in Create Chart that makes a chart with
ChromIQ's own layout engine ("we have absolute freedom when it comes to
creating charts"), and ``.ti2`` files that carry the instrument name. What
is held here:

* the geometry: every patch, every row's run-in and run-out and every aiming
  mark lies on the sheet and inside the arm's reach, nothing touches a mark,
  the rows run along the long side, and the capacity is the geometry's own;
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


def _build(tmp_path, n, paper="A4R", rep="RGB", **kw):
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path / "c.ti1", n, rep)
    result = chart.build_chart(ti1, tmp_path / "c", instrument="IO2",
                               paper=paper, dpi=150, **kw)
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    return result, side


@pytest.mark.parametrize("paper,labels,cols,rows", [
    ("A4R", True, 23, 21), ("A4R", False, 24, 21),
    ("LetterR", True, 21, 22), ("LetterR", False, 22, 22)])
def test_the_capacity_is_the_geometrys_own(paper, labels, cols, rows):
    """483 patches on A4 landscape with the row numbers (the default), 504
    without them; 462 and 484 on Letter landscape. Computed from the patch
    size, the 1 mm gap along the rows and the margins of `table_facts`, not
    looked up."""
    from workflow.layout_engine import geometry, instruments, papers
    g = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper,
         "row_indicators": None if labels else False})
    w, h = papers.dimensions_mm(paper)
    assert geometry.patches_per_sheet(g, w, h) == cols * rows
    assert (g.pwid, g.plen, g.pspa, g.rrsp) == (10.0, 8.0, 0.0, 11.0)


def test_whatever_a_recipe_asks_for_the_i1io_keeps_its_own_layout():
    """Spacers, a clip border, helper markers, other margins or an
    area-first layout asked of an i1iO chart change nothing: its capacity is
    the same as with nothing asked. A patch size is kept inside the table's
    limits: 6 x 6 mm comes out 8.9 x 7 mm, 30 x 30 mm comes out 20 x 20."""
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4R")
    plain = geometry.patches_per_sheet(instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4R"}), w, h)
    noisy = geometry.patches_per_sheet(instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4R",
         "spacer_on": True, "margins": (3, 3, 3, 3),
         "helper_markers": True,
         "layout_mode": "area_first", "clip_content_mode": "notes",
         "clip_band": 26.0}), w, h)
    assert noisy == plain
    for asked, got in (((6.0, 6.0), (8.9, 7.0)), ((30.0, 30.0), (20.0, 20.0)),
                       ((12.0, 9.0), (12.0, 9.0))):
        g = instruments.geom_from_build_kwargs(
            {"instrument": "IO2", "paper": "A4R", "patch_w": asked[0],
             "patch_h": asked[1]})
        assert (g.pwid, g.plen) == got


@pytest.mark.parametrize("paper", ["A4R", "LetterR"])
@pytest.mark.parametrize("n", [1, 37, 483, 1300])
def test_every_patch_run_and_mark_is_on_the_sheet_and_clear(tmp_path, paper,
                                                            n):
    from workflow.i1io import table_facts as F
    from workflow.i1io.chart import mark_zone, marks
    result, side = _build(tmp_path, n, paper)
    w, h = side["paper_mm"]
    assert w <= F.REACH_MM.value[0] and h <= F.REACH_MM.value[1]
    zones = [mark_zone(m) for m in marks(w, h)]
    seen = 0
    for page in side["pages"]:
        boxes = []
        for row in page["rows"]:
            x0, x1 = row["run_mm"]
            assert x0 >= F.RUN_EDGE_MM.value - 1e-6
            assert x1 <= w - F.RUN_EDGE_MM.value + 1e-6
            centres = [p["centre_mm"] for p in row["patches"]]
            # a row runs along X, every patch at the row's height
            assert all(abs(c[1] - row["y_mm"]) < 1e-6 for c in centres)
            assert centres == sorted(centres)
            assert centres[0][0] - 5.0 - x0 == pytest.approx(F.RUN_MM.value)
            assert x1 - (centres[-1][0] + 5.0) == pytest.approx(F.RUN_MM.value)
            for cx, cy in centres:
                box = (cx - 5.0, cy - 4.0, cx + 5.0, cy + 4.0)
                assert 0 <= box[0] and box[2] <= w and 0 <= box[1] and box[3] <= h
                for z in zones:
                    assert not (box[0] < z[2] and z[0] < box[2]
                                and box[1] < z[3] and z[1] < box[3])
                boxes.append(box)
                seen += 1
        # no two patches overlap
        boxes.sort()
        for a, b in zip(boxes, boxes[1:]):
            assert not (a[0] < b[2] - 1e-6 and b[0] < a[2] - 1e-6
                        and a[1] < b[3] - 1e-6 and b[1] < a[3] - 1e-6)
    assert seen == result.layout.total_patches
    assert side["page_count"] == result.layout.pages


def test_the_marks_are_in_the_order_the_person_aims(tmp_path):
    _, side = _build(tmp_path, 50)
    w, h = side["paper_mm"]
    got = [(m["number"], m["corner"], m["centre_mm"]) for m in side["marks_mm"]]
    from workflow.i1io.table_facts import MARK_INSET_MM
    i = MARK_INSET_MM.value
    assert got == [(1, "top-left", [i, i]),
                   (2, "bottom-left", [i, h - i]),
                   (3, "bottom-right", [w - i, h - i])]


def test_the_marks_are_printed_where_the_side_file_says(tmp_path):
    """The centre pixel of every mark's cross is ink, and so is a point on
    each arm; the top-right corner, where there is no mark, is blank."""
    from PIL import Image
    result, side = _build(tmp_path, 50)
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    s = 150 / 25.4
    for m in side["marks_mm"]:
        cx, cy = m["centre_mm"]
        for dx, dy in ((0, 0), (2.8, 0), (-2.8, 0), (0, 2.8), (0, -2.8)):
            assert img[round((cy + dy) * s), round((cx + dx) * s)] < 100
    w, _ = side["paper_mm"]
    corner = img[: round(20 * s), round((w - 20) * s):]
    assert corner.min() > 200


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
    assert side["instrument"] == "X-Rite i1iO"
    assert (side["table_model"], side["head_model"]) == ("i1iO 2", "i1Pro 2")
    for name in ("X-Rite i1iO", "x-rite i1io", '"X-Rite i1iO"', "i1iO",
                 "X-Rite i1iO 3", "GretagMacbeth i1iO"):
        assert is_i1io_instrument_name(name)
    # "i1iO 2" alone is i1Profiler's own name, written into measurements by
    # older imports: never taken for a chart of ours.
    for name in ("GretagMacbeth i1 Pro", "i1iSis", "X-Rite i1iSis 2", "",
                 None, "i1io2x", "i1iO 2", "X-Rite i1iO2"):
        assert not is_i1io_instrument_name(name)


def test_the_side_file_and_the_strips_json_agree_patch_for_patch(tmp_path):
    """The measuring step drives the arm from the side file; the preview
    draws from `.strips.json`. Both must put every location in one place,
    and every location must carry the sample the `.ti2` gives it."""
    from workflow.layout_engine.ti1_reader import read_ti1  # noqa: F401
    result, side = _build(tmp_path, 300)
    strips = json.loads((tmp_path / "c.strips.json").read_text())
    s = strips["dpi"] / 25.4
    rects = {(r["page"], r["loc"]): r for r in strips["patches"]}
    ids = {}
    for line in result.ti2_path.read_text().split("BEGIN_DATA\n", 1)[1].splitlines():
        if line.startswith("END_DATA"):
            break
        tok = line.split()
        ids[tok[1].strip('"')] = int(tok[0])
    for page in side["pages"]:
        for row in page["rows"]:
            for p in row["patches"]:
                r = rects[(page["page"] - 1, p["loc"])]
                cx, cy = p["centre_mm"]
                assert abs((r["x"] + r["w"] / 2) / s - cx) < 0.5
                assert abs((r["y"] + r["h"] / 2) / s - cy) < 0.5
                assert ids[p["loc"]] == p["sample_id"]


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


def test_a_portrait_or_oversized_sheet_is_refused():
    from workflow.i1io.chart import I1ioSheetRefused, sheet_size
    with pytest.raises(I1ioSheetRefused):
        sheet_size("A4")
    with pytest.raises(I1ioSheetRefused):
        sheet_size("420x297")
    assert sheet_size("A4R") == (297.0, 210.0)


def test_the_pdf_carries_the_marks_too(tmp_path):
    import fitz
    result, side = _build(tmp_path, 40, export_pdf=True)
    with fitz.open(result.pdf_path) as pdf:
        page = pdf[0]
        pix = page.get_pixmap(dpi=100)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)[..., :3].mean(axis=2)
    s = 100 / 25.4
    for m in side["marks_mm"]:
        cx, cy = m["centre_mm"]
        assert img[round(cy * s), round(cx * s)] < 120


def test_the_scan_numbers_follow_from_the_recorded_timing():
    """The patch length and the run-in are derived from the reading interval
    and the speeds seen, not guessed: at the design speed every patch gets
    the safe number of readings, the gap between neighbours stays inside
    i1Profiler's 20 % limit, and the run-in covers the shortest trigger
    delay seen at the fastest speed. After the aperture's smear and
    Argyll's two-thirds trim a patch keeps more readings than Argyll's
    minimum even at the fastest speed recorded."""
    from workflow.i1io import table_facts as F
    design = F.SCAN_DESIGN_SPEED_MM_S.value
    fastest = max(F.SCAN_SPEEDS_MM_S.value)
    assert F.readings_per_patch(F.PATCH_ALONG_MM.value, design) >= \
        F.SCAN_SAFE_READINGS.value
    (alo, ahi), (clo, chi) = F.patch_limits_mm()
    assert alo >= F.min_patch_length_mm() and alo <= F.PATCH_ALONG_MM.value
    assert F.SCAN_GAP_MM.value <= F.GAP_MAX_FRACTION.value * alo
    assert F.RUN_MM.value >= F.run_in_mm(fastest)
    clean = ((F.PATCH_ALONG_MM.value - F.APERTURE_MM.value)
             / (fastest * F.SCAN_READING_INTERVAL_S.value)) * 2 / 3
    assert clean > F.ARGYLL_MIN_SAMPLES.value
    assert clo == 7.0 and F.PATCH_ACROSS_MM.value >= clo


def test_the_wordmark_and_the_sheet_text_cost_no_patch(tmp_path):
    """The ChromIQ wordmark sits in the top band and the sheet text on the
    name line: the patch count is the same with them as without."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    r1, _ = _build(tmp_path / "a", 483)
    r2, side = _build(tmp_path / "b", 483, chart_text="Epson P900 · {date}")
    assert r1.layout.patches_per_page == r2.layout.patches_per_page == 483


def test_every_number_has_a_source_and_a_confidence():
    from workflow.i1io import table_facts as F
    record = F.as_record()
    assert {"REACH_MM", "APERTURE_MM", "PATCH_ALONG_MM", "RUN_MM",
            "MARK_INSET_MM"} <= set(record)
    for name, fact in record.items():
        assert fact["source"], name
        assert fact["confidence"] in (F.VERIFIED, F.PUBLISHED, F.LIKELY,
                                      F.OURS), name


def test_a_patch_set_fills_the_pages_in_order(tmp_path):
    """Any patch set (targen's, a loaded file, the editor's) is laid out
    whole: two full A4 pages hold exactly 966 patches with no padding, and
    every .ti2 SAMPLE_ID carries the .ti1 patch of the same number, so the
    patch set's order is the measurement's order whatever the randomising
    put where; the side file names every one of them once."""
    from workflow.layout_engine.ti1_reader import read_ti1
    result, side = _build(tmp_path, 966)
    assert (result.layout.pages, result.layout.padding) == (2, 0)
    ti1 = read_ti1(tmp_path / "c.ti1")
    rows = {}
    for line in result.ti2_path.read_text().split("BEGIN_DATA\n", 1)[1].splitlines():
        if line.startswith("END_DATA"):
            break
        tok = line.split()
        rows[int(tok[0])] = [float(v) for v in tok[2:5]]
    assert len(rows) == 966
    for i, (dev, _xyz) in enumerate(ti1.patches, start=1):
        assert rows[i] == pytest.approx(list(dev), abs=1e-6)
    ids = sorted(p["sample_id"] for pg in side["pages"] for r in pg["rows"]
                 for p in r["patches"])
    assert ids == list(range(1, 967))


@pytest.mark.parametrize("paper,along,rows,count", [
    ("A4R", None, None, 483), ("A4R", 0.0, 0.0, 525), ("A4R", 1.0, 1.0, 437),
    ("LetterR", None, None, 462), ("LetterR", 0.0, 0.0, 506),
    ("LetterR", 1.0, 1.0, 420), ("A4R", 9.0, 9.0, 336)])
def test_the_two_gaps_are_the_engines_own_controls_kept_apart(paper, along,
                                                             rows, count):
    """"Strip gap" is the separator along the scan (default 1 mm, at most
    20 % of the patch length), "Inter-patch gap" the gap between rows
    (default none, at most 3 mm). Each changes the capacity on its own."""
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"instrument": "IO2", "paper": paper}
    if along is not None:
        kw.update(strip_gap=along, inter_patch=rows)
    g = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm(paper)
    assert geometry.patches_per_sheet(g, w, h) == count


@pytest.mark.parametrize("n,partial", [(483, False), (470, True)])
def test_the_i1profiler_route_of_the_notice_works_for_an_i1io_run(tmp_path,
                                                                  n, partial):
    """What M-I1IO-NOT-YET says works today: the run's i1Profiler patch-set
    files are written for an i1iO chart (as for any RGB chart), and a
    measurement made in i1Profiler from them, which comes back in the patch
    list's order with its device values, is accepted as a measurement of the
    i1iO chart. A full sheet (what Guided always makes) comes in whole; a
    chart with fill-up patches comes in as partial, because fill-up patches
    count and i1Profiler's own chart has none (Knut's confirmed ruling,
    `measurement_state.expected_patches`), exactly as for any engine chart."""
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
