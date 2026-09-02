"""A project broken by the pre-4.1.3-beta.16 stem bug is repaired when opened.

Suggested path: tests/test_a_broken_project_repairs_its_own_names.py

THE FIXTURE IS PRODUCED BY THE REAL BUG, NOT HAND-FAKED. The old derivation
(`Path(out_base).with_suffix("")`, from `git show 8b3ca95b^ --
workflow/layout_engine/chart.py`) is monkeypatched back into the real
`build_chart`, which then writes real bytes under the truncated stem. Faking the
filenames risks getting the bug's own output wrong — which is how a repair
passes its tests and does nothing useful in the field.

Each test names, in its docstring, what it is RED against.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from core.file_manager import Project, Run
from core.name_repair import plan_for_folder
from core.resource_path import resource_path
from workflow.layout_engine import chart as le_chart

_TI1 = "assets/charts/knut/rgb/fulllayout/fls_i1pro_a4_484p_1page_portrait/chart.ti1"
DOTTED = "X-A4-484p-w10.0mm"
TRUNC = "X-A4-484p-w10"


def _tree(root: Path) -> dict[str, str]:
    """relative path -> sha256, for every file. The only honest "nothing was
    lost" check: a rename must preserve the multiset of content hashes."""
    return {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(root.rglob("*")) if f.is_file()}


def _build(root: Path, name: str, *, broken: bool, cal: bool = False) -> Path:
    proj = Project.create(root / name, name)
    run = proj.current_run()
    run.ensure_dir()
    folder, stem = run.dir, run.stem
    if cal:
        folder, stem = proj.calibration.ensure_dir(), proj.calibration.stem
    shutil.copy2(resource_path(_TI1), folder / f"{stem}.ti1")
    keep = (le_chart.without_ext, le_chart.artefact)
    if broken:
        le_chart.without_ext = lambda p, ext: Path(p).with_suffix("")
        le_chart.artefact = lambda s, ext: Path(s).with_suffix(ext)
    try:
        le_chart.build_chart(str(folder / f"{stem}.ti1"), str(folder / stem),
                             instrument="i1", paper="A4", dpi=100, seed=7)
    finally:
        le_chart.without_ext, le_chart.artefact = keep
    return root / name


@pytest.fixture
def broken_dotted(tmp_path):
    """A project broken EXACTLY the way the pre-fix code broke one."""
    p = _build(tmp_path, DOTTED, broken=True)
    run = p / "runs" / "run1"
    assert (run / f"{DOTTED}.ti1").is_file(), "the .ti1 must carry the FULL name"
    assert (run / f"{TRUNC}.ti2").is_file(), \
        "the fixture did not reproduce the bug — the .ti2 is not truncated"
    assert not (run / f"{DOTTED}.ti2").exists()
    return p


# ---------------------------------------------------------------- the point

def test_a_broken_project_is_repaired_when_opened(broken_dotted):
    """RED before the fix: chart_ti2 False, chart_tiffs() empty — the project
    cannot be measured at all, which is the whole reported symptom."""
    before = _tree(broken_dotted)
    run = Project.load(broken_dotted).current_run()
    assert run.chart_ti2.is_file()
    assert len(run.chart_tiffs()) == 2
    assert (run.dir / f"{DOTTED}.strips.json").is_file()
    after = _tree(broken_dotted)
    assert sorted(before.values()) == sorted(
        v for k, v in after.items() if k != "name-repair.json"), \
        "a rename must preserve every byte of every file"


def test_nothing_is_left_behind_under_the_truncated_name(broken_dotted):
    Project.load(broken_dotted)
    left = [f.name for f in (broken_dotted / "runs" / "run1").iterdir()
            if f.name.startswith(TRUNC) and not f.name.startswith(DOTTED)]
    assert left == []


def test_the_repair_is_idempotent(broken_dotted, monkeypatch):
    """The second open must perform ZERO renames — asserted on a spy over
    Path.rename, not just on the end state, which is identical either way."""
    Project.load(broken_dotted)
    calls = []
    real = Path.rename
    monkeypatch.setattr(Path, "rename",
                        lambda self, t: (calls.append(self), real(self, t))[1])
    Project.load(broken_dotted)
    assert calls == []


# ------------------------------------------------------- the controls

def test_a_clean_dotted_project_is_untouched(tmp_path):
    """RED against any implementation that finds candidates by globbing
    `<trunc>*` — `X-A4-484p-w10*` matches `X-A4-484p-w10.0mm.ti1`, so a glob
    renames the CORRECT files into `…0mm.0mm.ti1`-shaped garbage.
    To prove this test can see that, replace the whitelist in
    core/name_repair.py with `folder.glob(f"{trunc}*")` and watch it fail."""
    p = _build(tmp_path, DOTTED, broken=False)
    before = _tree(p)
    Project.load(p)
    assert _tree(p) == before


