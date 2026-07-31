"""#130 (Knut, 2026-07-29, testing beta.100/101): the two bar actions become
their icons, and nothing about how they behave may change.

*"The icons for 'Restore Used Chart' and 'Delete' buttons are implemented wrong.
The icons REPLACE the previous buttons totally, similar to the 'load profile'
icon in Create Chart tab or 'load ti2' icon in Print Chart tabs… so that clicking
the icon functions as a button. The info icons shall still be kept as is. The new
icons should have the same hight as the height of the previous buttons (now
removed)… Make a large table to compare all functions, actions, dependabilites
and combinations of options that control the visibility and function of the
old… buttons and compare with the implementation of the new icon-style buttons to
verify that all functionality is covered and verified as existing using tests."*

This module IS that table. :data:`TABLE` lists every situation that controls the
two buttons — where the bar is shown, whether a measurement is running, the run
type, which profile run and which verification date is picked, whether a stored
chart exists, whether it is stale, and how many runs and verification dates the
project has — and for each one states what BOTH buttons must do. Every row is
then played out on a real bar over a real project on disk, and the row is checked
against the live widgets.

The old text buttons and the new icon buttons are the SAME widgets in the same
places with the same signals; only their appearance changed. So a table that
passes here passes for both, and the structural tests at the end pin down what
actually did change: no label on the face, the mark alone, the old height, the ⓘ
untouched, and the name moved into the tooltip because the face can no longer
carry it.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                            # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton, QToolButton  # noqa: E402

import core.run_delete as rd                                  # noqa: E402
from core.file_manager import FileManager, Project            # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,      # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                         # noqa: E402
from ui.bar_icons import BarIconButton                        # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,  # noqa: E402
                                       MeasurementTargetController)
from workflow.chart_slot import slot_for                       # noqa: E402
from workflow.verify_chart_snapshot import (snapshot_chart,     # noqa: E402
                                            snapshot_slot)


def _live_differs(target) -> None:
    """Edit the live chart so that restoring it would actually change something.

    #130 (Knut, 2026-07-30): "Restore Used Chart" is greyed out when the loaded
    chart is already byte-identical to the stored one — pressing it then copies
    the files over themselves, which is why it looked like a button that does
    nothing. A snapshot taken on the previous line is identical by definition,
    so these tests now state the case they are really about: a stored chart that
    differs from what is loaded.
    """
    from workflow.chart_slot import slot_for
    for f in slot_for(target).files_to_copy():
        f.write_text(f.read_text() + "  # edited since the snapshot")
        return


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------------
# The world each row is played out in
# ---------------------------------------------------------------------------

def _project(tmp_path, *, runs=1, dated=(), snapshot_dates=(),
             profiling_snapshot=False, stale=False, verify_chart=False):
    """A project on disk with exactly the ingredients a row asks for."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    for _ in range(runs - 1):
        proj.new_run().ensure_dir()
    run.chart_ti1.write_text("TI1")
    run.chart_ti2.write_text("TI2")
    if profiling_snapshot:
        snapshot_slot(slot_for(run)); _live_differs(run)
        if stale:
            meta = run.load_meta()
            meta.chart_snapshot_stale = True
            run.save_meta(meta)
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    if verify_chart or dated:
        run.verify_chart_ti1.write_text("TI1")
        run.verify_chart_ti2.write_text("TI2")
        (run.verifications_dir / f"{run.verify_stem}.channels.json").write_text("{}")
    for vid in dated:
        v = run.verification(vid)
        v.ensure_dir()
        if vid in snapshot_dates:
            snapshot_chart(v); _live_differs(v)
    fm.set_target_name("P")
    return fm, proj, run


def _bar(fm, *, show_verification=True):
    ctl = MeasurementTargetController(fm)
    bar = MeasurementTargetBar(ctl, show_verification=show_verification)
    return ctl, bar


