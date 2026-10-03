"""Which verification files belong to an earlier profile (#182, UMM §6f).

Knut, 5964384250 Q1: a rebuild archives the profile only, and choosing
Verification afterwards offers to archive the old verification runs. The
decision is `workflow/verification_profile_match.py`; these tests take its
rules one at a time, each alone enough to flag a date, and the cases that
must NOT flag.

Every time below is placed relative to the profile's own header time, read
the way the module reads it, so the tests hold in any time zone.
"""
from __future__ import annotations

import json
import struct
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.cgats_date import created_stamp
from core.file_manager import Run
from workflow import verification_profile_match as VPM

#: The profile header time used throughout, in UTC (Knut's run2).
HEADER_UTC = datetime(2026, 10, 2, 22, 39, 18)


def write_icc(path: Path, utc: "datetime | None") -> Path:
    """A minimal ICC file whose header says *utc* (None: no date)."""
    b = bytearray(132)
    struct.pack_into(">I", b, 0, 132)
    b[36:40] = b"acsp"
    if utc is not None:
        struct.pack_into(">6H", b, 24, utc.year, utc.month, utc.day,
                         utc.hour, utc.minute, utc.second)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(b))
    return path


def local(utc: datetime) -> datetime:
    return utc.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


P = local(HEADER_UTC)


def vid(when: datetime) -> str:
    return when.strftime("%Y-%m-%d_%H%M%S")


