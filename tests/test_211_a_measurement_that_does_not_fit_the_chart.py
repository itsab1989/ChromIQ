"""#211: a measurement whose readings do not sit where the chart prints them.

vezar (4.3.5-beta.7, Windows, ColorMunki, Russian UI) converted an i1Profiler
measurement and imported it into run2. i1Profiler names its patches by its own
sheet: A1 … T21 on EACH of its four pages, so the file held 1,680 rows under
420 names, while the run's chart lays the same 1,680 patches out on strips A to
CB. After Analyse Profile Quality he chose "Guide me through refinement", read
four patches and pressed Stop, "Save and stop":

* ChromIQ's engine (and ArgyllCMS chartread, the same code) resumes BY
  LOCATION: for every patch of the chart it takes the FIRST row whose
  ``SAMPLE_LOC`` matches and writes one row per patch, with the chart's id and
  device values. So the first reading of each of the 420 names went onto
  whatever ChromIQ's chart prints there (another patch), the other 1,260 were
  dropped, and the file came out with 424 rows;
* the shrink check (§3b) put the old file back, so nothing was lost, but the
  four new readings went with it ("This session ended with fewer readings than
  it started with").

Measuring a sheet another program printed is out of scope (Basti,
2026-10-15). What ChromIQ owes is to notice BEFORE measuring and say so:
`measurement_pairing.resume_fit` and `TabMeasure._blocked_by_a_misfitting_
measurement`, with M-RESUME-LAYOUT-DIFFERS. And a measurement ChromIQ made
itself must never lose a row to a resume: the real engine is driven below.
"""
from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from workflow.measurement_pairing import resume_fit       # noqa: E402

_F = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"
STRIPS = ["A", "B", "C", "D"]
PER = 6
LOCS = [f"{s}{p}" for s in STRIPS for p in range(1, PER + 1)]


