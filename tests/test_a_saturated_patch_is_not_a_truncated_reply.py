"""A saturated patch on glossy paper reads exactly 0.0 in the bands its ink
absorbs, and that is a MEASUREMENT — not a truncated reply.

Reported from the field 2026-09-05: the most saturated patches of a chart could
not be read at all with a CR30 on glossy or satin paper, while the same patches
on matte read first time. What the user saw:

    That reading did not come through
    The reading for patch C16 did not arrive complete, so ChromIQ has not used
    it -- nothing wrong has gone into your measurement file.
    ...
    What the instrument reported: the instrument did not return a complete
    reading (no usable reply among the only candidate in 200 bytes; last
    reason: candidate at 0 has 3 zero bands (truncated reply))

Three. Exactly the threshold `Measurement.zero_run() >= 3` refused on, while
every truncated reply this project has ever recorded had a run of 5, 16 or 31.

The premise of that threshold -- "a real dark patch reads a few percent, never
exactly 0.0 across a run" -- is contradicted by this project's own captures. The
firmware CLAMPS: a signal at or below the stored dark reference comes back as
exactly 0.00000 %R (EXP-022 on open air; EXP-020 phase A, all 31 bands, five
readings; and again on the owner's unit 2026-09-05). Ink on glossy reaches
roughly 0.2..0.4 %R where it absorbs against 1.3..2.5 %R for the same ink soaked
into matte, and the dark reference -- taken against open air, on an instrument
with no black tile -- can sit high by ~0.15 %R. So glossy clamps and matte does
not, which is precisely the paper dependence that was reported.

The cost was not one refused reading. `measure_bridge.MAX_READ_RETRIES` re-arms
the patch five times and then gives up on it, and the cause is deterministic --
the patch really does read zero there -- so the chart could never be finished,
on that patch or any other one of that saturation.

What replaces the threshold is exact, and these tests pin both halves of it: the
readings that must now get through, and the not-ready replies that must still
not.
"""
from __future__ import annotations

import inspect
import struct

import pytest

from workflow.cr30 import ble, device
from workflow.cr30.device import CR30, _parse_reply
from workflow.cr30.measurement import Measurement, MeasurementError

WL = [400 + 10 * i for i in range(31)]

#: A saturated blue/violet on glossy, as the instrument reports it: real
#: reflectance at the short end, falling to the instrument's floor from about
#: 600 nm, with the three deepest bands clamped to exactly 0.0. This is the
#: shape in the field report.
SATURATED = [24.1, 22.8, 20.4, 17.9, 14.2, 10.6, 7.31, 5.02, 3.44, 2.51, 1.88,
             1.42, 1.09, 0.86, 0.71, 0.58, 0.47, 0.39, 0.31, 0.24, 0.17, 0.11,
             0.06, 0.02, 0.0, 0.0, 0.0, 0.03, 0.09, 0.18, 0.34]
SATURATED_LAB = (28.44, 52.13, -61.77)

#: An ordinary mid-tone, nothing clamped.
PLAIN = [10.0 + 0.5 * i for i in range(31)]
PLAIN_LAB = (50.0, 1.0, -1.0)


def reply(values, lab, total: int = 200) -> bytes:
    """One BLE measurement reply, laid out exactly as `device` reads it."""
    buf = bytearray(total)
    buf[0:4] = ble.MEASUREMENT_HDR
    struct.pack_into(">H", buf, 4, 400)
    buf[6], buf[7] = 10, 31
    struct.pack_into("<31f", buf, ble.SPECTRUM_AT, *values)
    struct.pack_into("<3f", buf, ble.LAB_AT, *lab)
    return bytes(buf)


def cut_at(raw: bytes, byte: int) -> bytes:
    """`raw` as the device leaves it when it has only written `byte` bytes.

    The buffer is pre-zeroed, so everything past the write is 0x00 -- which is
    what a real not-ready reply is, and why one is so hard to tell from a dark
    reading by looking at the spectrum alone.
    """
    return raw[:byte] + bytes(len(raw) - byte)


#: Byte offsets that reproduce the truncation shapes on record. The spectrum is
#: 31 little-endian float32 from `SPECTRUM_AT`, so band N starts at
#: `SPECTRUM_AT + 4*N`, and `LAB_AT` (184) is past all of them.
CUT_FOR_5_ZERO_BANDS = ble.SPECTRUM_AT + 4 * 26     # the vendor capture's half
CUT_FOR_16_ZERO_BANDS = ble.SPECTRUM_AT + 4 * 15    # 14_protocol.md F-3


def fake_ble_device(raw: bytes) -> CR30:
    """A CR30 whose transport hands back exactly `raw`, and nothing else."""

    class _T:
        def ask(self, cmd, done=None, **kw):
            return raw

    d = CR30.__new__(CR30)
    d._t, d.kind, d._previous = _T(), "ble", None
    d.model, d.learned_tile, d.unit_id, d.last_identity = "CR30", None, None, None
    return d


# ---- the readings that must get through ----------------------------------

