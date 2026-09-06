#!/usr/bin/env python3
"""Same preset in, same chart out — the byte-for-byte half of the fix.

The Chart-layout-information panel is a READOUT. Correcting its estimate column
may not change one pixel of the chart that gets built, so this drives the real
window, generates both of Knut's CR30 presets with the seed PINNED (the only
thing about the chart that is deliberately random), and prints a digest of
everything the build wrote:

  * the page TIFF, byte for byte
  * the .ti2, with only ``CREATED`` (a wall clock) removed
  * the .ti1 the chart was laid out from
  * the engine's ``channels.json`` layout block (patch rects, in pixels)

Run it once on the fix and once without it and diff the two digests.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cs.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-cs-presets
    python scripts/drive_layout_estimate_chart_unchanged.py --out <file.json>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

PRESET_SRC = Path("/Users/Basti/Desktop/beta 9/knut-cr30-presets")
PRESETS = ("CR30-A4-360p-1page-Portrait-w11.0mm",
           "CR30-A4-192p-1page-Portrait-w11.0mm")
SEED = 20260906


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_run(run_dir: Path) -> dict:
    """Everything the build wrote, with the wall clock taken out and nothing
    else."""
    d: dict = {}
    for p in sorted(run_dir.iterdir()):
        if p.is_dir():
            continue
        if p.suffix in (".tif", ".tiff", ".ti1", ".cht", ".ps"):
            d[p.name] = sha(p.read_bytes())
        elif p.suffix == ".ti2":
            txt = p.read_text(encoding="latin-1")
            txt = re.sub(r'^CREATED\s+".*"\n', "", txt, flags=re.MULTILINE)
            d[p.name] = sha(txt.encode("utf-8"))
        elif p.name.endswith(".channels.json"):
            doc = json.loads(p.read_text(encoding="utf-8"))
            d[p.name] = sha(json.dumps(doc.get("layout") or {},
                                       sort_keys=True).encode("utf-8"))
    return d


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-cs-chart-digest.json")

    ini = os.environ.get("CHROMIQ_SETTINGS_FILE")
    pdir = os.environ.get("CHROMIQ_PRESETS_DIR")
    if not ini or not pdir:
        print("REFUSING TO RUN: CHROMIQ_SETTINGS_FILE and CHROMIQ_PRESETS_DIR "
              "must both be set — this driver would write into the owner's "
              "real preferences and preset folder.")
        return 2
    dest = Path(pdir) / "Create Chart"
    dest.mkdir(parents=True, exist_ok=True)
    for name in PRESETS:
        for ext in (".json", ".ti1"):
            shutil.copy2(PRESET_SRC / f"{name}{ext}", dest / f"{name}{ext}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    from core.settings import AppSettings
    settings = AppSettings()
    root = str(settings.get("custom_output_path", ""))
    if not root.startswith("/tmp/"):
        print("REFUSING TO RUN: the sandboxed .ini has no /tmp output path.")
        return 2
    settings.set("use_chromiq_layout_engine", True)

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1750, 1080)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 1200)

    digests: dict = {}
    for name in PRESETS:
        project = f"CS-Bytes-{name.split('-')[2]}"
        tab._manual_target_name_edit.setText(project)
        tab._mark_name_typed_by_user()
        pump(app, 600)
        idx = tab._preset_combo.findData(name)
        assert idx >= 0, f"{name} not in the dropdown"
        tab._preset_combo.setCurrentIndex(idx)
        tab._on_preset_activated(idx)
        for _ in range(180):
            pump(app, 500)
            if not tab._runner.is_running:
                break
        pump(app, 1500)
        # Pin the seed and rebuild, so the only deliberately random thing about
        # the chart is held still and the bytes can be compared at all.
        panel = tab._manual_layout_panel
        panel.fixed_seed_cb.setChecked(True)
        panel.seed_spin.setValue(SEED)
        pump(app, 1200)
        tab._on_generate()
        for _ in range(180):
            pump(app, 500)
            if not tab._runner.is_running:
                break
        pump(app, 2000)
        run = Path(tab._margin_ti2).parent
        digests[name] = {"run": run.name, **digest_run(run)}
        print(f"{name}: {json.dumps(digests[name], indent=2)}")

    out.write_text(json.dumps(digests, indent=2, sort_keys=True),
                   encoding="utf-8")
    print(f"\nwrote {out}")
    win.close()
    pump(app, 800)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
