"""4.3.5 B2: a chart that is not RGB is printed in the colour space of its INKS.

Measured on capture queues (reports ``2026-10-10_435_photoshop_cmyk`` and
``2026-10-10_435_B2``): every printing path chose the colour space from the
number of channels, so a CMY + orange chart (four channels) printed its orange
as BLACK, the layout engine's CMY chart was an RGB TIFF of inverted ink values
and went as RGB colours, and a chart of five or more inks could not be printed
from the Print Chart tab at all (PIL cannot open it).

And Basti, 2026-10-10: "no regressions please since rgb printing finally seemed
to work". The second half of this file pins what an RGB chart sends, on the
PostScript, PDF, raster TIFF and vendor-table (reference) paths.
"""
from __future__ import annotations

import base64
import json
import os
import re
import zlib
from pathlib import Path

import numpy as np
import pytest
import tifffile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import chart_inks  # noqa: E402
from workflow.postscript_generator import PdfGenerator, PostScriptGenerator  # noqa: E402


# --- charts -------------------------------------------------------------------
def _page(n: int, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 256, (6, 5, n), dtype=np.uint8)
    return np.repeat(np.repeat(a, 8, 0), 8, 1)


def _separated(path: Path, n: int, codes: list[str] | None, *, rep: str | None = None,
               inkset: bool | None = None, pages: int = 1) -> np.ndarray:
    arrs = [_page(n, seed=3 + i) for i in range(pages)]
    if codes and codes == ["c", "m", "y"] and n == 4:
        for a in arrs:
            a[..., 3] = 0
    kw = dict(photometric="separated", resolution=(118.11, 118.11), resolutionunit=3)
    if inkset:
        kw["extratags"] = [(332, "H", 1, 1, True)]
    if n > 4:
        kw["extrasamples"] = ("unspecified",) * (n - 4)
    with tifffile.TiffWriter(str(path)) as tw:
        for a in arrs:
            tw.write(a, **kw)
    if codes is not None:
        path.with_suffix(".channels.json").write_text(json.dumps({"ink_channels": codes}))
    if rep is not None:
        path.with_suffix(".ti2").write_text(f'CTI2\n\nCOLOR_REP "{rep}"\n')
    return arrs[0]


def _decoded_ps_image(ps: str) -> bytes:
    i = ps.index("colorimage")
    start = ps.index("\n", i) + 1
    end = ps.index("~>", start)
    return zlib.decompress(base64.a85decode(re.sub(r"\s", "", ps[start:end])))


def _cs(ps: str) -> str:
    m = re.search(r"(/Device\w+ setcolorspace|\[/DeviceN \[[^\]]*\])", ps)
    return m.group(1)


# --- 1. the colour space follows the inks --------------------------------------
def test_cmy_plus_orange_is_devicen_never_cmyk(tmp_path):
    """MUTATION: drop the n == 4 DeviceN branch of ``chart_inks.plan_for`` and
    this goes red: orange is then the fourth channel of /DeviceCMYK, black."""
    t = tmp_path / "cmyo.tif"
    arr = _separated(t, 4, ["c", "m", "y", "o"])
    ps = PostScriptGenerator().generate(t, ink_channels=["c", "m", "y", "o"])
    assert _cs(ps) == "[/DeviceN [/Cyan /Magenta /Yellow /Orange]"
    assert "/DeviceCMYK setcolorspace" not in ps
    assert _decoded_ps_image(ps) == arr.tobytes()          # the values themselves
    pdf = PdfGenerator().generate(t, ink_channels=["c", "m", "y", "o"])
    assert b"/ColorSpace [/DeviceN [/Cyan /Magenta /Yellow /Orange] /DeviceCMYK 6 0 R]" in pdf
    assert b"/FunctionType 4" in pdf


def test_the_ink_list_comes_from_the_ti2_when_there_is_no_sidecar(tmp_path):
    t = tmp_path / "cmyo.tif"
    _separated(t, 4, None, rep="CMYO")
    assert _cs(PostScriptGenerator().generate(t)) == "[/DeviceN [/Cyan /Magenta /Yellow /Orange]"


def test_cmy_and_cmyk_stay_devicecmyk(tmp_path):
    for codes in (["c", "m", "y"], ["c", "m", "y", "k"]):
        t = tmp_path / f"{''.join(codes)}.tif"
        arr = _separated(t, 4, codes, inkset=True)
        ps = PostScriptGenerator().generate(t, ink_channels=codes)
        assert _cs(ps) == "/DeviceCMYK setcolorspace"
        assert _decoded_ps_image(ps) == arr.tobytes()


