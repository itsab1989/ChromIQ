"""4.3.40, F2: an i1iSis chart is measured in i1Profiler and imported;
ChromIQ never reads it. The Measure tab still showed "Scan each strip with
a slow, steady motion." under "Keep calm!", and its log said "Chart
instrument: X-Rite i1iSis → using Argyll's default strip recognition."

The i1iO table chart (also measured in i1Profiler) had the log line right
since 4.3.33 but the same advice line. Both are now treated alike: the
instrument line names the chart's instrument and nothing more, the advice
line is hidden; every other chart keeps both. With each Beta off nothing
changes.
"""
from __future__ import annotations

import pytest


@pytest.fixture
def betas(request):
    from workflow.i1io import support as io
    from workflow.isis import support as isis
    before = (io._latched, isis._latched)
    on = getattr(request, "param", True)
    io.set_enabled_for_this_process(on)
    isis.set_enabled_for_this_process(on)
    try:
        yield on
    finally:
        io._latched, isis._latched = before


def _chart(tmp_path, name):
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(
        "CTI2\n\nDESCRIPTOR \"t\"\n"
        f"TARGET_INSTRUMENT \"{name}\"\n"
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100 95 100 108\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(
        ti2.read_text(encoding="utf-8").replace("CTI2", "CTI1", 1),
        encoding="utf-8")
    return ti2.with_suffix(".ti1")


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


def _advice_shown(tab) -> bool:
    # isVisibleTo: the tab itself is never shown in the suite
    return tab._calm_subtext.isVisibleTo(tab._calm_subtext.parentWidget())


@pytest.mark.parametrize("name", ["X-Rite i1iSis", "X-Rite i1iO"])
def test_a_chart_measured_in_i1profiler_gets_neither(betas, measure_tab,
                                                     tmp_path, name):
    measure_tab.set_ti1_path(_chart(tmp_path, name))
    assert _instrument_line(measure_tab) == f"Chart instrument: {name}."
    assert "strip recognition" not in measure_tab._log.toPlainText()
    assert not _advice_shown(measure_tab)


def test_the_advice_comes_back_with_a_strip_chart(betas, measure_tab,
                                                  tmp_path):
    measure_tab.set_ti1_path(_chart(tmp_path, "X-Rite i1iSis"))
    assert not _advice_shown(measure_tab)
    other = tmp_path / "pro"
    other.mkdir()
    measure_tab.set_ti1_path(_chart(other, "GretagMacbeth i1 Pro"))
    assert _advice_shown(measure_tab)
    assert measure_tab._calm_subtext.text() == \
        "Scan each strip with a slow, steady motion."
    line = _instrument_line(measure_tab)
    assert "→" in line and "-b)" in line, line


@pytest.mark.parametrize("betas", [False], indirect=True)
@pytest.mark.parametrize("name", ["X-Rite i1iSis", "X-Rite i1iO"])
def test_with_the_betas_off_the_tab_reads_as_4339s(betas, measure_tab,
                                                   tmp_path, name):
    measure_tab.set_ti1_path(_chart(tmp_path, name))
    assert _instrument_line(measure_tab) == (
        f"Chart instrument: {name} → using Argyll's default strip "
        "recognition.")
    assert _advice_shown(measure_tab)


# ---- every instrument: the strip-recognition clause only where it applies --
#
# 4.3.40 review: a CR30 chart's log said "→ using Argyll's default strip
# recognition" although the CR30 is set down on each patch by hand. The
# clause is now logged only for an instrument the registry
# (`instruments.FINDS_PATCHES_BY_EDGES`) says finds its patches by colour
# edges along a strip. The Beta instruments follow their own switch: off,
# their line is 4.3.39's.

@pytest.fixture
def every_beta(request):
    from workflow.fd9 import support as fd9
    from workflow.i1io import support as io
    from workflow.isis import support as isis
    from workflow.barbieri import support as barbieri
    mods = (fd9, io, isis, barbieri)
    before = [m._latched for m in mods]
    on = getattr(request, "param", True)
    for m in mods:
        m.set_enabled_for_this_process(on)
    try:
        yield on
    finally:
        for m, b in zip(mods, before):
            m._latched = b


def _all_keys():
    from workflow.layout_engine.instruments import TARGET_INSTRUMENT_NAME
    return sorted(TARGET_INSTRUMENT_NAME)


@pytest.mark.parametrize("every_beta", [True, False], indirect=True)
@pytest.mark.parametrize("key", _all_keys())
def test_every_instrument_gets_the_strip_clause_only_where_it_applies(
        every_beta, measure_tab, tmp_path, key):
    from workflow.layout_engine.instruments import (
        FINDS_PATCHES_BY_EDGES, TARGET_INSTRUMENT_NAME, finds_patches_by_edges)
    assert key in FINDS_PATCHES_BY_EDGES, f"{key} is not classified"
    name = TARGET_INSTRUMENT_NAME[key]
    measure_tab.set_ti1_path(_chart(tmp_path, name))
    line = _instrument_line(measure_tab)
    beta_key = key in ("FD9", "IO2", "XRISIS", "B100XY")
    if beta_key and not every_beta:
        # the Beta off: exactly 4.3.39's line
        assert "→ using Argyll's default strip recognition." in line, line
        return
    clause = "→" in line
    assert clause == finds_patches_by_edges(key), (key, line)
    if not clause:
        assert line.startswith("Chart instrument: ") and line.endswith(".")
        assert "strip recognition" not in line
