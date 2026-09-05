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
* Nothing is archived to ``old/``: what the user confirms leaves the project.
* **It goes to the Trash — or the Recycle Bin, or the Wastebasket, whichever
  this platform calls it** (Basti, 2026-08-28), which changed the wording of
  every window here. Knut's original ruling was that a delete is permanent, and
  that stood until `shutil.rmtree` was measured doing the opposite of what its
  window promised: one unwritable sub-folder is enough for it to destroy most of
  a project and then raise, so the app said *"Nothing was changed."* over ten
  missing files. A Trash move is a rename — it cannot half-happen, and when
  there is nowhere to put the files it really does change nothing.
* So the windows no longer say "this cannot be undone". They say where the files
  went, and that emptying the Trash is what finally frees the space — which
  matters, because a full disk is half the reason people press Delete.
"""
from __future__ import annotations

import logging
import shutil

from core.trash import move_to_trash, trash_name
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

# Each reason says WHY the button is unavailable *and* what would make it
# available again. A disabled control is exactly where somebody needs the
# remedy, and stating only the fact leaves them stuck (#130, Sebastian's text
# audit of 2026-07-29, accepted by Knut).
_BLOCK_TOOLTIPS = {
    BLOCK_MEASURING: lambda: tr(
        "Not while a measurement is running. It will be available again as "
        "soon as the current measurement finishes or is stopped."),
    BLOCK_NO_PROJECT: lambda: tr(
        "Open or create a project first — there is nothing to delete until a "
        "profile project is loaded."),
    BLOCK_NEW_RUN: lambda: tr(
        "Select an existing profile run to delete. “New run” is not a run yet "
        "— there is nothing on disk to remove"),
    BLOCK_UNKNOWN_RUN: lambda: tr(
        "This profile run no longer exists — it may have been deleted or "
        "renamed outside ChromIQ. Pick another run from the Profile-run bar."),
    BLOCK_NO_VERIFICATIONS: lambda: tr(
        "This profile run has no verification files to delete. Verification "
        "files appear once you have measured a chart with Run type set to "
        "Verification."),
    BLOCK_UNKNOWN_VERIFICATION: lambda: tr(
        "This verification date no longer exists — its folder has gone. Pick "
        "another date, or choose “New verification” to start a fresh check."),
}


def block_tooltip(code: str) -> str:
    return _BLOCK_TOOLTIPS.get(code, lambda: tr(
        "Nothing to delete — this run holds no files yet. Generate a chart "
        "first, and Delete will be able to remove it."))()


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
    #: KIND_RUN only — the dates of the archives in this run's ``old/`` folder
    #: that hold a measurement, and those that hold a profile, oldest first.
    #:
    #: THE RUN THAT LOOKS UNMEASURED IS USUALLY THE ONE WITH THE MOST TO LOSE.
    #: Re-generating a chart on a measured run ARCHIVES the measurement and the
    #: profile into ``old/<date>/`` — Knut's #130 critical, because they cannot
    #: be recreated — and the run's live ``.ti3`` is then gone. Asking the live
    #: paths alone therefore reported such a run as never measured, and the
    #: window told the person that nothing would be lost while deleting two
    #: archived measurements, a profile and both averaging reads. Measured on
    #: screen, 2026-08-28, on the ordinary refinement loop.
    archived_measurements: list = field(default_factory=list)
    archived_profiles: list = field(default_factory=list)
    #: KIND_RUN only — the run keeps the chart a finished measurement was taken
    #: with in ``chart/``; it is the only copy, and Restore Used Chart reads it.
    has_chart_snapshot: bool = False
    #: KIND_RUN only — ``preconditioning.ti3/.icc``, the seed a refinement run
    #: was built from. `reset_chart_artefacts` goes out of its way to preserve
    #: these across a chart rebuild, and Delete removed them without a word.
    has_preconditioning: bool = False


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

    _arch_m, _arch_p = _archives(run)
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
        has_profile=run.profile_icc.exists() or run.artefact(".icm").exists(),
        archived_measurements=_arch_m, archived_profiles=_arch_p,
        has_chart_snapshot=_has_snapshot(run),
        has_preconditioning=_has_precond(run),
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
        return tr("This is the only run in the project, so deleting it would "
                  "leave nothing behind")
    if plan.kind == KIND_RUN:
        return tr("Delete profile run {n}?").format(n=run_number(plan.run_id))
    if plan.kind == KIND_VERIFY_ALL:
        return tr("Delete the verification files of run {n}?").format(
            n=run_number(plan.run_id))
    return tr("Delete the verification of {when}?").format(
        when=pretty_date(plan.verification_ids[0]))


def _archives(run) -> tuple:
    """(dates holding a measurement, dates holding a profile) from ``old/``.

    DATED FOLDERS, NOT FILES. ``old/`` holds one folder per archive event, so a
    run archived three times holds three sessions that may total a dozen files.
    "12 earlier files" tells a person nothing they can act on; three dates do.
    """
    measurements, profiles = [], []
    try:
        old = run.old_dir
        if not old.is_dir():
            return [], []
        for d in sorted(p for p in old.iterdir() if p.is_dir()):
            files = list(d.rglob("*"))
            if any(f.suffix.lower() == ".ti3" for f in files):
                measurements.append(d.name)
            if any(f.suffix.lower() in (".icc", ".icm") for f in files):
                profiles.append(d.name)
    except OSError:
        return measurements, profiles
    return measurements, profiles


def _has_snapshot(run) -> bool:
    """Does ``chart/`` hold the chart a measurement was actually taken with?

    It is the ONLY copy — Restore Used Chart reads it, and nothing else does —
    and no delete window mentioned it.
    """
    try:
        d = run.chart_snapshot_dir
        return d.is_dir() and any(d.iterdir())
    except OSError:
        return False


def _has_precond(run) -> bool:
    """``preconditioning.ti3/.icc`` — the seed a refinement run was built from.

    `Run.reset_chart_artefacts` deliberately preserves these across a chart
    rebuild, and Delete removed them without a word.
    """
    try:
        return run.preconditioning_ti3.exists() or run.preconditioning_icc.exists()
    except OSError:
        return False


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


def _archive_paragraphs(plan: DeletePlan) -> list:
    """What the run's ``old`` folder holds, named by date.

    Two sentences, never one: a dated folder can hold a measurement with no
    profile, so "2 measurements and 1 profiles" is exactly the fault the house
    rule against "(s)" exists to prevent.
    """
    out = []
    m, p = plan.archived_measurements, plan.archived_profiles
    if len(m) == 1:
        out.append(tr(
            "This run also holds one earlier measurement in its “old” folder, "
            "from {date}. It was put there when the chart was last re-made, "
            "because a measurement cannot be recreated without printing and "
            "measuring the chart again. Deleting the run deletes it as well.")
            .format(date=pretty_date(m[0])))
    elif len(m) > 1:
        out.append(tr(
            "This run also holds {n} earlier measurements in its “old” folder, "
            "from {dates}. They were put there each time the chart was re-made, "
            "because a measurement cannot be recreated without printing and "
            "measuring the chart again. Deleting the run deletes all of them.")
            .format(n=len(m), dates=_join([pretty_date(d) for d in m])))
    if len(p) == 1:
        out.append(tr(
            "There is one earlier printer profile in that “old” folder too, "
            "from {date}, and it goes with the rest.")
            .format(date=pretty_date(p[0])))
    elif len(p) > 1:
        out.append(tr(
            "There are {n} earlier printer profiles in that “old” folder too, "
            "from {dates}, and they go with the rest.")
            .format(n=len(p), dates=_join([pretty_date(d) for d in p])))
    return out


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
            "This run has no measurement and no profile in it right now. What "
            "goes is the chart, its printable pages and the working files that "
            "belong to it."))
    # WHAT IS IN old/ COUNTS, IN BOTH BRANCHES. A run whose chart was
    # re-generated after it was measured has its measurement and profile in
    # `old/<date>/` and nothing live, so it read as "never measured" — and the
    # window said so while deleting them.
    parts.extend(_archive_paragraphs(plan))
    if plan.has_chart_snapshot:
        parts.append(tr(
            "It also holds the copy of the chart this run was measured with, "
            "kept in its “chart” folder. That copy is what “Restore Used Chart” "
            "puts back, and there is no other one, so it goes too."))
    if plan.has_preconditioning:
        parts.append(tr(
            "And it holds the pre-conditioning files this run was started "
            "from, which is the measurement a refinement was built on top of. "
            "ChromIQ keeps those even when you re-make the chart, but deleting "
            "the run takes them with it."))
    if plan.seeded_runs:
        parts.append(_seeded_paragraph(plan))
    parts.append(tr(
        "The whole folder for this profile run is moved to your {trash}, so "
        "nothing is destroyed. If you change your mind, open the {trash} and "
        "drag the folder back where it was. ChromIQ does not keep a second copy "
        "in an “old” folder inside the project, and the space on your disk "
        "comes back once you empty the {trash}. This is the folder that goes:")
        .format(trash=trash_name())
        + f"\n\n{plan.path}")
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
           "clean run {n}. That means everything inside the run folder, "
           "including anything kept in its “old” folder from earlier "
           "measurements and the copy of the chart in its “chart” folder.")
           .format(n=run_number(plan.run_id)),
        tr("•  Delete the whole project — remove the project folder and "
           "everything in it: the shared calibration and every earlier one "
           "kept beside it, the project-wide exports, and every run with "
           "everything in its folders. ChromIQ then returns to the state it "
           "has when you start it fresh, with no project open."),
        tr("Both of these move the files to your {trash} rather than "
           "destroying them, so you can open the {trash} and put them back if "
           "you change your mind. Neither one leaves a copy behind in an “old” "
           "folder inside the project, and the space on your disk comes back "
           "once you empty the {trash}.").format(trash=trash_name()),
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
        "The folder is moved to your {trash}, so nothing is destroyed. If you "
        "change your mind, open the {trash} and drag it back where it was. "
        "Your profile runs keep the numbers they have now, because no profile "
        "run is being deleted here.").format(trash=trash_name()))
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
        "The folder is moved to your {trash}, so nothing is destroyed. If you "
        "change your mind, open the {trash} and drag it back where it was. "
        "Your profile runs keep the numbers they have now, and so do the other "
        "verification dates: each one is named after the moment it was "
        "measured, so none of them is ever renumbered.").format(
            trash=trash_name()))
    return "\n\n".join(parts)


def confirm_label(plan: DeletePlan) -> str:
    """The destructive button's text — it names what it will do."""
    if plan.kind == KIND_RUN:
        # NOT "permanently" any more. The body of this very window says the
        # folder is moved to the Trash and explains how to drag it back; the
        # button underneath said "DELETE RUN 2 PERMANENTLY". The two halves of
        # one window disagreed about whether the files survive, and the button
        # is the half people read. Found on German Windows 11.
        return tr("Delete run {n}").format(
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

    def __init__(self, paths: list, reason: str = "") -> None:
        super().__init__("could not delete: %s" % paths)
        self.paths = paths
        #: A plain-language sentence for the window, when there is one to give.
        #: Empty for the rename failures, which have their own wording.
        self.reason = reason


#: Marker for the two-phase rename. A folder is moved out of the way under this
#: name first, so an interrupted renumber can always be rolled back (Knut
#: accepted this, #130 2026-07-28).
_TMP_SUFFIX = ".chromiq-renumber-tmp"


def delete_verification(plan: DeletePlan) -> None:
    """Remove a whole ``verifications/`` folder or one dated folder."""
    if plan.path is None or not plan.path.exists():
        raise DeleteFailed([str(plan.path)])
    # TO THE TRASH, NOT DESTROYED (Basti, 2026-08-28). `rmtree` removes what it
    # can reach and raises only at the end, so one unwritable child leaves a
    # half-destroyed folder behind a message saying nothing was changed.
    res = move_to_trash(plan.path)
    if not res.ok:
        raise DeleteFailed([str(plan.path)], reason=res.reason)
    log.info("Moved %s to the Trash", plan.path)


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
    # TO THE TRASH — see `delete_verification`. This one matters most: the
    # renumbering below assumes the run really is gone, and a half-deleted run
    # folder would be renumbered around.
    res = move_to_trash(run_dir)
    if not res.ok:
        raise DeleteFailed([str(run_dir)], reason=res.reason)
    log.info("Moved run folder %s to the Trash", run_dir)

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
        # `duplicated_from` belongs here too: it names a run by id, and after a
        # delete the ids are renumbered, so an un-fixed value points at whatever
        # run now holds that number — or at the run itself.
        for attr in ("parent_run", "preconditioning_source_run",
                     "duplicated_from"):
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
    # ONE MOVE, NOT ONE PER CHILD. Trashing the children one at a time can stop
    # half way — measured: 2 of 7 gone, the `.icc` and the `.ti1` among them,
    # behind a message that read "nothing has been deleted and everything is
    # still exactly where it was". So the whole folder goes in a single move and
    # is then recreated empty, which is what "empty the run" means anyway. The
    # run keeps its id and its place in the numbering because the folder is
    # remade under the same name.
    res = move_to_trash(run.dir)
    if not res.ok:
        raise DeleteFailed([str(run.dir)], reason=res.reason)
    # THE GUARD HAS TO COVER THE WHOLE REPAIR, not just the mkdir. Writing the
    # fresh meta.json was left outside it, so a folder that could not be
    # recreated took the very next line down with a `PermissionError` — out of a
    # button's slot, which aborts ChromIQ. Measured through the real button:
    # exit 134, with the run already in the Trash. The contents are safe either
    # way; what is left is an empty shell that `Run.ensure_dir` makes on the
    # next use, and that is not worth losing the app over.
    try:
        run.dir.mkdir(parents=True, exist_ok=True)
        run.save_meta(RunMeta.fresh(run_id))
    except OSError as exc:
        log.warning("Emptied %s but could not put an empty run back: %s",
                    run.dir, exc)
        raise DeleteFailed([str(run.dir)], reason=tr(
            "The contents of this run are in your {trash}, so nothing has been "
            "lost. ChromIQ could not put an empty run folder back in their "
            "place, though, which usually means the project folder is "
            "read-only. The run will be remade the next time you use it."
        ).format(trash=trash_name())) from exc
    log.info("Emptied run %s", run.dir)
