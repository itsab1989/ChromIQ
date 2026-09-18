"""#182, beta 22: "Which presets can be verified", and the answers are the
report's own.

Knut asked for a button under the Create Chart presets dropdown opening a
window that lists the presets fulfilling the requirements for verification on a
chosen report type and limit set, highlights the charts suited to verification,
and says what a preset that falls short is missing.

Three things these guards refuse to let drift:

1. **the button is where he asked for it**, measured on a real ``TabChart`` in
   Manual mode, and the real click opens the real window;
2. **the window never hides a preset.** That decision was measured (see the
   dialog's own docstring) and a filter would show an empty list on the
   strictest combination, so "every preset is listed" is asserted on the real
   shipped set, in the state where nothing answers everything;
3. **the answers come from `measurement_report`, not from a second opinion.**
   Moving one of the report's own thresholds moves this window's verdict, and
   that is asserted by moving it.

The fixtures are the REAL preset set: 177 built-in charts with their real
`.ti1` files. A hand-made three-entry fixture cannot contain the fault this
window exists to find.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                           # noqa: E402

from core.argyll_runner import ArgyllRunner                        # noqa: E402
from core.file_manager import FileManager                          # noqa: E402
from core.preset_store import save_presets, sidecar_path           # noqa: E402
from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS,              # noqa: E402
                               TabChart, verification_preset_rows)
from workflow import compliance_sets as CS                         # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

#: The strictest combination ChromIQ can be asked for, and the one that decided
#: the window marks rather than filters: 16 rows, six of which no preset chart
#: can supply.
STRICT = (MR.REPORT_TYPE_FULL, "custom_iso_12647_7")
#: The everyday one: seven rows, every one of them a chart's own patches.
EVERYDAY = (MR.REPORT_TYPE_FULL, "chromiq_default")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def rows(qapp):
    """The REAL list the window is handed, built by the tab's own function."""
    return verification_preset_rows(AppSettings())


@pytest.fixture(scope="module")
def builtin_charts(qapp):
    """(label, .ti1 path) for every built-in preset that ships a chart."""
    out = []
    for r in verification_preset_rows(AppSettings()):
        if r.builtin and r.chart is not None:
            out.append((r.label, r.chart))
    return out


# ---------------------------------------------------------------------------
# 1. the button, on the real tab, through the app's own sequence
# ---------------------------------------------------------------------------
@pytest.fixture
def tab(qapp):
    s = AppSettings()
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t.show()
    qapp.processEvents()
    t._manual_btn.click()
    qapp.processEvents()
    yield t
    t.close()
    t.deleteLater()
    qapp.processEvents()


def test_the_button_sits_below_the_preset_dropdown(tab, qapp):
    """Knut: *"the function button I specified in Create Chart, BELOW the
    preset selection dropdown"*. Measured on the laid-out widgets, because a
    button in the same group box is not the same thing as a button under the
    dropdown."""
    btn, combo = tab._preset_verify_btn, tab._preset_combo
    top = btn.mapTo(tab, btn.rect().topLeft()).y()
    bottom = combo.mapTo(tab, combo.rect().bottomLeft()).y()
    assert top >= bottom, (
        f"the button's top is at y={top}, the dropdown's bottom at y={bottom}")
    assert btn.isVisibleTo(tab)
    assert combo.parent() is btn.parent(), \
        "the button left the Presets group box"


def test_the_button_opens_the_window_with_the_real_preset_list(tab, qapp,
                                                               monkeypatch):
    """The REAL click, the REAL handler, the REAL dialog. Two methods called
    by hand would not catch a button connected to nothing."""
    seen: list = []

    def _no_block(self):
        seen.append(self)
        return 0
    monkeypatch.setattr(PVD.PresetVerificationDialog, "exec", _no_block)
    tab._preset_verify_btn.click()
    qapp.processEvents()
    assert seen, "clicking the button opened no window"
    dlg = seen[0]
    assert dlg.windowTitle()
    assert len(dlg._rows) >= 100, \
        f"the window was handed only {len(dlg._rows)} presets"
    dlg.close()


