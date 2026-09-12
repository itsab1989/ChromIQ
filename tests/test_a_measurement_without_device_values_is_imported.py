"""A measurement that carries no device values belongs to the chart that names
its patches, and both import doors have to be able to take it.

THE REPORT (a user verifying a profile, 2026-09-11). She printed a verification
chart through her profile, read all 420 squares of it on an i1iO in i1Profiler,
exported CGATS, and ChromIQ answered:

    This file does not match the verification chart
    the file could not be read as a measurement
    (No device RGB columns, only RGB charts are supported.)

She is right about the tool, and said so: i1Profiler's measure tool reads a
chart it did not generate, has no colour space to express device values in, and
*"won't let you select RGB data to be included in the export"*. Her file is
`SAMPLE_ID`, `SAMPLE_NAME` and 36 spectral columns. `txt2ti3` converts it
without complaint ("No device values found - hope that's OK!"), `spec2cie` adds
XYZ, and `colprof` would build from it.

TWO INDEPENDENT FAULTS, and this file pins both.

**One: the door needed device values it never had to have.** The pairing is
keyed on ``SAMPLE_ID`` and the device values are only the WITNESS that the
pairing is right. Her ids are i1Profiler's reading order, which is not the
chart's order at all. Her NAMES are ``A1 … T21``, which are exactly the chart's
own ``SAMPLE_LOC`` labels, because that is what the chart printed beside each
square and what she aimed the instrument at. So the key is the name, the chart
supplies the device values, and the file becomes an ordinary ChromIQ ``.ti3``.

**Two: the count was measured against the wrong number.** Her chart is 408
designed patches, which the layout engine fills out to 420 squares on Letter
with an i1Pro (20 strips of 21). The refusal window quoted 408 and the chart
preview beside it quoted 420. A measurement of the whole printed sheet HOLDS
420, and judging it against 408 called it "a measurement of a different chart".
The design says when a measurement is SHORT; the sheet says when it is somebody
else's. Both numbers are real and neither answers the other's question.

WHAT MUST NOT BE WEAKENED. The patch-for-patch check exists so a measurement of
the wrong chart cannot be filed against this run, and a name is a stricter key
than "unchecked", not a looser one: a wrong chart names patches this chart does
not have. Where a name match is all there is — another chart laid out exactly
the same way carries the same names — ChromIQ says so and the person decides
(M-IMPORT-DEVICE-FROM-CHART).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_import import assess, complete_from_chart   # noqa: E402
from workflow.measurement_pairing import (                            # noqa: E402
    attach_device_values_from_chart, device_came_from_chart, match_by_name)
from workflow.measurement_state import (classify, expected_patches,   # noqa: E402
                                        sheet_patches)
from workflow.ti3_analysis import Ti3ParseError, parse_ti3            # noqa: E402

# Her shape: 408 designed patches on a 420-square sheet, 20 strips of 21.
DESIGNED, STEPS, STRIPS = 408, 21, 20
SHEET = STEPS * STRIPS

_CHART_FIELDS = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"


def _locs() -> "list[str]":
    """The chart's own labels: strip letter + position in the pass."""
    return [f"{chr(ord('A') + s)}{p + 1}"
            for s in range(STRIPS) for p in range(STEPS)]


def _shuffled_locs() -> "list[str]":
    """The sheet locations in the order the .ti2 hands them out, which is not
    the order the labels run in: the engine shuffles which patch lands where."""
    locs = _locs()
    return locs[7:] + locs[:7]


