"""The Check & Refine redesign Knut approved (#182 5963903650, 2026-10-03).

He answered six questions on the pictures in 5963737221:

1. two lists, worst first, a reason for each strip listed first, and the
   choice "first strips" / "all strips": *"Yes. Good."*
2. start over advised only when more than half of all patches are above the
   limit, refinement still offered: *"Yes."*
3. the default is "Re-measure the strips listed first".
4. the "stands out clearly" bar is statistical and relative to each check
   (median + 6 x 1.4826 x MAD; 5963916503 explains it).
5. the live "strip read twice" check: *"Yes."* (its own file,
   test_182_strip_read_twice.py).
6. the pre-conditioning text: *"OK"*.

Earlier rulings kept: *"Re-measuring the flagged strips can help"* stays, and
re-reads are not judged against the previous profile (5963360295).

Most of this runs on Knut's own data: the profcheck output of his run2's sixth
quality check (with the B26 line the capture cut in two) and of his run3, in
``tests/data/check_refine/``.
"""
from __future__ import annotations

import inspect
import math
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import i18n                                       # noqa: E402
from workflow import refine_plan as rp                      # noqa: E402
from workflow.profcheck_runner import (                     # noqa: E402
    ProfcheckResult, ProfcheckRunner, quality_explanation_body)

DATA = Path(__file__).parent / "data" / "check_refine"
RUN2 = (DATA / "knut_run2_profcheck_qc6.txt").read_text(encoding="utf-8")
RUN3 = (DATA / "knut_run3_profcheck.txt").read_text(encoding="utf-8")


def _plan(text, thr):
    return rp.build_plan(rp.parse_patches(text), thr,
                         rp.de_name_for(text, "-k"))


@pytest.fixture
def german():
    i18n.set_language("de")
    try:
        yield
    finally:
        i18n.set_language("en")


# ---- 2. start over only above half of all patches ---------------------------

def test_start_over_is_strictly_more_than_half_of_all_patches():
    assert rp.recommends_start_over(325, 648)
    assert not rp.recommends_start_over(324, 648)
    assert not rp.recommends_start_over(0, 0)


def test_the_strip_count_rule_is_gone():
    """Knut's run2 at 2.0 has a patch above the limit on all 24 strips. That
    was "24 of 24 strips, start over" with no way to refine; 17 % of the
    patches are above, so nothing is advised and refinement is offered."""
    plan = _plan(RUN2, 2.0)
    assert plan.n_total == 648 and plan.n_over == 110
    assert len(plan.offered) == 24
    assert not plan.start_over
    import workflow.profcheck_runner as pr
    assert not hasattr(pr, "REFINE_START_OVER_STRIP_RATIO")
    assert not hasattr(pr, "start_over_reason")


def test_more_than_half_advises_start_over_and_still_offers_refinement():
    plan = _plan(RUN2, 0.5)
    assert plan.n_over == 402 and plan.pct_over == 62
    assert plan.start_over
    assert plan.offered, "refinement must stay available (Knut, Q2)"


# ---- 4. the robust outlier bar ----------------------------------------------

def test_the_outlier_bar_is_median_plus_six_scaled_mads():
    des = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0]
    med, mad = 2.0, 1.0
    assert rp.outlier_limit(des) == pytest.approx(med + 6 * 1.4826 * mad)


def test_the_bar_follows_the_check_not_a_fixed_number():
    """5963916503: about 5.3 on Knut's laser run2, about 2.4 on his run3."""
    assert _plan(RUN2, 2.0).outlier_limit == pytest.approx(5.31, abs=0.01)
    assert _plan(RUN3, 2.0).outlier_limit == pytest.approx(2.36, abs=0.01)


def test_mad_zero_falls_back_to_the_mean_absolute_deviation():
    """More than half of the errors identical: MAD 0 would make every patch
    above the median "stand out"."""
    des = [0.5] * 60 + [0.6, 0.8, 1.0, 9.0]
    lim = rp.outlier_limit(des)
    mean_ad = sum(abs(d - 0.5) for d in des) / len(des)
    assert lim == pytest.approx(0.5 + 6 * 1.2533 * mean_ad)
    assert 0.6 < lim < 9.0