def test_a_clean_undotted_project_is_untouched(tmp_path):
    p = _build(tmp_path, "X-A4-484p-no-dots", broken=False)
    before = _tree(p)
    Project.load(p)
    assert _tree(p) == before


def test_an_undotted_project_costs_no_syscall(tmp_path, monkeypatch):
    """The repair runs on every target switch (measured: 3 loads for 4
    switches), so a project that cannot be affected must not be stat-ed."""
    p = _build(tmp_path, "X-A4-484p-no-dots", broken=False)
    import core.name_repair as nr
    seen = []
    monkeypatch.setattr(nr, "_journal_path",
                        lambda root: (seen.append(root), Path(root) / "x")[1])
    monkeypatch.setattr(nr, "_folders", lambda proj: seen.append("folders") or [])
    Project.load(p)
    assert seen == [], "the fast path did not fire for an undotted project"


# ---------------------------------------------- the false positives

def test_a_forged_fingerprint_in_a_healthy_run_changes_nothing(tmp_path):
    """RED against the §D5 two-gate detection (`<full>.ti1` present +
    destination absent), which has no `<full>.ti2` check and would rename the
    user's own file."""
    p = _build(tmp_path, DOTTED, broken=False)
    run = p / "runs" / "run1"
    (run / f"{TRUNC}.ti2").write_bytes(b"USER FILE - DO NOT TOUCH")
    (run / f"{TRUNC}.strips.json").write_text("{}", encoding="utf-8")
    before = _tree(p)
    Project.load(p)
    assert _tree(p) == before
    assert (run / f"{TRUNC}.ti2").read_bytes() == b"USER FILE - DO NOT TOUCH"


def test_without_the_fingerprint_nothing_is_repaired(broken_dotted):
    """Fail safe: a user who deleted .strips.json gets no repair rather than a
    repair decided on weaker evidence."""
    run = broken_dotted / "runs" / "run1"
    (run / f"{TRUNC}.strips.json").unlink()
    before = _tree(broken_dotted)
    Project.load(broken_dotted)
    assert _tree(broken_dotted) == before


def test_a_truncated_ti1_stops_the_repair(broken_dotted):
    """The `<full>.ti1` corroboration is what makes a hand-renamed project
    safe. Without it there is no evidence the folder belongs to a full-named
    project chart at all."""
    run = broken_dotted / "runs" / "run1"
    (run / f"{DOTTED}.ti1").rename(run / f"{TRUNC}.ti1")
    before = _tree(broken_dotted)
    Project.load(broken_dotted)
    assert _tree(broken_dotted) == before


def test_a_folder_renamed_to_add_a_dot_is_not_repaired(tmp_path):
    """THE WORST CASE. A healthy UNDOTTED project whose folder the user renamed
    in Finder to add ".0mm": every file is now `<trunc>.*`, so a design without
    the `<full>.ti1` gate would move the entire chart. RED against dropping it."""
    p = _build(tmp_path, TRUNC, broken=False)
    renamed = p.parent / DOTTED
    p.rename(renamed)
    before = _tree(renamed)
    Project.load(renamed)
    assert _tree(renamed) == before


def test_files_outside_the_whitelist_are_never_touched(broken_dotted):
    run = broken_dotted / "runs" / "run1"
    (run / "notes.txt").write_text("my notes", encoding="utf-8")
    (run / f"{TRUNC}.cie").write_text("USER CIE", encoding="utf-8")     # NOT on the whitelist
    Project.load(broken_dotted)
    assert (run / "notes.txt").read_text(encoding="utf-8") == "my notes"
    assert (run / f"{TRUNC}.cie").read_text(encoding="utf-8") == "USER CIE"


def test_a_nested_project_is_never_entered(tmp_path):
    """RED against rglob. Scope is runs/run*/ and cal/, direct children only."""
    outer = _build(tmp_path, "V4-outer-w10.0mm", broken=True)
    inner = _build(tmp_path, "V4-inner-w10.0mm", broken=True)
    dest = outer / "runs" / "run1" / inner.name
    shutil.move(str(inner), str(dest))
    before = _tree(dest)
    Project.load(outer)
    assert _tree(dest) == before


def test_the_destination_is_never_overwritten(broken_dotted):
    run = broken_dotted / "runs" / "run1"
    (run / f"{DOTTED}.ti2").write_bytes(b"SOMETHING ELSE")
    Project.load(broken_dotted)
    assert (run / f"{DOTTED}.ti2").read_bytes() == b"SOMETHING ELSE"


# ----------------------------------------------------- resume & records

