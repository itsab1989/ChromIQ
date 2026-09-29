"""Re-challenge R1 of beta 39, #6: a report across projects finds the other
project after it moved into a sub-folder of the ChromIQ folder.

Measured on screen (``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-
behaviour/k30``, K5 and K6): Report-Limits-Report-Folders-Second moved into
``Group/`` (§24.4 allows projects in sub-folders of the ChromIQ folder). The
report across the two projects then loaded 1 of its 2 dates with no note,
and Generate said "Nothing was changed". `resolve_recorded_folder` looked
only BESIDE the report's projects; step 3c now searches the ChromIQ folder
and its sub-folders for the ONE project that answers to the recorded name.

Every test names its mutation; each was run red (REPORT.md in
``~/Desktop/ChromIQ-beta39-proof/rechallenge-R1-fixes/``).
"""
from __future__ import annotations

import os
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                    # noqa: E402

from tests.test_calibration_reports import _settings, _window    # noqa: E402
from tests.test_challenge_c_report_files import (                # noqa: E402
    _across, _update_from, qapp, said)
from tests.test_g7_reports_across_places import _snapshot        # noqa: E402

assert qapp and said


@pytest.fixture
def chromiq_folder_is(monkeypatch):
    import workflow.measurement_report as mr

    def _set(path):
        monkeypatch.setattr(mr, "chromiq_folder", lambda: path)
    return _set


def _origins(ti3, qapp, *, ticked=False):
    dlg = _window(_settings(), ti3, qapp, "verification")
    try:
        assert dlg._loaded_doc_id, "the window did not open on a report"
        rows = dlg._runs_for_report() if ticked else dlg._history
        return {str(x.get("_origin_dir") or "") for x in rows}
    finally:
        dlg.close()


def test_a_project_moved_into_a_group_folder_is_still_covered(
        tmp_path, qapp, said, chromiq_folder_is):
    """Q moved into ``<ChromIQ folder>/Group/``: P's window loads BOTH dates
    of the report across P and Q, and an Update from P's side is not
    refused (nothing is lost).

    MUTATION, proven red: remove step 3c from `resolve_recorded_folder`
    (P's window holds P's date alone, and the Update is refused as
    M-REPORT-UPDATE-NOT-FOUND); and, separately, make
    `_recorded_keys_where_they_are_now` return ``set()`` (Q's date is
    loaded and left unticked, which is what the tester's window showed)."""
    from workflow import measurement_messages as M
    chromiq_folder_is(tmp_path)
    p, pv, q, qv, _doc = _across(tmp_path, qapp)
    (tmp_path / "Group").mkdir()
    moved = tmp_path / "Group" / "Q"
    shutil.move(str(q.root), str(moved))
    origins = _origins(pv.measurement_ti3, qapp)
    assert any(o.startswith(str(moved)) for o in origins), origins
    assert any(o.startswith(str(p.root)) for o in origins), origins
    # ...and BOTH are ticked: the report is shown whole, as it was written
    ticked = _origins(pv.measurement_ti3, qapp, ticked=True)
    assert any(o.startswith(str(moved)) for o in ticked), ticked
    assert any(o.startswith(str(p.root)) for o in ticked), ticked
    _update_from(pv.measurement_ti3, qapp)
    refused = M.CATALOGUE["M-REPORT-UPDATE-NOT-FOUND"].render(missing="")[0]
    assert not [x for _k, t, x in said if t == refused], said


def test_two_projects_answering_to_the_name_are_neither(
        tmp_path, qapp, said, chromiq_folder_is):
    """Q moved into ``Group/`` and a copy of it put in ``Other/``: the name
    is ambiguous, so neither is taken; the Update is refused, with nothing
    written, as for a project that cannot be found.

    MUTATION, proven red: in `resolve_recorded_folder` step 3c take
    ``found[0]`` whenever ``found`` is not empty (the report is filled from
    whichever copy sorts first)."""
    from workflow import measurement_messages as M
    chromiq_folder_is(tmp_path)
    p, pv, q, qv, _doc = _across(tmp_path, qapp)
    (tmp_path / "Group").mkdir()
    (tmp_path / "Other").mkdir()
    shutil.copytree(q.root, tmp_path / "Other" / "Q")
    shutil.move(str(q.root), str(tmp_path / "Group" / "Q"))
    origins = _origins(pv.measurement_ti3, qapp)
    assert not any("/Group/" in o or "/Other/" in o for o in origins), origins
    before = _snapshot(tmp_path)
    _update_from(pv.measurement_ti3, qapp)
    assert _snapshot(tmp_path) == before
    refused = M.CATALOGUE["M-REPORT-UPDATE-NOT-FOUND"].render(missing="")[0]
    assert [x for _k, t, x in said if t == refused], said
