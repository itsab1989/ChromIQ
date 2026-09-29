"""A project from before the folder redesign is actually moved, not just stamped.

A tester, 2026-09-17, on three of his own projects from February 2026:

    *"Loading any of the two older projects does not convert them into new
    project folder structure, and files are not moved to correct place. I did
    try several times. First time I tried, I got the message that the project
    loaded was made with an older ChromIQ and that it would be converted to new
    folder structure. That did not happen. No folders were created. The second
    and third time I tried, then I no longer got a message that the files in
    the folder were from an old project, and nothing was moved or reorganised
    to the new folder structure."*

Both halves are one fault. `_migrate_v1_to_v2` iterates `runs/runN` and tidies
what is inside each run folder -- but a pre-redesign project has no `runs/` at
all, so the loop found nothing, the schema was stamped to current anyway, the
guide was rewritten, and "Migration to v2 complete" went into the log. The next
load read that stamp and correctly concluded there was nothing to do.

It passed every test because `tests/golden/project_v1`, the fixture the whole
v1->v2 matrix runs against, ALREADY HAS `runs/`. The layout that actually
shipped before `c1fe7a0b` (2026-05-27) was flatter than the one the migration
was written for, and nothing in the suite held an example of it.

These tests hold one.
"""
import json

import pytest

STEM = "Printer_HP-Plain90g-sRGB-900Patches_2026.02.09"
#: what a pre-redesign project has loose in its folder: the Argyll chain plus
#: the page bitmaps, all carrying the project name as their stem.
CHAIN = [f"{STEM}.ti1", f"{STEM}.ti2", f"{STEM}.ti3", f"{STEM}.icc",
         f"{STEM}_01.tif", f"{STEM}_02.tif"]
#: files that are NOT the chain and must stay exactly where the user left them
BYSTANDERS = ["Argyll_Printer_Profiler_20260209_122908.log",
              f"{STEM}_sanity_check.txt", "my own notes.txt"]


def _pre_runs_project(tmp_path, *, manifest=None):
    """A project folder in the layout ChromIQ shipped before the redesign."""
    root = tmp_path / STEM
    root.mkdir(parents=True)
    for name in CHAIN + BYSTANDERS:
        (root / name).write_text(f"content of {name}", encoding="utf-8")
    if manifest is not None:
        (root / "project.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def _listing(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


# ---------------------------------------------------------------- the move

def test_a_pre_runs_project_moves_its_chain_into_run1(tmp_path):
    """The chart, the measurement and the profile end up in the run folder.

    The tester's projects A and C: no manifest at all. `create_or_load` used to
    build a brand-new empty project AROUND them, leaving every file loose.
    """
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path)
    proj = Project.create_or_load(root, root.name)

    run = proj.current_run()
    assert run.dir.is_dir(), "no run folder was created at all"
    for name in CHAIN:
        assert (run.dir / name).is_file(), f"{name} was not moved into the run"
        assert not (root / name).exists(), f"{name} was left loose as well"
    # the three the tester named, through the API the rest of the app uses
    assert run.chart_ti2.is_file()
    assert run.measurement_ti3.is_file()
    assert run.profile_icc.is_file()


def test_the_migration_keeps_every_byte(tmp_path):
    """Moved, never rewritten: this runs on somebody's only measurement."""
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path)
    proj = Project.create_or_load(root, root.name)
    for name in CHAIN:
        assert (proj.current_run().dir / name).read_text(
            encoding="utf-8") == f"content of {name}"


def test_files_that_are_not_the_chain_are_left_alone(tmp_path):
    """A user's own file in the project folder is not ChromIQ's to move."""
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path)
    Project.create_or_load(root, root.name)
    for name in BYSTANDERS:
        assert (root / name).is_file(), f"{name} was moved and should not be"


