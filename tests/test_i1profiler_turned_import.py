"""The way back from the beta "turned" i1Profiler export (§I.14).

i1Profiler numbers the readings of a chart it laid out 1..N in patch-list
order (its CxF objects carry no trace of ChromIQ's patch ids,
``measurement_report.verify_patch_identity``), so a measurement of the turned
chart arrives in the TURNED order. These tests build such a measurement the way
i1Profiler writes one (Target objects from the ``.txf``, then one
``M0_Measurement`` per patch, index-aligned), import it through the very
functions the import doors use, and check every reading lands on its own patch;
then they try to make it go wrong.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import exports_subdir                       # noqa: E402
from workflow import i1profiler_turned as T                        # noqa: E402
from workflow.measurement_import import (assess,                   # noqa: E402
                                         complete_from_turned_order)
from workflow.reference_convert import cxf_measurement_to_ti3       # noqa: E402
from workflow.ti3_analysis import parse_ti3                         # noqa: E402

from tests.test_i1profiler_turned_export import _chart              # noqa: E402

_NS = "http://colorexchangeformat.com/CxF3-core"


def _spectrum(r: float, g: float, b: float) -> list:
    """A plausible reflectance for device RGB 0..255: each band follows its
    channel, so every patch reads back a different, predictable colour."""
    out = []
    for i in range(36):
        lam = 380 + 10 * i
        ch = b if lam < 490 else g if lam < 580 else r
        out.append(round(0.02 + 0.9 * ch / 255.0, 5))
    return out


def _mxf_from_txf(txf: Path, out: Path, rows: "list[int] | None" = None) -> Path:
    """An i1Profiler-shaped measurement (.mxf) of the chart *txf* lays out.

    *rows* reorders the i1Profiler patch list (a list of indices into it),
    which is how a mis-read or swapped row is simulated: the readings move
    WITH their device values, as they would in a real file."""
    text = txf.read_text(encoding="utf-8")
    objs = re.findall(r'(<cc:Object ObjectType="Target".*?</cc:Object>)',
                      text, flags=re.S)
    rgb = [tuple(int(v) for v in re.findall(r"<cc:[RGB]>(\d+)</cc:[RGB]>", o))
           for o in objs]
    order = rows if rows is not None else list(range(len(objs)))
    targets, meas = [], []
    for k, i in enumerate(order, 1):
        r, g, b = rgb[i]
        targets.append(
            f'<cc:Object ObjectType="Target" Name="Target{k}" Id="c{k}">'
            f'<cc:DeviceColorValues><cc:ColorRGB ColorSpecification="Unknown">'
            f"<cc:R>{r}</cc:R><cc:G>{g}</cc:G><cc:B>{b}</cc:B>"
            "</cc:ColorRGB></cc:DeviceColorValues></cc:Object>")
        sp = " ".join(str(v) for v in _spectrum(r, g, b))
        meas.append(
            f'<cc:Object ObjectType="M0_Measurement" Name="M0_Measurement{k}" '
            f'Id="m{k}"><cc:ColorValues><cc:ReflectanceSpectrum '
            f'StartWL="380">{sp}</cc:ReflectanceSpectrum></cc:ColorValues>'
            "</cc:Object>")
    out.write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><cc:CxF xmlns:cc="{_NS}">'
        "<cc:Resources><cc:ObjectCollection>" + "".join(targets + meas)
        + "</cc:ObjectCollection></cc:Resources></cc:CxF>", encoding="utf-8")
    return out


@pytest.fixture()
def turned_chart(tmp_path):
    ti2 = _chart(tmp_path / "proj", "Proj", 350)
    res = T.write_turned_export(ti2, exports_subdir(ti2.parent), "Proj")
    assert not res.skipped
    return ti2, T.TurnedFiles(exports_subdir(ti2.parent), "Proj")


def _xyz_by_sid(ti3: Path) -> dict:
    d = parse_ti3(ti3)
    return {sid: tuple(np.round(x, 3)) for sid, x in zip(d.sample_ids, d.xyz)}


def _expected_xyz(ti2: Path, tmp: Path) -> dict:
    """What each CHART patch reads as, from a measurement made in the chart's
    own order (the ordinary, already supported import)."""
    plan = T.plan_for(ti2)
    sids = [sid for sid, _l, _v in plan.order]
    # the same spectra, written in the chart's SAMPLE_ID order
    txf = next(p for p in (exports_subdir(ti2.parent)).glob("*-i1Pro3.txf"))
    by_turned = list(range(len(sids)))
    chart_rank = sorted(by_turned, key=lambda j: int(sids[j]))
    mxf = _mxf_from_txf(txf, tmp / "plain.mxf", rows=chart_rank)
    ti3 = cxf_measurement_to_ti3(mxf, tmp / "plain.ti3")
    return _xyz_by_sid(ti3)


def test_a_turned_measurement_imports_with_every_reading_on_its_patch(
        turned_chart, tmp_path):
    ti2, files = turned_chart
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "turned.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "turned.ti3")
    v = assess(ti3, ti2)
    assert v.ok and v.turned_order and not v.device_from_chart, v.reason
    assert complete_from_turned_order(ti3, ti2) == len(T.plan_for(ti2).order)
    # every reading is the one its OWN patch gives
    assert _xyz_by_sid(ti3) == _expected_xyz(ti2, tmp_path)
    # and the ordinary identity check now agrees, by SAMPLE_ID
    from workflow.measurement_report import verify_patch_identity
    ident = verify_patch_identity(parse_ti3(ti3), ti2)
    assert ident["verdict"] == "verified" and ident["paired_by"] == "SAMPLE_ID"
    # names are the chart's own, and the file says how it was paired
    locs = parse_ti3(ti3).sample_locs
    assert set(locs) == {loc for _s, loc, _v in T.plan_for(ti2).order}
    assert T.TURNED_KEYWORD in ti3.read_text()
    # filed twice is filed once: the second pass finds nothing to do
    assert assess(ti3, ti2).turned_order is False
    assert complete_from_turned_order(ti3, ti2) == 0


def test_a_measurement_with_two_rows_swapped_is_refused(turned_chart, tmp_path):
    ti2, files = turned_chart
    plan = T.plan_for(ti2)
    R = plan.rows
    order = list(range(len(plan.order)))
    # swap i1Profiler rows 2 and 5 (entries j with j % R == 1 and == 4)
    for j in range(len(order)):
        if j % R == 1:
            order[j], order[j + 3] = order[j + 3], order[j]
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "swapped.mxf",
                        rows=order)
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "swapped.ti3")
    before = ti3.read_bytes()
    v = assess(ti3, ti2)
    assert not v.ok and not v.turned_order
    assert "do not hold the colour the chart asked for" in v.reason
    assert complete_from_turned_order(ti3, ti2) == 0
    assert ti3.read_bytes() == before


def test_an_order_written_for_another_chart_is_not_used(turned_chart, tmp_path):
    """The order is tied to the .ti2 by its SHA-256: a chart rebuilt under the
    same name does not inherit the old one's order."""
    ti2, files = turned_chart
    mxf = _mxf_from_txf(files.txf("i1Pro 3"), tmp_path / "turned.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "turned.ti3")
    ti2.write_text(ti2.read_text() + "\n", encoding="utf-8")   # another chart
    assert T.turned_order_for(ti2) is None
    v = assess(ti3, ti2)
    assert not v.ok and not v.turned_order


def _cgats(path: Path, fields: str, rows: list) -> Path:
    path.write_text("CTI3\n\nDESCRIPTOR \"sim\"\nNUMBER_OF_FIELDS "
                    f"{len(fields.split())}\nBEGIN_DATA_FORMAT\n{fields}\n"
                    f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\n"
                    "BEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
                    encoding="utf-8")
    return path


def _i1p_names(rows: int, cols: int) -> list:
    """i1Profiler-style grid names for patch-list entry j (column-major):
    row letter, column number. On a turned chart this is the very set of
    names ChromIQ printed (strips A.., places 1..), each on another patch."""
    letters = [chr(65 + i) if i < 26 else "A" + chr(65 + i - 26)
               for i in range(rows)]
    return [f"{letters[j % rows]}{j // rows + 1}" for j in range(rows * cols)]


def test_names_that_coincide_are_never_used_to_pair_a_turned_chart(
        turned_chart, tmp_path):
    ti2, files = turned_chart
    plan = T.plan_for(ti2)
    names = _i1p_names(plan.rows, plan.columns)
    chart_locs = {loc for _s, loc, _v in plan.order}
    assert set(names) == chart_locs, "the trap: every name exists on the chart"
    assert any(n != loc for n, (_s, loc, _v) in zip(names, plan.order))
    # 1. No device values: refused, never paired by name.
    rows = [f'{j + 1} "{n}" {50 + j % 40:.2f} 40.00 30.00'
            for j, n in enumerate(names)]
    bare = _cgats(tmp_path / "bare.ti3", "SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z",
                  rows)
    v = assess(bare, ti2)
    assert not v.ok and not v.device_from_chart
    assert "turned i1Profiler chart" in v.reason
    # 2. With device values: paired by the order, the names are ignored.
    rows = []
    for j, ((_sid, _loc, vals), n) in enumerate(zip(plan.order, names), 1):
        rows.append(f'{j} "{n}" {vals["R"]:.4f} {vals["G"]:.4f} '
                    f'{vals["B"]:.4f} {vals["R"] * .4:.4f} {vals["G"] * .5:.4f} '
                    f'{vals["B"] * .6:.4f}')
    meas = _cgats(tmp_path / "named.ti3",
                  "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
                  rows)
    v = assess(meas, ti2)
    assert v.ok and v.turned_order
    assert complete_from_turned_order(meas, ti2) == len(plan.order)
    d = parse_ti3(meas)
    chart = {sid: vals for sid, _l, vals in plan.order}
    loc_of = {sid: loc for sid, loc, _v in plan.order}
    for sid, loc, x in zip(d.sample_ids, d.sample_locs, d.xyz):
        want = chart[sid]
        assert tuple(x) == pytest.approx(
            (want["R"] * .4, want["G"] * .5, want["B"] * .6), abs=1e-3)
        assert loc == loc_of[sid]


# ---------------------------------------------------------------------------
# Every existing import behaves exactly as before
# ---------------------------------------------------------------------------

def _plain_measurement(ti2: Path, path: Path, *, with_device: bool) -> Path:
    """A measurement in the CHART's own order (the ordinary import)."""
    plan = T.plan_for(ti2)
    rows = sorted(plan.order, key=lambda t: int(t[0]))
    lines = []
    for sid, loc, vals in rows:
        dev = (f'{vals["R"]:.4f} {vals["G"]:.4f} {vals["B"]:.4f} '
               if with_device else "")
        lines.append(f'{sid} "{loc}" {dev}{vals["R"] * .4:.4f} '
                     f'{vals["G"] * .5:.4f} {vals["B"] * .6:.4f}')
    fields = ("SAMPLE_ID SAMPLE_LOC " + ("RGB_R RGB_G RGB_B " if with_device
                                          else "") + "XYZ_X XYZ_Y XYZ_Z")
    return _cgats(path, fields, lines)


@pytest.mark.parametrize("with_device", [True, False])
def test_an_ordinary_measurement_is_judged_as_before(tmp_path, with_device):
    """Without a turned export (option off, or a chart that does not qualify)
    the verdict is byte for byte today's; with one, an ordinary measurement
    carrying device values is too."""
    ti2 = _chart(tmp_path / "p", "P", 350)
    meas = _plain_measurement(ti2, tmp_path / "m.ti3", with_device=with_device)
    before = assess(meas, ti2)
    assert before.ok and before.turned_order is False
    assert before.device_from_chart is (not with_device)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "P")
    after = assess(meas, ti2)
    if with_device:
        assert after == before
    else:
        # the one deliberate change: a chart with a turned export cannot pair
        # a device-less file by name, because the turned chart's names are
        # the same set on other patches (see the test above)
        assert not after.ok


