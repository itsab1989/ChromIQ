"""#182, Knut 2026-09-21: the presets window's first line, and what FROM
PROFILE GAMUT changes about the answer.

> *"In the scrolling window, containing the list of presets, the first line
> should be a separate line not part of the presets list, but representing the
> current layout defined in Create Chart. That line should always be at the top
> and be shown as 'Current chart layout in Create Chart tab'. That line must be
> clearly separated from all the other presets with a separator line which is
> not clickable. […] This line cannot be double-clicked, as no new preset shall
> be applied […] If a chart has not been created in Create Chart […] then the
> right info panel notifies about this and informs that a chart must first be
> created."*

Every clause of that is a test below, taken off the REAL widget rather than off
the code that built it: the item is at row 0, the separator under it accepts no
flags, the double-click handler refuses it, and the pane says what it says.

And the half that makes the line worth having: *"performs the check if the
current chart fulfils all the metric requirements, **including if the current
chart has applied the 'From Profile Gamut' feature**"*. A chart that carries a
colorimetric reference answers three metrics that no preset ever can, and the
test for that writes the reference beside a real chart and watches the answer
change. A guard that only asserted the ordinary case would pass on code that
ignored the feature entirely.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt                                        # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402

from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

CORNER_CHART = Path("assets/charts/pharmacist/rgb/colormunki/a4/tc300/tc300.ti1")
#: The strictest shipped combination: it puts a limit on the three metrics a
#: colorimetric reference is the only key to, so it is the one that can tell a
#: gamut chart from an ordinary one.
STRICT = (MR.REPORT_TYPE_FULL, "custom_iso_12647_7")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _corner_chart() -> Path:
    return Path(__file__).resolve().parent.parent / CORNER_CHART


def _a_chart_in(tmp_path: Path) -> Path:
    dst = tmp_path / "P.ti2"
    shutil.copy2(_corner_chart(), dst)
    return dst


def _write_reference_beside(chart: Path) -> Path:
    """Write the sidecar a FROM PROFILE GAMUT build leaves beside its chart.

    **A FIXTURE, NOT A SECOND IMPLEMENTATION.** The real one is
    `workflow.gamut_target.write_colorimetric_reference`, and reaching it means
    a real ICC profile and a real gamut walk, which is minutes of Argyll for a
    file whose only job here is to name eight sample ids. What keeps the two in
    step is the assertion at the end: the file is read back with the
    application's OWN reader, and if that reader stops understanding this
    layout the fixture fails rather than the test quietly proving nothing.
    """
    import numpy as np

    from workflow.gamut_target import read_colorimetric_reference
    from workflow.ti3_analysis import parse_ti3
    from workflow.verification_print import colorimetric_reference_for

    data = parse_ti3(chart)
    rgb = MR._rgb_to_0_100(np.asarray(data.rgb, dtype=float))
    rows, ids = [], []
    for _name, target in MR.CUBE_CORNERS:
        diffs = np.abs(rgb - np.array(target))
        i = int((diffs ** 2).sum(axis=1).argmin())
        assert float(diffs[i].max()) <= MR.CORNER_PRESENT_TOL
        sid = data.sample_ids[i]
        ids.append(sid)
        lab = MR.xyz_to_lab(tuple(v / 100.0 for v in data.xyz[i]))
        rows.append((sid, tuple(rgb[i]), tuple(lab), tuple(data.xyz[i])))
    out = colorimetric_reference_for(chart)
    lines = [
        "CTI3   ", "",
        'DESCRIPTOR "ChromIQ colorimetric verification reference"',
        'ORIGINATOR "ChromIQ"',
        'COLOR_REP "RGB_XYZ"',
        'CHROMIQ_SET_VERSION "1"',
        'CHROMIQ_INTENT "absolute"',
        'CHROMIQ_MARGIN "safe"',
        'CHROMIQ_MASTER_TOTAL "8"',
        'CHROMIQ_IN_GAMUT "8"',
        'CHROMIQ_REQUESTED "8"',
        f'CHROMIQ_CORNER_IDS "{" ".join(ids)}"', "",
        "NUMBER_OF_FIELDS 10",
        "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z LAB_L LAB_A LAB_B",
        "END_DATA_FORMAT", "",
        f"NUMBER_OF_SETS {len(rows)}",
        "BEGIN_DATA",
    ]
    for sid, dev, lab, xyz in rows:
        lines.append(" ".join([str(sid)]
                              + [f"{float(v):.4f}" for v in dev]
                              + [f"{float(v):.4f}" for v in xyz]
                              + [f"{float(v):.4f}" for v in lab]))
    lines += ["END_DATA", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    blob = read_colorimetric_reference(out)
    assert blob is not None and set(blob["corner_ids"]) == set(ids), (
        "the application's own reader no longer understands the reference "
        "this fixture writes, so nothing below is testing what it claims")
    return out


def _row(chart, **kw):
    return PVD.PresetRow(group="", label="", chart=chart, patches=0, pages=0,
                         builtin=False, key=None, is_current_chart=True, **kw)


def _dialog(qapp, current):
    presets = [PVD.PresetRow(group="Group A", label="Preset one", chart=None,
                             patches=0, pages=0, builtin=True, key="k1")]
    return PVD.PresetVerificationDialog(presets, None, None, current=current)


# ---------------------------------------------------------------------------
# 1. the line is where he asked for it, and says what he asked it to say
# ---------------------------------------------------------------------------
def test_the_current_chart_is_the_first_line_and_is_not_in_a_group(qapp, tmp_path):
    dlg = _dialog(qapp, _row(_a_chart_in(tmp_path)))
    try:
        tree = dlg._tree
        first = tree.topLevelItem(0)
        row = first.data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(row, PVD.PresetRow) and row.is_current_chart
        assert first.text(0).strip() == "Current chart layout in Create Chart tab"
        assert first.childCount() == 0, "the top line was made a group heading"
    finally:
        dlg.deleteLater()


def test_a_separator_under_it_takes_no_click(qapp, tmp_path):
    dlg = _dialog(qapp, _row(_a_chart_in(tmp_path)))
    try:
        sep = dlg._tree.topLevelItem(1)
        assert sep.data(0, Qt.ItemDataRole.UserRole) is None
        assert sep.flags() == Qt.ItemFlag.NoItemFlags, (
            "the separator under the current chart can be selected, so it is "
            "a row of the list rather than a rule between two of them")
        assert dlg._tree.itemWidget(sep, 0) is not None, \
            "the separator draws nothing, so it reads as a blank row"
    finally:
        dlg.deleteLater()


def test_the_tick_box_cannot_hide_the_current_chart(qapp, tmp_path):
    """*"That line should ALWAYS be at the top."* The star filter is advice
    about other people's charts; it may not remove the reader's own."""
    dlg = _dialog(qapp, _row(_a_chart_in(tmp_path)))
    try:
        dlg._only_star.setChecked(True)
        first = dlg._tree.topLevelItem(0)
        row = first.data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(row, PVD.PresetRow) and row.is_current_chart
    finally:
        dlg.deleteLater()


def test_a_double_click_on_it_loads_nothing(qapp, tmp_path):
    """**THE ROW IS GIVEN A KEY ON PURPOSE.** In the app it has none, so a
    guard that only checked `not row.key` would pass on code that had no rule
    about this row at all, and the rule would be one careless caller away from
    gone. Knut's sentence is about the ROW: *"This line cannot be
    double-clicked, as no new preset shall be applied."*"""
    row = _row(_a_chart_in(tmp_path))
    row.key = "some-preset-key"
    dlg = _dialog(qapp, row)
    try:
        first = dlg._tree.topLevelItem(0)
        dlg._on_double_clicked(first, 0)
        assert dlg.chosen_key is None, \
            "double-clicking the current chart tried to apply it as a preset"
        assert dlg.isVisible() is False
    finally:
        dlg.deleteLater()


