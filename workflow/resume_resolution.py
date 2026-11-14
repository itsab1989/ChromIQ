"""Refine / resume and "High resolution spectral mode (-H)" (4.3.37).

A tester resumed a measurement whose 270 readings were taken without -H, with
-H ticked. ArgyllCMS's chartread (and ChromIQ's engine, a fork of it) only
notices when it WRITES the file: `save_ti3` compares every reading's spectrum
with the resumed ones and stops with "The resumed spectral type seems to have
changed!". By then the new strips had been measured; the engine's exit was
taken for a lost connection, stock chartread was started to continue, failed
the same way at the end, and the re-read strips were lost.

So this is asked BEFORE anything is measured: does the measurement being
continued have the spectral resolution this read would produce? Only the
resolution is compared: high resolution (bands closer than 10 nm) or
standard (10 nm). An instrument ArgyllCMS gives no high-resolution mode
ignores -H ("Warning - high resolution ignored"), so for it -H changes
nothing and nothing is refused.
"""
from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path

#: Instruments ArgyllCMS can measure in high resolution (i1pro.c, i1pro3.c,
#: munki.c: the "highres" mode); names normalised like core.measure_pace.
_HIGHRES_CAPABLE = re.compile(r"i1pro|colormunki|i1studio|colorcheckerstudio")

#: Closer than this (nm) between two bands is high resolution. Argyll's
#: standard mode is 10 nm; its high-resolution mode 3.333 nm.
_HIGHRES_BELOW_NM = 9.0


@dataclass(frozen=True)
class Resolution:
    bands: int
    start_nm: float
    end_nm: float

    @property
    def step_nm(self) -> float:
        return (self.end_nm - self.start_nm) / max(1, self.bands - 1)

    @property
    def high(self) -> bool:
        return self.bands > 1 and self.step_nm < _HIGHRES_BELOW_NM


def read_resolution(ti3: "str | Path") -> "Resolution | None":
    """The spectral resolution a .ti3 records, from its header keywords; None
    when it records no spectra (or cannot be read)."""
    vals = {}
    try:
        with open(ti3, encoding="latin-1", errors="replace") as fh:
            for line in fh:
                if line.startswith("BEGIN_DATA_FORMAT"):
                    break
                m = re.match(r'\s*(SPECTRAL_BANDS|SPECTRAL_START_NM|'
                             r'SPECTRAL_END_NM)\s+"?([0-9.]+)"?', line)
                if m:
                    vals[m.group(1)] = float(m.group(2))
    except OSError:
        return None
    if not {"SPECTRAL_BANDS", "SPECTRAL_START_NM",
            "SPECTRAL_END_NM"} <= set(vals):
        return None
    return Resolution(int(vals["SPECTRAL_BANDS"]), vals["SPECTRAL_START_NM"],
                      vals["SPECTRAL_END_NM"])


def asks_for_highres(extra_args: str) -> bool:
    """Whether the reader's arguments ask for -H."""
    try:
        parts = shlex.split(extra_args or "")
    except ValueError:
        parts = (extra_args or "").split()
    return "-H" in parts


def instrument_can_highres(name: "str | None") -> bool:
    """Whether ArgyllCMS has a high-resolution mode for this instrument (the
    chart's TARGET_INSTRUMENT, or the name the instrument reported). Unknown
    = True: then the file's own resolution decides."""
    if not name:
        return True
    low = re.sub(r"[\s\-_.]+", "", str(name).lower())
    return bool(_HIGHRES_CAPABLE.search(low))


@dataclass(frozen=True)
class Mismatch:
    #: the measurement so far was taken in high resolution
    file_high: bool
    #: this read would measure in high resolution
    read_high: bool
    resolution: Resolution
    #: 4.3.37 review (M4): the measurement was taken in high resolution and
    #: the instrument has no high-resolution mode at all: it cannot be
    #: continued in the same resolution with this instrument
    instrument_cannot: bool = False


def resume_mismatch(ti3: "str | Path | None", extra_args: str,
                    instrument: "str | None") -> "Mismatch | None":
    """The mismatch a resume onto *ti3* with *extra_args* would run into, or
    None when there is none (or nothing to compare)."""
    if ti3 is None:
        return None
    res = read_resolution(ti3)
    if res is None:
        return None
    read_high = asks_for_highres(extra_args) and instrument_can_highres(
        instrument)
    if not instrument_can_highres(instrument):
        # -H is ignored by such an instrument; a measurement taken in high
        # resolution cannot be continued with it at all (M4)
        if res.high:
            return Mismatch(file_high=True, read_high=False, resolution=res,
                            instrument_cannot=True)
        return None
    if res.high == read_high:
        return None
    return Mismatch(file_high=res.high, read_high=read_high, resolution=res)


def with_highres(extra_args: str, on: bool) -> str:
    """*extra_args* with -H added or removed, for one session."""
    try:
        parts = shlex.split(extra_args or "")
    except ValueError:
        parts = (extra_args or "").split()
    parts = [p for p in parts if p != "-H"]
    if on:
        parts.append("-H")
    return shlex.join(parts)


#: The sentence ArgyllCMS's chartread (and the engine) stops with when a
#: resumed file's spectra differ from the new readings (chartread.c save_ti3).
SPECTRAL_CHANGED_RE = re.compile(r"resumed spectral type seems to have changed",
                                 re.IGNORECASE)
