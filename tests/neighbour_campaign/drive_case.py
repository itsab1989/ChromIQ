#!/usr/bin/env python3
"""(4b) ON SCREEN: one campaign case in the REAL app, engine in ``--replay``.

    # 1. the plan, from this tree (the emulator's expectations included)
    python -m tests.neighbour_campaign.plan i1-0200 laser_hp glitch
    # 2. the app: THIS tree (fix/4.3.3-beta3 at 6e9de104 or later merged in,
    #    native/chromiq-chartread included), or CHROMIQ_TREE=<another tree>
    .venv/bin/python tests/neighbour_campaign/drive_case.py \
        <case dir>/plan.json <out dir> [en|de]
    # 3. what the tab drew against what the emulator expected
    python -m tests.neighbour_campaign.plan --compare <out dir>

What it does, as CLAUDE.md asks of a driver: a real window on screen, the
settings, the log and the presets sandboxed inside <out dir> (asserted), the
QApplication built like the app's (``capture_screens.build_app``: C numeric
locale, focus handed back to the terminal, display kept awake for this
process only), a ``PopupWatchdog`` so an unscripted question never hangs it,
every photograph taken from the window's own buffer (``capture_window``,
nothing raised or activated), and never a real instrument:
``ARGYLL_EXCLUDE_SERIAL_SCAN`` is set and the engine only ever replays.

The chart's project is copied into the sandbox (its measurement absent, so a
fresh profiling read), the Measure tab started, and every step of the plan
read: ``goto`` the strip, ``swipe`` (with ``"as":"f<strip>"`` for a re-read,
which gives the strip's true colours). After every step it records which
patches the tab outlines red and yellow (``outlines.json``); at the plan's
moments it hovers a patch and photographs its card; every window that opens
is photographed and its text kept (``windows.json``), the window that closes
the measurement included.

It imports NOTHING from this harness: the app's own ``tests`` and
``workflow`` packages come from CHROMIQ_TREE, and the plan is plain JSON.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if sys.path and Path(sys.path[0]).resolve() == HERE:
    sys.path.pop(0)                 # never shadow anything with this folder

PLAN_PATH = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
LANG = sys.argv[3] if len(sys.argv) > 3 else "en"
PLAN = json.loads(PLAN_PATH.read_text())
APP = Path(os.environ.get("CHROMIQ_TREE") or HERE.parents[1])
os.environ["CHROMIQ_TREE"] = str(APP)

# ---- the sandbox, before anything of the app is imported --------------------
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "sandbox").mkdir(parents=True)
(OUT / "logs").mkdir()
os.environ["CHROMIQ_SETTINGS_FILE"] = str(OUT / "sandbox" / "settings.ini")
os.environ["CHROMIQ_LOG_DIR"] = str(OUT / "logs")
os.environ["ARGYLL_EXCLUDE_SERIAL_SCAN"] = "/dev/cu.Bluetooth-Incoming-Port"
os.environ["CHROMIQ_REPLAY"] = PLAN["replay"]
os.environ.pop("QT_QPA_PLATFORM", None)
(OUT / "plan.json").write_text(json.dumps(PLAN, indent=1))
sys.path.insert(0, str(APP / "scripts"))
os.chdir(APP)

from userdrive import Drive  # noqa: E402

d = Drive(OUT, language=LANG)
assert str(d.settings._s.fileName()).startswith(str(OUT)) if hasattr(
    d.settings, "_s") else True, "SETTINGS NOT SANDBOXED"
from onscreen_capture import PopupWatchdog  # noqa: E402

dog = PopupWatchdog(d.out, policy="dismiss", grace_s=120, photograph=True)
dog.start()
P = PLAN["project"]
shutil.copytree(PLAN["project_dir"], d.work / P)
for f in (d.work / P / "runs" / "run1").glob(f"{P}.ti3"):
    f.unlink()
if PLAN.get("kind") == "verification":
    # A VERIFICATION judged against the run's profile (Knut 5983470377: limit
    # 10, no strip test, no neighbour check, no misread summary): the run has
    # its measurement and its profile (the printer's run profile, older than
    # the print), and the chart as its verification chart, printed raw by
    # ChromIQ (the print record verify_expected reads).
    run = d.work / P / "runs" / "run1"
    shutil.copy2(PLAN["profiling_ti3"], run / f"{P}.ti3")
    shutil.copy2(PLAN["run_profile"], run / f"{P}.icc")
    old = time.time() - 3600
    os.utime(run / f"{P}.icc", (old, old))
    vd = run / "verifications"
    vd.mkdir(exist_ok=True)
    for ext in (".ti1", ".ti2", ".cht", ".ps", ".channels.json"):
        if (run / f"{P}{ext}").exists():
            shutil.copy2(run / f"{P}{ext}", vd / f"{P}-verify{ext}")
    # The chart's page images (the preview and the measurement need them).
    for tif in run.glob(f"{P}*.tif"):
        shutil.copy2(tif, vd / (f"{P}-verify" + tif.name[len(P):]))
    from datetime import datetime as _dt
    (vd / f"{P}-verify.print.json").write_text(json.dumps({
        "printed_at": _dt.now().isoformat(timespec="seconds"),
        "colour": "raw", "intent": "", "route": "chromiq",
        "source_profile": ""}, indent=2))
    meta = json.loads((run / "meta.json").read_text())
    meta["status"] = "complete"
    (run / "meta.json").write_text(json.dumps(meta, indent=2))

from PyQt6.QtCore import QPoint  # noqa: E402
from PyQt6.QtWidgets import QAbstractButton  # noqa: E402

state = {"n": 0, "handled": set(), "windows": [], "prefer": [], "steps": [],
         "closing": False}
DEFAULTS = ("Start Calibration", "Calibrate", "Kalibrieren", "Continue",
            "Weiter", "Go to", "Zum", "OK", "Close", "Schließen")


def buttons(m):
    return [b.text().replace("&", "") for b in m.findChildren(QAbstractButton)
            if b.isVisible() and b.text()]


def click(m, pick):
    d.later(lambda: next(b for b in m.findChildren(QAbstractButton)
                         if b.isVisible() and b.text().replace("&", "") == pick
                         ).click())
    d.note(f"   clicked {pick!r}")


def windows(secs):
    end = time.monotonic() + secs
    while time.monotonic() < end:
        m = d.modal()
        if m is None or not m.isVisible() or id(m) in state["handled"]:
            yield 300
            continue
        state["handled"].add(id(m))
        state["n"] += 1
        n = state["n"]
        title, text, btns = m.windowTitle(), d.modal_text(m), buttons(m)
        state["windows"].append({"title": title, "text": text, "buttons": btns,
                                 "after_step": len(state["steps"]),
                                 "closing": state["closing"]})
        d.note(f"[window {n}] {title!r} buttons={btns} :: {text!r}")
        d.shot(m, f"{n:02d}-window-{LANG}")
        pick = None
        for cand in tuple(state["prefer"]) + DEFAULTS:
            pick = next((b for b in btns if b.startswith(cand)), None)
            if pick:
                break
        if pick is None and btns:
            pick = btns[-1]
        if pick:
            click(m, pick)
        yield 1500


def tab():
    return d.win._tab_measure


def box_index():
    t = tab()
    out = {}
    for page, boxes in enumerate(t._patch_boxes):
        for loc, r in boxes.items():
            out[(page, r.x(), r.y(), r.width(), r.height())] = loc
    return out


def outlines():
    """``{"red": [...], "yellow": [...], "green": [...]}`` as the preview
    draws them now (green: a misread a re-read corrected, Knut 5984277558)."""
    from workflow.patch_flags import is_corrected
    idx = box_index()
    out = {"red": [], "yellow": [], "green": []}
    for page, items in tab()._preview._patch_overlay.items():
        for it in items:
            r, flag = it[0], it[3]
            loc = idx.get((page, r.x(), r.y(), r.width(), r.height()))
            if loc is None or flag is False or flag is None:
                continue
            key = ("red" if flag is True else "green" if is_corrected(flag)
                   else "yellow")
            out[key].append(loc)
    return {k: sorted(v) for k, v in out.items()}


def card(loc, name):
    t = tab()
    pv = t._preview
    page, box = t._locate_patch(loc)
    if page < 0:
        d.note(f"{loc}: no box")
        return
    if page != pv.current_page():
        pv.show_page(page)
        yield 900
    scale, ox, oy = pv._paint_geom
    sy = pv._paint_scale_y or scale
    c = box.center()
    lp = QPoint(int(c.x() * scale + ox), int(c.y() * sy + oy))
    pv._update_patch_tile(pv._img_label.mapTo(pv, lp))
    yield 700
    tile = pv._patch_tile
    rows = [r for _s, r in (tile._rows if tile is not None else [])]
    d.note(f"{name}: {loc} card:\n   " + "\n   ".join(rows))
    state.setdefault("cards", []).append({"name": name, "loc": loc, "rows": rows})
    d.shot(d.win, f"{name}-{LANG}")


def script(d):
    d.settings.set("chartread_engine", "chromiq")
    d.settings.set("pace_hint_enabled", False)
    d.settings.set("measure_show_overlay", True)
    d.settings.set("measure_patch_tile", True)
    d.settings.set("measure_progress_bar", True)
    d.settings.set("patch_neighbour_buffer_de", float(PLAN.get("buffer", 10.0)))
    d.open_project(P)
    yield 1500
    d.later(lambda: d.set_bar(run="run1", run_type=(
        "Verification" if PLAN.get("kind") == "verification" else "Profiling")))
    yield 2500
    d.goto_tab("measure")
    yield 2500
    t = tab()
    # Tick "Show patch values on hover" as a user does (the setting alone is
    # read only when the tab is built).
    for name in ("_g_patch_tile", "_m_patch_tile"):
        box = getattr(t, name, None)
        if box is not None and not box.isChecked():
            d.later(lambda b=box: b.setChecked(True))
    yield 600
    d.note(f"case {PLAN['case']} ({PLAN.get('kind')}); limit "
           f"{t._patch_warn_limit()} (plan {PLAN.get('limit')}); neighbour "
           f"check applies {t._neighbour_check_applies()}; fence "
           f"{t._use_outlier_fence()}; predicted {t._expected_is_predicted()}")
    d.later(t._start_btn.click)
    yield 1500
    t0 = time.monotonic()
    while time.monotonic() - t0 < 60 and not t._manager._session_strips:
        yield from windows(1)
    yield from windows(3)
    labels = [s["strip"] for s in t._manager._session_strips]
    d.note(f"session started; {len(labels)} strips (plan: "
           f"{len({s['strip'] for s in PLAN['steps']})}); now: limit "
           f"{t._patch_warn_limit()}, neighbour check "
           f"{t._neighbour_check_applies()}, fence {t._use_outlier_fence()}, "
           f"predicted {t._expected_is_predicted()}")
    photos = {}
    for ph in PLAN["photos"]:
        photos.setdefault(ph["after_step"], []).append(ph)
    last = len(PLAN["steps"]) - 1
    for k, step in enumerate(PLAN["steps"]):
        rt = step.get("read_twice")
        state["prefer"] = (["Re-read", "Erneut"] if rt and rt["choice"] == "reread"
                           else ["Keep", "Behalten"] if rt else [])
        mgr = t._manager
        mgr.goto_strip(step["strip"])
        yield 700
        cmd = {"cmd": "swipe"}
        if step.get("as"):
            cmd["as"] = step["as"]
        mgr.send_command(cmd)
        if k == last:
            # The window this last strip opens closes the measurement.
            state["closing"] = True
        yield from windows(1.5 if k < last else 2.5)
        o = outlines()
        state["steps"].append({"strip": step["strip"], "as": step.get("as"), **o})
        d.note(f"step {k} {step['strip']}{' again' if step.get('as') else ''}: "
               f"red {o['red']} yellow {o['yellow']} green {o['green']}")
        for ph in photos.get(k, []):
            yield from card(ph["loc"], f"{k:03d}-{ph['name']}")
    summary = t.neighbour_summary_facts()
    misread = t._misread_summary()
    d.note(f"summary facts {summary}")
    d.note(f"misread summary: {misread!r}")
    yield from windows(25)
    (OUT / "outlines.json").write_text(json.dumps(
        {"steps": state["steps"], "summary": summary, "lang": LANG,
         "misread_summary": misread,
         "cards": state.get("cards", [])}, indent=1, ensure_ascii=False))
    (OUT / "windows.json").write_text(json.dumps(state["windows"], indent=1,
                                                 ensure_ascii=False))
    yield 2000
    d.shot(d.win, f"zz-final-{LANG}")


rc = d.run(script)
dog.stop()
d.note(f"watchdog events: {[(e.get('title'), e.get('unexpected')) for e in dog.events]}")
sys.exit(rc)
