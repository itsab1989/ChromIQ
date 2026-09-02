"""Tests for printer calibration read / apply / embed (hermetic, no Argyll)."""
import textwrap

from workflow.layout_engine import calibration

# Identity RGB cal (5-point).
LINEAR_CAL = textwrap.dedent("""\
    CAL

    DESCRIPTOR "Argyll Device Calibration Curves"
    COLOR_REP "RGB"

    NUMBER_OF_FIELDS 4
    BEGIN_DATA_FORMAT
    RGB_I RGB_R RGB_G RGB_B
    END_DATA_FORMAT

    NUMBER_OF_SETS 5
    BEGIN_DATA
    0.00 0.00 0.00 0.00
    0.25 0.25 0.25 0.25
    0.50 0.50 0.50 0.50
    0.75 0.75 0.75 0.75
    1.00 1.00 1.00 1.00
    END_DATA
    """)

# Non-identity: R squared-ish, G identity, B clipped to 0.5 max.
CURVE_CAL = textwrap.dedent("""\
    CAL
    COLOR_REP "RGB"
    BEGIN_DATA_FORMAT
    RGB_I RGB_R RGB_G RGB_B
    END_DATA_FORMAT
    BEGIN_DATA
    0.00 0.00 0.00 0.00
    0.50 0.25 0.50 0.50
    1.00 1.00 1.00 0.50
    END_DATA
    """)


def test_read_cal(tmp_path):
    p = tmp_path / "lin.cal"; p.write_text(LINEAR_CAL, encoding="utf-8")
    cal = calibration.read_cal(p)
    assert cal.color_rep == "RGB"
    assert cal.out_fields == ["RGB_R", "RGB_G", "RGB_B"]
    assert cal.n_channels == 3
    assert cal.input_axis.shape == (5,)


def test_identity_apply(tmp_path):
    p = tmp_path / "lin.cal"; p.write_text(LINEAR_CAL, encoding="utf-8")
    cal = calibration.read_cal(p)
    out = cal.apply((50.0, 0.0, 100.0))
    assert out[0] == 50.0 and out[1] == 0.0 and out[2] == 100.0


def test_curve_apply(tmp_path):
    p = tmp_path / "c.cal"; p.write_text(CURVE_CAL, encoding="utf-8")
    cal = calibration.read_cal(p)
    # R at 0.5 -> 0.25 -> 25 ; G identity -> 50 ; B clipped: 1.0 -> 0.5 -> 50
    out = cal.apply((50.0, 50.0, 100.0))
    assert abs(out[0] - 25.0) < 1e-6
    assert abs(out[1] - 50.0) < 1e-6
    assert abs(out[2] - 50.0) < 1e-6


def test_embed_text(tmp_path):
    p = tmp_path / "lin.cal"; p.write_text(LINEAR_CAL, encoding="utf-8")
    cal = calibration.read_cal(p)
    txt = calibration.cal_table_text(cal)
    assert txt.startswith("CAL")
    assert "BEGIN_DATA" in txt


def test_build_chart_embeds_and_applies(tmp_path):
    # hermetic: tiny RGB .ti1 + curve cal -> build_chart applies + embeds.
    from workflow.layout_engine import chart
    ti1 = tmp_path / "t.ti1"
    ti1.write_text(textwrap.dedent("""\
        CTI1
        COLOR_REP "RGB"
        BEGIN_DATA_FORMAT
        SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
        END_DATA_FORMAT
        BEGIN_DATA
        1 100.0 100.0 100.0 95.0 100.0 108.0
        2 50.0 50.0 100.0 30.0 30.0 60.0
        END_DATA
        """), encoding="utf-8")
    cal = tmp_path / "c.cal"; cal.write_text(CURVE_CAL, encoding="utf-8")
    res = chart.build_chart(ti1, tmp_path / "out", instrument="i1", paper="A4",
                            seed=1, dpi=72, cal_path=cal, apply_cal=True)
    text = res.ti2_path.read_text(encoding="utf-8")
    assert "COLOR_REP" in text
    # the embedded CAL table follows the CTI2 table
    assert text.count("BEGIN_DATA") >= 2
    assert "RGB_I" in text
