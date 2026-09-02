"""Tests for the colorant-agnostic .ti1 reader."""
import textwrap

import pytest

from workflow.layout_engine import ti1_reader

RGB_TI1 = textwrap.dedent("""\
    CTI1

    COLOR_REP "iRGB"

    NUMBER_OF_FIELDS 7
    BEGIN_DATA_FORMAT
    SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT

    NUMBER_OF_SETS 3
    BEGIN_DATA
    1 100.0 100.0 100.0 95.0 100.0 108.0
    2 0.0 0.0 0.0 1.0 1.0 1.0
    3 50.0 25.0 75.0 20.0 15.0 40.0
    END_DATA
    """)

CMYK_TI1 = textwrap.dedent("""\
    CTI1

    COLOR_REP "CMYK"

    NUMBER_OF_FIELDS 8
    BEGIN_DATA_FORMAT
    SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT

    NUMBER_OF_SETS 2
    BEGIN_DATA
    1 0.0 0.0 0.0 0.0 95.0 100.0 108.0
    2 100.0 0.0 0.0 0.0 20.0 30.0 60.0
    END_DATA
    """)

GRAY_TI1 = textwrap.dedent("""\
    CTI1
    COLOR_REP "W"
    BEGIN_DATA_FORMAT
    SAMPLE_ID GRAY_W XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT
    BEGIN_DATA
    1 100.0 95.0 100.0 108.0
    2 0.0 1.0 1.0 1.0
    END_DATA
    """)


def test_rgb(tmp_path):
    p = tmp_path / "rgb.ti1"; p.write_text(RGB_TI1, encoding="utf-8")
    t = ti1_reader.read_ti1(p)
    assert t.color_rep == "iRGB"
    assert t.device_fields == ["RGB_R", "RGB_G", "RGB_B"]
    assert t.n_channels == 3
    assert len(t.patches) == 3
    assert t.patches[0] == ((100.0, 100.0, 100.0), (95.0, 100.0, 108.0))
    # media = brightest (max XYZ_Y) = the white patch
    assert t.media_patch()[0] == (100.0, 100.0, 100.0)


def test_cmyk(tmp_path):
    p = tmp_path / "cmyk.ti1"; p.write_text(CMYK_TI1, encoding="utf-8")
    t = ti1_reader.read_ti1(p)
    assert t.color_rep == "CMYK"
    assert t.device_fields == ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
    assert t.n_channels == 4
    assert t.media_patch()[0] == (0.0, 0.0, 0.0, 0.0)   # 0 ink = white


def test_gray(tmp_path):
    p = tmp_path / "gray.ti1"; p.write_text(GRAY_TI1, encoding="utf-8")
    t = ti1_reader.read_ti1(p)
    assert t.color_rep == "W"
    assert t.device_fields == ["GRAY_W"]
    assert t.n_channels == 1


def test_missing_data_raises(tmp_path):
    p = tmp_path / "bad.ti1"; p.write_text('COLOR_REP "iRGB"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        ti1_reader.read_ti1(p)
