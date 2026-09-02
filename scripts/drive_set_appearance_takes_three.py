#!/usr/bin/env python3
"""Drive the REAL ChromIQ window and record what every appearance-taking
component decides, in Light and in Dark.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_set_appearance_takes_three.py <outdir>

Twenty-two methods take an appearance (21 ``set_appearance`` + one
``set_theme``), and sixteen of them folded whatever they were handed into two
values -- ``"light" if mode == "light" else "dark"`` -- so a third appearance
would have been repainted as Dark. This opens the real main window, switches it
between Light and Dark through the app's own ``apply_appearance``, and for each
component records the mode it stored, the colours it chose, and the pixels it
produced. Run once before the change and once after; the JSON files must be
identical and every PNG must have the same hash.

Sandboxed: CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR and a custom_output_path
written into the .ini BEFORE anything builds an AppSettings, so a missing output
path can never fall back to the owner's real ~/ChromIQ. The run ends by checking
~/ChromIQ gained nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# SANDBOX ITSELF, BEFORE ANY ChromIQ IMPORT -- do not rely on the shell.
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/setapp.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/setapp-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/setapp-work"))
OUT = Path(sys.argv[1] if len(sys.argv) > 1
           else "/Users/Basti/Desktop/beta7/set-appearance-proof/onscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                              # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog, QMessageBox,   # noqa: E402
                             QWidget)


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def save(pixmap, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(path))
    img = pixmap.toImage()
    b = img.bits()
    b.setsize(img.sizeInBytes())
    return hashlib.sha256(bytes(b)).hexdigest()[:16]


def tree_hash(root: Path) -> "dict[str, str]":
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        out[rel + ("/" if p.is_dir() else "")] = (
            "dir" if p.is_dir() else hashlib.sha1(p.read_bytes()).hexdigest())
    return out


def _jsonable(v):
    from PyQt6.QtGui import QColor
    if isinstance(v, QColor):
        # repr() would put the object's ADDRESS in the record and make two
        # identical runs differ. The colour is the fact; the object is not.
        return v.name(QColor.NameFormat.HexArgb)
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return repr(v)


def decision(w) -> dict:
    """Everything this component decided from the appearance it was handed."""
    d: dict = {"mode": getattr(w, "_mode", None)}
    pal = getattr(w, "_palette", None)
    if isinstance(pal, dict):
        d["palette"] = _jsonable(pal)
    theme = getattr(w, "_theme", None)
    if isinstance(theme, dict):
        d["theme"] = _jsonable(theme)
    try:
        ss = w.styleSheet()
        if ss:
            d["stylesheet_sha"] = hashlib.sha256(ss.encode()).hexdigest()[:16]
            d["stylesheet_len"] = len(ss)
    except Exception:
        pass
    return d


def grab(w, path: Path) -> "str | None":
    try:
        if w.width() <= 0 or w.height() <= 0:
            return None
        return save(w.grab(), path)
    except Exception as exc:      # a component that cannot be grabbed says so
        return f"ungrabbable: {exc!r}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    real_root = Path.home() / "ChromIQ"
    before_real = tree_hash(real_root)
    print(f"~/ChromIQ before: {len(before_real)} entries")

    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))

    from core.settings import AppSettings
    settings = AppSettings()
    opened = Path(settings._qs.fileName())
    if opened != SETTINGS_INI:
        raise SystemExit(f"REFUSING TO RUN: settings escaped the sandbox: {opened}")
    print(f"settings store: {opened}")
    WORK.mkdir(parents=True, exist_ok=True)
    if str(settings.get("custom_output_path", "")) != str(WORK):
        settings.set("custom_output_path", str(WORK))
    print(f"custom_output_path: {settings.get('custom_output_path')}")

    # Never leave a modal open.
    QDialog.exec = lambda self: 1                        # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                    # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance

    win = MainWindow(settings)
    win.show()
    if ONSCREEN:
        win.raise_()
        win.activateWindow()
    pump(app, 1400)

    report: dict[str, dict] = {}
    for mode in ("light", "dark"):
        print(f"\n=== {mode.upper()} ===")
        apply_appearance(app, win, mode)
        pump(app, 1000)
        d = OUT / mode
        d.mkdir(parents=True, exist_ok=True)
        r: dict[str, object] = {}

        # ---- the window itself, so the appearance is on the record ---------
        r["00_window_sha"] = save(win.grab(), d / "00-window.png")
        r["00_title_bar_mode"] = getattr(win, "_title_bar_mode", None)
        r["00_styled_tab_theme"] = _jsonable(
            getattr(win, "_styled_tab_theme", {}))

        # ---- 1. EVERY LIVE COMPONENT THAT TAKES AN APPEARANCE --------------
        # The broadcast in MainWindow.apply_theme() has just run over these.
        live: dict[str, list] = {}
        for w in win.findChildren(QWidget):
            if callable(getattr(w, "set_appearance", None)):
                live.setdefault(type(w).__name__, []).append(w)
        if callable(getattr(win._masthead, "set_appearance", None)):
            live.setdefault(type(win._masthead).__name__, []).append(win._masthead)
        r["01_live_classes"] = {k: len(v) for k, v in sorted(live.items())}
        for cls in sorted(live):
            inst = live[cls][0]
            r[f"01_live/{cls}"] = decision(inst)
            r[f"01_live/{cls}/sha"] = grab(inst, d / f"01-live-{cls}.png")

        # ---- 2. THE COMPONENTS THAT ARE NOT ON SCREEN UNTIL ASKED ----------
        made: list[tuple[str, QWidget]] = []

        from ui.tools_popup import ToolsPopup
        tp = ToolsPopup(win)
        tp.set_appearance(mode)
        made.append(("ToolsPopup", tp))

        from ui.builtin_preset_popup import BuiltinPresetPopup
        bp = BuiltinPresetPopup(
            [("i1Pro", [("TC9.18 by Pharmacist", "tc918"),
                        ("SpyderPrint 225", "spyder225")])], win)
        bp.set_appearance(mode)
        made.append(("BuiltinPresetPopup", bp))

        from ui.margin_inspector_panel import MarginInspectorPanel
        mi = MarginInspectorPanel(win)
        mi.set_appearance(mode)
        made.append(("MarginInspectorPanel", mi))

        from ui.dialogs.welcome_dialog import WorkflowIcon
        wi = WorkflowIcon("chart", win)
        wi.set_appearance(mode)
        wi.resize(64, 64)
        made.append(("WorkflowIcon", wi))

        from ui.fade_scroll import FadeScrollArea
        fs = FadeScrollArea(win, surface="panel")
        fs.set_appearance(mode)
        fs.resize(220, 160)
        made.append(("FadeScrollArea", fs))

        from ui.tiff_preview import _PatchInfoTile
        pit = _PatchInfoTile(win)
        pit.set_theme(mode)
        made.append(("_PatchInfoTile", pit))

        # The three QToolButtons whose set_appearance is a deliberate no-op --
        # on the record so "nothing to repaint" is proved, not asserted.
        from ui.widgets import (ImageFileButton, MeasuredChartButton,
                                PatchGridButton, RevealFolderButton,
                                StackedPagesButton, StripReadButton)
        for cls in (PatchGridButton, StackedPagesButton, StripReadButton,
                    MeasuredChartButton, RevealFolderButton, ImageFileButton):
            b = cls("#56d6a5", win)
            b.set_appearance(mode)
            b.resize(40, 40)
            made.append((cls.__name__, b))

        for name, w in made:
            try:
                w.show()
            except Exception:
                pass
        pump(app, 350)
        for name, w in made:
            r[f"02_made/{name}"] = decision(w)
            r[f"02_made/{name}/sha"] = grab(w, d / f"02-made-{name}.png")
        # FadeScrollArea's real output is the fade colour it hands its edges.
        r["02_made/FadeScrollArea/fade"] = [
            fs._top_fade._color.name() if hasattr(fs._top_fade, "_color") else None,
            fs._bot_fade._color.name() if hasattr(fs._bot_fade, "_color") else None,
        ]
        for name, w in made:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        pump(app, 150)

        # ---- 3. EdgeFades: not a QWidget, wraps a scroll area --------------
        from PyQt6.QtWidgets import QScrollArea
        from ui.fade_scroll import attach_edge_fades
        sa = QScrollArea(win)
        sa.resize(220, 160)
        ef = attach_edge_fades(sa, surface="dialog")
        ef.set_appearance(mode)
        sa.show()
        pump(app, 200)
        r["03_EdgeFades"] = decision(ef)
        r["03_EdgeFades/fade"] = [
            ef._top._color.name() if hasattr(ef._top, "_color") else None,
            ef._bot._color.name() if hasattr(ef._bot, "_color") else None,
        ]
        r["03_EdgeFades/sha"] = grab(sa, d / "03-edgefades.png")
        sa.hide(); sa.setParent(None); sa.deleteLater()

        # ---- 3b. The welcome dialog, its cards and their icons -------------
        # WelcomeDialog takes its appearance in the CONSTRUCTOR (initial_mode)
        # and broadcasts to every card and icon it owns.
        from ui.dialogs.welcome_dialog import (WelcomeDialog, WorkflowCard,
                                               WorkflowIcon as _WI)
        wd = WelcomeDialog(settings, win, initial_mode=mode)
        wd.show()
        pump(app, 500)
        r["03b_WelcomeDialog"] = decision(wd)
        r["03b_WelcomeDialog/sha"] = grab(wd, d / "03b-welcome-dialog.png")
        cards = wd.findChildren(WorkflowCard)
        r["03b_WelcomeDialog/cards"] = len(cards)
        if cards:
            r["03b_WorkflowCard"] = decision(cards[0])
            r["03b_WorkflowCard/sha"] = grab(cards[0], d / "03b-workflow-card.png")
        icons = wd.findChildren(_WI)
        r["03b_WelcomeDialog/icons"] = len(icons)
        if icons:
            r["03b_WorkflowIcon_live"] = decision(icons[0])
            r["03b_WorkflowIcon_live/sha"] = grab(icons[0],
                                                  d / "03b-workflow-icon.png")
        wd.close()
        wd.setParent(None)
        wd.deleteLater()
        pump(app, 200)

        # ---- 4. PatchCubePanel: takes its appearance in the CONSTRUCTOR ----
        # No grab: it builds a Chromium surface. Its whole decision is the
        # theme dict it keeps.
        from ui.patch_cube_panel import PatchCubePanel
        pc = PatchCubePanel(mode=mode)
        r["04_PatchCubePanel"] = decision(pc)
        pc.setParent(None)
        pc.deleteLater()

        # The macOS native title bar is NOT recorded here. It is one of the
        # genuinely two-answer sites (Aqua / DarkAqua), it writes nothing this
        # process can read back, and its source is edited by this change, so a
        # source hash would be a guaranteed difference that proves nothing.
        # Its equivalence is proved as a pure function in
        # tests/test_set_appearance_takes_three.py instead.

        for k in sorted(r):
            print(f"  {k}: {r[k]!r}"[:150])
        report[mode] = r

    (OUT / "onscreen.json").write_text(
        json.dumps(_jsonable(report), indent=2, sort_keys=True))
    print(f"\nwrote {OUT / 'onscreen.json'}")

    win.close()
    pump(app, 400)

    after_real = tree_hash(real_root)
    gained = sorted(set(after_real) - set(before_real))
    print(f"~/ChromIQ after: {len(after_real)} entries; gained {len(gained)}")
    if gained:
        print("  LEAK:", gained[:20])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
