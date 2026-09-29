#!/usr/bin/env python3
"""Round 27b: the 14 demo presets, installed from the SHIPPED pack, on screen.

Not regenerated. The folder the demo package actually puts on a user's Desktop
is copied into the presets folder the way its own README tells them to, the app
is started, and each demo is looked up in the real "Which presets can be
verified?" window opened by the real button. Regenerating them with the
generator would be a fixture that agrees with the code that wrote it.

For each demo the driver records the verdict chip, the reason codes the window
gives, and every line of the detail pane, and checks them against the reason
code the pack's own README claims for that preset.

    python scripts/adv27b_the_demo_presets_as_a_user_gets_them.py <out-dir>
"""
from __future__ import annotations

import json
import os
import re
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

from PyQt6.QtCore import Qt                                    # noqa: E402

from adv27b_the_preset_button import app_like_main, pump        # noqa: E402
from drive_182_preset_verification_window import twice          # noqa: E402

PACK = (Path.home() / "Desktop/ChromIQ-beta23-proof/demo-pack"
        / "ChromIQ-Report-Limit-Demos"
        / "Create Chart presets (verification demos)")
WORK = Path("/tmp/chromiq-r27b/work-d")
STRICT = ("t2_full_colour_check", "custom_iso_12647_7")


def claims_from_readme() -> "dict[str, list[str]]":
    """What the pack's own README promises each demo will say."""
    txt = (PACK / "README.txt").read_text(encoding="utf-8")
    out: "dict[str, list[str]]" = {}
    name = None
    for line in txt.splitlines():
        m = re.match(r"^  (Verify demo \d\d, .+?)\s*$", line)
        if m:
            name = m.group(1)
            out.setdefault(name, [])
            continue
        m2 = re.search(r"reason code: (\w+)", line)
        if m2 and name:
            out[name].append(m2.group(1))
        m3 = re.search(r"and, unavoidably: (\w+)", line)
        if m3 and name:
            out[name].append(m3.group(1))
    return out


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else
               Path.home() / "Desktop/ChromIQ-beta23-proof/round-27b-chart")
    shots = out / "shots-demos"
    shots.mkdir(parents=True, exist_ok=True)
    assert "/tmp/" in os.environ.get("CHROMIQ_SETTINGS_FILE", ""), "SANDBOX"
    assert "/tmp/" in os.environ.get("CHROMIQ_PRESETS_DIR", ""), "SANDBOX"
    assert PACK.is_dir(), f"the shipped pack is not at {PACK}"
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)

    log: "list[str]" = []

    def say(x=""):
        print(x, flush=True)
        log.append(x)

    app = app_like_main()
    from core.preset_store import tab_dir
    dest = tab_dir("create_chart")
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(PACK.iterdir()):
        if src.suffix in (".json", ".ti1"):
            shutil.copy2(src, dest / src.name)
            copied.append(src.name)

    from core.settings import AppSettings
    s = AppSettings()
    s.set("custom_output_path", str(WORK))
    from core.file_manager import Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from ui.main_window import MainWindow
    proj = WORK / "R27b-D"
    Project.create(proj, "R27b-D").current_run().ensure_dir()
    win = MainWindow(s)
    win.resize(1500, 1020)
    win.show()
    pump(app, 1400)
    win._file_mgr.open_project_at(proj)
    win._target_ctl.changed.emit()
    pump(app, 700)
    tab = win._tab_chart
    win._tabs.setCurrentIndex(win._tabs.indexOf(tab))
    pump(app, 600)
    tab._manual_btn.click()
    pump(app, 900)
    win._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app, 900)

    say("# round 27b — the 14 demo presets, from the SHIPPED pack")
    say("")
    say(f"driven {time.strftime('%Y-%m-%d %H:%M:%S')}")
    say(f"pack   : {PACK}")
    say(f"copied : {len(copied)} files into {dest}")
    say("mode   : ON SCREEN, a real window, capture_window by id")
    say("")

    combo = tab._preset_combo
    listed = [combo.itemText(i) for i in range(combo.count())]
    mine = [t for t in listed if "Verify demo" in t]
    say(f"## the pulldown holds {len(mine)} of them")
    for t in mine:
        say(f"    {t}")
    say("")

    from ui.dialogs import preset_verification_dialog as PVD
    opened: list = []
    orig = PVD.PresetVerificationDialog.exec

    def _no_block(self):
        opened.append(self)
        self.show()
        return 0
    PVD.PresetVerificationDialog.exec = _no_block
    rec: dict = {"copied": copied, "pulldown": mine, "presets": {}}
    try:
        tab._preset_verify_btn.click()
        pump(app, 2500)
        assert opened, "the button opened no window"
        dlg = opened[0]
        dlg.resize(1220, 780)
        dlg._type_combo.setCurrentIndex(dlg._type_combo.findData(STRICT[0]))
        dlg._set_combo.setCurrentIndex(dlg._set_combo.findData(STRICT[1]))
        pump(app, 1400)
        say(f"## judged as {dlg._type_combo.currentText()!r} against "
            f"{dlg._set_combo.currentText()!r}")
        say("")
        claims = claims_from_readme()
        rec["readme_claims"] = claims
        agree = disagree = 0
        for k, (name, want) in enumerate(sorted(claims.items()), start=1):
            item = row = head = None
            for i in range(dlg._tree.topLevelItemCount()):
                h = dlg._tree.topLevelItem(i)
                for j in range(h.childCount()):
                    c = h.child(j)
                    r = c.data(0, Qt.ItemDataRole.UserRole)
                    if r is not None and r.label == name:
                        head, item, row = h, c, r
            if item is None:
                say(f"    MISSING FROM THE WINDOW: {name}")
                rec["presets"][name] = {"found": False}
                disagree += 1
                continue
            from PyQt6.QtWidgets import QAbstractItemView
            dlg._tree.scrollToItem(
                item, QAbstractItemView.ScrollHint.PositionAtCenter)
            dlg._tree.setCurrentItem(item)
            pump(app, 500)
            said = sorted({w for _r, w in row.assessment.missing})
            detail = []
            for i in range(dlg._detail_layout.count()):
                w = dlg._detail_layout.itemAt(i).widget()
                if w is not None and hasattr(w, "text"):
                    detail.append(w.text())
            ok = (set(want) <= set(said)) if want else (
                not row.assessment.checked)
            agree += bool(ok)
            disagree += (not ok)
            say(f"    {'OK  ' if ok else 'FAIL'} {name}")
            say(f"         group {head.text(0)!r}, chip {item.text(3)!r}, "
                f"patches {row.patches}")
            say(f"         README claims : {want or ['(cannot be checked)']}")
            say(f"         the window says: {said or ['(nothing missing)']}")
            if not row.assessment.checked:
                say(f"         checked=False -> "
                    f"{[d for d in detail if 'Cannot' in d or 'preset' in d]}")
            rec["presets"][name] = {
                "found": True, "group": head.text(0),
                "chip": item.text(3), "patches": row.patches,
                "pages": row.pages, "starred": row.starred,
                "checked": row.assessment.checked,
                "readme": want, "window": said, "agrees": bool(ok),
                "detail": detail}
            p = shots / f"demo-{k:02d}.png"
            okf, why, d = twice(app, dlg, p)
            rec["presets"][name]["frame"] = [okf, why, d]
        say("")
        say(f"## {agree} of {agree + disagree} demo presets say what the "
            f"pack's README claims they will")
        rec["agree"] = agree
        rec["disagree"] = disagree
        dlg.close()
        pump(app, 500)
    finally:
        PVD.PresetVerificationDialog.exec = orig

    (out / "demo-presets.json").write_text(json.dumps(rec, indent=2),
                                           encoding="utf-8")
    (out / "demo-presets.md").write_text("\n".join(log) + "\n",
                                         encoding="utf-8")
    win.close()
    pump(app, 400)
    return 0 if rec.get("disagree") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
