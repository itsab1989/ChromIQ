"""An i1iSis measurement of a chart of SEVERAL pages is brought back (part 1
of the i1iSis pieces work; CHALLENGE S1, S2; `workflow.isis.import_pages`).

4.3.67 refused every one ("needs a later version"). Now it is paired by
position through the order file, as one page is, and filed only when every
check says the pages went in as printed: every patch once (missing pages
named), i1Profiler's grid, its places in a form ChromIQ's own .txf predicts
(none is on record yet), the colours of
every page by the one-page judge, and the whole chart against every way the
pages can be fed wrongly (swapped, one page twice, the pages in another
order). Where the pages cannot be told apart by their colours the person is
asked, Cancel the default; nothing is filed on the wrong pages in silence.

Charts are the app's own engine's, on A4 (1,008 patches a page), 2 to 4
pages, randomised or not: random colours, the same sorted by lightness, a
device grid (targen -m), a grey ramp (targen -g), the channel ramps, one
colour. Readings are synthetic (a printer that is not targen's estimate,
drift over the sheet, noise).
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import i1p_forward as F                       # noqa: E402
from tests.test_isis_import_not_randomised import (     # noqa: E402
    Chart, _grid, _light, _ramps, _random)

SETS = {
    "random": _random(1500, 11),                  # 2 pages
    "sorted": _light(_random(2600, 12)),          # 3 pages
    "grid": _grid(12),                            # 1728: 2 pages
    "grid3": _grid(14),                           # 2744: 3 pages
    "grey": _ramps(1100, "K"),                    # 2 pages, cannot tell pages
    "ramps": _ramps(300, "RGBK"),                 # 1200: 2 pages
    "four": _random(3600, 13),                    # 4 pages
    "even": [(60.0, 60.0, 60.0)] * 1500,          # 2 pages, one colour
}
#: Sets whose pages, or patches, cannot be told apart by their colours: a
#: right measurement of them is asked about, never refused, and a wrong one
#: may be asked about too.
ALIKE = {"grey", "even"}
#: ...and sets whose single pages are too regular for the one-page judge
#: (a third of a sorted set spans a third of its lightness; ramps): a right
#: measurement may be asked about, never refused.
REGULAR = ALIKE | {"sorted", "ramps"}
#: Sets whose wrong ways may be asked about rather than refused (item 63's
#: "cannot tell" on ramps, one page by itself).
ASKS_WRONG = ALIKE | {"ramps"}


@pytest.fixture(scope="module")
def beta():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


@pytest.fixture(scope="module")
def charts(beta, tmp_path_factory):
    root, made = tmp_path_factory.mktemp("isis-pages"), {}

    def get(name, randomize=False) -> Chart:
        key = (name, randomize)
        if key not in made:
            made[key] = Chart(root / f"{name}-{randomize}", SETS[name],
                              randomize)
        return made[key]
    return get


def _assess(ti3, chart, **kw):
    from workflow.measurement_import import assess
    return assess(ti3, chart.ti2, **kw)


def sizes(c):
    k = c.R * c.C
    return [min(k, c.n - p * k) for p in range(c.P)]


def pages_as(c, src):
    """p[j] when page b of the file holds the readings of page src[b]."""
    k, s = c.R * c.C, sizes(c)
    out = list(range(c.n))
    for b, a in enumerate(src):
        if a != b:
            for i in range(s[b]):
                out[b * k + i] = a * k + i if i < s[a] else b * k + i
    return out


def page_ways(c):
    """Every way the pages can go in wrongly, and one page read wrongly."""
    P, k, s, R = c.P, c.R * c.C, sizes(c), c.R
    ways = {}
    for a in range(P):
        for b in range(P):
            if a < b:
                m = list(range(P))
                m[a], m[b] = b, a
                ways[f"pages {a + 1} and {b + 1} swapped"] = pages_as(c, m)
            if a != b:
                m = list(range(P))
                m[b] = a
                ways[f"page {a + 1} twice, as page {b + 1}"] = pages_as(c, m)
    ways["last page first"] = pages_as(c, [P - 1] + list(range(P - 1)))
    ways["the pages backwards"] = pages_as(c, list(range(P))[::-1])
    for q in range(P):
        p, cols = list(range(c.n)), -(-s[q] // R)
        for i in range(s[q]):
            cc, r = divmod(i, R)
            i2 = (cols - 1 - cc) * R + (R - 1 - r)
            if 0 <= i2 < s[q]:
                p[q * k + i] = q * k + i2
        ways[f"page {q + 1} half a turn"] = p
        p = list(range(c.n))
        for i in range(s[q]):
            p[q * k + i] = q * k + (i + R) % s[q]
        ways[f"page {q + 1} one column off"] = p
        p = list(range(c.n))
        for i in range(s[q]):
            cc, r = divmod(i, R)
            i2 = cc * R + (r + 1) % R
            if i2 < s[q]:
                p[q * k + i] = q * k + i2
        ways[f"page {q + 1} one row off"] = p
    return ways


def _same_colours(c, p):
    return [c.rgbs[c.ids[j] - 1] for j in p] == [c.rgbs[i - 1] for i in c.ids]


# ---- the charts ------------------------------------------------------------

def test_the_charts_have_the_pages_the_tests_need(charts):
    want = {"random": 2, "sorted": 3, "grid": 2, "grid3": 3, "grey": 2,
            "ramps": 2, "four": 4, "even": 2}
    assert {k: charts(k).P for k in want} == want
    assert charts("sorted").ids == list(range(1, 2601))
    assert charts("random", True).ids != sorted(charts("random", True).ids)


# ---- a right measurement ---------------------------------------------------

PRINTERS = [None, *F.PRINTERS]


@pytest.mark.parametrize("randomize", [False, True])
@pytest.mark.parametrize("name", sorted(SETS))
def test_a_right_measurement_is_never_refused(charts, tmp_path, name,
                                              randomize):
    if name == "even" and randomize:
        return             # refused in words: test_one_colour_randomised_...
    c = charts(name, randomize)
    for i, printer in enumerate(PRINTERS[::2] if c.n > 2000 else PRINTERS):
        for drift in (1.0, 3.0):
            v = _assess(c.measure(tmp_path / "m.ti3", None, printer, seed=i,
                                  drift=drift), c)
            assert v.ok, (printer, drift, v.reason)
            assert v.turned_order is randomize and not v.partial
            if name not in REGULAR or randomize:
                assert not v.isis_ask_why, (printer, drift, v.isis_ask_why)


def test_where_pages_look_alike_the_person_is_asked(charts, tmp_path):
    for name in sorted(ALIKE):
        v = _assess(charts(name).measure(tmp_path / "m.ti3"), charts(name))
        assert v.ok and v.isis_ask_why, name
    v = _assess(charts("even").measure(tmp_path / "m.ti3"), charts("even"))
    assert v.isis_ask_why == "pages"


# ---- every wrong way -------------------------------------------------------

@pytest.mark.parametrize("randomize", [False, True])
@pytest.mark.parametrize("name", ["random", "sorted", "grid", "grid3",
                                  "ramps", "four", "grey"])
def test_pages_fed_in_another_order_are_named(charts, tmp_path, name,
                                              randomize):
    from workflow import measurement_messages as MM
    c = charts(name, randomize)
    for way, p in page_ways(c).items():
        if not any(w in way for w in ("swapped", "twice", "first",
                                      "backwards")):
            continue
        v = _assess(c.measure(tmp_path / "m.ti3", p), c)
        assert not v.ok, way
        assert "went through the i1iSis in another order" in v.reason, (
            way, v.reason)
    s = list(range(c.P))
    s[0], s[1] = 1, 0
    v = _assess(c.measure(tmp_path / "m.ti3", pages_as(c, s)), c)
    assert v.reason in (MM.isis_pages_mixed_reason(1, 2),
                        MM.isis_pages_mixed_reason(2, 1)), v.reason


@pytest.mark.parametrize("randomize", [False, True])
def test_a_page_of_another_chart_is_refused(charts, tmp_path, randomize):
    from workflow import measurement_messages as MM
    c = charts("sorted", randomize)
    other = Chart(tmp_path / "o", _random(2600, 99), randomize)
    k = c.R * c.C
    m = c.measure(tmp_path / "m.ti3")
    o = other.measure(tmp_path / "o.ti3")
    lines, olines = (p.read_text(encoding="utf-8").splitlines()
                     for p in (m, o))
    a = lines.index("BEGIN_DATA") + 1
    # page 2's readings from the other chart, the device values this one's
    for j in range(k, 2 * k):
        mine, theirs = lines[a + j].split(), olines[a + j].split()
        lines[a + j] = " ".join(mine[:5] + theirs[5:])
    m.write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = _assess(m, c)
    assert not v.ok
    assert v.reason in (MM.isis_colours_reason(),
                        MM.isis_pages_mixed_reason(2, 1),
                        MM.isis_pages_mixed_reason(2, 3)), v.reason


@pytest.mark.parametrize("pages", [2, 1])
def test_one_colour_randomised_is_refused_in_true_words(beta, tmp_path,
                                                        pages):
    """Every order fits a randomised chart of one colour: refused, one page
    or several, with the i1iSis's own sentence (review of part 1, S3), never
    the turned chart's "measure this sheet in ChromIQ"."""
    from workflow import measurement_messages as MM
    c = Chart(tmp_path / "c", [(60.0, 60.0, 60.0)] * (1500 if pages == 2
                                                      else 400), True)
    assert c.P == pages
    v = _assess(c.measure(tmp_path / "m.ti3"), c)
    assert not v.ok and v.reason == MM.isis_order_unknown_reason(), v.reason
    assert "ChromIQ instead" not in v.reason and "Randomise" in v.reason


