"""#182, beta 45: Knut's high-pass filter on the two evenness rows, the
limits derived from real printers, the ISO figures converted to ChromIQ's
method, and the guide to choosing limits (Knut, #182 5855259490 and
5855780690, 2026-09-27).

* **The filter.** From each squared difference the noise's expected share is
  taken away (`measurement_report._filtered_nine`), measured against an
  independent computation here, on even sheets and on sheets with a known
  unevenness added.
* **The limits.** tight 1.5 / 1.0, default 1.8 / 1.2, quick 2.5 / 1.7,
  Custom ISO 12647-7 1.5 / 1.0, Custom ISO 12647-8 3.0 / 2.0.
* **The conversion.** A standard's standard deviation times 3 and times 2,
  its own maximum difference from the average as it is, the stricter used,
  the first row kept inside 1.125 to 2 times the second
  (`compliance_sets.convert_iso_evenness`), whatever file supplies the
  figures.
* **Both rows can fail**, in every set.
* **The Report Limits window** marks the converted cells and explains them.
* **The presets window** says a chart that meets the page rules can be
  judged, with Knut's accepted text.

Every test names the mutation it was run against. OFFSCREEN: these are data
and widget-content checks; the windows are photographed on screen by the
proof driver.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                           # noqa: E402

from workflow import compliance_sets as CS                         # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

PAIR, FROM_MEAN = "uniformity_sd", "uniformity_de00_max_from_mean"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# the filter
# ---------------------------------------------------------------------------
def _page(per_band_strips: int, per_band_rows: int):
    """A one-page grid of 3 x 3 equal ninths, and each slot's ninth."""
    s, r = 3 * per_band_strips, 3 * per_band_rows
    g = MR.evenness_grid_from_layout([s], r, s * r, coverage=[1.0])
    st, rw = np.meshgrid(np.arange(s), np.arange(r), indexing="ij")
    area = (MR._bands_of(st.ravel(), np.full(s * r, s)) * 3
            + MR._bands_of(rw.ravel(), np.full(s * r, r)))
    return g, area


def _independent(area: np.ndarray, resid: np.ndarray):
    """The filtered pair, written again from the formula Knut was shown
    (#182 5854662899), with its own loops and ΔE00 from the profile engine,
    importing nothing of the report's evenness code."""
    from workflow.profile_engine.metrics import delta_e_2000
    n = np.array([np.sum(area == a) for a in range(9)], float)
    means = np.array([resid[area == a].mean(axis=0) for a in range(9)])
    ss = sum(((resid[area == a] - means[a]) ** 2).sum(axis=0)
             for a in range(9))
    var = ss / (n.sum() - 9)
    s2 = var[0] + 2.25 * var[1] + var[2]
    labs = means + np.array([50.0, 0.0, 0.0])
    best_p = 0.0
    for i in range(9):
        for j in range(i + 1, 9):
            d2 = float(delta_e_2000(labs[i:i + 1], labs[j:j + 1])[0]) ** 2
            best_p = max(best_p, np.sqrt(max(0.0, d2 - s2 * (1 / n[i] + 1 / n[j]))))
    c = labs.mean(axis=0, keepdims=True)
    best_d = 0.0
    for i in range(9):
        d2 = float(delta_e_2000(labs[i:i + 1], c)[0]) ** 2
        v = (1 / n[i]) * (1 - 2 / 9) + (1 / n).sum() / 81
        best_d = max(best_d, np.sqrt(max(0.0, d2 - s2 * v)))
    return best_p, best_d


