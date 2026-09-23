"""The references a saved report makes to a project and its runs, rewritten
when the project is renamed or its runs are renumbered (challenge C, beta 39).

A saved report records the measurements it covers by FOLDER: the project's
name and ``runs/runN`` (or ``cal``) from there down, in every
``document.measurements`` entry (``dir``, ``ti3`` and ``key``), and a report
inside a project also carries the project's name in its own ``ti3``,
``chart`` and ``profile`` fields. Two operations change those names under
the report, and neither told the reports:

* **a project rename** (`Project.rename`, the name field's rename and the
  folder-renamed window, B8-841). A report in the folder across projects
  (``<ChromIQ folder>/reports/``) went on naming the old folder, so the other
  project's window found "1 of the 3" and an Update from that side narrowed
  the report to what it found;
* **the bar's Delete of a profile run**, which renumbers the later runs
  (`core.run_delete.delete_run`). ``meta.json`` was rewritten and nothing
  else: a one-run record of run 3, now in ``runs/run2``, still said
  ``runs/run3`` and was listed as "Multiple runs".

This module rewrites exactly those references and nothing else, in every
report file that can hold one: the project's own (every ``reports/`` folder
under it), the folder across projects beside it, and the reports of the
projects beside it (a verdict record of a report across projects carries the
document's list). Archives (anything under an ``old/`` folder) are history
and are never touched, and nothing is archived: the content of a report does
not change, only the name it uses for a folder that has itself moved.

**ALL OR NOTHING.** Every file is read and its new content worked out before
the first write; a file that cannot be written stops the plan before anything
is written (`plan_is_writable`), and a write that fails anyway puts back every
file already written, byte for byte.

Qt-free and free of ``workflow`` imports, so `core.file_manager` and
`core.run_delete` can call it.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePath

log = logging.getLogger(__name__)

#: What a reference to a DELETED profile run becomes (`run_references_plan`).
#: The run's folder is in the Trash and its number now belongs to the run
#: after it, so leaving ``runs/run2`` in place would point the report at a
#: different measurement. ``runs/run2.deleted`` is on no disk: an Update of
#: that report then says which measurement cannot be found and why.
DELETED_RUN_SUFFIX = ".deleted"

#: The top-level fields of a report INSIDE a project that carry the
#: project's name as a file stem (the measurement, the chart, the profile).
_STEM_FIELDS = ("ti3", "chart", "profile")


def _nfc(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFC", str(s))


@dataclass
class RefPlan:
    """The files a rewrite would change: ``{path: (old bytes, new text)}``."""
    changes: "dict[Path, tuple[bytes, str]]" = field(default_factory=dict)
    #: Files that could not be read (listed in the log, never written).
    unreadable: "list[Path]" = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.changes)


# --------------------------------------------------------------------------
# Which files
# --------------------------------------------------------------------------

def _is_archived(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return "old" in rel.parts[:-1]


def _reports_under(root: Path) -> "list[Path]":
    """Every ``report_*.json`` in a ``reports/`` folder under *root*, archives
    excluded. Never raises."""
    out: "list[Path]" = []
    try:
        for p in root.rglob("report_*.json"):
            if p.parent.name != "reports" or _is_archived(p, root):
                continue
            if p.is_file():
                out.append(p)
    except OSError:
        pass
    return sorted(out)


def _sibling_projects(project_root: Path) -> "list[Path]":
    out: "list[Path]" = []
    try:
        for c in sorted(project_root.parent.iterdir()):
            if c == project_root or not c.is_dir():
                continue
            if (c / "project.json").is_file():
                out.append(c)
    except OSError:
        pass
    return out


def report_files_referring(project_root: Path, *, outside: bool = True
                           ) -> "list[Path]":
    """The report files that may name *project_root*'s folders: its own, and
    with *outside* the folder across projects beside it and every project
    beside it."""
    project_root = Path(project_root)
    files = _reports_under(project_root)
    if outside:
        across = project_root.parent / "reports"
        try:
            files += sorted(p for p in across.glob("report_*.json")
                            if p.is_file())
        except OSError:
            pass
        for sib in _sibling_projects(project_root):
            files += _reports_under(sib)
    return files


# --------------------------------------------------------------------------
# One recorded folder
# --------------------------------------------------------------------------

def _split_recorded(d: str) -> "tuple[str, str, list[str]] | None":
    """``(prefix, project name, [parts below the project])`` of a recorded
    measurement folder, or None outside a ``<project>/runs/runN[/verifications
    /<date>]`` or ``<project>/cal`` layout. The same layout rule as
    `workflow.measurement_report._project_folder_of`, on the recorded STRING,
    which names where the project was when the report was written."""
    if not d:
        return None
    parts = list(PurePath(d).parts)
    n = len(parts)
    if n >= 2 and parts[-1] == "cal":
        i = n - 2                                  # <project>/cal
    elif n >= 5 and parts[-2] == "verifications" and parts[-4] == "runs":
        i = n - 5                                  # <project>/runs/runN/verifications/<date>
    elif n >= 3 and parts[-2] == "runs":
        i = n - 3                                  # <project>/runs/runN
    else:
        return None
    if i < 0 or parts[i] in ("/", "\\") or not parts[i]:
        return None
    prefix = str(PurePath(*parts[:i])) if i > 0 else ""
    return prefix, parts[i], parts[i + 1:]


def _join(prefix: str, name: str, below: "list[str]") -> str:
    if prefix:
        return str(PurePath(prefix, name, *below))
    return str(PurePath(name, *below))


def _renamed_stem(value: str, old: str, new: str) -> str:
    """*value* with a leading project stem *old* replaced by *new*: only when
    the stem is followed by a separator ChromIQ's own names use, or nothing."""
    v, o = _nfc(value), _nfc(old)
    if v == o:
        return new
    if v.startswith(o) and v[len(o)] in "-._":
        return new + v[len(o):]
    return value


