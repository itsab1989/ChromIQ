"""X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan (Preferences > Beta,
2026-11-15): the condition files, as the app reads them, and the build.

* the pairing hash: the first table's data block only, ``\\r`` left out; a
  header edit or a second table does not change it, a reading does;
* ``Run.condition_ti3`` names a file by the readings it belongs to;
* "Build from" offers the main file's own condition always, another one only
  when its file is in step, never for a refinement merge, and says why;
* colprof reads the chosen file and still writes the run's own profile
  (``-O``); with ``readings_from`` unset its arguments are today's;
* the FWA gate asks the file the readings come from.
"""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Run  # noqa: E402
from workflow import i1pro3_conditions as C  # noqa: E402

TI3 = """CTI3
{head}
DESCRIPTOR "x"
TARGET_INSTRUMENT "X-Rite i1 Pro 3"
NUMBER_OF_FIELDS 6
BEGIN_DATA_FORMAT
SAMPLE_ID SAMPLE_LOC RGB_R XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 2
BEGIN_DATA
1 "A1" 0 {y} 1 1
2 "A2" 100 95 100 108
END_DATA
"""


#: A main file records its condition (the Measure tab does so at the end of
#: every session, R4); one that records none is review F1's case.
RECORDED_M0 = 'KEYWORD "MEASUREMENT_CONDITION"\nMEASUREMENT_CONDITION "M0"'


def _write(p: Path, y="1.0", head=RECORDED_M0, tail="", nl="\n") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((TI3.format(y=y, head=head) + tail).replace("\n", nl)
                  .encode("latin-1"))
    return p


def _sibling(main: Path, cond: str, y="2.0") -> Path:
    h = C.data_block_hash(main)
    p = Run.for_dir(main.parent).condition_ti3(cond, measurement=main)
    assert p == main.parent / "conditions" / f"{h}-{cond}.ti3"
    return _write(p, y=y, head=f'KEYWORD "MEASUREMENT_CONDITION"\n'
                  f'MEASUREMENT_CONDITION "{cond}"\n'
                  f'KEYWORD "CHROMIQ_CONDITION_OF"\nCHROMIQ_CONDITION_OF "{h}"')


def test_the_hash_is_of_the_readings_only(tmp_path):
    a = C.data_block_hash(_write(tmp_path / "a.ti3"))
    assert a and a == C.data_block_hash(_write(
        tmp_path / "b.ti3", head='KEYWORD "MEASUREMENT_CONDITION"\n'
        'MEASUREMENT_CONDITION "M0"'))
    assert a == C.data_block_hash(_write(tmp_path / "c.ti3", nl="\r\n"))
    assert a == C.data_block_hash(_write(
        tmp_path / "d.ti3", tail="CAL\nBEGIN_DATA\n1 2\nEND_DATA\n"))
    assert a != C.data_block_hash(_write(tmp_path / "e.ti3", y="1.5"))
    assert C.data_block_hash(tmp_path / "missing.ti3") is None


def test_build_from_offers_what_is_in_step(tmp_path):
    main = _write(tmp_path / "runs" / "run1" / "P.ti3")
    only = C.choices_for(main)
    assert [c.cond for c in only] == ["M0", "M1", "M2"]
    assert only[0].main and only[0].path == main
    assert not only[1].usable and "switched on" in only[1].reason
    m1 = _sibling(main, "M1")
    ch = C.choices_for(main)
    assert ch[1].usable and ch[1].path == m1 and not ch[2].usable
    assert C.condition_file(main, "M1") == m1
    assert C.condition_file(main, "M0") == main
    # a refinement merge: only the main
    assert [c.usable for c in C.choices_for(main, merging=True)] == [
        True, False, False]
    # the main's readings change (an average, an import): no pair any more
    _write(main, y="9.0")
    assert not C.choices_for(main)[1].usable
    # ... and back (a Discard puts them back): the pair is found again
    _write(main, y="1.0")
    assert C.choices_for(main)[1].usable


def test_a_file_whose_inside_disagrees_is_not_used(tmp_path):
    main = _write(tmp_path / "run" / "P.ti3")
    m1 = _sibling(main, "M1")
    m1.write_text(m1.read_text(encoding="latin-1").replace("CHROMIQ_CONDITION_OF \"",
                                         "CHROMIQ_CONDITION_OF \"x"),
                  encoding="latin-1")
    assert C.condition_file(main, "M1") is None


def test_another_instrument_is_named(tmp_path):
    main = _write(tmp_path / "run" / "P.ti3")
    main.write_text(main.read_text(encoding="latin-1").replace("X-Rite i1 Pro 3",
                                             "X-Rite i1 Pro 2"),
                    encoding="latin-1")
    assert "i1 Pro 2" in C.choices_for(main)[1].reason


def test_main_condition_follows_the_filter():
    assert C.main_condition(None) == "M0"
    assert C.main_condition("n") == "M0"
    assert C.main_condition("5") == "M1"
    assert C.main_condition("u") == "M2"
    assert C.main_condition("p") is None


def test_colprof_reads_the_chosen_file_and_writes_the_runs_profile(tmp_path):
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    main = _write(tmp_path / "run" / "P.ti3")
    m1 = _sibling(main, "M1")
    b = ProfileBuilder(runner=None)
    p = ProfileParams(ti3_path=main, description="P")
    today = b._build_args(p)
    assert today[-1] == str(main.with_suffix("")) and "-O" not in today
    on = b._build_args(replace(p, readings_from=m1))
    assert on[-1] == str(m1.with_suffix(""))
    k = on.index("-O")
    assert Path(on[k + 1]).stem == "P" and Path(on[k + 1]).parent == main.parent
    assert on[:k] == today[:-1]
    assert b.expected_icc_path(replace(p, readings_from=m1)) == \
        b.expected_icc_path(p)


def test_the_fwa_gate_asks_the_file_the_readings_come_from(tmp_path):
    from workflow.fwa_gate import without_refused_fwa
    from workflow.profile_builder import ProfileParams
    main = _write(tmp_path / "run" / "P.ti3")
    m1 = _sibling(main, "M1")
    p = ProfileParams(ti3_path=main, fwa_enabled=True, readings_from=m1)
    _params, refusal = without_refused_fwa(p)
    # the sibling was asked (its condition is M1), not the main (M0)
    assert refusal is not None and refusal.condition == "M1"


def test_a_duplicated_run_keeps_its_pair_paired(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.current_run()
    main = _write(run.measurement_ti3)
    m1 = _sibling(main, "M1")
    new = proj.duplicate_run(run)
    assert (new.condition_dir / m1.name).is_file()
    assert C.condition_file(new.measurement_ti3, "M1") == new.condition_dir / m1.name


def test_a_run_without_the_folder_duplicates_as_before(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.current_run()
    _write(run.measurement_ti3)
    new = proj.duplicate_run(run)
    assert not new.condition_dir.exists()
