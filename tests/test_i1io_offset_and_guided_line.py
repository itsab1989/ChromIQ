"""THE CHART OFFSET IS FITTED; GUIDED WITHOUT CROSSES KEEPS THE NAME LINE
(review 5, items 2 and 4).

* Item 2: defaults + chart offset X 3 mm (from about 1.5 mm with the crosses
  on), or Y 25 mm, was refused at Generate ("A patch would touch an aiming
  cross") while the estimate and "Measured from Preview" said OK. The floor on
  the side the block moves towards now grows by the offset, so the fit lays
  out fewer patches and the chart builds; the estimate, the Preview check and
  the build agree.
* Item 4: in Guided, with the crosses off, the name and page line was always
  left off on a full A4 or Letter sheet, and the log's advice (a larger right
  margin) cannot be followed in Guided. Guided keeps the right edge's room
  for the line (cost: A4 552 -> 528 patches, Letter 528 -> 506).
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(folder, paper, **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    r = chart.build_chart(_ti1(folder / "c.ti1", 5000), folder / "c",
                          instrument="IO2", paper=paper, dpi=100, seed=1,
                          project="P", chart_date="x", **kw)
    side = json.loads((folder / "c.i1io.json").read_text(encoding="utf-8"))
    return r, side


@pytest.mark.parametrize("paper", ["A4", "Letter"])
@pytest.mark.parametrize("crosses", [True, False])
@pytest.mark.parametrize("ox,oy", [(1.5, 0.0), (3.0, 0.0), (8.0, 0.0),
                                   (0.0, 25.0), (3.0, 3.0)])
def test_an_offset_builds_as_estimated(tmp_path, paper, crosses, ox, oy):
    from workflow.i1io import chart as C
    from workflow.layout_engine import geometry, instruments, papers
    kw = {"offset_x": ox, "offset_y": oy, C.CROSSES_KEY: crosses}
    full = dict(kw, instrument="IO2", paper=paper, dpi=100)
    geom = instruments.geom_from_build_kwargs(full)
    w, h = (float(v) for v in papers.dimensions_mm(paper))
    estimate = geometry.compute(geom, w, h, 5000).patches_per_page
    _s, notes = C.preview_checks(dict(full, area_target_count=5000))
    r, _side = _build(tmp_path, paper, **kw)          # never refused
    assert r.layout.patches_per_page == estimate
    assert sorted(notes) == sorted(r.warnings)


@pytest.mark.parametrize("paper,patches", [("A4", 528), ("Letter", 506)])
def test_guided_without_crosses_keeps_the_name_line(tmp_path, paper, patches):
    from workflow.i1io import chart as C
    r, side = _build(tmp_path, paper, **{C.CROSSES_KEY: False})
    assert r.layout.patches_per_page == patches
    for page in side["pages"]:
        assert page["text_line"]["text"], page["text_line"]
    assert not r.warnings
