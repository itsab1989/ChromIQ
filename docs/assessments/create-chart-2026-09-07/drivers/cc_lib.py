#!/usr/bin/env python3
"""Shared helpers for the Create Chart assessment drivers (Agent 1).

Builds the real app the way `main()` does (fonts, WinButtonLayoutStyle("Fusion"),
CompositeAppFilter, apply_appearance), on the real screen, against the sandbox
settings file. Refuses to start without the sandbox.

Modal policy (brief rule 3): every expected dialog is answered by an armed
watcher that first asserts the dialog is the one expected (title or text
substring), then clicks a NAMED button and logs it. An unexpected modal is
logged as UNEXPECTED (a finding) and, to keep the run unattended, is closed
through its Cancel / Close / reject route, which is also logged. QMessageBox.exec
is never patched.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

ASSESS = Path("/Users/Basti/Desktop/Create Chart Assessment")
REPO = Path("/Users/Basti/develop/ChromIQ")
SANDBOX_INI = ASSESS / "Test Runs" / "sandbox" / "chromiq-assessment.ini"
PROJECTS = Path("/Users/Basti/ChromIQ-assessment")
SHOTS = ASSESS / "Screenshots"
LOGS = ASSESS / "Test Runs" / "logs"

sys.path.insert(0, str(REPO))

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    sys.exit("refusing to run offscreen: the assessment is of the real screen")
if os.environ.get("CHROMIQ_SETTINGS_FILE") != str(SANDBOX_INI):
    sys.exit("CHROMIQ_SETTINGS_FILE is not the assessment sandbox; source env.sh first")
if not os.environ.get("CHROMIQ_PRESETS_DIR"):
    sys.exit("CHROMIQ_PRESETS_DIR unset; source env.sh first")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QFontDatabase  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox,  # noqa: E402
                             QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QLabel, QMessageBox, QPushButton, QSpinBox,
                             QWidget)

# ----------------------------------------------------------------------------
# logging: everything the app logs, plus our own lines, into one file per driver
# ----------------------------------------------------------------------------
_DRIVER = Path(sys.argv[0]).stem
LOGS.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOGS / f"{_DRIVER}.log"
_fh = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(_fh)
logging.getLogger().setLevel(logging.DEBUG)
_ours = logging.getLogger("assess")

SERIOUS: list[logging.LogRecord] = []


class _Catcher(logging.Handler):
    def emit(self, record):
        if record.levelno >= logging.ERROR and record.name != "assess":
            SERIOUS.append(record)


logging.getLogger().addHandler(_Catcher())


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    _ours.info(msg)


def serious_since(n: int) -> list[str]:
    return [f"[{r.levelname}] {r.name}: {r.getMessage()}" for r in SERIOUS[n:]]


# ----------------------------------------------------------------------------
# app
# ----------------------------------------------------------------------------
def pump(ms: int) -> None:
    app = QApplication.instance()
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build_app(lang: str | None = None):
    """Everything main() does before it builds a window, in the same order."""
    from core.freetype_bootstrap import ensure_freetype_library
    ensure_freetype_library()
    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.theme import apply_appearance
    from ui.widgets import CompositeAppFilter
    from core.version import APP_VERSION

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("ChromIQ")
    from core.qt_message_filter import install_qt_message_filter
    install_qt_message_filter(app)
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app._assess_filter = CompositeAppFilter(app)
    app.installEventFilter(app._assess_filter)

    from core.settings import AppSettings
    settings = AppSettings()
    settings.migrate()
    from core.platform_paths import set_icc_install_override
    set_icc_install_override(str(settings.get("profile_install_dir", "")))
    from core.i18n import install_qt_translator, set_language
    set_language(lang or settings.get("language", "en"))
    install_qt_translator(app)
    apply_appearance(app, None, settings.get("appearance", "auto"))
    log(f"app built: v{APP_VERSION} appearance={settings.get('appearance')} "
        f"lang={lang or settings.get('language')} settings={os.environ['CHROMIQ_SETTINGS_FILE']}")
    return app, settings


def build_window(app, settings, width=1700, height=1050):
    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    win = MainWindow(settings)
    apply_appearance(app, win, settings.get("appearance", "auto"))
    win.resize(width, height)
    win.move(10, 30)
    win.show()
    pump(2200)
    return win


def goto_chart_tab(win):
    tab = win._tab_chart
    win._tabs.setCurrentIndex(win._tabs.indexOf(tab))
    pump(900)
    return tab


def open_project(win, settings, name: str) -> bool:
    """Open a project the way the app does at start (session_target_name +
    _restore_last_session), then verify the run bar shows a run."""
    settings.set("session_target_name", name)
    settings.set("session_project_root", "")
    win._restore_last_session()
    pump(1200)
    run = win._target_bar._run_combo.currentText().strip()
    ok = bool(run) and not run.lower().startswith("new run")
    log(f"open_project({name!r}) -> run bar reads {run!r} ok={ok}")
    return ok


# ----------------------------------------------------------------------------
# modal watcher
# ----------------------------------------------------------------------------
class ModalWatcher:
    """Polls for the active modal; answers expected ones by named button, logs
    and closes unexpected ones. Keeps a record of everything it saw."""

    def __init__(self, app, poll_ms: int = 120):
        self.app = app
        self.expected: list[dict] = []
        self.seen: list[dict] = []
        self.unexpected: list[dict] = []
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(poll_ms)
        self._handled: set[int] = set()
        #: dialogs (by class name or title substring) a driver handles itself
        self.ignore: list[str] = []

    def expect(self, match: str, button: str, *, note: str = "") -> None:
        """Arm an answer: dialog whose title or text contains *match* gets the
        button whose text contains *button* clicked (or Escape if button ==
        '<reject>' / Return if '<accept>')."""
        self.expected.append({"match": match, "button": button, "note": note})
        log(f"  armed: dialog ~'{match}' -> click '{button}' {note}")

    def clear(self) -> None:
        self.expected.clear()

    @staticmethod
    def _describe(w) -> dict:
        d = {"class": type(w).__name__, "title": w.windowTitle(), "text": ""}
        if isinstance(w, QMessageBox):
            d["text"] = (w.text() or "") + " | " + (w.informativeText() or "")
            d["buttons"] = [b.text() for b in w.buttons()]
        else:
            labels = [l.text() for l in w.findChildren(QLabel) if l.text()]
            d["text"] = " | ".join(labels)[:600]
            d["buttons"] = [b.text() for b in w.findChildren(QPushButton) if b.text()]
        return d

    def _click(self, w, button: str) -> str:
        if button == "<reject>":
            w.reject() if hasattr(w, "reject") else w.close()
            return "reject()"
        if button == "<accept>":
            w.accept() if hasattr(w, "accept") else w.close()
            return "accept()"
        cands = []
        if isinstance(w, QMessageBox):
            cands = list(w.buttons())
        else:
            cands = list(w.findChildren(QPushButton))
            for bb in w.findChildren(QDialogButtonBox):
                cands.extend(bb.buttons())
        want = button.replace("&", "").lower()
        for b in cands:
            if want in b.text().replace("&", "").lower():
                b.click()
                return f"clicked '{b.text()}'"
        return f"NO BUTTON MATCHING '{button}' among {[b.text() for b in cands]}"

    def _tick(self) -> None:
        w = self.app.activeModalWidget()
        if w is None or not w.isVisible():
            return
        # `id()` is reused once a dialog is freed, so a handled id must be
        # forgotten as soon as its widget is gone (this silently swallowed a
        # dialog in D07). Keep only ids whose widget is still alive and shown.
        alive = {id(x) for x in self.app.topLevelWidgets() if x.isVisible()}
        self._handled &= alive
        if id(w) in self._handled:
            return
        d = self._describe(w)
        hay = (d["title"] + " " + d["text"]).lower()
        for ig in self.ignore:
            if ig.lower() in hay or ig == d["class"]:
                return                      # the driver drives this one itself
        for i, e in enumerate(self.expected):
            if e["match"].lower() in hay:
                self._handled.add(id(w))
                how = self._click(w, e["button"])
                d.update(answer=how, expected=e["match"])
                self.seen.append(d)
                log(f"  DIALOG expected [{d['class']}] '{d['title']}' -> {how}")
                del self.expected[i]
                return
        # unexpected
        self._handled.add(id(w))
        d["answer"] = "UNEXPECTED"
        self.unexpected.append(d)
        log(f"  DIALOG UNEXPECTED [{d['class']}] title='{d['title']}' "
            f"buttons={d.get('buttons')} text={d['text'][:300]!r}")
        # close it through its own reject route so the run stays unattended
        for pref in ("Cancel", "Close", "OK", "<reject>"):
            how = self._click(w, pref)
            if not how.startswith("NO BUTTON"):
                log(f"    closed via {how}")
                d["closed_via"] = how
                break
        self.seen.append(d)


# ----------------------------------------------------------------------------
# widget helpers
# ----------------------------------------------------------------------------
def set_combo_data(combo: QComboBox, data) -> bool:
    idx = combo.findData(data)
    if idx < 0:
        # try string form
        for i in range(combo.count()):
            if str(combo.itemData(i)) == str(data):
                idx = i
                break
    if idx < 0:
        log(f"    set_combo_data: {data!r} not in {[combo.itemData(i) for i in range(combo.count())]}")
        return False
    combo.setCurrentIndex(idx)
    pump(150)
    return True


def set_combo_text(combo: QComboBox, text: str) -> bool:
    for i in range(combo.count()):
        if text.lower() in combo.itemText(i).lower():
            combo.setCurrentIndex(i)
            pump(150)
            return True
    log(f"    set_combo_text: {text!r} not in {[combo.itemText(i) for i in range(combo.count())]}")
    return False


def combo_items(combo: QComboBox) -> list[tuple[str, object]]:
    return [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]


def set_spin(spin, value) -> None:
    spin.setValue(value)
    if hasattr(spin, "editingFinished"):
        spin.editingFinished.emit()
    pump(120)


def set_check(cb: QCheckBox, on: bool) -> None:
    if cb.isChecked() != on:
        cb.click()
        pump(150)


def click(btn) -> None:
    btn.click()
    pump(200)


def visible_text(w: QWidget, max_len=4000) -> str:
    """All visible label texts under w, in tree order (for reading panels)."""
    out = []
    for l in w.findChildren(QLabel):
        if l.isVisible() and l.text().strip():
            out.append(l.text().strip())
    s = " | ".join(out)
    return s[:max_len]


def grab(w: QWidget, path: Path, rect: QRect | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pm = w.grab(rect) if rect is not None else w.grab()
    pm.save(str(path))
    log(f"  shot {path.relative_to(ASSESS)}  ({pm.width()}x{pm.height()})")
    return path


def grab_screen(path: Path) -> Path:
    """Whole-screen capture (catches native popups and dialogs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    scr = QApplication.primaryScreen()
    pm = scr.grabWindow(0)
    pm.save(str(path))
    log(f"  screen {path.relative_to(ASSESS)} ({pm.width()}x{pm.height()})")
    return path


def wait_until(pred, timeout_ms: int, what: str = "") -> bool:
    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        if pred():
            return True
        pump(100)
    log(f"  TIMEOUT waiting {timeout_ms} ms for {what}")
    return False


def wait_build(tab, timeout_ms: int = 240_000) -> bool:
    """A build re-enables Generate when it finishes (success or failure)."""
    pump(400)
    ok = wait_until(lambda: tab._generate_btn.isEnabled()
                    and not tab._runner.is_running, timeout_ms, "build to finish")
    pump(800)
    return ok


def tab_log_text(tab) -> str:
    return tab._log.toPlainText()


# ----------------------------------------------------------------------------
# file inventory
# ----------------------------------------------------------------------------
def tiff_info(p: Path) -> dict:
    from PIL import Image
    try:
        with Image.open(p) as im:
            dpi = im.info.get("dpi")
            comp = im.info.get("compression")
            bits = None
            try:
                bits = im.tag_v2.get(258)
            except Exception:
                pass
            return {"file": p.name, "size_px": im.size, "mode": im.mode,
                    "dpi": dpi, "bits": bits, "compression": comp,
                    "bytes": p.stat().st_size}
    except Exception as e:  # noqa: BLE001
        return {"file": p.name, "error": str(e)}


def run_inventory(run_dir: Path) -> dict:
    inv = {"dir": str(run_dir), "files": [], "tiffs": [], "channels": None,
           "ti2_sets": None, "ti2_steps_in_pass": None, "ti2_passes": None}
    if not run_dir.is_dir():
        inv["missing"] = True
        return inv
    for p in sorted(run_dir.rglob("*")):
        if p.is_file():
            inv["files"].append((str(p.relative_to(run_dir)), p.stat().st_size))
            if p.suffix.lower() in (".tif", ".tiff"):
                inv["tiffs"].append(tiff_info(p))
    for p in run_dir.glob("*.channels.json"):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            lay = doc.get("layout") or {}
            rec = lay.get("recipe") or {}
            inv["channels"] = {
                "file": p.name,
                "keys": sorted(doc.keys()),
                "layout_keys": sorted(lay.keys()),
                "dpi": lay.get("dpi"),
                "n_patch_rects": len(lay.get("patches") or []),
                "recipe_instrument": rec.get("instrument"),
                "recipe_paper": rec.get("paper"),
                "recipe_layout_mode": rec.get("layout_mode"),
                "recipe_margins": [rec.get(k) for k in ("margin_top", "margin_right", "margin_bottom", "margin_left")],
                "recipe_use_instr": rec.get("use_instrument_margins"),
                "recipe_patch_wh": (rec.get("patch_w_mm"), rec.get("patch_h_mm")),
                "engine": doc.get("engine") or lay.get("engine"),
                "margins_chosen_by_user": doc.get("margins_chosen_by_user", lay.get("margins_chosen_by_user")),
            }
        except Exception as e:  # noqa: BLE001
            inv["channels"] = {"file": p.name, "error": str(e)}
    for p in run_dir.glob("*.ti2"):
        import re
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"NUMBER_OF_SETS\s+(\d+)", txt)
            inv["ti2_sets"] = int(m.group(1)) if m else None
            m = re.search(r'STEPS_IN_PASS\s+"?(\d+)"?', txt)
            inv["ti2_steps_in_pass"] = int(m.group(1)) if m else None
            m = re.search(r'PASSES_IN_STRIPS2\s+"?([\d,]+)"?', txt)
            inv["ti2_passes"] = m.group(1) if m else None
            m = re.search(r'PATCH_LENGTH\s+"?([\d.]+)"?', txt)
            inv["ti2_patch_length"] = m.group(1) if m else None
            m = re.search(r'PATCH_WIDTH\s+"?([\d.]+)"?', txt)
            inv["ti2_patch_width"] = m.group(1) if m else None
            m = re.search(r'TARGET_INSTRUMENT\s+"([^"]+)"', txt)
            inv["ti2_instrument"] = m.group(1) if m else None
            m = re.search(r'PAPER_SIZE\s+"?([^"\n]+)"?', txt)
            inv["ti2_paper"] = m.group(1).strip() if m else None
            inv["ti2_file"] = p.name
        except Exception as e:  # noqa: BLE001
            inv["ti2_error"] = str(e)
    return inv


