"""Restore Used Chart keeps the chart it replaces, page images apart, and a
.cht leaves together with its .cie (Knut, #182 5959825756).

*"1. Agreed, archive olde chart files to old, except the tif files, they are
deleted and can be regenerated if the other files are restored. They take too
much space on the drive. 2. Yes, the cht and cie file are always a pair that
belongs together and must always match for the chart used."* Until now the
replaced chart files were discarded (the window said "The chart that is there
now is not kept").
"""
from __future__ import annotations

from workflow.chart_slot import slot_for_run
from workflow.verify_chart_snapshot import restore_cht_plan, restore_slot

from tests.test_knut_beta3_the_run_cht_is_not_the_chart import (  # noqa: E402
    _layout, _measured, _new_chart)


def _replace_chart(run):
    """The run now holds another chart, with a page image, after the
    measurement that stored the first one."""
    run.chart_ti1.write_text("TI1 another set", encoding="utf-8")
    page = run.dir / f"{run.chart_ti2.stem}_01.tif"
    page.write_bytes(b"II*\x00 page image")
    return page


def test_the_replaced_chart_goes_to_old_and_its_pages_do_not(tmp_path):
    _proj, run, _ = _measured(tmp_path, _layout())
    page = _replace_chart(run)
    result = restore_slot(slot_for_run(run))
    assert result.ok and result.archive is not None
    kept = {p.name: p.read_text(encoding="utf-8", errors="replace")
            for p in result.archive.iterdir() if p.is_file()}
    assert kept.get(run.chart_ti1.name) == "TI1 another set"
    assert page.name not in kept, "page images are not kept (Knut)"
    assert not page.exists() or page.read_bytes() != b"II*\x00 page image"
    assert run.chart_ti1.read_text(encoding="utf-8") == "TI1 patches"


def test_nothing_is_left_in_a_stash(tmp_path):
    _proj, run, _ = _measured(tmp_path, _layout())
    _replace_chart(run)
    restore_slot(slot_for_run(run))
    assert not list(run.dir.parent.glob(".restore-stash-*"))


def test_a_removed_cht_takes_its_cie_with_it(tmp_path):
    _proj, run, _ = _measured(tmp_path, _layout())
    chts = _new_chart(run, _layout(shift=3))
    cie = chts[0].with_suffix(".cie")
    cie.write_text("CIE reference values", encoding="utf-8")
    plan = restore_cht_plan(slot_for_run(run))
    assert cie in plan.remove
    result = restore_slot(slot_for_run(run))
    assert result.ok and not cie.exists()
    archived = list((run.dir / "old").rglob(cie.name))
    assert len(archived) == 1
    assert archived[0].read_text(encoding="utf-8") == "CIE reference values"


def test_a_kept_cht_keeps_its_cie(tmp_path):
    _proj, run, chts = _measured(tmp_path, _layout())
    cie = chts[0].with_suffix(".cie")
    cie.write_text("CIE reference values", encoding="utf-8")
    result = restore_slot(slot_for_run(run))
    assert result.ok and cie.is_file() and chts[0].is_file()


def test_the_window_no_longer_says_not_kept():
    import inspect
    import ui.measurement_target_bar as bar
    src = inspect.getsource(bar)
    assert "The chart that is there now is not kept" not in src
    assert src.count("_restore_archive_sentence())") == 4
