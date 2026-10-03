"""Orchestrates printcal to create a printer calibration file (.cal)."""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings

log = get_logger(__name__)


# Errors / warnings that printcal can produce. Line refs target
# Argyll 3.5.0 spectro/profile/printcal.c.
_PRINTCAL_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L918 — caller forgot a mode flag
    (re.compile(r"One of -i, -r -e or -I must be set"),
     "no_mode",
     "No printcal mode was selected. Pick Initial / Re-calibrate / Verify / "
     "Imitation in the Calibration & Profiling tab."),
    # L942 — input .ti3 unreadable
    (re.compile(r"CGATS file read error\s*:\s*(.+)$"),
     "ti3_read",
     "The measurement file (.ti3) could not be read.\n\nArgyll reported: {0}"),
    # L978 — wrong file (.ti1 instead of .ti3 etc.)
    (re.compile(r"Input file doesn't contain keyword COLOR_REPS"),
     "ti3_no_color_reps",
     "The file you selected isn't a measured .ti3 file — it's missing the "
     "COLOR_REPS keyword. Did you accidentally pick a chart definition (.ti1/"
     ".ti2) instead?"),
    # L986/L994/L1000 — colour space mismatch / unsupported
    (re.compile(r"COLOR_REP '([^']+)' invalid(?: \(([^)]+)\))?"),
     "color_rep_invalid",
     "The colour space '{0}' in the measurement file isn't valid for "
     "printcal{1}. Use an RGB or CMYK chart."),
    # L1023 — re-calibrate against missing prev .cal
    (re.compile(r"No cal target '([^']+)' found for re-calibrate"),
     "no_prev_cal",
     "Re-calibrate / verify mode needs a previous calibration file, but "
     "'{0}' couldn't be found. Pick an existing .cal file to base the new "
     "calibration on."),
    # L1032 — prev .cal unreadable
    (re.compile(r"Reading cal target '([^']+)' failed"),
     "prev_cal_read",
     "The previous calibration file '{0}' could not be read. It may be "
     "corrupt or in an older format."),
    # L1035 — colorspace mismatch between chart and prev cal
    (re.compile(r"Target '([^']+)' colorspace '([^']+)' doesn't match '([^']+)' colorspace '([^']+)'"),
     "colorspace_mismatch",
     "Your chart's colour space ('{3}') doesn't match the previous "
     "calibration's colour space ('{1}'). Use a chart in the same colour "
     "space as the calibration you're re-using."),
    # L1056 / L1062 — missing field in prev cal
    (re.compile(r"Can't find field (\S+) in '([^']+)' table 3"),
     "cal_field_missing",
     "The previous calibration file is missing the '{0}' field. The file "
     "may be from an incompatible Argyll version."),
    # L1204 / L1237 — missing field in input
    (re.compile(r"(?:Can't find|Input file doesn't contain) field (\S+)"),
     "input_field_missing",
     "The measurement file is missing the '{0}' field. Re-measure the chart "
     "or check that the .ti3 wasn't edited."),
    # L1388 — no white patch found (the calibration needs at least one)
    (re.compile(r"Can't find even one white patch in '([^']+)'"),
     "no_white_patch",
     "No white patch was found in your measurements. printcal needs a "
     "100% white patch to anchor the calibration — re-measure the chart "
     "with the white patches included."),
    # L2808 / L2847 — permission to write
    (re.compile(r"(?:Couldn't open '([^']+)' for writing|Write error to file '([^']+)':\s*(.+)$)"),
     "write_failed",
     "Could not write the calibration file. Check that the folder is "
     "writable and not in use by another application."),
]

_PRINTCAL_WARNING_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # L1003 — chart probably wrong type
    (re.compile(r"COLOR_REP '([^']+)' is probably not suitable for print calibration"),
     "wrong_color_rep",
     "Note: the chart's colour space ('{0}') is unusual for print calibration "
     "— printcal will continue but the result may not be optimal."),
    # L1010 — re-calibrate ignores target overrides
    (re.compile(r"Command line calibration target paramers ignored on re-calibrate"),
     "targets_ignored",
     "Per-channel target overrides are ignored in re-calibrate / verify / "
     "imitate modes — they only apply to a fresh Initial calibration."),
    # L1787 — channel max clipped to monotonicity limit
    (re.compile(r"Chan (\d+), intended device max ([\d.]+) is beyond monotonicity limit of ([\d.]+)"),
     "max_clipped",
     "Channel {0}: requested max ({1}) is beyond the printer's monotonicity "
     "limit ({2}). printcal clipped it automatically."),
]


@dataclass
class ChannelTarget:
    """Per-channel initial target overrides for printcal (-x/-m/-n/-t flags)."""
    ch: int                     # channel index 0-7
    max_pct: float | None = None   # -x: max device % (override auto)
    dev_pct: float | None = None   # -m: dev target as % of auto max
    white_de: float | None = None  # -n: white minimum deltaE target
    t50_pct: float | None = None   # -t: 50% transfer curve percentage