@pytest.mark.parametrize("codes", [["c", "m", "y", "k", "o"], ["c", "m", "y", "k", "o", "g"],
                                   ["c", "m", "y", "k", "lc", "lm", "lk"]])
def test_five_to_seven_inks_are_devicen_with_their_names(tmp_path, codes):
    t = tmp_path / "multi.tif"
    arr = _separated(t, len(codes), codes)
    ps = PostScriptGenerator().generate(t, ink_channels=codes)
    assert _cs(ps).startswith("[/DeviceN [/Cyan /Magenta /Yellow /Black /")
    assert _decoded_ps_image(ps) == arr.tobytes()


def test_a_cmy_chart_the_engine_wrote_before_435_prints_as_cmyk_with_k_0(tmp_path):
    """An RGB TIFF of ``255 - ink`` with a CMY ink list: converted on read,
    exactly (the stored values are the inverted ink values)."""
    t = tmp_path / "old.tif"
    ink = _page(3)
    tifffile.imwrite(t, (255 - ink).astype(np.uint8), photometric="rgb",
                     resolution=(118.11, 118.11), resolutionunit=3)
    t.with_suffix(".channels.json").write_text(json.dumps({"ink_channels": ["c", "m", "y"]}))
    plan = chart_inks.plan_for_file(t)
    assert plan is not None and plan.legacy_engine_cmy and plan.space == "DeviceCMYK"
    ps = PostScriptGenerator().generate(t, ink_channels=["c", "m", "y"])
    assert _cs(ps) == "/DeviceCMYK setcolorspace"
    want = np.concatenate([ink, np.zeros(ink.shape[:2] + (1,), np.uint8)], 2)
    assert _decoded_ps_image(ps) == want.tobytes()
    assert not chart_inks.is_rgb_page(t)


# --- 2. the inks are named in words ----------------------------------------------
@pytest.mark.parametrize("codes,n,want", [
    (["c", "m", "y"], 4, "CMY, 3 inks"),
    (["c", "m", "y", "k0"], 4, "CMY, 3 inks"),
    (["c", "m", "y", "k"], 4, "CMYK, 4 inks"),
    (None, 4, "CMYK, 4 inks"),
    (["c", "m", "y", "o"], 4, "CMY + Orange, 4 inks"),
    (["c", "m", "y", "k", "o"], 5, "CMYK + Orange, 5 inks"),
    (["c", "m", "y", "k", "o", "g"], 6, "CMYK + Orange + Green, 6 inks"),
    (["c", "m", "y", "k", "lc", "lm", "lk"], 7,
     "CMYK + Light cyan + Light magenta + Light black, 7 inks"),
])
def test_the_ink_set_label(codes, n, want):
    assert chart_inks.ink_set_label(codes, n) == want


def test_the_extra_inks_in_words():
    assert chart_inks.extra_ink_label(["c", "m", "y", "o"]) == "Orange"
    assert chart_inks.extra_ink_label(["c", "m", "y", "k", "o", "g"]) == "Orange, Green"


# --- 3. the macOS dialog route refuses, naming the inks ----------------------------
@pytest.mark.parametrize("n,codes,label", [
    (6, ["c", "m", "y", "k", "o", "g"], "CMYK + Orange + Green, 6 inks"),
    (4, ["c", "m", "y", "o"], "CMY + Orange, 4 inks"),
    (4, ["c", "m", "y"], "CMY, 3 inks"),
])
def test_the_dialog_route_refuses_before_pil_and_names_the_inks(tmp_path, n, codes, label):
    """MUTATION: remove ``_refuse_unless_rgb`` from ``print_frames`` and a six-ink
    chart reaches PIL, which cannot open it ("cannot identify image file")."""
    from workflow.native_print_macos import ChartIsNotRGB, _refuse_unless_rgb
    t = tmp_path / "chart.tif"
    _separated(t, n, codes)
    with pytest.raises(ChartIsNotRGB) as e:
        _refuse_unless_rgb(t, 0)
    assert str(e.value) == label


