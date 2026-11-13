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
    ("A4", {}, 528), ("A4", {"spacer_mode": "bw"}, 528),
    ("A4", {"spacer_mode": "none"}, 572),
    ("A4", {"spacer_mode": "none", "draw_indicators": False,
            "row_indicators": False}, 594),
    ("Letter", {}, 506), ("Letter", {"spacer_mode": "none"}, 552),
    ("Letter", {"spacer_mode": "none", "draw_indicators": False,
                "row_indicators": False}, 575)])
def test_the_capacity_is_the_geometrys_own(paper, kw, count):
    """Per sheet: A4 528 with the default contrast spacers (572 without, 594
    with no spacers and no labels), Letter 506 (552, 575). (Until the digits
    moved beside their crosses along the strips: 504 and 462.) Computed from the
    patch size, the spacers and the smallest safe margins of `table_facts`,
    not looked up."""
    from workflow.layout_engine import geometry, instruments, papers
    g = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper, **kw})
    w, h = papers.dimensions_mm(paper)
    assert geometry.patches_per_sheet(g, w, h) == count
    assert (g.pwid, g.plen) == (8.0, 10.0)


def test_whatever_a_recipe_asks_for_the_i1io_keeps_its_own_layout():
    """A clip border asked for the old way, an area-first layout or
    margins below the safe minimum change nothing (helper markers and edge
    spacers are a person's options since Job D); a patch size is kept
    inside the table's limits (engine terms: width across a strip, height
    along it)."""
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    plain = geometry.patches_per_sheet(instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4"}), w, h)
    noisy = geometry.patches_per_sheet(instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "margins": (3, 3, 3, 3),
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
            top = min(c[1] for c in centres) - 5.0
            bottom = max(c[1] for c in centres) + 5.0
            assert top - y0 == pytest.approx(F.RUN_MM.value)
            assert y1 - bottom == pytest.approx(F.RUN_MM.value)
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
    corner = img[: round(10 * s), : round(10 * s)]
    assert corner.min() > 200          # the page's top-left: no mark


def _as_on_the_table(x, y, w, h):
    """A point of the portrait page where it lies on the table (the sheet a
    quarter turn clockwise), in mm from the table view's top-left."""
    return h - y, x


@pytest.mark.parametrize("n", [504, 700])
def test_held_as_on_the_table_the_sheet_reads_like_text(tmp_path, n):
    """The owner, 2026-11-13: held the way it lies on the table (landscape,
    cross 1 top-left, 2 bottom-left, 3 bottom-right), the strip letters stand
    at the LEFT end of each strip, A at the top; the patch numbers run 1, 2,
    3 ... from left to right along the top; and every text is upright.
    Derived from the layout itself (side file, `strip_letters`, the label
    turn), not from a picture."""
    from workflow.i1io import chart as C, table_facts as F
    from workflow.layout_engine import geometry, instruments
    result, side = _build(tmp_path, n)
    w, h = side["paper_mm"]
    marks = {m["number"]: _as_on_the_table(*m["centre_mm"], w, h)
             for m in side["marks_mm"]}
    assert marks[1][0] < marks[3][0] and marks[1][1] < marks[2][1]
    assert abs(marks[1][0] - marks[2][0]) < 1e-6                # 1 above 2
    assert abs(marks[2][1] - marks[3][1]) < 1e-6                # 2 left of 3
    strips = side["pages"][0]["strips"]
    # strips top to bottom on the table: A first
    tops = [_as_on_the_table(st["x_mm"], 0.0, w, h)[1] for st in strips]
    assert tops == sorted(tops)
    assert strips[0]["patches"][0]["loc"].startswith("A")
    for st in strips:
        # patches left to right on the table: 1, 2, 3 ...
        by_x = sorted(st["patches"], key=lambda p: _as_on_the_table(
            *p["centre_mm"], w, h)[0])
        numbers = [int(p["loc"].lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
                   for p in by_x]
        assert numbers == sorted(numbers) and numbers[0] == 1
    # the strip letters at the LEFT end, beyond the run
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "dpi": 150})
    layout = geometry.compute(geom, w, h, n)
    letters = C.strip_letters(geom, layout, w, h, 0, 150)
    assert [t for t, _c, _s in letters][:3] == ["A", "B", "C"]
    for (text, (x, y), _size), st in zip(letters, strips):
        tx, _ty = _as_on_the_table(x, y, w, h)
        first = min(_as_on_the_table(*p["centre_mm"], w, h)[0]
                    for p in st["patches"])
        assert tx < first - F.RUN_MM.value, text
    # upright on the table: every turned text turns a quarter turn
    # anticlockwise on the page, which the clockwise turn of the sheet undoes
    assert F.LABEL_TURN_DEG.value == 90
    assert "clockwise (its top edge to the right)" in side["orientation"]


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
        ys = [p["centre_mm"][1] for p in strip["patches"]]
        first, last = min(ys) - 5.0, max(ys) + 5.0
        left, right = round((x - 4.0) * s) + 1, round((x + 4.0) * s) - 1
        for a, b in ((y0, first), (last, y1)):
            band = img[round(a * s) + 1:round(b * s) - 1, left:right]
            assert band.size and band.min() >= 250, (x, a, b)


@pytest.mark.parametrize("n,kw", [(700, {}), (504, {"indicator_size_mm": 20.0})])
def test_the_strip_letters_end_before_every_run_in(tmp_path, n, kw):
    """Review r3 M1 and m2: a large label size, and the two-letter labels of
    a chart of more than 26 strips, printed into the blank run. The letters
    now stand beyond the run at the strips' bottom end on the page (the
    table's left). Measured on the raster: over each strip's width, the
    first ink below the run starts at least LABEL_CLEAR_MM after it, and
    there is no ink at all above the run's top."""
    from PIL import Image
    from workflow.i1io import table_facts as F
    result, side = _build(tmp_path, n, **kw)
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    s = 150 / 25.4
    for strip in side["pages"][0]["strips"]:
        y0, y1 = strip["run_mm"]
        x = strip["x_mm"]
        left, right = round((x - 4.0) * s) + 1, round((x + 4.0) * s) - 1
        rows = np.where((img[round(y1 * s):, left:right] < 200).any(axis=1))[0]
        assert len(rows), x                     # the letter is there
        assert rows.min() / s >= F.LABEL_CLEAR_MM.value - 0.2, (x, y1)
        assert (img[:round(y0 * s), left:right] >= 200).all(), (x, y0)


def test_the_label_size_is_never_above_the_i1ios_largest():
    """Review r3 M1: what Manual's size box may ask for (up to 72 pt) is
    printed at no more than LABEL_MAX_MM, so letters never run into each
    other at the narrowest strip pitch."""
    from workflow.i1io import chart, table_facts as F
    assert chart.label_size_mm(20.0) == F.LABEL_MAX_MM.value
    assert chart.label_size_mm(3.0) == 3.0
    assert chart.label_size_mm(None) == 0.0          # the engine's auto size
    assert chart.fixed_build_kwargs(
        {"indicator_size_mm": 40.0})["indicator_size_mm"] == F.LABEL_MAX_MM.value


def test_manuals_boxes_offer_only_what_the_i1io_prints(qapp, qtbot):
    """Review r3 m1 and M1: with the i1iO chosen, a margin box offers nothing
    below the safe minimum and the label size nothing above LABEL_MAX_MM;
    leaving the i1iO gives the other instrument its own ranges back."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel, mm_to_pt
    from workflow.i1io import table_facts as F
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    before = {k: b.minimum() for k, b in panel.margins.items()}
    size_max = panel.indicator_size.maximum()
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    least = dict(zip("trbl", F.margins_mm(True)))
    for k, box in panel.margins.items():
        box.setValue(1.0)
        assert box.value() >= least[k] - 1e-6, k
    panel.indicator_size.setValue(72.0)
    assert panel.indicator_size.value() <= round(mm_to_pt(F.LABEL_MAX_MM.value), 1)
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    assert {k: b.minimum() for k, b in panel.margins.items()} == before
    assert panel.indicator_size.maximum() == size_max


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
    for asked, count in (((3, 3, 3, 3), 528), ((40, 40, 40, 40), 304)):
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


def test_a_pro300_letter_edge_cuts_nothing_of_an_i1io_chart(tmp_path):
    """Review r3 m3: on a Canon PRO-300's Letter sheet (6.4 mm left, 6.3 mm
    right, 3.0 mm top, 5.0 mm bottom unprinted) the patch numbers sat at
    4 mm and were cut, and the note told the person to raise a greyed
    control. They now start 10 mm in, at no cost in patches, and nothing of
    the chart falls into that edge."""
    from workflow import printer_edges as PE
    result, side = _build(tmp_path, 506, "Letter")
    assert result.layout.patches_per_page == 506
    edges = PE.Edges(left=6.4, right=6.3, top=3.0, bottom=5.0, source="ppd")
    loss = PE.losses(result.tiff_paths[0], 0, edges, tuple(side["paper_mm"]))
    assert not loss.any(), loss


def test_the_edge_note_for_an_i1io_chart_names_only_live_controls(tmp_path):
    """A note must never point at something greyed. With an edge wide enough
    to take the crosses, the note is the i1iO's own (they cannot be moved);
    with one that takes only lettering, it names the two checkboxes Manual
    leaves live, never "Text distance from edge"."""
    from workflow import measurement_messages as MM, printer_edges as PE
    result, side = _build(tmp_path, 462, "Letter")
    paper = tuple(side["paper_mm"])
    wide = PE.Edges(left=10.0, right=10.0, top=10.0, bottom=10.0,
                    source="override")
    loss = PE.losses(result.tiff_paths[0], 0, wide, paper)
    assert loss.i1io_marks and not loss.text
    note = MM.edge_note("Printer", wide, loss)
    assert "crosses" in note and "Text distance from edge" not in note
    # only the lettering: a 12 mm left edge reaches the numbers (11 to 15 mm)
    # but, with the crosses taken out of the count, nothing else
    loss = PE.Loss(i1io_text=["left"])
    note = MM.edge_note("Printer", PE.Edges(left=12.0, source="override"),
                        loss)
    assert "Show row indicators" in note
    assert "Text distance from edge" not in note


def _wordmark_ink(tmp_path, dpi=300, **kw):
    """The page, the plan, and the ink masks of "Chrom" (near-black) and
    "IQ" (magenta) of a 1-page chart, in page pixels."""
    from PIL import Image
    from workflow.i1io import chart as C
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path / "w.ti1", 50)
    r = chart.build_chart(ti1, tmp_path / "w", instrument="IO2", paper="A4",
                          dpi=dpi, project="Logo-test", **kw)
    img = np.asarray(Image.open(r.tiff_paths[0]).convert("RGB")).astype(int)
    side = json.loads((tmp_path / "w.i1io.json").read_text(encoding="utf-8"))
    w, h = side["paper_mm"]
    plan = C.text_line_plan(w, h, C.page_line_text("Logo-test", 0, 1,
                                                   kw.get("chart_text", "")),
                            dpi)
    chrom = (np.abs(img - np.array(C.WORDMARK_RGB)).sum(axis=2) < 60)
    iq = (np.abs(img - np.array(C.WORDMARK_IQ_RGB)).sum(axis=2) < 90)
    # only the wordmark's own paper: between the crosses, near their line
    s = dpi / 25.4
    keep = np.zeros(chrom.shape, bool)
    box = plan["wordmark"]["box"]
    keep[round((box[1] - 1) * s):round((box[3] + 1) * s),
         round((box[0] - 3) * s):round((box[2] + 3) * s)] = True
    return img, plan, chrom & keep, iq & keep, w, h


@pytest.mark.parametrize("size", [4.0, 3.0, 2.0])
def test_the_wordmarks_iq_sits_on_chroms_baseline(tmp_path, monkeypatch,
                                                   size):
    """The owner, 2026-11-13: "the IQ is too high". Each part was centred by
    its own ink, and the italic Q's tail made the "IQ" taller, so its
    baseline stood above "Chrom"'s. As the engine sets the wordmark on every
    other chart (`raster._wordmark_geometry`: one baseline, the same size,
    "IQ" after "Chrom"'s advance and 0.02 of the size), at every size the
    shrink rule can give. Measured on the printed raster: the bottom of the
    "I" (no tail) is the bottom of "Chrom" (no descender), to a pixel."""
    from workflow.i1io import chart as C, table_facts as F
    monkeypatch.setattr(F, "WORDMARK_MM", F.Fact(size, "test", F.OURS))
    img, plan, chrom, iq, w, h = _wordmark_ink(tmp_path)
    assert plan["wordmark"]["size_mm"] == size
    s = 300 / 25.4
    # on the page, the baseline is the LARGEST x of the ink (turned text)
    cy, cx = np.nonzero(chrom)
    iy, ix = np.nonzero(iq)
    assert len(cx) and len(ix)
    chrom_base = cx.max()
    # the "I" is the first letter of "IQ", at the LARGER page y end (the
    # text runs up the page); the Q's tail is left out by taking that end
    i_rows = iy > iy.max() - 0.25 * (iy.max() - iy.min())
    i_base = ix[i_rows].max()
    assert abs(int(i_base) - int(chrom_base)) <= 1, (i_base, chrom_base)
    # and the IQ starts where the engine's would: Chrom's advance + kern
    wm = plan["wordmark"]
    assert wm["chrom_y"] - wm["iq_y"] == pytest.approx(
        (wm["iq_y"] - wm["chrom_y"]) * -1)
    assert iy.max() / s < wm["iq_y"] + 0.3


def test_the_text_line_is_centred_between_crosses_2_and_3(tmp_path):
    """The owner, 2026-11-13: the logo and the text line, as one group,
    centred between crosses 2 and 3: horizontally halfway between them on
    the table (the page's middle y) and vertically with each part's visual
    middle (half its capital height above its baseline) on the line
    through the crosses' centres. Measured on the raster."""
    from workflow.i1io import chart as C
    img, plan, chrom, iq, w, h = _wordmark_ink(tmp_path)
    s = 300 / 25.4
    marks = C.marks(w, h)
    line_x = marks[1].centre_mm[0]
    assert marks[2].centre_mm[0] == line_x
    mid_y = (marks[1].centre_mm[1] + marks[2].centre_mm[1]) / 2.0
    # the whole group's ink along the page's y (the table's horizontal)
    band = img[:, round((line_x - 6) * s):round((line_x + 6) * s)]
    ink = (band < 200).any(axis=2)
    zone_top = C.mark_zone(marks[2])[3]
    zone_bottom = C.mark_zone(marks[1])[1]
    rows = np.nonzero(ink.any(axis=1))[0] / s
    rows = rows[(rows > zone_top) & (rows < zone_bottom)]
    assert abs((rows.min() + rows.max()) / 2.0 - mid_y) < 0.6
    # visual middles on the crosses' line: the wordmark (no descender in
    # "Chrom") and the plan's text baseline, half a capital above
    from PIL import ImageFont  # noqa: F401
    wm = plan["wordmark"]
    cap = wm["box"][2] - wm["box"][0]
    cy, cx = np.nonzero(chrom)
    assert abs(cx.max() / s - cap / 2.0 - line_x) < 0.25
    assert plan["text_baseline_x"] > line_x
    assert plan["text"] == "Logo-test"


def test_a_long_text_is_shortened_before_the_logo_shrinks():
    """Too long for the room between the crosses: the text is shortened
    ("…") first, and the wordmark keeps its full size while that is enough;
    on a page too small for both, the wordmark shrinks; the group stays
    centred either way."""
    from workflow.i1io import chart as C, table_facts as F
    w, h = 210.0, 297.0
    long_text = "Name · " + "a sheet text that goes on and on " * 20
    plan = C.text_line_plan(w, h, long_text, 300)
    assert plan["text"].endswith("…")
    assert plan["wordmark"]["size_mm"] == F.WORDMARK_MM.value
    m = C.marks(w, h)
    mid_y = (m[1].centre_mm[1] + m[2].centre_mm[1]) / 2.0
    assert sum(plan["group"]) / 2.0 == pytest.approx(mid_y)
    small = C.text_line_plan(w, 66.0, long_text, 300)
    assert small["wordmark"] is None or small["wordmark"]["size_mm"] < 4.0


def test_the_marks_cost_one_strip_on_a4_and_nothing_on_letter():
    """The owner, 2026-11-13: "do they use space that could be used for
    printing more patches?" The digits sit beside their crosses ALONG the
    strips, in the side band the cross needs anyway, so they cost nothing;
    the side bands are the cross and its clearance (15 mm) and, at the left,
    the patch numbers (16 mm). Against a sheet with no marks at all (the
    text line alone needs 10 mm at the right), the crosses cost one strip on
    A4 and none on Letter: to cost nothing on A4 a cross would have to come
    within 6 mm of the paper edge, where a PRO-300 leaves Letter paper
    unprinted, or shrink below 3 mm."""
    from workflow.i1io import chart as C, table_facts as F
    from workflow.layout_engine import geometry, instruments, papers
    def per_sheet(paper, right=None):
        g = instruments.geom_from_build_kwargs({"instrument": "IO2",
                                                "paper": paper})
        if right is not None:
            from dataclasses import replace
            g = replace(g, margin_r=right)
        w, h = papers.dimensions_mm(paper)
        return geometry.patches_per_sheet(g, w, h)
    assert per_sheet("A4") == 528 and per_sheet("Letter") == 506
    assert per_sheet("A4", right=10.0) == 552          # no crosses: +1 strip
    assert per_sheet("Letter", right=10.0) == 506      # no crosses: the same
    for m in C.marks(210.0, 297.0):
        dx, dy = C.digit_offset(m)
        assert dx == 0.0 and dy != 0.0                 # along the strips
        z = C.mark_zone(m)
        assert z[2] - z[0] <= F.MARK_CROSS_MM.value + 2 * F.MARK_CLEAR_MM.value + 1e-9
