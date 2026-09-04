#!/usr/bin/env python3
"""AGENT-J — B8-22 regression sweep of the scanner/camera window.

Drives the REAL `ScannerProfileDialog` on screen, clicking real buttons with
QTest, and records PASS / FAIL / UNTESTED per function.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-beta8-agentJ.ini
    python sweep.py [check-id ...]

Nothing under /Users/Basti/develop/ChromIQ is written. The output root is
forced to /private/tmp/agentJ/ChromIQ so ~/ChromIQ is never touched.
"""
from __future__ import annotations
import json, os, sys, time, traceback
from pathlib import Path

ROOT = Path(os.environ.get("CHROMIQ_TREE", "/Users/Basti/develop/ChromIQ"))
sys.path.insert(0, str(ROOT))
WORK = Path("/private/tmp/agentJ")
OUT = WORK / "out"; OUT.mkdir(parents=True, exist_ok=True)
SHOTS = Path("/Users/Basti/Desktop/beta 8/11-regression-sweep/shots")
SHOTS.mkdir(parents=True, exist_ok=True)
_TAG = os.environ.get("AGENTJ_TAG", "base")
_PROGRESS_DIR = Path("/Users/Basti/Desktop/beta 8/_progress")
_PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
#: ONE FILE PER RUN, never a fixed name. This used to be a constant
#: `agentJ.md`, so the second sweep silently overwrote the first one's log —
#: the evidence for one finding replaced by the evidence for a later run on a
#: different tree, with the same 34/0 at the bottom and no way to tell them
#: apart. A log that a later run can overwrite is not evidence, so the tag and
#: the wall-clock go in the NAME.
PROGRESS = _PROGRESS_DIR / ("sweep-%s-%s.md" % (_TAG, time.strftime("%Y%m%d-%H%M%S")))
RESULTS = OUT / ("results-%s.json" % os.environ.get("AGENTJ_TAG", "base"))

assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"

try:
    import PyQt6.QtWebEngineWidgets  # noqa
except ImportError:
    pass
import numpy as np                                             # noqa: E402
from PyQt6.QtCore import Qt, QPoint                            # noqa: E402
from PyQt6.QtGui import QFontDatabase                          # noqa: E402
from PyQt6.QtTest import QTest                                 # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog,  # noqa: E402
                             QMessageBox)
from core.resource_path import resource_path                   # noqa: E402

KNUT = Path("/Users/Basti/Desktop/Combined Scanner Calibration Data")

# ---------------------------------------------------------------- plumbing
_results: list[dict] = []
if RESULTS.is_file():
    try:
        _results = json.loads(RESULTS.read_text(encoding="utf-8"))
    except Exception:
        _results = []

BOXES: list[tuple[str, str]] = []      # (kind, text) of every QMessageBox shown


def record(cid, name, status, note, evidence=""):
    row = {"id": cid, "name": name, "status": status, "note": note,
           "evidence": evidence, "when": time.strftime("%H:%M:%S")}
    _results[:] = [r for r in _results if r["id"] != cid] + [row]
    _results.sort(key=lambda r: r["id"])
    RESULTS.write_text(json.dumps(_results, indent=1, default=str), encoding="utf-8")
    lines = ["# AGENT-J — B8-22 scanner-window regression sweep (staged, append-only)",
             "", "Settings sandboxed to `%s`; output root forced to "
             "`/private/tmp/agentJ/ChromIQ`." % os.environ["CHROMIQ_SETTINGS_FILE"],
             "", "| id | function | status | note |", "|---|---|---|---|"]
    for r in _results:
        lines.append("| %s | %s | **%s** | %s |" % (
            r["id"], r["name"], r["status"],
            r["note"].replace("|", "\\|").replace("\n", "<br>")))
    PROGRESS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[{status:8s}] {cid} {name}: {note[:160]}")


def pump(ms=300):
    app = QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents(); time.sleep(0.005)


def click(btn):
    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
    pump(400)


def shot(w, name):
    p = SHOTS / name
    w.grab().save(str(p))
    return str(p)


# ---- QMessageBox: never block. Record every one, answer the default. -------
def _install_msgbox_capture():
    for meth in ("information", "warning", "critical", "question", "about"):
        orig = getattr(QMessageBox, meth)

        def make(m, o=orig):
            def f(*a, **k):
                txt = ""
                for x in a:
                    if isinstance(x, str):
                        txt += x + " | "
                BOXES.append((m, txt[:300]))
                if m == "question":
                    return QMessageBox.StandardButton.Yes
                return QMessageBox.StandardButton.Ok
            return staticmethod(f)
        setattr(QMessageBox, meth, make(meth))
    _exec = QMessageBox.exec

    def exec_(self):
        BOXES.append(("exec", (self.windowTitle() + " | " + self.text())[:300]))
        return QMessageBox.StandardButton.Ok
    QMessageBox.exec = exec_


# ---- marquee cache coherence ---------------------------------------------
def cache_state(m):
    """Force a paint (populating the cache), then compare the cache against a
    fresh recomputation from the CURRENT grid + sample fraction."""
    m.grab()
    old = getattr(m, "_cell_uv_cache", None)
    if old is None:
        return "empty"
    m._cell_uv_cache = None
    new = m._cell_uv()
    same = (old[2] == new[2] and old[0].shape == new[0].shape
            and np.array_equal(old[0], new[0]) and np.array_equal(old[1], new[1]))
    return "coherent" if same else "STALE"


def prime_cache(m):
    m.grab()


# ------------------------------------------------------------------ context
class Ctx:
    def __init__(self):
        app = QApplication.instance() or QApplication(sys.argv[:1])
        app.setApplicationName("ChromIQ")
        for fp in resource_path("assets/fonts").glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
        from ui.styles import APP_STYLESHEET
        app.setStyleSheet(APP_STYLESHEET)
        self.app = app
        from core.settings import AppSettings
        from core.argyll_runner import ArgyllRunner
        self.settings = AppSettings()
        self.settings.set("argyll_bin_path", "/Applications/Argyll/bin")
        self.settings.set("custom_output_path", str(WORK / "ChromIQ"))
        self.runner = ArgyllRunner(self.settings)
        # Record every Argyll command the WINDOW issues, without changing it.
        self.argv: list[tuple[str, list[str]]] = []
        _orig_run = ArgyllRunner.run

        def _rec(rself, tool, args, cwd, *a, **k):
            self.argv.append((tool, list(args)))
            return _orig_run(rself, tool, args, cwd, *a, **k)
        ArgyllRunner.run = _rec
        _install_msgbox_capture()
        self.new_dialog()

    def new_dialog(self):
        import ui.dialogs.scanin_dialog as sd
        self.sd = sd
        from ui.dialogs.scanin_dialog import ScannerProfileDialog
        self.dlg = ScannerProfileDialog(self.runner, self.settings, None)
        self.dlg.show(); self.dlg.raise_()
        pump(1200)
        return self.dlg

    def pick(self, method, path):
        """Run the dialog's REAL picker with only the file MODAL stubbed."""
        self.sd.open_file_dialog = lambda *a, **k: str(path)
        getattr(self.dlg, method)()
        pump(900)

    def pick_many(self, method, paths):
        self.sd.open_files_dialog = lambda *a, **k: [str(p) for p in paths]
        getattr(self.dlg, method)()
        pump(900)


# ==========================================================================
#                               THE CHECKS
# ==========================================================================
CHECKS = {}


def check(cid, name):
    def deco(fn):
        CHECKS[cid] = (name, fn)
        return fn
    return deco


def std_demo(c, key="it8Wolf", fiducials=None, sample=None):
    """Standard mode + target `key` + the app's own demo scan. Returns dlg."""
    d = c.dlg
    d._mode_standard.setChecked(True); pump(500)
    i = d._target_combo.findData(key)
    assert i >= 0, f"no target {key}"
    d._target_combo.setCurrentIndex(i); pump(700)
    click(d._demo_btn)
    pump(1500)
    if fiducials is not None:
        d._use_fiducials_cb.setChecked(fiducials); pump(500)
    if sample is not None:
        d._sample_area.setValue(sample); pump(400)
    return d


# --- J01 ------------------------------------------------------------------
@check("J01", "Window opens, both modes present, controls enumerated")
def j01(c):
    d = c.dlg
    ok = (d.windowTitle() == "Build profile with scanner or camera"
          and (d._mode_standard.isChecked() ^ d._mode_chromiq.isChecked()))
    n = d._target_combo.count()
    # every button that acts on a scan, with NO scan loaded
    dead = {b.text(): b.isEnabled() for b in
            (d._rotate_btn, d._auto_align_btn, d._reset_btn, d._reset_grid_btn,
             d._check_align_btn, d._popout_btn)}
    record("J01", "Window opens; mode radios; target list",
           "PASS" if ok and n > 1 else "FAIL",
           f"title={d.windowTitle()!r}; mode remembered={'chart' if d._mode_chromiq.isChecked() else 'standard'}; "
           f"{n} targets in the combo; run button disabled={not d._run_btn.isEnabled()}; "
           f"grid buttons enabled with NO scan loaded: {dead}",
           shot(d, "J01-window.png"))


