"""ONE corrupt byte must cost one character, not the whole measurement.

`core.text_io._not_text_at_all` refuses any file holding a NUL byte, because
UTF-16 with no byte-order mark is otherwise laundered into nonsense. A
`lenient=True` caller then falls through to `_decode_as_declared`, whose job is
to hand back the text somebody actually wrote rather than the nonsense the
refusal exists to prevent.

Its comment says it checks a *structure*: "ASCII text puts a NUL under every
second byte, on one fixed parity for the whole file." The code checked only the
parity of whatever NULs happened to be there, and **one** stray NUL at an odd
offset satisfies that. So a 344-byte ASCII `.ti3` with a single corrupt byte
was decoded as UTF-16LE and came back as 83 characters of CJK:

    BEFORE  b'CTI3\\n\\nDESCRIPTOR "Argyll Calibration Targ\\x00t chart informatio'
    AFTER   'KEYWORD "CHROMIQ_VERIFICATION"\\nCHROMIQ_VERIFICATION "true"\\n呃㍉ਊ䕄䍓...'

`workflow.ti3_analysis.mark_verification_ti3` reads leniently, edits, writes the
result to `<stem>-verify.ti3` and unlinks the original — so the person's
measurement was replaced by mojibake and the original deleted. Before
`core/text_io.py` existed the same bytes came back through
`read_text(errors="replace")` intact but for one character.

A real UTF-16 file has a NUL under about half its bytes. Requiring a quarter
admits even a file that is half CJK and rejects any plausible stray-NUL count.
"""
from __future__ import annotations

import pytest

from core.text_io import read_text
from workflow.ti3_analysis import mark_verification_ti3

# A .ti3 the way chartread writes one: ASCII, CGATS, no NUL anywhere.
GOOD_TI3 = (
    b'CTI3\n\n'
    b'DESCRIPTOR "Argyll Calibration Target chart information 3"\n'
    b'ORIGINATOR "Argyll chartread"\n'
    b'KEYWORD "DEVICE_CLASS"\nDEVICE_CLASS "OUTPUT"\n'
    b'NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
    b'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n'
    b'NUMBER_OF_SETS 2\nBEGIN_DATA\n'
    b'1 100.0 100.0 100.0 95.05 100.0 108.9\n'
    b'2 0.0 0.0 0.0 0.35 0.36 0.39\nEND_DATA\n'
)


def _corrupt(at: int) -> bytes:
    """`GOOD_TI3` with the byte at *at* zeroed, kept an even length.

    Even length matters: a crash or a short write leaves a file whose tail is
    zero-filled to a block boundary, and the UTF-16 shape test only looks at
    even-length files at all.
    """
    raw = bytearray(GOOD_TI3)
    raw[at] = 0
    if len(raw) % 2:
        raw += b"\n"
    return bytes(raw)


# Odd offsets are the dangerous ones: `all(i % 2 for i in nuls)` is satisfied
# by a single NUL there, which is what sent the whole file through utf-16-le.
@pytest.mark.parametrize("at", [1, 3, 41, 51, 101, 201])
def test_one_stray_nul_costs_one_character_not_the_file(tmp_path, at):
    p = tmp_path / "Chart.ti3"
    p.write_bytes(_corrupt(at))

    got = read_text(p, lenient=True)

    # The whole file back, with the one damaged byte and nothing else changed.
    assert got == _corrupt(at).decode("utf-8"), (
        f"a single corrupt byte at offset {at} was read as {got[:40]!r} — the "
        "measurement has been turned into something else entirely")
    assert "END_DATA" in got
    assert "95.05" in got, "a data row was lost"
    assert got.isascii(), f"the file went non-ASCII: {got[:60]!r}"


def test_the_measurement_survives_being_marked_as_a_verification(tmp_path):
    """The full route the fault was found on.

    `mark_verification_ti3` is what the Measure tab calls when a read is
    marked as a verification: it reads leniently, inserts the keyword, writes
    the result under a new name and unlinks the original. A bad decode here is
    not a display problem — it is the file, replaced, with no archive.
    """
    src = tmp_path / "Chart.ti3"
    src.write_bytes(_corrupt(41))

    out = mark_verification_ti3(src)

    text = out.read_text(encoding="utf-8")
    assert text.startswith("CTI3"), (
        "the written verification measurement is not a CGATS file any more: "
        f"{text[:60]!r}")
    assert "CHROMIQ_VERIFICATION" in text
    assert "95.05" in text and "0.35 0.36 0.39" in text, (
        "measured data was lost on the way through")


def test_a_real_bom_less_utf16_file_is_still_recognised(tmp_path):
    """The case the shape test exists for must keep working.

    PowerShell 5.1 and old Notepad write UTF-16; a copy that lost its BOM has
    a NUL under every second byte, and that is the structure being detected.
    Guarding the density must not cost this.
    """
    p = tmp_path / "notes.txt"
    p.write_bytes('CREATED "2026-09-02"\n'.encode("utf-16-le"))

    got = read_text(p, lenient=True)

    assert got.startswith('CREATED "2026-09-02"')
    assert "\x00" not in got


def test_a_zero_filled_tail_does_not_become_utf16_either(tmp_path):
    """The other shape a crash leaves: a file padded to a block with zeros.

    Those NULs land on both parities, so they never triggered the UTF-16 path,
    but the file must still come back as its own text rather than as
    replacement characters for the part that was written.
    """
    p = tmp_path / "Chart.ti3"
    p.write_bytes(GOOD_TI3 + b"\x00" * 64)

    got = read_text(p, lenient=True)

    assert got.startswith("CTI3")
    assert "END_DATA" in got