@pytest.fixture
def chart(tmp_path: Path) -> Path:
    """A ChromIQ-layout-engine `.ti2` of her shape, with its `.ti1` beside it.

    Each patch gets a device value derived from its row, so a wrong pairing is
    visible rather than a coincidence.
    """
    ti2 = tmp_path / "verify.ti2"
    slots = _shuffled_locs()
    rows = []
    for i in range(DESIGNED):
        v = (i % 101)
        rows.append(f'{i + 1} "{slots[i]}" {v}.0 {(v * 2) % 101}.0 '
                    f'{(v * 3) % 101}.0 40.0 42.0 44.0')
    for k in range(SHEET - DESIGNED):          # the fill-up: copies of media
        rows.append(f'{DESIGNED + k + 1} "{slots[DESIGNED + k]}" '
                    '100.0 100.0 100.0 95.0 100.0 108.0')
    ti2.write_text(
        'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ layout engine"\n'
        f'COLOR_REP "iRGB"\nSTEPS_IN_PASS "{STEPS}"\n\n'
        f"NUMBER_OF_FIELDS {len(_CHART_FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{_CHART_FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    d = [f"{i + 1} 0.0 0.0 0.0" for i in range(DESIGNED)]
    (tmp_path / "verify.ti1").write_text(
        'CTI1\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n'
        f"NUMBER_OF_SETS {DESIGNED}\nBEGIN_DATA\n" + "\n".join(d)
        + "\nEND_DATA\n", encoding="utf-8")
    return ti2


def _measurement(path: Path, locs: "list[str]") -> Path:
    """What `txt2ti3` + `spec2cie` make of an i1Profiler measure-tool export:
    SAMPLE_ID 1..N in READING order, SAMPLE_LOC the patch name, XYZ, and not
    one device column."""
    fields = "SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z"
    rows = [f'{i + 1} "{loc}" {30 + i % 40}.0 {31 + i % 40}.0 {32 + i % 40}.0'
            for i, loc in enumerate(locs)]
    path.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "Argyll target"\n'
        'DEVICE_CLASS "OUTPUT"\n\n'
        f"NUMBER_OF_FIELDS {len(fields.split())}\n"
        f"BEGIN_DATA_FORMAT\n{fields}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


def _reading_order() -> "list[str]":
    """How i1Profiler's grid hands them back: across the strips, not down one.
    A1, B1, C1 … T1, A2 … — which is what her own file holds."""
    return [f"{chr(ord('A') + s)}{p + 1}"
            for p in range(STEPS) for s in range(STRIPS)]


# --- 1. the file is READABLE at all ---------------------------------------
def test_a_measurement_with_no_device_columns_parses(tmp_path):
    """It was refused by `parse_ti3` before anything else could look at it."""
    m = _measurement(tmp_path / "m.ti3", _reading_order())
    d = parse_ti3(m)
    assert d.n_patches == SHEET
    assert d.has_device is False
    assert len(d.rgb) == 0, "an absent device column must be EMPTY, not zeros"


def test_a_non_rgb_device_measurement_is_still_refused(tmp_path):
    """No device columns is not the same thing as the WRONG device columns.
    A CMYK measurement still cannot be used, and must still say so."""
    fields = "SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z"
    p = tmp_path / "cmyk.ti3"
    p.write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        f"{fields}\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
        "1 0 0 0 0 90 95 100\n2 100 0 0 0 20 30 60\nEND_DATA\n",
        encoding="utf-8")
    with pytest.raises(Ti3ParseError, match="only RGB charts"):
        parse_ti3(p)


# --- 2. the counting rule, in both directions -----------------------------
def test_the_design_and_the_sheet_are_different_numbers(chart):
    assert expected_patches(chart) == DESIGNED
    assert sheet_patches(chart) == SHEET
    assert DESIGNED != SHEET, "the fixture must reproduce her padded chart"


def test_a_measurement_of_the_whole_sheet_is_complete_not_foreign(tmp_path,
                                                                  chart):
    """Her case. 420 readings of a 408-patch design printed as 420 squares."""
    m = _measurement(tmp_path / "m.ti3", _reading_order())
    v = assess(m, chart)
    assert v.ok, v.reason
    assert not v.partial
    assert v.device_from_chart
    assert classify(m, chart).state.value == "complete"


def test_a_short_measurement_is_still_called_short(tmp_path, chart):
    m = _measurement(tmp_path / "m.ti3", _reading_order()[:300])
    v = assess(m, chart)
    assert v.ok and v.partial, v.reason
    assert (v.n_chart, v.n_measured) == (DESIGNED, 300)


