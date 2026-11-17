"""D-4b as an option (owner-results round, item 6): "Use the table's stored white tile values
(as i1Profiler does)". Off (the default): the i1Pro 2's own white reference, as by hand, and
nothing changes. On: after each calibration the table's tile is read once at rest (nothing
moves), and the measurement's spectra are scaled per band by stored value / that reading; XYZ
and L*a*b* are computed again from the scaled spectrum. Only bytes 88-231 of the memory block
are read; values that do not look like a white tile are refused truthfully and the session
measures as with the option off. SYNTHETIC tile values only (never a real table's).
"""
from __future__ import annotations

import json
import math
import struct

import pytest

from tests.i1io_table import session_sim as ss
from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read
from workflow.i1io.table import job as J
from workflow.i1io.table import measurement as ms
from workflow.i1io.table import session_table as tbl
from workflow.i1io.table import spot as sp

#: made up: a white tile a little darker than the simulated reading of 88 % at rest
TILE = tuple(round(0.84 + 0.0008 * k, 4) for k in range(36))


@pytest.fixture(autouse=True)
def _a_white_tile_at_rest(monkeypatch):
    """The simulated helper reads 88 % in every band over the table's tile (at rest)."""
    from tests.i1io_table import reader_sim as RS
    orig = RS.spectrum_at
    monkeypatch.setattr(RS, "spectrum_at",
                        lambda x, y: [0.88] * 36 if y < 300 else orig(x, y))


def _job(tmp_path, stored=True, tile=TILE, script=None):
    job, sim, helper, run, p = job_for(tmp_path, script)
    sim.stored_tile = tile
    job.stored_tile_white = stored
    return job, sim, helper, run, p


def _spectra(path):
    text = path.read_text(encoding="utf-8")
    fields = text.split("BEGIN_DATA_FORMAT")[1].split("END_DATA_FORMAT")[0].split()
    body = text.split("BEGIN_DATA\n")[1].split("END_DATA")[0].strip().splitlines()
    rows = {}
    for ln in body:
        parts = ln.split()
        rows[parts[fields.index("SAMPLE_LOC")].strip('"')] = parts
    return fields, rows, text


# ---- the bytes and the check ----------------------------------------------------------------

def test_only_bytes_88_to_231_of_the_memory_block_are_read():
    block = ss._memory_a(TILE)
    got = tbl.stored_tile_values(block)
    assert got == pytest.approx(TILE, abs=1e-6)
    # every byte before 88 can be anything: the values do not change
    other = "00" * 88 + block[176:]
    assert tbl.stored_tile_values(other) == got
    assert tbl.STORED_TILE_FIRST_BYTE == 88 and tbl.STORED_TILE_BANDS == 36
    assert tbl.stored_tile_values(block[:300]) is None
    # the reply keeps nothing of the block but the values
    line_data = block
    rep = tbl.Reply("u8", 0, "", tbl.stored_tile_values(line_data))
    assert rep.data == ""


@pytest.mark.parametrize("stored,reading,why", [
    (None, [88.0] * 36, "stored_white_not_readable"),
    (TILE[:35], [88.0] * 36, "stored_white_not_readable"),
    ((float("nan"),) + TILE[1:], [88.0] * 36, "stored_white_not_a_white_tile"),
    ((-1.2e-12,) * 36, [88.0] * 36, "stored_white_not_a_white_tile"),
    ((0.2,) + TILE[1:], [88.0] * 36, "stored_white_not_a_white_tile"),
    ((1.5,) + TILE[1:], [88.0] * 36, "stored_white_not_a_white_tile"),
    (TILE, None, "stored_white_no_tile_reading"),
    (TILE, [88.0] * 35, "stored_white_no_tile_reading"),
    (TILE, [60.0] * 36, "stored_white_too_far_from_the_reading"),
])
def test_values_that_do_not_validate_are_refused(stored, reading, why):
    assert sp.stored_white_factors(stored, reading) == (None, why)


def test_valid_values_give_one_factor_per_band():
    f, why = sp.stored_white_factors(TILE, [88.0] * 36)
    assert why == "" and len(f) == 36
    assert f[0] == pytest.approx(0.84 / 0.88) and f[-1] == pytest.approx(TILE[-1] / 0.88)
    assert sp.factor_at(f, 385) == pytest.approx((f[0] + f[1]) / 2)
    assert sp.factor_at(f, 300) == f[0] and sp.factor_at(f, 800) == f[-1]


# ---- the job ----------------------------------------------------------------------------------

def test_off_is_todays_behaviour_no_tile_reading_no_scaling(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, stored=False)
    p.drive(job.open())
    readers = job.readers_started
    r = p.drive(job.calibrate())
    assert r.ok and "stored_white" not in r.detail
    assert job.readers_started == readers + 1           # the calibration's reader only
    assert job.white_scale is None


