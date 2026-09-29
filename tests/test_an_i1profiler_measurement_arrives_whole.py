"""What a user testing the profile-build import met on 2026-09-11, in three parts.

She measured a ChromIQ chart on an i1iO through i1Profiler and brought the
readings back. Three separate things were wrong, and each has its own section
below. The fixtures are built from the HEADERS of her two real exports (RGB +
spectral with no XYZ; RGB + XYZ on the 0..1 scale + spectral) — the files
themselves are 1.7 MB each and do not belong in the tree, so the shape is
reproduced and the counts are shrunk.

**1. A spectral measurement is a measurement.** Her working export carries RGB
and a reflectance curve per patch and no CIE columns at all. ``txt2ti3``
converts it without a murmur and ``colprof`` builds from it ("No CIE data found,
switching to spectral with standard observer & D50", colprof.c ~L1089). ChromIQ
alone refused it, with "No XYZ or Lab columns in the measurement."

**2. txt2ti3 scales the device and spectral columns and passes CIE straight
through.** Her second export carries XYZ on i1Profiler's 0..1 reflectance-factor
scale, so the converted ``.ti3`` came out a hundredfold small — paper white
``XYZ 0.872540 0.885770 0.869230`` where Argyll's own ``spec2cie`` on the same
file's spectral says ``87.25821 88.57786 86.92455``. Measured on the real files:
``colprof`` then records the media white as **L\\* 8.0** instead of **L\\* 95.4**,
and says nothing.

**3. Two layout engines pad, and only one was known about.** Her chart: targen
asked for 4,000, the ``.ti2`` holds 4,014, the last 14 rows paper white — the
ChromIQ layout engine filling out the last strip, exactly as printtarg does. The
i1Profiler hand-off ChromIQ itself writes carries the 4,000 designed patches
(``chart_exports.write_sidecars`` reads the ``.ti1``), so a complete measurement
of it holds 4,000 readings and was greeted with "The chart has 4014 patches and
this file holds 4000 readings, so part of the chart was not measured."
``measurement_state`` already discounted printtarg's fill-up (``SAMPLE_ID`` 0,
report 16) and its own docstring claimed ChromIQ's engine "has no padding".
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_import import assess                      # noqa: E402
from workflow.measurement_state import expected_patches             # noqa: E402
from workflow.reference_convert import repair_converted_cie         # noqa: E402
from workflow.ti3_analysis import Ti3ParseError, parse_ti3          # noqa: E402

# Her export's own bands, trimmed to five so the fixture stays readable.
_BANDS = (380.0, 420.0)
_N_BANDS = 5

# Reflectance percentages on ArgyllCMS's 0..100 scale, as txt2ti3 writes them.
_SPECTRA = {
    "white": [88.0, 89.0, 90.0, 90.5, 91.0],
    "grey":  [22.0, 22.5, 23.0, 23.2, 23.4],
    "black": [2.0, 2.1, 2.2, 2.25, 2.3],
}


def _ti3(rows, *, with_xyz: str | None = None) -> str:
    """A converted ``.ti3``. *with_xyz* is None (spectral only, what txt2ti3
    writes from a spectral export), "argyll" (0..100) or "unscaled" (0..1)."""
    spec = " ".join(f"SPEC_{int(_BANDS[0] + i * 10)}" for i in range(_N_BANDS))
    cie = "XYZ_X XYZ_Y XYZ_Z " if with_xyz else ""
    fields = f"SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B {cie}{spec}"
    body = []
    for i, (loc, dev, kind) in enumerate(rows, start=1):
        s = _SPECTRA[kind]
        cols = f'{i} "{loc}" {dev} {dev} {dev} '
        if with_xyz:
            # A rough XYZ for the patch; only its SCALE is under test.
            f = 0.01 if with_xyz == "unscaled" else 1.0
            cols += " ".join(f"{s[2] * f * k:.6f}" for k in (0.95, 1.0, 0.82)) + " "
        cols += " ".join(f"{v:.4f}" for v in s)
        body.append(cols)
    return (
        'CTI3   \n\nDESCRIPTOR "x"\nDEVICE_CLASS "OUTPUT"\n'
        'COLOR_REP "iRGB_XYZ"\n'
        f'SPECTRAL_BANDS "{_N_BANDS}"\n'
        f'SPECTRAL_START_NM "{int(_BANDS[0])}"\n'
        f'SPECTRAL_END_NM "{int(_BANDS[1])}"\n\n'
        f"NUMBER_OF_FIELDS {len(fields.split())}\n"
        f"BEGIN_DATA_FORMAT\n{fields}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(body)}\nBEGIN_DATA\n" + "\n".join(body)
        + "\nEND_DATA\n")


_ROWS = [("A1", "100.0000", "white"), ("A2", "50.0000", "grey"),
         ("A3", "0.0000", "black")]


# ---------------------------------------------------------------------------
# 1 · a spectral measurement is a measurement
# ---------------------------------------------------------------------------

def test_a_spectral_only_measurement_is_read(tmp_path):
    """The file she said works with txt2ti3. It must import."""
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(_ROWS), encoding="utf-8")

    data = parse_ti3(p)                     # must not raise

    assert data.n_patches == 3
    assert data.has_spectral
    # White is the lightest patch and lands where a ~90 % reflector should:
    # Y well above the grey's, on ArgyllCMS's 0..100 scale.
    assert 80.0 < data.xyz[0][1] < 100.0, data.xyz[0]
    assert data.xyz[0][1] > data.xyz[1][1] > data.xyz[2][1]


def test_a_file_with_no_colour_at_all_is_still_refused(tmp_path):
    """The fallback must not swallow a genuinely colourless file."""
    p = tmp_path / "m.ti3"
    p.write_text(
        'CTI3   \n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100\nEND_DATA\n",
        encoding="utf-8")
    with pytest.raises(Ti3ParseError):
        parse_ti3(p)


# ---------------------------------------------------------------------------
# 2 · the CIE columns txt2ti3 leaves wrong, or leaves out
# ---------------------------------------------------------------------------

_ARGYLL = Path("/Applications/Argyll/bin")
_needs_argyll = pytest.mark.skipif(
    not (_ARGYLL / "spec2cie").is_file(),
    reason="ArgyllCMS is not installed here")


@_needs_argyll
def test_the_conversion_gets_the_xyz_columns_it_claims_to_have(tmp_path):
    """txt2ti3 declares COLOR_REP "iRGB_XYZ" and then writes no XYZ columns."""
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(_ROWS), encoding="utf-8")

    note = repair_converted_cie(p, _ARGYLL)

    assert "spec2cie" in note, note
    data = parse_ti3(p)
    assert "XYZ_X" in data.fields
    assert data.n_patches == 3, "spec2cie lost patches"
    assert 80.0 < data.xyz[0][1] < 100.0, data.xyz[0]
    assert data.has_spectral, "the spectral readings must stay in the file"


def test_with_no_argyllcms_a_spectral_file_is_left_exactly_as_it_is(tmp_path):
    """Writing ChromIQ's own integration into the file would hand colprof worse
    input than it derives for itself. Better to change nothing."""
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(_ROWS), encoding="utf-8")
    before = p.read_text(encoding="utf-8")

    assert repair_converted_cie(p, None) == ""
    assert p.read_text(encoding="utf-8") == before
    assert parse_ti3(p).n_patches == 3      # and it still reads


def test_an_xyz_column_on_the_0_to_1_scale_is_put_right(tmp_path):
    """Her second export: paper white at Y=0.88 where Argyll means Y=88."""
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(_ROWS, with_xyz="unscaled"), encoding="utf-8")
    assert parse_ti3(p).xyz[0][1] < 1.5, "fixture is not on the 0..1 scale"

    note = repair_converted_cie(p, _ARGYLL)

    assert "0..1 scale" in note, note
    assert 80.0 < parse_ti3(p).xyz[0][1] < 100.0


def test_an_xyz_column_already_on_argylls_scale_is_left_alone(tmp_path):
    p = tmp_path / "m.ti3"
    p.write_text(_ti3(_ROWS, with_xyz="argyll"), encoding="utf-8")
    before = p.read_text(encoding="utf-8")

    assert repair_converted_cie(p, _ARGYLL) == ""
    assert p.read_text(encoding="utf-8") == before


def test_a_row_that_does_not_hold_every_column_stops_the_rewrite(tmp_path):
    """The rescale works by column POSITION, so a row that does not hold every
    column must stop it rather than be indexed into. Here the last row is cut
    off short, as a file written by something that died would be, and the whole
    file must come back byte for byte instead of an exception."""
    lines = _ti3(_ROWS, with_xyz="unscaled").splitlines()
    cut = next(i for i, ln in enumerate(lines) if ln.startswith('3 "A3"'))
    lines[cut] = '3 "A3" 0.0000 0.0002'          # four tokens, not eleven
    p = tmp_path / "m.ti3"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    before = p.read_text(encoding="utf-8")

    assert repair_converted_cie(p, _ARGYLL) == ""      # and does not raise
    assert p.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# 3 · the fill-up patches ChromIQ's own layout engine adds
# ---------------------------------------------------------------------------

_TI1 = """CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 4
BEGIN_DATA
1 100 100 100 95.1 100.0 108.8
2 50 50 50 20.0 21.0 17.0
3 0 0 0 0.3 0.3 0.3
4 25 25 25 5.0 5.2 4.3
END_DATA

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
INDEX RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 8
BEGIN_DATA
0 100 100 100 95.1 100.0 108.8
1 0 100 100 50.0 70.0 90.0
2 100 0 100 50.0 30.0 90.0
3 0 0 100 20.0 10.0 90.0
4 100 100 0 70.0 80.0 10.0
5 0 100 0 30.0 60.0 10.0
6 100 0 0 40.0 20.0 2.0
7 0 0 0 0.3 0.3 0.3
END_DATA
"""


def _engine_ti2(tmp_path, *, designed=4, fill_up=2, steps=3,
               originator="ChromIQ layout engine", fill_rgb="100.00000"):
    rows = [f'{i} "L{i}" {v} {v} {v} 20.0 21.0 17.0'
            for i, v in enumerate(["100.00000", "50.00000", "0.00000",
                                   "25.00000"][:designed], start=1)]
    rows += [f'{designed + i} "F{i}" {fill_rgb} {fill_rgb} {fill_rgb} '
             f"95.10649 100.00000 108.84400"
             for i in range(1, fill_up + 1)]
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text(
        f'CTI2   \n\nORIGINATOR "{originator}"\n'
        f'STEPS_IN_PASS "{steps}"\n\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    (tmp_path / "chart.ti1").write_text(_TI1, encoding="utf-8")
    return ti2


def test_the_engines_fill_up_patches_are_not_counted_as_patches(tmp_path):
    """4 designed + 2 fill-up = 6 rows, and the chart has 4 patches."""
    ti2 = _engine_ti2(tmp_path)
    assert expected_patches(ti2) == 4


def test_a_chart_with_no_fill_up_is_unchanged(tmp_path):
    ti2 = _engine_ti2(tmp_path, fill_up=0)
    assert expected_patches(ti2) == 4


def test_a_chart_that_is_not_the_engines_keeps_every_row(tmp_path):
    """A ``.ti1`` sitting beside a printtarg chart must never shrink it."""
    ti2 = _engine_ti2(tmp_path, originator="Argyll printtarg")
    assert expected_patches(ti2) == 6


def test_a_chart_with_no_ti1_beside_it_keeps_every_row(tmp_path):
    """The designed count comes from the run's own ``.ti1``. With no ``.ti1``
    there is nothing to subtract, and guessing is not allowed."""
    ti2 = _engine_ti2(tmp_path)
    (tmp_path / "chart.ti1").unlink()
    assert expected_patches(ti2) == 6


def test_trailing_rows_that_differ_are_not_fill_up(tmp_path):
    """Fill-up is one media colour repeated. Rows that are not identical are
    real patches, whatever the ``.ti1`` says."""
    ti2 = _engine_ti2(tmp_path)
    text = ti2.read_text(encoding="utf-8")
    ti2.write_text(text.replace('6 "F2" 100.00000 100.00000 100.00000',
                                '6 "F2" 100.00000 100.00000 99.00000'),
                   encoding="utf-8")
    assert expected_patches(ti2) == 6


def test_a_surplus_bigger_than_one_strip_is_not_fill_up(tmp_path):
    """Padding completes ONE pass, so it is always smaller than a strip. A
    larger difference means the ``.ti1`` is not this chart's."""
    ti2 = _engine_ti2(tmp_path, fill_up=3, steps=3)
    assert expected_patches(ti2) == 7


def test_a_complete_measurement_of_a_padded_chart_is_not_partial(tmp_path):
    """The sentence she was shown: "part of the chart was not measured"."""
    ti2 = _engine_ti2(tmp_path)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_ti3([("L1", "100.0000", "white"), ("L2", "50.0000", "grey"),
                         ("L3", "0.0000", "black"), ("L4", "25.0000", "black")],
                        with_xyz="argyll"), encoding="utf-8")

    verdict = assess(ti3, ti2)

    assert verdict.ok, verdict.reason
    assert not verdict.partial, (
        f"a complete measurement was filed as partial: "
        f"{verdict.n_measured} of {verdict.n_chart}")
    assert verdict.n_chart == 4


def test_a_genuinely_partial_measurement_is_still_partial(tmp_path):
    ti2 = _engine_ti2(tmp_path)
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text(_ti3([("L1", "100.0000", "white"), ("L2", "50.0000", "grey")],
                        with_xyz="argyll"), encoding="utf-8")

    verdict = assess(ti3, ti2)

    assert verdict.ok and verdict.partial
    assert (verdict.n_measured, verdict.n_chart) == (2, 4)
