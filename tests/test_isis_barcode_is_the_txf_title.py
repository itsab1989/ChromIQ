"""The barcode carries the chart's name exactly as the .txf's TitleString
does (review of a7ca1489e, M2: project "My Printer Glossy" printed
"MY PRINTER GLOSSY" in the barcode while the .txf said "My-Printer-Glossy",
so i1Profiler, which encodes its own title, would not find the sheet).

Both use the chart's file name, the project name as ChromIQ cleans it for
its folders; the name line on the sheet keeps the project's own name.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.file_manager import FileManager
from workflow.isis import chart as C

NAMES = ["My Printer Glossy", "Mein Drucker Glänzend", "epson_et8550 matte",
         "Ilford Gold Fibre Gloss (310)", "lower case name"]


@pytest.fixture(autouse=True)
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _ti1(path: Path, n: int) -> Path:
    rows = "\n".join(f"{i + 1} {i % 100:.1f} {(i * 7) % 100:.1f} "
                     f"{(i * 13) % 100:.1f}" for i in range(n))
    path.write_text(
        "CTI1\n\nDESCRIPTOR \"t\"\nCOLOR_REP \"RGB\"\n\n"
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    return path


@pytest.mark.parametrize("project", NAMES)
def test_the_barcode_and_the_txf_carry_one_title(tmp_path, project):
    from workflow.isis.export import write_isis_export
    from workflow.isis.support import read_side_file
    from workflow.layout_engine import chart
    stem = FileManager._sanitise(project)
    ti1 = _ti1(tmp_path / "c.ti1", 300)
    chart.build_chart(ti1, tmp_path / stem, instrument="XRISIS", paper="A4",
                      dpi=100, project=project, isis_barcode=True)
    ti2 = tmp_path / f"{stem}.ti2"
    res = write_isis_export(ti2, tmp_path, stem)
    txf = Path(res.txf) if getattr(res, "txf", None) else next(
        tmp_path.glob("*.txf"))
    title = re.search(r'TitleString="([^"]*)"',
                      txf.read_text(encoding="utf-8")).group(1)
    assert title == stem
    side = read_side_file(ti2)
    for page in side["pages_detail"]:
        code = page["barcode"]
        body, _star, check = code.rpartition("*")
        # the title in the barcode is the .txf's, as i1Profiler encodes it
        assert body.split(" ", 1)[1] == C.barcode_title(title), (code, title)
        # the DECIMAL checksum over everything before it, "*" included
        assert int(check) == sum(ord(c) for c in body + "*"), code
    # the sheet's name line keeps the project's own name
    assert side["name"] == project


def test_the_layout_panel_shows_the_nominal_patch(tmp_path):
    """Review NIT: an i1iSis chart's "Patch size" reads its nominal 6 x 6
    mm (what its .txf names), not the 6.01 its pixels round to; the pixels
    are unchanged."""
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path / "c.ti1", 300)
    chart.build_chart(ti1, tmp_path / "nominal", instrument="XRISIS",
                      paper="A4", dpi=300, project="nominal")
    # the chart's channels.json as Create Chart writes it: the first patch
    # rect in pixels (71 px = 6.01 mm at 300 dpi)
    import json
    (tmp_path / "nominal.channels.json").write_text(json.dumps({
        "layout": {"dpi": 300, "recipe": {"instrument": "XRISIS"},
                   "patches": [{"x": 0, "y": 0, "w": 71, "h": 71}]}}),
        encoding="utf-8")
    pw, ph, _pitch = TabChart._chart_patch_size_mm(tmp_path / "nominal.ti2")
    assert (pw, ph) == (6.0, 6.0)
