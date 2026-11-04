"""The Konica Minolta FD-9 as a Beta (PR #213, written and contributed by
lessbones), with the option ON: the review's findings, one test each.

* H2: a chart that is not UTF-8 never breaks the Measure tab, and the
  "is this an FD-9 chart?" answer is cached.
* H3: entering or leaving an FD-9 chart never lifts the lock of a running
  read, and gives back exactly what it greyed.
* M5 / M6: "FD-9" in the lists; the full name in the files, the old spelling
  still read; the header every engine chart has.
* The profile: colprof builds one from an FD-9 .ti3 written by the FD-9's own
  writer (RGB and CMYK).
* Landscape sheets inside the FD-9's envelope, and the compression honoured.
* M8: the session retention rule.
* M4: every fault is put into the right M-FD9-* window; the driver's progress
  is said in the user's words.
* M9: the patch set editor refuses an FD-9 chart and says why.
* The Preferences > Beta row credits the contributor.
"""
from __future__ import annotations


import os
import subprocess
from pathlib import Path

import pytest

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _ti1(tmp_path, rep, tokens, values, name="source.ti1"):
    fields = [rep + "_" + t for t in tokens]
    text = ["CTI1", f'COLOR_REP "{rep}"', f"NUMBER_OF_FIELDS {1 + len(fields)}",
            "BEGIN_DATA_FORMAT", "SAMPLE_ID " + " ".join(fields),
            "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(values)}", "BEGIN_DATA"]
    text += [str(i + 1) + " " + " ".join(f"{v:g}" for v in row)
             for i, row in enumerate(values)]
    text += ["END_DATA", ""]
    p = tmp_path / name
    p.write_text("\n".join(text), encoding="utf-8")
    return p


# ---- H2 --------------------------------------------------------------------
def test_a_cp1252_chart_is_simply_not_an_fd9_chart(tmp_path):
    from workflow.fd9.measurement import is_fd9_chart
    ti2 = tmp_path / "german.ti2"
    ti2.write_bytes(
        'CTI2\nDESCRIPTOR "Prüfdruck Müller"\n'
        'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n'.encode("cp1252"))
    assert is_fd9_chart(ti2) is False
    assert is_fd9_chart(tmp_path / "missing.ti2") is False


@pytest.mark.parametrize("name", ["FD-9", "Konica Minolta FD-9"])
def test_both_spellings_are_fd9_charts_and_the_answer_is_cached(
        tmp_path, name, monkeypatch):
    from workflow.fd9 import measurement as fm
    ti2 = tmp_path / "c.ti2"
    ti2.write_bytes(f'CTI2\r\nDESCRIPTOR "Prüf"\r\nTARGET_INSTRUMENT "{name}"\r\n'
                    .encode("cp1252"))
    assert fm.is_fd9_chart(ti2) is True
    opened = []
    import builtins
    real = builtins.open

    def counting(file, *a, **k):
        opened.append(file)
        return real(file, *a, **k)

    monkeypatch.setattr(builtins, "open", counting)
    assert fm.is_fd9_chart(ti2) is True
    assert opened == [], "the second answer must come from the cache"


# ---- H3 --------------------------------------------------------------------
@pytest.fixture
def tab(qapp, tmp_path):
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


@pytest.fixture
def fd9_chart(tmp_path):
    from workflow.fd9.chart import build_chart
    src = _ti1(tmp_path, "RGB", ("R", "G", "B"),
               [[i * 10 % 101, i * 20 % 101, i * 30 % 101] for i in range(24)])
    res = build_chart(src, tmp_path / "fd9chart", paper="A4", dpi=100, seed=7)
    return res.ti2_path