def test_more_readings_than_the_sheet_carries_is_a_different_chart(tmp_path,
                                                                   chart):
    locs = _reading_order() + ["A1"]
    m = _measurement(tmp_path / "m.ti3", locs)
    v = assess(m, chart)
    assert not v.ok
    assert "different chart" in v.reason
    assert str(SHEET) in v.reason, v.reason


# --- 3. the wrong chart is STILL refused ----------------------------------
def test_a_measurement_of_another_chart_is_refused(tmp_path, chart):
    """The same size, the same shape, names this chart does not have."""
    m = _measurement(tmp_path / "m.ti3",
                     ["Z" + loc for loc in _reading_order()])
    v = assess(m, chart)
    assert not v.ok, "a measurement of a different chart must be refused"
    assert "different chart" in v.reason
    assert not v.device_from_chart


def test_one_patch_measured_twice_is_refused(tmp_path, chart):
    locs = _reading_order()
    locs[5] = locs[0]
    m = _measurement(tmp_path / "m.ti3", locs)
    v = assess(m, chart)
    assert not v.ok
    assert "twice" in v.reason, v.reason


def test_a_file_with_no_names_at_all_is_refused(tmp_path, chart):
    fields = "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z"
    p = tmp_path / "nameless.ti3"
    rows = [f"{i + 1} 30.0 31.0 32.0" for i in range(SHEET)]
    p.write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        f"{fields}\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS {SHEET}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    v = assess(p, chart)
    assert not v.ok
    assert "no patch names" in v.reason or "nothing in it" in v.reason, v.reason


# --- 4. the device values come from the chart, in the CHART's order -------
def test_the_chart_supplies_the_device_values_and_its_own_order(tmp_path,
                                                                chart):
    m = _measurement(tmp_path / "m.ti3", _reading_order())
    assert complete_from_chart(m, chart) == SHEET
    design = parse_ti3(chart)
    got = parse_ti3(m)
    assert got.has_device
    assert got.sample_locs == design.sample_locs, \
        "the filed measurement must be in the chart's own row order"
    assert got.sample_ids == design.sample_ids
    assert (got.rgb == design.rgb).all(), \
        "every patch must carry the device value the chart printed there"
    assert device_came_from_chart(m) == chart.name


def test_the_reading_follows_its_name_and_not_its_row(tmp_path, chart):
    """The point of the whole exercise: reading number 1 in the file is patch
    A1 of the sheet, which is NOT row 1 of the chart."""
    locs = _reading_order()
    m = _measurement(tmp_path / "m.ti3", locs)
    before = parse_ti3(m)
    xyz_of = {loc: tuple(before.xyz[i]) for i, loc in enumerate(locs)}
    complete_from_chart(m, chart)
    after = parse_ti3(m)
    for i, loc in enumerate(after.sample_locs):
        assert tuple(after.xyz[i]) == xyz_of[loc], \
            f"{loc} did not keep its own reading"


def test_it_refuses_to_touch_a_file_that_already_has_device_values(tmp_path,
                                                                   chart):
    """Nothing here may rewrite an ordinary measurement."""
    fields = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"
    p = tmp_path / "native.ti3"
    body = 'CTI3\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n' \
        f'{fields}\nEND_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n' \
        '1 "A1" 1.0 2.0 3.0 40.0 41.0 42.0\nEND_DATA\n'
    p.write_text(body, encoding="utf-8")
    assert attach_device_values_from_chart(p, chart) == 0
    assert p.read_text(encoding="utf-8") == body


# --- 5. a partial keeps only the patches that were read -------------------
def test_a_partial_keeps_its_own_patches(tmp_path, chart):
    locs = _reading_order()[:100]
    m = _measurement(tmp_path / "m.ti3", locs)
    assert complete_from_chart(m, chart) == 100
    got = parse_ti3(m)
    assert got.n_patches == 100
    assert set(got.sample_locs) == set(locs)


