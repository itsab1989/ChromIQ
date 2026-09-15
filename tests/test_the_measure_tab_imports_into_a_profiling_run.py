"""§I.9 — the Measure tab's IMPORT module, filing into a PROFILING run.

Katrina (Red River Paper), 2026-09-15: *"an odd thing: when doing an icc
profile, importing from another program is on the Build ICC Profile tab, and
when doing a verification, importing is on the Measurement tab. Probably makes
sense for it to be on the Measurement tab on both?"* Sebastian ruled: add the
module to the Measure tab for a profiling run as well, and leave the Build ICC
profile tab's own import exactly where it is.

THE FAULT THESE TESTS EXIST TO MAKE IMPOSSIBLE is the obvious one: the module
was built around a verification, and every path in it reached for
``Run.verify_chart_ti2``. A profiling import that inherited one line of that
would be judged against a chart it is not a measurement of — silently, because
where the two charts have the same patch count the identity check is the only
thing left that can tell them apart, and where they do NOT the user is told
their complete measurement is the wrong size. This project has shipped a
patch-mispairing fault before.

The files here are minimal CGATS tables; the real Argyll round trip and the
profile that comes out of it are the on-screen driver's job.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (                     # noqa: E402
    RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


#: The run's own chart. Eight patches, distinct device values.
_CHART = [
    (0.0, 0.0, 0.0), (100.0, 100.0, 100.0), (100.0, 0.0, 0.0),
    (0.0, 100.0, 0.0), (0.0, 0.0, 100.0), (50.0, 50.0, 50.0),
    (25.0, 75.0, 10.0), (80.0, 20.0, 60.0),
]

#: A DIFFERENT eight-patch chart, of the same size. The verification chart in
#: these fixtures is deliberately this one: a pairing bug that reached for
#: `verify_chart_ti2` would sail past a patch-COUNT check and has to be caught
#: by the identity comparison instead, which is the case worth pinning.
_OTHER_CHART = [
    (11.0, 91.0, 31.0), (22.0, 82.0, 42.0), (33.0, 73.0, 53.0),
    (44.0, 64.0, 64.0), (55.0, 55.0, 75.0), (66.0, 46.0, 86.0),
    (77.0, 37.0, 97.0), (88.0, 28.0, 8.0),
]


def _cgats(kind: str, patches) -> str:
    lines = [kind,
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "iRGB_XYZ"', "",
             "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "",
             f"NUMBER_OF_SETS {len(patches)}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(patches, 1):
        x, y, z = r * 0.6 + 5, g * 0.7 + 3, b * 0.5 + 2
        lines.append(
            f'{i} "{i}" {r:.4f} {g:.4f} {b:.4f} {x:.4f} {y:.4f} {z:.4f}')
    return "\n".join(lines + ["END_DATA", ""])


def _env(tmp_path, *, verify_chart=_OTHER_CHART):
    """A profiling-ready run: its OWN chart on disk, and a verification chart
    of a different colour beside it so the two can never be confused."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    run = fm.project().run("run1")
    run.chart_ti2.write_text(_cgats("CTI2", _CHART), encoding="utf-8")
    if verify_chart is not None:
        run.profile_icc.write_bytes(b"icc")
        run.verifications_dir.mkdir(parents=True, exist_ok=True)
        run.verify_chart_ti2.write_text(_cgats("CTI2", verify_chart),
                                        encoding="utf-8")
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    return s, fm, ctl, run


def _tab(s, fm, ctl):
    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    return tab


def _measurement(tmp_path, patches, name="from-i1profiler.ti3") -> Path:
    p = tmp_path / name
    p.write_text(_cgats("CTI3", patches), encoding="utf-8")
    return p


def _silence(tab, monkeypatch):
    """Capture every window this path can open, so nothing spins an event
    loop and every sentence shown is inspectable."""
    seen: dict = {"done": [], "refused": [], "said": [], "new_run": [],
                  "filed": [], "how_printed": []}
    monkeypatch.setattr(tab, "_show_import_done_profiling",
                        lambda run, dst: seen["done"].append((run, dst)))
    monkeypatch.setattr(tab, "_show_import_done",
                        lambda v, dst: seen["done"].append((v, dst)))
    monkeypatch.setattr(tab, "_say_on_screen",
                        lambda title, body: seen["said"].append((title, body)))
    monkeypatch.setattr(tab, "_ask_how_printed",
                        lambda ti3: seen["how_printed"].append(ti3))
    import ui.measurement_filing as mf
    monkeypatch.setattr(mf, "refuse_it_does_not_belong",
                        lambda parent, reason: seen["refused"].append(reason))
    monkeypatch.setattr(mf, "ask_to_make_a_new_run",
                        lambda parent, proj, run: (seen["new_run"].append(run.id)
                                                   or True))
    monkeypatch.setattr(mf, "say_what_was_filed",
                        lambda parent, filed: seen["filed"].append(filed))
    return seen


# ---------------------------------------------------------------------------
# The headline: which chart the file is judged against
# ---------------------------------------------------------------------------