def test_a_project_already_stamped_as_current_is_still_repaired(tmp_path):
    """THE MANIFEST CANNOT BE THE GATE, BECAUSE THE MANIFEST ALREADY LIED.

    The tester's project B is the state the broken migration leaves behind: a
    manifest saying the current schema, `runs: ["run1"]`, and every file still
    loose in the project folder. Gate the repair on `schema_version` and this
    project can never be fixed -- which is exactly why his second and third
    attempts did nothing and said nothing.
    """
    from core.file_manager import SCHEMA_VERSION, Project

    root = _pre_runs_project(tmp_path, manifest={
        "schema_version": SCHEMA_VERSION,          # already "current"
        "created_at": "2026-07-19T05:31:32",
        "target_name": STEM,
        "current_run": "run1",
        "runs": ["run1"],
    })
    run = Project.load(root).current_run()
    assert run.measurement_ti3.is_file(), (
        "a project stamped with the current schema but still flat on disk was "
        "not repaired - the schema number is being trusted over the disk")
    assert run.chart_ti2.is_file()
    assert run.profile_icc.is_file()


def test_a_schema_1_project_is_migrated_through_load(tmp_path):
    """The door the tester used: open the project.json of an old project."""
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path, manifest={
        "schema_version": 1,
        "created_at": "2026-02-09T12:29:08",
        "target_name": STEM,
        "current_run": "run1",
        "runs": ["run1"],
    })
    run = Project.load(root).current_run()
    assert run.measurement_ti3.is_file()


# ------------------------------------------------------- refusing to guess

def test_a_refused_migration_changes_nothing_at_all(tmp_path):
    """When the run already holds a chart of its own, the loose files stay put.

    The failure mode of a migration that moves somebody's measurements has to
    be "did nothing", never "did half of it". Two charts with the same names
    means one of them is not this run's, and picking a winner per filename is
    not a decision this code is allowed to make.
    """
    from core.file_manager import Project, migrate_flat_project

    root = _pre_runs_project(tmp_path)
    run_dir = root / "runs" / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / f"{STEM}.ti2").write_text("a DIFFERENT chart", encoding="utf-8")

    before = _listing(root)
    assert migrate_flat_project(root, "run1") == 0, "it should have refused"
    assert _listing(root) == before, "a refusal moved something anyway"
    assert (run_dir / f"{STEM}.ti2").read_text(encoding="utf-8") == \
        "a DIFFERENT chart", "the run's own chart was overwritten"
    # and the loose measurement is still readable where the user left it
    assert (root / f"{STEM}.ti3").is_file()


def test_a_measurement_is_never_merged_into_a_run_with_a_DIFFERENT_chart(tmp_path):
    """The refusal that the filename check alone does not give you.

    When the names happen not to collide, a merge is silent and worse than a
    collision: the loose `.ti3` and `.icc` would join a run whose `.ti1`/`.ti2`
    are a different chart, pairing somebody's measurement with a layout it was
    not read from. Refuse on the run HOLDING a chart, not merely on a clash.
    """
    from core.file_manager import migrate_flat_project

    root = tmp_path / STEM
    root.mkdir(parents=True)
    # loose: only the measurement and the profile
    for name in (f"{STEM}.ti3", f"{STEM}.icc"):
        (root / name).write_text(f"content of {name}", encoding="utf-8")
    # the run already has a chart of its own, under names that do NOT clash
    run_dir = root / "runs" / "run1"
    run_dir.mkdir(parents=True)
    for name in (f"{STEM}.ti1", f"{STEM}.ti2"):
        (run_dir / name).write_text("a DIFFERENT chart", encoding="utf-8")

    assert migrate_flat_project(root, "run1") == 0, (
        "the loose measurement was merged into a run holding another chart")
    assert (root / f"{STEM}.ti3").is_file(), "the measurement was moved anyway"
    assert not (run_dir / f"{STEM}.ti3").exists()


def test_a_refusal_does_not_stamp_the_manifest(tmp_path):
    """A folder must never end up claiming a layout it does not have.

    That claim is the whole reason the tester's second and third loads were
    silent, so a refusal writing one would rebuild the fault it fixes.
    """
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path, manifest={
        "schema_version": 3, "created_at": "x", "target_name": STEM,
        "current_run": "run1", "runs": ["run1"]})
    run_dir = root / "runs" / "run1"
    run_dir.mkdir(parents=True)
    (run_dir / f"{STEM}.ti2").write_text("a DIFFERENT chart", encoding="utf-8")

    Project.load(root)
    assert (root / f"{STEM}.ti3").is_file(), (
        "the loose measurement was moved despite the run holding its own chart")


