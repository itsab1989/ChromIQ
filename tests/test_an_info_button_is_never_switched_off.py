"""An ⓘ always opens its explanation, even beside a greyed control.

Basti, 2026-10-25: the ⓘ beside "Measure my speed" did nothing, because the
button-shortcuts section switched it off with the rest of its controls.
`TooltipButton` deliberately stays enabled when its parent is disabled; only
an explicit `setEnabled(False)` silences it, so no app code may make one.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_no_app_code_switches_an_info_button_off():
    offenders = []
    for path in list((ROOT / "ui").rglob("*.py")) + list((ROOT / "workflow").rglob("*.py")):
        if path.name == "tooltip_button.py":
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"(\w*(?:tip|tooltip)\w*)\.setEnabled\(([^)]*)\)", text):
            if m.group(2).strip() != "True":
                line = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}: {m.group(0)}")
    assert not offenders, "an ⓘ must stay clickable:\n" + "\n".join(offenders)


def test_the_measure_my_speed_info_button_stays_clickable(qtbot):
    from core.settings import AppSettings
    from ui.button_shortcuts_section import ButtonShortcutsSection
    sec = ButtonShortcutsSection(AppSettings(), lambda: {"family": "colormunki",
                                                         "name": "ColorMunki"})
    qtbot.addWidget(sec)
    sec._enable_cb.setChecked(False)
    sec._sync_enabled()
    assert not sec._speed_btn.isEnabled()
    assert sec._speed_tip.isEnabled()
    assert sec._try_tip.isEnabled()
