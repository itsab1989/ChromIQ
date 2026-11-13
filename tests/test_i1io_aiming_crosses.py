"""THE i1iO's AIMING CROSSES ARE AN OPTION (Beta).

The owner, 2026-11-13: *"in theory we could add an option to turn on the
crosses (or not in turn) and then make even more patches fit a single sheet?
the info should then mention what to aim at. it either knows from how the
chart was created what to tell or should mention both things"*, and: *"without
the crosses then the chromiq logo and probably sheet text would also go
away"*. What is held here:

* the capacity both ways, A4 and Letter (the paper the crosses held goes to
  patches; the text line costs nothing);
* without the crosses: no cross on the sheet, the four corner slots hold
  clearly visible patches of the set (mid to dark, saturated or dark, never
  near white, different from their neighbours), ONLY positions move, the
  order is reproducible from the seed, and the `.ti2`, the TIFF, the
  `.strips.json` and the side file agree;
* every other instrument's order is the seed's, byte for byte;
* the files record what to aim at (`.ti2` CHROMIQ_I1IO_AIM, the side file's
  "aim" and "aim_points"), and a chart without the record is "unknown";
* the text line without the crosses, by the owner's priorities: everything
  fits; the logo dropped; the sheet text dropped; the name kept small; the
  name impossible.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True, scope="module")
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _ti1(path: Path, n: int) -> Path:
    """An RGB set with many light patches, as real sets have (a third of it
    near white), so a corner left to chance would often be pale."""
    rows = []
    for i in range(n):
        if i % 3 == 0:
            dev = [100.0 - (i % 7), 100.0 - (i % 5), 100.0 - (i % 3)]
        else:
            dev = [((i * (7 + 3 * k)) % 101) * 1.0 for k in range(3)]
        rows.append(f"{i + 1} " + " ".join(f"{v:.4f}" for v in dev)
                    + " 50.0 50.0 50.0")
    path.write_text(
        "CTI1\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        'COLOR_REP "RGB"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def _build(folder: Path, n: int, paper="A4", instrument="IO2", **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / "c.ti1", n)
    result = chart.build_chart(ti1, folder / "c", instrument=instrument,
                               paper=paper, dpi=100, seed=4242, **kw)
    return result


def _ti2_rows(path: Path) -> "dict[str, tuple]":
    """``{SAMPLE_LOC: (R, G, B)}`` of a written `.ti2`."""
    text = path.read_text(encoding="utf-8")
    data = text.split("BEGIN_DATA\n", 1)[1].split("END_DATA", 1)[0]
    out = {}
    for line in data.strip().splitlines():
        parts = line.split()
        out[parts[1].strip('"')] = tuple(float(v) for v in parts[2:5])
    return out


def _lab(rgb100):
    from workflow.i1io.chart import _lab_of_rgb
    return _lab_of_rgb(tuple(v * 2.55 for v in rgb100))


# ---- capacity ---------------------------------------------------------------

@pytest.mark.parametrize("paper,kw,on,off", [
    ("A4", {}, 528, 552),
    ("A4", {"spacer_mode": "none"}, 572, 598),
    ("A4", {"spacer_mode": "none", "patch_w": 7.0, "patch_h": 8.9}, 725, 783),
    ("Letter", {}, 506, 528),
    ("Letter", {"spacer_mode": "none"}, 552, 576),
    ("Letter", {"spacer_mode": "none", "patch_w": 7.0, "patch_h": 8.9},
     702, 729)])
def test_the_capacity_both_ways(paper, kw, on, off):
    """The table in docs/design/i1io_table_support.md: default, no spacers,
    and the maximum (no spacers, 7 mm across x 8.9 mm along)."""
    from workflow.i1io import chart
    assert chart.capacity({"paper": paper, **kw}, True) == on
    assert chart.capacity({"paper": paper, **kw}, False) == off


def test_the_crosses_default_on():
    from workflow.i1io import chart
    assert chart.crosses_of({}) is True
    assert chart.fixed_build_kwargs({})[chart.CROSSES_KEY] is True
    assert chart.fixed_build_kwargs(
        {chart.CROSSES_KEY: False})[chart.CROSSES_KEY] is False


# ---- the sheet without crosses ---------------------------------------------

@pytest.fixture(scope="module")
def off_chart(tmp_path_factory):
    folder = tmp_path_factory.mktemp("i1io_off")
    _build(folder, 552, i1io_crosses=False)
    return folder


@pytest.fixture(scope="module")
def on_chart(tmp_path_factory):
    folder = tmp_path_factory.mktemp("i1io_on")
    _build(folder, 528)
    return folder


def test_no_cross_is_printed_without_them(off_chart, on_chart):
    from PIL import Image
    from workflow.i1io import chart
    side = json.loads((off_chart / "c.i1io.json").read_text("utf-8"))
    w, h = side["paper_mm"]
    s = 100 / 25.4
    for folder, inked in ((on_chart, True), (off_chart, False)):
        img = np.asarray(Image.open(folder / "c.tif").convert("L"))
        for m in chart.marks(w, h):
            x, y = (int(round(v * s)) for v in m.centre_mm)
            box = img[y - 3:y + 4, x - 3:x + 4]
            assert (box.min() < 100) == inked, (folder, m)


def test_the_files_record_what_to_aim_at(off_chart, on_chart, tmp_path):
    from workflow.i1io import chart
    for folder, aim in ((on_chart, "crosses"), (off_chart, "corner patches")):
        text = (folder / "c.ti2").read_text("utf-8")
        assert 'KEYWORD "CHROMIQ_I1IO_AIM"' in text
        assert f'CHROMIQ_I1IO_AIM "{aim}"' in text
        side = json.loads((folder / "c.i1io.json").read_text("utf-8"))
        assert side["aim"] == aim
        assert chart.aim_recorded(folder / "c.ti2") == aim
        # whether the numbers 1, 2, 3 are printed (never a second set later)
        digits = "yes" if aim == "crosses" else "no"
        assert 'KEYWORD "CHROMIQ_I1IO_AIM_DIGITS"' in text
        assert f'CHROMIQ_I1IO_AIM_DIGITS "{digits}"' in text
        assert {p["digits_printed"] for p in side["pages"]} == {
            aim == "crosses"}
    # a chart made before the option records nothing: "unknown"
    old = tmp_path / "old.ti2"
    old.write_text(re.sub(r'.*CHROMIQ_I1IO_AIM.*\n', "",
                          (on_chart / "c.ti2").read_text("utf-8")),
                   encoding="utf-8")
    assert chart.aim_recorded(old) == "unknown"
    assert chart.aim_recorded(tmp_path / "missing.ti2") == "unknown"


def test_the_aim_points_are_in_aiming_order_on_page_and_table(off_chart,
                                                             on_chart):
    for folder, target in ((on_chart, "cross"), (off_chart, "patch")):
        side = json.loads((folder / "c.i1io.json").read_text("utf-8"))
        w, h = side["paper_mm"]
        points = side["pages"][0]["aim_points"]
        assert [p["number"] for p in points] == [1, 2, 3]
        assert [p["corner_on_table"] for p in points] == [
            "top-left", "bottom-left", "bottom-right"]
        assert {p["target"] for p in points} == {target}
        (x1, y1), (x2, y2), (x3, y3) = (p["table_mm"] for p in points)
        # on the table: 1 above 2 at the left, 3 right of 2 at the bottom
        assert abs(x1 - x2) < 1e-6 and y2 > y1
        assert abs(y2 - y3) < 1e-6 and x3 > x2
        for p in points:
            px, py = p["page_mm"]
            assert p["table_mm"] == [round(h - py, 4), round(px, 4)]


def test_the_aim_points_are_the_corner_patch_centres(off_chart):
    side = json.loads((off_chart / "c.i1io.json").read_text("utf-8"))
    page = side["pages"][0]
    centres = {}
    for strip in page["strips"]:
        for p in strip["patches"]:
            centres[p["loc"]] = p["centre_mm"]
    for corner, point in zip(("top-left", "bottom-left", "bottom-right"),
                             page["aim_points"]):
        loc = page["corner_patches"][corner]["loc"]
        assert centres[loc] == point["page_mm"]
    # strip A's patch 1 is the table's top left
    assert page["corner_patches"]["top-left"]["loc"] == "A1"


def test_the_corner_patches_are_easy_to_see(off_chart):
    """Mid to dark, saturated or dark, never near white, and different from
    their neighbours: in the .ti2 itself."""
    from workflow.i1io import chart
    from workflow.i1io import table_facts as F
    side = json.loads((off_chart / "c.i1io.json").read_text("utf-8"))
    rows = _ti2_rows(off_chart / "c.ti2")
    steps = int(re.search(r'STEPS_IN_PASS "(\d+)"',
                          (off_chart / "c.ti2").read_text("utf-8")).group(1))
    for corner, rec in side["pages"][0]["corner_patches"].items():
        lab = _lab(rows[rec["loc"]])
        chroma = (lab[1] ** 2 + lab[2] ** 2) ** 0.5
        assert lab[0] <= F.CORNER_MAX_L.value, (corner, lab)
        assert chroma >= F.CORNER_MIN_C.value or \
            lab[0] <= F.CORNER_DARK_L.value, (corner, lab)
        # the neighbours along the strip and in the next strip
        m = re.match(r"([A-Z]+)(\d+)", rec["loc"])
        strip, pos = m.group(1), int(m.group(2))
        near = [f"{strip}{pos + d}" for d in (-1, 1) if 1 <= pos + d <= steps]
        letters = sorted({re.match(r"[A-Z]+", k).group(0) for k in rows},
                         key=lambda t: (len(t), t))
        i = letters.index(strip)
        near += [f"{letters[j]}{pos}" for j in (i - 1, i + 1)
                 if 0 <= j < len(letters)]
        for loc in near:
            if loc in rows:
                assert chart._de(lab, _lab(rows[loc])) >= 10.0, (corner, loc)


def test_only_positions_move(off_chart, tmp_path):
    """The set and its count are unchanged: the .ti2 holds exactly the .ti1's
    patches, and the order differs from the seed's only in the swaps."""
    from workflow.layout_engine import permutation
    rows = _ti2_rows(off_chart / "c.ti2")
    ti1 = _ti1(tmp_path / "x.ti1", 552)
    want = []
    for line in ti1.read_text().split("BEGIN_DATA\n")[1].split(
            "END_DATA")[0].strip().splitlines():
        want.append(tuple(float(v) for v in line.split()[1:4]))
    assert Counter(rows.values()) == Counter(want)
    assert len(rows) == 552
    # against the seed's own order: at most 2 slots per corner differ
    seed_rows = {}
    slots = permutation.location_permutation(552, 4242, True)
    steps = int(re.search(r'STEPS_IN_PASS "(\d+)"',
                          (off_chart / "c.ti2").read_text("utf-8")).group(1))
    for i, slot in enumerate(slots):
        seed_rows[permutation.location_label(slot, steps)] = want[i]
    moved = [k for k in rows if rows[k] != seed_rows[k]]
    assert 0 < len(moved) <= 8


