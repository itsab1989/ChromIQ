"""Challenge 2 of beta 44: the report findings, fixed (B8-1270 to B8-1278).

1. (B8-1270) On a FROM PROFILE GAMUT chart built with the RELATIVE intent the
   two solid rows compared an ABSOLUTE reading with a RELATIVE prediction
   (`corner_predictions_through` asked xicclu with the chart's intent), so a
   perfect print read 2.94 / 2.13 against limits of 3.0 / 2.5. The row asks
   "does the solid print as profiled?", so the prediction is absolute,
   whatever the chart's intent.
2. (B8-1271) (b2) was applied to every measurement, profiling sheets
   included, which were compared with the profile built from themselves.
   Knut's "Yes" was to "every verification sheet": a measurement that is not
   a verification gets what the three rows gave it before K49.
3. (B8-1273) The Printing record's sentence named four graphs when up to
   thirteen are drawn.
4. (B8-1274) "The limits this report is judged against set none for it" was
   poor English, and untrue where NO limit set has a limit for the graph.
   Amended by K50 (B8-1320): the replacement named other limit sets, which a
   report may never do; it is one sentence about this report now.
5. (B8-1275) The Cube corners sentence called every aim "ideal"; the paper
   white of a FROM PROFILE GAMUT chart aims at the profile's paper.
7. (B8-1276) A graph with no limit line and a value on one date only was
   shown as an empty frame.
8. (B8-1277) A solid value shown for information carried no
   M-REPORT-SOLIDS-PREDICTED note.

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/fixes-2/mutations.txt).
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from tests.test_k37_paper_white_from_the_profile import (      # noqa: E402,F401
    _fpg_sheet, _project)
from workflow import measurement_report as MR                  # noqa: E402
import ui.dialogs.measurement_report_dialog as mrd             # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------------------
# 1. the solid rows' prediction is absolute, whatever the chart's intent
# --------------------------------------------------------------------------
def _relative(ti3: Path) -> None:
    """Make the FROM PROFILE GAMUT chart of *ti3* one built with the
    relative intent (its reference's CHROMIQ_INTENT)."""
    ref = next(ti3.parent.parent.glob("*-reference.ti3"))
    txt = ref.read_text(encoding="utf-8")
    txt, n = re.subn(r'CHROMIQ_INTENT "[^"]*"', 'CHROMIQ_INTENT "relative"',
                     txt)
    assert n == 1, "the reference carries no intent keyword"
    ref.write_text(txt, encoding="utf-8")


@pytest.fixture
def two_intents(monkeypatch):
    """xicclu's forward lookup, faked: the ABSOLUTE prediction of every
    corner is exactly its ideal value (which is what `_fpg_sheet` measured),
    the RELATIVE one 3 L* lighter. A row that compares the reading with the
    relative prediction reads about 3."""
    from workflow.gamut_target import CORNER_DEVICES, _corner_ideal_labs
    ideal = dict(zip(CORNER_DEVICES, _corner_ideal_labs()))
    asked = []

    def fake(rows, profile, bin_dir, *, intent="r", runner=None):
        asked.append((len(rows), intent))
        shift = 0.0 if intent == "a" else 3.0
        out = []
        for r in rows:
            lab = ideal[tuple(float(x) for x in r)]
            out.append((lab[0] + shift, lab[1], lab[2]))
        return out
    monkeypatch.setattr("workflow.xicclu_runner.forward_lab", fake)
    return asked


def test_a_relative_chart_s_solids_are_predicted_absolute(tmp_path,
                                                          two_intents):
    """A perfect print of a relative-intent FROM PROFILE GAMUT chart: the
    solid rows read 0, as on an absolute chart. The strip keeps asking with
    the chart's own intent (the older question, B8-1272, not changed here).

    MUTATION, proven red: drop the absolute re-ask in
    `condition_reference_block` (the rows read 3.0 / the relative shift)."""
    ti3 = _fpg_sheet(tmp_path)
    _relative(ti3)
    rep = MR.build_report(ti3, argyll_bin="/fake/argyll")
    assert rep["colorimetric"]["intent"] == "relative"
    assert (7, "r") in two_intents, "the strip no longer asks the chart's intent"
    assert any(i == "a" for _n, i in two_intents), "no absolute prediction"
    vals = MR.row_values(rep)
    assert vals["solids_de00_max"]["value"] == pytest.approx(0.0, abs=0.02)
    assert vals["cmy_solids_dhab_max"]["value"] == pytest.approx(0.0,
                                                                 abs=0.02)


def test_an_absolute_chart_asks_once(tmp_path, two_intents):
    """An absolute chart reuses the strip's own prediction: xicclu is asked
    once, absolute, and the rows read 0.

    MUTATION, proven red: ask again whatever the intent (two lookups)."""
    rep = MR.build_report(_fpg_sheet(tmp_path), argyll_bin="/fake/argyll")
    assert [i for _n, i in two_intents] == ["a"]
    assert MR.row_values(rep)["solids_de00_max"]["value"] == pytest.approx(
        0.0, abs=0.02)


@pytest.mark.slow
def test_a_perfect_print_reads_zero_in_both_intents_through_argyll(tmp_path):
    """The adversary's setup (relative_fpg.json), through ArgyllCMS for real:
    a FROM PROFILE GAMUT chart of 200 colours built by the app's module with
    each intent from one profile, a sheet fakeread through the same profile
    (a printer that prints exactly as profiled), judged against ISO
    12647-7. Before: relative 2.94 / 2.13, absolute 0.01 / 0.02."""
    argyll = Path("/Applications/Argyll/bin")
    if not (argyll / "xicclu").exists():
        pytest.skip("ArgyllCMS is not installed")
    import sys
    from datetime import datetime
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import make_report_limit_demos as DEMO
    from core.file_manager import Project
    from workflow.ti3_analysis import mark_verification_ti3
    # a real profile whose white is not D50, so the two intents differ
    src = argyll.parent / "ref" / "sRGB.icm"
    if not src.is_file():
        pytest.skip("ArgyllCMS's sRGB.icm is not installed")
    got = {}
    for intent in ("absolute", "relative"):
        proj = Project.create(tmp_path / intent, f"FPG-{intent}")
        run = proj.current_run()
        run.ensure_dir()
        shutil.copy2(src, run.dir / f"{run.stem}.icc")
        icc = run.built_profile_icc()
        vstem = run.verify_stem
        try:
            DEMO.make_gamut_chart(run.verifications_dir, vstem,
                                  DEMO.GamutChartRecipe(200, "A4",
                                                        intent=intent), icc)
        except Exception as exc:                       # noqa: BLE001
            pytest.skip(f"the profile cannot make a chart: {exc}")
        v = run.new_verification(datetime(2026, 9, 26, 10, 0, 0))
        v.ensure_dir()
        wk = v.dir / "_work"
        wk.mkdir()
        for ext in (".ti1", ".ti2", "-reference.ti3"):
            shutil.copy2(run.verifications_dir / f"{vstem}{ext}",
                         wk / f"{vstem}{ext}")
        ti3 = DEMO.fakeread(wk, vstem, icc)
        mark_verification_ti3(ti3)
        shutil.move(str(ti3), str(v.dir / f"{vstem}.ti3"))
        shutil.rmtree(wk)
        rep = MR.build_report(v.measurement_ti3, argyll_bin=argyll)
        vals = MR.row_values(rep)
        got[intent] = (vals["solids_de00_max"]["value"],
                       vals["cmy_solids_dhab_max"]["value"])
    for intent, (de, dh) in got.items():
        assert de is not None and de < 0.5, (intent, got)
        assert dh is None or dh < 0.5, (intent, got)


# --------------------------------------------------------------------------
# 2. only a verification is compared with the profile
# --------------------------------------------------------------------------
def test_a_profiling_measurement_is_not_compared_with_the_profile(tmp_path):
    """The same sheet as a verification reads its paper against the
    profile (K49); as a profiling measurement it reads what the row gave
    it before K49: N-A, needs a reference for the printing condition.

    MUTATION, proven red: drop the ``is_verification`` guard at the top of
    `condition_reference_block`."""
    ti3 = _project(tmp_path, with_paper=True)
    rep = MR.build_report(ti3)
    assert rep["is_verification"] is True
    cond = rep["condition_reference"]["paper"]
    assert cond["from"] == MR.CONDITION_FROM_PROFILE
    assert MR.row_values(rep)["substrate_de00_max"]["value"] is not None
    prof = dict(rep, is_verification=False)
    prof["condition_reference"] = MR.condition_reference_block(
        prof, ti3_path=ti3, argyll_bin=None)
    assert prof["condition_reference"] == {
        "paper": {"from": MR.CONDITION_NOT_VERIFICATION},
        "solids": {"from": MR.CONDITION_NOT_VERIFICATION}}
    vals = MR.row_values(prof)
    for rid in ("substrate_de00_max", "solids_de00_max",
                "cmy_solids_dhab_max"):
        assert vals[rid]["value"] is None, rid
        assert vals[rid]["reason"] == MR.REASON_NEEDS_REFERENCE_FILE, rid
        assert not vals[rid]["notes"], rid


def test_a_run_s_own_sheet_is_not_compared_with_its_own_profile(tmp_path):
    """The run's profiling sheet, where build_report finds it: not a
    verification, so no paper value against the profile built from it.

    MUTATION, proven red: as above."""
    ti3 = _project(tmp_path, with_paper=True)
    run_dir = ti3.parent.parent.parent
    for f in ti3.parent.glob("*-verify.ti*"):
        shutil.copy2(f, run_dir / f.name.replace("-verify", ""))
    sheet = run_dir / ti3.name.replace("-verify", "")
    txt = sheet.read_text(encoding="utf-8")
    sheet.write_text(re.sub(r"(?m)^CHROMIQ_VERIFICATION.*\n", "", txt),
                     encoding="utf-8")
    rep = MR.build_report(sheet)
    assert rep["is_verification"] is False
    assert rep["condition_reference"]["paper"]["from"] \
        == MR.CONDITION_NOT_VERIFICATION
    assert MR.row_values(rep)["substrate_de00_max"]["value"] is None


def test_the_help_says_a_profiling_measurement_reads_n_a():
    """The three rows' help is true for both kinds of measurement.

    MUTATION, proven red: take the profiling sentence out of any of the
    three."""
    from workflow.compliance_sets import ROW_BY_ID
    for rid in ("substrate_de00_max", "solids_de00_max",
                "cmy_solids_dhab_max"):
        text = ROW_BY_ID[rid].detect
        said = [p for p in re.split(r"(?<=\.)\s", text)
                if "profiling measurement" in p]
        assert said, rid
        assert "N-A" in " ".join(said) or "N-A" in text.split(
            "profiling measurement", 1)[1], rid
    assert "verification" in ROW_BY_ID["substrate_de00_max"].remedy


# --------------------------------------------------------------------------
# 3. the Printing record names every graph it carries
# --------------------------------------------------------------------------
def test_every_graph_has_a_name_in_the_record_sentence():
    """MUTATION, proven red: drop a key from `_RECORD_GRAPH_NAMES`."""
    assert set(mrd.MeasurementReportDialog._RECORD_GRAPH_NAMES) \
        == set(mrd._TREND_ABOUT)


def test_the_record_sentence_names_graphs_beyond_the_first_four(
        tmp_path, qapp, monkeypatch):
    """A drawn Evenness graph is named; `_graphs_drawn_for` looks at every
    tab, not the four that need no limit.

    MUTATION, proven red: keep `_graphs_drawn_for` to the four original
    charts (Evenness is never counted)."""
    from PyQt6.QtGui import QColor
    from tests.test_k32_report_rows_and_switch import _profiling_window
    dlg, host = _profiling_window(tmp_path, qapp)
    try:
        runs = dlg._runs_for_document()
        ev = dlg._trend_groups["evenness"]
        plan = [(ev, "Evenness", [("x", QColor("red"), lambda pt: 1.0)],
                 None, 1, False, None, [], True)]
        monkeypatch.setattr(dlg, "_trend_plan", lambda: plan)
        monkeypatch.setattr(mrd.MeasurementReportDialog, "_trend_extras",
                            lambda self, c: {"withheld": []})
        monkeypatch.setattr(MR, "report_trend",
                            lambda rs: [{"created": "a"}, {"created": "b"}])
        assert dlg._graphs_drawn_for(runs) == ["evenness"]
        monkeypatch.setattr(dlg, "_graphs_drawn_for",
                            lambda r: ["de", "white", "paper_diff", "solids",
                                       "strip", "evenness"])
        s = dlg._record_graphs_sentence(runs)
        assert s.endswith("The graphs it carries show colour accuracy, "
                          "paper white, the paper white difference, the solid "
                          "colours, the control strip and evenness."), s
    finally:
        dlg.close()
        host.deleteLater()


# --------------------------------------------------------------------------
# 4. why no line is drawn: B8-1274 chose it from the set data; K50 (Knut,
#    #182 5845519118, B8-1320) ruled that a report never refers to what
#    other limit sets have, so it is one sentence about this report
# --------------------------------------------------------------------------
_THIS_REPORT = ("This report sets no limit for what this graph shows, so no "
                "limit line is drawn.")


def test_a_graph_with_no_limit_line_speaks_of_this_report_only():
    """Every graph, under every set: the same sentence, about this report.
    Paper white, Darkest black and Cube corners (no set has a row for them)
    and the graphs another set limits read alike.

    MUTATION, proven red: bring back "although other limit sets named after
    ISO 12647 have one" for a set that has none."""
    for key in list(mrd._NO_LIMIT_SHOWS) + [""]:
        s = mrd.no_limit_note(key, mrd.NO_LIMIT_WHY_SET)
        assert s.endswith(_THIS_REPORT), key
        for gone in ("other limit set", "another limit set", "any of its",
                     "ChromIQ has no limit", "named after ISO"):
            assert gone not in s, (key, gone)
    # and the caption above Paper white difference claims no limit line,
    # which a graph shown with none (K49) would contradict
    assert "limit" not in mrd._TREND_ABOUT["paper_diff"]()


def test_the_sentence_does_not_read_the_sets(monkeypatch):
    """No set is asked: take every number out of every set, or give one set a
    number on the tone row, and the sentence does not move.

    MUTATION, proven red: key the tail on `factory_limits` again."""
    import workflow.compliance_sets as cs
    from workflow.compliance_sets import Limit
    before = {k: mrd.no_limit_note(k) for k in mrd._NO_LIMIT_SHOWS}
    monkeypatch.setattr(cs, "factory_limits", lambda sid: {})
    assert {k: mrd.no_limit_note(k) for k in mrd._NO_LIMIT_SHOWS} == before
    monkeypatch.setattr(cs, "factory_limits", lambda sid: (
        {"ramps_30_70_dl_max": Limit.value(2.0)}
        if sid == "iso_12647_8" else {}))
    assert {k: mrd.no_limit_note(k) for k in mrd._NO_LIMIT_SHOWS} == before


def test_the_new_sentences_are_german_by_hand_and_name_no_control():
    """German by hand, no "du" (report text), no em dash, no control of the
    app named (K39), no other limit set named (K50).

    MUTATION, proven red: delete one German entry."""
    import json
    from core.resource_path import resource_path
    de = json.load(open(resource_path("data/i18n/de.json"), encoding="utf-8"))
    texts = [mrd._NO_LIMIT_WHY[mrd.NO_LIMIT_WHY_SET](),
             mrd._SHEET_GRAPH_NOTES["corners"]()] + [
        f() for f in mrd.MeasurementReportDialog._RECORD_GRAPH_NAMES.values()]
    for en in texts:
        for word in ("Choose", "Press", "tick", "window", "tab", "button"):
            assert not re.search(rf"\b{word}\b", en), (word, en)
        assert "—" not in en
        g = de.get(en)
        assert g and g != en and "—" not in g, en
        assert " du " not in f" {g.lower()} " and "dein" not in g.lower(), en
        assert "Grenzwertsätze" not in g and "anderer" not in g, g
    assert de[_THIS_REPORT] == (
        "Dieser Bericht setzt für das, was diese Grafik zeigt, keinen "
        "Grenzwert, daher ist keine Grenzwertlinie eingezeichnet.")


# --------------------------------------------------------------------------
# 5. the Cube corners sentence agrees with its caption
# --------------------------------------------------------------------------
def test_the_cube_corners_sentence_says_aim_values_as_the_caption_does():
    """MUTATION, proven red: restore "from their ideal values".

    K51: the sentence is the Cube corners one of `_SHEET_GRAPH_NOTES`."""
    s = mrd._SHEET_GRAPH_NOTES["corners"]()
    assert "from their aim values" in s
    assert "aim values" in mrd._TREND_ABOUT["corners"]()
    assert "from their ideal values" not in s
    # only the black and the six colours are called ideal
    assert "aims of the black and the six colours are ideal values" in s


# --------------------------------------------------------------------------
# 7. a graph with no limit line needs two dates
# --------------------------------------------------------------------------
def test_a_graph_with_no_line_and_one_dated_value_is_hidden(tmp_path, qapp,
                                                            monkeypatch):
    """A tab that judges nothing is shown only for its trend. Since K51 that
    is a tab whose limit lines are shown for information (a Printing record:
    Grey balance, limited by ChromIQ default and judged on no date). With a
    value on ONE date only it would be an empty frame that "draws no trend":
    hidden, in the window and the PDF (one plan).

    MUTATION, proven red: drop the ``_dated < 2`` check in `_trend_plan`."""
    from tests.test_trend_graphs_for_judged_metrics import _open
    from workflow.compliance_sets import effective_limits
    dlg = _open(tmp_path, qapp, effective_limits("chromiq_default", {}))
    try:
        monkeypatch.setattr(type(dlg), "_ungraded_by_type", lambda self: True)
        grey = dlg._trend_groups["grey"]
        shown = {c: s for c, *_r, s in dlg._trend_plan()}
        assert shown[grey] is True, "the fixture has no grey trend"
        assert "grey_balance_neutral_ramp_avg" in dlg._info_trend_limits()
        for pt in dlg._trend_series[1:]:
            for rid in ("grey_balance_neutral_ramp_avg",
                        "grey_balance_neutral_ramp_max"):
                (pt.get("rows") or {}).pop(rid, None)
        shown = {c: s for c, *_r, s in dlg._trend_plan()}
        assert shown[grey] is False
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# 8. a value shown for information carries the note too
# --------------------------------------------------------------------------
def test_an_info_solid_value_carries_the_predicted_note(tmp_path,
                                                        two_intents,
                                                        monkeypatch):
    """A solid value shown for information (an ungraded sheet, a raw drift
    check: INFO) says what it was compared with, like a judged one.

    MUTATION, proven red: give INFO rows no notes in `judge`."""
    from workflow.compliance_sets import INFO, Limit
    rep = MR.build_report(_fpg_sheet(tmp_path), argyll_bin="/fake/argyll")
    monkeypatch.setattr(MR, "is_graded_sheet", lambda _r: False)
    rows = {r["row_id"]: r for r in MR.judge(rep, {
        "solids_de00_max": Limit.value(3.0),
        "cmy_solids_dhab_max": Limit.value(2.5)})}
    for rid in ("solids_de00_max", "cmy_solids_dhab_max"):
        assert rows[rid]["word"] == INFO, rows[rid]
        assert rows[rid]["value"] is not None
        assert MR.NOTE_SOLIDS_PREDICTED in rows[rid]["notes"], rid


def test_a_printing_record_keeps_the_value_notes(qapp, tmp_path):
    """The Printing record clears the notes that comment a verdict and
    keeps the ones that say what the value is.

    MUTATION, proven red: clear every note in `_ungrade` again."""
    from tests.test_k32_report_rows_and_switch import _profiling_window
    from workflow.compliance_sets import INFO, PASS
    dlg, host = _profiling_window(tmp_path, qapp)
    try:
        assert dlg._ungraded_by_type()
        rows = [{"row_id": "solids_de00_max", "word": PASS, "value": 0.1,
                 "notes": [MR.NOTE_SOLIDS_PREDICTED,
                           MR.NOTE_RECOMMENDED_LIMIT]}]
        out = dlg._ungrade(rows)
        assert out[0]["word"] == INFO
        assert out[0]["notes"] == [MR.NOTE_SOLIDS_PREDICTED]
    finally:
        dlg.close()
        host.deleteLater()


# --------------------------------------------------------------------------
# 6. the K49 driver photographs the page with no selection on it
# --------------------------------------------------------------------------
def test_the_k49_driver_leaves_no_selection_on_the_page(qapp):
    """`QTextBrowser.find()` selects what it finds; the driver scrolled with
    it and photographed the blue highlight (B8-1278).

    MUTATION, proven red: call ``view.ensureCursorVisible()`` in place of
    `_show_without_selection` in `_scroll_to`."""
    import sys
    import types
    from PyQt6.QtWidgets import QTextBrowser
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import drive_k49_reference_rows as K49
    view = QTextBrowser()
    view.setHtml("<p>intro</p><table><tr><td>Maximum ΔE00, solid colours"
                 "</td><td>PASS</td></tr></table>")
    dlg = types.SimpleNamespace(_view=view)
    assert K49._scroll_to(dlg, "Maximum ΔE00, solid colours", row=True)
    assert not view.textCursor().hasSelection()
    assert K49._scroll_to(dlg, "intro")
    assert not view.textCursor().hasSelection()
    view.deleteLater()
