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

import logging
import math
import statistics
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


class MeasurementError(Exception):
    """A reading that must not be used. Never downgraded to a warning."""


# ⚠ The wording matters and the previous wording was wrong in a way that could
# cost a user their calibration. It said the device "returns this constant
# instead of measuring ... read again". CALIBRATION.md's VERIFIED finding is
# stronger than that: the device performs a WHITE CALIBRATION against whatever
# is under the aperture. By the time this error is raised the stored white
# reference may ALREADY have been overwritten, and "read again" then produces
# readings that are wrong by a scale factor no guard here can see.
class MagnetGated(MeasurementError):
    """A reading taken with a magnet at the aperture.

    Its own class because it needs the OPPOSITE answer to every other refused
    reading. An ordinary refusal costs one button press and the patch is armed
    again; this one means the instrument has ALREADY recalibrated itself
    against whatever it was sitting on, so every reading after it would be
    wrong by an unknown factor — invisibly. Re-arming and inviting another
    press is the worst thing the app can do.

    It happened for real on 2026-08-30: a sheet of paper on a MacBook, whose
    magnets reached through it. The guard fired, and the session carried on.
    """


MAGNET_MESSAGE = (
    "a magnet at the aperture turned this reading into a white calibration, "
    "so the value is the instrument's stored tile and not your patch")

#: ⚠ KEEP IT SHORT AND TECHNICAL. This text is the exception's message, and it
#: reaches the user through M-CR30-MAGNET's "{reason}" slot -- so a long
#: teaching paragraph here is printed UNDERNEATH the window that has just
#: taught the same thing, in capitals, with double dashes, labelled as what the
#: instrument reported. It is not: the instrument reported a flag bit. The
#: window does the explaining and the remedy; this says only what was detected.