# ---------------------------------------------------------------------------
# THE TABLE
# ---------------------------------------------------------------------------
# Each row:
#   id            – the situation, in words
#   world         – kwargs for _project()
#   show_verif    – is the bar one of the three that carry these actions?
#   locked        – is the bar on Build Profile / Check & Refine?
#   measuring     – is a measurement running?
#   run_type      – profiling | verification
#   run           – the profile run selected ("" = New run)
#   date          – the verification date selected ("" = New verification)
#   restore       – (visible, enabled, a phrase the tooltip must contain)
#   delete        – (visible, enabled, a phrase the tooltip must contain)
#
# "" as the phrase means "do not care about the wording, only the state".

TABLE = [
    # --- where the bar is at all ------------------------------------------
    dict(id="bar without the verification block (Build Profile side)",
         world={}, show_verif=False, locked=False, measuring=False,
         run_type=RUN_TYPE_PROFILING, run="run1", date="",
         restore=(False, None, ""), delete=(False, None, "")),

    # --- the measurement lock --------------------------------------------
    dict(id="a measurement is running (profiling, everything else fine)",
         world=dict(profiling_snapshot=True), show_verif=True, locked=False,
         measuring=True, run_type=RUN_TYPE_PROFILING, run="run1", date="",
         restore=(True, False, "Not while a measurement is running"),
         delete=(True, False, "Not while a measurement is running")),

    # --- the tab lock (bar shown read-only) ------------------------------
    dict(id="bar locked on a tab that does not use the selection",
         world=dict(profiling_snapshot=True), show_verif=True, locked=True,
         measuring=False, run_type=RUN_TYPE_PROFILING, run="run1", date="",
         restore=(True, False, "not used on the Build Profile"),
         delete=(True, False, "not used on the Build Profile")),

    # --- Run type = Profiling --------------------------------------------
    dict(id="profiling, New run selected",
         world={}, show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_PROFILING, run="", date="",
         restore=(True, False, "Create the chart for this run first"),
         delete=(True, False, "Select an existing profile run to delete")),

    dict(id="profiling, run with no stored chart yet",
         world={}, show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_PROFILING, run="run1", date="",
         restore=(True, False, "has no stored chart yet"),
         delete=(True, True, "Empty this run, or delete the whole project")),

    dict(id="profiling, run with a stored chart",
         world=dict(profiling_snapshot=True), show_verif=True, locked=False,
         measuring=False, run_type=RUN_TYPE_PROFILING, run="run1", date="",
         restore=(True, True, "Restore the chart this profile run was measured"),
         delete=(True, True, "Empty this run, or delete the whole project")),

    dict(id="profiling, stored chart deliberately left alone (stale)",
         world=dict(profiling_snapshot=True, stale=True), show_verif=True,
         locked=False, measuring=False, run_type=RUN_TYPE_PROFILING,
         run="run1", date="",
         restore=(True, True, "it is from an earlier measurement"),
         delete=(True, True, "")),

    dict(id="profiling, several runs — a run can go on its own",
         world=dict(runs=3, profiling_snapshot=True), show_verif=True,
         locked=False, measuring=False, run_type=RUN_TYPE_PROFILING,
         run="run2", date="",
         restore=(True, False, "has no stored chart yet"),
         delete=(True, True, "Delete profile run 2 and everything in it")),

    # --- Run type = Verification -----------------------------------------
    dict(id="verification, New verification selected, no dates exist",
         world=dict(verify_chart=True), show_verif=True, locked=False,
         measuring=False, run_type=RUN_TYPE_VERIFICATION, run="run1", date="",
         restore=(True, False, "Select an existing Verification run date"),
         delete=(True, True, "whole verification folder")),

    dict(id="verification, a date with no stored chart",
         world=dict(dated=("2026-07-25_120000",)), show_verif=True,
         locked=False, measuring=False, run_type=RUN_TYPE_VERIFICATION,
         run="run1", date="2026-07-25_120000",
         restore=(True, False, "no available chart to restore"),
         delete=(True, True, "whole verification folder")),

    dict(id="verification, a date with a stored chart",
         world=dict(dated=("2026-07-25_120000",),
                    snapshot_dates=("2026-07-25_120000",)),
         show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_VERIFICATION, run="run1",
         date="2026-07-25_120000",
         restore=(True, True, "Restore chart used for selected verification"),
         delete=(True, True, "whole verification folder")),

    dict(id="verification, two dates and one picked — only that date goes",
         world=dict(dated=("2026-07-25_120000", "2026-07-26_120000"),
                    snapshot_dates=("2026-07-26_120000",)),
         show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_VERIFICATION, run="run1",
         date="2026-07-26_120000",
         restore=(True, True, "Restore chart used for selected verification"),
         delete=(True, True, "Delete only this verification date")),

    dict(id="verification, New verification with two dates present",
         world=dict(dated=("2026-07-25_120000", "2026-07-26_120000")),
         show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_VERIFICATION, run="run1", date="",
         restore=(True, False, "Select an existing Verification run date"),
         delete=(True, True, "and all 2 results")),

    dict(id="verification, New run selected",
         world={}, show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_VERIFICATION, run="", date="",
         restore=(True, False, "Select an existing Verification run date"),
         delete=(True, False, "Select an existing profile run to delete")),

    dict(id="verification, a run that has no verification files at all",
         world=dict(runs=2), show_verif=True, locked=False, measuring=False,
         run_type=RUN_TYPE_VERIFICATION, run="run2", date="",
         restore=(True, False, "Select an existing Verification run date"),
         delete=(True, False, "no verification files to delete")),
]


