"""Runs profcheck and parses its output for quality assessment."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import QThread, pyqtSignal

from core.i18n import tr
from core.logger import get_logger
from core.strip_utils import letter_to_idx

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

_SUMMARY_RE   = re.compile(r"max\.\s*=\s*([\d.]+).*?avg\.\s*=\s*([\d.]+)", re.IGNORECASE)
_PATCH_RE     = re.compile(r"^\s*\[([\d.]+)\]\s+\d+\s+@\s+([A-Za-z0-9]+):", re.MULTILINE)
_STRIP_LETTER = re.compile(r"^([A-Za-z]+)")


# Structured error / warning patterns for profcheck (Argyll 3.5.0
# spectro/profile/profcheck.c). Many error()s are per-field "Input file
# doesn't contain field X" variants — we collapse them into a single
# pattern below.
_PROFCHECK_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L307 / L353 — wrong illuminant for the measurement reference type
    (re.compile(r"(?:Target|CIE) illuminant '([^']+)' is wrong measurement type"),
     "illum_type",
     "The illuminant '{0}' isn't compatible with the reference data in the "
     ".ti3 file. Change or clear the illuminant in the Check & Refine "
     "options."),
    # L433
    (re.compile(r"CGATS file read error on '([^']+)'\s*:\s*(.+)$"),
     "ti3_read",
     "The measurement file ({0}) could not be read.\n\nArgyll reported: {1}"),
    # L501
    (re.compile(r"Input file '([^']+)' doesn't contain keyword COLOR_REPS"),
     "ti3_no_color_reps",
     "The file '{0}' isn't a measured .ti3 file — it's missing the "
     "COLOR_REPS keyword. Did you pick a chart definition (.ti1/.ti2) "
     "instead?"),
    # L578
    (re.compile(r"Device input file '([^']+)' has unhandled color representation '([^']+)'"),
     "unhandled_colorrep",
     "profcheck doesn't know how to handle the colour representation '{1}' "
     "in '{0}'. Use a chart in RGB, CMYK or another standard colour space."),
    # L583
    (re.compile(r"Input file '([^']+)' has no sets of data"),
     "ti3_empty",
     "The measurement file '{0}' contains no data sets. Re-measure the chart."),
    # L608-655 — all "Input file 'X' doesn't contain field Y" / "field Y is wrong type"
    (re.compile(r"Input file(?: '([^']+)')? (?:doesn't contain field|field) (\S+)(?: is wrong type)?"),
     "field_missing",
     "The measurement file is missing or has the wrong type for a required "
     "field ({1}). Re-measure the chart, or check the .ti3 wasn't edited."),
]

_PROFCHECK_WARNING_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L465
    (re.compile(r"-i illuminant ignored for emissive reference type"),
     "illum_ignored_emissive",
     "Illuminant setting was ignored — this measurement was made in emissive mode."),
    # L468
    (re.compile(r"-f FWA compensation ignored for emissive reference type"),
     "fwa_ignored_emissive",
     "FWA compensation was ignored — this measurement was made in emissive mode."),
]

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


def _ti3_device_channels(ti3_path: Path) -> int:
    """Number of device channels from the .ti3 COLOR_REP (0 if unreadable)."""
    try:
        head = Path(ti3_path).read_text(errors="replace")[:8000]
    except OSError:
        return 0
    m = re.search(r'^COLOR_REP\s+"([^"]+)"', head, re.M)
    return len(m.group(1).split("_")[0]) if m else 0


class _NChannelWorker(QThread):
    """Runs the Python +N accuracy check off the UI thread, streaming
    profcheck-format lines."""
    line = pyqtSignal(str)
    done = pyqtSignal(int)

    def __init__(self, params: "ProfcheckParams", bin_dir: Path, parent=None):
        super().__init__(parent)
        self._params = params
        self._bin_dir = bin_dir

    def run(self) -> None:                       # noqa: D102 — QThread worker
        from workflow.profcheck_nchannel import (NChannelCheckError,
                                                 run_check)
        p = self._params
        try:
            lines = run_check(
                p.ti3_path, p.icc_path, bin_dir=self._bin_dir,
                de_formula=p.de_formula, intent=p.intent, sort=p.sort,
                verbosity=p.verbosity, illum=p.illum, observer=p.observer,
                fwa=p.fwa_enabled, fwa_illum=p.fwa_illum)
        except NChannelCheckError as exc:
            self.line.emit(tr("[ERROR] {msg}").format(msg=exc))
            self.done.emit(1)
            return
        for ln in lines:
            self.line.emit(ln)
        self.done.emit(0)


class ProfcheckRunner:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner   = runner
        self._last_log = ""
        self._matched_errors: list[tuple[str, str]] = []
        self._matched_warnings: list[tuple[str, str]] = []
        self._nchan_worker: _NChannelWorker | None = None

    def run(
        self,
        params: ProfcheckParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        self._last_log = ""
        self._matched_errors = []
        self._matched_warnings = []

        def _accumulate(line: str) -> None:
            self._last_log += line + "\n"
            self._scan_line(line)
            on_line(line)

        # >4-ink profiles: stock profcheck refuses the colourspace, so run the
        # Python N-channel check (icclu forward lookup + ΔE) — same output
        # format, so all downstream parsing / grading / refine-strip flagging
        # works unchanged. Spectral options (FWA / custom illuminant / observer)
        # aren't recomputed; the file's CIE values are used.
        if _ti3_device_channels(params.ti3_path) > 4:
            bin_dir = Path(self._runner._settings.get(
                "argyll_bin_path", "/Applications/Argyll/bin"))
            log.info("profcheck (N-channel): %s vs %s",
                     params.ti3_path.name, params.icc_path.name)
            self._nchan_worker = w = _NChannelWorker(params, bin_dir)
            w.line.connect(_accumulate)

            def _finished(code: int) -> None:
                self._nchan_worker = None
                on_finish(code)

            w.done.connect(_finished)
            w.finished.connect(w.deleteLater)
            w.start()
            return

        args = self._build_args(params)
        cwd  = params.ti3_path.parent
        log.info("profcheck: %s  [cwd=%s]", " ".join(args), cwd)
        self._runner.run(
            "profcheck",
            args,
            cwd,
            on_line=_accumulate,
            on_finish=on_finish,
        )

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _PROFCHECK_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                groups = tuple(g or "" for g in m.groups())
                self._matched_errors.append((key, fmt.format(*groups)))
        for pattern, key, fmt in _PROFCHECK_WARNING_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_warnings.append((key, fmt.format(*m.groups())))

    def primary_failure(self) -> tuple[str, str] | None:
        return self._matched_errors[0] if self._matched_errors else None

    def captured_warnings(self) -> list[tuple[str, str]]:
        return list(self._matched_warnings)

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


def grade_display(grade: str) -> str:
    """Translated display form of a quality grade (grades stay English
    internally — they are dict keys and comparison values)."""
    return {
        "Excellent": tr("Excellent"),
        "Good": tr("Good"),
        "Acceptable": tr("Acceptable"),
        "Needs Work": tr("Needs Work"),
        "Unknown": tr("Unknown"),
    }.get(grade, grade)


def quality_explanation(avg_de: float | None, peak_de: float | None) -> str:
    if avg_de is None:
        return tr(
            "profcheck did not return summary statistics. "
            "Make sure the .ti3 and .icc files match and that "
            "per-patch verbosity is enabled."
        )

    avg_rank  = _grade_from_value(avg_de, _AVG_THRESHOLDS)
    peak_rank = _grade_from_value(peak_de, _PEAK_THRESHOLDS) if peak_de is not None else 0
    limiting  = "peak" if peak_rank > avg_rank else "avg"

    lines: list[str] = []
    lines.append(
        tr("Average \u0394E: {avg:.2f}  |  Peak \u0394E: {peak:.2f}").format(avg=avg_de, peak=peak_de)
        if peak_de is not None else tr("Average \u0394E: {avg:.2f}").format(avg=avg_de)
    )

    overall_rank = max(avg_rank, peak_rank)
    if overall_rank == 0:
        lines.append(tr(
            "Your profile is excellent. Both average and peak colour errors are very low — "
            "typical for a well-measured printer/paper combination."
        ))
    elif overall_rank == 1:
        if limiting == "peak":
            lines.append(tr(
                "Your profile is good overall (average \u0394E {avg:.2f}), but one or more "
                "individual patches have higher errors (peak \u0394E {peak:.2f}). "
                "Most colours will reproduce accurately; the outlier patches may cause "
                "subtle shifts in specific colours."
            ).format(avg=avg_de, peak=peak_de))
        else:
            lines.append(tr(
                "Your profile is good. Most colours will reproduce accurately. "
                "Small errors may be visible only in critical colour-matching situations."
            ))
    elif overall_rank == 2:
        if limiting == "peak":
            lines.append(tr(
                "Your profile's average accuracy is reasonable (\u0394E {avg:.2f}), but "
                "there are individual patches with significant errors (peak \u0394E {peak:.2f}). "
                "These outliers will likely cause noticeable colour shifts in specific areas. "
                "Re-measuring the flagged strips can help."
            ).format(avg=avg_de, peak=peak_de))
        else:
            lines.append(tr(
                "Your profile is acceptable but has room for improvement. "
                "Some colours may look slightly off in prints. "
                "Re-measuring the strips with the highest error can help."
            ))
    else:
        if limiting == "peak":
            avg_label = grade_display(_GRADE_LABELS[avg_rank]).lower()
            lines.append(tr(
                "Your average colour accuracy is {avg_label} (\u0394E {avg:.2f}), but "
                "one or more individual patches have very high errors (peak \u0394E {peak:.2f}). "
                "These outliers will cause clearly visible colour shifts in specific areas. "
                "Re-measuring the worst strips — or re-printing and measuring "
                "a fresh chart — is strongly recommended."
            ).format(avg_label=avg_label, avg=avg_de, peak=peak_de))
        else:
            lines.append(tr(
                "Your profile needs work. Colour accuracy is low and prints "
                "will likely show noticeable colour shifts. "
                "Re-measuring the worst strips — or re-printing and measuring "
                "a fresh chart — is strongly recommended."
            ))

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


def write_named_report(
    folder: Path,
    prefix: str,
    stem: str,
    summary_text: str,
    raw_log: str,
    log_title: str = "Full output",
) -> Path:
    """Write ``<prefix>_<n>_<stem>.txt`` into *folder*, incrementing *n* until
    the name is free — so repeated runs keep a little history instead of
    overwriting each other. Shared by the quality check and the two Verify
    tools (Knut, beta.5: verification runs should leave a report in
    ``reports/`` just like quality checks do)."""
    n = 1
    while True:
        candidate = folder / f"{prefix}_{n}_{stem}.txt"
        if not candidate.exists():
            target = candidate
            break
        n += 1

    target.write_text(
        f"{summary_text}\n\n{'─' * 60}\n\n{log_title}:\n\n{raw_log}",
        encoding="utf-8",
    )
    log.info("Report written to %s", target)
    return target


def write_quality_report(
    folder: Path,
    stem: str,
    summary_text: str,
    raw_log: str,
) -> Path:
    """Write Quality_Check_<n>_<stem>.txt, incrementing n until the name is free."""
    return write_named_report(folder, "Quality_Check", stem, summary_text,
                              raw_log, log_title="Full profcheck output")


def write_refine_strips(
    folder: Path,
    stem: str,
    strips: list[tuple[str, float]],
) -> Path:
    """Write Refine_Strips_<n>_<stem>.txt, incrementing n until the name is free.

    NUMBERED, LIKE THE QUALITY REPORT BESIDE IT. This wrote one fixed name and
    overwrote it in place, so a second check destroyed the first one's strip
    list without a word — against the project's own absolute rule that nothing
    the user created is deleted, only archived. A challenge round proved it by
    hand-editing the file and watching the next check take it away
    (2026-09-01). `write_named_report` already solves this for
    `Quality_Check`, and the two belong together: they describe the same run.

    An existing UNNUMBERED file from an older version is left exactly where it
    is. It is the user's, and renaming it would be the same fault wearing a
    politer face.
    """
    n = 1
    while (folder / f"Refine_Strips_{n}_{stem}.txt").exists():
        n += 1
    target = folder / f"Refine_Strips_{n}_{stem}.txt"
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
