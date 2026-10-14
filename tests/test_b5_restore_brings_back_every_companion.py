"""4.3.5 beta 5: a restored chart comes back WHOLE (Knut, #182 6167775557,
6168101507, 6168612728).

Knut pressed Restore Used Chart on run 5's verification. The stored chart was
a FROM PROFILE GAMUT chart printed through the profile on 2026-10-10, and it
came back without two of its files: the colorimetric reference
(``-reference.ti3``) and the print record (``.print.json``). Restore Used
Chart had copied them back; the page redraw that follows a restore then
archived the whole verification chart into ``old/`` (the normal build does,
``Run._clear_verify_chart_files``) and its guard put back only the ``.ti1``,
``.ti2`` and ``.channels.json``. His log, 13:49:51: "archived
test-verify-reference.ti3 -> old/2026-10-14_134951/" and "archived
test-verify.print.json -> old/2026-10-14_134951/", one second after the
restore. What followed:

* Start said "Stored chart differs": the stored chart has a reference, the
  live one had none (R1);
* the hover cards used the limits for a chart with estimated colours: no
  print record, so no profile prediction (R2);
* the report showed N-A everywhere: no reference to judge a gamut chart
  against, and no cube-corner aims (R4).

THE GUARD THIS FILE KEEPS: ``core.file_manager.CHART_COMPANION_SUFFIXES`` is
the one list of the files that belong to a chart. Every test below is
parametrised over it, so a file added to it is snapshot, restored and kept
through the redraw without anyone writing a test for it; and the first block
fails when a file is written beside a chart without being put on it.
"""
from __future__ import annotations

import inspect
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import file_manager as fm                                 # noqa: E402
from core.file_manager import (CHART_COMPANION_SUFFIXES, Run,        # noqa: E402
                               Verification, chart_companion_names)
from workflow.chart_slot import (PROFILING_CHART_SUFFIXES, slot_for,  # noqa: E402
                                 slot_for_run)
from workflow.verify_chart_snapshot import (live_differs_from_snapshot,  # noqa: E402
                                            restore_slot,
                                            slot_live_differs,
                                            snapshot_matches_live,
                                            snapshot_slot)

STEM = "test"


# ---------------------------------------------------------------------------
# 1. the list is complete: every writer of a chart companion is on it
# ---------------------------------------------------------------------------
#: Files named after a chart that are deliberately NOT companions, and why.
NOT_COMPANIONS = {
    # made from the MEASUREMENT by the scanner target, never kept with the
    # chart (Knut, #182 5958921500)
    ".cht": "measurement-derived",
    ".cie": "measurement-derived (Knut, D8)",
    # what a print job or an export produced from the chart
    ".ps": "print output",
    ".pdf": "print output",
}


def _suffix_after(stem: str, name: str) -> str:
    assert name.startswith(stem), (stem, name)
    return name[len(stem):]


def test_every_writer_of_a_chart_companion_names_a_listed_file(tmp_path):
    from workflow.control_strip import declaration_path
    from workflow.measurement_report import CONTROL_STRIP_SIDECAR
    from workflow.verification_print import (colorimetric_reference_for,
                                             print_record_path)
    ti2 = tmp_path / f"{STEM}-verify.ti2"
    written = {
        "the colorimetric reference": colorimetric_reference_for(ti2),
        "the print record": print_record_path(ti2),
        "the control-strip declaration": declaration_path(ti2),
    }
    for what, path in written.items():
        suffix = _suffix_after(ti2.stem, path.name)
        assert suffix in CHART_COMPANION_SUFFIXES, (
            f"{what} is written as '{path.name}', and '{suffix}' is not in "
            "core.file_manager.CHART_COMPANION_SUFFIXES: a restore would put "
            "the chart back without it")
    assert CONTROL_STRIP_SIDECAR in CHART_COMPANION_SUFFIXES


def test_every_chart_file_a_run_names_is_a_companion_or_says_why_not(tmp_path):
    """``Run.chart_artefact_names`` and every ``chart_*`` / ``verify_chart_*``
    path of a Run: a new one has to be either on the list or in
    :data:`NOT_COMPANIONS` with its reason."""
    run = Run.for_dir(tmp_path / "runs" / "run1")
    names = list(run.chart_artefact_names())
    for attr, member in inspect.getmembers(Run):
        if not (attr.startswith("chart_") or attr.startswith("verify_chart_")):
            continue
        if not isinstance(member, property) or attr.endswith("_dir"):
            continue        # a folder (``chart_snapshot_dir``), not a file
        value = getattr(run, attr)
        if isinstance(value, Path):
            names.append(value.name)
    for name in names:
        stem = run.verify_stem if name.startswith(run.verify_stem) else run.stem
        suffix = _suffix_after(stem, name)
        assert suffix in CHART_COMPANION_SUFFIXES or suffix in NOT_COMPANIONS, (
            f"'{name}' belongs to a chart, but '{suffix}' is neither in "
            "CHART_COMPANION_SUFFIXES nor in NOT_COMPANIONS")


def test_the_profiling_snapshot_takes_every_companion():
    assert set(CHART_COMPANION_SUFFIXES) <= set(PROFILING_CHART_SUFFIXES)


