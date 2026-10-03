"""The demo projects' verification dates come after the profile they verify.

`scripts/make_demo_projects.py` builds each profile NOW (colprof), but named
its verification dates by hand, in 2026-01 to 2026-06, so every demo date was
older than its own profile: a state no real project can reach, since a
verification measures a profile that already exists, and one that makes every
demo date look like a verification of an earlier profile (challenge of
2026-10-03, §2, "Demo projects").
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
