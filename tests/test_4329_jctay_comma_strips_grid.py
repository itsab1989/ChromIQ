"""4.3.29: three things found in jctay's forum report of 2026-11-09
(``ChromIQ-work/2026-11-09_jctay/``), each built and pinned here.

A. **Decimal commas in a CxF.** i1Profiler writes its numbers in the
   computer's number format: on a decimal-comma locale every reflectance is
   ``0,056192``. The import refused the whole file as "not a number"; a comma
   in a CMYK (or RGB) device value stopped it with an unhandled ValueError.
   A value group (one spectrum, one patch's device channels) written wholly
   with decimal commas is now read as decimals; mixed forms and real
   non-numbers are refused as before.
B. **Numbered strips.** With the strip and patch patterns swapped, the turned
   note and order file named "Row 1: strip 1A": the strip label came from a
   leading-letters regex that ``labels.py`` forbids.
C. **Another i1Profiler grid is still refused, with a truthful reason.** His
   4 x 9 (18 pages) and 3 x 4 (52 pages) files hold the readings of his
   6-page file unchanged: he changed i1Profiler's page settings after
   measuring. The refusal used to claim the readings were taken on other
   patches.

The fixtures are synthetic (``tests.test_i1profiler_turned_grid_check._mxf``
writes the CxF the way i1Profiler does), never his files.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                        # noqa: E402
from workflow import measurement_messages as M                     # noqa: E402
from workflow.i1profiler_import import parse_pxf                   # noqa: E402
from workflow.measurement_import import (assess,                   # noqa: E402
                                         complete_from_turned_order)
from workflow.measurement_report import verify_patch_identity      # noqa: E402
from workflow.reference_convert import (                           # noqa: E402
    ReferenceConvertError, cxf_measurement_to_ti3, i1p_grid_of)
from workflow.ti3_analysis import parse_ti3                         # noqa: E402

from tests.test_i1profiler_turned_export import _chart              # noqa: E402
from tests.test_i1profiler_turned_grid_check import _import, _mxf   # noqa: E402

_NS = "http://colorexchangeformat.com/CxF3-core"
#: jctay's chart shape: 12 mm wide, 10 mm long patches, 12 to a strip.
_SHAPE = dict(patch_w_mm=12.0, patch_h_mm=10.0, max_strip_mm=121.0)


def _turned(folder: Path, name: str, n: int, **kw):
    ti2 = _chart(folder, name, n, **{**_SHAPE, **kw})
    assert not T.write_turned_export(ti2, exports_subdir(ti2.parent),
                                     name).skipped
    return ti2, T.TurnedFiles(exports_subdir(ti2.parent), name), T.plan_for(ti2)


@pytest.fixture(scope="module")
def chart_120(tmp_path_factory):
    ti2, files, plan = _turned(tmp_path_factory.mktemp("c120") / "c", "C120",
                               120)
    assert (plan.columns, plan.rows) == (12, 10)
    return ti2, files, plan


@pytest.fixture(scope="module")
def chart_624(tmp_path_factory):
    """jctay's shape: 624 patches, the order asks for 12 x 52 on one page."""
    ti2, files, plan = _turned(tmp_path_factory.mktemp("c624") / "c", "C624",
                               624)
    assert (plan.columns, plan.rows) == (12, 52)
    return ti2, files, plan


def _commas(mxf: Path, out: Path, *, spectra=True, device=False) -> Path:
    """*mxf* as i1Profiler writes it on a decimal-comma locale."""
    text = mxf.read_text(encoding="utf-8")
    if spectra:
        text = re.sub(
            r"(<cc:ReflectanceSpectrum[^>]*>)([^<]*)",
            lambda m: m.group(1) + m.group(2).replace(".", ","), text)
    if device:
        text = re.sub(r"<cc:([RGB])>(\d+)</cc:\1>",
                      lambda m: f"<cc:{m.group(1)}>{m.group(2)},0</cc:{m.group(1)}>",
                      text)
    out.write_text(text, encoding="utf-8")
    return out


# ---- A. decimal commas ----------------------------------------------------

def test_the_number_group_rule():
    from workflow.reference_convert import cxf_number_group
    assert cxf_number_group(["0,5", "0", "1,25e-3"]) == ([0.5, 0.0, 0.00125],
                                                         True)
    assert cxf_number_group(["0.5", "1"]) == ([0.5, 1.0], False)
    mixed, comma = cxf_number_group(["0,5", "0.6"])
    assert comma is False and np.isnan(mixed[0]) and mixed[1] == 0.6
    for bad in (["1,2,3"], ["1.234,5"], [",5"], ["5,"], ["abc", "0,5"]):
        vals, _c = cxf_number_group(bad)
        assert np.isnan(vals[0]), bad


