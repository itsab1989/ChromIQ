#!/usr/bin/env python3
"""D04 (A5 furniture, A12 exports, A7 auto-update preview): i1Pro A4 clip,
area-first defaults, Auto count, 1 page. Each furniture option on its own;
estimate vs build, measured margins, files, preview shot. Then PDF export,
16-bit zlib, seed reproducibility, and the auto-update preview trigger."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402

OUT = L.SHOTS / "A5-furniture"
OUT12 = L.SHOTS / "A12-exports"
OUT7 = L.SHOTS / "A7-auto-preview"
PROJECT = "A5-Furniture"
LOGO = str(L.ASSESS / "Evidence" / "clip_test_logo.png")
R = []


def reset(p):
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip")
    L.set_combo_data(p.layout_mode, "area_first"); L.set_combo_data(p.area_method, "by_width")
    L.set_check(p.use_instr_margins, True)
    L.set_combo_data(p.clip_content_mode, "notes"); L.set_combo_data(p.clip_side, "left")
    L.set_spin(p.clip_width, 26.0); L.set_check(p.clip_flip_180, False)
    L.set_check(p.show_indicators, True); L.set_check(p.show_row_indicators, False)
    L.set_spin(p.indicator_size, 0.0); L.set_check(p.ind_bold, False); L.set_combo_data(p.indicator_rotation, 0)
    L.set_combo_data(p.underline_mode, "off")
    p.chart_text.setText(""); L.set_spin(p.chart_text_size, 0.0)
    L.set_check(p.stamp_command, False); L.set_check(p.edge_spacers_cb, False)
    L.set_check(p.helper_markers_cb, False)
    L.set_spin(p.offx, 0.0); L.set_spin(p.offy, 0.0)
    L.set_check(p.export_pdf, False); L.set_combo_data(p.bit_depth, 8); L.set_combo_data(p.compression, "lzw")
    L.set_combo_data(p.spacer_mode, "colored")
    L.set_check(p.randomize_cb, True)


def step(tag, win, tab, watcher, out, setup, note=""):
    p = tab._manual_layout_panel
    L.log(f"--- {tag}: {note}")
    reset(p); setup(p); L.pump(600)
    before = L.panel_snapshot(tab)
    rec = L.recipe_of(tab)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    n0 = len(L.SERIOUS); t0 = time.time()
    L.click(tab._generate_btn)
    ok = L.wait_build(tab, 300_000); watcher.clear()
    after = L.panel_snapshot(tab)
    L.grab(tab._preview, out / f"{tag}-preview.png")
    rd = L.current_run_dir(win); inv = L.run_inventory(rd) if rd else {}
    logtxt = L.tab_log_text(tab)
    eng = [l for l in logtxt.splitlines() if "layout engine]" in l or "[ERROR]" in l or "wrote" in l][-6:]
    r = {"tag": tag, "note": note, "ok": ok, "secs": round(time.time() - t0, 1),
         "est_before": before["layout_info_estimate"], "actual": after["layout_info_actual"], "est_after": after["layout_info_estimate"],
         "margin_text": after["margin_panel_text"][:330], "status": after["margin_status"], "notes": after["margin_notes"],
         "files": [f for f, _ in inv.get("files", [])], "tiffs": inv.get("tiffs"), "ti2": {k: v for k, v in inv.items() if k.startswith("ti2")},
         "recipe": {k: rec.get(k) for k in ("clip_content_mode", "clip_side", "clip_border_width_mm", "clip_flip_180", "show_strip_indicators",
                                            "show_row_indicators", "indicator_size_mm", "indicator_bold", "indicator_rotation", "underline_mode",
                                            "chart_text", "chart_text_size_mm", "stamp_command", "edge_spacers", "helper_markers", "offset_x_mm",
                                            "offset_y_mm", "export_pdf", "bit16", "compression", "spacer_mode", "randomize", "seed", "clip_image_path")},
         "engine_log": eng, "serious": L.serious_since(n0), "unexpected": list(watcher.unexpected)}
    watcher.unexpected.clear()
    R.append(r); L.save_json(R, L.LOGS / "d04_results.json")
    L.log(f"    est={r['est_before'] and (r['est_before']['total'], r['est_before']['rows'], r['est_before']['cols'])} act={r['actual'] and (r['actual']['total'], r['actual']['rows'], r['actual']['cols'])} margins={r['margin_text'][:150]} notes={r['notes']!r} files={[f for f in r['files'] if not f.startswith(('cache', 'exports'))]}")
    return r


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn); L.pump(400)
    tab._manual_target_name_edit.setText(PROJECT); tab._manual_target_name_edit.editingFinished.emit(); L.pump(300)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    p = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_spin(p.pages, 1)
    watcher.expect("Give this project a name", "<reject>")
    # visibility of the expert groups
    L.log(f"clip content group visible={p._clip_content_grp.isVisible()}  helper cb visible={p.helper_markers_cb.isVisible()} chart_text visible={p.chart_text.isVisible()} stamp visible={p.stamp_command.isVisible()}")

    step("f01-baseline-notes", win, tab, watcher, OUT, lambda p: None, "clip on, notes box")
    step("f02-clip-text", win, tab, watcher, OUT, lambda p: (L.set_combo_data(p.clip_content_mode, "text"), p.clip_text.setPlainText("Custom {project} {date} {instrument} {paper} {patches}")), "clip content: custom text with tokens")
    step("f03-clip-example", win, tab, watcher, OUT, lambda p: L.set_combo_data(p.clip_content_mode, "example"), "clip content: example table")
    step("f04-clip-branding", win, tab, watcher, OUT, lambda p: L.set_combo_data(p.clip_content_mode, "branding"), "clip content: branding")
    step("f05-clip-off", win, tab, watcher, OUT, lambda p: L.set_combo_data(p.clip_content_mode, "off"), "clip content: off (border stays)")
    step("f06-clip-image", win, tab, watcher, OUT, lambda p: (L.set_combo_data(p.clip_content_mode, "image"), p.clip_image_path.setText(LOGO), p.clip_image_path.editingFinished.emit()), "clip content: imported image")
    step("f07-clip-right-w40-flip", win, tab, watcher, OUT, lambda p: (L.set_combo_data(p.clip_side, "right"), L.set_spin(p.clip_width, 40.0), L.set_check(p.clip_flip_180, True)), "clip on the right, 40 mm, flipped")
    step("f08-no-strip-indicators", win, tab, watcher, OUT, lambda p: L.set_check(p.show_indicators, False), "strip indicators off")
    step("f09-row-indicators", win, tab, watcher, OUT, lambda p: L.set_check(p.show_row_indicators, True), "row indicators on")
    step("f10-indicator-6mm-bold-rot90", win, tab, watcher, OUT, lambda p: (L.set_spin(p.indicator_size, 6.0), L.set_check(p.ind_bold, True), L.set_combo_data(p.indicator_rotation, 90)), "indicator 6 mm bold rotated 90")
    step("f11-underline-black", win, tab, watcher, OUT, lambda p: L.set_combo_data(p.underline_mode, "black"), "underline black")
    step("f12-sheet-text", win, tab, watcher, OUT, lambda p: (p.chart_text.setText("Sheet {project} · {date} · {patches} patches · {rundescription}"), p.chart_text.editingFinished.emit(), L.set_spin(p.chart_text_size, 5.0)), "sheet text with tokens, 5 mm")
    step("f13-stamp", win, tab, watcher, OUT, lambda p: L.set_check(p.stamp_command, True), "stamp layout summary")
    step("f14-edge-spacers", win, tab, watcher, OUT, lambda p: L.set_check(p.edge_spacers_cb, True), "edge spacers")
    # helper markers: overlay proposal first (off), then printed
    reset(p); L.pump(300)
    L.grab(tab._preview, OUT / "f15a-helper-markers-off-overlay.png")
    step("f15-helper-markers", win, tab, watcher, OUT, lambda p: L.set_check(p.helper_markers_cb, True), "helper markers printed (default 2 mm edge, 2 mm long, 3 per patch)")
    L.log(f"    helper tips: cb={p.helper_markers_cb.toolTip()[:160]!r} edges_note={getattr(p, '_hm_edges_tip', None) and p._hm_edges_tip.toolTip()[:120]!r}")
    step("f16-offset-10-10", win, tab, watcher, OUT, lambda p: (L.set_spin(p.offx, 10.0), L.set_spin(p.offy, 10.0)), "page X/Y offset 10/10 mm")
    step("f17-spacers-bw", win, tab, watcher, OUT, lambda p: L.set_combo_data(p.spacer_mode, "bw"), "spacers black & white")
    step("f18-spacers-none", win, tab, watcher, OUT, lambda p: L.set_combo_data(p.spacer_mode, "none"), "spacers none")
    # A12 exports
    step("x01-export-pdf", win, tab, watcher, OUT12, lambda p: L.set_check(p.export_pdf, True), "also export a PDF")
    step("x02-16bit-zlib", win, tab, watcher, OUT12, lambda p: (L.set_combo_data(p.bit_depth, 16), L.set_combo_data(p.compression, "zlib")), "16-bit zlib")
    # seed reproducibility
    def fixed(p):
        L.set_check(p.randomize_cb, True)
        L.set_check(p.fixed_seed_cb, True); L.set_spin(p.seed_spin, 12345)
    r1 = step("s01-seed-12345-a", win, tab, watcher, OUT12, fixed, "fixed seed 12345, first")
    rd = L.current_run_dir(win); ti2a = next(rd.glob("*.ti2")).read_text(errors="replace")
    r2 = step("s02-seed-12345-b", win, tab, watcher, OUT12, fixed, "fixed seed 12345, second")
    ti2b = next(rd.glob("*.ti2")).read_text(errors="replace")
    same = [l for l in ti2a.splitlines() if l and l[0].isalpha() and l[0:1] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and "\t" in l or " " in l][:5]
    def body(t):
        return "\n".join(l for l in t.splitlines() if not l.startswith(("CREATED", "ORIGINATOR", "CHROMIQ", "DESCRIPTOR")))
    L.log(f"    seed reproducibility: identical bodies={body(ti2a) == body(ti2b)}  seed shown={p.seed_spin.value()}")
    R.append({"tag": "seed", "identical": body(ti2a) == body(ti2b), "seed": p.seed_spin.value()})
    L.set_check(p.fixed_seed_cb, False)

    # ---- A7 auto-update preview ----
    reset(p); L.pump(300)
    step("a00-auto-baseline", win, tab, watcher, OUT7, lambda p: None, "baseline before auto-update")
    rd = L.current_run_dir(win)
    def mtimes():
        return {f.name: round(f.stat().st_mtime, 2) for f in rd.iterdir() if f.is_file()}
    m0 = mtimes()
    L.log(f"auto-update checkbox visible={tab._auto_preview_check.isVisible()} checked={tab._auto_preview_check.isChecked()} setting={settings.get('auto_update_preview')}")
    L.set_check(tab._auto_preview_check, True)
    L.log(f"after tick: setting={settings.get('auto_update_preview')}")
    watcher.expect("quite fill", "OK")
    t0 = time.time()
    L.set_spin(p.margins["t"], 45.0)      # a layout change with instrument margins ON?  boxes are locked; use area min patch instead
    L.set_spin(p.area_min_patch, 10.0)
    fired = L.wait_until(lambda: tab._runner.is_running or mtimes() != m0, 4000, "auto preview to start")
    t1 = time.time()
    ok = L.wait_build(tab, 120_000)
    m1 = mtimes()
    changed = sorted(k for k in set(m0) | set(m1) if m0.get(k) != m1.get(k))
    s = L.panel_snapshot(tab)
    L.log(f"auto-update: fired={fired} after {round(t1 - t0, 2)} s; build ok={ok}; files rewritten={changed}; actual={s['layout_info_actual']} est={s['layout_info_estimate']} log_tail={[l for l in L.tab_log_text(tab).splitlines() if 'engine]' in l or 'Live' in l or 'live' in l][-3:]}")
    L.grab(win, OUT7 / "a01-after-auto-update.png")
    R.append({"tag": "auto-update", "fired": fired, "delay_s": round(t1 - t0, 2), "files_rewritten": changed, "actual": s["layout_info_actual"], "est": s["layout_info_estimate"]})
    # a non-layout change should not fire
    m2 = mtimes()
    tab._manual_chart_notes_edit.setText("notes only"); tab._manual_chart_notes_edit.editingFinished.emit()
    fired2 = L.wait_until(lambda: tab._runner.is_running or mtimes() != m2, 2500, "(should not fire)")
    L.log(f"auto-update on chart-notes edit: fired={fired2}")
    # a second nudge quickly twice: one build or two?
    m3 = mtimes(); n_before = L.tab_log_text(tab).count("random start")
    L.set_spin(p.area_min_patch, 11.0); L.pump(150); L.set_spin(p.area_min_patch, 12.0)
    L.wait_until(lambda: mtimes() != m3, 4000, "auto preview")
    L.wait_build(tab, 120_000); L.pump(1500)
    n_after = L.tab_log_text(tab).count("random start")
    L.log(f"two nudges 150 ms apart -> builds={n_after - n_before}")
    R.append({"tag": "auto-update-debounce", "builds_for_two_nudges": n_after - n_before, "fired_on_notes": fired2})
    L.set_check(tab._auto_preview_check, False)
    L.save_json(R, L.LOGS / "d04_results.json")
    L.log(f"unexpected: {watcher.unexpected} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
