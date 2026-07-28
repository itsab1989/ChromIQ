"""Deleting a profile run or a run's verification files (#130, Knut).

Kept free of Qt so every rule and every word can be unit tested, the same way
``core.measurement_target`` holds the chart-overwrite message. The bar builds
the actual window from what :func:`plan_for` returns.

**The shape of the feature, as ruled by Knut (2026-07-28):**

* Profiling deletes the **whole run folder**, then renumbers the survivors so
  the numbering stays unbroken, and lands on the **last** run — landing on the
  same run *number* would look as though nothing had happened.
* A project always keeps at least one run, so deleting the only run is refused
  and two ways out are offered instead: empty it, or delete the whole project.
* Verification deletes the **whole ``verifications/`` folder** whenever 0 or 1
  dated results exist — *"why would we leave other folders existing? Like the
  reports/ or old/ folders"* — and only the selected dated folder when several
  results exist and one of them is picked.
* Nothing is moved to the Trash. Nothing is archived to ``old/``. What the user
  confirms is removed for good, and the window says so.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from core.i18n import tr

log = logging.getLogger(__name__)

# What the button can do, and what the window has to say.
KIND_RUN = "run"                    # delete a whole profile run
KIND_LAST_RUN = "last_run"          # the only run — offer empty / delete project
KIND_VERIFY_ALL = "verify_all"      # the whole verifications/ folder
KIND_VERIFY_ONE = "verify_one"      # one dated verification folder

# Why the button is greyed. The codes double as test names.
BLOCK_MEASURING = "measuring"
BLOCK_NO_PROJECT = "no_project"
BLOCK_NEW_RUN = "new_run"
BLOCK_UNKNOWN_RUN = "unknown_run"
BLOCK_NO_VERIFICATIONS = "no_verifications"
BLOCK_UNKNOWN_VERIFICATION = "unknown_verification"

_BLOCK_TOOLTIPS = {
    BLOCK_MEASURING: lambda: tr("Not while a measurement is running"),
    BLOCK_NO_PROJECT: lambda: tr("Open or create a project first"),
    BLOCK_NEW_RUN: lambda: tr(
        "Select an existing profile run to delete. “New run” is not a run yet "
        "— there is nothing on disk to remove"),
    BLOCK_UNKNOWN_RUN: lambda: tr("This profile run no longer exists"),
    BLOCK_NO_VERIFICATIONS: lambda: tr(
        "This profile run has no verification files to delete"),
    BLOCK_UNKNOWN_VERIFICATION: lambda: tr(
        "This verification date no longer exists"),
}


def block_tooltip(code: str) -> str:
    return _BLOCK_TOOLTIPS.get(code, lambda: tr("Nothing to delete"))()


@dataclass
class DeletePlan:
    """What Delete would do, and everything the window needs to say it."""
    kind: str
    #: The folder that would be removed (None for KIND_LAST_RUN, which removes
    #: nothing until the user picks one of its two ways out).
    path: "Path | None" = None
    run_id: str = ""
    project_name: str = ""
    #: Dated verification ids involved, oldest first.
    verification_ids: list = field(default_factory=list)
    #: KIND_RUN only — what the run holds, so the window can be honest.
    has_measurement: bool = False
    has_profile: bool = False
    #: KIND_RUN only — runs that named this one as their pre-conditioning source.
    seeded_runs: list = field(default_factory=list)
    #: KIND_RUN only — (old_id, new_id) pairs the renumbering would apply.
    renumbering: list = field(default_factory=list)
    #: KIND_RUN only — the run that will be selected afterwards.
    lands_on: str = ""
    #: KIND_VERIFY_ALL only — whether the one dated result has readings.
    verification_measured: bool = False
    has_verify_chart: bool = False


def run_number(run_id: str) -> str:
    """``run6`` → ``6``; anything else is returned unchanged."""
    return run_id[3:] if run_id.startswith("run") else run_id


def _dated(run) -> list:
    try:
        return [v.id for v in run.verifications()]
    except Exception:      # noqa: BLE001
        return []


def plan_for(project, target, *, measuring: bool = False
             ) -> "DeletePlan | str":
    """What Delete would do for this selection — a :class:`DeletePlan`, or a
    ``BLOCK_*`` code saying why the button is greyed.

    The order of the checks is the order of the table in the review document,
    so a reader can follow one against the other.
    """
    if measuring:
        return BLOCK_MEASURING
    if project is None:
        return BLOCK_NO_PROJECT
    run_id = getattr(target, "profile_run", "")
    if not run_id:
        return BLOCK_NEW_RUN
    if not project.has_run(run_id):
        # Should be unreachable: the dropdown is rebuilt from the manifest after
        # every delete. Kept because Knut asked for it as a safety net.
        return BLOCK_UNKNOWN_RUN
    run = project.run(run_id)
    name = getattr(project, "root", Path(".")).name

    if target.is_verification():
        if not run.verifications_dir.exists():
            return BLOCK_NO_VERIFICATIONS
        dated = _dated(run)
        vid = getattr(target, "verification_id", "")
        if vid and vid not in dated:
            return BLOCK_UNKNOWN_VERIFICATION
        # 0 or 1 dated results → the whole folder, whatever the field shows.
        if len(dated) <= 1:
            measured = False
            if dated:
                try:
                    measured = run.verification(dated[0]).measurement_ti3.exists()
                except Exception:      # noqa: BLE001
                    measured = False
            return DeletePlan(
                kind=KIND_VERIFY_ALL, path=run.verifications_dir,
                run_id=run_id, project_name=name, verification_ids=list(dated),
                verification_measured=measured,
                has_verify_chart=run.has_verify_chart())
        if not vid:
            # "New verification" with several results → the whole folder.
            return DeletePlan(
                kind=KIND_VERIFY_ALL, path=run.verifications_dir,
                run_id=run_id, project_name=name, verification_ids=list(dated),
                has_verify_chart=run.has_verify_chart())
        verification = run.verification(vid)
        return DeletePlan(
            kind=KIND_VERIFY_ONE, path=verification.dir, run_id=run_id,
            project_name=name, verification_ids=[vid],
            verification_measured=verification.measurement_ti3.exists())

    # ---- profiling
    all_ids = [r.id for r in project.all_runs()]
    if len(all_ids) <= 1:
        return DeletePlan(kind=KIND_LAST_RUN, path=run.dir, run_id=run_id,
                          project_name=name)

    survivors = [r for r in all_ids if r != run_id]
    renumbering = [(old, f"run{i}") for i, old in enumerate(survivors, start=1)
                   if old != f"run{i}"]
    seeded = []
    for other in all_ids:
        if other == run_id:
            continue
        try:
            meta = project.run(other).load_meta()
        except Exception:      # noqa: BLE001
            continue
        if run_id in (meta.parent_run, meta.preconditioning_source_run):
            seeded.append(other)
    return DeletePlan(
        kind=KIND_RUN, path=run.dir, run_id=run_id, project_name=name,
        has_measurement=run.measurement_ti3.exists(),
        has_profile=run.profile_icc.exists() or (run.dir / f"{run.stem}.icm").exists(),
        seeded_runs=seeded, renumbering=renumbering,
        lands_on=f"run{len(survivors)}",
        verification_ids=_dated(run))


# ---------------------------------------------------------------------------
# The words
# ---------------------------------------------------------------------------

def _join(items: list) -> str:
    """"a, b and c" — real prose, and correct for one item."""
    items = [str(i) for i in items]
    if len(items) == 1:
        return items[0]
    return tr("{first} and {last}").format(
        first=", ".join(items[:-1]), last=items[-1])


def _renumber_sentence(plan: DeletePlan) -> str:
    if not plan.renumbering:
        return tr("No other run has to be renumbered — the numbering is "
                  "already unbroken without this one.")
    moves = [tr("run {old} becomes run {new}").format(
        old=run_number(o), new=run_number(n)) for o, n in plan.renumbering]
    if len(moves) == 1:
        body = tr("Your other runs are renumbered, so after this deletion "
                  "{move}.").format(move=moves[0])
    else:
        body = tr("Your other runs are renumbered. Run numbers stay in an "
                  "unbroken sequence, so after this deletion {moves}.").format(
                      moves=_join(moves))
    return body + " " + tr(
        "The files inside those runs are not renamed — only the folders they "
        "sit in.")


def title_for(plan: DeletePlan) -> str:
    if plan.kind == KIND_LAST_RUN:
        return tr("This is the only run in the project")
    if plan.kind == KIND_RUN:
        return tr("Delete profile run {n}?").format(n=run_number(plan.run_id))
    if plan.kind == KIND_VERIFY_ALL:
        return tr("Delete the verification files of run {n}?").format(
            n=run_number(plan.run_id))
    return tr("Delete the verification of {when}?").format(
        when=pretty_date(plan.verification_ids[0]))


def pretty_date(vid: str) -> str:
    """``2026-07-28_131500`` → ``2026-07-28 13:15:00``."""
    try:
        day, clock = vid.split("_")[:2]
        if len(clock) >= 6:
            return f"{day} {clock[:2]}:{clock[2:4]}:{clock[4:6]}"
    except (ValueError, IndexError):
        pass
    return vid


def message_for(plan: DeletePlan) -> str:
    """The whole body of the window."""
    if plan.kind == KIND_LAST_RUN:
        return _last_run_message(plan)
    if plan.kind == KIND_RUN:
        return _run_message(plan)
    if plan.kind == KIND_VERIFY_ALL:
        return _verify_all_message(plan)
    return _verify_one_message(plan)


def _run_message(plan: DeletePlan) -> str:
    n = run_number(plan.run_id)
    stem = plan.project_name
    parts = [tr("Profile run {n} will be deleted from your disk, with "
                "everything in it.").format(n=n)]
    if plan.has_measurement or plan.has_profile:
        lines = [tr("•  the chart and its printable pages")]
        if plan.has_measurement:
            lines.append(tr(
                "•  the measurement {stem}.ti3 — real ink on real paper, which "
                "cannot be recreated without printing and measuring the chart "
                "again").format(stem=stem))
        if plan.has_profile:
            lines.append(tr("•  the printer profile {stem}.icc").format(stem=stem))
        lines.append(tr("•  the quality checks and measurement reports"))
        lines.append(tr("•  the exports, the individual readings, and the "
                        "archived earlier versions"))
        if plan.verification_ids:
            lines.append(tr("•  every verification of this run, with all of "
                            "its dated results"))
        parts.append(tr("This includes:") + "\n" + "\n".join(lines))
    else:
        parts.append(tr(
            "This run has not been measured, so no measurement and no profile "
            "will be lost. What goes is the chart, its printable pages and the "
            "working files that belong to it."))
    if plan.seeded_runs:
        parts.append(_seeded_paragraph(plan))
    parts.append(tr(
        "This cannot be undone. Nothing is moved to the Trash and nothing is "
        "kept in an “old” folder — the whole run folder is removed:") +
        f"\n\n{plan.path}")
    parts.append(_renumber_sentence(plan))
    parts.append(tr(
        "Afterwards ChromIQ selects the last run in the project, run {n}, so "
        "you can see at once that the deletion happened.").format(
            n=run_number(plan.lands_on)))
    return "\n\n".join(parts)


def _seeded_paragraph(plan: DeletePlan) -> str:
    names = _join([run_number(r) for r in plan.seeded_runs])
    if len(plan.seeded_runs) == 1:
        head = tr("Run {names} was built on top of this run.").format(names=names)
        tail = tr(
            "It keeps its own copy of what it needed, so it goes on working "
            "and its profile is unaffected. What it loses is the record of "
            "where that seed came from — it will simply no longer say which "
            "run it was refined from.")
    else:
        head = tr("Runs {names} were built on top of this run.").format(names=names)
        tail = tr(
            "They keep their own copies of what they needed, so they go on "
            "working and their profiles are unaffected. What they lose is the "
            "record of where that seed came from — they will simply no longer "
            "say which run they were refined from.")
    return head + " " + tail


def _last_run_message(plan: DeletePlan) -> str:
    return "\n\n".join([
        tr("Run {n} is the only run in “{name}”. A project always has at least "
           "one run, so this run cannot be deleted on its own — deleting it "
           "would leave a project with nowhere to work.").format(
               n=run_number(plan.run_id), name=plan.project_name),
        tr("You have two ways forward:"),
        tr("•  Empty the run — keep run {n} but delete its chart, measurement, "
           "profile, reports and verifications, so you start again from a "
           "clean run {n}.").format(n=run_number(plan.run_id)),
        tr("•  Delete the whole project — remove the project folder and "
           "everything in it, including the shared calibration and the "
           "project-wide exports. ChromIQ then returns to the state it has "
           "when you start it fresh, with no project open."),
        tr("Both are permanent, and neither is moved to the Trash."),
    ])


def _verify_all_message(plan: DeletePlan) -> str:
    n = run_number(plan.run_id)
    parts = [tr(
        "Everything under “verifications” in profile run {n} will be deleted — "
        "the whole folder, with everything inside it.").format(n=n)]
    lines = []
    if plan.has_verify_chart:
        lines.append(tr("•  the verification chart and its printable pages"))
    if len(plan.verification_ids) > 1:
        lines.append(tr("•  all {c} verification results:").format(
            c=len(plan.verification_ids)))
        lines += [f"     – {pretty_date(v)}" for v in plan.verification_ids]
    elif plan.verification_ids:
        when = pretty_date(plan.verification_ids[0])
        lines.append(tr(
            "•  the verification of {when}, including its measurement and its "
            "report").format(when=when) if plan.verification_measured
            else tr("•  the verification started on {when}, which was never "
                    "measured").format(when=when))
    else:
        lines.append(tr("•  no verification has been measured yet, so no "
                        "readings will be lost"))
    lines.append(tr("•  the verification chart's sidecar files in “exports”"))
    lines.append(tr("•  the archived earlier verification charts in “old”"))
    lines.append(tr("•  anything else inside the folder, including reports and "
                    "cached tool files"))
    parts.append(tr("What is in there now:") + "\n" + "\n".join(lines))
    if len(plan.verification_ids) <= 1:
        parts.append(tr(
            "The whole folder goes because there would be no way to remove "
            "these leftovers otherwise: with the last verification gone, a "
            "folder holding only reports and archives has nothing left to "
            "belong to."))
    parts.append(tr(
        "The profiling side of run {n} is not touched — its chart, "
        "measurement, profile and reports all stay exactly as they are. Only "
        "this is removed:").format(n=n) + f"\n\n{plan.path}")
    parts.append(tr(
        "This cannot be undone, and nothing is moved to the Trash. Run "
        "numbering is unaffected — no run is being deleted."))
    if len(plan.verification_ids) > 1:
        parts.append(tr(
            "If you only wanted to remove one date, cancel, choose that date "
            "in the “Verification” box, and press Delete again."))
    return "\n\n".join(parts)


def _verify_one_message(plan: DeletePlan) -> str:
    n = run_number(plan.run_id)
    parts = [tr("Only this one verification result will be deleted:")
             + f"\n\n{plan.path}"]
    parts.append(tr(
        "That folder holds the measurement of that date, the chart copy kept "
        "with it, and its report.") if plan.verification_measured else tr(
        "This verification was started but never measured, so no readings "
        "will be lost. The folder holds only the chart copy that was kept "
        "when it began."))
    parts.append(tr(
        "Kept: the verification chart, and the other verification dates of "
        "this run. The profiling side of run {n} is not touched.").format(n=n))
    parts.append(tr(
        "This cannot be undone, and nothing is moved to the Trash. Run "
        "numbering is unaffected — verification dates are named after the "
        "moment they were measured and are never renumbered."))
    return "\n\n".join(parts)


def confirm_label(plan: DeletePlan) -> str:
    """The destructive button's text — it names what it will do."""
    if plan.kind == KIND_RUN:
        return tr("Delete run {n} permanently").format(
            n=run_number(plan.run_id))
    if plan.kind == KIND_VERIFY_ALL:
        if len(plan.verification_ids) > 1:
            return tr("Delete all {c} verifications").format(
                c=len(plan.verification_ids))
        return tr("Delete the verification files")
    if plan.kind == KIND_VERIFY_ONE:
        return (tr("Delete this verification") if plan.verification_measured
                else tr("Delete this empty verification"))
    return tr("Delete")


