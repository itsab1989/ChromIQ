"""#182 C1/C2 (Knut, 2026-10-02, 5943085974): after a run delete, a saved
report says the run its folder has now, and NOTHING ELSE changes.

    "leave the functionality as is today. Even though that means that the
    run number changes, that is an acceptable compromise, since the run
    numbers were renamed due to a delete. However, you need to verify that
    no other information than the run number is changed in the 'Report
    shown' name or the report content text."

So the run-number freeze of 93d9dcaf / 6a29257e is gone (a saved report
writes no ``saved_as``), and these tests hold the rest of the ruling: for
EVERY saved report of Knut's shape (runs 1 to 5, a dated verification in
run 5 with the Measure tab's automatic report and a report from before the
document block), the "Report shown" entry, the page text and the PDF text
after runs 1 to 4 are deleted are, word for word, the ones before with the
run number 5 read as 1. Driven through the real writers: the Measure tab's
automatic report, the bar's run delete (`core.run_delete.delete_run`, the
Trash sandboxed), the report window's list, page and PDF.

C4 (Knut, same comment): *"A report in a run is only related to that run.
Duplicating a run will make a new run, and any reports in that run will then
only relate to that new run"*: the last test, through `Project.duplicate_run`.

MUTATIONS, each proved red (L_impl_knut_rulings/MUTATIONS.md):
* `_run_number_for` reading nothing; the freeze put back (it answering 5
  after the delete); `_renumber_entry` leaving the reference on the old run;
* `duplicate_run` not calling `_copied_reports_name_the_new_run`; the
  duplicate plan mapping no run; the plan rewriting the SOURCE run's
  reports; a copy keeping its original's document id.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests.test_import_measurement_module import (_PATCHES, _cgats,  # noqa: E402
                                                  _verify_env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _Target:
    def __init__(self, profile_run):
        self.profile_run = profile_run
        self.run_type = "profiling"
        self.verification_id = ""

    def is_verification(self):
        return False


def _read(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _five_runs(tmp_path, qapp):
    """Knut's shape: runs 1 to 5, run 5 with a dated verification whose
    automatic report the Measure tab wrote, and a report from before the
    document block (B8-388) in the same date."""
    from core.file_manager import RunMeta
    from tests.test_the_measurement_report_defaults_are_knuts import \
        _measure_tab
    s, fm, ctl, run1 = _verify_env(tmp_path)
    proj = fm.project()
    for _ in range(4):
        proj.new_run()
    proj = fm.project()
    for run in proj.all_runs():
        run.ensure_dir()
        if not run.meta_path.exists():
            run.save_meta(RunMeta.fresh(run.id))
    run5 = proj.run("run5")
    run5.profile_icc.write_bytes(b"icc")
    run5.verifications_dir.mkdir(parents=True, exist_ok=True)
    run5.verify_chart_ti2.write_text(_cgats("CTI2", _PATCHES), encoding="utf-8")
    v = run5.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
    finally:
        tab.deleteLater()
    auto = sorted((v.dir / "reports").glob("report_*.json"))
    assert len(auto) == 1
    # a report as ChromIQ wrote it before the document block
    legacy = _read(auto[0])
    legacy.pop("document", None)
    legacy["created"] = "2026-09-01T10:00:00"
    old = v.dir / "reports" / "report_2026-09-01_10-00-00.json"
    old.write_text(json.dumps(legacy, indent=2), encoding="utf-8")
    os.utime(old, (time.time() - 3600, time.time() - 3600))
    return s, proj, v, auto[0], old


def _delete_runs_1_to_4(proj):
    """The bar's Delete of run 1, four times, as Knut did."""
    import shutil

    import core.run_delete as rd
    import core.trash as ct
    from core.file_manager import Project
    trash = Path(proj.root).parent / "trash-182c"
    trash.mkdir(exist_ok=True)
    count = [0]

    def _to_trash(path):
        count[0] += 1
        dest = trash / f"{Path(path).name}-{count[0]}"
        shutil.move(str(path), str(dest))
        return ct.TrashResult(True, dest)
    real = rd.move_to_trash
    rd.move_to_trash = _to_trash
    try:
        for _ in range(4):
            proj = Project.load(proj.root)
            plan = rd.plan_for(proj, _Target("run1"))
            assert plan.kind == rd.KIND_RUN, plan
            rd.delete_run(proj, plan)
    finally:
        rd.move_to_trash = real
    return Project.load(proj.root)


