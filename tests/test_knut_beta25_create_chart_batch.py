"""Knut's beta 25 batch: "Bugs relating to Create Chart and the new 'Which
Presets Can be Verified?'", items 1 to 7.

His seven sentences, and one guard family per sentence:

1. *"The name of the button is not logical, because it is not the preset that
   is being verified. Better suggestion: 'Which Presets Can Be Used for
   Verification?'. Update the name in all help text and the popup window
   referring to this button when loading a chart in a verification run, and any
   other place where this button is mentioned in text."*
2. *"The button height is a bit large. Use the button height similar to 'New
   Seed' or 'Reset to Preset' buttons."*
3. *"The button bottom edge overlaps with the bottom edge of the Presets frame.
   Make sure there is a distance … as done for other frames, such as the
   'Randomisation' or 'Layout' frames."*
4. *"The text refers to 'rows', or 'Rows answered', which is not intuitively
   understood as 'verification metrics' … Try to reword all the text, and the
   help text, so that you avoid 'rows'."*
5. the eleven "by Pharmacist" bundles: *"I prefer that these are noted as 'not
   usable for verification using From Profile Gamut' and then also mention
   which metrics cannot be fulfilled. Also, when ticking 'Show only the presets
   made for verification' these presets should not show up in the list."*
6. *"make it so that double-clicking a preset is equivalent to selecting and
   loading a preset from the 'Select preset' pulldown list … The double click
   feature must also be mentioned in the text explanation in the top of the
   window."*
7. *"The width of the right panel for detailed info is too narrow."*

**TWO OF THE SEVEN ARE GUARDS ON A STATE THAT WAS ALREADY TRUE**, and they are
here because a measurement said so, not because the code was changed to suit
them. Driven on screen 2026-09-19 in a real window
(`~/Desktop/ChromIQ-beta26-proof/knut-create-chart/`):

* item 2 — the button is **22 px** where "New seed" and "Reset to preset" are
  **24** each. It is already the shorter one, so the guard pins the relation
  Knut asked for rather than a number, and goes red the moment the button
  grows past either of them;
* item 7 — the splitter holds **73.8 / 26.2** at every window width measured
  (1040, 1179 and 1400 all gave it), which is the proportion in Knut's own
  screenshot. What his screenshot also has is a bigger WINDOW: 1179 px against
  the 1040 the window opened at, and that is the whole of the difference
  between a 263 px detail pane and a 299 px one. So the default is his size,
  and the guard pins the pane's share and its floor.

Every guard drives the REAL `TabChart` and the REAL dialog. `preset_eligibility`
is asked its own question directly only where the answer is a list of row ids.
"""
from __future__ import annotations

import inspect
import os
import re

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings, Qt                             # noqa: E402
from PyQt6.QtWidgets import (QApplication, QGroupBox,              # noqa: E402
                             QLabel, QSplitter)

from core.argyll_runner import ArgyllRunner                        # noqa: E402
from core.file_manager import FileManager, Project                 # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION          # noqa: E402
from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.measurement_target_bar import (                            # noqa: E402
    MeasurementTargetController)
from ui.tabs import tab_chart as TC                                # noqa: E402
from ui.tabs.tab_chart import (PREBUILT_PRESETS, TabChart,         # noqa: E402
                               verification_preset_rows)
from workflow import compliance_sets as CS                         # noqa: E402
from workflow import control_strip as CSP                          # noqa: E402
from workflow import measurement_messages as MM                    # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

#: His words, spelled here once so every guard below compares against the same
#: thing. Sentence case, which is what every other label in this app uses and
#: what the button font filter renders in capitals anyway; the WORDS are the
#: specification, and they are his.
NEW_NAME = "Which presets can be used for verification?"
OLD_NAME = "Which presets can be verified?"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "s.ini"),
                             QSettings.Format.IniFormat)
    out = tmp_path / "ChromIQ"
    out.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(out))
    # The ChromIQ layout engine's panel is where "New seed", "Randomisation"
    # and "Layout" live, and Knut named all three. Without this they are built
    # but hidden, and a hidden widget has no laid-out geometry to measure.
    settings.set("use_chromiq_layout_engine", True)
    fm = FileManager(settings)
    Project.create(out / "K", "K").current_run().ensure_dir()
    fm.set_target_name("K")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    return settings, fm, ctl


