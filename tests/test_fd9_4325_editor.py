"""4.3.25, F10 (Knut's finding): the patch set editor opens FD-9 charts.

4.3.24 refused them ("cannot lay it out yet"), which was wrong: the editor
loads the FD-9 chart with its own recipe, and the patch set it saves goes
back to Create Chart, which lays it out with the FD-9's own builder. These
tests walk that road with the real editor window (offscreen), and then the
FD-9 builder on what the editor wrote.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import json

import pytest

from tests.test_fd9_chart_creation import ti1
from workflow.fd9.chart import build_chart, capacity, chart_pages
from workflow.fd9.measurement import checked_chart, first_table


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    return s


def _fd9_chart(tmp_path, count, rep="RGB", tokens=("R", "G", "B"),
               name="chart", recipe=True):
    """An FD-9 chart as Create Chart leaves it: the chart files, and (when
    made in Manual) the recipe in its channels.json."""
    run = tmp_path / "run"
    run.mkdir(exist_ok=True)
    src, _ = ti1(run, rep=rep, tokens=tokens, count=count)
    (run / f"{name}.ti1").write_text(src.read_text())
    r = build_chart(run / f"{name}.ti1", run / name, paper="A4", dpi=100,
                    randomize=False)
    from workflow.layout_engine.presets import LayoutRecipe
    if recipe:
        rec = LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=8,
                           patch_h_mm=8, fd9_gap_mm=None, inter_patch_mm=1.0,
                           strip_gap_mm=1.0, dpi=100)
    else:
        # Guided keeps no layout recipe of its own: the chart creator
        # records one from the build kwargs (`_embed_layout_geometry`).
        rec = LayoutRecipe.from_build_kwargs(dict(
            instrument="FD9", paper="A4", patch_w=8.0, patch_h=8.0,
            fd9_gap=1.0, dpi=100))
    if True:
        side = json.loads((run / f"{name}.strips.json").read_text())
        side.update(engine="chromiq", engine_version=1, seed=r.seed,
                    color_rep=r.color_rep, recipe=rec.to_dict())
        (run / f"{name}.channels.json").write_text(json.dumps(
            {"layout": side}))
    return r.ti2_path


def _editor(qapp, qtbot, settings, chart):
    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.tools_dialogs import build_tool_dialog
    dlg = build_tool_dialog("ti2_relayout", ArgyllRunner(settings), settings,
                            None, initial_chart=chart)
    qtbot.addWidget(dlg)
    # The editor loads its chart from a zero-delay timer once it is up.
    qtbot.waitUntil(lambda: dlg._grid.count() > 0, timeout=20000)
    return dlg


def _relaid(tmp_path, stage, name):
    """What Create Chart does with the editor's patch set: the FD-9 builder,
    which also runs the detector check of every page."""
    r = build_chart(stage / f"{name}.ti1", tmp_path / "relaid" / name,
                    paper="A4", dpi=100, randomize=False)
    _, doc, _ = checked_chart(r.ti2_path)
    return r, chart_pages(doc)


def test_the_editor_has_no_fd9_refusal_any_more():
    from pathlib import Path
    from ui import main_window as mw
    assert not hasattr(mw.MainWindow, "_refuse_editor_for_fd9")
    src = Path(mw.__file__).read_text(encoding="utf-8")
    assert "cannot change an FD-9 chart" not in src


def test_round_trip_keeps_every_patch_and_the_fd9_layout(qapp, qtbot,
                                                         settings, tmp_path):
    chart = _fd9_chart(tmp_path, 120)
    dlg = _editor(qapp, qtbot, settings, chart)
    assert dlg._engine_active()
    assert dlg._engine_panel.get_recipe().instrument == "FD9"
    assert dlg._grid.count() == 120
    stage = tmp_path / "stage"
    dlg._write_chart_into(stage, "edited")
    assert (stage / "edited.fd9.json").is_file()
    _, before, _ = first_table(chart)
    r, pages = _relaid(tmp_path, stage, "edited")
    _, after, _ = first_table(r.ti2_path)
    key = [f for f in before[0] if f.startswith("RGB_")]
    assert sorted(tuple(x[k] for k in key) for x in after) == sorted(
        tuple(x[k] for k in key) for x in before)
    assert pages[0]["patch_mm"] == [8.0, 8.0] and pages[0]["gap_mm"] == [1.0, 1.0]


def test_removing_patches_across_a_page_boundary(qapp, qtbot, settings,
                                                 tmp_path, monkeypatch):
    cap = capacity("A4", 8.0, 8.0, 1.0, 100)
    chart = _fd9_chart(tmp_path, cap + 30)          # two sheets
    _, doc, _ = checked_chart(chart)
    assert len(chart_pages(doc)) == 2
    dlg = _editor(qapp, qtbot, settings, chart)
    n = len(first_table(chart)[2])         # with the white padding cells
    assert dlg._grid.count() == n
    # The editor's own question about the new count is answered "go on".
    from PyQt6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: (
        asked.append(self.text()), QMessageBox.StandardButton.Yes)[1])
    # The last ten of sheet one and the first ten of sheet two.
    for _ in range(20):
        dlg._grid.takeItem(cap - 10)
    assert dlg._grid.count() == n - 20
    stage = tmp_path / "stage"
    dlg._write_chart_into(stage, "edited")
    r, pages = _relaid(tmp_path, stage, "edited")
    assert len(pages) == 2
    assert sum(len(row) for p in pages for row in p["rows"]) >= n - 20
    assert len(first_table(stage / "edited.ti1")[2]) == n - 20


def test_cmyk_plus_n_inks_survive_the_editor(qapp, qtbot, settings, tmp_path):
    tokens = ("C", "M", "Y", "K", "c", "m", "k", "1k", "R", "G", "B")
    chart = _fd9_chart(tmp_path, 40, rep="CMYKcmk1kRGB", tokens=tokens)
    dlg = _editor(qapp, qtbot, settings, chart)
    assert dlg._grid.count() == 40
    stage = tmp_path / "stage"
    dlg._write_chart_into(stage, "edited")
    text = (stage / "edited.ti1").read_text()
    assert "CMYKcmk1kRGB" in text
    r, pages = _relaid(tmp_path, stage, "edited")
    assert pages[0]["channel_tokens"] == list(tokens)


def test_a_guided_made_chart_opens_with_the_fd9_defaults(qapp, qtbot,
                                                         settings, tmp_path):
    """Guided records no recipe: the editor still opens the chart, on the
    FD-9, and what it saves lays out as an FD-9 chart."""
    chart = _fd9_chart(tmp_path, 60, recipe=False)
    dlg = _editor(qapp, qtbot, settings, chart)
    assert dlg._grid.count() == len(first_table(chart)[2])
    assert dlg._engine_panel.get_recipe().instrument == "FD9"
    stage = tmp_path / "stage"
    dlg._write_chart_into(stage, "edited")
    r, pages = _relaid(tmp_path, stage, "edited")
    assert sum(len(row) for row in pages[0]["rows"]) >= 60


def test_with_the_beta_off_the_editor_path_is_4324s(qapp, qtbot, settings,
                                                    tmp_path):
    """Off, 4.3.24 never refused either (the refusal asked the switch
    first), so removing it changes nothing there: the editor opens the
    chart as one for an instrument it does not know."""
    chart = _fd9_chart(tmp_path, 30)
    from workflow.fd9 import support
    support.set_enabled_for_this_process(False)
    dlg = _editor(qapp, qtbot, settings, chart)
    assert dlg._grid.count() == len(first_table(chart)[2])
