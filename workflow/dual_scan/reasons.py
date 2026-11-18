"""Reason ids for every refusal of the dual-scan calculation, with the plain
English sentence the user-interface step will put through ``tr()`` and the
message catalogue (§M-PROPOSED of ``unified_measurement_management.md``).

The calculation itself never shows text: it raises :class:`DualScanRefused`
with an id from :data:`REASONS`, and the caller decides what to say. The
sentences here are DRAFTS for that later step (no ``tr()`` yet, on purpose:
this step adds no user-facing string).
"""
from __future__ import annotations

#: Notes that are NOT refusals: a pass was accepted, and this says what
#: could not be checked (the UI step shows them beside the strip).
NOTES: "dict[str, str]" = {
    "pairing_not_checked": (
        "The second pass of this strip could not be checked against the "
        "first one: its patches are too dark at 380 to 400 nm to compare "
        "(nothing to see there). The ruler checks were made and passed."),
    "alignment_not_checked": (
        "The second pass of this strip could not be checked for lining up "
        "with the first one: its patches hardly differ. The other checks "
        "were made and passed."),
}

#: what a hand strip's failed pass means on the instrument path: both
#: passes again (the helper's cq_dd_strip; provisional for the first Beta)
_BOTH_AGAIN = (
    "Read this strip once more, both passes: the first pass with the lamp "
    "as usual, then the second pass with the UV light right after it, "
    "without lifting the instrument. For now ChromIQ always reads the two "
    "passes of a strip together, so the first pass is read again too.")

#: id -> draft English sentence (for the UI step; not shown by this package)
REASONS: "dict[str, str]" = {
    "no_dual_calibration": (
        "This calibration was made for single scans, so it did not read the "
        "white tile with the UV light, and ChromIQ cannot work out M1 and M2 "
        "from it. M0 is not affected. Calibrate again with dual scan "
        "switched on: the calibration and the reading must be made in the "
        "same mode and at the same exposure."),
    "uv_tile_dark": (
        "During the calibration the UV light did not seem to light: the "
        "white tile gave back almost none of its light. ChromIQ does not "
        "work out M1 and M2 from this calibration. M0 is not affected. "
        "Calibrate again; if it happens again, the instrument's UV light "
        "may need a service."),
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
    # The pass refusals below: on the instrument path (helper, a hand strip)
    # a failed pass makes the strip a misread and BOTH passes are read again
    # (provisional rule for the first Beta, docs/design/i1pro2_dual_scan.md),
    # so every sentence says that, through _BOTH_AGAIN.
    "uv_pass_missing": (
        "The second pass (UV light) of this strip is missing or could not be "
        "read, so M1 and M2 cannot be worked out for it. " + _BOTH_AGAIN),
    "uv_pass_count": (
        "The second pass (UV light) does not hold the same number of "
        "patches as the first pass (lamp), so ChromIQ cannot tell which UV "
        "reading belongs to which patch. " + _BOTH_AGAIN),
    "uv_pass_short": (
        "The second pass (UV light) did not cover the whole strip. Make sure "
        "it runs over every patch, from the first to the last. " + _BOTH_AGAIN),
    "uv_pass_too_fast": (
        "The second pass (UV light) was read in a way that left too few "
        "readings per patch: move a little slower. " + _BOTH_AGAIN),
    "uv_pass_too_long": (
        "The second pass (UV light) took too long: it gave more than 4000 "
        "readings (about 20 seconds), more than ChromIQ can line up with the "
        "ruler, so none of it is used. Move a little faster, at an even "
        "speed. " + _BOTH_AGAIN),
    "uv_pass_stalled": (
        "The second pass (UV light) stopped or jumped part of the way along "
        "the strip, so some patches have no reading. Move at an even speed. "
        + _BOTH_AGAIN),
    "uv_pass_wrong_strip": (
        "The second pass (UV light) does not seem to belong to this strip: "
        "its readings do not follow the first pass. Perhaps it was read over "
        "the next row, or the instrument was set down one patch further "
        "along. " + _BOTH_AGAIN),
    "uv_pass_no_uv_light": (
        "The second pass (UV light) brought back almost no light from this "
        "strip: either the UV light did not light, or the pass was read over "
        "a much darker strip than the first pass. " + _BOTH_AGAIN),
    "uv_pass_misaligned": (
        "The second pass (UV light) does not line up with the first pass: "
        "the instrument was probably lifted or moved off the ruler between "
        "the two passes. " + _BOTH_AGAIN),
    "lamp_pass_changed": (
        "The first pass of this strip was read again, and the second pass "
        "taken earlier does not fit it any more. Read the second pass "
        "again too."),
    "dual_needs_ruler": (
        "A dual scan by hand needs the instrument's position ruler to match "
        "the two passes patch by patch, and the ruler cannot be used for the "
        "rest of this measurement: it gave no usable positions, or a second "
        "pass was left unread, so the ruler could not start again for the "
        "next strip. ChromIQ therefore stops working out M1 and M2 for this "
        "measurement; M0 goes on as always."),
    "uv_spot_failed": (
        "The reading of this patch with the UV light failed, so M1 and M2 "
        "cannot be worked out for it. Read the patch again: ChromIQ reads it "
        "with the lamp and then with the UV light in one go, so both "
        "readings are made again."),
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
    "mixed_factor": (
        "This measurement was started with another factor for M1 and M2, or "
        "with another white reference, than the one in use now. Readings "
        "made with two factors must not share one file, so continue it with "
        "the factor and white reference it was started with, or start a new "
        "measurement."),
    "dual_high_resolution": (
        "A dual scan is not available in high resolution mode: the "
        "instrument's factory data for M1 and M2 is given only at 10 nm "
        "steps. Switch high resolution off for a dual scan, or measure M0 "
        "in high resolution."),
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
    "refine_conditions_swapped": (
        "In the i1Profiler file M2 is brighter than M0 in the blue, which a "
        "paper never does: the file's M1 and M2 (or M0 and M2) seem to be "
        "swapped. Save the file again from i1Profiler with each condition "
        "in its own place."),
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