# --------------------------------------------------------------------------
# The rewrite of one parsed report
# --------------------------------------------------------------------------

def _walk_measurement_lists(obj, fn) -> bool:
    """Call *fn(entry)* on every dict inside any ``"measurements"`` list in
    *obj*; True when any call changed something."""
    changed = False
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "measurements" and isinstance(v, list):
                for m in v:
                    if isinstance(m, dict) and isinstance(m.get("dir"), str):
                        changed |= bool(fn(m))
            else:
                changed |= _walk_measurement_lists(v, fn)
    elif isinstance(obj, list):
        for v in obj:
            changed |= _walk_measurement_lists(v, fn)
    return changed


def _rekey(m: dict) -> None:
    """``key`` rebuilt from the entry's own three parts, the way
    `document_measurement_key` builds it, when it had that shape."""
    key = m.get("key")
    if isinstance(key, str) and key.count("|") >= 2:
        m["key"] = f"{m.get('dir', '')}|{m.get('created', '')}|{m.get('ti3', '')}"


def _rename_entry(m: dict, old: str, new: str, here=None) -> bool:
    split = _split_recorded(str(m.get("dir") or ""))
    if split is None or _nfc(split[1]) != _nfc(old):
        return False
    if here is not None and not here(m):
        return False
    prefix, _name, below = split
    m["dir"] = _join(prefix, new, below)
    if isinstance(m.get("ti3"), str):
        m["ti3"] = _renamed_stem(m["ti3"], old, new)
    _rekey(m)
    return True


def _rename_stems(obj, old: str, new: str) -> bool:
    """The project's name in the stem fields of a report inside it, at any
    depth outside a measurement list (``printing.profile`` and the like)."""
    changed = False
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "measurements" and isinstance(v, list):
                continue
            if k in _STEM_FIELDS and isinstance(v, str):
                nv = _renamed_stem(v, old, new)
                if nv != v:
                    obj[k] = nv
                    changed = True
            else:
                changed |= _rename_stems(v, old, new)
    elif isinstance(obj, list):
        for v in obj:
            changed |= _rename_stems(v, old, new)
    return changed


def _renumber_entry(m: dict, names: "frozenset[str]",
                    mapping: "dict[str, str]", deleted: str,
                    here=None) -> bool:
    split = _split_recorded(str(m.get("dir") or ""))
    if split is None or _nfc(split[1]) not in names:
        return False
    if here is not None and not here(m):
        return False
    prefix, name, below = split
    if len(below) < 2 or below[0] != "runs":
        return False
    run = below[1]
    if run == deleted:
        new_run = run + DELETED_RUN_SUFFIX
    elif run in mapping:
        new_run = mapping[run]
    else:
        return False
    m["dir"] = _join(prefix, name, ["runs", new_run, *below[2:]])
    _rekey(m)
    return True


