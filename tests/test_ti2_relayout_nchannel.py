"""N-channel TI1 writer + editor round-trip (#72 Tier A).

Covers the single-table engine-format writer (``write_ti1_nchannel``), the
generalised :func:`ti2_relayout.write_ti1` dispatch (RGB stays on the 3-table
emitter byte-for-byte — locked separately in test_ti1_emitter_golden.py), the
naive D50 XYZ fallback, and the full golden loop the issue's testing section
asks for: N-channel ``.ti1`` → engine ``.ti2`` → ``ChartSpec.from_ti2`` →
re-save → byte-stable.

Pure Python — no Argyll binaries needed (the engine lays out and writes the
.ti2 itself). The canonical COLOR_REP strings/fields below were derived from
real ``targen -d…`` runs (ArgyllCMS 3.5.0), per the issue's hard problem 10.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import workflow.ti2_relayout as R
from workflow.layout_engine import chart as eng_chart
from workflow.layout_engine import ti1_reader

_CREATED_RE = re.compile(r'^CREATED ".*"$', flags=re.MULTILINE)


def _mask(text: str) -> str:
    return _CREATED_RE.sub('CREATED "<masked>"', text)


# Canonical (COLOR_REP, dev_fields) pairs, from real targen 3.5.0 output.
CMYK_FIELDS = ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
CMYKOG_FIELDS = ["CMYKOG_C", "CMYKOG_M", "CMYKOG_Y",
                 "CMYKOG_K", "CMYKOG_O", "CMYKOG_G"]

CMYK_ROWS = [
    ((0.0, 0.0, 0.0, 0.0), None),                 # paper white
    ((100.0, 100.0, 100.0, 100.0), None),         # 400% black (writer must not judge)
    ((0.0, 0.0, 0.0, 100.0), None),               # K only
    ((100.0, 0.0, 0.0, 0.0), (20.0, 25.0, 55.0)),  # C with explicit XYZ
    ((12.3456, 65.4321, 33.3333, 5.5), None),
]

CMYKOG_ROWS = [
    ((0.0,) * 6, None),
    ((0.0, 0.0, 0.0, 100.0, 0.0, 0.0), None),
    ((10.0, 20.0, 30.0, 40.0, 50.0, 60.0), None),
    ((100.0, 0.0, 0.0, 0.0, 100.0, 0.0), (30.0, 35.0, 20.0)),
]


def _cmyk_spec(patches=None) -> R.ChartSpec:
    """A minimal CMYK ChartSpec (bypasses ChartSpec.new, still RGB-only)."""
    return R.ChartSpec(
        patches=patches or [], dev_fields=list(CMYK_FIELDS), has_xyz=True,
        color_rep="CMYK", white_point=None,
        instrument_flag="i1", paper_flag="A4", paper_mm=(210.0, 297.0),
    )


# --- write_ti1_nchannel ------------------------------------------------------


def test_nchannel_writer_roundtrips_through_engine_reader(tmp_path):
    out = R.write_ti1_nchannel("CMYK", CMYK_FIELDS, CMYK_ROWS, tmp_path / "c.ti1")
    tgt = ti1_reader.read_ti1(out)
    assert tgt.color_rep == "CMYK"
    assert tgt.device_fields == CMYK_FIELDS
    assert len(tgt.patches) == len(CMYK_ROWS)
    for (dev_in, _), (dev_out, _) in zip(CMYK_ROWS, tgt.patches):
        assert dev_out == pytest.approx(dev_in, abs=1e-4)


def test_nchannel_writer_cmykog_six_channels(tmp_path):
    out = R.write_ti1_nchannel(
        "CMYKOG", CMYKOG_FIELDS, CMYKOG_ROWS, tmp_path / "og.ti1")
    tgt = ti1_reader.read_ti1(out)
    assert tgt.color_rep == "CMYKOG"
    assert tgt.device_fields == CMYKOG_FIELDS
    assert tgt.n_channels == 6
    assert tgt.patches[2][0] == pytest.approx(
        (10.0, 20.0, 30.0, 40.0, 50.0, 60.0), abs=1e-4)


def test_nchannel_writer_xyz_fallback_and_passthrough(tmp_path):
    out = R.write_ti1_nchannel("CMYK", CMYK_FIELDS, CMYK_ROWS, tmp_path / "c.ti1")
    tgt = ti1_reader.read_ti1(out)
    xyz = [p[1] for p in tgt.patches]
    # Explicit XYZ passes through untouched.
    assert xyz[3] == pytest.approx((20.0, 25.0, 55.0), abs=1e-4)
    # Naive fallback: paper white lands near the D50 white point…
    assert xyz[0] == pytest.approx((96.42, 100.0, 82.49), rel=0.02)
    # …and even 400% black is never (0,0,0) — the 1% flare keeps chartread's
    # strip-ID and the engine's media-patch pick on solid ground (HP 12).
    assert all(v > 0.0 for v in xyz[1])
    assert xyz[1][1] < 2.5  # but it is still nearly black
    # Media-patch pick works off the fallback values: brightest = paper white.
    assert tgt.media_patch()[0] == pytest.approx((0.0, 0.0, 0.0, 0.0))


def test_nchannel_writer_stamps_ink_limit(tmp_path):
    out = R.write_ti1_nchannel(
        "CMYK", CMYK_FIELDS, CMYK_ROWS, tmp_path / "c.ti1", ink_limit=300.0)
    assert 'TOTAL_INK_LIMIT "300.0"' in out.read_text(encoding="utf-8")


def test_ink_limit_rides_ti1_to_ti2_to_spec(tmp_path):
    # The full #72 chain: .ti1 TOTAL_INK_LIMIT → engine .ti2 → ChartSpec →
    # re-saved .ti1 (exactly what printtarg does on its own path).
    ti1 = R.write_ti1_nchannel("CMYK", CMYK_FIELDS, CMYK_ROWS,
                               tmp_path / "c.ti1", ink_limit=280.0)
    assert ti1_reader.read_ti1(ti1).ink_limit == 280.0
    res = eng_chart.build_ti2_from_ti1(ti1, tmp_path / "c.ti2",
                                       seed=1, randomize=False)
    assert 'TOTAL_INK_LIMIT "280.0"' in res.ti2_path.read_text(encoding="utf-8")
    spec = R.ChartSpec.from_ti2(res.ti2_path)
    assert spec.ink_limit == 280.0
    resave = R.write_ti1(spec, [p.dev for p in spec.patches],
                         tmp_path / "resave.ti1")
    assert 'TOTAL_INK_LIMIT "280.0"' in resave.read_text(encoding="utf-8")
    # RGB charts record no limit.
    assert R.ChartSpec.new("i1", "A4").ink_limit is None


def test_nchannel_writer_rejects_bad_shape(tmp_path):
    with pytest.raises(ValueError, match="length mismatch"):
        R.write_ti1_nchannel(
            "CMYK", CMYK_FIELDS, [((1.0, 2.0, 3.0), None)], tmp_path / "b.ti1")
    with pytest.raises(ValueError, match="no patches"):
        R.write_ti1_nchannel("CMYK", CMYK_FIELDS, [], tmp_path / "e.ti1")


def test_nchannel_writer_byte_stable(tmp_path):
    a = R.write_ti1_nchannel("CMYK", CMYK_FIELDS, CMYK_ROWS, tmp_path / "a.ti1")
    b = R.write_ti1_nchannel("CMYK", CMYK_FIELDS, CMYK_ROWS, tmp_path / "b.ti1")
    assert _mask(a.read_text(encoding="utf-8")) == _mask(b.read_text(encoding="utf-8"))


# --- generalised write_ti1 dispatch ------------------------------------------


def test_write_ti1_rgb_still_three_tables(tmp_path):
    spec = R.ChartSpec.new("i1", "A4")
    out = R.write_ti1(spec, [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)],
                      tmp_path / "rgb.ti1")
    text = out.read_text(encoding="utf-8")
    assert text.count("CTI1") == 3          # patch list + extremes + combos
    assert 'COLOR_REP "iRGB"' in text


def test_write_ti1_cmyk_routes_to_single_table(tmp_path):
    spec = _cmyk_spec(patches=[
        R.Patch("1", "A1", (100.0, 0.0, 0.0, 0.0), (20.0, 25.0, 55.0)),
    ])
    dev_values = [(100.0, 0.0, 0.0, 0.0), (5.0, 6.0, 7.0, 8.0)]
    out = R.write_ti1(spec, dev_values, tmp_path / "c.ti1")
    text = out.read_text(encoding="utf-8")
    assert text.count("CTI1") == 1
    tgt = ti1_reader.read_ti1(out)
    assert tgt.color_rep == "CMYK"
    # Patch kept from spec: recorded XYZ preserved; new patch: naive fallback.
    assert tgt.patches[0][1] == pytest.approx((20.0, 25.0, 55.0), abs=1e-4)
    assert tgt.patches[1][1] != (0.0, 0.0, 0.0)


def test_regenerate_hard_fails_on_non_rgb(tmp_path):
    spec = _cmyk_spec()
    with pytest.raises(RuntimeError, match="RGB charts only"):
        R.regenerate(spec, [(0.0, 0.0, 0.0, 0.0)], tmp_path, tmp_path)


# --- the issue's golden loop: .ti1 -> engine .ti2 -> editor -> re-save -------


@pytest.mark.parametrize("color_rep,fields,rows", [
    ("CMYK", CMYK_FIELDS, CMYK_ROWS),
    ("CMYKOG", CMYKOG_FIELDS, CMYKOG_ROWS),
])
def test_engine_editor_roundtrip_byte_stable(tmp_path, color_rep, fields, rows):
    ti1 = R.write_ti1_nchannel(color_rep, fields, rows, tmp_path / "chart.ti1")
    res = eng_chart.build_ti2_from_ti1(
        ti1, tmp_path / "chart.ti2", instrument="i1", paper="A4",
        seed=42, randomize=False)
    assert res.color_rep == color_rep

    spec = R.ChartSpec.from_ti2(res.ti2_path)
    assert spec.color_rep == color_rep
    assert spec.dev_fields == fields
    assert spec.n_channels == len(fields)
    # Engine adds padding patches; every original device tuple must be present.
    devs = {tuple(round(v, 4) for v in p.dev) for p in spec.patches}
    for dev, _ in rows:
        assert tuple(round(v, 4) for v in dev) in devs

    # Editor re-save (the _engine_grid_ti1 path) is byte-stable: two writes of
    # the same edited program differ only in CREATED.
    program = [p.dev for p in spec.patches]
    a = R.write_ti1(spec, program, tmp_path / "resave_a.ti1")
    b = R.write_ti1(spec, program, tmp_path / "resave_b.ti1")
    assert _mask(a.read_text(encoding="utf-8")) == _mask(b.read_text(encoding="utf-8"))
    # And the re-saved file still reads back with identical patches + XYZ.
    tgt = ti1_reader.read_ti1(a)
    assert [p[0] for p in tgt.patches] == [
        pytest.approx(p.dev, abs=1e-4) for p in spec.patches]


# --- color_rep_for_inks + ChartSpec.new derivation (#72 HP 10) ----------------
# Expected strings below are golden values from real `targen -d… [-D…]` runs
# (ArgyllCMS 3.5.0) — never derived by hand.


@pytest.mark.parametrize("codes,rep,first,last", [
    (["c", "m", "y", "k"], "CMYK", "CMYK_C", "CMYK_K"),                    # -d4
    (["c", "m", "y"], "CMY", "CMY_C", "CMY_Y"),                            # -d5
    (["c", "m", "y", "k", "lc", "lm"], "CMYKcm", "CMYKcm_C", "CMYKcm_m"),  # -d6
    (["c", "m", "y", "k", "lc", "lm", "lk"], "CMYKcmk",
     "CMYKcmk_C", "CMYKcmk_k"),                                            # -d7
    (["c", "m", "y", "k", "r", "b"], "CMYKRB", "CMYKRB_C", "CMYKRB_B"),    # -d8
    (["c", "m", "y", "k", "o", "g"], "CMYKOG", "CMYKOG_C", "CMYKOG_G"),    # -d9
    (["c", "m", "y", "k", "r", "g", "b"], "CMYKRGB",
     "CMYKRGB_C", "CMYKRGB_B"),                                            # -d10
    (["c", "m", "y", "k", "o", "g", "v"], "CMYKOGV",
     "CMYKOGV_C", "CMYKOGV_V"),                                            # -d11
    (["c", "m", "y", "k", "o", "g", "b"], "CMYKOGB",
     "CMYKOGB_C", "CMYKOGB_B"),                                            # -d12
    (["c", "m", "y", "k", "lc", "lm", "lk", "llk"], "CMYKcmk1k",
     "CMYKcmk1k_C", "CMYKcmk1k_1k"),                                       # -d13
    (["c", "m", "y", "k", "o", "g", "lc", "lm"], "CMYKOGcm",
     "CMYKOGcm_C", "CMYKOGcm_m"),                                          # -d14
    (["c", "m", "y", "k", "lc", "lm", "mc", "mm"], "CMYKcm2c2m",
     "CMYKcm2c2m_C", "CMYKcm2c2m_2m"),                                     # -d15
])
def test_color_rep_matches_targen(codes, rep, first, last):
    got_rep, got_fields = R.color_rep_for_inks(codes)
    assert got_rep == rep
    assert got_fields[0] == first and got_fields[-1] == last
    assert len(got_fields) == len(codes)


def test_color_rep_canonicalises_order_like_targen():
    # targen -d4 -D7 -D5 stamps CMYKOG (bit order), not CMYKGO — verified live.
    assert R.color_rep_for_inks(["g", "o", "c", "m", "y", "k"])[0] == "CMYKOG"
    # -d4 -D19 -D11 → CMYKc1k (light cyan before light-light black).
    assert R.color_rep_for_inks(["llk", "lc", "c", "m", "y", "k"])[0] == "CMYKc1k"


def test_color_rep_rejects_unknown_code():
    with pytest.raises(ValueError, match="unknown ink code"):
        R.color_rep_for_inks(["c", "m", "y", "k", "q"])


def test_chartspec_new_rgb_unchanged():
    # Regression: the default call is byte-for-byte the pre-#72 RGB spec.
    spec = R.ChartSpec.new("i1", "A4")
    assert spec.dev_fields == ["RGB_R", "RGB_G", "RGB_B"]
    assert spec.color_rep == "iRGB"
    assert spec.paper_mm == (210.0, 297.0)
    assert R.ChartSpec.new("i1", "A4", device_type="3").color_rep == "iRGB"


def test_chartspec_new_cmyk_and_extras():
    spec = R.ChartSpec.new("i1", "A4", device_type="4")
    assert (spec.color_rep, spec.dev_fields) == ("CMYK", CMYK_FIELDS)
    og = R.ChartSpec.new("i1", "A4", device_type="4", extra_inks=("o", "g"))
    assert (og.color_rep, og.dev_fields) == ("CMYKOG", CMYKOG_FIELDS)
    # Extras already in the base set are not duplicated.
    dup = R.ChartSpec.new("i1", "A4", device_type="9", extra_inks=("o",))
    assert dup.color_rep == "CMYKOG"
    assert og.n_channels == dup.n_channels == 6


def test_chartspec_new_gray():
    k = R.ChartSpec.new("i1", "A4", device_type="0")
    assert (k.color_rep, k.dev_fields) == ("K", ["GRAY_K"])
    w = R.ChartSpec.new("i1", "A4", device_type="1")
    assert (w.color_rep, w.dev_fields) == ("W", ["GRAY_W"])


# --- the randomisation gate on N-channel charts (#72 R6) ----------------------
# Pre-#72 the RGB-only strip parse returned no strips for a CMYK .ti2 and the
# gate reported "trivially safe" — a silent bypass. Now CMYK charts are
# analysed for real and unparseable input is reported UNSAFE.

_TI2_HEAD_CMYK = """CTI2
DESCRIPTOR "t"
COLOR_REP "CMYK"
CHART_ID "42"
NUMBER_OF_FIELDS 9
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
"""


def _make_cmyk_ti2(tmp_path, strips: dict) -> Path:
    rows, sid = [], 0
    for letter, seq in strips.items():
        for i, dev in enumerate(seq, start=1):
            sid += 1
            vals = " ".join(f"{v:.1f}" for v in dev)
            rows.append(f'{sid} "{letter}{i}" {vals} 0 0 0')
    p = tmp_path / "chart.ti2"
    p.write_text(_TI2_HEAD_CMYK + f"NUMBER_OF_SETS {sid}\nBEGIN_DATA\n"
                 + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    return p


def test_gate_flags_identical_cmyk_strips_unsafe(tmp_path):
    seq = [(100, 0, 0, 0), (0, 100, 0, 0), (0, 0, 100, 0)]
    rep = R.analyze_randomisation(
        _make_cmyk_ti2(tmp_path, {"A": seq, "B": list(seq)}))
    assert rep.safe is False           # the old silent bypass returned True
    assert rep.n_strips == 2


def test_gate_passes_well_mixed_cmyk(tmp_path):
    strips = {
        "A": [(100, 0, 0, 0), (0, 100, 0, 0), (0, 0, 0, 100)],
        "B": [(0, 0, 100, 0), (50, 50, 0, 0), (100, 100, 0, 0)],
        "C": [(20, 40, 60, 0), (0, 0, 0, 50), (80, 10, 30, 5)],
    }
    rep = R.analyze_randomisation(_make_cmyk_ti2(tmp_path, strips))
    assert rep.safe is True
    assert rep.n_strips == 3


def test_gate_reports_unparseable_as_unsafe(tmp_path):
    missing = R.analyze_randomisation(tmp_path / "nope.ti2")
    assert missing.safe is False
    assert "could not be analysed" in missing.reason
    garbage = tmp_path / "garbage.ti2"
    garbage.write_text("CTI2\nDESCRIPTOR \"t\"\n", encoding="utf-8")   # no format/data blocks
    rep = R.analyze_randomisation(garbage)
    assert rep.safe is False
