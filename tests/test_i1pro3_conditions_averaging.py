"""X-Rite i1Pro 3: keep M0, M1 and M2 from every scan (Preferences > Beta):
averaging (Basti, 2026-11-15, ruling 3: "needed for completeness").

* The same reads are averaged in each of the other two conditions, in the
  same order and by the same method, and the averages are kept as the
  condition files of the averaged measurement (named by ITS readings), so
  Build Profile offers them.
* A condition one read has no readings in is not averaged and not offered
  for the averaged run; Build Profile names the read that lacks it.
* The real ArgyllCMS ``average`` makes the files: the M1 average equals the
  mean of the M1 reads, patch for patch.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from core.file_manager import Run
from core.resource_path import argyll_binary
from workflow import i1pro3_conditions as C

from tests.test_i1pro3_conditions_verification import _pair, _ti3

pytestmark = pytest.mark.skipif(
    not (Path(argyll_binary("average")).exists()
         or shutil.which("average") is not None),
    reason="ArgyllCMS `average` not installed")


def _xyz(path: Path) -> "list[float]":
    rows, on = [], False
    for ln in path.read_text(encoding="latin-1").splitlines():
        if ln.strip() == "BEGIN_DATA":
            on = True
            continue
        if ln.strip() == "END_DATA":
            break
        if on and ln.strip():
            rows.append(float(ln.split()[5]))
    return rows


def _reads(tmp_path, m2_in_both=True):
    run = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    r1 = _ti3(run.reads_dir / "read1.ti3", w="84")
    r2 = _ti3(run.reads_dir / "read2.ti3", w="86")
    _pair(r1, "M1", "88")
    _pair(r2, "M1", "90")
    _pair(r1, "M2", "80")
    if m2_in_both:
        _pair(r2, "M2", "82")
    return run, [r1, r2]


def _average_main(run, reads) -> Path:
    import subprocess
    out = run.measurement_ti3
    subprocess.run([str(argyll_binary("average")), str(reads[0]),
                    str(reads[1]), str(out)], check=True, timeout=60,
                   capture_output=True)
    return out


def test_the_same_reads_are_averaged_in_each_condition(tmp_path):
    run, reads = _reads(tmp_path)
    main = _average_main(run, reads)
    done = C.average_conditions(main, reads)
    assert done == {"M1": "", "M2": ""}
    m1 = C.condition_file(main, "M1")
    m2 = C.condition_file(main, "M2")
    assert m1 is not None and m2 is not None
    assert m1.parent == run.condition_dir
    assert m1.name.startswith(C.data_block_hash(main) + "-")
    assert _xyz(m1)[0] == pytest.approx(89.0)
    assert _xyz(m2)[0] == pytest.approx(81.0)
    assert _xyz(main)[0] == pytest.approx(85.0)
    assert C.file_condition(m1) == "M1" and C.file_condition(m2) == "M2"
    got = {c.cond: c.usable for c in C.choices_for(main)}
    assert got == {"M0": True, "M1": True, "M2": True}


def test_a_condition_one_read_lacks_is_not_offered_and_says_which(tmp_path):
    run, reads = _reads(tmp_path, m2_in_both=False)
    main = _average_main(run, reads)
    done = C.average_conditions(main, reads)
    assert done == {"M1": "", "M2": "read2.ti3"}
    assert C.condition_file(main, "M2") is None
    ch = {c.cond: c for c in C.choices_for(main)}
    assert ch["M1"].usable and not ch["M2"].usable
    assert "read2.ti3" in ch["M2"].reason and "average" in ch["M2"].reason


def test_the_measure_tab_averages_them_only_with_the_beta_on(tmp_path):
    from types import SimpleNamespace
    from ui.tabs.tab_measure import TabMeasure

    class _S(dict):
        def get(self, k, d=None):
            return super().get(k, d)

    class _Log:
        def __init__(self):
            self.lines = []

        def appendPlainText(self, t):
            self.lines.append(t)

    run, reads = _reads(tmp_path, m2_in_both=False)
    main = _average_main(run, reads)
    fake = SimpleNamespace(_settings=_S({C.SETTING: False}), _log=_Log())
    TabMeasure._average_the_conditions(fake, main, reads, "mean")
    assert fake._log.lines == [] and C.condition_file(main, "M1") is None
    fake._settings = _S({C.SETTING: True})
    TabMeasure._average_the_conditions(fake, main, reads, "mean")
    assert C.condition_file(main, "M1") is not None
    text = "\n".join(fake._log.lines)
    assert "averaged too" in text and "read2.ti3 has no" in text