def reference(path: Path, created: str) -> Path:
    """A colorimetric reference (a FROM PROFILE GAMUT chart's marker)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "CTI3\n\n"
        'DESCRIPTOR "ChromIQ colorimetric verification reference"\n'
        f'CREATED "{created}"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B LAB_L LAB_A LAB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100 95 0 0\nEND_DATA\n",
        encoding="utf-8")
    return path


@pytest.fixture
def run(tmp_path):
    r = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    r.verifications_dir.mkdir(parents=True)
    write_icc(r.profile_icc, HEADER_UTC)
    return r


def measured(run, when: datetime, *, ti3=True) -> "object":
    v = run.verification(vid(when))
    v.ensure_dir()
    if ti3:
        v.measurement_ti3.write_text("CTI3\nBEGIN_DATA\nEND_DATA\n",
                                     encoding="utf-8")
    return v


def print_record(path: Path, printed_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"colour": "raw",
                                "printed_at": printed_at.isoformat()}),
                    encoding="utf-8")


def gamut_chart(run, created: str) -> None:
    run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")
    reference(run.verifications_dir / f"{run.verify_stem}-reference.ti3",
              created)


# ---------------------------------------------------------------------------
# the anchor
# ---------------------------------------------------------------------------
def test_the_header_is_read_as_utc_and_given_in_local_time(run):
    assert VPM.profile_created(run.profile_icc) == P


def test_no_profile_flags_nothing(tmp_path):
    r = Run.for_dir(tmp_path / "P" / "runs" / "run1")
    r.verifications_dir.mkdir(parents=True)
    measured(r, datetime(2020, 1, 1, 10, 0, 0))
    items = VPM.earlier_profile_items(r)
    assert items.variant == "" and items.dates == ()


def test_a_header_without_a_date_flags_nothing(run):
    write_icc(run.profile_icc, None)
    measured(run, P - timedelta(days=30))
    assert VPM.earlier_profile_items(run).variant == ""


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="needs time.tzset")
def test_the_offset_is_the_one_valid_on_that_date(monkeypatch, tmp_path):
    """A summer build read in winter is not an hour off (CEST vs CET)."""
    monkeypatch.setenv("TZ", "Europe/Berlin")
    time.tzset()
    try:
        summer = write_icc(tmp_path / "s.icc", datetime(2026, 7, 1, 12, 0, 0))
        winter = write_icc(tmp_path / "w.icc", datetime(2026, 1, 9, 10, 0, 0))
        assert VPM.profile_created(summer) == datetime(2026, 7, 1, 14, 0, 0)
        assert VPM.profile_created(winter) == datetime(2026, 1, 9, 11, 0, 0)
    finally:
        monkeypatch.undo()
        time.tzset()


# ---------------------------------------------------------------------------
# the three rules, each alone
# ---------------------------------------------------------------------------
def test_a_folder_named_before_the_profile_is_flagged(run):
    v = measured(run, P - timedelta(minutes=5))
    items = VPM.earlier_profile_items(run)
    assert items.dates == (v.id,)
    assert items.variant == "B"


def test_a_snapshot_chart_made_before_the_profile_is_flagged(run):
    """Knut's run2 2026-10-03_005807: measured after the build, from a gamut
    chart the earlier profile chose."""
    v = measured(run, P + timedelta(minutes=20))
    reference(v.dir / "chart" / f"{v.stem}-reference.ti3",
              created_stamp(P - timedelta(hours=3)))
    assert VPM.earlier_profile_items(run).dates == (v.id,)


@pytest.mark.parametrize("where", ["beside", "chart"])
def test_its_own_print_record_before_the_profile_flags_it(run, where):
    v = measured(run, P + timedelta(minutes=20))
    folder = v.dir if where == "beside" else v.dir / "chart"
    print_record(folder / f"{v.stem}.print.json", P - timedelta(hours=1))
    assert VPM.earlier_profile_items(run).dates == (v.id,)


def test_the_shared_print_record_never_flags_a_date(run):
    """It describes the chart's LAST print, not this sheet's."""
    v = measured(run, P + timedelta(minutes=20))
    print_record(run.verifications_dir / f"{v.stem}.print.json",
                 P - timedelta(hours=1))
    assert VPM.earlier_profile_items(run).dates == ()


def test_a_later_date_with_no_evidence_is_not_flagged(run):
    v = measured(run, P + timedelta(minutes=20))
    reference(v.dir / "chart" / f"{v.stem}-reference.ti3",
              created_stamp(P + timedelta(minutes=10)))
    print_record(v.dir / f"{v.stem}.print.json", P + timedelta(minutes=15))
    assert VPM.earlier_profile_items(run).variant == ""


def test_an_unmeasured_folder_is_never_flagged(run):
    measured(run, P - timedelta(days=2), ti3=False)
    assert VPM.earlier_profile_items(run).dates == ()


# ---------------------------------------------------------------------------
# the live chart
# ---------------------------------------------------------------------------
def test_a_gamut_chart_made_before_the_profile_is_stale(run):
    gamut_chart(run, created_stamp(P - timedelta(hours=3)))
    items = VPM.earlier_profile_items(run)
    assert items.chart_stale and items.variant == "C"
    assert items.chart_when == P.replace(microsecond=0) - timedelta(hours=3)


def test_a_gamut_chart_made_after_the_profile_is_not(run):
    gamut_chart(run, created_stamp(P + timedelta(minutes=1)))
    assert VPM.earlier_profile_items(run).variant == ""


def test_an_ordinary_chart_is_never_stale(run):
    run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")
    measured(run, P - timedelta(days=1))
    items = VPM.earlier_profile_items(run)
    assert not items.chart_stale and items.variant == "B"


def test_a_german_created_line_is_read(run):
    gamut_chart(run, "Fr. Okt. 02 10:00:00 2026")
    assert VPM.earlier_profile_items(run).chart_stale


def test_an_unreadable_created_line_is_not_stale(run):
    gamut_chart(run, "garbage")
    assert VPM.earlier_profile_items(run).variant == ""


def test_stale_dates_and_a_stale_gamut_chart_are_text_a(run):
    measured(run, P - timedelta(days=1))
    gamut_chart(run, created_stamp(P - timedelta(days=2)))
    assert VPM.earlier_profile_items(run).variant == "A"


# ---------------------------------------------------------------------------
# which profile is current
# ---------------------------------------------------------------------------
def test_a_refinement_merge_makes_merged_icc_current(run):
    """The first merge replaces the profile: dates before it are flagged."""
    v = measured(run, P + timedelta(hours=1))
    write_icc(run.merged_icc, HEADER_UTC + timedelta(hours=2))
    assert VPM.earlier_profile_items(run).dates == (v.id,)


def test_a_build_without_a_merge_leaves_merged_icc_current(run):
    """merged.icc still outranks a newer plain profile, as it does for Print
    and the prediction, so nothing changed and nothing is flagged."""
    write_icc(run.merged_icc, HEADER_UTC)
    write_icc(run.profile_icc, HEADER_UTC + timedelta(hours=3))
    measured(run, P + timedelta(hours=1))
    assert VPM.earlier_profile_items(run).dates == ()


# ---------------------------------------------------------------------------
# the reports that travel with the dates
# ---------------------------------------------------------------------------
def _document(run, name: str, dates) -> Path:
    folder = run.verifications_dir / "reports"
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text(json.dumps({"document": {
        "id": name, "measurements": [
            {"dir": str(run.verification(d).dir)} for d in dates]}}),
        encoding="utf-8")
    return path


def test_a_document_of_moving_dates_only_moves(run):
    a = measured(run, P - timedelta(days=2))
    b = measured(run, P - timedelta(days=1))
    doc = _document(run, "report_1.json", [a.id, b.id])
    assert VPM.earlier_profile_items(run).documents == (doc,)


def test_a_document_that_also_covers_a_date_that_stays_does_not(run):
    a = measured(run, P - timedelta(days=2))
    c = measured(run, P + timedelta(days=1))
    _document(run, "report_1.json", [a.id, c.id])
    items = VPM.earlier_profile_items(run)
    assert items.dates == (a.id,) and items.documents == ()


def test_a_date_archived_earlier_does_not_hold_a_document_back(run):
    """Covered dates no longer at the top level of verifications/ (moved by an
    earlier archive) are not "staying"."""
    a = measured(run, P - timedelta(days=2))
    gone = run.verification(vid(P - timedelta(days=9)))
    doc = _document(run, "report_1.json", [a.id, gone.id])
    assert VPM.earlier_profile_items(run).documents == (doc,)


def test_a_document_covering_no_moving_date_stays(run):
    measured(run, P - timedelta(days=2))
    c = measured(run, P + timedelta(days=1))
    _document(run, "report_1.json", [c.id])
    assert VPM.earlier_profile_items(run).documents == ()


# ---------------------------------------------------------------------------
# Knut's run2, as measured on disk
# ---------------------------------------------------------------------------
def test_a_run_shaped_like_knuts_run2_is_text_a_with_one_date(tmp_path):
    """Header 2026-10-02 22:39:18 UTC; one date measured after it, from a
    gamut chart CREATED 21:27:02 and printed 21:27:45 local, on 2026-10-02."""
    r = Run.for_dir(tmp_path / "test" / "runs" / "run2")
    r.verifications_dir.mkdir(parents=True)
    write_icc(r.profile_icc, HEADER_UTC)
    p = VPM.profile_created(r.profile_icc)
    v = measured(r, p + timedelta(minutes=18, seconds=49))
    reference(v.dir / "chart" / f"{v.stem}-reference.ti3",
              "Fri Oct 02 21:27:02 2026")
    print_record(v.dir / "chart" / f"{v.stem}.print.json",
                 datetime(2026, 10, 2, 21, 27, 45))
    gamut_chart(r, "Fri Oct 02 21:27:02 2026")
    items = VPM.earlier_profile_items(r)
    assert items.variant == "A" and items.dates == (v.id,)


def test_it_never_raises(tmp_path):
    class Broken:
        def built_profile_icc(self):
            raise OSError("gone")
    assert VPM.earlier_profile_items(Broken()).variant == ""
