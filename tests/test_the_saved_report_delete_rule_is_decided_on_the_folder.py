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
    # B8-380: the button acts on a DOCUMENT, which may be several files, so it
    # asks `_delete_refusal_for`; that method's whole body is the same rule
    # applied to each of the document's files in turn with
    # `_saved_delete_refusal`, and the test below pins it.
    assert "_delete_refusal_for" in calls, "the refusal is no longer consulted"
    assert "_reload_sources" in calls, (
        "a refused delete must re-read the folder so the row can show why")
    # …and the refusal must not be answered by falling straight out.
    head = src.split("_delete_refusal_for", 1)[1]
    assert "_reload_sources" in head.split("members =", 1)[0], (
        "the refusal branch returns without telling the reader anything")
    per_file = inspect.getsource(MeasurementReportDialog._delete_refusal_for)
    assert "_saved_delete_refusal" in per_file, (
        "the document-level refusal no longer asks the per-file rule")


def test_a_file_the_window_cannot_read_is_not_a_spare(dated_verification):
    """The fix above, driven on screen, had widened the rule it tightened.

    `_gather_runs` reads every `report_*.json` with `json.loads` and skips the
    ones that raise, so a file that is not readable JSON is in no row, no
    selector and no trend. A bare `glob` counted it as a spare all the same,
    and combined round 3 photographed the consequence: on a dated verification
    holding one good report and one truncated one, Delete came up ENABLED with
    no reason beside it, the confirmation said *"0 saved reports of it are left
    afterwards"*, and the press left the date with no verdict the window can
    read. `save_report` writes with `write_text`, which is not atomic, so a
    process killed mid-write leaves exactly that file.

    MUTATION, PROVED TO LAND: drop the `json.loads` test from
    `_saved_delete_refusal` and count `glob("report_*.json")` again -- this
    goes red with an empty refusal while every other test in this file stays
    green.
    """
    broken = dated_verification / "reports" / "report_2026-06-24_16-40-00_2.json"
    broken.write_text('{"created": "2026-06-2', encoding="utf-8")   # cut short
    why = _refusal(_row(dated_verification, 1),
                   "report_2026-06-24_16-40-00.json")
    assert why, (
        "a report_*.json the window cannot read was counted as a spare, and "
        "the only readable verdict of the date became deletable")

    # …and an empty file, which is what a full disk leaves behind.
    broken.write_text("", encoding="utf-8")
    assert _refusal(_row(dated_verification, 1),
                    "report_2026-06-24_16-40-00.json"), (
        "a zero-byte report_*.json was counted as a spare")

    # Guard the guard: a READABLE second report is still a spare.
    broken.write_text(json.dumps({"created": "2026-06-24T16:40:00"}),
                      encoding="utf-8")
    assert not _refusal(_row(dated_verification, 2), broken.name), (
        "the rule now refuses everything; a real spare must stay deletable")


#: The app's own packages. A driver may legitimately open two of these windows
#: at once -- round 2's did -- so `scripts/` and `tests/` are not doors.
_DOOR_ROOTS = ("ui", "core", "workflow", "main.py")

#: Where the window is DEFINED, which is not a door.
_THE_WINDOW = pathlib.Path("ui") / "dialogs" / "measurement_report_dialog.py"


def _door_files():
    """Every app file that CONSTRUCTS a `MeasurementReportDialog`.

    **FOUND, NOT LISTED.** The first cut of this test named two files in a
    tuple and asserted the tuple had two entries in it, which pins the two
    doors that exist and says nothing whatever about a third. The safety
    argument of the rule above used to rest entirely on this modality, so the
    one thing this must catch is a door somebody adds LATER, in a file no
    tuple here mentions.
    """
    out = {}
    for rel in _DOOR_ROOTS:
        base = ROOT / rel
        paths = [base] if base.is_file() else sorted(base.rglob("*.py"))
        for path in paths:
            if path.relative_to(ROOT) == _THE_WINDOW:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            made = [n for n in ast.walk(tree)
                    if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id == "MeasurementReportDialog"]
            if made:
                out[path.relative_to(ROOT).as_posix()] = (tree, made)
    return out


def test_the_doors_are_found_and_not_merely_listed():
    """Guard the guard: a search that finds no door would pass for ever."""
    doors = _door_files()
    made = sum(len(v[1]) for v in doors.values())
    assert made >= 5, f"only {made} constructions found; the search is broken"
    assert set(doors) == {"ui/tabs/tab_measure.py",
                          "ui/dialogs/tools_dialogs.py"}, sorted(doors)


def test_every_door_opens_the_report_window_modally():
    """The assumption the snapshot used to rest on, written down at last.

    Two of these windows open at once is what turned a stale list into a lost
    verdict. They cannot be, because every door calls `exec()`; the rule above
    no longer depends on that, and this still says so, because a report window
    somebody makes modeless later is a reasonable thing to want and would put
    two of them on screen without anyone connecting it to a delete.

    MUTATION: change any `.exec()` on one of these to `.show()` and this goes
    red naming the file, and a door added in a file nothing here mentions is
    checked too, because `_door_files` goes and finds them.
    """
    bad = []
    for rel, (tree, made) in _door_files().items():
        for node in made:
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