def test_all_errors_identical_means_nothing_stands_out():
    assert rp.outlier_limit([1.5] * 30) == math.inf
    assert rp.outlier_limit([]) == math.inf
    patches = [rp.Patch(f"A{i}", 3.0, "A", i) for i in range(1, 11)]
    plan = rp.build_plan(patches, 2.0)
    assert not plan.first and [a.strip for a in plan.rest] == ["A"]


# ---- 1. the two lists on Knut's data (the pictures) -------------------------

def test_run2_at_2_lists_strip_n_first_and_23_after():
    plan = _plan(RUN2, 2.0)
    assert [(a.strip, a.kind, a.patch) for a in plan.first] == \
        [("N", rp.OUTLIER, "N1")]
    assert len(plan.rest) == 23
    assert plan.rest[0].strip == "H" and plan.rest[0].patch == "H9"
    assert [a.de for a in plan.rest] == sorted((a.de for a in plan.rest),
                                               reverse=True)


def test_run2_at_3_lists_strip_n_first_and_16_after():
    plan = _plan(RUN2, 3.0)
    assert [a.strip for a in plan.first] == ["N"]
    assert len(plan.rest) == 16


def test_run3_at_2_lists_seven_first_then_j_and_k():
    plan = _plan(RUN3, 2.0)
    assert [a.strip for a in plan.first] == ["E", "A", "D", "I", "G", "C", "L"]
    assert all(a.kind == rp.OUTLIER for a in plan.first)
    assert [a.strip for a in plan.rest] == ["J", "K"]


# ---- the unsteady swipe (partly read as its neighbour) ----------------------

def _blend_strip(t=0.3):
    """Strip K of five patches; K3 measured 30 % towards K4's colour."""
    pred = {1: (50, 0, 0), 2: (40, -20, 5), 3: (40, -20, 30),
            4: (70, 40, -30), 5: (30, 5, 5)}
    out = []
    for i, p in pred.items():
        meas = p
        if i == 3:
            meas = tuple(a + t * (b - a) for a, b in zip(p, pred[4]))
        de = math.dist(meas, p)
        out.append(rp.Patch(f"K{i}", de or 0.2, "K", i, p, meas))
    # a few quiet strips so the check has a typical spread
    for s in "ABC":
        for i in range(1, 6):
            out.append(rp.Patch(f"{s}{i}", 0.3 + 0.05 * i, s, i,
                                (50, 0, 0), (50.3, 0, 0)))
    return out


def test_a_patch_mixed_with_its_neighbour_is_named_with_that_neighbour():
    by = {p.loc: p for p in _blend_strip()}
    assert rp.blend_partner(by["K3"], by) == "K4"


def test_the_blend_reason_lists_the_strip_first():
    plan = rp.build_plan(_blend_strip(), 2.0, de_name="ΔE00")
    k = [a for a in plan.offered if a.strip == "K"][0]
    assert k in plan.first
    assert (k.kind, k.patch, k.neighbour) == (rp.BLEND, "K3", "K4")


def test_a_small_mix_is_not_called_a_blend():
    """Below 15 % of the neighbour: run2's L5 was once called "partly like L6"
    on a looser bar, and Knut's re-read read L5 the same."""
    by = {p.loc: p for p in _blend_strip(t=0.1)}
    assert rp.blend_partner(by["K3"], by) == ""


# Named ids: the default id is the whole profcheck text, which pytest puts in
# PYTEST_CURRENT_TEST, and Windows refuses an environment variable over 32767
# characters (the first CI run there errored at setup and teardown).
@pytest.mark.parametrize("text, thr", [(RUN2, 2.0), (RUN2, 3.0), (RUN3, 2.0)],
                         ids=["run2-2.0", "run2-3.0", "run3-2.0"])
def test_no_false_blend_on_knuts_real_runs(text, thr):
    """His full re-read of run2 confirms every patch was read correctly."""
    plan = _plan(text, thr)
    assert not [a for a in plan.offered if a.kind == rp.BLEND]


