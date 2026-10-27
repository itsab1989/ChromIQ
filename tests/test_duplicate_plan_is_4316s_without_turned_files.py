"""Duplicate's plan is 4.3.16's when no turned file is involved (review 4.3.17
r4, SF-1 and NIT-1).

SF-1: the turned-export change made every group skip what an earlier group
had already listed, so a project called "merged" or "preconditioning" lost
rows from the confirmation window and its total changed, with the beta option
off and no turned files at all. 4.3.16 lists a file two groups match under
both. `EXPECTED` below was produced by running this exact layout through the
4.3.16 tree (`git archive e73f93095`), and is hard-coded so the test does not
need that tree.

NIT-1: a stale turned order whose files are spelled decomposed on disk (a
project "Café" restored from an HFS+ volume) must still be recognised as the
turned export, so the exports group does not copy it by name.
"""
from __future__ import annotations

import os
import shutil
import sys
import unicodedata
from pathlib import Path

import pytest

from core.file_manager import Project
from workflow import i1profiler_turned as T

from tests.test_i1profiler_turned_export import _chart

#: The layout the expectation was computed on. Order and sizes matter: each
#: file is ``10 + index`` bytes, and a name already written is not rewritten.
NAMES = ["{s}.ti1", "{s}.ti2", "{s}_01.tif", "{s}.channels.json", "{s}.ti3",
         "{s}.icc", "merged.ti3", "merged.icc", "preconditioning.ti3",
         "preconditioning.icc", "calibrated.icc", "reports/report_1.json",
         "exports/{s}-i1profiler.txt"]

#: 4.3.16's `duplicate_run_plan` for that layout (e73f93095).
EXPECTED = {"P ('profile', 'refinement')": [['profile',
                                  ['P.icc',
                                   'merged.ti3',
                                   'merged.icc',
                                   'calibrated.icc'],
                                  68],
                                 ['refinement',
                                  ['preconditioning.ti3',
                                   'preconditioning.icc'],
                                  37]],
 'P None': [['chart', ['P.ti1', 'P.ti2', 'P.channels.json', 'P_01.tif'], 46],
            ['measurement', ['P.ti3'], 14],
            ['profile',
             ['P.icc', 'merged.ti3', 'merged.icc', 'calibrated.icc'],
             68],
            ['refinement',
             ['preconditioning.ti3', 'preconditioning.icc'],
             37],
            ['reports', ['reports/report_1.json'], 21],
            ['exports', ['exports/P-i1profiler.txt'], 22]],
 "calibrated ('profile', 'refinement')": [['profile',
                                           ['calibrated.icc',
                                            'merged.ti3',
                                            'merged.icc'],
                                           48],
                                          ['refinement',
                                           ['preconditioning.ti3',
                                            'preconditioning.icc'],
                                           37]],
 'calibrated None': [['chart',
                      ['calibrated.ti1',
                       'calibrated.ti2',
                       'calibrated.channels.json',
                       'calibrated_01.tif'],
                      46],
                     ['measurement', ['calibrated.ti3'], 14],
                     ['profile',
                      ['calibrated.icc', 'merged.ti3', 'merged.icc'],
                      48],
                     ['refinement',
                      ['preconditioning.ti3', 'preconditioning.icc'],
                      37],
                     ['reports', ['reports/report_1.json'], 21],
                     ['exports', ['exports/calibrated-i1profiler.txt'], 22]],
 "merged ('profile', 'refinement')": [['profile',
                                       ['merged.icc',
                                        'merged.ti3',
                                        'calibrated.icc'],
                                       49],
                                      ['refinement',
                                       ['preconditioning.ti3',
                                        'preconditioning.icc'],
                                       37]],
 'merged None': [['chart',
                  ['merged.ti1',
                   'merged.ti2',
                   'merged.channels.json',
                   'merged_01.tif'],
                  46],
                 ['measurement', ['merged.ti3'], 14],
                 ['profile',
                  ['merged.icc', 'merged.ti3', 'calibrated.icc'],
                  49],
                 ['refinement',
                  ['preconditioning.ti3', 'preconditioning.icc'],
                  37],
                 ['reports', ['reports/report_1.json'], 21],
                 ['exports', ['exports/merged-i1profiler.txt'], 22]],
 "preconditioning ('profile', 'refinement')": [['profile',
                                                ['preconditioning.icc',
                                                 'merged.ti3',
                                                 'merged.icc',
                                                 'calibrated.icc'],
                                                68],
                                               ['refinement',
                                                ['preconditioning.ti3',
                                                 'preconditioning.icc'],
                                                29]],
 'preconditioning None': [['chart',
                           ['preconditioning.ti1',
                            'preconditioning.ti2',
                            'preconditioning.channels.json',
                            'preconditioning_01.tif'],
                           46],
                          ['measurement', ['preconditioning.ti3'], 14],
                          ['profile',
                           ['preconditioning.icc',
                            'merged.ti3',
                            'merged.icc',
                            'calibrated.icc'],
                           68],
                          ['refinement',
                           ['preconditioning.ti3', 'preconditioning.icc'],
                           29],
                          ['reports', ['reports/report_1.json'], 21],
                          ['exports',
                           ['exports/preconditioning-i1profiler.txt'],
                           22]]}


