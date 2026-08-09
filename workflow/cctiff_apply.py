"""Applies an ICC **device-link** to an image with ``cctiff``.

A device-link bakes a *source → printer* transform (built by :mod:`collink`).
``cctiff`` pushes the image's pixels straight through the link's A2B0 table, so
the output TIFF is already in the printer's **native RGB** with no embedded
profile — ready to print *raw* (the same way ChromIQ prints test charts, i.e.
with the driver's colour management switched off) or to hand to a RIP.

Note: because the link's source space is baked in, ``cctiff`` ignores the
image's embedded profile — the image must already be in the link's source
colour space for the result to be correct.

Mirrors the other Argyll runners (:mod:`workflow.collink_runner`): a params
dataclass + a runner that builds the CLI and drives it through the singleton
:class:`~core.argyll_runner.ArgyllRunner` (single-process), with structured
error parsing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

from core.logger import get_logger

log = get_logger(__name__)


def link_args(link: Path, in_path: Path, out_path: Path,
              precise: bool = True, verbose: bool = True) -> list[str]:
    """``cctiff [-v] [-p] -f T <link> <in> <out>`` — apply a device-link. ``-f T``
    forces TIFF output so a JPEG source still yields a print-ready TIFF. No
    ``-i`` intent: it is baked into the link. Paths come last, link/in/out."""
    args: list[str] = []
    if verbose:
        args.append("-v")
    if precise:
        args.append("-p")
    args += ["-f", "T", str(link), str(in_path), str(out_path)]
    return args


def convert_args(from_profile: Path, to_profile: Path, in_path: Path,
                 out_path: Path, precise: bool = True, verbose: bool = True,
                 intent: str = "r") -> list[str]:
    """``cctiff [-v] [-p] -f T -i <intent> <from> -i <intent> <to> <in> <out>``
    — a profile-to-profile conversion of the image. *intent* is cctiff's own
    letter (``p`` perceptual, ``r`` relative, ``s`` saturation, ``a``
    absolute), applied to both ends; the default keeps the historical
    relative-colorimetric behaviour (#130 A0.2)."""
    args: list[str] = []
    if verbose:
        args.append("-v")
    if precise:
        args.append("-p")
    args += ["-f", "T", "-i", intent, str(from_profile), "-i", intent,
             str(to_profile), str(in_path), str(out_path)]
    return args


_CCTIFF_ERROR_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"ICC V4 not supported", re.IGNORECASE),
     "icc_v4",
     "The device-link is an ICC version-4 profile, which the ArgyllCMS engine "
     "can't read. Rebuild the link (ChromIQ writes version-2 links)."),
    (re.compile(r"[Cc]an'?t open (?:file|profile)?\s*'?([^'\n]+)'?"),
     "open_failed",
     "Couldn't open '{0}'. Check that the file exists and is readable."),
    (re.compile(r"not a device link|Expected .* device link|Wrong .*Colorspace"),
     "not_a_link",
     "That profile isn't a usable RGB device-link. Pick a device-link built by "
     "the 'Create device-link profile' tool."),
]


@dataclass
class CctiffApplyParams:
    """One image → printer-native TIFF through a device-link. Paths are absolute."""

    link_path: Path       # the device-link .icc (collink output, v2)
    in_path: Path         # source image (TIFF/JPEG, already in the link's source space)
    out_path: Path        # printer-native TIFF to write
    precise: bool = True   # -p  slow, precise correction (worth it for a print file)
    verbose: bool = True


class CctiffApplyRunner:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner = runner
        self._last_log = ""
        self._matched_errors: list[tuple[str, str]] = []

    def run(
        self,
        params: CctiffApplyParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        args = self._build_args(params)
        cwd = params.out_path.parent
        log.info("cctiff: %s  [cwd=%s]", " ".join(args), cwd)
        self._last_log = ""
        self._matched_errors = []

        def _accumulate(line: str) -> None:
            self._last_log += line + "\n"
            self._scan_line(line)
            on_line(line)

        self._runner.run("cctiff", args, cwd, on_line=_accumulate, on_finish=on_finish)

    def _scan_line(self, line: str) -> None:
        for pattern, key, fmt in _CCTIFF_ERROR_PATTERNS:
            m = pattern.search(line)
            if m:
                groups = tuple(g or "" for g in m.groups())
                self._matched_errors.append((key, fmt.format(*groups)))

    def primary_failure(self) -> tuple[str, str] | None:
        return self._matched_errors[0] if self._matched_errors else None

    @property
    def last_log(self) -> str:
        return self._last_log

    # ------------------------------------------------------------------
    def _build_args(self, p: CctiffApplyParams) -> list[str]:
        return link_args(p.link_path, p.in_path, p.out_path, p.precise, p.verbose)
