"""-K calibrates what is PRINTED, never the ``.ti2`` (printtarg semantics).

ArgyllCMS 3.5.0, ``target/printtarg.c``:

* ``tiff_setcolor`` / ``ps_setcolor``: ``if (cal != NULL) cal->interp(cal,
  cdev, c->dev);`` and the page is drawn from that local ``cdev``;
* the ``.ti2`` rows: ``ary[2 + j].d = 100.0 * cols[i].dev[j];`` -- the
  uncalibrated value -- followed by ``cal->write_cgats(cal, ocg)``.

chartread copies those device values into the ``.ti3`` and colprof profiles
against them, so the profile describes the CALIBRATED device and ``applycal``
folds the curves in once. ChromIQ's own layout engine used to write the
calibrated values into the ``.ti2`` as well, so its profile described the raw
printer and ``applycal`` (Build Profile's calibrated.icc) calibrated it a second
time. Measured with a synthetic printer: report folder AG_K_double_cal,
2026-10-02.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap

import numpy as np
import pytest
import tifffile

from workflow.layout_engine import calibration, chart

TI1_RGB = textwrap.dedent("""\
    CTI1

    DESCRIPTOR "Argyll Calibration Target chart information 1"
    COLOR_REP "iRGB"

    NUMBER_OF_FIELDS 7
    BEGIN_DATA_FORMAT
    SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT

    NUMBER_OF_SETS 6
    BEGIN_DATA
    1 100.0 100.0 100.0 95.1 100.0 108.8
    2 50.0 50.0 50.0 20.0 21.0 23.0
    3 25.0 75.0 40.0 20.0 30.0 15.0
    4 80.0 10.0 60.0 30.0 20.0 25.0
    5 0.0 0.0 0.0 1.0 1.0 1.0
    6 60.0 30.0 90.0 25.0 20.0 60.0
    END_DATA
    """)

TI1_CMYK = textwrap.dedent("""\
    CTI1

    DESCRIPTOR "Argyll Calibration Target chart information 1"
    COLOR_REP "CMYK"

    NUMBER_OF_FIELDS 8
    BEGIN_DATA_FORMAT
    SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z
    END_DATA_FORMAT

    NUMBER_OF_SETS 5
    BEGIN_DATA
    1 0.0 0.0 0.0 0.0 95.1 100.0 108.8
    2 50.0 20.0 70.0 10.0 20.0 25.0 10.0
    3 30.0 60.0 10.0 40.0 10.0 8.0 9.0
    4 80.0 80.0 0.0 0.0 5.0 4.0 20.0
    5 0.0 40.0 40.0 90.0 3.0 3.0 3.0
    END_DATA
    """)


def _cal_text(rep: str, prefix: str, fields: list[str], curves) -> str:
    x = np.linspace(0.0, 1.0, 256)
    rows = "\n".join(" ".join(f"{c:.6f}" for c in [v] + [f(v) for f in curves])
                     for v in x)
    return (f'CAL\n\nDESCRIPTOR "Argyll Device Calibration Curves"\n'
            f'ORIGINATOR "test"\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "{rep}"\n\n'
            f"NUMBER_OF_FIELDS {len(fields) + 1}\nBEGIN_DATA_FORMAT\n"
            f"{prefix}_I {' '.join(fields)}\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS 256\nBEGIN_DATA\n{rows}\nEND_DATA\n")


RGB_CAL = _cal_text("iRGB", "RGB", ["RGB_R", "RGB_G", "RGB_B"],
                    [lambda v: v ** 1.6, lambda v: v ** 0.7,
                     lambda v: 0.5 * (v + v ** 2.5)])
CMYK_CAL = _cal_text("CMYK", "CMYK", ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"],
                     [lambda v: 0.8 * v ** 1.3, lambda v: v ** 0.7,
                      lambda v: 0.9 * v, lambda v: v ** 1.5])


def _device_rows(path, prefix):
    """{SAMPLE_ID: (loc, device values 0..100)} from a .ti1/.ti2's first table."""
    text = path.read_text(encoding="utf-8", errors="replace")
    first = re.split(r"\n\s*CAL\s*\n", text)[0]
    fmt = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", first, re.S).group(1).split()
    data = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", first, re.S).group(1)
    di = [i for i, f in enumerate(fmt) if f.startswith(prefix + "_")]
    li = fmt.index("SAMPLE_LOC") if "SAMPLE_LOC" in fmt else None
    out = {}
    for ln in data.splitlines():
        t = re.findall(r'"[^"]*"|\S+', ln)
        if t:
            loc = t[li].strip('"') if li is not None else None
            out[t[0]] = (loc, tuple(float(t[i]) for i in di))
    return out


def _build(tmp_path, ti1_text, cal_text, apply_cal):
    ti1 = tmp_path / "t.ti1"
    ti1.write_text(ti1_text, encoding="utf-8")
    cal = tmp_path / "c.cal"
    cal.write_text(cal_text, encoding="utf-8")
    res = chart.build_chart(ti1, tmp_path / "t", instrument="i1", paper="A4",
                            seed=1, dpi=72, cal_path=cal, apply_cal=apply_cal)
    return ti1, cal, res


