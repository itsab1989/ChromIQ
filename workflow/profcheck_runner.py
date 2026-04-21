"""Runs profcheck and parses its output for quality assessment."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.logger import get_logger
from core.strip_utils import letter_to_idx

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

_SUMMARY_RE   = re.compile(r"max\.\s*=\s*([\d.]+).*?avg\.\s*=\s*([\d.]+)", re.IGNORECASE)
_PATCH_RE     = re.compile(r"^\s*\[([\d.]+)\]\s+\d+\s+@\s+([A-Za-z0-9]+):", re.MULTILINE)
_STRIP_LETTER = re.compile(r"^([A-Za-z]+)")

REFINE_DE_THRESHOLD          = 2.0   # flag a strip if any single patch exceeds this ΔE
REFINE_START_OVER_RATIO      = 0.5   # recommend start-over if patch ratio exceeds this
REFINE_START_OVER_STRIP_RATIO = 0.75  # recommend start-over if strip ratio exceeds this



@dataclass
class ProfcheckParams:
    ti3_path: Path
    icc_path: Path
    de_formula: str = ""          # "" = CIE76,  "-c" = CIE94,  "-k" = CIEDE2000
    intent: str = "a"              # "a" = absolute (default),  "r" = relative
    sort: bool = True
    verbosity: str = "2"          # "1" = summary only,  "2" = per-patch
    fwa_enabled: bool = False
    fwa_illum: str = "D50"
    illum: str = "D50"
    observer: str = "1931_2"
    prune_enabled: bool = False
    prune_value: float = 3.0
    x3dom: bool = False


@dataclass
class ProfcheckResult:
    avg_de: float | None = None
    peak_de: float | None = None
    patch_errors: list[tuple[str, float]] = field(default_factory=list)
    raw_log: str = ""


class ProfcheckRunner:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner   = runner
        self._last_log = ""

    def run(
        self,
        params: ProfcheckParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        args = self._build_args(params)
        cwd  = params.ti3_path.parent
        log.info("profcheck: %s  [cwd=%s]", " ".join(args), cwd)
        self._last_log = ""

        def _accumulate(line: str) -> None:
            self._last_log += line + "\n"
            on_line(line)

        self._runner.run(
            "profcheck",
            args,
            cwd,
            on_line=_accumulate,
            on_finish=on_finish,
        )

    @property
    def last_log(self) -> str:
        return self._last_log

    def parse_results(self, log_text: str = "") -> ProfcheckResult:
        text = log_text or self._last_log
        result = ProfcheckResult(raw_log=text)

        m = _SUMMARY_RE.search(text)
        if m:
            result.peak_de = float(m.group(1))
            result.avg_de  = float(m.group(2))

        for m in _PATCH_RE.finditer(text):
            de_val   = float(m.group(1))
            patch_id = m.group(2)
            result.patch_errors.append((patch_id, de_val))

        return result

    # ------------------------------------------------------------------

    def _build_args(self, p: ProfcheckParams) -> list[str]:
        args: list[str] = [f"-v{p.verbosity}"]
        if p.de_formula:
            args.append(p.de_formula)
        if p.intent and p.intent != "a":
            args += ["-I", p.intent]
        if p.sort:
            args.append("-s")
        if p.fwa_enabled:
            args.append(f"-f{p.fwa_illum}" if p.fwa_illum else "-f")
        if p.illum and p.illum != "D50":
            args += ["-i", p.illum]
        if p.observer and p.observer != "1931_2":
            args += ["-o", p.observer]
        if p.prune_enabled:
            args += ["-P", f"{p.prune_value:.2f}"]
        if p.x3dom:
            args.append("-w")
        args.append(str(p.ti3_path))
        args.append(str(p.icc_path))
        return args


# ---------------------------------------------------------------------------
# Quality assessment helpers
# ---------------------------------------------------------------------------

def _grade_from_value(value: float, thresholds: tuple[float, float, float]) -> int:
    """Return 0=Excellent, 1=Good, 2=Acceptable, 3=Needs Work."""
    t1, t2, t3 = thresholds
    if value < t1:
        return 0
    if value < t2:
        return 1
    if value < t3:
        return 2
    return 3


_GRADE_LABELS    = ("Excellent", "Good", "Acceptable", "Needs Work")
_AVG_THRESHOLDS  = (1.0, 2.0, 4.0)
_PEAK_THRESHOLDS = (3.0, 5.0, 8.0)


def quality_grade(avg_de: float | None, peak_de: float | None) -> str:
    if avg_de is None:
        return "Unknown"
    avg_rank  = _grade_from_value(avg_de, _AVG_THRESHOLDS)
    peak_rank = _grade_from_value(peak_de, _PEAK_THRESHOLDS) if peak_de is not None else 0
    return _GRADE_LABELS[max(avg_rank, peak_rank)]


def quality_explanation(avg_de: float | None, peak_de: float | None) -> str:
    if avg_de is None:
        return (
            "profcheck did not return summary statistics. "
            "Make sure the .ti3 and .icc files match and that "
            "per-patch verbosity is enabled."
        )

    avg_rank  = _grade_from_value(avg_de, _AVG_THRESHOLDS)
    peak_rank = _grade_from_value(peak_de, _PEAK_THRESHOLDS) if peak_de is not None else 0
    limiting  = "peak" if peak_rank > avg_rank else "avg"

    lines: list[str] = []
    lines.append(
        f"Average \u0394E: {avg_de:.2f}  |  Peak \u0394E: {peak_de:.2f}"
        if peak_de is not None else f"Average \u0394E: {avg_de:.2f}"
    )

    overall_rank = max(avg_rank, peak_rank)
    if overall_rank == 0:
        lines.append(
            "Your profile is excellent. Both average and peak colour errors are very low — "
            "typical for a well-measured printer/paper combination."
        )
    elif overall_rank == 1:
        if limiting == "peak":
            lines.append(
                f"Your profile is good overall (average \u0394E {avg_de:.2f}), but one or more "
                f"individual patches have higher errors (peak \u0394E {peak_de:.2f}). "
                "Most colours will reproduce accurately; the outlier patches may cause "
                "subtle shifts in specific colours."
            )
        else:
            lines.append(
                "Your profile is good. Most colours will reproduce accurately. "
                "Small errors may be visible only in critical colour-matching situations."
            )
    elif overall_rank == 2:
        if limiting == "peak":
            lines.append(
                f"Your profile's average accuracy is reasonable (\u0394E {avg_de:.2f}), but "
                f"there are individual patches with significant errors (peak \u0394E {peak_de:.2f}). "
                "These outliers will likely cause noticeable colour shifts in specific areas. "
                "Re-measuring the flagged strips can help."
            )
        else:
            lines.append(
                "Your profile is acceptable but has room for improvement. "
                "Some colours may look slightly off in prints. "
                "Re-measuring the strips with the highest error can help."
            )
    else:
        if limiting == "peak":
            avg_label = _GRADE_LABELS[avg_rank].lower()
            lines.append(
                f"Your average colour accuracy is {avg_label} (\u0394E {avg_de:.2f}), but "
                f"one or more individual patches have very high errors (peak \u0394E {peak_de:.2f}). "
                "These outliers will cause clearly visible colour shifts in specific areas. "
                "Re-measuring the worst strips — or re-printing and measuring "
                "a fresh chart — is strongly recommended."
            )
        else:
            lines.append(
                "Your profile needs work. Colour accuracy is low and prints "
                "will likely show noticeable colour shifts. "
                "Re-measuring the worst strips — or re-printing and measuring "
                "a fresh chart — is strongly recommended."
            )

    return "\n\n".join(lines)

def group_by_strip(
    patch_errors: list[tuple[str, float]],
) -> list[tuple[str, float]]:
    """Return (strip_letter, avg_dE) sorted worst-first. Used for display / reports."""
    strip_totals: dict[str, list[float]] = {}
    for patch_id, de in patch_errors:
        m = _STRIP_LETTER.match(patch_id)
        letter = m.group(1).upper() if m else patch_id.upper()
        strip_totals.setdefault(letter, []).append(de)
    averages = [
        (letter, sum(vals) / len(vals))
        for letter, vals in strip_totals.items()
    ]
    averages.sort(key=lambda x: x[1], reverse=True)
    return averages


def strips_to_refine(
    patch_errors: list[tuple[str, float]],
    threshold: float = REFINE_DE_THRESHOLD,
) -> list[tuple[str, float]]:
    """Return (strip_letter, max_dE) for strips where any patch exceeds threshold,
    sorted in chartread order (A, B … Z, AA, AB …) for forward-only navigation."""
    strip_max: dict[str, float] = {}
    for patch_id, de in patch_errors:
        m = _STRIP_LETTER.match(patch_id)
        letter = m.group(1).upper() if m else patch_id.upper()
        if de > threshold:
            strip_max[letter] = max(strip_max.get(letter, 0.0), de)
    return sorted(strip_max.items(), key=lambda x: letter_to_idx(x[0]))


def total_strip_count(patch_errors: list[tuple[str, float]]) -> int:
    """Count the total number of distinct strips present in the measurement data."""
    strips: set[str] = set()
    for patch_id, _ in patch_errors:
        m = _STRIP_LETTER.match(patch_id)
        strips.add(m.group(1).upper() if m else patch_id.upper())
    return len(strips)


def write_quality_report(
    folder: Path,
    stem: str,
    summary_text: str,
    raw_log: str,
) -> Path:
    """Write Quality_Check_<stem>.txt, numbering if it already exists."""
    base = folder / f"Quality_Check_{stem}.txt"
    if not base.exists():
        target = base
    else:
        n = 2
        while True:
            candidate = folder / f"Quality_Check_{n}_{stem}.txt"
            if not candidate.exists():
                target = candidate
                break
            n += 1

    target.write_text(
        f"{summary_text}\n\n{'─' * 60}\n\nFull profcheck output:\n\n{raw_log}",
        encoding="utf-8",
    )
    log.info("Quality report written to %s", target)
    return target


def write_refine_strips(
    folder: Path,
    stem: str,
    strips: list[tuple[str, float]],
) -> Path:
    """Write Refine_Strips_<stem>.txt with machine-readable strip list."""
    target = folder / f"Refine_Strips_{stem}.txt"
    lines = [
        "# CHROMIQ_REFINE_STRIPS_V1",
        "# Strip\tMaxDE",
    ]
    for letter, avg_de in strips:
        lines.append(f"{letter}\t{avg_de:.2f}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Refine strips file written to %s", target)
    return target


def parse_refine_strips(path: Path) -> list[str]:
    """Read a Refine_Strips file and return strip letters in order."""
    strips: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        strips.append(line.split()[0].upper())
    return strips