# ---------------------------------------------------------------------------
# 2. a restore, and the redraw after it, keep every companion
# ---------------------------------------------------------------------------
def _write_chart(folder: Path, stem: str, tag: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in chart_companion_names(stem):
        (folder / name).write_text(f"{name} of chart {tag}\n", encoding="utf-8")
    (folder / f"{stem}.channels.json").write_text(
        '{"layout": {"engine": "chromiq"}, "chart": "%s"}' % tag,
        encoding="utf-8")
    (folder / f"{stem}.tif").write_bytes(b"page of " + tag.encode())


def _verification(tmp_path) -> "tuple[Run, Verification]":
    run = Run.for_dir(tmp_path / "test" / "runs" / "run5")
    run.dir.mkdir(parents=True)
    v = run.verification("2026-10-10_095840")
    v.dir.mkdir(parents=True)
    return run, v


def test_restore_then_redraw_keeps_every_companion_of_a_verification(
        tmp_path, qapp):
    """Knut's sequence on run 5, with the redraw's own archive in it."""
    from ui.tabs.tab_chart import _ChartRebuildGuard
    run, v = _verification(tmp_path)
    vdir = run.verifications_dir
    _write_chart(vdir, run.verify_stem, "MEASURED")
    slot = slot_for(v)
    assert snapshot_slot(slot) is not None
    stored = {p.name: p.read_bytes() for p in slot.snapshot_dir.iterdir()}
    for name in chart_companion_names(run.verify_stem):
        assert name in stored, f"the snapshot did not take {name}"

    # He regenerated the chart since (2026-10-13): fewer companions.
    for p in list(vdir.iterdir()):
        if p.is_file():
            p.unlink()
    for suffix in (".ti1", ".ti2", ".channels.json"):
        (vdir / f"{run.verify_stem}{suffix}").write_text("other chart",
                                                         encoding="utf-8")
    assert live_differs_from_snapshot(v)

    result = restore_slot(slot)
    assert result.ok
    # The redraw: the guard is armed, the build archives the whole chart
    # into old/ and lays a chart of its own, then the guard is released.
    guard = _ChartRebuildGuard(run.verify_chart_ti2)
    run._clear_verify_chart_files()
    for suffix in (".ti1", ".ti2", ".channels.json"):
        (vdir / f"{run.verify_stem}{suffix}").write_text("the redraw's chart",
                                                         encoding="utf-8")
    guard.put_back()

    for name in chart_companion_names(run.verify_stem):
        live = vdir / name
        assert live.is_file(), f"{name} was lost by the redraw"
        assert live.read_bytes() == stored[name], f"{name} came back changed"
    assert not live_differs_from_snapshot(v), "Start would say 'Stored chart differs'"
    assert not slot_live_differs(slot)
    assert snapshot_matches_live(slot)


@pytest.mark.parametrize("suffix", CHART_COMPANION_SUFFIXES)
def test_the_redraw_guard_puts_back_each_companion(tmp_path, suffix):
    from ui.tabs.tab_chart import _ChartRebuildGuard
    folder = tmp_path / "verifications"
    _write_chart(folder, f"{STEM}-verify", "R")
    path = folder / f"{STEM}-verify{suffix}"
    kept = path.read_bytes()
    guard = _ChartRebuildGuard(folder / f"{STEM}-verify.ti2")
    assert guard.holds(path)
    path.unlink()
    guard.put_back()
    assert path.read_bytes() == kept


def test_putting_back_a_companion_is_not_called_a_changed_chart(tmp_path):
    """The warning "the redraw changed the chart itself" is for the layout;
    a reference or a print record the build set aside is routine."""
    from ui.tabs.tab_chart import _ChartRebuildGuard
    folder = tmp_path / "verifications"
    _write_chart(folder, f"{STEM}-verify", "R")
    guard = _ChartRebuildGuard(folder / f"{STEM}-verify.ti2")
    (folder / f"{STEM}-verify-reference.ti3").unlink()
    (folder / f"{STEM}-verify.print.json").unlink()
    assert guard.put_back() == []
    assert (folder / f"{STEM}-verify-reference.ti3").is_file()


@pytest.mark.parametrize("suffix", CHART_COMPANION_SUFFIXES)
def test_a_profiling_restore_brings_back_each_companion(tmp_path, suffix):
    run = Run.for_dir(tmp_path / "test" / "runs" / "run1")
    _write_chart(run.dir, run.stem, "MEASURED")
    slot = slot_for_run(run)
    snapshot_slot(slot)
    want = (run.dir / f"{run.stem}{suffix}").read_bytes()
    # another chart, without this companion
    for p in list(run.dir.iterdir()):
        if p.is_file():
            p.unlink()
    for s in (".ti1", ".ti2", ".channels.json"):
        if s != suffix:
            (run.dir / f"{run.stem}{s}").write_text("other", encoding="utf-8")
    assert restore_slot(slot).ok
    assert (run.dir / f"{run.stem}{suffix}").read_bytes() == want


def test_the_companions_helpers_find_what_is_there(tmp_path):
    run = Run.for_dir(tmp_path / "test" / "runs" / "run1")
    _write_chart(run.verifications_dir, run.verify_stem, "V")
    _write_chart(run.dir, run.stem, "P")
    assert [p.name for p in run.verify_chart_companions()] == \
        chart_companion_names(run.verify_stem)
    assert [p.name for p in run.chart_companions()] == \
        chart_companion_names(run.stem)
    shutil.rmtree(run.verifications_dir)
    assert run.verify_chart_companions() == []
    assert fm.chart_companions(tmp_path / "nowhere", "x") == []