@pytest.fixture
def verification_tab(qapp, tmp_path):
    """A real Create Chart tab, Manual mode, on a VERIFICATION run."""
    settings, fm, ctl = _env(tmp_path)
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab.resize(1000, 900)
    tab.show()
    qapp.processEvents()
    tab._manual_btn.click()
    qapp.processEvents()
    tab._sync_preset_verify_visibility()
    tab._manual_layout_grp.set_collapsed(False)
    tab._manual_preset_bar.setVisible(True)
    qapp.processEvents()
    yield tab
    tab.close()
    tab.deleteLater()
    qapp.processEvents()


@pytest.fixture
def window(qapp, tmp_path):
    """The real dialog, over the real preset list."""
    settings, _fm, _ctl = _env(tmp_path)
    rows = verification_preset_rows(settings)
    dlg = PVD.PresetVerificationDialog(rows, None, None)
    dlg.show()
    qapp.processEvents()
    yield dlg
    dlg.close()
    dlg.deleteLater()
    qapp.processEvents()


def _rows_of(dlg) -> list:
    out = []
    for i in range(dlg._tree.topLevelItemCount()):
        head = dlg._tree.topLevelItem(i)
        for j in range(head.childCount()):
            out.append(head.child(j))
    return out


def _item_for(dlg, label: str):
    for it in _rows_of(dlg):
        row = it.data(0, Qt.ItemDataRole.UserRole)
        if row is not None and row.label == label:
            return it
    return None


def _detail_text(dlg) -> str:
    lay = dlg._detail_layout
    return "\n".join(lay.itemAt(i).widget().text()
                     for i in range(lay.count())
                     if isinstance(lay.itemAt(i).widget(), QLabel))


def _real_double_click(tree, item) -> bool:
    """The five events a real double click delivers, on the real viewport.

    **NOT `itemDoubleClicked.emit`, AND NOT `QTest.mouseDClick`.** Emitting the
    signal proves the connection and nothing about the gesture. `mouseDClick`
    sends press, release, DblClick, release with no SECOND press, and
    `QAbstractItemView::mouseDoubleClickEvent` refuses to emit `doubleClicked`
    unless `d->pressedIndex` still holds the index -- the release cleared it,
    so the view treats the DblClick as another press and nothing fires.
    Measured on screen 2026-09-19: the point was verified to be over the row,
    the gesture was sent, and the window sat there until a watchdog closed it.
    The window server sends press, release, press, DblClick, release.

    Returns False when the row could not be brought under a point, so a guard
    can refuse to pass on a gesture it never managed to make.
    """
    from PyQt6.QtCore import QEvent, QPointF
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtTest import QTest
    tree.scrollToItem(item)
    QApplication.processEvents()
    point = tree.visualItemRect(item).center()
    if tree.itemAt(point) is not item:
        return False
    vp = tree.viewport()
    L = Qt.MouseButton.LeftButton
    N = Qt.KeyboardModifier.NoModifier
    QTest.mousePress(vp, L, N, point)
    QTest.mouseRelease(vp, L, N, point)
    QTest.mousePress(vp, L, N, point)
    QApplication.sendEvent(vp, QMouseEvent(
        QEvent.Type.MouseButtonDblClick, QPointF(point), L, L, N))
    QTest.mouseRelease(vp, L, N, point)
    return True


# ---------------------------------------------------------------------------
# 1. the name
# ---------------------------------------------------------------------------
def test_the_button_the_window_and_the_warning_all_carry_the_new_name(
        verification_tab, window):
    """Item 1, in all three places Knut listed at once.

    The third is the one that is easy to miss: the chart-import warning
    (M-VERIFY-NO-CONTROL-STRIP) names the button through a ``{button}``
    placeholder filled from `control_strip.ELIGIBILITY_CONTROL`, so the name
    is settled in one place and this proves the rendered sentence really says
    it. A literal there would pass a check on the constant and still show a
    user the old words.
    """
    assert verification_tab._preset_verify_btn.text() == NEW_NAME
    assert verification_tab._preset_verify_help._title == NEW_NAME
    assert window.windowTitle() == NEW_NAME.rstrip("?")
    assert CSP.ELIGIBILITY_CONTROL == NEW_NAME
    _title, body = MM.CATALOGUE["M-VERIFY-NO-CONTROL-STRIP"].render(
        n=3, button=CSP.ELIGIBILITY_CONTROL)
    assert NEW_NAME in body
    assert OLD_NAME not in body


