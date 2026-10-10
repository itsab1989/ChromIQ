#!/usr/bin/env python3
"""Beta 17, Knut's test plan (#182 6084756743), ON SCREEN in the real app.

    CHROMIQ_SETTINGS_FILE=<report>/run/driver.ini \\
    CHROMIQ_PRESETS_DIR=<report>/run/presets \\
    ARGYLL_EXCLUDE_SERIAL_SCAN=/dev/cu.Bluetooth-Incoming-Port \\
        python scripts/drive_b17_misread_protocol.py <demo-project> <report>

*"Make sure to test measurement of all types of charts and change all limit
values for each chart type up and down in preferences -> measurement and
verify that misreads are registered, and patch highlighting works for all
transitions of colors, Red, to yellow to green for all relevant tests
separately. Run tests on-screen on real app using demo data created to
trigger on all measurement misread error types on all types of charts."*

WHAT IS REAL AND WHAT IS NOT. The window, the Measure tab, the charts (laid
out by ChromIQ's engine, ``scripts/make_misread_demo.py``), the preview, the
outlines, the hover cards, Preferences ▸ Measurement and its OK, and every
photograph are the app's own. The INSTRUMENT is the one thing simulated, at
the seam the reading engine itself uses: the driver emits ``MeasureManager``'s
``session_map``, ``strip_measured`` and ``patch_measured`` signals with the
demo's readings, as the engine does when an instrument reports. A
verification's prediction is handed to the tab as its ``LiveExpected`` (the
demo's prediction is the chart's own expected colours). No instrument is
opened; nothing is written outside the report folder.

Every case is judged twice: what the app SHOWS (the outlines read off the
preview) against what Knut's rules EXPECT, worked out by this script's own
implementation of them (``make_misread_demo.four_steps``, the Tukey fence,
the limit), never by calling the app's judging code.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

KINDS = ["estimated", "accurate", "verification", "verification_fpg",
         "calibration"]
KIND_TITLE = {
    "estimated": "Profiling chart with estimated colours",
    "accurate": "Profiling chart made with a pre-conditioning profile",
    "verification": "Verification chart, through the profile",
    "verification_fpg": "Verification chart, From Profile Gamut",
    "calibration": "Calibration chart",
}
SETTING_KIND = {"estimated": "estimated", "accurate": "accurate",
                "verification": "verification",
                "verification_fpg": "verification",
                "calibration": "calibration"}

ROWS: list = []          # the protocol
LOG: list = []


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    LOG.append(line)


def pump(app, ms: int = 200) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


# ---- the rules, written apart from the app ----------------------------------
def tukey(des):
    if len(des) < 4:
        return 0.0
    s = sorted(des)

    def pct(p):
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return s[f] + (s[c] - s[f]) * (k - f)
    q1, q3 = pct(0.25), pct(0.75)
    return q3 + 1.5 * (q3 - q1)


class Oracle:
    """What Knut's rules say must be outlined, from the readings alone."""

    def __init__(self, sc: dict):
        from make_misread_demo import lab
        self.sc = sc
        self.exp_lab = {k: lab(v["exyz"]) for k, v in sc["patches"].items()}
        self.lab = lab

    def outlined(self, readings: dict, *, pel, strip_on, nb_on, nl, nr,
                 fence_mode: str) -> set:
        """*fence_mode*: "strip" (judged strip by strip, the fence of the
        strip as read), "none" (patch by patch: no strip to compare with)."""
        from make_misread_demo import four_steps
        from workflow.measurement_report import engine_patch_de
        de = {loc: engine_patch_de(self.sc["patches"][loc]["exyz"], x)
              for loc, x in readings.items()}
        fence = {}
        if strip_on and fence_mode == "strip":
            for letter, locs in self.sc["strip_locs"].items():
                f = tukey([de[x] for x in locs if x in de])
                for x in locs:
                    fence[x] = f
        out = set()
        meas = {loc: self.lab(x) for loc, x in readings.items()}
        order = {loc: i for i, loc in enumerate(readings)}
        # Every threshold at one decimal, above it to be flagged (Knut,
        # #182 6094941512), as the app compares them.
        from workflow.misread_settings import above
        for loc in readings:
            fe = fence.get(loc, 0.0)
            if above(de[loc], pel) and (fe <= 0.0 or above(de[loc], fe)):
                out.add(loc)
            elif nb_on:
                n, fu = four_steps(loc, self.exp_lab, meas, radius=nr,
                                   order=order)
                if fu is not None and above(fu, nl):
                    out.add(loc)
        return out


