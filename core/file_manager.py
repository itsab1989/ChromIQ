"""Working-folder management for ChromIQ sessions.

The folder layout owned by this module (v2, #127):

    work_dir/                          # one per project (target name)
      project.json                     # manifest (schema_version, current_run, runs[])
      Where are my files.txt           # the folder guide (from ui.file_guide)
      cal/                             # optional, shared across runs
        <name>-cal.ti1/.ti2/.ti3/.cal/.icc/.cht/.ps/_NN.tif
        exports/                       # the cal chart's hand-off sidecars
        meta.json
      exports/                         # Tools-menu exports (project-wide)
      runs/
        run1/                          # one folder per profile build
          <name>.ti1/.ti2/.cht/.cie/.ps/.pdf/.channels.json/.strips.json
          <name>_NN.tif                # NN = page index
          <name>.ti3                   # the measurement (chartread output)
          <name>.icc                   # the profile (colprof output)
          preconditioning.ti3 / .icc   # only when run was promoted from a parent
          merged.ti3 / merged.icc      # only when ti3_merge runs (refinement on)
          calibrated.icc               # applycal output
          reads/                       # only when averaging used
          reports/                     # quality checks, refine lists, measurement reports
          exports/                     # hand-off sidecars (-colours / -i1profiler)
          cache/                       # tool intermediates — always safe to delete
          meta.json
        run2/ ...

Everything a user prints, installs or measures stays at the run root (the
Argyll tools are stem+cwd coupled there); the ChromIQ-only paperwork lives in
reports/ / exports/ / cache/. Projects written before #127 (schema_version 1,
everything flat) are migrated in place by ``Project.load``.

All path construction in the app must go through ``Project`` / ``Run`` /
``Calibration`` (or the ``*_subdir`` helpers for explicit external folders).
String-concatenating paths anywhere else is a code smell.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from core.settings import AppSettings

log = get_logger(__name__)

#: The characters a project-folder name may keep, as a predicate rather than a
#: regular expression. It used to be ``re.compile(r"[^\w\-.]+")``, and ``\w``
#: does not match a COMBINING MARK — so a decomposed "Mu"+U+0308 became
#: "Mu_ller" while the precomposed "Müller" came through untouched, and a
#: trailing accent was deleted outright ("café" -> "cafe"). Python's ``re`` has
#: no ``\p{M}``, so the class is spelled out here instead.
#:
#: ``ch.isalnum() or ch == "_"`` is EXACTLY what ``\w`` matches for a str
#: pattern (CPython's SRE tests ``Py_UNICODE_ISALNUM(ch) || ch == '_'``); that
#: equivalence is proved over every code point in
#: tests/test_project_name_keeps_its_accents.py, so nothing that used to be
#: stripped survives the change.
_MARK_CATEGORIES = ("Mn", "Mc")


def _is_variation_selector(ch: str) -> bool:
    """Variation selectors are category Mn but are not part of anybody's name.

    They only pick a glyph shape — VS16 is the "draw the character before me as
    an emoji" switch. Kept out so an emoji still disappears whole: "🎨1" stays
    "1" rather than becoming an invisible "1️".
    """
    cp = ord(ch)
    return 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF


_TRAIL   = re.compile(r"^[._-]+|[._-]+$")   # also a trailing "-" from an empty descriptive-prefix tail

# Extensions ChromIQ itself generates during a session. A user-entered target
# name (or a loaded file's stem) must never carry one of these: the name is
# used verbatim as the working-folder name, so a name ending in e.g. ".icm"
# poisons every derived path.
_WORKFILE_EXTS = frozenset({
    ".icc", ".icm", ".mpp",
    ".ti1", ".ti2", ".ti3",
    ".tif", ".tiff",
    ".cal",
})

# Inside a Run.reads_dir, files are read1.ti3, read2.ti3, …
_NEW_READ_RE = re.compile(r"^read(\d+)$")

# ---------------------------------------------------------------------------
# The v2 sub-folder vocabulary (#127, names settled with Knut):
#   reports/ — things ChromIQ tells the user (quality checks, refine lists,
#              measurement reports)
#   exports/ — files made for use outside ChromIQ (same name and meaning as
#              the project-level exports/ folder)
#   cache/   — intermediates any tool can recreate; deleting never loses data
# The Argyll-coupled chain (.ti1→.ti2→.tif/.ps→.ti3→.icc) and its adjacency
# sidecars (channels/strips.json, .cht/.cie) stay flat at the run root.
# ---------------------------------------------------------------------------
REPORTS_DIRNAME = "reports"
EXPORTS_DIRNAME = "exports"
CACHE_DIRNAME   = "cache"
#: #130 — a profiling run's verification activity lives here: the shared verify
#: chart at the folder root, plus one dated sub-folder per verification run.
VERIFICATIONS_DIRNAME = "verifications"
#: #130 — the copy of the chart a run (or a dated verification) was measured
#: with. Same name at both levels, so one word means one thing.
CHART_SNAPSHOT_DIRNAME = "chart"

#: A dated verification-run folder id: "YYYY-MM-DD_HHMMSS" (+ optional "_N").
_VERIFY_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}(?:_\d+)?$")

#: Current on-disk project format. 1 = flat run folders (pre-#127),
#: 2 = reports/exports/cache sub-folders, 3 = verification runs moved into
#: runs/runN/verifications/<date>/ (#130). ``Project.load`` migrates in place;
#: formats newer than this open read-normally with a warning flag (see
#: ``Project.schema_too_new``) — the valuable files sit in the same place in
#: every format, so opening can't damage anything.
SCHEMA_VERSION = 3


def reports_subdir(folder: Path | str) -> Path:
    """``<folder>/reports`` — for callers working on an explicit directory
    (e.g. a browsed external ``.ti3``) where threading a ``Run`` through is
    not worth it. Keeps the folder name defined in exactly one place."""
    return Path(folder) / REPORTS_DIRNAME


def exports_subdir(folder: Path | str) -> Path:
    """``<folder>/exports`` — see :func:`reports_subdir`."""
    return Path(folder) / EXPORTS_DIRNAME


# Declutter-on-load (#36, Knut): the exact families ChromIQ itself writes, keyed
# to the v2 sub-folder they belong in. Deliberately narrow — only files matching
# these patterns move; anything else (user files, the Argyll-coupled chart chain)
# is left exactly where it is. The chart's OWN <name>.cht / <name>.cie never
# match (the cache patterns all require a -patchbox/-sample/-aligned tail).
_DECLUTTER_MAP = (
    (REPORTS_DIRNAME, (
        re.compile(r"^Quality_Check_\d+_.+\.txt$"),
        re.compile(r"^Refine_Strips_.+\.txt$"),
        re.compile(r"^Verify_Profile_\d+_.+\.txt$"),
        re.compile(r"^Verify_Reference_\d+_.+\.txt$"),
        re.compile(r"^report_.+\.json$"),
    )),
    (EXPORTS_DIRNAME, (
        re.compile(r"^.+-colours\.txt$"),
        re.compile(r"^.+-i1profiler\.(txt|pxf)$"),
    )),
    (CACHE_DIRNAME, (
        re.compile(r"^.+-patchbox\.cht$"),
        re.compile(r"^.+-patchbox-sample\.cht$"),
        re.compile(r"^.+-sample\.cht$"),
        re.compile(r"^.+-aligned\.cht$"),
        re.compile(r"^.+-aligned-patchbox.*\.cht$"),
        re.compile(r"^.+-diag\.tif$", re.IGNORECASE),
    )),
)


def maybe_declutter_on_load(path: "Path | str | None", settings) -> int:
    """Declutter the folder holding *path* when the user's ``declutter_on_load``
    preference is on (#36). A no-op when the setting is off, *path* is falsy, or
    nothing matches. Never raises — decluttering must not block a file load."""
    if not path:
        return 0
    try:
        if settings is not None and not settings.get("declutter_on_load", True):
            return 0
    except Exception:  # noqa: BLE001 — a settings hiccup must not block loading
        pass
    try:
        return declutter_folder(Path(path).parent)
    except Exception:  # noqa: BLE001
        return 0


def declutter_folder(folder: "Path | str") -> int:
    """Tidy a legacy flat folder into the v2 sub-folder layout (#36, Knut).

    Moves only the files ChromIQ itself writes — quality/verify reports and
    measurement JSON into ``reports/``, hand-off sidecars into ``exports/``,
    scanner-tool intermediates into ``cache/`` — creating the sub-folders as
    needed. User files and the Argyll-coupled chart chain are never touched,
    nothing is renamed or deleted, and a name clash leaves the file in place.
    Safe on any folder: one with no matching files is left untouched (no empty
    sub-folders created). Returns the number of files moved.

    Called by the file-load flows when Preferences → "Declutter files when
    loading from legacy folders" is on, so opening an old project tidies it.
    """
    folder = Path(folder)
    if not folder.is_dir():
        return 0
    moved = 0
    try:
        entries = sorted(folder.iterdir())
    except OSError:
        return 0
    for f in entries:
        try:
            if not f.is_file():
                continue
        except OSError:
            continue
        for dirname, patterns in _DECLUTTER_MAP:
            if any(rx.match(f.name) for rx in patterns):
                dst_dir = folder / dirname
                try:
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    dst = dst_dir / f.name
                    if dst.exists():
                        log.warning("declutter: %s already exists, leaving %s",
                                    dst, f)
                    else:
                        shutil.move(str(f), str(dst))
                        log.info("declutter: %s -> %s/", f.name, dirname)
                        moved += 1
                except OSError as exc:
                    log.warning("declutter: could not move %s: %s", f, exc)
                break
    return moved


def cache_subdir(folder: Path | str) -> Path:
    """``<folder>/cache`` — see :func:`reports_subdir`."""
    return Path(folder) / CACHE_DIRNAME


#: ``Path.glob`` is case-insensitive on Windows and case-sensitive everywhere
#: else. :func:`files_matching` reproduces that rather than changing it.
#:
#: READ AT CALL TIME, ON PURPOSE. This branch is dead on macOS and Linux, so the
#: whole gate ran past it for as long as it existed; a test that rebinds this
#: name is the only way it is ever executed here.
#: ``tests/test_a_name_is_not_a_pattern.py`` does exactly that.
#:
#: It lowercases the PATTERN as well as the name, which would mangle a genuine
#: character range (``[A-Z]`` -> ``[a-z]``). Every literal now arrives escaped —
#: ``[*]``, ``[?]``, ``[[]``, all case-free — so there is nothing left in a
#: ChromIQ pattern for that to damage, and lowering both sides is what
#: case-insensitive matching means.
_NAME_CASEFOLD = os.name == "nt"


def nfc(name: str) -> str:
    """*name* with its accents composed — the one spelling ChromIQ compares on.

    "Müller" is a single character U+00FC when a Mac keyboard types it and two
    ("u" + U+0308) when the same name comes back off a Mac OS Extended (HFS+)
    volume. HFS+ stores every filename decomposed, and ``shutil.copytree`` back
    onto APFS keeps that spelling, so a project restored from a Time Machine
    disk or an older external drive is spelled differently from the one that
    left. See :func:`files_matching` for why that matters.
    """
    return unicodedata.normalize("NFC", name)


#: ``*``, ``?`` and ``[`` are the only characters `fnmatch` treats as syntax.
#: A closing ``]`` with no class open is already a literal, so it is left alone
#: — escaping it would only make the pattern harder to read in a log line.
_GLOB_META = re.compile(r"([*?\[])")


def glob_escape(name: str) -> str:
    """*name* as a pattern that matches *name* and nothing else.

    A PROJECT FOLDER IS NAMED BY A PERSON, NOT BY US. ``_sanitise`` maps ``[``,
    ``]``, ``*`` and ``?`` to ``_``, so ChromIQ can never *create* a folder
    holding one — but ``open_project_at`` opens whatever folder the user picked,
    under the name it has on disk, and Finder will happily rename a project to
    ``Canon-Pro300 [test]``. Interpolated straight into ``f"{stem}*.tif"`` that
    name stops being a name and becomes syntax:

    * ``[`` and ``]`` open a character class, so ``Chart [v2]_01.tif`` does not
      match ``Chart [v2]*.tif`` — ``chart_ti2.exists()`` says True, the chart
      tiffs come back empty, and the Chart tab says there is no chart with four
      page bitmaps sitting in the folder. The identical signature to the HFS+
      decomposed-name fault :func:`files_matching` was written for;
    * ``*`` and ``?`` OVER-match, and pull in a file belonging to a project with
      a different name — which then gets printed, copied or **archived** as if
      it were a page of this chart.

    Escaping wraps each metacharacter in a one-character class (``*`` -> ``[*]``),
    which `fnmatch` reads as the literal. ``glob.escape`` does the same thing but
    splits a Windows drive letter off first; these are single path components,
    where that is meaningless, so this does it without the drive rule and behaves
    identically on all three platforms.

    Prefer :func:`stem_files` to calling this by hand — see its docstring for
    why the escaping belongs on the far side of the call.
    """
    return _GLOB_META.sub(r"[\1]", name)


def stem_files(folder: "Path | str | None", stem: str,
               *tails: str) -> list[Path]:
    """The files in *folder* called *stem* + one of *tails*.

    THE POINT OF THE SEPARATE ARGUMENT. Every caller of :func:`files_matching`
    in ChromIQ wanted the same thing: "the files whose name starts with this
    LITERAL stem". Written as ``files_matching(d, f"{stem}*.tif")`` the literal
    and the wildcard arrive as one string, and by then nothing can tell which
    ``*`` the caller meant and which one came out of somebody's folder name — so
    the fault could only ever be fixed one interpolation at a time, and the next
    interpolation somebody writes brings it back. Passing the stem as its own
    argument means the escaping happens once, here, and a metacharacter in a
    name can no longer reach the matcher at all.

    *tails* are the patterns (``"*.tif"``, ``"_*.tif"``, ``".ti2"``, ``"*"``);
    the stem is never one. ``tests/test_a_name_is_not_a_pattern.py`` fails if an
    f-string is ever handed to ``files_matching`` again.
    """
    esc = glob_escape(nfc(stem))
    return files_matching(folder, *(esc + t for t in tails))


def files_matching(folder: "Path | str | None", *patterns: str) -> list[Path]:
    """The files in *folder* matching any of *patterns*, ACCENT-SPELLING AND ALL.

    WHY THIS EXISTS, AND WHY ``Path.glob`` CANNOT BE USED FOR A STEM
    ---------------------------------------------------------------
    Every *existence* check in ChromIQ asks the filesystem, and APFS is
    normalisation-INSENSITIVE: ``(run.dir / "Müller.ti2").exists()`` is True
    whether the name on disk is composed or decomposed. ``Path.glob`` is not.
    It lists the directory and compares in Python, where the two spellings are
    simply different strings — so on a project restored from an HFS+ volume,
    ``chart_ti2.exists()`` said True while ``glob("Müller*.tif")`` returned
    nothing, and the Chart tab said "No chart for this profile run yet" with
    four page bitmaps sitting in the folder. Measured with a real 20 MB HFS+
    disk image; see ``tests/test_a_decomposed_name_finds_its_files.py``.

    So the comparison is done on the composed spelling of BOTH sides. A name
    that normalisation does not change — every ASCII name, which is the
    overwhelming majority — folds to itself, and takes exactly the path it took
    before: same matches, same order.

    WHAT THIS DELIBERATELY DOES NOT DO
    ----------------------------------
    It does not rename anything. On Linux (and on Windows) the filesystem is
    normalisation-*preserving and sensitive*, so ``Müller.tif`` composed and
    ``Müller.tif`` decomposed are two genuinely different files that can sit in
    one folder. Normalising names on the way in would have to overwrite one
    with the other; matching returns both, which is the truthful answer — they
    are both pages of that chart — and no caller here does anything to a match
    but read, copy or archive it.

    It does not fold case either. ``Path.glob`` is case-sensitive on POSIX and
    case-insensitive on Windows, and callers pass ``*.tif``/``*.TIF`` pairs
    because of it. That behaviour is reproduced exactly, so the only thing this
    helper changes anywhere is the accent spelling.

    *patterns* are single path components: ``"Müller*.tif"``, never
    ``"chart/*"``. A pattern with a separator raises rather than quietly
    matching less than the caller asked for.

    A PATTERN IS SYNTAX, AND A NAME IS NOT. Do not interpolate a stem into a
    pattern here — ``files_matching(d, f"{stem}*.tif")`` is the shape that lost
    a whole chart to a ``[`` in a folder name and adopted a stranger's file into
    another on a ``*``. Call :func:`stem_files` instead, which takes the literal
    as its own argument and escapes it. This function is for patterns that are
    genuinely patterns (``"*.x3d.html"``, ``"report_*.json"``).
    """
    if folder is None:
        return []
    for pat in patterns:
        if "/" in pat or os.sep in pat:
            raise ValueError(
                f"files_matching takes one path component, not {pat!r}")
    folded = [nfc(pat) for pat in patterns]
    out: list[Path] = []
    try:
        with os.scandir(str(folder)) as entries:
            for entry in entries:
                name = nfc(entry.name)
                if _NAME_CASEFOLD:
                    name = name.lower()
                if any(fnmatch.fnmatchcase(
                        name, pat.lower() if _NAME_CASEFOLD else pat)
                       for pat in folded):
                    out.append(Path(entry.path))
    except (OSError, ValueError):
        # A folder that is not there holds no files — the same answer
        # `Path.glob` gives, and every caller here already treats it that way.
        return []
    return sorted(out)


def ensure_subdir(path: Path) -> Path:
    """mkdir -p for a sub-folder; falls back to the parent when the volume
    refuses (e.g. a read-only scan folder) so writers always get a usable
    directory instead of an exception."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as exc:
        log.warning("Could not create %s (%s) — falling back to %s",
                    path, exc, path.parent)
        return path.parent


def write_json_atomically(path: Path, payload: dict) -> None:
    """Write *payload* to *path* so a crash can never leave it half-written.

    Knut, #130 (2026-08-06), on how the settings files must be handled:

        "Write the updated JSON data to a temporary file in the same directory,
        then rename (replace) the original file with the temporary one. This
        prevents file corruption if the process crashes mid-write."

    ``os.replace`` is atomic on every platform ChromIQ ships on, and the
    temporary file is made in the SAME directory so the rename never crosses a
    filesystem boundary — across one it silently degrades to copy-then-delete,
    which is the non-atomic behaviour being avoided.

    ``fsync`` before the rename, so a power loss cannot leave the rename
    committed while the contents are still sitting in a buffer.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except Exception:
        # Never leave the scratch file behind to be mistaken for real data.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Manifest dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ProjectManifest:
    """The contents of ``project.json``."""
    schema_version: int = 1          # projects written before #127 carry 1
    created_at: str = ""
    target_name: str = ""
    current_run: str = "run1"
    runs: list[str] = field(default_factory=lambda: ["run1"])

    @classmethod
    def fresh(cls, target_name: str) -> "ProjectManifest":
        return cls(
            schema_version=SCHEMA_VERSION,
            created_at=datetime.now().isoformat(timespec="seconds"),
            target_name=target_name,
            current_run="run1",
            runs=["run1"],
        )

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectManifest":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class RunMeta:
    """The contents of ``runs/runN/meta.json``."""
    run_id: str = ""
    created_at: str = ""
    parent_run: str | None = None
    instrument: str = ""
    paper: str = ""
    averaging_enabled: bool = False
    averaging_method: str = "mean"
    averaging_read_count: int = 0
    # Opt-in: keep scanner-recognition files (.cht + .cie) for this chart, rebuilt
    # from the measurement whenever it's finalised (#97). Off unless the user ticks
    # the "All Stripes Read" checkbox; only meaningful for engine charts.
    scanner_target_enabled: bool = False
    # #130: set when a measurement was taken with the chart copy deliberately
    # left alone ("Measure without changing the stored chart"). The stored chart
    # then describes an EARLIER measurement, so the interface must say so rather
    # than let Restore Used Chart put back a chart that does not match.
    chart_snapshot_stale: bool = False
    preconditioning_source_run: str | None = None
    # Set to "merged.ti3" when a refinement merge ran; otherwise the canonical
    # measurement carries the (project-name) chart stem.
    profile_built_from: str = ""
    # #137: which calibration this run's profile was built with, by stem. Absent
    # (empty) means UNKNOWN — the honest state of every run built before ChromIQ
    # recorded it, and of every run built without a calibration at all. Once a
    # calibration is replaced the older one lives on in cal/old/<date>/, so a
    # stored stem stays resolvable rather than dangling.
    calibration_used: str = ""
    # #130 (Knut): what this run is FOR, in the user's own words — "PhotoRag
    # Baryta, gloss, large chart". Optional and empty by default; it names no
    # file and changes no path. It belongs to the RUN, so restoring an earlier
    # chart never touches it.
    description: str = ""
    # #130: the working copy of the chart notes for the chart being edited.
    # The chart's own `.channels.json` is authoritative for a chart that
    # exists — the notes are PRINTED on that sheet, so they describe the paper
    # in your hand — and this is what lets the field survive a run change and
    # exist before any chart has been generated at all.
    chart_notes: str = ""
    # #130 (Knut, beta.150): the VERIFICATION chart's notes, kept apart from the
    # run's own. A run has two charts — the profiling chart and the one
    # verification chart — and they are different sheets of paper, so notes
    # written on one must not appear on the other: *"These fields must be
    # separate for Run type = Verification and Run type = Profiling (this only
    # applies to 'Verification Chart Notes' and 'Run 2 Description'
    # respectively)."* The DESCRIPTION stays shared, by his earlier ruling —
    # a verification belongs to the run it verifies.
    verify_chart_notes: str = ""
    #: Create Chart's settings as this target last had them — the WORKING copy,
    #: written whenever the user leaves the tab or uses them (#130 §3). The
    #: chart's own `<stem>.channels.json` keeps a separate record of what the
    #: chart it sits beside was actually made with, so Restore Used Chart is
    #: unaffected by anything here.
    #:
    #: Two homes because one cannot do the job: a target with no chart yet has
    #: no sidecar to write into, so W6 ("leaving a tab saves the settings")
    #: would lose the work a user does before pressing Generate Chart — the
    #: first thing they do. Knut approved the split (2026-08-06: "Sure, go
    #: ahead").
    #:
    #: Shape: {"<tool><flag>": {"enabled": bool, "value": …}}, or
    #: {"repeats": [ … ]} for a flag that may be given more than once.
    create_chart_settings: dict = field(default_factory=dict)
    #: The Create Chart controls that are not parameter rows (Knut's beta.3
    #: bug-test, 2026-08-11): the active module, Guided's shared settings
    #: (instrument, paper, pages, …), the layout-engine toggle and recipe,
    #: and the FROM PROFILE GAMUT module's options. Stored so they follow
    #: the target BEFORE any chart exists; once a chart is generated its
    #: sidecar still has the last word on what it recorded (Knut's
    #: precedence ruling).
    create_chart_ui: dict = field(default_factory=dict)
    #: The Measure tab's settings as this target last had them (#130 §5).
    #: Separate from create_chart_settings because they are different tabs with
    #: different keys; one dict would make a renamed key on one tab look like a
    #: stale key on the other.
    measure_settings: dict = field(default_factory=dict)
    #: The Build Profile tab's settings as this target last had them (#130 §5).
    #: Its own key for the same reason measure_settings has one: three tabs
    #: sharing a dict would make a renamed key on one look stale on another.
    profile_settings: dict = field(default_factory=dict)
    #: The Print Chart tab's verification-print choices for this target
    #: (#130 feature A, §11 Q5): ``{"colour", "intent", "route"}``. Its own key
    #: for the same reason the others have one. Only runs carry it — a
    #: calibration never shows the Colour row, so ``CalibrationMeta`` has no
    #: counterpart and the tab skips a calibration store.
    print_settings: dict = field(default_factory=dict)

    # #130 (Knut, beta.148): the Profile Description the user typed for THIS
    # run, when they typed one. Empty means "still automatic" — ChromIQ builds
    # it from the project name and the run's own description, and keeps it in
    # step as those change. His rule: *"Every run has its own values … Emptying
    # the Profile Description … will re-enable the automatic generation … for
    # that specific run."* Before this the override was one value for the whole
    # tab, so a description typed for run 3 followed the user into every run.
    profile_description: str = ""
    status: str = "in_progress"          # in_progress | complete
    # TI2 layout editor only: the printtarg layout knobs (a LayoutOptions dict)
    # the chart was rendered with + its file basename, so reopening the chart in
    # the editor restores the panel exactly as saved. printtarg discards these
    # once a chart is rendered, and they can't be recovered from the .ti2 alone.
    # The main app never sets or reads these — they stay None / "" for its runs.
    editor_layout: dict | None = None
    editor_basename: str = ""
    # TI2 layout editor only: the "creation recipe" — the New chart / Add window
    # state (_collect_gen_state: source mode, colour-set generators, instrument /
    # paper, layout) that produced the chart. Distinct from editor_layout (the
    # printtarg layout the Create Chart tab can edit): editor_layout is reloaded
    # when the chart reopens in the editor, while editor_recipe is reloaded into
    # the New chart / Add windows so the design can be tweaked / recreated.
    editor_recipe: dict | None = None
    # #130: the run this one was made from with the Duplicate button. A new run
    # in every other respect — its own id, its own timestamp — so this records
    # where its files came from without letting it claim to BE the source run.
    # Knut, 2026-08-01: "meta.json not copied. duplicated_from: runN note added."
    duplicated_from: str | None = None

    @classmethod
    def fresh(cls, run_id: str, parent: str | None = None) -> "RunMeta":
        return cls(
            run_id=run_id,
            created_at=datetime.now().isoformat(timespec="seconds"),
            parent_run=parent,
        )

    @classmethod
    def from_dict(cls, d: dict) -> "RunMeta":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


# ---------------------------------------------------------------------------
# The chart stash — ONE mechanism, used by a run and by the calibration
# ---------------------------------------------------------------------------

#: Where a chart waits while its replacement is being built. Dot-prefixed so
#: `live_files()` skips it, so it is never mistaken for the chart itself, and so
#: Finder keeps it out of the way.
CHART_STASH_PREFIX = ".chart-stash-"

#: Written into a stash that has been SUPERSEDED by a chart that really was
#: built, on the rare path where the stash could not be removed afterwards. Its
#: presence is the only thing that stops :meth:`Project.load` putting the old
#: chart back over the new one.
STASH_SUPERSEDED = "SUPERSEDED-by-a-finished-build"


def chart_stash_dirs(folder: Path) -> "list[Path]":
    """Every chart stash left in *folder*, oldest first.

    BY AGE, NOT BY NAME, and the difference is somebody's chart. The name is
    ``.chart-stash-<pid>-<n>``, so a plain `sorted()` orders by the pid AS A
    STRING: ``.chart-stash-10000-0`` comes before ``.chart-stash-9999-0``
    whatever their ages, and the counter is not zero-padded either. That order
    is not cosmetic — :meth:`Project.load` restores them in it, and each restore
    overwrites what the one before put back (:func:`settle_chart_stash` clears a
    name a leftover has taken), so the LAST one processed is the chart the user
    ends up with and the other is dropped, not archived. Ordering by name meant
    which chart survived two orphaned builds depended on two process ids.

    The modification time is the moment the last file was moved in, which is the
    order the stashes were made in; the name is the tie-break so the result is
    still stable when two stashes share a timestamp.
    """
    if not folder.is_dir():
        return []

    def _age(p: Path) -> "tuple[float, str]":
        try:
            return (p.stat().st_mtime, p.name)
        except OSError:            # vanished, or unreadable — sort it first
            return (0.0, p.name)

    return sorted((p for p in folder.iterdir()
                   if p.is_dir() and p.name.startswith(CHART_STASH_PREFIX)),
                  key=_age)


def make_chart_stash(folder: Path) -> "Path | None":
    """A fresh, empty stash inside *folder*, or None when one cannot be made.

    UNIQUE PER BUILD, NOT PER PROCESS. The name used to be the pid alone, so a
    second build in the same session reused the folder a previous one had left
    behind and merged into it — measured: the two charts' files in one stash,
    and the SUPERSEDED marker of the earlier build restored into the run as a
    file. ``exist_ok=False`` makes the collision impossible rather than
    unlikely.
    """
    for _n in range(1000):
        cand = folder / f"{CHART_STASH_PREFIX}{os.getpid()}-{_n}"
        if cand.exists():
            continue
        try:
            cand.mkdir(parents=True, exist_ok=False)
            return cand
        except FileExistsError:
            continue                      # lost the race; take the next name
        except OSError as exc:
            log.warning("Could not make a chart stash in %s: %s", folder, exc)
            return None
    log.warning("Could not find a free chart stash name in %s", folder)
    return None


def settle_chart_stash(folder: Path, stash: "Path | None", *, built: bool,
                       leftovers: "Callable[[], Iterable[Path]]") -> None:
    """Finish what a stashing reset started, for a run or for ``cal/`` alike.

    *built* True means a new chart was written, so the one that was set aside is
    no longer wanted and the stash goes. False means the build did not happen —
    it failed, it was stopped, or the app was closed while it ran — and every
    file is put back exactly where it was.

    *leftovers* names what a build that produced nothing may have written into
    *folder*. It is a callable, and it is the ONLY part of this that differs
    between a run and a calibration: a run enumerates the chart names it can
    hold, a calibration subtracts its results from what is live. Everything
    else — the empty-stash guard, the restore, the removal, the SUPERSEDED
    marking — is one implementation on purpose, because two would drift and the
    drift would be somebody's chart.

    WHAT "PUT BACK" HAS TO MEAN, and the first version got this wrong: a build
    that produced no chart still leaves rubbish behind, half-written page images
    and a `.ti1` with no `.ti2`. Skipping a stashed file because something of
    that name exists let those leftovers WIN, and the original was then
    destroyed with the stash. Measured on screen twice — Stop pressed during
    printtarg, and the app killed mid-build then reopened: the `.ti2` came back
    and the page image did not, which is round 11's data loss reached through
    the very fix written to prevent it. So on a build that did not finish, the
    leftovers go and every stashed file is restored, with no exceptions.

    Never raises: a stash that cannot be settled is left on disk, where
    :meth:`Project.load` deals with it on the next launch, and that is far
    better than a half-restored run.
    """
    if stash is None or not Path(stash).is_dir():
        return
    stash = Path(stash)
    # AN EMPTY STASH REPRESENTS NOTHING, AND MUST THEREFORE TAKE NOTHING.
    #
    # The sweep below removes every chart file that is not in the stash, on the
    # grounds that it belongs to a build which produced no chart. With an empty
    # stash that is EVERY chart file, and there is nothing to put back
    # afterwards. Measured on screen with a real Stop: the chart was restored
    # byte-for-byte, the log said "nothing is lost", and the next time the
    # project was opened the run held `meta.json` and nothing else — the `.ti2`
    # a printed sheet is read against among the casualties.
    #
    # An empty stash is reachable: this function catches a failed `rmtree`, logs
    # it and carries on, so a successful restore can leave the emptied folder
    # behind for the next open to find. Before the sweep existed that leftover
    # was harmless.
    try:
        if not any(q for q in stash.iterdir() if q.name != STASH_SUPERSEDED):
            log.info("An empty chart stash was left in %s; removing it and "
                     "leaving the folder alone", folder)
            shutil.rmtree(stash, ignore_errors=True)
            return
    except OSError as exc:
        log.warning("Could not read the chart stash %s: %s", stash, exc)
        return
    if not built:
        # SWEEP WHAT THE FAILED BUILD LEFT, not just the names we are about to
        # restore. Putting a chart back used to walk only the stash, so anything
        # the dead build wrote under a name the OLD chart never had simply
        # stayed — raise the page count, press Generate, press Stop, and the run
        # kept two extra page images for a one-page chart.
        try:
            dead = list(leftovers())
        except Exception as exc:      # noqa: BLE001 — a restore must not fail
            log.warning("Could not list what the unfinished build left in "
                        "%s: %s", folder, exc)
            dead = []
        for p in dead:
            if p.exists() and not (stash / p.name).exists():
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except OSError as exc:
                    log.warning("Could not clear %s: %s", p.name, exc)
        for p in sorted(stash.iterdir()):
            if p.name == STASH_SUPERSEDED:
                continue          # bookkeeping, not one of the person's files
            dest = folder / p.name
            try:
                if dest.exists():
                    # A leftover of a build that produced nothing. It has no
                    # claim on this name; the file it replaced does.
                    log.debug("preset undo: discarding %s left by the "
                              "unfinished build", dest.name)
                    if dest.is_dir():
                        shutil.rmtree(dest, ignore_errors=True)
                    else:
                        dest.unlink()
                shutil.move(str(p), str(dest))
            except OSError as exc:
                log.warning("Could not put %s back: %s", p.name, exc)
        log.info("Chart build did not finish — the previous chart was put "
                 "back in %s", folder)
    try:
        shutil.rmtree(stash)
    except OSError as exc:
        log.warning("Could not remove the chart stash %s: %s", stash, exc)
        if built:
            # The new chart is in place and this copy is stale. Say so inside
            # it, or the next open would put it back over the chart that really
            # was built.
            try:
                (stash / STASH_SUPERSEDED).write_text("", encoding="utf-8")
            except OSError:
                log.warning("…and could not mark it superseded either")


# ---------------------------------------------------------------------------
# Calibration — shared across all runs in a project
# ---------------------------------------------------------------------------

class CalibrationReset(NamedTuple):
    """What :meth:`Calibration.reset` did with the calibration that was there.

    Two fields rather than one path, because there are two outcomes and reading
    one for the other is exactly the confusion this whole thread was about: an
    ARCHIVE is a folder in ``cal/old/`` the user is meant to find and open, a
    STASH is a hidden folder that exists only until the build finishes and is
    then dropped.

    ``__bool__`` is defined on purpose. A tuple of two Nones is truthy, and a
    caller writing ``if cal.reset():`` would be told "yes, something was kept"
    over an empty ``cal/``.
    """
    archive: "Path | None" = None
    stash: "Path | None" = None

    def __bool__(self) -> bool:
        return self.archive is not None or self.stash is not None


@dataclass
class CalibrationMeta:
    """The contents of ``cal/meta.json`` (#130).

    A calibration is not a run, but it IS a printed sheet, and Knut's ruling is
    that a sheet you cannot label is a sheet you cannot tell apart six months
    later. So it gets the same two fields a run has, in its own file — never
    in a run's, because two writable copies is how they come to disagree.

    Unknown keys are dropped on load rather than raising, so a file written by
    a newer build opens in an older one.
    """
    description: str = ""
    chart_notes: str = ""
    #: The Profile Description typed for this calibration, or empty for
    #: "automatic" — the same rule a run follows (see ``RunMeta``).
    profile_description: str = ""
    #: Create Chart's settings as this target last had them — the WORKING copy,
    #: written whenever the user leaves the tab or uses them (#130 §3). The
    #: chart's own `<stem>.channels.json` keeps a separate record of what the
    #: chart it sits beside was actually made with, so Restore Used Chart is
    #: unaffected by anything here.
    #:
    #: Two homes because one cannot do the job: a target with no chart yet has
    #: no sidecar to write into, so W6 ("leaving a tab saves the settings")
    #: would lose the work a user does before pressing Generate Chart — the
    #: first thing they do. Knut approved the split (2026-08-06: "Sure, go
    #: ahead").
    #:
    #: Shape: {"<tool><flag>": {"enabled": bool, "value": …}}, or
    #: {"repeats": [ … ]} for a flag that may be given more than once.
    create_chart_settings: dict = field(default_factory=dict)
    #: The Create Chart controls that are not parameter rows (Knut's beta.3
    #: bug-test, 2026-08-11): the active module, Guided's shared settings
    #: (instrument, paper, pages, …), the layout-engine toggle and recipe,
    #: and the FROM PROFILE GAMUT module's options. Stored so they follow
    #: the target BEFORE any chart exists; once a chart is generated its
    #: sidecar still has the last word on what it recorded (Knut's
    #: precedence ruling).
    create_chart_ui: dict = field(default_factory=dict)
    #: The Measure tab's settings as this target last had them (#130 §5).
    #: Separate from create_chart_settings because they are different tabs with
    #: different keys; one dict would make a renamed key on one tab look like a
    #: stale key on the other.
    measure_settings: dict = field(default_factory=dict)
    #: The Build Profile tab's settings as this target last had them (#130 §5).
    #: Its own key for the same reason measure_settings has one: three tabs
    #: sharing a dict would make a renamed key on one look stale on another.
    profile_settings: dict = field(default_factory=dict)


    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationMeta":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


class Calibration:
    """The ``cal/`` folder. One calibration set is shared by every run."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root

    @property
    def stem(self) -> str:
        """File stem for calibration artefacts: ``<project>-cal``.

        Named after the project (so printtarg stamps it on the printed sheet)
        with a ``-cal`` marker so a printed calibration target is
        distinguishable from the profiling chart, which shares the project name.
        """
        return f"{self._root.name}-cal"

    @property
    def dir(self) -> Path:                    return self._root / "cal"
    @property
    def cal_path(self) -> Path:               return self.dir / f"{self.stem}.cal"
    @property
    def ti1(self) -> Path:                    return self.dir / f"{self.stem}.ti1"
    @property
    def ti2(self) -> Path:                    return self.dir / f"{self.stem}.ti2"
    @property
    def ti3(self) -> Path:                    return self.dir / f"{self.stem}.ti3"
    @property
    def icc(self) -> Path:                    return self.dir / f"{self.stem}.icc"
    @property
    def cht(self) -> Path:                    return self.dir / f"{self.stem}.cht"
    @property
    def ps(self) -> Path:                     return self.dir / f"{self.stem}.ps"
    @property
    def channels_json(self) -> Path:          return self.dir / f"{self.stem}.channels.json"
    @property
    def meta_path(self) -> Path:              return self.dir / "meta.json"

    # ---- meta (#130): the calibration's own description and chart notes
    def load_meta(self) -> "CalibrationMeta":
        """``cal/meta.json``, or an empty one when there is none yet."""
        if not self.meta_path.exists():
            return CalibrationMeta()
        try:
            raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return CalibrationMeta()      # unreadable is the same as absent here
        return CalibrationMeta.from_dict(raw)

    def save_meta(self, meta: "CalibrationMeta") -> None:
        write_json_atomically(self.meta_path, asdict(meta))

    # ---- v2 sub-folders (#127)
    @property
    def exports_dir(self) -> Path:            return self.dir / EXPORTS_DIRNAME

    def ensure_exports_dir(self) -> Path:
        return ensure_subdir(self.exports_dir)

    def chart_tiffs(self) -> list[Path]:
        # `<stem>*.tif` matches both single-page <stem>.tif and multi-page
        # <stem>_NN.tif (see Run.chart_tiffs for the rationale).
        return self.stem_files(self.stem, "*.tif", "*.TIF", "*.tiff")

    def files_matching(self, *patterns: str) -> list[Path]:
        """The calibration folder's files matching *patterns*, accent spelling
        and all. See :func:`files_matching`."""
        return files_matching(self.dir, *patterns)

    def stem_files(self, stem: str, *tails: str) -> list[Path]:
        """The calibration folder's files called *stem* + one of *tails*, with
        *stem* taken as a literal name. See :func:`stem_files`."""
        return stem_files(self.dir, stem, *tails)

    def exists(self) -> bool:
        """True when at least one calibration artefact is on disk."""
        return self.cal_path.exists() or self.ti3.exists()

    def ensure_dir(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir

    # ---- the archive (#137 D1) -------------------------------------------
    @property
    def old_dir(self) -> Path:                return self.dir / "old"

    @property
    def snapshot_dir(self) -> Path:
        """Where the calibration chart's stored copy lives (#137 decision 3).

        The same idea as a run's ``chart/``: a copy of the chart exactly as it
        was printed, so "Restore Used Chart" can put it back after the chart has
        been regenerated. See :func:`workflow.chart_slot.slot_for_calibration`.
        """
        return self.dir / "chart"

    #: ``cal/meta.json`` holds the user's own words about this calibration —
    #: its description and its chart notes. It is COPIED into an archive and
    #: never moved there, because it describes the calibration slot, which
    #: survives a rebuild. Moving it emptied both fields the moment a new
    #: calibration chart was generated (Knut, beta.147): *"adding text in
    #: Calibration Description and Calibration Chart Notes, then Generate
    #: Chart. The chart was made, but the text in the two fields
    #: dissappeared."* Runs have always kept their ``meta.json`` across a chart
    #: rebuild; this is the same rule for ``cal/``.
    KEPT_ACROSS_ARCHIVE = ("meta.json",)

    def live_files(self) -> "list[Path]":
        """Everything in ``cal/`` that is the calibration itself.

        Files only, so ``old/``, ``chart/`` and ``exports/`` are never swept
        into an archive of themselves — which would nest a previous archive
        inside the next one and make "go back to it" a dig rather than a look.

        ``meta.json`` is NOT one of them. It is the slot's own description, it
        exists as soon as the user types a Calibration Description, and it must
        not answer "is there a calibration here?" — that is what made Generate
        Chart claim *"You already made a calibration chart for this project"*
        over an empty ``cal/`` folder (Knut, beta.148). Same rule as
        ``ChartSlot.side_files``.
        """
        if not self.dir.exists():
            return []
        return sorted(p for p in self.dir.iterdir()
                      if p.is_file() and not p.name.startswith(".")
                      and p.name not in self.KEPT_ACROSS_ARCHIVE)

    def copied_to_archive(self) -> "list[Path]":
        """Files an archive gets a COPY of, while the live one stays put."""
        return [self.dir / name for name in self.KEPT_ACROSS_ARCHIVE
                if (self.dir / name).is_file()]

    #: What goes into the TOP LEVEL of an archive — the things that cannot be
    #: regenerated at all. Knut, beta.148: *"Only measurement ti3 files shall be
    #: copied to cal/old/<date_time>/ folder, similar to how it is done for a
    #: run."* The chart is kept too, one level down in ``chart/``, because the
    #: window shown before a rebuild promises it — see :meth:`reset`.
    RESULT_SUFFIXES = (".ti3", ".cal", ".icc", ".icm")

    #: The sub-folder of an archive that holds the chart the calibration was
    #: made with — the same name ``cal/chart/`` uses live, and the same place
    #: the whole-calibration archive already puts the stored chart copy.
    ARCHIVE_CHART_DIRNAME = "chart"

    def chart_files(self) -> "list[Path]":
        """The live files that ARE the chart: everything in ``cal/`` that is not
        a result and not the calibration's own words.

        Defined by subtraction on purpose. A list of stems and suffixes would go
        stale the first time a new sidecar is added — ``.strips.json`` and
        ``.print.json`` have both been forgotten by such a list already
        (``Run.chart_artefact_names``) — whereas "whatever is live and is not a
        measurement" cannot miss a file it has never heard of. So the ``.ti1``,
        the ``.ti2``, the ``.channels.json``, every ``_NN.tif`` page and any
        sidecar beside them are all covered by construction.
        """
        results = set(self.result_files())
        return [p for p in self.live_files() if p not in results]

    def result_files(self) -> "list[Path]":
        """The live files that cannot be regenerated — the measurement, the
        ``.cal``, any profile built from them, and the partial a measurement
        that stopped part way through leaves behind."""
        return [p for p in self.live_files()
                if p.suffix.lower() in self.RESULT_SUFFIXES
                or p.name.endswith(".ti3.engine-partial")]

    def archive_to_old(self, when: "datetime | None" = None,
                       *, only: "list[Path] | None" = None,
                       chart: "list[Path] | None" = None) -> "Path | None":
        """Move a calibration into ``cal/old/<date>/`` — never delete.

        A calibration is a whole printed and measured chart's worth of work, and
        it is what ``printcal``'s Re-calibrate and Verify modes read back
        (``printcal.c:110``); deleting it makes both impossible. Runs have had
        this protection since #130 §2a; ``cal/`` never did, and rebuilding a
        calibration chart called :meth:`reset`, which was ``rmtree``.

        ``only`` names what goes into the archive's TOP LEVEL; without it,
        everything live goes. The chart snapshot travels along ONLY in the
        everything case — a rebuild keeps ``chart/`` where it is, because it is
        the copy Restore Used Chart reads.

        ``chart`` names what goes into ``<archive>/chart/``. Two reasons it is
        a sub-folder rather than the top level, and they pull the same way:

        * The window the user reads before this happens promises the chart moves
          here and can be gone back to (M-CAL-REPLACE-CHART, and the first
          bullet of M-CAL-REPLACE-MEASURED). It has to be IN the archive.
        * Knut ruled at beta.148 that only what cannot be regenerated belongs in
          a dated folder, because a folder holding a bare ``.ti1``/``.ti2``
          "reads like a kept calibration and is not one". Putting the chart one
          level down, in a folder that says ``chart``, keeps the dated folder's
          own listing exactly as he asked for it and still keeps the chart.

        Returns the archive folder, or None when there was nothing to keep.
        """
        copied = self.copied_to_archive()
        if only is not None:
            existing = [p for p in only if p.is_file()]
        else:
            existing = [p for p in self.live_files() if p not in copied]
            # The stored chart copy travels with it: restoring a calibration you
            # have archived should give you the chart it was measured with, not
            # the chart that replaced it.
            if self.snapshot_dir.is_dir():
                existing.append(self.snapshot_dir)
        sub = [p for p in (chart or []) if p.exists()]
        if not existing and not sub:
            return None
        when = when or datetime.now()
        # ONE FOLDER PER ARCHIVE, always. Two rebuilds inside the same second
        # would otherwise share a dated folder and merge, and the user could no
        # longer tell which calibration was which — the whole point of keeping
        # them is being able to go back to a particular one.
        stamp = when.strftime("%Y-%m-%d_%H%M%S")
        dest = self.old_dir / stamp
        n = 2
        while dest.exists():
            dest = self.old_dir / f"{stamp}_{n}"
            n += 1
        dest.mkdir(parents=True, exist_ok=True)

        def _move_into(folder: Path, paths: "list[Path]") -> None:
            for p in paths:
                target = folder / p.name
                k = 1
                while target.exists():
                    target = folder / f"{p.stem}_{k}{p.suffix}"
                    k += 1
                try:
                    shutil.move(str(p), str(target))
                except OSError as exc:
                    # ONE PLACE OR THE OTHER, NEVER BOTH. `shutil.move` falls
                    # back to copy-then-unlink when the rename fails, so a file
                    # the OS will not let go of (a `uchg` flag, a lock) ends up
                    # copied into the archive AND still live — and the archive
                    # is then a chart with a hole in it while the window said it
                    # was whole. Measured by the adversarial round, 2026-09-02.
                    # The live file is the user's; the half-made copy is ours,
                    # so the copy goes.
                    log.warning("Could not archive calibration %s: %s — it is "
                                "left where it is", p.name, exc)
                    if target.exists() and p.exists():
                        try:
                            if target.is_dir():
                                shutil.rmtree(target, ignore_errors=True)
                            else:
                                target.unlink()
                        except OSError as exc2:
                            log.warning("…and the half-made copy at %s could "
                                        "not be removed either: %s",
                                        target, exc2)
                    continue
                log.info("archived calibration %s -> cal/old/%s/%s",
                         p.name, dest.name,
                         "" if folder == dest else f"{folder.name}/")

        _move_into(dest, existing)
        if sub:
            chart_dir = dest / self.ARCHIVE_CHART_DIRNAME
            chart_dir.mkdir(parents=True, exist_ok=True)
            _move_into(chart_dir, sub)
        # …and the calibration's own words go in as a COPY, so the archive
        # documents itself while the live fields keep what the user typed.
        for p in copied:
            shutil.copy2(str(p), str(dest / p.name))
            log.info("copied calibration %s into cal/old/%s/ (the live one "
                     "stays)", p.name, dest.name)
        return dest

    def chart_stash_dirs(self) -> "list[Path]":
        """Every chart stash left in ``cal/``, oldest first.

        Same folder-naming convention as a run's, from the same module-level
        helper — so :meth:`Project.load` settles a calibration stash left by a
        process that died exactly as it settles a run's.
        """
        return chart_stash_dirs(self.dir)

    def settle_chart_stash(self, stash: "Path | None", *, built: bool) -> None:
        """Finish what :meth:`reset` started when it set a chart aside.

        *built* True: the replacement chart was really written, so the one that
        was set aside goes — that is the owner's ruling (option 3, 2026-09-02),
        an unmeasured chart is an experiment and leaves nothing. False: the
        build failed, was stopped, or the app was closed while it ran, and every
        file goes back exactly where it was.

        THE DIFFERENCE FROM A RUN IS ONE CALLBACK, and it is the subtraction
        this class is built on: what a dead build may have left in ``cal/`` is
        "everything live that is not a result", not a list of names that could
        go stale. :func:`settle_chart_stash` is the rest.
        """
        def _leftovers():
            out = list(self.chart_files())
            if self.exports_dir.is_dir():
                out.append(self.exports_dir)
            return out
        settle_chart_stash(self.dir, stash, built=built, leftovers=_leftovers)

    def _archive_without_raising(self, results: "list[Path]",
                                 chart: "list[Path]") -> "Path | None":
        """:meth:`archive_to_old`, with the one thing a Qt slot cannot take.

        `reset()` is called from `ChartCreator.generate`, which runs inside a Qt
        slot with no `except` above it. A `cal/` the user cannot write to — a
        read-only volume, a locked folder, a permission the OS revoked — made
        `mkdir(cal/old)` raise `PermissionError` straight out of that slot, with
        the slow-chart watchdog already armed two lines earlier. Found by the
        adversarial round, 2026-09-02.

        Failing here leaves ``cal/`` exactly as it was, which is the safe end
        state: nothing archived, nothing removed, and the build that follows
        cannot write to that folder either, so it reports its own failure in the
        log the user is watching.

        **The user is not told which of the two happened, and that is an open
        item, not a decision** — a window saying so would be new text and is the
        owner's to approve. It is named in the hand-back report.
        """
        try:
            return self.archive_to_old(only=results, chart=chart)
        except OSError as exc:
            log.error("Could not archive the calibration in %s: %s — nothing "
                      "has been moved and cal/ is untouched", self.dir, exc)
            return None

    def reset(self, *, stash: bool = False) -> "CalibrationReset":
        """Make room for a new calibration chart.

        Two branches, and which one runs is decided by :meth:`result_files`.

        **Something was measured** — the calibration is KEPT, whole. The
        measurement, the ``.cal`` and any profile built from them go to the top
        of ``cal/old/<date_time>/``; the chart that made them — the ``.ti1``,
        the ``.ti2``, the ``.channels.json``, every page image and any sidecar
        beside them — goes to ``cal/old/<date_time>/chart/``, and
        ``cal/exports/`` goes with it. Nothing is deleted. This branch is
        unchanged.

        **Nothing was measured** — the chart is an EXPERIMENT and leaves
        nothing, which is what the owner ruled on 2026-09-02 (option 3 of
        `RULING-calibration-old-charts.txt`, chosen against the recommendation
        of keeping the last one) and what K6 had already asked for:
        `docs/design/per_run_description.md:400`, *"The chart is replaced, as a
        run's is."* A profile run has answered this question that way since
        `93ba45ee`: iterating on a layout ten times must not leave ten dated
        folders holding charts their owner had already decided against.

        **``stash`` IS NOT ABOUT KEEPING THE CHART. It is about the build.**
        The chart is set aside rather than unlinked, and dropped only once a
        replacement really exists — because nothing here is "regenerated"
        unless the build finishes, and a build can fail, be stopped, or be
        killed with the app. Without it, pressing Generate and then Stop would
        leave ``cal/`` with no chart at all: the ``.ti2`` is the file a printed
        sheet is read against, and the layout seed lives only inside it, so
        pages already on the desk would become waste paper. The caller settles
        the stash through :meth:`settle_chart_stash` with whether a chart was
        written; :meth:`Project.load` settles one left behind by a process that
        died. Without ``stash`` the chart is unlinked outright, which is what a
        caller that is not running a build should get.

        **``cal/exports/`` goes wherever the chart goes.** The hand-off
        sidecars (``-colours.txt``, ``-i1profiler.txt/.pxf``) describe one
        particular chart and are rebuilt from it. On the measured branch they
        travel into the archive beside it; on the unmeasured branch they go into
        the stash with it, and are dropped or restored with it. They must not
        outlive the chart they describe — a ``-colours.txt`` for a chart nobody
        can produce again is exactly the "reads like something usable and is
        not" fault Knut objected to at beta.148 — and they must not die BEFORE
        it either, which is what the run path's outright ``rmtree`` would do to
        a build that then failed.

        ``meta.json`` stays (it describes the calibration, not the chart) and is
        copied into an archive, and ``cal/chart/`` stays where it is — it is the
        copy Restore Used Chart reads. Anything already in ``cal/old/`` is left
        alone: an archive of archives helps nobody.

        Returns what happened: the archive folder, the stash folder, or neither.
        """
        # THE ENGINE PARTIAL IS SOMEBODY'S MEASUREMENT TOO, and it is why
        # "measured" is `result_files()` and not `ti3.exists()`.
        # `<stem>.ti3.engine-partial` is what a measurement that stopped part
        # way through leaves behind — an abandoned reading is still an
        # afternoon — and `Run.reset_chart_artefacts` names it explicitly as
        # something to preserve. A calibration had no such mercy: measured, it
        # survived nowhere. `result_files()` counts it, so a calibration holding
        # one takes the KEEP branch.
        results = self.result_files()
        chart = self.chart_files()
        # AN EMPTY `cal/exports/` IS NOT WORK, AND `cal/exports/` ON ITS OWN IS
        # NOT THE USER'S TO MOVE. `exports/` used to be appended whenever the
        # folder merely existed, so a `cal/` holding nothing but the empty
        # directory the app itself creates produced a whole dated archive of
        # nothing — and `reset()`'s "None when cal/ held nothing" was false.
        # Found by the adversarial round, 2026-09-02, with a one-line mutation.
        # The sidecars describe a chart: if there is no chart and no result,
        # there is nothing being replaced, so they are left exactly where they
        # are rather than moved or dropped.
        if not results and not chart:
            return CalibrationReset()
        if self.exports_dir.is_dir():
            chart.append(self.exports_dir)
        if results:
            dest = self._archive_without_raising(results, chart)
            # Whatever the move could not take (a permission error, a file that
            # appeared in between) is left where it is rather than unlinked. An
            # unarchivable file is still the user's; the build that follows will
            # overwrite what it needs to and no more.
            for p in self.live_files():
                log.warning("calibration file %s could not be archived and has "
                            "been left in cal/", p.name)
            return CalibrationReset(archive=dest, stash=None)
        stash_dir = make_chart_stash(self.dir) if stash else None
        for p in chart:
            if stash_dir is not None:
                try:
                    shutil.move(str(p), str(stash_dir / p.name))
                    continue
                except OSError as exc:
                    log.warning("Could not set the calibration chart's %s "
                                "aside: %s", p.name, exc)
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            except OSError as exc:
                log.warning("Could not remove %s: %s", p.name, exc)
        return CalibrationReset(archive=None, stash=stash_dir)


# ---------------------------------------------------------------------------
# Run — one profile build
# ---------------------------------------------------------------------------

class Run:
    """A single profile-build attempt under ``runs/<id>/``.

    Holds chart artefacts, measurement(s), optional pre-conditioning seed, and
    the built profile. All path construction lives here — callers never build
    filenames by string concatenation.
    """

    def __init__(self, project: "Project | None", run_id: str,
                 dir_override: Path | None = None) -> None:
        self._project = project
        self._run_id = run_id
        self._dir_override = dir_override

    @classmethod
    def for_dir(cls, run_dir: Path) -> "Run":
        """A project-less Run bound to an explicit folder.

        Useful where only path operations on a known run directory are needed
        (e.g. the Measure tab deriving the run from the chart's .ti1 parent)
        without threading the whole Project through. Project-dependent
        operations (new_run seeding) aren't available on such a Run.
        """
        return cls(None, run_dir.name, dir_override=run_dir)

    # ---- identity & dir
    @property
    def id(self) -> str:                      return self._run_id
    @property
    def dir(self) -> Path:
        if self._dir_override is not None:
            return self._dir_override
        return self._project.runs_root / self._run_id

    @property
    def stem(self) -> str:
        """Chart file stem = the (sanitised) project folder name.

        The run dir is ``<project>/runs/<id>``, so the project folder is
        ``dir.parents[1]``. Using the project name as the stem means printtarg
        stamps it on the printed sheet, the built ICC is self-identifying, and
        Finder shows it — while the per-run folder still removes the need for
        any state-encoding prefix/suffix. Derived from the folder so it works
        for both project-backed and Run.for_dir instances.
        """
        return self.dir.parents[1].name

    # ---- chart artefacts (regenerated by chart_creator)
    # chartread/colprof are stem-coupled (reading <stem>.ti2 → <stem>.ti3 →
    # <stem>.icc), so the whole chart chain shares the project-name stem. The
    # per-run folder removes the need for prefixes/suffixes; reads/ and the
    # role files (merged/preconditioning/calibrated) stay role-named.
    @property
    def chart_ti1(self) -> Path:              return self.dir / f"{self.stem}.ti1"
    @property
    def chart_ti2(self) -> Path:              return self.dir / f"{self.stem}.ti2"
    @property
    def chart_cht(self) -> Path:              return self.dir / f"{self.stem}.cht"
    @property
    def chart_ps(self) -> Path:               return self.dir / f"{self.stem}.ps"
    @property
    def chart_channels_json(self) -> Path:    return self.dir / f"{self.stem}.channels.json"

    def chart_tiffs(self) -> list[Path]:
        """All chart page bitmaps in this run, sorted.

        Matches both single-page `<stem>.tif` (printtarg's output for one page)
        and multi-page `<stem>_NN.tif` — the glob is `<stem>*.tif`, mirroring
        chart_creator._printtarg_done. Using `<stem>_*.tif` (underscore) would
        silently miss single-page charts.
        """
        return self.stem_files(self.stem, "*.tif", "*.TIF", "*.tiff")

    def files_matching(self, *patterns: str) -> list[Path]:
        """This run's files matching *patterns*, accent spelling and all.

        For "which files in this run are called <stem>-something" use
        :meth:`stem_files`, which takes the name as a literal. This one is for
        a pattern that is genuinely a pattern — see :func:`files_matching`.
        """
        return files_matching(self.dir, *patterns)

    def stem_files(self, stem: str, *tails: str) -> list[Path]:
        """This run's files called *stem* + one of *tails*.

        The one way anything in ChromIQ asks "which files in this run are
        called <stem>-something". `Path.glob` is not, because it compares
        spellings rather than names; and an f-string is not, because a folder
        somebody renamed to ``Chart [v2]`` in Finder stops being a name the
        moment it is pasted into a pattern — see :func:`stem_files`.
        """
        return stem_files(self.dir, stem, *tails)

    # ---- measurements
    # The canonical measurement is ``<stem>.ti3`` — chartread is stem-coupled
    # (reading ``<stem>.ti2`` produces ``<stem>.ti3``). Per-read averaging
    # snapshots live in reads/readN.ti3 and are averaged back into <stem>.ti3.
    @property
    def measurement_ti3(self) -> Path:        return self.dir / f"{self.stem}.ti3"
    @property
    def reads_dir(self) -> Path:              return self.dir / "reads"

    def reads(self) -> list[Path]:
        """Sorted list of reads/readN.ti3 files."""
        if not self.reads_dir.exists():
            return []
        found: list[tuple[int, Path]] = []
        for f in self.reads_dir.glob("read*.ti3"):
            m = _NEW_READ_RE.match(f.stem)
            if m:
                found.append((int(m.group(1)), f))
        found.sort(key=lambda t: t[0])
        return [f for _, f in found]

    def next_read_index(self) -> int:
        reads = self.reads()
        if not reads:
            return 1
        nums = [int(_NEW_READ_RE.match(f.stem).group(1)) for f in reads]
        return max(nums) + 1

    def next_read_path(self) -> Path:
        return self.reads_dir / f"read{self.next_read_index()}.ti3"

    def clear_reads(self) -> None:
        """Clear the averaging inputs — by ARCHIVING them, never destroying.

        `reads/readN.ti3` are measurements somebody stood at an instrument to
        make. This called `shutil.rmtree` on the whole folder with no archive
        and nothing in the Trash, and it is reachable from a button: "Measure
        again to average" (`ui/tabs/tab_measure.py`). The standing rule is that
        user work is archived, never deleted, and a report predicted this caller
        before anyone checked that it already existed.
        """
        if not self.reads_dir.exists():
            return
        keep = [p for p in self.reads_dir.rglob("*") if p.is_file()]
        if keep:
            from workflow.chart_import import _archive_project_contents
            try:
                dest = _archive_project_contents(self.reads_dir)
                log.info("cleared %d read(s); they are kept at %s",
                         len(keep), dest)
                return
            except OSError as exc:
                # NEVER fall back to destroying them — that is the behaviour
                # this exists to remove. Leave them and say why.
                log.error("the previous reads could not be archived (%s); they "
                          "are left in place at %s", exc, self.reads_dir)
                return
        shutil.rmtree(self.reads_dir)

    def promote_measurement_to_read(self) -> Path:
        """Move ``chart.ti3`` to the next ``reads/readN.ti3`` slot.

        Used when the user clicks "Measure again to average" — the just-finished
        measurement becomes the first (or next) input to averaging.
        Returns the new path.
        """
        if not self.measurement_ti3.exists():
            raise FileNotFoundError(
                f"Nothing to promote: {self.measurement_ti3} does not exist"
            )
        self.reads_dir.mkdir(parents=True, exist_ok=True)
        dst = self.next_read_path()
        shutil.move(str(self.measurement_ti3), str(dst))
        log.info("Promoted measurement to %s", dst.name)
        return dst

    # ---- the engine's partial-measurement backup
    @property
    def partial_ti3(self) -> Path:
        """The engine's partial measurement, copied aside before stock chartread
        resumes from it (#134). Named here rather than rebuilt from a string at
        each site, so it can never be forgotten by one of them — which is how it
        came to be left behind when a re-generation archived the .ti3 it belongs
        to (Knut, #130 2026-07-30)."""
        return self.dir / f"{self.stem}.ti3.engine-partial"

    def recoverable_partial_ti3(self) -> "Path | None":
        """The partial measurement when it is the ONLY record of those readings —
        i.e. the backup is there and the measurement it was taken from is not.

        Real ink on real paper that nothing in the app would otherwise offer
        back: Knut loaded a run holding just such a file and the Measure tab
        showed no resume, no overlay and no warning (#130, 2026-07-30)."""
        p = self.partial_ti3
        return p if p.is_file() and not self.measurement_ti3.exists() else None

    # ---- pre-conditioning (set when this run was created from a parent)
    @property
    def preconditioning_ti3(self) -> Path:    return self.dir / "preconditioning.ti3"
    @property
    def preconditioning_icc(self) -> Path:    return self.dir / "preconditioning.icc"

    def has_preconditioning(self) -> bool:
        return self.preconditioning_ti3.exists() and self.preconditioning_icc.exists()

    # ---- build-time merge output (only when chromiq_refinement is on)
    # merged.ti3 = average -m of chart.ti3 + preconditioning.ti3, fed to
    # colprof to build merged.icc. The clean chart.ti3 stays untouched for
    # Check/Refine (Architecture D).
    @property
    def merged_ti3(self) -> Path:             return self.dir / "merged.ti3"
    @property
    def merged_icc(self) -> Path:             return self.dir / "merged.icc"

    # ---- profile output
    # colprof reading <stem>.ti3 writes <stem>.icc (stem-coupled). When a merge
    # ran, the deliverable is merged.icc instead — see built_profile_icc().
    @property
    def profile_icc(self) -> Path:            return self.dir / f"{self.stem}.icc"

    def built_profile_icc(self) -> Path:
        """The profile a user should treat as the run's output.

        ``merged.icc`` when a pre-conditioning merge produced one, else the
        plain ``chart.icc``.
        """
        return self.merged_icc if self.merged_icc.exists() else self.profile_icc

    # ---- applycal output (calibration baked into a built profile)
    @property
    def calibrated_icc(self) -> Path:         return self.dir / "calibrated.icc"

    # ---- v2 sub-folders (#127)
    # reports/ — quality checks, refine lists, measurement reports.
    # exports/ — the chart's hand-off files for other programs.
    # cache/   — tool intermediates; always safe to delete.
    @property
    def reports_dir(self) -> Path:            return self.dir / REPORTS_DIRNAME
    @property
    def exports_dir(self) -> Path:            return self.dir / EXPORTS_DIRNAME
    @property
    def cache_dir(self) -> Path:              return self.dir / CACHE_DIRNAME

    def ensure_reports_dir(self) -> Path:     return ensure_subdir(self.reports_dir)
    def ensure_exports_dir(self) -> Path:     return ensure_subdir(self.exports_dir)
    def ensure_cache_dir(self) -> Path:       return ensure_subdir(self.cache_dir)

    # ---- verification runs (#130)
    # runs/runN/verifications/ holds ONE shared verify chart (a smaller chart
    # printed through this run's profile) at its root, plus one dated sub-folder
    # per verification measurement. Profiling reports and verification reports
    # therefore live in physically separate folders and never mix.
    @property
    def verifications_dir(self) -> Path:      return self.dir / VERIFICATIONS_DIRNAME
    @property
    def verify_stem(self) -> str:             return f"{self.stem}-verify"
    @property
    def verify_chart_ti1(self) -> Path:       return self.verifications_dir / f"{self.verify_stem}.ti1"
    @property
    def verify_chart_ti2(self) -> Path:       return self.verifications_dir / f"{self.verify_stem}.ti2"
    @property
    def verify_chart_cht(self) -> Path:       return self.verifications_dir / f"{self.verify_stem}.cht"
    @property
    def verify_chart_ps(self) -> Path:        return self.verifications_dir / f"{self.verify_stem}.ps"
    @property
    def verify_chart_channels_json(self) -> Path:
        return self.verifications_dir / f"{self.verify_stem}.channels.json"

    def verify_chart_tiffs(self) -> list[Path]:
        return stem_files(self.verifications_dir, self.verify_stem, "*.tif")

    def has_verify_chart(self) -> bool:       return self.verify_chart_ti2.exists()

    def verifications(self) -> "list[Verification]":
        """Dated verification runs, oldest-first (folder id = timestamp)."""
        vdir = self.verifications_dir
        if not vdir.exists():
            return []
        ids = sorted(d.name for d in vdir.iterdir()
                     if d.is_dir() and _VERIFY_ID_RE.match(d.name))
        return [Verification(self, vid) for vid in ids]

    def verification(self, vid: str) -> "Verification":
        return Verification(self, vid)

    def new_verification(self, when: "datetime | None" = None) -> "Verification":
        """A fresh dated verification folder (not yet created on disk)."""
        when = when or datetime.now()
        base = when.strftime("%Y-%m-%d_%H%M%S")
        v = Verification(self, base)
        n = 1
        while v.dir.exists():          # same-second collision → suffix
            v = Verification(self, f"{base}_{n}")
            n += 1
        return v

    #: Chart-file extensions moved when a generated chart becomes a verify chart.
    _CHART_EXTS = (".ti1", ".ti2", ".cht", ".ps", ".channels.json",
                   ".strips.json", ".cie", ".pdf")

    def adopt_run_chart_as_verify(self) -> "Path | None":
        """Move a just-generated chart from the run root into ``verifications/``
        as this run's shared verify chart, renaming ``<stem>.*`` → ``<stem>-
        verify.*`` (#130). Only the chart files + page TIFFs move — never the
        measurement (``.ti3``) or profile (``.icc``). Returns the moved verify
        ``.ti2``, or None when there's no chart at the run root to adopt.

        Guarded by construction: nothing calls this unless the user chose Run
        type = Verification, so the normal profiling flow is untouched."""
        if not self.chart_ti2.exists():
            return None
        self.verifications_dir.mkdir(parents=True, exist_ok=True)
        # Clear any previous verification chart first. Regenerating a smaller
        # verify chart (fewer pages) would otherwise leave the old higher-numbered
        # page TIFFs behind, and verify_chart_tiffs() globs the folder — so the
        # preview kept showing a phantom extra page (Knut #130 beta-2 test #2).
        self._clear_verify_chart_files()
        old, new = self.stem, self.verify_stem
        moved_ti2: "Path | None" = None
        for ext in self._CHART_EXTS:
            src = self.dir / f"{old}{ext}"
            if src.exists():
                dst = self.verifications_dir / f"{new}{ext}"
                shutil.move(str(src), str(dst))
                if ext == ".ti2":
                    moved_ti2 = dst
        # NFC on both sides of the rename as well as the match: a page whose
        # name came off an HFS+ volume is spelled differently from `old`, so
        # `str.replace` would find nothing and move the page to verifications/
        # still carrying the PROFILING stem — a verify chart with a page the
        # verify glob cannot see.
        for tif in self.stem_files(old, "_*.tif"):
            dst = self.verifications_dir / nfc(tif.name).replace(nfc(old),
                                                                nfc(new), 1)
            shutil.move(str(tif), str(dst))
        # A single-page chart's TIFF has no "_NN" suffix — it's just "<stem>.tif"
        # — so the glob above misses it. Move that too, or a single-page verify
        # chart lands in verifications/ with no page bitmap and never previews
        # (Knut #130: "Run type = Verification shows no preview").
        single_tif = self.dir / f"{old}.tif"
        if single_tif.exists():
            shutil.move(str(single_tif), str(self.verifications_dir / f"{new}.tif"))
        # The chart's hand-off sidecars (exports/) belong with the verify chart.
        exp = self.exports_dir
        if exp.exists():
            vexp = self.verifications_dir / EXPORTS_DIRNAME
            vexp.mkdir(parents=True, exist_ok=True)
            for f in list(exp.iterdir()):
                if f.is_file() and nfc(f.name).startswith(nfc(old)):
                    shutil.move(str(f), str(
                        vexp / nfc(f.name).replace(nfc(old), nfc(new), 1)))
        return moved_ti2

    def _clear_verify_chart_files(self) -> None:
        """**Archive** the shared verification CHART files at the
        ``verifications/`` root (``<verify_stem>.*`` + ``<verify_stem>_NN.tif``
        + the exports sidecars) into ``verifications/old/<date>/`` — never
        delete them. Found on hardware (Sebastian, 2026-08-10): a regenerate
        deleted the gamut chart and its colorimetric reference outright while
        the replace window promised "moved to the 'old' folder … nothing is
        deleted"; only the measured date's snapshot preserved the chart. The
        dated ``verifications/<date>/`` measurement folders are named by
        timestamp, not by the verify stem, so they are never matched — the
        verification HISTORY is untouched, only the reusable chart is
        replaced (#130)."""
        vdir = self.verifications_dir
        if not vdir.exists():
            return
        stem = self.verify_stem
        targets = [p for p in stem_files(vdir, stem, "*") if p.is_file()]
        vexp = vdir / EXPORTS_DIRNAME
        if vexp.is_dir():
            targets += [f for f in stem_files(vexp, stem, "*")
                        if f.is_file()]
        try:
            self.archive_to_old(targets, into=self.verifications_old_dir)
        except OSError as exc:
            # Archiving must never abort the adopt — but deleting is not an
            # acceptable fallback either, so leave what could not move.
            log.warning("Could not archive the displaced verify chart: %s", exc)

    # ---- overwrite safety: "start fresh" archive (#130)
    @property
    def old_dir(self) -> Path:                return self.dir / "old"
    @property
    def chart_snapshot_dir(self) -> Path:
        """``runs/runN/chart/`` — a copy of the chart this run was measured
        with (#130). Taken when a measurement starts, and what
        **Restore Used Chart** puts back for a profiling run."""
        return self.dir / CHART_SNAPSHOT_DIRNAME

    @property
    def verifications_old_dir(self) -> Path:
        """``runs/runN/verifications/old/`` — where a **verification** Replace
        archives what it displaces (#130, Knut). A verification only ever acts
        on the files inside ``verifications/``, so its history stays inside that
        folder rather than landing in the run's own ``old/``."""
        return self.verifications_dir / "old"

    def archive_to_old(self, paths: "list[Path]",
                       when: "datetime | None" = None,
                       *, into: "Path | None" = None) -> "Path | None":
        """Move existing *paths* (files or folders) into a timestamped
        ``runs/runN/old/<date>/`` folder before an overwrite, so "start fresh"
        never silently destroys the previous measurement / profile / reports
        (#130, Knut). Missing paths are skipped; name clashes get a numeric
        suffix. Returns the archive folder, or None when nothing existed.

        *into* overrides the base folder — used by a verification Replace, which
        archives into ``verifications/old/`` instead (see
        :attr:`verifications_old_dir`)."""
        existing = [p for p in paths if p.exists()]
        if not existing:
            return None
        when = when or datetime.now()
        dest = (into or self.old_dir) / when.strftime("%Y-%m-%d_%H%M%S")
        dest.mkdir(parents=True, exist_ok=True)
        for p in existing:
            target = dest / p.name
            n = 1
            while target.exists():
                target = dest / f"{p.stem}_{n}{p.suffix}"
                n += 1
            shutil.move(str(p), str(target))
            log.info("archived %s -> old/%s/", p.name, dest.name)
        return dest

    # ---- meta
    @property
    def meta_path(self) -> Path:              return self.dir / "meta.json"

    def load_meta(self) -> RunMeta:
        """``runs/runN/meta.json``, or a fresh one when it cannot be read.

        A truncated or half-written file used to raise here, while the very
        same corruption in ``cal/meta.json`` was survived — ``Calibration``
        has treated "unreadable" as "absent" all along. The inconsistency was
        not academic: every caller of this is wrapped in a broad ``except``, so
        the run simply stopped storing anything, silently and for good.

        Knut's D2 case (*"some cases can occur if user deletes a file"*).
        Atomic writes make ChromIQ unlikely to produce one, but a crashed
        editor, a full disk or a sync client still can.
        """
        if not self.meta_path.exists():
            return RunMeta.fresh(self._run_id)
        try:
            raw = json.loads(self.meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("%s is unreadable — treating it as a fresh run",
                        self.meta_path)
            return RunMeta.fresh(self._run_id)
        return RunMeta.from_dict(raw)

    def save_meta(self, meta: RunMeta) -> None:
        write_json_atomically(self.meta_path, asdict(meta))

    # ---- lifecycle
    def ensure_dir(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir

    #: The module-level names, kept as attributes because callers and tests use
    #: them through the class. ONE prefix and ONE marker for a run and for the
    #: calibration alike — see :func:`settle_chart_stash`.
    CHART_STASH_PREFIX = CHART_STASH_PREFIX
    STASH_SUPERSEDED = STASH_SUPERSEDED

    def chart_stash_dirs(self) -> list[Path]:
        """Every chart stash left in this run, oldest first."""
        return chart_stash_dirs(self.dir)

    def chart_artefact_names(self) -> list:
        """Every chart file name this run can hold, page images aside.

        Shared so the wipe and the restore agree about what a chart IS. They
        did not: a build stopped after the page count had been raised left
        `_02.tif` and `_03.tif` behind, because putting a chart back only walks
        the STASH, and a page the old chart never had is not in it. The run then
        showed three pages for a one-page `.ti2`.
        """
        s = self.stem
        return [f"{s}.ti1", f"{s}.ti2", f"{s}.cht", f"{s}.cie", f"{s}.ps",
                f"{s}.pdf", f"{s}.channels.json", f"{s}.strips.json"]

    def settle_chart_stash(self, stash: "Path | None", *, built: bool) -> None:
        """Finish what :meth:`reset_chart_artefacts` started.

        The whole of it lives in :func:`settle_chart_stash`, which the
        calibration slot uses too. All this adds is the run's own answer to the
        one question that differs: what a build which produced no chart may have
        left behind in the folder. For a run that is every name a chart can have
        plus every page image, because putting a chart back used to walk only
        the STASH — so a build stopped after the page count had been raised left
        `_02.tif` and `_03.tif` behind, and the run showed three pages for a
        one-page `.ti2`.
        """
        def _leftovers():
            return ([self.dir / n for n in self.chart_artefact_names()]
                    + list(self.chart_tiffs()))
        settle_chart_stash(self.dir, stash, built=built, leftovers=_leftovers)

    def reset_chart_artefacts(self, *, keep_results: bool = False,
                              stash: bool = False) -> "Path | None":
        """Wipe chart files + reads + measurement + merged + profile.

        ``keep_results`` redraws the pages of the chart that is already there
        without touching the measurement or the profile — the case of **Restore
        Used Chart**, which puts back the very chart a result was measured with
        (Knut, #130 2026-07-27). Everything else still goes: the page images and
        sidecars are about to be rebuilt from the same recipe.

        Preserves ``preconditioning.*`` and ``meta.json`` so the run's identity
        and pre-conditioning seed survive a chart re-generation, and
        ``reports/`` — past quality checks document history. ``reads/`` is
        archived beside the measurement it belongs to; ``exports/`` and
        ``cache/`` are derived from the chart and go with it.

        ``stash`` MOVES THE CHART ASIDE INSTEAD OF DELETING IT, and returns the
        folder it moved it to; the caller then calls :meth:`settle_chart_stash`
        with whether a new chart was really written. This method runs BEFORE
        targen, and the chart it clears is only "regenerated" if the build
        finishes — so a build that failed, was stopped, or was interrupted by
        the app closing used to leave the run with no chart at all. The `.ti2`
        went with it, which is the file a printed sheet is read against, and the
        layout seed lives only in that `.ti2` — so pages already on the desk
        became waste paper, and rebuilding from the same settings produced a
        chart that no longer matched them. Measured on screen, 2026-08-28: seven
        files gone from an unmeasured run, none archived, no window shown.

        NOT archived to ``old/``, though that would also have worked: Knut ruled
        the other way for the calibration chart at beta.148 — only measurements
        belong in ``old/``, or it stops being readable — and a run with nothing
        to lose must not spawn an ``old/`` folder at all. A stash costs neither.
        """
        stash_dir: "Path | None" = None
        s = self.stem
        # #130 (Knut, critical): a chart re-generation must NEVER delete the
        # run's finished MEASUREMENT / PROFILE — they can't be regenerated. If
        # this run already has results, archive them (and the reports that
        # document them) to old/<timestamp>/ first. Chart files (below) are
        # regenerated, so they may be dropped. Only archives when results exist,
        # so iterating on a not-yet-measured chart doesn't spawn old/ folders.
        results = [self.dir / f"{s}.ti3", self.partial_ti3,
                   self.dir / f"{s}.icc",
                   self.dir / f"{s}.icm", self.dir / "merged.ti3",
                   self.dir / "merged.icc", self.dir / "calibrated.icc"]
        if keep_results:
            results = []
        # reads/ IS ARCHIVED, NOT DELETED. `clear_reads()` used to `rmtree` it
        # at the end of this method — while §4 W4 of the model says, in as many
        # words, *"Everything is kept in old/ and nothing is deleted"*, and this
        # method's own comment repeated it. Measured on a finished run: 26 files
        # in, 5 archived, 6 left alone and 15 destroyed, among them
        # `reads/read1..3.ti3` — the individual instrument readings someone took
        # by hand, which cannot be regenerated from anything on disk, while the
        # averaged .ti3 built FROM them was carefully archived.
        #
        # An EMPTY reads/ folder is not work, though, and archiving it would
        # break the rule one line above: a run with nothing to lose spawns no
        # old/ folder.
        archive = [p for p in results if p.exists()]
        if not keep_results and any(self.reads_dir.glob("*")):
            archive.append(self.reads_dir)
        if archive:
            self.archive_to_old(archive)
        # exports/ AND cache/ ARE DERIVED, and go with the chart they describe.
        # Archiving exports/ as well looked like the same kindness and was not:
        # the sidecars are rebuilt from the chart on every build, so it broke
        # the rule that a run with no results spawns no `old/` folder — every
        # live-preview render started leaving one behind.
        for sub in (self.exports_dir, self.cache_dir):
            if sub.exists():
                try:
                    shutil.rmtree(sub)
                except OSError as exc:
                    log.warning("Could not delete %s: %s", sub, exc)
        def _drop(p: Path) -> None:
            """Delete, or set aside in the stash when the caller asked for one."""
            nonlocal stash_dir
            if stash and stash_dir is None:
                stash_dir = make_chart_stash(self.dir)
            if stash and stash_dir is not None:
                try:
                    shutil.move(str(p), str(stash_dir / p.name))
                    return
                except OSError as exc:
                    log.warning("Could not set %s aside: %s", p, exc)
            try:
                p.unlink()
            except OSError as exc:
                log.warning("Could not delete %s: %s", p, exc)

        for name in (
            f"{s}.ti1", f"{s}.ti2", f"{s}.cht", f"{s}.cie", f"{s}.ps",
            f"{s}.pdf",                  # vector-PDF export (was left stale, Basti)
            f"{s}.channels.json", f"{s}.strips.json",
        ) + ((
            f"{s}.ti3",                  # the measurement (chartread output)
            f"{s}.ti3.engine-partial",   # …and the engine partial beside it
            f"{s}.icc",                  # the profile (colprof output)
            "merged.ti3", "merged.icc",  # build-time refinement merge outputs
            "calibrated.icc",            # applycal output
        ) if not keep_results else ()):
            p = self.dir / name
            if p.exists():
                _drop(p)
        for tiff in self.chart_tiffs():
            _drop(tiff)
        # The reads went with the measurement, into old/ — see above. Anything
        # left behind (an empty reads/ folder, or one that appeared between the
        # archive and here) is swept so the run starts clean.
        if not keep_results and self.reads_dir.exists():
            self.clear_reads()
        return stash_dir


# ---------------------------------------------------------------------------
# Verification — one dated verification run under a Run (#130)
# ---------------------------------------------------------------------------

class Verification:
    """One dated verification measurement: ``runs/runN/verifications/<id>/``.

    Holds only the measurement (``<stem>-verify.ti3``) + its own ``reads/`` and
    ``reports/``; the (shared, smaller) verify chart lives one level up, at the
    ``verifications/`` root, owned by the :class:`Run`. A verification grades the
    run's built profile — never overwrites the profiling measurement, and never
    produces a profile itself."""

    def __init__(self, run: "Run", vid: str) -> None:
        self._run = run
        self._vid = vid

    @classmethod
    def for_dir(cls, vdir: Path) -> "Verification":
        """A project-less Verification for path ops on a known dated folder
        (``…/runs/runN/verifications/<id>``)."""
        run = Run.for_dir(vdir.parents[1])
        return cls(run, vdir.name)

    @property
    def id(self) -> str:                      return self._vid
    @property
    def run(self) -> "Run":                   return self._run
    @property
    def dir(self) -> Path:                    return self._run.verifications_dir / self._vid
    @property
    def stem(self) -> str:                    return self._run.verify_stem
    @property
    def measurement_ti3(self) -> Path:        return self.dir / f"{self.stem}.ti3"
    @property
    def reads_dir(self) -> Path:              return self.dir / "reads"
    @property
    def reports_dir(self) -> Path:            return self.dir / REPORTS_DIRNAME
    @property
    def cache_dir(self) -> Path:              return self.dir / CACHE_DIRNAME

    def ensure_dir(self) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir

    def exists(self) -> bool:                 return self.measurement_ti3.exists()


# ---------------------------------------------------------------------------
# Project — the work_dir root
# ---------------------------------------------------------------------------

# Emergency fallback only — the real guide comes from ui.file_guide (one
# source for the Welcome/Help card and this file); see Project.write_readme.
_PROJECT_README_FALLBACK = """\
ChromIQ project: {name}

  runs/runN/{name}_01.tif        <- the printable chart pages
  runs/runN/{name}.ti3           <- your measurements (keep!)
  runs/runN/{name}.icc           <- your finished ICC profile
  runs/runN/reports/             <- quality checks & measurement reports
  runs/runN/exports/             <- files for other programs (i1Profiler ...)
  runs/runN/cache/               <- temporary tool files, always safe to delete
  runs/runN/reads/               <- individual readings when averaging
  cal/                           <- optional printer calibration (shared)
  exports/                       <- Tools-menu exports (project-wide)

Keep your measurements ({name}.ti3, reads/, cal/{name}-cal.ti3) — they are
real ink on real paper. Everything in cache/ is always safe to delete.
"""



#: Marker added to a file that already occupies the name a rename needs
#: (#130, Knut 2026-07-27). Underscores rather than parentheses, which some
#: tools and shells treat specially on one platform or another.
CONFLICT_MARKER = "_conflicted_at_renaming_procedure"


def _move_aside_conflict(path: Path) -> "Path | None":
    """Move *path* out of the way so a rename can take its name.

    Returns where it went, or None when it could not be moved — in which case
    the caller leaves everything as it was rather than risk losing a file. A
    number is appended if the marked name is taken too, so renaming twice
    cannot overwrite the first file moved aside.
    """
    stem, suffix = path.stem, path.suffix
    candidate = path.with_name(f"{stem}{CONFLICT_MARKER}{suffix}")
    n = 2
    while candidate.exists():
        candidate = path.with_name(f"{stem}{CONFLICT_MARKER}_{n}{suffix}")
        n += 1
    try:
        path.rename(candidate)
    except OSError as exc:
        log.warning("Could not move the conflicting file aside: %s (%s)",
                    path, exc)
        return None
    log.warning("A file was already called %s; moved it aside to %s",
                path.name, candidate.name)
    return candidate


#: What a duplicated run inherits from its source, and what it must not.
#:
#: These two sets partition `RunMeta` EXHAUSTIVELY — `tests/
#: test_a_duplicate_carries_its_settings.py` asserts they are disjoint and
#: together name every field. That is deliberate: a deny-list alone would make a
#: newly added field carried by accident, and an allow-list alone would make it
#: dropped by accident. With a partition, adding a field to `RunMeta` fails a
#: test until somebody decides which side it belongs on.
DUPLICATE_META_FRESH: frozenset = frozenset({
    # Identity — the copy is its own run, made now.
    "run_id", "created_at",
    # Set explicitly to the source; inherited, a chain of copies would all
    # point at the first run instead of at the one they came from.
    "duplicated_from",
    # Rewritten as "(copy) <source>" below, so two runs cannot read as the
    # same work.
    "description",
    # `verifications/` is deliberately NOT copied, so notes about a
    # verification sheet would describe a sheet the copy does not have.
    "verify_chart_notes",
    # Becomes the ICC's Description tag: copied verbatim, two different
    # profiles would ship under one name. Empty means "automatic", which
    # regenerates from the project name and the copy's own "(copy) …".
    "profile_description",
    # Lifecycle, and nothing in the app reads or writes it — leave it at the
    # fresh default rather than propagate a state nothing maintains.
    "status",
})

DUPLICATE_META_CARRY: frozenset = frozenset({
    # The five settings groups — the whole point. `create_chart_ui` carries
    # Guided's instrument/paper/pages, the engine toggle and the layout recipe;
    # without it "the same settings" would still build a different sheet.
    "create_chart_settings", "create_chart_ui", "measure_settings",
    "profile_settings", "print_settings",
    # Describes the copied measurement (`reads/**/*` come across).
    "averaging_enabled", "averaging_method", "averaging_read_count",
    # Describes the copied chart.
    "instrument", "paper", "chart_notes", "scanner_target_enabled",
    "chart_snapshot_stale",
    # Describes the copied profile.
    "profile_built_from", "calibration_used",
    # Describes the copied preconditioning (`preconditioning.ti3`/`.icc`).
    # `run_delete._rewrite_metas` renumbers both, so the reference stays live.
    "parent_run", "preconditioning_source_run",
    # TI2-editor state, which cannot be recovered from the .ti2 alone.
    "editor_layout", "editor_basename", "editor_recipe",
})


class Project:
    """A working-folder project. Owns ``project.json`` and all runs."""

    MANIFEST = "project.json"
    README   = "Where are my files.txt"

    def __init__(self, root: Path, manifest: ProjectManifest) -> None:
        self._root = root
        self._manifest = manifest
        #: True when project.json carries a schema newer than this build knows.
        #: The project still opens (no format ever moves the valuable files),
        #: but the UI should tell the user to update ChromIQ (#127).
        self.schema_too_new: bool = manifest.schema_version > SCHEMA_VERSION
        #: How many files the truncated-stem repair renamed on THIS load (0 for
        #: every project that was never affected). NOTHING READS THIS YET. The
        #: comment here used to claim "the window uses it for one statusbar
        #: line", and no such line exists: a repair renames files in a user's
        #: project and tells them nothing but a log line. Surfacing it needs new
        #: user-facing text, which per CLAUDE.md goes to §M-PROPOSED first — so
        #: until that lands, this is a hook, and it is labelled as one.
        self.repaired_names: int = 0

    # ---- identity
    @property
    def root(self) -> Path:                   return self._root
    @property
    def target_name(self) -> str:             return self._manifest.target_name
    @property
    def runs_root(self) -> Path:              return self._root / "runs"
    @property
    def exports_dir(self) -> Path:            return self._root / "exports"
    @property
    def calibration(self) -> Calibration:    return Calibration(self._root)
    @property
    def manifest_path(self) -> Path:          return self._root / self.MANIFEST
    @property
    def readme_path(self) -> Path:            return self._root / self.README

    # ---- manifest I/O
    @classmethod
    def create(cls, root: Path, target_name: str) -> "Project":
        """Create a fresh project at ``root`` with ``run1`` prepared."""
        manifest = ProjectManifest.fresh(target_name)
        proj = cls(root, manifest)
        proj._root.mkdir(parents=True, exist_ok=True)
        proj.runs_root.mkdir(parents=True, exist_ok=True)
        run = proj.current_run()
        run.ensure_dir()
        run.save_meta(RunMeta.fresh("run1"))
        proj.save_manifest()
        proj.write_readme()
        log.info("Created project at %s", root)
        return proj

    @classmethod
    def load(cls, root: Path) -> "Project":
        mp = root / cls.MANIFEST
        if not mp.exists():
            raise FileNotFoundError(f"No project manifest at {mp}")
        data = json.loads(mp.read_text(encoding="utf-8"))
        proj = cls(root, ProjectManifest.from_dict(data))
        if proj.schema_too_new:
            log.warning(
                "Project %s has schema_version %s (this build knows %s) — "
                "opening without migration; update ChromIQ.",
                root, proj._manifest.schema_version, SCHEMA_VERSION)
        elif proj._manifest.schema_version < SCHEMA_VERSION:
            # Cumulative, idempotent migrations. Capture the ORIGINAL version
            # first — _migrate_v1_to_v2 bumps schema_version to SCHEMA_VERSION,
            # which would otherwise make the v2→v3 check skip itself.
            orig = proj._manifest.schema_version
            if orig < 2:
                proj._migrate_v1_to_v2()
            if orig < 3:
                proj._migrate_v2_to_v3()
            proj._manifest.schema_version = SCHEMA_VERSION
            proj.save_manifest()
        # Backfill the README for projects created before it shipped — and
        # rewrite a 0-byte file, which is exactly the artefact a pre-fix Windows
        # build left behind: write_readme crashed mid-write (UnicodeEncodeError
        # encoding the template's arrows under the cp1252 default), leaving the
        # file created but empty. Never touch a non-empty file — the user is
        # free to edit theirs (the v1→v2 migration is the one deliberate
        # exception: it regenerates the guide so it describes the new layout).
        rp = proj.readme_path
        if not rp.exists() or rp.stat().st_size == 0:
            proj.write_readme()
        # PUT BACK A CHART WHOSE BUILD NEVER FINISHED. `reset_chart_artefacts`
        # sets the old chart aside before targen runs and the build settles it
        # afterwards — but a build interrupted by the app CLOSING never reaches
        # that point, and closing the window is exactly what a person does when
        # a build is taking too long, because there is no Stop button. So the
        # stash is settled here instead, on the next open.
        #
        # Which way it ended is decided from what is on disk — see below.
        try:
            for _run in proj.all_runs():
                for _stash in _run.chart_stash_dirs():
                    # A STASH THAT IS STILL HERE MEANS THE BUILD NEVER FINISHED.
                    # That is exact, not a guess: every ending a build can have
                    # goes through `_finish`, which settles the stash and removes
                    # it, so one that survives belongs to a process that died.
                    #
                    # The guess this replaces asked whether the run held a
                    # `.ti2` and a page image — and printtarg writes the page at
                    # 0.28 s and the `.ti2` at 0.49 s of a 1.4 s build, so that
                    # was true for most of every build. Measured on screen: the
                    # complete original was dropped and the interrupted build's
                    # half a chart kept.
                    #
                    # The one exception is marked inside the stash itself.
                    _built = (_stash / Run.STASH_SUPERSEDED).exists()
                    log.info("Found a chart set aside in %s by a build that "
                             "never finished — %s", _run.dir,
                             "it was superseded, so the copy is dropped"
                             if _built else "putting it back")
                    _run.settle_chart_stash(_stash, built=_built)
            # …AND THE CALIBRATION'S, which is set aside the same way and by the
            # same code since the owner ruled that an unmeasured calibration
            # chart is an experiment (2026-09-02). A stash left in `cal/` by a
            # process that died is the one case where the user would otherwise
            # be left with neither chart: the old one hidden in a dot-folder and
            # no new one built.
            _cal = proj.calibration
            for _stash in _cal.chart_stash_dirs():
                _built = (_stash / STASH_SUPERSEDED).exists()
                log.info("Found a calibration chart set aside in %s by a build "
                         "that never finished — %s", _cal.dir,
                         "it was superseded, so the copy is dropped"
                         if _built else "putting it back")
                _cal.settle_chart_stash(_stash, built=_built)
        except Exception as exc:      # noqa: BLE001 — opening must never fail
            log.warning("Could not settle a leftover chart stash: %s", exc)
        # Repair file stems truncated by the pre-4.1.3-beta.16 layout-engine
        # bug. Deliberately NOT gated on schema_version: being affected depends
        # on the project's NAME and on which build made its chart, not on the
        # manifest format, and a schema bump would run once and then never
        # again on a project an older ChromIQ had re-broken. It is free for an
        # undotted project (one string operation) and one stat() for a project
        # already repaired. See core/name_repair.py for why it cannot touch the
        # wrong file, and CHROMIQ_NAME_REPAIR=dry to see what it would do.
        try:
            from core.name_repair import repair_project
            from core.version import APP_VERSION
            proj.repaired_names = repair_project(proj, app_version=APP_VERSION)
        except Exception as exc:      # noqa: BLE001 — opening must never fail
            log.warning("name repair skipped for %s: %s", root, exc)
        return proj

    @classmethod
    def create_or_load(cls, root: Path, target_name: str) -> "Project":
        """Open the project at *root*, creating it if it is not there yet.

        SAY WHICH OF THE TWO HAPPENED. Adopting a project that already exists
        and creating a brand-new one are very different events for the person
        reading a log afterwards — the first means the work about to be done
        lands on somebody's existing chart, measurement and profile. Knut's
        2026-08-27 log has this moment in it (he typed the name of a project he
        already had) and there is no line anywhere that says so; only
        "Target name set to: test", which reads identically either way.
        """
        if (root / cls.MANIFEST).exists():
            proj = cls.load(root)
            try:
                runs = len(proj.all_runs())
            except Exception:      # noqa: BLE001 — a log line is never worth a crash
                runs = -1
            log.info("opened the EXISTING project at %s (%s run(s) on disk)",
                     root, runs if runs >= 0 else "?")
            return proj
        log.info("created a NEW project '%s' at %s", target_name, root)
        return cls.create(root, target_name)

    # ---- v1 → v2 migration (#127)
    #
    # v1 kept everything flat in each run folder; v2 groups the ChromIQ-only
    # files into reports/ (quality checks, refine lists), exports/ (hand-off
    # sidecars) and cache/ (tool intermediates). Only files matching the exact
    # patterns ChromIQ itself writes are moved — user files are never touched,
    # nothing is renamed or deleted, and the Argyll-coupled chain stays put.
    # Idempotent: a re-run (e.g. after a crash mid-migration) finds nothing
    # left to move and simply bumps the schema again.

    # Quality_Check_<n>_<stem>.txt / Refine_Strips_<stem>.txt → reports/
    _MIG_REPORTS = (
        re.compile(r"^Quality_Check_\d+_.+\.txt$"),
        re.compile(r"^Refine_Strips_.+\.txt$"),
    )
    # scanner-tool intermediates (current and legacy naming) → cache/
    _MIG_CACHE = (
        re.compile(r"^.+-patchbox\.cht$"),
        re.compile(r"^.+-patchbox-sample\.cht$"),
        re.compile(r"^.+-sample\.cht$"),
        re.compile(r"^.+-aligned\.cht$"),
        re.compile(r"^.+-aligned-patchbox.*\.cht$"),
        re.compile(r"^.+-diag\.tif$", re.IGNORECASE),
    )

    @staticmethod
    def _migrate_move(src: Path, dst_dir: Path) -> None:
        """Move one file into ``dst_dir``; skip (with a warning) on conflict,
        never raise — a single stubborn file must not abort the migration."""
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / src.name
            if dst.exists():
                log.warning("migration: %s already exists, leaving %s in place",
                            dst, src)
                return
            shutil.move(str(src), str(dst))
            log.info("migration: %s -> %s/", src.name, dst_dir.name)
        except OSError as exc:
            log.warning("migration: could not move %s: %s", src, exc)

    def _migrate_v1_to_v2(self) -> None:
        """Tidy a flat (schema 1) project into the v2 sub-folder layout."""
        log.info("Migrating project %s to folder-layout v2", self._root)
        stem = self._root.name

        # every run folder — the manifest list plus a defensive glob, so a
        # run folder missing from a hand-edited manifest is still tidied
        run_dirs = {self.runs_root / rid for rid in self._manifest.runs}
        if self.runs_root.exists():
            run_dirs.update(d for d in self.runs_root.glob("run*") if d.is_dir())

        # The chart chain itself (<stem>.ext / <stem>_NN.ext) must never move,
        # even when the project NAME happens to end in a pattern tail (a
        # project called "X-sample" owns a chart "X-sample.cht" that would
        # otherwise match the cache pattern).
        #
        # NFC ON BOTH SIDES, for the same reason `rename` and `files_matching`
        # compare that way: `stem` is the FOLDER's spelling and `f.name` is the
        # FILE's, and a project whose chart came off a Mac OS Extended volume
        # has them spelled differently. Compared raw, `_protected` did not
        # recognise its own chart — so a project called "Müller-diag" had its
        # single page bitmap "Müller-diag.tif" swept into `cache/`, the one
        # folder the guide tells the user is always safe to delete. Measured;
        # tests/test_migration_protects_an_accented_chart.py.
        def _protected(name: str, chain_stem: str) -> bool:
            return re.fullmatch(
                rf"{re.escape(nfc(chain_stem))}(_\d+)?\.[\w.]+",
                nfc(name)) is not None

        stem_nfc = nfc(stem)
        for rd in sorted(run_dirs):
            if not rd.is_dir():
                continue
            for f in sorted(rd.iterdir()):
                if not f.is_file() or _protected(f.name, stem):
                    continue
                name_nfc = nfc(f.name)
                if any(rx.match(name_nfc) for rx in self._MIG_REPORTS):
                    self._migrate_move(f, rd / REPORTS_DIRNAME)
                elif name_nfc in (f"{stem_nfc}-colours.txt",
                                  f"{stem_nfc}-i1profiler.txt",
                                  f"{stem_nfc}-i1profiler.pxf"):
                    self._migrate_move(f, rd / EXPORTS_DIRNAME)
                elif any(rx.match(name_nfc) for rx in self._MIG_CACHE):
                    self._migrate_move(f, rd / CACHE_DIRNAME)

        cal_dir = self.calibration.dir
        cal_stem = nfc(self.calibration.stem)
        if cal_dir.is_dir():
            for f in sorted(cal_dir.iterdir()):
                if not f.is_file() or _protected(f.name, cal_stem):
                    continue
                name_nfc = nfc(f.name)
                if name_nfc in (f"{cal_stem}-colours.txt",
                                f"{cal_stem}-i1profiler.txt",
                                f"{cal_stem}-i1profiler.pxf"):
                    self._migrate_move(f, cal_dir / EXPORTS_DIRNAME)
                elif any(rx.match(name_nfc) for rx in self._MIG_CACHE):
                    self._migrate_move(f, cal_dir / CACHE_DIRNAME)

        self._manifest.schema_version = SCHEMA_VERSION
        self.save_manifest()
        # Regenerate the folder guide so it describes the layout the user now
        # actually has — the one deliberate overwrite of this file.
        self.write_readme()
        log.info("Migration to v2 complete: %s", self._root)

    def _migrate_v2_to_v3(self) -> None:
        """#130: fold a legacy single ``<stem>-verify.ti3`` (written flat in the
        run root by the old one-slot verification) into a dated
        ``verifications/<date>/`` folder, so verification history can accrue.
        The date comes from the file's modification time. Idempotent — runs
        already on the new layout have nothing to move; the profiling chain is
        never touched."""
        log.info("Migrating project %s verification files to layout v3", self._root)
        rids = list(self._manifest.runs) or [
            d.name for d in self.runs_root.glob("run*") if d.is_dir()]
        for rid in rids:
            run = Run(self, rid)
            legacy = run.dir / f"{run.stem}-verify.ti3"
            if not legacy.is_file():
                continue
            when = datetime.fromtimestamp(legacy.stat().st_mtime)
            v = run.new_verification(when)
            v.ensure_dir()
            self._migrate_move(legacy, v.dir)
            legacy_ti2 = run.dir / f"{run.stem}-verify.ti2"
            if legacy_ti2.is_file():
                self._migrate_move(legacy_ti2, run.verifications_dir)

    def save_manifest(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(asdict(self._manifest), indent=2), encoding="utf-8")

    def write_readme(self) -> None:
        """Write a user-facing "Where are my files.txt" at the project root.

        Written by ``create`` for new projects, backfilled by ``load`` if
        absent, and regenerated by the v1→v2 migration. The content is the
        same folder guide the Welcome/Help card shows (``ui.file_guide`` —
        one source, no drift), with the ``{name}`` placeholder resolved to
        the real project name. ``ui.file_guide`` is Qt-free (it imports only
        ``core.i18n``), so the lazy import is safe in headless contexts; the
        static template remains as a fallback should it ever fail.
        """
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            from ui.file_guide import file_guide_body
            body = file_guide_body().replace("{name}", self.target_name)
        except Exception:  # noqa: BLE001 — the guide must never block a project
            log.warning("file_guide unavailable — falling back to the static "
                        "README template", exc_info=True)
            body = _PROJECT_README_FALLBACK.format(name=self.target_name)
        self.readme_path.write_text(body, encoding="utf-8")

    def rename(self, new_stem: str) -> None:
        """Relabel an in-place project from its current stem to ``new_stem``.

        Chart artefacts carry the project name as their file stem (see
        ``Run.stem`` / ``Calibration.stem``), so simply moving the project
        folder is not enough — the files inside would keep the old stem while
        every ``Run``/``Calibration`` path property now resolves to the new one,
        silently breaking the project. This renames every ChromIQ-generated file
        whose stem is the old name (across ``runs/``, ``cal/`` and ``exports/``),
        updates ``project.json`` and rewrites the README.

        ``self._root`` must already be at the new location (the folder move is
        the caller's job) — this fixes up the contents and the manifest. A
        no-op when ``new_stem`` equals the current name.
        """
        old_stem = self._manifest.target_name
        if not old_stem or not new_stem or new_stem == old_stem:
            return

        # Only rename files shaped like a ChromIQ artefact for this stem:
        #   <stem>[-cal][-i1profiler|-colours][_NN].<ext...>
        # so a user's own "<stem>-notes.txt" is left untouched, and structural
        # files (project.json, meta.json, the README) never match. The bare
        # extensions (.ti1/.ti2/.cht/.cie/…) match via the trailing \.[\w.]+$.
        # -cal / -verify may combine with a sidecar marker: a calibration chart's
        # exports are "<stem>-cal-colours.txt" etc. (#127 — the old single-marker
        # pattern silently skipped those on rename). -verify covers the shared
        # verification chart (verifications/<stem>-verify.*) and the dated
        # verification measurements (verifications/<date>/<stem>-verify.ti3), so a
        # project rename carries them along too (#130, Hole 8).
        protected = {self.MANIFEST, self.README, "meta.json"}
        tail_re = re.compile(r"(-cal|-verify)?(-i1profiler|-colours)?(_\d+)?\.[\w.]+$")

        # NFC ON BOTH SIDES. `old_stem` comes from a name ChromIQ composed;
        # the names on disk may be decomposed, because a project restored from
        # a Mac OS Extended volume is spelled that way. Compared raw, a rename
        # skipped every accented artefact and left the whole chart behind under
        # the old name while the project moved on.
        old_stem_nfc = nfc(old_stem)
        for f in sorted(self._root.rglob("*")):
            if not f.is_file() or f.name in protected:
                continue
            name_nfc = nfc(f.name)
            if not name_nfc.startswith(old_stem_nfc):
                continue
            tail = name_nfc[len(old_stem_nfc):]
            if not tail_re.fullmatch(tail):
                continue
            dst = f.with_name(new_stem + tail)
            if dst.exists():
                # Something in the folder is already called what this file is
                # about to be called. ChromIQ never generates such a pair —
                # its own artefacts all carry the project stem — so this can
                # only come from a file put there or renamed by hand (Knut,
                # #130 2026-07-27).
                #
                # Skipping used to leave the REAL file behind under the old
                # name while the project silently used the stranger, and no
                # later rename ever repaired it. The stranger is moved aside
                # instead, so the rename can finish correctly and nothing is
                # lost.
                _move_aside_conflict(dst)
                if dst.exists():           # could not be moved: leave well alone
                    log.warning("Rename target already exists, skipping: %s", dst)
                    continue
            f.rename(dst)

        self._manifest.target_name = new_stem
        self.save_manifest()
        self.write_readme()
        log.info("Renamed project stem %s -> %s at %s", old_stem, new_stem, self._root)

    # ---- run access
    def run(self, run_id: str) -> Run:
        return Run(self, run_id)

    def current_run(self) -> Run:
        return Run(self, self._manifest.current_run)

    def all_runs(self) -> list[Run]:
        return [Run(self, rid) for rid in self._manifest.runs]

    def run(self, run_id: str) -> Run:
        """The Run with this id (not validated against the manifest — callers
        that need existence use :meth:`has_run`)."""
        return Run(self, run_id)

    def has_run(self, run_id: str) -> bool:
        return run_id in self._manifest.runs

    def set_current_run(self, run_id: str) -> None:
        if run_id not in self._manifest.runs:
            raise ValueError(f"Unknown run: {run_id}")
        self._manifest.current_run = run_id
        self.save_manifest()

    def set_runs(self, run_ids: "list[str]", *, current: str) -> None:
        """Replace the manifest's run list wholesale (#130, Knut 2026-07-28).

        Only :mod:`core.run_delete` uses this: after a run is deleted the
        survivors are renumbered, so ``runs[]`` is rebuilt rather than edited,
        and ``current_run`` moves to the run the bar will select. Deliberately
        does **not** validate ``current`` against the old list — the whole point
        is that the old list no longer describes the folders on disk.
        """
        self._manifest.runs = list(run_ids)
        self._manifest.current_run = current
        self.save_manifest()

    def new_run(self, *, preconditioning_from: Run | None = None) -> Run:
        """Create a new ``runN`` folder; if seeded with ``preconditioning_from``,
        copy the parent's ``profile.icc`` and ``measurement.ti3`` into the new
        run as ``preconditioning.icc`` / ``preconditioning.ti3``.

        Updates the manifest to make the new run current. Returns it.
        """
        run_id = f"run{self._next_run_index()}"
        new_run = Run(self, run_id)
        new_run.ensure_dir()

        meta = RunMeta.fresh(run_id)
        if preconditioning_from is not None:
            if not preconditioning_from.profile_icc.exists():
                raise FileNotFoundError(
                    f"Parent run {preconditioning_from.id} has no profile.icc"
                )
            if not preconditioning_from.measurement_ti3.exists():
                raise FileNotFoundError(
                    f"Parent run {preconditioning_from.id} has no measurement.ti3"
                )
            shutil.copy2(preconditioning_from.profile_icc, new_run.preconditioning_icc)
            shutil.copy2(preconditioning_from.measurement_ti3, new_run.preconditioning_ti3)
            meta.parent_run = preconditioning_from.id
            meta.preconditioning_source_run = preconditioning_from.id
            log.info(
                "New run %s seeded with preconditioning from %s",
                run_id, preconditioning_from.id,
            )

        new_run.save_meta(meta)
        self._manifest.runs.append(run_id)
        self._manifest.current_run = run_id
        self.save_manifest()
        return new_run

    #: What Duplicate copies, as ``(group key, [glob relative to the run])``.
    #: Order is the order the confirmation window lists them in.
    #:
    #: Knut's specification (#130, 2026-08-01), settled over three exchanges:
    #: the chart, the measurement and the profile built from it — everything
    #: that describes the work — plus the reports and export sidecars that
    #: describe *those*. ``{stem}`` is filled in with the run's own stem.
    DUPLICATE_GROUPS: tuple = (
        # `.print.json` travels WITH the chart, like `.channels.json` beside
        # it. It was in no group at all, so every duplication dropped it — and
        # the guard that asks "was this sheet converted when it was printed?"
        # then stops firing on the copy, silently, because its record is the
        # thing that went missing (found by a challenge round, 2026-09-01).
        ("chart", ("{stem}.ti1", "{stem}.ti2", "{stem}.cht", "{stem}.cie",
                   "{stem}.ps", "{stem}.pdf", "{stem}.channels.json",
                   "{stem}.strips.json", "{stem}.print.json",
                   "{stem}_*.tif", "{stem}.tif",
                   "chart/**/*")),
        ("measurement", ("{stem}.ti3", "reads/**/*")),
        ("profile", ("{stem}.icc", "{stem}.icm", "merged.ti3", "merged.icc",
                     "merged.icm", "calibrated.icc", "calibrated.icm",
                     "*.x3d.html", "x3dom.css", "x3dom.js")),
        ("refinement", ("preconditioning.ti3", "preconditioning.icc")),
        # Knut named these three exactly (2026-08-01): the quality report, the
        # re-measure list and the report JSONs belong with the measurement and
        # profile they describe. Anything else under reports/ does not.
        ("reports", ("reports/Quality_Check_*", "reports/Refine_Strips_*",
                     "reports/report_*.json")),
        ("exports", ("exports/**/*",)),
    )

    #: Never duplicated. ``meta.json`` is written fresh (a copy would make the
    #: new run claim to BE the old one); ``verifications/`` is excluded because
    #: use case 3 is precisely "carry on with a DIFFERENT verification chart";
    #: ``old/`` and ``cache/`` are history and scratch.
    DUPLICATE_NEVER: tuple = ("meta.json", "verifications", "old", "cache")

    def duplicate_run_plan(self, source: Run,
                           groups: "tuple[str, ...] | None" = None
                           ) -> "list[tuple[str, list[Path], int]]":
        """What :meth:`duplicate_run` would copy: ``[(group, files, bytes)]``.

        Built from what is actually on disk, so the confirmation window states
        the real thing rather than the specification's wish list (Knut,
        2026-08-01: *"it is ok to show what is being copied (based on what is
        actually found) in selected run"*). Groups with nothing in them are
        left out entirely — a row reading "Profile — 0 files" would suggest
        something is missing rather than simply absent.
        """
        plan = []
        for group, patterns in self.DUPLICATE_GROUPS:
            if groups is not None and group not in groups:
                continue
            found: list[Path] = []
            for pat in patterns:
                # THE STEM GOES IN ESCAPED. These are templates, so the folder
                # name lands inside a pattern whatever the call looks like — and
                # a project called `Chart [v2]` then copied its `.ti1` and none
                # of its pages, while one called `Chart*A` would have copied a
                # different project's. `{stem}` never appears in the
                # multi-segment patterns, so escaping is a no-op for those.
                filled = pat.format(stem=glob_escape(nfc(source.stem)))
                # `chart/**/*` and friends are multi-segment and carry no stem,
                # so `Path.glob` is still right for them; the stem patterns are
                # all single names and go through the accent-blind matcher, or
                # a duplicate of a project restored from an HFS+ volume copies
                # the chart's metadata and none of its pages.
                hits = (sorted(source.dir.glob(filled)) if "/" in filled
                        else files_matching(source.dir, filled))
                for p in hits:
                    if p.is_file() and p not in found:
                        found.append(p)
            if found:
                total = 0
                for p in found:
                    try:
                        total += p.stat().st_size
                    except OSError:      # vanished between glob and stat
                        pass
                plan.append((group, found, total))
        return plan

    def duplicate_run(self, source: Run,
                      groups: "tuple[str, ...] | None" = None) -> Run:
        """Copy *source*'s work into a brand-new run and make it current.

        Knut and Sebastian chose this over archiving a run's files whenever its
        chart was regenerated (#130, 2026-08-01, "course B"). His reasoning:
        moving everything into ``old/`` "basically means to start fresh, and
        that is better done by making a new run". So nothing is ever moved or
        overwritten — the source run is untouched, and the copy is somewhere
        new to carry on from.

        The new run gets a **fresh** ``meta.json`` recording ``duplicated_from``.
        Copying the old one would have given the new folder a manifest naming
        the old run — the exact kind of silent mismatch this model exists to
        prevent.
        """
        # *groups* limits WHAT is copied, to the names in `DUPLICATE_GROUPS`.
        # None keeps the whole run, which is what the Duplicate button means.
        # `("chart",)` is what an IMPORT needs (§I.9): the copy gets the chart
        # the incoming measurement belongs to and nothing else. Copying the
        # whole run there was driven on a real project and made a run that
        # contradicted itself — the copy carried a measurement, a profile,
        # `reads/`, `reports/` and a 153 KB export, every one of them orphaned
        # the moment the import wrote its own `.ti3` over the top.
        plan = self.duplicate_run_plan(source, groups)
        new_run = self.new_run()
        try:
            for _group, files, _size in plan:
                for src in files:
                    rel = src.relative_to(source.dir)
                    dst = new_run.dir / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
        except OSError:
            # A half-copied run is worse than none: it would look like a real
            # run and measure into a chart that is missing pages. Undone here
            # directly rather than through run_delete, whose delete also
            # RENUMBERS the remaining runs — this run never existed as far as
            # the user is concerned, so nothing else may move.
            log.exception("Duplicating %s failed — removing the partial run",
                          source.id)
            self._discard_run(new_run, just_created=True)
            raise
        meta = new_run.load_meta()
        src_meta = source.load_meta()
        meta.duplicated_from = source.id
        # EVERYTHING THE COPIED FILES ARE DESCRIBED BY COMES ACROSS WITH THEM.
        # `per_target_settings.md` §6.3: *"Duplicate run — the copy takes the
        # source's settings, since it takes the source's chart."* Carried by
        # exhaustive partition rather than an allow-list, so a NEW RunMeta field
        # cannot be silently forgotten: `DUPLICATE_META_CARRY | _FRESH` must
        # equal every field, and a test fails the day it does not.
        #
        # Safe in this direction because every carried value already describes a
        # file the copy has: a duplicate can only reach a state its source was
        # already in, never invent one. Each of the seven exceptions in _FRESH
        # names either an identity the copy must not claim or a file it does not
        # have.
        for _field in DUPLICATE_META_CARRY:
            setattr(meta, _field, getattr(src_meta, _field))
        # …and so does what the user wrote about it. The description is marked
        # as a copy so two runs cannot read as the same work, and the marker
        # goes at the START where it can be seen without scrolling the field —
        # Sebastian's point, and the specification's §5 T5.2. An empty
        # description stays empty: this feature never invents text, and
        # "(copy) " on its own would describe nothing. Knut, beta.148: *"The
        # new run 4 created gets the 'Run 4 Description' cleared."*
        meta.description = (f"(copy) {src_meta.description}"
                            if src_meta.description else "")
        new_run.save_meta(meta)
        log.info("Duplicated %s into %s (%d files)", source.id, new_run.id,
                 sum(len(f) for _g, f, _s in plan))
        return new_run

    def _discard_run(self, run: Run, *, just_created: bool = False) -> None:
        """Remove a run that was created but never became real.

        Only for undoing a failed :meth:`duplicate_run`. Deliberately NOT the
        Delete button's path: that one renumbers the runs after it, which is
        right when a user deletes a run they have seen and wrong for one that
        existed for a fraction of a second.
        """
        # ONLY IF IT REALLY NEVER BECAME REAL.
        #
        # This is an undo for a duplicate that failed, and it assumed the folder
        # it is about to remove was made moments ago and holds nothing. That is
        # not guaranteed: `new_run()` allocates from the MANIFEST, `ensure_dir()`
        # is `exist_ok=True`, and `Project.load` never reconciles the two — so a
        # manifest that has lost track of a run hands back a folder that already
        # holds somebody's `.ti3` and `.icc`, and this then destroyed it with no
        # archive and nothing in the Trash. Measured, 2026-08-31.
        #
        # A folder holding results is not "a run that never became real", so it
        # is kept and the manifest is left pointing at it. Loud, because the
        # duplicate still failed and somebody has to know why the tidy-up did
        # not happen.
        # RECURSIVELY, AND NOT ONLY THE RESULT SUFFIXES.
        # A first attempt filtered top-level files by suffix, which still
        # destroyed a printed but unmeasured chart (real ink and paper), the
        # `reads/`, `verifications/` and `reports/` folders, the run's OWN
        # `old/` archive, its `meta.json`, and an unconverted `.txt` — measured,
        # with nothing in the Trash. The honest question is not "does this look
        # like a result?" but "did somebody make anything in here?", and the
        # only safe answer scans the whole folder.
        #
        # `_next_run_index` now refuses to hand out an occupied folder at all,
        # so this should never fire. It stays because it is the last thing
        # between a bug of ours and somebody's work, and because that is exactly
        # what the previous version was assumed to be.
        # *just_created* is the ONE caller that made this folder moments ago and
        # knows every file in it is a copy it made itself: `duplicate_run`'s own
        # rollback. Without it the guard below fired on every failed duplicate —
        # the copied files looked exactly like somebody's work — so the undo
        # NEVER ran and a half-copied run was left in the manifest, which this
        # method's own docstring calls worse than none. The guard was written to
        # stop a folder that PRE-EXISTED being destroyed; it must not stop a
        # folder being cleaned up by the code that created it.
        _skip = {"meta.json"}
        _keep = [] if just_created else [
            q for q in run.dir.rglob("*")
            if q.is_file() and q.name not in _skip]
        if _keep:
            log.error("run %s was not discarded: it holds %d file(s) somebody "
                      "made (%s). The failed duplicate is left in place rather "
                      "than destroying them.", run.id, len(_keep),
                      ", ".join(p.name for p in _keep[:4]))
            return
        shutil.rmtree(run.dir, ignore_errors=True)
        if run.id in self._manifest.runs:
            self._manifest.runs.remove(run.id)
        if self._manifest.current_run == run.id:
            self._manifest.current_run = (self._manifest.runs[-1]
                                          if self._manifest.runs else "")
        self.save_manifest()

    def _next_run_index(self) -> int:
        """The next free run number — free ON DISK as well as in the manifest.

        THE MANIFEST IS NOT THE ONLY TRUTH. This counted only the runs the
        manifest lists, while `ensure_dir()` is `exist_ok=True` and
        `Project.load` never reconciles the two. So a manifest that has lost
        track of a run — a hand-edited file, a restore, a crash between the
        folder being made and the manifest being saved — handed the NEXT caller
        a folder that already held somebody's chart, measurement and profile.
        `duplicate_run` then copied straight over them: measured, with the
        operation reporting success and nothing in the Trash.

        Skipping numbers whose folder exists costs a directory listing once per
        new run, and no caller can then be handed occupied ground. A gap in the
        numbering is not a fault: run folders are named, not counted.
        """
        n = 0
        for rid in self._manifest.runs:
            m = re.match(r"run(\d+)$", rid)
            if m:
                n = max(n, int(m.group(1)))
        n += 1
        try:
            while (self.runs_root / f"run{n}").exists():
                log.warning("run%d exists on disk but not in the manifest — "
                            "skipping it rather than building on top of "
                            "somebody's work", n)
                n += 1
        except OSError:          # unreadable runs/ — the caller will fail louder
            pass
        return n

    # ---- exports
    def ensure_exports_dir(self) -> Path:
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        return self.exports_dir


# ---------------------------------------------------------------------------
# FileManager — thin wrapper holding target_name + settings, exposing a
# Project for the current working folder.
# ---------------------------------------------------------------------------

class FileManager:
    def __init__(self, settings: "AppSettings") -> None:
        self._settings = settings
        self._target_name: str = ""
        self._project: Project | None = None
        # Told whenever a project starts or stops being NAMED. The UI's
        # "is a project open?" state used to be refreshed off the Profile-run
        # bar's `changed` signal — a signal about the BAR, while the state it
        # reads lives here. Every route that named a project without moving the
        # bar therefore left the masthead stale, which is how Close Project
        # stayed greyed after Generate and after Open Chart File (#164).
        # A plain callback list, not a Qt signal: FileManager is not a QObject
        # and the test doubles that stand in for it are not either.
        self._named_state_listeners: list = []
        # #130 (Knut): projects may be organised in SUB-folders of the ChromIQ
        # folder. When a nested project is opened, this holds its actual root so
        # working_dir() resolves there instead of <ChromIQ>/<name>. Dropped by
        # set_target_name only when the name names a DIFFERENT project (a fresh
        # project always lives directly under the ChromIQ folder).
        self._project_root_override: "Path | None" = None

    # ---- target name
    @staticmethod
    def strip_workfile_ext(name: str) -> str:
        """Strip any trailing ChromIQ work-file extension(s) from a target name.

        Handles stacked extensions ("chart.icm.ti3" -> "chart") so a name
        pasted from an existing generated file can't poison a new session.
        Dots that are not a known extension (e.g. "Pro.1000") are preserved.
        """
        s = name.strip()
        while True:
            stem, dot, ext = s.rpartition(".")
            if dot and ("." + ext.lower()) in _WORKFILE_EXTS:
                s = stem.rstrip()
                continue
            return s

    @staticmethod
    def _sanitise(name: str) -> str:
        """The folder name ChromIQ makes from a typed (or on-disk) project name.

        AN ACCENT IS PART OF THE NAME. "Müller" is one character on a Mac
        keyboard (U+00FC) and two — "u" plus a combining diaeresis — when the
        same name arrives from a zip, a backup, a sync client or an HFS+
        volume. Composing to NFC first means one spelling reaches the folder
        name, the manifest, the chart stems and the name box, so the box can no
        longer read "Mu_ller" for a project called "Müller" on disk.

        NFC ALONE IS NOT ENOUGH. Thai, Devanagari, Hebrew niqqud and Arabic
        harakat have marks with no composed form to normalise to, so the
        character class has to admit combining marks as well — see
        ``_MARK_CATEGORIES`` above.

        A NAME ALREADY ON DISK IS A FIXED POINT, and that is why this function
        does NOT cap the length or refuse the Windows device names. It is also
        the function that RESOLVES an existing folder: ``open_project_at``
        cleans a folder's own name to derive the target name, and
        ``working_dir`` re-cleans it to decide whether the project is where it
        says it is — so a rule that shortened a long name or turned ``CON`` into
        something else would move somebody's existing project (Basti's ruling;
        ``tests/test_project_name_keeps_its_accents.py`` pins it name by name).

        Those two rules belong at the door instead, where the name is still
        somebody's typing rather than a folder that exists:
        ``ui.dialogs.name_prompt.validate`` caps at 120 UTF-8 bytes and refuses
        the device names, and every route that accepts a NEW name goes through
        it — see ``tests/test_a_new_project_name_goes_through_one_door.py``.
        """
        s = unicodedata.normalize("NFC", name).strip().replace(" ", "-")
        out: list[str] = []
        run_of_illegal = False
        for ch in s:
            if ch.isalnum() or ch in "_-.":
                out.append(ch)
                run_of_illegal = False
            elif (unicodedata.category(ch) in _MARK_CATEGORIES
                    and not _is_variation_selector(ch)
                    and out
                    and (out[-1].isalnum()
                         or unicodedata.category(out[-1]) in _MARK_CATEGORIES)):
                # A COMBINING MARK IS PART OF THE LETTER IT SITS ON — but only
                # when there is a letter under it. An orphan mark (nothing
                # before it, or a base that was itself illegal) is dropped with
                # the run it belongs to.
                out.append(ch)
                run_of_illegal = False
            elif not run_of_illegal:
                out.append("_")
                run_of_illegal = True
        s = _TRAIL.sub("", "".join(out))
        # A FOLDER WHOSE NAME IS A COMBINING MARK HAS NO VISIBLE NAME AT ALL,
        # and that stays impossible without a second guard: the FIRST mark in a
        # name has nothing under it, so it is dropped with the illegal run, and
        # every mark that survives therefore sits behind an alphanumeric base.
        # A marks-only name still cleans down to the same "session" an empty
        # one does. Asserted over 20,000 random names in
        # tests/test_project_name_keeps_its_accents.py.
        return s or "session"

    def set_target_name(self, name: str) -> None:
        _was = self._project_identity()
        cleaned = self.strip_workfile_ext(name)
        new_name = self._auto_name() if not cleaned.strip() else self._sanitise(cleaned)
        # #130 (Knut): a nested project keeps its real location as long as the
        # name still names THAT project. Re-applying the unchanged name is
        # routine — the Create Chart name field, every preset and Generate all
        # do it — and used to drop the override, so working_dir() silently
        # jumped to <ChromIQ>/<name> and the next project() call CREATED an
        # empty duplicate there. Everything the user did afterwards (importing a
        # chart, replacing a verification, adding a run) then landed in that
        # phantom project instead of the one on screen. A genuinely different
        # name means a different, fresh project, which always lives directly
        # under the ChromIQ folder — so the override is dropped in that case.
        ov = self._project_root_override
        if ov is None or self._sanitise(ov.name) != new_name:
            self._project_root_override = None
        self._target_name = new_name
        # Invalidate cached Project — new name = different folder.
        self._project = None
        log.debug("Target name set to: %s (root %s)", self._target_name,
                  self.working_dir())
        self._notify_named_state(_was)

    def start_new_project(self, name: str) -> None:
        """Point at a BRAND-NEW project called *name*, directly under the ChromIQ
        folder — even when a project of the same name is currently open from a
        sub-folder.

        ``set_target_name`` deliberately keeps a nested project's location when
        the name still refers to it (#130), so the "start a new project" flows
        say what they mean here instead of relying on that side effect.
        """
        self._project_root_override = None
        self.set_target_name(name)

    def close_project(self) -> None:
        """Forget the current project entirely, leaving this file manager in the
        state a freshly started ChromIQ has.

        #130 (Knut, 2026-07-29): after "Delete the whole project" the name was
        still set here, so the very next thing that asked for the project —
        switching to another tab was enough — CREATED the folder again, and the
        location line proudly showed a project the user had just deleted and
        never asked to have back.

        Clearing the name is what makes that impossible: with no name there is
        nothing for :meth:`project` to be called about, exactly as at launch.
        """
        _was = self._project_identity()
        self._target_name = ""
        self._project_root_override = None
        self._project = None
        log.info("Project closed — back to the state a fresh start has")
        self._notify_named_state(_was)

    def add_named_state_listener(self, callback) -> None:
        """Call *callback* whenever the project that is open CHANGES — including
        one project being swapped for another, not only opened or closed."""
        if callback not in self._named_state_listeners:
            self._named_state_listeners.append(callback)

    def _project_identity(self) -> "tuple[bool, str]":
        """What "which project is open" means, for change detection.

        The FOLDER, not the name: a project opened from a sub-folder has the
        same name as a different one at the top level, and swapping between them
        changes everything about where a build goes. Asking never creates
        anything — `working_dir()` is only consulted when something is named.
        """
        if not self.is_named():
            return (False, "")
        try:
            return (True, str(self.working_dir()))
        except OSError:
            return (True, self._target_name)

    def _notify_named_state(self, was) -> None:
        """Fire the listeners, but only on an actual change.

        WAS NAMED↔UNNAMED ONLY, AND THAT WAS TOO NARROW. `set_target_name` runs
        on every keystroke path, every preset and every Generate, so re-notifying
        on each would be churn — but a build that adopts a DIFFERENT project
        while one is already open changed nothing this could see, and the Create
        Chart hint that says "you already have a project with this name" went on
        showing after the app had opened exactly that project. Compare the folder
        instead: churn is still avoided, and a swap is no longer invisible.

        *was* is what :meth:`_project_identity` returned before the change. A
        bare ``bool`` is still accepted, because that is what this took for a
        year and a caller elsewhere may still pass one.
        """
        if isinstance(was, bool):
            was = (was, "" if not was else "?")
        if tuple(was) == self._project_identity():
            return
        for cb in list(self._named_state_listeners):
            try:
                cb()
            except Exception:      # noqa: BLE001 — a listener must never
                log.exception("project-change listener failed")   # break a rename

    def is_named(self) -> bool:
        """Whether a project has a NAME yet — without inventing one.

        Weaker than :meth:`has_project`, which also wants the manifest on disk.
        Use this where the question is "may I write into the project folder?"
        during the moments when a project is being created and its
        ``project.json`` does not exist yet. Like `has_project`, asking never
        creates anything — which is the whole point, since `get_target_name()`
        does (#164).
        """
        return bool(self._target_name) or self._project_root_override is not None

    def has_project(self) -> bool:
        """Whether a project is open at all — i.e. something is named AND its
        folder holds a manifest. Asking this never creates anything, which is
        what makes it safe to call from a UI refresh."""
        if not self._target_name and self._project_root_override is None:
            return False
        try:
            return (self.working_dir() / "project.json").exists()
        except OSError:
            return False

    def open_project_at(self, root: "Path") -> None:
        """Open a project at its ACTUAL folder *root*, which may be nested in a
        sub-folder of the ChromIQ folder (#130, Knut). working_dir() then
        resolves there rather than <ChromIQ>/<name>."""
        _was = self._project_identity()
        root = Path(root)
        self._target_name = self._sanitise(root.name)
        self._project_root_override = root
        self._project = None
        log.debug("Opened nested project at: %s", root)
        self._notify_named_state(_was)

    def project_root_override(self) -> "Path | None":
        return self._project_root_override

    def get_target_name(self) -> str:
        if not self._target_name:
            self._target_name = self._auto_name()
        return self._target_name

    @classmethod
    def default_target_name(
        cls,
        printer: str = "Printer",
        paper: str = "Paper",
        papertype: str = "Type",
        instrument: str = "Instr",
    ) -> str:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        parts = [printer, paper, papertype, instrument, ts]
        return "_".join(cls._sanitise(p) for p in parts)

    def _auto_name(self) -> str:
        return self.default_target_name()

    # ---- folder resolution
    def root_dir(self) -> Path:
        custom = self._settings.get("custom_output_path", "")
        return Path(custom) if custom else Path.home() / "ChromIQ"

    def working_dir(self) -> Path:
        # A nested project (opened from a sub-folder) resolves at its actual
        # location; every other project lives directly under the ChromIQ folder.
        ov = self._project_root_override
        if ov is not None and self._sanitise(ov.name) == self.get_target_name():
            return ov
        return self.root_dir() / self.get_target_name()

    def preview_project_root(self, raw_name: str) -> Path | None:
        """Compute the project root for a not-yet-set target name.

        Used by UI live-validation (e.g. tab_chart's "is there a calibration
        file for this project?" check). Returns None if the cleaned name is
        empty.
        """
        cleaned = self.strip_workfile_ext(raw_name)
        if not cleaned.strip():
            return None
        return self.root_dir() / self._sanitise(cleaned)

    def resolved_root_for_name(self, raw_name: str) -> "Path | None":
        """Where a build under *raw_name* would ACTUALLY land.

        :meth:`preview_project_root` answers ``<ChromIQ>/<name>`` and nothing
        else. That is right for a fresh name and wrong for the name of a NESTED
        project that is already open: :meth:`set_target_name` deliberately keeps
        such a project where it is, so the build goes to the sub-folder while
        the preview pointed at the top level. Asking the wrong one is not
        academic — a window offered to replace ``<ChromIQ>/test`` while the
        build wrote to ``<ChromIQ>/Group-A/test``, so one click emptied a
        project the build never touched.

        This mirrors ``set_target_name`` + ``working_dir()`` exactly, and
        creates nothing.
        """
        cleaned = self.strip_workfile_ext(raw_name)
        if not cleaned.strip():
            return None
        name = self._sanitise(cleaned)
        ov = self._project_root_override
        if ov is not None and self._sanitise(ov.name) == name:
            return ov
        return self.root_dir() / name

    def ensure_folder(self) -> Path:
        d = self.working_dir()
        d.mkdir(parents=True, exist_ok=True)
        log.debug("Working dir: %s", d)
        return d

    # ---- project access (the new API)
    def project(self) -> Project:
        """Return the Project for the current target.

        Creates ``project.json`` + ``runs/run1/`` on first call for a target.
        Subsequent calls return the cached project (invalidated by
        ``set_target_name``).
        """
        if self._project is None:
            root = self.working_dir()
            self._project = Project.create_or_load(root, self.get_target_name())
        return self._project

    def target_snapshot(self) -> tuple:
        """What is open right now, so a caller can put it back.

        Used where a question is asked AFTER the project has been switched — the
        question has to be about the right run, and its "no" has to leave the
        app where it found it.
        """
        return (self._target_name, self._project_root_override)

    def restore_target(self, snapshot: tuple) -> None:
        """Put back what :meth:`target_snapshot` recorded."""
        _was = self._project_identity()
        self._target_name, self._project_root_override = snapshot
        self._project = None
        log.info("target restored to %r", self._target_name or "(nothing open)")
        self._notify_named_state(_was)

    def forget_cached_project(self) -> None:
        """Drop the cached :class:`Project` so the next call re-reads the disk.

        The UI needs this after it has changed a project folder underneath the
        file manager (a Replace empties it), and was reaching into
        ``_project`` to do it.
        """
        self._project = None

    def rename_existing_project(self, old: "str | Path", new_name_raw: str) -> Path:
        """Move the project folder ``old_name`` to the sanitised ``new_name`` and
        fix every artefact stem + the manifest inside it.

        Used when the user changes the Output name after a first generate and
        chooses "rename". Makes the renamed project the current target. Returns
        the new root.

        Raises ``FileExistsError`` if a project already occupies the new name,
        and ``FileNotFoundError`` if ``old_name`` is not a project on disk.
        """
        # A NESTED PROJECT IS RENAMED WHERE IT LIVES. Both sides used to be
        # derived from `root_dir()`, so for a project opened from a sub-folder
        # this raised `FileNotFoundError` — and the one caller answers that by
        # "creating fresh instead", which leaves an empty project at the new
        # name and abandons the real one in its sub-folder. Measured.
        #
        # A PATH MAY BE PASSED, and the UI does. Resolving a NAME here while the
        # caller shows the user a folder it resolved differently is how the
        # window came to name one project and the delete to take another; the
        # caller now hands in the folder it displayed.
        old_root = (Path(old) if isinstance(old, Path)
                    else self.resolved_root_for_name(old))
        if old_root is None:
            raise ValueError("Empty target name")
        cleaned = self.strip_workfile_ext(new_name_raw)
        if not cleaned.strip():
            raise ValueError("Empty target name")
        # The NEW name goes beside the old project, not at the top level: a
        # rename must not also move a project out of the group it is filed in.
        new_root = old_root.parent / self._sanitise(cleaned)
        if new_root == old_root:
            return old_root
        if not (old_root / Project.MANIFEST).exists():
            raise FileNotFoundError(old_root)
        if new_root.exists():
            raise FileExistsError(new_root)

        _was = self._project_identity()
        shutil.move(str(old_root), str(new_root))
        proj = Project.load(new_root)
        proj.rename(new_root.name)
        self._target_name = new_root.name
        # Keep the override pointing at where the project now is, or a nested
        # one silently detaches the moment it is renamed.
        self._project_root_override = (
            new_root if new_root.parent != self.root_dir() else None)
        self._project = proj
        # A rename changes which folder is open and told nobody at all.
        self._notify_named_state(_was)
        return new_root

    def project_has_built_profile(self, name: str) -> bool:
        """True if a project ``name`` exists on disk and any run holds a built
        ICC profile (the deliverable). Used to block renaming a profile once it
        has been created — at that point the embedded ICC description is baked
        in, so the user copies it to a new name instead (#70, Knut).
        """
        # `resolved_root_for_name`, not `preview_project_root`: for a project
        # open from a sub-folder the latter answers `<ChromIQ>/<name>`, which
        # does not exist — so this returned False for a project with an ICC
        # sitting in it, and the "you cannot rename a built profile" guard
        # never fired. Measured.
        root = self.resolved_root_for_name(name)
        if root is None or not (root / Project.MANIFEST).exists():
            return False
        try:
            proj = Project.load(root)
        except Exception as exc:  # noqa: BLE001 — a corrupt manifest isn't fatal here
            log.warning("Could not inspect project '%s' for a built profile: %s",
                        name, exc)
            return False
        return any(r.built_profile_icc().exists() for r in proj.all_runs())

    def delete_project_folder(self, name: "str | Path") -> bool:
        """Move a ChromIQ project folder to the system Trash.

        NOT `shutil.rmtree`, which is what this used to be. It removes
        everything it can reach and raises only at the end, so one unwritable
        sub-folder left a project half destroyed — measured through the target
        bar's own Delete, ten of twenty-nine files gone with `project.json`
        among them. This path is reached from the rename chooser instead of the
        bar, which is why it was missed when the others were fixed.

        Returns whether the folder went. False means nothing was touched.

        Guarded so a stray/empty name can never remove something unexpected: the
        folder must be INSIDE :meth:`root_dir` and contain a ``project.json``.
        Anything else is refused with a warning.

        "Inside", not "directly under": a project opened from a sub-folder of
        the ChromIQ folder is a real project, and this refused to delete it with
        nothing but a log line — so the rename chooser's Delete branch appeared
        to do nothing at all. The safety this guard exists for is unchanged:
        the target must still be under the ChromIQ folder, must not BE it, and
        must carry a manifest.
        """
        root = self.root_dir()
        # A PATH MAY BE PASSED, and the UI does — so that the folder the window
        # named is the folder that goes. See `rename_existing_project`.
        target = (Path(name) if isinstance(name, Path)
                  else self.resolved_root_for_name(name))
        if target is None:
            log.warning("Refusing to delete an empty project name")
            return
        try:
            inside = (target != root
                      and root.resolve() in target.resolve().parents)
        except OSError:
            inside = False
        if not inside:
            log.warning("Refusing to delete unsafe path: %s", target)
            return
        if not (target / Project.MANIFEST).exists():
            log.warning("Refusing to delete non-project folder: %s", target)
            return
        from core.trash import move_to_trash
        res = move_to_trash(target)
        if not res.ok:
            log.warning("Could not move project folder %s to the Trash", target)
            return False
        log.info("Moved project folder %s to the Trash", target)
        return True

    def cwd_for_chart(self, *, cal_target: bool) -> Path:
        """Folder chart_creator must run targen/printtarg in.

        Calibration targets go to ``cal/`` (one calibration per project,
        shared across all runs). Normal chart generation goes to the
        current run's folder.
        """
        proj = self.project()
        return proj.calibration.ensure_dir() if cal_target else proj.current_run().ensure_dir()

    def chart_stem(self, *, cal_target: bool) -> str:
        """File stem chart_creator passes to targen/printtarg.

        Calibration targets resolve to ``<project>-cal``; profiling charts to
        the bare (sanitised) project name. printtarg prints this as the chart
        identifier on the page, so it must be descriptive (not the generic
        ``chart``/``calibration`` placeholders from the early redesign).
        """
        proj = self.project()
        return proj.calibration.stem if cal_target else proj.current_run().stem



# ---------------------------------------------------------------------------
# Looking at a project WITHOUT opening it (#: the typed-name gate, 2026-08-27)
# ---------------------------------------------------------------------------

def is_a_project(folder: "Path | None") -> bool:
    """True when *folder* is a ChromIQ project, and not merely a folder.

    ONE PLACE, BECAUSE BOTH LOADERS ANSWERED IT WITH `.exists()`. That is true
    of any folder at all, so the import door's collision line told a person, in
    red, that their plain folder of notes was "already a project" — about the
    folder whose NOT being one is the only reason that window opens (round 2,
    T1-D, driven 2026-09-02: `ROUND2/shots/repro-folder-win03.png`). The
    difference matters twice over: what is safe to say, and what "Replace it"
    is about to move aside.

    `is_file()` rather than `exists()`, because a `project.json` that is a
    directory is not a manifest either.
    """
    if folder is None:
        return False
    try:
        return (Path(folder) / Project.MANIFEST).is_file()
    except OSError:
        return False


def dir_holds(folder: "Path | None", path: "Path | None") -> bool:
    """True when *folder* is *path* or contains it, at any depth.

    The question every importer must ask before replacing a folder: "does the
    thing I am about to replace hold the file I am importing?" Both loaders
    asked it themselves, and both asked it wrong — comparing *folder* with the
    file's IMMEDIATE PARENT, so a measurement at `<work>/Canon/runs/run1/x.txt`
    did not match the name "Canon", and replacing that project destroyed the
    project, the profile and the file being imported. Measured: 8 files to 5,
    ending in FileNotFoundError.

    One copy, so the two loaders cannot drift again, and `same_dir` throughout
    because `==` and `.resolve()` both miss that APFS and Windows fold case and
    that a name typed in NFC never equals a folder created in NFD.
    """
    if folder is None or path is None:
        return False
    try:
        return same_dir(folder, path) or any(same_dir(folder, p)
                                             for p in Path(path).parents)
    except OSError:
        return False


def same_dir(a: "Path | None", b: "Path | None") -> bool:
    """True when *a* and *b* are the same directory on THIS filesystem.

    ``==`` on two Paths is a string comparison, and every interesting case
    defeats it: macOS and Windows treat ``REAL`` and ``real`` as one folder, a
    project opened through a symlink resolves elsewhere, and a name typed in NFC
    never equals a folder created in NFD. Each of those made ChromIQ call the
    project on screen "a different project" — and then offer to replace it.
    """
    if a is None or b is None:
        return False
    try:
        return Path(a).samefile(Path(b))
    except OSError:
        # samefile needs both to exist; before a project is created one does
        # not. Fall back to the strongest comparison that works on paths alone.
        return (os.path.normcase(os.path.realpath(a))
                == os.path.normcase(os.path.realpath(b)))


@dataclass(frozen=True)
class RunPeek:
    """One run of a project, read without opening it. See :func:`peek_project`."""

    id: str
    chart: bool = False
    measurement: bool = False
    profile: bool = False
    verifications: int = 0

    @property
    def holds_anything(self) -> bool:
        return bool(self.chart or self.measurement or self.profile
                    or self.verifications)

    @property
    def number(self) -> str:
        """"1" for ``run1`` — the number a message puts into "Run {n}"."""
        if self.id.startswith("run") and self.id[3:].isdigit():
            return self.id[3:]
        return self.id or "1"


@dataclass(frozen=True)
class ProjectPeek:
    """What a project holds, read without opening it.

    WHY NOT `Project.load`. Loading MIGRATES the folder in place — that is what
    brings a pre-#127 project up to the current layout — and this is asked while
    the user is merely *considering* a name. A question that rearranges someone
    else's project before they have answered it is not a question. So this reads
    ``project.json`` as plain JSON and looks at the run folder with `glob`, and
    it writes nothing, creates nothing and migrates nothing.

    ``exists`` False means "no project of that name" — every other field is then
    meaningless. ``run_id`` is the run a build would land in: the manifest's
    ``current_run``.
    """

    root: Path
    exists: bool = False
    run_id: str = ""
    chart: bool = False
    measurement: bool = False
    profile: bool = False
    verifications: int = 0
    calibration: bool = False
    #: EVERY run, oldest first — not only the current one. A project whose
    #: current run is empty can still hold four finished ones, and joining it
    #: unannounced is what Basti asked to be told about (2026-08-27).
    runs: tuple = ()

    @property
    def holds_anything(self) -> bool:
        """Whether there is anything in there a person would mind losing."""
        return bool(self.chart or self.measurement or self.profile
                    or self.verifications or self.calibration
                    or self.other_runs_hold)

    @property
    def other_runs_hold(self) -> bool:
        """Whether a run OTHER than the current one holds work."""
        return any(r.holds_anything for r in self.runs if r.id != self.run_id)

    @property
    def finished_runs(self) -> int:
        """How many runs hold anything at all."""
        return sum(1 for r in self.runs if r.holds_anything)

    @property
    def run_number(self) -> str:
        """"1" for ``run1`` — the number a message puts into "Run {n}".

        The LABEL is built by the caller, not here: this module has no `tr()`
        and an English "Run 1" baked in would have walked straight into twelve
        translated messages.
        """
        if self.run_id.startswith("run") and self.run_id[3:].isdigit():
            return self.run_id[3:]
        return self.run_id or "1"


def peek_project(root: "Path | None") -> ProjectPeek:
    """Read-only: what is in the project at *root*? Never creates or migrates."""
    if root is None:
        return ProjectPeek(Path(""), exists=False)
    root = Path(root)
    manifest = root / Project.MANIFEST
    try:
        if not manifest.is_file():
            return ProjectPeek(root, exists=False)
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # A manifest we cannot read still means a project folder is sitting
        # there, and the honest answer is "something is here" rather than
        # "nothing is here" — the latter would let a build walk into it.
        log.warning("could not read %s: %s", manifest, exc)
        return ProjectPeek(root, exists=True, chart=True)

    if not isinstance(data, dict):
        # Valid JSON, but a list or a number. `data.get` then raises
        # AttributeError out of a method whose whole promise is that asking is
        # safe — and takes Generate Chart down with it.
        log.warning("%s is not a project manifest (%s)", manifest, type(data).__name__)
        return ProjectPeek(root, exists=True, chart=True)

    schema = 1
    try:
        schema = int(data.get("schema_version", 1))
    except (TypeError, ValueError):
        pass
    # A MANIFEST IS A FILE PEOPLE CAN EDIT, AND PROJECTS GET MAILED AROUND.
    # These ids become path components below, so a `current_run` of "../.." or
    # "/etc" would walk this read straight out of the project — the same shape
    # as the journal traversal fixed in 4.1.3-beta.18. Anything that is not a
    # plain folder name is dropped.
    def _safe_id(value) -> str:
        v = str(value or "").strip()
        return v if v and v not in (".", "..") and "/" not in v and "\\" not in v else ""

    run_id = _safe_id(data.get("current_run"))
    runs = [r for r in (_safe_id(x) for x in (data.get("runs") or [])) if r]
    if not run_id:
        run_id = runs[0] if runs else "run1"

    # v1 kept everything flat in the project folder; v2+ put it in runs/runN/.
    # A CALIBRATION IS WORK TOO. It lives in the project's own `cal/`, shared
    # by every run, and a project that holds only a calibration used to read as
    # empty here — so no window appeared and a build could replace it in
    # silence. Looked for before the run, because it does not belong to one.
    cal_dir = root / "cal"
    calibration = False
    if cal_dir.is_dir():
        calibration = any(cal_dir.glob("*.cal")) or any(cal_dir.glob("*.ti3"))

    # EVERY run on disk, not only the ones the manifest lists — a folder the
    # manifest has lost still holds somebody's work.
    #
    # AND `runs/` IS RIGHT FOR SCHEMA 1 TOO. This used to look for a v1
    # project's files flat in the project folder, on the assumption that
    # per-run folders arrived with #127. They did not:
    # `tests/test_legacy_migration.py` says so in as many words — v1 HAD
    # `runs/`, it was the `reports/`, `exports/` and `cache/` sub-folders
    # inside each run that did not exist, and that is all `_migrate_v1_to_v2`
    # moves. The consequence of getting it wrong was total: every project made
    # before #127 read as EMPTY, so no window appeared and the project was
    # adopted in silence — which is Knut's original report, unfixed for every
    # 3.13-era project.
    runs_root = root / "runs"
    ids = list(runs)
    if runs_root.is_dir():
        try:
            for d in sorted(runs_root.glob("run*")):
                if d.is_dir() and d.name not in ids:
                    ids.append(d.name)
        except OSError:
            pass

    def _peek_run(rid: str) -> "RunPeek | None":
        run_dir = runs_root / rid
        if not run_dir.is_dir():
            return None

        def _any(*patterns: str, skip: "tuple[str, ...]" = ()) -> bool:
            for pat in patterns:
                for f in run_dir.glob(pat):
                    if f.name not in skip:
                        return True
            return False

        # `preconditioning.*` is a COPY seeded from the parent run, not this
        # run's own work, so it must not make an untouched run look finished.
        vdir = run_dir / VERIFICATIONS_DIRNAME
        n_ver = 0
        if vdir.is_dir():
            try:
                n_ver = sum(1 for d in vdir.iterdir()
                            if d.is_dir() and _VERIFY_ID_RE.match(d.name))
            except OSError:
                n_ver = 0
        return RunPeek(
            rid,
            chart=_any("*.ti1", "*.ti2"),
            measurement=_any("*.ti3", skip=("preconditioning.ti3",)),
            profile=_any("*.icc", "*.icm", skip=("preconditioning.icc",)),
            verifications=n_ver,
        )

    peeked = tuple(r for r in (_peek_run(i) for i in ids) if r is not None)
    current = next((r for r in peeked if r.id == run_id), None)
    if current is None:
        return ProjectPeek(root, exists=True, run_id=run_id,
                           calibration=calibration, runs=peeked)

    return ProjectPeek(root, exists=True, run_id=run_id, chart=current.chart,
                       measurement=current.measurement, profile=current.profile,
                       verifications=current.verifications,
                       calibration=calibration, runs=peeked)
