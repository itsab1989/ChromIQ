"""The engine can emit an ArgyllCMS .cie reference (measured XYZ) from a run's
.ti3, as the colour half of a scanner-recognition target (#97)."""
from workflow.layout_engine import cie_writer
from workflow.ti3_analysis import parse_ti3

# A tiny CGATS .ti3 with device RGB, measured XYZ and SAMPLE_LOC (the loc the
# .cht boxes use). Two patches — one white, one red.
_TI3 = (
    "CTI3\n\n"
    'KEYWORD "SAMPLE_LOC"\n'
    "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
    "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
    "NUMBER_OF_SETS 2\nBEGIN_DATA\n"
    '1 "A01" 100 100 100 95.05 100.00 108.90\n'
    '2 "A02" 100 0 0 41.24 21.26 1.93\n'
    "END_DATA\n"
)


def test_build_cie_text_structure(tmp_path):
    p = tmp_path / "c.ti3"
    p.write_text(_TI3, encoding="utf-8")
    out = cie_writer.write_cie(tmp_path / "c.cie", p, descriptor="My chart")
    txt = out.read_text(encoding="utf-8")

    assert txt.startswith("IT8.7/2")
    assert 'DESCRIPTOR "My chart"' in txt
    assert "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z" in txt
    assert "NUMBER_OF_SETS 2" in txt
    # rows keyed by SAMPLE_LOC (== the .cht box loc), measured XYZ verbatim
    assert "A01 95.050000 100.000000 108.900000" in txt
    assert "A02 41.240000 21.260000 1.930000" in txt
    assert txt.rstrip().endswith("END_DATA")


def test_cie_rows_key_on_sample_loc_not_id(tmp_path):
    """The reference must key on SAMPLE_LOC (A01…), the id scanin matches to the
    .cht — never the bare numeric SAMPLE_ID."""
    p = tmp_path / "c.ti3"
    p.write_text(_TI3, encoding="utf-8")
    rows = cie_writer.cie_rows_from_ti3(parse_ti3(p))
    assert [r[0] for r in rows] == ["A01", "A02"]
    # measured XYZ carried straight through (no reconstruction)
    assert rows[0][1:] == (95.05, 100.0, 108.9)
