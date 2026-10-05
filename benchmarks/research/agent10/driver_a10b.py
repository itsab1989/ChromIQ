"""Agent 10b: the Build Profile options, ON SCREEN, in the real app.

Real ChromIQ window (research tree research/pe-options-p2 = integration 2),
real display. What it does:

  A. engine ON (Preferences > Beta: ChromIQ engine, Maximum accuracy): the
     Manual tab photographed group by group; then one build per option on an
     RGB, a CMYK and a CMYKOG project (battery v3 measurements), each with its
     log, its profile and a photograph of the window;
  B. switching the engine OFF and ON again with non-default values set in
     colprof controls and in the engine rows: which rows hide, and whether
     every value comes back;
  C. engine OFF: ten builds whose profile is then compared byte for byte with
     the same colprof command typed by hand (run afterwards, not here);
     three refusals (D65M2, -V 3.5, -bn) shown with their log.

Safety, every run:
* settings sandboxed (CHROMIQ_SETTINGS_FILE, a fresh .ini per run);
  projects in this folder; the real store is never touched;
* scripts/capture_screens.build_app: FocusGiveBack (never takes Basti's
  keyboard), keep_display_awake (only while this process lives), C numeric
  locale, the app's own event filters;
* PopupWatchdog policy "dismiss": every unscripted question is answered with
  its own Escape/Cancel within 2 s and logged; "Profile Built" (Done) and
  "Profile Build Failed" (recorded, closed) are scripted explicitly;
* captures never raise or activate a window (capture_window, window id);
* a guard thread gives every step a budget (120 s for UI steps; a build
  step says its own) and ends the process itself (stacks to hang-*.txt,
  os._exit) if one runs out, or if a modal window stays open 60 s;
* the run ends with os._exit after writing result.json.

    python driver_a10b.py --offscreen --only rgb-default,rgb-kx     # dry run
    python driver_a10b.py                                            # all
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
A10 = HERE.parent
TREE = A10 / "tree"
WORK = A10 / "p2" / "run1" / "work"
CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"
CMYK_SRC = "/Applications/Argyll/ref/cmyk.icm"

ap = argparse.ArgumentParser()
ap.add_argument("--offscreen", action="store_true")
ap.add_argument("--only", default="", help="comma-separated build labels")
ap.add_argument("--parts", default="A,B,C")
ap.add_argument("--tag", default="")
ARGS = ap.parse_args()

RUN = "dry" if ARGS.offscreen else "run"
OUT = HERE / (RUN + (f"-{ARGS.tag}" if ARGS.tag else ""))
SANDBOX = OUT / "sandbox"
PROJECTS = SANDBOX / "projects"
PROFILES = OUT / "profiles"
LOGS = OUT / "logs"
for d in (PROJECTS, PROFILES, LOGS):
    d.mkdir(parents=True, exist_ok=True)
ini = SANDBOX / "ChromIQ.ini"
if ini.exists():
    ini.unlink()
os.environ["CHROMIQ_SETTINGS_FILE"] = str(ini)
for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[k] = "1"
os.environ["CHROMIQ_ENGINE_THREADS"] = "1"
os.environ.pop("CHROMIQ_ENGINE_NEXT", None)
os.environ.setdefault("CHROMIQ_GAMMAP", "/Users/Basti/develop/ChromIQ/native/chromiq-gammap")
(OUT / "tmp").mkdir(exist_ok=True)
os.environ["TMPDIR"] = str(OUT / "tmp")
if ARGS.offscreen:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path[:0] = [str(TREE), str(TREE / "scripts")]
os.chdir(TREE)

LOG = OUT / "driver.log"
LOG.write_text("")
RESULT: dict = {"mode": "offscreen (dry run)" if ARGS.offscreen else "on screen",
                "builds": [], "toggle": {}, "groups": {}}


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def write_result():
    (OUT / "result.json").write_text(json.dumps(RESULT, indent=1, default=str))


# ---------------------------------------------------------------------------
# the guard: every step has a budget; the process ends itself
# ---------------------------------------------------------------------------
class Guard(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.name_ = "start"
        self.deadline = time.time() + 120
        self.total_end = time.time() + 10 * 3600

    def step(self, name, budget=120):
        self.name_ = name
        self.deadline = time.time() + budget
        log(f"-- step {name} (budget {budget} s)")

    def run(self):
        while True:
            time.sleep(1.0)
            now = time.time()
            if now > self.deadline or now > self.total_end:
                why = f"step {self.name_!r} ran out of its budget"
                p = OUT / f"hang-{int(now)}.txt"
                with p.open("w") as fh:
                    fh.write(why + "\n")
                    faulthandler.dump_traceback(file=fh, all_threads=True)
                RESULT["hang"] = why
                try:
                    write_result()
                    log(f"GUARD: {why}; stacks in {p.name}; ending the process")
                except Exception:  # noqa: BLE001
                    pass
                os._exit(3)


GUARD = Guard()
GUARD.start()

from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QPushButton, QDialog     # noqa: E402

from capture_screens import build_app                             # noqa: E402
from onscreen_capture import PopupWatchdog, capture_window        # noqa: E402


def pump(ms):
    end = time.time() + ms / 1000.0
    while time.time() < end:
        QApplication.processEvents()
        time.sleep(0.02)


MODAL_SINCE = [None]


def wait_until(pred, timeout_s, what):
    end = time.time() + timeout_s
    while time.time() < end:
        QApplication.processEvents()
        m = QApplication.activeModalWidget()
        if m is not None and m.isVisible():
            MODAL_SINCE[0] = MODAL_SINCE[0] or time.time()
            if time.time() - MODAL_SINCE[0] > 60:
                GUARD.name_ += f": modal {type(m).__name__} {m.windowTitle()!r} left open"
                GUARD.deadline = 0
                time.sleep(5)
        else:
            MODAL_SINCE[0] = None
        try:
            if pred():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.05)
    log(f"TIMEOUT waiting for {what}")
    return False


def shot(win, name):
    if ARGS.offscreen:
        return False
    ok, why = capture_window(win, OUT / f"{name}.png", allow_hide=False)
    log(f"capture {name}: {'ok' if ok else 'FAILED ' + why}")
    RESULT.setdefault("captures", {})[name] = True if ok else why
    return ok


def button(w, text):
    want = text.replace("&", "")
    for b in w.findChildren(QPushButton):
        if b.text().replace("&", "") == want and b.isVisible():
            return b
    return None


# ---------------------------------------------------------------------------
# what is built
# ---------------------------------------------------------------------------
PROJECTS_SRC = {
    "rgb": WORK / "X1-typical-s23-targen400.ti3",
    "cmyk": WORK / "X3-typical-s23-targen400.ti3",
    "cmykog": WORK / "X5-typical-s23-targen900.ti3",
}

# (label, project, preset-data overrides, expected ProfileParams values,
#  what the log or profile should show). Quality "l" unless the row says.
META = {"mfr_enabled": True, "mfr": "ACME Print", "model_enabled": True, "model": "Model 9",
        "copy_enabled": True, "copy": "© 2026 Test Druck", "z_surface": "m",
        "z_media_type": "t", "z_polarity": "n", "z_color_mode": "b",
        "z_default_intent": "p", "no_embedded": True}
ENGINE_ON = [
    ("rgb-default", "rgb", {}, {}),
    ("rgb-meta", "rgb", dict(META, _desc="Prüfdruck Müller"),
     {"manufacturer": "ACME Print", "z_default_intent": "p", "no_embedded_data": True}),
    ("rgb-ax", "rgb", {"algorithm": "x"}, {"algorithm": "x"}),
    ("rgb-qm", "rgb", {"quality": "m"}, {"quality": "m"}),
    ("rgb-bh", "rgb", {"b2a_enabled": True, "b2a_quality": "h"}, {"b2a_quality": "h"}),
    ("rgb-bn", "rgb", {"b2a_enabled": True, "b2a_quality": "n"}, {"b2a_quality": "n"}),
    ("rgb-r2", "rgb", {"smoothing": 2.0}, {"smoothing": 2.0}),
    ("rgb-V2", "rgb", {"dark_emphasis": 2.0}, {"dark_emphasis": 2.0}),
    ("rgb-iD65", "rgb", {"illuminant": "D65"}, {"illuminant": "D65"}),
    ("rgb-iD65M2", "rgb", {"illuminant": "D65M2"}, {"illuminant": "D65M2"}),
    ("rgb-o1964", "rgb", {"observer": "1964_10"}, {"observer": "1964_10"}),
    ("rgb-kx", "rgb", {"kgen_rule": "x"}, {"k_rule": "x"}),
    ("rgb-gnone", "rgb", {"gamut_mode": ""}, {"gamut_sat_src": ""}),
    ("rgb-gs", "rgb", {"gamut_mode": "s"}, {"gamut_src": CLAY}),
    ("rgb-ni", "rgb", {"no_input_shaper": True}, {"no_input_shaper": True}),
    ("rgb-no", "rgb", {"no_output_shaper": True}, {"no_output_shaper": True}),
    ("rgb-np", "rgb", {"no_grid_pos": True}, {"no_grid_pos": True}),
    ("rgb-v4", "rgb", {"icc_version": "4"}, {"icc_version": "4"}),
    ("rgb-noise", "rgb", {"noise_model": True}, {"noise_model": True}),
    ("rgb-physics", "rgb", {"spectral_physics": True}, {"spectral_physics": True}),
    ("rgb-bijective", "rgb", {"render_style": "bijective"}, {"render_style": "bijective"}),
    ("cmyk-default", "cmyk", {}, {}),
    ("cmyk-kz", "cmyk", {"kgen_rule": "z"}, {"k_rule": "z"}),
    ("cmyk-kx", "cmyk", {"kgen_rule": "x"}, {"k_rule": "x"}),
    ("cmyk-kr", "cmyk", {"kgen_rule": "r"}, {"k_rule": "r"}),
    ("cmyk-kp", "cmyk", {"kgen_rule": "p", "kgen_curve": [0.0, 0.1, 0.9, 1.0, 1.0]},
     {"k_rule": "p"}),
    ("cmyk-Kx", "cmyk", {"kgen_rule": "x", "kgen_locus": True}, {"k_locus": True}),
    ("cmyk-tpa", "cmyk", {"perc_intent_enabled": True, "perc_intent": "pa"},
     {"perc_intent": "pa"}),
    ("cmyk-Tms", "cmyk", {"sat_intent_enabled": True, "sat_intent": "ms"},
     {"sat_intent": "ms"}),
    ("cmyk-cd", "cmyk", {"src_viewing": "mt", "dst_viewing": "pp"},
     {"src_viewing_cond": "mt", "dst_viewing_cond": "pp"}),
    ("cmyk-nP-cmyksrc", "cmyk", {"gamut_src": CMYK_SRC, "no_perc_gamut": True},
     {"no_perc_gamut": True, "gamut_sat_src": CMYK_SRC}),
    ("cmyk-nI", "cmyk", {"inv_gamut": True}, {"inv_gamut_map": True}),
    ("cmyk-r025", "cmyk", {"smoothing": 0.25}, {"smoothing": 0.25}),
    ("cmyk-iF8", "cmyk", {"illuminant": "F8"}, {"illuminant": "F8"}),
    ("cmyk-f", "cmyk", {"fwa_enabled": True}, {"fwa_enabled": True}),
    ("cmyk-bn", "cmyk", {"b2a_enabled": True, "b2a_quality": "n"}, {"b2a_quality": "n"}),
    ("cmyk-v4", "cmyk", {"icc_version": "4"}, {"icc_version": "4"}),
    ("cmyk-noise", "cmyk", {"noise_model": True}, {"noise_model": True}),
    ("cmyk-bijective", "cmyk", {"render_style": "bijective"}, {"render_style": "bijective"}),
    ("cmykog-default", "cmykog", {}, {}),
    ("cmykog-kx", "cmykog", {"kgen_rule": "x"}, {"k_rule": "x"}),
    ("cmykog-tpa", "cmykog", {"perc_intent_enabled": True, "perc_intent": "pa"},
     {"perc_intent": "pa"}),
]
# engine OFF: ten states built in the app, then repeated by hand (byte check)
ENGINE_OFF = [
    ("off-default", "cmyk", {}, {}),
    ("off-qh", "cmyk", {"quality": "h"}, {"quality": "h"}),
    ("off-bh", "cmyk", {"b2a_enabled": True, "b2a_quality": "h"}, {"b2a_quality": "h"}),
    ("off-r1", "cmyk", {"smoothing": 1.0}, {"smoothing": 1.0}),
    ("off-kx", "cmyk", {"kgen_rule": "x"}, {"k_rule": "x"}),
    ("off-kp", "cmyk", {"kgen_rule": "p", "kgen_curve": [0.1, 0.2, 0.8, 0.9, 1.2]},
     {"k_rule": "p"}),
    ("off-tpa", "cmyk", {"perc_intent_enabled": True, "perc_intent": "pa"},
     {"perc_intent": "pa"}),
    ("off-nI", "cmyk", {"inv_gamut": True}, {"inv_gamut_map": True}),
    ("off-nc", "cmyk", {"no_embedded": True}, {"no_embedded_data": True}),
    ("off-Zmp", "cmyk", {"z_surface": "m", "z_default_intent": "p"}, {"z_surface": "m"}),
    # the three engine-off refusals Part 1 found (reported, not fixed)
    ("off-iD65M2", "cmyk", {"illuminant": "D65M2"}, {"illuminant": "D65M2"}),
    ("off-V3.5", "cmyk", {"dark_emphasis": 3.5}, {"dark_emphasis": 3.5}),
    ("off-bn", "cmyk", {"b2a_enabled": True, "b2a_quality": "n"}, {"b2a_quality": "n"}),
]


def selected(rows):
    want = [x for x in ARGS.only.split(",") if x]
    return [r for r in rows if not want or r[0] in want]


# ---------------------------------------------------------------------------
# app helpers
# ---------------------------------------------------------------------------
STATE = {"project": None}


def engine(settings, on: bool):
    settings.set("profile_engine_beta", bool(on))
    settings.set("gammap_mode", "accurate")


def revisit_build_tab(win):
    """A Preferences change takes effect on the next visit of the tab
    (`_refresh_engine_rows` runs on showEvent): go to Measure and back."""
    win._tabs.setCurrentWidget(win._tab_measure)
    pump(400)
    win._tabs.setCurrentWidget(win._tab_profile)
    pump(800)


def open_project(win, key):
    if STATE["project"] == key:
        return
    GUARD.step(f"open project {key}")
    fm = win._file_mgr
    name = f"A10b-{key}"
    fm.set_target_name(name)
    run = fm.project().current_run()
    run.ensure_dir()
    meas = run.dir / f"{run.stem}.ti3"
    if not meas.exists():
        shutil.copy2(PROJECTS_SRC[key], meas)
    win._on_measure_done(meas)
    pump(800)
    pt = win._tab_profile
    win._tabs.setCurrentWidget(pt)
    pump(800)
    if pt._current_mode() != "manual":
        pt._manual_btn.click()
        pump(600)
    STATE["project"] = key
    STATE["run_dir"] = run.dir
    log(f"project {name}: measurement {meas}")


def apply(pt, defaults, overrides):
    data = dict(defaults)
    desc = overrides.get("_desc")
    data.update({k: v for k, v in overrides.items() if not k.startswith("_")})
    pt._m_apply_preset_data(data)
    if desc is not None:
        pt._m_desc_edit.setText(desc)
    pump(200)


def check_params(pt, expect):
    p = pt._collect_params()
    bad = {k: (getattr(p, k), v) for k, v in expect.items() if getattr(p, k) != v}
    return p, bad


def build(win, label, settings, project, overrides, expect, budget):
    pt = win._tab_profile
    open_project(win, project)
    GUARD.step(f"set {label}")
    defaults = STATE["defaults"]
    base = dict(defaults, quality="l")
    apply(pt, base, overrides)
    params, bad = check_params(pt, expect)
    rec = {"label": label, "project": project, "overrides": {k: v for k, v in overrides.items()},
           "params_mismatch": bad, "engine_on": bool(settings.get("profile_engine_beta")),
           "params": {k: getattr(params, k) for k in params.__dataclass_fields__
                      if k != "ti3_path"}}
    if bad:
        log(f"{label}: PARAMS MISMATCH {bad}")
    GUARD.step(f"build {label}", budget)
    built = {"done": False}

    def in_built(dlg):
        built["dialog"] = dlg.windowTitle()
        shot(dlg, f"{label}-dialog")
        if dlg.windowTitle() == "Profile Built":
            b = button(dlg, "Done")
            b.click() if b is not None else dlg.accept()
        else:
            from PyQt6.QtWidgets import QLabel
            built["dialog_text"] = " | ".join(
                w.text() for w in dlg.findChildren(QLabel) if w.text())[:1500]
            dlg.reject()
        built["done"] = True

    def watch():
        m = QApplication.activeModalWidget()
        if (isinstance(m, QDialog) and m.isVisible()
                and m.windowTitle() in ("Profile Built", "Profile Build Failed",
                                        "Multi-ink measurement")):
            in_built(m)
            return
        if not built["done"]:
            QTimer.singleShot(250, watch)

    QTimer.singleShot(250, watch)
    t0 = time.time()
    pt._on_build()
    wait_until(lambda: (time.time() - t0 > 3 and not pt._engine_builder.is_running
                        and not win._runner.is_running and pt._build_btn.isEnabled()
                        and (built["done"] or time.time() - t0 > 8)),
               budget - 30, f"build {label}")
    pump(1500)
    built["done"] = True
    text = pt._log.toPlainText()
    (LOGS / f"{label}.log").write_text(text)
    icc = Path(pt._icc_path) if getattr(pt, "_icc_path", None) else None
    rec.update({"seconds": round(time.time() - t0), "dialog": built.get("dialog"),
                "dialog_text": built.get("dialog_text"),
                "log_lines": len(text.splitlines()),
                "log_head": text.splitlines()[:6]})
    if icc and icc.exists() and icc.stat().st_mtime >= t0 - 1:
        keep = PROFILES / f"{label}.icc"
        shutil.copy2(icc, keep)
        rec["icc"] = str(keep)
        twin = icc.with_name(icc.stem + "-v4.icc")
        if twin.exists() and twin.stat().st_mtime >= t0 - 1:
            shutil.copy2(twin, PROFILES / f"{label}-v4.icc")
    else:
        rec["icc"] = None
    log(f"{label}: {rec['seconds']} s, dialog {rec['dialog']!r}, profile "
        f"{'kept' if rec['icc'] else 'NOT built'}")
    shot(win, f"{label}-window")
    RESULT["builds"].append(rec)
    write_result()
    pt._m_desc_edit.setText(STATE["desc_default"])
    return rec


def group_shots(win, prefix):
    pt = win._tab_profile
    scroll = getattr(pt, "_m_scroll", None)
    names = {"engine_rows": "_m_engine_rows_widget", "kgen": "_m_kgen_combo",
             "dark": "_m_dark_spin", "b2a": "_m_b2a_combo", "illum": "_m_illum_combo",
             "gamut": "_m_gam_mode_combo", "intents": "_m_perc_intent_combo",
             "curves": "_m_no_input_cb", "meta": "_m_mfr_edit", "zattr": "_m_z_surface_combo"}
    vis = {}
    for key, attr in names.items():
        w = getattr(pt, attr)
        vis[key] = bool(w.isVisibleTo(pt))
        if scroll is not None and vis[key]:
            try:
                scroll.ensureWidgetVisible(w, 0, 60)
            except RuntimeError:
                pass
            pump(300)
            shot(win, f"{prefix}-{key}")
    return vis


def main():
    app = build_app()
    from core.settings import AppSettings
    settings = AppSettings()
    for k, v in (("show_welcome_dialog", False), ("custom_output_path", str(PROJECTS)),
                 ("language", "en"), ("update_notify", False), ("calibration_mode", False)):
        settings.set(k, v)
    engine(settings, True)
    dog = PopupWatchdog(OUT, photograph=not ARGS.offscreen, policy="dismiss",
                        grace_s=2.0, log=log)
    dog.start()
    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(1500)
    try:
        app._chromiq_focus_give_back.give_back()
    except Exception:  # noqa: BLE001
        pass
    log(f"window up ({RESULT['mode']}); settings {os.environ['CHROMIQ_SETTINGS_FILE']}")
    parts = ARGS.parts.split(",")
    pt = win._tab_profile

    open_project(win, "rgb")
    STATE["defaults"] = pt._m_collect_preset_data()
    STATE["desc_default"] = pt._m_desc_edit.text()
    RESULT["manual_defaults"] = STATE["defaults"]
    log(f"Manual defaults: {STATE['defaults']}")

    if "A" in parts:
        GUARD.step("A: Manual tab, engine on, group by group")
        revisit_build_tab(win)
        RESULT["groups"]["engine_on"] = group_shots(win, "A0-engine-on")
        for label, proj, ov, exp in selected(ENGINE_ON):
            budget = 3600 if proj == "cmykog" else 1200
            build(win, label, settings, proj, ov, exp, budget)

    if "B" in parts:
        GUARD.step("B: engine off and on, stored values")
        open_project(win, "cmyk")
        odd = dict(STATE["defaults"], kgen_rule="x", dark_emphasis=2.0, b2a_enabled=True,
                   b2a_quality="n", illuminant="D65M2", no_input_shaper=True,
                   no_output_shaper=True, no_grid_pos=True, spectral_physics=True,
                   icc_version="4", noise_model=True, render_style="bijective")
        pt._m_apply_preset_data(odd)
        pump(300)
        before = pt._m_collect_preset_data()
        RESULT["toggle"]["set"] = before
        RESULT["toggle"]["engine_on_rows_visible"] = pt._m_engine_rows_widget.isVisibleTo(pt)
        RESULT["toggle"]["params_engine_on"] = {
            k: getattr(pt._collect_params(), k) for k in
            ("spectral_physics", "icc_version", "noise_model", "render_style", "k_rule",
             "dark_emphasis", "b2a_quality", "illuminant")}
        group_shots(win, "B1-engine-on-odd-values")
        engine(settings, False)
        revisit_build_tab(win)
        off = pt._m_collect_preset_data()
        RESULT["toggle"]["engine_off_rows_visible"] = pt._m_engine_rows_widget.isVisibleTo(pt)
        RESULT["toggle"]["changed_by_off"] = {k: (before[k], off[k]) for k in before
                                              if before[k] != off[k]}
        RESULT["toggle"]["params_engine_off"] = {
            k: getattr(pt._collect_params(), k) for k in
            ("spectral_physics", "icc_version", "noise_model", "render_style", "k_rule",
             "dark_emphasis", "b2a_quality", "illuminant")}
        RESULT["groups"]["engine_off"] = group_shots(win, "B2-engine-off")
        engine(settings, True)
        revisit_build_tab(win)
        again = pt._m_collect_preset_data()
        RESULT["toggle"]["engine_on_again_rows_visible"] = pt._m_engine_rows_widget.isVisibleTo(pt)
        RESULT["toggle"]["changed_after_round_trip"] = {k: (before[k], again[k]) for k in before
                                                        if before[k] != again[k]}
        group_shots(win, "B3-engine-on-again")
        pt._m_apply_preset_data(STATE["defaults"])
        log(f"toggle: {json.dumps(RESULT['toggle'], default=str)[:800]}")
        write_result()

    if "C" in parts:
        engine(settings, False)
        revisit_build_tab(win)
        for label, proj, ov, exp in selected(ENGINE_OFF):
            build(win, label, settings, proj, ov, exp, 1500)
        engine(settings, True)

    return finish(dog)


def finish(dog):
    GUARD.step("finish", 60)
    dog.stop()
    RESULT["popups"] = list(getattr(dog, "events", []))
    RESULT["unexpected_popups"] = len(dog.unexpected_events())
    write_result()
    log("done; result.json written; ending the process (no window can stay)")
    os._exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        import traceback
        RESULT["fatal"] = traceback.format_exc()
        write_result()
        log(f"FATAL {exc!r}")
        os._exit(2)