def _play(qapp, tmp_path, row):
    fm, proj, run = _project(tmp_path, **row["world"])
    ctl, bar = _bar(fm, show_verification=row["show_verif"])
    ctl.set_profile_run(row["run"])
    ctl.set_run_type(row["run_type"])
    ctl.set_verification_id(row["date"])
    ctl.set_measuring(row["measuring"])
    bar.set_locked(row["locked"])
    bar.refresh()
    return bar


@pytest.mark.parametrize("row", TABLE, ids=[r["id"] for r in TABLE])
@pytest.mark.parametrize("which", ["restore", "delete"])
def test_the_table_holds_for_the_icon_buttons(qapp, tmp_path, row, which):
    """Every row of the table, on the real bar, for both buttons."""
    bar = _play(qapp, tmp_path, row)
    btn = bar._restore_btn if which == "restore" else bar._delete_btn
    want_visible, want_enabled, phrase = row[which]

    # isVisibleTo, not isVisible: the bar itself is never shown in a test, and
    # isVisible() would then be False for everything and prove nothing.
    assert btn.isVisibleTo(bar) is want_visible, (
        f"{which}: expected visible={want_visible} in “{row['id']}”")
    if not want_visible:
        return
    assert btn.isEnabled() is want_enabled, (
        f"{which}: expected enabled={want_enabled} in “{row['id']}” "
        f"(tooltip: {btn.toolTip()!r})")
    if phrase:
        assert phrase in btn.toolTip(), (
            f"{which}: “{phrase}” missing from the tooltip in “{row['id']}”: "
            f"{btn.toolTip()!r}")


@pytest.mark.parametrize("row", TABLE, ids=[r["id"] for r in TABLE])
def test_the_info_buttons_follow_their_action(qapp, tmp_path, row):
    """Knut: *"The info icons shall still be kept as is."* Each ⓘ appears and
    disappears with its action, and is never greyed with it — the explanation has
    to stay readable precisely when the action cannot be used."""
    bar = _play(qapp, tmp_path, row)
    for btn, tip in ((bar._restore_btn, bar._restore_tip),
                     (bar._delete_btn, bar._delete_tip)):
        assert tip.isVisibleTo(bar) is btn.isVisibleTo(bar)
        if tip.isVisibleTo(bar):
            assert tip.isEnabled(), "an ⓘ was greyed with its action"


