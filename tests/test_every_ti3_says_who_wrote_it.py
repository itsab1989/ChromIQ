"""A10 (4.3.50): every .ti3 ChromIQ writes or finalises says which ChromIQ and which
chart-reading helper made it (CHROMIQ_VERSION, CHROMIQ_HELPER_BUILD), header only,
and ArgyllCMS still reads it (colprof builds a profile from a stamped file)."""
from __future__ import annotations

import inspect
import shutil
import subprocess
from pathlib import Path

import pytest

from core.version import APP_VERSION
from workflow import ti3_provenance as tp

ROOT = Path(__file__).resolve().parent.parent
ARGYLL = Path("/Applications/Argyll/bin")


def _a_ti3(tmp_path) -> Path:
    src = next(p for p in sorted((ROOT / "tests" / "data").rglob("*.ti3"))
               if p.stat().st_size > 20_000 and b"BEGIN_DATA_FORMAT" in p.read_bytes())
    dst = tmp_path / "m.ti3"
    shutil.copy(src, dst)
    return dst


def test_the_keywords_go_into_the_header_and_nothing_else_changes(tmp_path):
    from workflow.i1pro3_conditions import data_block_hash
    f = _a_ti3(tmp_path)
    before = f.read_bytes()
    h0 = data_block_hash(f)
    assert tp.stamp(f, "chromiq-chartread_2026-11-19d_legacy-labels+ruler-check+x")
    assert tp.read(f) == (APP_VERSION, "chromiq-chartread_2026-11-19d_legacy-labels")
    after = f.read_bytes()
    assert data_block_hash(f) == h0
    assert after.split(b"BEGIN_DATA_FORMAT", 1)[1] == before.split(b"BEGIN_DATA_FORMAT", 1)[1]
    assert not tp.stamp(f, "chromiq-chartread_2026-11-19d_legacy-labels")   # idempotent
    # a Python step keeps the helper's build; stock chartread is named
    assert not tp.stamp(f) and tp.read(f)[1] == "chromiq-chartread_2026-11-19d_legacy-labels"
    assert tp.stamp(f, tp.STOCK) and tp.read(f)[1] == "stock chartread"
    head = f.read_bytes().split(b"BEGIN_DATA_FORMAT")[0]
    assert head.count(b"CHROMIQ_VERSION") == 2 and head.count(b"CHROMIQ_HELPER_BUILD") == 2


def test_a_file_without_a_helper_says_so(tmp_path):
    f = _a_ti3(tmp_path)
    assert tp.stamp(f) and tp.read(f) == (APP_VERSION, "-")


def test_never_raises(tmp_path):
    assert tp.stamp(tmp_path / "missing.ti3") is False
    junk = tmp_path / "junk.ti3"
    junk.write_bytes(b"\x00\x01 not cgats")
    assert tp.stamp(junk) is False and junk.read_bytes() == b"\x00\x01 not cgats"


@pytest.mark.skipif(not (ARGYLL / "colprof").is_file(), reason="ArgyllCMS not installed")
def test_argyll_reads_a_stamped_file(tmp_path):
    f = _a_ti3(tmp_path)
    tp.stamp(f, "chromiq-chartread_2026-11-19d+x")
    res = subprocess.run([str(ARGYLL / "colprof"), "-qm", "-O", "x.icc", f.stem],
                         cwd=tmp_path, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=600)
    assert res.returncode == 0, res.stdout[-1500:] + res.stderr[-1500:]
    assert (tmp_path / "x.icc").is_file()


def test_every_writing_path_stamps():
    """The places ChromIQ writes or finalises a .ti3 each call the stamp."""
    from ui.tabs import tab_measure
    from workflow import i1pro3_conditions, reference_convert, ti3_average, ti3_merge
    from workflow.i1io.table import job
    assert "_stamp_provenance_at_end()" in inspect.getsource(tab_measure.TabMeasure)
    assert "stamp(result)" in inspect.getsource(ti3_merge.settle_combined_xyz_method)
    assert "stamp(tmp)" in inspect.getsource(i1pro3_conditions.average_conditions)
    assert "stamp(out)" in inspect.getsource(ti3_average.average_scanner_ti3)
    assert "stamp(ti3_path)" in inspect.getsource(reference_convert)
    # NOT the table's save: its session-state check compares the filed file byte for
    # byte, so a header written after filing made a saved sitting read "interrupted"
    # (tests/i1io_table/test_job_review8_fixes.py); the table path is listed as not covered
    assert "provenance" not in inspect.getsource(job)


def test_the_tab_stamps_the_session_file_and_its_conditions(tmp_path, monkeypatch):
    from ui.tabs import tab_measure as T
    f = _a_ti3(tmp_path)
    ti1 = f.with_suffix(".ti1")

    class _Mgr:
        applog_helper_build = "chromiq-chartread_b+caps"

    class _Fake:
        _ti1_path = ti1
        _ti3_mtime_before = None
        _manager = _Mgr()
        _settings = {"i1pro3_conditions_beta": False}
    T.TabMeasure._stamp_provenance_at_end(_Fake())
    assert tp.read(f) == (APP_VERSION, "chromiq-chartread_b")