def test_an_interrupted_repair_completes_on_the_next_open(broken_dotted):
    """RED against a run-level gate with no journal: once the .ti2 is renamed
    the run looks fine and the pages stay orphaned for ever."""
    run = broken_dotted / "runs" / "run1"
    moves = plan_for_folder(run, DOTTED)
    assert len(moves) == 4
    (broken_dotted / "name-repair.json").write_text(json.dumps({"repairs": [{
        "state": "planned",
        "moves": [{"from": str(s.relative_to(broken_dotted)),
                   "to": str(d.relative_to(broken_dotted)),
                   "state": "done" if i == 0 else "planned"}
                  for i, (s, d) in enumerate(moves)]}]}), encoding="utf-8")
    moves[0][0].rename(moves[0][1])            # the crash: one move applied
    r = Project.load(broken_dotted).current_run()
    assert r.chart_ti2.is_file() and len(r.chart_tiffs()) == 2


def test_every_rename_is_recorded(broken_dotted):
    Project.load(broken_dotted)
    doc = json.loads((broken_dotted / "name-repair.json").read_text(encoding="utf-8"))
    session = doc["repairs"][-1]
    assert session["state"] == "complete"
    assert len(session["moves"]) == 4
    assert all(m["state"] == "done" for m in session["moves"])
    assert session["how_to_undo"] and session["chromiq_version"]


def test_a_second_repair_does_not_erase_the_first_record(broken_dotted, tmp_path):
    """RED against one-session-per-file journals — an undo record a later run
    can overwrite is not an undo record."""
    Project.load(broken_dotted)
    first = json.loads((broken_dotted / "name-repair.json").read_text(encoding="utf-8"))["repairs"]
    # a second broken build lands in the same project (restored backup, run2)
    run2 = broken_dotted / "runs" / "run2"
    shutil.copytree(broken_dotted / "runs" / "run1", run2)
    for f in list(run2.iterdir()):
        if f.name.startswith(DOTTED) and f.suffix != ".ti1":
            f.rename(run2 / (TRUNC + f.name[len(DOTTED):]))
    Project.load(broken_dotted)
    doc = json.loads((broken_dotted / "name-repair.json").read_text(encoding="utf-8"))["repairs"]
    assert len(doc) == len(first) + 1
    assert doc[0] == first[0], "the first session's record was modified"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_a_read_only_project_root_renames_nothing(broken_dotted):
    """A move ChromIQ cannot record is a move it does not make."""
    before = _tree(broken_dotted)
    os.chmod(broken_dotted, 0o555)
    try:
        Project.load(broken_dotted)          # must not raise
        assert _tree(broken_dotted) == before
    finally:
        os.chmod(broken_dotted, 0o755)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_a_read_only_run_folder_leaves_the_project_usable(broken_dotted):
    run = broken_dotted / "runs" / "run1"
    before = _tree(broken_dotted)
    os.chmod(run, 0o555)
    try:
        Project.load(broken_dotted)          # must not raise
    finally:
        os.chmod(run, 0o755)
    assert sorted(before.values()) == sorted(
        v for k, v in _tree(broken_dotted).items() if k != "name-repair.json")
    Project.load(broken_dotted)              # resumes now that it can write
    assert (run / f"{DOTTED}.ti2").is_file()


# ------------------------------------------------------------- cal & modes

def test_the_calibration_chart_uses_its_own_stem(tmp_path):
    """RED against sharing the project stem, which §D5 implies:
    Path("X-…-w10.0mm-cal").stem is "X-…-w10", NOT "X-…-w10.0mm-cal"."""
    p = _build(tmp_path, DOTTED, broken=True, cal=True)
    Project.load(p)
    assert (p / "cal" / f"{DOTTED}-cal.ti2").is_file()
    assert not (p / "cal" / f"{DOTTED}.ti2").exists()


@pytest.mark.parametrize("mode", ["dry", "off"])
def test_dry_and_off_change_nothing_on_disk(broken_dotted, monkeypatch, mode):
    monkeypatch.setenv("CHROMIQ_NAME_REPAIR", mode)
    before = _tree(broken_dotted)
    Project.load(broken_dotted)
    assert _tree(broken_dotted) == before


def test_the_page_pattern_is_anchored(tmp_path):
    """A project whose truncation itself ends in _NN must still map correctly.
    RED against an unanchored or greedy page pattern."""
    p = _build(tmp_path, "Y_01.0mm", broken=True)
    Project.load(p)
    run = p / "runs" / "run1"
    assert (run / "Y_01.0mm_01.tif").is_file()
    assert (run / "Y_01.0mm_02.tif").is_file()
    assert not (run / "Y_01_01.tif").exists()
