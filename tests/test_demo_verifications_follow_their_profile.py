"""The demo projects' verification dates come after the profile they verify.

`scripts/make_demo_projects.py` builds each profile NOW (colprof), but its
verification dates are history, 2026-01 to 2026-06, so every demo date was
older than its own profile: a state no real project can reach, since a
verification measures a profile that already exists (challenge of
2026-10-03, §2, "Demo projects"). The generator dates the profile back to
before its first verification (`_backdate_profile`) instead of moving the
dates up to the build, so Demo-Verify-History still trends over months.
"""
from __future__ import annotations

import struct
from datetime import datetime, timezone

from core.file_manager import Project


def _icc_built(icc) -> datetime:
    """The later of the profile's file time and its ICC header date (UTC)."""
    head = icc.read_bytes()[24:36]
    y, mo, d, h, mi, s = struct.unpack(">6H", head)
    header = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc) \
        .astimezone().replace(tzinfo=None)
    mtime = datetime.fromtimestamp(icc.stat().st_mtime)
    return max(header, mtime)


def _dates_after_profile(root, run_id: str, expect: int) -> None:
    run = Project.load(root).run(run_id)
    icc = run.profile_icc
    assert icc.is_file(), "the demo has no profile to verify"
    built = _icc_built(icc)
    dates = run.verifications()
    assert len(dates) == expect
    for v in dates:
        when = datetime.strptime(v.id, "%Y-%m-%d_%H%M%S")
        assert when > built, (
            f"{root.name}/{run_id}: verification {v.id} is older than the "
            f"profile it verifies (built {built:%Y-%m-%d %H:%M:%S})")


def test_demo_full_rgb_verifications_follow_the_profile(demo_project):
    _dates_after_profile(demo_project("Demo-Full-RGB"), "run2", 2)


def test_demo_verify_history_follows_the_profile(demo_project):
    _dates_after_profile(demo_project("Demo-Verify-History"), "run1", 5)


def test_demo_verify_history_still_spans_months(demo_project):
    """The trend the demo exists for: five checks a printer drifted across,
    not five checks a minute apart."""
    run = Project.load(demo_project("Demo-Verify-History")).run("run1")
    whens = sorted(datetime.strptime(v.id, "%Y-%m-%d_%H%M%S")
                   for v in run.verifications())
    assert (whens[-1] - whens[0]).days >= 300


def test_the_backdated_profile_keeps_a_valid_profile_id(demo_project):
    """A header date is part of what a v4 profile ID hashes, so moving it
    must recompute the ID, or the profile reads as corrupt."""
    from core.icc_text import _profile_id
    icc = Project.load(demo_project("Demo-Verify-History")).run("run1").profile_icc
    data = icc.read_bytes()
    if data[84:100] != b"\0" * 16:
        assert data[84:100] == _profile_id(data)
