"""THE PRINTED SHEETS OF AN i1iO CHART IN PIECES (the new chart layout, step 7a).

A sheet image is its pieces' page images, pixel for pixel, with the cut lines
between them and every tag a page has; it is built again whenever it does not
fit the pages; and everything that asks about an image (its inks, its
instrument, its crosses, how it is shown) answers for a sheet as for its pages.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import tifffile

from core import file_manager as FM
from workflow.i1io import pieces as P
from workflow.i1io import sheets as S

A3 = "v1;sheet=297x420;piece=210x297;turn=1;at=0,0/0,210;cut_x=;cut_y=210"
INKS = {"RGB": ["RGB_R", "RGB_G", "RGB_B"], "CMY": ["CMY_C", "CMY_M", "CMY_Y"],
        "CMYK": [f"CMYK_{c}" for c in "CMYK"],
        "CMYKOG": [f"CMYKOG_{c}" for c in "CMYKOG"]}


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _ti1(path: Path, n: int, rep: str) -> Path:
    fields = INKS[rep]
    rows = [f"{i + 1} " + " ".join(
        f"{float((i * (7 + 3 * k)) % 101):.4f}" for k in range(len(fields)))
        + " 50.0 50.0 50.0" for i in range(n)]
    path.write_text(
        'CTI1\n\nDESCRIPTOR "x"\n'
        f'COLOR_REP "{"iRGB" if rep == "RGB" else rep}"\n\n'
        f"NUMBER_OF_FIELDS {len(fields) + 4}\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID " + " ".join(fields) + " XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {n}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    return path


def build(folder: Path, paper="A3", n=700, rep="RGB", dpi=72, **kw):
    """A divided chart on its own: `<folder>/c.*`, its ink list beside it as
    Create Chart writes it. Two pieces and a blank third quarter by default."""
    from workflow.layout_engine import chart
    from workflow.layout_engine.presets import default_recipe
    folder.mkdir(parents=True, exist_ok=True)
    k = default_recipe("IO2", paper).build_kwargs()
    k.update(dpi=dpi, seed=1, chart_date="x", **kw)
    r = chart.build_chart(_ti1(folder / "c.ti1", n, rep), folder / "c", **k)
    codes = {"RGB": ["r", "g", "b"]}.get(rep, [c.lower() for c in rep])
    (folder / "c.channels.json").write_text(json.dumps(
        {"ink_channels": codes,
         "layout": {"engine": "chromiq",
                    "recipe": {"instrument": "IO2", "paper": paper}}}),
        encoding="utf-8")
    return r


def _tags(path):
    with tifffile.TiffFile(str(path)) as tif:
        p = tif.pages[0]
        return {c: (p.tags[c].value if c in p.tags else None)
                for c in (258, 259, 262, 274, 277, 282, 283, 284, 296, 317, 332,
                          333, 334, 338, 339, 34675)}


# ---- the pixels --------------------------------------------------------------

@pytest.mark.parametrize("rep,bit16", [("RGB", False), ("RGB", True),
                                       ("CMY", False), ("CMYK", False),
                                       ("CMYK", True), ("CMYKOG", False)])
def test_a_sheet_is_its_pieces(tmp_path, rep, bit16):
    """Pixel for pixel, whichever inks: A3 (pieces turned), the last sheet
    with one piece missing."""
    r = build(tmp_path, n=1100, rep=rep, bit16=bit16)
    assert len(r.tiff_paths) == 3
    out = S.ensure(r.ti2_path)
    assert [p.name for p in out] == ["c-sheet_01.tif", "c-sheet_02.tif"]
    assert all(p.parent == tmp_path / "exports" for p in out)
    pages = [tifffile.imread(str(p)) for p in r.tiff_paths]
    top = np.iinfo(pages[0].dtype).max
    white = top if rep == "RGB" else 0
    h, w = pages[0].shape[:2]
    line = round(0.4 * top)
    t = max(1, round(0.25 * 72 / 25.4))
    for k, path in enumerate(out):
        sheet = tifffile.imread(str(path))
        assert sheet.dtype == pages[0].dtype
        assert sheet.shape[:2] == (round(420 / 25.4 * 72), round(297 / 25.4 * 72))
        for place in range(2):
            y0 = round(place * 210 / 25.4 * 72)
            got = sheet[y0:y0 + w, :h]
            if 2 * k + place < 3:
                want = np.rot90(pages[2 * k + place], -1).copy()
            else:
                want = np.full((w, h) + pages[0].shape[2:], white, pages[0].dtype)
            got = got[t:-t] if got.shape[0] == w else got[t:]
            want = want[t:t + got.shape[0]]
            assert np.array_equal(got, want), (k, place)
        cut = sheet[round(210 / 25.4 * 72)]
        assert (cut == cut[0]).all()          # from edge to edge, one value
        want = {"RGB": [round(0.6 * top)] * 3, "CMY": [line] * 3 + [0],
                "CMYK": [0, 0, 0, line], "CMYKOG": [0, 0, 0, line, 0, 0]}[rep]
        assert cut[0].tolist() == want
    # every tag of a page but its size and its strips
    assert _tags(out[0]) == _tags(r.tiff_paths[0])
    leftovers = {p.name for p in (tmp_path / "exports").iterdir()}
    assert leftovers == {"c-sheet_01.tif", "c-sheet_02.tif", "c-sheets.json"}


@pytest.mark.parametrize("paper", ["420x297", "A2", "Legal", "13x19"])
def test_other_divisions_and_the_resolution_unit(tmp_path, paper, monkeypatch):
    """A sheet whose pieces are not turned, one of four, one cut to one piece:
    each piece's pixels are found at its place."""
    from workflow.page_output import support as po
    monkeypatch.setattr(po, "page_output_enabled", lambda: True)
    if paper == "13x19":
        paper = "330.2x482.6"
    r = build(tmp_path, paper=paper, n=1100, tiff_res_unit="in")
    plan = S.info(r.ti2_path).plan
    out = S.ensure(r.ti2_path)
    assert len(out) == -(-len(r.tiff_paths) // plan.count)
    assert _tags(out[0])[296] == 2 and _tags(out[0])[282] == (72, 1)
    for page, path in enumerate(r.tiff_paths):
        sheet_no, place = plan.sheet_of(page)
        arr = tifffile.imread(str(path))
        sheet = tifffile.imread(str(out[sheet_no]))
        # a point well inside every patch's neighbourhood, through the plan
        for x, y in itertools.product((40.0, 105.0, 160.0), (60.0, 150.0, 240.0)):
            if x > plan.piece_mm[0] - 5 or y > plan.piece_mm[1] - 5:
                continue
            a = arr[int(y / 25.4 * 72), int(x / 25.4 * 72)]
            sx, sy = plan.to_sheet(page, x, y)
            box = sheet[int(sy / 25.4 * 72) - 1:int(sy / 25.4 * 72) + 2,
                        int(sx / 25.4 * 72) - 1:int(sx / 25.4 * 72) + 2]
            assert (box.reshape(-1, 3) == a).all(axis=1).any(), (page, x, y)


def test_the_independent_cut_check_finds_the_sheet_to_scale(tmp_path):
    from scripts import i1io_cut_check as C
    r = build(tmp_path, n=1056, dpi=200)
    out = S.ensure(r.ti2_path)
    res = C.check(out[0], tmp_path / "c.i1io.json")
    assert res["ok"], res
    assert len(res["pieces"]) == 2
    # four pieces, taken in the order they stand on the sheet
    r = build(tmp_path / "a2", paper="A2", n=2112, dpi=200)
    out = S.ensure(r.ti2_path)
    res = C.check(out[0], tmp_path / "a2" / "c.i1io.json", None, [2, 4, 1, 3])
    assert res["ok"], res
    assert len(res["pieces"]) == 4


# ---- built again when it does not fit -----------------------------------------

def _stamps(files):
    return [f.stat().st_mtime_ns for f in files]


def test_it_is_built_again_only_when_it_does_not_fit(tmp_path):
    r = build(tmp_path)
    out = S.ensure(r.ti2_path)
    first = _stamps(out)
    assert S.ensure(r.ti2_path) == out and _stamps(out) == first
    # a page drawn again
    page = tifffile.imread(str(r.tiff_paths[1]))
    tifffile.imwrite(str(r.tiff_paths[1]), 255 - page, photometric="rgb",
                     resolution=(72 / 2.54, 72 / 2.54), resolutionunit=3)
    assert not S.fits(S.info(r.ti2_path))
    S.ensure(r.ti2_path)
    assert S.fits(S.info(r.ti2_path))
    sheet = tifffile.imread(str(out[0]))
    want = np.rot90(255 - page, -1)
    y0 = round(210 / 25.4 * 72)
    assert np.array_equal(sheet[y0 + 2:y0 + 300], want[2:300])
    # the sheet itself touched, its record gone, another division recorded
    def touched():
        arr = tifffile.imread(str(out[0]))
        arr[0, 0] = 7
        tifffile.imwrite(str(out[0]), arr, photometric="rgb",
                         software=S.MARK)

    def record(**kw):
        p = tmp_path / "exports" / "c-sheets.json"
        p.write_text(json.dumps({**json.loads(p.read_text(encoding="utf-8")), **kw}), encoding="utf-8")
    for spoil in (touched,
                  lambda: (tmp_path / "exports" / "c-sheets.json").unlink(),
                  lambda: out[0].unlink(),
                  lambda: record(token=A3.replace("cut_y=210", "cut_y=211")),
                  lambda: record(pages_sha256=[]),
                  lambda: record(sheets=[]), lambda: record(schema=2)):
        spoil()
        assert not S.fits(S.info(r.ti2_path))
        S.ensure(r.ti2_path)
        assert S.fits(S.info(r.ti2_path))


def test_a_page_that_is_not_there_is_no_sheet(tmp_path):
    r = build(tmp_path)
    S.ensure(r.ti2_path)
    for p in reversed(r.tiff_paths):        # the last one, then all of them
        p.unlink()
        assert not S.fits(S.info(r.ti2_path))
        with pytest.raises(S.SheetsUnavailable):
            S.ensure(r.ti2_path)
        assert list((tmp_path / "exports").iterdir()) == []


def test_a_record_that_cannot_be_trusted_makes_no_sheet(tmp_path):
    r = build(tmp_path)
    S.ensure(r.ti2_path)
    r.ti2_path.write_text(r.ti2_path.read_text(encoding="utf-8").replace(
        "cut_y=210", "cut_y=200"), encoding="utf-8")
    with pytest.raises(S.SheetsUnavailable):
        S.ensure(r.ti2_path)
    assert list((tmp_path / "exports").iterdir()) == []     # (nor an old one)


def test_a_page_of_another_size_is_refused_and_nothing_is_left(tmp_path):
    r = build(tmp_path)
    S.ensure(r.ti2_path)
    page = tifffile.imread(str(r.tiff_paths[0]))
    tifffile.imwrite(str(r.tiff_paths[1]), page[:100], photometric="rgb",
                     resolution=(72 / 2.54, 72 / 2.54), resolutionunit=3)
    with pytest.raises(S.SheetsUnavailable):
        S.ensure(r.ti2_path)
    assert list((tmp_path / "exports").iterdir()) == []


@pytest.mark.parametrize("how", ["the first page", "the second sheet",
                                 "the record", "the disk", "killed"])
def test_a_failure_leaves_nothing_that_could_be_printed(tmp_path, monkeypatch,
                                                        how):
    """REVIEW_7A S1: whatever goes wrong, and whenever, no sheet of the old
    pages and none of the new ones is left."""
    r = build(tmp_path, n=1100)
    S.ensure(r.ti2_path)
    (tmp_path / "exports" / "c-sheets.json").unlink()       # (and no record)
    boom = OSError(28, "no space left")
    if how == "the first page":
        tifffile.imwrite(str(r.tiff_paths[0]), np.zeros((9, 9, 3), np.uint8),
                         photometric="rgb", resolution=(28, 28),
                         resolutionunit=3)
    elif how == "the second sheet":
        tifffile.imwrite(str(r.tiff_paths[2]), np.zeros((9, 9, 3), np.uint8),
                         photometric="rgb")
    elif how == "the record":
        real, n = S.write_json_atomically, []

        def fail(p, doc):
            n.append(1)
            if "sheets" in doc:
                raise boom
            real(p, doc)
        monkeypatch.setattr(S, "write_json_atomically", fail)
    elif how == "the disk":
        monkeypatch.setattr(tifffile, "imwrite",
                            lambda *a, **k: (_ for _ in ()).throw(boom))
    else:
        monkeypatch.setattr(S.os, "replace",
                            lambda *a: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(BaseException):
        S.ensure(r.ti2_path)
    monkeypatch.undo()
    assert list((tmp_path / "exports").iterdir()) == []


def test_the_working_files_of_a_killed_run_go_by_their_recorded_names(
        tmp_path):
    r = build(tmp_path)
    out = S.ensure(r.ti2_path)
    ex = tmp_path / "exports"
    rec = json.loads((ex / "c-sheets.json").read_text(encoding="utf-8"))
    mine = ["chromiq-sheet-abc.raw", "c-sheet_01.tif.part"]
    theirs = ["chromiq-sheet-other.raw", "c-sheet_07.tif.part", "notes.raw"]
    for name in mine + theirs:
        (ex / name).write_bytes(b"x")
    outside = tmp_path / "keep.raw"
    outside.write_bytes(b"x")
    (ex / "c-sheets.json").write_text(json.dumps(
        {"schema": 1, "working": mine + ["../keep.raw", "notes.raw", 5]}), encoding="utf-8")
    assert S.ensure(r.ti2_path) == out
    left = {p.name for p in ex.iterdir()}
    assert left == {"c-sheet_01.tif", "c-sheets.json", *theirs}
    assert outside.is_file()
    assert json.loads((ex / "c-sheets.json").read_text(encoding="utf-8")) == rec


@pytest.mark.parametrize("name", ["c-sheet_01.tif", "c-sheet_07.tif"])
def test_a_persons_own_file_is_never_deleted(tmp_path, name):
    """A file that only looks like a sheet stays; one that has a sheet's name
    makes the sheet take another, which everything knows as that sheet."""
    from workflow import chart_inks as I
    ex = tmp_path / "exports"
    r = build(tmp_path)
    ex.mkdir()
    (ex / name).write_bytes(b"mine")
    for _again in range(2):
        out = S.ensure(r.ti2_path)
        assert (ex / name).read_bytes() == b"mine"
        assert S.fits(S.info(r.ti2_path))
        assert out == [ex / ("c-sheet_01-1.tif" if name.endswith("01.tif")
                             else "c-sheet_01.tif")]
        assert FM.sheet_of_chart(out[0]) == (r.ti2_path, 1)
        assert I.sidecar_ink_codes(out[0]) == ["r", "g", "b"]
        page = tifffile.imread(str(r.tiff_paths[0]))
        tifffile.imwrite(str(r.tiff_paths[0]), 255 - page, photometric="rgb",
                         resolution=(72 / 2.54, 72 / 2.54), resolutionunit=3)
    S.forget_of(r.ti2_path)
    assert [p.name for p in ex.iterdir()] == [name]


def test_the_disk_is_asked_before_anything_is_written(tmp_path, monkeypatch):
    r = build(tmp_path, paper="A2", n=2112)
    S.ensure(r.ti2_path)
    si = S.info(r.ti2_path)
    h, w = tifffile.imread(str(si.sheet_files[0])).shape[:2]
    need = S._space_needed(si, h * w * 3)
    assert need >= h * w * 3 + sum(p.stat().st_size for p in r.tiff_paths)
    from types import SimpleNamespace
    S.forget_of(r.ti2_path)
    monkeypatch.setattr(S.shutil, "disk_usage",
                        lambda p: SimpleNamespace(free=need - 1))
    monkeypatch.setattr(S.tempfile, "mkstemp", lambda **k: 1 / 0)
    with pytest.raises(S.NoRoom) as e:
        S.ensure(r.ti2_path)
    assert e.value.need == need and e.value.free == need - 1
    assert list((tmp_path / "exports").iterdir()) == []


def test_every_cut_line_of_both_directions_is_there(tmp_path):
    """The vertical ones too (420 x 297, A2, 13 x 19): a line of the line's
    colour from edge to edge, at its place, and nowhere else."""
    for paper in ("420x297", "A2", "330.2x482.6"):
        r = build(tmp_path / paper, paper=paper, n=1100)
        plan = S.info(r.ti2_path).plan
        sheet = tifffile.imread(str(S.ensure(r.ti2_path)[0]))
        k = 72 / 25.4
        for cuts, axis in ((plan.cut_x, 1), (plan.cut_y, 0)):
            for v in cuts:
                cut = np.take(sheet, round(v * k), axis=axis)
                assert (cut == 153).all(), (paper, axis, v)
        lines = [(sheet == 153).all(axis=2).all(axis=a).sum() for a in (0, 1)]
        assert lines == [len(plan.cut_x), len(plan.cut_y)]
    assert plan.cut_x and plan.cut_y


def test_an_icc_profile_goes_along(tmp_path):
    from PIL import Image, ImageCms
    r = build(tmp_path)
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    for p in r.tiff_paths:
        tifffile.imwrite(str(p), tifffile.imread(str(p)), photometric="rgb",
                         resolution=(72 / 2.54, 72 / 2.54), resolutionunit=3,
                         iccprofile=icc)
    sheet = S.ensure(r.ti2_path)[0]
    with Image.open(sheet) as im:
        assert im.info["icc_profile"] == icc
    with tifffile.TiffFile(str(sheet)) as a, \
            tifffile.TiffFile(str(r.tiff_paths[0])) as b:
        assert a.pages[0].tags[34675].dtype == b.pages[0].tags[34675].dtype


def test_only_the_charts_own_pages_count(tmp_path):
    """Copies and other charts' files beside it are nobody's pages."""
    r = build(tmp_path, n=1100)
    for name in ("c.tif", "c Kopie.tif", "c_01 copy.tif", "c2.tif",
                 "c_04.tif"):
        shutil.copy(r.tiff_paths[0], tmp_path / name)
    si = S.info(r.ti2_path)
    assert list(si.pages) == list(r.tiff_paths)
    assert len(S.ensure(r.ti2_path)) == 2


def test_a_one_piece_chart_has_no_sheets(tmp_path):
    r = build(tmp_path, paper="A4", n=100)
    assert S.info(r.ti2_path) is None and S.ensure(r.ti2_path) == []
    assert not (tmp_path / "exports").exists()


def test_the_keyword_alone_is_enough(tmp_path):
    """A chart whose side file is gone is still known by its .ti2."""
    r = build(tmp_path)
    (tmp_path / "c.i1io.json").unlink()
    assert S.info(r.ti2_path).plan.token == A3


# ---- what is asked about an image ------------------------------------------------

@pytest.mark.parametrize("rep,space", [("RGB", None), ("CMY", "DeviceCMYK"),
                                       ("CMYK", None), ("CMYKOG", "DeviceN")])
def test_a_sheets_inks_are_its_charts(tmp_path, rep, space):
    """Every reader of an image's inks, on a page and on a sheet: the same
    answer (a CMYK+N sheet taken for plain CMYK would print wrong inks)."""
    from ui.tiff_preview import _find_sidecar_channels
    from workflow import chart_inks as I
    r = build(tmp_path, rep=rep)
    page, sheet = r.tiff_paths[0], S.ensure(r.ti2_path)[0]
    codes = {"RGB": ["r", "g", "b"]}.get(rep, [c.lower() for c in rep])
    assert I.sidecar_ink_codes(sheet) == I.sidecar_ink_codes(page) == codes
    assert _find_sidecar_channels(sheet) == _find_sidecar_channels(page) == codes
    a, b = I.plan_for_file(page), I.plan_for_file(sheet)
    assert a == b
    assert (a.space if a else None) == space
    if space == "DeviceN":
        assert b.codes == tuple(codes)
    assert I.is_rgb_page(page) == I.is_rgb_page(sheet) == (rep == "RGB")
    # without the channels file, from the .ti2
    (tmp_path / "c.channels.json").unlink()
    assert I.sidecar_ink_codes(sheet) == I.sidecar_ink_codes(page)
    assert I.plan_for_file(sheet) == I.plan_for_file(page)


@pytest.mark.parametrize("rep", ["RGB", "CMYK", "CMYKOG"])
def test_the_print_files_have_the_sheets_size(tmp_path, rep):
    from workflow.postscript_generator import PdfGenerator, PostScriptGenerator
    r = build(tmp_path, rep=rep)
    sheet = S.ensure(r.ti2_path)[0]
    ps = PostScriptGenerator().generate(sheet, dpi=72)
    m = re.search(r"/PageSize \[\s*([\d.]+)\s+([\d.]+)\s*\]", ps)
    assert float(m.group(1)) == pytest.approx(842, abs=1)
    assert float(m.group(2)) == pytest.approx(1191, abs=1)
    h, w = tifffile.imread(str(sheet)).shape[:2]
    assert re.search(rf"\b{w}\b.*\b{h}\b", ps, re.S)
    page_ps = PostScriptGenerator().generate(r.tiff_paths[0], dpi=72)

    def space(text):
        return re.search(r"/Device\w+ setcolorspace|\[/DeviceN.*?\]",
                         text, re.S).group(0)
    assert space(ps) == space(page_ps)
    data = PdfGenerator().generate(sheet, dpi=72)
    box = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", data)
    assert float(box.group(1)) == pytest.approx(842, abs=1)
    assert float(box.group(2)) == pytest.approx(1191, abs=1)


def test_a_verification_sheet_is_converted_like_a_page(tmp_path):
    """cctiff reads the sheet and gives it back at its own size."""
    from workflow import verification_print as V
    bin_dir = "/Applications/Argyll/bin"
    if not (Path(bin_dir) / "cctiff").exists():
        pytest.skip("no ArgyllCMS")
    src = V.source_profile_path(bin_dir)
    if not src:
        pytest.skip("no sRGB profile")
    r = build(tmp_path)
    sheet = S.ensure(r.ti2_path)[0]
    out = V.convert_pages_through_profile([sheet], Path(src), "relative",
                                          tmp_path / "cache", bin_dir=bin_dir)
    got = out[sheet]
    a, b = tifffile.imread(str(sheet)), tifffile.imread(str(got))
    assert a.shape == b.shape
    ta, tb = _tags(sheet), _tags(got)
    ra = ta[282][0] / ta[282][1] / (1 if ta[296] == 3 else 2.54)
    rb = tb[282][0] / tb[282][1] / (1 if tb[296] == 3 else 2.54)
    assert ra == pytest.approx(rb, rel=1e-4)


def test_what_the_print_notes_read(tmp_path):
    """The overhang and edge notes: the instrument and the maker from the
    chart, no helper markers, and every piece's crosses where they are."""
    from workflow import overhang as O
    from workflow import printer_edges as E
    r = build(tmp_path, n=700)
    page, sheet = r.tiff_paths[0], S.ensure(r.ti2_path)[0]
    assert O.instrument_of(page) == O.instrument_of(sheet) == "IO2"
    (tmp_path / "c.channels.json").rename(tmp_path / "x")
    ti2 = r.ti2_path.read_text(encoding="utf-8")
    r.ti2_path.write_text(re.sub(r'ORIGINATOR "[^"]*"',
                                 'ORIGINATOR "Argyll printtarg"', ti2),
                          encoding="utf-8")
    assert O.made_by_printtarg(page) is O.made_by_printtarg(sheet) is True
    r.ti2_path.write_text(ti2, encoding="utf-8")
    (tmp_path / "x").rename(tmp_path / "c.channels.json")
    assert O.made_by_printtarg(sheet) is False
    doc = json.loads((tmp_path / "c.channels.json").read_text(encoding="utf-8"))
    doc["layout"]["recipe"].update(helper_markers=True,
                                   helper_marker_edge_mm=2.0,
                                   helper_marker_len_mm=2.0)
    marked = tifffile.imread(str(sheet))
    k = 72 / 25.4
    marked[round(2 * k):round(4 * k), 60:61] = 0         # (a dash, as drawn)
    tifffile.imwrite(str(sheet), marked, photometric="rgb", software=S.MARK,
                     resolution=(72 / 2.54, 72 / 2.54), resolutionunit=3)
    (tmp_path / "c.channels.json").write_text(json.dumps(doc), encoding="utf-8")
    plain = tmp_path / "exports" / "plain.tif"
    shutil.copy(sheet, plain)
    shutil.copy(tmp_path / "c.channels.json",
                tmp_path / "exports" / "plain.channels.json")
    assert O.helper_markers(plain)["top"]         # (a page would have them)
    assert O.helper_markers(sheet) == {}
    page_boxes, boxes = E._i1io_mark_boxes(page), E._i1io_mark_boxes(sheet)
    assert len(page_boxes) == 3 and len(boxes) == 6
    plan = P.from_token(A3)
    for k, (x0, y0, x1, y1) in enumerate(page_boxes):
        for place in range(2):
            a, b = plan.to_sheet(place, x0, y0), plan.to_sheet(place, x1, y1)
            assert boxes[place * 3 + k] == pytest.approx(
                (min(a[0], b[0]), min(a[1], b[1]),
                 max(a[0], b[0]), max(a[1], b[1])))
    # the ink really is there: each box holds the cross's black
    arr = tifffile.imread(str(sheet))
    for x0, y0, x1, y1 in boxes:
        cut = arr[int(y0 * 72 / 25.4):int(y1 * 72 / 25.4) + 1,
                  int(x0 * 72 / 25.4):int(x1 * 72 / 25.4) + 1]
        assert cut.min() < 80
    # a lone piece on the last sheet: only its own three
    r3 = build(tmp_path / "x", n=1100)
    assert len(E._i1io_mark_boxes(S.ensure(r3.ti2_path)[1])) == 3
    # the edge losses' key knows the chart's files
    key = E._page_key(sheet, 0)
    side = tmp_path / "c.i1io.json"
    os.utime(side, ns=(1, 1))
    assert E._page_key(sheet, 0) != key


def test_the_edge_note_counts_the_crosses_of_every_piece(tmp_path):
    from workflow import printer_edges as E
    r = build(tmp_path, n=1056, dpi=150)
    sheet = S.ensure(r.ti2_path)[0]
    loss = E.losses(sheet, 0, E.Edges(30.0, 30.0, 30.0, 30.0), (297.0, 420.0))
    assert set(loss.i1io_marks) == {"left", "right", "top", "bottom"}
    loss = E.losses(sheet, 0, E.Edges(0.0, 0.0, 0.0, 0.0), (297.0, 420.0))
    assert not loss.i1io_marks


@pytest.mark.parametrize("paper", ["A3", "A2"])
def test_the_cut_lines_are_nobodys_text(tmp_path, paper, monkeypatch):
    """They run to the paper's edge on purpose: a printer that leaves its
    edge white takes nothing of the chart, and no note is shown; patches are
    found where they are."""
    from workflow import overhang as O
    from workflow import printer_edges as E
    from workflow.layout_engine.papers import dimensions_mm
    r = build(tmp_path, paper=paper, n=2112, dpi=100)
    sheet = S.ensure(r.ti2_path)[0]
    mm = dimensions_mm(paper)
    loss = E.losses(sheet, 0, E.Edges(3.4, 3.4, 3.0, 5.0), mm)
    assert not (loss.text or loss.i1io_text or loss.i1io_marks or loss.patches
                or loss.needed_mm)
    # …also in the copy a verification print converts
    copy = tmp_path / "cache" / sheet.name
    copy.parent.mkdir()
    shutil.copy(sheet, copy)
    loss = E.losses(copy, 0, E.Edges(3.4, 3.4, 3.0, 5.0), mm)
    assert not (loss.text or loss.i1io_text or loss.needed_mm)
    assert O.content_box(copy) == O.content_box(sheet)
    # …but what is printed 2 mm beside one is ink
    arr = tifffile.imread(str(sheet))
    k = 100 / 25.4
    plan = S.info(r.ti2_path).plan
    y = round((plan.cut_y[0] + 2.0) * k)
    arr[y - 2:y + 2, 2:30] = 0
    marked = tmp_path / "cache" / "c-sheet_01-5.tif"
    tifffile.imwrite(str(marked), arr, photometric="rgb",
                     resolution=(100 / 2.54, 100 / 2.54), resolutionunit=3)
    assert E.losses(marked, 0, E.Edges(3.4, 3.4, 3.0, 5.0), mm).i1io_text
    one = O.patch_box(r.tiff_paths[0])
    box = O.patch_box(sheet)
    plan = S.info(r.ti2_path).plan
    xs, ys = zip(*(plan.to_sheet(p, x, y) for p in range(plan.count)
                   for x, y in ((one.left, one.top), (one.right, one.bottom))))
    assert (box.left, box.top, box.right, box.bottom) == pytest.approx(
        (min(xs), min(ys), max(xs), max(ys)), abs=1.0)


def test_how_a_sheet_is_shown(tmp_path):
    from workflow.i1io import support as U
    r = build(tmp_path)
    sheets = S.ensure(r.ti2_path)
    assert U.pages_are_i1io_chart(sheets)
    assert U.aim_for_pages(sheets) == U.aim_for_pages(r.tiff_paths) == "crosses"
    assert U.display_rotation_for(r.tiff_paths) == 90
    assert U.display_rotation_for(sheets) == 0       # its pieces lie turned
    r2 = build(tmp_path / "l", paper="420x297")
    assert U.display_rotation_for(S.ensure(r2.ti2_path)) == 90


def test_only_a_sheets_name_in_exports_is_a_sheet(tmp_path):
    d = tmp_path / "exports"
    d.mkdir()
    (tmp_path / "a.b-w10.0mm.ti2").write_text("x", encoding="utf-8")
    assert FM.sheet_of_chart(d / "a.b-w10.0mm-sheet_02.tif") == (
        tmp_path / "a.b-w10.0mm.ti2", 2)
    assert FM.beside_the_chart(d / "a.b-w10.0mm-sheet_02.tif") == \
        tmp_path / "a.b-w10.0mm.tif"
    assert FM.sheet_of_chart(d / "a.b-w10.0mm-sheet_02-3.tif")[1] == 2
    c = tmp_path / "cache"
    assert FM.sheet_of_chart(c / "a.b-w10.0mm-sheet_01.tif") == (
        tmp_path / "a.b-w10.0mm.ti2", 1)
    for p in (tmp_path / "a.b-w10.0mm-sheet_02.tif", d / "z-sheet_01.tif",
              tmp_path / "old" / "a.b-w10.0mm-sheet_01.tif",
              d / "a.b-w10.0mm_01.tif"):
        assert FM.sheet_of_chart(p) is None
        assert FM.beside_the_chart(p) == p


# ---- Generate ----------------------------------------------------------------------

def _generated(tmp_path, paper="A3", **params):
    """Generate through `ChartCreator`, as a loaded patch set is."""
    from tests.test_chart_creator_engine import (ChartParams, _EngineRunner,
                                                 _EngineSettings,
                                                 _MockFileManager)
    from workflow.chart_creator import ChartCreator
    from workflow.layout_engine import presets
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    done: list = []
    from dataclasses import replace
    creator.load_ti1_and_generate_preview(
        _ti1(tmp_path / "in.ti1", 700, "RGB"),
        ChartParams(instrument="IO2", paper=paper, is_manual=True, tiff_dpi=72,
                    layout_recipe=replace(presets.default_recipe("IO2", paper),
                                          dpi=72), **params),
        on_line=lambda _l: None, on_finish=done.append)
    assert done and done[0]
    return next((tmp_path / "p" / "runs" / "run1").glob("*.ti2"))


def test_generate_builds_them_and_a_live_preview_does_not(tmp_path):
    ti2 = _generated(tmp_path)
    si = S.info(ti2)
    assert si is not None and len(si.sheet_files) == 1 and S.fits(si)
    # the pages drawn again by a live preview: no sheet of the old pages stays
    _generated(tmp_path, compose_sheets=False)
    assert not list(si.files.folder.glob("*-sheet*"))
    assert S.ensure(ti2) == si.sheet_files
    # another paper in the same run: nothing of the divided chart stays
    _generated(tmp_path, "A4")
    assert not list(si.files.folder.glob("*-sheet*"))


def test_a_preview_drawn_over_a_chart_takes_its_sheets_away(tmp_path):
    from types import SimpleNamespace
    import _i1io_baseline as base
    from workflow.chart_creator import ChartParams
    r = build(tmp_path)
    for token in (A3, ""):
        S.ensure(r.ti2_path)
        if not token:                           # (also without their record)
            (tmp_path / "exports" / "c-sheets.json").unlink()
        base._creator()._compose_i1io_sheets(
            SimpleNamespace(ti2_path=r.ti2_path, i1io_pieces=token),
            ChartParams(compose_sheets=token == ""))
        assert list((tmp_path / "exports").iterdir()) == []


def test_a_failed_sheet_is_no_failed_chart(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "compose", lambda si: 1 / 0)
    assert _generated(tmp_path).is_file()


def test_the_live_preview_asks_for_no_sheets():
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._generate_from_ti1)
    assert "params.compose_sheets = not preview" in src


# ---- the project's files ------------------------------------------------------------

def _project(tmp_path):
    proj = FM.Project.create_or_load(tmp_path / "Dotted-w10.0mm",
                                     "Dotted-w10.0mm")
    run = proj.current_run()
    r = build(tmp_path / "src")
    for f in sorted((tmp_path / "src").iterdir()):
        shutil.copy(f, run.dir / (run.stem + f.name[1:]))
    assert len(S.ensure(run.chart_ti2)) == 1
    return proj, run


def test_renaming_the_project_takes_the_sheets_along(tmp_path):
    proj, run = _project(tmp_path)
    proj.rename("New-Name")
    shutil.move(str(tmp_path / "Dotted-w10.0mm"), str(tmp_path / "New-Name"))
    run = FM.Project.load(tmp_path / "New-Name").current_run()
    files = FM.I1ioSheetFiles.for_chart(run.chart_ti2)
    assert files.record.is_file() and files.sheet(1).is_file()
    assert S.fits(S.info(run.chart_ti2))
    assert not list(run.exports_dir.glob("Dotted*"))


def test_duplicating_the_run_takes_the_sheets_along(tmp_path):
    proj, run = _project(tmp_path)
    copy = proj.duplicate_run(run)
    assert copy.dir != run.dir and S.fits(S.info(copy.chart_ti2))
    assert S.fits(S.info(run.chart_ti2))


def test_adopting_the_chart_for_verification_takes_them_along(tmp_path):
    proj, run = _project(tmp_path)
    ti2 = run.adopt_run_chart_as_verify()
    assert S.fits(S.info(ti2))
    assert not run.exports_dir.exists() or not list(run.exports_dir.iterdir())


def test_another_chart_in_their_place_never_prints_the_old_sheet(tmp_path):
    """Whatever put another chart's pages under the same name (an import, a
    restore, an archive brought back): the sheets are rebuilt from those."""
    proj, run = _project(tmp_path)
    old = S.info(run.chart_ti2).sheet_files[0].read_bytes()
    r = build(tmp_path / "other", n=900, rep="RGB")
    for f in sorted((tmp_path / "other").iterdir()):
        if f.is_file():
            shutil.copy(f, run.dir / (run.stem + f.name[1:]))
    out = S.ensure(run.chart_ti2)
    assert out[0].read_bytes() != old and S.fits(S.info(run.chart_ti2))


# ---- memory --------------------------------------------------------------------------

def test_one_piece_at_a_time_in_memory(tmp_path):
    """A2 in four pieces: what is taken stays under one and a half pieces and
    64 MB (the sheet itself is on disk)."""
    r = build(tmp_path, paper="A2", n=2100, dpi=300)
    piece = tifffile.imread(str(r.tiff_paths[0])).nbytes
    tracemalloc.start()
    S.compose(S.info(r.ti2_path))
    _now, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 1.5 * piece + 64e6, (peak, piece)


@pytest.mark.parametrize("paper,dpi,bit16,inks,drawn,printed", [
    ("A3", 600, False, 3, 686e6, 645e6), ("A3", 600, True, 3, 998e6, 1495e6),
    ("A3", 600, False, 4, 4011e6, 805e6), ("A2", 600, False, 3, 965e6, 1202e6),
    ("A2", 600, True, 3, 1278e6, 2949e6), ("A2", 600, False, 4, 4687e6, 1541e6),
    ("A2", 600, True, 4, 5247e6, 3907e6), ("A2", 1200, False, 3, 4078e6, 6021e6)])
def test_the_budget_is_never_under_what_was_measured(
        paper, dpi, bit16, inks, drawn, printed, monkeypatch):
    """The peaks of whole processes (Generate; PostScript, PDF and preview of
    a sheet), as measured: with a budget of just under the larger one the
    chart is refused, whichever of the two it is."""
    from workflow.layout_engine.papers import dimensions_mm
    from workflow.page_output import support as po
    plan = P.plan_for(dimensions_mm(paper))
    w, h = (po.pixels_of(v, dpi) for v in plan.piece_mm)
    kind = dict(inks=inks, device=inks >= 4, bit16=bit16)
    base = 47e6                                     # an empty process
    assert S.DRAW_MARGIN * po.estimated_bytes(w, h, plan.count, **kind) \
        >= drawn - base
    assert S.drawing_problem(w, h, plan.count, **kind) is None
    with monkeypatch.context() as m:
        m.setattr(po, "MEMORY_BUDGET_BYTES", drawn - base - 1)
        assert "per piece" in S.drawing_problem(w, h, plan.count, **kind)
    monkeypatch.setattr(po, "MEMORY_BUDGET_BYTES", printed - base - 1)
    assert S.budget_problem(plan, dpi, **kind)


def test_a_sheet_too_large_to_print_is_refused_before_a_page_is_drawn(
        tmp_path, monkeypatch):
    from workflow.page_output import support as po
    with pytest.raises(po.PageBudgetError) as e:
        build(tmp_path, paper="A2", dpi=1200, bit16=True)
    assert "printed sheet" in str(e.value) and "No page" in str(e.value)
    assert not list(tmp_path.glob("*.tif"))
    plan = P.plan_for((420.0, 594.0))
    assert S.budget_problem(plan, 1200) is None
    assert S.budget_problem(plan, 600, inks=6, bit16=True) is None
    assert "Nothing was written" in S.budget_problem(plan, 1200, bit16=True,
                                                     early=True)
    # the pieces of very many sheets are drawn pages too
    monkeypatch.setattr(po, "MEMORY_BUDGET_BYTES", 10_000_000)
    with pytest.raises(po.PageBudgetError):
        build(tmp_path / "b", paper="A3", n=700)
    build(tmp_path / "a4", paper="A4", n=100)      # a one-page chart is not asked


def test_the_tab_refuses_it_before_anything_ran(qtbot, tmp_path):
    """Generate's own early check, with all the pieces it would draw."""
    from types import SimpleNamespace
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from dataclasses import replace
    from ui.tabs import tab_chart
    from workflow.layout_engine.presets import default_recipe
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "p"))
    s.set("use_chromiq_layout_engine", True)
    tab = tab_chart.TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(tab)
    tab._switch_mode("manual")
    for paper, pieces, refused in (("A2", 4, False), ("A2", 40, True),
                                   ("A4", 40, False)):
        tab._manual_layout_panel.set_recipe(
            replace(default_recipe("IO2", paper), dpi=600))
        tab._log.clear()
        tab._estimated_layout = SimpleNamespace(pages=pieces)
        assert tab._refuse_page_over_budget() is refused, (paper, pieces)
        text = tab._log.toPlainText()
        assert ("40 pieces" in text and text.endswith(
            "Nothing was written.")) is refused