# --- J02 ------------------------------------------------------------------
@check("J02", "Every target in the combo selects and yields a grid")
def j02(c):
    d = c.dlg
    d._mode_standard.setChecked(True); pump(400)
    bad, rows = [], []
    for i in range(d._target_combo.count()):
        key = d._target_combo.itemData(i)
        d._target_combo.setCurrentIndex(i); pump(250)
        label = d._target_combo.itemText(i)
        if not key:                           # the "Other…" entry
            rows.append((label, "other", d._cht_row_w.isVisible(),
                         d._demo_btn.isEnabled()))
            if not d._cht_row_w.isVisible() or d._demo_btn.isEnabled():
                bad.append(f"{label}: Other… row visible="
                           f"{d._cht_row_w.isVisible()} demo enabled="
                           f"{d._demo_btn.isEnabled()}")
            continue
        g = d._std_grid
        nrects = len(g.rects) if g else 0
        npages = len(d._std_chts)
        rows.append((label, key, nrects, npages))
        if nrects == 0:
            bad.append(f"{label} ({key}): grid has no cells")
    (OUT / "J02-targets.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    record("J02", "Target combo — every entry builds a grid",
           "FAIL" if bad else "PASS",
           f"{len(rows)} entries; multi-page sets: "
           + ", ".join(f"{r[0]}={r[3]}pp" for r in rows
                       if isinstance(r[3], int) and r[3] > 1)
           + ("; PROBLEMS: " + "; ".join(bad) if bad else ""))


# --- J03 ------------------------------------------------------------------
@check("J03", "Try with a demo scan (single page)")
def j03(c):
    d = std_demo(c, "it8Wolf")
    img = d._marquee.image_size()
    p = d._cur_shot()["path"]
    ok = bool(p) and Path(p).is_file() and img[0] > 0 and d._std_ref is not None
    under_home = str(p).startswith(str(Path.home() / "ChromIQ"))
    record("J03", "Try with a demo scan (single page)",
           "FAIL" if not ok or under_home else "PASS",
           f"scan={p}; ref={d._std_ref}; marquee image={img}; "
           f"grid cells={len(d._std_grid.rects)}; run enabled={d._run_btn.isEnabled()}"
           + ("; WROTE INTO ~/ChromIQ" if under_home else ""),
           shot(d, "J03-demo-loaded.png"))


# --- J04 ------------------------------------------------------------------
@check("J04", "Rotate 90 x4 returns to the start; cache stays coherent")
def j04(c):
    d = std_demo(c, "it8Wolf")
    m = d._marquee
    prime_cache(m)
    size0 = m.image_size(); q0 = m.corners_image_px()
    states, sizes = [], []
    for k in range(4):
        click(d._rotate_btn)
        states.append(cache_state(m)); sizes.append(m.image_size())
    q4 = m.corners_image_px()
    back = (m.image_size() == size0
            and max(abs(a - b) for p, r in zip(q0, q4) for a, b in zip(p, r)) < 0.5)
    swapped = sizes[0] == (size0[1], size0[0])
    bad = [s for s in states if s != "coherent"]
    record("J04", "Rotate 90°",
           "FAIL" if (not back or not swapped or bad) else "PASS",
           f"sizes {size0}->{sizes}; back to start after 4={back}; "
           f"first turn swaps w/h={swapped}; cache after each turn={states}",
           shot(d, "J04-rotate.png"))


# --- J05/J06 --------------------------------------------------------------
@check("J05", "Reset view (zoom/pan) and Reset grid")
def j05(c):
    d = std_demo(c, "it8Wolf")
    m = d._marquee
    prime_cache(m)
    m._zoom_at_centre(2.0); pump(200)
    m._pan = [40.0, -30.0]; m.update(); pump(200)
    z1, p1 = m._zoom, list(m._pan)
    click(d._reset_btn)
    z2, p2 = m._zoom, list(m._pan)
    cs_view = cache_state(m)
    # move the grid, then Reset grid
    q_seed = m.corners_image_px()
    m.set_corners([(x + 25, y + 17) for x, y in q_seed]); pump(200)
    moved = m.corners_image_px()
    click(d._reset_grid_btn)
    q_back = m.corners_image_px()
    cs_grid = cache_state(m)
    reseeded = max(abs(a - b) for p, r in zip(q_seed, q_back)
                   for a, b in zip(p, r)) < 0.5
    ok = (abs(z2 - 1.0) < 1e-9 and p2 == [0.0, 0.0] and reseeded
          and cs_view == "coherent" and cs_grid == "coherent")
    record("J05", "Reset view / Reset grid",
           "PASS" if ok else "FAIL",
           f"zoom {z1}->{z2}, pan {p1}->{p2}; grid moved by 25,17 then Reset grid "
           f"returns to the seed={reseeded}; cache after reset view={cs_view}, "
           f"after reset grid={cs_grid}",
           shot(d, "J05-reset.png"))


# --- J07 ------------------------------------------------------------------
@check("J07", "Pop out / dock back")
def j07(c):
    d = std_demo(c, "it8Wolf")
    m = d._marquee
    prime_cache(m)
    before_parent = m.parent()
    before_q = m.corners_image_px()
    click(d._popout_btn); pump(900)
    popped_parent = m.parent()
    popped_text = d._popout_btn.text()
    rot_dis = not d._rotate_btn.isEnabled()
    cs_out = cache_state(m)
    q_out = m.corners_image_px()
    click(d._popout_btn); pump(900)
    docked_parent = m.parent()
    cs_in = cache_state(m)
    q_in = m.corners_image_px()
    kept = (max(abs(a - b) for p, r in zip(before_q, q_in)
                for a, b in zip(p, r)) < 0.5)
    ok = (popped_parent is not before_parent and docked_parent is before_parent
          and "Dock" in popped_text and rot_dis and kept
          and cs_out == "coherent" and cs_in == "coherent")
    record("J07", "Pop out / dock back",
           "PASS" if ok else "FAIL",
           f"parent {type(before_parent).__name__}->{type(popped_parent).__name__}"
           f"->{type(docked_parent).__name__}; button said {popped_text!r}; "
           f"Rotate disabled while popped={rot_dis}; placement kept={kept}; "
           f"cache popped={cs_out} docked={cs_in}",
           shot(d, "J07-docked-again.png"))


# --- J08 ------------------------------------------------------------------
@check("J08", "Sample-area spinbox drives the marquee AND the cht scanin reads")
def j08(c):
    from workflow.scanin_runner import cht_with_sample_area, sample_margin
    from core.text_io import read_text
    d = std_demo(c, "it8Wolf")
    m = d._marquee
    rows, bad = [], []
    lo, hi = d._sample_area.minimum(), d._sample_area.maximum()
    rows.append(("range", lo, hi, "", ""))
    for v in (lo, 40, 60, hi):
        prime_cache(m)
        d._sample_area.setValue(v); pump(350)
        cs = cache_state(m)
        frac = m._sample_frac
        # the marquee's own inner box, for the first cell
        u, vv, w, hh = m._grid.rects[0]
        asp = m._grid.aspect or 1.0
        mg = sample_margin(w * asp, hh, frac)
        drawn_side_ratio = (w - 2 * mg / asp) / w
        rows.append((v, frac, cs, round(drawn_side_ratio, 4),
                     round(drawn_side_ratio ** 2, 4)))
        if cs != "coherent":
            bad.append(f"{v}%: cache {cs}")
        if abs(frac - v / 100.0) > 1e-9:
            bad.append(f"{v}%: marquee fraction {frac}")
    # THE BOX THE MARQUEE DRAWS vs THE BOX scanin IS ACTUALLY GIVEN
    from workflow.cht_parser import parse_cht
    txt = read_text(d._std_cht, lenient=True)
    worst = 0.0
    for v in (20, 60, 80):
        d._sample_area.setValue(v); pump(250)
        shrunk = parse_cht(cht_with_sample_area(txt, v / 100.0))
        full = parse_cht(txt)
        # the marquee's inner box for the same patches, in .cht units
        for pb, sb in zip(full.patches[:40], shrunk.patches[:40]):
            w, hh = pb.x2 - pb.x1, pb.y2 - pb.y1
            mg = sample_margin(w, hh, v / 100.0)
            want = (pb.x1 + mg, pb.y1 + mg, pb.x2 - mg, pb.y2 - mg)
            got = (sb.x1, sb.y1, sb.x2, sb.y2)
            worst = max(worst, max(abs(a - b) for a, b in zip(want, got)))
    if worst > 0.01:
        bad.append(f"marquee sample box vs the .cht handed to scanin differ by "
                   f"{worst:.4f} cht units")
    record("J08", "Sample area 10–80 %",
           "FAIL" if bad else "PASS",
           "(%, marquee frac, cache, drawn side ratio, drawn AREA ratio): "
           + str(rows) + f"; marquee box vs scanin's own .cht box: worst "
           f"disagreement {worst:.5f} cht units over 40 patches x 3 fractions"
           + ("; PROBLEMS " + "; ".join(bad) if bad else ""),
           shot(d, "J08-sample-area.png"))


