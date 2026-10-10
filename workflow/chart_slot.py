"""What "the chart this was measured with" means for a run and for a dated
verification (#130, Knut 2026-07-26/27).

Both levels keep the same promise — *a copy of the chart, taken when the
measurement started, so an old result never stops describing something you
still have* — but they differ in three ways, and only three:

============  ===================================  =========================
              Profiling run                        Dated verification
============  ===================================  =========================
live chart    ``runs/runN/``                       ``runs/runN/verifications/``
copy kept in  ``runs/runN/chart/``                 ``…/<date>/chart/``
which files   a **named list** of chart files      everything at that root
============  ===================================  =========================

That last row is the one that matters. A verification folder holds nothing but
the chart, so "everything except the page images" is safe there. A run's folder
also holds the measurement, the profile, the PostScript and ``meta.json`` — and
the copy is taken *before* the measurement exists, so a ``.ti3`` or ``.icc``
found there could only be a leftover from a previous read, never part of the
chart this run is about to be measured with (Knut's reasoning). Hence the named
list.

A :class:`ChartSlot` carries those three differences so that snapshotting,
comparing and restoring can be written once.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.file_manager import (CHART_SNAPSHOT_DIRNAME, Calibration, Run,
                               Verification)
from workflow.measurement_report import CONTROL_STRIP_SIDECAR

_IMAGE_SUFFIXES = (".tif", ".tiff")
_RECIPE_SUFFIX = ".channels.json"

#: The chart files a profiling run keeps a copy of. A named list rather than
#: "everything except images": see the module docstring. ``.cie`` is not on it:
#: it is derived from a measurement (Knut, D8).
#:
#: NOR IS ``.cht`` (Knut, #182 5958921500, 4.3.3-beta.3): *"Why is the .cht
#: file backed up into chart/ folder? The cht file is only created at the end
#: of a completed measurement, so it should never actually be backed up to
#: chart/ folder (which happens at the start of a measurement)."* A run's
#: ``<stem>.cht`` (``<stem>_NN.cht`` on a multi-page chart) is written only by
#: the scanner-recognition target (``workflow/scanin_target.py``) from the
#: run's ``.ti3``; Create Chart keeps its printtarg ``-s`` geometry inside
#: ``.channels.json``, never as a file. Restore Used Chart decides about a
#: run's ``.cht`` on its own: :meth:`ChartSlot.scanner_cht_files` and
#: :func:`workflow.verify_chart_snapshot.restore_cht_plan`. A ``.cht`` already
#: in an older snapshot stays on disk and is ignored.
#:
#: ``.control-strip.json`` is on the list because a declaration is tied to the
#: CHART, not to the run (Knut, 2026-09-19): *"The control strip declaration is
#: tied to the chart it is made for, not the run. If the declaration exists,
#: and measurement is started, that file shall also be backed up to chart/
#: folder (like other chart files), and if the Restore Used Chart button is
#: pressed, the controls strip declaration shall also be restored with the
#: other chart files."* A verification chart's declaration already travelled,
#: because that slot copies everything at its root; a profiling chart's did
#: not, and a profiling chart can carry one — the Measurement Report reads a
#: sidecar beside whatever chart a measurement is paired with, and its own help
#: text tells the user to write one. Without this entry a restore put chart X
#: back under the declaration of chart Y, which is the one thing "tied to the
#: chart" forbids. The suffix is read from the report rather than spelled again
#: here, for the reason :func:`workflow.control_strip.declaration_path` gives.
PROFILING_CHART_SUFFIXES = (
    ".ti1", ".ti2", ".channels.json", ".strips.json",
    CONTROL_STRIP_SIDECAR,
)

#: Files that belong to the chart but do not carry the chart's stem. ``meta.json``
#: holds the patch-set editor's design (``editor_recipe``) and the printtarg
#: knobs the chart was saved with, so a chart restored without it comes back
#: without the settings it was made with (Knut, #130 2026-07-27: "this file
#: should also be backed up to the chart/ folders … Restoring the chart files
#: should then also copy that meta.json file").
CHART_SIDE_FILES = ("meta.json",)

#: The print record, ``<stem>.print.json`` (``workflow/verification_print.py::
#: print_record_path``). It says how the sheet was PRINTED: when, which way,
#: through which profile. It travels with the chart, so a dated verification
#: keeps the record of the sheet it measured, but it never says WHICH chart
#: that is. Printing the same chart again rewrites it with a new
#: ``printed_at``, and counting it as chart made Knut's verification say
#: "Stored chart differs" for a chart nobody had touched (4.3.3, run5).
PRINT_RECORD_SUFFIX = ".print.json"


def defines_the_chart(path: Path) -> bool:
    """Whether *path*'s content decides WHICH chart this is.

    False for the files that travel with a chart without describing it: the
    settings ``meta.json`` (:data:`CHART_SIDE_FILES`) and the print record
    (:data:`PRINT_RECORD_SUFFIX`). Every "is it the same chart?" comparison
    asks this one question, so the warning before a measurement and the
    Restore Used Chart button cannot disagree about it.
    """
    name = Path(path).name
    return name not in CHART_SIDE_FILES and \
        not name.lower().endswith(PRINT_RECORD_SUFFIX)


def _is_image(p: Path) -> bool:
    return p.suffix.lower() in _IMAGE_SUFFIXES


def has_layout_recipe(files) -> bool:
    """Whether *files* carry the recipe the page images can be rebuilt from."""
    return any(p.name.endswith(_RECIPE_SUFFIX) for p in files)


@dataclass(frozen=True)
class ChartSlot:
    """One place a chart lives, and where its copy is kept."""
    live_dir: Path
    snapshot_dir: Path
    stem: str
    #: None → every file at the root counts as chart (the verification rule);
    #: otherwise only files whose name ends with one of these.
    suffixes: "tuple[str, ...] | None"

    # ---- the live chart ---------------------------------------------------
    def live_files(self) -> "list[Path]":
        """The chart as it is now. Folders are never included, so the dated
        verification runs, ``old/`` and ``reports/`` are safe."""
        if not self.live_dir.exists():
            return []
        # Dot-files are the operating system's, not the chart's — macOS leaves
        # `.DS_Store` in any folder opened in Finder and `._name` shadow files
        # in anything unzipped. The stored side already skips them; without the
        # same rule here the two sides disagree about what the chart contains
        # (#130, 2026-08-01).
        files = sorted(p for p in self.live_dir.iterdir()
                       if p.is_file() and not p.name.startswith("."))
        if self.suffixes is None:
            # The verification rule: every file at the root is chart, except
            # the reader's working measurement ``<stem>.ti3`` (see
            # `verify_chart_snapshot.live_chart_files`, the same exclusion).
            # Its yellow memory ``<stem>.confirmed.json`` likewise (#182 K4).
            from workflow.confirmed_patches import SUFFIX as _MEMORY
            measurement = {f"{self.stem}.ti3".lower(),
                           f"{self.stem}{_MEMORY}".lower()}
            return [p for p in files if p.name.lower() not in measurement]
        return [p for p in files if p.name.endswith(self.suffixes)
                or _is_image(p)]

    @property
    def holds_measurement_cht(self) -> bool:
        """Whether this slot's folder can hold a ``.cht`` made from the
        measurement: a profiling run's and the calibration's (both
        suffix-filtered), never the verification chart's folder, where every
        file is chart and Knut's ``.cht`` rule does not apply ("not applicable
        for a verification run", #182 5958921500)."""
        return self.suffixes is not None

    def scanner_cht_files(self) -> "list[Path]":
        """The scanner-recognition ``.cht`` page(s) made from this slot's
        measurement: ``<stem>.cht``, or ``<stem>_NN.cht`` per page. Nothing
        else that ends in ``.cht`` (a user's own file, scanin's working copies)
        is matched. Empty for a verification slot."""
        if not self.holds_measurement_cht or not self.live_dir.is_dir():
            return []
        pat = re.compile(re.escape(self.stem) + r"(?:_\d{2,})?\.cht")
        return sorted(p for p in self.live_dir.iterdir()
                      if p.is_file() and pat.fullmatch(p.name))

    def side_files(self) -> "list[Path]":
        """Files that belong WITH the chart but are not the chart.

        Kept out of :meth:`live_files` deliberately: they must not decide
        whether a run has a chart at all, and a change in one of them is not a
        change of chart — otherwise editing the printtarg knobs would raise the
        "this is a different chart" warning.
        """
        return [self.live_dir / name for name in CHART_SIDE_FILES
                if (self.live_dir / name).is_file()]

    def files_to_copy(self) -> "list[Path]":
        """What a copy takes: the chart files, but not the page images — unless
        there is no layout recipe to redraw them from, in which case the images
        must travel too or a restore would leave nothing printable."""
        files = self.live_files()
        if not files:
            return []
        if has_layout_recipe(files):
            files = [p for p in files if not _is_image(p)]
        # …and whatever travels with a chart, but only when there IS one.
        return files + self.side_files()


