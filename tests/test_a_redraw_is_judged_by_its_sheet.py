"""Restore Used Chart says that the redraw would change the chart only when it
would (after 4.3.66).

The redraw keeps the restored chart's own files. It told the person "Redrawing
the pages would have changed the chart itself ... the pages shown here were
drawn from a different layout" of charts it redraws pixel for pixel: of every
chart (the ``.ti2``'s CREATED stamp was counted), of every chart whose seed was
drawn, and of every Guided chart, because ``channels.json`` also holds the rows
of the form and who chose a value. It is judged by its sheet now. Where the
pages really come out different, it is still told: both directions here, with
the pages themselves as the judge, for every instrument.

Real builds: targen from ArgyllCMS and the layout engine.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_run_types import (_generate, _pick, _prof,  # noqa: E402,F401
                                       requires_argyll, win)
from ui.tabs import tab_chart as TC                             # noqa: E402

TOLD = "Redrawing the pages would have changed the chart itself"
INSTRUMENTS = ["i1", "p3", "CM", "SS", "CR30", "FD9", "IO2", "XRISIS",
               "B100XY"]


@pytest.fixture(autouse=True)
def _every_beta_on(monkeypatch):
    for name in ("fd9", "i1io", "isis", "barbieri"):
        support = importlib.import_module(f"workflow.{name}.support")
        monkeypatch.setattr(support, "_latched", True)


def _pages(folder):
    import tifffile
    return [hashlib.sha256(tifffile.imread(str(p)).tobytes()).hexdigest()
            for p in sorted(folder.glob("*.tif"))]


def _guided(tc, qapp, instrument, paper):
    tc._switch_mode("guided")
    for combo, value in ((tc._instr_combo, instrument),
                         (tc._paper_combo, paper)):
        i = combo.findData(value)
        assert i >= 0, (instrument, paper)
        combo.setCurrentIndex(i)
        combo.activated.emit(i)
        qapp.processEvents()


def _restored(win, qapp, qtbot, monkeypatch, make, changed=False):  # noqa: F811
    """The chart *make* generates, stored, replaced by another one, restored
    and redrawn: ``(its pages before, its pages after, what the log says)``."""
    from workflow.chart_slot import slot_for_run
    from workflow.verify_chart_snapshot import restore_slot, snapshot_slot
    tc = win._tab_chart
    other = make(tc)
    _generate(win, qapp, qtbot, expect=_prof(win))
    run = win._file_mgr.project().current_run()
    before = _pages(run.dir)
    held = {p: p.read_bytes() for p in run.dir.glob(f"{run.stem}.*")
            if p.suffix in (".ti1", ".ti2", ".json")}
    snapshot_slot(slot_for_run(run))
    if changed:                   # (the test's own snapshot edits the record)
        held = {p: p.read_bytes() for p in held}
    _guided(tc, qapp, other, "Letter")
    _generate(win, qapp, qtbot, expect=_prof(win))
    assert before and _pages(run.dir) != before
    assert restore_slot(slot_for_run(run)).ok
    released = []
    real = TC.TabChart._release_rebuild_guard
    monkeypatch.setattr(TC.TabChart, "_release_rebuild_guard", lambda self: (
        real(self), released.append(1))[0])
    tc._log.clear()
    assert tc.rebuild_verification_pages()
    qtbot.waitUntil(lambda: released and tc._generate_btn.isEnabled(),
                    timeout=180_000)
    for _ in range(10):
        qapp.processEvents()
    # whatever is told, the restored chart's own files are what they were
    assert {p: p.read_bytes() for p in held} == held
    return before, _pages(run.dir), tc._log.toPlainText()


@requires_argyll
@pytest.mark.parametrize("mode", ["guided", "manual"])
@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_it_is_told_exactly_when_the_pages_come_out_different(
        win, qapp, qtbot, monkeypatch, instrument, mode):  # noqa: F811
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)

    def make(tc):
        if mode == "guided":
            _guided(tc, qapp, instrument, "A4")
        else:
            _pick(tc, qapp, instrument)
            tc._manual_auto_patches_check.setChecked(False)
            tc._on_auto_patches_toggled(False)
            tc._set_manual_value("targen", "-f", 60)
        return "CM" if instrument == "i1" else "i1"
    before, after, log = _restored(win, qapp, qtbot, monkeypatch, make)
    assert (TOLD in log) is (after != before), log
    assert after == before


@requires_argyll
@pytest.mark.parametrize("old", [True, False], ids=["as 4.3.66 stored it",
                                                    "margins of a person"])
def test_a_guided_chart_stored_with_the_wrong_margins(
        win, qapp, qtbot, monkeypatch, old):  # noqa: F811
    """A stored Guided chart of 4.3.66 is redrawn as it was printed. One whose
    margins are said to be a person's is redrawn with them: another sheet, and
    told."""
    from tests.test_i1io_run_types import _prof as chart
    tc = win._tab_chart
    _guided(tc, qapp, "i1", "A4")
    _generate(win, qapp, qtbot, expect=chart(win))

    def make(tab):
        _guided(tab, qapp, "i1", "A4")
        return "CM"
    from workflow import verify_chart_snapshot as V
    real = V.snapshot_slot

    def as_4366(slot):
        side = chart(win).with_suffix(".channels.json")
        doc = json.loads(side.read_text(encoding="utf-8"))
        for edge in ("top", "right", "bottom", "left"):
            assert doc["layout"]["recipe"][f"margin_{edge}"] == 10.0
            doc["layout"]["recipe"][f"margin_{edge}"] = 6.0
        if not old:
            doc["layout"].pop("margins_chosen_by_user")
        side.write_text(json.dumps(doc), encoding="utf-8")
        return real(slot)
    monkeypatch.setattr(V, "snapshot_slot", as_4366)
    before, after, log = _restored(win, qapp, qtbot, monkeypatch, make,
                                   changed=True)
    assert (after == before) is old
    assert (TOLD in log) is not old


@requires_argyll
@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_manual_shows_the_restored_charts_settings(
        win, qapp, qtbot, monkeypatch, instrument):  # noqa: F811
    """Item 61: the switch from Guided to Manual on the way wrote the settings
    Guided held (the chart that was replaced) over the restored ones: Letter
    beside an A4 chart. The target's stored settings follow."""
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    tc = win._tab_chart
    side = _prof(win).with_suffix(".channels.json")

    def make(tab):
        _guided(tab, qapp, instrument, "A4")
        return "CM" if instrument == "i1" else "i1"
    before, after, log = _restored(win, qapp, qtbot, monkeypatch, make)
    assert after == before and TOLD not in log
    assert "Manual now shows the settings" not in log
    assert tc._current_mode() == "manual"
    recipe = json.loads(side.read_text(encoding="utf-8"))["layout"]["recipe"]
    shown = tc._manual_layout_panel.get_recipe()
    assert (shown.instrument, shown.paper) == (instrument, "A4")
    margins = ((), ("margin_top", "margin_left"))[instrument not in (
        "IO2", "FD9")]            # (the panel shows the ones those have)
    for name in ("border", "pscale", "cm_density", "clip_border",
                 *margins):
        assert getattr(shown, name) == pytest.approx(recipe[name]) if \
            isinstance(recipe[name], float) else \
            getattr(shown, name) == recipe[name], name
    assert tc._manual_value("printtarg", "-i") == instrument
    assert tc._manual_value("printtarg", "-p") == "A4"
    # (N8 of the review: nor may a later click, should the redraw have failed)
    import inspect
    body = inspect.getsource(TC.TabChart.rebuild_verification_pages)
    assert body.index('_switch_mode("manual")') < body.index(
        "_guided_transfer_pending = False") < body.index(
        "load_ti1_and_generate_preview")
    # (Guided keeps what it held)
    assert tc._paper_combo.currentData() == "Letter"