def test_on_scales_the_measurement_and_logs_only_the_range(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    p.drive(job.open())
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert r.ok, (r.reason, r.detail)
    assert r.detail["stored_white"]["used"] is True
    # nothing moved for the tile reading
    assert [ln for ln in sim.received[n:] if ln[1:3] in ("m0", "m1", "m2", "i1", "i0")] == []
    want, _w = sp.stored_white_factors(TILE, job._tile_spectrum)
    assert job.white_scale == pytest.approx(want, abs=1e-6)
    log = "\n".join(job.diag.lines)
    assert "per-band factors from" in log and "stored white tile values" in log
    assert f"{TILE[3]:.4f}" not in log and ss.FAKE_SERIAL not in log
    ready_to_read(job, p, steps=("align",))
    rows = read_page(job, p)
    assert rows and all(x.ok for x in rows)
    m = job.measurement()
    assert m.ok, (m.reason, m.detail)
    out = job.run.i1io_table_measurement(job.stamp)
    from pathlib import Path
    fields, got, text = _spectra(Path(out))
    assert f'KEYWORD "{ms.WHITE_KEYWORD}"' in text
    # each value: the reader's own spectrum times the band's factor, XYZ computed again
    recs = [json.loads(f.read_text(encoding="utf-8")) for f in Path(job.diag.folder).glob("*/*.row.json")]
    assert recs and all(rec["white_scale"] == pytest.approx(list(job.white_scale))
                        for rec in recs)
    raw_file = next(Path(job.diag.folder).glob(f"*/{recs[0]['reader_ti3']}"))
    rf, raw, _t = _spectra(raw_file)
    loc = next(iter(raw))
    for k, f in enumerate(fields):
        if f.startswith("SPEC_"):
            band = sp.STORED_TILE_WL.index(int(float(f[5:])))
            assert float(got[loc][k]) == pytest.approx(
                float(raw[loc][rf.index(f)]) * job.white_scale[band], abs=2e-5)
    y_raw, y_new = float(raw[loc][rf.index("XYZ_Y")]), float(got[loc][fields.index("XYZ_Y")])
    assert y_new != pytest.approx(y_raw, abs=1e-3) and math.isfinite(y_new)


def test_values_that_are_no_white_tile_are_refused_and_the_session_measures_as_off(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, tile=None)       # the simulator's filler bytes
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert r.ok and r.detail["stored_white"] == {"used": False,
                                                "why": "stored_white_not_a_white_tile"}
    assert job.white_scale is None
    assert "the i1Pro 2's own" in "\n".join(job.diag.lines)
    ready_to_read(job, p, steps=("align",))
    assert all(x.ok for x in read_page(job, p))
    m = job.measurement()
    from pathlib import Path
    text = Path(job.run.i1io_table_measurement(job.stamp)).read_text(encoding="utf-8")
    assert m.ok and ms.WHITE_KEYWORD not in text


def test_no_spectral_values_refuses_the_option_truthfully(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    assert job.set_options(["-v", "-c", "1", "-p", "-n", "chart"]).ok
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert r.ok and r.detail["stored_white"] == {"used": False,
                                                "why": "stored_white_needs_spectral_values"}


def test_readings_with_and_without_the_stored_white_never_mix(tmp_path):
    rows = {"A1": ["1", '"A1"', "50.0", "50.0", "50.0", "80.0"]}
    fields = ["SAMPLE_ID", "SAMPLE_LOC", "XYZ_X", "XYZ_Y", "XYZ_Z", "SPEC_500"]
    with pytest.raises(ms.Refused):
        ms._scaled(fields[:5], rows["A1"][:5], (1.0,) * 36)    # no spectrum: refused
    wl = [f"SPEC_{w}" for w in sp.STORED_TILE_WL]
    full = fields[:5] + wl
    row = rows["A1"][:5] + ["80.0"] * 36
    out = ms._scaled(full, row, (0.5,) * 36)
    assert all(float(v) == pytest.approx(40.0) for v in out[5:])
    assert float(out[3]) == pytest.approx(40.0, abs=0.05)        # Y of a flat 40 % grey


# ---- the window --------------------------------------------------------------------------------

def test_every_refusal_has_its_sentence():
    from ui import i1io_table_window as W
    for why in ("stored_white_not_readable", "stored_white_not_a_white_tile",
                "stored_white_no_tile_reading", "stored_white_too_far_from_the_reading",
                "stored_white_needs_spectral_values"):
        assert "_" not in W.stored_white_reason(why), why
    from workflow import measurement_messages as M
    t, b = M.M_I1IO_DRIVE_STORED_WHITE_REFUSED.render(why=W.stored_white_reason(
        "stored_white_not_a_white_tile"))
    assert "own white reference" in b and "—" not in b


def test_the_struct_layout_is_little_endian_floats():
    raw = struct.pack("<36f", *TILE)
    assert struct.unpack("<36f", raw) == pytest.approx(TILE, abs=1e-6)
