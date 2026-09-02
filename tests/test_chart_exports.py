"""Hand-off sidecars written alongside every chart (colours / i1Profiler).
Regression for the editor engine-save path that used to skip these, and the
Create Chart tab that only wrote them for i1iSis.

The engine keeps the ``emit_cht`` *capability* (exercised here), but production
charts no longer write a ``.cht`` at build time — a recognition template is only
meaningful paired with a *measured* ``.cie``, so both are produced together from
the measured ``.ti3`` after measurement (workflow.scanin_target, #97)."""
from pathlib import Path

from workflow.chart_exports import write_colours_txt, write_sidecars

_TI1 = (
    "CGATS.17\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
    "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
    "NUMBER_OF_SETS 4\nBEGIN_DATA\n"
    "1 100 100 100 95 100 108\n2 100 0 0 41 21 2\n"
    "3 0 100 0 36 71 12\n4 0 0 100 18 7 95\nEND_DATA\n"
)


def _build(tmp_path: Path):
    from workflow.layout_engine import chart as le_chart
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text(_TI1, encoding="utf-8")
    le_chart.build_chart(str(ti1), tmp_path / "chart", instrument="i1",
                         paper="A4", emit_cht=True)
    return ti1, tmp_path / "chart.ti2"


def test_emit_cht_writes_recognition_template(tmp_path):
    _build(tmp_path)
    cht = tmp_path / "chart.cht"
    assert cht.is_file()
    assert "BOXES" in cht.read_text(encoding="utf-8") and "EXPECTED XYZ" in cht.read_text(encoding="utf-8")


def test_write_colours_txt_rgb_only(tmp_path):
    ti1 = tmp_path / "c.ti1"
    ti1.write_text(_TI1, encoding="utf-8")
    p = write_colours_txt(ti1, tmp_path / "c-colours.txt")
    assert p is not None
    lines = p.read_text(encoding="utf-8").split()
    assert lines[:4] == ["#ffffff", "#ff0000", "#00ff00", "#0000ff"]
    # CMYK chart → no colour list
    cmyk = tmp_path / "k.ti1"
    cmyk.write_text("CTI1\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
                    "SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K\nEND_DATA_FORMAT\n"
                    "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 0 0 0 100\nEND_DATA\n",
                    encoding="utf-8")
    assert write_colours_txt(cmyk, tmp_path / "k-colours.txt") is None


def test_write_sidecars_writes_colours_and_i1profiler(tmp_path):
    ti1, _ti2 = _build(tmp_path)
    extras = write_sidecars(ti1, tmp_path, "chart")
    names = {e.name for e in extras}
    assert names == {"chart-colours.txt", "chart-i1profiler.txt",
                     "chart-i1profiler.pxf"}
    for n in names:
        assert (tmp_path / n).is_file()
    assert not (tmp_path / "chart.cie").exists()   # .cie dropped for now