# ---------------------------------------------------------------------------
# 2. it marks; it never hides
# ---------------------------------------------------------------------------
def test_every_shipped_preset_reaches_the_window(rows):
    listed = {r.label for r in rows if r.builtin}
    shipped = {overlay for _g, entries in BUILTIN_PRESET_GROUPS
               for (_c, overlay, _k) in entries}
    assert listed == shipped, f"missing: {sorted(shipped - listed)}"


def test_nothing_is_hidden_on_the_combination_that_nothing_answers(qapp, rows):
    """THE WHOLE REASON THE WINDOW MARKS INSTEAD OF FILTERING.

    On Full colour check judged against Custom ISO 12647-7, not one shipped
    preset answers every row asked, because both Custom columns limit the three
    reference rows and the three control-strip rows and no preset chart carries
    either. A filter would open on an empty list; this asserts the list is
    full.
    """
    dlg = PVD.PresetVerificationDialog(rows)
    try:
        dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(STRICT[0]))
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(STRICT[1]))
        qapp.processEvents()
        built = [r for r in dlg._rows if r.builtin]
        assert not any(r.assessment.answers_everything for r in built), \
            "a built-in preset answered every row of the strictest set"
        shown = sum(dlg._tree.topLevelItem(i).childCount()
                    for i in range(dlg._tree.topLevelItemCount()))
        assert shown == len(dlg._rows), \
            f"{len(dlg._rows) - shown} presets were hidden"
    finally:
        dlg.close()


def test_the_opt_in_tick_box_is_the_only_thing_that_narrows(qapp, rows):
    dlg = PVD.PresetVerificationDialog(rows)
    try:
        qapp.processEvents()
        assert not dlg._only_star.isChecked(), "the window opens filtered"
        dlg._only_star.setChecked(True)
        qapp.processEvents()
        shown = sum(dlg._tree.topLevelItem(i).childCount()
                    for i in range(dlg._tree.topLevelItemCount()))
        assert shown == sum(1 for r in dlg._rows if r.starred)
        assert 0 < shown < len(dlg._rows)
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 3. the answers are the report's own
# ---------------------------------------------------------------------------
def test_moving_the_reports_own_threshold_moves_this_window(builtin_charts,
                                                            monkeypatch):
    """NO SECOND OPINION. The outer-gamut row is judged when the top chroma
    quarter holds `OUTER_GAMUT_MIN` patches; raise that constant in
    `measurement_report` and this window must stop saying the chart can answer
    the row. A window with its own copy of the number would not notice."""
    _label, chart = builtin_charts[0]
    PE.clear_cache()
    before = PE.chart_row_values(chart)["outer_gamut_226_de00_avg"]
    assert before["value"] is not None, "pick a chart that answers it"
    monkeypatch.setattr(MR, "OUTER_GAMUT_MIN", 10 ** 9)
    PE.clear_cache()
    after = PE.chart_row_values(chart)["outer_gamut_226_de00_avg"]
    assert after["value"] is None
    assert after["reason"] == MR.REASON_TOO_FEW_OUTER_PATCHES
    PE.clear_cache()


def test_the_grey_rule_is_the_reports_grey_rule(builtin_charts, monkeypatch):
    """The same, on the grey ramp's minimum number of steps."""
    _label, chart = builtin_charts[0]
    PE.clear_cache()
    assert PE.chart_row_values(chart)[
        "grey_balance_neutral_ramp_avg"]["value"] is not None
    monkeypatch.setattr(MR, "GREY_MIN_LEVELS", 10 ** 6)
    PE.clear_cache()
    v = PE.chart_row_values(chart)["grey_balance_neutral_ramp_avg"]
    assert v["value"] is None and v["reason"] == MR.REASON_TOO_FEW_STEPS
    PE.clear_cache()


def test_what_a_report_type_asks_is_the_reports_own_row_list(monkeypatch):
    asked = PE.rows_asked(MR.REPORT_TYPE_GREY, "custom_iso_12647_7")
    only = set(MR.rows_for_report_type(MR.REPORT_TYPE_GREY) or ())
    assert asked and set(asked) <= only