# ---- the app ---------------------------------------------------------------
class Driver:
    def __init__(self, demo: Path, report: Path):
        assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
        assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
        assert not os.environ.get("QT_QPA_PLATFORM"), "this driver opens windows"
        self.report = report
        self.shots = report / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.work = report / "work"
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        self.project = self.work / demo.name
        shutil.copytree(demo, self.project)
        from capture_screens import build_app
        self.app = build_app()
        from core.settings import AppSettings
        s = self.settings = AppSettings()
        s.set("custom_output_path", str(self.work))
        for k, v in (("appearance", "light"), ("language", "en"),
                     ("show_welcome", False), ("update_notify", False),
                     ("sound_enabled", False), ("chartread_engine", "chromiq"),
                     ("restore_last_session", False)):
            s.set(k, v)
        assert s.get("custom_output_path", "") == str(self.work)
        from onscreen_capture import PopupWatchdog
        self.dog = PopupWatchdog(report, photograph=True)
        self.dog.start()
        from ui.main_window import MainWindow
        from ui.theme import apply_appearance
        apply_appearance(self.app, None, "light")
        self.win = MainWindow(s)
        self.win.resize(1500, 1060)
        self.win.show()
        pump(self.app, 2500)
        give = getattr(self.app, "_chromiq_focus_give_back", None)
        if give is not None:
            give.give_back()
        self.mt = self.win._tab_measure
        self.win._tabs.setCurrentWidget(self.mt)
        pump(self.app, 800)
        self.mt._switch_mode("manual")
        pump(self.app, 400)
        self.views_on()
        pump(self.app, 400)
        self.n_shot = 0

    def views_on(self):
        """The overlay from the measurement on disk, and the patch values
        on hover: the two boxes of the Measure tab, ticked as a user does."""
        self.settings.set("measure_show_overlay", True)
        self.mt._m_overlay_cb.setChecked(True)
        self.mt._m_patch_tile.setChecked(True)
        self.mt._apply_active_view_settings()

    # -- chart and readings ---------------------------------------------------
    def load(self, kind: str):
        scs = [json.loads(p.read_text(encoding="utf-8"))
               for p in self.project.rglob("*.misreads.json")]
        sc = next(x for x in scs if x["kind"] == kind)
        ti2 = self.project / sc["chart_rel"]
        for suffix in (".ti3", ".confirmed.json"):
            p = ti2.with_suffix(suffix)
            if p.exists():
                p.unlink()
        mt = self.mt
        mt._session_live = False
        mt.set_ti1_path(ti2)
        pump(self.app, 1500)
        self.views_on()
        self.kind, self.sc, self.ti2 = kind, sc, ti2
        self.oracle = Oracle(sc)
        from workflow import verify_expected as ve
        if kind.startswith("verification"):
            pred = {loc: tuple(v["exyz"]) for loc, v in sc["patches"].items()}
            le = ve.LiveExpected(ve.SOURCE_PREDICTION, "demo prediction", pred)
            mt._expected_source_for = lambda ti3, le=le: le
            self.le = le
        else:
            mt.__dict__.pop("_expected_source_for", None)
            self.le = None
        mt._live_expected = self.le
        mt._warn_kind_cache = None
        mt._reset_flag_judge()
        mt._preview.clear_patch_overlay()
        assert mt._chart_kind() == SETTING_KIND[kind], (mt._chart_kind(), kind)
        return sc

    def event(self, loc: str, xyz) -> dict:
        from workflow.measurement_report import engine_patch_de
        p = self.sc["patches"][loc]
        return {"id": p["sid"], "loc": loc, "exyz": list(p["exyz"]),
                "xyz": list(xyz), "de": round(engine_patch_de(p["exyz"], xyz), 2)}

    def start(self, pbp: bool):
        mt = self.mt
        mt._spot_session = pbp
        mt._session_resumes = False
        mt._session_live = True
        mt._live_expected = self.le
        mt._reset_flag_judge()
        smap = [{"strip": s, "read": False, "verifiable": True}
                for s in self.sc["strips"]]
        mt._manager.session_map.emit(smap)
        pump(self.app, 600)
        self.readings: dict = {}

    def read_all(self, readings: dict, pbp: bool):
        for letter in self.sc["strips"]:
            locs = self.sc["strip_locs"][letter]
            if pbp:
                for loc in locs:
                    self.mt._manager.patch_measured.emit(
                        self.event(loc, readings[loc]))
                    self.readings[loc] = readings[loc]
                pump(self.app, 40)
            else:
                self.mt._manager.strip_measured.emit(
                    {"strip": letter,
                     "patches": [self.event(x, readings[x]) for x in locs]})
                for x in locs:
                    self.readings[x] = readings[x]
                pump(self.app, 60)
        pump(self.app, 600)

    def reread(self, loc: str, xyz, pbp: bool, strip_readings=None):
        """Read *loc* again: patch by patch the patch alone; reading strips
        its whole strip (each other patch with its last reading, or
        *strip_readings*)."""
        if pbp:
            self.mt._manager.patch_measured.emit(self.event(loc, xyz))
            self.readings[loc] = xyz
        else:
            letter = "".join(c for c in loc if c.isalpha())
            locs = self.sc["strip_locs"][letter]
            new = dict(strip_readings or {})
            new[loc] = xyz
            pats = []
            for x in locs:
                r = new.get(x, self.readings[x])
                self.readings[x] = r
                pats.append(self.event(x, r))
            self.mt._manager.strip_measured.emit({"strip": letter,
                                                  "patches": pats})
        pump(self.app, 700)

    def end(self):
        """The session ends: its readings are the measurement on disk."""
        from make_misread_demo import write_ti3
        patches = [{"sid": v["sid"], "loc": k, "rgb": v["rgb"]}
                   for k, v in self.sc["patches"].items()
                   if k in self.readings]
        write_ti3(self.ti2.with_suffix(".ti3"), patches, self.readings)
        self.mt._session_live = False
        pump(self.app, 300)

    def on_disk(self, readings: dict):
        """A measurement already on disk, read once (no re-reads, no
        memory), painted by the tab from the file."""
        from make_misread_demo import write_ti3
        cj = self.ti2.with_suffix(".confirmed.json")
        if cj.exists():
            cj.unlink()
        patches = [{"sid": v["sid"], "loc": k, "rgb": v["rgb"]}
                   for k, v in self.sc["patches"].items()]
        write_ti3(self.ti2.with_suffix(".ti3"), patches, readings)
        self.readings = dict(readings)
        self.mt._session_live = False
        self.views_on()
        self.mt._reset_flag_judge()
        self.mt._preview.clear_patch_overlay()
        self.mt.refresh_patch_flags()
        pump(self.app, 1200)

    # -- what the app shows -----------------------------------------------------
    def flags(self) -> dict:
        mt = self.mt
        by_box = {(b.x(), b.y(), b.width()): loc
                  for loc, b in mt._patch_boxes[0].items()}
        out = {}
        for it in mt._preview._patch_overlay.get(0, []):
            b = it[0]
            loc = by_box.get((b.x(), b.y(), b.width()))
            if loc:
                out[loc] = it[3]
        return out

    @staticmethod
    def word(f) -> str:
        from workflow import patch_flags as pf
        if f is pf.FLAG_RED or f is True:
            return "red"
        if f == pf.FLAG_CONFIRMED:
            return "yellow (re-read)"
        if f == pf.FLAG_LEARNED:
            return "yellow (learned)"
        if f == pf.FLAG_CORRECTED:
            return "green"
        return "none"

    def outlined(self) -> set:
        return {loc for loc, f in self.flags().items()
                if self.word(f) != "none"}

    # -- Preferences ▸ Measurement, the real dialog, OK ---------------------------
    def prefs(self, changes: dict, shot: str) -> str:
        """Open Preferences through the app's own menu path, set *changes*
        (setting key -> value) in the misread table, photograph it, press
        OK. The app then judges the outlines again (MainWindow._open_settings
        -> TabMeasure.refresh_patch_flags)."""
        from PyQt6.QtWidgets import QDialog, QPushButton
        from ui.dialogs.settings_dialog import SettingsDialog
        from workflow import misread_settings as MS
        drv = self
        photo = {"path": ""}

        def scripted_exec(dlg):
            dlg.show()
            tabs = dlg._tabs
            i = next(i for i in range(tabs.count())
                     if tabs.widget(i).isAncestorOf(dlg._misread_table))
            tabs.setCurrentIndex(i)
            pump(drv.app, 500)
            page = tabs.widget(i)
            y = dlg._misread_table.mapTo(page.widget(), dlg._misread_table
                                         .rect().topLeft()).y()
            page.verticalScrollBar().setValue(max(0, y - 120))
            for key, value in changes.items():
                w = None
                for k in MS.KINDS:
                    if key == MS.PATCH_ERROR_LIMIT_KEYS[k]:
                        w = dlg._patch_limit_spins[k]
                    elif key == MS.STRIP_TEST_KEYS[k]:
                        w = dlg._strip_test_checks[k]
                    elif key == MS.NEIGHBOUR_LIMIT_KEYS[k]:
                        w = dlg._neighbour_limit_spins[k]
                    elif key == MS.NEIGHBOUR_RADIUS_KEYS[k]:
                        w = dlg._neighbour_radius_spins[k]
                if key == MS.SAME_READING_KEY:
                    w = dlg._same_reading_spin
                if key == MS.NEIGHBOUR_CHECK_KEY:
                    w = dlg._patch_neighbour_check
                assert w is not None, key
                if isinstance(value, bool):
                    w.setChecked(value)
                else:
                    w.setValue(float(value))
            pump(drv.app, 600)
            photo["path"] = drv.photo(dlg, shot)
            ok = next(b for b in dlg.findChildren(QPushButton)
                      if b.text().replace("&", "").strip().upper() == "OK")
            ok.click()
            pump(drv.app, 300)
            return int(QDialog.DialogCode.Accepted.value)

        real = SettingsDialog.exec
        SettingsDialog.exec = scripted_exec
        try:
            self.win._open_settings()
        finally:
            SettingsDialog.exec = real
        pump(self.app, 1500)
        return photo["path"]

    # -- photographs ----------------------------------------------------------------
    def photo(self, widget, name: str) -> str:
        from onscreen_capture import capture_window
        self.n_shot += 1
        path = self.shots / f"{self.n_shot:03d}_{name}.png"
        ok, why = capture_window(widget, path)
        if not ok:
            log(f"PHOTO FAILED {path.name}: {why}")
            return f"(not taken: {why})"
        return str(path.relative_to(self.report))

    def card(self, loc: str, name: str) -> str:
        """Point at *loc* in the preview, as a hover does, and photograph
        the window with the card open."""
        from PyQt6.QtCore import QPoint
        pv = self.mt._preview
        rect = self.mt._patch_boxes[0][loc]
        geom = pv._paint_geom
        if geom is None:
            return "(no preview geometry)"
        scale, ox, oy = geom
        sy = pv._paint_scale_y or scale
        lp = QPoint(int(rect.center().x() * scale + ox),
                    int(rect.center().y() * sy + oy))
        pos = pv._img_label.mapTo(pv, lp)
        pv._update_patch_tile(pos)
        pump(self.app, 500)
        shot = self.photo(self.win, name)
        pv._hide_patch_tile()
        return shot

    def card_text(self, loc: str) -> str:
        tile = self.mt._preview._patch_tile
        if tile is None:
            return ""
        return " / ".join(t for _s, t in tile._rows if t)

    # -- the protocol ------------------------------------------------------------------
    def row(self, case: str, mode: str, action: str, expected: str, seen: str,
            ok: bool, shots: "list[str]") -> None:
        ROWS.append({"kind": self.kind, "case": case, "mode": mode,
                     "action": action, "expected": expected, "seen": seen,
                     "pass": bool(ok), "shots": shots})
        log(f"{'PASS' if ok else 'FAIL'} {self.kind} {mode} {case}: {seen}")


