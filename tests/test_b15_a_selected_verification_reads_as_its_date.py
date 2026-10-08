"""Beta 15 follow-up: a selected dated verification reads as its date.

b15 item 9 opens the Verification box on the latest dated verification. Its
entry read "Overwrite 2027-01-07 11:00" (from #130 phase 4, when the box
opened on "New verification" and picking a date was the step towards
measuring over it), so merely LOOKING at a verification read like a
destructive act, and the long entry was cut to "Overwrite 2027-01-07 11:0".
Every date now reads as the date alone; measuring over one that holds
readings is still asked about at Start Measurement. "<date> - no measurement
yet" is unchanged.

The bar also gives way in a better order when its row is too tight: every
box first gives up what it holds beyond the entry it shows, and the last cut
takes the end of "Run N (overwrite)" before the date (measured on screen at
1280 px: Russian and Ukrainian cut the date to "2027-").
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import pytest

from core.file_manager import Project
from core.measurement_target import (RUN_TYPE_VERIFICATION,
                                     pretty_verification_date)


@pytest.fixture(autouse=True)
def _restore_the_ui_language():
    import core.i18n as i18n
    previous = getattr(i18n, "_language", "en")
    try:
        yield
    finally:
        i18n.set_language(previous)


class _FM:
    def __init__(self, root: Path):
        self._root = root

    def working_dir(self) -> Path:
        return self._root

    def project(self) -> Project:
        return Project.load(self._root)


def _project(tmp_path: Path) -> Path:
    proj = Project.create(tmp_path / "Canon", "Canon")
    r1 = proj.current_run()
    r1.ensure_dir()
    r1.profile_icc.write_text("icc", encoding="utf-8")
    for when in (_dt.datetime(2026, 10, 9, 11, 0), _dt.datetime(2027, 1, 7, 11, 0)):
        v = r1.new_verification(when)
        v.ensure_dir()
        v.measurement_ti3.write_text("CTI3\n", encoding="utf-8")
    proj.new_run()            # run2 current; the test picks run1
    return proj.root


def _bar(qapp, tmp_path, lang):
    import core.i18n as i18n
    i18n.set_language(lang)
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)
    ctl = MeasurementTargetController(_FM(_project(tmp_path)))
    bar = MeasurementTargetBar(ctl, show_verification=True)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    bar.show()
    qapp.processEvents()
    return ctl, bar


@pytest.mark.parametrize("lang", ["en", "de", "ru", "uk", "pl"])
def test_the_latest_date_reads_as_the_date(qapp, tmp_path, lang):
    ctl, bar = _bar(qapp, tmp_path, lang)
    box = bar._verify_combo
    vid = ctl.target.verification_id
    assert vid, "the box opens on the latest dated verification (item 9)"
    assert box.currentText() == pretty_verification_date(vid)
    dates = [box.itemText(i) for i in range(box.count() - 1)]
    assert dates == [pretty_verification_date(v)
                     for v in ctl.verification_ids("run1")]


def test_no_language_keeps_the_overwrite_entry():
    import json
    from core.resource_path import resource_path
    folder = Path(resource_path("data/i18n"))
    for f in folder.glob("*.json"):
        assert "Overwrite {when}" not in json.loads(f.read_text("utf-8")), f.name


@pytest.mark.parametrize("lang", ["en", "ru", "uk"])
def test_a_tight_row_cuts_the_run_box_before_the_date(qapp, tmp_path, lang):
    ctl, bar = _bar(qapp, tmp_path, lang)
    box = bar._verify_combo
    row = bar.layout().itemAt(0).layout()
    natural = row.minimumSize().width()
    # 60 px short of what the row wants, the shortfall the Russian bar had
    # at 1280 px once the Run type box had given up its spare width.
    bar.set_available_width(natural - 60)
    qapp.processEvents()
    assert box.minimumWidth() >= bar._current_width(box), (
        lang, box.minimumWidth(), bar._current_width(box),
        bar._run_combo.minimumWidth())
