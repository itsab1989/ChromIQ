"""The native dialog owns printer selection, not the hidden direct-print queue."""
from types import SimpleNamespace
from PyQt6.QtWidgets import QLabel
from ui.tabs.tab_print import TabPrint


def test_native_dialog_hides_a_stale_9400b_queue_note(qapp):
    label = QLabel("Canon_IPF9400B: stale margin warning")
    label.show()
    settings = SimpleNamespace(get=lambda key, default=None: True if key == "use_native_print_dialog" else default)
    calls=[]
    def queue():
        calls.append("Canon_IPF9400B")
        return "Canon_IPF9400B"
    tab = SimpleNamespace(_edge_note_lbl=label, _settings=settings,
                          _printer_combo=SimpleNamespace(currentData=queue),
                          _preview=SimpleNamespace(_pages=[("invented.tif",1)]))
    TabPrint._update_edge_note(tab)
    assert label.isHidden() and label.text() == "" and calls == []
    label.deleteLater()
