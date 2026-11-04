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

import pytest                                                  # noqa: E402
from workflow import printer_edges as PE                      # noqa: E402


class _Settings(dict):
    def get(self, k, d=None):
        return super().get(k, d)

    def set(self, k, v):
        self[k] = v


def test_own_route_uses_the_list_and_the_dialog_uses_its_own_printer(
        monkeypatch):
    monkeypatch.setattr(PE, "system_default_printer", lambda: "HP_Default")
    s = _Settings(use_native_print_dialog=False)
    assert PE.note_printer(s, "Canon_IPF9400B") == "Canon_IPF9400B"
    s["use_native_print_dialog"] = True
    # nothing printed through the dialog yet: the printer it opens on
    # (review r1 M1), never the hidden list's
    assert PE.note_printer(s, "Canon_IPF9400B") == "HP_Default"
    s["printer_last_used_by_dialog"] = "EPSON_P900"
    assert PE.note_printer(s, "Canon_IPF9400B") == "EPSON_P900"


def test_no_default_printer_and_nothing_printed_means_no_note(monkeypatch):
    monkeypatch.setattr(PE, "system_default_printer", lambda: "")
    s = _Settings(use_native_print_dialog=True)
    assert PE.note_printer(s, "Canon_IPF9400B") == ""


def test_the_system_default_is_asked_read_only():
    """It is Qt's printer-name query, nothing is sent to a printer."""
    import re
    from pathlib import Path
    src = Path(PE.__file__).read_text(encoding="utf-8")
    body = src[src.index("def _ask_system_default_printer"):]
    body = body[:re.search(r"^def ", body[5:], re.M).start() + 5]
    assert "QPrinterInfo.defaultPrinterName()" in body
    assert "QPrinter(" not in body


def test_r2_l1_the_suite_never_asks_the_host():
    assert PE.system_default_printer() == ""


def test_r2_l2_the_answer_is_remembered_until_the_route_or_a_print_changes(
        monkeypatch):
    asked = []

    def ask():
        asked.append(1)
        return "HP_Default"
    monkeypatch.setattr(PE, "_ask_system_default_printer", ask)
    PE.forget_system_default_printer()
    s = _Settings(use_native_print_dialog=True)
    for _ in range(5):                         # five redraws, one question
        assert PE.note_printer(s, "") == "HP_Default"
    assert len(asked) == 1
    PE.forget_system_default_printer()         # route switched / printed
    assert PE.note_printer(s, "") == "HP_Default" and len(asked) == 2


def test_r2_l2_route_change_and_dialog_print_forget_the_answer():
    import inspect
    from ui.tabs.tab_print import TabPrint
    src = inspect.getsource(TabPrint._refresh_both_edge_notes)
    assert "forget_system_default_printer()" in src
    assert "_refresh_both_edge_notes()" in inspect.getsource(
        TabPrint._set_native_mode)
    assert "_refresh_both_edge_notes()" in inspect.getsource(
        TabPrint._remember_printer_the_dialog_used)


def test_both_tabs_ask_the_same_function():
    import inspect
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_print import TabPrint
    assert "note_printer(" in inspect.getsource(TabPrint._update_edge_note)
    assert "note_printer(" in inspect.getsource(TabChart._printer_edge_notice)
    # switching the route redraws the note at once
    # switching the route redraws both tabs' notes at once
    assert "_refresh_both_edge_notes()" in inspect.getsource(
        TabPrint._set_native_mode)
    assert "_refresh_printer_edge_note" in inspect.getsource(
        TabPrint._refresh_both_edge_notes)


def test_a_dialog_print_remembers_its_printer(qapp, monkeypatch):
    from ui.tabs.tab_print import TabPrint
    s = _Settings(use_native_print_dialog=True)
    seen = []

    class Stand:
        _settings = s

        def _refresh_both_edge_notes(self):
            seen.append(PE.note_printer(s, "Canon_IPF9400B"))
    TabPrint._remember_printer_the_dialog_used(Stand(), "EPSON_P900")
    assert s["printer_last_used_by_dialog"] == "EPSON_P900"
    assert seen == ["EPSON_P900"]
    TabPrint._remember_printer_the_dialog_used(Stand(), "")
    assert s["printer_last_used_by_dialog"] == "EPSON_P900"


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
    assert "_remember_printer_the_dialog_used(_used)" in body("_print_native")
    qt = body("_print_native_qt")
    # Windows: only once the print really went out, after every refusal
    assert "_remember_printer_the_dialog_used(chosen)" in qt
    assert qt.index("_remember_printer_the_dialog_used(chosen)") > qt.index(
        "painter.end()")