# --- J09 ------------------------------------------------------------------
@check("J09", "Use fiducial marks checkbox")
def j09(c):
    d = std_demo(c, "it8Wolf")
    m = d._marquee
    prime_cache(m)
    d._use_fiducials_cb.setChecked(False); pump(500)
    q_off = m.corners_image_px(); cs_off = cache_state(m)
    f_off = m._show_fiducials
    corners_off = d._scanin_corners(q_off, d._std_cht)
    d._use_fiducials_cb.setChecked(True); pump(500)
    q_on = m.corners_image_px(); cs_on = cache_state(m)
    f_on = m._show_fiducials
    corners_on = d._scanin_corners(q_on, d._std_cht)
    moved = max(abs(a - b) for p, r in zip(q_off, q_on) for a, b in zip(p, r))
    dif = max(abs(a - b) for p, r in zip(corners_off, corners_on)
              for a, b in zip(p, r))
    iw, ih = m.image_size()
    inside = all(-2 <= x <= iw + 2 and -2 <= y <= ih + 2 for x, y in corners_on)
    ok = (f_off is False and f_on is True and cs_off == "coherent"
          and cs_on == "coherent" and inside)
    record("J09", "Use fiducial marks",
           "PASS" if ok else "FAIL",
           f"show_fiducials off/on = {f_off}/{f_on}; marquee quad moved {moved:.2f}px; "
           f"-F corners differ by {dif:.2f}px; -F corners on-image with fiducials "
           f"ON={inside} ({[(round(a,1),round(b,1)) for a,b in corners_on]}, image "
           f"{iw}x{ih}); cache off={cs_off} on={cs_on}",
           shot(d, "J09-fiducials.png"))


# --- J10/J11 --------------------------------------------------------------
def _tokens(cmd):
    return cmd.replace("\n", " ").split()


def _scanin_argv_for(c, d):
    """Run the window's own Check alignment and return the scanin argv it
    issued — the only honest way to see the flags the WINDOW builds."""
    c.argv.clear()
    seen = set(c.app.topLevelWidgets())
    click(d._check_align_btn)
    w = wait_dialog(c, seen)
    if w is not None:
        w.close(); pump(400)
    return [a for (t, a) in c.argv if "scanin" in t]


@check("J10", "The inert “Correct perspective” control is gone, and -p with it")
def j10(c):
    """B8-30. The checkbox was on screen, enabled and TICKED BY DEFAULT, and
    `scanin_args` appends `-p` only when `corners is None` — while all four of
    this window's scanin call sites pass `corners=self._scanin_corners(...)`.
    It was measured inert in beta.7 (ticked and unticked argv identical) and is
    removed in beta 8. This check proves BOTH halves: the control is not there,
    and no scanin call this window makes carries `-p`."""
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    gone = not hasattr(d, "_perspective")
    labels = [w.text() for w in d.findChildren(QCheckBox)]
    no_label = not any("perspective" in (t or "").lower() for t in labels)
    argv = _scanin_argv_for(c, d)
    hasp = [("-p" in a) for a in argv]
    hasF = [("-F" in a) for a in argv]
    ok = gone and no_label and argv and not any(hasp) and all(hasF)
    record("J10", "Correct perspective (-p)",
           "PASS" if ok else "FAIL",
           f"the checkbox is gone={gone}; no checkbox in this window still "
           f"mentions perspective={no_label} (labels={labels}); -p present per "
           f"scanin call={hasp}; -F present={hasF}. `scanin_args` suppresses "
           "-p whenever corners are given (deliberate, measured, documented in "
           "scanin_runner.py: 23.3 % of hexagonal reads FAILED with it and 42 "
           "conditions came out bit-identical without it) and all four call "
           "sites in scanin_dialog always give corners — so the control could "
           "never act. See J27 for the real BUILD's argv, which is the same.",
           shot(d, "J10-perspective.png"))