def test_the_order_is_reproducible(off_chart, tmp_path):
    _build(tmp_path / "again", 552, i1io_crosses=False)
    assert (_ti2_rows(tmp_path / "again" / "c.ti2")
            == _ti2_rows(off_chart / "c.ti2"))


def test_tiff_strips_and_side_file_agree_with_the_ti2(off_chart):
    """Every corner patch: the TIFF's colour at the place the .strips.json
    draws it is the .ti2's colour for that SAMPLE_LOC, and the side file
    names the same sample."""
    from PIL import Image
    from workflow.layout_engine.raster import to_display_rgb
    rows = _ti2_rows(off_chart / "c.ti2")
    strips = json.loads((off_chart / "c.strips.json").read_text("utf-8"))
    rect = {r["loc"]: r for r in strips["patches"] if r.get("page", 0) == 0}
    img = np.asarray(Image.open(off_chart / "c.tif").convert("RGB"))
    side = json.loads((off_chart / "c.i1io.json").read_text("utf-8"))
    ids = {}
    for line in (off_chart / "c.ti2").read_text("utf-8").split(
            "BEGIN_DATA\n")[1].split("END_DATA")[0].strip().splitlines():
        parts = line.split()
        ids[parts[1].strip('"')] = int(parts[0])
    for corner, rec in side["pages"][0]["corner_patches"].items():
        r = rect[rec["loc"]]
        cx, cy = int(r["x"] + r["w"] / 2), int(r["y"] + r["h"] / 2)
        want = to_display_rgb(rows[rec["loc"]], "RGB")
        got = tuple(int(v) for v in img[cy, cx])
        assert max(abs(a - b) for a, b in zip(got, want)) <= 1, corner
        assert rec["sample_id"] == ids[rec["loc"]]


