"""4.3.37 review (M7): which strips a measurement is missing, named through
the chart's OWN label scheme.

`workflow/incomplete_measurement.py` took the strip of a location to be its
leading letters ("A12" -> "A"). On ChromIQ's engine charts strips are
numbers and patches letters ("9I"): the window before building a profile
(M-BUILD-INCOMPLETE) then named no strip at all. It now asks the chart's
labels (`labels_for_chart`), as the ruler file does, and keeps the old rule
only as the fallback.
"""
from __future__ import annotations

from workflow.incomplete_measurement import missing_readings


def _write(tmp, name, strip_pat, patch_pat, locs, read, order="STRIP_THEN_PATCH",
           steps=None):
    ti2 = tmp / f"{name}.ti2"
    ti3 = tmp / f"{name}.ti3"
    head = (f'STRIP_INDEX_PATTERN "{strip_pat}"\nPATCH_INDEX_PATTERN "{patch_pat}"\n'
            f'INDEX_ORDER "{order}"\n'
            + (f'STEPS_IN_PASS "{steps}"\n' if steps else ""))
    ti2.write_text(
        "CTI2\n\n" + head + "\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(locs)}\nBEGIN_DATA\n"
        + "".join(f'{i + 1} "{loc}" 50 50 50\n' for i, loc in enumerate(locs))
        + "END_DATA\n", encoding="latin-1")
    rows = [(i + 1, loc) for i, loc in enumerate(locs) if loc in read]
    ti3.write_text(
        "CTI3\n\n" + head + "\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
        + "".join(f'{i} "{loc}" 50 50 50 20 20 20\n' for i, loc in rows)
        + "END_DATA\n", encoding="latin-1")
    return ti3, ti2


def test_number_strips_with_letter_patches(tmp_path):
    locs = [f"{n}{c}" for n in range(1, 13) for c in "ABCDEFGHIJKL"]
    read = [loc for loc in locs if not loc.startswith("9")
            or loc in ("9A", "9B")]               # strip 9 mostly unread
    read = [loc for loc in read if not loc.startswith("10")]
    ti3, ti2 = _write(tmp_path, "engine", "0-9@0-9", "A-Z", locs, set(read),
                      steps=12)
    m = missing_readings(ti3, ti2)
    assert m is not None and m.missing == 10 + 12
    assert [(g.strip, g.missing, g.total) for g in m.strips] == [
        ("9", 10, 12), ("10", 12, 12)]           # in the sheet's order


def test_letter_strips_with_number_patches_as_before(tmp_path):
    locs = [f"{s}{i}" for s in ("A", "B", "C", "AA") for i in range(1, 11)]
    read = {loc for loc in locs if not loc.startswith("B")}
    ti3, ti2 = _write(tmp_path, "classic", "A-Z, A-Z", "0-9,@-9,@-9;1-999",
                      locs, read, steps=10)
    m = missing_readings(ti3, ti2)
    assert [(g.strip, g.missing) for g in m.strips] == [("B", 10)]


def test_patch_then_strip_order_as_an_i1io_sheet_may_print_it(tmp_path):
    """A sheet whose labels put the patch first (INDEX_ORDER
    PATCH_THEN_STRIP, "A1" = patch A of strip 1)."""
    locs = [f"{c}{n}" for n in range(1, 6) for c in "ABCDEFGH"]
    read = {loc for loc in locs if not loc.endswith("3")}
    ti3, ti2 = _write(tmp_path, "pts", "0-9@0-9", "A-Z", locs, read,
                      order="PATCH_THEN_STRIP", steps=8)
    m = missing_readings(ti3, ti2)
    assert [(g.strip, g.missing, g.total) for g in m.strips] == [("3", 8, 8)]


def test_patch_flags_sort_both_label_schemes_in_reading_order():
    from workflow.patch_flags import sorted_locs
    assert sorted_locs(["A10", "B1", "A9", "AA1", "Z3"]) == \
        ["A9", "A10", "B1", "Z3", "AA1"]
    assert sorted_locs(["10A", "9I", "1AA", "1B", "1Z", "2A"]) == \
        ["1B", "1Z", "1AA", "2A", "9I", "10A"]