# --- 6. the name check runs BEFORE the device values are written ----------
def test_the_identity_check_cannot_validate_its_own_repair(tmp_path, chart):
    """Once the chart's device values are in the file, `verify_patch_identity`
    compares them with themselves and answers "verified" whatever happened.
    That is exactly the self-validating trap §I rejected, so the check that
    decides has to be the NAME check, and it has to run first."""
    from workflow.measurement_report import verify_patch_identity
    m = _measurement(tmp_path / "m.ti3", _reading_order())
    assert match_by_name(m, chart).ok
    complete_from_chart(m, chart)
    after = verify_patch_identity(parse_ti3(m), chart)
    assert after["verdict"] == "verified" and after["worst"] == 0.0, \
        "if this ever fails, the trap this test names has changed shape"


# --- 6b. …and with NO chart there is nothing to complete it from ----------
def test_a_device_less_measurement_with_no_chart_beside_it_is_refused(tmp_path):
    """The door that has no chart is the one that was left open.

    `parse_ti3` used to refuse a file with no device columns outright, so BOTH
    profile-build doors refused this. Teaching the parser to read it opened
    every door at once, and only the doors that HAVE a chart were given the
    completion step: `ui.measurement_filing.say_what_was_filed` returns before
    it when `chart_the_copy_will_be_judged_against` is None. A spectral-only
    export dropped on "New project from a measurement" was therefore copied in,
    announced as filed, and left with no device values for ever, because the
    completion only ever runs at import. `colprof` cannot build from such a
    file and the report can compute no grey ramp in it.

    MUTATION: put `and chart_ti2 is not None` back on the `has_device` test in
    `assess` and this goes red, because the file comes back ok.
    """
    m = _measurement(tmp_path / "loose.ti3", ["A1", "A2", "A3"])
    v = assess(m, None)
    assert not v.ok, (
        "a measurement with no device values and no chart to supply them was "
        "accepted; nothing downstream can ever give it any")
    assert not v.device_from_chart
    assert "no device values" in v.reason and "no chart file" in v.reason


def test_a_device_less_measurement_with_a_chart_is_still_taken(tmp_path, chart):
    """The refusal above may not close the door round 4 opened."""
    m = _measurement(tmp_path / "m.ti3", _reading_order())
    v = assess(m, chart)
    assert v.ok and v.device_from_chart, v.reason


# --- 7. ONE RULE, and the Measure tab's door reaches it -------------------
def test_the_verification_door_judges_through_the_shared_rule():
    """The tab had its own copy of the count-and-identity rule, and the copy
    drifted twice in two days: the profile-build door learned to read a
    spectral-only export and this one still refused it the next morning.
    Neither door may carry a second implementation."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._import_verdict)
    assert "measurement_import import assess" in src, src
    reason = inspect.getsource(TabMeasure._import_mismatch_reason)
    assert "_import_verdict" in reason
    for gone in ("verify_patch_identity", "parse_ti3", "Ti3ParseError"):
        assert gone not in reason, \
            f"{gone} is a second copy of the shared rule in the tab"


def test_the_device_values_are_attached_before_the_copy_is_filed():
    """Order, not presence. A file copied into the run before the chart has
    supplied its device values is paired by the measuring tool's reading order
    and every number in the report is then about the wrong patch."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_import_measurement)
    assert "complete_from_chart" in src, \
        "the verification door never asks the chart for the device values"
    assert src.index("complete_from_chart") < src.index("shutil.copy2"), \
        "the copy is filed before the chart supplies the device values"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _verification_tab(tmp_path, chart_ti2: Path):
    """A real TabMeasure pointed at a real verification run of a real project,
    whose verification chart is the padded one above."""
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager, Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    run.built_profile_icc().write_bytes(b"not a real profile, only its name")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text(chart_ti2.read_text(encoding="utf-8"),
                                    encoding="utf-8")
    run.verify_chart_ti1.write_text(
        chart_ti2.with_suffix(".ti1").read_text(encoding="utf-8"),
        encoding="utf-8")
    fm = FileManager(s)
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    ctl.set_profile_run(run.id)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return tab, ctl, run


