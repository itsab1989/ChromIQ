"""Target-name hygiene + colprof output-path resolution.

Covers the "extension in the target name" failure mode: a chart name that
carries a file extension (e.g. a pasted ".icm" profile name) is reused as the
working-folder name and the stem of every generated file, producing
"<name>.icm.ti3"; colprof then writes "<name>.icm.icc", which the Build-Profile
step previously looked for under the wrong name and reported as a phantom
"Profile file was not created".

Two fixes are exercised here:
  1. FileManager strips known work-file extensions from the target name.
  2. ProfileBuilder.expected_icc_path finds colprof's actual (appended) output.
"""
from __future__ import annotations

import pytest

from core.file_manager import FileManager
from workflow.profile_builder import ProfileBuilder, ProfileParams


class _StubSettings:
    def get(self, key, default=None):
        return "" if default is None else default


class _StubRunner:
    def run(self, *a, **k):
        pass


# ---------------------------------------------------------------------------
# 1. Source guard — FileManager
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("chart.icm", "chart"),
    ("chart.icc", "chart"),
    ("chart.tif", "chart"),
    ("chart.TI3", "chart"),                                # case-insensitive
    ("My_Target.icm.ti3", "My_Target"),                   # stacked extensions
    ("Action_optimized_target.icm", "Action_optimized_target"),
    ("  spaced.icm  ", "spaced"),                          # trimmed
    ("plain_name", "plain_name"),                          # untouched
    ("Pro.1000", "Pro.1000"),                              # non-extension dot kept
    ("v2.icm.report", "v2.icm.report"),                    # ext not trailing → kept
])
def test_strip_workfile_ext(raw, expected):
    assert FileManager.strip_workfile_ext(raw) == expected


def test_set_target_name_strips_extension():
    fm = FileManager(_StubSettings())
    fm.set_target_name("Action_optimized_target.icm")
    assert fm.get_target_name() == "Action_optimized_target"
    # the working folder no longer carries the stray ".icm"
    assert fm.working_dir().name == "Action_optimized_target"


def test_set_target_name_strips_stacked_extension():
    fm = FileManager(_StubSettings())
    fm.set_target_name("My_Target.icm.ti3")
    assert fm.get_target_name() == "My_Target"


def test_set_target_name_extension_only_falls_back_to_auto():
    fm = FileManager(_StubSettings())
    fm.set_target_name(".icm")
    # nothing left after stripping → auto name, never an empty folder name
    assert fm.get_target_name()
    assert not fm.get_target_name().endswith(".icm")


# ---------------------------------------------------------------------------
# 2. Sink defence — ProfileBuilder.expected_icc_path
# ---------------------------------------------------------------------------

def _builder() -> ProfileBuilder:
    return ProfileBuilder(_StubRunner())


def test_expected_icc_path_finds_appended_output(tmp_path):
    # Contaminated case: the .ti3 still carries a ".icm" stem, so colprof
    # (which appends) writes "<name>.icm.icc", not "<name>.icc".
    ti3 = tmp_path / "chart.icm.ti3"
    ti3.write_text("ti3", encoding="utf-8")
    written = tmp_path / "chart.icm.icc"
    written.write_bytes(b"x" * 2000)
    got = _builder().expected_icc_path(ProfileParams(ti3_path=ti3))
    assert got == written


def test_expected_icc_path_plain_name(tmp_path):
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("ti3", encoding="utf-8")
    icc = tmp_path / "chart.icc"
    icc.write_bytes(b"x" * 2000)
    assert _builder().expected_icc_path(ProfileParams(ti3_path=ti3)) == icc


def test_expected_icc_path_icm_output(tmp_path):
    # ArgyllCMS colprof's default output extension is ".icm" on Windows; a clean
    # session must still be recognised as success when only ".icm" is written.
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("ti3", encoding="utf-8")
    icm = tmp_path / "chart.icm"
    icm.write_bytes(b"x" * 2000)
    assert _builder().expected_icc_path(ProfileParams(ti3_path=ti3)) == icm


def test_expected_icc_path_finds_appended_icm_output(tmp_path):
    # Contaminated name + Windows ".icm" default → colprof writes "<name>.icm.icm".
    ti3 = tmp_path / "chart.icm.ti3"
    ti3.write_text("ti3", encoding="utf-8")
    written = tmp_path / "chart.icm.icm"
    written.write_bytes(b"x" * 2000)
    assert _builder().expected_icc_path(ProfileParams(ti3_path=ti3)) == written


def test_expected_icc_path_fallback_when_missing(tmp_path):
    ti3 = tmp_path / "chart.icm.ti3"
    ti3.write_text("ti3", encoding="utf-8")
    # Nothing written yet → returns colprof's appended .icc name.
    got = _builder().expected_icc_path(ProfileParams(ti3_path=ti3))
    assert got == tmp_path / "chart.icm.icc"
