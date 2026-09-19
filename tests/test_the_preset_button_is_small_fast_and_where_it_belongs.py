"""Round 27b: the "Which presets can be verified?" button, after Basti's two
sentences about it and Knut's one.

Basti, on beta 22: *"the which presets can be verified button in create chart
tab under the presets combobox is very big. at least the hight could be
reduced"* and *"clicking the button takes quite long until the window opens."*
Knut, the same day: the pair belongs to a **verification run only**.

Beta 22 + three commits answered all three. Driven on screen (round 27b,
``~/Desktop/ChromIQ-beta23-proof/round-27b-chart/``), three of the answers were
wrong or incomplete, and these are the guards on the corrections:

1. **the button was 2 px TALLER than the one Basti called too big.** Its
   stylesheet set ``min-height: 22px``, which Qt applies to the CONTENT
   rectangle and then adds padding and frame to: 24 px became 26. Photographed
   with beta 22's own button inserted beside it
   (``shots/crop-03-old-and-new-height.png``).
2. **the idle warming ran on a profiling run**, where Knut's rule means the
   button does not exist: 177 preset charts read off disk and a second of
   processor for a window that cannot be opened.
3. **every open re-parsed all 177 ``.ti1`` files** to count their patches,
   which is the other half of the wait and was not cached with the first half.
   Timed in the real window: 324 ms warm before, 45 ms after.
4. **the window opened on nothing**, so the answer to "can THIS preset be
   verified?" was a list of 177 rows in nine groups with no search field.
5. **a preset whose patch set cannot be read was blamed on its page count**,
   in the sentence above the one that says what is really wrong.

Every guard drives the real ``TabChart`` and the real dialog. Measuring the
helpers would not have caught (1) at all — the number in the stylesheet was
22, and the button was 26.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                                 # noqa: E402
from PyQt6.QtGui import QFontMetrics                               # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton              # noqa: E402

from core.argyll_runner import ArgyllRunner                        # noqa: E402
from core.file_manager import FileManager, Project                 # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,           # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.measurement_target_bar import (                            # noqa: E402
    MeasurementTargetController)
from ui.tabs.tab_chart import (BUILTIN_PRESET_GROUPS,              # noqa: E402
                               TabChart, verification_preset_rows)
from workflow import preset_eligibility as PE                      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _env(tmp_path):
    """A real project, a real FileManager, a real target controller."""
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "s.ini"),
                             QSettings.Format.IniFormat)
    out = tmp_path / "ChromIQ"
    out.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(out))
    fm = FileManager(settings)
    Project.create(out / "D", "D").current_run().ensure_dir()
    fm.set_target_name("D")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    return settings, fm, ctl


def _tab(settings, fm, ctl):
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    return tab


@pytest.fixture
def verification_tab(qapp, tmp_path):
    """A real Create Chart tab, in Manual mode, on a VERIFICATION run."""
    settings, fm, ctl = _env(tmp_path)
    tab = _tab(settings, fm, ctl)
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab.show()
    qapp.processEvents()
    tab._manual_btn.click()
    qapp.processEvents()
    tab._sync_preset_verify_visibility()
    qapp.processEvents()
    yield tab
    tab.close()
    tab.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# 1. the height
# ---------------------------------------------------------------------------
def test_the_button_is_shorter_than_the_one_beta_22_shipped(verification_tab,
                                                            qapp):
    """Basti asked for it to be shorter. Beta 22's button is the yardstick,
    and it is built here rather than remembered: same label, same parent, no
    size rule — which is exactly what beta 22 had.

    The first answer to his message set the height through a stylesheet and
    made the button BIGGER, because ``min-height`` in a stylesheet sizes the
    content box and Qt adds the padding and the frame around it. A number in a
    rule is not a height; only the widget's own height is.
    """
    tab = verification_tab
    btn = tab._preset_verify_btn
    assert btn.isVisibleTo(tab), "the button is not on screen to be measured"

    plain = QPushButton(btn.text(), btn.parentWidget())
    plain.setFont(btn.font())
    plain.show()
    qapp.processEvents()
    beta22 = plain.sizeHint().height()
    plain.setParent(None)
    plain.deleteLater()

    assert btn.height() < beta22, (
        f"the button is {btn.height()} px tall and beta 22's — the one Basti "
        f"called very big — is {beta22} px. It was asked to shrink.")
    # …and it is still a button with a whole word in it.
    line = QFontMetrics(btn.font()).height()
    assert btn.height() >= line, (
        f"{btn.height()} px of button for {line} px of text clips the label")


# ---------------------------------------------------------------------------
# 2. the warming belongs to the run type the button belongs to
# ---------------------------------------------------------------------------
def test_a_profiling_run_never_pays_for_the_warming(qapp, tmp_path):
    """Knut: the button is for a verification run only. So is the work behind
    it. Measured on screen before this guard: a plain profiling session opened
    Create Chart and read all 177 preset charts for a window it cannot open."""
    settings, fm, ctl = _env(tmp_path)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    tab = _tab(settings, fm, ctl)
    try:
        tab.show()
        qapp.processEvents()
        tab._manual_btn.click()          # the mode the Presets group lives in
        qapp.processEvents()
        assert not tab._preset_verify_btn.isVisibleTo(tab), \
            "the button is on screen during a profiling run"
        assert getattr(tab, "_preset_warm_timer", None) is None, (
            "a profiling run started warming "
            f"{len(getattr(tab, '_preset_warm_charts', []) or [])} preset "
            "charts for a button that is not there")

        # …and the moment the run type makes the button appear, it starts.
        ctl.set_run_type(RUN_TYPE_VERIFICATION)
        tab._sync_preset_verify_visibility()
        qapp.processEvents()
        assert tab._preset_verify_btn.isVisibleTo(tab)
        assert getattr(tab, "_preset_warm_timer", None) is not None, (
            "the button appeared and nothing began filling the cache behind "
            "it, so the first click pays the whole three seconds")
        assert len(tab._preset_warm_charts) > 100
    finally:
        t = getattr(tab, "_preset_warm_timer", None)
        if t is not None:
            t.stop()
        tab.close()
        tab.deleteLater()
        qapp.processEvents()


# ---------------------------------------------------------------------------
# 3. the other half of the wait
# ---------------------------------------------------------------------------
def test_the_list_does_not_reparse_every_ti1_on_every_open(qapp, monkeypatch):
    """`verification_preset_rows` counts the patches of all 177 shipped charts
    to build the list, and did it again on every open of the window. 280 ms,
    measured, on top of a cache that had already been filled."""
    PE.clear_cache()
    settings = AppSettings()
    verification_preset_rows(settings)              # the first, honest read

    calls: list = []
    real = PE.parse_ti3

    def counted(path, *a, **kw):
        calls.append(path)
        return real(path, *a, **kw)
    monkeypatch.setattr(PE, "parse_ti3", counted)

    verification_preset_rows(settings)              # …and the second
    assert not calls, (
        f"opening the window read {len(calls)} chart files again: "
        f"{[Path(p).name for p in calls[:4]]}")


# ---------------------------------------------------------------------------
# 4. the window opens on the preset you asked about
# ---------------------------------------------------------------------------
def test_the_window_opens_on_the_preset_the_pulldown_is_on(verification_tab,
                                                           qapp, monkeypatch):
    """The real pulldown, the real button, the real handler, the real dialog.

    Before this, the answer to "can the preset I have chosen be verified?" was
    177 rows in nine instrument groups with nothing selected and no way to
    search by name.
    """
    tab = verification_tab
    combo = tab._preset_combo
    want = next(i for i in range(combo.count())
                if combo.itemData(i) and combo.model().item(i).isEnabled())
    combo.setCurrentIndex(want)
    qapp.processEvents()
    label = tab._chosen_preset_label()
    assert label, "the tab could not name the preset its own pulldown is on"

    seen: list = []

    def _no_block(self):
        seen.append(self)
        return 0
    monkeypatch.setattr(PVD.PresetVerificationDialog, "exec", _no_block)
    tab._preset_verify_btn.click()
    qapp.processEvents()
    assert seen, "the button opened no window"
    dlg = seen[0]
    try:
        cur = dlg._tree.currentItem()
        assert cur is not None, (
            "the window opened with nothing selected, so the preset the user "
            "asked about is one row among %d" % len(dlg._rows))
        from PyQt6.QtCore import Qt
        row = cur.data(0, Qt.ItemDataRole.UserRole)
        assert row is not None and row.label == label, (
            f"the window opened on {cur.text(0)!r}, not on the preset the "
            f"pulldown is on ({label!r})")
        # …and the reader's own later choice survives a refresh.
        other = None
        for i in range(dlg._tree.topLevelItemCount()):
            head = dlg._tree.topLevelItem(i)
            for j in range(head.childCount()):
                c = head.child(j)
                if c is not cur:
                    other = c
                    break
            if other is not None:
                break
        dlg._tree.setCurrentItem(other)
        kept = other.text(0)
        dlg.refresh()
        qapp.processEvents()
        assert dlg._tree.currentItem() is not None
        assert dlg._tree.currentItem().text(0) == kept, \
            "a refresh threw the reader back to the preset they came in on"
    finally:
        dlg.close()


# ---------------------------------------------------------------------------
# 5. the reason a preset cannot be checked is the reason that is shown
# ---------------------------------------------------------------------------
def test_an_unreadable_patch_set_is_not_blamed_on_the_page_count(qapp,
                                                                 tmp_path):
    """The demo pack's "Verify demo 13, the patch set cannot be read", in the
    real detail pane.

    It read: *"ChromIQ cannot tell how many pages this preset lays out until
    its chart is generated…"* and only underneath it *"ChromIQ could not read
    this preset's patch set."* The first sentence sends a reader off to
    generate a chart; the second is what is actually wrong.
    """
    bad = tmp_path / "not-a-chart.ti1"
    bad.write_text("this is not a chart\n", encoding="utf-8")
    row = PVD.PresetRow(group="Custom presets", label="R27b unreadable",
                        chart=bad, patches=0, pages=0, builtin=False)
    dlg = PVD.PresetVerificationDialog([row])
    try:
        qapp.processEvents()
        item = dlg._tree.topLevelItem(0).child(0)
        dlg._tree.setCurrentItem(item)
        qapp.processEvents()
        shown = []
        for i in range(dlg._detail_layout.count()):
            w = dlg._detail_layout.itemAt(i).widget()
            if w is not None and hasattr(w, "text"):
                shown.append(w.text())
        assert any("could not read this preset's patch set" in t
                   for t in shown), shown
        assert not any("how many pages this preset lays out" in t
                       for t in shown), (
            "the pane blames the page count for a patch set it could not read "
            f"at all: {shown}")
    finally:
        dlg.close()