def slot_for_run(run: Run) -> ChartSlot:
    """The profiling chart of *run*, copied into ``runs/runN/chart/``."""
    return ChartSlot(live_dir=run.dir,
                     snapshot_dir=run.dir / CHART_SNAPSHOT_DIRNAME,
                     stem=run.stem,
                     suffixes=PROFILING_CHART_SUFFIXES)


def slot_for_verification(verification: Verification) -> ChartSlot:
    """The shared verification chart, copied into ``<date>/chart/``."""
    run = verification.run
    return ChartSlot(live_dir=run.verifications_dir,
                     snapshot_dir=verification.dir / CHART_SNAPSHOT_DIRNAME,
                     stem=run.verify_stem,
                     suffixes=None)


def slot_for_calibration(calibration: Calibration) -> ChartSlot:
    """The project's calibration chart, copied into ``cal/chart/`` (#137).

    A calibration chart is the one chart whose loss could not be undone: it
    cannot be reloaded, and rebuilding it starts the print-and-measure round
    again from nothing. Giving it the same slot every other chart has means
    Restore Used Chart works for it with no new snapshot logic at all — the
    copying, the "already identical" check and the restore are the ones runs and
    verifications already use.

    The suffix filter is the profiling one: a calibration folder also holds the
    measurement (``.ti3``) and the calibration itself (``.cal``), and neither is
    part of *the chart* — restoring a chart must never put back a stale
    measurement over a fresh one.
    """
    return ChartSlot(live_dir=calibration.dir,
                     snapshot_dir=calibration.snapshot_dir,
                     stem=calibration.stem,
                     suffixes=PROFILING_CHART_SUFFIXES)


def slot_for(target) -> ChartSlot:
    """The slot for whichever of the three *target* is.

    Matched by explicit type rather than by duck-typing, so a new kind of target
    fails loudly here instead of quietly being treated as a run.
    """
    if isinstance(target, Calibration):
        return slot_for_calibration(target)
    if isinstance(target, Verification):
        return slot_for_verification(target)
    return slot_for_run(target)