def test_a_decimal_comma_mxf_converts_exactly_like_the_dot_one(chart_120,
                                                               tmp_path,
                                                               caplog):
    ti2, files, plan = chart_120
    dots = _mxf(files.txf("i1Pro 3"), tmp_path / "dots.mxf",
                columns=plan.columns)
    comma = _commas(dots, tmp_path / "comma.mxf")
    assert "0," in comma.read_text(encoding="utf-8")
    a = cxf_measurement_to_ti3(dots, tmp_path / "dots.ti3")
    with caplog.at_level("INFO", logger="workflow.reference_convert"):
        b = cxf_measurement_to_ti3(comma, tmp_path / "comma.ti3")
    da, db = parse_ti3(a), parse_ti3(b)
    assert np.abs(np.asarray(da.xyz) - np.asarray(db.xyz)).max() <= 1e-9
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    said = [r.getMessage() for r in caplog.records if "decimal commas" in
            r.getMessage()]
    assert len(said) == 1, said                       # logged once
    # and the turned import files it like the dot file
    v = assess(b, ti2)
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(b, ti2) == 120


def _spectra_edited(mxf: Path, out: Path, edit) -> Path:
    """Every spectrum of *mxf* passed through *edit* (whichever condition the
    import takes, it meets the edited values)."""
    text = re.sub(r"(<cc:ReflectanceSpectrum[^>]*>)([^<]*)",
                  lambda m: m.group(1) + " ".join(edit(m.group(2).split())),
                  mxf.read_text(encoding="utf-8"))
    out.write_text(text, encoding="utf-8")
    return out


@pytest.mark.parametrize("edit, shown", [
    # one dot among commas: the spectrum mixes the two forms
    (lambda v: [v[0].replace(",", ".")] + v[1:], None),
    # a real non-number among commas
    (lambda v: v[:3] + ["n/a"] + v[4:], "n/a"),
])
def test_mixed_or_real_non_numbers_are_still_refused(chart_120, tmp_path,
                                                     edit, shown):
    ti2, files, plan = chart_120
    dots = _mxf(files.txf("i1Pro 3"), tmp_path / "d.mxf", columns=plan.columns)
    comma = _commas(dots, tmp_path / "c.mxf")
    bad = _spectra_edited(comma, tmp_path / "bad.mxf", edit)
    with pytest.raises(ReferenceConvertError) as exc:
        cxf_measurement_to_ti3(bad, tmp_path / "bad.ti3")
    assert exc.value.message_id == M.M_CONVERT_CXF_SPECTRUM_NOT_A_NUMBER.id
    assert "is not a number" in str(exc.value)
    if shown:
        assert f"“{shown}”" in str(exc.value)


def test_decimal_comma_rgb_device_values_convert(chart_120, tmp_path):
    ti2, files, plan = chart_120
    dots = _mxf(files.txf("i1Pro 3"), tmp_path / "d.mxf", columns=plan.columns)
    both = _commas(dots, tmp_path / "both.mxf", device=True)
    text = both.read_text(encoding="utf-8")
    assert "<cc:R>" in text and ",0</cc:R>" in text
    a = cxf_measurement_to_ti3(dots, tmp_path / "d.ti3")
    b = cxf_measurement_to_ti3(both, tmp_path / "b.ti3")
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


def _cmyk_cxf(path: Path, cmyk: "list[tuple[str, str, str, str]]") -> Path:
    spectrum = " ".join("0,5" for _ in range(36))
    objs = []
    for i, (c, m, y, k) in enumerate(cmyk, 1):
        objs.append(
            f'<cc:Object ObjectType="Target" Name="Target{i}" Id="t{i}">'
            "<cc:DeviceColorValues><cc:ColorCMYK>"
            f"<cc:Cyan>{c}</cc:Cyan><cc:Magenta>{m}</cc:Magenta>"
            f"<cc:Yellow>{y}</cc:Yellow><cc:Black>{k}</cc:Black>"
            "</cc:ColorCMYK></cc:DeviceColorValues></cc:Object>")
        objs.append(
            f'<cc:Object ObjectType="M0_Measurement" Name="M0_Measurement{i}" '
            f'Id="m{i}"><cc:ColorValues><cc:ReflectanceSpectrum StartWL="380">'
            f"{spectrum}</cc:ReflectanceSpectrum></cc:ColorValues></cc:Object>")
    path.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><cc:CxF xmlns:cc="{_NS}">'
        "<cc:Resources><cc:ObjectCollection>" + "".join(objs)
        + "</cc:ObjectCollection></cc:Resources></cc:CxF>", encoding="utf-8")
    return path