# ---- every patch once (R1) ---------------------------------------------------

@pytest.mark.parametrize("randomize", [False, True])
def test_a_missing_page_is_named(charts, tmp_path, randomize):
    c = charts("sorted", randomize)
    k = c.R * c.C
    v = _assess(c.measure(tmp_path / "m.ti3", keep=lambda j: j < 2 * k), c)
    assert not v.ok and "page 3 is not in it" in v.reason, v.reason
    assert "2 of the 3 pages" in v.reason
    v = _assess(c.measure(tmp_path / "m.ti3", keep=lambda j: j < k), c)
    assert not v.ok and "pages 2 and 3 are not in it" in v.reason, v.reason
    v = _assess(c.measure(tmp_path / "m.ti3",
                          keep=lambda j: not k <= j < 2 * k), c)
    assert "page 2 is not in it" in v.reason, v.reason
    # part of a page: counted, as on one page
    v = _assess(c.measure(tmp_path / "m.ti3", keep=lambda j: j < k + 5), c)
    assert not v.ok and f"{k + 5} of the {c.n} patches" in v.reason


@pytest.mark.parametrize("randomize", [False, True])
def test_an_extra_page_is_refused(charts, tmp_path, randomize):
    c = charts("random", randomize)
    p = c.measure(tmp_path / "m.ti3")
    lines = p.read_text(encoding="utf-8").splitlines()
    a, b = lines.index("BEGIN_DATA") + 1, lines.index("END_DATA")
    k = c.R * c.C
    extra = []
    for i, ln in enumerate(lines[a:a + k]):
        parts = ln.split()
        parts[0] = parts[1] = str(c.n + i + 1)
        parts[1] = f'"{parts[1]}"'
        extra.append(" ".join(parts))
    lines[b:b] = extra
    p.write_text("\n".join(lines).replace(
        f"NUMBER_OF_SETS {c.n}", f"NUMBER_OF_SETS {c.n + k}") + "\n",
        encoding="utf-8")
    assert not _assess(p, c).ok