def test_a_profiling_import_is_judged_against_the_runs_own_chart(
        qapp, tmp_path, monkeypatch):
    """The whole point of the change, stated as the thing that must be true.

    The run's chart and its verification chart hold the SAME NUMBER of patches
    and different colours, so a pipeline that reached for `verify_chart_ti2`
    cannot be saved by the patch-count check: it would refuse this file.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert not seen["refused"], (
        "a measurement of the run's OWN chart was refused, which is what "
        f"judging it against the verification chart looks like: {seen['refused']}")
    assert run.measurement_ti3.is_file()
    assert len(seen["done"]) == 1


def test_a_measurement_of_the_verification_chart_is_refused_here(
        qapp, tmp_path, monkeypatch):
    """The mutation of the test above, driven rather than reasoned about.

    Same run, same sizes; this file is a measurement of the VERIFICATION chart.
    A profiling import must refuse it, and must write nothing.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _OTHER_CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["refused"], (
        "a measurement of a different chart was accepted into a profiling run")
    assert not run.measurement_ti3.exists(), (
        "a refusal wrote a file; its promise that nothing changed is false")
    assert not seen["done"]


def test_the_chart_the_panel_names_is_the_chart_it_is_judged_against(
        qapp, tmp_path, monkeypatch):
    """The info box and the validation must read the same line.

    They used to be two separate expressions of the same idea, which is how a
    panel comes to promise a check against one chart while the code performs it
    against another. Both ask `_import_chart_for` now.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    assert tab._import_chart_for(run) == run.chart_ti2
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._import_chart_for(run) == run.verify_chart_ti2
    assert tab._import_chart_for(None) is None


# ---------------------------------------------------------------------------
# Where it lands
# ---------------------------------------------------------------------------

def test_it_lands_on_the_runs_canonical_stem(qapp, tmp_path, monkeypatch):
    """§I.9 I.7. Not the source file's name: the report finds a measurement's
    chart by the stem, and anything else falls back to `reference_source:
    device` without saying so."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    src = _measurement(tmp_path, _CHART, name="whatever-i1profiler-called-it.ti3")
    tab._import_path = src
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert run.measurement_ti3.is_file()
    assert run.measurement_ti3.stem == run.chart_ti2.stem
    assert not (run.dir / src.name).exists()
    # The user's own file is never moved or changed.
    assert src.is_file()
    assert src.read_text(encoding="utf-8") == _cgats("CTI3", _CHART)


def test_it_never_lands_in_a_verification_folder(qapp, tmp_path, monkeypatch):
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert not list(run.verifications_dir.glob("*/*.ti3")), (
        "a profiling import made a dated verification")


def test_it_is_not_stamped_as_a_verification(qapp, tmp_path, monkeypatch):
    """`mark_verification_ti3` stamps CHROMIQ_VERIFICATION "true", which is how
    Build Profile knows to refuse a file. A profiling import that inherited
    that line would file a measurement no profile could ever be built from."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    text = run.measurement_ti3.read_text(encoding="utf-8")
    assert "CHROMIQ_VERIFICATION" not in text


def test_it_does_not_write_into_the_reads_folder(qapp, tmp_path, monkeypatch):
    """§I.9: an import is a standalone read, not a member of an averaging set.

    The run is given a leftover `reads/` first, exactly as a session abandoned
    earlier would leave one, because the question is whether the import joins
    that set. It must not: it lands where a standalone read lands, and the
    leftovers stay untouched until somebody opts into averaging again.
    """
    s, fm, ctl, run = _env(tmp_path)
    run.reads_dir.mkdir(parents=True, exist_ok=True)
    leftover = run.reads_dir / "read1.ti3"
    leftover.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab = _tab(s, fm, ctl)
    _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert run.measurement_ti3.is_file()
    assert sorted(p.name for p in run.reads_dir.glob("*.ti3")) == ["read1.ti3"]
    assert leftover.read_text(encoding="utf-8") == _cgats("CTI3", _CHART)


# ---------------------------------------------------------------------------
# A measurement that is already there
# ---------------------------------------------------------------------------

def test_an_existing_measurement_is_never_written_over(qapp, tmp_path,
                                                       monkeypatch):
    """§I.9's rule, and the fault it was written after: overwriting the `.ti3`
    orphans the run's `.icc` and every report describing it, while leaving them
    on screen looking current. The road to a second result is a new place to
    put it."""
    s, fm, ctl, run = _env(tmp_path)
    kept = _cgats("CTI3", _CHART).replace("END_DATA", "END_DATA\n")
    run.measurement_ti3.write_text(kept, encoding="utf-8")
    run.built_profile_icc().write_bytes(b"a profile built from it")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["new_run"] == ["run1"], (
        "the duplicate question was not asked about the run that was full")
    assert run.measurement_ti3.read_text(encoding="utf-8") == kept, (
        "run 1's measurement was written over")
    # …and the copy holds the import, with the chart and nothing else.
    proj = fm.project()
    made = [r for r in proj.all_runs() if r.id != "run1"]
    assert len(made) == 1, [r.id for r in proj.all_runs()]
    new = made[0]
    assert new.measurement_ti3.is_file()
    assert new.chart_ti2.is_file()
    assert not new.built_profile_icc().exists(), (
        "the copy carries a profile that was built from a different "
        "measurement, which is the orphan §I.9 forbids")


def test_declining_the_new_run_writes_nothing(qapp, tmp_path, monkeypatch):
    s, fm, ctl, run = _env(tmp_path)
    kept = _cgats("CTI3", _CHART)
    run.measurement_ti3.write_text(kept, encoding="utf-8")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    import ui.measurement_filing as mf
    monkeypatch.setattr(mf, "ask_to_make_a_new_run",
                        lambda parent, proj, run: False)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert run.measurement_ti3.read_text(encoding="utf-8") == kept
    assert [r.id for r in fm.project().all_runs()] == ["run1"], (
        "a cancelled import left a run behind")
    assert not seen["done"]


def test_the_panel_says_so_before_the_button_is_pressed(qapp, tmp_path):
    """A person who learns about the duplicate only in the window that asks it
    has already committed to the act."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    tab._update_import_panel()
    assert "already holds a measurement" not in tab._import_box_body.text()
    run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab._update_import_panel()
    assert "already holds a measurement" in tab._import_box_body.text()
    assert "new run" in tab._import_box_body.text()