def test_the_dialog_route_refuses_an_old_engine_cmy_chart(tmp_path):
    from workflow.native_print_macos import ChartIsNotRGB, _refuse_unless_rgb
    t = tmp_path / "old.tif"
    tifffile.imwrite(t, _page(3), photometric="rgb")
    t.with_suffix(".channels.json").write_text(json.dumps({"ink_channels": ["c", "m", "y"]}))
    with pytest.raises(ChartIsNotRGB, match="CMY, 3 inks"):
        _refuse_unless_rgb(t, 0)


def test_the_dialog_route_lets_an_rgb_chart_through(tmp_path):
    from workflow.native_print_macos import _refuse_unless_rgb
    t = tmp_path / "rgb.tif"
    tifffile.imwrite(t, _page(3), photometric="rgb")
    t.with_suffix(".channels.json").write_text(json.dumps({"ink_channels": ["r", "g", "b"]}))
    _refuse_unless_rgb(t, 0)          # no exception


# --- 4. a page is split with tifffile, keeping every channel -------------------------
def test_a_page_of_a_six_ink_chart_is_split_with_every_channel(tmp_path):
    """MUTATION: split with PIL (``Image.open``) and this raises."""
    t = tmp_path / "multi.tif"
    _separated(t, 6, ["c", "m", "y", "k", "o", "g"], pages=2)
    out = chart_inks.split_page(t, 1)
    try:
        with tifffile.TiffFile(str(out)) as tf:
            pg = tf.pages[0]
            assert pg.shape[2] == 6 and int(pg.photometric) == 5
            assert np.array_equal(pg.asarray(), _page(6, seed=4))
    finally:
        out.unlink()
    assert chart_inks.split_page(tmp_path / "multi.tif", 0) is not None
    single = tmp_path / "single.tif"
    _separated(single, 6, ["c", "m", "y", "k", "o", "g"])
    assert chart_inks.split_page(single, 0) is None


def test_the_print_tab_prints_a_six_ink_chart_with_its_inks(tmp_path, monkeypatch):
    """The direct route of the Print Chart tab reached ``Image.open`` first and
    stopped there for five inks or more ("Cannot read TIFF file")."""
    from ui.tabs import tab_print as tp
    t = tmp_path / "multi.tif"
    _separated(t, 6, ["c", "m", "y", "k", "o", "g"], pages=2)
    seen = {}

    class _Printer:
        last_job_id = None

        def print_job_ps(self, path, config, ink_channels=None, on_finish=None, **kw):
            with tifffile.TiffFile(str(path)) as tf:
                seen["shape"] = tf.pages[0].shape
            seen["inks"] = ink_channels
            on_finish(0)

    class _Module:
        def build_config(self, printer, options):
            return object()

    tab = tp.TabPrint.__new__(tp.TabPrint)
    tab._printer_combo = type("C", (), {"currentData": lambda self: "Q"})()
    tab._option_combos = {}
    tab._module = _Module()
    tab._printer = _Printer()
    tab._settings = {}
    tab._set_status = lambda text: None
    tab._on_print_done = lambda code: None
    monkeypatch.setattr(tp, "is_macos", lambda: False)
    assert tp.TabPrint._send_page(tab, t, 1) is True
    assert seen["shape"][2] == 6
    assert seen["inks"] == ["c", "m", "y", "k", "o", "g"]


# --- 5. the layout engine writes CMY as printtarg does ---------------------------------
def test_the_engine_writes_cmy_as_cmyk_with_k_0(tmp_path):
    """MUTATION: drop the ``is_cmy_target`` branch of ``build_chart`` and the
    TIFF is RGB again (photometric 2, three channels)."""
    from workflow.layout_engine import raster
    from workflow.layout_engine.chart import build_chart
    ti1 = tmp_path / "cmy.ti1"
    rows = "\n".join(f"{i + 1} {c} {m} {y} 50 50 50" for i, (c, m, y) in enumerate(
        [(0, 0, 0), (100, 0, 0), (0, 100, 0), (0, 0, 100), (50, 25, 75), (100, 100, 100)] * 4))
    ti1.write_text('CTI1\n\nCOLOR_REP "CMY"\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
                   'SAMPLE_ID CMY_C CMY_M CMY_Y XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n'
                   f'NUMBER_OF_SETS 24\nBEGIN_DATA\n{rows}\nEND_DATA\n')
    (tmp_path / "out").mkdir()
    res = build_chart(ti1, tmp_path / "out" / "cmy", instrument="i1", dpi=100)
    tif = [p for p in res.tiff_paths][0]
    with tifffile.TiffFile(str(tif)) as tf:
        pg = tf.pages[0]
        a = pg.asarray()
        assert int(pg.photometric) == 5 and a.shape[2] == 4
        assert pg.tags["InkSet"].value == 1
        assert a[..., 3].max() == 0                      # K is empty
    assert raster.is_cmy_target(type("T", (), {"n_channels": 3, "device_fields": ["CMY_C", "CMY_M", "CMY_Y"]})())


