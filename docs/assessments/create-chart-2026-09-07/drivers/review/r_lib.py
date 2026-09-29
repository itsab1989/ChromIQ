#!/usr/bin/env python3
"""Agent 2 (review) driver library. Written independently of Agent 1's cc_lib
(the app-build recipe is the one main() uses and the one the brief names;
the helpers below are my own so that my logs, shots and modal policy land
under Review/ and not in Agent 1's folders).

Modal policy (brief rule 3): every expected dialog is answered by an armed
watcher that FIRST asserts the dialog is the one expected (title or text
substring), THEN clicks a NAMED button and logs both. An unexpected modal is
logged as UNEXPECTED (a finding) and closed through its own Cancel / Close /
OK route so the run stays unattended. QMessageBox.exec is never patched.

Sandbox: refuses to start unless CHROMIQ_SETTINGS_FILE is the assessment
sandbox ini and CHROMIQ_PRESETS_DIR is set (source env.sh first). Refuses
offscreen.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import traceback
from pathlib import Path

ASSESS = Path("/Users/Basti/Desktop/Create Chart Assessment")
REVIEW = ASSESS / "Review"
REPO = Path("/Users/Basti/develop/ChromIQ")
SANDBOX_INI = ASSESS / "Test Runs" / "sandbox" / "chromiq-assessment.ini"
PROJECTS = Path("/Users/Basti/ChromIQ-assessment")
SHOTS = REVIEW / "Screenshots"
LOGS = REVIEW / "Test Runs" / "logs"

sys.path.insert(0, str(REPO))

if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
    sys.exit("refusing to run offscreen: the review is of the real screen")
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

_DRIVER = Path(sys.argv[0]).stem
LOGS.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOGS / f"{_DRIVER}.log"
_fh = logging.FileHandler(LOG_PATH, mode="a", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(_fh)
logging.getLogger().setLevel(logging.DEBUG)
_ours = logging.getLogger("review")

SERIOUS: list[logging.LogRecord] = []
APP_LINES: list[str] = []      # every log record the app emits, for grepping


class _Catcher(logging.Handler):
    def emit(self, record):
        if record.name in ("review",):
            return
        try:
            APP_LINES.append(f"[{record.levelname}] {record.name}: {record.getMessage()}")
        except Exception:  # noqa: BLE001
            pass
        if record.levelno >= logging.ERROR:
            SERIOUS.append(record)


logging.getLogger().addHandler(_Catcher())


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    _ours.info(msg)


def serious_since(n: int) -> list[str]:
    return [f"[{r.levelname}] {r.name}: {r.getMessage()}" for r in SERIOUS[n:]]


def app_lines_since(n: int, pattern: str | None = None) -> list[str]:
    lines = APP_LINES[n:]
    if pattern:
        lines = [l for l in lines if re.search(pattern, l)]
    return lines


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
    app._review_filter = CompositeAppFilter(app)
    app.installEventFilter(app._review_filter)

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
        f"lang={lang or settings.get('language')} settings={os.environ['CHROMIQ_SETTINGS_FILE']} "
        f"presets={os.environ['CHROMIQ_PRESETS_DIR']} projects={settings.get('custom_output_path')}")
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
    """Open a project the way the app does at start."""
    settings.set("session_target_name", name)
    settings.set("session_project_root", "")
    win._restore_last_session()
    pump(1500)
    run = win._target_bar._run_combo.currentText().strip()
    ok = bool(run) and not run.lower().startswith("new run")
    log(f"open_project({name!r}) -> run bar reads {run!r} ok={ok}")
    return ok


# ----------------------------------------------------------------------------
# modal watcher
# ----------------------------------------------------------------------------
class ModalWatcher:
    def __init__(self, app, poll_ms: int = 100):
        self.app = app
        self.expected: list[dict] = []
        self.seen: list[dict] = []
        self.unexpected: list[dict] = []
        self.ignore: list[str] = []
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)
        self._timer.start(poll_ms)
        self._handled: set[int] = set()

    def expect(self, match: str, button: str, *, note: str = "") -> None:
        self.expected.append({"match": match, "button": button, "note": note})
        log(f"  armed: dialog ~'{match}' -> click '{button}' {note}")

    def clear(self) -> None:
        self.expected.clear()

    @staticmethod
    def describe(w) -> dict:
        d = {"class": type(w).__name__, "title": w.windowTitle(), "text": ""}
        if isinstance(w, QMessageBox):
            d["text"] = (w.text() or "") + " | " + (w.informativeText() or "")
            d["buttons"] = [b.text() for b in w.buttons()]
        else:
            labels = [l.text() for l in w.findChildren(QLabel) if l.text()]
            d["text"] = " | ".join(labels)[:700]
            d["buttons"] = [b.text() for b in w.findChildren(QPushButton) if b.text()]
        return d

    @staticmethod
    def _click(w, button: str) -> str:
        if button == "<reject>":
            w.reject() if hasattr(w, "reject") else w.close()
            return "reject()"
        if button == "<accept>":
            w.accept() if hasattr(w, "accept") else w.close()
            return "accept()"
        cands = list(w.buttons()) if isinstance(w, QMessageBox) else list(w.findChildren(QPushButton))
        if not isinstance(w, QMessageBox):
            for bb in w.findChildren(QDialogButtonBox):
                cands.extend(bb.buttons())
        want = button.replace("&", "").lower()
        for b in cands:
            if want in b.text().replace("&", "").lower():
                b.click()
                return f"clicked '{b.text()}'"
        return f"NO BUTTON MATCHING '{button}' among {[b.text() for b in cands]}"

    def _tick(self) -> None:
        try:
            self._tick_inner()
        except Exception as exc:  # noqa: BLE001
            log(f"  WATCHER ERROR {exc!r}")

    def _find_modal(self):
        w = self.app.activeModalWidget()
        if w is not None and w.isVisible():
            return w
        # A dialog run through exec() from a non-GUI-event slot is not always
        # reported by activeModalWidget(); look for any visible modal dialog.
        for t in self.app.topLevelWidgets():
            if isinstance(t, (QDialog, QMessageBox)) and t.isVisible() and t.isModal():
                return t
        return None

    def _tick_inner(self) -> None:
        w = self._find_modal()
        if w is None:
            return
        alive = {id(x) for x in self.app.topLevelWidgets() if x.isVisible()}
        self._handled &= alive
        if id(w) in self._handled:
            return
        d = self.describe(w)
        hay = (d["title"] + " " + d["text"]).lower()
        for ig in self.ignore:
            if ig.lower() in hay or ig == d["class"]:
                return
        for i, e in enumerate(self.expected):
            if e["match"].lower() in hay:
                self._handled.add(id(w))
                how = self._click(w, e["button"])
                d.update(answer=how, expected=e["match"])
                self.seen.append(d)
                log(f"  DIALOG expected [{d['class']}] title='{d['title']}' "
                    f"buttons={d.get('buttons')} text={d['text'][:200]!r} -> {how}")
                del self.expected[i]
                return
        self._handled.add(id(w))
        d["answer"] = "UNEXPECTED"
        self.unexpected.append(d)
        log(f"  DIALOG UNEXPECTED [{d['class']}] title='{d['title']}' "
            f"buttons={d.get('buttons')} text={d['text'][:400]!r}")
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


def combo_items(combo: QComboBox) -> list:
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


def pw(tab, tool: str, flag: str):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w
    return None


def visible_text(w: QWidget, max_len=4000) -> str:
    out = []
    for l in w.findChildren(QLabel):
        if l.isVisible() and l.text().strip():
            out.append(l.text().strip())
    return " | ".join(out)[:max_len]


def grab(w: QWidget, path: Path, rect: QRect | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pm = w.grab(rect) if rect is not None else w.grab()
    pm.save(str(path))
    log(f"  shot {path.relative_to(ASSESS)}  ({pm.width()}x{pm.height()})")
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
    pump(400)
    ok = wait_until(lambda: tab._generate_btn.isEnabled()
                    and not tab._runner.is_running, timeout_ms, "build to finish")
    pump(800)
    return ok


def gen(tab, watcher, label: str, extra_expect: list | None = None, timeout_ms: int = 240_000) -> dict:
    """Press Generate with the two routine dialogs armed, wait, snapshot."""
    n0 = len(APP_LINES)
    watcher.expect("quite fill", "OK", note="(last page hint)")
    for m, b in (extra_expect or []):
        watcher.expect(m, b)
    click(tab._generate_btn)
    ok = wait_build(tab, timeout_ms)
    watcher.clear()
    s = panel_snapshot(tab)
    s["built_ok"] = ok
    s["errors"] = app_lines_since(n0, r"\[ERROR\]|\[CRITICAL\]|Traceback")
    s["engine_lines"] = app_lines_since(n0, r"layout engine|patches \(|page")[:6]
    log(f"  [{label}] built ok={ok} actual={s['layout_info_actual']} est={s['layout_info_estimate']}\n"
        f"      margins={s['margin_panel_text'][:260]}\n"
        f"      status={s['margin_status']!r} notes={s['margin_notes']!r}")
    return s


def tab_log_text(tab) -> str:
    return tab._log.toPlainText()


def panel_snapshot(tab) -> dict:
    li = tab._layout_info_panel
    mp = tab._margin_panel
    return {
        "layout_info_visible": li.isVisible(),
        "layout_info_text": visible_text(li),
        "layout_info_actual": getattr(li, "_actual", None),
        "layout_info_estimate": getattr(li, "_estimate", None),
        "margin_panel_visible": mp.isVisible(),
        "margin_panel_text": visible_text(mp),
        "margin_status": mp._status.text() if hasattr(mp, "_status") else None,
        "margin_status_visible": mp._status.isVisible() if hasattr(mp, "_status") else None,
        "margin_notes": mp.text_notes() if hasattr(mp, "text_notes") else None,
        "generate_enabled": tab._generate_btn.isEnabled(),
        "stop_visible": tab._stop_btn.isVisible() if hasattr(tab, "_stop_btn") else None,
        "preview_pages": getattr(tab._preview, "_page_count", None) or getattr(tab._preview, "page_count", lambda: None)(),
    }


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


def listing(d: Path) -> dict:
    out = {}
    if d is None or not d.is_dir():
        return out
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d))] = (p.stat().st_size, int(p.stat().st_mtime))
    return out


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def ti2_facts(p: Path) -> dict:
    d = {}
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
        for key, rx in (("sets", r"NUMBER_OF_SETS\s+(\d+)"), ("steps", r'STEPS_IN_PASS\s+"?(\d+)"?'),
                        ("passes", r'PASSES_IN_STRIPS2\s+"?([\d,]+)"?'), ("patch_len", r'PATCH_LENGTH\s+"?([\d.]+)"?'),
                        ("patch_w", r'PATCH_WIDTH\s+"?([\d.]+)"?'), ("instr", r'TARGET_INSTRUMENT\s+"([^"]+)"'),
                        ("paper", r'PAPER_SIZE\s+"?([^"\n]+)"?'), ("created", r'CREATED\s+"([^"]+)"')):
            m = re.search(rx, txt)
            d[key] = m.group(1) if m else None
    except Exception as e:  # noqa: BLE001
        d["error"] = str(e)
    return d


def ti1_sets(p: Path) -> int | None:
    try:
        m = re.search(r"NUMBER_OF_SETS\s+(\d+)", p.read_text(encoding="utf-8", errors="replace"))
        return int(m.group(1)) if m else None
    except Exception:  # noqa: BLE001
        return None


# ----------------------------------------------------------------------------
# instrumentation: who writes a widget?
# ----------------------------------------------------------------------------
TRACES: list[dict] = []


def _short_stack(skip: int = 2, depth: int = 14) -> list[str]:
    frames = traceback.extract_stack()[:-skip]
    out = []
    for f in frames[-depth:]:
        if "/ChromIQ/" in f.filename or "drivers" in f.filename:
            out.append(f"{Path(f.filename).name}:{f.lineno} {f.name}")
    return out


def trace_pw(widget, name: str) -> None:
    """Wrap a ParameterWidget's set_value and reset_to_default (and its inner
    checkbox's setChecked, when it has one) so every write is logged with a
    stack."""
    orig_set = widget.set_value
    orig_reset = widget.reset_to_default

    def set_value(v, *a, **k):
        st = _short_stack()
        TRACES.append({"widget": name, "op": "set_value", "value": v, "stack": st, "t": time.time()})
        log(f"  TRACE {name}.set_value({v!r}) <- {' < '.join(reversed(st[-8:]))}")
        return orig_set(v, *a, **k)

    def reset_to_default(*a, **k):
        st = _short_stack()
        TRACES.append({"widget": name, "op": "reset_to_default", "stack": st, "t": time.time()})
        log(f"  TRACE {name}.reset_to_default() <- {' < '.join(reversed(st[-8:]))}")
        return orig_reset(*a, **k)

    widget.set_value = set_value
    widget.reset_to_default = reset_to_default
    ctl = getattr(widget, "_control", None)
    if isinstance(ctl, QCheckBox):
        orig_sc = ctl.setChecked

        def setChecked(v):  # noqa: N802
            st = _short_stack()
            TRACES.append({"widget": name, "op": "control.setChecked", "value": v, "stack": st, "t": time.time()})
            log(f"  TRACE {name}.control.setChecked({v!r}) <- {' < '.join(reversed(st[-8:]))}")
            return orig_sc(v)
        ctl.setChecked = setChecked


def trace_method(obj, meth: str, name: str, show=lambda a, k: "") -> None:
    orig = getattr(obj, meth)

    def wrapper(*a, **k):
        st = _short_stack()
        TRACES.append({"widget": name, "op": meth, "detail": show(a, k), "stack": st, "t": time.time()})
        log(f"  TRACE {name}.{meth}({show(a, k)}) <- {' < '.join(reversed(st[-8:]))}")
        return orig(*a, **k)
    setattr(obj, meth, wrapper)