def test_every_other_instrument_keeps_the_seeds_order(tmp_path):
    """No chart but an i1iO without crosses is reordered: an i1Pro chart's
    .ti2 is byte for byte the one written from the seed's own order."""
    from workflow.layout_engine import ti2_writer, permutation
    _build(tmp_path / "i1", 300, instrument="i1")
    rows = _ti2_rows(tmp_path / "i1" / "c.ti2")
    steps = int(re.search(r'STEPS_IN_PASS "(\d+)"',
                          (tmp_path / "i1" / "c.ti2").read_text()).group(1))
    total = len(rows)
    slots = permutation.location_permutation(total, 4242, True)
    ti1 = _ti1(tmp_path / "y.ti1", 300)
    want = [tuple(float(v) for v in line.split()[1:4]) for line in
            ti1.read_text().split("BEGIN_DATA\n")[1].split(
                "END_DATA")[0].strip().splitlines()]
    want += [(100.0, 100.0, 100.0)] * (total - 300)
    for i, slot in enumerate(slots):
        loc = permutation.location_label(slot, steps)
        assert rows[loc] == want[i]
    import inspect
    assert "slots: \"list[int] | None\" = None" in inspect.getsource(
        ti2_writer.build_ti2_text)


def test_the_corner_order_is_only_swaps():
    from workflow.i1io import chart
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", chart.CROSSES_KEY: False})
    layout = geometry.compute(geom, w, h, 552)
    from workflow.layout_engine.permutation import location_permutation
    slots = location_permutation(552, 7, True)
    rgbs = [(250, 250, 250)] * 500 + [(40, 60, 160)] * 30 + [(20, 20, 20)] * 22
    out = chart.corner_order(slots, rgbs, 552, geom, layout, w, h)
    assert sorted(out) == sorted(slots)
    changed = [i for i in range(552) if out[i] != slots[i]]
    assert len(changed) <= 8
    for corner, cell in chart.corner_cells(geom, layout, w, h, 0).items():
        i = out.index(cell[0])
        assert rgbs[i] != (250, 250, 250), corner
    # a set with nothing dark keeps its order rather than aim at white
    pale = [(250, 250, 250)] * 552
    assert chart.corner_order(slots, pale, 552, geom, layout, w, h) == slots


