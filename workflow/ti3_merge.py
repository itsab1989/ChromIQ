"""Merge pre-conditioning measurement data into a freshly measured .ti3.

Part of the optional "ChromIQ-style refinement process" (gated by the
``chromiq_refinement`` setting). When the user opts in, the patches measured
for an earlier pre-conditioning profile — copied into the refined run as
``preconditioning.ti3`` by ``Project.new_run`` — are merged into the chart
just measured (``chart.ti3``). The combined file (``merged.ti3``) is handed to
colprof, which then builds the profile from more data points.

The concatenation itself is done by ArgyllCMS's own ``average -m`` tool, which
appends the patch rows of two field-compatible measurement files (taking all
header/keyword data from the first input). Before invoking it we verify the two
files share a COLOR_REP and DATA_FORMAT, so an incompatible pairing (e.g. a
different instrument, or spectral vs. tristimulus data) yields a clear message
instead of a terse tool error.

The merged file feeds colprof only; Check & Refine always works from the clean
fresh chart.ti3, so the merged file needs no ChromIQ-specific markup. Validated
against ArgyllCMS 3.5.0: ``average -m`` output is ingested in full by colprof
and read back by profcheck.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary
from core.text_io import read_text

log = get_logger(__name__)


class Ti3MergeError(Exception):
    """Raised when two measurement files cannot be safely merged.

    Carries a human-readable ``message`` suitable for showing in a dialog.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class _Parsed:
    color_rep: str
    data_format: list[str]
    n_sets: int


def _parse(path: Path) -> _Parsed:
    """Read just enough of a CGATS .ti3 to validate compatibility before merging."""
    try:
        text = read_text(path)
    except OSError as exc:
        raise Ti3MergeError(f"Could not read '{path.name}': {exc}") from exc

    lines = text.splitlines()
    color_rep = ""
    data_format: list[str] = []

    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("COLOR_REP"):
            parts = s.split(None, 1)
            if len(parts) == 2:
                color_rep = parts[1].strip().strip('"')
        elif s == "BEGIN_DATA_FORMAT" and i + 1 < len(lines):
            data_format = lines[i + 1].split()

    def _find(token: str) -> int:
        for i, ln in enumerate(lines):
            if ln.strip() == token:
                return i
        return -1

    b, e = _find("BEGIN_DATA"), _find("END_DATA")
    if b == -1 or e == -1 or e <= b:
        raise Ti3MergeError(
            f"'{path.name}' is not a valid measurement file "
            "(missing BEGIN_DATA / END_DATA)."
        )
    if not color_rep or not data_format:
        raise Ti3MergeError(
            f"'{path.name}' is missing its COLOR_REP or DATA_FORMAT header."
        )

    n_sets = sum(1 for ln in lines[b + 1:e] if ln.strip())
    if n_sets == 0:
        raise Ti3MergeError(f"'{path.name}' contains no measurement data.")

    return _Parsed(color_rep, data_format, n_sets)


def _resolve_average(bin_dir: Path | str | None) -> str:
    """Return the path to the ArgyllCMS ``average`` binary (falling back to PATH)."""
    name = argyll_binary("average")
    if bin_dir:
        candidate = Path(bin_dir) / name
        if candidate.exists():
            return str(candidate)
    return name