def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    qapp.processEvents()
    return dlg


def _saved_entries(dlg, folder: Path):
    """``{report file name: (data key, entry text)}`` of every saved report
    "Report shown" lists with a file in *folder* (the measurement's own;
    a profiling window lists every run's reports)."""
    combo = dlg._saved_combo
    out = {}
    for e in dlg._saved_documents(dlg._run_ctx.run if dlg._run_ctx else None):
        i = combo.findData(e["key"])
        assert i >= 0, e["key"]
        homes = {Path(str(r.get("_origin_dir") or ""))
                 for r, _n in e["members"]}
        if Path(folder) not in homes:
            continue
        # every report here covers this one measurement: an entry that also
        # holds a file of another folder is two reports taken for one (a
        # duplicated run's copy that kept its original's document id)
        assert homes == {Path(folder)}, (e["key"], homes)
        for r, name in e["members"]:
            assert name not in out, (name, "listed twice")
            out[name] = (e["key"], combo.itemText(i))
    return out


def _everything(s, ti3, qapp, tmp_path, tag, monkeypatch):
    """For every saved report: its "Report shown" text, its page text and
    the text of its PDF, as the window gives them."""
    import pymupdf
    from PyQt6.QtGui import QDesktopServices

    import ui.widgets as W
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: True)
    dlg = _window(s, ti3, qapp)
    got = {}
    try:
        entries = _saved_entries(dlg, Path(ti3).parent)
        assert len(entries) >= 2, entries
        for name, (key, label) in sorted(entries.items()):
            combo = dlg._saved_combo
            combo.setCurrentIndex(combo.findData(key))
            qapp.processEvents()
            assert dlg._loaded_doc_id == key
            page = dlg._view.toPlainText()
            out = tmp_path / f"{tag}-{name}.pdf"
            monkeypatch.setattr(W, "save_file_dialog",
                                lambda *a, _o=out, **k: str(_o))
            dlg._export_pdf()
            assert out.is_file(), out
            pdf = " ".join(pg.get_text() for pg in pymupdf.open(str(out)))
            got[name] = {"entry": label, "page": page, "pdf": pdf}
    finally:
        dlg.close()
    return got


def _words(text: str) -> "list[str]":
    return text.split()


def word_diff(want: "list[str]", have: "list[str]") -> "list[str]":
    """The differing stretches of two word lists, with a little context."""
    import difflib
    out = []
    sm = difflib.SequenceMatcher(a=want, b=have, autojunk=False)
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal":
            continue
        ctx = " ".join(want[max(0, a0 - 6):a0])
        out.append(f"{op} after '...{ctx}': -[{' '.join(want[a0:a1])}] "
                   f"+[{' '.join(have[b0:b1])}]")
    return out


def _as_after_delete(text: str, en=True) -> str:
    """*text* with the run number 5 read as 1, and nothing else."""
    return re.sub(r"\b(run|Run|Lauf)( ?)5\b", r"\g<1>\g<2>1", text)


def test_after_runs_1_to_4_go_only_the_run_number_changes(tmp_path, qapp,
                                                          monkeypatch):
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    before = _everything(s, v.measurement_ti3, qapp, tmp_path, "before",
                         monkeypatch)
    # each says run 5 somewhere, or the test proves nothing
    for name, b in before.items():
        assert re.search(r"\brun 5\b", b["page"]), (name, b["page"][:400])
    proj = _delete_runs_1_to_4(proj)
    d = proj.root / "runs" / "run1" / "verifications" / v.dir.name
    assert d.is_dir()
    after = _everything(s, d / v.measurement_ti3.name, qapp, tmp_path,
                        "after", monkeypatch)
    assert sorted(after) == sorted(before)
    # the references follow the runs (§13.14): the automatic report's
    # measurement is named where it is now
    rep = _read(d / "reports" / auto.name)
    assert _runs_named(json.dumps(rep)) == {"runs/run1"}, rep["document"]
    for name in before:
        for part in ("entry", "page", "pdf"):
            want = _words(_as_after_delete(before[name][part]))
            have = _words(after[name][part])
            assert have == want, (name, part, word_diff(want, have))
        assert re.search(r"\brun 1\b", after[name]["page"]), name
        assert not re.search(r"\brun 5\b", after[name]["page"]), name