# ---- the text line without crosses -----------------------------------------

def _spot(width, length=200.0):
    return {"spot": "bottom edge", "x0": 100.0, "x1": 100.0 + width,
            "y0": 50.0, "y1": 50.0 + length, "mid_y": 50.0 + length / 2.0}


def test_text_everything_fits():
    from workflow.i1io.chart import free_text_plan
    plan = free_text_plan(_spot(10.0), "1/2  ·  My chart", "Matte paper",
                          300)
    assert plan["kept"] == ("name", "sheet text", "logo")
    assert plan["text"] == "1/2  ·  My chart  ·  Matte paper"
    assert plan["name_whole"] and not plan["name_small"]


def test_text_logo_dropped_first():
    """A narrow spot: the logo goes (its smallest size does not fit across
    or along), the name and the sheet text stay."""
    from workflow.i1io.chart import free_text_plan
    plan = free_text_plan(_spot(10.0, 65.0), "1/2  ·  My chart",
                          "Matte paper", 300)
    assert "logo" not in plan["kept"]
    assert "name" in plan["kept"] and "sheet text" in plan["kept"]
    assert plan["wordmark"] is None


def test_text_sheet_text_dropped_before_the_name():
    from workflow.i1io.chart import free_text_plan
    head = "1/2  ·  My chart"
    plan = free_text_plan(_spot(10.0, 40.0), head,
                          "A rather long note about the paper and the inks",
                          300)
    assert plan["kept"] == ("name",)
    assert plan["text"] == head


def test_text_name_kept_small():
    """Too short for the name at full size: it is printed smaller, whole,
    with the page number."""
    from workflow.i1io.chart import free_text_plan
    head = "1/2  ·  ET-8550 Hahnemuehle Photo Rag"
    full = free_text_plan(_spot(10.0, 300.0), head, "", 300)
    plan = free_text_plan(_spot(3.0, 300.0), head, "", 300)
    assert plan["text"] == head and plan["name_small"]
    assert plan["text_size_px"] < full["text_size_px"]
    # and shorter still: shortened, the page number whole
    short = free_text_plan(_spot(3.0, 30.0), head, "", 300)
    assert short["text"].startswith("1/2  ·  ") and short["text"].endswith(
        "…")


