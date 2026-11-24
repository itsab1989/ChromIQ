"""The Barbieri Beta, step 2: IMPORT of a Spectro32 measurement into a run.

An owner's real run (issue 215) read a 32 x 28 chart of 6.5 mm patches in one
go: 896 lines, one per reading, in the order the table read them (A1, B1, ...
AF1, then A2 ...), 41 spectral values from 380 to 780 nm as fractions, X Y Z
on the 0 to 100 scale, no patch names. These tests reproduce that GEOMETRY
with SYNTHETIC values (`tests._barbieri_fixture`): no tester data is in the
repository.

What they pin:

* a reading finds its patch by its position in the file through the chart's
  side file, and the filed copy holds the chart's own SAMPLE_ID, SAMPLE_LOC and
  device values, the spectra in percent and the XYZ computed from them as
  ArgyllCMS computes it;
* a sheet laid mirrored, upside down or turned, or aimed one patch off, is
  refused and named; nothing is ever moved to make it fit;
* every malformed file is refused with its own reason: a count that is not the
  page's, missing bands, a failed reading (Gateway writes ``1.#QO``), a gap in
  the reading numbers, another scale, a file of colours only, a side file that
  belongs to another chart, several files for one page;
* Spectro32's own colours are compared with the spectra; another Spectro32
  setting is only said, a disagreement nothing explains is asked about;
* where the colours cannot tell (a sorted chart), the check patches decide,
  and without them the person is asked;
* transmission is filed as ArgyllCMS files it and recorded as such;
* the Measure tab's door files it through the ordinary ending, and with the
  Beta off nothing of this is reached.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests._barbieri_fixture import (barbieri_on, readings_for,  # noqa: E402
                                     write_spectro32, write_ti1)


@pytest.fixture(autouse=True)
def _on():
    with barbieri_on():
        yield


def _owner_margins():
    """32 x 28 patches of 6.5 mm on A4 landscape (the owner's chart)."""
    return (10.0, 297.0 - 15.0 - 208.0 - 0.1, 210.0 - 10.0 - 182.0 - 0.1,
            15.0)


def _chart(tmp_path, n=896, name="c", **over):
    from workflow.layout_engine import presets
    from workflow.layout_engine.chart import build_chart
    tmp_path.mkdir(parents=True, exist_ok=True)
    ti1 = write_ti1(tmp_path / f"{name}.ti1", n, seed=over.pop("seed", 7))
    paper = over.pop("paper", "A4R")
    kw = presets.default_recipe("B100XY", paper).build_kwargs()
    if n == 896 and "margins" not in over:
        over.update(margins=_owner_margins(), patch_w=6.5, patch_h=6.5)
    kw.update(over)
    build_chart(ti1, tmp_path / name, **kw)
    ti2 = tmp_path / f"{name}.ti2"
    side = json.loads((tmp_path / f"{name}.barbieri.json").read_text(
        encoding="utf-8"))
    return ti2, side


@pytest.fixture(scope="module")
def owner(tmp_path_factory):
    """The owner's geometry: one page of 32 x 28, 896 patches."""
    from workflow.barbieri import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        ti2, side = _chart(tmp_path_factory.mktemp("owner"))
    finally:
        support._latched = before
    return ti2, side


def _file(tmp_path, ti2, side, name="run_measurements.txt", *,
          arrangement="straight", **kw):
    sp = readings_for(ti2, side, arrangement=arrangement)
    return write_spectro32(tmp_path / name, sp, **kw), sp


def _assess(paths, ti2):
    from workflow.barbieri.spectro32_import import assess_files
    return assess_files([paths] if isinstance(paths, Path) else paths, ti2)


# ---- the owner's geometry, filed -------------------------------------------

def test_the_owners_geometry_is_paired_by_reading_order(tmp_path, owner):
    from workflow.barbieri.spectro32_import import (spectra_xyz,
                                                    write_ti3)
    from workflow.ti3_analysis import parse_ti3
    ti2, side = owner
    pg = side["pages_detail"][0]
    assert (pg["columns"], pg["rows"]) == (32, 28)
    assert pg["spectro32"] == "R0,0,2015,1755,32,28"
    f, sp = _file(tmp_path, ti2, side)
    v = _assess(f, ti2)
    assert v.ok, v.reason
    assert not v.ask_why and v.xyz_ask is None
    assert v.pages[0].judgement.decided_by == "fit"
    out = write_ti3(v, ti2, tmp_path / "out")
    data = parse_ti3(out)
    assert data.n_patches == 896
    text = out.read_text(encoding="utf-8")
    rows = {ln.split()[1].strip('"'): ln.split()
            for ln in text.split("BEGIN_DATA\n", 1)[1].split(
                "END_DATA", 1)[0].strip().splitlines()}
    # reading 1 is A1, reading 32 is AF1, reading 33 is A2, the last AF28
    for k, name in ((0, "A1"), (31, "AF1"), (32, "A2"), (895, "AF28")):
        assert pg["reading_order"][k] == name
        got = np.array([float(x) for x in rows[name][-41:]])
        assert np.allclose(got, sp[k] * 100.0, atol=1e-4), name
        xyz = np.array([float(x) for x in rows[name][5:8]])
        assert np.allclose(xyz, spectra_xyz(sp[k:k + 1])[0], atol=1e-4)
    # the chart's own ids, locations and device values, in the chart's order
    t2 = ti2.read_text(encoding="utf-8").split("BEGIN_DATA\n", 1)[1]
    chart_rows = [ln.split() for ln in t2.split("END_DATA")[0].strip()
                  .splitlines()]
    filed = [ln.split() for ln in text.split("BEGIN_DATA\n", 1)[1].split(
        "END_DATA", 1)[0].strip().splitlines()]
    assert [r[:5] for r in filed] == [r[:5] for r in chart_rows]
    assert 'CHROMIQ_BARBIERI_MODE "reflection"' in text
    assert "CHROMIQ_PAIRED_BY_BARBIERI_ORDER" in text
    assert 'TARGET_INSTRUMENT "Barbieri Spectro 100xy"' in text


@pytest.mark.parametrize("kind", ["val", "spectrum"])
def test_the_val_and_spectrum_files_read_the_same(tmp_path, owner, kind):
    ti2, side = owner
    a, _sp = _file(tmp_path, ti2, side)
    b, _sp = _file(tmp_path, ti2, side, name=f"other_{kind}.txt", kind=kind)
    va, vb = _assess(a, ti2), _assess(b, ti2)
    assert va.ok and vb.ok, vb.reason
    assert np.allclose(va.pages[0].xyz, vb.pages[0].xyz, atol=1e-4)
    if kind == "val":
        assert vb.pages[0].file.setting == ("D50", "2")
        assert vb.pages[0].file.template == "chart-reflection.TXT"


def test_a_spectrum_file_is_checked_against_its_xyz_companion(tmp_path,
                                                              owner):
    from workflow.barbieri.spectro32_import import spectra_xyz
    ti2, side = owner
    f, sp = _file(tmp_path, ti2, side, name="r_spectrum.txt", kind="spectrum")
    xyz = spectra_xyz(sp)
    (tmp_path / "r_XYZ.txt").write_bytes(
        ("XYZ100\r\nchart-reflection.TXT\r\n\r\nD50  2\r\n" + "".join(
            f"{x:.3f}\t{y:.3f}\t{z:.3f}\r\n" for x, y, z in xyz)
         ).encode("cp1252"))
    v = _assess(f, ti2)
    assert v.ok
    xc = v.pages[0].xyz_check
    assert xc.available and xc.agree and xc.source == "XYZ"
    assert v.pages[0].file.setting == ("D50", "2")


def test_a_decimal_comma_file_is_read(tmp_path, owner):
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side, decimal_comma=True)
    v = _assess(f, ti2)
    assert v.ok, v.reason
    assert v.pages[0].file.decimal_comma