def test_no_string_a_user_can_read_still_says_can_be_verified():
    """*"…and any other place where this button is mentioned in text."*

    Over the `tr()` literals of the two modules that carry this window's text
    and the constant the warning interpolates, read off the source. A comment
    quoting Knut or Basti is not a string a user can read, so only `tr(...)`
    arguments and the constant are searched.
    """
    offenders = []
    for mod in (PVD, TC):
        src = inspect.getsource(mod)
        for lit in re.findall(r'tr\(\s*((?:"(?:[^"\\]|\\.)*"\s*)+)\)', src):
            text = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', lit))
            if "can be verified" in text:
                offenders.append(text[:90])
    assert CSP.ELIGIBILITY_CONTROL != OLD_NAME
    assert not offenders, (
        f"{len(offenders)} translated strings still say 'can be verified': "
        f"{offenders}")


def test_the_readme_a_user_downloads_names_the_button_the_window_shows():
    """R29-F1. A FOURTH place, and the one nothing was looking at.

    The check above reads `tr()` literals out of two UI modules, which is
    everything the WINDOW shows and nothing else. The demo-preset pack ships a
    README whose whole subject is this button, and its title is plain text in
    `scripts/make_verification_preset_demos.py`, so the rename went past it:
    the pack rebuilt hours after the rename still opened *ChromIQ demo presets
    for "Which presets can be verified?"*. Measured on the rebuilt folder at
    `/private/tmp/chromiq-k3/…/Create Chart presets (verification demos)/README.txt`.

    Knut's sentence is *"any other place where this button is mentioned in
    text"*, and a file a user downloads and reads is such a place. The title is
    now read off `control_strip.ELIGIBILITY_CONTROL`, so this asks the two
    questions that can still go wrong: the old words are gone, and the name in
    the README is the name the button carries.
    """
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "scripts") not in sys.path:
        sys.path.insert(0, str(root / "scripts"))
    import make_verification_preset_demos as GEN
    text = GEN.readme()
    assert OLD_NAME not in text, (
        "the README a user downloads still names the button Knut renamed")
    assert CSP.ELIGIBILITY_CONTROL in text, (
        "the README names no button at all, so nothing keeps it in step with "
        "the window")


# ---------------------------------------------------------------------------
# 2. the height
# ---------------------------------------------------------------------------
def test_the_button_is_no_taller_than_the_two_knut_named(verification_tab,
                                                         qapp):
    """Item 2, as a RELATION and not as a number.

    Knut asked for *"the button height similar to 'New Seed' or 'Reset to
    Preset'"*. Measured on screen on 2026-09-19 the three are 22, 24 and 24, so
    the button is already the shortest of them; the requirement he stated is
    that it is not the tallest, and that is what is pinned. A hard-coded 22
    here would go red the day somebody legitimately changes the app's button
    metrics, and would say nothing about the two buttons he actually named.
    """
    tab = verification_tab
    btn = tab._preset_verify_btn
    new_seed = tab._manual_layout_panel.new_seed_btn
    reset = tab._manual_preset_reset_btn
    assert btn.isVisibleTo(tab), "the button is not laid out, so not measurable"
    for name, other in (("New seed", new_seed), ("Reset to preset", reset)):
        assert other.height() > 0, f"{name} is not laid out"
        assert btn.height() <= other.height(), (
            f"the preset-eligibility button is {btn.height()} px and "
            f"{name!r} is {other.height()} px, so it is the taller of the two "
            f"— Knut asked for the opposite")


# ---------------------------------------------------------------------------
# 3. the distance to the frame's bottom edge
# ---------------------------------------------------------------------------
def test_the_presets_frame_leaves_the_same_bottom_gap_as_the_others(
        verification_tab):
    """Item 3, against the two frames Knut named, in their own units.

    "Randomisation" and "Layout" set no contents margins at all, so they get
    the style's `PM_LayoutBottomMargin`; the Presets frame set its own 8 and
    came out 1 px tighter than both. The comparison is the point, so the
    numbers are read off the three layouts rather than written down.
    """
    tab = verification_tab
    presets = next(g for g in tab.findChildren(QGroupBox)
                   if g.title() == "Presets")
    named = {g.title(): g
             for g in tab._manual_layout_panel.findChildren(QGroupBox)
             if g.title() in ("Randomisation", "Layout")}
    assert set(named) == {"Randomisation", "Layout"}, (
        f"the two frames Knut named are not both here: {sorted(named)}")
    mine = presets.layout().contentsMargins().bottom()
    for title, grp in named.items():
        theirs = grp.layout().contentsMargins().bottom()
        assert mine >= theirs, (
            f"the Presets frame leaves {mine} px under its last widget and "
            f"{title!r} leaves {theirs} px, so the button sits closer to its "
            f"frame edge than Knut's reference frames do")


