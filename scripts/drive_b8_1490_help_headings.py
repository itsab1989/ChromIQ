#!/usr/bin/env python3
"""B8-1490 (Knut, #182 5856723428): the help windows show their topic
lead-ins and headings in bold, driven ON SCREEN in the real app.

    CHROMIQ_LOG_DIR=<sandbox> \\
        python scripts/drive_b8_1490_help_headings.py <out> <en|de> <light|dark>

What it photographs, every (i) clicked the way a user clicks it (its own
exec() runs; the drive keeps going inside it):

* Report Limits: the (i) of "Maximum ΔE00, between two of the nine sheet
  areas" (top, middle, bottom: the three headings, the evenness lead-ins and
  "may come from the instrument"), the (i) of "one sheet area against the
  whole sheet", and the (i) of the paper row, another metric;
* the Measure tab's own (i) ("Before you start:", "How to use this screen:");
* the Create Chart tab's own (i);
* a Preferences (i) ("Misalignment safety net");
* the help card "Your first profile", which draws its headings itself.

Every modal the drive does not expect is photographed and cancelled by the
watchdog; a deadline ends the run. Settings, presets and output are
sandboxed by `userdrive`, the log by CHROMIQ_LOG_DIR, the ISO file forced to
the repository's own.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

TREE = os.environ.get("CHROMIQ_TREE") or str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TREE + "/scripts")
sys.path.insert(0, TREE)
from userdrive import Drive                                    # noqa: E402
import drive_b42_k36 as K36                                    # noqa: E402

K36.DEADLINE_S = 600

MEASURE_HELP = "On this screen, your spectrophotometer reads every"
CHART_HELP = "This is where you design the sheet of colour patches"


def _key(prefix: str) -> str:
    cat = json.loads((Path(TREE) / "data" / "i18n" / "de.json").read_text(
        encoding="utf-8"))
    hits = [k for k in cat if k.startswith(prefix)]
    assert len(hits) == 1, (prefix, len(hits))
    return hits[0]


def script(lang: str, look: str):
    def s(d):
        rec = d.record
        rec.update({"language": lang, "appearance": look,
                    "mode": "ON SCREEN"})
        assert os.environ.get("CHROMIQ_LOG_DIR"), "SANDBOX THE LOG FIRST"
        K36._install_watchdog(d, rec)
        from core.help_markup import bold_runs, has_markup
        from core.i18n import tr
        from PyQt6.QtWidgets import QLabel, QScrollArea
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        from ui.tooltip_button import TooltipButton
        yield 600

        def open_info(btn, name, *, scroll=(), tall=900):
            """Click *btn* as a user does; photograph the (i) window at the
            top and at each fraction of its scroll in *scroll*."""
            K36.EXPECTED.add("_InfoDialog")
            d.later(btn.click)
            for _ in range(30):
                yield 200
                info = d.modal()
                if info is not None and type(info).__name__ == "_InfoDialog":
                    break
            else:
                rec.setdefault("missing", []).append(name)
                K36.EXPECTED.discard("_InfoDialog")
                return
            info.resize(max(info.width(), 640), tall)
            yield 700
            labels = [lab for lab in info.findChildren(QLabel) if lab.wordWrap()]
            body = max(labels, key=lambda lab: len(lab.text()))
            rec.setdefault("windows", {})[name] = {
                "rich": body.textFormat().name,
                "bold": body.text().count("<b>"),
                "asterisks_shown": "**" in body.text().replace("<b>", "")
                .replace("</b>", ""),
            }
            d.shot(info, f"{lang}-{look}-{name}")
            for i, frac in enumerate(scroll, start=1):
                for sa in info.findChildren(QScrollArea):
                    sb = sa.verticalScrollBar()
                    sb.setValue(int(sb.maximum() * frac))
                    yield 600
                    d.shot(info, f"{lang}-{look}-{name}-{i}")
                    break
            info.close()
            K36.EXPECTED.discard("_InfoDialog")
            yield 700

        # 1. REPORT LIMITS: three (i) windows
        td = ThresholdsDialog(d.settings, d.win)
        td.resize(1480, 960)
        td.show()
        td.raise_()
        yield 2000
        for rid, name, scroll in (
                ("uniformity_sd", "01-evenness-between-two-areas", (0.5, 1.0)),
                ("uniformity_de00_max_from_mean", "02-evenness-one-area", ()),
                ("substrate_de00_max", "03-paper-row", ())):
            lab = td._row_labels[rid]
            td._scroll.ensureWidgetVisible(lab, 0, 260)
            yield 500
            btn = lab.parent().findChildren(TooltipButton)[0]
            rec.setdefault("bodies", {})[name] = bold_runs(btn.dialog_body())
            yield from open_info(btn, name, scroll=scroll, tall=960)
        td.close()
        yield 800

        # 2. THE MEASURE TAB'S OWN (i)
        want = {MEASURE_HELP: ("measure", "04-measure-tab"),
                CHART_HELP: ("chart", "05-create-chart-tab")}
        for prefix, (tab, name) in want.items():
            d.goto_tab(tab)
            text = tr(_key(prefix)).strip()
            btns = [b for b in d.win.findChildren(TooltipButton)
                    if b.dialog_body().strip() == text]
            rec.setdefault("found", {})[name] = len(btns)
            if btns:
                rec.setdefault("bodies", {})[name] = bold_runs(text)
                yield from open_info(btns[0], name)

        # 3. A PREFERENCES (i): "Misalignment safety net"
        from ui.dialogs.settings_dialog import SettingsDialog
        sd = SettingsDialog(d.settings, d.win)
        sd.show()
        yield 1800
        title = tr("Misalignment safety net")
        btns = [b for b in sd.findChildren(TooltipButton) if b._title == title]
        rec.setdefault("found", {})["06-preferences"] = len(btns)
        if btns:
            b = btns[0]
            # bring its page forward: walk up to the tab page that holds it
            from PyQt6.QtWidgets import QTabWidget
            for tw in sd.findChildren(QTabWidget):
                for i in range(tw.count()):
                    if tw.widget(i).isAncestorOf(b):
                        tw.setCurrentIndex(i)
            yield 800
            rec["bodies"]["06-preferences"] = bold_runs(b.dialog_body())
            yield from open_info(b, "06-preferences")
        sd.close()
        yield 800

        # 4. A HELP CARD, which draws its own headings
        d.win.open_welcome_dialog()
        yield 1800
        wd = K36._wait(d, "WelcomeDialog")
        if wd is not None:
            wd.resize(1100, 900)
            wd._on_card_clicked("first_profile")
            yield 1500
            d.shot(wd, f"{lang}-{look}-07-help-card")
            wd.close()
        yield 800
        rec["marks_in_bodies"] = {k: len(v) for k, v in rec.get("bodies", {}).items()}
        rec["no_asterisks_shown"] = not any(
            w.get("asterisks_shown") for w in rec.get("windows", {}).values())
        rec["has_markup_check"] = has_markup("**a** b")
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
