"""Orchestrates ArgyllCMS `average` to combine repeated measurements of one chart.

Reading the same printed chart several times and averaging the .ti3 sets reduces
instrument noise. `average` averages every measured field (XYZ + all spectral
bands) while leaving the device RGB values and labels untouched — see
docs/dev_averaging.md for the analysis. With only two reads, mean and median are
identical (Argyll falls back to the mean for <3 values); the median (`-e`) option
only diverges at 3+ reads.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)


# Errors `average` can produce. Line refs target Argyll 3.5.0 spectro/average.c.
_AVERAGE_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # :642 — field count differs between reads
    (re.compile(r"File '[^']+' has \d+ fields, file '[^']+ has \d+"),
     "field_count_mismatch",
     "The measurement files don't have the same set of fields, so they can't be "
     "averaged. Make sure every read used the same chart and instrument."),
    # :646 — a field name/type differs between reads
    (re.compile(r"field no\. \d+ named '[^']+' doesn't match"),
     "field_mismatch",
     "The measurement files have different fields, so they can't be averaged. "
     "Make sure every read used the same chart and instrument."),
    # :661 — patch count differs between reads
    (re.compile(r"File '[^']+' has \d+ sets, file '[^']+ has \d+"),
     "set_count_mismatch",
     "The reads contain different numbers of patches, so they can't be averaged. "
     "Re-read the same chart for every pass."),
    # :680 / :691 — a device (or PCS) value differs → not the same chart
    (re.compile(r"set \d+ has field '[^']+' value that differs"),
     "value_mismatch",
     "The reads don't describe the same chart (a patch's device value differs). "
     "Averaging only works across repeated reads of one identical chart."),
    # :202 — a file couldn't be read
    (re.compile(r"CGATS file '([^']+)' read error\s*:\s*(.+)$"),
     "read_error",
     "A measurement file could not be read ({0}): {1}"),
]


@dataclass
class AverageParams:
    inputs: list[Path]          # two or more .ti3 reads of the same chart
    output: Path                # averaged .ti3 to write
    method: str = "mean"        # "mean" | "median" (median == argyll -e)


def _rel_to(target: Path, base: Path) -> str:
    """``target`` addressed from ``base``, falling back to the absolute path when
    the two live on different Windows drives (os.path.relpath raises there)."""
    try:
        return os.path.relpath(target, base)
    except ValueError:
        return str(target)


class AverageRunner:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner = runner
        self._out: Path | None = None
        self._matched_errors: list[tuple[str, str]] = []

    def run(
        self,
        params: AverageParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[Path | None], None],
    ) -> None:
        """Run `average`; call on_finish(output) on success, on_finish(None) on failure."""
        self._matched_errors = []
        self._out = params.output

        if len(params.inputs) < 2:
            log.error("average needs at least two inputs, got %d", len(params.inputs))
            on_finish(None)
            return

        from workflow.cal_repair import repair_all
        repair_all(params.inputs)
        cwd = params.output.parent
        args = self._build_args(params)
        log.info("average args: %s  [cwd=%s]", args, cwd)

        def _scan(line: str) -> None:
            self._scan_line(line)
            on_line(line)

        self._runner.run(
            "average",
            args,
            cwd,
            on_line=_scan,
            on_finish=lambda code: self._done(code, on_finish),
        )

    def primary_failure(self) -> tuple[str, str] | None:
        return self._matched_errors[0] if self._matched_errors else None

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _AVERAGE_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_errors.append((key, fmt.format(*m.groups())))

    def _done(self, code: int, on_finish: Callable[[Path | None], None]) -> None:
        out = self._out
        success = (code == 0) and out is not None and out.exists()
        if success:
            log.info("average succeeded → %s", out)
            on_finish(out)
        else:
            log.error("average failed (code %d)", code)
            on_finish(None)

    def _build_args(self, p: AverageParams) -> list[str]:
        # `average` runs with cwd == the output's folder (see run()) and writes
        # the output there, so the output is addressed by bare name. The inputs
        # may sit in a *sub-folder* of that cwd, though: under the per-run layout
        # the reads live in <run>/reads/ while the averaged result is the run-dir
        # chart.ti3 — so each input is expressed relative to the cwd rather than
        # by bare name, or `average` can't open them. -X/-L geometric median is
        # deliberately not offered: it only rewrites the XYZ 3-vector, which the
        # profiler recomputes from the (mean-averaged) spectral data, so it would
        # be a no-op here (see docs/dev_averaging.md).
        cwd = p.output.parent
        args: list[str] = ["-v"]
        if p.method == "median":
            args.append("-e")
        args += [_rel_to(f, cwd) for f in p.inputs]
        args.append(p.output.name)
        return args