def test_a_double_click_on_a_real_preset_still_loads_it(qapp, tmp_path):
    """The mutation's other half: the refusal must be about THIS row and not
    about double-clicking having been switched off."""
    dlg = _dialog(qapp, _row(_a_chart_in(tmp_path)))
    try:
        preset = dlg._tree.topLevelItem(2).child(0)
        dlg._on_double_clicked(preset, 0)
        assert dlg.chosen_key == "k1"
    finally:
        dlg.deleteLater()


def test_the_window_opens_on_the_current_chart_when_no_preset_is_named(qapp, tmp_path):
    """B8-611, photographed: with nothing chosen in the pulldown the window
    opened on 177 rows and a pane reading "Select a preset on the left", which
    is the emptiness B8-423 already fixed for the preset case. The chart the
    reader has is the most particular chart in the list."""
    dlg = _dialog(qapp, _row(_a_chart_in(tmp_path)))
    try:
        cur = dlg._tree.currentItem()
        assert cur is not None, "the window opens with nothing selected"
        row = cur.data(0, Qt.ItemDataRole.UserRole)
        assert isinstance(row, PVD.PresetRow) and row.is_current_chart
    finally:
        dlg.deleteLater()


def test_a_named_preset_still_wins_over_the_current_chart(qapp, tmp_path):
    """The caller's own answer to "which chart is this about" is not
    overridden by the fallback."""
    presets = [PVD.PresetRow(group="Group A", label="Preset one", chart=None,
                             patches=0, pages=0, builtin=True, key="k1")]
    dlg = PVD.PresetVerificationDialog(presets, None, None, select="Preset one",
                                       current=_row(_a_chart_in(tmp_path)))
    try:
        row = dlg._tree.currentItem().data(0, Qt.ItemDataRole.UserRole)
        assert row.label == "Preset one"
    finally:
        dlg.deleteLater()


