"""An i1Profiler "Measure Chart" measurement of ChromIQ's own i1iO sheet (the
i1iO Beta, one page; design 2026-11-14 with its challenge, §I.17).

Every reading is placed by ITS OWN Row/Column tag through the chart's side
file, never by colour; the colours only decide, and every mistake is REFUSED,
nothing is ever corrected. The files are made by a forward model of the scan
(`tests/i1p_forward.py`: three aimed points, i1Profiler's grid through them,
a 4 mm aperture on the printed sheet, a printer that is not targen's
estimate), from charts ChromIQ's own engine builds here.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import i1p_forward as F          # noqa: E402


@pytest.fixture(autouse=True)
def i1io_beta_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    """name -> .ti2 of the chart kinds the challenge names, plus a second
    build of the random set (the wrong chart with the same grid), a chart
    made without crosses and one with lettered patches."""
    from workflow.i1io import support
    root = tmp_path_factory.mktemp("mc_charts")
    rng = np.random.default_rng(5)
    out = {}
    for name, (rgbs, kw) in F.chart_sets(rng).items():
        out[name] = F.build_chart(root / name, rgbs, **kw)
    rand = F.chart_sets(np.random.default_rng(5))["random"][0]
    out["other-build"] = F.build_chart(root / "other", rand, seed=99)
    out["no-crosses"] = F.build_chart(root / "nocross", rand, seed=11,
                                      i1io_crosses=False)
    support._latched = None
    return out


def _copy_chart(ti2: Path, dst: Path) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for p in ti2.parent.glob(ti2.stem + "*"):
        if p.is_file():
            shutil.copy2(p, dst / p.name)
    return dst / ti2.name


def _assess(cxf: Path, ti2: Path, tmp: Path):
    from workflow.measurement_import import assess
    conv = F.convert(cxf, tmp / ("conv_" + cxf.stem))
    return assess(conv, ti2, source=cxf), conv


def _code(v) -> str:
    return v.i1io_grid.code if v.ok else getattr(v, "_code", "")


def _refused_with(v, ti2) -> str:
    """Which reason text the refusal carries (by the catalogue's own parts)."""
    from workflow import measurement_messages as MM
    assert not v.ok
    for code, part in (("grid", MM._I1IO_IMPORT_GRID),
                       ("count", MM._I1IO_IMPORT_COUNT),
                       ("places", MM._I1IO_IMPORT_PLACES),
                       ("pages", MM._I1IO_IMPORT_PAGES),
                       ("side", MM._I1IO_IMPORT_SIDE),
                       ("turned", MM._I1IO_IMPORT_TURNED),
                       ("aimed", MM._I1IO_IMPORT_AIMED),
                       ("unsure", MM._I1IO_IMPORT_UNSURE),
                       ("strip", MM._I1IO_IMPORT_STRIP),
                       ("other-chart", MM._I1IO_IMPORT_OTHER_CHART),
                       ("paper", MM._I1IO_IMPORT_PAPER),
                       ("beside", MM._I1IO_IMPORT_BESIDE),
                       ("text", MM._I1IO_IMPORT_TEXT)):
        head = part.split("{", 1)[0][:40]
        if v.reason.startswith(head):
            return code
    return "other: " + v.reason[:60]


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def test_row_is_the_strip_and_column_the_patch(charts):
    """i1Profiler's Row r = the r-th strip from the table's top, Column c =
    the (c+1)-th patch from the table's left; the three aim patches are the
    chart's own corner patches (top left, bottom left, bottom right)."""
    from workflow.i1io.measure_chart import measure_chart_grid
    side = json.loads(Path(str(charts["no-crosses"])[:-4] + ".i1io.json")
                      .read_text(encoding="utf-8"))
    g = measure_chart_grid(side, 1)
    assert (g.rows, g.columns) == (22, 24)
    assert g.loc[0][0] == "A1" and g.loc[0][23] == "A24"
    assert g.loc[1][0] == "B1" and g.loc[21][0] == "V1"
    corners = side["pages"][0]["corner_patches"]
    assert g.aim == (corners["top-left"]["loc"], corners["bottom-left"]["loc"],
                     corners["bottom-right"]["loc"])
    # the new record says the same, and an old side file without it works
    assert side["pages"][0]["measure_chart"]["aim_patches"] == list(g.aim)
    assert side["pages"][0]["measure_chart"]["columns"] == 24
    del side["pages"][0]["measure_chart"]
    assert measure_chart_grid(side, 1) == g


def test_the_grid_follows_the_coordinates_not_the_list_order(charts):
    from workflow.i1io.measure_chart import measure_chart_grid
    side = json.loads(Path(str(charts["random"])[:-4] + ".i1io.json")
                      .read_text(encoding="utf-8"))
    g = measure_chart_grid(side, 1)
    st = side["pages"][0]["strips"]
    st.reverse()
    for s in st:
        s["patches"].reverse()
    assert measure_chart_grid(side, 1) == g


# ---------------------------------------------------------------------------
# A right measurement: filed, every reading on its own patch
# ---------------------------------------------------------------------------

def test_a_right_measurement_is_filed_reading_by_reading(charts, tmp_path):
    from workflow.measurement_import import assess, complete_from_i1io_grid
    from workflow.ti3_analysis import parse_ti3
    ti2 = _copy_chart(charts["random"], tmp_path / "chart")
    sh = F.load_sheet(ti2)
    cxf = F.measure(sh, tmp_path / "right.cmxf")
    v, conv = _assess(cxf, ti2, tmp_path)
    assert v.ok and v.i1io_grid is not None, v.reason
    assert v.i1io_grid.code == "agree" and not v.i1io_grid.ask_why
    before = parse_ti3(conv)
    # converted row i is the reading i1Profiler wrote i-th, at (i % R, i // R)
    R = sh.rows
    want = {sh.grid[i % R][i // R][0]: before.xyz[i]
            for i in range(len(before.xyz))}
    assert complete_from_i1io_grid(conv, ti2, v) == 528
    filed = parse_ti3(conv)
    text = conv.read_text(encoding="utf-8")
    assert 'CHROMIQ_PAIRED_BY_I1IO_GRID "c.i1io.json page 1, 24 x 22"' in text
    assert 'CHROMIQ_I1IO_GRID_COLOURS "score=0.9' in text
    chart = {int(r.split()[0]): r.split() for r in
             ti2.read_text(encoding="utf-8").split("BEGIN_DATA\n", 1)[1].split("END_DATA")[0]
             .strip().splitlines()}
    for sid, xyz, rgb in zip(filed.sample_ids, filed.xyz, filed.rgb):
        sid = int(str(sid).strip('"'))
        assert np.allclose(xyz, want[sid]), sid
        assert np.allclose(rgb, [float(x) for x in chart[sid][2:5]])
    # in the chart's order, every patch once
    assert [int(str(s).strip('"')) for s in filed.sample_ids] == \
        sorted(chart)
    # an ordinary measurement now: §I.5 verifies it, a second filing is a
    # no-op (it is not a Measure Chart file any more)
    again = assess(conv, ti2)
    assert again.ok and again.i1io_grid is None and not again.turned_order


@pytest.mark.parametrize("name", ["random", "small", "no-crosses"])
def test_right_measurements_are_filed_with_realistic_noise(charts, tmp_path,
                                                           name):
    sh = F.load_sheet(charts[name])
    for k, noise in enumerate((0.8, 2.5, 5.0)):
        cxf = F.measure(sh, tmp_path / f"r{k}.cmxf",
                        rng=np.random.default_rng(10 + k), noise=noise)
        v, _ = _assess(cxf, charts[name], tmp_path)
        assert v.ok and v.i1io_grid.code == "agree", (noise, v.reason)


@pytest.mark.parametrize("name", ["sorted", "ramps", "near"])
def test_a_chart_that_cannot_tell_asks_and_never_files_in_silence(
        charts, tmp_path, name):
    sh = F.load_sheet(charts[name])
    cxf = F.measure(sh, tmp_path / "right.cmxf")
    v, _ = _assess(cxf, charts[name], tmp_path)
    assert v.ok and v.i1io_grid.ask_why in ("neighbours", "similar"), v.reason


def test_the_false_alarm_sweep(charts):
    """Right readings with noise up to 5 on every kind of chart: never
    refused (the net's thresholds were fixed by a wider sweep in the build:
    25 seeds x 5 kinds x 3 noises)."""
    from workflow.i1io.measure_chart import judge_readings
    from workflow.turned_colour_check import expected_lab_rgb, measured_lab
    refused = []
    for name in ("random", "small", "sorted", "ramps", "near", "greys"):
        sh = F.load_sheet(charts[name])
        R, C = sh.rows, sh.cols
        E = expected_lab_rgb([sh.rgb_of[sh.grid[j % R][j // R][0]]
                              for j in range(R * C)])
        for seed in range(8):
            rng = np.random.default_rng(300 + seed)
            # A chart of near-identical colours is judged by its fit
            # relative to the readings' spread (review M5); a scatter of
            # 2.5 dE per reading is half that spread and is refused there
            # (the safe side). Real readings scatter well under 1.5 dE.
            for noise in ((0.8, 1.5) if name == "near" else (0.8, 2.5, 5.0)):
                rd = F.scan(F.reader(sh, rng, noise), sh.right_aims(), R, C)
                M = measured_lab(np.array([F._lab_to_xyz_d50(l)
                                           for _, _, l in rd]))
                net = judge_readings(E, M, R, C)
                if net.action == "refuse":
                    refused.append((name, seed, noise, net.code, net.detail))
    assert not refused, refused


# ---------------------------------------------------------------------------
# Every mistake of the challenge: refused (or, where the chart's colours
# cannot tell, at least never filed in silence)
# ---------------------------------------------------------------------------

#: (chart, mistake) -> the reason. Every other pair must be refused with
#: the reason given here; the pairs in ASKED are the honest "cannot tell"
#: cases the challenge names (charts whose colours cannot judge them).
EXPECT = {
    "random": {"half-turn": "turned", "mirror-along": "aimed",
               "mirror-strips": "aimed", "transposed": "other-chart",
               "one-patch-along": "aimed", "one-strip-down": "aimed",
               "corner1-3.5mm-across": "beside", "aimed-crosses": "paper"},
    "small": {"half-turn": "turned", "mirror-along": "aimed",
              "mirror-strips": "aimed", "one-patch-along": "aimed",
              "one-strip-down": "aimed", "corner1-3.5mm-across": "beside"},
    "sorted": {"half-turn": "turned", "mirror-along": "aimed",
               "mirror-strips": "aimed", "transposed": "other-chart",
               "one-patch-along": "aimed", "one-strip-down": "aimed",
               "corner1-3.5mm-across": "beside", "aimed-crosses": "paper"},
    "ramps": {"half-turn": "turned", "mirror-along": "aimed",
              "mirror-strips": "aimed", "one-patch-along": "aimed",
              "one-strip-down": "aimed", "aimed-crosses": "paper"},
    "near": {"half-turn": "turned", "mirror-along": "aimed",
             "mirror-strips": "aimed", "one-patch-along": "aimed",
             "one-strip-down": "aimed", "corner1-3.5mm-across": "beside"},
}
#: Asked, never filed silently: the chart's colours cannot tell these.
ASKED = {("ramps", "corner1-3.5mm-across"),
         # (the near chart's transposed aim and crosses were asked before
         # review M5; refused now by the relative fit)
         # round 2: on near-identical colours (neighbouring strips under
         # 12 dE apart) the blend is not judged; asked, never filed
         ("near", "corner1-3.5mm-across")}
#: The mistakes of the challenge's list (the review's further aims are
#: tested below, on the charts that cannot tell).
ORIGINAL = ("half-turn", "mirror-along", "mirror-strips", "transposed",
            "one-patch-along", "one-strip-down", "corner1-3.5mm-across",
            "aimed-crosses")


@pytest.mark.parametrize("name", sorted(EXPECT))
def test_every_mistake_is_refused(charts, tmp_path, name):
    sh = F.load_sheet(charts[name])
    got = {}
    for mk, aims in F.mistakes(sh).items():
        if mk == "right" or mk not in ORIGINAL:
            continue
        cxf = F.measure(sh, tmp_path / f"{mk}.cmxf", aims,
                        rng=np.random.default_rng(3))
        v, _ = _assess(cxf, charts[name], tmp_path)
        if (name, mk) in ASKED:
            assert v.ok and v.i1io_grid.ask_why, (mk, v.reason)
            continue
        got[mk] = "filed" if v.ok else _refused_with(v, charts[name])
        if v.ok:
            continue
        assert "{" not in v.reason, v.reason
    want = {mk: c for mk, c in EXPECT[name].items()
            if (name, mk) not in ASKED}
    # every mistake refused; "aimed" may come as the unsure wording
    norm = {k: ("aimed" if g == "unsure" else g) for k, g in got.items()}
    assert norm == {k: want.get(k, norm[k]) for k in norm} and \
        "filed" not in norm.values(), (got, want)


def test_one_strip_shifted_names_the_strip(charts, tmp_path):
    sh = F.load_sheet(charts["random"])
    R, C = sh.rows, sh.cols
    read = F.reader(sh, np.random.default_rng(4))
    rd = F.scan(read, sh.right_aims(), R, C)
    k = 9                                       # strip J slipped one patch
    for i, (r, c, lab) in enumerate(rd):
        if r == k:
            rd[i] = (r, c, read(*sh.point(k, c + 1)) if c + 1 < C
                     else F.PAPER)
    cxf = F.write_cmxf(tmp_path / "slip.cmxf", rd, columns=C, rows=R)
    v, _ = _assess(cxf, charts["random"], tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "strip"
    assert v.reason.startswith("strip J ")


def test_one_strip_read_back_to_front_is_refused(charts, tmp_path):
    sh = F.load_sheet(charts["random"])
    R, C = sh.rows, sh.cols
    rd = F.scan(F.reader(sh, np.random.default_rng(4)), sh.right_aims(), R, C)
    labs = {(r, c): lab for r, c, lab in rd}
    rd = [(r, c, labs[(r, C - 1 - c)] if r == 5 else lab)
          for r, c, lab in rd]
    cxf = F.write_cmxf(tmp_path / "rev.cmxf", rd, columns=C, rows=R)
    v, _ = _assess(cxf, charts["random"], tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "strip"


# ---------------------------------------------------------------------------
# Exact refusals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typed", [(22, 24), (24, 21), (23, 22)])
def test_another_grid_typed_is_refused_with_the_right_numbers(
        charts, tmp_path, typed):
    sh = F.load_sheet(charts["random"])
    cxf = F.measure(sh, tmp_path / "g.cmxf", typed=typed)
    v, _ = _assess(cxf, charts["random"], tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "grid"
    assert v.i1io_refusal                  # its own window (review m3)
    assert f"grid of {typed[0]} columns and {typed[1]} rows" in v.reason
    assert "needs 24 columns and 22 rows" in v.reason


def test_a_missing_row_or_a_cell_twice_is_refused(charts, tmp_path):
    sh = F.load_sheet(charts["random"])
    R, C = sh.rows, sh.cols
    rd = F.scan(F.reader(sh, np.random.default_rng(1)), sh.right_aims(), R, C)
    short = [x for x in rd if x[0] != R - 1]
    v, _ = _assess(F.write_cmxf(tmp_path / "short.cmxf", short, columns=C,
                                rows=R), charts["random"], tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "count"
    twice = list(rd)
    twice[5] = (twice[4][0], twice[4][1], twice[5][2])
    v, _ = _assess(F.write_cmxf(tmp_path / "twice.cmxf", twice, columns=C,
                                rows=R), charts["random"], tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "count"


def test_targets_and_readings_that_disagree_are_refused(charts, tmp_path):
    """S2: the place is the READING's own, checked against its Target."""
    sh = F.load_sheet(charts["random"])
    R, C = sh.rows, sh.cols
    rd = F.scan(F.reader(sh, np.random.default_rng(1)), sh.right_aims(), R, C)
    cells = [(r, c) for r, c, _ in rd]
    cells[0], cells[1] = cells[1], cells[0]
    v, _ = _assess(F.write_cmxf(tmp_path / "x.cmxf", rd, columns=C, rows=R,
                                target_cells=cells), charts["random"],
                   tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "places"
    v, _ = _assess(F.write_cmxf(tmp_path / "y.cmxf", rd, columns=C, rows=R,
                                drop_reading_tags=True), charts["random"],
                   tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) == "places"


def test_the_wrong_chart_with_the_same_grid_is_refused(charts, tmp_path):
    other = F.load_sheet(charts["other-build"])
    cxf = F.measure(other, tmp_path / "other.cmxf")
    v, _ = _assess(cxf, charts["random"], tmp_path)
    assert not v.ok and _refused_with(v, charts["random"]) in (
        "other-chart", "aimed", "unsure")


def test_a_side_file_of_another_build_is_refused(charts, tmp_path):
    ti2 = _copy_chart(charts["random"], tmp_path / "chart")
    shutil.copy2(Path(str(charts["other-build"])[:-4] + ".i1io.json"),
                 Path(str(ti2)[:-4] + ".i1io.json"))
    cxf = F.measure(F.load_sheet(charts["random"]), tmp_path / "r.cmxf")
    v, _ = _assess(cxf, ti2, tmp_path)
    assert not v.ok and _refused_with(v, ti2) == "side"


def test_a_chart_of_several_pages_is_refused_with_words(charts, tmp_path):
    ti2 = _copy_chart(charts["random"], tmp_path / "chart")
    side = Path(str(ti2)[:-4] + ".i1io.json")
    doc = json.loads(side.read_text(encoding="utf-8"))
    doc["page_count"] = 2
    side.write_text(json.dumps(doc), encoding="utf-8")
    cxf = F.measure(F.load_sheet(charts["random"]), tmp_path / "r.cmxf")
    v, _ = _assess(cxf, ti2, tmp_path)
    # 2026-11-16: several sheets come back through the profiling door of
    # the Measure tab (`workflow.i1io.pages`); `assess` itself, which the
    # verification door uses, still refuses a chart of several pages
    from workflow import measurement_messages as MM
    assert not v.ok and v.reason.startswith(
        MM._I1IO_PAGES_VERIFY.split("{", 1)[0])
    assert "2 pages" in v.reason


def test_a_text_export_is_refused_and_a_real_one_is_not_taken(charts,
                                                              tmp_path):
    """S3: a text export without device values or with the placeholders is
    refused on an i1iO chart; one with real device values goes on as before
    (the route does not take it)."""
    from workflow.measurement_import import assess
    ti2 = charts["random"]
    rows = []
    for i in range(528):
        rows.append(f'{i + 1} "A{i + 1}" 58.8235 58.8235 58.8235 40 41 42')
    txt = tmp_path / "m.ti3"
    txt.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "Argyll target"\n'
        'COLOR_REP "iRGB_XYZ"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\n\nNUMBER_OF_SETS 528\nBEGIN_DATA\n'
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    v = assess(txt, ti2, source=tmp_path / "m.txt")
    assert not v.ok and _refused_with(v, ti2) == "text"
    # the other doors (no picked file): one sentence to the Measure tab
    from workflow import measurement_messages as MM
    v = assess(txt, ti2)
    assert not v.ok and v.reason == MM.i1io_import_reason("other-door")


def test_a_cxf_with_real_device_values_is_not_this_route(charts, tmp_path):
    """i1Profiler's own iO chart printed from ChromIQ's patch sets carries
    real device values: the ordinary import judges it, unchanged."""
    from workflow.i1io.measure_chart import assess_file
    sh = F.load_sheet(charts["random"])
    cxf = F.measure(sh, tmp_path / "real.cmxf",
                    device=[(k % 256, (3 * k) % 256, 7) for k in range(528)])
    conv = F.convert(cxf, tmp_path / "c")
    assert assess_file(cxf, conv, charts["random"]) is None


def test_the_converter_is_unchanged_for_a_cmxf():
    """The converter does not take a .cmxf for a CxF (i1Profiler's
    "Measurement only" save): only the gated route reads it as one."""
    from workflow.reference_convert import is_cxf
    assert not is_cxf(Path("scan.cmxf"))
    assert is_cxf(Path("scan.mxf")) and is_cxf(Path("scan.cxf"))


def test_a_dual_scan_file_takes_the_chosen_condition(charts, tmp_path):
    sh = F.load_sheet(charts["random"])
    cxf = F.measure(sh, tmp_path / "dual.cmxf", conditions=("M0", "M1", "M2"))
    from workflow.i1io.measure_chart import convert
    from workflow.measurement_import import assess
    conv = convert(cxf, tmp_path / "c", condition="M2")
    assert 'MEASUREMENT_CONDITION "M2"' in conv.read_text(encoding="utf-8")
    v = assess(conv, charts["random"], source=cxf)
    assert v.ok and v.i1io_grid.code == "agree", v.reason


# ---------------------------------------------------------------------------
# The texts
# ---------------------------------------------------------------------------

def test_the_start_window_shows_the_charts_own_numbers(charts):
    from workflow import measurement_messages as MM
    from workflow.i1io.measure_chart import instruction_numbers
    nums = instruction_numbers(charts["random"])
    assert (nums["cols"], nums["rows"], nums["pages"]) == (24, 22, 1)
    title, body = MM.i1io_measure_chart_window(nums, by_hand=False)
    assert "set it to 24 columns and 22 rows" in body
    assert f"patch {nums['p1']} at the top left" in body
    assert MM.tr(MM._I1IO_MC_CROSSES) in body        # crosses: M3
    assert "aim the cross" not in body.lower().replace("cross hair", "")
    assert "{" not in body and "—" not in body
    # without crosses there is no crosses sentence, and no mark is named
    nums2 = instruction_numbers(charts["no-crosses"])
    assert nums2["crosses"] is False
    _t, body2 = MM.i1io_measure_chart_window(nums2, by_hand=True)
    assert MM.tr(MM._I1IO_MC_CROSSES) not in body2
    assert "mark 1" not in body2 and "cross 1" not in body2
    assert body2.endswith(MM.tr(MM._I1IO_OTHER_WAY_BY_HAND))
    # an unlabelled chart is told by position, never by a name
    nums2["labelled"] = False
    _t, body3 = MM.i1io_measure_chart_window(nums2, by_hand=False)
    assert nums2["p1"] not in body3.replace("i1Pro", "")
    assert "top-left corner of the block of patches" in body3


def test_the_false_sentence_is_gone():
    from workflow import measurement_messages as MM
    for m in MM.CATALOGUE.values():
        assert "cannot read ChromIQ's own i1iO sheet" not in m.body, m.id


# ---------------------------------------------------------------------------
# Review 2026-11-15, M1/M2: the neighbour-strip check on other papers
# ---------------------------------------------------------------------------

def _readings(sh, aims, paper, seed=0, noise=0.004):
    from workflow.turned_colour_check import expected_lab_rgb, measured_lab
    R, C = sh.rows, sh.cols
    rg = np.random.default_rng(seed)
    read = F.reader(sh, rg, noise, printer=F.InkPrinter(**F.PRINTERS[paper]))
    rd = F.scan(read, aims, R, C)
    E = expected_lab_rgb([sh.rgb_of[sh.grid[j % R][j // R][0]]
                          for j in range(R * C)])
    M = measured_lab(np.array([F._lab_to_xyz_d50(l) for _, _, l in rd]))
    return E, M


@pytest.mark.parametrize("paper", ["glossy", "glossy-extreme", "white"])
def test_a_good_sorted_chart_on_glossy_paper_is_not_refused(charts, paper):
    """M2: the printer's tone curve is not a neighbouring strip."""
    from workflow.i1io.measure_chart import judge_readings
    sh = F.load_sheet(charts["sorted"])
    for seed in (0, 1):
        E, M = _readings(sh, sh.right_aims(), paper, seed)
        net = judge_readings(E, M, sh.rows, sh.cols)
        assert net.action == "ask" and net.code == "cannot-tell", net.detail


@pytest.mark.parametrize("paper", ["matte", "low-gamut", "dark-paper",
                                   "cream-lowgamut", "white"])
@pytest.mark.parametrize("corner", ["corner1-3.5mm-across",
                                    "corner3-3.5mm-across",
                                    "all-3.5mm-across"])
def test_a_corner_aimed_3_5_mm_across_is_refused_on_every_paper(
        charts, paper, corner):
    """M1: one corner off blends the next strip in growing along the strip;
    filed silently before on matte, low-gamut and dark papers."""
    from workflow.i1io.measure_chart import judge_readings
    sh = F.load_sheet(charts["random"])
    E, M = _readings(sh, F.mistakes(sh)[corner], paper)
    net = judge_readings(E, M, sh.rows, sh.cols)
    assert net.action == "refuse", (net.code, net.detail)


# ---------------------------------------------------------------------------
# Review 2026-11-15, M5: the fit relative to the readings' spread
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["sorted", "near", "greys"])
@pytest.mark.parametrize("paper", ["white", "low-gamut", "glossy"])
def test_charts_that_cannot_tell_refuse_the_reviews_mistakes(charts, name,
                                                             paper):
    """Asked before (the person cannot know), refused now: the recorded
    order's fit residual is more than half the readings' spread. A right
    sheet is still asked, never refused."""
    from workflow.i1io.measure_chart import judge_readings
    sh = F.load_sheet(charts[name])
    E, M = _readings(sh, sh.right_aims(), paper)
    net = judge_readings(E, M, sh.rows, sh.cols)
    assert net.action == "ask", (net.code, net.detail)
    ms = F.mistakes(sh)
    for mk in ("transposed", "aim3-one-short", "aim1-one-patch-along",
               "aimed-crosses"):
        E, M = _readings(sh, ms[mk], paper)
        net = judge_readings(E, M, sh.rows, sh.cols)
        assert net.action == "refuse", (mk, net.code, net.detail)


def test_the_fit_limit_does_not_shrink_with_the_gamut(charts):
    """A transposed aim on a sorted chart, low-gamut printer: under 20 dE,
    which the absolute ceiling let through; refused by the relative one."""
    from workflow.i1io.measure_chart import fit_ranking, judge_readings
    sh = F.load_sheet(charts["sorted"])
    E, M = _readings(sh, F.mistakes(sh)["transposed"], "low-gamut")
    net = judge_readings(E, M, sh.rows, sh.cols)
    assert net.action == "refuse" and net.code == "other-chart", net.detail


def test_a_numbered_strip_is_named_as_a_strip_not_as_a_patch(tmp_path):
    """Review m1: numbered strips with lettered patches ("3A".."3X"): the
    refusal names strip "10", never a patch such as "10A"."""
    from workflow.i1io.measure_chart import _strip_name
    assert _strip_name(["3A", "3B", "3X"]) == "3"
    assert _strip_name(["10A", "10B"]) == "10"
    assert _strip_name(["A1", "A2", "A24"]) == "A"
    rng = np.random.default_rng(8)
    rgbs = [tuple(rng.uniform(0, 100, 3)) for _ in range(300)]
    ti2 = F.build_chart(tmp_path / "num", rgbs, seed=10,
                        strip_pattern="0-9,@-9,@-9;1-999",
                        patch_pattern="A-Z, A-Z")
    sh = F.load_sheet(ti2)
    R, C = sh.rows, sh.cols
    read = F.reader(sh, np.random.default_rng(4))
    rd = F.scan(read, sh.right_aims(), R, C)
    k = 9
    for i, (r, c, lab) in enumerate(rd):
        if r == k:
            rd[i] = (r, c, read(*sh.point(k, c + 1)) if c + 1 < C
                     else F.PAPER)
    cxf = F.write_cmxf(tmp_path / "slip.cmxf", rd, columns=C, rows=R)
    v, _ = _assess(cxf, ti2, tmp_path)
    strip = _strip_name(sh.loc_of[sh.grid[k][c][0]] for c in range(C))
    assert not v.ok and v.reason.startswith(f"strip {strip} "), v.reason
    assert strip.isdigit()
