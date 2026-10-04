"""The local macOS gate measures chart text with Pillow's RAQM engine, so the
frozen RAQM numbers are the ones it checks (review of CI round 2).

`tests/helpers/text_layout.pillow_lays_out_with_raqm()` lets four tests pick a
BASIC-layout expectation where Pillow has no FriBiDi (the GitHub runners,
Windows). That choice is made by the MACHINE, at run time, so on the Mac the
numbers were frozen on it would switch silently to the BASIC values the day
Homebrew's libfribidi went missing, and the gate would go on reading green
while checking different numbers. This makes that day loud instead.

Skipped on the CI runners (GitHub Actions sets ``CI``), where BASIC is the
expected engine, and off macOS.
"""
from __future__ import annotations

import os
import sys

import pytest


@pytest.mark.skipif(sys.platform != "darwin" or bool(os.environ.get("CI")),
                    reason=("the frozen RAQM text measurements are required on "
                            "the local macOS gate only; CI runners and other "
                            "systems lay text out with Pillow's BASIC engine"))
def test_pillow_lays_text_out_with_raqm_on_the_mac_gate():
    from tests.helpers.text_layout import pillow_lays_out_with_raqm
    assert pillow_lays_out_with_raqm(), (
        "Pillow lays text out with its BASIC engine on this Mac (no FriBiDi "
        "found; Homebrew's libfribidi provides it: `brew install fribidi`). "
        "The frozen chart-text numbers were measured with RAQM, so the "
        "suite would now check the CI runners' BASIC values instead "
        "(tests/helpers/text_layout.py, REAL_BUGS RB-6)")