# ---- the sheet as it lay ----------------------------------------------------

@pytest.mark.parametrize("arrangement,code", [
    ("mirrored", "arranged-mirrored"),
    ("upside-down", "arranged-upside-down"),
    ("turned", "arranged-turned"),
    ("right", "aimed-right"), ("left", "aimed-left"),
    ("up", "aimed-up"), ("down", "aimed-down")])
def test_a_sheet_laid_or_aimed_wrong_is_refused_and_named(
        tmp_path, owner, arrangement, code):
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side, arrangement=arrangement)
    v = _assess(f, ti2)
    assert not v.ok and v.code == code
    assert "AF1" in v.reason and "{" not in v.reason
    if arrangement == "mirrored":
        assert "mirrored" in v.reason and "wrong side up" in v.reason


def test_another_chart_of_the_same_size_is_refused(tmp_path, owner):
    ti2, side = owner
    other_ti2, other_side = _chart(tmp_path / "other", seed=99)
    f, _sp = _file(tmp_path, other_ti2, other_side)
    v = _assess(f, ti2)
    assert not v.ok and v.code == "other-chart"


# ---- malformed files ---------------------------------------------------------

@pytest.mark.parametrize("cut", [1, -1])
def test_a_count_that_is_not_the_pages_is_refused(tmp_path, owner, cut):
    ti2, side = owner
    sp = readings_for(ti2, side)
    sp = sp[:-1] if cut == 1 else np.vstack([sp, sp[:1]])
    f = write_spectro32(tmp_path / "x_measurements.txt", sp)
    v = _assess(f, ti2)
    assert not v.ok and v.code == "count"
    assert "896" in v.reason and str(len(sp)) in v.reason