@check("J11", "Diagnostic checkbox -> -dipon, and an image is produced")
def j11(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    out = {}
    for on in (True, False):
        d._diag.setChecked(on); pump(300)
        out[on] = _scanin_argv_for(c, d)
    def dflags(v):
        return [[t for t in a if t.startswith("-d")] for a in v]
    ok = (out[True] and all(any(t == "-dipon" for t in a) for a in out[True]))
    record("J11", "Save a diagnostic image (-dipon)",
           "PASS" if ok else "FAIL",
           f"Check alignment ALWAYS asks for the diagnostic (it is what the "
           f"verdict window shows). -d flags with the box ticked={dflags(out[True])}, "
           f"unticked={dflags(out[False])}; full ticked argv: {out[True]}")


# --- J12 ------------------------------------------------------------------
def wait_align(d, secs=90):
    t0 = time.time()
    while d._align_thread is not None and time.time() - t0 < secs:
        pump(200)
    pump(400)
    return d._align_thread is None


@check("J12", "Auto align, and a second press undoes it")
def j12(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    m = d._marquee
    d._log.clear()
    before = m.corners_image_px()
    # nudge the grid so there IS something to undo to
    m.set_corners([(x + 30, y + 12) for x, y in before]); pump(300)
    start = m.corners_image_px()
    prime_cache(m)
    click(d._auto_align_btn)
    fin = wait_align(d)
    after = m.corners_image_px()
    cs = cache_state(m)
    txt = d._log.toPlainText()
    moved = max(abs(a - b) for p, r in zip(start, after) for a, b in zip(p, r))
    accepted = "Undo auto align" in d._auto_align_btn.text()
    iw, ih = m.image_size()
    onimg = all(-3 <= x <= iw + 3 and -3 <= y <= ih + 3 for x, y in after)
    scanin_c = d._scanin_corners(after, d._std_cht)
    f_onimg = all(-3 <= x <= iw + 3 and -3 <= y <= ih + 3 for x, y in scanin_c)
    shot(d, "J12-after-auto-align.png")
    # undo
    click(d._auto_align_btn); pump(600)
    undone = m.corners_image_px()
    back = max(abs(a - b) for p, r in zip(start, undone) for a, b in zip(p, r))
    ok = (fin and accepted and moved > 1 and back < 0.5 and onimg and f_onimg
          and cs == "coherent")
    record("J12", "Auto align + undo (fiducials ON)",
           "PASS" if ok else "FAIL",
           f"thread finished={fin}; accepted={accepted}; grid moved {moved:.1f}px; "
           f"result quad on the image={onimg}; the -F corners scanin would get are "
           f"on the image={f_onimg} {[(round(a,1),round(b,1)) for a,b in scanin_c]}; "
           f"undo returns to within {back:.2f}px; cache={cs}; log: "
           + " / ".join(txt.strip().splitlines()[-3:]),
           str(SHOTS / "J12-after-auto-align.png"))


# --- J13 ------------------------------------------------------------------
def wait_dialog(c, seen, secs=240):
    t0 = time.time()
    while time.time() - t0 < secs:
        pump(200)
        new = [w for w in c.app.topLevelWidgets()
               if isinstance(w, QDialog) and w not in seen and w.isVisible()]
        if new:
            pump(800)
            return new[0]
    return None


@check("J13", "Check alignment produces a verdict window")
def j13(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    d._log.clear()
    seen = set(c.app.topLevelWidgets())
    click(d._check_align_btn)
    w = wait_dialog(c, seen)
    if w is None:
        record("J13", "Check alignment", "FAIL",
               "no result window within 240 s; log: "
               + " / ".join(d._log.toPlainText().strip().splitlines()[-4:]))
        return
    from PyQt6.QtWidgets import QLabel
    texts = [l.text() for l in w.findChildren(QLabel) if l.text()]
    body = " ".join(texts)
    title = w.windowTitle()
    p = shot(w, "J13-check-alignment.png")
    w.close(); pump(400)
    ok = ("placement agreement" in body or "sample boxes" in body)
    record("J13", "Check alignment (verdict window)",
           "PASS" if ok else "FAIL",
           f"window {title!r}; verdict: {body[:400]}", p)


# --- J14 ------------------------------------------------------------------
def wait_run(d, secs=300):
    """`_finish` appends "[DONE]" on success and the failure paths log a reason,
    so the log is the honest end-of-run signal. The Run button is NOT: it stays
    disabled after a successful build until something changes."""
    t0 = time.time()
    while time.time() - t0 < secs:
        pump(300)
        txt = d._log.toPlainText()
        if "[DONE]" in txt:
            pump(800)
            return True
        if not d._busy_bar.isVisible() and time.time() - t0 > 8:
            pump(800)
            return "[DONE]" in d._log.toPlainText()
    return False


@check("J14", "Build the profile, end to end, from the demo scan")
def j14(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    d._log.clear()
    click(d._auto_align_btn); wait_align(d)
    if not d._run_btn.isEnabled():
        record("J14", "Build profile", "FAIL",
               "the Run button never enabled; can_run=%s" % d._can_run())
        return
    t0 = time.time()
    click(d._run_btn)
    fin = wait_run(d)
    dt = time.time() - t0
    txt = d._log.toPlainText()
    prof = getattr(d, "_last_profile", None)
    icc = sorted(Path(WORK / "ChromIQ" / "scanner-test-targets").glob("*.icc"))
    record("J14", "Build profile (end to end)",
           "PASS" if (fin and (prof or icc)) else "FAIL",
           f"finished={fin} in {dt:.0f}s; _last_profile={prof}; .icc files found="
           f"{[p.name for p in icc]}; reveal enabled={d._reveal_btn.isEnabled()}; "
           f"install enabled={d._install_btn.isEnabled()}; log tail: "
           + " / ".join(txt.strip().splitlines()[-6:]),
           shot(d, "J14-after-build.png"))


# --- J15 ------------------------------------------------------------------
@check("J15", "Averaging: add / remove a scan, and the method combo")
def j15(c):
    d = std_demo(c, "it8Wolf")
    first = d._cur_shot()["path"]
    n0 = len(d._page_shots())
    click(d._add_shot_btn); pump(500)
    n1 = len(d._page_shots())
    combo_on = d._shot_combo.isEnabled() and d._avg_method.isEnabled()
    can_run_empty = d._can_run()
    # give the second shot the same demo file
    c.pick("_pick_scan", first)
    n_paths = sum(1 for s in d._page_shots() if s["path"])
    can_run_full = d._can_run()
    methods = [d._avg_method.itemText(i) for i in range(d._avg_method.count())]
    # switch between shots — the placement must be per shot
    d._shot_combo.setCurrentIndex(0); pump(400)
    q0 = d._marquee.corners_image_px()
    d._shot_combo.setCurrentIndex(1); pump(400)
    d._marquee.set_corners([(x + 40, y) for x, y in d._marquee.corners_image_px()])
    d._capture_current_corners(); pump(200)
    d._shot_combo.setCurrentIndex(0); pump(400)
    q0b = d._marquee.corners_image_px()
    per_shot = max(abs(a - b) for p, r in zip(q0, q0b) for a, b in zip(p, r)) < 0.5
    click(d._remove_shot_btn); pump(500)
    n2 = len(d._page_shots())
    ok = (n1 == n0 + 1 and n2 == n1 - 1 and combo_on and n_paths == 2
          and can_run_full and per_shot and len(methods) == 3)
    record("J15", "Averaging (add / remove / method)",
           "PASS" if ok else "FAIL",
           f"shots {n0}->{n1}->{n2}; shot+method combos enabled once a 2nd scan "
           f"is added={combo_on}; can_run with an EMPTY 2nd slot={can_run_empty} "
           f"(should be False); with both filled={can_run_full}; per-shot placement "
           f"kept={per_shot}; methods={methods}",
           shot(d, "J15-averaging.png"))


# --- J16 ------------------------------------------------------------------
@check("J16", "Multi-page set: a demo per page, per-page grid and placement")
def j16(c):
    d = c.dlg
    d._mode_standard.setChecked(True); pump(400)
    key = None
    for i in range(d._target_combo.count()):
        k = d._target_combo.itemData(i)
        if not k:
            continue
        d._target_combo.setCurrentIndex(i); pump(200)
        if len(d._std_chts) > 1:
            key = k
            break
    if key is None:
        record("J16", "Multi-page set", "UNTESTED", "no multi-page target in the combo")
        return
    click(d._demo_btn); pump(2500)
    pages = list(d._pages)
    per_page = []
    for pg in pages:
        d._page_combo.setCurrentIndex(pg); pump(700)
        sh = d._cur_shot()
        per_page.append((pg, str(sh["path"] or "")[-28:],
                         len(d._marquee._grid.rects), d._std_cht.name,
                         cache_state(d._marquee)))
    # move page 1's grid, go away and come back
    d._page_combo.setCurrentIndex(0); pump(500)
    q = d._marquee.corners_image_px()
    d._marquee.set_corners([(x + 33, y + 7) for x, y in q]); d._capture_current_corners()
    pump(300)
    d._page_combo.setCurrentIndex(1); pump(600)
    d._page_combo.setCurrentIndex(0); pump(600)
    q2 = d._marquee.corners_image_px()
    kept = max(abs((a + (33 if i % 2 == 0 else 7)) - b)
               for p, r in zip(q, q2) for i, (a, b) in enumerate(zip(p, r))) < 0.5
    distinct = len({r[1] for r in per_page}) == len(pages)
    chts = len({r[3] for r in per_page}) == len(pages)
    bad = [r for r in per_page if r[2] == 0 or r[4] != "coherent"]
    record("J16", "Multi-page set",
           "FAIL" if (bad or not distinct or not chts or not kept) else "PASS",
           f"target={key}; {len(pages)} pages; (page, scan, cells, cht, cache)="
           f"{per_page}; a different demo scan per page={distinct}; a different "
           f".cht per page={chts}; placement survives a page round trip={kept}",
           shot(d, "J16-multipage.png"))


# --- J17 ------------------------------------------------------------------
@check("J17", "Other… (.cht) — a target file the app does not bundle")
def j17(c):
    d = c.dlg
    d._mode_standard.setChecked(True); pump(400)
    i = d._target_combo.findData("")
    if i < 0:
        i = d._target_combo.count() - 1
    d._target_combo.setCurrentIndex(i); pump(500)
    row_shown = d._cht_row_w.isVisible()
    demo_off = not d._demo_btn.isEnabled()
    # Argyll's own copy of a target ChromIQ does NOT bundle
    cand = Path("/Applications/Argyll/ref/ColorChecker.cht")
    if not cand.is_file():
        record("J17", "Other… (.cht)", "UNTESTED", f"{cand} not present")
        return
    c.pick("_pick_cht", cand)
    cells = len(d._std_grid.rects) if d._std_grid else 0
    click(d._demo_btn); pump(2000)
    demo_enabled_now = d._demo_btn.isEnabled()
    got_scan = bool(d._cur_shot()["path"])
    record("J17", "Other… (.cht)",
           "PASS" if (row_shown and demo_off and cells > 0) else "FAIL",
           f"the .cht row appears={row_shown}; “Try with a demo scan” disabled for "
           f"Other…={demo_off}; after picking {cand.name} the grid has {cells} cells; "
           f"demo button enabled after the pick={demo_enabled_now}; demo scan "
           f"loaded={got_scan}",
           shot(d, "J17-other-cht.png"))


# --- J18 ------------------------------------------------------------------
@check("J18", "Save as Defaults / Restore defaults")
def j18(c):
    d = std_demo(c, "it8Wolf")
    d._sample_area.setValue(35)
    d._use_fiducials_cb.setChecked(True)
    d._diag.setChecked(True)
    d._ptype.setCurrentIndex(1)
    pump(400)
    want = (35, True, True, d._ptype.currentText())
    click(d._save_defaults_btn); pump(600)
    d.close(); pump(300)
    d = c.new_dialog()
    d._mode_standard.setChecked(True); pump(400)
    # …AND THE TARGET, because "Use fiducial marks" is unticked for a target
    # that has none: the honest round trip is the one a user makes.
    _target(d, "it8Wolf"); pump(400)
    got = (d._sample_area.value(), d._use_fiducials_cb.isChecked(),
           d._diag.isChecked(), d._ptype.currentText())
    saved_ok = got == want
    click(d._restore_defaults_btn); pump(800)
    after = (d._sample_area.value(), d._use_fiducials_cb.isChecked(),
             d._diag.isChecked(), d._ptype.currentText())
    restored = after != want
    record("J18", "Save as Defaults / Restore defaults",
           "PASS" if (saved_ok and restored) else "FAIL",
           f"set {want}; after Save-as-Defaults + reopen got {got} (kept={saved_ok}); "
           f"after Restore defaults {after} (changed back={restored}); "
           f"message boxes seen: {BOXES}",
           shot(d, "J18-defaults.png"))


# --- J19 ------------------------------------------------------------------
@check("J19", "Close the window mid-run")
def j19(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    click(d._auto_align_btn); wait_align(d)
    if not d._run_btn.isEnabled():
        record("J19", "Close mid-run", "UNTESTED", "run never enabled")
        return
    click(d._run_btn); pump(2500)
    running = d._busy_bar.isVisible() or not d._run_btn.isEnabled()
    d.close(); pump(1500)
    alive = QApplication.instance() is not None
    still = getattr(d, "_align_thread", None)
    pump(3000)
    record("J19", "Close the window mid-run",
           "PASS" if (running and alive) else "FAIL",
           f"a build was in flight when Close was pressed={running}; the app "
           f"survived the close={alive}; align thread left behind={still}; "
           f"boxes: {BOXES}")


# --- J20 ------------------------------------------------------------------
@check("J20", "Printer mode (scanner as the measuring device)")
def j20(c):
    d = c.dlg
    d._mode_chromiq.setChecked(True); pump(500)
    was = d._printer_cb.isEnabled()
    d._printer_cb.setChecked(True); pump(600)
    label = d._chart_label.text()
    prof_row = d._printer_prof_field.isVisible()
    d._printer_cb.setChecked(False); pump(400)
    label_off = d._chart_label.text()
    record("J20", "Printer mode toggle",
           "PASS" if (label != label_off and prof_row) else "FAIL",
           f"the printer checkbox is enabled in ChromIQ-chart mode={was}; the chart "
           f"row is labelled {label!r} with printer mode on and {label_off!r} with "
           f"it off; the scanner-profile row appears={prof_row}",
           shot(d, "J20-printer-mode.png"))


CHART = Path("/private/tmp/agentJ/charts/Knut-Scanner")


def chromiq_chart(c, page=0):
    d = c.dlg
    d._mode_chromiq.setChecked(True); pump(500)
    c.pick("_pick_chart", CHART / "Knut-Scanner.ti3")
    pump(800)
    if d._page_combo.count() > page:
        d._page_combo.setCurrentIndex(page); pump(500)
    c.pick("_pick_scan", CHART / f"Knut-Scanner_{page + 1:02d}.tif")
    pump(1200)
    return d


# --- J21 ------------------------------------------------------------------
@check("J21", "ChromIQ-chart mode: real 3-page chart, grid, pages, align, check")
def j21(c):
    d = chromiq_chart(c, 0)
    pages = list(d._pages)
    cells = len(d._marquee._grid.rects)
    img = d._marquee.image_size()
    cs = cache_state(d._marquee)
    per_page = []
    for pg in pages:
        d._page_combo.setCurrentIndex(pg); pump(500)
        if not d._cur_shot()["path"]:
            c.pick("_pick_scan", CHART / f"Knut-Scanner_{pg + 1:02d}.tif")
        per_page.append((pg, len(d._marquee._grid.rects),
                         d._marquee.image_size(), cache_state(d._marquee)))
    d._page_combo.setCurrentIndex(0); pump(400)
    d._log.clear()
    click(d._auto_align_btn); fin = wait_align(d)
    align_log = " / ".join(d._log.toPlainText().strip().splitlines()[-2:])
    accepted = "Undo auto align" in d._auto_align_btn.text()
    ok = (len(pages) == 3 and cells > 0 and img[0] > 0
          and all(r[1] > 0 for r in per_page) and cs == "coherent")
    record("J21", "ChromIQ-chart mode (real 3-page chart)",
           "PASS" if ok else "FAIL",
           f"chart={d._ti3.name if d._ti3 else None}; pages={pages}; grid cells "
           f"page1={cells}; scan {img}; per page (pg, cells, image, cache)="
           f"{per_page}; Auto align finished={fin}, accepted={accepted}: "
           f"{align_log}",
           shot(d, "J21-chromiq-chart.png"))


# --- J22 ------------------------------------------------------------------
@check("J22", "Check alignment + build in ChromIQ-chart mode")
def j22(c):
    d = chromiq_chart(c, 0)
    d._log.clear()
    click(d._auto_align_btn); wait_align(d)
    seen = set(c.app.topLevelWidgets())
    click(d._check_align_btn)
    w = wait_dialog(c, seen)
    verdict = ""
    if w is not None:
        from PyQt6.QtWidgets import QLabel
        verdict = " ".join(l.text() for l in w.findChildren(QLabel) if l.text())
        shot(w, "J22-chromiq-check.png")
        w.close(); pump(400)
    can = d._can_run()
    record("J22", "Check alignment (ChromIQ chart)",
           "PASS" if (w is not None and verdict) else "FAIL",
           f"verdict: {verdict[:320]}; can_run with only page 1 loaded={can} "
           f"(3 pages exist, 2 have no scan)")


# --- J23 ------------------------------------------------------------------
@check("J23", "Sample-area cap does not leak from one chart/mode to the next")
def j23(c):
    d = c.dlg
    d._mode_standard.setChecked(True); pump(400)
    i = d._target_combo.findData("it8Wolf"); d._target_combo.setCurrentIndex(i)
    pump(400)
    std_max_before = d._sample_area.maximum()
    d = chromiq_chart(c, 0)
    chart_max = d._sample_area.maximum()
    d._mode_standard.setChecked(True); pump(600)
    std_max_after = d._sample_area.maximum()
    record("J23", "Sample-area maximum across mode changes",
           "PASS" if std_max_after == std_max_before else "FAIL",
           f"standard-mode maximum before={std_max_before}%, ChromIQ chart "
           f"maximum={chart_max}%, standard-mode maximum after switching "
           f"back={std_max_after}% (a hexagonal chart caps it lower; the cap "
           f"must not survive into a bought target)")


# --- J24 ------------------------------------------------------------------
@check("J24", "Knut's own Wolf Faust and LaserSoft scans, end to end")
def j24(c):
    rows = []
    cases = [("it8Wolf", KNUT / "ScannedTargetIT8-ISO12641-1-2025-10-07-21-30-01.tif",
              KNUT / "Scanner Calibration Files"),
             ("ISO12641_2_1", KNUT / "ScannedTargetIT8-ISO12641-2-2025-10-08-12-51-01.tif",
              KNUT / "R250715.cie")]
    for key, scan, ref in cases:
        if not scan.is_file():
            rows.append((key, "UNTESTED", f"{scan.name} missing"))
            continue
        refp = ref
        if ref.is_dir():
            cand = sorted(ref.rglob("R*.txt"))
            refp = cand[0] if cand else None
        if refp is None or not refp.is_file():
            rows.append((key, "UNTESTED", "no reference file found"))
            continue
        d = c.new_dialog()
        d._mode_standard.setChecked(True); pump(400)
        i = d._target_combo.findData(key); d._target_combo.setCurrentIndex(i)
        pump(500)
        c.pick("_pick_ref", refp)
        c.pick("_pick_scan", scan)
        d._use_fiducials_cb.setChecked(True)
        d._sample_area.setValue(60); pump(400)
        d._log.clear()
        t0 = time.time()
        click(d._auto_align_btn); fin = wait_align(d)
        dt = time.time() - t0
        accepted = "Undo auto align" in d._auto_align_btn.text()
        log = " / ".join(d._log.toPlainText().strip().splitlines()[-2:])
        q = d._marquee.corners_image_px()
        iw, ih = d._marquee.image_size()
        fcorn = d._scanin_corners(q, d._std_cht)
        onimg = all(-3 <= x <= iw + 3 and -3 <= y <= ih + 3 for x, y in fcorn)
        shot(d, f"J24-{key}-aligned.png")
        seen = set(c.app.topLevelWidgets())
        click(d._check_align_btn)
        w = wait_dialog(c, seen)
        verdict = ""
        if w is not None:
            from PyQt6.QtWidgets import QLabel
            verdict = " ".join(l.text() for l in w.findChildren(QLabel) if l.text())
            shot(w, f"J24-{key}-check.png")
            w.close(); pump(400)
        rows.append((key, "PASS" if (fin and accepted and onimg) else "FAIL",
                     f"{dt:.1f}s accepted={accepted} -F on image={onimg} "
                     f"| {log} | verdict: {verdict[:260]}"))
    bad = [r for r in rows if r[1] == "FAIL"]
    record("J24", "Knut's own scans (auto align + check alignment)",
           "FAIL" if bad else ("UNTESTED" if all(r[1] == "UNTESTED" for r in rows)
                               else "PASS"),
           " ;; ".join(f"{r[0]}: {r[1]} — {r[2]}" for r in rows))


# --- J25 ------------------------------------------------------------------
@check("J25", "Demo framing: is the SEEDED grid on the patches any more?")
def j25(c):
    """The demo generator now paints a sheet on a platen, so the image is bigger
    than the patch block and the block is off-centre. The marquee seeds a quad at
    90 % of the IMAGE. Measure the gap, and what Check alignment says about it
    straight after the button that produced it."""
    from workflow.standard_targets import demo_scan_layout
    from workflow.cht_parser import parse_cht
    from core.text_io import read_text
    rows = []
    for key in ("it8Wolf", "ColorChecker", "ISO12641_2_1", "SpyderChecker24"):
        d = c.new_dialog()
        i = d._target_combo.findData(key)
        if i < 0:
            rows.append((key, "no such target")); continue
        d._mode_standard.setChecked(True); pump(300)
        d._target_combo.setCurrentIndex(i); pump(400)
        click(d._demo_btn); pump(2000)
        m = d._marquee
        if not m.image_size()[0]:
            rows.append((key, "no demo scan")); continue
        text = read_text(d._std_cht, lenient=True)
        boxes = parse_cht(text).patches
        (scale, px0, py0, pw, ph, W, H, sheet_rect, sheet) = \
            demo_scan_layout(text, boxes)
        truth = [(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)]
        seed = m.corners_image_px()
        off = max(abs(a - b) for p, r in zip(truth, seed) for a, b in zip(p, r))
        pitch = min(b.x2 - b.x1 for b in boxes) * scale
        rows.append((key, f"image {W}x{H}, patch block {int(pw)}x{int(ph)} at "
                          f"({int(px0)},{int(py0)}), sheet painted={sheet}; the "
                          f"SEEDED quad is {off:.0f} px = {off / pitch:.2f} patch "
                          f"pitches from the patch block"))
    record("J25", "Demo framing vs the seeded grid",
           "PASS", "; ".join(f"{k}: {v}" for k, v in rows))


# --- J26 ------------------------------------------------------------------
@check("J26", "Marquee geometry cache — every path that can move the grid")
def j26(c):
    d = std_demo(c, "it8Wolf")
    m = d._marquee
    res = {}

    def step(name, fn):
        prime_cache(m)
        fn()
        pump(300)
        res[name] = cache_state(m)

    step("drag a corner", lambda: _drag_corner(m))
    step("nudge with the keyboard", lambda: _key(m))
    step("zoom", lambda: m._zoom_at_centre(1.8))
    step("pan", lambda: setattr(m, "_pan", [22.0, 9.0]))
    step("resize the widget", lambda: m.resize(m.width() - 40, m.height() - 30))
    step("rotate 90", lambda: click(d._rotate_btn))
    step("reset view", lambda: click(d._reset_btn))
    step("reset grid", lambda: click(d._reset_grid_btn))
    step("sample area 20", lambda: d._sample_area.setValue(20))
    step("sample area 80", lambda: d._sample_area.setValue(80))
    step("fiducials on", lambda: d._use_fiducials_cb.setChecked(True))
    step("fiducials off", lambda: d._use_fiducials_cb.setChecked(False))
    step("pop out", lambda: click(d._popout_btn))
    step("dock back", lambda: click(d._popout_btn))
    step("change target", lambda: _other_target(d))
    step("demo scan for the new target", lambda: click(d._demo_btn))
    step("change target back", lambda: _target(d, "it8Wolf"))
    step("demo scan again", lambda: click(d._demo_btn))
    step("auto align", lambda: (click(d._auto_align_btn), wait_align(d)))
    step("undo auto align", lambda: (click(d._auto_align_btn), pump(600)))
    # "empty" = the marquee has no scan, so nothing is cached and nothing can be
    # stale. Only a cache that DISAGREES with a fresh recomputation is a fault.
    bad = {k: v for k, v in res.items() if v == "STALE"}
    scan_dropped = res.get("change target") == "empty"
    record("J26", "Marquee cell-geometry cache invalidation",
           "FAIL" if bad else "PASS",
           "after each action the cached cell geometry was compared with a fresh "
           "recomputation from the CURRENT grid + sample fraction: " + str(res)
           + ("; STALE AFTER: " + str(bad) if bad else "; no path leaves a stale cache")
           + (". NOTE: changing the Target type DISCARDS the loaded scan "
              "(marquee goes empty)." if scan_dropped else ""))


def _drag_corner(m):
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent
    pos = m._handle_pos(0)
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(pos),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier)
    m.mousePressEvent(ev)
    ev2 = QMouseEvent(QEvent.Type.MouseMove, QPointF(pos.x() + 18, pos.y() + 11),
                      Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                      Qt.KeyboardModifier.NoModifier)
    m.mouseMoveEvent(ev2)
    m.grab()                       # a paint DURING the drag
    ev3 = QMouseEvent(QEvent.Type.MouseButtonRelease,
                      QPointF(pos.x() + 18, pos.y() + 11),
                      Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                      Qt.KeyboardModifier.NoModifier)
    m.mouseReleaseEvent(ev3)


def _key(m):
    QTest.keyClick(m, Qt.Key.Key_Right)
    QTest.keyClick(m, Qt.Key.Key_Down)


def _target(d, key):
    i = d._target_combo.findData(key)
    d._target_combo.setCurrentIndex(i)


def _other_target(d):
    _target(d, "SpyderChecker24")


# --- J27 ------------------------------------------------------------------
@check("J27", "What the BUILD actually sends to scanin (-F, -p, -dipon, cht)")
def j27(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    click(d._auto_align_btn); wait_align(d)
    d._diag.setChecked(True); pump(300)
    c.argv.clear()
    click(d._run_btn)
    wait_run(d)
    scan_calls = [a for (t, a) in c.argv if "scanin" in t]
    colprof = [a for (t, a) in c.argv if "colprof" in t]
    flags = [[t for t in a if t.startswith("-")] for a in scan_calls]
    record("J27", "The real build's scanin command line",
           "PASS" if scan_calls else "FAIL",
           f"{len(scan_calls)} scanin call(s), flags={flags}; colprof calls="
           f"{len(colprof)}; full first scanin argv={scan_calls[0] if scan_calls else None}")


# --- J28 ------------------------------------------------------------------
@check("J28", "Demo scan -> Auto align -> Check alignment, several targets")
def j28(c):
    """The journey the demo button exists for, on the app's own material. A
    demo is the only case where the truth is known, so a verdict of anything
    but 'the grid is on the patches' here is a fault in the tool, not the
    scan."""
    from workflow.standard_targets import demo_scan_layout
    from workflow.cht_parser import parse_cht
    from core.text_io import read_text
    from PyQt6.QtWidgets import QLabel
    targets = ["it8Wolf", "ISO12641_2_1", "ColorChecker", "ColorCheckerSG",
               "SpyderChecker24", "QPcard_202", "Hutchcolor",
               "CMP_Digital_Target_Studio"]
    rows, bad = [], []
    for key in targets:
        d = c.new_dialog()
        i = d._target_combo.findData(key)
        if i < 0:
            rows.append((key, "SKIP", "not in the combo", "")); continue
        d._mode_standard.setChecked(True); pump(300)
        d._target_combo.setCurrentIndex(i); pump(400)
        click(d._demo_btn); pump(2000)
        if not d._marquee.image_size()[0]:
            rows.append((key, "SKIP", "no demo scan", "")); continue
        fid = d._use_fiducials_cb.isEnabled() and d._use_fiducials_cb.isVisible()
        if fid:
            d._use_fiducials_cb.setChecked(True); pump(300)
        d._sample_area.setValue(60); pump(200)
        d._log.clear()
        click(d._auto_align_btn); wait_align(d)
        accepted = "Undo auto align" in d._auto_align_btn.text()
        # ground truth from the generator itself
        text = read_text(d._std_cht, lenient=True)
        boxes = parse_cht(text).patches
        (scale, px0, py0, pw, ph, W, H, _sr, _sh) = demo_scan_layout(text, boxes)
        truth = [(px0, py0), (px0 + pw, py0), (px0 + pw, py0 + ph), (px0, py0 + ph)]
        q = d._marquee.corners_image_px()
        err = max(abs(a - b) for p, r in zip(truth, q) for a, b in zip(p, r))
        pitch = min(b.x2 - b.x1 for b in boxes) * scale
        seen = set(c.app.topLevelWidgets())
        click(d._check_align_btn)
        w = wait_dialog(c, seen)
        verdict = ""
        if w is not None:
            verdict = " ".join(l.text() for l in w.findChildren(QLabel) if l.text())
            shot(w, f"J28-{key}-check.png")
            w.close(); pump(300)
        good = ("⚠" not in verdict) and verdict != ""
        # THE CHECK IS ON THE OUTCOME, NOT ON WHICH BUTTON MOVED THE GRID
        # (B8-40, settled by B8-42). This used to require `accepted` — that the
        # placement button had MOVED the grid — and two of beta 8's fixes made
        # that the wrong question on purpose: the demo now paints the sheet, so
        # its seeded grid opens 1 px (0.02 of a patch pitch) from the patch
        # block, and B8-28 stopped the recogniser treating the app's own seed
        # as a rival while leaving it free to decline a placement it cannot
        # improve. Declining there is the CORRECT answer and Check alignment
        # says so, and a demo scan that ended on the patches was being reported
        # as a fault. What this check exists for is in its own docstring: "a
        # verdict of anything but 'the grid is on the patches' here is a fault
        # in the tool". So that is what it asks — by whichever route, including
        # no route at all. Written this way it would have passed before the
        # change and after it, which is what a regression check is for.
        # `accepted` is still REPORTED, so nothing is hidden by not asserting it.
        on_patches = pitch > 0 and (err / pitch) <= 0.25
        rows.append((key, "ok" if (on_patches and good) else "PROBLEM",
                     f"fid={d._use_fiducials_cb.isChecked()} accepted={accepted} "
                     f"err={err:.0f}px ({err / pitch:.2f} pitch)",
                     verdict[:220]))
        if not (on_patches and good):
            bad.append(key)
    (OUT / "J28-targets.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    record("J28", "Demo -> Auto align -> Check alignment",
           "FAIL" if bad else "PASS",
           "; ".join(f"{r[0]}: {r[1]} [{r[2]}] {r[3]}" for r in rows))


# --- J29 ------------------------------------------------------------------
@check("J29", "Crossed options: fiducials x sample area x page, on one target")
def j29(c):
    """Basti's rule: one option at a time proves nothing about pairs. The cross
    is over what this session changed — fiducials (the double-extrapolation
    fix), the sample area (the marquee cache), and the page (the multi-page
    .cht swap)."""
    from PyQt6.QtWidgets import QLabel
    rows, bad = [], []
    for key, pages in (("it8Wolf", [0]), ("ISO12641_2_3", [0, 2])):
        for fid in (False, True):
            for sa in (20, 60, 80):
                for pg in pages:
                    # START FROM THE SEED EVERY TIME. The window remembers the
                    # last ACCEPTED placement per target (`scanin_grid_placements`,
                    # written by `_remember_accepted_placement` after a build) and
                    # restores it when a scan of that target is loaded. That is
                    # correct behaviour and it makes Auto align rightly answer
                    # "no better" — but it also means a sweep that has already
                    # built once is no longer testing the fresh case. Clearing it
                    # makes each combination start where a new user starts.
                    c.settings.set("scanin_grid_placements", {})
                    d = c.new_dialog()
                    i = d._target_combo.findData(key)
                    if i < 0:
                        continue
                    d._mode_standard.setChecked(True); pump(250)
                    d._target_combo.setCurrentIndex(i); pump(400)
                    click(d._demo_btn); pump(2200)
                    if d._page_combo.count() > pg:
                        d._page_combo.setCurrentIndex(pg); pump(500)
                    avail = d._use_fiducials_cb.isEnabled()
                    d._use_fiducials_cb.setChecked(fid and avail); pump(250)
                    d._sample_area.setValue(sa); pump(250)
                    d._log.clear()
                    click(d._auto_align_btn); wait_align(d)
                    # The button text only becomes "Undo auto align" when there
                    # was a previous placement to undo TO, so it is not a proxy
                    # for acceptance. The log line is.
                    lg = d._log.toPlainText()
                    acc = "put the grid on the patches" in lg
                    q = d._marquee.corners_image_px()
                    iw, ih = d._marquee.image_size()
                    fc = d._scanin_corners(q, d._std_cht)
                    onimg = all(-3 <= x <= iw + 3 and -3 <= y <= ih + 3
                                for x, y in fc)
                    seen = set(c.app.topLevelWidgets())
                    click(d._check_align_btn)
                    w = wait_dialog(c, seen)
                    verdict = ""
                    if w is not None:
                        verdict = " ".join(l.text() for l in
                                           w.findChildren(QLabel) if l.text())
                        w.close(); pump(250)
                    good = verdict and "⚠" not in verdict
                    tag = f"{key} fid={fid and avail} sa={sa} pg={pg + 1}"
                    rows.append((tag, acc, onimg, bool(good), verdict[:150]))
                    # What must hold: the grid ends ON the patches and the -F
                    # corners are on the image. Whether Auto align MOVED it is
                    # recorded but is not the criterion — a restored placement
                    # that is already right makes "no better" the right answer.
                    if not (onimg and good):
                        bad.append(tag)
                    if not acc:
                        bad.append(tag + " (auto align did not place it)")
                    cache = cache_state(d._marquee)
                    if cache == "STALE":
                        bad.append(tag + " STALE CACHE")
    (OUT / "J29-cross.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    record("J29", "Crossed: fiducials x sample area x page",
           "FAIL" if bad else "PASS",
           f"{len(rows)} combinations driven end to end (Auto align + Check "
           f"alignment each time). Failing: {bad or 'none'}. "
           + " ;; ".join(f"{r[0]} accepted={r[1]} -F on image={r[2]} check-OK={r[3]}"
                         for r in rows))


# --- J30 ------------------------------------------------------------------
WFREF = (KNUT / "Scanner Calibration Files"
         / "Matrix-Shaper Profile Created for Scanner (high resolution)"
         / "R230122W.txt")


@check("J30", "The untouched SEED quad vetoes the recogniser on Knut's real scan")
def j30(c):
    """Auto align compares its candidate against `rho_before` — the agreement of
    the quad already on screen — and refuses anything less than
    IMPROVEMENT_MARGIN better. On a fresh scan that quad is the marquee's own
    SEED, which nobody placed. This measures both placements with the window's
    own Check alignment."""
    from PyQt6.QtWidgets import QLabel
    scan = KNUT / "ScannedTargetIT8-ISO12641-1-2025-10-07-21-30-01.tif"
    if not scan.is_file() or not WFREF.is_file():
        record("J30", "Seed vetoes the recogniser", "UNTESTED", "Knut's files absent")
        return
    d = c.new_dialog()
    d._mode_standard.setChecked(True); pump(300)
    d._target_combo.setCurrentIndex(d._target_combo.findData("it8Wolf")); pump(400)
    c.pick("_pick_ref", WFREF)
    c.pick("_pick_scan", scan)
    d._use_fiducials_cb.setChecked(True); d._sample_area.setValue(60); pump(400)
    seed = d._marquee.corners_image_px()

    def verdict(tag):
        seen = set(c.app.topLevelWidgets())
        click(d._check_align_btn)
        w = wait_dialog(c, seen)
        v = ""
        if w is not None:
            v = " ".join(l.text() for l in w.findChildren(QLabel) if l.text())
            shot(w, f"J30-{tag}.png")
            w.close(); pump(300)
        return v

    v_seed = verdict("seed")
    d._log.clear()
    click(d._auto_align_btn); wait_align(d)
    said = " / ".join(d._log.toPlainText().strip().splitlines()[-2:])
    after = d._marquee.corners_image_px()
    stayed = max(abs(a - b) for p, r in zip(seed, after) for a, b in zip(p, r)) < 0.5
    # now put the recogniser's OWN answer in by hand and ask again
    from workflow.scan_auto_align import auto_align, expected_luminance
    from workflow.cht_parser import parse_cht
    from core.text_io import read_text
    from core.resource_path import argyll_binary
    text = read_text(d._std_cht, lenient=True)
    boxes = parse_cht(text).patches
    exp = expected_luminance(text, d._std_ref, chart_ids=[b.name for b in boxes])
    exe = str(Path(d._settings.get("argyll_bin_path")) / argyll_binary("scanin"))
    r = auto_align(exe, scan, d._std_cht, d._std_ref, boxes, exp,
                   d._marquee.image_size(), current_corners=None, sample_frac=0.6)
    v_found = ""
    if r is not None and r.corners:
        d._marquee.set_corners([tuple(x) for x in r.corners])
        d._capture_current_corners(); pump(400)
        shot(d, "J30-recogniser-quad.png")
        v_found = verdict("recogniser-quad")
    off = (max(abs(a - b) for p, q in zip(seed, r.corners) for a, b in zip(p, q))
           if r and r.corners else None)
    record("J30", "The untouched seed vetoes the recogniser (Knut's WF scan)",
           "FAIL" if stayed else "PASS",
           f"Auto align kept the seed={stayed}; it said: {said}. "
           f"Check alignment AT THE SEED: {v_seed[:200]} ||| the recogniser's own "
           f"answer scores rho={getattr(r, 'rho', None)} vs the seed's "
           f"rho_before, is {off:.0f} px away, and Check alignment there says: "
           f"{v_found[:200]}",
           str(SHOTS / "J30-recogniser-quad.png"))


# --- J31 ------------------------------------------------------------------
@check("J31", "Printer mode end to end: the scanner IS the instrument")
def j31(c):
    icc = CHART / "Knut-Scanner-scanner.icc"
    if not icc.is_file():
        record("J31", "Printer mode end to end", "UNTESTED",
               "no scanner ICC to hand")
        return
    d = c.dlg
    d._mode_chromiq.setChecked(True); pump(400)
    d._printer_cb.setChecked(True); pump(500)
    c.pick("_pick_chart", CHART / "Knut-Scanner.ti2")
    pump(700)
    c.pick("_pick_scanner_profile", icc)
    pump(400)
    pages = list(d._pages)
    for pg in pages:
        d._page_combo.setCurrentIndex(pg); pump(400)
        c.pick("_pick_scan", CHART / f"Knut-Scanner_{pg + 1:02d}.tif")
        pump(700)
        click(d._auto_align_btn); wait_align(d)
    can = d._can_run()
    d._log.clear()
    if can:
        c.argv.clear()
        click(d._run_btn)
        fin = wait_run(d, 420)
    else:
        fin = False
    tail = " / ".join(d._log.toPlainText().strip().splitlines()[-5:])
    calls = [(t, [a for a in args if a.startswith("-")]) for t, args in c.argv]
    record("J31", "Printer mode end to end",
           "PASS" if (can and fin) else "FAIL",
           f"chart row label={d._chart_label.text()!r}; scanner ICC={icc.name}; "
           f"{len(pages)} pages each with a scan; can_run={can}; build "
           f"finished={fin}; Argyll calls={calls}; log tail: {tail}",
           shot(d, "J31-printer-mode.png"))


# --- J32 ------------------------------------------------------------------
@check("J32", "An EMPTY averaging slot: what does the build actually read?")
def j32(c):
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    click(d._auto_align_btn); wait_align(d)
    click(d._add_shot_btn); pump(600)          # a second slot, left EMPTY
    n = len(d._page_shots())
    filled = sum(1 for s in d._page_shots() if s["path"])
    can = d._can_run()
    d._log.clear()
    c.argv.clear()
    fin = False
    if can:
        click(d._run_btn)
        fin = wait_run(d, 300)
    scanin_calls = [a for (t, a) in c.argv if "scanin" in t]
    avg = [t for (t, a) in c.argv if "average" in t.lower()]
    txt = d._log.toPlainText()
    warned = any(w in txt.lower() for w in ("ignored", "empty", "only one",
                                            "second scan", "no scan"))
    record("J32", "Averaging with an empty second slot",
           "FAIL" if (can and not warned) else "PASS",
           f"{n} shot slots, {filled} with a file; can_run={can}; build "
           f"finished={fin}; {len(scanin_calls)} scanin call(s) — one per scan "
           f"actually read; averaging step run={bool(avg)}; anything said about "
           f"the empty slot={warned}; log: "
           + " / ".join(txt.strip().splitlines()[-6:]),
           shot(d, "J32-empty-average-slot.png"))


# --- J33 ------------------------------------------------------------------
@check("J33", "ChromIQ's warning sign renders in all three appearances")
def j33(c):
    from ui.warning_sign import warning_colours, warning_pixmap
    rows, bad = [], []
    imgs = {}
    for mode in ("light", "dark", "neutral"):
        fill, mark = warning_colours(mode)
        px = warning_pixmap(48, mode, 2.0)
        img = px.toImage()
        imgs[mode] = img
        w, h = img.width(), img.height()
        opaque = sum(1 for y in range(0, h, 2) for x in range(0, w, 2)
                     if img.pixelColor(x, y).alpha() > 200)
        total = len(range(0, h, 2)) * len(range(0, w, 2))
        # the mark must actually be cut into the fill
        cols = {img.pixelColor(x, y).name()
                for y in range(0, h, 2) for x in range(0, w, 2)
                if img.pixelColor(x, y).alpha() > 200}
        rows.append((mode, fill, mark, f"{opaque}/{total} opaque",
                     f"{len(cols)} distinct colours"))
        img.save(str(SHOTS / f"J33-warning-sign-{mode}.png"))
        if opaque < 0.25 * total:
            bad.append(f"{mode}: the sign is nearly transparent")
        if len(cols) < 2:
            bad.append(f"{mode}: the mark is not cut into the fill")
    # the three must not be the same picture
    same = []
    for a, b in (("light", "dark"), ("light", "neutral"), ("dark", "neutral")):
        if imgs[a] == imgs[b]:
            same.append(f"{a} == {b}")
    # an unknown appearance
    unknown = warning_colours("chartreuse")
    fell_back_to = ("dark" if unknown == warning_colours("dark") else
                    "light" if unknown == warning_colours("light") else
                    "neutral" if unknown == warning_colours("neutral") else "?")
    record("J33", "The warning sign in Light / Dark / Neutral",
           "FAIL" if bad else "PASS",
           f"(mode, fill, mark, coverage, colours): {rows}; identical pairs="
           f"{same or 'none'}; an UNKNOWN appearance silently resolves to "
           f"{fell_back_to} — `theme.by_mode` ends `.get(mode, dark)`, so the "
           f"claim in warning_sign.py's own header that a fourth appearance "
           f"'fails loudly here' is not what the code does"
           + ("; PROBLEMS " + "; ".join(bad) if bad else ""),
           str(SHOTS / "J33-warning-sign-neutral.png"))


# --- J34 ------------------------------------------------------------------
@check("J34", "A real warning box in this window carries the sign, and its buttons still work")
def j34(c):
    """`set_warning_icon` replaces the platform triangle on three boxes in this
    window. Build each one exactly as the window builds it, show it, photograph
    it, and click each button to prove the RETURN is unchanged."""
    from PyQt6.QtWidgets import QMessageBox
    d = std_demo(c, "it8Wolf", fiducials=True, sample=60)
    shown = []
    real_exec = QMessageBox.exec

    results = {}

    def grab_exec(self, tag=[0]):
        self.setModal(False)
        self.show()
        pump(700)
        name = f"J34-warning-{tag[0]}.png"
        tag[0] += 1
        self.grab().save(str(SHOTS / name))
        icon_ok = not self.iconPixmap().isNull()
        btns = [b.text() for b in self.buttons()]
        dflt = self.defaultButton().text() if self.defaultButton() else ""
        shown.append((self.windowTitle(), icon_ok, btns, dflt, name))
        self.hide()
        return QMessageBox.StandardButton.Ok

    QMessageBox.exec = grab_exec
    try:
        # 1 — the read-findings box (Stop / Build anyway)
        d._read_findings = [("Part of this scan has no colour left in it",
                             "A driver-made finding, so the box can be shown.")]
        results["read_findings_default"] = d._confirm_despite_read_findings()
        # 2 — the misalignment box (Stop / Build anyway)
        d._align_warnings = ["Page 1: the read does not match the chart."]
        results["misalignment_default"] = d._confirm_despite_misalignment()
        # 3 — now CLICK Stop on each, to prove the return still flips
        def click_stop(self, tag=[0]):
            self.setModal(False)
            self.show(); pump(300)
            for b in self.buttons():
                if b.text() == "Stop":
                    b.click()
                    break
            self.hide()
            return QMessageBox.StandardButton.Cancel
        QMessageBox.exec = click_stop
        results["read_findings_stop"] = d._confirm_despite_read_findings()
        results["misalignment_stop"] = d._confirm_despite_misalignment()
    finally:
        QMessageBox.exec = real_exec
        _install_msgbox_capture()
    ok = (all(r[1] for r in shown) and len(shown) == 2
          and results.get("read_findings_default") is True
          and results.get("misalignment_default") is True
          and results.get("read_findings_stop") is False
          and results.get("misalignment_stop") is False)
    record("J34", "Warning boxes in this window after the sign conversion",
           "PASS" if ok else "FAIL",
           f"(title, has a pixmap icon, buttons, default, shot): {shown}; "
           f"return values — dismissed without clicking Stop: "
           f"read_findings={results.get('read_findings_default')}, "
           f"misalignment={results.get('misalignment_default')} (both must be "
           f"True = build anyway); Stop CLICKED: "
           f"read_findings={results.get('read_findings_stop')}, "
           f"misalignment={results.get('misalignment_stop')} (both must be "
           f"False = stop)",
           str(SHOTS / "J34-warning-0.png"))


# --- J35 ------------------------------------------------------------------
@check("J35", "Every grid button pressed with NO scan loaded")
def j35(c):
    """J01 found all six live before anything is loaded. Press them all."""
    d = c.dlg
    d._mode_standard.setChecked(True); pump(400)
    d._target_combo.setCurrentIndex(d._target_combo.findData("it8Wolf")); pump(400)
    d._log.clear()
    said = {}
    for name, btn in (("Rotate 90", d._rotate_btn),
                      ("Reset view", d._reset_btn),
                      ("Reset grid", d._reset_grid_btn),
                      ("Auto align", d._auto_align_btn),
                      ("Check alignment", d._check_align_btn),
                      ("Pop out", d._popout_btn)):
        before = d._log.toPlainText()
        click(btn)
        if name == "Auto align":
            wait_align(d)
        pump(400)
        new = d._log.toPlainText()[len(before):].strip()
        said[name] = new.splitlines()[0][:90] if new else "(silent)"
    click(d._popout_btn); pump(600)          # dock back
    alive = d.isVisible()
    record("J35", "Grid buttons with no scan loaded",
           "PASS" if alive else "FAIL",
           f"the window survived all six={alive}; what each one said: {said}; "
           f"boxes: {BOXES}",
           shot(d, "J35-no-scan.png"))


# ==========================================================================
def main():
    want = sys.argv[1:]
    c = Ctx()
    ids = want or sorted(CHECKS)
    for cid in ids:
        if cid not in CHECKS:
            print("no such check", cid); continue
        name, fn = CHECKS[cid]
        BOXES.clear()
        try:
            fn(c)
        except Exception:
            record(cid, name, "FAIL",
                   "the driver raised: " + traceback.format_exc()[-700:])
        if BOXES:
            print("   boxes:", BOXES)
        # fresh dialog between checks so state never leaks between them
        try:
            c.dlg.close()
        except Exception:
            pass
        pump(200)
        c.new_dialog()
    print("\nDONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
