"""#182 beta 39, K28a: four of Knut's rulings of 2026-09-23 (5795087247).

1. **E8**: evenness is judged in ABSOLUTE Lab, whatever the print's intent.
2. **B8-483**: the grey ramp's required steps are picked roughly evenly
   spaced, within a few percent of full scale (`GREY_SPACING_TOL`, 4).
3. **R2 / G5**: the verification pre-flight carries the full paragraph, in a
   box wide enough for it, and falls back to one line on a short screen.
4. The folder guide ("Where are my files?") shows the ChromIQ folder's own
   `reports/` and `old/`, where a report across projects goes when deleted.

Every test names the mutation it was proved red against.
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow.ti3_analysis import _lab_to_xyz_array            # noqa: E402

from tests.test_evenness_across_the_sheet import (             # noqa: E402
    _write_chart, _write_sheet)

#: A real paper, not the ideal white the design aims describe: L* 95.5 with a
#: slight blue from brighteners.
PAPER_LAB = (95.5, 0.5, -3.0)
D50 = np.array([96.42, 100.0, 82.49])


# ===========================================================================
# 1. E8
# ===========================================================================
def _blotch(page, s, r, rng):
    """One ninth (the last band of strips and of rows) 1.35 L* lighter."""
    d = rng.normal(0, 0.25, 3)
    if s >= 12 and r >= 12:
        d[0] += 1.35
    return d


def _drift(page, s, r, rng):
    """b* drifting 2.2 from one side of the sheet to the other."""
    d = rng.normal(0, 0.25, 3)
    d[2] += (s / 17 - 0.5) * 2.2
    return d


def _sheet(tmp_path: Path, name: str, residual, *, intent: str,
           paper=None) -> Path:
    """An 18 by 18 chart and its measured sheet. With *paper*, the sheet is
    what a print that MAPS PAPER WHITE reads on that paper: every reading's
    XYZ scaled by paper / D50."""
    ti2, where = _write_chart(tmp_path / name, pages=(18,), rows=18, seed=5)
    # …with a bare-paper patch, as every real chart has: the report takes the
    # LIGHTEST reading as the paper white.
    text = ti2.read_text(encoding="utf-8").splitlines()
    for k, ln in enumerate(text):
        if ln.startswith("1 \""):
            loc = ln.split()[1]
            text[k] = f"1 {loc} 100.0000 100.0000 100.0000 96.420000 " \
                      f"100.000000 82.490000"
    ti2.write_text("\n".join(text), encoding="utf-8")
    where = [(sid, pg, s, r, (np.array([100.0, 100.0, 100.0]) if sid == "1"
                              else rgb)) for sid, pg, s, r, rgb in where]
    ti3 = _write_sheet(ti2, where, residual)
    if paper is not None:
        scale = _lab_to_xyz_array(np.asarray([paper], float))[0] / D50
        out = []
        for ln in ti3.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            if len(parts) == 7 and parts[0].isdigit():
                xyz = np.asarray([float(v) for v in parts[4:]]) * scale
                ln = " ".join(parts[:4] + [f"{v:.6f}" for v in xyz])
            out.append(ln)
        ti3.write_text("\n".join(out), encoding="utf-8")
    (ti3.parent / f"{ti3.stem}.print.json").write_text(json.dumps({
        "colour": "through-profile", "intent": intent,
        "route": "chromiq"}), encoding="utf-8")
    return ti3


def test_a_white_mapped_sheet_is_read_as_measured_for_evenness(tmp_path):
    """The ΔE00 rows of a relative-intent sheet are read media-relative (that
    is unchanged); the evenness block is computed from the readings AS
    MEASURED, against the aims carried onto the paper.

    MUTATION: hand `evenness_block` the media-relative `lab` again (the beta 38
    wiring) and this goes red: the block's numbers are no longer those of the
    absolute readings."""
    ti3 = _sheet(tmp_path, "rel", _blotch, intent="relative", paper=PAPER_LAB)
    rep = MR.build_report(ti3)
    assert rep["yardstick"] == "media-relative"
    ev = rep["evenness"]
    assert ev["yardstick"] == "absolute"
    assert ev["aims"] == "on_the_paper"
    # the same arithmetic, asked directly of the absolute readings
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(ti3)
    absolute = [MR.xyz_to_lab((x / 100, y / 100, z / 100))
                for x, y, z in data.xyz]
    white = np.asarray(data.xyz[MR.lightest_and_darkest(absolute)[0]], float)
    ref = MR._reference_labs(ti3.with_suffix(".ti2"))
    want = MR.evenness_block(
        absolute, MR.aims_on_the_paper(ref, white), data.sample_ids,
        MR._rgb_to_0_100(np.asarray(data.rgb, float)), ti3.with_suffix(".ti2"))
    assert (ev["pairwise"], ev["from_mean"]) == (want["pairwise"],
                                                 want["from_mean"])


def test_the_paper_is_not_counted_as_unevenness(tmp_path):
    """A relative print on a real paper reads, for evenness, what the same
    sheet printed absolute on an ideal paper reads: the paper's own tint is
    one offset for the whole sheet, not a difference between places.

    MUTATION: give evenness the design aims unchanged (`ref` instead of
    `evenness_ref`, i.e. absolute readings against an ideal white paper) and
    this goes red: the sheet's own noise rises several-fold (measured here
    0.19 against 0.87) and the verdicts move."""
    rel = MR.build_report(_sheet(tmp_path, "rel", _drift, intent="relative",
                                 paper=PAPER_LAB))["evenness"]
    ideal = MR.build_report(_sheet(tmp_path, "abs", _drift,
                                   intent="absolute"))["evenness"]
    assert ideal["aims"] == "as_designed"
    assert abs(rel["pairwise"] - ideal["pairwise"]) < 0.1, (rel, ideal)
    assert abs(rel["noise_pairwise_p95"] - ideal["noise_pairwise_p95"]) < 0.1
    assert rel["noise_pairwise_p95"] < 0.8, rel


def test_an_absolute_sheet_keeps_its_aims_as_designed(tmp_path):
    """Nothing changes for a sheet the report already reads absolute.

    MUTATION: carry the aims onto the paper for every sheet (drop the
    white-mapping condition) and this goes red: the design aims of an
    absolute print already describe the absolute colour."""
    ti3 = _sheet(tmp_path, "abs", _blotch, intent="absolute")
    rep = MR.build_report(ti3)
    assert rep["yardstick"] == "absolute"
    assert rep["evenness"]["aims"] == "as_designed"
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(ti3)
    lab = [MR.xyz_to_lab((x / 100, y / 100, z / 100)) for x, y, z in data.xyz]
    want = MR.evenness_block(lab, MR._reference_labs(ti3.with_suffix(".ti2")),
                             data.sample_ids,
                             MR._rgb_to_0_100(np.asarray(data.rgb, float)),
                             ti3.with_suffix(".ti2"))
    assert rep["evenness"]["from_mean"] == want["from_mean"]


def test_aims_on_the_paper_is_one_scale_for_every_patch():
    """The paper-white patch's own aim lands on the paper exactly, and the
    ideal white paper changes nothing.

    MUTATION: divide by the paper instead of multiplying (the media-relative
    direction) and this goes red."""
    ref = {"w": (100.0, 0.0, 0.0), "g": (50.0, 10.0, -20.0)}
    paper = _lab_to_xyz_array(np.asarray([PAPER_LAB], float))[0]
    on = MR.aims_on_the_paper(ref, paper)
    assert np.allclose(on["w"], PAPER_LAB, atol=0.05), on["w"]
    same = MR.aims_on_the_paper(ref, D50)
    assert np.allclose(same["g"], ref["g"], atol=1e-6)


def test_the_help_text_says_evenness_is_read_as_measured():
    """MUTATION: drop the sentence from `_D_EVENNESS` and this goes red."""
    assert "The readings are taken as measured" in CS._D_EVENNESS
    assert "carried onto the paper" in CS._D_EVENNESS


# ===========================================================================
# 2. B8-483: the grey ramp's steps roughly evenly spaced
# ===========================================================================
def _grey_block(levels):
    rgb = np.asarray([[v, v, v] for v in levels] +
                     [[90.0, 10.0, 10.0]], dtype=float)
    ids = [str(i) for i in range(len(rgb))]
    lab = [(float(v), 0.0, 0.0) for v in levels] + [(50.0, 60.0, 40.0)]
    ref = {sid: tuple(lab[i]) for i, sid in enumerate(ids)}
    return MR.grey_balance_block(rgb, lab, ref, ids)


def test_a_bunched_ramp_is_refused_and_says_where():
    """Knut's own example: black, then seven steps inside 3.6 units at the
    light end. Eight distinct steps, white and black reached, and refused.

    MUTATION: delete the `pick_even_grey_steps` branch in
    `grey_balance_block` and this goes red (the block is eligible)."""
    b = _grey_block((0.0, 90.0, 90.6, 91.2, 91.8, 92.4, 93.0, 93.6))
    assert b["levels"] == 8
    assert not b["eligible"]
    assert b["reason"] == MR.REASON_GREY_STEPS_BUNCHED
    assert b["missing_level"] == 13.4          # 93.6 / 7, nothing near it


def test_an_even_ramp_with_more_steps_than_required_passes():
    """0, 10 … 100 holds no EIGHT steps within 4 of an 8-step spacing (14.3
    is 4.3 from 10 and 20), yet it is as evenly spaced as a ramp can be.

    MUTATION: try only m = GREY_MIN_LEVELS in `pick_even_grey_steps` and this
    goes red."""
    b = _grey_block(tuple(float(v) for v in range(0, 101, 10)))
    assert b["eligible"], b
    assert b["picked_levels"] == [float(v) for v in range(100, -1, -10)]


def test_the_tolerance_is_four_and_inclusive():
    """A step exactly 4.0 from its even position counts; 4.1 does not.

    MUTATION: `>` to `>=` in `pick_even_grey_steps`, or GREY_SPACING_TOL to
    3.9, and the first assertion goes red; 4.2 and the second does."""
    assert MR.GREY_SPACING_TOL == 4.0
    # 0 to 98 in steps of exactly 14, so the distances are exact decimals
    even = [14.0 * k for k in range(8)]
    on = list(even)
    on[3] = 46.0                         # 4.0 from 42
    assert MR.pick_even_grey_steps(on)[0] is not None
    off = list(even)
    off[3] = 46.1                        # 4.1 from 42
    assert MR.pick_even_grey_steps(off)[0] is None


def test_the_statistics_still_cover_every_grey():
    """The rule decides whether the ramp meets the step count; the average
    and largest ΔCh are still over every grey (CH-10, confirmed).

    MUTATION: average over `picked_levels` only and this goes red."""
    levels = tuple(float(v) for v in range(0, 101, 5))      # 21 steps
    rgb = np.asarray([[v, v, v] for v in levels], dtype=float)
    ids = [str(i) for i in range(len(levels))]
    ref = {sid: (float(v), 0.0, 0.0) for sid, v in zip(ids, levels)}
    # a cast of 2 on the 60 step only, which is not one of the 8 picked
    lab = [(float(v), 2.0 if v == 60.0 else 0.0, 0.0) for v in levels]
    b = MR.grey_balance_block(rgb, lab, ref, ids)
    assert b["eligible"] and 60.0 not in b["picked_levels"], b
    assert b["max"] == 2.0


def test_no_built_in_chart_loses_its_grey_rows():
    """Measured before the rule was built: 181 built-in charts had an eligible
    grey ramp, and every one of them still has.

    MUTATION: GREY_SPACING_TOL to 2.0 without the m >= n search and this
    goes red on 28 charts."""
    import glob
    from workflow.ti3_analysis import parse_ti3
    root = Path(__file__).resolve().parents[1] / "assets"
    files = sorted(glob.glob(str(root / "charts" / "**" / "*.ti1"),
                             recursive=True))
    files += glob.glob(str(root / "verification" / "*.ti1"))
    eligible, refused = 0, []
    for f in files:
        d = parse_ti3(f)
        rgb = MR._rgb_to_0_100(np.asarray(d.rgb, float))
        lv = [float(r.mean()) for r in rgb if r.max() - r.min() <= 1.0]
        if not lv or MR._distinct_levels(lv) < MR.GREY_MIN_LEVELS \
                or max(lv) < MR.GREY_LIGHTEST_MIN \
                or min(lv) > MR.GREY_DARKEST_MAX:
            continue
        eligible += 1
        if MR.pick_even_grey_steps(lv)[0] is None:
            refused.append(Path(f).name)
    assert eligible >= 181, eligible
    assert not refused, refused


def test_the_help_text_quotes_the_tolerance():
    """MUTATION: change GREY_SPACING_TOL without the help text and this goes
    red."""
    assert f"within {MR.GREY_SPACING_TOL:g} % of full scale" in CS._D_GREY_RAMP


def test_the_na_note_names_the_level_and_tells_nothing_to_do(qapp):
    """K22: the note says what the measured chart lacks, no instruction.

    MUTATION: drop the "grey_steps_bunched" entry from `_reason_sentence`
    and this goes red (the code has no sentence)."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    text = MeasurementReportDialog._reason_sentence(
        None, MR.REASON_GREY_STEPS_BUNCHED,
        {"grey_balance": {"missing_level": 13.4}})
    assert "13.4" in text and "within 4 of" in text, text
    for bad in ("add", "use a", "create chart", "chromiq"):
        assert bad not in text.lower(), (bad, text)