def panel_snapshot(tab) -> dict:
    """The two info frames as text, plus the estimate/actual dicts."""
    li = tab._layout_info_panel
    mp = tab._margin_panel
    d = {
        "layout_info_visible": li.isVisible(),
        "layout_info_text": visible_text(li),
        "layout_info_actual": getattr(li, "_actual", None),
        "layout_info_estimate": getattr(li, "_estimate", None),
        "margin_panel_visible": mp.isVisible(),
        "margin_panel_text": visible_text(mp),
        "margin_status": mp._status.text() if hasattr(mp, "_status") else None,
        "margin_status_visible": mp._status.isVisible() if hasattr(mp, "_status") else None,
        "margin_notes": mp.text_notes() if hasattr(mp, "text_notes") else None,
    }
    return d


def recipe_of(tab) -> dict:
    try:
        return tab._manual_layout_panel.get_recipe().to_dict()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    log(f"  json {path.relative_to(ASSESS)}")


def current_run_dir(win) -> Path | None:
    try:
        proj = win._file_mgr.project()
        return Path(proj.current_run().dir)
    except Exception as e:  # noqa: BLE001
        log(f"  current_run_dir: {e}")
        return None


def spinbox_bounds(w) -> dict:
    d = {"min": w.minimum(), "max": w.maximum(), "value": w.value(),
         "enabled": w.isEnabled(), "visible": w.isVisible()}
    if isinstance(w, QDoubleSpinBox):
        d["decimals"] = w.decimals()
        d["step"] = w.singleStep()
    if hasattr(w, "specialValueText") and w.specialValueText():
        d["special"] = w.specialValueText()
    if w.suffix():
        d["suffix"] = w.suffix()
    return d