# --------------------------------------------------------------------------
# Whose folder a reference names
# --------------------------------------------------------------------------

def _same_folder(a: Path, b: Path) -> bool:
    try:
        return os.path.realpath(str(a)) == os.path.realpath(str(b))
    except OSError:
        return str(a) == str(b)


def _inside_folder(p: Path, root: Path) -> bool:
    try:
        rp = os.path.realpath(str(p))
        rr = os.path.realpath(str(root))
    except OSError:
        return _is_inside(Path(p), Path(root))
    return rp == rr or rp.startswith(rr.rstrip(os.sep) + os.sep)


def refers_here(project_root: "str | Path", report: "str | Path",
                rep: dict):
    """A test ``fn(entry) -> bool``: whether one recorded measurement of the
    report *report* (parsed as *rep*) names a folder of the project at
    *project_root*, and no other project's (re-challenge R1, beta 39, #1
    and #2).

    **A NAME IS NOT AN IDENTITY.** Matching by name alone rewrote the
    reports of a DIFFERENT project that has, or had, the same name: deleting
    a run in a renamed Finder duplicate renumbered 14 reports of its
    original, and deleting a run in a renamed project renumbered all 30
    reports of a fresh project that took its former name. A reference is
    now this project's only when the app's own reading of it says so
    (`workflow.measurement_report.resolve_recorded_folder`, seen from where
    the report's file lives: the project it is inside, or the folder across
    projects), and when that reading lands inside *project_root*. Outside
    the project, a name another existing project folder beside it holds is
    never this project's, whatever ``former_names`` says."""
    from workflow.measurement_report import (project_home_of,
                                             resolve_recorded_folder)
    root = Path(project_root)
    report = Path(report)
    home = project_home_of(report.parent)
    inside = home is not None and _same_folder(home, root)
    # A report with no project around it (``<ChromIQ folder>/reports``) is
    # read from its own folder: no project answers to "reports", so only
    # the rules that look BESIDE it (a project of the recorded name, or the
    # one project that answers to it) can claim the folder.
    homes = [home] if home is not None else [report.parent]
    recorded: "set[str]" = set()

    def _collect(m: dict) -> bool:
        split = _split_recorded(str(m.get("dir") or ""))
        recorded.add(_nfc(split[1]) if split else "")
        return False
    _walk_measurement_lists(rep, _collect)
    # "A report of one project is filed inside it" (rule 2) only holds for a
    # report that IS inside a project; read from the folder across projects
    # it would claim the folder for "reports" itself.
    one = home is not None and len(recorded) == 1

    def test(m: dict) -> bool:
        d = str(m.get("dir") or "")
        split = _split_recorded(d)
        if split is None:
            return False
        if not inside:
            namesake = root.parent / split[1]
            try:
                held = ((namesake / "project.json").is_file()
                        and not _same_folder(namesake, root))
            except OSError:
                held = True
            if held:
                return False
        try:
            got = resolve_recorded_folder(d, homes, one_project=one,
                                          must_exist=False)
        except Exception:                              # noqa: BLE001
            return False
        return got is not None and _inside_folder(Path(str(got)), root)
    return test


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------

def _plan(files, edit) -> RefPlan:
    plan = RefPlan()
    seen: "set[str]" = set()
    for p in files:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            raw = p.read_bytes()
            rep = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            plan.unreadable.append(p)
            continue
        if not isinstance(rep, dict):
            continue
        if edit(p, rep):
            plan.changes[p] = (raw, json.dumps(rep, indent=2))
    return plan


