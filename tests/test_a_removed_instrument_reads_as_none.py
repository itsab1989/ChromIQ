"""A stored ``isis`` reads as no instrument: the guard, not a migration.

The printtarg entry "i1iSis (via i1Profiler)" (code ``isis``) was removed by
the owner's ruling of 2026-11-14 (Basti: "the isis entry without the beta
option enabled is removed. and with the new option in beta the users get the
new improved isis/xl entry"; "i think no migration is really needed for it").
What a person may still have stored, from Save as Defaults, a named preset, a
target's own settings or a 4.3.36 project, must open without a traceback, on
the i1Pro and A4 (the entry's own A3+, -n and -P defaults go with it), and
nothing is written back until the person saves
(`ui.tabs.tab_chart._saved_beta_instrument_is_off`,
`data.patch_db.REMOVED_INSTRUMENT_CODES`).

The same holds with the new Beta "X-Rite i1iSis charts" on: ``isis`` is not
its code (``XRISIS`` is), so a stale ``isis`` never turns into the new entry.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                              # noqa: E402


def test_the_removed_code_is_listed_with_its_reason():
    from data.patch_db import (EXTERNAL_INSTRUMENTS, INSTRUMENT_LABELS,
                               REMOVED_INSTRUMENT_CODES, instrument_family_of)
    assert REMOVED_INSTRUMENT_CODES == {"isis"}
    assert "isis" not in INSTRUMENT_LABELS
    assert EXTERNAL_INSTRUMENTS == frozenset()
    # the model FAMILY of imported measurements stays
    assert instrument_family_of("X-Rite i1iSis 2") == "isis"


@pytest.fixture(params=[False, True], ids=["beta off", "beta on"])
def beta(request):
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(request.param)
    yield request.param
    support._latched = before


def _store(tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


def _tab(s):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from ui.tabs.tab_chart import TabChart
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _stale(s, engine: bool):
    """What 4.3.36's Save as Defaults stored on the old entry: Guided's and
    Manual's instrument, its A3+ sheet, -n and -P on."""
    s.set("chart_instrument", "isis")
    s.set("chart_paper", "329x483")
    s.set("use_chromiq_layout_engine", engine)
    s.set("manual_printtarg_-i_l", "isis")
    s.set("manual_printtarg_-p_l", "329x483")
    s.set("manual_printtarg_-n_l", True)
    s.set("manual_printtarg_-P_l", True)
    s.set("manual_engine_recipe", {"instrument": "isis", "paper": "329x483",
                                   "dpi": 300})


@pytest.mark.parametrize("engine", [False, True], ids=["printtarg", "engine"])
def test_saved_defaults_naming_isis_open_on_the_i1pro_and_a4(
        qapp, tmp_path, beta, engine):
    s = _store(tmp_path)
    _stale(s, engine)
    s._qs.sync()
    t = _tab(s)
    try:
        qapp.processEvents()
        assert t._instr_combo.currentData() == "i1"
        assert t._paper_combo.currentData() == "A4"
        assert t._manual_value("printtarg", "-i") == "i1"
        assert t._manual_value("printtarg", "-p") == "A4"
        assert not t._manual_value("printtarg", "-n")
        assert not t._manual_value("printtarg", "-P")
        assert t._stored_defaults_recipe() is None
        # nothing written back until the person saves
        s._qs.sync()
        assert s.get("chart_instrument") == "isis"
        assert s.get("manual_printtarg_-i_l") == "isis"
    finally:
        t.deleteLater()
        qapp.processEvents()


def test_a_named_preset_naming_isis_is_read_without_a_traceback(beta):
    from workflow.layout_engine.presets import LayoutRecipe, PresetStore
    store = PresetStore.from_named_dict(
        {"isis|329x483|default": {"instrument": "isis", "paper": "329x483"}})
    r = LayoutRecipe.from_dict(store.as_named_dict()["isis|329x483|default"])
    assert r.instrument == "isis"
    # the guard every reader of a stored instrument asks
    from ui.tabs.tab_chart import _saved_beta_instrument_is_off
    assert _saved_beta_instrument_is_off(r.instrument) is True
    # and the engine refuses it as an unknown code, never a KeyError
    from workflow.layout_engine import instruments
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.build("isis")


def test_a_targets_stored_isis_row_is_not_put_on_screen(qapp, tmp_path,
                                                         beta):
    s = _store(tmp_path)
    t = _tab(s)
    try:
        t._apply_ui_state({"guided": {"instrument": "isis",
                                      "paper": "329x483", "pages": 1}})
        qapp.processEvents()
        assert t._instr_combo.currentData() != "isis"
        assert t._instr_combo.currentData() in ("i1", None)
    finally:
        t.deleteLater()
        qapp.processEvents()


def test_a_4336_project_meta_naming_isis_is_left_byte_identical(
        qapp, tmp_path, beta):
    """A run made with the old entry: its meta.json names ``isis``. Opening
    the project reads it as none and writes nothing; a NEW run's meta.json
    does not name ``isis``."""
    from core.file_manager import Project
    s = _store(tmp_path)
    out = tmp_path / "out"
    project = Project.create(out / "Old-Isis-Project", "Old-Isis-Project")
    run = project.current_run()
    meta_path = run.dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) \
        if meta_path.is_file() else {}
    meta["create_chart_settings"] = {"printtarg-i": {"value": "isis"},
                                     "printtarg-p": {"value": "329x483"}}
    meta["create_chart_ui"] = {"guided": {"instrument": "isis",
                                          "paper": "329x483"}}
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    before = meta_path.read_bytes()
    t = _tab(s)
    try:
        t.open_project_manifest(project.root / "project.json")
        for _ in range(20):
            qapp.processEvents()
        assert t._instr_combo.currentData() != "isis"
        assert meta_path.read_bytes() == before
        new = project.new_run()
        nm = new.dir / "meta.json"
        if nm.is_file():
            assert '"isis"' not in nm.read_text(encoding="utf-8")
    finally:
        t.deleteLater()
        qapp.processEvents()