# ---- the record of the sheet -----------------------------------------------

def _doc(tmp_path):
    from workflow.layout_engine.presets import default_recipe
    recipe = default_recipe("i1", "A4").to_dict()
    recipe["seed"] = None
    return {"ink_channels": ["R", "G", "B"], "chart_notes": "n",
            "run_description": "first", "stamp_commands": False,
            "auto_patches": True, "patch_set_given": False,
            "create_chart_settings": {"printtarg-p": {"value": "A4"}},
            "printtarg_fields": [{"flag": "-p", "value": "A4"}],
            "printer_calibration": {"mode": "off", "cal_sha1": "",
                                    "cal_name": "", "engine": "chromiq"},
            "layout": {"engine": "chromiq", "seed": 7, "recipe": recipe,
                       "margins_chosen_by_user": False,
                       "label_band_bottom_px": 184,
                       "patches": [{"loc": "A1", "x": 1, "y": 2}]}}


def _set(doc, path, value):
    doc = copy.deepcopy(doc)
    at = doc
    *way, last = path
    for k in way:
        at = at[k]
    if value is None:
        at.pop(last, None)
    else:
        at[last] = value
    return doc


def _same(old, new):
    return TC._same_sheet(json.dumps(old).encode(), json.dumps(new).encode())


@pytest.mark.parametrize("path,value", [
    (("create_chart_settings", "printtarg-p"), {"value": "Letter"}),
    (("printtarg_fields",), [{"flag": "-p", "value": "Letter"}]),
    (("auto_patches",), False), (("patch_set_given",), True),
    (("run_description",), "another"),
    (("layout", "margins_chosen_by_user"), None),
    (("layout", "recipe", "seed"), 7),
    (("layout", "recipe", "label_style_explicit"), True),
    (("layout", "recipe", "margins_explicit"), True),
    (("layout", "something_a_later_version_records"), 1),
    (("something_a_later_version_records",), 1)])