def rename_references_plan(project_root: "str | Path", old, new: str
                           ) -> RefPlan:
    """What a rename of the project at *project_root* (already under its new
    folder) to *new* changes in the reports that name it by *old* (a name,
    or every name it had: a report records the name of its day).

    Inside the project: every measurement entry recorded under an old name,
    and the report's own stem fields. Outside it (the folder across
    projects, the projects beside it): the measurement entries recorded
    under an old name, and only for a name no OTHER project beside it is
    still called. That one is a duplicate's original: its reports
    name their own folders by that name and are not this project's to
    rewrite."""
    root = Path(project_root)
    olds = [old] if isinstance(old, str) else list(old or ())
    olds = [o for o in dict.fromkeys(olds) if o and _nfc(o) != _nfc(new)]
    if not olds or not new:
        return RefPlan()

    def _free(name: str) -> bool:
        namesake = root.parent / name
        try:
            return not ((namesake / "project.json").is_file()
                        and namesake.resolve() != root.resolve())
        except OSError:
            return False
    outside_ok = {o for o in olds if _free(o)}

    def edit(p: Path, rep: dict) -> bool:
        inside = _is_inside(p, root)
        here = refers_here(root, p, rep)
        changed = False
        for o in olds:
            if not inside and o not in outside_ok:
                continue
            changed |= _walk_measurement_lists(
                rep, lambda m, o=o: _rename_entry(m, o, new, here))
            if inside:
                changed |= _rename_stems(rep, o, new)
        return changed
    return _plan(report_files_referring(root, outside=bool(outside_ok)), edit)


def run_references_plan(project_root: "str | Path", names,
                        mapping: "dict[str, str]", deleted: str) -> RefPlan:
    """What renumbering *project_root*'s runs by *mapping* (``{"run3":
    "run2", ...}``) after *deleted* went changes in the reports that name
    them. *names* is every name the project answers to (its folder, its
    files, its former names), because a report records the name the project
    had when it was written. A reference to *deleted* gets
    `DELETED_RUN_SUFFIX`, so it can never point at the run that took its
    number."""
    root = Path(project_root)
    names = frozenset(_nfc(n) for n in (names or ()) if n)
    if not names or (not mapping and not deleted):
        return RefPlan()

    def edit(p: Path, rep: dict) -> bool:
        here = refers_here(root, p, rep)
        return _walk_measurement_lists(
            rep, lambda m: _renumber_entry(m, names, dict(mapping), deleted,
                                           here))
    return _plan(report_files_referring(root, outside=True), edit)


def _is_inside(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Writing a plan
# --------------------------------------------------------------------------

def plan_is_writable(plan: RefPlan) -> "list[Path]":
    """The folders of *plan* ChromIQ may not write in (empty when it may)."""
    stuck: "list[Path]" = []
    for p in plan.changes:
        if not (os.access(p, os.W_OK) and os.access(p.parent, os.W_OK)):
            if p.parent not in stuck:
                stuck.append(p.parent)
    return stuck


def apply_plan(plan: RefPlan) -> bool:
    """Write every file of *plan*, or none: True when all were written.

    Each file is written through a scratch file in its own folder and swapped
    in (`os.replace`), and a failure puts back, byte for byte, every file
    already written. Nothing is archived (see the module docstring)."""
    if not plan:
        return True
    if plan_is_writable(plan):
        return False
    done: "list[Path]" = []
    try:
        for p, (_raw, text) in plan.changes.items():
            _swap_in(p, text.encode("utf-8"))
            done.append(p)
    except OSError as exc:
        log.warning("could not rewrite the references in %s (%s); putting "
                    "back the %d already rewritten", p, exc, len(done))
        for q in reversed(done):
            try:
                _swap_in(q, plan.changes[q][0])
            except OSError:
                log.error("could not put back %s", q)
        return False
    for p in done:
        log.info("rewrote the folder references in %s", p)
    return True


def _swap_in(path: Path, data: bytes) -> None:
    """Replace *path*'s content with *data*, keeping its mode and, to within
    a nanosecond, its modification time.

    **THE TIME IS KEPT BECAUSE THE WINDOW READS IT.** Which report of a
    measurement is the newest is decided by the file's mtime
    (`measurement_report_dialog._report_file_order` and its caller), so a
    rewrite that stamped every file "now" made the last file rewritten the
    newest report, and a window opened on a renamed duplicate came up on a
    one-date report instead of the document it had been on (caught by
    `test_beta38_challenge_fixes::test_a_renamed_duplicate_loads_its_own_
    other_run`). One nanosecond later, so a cache keyed on the time still
    sees that the content changed."""
    tmp = path.with_name(path.name + ".refs-tmp")
    try:
        st = os.stat(path)
    except OSError:
        st = None
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            import shutil
            shutil.copymode(path, tmp)
        except OSError:
            pass
        if st is not None:
            try:
                os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns + 1))
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