STEMS = ("merged", "preconditioning", "calibrated", "P")


def _layout(tmp_path: Path, stem: str):
    proj = Project.create(tmp_path / stem, stem)
    run = proj.current_run()
    run.ensure_dir()
    for i, n in enumerate(NAMES):
        p = run.dir / n.format(s=run.stem)
        p.parent.mkdir(exist_ok=True)
        if not p.exists():
            p.write_bytes(b"x" * (10 + i))
    return proj, run


@pytest.mark.parametrize("groups", [None, ("profile", "refinement")],
                         ids=["whole-run", "profile+refinement"])
@pytest.mark.parametrize("stem", STEMS)
def test_the_plan_is_4316s_for_a_stem_two_groups_share(tmp_path, stem, groups):
    proj, run = _layout(tmp_path, stem)
    got = [[g, [str(p.relative_to(run.dir)) for p in fs], n]
           for g, fs, n in proj.duplicate_run_plan(run, groups)]
    assert got == EXPECTED[f"{stem} {groups}"]


def test_a_shared_file_is_copied_once_as_in_4316(tmp_path):
    proj, run = _layout(tmp_path, "merged")
    new = proj.duplicate_run(run)
    assert (new.dir / "merged.ti3").read_bytes() == (
        run.dir / "merged.ti3").read_bytes()


@pytest.mark.skipif(sys.platform != "darwin",
                    reason="APFS is the filesystem that finds a decomposed "
                           "name by its composed spelling")
def test_a_stale_turned_order_spelled_decomposed_is_not_copied(tmp_path):
    src = _chart(tmp_path / "src", "Src", 350)
    proj = Project.create(tmp_path / "Café", "Café")
    run = proj.current_run()
    run.ensure_dir()
    st = run.stem
    for f in src.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, run.dir / (st + f.name[3:]))
    t = run.chart_ti2.read_text(encoding="utf-8")
    run.chart_ti2.write_text(t.replace('DESCRIPTOR "', 'DESCRIPTOR "X ', 1),
                             encoding="utf-8")
    T.write_turned_export(run.chart_ti2, run.exports_dir, st)
    (run.exports_dir / f"{st}-i1profiler.txt").write_text("x")
    shutil.copy2(src, run.chart_ti2)            # the order is now stale
    for p in list(run.exports_dir.iterdir()):   # spelled as HFS+ spells it
        tmp = p.with_name("tmp_" + p.name)
        p.rename(tmp)
        tmp.rename(p.with_name(unicodedata.normalize("NFD", p.name)))
    names = os.listdir(run.exports_dir)
    assert all(n != unicodedata.normalize("NFC", n) for n in names), names
    assert T.turned_order_for(run.chart_ti2) is None

    plan = {g: [p.name for p in fs] for g, fs, _ in proj.duplicate_run_plan(run)}
    turned = [n for fs in plan.values() for n in fs if "turned" in n]
    assert turned == []
    # The ordinary export beside it is still copied, as in 4.3.16.
    assert [unicodedata.normalize("NFC", n) for n in plan["exports"]] == [
        f"{st}-i1profiler.txt"]
    new = proj.duplicate_run(run)
    assert not [p for p in new.dir.rglob("*") if "turned" in p.name]