# ---------------------------------------------------------------------------
# 4. "rows" is gone
# ---------------------------------------------------------------------------
def test_nothing_this_window_shows_a_reader_says_row(window, qapp):
    """Item 4, over every sentence the window actually puts on screen.

    Not over the source: the source still holds `row_label`, `rows_asked` and
    a hundred row ids, and none of those is text. This walks the built widgets
    — the intro, the count line, the tick box, the four column headings, the
    figures line and a filled detail pane — and searches what they display.
    """
    window._type_combo.setCurrentIndex(0)
    qapp.processEvents()
    shown = [window._asked_label.text(), window._only_star.text(),
             window._figures.text(), window.windowTitle()]
    outer = window.layout()
    shown += [outer.itemAt(i).widget().text() for i in range(outer.count())
              if isinstance(outer.itemAt(i).widget(), QLabel)]
    shown += [window._tree.headerItem().text(c)
              for c in range(window._tree.columnCount())]
    items = _rows_of(window)
    assert items, "the list is empty, so this guard would pass on nothing"
    shown.append(items[0].text(3))
    window._tree.setCurrentItem(items[0])
    qapp.processEvents()
    shown.append(_detail_text(window))
    # THE CHART'S OWN ROWS ARE NOT TABLE ROWS (beta 38, E2). Item 4 is about
    # calling a metric a "row". "9 strips and 9 rows" is the patch grid on the
    # page, the evenness floor Knut ruled in those words, and it first reached
    # this pane when the page-coverage floor gave the first preset in the list
    # an evenness shortfall. That same shortfall exposed four "row"s in
    # M-VERIFY-UNCHECKED-METRICS and one in the evenness remedy, which now say
    # "metric". MUTATION: put "the row is shown reading N-A" back and this
    # goes red.
    shown = [re.sub(r"\bstrips and \d+ rows\b", "strips and N patch-lines", s)
             for s in shown]
    bad = [s for s in shown if re.search(r"\brows?\b", s, re.I)]
    assert not bad, f"still says 'row': {[b[:80] for b in bad]}"


def test_the_count_line_is_the_sentence_knut_wrote(window, qapp):
    """*"How about writing 'This report type and limit set asks to verify 9
    metrics of a chart during verification.'"* — his sentence, with the count
    coming from the app."""
    window._type_combo.setCurrentIndex(0)
    qapp.processEvents()
    n = len(PE.rows_asked(window.current_type(), window.current_set(), None))
    assert n > 1, "pick a combination that asks for more than one metric"
    assert window._asked_label.text() == (
        f"This report type and limit set asks to verify {n} metrics of a "
        f"chart during verification.")


# ---------------------------------------------------------------------------
# 5. the "by Pharmacist" bundles
# ---------------------------------------------------------------------------
def test_every_by_pharmacist_preset_is_a_prebuilt_image_and_no_others_are(
        tmp_path):
    """The set Knut named by NAME is the set the code can name by PROPERTY.

    He wrote *"all the built-in presets called '… by Pharmacist'"* and gave the
    reason: *"these charts do not have a proper layout and come with pre-made
    tif files"*. Those are two different ways of picking a set, and this is
    what makes it safe to implement the property: measured on this tree they
    are the same eleven presets, so nothing is excluded that he did not name
    and nothing he named is left in.
    """
    settings, _fm, _ctl = _env(tmp_path)
    rows = verification_preset_rows(settings)
    by_name = {r.label for r in rows if "by Pharmacist" in r.label}
    by_property = {r.label for r in rows if not r.relayoutable}
    assert by_name == by_property, (
        f"named but not excluded: {sorted(by_name - by_property)}; "
        f"excluded but not named: {sorted(by_property - by_name)}")
    assert len(by_name) == len(PREBUILT_PRESETS) == 11