def fmt_set(s) -> str:
    s = sorted(s)
    return "{" + ", ".join(s[:12]) + ("…" if len(s) > 12 else "") + "}" \
        + f" ({len(s)})"


# ---- the cases -----------------------------------------------------------------
def defaults(kind):
    from workflow import misread_settings as MS
    k = SETTING_KIND[kind]
    return dict(pel=MS.PATCH_ERROR_LIMIT_DEFAULTS[k],
                strip_on=MS.STRIP_TEST_DEFAULTS[k], nb_on=True,
                nl=MS.NEIGHBOUR_LIMIT_DEFAULTS[k],
                nr=MS.NEIGHBOUR_RADIUS_DEFAULTS[k])


def all_defaults() -> dict:
    from workflow import misread_settings as MS
    out = {}
    for k in MS.KINDS:
        out[MS.PATCH_ERROR_LIMIT_KEYS[k]] = MS.PATCH_ERROR_LIMIT_DEFAULTS[k]
        out[MS.STRIP_TEST_KEYS[k]] = MS.STRIP_TEST_DEFAULTS[k]
        out[MS.NEIGHBOUR_LIMIT_KEYS[k]] = MS.NEIGHBOUR_LIMIT_DEFAULTS[k]
        out[MS.NEIGHBOUR_RADIUS_KEYS[k]] = MS.NEIGHBOUR_RADIUS_DEFAULTS[k]
    out[MS.SAME_READING_KEY] = MS.SAME_READING_DEFAULT
    out[MS.NEIGHBOUR_CHECK_KEY] = True
    return out