def _plain_chart(tmp_path):
    ti2 = tmp_path / "plain.ti2"
    ti2.write_text('CTI2\nTARGET_INSTRUMENT "GretagMacbeth i1 Pro"\n'
                   'COLOR_REP "RGB"\nNUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\n'
                   'SAMPLE_ID SAMPLE_LOC\nEND_DATA_FORMAT\nNUMBER_OF_SETS 1\n'
                   'BEGIN_DATA\n1 A1\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text("CTI1\n", encoding="utf-8")
    return ti2


def _options(tab):
    return (tab._g_options.isEnabled(), tab._m_options.isEnabled(),
            tab._save_defaults_btn.isEnabled())


def test_a_chart_change_mid_read_never_unlocks_the_options(tab, fd9_chart,
                                                           tmp_path):
    plain = _plain_chart(tmp_path)
    tab.set_ti1_path(plain.with_suffix(".ti1"))
    assert _options(tab) == (True, True, True)
    tab._set_settings_enabled(False)              # a read is running
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert _options(tab) == (False, False, False)
    tab.set_ti1_path(plain.with_suffix(".ti1"))   # leaving the FD-9 chart
    assert _options(tab) == (False, False, False), (
        "leaving an FD-9 chart lifted the lock of the running read (H3)")
    tab._set_settings_enabled(True)               # the read ended
    assert _options(tab) == (True, True, True)


def test_clearing_the_chart_leaves_the_fd9_state(tab, fd9_chart):
    """Found on screen: opening another project cleared the Measure tab's
    chart through `clear_chart_file`, and the FD-9 row and the greyed
    options stayed for a tab with no chart at all."""
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert tab._fd9_shown and not tab._fd9_panel.isHidden()
    tab.clear_chart_file()
    assert not tab._fd9_shown and tab._fd9_panel.isHidden()
    assert _options(tab) == (True, True, True)


def test_a_normal_chart_after_an_fd9_chart_gets_its_preview_back(
        tab, fd9_chart, tmp_path):
    """Found on screen: the swipe arrow stayed off for the next chart."""
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert tab._preview._no_swipe is True
    assert tab._preview._notice_lbl.text() in tab._fd9_notices()
    tab.set_ti1_path(_plain_chart(tmp_path).with_suffix(".ti1"))
    assert tab._preview._no_swipe is False
    assert tab._preview._notice_lbl.text() not in tab._fd9_notices()


def test_an_fd9_chart_keeps_its_options_greyed_after_a_read_ends(tab,
                                                                 fd9_chart):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert not tab._fd9_panel.isHidden()
    assert _options(tab) == (False, False, False)
    tab._set_settings_enabled(False)
    tab._set_settings_enabled(True)
    assert _options(tab) == (False, False, False), (
        "Patch by patch and the other chartread options must stay greyed "
        "for an FD-9 chart")
    assert tab._preview._no_swipe is True


def test_the_fd9_keys_are_stored_for_an_fd9_chart_only(tab, fd9_chart,
                                                       tmp_path):
    from workflow.measure_settings import FD9_CONTROLS, snapshot
    tab.set_ti1_path(_plain_chart(tmp_path).with_suffix(".ti1"))
    assert not set(FD9_CONTROLS) & set(snapshot(tab))
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    assert set(FD9_CONTROLS) <= set(snapshot(tab))


def test_the_preview_lights_rows_not_columns(tab, fd9_chart):
    from workflow.fd9.measurement import checked_chart
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    _, layout, _ = checked_chart(fd9_chart)
    strips = tab._page_stripe_rects[0]
    assert len(strips) == len(layout["rows"])
    assert all(r.width() > r.height() for r in strips)


# ---- M5 / M6 ---------------------------------------------------------------
def test_the_lists_say_fd9(qapp):
    from data.patch_db import INSTRUMENT_LABELS
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    assert INSTRUMENT_LABELS["FD9"] == "FD-9"
    assert dict(LayoutOptionsPanel.instruments())["FD9"] == "FD-9"
    import yaml
    from core.resource_path import resource_path
    with open(resource_path("data/parameters.yaml"), encoding="utf-8") as f:
        params = yaml.safe_load(f)["parameters"]["printtarg"]
    i = next(p for p in params if p["flag"] == "-i")
    assert i["labels"][i["choices"].index("FD9")] == "FD-9"


def test_the_chart_header_is_an_engine_charts(fd9_chart):
    from workflow.fd9.measurement import checked_chart
    text = fd9_chart.read_text(encoding="utf-8")
    for line in ('DESCRIPTOR "Argyll Calibration Target chart information 2"',
                 'TARGET_INSTRUMENT "Konica Minolta FD-9"',
                 "CREATED ", "APPROX_WHITE_POINT "):
        assert line in text, line
    assert '\n1 "' in text, "SAMPLE_LOC is quoted, as in every engine chart"
    checked_chart(fd9_chart)
    from ui.ti2_loader import read_target_instrument
    assert read_target_instrument(fd9_chart) == "Konica Minolta FD-9"
    from workflow.ti2_relayout import instrument_to_flag
    assert instrument_to_flag("Konica Minolta FD-9") == "FD9"
    assert instrument_to_flag("FD-9") == "FD9"


def test_a_chart_with_the_old_spelling_still_measures(fd9_chart):
    from workflow.fd9.measurement import checked_chart, is_fd9_chart
    text = fd9_chart.read_text(encoding="utf-8").replace(
        'TARGET_INSTRUMENT "Konica Minolta FD-9"', 'TARGET_INSTRUMENT "FD-9"')
    fd9_chart.write_text(text, encoding="utf-8")
    assert is_fd9_chart(fd9_chart)
    checked_chart(fd9_chart)


# ---- the profile -------------------------------------------------------------
def _colprof():
    import shutil
    from tests.argyll_env import argyll_tool
    tool = argyll_tool("colprof") or shutil.which("colprof")
    if not tool:
        pytest.skip("ArgyllCMS colprof not installed")
    return tool


class _Sample:
    def __init__(self, values):
        self.values = values

    def for_condition(self, _condition):
        return self


def _spectrum(rep, dev):
    """A smooth, plausible reflectance for the device values (fractions)."""
    import numpy as np
    lam = np.arange(380, 731, 10, dtype=float)

    def bump(c, w):
        return np.exp(-((lam - c) / w) ** 2)

    if rep == "RGB":
        r, g, b = (v / 100 for v in dev)
        refl = 0.03 + 0.9 * (r * bump(640, 60) + g * bump(540, 45)
                             + b * bump(450, 40)) / 1.2
    else:
        c, m, y, k = (v / 100 for v in dev)
        refl = (0.9 * (1 - 0.85 * c * bump(620, 70))
                * (1 - 0.85 * m * bump(540, 50))
                * (1 - 0.85 * y * bump(440, 45)) * (1 - 0.92 * k) + 0.02)
    return list(np.clip(refl, 0.01, 0.98))


@pytest.mark.parametrize("rep,tokens,steps", [
    ("RGB", ("R", "G", "B"), 6), ("CMYK", ("C", "M", "Y", "K"), 4)])
def test_colprof_builds_a_profile_from_an_fd9_measurement(
        tmp_path, monkeypatch, rep, tokens, steps):
    import itertools
    tool = _colprof()
    from workflow.fd9 import native_evidence
    from workflow.fd9.chart import build_chart
    from workflow.fd9.measurement import checked_chart, stamp_locations
    from workflow.fd9.native_export import export_native

    grid = [100 * i / (steps - 1) for i in range(steps)]
    values = [list(v) for v in itertools.product(grid, repeat=len(tokens))]
    src = _ti1(tmp_path, rep, tokens, values)
    res = build_chart(src, tmp_path / "chart" / "fd9", paper="A3",
                      patch_mm=6, gap_mm=0.5, dpi=100, seed=3)
    chart = res.ti2_path
    layout_path, layout, locations = checked_chart(chart)
    patches = [p for row in layout["rows"] for p in row]
    session = tmp_path / "session"
    session.mkdir()
    (session / "progress.json").write_text("{}", encoding="utf-8")
    evidence = {
        "layout": layout, "patches": patches,
        "samples": [_Sample(_spectrum(rep, p["device_values"])) for p in patches],
        "factory_sections_sha256": "0" * 64,
        "manifest": {"host": "synthetic"},
        "acquisition_complete": True,
        "row_indices": list(range(len(layout["rows"]))),
    }
    monkeypatch.setattr(native_evidence, "verified_native_rows",
                        lambda *a, **k: evidence)
    raw = session / "M1-factory.ti3"
    export_native(None, session, layout_path, raw, "M1")
    out = tmp_path / "prof"
    out.mkdir()
    ti3 = out / "fd9.ti3"
    stamp_locations(raw, ti3, locations, session, chart=chart)
    text = ti3.read_text(encoding="utf-8")
    assert 'TARGET_INSTRUMENT "Konica Minolta FD-9"' in text
    assert "CREATED " in text and 'MEASUREMENT_CONDITION "M1"' in text
    args = [tool, "-v0", "-qf", "-D", "FD-9 synthetic"]
    if rep == "CMYK":
        args += ["-kr", "-l300"]
    try:
        r = subprocess.run(args + ["fd9"], cwd=str(out), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=600)
    except subprocess.TimeoutExpired:
        pytest.fail("colprof did not finish within 600 s")
    assert r.returncode == 0, r.stderr[-2000:] + r.stdout[-2000:]
    assert (out / "fd9.icc").stat().st_size > 1000


# ---- landscape, compression --------------------------------------------------
@pytest.mark.parametrize("paper,size_mm", [("A4R", (297.0, 210.0)),
                                           ("LetterR", (279.4, 215.9))])
def test_landscape_sheets_are_offered_and_laid_out(tmp_path, paper, size_mm):
    import tifffile
    from workflow.fd9.chart import (MAX_HEIGHT, MAX_WIDTH, MIN_HEIGHT,
                                    MIN_WIDTH, PAPERS, build_chart, capacity,
                                    dimensions)
    from workflow.fd9.measurement import checked_chart
    assert paper in PAPERS
    w, h = dimensions(paper)
    assert (w, h) == size_mm
    assert MIN_WIDTH <= w <= MAX_WIDTH and MIN_HEIGHT <= h <= MAX_HEIGHT
    n = capacity(paper)
    src = _ti1(tmp_path, "RGB", ("R", "G", "B"),
               [[i % 101, (i * 7) % 101, (i * 13) % 101] for i in range(n)])
    res = build_chart(src, tmp_path / "land", paper=paper, dpi=100, seed=1)
    _, layout, _ = checked_chart(res.ti2_path)
    assert sum(len(r) for r in layout["rows"]) == n
    assert layout["paper_mm"] == [w, h]
    for x, y in layout["fiducials_mm"]:
        assert 0 < x < w and 0 < y < h
    for row in layout["rows"]:
        for p in row:
            x, y = p["centre_mm"]
            assert 15 <= x <= w - 15 and y <= h - 33
    with tifffile.TiffFile(str(res.tiff_paths[0])) as tif:
        page = tif.pages[0]
        assert (page.imagewidth, page.imagelength) == (
            round(w * 100 / 25.4), round(h * 100 / 25.4))


@pytest.mark.parametrize("compression,tag", [("lzw", 5), ("zlib", 8),
                                             ("none", 1)])
def test_the_compression_choice_is_honoured(tmp_path, compression, tag):
    import tifffile
    from workflow.fd9.chart import build_chart
    src = _ti1(tmp_path, "RGB", ("R", "G", "B"), [[0, 0, 0], [100, 100, 100]])
    res = build_chart(src, tmp_path / "c", paper="137x300", dpi=72,
                      compression=compression)
    with tifffile.TiffFile(str(res.tiff_paths[0])) as tif:
        assert int(tif.pages[0].compression) == tag


# ---- M8 ----------------------------------------------------------------------
def test_sessions_keep_what_filed_or_can_resume_and_the_newest_failure(tmp_path):
    import time
    from core.file_manager import Run
    from workflow.fd9.sessions import (mark_filed, preview_cache_dir,
                                       prune_sessions, sessions_dir)
    chart = tmp_path / "run1" / "x.ti2"
    chart.parent.mkdir()
    chart.write_text("CTI2\n", encoding="utf-8")
    root = sessions_dir(chart)
    assert root == Run.for_dir(chart.parent).fd9_sessions_dir
    assert root == chart.parent / "fd9-sessions"
    vchart = tmp_path / "run1" / "verifications" / "x-verify.ti2"
    assert preview_cache_dir(vchart) == tmp_path / "run1" / "cache"

    def make(name):
        d = root / name
        d.mkdir(parents=True)
        (d / "progress.json").write_text("{}", encoding="utf-8")
        time.sleep(0.02)
        return d

    filed = make("filed1")
    mark_filed(filed)
    named = make("named1")
    chart.with_suffix(".ti3").write_text(
        'CTI3\nFD9_SOURCE_SESSIONS "named1"\nBEGIN_DATA_FORMAT\n',
        encoding="utf-8")
    old_named = make("oldnamed")
    (chart.parent / "old" / "2026").mkdir(parents=True)
    (chart.parent / "old" / "2026" / "x.ti3").write_text(
        'CTI3\nCHROMIQ_FD9_SESSION "oldnamed"\n', encoding="utf-8")
    pending = make("pending1")
    failed_old = make("failed1")
    failed_new = make("failed2")
    removed = prune_sessions(chart, keep={"pending1"})
    assert removed == [failed_old]
    for kept in (filed, named, old_named, pending, failed_new):
        assert kept.is_dir(), kept.name


# ---- M4 ----------------------------------------------------------------------
@pytest.mark.parametrize("message,expected", [
    ("Capture failed; evidence preserved: Unsupported sensor model version; "
     "expected 1.0.0.2", "M-FD9-WRONG-FIRMWARE"),
    ("Capture failed; evidence preserved: Expected exactly four isolated "
     "square marks, found 2", "M-FD9-MARKS-NOT-FOUND"),
    ("Capture failed; evidence preserved: timed out", "M-FD9-NO-CONNECTION"),
    ("Capture failed; evidence preserved: [Errno 61] Connection refused",
     "M-FD9-NO-CONNECTION"),
    ("Resume requires the same chart, condition, conversion source and colour "
     "data", "M-FD9-RESUME-REFUSED"),
    ("Only a consistent partial measurement can resume",
     "M-FD9-RESUME-REFUSED"),
    ("Colour data changed during native measurement", "M-FD9-FAILED"),
])
def test_every_fault_gets_the_window_that_explains_it(tab, fd9_windows,
                                                      message, expected):
    tab._settings.set("fd9_host", "10.0.0.9")
    tab._fd9_explain_error(message)
    assert [w[0] for w in fd9_windows] == [expected]


def test_a_stop_with_the_sheet_inside_says_so_and_one_before_does_not(
        tab, fd9_windows):
    tab._fd9_sheet_in = False
    tab._fd9_explain_error("Operator stopped the FD9 session", cancelled=True)
    assert fd9_windows == []
    tab._fd9_sheet_in = True
    tab._fd9_explain_error("Operator stopped the FD9 session", cancelled=True)
    assert [w[0] for w in fd9_windows] == ["M-FD9-SHEET-STILL-INSIDE"]


def test_the_insert_window_opens_and_closes_with_the_drivers_progress(
        tab, fd9_windows, fd9_chart):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    lines = []
    tab._fd9_log = lines.append
    tab._fd9_progress("FD9 insertion screen ready. Insert chart arrow first, "
                      "printed face up.")
    assert [w[0] for w in fd9_windows] == ["M-FD9-INSERT-SHEET"]
    tab._fd9_progress("Sheet detected. Starting pre-scan.")
    assert tab._fd9_sheet_in is True
    tab._fd9_progress("FD9 measurement: 12/36 patches")
    tab._fd9_progress("Measurement complete. Remove the ejected sheet fully "
                      "past the paper sensor before starting another FD-9 "
                      "measurement.")
    assert tab._fd9_sheet_in is False
    assert lines[2] == "FD-9: 12 of 36 patches measured."
    assert not any(line.startswith(("FD9 insertion", "Sheet detected"))
                   for line in lines), "the driver's English reached the log"


def test_no_address_is_asked_for_before_anything_starts(tab, fd9_windows,
                                                        fd9_chart, monkeypatch):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._settings.set("fd9_host", "")
    monkeypatch.setattr(tab, "_blocked_by_new_run", lambda: False)
    tab._on_start()
    assert [w[0] for w in fd9_windows] == ["M-FD9-NO-ADDRESS"]
    assert not tab._fd9_live and tab._fd9_job is None


def test_the_start_runs_the_preflight_every_instrument_gets(
        tab, fd9_chart, monkeypatch):
    """H4: W6, the verification guard and §5 are asked for the FD-9 too."""
    asked = []
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._settings.set("fd9_host", "10.0.0.9")
    monkeypatch.setattr(tab, "_blocked_by_new_run", lambda: False)
    monkeypatch.setattr(tab, "_recover_engine_autosave",
                        lambda: asked.append("M3"))
    monkeypatch.setattr(tab, "_blocked_by_a_misfitting_measurement",
                        lambda params=None: asked.append("W6") or False)
    monkeypatch.setattr(tab, "_verification_guard",
                        lambda: asked.append("verification") or None)
    monkeypatch.setattr(tab, "_confirm_replacing_measurement",
                        lambda: asked.append("§5") or False)
    tab._on_start()
    assert asked == ["M3", "W6", "verification", "§5"]
    assert not tab._fd9_live, "declining §5 starts nothing"


# ---- M9 ----------------------------------------------------------------------
# 4.3.25 (F10): the patch set editor opens FD-9 charts; its refusal is gone
# (tests/test_fd9_4325_editor.py).


# ---- Preferences > Beta ------------------------------------------------------
def test_the_beta_row_credits_lessbones_and_says_restart(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    from ui.tooltip_button import TooltipButton
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        box = dlg._fd9_support_check
        assert box.isChecked() is False        # the stored default
        tips = [b for b in dlg.findChildren(TooltipButton)
                if b._title == "Konica Minolta FD-9 support (beta)"]
        assert len(tips) == 1
        body = tips[0]._body
        for needed in ("written and contributed by lessbones", "Ethernet",
                       "Konica Minolta software", "several numbered sheets",
                       "6 to 30 mm", "137 to 330 mm", "170 to 660 mm",
                       "1.0.0.2", "one FD-9, on macOS", "arrow first",
                       "printed side", "turned", "nothing changes",
                       "next time you start ChromIQ"):
            assert needed in body, needed
        assert "\u2014" not in body, "no em dash in user-facing text"
        # This run has FD-9 on (fixture); unticking differs → restart note.
        assert dlg._fd9_support_restart_hint.isHidden() is False
        box.setChecked(True)
        assert dlg._fd9_support_restart_hint.isHidden() is True
    finally:
        dlg.deleteLater()


def test_the_layout_panel_greys_only_what_the_fd9_ignores(qapp):
    """Output, Printer calibration and Randomisation are honoured for the
    FD-9 and stay live; the geometry controls are greyed with the reason and
    come back exactly as they were (found on screen: the first cut greyed
    everything, because those groups sit inside Basic / Expert Options)."""
    from ui.dialogs.layout_options_panel import (LayoutOptionsPanel,
                                                 fd9_greyed_reason)
    p = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    try:
        margin = next(iter(p.margins.values()))
        tip_before = margin.toolTip()
        p.instr.setCurrentIndex(p.instr.findData("FD9"))
        p._sync_instrument_widgets("FD9")
        for live in (p.compression, p.bit_depth, p.export_pdf,
                     p.randomize_cb, p.dpi):
            assert live.isEnabled(), live
        assert p.dpi.maximum() == 600
        assert not margin.isEnabled()
        assert margin.toolTip() == fd9_greyed_reason()
        p.instr.setCurrentIndex(p.instr.findData("i1"))
        p._sync_instrument_widgets("i1")
        assert margin.isEnabled() and margin.toolTip() == tip_before
        assert p.dpi.maximum() == 1200
    finally:
        p.deleteLater()
