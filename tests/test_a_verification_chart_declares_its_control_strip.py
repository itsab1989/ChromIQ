"""A verification chart ChromIQ builds declares its own control strip.

#182, beta 22. The DETECTION of a control strip shipped in B8-397 and nothing
fed it: a chart declares a strip through a ``<stem>.control-strip.json``
sidecar or a CGATS ``CONTROL_STRIP_IDS`` keyword, and nothing in ChromIQ wrote
either, so three rows of every Measurement Report on every disk read *"this
chart declares no control strip"*. Knut, beta 22: *"It is essential that the
function that makes ChromIQ write a control-strip declaration for a chart is
implemented, tested and working."*

**THE CHARTS HERE ARE REAL.** Every one is built by ``targen`` and laid out by
``printtarg``, at four sizes, because the whole question this module answers is
*what does a real patch set actually supply*. A hand-written .ti1 with twenty-nine
tidy patches would fill the ladder perfectly and prove nothing: the sizes that
matter are the ones where it does not, and those are only knowable by building
them. 17 patches supplies 7 rungs and cannot declare; 21 supplies 11 and can.

**AND THE APP'S OWN SEQUENCE FILES THEM.** `test_the_app_declares_the_strip_*`
drives `TabChart._on_generate_finished`, which is the single funnel every
creation path reaches (Generate Chart, every preset, a loaded .ti1, a prebuilt
bundle, the patch-set editor's Apply, the gamut module, a page rebuild) — so
the guard exercises the adopt into ``verifications/``, the declaration, the log
and the warning in one go, in the order the app does them.
"""
from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import control_strip as cs                  # noqa: E402
from workflow import measurement_report as mr             # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

#: (name, patch count). 17 is under the line and 21 is over it, MEASURED on the
#: charts targen really builds — see the module docstring.
SIZES = (("tiny", 16), ("over", 20), ("mid", 100), ("big", 210))


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
                   capture_output=True, timeout=300)


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    """Four real charts, built exactly as ChromIQ builds one.

    The flags are `ChartCreator._build_targen_args`'s own defaults for a manual
    build (``-d2 -fN -e4 -B4 -G``) and `_build_printtarg_args`'s i1 / A4 / 300
    dpi, so what the ladder meets here is what it meets in the app.
    """
    root = tmp_path_factory.mktemp("controlstrip")
    out = {}
    for name, n in SIZES:
        d = root / name
        d.mkdir()
        _run([_argyll("targen"), "-v", "-d2", f"-f{n}", "-e4", "-B4", "-G",
              "chart"], d)
        _run([_argyll("printtarg"), "-v", "-ii1", "-pA4", "-t300", "chart"], d)
        out[name] = d / "chart.ti2"
        assert out[name].is_file()
    return out


