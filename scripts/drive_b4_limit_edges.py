#!/usr/bin/env python3
"""Every misread limit, exactly at its edge, on every chart type, ON SCREEN
(#182, Knut 6154440320, 4.3.5 beta 4).

    python scripts/make_limit_edge_demo.py <dir>          # the demo data
    CHROMIQ_SETTINGS_FILE=<report>/driver.ini \\
    CHROMIQ_PRESETS_DIR=<report>/presets \\
        python scripts/drive_b4_limit_edges.py <dir>/Demo-Limit-Edges <report>

WHAT IS REAL AND WHAT IS NOT. The window, the Measure tab, the charts (laid
out by ChromIQ's engine), the preview, its outlines, the hover cards read off
the preview under the pointer, and Preferences ▸ Measurement with its OK are
the app's own; every card is photographed from the window by its id. The
INSTRUMENT is simulated at the seam the reading engine uses: the driver emits
``MeasureManager``'s ``session_map`` and ``strip_measured`` signals with the
demo's readings (``scripts/make_limit_edge_demo.py``). A verification judged
against its profile is handed the chart's own expected colours as the
profile's prediction; the "later" verification is handed the estimate, with
the profile made after the sheet was printed (the spec's A27). No instrument
is opened; nothing is written outside the report folder.

THE PROTOCOL (:func:`protocol`), per chart type, with every limit of
Preferences ▸ Measurement set to its own unique value
(``make_limit_edge_demo.LIMITS``):

* pass A, the neighbour check OFF: the patch error limit (under, on, over),
  the strip test (fence - 0.01, fence + 0.01), similar patches (yellow), the
  re-reads (yellow at exactly the Same-reading tolerance, red and unsettled
  0.01 beyond it, green by the limit) and a colour range learning (yellow,
  judged like a confirmed patch);
* pass B, the neighbour check ON: the Neighbour limit (under, on, over),
  "does not stand out", "closer", "not compared" (fewer than 2 similar
  patches), red for both tests, and the re-reads (yellow, green by the
  neighbour check).

Every case is judged twice: the outline the preview draws and the card's
sentences, against what the demo's own figures say (never the app's judging
code). The same protocol runs offscreen in
``tests/test_435b4_limit_edges.py`` (:class:`Rig`), without photographs.
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


def ab(v) -> str:
    return "ΔE*ab " + f"{float(v):.2f}"


# ---- the app, driven at the reading engine's seam ----------------------------
class Rig:
    """The Measure tab with a demo chart loaded, read through the engine's
    signals. Offscreen (the test) and on screen (:class:`OnScreen`) alike."""

    def __init__(self, app, mt, project: Path):
        self.app, self.mt, self.project = app, mt, Path(project)
        self.kind = None
        self.sc = None

    # -- preferences --------------------------------------------------------
    def prefs(self, changes: dict, shot: str = "") -> None:
        s = self.mt._settings
        for k, v in changes.items():
            s.set(k, v)
        self.mt.refresh_patch_flags()
        pump(self.app, 300)

    # -- the chart ----------------------------------------------------------
    def load(self, kind: str) -> dict:
        from workflow import verify_expected as ve
        sc = json.loads(next(
            p for p in self.project.rglob("*.edges.json")
            if json.loads(p.read_text(encoding="utf-8"))["kind"] == kind
        ).read_text(encoding="utf-8"))
        ti2 = self.project / sc["chart_rel"]
        for suffix in (".ti3", ".confirmed.json"):
            p = ti2.with_suffix(suffix)
            if p.exists():
                p.unlink()
        mt = self.mt
        mt._session_live = False
        mt.set_ti1_path(ti2)
        pump(self.app, 800)
        self.views_on()
        if kind in ("verification", "verification_fpg"):
            pred = {loc: tuple(v["exyz"]) for loc, v in sc["patches"].items()}
            le = ve.LiveExpected(ve.SOURCE_PREDICTION, "demo prediction", pred)
        elif kind == "verification_later":
            le = ve.estimate("the profile has changed since the sheet was "
                             "printed (demo)", profile_newer=True)
        else:
            le = None
        mt._expected_source_for = (lambda ti3, le=le: le)
        mt._live_expected = le
        self.le = le
        mt._warn_kind_cache = None
        mt._reset_flag_judge()
        mt._preview.clear_patch_overlay()
        self.kind, self.sc, self.ti2 = kind, sc, ti2
        got = mt._chart_kind()
        assert got == sc["judged_as"], (kind, got, sc["judged_as"])
        return sc

    def views_on(self) -> None:
        mt = self.mt
        mt._settings.set("measure_show_overlay", True)
        for cb in (getattr(mt, "_m_overlay_cb", None),
                   getattr(mt, "_m_patch_tile", None)):
            if cb is not None:
                cb.setChecked(True)
        if hasattr(mt, "_apply_active_view_settings"):
            mt._apply_active_view_settings()

    # -- reading ------------------------------------------------------------
    def event(self, loc: str, xyz) -> dict:
        from workflow.measurement_report import engine_patch_de
        p = self.sc["patches"][loc]
        return {"id": p["sid"], "loc": loc, "exyz": list(p["exyz"]),
                "xyz": list(xyz),
                "de": round(engine_patch_de(p["exyz"], xyz), 2)}

    def start(self) -> None:
        mt = self.mt
        mt._spot_session = False
        mt._session_resumes = False
        mt._session_live = True
        mt._live_expected = self.le
        mt._reset_flag_judge()
        mt._neighbour_reset()
        mt._preview.clear_patch_overlay()
        smap = [{"strip": s, "read": False, "verifiable": True}
                for s in self.sc["strips"]]
        mt._manager.session_map.emit(smap)
        pump(self.app, 300)
        self.readings: dict = {}

    def read_all(self, readings: dict) -> None:
        for letter in self.sc["strips"]:
            locs = self.sc["strip_locs"][letter]
            self.mt._manager.strip_measured.emit(
                {"strip": letter,
                 "patches": [self.event(x, readings[x]) for x in locs]})
            for x in locs:
                self.readings[x] = readings[x]
            pump(self.app, 40)
        pump(self.app, 400)

    def reread(self, loc: str, xyz) -> None:
        """Read *loc*'s strip again: *loc* with *xyz*, every other patch of
        the strip with its last reading."""
        letter = "".join(c for c in loc if c.isalpha())
        pats = []
        for x in self.sc["strip_locs"][letter]:
            r = xyz if x == loc else self.readings[x]
            self.readings[x] = r
            pats.append(self.event(x, r))
        self.mt._manager.strip_measured.emit({"strip": letter,
                                              "patches": pats})
        pump(self.app, 500)

    def end(self) -> None:
        self.mt._session_live = False
        pump(self.app, 200)

    # -- photographs: none offscreen (:class:`OnScreen` takes them) ---------
    def shot_window(self, name: str) -> str:
        return ""

    def photo_card(self, loc: str, name: str) -> str:
        return ""

    # -- what the app shows -------------------------------------------------
    def _box_of(self, loc):
        return self.mt._patch_boxes[0][loc]

    def flag(self, loc: str):
        mt = self.mt
        b0 = self._box_of(loc)
        for it in mt._preview._patch_overlay.get(0, []):
            b = it[0]
            if (b.x(), b.y(), b.width()) == (b0.x(), b0.y(), b0.width()):
                return it[3]
        return None

    @staticmethod
    def word(f) -> str:
        from workflow import patch_flags as pf
        if f is pf.FLAG_RED or f is True:
            return "red"
        if f == pf.FLAG_CONFIRMED:
            return "yellow (confirmed)"
        if f == pf.FLAG_LEARNED:
            return "yellow (learned)"
        if f == pf.FLAG_CORRECTED:
            return "green"
        return "none"

    def info(self, loc: str) -> dict:
        b0 = self._box_of(loc)
        for b, info in self.mt._preview._patch_info.get(0, []):
            if (b.x(), b.y(), b.width()) == (b0.x(), b0.y(), b0.width()):
                return info
        raise AssertionError(f"no card for {loc}")

    def card(self, loc: str, name: str) -> str:
        """The card's text, as the preview's own tile lays it out."""
        from PyQt6.QtWidgets import QWidget
        from ui.tiff_preview import _PatchInfoTile
        host = QWidget()
        tile = _PatchInfoTile(host)
        tile.set_content(self.info(loc), "both")
        text = "\n".join(str(t) for _s, t in tile._logical)
        host.deleteLater()
        return text


# ---- the protocol, written apart from the app's judging -------------------------
def _expect_cards(sc: dict) -> dict:
    """The sentences each planted patch's card must hold, from the demo's own
    figures (the approved card words, M-PATCH-CARD-PLAIN / M-PATCH-LIMIT)."""
    from workflow import measurement_messages as M
    lim, ph, fa = sc["limits"], sc["kind_phrase"], sc["facts"]
    out = {}

    def lim_s(name, fenced=False):
        t = M._CARDP_LIMIT_FENCED if fenced else M._CARDP_LIMIT
        return t.format(de=ab(fa[name]["de"]), limit=ab(lim["pel"]), kind=ph)

    def nb_red(name, also=False):
        t = M._CARDP_NB_ALSO if also else M._CARDP_NB_RED
        return t.format(d=ab(abs(fa[name]["further"])), limit=ab(lim["nl"]),
                        kind=ph)
    out["pe_over"] = [lim_s("pe_over")]
    out["fence_over"] = [lim_s("fence_over", fenced=True)]
    out["nl_over"] = [nb_red("nl_over")]
    out["nl_green"] = [nb_red("nl_green")]
    out["pe_over_both"] = [lim_s("pe_over"), nb_red("pe_over", also=True)]
    return out


class Protocol:
    def __init__(self, rig: Rig, photos: bool = False):
        self.rig = rig
        self.rows: list = []
        self.photos = photos

    def row(self, case, loc, expected, seen, ok, shot="", card=""):
        self.rows.append({"kind": self.rig.kind, "case": case, "loc": loc,
                          "expected": expected, "seen": seen, "pass": bool(ok),
                          "shot": shot, "card": card})
        log(f"{'PASS' if ok else 'FAIL'} {self.rig.kind:19} {case:32} {loc:5} "
            f"{seen}")

    def look(self, case: str, name: str, want_word: str,
             sentences=(), absent=()) -> None:
        r = self.rig
        loc = r.sc["plan"][name]
        w = r.word(r.flag(loc))
        text = r.card(loc, f"{r.kind}_{case}_{loc}")
        flat = " ".join(text.split())
        missing = [s for s in sentences if " ".join(s.split()) not in flat]
        present = [s for s in absent if " ".join(s.split()) in flat]
        ok = w == want_word and not missing and not present
        seen = w + ("" if not missing else f"; card lacks {missing}") + (
            "" if not present else f"; card has {present}")
        shot = r.photo_card(loc, f"{r.kind}_{case}_{loc}") if self.photos else ""
        self.row(case, loc, want_word + (f"; card: {list(sentences)}"
                                         if sentences else ""),
                 seen, ok, shot, text)

    def run(self, kind: str) -> list:
        from workflow import measurement_messages as M
        from workflow import misread_settings as MS
        from make_limit_edge_demo import settings_values
        r = self.rig
        sc = r.load(kind)
        lim, fa, plan, rr = sc["limits"], sc["facts"], sc["plan"], sc["rereads"]
        ph = sc["kind_phrase"]
        cards = _expect_cards(sc)
        basis = (M._CARDP_BASIS_PREDICTED if kind in ("verification",
                                                      "verification_fpg")
                 else M._CARDP_BASIS_ACCURATE if kind == "accurate"
                 else M._CARDP_BASIS_ESTIMATE)
        # ---- pass A: the neighbour check off --------------------------------
        r.prefs(dict(settings_values(), **{MS.NEIGHBOUR_CHECK_KEY: False}),
                f"{kind}_prefs_A")
        r.start()
        r.read_all(sc["first"])
        r.shot_window(f"{kind}_A_first_read")
        self.look("pe under (limit-0.01)", "pe_under", "none", [basis],
                  absent=[M._CARDP_LIMIT_HEAD])
        self.look("pe on (= limit)", "pe_on", "none",
                  absent=[M._CARDP_LIMIT_HEAD])
        later_a = ([" ".join((M._CARD_LATER_PROFILE_2,
                              M._CARD_LATER_PROFILE_3,
                              M._CARD_LATER_PROFILE_4))]
                   if kind == "verification_later" else [])
        self.look("pe over (limit+0.01)", "pe_over", "red",
                  [M._CARDP_LIMIT_HEAD] + cards["pe_over"] + later_a)
        self.look("fence under (fence-0.01)", "fence_under", "none",
                  absent=[M._CARDP_LIMIT_HEAD])
        self.look("fence over (fence+0.01)", "fence_over", "red",
                  cards["fence_over"])
        peer_head = M._CARD_PEER_1
        for n in (1, 2):
            self.look(f"similar patches {n}", f"peer_{n}", "yellow (confirmed)",
                      [peer_head, M._CARDP_LIMIT_YELLOW.format(
                          de=ab(fa[f"peer_{n}"]["de"]), limit=ab(lim["pel"]),
                          kind=ph)])
        self.look("range: 2 confirmed, not learned yet", "learn_4", "red")
        # the re-reads
        r.reread(plan["pe_over"], rr["pe_over_same"])
        self.look(f"re-read {sc['same_reading']:.2f} apart: same", "pe_over",
                  "yellow (confirmed)",
                  ["Yellow outline: confirmed by a re-read",
                   M._CARDP_CONFIRMED.format(
                       de=ab(fa["rereads"]["pe_over_same_de"]),
                       prev=ab(fa["pe_over"]["de"])),
                   M._CARDP_LIMIT_YELLOW.format(
                       de=ab(fa["rereads"]["pe_over_same_de"]),
                       limit=ab(lim["pel"]), kind=ph)])
        r.reread(plan["pe_unsettled"], rr["pe_unsettled_other"])
        self.look(f"re-read {sc['same_reading'] + 0.01:.2f} apart: unsettled",
                  "pe_unsettled", "red",
                  [M._CARD_UNSETTLED_HEAD,
                   M._CARDP_UNSETTLED_DE_ONE.format(
                       de=ab(fa["rereads"]["pe_unsettled_other_de"]),
                       prevs=ab(fa["pe_unsettled"]["de"])),
                   M._CARDP_UNSETTLED_TWO.format(n=2, limit=ab(lim["pel"]),
                                                 kind=ph)])
        r.reread(plan["pe_green"], rr["pe_green_good"])
        self.look("re-read within the limit: green", "pe_green", "green",
                  [M._CARD_GREEN_HEAD, M._CARDP_GREEN_LIMIT.format(
                      de=ab(fa["pe_green"]["de"]))])
        r.reread(plan["learn_1"], rr["learn_1_same"])
        self.look("third confirmation: re-read", "learn_1", "yellow (confirmed)",
                  ["Yellow outline: confirmed by a re-read"])
        self.look("range learned: judged like", "learn_4", "yellow (learned)",
                  [M._CARD_RANGE_LEARNED_1])
        r.shot_window(f"{kind}_A_after_rereads")
        r.end()
        # ---- pass B: the neighbour check on ------------------------------------
        r.prefs({MS.NEIGHBOUR_CHECK_KEY: True}, f"{kind}_prefs_B")
        r.start()
        r.read_all(sc["first"])
        r.shot_window(f"{kind}_B_first_read")

        def nbc(name, t):
            n, fu = fa[name]["n"], fa[name]["further"]
            return t.format(n=n, d=ab(abs(fu)), own=ab(fa[name]["err"]),
                            median=ab(fa[name]["err"] - fu))
        self.look("nb under (limit-0.01)", "nl_under", "none",
                  [nbc("nl_under", M._CARDP_NBC_FURTHER)])
        self.look("nb on (= limit)", "nl_on", "none",
                  [nbc("nl_on", M._CARDP_NBC_FURTHER)])
        later = ([" ".join((M._CARD_LATER_PROFILE_2, M._CARD_LATER_PROFILE_3,
                            M._CARD_LATER_PROFILE_4))]
                 if kind == "verification_later" else [])
        self.look("nb over (limit+0.01)", "nl_over", "red",
                  [nbc("nl_over", M._CARDP_NBC_FURTHER)] + cards["nl_over"]
                  + later)
        self.look("nb equal: does not stand out", "nb_equal", "none",
                  [M._CARDP_NBC_EQUAL.format(n=fa["nb_equal"]["n"],
                                             own=ab(fa["nb_equal"]["err"]))])
        self.look("nb closer", "nb_closer", "none",
                  [nbc("nb_closer", M._CARDP_NBC_CLOSER)])
        if "nb_few" in plan:
            self.look("nb fewer than 2 similar", "nb_few", "none",
                      [M._CARDP_NBC_FEW])
        self.look("both tests", "pe_over", "red", cards["pe_over_both"])
        r.reread(plan["nl_over"], rr["nl_over_same"])
        self.look("nb re-read the same: yellow", "nl_over",
                  "yellow (confirmed)", ["Yellow outline: confirmed by a re-read"])
        r.reread(plan["nl_green"], rr["nl_green_good"])
        self.look("nb re-read that fits: green", "nl_green", "green",
                  [M._CARD_GREEN_HEAD, M._CARDP_GREEN_NB.format(
                      de=ab(fa["nl_green"]["de"]))])
        r.shot_window(f"{kind}_B_after_rereads")
        r.end()
        return self.rows


# ---- on screen ---------------------------------------------------------------
class OnScreen(Rig):
    def __init__(self, demo: Path, report: Path):
        assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
        assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
        assert not os.environ.get("QT_QPA_PLATFORM"), "this driver opens windows"
        self.report = report
        self.shots = report / "shots"
        self.shots.mkdir(parents=True, exist_ok=True)
        work = report / "work"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        project = work / demo.name
        shutil.copytree(demo, project)
        from capture_screens import build_app
        app = build_app()
        from core.settings import AppSettings
        s = self.settings = AppSettings()
        s.set("custom_output_path", str(work))
        for k, v in (("appearance", "light"), ("language", "en"),
                     ("show_welcome", False), ("update_notify", False),
                     ("sound_enabled", False), ("chartread_engine", "chromiq"),
                     ("restore_last_session", False)):
            s.set(k, v)
        assert s.get("custom_output_path", "") == str(work)
        from onscreen_capture import PopupWatchdog
        self.dog = PopupWatchdog(report, photograph=True)
        self.dog.start()
        from ui.main_window import MainWindow
        from ui.theme import apply_appearance
        apply_appearance(app, None, "light")
        self.win = MainWindow(s)
        self.win.resize(1500, 1060)
        self.win.show()
        pump(app, 2500)
        give = getattr(app, "_chromiq_focus_give_back", None)
        if give is not None:
            give.give_back()
        mt = self.win._tab_measure
        self.win._tabs.setCurrentWidget(mt)
        pump(app, 800)
        mt._switch_mode("manual")
        pump(app, 400)
        super().__init__(app, mt, project)
        self.n_shot = 0
        self.prefs_shots = 0

    def prefs(self, changes: dict, shot: str = "") -> None:
        """Preferences ▸ Measurement, the real dialog: every value set in its
        own control, photographed, OK (MainWindow._open_settings then
        judges the outlines again)."""
        from PyQt6.QtWidgets import QPushButton
        from ui.dialogs.settings_dialog import SettingsDialog
        from workflow import misread_settings as MS
        drv = self

        def scripted_exec(dlg):
            dlg.show()
            tabs = dlg._tabs
            i = next(i for i in range(tabs.count())
                     if tabs.widget(i).isAncestorOf(dlg._misread_table))
            tabs.setCurrentIndex(i)
            pump(drv.app, 400)
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
            pump(drv.app, 500)
            if shot:
                drv.photo(dlg, shot)
            ok = next(b for b in dlg.findChildren(QPushButton)
                      if b.text().replace("&", "").strip().upper() == "OK")
            ok.click()
            pump(drv.app, 300)
            return 1

        real = SettingsDialog.exec
        SettingsDialog.exec = scripted_exec
        try:
            self.win._open_settings()
        finally:
            SettingsDialog.exec = real
        pump(self.app, 1200)
        for k, v in changes.items():
            got = self.settings.get(k)
            assert (bool(got) == v if isinstance(v, bool)
                    else abs(float(got) - float(v)) < 1e-9), (k, v, got)

    def photo(self, widget, name: str) -> str:
        from onscreen_capture import capture_window
        import re
        self.n_shot += 1
        name = re.sub(r"[^A-Za-z0-9_.+-]+", "_", name).strip("_")
        path = self.shots / f"{self.n_shot:03d}_{name}.png"
        ok, why = capture_window(widget, path)
        if not ok:
            log(f"PHOTO FAILED {path.name}: {why}")
            return f"(not taken: {why})"
        return str(path.relative_to(self.report))

    def shot_window(self, name: str) -> str:
        return self.photo(self.win, name)

    def photo_card(self, loc: str, name: str) -> str:
        """Point at *loc* in the preview as a hover does, photograph the
        window with the card open, and keep the card's text beside it."""
        from PyQt6.QtCore import QPoint
        pv = self.mt._preview
        page, rect = self.mt._locate_patch(loc)
        if pv.current_page() != page:
            pv.show_page(page) if hasattr(pv, "show_page") else None
            pump(self.app, 400)
        geom = pv._paint_geom
        if geom is None or rect is None:
            return "(no preview geometry)"
        scale, ox, oy = geom
        sy = pv._paint_scale_y or scale
        lp = QPoint(int(rect.center().x() * scale + ox),
                    int(rect.center().y() * sy + oy))
        pos = pv._img_label.mapTo(pv, lp)
        pv._update_patch_tile(pos)
        pump(self.app, 450)
        shot = self.photo(self.win, name)
        tile = pv._patch_tile
        if tile is not None and not shot.startswith("("):
            (self.report / (shot[:-4] + ".txt")).write_text(
                "\n".join(str(t) for _s, t in tile._logical), encoding="utf-8")
        pv._hide_patch_tile()
        return shot

    def card(self, loc: str, name: str) -> str:
        """On screen: the text of the card the PREVIEW shows under the
        pointer (the photograph's), not a card built for the purpose."""
        from PyQt6.QtCore import QPoint
        pv = self.mt._preview
        page, rect = self.mt._locate_patch(loc)
        geom = pv._paint_geom
        if geom is None or rect is None:
            return super().card(loc, name)
        scale, ox, oy = geom
        sy = pv._paint_scale_y or scale
        lp = QPoint(int(rect.center().x() * scale + ox),
                    int(rect.center().y() * sy + oy))
        pv._update_patch_tile(pv._img_label.mapTo(pv, lp))
        pump(self.app, 150)
        tile = pv._patch_tile
        text = ("\n".join(str(t) for _s, t in tile._logical)
                if tile is not None and tile.isVisible() else "")
        pv._hide_patch_tile()
        return text or super().card(loc, name)