def test_four_inks_that_are_not_cmyk_get_no_inkset(tmp_path):
    from workflow.layout_engine import raster
    p = raster.save_separated_tiffs([np.zeros((4, 4, 4), np.uint8)], tmp_path / "cmyo.tif",
                                    ink_names=["Cyan", "Magenta", "Yellow", "Orange"])
    with tifffile.TiffFile(str(p[0])) as tf:
        assert tf.pages[0].tags.get("InkSet") is None


def test_the_vector_pdf_of_a_cmy_chart_fills_with_cmyk(tmp_path):
    from workflow.layout_engine import vector_pdf
    ops = vector_pdf._fill_color_op((0.5, 0.25, 0.0, 0.0), 4)
    assert ops.endswith(" k")
    assert vector_pdf._fill_color_op((0.1, 0.2, 0.3, 0.4), 4, devicen=True).endswith(" scn")


# --- 6. i1Profiler: a chart of other inks is skipped with one line -----------------------
def test_the_i1profiler_export_skips_cmy_with_a_log_line(tmp_path, caplog):
    from workflow.chart_exports import write_sidecars
    from workflow.i1profiler_export import UnsupportedInkSet, export_from_ti1
    ti1 = tmp_path / "c.ti1"
    ti1.write_text('CTI1\n\nCOLOR_REP "CMY"\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
                   'SAMPLE_ID CMY_C CMY_M CMY_Y\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 1\n'
                   'BEGIN_DATA\n1 10 20 30\nEND_DATA\n')
    with pytest.raises(UnsupportedInkSet):
        export_from_ti1(ti1, tmp_path, base_name="x")
    import logging
    caplog.set_level(logging.INFO)
    write_sidecars(ti1, tmp_path / "exp", base_name="c")
    rec = [r for r in caplog.records if "i1Profiler export" in r.getMessage()]
    assert rec and all(r.levelno == logging.INFO and not r.exc_info for r in rec)


# --- 7. which queues convert the inks ----------------------------------------------------
_RGB_RASTER = ('*cupsFilter: "application/vnd.cups-raster 0 x"\n*DefaultColorModel: RGB\n'
               '*ColorModel RGB/RGB: "<</cupsColorSpace 1>>setpagedevice"\n')
_CMYK_RASTER = ('*cupsFilter: "application/vnd.cups-raster 0 x"\n*DefaultColorModel: CMYK\n'
                '*ColorModel CMYK/CMYK: "<</cupsColorSpace 6>>setpagedevice"\n')
_POSTSCRIPT = '*PPD-Adobe: "4.3"\n*ColorDevice: True\n'
_PDF = '*cupsFilter: "application/pdf 0 x"\n'


@pytest.mark.parametrize("ppd,space,want", [
    (_RGB_RASTER, "DeviceCMYK", "converted"), (_RGB_RASTER, "DeviceN", "converted"),
    (_CMYK_RASTER, "DeviceCMYK", None), (_CMYK_RASTER, "DeviceN", "approximate"),
    (_POSTSCRIPT, "DeviceCMYK", None), (_POSTSCRIPT, "DeviceN", "approximate"),
    (_PDF, "DeviceCMYK", None), (None, "DeviceN", None),
])
def test_the_ink_route(ppd, space, want):
    from workflow.ppd_color import ink_route
    assert ink_route(ppd, space) == want


def test_a_converted_job_is_not_called_confirmed(monkeypatch):
    """MUTATION: drop the ``ink_conversion`` branch of ``_report_job_ticket`` and
    the status line says "The printing system confirms ..." for a chart macOS
    converted."""
    from ui.tabs import tab_print as tp
    tab = tp.TabPrint.__new__(tp.TabPrint)
    said = []
    tab._set_status = said.append
    rep = type("R", (), {"read": True, "ok": True, "mismatches": {}, "paper_profile": None,
                         "carried": {}, "tag_matches_job": None, "job_id": 7})()
    tp.TabPrint._report_job_ticket(tab, rep, ("converted", "CMYK, 4 inks", ""))
    assert said and "confirms" not in said[-1]
    said.clear()
    monkeypatch.setattr(tp, "_reset_vendors", lambda r: set())
    tp.TabPrint._report_job_ticket(tab, rep, None)        # an RGB job: as before
    assert "confirms" in said[-1]