#: ⚠ The recovery this message used to give — "seat the cap and press the device
#: button" — was the side-effect method ChromIQ itself has stopped using. Worse,
#: followed in the middle of a session it produces ANOTHER gated reading and
#: another refusal. ChromIQ now offers to recalibrate with the instrument's own
#: command instead, so the message says WHAT must happen and the app does it.


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
    def looks_like_calibration_tile(self, tol: float = 0.05,
                                    learned: "list[float] | None" = None) -> bool:
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
        Pass `learned` -- this unit's own constant, captured from a proven
        gated press by `tile_learning` -- and the check works on ANY unit. That
        is the fix this docstring has been asking for; the hard-coded constant
        stays as the fallback for a unit that has not been through the learning
        step, where it protects the owner's instrument and, honestly, nothing
        else. `gate_flag` remains the unit-independent check and is preferred
        where the transport reports one (USB button presses only).
        """
        if learned and len(self.values) == len(learned):
            # A LEARNED signature is this unit's own constant, captured at the
            # precision the device actually returns, so it is compared far more
            # tightly than the hard-coded one -- see tile_learning.
            from .tile_learning import LEARNED_TOLERANCE
            if all(abs(a - b) <= LEARNED_TOLERANCE
                   for a, b in zip(self.values, learned)):
                return True
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

    def check_usable(self, previous: "Measurement | None" = None, *,
                     learned_tile: "list[float] | None" = None) -> None:
        """Full gate. Raise unless this reading may be used for profiling.

        Order matters: the protocol flag is checked FIRST because it is the only
        one of the three that is unit-independent and works on the first reading
        of a run. See `gate_flag`.
        """
        self.validate()
        if self.gate_flag:
            raise MagnetGated(
                MAGNET_MESSAGE + ". The device's own header flagged it: "
                "frame offset 24 = 1.")
        if self.looks_like_calibration_tile(learned=learned_tile):
            raise MagnetGated(
                MAGNET_MESSAGE + ". The reading matches "
                + ("this instrument's own learned tile value exactly."
                   if learned_tile else
                   "the built-in tile value."))
        incomplete = self.truncation_reason()
        if incomplete:
            raise MeasurementError(incomplete)
        if self.identical_to(previous):
            raise MeasurementError(
                "the instrument returned exactly the same numbers as last "
                "time, down to the last digit. Real readings always differ a "
                "little, so no new measurement was taken.")
        # An ACCEPTED reading that sits on the instrument's floor in some
        # bands. Ordinary for a saturated ink on glossy paper, and worth a line
        # in the log rather than a window: those bands are a floor, not a
        # measurement, so a profile built from them is slightly optimistic
        # there. It was this shape of reading that the old zero-run guard
        # refused outright, so a support log should now say when one arrives.
        clamped = self.clamped_bands()
        if clamped:
            log.info("CR30: reading accepted with %d of %d bands at exactly "
                     "0.0 %%R -- the sample is at or below this instrument's "
                     "zero point there", clamped, len(self.values))

    def truncation_reason(self) -> "str | None":
        """Why this reply is INCOMPLETE, or None if it is a reading.

        A truncated, zero-filled reply looks structurally perfect: right header,
        right length, valid checksum. So something has to tell it from a real
        reading, and this is it.

        ⚠ IT USED TO BE `zero_run() >= 3`, AND THAT REFUSED REAL MEASUREMENTS.
        Reported from the field 2026-09-05: the most saturated patches of a
        chart could not be read at all on GLOSSY or SATIN paper, while the same
        patches on MATTE read first time. The window said "candidate at 0 has
        **3** zero bands (truncated reply)" -- exactly the threshold -- and the
        patch was refused six times over and then given up on, which stops the
        chart for good.

        The premise was wrong. It was written as "a real dark patch reads a few
        percent, never exactly 0.0 across a run", and this project's own
        captures say otherwise: the firmware CLAMPS, so a signal at or below the
        stored dark reference comes back as exactly 0.00000 %R.

        * EXP-022 (`device.read_measurement`): open air reads "exactly 0.00000
          %R on this instrument -- measured before and after".
        * EXP-020 phase A (`docs/cr30_reports/20_blackcal.md`): "0.00000
          exactly, all 31 bands, ALL FIVE readings"; phase C returned 0.034,
          0.151, 0.090, **0.000**, 0.0007.
        * Confirmed again on the owner's unit 2026-09-05: a stored buffer of 31
          bands, every one of them exactly 0.0.

        And the physics matches the paper dependence exactly. Ink on GLOSSY sits
        on the surface and reaches a far higher density than the same ink soaked
        into MATTE -- roughly 0.2..0.4 %R against 1.3..2.5 %R in the band the
        ink absorbs. The dark reference is taken against open air and may sit
        high by ~0.15 %R (EXP-020 phase C, and `20_blackcal.md` F5 works the
        arithmetic through), so on glossy the difference goes to or below zero
        and clamps, and on matte it never does. Three neighbouring bands is one
        30 nm window at an ink's absorption peak: entirely ordinary.

        WHAT REPLACES IT IS EXACT, NOT A THRESHOLD, and it covers every
        truncation this project has ever recorded (runs of 5, 16 and 31 zero
        bands -- never 3):

        1. **Every band exactly 0.0.** No signal at all; there is no reading in
           there to keep, whatever caused it. This is the device's not-ready
           buffer (the calibration read-back that failed with "16 zero bands"
           and the Bluetooth one with 31), and it is why the black calibration
           -- which points at open air and expects precisely this -- has to ask
           for it with `allow_dark`.
        2. **Reflectance in the spectrum but a Lab of pure black.** Those two
           cannot both be true: a spectrum with any reflectance in it has
           L* > 0. This is a proof rather than a guess, because of where the
           fields sit in the reply -- the spectrum occupies `SPECTRUM_AT`
           (8) to 131 and the Lab `LAB_AT` (184) to 195, so **a reply truncated
           anywhere inside the spectrum has necessarily lost its Lab as well.**
           That is the vendor capture's 5-zero-band candidate, and the 16-band
           one, without either needing a number chosen for it.

        The one shape this cannot see is a reply cut off between the end of the
        spectrum and the Lab: complete spectrum, empty Lab. It is refused too
        (rule 2), which costs one more poll and nothing else -- the chart is
        profiled from `values`, never from the device's Lab
        (`measure_bridge._xyz` -> `spectrum_to_xyz(m.values)`).
        """
        if not self.values:
            return "the reply carried no spectrum at all"
        if all(v == 0.0 for v in self.values):
            return (f"all {len(self.values)} bands came back exactly 0.0 %R, "
                    "so there is no reading in the reply at all")
        if self.lab is not None and not any(self.lab):
            return ("the reply carries reflectance but a Lab of pure black, "
                    "which cannot both be true -- the Lab sits after the "
                    "spectrum in the reply, so it is the part still unwritten")
        return None

    def clamped_bands(self) -> int:
        """How many bands came back at exactly 0.0 %R.

        Not a fault. It means the sample is at or below this instrument's zero
        point in those bands -- routine for a saturated ink on glossy paper --
        and the value there is a floor rather than a measurement. Reported so a
        support log says so; never a reason to refuse a reading. See
        :meth:`truncation_reason`.
        """
        return sum(1 for v in self.values if v == 0.0)

    def zero_run(self, n: int = 3) -> int:
        """Longest run of consecutive bands at EXACTLY 0.0.

        Diagnostic only since 2026-09-05. It is NOT a validity test and must not
        become one again: see :meth:`truncation_reason` for why a real reading
        contains exact zeros.
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