@pytest.mark.parametrize("randomize", [False, True])
def test_patches_numbered_again_on_every_page_are_not_guessed(
        charts, tmp_path, randomize):
    """S2: if i1Profiler numbers SampleID per page, the file cannot be paired
    by position; refused with a request for the file."""
    c = charts("random", randomize)
    k = c.R * c.C
    v = _assess(c.measure(tmp_path / "m.ti3", ids=lambda j: str(j % k + 1)),
                c)
    assert not v.ok and "send us this file" in v.reason, v.reason


# ---- the grid and the places (R3, R4) ---------------------------------------

def write_cxf(path, c, read_of=None, *, columns=None, rows=None, pages=None,
              places="page-local", seed=1):
    """An i1Profiler-shaped CxF of chart *c*: real device values, M2,
    every Target and reading with a Location in the form *places*
    ("page-local", "counted-on", "handheld", "none")."""
    from workflow.isis.import_pages import place_of
    rng = np.random.default_rng(seed)
    read_of = list(read_of) if read_of is not None else list(range(c.n))
    R, C, P = c.R, c.C, c.P
    rows_total = -(-c.n // C)
    per = [-(-rows_total // P)] * P

    def loc(j):
        if places == "none":
            return None
        if places == "handheld":
            col, rg = divmod(j, rows_total)
            pg = 0
            while rg >= per[pg]:
                rg -= per[pg]
                pg += 1
            return pg + 1, rg, col
        return place_of(j, R, C, places == "counted-on")
    objs = []
    for j in range(c.n):
        lab = F.printer_lab(c.rgbs[c.ids[read_of[j]] - 1], rng, .4)
        sp = " ".join(f"{v:.5f}" for v in F.spectrum_for(lab))
        L = loc(j)
        tag = "" if L is None else (
            '<cc:TagCollection Name="Location">'
            f'<cc:Tag Name="Column" Value="{L[2]}"/>'
            f'<cc:Tag Name="Page" Value="{L[0]}"/>'
            f'<cc:Tag Name="Row" Value="{L[1]}"/></cc:TagCollection>')
        objs.append(
            f'<cc:Object ObjectType="M2_Measurement" Name="m{j + 1}" '
            f'Id="m{j + 1}"><cc:ColorValues><cc:ReflectanceSpectrum '
            f'StartWL="380" ColorSpecification="M2_Measurement_spec">{sp}'
            f'</cc:ReflectanceSpectrum></cc:ColorValues>{tag}</cc:Object>')
    for j in range(c.n):
        dv = [round(v * 2.55) for v in c.rgbs[c.ids[j] - 1]]
        L = loc(j)
        tag = "" if L is None else (
            '<cc:TagCollection Name="Location">'
            f'<cc:Tag Name="Column" Value="{L[2]}"/>'
            f'<cc:Tag Name="Page" Value="{L[0]}"/>'
            f'<cc:Tag Name="Row" Value="{L[1]}"/></cc:TagCollection>')
        objs.append(
            f'<cc:Object ObjectType="Target" Name="t{j + 1}" Id="t{j + 1}">'
            '<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="u">'
            f'<cc:R>{dv[0]}</cc:R><cc:G>{dv[1]}</cc:G><cc:B>{dv[2]}</cc:B>'
            f'</cc:ColorRGB></cc:DeviceColorValues>{tag}</cc:Object>')
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<cc:CxF xmlns:cc="http://colorexchangeformat.com/CxF3-core">\n'
        '<cc:FileInformation><cc:Creator>X-Rite - Prism</cc:Creator>'
        '<cc:CreationDate>2026-11-27T10:00:00+01:00</cc:CreationDate>'
        '</cc:FileInformation>\n<cc:Resources><cc:ObjectCollection>\n'
        + "\n".join(objs) + '\n</cc:ObjectCollection>'
        '<cc:ColorSpecificationCollection><cc:ColorSpecification '
        'Id="M2_Measurement_spec"><cc:MeasurementSpec><cc:MeasurementType>'
        'Spectrum_Reflectance</cc:MeasurementType><cc:WavelengthRange '
        'StartWL="380" Increment="10"/></cc:MeasurementSpec>'
        '</cc:ColorSpecification></cc:ColorSpecificationCollection>'
        '</cc:Resources>\n<cc:CustomResources><xrp:Prism xmlns:xrp="http://'
        'www.xrite.com/products/prism" release="2.0"><xrp:CustomAttributes '
        'MeasurementDevice="i1iSis" MeasurementMode="1" '
        f'NumberPatchColumns="{columns or C}" '
        f'NumberPatchPages="{P if pages is None else pages}" '
        f'NumberPatchRows="{rows or R}" SelectedMeasurementCondition="2"/>'
        '</xrp:Prism></cc:CustomResources>\n</cc:CxF>\n', encoding="utf-8")
    return path


def _import_cxf(c, cxf, tmp_path):
    from workflow.reference_convert import cxf_measurement_to_ti3
    ti3 = cxf_measurement_to_ti3(cxf, tmp_path / "conv.ti3")
    return _assess(ti3, c, source=cxf), ti3


@pytest.mark.parametrize("randomize", [False, True])
@pytest.mark.parametrize("places", ["page-local", "counted-on", "none"])
def test_the_forms_the_test_chart_predicts_are_filed(charts, tmp_path, randomize, places):
    c = charts("sorted", randomize)
    v, ti3 = _import_cxf(c, write_cxf(tmp_path / "m.mxf", c, places=places),
                         tmp_path)
    assert v.ok and not v.isis_ask_why, v.reason
    assert v.turned_order is randomize
    v, _ = _import_cxf(c, write_cxf(tmp_path / "m.mxf", c, places=places,
                                    pages=0), tmp_path)
    assert v.ok, ("pages 0 says nothing", v.reason)


@pytest.mark.parametrize("randomize", [False, True])
def test_another_grid_is_refused_with_both_named(charts, tmp_path,
                                                  randomize):
    c = charts("sorted", randomize)
    for kw in ({"columns": c.C + 1}, {"rows": c.R - 1}, {"pages": 1},
               {"pages": c.P + 1}):
        v, _ = _import_cxf(c, write_cxf(tmp_path / "m.mxf", c, **kw),
                           tmp_path)
        assert not v.ok and "asks for" in v.reason, (kw, v.reason)
        assert f"{c.C} columns and {c.R} rows on {c.P} pages" in v.reason


@pytest.mark.parametrize("randomize", [False, True])
def test_places_in_a_form_the_test_chart_does_not_predict_need_every_page_clear(
        charts, tmp_path, randomize):
    """R4: the handheld rule's places (or any other form) are filed only
    when the colours of every page clearly sit on their own patches; on a
    chart whose pages cannot be told apart they are refused, asking for
    the file."""
    c = charts("random", randomize)
    v, _ = _import_cxf(c, write_cxf(tmp_path / "m.mxf", c,
                                    places="handheld"), tmp_path)
    assert v.ok and not v.isis_ask_why, v.reason
    g = charts("grey", False)
    v, _ = _import_cxf(g, write_cxf(tmp_path / "g.mxf", g,
                                    places="handheld"), tmp_path)
    assert not v.ok and "send us this file" in v.reason, v.reason
    # ...and with the places the .txf predicts, the same file is asked about
    v, _ = _import_cxf(g, write_cxf(tmp_path / "g.mxf", g), tmp_path)
    assert v.ok and v.isis_ask_why


@pytest.mark.parametrize("randomize", [False, True])
def test_a_wrong_way_read_from_an_mxf_is_refused(charts, tmp_path,
                                                 randomize):
    c = charts("grid", randomize)
    for way in ("pages 1 and 2 swapped", "page 1 twice, as page 2",
                "page 2 half a turn"):
        v, _ = _import_cxf(c, write_cxf(tmp_path / "m.mxf", c,
                                        page_ways(c)[way]), tmp_path)
        assert not v.ok, way


# ---- filing ------------------------------------------------------------------

def test_a_randomised_measurement_is_filed_on_its_own_patches(charts,
                                                             tmp_path):
    """R7: the filing step pairs it through the order, on the grid of
    several pages, and every reading lands on the patch printed there."""
    from workflow.measurement_import import complete_from_turned_order
    from workflow.ti3_analysis import parse_ti3
    c = charts("four", True)
    cxf = write_cxf(tmp_path / "m.mxf", c)
    v, ti3 = _import_cxf(c, cxf, tmp_path)
    assert v.ok and v.turned_order
    assert complete_from_turned_order(ti3, c.ti2) == c.n
    got = parse_ti3(ti3)
    want = {str(i): c.rgbs[i - 1] for i in range(1, c.n + 1)}
    for sid, rgb in zip(got.sample_ids, got.rgb):
        assert np.allclose(rgb, want[str(sid)], atol=0.3), sid
    # ...and not on another grid, whichever door asks
    bad = write_cxf(tmp_path / "b.mxf", c, columns=c.C + 1)
    from workflow.reference_convert import cxf_measurement_to_ti3
    t2 = cxf_measurement_to_ti3(bad, tmp_path / "b.ti3")
    assert complete_from_turned_order(t2, c.ti2) == 0


@pytest.mark.parametrize("randomize", [False, True])
def test_without_the_order_file_the_side_file_is_enough(charts, tmp_path,
                                                        randomize):
    import shutil

    from workflow.measurement_import import assess
    c = charts("sorted", randomize)
    shutil.copytree(c.folder, tmp_path / "c")
    shutil.rmtree(tmp_path / "c" / "exports")
    ti2 = tmp_path / "c" / "c.ti2"
    v = assess(c.measure(tmp_path / "m.ti3"), ti2)
    if randomize:
        # the turned pairing needs the order file (as on one page): refused
        assert not v.ok
    else:
        assert v.ok, v.reason
        s = list(range(c.P))
        s[0], s[2] = 2, 0
        assert not assess(c.measure(tmp_path / "m.ti3", pages_as(c, s)),
                          ti2).ok


# ---- the question --------------------------------------------------------------

@pytest.mark.parametrize("go", [True, False])
def test_the_pages_question_at_the_filing_doors(qapp, monkeypatch, go):
    from PyQt6.QtWidgets import QMessageBox

    import ui.measurement_filing as MF
    from workflow.measurement_import import ImportVerdict
    said = []

    def ex(box):
        said.append((box.text(), box.informativeText(),
                     box.defaultButton().text()))
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda b: next(
            x for x in b.buttons()
            if (b.buttonRole(x) == QMessageBox.ButtonRole.AcceptRole) is go))
    monkeypatch.setattr(QMessageBox, "exec", ex)
    v = ImportVerdict(True, isis_ask_why="pages")
    assert MF.only_you_can_confirm_the_chart(None, v, None) is go
    assert said[0][0] == "ChromIQ cannot tell the pages of this measurement apart"
    assert "order of its page number" in said[0][1] and "{" not in said[0][1]
    assert said[0][2].replace("&", "") == "Cancel"


@pytest.mark.parametrize("go", [True, False])
def test_the_pages_question_on_the_measure_tab(go):
    from ui.tabs.tab_measure import TabMeasure as T
    from workflow import measurement_messages as MM
    from workflow.measurement_import import ImportVerdict
    said = []

    class Tab:
        class _log:
            appendPlainText = staticmethod(said.append)

        def _ask_import_question(self, message, label, **kw):
            said.append(message)
            return go
    assert T._isis_import_confirmed(
        Tab(), ImportVerdict(True, isis_ask_why="pages")) is go
    assert said[0] is MM.M_IMPORT_ISIS_PAGES_CANNOT_CHECK
    said.clear()
    T._isis_import_confirmed(Tab(), ImportVerdict(True, isis_ask_why="way"))
    assert said[0] is MM.M_IMPORT_ISIS_CANNOT_CHECK


# ---- nothing else changes --------------------------------------------------------

def test_beta_off_is_untouched(charts, tmp_path):
    from workflow.isis import support
    c = charts("random")
    s = list(range(c.P))
    s[0], s[1] = 1, 0
    p = c.measure(tmp_path / "m.ti3", pages_as(c, s))
    assert not _assess(p, c).ok
    support.set_enabled_for_this_process(False)
    try:
        assert _assess(p, c).ok            # 4.3.37's import, unchanged
    finally:
        support.set_enabled_for_this_process(True)