def test_the_filter_is_the_formula_knut_was_shown():
    """The report's two numbers are the independent computation's, to the
    rounding the block uses, on a sheet with an unevenness in it.

    MUTATION, proven red: drop the ``1/n_j`` term of the pairwise noise in
    `_filtered_nine` (the pairwise figure moves by about 0.1)."""
    g, area = _page(4, 5)                                     # 20 in a ninth
    rng = np.random.default_rng(7)
    resid = rng.normal(0, 1.1, (area.size, 3))
    resid[area == 2, 0] += 1.3                                # one ninth off
    b = MR.evenness_from_residuals(g, resid, shuffles=50)
    p, d = _independent(area, resid)
    assert b["pairwise"] == pytest.approx(p, abs=1.5e-3), (b["pairwise"], p)
    assert b["from_mean"] == pytest.approx(d, abs=1.5e-3), (b["from_mean"], d)
    assert b["filter"] == MR.EVENNESS_FILTER
    # the filter took something away, and the block says how much
    assert b["pairwise_unfiltered"] > b["pairwise"]
    assert b["from_mean_unfiltered"] >= b["from_mean"]
    assert len(b["within_sd"]) == 3


def test_an_even_sheet_reads_close_to_zero_and_below_its_unfiltered_reading():
    """Knut's water level: a perfectly even sheet, noise only. Averaged over
    twenty sheets at 60 in each ninth the filtered pair reads well under the
    unfiltered one (the analysis measured 0.60 against 0.73 at sigma 1.1).

    MUTATION, proven red: `_filtered_nine` returning the unfiltered ΔE00."""
    g, area = _page(6, 10)
    raw, filt = [], []
    for seed in range(20):
        rng = np.random.default_rng(100 + seed)
        b = MR.evenness_from_residuals(g, rng.normal(0, 1.1, (area.size, 3)),
                                       shuffles=20)
        raw.append(b["pairwise_unfiltered"])
        filt.append(b["pairwise"])
    assert np.mean(filt) < 0.9 * np.mean(raw), (np.mean(filt), np.mean(raw))
    assert np.mean(filt) < 0.7, np.mean(filt)