def test_the_field_report_reading_is_accepted_not_refused():
    """The exact shape from the report, through the real read path."""
    m = fake_ble_device(reply(SATURATED, SATURATED_LAB)).read_measurement()
    assert [w for w, v in zip(m.wavelengths, m.values) if v == 0.0] == [640, 650, 660]
    assert m.lab == [28.44, 52.13, -61.77], (
        "the device's own Lab was lost, so this is not the reply that arrived")


def test_the_words_from_the_field_report_can_no_longer_be_produced():
    """No 'N zero bands (truncated reply)' for a reading that has a spectrum."""
    d = fake_ble_device(reply(SATURATED, SATURATED_LAB))
    try:
        d.read_measurement()
    except MeasurementError as exc:                       # pragma: no cover
        pytest.fail(f"the reported refusal is back: {exc}")


def test_the_polling_predicate_stops_on_a_saturated_patch():
    """`_parse_reply` is the `done=` predicate the transport polls with. While
    it said no, the read went on asking until `_read_when_ready` gave up -- so
    a saturated patch cost six round trips before the window appeared."""
    assert _parse_reply(reply(SATURATED, SATURATED_LAB)) == 0


def test_a_clamped_reading_passes_the_full_gate_on_the_usb_path():
    """USB has no Lab at all (`usb_measure.read_stored` leaves it None), so the
    rule has to work without one."""
    Measurement(WL, list(SATURATED)).check_usable()


def test_a_run_of_zeros_is_no_longer_a_reason_on_its_own():
    """Longer than three, and still a reading: a deeper ink clamps more bands.
    Nothing about the length of the run decides this any more."""
    for clamped in (3, 6, 11):
        vals = [12.0] * (31 - clamped) + [0.0] * clamped
        assert Measurement(WL, vals).truncation_reason() is None, clamped
        Measurement(WL, vals).check_usable()


def test_the_number_of_clamped_bands_is_reported():
    m = Measurement(WL, list(SATURATED))
    assert m.clamped_bands() == 3
    assert Measurement(WL, [1.0] * 31).clamped_bands() == 0


# ---- the not-ready replies that must still be refused --------------------

def test_a_wholly_zero_filled_reply_is_still_refused():
    """The 31-zero-band Bluetooth read-back, and the device's not-ready buffer
    generally. There is no reading in it to keep."""
    assert _parse_reply(reply([0.0] * 31, (0.0, 0.0, 0.0))) is None
    with pytest.raises(MeasurementError):
        fake_ble_device(reply([0.0] * 31, (0.0, 0.0, 0.0))).read_measurement()
    with pytest.raises(MeasurementError):
        Measurement(WL, [0.0] * 31).check_usable()


@pytest.mark.parametrize("cut,zero_bands", [(CUT_FOR_5_ZERO_BANDS, 5),
                                            (CUT_FOR_16_ZERO_BANDS, 16)])
def test_a_half_written_reply_is_still_refused(cut, zero_bands):
    """The two truncation shapes on record: the vendor capture's 5-zero-band
    candidate and the live 16-zero-band one. Both keep a real head of spectrum,
    so no 'is it all zero' test alone would catch them -- what catches them is
    that the Lab sits AFTER the spectrum, so a reply cut off inside the spectrum
    has necessarily lost its Lab as well."""
    raw = cut_at(reply(PLAIN, PLAIN_LAB), cut)
    assert Measurement(WL, PLAIN[:31 - zero_bands] + [0.0] * zero_bands,
                       lab=[0.0, 0.0, 0.0]).zero_run() == zero_bands, (
        "this fixture no longer reproduces the recorded truncation shape")
    assert _parse_reply(raw) is None, f"a reply cut at {cut} was accepted"
    with pytest.raises(MeasurementError):
        fake_ble_device(raw).read_measurement()


def test_the_truncated_half_of_a_double_reply_still_loses_to_the_complete_one():
    """The vendor's 410-byte stream: a truncated reply followed by a whole one.
    The scan runs from the end, so the complete one wins -- but the truncated
    one must still be rejected on its own, or polling stops on it."""
    bad = cut_at(reply(PLAIN, PLAIN_LAB), CUT_FOR_5_ZERO_BANDS)
    good = reply(SATURATED, SATURATED_LAB)
    assert _parse_reply(bad) is None
    assert _parse_reply(bad + good) == len(bad)


def test_the_black_calibration_read_back_still_gets_its_answer():
    """`allow_dark` exists for exactly one caller, and open air really does read
    0.00000 on this instrument. It must keep working."""
    raw = reply([0.0] * 31, (0.0, 0.0, 0.0))
    assert _parse_reply(raw, allow_dark=True) == 0
    d = fake_ble_device(raw)
    m = d.read_measurement(enforce=False, allow_dark=True)
    assert m.values == [0.0] * 31


# ---- and it must not turn back into a threshold --------------------------

def test_no_zero_run_threshold_decides_a_reading_any_more():
    """`zero_run` is a diagnostic now. If it comes back as a gate, the field
    report comes back with it."""
    for src in (inspect.getsource(device),
                inspect.getsource(Measurement.check_usable)):
        for line in src.splitlines():
            code = line.split("#", 1)[0]
            assert "zero_run()" not in code or "raise" not in code, line
            assert "zero_run() >=" not in code, (
                "the zero-run threshold is refusing readings again: " + line)