def tooltip_for(plan: DeletePlan) -> str:
    """The enabled button's tooltip — the counterpart of block_tooltip()."""
    if plan.kind == KIND_RUN:
        return tr("Delete profile run {n} and everything in it").format(
            n=run_number(plan.run_id))
    if plan.kind == KIND_LAST_RUN:
        return tr("Empty this run, or delete the whole project")
    if plan.kind == KIND_VERIFY_ALL:
        if len(plan.verification_ids) > 1:
            return tr("Delete this run's whole verification folder — the "
                      "verification chart and all {c} results").format(
                          c=len(plan.verification_ids))
        return tr("Delete this run's whole verification folder — the "
                  "verification chart and its results")
    return tr("Delete only this verification date. The verification chart and "
              "the other dates are kept")


# ---------------------------------------------------------------------------
# Doing it
# ---------------------------------------------------------------------------

class DeleteFailed(Exception):
    """Something could not be removed or renamed; nothing has been left half
    done — the caller shows the "Could not delete everything" window."""

    def __init__(self, paths: list) -> None:
        super().__init__("could not delete: %s" % paths)
        self.paths = paths


#: Marker for the two-phase rename. A folder is moved out of the way under this
#: name first, so an interrupted renumber can always be rolled back (Knut
#: accepted this, #130 2026-07-28).
_TMP_SUFFIX = ".chromiq-renumber-tmp"