@pytest.mark.parametrize("evil", ["../..", "..", ".", "", "a/b", "x\\y"])
def test_a_hand_edited_current_run_cannot_carry_the_files_out(tmp_path, evil):
    """Found by a challenge round on this change, not by the report.

    `run_id` comes from `project.json`'s `current_run`, and
    `ProjectManifest.from_dict` does not sanitise it - only `peek_project`
    does, in its own `_safe_id`, and it says why: a manifest is a file people
    can edit and projects get mailed around. Everything else that builds a path
    from it only READS. This MOVES somebody's measurements, so `"../.."` would
    carry them out of the project entirely.
    """
    from core.file_manager import migrate_flat_project

    root = _pre_runs_project(tmp_path)
    outside = _listing(tmp_path)

    assert migrate_flat_project(root, evil) == 0, f"{evil!r} was accepted"
    assert _listing(tmp_path) == outside, (
        f"{evil!r} moved something; the project folder or its neighbours "
        "changed")
    assert (root / f"{STEM}.ti3").is_file(), "the measurement left the project"


def test_the_manifest_route_refuses_the_same_way(tmp_path):
    """And through `Project.load`, which is how a mailed project arrives."""
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path, manifest={
        "schema_version": 1, "created_at": "x", "target_name": STEM,
        "current_run": "../..", "runs": ["../.."]})
    before = _listing(tmp_path)
    Project.load(root)
    assert (root / f"{STEM}.ti3").is_file(), "the measurement left the project"
    assert (root / f"{STEM}.icc").is_file()
    # nothing was created outside the project folder
    assert {e for e in _listing(tmp_path) if not e.startswith(STEM)} == \
           {e for e in before if not e.startswith(STEM)}


# ------------------------------------------------------------ idempotence

def test_opening_twice_moves_nothing_the_second_time(tmp_path):
    """Loading a migrated project must be a no-op on disk."""
    from core.file_manager import Project

    root = _pre_runs_project(tmp_path)
    Project.create_or_load(root, root.name)
    after_first = _listing(root)
    Project.create_or_load(root, root.name)
    assert _listing(root) == after_first


def test_a_laid_out_project_has_nothing_loose_to_find(tmp_path):
    """The detector must not misfire on a project that is already correct."""
    from core.file_manager import Project, flat_legacy_chain

    root = tmp_path / STEM
    proj = Project.create(root, STEM)
    run = proj.current_run()
    for name in CHAIN:
        (run.dir / name).write_text("x", encoding="utf-8")
    assert flat_legacy_chain(root) == [], (
        "a correctly laid-out project looks like a legacy one")


# ------------------------------------- it must not read as empty beforehand

@pytest.mark.parametrize("with_manifest", [False, True])
def test_a_pre_runs_project_does_not_read_as_empty(tmp_path, with_manifest):
    """`peek_project` is the "nothing shall ever be lost" guard, and it said
    these projects held nothing at all -- so a build could land on top of a
    chart, a measurement and a profile without a word."""
    from core.file_manager import peek_project

    manifest = {"schema_version": 3, "created_at": "x", "target_name": STEM,
                "current_run": "run1", "runs": ["run1"]} if with_manifest else None
    root = _pre_runs_project(tmp_path, manifest=manifest)

    peek = peek_project(root)
    assert peek.exists, "a folder full of somebody's work read as absent"
    assert peek.holds_anything, "it read as holding nothing"
    assert peek.chart and peek.measurement and peek.profile


def test_peeking_never_moves_anything(tmp_path):
    """Asking is read-only: it is asked while a user is merely typing a name."""
    from core.file_manager import peek_project

    root = _pre_runs_project(tmp_path)
    before = _listing(root)
    peek_project(root)
    assert _listing(root) == before
