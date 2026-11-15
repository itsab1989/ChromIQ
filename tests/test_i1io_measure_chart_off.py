"""WITH THE i1iO BETA OFF, THE IMPORT IS WHAT IT WAS (the Measure Chart route,
2026-11-15).

* the route's module is never imported and the picked file is never opened
  for it while the switch is off, on either door;
* the verdict for every kind of file is the same with the picked file passed
  (the Measure tab) as without it (4.3.37's call), Beta off, and Beta on for
  a chart that is not an i1iO chart;
* the Measure tab converts a ``.cmxf`` exactly as before while off (the
  converter's own route), and only the gated route reads it as a CxF.
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests import i1p_forward as F          # noqa: E402

MODULE = "workflow.i1io.measure_chart"


@pytest.fixture
def beta():
    from workflow.i1io import support
    before = support._latched

    def set_(value):
        support.set_enabled_for_this_process(value)
    yield set_
    support._latched = before


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    """An i1iO chart with a Measure Chart file, an ordinary i1Pro chart with
    a measurement of its own (device values), a device-less one, and a
    Measure Chart shaped file of the ordinary chart."""
    from workflow.i1io import support
    from workflow.layout_engine import chart as engine
    root = tmp_path_factory.mktemp("mc_off")
    rng = np.random.default_rng(2)
    rgbs = [tuple(rng.uniform(0, 100, 3)) for _ in range(120)]
    io = F.build_chart(root / "io", rgbs, seed=4)
    sh = F.load_sheet(io)
    mc = F.measure(sh, root / "scan.cmxf")
    mc_mxf = F.measure(sh, root / "scan.mxf")
    support._latched = None
    ti1 = F.write_ti1(root / "p.ti1", rgbs)
    (root / "plain").mkdir()
    engine.build_chart(ti1, root / "plain" / "p", instrument="i1",
                       paper="A4", dpi=72, seed=4)
    plain = root / "plain" / "p.ti2"
    lines = plain.read_text().split("BEGIN_DATA\n", 1)[1].split(
        "END_DATA")[0].strip().splitlines()
    head = ('CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "Argyll chartread"\n'
            'COLOR_REP "RGB_XYZ"\n\n')
    rows_dev, rows_bare = [], []
    for ln in lines:
        p = ln.split()
        lab = F.printer_lab([float(v) for v in p[2:5]], rng, 0.5)
        x, y, z = F._lab_to_xyz_d50(lab)
        rows_dev.append(f"{p[0]} {p[1]} {p[2]} {p[3]} {p[4]} {x:.4f} "
                        f"{y:.4f} {z:.4f}")
        rows_bare.append(f"{p[0]} {p[1]} {x:.4f} {y:.4f} {z:.4f}")
    dev = root / "dev.ti3"
    dev.write_text(head + "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\nSAMPLE_ID "
                   "SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
                   "END_DATA_FORMAT\n\n"
                   f"NUMBER_OF_SETS {len(rows_dev)}\nBEGIN_DATA\n"
                   + "\n".join(rows_dev) + "\nEND_DATA\n")
    bare = root / "bare.ti3"
    bare.write_text(head.replace("RGB_XYZ", "XYZ") + "NUMBER_OF_FIELDS 5\n"
                    "BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y "
                    "XYZ_Z\nEND_DATA_FORMAT\n\n"
                    f"NUMBER_OF_SETS {len(rows_bare)}\nBEGIN_DATA\n"
                    + "\n".join(rows_bare) + "\nEND_DATA\n")
    return dict(root=root, io=io, mc=mc, mc_mxf=mc_mxf,
                mc_conv=F.convert(mc, root / "c1"),
                mxf_conv=F.convert(mc_mxf, root / "c2"),
                plain=plain, dev=dev, bare=bare)


@pytest.fixture
def module_forbidden(monkeypatch):
    """Importing the route's module, or opening a picked file for it, fails
    the test."""
    class Boom(types.ModuleType):
        def __getattr__(self, name):
            raise AssertionError(f"{MODULE}.{name} used with the Beta off")
    monkeypatch.delitem(sys.modules, MODULE, raising=False)
    monkeypatch.setitem(sys.modules, MODULE, Boom(MODULE))
    import workflow.i1io as pkg
    monkeypatch.setattr(pkg, "measure_chart", sys.modules[MODULE],
                        raising=False)
    import xml.etree.ElementTree as ET
    real = ET.parse

    def parse(src, *a, **k):
        if str(src).endswith((".cmxf",)):
            raise AssertionError(f"{src} opened with the Beta off")
        return real(src, *a, **k)
    monkeypatch.setattr(ET, "parse", parse)


def _cases(f):
    return [("measure chart cmxf on its i1iO chart", f["mc_conv"], f["io"],
             f["mc"]),
            ("measure chart mxf on its i1iO chart", f["mxf_conv"], f["io"],
             f["mc_mxf"]),
            ("measure chart on an ordinary chart", f["mxf_conv"], f["plain"],
             f["mc_mxf"]),
            ("measurement with device values", f["dev"], f["plain"],
             f["dev"]),
            ("device-less measurement", f["bare"], f["plain"], f["bare"])]


def test_with_the_beta_off_nothing_is_read_and_nothing_changes(
        files, beta, module_forbidden):
    from workflow.measurement_import import assess
    beta(False)
    for name, conv, chart, source in _cases(files):
        if source.suffix == ".cmxf":
            continue                 # never converted while off (below)
        a = assess(conv, chart)
        b = assess(conv, chart, source=source)
        assert a == b, name
        assert b.i1io_grid is None, name


def test_with_the_beta_on_an_ordinary_chart_is_judged_as_before(files, beta):
    from workflow.measurement_import import assess
    beta(False)
    before = {n: assess(c, ch) for n, c, ch, _s in _cases(files)
              if "ordinary" in n or "device" in n}
    beta(True)
    for name, conv, chart, source in _cases(files):
        if name not in before:
            continue
        assert assess(conv, chart, source=source) == before[name], name
    # and the filed rows of an ordinary import do not move: the measurement
    # with device values is verified, the device-less one paired by name
    assert before["measurement with device values"].ok
    assert before["device-less measurement"].device_from_chart


def test_the_measure_chart_file_is_refused_as_today_with_the_beta_off(
        files, beta, module_forbidden):
    """An .mxf with i1Profiler's placeholders on an i1iO chart, Beta off:
    the identity check refuses it exactly as 4.3.37 did."""
    from workflow.measurement_import import assess
    beta(False)
    v = assess(files["mxf_conv"], files["io"], source=files["mc_mxf"])
    assert not v.ok and v.i1io_grid is None
    assert v == assess(files["mxf_conv"], files["io"])


def test_the_measure_tab_converts_a_cmxf_as_before_while_off(
        files, beta, module_forbidden, monkeypatch, tmp_path):
    """Off, a .cmxf goes to the converter's own route (txt2ti3), exactly as
    before; the gated CxF reading of it is never reached."""
    from ui.tabs.tab_measure import TabMeasure
    import workflow.reference_convert as RC
    beta(False)
    calls = []

    def fake_convert(path, argyll, out_dir, **kw):
        calls.append((Path(path), kw))
        return Path(path)
    monkeypatch.setattr(RC, "convert_i1profiler_measurement", fake_convert)

    class Run:
        def ensure_cache_dir(self):
            return tmp_path

    class Log:
        def appendPlainText(self, *_a):
            pass

    class Settings:
        def get(self, _k, d=None):
            return d
    fake = types.SimpleNamespace(_log=Log(), _settings=Settings())
    out = TabMeasure._convert_import_file(fake, Run(), files["mc"],
                                          chart=files["io"])
    assert calls == [(files["mc"], {"condition": None})]
    assert out == files["mc"]


def test_with_the_beta_on_the_cmxf_is_read_as_a_cxf(files, beta, monkeypatch,
                                                    tmp_path):
    from ui.tabs.tab_measure import TabMeasure
    import workflow.reference_convert as RC
    beta(True)
    monkeypatch.setattr(RC, "convert_i1profiler_measurement",
                        lambda *a, **k: pytest.fail("the converter's route"))

    class Run:
        def ensure_cache_dir(self):
            return tmp_path

    class Log:
        def appendPlainText(self, *_a):
            pass

    class Settings:
        def get(self, _k, d=None):
            return d
    fake = types.SimpleNamespace(_log=Log(), _settings=Settings())
    out = TabMeasure._convert_import_file(fake, Run(), files["mc"],
                                          chart=files["io"])
    assert out.suffix == ".ti3" and "MEASUREMENT_CONDITION" in out.read_text()
