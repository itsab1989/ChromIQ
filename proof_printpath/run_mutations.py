#!/usr/bin/env python3
"""Every mutation, and the proof it LANDED.

A test that does not fail when the thing it guards is broken guards nothing.
This applies each mutation to the tree that would be committed, runs the test
file, records the result, and puts the tree back. `__pycache__` is purged
between every step.

    python proof_printpath/run_mutations.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"
TESTFILE = "tests/test_a_log_pane_follows_the_tail_only_from_the_bottom.py"

W = ROOT / "ui" / "widgets.py"
CHART = ROOT / "ui" / "tabs" / "tab_chart.py"
SPOT = ROOT / "ui" / "dialogs" / "spot_read_dialog.py"

#: (name, file, old, new, the test that must go red)
MUTATIONS = [
    ("M1 the bottom is sampled AFTER the text arrives, not before", W,
     """        follow = self.is_at_bottom()
        call(*args)
        self._following_tail = follow""",
     """        call(*args)
        follow = self.is_at_bottom()
        self._following_tail = follow""",
     "test_an_insert_at_the_top_keeps_the_reader_at_the_bottom"),

    ("M2 ensureCursorVisible obeys everyone again", W,
     """    def ensureCursorVisible(self) -> None:                 # noqa: N802
        if self._following_tail:
            super().ensureCursorVisible()""",
     """    def ensureCursorVisible(self) -> None:                 # noqa: N802
        super().ensureCursorVisible()""",
     "test_a_pane_the_reader_scrolled_up_is_left_alone"),

    ("M3 the append stops pinning the bottom itself", W,
     """        self._following_tail = follow
        if follow:
            sb = self.verticalScrollBar()
            sb.setValue(sb.maximum())""",
     """        self._following_tail = follow""",
     "test_an_insert_at_the_top_keeps_the_reader_at_the_bottom"),

    ("M4 clear() no longer starts following again", W,
     """    def clear(self) -> None:
        self._following_tail = True
        super().clear()""",
     """    def clear(self) -> None:
        super().clear()""",
     "test_clearing_the_pane_starts_following_again"),

    ("M5 setPlainText() no longer starts following again", W,
     """    def setPlainText(self, text: str) -> None:             # noqa: N802
        self._following_tail = True
        super().setPlainText(text)""",
     """    def setPlainText(self, text: str) -> None:             # noqa: N802
        super().setPlainText(text)""",
     "test_set_plain_text_starts_following_again"),

    ("M6 a cursor handed in scrolls the view again", W,
     """        sb = self.verticalScrollBar()
        where = sb.value()
        super().setTextCursor(cursor)
        sb.setValue(where)""",
     """        super().setTextCursor(cursor)""",
     "test_a_cursor_handed_to_the_pane_does_not_drag_the_view"),

    ("M7 'at the bottom' grows a one-line tolerance", W,
     "        return sb.value() >= sb.maximum()",
     "        return sb.value() >= sb.maximum() - 1",
     "test_a_reader_one_line_up_is_not_at_the_bottom"),

    ("M7b 'at the bottom' swallows the whole document", W,
     "        return sb.value() >= sb.maximum()",
     "        return True",
     "test_a_pane_the_reader_scrolled_up_is_left_alone"),

    ("M8 'at the bottom' stops including the bottom itself", W,
     "        return sb.value() >= sb.maximum()",
     "        return sb.value() > sb.maximum()",
     "test_a_short_document_that_cannot_scroll_still_follows"),

    ("M9 TailFollowLog subscribes to the scroll bar", W,
     "        self._following_tail = True\n\n    # -- the question ",
     "        self._following_tail = True\n        self.verticalScrollBar()"
     ".valueChanged.connect(self._noop)\n\n    def _noop(self, _v) -> None:\n"
     "        pass\n\n    # -- the question ",
     "test_the_tail_follow_pane_connects_nothing_to_a_scroll_bar_signal"),

    ("M10 the Create Chart pane goes back to a bare QPlainTextEdit", CHART,
     "        self._log = TailFollowLog(self)",
     "        self._log = QPlainTextEdit(self)",
     "test_no_log_pane_is_a_bare_QPlainTextEdit"),

    ("M11 the spot-read table asks after inserting the row", SPOT,
     """        sb = self._table.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum()
        self._table.blockSignals(True)
        row = self._table.rowCount()
        self._table.insertRow(row)""",
     """        self._table.blockSignals(True)
        row = self._table.rowCount()
        self._table.insertRow(row)
        sb = self._table.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum()""",
     "test_the_spot_read_results_table_follows_the_same_rule"),

    ("M12 the spot-read table scrolls unconditionally again", SPOT,
     """        if at_bottom:
            self._table.scrollToBottom()""",
     """        self._table.scrollToBottom()""",
     "test_the_spot_read_results_table_follows_the_same_rule"),
]


def purge() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".git" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run(expr: str) -> "tuple[int, str]":
    purge()
    p = subprocess.run(
        [PY, "-m", "pytest", TESTFILE, "-q", "-p", "no:randomly",
         "-k", expr, "--no-header"],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
    tail = [l for l in p.stdout.splitlines() if l.strip()][-1:]
    return p.returncode, (tail[0] if tail else "")


def main() -> int:
    results = []

    code, line = run("")
    print(f"BASELINE  exit {code}  {line}")
    results.append({"mutation": "BASELINE (no mutation)", "exit": code,
                    "summary": line, "landed": code == 0})
    if code != 0:
        print("the baseline is not green; stopping")
        return 1

    for name, path, old, new, test in MUTATIONS:
        src = path.read_text(encoding="utf-8")
        n = src.count(old)
        if n != 1:
            print(f"!! {name}: the mutation text appears {n} times in "
                  f"{path.name}; it must be applied exactly once")
            results.append({"mutation": name, "applied": False, "count": n})
            continue
        path.write_text(src.replace(old, new), encoding="utf-8")
        try:
            code, line = run(test)
        finally:
            path.write_text(src, encoding="utf-8")
        landed = code != 0
        print(f"{'LANDED ' if landed else 'MISSED '} {name}\n"
              f"           -> {test}: exit {code}  {line}")
        results.append({"mutation": name, "file": str(path.relative_to(ROOT)),
                        "test": test, "exit": code, "summary": line,
                        "landed": landed})

    purge()
    code, line = run("")
    print(f"RESTORED  exit {code}  {line}")
    results.append({"mutation": "RESTORED (tree back as committed)",
                    "exit": code, "summary": line, "landed": code == 0})

    out = ROOT / "proof_printpath" / "mutations.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    missed = [r for r in results if r.get("landed") is False
              and "BASELINE" not in r["mutation"]
              and "RESTORED" not in r["mutation"]]
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