def test_decimal_comma_cmyk_device_values_convert(tmp_path):
    """Until 4.3.29 this raised a bare ValueError out of the import."""
    src = _cmyk_cxf(tmp_path / "cmyk.mxf",
                    [("12,5", "0", "100", "7,25"), ("0", "50,5", "0", "0")])
    ti3 = cxf_measurement_to_ti3(src, tmp_path / "cmyk.ti3")
    rows = ti3.read_text(encoding="utf-8").split("BEGIN_DATA\n")[1].splitlines()
    assert rows[0].split()[2:6] == ["12.5000", "0.0000", "100.0000", "7.2500"]
    assert rows[1].split()[2:6] == ["0.0000", "50.5000", "0.0000", "0.0000"]


@pytest.mark.parametrize("values", [("12,5", "13.5", "0", "0"),
                                    ("12,5", "x", "0", "0")])
def test_a_cmyk_value_that_is_no_number_is_refused_with_the_catalogues_reason(
        tmp_path, values):
    src = _cmyk_cxf(tmp_path / "cmyk.mxf", [values])
    with pytest.raises(ReferenceConvertError) as exc:
        cxf_measurement_to_ti3(src, tmp_path / "cmyk.ti3")
    assert exc.value.message_id == M.M_CONVERT_CXF_NO_DEVICE_VALUES.id


def test_a_pxf_patch_set_with_decimal_commas_keeps_every_patch(tmp_path):
    """The .pxf patch-set reader skipped such a patch in silence."""
    objs = "".join(
        f'<cc:Object ObjectType="Target" Name="T{i}"><cc:DeviceColorValues>'
        f"<cc:ColorRGB><cc:R>{r}</cc:R><cc:G>{g}</cc:G><cc:B>{b}</cc:B>"
        "</cc:ColorRGB></cc:DeviceColorValues></cc:Object>"
        for i, (r, g, b) in enumerate([("255", "127,5", "0"),
                                       ("0", "0", "0"),
                                       ("255", "255", "255")]))
    pxf = tmp_path / "set.pxf"
    pxf.write_text(f'<?xml version="1.0"?><cc:CxF xmlns:cc="{_NS}">'
                   f"<cc:Resources><cc:ObjectCollection>{objs}"
                   "</cc:ObjectCollection></cc:Resources></cc:CxF>",
                   encoding="utf-8")
    patches = parse_pxf(pxf)
    assert len(patches) == 3
    assert abs(patches[0].g - 50.0) < 1e-9


def test_a_17_column_5_page_grid_with_a_short_last_column(chart_624,
                                                         tmp_path):
    """The shape i1Profiler made of the 624-patch turned chart on an A5 page
    (``i1p_out/A5_18col_5pages``, with decimal commas): 17 columns of 37 rows
    is 629 cells for 624 patches, the last column five short, its rows shared
    8 + 8 + 7 + 7 + 7 over 5 pages. Every Location is where i1Profiler's fill
    rule puts it (the real file gave misplaced 0 too), so nothing is counted
    as misplaced. Since 4.3.32 its colours decide: that file was jctay's
    measurement re-laid by i1Profiler, every reading on its own patch, so it
    is filed; the same grid with the readings taken on other patches is
    refused for its 17 columns, not for a cell."""
    ti2, files, plan = chart_624
    mxf = _commas(_mxf(files.txf("i1Pro 3"), tmp_path / "a5.mxf", columns=17,
                       pages=5), tmp_path / "a5-comma.mxf")
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.columns, g.rows, g.pages) == (17, 8, 5)
    assert 17 * -(-g.patches // g.columns) == 629
    assert (g.patches, g.located, g.misplaced) == (624, 624, 0)
    assert v.ok and v.turned_order, v.reason
    bad = _commas(_mxf(files.txf("i1Pro 3"), tmp_path / "a5b.mxf",
                       columns=17, pages=5,
                       misread=(plan.rows, plan.columns)),
                  tmp_path / "a5b-comma.mxf")
    _ti3, v = _import(bad, ti2)
    assert not v.ok and "columns: 17, pages: 5" in v.reason
    assert "Here they do not match" in v.reason


# ---- B. numbered strips ---------------------------------------------------

@pytest.fixture(scope="module")
def numbered(tmp_path_factory):
    return _turned(tmp_path_factory.mktemp("num") / "n", "Num", 120,
                   strip_pattern="0-9,@-9,@-9;1-999",
                   patch_pattern="A-Z, A-Z")


def test_numbered_strips_are_named_by_their_number(numbered, tmp_path):
    ti2, files, plan = numbered
    labels = [lab for _r, _s, lab in plan.row_strips]
    assert labels == [str(i) for i in range(1, plan.rows + 1)]
    note = files.note.read_text(encoding="utf-8")
    assert "  Row 1: strip 1\n" in note
    assert re.search(r"strip \d+[A-Z]", note) is None
    order = json.loads(files.order.read_text(encoding="utf-8"))
    assert "1A" not in json.dumps(order.get("row_strips"))
    # pairing is untouched: a turned measurement still files patch for patch
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "n.mxf", columns=plan.columns)
    ti3, v = _import(mxf, ti2)
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, ti2) == 120
    ident = verify_patch_identity(parse_ti3(ti3), ti2)
    assert ident["verdict"] == "verified"