def test_a_known_unevenness_is_read_closer_to_the_truth_with_the_filter():
    """A change across the strips whose true pairwise size is 1.0, under the
    noise of a typical print: at 200 in each ninth the filtered figure reads
    it within 0.15 (the analysis: 1.12; the largest of 36 noisy pairs keeps a
    little of the noise), and nearer than the unfiltered one.

    MUTATION, proven red: add the noise's share instead of taking it away."""
    g, area = _page(10, 20)
    band = area // 3                                  # 0, 1, 2 across strips
    field = np.zeros((9, 3))
    for a in range(9):
        field[a, 2] = (a // 3 - 1) * 0.5              # b*: -0.5, 0, +0.5
    true_p = float(MR._nine_numbers(field[None])[0][0])
    got, raw = [], []
    for seed in range(12):
        rng = np.random.default_rng(300 + seed)
        resid = rng.normal(0, 1.1, (area.size, 3)) + field[area]
        b = MR.evenness_from_residuals(g, resid, shuffles=20)
        got.append(b["pairwise"])
        raw.append(b["pairwise_unfiltered"])
    assert band.max() == 2
    assert abs(np.mean(got) - true_p) < 0.15, (np.mean(got), true_p)
    assert abs(np.mean(got) - true_p) < abs(np.mean(raw) - true_p)


def test_the_noise_a_limit_must_clear_is_the_noise_of_the_filtered_number():
    """The shuffle runs the SAME filter, so its 95th percentile is of the
    statistic the limit is compared with: on an even sheet the measured
    number sits under its own noise figure, and the noise figure is lower
    than the unfiltered shuffle's would be (the multipliers of the model,
    6.35 and 3.73, against 6.99 and 4.21 before).

    MUTATION, proven red: run `_nine_numbers` (unfiltered) on the shuffles."""
    assert MR.EVENNESS_NOISE_PER_ROOT_PATCH == {"pairwise": 6.35,
                                                "from_mean": 3.73}
    g, area = _page(20, 20)                           # 400 in each ninth
    got = []
    for seed in range(4):
        rng = np.random.default_rng(1000 + seed)
        b = MR.evenness_from_residuals(g, rng.normal(0, 1.0, (area.size, 3)),
                                       shuffles=600, seed=seed)
        got.append(b["noise_pairwise_p95"] * 20)
    assert np.mean(got) == pytest.approx(6.35, rel=0.05), got


# ---------------------------------------------------------------------------
# the limits, the conversion, the ratio
# ---------------------------------------------------------------------------
LIMITS = {"chromiq_tight": (1.5, 1.0), "chromiq_default": (1.8, 1.2),
          "chromiq_quick": (2.5, 1.7), "custom_iso_12647_7": (1.5, 1.0),
          "custom_iso_12647_8": (3.0, 2.0), "iso_12647_7": (1.5, 1.0),
          "iso_12647_8": (3.0, 2.0)}


@pytest.mark.parametrize("sid", sorted(LIMITS))
def test_every_set_carries_knuts_limits(sid):
    """MUTATION, proven red: any one of the seven pairs changed."""
    f = CS.factory_limits(sid)
    assert (f[PAIR].number, f[FROM_MEAN].number) == LIMITS[sid]
    assert f[PAIR].kind == f[FROM_MEAN].kind == "value"


@pytest.mark.parametrize("sid", sorted(LIMITS))
def test_both_rows_can_fail_on_their_own_in_every_set(sid):
    """The relational guard, again: with nine areas "between two areas" is
    always between 1.125 and 2 times "one area against the whole sheet", so a
    pair outside that range leaves one row unable ever to fail alone. Checked
    on the limits and, for the two extremes, on real fields: a blotch trips
    the second row first and a change across the strips the first.

    MUTATION, proven red: ISO 12647-8's first row left at 4.5 (above twice
    the second) in `convert_iso_evenness`."""
    lo, hi = CS.EVENNESS_RATIO_RANGE
    pw, fm = LIMITS[sid]
    assert lo * fm < pw < hi * fm, (sid, pw / fm)
    blotch = np.zeros((9, 3))
    blotch[4, 0] = 1.0
    grad = np.zeros((9, 3))
    for a in range(9):
        grad[a, 2] = (a // 3 - 1) * 0.5
    for field, first in ((blotch, "from_mean"), (grad, "pairwise")):
        p, d = (float(x[0]) for x in MR._nine_numbers(field[None]))
        # scale the field until one row just fails; that row is `first`
        k_p, k_d = pw / p, fm / d
        assert (k_d < k_p) == (first == "from_mean"), (sid, first, k_p, k_d)


def test_the_conversion_of_both_standards():
    """ISO 12647-7:2016 (0.5, 2.0) gives 1.5 and 1.0; ISO 12647-8:2021 (1.5,
    2.0) gives 3.0 and 2.0, its first row brought down from 4.5; a standard
    that gives only one figure still converts; none gives nothing.

    MUTATION, proven red: take the LOOSER of the two for the second row."""
    assert CS.convert_iso_evenness(0.5, 2.0) == (1.5, 1.0)
    assert CS.convert_iso_evenness(1.5, 2.0) == (3.0, 2.0)
    assert CS.convert_iso_evenness(0.5, None) == (1.5, 1.0)
    assert CS.convert_iso_evenness(None, 2.0) == (3.0, 2.0)
    assert CS.convert_iso_evenness(None, None) is None
    assert (CS.EVENNESS_SD_TO_BETWEEN, CS.EVENNESS_SD_TO_FROM_MEAN,
            CS.EVENNESS_RATIO_AIM) == (3.0, 2.0, 1.5)


def test_a_licence_holders_own_file_is_converted_too(tmp_path, monkeypatch):
    """The evenness rows of the read-only ISO columns are ChromIQ's
    conversion, not the file's figures, so a user's own file that states the
    standard's 0.5 and 2.0 reads 1.5 and 1.0 like the shipped one, and a
    file that states other figures is converted by the same rule.

    MUTATION, proven red: apply the conversion to the shipped file only."""
    from tests.helpers.iso_files import use_repo_iso
    use_repo_iso(monkeypatch)
    own = tmp_path / "mine.json"
    own.write_text(json.dumps({"iso_12647_7": {PAIR: 0.5, FROM_MEAN: 2.0},
                               "iso_12647_8": {PAIR: 1.0, FROM_MEAN: 1.5}}),
                   encoding="utf-8")
    monkeypatch.setenv(CS.ISO_DATA_ENV, str(own))
    CS.reset_iso_cache()
    try:
        f7, f8 = CS.factory_limits("iso_12647_7"), CS.factory_limits("iso_12647_8")
        assert (f7[PAIR].number, f7[FROM_MEAN].number) == (1.5, 1.0)
        assert (f8[PAIR].number, f8[FROM_MEAN].number) == (2.25, 1.5)
        # the reference the window's note names is the file's own figures
        assert CS.iso_evenness_figures("iso_12647_8") == {"sd": 1.0,
                                                          "from_mean": 1.5}
    finally:
        CS.reset_iso_cache()


def test_a_value_the_user_set_is_kept():
    """No migration touches a value the user set: an override on a ChromIQ
    set's evenness row still wins over the new factory number, and a row
    without one takes the new number.

    MUTATION, proven red: `effective_limits` ignoring overrides."""
    eff = CS.effective_limits("chromiq_default", {"chromiq_default": {PAIR: 1.5}})
    assert eff[PAIR].number == 1.5
    assert eff[FROM_MEAN].number == 1.2


def test_the_guide_quotes_the_numbers_the_tables_hold():
    """Every number the evenness rows' relation text names is the code's:
    the ratio range, the factors, both standards' figures and the two ISO
    sets' converted pairs. It names no ChromIQ set's numbers and relates no
    set to another (Knut, K60, #182 5850330710).

    MUTATION, proven red: change ISO 12647-8's first row to 4.0 without the
    sentence."""
    rel = CS.ROW_BY_ID[PAIR].relation
    assert rel == CS.ROW_BY_ID[FROM_MEAN].relation
    lo, hi = CS.EVENNESS_RATIO_RANGE
    assert f"more than {lo:g} times and less than {hi:g} times" in rel
    assert f"times about {CS.EVENNESS_SD_TO_BETWEEN:g} gives" in rel
    assert f"times about {CS.EVENNESS_SD_TO_FROM_MEAN:g} gives" in rel
    f = {s: CS.factory_limits(s) for s in LIMITS}

    def pair(sid):
        return f"{f[sid][PAIR].number:.1f} and {f[sid][FROM_MEAN].number:.1f}"
    for name in ("ChromIQ tight", "ChromIQ default", "Quick check", "Custom"):
        assert name not in rel, name
    assert (f"converted limits, {pair('iso_12647_7')}, and "
            f"{pair('iso_12647_8')}") in rel
    from tests.helpers.iso_files import shipped_limits
    s7, s8 = shipped_limits("iso_12647_7"), shipped_limits("iso_12647_8")
    assert (f"ISO 12647-7:2016 allows a standard deviation of "
            f"{s7[PAIR].number:g} and a maximum difference from the average "
            f"of {s7[FROM_MEAN].number:.1f}") in rel
    assert (f"ISO 12647-8:2021 allows {s8[PAIR].number:.1f} and "
            f"{s8[FROM_MEAN].number:.1f}") in rel
    # the help says what the maximum difference from the average IS
    assert "the largest ΔE00 between the average of the nine readings" in rel
    assert "—" not in rel


def test_the_description_names_both_rows_and_the_filter():
    """Knut: *"the description of the Evenness feature must clearly specify
    which metrics are part of this feature"*.

    MUTATION, proven red: drop the second name from `_EVEN_INTRO`."""
    for rid in (PAIR, FROM_MEAN):
        row = CS.ROW_BY_ID[rid]
        for other in (PAIR, FROM_MEAN):
            assert f"“{CS.ROW_BY_ID[other].label}”" in row.blurb
        assert "water level" in row.detect and "takes it away" in row.detect
        for text in (row.blurb, row.detect, row.relation, row.remedy):
            assert "—" not in text


# ---------------------------------------------------------------------------
# the Report Limits window
# ---------------------------------------------------------------------------
def test_the_converted_cells_carry_the_mark_and_the_note_explains_them(
        qapp, tmp_path, monkeypatch):
    """Knut: *"maybe add a superscript number reference that points to a note
    that explains this in the window"*. The ⁴ is on the two evenness cells of
    each read-only ISO column and nowhere else, and the note names both
    standards' figures and what they became.

    MUTATION, proven red: `_cell_is_converted` without its row test (every
    numeric cell of an ISO column carries the mark)."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from tests.helpers.iso_files import use_repo_iso
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    use_repo_iso(monkeypatch)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s, None)
    try:
        mark = ThresholdsDialog.CONVERTED_MARK
        assert mark == "⁴" and ThresholdsDialog.RECOMMENDED_MARK == "⁵"
        for (col, rid), w in dlg._cells.items():
            text = w.text() if hasattr(w, "text") and not hasattr(w, "value") \
                else ""
            want = col in ("iso_12647_7", "iso_12647_8") and rid in (PAIR, FROM_MEAN)
            assert (mark in text) == want, (col, rid, text)
        notes = dlg._notes_text()
        assert f" {mark} These two evenness limits are the standard's own " \
               "figures converted" in notes
        loc = re.sub(r"\s", " ", notes)
        for std, sd, fm, pw, fm2 in (("ISO 12647-7:2016", 0.5, 2.0, 1.5, 1.0),
                                     ("ISO 12647-8:2021", 1.5, 2.0, 3.0, 2.0)):
            from PyQt6.QtCore import QLocale
            n = lambda x: QLocale.system().toString(float(x), "f", 1)  # noqa: E731
            assert (f"{std} states a standard deviation of {n(sd)} and a "
                    f"maximum difference from the average of {n(fm)}, which "
                    f"become {n(pw)} and {n(fm2)}") in loc, loc
        # hide both ISO columns and the mark's note goes with them
        for c in ("iso_12647_7", "iso_12647_8"):
            dlg._column_checks[c].setChecked(False)
        dlg._refresh_row_labels()
        assert f" {mark} " not in dlg._notes_text()
    finally:
        dlg.close()
        dlg.deleteLater()
        CS.reset_iso_cache()


# ---------------------------------------------------------------------------
# the presets window
# ---------------------------------------------------------------------------
def test_the_presets_window_says_a_chart_that_meets_the_page_rules_can_be_judged(
        qapp, tmp_path):
    """Knut accepted the text (#182 5855780690): it stands once under the
    evenness rows a chart answers, singular for one, plural for both.

    MUTATION, proven red: the line appended after every evenness row."""
    from ui.dialogs import preset_verification_dialog as PVD
    one = PVD.evenness_judged_line(1)
    both = PVD.evenness_judged_line(2)
    assert one.startswith("This chart can be judged on this metric.")
    assert both.startswith("This chart can be judged on these metrics.")
    for t in (one, both):
        assert "takes away what the measurement noise adds to it on average" in t
        assert "the lower the limit, the more patches it takes" in t
        assert "—" not in t
    a = PE.Assessment(asked=(PAIR, FROM_MEAN, "all_de00_avg"),
                      answered=(PAIR, FROM_MEAN, "all_de00_avg"), missing=())
    row = PVD.PresetRow(group="g", label="x", chart=tmp_path / "x.ti1",
                        patches=300, pages=1, builtin=False, recipe=None,
                        assessment=a)
    lines = [ln.text for ln in PVD.detail_lines(row)]
    assert lines.count(both) == 1, lines
    assert lines.index(both) == lines.index("✓  " + PE.row_label(FROM_MEAN)) + 1