@pytest.mark.parametrize("row", TABLE, ids=[r["id"] for r in TABLE])
def test_the_tooltip_always_names_the_action(qapp, tmp_path, row):
    """With no label on the face, the tooltip is the only place the name can
    come from — in every state, enabled or greyed."""
    bar = _play(qapp, tmp_path, row)
    for btn in (bar._restore_btn, bar._delete_btn):
        if btn.isVisibleTo(bar):
            assert btn.toolTip().startswith(btn.text()), (
                f"{btn.text()!r} is not named by its own tooltip: "
                f"{btn.toolTip()[:60]!r}")


# ---------------------------------------------------------------------------
# What actually changed: the face
# ---------------------------------------------------------------------------

def test_both_are_icon_only_buttons_now(qapp, tmp_path):
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    for btn in (bar._restore_btn, bar._delete_btn):
        assert isinstance(btn, BarIconButton)
        assert isinstance(btn, QToolButton) and not isinstance(btn, QPushButton)
        assert not btn.icon().isNull(), "the mark is missing"


def test_the_label_is_not_painted_but_is_still_the_name(qapp, tmp_path):
    """Knut asked for the whole button to be replaced by the mark. The text stays
    on the widget so the button still HAS a name — for the tooltip, for assistive
    technology, and for anything that asks what it is — but it is never drawn."""
    from PyQt6.QtCore import Qt
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    for btn, name in ((bar._restore_btn, "Restore Used Chart"),
                      (bar._delete_btn, "Delete")):
        assert btn.text() == name
        assert btn.accessibleName() == name
        assert btn.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly


def test_they_are_clearly_bigger_than_the_info_icons(qapp, tmp_path):
    """Knut asked first for the height the text buttons had (26 px), then — on
    seeing it — for the MARK to grow by about half, *"even if that makes them a
    little taller than the input boxes"*, and to be *"clearly bigger and more
    prominent than the info icons"*. So the square follows the mark now, not the
    row."""
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    for btn, tip in ((bar._restore_btn, bar._restore_tip),
                     (bar._delete_btn, bar._delete_tip)):
        assert btn.height() == BarIconButton.HEIGHT == 34
        assert btn.width() == 34, "a square hit target, not a slot"
        assert btn.height() > tip.height(), "no bigger than the ⓘ beside it"
        assert btn.iconSize().height() >= tip.height() * 1.2, (
            "the mark is not clearly more prominent than the ⓘ: "
            f"{btn.iconSize().height()} px of mark vs a {tip.height()} px ⓘ")


def test_nothing_widens_them_for_a_label_they_no_longer_show(qapp, tmp_path):
    """The width fitter used to size these two for their text. A refresh must not
    put that back, or the app would reserve room for an invisible label."""
    fm, _proj, _run = _project(tmp_path)
    ctl, bar = _bar(fm)
    for _ in range(3):
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
        bar.refresh()
        ctl.set_run_type(RUN_TYPE_PROFILING)
        bar.refresh()
    for btn in (bar._restore_btn, bar._delete_btn):
        assert btn.width() == BarIconButton.HEIGHT

    src = inspect.getsource(MeasurementTargetBar._fit_widths)
    assert "_restore_btn" not in src and "_delete_btn" not in src, \
        "the width fitter is sizing an icon-only button again"


