"""b15 item 9 (Knut #182 6065640028, approved by Basti): with run type
Verification, the Verification box opens on the run's LATEST dated
verification, and on "New verification" only when the run has none. It
applies when the run changes, when the run type changes, and on reopening a
project (which selects the run). A user's own pick of "New verification" is
never overridden."""
from __future__ import annotations

import pytest

from core.measurement_target import RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION


@pytest.fixture()
def ctl(qapp):
    from ui.measurement_target_bar import MeasurementTargetController
    c = MeasurementTargetController(file_mgr=None)
    dates = {"run1": ["2026-10-01_100000", "2026-10-06_154750"], "run2": []}
    c.verification_ids = lambda run_id: list(dates.get(run_id, []))
    return c


def test_a_run_chosen_on_verification_opens_on_its_latest(ctl):
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    assert ctl.target.verification_id == "2026-10-06_154750"


def test_a_run_without_verifications_opens_on_new(ctl):
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run2")
    assert ctl.target.verification_id == ""


def test_switching_the_run_type_to_verification_opens_on_the_latest(ctl):
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run1")
    assert ctl.target.verification_id == ""
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert ctl.target.verification_id == "2026-10-06_154750"


def test_a_users_new_verification_is_kept(ctl):
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    ctl.set_verification_id("")            # the user picks "New verification"
    assert ctl.target.verification_id == ""


def test_the_default_is_asked_of_the_run(qapp, ctl):
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    ctl.set_profile_run("run1")
    assert ctl.default_verification_id("run1") == "2026-10-06_154750"