@pytest.mark.parametrize("text", ["1.#QO", "-1.#IND", "nan", "inf", ""])
def test_a_failed_reading_is_refused_never_filled_in(tmp_path, owner, text):
    ti2, side = owner
    sp = readings_for(ti2, side)
    f = write_spectro32(tmp_path / "x_measurements.txt", sp,
                        replace={(17, 5): text or "-"})
    v = _assess(f, ti2)
    assert not v.ok and v.code == "failed-value", v.code
    assert "17" in v.reason


def test_a_gap_in_the_reading_numbers_is_refused(tmp_path, owner):
    ti2, side = owner
    sp = readings_for(ti2, side)
    f = write_spectro32(tmp_path / "x_measurements.txt", sp,
                        replace={(40, 0): "41"})
    v = _assess(f, ti2)
    assert not v.ok and v.code == "numbering"
    assert "39" in v.reason and "41" in v.reason


def test_missing_bands_are_refused(tmp_path, owner):
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side)
    lines = f.read_bytes().decode("cp1252").split("\r\n")
    lines = ["\t".join(ln.split("\t")[:1] + ln.split("\t")[2:])
             for ln in lines]                       # drops 380 nm
    f.write_bytes("\r\n".join(lines).encode("cp1252"))
    v = _assess(f, ti2)
    assert not v.ok and v.code == "bands" and "40" in v.reason


def test_a_line_cut_short_is_refused(tmp_path, owner):
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side)
    lines = f.read_bytes().decode("cp1252").split("\r\n")
    lines[10] = "\t".join(lines[10].split("\t")[:20])
    f.write_bytes("\r\n".join(lines).encode("cp1252"))
    v = _assess(f, ti2)
    assert not v.ok and v.code == "row-shape" and "11" in v.reason


def test_spectra_on_another_scale_are_refused(tmp_path, owner):
    ti2, side = owner
    sp = readings_for(ti2, side) * 100.0
    f = write_spectro32(tmp_path / "x_measurements.txt", sp)
    v = _assess(f, ti2)
    assert not v.ok and v.code == "scale"


def test_a_value_far_below_zero_is_refused(tmp_path, owner):
    ti2, side = owner
    sp = readings_for(ti2, side)
    sp[9, 3] = -0.4
    f = write_spectro32(tmp_path / "x_measurements.txt", sp)
    v = _assess(f, ti2)
    assert not v.ok and v.code == "negative" and "10" in v.reason


def test_a_file_of_colours_only_sends_to_the_measurements_file(tmp_path,
                                                                owner):
    ti2, _side = owner
    p = tmp_path / "r_LAB.txt"
    p.write_bytes(b"Lab\r\nchart.TXT\r\n\r\nD50  2\r\n50.0\t1.0\t2.0\r\n")
    v = _assess(p, ti2)
    assert not v.ok and v.code == "colours-only"
    assert "_measurements.txt" in v.reason


def test_a_file_that_is_not_spectro32s_is_refused(tmp_path, owner):
    ti2, _side = owner
    p = tmp_path / "notes.txt"
    p.write_text("hello\nworld\n", encoding="utf-8")
    v = _assess(p, ti2)
    assert not v.ok and v.code == "not-spectro32"
    from workflow.barbieri.spectro32_import import looks_like_spectro32
    assert not looks_like_spectro32(p)