def test_a_report_type_that_grades_nothing_asks_for_nothing():
    """T4 withholds every judgement, so no chart can be short of anything for
    it. Asking the set's sixteen rows there would mark every preset down for a
    document that judges none of them."""
    for sid in CS.selectable_set_ids(None):
        assert PE.rows_asked(MR.REPORT_TYPE_RECORD, sid) == ()


def test_a_set_that_limits_nothing_is_not_offered():
    """The two read-only ISO columns ship empty, so `selectable_set_ids` leaves
    them out and this window can never open on one."""
    ids = CS.selectable_set_ids(None)
    for sid in ("iso_12647_7", "iso_12647_8"):
        assert sid not in ids


# ---------------------------------------------------------------------------
# 4. a chart that really is short, and what it is told
# ---------------------------------------------------------------------------
def _write_ti1(path: Path, rgbs) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "test"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(rgbs)}",
             "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rgbs, start=1):
        y = max(0.05, (0.2126 * r + 0.7152 * g + 0.0722 * b))
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f} "
                     f"{y * 0.9505:.4f} {y:.4f} {y * 1.089:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_a_chart_too_small_is_told_exactly_what_it_is_short_of(tmp_path):
    """Twelve patches, no grey ramp worth the name, no mid-tone ramp. Every
    reason that comes back is one of the report's own codes, and each is a
    patch shortfall a different preset would fix."""
    chart = _write_ti1(tmp_path / "tiny.ti1",
                       [(v, 0.0, 0.0) for v in range(0, 101, 10)] + [(0, 0, 0)])
    PE.clear_cache()
    a = PE.assess(chart, *EVERYDAY)
    missing = dict(a.missing)
    assert a.checked
    assert missing, "a twelve-patch chart answered every row"
    assert missing.get("worst5_de00_avg") == MR.REASON_SMALL_SAMPLE
    assert missing.get("grey_balance_neutral_ramp_avg") in (
        MR.REASON_NO_GREYS, MR.REASON_TOO_FEW_STEPS,
        MR.REASON_NO_WHITE, MR.REASON_NO_BLACK)
    assert all(PE.is_patch_shortfall(w) for w in missing.values()), missing
    assert not PE.made_for_verification(chart, 12, 1)
    PE.clear_cache()


def test_every_reason_this_window_can_show_has_a_sentence():
    """A row that says only "✕" teaches nobody anything, which is the half of
    Knut's request this covers."""
    fallback = PVD.reason_line("__not_a_reason__")
    for code in sorted(PE.classified_reasons()):
        line = PVD.reason_line(code)
        assert line, code
        if code != MR.REASON_NOT_COMPUTED:
            assert line != fallback, f"{code} falls back to the generic line"


def test_every_reason_the_report_can_produce_is_classified():
    """The two buckets have to cover everything, or the star quietly mis-files
    a shortfall as somebody else's problem."""
    #: A NOTE, not a reason: it comments a verdict that WAS given, and
    #: `row_values` passes it in `notes`, never in `reason`.
    notes = {MR.NOTE_PRINTING_UNRECORDED, MR.REASON_PRINTING_UNRECORDED}
    produced = {v for k, v in vars(MR).items()
                if k.startswith("REASON_") and isinstance(v, str)}
    assert produced - notes <= PE.classified_reasons(), \
        sorted(produced - notes - PE.classified_reasons())


