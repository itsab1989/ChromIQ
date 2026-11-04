"""4.3.24 (lessbones, #214; review M2): with the system print dialog, the edge
note never names the hidden direct-print printer.

ChromIQ's own route has a printer list on the Print Chart tab, and the note
(M-EDGE-NOT-PRINTED) is about the printer chosen there. With the system print
dialog that list is hidden and can still hold a queue nobody prints to (his:
a Canon iPF9400B), so a note naming it was about a printer not in use. The
note is now about the printer the system dialog last printed to, and there is
no note until something has been printed that way. Create Chart and Print
Chart ask the same function, so they cannot disagree. No real printer is
asked: the driver query is replaced.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import printer_edges as PE                      # noqa: E402


class _Settings(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def test_own_route_uses_the_list_and_the_dialog_uses_its_own_printer():
    s = _Settings(use_native_print_dialog=False)
    assert PE.note_printer(s, "Canon_IPF9400B") == "Canon_IPF9400B"
    s["use_native_print_dialog"] = True
    assert PE.note_printer(s, "Canon_IPF9400B") == ""        # none printed yet
    s["native_dialog_printer"] = "EPSON_P900"
    assert PE.note_printer(s, "Canon_IPF9400B") == "EPSON_P900"


def test_both_tabs_ask_the_same_function():
    import inspect
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_print import TabPrint
    assert "note_printer(" in inspect.getsource(TabPrint._update_edge_note)
    assert "note_printer(" in inspect.getsource(TabChart._printer_edge_notice)
    # switching the route redraws the note at once
    assert "_update_edge_note()" in inspect.getsource(TabPrint._set_native_mode)


def test_a_dialog_print_remembers_its_printer(qapp, monkeypatch):
    from ui.tabs.tab_print import TabPrint
    s = _Settings(use_native_print_dialog=True)
    seen = []

    class Stand:
        _settings = s

        def _update_edge_note(self):
            seen.append(PE.note_printer(s, "Canon_IPF9400B"))

        def window(self):
            return None
    TabPrint._remember_dialog_printer(Stand(), "EPSON_P900")
    assert s["native_dialog_printer"] == "EPSON_P900"
    assert seen == ["EPSON_P900"]
    TabPrint._remember_dialog_printer(Stand(), "")
    assert s["native_dialog_printer"] == "EPSON_P900"


def test_both_dialog_routes_remember_the_printer():
    """Read from the file: the suite replaces both dialog routes (no real
    print dialog may open in a test)."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "ui" / "tabs"
           / "tab_print.py").read_text(encoding="utf-8")

    def body(name):
        start = src.index(f"    def {name}(")
        nxt = re.search(r"^    def ", src[start + 10:], re.M)
        return src[start:start + 10 + (nxt.start() if nxt else len(src))]
    assert "_remember_dialog_printer(_used)" in body("_print_native")
    assert "_remember_dialog_printer(chosen)" in body("_print_native_qt")