def test_a_side_file_of_another_version_of_the_chart_is_refused(tmp_path,
                                                                owner):
    ti2, side = owner
    d = tmp_path / "copy"
    d.mkdir()
    t = d / "c.ti2"
    shutil.copy2(ti2, t)
    shutil.copy2(Path(str(ti2)[:-4] + ".barbieri.json"),
                 d / "c.barbieri.json")
    t.write_text(t.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    f, _sp = _file(tmp_path, ti2, side)
    v = _assess(f, t)
    assert not v.ok and v.code == "side" and "c.barbieri.json" in v.reason


def test_two_files_for_a_chart_of_one_page_are_refused(tmp_path, owner):
    ti2, side = owner
    a, _ = _file(tmp_path, ti2, side, name="a_measurements.txt")
    b, _ = _file(tmp_path, ti2, side, name="b_measurements.txt")
    v = _assess([a, b], ti2)
    assert not v.ok and v.code == "one-page"


def test_every_reason_reads_complete_without_an_em_dash():
    from workflow import measurement_messages as M
    kw = dict(name="r_measurements.txt", other="s_measurements.txt",
              reading=3, previous=2, column="400 nm", text="1.#QO", count=40,
              line=7, top="88", value="-0.4", page=1, cells=896, cols=32,
              rows=28, got=895, pages=2, files=3, side="c.barbieri.json",
              first="A1", aim="AF1")
    codes = list(M._BARB_REASON_TEXT) + [
        "arranged-" + k for k in M._BARB_HOW_TEXT] + [
        "aimed-" + k for k in M._BARB_WHERE_TEXT]
    for code in codes:
        text = M.barbieri_import_reason(code, **kw)
        assert "{" not in text and "—" not in text, code
        assert text.endswith("."), code


# ---- Spectro32's own colours -------------------------------------------------

def test_another_spectro32_setting_is_recognised_and_only_said(tmp_path,
                                                               owner):
    from workflow import measurement_messages as M
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side, kind="val", setting=("D65", "10"),
                   xyz_setting=("D65", "1964_10"))
    v = _assess(f, ti2)
    assert v.ok and v.xyz_ask is None
    assert v.pages[0].xyz_check.other_setting == ("D65", "10")
    notes = M.barbieri_notes(v)
    assert any("D65 with the 10 degree observer" in n for n in notes)


def test_colours_that_nothing_explains_are_asked_about(tmp_path, owner):
    from workflow.barbieri.spectro32_import import spectra_xyz
    ti2, side = owner
    sp = readings_for(ti2, side)
    # the spectra one band out of place, the colours of the true spectra
    shifted = np.hstack([sp[:, 1:], sp[:, -1:]])
    f = write_spectro32(tmp_path / "x_measurements.txt", shifted,
                        xyz_override=spectra_xyz(sp))
    v = _assess(f, ti2)
    assert v.ok
    assert v.xyz_ask is not None and v.xyz_ask.median > 1.0


def test_the_owners_agreement_is_inside_the_tolerance():
    """The tolerance's reason, as numbers: his 896 readings agreed to 0.014
    dE76 at most; the nearest wrong setting measured was 4.6 (median)."""
    from workflow.barbieri import spectro32_import as S
    assert 0.014 * 3 < S.XYZ_AGREE_DE < 4.6 / 3


# ---- where the colours cannot tell ------------------------------------------

def _sorted_field(cols=12, rows=10):
    """A chart sorted across the sheet (the fit cannot tell a mirrored or
    flipped sheet from the right one) with the five check patches in their
    corners, as `chart.check_order` puts them."""
    E = np.zeros((rows * cols, 3))
    for k in range(rows * cols):
        c, r = k % cols, k // cols
        E[k] = (30.0 + 40.0 * r / (rows - 1), -30.0 + 60.0 * c / (cols - 1),
                -20.0 + 30.0 * (c + r) / (cols + rows - 2))
    checks = {0: (4.0, 0.0, 0.0),                       # A1 darkest
              cols - 1: (55.0, 75.0, 70.0),             # aim, colourful
              (rows - 1) * cols: (97.0, 0.0, -2.0),     # lower left, lightest
              1: (50.0, -60.0, 60.0),                   # right of A1
              cols: (40.0, 50.0, -60.0)}                # below A1
    for k, lab in checks.items():
        E[k] = lab
    return E, sorted(checks)


def _measured(E, arrangement, cols, rows):
    from workflow.barbieri.spectro32_import import arrangement_cells
    cells = arrangement_cells(arrangement, cols, rows)
    rng = np.random.default_rng(1)
    M = np.array([E[c] if c is not None else (95.0, 0.0, 0.0)
                  for c in cells], dtype=float)
    # a printer that is not the expected one: a smooth change plus noise
    M = M * np.array([0.92, 1.1, 0.9]) + np.array([3.0, -2.0, 4.0])
    return M + rng.normal(0, 0.4, M.shape)