def test_text_name_impossible():
    from workflow.i1io.chart import free_text_plan
    plan = free_text_plan(_spot(1.0), "1/2  ·  My chart", "notes", 300)
    assert plan["text"] == "" and plan["wordmark"] is None
    assert plan["kept"] == ()


def test_the_line_is_centred_between_the_bottom_corner_patches(off_chart):
    """With the crosses off the group is centred between the table's
    bottom-left and bottom-right corner patches, every part's visual middle
    on one line, inside the free paper beside the last strip (a page of 13
    strips: a full A4 page leaves no free paper 10 mm in, see
    `test_without_crosses_the_line_keeps_10_mm_from_every_edge`)."""
    from workflow.i1io import chart
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", chart.CROSSES_KEY: False})
    layout = geometry.compute(geom, w, h, 13 * 24)
    plan = chart.line_plan(geom, layout, w, h, 0, name="My chart",
                           sheet_text="", dpi=300, crosses=False)
    corners = chart.corner_cells(geom, layout, w, h, 0)
    bl, br = corners["bottom-left"], corners["bottom-right"]
    mid = ((bl[4] + bl[6]) / 2 + (br[4] + br[6]) / 2) / 2
    lo, hi = plan["group"]
    assert abs((lo + hi) / 2 - mid) < 0.5
    assert plan["spot"] == "bottom edge"
    last = max(c[5] for c in chart.page_patches(geom, layout, w, h, 0))
    assert plan["line_x"] > last


# ---- every page on its own (X-Rite: each sheet is laid down by hand) -------

def test_every_page_has_its_own_aim_points_and_names(tmp_path):
    """Two full pages and a third of two strips: every page records its own
    three patches by the names printed on it, the letters running on."""
    from workflow.i1io import chart
    _build(tmp_path, 552 * 2 + 48, i1io_crosses=False)
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    pages = side["pages"]
    assert [p["aim"] for p in pages] == ["corner patches"] * 3
    assert pages[0]["aim_patches"] == ["A1", "W1", "W24"]
    assert pages[1]["aim_patches"] == ["X1", "AT1", "AT24"]
    assert pages[2]["aim_patches"] == ["AU1", "AV1", "AV24"]
    for p in pages:
        assert [a["patch"] for a in p["aim_points"]] == p["aim_patches"]
    text = (tmp_path / "c.ti2").read_text("utf-8")
    assert 'KEYWORD "CHROMIQ_I1IO_AIM_PATCHES"' in text
    assert ('CHROMIQ_I1IO_AIM_PATCHES "1: A1 W1 W24; 2: X1 AT1 AT24; '
            '3: AU1 AV1 AV24"') in text
    d = chart.aim_details(tmp_path / "c.ti2")
    assert d["aim"] == "corner patches" and d["labels"] is True
    assert [p["patches"] for p in d["pages"]] == [
        p["aim_patches"] for p in pages]


def test_a_last_page_of_one_strip_keeps_its_crosses(tmp_path):
    """Never aim at a patch that is not there: a last page of ONE strip has
    no bottom-left corner apart from its top-left one, so it keeps the three
    crosses (and they are printed there and only there)."""
    from PIL import Image
    from workflow.i1io import chart
    _build(tmp_path, 552 + 24, i1io_crosses=False)
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    assert [p["aim"] for p in side["pages"]] == ["corner patches", "crosses"]
    assert [p["digits_printed"] for p in side["pages"]] == [False, True]
    assert 'CHROMIQ_I1IO_AIM_DIGITS "yes"' in (tmp_path / "c.ti2").read_text(
        "utf-8")
    assert side["pages"][1]["aim_patches"] == []
    assert {a["target"] for a in side["pages"][1]["aim_points"]} == {"cross"}
    assert 'CHROMIQ_I1IO_AIM_PATCHES "1: A1 W1 W24; 2: crosses"' in (
        tmp_path / "c.ti2").read_text("utf-8")
    w, h = side["paper_mm"]
    s = 100 / 25.4
    for page, inked in ((1, False), (2, True)):
        img = np.asarray(Image.open(tmp_path / f"c_0{page}.tif").convert("L"))
        for m in chart.marks(w, h):
            x, y = (int(round(v * s)) for v in m.centre_mm)
            assert (img[y - 3:y + 4, x - 3:x + 4].min() < 100) == inked


