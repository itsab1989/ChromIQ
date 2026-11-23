"""Is the calibration behind a spot reading believable? (Read single patches)

WHY THIS EXISTS. ArgyllCMS accepts a white calibration that is too WEAK. Its
white check for the i1Pro family (``i1pro_imp.c``, the white reference test)
compares the SHAPE of the tile's spectrum, normalised at 550 nm, and nothing
else, so a calibration taken with the instrument not flat on its white tile
(too little of the lamp's light comes back) passes as "Calibration complete".
Every reading of that session then comes out too light by one factor: the
reflectance is the patch's signal divided by the tile's, and the tile's was too
small. A tester's ES-2000 logs show it in 2 of 37 calibrations: a whole session
x1.08 to x1.12 too light, and one where a yellow read x1.33, then x1.62, then
"Sensor is saturated". The next calibration put both right.

WHAT IS LOOKED AT, AND THE PHYSICS BEHIND THE NUMBERS.

* **Reflectance above 1 between 530 and 700 nm.** A reflective print, measured
  in 45/0 geometry (the gloss is not seen), cannot send back more light than a
  perfect white diffuser at the same wavelength: that is a reflectance of 1.00
  (100 %), and the instrument's white tile is calibrated to it. The exception
  is fluorescence, which moves energy from one wavelength to another. Paper
  brighteners (OBA) absorb UV and re-emit blue, peaking at 430-450 nm and
  falling to a few percent of the peak by about 500 nm, so a brightened paper
  read in M0 or M1 can read 105-120 % in the blue. Above about 520 nm their
  emission is negligible. So the band starts at **530 nm**, with a margin past
  that tail, and ends at **700 nm**, because the last bands (700-730 nm) carry
  the least lamp light and are the noisiest. The band MEAN is used, so a
  narrow peak (a fluorescing magenta dye emits around 600 nm, but absorbs
  strongly from 530 to 580 nm) cannot carry the mean above the limit.
* **The limit is 102 %, not 100 %.** The brightest papers reach about 92-95 %
  in this band. The 2 % covers what a good calibration can still leave: the
  tile's stored reference values (instrument to instrument well under 1 %)
  and the repeatability of a reading, which averaged over the 18 bands is a
  few tenths of a percent. A correctly calibrated instrument therefore does
  not cross 102 % on any ordinary paper or ink, and a weak calibration of
  factor k crosses it on the first patch whose true band reflectance R has
  k * R > 1.02: on a 90 % paper from k = 1.13, on a light yellow (about 85 %
  there) from k = 1.20.
* **Saturation.** The i1Pro family sets its integration time on the white tile
  at calibration, with headroom for anything a print can reflect. A sensor
  that saturates on a reflective patch afterwards means the instrument expects
  far less light than a print returns, which is the same weak calibration
  seen from the other side (the tester's x1.62 session ended exactly so).

WHAT IT CANNOT SEE. A weak calibration small enough that no patch of the
session crosses 102 %: the tester's x1.11 session on a paper of about 88 %
reached 98 %, which a perfectly calibrated bright paper can also read. Only a
comparison with an earlier session can show that, so the Calibration Complete
window suggests reading the bare paper first.

WHAT IT NEVER DOES. It never refuses, drops or changes a reading. It says so,
once per calibration, and the person decides.

Without a spectrum (a reflective instrument ArgyllCMS cannot give spectral
data for) the same limit is applied to Y, the luminance, which is the
reflectance weighted by the eye's sensitivity: it also cannot pass 100 for a
non-fluorescent print, and the brighteners' blue adds almost nothing to it.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

#: The band the reflectance is averaged over, in nm (see the module docstring:
#: past the brighteners' emission, short of the noisy far red).
BAND_NM = (530.0, 700.0)

#: The limit on the band mean, as a reflectance in percent: a perfect white
#: diffuser is 100; 2 % for the tile's reference values and the repeatability
#: of one reading.
LIMIT_PERCENT = 102.0

#: "Spectrum from 380.000 to 730.000 nm in 36 steps" (spotread -s)
SPECTRUM_HEAD_RE = re.compile(
    r"Spectrum from\s+([\d.]+)\s+to\s+([\d.]+)\s+nm in\s+(\d+)\s+steps",
    re.IGNORECASE)

#: "Spot read failed due to misread (Sensor is saturated)"
SATURATED_RE = re.compile(r"saturat", re.IGNORECASE)


def parse_spectrum_values(line: str, steps: int) -> "list[float] | None":
    """The values line that follows the spectrum header, or None if it is not one."""
    parts = [p for p in re.split(r"[,\s]+", line.strip()) if p]
    if len(parts) != steps:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def band_mean_percent(values: "list[float]", wl_short: float, wl_long: float,
                      y: "float | None" = None) -> "float | None":
    """Mean reflectance over :data:`BAND_NM`, in percent.

    ArgyllCMS prints a reflective spectrum in percent (the i1Pro and
    ColorMunki drivers scale it by 100, ``sp.norm = 100``). Should a driver
    print fractions instead, the luminance *y* (0..100) settles which scale it
    is: the one that brings the spectrum's mean nearer to Y. Never decided
    from the size of the values alone, because a black patch in percent is as
    small as a white one in fractions.
    """
    n = len(values)
    if n < 2 or wl_long <= wl_short:
        return None
    step = (wl_long - wl_short) / (n - 1)
    lo, hi = BAND_NM
    band = [v for i, v in enumerate(values)
            if lo - 1e-6 <= wl_short + i * step <= hi + 1e-6]
    if not band:
        return None
    mean = sum(band) / len(band)
    if y is not None and y > 0:
        whole = sum(values) / n
        if whole > 0 and abs(math.log(whole * 100.0 / y)) < abs(math.log(whole / y)):
            mean *= 100.0
    return mean


@dataclass(frozen=True)
class Verdict:
    """Why the calibration looks too weak."""
    reason: str                  # "too_light" | "saturated"
    percent: "float | None" = None   # the band mean (or Y) that crossed the limit


class SpotCalibrationCheck:
    """Watches the readings of one calibration and speaks once.

    :meth:`reset` is called when a calibration is in force (the session start,
    which reads with the instrument's start-up or stored calibration, and each
    finished calibration). The first reading that crosses the limit, or the
    first saturation, gives a :class:`Verdict`; after that the check is quiet
    until the next :meth:`reset`.
    """

    def __init__(self) -> None:
        self._armed = True

    def reset(self) -> None:
        self._armed = True

    @property
    def armed(self) -> bool:
        return self._armed

    def on_reading(self, xyz: "tuple[float, float, float]",
                   spectrum: "tuple[float, float, list[float]] | None" = None
                   ) -> "Verdict | None":
        """Judge one reflective reading: XYZ on the 0..100 scale and, when
        spotread printed one, (wl_short, wl_long, values)."""
        if not self._armed:
            return None
        y = float(xyz[1]) if xyz and len(xyz) > 1 else None
        level = None
        if spectrum is not None:
            level = band_mean_percent(spectrum[2], spectrum[0], spectrum[1], y)
        if level is None:
            level = y
        if level is None or level <= LIMIT_PERCENT:
            return None
        self._armed = False
        return Verdict("too_light", level)

    def on_saturated(self) -> "Verdict | None":
        if not self._armed:
            return None
        self._armed = False
        return Verdict("saturated")