# ---- the line the capture cut in two (B26 on Knut's run2) -------------------

def test_knuts_split_b26_line_is_mended():
    assert "[0.047433] 162 @ B26: 0.80000000 0.400000\n00 1.00000000" in RUN2
    patches = {p.loc: p for p in rp.parse_patches(RUN2)}
    assert len(patches) == 648
    b26 = patches["B26"]
    assert b26.de == pytest.approx(0.047433)
    assert b26.pred == pytest.approx((51.564012, 21.834236, -27.948463))
    assert b26.meas == pytest.approx((51.600346, 21.770761, -27.906072))


def test_the_parser_of_the_tab_mends_it_too():
    res = ProfcheckRunner.__new__(ProfcheckRunner)
    res._last_log = RUN2
    parsed = ProfcheckRunner.parse_results(res)
    assert len(parsed.patch_errors) == 648
    assert ("B26", 0.047433) in parsed.patch_errors


LINE = ("[5.316670] 542 @ N1: 0.71059400 0.68750000 0.66440600 -> 67.010785 "
        "3.564747 -1.141161 should be 67.091487 3.328501 -7.385683")


@pytest.mark.parametrize("cut", range(1, len(LINE)))
def test_a_line_cut_anywhere_is_put_back(cut):
    text = ("No of test patches = 2\n" + LINE[:cut] + "\n" + LINE[cut:] + "\n"
            "[0.1] 1 @ A2: 0 0 0 -> 1 2 3 should be 1 2 3\n"
            "Profile check complete, errors(CIEDE2000): max. = 5.316670, "
            "avg. = 2.7, RMS = 3.0\n")
    got = {p.loc: p for p in rp.parse_patches(text)}
    assert set(got) == {"N1", "A2"}
    assert got["N1"].meas == pytest.approx((67.091487, 3.328501, -7.385683))


# ---- 3. the default choice ---------------------------------------------------

def test_the_default_is_the_strips_listed_first_in_chart_order():
    plan = _plan(RUN3, 2.0)
    assert [s for s, _ in plan.chosen()] == ["A", "C", "D", "E", "G", "I", "L"]
    assert [s for s, _ in plan.chosen(first_only=False)] == \
        ["A", "C", "D", "E", "G", "I", "J", "K", "L"]


def test_with_no_first_list_every_strip_is_chosen_and_there_is_no_choice():
    patches = [rp.Patch(f"{s}{i}", 2.5 if i == 2 else 1.8, s, i)
               for s in "AB" for i in range(1, 6)]
    plan = rp.build_plan(patches, 2.0)
    assert not plan.first and not plan.has_choice
    assert [s for s, _ in plan.chosen()] == ["A", "B"]


# ---- 6. yellow patches are offered like any other (Knut 5980560281) --------
# Beta 7 left out patches a re-read confirmed; Knut ruled that Check & Refine
# is not influenced by confirmed or unconfirmed patches at all. The memory
# itself is guarded in test_check_refine_ignores_the_confirmed_patches_memory.

def test_every_patch_above_the_limit_is_offered_confirmed_or_not():
    plan = _plan(RUN3, 2.0)
    strips = {a.strip for a in plan.offered}
    assert {"I", "C", "L"} <= strips
    assert not hasattr(plan, "confirmed_skipped")
    assert not hasattr(rp.plan_text(plan, 0.67, 4.34), "confirmed")


# ---- 4. one formula, named on every number -----------------------------------

@pytest.mark.parametrize("summary, flag, name", [
    ("errors(CIEDE2000): max. = 1", "", "ΔE00"),
    ("errors (CIE94): max. = 1", "", "ΔE94"),
    ("errors: max. = 1", "-k", "ΔE76"),
    ("", "-k", "ΔE00"),
    ("", "", "ΔE76"),
])
def test_the_formula_name_comes_from_the_check(summary, flag, name):
    text = f"Profile check complete, {summary}\n" if summary else ""
    assert rp.de_name_for(text, flag) == name