def test_every_aimed_corner_patch_is_a_visible_patch_of_the_set(tmp_path):
    """On every page aimed at its corners, each of the three is one of the
    set's own patches (never the padding paper) and visible."""
    from workflow.i1io import chart
    _build(tmp_path, 552 + 48 + 7, i1io_crosses=False)
    rows = _ti2_rows(tmp_path / "c.ti2")
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    for p in side["pages"]:
        for name in p["aim_patches"]:
            lab = _lab(rows[name])
            assert lab[0] < 85.0, (p["page"], name)


def test_a_pale_set_keeps_the_crosses():
    """A set with nothing that can be aimed at keeps the crosses on every
    page rather than send the person to paper."""
    from workflow.i1io import chart
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.permutation import location_permutation

    class T:
        color_rep = "RGB"
        patches = [((99.0, 99.0, 99.0), (90.0, 95.0, 100.0))] * 552

        def media_patch(self):
            return ((100.0, 100.0, 100.0), (95.0, 100.0, 108.0))
    w, h = papers.dimensions_mm("A4")
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", chart.CROSSES_KEY: False})
    layout = geometry.compute(geom, w, h, 552)
    slots = location_permutation(552, 3, True)
    assert chart.page_crosses(T(), layout, geom, w, h, slots, False) == [True]


# ---- the texts that say what to aim at follow the record -------------------

def test_the_aim_text_follows_the_record():
    from workflow import measurement_messages as M
    crosses = M.i1io_aim_text({"aim": "crosses"})
    assert "cross 1" in crosses and "patch" in crosses
    assert "every page is aimed at on its own" in crosses
    corners = M.i1io_aim_text({"aim": "corner patches", "labels": True,
                               "pages": [{"page": 1, "aim": "corner patches",
                                          "patches": ["A1", "W1", "W24"]},
                                         {"page": 2, "aim": "crosses",
                                          "patches": []}]})
    assert "Page 1: patch A1 (top-left corner), then patch W1 (bottom-left " \
        "corner), then patch W24 (bottom-right corner)." in corners
    assert "Page 2: this page carries the three numbered crosses" in corners
    assert "cross 1 at the top left" not in corners
    bare = M.i1io_aim_text({"aim": "corner patches", "labels": False,
                            "pages": [{"page": 1, "aim": "corner patches",
                                       "patches": ["A1", "W1", "W24"]}]})
    assert "A1" not in bare and "top-left corner" in bare
    unknown = M.i1io_aim_text({"aim": "unknown"})
    assert "cross 1" in unknown and "top-left patch" in unknown
    for text in (crosses, corners, bare, unknown):
        assert "—" not in text


def test_the_crosses_help_counts_and_names_live():
    from ui.dialogs.layout_options_panel import i1io_crosses_help
    text = i1io_crosses_help({"paper": "A4", "instrument": "IO2"},
                             name="My chart", sheet_text="", pages=1,
                             paper_label="A4")
    assert "528 patches with the crosses, 552 without them" in text
    assert "gains 24 patches" in text
    assert "patch A1 (top-left corner)" in text and "W24" in text
    assert "—" not in text
    letter = i1io_crosses_help({"paper": "Letter", "instrument": "IO2"},
                               name="My chart", paper_label="Letter")
    assert "506 patches with the crosses, 528 without them" in letter
    # Letter leaves no free paper 10 mm from the edge on a full page (it
    # used to move to the top edge, 5 to 9 mm from it: item 4, 2026-11-13)
    assert "move to the top edge" not in letter
    assert "write the name and the page number on each sheet by hand" \
        in letter


