#!/usr/bin/env python3
"""Knut's run 6 replayed ON SCREEN in the real app (#182, 4.3.5 beta 8).

    CHROMIQ_SETTINGS_FILE=<report>/run/driver.ini \\
    CHROMIQ_PRESETS_DIR=<report>/run/presets \\
        python scripts/drive_b8_run6_similar_patches.py <run6 folder> \\
            <fixture json> <report> <tag>

Knut, #182 6196599132, approving the similar-patch rule for both tests:
*"In run 6 it turns C18, E27, F27 and F2 yellow by similar patches and C27
and E22 yellow through their range ...; I27 and I11 stay red (same strip)."*
This driver shows it in the window, and is run once on the tree before the
change (tag "before") and once after (tag "after"), so the two sets of
photographs are of the same readings.

WHAT IS REAL AND WHAT IS NOT. The window, the Measure tab, Knut's own
verification chart (a copy of his run 6 folder in the report), the preview,
its outlines and the hover cards are the app's own; every picture is the
window photographed by its id (``onscreen_capture.capture_window``). The
INSTRUMENT is simulated at the seam the reading engine uses: the driver
emits ``MeasureManager``'s ``session_map`` and ``strip_measured`` signals
with the strips Knut's log recorded (``tests/data/knut_run6``), in his order
(strip A, strip A again, B to L). The expected colours are his run profile's
prediction, as ``verify_expected`` works them out (saved in the fixture),
handed to the tab as its ``LiveExpected``. The card is opened by the
preview's own hover code at the patch's centre (no mouse events, so
Basti's keyboard and pointer are never taken). No instrument is opened,
nothing is printed, nothing is written outside the report folder.

Settings, sandboxed: Knut's of the log, patch error limit 15, neighbour
limit 7 (and a second pass at 5, the value of his I27 / I11 pictures),
colour-neighbour radius 30, same-reading tolerance 3, strip test off.
"""
from __future__ import annotations

import json
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

FOCUS = ["C18", "E27", "F27", "F2", "C27", "E22", "I27", "I11"]
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