def test_they_never_take_keyboard_focus(qapp, tmp_path):
    """One of them deletes a project. The space bar must not reach it because a
    tab handed it the initial focus — the same rule the load icons follow."""
    from PyQt6.QtCore import Qt
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    for btn in (bar._restore_btn, bar._delete_btn):
        assert btn.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_the_greyed_mark_is_drawn_grey_rather_than_left_coloured(qapp, tmp_path):
    """A coloured pixmap is not convincingly dimmed by Qt's own disabled
    rendering, so the disabled look is drawn explicitly — otherwise "greyed" is
    just "slightly paler magenta", which reads as available."""
    from PyQt6.QtGui import QIcon
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    for btn in (bar._restore_btn, bar._delete_btn):
        normal = btn.icon().pixmap(BarIconButton.ICON, BarIconButton.ICON, QIcon.Mode.Normal).toImage()
        off = btn.icon().pixmap(BarIconButton.ICON, BarIconButton.ICON, QIcon.Mode.Disabled).toImage()
        assert normal != off, "the disabled mark is the coloured one"
        # …and the grey really is grey: no channel stands out.
        greys = []
        for y in range(off.height()):
            for x in range(off.width()):
                c = off.pixelColor(x, y)
                if c.alpha() > 200:
                    greys.append(max(c.red(), c.green(), c.blue())
                                 - min(c.red(), c.green(), c.blue()))
        assert greys, "the disabled mark paints nothing"
        assert max(greys) < 30, "the disabled mark still carries a hue"


def test_the_greyed_mark_is_never_more_prominent_than_a_live_one(qapp, tmp_path):
    """The first attempt used ``palette(Disabled, ButtonText)``, which this app's
    dark theme leaves at near-white — so on the dark bar the greyed mark came out
    BRIGHTER than the enabled mark beside it. Caught by rendering the bar in both
    themes and looking at it, which is the only way this kind of fault shows up.
    """
    from PyQt6.QtGui import QColor, QPalette
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    btn = bar._delete_btn
    for text, name in (("#e6e6e6", "dark theme"), ("#22211f", "light theme")):
        pal = btn.palette()
        pal.setColor(QPalette.ColorRole.WindowText, QColor(text))
        btn.setPalette(pal)
        grey = QColor(btn._disabled_colour())
        bg_is_dark = QColor(text).lightness() > 127
        page = QColor("#181818") if bg_is_dark else QColor("#f4f2ee")
        # The greyed mark sits between the page and the text colour — never
        # further from the page than the text it would replace.
        assert abs(grey.lightness() - page.lightness()) \
               < abs(QColor(text).lightness() - page.lightness()), \
               f"the greyed mark is as loud as live text on the {name}"


def test_the_greys_are_the_ones_the_app_already_uses(qapp):
    """So a greyed mark greys exactly like a greyed label, and a later theme
    tweak cannot leave the two disagreeing."""
    from ui.light_styles import LM_TEXT_FAINT
    from ui.styles import APP_STYLESHEET
    assert BarIconButton.GREY_ON_LIGHT == LM_TEXT_FAINT
    assert f"color: {BarIconButton.GREY_ON_DARK};" in APP_STYLESHEET, \
        "the dark theme no longer greys buttons with this colour"


def test_the_grey_follows_a_theme_switch(qapp, tmp_path):
    """A grey that is right on the dark theme is nearly invisible on the light
    one, so the disabled mark has to be re-derived when the theme changes under
    it — not baked in once at construction.

    Driven by re-palettting the button rather than by calling
    ``apply_appearance``: that sets the app-wide stylesheet, which stays set for
    every test that runs afterwards. Mine did, and a message-box width test 400
    files later started measuring buttons in a font the app had not chosen.
    """
    from PyQt6.QtGui import QColor, QIcon, QPalette
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    btn = bar._delete_btn

    def greyed_mark_under(text_colour: str):
        pal = btn.palette()
        pal.setColor(QPalette.ColorRole.WindowText, QColor(text_colour))
        btn.setPalette(pal)          # Qt delivers PaletteChange from here
        qapp.processEvents()
        return btn.icon().pixmap(BarIconButton.ICON, BarIconButton.ICON, QIcon.Mode.Disabled).toImage()

    light = greyed_mark_under("#22211f")     # dark text ⇒ light theme
    dark = greyed_mark_under("#e6e6e6")     # light text ⇒ dark theme
    assert light != dark, "the greyed mark ignored the theme switch"