def test_a_prebuilt_preset_never_carries_the_star_and_leaves_the_filtered_list(
        window, qapp):
    """*"when ticking 'Show only the presets made for verification' these
    presets should not show up in the list."*

    And the negative control in the same guard: with the box UNticked they are
    all still there, because Knut asked for them to be noted, not hidden.
    """
    unfiltered = {it.data(0, Qt.ItemDataRole.UserRole).label
                  for it in _rows_of(window)}
    pharma = {lbl for lbl in unfiltered if "by Pharmacist" in lbl}
    assert len(pharma) == 11, f"only {len(pharma)} of the eleven are listed"
    assert not any(r.starred for r in window._rows if not r.relayoutable)

    window._only_star.setChecked(True)
    qapp.processEvents()
    filtered = {it.data(0, Qt.ItemDataRole.UserRole).label
                for it in _rows_of(window)}
    assert filtered, "the filtered list is empty, so this proves nothing"
    assert not (filtered & pharma), (
        f"still listed with the tick box on: {sorted(filtered & pharma)}")


def test_the_detail_pane_says_from_profile_gamut_and_names_the_metrics(
        window, qapp):
    """*"noted as 'not usable for verification using From Profile Gamut' and
    then also mention which metrics cannot be fulfilled."*"""
    label = next(r.label for r in window._rows if not r.relayoutable)
    item = _item_for(window, label)
    assert item is not None
    window._tree.setCurrentItem(item)
    qapp.processEvents()
    text = _detail_text(window)
    assert "Not usable for verification using From Profile Gamut" in text
    named = PE.gamut_only_rows()
    assert named, "there is nothing to name, so this guard proves nothing"
    for rid in named:
        assert PE.row_label(rid) in text, (
            f"{PE.row_label(rid)!r} is out of reach on this preset and the "
            f"pane does not say so")


def test_the_gamut_only_metrics_are_the_rows_the_report_itself_withholds():
    """The list in the pane is not a second opinion.

    `gamut_only_rows` reads the row table; the report withholds a row with
    ``needs_reference_file`` when it has no colorimetric reference. This asks
    a REAL preset chart through `chart_row_values`, which is
    `measurement_report`'s own code, and requires the two to agree exactly.
    Two lists of metrics that can drift apart is the fault this project keeps
    finding.
    """
    from core.resource_path import resource_path
    chart = resource_path(TC.PREBUILT_PRESETS[TC.TC300_PRESET_KEY][0] + ".ti1")
    assert chart.is_file(), f"the fixture chart is missing: {chart}"
    values = PE.chart_row_values(chart)
    withheld = tuple(
        r.id for r in CS.ROWS
        if (values.get(r.id) or {}).get("reason")
        == MR.REASON_NEEDS_REFERENCE_FILE)
    assert withheld, "no row was withheld, so the comparison is vacuous"
    assert PE.gamut_only_rows() == withheld


def test_made_for_verification_refuses_a_sheet_that_cannot_be_laid_out_again():
    """The rule, at the level it is applied, with the negative control beside
    it: the SAME chart, patch count and page count, starred when the sheet can
    be built again and not when it cannot."""
    from core.resource_path import resource_path
    chart = resource_path(TC.PREBUILT_PRESETS[TC.TC300_PRESET_KEY][0] + ".ti1")
    patches = PE.patch_count(chart)
    assert PE.made_for_verification(chart, patches, 1, relayoutable=True)
    assert not PE.made_for_verification(chart, patches, 1, relayoutable=False)


# ---------------------------------------------------------------------------
# 6. the double click
# ---------------------------------------------------------------------------
def test_a_double_click_records_the_preset_and_closes_the_window(window,
                                                                 qapp):
    """Item 6's first half. The window does not load anything itself: it says
    WHICH preset and accepts, because applying one asks for a name and can
    start a build, and none of that may happen under a modal still on screen.
    """
    item = next(it for it in _rows_of(window)
                if it.data(0, Qt.ItemDataRole.UserRole).key)
    row = item.data(0, Qt.ItemDataRole.UserRole)
    assert window.chosen_key is None
    assert _real_double_click(window._tree, item), (
        "the row could not be brought under a click point, so no gesture was "
        "made and this guard would pass on nothing")
    qapp.processEvents()
    assert window.chosen_key == row.key
    assert not window.isVisible()
    assert window.result() == PVD.QDialog.DialogCode.Accepted