def test_every_number_in_the_window_text_carries_the_name():
    t = rp.plan_text(_plan(RUN3, 2.0), 0.67, 4.34)
    assert t.numbers == "Average ΔE00 0.67  |  Largest ΔE00 4.34"
    assert t.over == ("19 of 324 patches (6%) are above your limit of "
                      "ΔE00 2.0.")
    for _label, why in t.first_rows:
        assert "(ΔE00 " in why
    assert "ΔE00 2.0" in t.rest_head


def test_the_explanation_names_the_formula_and_keeps_its_advice():
    body = quality_explanation_body(1.09, 5.32, "ΔE00")
    assert "Re-measuring the flagged strips can help" in body
    assert "ΔE00 1.09" in body and "ΔE00 5.32" in body
    assert "Average" not in body.split("\n")[0][:8], "the numbers line is gone"


@pytest.mark.parametrize("code", [c for c, _n in i18n.available_languages()
                                  if c != "en"])
def test_every_language_keeps_the_formula_name_in_the_explanation(code):
    i18n.set_language(code)
    try:
        body = quality_explanation_body(1.09, 5.32, "ΔE00")
    finally:
        i18n.set_language("en")
    assert "ΔE00" in body, code


# ---- the window -------------------------------------------------------------

def _tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    return TabCheckRefine(ArgyllRunner(s), s)


def _open(qapp, tmp_path, monkeypatch, text, thr, *, icc=True, ti3=True):
    from PyQt6.QtWidgets import QDialog
    tab = _tab(qapp, tmp_path)
    if icc:
        tab._icc_path = tmp_path / "test.icc"
    if ti3:
        tab._ti3_path = tmp_path / "test.ti3"
    res = ProfcheckResult(raw_log=text)
    from workflow.profcheck_runner import _SUMMARY_RE
    m = _SUMMARY_RE.search(text)
    res.peak_de, res.avg_de = float(m.group(1)), float(m.group(2))
    plan = tab._plan_for(res, thr)
    folder = tmp_path / "reports"
    folder.mkdir(exist_ok=True)
    from workflow.profcheck_runner import write_refine_strips
    strips_file = write_refine_strips(folder, "test", plan.chosen())
    seen = []

    def _exec(dlg):
        seen.append(dlg)
        return 0
    monkeypatch.setattr(QDialog, "exec", _exec)
    tab._show_result_dialog(res, plan, strips_file)
    return tab, plan, seen[0], strips_file


def _texts(dlg):
    from PyQt6.QtWidgets import QAbstractButton, QLabel
    return ([lbl.text() for lbl in dlg.findChildren(QLabel)]
            + [b.text() for b in dlg.findChildren(QAbstractButton)])


def _buttons(dlg):
    from PyQt6.QtWidgets import QPushButton
    return {b.text(): b for b in dlg.findChildren(QPushButton)}


def test_the_window_shows_the_pictured_lines(qapp, tmp_path, monkeypatch):
    _tab_, _plan_, dlg, _f = _open(qapp, tmp_path, monkeypatch, RUN3, 2.0)
    text = "\n".join(_texts(dlg))
    for line in (
            "Average ΔE00 0.67  |  Largest ΔE00 4.34",
            "19 of 324 patches (6%) are above your limit of ΔE00 2.0.",
            "<b>Re-measure these strips first</b> (worst first). Each has a "
            "patch that may have been misread, and a re-read shows whether "
            "it was:",
            "Patch E13 (ΔE00 4.34) stands out clearly from the rest of "
            "this check. 3 patches in this strip are above your limit.",
            "<b>2 more strips have patches above ΔE00 2.0</b> (worst "
            "first; worst patch, and how many are above):",
            "J  ΔE00 2.26 (2)", "K  ΔE00 2.23 (2)",
            "Re-measure the 7 strips listed first",
            "Re-measure all 9 strips above your limit",
            "The guide takes you through the chosen strips in chart order "
            "(A, B, C ...), the order the instrument reads them in."):
        assert line in text, line
    assert "avg ΔE" not in text and "(avg" not in text, "no strip averages"
    dlg.deleteLater()


