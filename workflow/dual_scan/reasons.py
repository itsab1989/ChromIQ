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
    # The calibration and session-level sentences below say what happened
    # and nothing about what to do: they are used both in "Calibration
    # Complete" (M-DUAL-CAL-REFUSED, which adds "calibrate again") and in
    # M-DUAL-ENDED (which says that M0 goes on), and an action inside them
    # contradicted the one around them (review of 2026-11-18, M-3).
    "no_dual_calibration": (
        "This calibration has no reading of the white tile with the UV "
        "light (the UV reading of the tile did not succeed, or the "
        "calibration was made without the dual scan), so ChromIQ cannot work "
        "out M1 and M2 from it. M0 is not affected."),
    "uv_tile_dark": (
        "During the calibration the UV light did not seem to light: the "
        "white tile gave back almost none of its light. ChromIQ does not "
        "work out M1 and M2 from this calibration. M0 is not affected. If "
        "this happens again after a new calibration, the instrument's UV "
        "light may need to be checked by a service."),
    "calibration_mismatch": (
        "The calibration was made at another exposure than this reading, so "
        "it does not fit the reading."),
    "no_uv_tables": (
        "This instrument does not hold the factory data needed to work out "
        "M1 and M2 (some i1Pro 2 units have no UV light). The instrument "
        "can still measure as always, without the dual scan."),
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
    # fix round of 2026-11-21 (review B1): the passes lined up over the
    # readings that are averaged (cut.py MAX_EDGE_FLATNESS)
    "uv_pass_shifted": (
        "The second pass (UV light) did not line up closely enough with the"
        " first pass at the ends of the patches: on the way back the "
        "instrument's position along the ruler came out a little different,"
        " for example because it was lifted slightly, tilted or pressed "
        "differently. Near the patch edges ChromIQ then cannot be sure "
        "which patch a reading belongs to, so none of this pass is used. " + _BOTH_AGAIN),
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
        "measurement."),
    "uv_spot_failed": (
        "The reading of this patch with the UV light failed, so M1 and M2 "
        "cannot be worked out for it. Read the patch again: ChromIQ reads it "
        "with the lamp and then with the UV light in one go, so both "
        "readings are made again."),
    "no_ruler": (
        "The instrument's position ruler gave no usable positions for the "
        "two passes of this strip, so they cannot be matched patch by patch. "
        + _BOTH_AGAIN),
    "calibration_mode_changed": (
        "The reading mode changed since the last calibration (a dual scan "
        "and a single scan each need their own calibration)."),
    "bad_values": (
        "A reading holds values that are not numbers, so ChromIQ does not "
        "use it for M1 and M2."),
    "bad_scale": (
        "The factor used for M1 and M2 is not a sensible number, so ChromIQ "
        "does not use it."),
    "mixed_scan_kind": (
        "This measurement was started as a dual scan (M0, M1 and M2) and "
        "cannot be continued with single scans, or the other way round: "
        "the readings would not belong together. Continue it the way it "
        "was started, or start a new measurement."),
    # 4.3.54 (issue 217): "mixed" in words true for each case (could_he_tell.txt R1, R2)
    "mixed_new": (
        "This run already holds a measurement that was read with one pass per "
        "strip, and this copy of ChromIQ's reading program cannot start a dual "
        "scan while that file is there. So this measurement is read with one "
        "pass per strip, and only M0 is saved. For M1 and M2, untick “Refine / "
        "resume existing measurement (-r)” and start again: the earlier "
        "measurement is then moved to the run's “old” folder first."),
    "mixed_single_continued": (
        "You are continuing a measurement that was read with one pass per "
        "strip. A dual scan cannot add to it, because its readings and the "
        "new ones would not belong together. For M1 and M2, start a new "
        "measurement: untick “Refine / resume existing measurement (-r)”."),
    "mixed_factor": (
        "This measurement was started with another factor for M1 and M2, or "
        "with another white reference, than the one in use now. Readings "
        "made with two factors must not share one file, so continue it with "
        "the factor and white reference it was started with, or start a new "
        "measurement."),
    "dual_high_resolution": (
        "A dual scan is not available with “High resolution spectral mode "
        "(-H)”: the instrument's factory data for M1 and M2 is given only at "
        "10 nm steps. For a dual scan, switch “High resolution spectral mode "
        "(-H)” off before you start, or measure M0 in high resolution."),
    # Session-level ends the engine can give besides the ones above (review
    # of 2026-11-18, S-4: each had no sentence and was shown as its raw id).
    # The engine's own words: chromiq_dualdev.c (not_available, record,
    # memory, conversion) and chromiq_chartread.c cq_cond_for_session /
    # cq_cond_lose (mode, filter, files, instrument, resume, write, typed).
    "not_available": (
        "This i1Pro 2 does not offer what the dual scan needs, so ChromIQ "
        "does not try the dual scan with it. An OEM i1Pro 2, such as an EFI "
        "ES-2000, may or may not have the UV light (ArgyllCMS names the part "
        "number EO2-XR-UF for the units built without it). The instrument "
        "measures as always, without the dual scan."),
    "record": (
        "ChromIQ lost track of which reading belongs to which patch for M1 "
        "and M2, so it stops working them out for this measurement."),
    "memory": (
        "The computer did not give ChromIQ enough memory to work out M1 and "
        "M2, so it stops working them out for this measurement."),
    "conversion": (
        "The readings for M1 and M2 could not be converted into colour "
        "values, so ChromIQ stops working them out for this measurement."),
    "write": (
        "The files for M1 and M2 could not be saved, so ChromIQ stops "
        "keeping them for this measurement. Check that the disk has free "
        "space and that the project folder can be written to."),
    "resume": (
        "M1 and M2 ended earlier in this measurement: its files for M1 and M2 "
        "no longer belong to its readings, and the strips read since then "
        "have M0 only. So what is read now is M0 only, one pass per strip."),
    "mode": (
        "The dual scan works only for reflective readings of a printed "
        "chart, so this reading gives M0 only."),
    "filter": (
        "A filter choice reached the instrument together with the dual scan, "
        "and the two do not go together, so this reading gives M0 only."),
    "files": (
        "ChromIQ had no folder for the M1 and M2 files of this measurement, "
        "so this reading gives M0 only."),
    "instrument": (
        "The connected instrument is not an i1Pro 2, so the dual scan is not "
        "used: it measures as it would without it."),
    "typed": (
        "A value was typed in by hand, and a typed value has no M1 and M2, so "
        "ChromIQ stops keeping them for this measurement."),
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
