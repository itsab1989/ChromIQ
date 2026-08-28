"""#130 (Knut, 2026-07-28): the Delete button — every case and every state.

His instruction was *"make test plan that covers every case, every button and
option"*, so this file is that plan in executable form: one test per row of the
review document, checked on disk as well as in the returned plan.

The rulings these tests pin, in his words:

* **D1** — the last run is refused; *"Offer the two options 'Empty the run' or
  'Delete the whole project'."*
* **D2** — *"I prefer landing on last run in the project, and that the warning
  window tells user about this behaviour."*
* **D3** — *"Let is be permanent."*
* **D4** — "Empty the run" only in the last-run case.
* **D5** — with 0 or 1 dated results the **whole** ``verifications/`` folder
  goes: *"why would we leave other folders existing? Like the reports/ or old/
  folders"*.
"""
from __future__ import annotations

import json

import pytest

from core.file_manager import Project, RunMeta
import core.run_delete as rd


# ---------------------------------------------------------------------------
# A real project on disk — these rules are about folders, so nothing is faked.
# ---------------------------------------------------------------------------
def _project(tmp_path, runs=1, name="Test-Profiling-P"):
    root = tmp_path / name
    root.mkdir(parents=True)
    proj = Project.create(root, name) if hasattr(Project, "create") else None
    if proj is None:                       # build the manifest by hand
        (root / "runs").mkdir()
        (root / Project.MANIFEST).write_text(json.dumps({
            "schema_version": 3, "created_at": "", "target_name": name,
            "current_run": "run1", "runs": ["run1"],
        }), encoding="utf-8")
        proj = Project.load(root)
    for _ in range(runs - 1):
        proj.new_run()
    for r in proj.all_runs():
        r.ensure_dir()
        if not r.meta_path.exists():
            r.save_meta(RunMeta.fresh(r.id))
    return proj


class _Target:
    def __init__(self, profile_run="run1", run_type="profiling",
                 verification_id=""):
        self.profile_run = profile_run
        self.run_type = run_type
        self.verification_id = verification_id

    def is_verification(self):
        return self.run_type == "verification"


def _measure(run):
    (run.dir / f"{run.stem}.ti3").write_text("MEAS")


def _profile(run):
    (run.dir / f"{run.stem}.icc").write_bytes(b"ICC")


def _verification(run, vid, *, measured=True):
    v = run.verification(vid)
    v.ensure_dir()
    if measured:
        v.measurement_ti3.write_text("V")
    return v


def _verify_chart(run):
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("TI2")


# ---------------------------------------------------------------------------
# E1–E12 — when the button is greyed, and why
# ---------------------------------------------------------------------------
def test_e1_not_while_measuring(tmp_path):
    p = _project(tmp_path, runs=2)
    assert rd.plan_for(p, _Target("run1"), measuring=True) == rd.BLOCK_MEASURING


def test_e2_no_project():
    assert rd.plan_for(None, _Target("run1")) == rd.BLOCK_NO_PROJECT


def test_e3_new_run_names_nothing(tmp_path):
    p = _project(tmp_path, runs=2)
    assert rd.plan_for(p, _Target("")) == rd.BLOCK_NEW_RUN


def test_e4_a_run_not_in_the_manifest(tmp_path):
    """Knut: "this should strictly never happen… However, this case is ok to
    have in case it happens." """
    p = _project(tmp_path, runs=2)
    assert rd.plan_for(p, _Target("run9")) == rd.BLOCK_UNKNOWN_RUN


def test_e5_a_profiling_run_is_deletable(tmp_path):
    p = _project(tmp_path, runs=2)
    plan = rd.plan_for(p, _Target("run1"))
    assert plan.kind == rd.KIND_RUN


def test_e6_no_verifications_folder(tmp_path):
    p = _project(tmp_path, runs=2)
    assert rd.plan_for(p, _Target("run1", "verification")) == \
        rd.BLOCK_NO_VERIFICATIONS