def _write(path: Path, rows, kind="CTI3", fields=_F) -> Path:
    path.write_text(
        f"{kind}\n\nDESCRIPTOR \"x\"\nNUMBER_OF_FIELDS {len(fields.split())}\n"
        f"BEGIN_DATA_FORMAT\n{fields}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def _chart(tmp: Path) -> Path:
    # A randomised chart: the id printed at a place is not its row number.
    order = list(range(1, len(LOCS) + 1))[::-1]
    rows = [f'{sid} "{loc}" {sid} {sid} {sid} 1 1 1'
            for sid, loc in zip(order, LOCS)]
    return _write(tmp / "chart.ti2", rows, "CTI2")


def _chart_map(ti2: Path) -> "dict[str, str]":
    out = {}
    for ln in ti2.read_text().split("BEGIN_DATA\n", 1)[1].splitlines():
        f = ln.split()
        if len(f) > 2:
            out[f[0]] = f[1].strip('"')
    return out


def _measurement(tmp: Path, ti2: Path, *, loc_of=None, name="chart.ti3"):
    at = _chart_map(ti2)
    rows = []
    for sid in sorted(at, key=int):
        loc = loc_of(int(sid), at[sid]) if loc_of else at[sid]
        rows.append(f'{sid} "{loc}" {sid} {sid} {sid} 20 21 22')
    return _write(tmp / name, rows)


# ---- the check -------------------------------------------------------------

def test_a_measurement_chromiq_made_fits(tmp_path):
    ti2 = _chart(tmp_path)
    fit = resume_fit(_measurement(tmp_path, ti2), ti2)
    assert fit.fits and fit.wrong == 0 and fit.rows == len(LOCS)


def test_a_partial_measurement_chromiq_made_fits(tmp_path):
    ti2 = _chart(tmp_path)
    ti3 = _measurement(tmp_path, ti2)
    text = ti3.read_text().splitlines()
    keep = [ln for ln in text if not ln.startswith(("3 ", "4 ", "5 "))]
    ti3.write_text("\n".join(keep).replace(
        f"NUMBER_OF_SETS {len(LOCS)}", f"NUMBER_OF_SETS {len(LOCS) - 3}") + "\n")
    assert resume_fit(ti3, ti2).fits


def test_issue_211s_shape_does_not_fit(tmp_path):
    """Four pages of i1Profiler's own names: every name used four times, so
    three rows of every four would be dropped, and the first goes onto the
    patch this chart prints there, which is another one."""
    ti2 = _chart(tmp_path)
    page = [f"{s}{p}" for s in "AB" for p in range(1, 4)]       # 6 names

    def i1profiler(sid, _loc):
        return page[(sid - 1) % len(page)]
    fit = resume_fit(_measurement(tmp_path, ti2, loc_of=i1profiler), ti2)
    assert not fit.fits
    assert fit.rows == len(LOCS)
    # 18 repeats, plus every first use that names a place where the chart
    # prints a different patch.
    assert fit.wrong >= len(LOCS) - len(page)


def test_the_same_places_with_other_patches_do_not_fit(tmp_path):
    """No row lost, every name once, and still wrong: the readings would land
    on other patches. Ids are the witness."""
    ti2 = _chart(tmp_path)
    fit = resume_fit(_measurement(
        tmp_path, ti2, loc_of=lambda sid, _l: LOCS[sid - 1]), ti2)
    assert not fit.fits and fit.wrong > 0


def test_a_place_the_chart_does_not_have_does_not_fit(tmp_path):
    ti2 = _chart(tmp_path)
    fit = resume_fit(_measurement(
        tmp_path, ti2, loc_of=lambda sid, loc: "Z9" if sid == 2 else loc), ti2)
    assert not fit.fits and fit.wrong == 1


def test_a_file_with_no_locations_does_not_fit(tmp_path):
    ti2 = _chart(tmp_path)
    ti3 = _write(tmp_path / "m.ti3", [f"{i} 1 1 1 20 21 22" for i in range(1, 5)],
                 fields="SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z")
    fit = resume_fit(ti3, ti2)
    assert not fit.fits and fit.no_locations and fit.wrong == 4


def test_unreadable_files_are_left_to_the_other_checks(tmp_path):
    ti2 = _chart(tmp_path)
    assert resume_fit(tmp_path / "gone.ti3", ti2) is None
    empty = _write(tmp_path / "e.ti3", [])
    assert resume_fit(empty, ti2) is None


# ---- the Measure tab stops BEFORE anything happens --------------------------

@pytest.fixture
def tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    run = tmp_path / "run"
    run.mkdir()
    ti2 = _chart(run)
    (run / "chart.ti1").write_text("CTI1\n", encoding="utf-8")
    t._ti1_path = run / "chart.ti1"
    shown: list = []
    t._say_on_screen = lambda title, body: shown.append((title, body))
    yield t, run, ti2, shown
    t.deleteLater()


class _P:
    def __init__(self, resume):
        self.resume = resume


def test_the_tab_refuses_issue_211s_file_and_says_why(tab):
    t, run, ti2, shown = tab
    page = [f"{s}{p}" for s in "AB" for p in range(1, 4)]
    _measurement(run, ti2, loc_of=lambda sid, _l: page[(sid - 1) % 6])
    before = sorted(p.name for p in run.iterdir())
    assert t._blocked_by_a_misfitting_measurement(_P(True)) is True
    assert len(shown) == 1
    title, body = shown[0]
    assert title == "This measurement does not fit this chart"
    assert f"of its {len(LOCS)} readings" in body
    assert "i1Profiler" in body and "Build Profile" in body
    assert "Nothing has been measured, and nothing has been changed." in body
    assert sorted(p.name for p in run.iterdir()) == before, \
        "nothing archived, nothing written"
    assert "This measurement does not fit this chart" in \
        t._log.toPlainText()


def test_the_tab_lets_a_fitting_resume_through(tab):
    t, run, ti2, shown = tab
    _measurement(run, ti2)
    assert t._blocked_by_a_misfitting_measurement(_P(True)) is False
    assert shown == []


def test_a_fresh_measurement_is_never_asked(tab):
    """Without Refine / resume nothing is resumed; the replace question and
    the archive deal with the old file as before."""
    t, run, ti2, shown = tab
    page = [f"{s}{p}" for s in "AB" for p in range(1, 4)]
    _measurement(run, ti2, loc_of=lambda sid, _l: page[(sid - 1) % 6])
    assert t._blocked_by_a_misfitting_measurement(_P(False)) is False
    assert shown == []


def test_one_reading_has_its_own_sentence(tab):
    t, run, ti2, shown = tab
    _measurement(run, ti2, loc_of=lambda sid, loc: "Z9" if sid == 2 else loc)
    assert t._blocked_by_a_misfitting_measurement(_P(True)) is True
    assert f"1 of its {len(LOCS)} readings is not filed" in shown[0][1]


def test_on_start_asks_before_every_question_that_writes_and_the_archive():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    i = src.index("self._blocked_by_a_misfitting_measurement()")
    assert i < src.index("self._snapshot_verification_chart()")
    assert i < src.index("self._confirm_replacing_measurement()")
    assert i < src.index("self._archive_measurement_before_replacing()")
    assert i < src.index("self._begin_session_guard(")
    assert i < src.index("self._manager.start(")


# ---- the real engine: what a resume keeps ------------------------------------

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")


def _engine_chart(tmp: Path) -> Path:
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    printtarg = shutil.which("printtarg") or str(ARGYLL / "printtarg")
    if not Path(targen).exists() or not Path(printtarg).exists():
        pytest.skip("Argyll targen/printtarg not available")
    base = tmp / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", "-f30",
                    str(base)], check=True, capture_output=True, cwd=tmp,
                   timeout=120)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", str(base)],
                   check=True, capture_output=True, cwd=tmp, timeout=120)
    return base