def test_default_labels_are_unchanged(chart_120):
    ti2, files, plan = chart_120
    labels = [lab for _r, _s, lab in plan.row_strips]
    assert labels == [chr(ord("A") + i) for i in range(plan.rows)]
    assert "  Row 1: strip A\n" in files.note.read_text(encoding="utf-8")


def test_the_label_fallback_is_the_old_rule():
    class NoLabels:
        def strip_of(self, loc):
            return None
    assert T._strip_label("AB12", NoLabels()) == "AB"
    assert T._strip_label("AB12") == "AB"


# ---- C. another grid: still refused, with a truthful reason ---------------

@pytest.mark.parametrize("columns, pages, first_rows", [(4, 18, 9),
                                                        (3, 52, 4)])
def test_a_re_laid_grid_is_filed_on_its_colours(chart_624, tmp_path,
                                                columns, pages, first_rows):
    """4.3.32: his 4 x 9 (18 pages) and 3 x 4 (52 pages) files hold the
    readings of his 6-page file unchanged. Their colours agree with the
    chart, so they are filed, the filed copy says so in its header, and the
    window that says so names both grids and the score."""
    from workflow.i1profiler_turned import colour_check_fields
    ti2, files, plan = chart_624
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "g.mxf", columns=columns,
               pages=pages)
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.columns, g.rows, g.pages) == (columns, first_rows, pages)
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, ti2) == 624
    fields = colour_check_fields(ti3)
    assert fields["columns"] == str(columns) and fields["pages"] == str(pages)
    assert float(fields["score"]) >= 0.75
    title, body = M.turned_grid_colours_filed(fields)
    assert title.startswith("Filed:")
    assert (f"the file names columns: {columns}, rows on its first page: "
            f"{first_rows}, pages: {pages}") in body
    assert "columns: 12, rows: 52, pages: 1" in body
    assert "{" not in body and "—" not in body
    # filed exactly as the note's own grid would have been
    ok = _mxf(files.txf("i1Pro 3"), tmp_path / "ok.mxf", columns=12)
    ti3_ok, v_ok = _import(ok, ti2)
    assert complete_from_turned_order(ti3_ok, ti2) == 624
    assert colour_check_fields(ti3_ok) is None
    assert verify_patch_identity(parse_ti3(ti3), ti2)["verdict"] == "verified"


@pytest.mark.parametrize("columns, pages, first_rows", [(4, 18, 9),
                                                        (3, 52, 4)])
def test_a_grid_measured_wrongly_is_still_refused_with_both_causes(
        chart_624, tmp_path, columns, pages, first_rows):
    ti2, files, plan = chart_624
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "g.mxf", columns=columns,
               pages=pages, misread=(plan.rows, plan.columns))
    ti3, v = _import(mxf, ti2)
    g = i1p_grid_of(ti3)
    assert (g.columns, g.rows, g.pages) == (columns, first_rows, pages)
    assert not v.ok and not v.turned_order
    r = v.reason
    assert (f"columns: {columns}, pages: {pages}, rows on its first page: "
            f"{first_rows}") in r
    assert "Its rows therefore did not line up" not in r
    assert "This can happen in two ways" in r
    assert "the page settings in i1Profiler (Page setup on the Test Chart page" in r
    assert "So ChromIQ compared the colours" in r
    assert "Here they do not match" in r
    # a clear disagreement does not offer setting the page back: that would
    # only hide readings taken on other patches
    assert "set Page setup back to the paper size you measured with" not in r
    assert r.endswith("import that file")
    assert "—" not in r
    assert complete_from_turned_order(ti3, ti2) == 0