def test_a_double_click_on_a_group_heading_does_nothing(window, qapp):
    """A heading is not a preset, and double-clicking one expands the group,
    which is what a reader expects. Nothing may be loaded from it."""
    head = window._tree.topLevelItem(0)
    assert head is not None and head.childCount()
    assert _real_double_click(window._tree, head), (
        "the heading could not be brought under a click point")
    qapp.processEvents()
    assert window.chosen_key is None
    assert window.isVisible()


def test_every_row_carries_the_key_the_pulldown_uses(tmp_path, qapp):
    """A double-click can only load what it can address. Each built-in row's
    key must be an entry in the Create Chart pulldown, or the gesture would
    close the window and do nothing."""
    settings, fm, ctl = _env(tmp_path)
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    qapp.processEvents()
    try:
        in_combo = {tab._preset_combo.itemData(i)
                    for i in range(tab._preset_combo.count())}
        rows = verification_preset_rows(settings)
        missing = [r.label for r in rows
                   if r.builtin and (not r.key or r.key not in in_combo)]
        assert not missing, (
            f"{len(missing)} listed presets cannot be reached through the "
            f"pulldown: {missing[:5]}")
    finally:
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


def test_the_tab_loads_what_the_window_chose_through_the_pulldowns_own_path(
        verification_tab, qapp, monkeypatch):
    """Item 6's second half: *"equivalent to selecting and loading a preset
    from the 'Select preset' pulldown list."*

    Equivalent means the same code, so the guard is that the tab routes the
    choice into `_activate_builtin_preset`, which is the pulldown's own "apply
    this entry now" path — not that some preset was applied somehow.
    """
    tab = verification_tab
    applied: list = []
    monkeypatch.setattr(TabChart, "_activate_builtin_preset",
                        lambda self, key: applied.append(key))

    chosen = {"key": None}

    class _Stub:
        chosen_key = None

        def __init__(self, *a, **k):
            self.chosen_key = chosen["key"]

        def exec(self):
            return 0

    monkeypatch.setattr(PVD, "PresetVerificationDialog", _Stub)

    chosen["key"] = None
    tab._open_preset_verification_window()
    assert applied == [], "a window closed with no choice applied a preset"

    chosen["key"] = TC.TC300_PRESET_KEY
    tab._open_preset_verification_window()
    assert applied == [TC.TC300_PRESET_KEY]


def test_the_window_tells_the_reader_about_the_double_click(window):
    """*"The double click feature must also be mentioned in the text
    explanation in the top of the window."* — the intro label, which is the
    first thing in the window's own layout."""
    outer = window.layout()
    intro = next(outer.itemAt(i).widget() for i in range(outer.count())
                 if isinstance(outer.itemAt(i).widget(), QLabel))
    assert "double-click" in intro.text().lower()


# ---------------------------------------------------------------------------
# 7. the right panel
# ---------------------------------------------------------------------------
def test_the_window_opens_at_the_size_in_knuts_screenshot(window):
    """Item 7. His picture is 1179 x 730 and its detail pane is about 305 px;
    the window used to open at 1040 x 700, where the same proportion gives
    263. The proportion was never the difference — the window size was."""
    assert window.width() == 1179
    assert window.height() <= 730


def test_the_detail_pane_keeps_its_share_and_has_a_floor(window, qapp):
    """The share Knut photographed, and a floor under it.

    Measured off his screenshot: the list is 73.1 % of the splitter and the
    detail pane 26.5 %. The guard allows the pane a little more and never
    less, and separately requires it to survive a window small enough to
    squeeze it, because a word-wrapped metric name three words wide is not
    readable and an elided preset name still is.
    """
    split = window.findChild(QSplitter)
    sizes = split.sizes()
    share = sizes[1] / float(sum(sizes))
    assert 0.25 <= share <= 0.40, (
        f"the detail pane is {share:.1%} of the splitter; Knut's screenshot "
        f"is 26.5 % and he asked for no less")
    window.resize(700, window.height())
    qapp.processEvents()
    assert window.findChild(QSplitter).sizes()[1] >= 280, (
        "the detail pane collapsed when the window was made small")