def _fake_measurement(ti2: Path, ti3: Path, seed: int = 11) -> Path:
    """A .ti3 of *ti2*: the chart's own design XYZ, nudged, so every patch has a
    reference and a non-zero ΔE00. The strip statistics need both."""
    lines = ti2.read_text(encoding="utf-8").splitlines()
    fields = lines[lines.index("BEGIN_DATA_FORMAT") + 1].split()
    ix = {f: i for i, f in enumerate(fields)}
    s = lines.index("BEGIN_DATA")
    e = lines.index("END_DATA")
    rnd = random.Random(seed)
    rows = []
    for ln in lines[s + 1:e]:
        p = ln.split()
        if len(p) <= max(ix.values()):
            continue
        rgb = [p[ix[f"RGB_{c}"]] for c in "RGB"]
        xyz = [float(p[ix[f"XYZ_{c}"]]) * (1 + rnd.uniform(-0.03, 0.03))
               for c in "XYZ"]
        rows.append(f"{p[ix['SAMPLE_ID']]} {' '.join(rgb)} "
                    f"{xyz[0]:.4f} {xyz[1]:.4f} {xyz[2]:.4f}")
    ti3.write_text("\n".join([
        "CTI3   ", "", 'DESCRIPTOR "fake"', 'ORIGINATOR "ChromIQ"',
        'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"', "",
        "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT", "",
        f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA", *rows, "END_DATA", ""]), encoding="utf-8")
    return ti3


# --- the rule itself -------------------------------------------------------

def test_the_ladder_is_the_wedge_it_says_it_is():
    """29 rungs: paper, the eight cube corners, three tints of each of the six
    ink colours, three neutral greys. The help text and the message both state
    that composition, and a reader who counts must find it."""
    keys = [s.key for s in cs.SLOTS]
    assert len(keys) == len(set(keys)) == 29
    assert keys[0] == "paper"
    solids = [k for k in keys if k.startswith("solid_")]
    assert sorted(solids) == sorted(
        f"solid_{c}" for c in ("K", "C", "M", "Y", "R", "G", "B"))
    tints = [k for k in keys if k.startswith("tint_")]
    assert len(tints) == 18
    assert sorted(k for k in keys if k.startswith("grey_")) == \
        ["grey_25", "grey_50", "grey_75"]
    # the aims are the cube corners the report already reads, to the letter
    by_key = {s.key: s.device for s in cs.SLOTS}
    for name, dev in mr.CUBE_CORNERS:
        want = "paper" if name == "W" else f"solid_{name}"
        assert by_key[want] == dev, want


def test_the_tolerance_is_the_reports_own_number():
    """One answer to "is there a patch at this device aim", not two. A copied
    12.0 here would go on saying 12 after the report's changed."""
    assert cs.SLOT_TOL == mr.CORNER_PRESENT_TOL
    assert cs.declaration_path(Path("/x/y.ti2")).name == \
        "y" + mr.CONTROL_STRIP_SIDECAR


# --- what real charts of several sizes supply ------------------------------

def test_a_real_chart_too_small_cannot_declare_a_strip(charts, tmp_path):
    ti2 = tmp_path / "tiny.ti2"
    shutil.copyfile(charts["tiny"], ti2)
    result = cs.declare_for_chart(ti2)
    assert result.outcome == cs.OUTCOME_TOO_FEW
    assert result.needs_warning
    assert result.selection.n < mr.CONTROL_STRIP_MIN, result.selection.n
    assert not cs.declaration_path(ti2).exists()


def test_a_real_chart_just_over_the_line_declares_one(charts, tmp_path):
    ti2 = tmp_path / "over.ti2"
    shutil.copyfile(charts["over"], ti2)
    result = cs.declare_for_chart(ti2)
    assert result.written and not result.needs_warning
    assert mr.CONTROL_STRIP_MIN <= result.selection.n < mr.CONTROL_STRIP_P95_MIN
    assert not result.selection.p95_ready
    assert cs.declaration_path(ti2).is_file()


def test_a_bigger_real_chart_carries_the_95th_percentile_as_well(charts, tmp_path):
    for name in ("mid", "big"):
        ti2 = tmp_path / f"{name}.ti2"
        shutil.copyfile(charts[name], ti2)
        result = cs.declare_for_chart(ti2)
        assert result.written, name
        assert result.selection.p95_ready, (name, result.selection.n)


def test_the_strip_grows_with_the_chart_and_never_shrinks(charts):
    """The four sizes in order. A rule whose yield went DOWN as a chart grew
    would be picking patches by something other than what is on the sheet."""
    ns = [cs.strip_for_chart(charts[name]).n for name, _n in SIZES]
    assert ns == sorted(ns), dict(zip([s[0] for s in SIZES], ns))
    assert ns[-1] >= 20


def test_no_patch_serves_two_rungs(charts, monkeypatch):
    """Each patch fills at most one rung.

    On a real chart at the shipped tolerance this cannot be violated and the
    assertion alone proves nothing: the rungs are 25 device units apart and a
    patch has to be within 12 of one, so it is at least 13 from every other.
    A mutation that removes the once-only rule therefore passes such a check
    (measured, 2026-09-19). So the rule is exercised where it can actually
    bite: a tolerance wide enough for one patch to answer two rungs.
    """
    for name, _n in SIZES:
        ids = cs.strip_for_chart(charts[name]).ids
        assert len(ids) == len(set(ids)), name
    monkeypatch.setattr(cs, "SLOT_TOL", 60.0)
    contested = cs.strip_for_chart(charts["tiny"])
    ids = contested.ids
    assert len(ids) > 1, "the wide tolerance filled nothing to contest"
    assert len(ids) == len(set(ids)), (
        "one patch answered two rungs, so the strip counts it twice and k is "
        "not the number of patches a reader would measure")


def test_the_same_chart_declares_the_same_strip_every_time(charts):
    a = cs.strip_for_chart(charts["big"]).ids
    b = cs.strip_for_chart(charts["big"]).ids
    assert a == b and a


def test_every_rung_it_filled_is_really_within_the_tolerance(charts):
    devices = cs.chart_device_values(charts["big"])
    aim = {s.key: s.device for s in cs.SLOTS}
    for fill in cs.strip_for_chart(charts["big"]).fills:
        if fill.sample_id is None:
            continue
        d = max(abs(a - b) for a, b in zip(devices[fill.sample_id],
                                           aim[fill.key]))
        assert d <= cs.SLOT_TOL + 1e-6, (fill.key, d)


# --- the report reads back what this module writes -------------------------

def test_the_report_reads_the_declaration_back(charts, tmp_path):
    ti2 = tmp_path / "rb.ti2"
    shutil.copyfile(charts["big"], ti2)
    result = cs.declare_for_chart(ti2)
    got = mr.control_strip_declaration(ti2, ti2)
    assert got is not None and got["source"] == "sidecar"
    assert got["ids"] == result.selection.ids
    assert got["name"] == cs.STRIP_NAME


def test_the_three_rows_are_judged_on_a_chart_that_declares_one(charts, tmp_path):
    d = tmp_path / "judged"
    d.mkdir()
    ti2 = d / "chart.ti2"
    shutil.copyfile(charts["big"], ti2)
    cs.declare_for_chart(ti2)
    report = mr.build_report(_fake_measurement(ti2, d / "chart.ti3"))
    block = report["control_strip"]
    assert block["declared"] and block["eligible"] and block["p95_eligible"]
    rows = mr.row_values(report)
    for rid in ("control_strip_de00_avg", "control_strip_de00_max",
                "control_strip_de00_p95"):
        assert rows[rid]["value"] is not None, rid
        assert rows[rid]["reason"] is None, rid


def test_a_chart_that_cannot_declare_still_says_why(charts, tmp_path):
    d = tmp_path / "unjudged"
    d.mkdir()
    ti2 = d / "chart.ti2"
    shutil.copyfile(charts["tiny"], ti2)
    cs.declare_for_chart(ti2)
    report = mr.build_report(_fake_measurement(ti2, d / "chart.ti3"))
    assert report["control_strip"]["declared"] is False
    rows = mr.row_values(report)
    assert rows["control_strip_de00_avg"]["reason"] == mr.REASON_NO_CONTROL_STRIP


# --- what it must never do -------------------------------------------------

def test_a_declaration_the_chart_already_carries_is_left_alone(charts, tmp_path):
    """A sidecar somebody else wrote, and a CGATS keyword, both outrank this
    module. Overwriting either would throw away a real declaration."""
    ti2 = tmp_path / "theirs.ti2"
    shutil.copyfile(charts["big"], ti2)
    mine = cs.declaration_path(ti2)
    mine.write_text(json.dumps({"name": "Their strip",
                                "sample_ids": ["1", "2", "3"]}),
                    encoding="utf-8")
    result = cs.declare_for_chart(ti2)
    assert result.outcome == cs.OUTCOME_ALREADY
    assert json.loads(mine.read_text(encoding="utf-8"))["name"] == "Their strip"

    kw = tmp_path / "kw.ti2"
    text = charts["big"].read_text(encoding="utf-8")
    kw.write_text(text.replace('CTI2   ',
                               'CTI2   \nCONTROL_STRIP_IDS "1 2 3 4 5"', 1),
                  encoding="utf-8")
    assert cs.declare_for_chart(kw).outcome == cs.OUTCOME_ALREADY
    assert not cs.declaration_path(kw).exists()


def test_a_stale_declaration_of_ours_does_not_outlive_its_chart(charts, tmp_path):
    """A regenerate puts a different chart at the same path. The sidecar beside
    it then names patches the new chart may not have, so ChromIQ's own is
    removed when the new chart cannot declare one."""
    ti2 = tmp_path / "regen.ti2"
    shutil.copyfile(charts["big"], ti2)
    assert cs.declare_for_chart(ti2).written
    assert cs.declaration_path(ti2).is_file()
    shutil.copyfile(charts["tiny"], ti2)          # the regenerate
    assert cs.declare_for_chart(ti2).outcome == cs.OUTCOME_TOO_FEW
    assert not cs.declaration_path(ti2).exists()


def test_asking_without_writing_writes_nothing(charts, tmp_path):
    ti2 = tmp_path / "ask.ti2"
    shutil.copyfile(charts["big"], ti2)
    result = cs.declare_for_chart(ti2, write=False)
    assert result.written and not cs.declaration_path(ti2).exists()


def test_an_unreadable_chart_is_reported_and_not_guessed_at(tmp_path):
    bad = tmp_path / "bad.ti2"
    bad.write_bytes(b"\x00\x01not a chart at all")
    result = cs.declare_for_chart(bad)
    assert result.outcome == cs.OUTCOME_UNREADABLE
    assert result.needs_warning and not cs.declaration_path(bad).exists()


def test_only_the_first_data_table_of_a_ti1_is_read(charts, tmp_path):
    """A ChromIQ .ti1 carries three tables and the later two repeat SAMPLE_IDs
    that mean something else. Reading them would pair an id with the wrong
    device value, and the strip would name patches that are not there."""
    ti1 = charts["big"].with_suffix(".ti1")
    text = ti1.read_text(encoding="utf-8")
    assert text.count("BEGIN_DATA\n") >= 2, "this .ti1 has only one table"
    devices = cs.chart_device_values(ti1)
    first_n = int(text.split("NUMBER_OF_SETS")[1].split()[0])
    assert len(devices) == first_n, (len(devices), first_n)


# --- THE APP'S OWN SEQUENCE ------------------------------------------------

@pytest.fixture(scope="module")
def tab_and_project(qapp, tmp_path_factory):
    root = tmp_path_factory.mktemp("cstab")
    out = root / "out"
    out.mkdir(parents=True, exist_ok=True)
    settings = AppSettings()
    settings._qs = QSettings(str(root / "s.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(out))
    settings.set("argyll_bin_path", str(ARGYLL))
    fm = FileManager(settings)
    Project.create(out / "CS", "CS").current_run().ensure_dir()
    fm.set_target_name("CS")
    ctl = MeasurementTargetController(fm)
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(settings), fm, settings, None)
    tab.set_target_controller(ctl)
    return tab, fm, ctl


def _file_through_the_app(tab, fm, ctl, chart_ti2: Path, run_type: str,
                          monkeypatch) -> "list[tuple]":
    """Put *chart_ti2* at the run root and let the app finish a generation.

    `_on_generate_finished` is the one funnel every creation path reaches, so
    driving it drives the adopt into ``verifications/``, the declaration, the
    log line and the warning, in the app's own order.
    """
    run = fm.project().current_run()
    run.ensure_dir()
    for ext in (".ti1", ".ti2"):
        src = chart_ti2.with_suffix(ext)
        if src.is_file():
            shutil.copyfile(src, run.artefact(ext))
    tif = run.dir / f"{run.stem}_01.tif"
    src_tif = next((p for p in chart_ti2.parent.glob("*.tif")), None)
    assert src_tif is not None
    shutil.copyfile(src_tif, tif)

    shown: "list[tuple]" = []
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                        lambda *a, **kw: type("D", (), {"exec": lambda s: 0})())
    monkeypatch.setattr(type(tab), "_warn_no_control_strip",
                        lambda self, n: shown.append(
                            self._no_control_strip_message(n)))
    ctl.set_run_type(run_type)
    tab._on_generate_finished([tif])              # THE APP'S OWN FUNNEL
    return shown


def test_the_app_declares_the_strip_when_it_files_a_verification_chart(
        tab_and_project, charts, monkeypatch):
    tab, fm, ctl = tab_and_project
    shown = _file_through_the_app(tab, fm, ctl, charts["big"],
                                  RUN_TYPE_VERIFICATION, monkeypatch)
    run = fm.project().current_run()
    sidecar = cs.declaration_path(run.verify_chart_ti2)
    assert sidecar.is_file(), (
        "the app filed a verification chart and declared no control strip")
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    assert doc["generator"] == cs.GENERATOR
    assert len(doc["sample_ids"]) >= mr.CONTROL_STRIP_P95_MIN
    assert not shown, "a chart that CAN declare one must not be warned about"
    assert "control strip" in tab._log.toPlainText()


def test_the_app_warns_when_the_chart_it_filed_cannot_carry_one(
        tab_and_project, charts, monkeypatch):
    tab, fm, ctl = tab_and_project
    tab._log.clear()
    shown = _file_through_the_app(tab, fm, ctl, charts["tiny"],
                                  RUN_TYPE_VERIFICATION, monkeypatch)
    run = fm.project().current_run()
    assert not cs.declaration_path(run.verify_chart_ti2).exists()
    assert shown, "the app filed a chart that cannot carry a strip, in silence"
    title, body = shown[0]
    assert title == "This chart cannot carry a control strip"
    # The warning says WHAT IS REQUIRED and points at the Create Chart control,
    # which is the half of Knut's request a bare "cannot" would not meet.
    assert "at least 8" in body.lower()
    assert "29" in body
    assert cs.ELIGIBILITY_CONTROL in body
    assert "—" not in body


def test_a_profiling_chart_is_left_exactly_as_it_was(
        tab_and_project, charts, monkeypatch):
    """Knut scoped this to the verification chart. A profiling run's own chart
    gets no sidecar and no window."""
    tab, fm, ctl = tab_and_project
    proj = fm.project()
    run = proj.new_run()
    shown = _file_through_the_app(tab, fm, ctl, charts["big"],
                                  RUN_TYPE_PROFILING, monkeypatch)
    assert not shown
    assert not cs.declaration_path(run.chart_ti2).exists()
    # ANYWHERE under the run, not just at its root: a mutation that files a
    # profiling chart as a verification puts the declaration one folder down,
    # where a root-only check cannot see it (measured, 2026-09-19).
    assert not list(run.dir.rglob("*" + mr.CONTROL_STRIP_SIDECAR))
    assert run.chart_ti2.is_file(), (
        "the profiling chart left the run root, so this run type was filed as "
        "a verification")


# --- the message ------------------------------------------------------------

def test_the_warning_is_the_catalogue_entry_and_is_not_approved_yet():
    from workflow import measurement_messages as M
    msg = M.CATALOGUE["M-VERIFY-NO-CONTROL-STRIP"]
    assert msg.approved is False, (
        "this wording has not been reviewed; §M-PROPOSED is where it lives")
    title, body = msg.render(n=3, button=cs.ELIGIBILITY_CONTROL)
    assert "{" not in body and "}" not in body
    assert str(len(cs.SLOTS)) in body
    assert str(mr.CONTROL_STRIP_MIN) in body
    assert str(mr.CONTROL_STRIP_P95_MIN) in body