def test_no_report_records_a_run_number_of_its_own(tmp_path, qapp):
    """The freeze is gone: neither the automatic report nor a run delete
    writes ``saved_as`` into a file."""
    s, proj, v, auto, old = _five_runs(tmp_path, qapp)
    proj = _delete_runs_1_to_4(proj)
    d = proj.root / "runs" / "run1" / "verifications" / v.dir.name
    for p in (d / "reports").glob("report_*.json"):
        text = p.read_text(encoding="utf-8")
        assert "saved_as" not in text, p


# --------------------------------------------------------------------------
# C4: a duplicated run's reports are that run's
# --------------------------------------------------------------------------
def _one_run_with_two_reports(tmp_path, qapp):
    """Run 1 with a measurement and two reports the Measure tab wrote."""
    from tests.test_import_measurement_module import _env
    from tests.test_the_measurement_report_defaults_are_knuts import \
        _measure_tab
    s, fm, _ctl = _env(tmp_path)
    proj = fm.project()
    run1 = proj.run("run1")
    run1.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    for i in range(2):
        if i:
            time.sleep(1.1)          # a report's file name is its second
        tab = _measure_tab(s, qapp)
        try:
            tab._maybe_save_measurement_report(run1.measurement_ti3)
        finally:
            tab.deleteLater()
    reps = sorted((run1.dir / "reports").glob("report_*.json"))
    assert len(reps) == 2, reps
    return s, proj, run1, reps


def _runs_named(text: str) -> "set[str]":
    return set(re.findall(r"runs[/\\]+run\d+", text.replace("\\\\", "/")))


def test_a_duplicated_runs_reports_name_the_new_run(tmp_path, qapp,
                                                    monkeypatch):
    """Knut, C4: *"A report in a run is only related to that run.
    Duplicating a run will make a new run, and any reports in that run will
    then only relate to that new run."* The bar's Duplicate copies
    ``reports/report_*.json`` (`Project.duplicate_run`); the copies went on
    naming run 1 in every measurement reference. Now every reference in a
    copy names run 2, the page and PDF say run 2, and nothing else differs
    from the original's; run 1's own reports are untouched."""
    s, proj, run1, reps = _one_run_with_two_reports(tmp_path, qapp)
    originals = {p.name: p.read_bytes() for p in reps}
    new = proj.duplicate_run(run1)
    assert new.id == "run2"
    # the original as it reads NOW: with two measured runs in the project
    # its page says it covers 1 of the 2 (a live line about the project,
    # the same in both); everything else must match the copy
    before = _everything(s, run1.measurement_ti3, qapp, tmp_path, "src",
                         monkeypatch)
    for name, raw in originals.items():
        assert (run1.dir / "reports" / name).read_bytes() == raw, (
            "the source run's report was rewritten")
        text = (new.dir / "reports" / name).read_text(encoding="utf-8")
        assert _runs_named(text) == {"runs/run2"}, (name, _runs_named(text))
    after = _everything(s, new.measurement_ti3, qapp, tmp_path, "dup",
                        monkeypatch)
    assert sorted(after) == sorted(before)
    for name in before:
        for part in ("entry", "page", "pdf"):
            want = _words(re.sub(r"\b(run|Run|Lauf)( ?)1\b", r"\g<1>\g<2>2",
                                 before[name][part]))
            have = _words(after[name][part])
            assert have == want, (name, part, word_diff(want, have))