def test_what_is_not_on_the_sheet_is_no_difference(tmp_path, path, value):
    old = _doc(tmp_path)
    new = _set(old, path, value)
    assert _same(old, new)


@pytest.mark.parametrize("path,value", [
    (("chart_notes",), "other notes"), (("stamp_commands",), True),
    (("ink_channels",), ["C", "M", "Y", "K"]),
    (("printer_calibration", "mode"), "apply"),
    (("layout", "seed"), 8), (("layout", "patches"), [{"loc": "A2"}]),
    (("layout", "patches"), None),
    (("layout", "label_band_bottom_px"), 137),
    (("layout", "engine"), "printtarg"),
    (("layout", "recipe", "paper"), "Letter"),
    (("layout", "recipe", "spacer_mode"), "bw"),
    (("layout", "recipe", "indicator_size_mm"), 4.23),
    (("layout", "recipe", "chart_text"), "x"),
    (("layout", "recipe", "border"), 9.0)])
def test_what_is_on_the_sheet_is_a_difference(tmp_path, path, value):
    old = _doc(tmp_path)
    assert not _same(old, _set(old, path, value))


def test_other_margins_are_another_sheet(tmp_path):
    """Those of a Guided chart are its base margin whatever it recorded; the
    redraw records them without "nobody chose these"."""
    guided = _doc(tmp_path)
    base = guided["layout"]["recipe"]["border"]
    for mm, same in ((base, True), (base + 3.0, False)):
        redrawn = _set(guided, ("layout", "margins_chosen_by_user"), None)
        for side in ("top", "right", "bottom", "left"):
            redrawn = _set(redrawn, ("layout", "recipe", f"margin_{side}"), mm)
        assert _same(guided, redrawn) is same


def test_a_description_that_is_printed_counts(tmp_path):
    old = _set(_doc(tmp_path), ("layout", "recipe", "chart_text"),
               "{rundescription}")
    assert not _same(old, _set(old, ("run_description",), "another"))


def test_an_older_chart_without_the_later_fields_is_the_same_sheet(tmp_path):
    new = _doc(tmp_path)
    old = _set(new, ("printer_calibration",), None)
    for key in ("i1io_limits", "page_output", "label_style_explicit"):
        old = _set(old, ("layout", "recipe", key), None)
    assert _same(old, new)
    assert not _same(old, _set(new, ("printer_calibration", "mode"), "apply"))


@pytest.mark.parametrize("old,new,same", [
    (b"not json", b"not json", True), (b"not json", b"other", False),
    (b'{"layout": {"seed": 1}}', b'{"layout": {"seed": 2}}', False)])
def test_any_other_file_is_compared_byte_by_byte(old, new, same):
    assert TC._same_sheet(old, new) is same


def test_a_new_stamp_alone_is_not_told(tmp_path):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text('CTI2\nCREATED "Mon"\nNUMBER_OF_SETS 1\n', encoding="utf-8")
    held = ti2.read_bytes()
    guard = TC._ChartRebuildGuard(ti2)
    ti2.write_text('CTI2\nCREATED "Tue"\nNUMBER_OF_SETS 1\n', encoding="utf-8")
    assert guard.put_back() == [] and ti2.read_bytes() == held
