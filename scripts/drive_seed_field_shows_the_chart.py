#!/usr/bin/env python3
"""Drive the REAL ChromIQ window through Basti's exact seed-field sequence.

Basti, 4.1.5-beta.9: *"when creating a chart with the layout engine and in the
randomisation section 'randomise patch order' is active (which is on by default)
then there is no way to see which seed number was used it seems. […] on initial
generation the seed number there is always 0 at first or stuck at any other
number even when i generate again. i think that even when this field is greyed
it should reflect the seed number of the chart on screen"*.

His sequence, nothing skipped:

    1. open Create Chart → Manual, layout engine on, leave "Randomise patch
       order" ticked            → photograph the Seed field
    2. Generate Chart           → photograph
    3. Generate Chart again     → photograph
    4. press "New seed"         → photograph
    5. Generate Chart           → photograph

After every generation the driver reads the seed the chart on screen was
ACTUALLY built with, from two independent places on disk — ``RANDOM_START`` in
the ``.ti2`` and ``layout.seed`` in ``<stem>.channels.json`` — and compares it
with the number in the widget. No judgement is needed: the field either shows
that number or it does not.

    CHROMIQ_DRIVE_ONSCREEN=1 .venv/bin/python scripts/drive_seed_field_shows_the_chart.py

Settings are sandboxed to a throwaway .ini and the projects go to a temp folder;
nothing of the user's is touched.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

SHOTS = Path(os.environ.get(
    "CHROMIQ_SEED_SHOTS", "/Users/Basti/Desktop/beta 9/seed-field"))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def ti2_seed(ti2: Path) -> tuple[str, str] | None:
    """(keyword, value) of the .ti2's RANDOM_START / CHART_ID line."""
    if not ti2.is_file():
        return None
    for line in ti2.read_text(encoding="utf-8", errors="replace").splitlines():
        for kw in ("RANDOM_START", "CHART_ID"):
            if line.strip().startswith(kw):
                return kw, line.split('"')[1]
    return None


def sidecar_seed(ti2: Path):
    p = ti2.with_suffix(".channels.json")
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("layout", {}).get("seed")
    except (OSError, ValueError):
        return None


def patch_order(ti2: Path) -> list[str]:
    """SAMPLE_LOC column in file order — the sheet's actual patch order."""
    if not ti2.is_file():
        return []
    lines = ti2.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        start = next(i for i, ln in enumerate(lines)
                     if ln.strip() == "BEGIN_DATA") + 1
        end = next(i for i, ln in enumerate(lines) if ln.strip() == "END_DATA")
    except StopIteration:
        return []
    return [ln.split()[1] for ln in lines[start:end] if ln.split()]


def shoot(tab, name: str) -> None:
    panel = tab._manual_layout_panel
    grp = panel.randomize_cb.parentWidget()          # the "Randomisation" group
    grp.grab().save(str(SHOTS / f"{name}_randomisation.png"))
    tab.grab().save(str(SHOTS / f"{name}_tab.png"))


def seed_field(tab) -> dict:
    p = tab._manual_layout_panel
    return {
        "randomise": p.randomize_cb.isChecked(),
        "fixed": p.fixed_seed_cb.isChecked(),
        "spin": int(p.seed_spin.value()),
        "spin_enabled": p.seed_spin.isEnabled(),
    }