def test_a_part_filled_last_page_uses_the_engines_own_fill_up(tmp_path):
    """A Manual count that leaves the last page partly filled: the engine
    lays it out as on every chart (exact capacity per page, the last strip
    padded to the strip length, IO2's `padlrow`), and the three aiming
    patches of that page are its first strip's patch 1, its last strip's
    patch 1 and its last strip's last patch: all of them printed, and all of
    them patches of the set, never the padding."""
    from workflow.i1io import chart
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", chart.CROSSES_KEY: False})
    layout = geometry.compute(geom, w, h, 552 + 30)
    assert geometry.patches_per_sheet(geom, w, h) == 552
    assert layout.pages == 2 and layout.padding == 18
    assert layout.total_patches == 552 + 48
    _build(tmp_path, 552 + 30, i1io_crosses=False)
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    assert side["generation"]["padding_patches"] == 18
    assert side["pages"][1]["aim_patches"] == ["X1", "Y1", "Y24"]
    rows = _ti2_rows(tmp_path / "c.ti2")
    for name in side["pages"][1]["aim_patches"]:
        assert rows[name] != (100.0, 100.0, 100.0), name
        assert _lab(rows[name])[0] < 85.0, name


# ---- the name line keeps 10 mm from the edge (2026-11-13, item 4) -----------

PRO300_LETTER = dict(left=6.4, right=6.3, top=3.0, bottom=5.0)


@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("n", [100, 13 * 24, 2000])
@pytest.mark.parametrize("sheet", ["", "Hahnemühle Photo Rag, 2026-11-13"])
def test_without_crosses_the_line_keeps_10_mm_from_every_edge(paper, n,
                                                               sheet):
    """Without the crosses the chart name line is printed only where it
    costs no patch AND at least `TEXT_EDGE_MM` (10 mm, the patch numbers'
    own distance) from every paper edge, whichever printer prints it; the
    top-edge band 5 to 9 mm in is gone. Where nothing that far in is free,
    the line is left off (the help asks for the name by hand)."""
    from workflow.i1io import chart, table_facts as F
    from workflow.layout_engine import geometry, instruments, papers
    assert F.TEXT_EDGE_MM.value == F.NUMBERS_EDGE_MM.value == 10.0
    w, h = papers.dimensions_mm(paper)
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": paper, chart.CROSSES_KEY: False})
    layout = geometry.compute(geom, w, h, n)
    for page in range(layout.pages):
        for spot in chart.free_spots(geom, layout, w, h, page):
            assert spot["x0"] >= 10.0 - 1e-9 and spot["x1"] <= w - 10.0 + 1e-9
            assert spot["y0"] >= 10.0 - 1e-9 and spot["y1"] <= h - 10.0 + 1e-9
            assert spot["spot"] != "top edge"     # numbers printed
        plan = chart.line_plan(geom, layout, w, h, page, name="My chart",
                               sheet_text=sheet, dpi=300, crosses=False)
        if not plan["kept"]:
            assert plan["text"] == "" and plan["wordmark"] is None
            continue
        lo, hi = plan["group"]
        assert lo >= 10.0 - 1e-6 and hi <= h - 10.0 + 1e-6
        assert plan["line_x"] >= 10.0 and plan["line_x"] <= w - 10.0


def test_a_full_a4_or_letter_page_without_crosses_leaves_the_name_off():
    """The free paper beside the last strip of a full page lies within
    10 mm of the edge on both sheets, so the line is left off there, and
    the help says so and asks for the name by hand."""
    from ui.dialogs.layout_options_panel import i1io_crosses_help
    from workflow.i1io import chart
    for paper in ("A4", "Letter"):
        fx = chart.crosses_off_effects({"paper": paper}, name="My chart")
        assert fx["name"] == "none" and fx["spot"] is None, (paper, fx)
        text = i1io_crosses_help({"paper": paper, "instrument": "IO2"},
                                 name="My chart", paper_label=paper)
        assert "write the name and the page number on each sheet by hand" \
            in text


@pytest.mark.parametrize("n", [100, 552])
def test_a_pro300_letter_edge_cuts_nothing_without_the_crosses(tmp_path, n):
    """The owner's case: a Canon PRO-300 leaves 6.4 mm (left), 6.3 mm
    (right), 3.0 mm (top) and 5.0 mm (bottom) of a Letter sheet unprinted.
    Without the crosses nothing of the chart falls into that edge: no
    patch, no label, and no part of the name line."""
    from workflow import printer_edges as PE
    _build(tmp_path, n, paper="Letter", i1io_crosses=False)
    side = json.loads((tmp_path / "c.i1io.json").read_text("utf-8"))
    tif = sorted(tmp_path.glob("c*.tif"))[0]
    edges = PE.Edges(**PRO300_LETTER, source="ppd")
    loss = PE.losses(tif, 0, edges, tuple(side["paper_mm"]))
    assert not loss.any(), loss