def _centre_pixels(res, tmp_path):
    """{loc: pixel (0..1 per channel)} at each patch's centre."""
    rects = json.loads((tmp_path / "t.strips.json").read_text(encoding="utf-8"))["patches"]
    pages = [tifffile.imread(p) for p in res.tiff_paths]
    out = {}
    for r in rects:
        im = pages[r.get("page", 0)]
        px = im[r["y"] + r["h"] // 2, r["x"] + r["w"] // 2]
        mx = 65535.0 if im.dtype == np.uint16 else 255.0
        out[r["loc"]] = np.asarray(px, dtype=float) / mx
    return out


@pytest.mark.parametrize("ti1_text,cal_text,prefix", [
    (TI1_RGB, RGB_CAL, "RGB"), (TI1_CMYK, CMYK_CAL, "CMYK")],
    ids=["rgb", "cmyk"])
def test_k_keeps_the_ti1_values_in_the_ti2(tmp_path, ti1_text, cal_text, prefix):
    ti1, _cal, res = _build(tmp_path, ti1_text, cal_text, apply_cal=True)
    want = _device_rows(ti1, prefix)
    got = _device_rows(res.ti2_path, prefix)
    for sid, (_loc, dev) in want.items():
        assert got[sid][1] == pytest.approx(dev, abs=1e-3), (
            f"patch {sid}: the .ti2 carries {got[sid][1]}, the .ti1 {dev}. "
            "printtarg -K writes the UNcalibrated value (cols[i].dev); a "
            "calibrated one makes applycal calibrate the profile twice.")
    text = res.ti2_path.read_text(encoding="utf-8")
    assert f"{prefix}_I" in text.split("END_DATA", 1)[1], "-K must embed the CAL"


@pytest.mark.parametrize("ti1_text,cal_text,prefix", [
    (TI1_RGB, RGB_CAL, "RGB"), (TI1_CMYK, CMYK_CAL, "CMYK")],
    ids=["rgb", "cmyk"])
def test_k_prints_the_calibrated_colour(tmp_path, ti1_text, cal_text, prefix):
    ti1, cal_path, res = _build(tmp_path, ti1_text, cal_text, apply_cal=True)
    cal = calibration.read_cal(cal_path)
    rows = _device_rows(res.ti2_path, prefix)
    px = _centre_pixels(res, tmp_path)
    for sid, (loc, dev) in _device_rows(ti1, prefix).items():
        want = np.array(cal.apply(dev)) / 100.0
        got = px[rows[sid][0]][:len(dev)]
        assert np.abs(got - want).max() <= 1.5 / 255, (sid, got, want)


def test_i_prints_and_records_the_uncalibrated_colour(tmp_path):
    ti1, _cal, res = _build(tmp_path, TI1_RGB, RGB_CAL, apply_cal=False)
    rows = _device_rows(res.ti2_path, "RGB")
    px = _centre_pixels(res, tmp_path)
    for sid, (_loc, dev) in _device_rows(ti1, "RGB").items():
        assert rows[sid][1] == pytest.approx(dev, abs=1e-3)
        got = px[rows[sid][0]][:3]
        assert np.abs(got - np.array(dev) / 100.0).max() <= 1.5 / 255


def _argyll(tool):
    import pathlib
    return shutil.which(tool) or next(
        (str(p) for p in (pathlib.Path("/opt/homebrew/bin") / tool,
                          pathlib.Path("/Applications/Argyll/bin") / tool)
         if p.exists()), None)


@pytest.mark.skipif(_argyll("printtarg") is None or _argyll("targen") is None,
                    reason="ArgyllCMS not installed")
@pytest.mark.parametrize("cal_text,prefix,targen_d", [
    (RGB_CAL, "RGB", "-d2"), (CMYK_CAL, "CMYK", "-d4")], ids=["rgb", "cmyk"])
def test_k_ti2_matches_printtarg(tmp_path, cal_text, prefix, targen_d):
    """The engine's -K .ti2 device values are printtarg -K's, patch for patch,
    built from the same targen .ti1 and the same .cal."""
    pt = tmp_path / "pt"
    pt.mkdir()
    r = subprocess.run([_argyll("targen"), "-v0", targen_d, "-f24", "t"], cwd=pt,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    (pt / "c.cal").write_text(cal_text, encoding="utf-8")
    r = subprocess.run([_argyll("printtarg"), "-ii1", "-pA4", "-K", "c.cal", "t"],
                       cwd=pt, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    eng = tmp_path / "eng"
    eng.mkdir()
    _ti1, _cal, res = _build(eng, (pt / "t.ti1").read_text(encoding="utf-8"),
                             cal_text, apply_cal=True)
    a = _device_rows(pt / "t.ti2", prefix)
    b = _device_rows(res.ti2_path, prefix)
    # printtarg numbers its strip padding 0 and the engine numbers it on from
    # the last patch, so compare the .ti1's own patches.
    ids = _device_rows(pt / "t.ti1", prefix)
    assert ids
    for sid in ids:
        assert b[sid][1] == pytest.approx(a[sid][1], abs=1e-3), sid