def test_generate_says_what_takes_the_time(tmp_path):
    from types import SimpleNamespace
    import _i1io_baseline as base
    from workflow.chart_creator import ChartParams
    r = build(tmp_path)
    said = []
    for token, n in ((A3, 1), ("", 1)):
        base._creator()._compose_i1io_sheets(
            SimpleNamespace(ti2_path=r.ti2_path, i1io_pieces=token),
            ChartParams(), said.append)
        assert len(said) == n and said[0].startswith("Putting the sheets")


def test_generate_refuses_it_before_anything_ran(qtbot):
    from ui.dialogs import page_output_panel as pop
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    panel = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(panel)
    panel.instr.setCurrentIndex(panel.instr.findData("IO2"))
    panel.paper.setCurrentIndex(panel.paper.findData("A2"))
    assert pop.divided_problem(panel) is None
    panel.dpi.setMaximum(2400)
    panel.dpi.setValue(2400)
    why = pop.divided_problem(panel)
    assert why and why.endswith("Nothing was written.")
    assert not pop.divided_problem(panel, words_only=True).endswith("written.")


def test_a_project_rename_takes_the_sheets_and_no_file_of_a_person(tmp_path):
    """(the final review, S4 and C2): every name a printed sheet may have is carried along; a
    person's own ``Name_01-2.tif`` is nobody's and stays, as in 4.3.65."""
    from core.file_manager import Project
    proj = Project.create(tmp_path / "Old", "Old")
    run = proj.current_run()
    run.ensure_dir()
    ours = ["Old-sheet_01.tif", "Old-sheet_02-1.tif", "Old-sheets.json", "Old-verify-sheet_01.tif",
            "Old-verify-sheet_01-3.tif", "Old-cal-sheet_01.tif", "Old_01.tif", "Old-cal_02.tif",
            "Old-verify.control-strip.json", "Old-i1profiler.pxf", "Old-colours.txt", "Old.ti2"]
    theirs = ["Old_01-2.tif", "Old-cal_01-2.tif", "Old-i1profiler_01-2.txt", "Old-colours_1-2.txt",
              "Old-sheet.tif", "Old-sheet_01-.tif", "Old-sheet_01-1-2.tif", "Old_01-2.tiff",
              "Old-sheet_a.tif"]
    ex = run.dir / "exports"
    ex.mkdir()
    for n in ours + theirs:
        (ex / n).write_text(n, encoding="utf-8")
    moved = tmp_path / "New"
    proj.root.rename(moved)
    proj = Project.load(moved)
    proj.rename("New")
    left = {p.name for p in (moved / ex.relative_to(tmp_path / "Old")).iterdir()}
    assert left == {n.replace("Old", "New", 1) for n in ours} | set(theirs)
