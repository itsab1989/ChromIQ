"""B8-926 (beta 40): a recorded folder that still holds a project is read as
that project, never as a namesake elsewhere in the ChromIQ folder.

`workflow.measurement_report.resolve_recorded_folder` step 3c (B8-919)
searched the ChromIQ folder, top level and one level down, for the ONE
project that answers to the recorded name, and took it BEFORE it looked at
the recorded folder. A report across P (in the ChromIQ folder) and Q (kept
outside it, K30) therefore read Q's dates from a copy of Q in
``<ChromIQ folder>/Group/`` while the real Q was still where the report
names it. The rewrite side (`core.report_refs.refers_here`) already refused
such a reference; the read side now agrees: step 3c only when the recorded
folder is gone, and only when exactly one candidate answers.

MUTATION, proven red (REPORT in ~/Desktop/ChromIQ-beta40-proof/small-fixes/):
delete the ``still_there`` early return in step 3c.
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


def _mk(root: Path, name: str, rel: str = "runs/run1") -> Path:
    p = root / name
    (p / rel).mkdir(parents=True)
    (p / "project.json").write_text(
        json.dumps({"schema_version": 2, "target_name": name}),
        encoding="utf-8")
    return p


@pytest.fixture
def chromiq_folder_is(monkeypatch):
    import workflow.measurement_report as mr

    def _set(path):
        monkeypatch.setattr(mr, "chromiq_folder", lambda: path)
    return _set


def test_the_recorded_project_wins_over_one_namesake(tmp_path,
                                                     chromiq_folder_is):
    """Q still where the report names it, one copy of Q in a sub-folder of
    the ChromIQ folder: the reading is Q's own folder."""
    from workflow.measurement_report import resolve_recorded_folder
    cq = tmp_path / "cq"
    p = _mk(cq, "P")
    q = _mk(tmp_path / "away", "Q")
    twin = _mk(cq / "Group", "Q")
    chromiq_folder_is(cq)
    got = resolve_recorded_folder(q / "runs/run1", [p])
    assert got == q / "runs/run1", got
    assert twin not in Path(str(got)).parents


def test_a_gone_recorded_folder_still_finds_the_one_namesake(
        tmp_path, chromiq_folder_is):
    """B8-919 is kept: the recorded folder gone, the one project that
    answers to the name is taken; two that answer are neither."""
    from workflow.measurement_report import resolve_recorded_folder
    cq = tmp_path / "cq"
    p = _mk(cq, "P")
    moved = _mk(cq / "Group", "Q")
    chromiq_folder_is(cq)
    gone = tmp_path / "away" / "Q" / "runs/run1"
    assert resolve_recorded_folder(gone, [p]) == moved / "runs/run1"
    _mk(cq / "Other", "Q")
    assert resolve_recorded_folder(gone, [p]) == gone


def test_the_window_reads_the_recorded_project_not_its_copy(
        tmp_path, qapp, said, chromiq_folder_is):
    """On the window: P in the ChromIQ folder, Q outside it, one report
    across both (in ``<ChromIQ folder>/reports``), then a Finder copy of Q
    put in ``<ChromIQ folder>/Group/``. P's window loads Q's date from Q."""
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
    (cq / "Group").mkdir()
    twin = cq / "Group" / "Q"
    shutil.copytree(q.root, twin)
    dlg = _window(_settings(), pv.measurement_ti3, qapp, "verification")
    try:
        assert dlg._loaded_doc_id, "the window did not open on the report"
        origins = {str(x.get("_origin_dir") or "") for x in dlg._history}
    finally:
        dlg.close()
    assert any(o.startswith(str(q.root)) for o in origins), origins
    assert not any(o.startswith(str(twin)) for o in origins), origins