def test_a_missing_row_shows_the_metrics_own_lever(qapp, rows):
    """The remedy under a ✕ is the metric help icon's own `remedy` string, not
    a second sentence written here that could say something else."""
    dlg = PVD.PresetVerificationDialog(rows)
    try:
        dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(STRICT[0]))
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(STRICT[1]))
        qapp.processEvents()
        row = next(r for r in dlg._rows if r.assessment.missing)
        dlg._show_detail(row)
        qapp.processEvents()
        shown = [dlg._detail_layout.itemAt(i).widget().text()
                 for i in range(dlg._detail_layout.count())
                 if dlg._detail_layout.itemAt(i).widget() is not None]
        for rid, why in row.assessment.missing:
            assert PVD.reason_line(why) in shown, why
            remedy = PE.row_remedy(rid)
            if remedy:
                assert remedy in shown, rid
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 5. the star, in numbers, on the real set
# ---------------------------------------------------------------------------
def test_the_star_means_one_page_and_a_few_hundred_patches(rows):
    """Knut: *"any one-page preset … from about 80 patches to a few hundred"*.

    Asserted as the conditions themselves rather than as a count, so adding a
    preset cannot make this test wrong and cannot make it vacuous either: every
    starred preset meets all three, and every unstarred one fails at least one.
    """
    for r in rows:
        meets = (r.chart is not None
                 and r.pages == PE.VERIFICATION_MAX_PAGES
                 and 0 < r.patches <= PE.VERIFICATION_MAX_PATCHES
                 and not PE.assess(r.chart, *EVERYDAY).patch_shortfalls)
        starred = PE.made_for_verification(r.chart, r.patches, r.pages)
        assert starred == meets, f"{r.label}: starred={starred}, meets={meets}"


def test_the_star_does_not_move_when_the_pulldowns_do(qapp, rows):
    """It describes the CHART. A mark that flickers while a reader compares two
    report types is a mark nobody can use."""
    dlg = PVD.PresetVerificationDialog(rows)
    try:
        marks = {}
        for tid in (MR.REPORT_TYPE_FULL, MR.REPORT_TYPE_GREY,
                    MR.REPORT_TYPE_RECORD):
            for sid in ("chromiq_default", "custom_iso_12647_7"):
                dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(tid))
                dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(sid))
                qapp.processEvents()
                marks[(tid, sid)] = tuple(r.starred for r in dlg._rows)
        assert len(set(marks.values())) == 1, "the star moved with a pulldown"
    finally:
        dlg.close()


def test_each_instrument_group_has_at_least_one_starred_preset(rows):
    """Knut: *"Most preset groups for instruments and medium and small paper
    sizes have at least one chart preset with a lower patch count"*. Measured:
    the four instrument groups do. Scanner and Red River Paper do not, and are
    named here so that stays a stated fact rather than a silent gap: the
    Scanner charts start at 3,250 patches and the Red River set is 2,052
    patches over four to nine sheets."""
    groups = {}
    for r in rows:
        if r.builtin:
            groups.setdefault(r.group, []).append(r.starred)
    without = sorted(g for g, marks in groups.items() if not any(marks))
    assert without == ["Red River Paper", "Scanner"], without


def test_the_three_reference_rows_are_beyond_every_preset(builtin_charts):
    """MEASURED, on all of them: a colorimetric reference is written only
    beside a chart built FROM PROFILE GAMUT, so no preset can answer these
    three, and the window says so with the row's own remedy instead of
    pretending otherwise."""
    for label, chart in builtin_charts:
        v = PE.chart_row_values(chart)
        for rid in ("substrate_de00_max", "solids_de00_max",
                    "cmy_solids_dhab_max"):
            assert v[rid]["value"] is None, f"{label} answered {rid}"
            assert v[rid]["reason"] == MR.REASON_NEEDS_REFERENCE_FILE


def test_the_control_strip_is_the_one_chromiq_would_declare(builtin_charts):
    """NO PRESET SHIPS A `.control-strip.json`, and reading one off the disk
    would have this window tell every user that every preset declares no
    control strip. That was true until B8-405 landed the same week: ChromIQ now
    writes the declaration out of the chart's own patches when a verification
    chart is filed. Measured on all 177: every one fills the ladder past its
    twenty-rung mark, so all three control-strip rows are answered."""
    from workflow import control_strip as CSP
    for label, chart in builtin_charts:
        assert MR.control_strip_declaration(chart, chart) is None, \
            f"{label} ships a declaration; this test is about the ones that do not"
        assert CSP.strip_for_chart(chart).p95_ready, label
        v = PE.chart_row_values(chart)
        for rid in ("control_strip_de00_avg", "control_strip_de00_max",
                    "control_strip_de00_p95"):
            assert v[rid]["value"] is not None, f"{label} withheld {rid}"


