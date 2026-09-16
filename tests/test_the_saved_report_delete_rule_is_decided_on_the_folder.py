"""The only saved report of a dated verification is kept, and not by luck.

§5 of `docs/design/measurement_report_limits.md` says a dated verification's
last saved report stays: every date of a run is judged the same way, and a date
whose report is gone has no recorded verdict at all. The window would then grade
it live against today's numbers, which is the one thing the lock exists to
prevent.

WHAT COMBINED ROUND 2 DROVE, AND WHAT IT FOUND
----------------------------------------------
`_saved_delete_refusal` implemented that rule by counting `_all_report_files`,
a list filled when the window GATHERED its sources and refreshed only by
`_reload_sources`. So the rule was decided on a snapshot.

Two `MeasurementReportDialog` windows were opened on one dated verification
that really did hold two saved reports of one measurement. The second window
deleted the spare. The first window was then asked to delete the other one
WITHOUT touching its selector -- a re-pick is the one action that re-reads the
folder, and a person who has already chosen the report they want does not make
it. The first window still believed there was a spare, the refusal did not
fire, and the date's `reports/` folder was left EMPTY, under a confirmation
that said *"One saved report of it is left afterwards"*. Driven on screen and
photographed in `~/Desktop/ChromIQ-beta20-proof/combined-round-2/`
(`W3-A-on-the-last-report.png`, `W4-after-A-tried.png`).

**Nothing shipped that way**, and the reason is the last test in this file:
every door that opens this window opens it with `exec()`, so a person cannot
have two of them at once. That was the only thing making the snapshot safe and
it was written down nowhere. Both halves are pinned here: the rule now asks the
folder it is about to write in, and the modality that used to carry it cannot
change in silence either.
"""
from __future__ import annotations

import ast
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _row(date_dir: pathlib.Path, claims: int) -> dict:
    """A history row as `_gather_runs` builds one, claiming *claims* files."""
    return {
        "_origin_dir": str(date_dir),
        "_all_report_files": [f"report_2026-06-24_16-40-0{i}.json"
                              for i in range(claims)],
    }


def _refusal(row: dict, name: str) -> str:
    """`_saved_delete_refusal` uses no instance state, so it is asked directly
    rather than through a window that costs two seconds to build."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog._saved_delete_refusal(None, row, name)


@pytest.fixture()
def dated_verification(tmp_path):
    """A run with one dated verification holding ONE saved report."""
    from core.file_manager import VERIFICATIONS_DIRNAME
    d = tmp_path / "runs" / "run2" / VERIFICATIONS_DIRNAME / "2026-06-24_164000"
    (d / "reports").mkdir(parents=True)
    p = d / "reports" / "report_2026-06-24_16-40-00.json"
    p.write_text(json.dumps({"created": "2026-06-24T16:40:00"}), encoding="utf-8")
    return d


def test_the_last_report_of_a_dated_verification_is_kept(dated_verification):
    """The plain case, which always worked: one file, one refusal."""
    why = _refusal(_row(dated_verification, 1),
                   "report_2026-06-24_16-40-00.json")
    assert why, "the last saved report of a dated verification was not protected"
    assert "kept" in why


def test_a_spare_on_disk_still_lets_a_report_go(dated_verification):
    """Guard the guard: the rule must not refuse everything."""
    spare = dated_verification / "reports" / "report_2026-06-24_16-40-00_2.json"
    spare.write_text("{}", encoding="utf-8")
    assert not _refusal(_row(dated_verification, 2),
                        "report_2026-06-24_16-40-00_2.json"), (
        "with two reports on disk the spare must still be deletable")


def test_the_rule_is_decided_on_the_folder_and_not_on_a_stale_list(
        dated_verification):
    """The fault, reduced to its mechanism.

    The row claims TWO report files, exactly as a window that gathered its
    sources before another one deleted the spare. The folder holds ONE. The
    date's record must survive the disagreement.

    MUTATION, PROVED TO LAND: put
    ``spares = len(r.get("_all_report_files") or [])`` back in
    `_saved_delete_refusal` in place of the folder count and this test goes
    red with an empty refusal, while the two tests above stay green -- which
    is why they are not enough on their own.
    """
    row = _row(dated_verification, 2)          # the window's stale memory
    on_disk = sorted(p.name for p in
                     (dated_verification / "reports").glob("report_*.json"))
    assert len(on_disk) == 1, on_disk          # the truth, read back
    why = _refusal(row, on_disk[0])
    assert why, (
        "a window whose list is one delete out of date was allowed to remove "
        "the last saved report of a dated verification")


def test_a_refused_delete_re_reads_instead_of_doing_nothing():
    """A refusal a reader cannot see is a button that does nothing.

    Now that the rule asks the folder, it can fire on a row whose Delete is
    still live because the window has not re-read since. `_on_delete_report`
    must catch the window up rather than return in silence, so the button
    greys and the row shows the reason in the words it already uses.

    MUTATION: make the refusal branch a bare `return` and this goes red.
    """
    import inspect
    import textwrap

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._on_delete_report)
    tree = ast.parse(textwrap.dedent(src))
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "_saved_delete_refusal" in calls, "the refusal is no longer consulted"
    assert "_reload_sources" in calls, (
        "a refused delete must re-read the folder so the row can show why")
    # …and the refusal must not be answered by falling straight out.
    head = src.split("_saved_delete_refusal", 1)[1]
    assert "_reload_sources" in head.split("path =", 1)[0], (
        "the refusal branch returns without telling the reader anything")


#: Every place in the app that opens the Measurement Report window.
_DOORS = ("ui/tabs/tab_measure.py", "ui/dialogs/tools_dialogs.py")


def test_every_door_opens_the_report_window_modally():
    """The assumption the snapshot used to rest on, written down at last.

    Two of these windows open at once is what turned a stale list into a lost
    verdict. They cannot be, because every door calls `exec()`; the rule above
    no longer depends on that, and this still says so, because a report window
    somebody makes modeless later is a reasonable thing to want and would put
    two of them on screen without anyone connecting it to a delete.

    MUTATION: change any `.exec()` on one of these to `.show()` and this goes
    red naming the file.
    """
    bad = []
    for rel in _DOORS:
        path = ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "MeasurementReportDialog"):
                continue
            # …either `MeasurementReportDialog(...).exec()`, or bound to a
            # name that is `exec()`ed in the same module.
            chained = any(
                isinstance(p, ast.Call) and isinstance(p.func, ast.Attribute)
                and p.func.attr == "exec" and p.func.value is node
                for p in ast.walk(tree))
            bound = [a for a in ast.walk(tree)
                     if isinstance(a, ast.Assign) and a.value is node
                     and len(a.targets) == 1
                     and isinstance(a.targets[0], ast.Name)]
            execed = False
            if bound:
                nm = bound[0].targets[0].id
                execed = any(
                    isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and c.func.attr == "exec"
                    and isinstance(c.func.value, ast.Name)
                    and c.func.value.id == nm
                    for c in ast.walk(tree))
            if not (chained or execed):
                bad.append(f"{rel}:{node.lineno}")
    assert not bad, (
        "these open the Measurement Report window without exec(), so two of "
        "them can be on screen at once: " + ", ".join(bad))
    assert len(_DOORS) == 2
