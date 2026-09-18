"""A FROM PROFILE GAMUT chart must be printable, and must be read against the
corners it declares.

Both faults this file guards were found on a real chart built by the app's own
module (B8-393, 2026-09-18) and neither can be reproduced on a hand-written
.ti1, so the fixture builds the real thing: a real ICC from Argyll, the Create
Chart tab's own Generate, the layout engine's own sheet, the adopt hook's own
colorimetric reference, and a fake-read of that sheet through the same profile.

**F1 — the selection asked for ink amounts that do not exist.** ``xicclu``'s
numeric inverse answers outside the device cube, and the forward leg
extrapolates back, so a colour needing device 107.69 round-tripped 0.000 ΔE00
from its aim and was selected as reachable. Measured on the fixture's own
profile: 304 of the 5,960 master colours, 238 of them past 101. One patch past
101 is all it takes: ``measurement_report._rgb_to_0_100`` then reads the whole
chart as 0..255 code values and divides every device value by 2.55, device
white lands at 39.2, and not one cube corner is found. Measured before the fix
on this fixture's chart: 19 patches over 100, seven of the eight corners
``present: false``, paper white and the CMY hue row ``no_corners``, and
"Solid colours, largest" reporting 0.00 off a body patch.

**F2 — the chart's declaration was read by nobody.** The corners were found by
nearest device value over the whole chart, so the black block's own patch at
device (0,0,0) was read as the composite black while the declared corner was
read by nobody, and stayed in the ΔE00 statistics as well: counted twice.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import gamut_target as gt                   # noqa: E402
from workflow.measurement_report import (CUBE_CORNERS,    # noqa: E402
                                         build_report, row_values)
from workflow.ti3_analysis import parse_ti3               # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")
#: Big enough that the master set's own black patch is in the body — which is
#: the patch the corner search used to read the composite black off.
COUNT = 200


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _argyll(tool: str) -> str:
    p = shutil.which(tool) or str(ARGYLL / tool)
    if not Path(p).exists():
        pytest.skip(f"Argyll {tool} not available")
    return p


def _run(cmd, cwd):
    subprocess.run([str(c) for c in cmd], cwd=str(cwd), check=True,
                   capture_output=True, timeout=600)


@pytest.fixture(scope="module")
def gamut_chart(qapp, tmp_path_factory):
    """A real profile-gamut chart, built by the app, fake-read, reported on.

    The one step stood in for is the sheet layout: the tab hands its .ti1 to
    ``_generate_from_ti1``, which opens windows and runs asynchronously, so the
    fixture calls the ChromIQ layout engine the same way that path does.
    Everything the two faults live behind is the app's own code.
    """
    root = tmp_path_factory.mktemp("gamutchart")
    work = root / "profile"
    work.mkdir()
    srgb = ARGYLL.parent / "ref" / "sRGB.icm"
    if not srgb.is_file():
        pytest.skip("Argyll reference profiles not available")
    # A profile of the shape a user really builds: a few hundred patches and
    # colprof's fast quality. The overshoot is a property of such a profile's
    # inverse, so a fixture built any other way would not contain the fault.
    _run([_argyll("targen"), "-d2", "-e4", "-B4", "-g16", "-s12", "-f210",
          "chart"], work)
    _run([_argyll("fakeread"), str(srgb), "chart"], work)
    _run([_argyll("colprof"), "-v0", "-ql", "-aG", "chart"], work)
    profile = work / "chart.icc"

    out = root / "out"
    settings = AppSettings()
    settings._qs = QSettings(str(root / "s.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(out))
    settings.set("argyll_bin_path", str(ARGYLL))
    fm = FileManager(settings)
    out.mkdir(parents=True, exist_ok=True)
    Project.create(out / "G", "G").current_run().ensure_dir()
    fm.set_target_name("G")
    ctl = MeasurementTargetController(fm)

    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    run = fm.project().run("run1")
    shutil.copyfile(profile, run.profile_icc)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")

    built: "list[Path]" = []

    def _fake_build(ti1, **kw):
        tab._log.clear()
        built.append(Path(ti1))
        return True

    tab._generate_from_ti1 = _fake_build      # the layout step, stood in for
    tab._gamut_count_spin.setValue(COUNT)
    gt.clear_round_trip_cache()
    tab._on_generate()                        # THE APP'S OWN GENERATE
    assert built, "Generate did not route through the gamut module"
    selection = tab._pending_gamut_selection
    assert selection is not None and selection.achieved == COUNT

    # The sheet, and then the adopt hook's own reference beside it.
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.verify_chart_ti2
    shutil.copyfile(built[0], ti2.with_suffix(".ti1"))
    from workflow.layout_engine.chart import build_chart
    build_chart(ti2.with_suffix(".ti1"), ti2.with_suffix(""),
                instrument="i1", paper="A4", randomize=False)
    tab._write_gamut_reference_after_adopt(ti2)   # THE APP'S OWN ADOPT HOOK
    from workflow.verification_print import colorimetric_reference_for
    reference = colorimetric_reference_for(ti2)
    assert reference.is_file()

    # The print and the read. The sheet goes on paper RAW (its device values
    # already carry the conversion), so the profile that chose them is the
    # perfect printer: every patch should read its own aim.
    read = root / "read"
    read.mkdir()
    shutil.copyfile(ti2.with_suffix(".ti1"), read / "sheet.ti1")
    _run([_argyll("fakeread"), str(profile), "sheet"], read)
    ti3 = ti2.with_suffix(".ti3")
    shutil.move(str(read / "sheet.ti3"), str(ti3))

    report = build_report(ti3, argyll_bin=ARGYLL)
    cref = gt.read_colorimetric_reference(reference)

    # The same measurement with no declaration at all, for the rule that a
    # chart which declares nothing must answer exactly as it did before.
    plain = root / "plain"
    plain.mkdir()
    shutil.copyfile(ti2, plain / ti2.name)
    shutil.copyfile(ti3, plain / ti3.name)
    plain_report = build_report(plain / ti3.name, argyll_bin=ARGYLL)

    return {
        "profile": profile, "selection": selection, "ti1": ti2.with_suffix(".ti1"),
        "ti2": ti2, "ti3": ti3, "reference": reference, "cref": cref,
        "report": report, "rows": row_values(report),
        "plain_report": plain_report,
    }


def _devices(path: Path):
    import numpy as np
    return np.asarray(parse_ti3(path).rgb, dtype=float)


def _corners(report) -> "dict[str, dict]":
    return {c["name"]: c for c in report["corners"]}


# --- F1: the ink amount has to exist ---------------------------------------

def test_the_profile_really_does_ask_for_ink_that_does_not_exist(gamut_chart):
    """The fixture contains the fault, or it proves nothing about the fix.

    The round trip on its own admits colours whose device values are outside
    0..100, because both legs extrapolate and the errors cancel.
    """
    labs = gt.load_master_labs()
    device, back = gt._round_trip(labs, gamut_chart["profile"], ARGYLL, "a",
                                  subprocess.run)
    import math
    admitted = [i for i, (a, b) in enumerate(zip(labs, back))
                if math.dist(a, b) <= gt.MARGIN_THRESHOLD_DE76[gt.MARGIN_SAFE]]
    unprintable = [i for i in admitted if max(device[i]) > 101.0]
    assert unprintable, (
        "this profile's inverse no longer leaves the device cube, so the "
        "fixture cannot show what the selection filter is for")


def test_no_selected_colour_needs_an_ink_amount_the_printer_has_not_got(gamut_chart):
    for _i, _lab, dev in gamut_chart["selection"].targets:
        assert all(0.0 <= v <= 100.0 for v in dev), (
            f"the selection kept an unprintable ink amount: {dev}")


def test_the_chart_and_its_reference_carry_only_printable_ink_amounts(gamut_chart):
    for name in ("ti1", "ti2"):
        rgb = _devices(gamut_chart[name])
        assert rgb.min() >= 0.0 and rgb.max() <= 100.0, (
            f"{gamut_chart[name].name} carries a device value outside 0..100; "
            "one patch past 101 makes the report read the whole chart as "
            "0..255 and divide every value by 2.55")
    for sid, dev in gamut_chart["cref"]["devices"].items():
        assert all(0.0 <= v <= 100.0 for v in dev), (
            f"the colorimetric reference carries {dev} for sample {sid}")


def test_the_chart_and_the_reference_agree_on_every_ink_amount(gamut_chart):
    """One patch, one ink amount. The chart and the reference beside it are
    written from the same selection and must never describe it two ways."""
    data = parse_ti3(gamut_chart["ti1"])
    ref_devices = gamut_chart["cref"]["devices"]
    seen = 0
    for sid, dev in zip(data.sample_ids, data.rgb):
        if sid in ref_devices:
            seen += 1
            assert tuple(round(float(v), 3) for v in dev) == \
                pytest.approx(tuple(round(float(v), 3)
                                    for v in ref_devices[sid]), abs=0.001)
    assert seen == COUNT + len(CUBE_CORNERS)


def test_every_stored_aim_is_a_colour_the_stored_ink_amount_can_make(gamut_chart):
    """THE REASON THE OUT-OF-RANGE COLOURS ARE DROPPED RATHER THAN CLAMPED.

    The reference file states, for each patch, the colour the sheet should
    come back as. Clamping an extrapolated ink amount to 100 keeps the patch
    and keeps that aim, and the aim is then one the profile itself says the
    ink cannot produce: measured on this fixture's profile, 17 of 200 patches,
    up to 8.24 ΔE00 out. The verification report would charge every one of
    those to the printer.

    The bound is the margin's own: a chart may not promise a colour further
    from its ink than the margin it was selected under. Measured after the
    fix: mean 0.032, max 0.726 over the 200 colours.
    """
    from workflow.measurement_report import ciede2000
    from workflow.xicclu_runner import forward_lab
    sel = gamut_chart["selection"]
    devices = [dev for _i, _lab, dev in sel.targets]
    aims = [lab for _i, lab, _dev in sel.targets]
    made = forward_lab(devices, gamut_chart["profile"], ARGYLL,
                       intent=gt.intent_letter(sel.intent))
    worst = max(ciede2000(tuple(a), tuple(m)) for a, m in zip(aims, made))
    assert worst <= gt.MARGIN_THRESHOLD_DE76[gt.MARGIN_SAFE], (
        f"a patch's stored aim is {worst:.2f} ΔE00 from the colour the "
        "profile says its stored ink amount makes")


def test_the_report_reads_the_chart_on_the_scale_it_was_written_on(gamut_chart):
    """The mechanism by which one unprintable patch ruins the whole report:
    ``_rgb_to_0_100`` rescales every device value by 100/255 as soon as one
    exceeds 101, and device white then reads 39.2."""
    corners = _corners(gamut_chart["report"])
    assert corners["W"]["rgb"] == [100.0, 100.0, 100.0]
    assert corners["K"]["rgb"] == [0.0, 0.0, 0.0]


def test_the_report_finds_every_cube_corner(gamut_chart):
    missing = [n for n, c in _corners(gamut_chart["report"]).items()
               if not c["present"]]
    assert not missing, (
        f"the report found no patch at these corners: {missing}")


@pytest.mark.parametrize("row", ["substrate_de00_max", "solids_de00_max",
                                 "cmy_solids_dhab_max"])
def test_the_three_reference_rows_get_a_number(gamut_chart, row):
    """These rows exist for this chart kind and nothing else can supply them."""
    got = gamut_chart["rows"][row]
    assert got["value"] is not None, (
        f"{row} came back with no value: {got['reason']}")


# --- F2: the chart's own declaration ---------------------------------------

def test_every_corner_is_the_patch_the_chart_declares(gamut_chart):
    cref = gamut_chart["cref"]
    corners = _corners(gamut_chart["report"])
    for name, target in CUBE_CORNERS:
        declared = [sid for sid in cref["corner_ids"]
                    if cref["devices"].get(sid) == pytest.approx(target, abs=0.01)]
        assert len(declared) == 1, f"the chart declares {declared} for {name}"
        assert corners[name]["declared"] is True
        assert str(corners[name]["sample"]) == declared[0], (
            f"the {name} corner was read off sample {corners[name]['sample']}, "
            f"while the chart declares sample {declared[0]}")


def test_the_composite_black_is_not_read_off_a_body_patch(gamut_chart):
    """The fault by name: a selected colour sitting at device (0,0,0) is not
    the corner, and the chart says which patch is."""
    cref = gamut_chart["cref"]
    body_black = [sid for sid, dev in cref["devices"].items()
                  if sid not in cref["corner_ids"] and max(dev) <= 0.0]
    assert body_black, (
        "this chart has no body patch at device (0,0,0), so it cannot show "
        "which of the two the report reads")
    assert str(_corners(gamut_chart["report"])["K"]["sample"]) not in body_black


def test_no_patch_is_both_a_corner_and_a_statistic(gamut_chart):
    """The wrongly chosen patch was inside the ΔE00 statistics as well, so it
    was counted twice. The declared corners are the eight excluded ones."""
    report = gamut_chart["report"]
    read_off = {str(c["sample"]) for c in report["corners"]}
    excluded = gamut_chart["cref"]["corner_ids"]
    assert read_off <= excluded, (
        f"these corners were read off patches the statistics also count: "
        f"{sorted(read_off - excluded)}")
    assert report["de00"]["n"] == COUNT, (
        "the ΔE00 statistics must hold the chart's colours and neither more "
        "nor fewer: the eight declared corners have their own section")


def test_a_chart_that_declares_nothing_answers_exactly_as_it_did(gamut_chart):
    """Nothing on anybody's disk changes unless the chart declares. With no
    reference beside it the same measurement is judged the old way: the
    corners are the nearest patch by device value, including the body patch
    the search has always preferred at (0,0,0)."""
    plain = gamut_chart["plain_report"]
    assert plain["reference_source"] == "design"
    corners = _corners(plain)
    assert all(c["declared"] is False for c in corners.values())
    import numpy as np
    rgb = np.asarray(parse_ti3(gamut_chart["ti3"]).rgb, dtype=float)
    ids = list(parse_ti3(gamut_chart["ti3"]).sample_ids)
    for name, target in CUBE_CORNERS:
        diffs = np.abs(rgb - np.array(target))
        nearest = ids[int((diffs ** 2).sum(axis=1).argmin())]
        assert str(corners[name]["sample"]) == nearest
