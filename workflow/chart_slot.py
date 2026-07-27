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

from dataclasses import dataclass
from pathlib import Path

from core.file_manager import CHART_SNAPSHOT_DIRNAME, Run, Verification

_IMAGE_SUFFIXES = (".tif", ".tiff")
_RECIPE_SUFFIX = ".channels.json"

#: The chart files a profiling run keeps a copy of. A named list rather than
#: "everything except images": see the module docstring. ``.cht`` belongs to the
#: chart (it describes where the patches are); ``.cie`` does not — it is derived
#: from a measurement (Knut, D8).
PROFILING_CHART_SUFFIXES = (
    ".ti1", ".ti2", ".cht", ".channels.json", ".strips.json",
)


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
        files = sorted(p for p in self.live_dir.iterdir() if p.is_file())
        if self.suffixes is None:
            return files
        return [p for p in files if p.name.endswith(self.suffixes)
                or _is_image(p)]

    def files_to_copy(self) -> "list[Path]":
        """What a copy takes: the chart files, but not the page images — unless
        there is no layout recipe to redraw them from, in which case the images
        must travel too or a restore would leave nothing printable."""
        files = self.live_files()
        if not files:
            return []
        if has_layout_recipe(files):
            return [p for p in files if not _is_image(p)]
        return files


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


def slot_for(target) -> ChartSlot:
    """The slot for whichever of the two *target* is."""
    return (slot_for_verification(target) if isinstance(target, Verification)
            else slot_for_run(target))