def generate(app, tab) -> None:
    tab._on_generate()
    for _ in range(180):
        pump(app, 500)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            break
    pump(app, 1500)


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_seedfield_"))
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "settings.ini"),
                             QSettings.Format.IniFormat)
    out = sandbox / "ChromIQ"
    out.mkdir()
    settings.set("custom_output_path", str(out))
    settings.set("use_chromiq_layout_engine", True)
    print(f"Sandbox: {sandbox}")

    QDialog.exec = lambda self: 1                    # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1700, 1080)
    win.show()
    pump(app, 3000)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 1200)
    tab._switch_mode("manual")
    pump(app, 1500)

    if getattr(tab, "_manual_layout_panel", None) is None:
        print("FAIL  the layout panel was never built — the engine is not on")
        return 2

    tab._manual_target_name_edit.setText("SeedFieldProbe")
    tab._set_manual_value("targen", "-f", 64)        # small, so this is quick
    pump(app, 800)

    rows: list[tuple[str, dict, object, object]] = []

    print("\n1. Create Chart → Manual, engine on, nothing generated yet")
    print("   seed field:", seed_field(tab))
    shoot(tab, "1_before_any_generation")
    rows.append(("1 before any generation", seed_field(tab), None, None))

    orders: dict[str, list[str]] = {}
    for step, label in ((2, "2_first_generate"), (3, "3_second_generate")):
        print(f"\n{step}. Generate Chart")
        generate(app, tab)
        ti2 = tab._shown_chart_ti2
        real = ti2_seed(Path(ti2)) if ti2 else None
        side = sidecar_seed(Path(ti2)) if ti2 else None
        f = seed_field(tab)
        print("   .ti2 says       :", real)
        print("   channels.json   :", side)
        print("   seed field shows:", f)
        shoot(tab, label)
        rows.append((label, f, real, side))
        if ti2:
            orders[label] = patch_order(Path(ti2))

    print("\n4. press “New seed”")
    tab._manual_layout_panel._on_new_seed()
    pump(app, 600)
    typed = seed_field(tab)
    print("   seed field shows:", typed)
    shoot(tab, "4_after_new_seed")
    rows.append(("4 after New seed", typed, None, None))

    print("\n5. Generate Chart with that typed seed")
    generate(app, tab)
    ti2 = Path(tab._shown_chart_ti2) if tab._shown_chart_ti2 else None
    real = ti2_seed(ti2) if ti2 else None
    side = sidecar_seed(ti2) if ti2 else None
    f = seed_field(tab)
    print("   .ti2 says       :", real)
    print("   channels.json   :", side)
    print("   seed field shows:", f)
    shoot(tab, "5_generate_with_typed_seed")
    rows.append(("5 generate with typed seed", f, real, side))
    if ti2:
        orders["5_typed"] = patch_order(ti2)
        shutil.copy2(ti2, sandbox / "typed_seed_first.ti2")

    print("\n6. Generate again with the SAME typed seed — the order must repeat")
    generate(app, tab)
    ti2b = Path(tab._shown_chart_ti2) if tab._shown_chart_ti2 else None
    if ti2b:
        orders["6_typed_again"] = patch_order(ti2b)
    same = orders.get("5_typed") and orders.get("5_typed") == orders.get("6_typed_again")
    print(f"   same patch order from the same seed: {bool(same)}")
    shoot(tab, "6_same_seed_again")

    print("\n7. RELOAD: forget the seed on screen, then restore the chart's own")
    panel = tab._manual_layout_panel
    panel.fixed_seed_cb.setChecked(False)
    panel.seed_spin.setValue(0)
    pump(app, 400)
    print("   box wiped to      :", seed_field(tab))
    restored_ok = False
    if ti2b is not None:
        tab._restore_chart_settings(ti2b)
        pump(app, 900)
        f7 = seed_field(tab)
        want = ti2_seed(ti2b)
        print("   after restore     :", f7)
        print("   the chart's seed  :", want)
        restored_ok = bool(want) and str(f7["spin"]) == want[1]
        print(f"   the reload round trip brings the seed back: {restored_ok}")
        shoot(tab, "7_after_reload")

    print("\n" + "=" * 78)
    print(f"{'step':30s} {'field':>12s} {'fixed':>6s} {'.ti2':>14s} {'sidecar':>12s}")
    for name, f, real, side in rows:
        print(f"{name:30s} {f['spin']:>12d} {str(f['fixed']):>6s} "
              f"{(real[1] if real else '-'):>14s} {str(side):>12s}")
    print("=" * 78)

    bad = [n for n, f, real, _ in rows
           if real is not None and str(f["spin"]) != real[1]]
    print("\nSteps where the field did NOT show the chart's seed:", bad or "none")
    print("Shots:", SHOTS)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
