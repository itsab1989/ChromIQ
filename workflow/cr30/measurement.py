"""The measurement model, and the guards that keep a bad one out.

Everything here exists because of a VERIFIED hazard (MEASUREMENT.md,
CALIBRATION.md): with a magnet near the aperture the CR30 performs a white
CALIBRATION instead of a measurement and returns a stored constant. The
transaction is indistinguishable from a real one — correct framing, valid
checksum, a plausible near-neutral spectrum, no error, no status byte, and
offset 24 unchanged on the host path.

So a caller CANNOT rely on the protocol to tell it something went wrong **on a
host-triggered read**. On a BUTTON-triggered read over USB it can: the device's
own unsolicited `BB 01 09` header carries offset 24 = 0x01 when the gate is
engaged and 0x00 when it is not (3/3 button frames, 0/20+ host-triggered ones --
MEASUREMENT.md). The spot workflow this project recommends is exactly the button
case, so that flag IS available and `gate_flag` carries it. It is the only one of
the three checks here that is unit-independent and that works on the FIRST
reading of a run. Prefer it; the two behavioural checks are the fallback.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field


class MeasurementError(Exception):
    """A reading that must not be used. Never downgraded to a warning."""


# ⚠ The wording matters and the previous wording was wrong in a way that could
# cost a user their calibration. It said the device "returns this constant
# instead of measuring ... read again". CALIBRATION.md's VERIFIED finding is
# stronger than that: the device performs a WHITE CALIBRATION against whatever
# is under the aperture. By the time this error is raised the stored white
# reference may ALREADY have been overwritten, and "read again" then produces
# readings that are wrong by a scale factor no guard here can see.
MAGNET_MESSAGE = (
    "this reading was taken with a magnet at the aperture. The CR30 does not "
    "measure in that state -- it performs a WHITE CALIBRATION against whatever "
    "is under the aperture and reports the stored tile value. STOP: remove the "
    "cap and any magnet, then RECALIBRATE (seat the cap correctly, white tile "
    "toward the aperture, and press the device button) before reading anything "
    "else. The device's stored white reference may already be wrong, and a "
    "wrong white reference is invisible in the data.")


# The gated/stored tile spectrum, captured on this unit over BOTH transports
# (EXP-MEAS-002/003, EXP-BLE-010) — bit-identical every time, and identical
# with white OR green under the aperture.
TILE_SIGNATURE = [
    70.3943, 74.8234, 77.4351, 78.3985, 77.9172, 77.6712, 78.0504, 78.5432,
    79.2815, 80.1434, 80.6955, 80.7391, 80.5451, 80.1352, 79.9302, 79.7828,
    79.6362, 79.6665, 79.7891, 79.9468, 79.9118, 79.8988, 79.9740, 80.0577,
    80.1447, 80.6163, 80.4520, 80.1841, 79.5773, 78.8277, 77.9322,
]

# Physical bounds. A reflectance FACTOR can legitimately exceed 100 % — a
# strongly brightened paper fluoresces under the device's illumination while the
# calibration tile does not — but not by much. Above ~120 % the explanation is a
# wrong white reference, not a bright sample.
#
# Calibrated with real data: a healthy reading of plain paper peaked at 96.4 %
# (EXP-MEAS-001); the same paper read 156.8 % mean and 193.8 % peak with the
# white reference corrupted (EXP-CAL-002). The hard bound must therefore sit
# below 156, and comfortably above 100.
#
# ⚠⚠ KNOW WHAT THIS DOES NOT DO. `[CR30-SKEPTIC]`, 2026-08-28.
#
# 1. It is fitted to the single most extreme corrupted number ever recorded, and
#    a LESS extreme corrupted reading survives in this repository and PASSES.
#    `EXP-MEAS-003`'s `patch_after` was taken immediately after the calibration
#    was destroyed, under the green reference, and peaks at **105.47 %R**. It is
#    below MAX (130) and below SUSPICIOUS (110): `check_usable()` ACCEPTS it,
#    silently, with no warning. Proven in tests/test_skeptic_guard_gaps.py.
# 2. The guard is ONE-SIDED and the failure is TWO-SIDED. Calibrating against a
#    surface DARKER than the tile inflates every later reading (catchable);
#    calibrating against a surface BRIGHTER than the tile DEFLATES them, and
#    nothing here can see that. The realistic accident during a chart read is
#    gating on a near-white chart patch: paper reads ~85.8 % mean against the
#    tile's ~78.9 %, so every subsequent reading comes back ~8 % DARK, forever,
#    with no symptom at all.
# 3. Even on the catchable side it only bites when the sample is already bright.
#    A corruption factor below 130/96.4 = 1.35 never breaches MAX on paper, and
#    on the dark patches that make up most of a chart no factor ever does.
#
# CONCLUSION: treat these bounds as a coarse backstop against gross corruption,
# NOT as a calibration check. A real calibration check re-measures a known
# reference; see EXP-CAL-002's design. `[CR30-SKEPTIC]` recommends the numbers
# are NOT changed on present evidence -- widening or narrowing them does not fix
# a one-sided test -- and that the limitation is stated in INTEGRATION.md
# instead. Whether a fluorescing OBA paper can legitimately reach 130 %R on THIS
# device is UNKNOWN: it depends on the UV content of the CR30's illuminant,
# which nobody has measured. EXP-MEAS-006 is specified in MEASUREMENT.md.
SUSPICIOUS_REFLECTANCE = 110.0   # plausible only for a fluorescing sample
MAX_REFLECTANCE = 130.0          # above this the white reference is wrong
MIN_REFLECTANCE = -1.0


@dataclass
class Measurement:
    """One CR30 reading. `values` are PERCENT reflectance."""

    wavelengths: list[int]
    values: list[float]
    lab: list[float] | None = None          # device-reported L*a*b*, if available
    gate_flag: bool | None = None           # frame offset 24 of the BUTTON header
    transport: str = ""
    device_model: str = ""
    timestamp: str = ""
    raw: bytes = b""
    metadata: dict = field(default_factory=dict)

    # -- validation ------------------------------------------------------
    def validate(self) -> None:
        """Raise unless this is structurally and physically plausible."""
        if len(self.values) != len(self.wavelengths):
            raise MeasurementError(
                f"{len(self.values)} values for {len(self.wavelengths)} bands")
        if not self.values:
            raise MeasurementError("empty spectrum")
        bad = [(w, v) for w, v in zip(self.wavelengths, self.values)
               if not math.isfinite(v)]
        if bad:
            raise MeasurementError(f"non-finite value at {bad[0][0]} nm")
        lo, hi = min(self.values), max(self.values)
        if lo < MIN_REFLECTANCE or hi > MAX_REFLECTANCE:
            raise MeasurementError(
                f"reflectance outside physical range: {lo:.4g}..{hi:.4g} %. "
                "A reading far above 100 % means the stored white reference is "
                "wrong, not that the sample is bright — recalibrate against the "
                "white tile (seat the cap correctly, press the device button).")
        if hi > SUSPICIOUS_REFLECTANCE:
            self.metadata["warning"] = (
                f"peak {hi:.1f} %R exceeds {SUSPICIOUS_REFLECTANCE:.0f} %. "
                "Plausible for a strongly brightened paper, but also the early "
                "sign of a drifting white reference.")
        if self.lab is not None:
            if not all(math.isfinite(x) for x in self.lab):
                raise MeasurementError("non-finite Lab")
            if not 0.0 <= self.lab[0] <= 100.0:
                raise MeasurementError(f"L* out of range: {self.lab[0]:.4g}")

    # -- the magnet hazard ----------------------------------------------
    def looks_like_calibration_tile(self, tol: float = 0.05) -> bool:
        """Is this the stored tile constant rather than a measurement?

        VERIFIED **on this unit**: with a magnet present the device returns
        exactly this, whether the white tile or a GREEN surface is under the
        aperture.

        ⚠ **This check is unit-specific and cannot be assumed to work on another
        CR30.** `TILE_SIGNATURE` is one unit's stored constant. The only other
        CR30 we have data for reads its white reference **up to 4.69 %R lower**
        (`PRIORART-001`, "Calibrate White and Black and Test Target" /
        "Test Sample white": band ratio 0.9703 +/- 0.0161, dE76 1.73 against
        `TILE_SIGNATURE`). 4.69 is **94x** this tolerance, so on that unit this
        method returns False for every gated reading and contributes nothing.
        Widening `tol` is not the fix -- 4.69 %R would swallow real patches.
        The fix is to LEARN the constant per unit; see MEASUREMENT.md.
        `gate_flag` is the unit-independent check and must be preferred.
        """
        if len(self.values) != len(TILE_SIGNATURE):
            return False
        return all(abs(a - b) <= tol
                   for a, b in zip(self.values, TILE_SIGNATURE))

    def identical_to(self, other: "Measurement | None") -> bool:
        """Bit-identical to the previous reading.

        Genuine consecutive readings differ in the low bits even without lifting
        the instrument (0.056 % worst-band SD, EXP-MEAS-001). Exact equality
        means either the device is gated or no new reading was taken.
        """
        if other is None:
            return False
        return self.values == other.values

    def check_usable(self, previous: "Measurement | None" = None) -> None:
        """Full gate. Raise unless this reading may be used for profiling.

        Order matters: the protocol flag is checked FIRST because it is the only
        one of the three that is unit-independent and works on the first reading
        of a run. See `gate_flag`.
        """
        self.validate()
        if self.gate_flag:
            raise MeasurementError(MAGNET_MESSAGE + " (The device's own header "
                                   "flagged this reading: frame offset 24 = 1.)")
        if self.looks_like_calibration_tile():
            raise MeasurementError(MAGNET_MESSAGE)
        if self.zero_run() >= 3:
            raise MeasurementError(
                f"{self.zero_run()} consecutive bands are exactly 0.0 %R. That is "
                "a truncated or zero-filled reply, not a dark sample -- a real "
                "dark patch still reads a few percent.")
        if self.identical_to(previous):
            raise MeasurementError(
                "reading is bit-identical to the previous one. Either no new "
                "measurement was taken, or a magnet is gating the device. "
                "Genuine repeats differ in the low bits.")

    def zero_run(self, n: int = 3) -> int:
        """Longest run of EXACTLY 0.0 bands.

        A truncated, zero-filled reply looks structurally perfect: right header,
        right length, valid checksum. The vendor's own 410-byte BLE stream is a
        truncated reply followed by a complete one, and a naive first-match scan
        takes the truncated one -- five bands of 0.0 %R and a Lab of pure black,
        which every other check accepts.

        A real dark patch reads a few percent, never exactly 0.0 across a run.
        """
        best = run = 0
        for v in self.values:
            run = run + 1 if v == 0.0 else 0
            best = max(best, run)
        return best

    # -- convenience -----------------------------------------------------
    @property
    def mean(self) -> float:
        return statistics.fmean(self.values)

    def as_dict(self) -> dict:
        return {"wavelengths": self.wavelengths, "values": self.values,
                "lab": self.lab, "transport": self.transport,
                "device": self.device_model, "timestamp": self.timestamp,
                "metadata": self.metadata}
