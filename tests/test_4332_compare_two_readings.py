"""4.3.32, feature A (jctay, forum 2026-11-10; Basti 2026-11-11 "do both"):
Tools > Inspect a measurement compares the measurement with ANOTHER READING
OF THE SAME CHART.

Pinned here:
* the pairing is checked before any number is shown (the 4.3.30 rule of
  Verify against reference): patch count, patch numbers, device values
  within PATCH_IDENTITY_TOL; a file of another chart is refused with
  M-READINGS-NOT-SAME-CHART, never compared patch by wrong patch;
* two files of the same chart in different orders (another i1Profiler grid,
  the turned order) are paired by their device values, and only where each
  value names one patch; repeated values are left out and said to be;
* an i1Profiler .mxf is read directly, in the measurement's condition;
* the statistics, the tolerance (presets and custom), the worst patches with
  their strip and place, the per-strip summary that names a whole strip off;
* nothing is written: both files are byte for byte as before;
* the window shows it in both modes and the saved inspection carries it.

Fixtures are made from the suite's own ET-8550 verification reading
(`tests/data/g_basti_et8550_run1_verify`), never from a tester's file.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                  # noqa: E402
from workflow.reading_compare import (                          # noqa: E402
    MAX_LEFT_OUT_SHARE, ReadingsNotComparable, compare, load_reading,
    pair_readings)

SRC = (Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
       / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")


def _table(text: str):
    lines = text.splitlines()
    f0 = lines.index("BEGIN_DATA_FORMAT")
    fields = lines[f0 + 1].split()
    d0 = next(i for i in range(f0, len(lines)) if lines[i].strip() == "BEGIN_DATA")
    d1 = next(i for i in range(d0, len(lines)) if lines[i].strip() == "END_DATA")
    return lines, fields, d0, d1


def _write(out: Path, edit_rows) -> Path:
    """A copy of SRC (XYZ columns only, spectra dropped) with its data rows
    passed through *edit_rows(rows, fields) -> rows* (rows: lists of tokens)."""
    lines, fields, d0, d1 = _table(SRC.read_text(encoding="utf-8"))
    keep = [i for i, f in enumerate(fields) if not f.startswith("SPEC_")]
    rows = [[ln.split()[i] for i in keep] for ln in lines[d0 + 1:d1]]
    kf = [fields[i] for i in keep]
    rows = edit_rows(rows, kf)
    head = [ln for ln in lines[:lines.index("BEGIN_DATA_FORMAT")]
            if not ln.startswith(("NUMBER_OF_FIELDS", "SPECTRAL_"))]
    body = head + [f"NUMBER_OF_FIELDS {len(kf)}", "BEGIN_DATA_FORMAT",
                   " ".join(kf), "END_DATA_FORMAT", "",
                   f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA",
                   *[" ".join(r) for r in rows], "END_DATA", ""]
    out.write_text("\n".join(body), encoding="utf-8")
    return out


def _same(rows, fields):
    return rows


def _noisy(seed=7, bad=(), bad_scale=1.15, strip=None):
    """Instrument-like noise (about 0.3 %) on XYZ, *bad* row indexes off by
    *bad_scale*, and every patch of *strip* (a SAMPLE_LOC prefix) off too."""
    def edit(rows, fields):
        rng = np.random.default_rng(seed)
        xi = [fields.index(f"XYZ_{c}") for c in "XYZ"]
        li = fields.index("SAMPLE_LOC")
        for k, r in enumerate(rows):
            g = 1 + rng.normal(0, 0.003)
            loc = r[li].strip('"')
            off = (k in bad) or (strip is not None
                                 and re.fullmatch(strip + r"\d+", loc))
            for i in xi:
                r[i] = f"{float(r[i]) * g * (bad_scale if off else 1):.6f}"
        return rows
    return edit


def _renumbered(rows, fields):
    """The same readings in another order with new patch numbers 1..N: what
    a file saved on another grid (or in the turned order) looks like."""
    rng = np.random.default_rng(3)
    order = rng.permutation(len(rows))
    out = [list(rows[i]) for i in order]
    si = fields.index("SAMPLE_ID")
    for k, r in enumerate(out):
        r[si] = str(k + 1)
    return out


def _ids_moved_on(rows, fields):
    """Patch numbers moved on by six, readings unchanged (4.3.30's case)."""
    si = fields.index("SAMPLE_ID")
    n = len(rows)
    for k, r in enumerate(rows):
        r[si] = str((k + 6) % n + 1)
    return rows


@pytest.fixture
def a(tmp_path):
    return _write(tmp_path / "a.ti3", _same)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---- the statistics ------------------------------------------------------

def test_the_same_file_twice_is_zero_everywhere(a):
    c = compare(load_reading(a), load_reading(a))
    assert c.paired_by == "id" and c.device_checked
    assert c.n == 616 and c.mean == c.worst == 0.0
    assert c.above(0.5) == [] and c.left_out == 0


def test_noise_and_four_bad_patches(a, tmp_path):
    bad = (10, 200, 300, 500)
    b = _write(tmp_path / "b.ti3", _noisy(bad=bad))
    before = (_sha(a), _sha(b))
    c = compare(load_reading(a), load_reading(b))
    assert c.paired_by == "id" and c.n == 616
    assert 0.005 < c.median < 0.5 and c.median <= c.mean <= c.p95 <= c.worst
    assert c.p95 == pytest.approx(np.percentile([p.de for p in c.patches], 95))
    worst4 = {p.sid for p in c.worst_patches(4)}
    assert worst4 == {str(k + 1) for k in bad}
    # the tolerance decides the count; equal to it is within it
    assert len(c.above(1.0)) >= 4
    assert len(c.above(c.worst)) == 0
    assert len(c.above(0.1)) > len(c.above(1.0))
    # the place as printed: strip label and position from the SAMPLE_LOC
    w = c.worst_patches(1)[0]
    assert w.strip is not None and w.position is not None
    assert w.loc == f"{w.strip}{w.position}"
    assert (_sha(a), _sha(b)) == before, "a file was written to"


def test_a_whole_strip_off_is_named(a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy(strip="H"))
    c = compare(load_reading(a), load_reading(b))
    strips = c.strips(1.0)
    assert strips[0].label == "H" and strips[0].whole_strip_off
    assert not any(s.whole_strip_off for s in strips[1:])


# ---- the pairing check ---------------------------------------------------

def test_another_order_is_paired_by_device_values(a, tmp_path):
    b = _write(tmp_path / "b.ti3", lambda r, f: _renumbered(_noisy()(r, f), f))
    c = compare(load_reading(a), load_reading(b))
    assert c.paired_by == "device"
    straight = compare(load_reading(a),
                       load_reading(_write(tmp_path / "s.ti3", _noisy())))
    # the very same pairs as the file in the chart's order
    assert c.left_out + c.n == 616
    by = {p.sid: p.de for p in straight.patches}
    for p in c.patches:
        assert p.de == pytest.approx(by[p.sid], abs=1e-9)


def _with_repeats(rows, fields):
    """Rows 2 and 3 printed with the device values of row 1 (a chart with
    three copies of one colour)."""
    di = [fields.index(f"RGB_{c}") for c in "RGB"]
    for k in (1, 2):
        for i in di:
            rows[k][i] = rows[0][i]
    return rows


def test_repeated_device_values_are_left_out_and_said(tmp_path):
    a = _write(tmp_path / "a.ti3", _with_repeats)
    b = _write(tmp_path / "b.ti3",
               lambda r, f: _renumbered(_with_repeats(r, f), f))
    c = compare(load_reading(a), load_reading(b))
    assert c.paired_by == "device" and c.left_out == 3 and c.n == 613
    assert not {"1", "2", "3"} & {p.sid for p in c.patches}


def test_too_many_repeats_are_refused(tmp_path):
    def many(rows, fields):
        di = [fields.index(f"RGB_{c}") for c in "RGB"]
        for k in range(1, int(MAX_LEFT_OUT_SHARE * len(rows)) + 2):
            for i in di:
                rows[k][i] = rows[0][i]
        return rows
    a = _write(tmp_path / "a.ti3", many)
    b = _write(tmp_path / "b.ti3", lambda r, f: _renumbered(many(r, f), f))
    with pytest.raises(ReadingsNotComparable) as e:
        compare(load_reading(a), load_reading(b))
    assert "more than one patch" in e.value.reason


def test_patch_numbers_moved_on_are_refused_or_paired_right(a, tmp_path):
    """4.3.30's measured case: compared by number this gave ΔE00 18."""
    b = _write(tmp_path / "b.ti3", _ids_moved_on)
    c = compare(load_reading(a), load_reading(b))
    assert c.paired_by == "device"
    assert c.worst == pytest.approx(0.0, abs=1e-9)


def test_another_chart_is_refused(a, tmp_path):
    def other(rows, fields):
        ri = fields.index("RGB_R")
        for r in rows:
            r[ri] = f"{min(100.0, float(r[ri]) + 7.0):.5f}"
        return rows
    b = _write(tmp_path / "b.ti3", other)
    with pytest.raises(ReadingsNotComparable) as e:
        compare(load_reading(a), load_reading(b))
    assert e.value.message is M.M_READINGS_NOT_SAME_CHART
    title, body = e.value.render("b.ti3")
    assert "b.ti3" in body and "{" not in body


def test_a_different_patch_count_is_refused(a, tmp_path):
    b = _write(tmp_path / "b.ti3", lambda r, f: r[:-10])
    with pytest.raises(ReadingsNotComparable) as e:
        compare(load_reading(a), load_reading(b))
    assert "616" in e.value.reason and "606" in e.value.reason


def test_a_file_without_colour_is_unusable(a, tmp_path):
    p = tmp_path / "chart.ti2"
    p.write_text((SRC.parent / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti2"
                  ).read_text(encoding="utf-8"), encoding="utf-8")
    text = p.read_text(encoding="utf-8")
    if "XYZ_X" in text:      # a chart may carry targen's estimates: drop them
        lines, fields, d0, d1 = _table(text)
        keep = [i for i, f in enumerate(fields) if not f.startswith("XYZ_")]
        rows = [" ".join(ln.split()[i] for i in keep)
                for ln in lines[d0 + 1:d1]]
        text = "\n".join(lines[:lines.index("BEGIN_DATA_FORMAT")] + [
            f"NUMBER_OF_FIELDS {len(keep)}", "BEGIN_DATA_FORMAT",
            " ".join(fields[i] for i in keep), "END_DATA_FORMAT",
            f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA"])
        p.write_text(text, encoding="utf-8")
    with pytest.raises(ReadingsNotComparable) as e:
        load_reading(p)
    assert e.value.message is M.M_READINGS_UNUSABLE
    with pytest.raises(ReadingsNotComparable):
        load_reading(tmp_path / "missing.ti3")


def test_no_device_values_pairs_by_number_and_says_unchecked(a, tmp_path):
    def strip_device(rows, fields):
        return rows
    b = _write(tmp_path / "b.ti3", _noisy())
    rb = load_reading(b)
    rb.device = np.empty((0, 3))
    pairs, how, checked, left = pair_readings(load_reading(a), rb)
    assert how == "id" and not checked and left == 0 and len(pairs) == 616


# ---- an i1Profiler measurement, read directly ---------------------------

def test_an_mxf_is_read_directly_in_the_measurements_condition(tmp_path):
    from tests.test_i1profiler_turned_export import _chart
    from tests.test_i1profiler_turned_grid_check import _mxf
    from workflow import i1profiler_turned as T
    from core.file_manager import exports_subdir
    from workflow.reference_convert import cxf_measurement_to_ti3
    ti2 = _chart(tmp_path / "c", "C", 120, patch_w_mm=12.0, patch_h_mm=10.0,
                 max_strip_mm=121.0)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "C")
    plan = T.plan_for(ti2)
    files = T.TurnedFiles(exports_subdir(ti2.parent), "C")
    mxf = _mxf(files.txf("i1Pro 3"), tmp_path / "m.mxf", columns=plan.columns)
    a = cxf_measurement_to_ti3(mxf, tmp_path / "a.ti3", "M2")
    before = _sha(mxf)
    ra = load_reading(a)
    rb = load_reading(mxf, ra.condition)
    assert rb.converted_from_cxf and rb.condition == "M2"
    c = compare(ra, rb)
    assert c.worst == pytest.approx(0.0, abs=1e-6)
    assert _sha(mxf) == before
    # no temporary folder is left behind beside the file
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        ["c", "m.mxf", "a.ti3"])


# ---- the window ----------------------------------------------------------

def _inspector(qapp, ti3):
    from tests.test_profile_tools import _runner, _Settings
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    dlg = Ti3InfoDialog(_runner(), _Settings())
    dlg.load_measurement(ti3)
    qapp.processEvents()
    return dlg


def _texts(dlg) -> str:
    from PyQt6.QtWidgets import QLabel
    return "\n".join(w.text() for w in dlg._details.findChildren(QLabel))


@pytest.mark.parametrize("mode", ["inspect", "verify"])
def test_the_window_shows_the_comparison_in_both_modes(qapp, a, tmp_path,
                                                        mode):
    b = _write(tmp_path / "b.ti3", _noisy(bad=(10, 200)))
    dlg = _inspector(qapp, a)
    if mode == "verify":
        dlg._rb_verify.setChecked(True)
    dlg.load_second_reading(b)
    qapp.processEvents()
    t = _texts(dlg)
    assert "Another reading of this chart" in t
    assert "95th percentile ΔE₀₀" in t and "Above the tolerance" in t
    assert "Patch 11" in t and "What this tells you" in t
    assert dlg._tol_box.isVisibleTo(dlg)
    # the tolerance changes the count, presets and custom
    n1 = re.search(r"(\d+|none) of 616 patches", t).group(0)
    dlg._tol_combo.setCurrentIndex(dlg._tol_combo.count() - 1)   # Custom
    assert dlg._tol_spin.isVisibleTo(dlg)
    dlg._tol_spin.setValue(0.1)
    qapp.processEvents()
    n2 = re.search(r"(\d+|none) of 616 patches", _texts(dlg)).group(0)
    assert n1 != n2
    # Clear stops comparing
    dlg._on_second_clear()
    assert "Another reading of this chart" not in _texts(dlg)
    assert not dlg._tol_box.isVisibleTo(dlg)
    dlg.deleteLater()


def test_the_window_refuses_another_chart_in_words(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", lambda r, f: r[:-1])
    dlg = _inspector(qapp, a)
    dlg.load_second_reading(b)
    t = _texts(dlg)
    title, _body = M.M_READINGS_NOT_SAME_CHART.render(file="b.ti3",
                                                      reason="x")
    assert title in t and "Average ΔE₀₀" not in t.split(title)[1]
    dlg.deleteLater()


def test_the_saved_inspection_carries_the_comparison(qapp, a, tmp_path):
    b = _write(tmp_path / "b.ti3", _noisy(bad=(10, 200, 300)))
    dlg = _inspector(qapp, a)
    dlg.load_second_reading(b)
    text = "\n".join(dlg._report)
    assert "Another reading of this chart" in text
    assert "All patches above the tolerance" in text
    assert "Patch 11" in text and "Patch 301" in text
    dlg.deleteLater()
