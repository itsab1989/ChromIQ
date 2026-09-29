"""B8-955 (beta 41): a recorded folder that still holds a project is read as
that project, whichever namesake step could have claimed it.

B8-926 put the ``still_there`` guard in front of step 3c only (the one
project in the ChromIQ folder that answers to the recorded name). Steps 3
(a project of the recorded name BESIDE a home) and 3b (the one project
beside a home that answers to it, e.g. a Finder "Q copy" whose target_name
is still Q) ran before it, so a report across P and Q (Q kept outside the
ChromIQ folder, K30) read Q's dates from a copy of Q beside P while the real
Q was still where the report names it. Measured by
~/Desktop/ChromIQ-beta40-proof/second-check/tools/p1_resolve_probe.py
(p1-result.txt: cases A and B answered with the copy).

MUTATION, proven red (~/Desktop/ChromIQ-beta41-proof/small-fixes/): move
the ``still_there`` early return back below step 3b.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                    # noqa: E402

from tests.test_calibration_reports import _settings, _window    # noqa: E402
from tests.test_challenge_c_report_files import qapp, said       # noqa: E402
from tests.test_g7_reports_across_places import (                # noqa: E402
    _new_report_of_everything, _press, _project, _reports)

assert qapp and said


def _mk(root: Path, folder: str, target: str | None = None,
        rel: str = "runs/run1") -> Path:
    p = root / folder
    (p / rel).mkdir(parents=True)
    (p / "project.json").write_text(
        json.dumps({"schema_version": 2, "target_name": target or folder}),
        encoding="utf-8")
    return p


@pytest.fixture
def chromiq_folder_is(monkeypatch):
    import workflow.measurement_report as mr

    def _set(path):
        monkeypatch.setattr(mr, "chromiq_folder", lambda: path)
    return _set


def test_a_copy_that_answers_to_the_name_beside_the_home_loses(
        tmp_path, chromiq_folder_is):
    """Step 3b: "Q copy" (target_name Q) beside P; Q still outside."""
    from workflow.measurement_report import resolve_recorded_folder
    cq = tmp_path / "cq"
    p = _mk(cq, "P")
    q = _mk(tmp_path / "away", "Q")
    _mk(cq, "Q copy", target="Q")
    chromiq_folder_is(cq)
    assert resolve_recorded_folder(q / "runs/run1", [p]) == q / "runs/run1"


def test_a_copy_named_like_it_beside_the_home_loses(tmp_path,
                                                    chromiq_folder_is):
    """Step 3: a project folder named Q beside P; Q still outside."""
    from workflow.measurement_report import resolve_recorded_folder
    cq = tmp_path / "cq"
    p = _mk(cq, "P")
    q = _mk(tmp_path / "away", "Q")
    _mk(cq, "Q")
    chromiq_folder_is(cq)
    assert resolve_recorded_folder(q / "runs/run1", [p]) == q / "runs/run1"


def test_a_gone_recorded_folder_still_finds_the_namesakes(
        tmp_path, chromiq_folder_is):
    """Steps 3 and 3b are kept for a recorded folder that is gone."""
    from workflow.measurement_report import resolve_recorded_folder
    cq = tmp_path / "cq"
    p = _mk(cq, "P")
    chromiq_folder_is(cq)
    gone = tmp_path / "away" / "Q" / "runs/run1"
    renamed = _mk(cq, "Q2", target="Q")
    assert resolve_recorded_folder(gone, [p]) == renamed / "runs/run1"
    beside = _mk(cq, "Q")
    assert resolve_recorded_folder(gone, [p]) == beside / "runs/run1"


def test_the_window_reads_the_recorded_project_not_the_copy_beside(
        tmp_path, qapp, said, chromiq_folder_is):
    """On the window: P in the ChromIQ folder, Q outside it, one report
    across both, then a Finder copy "Q copy" of Q put beside P. P's window
    loads Q's date from Q."""
    cq = tmp_path / "cq"
    cq.mkdir()
    chromiq_folder_is(cq)
    _p, _pr, pv = _project(cq, "P")
    away = tmp_path / "away"
    away.mkdir()
    q, _qr, qv = _project(away, "Q")
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        dlg._ask_update_or_create_new = lambda: "new"
        dlg._add_source(qv.measurement_ti3)
        qapp.processEvents()
        _new_report_of_everything(dlg, qapp)
        _press(dlg, qapp)
    finally:
        dlg.close()
    assert len(_reports(cq / "reports")) == 1
    twin = cq / "Q copy"
    shutil.copytree(q.root, twin)
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        assert dlg._loaded_doc_id, "the window did not open on the report"
        origins = {str(x.get("_origin_dir") or "") for x in dlg._history}
    finally:
        dlg.close()
    assert any(o.startswith(str(q.root)) for o in origins), origins
    assert not any(o.startswith(str(twin)) for o in origins), origins


def test_a_copied_pack_still_reads_its_own_copy(tmp_path, chromiq_folder_is):
    """K25 kept: P and Q copied together (the originals kept): the home's
    original stands beside the recorded Q, so the copy's own Q is meant."""
    from workflow.measurement_report import resolve_recorded_folder
    _mk(tmp_path, "P")
    q = _mk(tmp_path, "Q")
    moved = tmp_path / "moved"
    p2 = _mk(moved, "P")
    q2 = _mk(moved, "Q")
    chromiq_folder_is(moved)
    assert resolve_recorded_folder(q / "runs/run1", [p2]) == q2 / "runs/run1"
