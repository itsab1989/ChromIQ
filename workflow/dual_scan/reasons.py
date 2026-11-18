"""Reason ids for every refusal of the dual-scan calculation, with the plain
English sentence the user-interface step will put through ``tr()`` and the
message catalogue (§M-PROPOSED of ``unified_measurement_management.md``).

The calculation itself never shows text: it raises :class:`DualScanRefused`
with an id from :data:`REASONS`, and the caller decides what to say. The
sentences here are DRAFTS for that later step (no ``tr()`` yet, on purpose:
this step adds no user-facing string).
"""
from __future__ import annotations

#: id -> draft English sentence (for the UI step; not shown by this package)
REASONS: "dict[str, str]" = {
    "no_dual_calibration": (
        "This instrument was not calibrated for a dual scan. A dual scan "
        "needs a calibration that also reads the white tile with the UV "
        "light; without it the values come out about 15 % too bright. "
        "Calibrate again with dual scan switched on."),
    "calibration_mismatch": (
        "The calibration was made at another exposure than this reading, so "
        "it does not fit the reading. Calibrate again before measuring."),
    "no_uv_tables": (
        "This instrument does not hold the factory data needed to work out "
        "M1 and M2 (some i1Pro 2 versions have no UV light). M0 can be "
        "measured as always."),
    "bad_uv_tables": (
        "The instrument's factory data for M1 and M2 is not in the form "
        "ChromIQ knows, so ChromIQ does not use it. M0 can be measured as "
        "always."),
    "uv_pass_missing": (
        "The second pass with the UV light is missing for this reading, so "
        "M1 and M2 cannot be worked out. Read it again."),
    "uv_pass_count": (
        "The UV pass does not hold the same number of patches as the lamp "
        "pass, so ChromIQ cannot tell which UV reading belongs to which "
        "patch. Read the strip again."),
    "uv_pass_short": (
        "The second pass (UV light) did not cover the whole strip. Read the "
        "second pass of this strip again, over every patch; the first pass "
        "is kept."),
    "uv_pass_too_fast": (
        "The second pass (UV light) was read in a way that left too few "
        "readings per patch: move a little slower. Read the second pass of "
        "this strip again; the first pass is kept."),
    "uv_pass_stalled": (
        "The second pass (UV light) stopped or jumped part of the way along "
        "the strip, so some patches have no reading. Read the second pass of "
        "this strip again at an even speed; the first pass is kept."),
    "uv_pass_wrong_strip": (
        "The second pass (UV light) does not seem to belong to this strip: "
        "its readings do not follow the first pass. Read the second pass of "
        "this strip again, on the same strip; the first pass is kept."),
    "lamp_pass_changed": (
        "The first pass of this strip was read again, and the second pass "
        "taken earlier does not fit it any more. Read the second pass "
        "again too."),
    "dual_needs_ruler": (
        "A dual scan by hand needs the instrument's position ruler, to match "
        "the two passes patch by patch, and it gave no usable positions. "
        "M0 can still be measured as always."),
    "no_ruler": (
        "The instrument's position ruler gave no usable positions for this "
        "dual scan, so the two passes cannot be matched patch by patch. "
        "Read the strip again."),
    "calibration_mode_changed": (
        "The reading mode changed since the last calibration (dual scan "
        "and single scan need their own calibration). Calibrate again "
        "before measuring."),
    "bad_values": (
        "A reading holds values that are not numbers, so ChromIQ does not "
        "use it. Read it again."),
    "bad_scale": (
        "The factor used for M1 and M2 is not a sensible number, so ChromIQ "
        "does not use it."),
    "mixed_scan_kind": (
        "This measurement was started as a dual scan (M0, M1 and M2) and "
        "cannot be continued with single scans, or the other way round: "
        "the readings would not belong together. Continue it the way it "
        "was started, or start a new measurement."),
    # refining the factor from an i1Profiler file (optional)
    "refine_no_conditions": (
        "The i1Profiler file does not hold M0, M1 and M2. Measure the strip "
        "in i1Profiler with dual scan switched on and save all three."),
    "refine_patches_differ": (
        "The i1Profiler file and ChromIQ's dual scan do not hold the same "
        "patches, so they cannot be compared."),
    "refine_m0_differs": (
        "ChromIQ's M0 and i1Profiler's M0 of these patches differ too much "
        "to be the same strip read with the same instrument. Check that it "
        "is the same strip, read in the same direction, with the same "
        "instrument."),
    "refine_other_instrument": (
        "The i1Profiler file was not measured with this instrument: its M1 "
        "does not follow this instrument's factory data. Use a file "
        "measured with the same i1Pro 2."),
    "refine_no_glow": (
        "This paper has (almost) no optical brightener, so there is nothing "
        "to learn the factor from. Use a strip printed on a brightened "
        "paper (most bright white papers are)."),
    "refine_poor_fit": (
        "The factor could not be found cleanly from these readings (the "
        "readings and i1Profiler's values do not agree well enough). The "
        "standard factor stays in use."),
}


class DualScanRefused(ValueError):
    """The calculation will not give a result, and why (:data:`REASONS`)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        if reason not in REASONS:
            raise KeyError(f"unknown dual-scan reason id {reason!r}")
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)

    @property
    def sentence(self) -> str:
        """The draft English sentence (for logs and the later UI step)."""
        return REASONS[self.reason]
