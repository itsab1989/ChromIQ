"""4.3.26: the reason a measurement whose colours do not follow the chart is
refused, with the way out for a patch list somebody reordered.

jctay (printerknowledge forum, 2026-11-07) put a chart's patches in another
order with another program before measuring them in i1Profiler. The import
refused the file, as it must: ChromIQ never pairs readings with patches by
their colours (§I.9). The reason said only that the colours did not agree, in
English whatever the language. It now says what to do instead, in every
language, and §M-PROPOSED quotes it word for word.
"""
from __future__ import annotations

from pathlib import Path

from workflow import measurement_messages as M

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/design/unified_measurement_management.md"


def _quoted_block(mid: str) -> "list[str]":
    text = SPEC.read_text(encoding="utf-8")
    start = text.index(f"### {mid} ")
    end = text.index("\n### ", start + 1)
    lines = [l for l in text[start:end].splitlines() if l.startswith(">")]
    return [l[1:].strip() for l in lines]


def test_the_block_is_the_headline_and_every_fragment_of_the_code():
    quoted = _quoted_block("M-IMPORT-IDENTITY-REASON")
    msg = M.M_IMPORT_IDENTITY_REASON
    assert not msg.approved
    assert quoted[0] == f"**{msg.title}**"
    body = [l for l in quoted[1:] if l]
    assert body == [M._IDENTITY_ALL, M._IDENTITY_ONE, M._IDENTITY_ONLY,
                    M._IDENTITY_REORDERED]
    assert body == msg.body.split("\n")


def test_counts_have_a_real_singular_and_the_way_out_follows():
    many = M.identity_mismatch_reason(12, 24)
    assert many.startswith("12 of 24 patches do not hold the colour")
    one = M.identity_mismatch_reason(1, 24)
    assert one.startswith("1 of 24 patches does not hold the colour")
    only = M.identity_mismatch_reason(1, 1)
    assert only.startswith("the one patch in this file does not hold")
    for r in (many, one, only):
        assert "put in another order for i1Profiler by another program" in r
        assert "turned export" in r
        # It is the {reason} of "The reason: {reason}.": no full stop of
        # its own at the end, and lower case at the start.
        assert not r.endswith(".") and r[0].islower() or r[0].isdigit()


def test_verify_patch_identity_gives_this_reason(tmp_path):
    import numpy as np

    from workflow.measurement_report import verify_patch_identity

    ti2 = tmp_path / "c.ti2"
    ti2.write_text(
        "CTI2\n\nCOLOR_REP \"iRGB\"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
        "1 A1 100 0 0 40 20 2\n2 A2 0 0 100 20 10 90\nEND_DATA\n", encoding="utf-8")

    class _Measured:
        rgb = np.array([[0.0, 0.0, 100.0], [100.0, 0.0, 0.0]])
        sample_ids = ["1", "2"]

    v = verify_patch_identity(_Measured(), ti2)
    assert v["verdict"] == "mismatch", v
    assert v["reason"] == M.identity_mismatch_reason(2, 2)