def test_the_pointer_promises_only_what_will_happen(qapp, tmp_path):
    from PyQt6.QtCore import Qt
    fm, _proj, _run = _project(tmp_path, profiling_snapshot=True)
    ctl, bar = _bar(fm)
    ctl.set_profile_run("run1")
    bar.refresh()
    assert bar._restore_btn.isEnabled()
    assert bar._restore_btn.cursor().shape() == Qt.CursorShape.PointingHandCursor

    ctl.set_measuring(True)
    bar.refresh()
    assert not bar._restore_btn.isEnabled()
    assert bar._restore_btn.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_both_marks_follow_the_active_tab(qapp, tmp_path):
    """Everything on this bar takes the accent of the tab you are looking at, and
    now that the marks ARE the buttons that matters more, not less."""
    from PyQt6.QtGui import QIcon
    fm, _proj, _run = _project(tmp_path)
    _ctl, bar = _bar(fm)
    before = [btn.icon().pixmap(BarIconButton.ICON, BarIconButton.ICON, QIcon.Mode.Normal).toImage()
              for btn in (bar._restore_btn, bar._delete_btn)]
    bar.set_accent("#37bcd6")
    after = [btn.icon().pixmap(BarIconButton.ICON, BarIconButton.ICON, QIcon.Mode.Normal).toImage()
             for btn in (bar._restore_btn, bar._delete_btn)]
    for a, b in zip(before, after):
        assert a != b, "a mark ignored the tab's accent colour"


# ---------------------------------------------------------------------------
# The actions themselves are untouched
# ---------------------------------------------------------------------------

def test_clicking_the_mark_runs_the_same_handler_as_the_button_did(qapp, tmp_path):
    fm, _proj, _run = _project(tmp_path, profiling_snapshot=True)
    ctl, bar = _bar(fm)
    ctl.set_profile_run("run1")
    bar.refresh()
    calls = []
    bar._on_restore_clicked = lambda: calls.append("restore")   # type: ignore
    bar._on_delete_clicked = lambda: calls.append("delete")     # type: ignore
    # Re-wire, because the handlers were connected in __init__.
    bar._restore_btn.clicked.disconnect()
    bar._delete_btn.clicked.disconnect()
    bar._restore_btn.clicked.connect(bar._on_restore_clicked)
    bar._delete_btn.clicked.connect(bar._on_delete_clicked)
    bar._restore_btn.click()
    bar._delete_btn.click()
    assert calls == ["restore", "delete"]


def test_a_greyed_mark_cannot_be_clicked(qapp, tmp_path):
    """Qt swallows clicks on a disabled widget, and the reasons in the table rely
    on that — the trash can must be unusable, not merely discouraging."""
    fm, _proj, _run = _project(tmp_path)
    ctl, bar = _bar(fm)
    ctl.set_profile_run("")            # New run → nothing to delete
    bar.refresh()
    fired = []
    bar._delete_btn.clicked.connect(lambda: fired.append(1))
    assert not bar._delete_btn.isEnabled()
    bar._delete_btn.click()
    assert fired == [], "a greyed trash can still fired"


def test_every_block_reason_still_has_its_own_words(qapp):
    """The table above covers the reasons reachable from the bar; these are all
    of them, and each must still say why AND what would help."""
    for code in (rd.BLOCK_MEASURING, rd.BLOCK_NO_PROJECT, rd.BLOCK_NEW_RUN,
                 rd.BLOCK_UNKNOWN_RUN, rd.BLOCK_NO_VERIFICATIONS,
                 rd.BLOCK_UNKNOWN_VERIFICATION):
        text = rd.block_tooltip(code)
        assert len(text) > 60, f"{code} has no explanation"
        assert "(s)" not in text