def test_e7_one_dated_result_takes_the_whole_folder(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-28_131500")
    plan = rd.plan_for(p, _Target("run1", "verification"))
    assert plan.kind == rd.KIND_VERIFY_ALL
    assert plan.path == run.verifications_dir


def test_e7_wording_is_his(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-28_131500")
    plan = rd.plan_for(p, _Target("run1", "verification"))
    assert rd.tooltip_for(plan) == (
        "Delete this run's whole verification folder — the verification chart "
        "and its results")


def test_e8_new_verification_with_several_results(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    for vid in ("2026-07-14_090211", "2026-07-21_114035"):
        _verification(run, vid)
    plan = rd.plan_for(p, _Target("run1", "verification"))
    assert plan.kind == rd.KIND_VERIFY_ALL
    assert "all 2" in rd.tooltip_for(plan)


def test_e9_selecting_the_only_date_is_the_same_case_as_e7(tmp_path):
    """His ruling: E9 folds into E7 — same situation, same window."""
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    vid = "2026-07-28_131500"
    _verification(run, vid)
    picked = rd.plan_for(p, _Target("run1", "verification", vid))
    unpicked = rd.plan_for(p, _Target("run1", "verification"))
    assert picked.kind == unpicked.kind == rd.KIND_VERIFY_ALL
    assert picked.path == unpicked.path == run.verifications_dir


def test_e10_one_of_several_dates(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    for vid in ("2026-07-14_090211", "2026-07-21_114035"):
        _verification(run, vid)
    plan = rd.plan_for(p, _Target("run1", "verification", "2026-07-14_090211"))
    assert plan.kind == rd.KIND_VERIFY_ONE
    assert plan.path.name == "2026-07-14_090211"


def test_e11_a_date_that_is_gone(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    for vid in ("2026-07-14_090211", "2026-07-21_114035"):
        _verification(run, vid)
    assert rd.plan_for(p, _Target("run1", "verification", "1999-01-01_000000")) \
        == rd.BLOCK_UNKNOWN_VERIFICATION


def test_e12_the_only_run_offers_the_two_ways_out(tmp_path):
    p = _project(tmp_path, runs=1)
    plan = rd.plan_for(p, _Target("run1"))
    assert plan.kind == rd.KIND_LAST_RUN
    assert rd.tooltip_for(plan) == "Empty this run, or delete the whole project"


# ---------------------------------------------------------------------------
# §3 — the windows say the right things
# ---------------------------------------------------------------------------
def test_p1_names_the_measurement_and_the_profile(tmp_path):
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    _measure(run)
    _profile(run)
    plan = rd.plan_for(p, _Target("run2"))
    body = rd.message_for(plan)
    assert ".ti3" in body and ".icc" in body
    assert "cannot be recreated" in body
    assert "Trash" in body and "cannot be undone" not in body


def test_p2_says_plainly_that_nothing_measured_is_lost(tmp_path):
    """A run with nothing in it must not be described as though it had.

    THE WORDING CHANGED FROM "has not been measured" TO "has no measurement …
    right now", and that is the whole point: the old sentence was a claim about
    the run's HISTORY, and it was false for the commonest case. Re-generating a
    chart on a measured run archives the measurement and the profile into
    `old/<date>/` — deliberately, because they cannot be recreated — leaving no
    live `.ti3`. Such a run read as "has not been measured" while the window
    went on to delete two archived measurements and a profile.
    """
    p = _project(tmp_path, runs=3)
    plan = rd.plan_for(p, _Target("run2"))
    body = rd.message_for(plan)
    assert "no measurement and no profile in it right now" in body
    assert ".ti3" not in body
    # …and it must not claim anything about what the run once held.
    assert "has not been measured" not in body


def test_p1_lists_the_renumbering_in_full(tmp_path):
    """His example: 10 runs, delete run6 → 7..10 become 6..9."""
    p = _project(tmp_path, runs=10)
    plan = rd.plan_for(p, _Target("run6"))
    assert plan.renumbering == [("run7", "run6"), ("run8", "run7"),
                                ("run9", "run8"), ("run10", "run9")]
    body = rd.message_for(plan)
    for phrase in ("run 7 becomes run 6", "run 8 becomes run 7",
                   "run 9 becomes run 8", "run 10 becomes run 9"):
        assert phrase in body, phrase


def test_deleting_the_last_run_renumbers_nothing(tmp_path):
    p = _project(tmp_path, runs=3)
    plan = rd.plan_for(p, _Target("run3"))
    assert plan.renumbering == []
    assert "already unbroken" in rd.message_for(plan)


def test_d2_the_window_says_where_you_land(tmp_path):
    """"…and that the warning window tells user about this behaviour." """
    p = _project(tmp_path, runs=10)
    plan = rd.plan_for(p, _Target("run6"))
    assert plan.lands_on == "run9"
    assert "selects the last run in the project, run 9" in rd.message_for(plan)


def test_p3_mentions_a_run_seeded_from_this_one(tmp_path):
    p = _project(tmp_path, runs=2)
    parent = p.run("run1")
    _measure(parent)
    _profile(parent)
    child = p.run("run2")
    meta = child.load_meta()
    meta.parent_run = "run1"
    meta.preconditioning_source_run = "run1"
    child.save_meta(meta)

    plan = rd.plan_for(p, _Target("run1"))
    assert plan.seeded_runs == ["run2"]
    body = rd.message_for(plan)
    assert "Run 2 was built on top of this run" in body
    assert "goes on working" in body


def test_p3_uses_real_plural_for_several_children(tmp_path):
    p = _project(tmp_path, runs=3)
    for rid in ("run2", "run3"):
        child = p.run(rid)
        meta = child.load_meta()
        meta.parent_run = "run1"
        child.save_meta(meta)
    plan = rd.plan_for(p, _Target("run1"))
    body = rd.message_for(plan)
    assert "Runs 2 and 3 were built" in body
    assert "(s)" not in body


def test_p5_offers_both_ways_out(tmp_path):
    p = _project(tmp_path, runs=1)
    body = rd.message_for(rd.plan_for(p, _Target("run1")))
    assert "Empty the run" in body
    assert "Delete the whole project" in body
    assert "start it fresh, with no project open" in body


@pytest.mark.parametrize("measured,phrase", [
    (True, "including its measurement and its report"),
    (False, "which was never measured"),
])
def test_v1_wording_follows_what_is_actually_there(tmp_path, measured, phrase):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-28_131500", measured=measured)
    body = rd.message_for(rd.plan_for(p, _Target("run1", "verification")))
    assert phrase in body


def test_v1_with_no_dated_result_at_all(tmp_path):
    """D5: the folder exists with only a chart and leftovers in it."""
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    (run.verifications_dir / "old").mkdir()
    body = rd.message_for(rd.plan_for(p, _Target("run1", "verification")))
    assert "no verification has been measured yet" in body
    assert "13:15" not in body, "it must not name a date that does not exist"


def test_v1_explains_why_the_whole_folder_goes(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-28_131500")
    body = rd.message_for(rd.plan_for(p, _Target("run1", "verification")))
    assert "nothing left to belong to" in body
    assert "“exports”" in body and "“old”" in body


def test_v1_promises_the_profiling_side_is_untouched(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-28_131500")
    body = rd.message_for(rd.plan_for(p, _Target("run1", "verification")))
    assert "profiling side of run 1 is not touched" in body
    assert "keep the numbers they have now" in body, \
        "the window no longer reassures the person that numbering is unaffected"


def test_v2_lists_every_date_that_will_be_lost(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    ids = ("2026-07-14_090211", "2026-07-21_114035", "2026-07-28_131500")
    for vid in ids:
        _verification(run, vid)
    plan = rd.plan_for(p, _Target("run1", "verification"))
    body = rd.message_for(plan)
    for vid in ids:
        assert rd.pretty_date(vid) in body
    assert rd.confirm_label(plan) == "Delete all 3 verifications"


def test_v3_names_only_the_one_folder(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    for vid in ("2026-07-14_090211", "2026-07-21_114035"):
        _verification(run, vid)
    plan = rd.plan_for(p, _Target("run1", "verification", "2026-07-14_090211"))
    body = rd.message_for(plan)
    assert "Only this one verification result" in body
    assert "the other verification dates of this run" in body
    assert rd.confirm_label(plan) == "Delete this verification"


def test_v3_empty_date_says_no_readings_are_lost(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-14_090211", measured=True)
    _verification(run, "2026-07-21_114035", measured=False)
    plan = rd.plan_for(p, _Target("run1", "verification", "2026-07-21_114035"))
    assert "never measured, so no readings will be lost" in rd.message_for(plan)
    assert rd.confirm_label(plan) == "Delete this empty verification"


def test_every_window_says_where_the_files_go(tmp_path):
    """Every window has to say what really happens to the files.

    IT USED TO ASSERT THE OPPOSITE, AND WAS RIGHT TO. Knut ruled "let it be
    permanent" (D3) and every window said "this cannot be undone". That stood
    until `shutil.rmtree` was measured doing the opposite of its own promise:
    one unwritable sub-folder is enough for it to destroy most of a project and
    only then raise, so the app said "Nothing was changed." over ten missing
    files, `project.json` among them. Basti ruled on 2026-08-28 that a delete
    moves to the Trash — a rename, which cannot half-happen — so the windows
    now say where the files went and that they can be brought back.
    """
    p = _project(tmp_path, runs=3)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-14_090211")
    _verification(run, "2026-07-21_114035")
    for target in (_Target("run1"),
                   _Target("run1", "verification"),
                   _Target("run1", "verification", "2026-07-14_090211")):
        body = rd.message_for(rd.plan_for(p, target))
        assert "Trash" in body, target.run_type
        assert "cannot be undone" not in body, (
            f"{target.run_type}: the window still promises permanence, which "
            f"is no longer what happens")
        # The point is that the window says the files can be RECOVERED, not
        # that it uses one particular phrase — assert the meaning, or the test
        # breaks on every rewording and teaches nothing.
        assert any(w in body for w in ("back where it was", "back to its place",
                                       "put them back", "back on its place")), \
            f"{target.run_type}: the window never says the files can be recovered"


def test_no_window_ever_writes_s_in_brackets(tmp_path):
    p = _project(tmp_path, runs=4)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-14_090211")
    for target in (_Target("run2"), _Target("run1", "verification")):
        assert "(s)" not in rd.message_for(rd.plan_for(p, target))


# ---------------------------------------------------------------------------
# §4 — doing it, checked on disk
# ---------------------------------------------------------------------------
def test_deleting_a_run_removes_it_and_renumbers_the_rest(tmp_path):
    p = _project(tmp_path, runs=4)
    for rid in ("run1", "run2", "run3", "run4"):
        (p.run(rid).dir / "marker.txt").write_text(rid)

    plan = rd.plan_for(p, _Target("run2"))
    landed = rd.delete_run(p, plan)

    root = p.runs_root
    assert sorted(d.name for d in root.iterdir() if d.is_dir()) == \
        ["run1", "run2", "run3"]
    # …and the folders kept their CONTENTS, only their names moved.
    assert (root / "run1" / "marker.txt").read_text() == "run1"
    assert (root / "run2" / "marker.txt").read_text() == "run3"
    assert (root / "run3" / "marker.txt").read_text() == "run4"
    assert landed == "run3"


def test_the_manifest_follows_the_folders(tmp_path):
    p = _project(tmp_path, runs=4)
    rd.delete_run(p, rd.plan_for(p, _Target("run2")))

    manifest = json.loads((p.root / Project.MANIFEST).read_text())
    assert manifest["runs"] == ["run1", "run2", "run3"]
    assert manifest["current_run"] == "run3", "D2: land on the last run"


def test_every_meta_json_is_rewritten(tmp_path):
    p = _project(tmp_path, runs=4)
    rd.delete_run(p, rd.plan_for(p, _Target("run2")))

    for rid in ("run1", "run2", "run3"):
        meta = json.loads((p.runs_root / rid / "meta.json").read_text())
        assert meta["run_id"] == rid, f"{rid} still claims to be {meta['run_id']}"


def test_a_reference_to_a_renamed_run_is_remapped(tmp_path):
    p = _project(tmp_path, runs=4)
    child = p.run("run4")
    meta = child.load_meta()
    meta.parent_run = "run3"
    meta.preconditioning_source_run = "run3"
    child.save_meta(meta)

    rd.delete_run(p, rd.plan_for(p, _Target("run2")))   # run3 → run2, run4 → run3

    moved = json.loads((p.runs_root / "run3" / "meta.json").read_text())
    assert moved["parent_run"] == "run2"
    assert moved["preconditioning_source_run"] == "run2"


def test_a_reference_to_the_deleted_run_is_cleared(tmp_path):
    p = _project(tmp_path, runs=3)
    child = p.run("run3")
    meta = child.load_meta()
    meta.parent_run = "run2"
    meta.preconditioning_source_run = "run2"
    child.save_meta(meta)

    rd.delete_run(p, rd.plan_for(p, _Target("run2")))

    moved = json.loads((p.runs_root / "run2" / "meta.json").read_text())
    assert moved["parent_run"] is None
    assert moved["preconditioning_source_run"] is None


def test_files_inside_a_renamed_run_keep_their_names(tmp_path):
    """`Run.stem` is the PROJECT name, so renumbering renames no file."""
    p = _project(tmp_path, runs=3)
    run3 = p.run("run3")
    _measure(run3)
    _profile(run3)

    rd.delete_run(p, rd.plan_for(p, _Target("run1")))

    moved = p.runs_root / "run2"
    assert (moved / "Test-Profiling-P.ti3").exists()
    assert (moved / "Test-Profiling-P.icc").exists()


def test_deleting_a_verification_folder_leaves_the_run_alone(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _measure(run)
    _profile(run)
    _verify_chart(run)
    _verification(run, "2026-07-28_131500")
    (run.verifications_dir / "old").mkdir()

    rd.delete_verification(rd.plan_for(p, _Target("run1", "verification")))

    assert not run.verifications_dir.exists()
    assert run.measurement_ti3.exists(), "the profiling side must be untouched"
    assert run.profile_icc.exists()


def test_deleting_one_date_keeps_the_chart_and_the_others(tmp_path):
    p = _project(tmp_path, runs=2)
    run = p.run("run1")
    _verify_chart(run)
    _verification(run, "2026-07-14_090211")
    _verification(run, "2026-07-21_114035")

    rd.delete_verification(
        rd.plan_for(p, _Target("run1", "verification", "2026-07-14_090211")))

    assert not (run.verifications_dir / "2026-07-14_090211").exists()
    assert (run.verifications_dir / "2026-07-21_114035").exists()
    assert run.verify_chart_ti2.exists()


def test_emptying_a_run_keeps_the_folder_and_a_fresh_meta(tmp_path):
    p = _project(tmp_path, runs=1)
    run = p.run("run1")
    _measure(run)
    _profile(run)
    _verify_chart(run)

    rd.empty_run(p, "run1")

    assert run.dir.exists()
    assert not run.measurement_ti3.exists()
    assert not run.profile_icc.exists()
    assert not run.verifications_dir.exists()
    assert json.loads(run.meta_path.read_text())["run_id"] == "run1"


def test_nothing_is_ever_moved_to_an_old_folder(tmp_path):
    """D3 again, this time on disk: Delete is not Replace — it does not
    archive."""
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    _measure(run)

    rd.delete_run(p, rd.plan_for(p, _Target("run2")))

    assert not list(p.runs_root.glob("*/old/*")), "something was archived"


def test_a_missing_folder_reports_failure_rather_than_pretending(tmp_path):
    p = _project(tmp_path, runs=3)
    plan = rd.plan_for(p, _Target("run2"))
    import shutil
    shutil.rmtree(plan.path)

    with pytest.raises(rd.DeleteFailed):
        rd.delete_run(p, plan)


def test_a_failed_rename_rolls_back_and_leaves_the_numbering_alone(tmp_path, monkeypatch):
    """X1: "the run numbering has been left exactly as it was" must be true,
    not hopeful — which is why the rename is two-phase."""
    p = _project(tmp_path, runs=4)
    plan = rd.plan_for(p, _Target("run2"))

    from pathlib import Path
    real = Path.rename
    calls = {"n": 0}

    def flaky(self, target):
        calls["n"] += 1
        if calls["n"] == 3:                    # part-way through
            raise OSError("in use")
        return real(self, target)

    monkeypatch.setattr(Path, "rename", flaky)
    with pytest.raises(rd.DeleteFailed):
        rd.delete_run(p, plan)
    monkeypatch.setattr(Path, "rename", real)

    # run2 is gone (that succeeded), but nothing else moved and no temporary
    # folder was left behind.
    names = sorted(d.name for d in p.runs_root.iterdir() if d.is_dir())
    assert names == ["run1", "run3", "run4"], names
    assert not any(rd._TMP_SUFFIX in n for n in names)


# ---------------------------------------------------------------------------
# F6: what the run keeps in old/ — the run that LOOKS unmeasured is usually the
# one with the most to lose
# ---------------------------------------------------------------------------

def _archive(run, when: str, *, measurement=True, profile=True):
    """Put an archived session in the run's old/ folder, as a chart re-make does."""
    d = run.old_dir / when
    d.mkdir(parents=True, exist_ok=True)
    if measurement:
        (d / f"{run.stem}.ti3").write_text("readings")
        reads = d / "reads"
        reads.mkdir(exist_ok=True)
        (reads / "read1.ti3").write_text("one")
    if profile:
        (d / f"{run.stem}.icc").write_text("profile")
    return d


def test_a_run_whose_chart_was_remade_is_not_called_unmeasured(tmp_path):
    """The exact sequence a person follows in the ordinary refinement loop:
    measure a run, then re-make its chart. ChromIQ archives the measurement and
    the profile on purpose. Delete then said "no measurement and no profile
    will be lost" and removed both."""
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    _archive(run, "2026-08-11_101500")
    body = rd.message_for(rd.plan_for(p, _Target("run2")))
    assert "one earlier measurement" in body
    assert "2026-08-11 10:15:00" in body
    assert "cannot be recreated" in body
    assert "one earlier printer profile" in body


def test_several_archives_are_counted_and_dated(tmp_path):
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    _archive(run, "2026-08-11_101500")
    _archive(run, "2026-08-14_090000")
    _archive(run, "2026-08-27_173000")
    body = rd.message_for(rd.plan_for(p, _Target("run2")))
    assert "3 earlier measurements" in body
    for d in ("2026-08-11 10:15:00", "2026-08-14 09:00:00", "2026-08-27 17:30:00"):
        assert d in body, d
    assert "3 earlier printer profiles" in body


def test_measurements_and_profiles_are_counted_separately(tmp_path):
    """A dated folder can hold a measurement with no profile. Composing one
    sentence from two counts is how "2 measurements and 1 profiles" happens,
    which is the fault the house rule against "(s)" exists to prevent."""
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    _archive(run, "2026-08-11_101500", profile=False)
    _archive(run, "2026-08-14_090000")
    body = rd.message_for(rd.plan_for(p, _Target("run2")))
    assert "2 earlier measurements" in body
    assert "one earlier printer profile" in body
    assert "(s)" not in body


def test_the_chart_a_measurement_was_taken_with_is_named(tmp_path):
    """`chart/` is the only copy of it, and Restore Used Chart is the only thing
    that reads it. No delete window mentioned it."""
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    run.chart_snapshot_dir.mkdir(parents=True, exist_ok=True)
    (run.chart_snapshot_dir / f"{run.stem}.ti2").write_text("the used chart")
    body = rd.message_for(rd.plan_for(p, _Target("run2")))
    assert "Restore Used Chart" in body
    assert "no other one" in body


def test_the_preconditioning_seed_is_named(tmp_path):
    """ChromIQ preserves preconditioning.* across a chart rebuild on purpose,
    then Delete removed it silently."""
    p = _project(tmp_path, runs=3)
    run = p.run("run2")
    run.preconditioning_ti3.write_text("the seed")
    body = rd.message_for(rd.plan_for(p, _Target("run2")))
    assert "pre-conditioning" in body


def test_an_empty_old_folder_says_nothing_extra(tmp_path):
    """The negative control: a run with nothing archived must not grow a
    paragraph about archives."""
    p = _project(tmp_path, runs=3)
    p.run("run2").old_dir.mkdir(parents=True, exist_ok=True)
    body = rd.message_for(rd.plan_for(p, _Target("run2")))
    assert "earlier measurement" not in body
    assert "earlier printer profile" not in body
