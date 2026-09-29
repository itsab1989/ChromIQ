"""A control-strip declaration may not name a patch nobody will ever measure.

B8-407, found by the B8-393 round while rebuilding the demo package against the
producer B8-405 shipped.

``printtarg`` pads a partial last strip with bare-paper patches and gives every
one of them ``SAMPLE_ID 0``. They are printed on the sheet, they are never
read, and no ``.ti3`` ever carries that id. ChromIQ has known this since the
relayout engine was written (``workflow/ti2_relayout.py``: *"printtarg pads a
partial last strip with white patches whose SAMPLE_ID is 0 ... they don't
correspond to anything the user placed, so skip them"*).

``control_strip.chart_device_values`` did not know it. A pad patch sits at
device (100, 100, 100), which is the ladder's FIRST aim, so on every padded
chart the pad took the substrate rung and the real bare-paper patch beside it
was never declared. ``control_strip_block`` then counted the declared id as
absent and ``k`` fell by one.

MEASURED on the demo package, 2026-09-19, before the fix: **23 of 89 dated
declarations named sample id 0**, and on the 20-patch chart that single
phantom took k from 8 to 7, under ``CONTROL_STRIP_MIN``, so all three
control-strip rows read ``control_strip_too_small`` on a chart that really does
carry a strip.

**THE CHART HERE IS REAL AND IS REALLY PADDED.** A hand-written .ti2 with a
tidy row of pad patches would be a fixture built to the shape of the bug, and
the point of this one is that ``printtarg`` produces it unasked: the fixture
asserts the pad rows are there before it asserts anything about the strip, so
a run in which printtarg did not pad fails loudly instead of passing quietly.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import control_strip as cs                  # noqa: E402
from workflow.measurement_report import CONTROL_STRIP_MIN  # noqa: E402
from workflow.ti3_analysis import parse_ti3               # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")


def _argyll(tool: str) -> str:
    p = shutil.which(tool) or str(ARGYLL / tool)
    if not Path(p).exists():
        pytest.skip(f"Argyll {tool} not available")
    return p


def _run(cmd, cwd):
    subprocess.run([str(c) for c in cmd], cwd=str(cwd), check=True,
                   capture_output=True, timeout=300)


def _ti2_rows(ti2: Path) -> "list[list[str]]":
    """Every data row of the first table, as tokens."""
    lines = ti2.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
    end = next(i for i, ln in enumerate(lines[start:], start)
               if ln.strip() == "END_DATA")
    return [ln.split() for ln in lines[start + 1:end] if ln.split()]


@pytest.fixture(scope="module")
def padded_chart(tmp_path_factory):
    """A real chart printtarg really padded, plus its measurement.

    Twenty patches on A4 at the ColorMunki's own strip length: targen designs
    twenty, printtarg needs thirty to fill its last strip and invents ten.
    """
    d = tmp_path_factory.mktemp("padded")
    _run([_argyll("targen"), "-d2", "-f20", "-g10", "-s0", "chart"], d)
    _run([_argyll("printtarg"), "-iCM", "-pA4", "-t150", "-L", "chart"], d)
    ti2 = d / "chart.ti2"
    assert ti2.is_file()
    pads = [r for r in _ti2_rows(ti2) if r[0].strip('"') == "0"]
    assert pads, (
        "printtarg did not pad this chart, so the fixture cannot contain the "
        "fault it exists to catch. Pick a patch count that does not fill the "
        "last strip exactly, or this guard is worthless.")
    # The measurement, so "does this id exist" is asked of a real .ti3 rather
    # than of an assumption about what fakeread keeps.
    srgb = ARGYLL.parent / "ref" / "sRGB.icm"
    if not srgb.is_file():
        pytest.skip("Argyll ref/sRGB.icm not available")
    _run([_argyll("fakeread"), srgb, "chart"], d)
    return {"ti2": ti2, "ti3": d / "chart.ti3", "pads": len(pads)}


def test_printtarg_really_pads_this_chart_with_sample_id_zero(padded_chart):
    """The precondition, stated as its own check.

    A guard whose fixture quietly stopped containing the fault would go on
    passing for the wrong reason; this is the line that would go red first.
    """
    assert padded_chart["pads"] >= 1
    rows = _ti2_rows(padded_chart["ti2"])
    real = [r for r in rows if r[0].strip('"') != "0"]
    assert len(real) == 20 and len(rows) == 20 + padded_chart["pads"]


def test_a_padding_patch_is_in_no_measurement(padded_chart):
    """Why naming one is a fault and not merely untidy."""
    measured = set(parse_ti3(padded_chart["ti3"]).sample_ids)
    assert "0" not in measured
    assert len(measured) == 20


def test_the_device_values_skip_the_padding(padded_chart):
    """MUTATION: drop the ``int(sid) <= 0`` skip in `chart_device_values` and
    this goes red, because the pad rows come back with it."""
    devices = cs.chart_device_values(padded_chart["ti2"])
    assert "0" not in devices, (
        "chart_device_values returned printtarg's padding as a patch; the "
        "ladder will offer the substrate rung to a patch no instrument will "
        "ever read")
    assert len(devices) == 20


def test_the_declared_strip_names_only_patches_the_sheet_will_be_read_for(
        padded_chart):
    """The fault as the report meets it: a declared id that is not there.

    MUTATION: same one. Without the skip the substrate rung is filled by
    sample id 0 and this line names it.
    """
    sel = cs.strip_for_chart(padded_chart["ti2"])
    measured = set(parse_ti3(padded_chart["ti3"]).sample_ids)
    phantom = [sid for sid in sel.ids if sid not in measured]
    assert not phantom, (
        f"the declaration names {phantom}, which no measurement of this chart "
        f"can contain, so the report counts the strip one patch shorter than "
        f"it declared")


def test_the_substrate_rung_is_a_real_bare_paper_patch(padded_chart):
    """And it is the SUBSTRATE that the padding took, which is why one phantom
    id was enough to lose the whole strip on a small chart."""
    sel = cs.strip_for_chart(padded_chart["ti2"])
    paper = {f.key: f.sample_id for f in sel.fills}["paper"]
    assert paper is not None and paper != "0"
    devices = cs.chart_device_values(padded_chart["ti2"])
    assert min(devices[paper]) >= 99.0, (
        "the substrate rung was not filled by a bare-paper patch")


def test_the_chart_can_still_declare_a_strip_at_all(padded_chart):
    """The consequence the fix restores, on the size where it mattered.

    Twenty patches fill exactly eight rungs, which is `CONTROL_STRIP_MIN`. One
    phantom id put it at seven and the report refused the whole strip.
    """
    sel = cs.strip_for_chart(padded_chart["ti2"])
    assert sel.n >= CONTROL_STRIP_MIN, (
        f"a 20-patch chart fills {sel.n} rungs and needs {CONTROL_STRIP_MIN}")
    assert sel.can_declare and not sel.p95_ready