def test_the_presets_window_counts_it_as_a_patch_shortfall():
    """A longer, evenly spaced ramp fixes it, so it decides the star.

    MUTATION: leave it out of `PATCH_SHORTFALL_REASONS` and this goes red."""
    from workflow import preset_eligibility as PE
    assert MR.REASON_GREY_STEPS_BUNCHED in PE.PATCH_SHORTFALL_REASONS


# ===========================================================================
# 3. R2 / G5: the wider pre-flight
# ===========================================================================
class _Geo:
    def __init__(self, w, h):
        self._w, self._h = w, h

    def width(self):
        return self._w

    def height(self):
        return self._h


class _Screen:
    def __init__(self, w, h):
        self.g = _Geo(w, h)

    def availableGeometry(self):
        return self.g


class _Box:
    def __init__(self, w, h):
        self.s = _Screen(w, h)

    def screen(self):
        return self.s


def test_the_width_is_held_inside_qts_own_ceiling():
    """Qt caps a message box at the screen width less 480, and past it wraps
    the text anywhere, words broken. A 13-inch Air (1470) keeps the full 920;
    a 1280 screen gets 752.

    MUTATION: return PREFLIGHT_TEXT_WIDTH unclamped and the second assertion
    goes red."""
    from ui.tabs import tab_measure as TM
    assert TM.preflight_text_width(_Box(1470, 918)) == TM.PREFLIGHT_TEXT_WIDTH
    assert TM.preflight_text_width(_Box(1280, 760)) == 1280 - 480 - 48


