#!/usr/bin/env python3
"""Apply a named mutation to the tree, run a test selection, restore the tree.

Every fix in this round records its mutation here and the result it produced, so
"proven to land" is a file somebody can re-run rather than a claim.

    python proof_adv2/mutate.py <name>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"

#: name -> (file, old, new, pytest target)
MUTATIONS = {
    # ---- F1: the Create Chart progress line ------------------------------
    "F1-flag-not-refreshed": (
        "ui/widgets.py",
        "        self._following_tail = self.is_at_bottom()\n"
        "        cur = self.textCursor()",
        "        cur = self.textCursor()",
        "tests/test_a_log_pane_follows_the_tail_only_from_the_bottom.py",
    ),
    "F1-cursor-guard-removed": (
        "ui/widgets.py",
        "    def setTextCursor(self, cursor) -> None:               # noqa: N802\n"
        "        if self._following_tail:",
        "    def setTextCursor(self, cursor) -> None:               # noqa: N802\n"
        "        if True:",
        "tests/test_a_log_pane_follows_the_tail_only_from_the_bottom.py",
    ),
    "F1-tab-does-the-cursor-work-again": (
        "ui/tabs/tab_chart.py",
        "        if self._progress_line_active:\n"
        "            self._log.replace_last_line(text)",
        "        if self._progress_line_active:\n"
        "            from PyQt6.QtGui import QTextCursor\n"
        "            cur = self._log.textCursor()\n"
        "            cur.movePosition(QTextCursor.MoveOperation.End)\n"
        "            cur.select(QTextCursor.SelectionType.LineUnderCursor)\n"
        "            cur.removeSelectedText()\n"
        "            cur.insertText(text)\n"
        "            self._log.setTextCursor(cur)",
        "tests/test_a_log_pane_follows_the_tail_only_from_the_bottom.py",
    ),
    # ---- F2: the placeholder-source allowlist ----------------------------
    "F2-placeholder-takes-a-quick-check-number": (
        "workflow/compliance_sets.py",
        '    "cmy_solids_dhab_max": Limit.value(2.0),         # ΔH*ab',
        '    "cmy_solids_dhab_max": Limit.value(4.0),         # ΔH*ab',
        "tests/test_compliance_sets.py",
    ),
    "F2-placeholder-takes-a-tight-number": (
        "workflow/compliance_sets.py",
        '    "substrate_de00_max": Limit.value(3.0),          # ΔE00',
        '    "substrate_de00_max": Limit.value(1.0),          # ΔE00',
        "tests/test_compliance_sets.py",
    ),
    # ---- F3: a device-less measurement with no chart ---------------------
    "F3-no-chart-is-accepted-again": (
        "workflow/measurement_import.py",
        "    if not measured.has_device:\n"
        "        if chart_ti2 is None:",
        "    if not measured.has_device and chart_ti2 is not None:\n"
        "        if False:",
        "tests/test_a_measurement_without_device_values_is_imported.py",
    ),
    # ---- F4: the "always built" list was checked by grepping ------------
    "F4-a-conditional-block-joins-the-always-list": (
        "ui/dialogs/measurement_report_dialog.py",
        'ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", "ramps_30_70",\n'
        '                                          "summary_patches")',
        'ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", "ramps_30_70",\n'
        '                                          "summary_patches",\n'
        '                                          "gamut_split")',
        "tests/test_a_row_that_was_never_computed_is_rebuilt.py",
    ),
    # The realistic form: a developer adds a block to the tuple AND to the set
    # the sibling test pins, exactly as the three real blocks were added. Only
    # a test that RUNS the builder can tell a conditional block from an
    # unconditional one.
    "F4-a-developer-adds-a-conditional-block-properly": (
        "ui/dialogs/measurement_report_dialog.py",
        'ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", "ramps_30_70",\n'
        '                                          "summary_patches")',
        'ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", "ramps_30_70",\n'
        '                                          "summary_patches",\n'
        '                                          "gamut_split")',
        "tests/test_a_row_that_was_never_computed_is_rebuilt.py"
        "::test_every_block_in_the_list_really_is_always_built",
    ),
}


def run(name: str) -> int:
    f, old, new, target = MUTATIONS[name]
    p = ROOT / f
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        print(f"!! the mutation site appears {text.count(old)} times in {f}; "
              "the mutation CANNOT be proven to land")
        return 2
    p.write_text(text.replace(old, new), encoding="utf-8")
    try:
        r = subprocess.run(
            [PY, "-m", "pytest", target, "-q", "--no-header"],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
            env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"})
        tail = [ln for ln in r.stdout.splitlines() if ln.strip()][-4:]
        out = {"mutation": name, "file": f, "target": target,
               "exit": r.returncode, "tail": tail,
               "landed": r.returncode != 0}
    finally:
        p.write_text(text, encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0 if out["landed"] else 1


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in MUTATIONS:
        print("names:", ", ".join(MUTATIONS))
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
