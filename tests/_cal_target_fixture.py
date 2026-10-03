"""Shared set-up for the #182 "Calibration builds into a run" tests.

Knut, #182 5964478612 (2026-10-03): with a profiling patch set still bound,
Generate Chart in Run type = Calibration rebuilt his run4's chart and moved its
``.ti3`` and ``.icc`` into ``old/``. These helpers give the tests a real main
window, a project with a run whose chart came from a patch set of the user's
own, and a way to prove that run's files were not touched.

Every project lives under the test's ``tmp_path``; the suite's conftest
sandboxes the settings store.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT = "Cal-Guard"


def write_run_chart(run, *, given: bool, rows: int = 4,
                    with_results: bool = True) -> dict:
    """A small but complete chart in *run*: .ti1, .ti2, one page, a sidecar,
    and (by default) a measurement and a profile. Returns {name: path}.

    *given* decides what the chart says about its patch set: a loaded set
    (ORIGINATOR of an import, sidecar ``patch_set_given: true``) or targen's
    own output (``patch_set_given: false``).
    """
    from PyQt6.QtGui import QColor, QImage

    d = run.ensure_dir()
    stem = run.stem
    originator = ("ChromIQ i1Profiler import" if given
                  else "Argyll targen")
    data = "\n".join(f"{i} {v:.4f} {v:.4f} {v:.4f} {v:.4f} {v:.4f} {v:.4f}"
                     for i, v in enumerate(
                         (100.0 - 100.0 * k / max(1, rows - 1)
                          for k in range(rows)), 1))
    ti1 = d / f"{stem}.ti1"
    ti1.write_text(
        f'CTI1\n\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        f'ORIGINATOR "{originator}"\nCOLOR_REP "iRGB"\n\n'
        f"NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        f"SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {rows}\nBEGIN_DATA\n{data}\nEND_DATA\n",
        encoding="utf-8")
    ti2 = d / f"{stem}.ti2"
    ti2.write_text(
        f'CTI2\n\nORIGINATOR "ChromIQ layout engine"\nCOLOR_REP "iRGB"\n'
        f'CHART_ID "1"\nSTEPS_IN_PASS "{rows}"\n\n'
        f"NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {rows}\nBEGIN_DATA\n"
        + "".join(f'{i} "A{i}"\n' for i in range(1, rows + 1))
        + "END_DATA\n", encoding="utf-8")
    img = QImage(60, 40, QImage.Format.Format_RGB32)
    img.fill(QColor(200, 200, 200))
    tif = d / f"{stem}.tif"
    assert img.save(str(tif), "TIFF")
    sidecar = d / f"{stem}.channels.json"
    sidecar.write_text(json.dumps({"patch_set_given": bool(given)}),
                       encoding="utf-8")
    out = {"ti1": ti1, "ti2": ti2, "tif": tif, "sidecar": sidecar}
    if with_results:
        ti3 = d / f"{stem}.ti3"
        ti3.write_text("CTI3\nMEASURED\n", encoding="utf-8")
        icc = d / f"{stem}.icc"
        icc.write_bytes(b"not really a profile, but its bytes are watched")
        out.update(ti3=ti3, icc=icc)
    return out


def fingerprint(folder: Path) -> dict:
    """Every file under *folder*: its sha256 and mtime. A build that touched
    the run, or archived anything into ``old/``, changes this."""
    res = {}
    for p in sorted(Path(folder).rglob("*")):
        if p.is_file():
            res[str(p.relative_to(folder))] = (
                hashlib.sha256(p.read_bytes()).hexdigest(),
                p.stat().st_mtime_ns)
    return res


def make_window(qapp, tmp_path):
    """A real main window with calibration options on, and an empty project."""
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    s.set("calibration_mode", True)
    s.set("auto_update_preview", False)
    w = MainWindow(s)
    qapp.processEvents()
    w._target_ctl.set_calibration_allowed(True)
    tc = w._tab_chart
    tc.set_calibration_mode(True)
    w._file_mgr.set_target_name(PROJECT)
    w._file_mgr.project().current_run().ensure_dir()
    tc._switch_mode("manual")
    if tc._manual_target_name_edit is not None:
        tc._manual_target_name_edit.setText(PROJECT)
    qapp.processEvents()
    return w


def show_run(w, qapp, run_id: str) -> None:
    """Point the bar at *run_id* under Run type Profiling, as a click does."""
    from core.measurement_target import RUN_TYPE_PROFILING

    ctl = w._target_ctl
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run(run_id)
    ctl.changed.emit()
    qapp.processEvents()


def bound(tc) -> bool:
    """Is any patch set or preset chart bound to the next Generate?"""
    return bool(tc._ti1_preset_active() or tc._prebuilt_active
                or tc._applied_active)


def override_row_shown(tc) -> bool:
    return not tc._override_targen_row.isHidden()


def targen_panel_enabled(tc) -> bool:
    return all(w.isEnabled() for w in tc._manual_targen_content)


class Refusals:
    """Stands in for InfoDialog in ui.tabs.tab_chart and keeps every window
    it was asked to show, so a test can say which one appeared."""

    def __init__(self):
        self.shown: list[tuple[str, str]] = []

    def __call__(self, title, body="", *a, **k):
        shown = self.shown

        class _D:
            def exec(self_inner):
                shown.append((str(title), str(body)))
                return 0
        return _D()
