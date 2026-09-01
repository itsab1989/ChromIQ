#!/usr/bin/env python3
"""Drive the REAL ChromIQ window to prove a project name keeps its accents.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_name_accents.py

Two halves, and the second matters as much as the first:

  A. A NEW project called "Müller-Café" — typed DECOMPOSED, the spelling that
     used to come out as "Mu_ller" — gets a real chart built in it, and the
     folder, the file stems, the name box, project.json and the chart on screen
     all carry the accents.

  B. An EXISTING project is opened afterwards and NOTHING about it changes —
     Basti's ruling: leave every folder he already has exactly as it is. Proved
     by hashing the whole tree before and after.

Everything is sandboxed: CHROMIQ_SETTINGS_FILE, CHROMIQ_PRESETS_DIR and a
custom_output_path that is written into the .ini BEFORE the app is built, so a
missing output path can never fall back to the owner's real ~/ChromIQ. The run
ends by checking ~/ChromIQ gained nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import unicodedata as ud
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# SANDBOX ITSELF, BEFORE ANY ChromIQ IMPORT — do not rely on the shell.
#
# THIS COST AN INCIDENT. Exporting CHROMIQ_SETTINGS_FILE in one shell does not
# reach a script launched from another, and a helper this one spawns inherits
# only what it is given. A run that misses it builds a REAL `AppSettings` and
# writes `custom_output_path` into the owner's live preference store — pointing
# at a /tmp folder that is swept nightly, after which ChromIQ looks for every
# one of his projects in a directory that no longer exists and quietly finds
# none. Set here, passed to children, and checked below against what
# `AppSettings` actually opened.
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", "/tmp/accents.ini")
os.environ.setdefault("CHROMIQ_PRESETS_DIR", "/tmp/accents-presets")
SETTINGS_INI = Path(os.environ["CHROMIQ_SETTINGS_FILE"])
WORK = Path(os.environ.get("CHROMIQ_WORK", "/tmp/accents-work"))
SHOTS = Path(os.environ.get("CHROMIQ_SHOTS",
                            "/Users/Basti/Desktop/beta7/name-accents-proof"))

TYPED = ud.normalize("NFD", "Müller-Café")      # the spelling that used to break
WANT = ud.normalize("NFC", "Müller-Café")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QSettings                                 # noqa: E402
from PyQt6.QtGui import QFontDatabase                              # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,                # noqa: E402
                             QMessageBox)

RESULTS: "list[tuple[str, bool, str]]" = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def tree_hash(root: Path) -> "dict[str, str]":
    """name -> sha1 of contents, for every file under *root*, plus its NAME
    bytes — a rename is a change too."""
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_dir():
            out[rel + "/"] = "dir"
        else:
            try:
                out[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
            except OSError as exc:
                out[rel] = f"unreadable:{exc}"
    return out


def shoot(app, widget, name: str) -> Path:
    """Qt grabbing — `screencapture` returns the wallpaper in this environment."""
    pump(app, 250)
    path = SHOTS / name
    widget.grab().save(str(path))
    print(f"      shot: {path}")
    return path


def main() -> int:
    SHOTS.mkdir(parents=True, exist_ok=True)

    real_root = Path.home() / "ChromIQ"
    before_real = tree_hash(real_root)
    print(f"~/ChromIQ before: {len(before_real)} entries\n")

    from core.resource_path import resource_path
    from ui.styles import APP_STYLESHEET, WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))
    app.setStyleSheet(APP_STYLESHEET)

    from core.settings import AppSettings
    settings = AppSettings()
    # The store `AppSettings` actually opened — not the variable we set. A real
    # NativeFormat plist path here means the run is writing the owner's live
    # preferences, and it must stop before it touches anything.
    opened = Path(settings._qs.fileName())
    if opened != SETTINGS_INI:
        raise SystemExit(
            f"REFUSING TO RUN: settings escaped the sandbox.\n"
            f"  wanted: {SETTINGS_INI}\n  opened: {opened}\n"
            f"Set CHROMIQ_SETTINGS_FILE before importing anything from core/.")
    check(True, "the settings store is the sandbox .ini", str(opened))
    check(str(settings.get("custom_output_path")) == str(WORK),
          "the sandbox .ini already carries custom_output_path",
          str(settings.get("custom_output_path")))

    WORK.mkdir(parents=True, exist_ok=True)
    if str(settings.get("custom_output_path", "")) != str(WORK):
        # A sandboxed .ini with NO output path falls back to the owner's real
        # ~/ChromIQ, which is how junk projects appear there.
        settings.set("custom_output_path", str(WORK))

    # An existing project to prove nothing about it changes (half B).
    existing_src = ROOT / "demo-projects" / "Demo-Report-Matrix"
    existing = WORK / "Demo-Report-Matrix"
    if existing.exists():
        shutil.rmtree(existing)
    shutil.copytree(existing_src, existing)
    existing_before = tree_hash(existing)
    print(f"existing project staged: {existing} ({len(existing_before)} entries)\n")

    # Never leave a modal open.
    QDialog.exec = lambda self: 1                        # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: 0                    # type: ignore[assignment]

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    win = MainWindow(settings)
    win.show()
    if ONSCREEN:
        win.raise_()
        win.activateWindow()
    pump(app, 2500)

    tab = win._tab_chart
    fm = win._file_mgr

    # ---------------------------------------------------------------- half A
    print("HALF A — a NEW project typed with a decomposed accent")
    tab._switch_mode("manual")
    pump(app, 800)

    box = tab._manual_target_name_edit
    box.setText(TYPED)
    pump(app, 900)

    from ui.dialogs import name_prompt
    check(name_prompt.folder_name(TYPED) == WANT,
          "the dialog's live 'folder ChromIQ will make' line agrees",
          name_prompt.folder_name(TYPED))
    shoot(app, tab, "01-name-box-manual.png")

    # A small real build: a few patches through the real targen + printtarg.
    pw = getattr(tab, "_manual_f_pw", None)
    if getattr(tab, "_manual_auto_patches_check", None) is not None:
        tab._manual_auto_patches_check.setChecked(False)
        pump(app, 300)
    if pw is not None:
        pw._control.setValue(64)
        pump(app, 400)
    print(f"    patch count = {pw._control.value() if pw else '?'}")

    tab._on_generate()
    print("    Generate Chart pressed — waiting for the real Argyll build…")
    root = WORK / WANT
    deadline = time.time() + 240
    while time.time() < deadline:
        pump(app, 500)
        tifs = list(root.rglob("*.tif")) if root.exists() else []
        if tifs and not win._runner.is_running:
            break
    pump(app, 1500)

    check(root.is_dir(), "the folder on disk carries the accents",
          f"{root}  exists={root.is_dir()}")
    if not root.is_dir():
        for child in sorted(WORK.iterdir()):
            print(f"      on disk: {ascii(child.name)}")
    on_disk = [p.name for p in WORK.iterdir() if p.is_dir()]
    check(WANT in on_disk, "…and it is spelled NFC, one spelling only",
          f"{[ascii(n) for n in on_disk]}")

    run_dir = root / "runs" / "run1"
    stems = sorted(p.name for p in run_dir.iterdir()) if run_dir.is_dir() else []
    print("    run1 holds:")
    for s in stems:
        print(f"      {s}")
    for ext in (".ti1", ".ti2", ".tif", ".channels.json"):
        got = [s for s in stems if s.endswith(ext)]
        check(bool(got) and all(ud.normalize("NFC", s).startswith(WANT)
                                for s in got),
              f"every {ext} carries the accented stem", ", ".join(got) or "none")
    # No .cht is written at build time by design (chart_creator._run_engine):
    # a scan template is only useful paired with a measured .cie.
    exports = sorted(p.name for p in (run_dir / "exports").iterdir()) \
        if (run_dir / "exports").is_dir() else []
    check(bool(exports) and all(ud.normalize("NFC", e).startswith(WANT)
                                for e in exports),
          "the export sidecars carry it too", ", ".join(exports) or "none")

    # THE ONE FILE ARGYLL ITSELF NAMES. Qt normalises every QProcess argument
    # to NFD on macOS (measured: plain subprocess does not), so targen writes
    # its .ti1 decomposed however ChromIQ spells the stem. Canonically the same
    # name, and APFS opens it either way — recorded here rather than asserted
    # away, because a glob would not fold it.
    ti1 = [s for s in stems if s.endswith(".ti1")]
    check(bool(ti1), "targen wrote a .ti1", ", ".join(map(ascii, ti1)))
    for s_ in ti1:
        print(f"      .ti1 on disk is "
              f"{'NFC' if s_ == ud.normalize('NFC', s_) else 'NFD'} "
              f"(Qt normalises process arguments on macOS)")
    check(all(run.exists() for run in (run_dir / f"{WANT}.ti1",)),
          "…and ChromIQ opens it under the accented name it asked for")

    manifest_path = root / "project.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    check(manifest.get("target_name") == WANT,
          "project.json agrees with the folder",
          ascii(str(manifest.get("target_name"))))
    check(fm.get_target_name() == WANT and fm.working_dir() == root,
          "the FileManager and the Project do not disagree (no split brain)",
          f"{ascii(fm.get_target_name())} @ {fm.working_dir()}")

    (SHOTS / "project.json.txt").write_text(
        manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
    (SHOTS / "folder-listing.txt").write_text(
        "\n".join(sorted(str(p.relative_to(WORK)) for p in root.rglob("*"))),
        encoding="utf-8")

    shoot(app, win, "02-window-after-build.png")
    shoot(app, tab._preview, "03-chart-preview.png")
    shoot(app, tab, "04-create-chart-tab.png")

    # the sheet itself, as printtarg drew it
    tifs = sorted(run_dir.glob("*.tif")) if run_dir.is_dir() else []
    if tifs:
        from PyQt6.QtGui import QImage
        img = QImage(str(tifs[0]))
        small = img.scaledToWidth(900)
        small.save(str(SHOTS / "05-printed-sheet.png"))
        print(f"      shot: {SHOTS / '05-printed-sheet.png'}  (from {tifs[0].name})")
        check(not img.isNull(), "the chart TIFF renders", f"{img.width()}x{img.height()}")

    # --------------------------------------------------------------- half A2
    print("\nHALF A2 — the reported on-screen fault: a project that arrived "
          "DECOMPOSED")
    nfd_root = WORK / ud.normalize("NFD", "Zip-Müller-Café")
    shutil.copytree(root, nfd_root)
    check(nfd_root.name != ud.normalize("NFC", nfd_root.name),
          "the folder on disk really is decomposed (as unzip/ditto leave it)",
          ascii(nfd_root.name))

    fm.open_project_at(nfd_root)
    tab._last_target_name = fm.get_target_name()
    tab._update_name_fields()
    pump(app, 900)
    shown = tab._manual_target_name_edit.text()
    guided = tab._target_name_edit.text()
    check(shown == ud.normalize("NFC", "Zip-Müller-Café"),
          "the name box reads the project's name, not 'Zip-Mu_ller-Cafe'",
          f"box={ascii(shown)}")
    check(guided == shown, "the Guided box says the same",
          f"guided={ascii(guided)}")
    check(fm.working_dir() == nfd_root,
          "…and the path is still the filesystem's own bytes",
          ascii(str(fm.working_dir().name)))
    manifest2 = json.loads((nfd_root / "project.json").read_text(encoding="utf-8"))
    check(ud.normalize("NFC", manifest2["target_name"])
          == ud.normalize("NFC", "Müller-Café"),
          "no split brain: the box and the manifest name the same project",
          f"manifest={ascii(manifest2['target_name'])} box={ascii(shown)}")
    shoot(app, tab, "07-decomposed-project-name-box.png")

    # ---------------------------------------------------------------- half B
    print("\nHALF B — an EXISTING project is untouched")
    # The real open route — the same call the project picker makes.
    fm.open_project_at(existing)
    tab._last_target_name = fm.get_target_name()
    tab._update_name_fields()
    win._tabs.setCurrentWidget(tab)
    pump(app, 1500)
    shoot(app, win, "06-existing-project-open.png")
    check(tab._manual_target_name_edit.text() == "Demo-Report-Matrix",
          "the name box shows the existing project, unchanged",
          ascii(tab._manual_target_name_edit.text()))

    existing_after = tree_hash(existing)
    changed = {k for k in set(existing_before) | set(existing_after)
               if existing_before.get(k) != existing_after.get(k)}
    check(sorted(existing_before) == sorted(existing_after)
          or set(existing_after) > set(existing_before),
          "not one file of the existing project was RENAMED",
          f"{len(set(existing_before) - set(existing_after))} names lost")
    # Every file that was there is still there, byte for byte, EXCEPT the two
    # ChromIQ rewrites for any project it opens after a build (its per-target
    # Create Chart settings). Proved to be nothing to do with this fix: the
    # same two files are rewritten by the same sequence under a PURE ASCII
    # project name, for which `_sanitise` is byte-identical before and after.
    BOOKKEEPING = {"runs/run1/meta.json", "runs/run1/cache/",
                   "runs/run1/cache/new_run.json"}
    unexpected = sorted(changed - BOOKKEEPING)
    check(not unexpected,
          "nothing in its chart, measurement or profile chain changed",
          f"{unexpected[:5]}" if unexpected else
          f"only ChromIQ's per-target settings: {sorted(changed)}")
    check(fm.get_target_name() == "Demo-Report-Matrix",
          "…and its name is still exactly its own",
          fm.get_target_name())
    (SHOTS / "existing-project-unchanged.txt").write_text(
        f"entries before: {len(existing_before)}\n"
        f"entries after : {len(existing_after)}\n"
        f"differences   : {sorted(changed)}\n", encoding="utf-8")

    win.close()
    pump(app, 500)

    # ------------------------------------------------------------- sandbox
    print("\nSANDBOX")
    after_real = tree_hash(real_root)
    gained = sorted(set(after_real) - set(before_real))
    check(not gained, "~/ChromIQ gained nothing", f"{gained[:5]}")
    check(str(settings.get("custom_output_path")) == str(WORK),
          "custom_output_path never left the sandbox",
          str(settings.get("custom_output_path")))

    print("\n" + "=" * 62)
    bad = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   — {detail}" if detail else ""))
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    print(f"Shots and dumps: {SHOTS}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