def test_an_rgb_chart_is_never_asked_about_its_inks(tmp_path):
    from ui.tabs import tab_print as tp
    t = tmp_path / "rgb.tif"
    tifffile.imwrite(t, _page(3), photometric="rgb")
    tab = tp.TabPrint.__new__(tp.TabPrint)
    assert tp.TabPrint._ink_conversion(tab, "Canon_PRO_300_", {}, t) is None


# --- 8. RGB: what reaches the printer is pinned ---------------------------------------
# The PostScript of an RGB chart, everything except the image data, word for
# word as v4.3.4 and the branch before B2 write it; the image data must be the
# chart's own bytes. MUTATION: let ``_ink_plan`` return a plan for an RGB chart
# (DeviceCMYK) and this goes red.
_RGB_PS_FRAME = (
    "%!PS-Adobe-3.0\n%%LanguageLevel: 3\n%cupsJobTicket: cups-disable-cmm\n%%EndComments\n\n"
    "<< /PageSize [595.00 842.00] /ImagingBBox null /Duplex false /Tumble false >> setpagedevice\n\n"
    "/DeviceRGB setcolorspace\n\n"
    "{xo} {yo} translate\n{w} {h} scale\n40 48 8\n[40 0 0 -48 0 48]\n"
    "currentfile /ASCII85Decode filter /FlateDecode filter\nfalse 3\ncolorimage\n")


@pytest.fixture
def rgb_chart(tmp_path):
    t = tmp_path / "rgb.tif"
    arr = _page(3)
    tifffile.imwrite(t, arr, photometric="rgb", resolution=(118.11, 118.11), resolutionunit=3)
    t.with_suffix(".channels.json").write_text(json.dumps({"ink_channels": ["r", "g", "b"]}))
    return t, arr


def test_rgb_postscript_is_pinned(rgb_chart):
    t, arr = rgb_chart
    ps = PostScriptGenerator().generate(t, ink_channels=["r", "g", "b"], page_size_pt=(595.0, 842.0))
    w = 40 * 72 / (118.11 * 2.54)
    h = 48 * 72 / (118.11 * 2.54)
    frame = _RGB_PS_FRAME.format(xo=f"{(595 - w) / 2:.2f}", yo=f"{(842 - h) / 2:.2f}",
                                 w=f"{w:.2f}", h=f"{h:.2f}")
    assert ps.startswith(frame)
    assert ps.endswith("~>\n\nshowpage\n%%EOF\n")
    assert _decoded_ps_image(ps) == arr.tobytes()


def test_rgb_pdf_and_the_tagged_pdf_are_pinned(rgb_chart):
    t, arr = rgb_chart
    pdf = PdfGenerator().generate(t, ink_channels=["r", "g", "b"], page_size_pt=(595.0, 842.0))
    assert b"/ColorSpace /DeviceRGB" in pdf and b"DeviceN" not in pdf and b"ICCBased" not in pdf
    m = re.search(rb"/Length (\d+) >>\nstream\n", pdf[pdf.index(b"/Subtype /Image"):])
    start = pdf.index(b"/Subtype /Image") + m.end()
    assert zlib.decompress(pdf[start:start + int(m.group(1))]) == arr.tobytes()
    icc = b"\0" * 128 + b"fake"
    tagged = PdfGenerator().generate(t, page_size_pt=(595.0, 842.0), icc_profile=icc)
    assert b"/ColorSpace [/ICCBased 6 0 R]" in tagged


def test_rgb_reference_job_keeps_its_route(rgb_chart, monkeypatch):
    """The vendor-table (Canon/Epson) route is taken for an RGB chart exactly as
    before: ``_reference_paper_profile`` does not drop it."""
    from workflow import cups_printer as cp
    t, _arr = rgb_chart
    pp = type("PP", (), {"icc_path": str(t), "option": "X", "value": "1", "label": "L"})()
    monkeypatch.setattr(cp, "sys", type("S", (), {"platform": "darwin"}))
    monkeypatch.setattr(cp, "paper_profile_for_queue", lambda *a, **k: pp)
    assert cp.CupsRawPrinter._reference_paper_profile(t, cp.PrintConfig("Q")) is pp


