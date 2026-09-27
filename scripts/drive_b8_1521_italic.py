#!/usr/bin/env python3
"""B8-1521: a parameter help's ``*surface*`` shows in italic, not as
asterisks, driven ON SCREEN in the real app.

    CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_b8_1521_italic.py <out> <en|de> <light|dark>

It clicks the (i) of targen -M ("on the *surface* of the printer's colour
cube") in Create Chart's Manual settings, the way a user does, photographs the
window, and records whether any word still stands between asterisks.

Every modal the drive does not expect is photographed and cancelled by the
K36 watchdog. On top of it, a second watchdog closes any NON-modal top-level
window that is not the one being photographed (the "Auto-update preview"
popup that held another agent's driver, 2026-09-27, among them), photographs
it first, and marks the run: every result recorded after such a window is
flagged `after_unexpected_window` and is not evidence. Settings, presets and
output are sandboxed by `userdrive`, the log by CHROMIQ_LOG_DIR, the ISO file
forced to the repository's own.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 300
_WORD_IN_STARS = re.compile(r"(?<![*\w])\*[^\W\d_][^*\n]{0,40}?[^\W_]\*(?![*\w])")


def _install_window_watchdog(d, rec, allowed):
    """Close, photograph and record any visible top-level dialog that is not
    in *allowed* (a set of objects the drive opened itself)."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QDialog

    def tick():
        for w in QApplication.topLevelWidgets():
            if (not w.isVisible() or w is d.win or w in allowed
                    or not isinstance(w, QDialog)
                    or type(w).__name__ in K36.EXPECTED):
                continue
            n = len(rec.setdefault("unexpected_windows", [])) + 1
            try:
                from onscreen_capture import capture_window
                capture_window(w, d.shots / f"unexpected-{n:02d}.png")
            except Exception:                              # noqa: BLE001
                pass
            rec["unexpected_windows"].append(
                {"type": type(w).__name__, "title": w.windowTitle(),
                 "text": d.modal_text(w)[:300]})
            rec["after_unexpected_window"] = True
            w.close()

    t = QTimer(d.win)
    t.timeout.connect(tick)
    t.start(400)
    return t


def script(lang: str, look: str):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "appearance": look, "mode": "ON SCREEN"})
        assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
        K36._install_watchdog(d, rec)
        allowed: set = set()
        _install_window_watchdog(d, rec, allowed)
        from PyQt6.QtWidgets import QLabel
        from ui.tooltip_button import TooltipButton
        yield 800
        d.goto_tab("chart")
        yield 1500
        # the (i) whose body carries the -M text in this language
        needle = {"en": "*surface*", "de": "*Oberfläche*"}[lang]
        btns = [b for b in d.win.findChildren(TooltipButton)
                if needle in (b.dialog_body() or "")]
        rec["found"] = len(btns)
        if not btns:
            return
        K36.EXPECTED.add("_InfoDialog")
        d.later(btns[0].click)
        info = None
        for _ in range(30):
            yield 200
            m = d.modal()
            if m is not None and type(m).__name__ == "_InfoDialog":
                info = m
                break
        if info is None:
            rec["missing"] = True
            K36.EXPECTED.discard("_InfoDialog")
            return
        allowed.add(info)
        info.resize(max(info.width(), 700), 760)
        yield 800
        body = max((lab for lab in info.findChildren(QLabel) if lab.wordWrap()),
                   key=lambda lab: len(lab.text()))
        shown = re.sub(r"<[^>]+>", "", body.text())
        rec["window"] = {
            "title": info.windowTitle(),
            "rich": body.textFormat().name,
            "italic_runs": body.text().count("<i>"),
            "bold_runs": body.text().count("<b>"),
            "words_in_asterisks_shown": _WORD_IN_STARS.findall(shown),
        }
        d.shot(info, f"{lang}-{look}-targen-M-help")
        info.close()
        K36.EXPECTED.discard("_InfoDialog")
        yield 700
    return s


def main() -> int:
    out = Path(sys.argv[1])
    lang, look = sys.argv[2], sys.argv[3]
    d = Drive(out, projects=[], language=lang, appearance=look)
    rc = d.run(script(lang, look))
    (out / f"{lang}-{look}-record.json").write_text(
        json.dumps(d.record, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    print(f"rc={rc}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
