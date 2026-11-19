"""docs/i1pro2_dual_scan.md (4.3.48): the hand dual-scan guide stays true to the app.

Its pictures are linked from forum posts by their master path, so they must exist under the
names the guide uses, stay small, and every name the guide quotes must be one the app shows.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "i1pro2_dual_scan.md"
PICS = ROOT / "docs" / "i1pro2_dual_scan"


def _text() -> str:
    """The guide with its line breaks inside paragraphs read as spaces."""
    return re.sub(r"[ \t]*\n(?!\n)[ \t]*", " ", GUIDE.read_text(encoding="utf-8"))


def test_every_picture_the_guide_shows_is_in_the_tree_and_small():
    names = re.findall(r"\]\(i1pro2_dual_scan/([^)]+\.png)\)", _text())
    assert len(names) == 11, names
    assert sorted(names) == sorted(p.name for p in PICS.glob("*.png"))
    for n in names:
        assert (PICS / n).stat().st_size <= 400_000, n


def test_the_guide_quotes_the_app_s_own_names():
    from workflow import measurement_messages as M
    from workflow.dual_scan import session
    text = _text()
    assert session.parent_label() in text and session.switch_label() in text
    for msg in (M.M_DUAL_MODEL_ASK, M.M_DUAL_ENDED, M.M_DUAL_BEFORE_START):
        assert msg.render(strip="A", reason="", usb="", where="", chosen="M2")[0] in text
    # the two notes about strips with M0 only (4.3.49), as the Measure tab shows them
    for msg in (M.M_DUAL_CONTINUE_FILL, M.M_DUAL_FILL_OFFER):
        assert msg.render(strips="strips B, C", resume="", start="")[0] in text
    for s in ("Instrument for the dual scan:", "Ask before the next measurement",
              "Another instrument (not an i1Pro 2)", "Spectral filter type (-F)",
              "Skip initial calibration (-N)", "High resolution spectral mode (-H)",
              "M2: UV cut (no UV)", "Build from:"):
        assert s in text, s
    ui = "\n".join(p.read_text(encoding="utf-8") for p in (
        ROOT / "ui/dialogs/settings_dialog.py", ROOT / "ui/tabs/tab_measure.py",
        ROOT / "ui/tabs/tab_profile.py"))
    for s in ("Instrument for the dual scan:", "Ask before the next measurement",
              "Skip initial calibration (-N)", "Build from:"):
        assert s in ui, s


def test_the_file_names_are_the_run_s():
    from core.file_manager import Run
    from workflow.i1pro3_conditions import CONDITION_DIRNAME
    text = _text()
    assert f"{CONDITION_DIRNAME}/<number>-M1.ti3" in text
    p = Run.dual_pass_record(Path("/x/runs/run1/P.ti3"))
    assert p.parent.name == "dual_scan" and p.name == "P.passes.json"
    assert "dual_scan/<project>.passes.json" in text


def test_no_em_dash_and_the_simulation_is_said():
    text = _text()
    assert "—" not in text
    assert "simulated instrument" in text
    assert "no part of it has run on a real" in text.lower()


def test_linked_from_readme_and_the_4348_entry():
    assert "docs/i1pro2_dual_scan.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "docs/i1pro2_dual_scan.md" in log.split("## v4.3.47", 1)[0]