def test_with_no_chart_the_pane_says_one_must_be_created(qapp):
    dlg = _dialog(qapp, _row(None))
    try:
        dlg.refresh()
        text = " ".join(line.text for line in PVD.detail_lines(dlg._current))
        assert "No chart is defined in the Create Chart tab" in text
        assert "Create a chart first" in text
        assert "This preset stores settings only" not in text, (
            "the no-chart line is a preset's sentence, which is not true of "
            "the current chart at all")
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 2. the check itself, including From Profile Gamut
# ---------------------------------------------------------------------------
def test_an_ordinary_chart_cannot_answer_the_reference_metrics(tmp_path):
    PE.clear_cache()
    chart = _a_chart_in(tmp_path)
    a = PE.assess(chart, *STRICT, None)
    missing = dict(a.missing)
    for rid in PE.gamut_only_rows():
        assert missing.get(rid) == MR.REASON_NEEDS_REFERENCE_FILE, \
            f"{rid} is not withheld from a chart with no reference"


def test_a_from_profile_gamut_chart_answers_them(tmp_path):
    """The one thing the current-chart line can show that no preset row ever
    can. Same chart, same set; the only change is the reference beside it."""
    PE.clear_cache()
    chart = _a_chart_in(tmp_path)
    before = PE.assess(chart, *STRICT, None)
    _write_reference_beside(chart)
    after = PE.assess(chart, *STRICT, None)
    for rid in PE.gamut_only_rows():
        assert rid in before.missing_ids(), rid
        assert rid in after.answered, (
            f"{rid} is still withheld from a chart built FROM PROFILE GAMUT, "
            "so the feature makes no difference to the check Knut asked for")


def test_the_answer_is_not_served_from_a_stale_cache(tmp_path):
    """The reference is written AFTER the sheet is laid out, so the chart file
    itself does not change when a chart becomes a gamut chart. Keyed on the
    chart alone, the first assessment would be the wrong one and would stay."""
    PE.clear_cache()
    chart = _a_chart_in(tmp_path)
    PE.assess(chart, *STRICT, None)          # warm the cache on the old state
    _write_reference_beside(chart)
    after = PE.assess(chart, *STRICT, None)  # …no clear_cache in between
    assert set(PE.gamut_only_rows()) <= set(after.answered)


def test_a_reference_that_has_gone_is_not_believed(tmp_path):
    """`chart_conversion_state` answers "converted-reference-missing" when the
    sidecar claims one and the file is not there. There is then nothing to
    read the corners out of, so the rows must fall back rather than crash or
    claim an answer."""
    import json
    PE.clear_cache()
    chart = _a_chart_in(tmp_path)
    ref = _write_reference_beside(chart)
    ref.unlink()
    chart.with_name(chart.stem + ".channels.json").write_text(
        json.dumps({"colorimetric_reference": ref.name}), encoding="utf-8")
    a = PE.assess(chart, *STRICT, None)
    missing = dict(a.missing)
    for rid in PE.gamut_only_rows():
        assert missing.get(rid) == MR.REASON_NEEDS_REFERENCE_FILE, rid


def test_the_pane_says_which_of_the_two_this_chart_is(tmp_path):
    """The three rows are withheld with the same words on a chart that was
    never converted and on one whose reference was deleted, so only this line
    tells a reader which they are looking at."""
    chart = _a_chart_in(tmp_path)
    plain = " ".join(l.text for l in PVD.detail_lines(
        _row(chart, from_profile_gamut=False)))
    assert "was not built with From Profile Gamut" in plain
    gamut = " ".join(l.text for l in PVD.detail_lines(
        _row(chart, from_profile_gamut=True)))
    assert "was built with From Profile Gamut" in gamut


# ---------------------------------------------------------------------------
# 3. the two windows read one function
# ---------------------------------------------------------------------------
def test_the_pane_renders_detail_lines_and_decides_nothing_itself():
    import inspect
    src = inspect.getsource(PVD.PresetVerificationDialog._show_detail)
    assert "detail_lines(" in src
    for banned in ("row.assessment", "a.missing", "a.answered"):
        assert banned not in src, (
            "the pane has grown an opinion of its own again, so the pre-flight "
            f"window can drift away from it: {banned}")


def test_the_summary_is_shorter_than_the_pane_and_says_the_same_things(tmp_path):
    PE.clear_cache()
    chart = _a_chart_in(tmp_path)
    row = _row(chart)
    row.assessment = PE.assess(chart, *STRICT, None)
    full = PVD.detail_lines(row)
    short = PVD.summary_lines(row)
    assert len(short) < len(full), \
        "the summary is no shorter than the pane it summarises"
    missing_labels = {PE.row_label(rid) for rid, _ in row.assessment.missing}
    shown = " ".join(l.text for l in short)
    for label in missing_labels:
        assert label in shown, \
            f"the summary drops {label!r}, which is what the reader must act on"