@dataclass
class PrintcalParams:
    ti3_path: Path                   # input measurement file (base name also used for output .cal)
    mode: str = "initial"            # "initial" | "recalibrate" | "verify" | "imitation"
    prev_cal: str = ""               # previous .cal path (used in recalibrate/verify mode)
    verbosity: int = 1
    smoothing: float = 1.0
    resolution: int = 256
    manufacturer: str = ""
    model: str = ""
    description: str = ""
    copyright: str = ""
    dry_run: bool = False            # -d: simulate without writing files
    channel_targets: list[ChannelTarget] = field(default_factory=list)
    extra_args: str = ""


class PrintcalRunner:
    def __init__(self, runner: "ArgyllRunner", settings: "AppSettings") -> None:
        self._runner = runner
        self._settings = settings
        self._on_finish_cb: Callable[[Path | None], None] | None = None
        self._out_cal: Path | None = None
        self._matched_errors: list[tuple[str, str]] = []
        self._matched_warnings: list[tuple[str, str]] = []

    def run(
        self,
        params: PrintcalParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[Path | None], None],
    ) -> None:
        """Run printcal; call on_finish(cal_path) on success, on_finish(None) on failure."""
        self._on_finish_cb = on_finish
        self._matched_errors = []
        self._matched_warnings = []
        # A calibration chart printed through an earlier calibration carries
        # it too, and printcal loads the .ti3 the same way colprof does.
        from workflow.cal_repair import repair_embedded_cal
        repair_embedded_cal(params.ti3_path)

        stem = params.ti3_path.stem  # base name without extension
        work_dir = params.ti3_path.parent
        self._out_cal = work_dir / f"{stem}.cal"

        args = self._build_args(params, stem)
        log.info("printcal args: %s", args)

        def _scan(line: str) -> None:
            self._scan_line(line)
            on_line(line)

        self._runner.run(
            "printcal",
            args,
            work_dir,
            on_line=_scan,
            on_finish=lambda code: self._done(code, on_finish),
        )

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _PRINTCAL_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                # ``COLOR_REP '%s' invalid`` has an optional 2nd group — render
                # the parenthetical bit only when it's present.
                groups = tuple(g or "" for g in m.groups())
                if key == "color_rep_invalid" and groups[1]:
                    msg = fmt.format(groups[0], " — " + groups[1])
                elif key == "color_rep_invalid":
                    msg = fmt.format(groups[0], "")
                else:
                    msg = fmt.format(*groups)
                self._matched_errors.append((key, msg))
        for pattern, key, fmt in _PRINTCAL_WARNING_PATTERNS:
            m = pattern.search(line)
            if m:
                self._matched_warnings.append((key, fmt.format(*m.groups())))

    def primary_failure(self) -> tuple[str, str] | None:
        return self._matched_errors[0] if self._matched_errors else None

    def captured_warnings(self) -> list[tuple[str, str]]:
        return list(self._matched_warnings)

    def _done(self, code: int, on_finish: Callable[[Path | None], None]) -> None:
        cal = self._out_cal
        success = (code == 0) and cal is not None and cal.exists()
        if success:
            log.info("printcal succeeded → %s", cal)
            on_finish(cal)
        else:
            log.error("printcal failed (code %d)", code)
            on_finish(None)

    def _build_args(self, p: PrintcalParams, stem: str) -> list[str]:
        args: list[str] = []

        args.append(f"-v{p.verbosity}")
        args.append(f"-s{p.smoothing:.1f}")

        if p.resolution != 256:
            args.append(f"-z{p.resolution}")

        if p.mode == "initial":
            args.append("-i")
        elif p.mode == "recalibrate":
            args.append("-r")
        elif p.mode == "verify":
            args.append("-e")
        elif p.mode == "imitation":
            args.append("-I")

        if p.dry_run:
            args.append("-d")

        if p.manufacturer:
            args += ["-A", p.manufacturer]
        if p.model:
            args += ["-M", p.model]
        if p.description:
            args += ["-D", p.description]
        if p.copyright:
            args += ["-C", p.copyright]

        # Per-channel initial target overrides (only meaningful for initial/imitation modes)
        # Format: flag+channel-code as one arg, value as separate arg (e.g. "-x0" "85.0")
        for ct in p.channel_targets:
            ch = str(ct.ch)
            if ct.max_pct is not None:
                args += [f"-x{ch}", f"{ct.max_pct:.1f}"]
            if ct.dev_pct is not None:
                args += [f"-m{ch}", f"{ct.dev_pct:.1f}"]
            if ct.white_de is not None:
                args += [f"-n{ch}", f"{ct.white_de:.2f}"]
            if ct.t50_pct is not None:
                args += [f"-t{ch}", f"{ct.t50_pct:.1f}"]

        if p.extra_args:
            args += shlex.split(p.extra_args)

        # previous .cal must come before the inoutfile when recalibrating/verifying
        if p.mode in ("recalibrate", "verify") and p.prev_cal:
            args.append(p.prev_cal)

        args.append(stem)
        return args