def test_the_default_choice_is_checked(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QRadioButton
    _t, _p, dlg, _f = _open(qapp, tmp_path, monkeypatch, RUN3, 2.0)
    rbs = {rb.objectName(): rb for rb in dlg.findChildren(QRadioButton)}
    assert rbs["refine_choice_first"].isChecked()
    assert not rbs["refine_choice_all"].isChecked()
    dlg.deleteLater()


@pytest.mark.parametrize("pick_all, expected", [
    (False, ["A", "C", "D", "E", "G", "I", "L"]),
    (True, ["A", "C", "D", "E", "G", "I", "J", "K", "L"]),
])
def test_the_guide_gets_the_chosen_strips_in_chart_order(
        qapp, tmp_path, monkeypatch, pick_all, expected):
    from PyQt6.QtWidgets import QRadioButton
    from workflow.profcheck_runner import parse_refine_strips
    tab, _p, dlg, f = _open(qapp, tmp_path, monkeypatch, RUN3, 2.0)
    got = []
    tab.guide_refinement_requested.connect(lambda ti3, path: got.append(path))
    if pick_all:
        [rb for rb in dlg.findChildren(QRadioButton)
         if rb.objectName() == "refine_choice_all"][0].setChecked(True)
    _buttons(dlg)["← Guide Me Through Refinement"].click()
    assert got == [f], "the same file, this check's own"
    assert parse_refine_strips(got[0]) == expected
    assert len(list(f.parent.glob("Refine_Strips_*"))) == 1
    dlg.deleteLater()


def test_refinement_is_offered_when_start_over_is_advised(qapp, tmp_path,
                                                          monkeypatch):
    _t, plan, dlg, _f = _open(qapp, tmp_path, monkeypatch, RUN2, 0.5)
    assert plan.start_over
    text = "\n".join(_texts(dlg))
    assert ("<b>More than half of your patches are above your limit (402 of "
            "648, 62%).</b>") in text
    assert "← Guide Me Through Refinement" in _buttons(dlg)
    dlg.deleteLater()


def test_preconditioning_keeps_its_accent_while_refinement_is_offered(
        qapp, tmp_path, monkeypatch):
    """Sebastian, 2026-10-03: "Use as pre-conditioning" keeps the violet
    accent whenever it is shown, beside "Guide me" too, as in beta 5 and 6.
    The redesign had taken it off; only the colour comes back, the text still
    describes what targen -c does."""
    _t, _p, dlg, _f = _open(qapp, tmp_path, monkeypatch, RUN3, 2.0)
    b = _buttons(dlg)
    assert b["← Guide Me Through Refinement"].objectName() == "primary"
    assert b["← Use as Pre-conditioning"].objectName() == "primary"
    text = "\n".join(_texts(dlg))
    assert "spread evenly by how colours look" in text
    assert "least accurately" not in text and "Recommended" not in text
    dlg.deleteLater()


def test_with_nothing_above_the_limit_nothing_is_offered(qapp, tmp_path,
                                                         monkeypatch):
    _t, plan, dlg, _f = _open(qapp, tmp_path, monkeypatch, RUN3, 5.0)
    assert not plan.offered
    text = "\n".join(_texts(dlg))
    assert ("No patch is above your limit of ΔE00 5.0. Nothing needs "
            "re-measuring.") in text
    assert "← Guide Me Through Refinement" not in _buttons(dlg)
    assert _buttons(dlg)["← Use as Pre-conditioning"].objectName() == \
        "primary"
    dlg.deleteLater()


def test_the_manual_panel_uses_its_own_limit(qapp, tmp_path):
    tab = _tab(qapp, tmp_path)
    tab._threshold_spin.setValue(2.0)
    tab._m_threshold_spin.setValue(3.5)
    tab._switch_mode("manual")
    assert tab._limit() == 3.5
    tab._switch_mode("guided")
    assert tab._limit() == 2.0


# ---- 7. the saved report says what the window says ---------------------------

def test_the_report_carries_every_window_line(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_check_refine import TabCheckRefine
    _t, plan, dlg, _f = _open(qapp, tmp_path, monkeypatch, RUN2, 0.5)
    res = ProfcheckResult(avg_de=1.086052, peak_de=5.31667, raw_log=RUN2)
    report = TabCheckRefine._report_summary_text(res, plan)
    t = rp.plan_text(plan, res.avg_de, res.peak_de)
    from ui.tabs.tab_check_refine import _plain
    for line in (t.numbers, t.over, _plain(t.start_over), _plain(t.first_head),
                 _plain(t.rest_head), t.choice_first, t.choice_all, t.order):
        assert line in report, line
    for label, why in t.first_rows:
        assert label in report and why in report
    for item in t.rest_items:
        assert item in report
    assert quality_explanation_body(res.avg_de, res.peak_de,
                                    "ΔE00") in report
    assert "<b>" not in report and "<br>" not in report
    assert "avg ΔE" not in report
    dlg.deleteLater()


def test_the_saved_report_and_strip_file_are_written(qapp, tmp_path,
                                                     monkeypatch):
    """`_on_done` writes the report AND the strips file, start over or not."""
    from PyQt6.QtWidgets import QDialog
    from workflow.profcheck_runner import parse_refine_strips
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    tab = _tab(qapp, tmp_path)
    tab._threshold_spin.setValue(0.5)
    ti3 = tmp_path / "run2" / "test.ti3"
    ti3.parent.mkdir()
    ti3.write_text("CTI3\n", encoding="utf-8")
    tab._ti3_path = ti3
    tab._checking_in_place = True
    res = ProfcheckResult(avg_de=1.086052, peak_de=5.31667, raw_log=RUN2)
    res.patch_errors = [(p.loc, p.de) for p in rp.parse_patches(RUN2)]
    monkeypatch.setattr(tab._checker, "parse_results", lambda: res)
    tab._on_done(1)
    body = next(ti3.parent.glob("Quality_Check_*_test.txt")).read_text(
        encoding="utf-8")
    assert "More than half of your patches are above your limit" in body
    assert "Re-measure these strips first" in body
    assert "23 more strips have patches above ΔE00 0.5" in body
    strips = parse_refine_strips(next(ti3.parent.glob("Refine_Strips_*")))
    assert strips == ["N"]


def test_the_report_is_translated(german):
    from ui.tabs.tab_check_refine import TabCheckRefine
    plan = _plan(RUN3, 2.0)
    res = ProfcheckResult(avg_de=0.67, peak_de=4.34, raw_log=RUN3)
    report = TabCheckRefine._report_summary_text(res, plan)
    assert "Re-measure these strips first" not in report
    assert "stands out clearly" not in report
    assert "ΔE00" in report


# ---- 5. the pre-conditioning text, in all three places ------------------------

def test_the_preconditioning_text_is_the_approved_one_everywhere():
    from ui.tabs import tab_chart, tab_check_refine, tab_profile
    from workflow import measurement_messages as mm
    assert "spread evenly by how colours look" in mm._CR_PRECOND
    assert "_CR_PRECOND" in inspect.getsource(
        tab_check_refine.TabCheckRefine._show_result_dialog)
    assert "_CR_PRECOND" in inspect.getsource(
        tab_profile.TabProfile._show_build_result_dialog)
    for mod in (tab_chart, tab_check_refine, tab_profile):
        src = inspect.getsource(mod)
        assert "reproduces least accurately" not in src, mod.__name__
        assert "place the new test patches more cleverly" not in src
    assert "targen -c" in inspect.getsource(tab_chart)


def test_the_window_composes_from_the_catalogue_only():
    """Every sentence of the new window is a §M-PROPOSED fragment."""
    from ui.tabs.tab_check_refine import TabCheckRefine
    src = inspect.getsource(TabCheckRefine._show_result_dialog)
    for gone in ("Strips with the highest error", "Listed in measurement order",
                 "should be re-measured", "avg ΔE", "<pre>"):
        assert gone not in src
    src = inspect.getsource(rp.plan_text)
    assert "measurement_messages" in src
