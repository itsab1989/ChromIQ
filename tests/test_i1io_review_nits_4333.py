"""THREE NITS THE 4.3.33 REVIEW LEFT ON THE i1iO TABLE BETA (2026-11-13).

1. The aiming crosses became an option in 4.3.33, but three texts still said
   every i1iO chart has "three numbered aiming marks in the corners": the
   Instrument (i) bullet, the Beta option's (i) and every greyed control's
   tooltip. Each now says the crosses are the default and can be switched off,
   and what is aimed at without them.
2. The Measure log said "using Argyll's default strip recognition" for an
   i1iO chart, a reading that does not happen: Start says measuring with the
   table is not available yet. With i1iO support on the line names the chart
   instrument only; off, it is 4.3.33's line, word for word.
3. A closure over the Create Chart tab was parked in a QTimer
   (`_remember_fd9_off_screen`, the i1iO branch). It is a bound method now
   (CLAUDE.md: never a self-capturing closure as a Qt callback).
"""
from __future__ import annotations

import ast
import inspect
import os
import textwrap

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def i1io(request):
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(getattr(request, "param", True))
    try:
        yield
    finally:
        support._latched = before


# ---- 1. the texts -----------------------------------------------------------

def _texts():
    from ui.dialogs.layout_options_panel import i1io_greyed_reason
    from ui.dialogs.settings_dialog import i1io_support_help
    from ui.tabs.tab_chart import i1io_instrument_bullet
    return {"bullet": i1io_instrument_bullet(),
            "beta": i1io_support_help(),
            "greyed": i1io_greyed_reason(),
            "greyed with a reason": i1io_greyed_reason("scale")}


@pytest.mark.parametrize("which", ["bullet", "beta", "greyed",
                                   "greyed with a reason"])
def test_no_text_says_every_i1io_chart_has_aiming_marks(which):
    text = _texts()[which]
    assert "aiming marks" not in text, which
    assert "aiming crosses" in text, which
    # ... and that they are an option, with what is aimed at instead
    assert "switch" in text and "corner patches" in text, which


def test_the_bullet_keeps_every_part_it_had():
    from ui.tabs.tab_chart import (i1io_instrument_bullet,
                                   i1io_instrument_bullet_manual,
                                   i1io_instrument_bullet_rest,
                                   i1io_instrument_bullet_sheet)
    whole = i1io_instrument_bullet()
    assert whole == " ".join((i1io_instrument_bullet_sheet(),
                              i1io_instrument_bullet_manual(),
                              i1io_instrument_bullet_rest()))
    assert whole.startswith("  •  i1iO 2 + i1Pro 2 (X-Rite)")
    assert "Preferences → Beta" in whole


def test_the_greyed_tooltip_is_its_two_halves():
    from ui.dialogs.layout_options_panel import (i1io_greyed_reason,
                                                 i1io_layout_summary,
                                                 i1io_settable_summary)
    assert i1io_greyed_reason() == (i1io_layout_summary() + "\n\n"
                                    + i1io_settable_summary())


# ---- 2. the Measure log -----------------------------------------------------

def _chart(tmp_path, name):
    ti2 = tmp_path / "iochart.ti2"
    ti2.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        f'TARGET_INSTRUMENT "{name}"\nCOLOR_REP "RGB"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100 95 100 108\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(
        ti2.read_text(encoding="utf-8").replace("CTI2", "CTI1", 1),
        encoding="utf-8")
    return ti2


@pytest.fixture
def measure_tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()
    t.deleteLater()


def _instrument_line(tab) -> str:
    lines = [ln for ln in tab._log.toPlainText().splitlines()
             if ln.startswith("Chart instrument:")]
    assert lines, tab._log.toPlainText()
    return lines[-1]


def test_an_i1io_chart_gets_no_strip_recognition_line(i1io, measure_tab,
                                                      tmp_path):
    measure_tab.set_ti1_path(_chart(tmp_path, "X-Rite i1iO")
                             .with_suffix(".ti1"))
    measure_tab._refresh_bidir_autodetect()
    assert _instrument_line(measure_tab) == "Chart instrument: X-Rite i1iO."


@pytest.mark.parametrize("i1io", [False], indirect=True)
def test_with_the_beta_off_the_line_is_4333s(i1io, measure_tab, tmp_path,
                                             monkeypatch):
    import workflow.i1io.support as sup

    def asked(*_a, **_k):
        raise AssertionError("the name was judged for the i1iO while off")

    monkeypatch.setattr(sup, "is_i1io_instrument_name", asked)
    measure_tab.set_ti1_path(_chart(tmp_path, "X-Rite i1iO")
                             .with_suffix(".ti1"))
    measure_tab._refresh_bidir_autodetect()
    assert _instrument_line(measure_tab) == (
        "Chart instrument: X-Rite i1iO → using Argyll's default strip "
        "recognition.")


def test_an_i1pro_chart_keeps_its_line(i1io, measure_tab, tmp_path):
    measure_tab.set_ti1_path(_chart(tmp_path, "GretagMacbeth i1 Pro")
                             .with_suffix(".ti1"))
    measure_tab._refresh_bidir_autodetect()
    line = _instrument_line(measure_tab)
    assert "→" in line and "-b)" in line, line


# ---- 3. no closure over the tab in a timer ----------------------------------

def test_the_off_screen_snapshot_is_retaken_by_a_bound_method():
    from ui.tabs.tab_chart import TabChart
    src = textwrap.dedent(inspect.getsource(
        TabChart._remember_fd9_off_screen))
    fn = ast.parse(src).body[0]
    nested = [n.name for n in ast.walk(fn)
              if isinstance(n, (ast.FunctionDef, ast.Lambda))
              and n is not fn and hasattr(n, "name")]
    lambdas = [n for n in ast.walk(fn) if isinstance(n, ast.Lambda)]
    assert not nested and not lambdas
    assert "QTimer.singleShot(0, self._i1io_off_screen_settled)" in src


class _Snap:
    def __init__(self, own=False):
        self.own = own


def test_the_settle_retakes_only_an_untouched_target(qapp, monkeypatch):
    from ui.tabs.tab_chart import TabChart
    import workflow.i1io.support as sup
    import workflow.per_target_settings as pts

    class Stand(TabChart):
        def __init__(self):     # no widgets: only the two methods matter
            pass

        def _collect_ui_state(self):
            return {"ui": 1}

    tab = Stand()
    made = []
    monkeypatch.setattr(sup, "off_snapshot",
                        lambda *a: made.append(a) or _Snap())
    monkeypatch.setattr(pts, "snapshot", lambda _tab: {"params": 1})
    tab._fd9_off_screens()["kept"] = _Snap(own=False)
    tab._fd9_off_screens()["written"] = _Snap(own=True)
    tab._i1io_off_screen_pending().update(
        {"kept": ("P", "U"), "written": ("P2", "U2"), "gone": ("P3", "U3")})
    tab._i1io_off_screen_settled()
    assert made == [({"params": 1}, {"ui": 1}, "P", "U")]
    assert tab._i1io_off_screen_pending() == {}
    # a second queued call finds nothing to do
    tab._i1io_off_screen_settled()
    assert len(made) == 1
