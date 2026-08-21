#!/usr/bin/env python3
"""Drive the REAL ChromIQ window: Guided must never write into Manual (#160).

soul-traveller: *"the hidden hardcoded attributes in guided cannot be
transferred to manual mode as that would overwrite changes made in manual mode
if one changes from manual to guided and back"*.

The six chartread options Guided does not offer (-H -F -l -L -n -A) are Manual's
alone. This script sets every one of them to a non-default value in Manual, then
puts the tab through every path that could plausibly write them — switching
module both ways, saving defaults from inside Guided, restoring defaults,
leaving the target and coming back — and checks after each that Manual still
holds exactly what the user typed, and that Guided's command line carries none
of those flags.

    python scripts/drive_160_guided_does_not_touch_manual.py [target]

Basti's preferences are copied to a throwaway .ini and a project is copied to a
temp folder; nothing of his is touched.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
RESULTS: list[tuple[bool, str, str]] = []

#: What the user types into Manual. Every one of these is an option Guided does
#: NOT offer, so Guided must neither read nor write it.
MANUAL_CHOICES = {
    "highres": (True, None),
    "filter": (True, "6"),      # the -F argument, not a name: n/5/6/u/p
    "save_lab": (True, None),
    "save_lab_and_xyz": (True, None),
    "no_spectral": (True, None),
    "xrga": (True, None),
}


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _manual_state(tab) -> dict:
    """What Manual's six own options say right now."""
    out = {}
    for opt in tab._m_chartread_opts:
        if opt.key not in MANUAL_CHOICES:
            continue
        val = None
        w = opt.widget
        if w is not None:
            val = w.currentData() if hasattr(w, "currentData") else w.value()
        out[opt.key] = (bool(opt.checkbox.isChecked()), val)
    return out


