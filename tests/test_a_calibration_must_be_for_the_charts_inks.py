"""#182 5956560815: "Apply & Embed (-K) fails with: calibration has 4 channels,
target has 3", from a PrintFab user with a CR30 and a CMYK calibration.

DRIVEN ON SCREEN FIRST (report folder AE_impl_cmyk_K): the engine applies a
4-channel CMYK .cal to a CMYK chart without complaint. What the user hit is
the order of work. They made the CMYK calibration chart with Device Type set
to CMYK, then switched Run type to Profiling, and a profiling run with nothing
stored opens on the DEFAULT Device Type, "Print RGB" (per_target_settings.md
§4 S4; a calibration never seeds a run, N-6). So the "450-patch CMYK chart"
that None built was an RGB chart, -K refused it in the engine's own words, and
-I quietly embedded a CMYK calibration in an RGB chart.

What this file holds:

* a CMYK chart with a CMYK calibration builds with -K: the .ti2 is CMYK, the
  calibration is embedded, and the patch values went through the curves;
* a calibration for other inks is refused for -K AND -I, as printtarg 3.5.0
  refuses both ("Calibration colorspace CMYK doesn't match .ti1 iRGB",
  measured), with a typed exception that says which is which;
* the refusal reaches a person as the build-failed window, in words that say
  what to change, from the engine and from printtarg's own line alike;
* an RGB calibration still goes on an RGB chart (print RGB or video RGB).
"""
from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.layout_engine import calibration, chart  # noqa: E402

CMYK_CAL = textwrap.dedent("""\
    CAL

    DESCRIPTOR "Argyll Device Calibration Curves"
    ORIGINATOR "Argyll printcal"
    DEVICE_CLASS "OUTPUT"
    COLOR_REP "CMYK"

    NUMBER_OF_FIELDS 5
    BEGIN_DATA_FORMAT
    CMYK_I CMYK_C CMYK_M CMYK_Y CMYK_K
    END_DATA_FORMAT

    NUMBER_OF_SETS 3
    BEGIN_DATA
    0.00 0.00 0.00 0.00 0.00
    0.50 0.30 0.40 0.25 0.45
    1.00 1.00 1.00 1.00 1.00
    END_DATA
    """)

RGB_CAL = textwrap.dedent("""\
    CAL
    COLOR_REP "iRGB"
    BEGIN_DATA_FORMAT
    RGB_I RGB_R RGB_G RGB_B
    END_DATA_FORMAT
    BEGIN_DATA
    0.00 0.00 0.00 0.00
    0.50 0.25 0.50 0.40
    1.00 1.00 1.00 1.00
    END_DATA
    """)