def live_transitions(d: Driver, kind: str, pbp: bool) -> None:
    """Every test at its default: the first read, then the re-reads that take
    a patch red -> yellow -> green and back to red."""
    mode = "patch by patch" if pbp else "strips"
    tag = f"{kind}_{'pbp' if pbp else 'strip'}"
    sc = d.sc
    plan, rr = sc["plan"], sc["rereads"]
    p = defaults(kind)
    d.prefs(all_defaults(), f"{tag}_prefs_defaults")
    d.start(pbp)
    d.read_all(sc["first"], pbp)
    want = d.oracle.outlined(d.readings, **p,
                             fence_mode="none" if pbp else "strip")
    seen = d.outlined()
    shot = d.photo(d.win, f"{tag}_first_read")
    d.row("first read, defaults", mode, "every strip read once (misreads: "
          + ", ".join(f"{k} {plan[k]}" for k in
                      ("gross", "small", "small2", "small3", "gamut")) + ")",
          "outlined " + fmt_set(want), "outlined " + fmt_set(seen),
          seen == want, [shot])
    for name, loc in (("small", plan["small"]), ("gross", plan["gross"]),
                      ("gamut", plan["gamut"])):
        c = d.card(loc, f"{tag}_card_{name}_{loc}")
        f = d.word(d.flags().get(loc))
        d.row(f"card, {name} {loc}", mode, f"hover {loc}",
              "red, its card says why",
              f"{f}", f == "red", [c])

    def step(case, loc, xyz, expect, test):
        d.reread(loc, xyz, pbp)
        f = d.word(d.flags().get(loc))
        c = d.card(loc, f"{tag}_{case.replace(' ', '_')}_{loc}")
        d.row(case, mode, f"{loc} read again", f"{loc} {expect} ({test})",
              f"{loc} {f}", f == expect, [c])

    step("neighbour red to yellow", plan["small"], rr["small_same_jitter"],
         "yellow (re-read)", "neighbour check, its own re-read the same")
    step("neighbour red to green", plan["small3"], rr["small3_good"],
         "green", "neighbour check, re-read that fits")
    step("neighbour green to red", plan["small3"], rr["small3_bad_again"],
         "red", "neighbour check, a misread again")
    step("tolerance 3: 3.6 apart stays red", plan["small2"], rr["small2_3_6"],
         "red", "same-reading tolerance 3")
    step("limit red to green", plan["gross"], rr["gross_good"], "green",
         "patch error limit, re-read that fits")
    step("gamut red to yellow", plan["gamut"], rr["gamut_same"],
         "yellow (re-read)", "the same reading twice")
    d.end()
    # the same-reading tolerance at 5: the 3.6 re-read is the same colour
    from workflow import misread_settings as MS
    d.prefs({MS.SAME_READING_KEY: 5.0}, f"{tag}_prefs_tolerance_5")
    d.start(pbp)
    d.read_all(sc["first"], pbp)
    step("tolerance 5: 3.6 apart turns yellow", plan["small2"],
         rr["small2_3_6"], "yellow (re-read)", "same-reading tolerance 5")
    d.end()
    d.prefs({MS.SAME_READING_KEY: 3.0}, f"{tag}_prefs_tolerance_back_3")


