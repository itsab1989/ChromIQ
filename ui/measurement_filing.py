"""Where a measurement goes, asked once and answered in one place.

§I.9 of `docs/design/unified_measurement_management.md`. Lifted out of
`ui/tabs/tab_profile.py` so that Check & Refine can ask the SAME question with
the same window rather than growing a second copy of it — that tab has been
importing all along, through a route that created a project without asking.

The lift is the point. `tab_profile.py` records that the run picker's signal
was once left unconnected and "EVERY import went to 'a new run' no matter what
was selected on screen"; a second copy of this code is exactly how that comes
back.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core.i18n import tr
from ui.tooltip_button import InfoDialog
from ui.widgets import fit_message_box_buttons, spread_message_box_buttons, fit_button_width

log = logging.getLogger(__name__)


def offer_import_into_a_project(parent, measurement: Path, *,
                                accent: str = "",
                                extra_answers=(),
                                on_filed=None):
    """Ask where a measurement should go, and put it there.

    Returns True when it has been dealt with (the caller stops), False to let
    the caller's own fallback run, or
    :data:`ui.dialogs.project_picker.IN_PLACE` when the person asked for the
    file to be used where it lies. THREE outcomes, not two: a boolean cannot
    say "handled, but not filed", and squeezing it into one would put the
    caller back to guessing.
    """
    """§I.9 — ask where this measurement should go, and put it there.

    Returns True when it has been filed (the caller stops), False to let the
    old "make a new project for it" behaviour run.

    THE QUESTION IS ASKED BY ONE BOX, not by a fork of two dialogs. A name
    that already belongs to a project means "file it in there"; a name that
    does not means "make that project". That is §S4.7's own structure and
    the structure both loaders were given, so a person meets the same
    question in the same words wherever they are — and with a project open
    the box arrives pre-filled with its name, so filing into the project you
    are looking at costs one Continue and no typing.
    """
    from PyQt6.QtWidgets import QMessageBox

    from core.file_manager import peek_project
    from ui.dialogs.name_prompt import ask_for_project_name
    from workflow.measurement_import import assess

    # ASKED BEFORE A WINDOW IS DRAWN. `file_into_project` checks this too, but
    # it is only reached after the person has answered the picker — so a caller
    # that forgot the argument put the whole question on screen and then died
    # on the answer. The contract belongs at the door.
    if on_filed is None:
        raise TypeError(
            "offer_import_into_a_project needs on_filed: the caller must say "
            "what to do with the copy it would file")

    ctl = getattr(parent, "_target_ctl", None)
    fm = getattr(ctl, "_fm", None)
    if fm is None:
        return False                      # no project machinery: old path

    open_name = ""
    try:
        if fm.is_named():
            open_name = Path(fm.working_dir()).name
    except OSError:
        open_name = ""

    def _literal_root(name: str) -> "Path | None":
        """The folder of exactly that name, when there is one.

        The same sanitising trap as `file_into_project`: typing the name the
        picker just showed you — "Demo-Report-Matrix copy" — was reported FREE,
        because the check asked about the sanitised twin. The person was then
        told they were making a new project while looking at the old one."""
        raw = (name or "").strip()
        if not raw:
            return None
        try:
            cand = Path(fm.root_dir()) / raw
            return cand if (cand / "project.json").is_file() else None
        except OSError:
            return None

    def _exists(name: str) -> bool:
        if _literal_root(name) is not None:
            return True
        root = fm.resolved_root_for_name((name or "").strip())
        try:
            return root is not None and (root / "project.json").is_file()
        except OSError:
            return False

    # THE LIST FIRST, WHEN THERE IS ONE TO SHOW.
    # Typing beats picking only if you remember the name, and there was no
    # way to see the list at all — ChromIQ has no project chooser anywhere,
    # Open Project being a file dialog on `project.json`. So: pick from what
    # is in the working folder, or say you want a new one and answer that in
    # the window that already asks it. Cancel is a third answer and means
    # cancel: a Cancel that quietly made a new project would be how somebody
    # ends up with a project they never asked for.
    from ui.dialogs.project_picker import (IN_PLACE, NEW_PROJECT,
                                            choose_project, list_projects)
    _in_place = "check_in_place" in tuple(extra_answers or ())
    # THE BODY SAYS WHAT EACH ANSWER COSTS. Filing keeps the work together;
    # working in place keeps nothing but is nobody's business but the user's,
    # so the sentence for it is only shown where it is offered.
    _body = tr("This measurement is not in one of your projects yet. Choose "
               "the project it belongs to and ChromIQ will open it and ask "
               "which run to file it in, so everything it produces is kept "
               "with the rest of that work. The file you picked stays where "
               "it is, and a copy is filed.")
    if _in_place:
        _body = tr("This measurement is not in one of your projects yet. "
                   "Choose the project it belongs to and ChromIQ will open it "
                   "and ask which run to file it in, so the check and "
                   "everything it produces are kept with the rest of that "
                   "work. Or check the file where it is, and the report is "
                   "written next to it instead, with no project and no run to "
                   "look it up in later. Either way the file you picked is "
                   "never moved or changed.")
    picked = choose_project(
        parent, fm.root_dir(),
        title=tr("Where should this measurement go?"),
        body=_body, accent=accent, offer_in_place=_in_place)
    if picked == IN_PLACE:
        return IN_PLACE                      # the caller works where it lies
    if picked is None:
        # CANCEL IS CANCEL, whether the list had anything in it or not. The
        # `and list_projects(...)` was only ever right while an empty folder
        # drew no window at all; now that it does, a new user's very first
        # import answered Cancel and was met by the name box instead.
        return True                          # cancelled at the list
    if picked and picked != NEW_PROJECT:
        # The folder the picker listed, not a name to be re-derived.
        return file_into_project(parent, picked, measurement, fm, ctl,
                                 accent=accent, on_filed=on_filed,
                                 root=Path(fm.root_dir()) / picked)

    name = ask_for_project_name(
        parent, prefill=open_name,
        body=tr("Where should this measurement go?\n\nType the name of a "
                "project you already have and ChromIQ files the measurement "
                "in it. Type a new name and ChromIQ makes that project and "
                "puts the measurement in its first run.\n\nEither way the "
                "file you picked stays where it is, and a copy is filed."),
        exists=_exists, accent=accent)
    if not name:
        # CANCEL MEANS NOTHING HAPPENS. It used to mean "nothing happens" only
        # when a project was already open, and otherwise fell through to the
        # old `resolve_ti3` route -- so answering Cancel to "Where should this
        # measurement go?" was met by a DIFFERENT question, "Copy Chart Files",
        # about a project the person had just declined to choose. Now that the
        # door asks properly, the answer has to be taken (Basti, 2026-09-01).
        return True

    if not _exists(name):
        # A NEW PROJECT, MADE WITH THE NAME THAT WAS JUST TYPED.
        #
        # This was `return False  # a new project: the old path`, and the old
        # path asked for the name a SECOND time — in a box that arrived empty,
        # called the project a "profile", and showed a literal `<name>` in the
        # folder it promised to use. The person's first answer was thrown away,
        # and the project that was eventually made was never opened, so ChromIQ
        # finished by telling them to go and load it (R3 review F1 + F2, driven
        # again here 2026-09-02).
        #
        # One question, asked once, and the same ending as the other answer to
        # it — see `finish_the_import`, which both branches now end on.
        return make_new_project_and_file(parent, name, measurement, fm, ctl,
                                         accent=accent, on_filed=on_filed)
    return file_into_project(parent, name, measurement, fm, ctl,
                             accent=accent, on_filed=on_filed,
                             root=_literal_root(name))

def run_the_project_is_on(root) -> "str | None":
    """Which run a project's manifest names, read without opening it.

    A named function because the first version of the restore asked
    `ProjectPeek` for `.current_run` — a field that does not exist; the field
    is `run_id` — so it silently answered None every time and the whole restore
    was dead code that read as a fix (challenge round 4, 2026-09-01). One
    expression, used by the code and by the test that guards it.
    """
    from core.file_manager import peek_project
    try:
        return getattr(peek_project(Path(root)), "run_id", None) or None
    except (OSError, ValueError):
        return None


def _undo_the_run(proj, made_here, was_current) -> None:
    """Undo a run this import made, and put `current_run` back where it was.

    `_discard_run` restores the manifest to the LAST run in the list, which is
    only right when that is where the person was. Import into a two-run project
    and be refused, and it moved them from run 1 to run 2 under a window saying
    nothing had been changed.
    """
    if made_here is None:
        return
    try:
        proj._discard_run(made_here, just_created=True)
    except Exception:      # noqa: BLE001 — never lose the message
        log.warning("import: could not undo the run it made", exc_info=True)
        return
    if not was_current:
        return
    try:
        # `current_run` is a METHOD on Project, and the same file calls it with
        # parentheses eighty lines earlier. Without them this raised
        # AttributeError the moment the line above started working.
        if proj.current_run().id != was_current:
            proj.set_current_run(was_current)
    except Exception:      # noqa: BLE001 — the run is gone either way
        log.warning("import: could not put current_run back to %s",
                    was_current, exc_info=True)


def _cannot_file(parent, reason: str, *, project: str = "") -> bool:
    """Say the filing did not happen, and why. Always returns True — handled.

    Every one of these used to be an exception escaping a Qt slot, which is not
    a log line: PyQt6 calls `qFatal()` and the process ends, mid-import, with
    whatever was on screen. Four separate causes reached it — a manifest that
    will not parse, a folder that cannot be written to, a run that cannot be
    made, a project that would not open.
    """
    InfoDialog(
        tr("ChromIQ could not file the measurement"),
        tr("Nothing has been changed, and your own file is untouched where it "
           "is.\n\nThe reason: {reason}.\n\nThis usually means the folder is "
           "read-only, the disk is full, it lives on a drive or share that is "
           "no longer connected, or the project's own {manifest} file has been "
           "damaged. Check the project and try again, or choose another one."
           ).format(reason=reason, manifest="project.json"),
        parent, min_width=580).exec()
    if project:
        log.warning("import: could not file into %s: %s", project, reason)
    return True


#: `open_the_project` was not able to even try, and has said nothing — there is
#: no Create Chart tab to perform the open. Distinct from `None`, which means it
#: tried, failed, and has already put a window on screen. Two outcomes that a
#: bare `None` cannot tell apart, and the caller has to: one is "run your own
#: fallback", the other is "stop, the person has been told".
NO_MACHINERY = object()


def open_the_project(parent, fm, name: str, root: Path):
    """Open the project at *root* — the WHOLE open — and say where it landed.

    Returns the root the project is actually open at, ``None`` when the open
    was attempted and failed (a window has already said so), or
    :data:`NO_MACHINERY` when there is no Create Chart tab to perform it with.

    LIFTED OUT SO THE TWO DOORS CANNOT DRIFT APART, which is the whole shape of
    the fault this was written for. Answering "Where should this measurement
    go?" with the name of a project that EXISTS ran this and ended up inside
    that project; answering with a name that does not exist made the project
    and never opened it, so ChromIQ told the person to go and load the project
    it had just made for them, with `working_dir()` naming a folder that had
    never been created (driven, 2026-09-02, `shots/before-new-bar.png`).
    """
    root = Path(root)
    # THE WHOLE OPEN, not a cut-down one — see `open_project_manifest`.
    #
    # AND IT HAS TO BE CHECKED AFTERWARDS. `open_project_manifest` returns None
    # whether it opened the project or gave up, and nothing looked: with a
    # symlinked project — an external drive, a NAS, a Dropbox folder — the
    # person was asked an unrelated question, and answering it left the
    # measurement filed into WHATEVER PROJECT WAS OPEN while every window named
    # the one they picked. With nothing open at all, ChromIQ invented a
    # `Printer_Paper_Type_Instr_<timestamp>` project to put it in.
    #
    # `except OSError` was also too narrow. `Project.load` parses the manifest,
    # and `json.JSONDecodeError` is a ValueError — so a truncated `project.json`
    # (and `save_manifest` writes non-atomically, so truncation is an ordinary
    # accident) took the whole app down from inside a Qt slot. Every other
    # reader in ChromIQ already catches it; only the importer did not.
    try:
        if fm.is_named() and Path(fm.working_dir()) == root:
            return root                      # already open, nothing to do
        tab_chart = getattr(parent.window(), "_tab_chart", None)
        if tab_chart is None:
            return NO_MACHINERY
        _before = Path(fm.working_dir()) if fm.is_named() else None
        tab_chart.open_project_manifest(root / "project.json")
        _after = Path(fm.working_dir()) if fm.is_named() else None
        # NOT "did it open AT `root`" — "did it open". A project reached
        # through a symlink (an external drive, a NAS, a Dropbox folder)
        # goes through the copy-in flow and legitimately ends up open at a
        # DIFFERENT root, and comparing against the path we asked for then
        # refused a project that had opened perfectly well — after
        # duplicating it onto the disk — with a window blaming a read-only
        # folder or a damaged project.json. All of it false.
        if _after is None or _after == _before:
            _cannot_file(parent,
                         tr("“{name}” could not be opened").format(name=name),
                         project=str(root))
            return None
        return _after                        # …and file into the one that is open
    except (OSError, ValueError) as exc:
        _cannot_file(parent, str(exc) or type(exc).__name__, project=str(root))
        return None


def finish_the_import(ctl, run_id: str, filed: Path, on_filed) -> None:
    """The tail EVERY successful import ends on, whichever door it came in by.

    Point the bar at the run the measurement went into, refresh it, and hand
    the filed copy back to the tab that asked. One function rather than two
    copies of three calls, because the two doors having their own endings is
    precisely how one of them ended with the app saying "load a profile
    project" about the project it had just made.

    THE RUN TYPE IS PART OF THE ANSWER, AND IT WAS NEVER SET.

    It was inherited from whatever the project was last left on. Open a
    project whose bar was on Verification and the measurement was filed
    while the app still called this a verification run — with Build
    Profile disabled (`ui/main_window.py:1590`), so the person could not
    even reach the tab they had just imported from.

    An import from Build Profile is a PROFILING import by construction:
    that tab is disabled for verification runs, so the tab somebody is
    standing on has already said which act this is. Say it out loud
    rather than inheriting it, and point the bar at the run that was
    chosen so "Location being edited" names the folder the file went to.
    """
    if ctl is not None:
        try:
            ctl.set_run_type("profiling")
            ctl.set_verification_id("")
            ctl.set_profile_run(run_id)
        except Exception:      # noqa: BLE001 — never block the import
            log.warning("import: could not point the bar at %s", run_id,
                        exc_info=True)
    if ctl is not None and hasattr(ctl, "project_replaced_on_disk"):
        # WRAPPED, like the controller call above. It sat bare one line before
        # the hand-back, so a controller that raised left the copy filed on
        # disk with nothing pointing at it — the import happened and the tab
        # showed the old file. Refreshing the bar is a courtesy; it may not
        # cost the person the thing they just filed.
        try:
            ctl.project_replaced_on_disk()
        except Exception:      # noqa: BLE001 — never block the import
            log.warning("import: could not refresh the target bar",
                        exc_info=True)
    # THE FILED COPY IS HANDED BACK, NOT POKED INTO A TAB. This used to call
    # `parent.set_ti3_path(...)` and `parent.ti3_manually_loaded.emit()`, which
    # only Build Profile has. When Check & Refine became the third import door
    # it inherited those two lines and aborted on the SUCCESS path — after the
    # copy was made, the run created and the manifest written, so the user
    # restarted into a run they never asked for. Every caller now says what it
    # wants done with the copy, and nothing here knows a tab's private API.
    on_filed(filed)


def make_new_project_and_file(parent, name: str, measurement: Path, fm, ctl,
                              *, accent: str = "", on_filed=None) -> bool:
    """Make the project the person just named, put the measurement in it, and
    open it — the other half of `file_into_project`, and its equal.

    THE NAME THEY TYPED IS THE NAME THAT IS USED. This branch used to
    `return False  # a new project: the old path`, throwing the answer away and
    letting the caller's `resolve_ti3` fallback ask for it a SECOND time — in a
    box that arrived empty, called the project a "profile", and showed a literal
    `<name>` in the path it promised to use. One question had two answers and
    two different end states (R3 review, F1 and F2, 2026-09-02).

    The disk work is still `resolve_ti3`'s, handed the name instead of asking
    for it: that keeps `_copy_ti3_only`'s archive-never-delete rule, the sibling
    `.icc` carry, and the sibling `.ti2` chart import, none of which would
    survive being written a second time here. What is new is the ENDING, and it
    is the same object `file_into_project` ends on.
    """
    from ui.ti2_loader import _project_root_for, resolve_ti3

    if on_filed is None:
        raise TypeError(
            "make_new_project_and_file needs on_filed: the caller must say "
            "what to do with the copy it files")

    root_dir = Path(fm.root_dir())
    # THE TAB'S OWN SETTINGS, which is the object every other `resolve_ti3`
    # caller hands it. `resolve_ti3` reads exactly one key from it,
    # `custom_output_path`, and the FileManager reads the same key from the same
    # object for `root_dir()` — so the two cannot disagree. The FileManager is
    # the fallback for a caller that has no settings of its own.
    settings = getattr(parent, "_settings", None) or fm._settings
    try:
        filed = resolve_ti3(parent, measurement, settings, name=name)
    except (OSError, ValueError) as exc:
        return _cannot_file(parent, str(exc) or type(exc).__name__, project=name)
    if filed is None:
        # The one question this route can still raise — a folder of that name
        # that is not a project, and whether to archive it — was answered
        # Cancel. Nothing was created, and nothing more is asked.
        return True

    filed = Path(filed)
    root = _project_root_for(filed, root_dir)
    if root is None:
        # The copy landed somewhere with no manifest above it. Nothing to open
        # and nothing to point the bar at, but the file IS on disk, so it is
        # handed back rather than lost.
        log.warning("import: filed %s but found no project above it", filed)
        finish_the_import(ctl, "", filed, on_filed)
        return True

    opened = open_the_project(parent, fm, name, root)
    if opened is None:
        return True                      # it said so on screen
    if opened is NO_MACHINERY:
        # No Create Chart tab to open with. The measurement is filed and the
        # project is on disk; hand the copy back rather than pretend nothing
        # happened, and leave the bar alone because there is nothing to point.
        finish_the_import(ctl, "", filed, on_filed)
        return True

    # WHICH RUN IT WENT INTO, taken from the project that is now open rather
    # than assumed to be run 1. `Project.create` makes one run and files there,
    # but reading it back is what makes this true if that ever changes.
    run_id = ""
    try:
        proj = fm.project()
        run_id = next((r.id for r in proj.all_runs()
                       if r.measurement_ti3 == filed), "")
        if not run_id:
            run_id = proj.current_run().id
    except Exception:      # noqa: BLE001 — the file is filed either way
        log.warning("import: could not name the run %s went into", filed,
                    exc_info=True)
    finish_the_import(ctl, run_id, filed, on_filed)
    return True


def file_into_project(parent, name: str, measurement: Path, fm, ctl,
                      *, accent: str = "", on_filed=None, root=None) -> bool:
    """Open *name* (if it is not already open) and file the measurement in
    a run of it. Shared by the list and the name box, so both answers reach
    exactly the same act."""
    from PyQt6.QtWidgets import QMessageBox
    from core.file_manager import peek_project as _peek
    from workflow.measurement_import import assess

    # ASKED BEFORE ANYTHING IS TOUCHED. The old version reached into ONE tab's
    # API at the very end, after the copy, the run and the manifest — so the
    # tab that did not have that API aborted the app with the project already
    # changed on disk. The question "what should happen to the copy?" is now
    # answered before the first byte moves.
    if on_filed is None:
        raise TypeError(
            "file_into_project needs on_filed: the caller must say what to do "
            "with the copy it files")

    made_here = None       # a run this call created, to undo if it refuses
    was_current = None     # …and the run the project was ON before we did
    # A NAME THE PERSON PICKED IS A FOLDER; A NAME THEY TYPED IS A NAME.
    #
    # The picker lists real folders and hands back `child.name` verbatim, but
    # this used to throw that away and re-derive the path through
    # `resolved_root_for_name`, which SANITISES. A folder called
    # "Demo-Report-Matrix copy" — Finder's Duplicate, an unzipped hand-off, a
    # Dropbox conflicted copy — became "Demo-Report-Matrix-copy", which does
    # not exist, so ChromIQ made an empty project of that name, switched to it,
    # and then refused with "has no chart in it yet" about the row that had
    # just said "2 runs, 1 verification". Where the sanitised twin DID exist,
    # the measurement was filed into the wrong project while the window named
    # the one that had been picked.
    #
    # So the picker passes the folder it listed and it is used as it stands;
    # only a typed name is resolved, where sanitising is exactly right.
    root = Path(root) if root is not None else fm.resolved_root_for_name(name)
    # THE WHOLE OPEN, and the SAME one the new-project door performs — see
    # `open_the_project`, which this used to hold inline while the other door
    # had no open at all.
    _opened = open_the_project(parent, fm, name, root)
    if _opened is None:
        return True                      # it said so on screen
    if _opened is NO_MACHINERY:
        return False                     # no Create Chart tab: the old path
    root = _opened

    try:
        proj_probe = fm.project()
        # WHICH RUN THE PROJECT WAS ON, so a refusal can put it back. Undoing
        # the run restores `current_run` to the LAST run in the list, which is
        # not necessarily the one the person was looking at: import into a
        # two-run project, be refused, and the project had quietly moved from
        # run 1 to run 2 under a window saying nothing had been changed.
        was_current = run_the_project_is_on(proj_probe.root)
    except (OSError, ValueError) as exc:
        return _cannot_file(parent, str(exc) or type(exc).__name__,
                            project=str(root))
    del proj_probe

    # WHICH RUN? ASK — DO NOT INHERIT ONE.
    #
    # Two ways of guessing were both wrong. The manifest's `current_run` is
    # whatever that project was last left on, which for a project the person
    # has just NAMED they never chose and cannot see. The bar's run is right
    # when the project was already open and meaningless the moment ChromIQ
    # opened one for them — it points at the manifest again.
    #
    # So the question is put, with §S4.7's own picker (`_build_run_picker`),
    # in §S4.7's own order: **a new run first**, because it is the one
    # answer that cannot cost anything, then every run that exists with what
    # each already holds.
    from core.file_manager import peek_project as _peek
    proj = fm.project()
    run = None
    tab_chart = getattr(parent.window(), "_tab_chart", None)
    picker = None
    chosen: list = [""]
    if tab_chart is not None and hasattr(tab_chart, "_build_run_picker"):
        try:
            picker, chosen = tab_chart._build_run_picker(_peek(proj.root))
        except Exception:      # noqa: BLE001 — fall back to asking nothing
            picker, chosen = None, [""]
    if picker is not None:
        # CONNECT IT, OR IT IS A DECORATION.
        # `_build_run_picker` hands back the combo and a one-element list it
        # writes the choice into — but only if somebody wires the signal.
        # §S4.7 does; this did not, so `chosen[0]` kept the value it had when
        # the window opened and EVERY import went to "a new run" no matter
        # what was selected on screen. Driven: Run 2 highlighted at the
        # moment of clicking, measurement filed into Run 6.
        picker.currentIndexChanged.connect(
            lambda _i: chosen.__setitem__(0, picker.currentData() or ""))
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.NoIcon)
        _t = tr("Where should the measurement go?")
        box.setWindowTitle(_t)
        box.setText(_t)
        box.setInformativeText(tr(
            "Choose the run in “{name}” to file it in. A new run leaves "
            "everything already there untouched.").format(name=name))
        # THE BUTTON NAMES THE RUN IT WILL USE, and follows the picker.
        #
        # It said "File it here", and "here" reads as the run the person is
        # already looking at -- which is the one thing it never means: the
        # whole point of this window is that the combo above it may be
        # pointing somewhere else (Basti, 2026-08-31). Naming the run
        # outright means the button and the combo cannot disagree, and
        # nobody has to look up to check what "here" refers to.
        _go = box.addButton(tr("File it in a new run"),
                            QMessageBox.ButtonRole.AcceptRole)
        _stop = box.addButton(tr("Cancel"),
                              QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(_stop)

        def _name_the_run() -> None:
            """Say which run, in the picker's own words."""
            text = picker.currentText().strip()
            run_id = (picker.currentData() or "").strip()
            if not run_id:
                label = tr("File it in a new run")
            elif text:
                # The picker already carries the translated "Run 2".
                label = tr("File it in {run}").format(run=text)
            else:
                label = tr("File it in the selected run")
            _go.setText(label)
            # RE-FIT EVERY TIME. The label changes length as the picker
            # moves, and a button sized for "a new run" clips "Run 12".
            fit_button_width(_go)

        picker.currentIndexChanged.connect(lambda _i: _name_the_run())
        _name_the_run()
        fit_message_box_buttons(box)
        spread_message_box_buttons(box, order=[_go, _stop])
        if hasattr(tab_chart, "_attach_run_picker"):
            tab_chart._attach_run_picker(
                box, picker, label=tr("File the measurement in:"))
        box.exec()
        if box.clickedButton() is not _go:
            return True                      # cancelled; nothing touched
    want = (chosen[0] or "").strip()
    if want:
        # `all_runs()`, not `runs()`. `Project` has no `runs()` at all, so
        # this raised AttributeError into the guard above and fell through
        # to "a new run" — which is why choosing a run appeared to work and
        # never did.
        run = next((r for r in proj.all_runs() if r.id == want), None)

    # A NEW RUN NEEDS THE CHART, OR NOTHING CAN BE CHECKED AGAINST IT.
    #
    # "A new run" used to mean `proj.new_run()` — an EMPTY folder. With no
    # chart in it `assess()` has nothing to compare against: the patch count
    # is unknown, the identity check cannot run, and the import accepts
    # ANY file in silence. Driven: a six-patch file bearing no relation to
    # anything went into a real project with not one word on screen.
    #
    # So a new run is made the way §I.9 says a run is made for an import:
    # `duplicate_run(source, groups=("chart",))` — the chart the measurement
    # is supposed to be OF, and nothing else. Where there is no source run
    # to take a chart from, the import is refused rather than filed blind.
    if run is None:
        source = None
        try:
            source = proj.current_run()
        except Exception:      # noqa: BLE001
            source = None
        if source is None or not source.chart_ti2.is_file():
            InfoDialog(
                tr("There is no chart to check this measurement against"),
                tr("A measurement is filed against the chart it was made "
                   "from, and “{name}” has no chart in it yet.\n\nMake or "
                   "load the chart first, then import the measurement — "
                   "ChromIQ can then tell you whether the two match."
                   ).format(name=name), parent, min_width=560).exec()
            return True
        try:
            run = proj.duplicate_run(source, ("chart",))
        except (OSError, ValueError) as exc:
            # `duplicate_run`'s own rollback sets `current_run = runs[-1]`, so
            # a failure here MOVES the person to another run — under a window
            # whose first sentence is "Nothing has been changed". Every one of
            # these handlers has to put it back.
            _undo_the_run(proj, made_here, was_current)
            # MAKING THE RUN IS A WRITE, AND IT RE-RAISES. The copy below is
            # guarded and this was not, so a read-only folder, a full disk or a
            # disconnected share killed the app one step earlier than the fault
            # that guard was written for — same journey, different line.
            return _cannot_file(parent, str(exc) or type(exc).__name__,
                                project=name)
        made_here = run

    # …AND SO DOES A RUN THE PERSON PICKED. The guard above sat inside
    # `if run is None:`, so it protected one branch of two: choosing an
    # EXISTING run that happens to hold no chart accepted anything at all,
    # in silence. That is the same "a six-patch file bearing no relation to
    # anything went into a real project" fault §I.9 says was fixed, still
    # live on the other road into this function (found by a challenge
    # round, 2026-09-01).
    if run is not None and not run.chart_ti2.is_file():
        _run_name = tr("Run {n}").format(
            n=getattr(run, "number", None) or run.id.replace("run", ""))
        InfoDialog(
            tr("There is no chart to check this measurement against"),
            tr("A measurement is filed against the chart it was made "
               "from, and {run} has no chart in it yet.\n\nMake or load "
               "the chart in that run first, or choose a run that already "
               "has one, and ChromIQ can then tell you whether the two "
               "match.").format(run=_run_name),
            parent, min_width=560).exec()
        return True

    # §I.9: A RUN THAT ALREADY HOLDS A MEASUREMENT IS NOT DISPLACED.
    #
    # This wrote straight over `run.measurement_ti3` — no archive, nothing
    # in the Trash — in the very change whose purpose was to stop exactly
    # that happening on three other routes. Driven on a real project: the
    # measurement was gone, and the run's `.icc` and two verification
    # reports were left describing a measurement that no longer existed.
    # The rule was written into §I.9 hours before the code was: the road to
    # a second result is a NEW PLACE to put it.
    if run.measurement_ti3.is_file():
        try:
            plan = proj.duplicate_run_plan(run, ("chart",))
        except (OSError, ValueError) as exc:
            _undo_the_run(proj, made_here, was_current)
            return _cannot_file(parent, str(exc) or type(exc).__name__,
                                project=name)
        n_files = sum(len(files) for _g, files, _s in plan)
        # "Run 2", not "Run run2" — the same translated label §S4.7 uses.
        _run_label = tr("Run {n}").format(
            n=getattr(run, "number", None) or run.id.replace("run", ""))
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.NoIcon)
        _t = tr("That run already has a measurement")
        box.setWindowTitle(_t)
        box.setText(_t)
        box.setInformativeText(tr(
            "{label} already holds a measurement, and ChromIQ does not "
            "write over one.\n\nInstead it can make a new run beside it "
            "with a copy of the same chart ({n} chart files), and file the "
            "measurement you are importing there. Nothing in {label} is "
            "touched.").format(label=_run_label, n=n_files))
        _go = box.addButton(tr("Make a new run"),
                            QMessageBox.ButtonRole.AcceptRole)
        _stop = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(_stop)
        # THE TWO HOUSE RULES FOR EVERY WINDOW, and this one had neither.
        # `fit_message_box_buttons` sizes each button to the words it will
        # actually paint — without it "Make a new run" came out as "lake a
        # new ru", clipped at both ends, which is the very fault Knut
        # reported on the Delete windows (#130) and had these helpers
        # written for. `spread_message_box_buttons` puts CANCEL ON THE FAR
        # RIGHT, never between the safe answer and the one that acts.
        fit_message_box_buttons(box)
        spread_message_box_buttons(box, order=[_go, _stop])
        box.exec()
        if box.clickedButton() is not _go:
            return True                      # cancelled; nothing touched
        try:
            run = proj.duplicate_run(run, ("chart",))
        except (OSError, ValueError) as exc:
            _undo_the_run(proj, made_here, was_current)
            return _cannot_file(parent, str(exc) or type(exc).__name__,
                                project=name)
        made_here = run

    verdict = assess(measurement, run.chart_ti2)
    if not verdict.ok:
        # AND THE PROMISE HAS TO BE TRUE. This window says "nothing has
        # been changed" while a run made moments earlier was still on disk
        # and counted in `project.json` — driven, Run 4 created by an
        # import that was then refused (found by a challenge round,
        # 2026-09-01). A run that existed for a fraction of a second and
        # never held anything is undone, which is exactly what
        # `_discard_run(just_created=True)` is for; it refuses to remove a
        # folder that turns out to hold work.
        _undo_the_run(proj, made_here, was_current)
        InfoDialog(
            tr("This measurement does not belong to that chart"),
            tr("ChromIQ did not file it, and nothing has been changed.\n\n"
               "The reason: {reason}.").format(reason=verdict.reason),
            parent, min_width=560).exec()
        return True
    import shutil
    try:
        shutil.copy2(measurement, run.measurement_ti3)
    except (OSError, ValueError) as exc:
        # A FOURTH DOOR THAT KILLED THE APP. A read-only folder, a stale
        # network share or a full disk raised out of `copy2` inside a Qt slot
        # and ended the process. Filing into a place the app cannot write is
        # an ordinary thing to get wrong, and it must end in a sentence.
        log.warning("import: could not copy the measurement into %s",
                    run.measurement_ti3, exc_info=True)
        _undo_the_run(proj, made_here, was_current)
        InfoDialog(
            tr("ChromIQ could not write into that project"),
            tr("The measurement has not been filed, and nothing has been "
               "changed. Your own file is untouched where it is.\n\n"
               "The reason: {reason}.\n\nThis usually means the folder is "
               "read-only, the disk is full, or it lives on a drive or share "
               "that is no longer connected. Check the folder and try again, "
               "or choose another project."
               ).format(reason=exc.strerror or exc),
            parent, min_width=580).exec()
        return True
    if verdict.partial:
        InfoDialog(
            tr("Filed \u2014 and it is a partial measurement"),
            tr("The chart has {chart} patches and this file holds {got} "
               "readings, so part of the chart was not measured. ChromIQ "
               "has filed it anyway: a measurement you stopped part way "
               "through is a normal thing to come back to.\n\nA profile "
               "built from fewer readings is a rougher profile \u2014 the "
               "measurement report states both counts."
               ).format(chart=verdict.n_chart, got=verdict.n_measured),
            parent, min_width=580).exec()
    # THE SAME ENDING THE NEW-PROJECT DOOR USES, and the reason the bar is
    # pointed HERE rather than earlier: this runs only once the file has been
    # judged and copied. It ran before the judgement once, so a refusal left
    # the bar reading "Run 3 (overwrite)" for a run that had just been created
    # and deleted again, under a window promising "nothing has been changed".
    finish_the_import(ctl, run.id, run.measurement_ti3, on_filed)
    return True