@pytest.mark.parametrize("arrangement", ["mirrored", "upside-down",
                                         "turned"])
def test_the_check_patches_decide_what_the_fit_cannot(arrangement):
    from workflow.barbieri.spectro32_import import judge_page
    E, checks = _sorted_field(36, 28)
    j = judge_page(E, _measured(E, "straight", 36, 28), 36, 28, checks)
    assert j.status == "ok" and j.decided_by == "check patches"
    j = judge_page(E, _measured(E, arrangement, 36, 28), 36, 28, checks)
    assert j.status == "refuse" and j.how == arrangement


def test_without_check_patches_the_person_is_asked():
    from workflow.barbieri.spectro32_import import judge_page
    E, _checks = _sorted_field(36, 28)
    j = judge_page(E, _measured(E, "straight", 36, 28), 36, 28, [])
    assert j.status == "ask" and j.why == "no-checks"
    j = judge_page(None, _measured(E, "straight", 36, 28), 36, 28, [])
    assert j.status == "ask" and j.why == "no-colours"


# ---- transmission -----------------------------------------------------------

def test_transmission_is_filed_as_argyll_files_it(tmp_path):
    from workflow import measurement_messages as M
    from workflow.barbieri.spectro32_import import write_ti3
    ti2, side = _chart(tmp_path / "t", 300, barbieri_head="transmission-3")
    assert side["mode"] == "transmission"
    f, sp = _file(tmp_path, ti2, side)
    v = _assess(f, ti2)
    assert v.ok and v.mode == "transmission"
    text = write_ti3(v, ti2, tmp_path / "out").read_text(encoding="utf-8")
    assert 'CHROMIQ_BARBIERI_MODE "transmission"' in text
    assert 'DEVICE_CLASS "OUTPUT"' in text      # as chartread -t writes it
    notes = M.barbieri_notes(v)
    assert any("Transparent" in n and "GitHub" in n for n in notes)


# ---- several pages ----------------------------------------------------------

@pytest.fixture(scope="module")
def two_pages(tmp_path_factory):
    from workflow.barbieri import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        ti2, side = _chart(tmp_path_factory.mktemp("pages"), 1300,
                           paper="A4R")
    finally:
        support._latched = before
    return ti2, side


def test_each_page_file_finds_its_page_whatever_the_order(tmp_path,
                                                          two_pages):
    ti2, side = two_pages
    assert len(side["pages_detail"]) == 2
    files = []
    for page in (1, 0):
        sp = readings_for(ti2, side, page)
        files.append(write_spectro32(tmp_path / f"p{page}_measurements.txt",
                                     sp))
    v = _assess(files, ti2)
    assert v.ok, v.reason
    assert [p.page for p in v.pages] == [1, 2]
    assert v.pages[0].file.name == "p0_measurements.txt"
    from workflow.barbieri.spectro32_import import write_ti3
    from workflow.measurement_state import expected_patches
    from workflow.ti3_analysis import parse_ti3
    out = write_ti3(v, ti2, tmp_path / "out")
    assert parse_ti3(out).n_patches == expected_patches(ti2)


def test_a_chart_of_two_pages_needs_both_files(tmp_path, two_pages):
    ti2, side = two_pages
    a = write_spectro32(tmp_path / "a_measurements.txt",
                        readings_for(ti2, side, 0))
    v = _assess(a, ti2)
    assert not v.ok and v.code == "pages-one"
    v = _assess([a, a], ti2)
    assert not v.ok and v.code in ("same-page", "count")


# ---- the route and the Measure tab's door ------------------------------------

def test_assess_takes_only_a_paired_copy(tmp_path, owner):
    from workflow.barbieri.spectro32_import import write_ti3
    from workflow.measurement_import import assess
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side)
    from workflow.barbieri.spectro32_import import assess_files
    out = write_ti3(assess_files([f], ti2), ti2, tmp_path / "out")
    v = assess(out, ti2, source=f)
    assert v.ok and v.n_measured == 896
    # a copy that the door did not pair is refused
    bare = tmp_path / "bare.ti3"
    bare.write_text(out.read_text(encoding="utf-8").replace(
        "CHROMIQ_PAIRED_BY_BARBIERI_ORDER", "CHROMIQ_SOMETHING"),
        encoding="utf-8")
    v = assess(bare, ti2, source=f)
    assert not v.ok and v.barbieri_refusal