def test_rgb_raster_tiff_fallback_is_unchanged(rgb_chart, monkeypatch):
    from workflow import cups_printer as cp
    t, _arr = rgb_chart
    sent = []
    pr = cp.CupsRawPrinter()
    monkeypatch.setattr(pr, "_run_lp", lambda cmd, on_finish: sent.append(cmd))
    pr._print_job_tiff(t, cp.PrintConfig("Q", {}))
    assert sent and sent[0][-1] == str(t)               # the chart itself, no copy
    assert "cupsColorSpace=DeviceRGB" in " ".join(sent[0])


# --- 9. the badge sits in the Inks row, on every tab --------------------------------------
@pytest.fixture
def hidden_preview(qapp, monkeypatch):
    """A preview inside a parent that is NOT on screen, as on the Print Chart
    and Measure tabs while another tab is shown."""
    from PyQt6.QtWidgets import QWidget
    from ui import tiff_preview as TP
    monkeypatch.setattr(TP, "last_render_mode", lambda: "approx")
    parent = QWidget()
    pv = TP.TiffPreview(parent)
    yield pv
    parent.deleteLater()


@pytest.mark.parametrize("codes", [["c", "m", "y", "k", "o", "g"], ["c", "m", "y"]])
def test_the_badge_goes_in_the_ink_row_even_while_the_tab_is_hidden(tmp_path, hidden_preview, codes):
    """MUTATION: test ``self._ink_row.isVisible()`` again and the badge floats
    over the image (top right, over the column letters) on Print Chart, as
    Basti saw it; leave CMY out of ``_current_ink_codes`` and a CMY chart has
    no Inks row to hold it."""
    pv = hidden_preview
    t = tmp_path / "chart.tif"
    _separated(t, 6 if len(codes) == 6 else 4, codes, inkset=len(codes) == 3)
    pv._pages = [(t, 0)]
    pv._ink_channels = None
    pv._rebuild_ink_row()
    assert not pv._ink_row.isHidden()
    pv._update_render_badge()
    assert not pv._ink_badge.isHidden()
    assert pv._ink_badge.full_text().startswith("Approximate colours")
    assert getattr(pv, "_badge_lbl", None) is None or pv._badge_lbl.isHidden()


def test_an_old_engine_cmy_chart_has_no_ink_row(tmp_path, hidden_preview):
    pv = hidden_preview
    t = tmp_path / "old.tif"
    tifffile.imwrite(t, _page(3), photometric="rgb")
    t.with_suffix(".channels.json").write_text(json.dumps({"ink_channels": ["c", "m", "y"]}))
    pv._pages = [(t, 0)]
    pv._ink_channels = None
    pv._rebuild_ink_row()
    assert pv._ink_row.isHidden()


def test_the_badge_is_one_line_when_the_row_has_room_and_elides_when_not(qapp):
    """Basti, 2026-10-11: the badge wrapped onto two lines beside free space.
    MUTATION: make it a word-wrapping QLabel again and the wide case goes red
    (it then asks for a fraction of its text's width)."""
    from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget
    from ui.tiff_preview import _OneLineFirstLabel
    text = "Approximate colours \u2014 the ink values in the file are exact"

    def row(width):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.addWidget(QLabel("Inks:"))
        chips = [QCheckBox(c) for c in "CMYK"]
        for c in chips:
            lay.addWidget(c)
        lay.addStretch(1)
        b = _OneLineFirstLabel("", w)
        b.setStyleSheet("QLabel { padding: 2px 8px; font-size: 11px; }")
        lay.addWidget(b)
        b.setText(text)
        w.resize(width, 40)
        w.show()
        for _ in range(3):
            qapp.processEvents()
        return w, b, chips

    w, b, chips = row(1000)
    assert b.text() == text and b.width() >= b.sizeHint().width() and not b.toolTip()
    assert all(c.geometry().right() < b.geometry().left() for c in chips)
    w.close()
    w, b, chips = row(260)
    assert b.full_text() == text
    assert b.text() != text and b.text().endswith("\u2026") and b.toolTip() == text
    assert all(c.geometry().right() < b.geometry().left() for c in chips)
    w.close()