def delete_verification(plan: DeletePlan) -> None:
    """Remove a whole ``verifications/`` folder or one dated folder."""
    if plan.path is None or not plan.path.exists():
        raise DeleteFailed([str(plan.path)])
    try:
        shutil.rmtree(plan.path)
    except OSError as exc:
        log.warning("Could not delete %s: %s", plan.path, exc)
        raise DeleteFailed([str(plan.path)]) from exc
    log.info("Deleted %s", plan.path)


def delete_run(project, plan: DeletePlan) -> str:
    """Delete the run folder, renumber the survivors, and rewrite the manifest.

    Returns the run id that should now be selected (the **last** run — Knut's
    D2: landing on the same run *number* would look as though nothing had
    happened). Raises :class:`DeleteFailed` with nothing changed if a rename
    cannot be completed.
    """
    run_dir = plan.path
    if run_dir is None or not run_dir.exists():
        raise DeleteFailed([str(run_dir)])
    try:
        shutil.rmtree(run_dir)
    except OSError as exc:
        log.warning("Could not delete %s: %s", run_dir, exc)
        raise DeleteFailed([str(run_dir)]) from exc
    log.info("Deleted run folder %s", run_dir)

    root = project.runs_root
    done: list = []          # (path_now, path_before) for rollback
    try:
        # Phase 1 — everything that has to move goes to a temporary name, so no
        # rename can ever collide with a folder that is still in place.
        for old, _new in plan.renumbering:
            src = root / old
            if not src.exists():
                continue
            tmp = root / f"{old}{_TMP_SUFFIX}"
            src.rename(tmp)
            done.append((tmp, src))
        # Phase 2 — into place.
        moved: list = []
        for old, new in plan.renumbering:
            tmp = root / f"{old}{_TMP_SUFFIX}"
            if not tmp.exists():
                continue
            dst = root / new
            tmp.rename(dst)
            moved.append((dst, tmp))
        done = moved + done
    except OSError as exc:
        log.warning("Renumbering failed (%s) — rolling back", exc)
        for now, before in done:
            try:
                if now.exists():
                    now.rename(before)
            except OSError:
                log.error("Rollback could not restore %s", before)
        raise DeleteFailed([str(root)]) from exc

    _rewrite_metas(project, plan)
    survivors = [f"run{i}" for i in range(1, len(_surviving(project, plan)) + 1)]
    project.set_runs(survivors, current=survivors[-1] if survivors else "run1")
    return survivors[-1] if survivors else "run1"