def threshold_sweeps(d: Driver, kind: str) -> None:
    """Every threshold of this chart type up and down in Preferences, on the
    measurement on disk; after each OK the app judges the outlines again."""
    from workflow import misread_settings as MS
    k = SETTING_KIND[kind]
    tag = f"{kind}_disk"
    sc = d.sc
    plan, facts = sc["plan"], sc["facts"]
    p = defaults(kind)
    d.prefs(all_defaults(), f"{tag}_prefs_defaults")
    d.on_disk(sc["first"])

    def check(case, changes, params, focus):
        shot_p = d.prefs(changes, f"{tag}_{case}_prefs") if changes else ""
        want = d.oracle.outlined(d.readings, **params, fence_mode="strip")
        seen = d.outlined()
        shot = d.photo(d.win, f"{tag}_{case}")
        f = {x: ("outlined" if x in seen else "not outlined") for x in focus}
        d.row(case.replace("_", " "), "measurement on disk",
              ", ".join(f"{kk} = {vv}" for kk, vv in changes.items())
              or "as measured",
              "outlined " + fmt_set(want) + "; "
              + ", ".join(f"{x} {'outlined' if x in want else 'not outlined'}"
                          for x in focus),
              "outlined " + fmt_set(seen) + "; "
              + ", ".join(f"{x} {v}" for x, v in f.items()),
              seen == want, [s for s in (shot_p, shot) if s])

    focus = [plan["small"], plan["small2"], plan["gamut"], plan["gross"]]
    check("defaults", {}, p, focus)
    # Patch error limit, neighbour check off so the limit is seen alone
    lim_p = dict(p, nb_on=False)
    d.prefs({MS.NEIGHBOUR_CHECK_KEY: False}, f"{tag}_prefs_neighbour_off")
    check("patch error limit default, neighbour check off", {}, lim_p, focus)
    g_de, s_de = facts["gamut"]["de"], facts["small"]["de"]
    down = round(min(g_de, s_de) - 2.0, 1)
    if down >= p["pel"]:
        down = round(p["pel"] - 1.0, 1)
    check("patch error limit down", {MS.PATCH_ERROR_LIMIT_KEYS[k]: down},
          dict(lim_p, pel=down), focus)
    up = round(max(g_de, s_de, p["pel"]) + 3.0, 1)
    check("patch error limit up", {MS.PATCH_ERROR_LIMIT_KEYS[k]: up},
          dict(lim_p, pel=up), focus)
    d.prefs({MS.PATCH_ERROR_LIMIT_KEYS[k]: p["pel"],
             MS.NEIGHBOUR_CHECK_KEY: True}, f"{tag}_prefs_back")
    # Neighbour limit
    sm = max(facts[x]["further"] for x in ("small", "small2", "small3"))
    nl_up = round(sm + 1.0, 1)
    check("neighbour limit up", {MS.NEIGHBOUR_LIMIT_KEYS[k]: nl_up},
          dict(p, nl=nl_up), focus)
    nl_down = round(max(0.5, p["nl"] / 2), 1)
    check("neighbour limit down", {MS.NEIGHBOUR_LIMIT_KEYS[k]: nl_down},
          dict(p, nl=nl_down), focus)
    d.prefs({MS.NEIGHBOUR_LIMIT_KEYS[k]: p["nl"]}, f"{tag}_prefs_nl_back")
    # Colour-neighbour radius
    check("colour-neighbour radius down", {MS.NEIGHBOUR_RADIUS_KEYS[k]: 2.0},
          dict(p, nr=2.0), focus)
    check("colour-neighbour radius up", {MS.NEIGHBOUR_RADIUS_KEYS[k]: 60.0},
          dict(p, nr=60.0), focus)
    d.prefs({MS.NEIGHBOUR_RADIUS_KEYS[k]: p["nr"]}, f"{tag}_prefs_nr_back")
    # The strip test, on the strip measurement, neighbour check off and the
    # limit under the strip's offset
    d.on_disk(sc["strip_set"])
    off_de = 30.0 if kind in ("estimated", "calibration") else None
    pel_s = 25.0 if off_de else p["pel"]
    t_locs = sc["strip_locs"][plan["strip_offset"]]
    sfocus = [t_locs[1], plan["partial_locs"][0],
              sc["strip_locs"][plan["out_of_step"]][2],
              sc["strip_locs"][plan["wrong_strip"]][2]]
    d.prefs({MS.NEIGHBOUR_CHECK_KEY: False,
             MS.PATCH_ERROR_LIMIT_KEYS[k]: pel_s},
            f"{tag}_prefs_strip_case")
    sp = dict(p, nb_on=False, pel=pel_s)
    check("strip test on", {MS.STRIP_TEST_KEYS[k]: True},
          dict(sp, strip_on=True), sfocus)
    check("strip test off", {MS.STRIP_TEST_KEYS[k]: False},
          dict(sp, strip_on=False), sfocus)
    # every misread type with every test at its default
    d.prefs(all_defaults(), f"{tag}_prefs_defaults_again")
    check("every strip misread, defaults", {}, p, sfocus)
    d.prefs(all_defaults(), f"{tag}_prefs_end")