def write_protocol(report: Path, rows: list) -> None:
    (report / "protocol.json").write_text(json.dumps(rows, indent=1),
                                          encoding="utf-8")
    from make_limit_edge_demo import JUDGED_AS, LIMITS, SAME_READING
    n_ok = sum(1 for r in rows if r["pass"])
    lines = ["# Every misread limit at its edge, every chart type (4.3.5 beta 4)",
             "", f"{len(rows)} cases, {n_ok} as expected, "
             f"{len(rows) - n_ok} not.", "",
             "Real app, real windows (light mode, English); the instrument "
             "simulated at the reading engine's signals; expected values from "
             "the demo's own figures. Screenshots in `shots/`, each card's "
             "text beside its picture.", "",
             "Unique limits (Preferences ▸ Measurement): " + "; ".join(
                 f"{k}: patch error {v['pel']:.2f}, neighbour {v['nl']:.2f}, "
                 f"radius {v['nr']:.2f}, strip test on"
                 for k, v in LIMITS.items())
             + f"; same-reading tolerance {SAME_READING:.2f}.", ""]
    kinds = []
    for r in rows:
        if r["kind"] not in kinds:
            kinds.append(r["kind"])
    for k in kinds:
        lines += [f"## {k} (judged with the {JUDGED_AS[k]} limits)", "",
                  "| # | case | patch | expected | seen | ok | card |",
                  "|---|---|---|---|---|---|---|"]
        for i, r in enumerate([x for x in rows if x["kind"] == k], 1):
            shot = (f"[{Path(r['shot']).name}]({r['shot']})"
                    if r["shot"] and not r["shot"].startswith("(") else "")
            exp = r["expected"].replace("|", "/")
            lines.append(f"| {i} | {r['case']} | {r['loc']} | {exp[:220]} | "
                         f"{r['seen'][:200]} | "
                         f"{'yes' if r['pass'] else '**NO**'} | {shot} |")
        lines.append("")
    (report / "PROTOCOL.md").write_text("\n".join(lines), encoding="utf-8")
    (report / "driver.log").write_text("\n".join(LOG), encoding="utf-8")


def main() -> int:
    from make_limit_edge_demo import KINDS
    demo, report = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else KINDS
    d = OnScreen(demo, report)
    rows: list = []
    try:
        for kind in only:
            p = Protocol(d, photos=True)
            try:
                p.run(kind)
            finally:
                rows.extend(p.rows)
                write_protocol(report, rows)
    except Exception as exc:      # noqa: BLE001
        import traceback
        log("EXCEPTION " + "".join(traceback.format_exception(exc)))
    finally:
        write_protocol(report, rows)
        d.dog.stop()
        log(f"popups: {d.dog.unexpected_events()}")
        (report / "driver.log").write_text("\n".join(LOG), encoding="utf-8")
        d.win.close()
        pump(d.app, 400)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