def _set_manual(tab) -> None:
    for opt in tab._m_chartread_opts:
        if opt.key not in MANUAL_CHOICES:
            continue
        want_on, want_val = MANUAL_CHOICES[opt.key]
        opt.checkbox.setChecked(want_on)
        if want_val is not None and opt.widget is not None:
            i = opt.widget.findData(want_val)
            if i >= 0:
                opt.widget.setCurrentIndex(i)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "Canon-Pro300-CanonSG-i1Pro"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_160_"))
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst

    configured = str(settings.get("custom_output_path") or "").strip()
    real_root = Path(configured) if configured else (Path.home() / "ChromIQ")
    if not real_root.is_dir():
        real_root = Path.home() / "ChromIQ"
    work = sandbox / "ChromIQ"
    work.mkdir()
    for name in (target,):
        if (real_root / name).is_dir():
            shutil.copytree(real_root / name, work / name)
    settings.set("custom_output_path", str(work))
    print(f"Sandbox: {sandbox}\n")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    tab = win._tab_measure

    print("SCENARIO 1 — Guided owns only what it shows")
    guided_keys = {o.key for o in tab._chartread_opts}
    check(guided_keys == {"tolerance"},
          "Guided has a widget for the tolerance and nothing else",
          f"Guided owns {sorted(guided_keys)}")
    check(not (guided_keys & set(MANUAL_CHOICES)),
          "Guided has NO widget for any of Manual's six options",
          "with no widget there is nothing that could be transferred")

    print("\nSCENARIO 2 — set all six in Manual, then switch module and come back")
    tab._switch_mode("manual")
    pump(app, 500)
    _set_manual(tab)
    pump(app, 400)
    typed = _manual_state(tab)
    check(all(v[0] for v in typed.values()),
          "all six options are on in Manual", f"{sorted(typed)}")
    tab._switch_mode("guided")
    pump(app, 500)
    tab._switch_mode("manual")
    pump(app, 500)
    check(_manual_state(tab) == typed,
          "Manual → Guided → Manual leaves every one of them untouched",
          "this is soul-traveller's exact sequence")

    print("\nSCENARIO 3 — what Guided would actually run")
    tab._switch_mode("guided")
    pump(app, 300)
    g = tab._collect_guided()
    for flag in ("-H", "-F", "-l", "-L", "-n", "-A"):
        check(flag not in g.extra_args.split(),
              f"Guided's command line does not carry {flag}",
              f"extra_args={g.extra_args!r}" if flag == "-H" else "")
    check(g.disable_initial_cal is False,
          "Guided never skips the initial calibration",
          "hard-coded False, not read from the hidden box")
    tab._switch_mode("manual")
    pump(app, 300)
    m = tab._collect_manual()
    check(all(f in m.extra_args.split() for f in ("-H", "-l", "-L", "-n", "-A")),
          "…while Manual's command line carries the user's choices",
          f"extra_args={m.extra_args!r}")

    print("\nSCENARIO 4 — Save as Defaults from inside Guided, then Restore")
    tab._switch_mode("guided")
    pump(app, 300)
    tab._on_save_defaults()
    pump(app, 400)
    tab._switch_mode("manual")
    pump(app, 300)
    check(_manual_state(tab) == typed,
          "saving defaults while Guided is showing does not disturb Manual")
    # Restore Defaults is SUPPOSED to replace what is on screen, so the test is
    # not "the typed values come back" — it is that Manual is restored from
    # MANUAL's own stored keys. Guided's widgets are restored first and seven of
    # them are linked, so a missing manual2_* restore would leave Manual holding
    # whatever Guided's default pushed through the link.
    tab._restore_defaults()
    pump(app, 500)
    restored = _manual_state(tab)
    want = {k: bool(settings.get(f"manual2_chartread_{k}_enabled", False))
            for k in MANUAL_CHOICES}
    check(all(restored[k][0] == want[k] for k in want),
          "Restore Defaults takes Manual's six from Manual's own saved keys",
          f"restored={{k: v[0] for k, v in restored.items()}}, "
          f"manual2_*={want}")
    _set_manual(tab)
    pump(app, 400)
    typed = _manual_state(tab)

    print("\nSCENARIO 5 — leave the target and come back (per-target settings)")
    from workflow import measure_settings
    snap = measure_settings.snapshot(tab)
    hidden = [k for k in snap if k.startswith("chartread.")
              and k.split(".", 1)[1] in MANUAL_CHOICES]
    check(not hidden,
          "the per-target file stores none of the six under Guided's prefix",
          f"Guided keys stored: {sorted(k for k in snap if k.startswith('chartread.'))}")
    for opt in tab._m_chartread_opts:
        if opt.key in MANUAL_CHOICES:
            opt.checkbox.setChecked(False)
    pump(app, 300)
    unknown = measure_settings.apply(tab, snap)
    pump(app, 400)
    check(_manual_state(tab) == typed,
          "re-applying the stored target settings restores Manual's six exactly",
          f"unknown keys: {unknown}" if unknown else "")

    print("\nSCENARIO 6 — every linked Guided control is one the user can SEE")
    # The general form of his rule, checked where it can honestly be checked: in
    # a window that is actually on screen. `isVisible()` is False for everything
    # on an unshown tab, which is why the unit tests name the one offender
    # instead. A hidden control that is linked would write into Manual with
    # nothing on the Guided panel to explain it.
    # The Measure tab has to be the CURRENT tab, or every widget on it reports
    # isVisible() == False and this check passes for the wrong reason — the same
    # trap that made an earlier isVisible() filter drop the tolerance row.
    win._tabs.setCurrentWidget(tab)
    tab._switch_mode("guided")
    pump(app, 800)
    check(tab._pbp_cb.isVisible(),
          "the Guided panel is genuinely on screen",
          "patch-by-patch is visible, so isVisible() means something here")
    hidden = []
    for g_name, m_name in tab._LINKED_PAIRS:
        w = getattr(tab, g_name, None)
        if w is not None and not w.isVisible():
            hidden.append((g_name, m_name))
    # `_resume_cb` is shown only when there is something to resume, so it is
    # allowed to be hidden right now; it is a real Guided control either way.
    hidden = [p for p in hidden if p[0] != "_resume_cb"]
    check(not hidden,
          "no linked Guided control is hidden from the Guided user",
          f"hidden and linked: {hidden}" if hidden else
          f"{len(tab._LINKED_PAIRS)} pairs checked on a shown window")
    check("_nocal_cb" not in {n for pair in tab._LINKED_PAIRS for n in pair},
          "the hidden skip-calibration box is not linked to Manual",
          "the one control Guided keeps fixed")

    bad = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
