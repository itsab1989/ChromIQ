#!/usr/bin/env python3
"""On-screen proof for fix/preset-goes-stale.

Drives the REAL ChromIQ window against a sandboxed settings file and a
sandboxed working folder, and answers four questions in order:

  1. What does the layout panel hold right after a built-in preset is applied?
  2. Does a second Generate draw the same sheet as the first? (page hashes)
  3. What did the run's meta.json record as its Create Chart layout?
  4. Knut's beta-5 journey: preset, then instrument -> CR30. Does the
     "Create layout" mode flip, and if so, which code moved it?

Run it twice — once with the guard in `_open_this_target_on_its_defaults`
removed, once with it in — and the two JSON files are the before/after.

    CHROMIQ_SETTINGS_FILE=/tmp/preset.ini \
    CHROMIQ_PRESETS_DIR=/tmp/preset-presets \
    python scripts/drive_preset_stale_proof.py --out DIR --tag before|after
"""
from __future__ import annotations

import hashlib
import json
import os
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

from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

CM84 = ("__chromiq_knut_cm_a4_84p_1page_portrait_w26_0mm_fast_reading_"
        "speed_hand_held__")
PROJECT = "Preset-Stale-Proof"

modals: list[dict] = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(widget, path: Path) -> str:
    ok = widget.grab().save(str(path))
    print(f"    shot {path.name}: {'saved' if ok else 'FAILED'}")
    return path.name if ok else ""