def merge_preconditioning(
    fresh_ti3: Path,
    pre_data: Path,
    out_ti3: Path,
    bin_dir: Path | str | None = None,
) -> int:
    """Merge ``pre_data`` patches into ``fresh_ti3``; write the result to ``out_ti3``.

    ``pre_data`` holds CGATS .ti3 content (typically the run's
    ``preconditioning.ti3``). The merge is performed by ``average -m`` (located
    under ``bin_dir`` if given, otherwise via PATH). Returns the total number of
    sets in the merged file.

    Raises ``Ti3MergeError`` when the two files use a different COLOR_REP or
    DATA_FORMAT — colprof needs a single, consistent column layout — or when the
    ``average`` tool fails.
    """
    fresh = _parse(fresh_ti3)
    pre = _parse(pre_data)

    if fresh.color_rep != pre.color_rep:
        raise Ti3MergeError(
            "The pre-conditioning measurements use a different colour "
            f"representation ({pre.color_rep}) than the chart just measured "
            f"({fresh.color_rep}). They were likely made with a different "
            "instrument or colour space and cannot be combined.\n\n"
            "The profile will be built from the new measurements only."
        )
    if fresh.data_format != pre.data_format:
        raise Ti3MergeError(
            "The pre-conditioning measurements have a different data layout "
            "(e.g. spectral vs. non-spectral, or a different field set) than "
            "the chart just measured, so they cannot be combined.\n\n"
            "The profile will be built from the new measurements only."
        )

    average = _resolve_average(bin_dir)
    cmd = [average, "-m", str(fresh_ti3), str(pre_data), str(out_ti3)]
    try:
        proc = run_text(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise Ti3MergeError(
            f"Could not run ArgyllCMS 'average' to merge the data: {exc}\n\n"
            "The profile will be built from the new measurements only."
        ) from exc

    if proc.returncode != 0 or not out_ti3.exists():
        detail = (proc.stderr or proc.stdout or "").strip()
        raise Ti3MergeError(
            "ArgyllCMS 'average' could not merge the measurement files"
            + (f":\n{detail}" if detail else ".")
            + "\n\nThe profile will be built from the new measurements only."
        )

    total = fresh.n_sets + pre.n_sets
    log.info(
        "Merged measurements via 'average -m': %d fresh + %d pre-conditioning "
        "= %d sets -> %s",
        fresh.n_sets, pre.n_sets, total, out_ti3.name,
    )
    return total


def merge_measurements(
    inputs: list[Path],
    out_ti3: Path,
    bin_dir: Path | str | None = None,
) -> int:
    """Concatenate the patches of ``inputs`` into ``out_ti3`` via ``average -m``.

    Generalises :func:`merge_preconditioning` to any number of measurement
    files (two or more). The first input is the primary: ``average -m`` takes
    its header/keyword data and appends every other input's patch rows.

    Every input must share the primary's COLOR_REP and DATA_FORMAT — colprof
    needs one consistent column layout — otherwise a ``Ti3MergeError`` naming
    the offending file is raised. Returns the total number of sets written.
    """
    if len(inputs) < 2:
        raise Ti3MergeError("Merging needs at least two measurement files.")

    primary = _parse(inputs[0])
    total = primary.n_sets
    for extra_path in inputs[1:]:
        extra = _parse(extra_path)
        if extra.color_rep != primary.color_rep:
            raise Ti3MergeError(
                f"'{extra_path.name}' uses a different colour representation "
                f"({extra.color_rep}) than the primary file "
                f"'{inputs[0].name}' ({primary.color_rep}). They were likely "
                "made with a different instrument or colour space and cannot "
                "be combined."
            )
        if extra.data_format != primary.data_format:
            raise Ti3MergeError(
                f"'{extra_path.name}' has a different data layout (e.g. spectral "
                "vs. non-spectral, or a different field set) than the primary "
                f"file '{inputs[0].name}', so they cannot be combined."
            )
        total += extra.n_sets

    average = _resolve_average(bin_dir)
    cmd = [average, "-m", *(str(p) for p in inputs), str(out_ti3)]
    try:
        proc = run_text(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise Ti3MergeError(
            f"Could not run ArgyllCMS 'average' to merge the data: {exc}"
        ) from exc

    if proc.returncode != 0 or not out_ti3.exists():
        detail = (proc.stderr or proc.stdout or "").strip()
        raise Ti3MergeError(
            "ArgyllCMS 'average' could not merge the measurement files"
            + (f":\n{detail}" if detail else ".")
        )

    log.info(
        "Merged %d measurement files via 'average -m' = %d sets -> %s",
        len(inputs), total, out_ti3.name,
    )
    return total