class Driver:
    def __init__(self, run6: Path, fixture: Path, report: Path, tag: str):
        assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
        assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
        assert not os.environ.get("QT_QPA_PLATFORM"), "this driver opens windows"
        self.tag = tag
        self.data = json.loads(fixture.read_text(encoding="utf-8"))
        self.shots = report / "shots" / tag
        self.shots.mkdir(parents=True, exist_ok=True)
        self.work = report / "work" / tag
        if self.work.exists():
            shutil.rmtree(self.work)
        self.work.mkdir(parents=True)
        # Knut's run, copied: the verification chart is read from the copy
        self.run = self.work / "knut-run6" / "runs" / "run6"
        shutil.copytree(run6, self.run)
        # the run's verification chart (its .tif beside it; the dated
        # folder keeps an identical copy of the .ti2)
        self.ti2 = self.run / "verifications" / "test-verify.ti2"
        assert self.ti2.exists(), self.ti2
        from capture_screens import build_app
        self.app = build_app()
        from core.settings import AppSettings
        from workflow import misread_settings as MS
        s = self.settings = AppSettings()
        s.set("custom_output_path", str(self.work))
        for k, v in (("appearance", "light"), ("language", "en"),
                     ("show_welcome", False), ("update_notify", False),
                     ("sound_enabled", False), ("chartread_engine", "chromiq"),
                     ("restore_last_session", False)):
            s.set(k, v)
        s.set(MS.PATCH_ERROR_LIMIT_KEYS["verification"], 15.0)
        s.set(MS.NEIGHBOUR_LIMIT_KEYS["verification"], 7.0)
        s.set(MS.NEIGHBOUR_RADIUS_KEYS["verification"], 30.0)
        s.set(MS.STRIP_TEST_KEYS["verification"], False)
        s.set(MS.SAME_READING_KEY, 3.0)
        s.set(MS.NEIGHBOUR_CHECK_KEY, True)
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
        self.n_shot = 0

    def views_on(self):
        self.settings.set("measure_show_overlay", True)
        self.mt._m_overlay_cb.setChecked(True)
        self.mt._m_patch_tile.setChecked(True)
        self.mt._apply_active_view_settings()

    def load(self):
        from workflow import verify_expected as ve
        mt = self.mt
        mt._session_live = False
        mt.set_ti1_path(self.ti2)
        pump(self.app, 1500)
        self.views_on()
        pred = {p["loc"]: tuple(p["exyz"])
                for p in self.data["events"][0]["patches"]}
        for ev in self.data["events"]:
            for p in ev["patches"]:
                pred[p["loc"]] = tuple(p["exyz"])
        le = ve.LiveExpected(ve.SOURCE_PREDICTION,
                             "Knut's run 6: the run profile's prediction", pred,
                             route="raw")
        mt._expected_source_for = lambda ti3, le=le: le
        mt._live_expected = self.le = le
        mt._warn_kind_cache = None
        mt._reset_flag_judge()
        mt._preview.clear_patch_overlay()
        log(f"chart kind {mt._chart_kind()}, limit {mt._patch_warn_limit()}, "
            f"neighbour {mt._neighbour_parameters()}")
        assert mt._chart_kind() == "verification"

    def session(self):
        mt = self.mt
        mt._spot_session = False
        mt._session_resumes = False
        mt._session_live = True
        mt._live_expected = self.le
        mt._reset_flag_judge()
        strips = sorted({e["strip"] for e in self.data["events"]})
        mt._manager.session_map.emit([{"strip": s, "read": False,
                                       "verifiable": True} for s in strips])
        pump(self.app, 600)
        for ev in self.data["events"]:
            mt._manager.strip_measured.emit(
                {"strip": ev["strip"],
                 "patches": [{"id": p["loc"], "loc": p["loc"],
                              "exyz": p["exyz"], "xyz": p["xyz"],
                              "de": p["de"]} for p in ev["patches"]]})
            pump(self.app, 120)
            log(f"strip {ev['strip']} read ({ev['time']})")
        pump(self.app, 800)

    def flags(self) -> dict:
        mt = self.mt
        by_box = {(b.x(), b.y(), b.width()): loc
                  for loc, b in mt._patch_boxes[0].items()}
        out = {}
        for it in mt._preview._patch_overlay.get(0, []):
            loc = by_box.get((it[0].x(), it[0].y(), it[0].width()))
            if loc:
                out[loc] = it[3]
        return out

    @staticmethod
    def word(f) -> str:
        from workflow import patch_flags as pf
        if f is True:
            return "red"
        if f == pf.FLAG_CONFIRMED:
            return "yellow (confirmed)"
        if f == pf.FLAG_LEARNED:
            return "yellow (learned)"
        if f == pf.FLAG_CORRECTED:
            return "green"
        return "none"

    def photo(self, widget, name: str) -> str:
        from onscreen_capture import capture_window
        self.n_shot += 1
        path = self.shots / f"{self.n_shot:02d}_{name}.png"
        ok, why = capture_window(widget, path)
        if not ok:
            log(f"PHOTO FAILED {path.name}: {why}")
            return f"(not taken: {why})"
        return str(path)

    def card(self, loc: str, name: str) -> "tuple[str, str]":
        from PyQt6.QtCore import QPoint
        pv = self.mt._preview
        rect = self.mt._patch_boxes[0][loc]
        geom = pv._paint_geom
        scale, ox, oy = geom
        sy = pv._paint_scale_y or scale
        lp = QPoint(int(rect.center().x() * scale + ox),
                    int(rect.center().y() * sy + oy))
        pv._update_patch_tile(pv._img_label.mapTo(pv, lp))
        pump(self.app, 600)
        tile = pv._patch_tile
        text = "" if tile is None else " / ".join(
            str(t) for _s, t in tile._rows if t)
        shot = self.photo(self.win, name)
        pv._hide_patch_tile()
        pump(self.app, 200)
        return shot, text


def main() -> int:
    run6, fixture, report, tag = (Path(sys.argv[1]).resolve(),
                                  Path(sys.argv[2]).resolve(),
                                  Path(sys.argv[3]).resolve(), sys.argv[4])
    d = Driver(run6, fixture, report, tag)
    result = {"tag": tag, "tree": str(ROOT), "passes": {}}
    from workflow import misread_settings as MS
    try:
        for nb in (7.0, 5.0):
            d.settings.set(MS.NEIGHBOUR_LIMIT_KEYS["verification"], nb)
            d.load()
            d.session()
            flags = {k: d.word(v) for k, v in d.flags().items()}
            tally: dict = {}
            for w in flags.values():
                tally[w] = tally.get(w, 0) + 1
            tally["none"] = 324 - sum(v for k, v in tally.items()
                                      if k != "none")
            key = f"limit15_nb{nb:g}"
            log(f"{key}: {tally}")
            d.photo(d.win, f"{key}_outlines")
            cards = {}
            for loc in FOCUS:
                shot, text = d.card(loc, f"{key}_card_{loc}")
                cards[loc] = {"outline": flags.get(loc, "none"),
                              "shot": shot, "text": text}
                log(f"{key} {loc}: {flags.get(loc, 'none')}")
            result["passes"][key] = {"tally": tally, "cards": cards,
                                     "outlines": flags}
            d.mt._session_live = False
            pump(d.app, 300)
    finally:
        (report / f"result_{tag}.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        d.dog.stop()
        (report / f"driver_{tag}.log").write_text("\n".join(LOG),
                                                  encoding="utf-8")
        d.win.close()
        pump(d.app, 400)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