def test_a_wrong_measurement_is_refused_as_before(tmp_path):
    ti2 = _chart(tmp_path / "p", "P", 350)
    meas = _plain_measurement(ti2, tmp_path / "m.ti3", with_device=True)
    txt = meas.read_text().splitlines()
    i = txt.index("BEGIN_DATA") + 1
    a, b = txt[i].split(" ", 1), txt[i + 7].split(" ", 1)
    txt[i], txt[i + 7] = f"{b[0]} {a[1]}", f"{a[0]} {b[1]}"   # ids swapped
    meas.write_text("\n".join(txt) + "\n")
    before = assess(meas, ti2)
    T.write_turned_export(ti2, exports_subdir(ti2.parent), "P")
    after = assess(meas, ti2)
    assert not before.ok and after == before


def test_a_turned_measurement_without_the_option_is_refused_as_before(tmp_path):
    """No order file (the option was off when the chart was made): a file in
    the turned order is what it always was, a mismatch, refused."""
    ti2 = _chart(tmp_path / "p", "P", 350)
    side = tmp_path / "side"
    T.write_turned_export(ti2, side, "P")
    mxf = _mxf_from_txf(T.TurnedFiles(side, "P").txf("i1Pro 3"),
                        tmp_path / "t.mxf")
    ti3 = cxf_measurement_to_ti3(mxf, tmp_path / "t.ti3")
    v = assess(ti3, ti2)
    assert not v.ok and not v.turned_order


def test_every_import_door_files_a_turned_measurement_through_it():
    import inspect
    from ui import measurement_filing
    from ui.tabs.tab_measure import TabMeasure
    assert "complete_from_turned_order" in inspect.getsource(
        measurement_filing.say_what_was_filed)
    for door in (TabMeasure._import_into_verification,
                 TabMeasure._import_into_profiling_run):
        src = inspect.getsource(door)
        assert "turned_order" in src and "_complete_turned_import" in src