def test_with_the_beta_off_the_route_reads_nothing(tmp_path, owner,
                                                   monkeypatch):
    from workflow.barbieri import spectro32_import as S
    from workflow.barbieri import support
    from workflow.measurement_import import barbieri_route_applies
    ti2, _side = owner
    support.set_enabled_for_this_process(False)
    opened = []
    monkeypatch.setattr(S, "route_applies",
                        lambda c: opened.append(c) or True)
    assert barbieri_route_applies(ti2) is False
    assert opened == []


# ---- the door, filing into a profiling run ----------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _profiling_run(tmp_path, ti2):
    from PyQt6.QtCore import QSettings
    from core.file_manager import FileManager, Project
    from core.measurement_target import RUN_TYPE_PROFILING
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    run = fm.project().run("run1")
    shutil.copy2(ti2, run.chart_ti2)
    shutil.copy2(Path(str(ti2)[:-4] + ".barbieri.json"),
                 run.chart_ti2.parent / (run.chart_ti2.name[:-4] +
                                         ".barbieri.json"))
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    return s, fm, ctl, run


def _door(tmp_path, monkeypatch, ti2, paths, answer=True):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    import ui.measurement_filing as mf
    s, fm, ctl, run = _profiling_run(tmp_path, ti2)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    seen = {"done": [], "refused": [], "asked": [], "said": []}
    monkeypatch.setattr(tab, "_show_import_done_profiling",
                        lambda run, dst: seen["done"].append(dst))
    monkeypatch.setattr(tab, "_show_import_refusal",
                        lambda msg, **kw: seen["refused"].append(
                            (msg.id, kw)))
    monkeypatch.setattr(tab, "_ask_import_question",
                        lambda msg, *a, **k: seen["asked"].append(msg.id)
                        or answer)
    monkeypatch.setattr(tab, "_say_on_screen",
                        lambda t, b: seen["said"].append((t, b)))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    monkeypatch.setattr(mf, "refuse_it_does_not_belong",
                        lambda parent, reason: seen["refused"].append(reason))
    monkeypatch.setattr(mf, "say_what_was_filed", lambda parent, f: None)
    try:
        tab._switch_mode("import")
        tab._use_import_files(paths)
        seen["box"] = tab._import_box_body.text()
        tab._on_import_measurement()
        seen["log"] = tab._log.toPlainText()
    finally:
        tab.deleteLater()
    return run, seen


def test_the_door_files_it_as_the_runs_measurement(tmp_path, owner, qapp,
                                                   monkeypatch):
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side)
    run, seen = _door(tmp_path / "w", monkeypatch, ti2, [f])
    assert not seen["refused"] and not seen["said"], seen
    assert seen["done"] == [run.measurement_ti3]
    assert "Spectro32 measurement" in seen["box"]
    assert "CHROMIQ_PAIRED_BY_BARBIERI_ORDER" in \
        run.measurement_ti3.read_text(encoding="utf-8")
    assert "896 Spectro32 readings" in seen["log"]


def test_the_door_refuses_a_mirrored_sheet_and_writes_nothing(
        tmp_path, owner, qapp, monkeypatch):
    ti2, side = owner
    f, _sp = _file(tmp_path, ti2, side, arrangement="mirrored")
    run, seen = _door(tmp_path / "w", monkeypatch, ti2, [f])
    assert [r[0] for r in seen["refused"]] == ["M-IMPORT-BARBIERI-REFUSED"]
    assert "mirrored" in seen["refused"][0][1]["reason"]
    assert not seen["done"] and not run.measurement_ti3.exists()


def test_the_door_asks_and_cancel_changes_nothing(tmp_path, owner, qapp,
                                                  monkeypatch):
    from workflow.barbieri.spectro32_import import spectra_xyz
    ti2, side = owner
    sp = readings_for(ti2, side)
    shifted = np.hstack([sp[:, 1:], sp[:, -1:]])
    f = write_spectro32(tmp_path / "x_measurements.txt", shifted,
                        xyz_override=spectra_xyz(sp))
    run, seen = _door(tmp_path / "w", monkeypatch, ti2, [f], answer=False)
    assert seen["asked"] == ["M-IMPORT-BARBIERI-COLOURS-DIFFER"]
    assert not seen["done"] and not run.measurement_ti3.exists()
