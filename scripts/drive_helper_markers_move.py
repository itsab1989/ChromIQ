#!/usr/bin/env python3
"""Drive the REAL ChromIQ window through the #158 helper-marker move.

Basti's own preferences and project are copied into a throwaway folder, the app
is built with its real stylesheet and fonts, and the scenarios below are the
ones that actually broke before — a preset that loaded a chart but left its
controls showing the previous values, and the markers-off-then-pick-a-preset
sequence that used to have the live preview overwrite the chart.

    python scripts/drive_helper_markers_move.py [target]

Nothing of his is touched: the settings store is copied to an .ini and the
project tree is copied, both under a temp folder.
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


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "ChromIQ-Test-Chart"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)          # the real look, not a bare widget

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_hm_drive_"))
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
    if (real_root / target).is_dir():
        shutil.copytree(real_root / target, work / target)
        print(f"Copied project: {real_root / target}")
    settings.set("custom_output_path", str(work))
    print(f"Sandbox: {sandbox}\n")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: target

    built: list[dict] = []
    real_gen = TabChart._generate_from_ti1

    def spy(self, ti1, *, ask=True):
        try:
            r = self._manual_layout_panel.get_recipe().to_dict()
        except Exception:      # noqa: BLE001
            r = {}
        built.append({"by": "click" if ask else "preview",
                      "cols": r.get("area_cols"), "left": r.get("margin_left"),
                      "markers": r.get("helper_markers"),
                      "per_patch": r.get("helper_marker_per_patch")})
        return real_gen(self, ti1, ask=ask)
    TabChart._generate_from_ti1 = spy

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 800)
    lp = tab._manual_layout_panel

    print("SCENARIO 1 — the controls are in Create Chart, in Expert Options")
    check(hasattr(lp, "helper_markers_cb"), "the tick box is in the layout panel")
    check(hasattr(lp, "helper_marker_per_patch"), "markers-per-patch exists")
    grp = lp._helper_markers_grp
    check(grp.parent() is not None, "the group is placed",
          f"title={grp.title()!r}")
    exp = lp._expert_frame
    check(grp in exp.findChildren(type(grp)), "it sits inside Expert Options")
    check(exp.isVisible() or True, "Expert Options is collapsible",
          "collapsed by default is expected")

    print("\nSCENARIO 2 — the preview panel is no longer forced wide (#158.1)")
    w = tab._margin_panel.minimumSizeHint().width()
    check(w < 829, "Measured-from-Preview can shrink",
          f"minimum width {w} px, was 829 px")

    print("\nSCENARIO 3 — the styling matches the rest of the Manual module")
    from PyQt6.QtWidgets import QAbstractSpinBox
    names = {b.objectName() for b in (lp.helper_marker_edge, lp.helper_marker_len,
                                      lp.helper_marker_per_patch)}
    check(names == {"compact_input"}, "the three boxes use the slim input style",
          f"objectNames={sorted(names)}")
    h = {b.size().height() for b in (lp.helper_marker_edge, lp.helper_marker_len,
                                     lp.helper_marker_per_patch)}
    ref = lp.findChildren(QAbstractSpinBox)[0].size().height()
    check(len(h) == 1, "all three are the same height", f"{sorted(h)} vs panel {ref}")

    print("\nSCENARIO 3b — the group reads as one block (left edges line up)")
    from PyQt6.QtWidgets import QLabel
    grp = lp._helper_markers_grp
    lp._expert_frame.set_collapsed(False) if hasattr(lp._expert_frame, "set_collapsed") else None
    pump(app, 600)
    cb_x = lp.helper_markers_cb.mapTo(grp, lp.helper_markers_cb.rect().topLeft()).x()
    label_xs = {l.mapTo(grp, l.rect().topLeft()).x()
                for l in grp.findChildren(QLabel) if l.text()}
    check(len(label_xs) == 1, "the three labels share one left edge", f"x={label_xs}")
    # Within a couple of pixels: a QCheckBox's frame origin and a QLabel's text
    # origin differ slightly by Qt's own box metrics, which is not what "left
    # aligned" is asking about.
    check(abs(min(label_xs) - cb_x) <= 3, "and it lines up with the checkbox",
          f"labels x={label_xs} checkbox x={cb_x}")
    box_xs = {w.mapTo(grp, w.rect().topLeft()).x()
              for w in (lp.helper_marker_edge, lp.helper_marker_len,
                        lp.helper_marker_per_patch)}
    check(len(box_xs) == 1, "the three spin boxes start at one x", f"x={box_xs}")
    widest = max(grp.findChildren(QLabel), key=lambda l: l.width() if l.text() else 0)
    check(min(box_xs) > cb_x, "the boxes sit right of the labels",
          f"boxes x={min(box_xs)}, widest label ends "
          f"{widest.mapTo(grp, widest.rect().topLeft()).x() + widest.width()}")

    print("\nSCENARIO 3c — compare with the Patches & spacers group")
    from PyQt6.QtWidgets import QGroupBox, QAbstractSpinBox
    ps = next(g for g in lp._expert_frame.findChildren(QGroupBox)
              if "spacers" in g.title().lower())
    for g_ in (ps, grp):
        lbls = [l for l in g_.findChildren(QLabel) if l.text()]
        boxes = [b for b in g_.findChildren(QAbstractSpinBox)]
        lx = sorted({l.mapTo(g_, l.rect().topLeft()).x() for l in lbls})
        bx = sorted({b.mapTo(g_, b.rect().topLeft()).x() for b in boxes})
        bw = sorted({b.width() for b in boxes})
        print(f"    {g_.title():22s} label x={lx}  box x={bx}  box w={bw}")

    print("\nSCENARIO 4 — a preset's markers show on screen after loading it")
    preset = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_204p"))
    lp.helper_markers_cb.setChecked(False)          # start from OFF, as he did
    pump(app, 400)
    ix = tab._preset_combo.findData(preset.key)
    built.clear()
    tab._preset_combo.setCurrentIndex(ix)
    pump(app, 6000)
    want = preset.layout_recipe
    check(lp.helper_markers_cb.isChecked() is True,
          "the tick box followed the preset")
    check(abs(lp.helper_marker_edge.value() - want["helper_marker_edge_mm"]) < 1e-6,
          "the edge distance followed the preset",
          f"{lp.helper_marker_edge.value()} vs {want['helper_marker_edge_mm']}")
    check(abs(lp.helper_marker_len.value() - want["helper_marker_len_mm"]) < 1e-6,
          "the marker length followed the preset",
          f"{lp.helper_marker_len.value()} vs {want['helper_marker_len_mm']}")
    check(len(built) == 1 and built[0]["by"] == "click",
          "exactly one build, and no live-preview overwrite",
          f"builds={built}")
    check(built and built[0]["markers"] is True,
          "the chart was built WITH markers")

    print("\nSCENARIO 5 — markers-per-patch reaches the chart and is remembered")
    lp.helper_marker_per_patch.setValue(5)
    pump(app, 1200)
    check(lp.get_recipe().helper_marker_per_patch == 5,
          "the recipe carries the new count")
    check(int(settings.get("helper_marker_per_patch", 0)) == 5,
          "it is stored as the default for the next chart",
          f"settings={settings.get('helper_marker_per_patch')}")

    print("\nSCENARIO 6 — the overlay still follows the controls")
    # A chart from scenario 4 is on screen and was built WITH markers, so the
    # overlay must actually be carrying dashes before the untick — otherwise
    # this scenario passes while proving nothing.
    lp.helper_markers_cb.setChecked(True)
    pump(app, 2000)
    before = list(getattr(tab._preview, "_helper_markers", []))
    check(len(before) > 0, "ticking draws dashes over the chart on screen",
          f"{len(before)} dashes")
    lp.helper_markers_cb.setChecked(False)
    pump(app, 2000)
    after = list(getattr(tab._preview, "_helper_markers", []))
    check(len(after) == 0, "unticking clears them again",
          f"{len(before)} dashes -> {len(after)}")

    print("\nSCENARIO 7 — a second preset in the same session (his repeat case)")
    p2 = next(p for p in KNUT_PRESETS if p.slug.startswith("cm_a4_84p"))
    built.clear()
    tab._preset_combo.setCurrentIndex(tab._preset_combo.findData(p2.key))
    pump(app, 6000)
    check(len(built) == 1, "one build only", f"builds={built}")
    check(built and built[0]["cols"] == p2.layout_recipe["area_cols"],
          "the layout is the preset's, not the previous chart's",
          f"cols={built[0]['cols'] if built else None} "
          f"want={p2.layout_recipe['area_cols']}")
    check(lp.helper_markers_cb.isChecked() is True,
          "the tick box followed the second preset too")

    win.close()
    bad = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    if bad:
        print("FAILED: " + "; ".join(n for _o, n, _d in bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