# ---------------------------------------------------------------------------
# What the panel says
# ---------------------------------------------------------------------------

def test_a_profiling_reader_is_never_told_about_verifications(qapp, tmp_path):
    """Every sentence the module shows in a profiling run, swept for the word.

    The module was built for verifications, so its info box, its ⓘ help and its
    destination line all spoke in those terms. A profiling reader meeting
    "verification chart" or "dated verification folder" is being told about an
    act they are not performing.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    tab._import_path = tmp_path / "some-measurement.mxf"
    tab._update_import_panel()

    shown = "\n".join([
        tab._import_box_body.text(),
        tab._import_destination_text(run),
        tab._import_help_body(verifying=False),
    ]).lower()
    assert "verif" not in shown, (
        "a profiling run's IMPORT module speaks about verifications:\n"
        + shown)
    # …and it names the run's own chart instead.
    assert run.chart_ti2.name in tab._import_box_body.text()


def test_the_help_follows_the_run_type(qapp, tmp_path):
    """A ⓘ built once describes whichever run type was on the bar when the tab
    was constructed, which for a restored session is not the one on screen."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    tab._update_import_panel()
    assert "verification chart" not in tab._import_help_btn._body
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._update_import_panel()
    assert "verification chart" in tab._import_help_btn._body


def test_the_how_printed_question_is_not_asked_for_a_profiling_sheet(
        qapp, tmp_path, monkeypatch):
    """M-HOW-PRINTED offers "with colour management … with this run's profile
    applied", which cannot be true of a profiling chart: the profile is what
    the measurement is FOR."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert not seen["how_printed"]


# ---------------------------------------------------------------------------
# §I.10 — partial in, oversized out
# ---------------------------------------------------------------------------

def test_a_partial_measurement_is_filed_and_both_counts_are_stated(
        qapp, tmp_path, monkeypatch):
    """§I.10: fewer readings than the chart has patches is FILED, not refused.

    *"A file ChromIQ wrote must be a file ChromIQ will take back."* The partial
    sentence comes from the shared `say_what_was_filed`, so the two doors state
    it identically or not at all.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART[:5], name="partial.ti3")
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert not seen["refused"]
    assert run.measurement_ti3.is_file()
    assert seen["filed"] == [run.measurement_ti3], (
        "the partial notice was not reached, so the person is not told that "
        "part of the chart was never measured")