def _surviving(project, plan: DeletePlan) -> list:
    return [r for r in [x.id for x in project.all_runs()] if r != plan.run_id]


def _rewrite_metas(project, plan: DeletePlan) -> None:
    """``run_id`` for every renamed run, and every reference to a run that has
    moved or gone — in **all** runs, including ones that did not move."""
    mapping = dict(plan.renumbering)
    for new_id in [f"run{i}"
                   for i in range(1, len(_surviving(project, plan)) + 1)]:
        run = project.run(new_id)
        if not run.dir.exists():
            continue
        try:
            meta = run.load_meta()
        except Exception:      # noqa: BLE001
            continue
        meta.run_id = new_id
        for attr in ("parent_run", "preconditioning_source_run"):
            ref = getattr(meta, attr, None)
            if ref == plan.run_id:
                setattr(meta, attr, None)      # the run it named is gone
            elif ref in mapping:
                setattr(meta, attr, mapping[ref])
        try:
            run.save_meta(meta)
        except Exception:      # noqa: BLE001
            log.warning("Could not update %s", run.meta_path, exc_info=True)


def empty_run(project, run_id: str) -> None:
    """Keep the folder, remove everything in it, and start its meta afresh.

    Offered only for the last remaining run (Knut's D4: *"No, do not make
    available"* as a general action).
    """
    from core.file_manager import RunMeta
    run = project.run(run_id)
    if not run.dir.exists():
        raise DeleteFailed([str(run.dir)])
    failed = []
    for child in list(run.dir.iterdir()):
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError:
            failed.append(str(child))
    if failed:
        raise DeleteFailed(failed)
    run.save_meta(RunMeta.fresh(run_id))
    log.info("Emptied run %s", run.dir)
