"""On-screen test plan for the #130 Delete button (Knut, 2026-07-28).

Drives the REAL MeasurementTargetBar in a real window: for every case it sets
the selection, reads the button's live enabled state and tooltip, clicks it,
captures the window that appears (title, body, buttons), answers a named
button, and then checks what actually happened ON DISK.

Run:  PYTHONPATH=<repo> python drive_delete_plan.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
import PyQt6.QtWidgets as W

from core.file_manager import Project, RunMeta
from ui.measurement_target_bar import (MeasurementTargetBar,
                                       MeasurementTargetController)
import core.run_delete as rd

ROWS = []
# Window grabs go to a temp folder — they are diagnostics for one run, not
# something the repository should carry.
import tempfile as _tf
SHOTS = Path(_tf.mkdtemp(prefix="chromiq_delete_shots_"))


def row(name, ok, detail=""):
    ROWS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"   — {detail}" if detail else ""))


def make_project(tmp, runs=1, name="Test-Profiling-P"):
    root = Path(tmp) / name
    root.mkdir(parents=True)
    (root / "runs").mkdir()
    (root / Project.MANIFEST).write_text(json.dumps({
        "schema_version": 3, "created_at": "", "target_name": name,
        "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    proj = Project.load(root)
    for _ in range(runs - 1):
        proj.new_run()
    for r in proj.all_runs():
        r.ensure_dir()
        if not r.meta_path.exists():
            r.save_meta(RunMeta.fresh(r.id))
    return proj


class Bar:
    """A real bar wired to a real project."""

    def __init__(self, proj):
        self.proj = proj
        class _FM:
            def project(_s): return proj
        self.ctl = MeasurementTargetController(_FM())
        self.ctl.project_or_none = lambda: proj          # bind to this project
        self.bar = MeasurementTargetBar(self.ctl, show_verification=True)
        self.bar.resize(1400, 90)
        self.bar.show()
        QApplication.instance().processEvents()

    def select(self, run_id, run_type="profiling", vid=""):
        self.ctl.target.profile_run = run_id
        self.ctl.target.run_type = run_type
        self.ctl.target.verification_id = vid
        self.bar.refresh()
        QApplication.instance().processEvents()


def click_delete(bar, answer=None, shot=None):
    """Press Delete, capture the window, and answer `answer` (button text
    substring) or Cancel. Returns (title, body, [button texts])."""
    seen = {}
    real = W.QMessageBox.exec

    def fake(self):
        self.show()
        QApplication.instance().processEvents()
        if shot:
            self.grab().save(str(SHOTS / f"{shot}.png"))
        seen["title"] = self.windowTitle()
        seen["body"] = self.text()
        seen["buttons"] = [b.text() for b in self.buttons()]
        target = None
        if answer:
            for b in self.buttons():
                if answer.lower() in b.text().lower():
                    target = b
                    break
        self.hide()
        if target is None:
            for b in self.buttons():
                if "cancel" in b.text().lower():
                    target = b
        self._picked = target
        return 0

    def picked(self):
        return getattr(self, "_picked", None)

    W.QMessageBox.exec = fake
    W.QMessageBox.clickedButton = picked
    try:
        bar.bar._delete_btn.click()
        QApplication.instance().processEvents()
    finally:
        W.QMessageBox.exec = real
        del W.QMessageBox.clickedButton
    return seen


def verify_chart(run):
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti2.write_text("TI2")


def verification(run, vid, measured=True):
    v = run.verification(vid)
    v.ensure_dir()
    if measured:
        v.measurement_ti3.write_text("V")


def main(app):

    # ---- E-states -------------------------------------------------------
    tmp = tempfile.mkdtemp()
    proj = make_project(tmp, runs=3)
    b = Bar(proj)

    b.select("")
    en, tip = b.ctl.delete_state()
    row("E3  New run → greyed", not en and "New run" in tip, tip)

    b.select("run9")
    en, tip = b.ctl.delete_state()
    row("E4  unknown run → greyed", not en and "no longer exists" in tip, tip)

    b.select("run1")
    en, tip = b.ctl.delete_state()
    row("E5  profiling run → enabled", en and "everything in it" in tip, tip)

    b.select("run1", "verification")
    en, tip = b.ctl.delete_state()
    row("E6  no verifications → greyed", not en and "no verification files" in tip, tip)

    b.ctl.set_measuring(True)
    en, tip = b.ctl.delete_state()
    row("E1  measuring → greyed", not en and "Not while" in tip, tip)
    b.ctl.set_measuring(False)

    run1 = proj.run("run1")
    verify_chart(run1)
    verification(run1, "2026-07-28_131500")
    b.select("run1", "verification")
    en, tip = b.ctl.delete_state()
    row("E7  one date → enabled, whole folder",
        en and tip == ("Delete this run's whole verification folder — the "
                       "verification chart and its results"), tip)

    b.select("run1", "verification", "2026-07-28_131500")
    en, tip = b.ctl.delete_state()
    row("E9  the only date selected == E7", en and "whole verification folder" in tip, tip)

    verification(run1, "2026-07-21_114035")
    b.select("run1", "verification", "2026-07-21_114035")
    en, tip = b.ctl.delete_state()
    row("E10 one of several → only that date", en and "other dates are kept" in tip, tip)

    b.select("run1", "verification", "1999-01-01_000000")
    en, tip = b.ctl.delete_state()
    row("E11 unknown date → greyed", not en and "no longer exists" in tip, tip)

    # ---- the fields' info icon placement (2.1) --------------------------
    b.select("run1", "verification")
    r = b.bar.layout().itemAt(0).layout()
    order = []
    for i in range(r.count()):
        w = r.itemAt(i).widget()
        if w is not None and w.isVisible():
            order.append(w.objectName() or type(w).__name__)
    idx_tip = None
    widgets = [r.itemAt(i).widget() for i in range(r.count())]
    widgets = [w for w in widgets if w is not None]
    try:
        i_verify = widgets.index(b.bar._verify_combo)
        i_tip = widgets.index(b.bar._tip_btn)
        i_restore = widgets.index(b.bar._restore_btn)
        i_del = widgets.index(b.bar._delete_btn)
        ok = i_verify < i_tip < i_restore < i_del
        row("2.1 ⓘ after Verification, then Restore, then Delete", ok,
            f"verify={i_verify} tip={i_tip} restore={i_restore} delete={i_del}")
    except ValueError as exc:
        row("2.1 ⓘ placement", False, str(exc))

    # x-position check with Verification hidden
    b.select("run1", "profiling")
    QApplication.instance().processEvents()
    ok = (b.bar._tip_btn.x() > b.bar._type_combo.x()
          and b.bar._tip_btn.x() < b.bar._restore_btn.x())
    row("2.1 ⓘ follows Run type when Verification hidden", ok,
        f"type={b.bar._type_combo.x()} tip={b.bar._tip_btn.x()} "
        f"restore={b.bar._restore_btn.x()}")

    # ---- V2: several dates + "New verification" → the whole folder -------
    # (run1 has TWO dates at this point, so this is V2, not V1.)
    b.select("run1", "verification")
    seen = click_delete(b, answer="Delete all", shot="V2")
    row("V2  button names the count", "Delete all 2 verifications" in seen["buttons"],
        str(seen["buttons"]))
    row("V2  lists every date that will be lost",
        "2026-07-28 13:15:00" in seen["body"] and "2026-07-21 11:40:35" in seen["body"])
    row("V2  whole verifications/ folder deleted on disk",
        not run1.verifications_dir.exists())
    row("V2  profiling side untouched", run1.dir.exists())

    # ---- V1: exactly ONE date → still the whole folder (his D5) ----------
    verify_chart(run1)
    verification(run1, "2026-07-28_131500")
    (run1.verifications_dir / "old").mkdir(exist_ok=True)
    b.select("run1", "verification")
    seen = click_delete(b, answer="Delete the verification files", shot="V1")
    row("V1  whole verifications/ folder deleted on disk",
        not run1.verifications_dir.exists())
    row("V1  window explains why the whole folder goes",
        "nothing left to belong to" in seen["body"])
    row("V1  window names the folder and promises permanence",
        "verifications" in seen["body"] and "Trash" in seen["body"]
        and "cannot be undone" in seen["body"])
    row("V1  profiling side untouched", run1.dir.exists())

    # ---- V3: one of several dates ---------------------------------------
    verify_chart(run1)
    verification(run1, "2026-07-14_090211")
    verification(run1, "2026-07-21_114035")
    b.select("run1", "verification", "2026-07-14_090211")
    seen = click_delete(b, answer="Delete this verification", shot="V3")
    ok = (not (run1.verifications_dir / "2026-07-14_090211").exists()
          and (run1.verifications_dir / "2026-07-21_114035").exists()
          and run1.verify_chart_ti2.exists())
    row("V3  only that date deleted; chart + other date kept", ok)

    # ---- Cancel really cancels ------------------------------------------
    b.select("run1", "verification", "2026-07-21_114035")
    click_delete(b, answer="Cancel", shot="V3_cancel")
    row("Cancel leaves everything in place",
        (run1.verifications_dir / "2026-07-21_114035").exists())

    b.bar.close()
    shutil.rmtree(tmp, ignore_errors=True)

    # ---- P1 + renumbering, on a fresh project ---------------------------
    tmp = tempfile.mkdtemp()
    proj = make_project(tmp, runs=4)
    for rid in ("run1", "run2", "run3", "run4"):
        (proj.run(rid).dir / "marker.txt").write_text(rid)
    r2 = proj.run("run2")
    (r2.dir / f"{r2.stem}.ti3").write_text("MEAS")
    b = Bar(proj)
    b.select("run2")
    seen = click_delete(b, answer="Delete run 2 permanently", shot="P1")
    root = proj.runs_root
    names = sorted(d.name for d in root.iterdir() if d.is_dir())
    row("P1  window lists the renumbering",
        "run 3 becomes run 2" in seen["body"] and "run 4 becomes run 3" in seen["body"])
    row("P1  window states the landing run (D2)",
        "selects the last run in the project, run 3" in seen["body"])
    row("P1  folders renumbered on disk", names == ["run1", "run2", "run3"], str(names))
    row("P1  contents travelled with the folder",
        (root / "run2" / "marker.txt").read_text() == "run3")
    man = json.loads((proj.root / Project.MANIFEST).read_text())
    row("P1  manifest rebuilt", man["runs"] == ["run1", "run2", "run3"], str(man["runs"]))
    row("P1  current_run = last run (D2)", man["current_run"] == "run3",
        man["current_run"])
    metas = [json.loads((root / rid / "meta.json").read_text())["run_id"]
             for rid in ("run1", "run2", "run3")]
    row("P1  every meta.json rewritten", metas == ["run1", "run2", "run3"], str(metas))
    row("P1  bar now offers exactly the surviving runs",
        b.bar._run_combo.count() >= 3)

    b.bar.close()
    shutil.rmtree(tmp, ignore_errors=True)

    # ---- P5: the last run ------------------------------------------------
    tmp = tempfile.mkdtemp()
    proj = make_project(tmp, runs=1)
    run1 = proj.run("run1")
    (run1.dir / f"{run1.stem}.ti3").write_text("MEAS")
    b = Bar(proj)
    b.select("run1")
    en, tip = b.ctl.delete_state()
    row("E12 only run → enabled, offers both ways", en and "whole project" in tip, tip)
    seen = click_delete(b, answer="Empty run 1", shot="P5")
    row("P5  window offers both buttons",
        any("Empty" in x for x in seen["buttons"])
        and any("whole project" in x for x in seen["buttons"]), str(seen["buttons"]))
    row("P5  Empty keeps the folder, clears the contents",
        run1.dir.exists() and not run1.measurement_ti3.exists())
    row("P5  meta.json is fresh", run1.meta_path.exists())

    b.bar.close()
    shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 72)
    bad = [r for r in ROWS if not r[1]]
    print(f"{len(ROWS) - len(bad)}/{len(ROWS)} rows passed")
    for name, _ok, detail in bad:
        print(f"  FAILED: {name}  {detail}")
    return 1 if bad else 0


def _run_in_loop():
    """Run the plan INSIDE a real event loop, which is what an on-screen
    (cocoa) run needs — driving a shown window with processEvents() alone
    never returns."""
    from PyQt6.QtCore import QTimer
    app = QApplication.instance() or QApplication(sys.argv)
    code = {"rc": 1}

    def go():
        try:
            code["rc"] = main(app)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            app.quit()

    QTimer.singleShot(0, go)
    QTimer.singleShot(180000, app.quit)          # never hang the session
    app.exec()
    return code["rc"]


if __name__ == "__main__":
    sys.exit(_run_in_loop())
