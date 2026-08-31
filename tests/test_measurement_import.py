"""§I.9/§I.10 — filing a measurement made elsewhere into a run.

The rules under test, all from the amended §I:
  * fewer readings than the chart has patches is FILED, with both counts;
  * more readings is REFUSED — that is a different chart, not a partial one;
  * a measurement of the wrong chart is REFUSED and never re-paired.
"""
import pathlib
import tempfile

import pytest

from workflow.measurement_import import assess

_HDR = ("CTI3\n\nKEYWORD \"SAMPLE_LOC\"\nNUMBER_OF_FIELDS 7\n"
        "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B "
        "XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n")


def _ti3(path, rows):
    body = "".join(f"{i} \"A{i}\" {r} {g} {b} {r*0.9:.4f} {g*1.0:.4f} "
                   f"{b*1.1:.4f}\n" for i, (r, g, b) in enumerate(rows, 1))
    path.write_text(_HDR + f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
                    + body + "END_DATA\n")
    return path


def _ti2(path, rows):
    """A chart the way printtarg writes one — device values AND the expected
    XYZ. An earlier version of this helper wrote device values only, which no
    real chart does, and the identity check then could not read it at all."""
    body = "".join(f"{i} \"A{i}\" {r} {g} {b} {r*0.9:.4f} {g*1.0:.4f} "
                   f"{b*1.1:.4f}\n" for i, (r, g, b) in enumerate(rows, 1))
    path.write_text("CTI2\n\nKEYWORD \"SAMPLE_LOC\"\nNUMBER_OF_FIELDS 8\n"
                    "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G "
                    "RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n"
                    f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + body
                    + "END_DATA\n")
    return path


@pytest.fixture()
def work():
    return pathlib.Path(tempfile.mkdtemp())


_CHART = [(100, 100, 100), (100, 0, 0), (0, 100, 0), (0, 0, 100),
          (50, 50, 50), (0, 0, 0)]


def test_a_matching_measurement_is_filed(work):
    v = assess(_ti3(work / "m.ti3", _CHART), _ti2(work / "c.ti2", _CHART))
    assert v.ok and not v.partial, v.reason


def test_fewer_readings_is_a_partial_and_carries_both_counts(work):
    """§I.10: filed, not refused. ChromIQ already builds a profile from a
    partial measurement made here, and refusing the same data on import would
    lock a person out of their own file."""
    v = assess(_ti3(work / "m.ti3", _CHART[:4]), _ti2(work / "c.ti2", _CHART))
    assert v.ok, v.reason
    assert v.partial
    assert (v.n_measured, v.n_chart) == (4, 6), (
        "both counts must travel, or the window cannot state them")


def test_more_readings_than_patches_is_refused_as_a_different_chart(work):
    """Not a partial — a measurement of something else. Real hazard: among the
    owner's own charts, Red River A4 (2060 patches) is a strict subset of
    Letter (2064)."""
    v = assess(_ti3(work / "m.ti3", _CHART + [(10, 10, 10)]),
               _ti2(work / "c.ti2", _CHART))
    assert not v.ok
    assert "different chart" in v.reason


def test_a_measurement_of_another_chart_is_refused_not_repaired(work):
    """THE RULE THIS MODULE EXISTS FOR. A shuffled or foreign measurement is
    refused. It is never re-paired by matching device values: the check that
    would have to validate such a repair is the same comparison the repair
    optimises, so it reports "verified" whether the repair is right or wrong."""
    other = [(0, 0, 0), (5, 5, 5), (9, 9, 9), (12, 12, 12), (20, 20, 20),
             (30, 30, 30)]
    v = assess(_ti3(work / "m.ti3", other), _ti2(work / "c.ti2", _CHART))
    assert not v.ok, "a measurement of a different chart was accepted"


def test_a_measurement_out_of_the_chart_s_order_is_refused_not_re_paired(work):
    """§I.9's decision, asserted from the VERDICT rather than the vocabulary.

    This used to grep the module for "argmin", "argsort", "cdist" and
    "linear_sum_assignment" — and a hand-written nearest-neighbour loop, using
    none of those four words, passed it. What §I.9 forbids is the BEHAVIOUR:
    a measurement whose readings do not line up with the chart is refused and
    said so, never quietly re-paired into looking correct.

    Held on measured evidence: a tolerant match can hand a reading to a patch
    16.24 dE00 away.
    """
    chart = _ti2(work / "c.ti2", _CHART)
    shuffled = _ti3(work / "m.ti3", list(reversed(_CHART)))

    v = assess(shuffled, chart)
    assert not v.ok, (
        "a measurement in a different order was accepted — either the "
        "readings were re-paired, or the check no longer looks at colour")
    assert v.reason, "it was refused without saying why"
    # …and the same readings IN THE CHART'S ORDER are fine, so the refusal is
    # about the pairing and not about the file.
    assert assess(_ti3(work / "ok.ti3", _CHART), chart).ok


def test_one_reading_in_the_wrong_place_is_still_refused(work):
    """The weaker case: a single swap, which a repair would silently undo."""
    rows = list(_CHART)
    rows[1], rows[2] = rows[2], rows[1]
    v = assess(_ti3(work / "m.ti3", rows), _ti2(work / "c.ti2", _CHART))
    assert not v.ok, (
        "two readings exchanged places and the file was accepted anyway")


def test_an_unreadable_chart_does_not_refuse_every_measurement(work):
    """0 means "do not judge by count", not "the chart has no patches"."""
    v = assess(_ti3(work / "m.ti3", _CHART), work / "missing.ti2")
    assert v.ok, v.reason
    assert not v.partial


def test_a_partial_is_still_checked_against_the_chart(work):
    """A partial is FILED, but it is still a measurement of THIS chart or not.

    Returning early on "fewer readings" skipped the identity check entirely, so
    a 240-patch measurement of a different chart was filed into a 399-patch run
    and described to the person as "part of the chart was not measured".
    """
    foreign = [(0, 0, 0), (5, 5, 5), (9, 9, 9)]        # nothing like _CHART
    v = assess(_ti3(work / "m.ti3", foreign), _ti2(work / "c.ti2", _CHART))
    assert not v.ok, (
        "a short measurement of a DIFFERENT chart was accepted as a partial")


def test_a_genuine_partial_of_the_right_chart_is_still_filed(work):
    """…and the check must not refuse a real partial."""
    v = assess(_ti3(work / "m.ti3", _CHART[:4]), _ti2(work / "c.ti2", _CHART))
    assert v.ok and v.partial and (v.n_measured, v.n_chart) == (4, 6), v.reason