def test_cannot_tell_names_the_way_back_of_the_first_cause():
    """The way out without measuring again, as checked in i1Profiler 3.8.8 on
    jctay's 18-page file, is offered when the colours cannot tell."""
    from workflow.turned_colour_check import UNSURE, ColourJudgement
    r = M.turned_grid_differs_reason(
        12, 52, 4, 9, 18, colour=ColourJudgement(UNSURE, "between", 0.61, 624))
    assert "Here the colours cannot settle it" in r
    assert "agreement 0.61" in r and "at least 0.75" in r
    assert "Load under Page Data on the Measurement page" in r
    assert "set Page setup back to the paper size you measured with" in r
    assert "Save under Page Data on the Measurement page" in r
    assert "check that the one you want is selected" in r
    assert r.endswith("import that file")
    assert "{" not in r and "—" not in r


def test_the_one_page_reason_names_both_causes_too():
    r = M.turned_grid_differs_reason(12, 52, 13, 48, 1)
    assert "columns: 13, rows: 48, pages: 1." in r
    assert "This can happen in two ways" in r
    # the cell reasons are not about page settings
    for other in (M.turned_grid_cells_differ_reason(12, 52, 3, 624),
                  M.turned_grid_paged_cells_reason(12, 52, 9, 6, 3, 624),
                  M.turned_grid_paged_no_place_reason(12, 52, 9, 6)):
        assert "two ways" not in other


@pytest.mark.parametrize("pages", [1, 6])
def test_the_notes_grid_on_one_or_six_pages_is_still_filed(chart_624,
                                                           tmp_path, pages):
    ti2, files, plan = chart_624
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "ok.mxf", columns=12,
               pages=pages)
    ti3, v = _import(mxf, ti2)
    assert v.ok and v.turned_order, v.reason
    assert complete_from_turned_order(ti3, ti2) == 624


def test_the_note_says_not_to_change_the_page_settings(chart_120):
    ti2, files, plan = chart_120
    lines = files.note.read_text(encoding="utf-8").splitlines()
    i7 = next(i for i, l in enumerate(lines) if l.startswith("7. "))
    i8 = next(i for i, l in enumerate(lines) if l.startswith("8. "))
    want = "   " + T.PAGE_SETTINGS_NOTE
    assert want in lines[i7:i8]
    assert "—" not in T.PAGE_SETTINGS_NOTE


def test_a_normal_export_measured_on_18_pages_files_by_sample_id(chart_624,
                                                                 tmp_path):
    """The turned order is in the folder, but the measurement was made from
    the chart's NORMAL export (chart order) and i1Profiler cut it over 18
    pages of 4 columns: it is not a turned measurement, the grid is not
    asked about, and it pairs by SAMPLE_ID as before."""
    ti2, files, plan = chart_624
    txf = files.txf("i1Pro 3")
    text = txf.read_text(encoding="utf-8")
    objs = re.findall(r'(<cc:Object ObjectType="Target".*?</cc:Object>)',
                      text, flags=re.S)
    rank = sorted(range(len(plan.order)), key=lambda j: int(plan.order[j][0]))
    head = text[:text.index(objs[0])]
    rest = text[text.rindex(objs[-1]) + len(objs[-1]):]
    straight = tmp_path / "straight.txf"
    straight.write_text(head + "".join(objs[j] for j in rank) + rest,
                        encoding="utf-8")
    mxf = _mxf(straight, tmp_path / "straight.mxf", columns=4, pages=18)
    ti3, v = _import(mxf, ti2)
    assert i1p_grid_of(ti3).pages == 18
    assert v.ok and not v.turned_order, v.reason
    ident = verify_patch_identity(parse_ti3(ti3), ti2)
    assert ident["verdict"] == "verified"
    assert ident["paired_by"] == "SAMPLE_ID"


def test_step_8_says_the_import_asks_which_condition(chart_120):
    """Since 4.3.23 the import asks which condition of a multi-condition CxF
    to take (cxf_condition_dialog), suggesting the file's own choice, else
    M1. The note still said "ChromIQ uses M2, then M1, then M0" until
    4.3.29."""
    from workflow.reference_convert import CxfConditions
    ti2, files, plan = chart_120
    note = files.note.read_text(encoding="utf-8")
    step8 = next(l for l in note.splitlines() if l.startswith("8. "))
    assert "uses M2, then M1, then M0" not in step8
    assert "ChromIQ asks which one to import" in step8
    assert "otherwise M1 if the file holds it" in step8
    assert "If you press Cancel in that window, nothing is imported" in step8
    # and what it claims is what the import does
    c = CxfConditions(("M0", "M1", "M2"), None, None)
    assert c.needs_choice and c.preselect == "M1"
    assert CxfConditions(("M0", "M1", "M2"), "2", "M2").preselect == "M2"
    assert not CxfConditions(("M2",), None, None).needs_choice
