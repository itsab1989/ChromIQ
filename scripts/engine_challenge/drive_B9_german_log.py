"""B9 — wording and i18n on screen (S20, S24).

App booted in GERMAN (the harness applies `set_language("de")` exactly as
main.py does). Manual + accurate, all four engine rows on, gamut source -S
ClayRGB1998.icm (so every stage prints). Build, dump every log line, and
classify each: translated (German), an English source string that HAS a
German entry but was not routed through tr(), or an English f-string with
no catalogue entry at all.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_924, ROOT, WORK_B, build_and_answer, click, grab, pick,
    run_journey, sandbox, say)

OUT = WORK_B / "B9"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []
CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"
PREFIX = re.compile(r"^\d+% · (?:[^·]+· )?")


def classify(line: str, de: dict) -> str:
    body = PREFIX.sub("", line).strip()
    if not body:
        return "blank"
    if body in de.values():
        return "GERMAN"
    if body in de:
        return "ENGLISH (has a German entry, not routed through tr)"
    # a formatted line: does some key's static text match after placeholders?
    for k in de:
        if "{" in k:
            pat = "^" + re.escape(k)
            pat = re.sub(r"\\\{[^}]*\\\}", ".*?", pat) + "$"
            if re.match(pat, body, re.S):
                return "ENGLISH (has a German entry, not routed through tr)"
    for v in de.values():
        if "{" in v:
            pat = "^" + re.sub(r"\\\{[^}]*\\\}", ".*?", re.escape(v)) + "$"
            if re.match(pat, body, re.S):
                return "GERMAN"
    return "ENGLISH (no catalogue entry — f-string)"


def journey(h, de):
    win, prof = h.win, h.win._tab_profile
    h.go_profile_tab("manual")
    yield 400
    say(f"tab title={win._tabs.tabText(win._tabs.currentIndex())!r} build btn={prof._build_btn.text()!r} "
        f"rows: {prof._m_spectral_cb.text()!r} / {prof._m_noise_cb.text()!r}")
    click(prof._m_spectral_cb); yield 150
    click(prof._m_noise_cb); yield 150
    pick(prof._m_render_combo, prof._m_render_combo.itemText(1)); yield 150
    pick(prof._m_iccver_combo, prof._m_iccver_combo.itemText(2)); yield 150
    pick(prof._m_gam_mode_combo, prof._m_gam_mode_combo.itemText(2)); prof._m_gam_path_edit.setText(CLAY); yield 150
    say(f"rows: spectral={prof._m_spectral_cb.isChecked()} noise={prof._m_noise_cb.isChecked()} "
        f"render={prof._m_render_combo.currentData()} iccver={prof._m_iccver_combo.currentData()} gam={prof._m_gam_mode_combo.currentData()}")
    grab(win, OUT / "manual-de.png")
    el, title = yield from build_and_answer(h, OUT, "de", SEEN, answer=("Fertig", "Done", "OK", "Schließen", "Close"), shots=(15,))
    lines = prof._log.toPlainText().splitlines()
    seen = set()
    table = []
    for ln in lines:
        body = PREFIX.sub("", ln).strip()
        key = re.sub(r"\d+/\d+", "k/n", body)
        if key in seen:
            continue
        seen.add(key)
        table.append((classify(ln, de), ln))
    (OUT / "de-lines.json").write_text(json.dumps(table, indent=1, ensure_ascii=False), encoding="utf-8")
    say(f"distinct log lines: {len(table)}")
    for cls, ln in table:
        say(f"  [{cls}] {ln}")


def main() -> int:
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    de = {k: v for k, v in de.items() if not k.startswith("@")}
    h = Harness(sandbox("B9"), language="de")
    h.boot()
    h.make_project("Real-924", CHART_924)
    h.enable_engine("accurate")
    h.open_project("Real-924")
    run_journey(h, journey(h, de), timeout=900)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
