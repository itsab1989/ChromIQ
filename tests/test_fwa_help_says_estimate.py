"""The FWA option's help names it for what it is: an ESTIMATE from M0.

ArgyllCMS's brightener compensation (``colprof`` / ``profcheck -f``) takes
ordinary readings made under the instrument's own lamp (M0) and the paper
white, and estimates from a model how the print looks under another light:
with D50 the light of condition M1, with D50M2 that of M2. Nothing is
measured under either light (the dual scan study, 2026-11-15, stage 1). So:

* both tabs show the same help paragraphs, built in ``workflow.fwa_gate``,
  and say "estimate", "M0" and "not a measurement";
* the help says when it helps and when it does little or nothing;
* no number: the study's 0.17 / 0.76 dE00 were measured on one i1Pro 3 on one
  paper, and a tooltip would read them as a promise (see the comment above
  ``_fwa_help_intro``);
* nothing on a ``-f`` path records a measurement condition, so the option can
  never turn a file into "M1".
"""
from __future__ import annotations

import inspect
import re

from workflow import fwa_gate


def test_both_helps_say_it_is_an_estimate_from_m0_readings():
    for text in (fwa_gate.fwa_help_build(), fwa_gate.fwa_help_check()):
        assert "estimate" in text
        assert "(measurement condition M0)" in text
        assert "not a measurement taken under that light" in text
        assert "never records it as M1 or M2" in text
        assert "D50" in text and "M1" in text and "D50M2" in text


def test_the_two_helps_differ_only_in_what_the_option_does_there():
    build = fwa_gate.fwa_help_build().split("\n\n")
    check = fwa_gate.fwa_help_check().split("\n\n")
    assert len(build) == len(check)
    differing = [i for i, (a, b) in enumerate(zip(build, check)) if a != b]
    assert differing == [1]
    assert "builds the profile for that light" in build[1]
    assert "compares the profile with that estimate" in check[1]
    assert "Use the same setting as when the profile was built" in check[1]


def test_the_help_says_when_it_helps_and_when_it_does_nothing():
    text = fwa_gate.fwa_help_build()
    assert "**When it helps:**" in text
    assert "**When it does little or nothing:**" in text
    assert "papers without brighteners" in text


def test_the_help_quotes_no_accuracy_figure():
    for text in (fwa_gate.fwa_help_build(), fwa_gate.fwa_help_check()):
        assert not re.search(r"\d+[.,]\d+", text), text
        assert "dE" not in text and "ΔE" not in text


def test_no_em_dash_in_the_help():
    for text in (fwa_gate.fwa_help_build(), fwa_gate.fwa_help_check()):
        assert "—" not in text


def test_every_fwa_help_button_uses_the_shared_text():
    from ui.tabs import tab_check_refine, tab_profile
    prof = inspect.getsource(tab_profile)
    check = inspect.getsource(tab_check_refine)
    assert prof.count("fwa_help_build()") == 2       # manual + guided
    assert check.count("fwa_help_check()") == 2      # guided + manual
    for src in (prof, check):
        assert "Compensates for Fluorescent Whitening Agents" not in src
        assert "Some papers contain optical brighteners" not in src


def test_no_fwa_path_records_a_measurement_condition():
    """``-f`` changes the numbers a profile or a check is computed from; it
    never stamps the measurement. The builders and the check runner do not
    call ``record_condition`` or name the keyword at all."""
    from workflow import engine_builder, profcheck_runner, profile_builder
    for mod in (profile_builder, engine_builder, profcheck_runner):
        src = inspect.getsource(mod)
        assert "record_condition" not in src, mod.__name__
        assert "MEASUREMENT_CONDITION" not in src, mod.__name__
    # The gate only READS the header; it writes no file at all.
    gate = inspect.getsource(fwa_gate)
    assert "record_condition" not in gate
    assert "write_text" not in gate and "write_bytes" not in gate