def _read_whole_chart(base: Path, replay: Path) -> None:
    s = ReplaySession(base, replay, ["-p"])
    try:
        ev = s.wait_event("spot_ready", timeout=30)
        while not ev.get("all_done"):
            i = s.event_index()
            s.send(cmd="read")
            s.wait_event("patch_read", after=i, timeout=30)
            ev = s.wait_event("spot_ready", after=i, timeout=30)
        s.send(cmd="done")
        s.finish(timeout=30)
    finally:
        if s.proc.poll() is None:
            s.proc.kill()


def _rows(ti3: Path) -> "list[list[str]]":
    body = ti3.read_text(encoding="latin-1").split("BEGIN_DATA\n")[-1]
    body = body.split("END_DATA")[0]
    return [ln.split() for ln in body.splitlines() if ln.strip()]


def _save_and_stop(s: ReplaySession) -> None:
    """ChromIQ's Save and stop on the engine: a quit, and a second one once
    the give-up prompt is up (`MeasureManager`, "the printed give-up prompt
    arrived; sending the second key")."""
    i = s.event_index()
    s.send(cmd="quit")
    s.wait_event("strip_interrupted", after=i, timeout=30)
    s.send(cmd="quit")
    s.finish(timeout=30)


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_a_refinement_of_a_chromiq_measurement_keeps_every_row(tmp_path):
    """Patch by patch, Refine / resume on a finished measurement ChromIQ made,
    one patch re-read, Stop and Save and stop: every row is still there, and
    the re-read patch's old reading is REPLACED by the new one."""
    base = _engine_chart(tmp_path)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    _read_whole_chart(base, replay)
    ti3 = base.with_suffix(".ti3")
    full = _rows(ti3)
    n = len(full)
    assert n >= 30
    assert resume_fit(ti3, base.with_suffix(".ti2")).fits
    # Spoil one reading, so its re-read is visible.
    victim = full[5]
    text = ti3.read_text(encoding="latin-1")
    spoiled = " ".join(victim[:5] + ["1.11111", "2.22222", "3.33333"]
                       + victim[8:])
    ti3.write_text(text.replace(" ".join(victim), spoiled, 1),
                   encoding="latin-1")
    loc = victim[1].strip('"')
    s = ReplaySession(base, replay, ["-p", "-r"])
    try:
        s.wait_event("spot_ready", timeout=30)
        i = s.event_index()
        s.send(cmd="goto", patch=loc)
        s.wait_event("spot_ready", after=i, timeout=30, loc=loc)
        i = s.event_index()
        s.send(cmd="read")
        s.wait_event("saved", after=i, timeout=30)
        _save_and_stop(s)
    finally:
        if s.proc.poll() is None:
            s.proc.kill()
    after = _rows(ti3)
    assert len(after) == n, "a resume of ChromIQ's own measurement lost rows"
    again = {r[1].strip('"'): r for r in after}[loc]
    assert again[5:8] != ["1.11111", "2.22222", "3.33333"], \
        "the re-read patch keeps its old reading"
    assert {r[1] for r in after} == {r[1] for r in full}


@pytest.mark.skipif(not HELPER.exists(),
                    reason="chromiq-chartread helper not built")
def test_the_engine_collapses_issue_211s_shape_which_is_why_it_is_refused(
        tmp_path):
    """The root cause, measured on the real engine: a file whose names repeat
    comes out of a resume with one row per name. ChromIQ therefore never
    starts that resume (above)."""
    base = _engine_chart(tmp_path)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay)
    _read_whole_chart(base, replay)
    ti3 = base.with_suffix(".ti3")
    rows = _rows(ti3)
    n = len(rows)
    half = n // 2
    # i1Profiler's page names: the second half reuses the first half's names.
    text = ti3.read_text(encoding="latin-1")
    for k in range(half, 2 * half):
        old = " ".join(rows[k])
        new = " ".join([rows[k][0], rows[k - half][1]] + rows[k][2:])
        text = text.replace(old, new, 1)
    ti3.write_text(text, encoding="latin-1")
    fit = resume_fit(ti3, base.with_suffix(".ti2"))
    assert not fit.fits and fit.wrong >= half
    s = ReplaySession(base, replay, ["-p", "-r"])
    try:
        ev = s.wait_event("spot_ready", timeout=30)
        i = s.event_index()
        s.send(cmd="read")
        s.wait_event("saved", after=i, timeout=30)
        _save_and_stop(s)
    finally:
        if s.proc.poll() is None:
            s.proc.kill()
    assert len(_rows(ti3)) < n, (
        "the engine kept every row; if that is now true, the refusal can be "
        "reconsidered")
    assert ev["loc"]


def test_without_parameters_the_resume_tick_decides(tab):
    t, run, ti2, shown = tab
    page = [f"{s}{p}" for s in "AB" for p in range(1, 4)]
    _measurement(run, ti2, loc_of=lambda sid, _l: page[(sid - 1) % 6])
    for cb in (t._resume_cb, t._m_resume_cb):
        cb.setChecked(False)
    assert t._blocked_by_a_misfitting_measurement() is False
    for cb in (t._resume_cb, t._m_resume_cb):
        cb.setChecked(True)
    assert t._blocked_by_a_misfitting_measurement() is True
