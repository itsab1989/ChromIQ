#!/usr/bin/env python3
"""Every combination of the two misread tests, ON SCREEN in the real app
(#182, 4.3.5 beta 8; UMM 10.12 and its 35-row table).

    CHROMIQ_SETTINGS_FILE=<report>/run/driver.ini \\
    CHROMIQ_PRESETS_DIR=<report>/run/presets \\
        python scripts/drive_b8_matrix.py <report folder> [scenario ids...]

Knut, #182 6196667833: *"Make sure all combination of messages, errors and
neighbour check combinations are verified using demo data on screen on the
app ... and all the combinations of the hover-text cards, as well as the
behaviour of the highlighting colors."*

The demo data is ``scripts/b8_matrix_demo.py``: one chart made by ChromIQ's
layout engine (copied as each chart type) and one scenario per case, each a
measurement session of its own. WHAT IS REAL: the window, the Measure tab,
the chart and its preview, the outlines, the hover cards (opened by the
preview's own hover code at the patch's centre, no mouse events, so Basti's
pointer and keyboard are never taken), the closing window's summary
(``_misread_summary``, the text that window shows), the Preferences values
(the sandboxed settings the app reads) and the repaint from disk. WHAT IS
SIMULATED: the instrument, at the seam the reading engine uses: the driver
emits ``MeasureManager.session_map`` / ``strip_measured`` /
``patch_measured`` with the scenario's readings. Nothing is printed, no
instrument is opened, nothing is written outside the report folder.

Every check is photographed (the window, by its id) and the outline colour
is ALSO read from that photograph: the pixels around the patch, against the
three ring colours of ``ui/tiff_preview.py``. ``results.json`` holds every
observation; ``VERDICTS.md`` is written from it by
``scripts/b8_matrix_verdicts.py``.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

import b8_matrix_demo as demo  # noqa: E402

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


# ---- matching a card against the specification's sentences ---------------------
NUM_RX = r"ΔE\*ab (\d+\.\d\d)"


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", str(t)).strip()


def frag_regex(frag: str):
    """(regex, wanted numbers): *frag*'s literal words, any ΔE*ab figure
    for NUM, any of the listed patches for LIKE, and every ΔE*ab figure
    it names captured, to be compared within 0.011."""
    parts, nums = [], []
    pos = 0
    tok = re.compile(r"\x00NUM\x00|\x00LIKE:([^\x00]*)\x00|ΔE\*ab (\d+\.\d\d)")
    frag = norm_text(frag)
    for m in tok.finditer(frag):
        parts.append(re.escape(frag[pos:m.start()]))
        if m.group(0) == demo.NUM:
            parts.append(r"ΔE\*ab \d+\.\d\d")
        elif m.group(1) is not None:
            parts.append("(?:" + "|".join(re.escape(x)
                                         for x in m.group(1).split("|")) + ")")
        else:
            parts.append(NUM_RX)
            nums.append(float(m.group(2)))
        pos = m.end()
    parts.append(re.escape(frag[pos:]))
    rx = "".join(parts).replace(r"\ ", r"\s+")
    return re.compile(rx), nums


def match_card(text: str, frags, absent) -> dict:
    text = norm_text(text)
    pos, missing, order, numbers = 0, [], [], []
    for f in frags:
        rx, nums = frag_regex(f)
        m = rx.search(text, pos)
        while m is not None:
            got = [float(x) for x in m.groups() if x is not None
                   and re.fullmatch(r"\d+\.\d\d", x)]
            if all(abs(a - b) <= 0.011 for a, b in zip(got, nums)):
                break
            m = rx.search(text, m.start() + 1)
        if m is None:
            m2 = rx.search(text)
            if m2 is not None:
                order.append(norm_text(f))
            else:
                # the words are there with other numbers?
                loose = re.compile(re.sub(re.escape(NUM_RX), r"ΔE\\*ab \\d+\\.\\d\\d",
                                          rx.pattern))
                if loose.search(text):
                    numbers.append(norm_text(f))
                else:
                    missing.append(norm_text(f))
            continue
        pos = m.end()
    present = [a for a in list(absent) + demo.GONE if a in text]
    return {"missing": missing, "order": order, "numbers": numbers,
            "present_absent": present,
            "ok": not (missing or order or numbers or present)}


class Driver:
    def __init__(self, report: Path):
        assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
        assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
        assert not os.environ.get("QT_QPA_PLATFORM"), "this driver opens windows"
        self.report = report
        self.shots = report / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        self.work = report / "work"
        self.charts = demo.build_charts(self.work / "charts")
        self.xyz = demo.read_ti2_xyz(self.charts["estimated"])
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
        self.appearance = "light"
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
        self.loaded = None

    # ---- set up ----------------------------------------------------------------
    def apply_settings(self, sc: dict, **over) -> None:
        from workflow import misread_settings as MS
        k = sc["kind"]
        vals = {"pe": sc["pe"], "nb": sc["nb"], "radius": sc["radius"],
                "tol": sc["tol"]}
        vals.update(over)
        s = self.settings
        s.set(MS.PATCH_ERROR_LIMIT_KEYS[k], float(vals["pe"]))
        s.set(MS.NEIGHBOUR_LIMIT_KEYS[k], float(vals["nb"]))
        s.set(MS.NEIGHBOUR_RADIUS_KEYS[k], float(vals["radius"]))
        s.set(MS.STRIP_TEST_KEYS[k], bool(sc["strip_test"]))
        s.set(MS.SAME_READING_KEY, float(vals["tol"]))
        s.set(MS.NEIGHBOUR_CHECK_KEY, bool(sc["nb_on"]))
        self.cur = vals

    def views_on(self) -> None:
        self.settings.set("measure_show_overlay", True)
        self.mt._m_overlay_cb.setChecked(True)
        self.mt._m_patch_tile.setChecked(True)
        self.mt._apply_active_view_settings()

    def expected_source(self, sc):
        from workflow import verify_expected as ve
        if sc["kind"] == "verification":
            return ve.LiveExpected(ve.SOURCE_PREDICTION,
                                   "b8 matrix demo: the prediction is the "
                                   "chart's own colour", dict(self.xyz),
                                   route="raw")
        if sc["mode"] == "later":
            return ve.estimate("b8 matrix demo: the profile is newer",
                               profile_newer=True)
        return None

    def reading(self, loc: str, err) -> dict:
        exyz = list(self.xyz[loc])
        exp_lab = demo.xyz100_to_lab(exyz)
        xyz = list(demo.lab_to_xyz100(demo.add(exp_lab, err)))
        return {"id": loc, "loc": loc, "exyz": exyz, "xyz": xyz,
                "de": demo.norm(err)}

    def final_readings(self, sc) -> dict:
        last: dict = {}
        for st in sc["steps"]:
            if st[0] == "strip":
                last.update(st[2])
            elif st[0] == "patch":
                last[st[1]] = st[2]
        return last

    def write_ti3(self, ti3: Path, readings: dict) -> None:
        """The measurement as the session will leave it: the last reading of
        every patch read, in the chart's own order."""
        order = {loc: i for i, loc in enumerate(demo.all_locs())}
        lines = ["CTI3   ", "",
                 'DESCRIPTOR "Argyll Calibration Target chart information 3"',
                 'ORIGINATOR "b8 matrix demo"', 'DEVICE_CLASS "OUTPUT"',
                 'COLOR_REP "RGB_XYZ"', "", "NUMBER_OF_FIELDS 8",
                 "BEGIN_DATA_FORMAT",
                 "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z ",
                 "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(readings)}",
                 "BEGIN_DATA"]
        for loc in sorted(readings, key=lambda x: order[x]):
            r = self.reading(loc, readings[loc])
            lines.append(f'{order[loc] + 1} "{loc}" 50.0 50.0 50.0 '
                         + " ".join(f"{v:.6f}" for v in r["xyz"]))
        lines.append("END_DATA")
        ti3.write_text("\n".join(lines) + "\n", encoding="ascii")

    def load(self, sc) -> None:
        mt = self.mt
        mt._session_live = False
        ti2 = self.charts[sc["kind"]]
        ti3 = ti2.with_suffix(".ti3")
        for p in (ti3, ti2.parent / (ti2.stem + ".confirmed.json")):
            if p.exists():
                p.unlink()
        old = ti2.parent / "old"
        if old.exists():
            shutil.rmtree(old)
        app = sc.get("appearance", "light")
        if app != self.appearance:
            from ui.theme import apply_appearance
            self.settings.set("appearance", app)
            apply_appearance(self.app, None, app)
            self.appearance = app
            pump(self.app, 800)
        self.apply_settings(sc)
        mt.__dict__.pop("_expected_source_for", None)
        self.le = self.expected_source(sc)
        if self.le is not None:
            mt._expected_source_for = lambda ti3, le=self.le: le
        if self.loaded != ti2:
            mt.set_ti1_path(ti2)
            pump(self.app, 1500)
            self.loaded = ti2
            self.views_on()
        mt._live_expected = self.le
        mt._warn_kind_cache = None
        mt._preview.clear_patch_overlay()
        mt._reset_flag_judge()
        pump(self.app, 200)

    def start_session(self, sc) -> None:
        mt = self.mt
        mt._spot_session = bool(sc["pbp"])
        mt._session_whole_chart = False
        mt._session_resumes = False
        mt._strips_read_again = []
        mt._session_live = True
        mt._live_expected = self.le
        mt._reset_flag_judge()
        mt._preview.clear_patch_overlay()
        mt._manager.session_map.emit([{"strip": s, "read": False,
                                       "verifiable": True}
                                      for s in demo.STRIPS])
        pump(self.app, 400)

    # ---- observe ---------------------------------------------------------------
    def info_of(self, loc: str) -> "tuple[object, dict | None]":
        pv = self.mt._preview
        box = self.mt._patch_boxes[0][loc]
        flag = None
        for it in pv._patch_overlay.get(0, []):
            b = it[0]
            if (b.x(), b.y(), b.width(), b.height()) == (
                    box.x(), box.y(), box.width(), box.height()):
                flag = it[3]
        info = None
        for rect, inf in pv._patch_info.get(0, []):
            if (rect.x(), rect.y(), rect.width()) == (box.x(), box.y(),
                                                       box.width()):
                info = inf
        return flag, info

    @staticmethod
    def word(f) -> str:
        from workflow import patch_flags as pf
        if f is None or f is False:
            return "none"
        if f is True:
            return "red"
        if pf.is_yellow(f):
            return "yellow"
        if pf.is_corrected(f):
            return "green"
        return f"?{f!r}"

    def photo(self, name: str) -> "tuple[str, object]":
        from onscreen_capture import capture_window
        from PyQt6.QtGui import QImage
        self.n_shot += 1
        path = self.shots / f"{self.n_shot:03d}_{name}.png"
        ok, why = capture_window(self.win, path)
        if not ok:
            log(f"PHOTO FAILED {path.name}: {why}")
            return f"(not taken: {why})", None
        return str(path), QImage(str(path))

    def ring_colour(self, img, loc: str) -> str:
        """The outline colour as the PHOTOGRAPH shows it: the pixels of a
        band around the patch, counted against the three ring colours."""
        if img is None or img.isNull():
            return "no photo"
        from PyQt6.QtCore import QPoint
        pv = self.mt._preview
        rect = self.mt._patch_boxes[0][loc]
        scale, ox, oy = pv._paint_geom
        sy = pv._paint_scale_y or scale
        x0, y0 = rect.x() * scale + ox, rect.y() * sy + oy
        x1, y1 = (rect.x() + rect.width()) * scale + ox, (
            rect.y() + rect.height()) * sy + oy
        g0 = pv._img_label.mapToGlobal(QPoint(int(round(x0)), int(round(y0))))
        g1 = pv._img_label.mapToGlobal(QPoint(int(round(x1)), int(round(y1))))
        fg = self.win.frameGeometry()
        k = img.width() / max(1, fg.width())
        X0, Y0 = (g0.x() - fg.x()) * k, (g0.y() - fg.y()) * k
        X1, Y1 = (g1.x() - fg.x()) * k, (g1.y() - fg.y()) * k
        targets = {"red": (0xff, 0x2b, 0x2b), "yellow": (0xff, 0xd4, 0x00),
                   "green": (0x1f, 0xd6, 0x5f)}
        counts = {n: 0 for n in targets}
        band = max(2, int(round(4 * k)))
        total = 0
        # THE LEFT AND RIGHT SIDES ONLY, between the corners: the chart's
        # coloured spacers run above and below each patch, and a yellow or
        # cyan spacer must not be read as an outline.
        for yy in range(int(Y0) + 2 * band, int(Y1) - 2 * band + 1):
            for xx in list(range(int(X0) - band, int(X0) + band + 1)) + list(
                    range(int(X1) - band, int(X1) + band + 1)):
                if not (0 <= xx < img.width() and 0 <= yy < img.height()):
                    continue
                c = img.pixelColor(xx, yy)
                total += 1
                for n, (r, g, b) in targets.items():
                    if (abs(c.red() - r) + abs(c.green() - g)
                            + abs(c.blue() - b)) < 45:
                        counts[n] += 1
        best = max(counts, key=counts.get)
        if counts[best] < max(4, total * 0.03):
            return "none"
        return best

    def card(self, loc: str) -> "tuple[str, list]":
        from PyQt6.QtCore import QPoint
        pv = self.mt._preview
        rect = self.mt._patch_boxes[0][loc]
        scale, ox, oy = pv._paint_geom
        sy = pv._paint_scale_y or scale
        lp = QPoint(int(rect.center().x() * scale + ox),
                    int(rect.center().y() * sy + oy))
        pv._update_patch_tile(pv._img_label.mapTo(pv, lp))
        pump(self.app, 500)
        tile = pv._patch_tile
        rows = [] if tile is None or not tile.isVisible() else [
            str(t) for _s, t in tile._rows if t]
        return " ".join(rows), rows

    def hide_card(self) -> None:
        self.mt._preview._hide_patch_tile()
        pump(self.app, 150)

    def observe(self, sc, checks, stage: str, overview=None) -> list:
        """Each check now: outline (drawn and photographed), card text,
        inputs (each test triggered or not), the card's photograph."""
        out = []
        shot, img = overview if overview else self.photo(
            f"{sc['id']}_{stage}_outlines")
        for ck in checks:
            loc = ck["loc"]
            flag, info = self.info_of(loc)
            drawn = self.word(flag)
            seen = self.ring_colour(img, loc)
            text, rows = self.card(loc)
            cshot, _ = self.photo(f"{sc['id']}_{stage}_card_{loc}")
            self.hide_card()
            pe_in = "y" if info and info.get("warn") else "n"
            nb_in = "y" if info and info.get("neighbour") else "n"
            res = {"case": ck["case"], "loc": loc, "stage": stage,
                   "expect_outline": ck["outline"], "drawn": drawn,
                   "photo_outline": seen, "card_text": text, "rows": rows,
                   "card_shot": cshot, "overview_shot": shot,
                   "pe_input": pe_in, "nb_input": nb_in,
                   "pe_state": (info or {}).get("pe_state", ""),
                   "nb_state": (info or {}).get("nb_state", ""),
                   "want_pe": ck.get("pe", ""), "want_nb": ck.get("nb", ""),
                   "note": ck.get("note", ""),
                   "expect_card": ck["card"], "absent": ck["absent"]}
            if ck["card"] is not None:
                res["match"] = match_card(text, ck["card"], ck["absent"])
            else:
                res["match"] = match_card(text, [], ck["absent"])
                res["match"]["card_not_specified"] = True
            inputs_ok = ((not ck.get("pe") or ck["pe"] == pe_in)
                         and (not ck.get("nb") or ck["nb"] == nb_in))
            res["inputs_ok"] = inputs_ok
            res["outline_ok"] = drawn == ck["outline"] and (
                seen == ck["outline"] or seen == "no photo")
            res["pass"] = bool(res["outline_ok"] and res["match"]["ok"]
                               and inputs_ok)
            log(f"  {sc['id']} {stage} {loc}: case {ck['case']} drawn {drawn}"
                f" / photo {seen} (want {ck['outline']}); pe {pe_in} nb "
                f"{nb_in} [{res['pe_state']}/{res['nb_state']}]; card "
                f"{'ok' if res['match']['ok'] else res['match']}; "
                f"{'PASS' if res['pass'] else 'FAIL'}")
            out.append(res)
        return out

    def end_with_file(self, sc) -> None:
        """The session ends as the engine leaves it: the .ti3 holds the last
        reading of every patch, and the tab writes its memory beside it,
        stamped with that file (``_save_confirmed_memory``, what
        ``_save_confirmed_memory_at_end`` does). Written only now: a .ti3 on
        disk DURING the session would be painted as earlier readings."""
        ti3 = self.charts[sc["kind"]].with_suffix(".ti3")
        self.write_ti3(ti3, self.final_readings(sc))
        self.mt._save_confirmed_memory(ti3)
        log(f"  measurement written: {ti3.name} + memory")

    def closing_window(self, sc) -> dict:
        """The window that closes a measurement, opened by the tab's own
        ``_show_all_stripes_done`` while the session is live, photographed
        and closed with its "Re-read" answer (reject): nothing is saved."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QLabel
        from onscreen_capture import capture_window
        got: dict = {}

        def grab():
            dlg = QApplication.activeModalWidget()
            if dlg is None:
                if got.get("tries", 0) < 20:
                    got["tries"] = got.get("tries", 0) + 1
                    QTimer.singleShot(250, grab)
                return
            self.n_shot += 1
            path = self.shots / f"{self.n_shot:03d}_{sc['id']}_closing_window.png"
            ok, why = capture_window(dlg, path)
            got["title"] = dlg.windowTitle()
            got["text"] = "\n".join(lb.text() for lb in dlg.findChildren(QLabel))
            got["shot"] = str(path) if ok else f"(not taken: {why})"
            dlg.reject()
        QTimer.singleShot(1200, grab)
        self.mt._show_all_stripes_done()
        pump(self.app, 400)
        log(f"  closing window: {got.get('title')} ({got.get('shot')})")
        return got

    def refresh(self) -> None:
        """What the main window does when Preferences closes with OK."""
        mt = self.mt
        loads = getattr(mt, "_memory_loads", 0)
        try:
            ex = mt._existing_ti3_for_chart()
        except Exception as exc:      # noqa: BLE001
            ex = f"error {exc}"
        log(f"  refresh: overlay box {mt._m_overlay_cb.isChecked()} mode {mt._current_mode()}, measurement on disk {ex}, loading settings "
            f"{getattr(mt, '_loading_measure_settings', None)}")
        self.win._tab_measure.refresh_patch_flags()
        pump(self.app, 800)
        j = mt._flag_judge()
        log(f"  refresh: session {mt._session_live}, memory loads {loads} -> "
            f"{getattr(mt, '_memory_loads', 0)}, judge tolerance "
            f"{j.same_reading_de}, radius {j.peer_radius}, references "
            f"{sorted(j._refs)}")

    def summary(self) -> str:
        try:
            return self.mt._misread_summary()
        except Exception as exc:      # noqa: BLE001
            return f"(summary failed: {exc})"

    @staticmethod
    def summary_check(text: str, wanted) -> dict:
        lines = [norm_text(x) for x in text.splitlines() if x.strip()]
        res = {"lines": lines, "missing": [], "unexpected": []}
        for w in wanted or []:
            if w == "(none)":
                bad = [x for x in lines if "Neighbour check" in x]
                res["unexpected"] += bad
                continue
            name, *args = w.split(":", 2)
            kw = {}
            if name in ("_SUM_NB_RED_ONE", "_SUM_NB_RED_ONE_VERIFY"):
                kw = {"locs": args[0]}
            elif name in ("_SUM_NB_RED", "_SUM_NB_RED_VERIFY"):
                kw = {"n": args[0], "locs": args[1]}
            elif name == "_SUM_NB_KEPT":
                kw = {"n": args[0]}
            elif name == "_SUM_NB_NONE_CHECKED":
                kw = {"total": args[0]}
            want = norm_text(demo.M(name, **kw))
            if want not in lines:
                res["missing"].append(want)
        nb_lines = [x for x in lines if x.startswith("Neighbour check:")
                    or "flagged were read again" in x
                    or "flagged was read again" in x]
        wanted_txt = []
        for w in wanted or []:
            if w != "(none)":
                wanted_txt.append(w)
        res["nb_lines"] = nb_lines
        res["ok"] = not res["missing"] and not res["unexpected"]
        return res

    def emit_strip(self, st) -> None:
        """One strip read: ("strip", letter, readings[, event extras]); the
        extras (e.g. {"misaligned": 1}, the engine's safety net, #210) go
        into the strip_read event as the engine puts them there."""
        ev = {"strip": st[1],
              "patches": [self.reading(loc, err) for loc, err in st[2].items()]}
        if len(st) > 3:
            ev.update(st[3])
        self.mt._manager.strip_measured.emit(ev)
        pump(self.app, 150)

    def resume(self, sc) -> None:
        """The session ends with its file and memory written, and a new one
        resumes that measurement (Refine / resume): the tab's own session
        start, `_on_session_map` with `_session_resumes`, which loads the
        memory and repaints the stored readings."""
        self.end_with_file(sc)
        mt = self.mt
        mt._session_live = False
        pump(self.app, 200)
        self.views_on()
        mt._session_resumes = True
        mt._strips_read_again = []
        mt._session_live = True
        mt._live_expected = self.le
        mt._manager.session_map.emit([{"strip": s, "read": True,
                                       "verifiable": True}
                                      for s in demo.STRIPS])
        pump(self.app, 800)
        log(f"  session resumed: slipped from the memory "
            f"{sorted(getattr(mt, '_slipped_locs', ()))[:8]}")

    # ---- one scenario ------------------------------------------------------------
    def run(self, sc) -> dict:
        log(f"== {sc['id']}: {sc['title']}")
        self.load(sc)
        self.start_session(sc)
        mt = self.mt
        res = {"id": sc["id"], "title": sc["title"], "kind": sc["kind"],
               "pe": sc["pe"], "nb": sc["nb"], "radius": sc["radius"],
               "tol": sc["tol"], "strip_test": sc["strip_test"],
               "nb_on": sc["nb_on"], "mode": sc["mode"], "pbp": sc["pbp"],
               "appearance": sc.get("appearance", "light"), "observed": []}
        staged = {}
        for ck in sc["checks"]:
            m = re.search(r"at (?:step )?'([^']+)'", ck.get("note", ""))
            staged.setdefault(m.group(1) if m else "", []).append(ck)
        for st in sc["steps"]:
            if st[0] == "strip":
                self.emit_strip(st)
            elif st[0] == "patch":
                mt._manager.patch_measured.emit(self.reading(st[1], st[2]))
                pump(self.app, 150)
            elif st[0] == "set":
                over = dict(self.cur)
                over[st[1]] = st[2]
                self.apply_settings(sc, **over)
                log(f"  Preferences: {st[1]} = {st[2]}")
            elif st[0] == "refresh":
                self.refresh()
            elif st[0] == "check":
                pump(self.app, 300)
                res["observed"] += self.observe(sc, staged.get(st[1], []),
                                                re.sub(r"\W+", "-", st[1]))
        pump(self.app, 500)
        final = self.observe(sc, staged.get("", []), "final")
        res["observed"] += final
        res["summary"] = self.summary()
        if sc.get("summary"):
            res["summary_check"] = self.summary_check(res["summary"],
                                                      sc["summary"])
            log(f"  summary: {res['summary_check']}")
        for st in sc.get("after", []):
            if st[0] == "resume":
                self.resume(sc)
            elif st[0] == "strip":
                self.emit_strip(st)
            elif st[0] == "end":
                self.end_with_file(sc)
                mt._session_live = False
                pump(self.app, 200)
                # the measurement on disk shown as the overlay, as a user
                # who ticks "Show it as an overlay" sees it
                self.views_on()
                pump(self.app, 600)
                log("  session ended; overlay box ticked")
            elif st[0] == "set":
                over = dict(self.cur)
                over[st[1]] = st[2]
                self.apply_settings(sc, **over)
                log(f"  Preferences: {st[1]} = {st[2]}")
            elif st[0] == "refresh":
                self.refresh()
            elif st[0] == "window":
                res["closing_window"] = self.closing_window(sc)
            elif st[0] == "expect":
                ck = st[1]
                res["observed"] += self.observe(
                    sc, [ck], re.sub(r"\W+", "-", ck.get("note", "after"))[:30])
            elif st[0] == "reopen":
                self.end_with_file(sc)
                mt._session_live = False
                pump(self.app, 200)
                mt._reset_flag_judge()
                mt._preview.clear_patch_overlay()
                pump(self.app, 200)
                ok = mt._show_overlay_from_existing_ti3()
                pump(self.app, 800)
                log(f"  reopened from disk: painted {ok}")
                again = self.observe(sc, staged.get("", []), "reopened")
                for a, b in zip(final, again):
                    mask = lambda t: re.sub(r"\d+\.\d\d", "#", t)  # noqa: E731
                    b["same_as_session"] = (
                        a["drawn"] == b["drawn"]
                        and mask(a["card_text"]) == mask(b["card_text"]))
                    b["pass"] = bool(b["pass"] and b["same_as_session"])
                res["observed"] += again
        mt._session_live = False
        pump(self.app, 200)
        return res


def main() -> int:
    report = Path(sys.argv[1]).resolve()
    only = set(sys.argv[2:])
    d = Driver(report)
    results = {"tree": str(ROOT), "charts": {k: str(v) for k, v in
                                             d.charts.items()},
               "started": time.strftime("%Y-%m-%d %H:%M:%S"),
               "scenarios": []}
    out = report / ("results.json" if not only else "results_partial.json")
    try:
        for sc in demo.scenarios():
            if only and sc["id"] not in only:
                continue
            try:
                results["scenarios"].append(d.run(sc))
            except Exception:      # noqa: BLE001 — record it and go on
                tb = traceback.format_exc()
                log(f"SCENARIO {sc['id']} FAILED TO RUN:\n{tb}")
                results["scenarios"].append({"id": sc["id"], "error": tb})
            out.write_text(json.dumps(results, indent=1, ensure_ascii=False),
                           encoding="utf-8")
    finally:
        results["popups"] = [dict((k, v) for k, v in ev.items()
                                  if isinstance(v, (str, int, float, bool)))
                             for ev in d.dog.events]
        out.write_text(json.dumps(results, indent=1, ensure_ascii=False),
                       encoding="utf-8")
        d.dog.stop()
        (report / "driver.log").write_text("\n".join(LOG), encoding="utf-8")
        d.win.close()
        pump(d.app, 400)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