def install_modal_watchdog(app, out: Path):
    """Never leave a modal open — grab it, record it, close it."""
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        name = f"modal_{len(modals):02d}.png"
        try:
            w.grab().save(str(out / name))
        except Exception:
            name = ""
        modals.append({"title": title, "text": text[:400], "shot": name})
        print(f"    !! modal appeared: {title!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(500)
    t.timeout.connect(check)
    t.start()
    return t


def recipe_facts(tab) -> dict:
    r = tab._manual_layout_panel.get_recipe()
    return {
        "instrument": r.instrument, "paper": r.paper,
        "layout_mode": r.layout_mode, "area_method": r.area_method,
        "area_cols": r.area_cols, "area_rows": r.area_rows,
        "area_min_patch_mm": r.area_min_patch_mm,
        "margin_left": r.margin_left, "margin_top": r.margin_top,
        "margin_right": r.margin_right, "margin_bottom": r.margin_bottom,
        "spacer_mode": r.spacer_mode, "clip_border_width_mm": r.clip_border_width_mm,
        "helper_markers": r.helper_markers,
    }


def geometry_digest(run_dir: Path) -> dict:
    """The sheet's LAYOUT, with the colours left out.

    The ColorMunki family's recipe carries ``randomize: True`` and no fixed
    seed, so two builds legitimately place different colours in the same
    boxes and the TIFF bytes differ by design. What must NOT differ is where
    the boxes are — that is what "a second Generate lays out differently"
    means, and it is what the sidecar records.
    """
    import json as _json
    out = {}
    for side in sorted(run_dir.glob("*.channels.json")):
        lay = _json.loads(side.read_text(encoding="utf-8")).get("layout", {})
        geo = {
            "paper_mm": lay.get("paper_mm"),
            "steps_in_pass": lay.get("steps_in_pass"),
            "strips": [(s_["page"], s_["x"], s_["y"], s_["w"], s_["h"])
                       for s_ in lay.get("strips", [])],
            "patches": [(q["page"], q["loc"], q["x"], q["y"], q["w"], q["h"])
                        for q in lay.get("patches", [])],
        }
        out[side.name] = hashlib.sha256(
            _json.dumps(geo, sort_keys=True).encode()).hexdigest()[:16]
        out[side.name + ":patch_w_px"] = (
            lay.get("patches", [{}])[0].get("w") if lay.get("patches") else None)
    return out


def page_hashes(run_dir: Path) -> dict:
    out = {}
    for tif in sorted(run_dir.glob("*.tif")):
        out[tif.name] = hashlib.sha256(tif.read_bytes()).hexdigest()[:16]
    return out


def wait_for_build(app, tab, timeout=180) -> bool:
    end = time.time() + timeout
    pump(app, 800)
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            pump(app, 1500)
            if tab._generate_btn.isEnabled() and not tab._runner.is_running:
                return True
    return False


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path.home() / "Desktop/beta7/preset-stale-proof"
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    from core.settings import AppSettings
    settings = AppSettings()
    work = Path("/tmp/preset-work")
    if (work / PROJECT).exists():
        shutil.rmtree(work / PROJECT)
    work.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    assert settings.get("custom_output_path", "") == str(work)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(app, 900)
    watchdog = install_modal_watchdog(app, out)

    tab = win._tab_chart
    res: dict = {"tag": tag}

    # -- Manual mode, and a project name so the §S4.7 name prompt has nothing
    #    to ask. Typed the way a person types it.
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 300)
    tab._refresh_manual_command_preview()
    pump(app, 300)
    tab._manual_target_name_edit.setText(PROJECT)
    pump(app, 200)

    res["01_panel_before_preset"] = recipe_facts(tab)
    print("01 panel before preset:", json.dumps(res["01_panel_before_preset"]))
    res["shots"] = [shot(win, out / f"{tag}_01_before_preset.png")]

    # -- The preset the report names, chosen the way the overlay chooses it.
    print("02 applying built-in ColorMunki A4 84p Hand Held")
    tab._activate_builtin_preset(CM84)
    ok = wait_for_build(app, tab)
    res["02_build_finished"] = ok
    pump(app, 800)

    res["03_panel_after_preset"] = recipe_facts(tab)
    print("03 panel after preset :", json.dumps(res["03_panel_after_preset"]))
    res["shots"].append(shot(win, out / f"{tag}_03_after_preset.png"))
    if getattr(tab, "_manual_layout_grp", None) is not None:
        res["shots"].append(
            shot(tab._manual_layout_grp, out / f"{tag}_03_layout_panel.png"))

    # -- What the preset itself asks for, straight from the registry.
    from ui.tabs.tab_chart import KNUT_PRESETS_BY_KEY
    from workflow.layout_engine.presets import LayoutRecipe
    want = LayoutRecipe.from_dict(KNUT_PRESETS_BY_KEY[CM84].layout_recipe)
    res["00_preset_says"] = {
        k: getattr(want, k) for k in res["01_panel_before_preset"]}
    res["04_panel_matches_preset"] = (
        res["03_panel_after_preset"] == res["00_preset_says"])
    print("04 panel == preset    :", res["04_panel_matches_preset"])

    # -- Page hashes of the first sheet, kept before anything can overwrite it.
    proj_dir = work / PROJECT
    run_dir = proj_dir / "runs" / "run1"
    res["05_first_generate_hashes"] = page_hashes(run_dir)
    res["05b_first_generate_geometry"] = geometry_digest(run_dir)
    keep = out / f"{tag}_pages_first"
    keep.mkdir(exist_ok=True)
    for t in run_dir.glob("*.tif"):
        shutil.copy2(t, keep / t.name)

    # -- What went into the store.
    try:
        import json as _json
        meta = _json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        rec = (meta.get("create_chart_ui") or {}).get("engine_recipe") or {}
        res["06_meta_json_recipe"] = {
            k: rec.get(k) for k in res["01_panel_before_preset"]}
        res["07_meta_matches_preset"] = (
            res["06_meta_json_recipe"] == res["00_preset_says"])
    except Exception as exc:
        res["06_meta_json_recipe"] = f"{type(exc).__name__}: {exc}"
        res["07_meta_matches_preset"] = None
    print("07 meta == preset     :", res.get("07_meta_matches_preset"))

    # -- SECOND Generate, nothing touched in between.
    print("08 pressing Generate a second time")
    tab._generate_btn.click()
    ok2 = wait_for_build(app, tab)
    res["08_second_build_finished"] = ok2
    pump(app, 800)
    res["09_second_generate_hashes"] = page_hashes(run_dir)
    res["09b_second_generate_geometry"] = geometry_digest(run_dir)
    res["10_two_generates_same_geometry"] = (
        res["05b_first_generate_geometry"] == res["09b_second_generate_geometry"]
        and bool(res["05b_first_generate_geometry"]))
    res["10b_two_generates_byte_identical"] = (
        res["05_first_generate_hashes"] == res["09_second_generate_hashes"])
    print("10 two Generates, same LAYOUT:", res["10_two_generates_same_geometry"])
    print("   first :", res["05b_first_generate_geometry"])
    print("   second:", res["09b_second_generate_geometry"])
    print("10b byte-identical (randomise is on, so expect False):",
          res["10b_two_generates_byte_identical"])
    res["shots"].append(shot(win, out / f"{tag}_10_after_second_generate.png"))
    res["11_panel_after_second_generate"] = recipe_facts(tab)

    # -- WITH THE ONLY LEGITIMATE DIFFERENCE REMOVED: tick "Use a fixed seed"
    #    on the panel, the way a person would, and build twice more. Now the
    #    printed sheet itself must come back byte for byte.
    print("11b fixing the seed, then two more Generates")
    try:
        p0 = tab._manual_layout_panel
        p0.randomize_cb.setChecked(True)
        p0.fixed_seed_cb.setChecked(True)
        p0.seed_spin.setValue(4242)
        pump(app, 400)
        tab._generate_btn.click()
        wait_for_build(app, tab)
        pump(app, 600)
        res["11c_seeded_first"] = page_hashes(run_dir)
        tab._generate_btn.click()
        wait_for_build(app, tab)
        pump(app, 600)
        res["11d_seeded_second"] = page_hashes(run_dir)
        res["11e_seeded_byte_identical"] = (
            res["11c_seeded_first"] == res["11d_seeded_second"]
            and bool(res["11c_seeded_first"]))
        print("11e seeded pair byte-identical:",
              res["11e_seeded_byte_identical"])
        print("   ", res["11c_seeded_first"], res["11d_seeded_second"])
        res["11f_panel_after_seeded_pair"] = recipe_facts(tab)
    except Exception as exc:
        res["11e_seeded_byte_identical"] = f"{type(exc).__name__}: {exc}"

    # -- Knut's journey, exactly as he wrote it.
    print("12 Knut's journey: instrument -> CR30")
    p = tab._manual_layout_panel
    res["12_mode_before_cr30"] = p.get_recipe().layout_mode
    i = p.instr.findData("CR30")
    p.instr.setCurrentIndex(i)
    pump(app, 600)
    res["13_mode_after_cr30"] = p.get_recipe().layout_mode
    res["14_mode_flipped"] = res["12_mode_before_cr30"] != res["13_mode_after_cr30"]
    res["15_panel_after_cr30"] = recipe_facts(tab)
    print(f"   mode {res['12_mode_before_cr30']} -> {res['13_mode_after_cr30']}")
    res["shots"].append(shot(win, out / f"{tag}_13_after_cr30.png"))
    if getattr(tab, "_manual_layout_grp", None) is not None:
        res["shots"].append(
            shot(tab._manual_layout_grp, out / f"{tag}_13_layout_panel_cr30.png"))

    # -- ...and Generate after it, which is the rest of Knut's sentence:
    #    "Generate Chart then changed appearance (much smaller patches)".
    print("16 Generate after the CR30 switch")
    try:
        tab._generate_btn.click()
        wait_for_build(app, tab)
        pump(app, 800)
        res["16_geometry_after_cr30_generate"] = geometry_digest(run_dir)
        res["17_patch_width_px_preset_vs_cr30"] = [
            res["05b_first_generate_geometry"].get(
                "Preset-Stale-Proof.channels.json:patch_w_px"),
            res["16_geometry_after_cr30_generate"].get(
                "Preset-Stale-Proof.channels.json:patch_w_px")]
        print("17 patch width px, preset -> after CR30:",
              res["17_patch_width_px_preset_vs_cr30"])
        res["shots"].append(
            shot(win, out / f"{tag}_16_generated_on_cr30.png"))
    except Exception as exc:
        res["16_geometry_after_cr30_generate"] = f"{type(exc).__name__}: {exc}"

    res["modals"] = modals
    watchdog.stop()
    win.close()
    pump(app, 300)

    (out / f"{tag}_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nwrote {out / (tag + '_results.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
