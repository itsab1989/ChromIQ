"""Arriving at the Measure tab paints the overlay at most once, and not at all
when nothing it is made from has changed (perf audit 2026-11-07, item 2).

Measured on screen on a 1,232-patch run: every switch to Measure with "Show
overlay" ticked painted the whole overlay twice, once from `showEvent`
(`_update_resume_availability` -> `_restore_overlay_after_measurement`) and
once from the deferred `refresh_patch_flags`, and a third time when the
arrival offer was accepted: 0.6 to 1.2 s of a frozen window per switch.

What may NOT change is the picture. So every test here also compares what is
on the preview with a painting made from scratch, and every input of the
painting gets its own test that it still paints, exactly once, with the new
result: the measurement file, a limit in Preferences, another chart, a
re-read confirmed, and anything else that replaced the painting on screen.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402

import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

from core.file_manager import Project  # noqa: E402
from workflow import confirmed_patches as cp  # noqa: E402
from workflow import misread_settings as ms  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

from tests.test_k182_k3_k4_overlay_and_memory import (  # noqa: E402
    _write_chart, _write_ti3)


@pytest.fixture(autouse=True)
def _reread_route_only(monkeypatch):
    """As in test_k182_k3_k4_overlay_and_memory: the re-read route alone, so
    one confirmation in the memory file is one yellow patch."""
    monkeypatch.setattr(pf, "PEERS_ON", False)


@pytest.fixture(autouse=True)
def _preferences_put_back(qapp):
    """Every preference a test here sets is put back afterwards, stored or
    not, so no later file on this worker inherits a limit of 1.0."""
    from core.settings import AppSettings
    qs = AppSettings()._qs
    before = {k: qs.value(k) for k in qs.allKeys()}
    yield
    qs = AppSettings()._qs
    for k in qs.allKeys():
        if k not in before:
            qs.remove(k)
    for k, v in before.items():
        qs.setValue(k, v)
    qs.sync()


def _boxes():
    every = [chr(ord("A") + i) for i in range(24)]
    boxes = {}
    for i, c in enumerate(every):
        if c not in ("A", "F", "O"):
            continue
        for n in range(1, 28):
            boxes[f"{c}{n}"] = QRect(22 * (n - 1), 20 * i, 20, 18)
    return [boxes]


class _Painted:
    """Counts the paintings from disk: each one ends in exactly one
    `_on_chart_measured(..., live=False)` (the painter of a measurement on
    disk), and nothing else calls it that way outside a session."""

    def __init__(self, tab, monkeypatch):
        self.n = 0
        real = tab._on_chart_measured

        def counting(ev, *, live=True, strip_fence=False):
            if not live:
                self.n += 1
            return real(ev, live=live, strip_fence=strip_fence)
        monkeypatch.setattr(tab, "_on_chart_measured", counting)

    def take(self) -> int:
        n, self.n = self.n, 0
        return n


@pytest.fixture
def setup(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    # The suite's settings store lives as long as the worker: start every
    # test from the defaults of what these tests change.
    for k in (*ms.PATCH_ERROR_LIMIT_KEYS.values(),
              *ms.NEIGHBOUR_RADIUS_KEYS.values(), ms.SAME_READING_KEY,
              "a_preference_nobody_reads_today"):
        s.unset(k)
    s.set("chartread_engine", "chromiq")
    tab = TabMeasure(ArgyllRunner(s), s)
    folder = tmp_path / "run1"
    tab._ti1_path = _write_chart(folder)
    ti3 = _write_ti3(folder)
    tab._patch_boxes = _boxes()
    # The arrival offer is a modal window; what accepting it does is
    # `_on_overlay_toggled(True)`, which a test below calls itself.
    monkeypatch.setattr(tab, "_maybe_offer_existing_overlay", lambda: None)
    tab._update_resume_availability()
    cb = tab._overlay_cb if tab._current_mode() == "guided" else tab._m_overlay_cb
    assert not cb.isHidden(), "the overlay box is offered for this measurement"
    cb.setChecked(True)
    tab.resize(1200, 900)
    painted = _Painted(tab, monkeypatch)
    tab._test_painted = painted

    def show():
        tab.show()
        for _ in range(8):
            qapp.processEvents()
        tab.hide()
        for _ in range(2):
            qapp.processEvents()
        return painted.take()

    # Settle once, the way any earlier visit leaves things: the first visit
    # may bring the confirmed-patches memory into line with the judge, which
    # is a change of a file the painting reads, so it is painted once more.
    show()
    show()
    yield tab, ti3, s, show, painted
    tab.close()


def _picture(tab):
    """What is on the preview, as plain values: per page, every patch's box,
    colours and outline, and its hover numbers."""
    pv = tab._preview

    def rect(r):
        return (r.x(), r.y(), r.width(), r.height())
    ov = {p: sorted((rect(it[0]), it[1].name(), it[2].name(), repr(it[3]))
                    for it in items) for p, items in pv._patch_overlay.items()}
    info = {p: sorted((rect(b), repr(sorted(d.items())))
                      for b, d in items) for p, items in pv._patch_info.items()}
    return ov, info


def _from_scratch(tab):
    """The same painting, made with nothing remembered from the last one
    (and not counted: `_Painted` is told to forget it)."""
    tab._preview.clear_patch_overlay()
    assert tab._show_overlay_from_existing_ti3()
    counter = getattr(tab, "_test_painted", None)
    if counter is not None:
        counter.n = max(0, counter.n - 1)
    return _picture(tab)


def _flags(tab):
    by_box = {(b.x(), b.y()): loc for loc, b in tab._patch_boxes[0].items()}
    return {by_box[(it[0].x(), it[0].y())]: it[3]
            for it in tab._preview._patch_overlay.get(0, [])}


# ---- the redundant paintings are gone ---------------------------------------

def test_an_arrival_paints_at_most_once_and_a_second_one_not_at_all(setup):
    tab, ti3, s, show, painted = setup
    ti3.write_text(ti3.read_text(encoding="utf-8"), encoding="utf-8")  # touched
    assert show() <= 1, "one arrival painted the whole overlay more than once"
    assert show() == 0, "nothing changed, and the overlay was painted again"
    seen = _picture(tab)
    assert seen[0], "the overlay is on the preview"
    assert seen == _from_scratch(tab), "the picture differs from a full repaint"


def test_accepting_the_arrival_offer_paints_nothing_more(setup):
    tab, ti3, s, show, painted = setup
    assert show() == 0
    # What OK in "This chart already has a measurement" applies.
    tab._sync_overlay_checkboxes(True)
    tab._on_overlay_toggled(True)
    assert painted.take() == 0
    assert _picture(tab)[0], "and the overlay is still there"


# ---- every input still paints, exactly once, with the new result ------------

def test_a_rewritten_measurement_is_painted_again(setup):
    tab, ti3, s, show, painted = setup
    before = _picture(tab)
    _write_ti3(ti3.parent, scale=1.07)        # other readings, same chart
    assert show() == 1
    after = _picture(tab)
    assert after != before, "the new readings did not reach the preview"
    assert after == _from_scratch(tab)
    assert show() == 0


@pytest.mark.parametrize("key,value", [
    (ms.PATCH_ERROR_LIMIT_KEYS[ms.ESTIMATED], 1.0),
    (ms.PATCH_ERROR_LIMIT_KEYS[ms.ACCURATE], 1.0),
    (ms.NEIGHBOUR_RADIUS_KEYS[ms.ESTIMATED], 3.0),
    (ms.SAME_READING_KEY, 0.5),
    ("a_preference_nobody_reads_today", 1),
])
def test_a_changed_preference_is_painted_again(setup, key, value):
    """The WHOLE preferences store is in the key, so a limit added later
    cannot be forgotten; a key nobody reads costs one painting, never a
    stale picture."""
    tab, ti3, s, show, painted = setup
    s.set(key, value)
    assert show() == 1
    assert _picture(tab) == _from_scratch(tab)
    assert show() == 0


def test_a_lower_limit_turns_patches_red_on_arrival(setup):
    tab, ti3, s, show, painted = setup
    red_before = sum(1 for f in _flags(tab).values() if f is pf.FLAG_RED)
    for k in ms.PATCH_ERROR_LIMIT_KEYS.values():
        s.set(k, 1.0)
    assert show() == 1
    red_after = sum(1 for f in _flags(tab).values() if f is pf.FLAG_RED)
    assert red_after > red_before


def test_preferences_ok_paints_a_changed_limit_once(setup):
    """The main window calls `refresh_patch_flags` when Preferences closes
    with OK, on a hidden tab too."""
    tab, ti3, s, show, painted = setup
    tab.refresh_patch_flags()
    assert painted.take() == 0, "OK with nothing changed"
    s.set(ms.PATCH_ERROR_LIMIT_KEYS[ms.ESTIMATED], 2.0)
    tab.refresh_patch_flags()
    assert painted.take() == 1


def test_a_re_read_confirmed_in_the_memory_is_painted_again(setup):
    tab, ti3, s, show, painted = setup
    assert _flags(tab)["A17"] is pf.FLAG_RED
    cp.write(ti3, {"A17": {"kind": "confirmed", "de": 105.0, "prev_de": 104.0,
                           "exp_lab": [1, 2, 3], "meas_lab": [4, 5, 6],
                           "shift": [3, 3, 3], "standout": None}}, "patch")
    assert show() == 1
    assert _flags(tab)["A17"] == pf.FLAG_CONFIRMED
    assert _picture(tab) == _from_scratch(tab)


def test_another_chart_is_painted(setup, tmp_path):
    tab, ti3, s, show, painted = setup
    before = _picture(tab)
    tab._ti1_path = _write_chart(tmp_path / "run2")
    _write_ti3(tmp_path / "run2", scale=0.93)
    assert show() == 1
    assert _picture(tab) != before
    assert _picture(tab) == _from_scratch(tab)


def test_the_reading_mode_is_part_of_it(setup, monkeypatch):
    """Strips are judged against their strip, patch by patch is not (#182
    K3): the mode set on the panel decides when the memory does not."""
    tab, ti3, s, show, painted = setup
    monkeypatch.setattr(tab, "_is_pbp_checked", lambda: True)
    assert show() == 1
    assert _picture(tab) == _from_scratch(tab)


def test_a_cleared_preview_is_painted_again(setup):
    """Whatever replaced the painting on screen, a session, a chart reload,
    the box unticked, the next asking paints."""
    tab, ti3, s, show, painted = setup
    tab._preview.clear_patch_overlay()
    assert show() == 1
    assert _picture(tab)[0]


def test_a_memory_started_again_elsewhere_is_painted_again(setup):
    tab, ti3, s, show, painted = setup
    tab._reset_flag_judge()
    assert show() == 1


def test_never_skipped_while_a_session_runs(setup):
    tab, ti3, s, show, painted = setup
    tab._session_live = True
    try:
        assert tab._overlay_repaint_key(ti3) is None
    finally:
        tab._session_live = False


def test_a_settings_stand_in_never_skips(qapp, tmp_path):
    """A settings object that cannot be listed (the suite's stand-ins) is
    painted every time, as before."""
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure

    class _S:
        def get(self, k, d=None):
            return {"chartread_engine": "chromiq"}.get(k, d)

        def set(self, k, v):
            pass
    tab = TabMeasure(ArgyllRunner(_S()), _S())
    tab._ti1_path = _write_chart(tmp_path)
    ti3 = _write_ti3(tmp_path)
    tab._patch_boxes = _boxes()
    assert tab._overlay_repaint_key(ti3) is None


def test_a_page_of_patch_geometry_replaced_in_place_is_painted_again(setup):
    tab, ti3, s, show, painted = setup
    tab._patch_boxes[0] = dict(tab._patch_boxes[0])
    assert show() == 1


# ---- a verification: its record, its run's profile, its calibration --------

class _Ctl:
    """The bar's controller as far as the Measure tab asks it."""

    def __init__(self, root, run_id, vid):
        from core.measurement_target import (MeasurementTarget,
                                             RUN_TYPE_VERIFICATION)
        self.root = root
        self.target = MeasurementTarget(run_type=RUN_TYPE_VERIFICATION,
                                        profile_run=run_id,
                                        verification_id=vid)

    def project_or_none(self):
        return Project.load(self.root)


def _fake_live_expected(chart, record_ti3, run, *, bin_dir):
    """A prediction made from exactly the files the real one reads: the run's
    profile, the print record and the calibration it names. Every patch's
    expected colour moves with them, so a stale one shows in the picture."""
    import hashlib
    import json
    from workflow.verification_print import read_print_record
    from workflow.verify_expected import SOURCE_PREDICTION, LiveExpected
    # CONTENT ONLY, never the test's temp-folder path: with the path in the
    # hash an unlucky folder name gave the old and the new record the same
    # factor about one run in two hundred (seen twice in 22 loaded rounds).
    # Without it every input below maps to the same factor in every run, and
    # each test's before and after were checked to differ.
    h = hashlib.md5()
    prof = Path(run.built_profile_icc())
    h.update(prof.read_bytes() if prof.is_file() else b"-")
    rec = read_print_record(Path(record_ti3)) or {}
    cal = Path(str(rec.get("cal_from") or "-"))
    shown = dict(rec)
    if "cal_from" in shown:
        shown["cal_from"] = cal.name
    h.update(json.dumps(shown, sort_keys=True).encode())
    h.update(cal.read_bytes() if cal.is_file() else b"-")
    f = 0.9 + (int(h.hexdigest()[:8], 16) % 2000) / 10000.0
    from tests.test_k182_k3_k4_overlay_and_memory import KNUT
    return LiveExpected(SOURCE_PREDICTION, "test",
                        {loc: tuple(v * f for v in e) for loc, e, _m in KNUT})


@pytest.fixture
def verifying(qapp, tmp_path, monkeypatch):
    """A dated verification of run1, read and painted from disk, with a
    second date and a second run holding a measurement too."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    import workflow.verify_expected as ve
    monkeypatch.setattr(ve, "live_expected", _fake_live_expected)
    root = tmp_path / "P"
    proj = Project.create(root, "P")
    cal = tmp_path / "elsewhere" / "printer.cal"
    cal.parent.mkdir()
    cal.write_text("CAL 1\n", encoding="utf-8")
    vids = {}
    for rid, scale in (("run1", 1.0), ("run2", 0.95)):
        run = proj.run(rid) if rid == "run1" else proj.new_run()
        run.dir.mkdir(parents=True, exist_ok=True)
        run.profile_icc.write_bytes(b"profile of " + rid.encode())
        vdir = run.verifications_dir
        _write_chart(vdir, stem=run.verify_stem)
        for n, vid in enumerate(("2026-11-01_100000", "2026-11-02_100000")):
            v = run.verification(vid)
            v.dir.mkdir(parents=True, exist_ok=True)
            _write_ti3(v.dir, stem=v.stem, scale=scale + 0.02 * n)
            (v.dir / f"{v.stem}.print.json").write_text(
                '{"route": "chromiq", "cal_from": "%s"}' % cal,
                encoding="utf-8")
        vids[run.id] = run
    s = AppSettings()
    s.set("chartread_engine", "chromiq")
    tab = TabMeasure(ArgyllRunner(s), s)
    run1 = vids["run1"]
    tab._target_ctl = _Ctl(root, run1.id, "2026-11-01_100000")
    tab._ti1_path = run1.verifications_dir / f"{run1.verify_stem}.ti2"
    tab._patch_boxes = _boxes()
    monkeypatch.setattr(tab, "_maybe_offer_existing_overlay", lambda: None)
    tab._update_resume_availability()
    cb = tab._overlay_cb if tab._current_mode() == "guided" else tab._m_overlay_cb
    assert not cb.isHidden(), "the dated verification's overlay is offered"
    cb.setChecked(True)
    tab.resize(1200, 900)
    painted = _Painted(tab, monkeypatch)
    tab._test_painted = painted

    def show():
        tab.show()
        for _ in range(8):
            qapp.processEvents()
        tab.hide()
        for _ in range(2):
            qapp.processEvents()
        return painted.take()
    show()
    show()
    assert tab._expected_is_predicted(), "painted against the prediction"
    assert show() == 0
    yield tab, run1, vids["run2"], cal, show
    tab.close()


def _record(run1, vid="2026-11-01_100000"):
    v = run1.verification(vid)
    return v.dir / f"{v.stem}.print.json"


def test_a_rewritten_run_profile_is_painted_again(verifying):
    tab, run1, run2, cal, show = verifying
    before = _picture(tab)
    run1.profile_icc.write_bytes(b"another profile")
    assert show() == 1
    assert _picture(tab) != before, "the new prediction did not reach it"
    assert _picture(tab) == _from_scratch(tab)
    assert show() == 0


def test_a_rewritten_print_record_is_painted_again(verifying):
    tab, run1, run2, cal, show = verifying
    before = _picture(tab)
    _record(run1).write_text('{"route": "chromiq", "cal_from": "%s", '
                             '"colour": "raw"}' % cal, encoding="utf-8")
    assert show() == 1
    assert _picture(tab) != before
    assert _picture(tab) == _from_scratch(tab)


def test_a_record_in_the_dated_chart_snapshot_is_painted_again(verifying):
    """`read_print_record` reads the dated folder's chart/ snapshot when
    there is none beside the measurement."""
    tab, run1, run2, cal, show = verifying
    rec = _record(run1)
    snap = rec.parent / "chart" / rec.name
    snap.parent.mkdir()
    snap.write_text(rec.read_text(encoding="utf-8"), encoding="utf-8")
    rec.unlink()
    assert show() == 1
    before = _picture(tab)
    snap.write_text('{"route": "chromiq", "cal_from": "%s", "x": 1}' % cal,
                    encoding="utf-8")
    assert show() == 1
    assert _picture(tab) != before
    assert _picture(tab) == _from_scratch(tab)


@pytest.mark.parametrize("how", ["edited", "deleted"])
def test_the_recorded_calibration_file_is_part_of_it(verifying, how):
    tab, run1, run2, cal, show = verifying
    before = _picture(tab)
    if how == "edited":
        cal.write_text("CAL 2, another calibration\n", encoding="utf-8")
    else:
        cal.unlink()
    assert show() == 1
    assert _picture(tab) != before
    assert _picture(tab) == _from_scratch(tab)
    assert show() == 0


def test_another_date_is_painted(verifying):
    tab, run1, run2, cal, show = verifying
    before = _picture(tab)
    tab._target_ctl.target.verification_id = "2026-11-02_100000"
    assert show() == 1
    assert _picture(tab) != before
    assert _picture(tab) == _from_scratch(tab)


def test_another_run_is_painted(verifying):
    tab, run1, run2, cal, show = verifying
    before = _picture(tab)
    tab._target_ctl.target.profile_run = run2.id
    tab._ti1_path = run2.verifications_dir / f"{run2.verify_stem}.ti2"
    assert show() == 1
    assert _picture(tab) != before
    assert _picture(tab) == _from_scratch(tab)


def test_a_staged_resume_counts_its_dated_folders_record(verifying):
    """A dated verification staged beside the chart for a resume is described
    by its dated folder's record (`_record_ti3_for`): that folder's files are
    in the key, not only the path."""
    tab, run1, run2, cal, show = verifying
    v = run1.verification("2026-11-01_100000")
    beside = tab._ti1_path.with_suffix(".ti3")
    shutil.copyfile(v.measurement_ti3, beside)
    tab._staged_verification_ti3 = beside
    tab._staged_from = v.measurement_ti3
    k1 = tab._overlay_repaint_key(beside)
    _record(run1).write_text('{"route": "chromiq", "y": 2}', encoding="utf-8")
    assert tab._overlay_repaint_key(beside) != k1
    k2 = tab._overlay_repaint_key(beside)
    snap = v.dir / "chart" / _record(run1).name
    snap.parent.mkdir()
    snap.write_text("{}", encoding="utf-8")
    assert tab._overlay_repaint_key(beside) != k2


def test_never_skipped_while_an_fd9_scan_is_live(setup):
    tab, ti3, s, show, painted = setup
    tab._fd9_live = True
    try:
        assert tab._overlay_repaint_key(ti3) is None
    finally:
        tab._fd9_live = False
