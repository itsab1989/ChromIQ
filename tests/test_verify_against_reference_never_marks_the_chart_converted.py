"""Tools > Verify against reference must not write `<stem>-reference.ti3`
beside the measurement it checks (W review, 4.3.3-beta.3).

Beside a run's `<stem>.ti3` sits the run's chart `<stem>.ti2`, and
`<stem>-reference.ti3` beside THAT is `colorimetric_reference_for(<stem>.ti2)`:
the FROM PROFILE GAMUT marker. The tool wrote its reference there whenever no
3D map was asked for, and from then on the run's Measurement Report judged the
run against the values typed into this tool (measured on a copy of
Demo-Full-RGB run1: 240 patches at avg dE00 21.3 became 24 patches at 43.4,
reference source "colorimetric") and the chart counted as already converted
through the profile.

The reference is this check's input only, so it is staged with the 3D map's
staging folder and removed with it when the window closes.

MUTATION: put back `ref_path = self._measured.parent / f"{stem}-reference.ti3"`
for the no-map branch, and every assertion below about the run's folder is red.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_182_b_inspect_saves_into_the_owners_reports import (  # noqa: E402
    _TI3,
)
from tests.test_profile_tools import _Settings  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("want_plot", [False, True])
def test_the_reference_is_staged_and_the_runs_chart_stays_regular(
        tmp_path, qapp, want_plot):
    from core.file_manager import Project
    from ui.dialogs.tools_dialogs import VerifyAgainstReferenceDialog
    from workflow.colverify_runner import ColverifyRunner
    from workflow.verification_print import (STATE_REGULAR,
                                             chart_conversion_state,
                                             colorimetric_reference_for)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    ti3 = run.dir / "P.ti3"
    ti3.write_text(_TI3, encoding="utf-8")
    ti2 = run.dir / "P.ti2"
    ti2.write_text(_TI3.replace("CTI3", "CTI2", 1), encoding="utf-8")
    assert chart_conversion_state(ti2) == STATE_REGULAR
    before = sorted(p.name for p in run.dir.iterdir())

    seen = {}
    log = "  Total errors (CIEDE2000):     peak = 3.000000, avg = 1.000000\n"

    def _run(params, on_line, on_finish):
        seen["ref"] = Path(params.ref_ti3)
        seen["ref_existed"] = Path(params.ref_ti3).is_file()
        on_finish(0)

    dlg = VerifyAgainstReferenceDialog(
        SimpleNamespace(is_running=False), _Settings())
    dlg._measured = ti3
    dlg._chart = None
    dlg._ref_edit.setPlainText("1 90 0 0\n2 50 0 0\n3 5 0 0\n")
    dlg._vrml_cb.setChecked(want_plot)
    dlg._cv = SimpleNamespace(
        run=_run,
        parse_results=lambda: ColverifyRunner(None).parse_results(log))
    try:
        dlg._execute()
        # colverify was handed a real reference, outside the project
        assert seen.get("ref_existed"), seen
        assert run.dir not in seen["ref"].parents, seen["ref"]
        assert Path(proj.root) not in seen["ref"].parents, seen["ref"]
    finally:
        dlg.close()
        dlg.done(0)
    # nothing written beside the measurement but the report in reports/
    assert not colorimetric_reference_for(ti2).exists(), \
        sorted(p.name for p in run.dir.iterdir())
    after = sorted(p.name for p in run.dir.iterdir())
    assert set(after) - set(before) <= {"reports"}, (before, after)
    assert chart_conversion_state(ti2) == STATE_REGULAR
    assert (run.dir / "reports" / "Verify_Reference_1_P.txt").is_file()
    # the staged reference goes with the window
    assert not seen["ref"].exists(), seen["ref"]