def test_a_screen_too_short_for_the_wide_box_gets_the_one_line(qapp,
                                                                 monkeypatch):
    """The box with the full paragraph, widened as the pre-flight widens it:
    it fits a tall work area and not a short one.

    MUTATION: make `_preflight_fits` return True and the second assertion
    goes red; drop the caption from its sum and a box exactly at the limit
    passes when it should not."""
    from PyQt6.QtWidgets import QMessageBox

    from ui.tabs import tab_measure as TM
    from ui.widgets import widen_message_box
    from workflow import measurement_messages as M
    t, b = M.M_VERIFY_UNCHECKED_METRICS.render()
    box = QMessageBox()
    box.setText("\n\n".join([t, b] * 4))
    widen_message_box(box, TM.PREFLIGHT_TEXT_WIDTH)
    box.layout().activate()
    need = max(box.sizeHint().height(), box.minimumSizeHint().height())
    monkeypatch.setattr(TM, "_preflight_work_height", lambda _b: need + 28)
    assert TM._preflight_fits(box)
    monkeypatch.setattr(TM, "_preflight_work_height", lambda _b: need + 27)
    assert not TM._preflight_fits(box)
    box.deleteLater()


def test_the_popup_is_widened_and_guarded():
    """The pre-flight widens its box and asks the guard before it opens.

    MUTATION: remove either call from `_show_verification_preflight_now`, or
    ask the guard before the box is shown, and this goes red."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._show_verification_preflight_now)
    assert "widen_message_box(box, preflight_text_width(box))" in src
    assert "_preflight_fits(box)" in src
    assert "short=True" in src
    # asked of the SHOWN box: before it is shown its size hint was measured
    # 144 px short of the frame it opened with
    assert "QTimer.singleShot(0, _fit_the_screen)" in src


# ===========================================================================
# 4. the folder guide
# ===========================================================================
def test_the_folder_guide_shows_the_chromiq_folders_own_old():
    """Knut, 5795087247: *"This outside-of-project folder also needs to be
    visible in the help card for 'Where are my files?'"*.

    MUTATION: remove the "Your ChromIQ folder/" rows from `_structure` and
    this goes red."""
    from ui import file_guide as fg
    rows = fg.tree_rows()
    names = [(p, n) for p, n, _m in rows]
    i = next(k for k, (p, n) in enumerate(names)
             if p == "" and n == "Your ChromIQ folder/")
    kids = {n: m for (p, n), (_p, _n, m) in zip(names[i + 1:i + 3],
                                                rows[i + 1:i + 3])}
    assert set(kids) == {"reports/", "old/"}, kids
    assert "Delete Selected Report" in kids["old/"]
    assert "more than one project" in kids["reports/"]
    # …and the project's own old/, for a report across several runs
    j = next(k for k, (p, n) in enumerate(names) if n == "{name}/")
    project_level = [n for p, n in names[j + 1:i] if len(p) == 3]
    assert "old/" in project_level, project_level