def test_more_readings_than_the_chart_has_patches_is_refused(
        qapp, tmp_path, monkeypatch):
    """Not a partial: a measurement of something else."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART + _OTHER_CHART,
                                    name="too-many.ti3")
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["refused"]
    assert not run.measurement_ti3.exists()


# ---------------------------------------------------------------------------
# The guards before anything is converted
# ---------------------------------------------------------------------------

def test_a_run_with_no_chart_cannot_accept_anything(qapp, tmp_path,
                                                    monkeypatch):
    """Without a chart `assess()` has nothing to compare against and accepts
    ANY file in silence — the exact fault the other door was given this guard
    for (driven 2026-09-01: "a six-patch file bearing no relation to anything
    went into a real project with not one word on screen")."""
    s, fm, ctl, run = _env(tmp_path)
    run.chart_ti2.unlink()
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["said"], "nothing was said about a run with no chart"
    assert not run.measurement_ti3.exists()
    assert not seen["done"]


def test_a_new_run_on_the_bar_is_explained_not_imported_into(
        qapp, tmp_path, monkeypatch):
    """§I.1, the same guard Start uses: "New run" names a run that does not
    exist yet, so there is nothing to file into."""
    s, fm, ctl, run = _env(tmp_path)
    ctl.set_profile_run("")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    said: list = []
    monkeypatch.setattr("ui.tabs.tab_measure.inform",
                        lambda parent, title, body: said.append(title))
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert said, "the New-run guard said nothing"
    assert not seen["done"]
    assert not run.measurement_ti3.exists()


# ---------------------------------------------------------------------------
# The run type moving under the module
# ---------------------------------------------------------------------------

def test_switching_run_type_keeps_the_module_honest(qapp, tmp_path):
    """Profiling → Verification → Profiling, with the module on screen the
    whole time. Each state must describe itself, and the module must never be
    left showing the other one's words."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._switch_mode("import")
    assert tab._stack.currentIndex() == 2
    assert run.chart_ti2.name in tab._import_box_body.text()

    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    assert tab._stack.currentIndex() == 2, "the module was left for no reason"
    assert run.verify_chart_ti2.name in tab._import_box_body.text()

    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._stack.currentIndex() == 2
    assert run.chart_ti2.name in tab._import_box_body.text()
    assert "verif" not in tab._import_box_body.text().lower()


# ---------------------------------------------------------------------------
# Challenge round 1 — what the import leaves behind on screen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("run_is_already_full", [False, True],
                         ids=["an ordinary import", "one that duplicates"])
def test_the_import_does_not_then_ask_about_the_file_it_just_filed(
        qapp, tmp_path, monkeypatch, run_is_already_full):
    """Found by driving it on screen, 2026-09-15.

    An import into a run that is already full duplicates the run, so the chart
    on screen CHANGES, so `set_ti1_path` queues `_maybe_offer_existing_overlay`
    — and one second after "The measurement was imported" the person was asked
    "This chart already has a measurement. Show the overlay? Refine / resume
    it?", with a warning that starting a new measurement would REPLACE it.
    Every word of it true, none of it a question they asked. It blocked the
    on-screen driver outright, which is how it was caught.

    Driven rather than read: the real `set_ti1_path` runs, the real queue runs,
    and the offer is called the way the event loop calls it.
    """
    s, fm, ctl, run = _env(tmp_path)
    if run_is_already_full:
        run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    # The filing helper's ending is the real one here: it is what calls back
    # into the tab, and the callback is what loads the new run's chart.
    import ui.measurement_filing as mf
    monkeypatch.setattr(mf, "say_what_was_filed", lambda parent, filed: None)
    offered: list = []
    real_offer = tab._maybe_offer_existing_overlay

    def _count_the_offer():
        # Run the REAL gate, and record only whether it decided to open a
        # window. Patching it out entirely would test nothing.
        before = getattr(tab, "_offer_open", False)
        opened = {"yes": False}
        from PyQt6.QtWidgets import QDialog
        real_exec = QDialog.exec

        def _no_modal(self_dlg):
            opened["yes"] = True
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", _no_modal)
        try:
            real_offer()
        finally:
            monkeypatch.setattr(QDialog, "exec", real_exec)
        if opened["yes"]:
            offered.append(True)

    monkeypatch.setattr(tab, "_maybe_offer_existing_overlay", _count_the_offer)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()
    # Whatever the import queued, let it run — that is the turn of the event
    # loop the offer was scheduled for.
    qapp.processEvents()
    tab._maybe_offer_existing_overlay()

    assert seen["new_run"] == (["run1"] if run_is_already_full else [])
    assert not offered, (
        "the app asked whether to refine the measurement the import had just "
        "filed, one window after telling the person it had filed it")


def test_the_silence_is_scoped_to_the_run_the_import_went_into(
        qapp, tmp_path, monkeypatch):
    """The remedy must not switch the window off everywhere.

    `_offer_silenced` is keyed by project + run (Knut, #131), so silencing the
    run the import landed in leaves every OTHER run asking. A fix that cleared
    the set, or set a global flag, would take a window away from journeys that
    have nothing to do with importing.
    """
    s, fm, ctl, run = _env(tmp_path)
    run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    import ui.measurement_filing as mf
    monkeypatch.setattr(mf, "say_what_was_filed", lambda parent, filed: None)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert len(tab._offer_silenced) == 1, (
        f"the import silenced {len(tab._offer_silenced)} scopes; it may only "
        "silence the one run it filed into")
    # …and run 1, which the import did NOT write to, is not among them.
    ctl.set_profile_run("run1")
    assert tab._replace_warning_scope() not in tab._offer_silenced, (
        "the import silenced the window for a run it never touched")


# ---------------------------------------------------------------------------
# Challenge round 2 — the promises the done window makes
# ---------------------------------------------------------------------------

def test_the_tab_that_builds_from_it_is_actually_holding_it(
        qapp, tmp_path, monkeypatch):
    """A MESSAGE IS A PROMISE, and this one was not kept.

    The done window says "You can build a profile from it now on the Build ICC
    profile tab" and carries a **Build the profile** button. That button
    emitted `proceed_to_profile`, which changes tab and nothing else, so the
    person arrived on a tab still holding whatever it held before.

    `measure_finished` is the line that hands a measurement over — a native
    session emits it before it offers to go to tab 4, and
    `MainWindow._on_measure_done` turns it into `set_ti3_path(ti3,
    propagate=False)`. The import must emit it too, and BEFORE the done window,
    so the tab is armed whether or not the button is pressed.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    handed: list = []
    tab.measure_finished.connect(handed.append)
    order: list = []
    tab.measure_finished.connect(lambda _p: order.append("handed over"))
    monkeypatch.setattr(tab, "_show_import_done_profiling",
                        lambda r, dst: (order.append("done window"),
                                        seen["done"].append((r, dst))))
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert handed == [run.measurement_ti3], (
        "the import never handed the measurement to the tab that builds from "
        "it, while its own window said that tab could build from it")
    assert order == ["handed over", "done window"], (
        f"the hand-over must happen before the window that promises it: {order}")


def test_an_import_does_not_join_a_live_averaging_set(qapp, tmp_path,
                                                      monkeypatch):
    """§I.9: an imported file has no position in a sequence of reads taken here.

    A set left live by an earlier session in this tab would otherwise still be
    live, and the next read would be averaged with a sheet measured somewhere
    else, on another instrument, on another day. Opting into averaging again
    starts a clean set, exactly as it does after any standalone read.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    _silence(tab, monkeypatch)
    # THE OTHER ROUTE IS CLOSED ON PURPOSE. `set_ti1_path` clears the flag when
    # the chart CHANGES, which happens on the duplicating import and covers the
    # ordinary one by luck — the shared ending happens to reload the chart. A
    # mutation that removed the import's own line stayed green because of it,
    # so the belt is tested where the braces cannot reach: with the chart
    # load stubbed out, only the import itself can clear the flag.
    monkeypatch.setattr(tab, "set_ti1_path", lambda p: None)
    tab._averaging_active = True
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert tab._averaging_active is False, (
        "an averaging set was left live across an import, so the next read "
        "would be averaged with a measurement made on another instrument")


def test_a_full_run_with_no_reachable_project_says_so(qapp, tmp_path,
                                                      monkeypatch):
    """A button that does nothing at all reads as a broken app.

    Without a project there is nowhere to put the duplicate §I.9 requires, so
    the import cannot go on — and it must say that rather than return.
    """
    s, fm, ctl, run = _env(tmp_path)
    run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    # The run has to be REACHABLE for the import to get as far as the branch
    # under test, and the project must not be: `_guard_run` falls back to the
    # run the loaded chart sits in, which is exactly the shape this covers.
    tab.set_ti1_path(run.chart_ti2)
    monkeypatch.setattr(ctl, "project_or_none", lambda: None)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["said"], "the import gave up without a word"
    assert not seen["done"]


def test_an_import_accrues_a_dated_report_like_a_read_made_here(
        qapp, tmp_path, monkeypatch):
    """Found by driving it (round 4): the hand-over signal also saves the dated
    accuracy report, because `measure_finished` is wired to
    `_maybe_save_measurement_report`.

    Written down as a decision rather than left as a side effect. It is what
    the feature wants — Knut's reason for dated reports is that they accrue for
    over-time comparison, and an imported measurement carries the date it was
    MEASURED rather than converted — and it obeys the person's own Settings
    switch, which is the half that makes it safe.
    """
    s, fm, ctl, run = _env(tmp_path)
    s.set("save_measurement_report", True)
    tab = _tab(s, fm, ctl)
    _silence(tab, monkeypatch)
    # Observed through the REPORT ON DISK, not through the method: the signal
    # is connected to a bound method in __init__, so patching the attribute
    # afterwards changes nothing and a test that did would pass for ever.
    asked: list = []
    import workflow.measurement_report as mr
    real_save = mr.save_report
    monkeypatch.setattr(
        "ui.tabs.tab_measure.TabMeasure._say_report_not_saved",
        lambda self, exc: asked.append(("failed", exc)))
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    reports = sorted((run.dir / "reports").glob("report_*.json")) \
        if (run.dir / "reports").is_dir() else []
    assert reports or asked, (
        "an import neither wrote a dated report nor said it could not, so "
        "imported runs drop out of the over-time comparison the others are in")
    assert not asked, f"the report could not be written: {asked}"


# ---------------------------------------------------------------------------
# Challenge round 6 — the doors that refuse
# ---------------------------------------------------------------------------

def test_the_runs_own_chart_cannot_be_imported_as_its_measurement(
        qapp, tmp_path, monkeypatch):
    """Found by driving the refusal doors, 2026-09-15.

    The chart and the measurement live in the same folder under the same stem
    and are both CGATS tables, so picking the wrong one is an easy slip. And
    nothing downstream could tell: printtarg writes the chart's AIM XYZ into
    the `.ti2`, so it parses as a full set of readings, the patch count matches
    exactly because it IS the same file, and the identity check compares the
    chart with itself and reports a flawless match. It was filed in silence as
    the run's measurement, and a profile built from it would describe a printer
    that had never printed anything.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    tab._import_path = run.chart_ti2
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["refused"], "the run's own chart was accepted as its measurement"
    assert "chart, not a measurement" in seen["refused"][0], seen["refused"]
    assert not run.measurement_ti3.exists()
    assert not seen["done"]


def test_a_chart_is_refused_by_what_the_file_says_it_is(tmp_path):
    """At the level both doors share, and by the file's own first line.

    A suffix test would be worthless: the slip this guards against is a file
    whose CONTENTS are a chart, and the Build ICC profile door accepts a
    measurement under any name at all.
    """
    from workflow.measurement_import import _cgats_table_kind, assess
    # `tmp_path`, never `tempfile.mkdtemp()`: an unprefixed temp folder is one
    # the suite's own sweep cannot see, and 62,548 of them once cost 198 GB.
    d = tmp_path
    chart = d / "looks-like-a-measurement.ti3"
    chart.write_text(_cgats("CTI2", _CHART), encoding="utf-8")
    real = d / "actually-a-measurement.ti3"
    real.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    assert _cgats_table_kind(chart) == "CTI2"
    assert _cgats_table_kind(real) == "CTI3"
    assert not assess(chart, chart).ok, (
        "a chart named .ti3 was accepted as a measurement of itself")
    assert assess(real, chart).ok, (
        "a real measurement was refused by the chart guard")


def test_the_report_lands_under_the_run_the_import_went_into(
        qapp, tmp_path, monkeypatch):
    """Re-checked after the Measurement Report window was taught to file under
    the run it was asked from (a report asked on run 2 was written into run 1).

    That fix is in the WINDOW; the report an import accrues comes from
    `_maybe_save_measurement_report`, which files beside the `.ti3` it is
    handed. The case worth driving is the one where those two disagree: an
    import into a full run lands in a run the import just CREATED, so a
    hand-over carrying the wrong path would file the new run's numbers under
    the old run and leave the new one saying no report had been generated for
    it — the exact shape of the fault that was just fixed next door.
    """
    s, fm, ctl, run = _env(tmp_path)
    s.set("save_measurement_report", True)
    run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    import ui.measurement_filing as mf
    monkeypatch.setattr(mf, "say_what_was_filed", lambda parent, filed: None)
    before = sorted((run.dir / "reports").glob("report_*.json")) \
        if (run.dir / "reports").is_dir() else []
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert seen["new_run"] == ["run1"], "the duplicate was not taken"
    made = [r for r in fm.project().all_runs() if r.id != "run1"]
    assert len(made) == 1, [r.id for r in fm.project().all_runs()]
    new = made[0]
    mine = sorted((new.dir / "reports").glob("report_*.json")) \
        if (new.dir / "reports").is_dir() else []
    assert mine, (
        "no report was filed under the run the import actually went into")
    after = sorted((run.dir / "reports").glob("report_*.json")) \
        if (run.dir / "reports").is_dir() else []
    assert after == before, (
        "the import filed its report under run 1, which is not the run the "
        f"measurement went into: {after}")


def _spectral_only(tmp_path, patches, chart_names, name="no-device.ti3"):
    """A measurement the way i1Profiler's measure tool writes one: patch NAMES
    and colour, and no device values at all, because it read a chart it did not
    generate and has no colour space to express them in."""
    # SAMPLE_LOC, which is where txt2ti3 puts i1Profiler's patch name and what
    # `measurement_pairing` keys on; SAMPLE_NAME alone reads as "no patch names
    # either" and the file is refused before the question is ever asked.
    lines = ["CTI3", 'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "XYZ"', "",
             "NUMBER_OF_FIELDS 5", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", "",
             f"NUMBER_OF_SETS {len(patches)}", "BEGIN_DATA"]
    for i, ((r, g, b), loc) in enumerate(zip(patches, chart_names), 1):
        x, y, z = r * 0.6 + 5, g * 0.7 + 3, b * 0.5 + 2
        lines.append(f'{i} "{loc}" {x:.4f} {y:.4f} {z:.4f}')
    p = tmp_path / name
    p.write_text("\n".join(lines + ["END_DATA", ""]), encoding="utf-8")
    return p


def test_a_measurement_with_no_device_values_is_imported_here_too(
        qapp, tmp_path, monkeypatch):
    """The verification door learned this on 2026-09-12, after a user's own
    complete i1iO reading was refused with "No device RGB columns". This door
    was written the same week and had not learned it, so the identical file
    would have been refused one door along — caught by that fix's own test
    noticing the split.

    The pairing is keyed on the patch NAME, the chart supplies the device
    values, and the person is asked first because it is the one thing ChromIQ
    cannot check.
    """
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    asked: list = []
    monkeypatch.setattr(
        tab, "_ask_import_question",
        lambda msg, go, **kw: (asked.append((msg.id, kw)) or True))
    tab._import_path = _spectral_only(
        tmp_path, _CHART, [str(i) for i in range(1, len(_CHART) + 1)])
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert asked and asked[0][0] == "M-IMPORT-DEVICE-FROM-CHART", (
        f"the person was not asked before the chart supplied the values: {asked}")
    assert asked[0][1]["chart"] == run.chart_ti2.name, (
        "the question named the wrong chart")
    assert not seen["refused"], seen["refused"]
    assert run.measurement_ti3.is_file(), (
        "a spectral-only i1Profiler export was refused by the profiling door")
    filed = run.measurement_ti3.read_text(encoding="utf-8")
    assert "RGB_R" in filed, (
        "the copy was filed without the device values the chart supplies")


def test_saying_no_to_that_question_writes_nothing(qapp, tmp_path,
                                                   monkeypatch):
    """It is a question, so No has to mean no."""
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    monkeypatch.setattr(tab, "_ask_import_question",
                        lambda msg, go, **kw: False)
    tab._import_path = _spectral_only(
        tmp_path, _CHART, [str(i) for i in range(1, len(_CHART) + 1)])
    tab._switch_mode("import")

    tab._on_import_measurement()

    assert not run.measurement_ti3.exists()
    assert not seen["done"]


# ---------------------------------------------------------------------------
# §I.9 step 4: the one refusal that happens AFTER the duplicate was made
# ---------------------------------------------------------------------------

def _stale_stored_chart(run) -> None:
    """The state "Stored chart differs" is asked about: a run whose stored copy
    of its chart is not the chart it holds now.

    Reached in the app by regenerating the chart, or by answering "Keep stored
    chart" once, which ChromIQ records as ``chart_snapshot_stale``.
    """
    from workflow.chart_slot import slot_for
    from workflow.verify_chart_snapshot import snapshot_slot
    snapshot_slot(slot_for(run))
    run.chart_ti2.write_text(
        run.chart_ti2.read_text(encoding="utf-8")
        + '\nKEYWORD "CHROMIQ_EDITED"\n', encoding="utf-8")


def _second_import_stopped_at_the_chart_question(tmp_path, monkeypatch,
                                                 *, answer="cancel"):
    """Import into a full run, answer "Make a new run", then answer the
    stored-chart question with *answer*. Returns (fm, ctl, run1, seen)."""
    s, fm, ctl, run = _env(tmp_path)
    run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    _stale_stored_chart(run)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    # the real `_snapshot_profiling_chart` runs; only the WINDOW is answered
    monkeypatch.setattr(tab, "_profiling_overwrite_choice",
                        lambda r: answer)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")
    tab._on_import_measurement()
    return fm, ctl, run, seen


def test_stopping_at_the_stored_chart_question_undoes_the_run_it_made(
        qapp, tmp_path, monkeypatch):
    """THE FAULT. Step 3 duplicates the run and points the bar at the copy;
    step 4 said `return` with no rollback, so a person who pressed Cancel on
    "Stored chart differs" was left with an empty Run 2 on disk and in
    `project.json`. Driven on screen with every window answered by clicking its
    own button (combined round 4, `N-result.json`).

    MUTATION: put step 4 back to a bare `return` and this goes red with two
    runs, the second holding nothing.
    """
    fm, _ctl, run, _seen = _second_import_stopped_at_the_chart_question(
        tmp_path, monkeypatch)
    ids = [r.id for r in fm.project().all_runs()]
    assert ids == ["run1"], (
        "a stopped import left %r behind" % (ids,))
    assert not [d for d in (fm.project().root / "runs").iterdir()
                if d.is_dir() and d.name != "run1"], (
        "the run folder is still on disk even though the manifest forgot it")


def test_stopping_there_puts_the_bar_back_on_the_run_the_person_was_on(
        qapp, tmp_path, monkeypatch):
    """The bar is moved to the copy BEFORE the snapshot step, deliberately, so
    the rollback has to move it back. Leaving it on a run that no longer exists
    is how "Location being edited" came to name a folder that was not there.

    MUTATION: drop the `ctl.set_profile_run(was_current)` line and this goes
    red with the bar on run2.
    """
    _fm, ctl, _run, _seen = _second_import_stopped_at_the_chart_question(
        tmp_path, monkeypatch)
    assert ctl.target.profile_run == "run1", (
        "the bar was left on %r" % (ctl.target.profile_run,))


def test_stopping_there_says_so_rather_than_doing_nothing(
        qapp, tmp_path, monkeypatch):
    """A button that does nothing at all reads as a broken app — this door's
    own comment, written after the same fault on four other routes.

    MUTATION: remove the `_say_on_screen` call and this goes red.
    """
    _fm, _ctl, _run, seen = _second_import_stopped_at_the_chart_question(
        tmp_path, monkeypatch)
    assert seen["said"], "nothing at all was said"
    title, body = seen["said"][-1]
    assert "not imported" in title.lower()
    assert "nothing has been changed" in body.lower()
    assert not seen["done"], "the import reported success after being stopped"


def test_the_measurement_is_not_filed_when_the_question_is_stopped(
        qapp, tmp_path, monkeypatch):
    """…and the run that was full keeps exactly what it had."""
    kept = None
    fm, _ctl, run, _seen = _second_import_stopped_at_the_chart_question(
        tmp_path, monkeypatch)
    assert run.measurement_ti3.is_file()
    assert 'CHROMIQ_EDITED' in run.chart_ti2.read_text(encoding="utf-8"), (
        "run 1's own chart was changed by an import that was stopped")


def test_answering_the_chart_question_still_files_into_the_new_run(
        qapp, tmp_path, monkeypatch):
    """THE BEHAVIOUR THE ROLLBACK MUST NOT EAT. Answering "Replace the stored
    chart" goes on, and the copy gets the measurement.

    MUTATION: roll the run back unconditionally and this goes red.
    """
    fm, ctl, run, seen = _second_import_stopped_at_the_chart_question(
        tmp_path, monkeypatch, answer="go")
    ids = [r.id for r in fm.project().all_runs()]
    assert len(ids) == 2, ids
    made = [r for r in fm.project().all_runs() if r.id != "run1"][0]
    assert made.measurement_ti3.is_file(), (
        "the import did not file into the run it made")
    assert ctl.target.profile_run == made.id


# ---------------------------------------------------------------------------
# §I.7 — the copy itself is refused, ONE LINE past the refusal round 4 fixed
# ---------------------------------------------------------------------------

def _second_import_whose_copy_is_refused(tmp_path, monkeypatch):
    """Import into a full run, answer "Make a new run", and let the copy that
    files the measurement fail — a full disk, a read-only folder, a share that
    has gone away. Returns (fm, ctl, run1, seen)."""
    import shutil as _sh
    s, fm, ctl, run = _env(tmp_path)
    run.measurement_ti3.write_text(_cgats("CTI3", _CHART), encoding="utf-8")
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    real = _sh.copy2

    def _copy2(src, dst, *a, **k):
        if str(dst).endswith(run.measurement_ti3.name) and "runs" in str(dst):
            raise OSError(28, "No space left on device")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(_sh, "copy2", _copy2)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")
    tab._on_import_measurement()
    return fm, ctl, run, seen


def test_a_refused_copy_undoes_the_run_the_import_made(qapp, tmp_path,
                                                       monkeypatch):
    """THE FAULT (combined round 5, B8-214). Round 4 gave step 4's refusal the
    rollback every other refusal on this door has; the copy at step 5 still
    said "nothing has been changed" over a run it had just made, while the
    SIBLING door has always undone the run at exactly this failure.

    Driven on screen with the copy refused once
    (`~/Desktop/ChromIQ-beta18-proof/combined-round-5/F-result.json`,
    `F1-after-the-refused-copy.png`): run 2 was on disk and in `project.json`,
    `current_run` pointed at it, and the bar read "Location being edited:
    runs/run2/".

    MUTATION: drop the `_undo_the_run` call and this goes red with two runs.
    """
    fm, _ctl, _run, _seen = _second_import_whose_copy_is_refused(
        tmp_path, monkeypatch)
    ids = [r.id for r in fm.project().all_runs()]
    assert ids == ["run1"], "a refused copy left %r behind" % (ids,)
    assert not [d for d in (fm.project().root / "runs").iterdir()
                if d.is_dir() and d.name != "run1"], (
        "the run folder is still on disk even though the manifest forgot it")


def test_a_refused_copy_puts_the_bar_back(qapp, tmp_path, monkeypatch):
    """MUTATION: drop the `ctl.set_profile_run(was_current)` line and this goes
    red with the bar standing on a run that no longer exists."""
    _fm, ctl, _run, _seen = _second_import_whose_copy_is_refused(
        tmp_path, monkeypatch)
    assert ctl.target.profile_run == "run1", (
        "the bar was left on %r" % (ctl.target.profile_run,))


def test_a_refused_copy_says_what_it_actually_did(qapp, tmp_path, monkeypatch):
    """A MESSAGE IS A PROMISE. "Nothing has been changed" was false while the
    run stayed; now the run is really gone and the sentence says so.

    MUTATION: put the single unconditional sentence back and this goes red.
    """
    _fm, _ctl, _run, seen = _second_import_whose_copy_is_refused(
        tmp_path, monkeypatch)
    assert seen["said"], "nothing at all was said"
    title, body = seen["said"][-1]
    assert "could not write" in title.lower(), title
    assert "nothing has been changed" in body.lower(), body
    assert "removed again" in body.lower(), (
        "the window does not say the run it made was taken away: %r" % body)
    assert "no space left on device" in body.lower(), body
    assert not seen["done"], "the import reported success after failing"


def test_the_run_that_was_full_keeps_what_it_had(qapp, tmp_path, monkeypatch):
    fm, _ctl, run, _seen = _second_import_whose_copy_is_refused(
        tmp_path, monkeypatch)
    assert run.measurement_ti3.read_text(encoding="utf-8") == \
        _cgats("CTI3", _CHART)


def test_a_refused_copy_with_no_run_to_undo_still_says_the_plain_sentence(
        qapp, tmp_path, monkeypatch):
    """An EMPTY run needs no duplicate, so there is nothing to roll back and
    the window must not claim a run was removed.

    MUTATION: make the sentence unconditional the other way and this goes red.
    """
    import shutil as _sh
    s, fm, ctl, run = _env(tmp_path)
    tab = _tab(s, fm, ctl)
    seen = _silence(tab, monkeypatch)
    real = _sh.copy2

    def _copy2(src, dst, *a, **k):
        if str(dst).endswith(run.measurement_ti3.name) and "runs" in str(dst):
            raise OSError(13, "Permission denied")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(_sh, "copy2", _copy2)
    tab._import_path = _measurement(tmp_path, _CHART)
    tab._switch_mode("import")
    tab._on_import_measurement()
    assert [r.id for r in fm.project().all_runs()] == ["run1"]
    title, body = seen["said"][-1]
    assert "nothing has been changed" in body.lower()
    assert "removed again" not in body.lower(), (
        "no run was made, so none can have been removed: %r" % body)