def test_r3_a_default_changed_while_open_is_seen_when_a_tab_is_shown(
        monkeypatch):
    answers = ["HP_Default", "HP_Default", "EPSON_Other"]
    asked = []

    def ask():
        asked.append(1)
        return answers[min(len(asked) - 1, len(answers) - 1)]
    monkeypatch.setattr(PE, "_ask_system_default_printer", ask)
    PE.forget_system_default_printer()
    s = _Settings(use_native_print_dialog=True)
    assert PE.note_printer(s, "") == "HP_Default"
    for _ in range(4):                          # redraws ask nothing more
        PE.note_printer(s, "")
    assert len(asked) == 1
    import sys
    monkeypatch.setattr(sys, "platform", "darwin")
    assert PE.recheck_system_default_printer(now=100.0) is False  # same
    assert PE.recheck_system_default_printer(now=200.0) is True   # changed
    assert PE.note_printer(s, "") == "EPSON_Other" and len(asked) == 3


def test_r3_both_tabs_recheck_once_when_shown_and_redraw_only_on_a_change(
        qapp, monkeypatch):
    import inspect
    from ui.tabs.tab_chart import TabChart
    from ui.tabs.tab_print import TabPrint
    assert "_recheck_default_printer()" in inspect.getsource(TabPrint.showEvent)
    assert "_recheck_default_printer()" in inspect.getsource(TabChart.showEvent)
    import sys
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(PE, "RECHECK_INTERVAL_S", 0.0)   # throttle tested apart
    redrawn = []

    class Stand:
        _settings = _Settings(use_native_print_dialog=True)

        def _refresh_printer_edge_note(self):
            redrawn.append(1)
    monkeypatch.setattr(PE, "_ask_system_default_printer", lambda: "A")
    PE.forget_system_default_printer()
    TabChart._recheck_default_printer(Stand())     # first answer: no change
    TabChart._recheck_default_printer(Stand())
    assert redrawn == []
    monkeypatch.setattr(PE, "_ask_system_default_printer", lambda: "B")
    TabChart._recheck_default_printer(Stand())
    assert redrawn == [1]
    Stand._settings = _Settings(use_native_print_dialog=False)
    monkeypatch.setattr(PE, "_ask_system_default_printer",
                        lambda: pytest.fail("asked with ChromIQ's own route"))
    TabChart._recheck_default_printer(Stand())


def test_r3_the_suite_still_gets_no_host_printer():
    PE.forget_system_default_printer()
    assert PE.recheck_system_default_printer() is False
    assert PE.system_default_printer() == ""


def test_final_3_at_most_once_a_minute_and_never_on_linux(monkeypatch):
    import sys
    asked = []
    monkeypatch.setattr(PE, "_ask_system_default_printer",
                        lambda: asked.append(1) or "A")
    monkeypatch.setattr(sys, "platform", "darwin")
    PE.forget_system_default_printer()
    assert PE.recheck_system_default_printer(now=1000.0) is False
    for t in (1001.0, 1030.0, 1059.9):            # tab switches in a minute
        PE.recheck_system_default_printer(now=t)
    assert len(asked) == 1
    PE.recheck_system_default_printer(now=1060.0)
    assert len(asked) == 2
    monkeypatch.setattr(sys, "platform", "linux")
    PE.forget_system_default_printer()
    assert PE.recheck_system_default_printer(now=5000.0) is False
    assert len(asked) == 2                         # Linux: tab show asks nothing
    PE.forget_system_default_printer()             # route change / dialog print
    assert PE.system_default_printer() == "A" and len(asked) == 3
