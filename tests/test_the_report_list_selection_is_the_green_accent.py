"""The Measurement Report's measurement list highlights a row in the window's
own green, not in the application's cyan.

Basti, 2026-09-18, on a photograph of that list::

    when i click the demo switching in the list it gets a cyan overlay. should
    be the green accent color instead

Where the cyan came from: one app-wide rule in `ui/styles.py`,
``QListWidget::item:selected { background: {ACCENT} }`` with
``ACCENT = SPEC_CYAN``. Every other accent in this window is ``SPEC_GREEN``
already: the info icons, the help buttons and the two tick boxes. It is
overridden on the one list he pointed at rather than app-wide, because that one
line repaints every list in ChromIQ and that is his call.

Photographed before and after in a real window on a real screen:
``~/Desktop/ChromIQ-beta22-proof/b383-the-document-record/``
(`S1-selected-row-cyan-BEFORE.png`, `S2-selected-row-green-AFTER.png`).
"""
from __future__ import annotations

import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _dialog(tmp_path, qapp):
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    s, _fm, _ctl, run = _verify_env(tmp_path)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.show()
    qapp.processEvents()
    return dlg


def test_the_selected_measurement_row_is_the_green_accent(tmp_path, qapp):
    """MUTATION: drop the `setStyleSheet` on `_profile_list` and this goes red.
    """
    from ui.styles import SPEC_CYAN, SPEC_GREEN
    dlg = _dialog(tmp_path, qapp)
    try:
        css = dlg._profile_list.styleSheet()
        assert "item:selected" in css, (
            "the list takes the application's own selection colour, which is "
            f"{SPEC_CYAN}")
        m = re.search(r"background:\s*(#[0-9a-fA-F]{6})", css)
        assert m and m.group(1).lower() == SPEC_GREEN.lower(), css
        assert SPEC_CYAN.lower() not in css.lower()
    finally:
        dlg.close()


def test_the_text_on_it_is_dark_enough_to_read(tmp_path, qapp):
    """SPEC_GREEN is a LIGHT colour and white on it is the contrast fault this
    project has fixed twice elsewhere.

    MUTATION: set `color: #ffffff` and this goes red.
    """
    from ui.styles import SPEC_GREEN
    dlg = _dialog(tmp_path, qapp)
    try:
        css = dlg._profile_list.styleSheet()
        m = re.search(r"color:\s*(#[0-9a-fA-F]{6})", css)
        assert m, css

        def lum(h: str) -> float:
            h = h.lstrip("#")
            c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
                 for x in c]
            return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

        a, b = sorted((lum(m.group(1)), lum(SPEC_GREEN)))
        assert (b + 0.05) / (a + 0.05) >= 4.5, (
            f"the selected row's text scores {(b + 0.05) / (a + 0.05):.2f}:1 "
            f"on {SPEC_GREEN}")
    finally:
        dlg.close()