def test_a_chart_whose_ladder_does_not_fill_is_told_so(tmp_path):
    """The other side: a chart with too few of the strip's colours on it gets
    `no_control_strip`, which is the reason ChromIQ's own declaration code
    returns rather than one this window invents."""
    from workflow import control_strip as CSP
    chart = _write_ti1(tmp_path / "flat.ti1",
                       [(v, v, v) for v in range(0, 100, 4)])
    assert not CSP.strip_for_chart(chart).can_declare
    PE.clear_cache()
    v = PE.chart_row_values(chart)
    assert v["control_strip_de00_avg"]["reason"] == MR.REASON_NO_CONTROL_STRIP
    PE.clear_cache()


# ---------------------------------------------------------------------------
# 6. a preset ChromIQ cannot check at all
# ---------------------------------------------------------------------------
def test_a_user_preset_with_no_patch_set_is_listed_and_told_why(qapp):
    """It cannot be judged, and saying nothing about it is not an option."""
    save_presets("create_chart", {
        "Settings only, no chart": {"attached_ti1": False},
    })
    try:
        rows = verification_preset_rows(AppSettings())
        mine = [r for r in rows if r.label == "Settings only, no chart"]
        assert mine, "the user preset never reached the window"
        row = mine[0]
        assert row.chart is None
        dlg = PVD.PresetVerificationDialog(rows)
        try:
            qapp.processEvents()
            assert not row.assessment.checked
            assert not row.starred
            dlg._show_detail(row)
            qapp.processEvents()
            shown = [dlg._detail_layout.itemAt(i).widget().text()
                     for i in range(dlg._detail_layout.count())
                     if dlg._detail_layout.itemAt(i).widget() is not None]
            assert PVD._unreadable_line(row) in shown
            assert any("attach its .ti1" in t for t in shown), \
                "the sentence does not name the tick box that fixes it"
            # AND IT NEVER PRINTS A ZERO. "0 patches · 0 pages" is a statement
            # about a preset whose chart ChromIQ has never seen, and it was on
            # screen before this line existed.
            assert not any(t.startswith("0 patch") or " 0 page" in t
                           for t in shown), shown
        finally:
            dlg.close()
    finally:
        save_presets("create_chart", {})


def test_a_user_preset_with_an_attached_chart_is_judged(qapp, tmp_path):
    """The other side of it: attach a real `.ti1` and the preset is assessed
    exactly like a built-in."""
    save_presets("create_chart", {"Mine": {"attached_ti1": True}})
    sc = sidecar_path("create_chart", "Mine", ".ti1")
    sc.parent.mkdir(parents=True, exist_ok=True)
    _write_ti1(sc, [(r, g, b)
                    for r in (0.0, 50.0, 100.0)
                    for g in (0.0, 50.0, 100.0)
                    for b in (0.0, 50.0, 100.0)])
    try:
        PE.clear_cache()
        rows = verification_preset_rows(AppSettings())
        mine = next(r for r in rows if r.label == "Mine")
        assert mine.chart == sc
        assert mine.patches == 27
        assert mine.assessment is PE.UNCHECKED      # not assessed until shown
        a = PE.assess(mine.chart, *EVERYDAY)
        assert a.checked and a.missing
    finally:
        save_presets("create_chart", {})
        sc.unlink(missing_ok=True)
        PE.clear_cache()


# ---------------------------------------------------------------------------
# 7. the window's own hygiene
# ---------------------------------------------------------------------------
def test_no_self_capturing_lambda_is_connected_to_a_signal():
    """CLAUDE.md's fade-scroll SIGSEGV rule, in the file it applies to."""
    import inspect
    src = inspect.getsource(PVD)
    for line in src.splitlines():
        if ".connect(" in line:
            assert "lambda" not in line, line.strip()


def test_no_user_facing_string_here_carries_an_em_dash():
    """The house rule, on the strings that reach the screen. Comments and
    docstrings are not user-facing and are left to
    `tests/test_no_new_em_dash_in_user_facing_text.py`, which is the sweep that
    owns this rule."""
    import ast
    import inspect
    for mod in (PVD, PE):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "tr"):
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        assert "—" not in a.value, a.value
