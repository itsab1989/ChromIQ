"""#182 K3 + K4: the preview after a measurement shows what it showed during it,
and which patches a re-read confirmed is kept with the measurement.

Knut, #182 5959352118: after a measurement the red outlines were gone. The
repaint from the file (`per_patch_overlay`) used the Measurement Report's
ΔE2000 on D65->D50 adapted expected values, while the engine compares the raw
`.ti2` XYZ by ΔE*ab: his A23 was 103.2 live and 16.1 afterwards. Sebastian
approved keeping the yellow memory with the measurement (5959447807).

Every part has a test that fails without it (mutation-proved, see the report
AL_overlay_and_memory):

* K3 the engine's numbers:   test_a23_repainted_from_the_file_is_red_at_its_live_de
* K3 same outlines:          test_reading_then_ending_leaves_every_outline_as_it_was
* K3 the strip test:         test_the_repaint_applies_the_strip_test_in_strip_mode
* K3 earlier session:        test_rereading_a_strip_from_an_earlier_session_confirms
* K4 the end repaint:        test_a_confirmed_patch_survives_the_end_of_the_measurement
* K4 resume:                 test_a_resumed_read_remembers_a_fresh_read_forgets
* K4 archive:                test_a_fresh_read_moves_the_memory_to_old_with_the_ti3
* K4 hash:                   test_a_memory_for_another_version_of_the_ti3_is_ignored
* K4 carried:                test_the_verify_marker_carries_it, ..._project_rename_...,
                             ..._duplicate_...
* K4 helper:                 test_confirmed_locations
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from workflow import confirmed_patches as cp  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

from tests.test_k182_two_limits_and_the_yellow_outline import (  # noqa: E402
    KNUT, _Settings, _strip)



@pytest.fixture(autouse=True)
def _reread_route_only(monkeypatch):
    """These tests are about the RE-READ confirmation on Knut's own strips.
    His blues are similar patches of different strips, which confirm each
    other since beta 9 (Knut 5979886227, tests/test_k22_peer_confirmation.py);
    here that route is switched off so each test still measures the re-read."""
    from workflow import patch_flags as _pf
    monkeypatch.setattr(_pf, "PEER_EXPECTED_DE", 0.0)

@pytest.fixture(autouse=True)
def _qapp():
    return QApplication.instance() or QApplication([])


def _ti2_text(rows):
    lines = ['CTI2', '', 'ORIGINATOR "ChromIQ layout engine"',
             'APPROX_WHITE_POINT "95.050000 100.000000 108.900000"',
             'NUMBER_OF_FIELDS 5', 'BEGIN_DATA_FORMAT',
             'SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
             f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    for i, (loc, e, _m) in enumerate(rows, 1):
        lines.append(f'{i} "{loc}" {e[0]:.4f} {e[1]:.4f} {e[2]:.4f}')
    lines.append('END_DATA')
    return "\n".join(lines) + "\n"


def _ti3_text(rows, scale=1.0):
    lines = ['CTI3', '', 'ORIGINATOR "Argyll chartread"',
             'NUMBER_OF_FIELDS 8', 'BEGIN_DATA_FORMAT',
             'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z',
             'END_DATA_FORMAT', f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    for i, (loc, _e, m) in enumerate(rows, 1):
        lines.append(f'{i} "{loc}" 0 0 0 {m[0] * scale:.4f} '
                     f'{m[1] * scale:.4f} {m[2] * scale:.4f}')
    lines.append('END_DATA')
    return "\n".join(lines) + "\n"


def _write_chart(folder: Path, rows=KNUT, stem="chart"):
    folder.mkdir(parents=True, exist_ok=True)
    ti2 = folder / f"{stem}.ti2"
    ti2.write_text(_ti2_text(rows), encoding="utf-8")
    return ti2


def _write_ti3(folder: Path, rows=KNUT, stem="chart", scale=1.0):
    ti3 = folder / f"{stem}.ti3"
    ti3.write_text(_ti3_text(rows, scale), encoding="utf-8")
    return ti3


def _tab(folder: Path, settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings(settings or {"chartread_engine": "chromiq"})
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._ti1_path = _write_chart(folder)
    every = [chr(ord("A") + i) for i in range(24)]
    tab._page_stripe_rects = [[QRect(0, 20 * i, 600, 18) for i in range(24)]]
    tab._strips_per_page = [24]
    tab._engine_strips = [{"strip": c} for c in every]
    boxes = {}
    for i, c in enumerate(every):
        if c not in ("A", "F", "O"):
            continue
        for n in range(1, 28):
            boxes[f"{c}{n}"] = QRect(22 * (n - 1), 20 * i, 20, 18)
    tab._patch_boxes = [boxes]
    return tab


def _flags(tab):
    boxes = tab._patch_boxes[0]
    by_box = {(b.x(), b.y()): loc for loc, b in boxes.items()}
    return {by_box[(it[0].x(), it[0].y())]: it[3]
            for it in tab._preview._patch_overlay.get(0, [])}


def _info(tab, loc):
    box = tab._patch_boxes[0][loc]
    for b, info in tab._preview._patch_info.get(0, []):
        if (b.x(), b.y()) == (box.x(), box.y()):
            return info
    raise AssertionError(loc)


def _again(letter):
    """Knut's re-read: the same colour within the instrument's noise."""
    ev = _strip(letter)
    for p in ev["patches"]:
        p["xyz"] = [v * 1.004 for v in p["xyz"]]
    return ev


def _live_session(tab):
    tab._session_live = True
    tab._spot_session = False


def _end_session(tab, ti3):
    """What `_on_measure_done` does with the yellow memory, then the repaint."""
    tab._session_live = False
    tab._ti3_mtime_before = None
    tab._save_confirmed_memory_at_end()
    tab._preview.clear_patch_overlay()
    assert tab._show_overlay_from_existing_ti3()
    tab._save_confirmed_memory_at_end()


# ---- K3 ---------------------------------------------------------------------
def test_per_patch_overlay_gives_the_engines_numbers(tmp_path):
    from workflow.measurement_report import per_patch_overlay
    ti2 = _write_chart(tmp_path)
    ti3 = _write_ti3(tmp_path)
    got = {p["loc"]: p for p in per_patch_overlay(ti3, ti2)}
    a23 = got["A23"]
    # the .ti2 XYZ as written: no D65 -> D50 adaptation
    assert a23["exyz"] == pytest.approx([19.1748, 8.8575, 95.3068])
    assert a23["de"] == pytest.approx(103.2, abs=0.05)


def test_a23_repainted_from_the_file_is_red_at_its_live_de(tmp_path):
    tab = _tab(tmp_path)
    _write_ti3(tmp_path)
    assert tab._show_overlay_from_existing_ti3()
    info = _info(tab, "A23")
    assert info["de"] >= 95 and info["warn"] is True
    assert _flags(tab)["A23"] is True


def test_reading_then_ending_leaves_every_outline_as_it_was(tmp_path):
    tab = _tab(tmp_path)
    _live_session(tab)
    for c in "AFO":
        tab._on_strip_measured(_strip(c))
    live = _flags(tab)
    live_de = {loc: _info(tab, loc)["de"] for loc in live}
    assert sorted(l for l, f in live.items() if f) == ["A17", "A23", "F4", "O9"]
    ti3 = _write_ti3(tmp_path)
    _end_session(tab, ti3)
    after = _flags(tab)
    assert after == live
    for loc, de in live_de.items():
        assert _info(tab, loc)["de"] == pytest.approx(de, abs=0.05), loc


def test_the_repaint_applies_the_strip_test_in_strip_mode(tmp_path):
    # A low limit: many patches pass it, only strip outliers are flagged live.
    settings = {"chartread_engine": "chromiq",
                pf.ESTIMATED_KEY: 25.0, "patch_strip_test_estimated": True}
    tab = _tab(tmp_path, settings)
    _live_session(tab)
    for c in "AFO":
        tab._on_strip_measured(_strip(c))
    live = _flags(tab)
    past_limit = [l for l in live if _info(tab, l)["de"] >= 25.0]
    fenced_out = [l for l in past_limit if not live[l]]
    assert fenced_out, "the strip test must hold some patch back for this test"
    ti3 = _write_ti3(tmp_path)
    _end_session(tab, ti3)
    assert _flags(tab) == live
    assert _info(tab, fenced_out[0])["fenced"] is True


def test_patch_by_patch_repaint_has_no_strip_test(tmp_path):
    settings = {"chartread_engine": "chromiq",
                pf.ESTIMATED_KEY: 25.0, "patch_strip_test_estimated": True}
    tab = _tab(tmp_path, settings)
    ti3 = _write_ti3(tmp_path)
    cp.write(ti3, {}, "patch")
    assert tab._show_overlay_from_existing_ti3()
    flags = _flags(tab)
    for loc, f in flags.items():
        assert bool(f) == (_info(tab, loc)["de"] >= 25.0), loc


def test_rereading_a_strip_from_an_earlier_session_confirms(tmp_path):
    tab = _tab(tmp_path)
    _write_ti3(tmp_path)                       # strip A read in an earlier session
    tab._session_resumes = True
    _live_session(tab)
    cb = tab._overlay_cb if tab._current_mode() == "guided" else tab._m_overlay_cb
    cb.blockSignals(True)
    cb.setChecked(True)
    cb.blockSignals(False)
    tab._on_session_map([{"strip": c, "read": c in "AFO"} for c in "AFO"])
    assert _flags(tab)["A17"] is True          # the repaint: red, as it was
    tab._on_strip_measured(_again("A"))
    assert _flags(tab)["A17"] == pf.FLAG_CONFIRMED
    assert _flags(tab)["A23"] == pf.FLAG_CONFIRMED


# ---- K4 ---------------------------------------------------------------------
def _confirm_a_and_end(tmp_path):
    tab = _tab(tmp_path)
    _live_session(tab)
    for c in "AFO":
        tab._on_strip_measured(_strip(c))
    tab._on_strip_measured(_again("A"))
    assert _flags(tab)["A17"] == pf.FLAG_CONFIRMED
    ti3 = _write_ti3(tmp_path)
    _end_session(tab, ti3)
    return tab, ti3


def test_a_confirmed_patch_survives_the_end_of_the_measurement(tmp_path):
    tab, ti3 = _confirm_a_and_end(tmp_path)
    flags = _flags(tab)
    assert flags["A17"] == pf.FLAG_CONFIRMED
    assert flags["A23"] == pf.FLAG_CONFIRMED
    data = json.loads(cp.confirmed_path(ti3).read_text(encoding="utf-8"))
    assert data["schema"] == 1 and data["mode"] == "strip"
    assert data["ti3_sha256"] == cp.ti3_sha256(ti3)
    assert data["patches"]["A17"]["kind"] == "confirmed"
    # F4 is a blue like A17 and A23, but two confirmations less than ΔE 6
    # apart do not teach the blue range (#182 k10): it stays red, and nothing
    # learned is stored. Storing a learned patch is
    # tests/test_k182_k10_colour_ranges.py's.
    assert flags["F4"] is pf.FLAG_RED
    assert "F4" not in data["patches"]


def test_the_memory_is_written_while_the_session_runs(tmp_path):
    tab = _tab(tmp_path)
    _live_session(tab)
    tab._on_strip_measured(_strip("A"))
    assert not cp.confirmed_path(tmp_path / "chart.ti3").is_file()
    tab._on_strip_measured(_again("A"))
    raw = cp.read_raw(tmp_path / "chart.ti3")
    assert raw is not None and raw["patches"]["A17"]["kind"] == "confirmed"


def test_a_resumed_read_remembers_a_fresh_read_forgets(tmp_path):
    _tab0, ti3 = _confirm_a_and_end(tmp_path)
    resumed = _tab(tmp_path)
    resumed._session_resumes = True
    _live_session(resumed)
    resumed._on_session_map([{"strip": c, "read": True} for c in "AFO"])
    assert set(resumed._flag_judge().confirmed) >= {"A17", "A23"}
    fresh = _tab(tmp_path)
    fresh._session_resumes = False
    _live_session(fresh)
    fresh._on_session_map([{"strip": c, "read": False} for c in "AFO"])
    assert fresh._flag_judge().confirmed == []


def test_reopening_the_measurement_shows_the_yellow_again(tmp_path):
    _tab0, _ti3 = _confirm_a_and_end(tmp_path)
    other = _tab(tmp_path)                     # a new window, a new memory
    assert other._show_overlay_from_existing_ti3()
    assert _flags(other)["A17"] == pf.FLAG_CONFIRMED


def test_a_fresh_read_moves_the_memory_to_old_with_the_ti3(tmp_path):
    tab, ti3 = _confirm_a_and_end(tmp_path)
    mem = cp.confirmed_path(ti3)
    assert mem.is_file()
    tab._read_builds_on_existing = lambda: False
    tab._archive_measurement_before_replacing()
    assert not ti3.exists() and not mem.exists()
    kept = list((tmp_path / "old").glob("*/chart.confirmed.json"))
    assert len(kept) == 1
    assert (kept[0].parent / "chart.ti3").is_file()
    assert cp.confirmed_locations(kept[0].parent / "chart.ti3") >= {"A17", "A23"}


def test_a_memory_for_another_version_of_the_ti3_is_ignored(tmp_path):
    _tab0, ti3 = _confirm_a_and_end(tmp_path)
    assert "A17" in cp.confirmed_locations(ti3)
    _write_ti3(tmp_path, scale=1.0001)          # the file changed since
    assert cp.load(ti3) is None
    assert cp.confirmed_locations(ti3) == set()
    other = _tab(tmp_path)
    assert other._show_overlay_from_existing_ti3()
    assert _flags(other)["A17"] is True


def test_confirmed_locations(tmp_path):
    ti3 = _write_ti3(tmp_path)
    assert cp.confirmed_locations(ti3) == set()
    cp.write(ti3, {"A17": {"kind": "confirmed", "de": 105.0, "prev_de": 104.0,
                           "exp_lab": [1, 2, 3], "meas_lab": [4, 5, 6],
                           "shift": [3, 3, 3], "standout": 60.0},
                   "F4": {"kind": "learned", "like": "A17"}}, "strip")
    assert cp.confirmed_locations(ti3) == {"A17"}
    assert cp.confirmed_path(ti3).name == "chart.confirmed.json"
    assert cp.confirmed_locations(tmp_path / "absent.ti3") == set()


def _one_confirmed(ti3):
    cp.write(ti3, {"A17": {"kind": "confirmed", "de": 105.0, "prev_de": 104.0,
                           "exp_lab": [1, 2, 3], "meas_lab": [4, 5, 6],
                           "shift": [3, 3, 3], "standout": None}}, "patch")


def test_the_verify_marker_carries_it(tmp_path):
    from workflow.ti3_analysis import mark_verification_ti3
    ti3 = _write_ti3(tmp_path)
    _one_confirmed(ti3)
    marked = mark_verification_ti3(ti3)
    assert marked.name == "chart-verify.ti3"
    mem = tmp_path / "chart-verify.confirmed.json"
    assert mem.is_file() and not cp.confirmed_path(ti3).exists()
    assert cp.confirmed_locations(marked) == {"A17"}   # re-stamped
    assert cp.load(marked)["mode"] == "patch"


def test_a_project_rename_carries_it(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.current_run()
    ti3 = _write_ti3(run.dir, stem=run.stem)
    _one_confirmed(ti3)
    proj.rename("Other")
    new = run.dir / "Other.ti3"
    assert (run.dir / "Other.confirmed.json").is_file()
    assert cp.confirmed_locations(new) == {"A17"}


def test_a_duplicate_run_carries_it(tmp_path):
    from core.file_manager import Project
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.current_run()
    ti3 = _write_ti3(run.dir, stem=run.stem)
    _one_confirmed(ti3)
    new = proj.duplicate_run(run)
    assert cp.confirmed_locations(new.dir / f"{new.stem}.ti3") == {"A17"}


def test_the_end_of_a_measurement_saves_before_and_after_its_repaint():
    """`_on_measure_done` stamps the memory for the final file BEFORE anything
    paints from it, and once more AFTER the repaint, which is when a patch read
    before its like was confirmed turns learned (tested end to end above with
    the same two calls, `_end_session`)."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_measure_done)
    first = src.index("self._save_confirmed_memory_at_end()")
    repaint = src.index("self._restore_overlay_after_measurement()")
    last = src.rindex("self._save_confirmed_memory_at_end()")
    assert first < repaint < last
    assert src.index("self._drop_unused_verification_stage()") < first