def strip_test_transitions(d: Driver, kind: str) -> None:
    """The strip test alone: neighbour check off, strip test off, limit
    under the offset; the offset strip red, a re-read of it that fits makes
    it green; the partial strip read again the same makes it yellow."""
    from workflow import misread_settings as MS
    k = SETTING_KIND[kind]
    tag = f"{kind}_striptest"
    sc = d.sc
    plan, rr = sc["plan"], sc["rereads"]
    pel_s = 25.0 if kind in ("estimated", "calibration") else \
        MS.PATCH_ERROR_LIMIT_DEFAULTS[k]
    d.prefs({MS.NEIGHBOUR_CHECK_KEY: False, MS.STRIP_TEST_KEYS[k]: False,
             MS.PATCH_ERROR_LIMIT_KEYS[k]: pel_s}, f"{tag}_prefs")
    d.start(False)
    d.read_all(sc["strip_set"], False)
    t = plan["strip_offset"]
    planned = {v for v in plan.values() if isinstance(v, str)}
    # a patch of the offset strip that no other misread uses (the strip may
    # hold the demo's real gamut limit, which no re-read can make green)
    loc = next(x for x in sc["strip_locs"][t][1:] if x not in planned)
    f0 = d.word(d.flags().get(loc))
    s0 = d.photo(d.win, f"{tag}_strip_{t}_read_off")
    d.row("strip test off: an offset strip", "strips",
          f"strip {t} read off together (limit {pel_s})",
          f"{loc} outlined: red, or yellow where a patch of another strip "
          "expected nearly the same colour is off the same way (similar "
          "patches, 10.3a)", f"{loc} {f0}", f0 in ("red", "yellow (re-read)"),
          [s0])
    # the partial strip, read again the same
    pp = plan["partial"]
    ploc = plan["partial_locs"][0]
    same = {x: d.readings[x] for x in sc["strip_locs"][pp]}
    d.reread(ploc, d.readings[ploc], False, strip_readings=same)
    f1 = d.word(d.flags().get(ploc))
    c1 = d.card(ploc, f"{tag}_partial_{pp}_reread_same_{ploc}")
    d.row("strip test: red to yellow", "strips",
          f"strip {pp} read again, the same", f"{ploc} yellow (re-read)",
          f"{ploc} {f1}", f1 == "yellow (re-read)", [c1])
    # the offset strip read again, correctly
    clean = {x: sc["clean"][x] for x in sc["strip_locs"][t]}
    d.reread(loc, clean[loc], False, strip_readings=clean)
    f2 = d.word(d.flags().get(loc))
    c2 = d.card(loc, f"{tag}_offset_{t}_reread_good_{loc}")
    d.row("strip test: red to green", "strips",
          f"strip {t} read again, correctly", f"{loc} green",
          f"{loc} {f2}", f2 == "green", [c2])
    d.end()
    d.prefs(all_defaults(), f"{tag}_prefs_back")