def _ti1(path: Path, rep: str, fields: list[str], rows: list[tuple]) -> Path:
    lines = ["CTI1", f'COLOR_REP "{rep}"', "BEGIN_DATA_FORMAT",
             "SAMPLE_ID " + " ".join(fields) + " XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "BEGIN_DATA"]
    for i, dev in enumerate(rows, 1):
        lines.append(f"{i} " + " ".join(f"{v:.4f}" for v in dev)
                     + " 50.0 50.0 50.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


CMYK_ROWS = [(0, 0, 0, 0), (50, 0, 0, 0), (0, 50, 0, 0), (0, 0, 50, 0),
             (0, 0, 0, 50), (50, 50, 50, 50), (100, 100, 100, 100)]
RGB_ROWS = [(100, 100, 100), (50, 50, 50), (0, 0, 0), (50, 100, 0)]


def _cmyk_ti1(tmp_path):
    return _ti1(tmp_path / "cmyk.ti1", "CMYK",
                ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"], CMYK_ROWS)


def _rgb_ti1(tmp_path, rep="iRGB"):
    return _ti1(tmp_path / "rgb.ti1", rep, ["RGB_R", "RGB_G", "RGB_B"], RGB_ROWS)


def _cal(tmp_path, text, name):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _ti2_device_rows(ti2: Path, fields: list[str]) -> dict[int, tuple]:
    import re
    text = ti2.read_text(encoding="utf-8")
    fmt = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", text,
                    re.S).group(1).split()
    body = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.S).group(1)
    idx = [fmt.index(f) for f in fields]
    out = {}
    for ln in body.splitlines():
        tok = ln.split()
        if tok and tok[0].isdigit():
            out[int(tok[0])] = tuple(float(tok[i]) for i in idx)
    return out


# ---- a CMYK chart with a CMYK calibration ------------------------------------

def test_minus_k_builds_a_cmyk_chart_with_a_cmyk_calibration(tmp_path):
    cal = _cal(tmp_path, CMYK_CAL, "cmyk.cal")
    res = chart.build_chart(_cmyk_ti1(tmp_path), tmp_path / "out",
                            instrument="CR30", paper="A4", seed=1, dpi=72,
                            cal_path=cal, apply_cal=True)
    text = res.ti2_path.read_text(encoding="utf-8")
    assert 'COLOR_REP "CMYK"' in text
    assert "CMYK_I CMYK_C CMYK_M CMYK_Y CMYK_K" in text, "the .cal is not embedded"
    rows = _ti2_device_rows(res.ti2_path, ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"])
    # 50 % of each ink alone goes through its own curve: C 30, M 40, Y 25, K 45
    assert rows[2] == pytest.approx((30, 0, 0, 0), abs=1e-3)
    assert rows[3] == pytest.approx((0, 40, 0, 0), abs=1e-3)
    assert rows[4] == pytest.approx((0, 0, 25, 0), abs=1e-3)
    assert rows[5] == pytest.approx((0, 0, 0, 45), abs=1e-3)
    assert rows[7] == pytest.approx((100, 100, 100, 100), abs=1e-3)


def test_minus_i_embeds_a_cmyk_calibration_without_touching_the_values(tmp_path):
    cal = _cal(tmp_path, CMYK_CAL, "cmyk.cal")
    res = chart.build_chart(_cmyk_ti1(tmp_path), tmp_path / "out",
                            instrument="CR30", paper="A4", seed=1, dpi=72,
                            cal_path=cal, apply_cal=False)
    assert "CMYK_I CMYK_C" in res.ti2_path.read_text(encoding="utf-8")
    rows = _ti2_device_rows(res.ti2_path, ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"])
    assert rows[2] == pytest.approx((50, 0, 0, 0), abs=1e-3)


@pytest.mark.parametrize("rep", ["iRGB", "RGB"])
def test_an_rgb_calibration_still_goes_on_an_rgb_chart(tmp_path, rep):
    cal = _cal(tmp_path, RGB_CAL, "rgb.cal")
    res = chart.build_chart(_rgb_ti1(tmp_path, rep), tmp_path / "out",
                            instrument="i1", paper="A4", seed=1, dpi=72,
                            cal_path=cal, apply_cal=True)
    rows = _ti2_device_rows(res.ti2_path, ["RGB_R", "RGB_G", "RGB_B"])
    assert rows[2] == pytest.approx((25, 50, 40), abs=1e-3)


# ---- a calibration for other inks ---------------------------------------------

@pytest.mark.parametrize("apply_cal", [True, False], ids=["-K", "-I"])
def test_a_cmyk_calibration_on_an_rgb_chart_is_refused(tmp_path, apply_cal):
    """-I too: printtarg refuses both, and an RGB chart carrying a CMYK
    calibration is wrong for anything that reads it afterwards."""
    cal = _cal(tmp_path, CMYK_CAL, "cmyk.cal")
    with pytest.raises(calibration.CalibrationMismatch) as info:
        chart.build_chart(_rgb_ti1(tmp_path), tmp_path / "out",
                          instrument="CR30", paper="A4", seed=1, dpi=72,
                          cal_path=cal, apply_cal=apply_cal)
    assert (info.value.cal_rep, info.value.chart_rep) == ("CMYK", "iRGB")
    assert not (tmp_path / "out.ti2").exists(), "a chart was written anyway"


def test_an_rgb_calibration_on_a_cmyk_chart_is_refused(tmp_path):
    cal = _cal(tmp_path, RGB_CAL, "rgb.cal")
    with pytest.raises(calibration.CalibrationMismatch):
        chart.build_chart(_cmyk_ti1(tmp_path), tmp_path / "out",
                          instrument="CR30", paper="A4", seed=1, dpi=72,
                          cal_path=cal, apply_cal=True)


def test_the_message_names_both_inks_and_what_to_change():
    text = calibration.calibration_mismatch_message("CMYK", "iRGB")
    assert "made for a CMYK chart" in text
    assert "you are building is RGB" in text, "iRGB must read as RGB"
    assert "Device Type" in text and "“None”" in text
    assert "channels" not in text, "the engine's words must not reach a person"
    assert "—" not in text


# ---- the window, from both layout routes --------------------------------------

def test_the_engine_refusal_becomes_the_build_failed_window(tmp_path, monkeypatch):
    from workflow.chart_creator import ChartCreator
    from tests.test_chart_creator_engine import (_EngineRunner, _EngineSettings,
                                                 _MockFileManager)
    fm = _MockFileManager(tmp_path / "PrintFab")
    creator = ChartCreator(_EngineRunner(), fm, _EngineSettings())
    work = fm.cwd_for_chart(cal_target=False)
    stem = fm.chart_stem(cal_target=False)
    _rgb_ti1(tmp_path).replace(work / f"{stem}.ti1")
    cal = _cal(tmp_path, CMYK_CAL, "cmyk.cal")
    monkeypatch.setattr(creator, "_engine_kwargs", lambda p: {
        "instrument": "CR30", "paper": "A4", "dpi": 72, "seed": 1,
        "cal_path": str(cal), "apply_cal": True})
    lines: list[str] = []
    from workflow.chart_creator import ChartParams
    creator._run_engine(ChartParams(instrument="CR30", paper="A4"), work,
                        lines.append)
    failure = creator.primary_failure()
    assert failure is not None, "the refusal reached the log only"
    tool, key, text = failure
    assert (tool, key) == ("engine", "cal_colorspace_mismatch")
    assert "made for a CMYK chart" in text and "Device Type" in text
    assert any("[ERROR] ChromIQ layout engine:" in ln for ln in lines)


def test_printtargs_own_refusal_gets_the_same_words(tmp_path):
    from workflow.chart_creator import ChartCreator
    from tests.test_chart_creator_engine import (_EngineRunner, _EngineSettings,
                                                 _MockFileManager)
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    creator._matched_errors, creator._raw_errors = [], []
    creator._scan_line("printtarg", "printtarg: Error - Calibration colorspace "
                                    "CMYK doesn't match .ti1 iRGB")
    tool, key, text = creator.primary_failure()
    assert key == "cal_colorspace_mismatch"
    assert text == calibration.calibration_mismatch_message("CMYK", "iRGB")


def test_the_window_has_a_title_for_an_engine_failure():
    import inspect
    from ui.tabs import tab_chart
    src = inspect.getsource(tab_chart.TabChart)
    assert 'if tool == "engine"' in src


def test_every_catalogue_translates_the_message():
    import json
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    key = calibration.calibration_mismatch_message.__code__.co_consts
    english = next(c for c in key if isinstance(c, str)
                   and c.startswith("The calibration file was made for a"))
    for p in sorted(root.glob("*.json")):
        cat = json.loads(p.read_text(encoding="utf-8"))
        assert english in cat, f"{p.name} has no translation"
        assert "{cal_space}" in cat[english] and "{chart_space}" in cat[english]


def test_apply_to_target_refuses_other_inks_on_its_own(tmp_path):
    """The -K apply step guards itself too, for any caller but build_chart."""
    from workflow.layout_engine import ti1_reader
    target = ti1_reader.read_ti1(_rgb_ti1(tmp_path))
    cal = calibration.read_cal(_cal(tmp_path, CMYK_CAL, "cmyk.cal"))
    with pytest.raises(calibration.CalibrationMismatch):
        calibration.apply_to_target(target, cal)


def test_the_same_number_of_channels_is_not_the_same_inks(tmp_path):
    """An RGB calibration on a CMY chart: three channels each, and printtarg
    refuses it ("Calibration colorspace RGB doesn't match .ti1 CMY",
    measured). Counting channels, the old test, let it through."""
    ti1 = _ti1(tmp_path / "cmy.ti1", "CMY", ["CMY_C", "CMY_M", "CMY_Y"],
               [(0, 0, 0), (50, 50, 50), (100, 100, 100)])
    cal = _cal(tmp_path, RGB_CAL, "rgb.cal")
    with pytest.raises(calibration.CalibrationMismatch):
        chart.build_chart(ti1, tmp_path / "out", instrument="i1", paper="A4",
                          seed=1, dpi=72, cal_path=cal, apply_cal=True)
