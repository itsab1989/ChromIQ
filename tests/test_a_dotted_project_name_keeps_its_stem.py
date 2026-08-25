"""A project name containing a dot must not split the run's file stems.

120 of the 130 built-in chart presets suggest a project name with a dot in it —
`…-w10.0mm`, `…-TC9.18-extended-greys-by-Pharmacist`, `…-TC3.00-by-Pharmacist`.
`core/file_manager.py:56` keeps the dot deliberately (`_ILLEGAL` allows `.`), and
`Run` builds every canonical path by string concatenation, so the `.ti1` gets
the full name.

The ChromIQ layout engine did not: `chart.py` derived its stem with
`Path(out_base).with_suffix("")`, and on a dotted name Python reads `.0mm` as
the extension and drops it. The `.ti2`, the TIFFs and `.strips.json` were then
written under a TRUNCATED stem while `Run.chart_ti2` looked for the full one —
so `Run.chart_ti2.exists()` was False, `Run.chart_tiffs()` was empty, Duplicate
Run was greyed out, and chartread was handed a base whose `.ti2` did not exist,
which means **the project could not be measured at all**.

Only the engine path was affected; ArgyllCMS's printtarg appends strings and is
clean.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.stem_paths import artefact, without_ext
from workflow.layout_engine import chart as le_chart  # noqa: F401


#: Real suggested names from the built-in presets, plus the plain control.
DOTTED = [
    "ColorMunki-A4-1224p-4pages-Portrait-Slow-Reading-Speed-w10.0mm",
    "i1Pro-A4-1160p-2pages-TC9.18-extended-greys-by-Pharmacist",
    "ColorMunki-A4-300p-1page-TC3.00-by-Pharmacist",
    "i1Pro-A4-484p-1page-Portrait-w7.5mm",
]


@pytest.mark.parametrize("name", DOTTED + ["i1Pro-A4-484p-1page-no-dots"])
def test_the_stem_survives_a_dot(tmp_path, name):
    """A stem is taken verbatim — nothing in it is ever read as an extension."""
    assert without_ext(tmp_path / name, ".ti1").name == name, (
        f"the stem of {name!r} was truncated — every file the engine writes "
        "would land under a different name than the .ti1")


@pytest.mark.parametrize("ext", [".ti2", ".tif", ".pdf", ".cht", ".strips.json"])
@pytest.mark.parametrize("name", DOTTED)
def test_every_artefact_keeps_the_whole_name(tmp_path, name, ext):
    """The names the engine writes must match what `Run` looks for."""
    assert artefact(tmp_path / name, ext).name == name + ext


def test_a_real_extension_is_still_removed(tmp_path):
    """The helper must not become a no-op: a genuine .ti1 stem still resolves.

    Without this the fix could be 'never strip anything', which would give
    `<name>.ti1.ti2` and break the non-dotted case that works today.
    """
    assert without_ext(tmp_path / "chart.ti1", ".ti1").name == "chart"
    assert without_ext(tmp_path / "chart.TI1", ".ti1").name == "chart", \
        "the extension check must be case-insensitive"


@pytest.mark.parametrize("name", ["Canon.ps", "Proof.pdf", "Chart.cht",
                                  "Data.json", "Epson.P900"])
def test_a_name_that_LOOKS_like_an_extension_is_left_alone(tmp_path, name):
    """`_WORKFILE_EXTS` (core/file_manager.py:63) blocks a target name ending in
    a work-file extension, but NOT ".ps"/".pdf"/".cht"/".json". Those are legal
    project names, so an allow-list of "extensions to strip" would eat them —
    which is why the helper removes only the ONE extension it is told to."""
    from core.file_manager import FileManager
    assert FileManager._sanitise(FileManager.strip_workfile_ext(name)) == name, \
        "this name is not legal after all — the test's premise has changed"
    assert without_ext(tmp_path / name, ".ti1").name == name
    assert artefact(tmp_path / name, ".ti2").name == name + ".ti2"


def test_the_run_and_the_engine_agree_on_every_path(tmp_path):
    """The two halves of the app must derive the SAME names.

    `core.file_manager.Run` concatenates; the engine used `with_suffix`. This is
    the disagreement that cost the user the whole measurement.
    """
    from core.file_manager import Run

    name = "ColorMunki-A4-1224p-4pages-Portrait-Slow-Reading-Speed-w10.0mm"
    run_dir = tmp_path / name / "runs" / "run1"
    run_dir.mkdir(parents=True)
    run = Run.for_dir(run_dir)

    assert artefact(run_dir / name, ".ti2") == run.chart_ti2, (
        "the engine and Run disagree on the .ti2 path — Run.chart_ti2 would "
        "report a file that is not there")