def write_protocol(report: Path) -> None:
    (report / "protocol.json").write_text(json.dumps(ROWS, indent=1),
                                          encoding="utf-8")
    n_ok = sum(1 for r in ROWS if r["pass"])
    lines = ["# Beta 17, Knut's test plan (#182 6084756743): on-screen protocol",
             "",
             f"{len(ROWS)} cases, {n_ok} as expected, {len(ROWS) - n_ok} not.",
             "",
             "Real app, real windows (light mode, English), the instrument "
             "simulated at the reading engine's own signals; expected values "
             "from this driver's own implementation of the rules. Screenshots "
             "in `shots/`.", ""]
    for kind in KINDS:
        rows = [r for r in ROWS if r["kind"] == kind]
        if not rows:
            continue
        lines += [f"## {KIND_TITLE[kind]}", "",
                  "| # | case | read | action | expected | seen | ok | screenshot |",
                  "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rows, 1):
            shots = " ".join(f"[{Path(s).name}]({s})" for s in r["shots"]
                             if s and not s.startswith("("))
            lines.append(f"| {i} | {r['case']} | {r['mode']} | {r['action']} | "
                         f"{r['expected']} | {r['seen']} | "
                         f"{'yes' if r['pass'] else '**NO**'} | {shots} |")
        lines.append("")
    (report / "PROTOCOL.md").write_text("\n".join(lines), encoding="utf-8")
    (report / "driver.log").write_text("\n".join(LOG), encoding="utf-8")


def main() -> int:
    demo, report = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else KINDS
    d = Driver(demo, report)
    try:
        for kind in only:
            d.load(kind)
            log(f"=== {kind}: {d.ti2}")
            live_transitions(d, kind, pbp=False)
            d.load(kind)
            live_transitions(d, kind, pbp=True)
            d.load(kind)
            threshold_sweeps(d, kind)
            d.load(kind)
            strip_test_transitions(d, kind)
            write_protocol(report)
    finally:
        write_protocol(report)
        d.dog.stop()
        ev = d.dog.unexpected_events() if hasattr(d.dog, "unexpected_events") \
            else []
        log(f"popups: {ev}")
        (report / "driver.log").write_text("\n".join(LOG), encoding="utf-8")
        d.win.close()
        pump(d.app, 400)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
