# SPDX-License-Identifier: GPL-3.0-or-later
"""Release review 4.3.47 (independent): two things the release texts must keep true.

1. The v4.3.47 CHANGELOG entry is the published release note (`scripts/release_notes.py`).
   A `###` heading that script does not know is NOT a section: it is copied, heading and
   all, into the section above it and its bullets are counted there. v4.3.46's
   "### Honest limits" rendered inside "Changed" and counted its limits as changes. Every
   heading of the 4.3.47 entry must be one the script renders as its own section.
2. The reason shown when an arrival is read twice beside its target says what the rule is:
   the rule accepts up to and INCLUDING 10 units (1 mm) on each axis (`_near` is `<=`), so
   "less than 1 mm" was not true of an arm exactly 1 mm off.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _entry(version: str) -> "list[str]":
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    out, on = [], False
    for ln in lines:
        if re.match(r"^## \S+\s*$", ln):
            if on:
                break
            on = ln.strip() == f"## {version}"
            continue
        if on:
            out.append(ln)
    assert out, f"no CHANGELOG entry {version}"
    return out


def test_every_heading_of_the_4347_entry_renders_as_its_own_section():
    import release_notes as rn
    known = {md.lower() for _k, md, _p in rn.SECTIONS}
    heads = [re.sub(r"^#+\s*", "", ln).strip() for ln in _entry("v4.3.47")
             if ln.startswith("### ")]
    assert heads, "the entry has no section headings"
    unknown = [h for h in heads if h.lower() not in known]
    assert not unknown, f"headings the release note would bury in another section: {unknown}"
    note = rn.build(["v4.3.47"], "v4.3.47")
    assert "### ⚠️ Known issues" in note
    # the honest limits are not counted as changes or fixes
    known_part = note.split("### ⚠️ Known issues", 1)[1]
    assert "has still not read a chart on a real table" in known_part


def test_the_arrival_beside_reason_says_at_most_1_mm():
    from ui.i1io_table_window import reason_text
    from workflow.i1io.table import job as J
    assert J.ARRIVAL_BESIDE_UNITS == 10
    # inclusive: an arm exactly 10 units (1 mm) off on one axis is within the rule
    assert J._near((10, 0), (0, 0), J.ARRIVAL_BESIDE_UNITS)
    assert J._near((10, 10), (0, 0), J.ARRIVAL_BESIDE_UNITS)
    text = reason_text("arrived_beside_the_target")
    assert "less than 1 mm" not in text
    assert "at most 1 mm" in text


# ---- three planted faults of the release review that no test caught --------------------------
def test_a_window_answer_makes_the_last_reading_stale():
    """Planted fault A5: `person_answered` (the window's own questions: Carry on, the mark-3
    check, the problem page) no longer marked the answer. Every reading before such an answer
    must count as stale, so the next computed move reads the arm again first (MUST-1)."""
    from tests.i1io_table import job_harness as H
    job, sim, _t = H.make_job()
    person = H.Person(job, sim, None, None)
    person.drive(job.open())
    person.drive(job.park())
    assert job._table is not None and job._gen is None
    job._table.position()
    assert job._reading_is_stale() is False
    job.person_answered("check_mark", "not centred")
    assert job._reading_is_stale() is True
    job._table.position()
    assert job._reading_is_stale() is False
    # also the hands-off confirmation of the window marks the answer (the reading before it is
    # as old as any other)
    job.person_answered("check_mark", "centred")
    assert job._reading_is_stale() is True
    job.close()


def test_the_creeps_own_steps_read_the_arm_again_after_a_question():
    """Planted fault A3: the creep's loop judged its step from `position_now` again. No test
    drives a question inside that loop (none is asked there today), so the call is pinned."""
    import inspect
    from workflow.i1io.table import job as J
    src = inspect.getsource(J.TableJob._creep)
    loop = src[src.index("while self.front_reached() < need:"):]
    assert 'self._read_again_if_asked(d.position_now, "creep")' in loop
    assert loop.index('yield from self._hands_off("creep")') < loop.index("_read_again_if_asked")
    assert loop.index("_read_again_if_asked") < loop.index("geo.m0_line(")


def test_no_project_import_with_pages_draws_none(tmp_path, monkeypatch):
    """Planted fault B3: the no-project route drew pages although the chart came with its
    own. Pages that came with a chart are the sheet that was printed: never redrawn."""
    import workflow.chart_import as ci
    from ui.ti2_loader import _copy_files
    ext = tmp_path / "ext"
    ext.mkdir()
    (ext / "src.ti2").write_text("ti2", encoding="utf-8")
    (ext / "src.ti1").write_text("ti1", encoding="utf-8")
    tif = ext / "src_01.tif"
    tif.write_text("tif", encoding="utf-8")
    monkeypatch.setattr(ci, "rebuild_missing_pages",
                        lambda *a: (_ for _ in ()).throw(AssertionError(a)))
    out, pages = _copy_files(ext / "src.ti2", ext / "src.ti1", [tif], tmp_path / "work",
                             "Has-Pages", bin_dir=tmp_path / "bin")
    assert [p.read_text(encoding="utf-8") for p in pages] == ["tif"]
