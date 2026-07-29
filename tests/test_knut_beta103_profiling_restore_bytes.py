"""#130: a restored PROFILING chart must come back byte-for-byte.

Found while reproducing Knut's beta.98 report on 2026-07-29, and confirmed here:
for a profiling run the ``.ti2`` was still not identical after Restore Used Chart.

The cause is an ordering fault in ``_on_generate_finished``. The redraw that
follows a restore arms :class:`_ChartRebuildGuard`, which holds the chart's own
bytes and puts them back if the redraw changed them. But the guard was released
in the *"not a verification build"* branch — written when a profiling build could
never arm it — and that branch runs BEFORE ``_maybe_autotag_randomised``, which
rewrites ``CHART_ID`` to ``RANDOM_START`` on a well-mixed fixed-order chart. So
the bytes were put back and then re-tagged a line later, and the chart that came
back was marked as shuffled when it had been laid out in fixed order. chartread
reads those two differently, so the run's measurement described a sheet that no
longer existed — silently, which is the same shape as the beta.97 fault.

The release after the auto-tag is the correct one, and the early release now only
covers the case it was really for: a build that produced no chart at all, where
the later release is never reached.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtGui import QImage                            # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.tabs.tab_chart import TabChart, _ChartRebuildGuard  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# A fixed-order chart whose colours ARE well mixed — exactly the kind the
# auto-tag upgrades, and therefore the kind a restore can silently alter.
def _mixed_fixed_order_ti2(n: int = 24) -> str:
    rows = []
    # A deliberately shuffled walk through the cube, so analyze_randomisation
    # sees a well-mixed layout rather than a ramp.
    steps = [0, 100, 50, 75, 25, 100, 0, 50, 75, 25, 50, 0,
             100, 25, 75, 0, 50, 100, 25, 0, 75, 50, 100, 25]
    for i in range(n):
        r = steps[i % len(steps)]
        g = steps[(i * 7 + 3) % len(steps)]
        b = steps[(i * 5 + 11) % len(steps)]
        row, col = divmod(i, 6)
        rows.append(f"{i + 1} {chr(65 + row)}{col + 1} {r} {g} {b}")
    body = "\n".join(rows)
    return (
        "CTI2\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        'CREATED "test"\n'
        "CHART_ID 12345\n"
        "TOTAL_INK_LIMIT 400\n"
        "COLOR_REP RGB\n"
        "NUMBER_OF_FIELDS 5\n"
        "BEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\n"
        f"NUMBER_OF_SETS {n}\n"
        "BEGIN_DATA\n"
        f"{body}\n"
        "END_DATA\n"
    )


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"
    root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    fm.set_target_name("P")
    tab = TabChart(ArgyllRunner(s), fm, s)
    return s, fm, run, tab


def _page(run):
    """A real (tiny) page image beside the chart, so the preview can load it."""
    tif = run.dir / f"{run.stem}_01.tif"
    img = QImage(8, 8, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    assert img.save(str(tif), "TIFF")
    return tif


def test_the_auto_tag_really_would_alter_this_chart(qapp, tmp_path):
    """The premise of the test below: without a guard, finishing a build rewrites
    this chart's keyword. If this ever stops being true the next test proves
    nothing, so it is asserted on its own."""
    _s, _fm, run, tab = _env(tmp_path)
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())
    before = ti2.read_bytes()

    tab._maybe_autotag_randomised(ti2)

    assert ti2.read_bytes() != before, \
        "the auto-tag left this chart alone — pick a layout it does upgrade"
    assert b"RANDOM_START" in ti2.read_bytes()


def test_a_restored_profiling_chart_survives_the_redraw(qapp, tmp_path):
    """Knut's case, driven through the real handler: the guard is armed as
    ``rebuild_verification_pages`` arms it, the finished build is reported, and
    the chart must be exactly what was restored."""
    _s, _fm, run, tab = _env(tmp_path)
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())
    ti2.with_suffix(".ti1").write_text("CTI1\n")
    restored = ti2.read_bytes()
    tif = _page(run)

    tab._rebuild_guard = _ChartRebuildGuard(ti2)
    tab._on_generate_finished([tif])

    assert ti2.read_bytes() == restored, (
        "the redraw altered the restored chart: "
        f"CHART_ID={b'CHART_ID' in ti2.read_bytes()} "
        f"RANDOM_START={b'RANDOM_START' in ti2.read_bytes()}")
    assert b"CHART_ID" in ti2.read_bytes(), \
        "the fixed-order keyword was replaced — chartread would read this " \
        "chart differently from the sheet that was measured"


def test_an_ordinary_profiling_build_is_still_auto_tagged(qapp, tmp_path):
    """The guard must not become a general "never re-tag" switch: a NORMAL build
    (no restore, so no guard) still gets the upgrade that makes chartread read it
    bidirectionally."""
    _s, _fm, run, tab = _env(tmp_path)
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())
    ti2.with_suffix(".ti1").write_text("CTI1\n")
    tif = _page(run)

    assert getattr(tab, "_rebuild_guard", None) is None
    tab._on_generate_finished([tif])

    assert b"RANDOM_START" in ti2.read_bytes(), \
        "a normal build lost its auto-tag"


def test_a_build_that_made_no_chart_still_lets_the_guard_go(qapp, tmp_path):
    """The early release exists for a verification build that failed or was
    cancelled — the success path never runs, so nothing else would free it."""
    _s, _fm, run, tab = _env(tmp_path)
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())

    tab._rebuild_guard = _ChartRebuildGuard(ti2)
    tab._on_generate_finished([])

    assert getattr(tab, "_rebuild_guard", None) is None, \
        "a failed build left the guard armed, so the next build would be held"


def test_the_early_release_is_gated_on_there_being_no_chart():
    """Pins the ordering rule in the source, because the failure it prevents is
    invisible: the bytes are put back and then rewritten one line later."""
    src = inspect.getsource(TabChart._on_generate_finished)
    early = src.index("if not tiffs:\n                self._release_rebuild_guard()")
    late = src.rindex("self._release_rebuild_guard()")
    assert early < late, "there is no longer a release after the auto-tag"
    autotag = src.index("_maybe_autotag_randomised")
    assert autotag < late, \
        "the guard is released before the auto-tag again — that is the bug"


# ---- the other half of Knut's beta.98 report ------------------------------
def test_the_options_are_restored_when_the_copy_records_them(qapp, tmp_path):
    """*"After restore of the chart the options in the Create Chart is not
    changed back to what they were before."*

    Driven on the real panel: a chart made WITHOUT a clip border, options then
    changed to have one, and the restore must put the chart's own settings back.
    This is the case that was reported, and it works — which is why the message
    added alongside covers the case that genuinely cannot.
    """
    import json

    from workflow.layout_engine.presets import default_recipe
    _s, _fm, run, tab = _env(tmp_path)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    panel = tab._manual_layout_panel

    as_measured = default_recipe("i1", "A4")
    as_measured.clip_border = False
    as_measured.clip_content_mode = "off"
    as_measured.patch_w_mm = 9.0
    as_measured.chart_text = "as measured"
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())
    ti2.with_suffix(".channels.json").write_text(json.dumps({
        "inks": ["R", "G", "B"],
        "layout": {"recipe": {k: v for k, v in vars(as_measured).items()},
                   "seed": 12345, "patches": [{"page": 0}]},
        "engine": "chromiq", "engine_version": 2, "color_rep": "RGB"}))

    meddled = default_recipe("i1", "A4")
    meddled.clip_border = True
    meddled.clip_content_mode = "notes"
    meddled.patch_w_mm = 7.0
    meddled.chart_text = "user meddled"
    panel.set_recipe(meddled)
    assert panel.clip_enabled() is True

    assert tab._restore_chart_settings(ti2) is True

    assert panel.clip_enabled() is False, "the clip border stayed on"
    assert panel.mode.currentData() == as_measured.mode()
    assert panel.patch_x.value() == 9.0
    assert panel.chart_text.text() == "as measured"


def test_a_copy_without_its_settings_says_so_instead_of_staying_silent(qapp, tmp_path):
    """A stored chart from before the settings sidecar existed has nothing to
    restore the options from. Leaving them alone is right; leaving them alone
    WITHOUT A WORD is what made a working restore look broken."""
    _s, _fm, run, tab = _env(tmp_path)
    src = inspect.getsource(TabChart.rebuild_verification_pages)
    assert "if not restored_recipe:" in src
    assert "carries no record of the" in src
    # …and it is said after the restore was attempted, not before.
    assert src.index("_restore_chart_settings(ti2)") < src.index(
        "if not restored_recipe:")


def test_the_message_never_claims_the_chart_itself_is_wrong(qapp):
    """The chart files ARE guaranteed — only the on-screen options are not. A
    message that blurred those two would frighten somebody off a good restore."""
    src = inspect.getsource(TabChart.rebuild_verification_pages)
    start = src.index("carries no record of the")
    text = src[start - 400:start + 700]
    assert "put back exactly as they were" in text
    assert "(s)" not in text


# ---- Knut's actual case, named on 2026-07-29 22:40Z -----------------------
def test_restoring_a_printtarg_chart_turns_the_engine_toggle_off(qapp, tmp_path):
    """*"If the stored chart in chart/ folder was made with printtarg layout
    engine, and I change the Create Chart manual mode parameters for ChromIQ
    layout engine, then settings from both layout engines should be restored when
    clicking Restore Used Chart. I suspected this was the case."*

    He was right, and it was the opposite way round from what I had been testing.
    Restoring an ENGINE chart switches the engine on. Restoring a PRINTTARG chart
    used to leave it on as well — and with the engine on, the printtarg fields
    that had just been restored were ignored, because the build reads whichever
    engine is selected. So the options on screen did not describe the stored
    chart.
    """
    import json

    _s, _fm, run, tab = _env(tmp_path)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()

    # A stored chart with NO layout recipe — i.e. drawn by printtarg — but with
    # its printtarg fields saved beside it, which is what a build writes.
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())
    fields = [{"flag": pw.flag, "value": pw.get_raw_value(), "enabled": False}
              for pw in tab._manual_widgets.get("printtarg", [])]
    assert fields, "no printtarg fields to restore — check the panel built"
    ti2.with_suffix(".channels.json").write_text(json.dumps({
        "inks": ["R", "G", "B"], "printtarg_fields": fields}))

    # The user has since moved to the ChromIQ engine.
    tab._manual_engine_check.setChecked(True)
    assert tab._manual_engine_check.isChecked()

    assert tab._restore_chart_settings(ti2) is False   # no recipe to restore

    assert not tab._manual_engine_check.isChecked(), (
        "the engine stayed on after restoring a printtarg chart, so the "
        "restored printtarg fields would be ignored")


def test_restoring_an_engine_chart_still_turns_the_engine_on(qapp, tmp_path):
    """The other direction must keep working — this is a symmetry fix, not a
    switch-it-off-always."""
    import json

    from workflow.layout_engine.presets import default_recipe
    _s, _fm, run, tab = _env(tmp_path)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    rec = default_recipe("i1", "A4")
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())
    ti2.with_suffix(".channels.json").write_text(json.dumps({
        "inks": ["R", "G", "B"],
        "layout": {"recipe": {k: v for k, v in vars(rec).items()},
                   "seed": 1, "patches": [{"page": 0}]},
        "engine": "chromiq", "engine_version": 2}))

    tab._manual_engine_check.setChecked(False)
    assert tab._restore_chart_settings(ti2) is True
    assert tab._manual_engine_check.isChecked(), \
        "an engine chart must bring the engine back on"


def test_a_chart_with_no_sidecar_at_all_leaves_the_toggle_alone(qapp, tmp_path):
    """Nothing is known about such a chart, so nothing should be claimed about
    it — flipping the engine off here would be a guess, not a restore."""
    _s, _fm, run, tab = _env(tmp_path)
    tab._switch_mode("manual")
    if not tab._manual_panel_inited:
        tab._init_manual_layout_panel()
    ti2 = run.chart_ti2
    ti2.write_text(_mixed_fixed_order_ti2())      # no .channels.json beside it

    tab._manual_engine_check.setChecked(True)
    assert tab._restore_chart_settings(ti2) is False
    assert tab._manual_engine_check.isChecked(), \
        "with no sidecar there is nothing to restore, so nothing may change"