def test_the_verification_door_files_her_file_and_says_where_from(
        qapp, tmp_path, chart, monkeypatch):
    """The whole act, through the tab's own handler: a device-less measurement
    of the whole printed sheet is filed, with the chart's device values in it
    and in the chart's own order, and the person was asked first."""
    import ui.tabs.tab_measure as mod

    m = _measurement(tmp_path / "i1measurement.ti3", _reading_order())
    tab, ctl, run = _verification_tab(tmp_path, chart)
    asked: list = []
    monkeypatch.setattr(mod.TabMeasure, "_ask_import_question",
                        lambda self, msg, label, **kw: (
                            asked.append((msg.id, kw)) or True))
    monkeypatch.setattr(mod.TabMeasure, "_show_import_done",
                        lambda self, v, d: None)
    monkeypatch.setattr(mod.TabMeasure, "_ask_how_printed", lambda self, d: None)
    refused: list = []
    monkeypatch.setattr(mod.TabMeasure, "_show_import_refusal",
                        lambda self, msg, **kw: refused.append(kw.get("reason", "")))
    tab._import_path = m
    tab._on_import_measurement()

    assert not refused, refused
    assert asked and asked[0][0] == "M-IMPORT-DEVICE-FROM-CHART", asked
    assert asked[0][1]["count"] == SHEET
    vid = ctl.target.verification_id
    filed = run.verification(vid).measurement_ti3
    assert filed.is_file(), "nothing was filed"
    design, got = parse_ti3(chart), parse_ti3(filed)
    assert got.has_device and got.sample_locs == design.sample_locs
    assert device_came_from_chart(filed) == run.verify_chart_ti2.name


def test_the_verification_door_files_nothing_when_the_person_cancels(
        qapp, tmp_path, chart, monkeypatch):
    import ui.tabs.tab_measure as mod

    m = _measurement(tmp_path / "i1measurement.ti3", _reading_order())
    tab, ctl, run = _verification_tab(tmp_path, chart)
    monkeypatch.setattr(mod.TabMeasure, "_ask_import_question",
                        lambda self, msg, label, **kw: False)
    monkeypatch.setattr(mod.TabMeasure, "_show_import_done",
                        lambda self, v, d: None)
    monkeypatch.setattr(mod.TabMeasure, "_ask_how_printed", lambda self, d: None)
    tab._import_path = m
    tab._on_import_measurement()
    assert not list(run.verifications_dir.glob("*/*.ti3")), \
        "Cancel must leave nothing behind"
    assert not parse_ti3(m).has_device, "the user's own file was rewritten"


def test_the_verification_door_still_refuses_another_chart(
        qapp, tmp_path, chart, monkeypatch):
    import ui.tabs.tab_measure as mod

    m = _measurement(tmp_path / "other.ti3",
                     ["Z" + loc for loc in _reading_order()])
    tab, ctl, run = _verification_tab(tmp_path, chart)
    refused: list = []
    monkeypatch.setattr(mod.TabMeasure, "_show_import_refusal",
                        lambda self, msg, **kw: refused.append(kw.get("reason", "")))
    monkeypatch.setattr(mod.TabMeasure, "_ask_import_question",
                        lambda self, msg, label, **kw: True)
    monkeypatch.setattr(mod.TabMeasure, "_show_import_done",
                        lambda self, v, d: None)
    monkeypatch.setattr(mod.TabMeasure, "_ask_how_printed", lambda self, d: None)
    tab._import_path = m
    tab._on_import_measurement()
    assert refused and "different chart" in refused[0], refused
    assert not list(run.verifications_dir.glob("*/*.ti3"))


def test_the_asking_window_comes_from_the_catalogue():
    """New user-facing text goes through §M, and this window is no exception."""
    from workflow import measurement_messages as M
    msg = M.CATALOGUE["M-IMPORT-DEVICE-FROM-CHART"]
    assert msg.approved is False, "it has not been reviewed yet"
    title, body = msg.render(count=420, chart="verify.ti2")
    assert "{" not in body and "{" not in title
    one_title, one_body = msg.render(count=1, chart="verify.ti2")
    assert "All 420 readings" in body and "Its one reading" in one_body
