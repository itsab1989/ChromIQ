"""A1 (4.3.50): the app log's session header names every Beta switch.

A new switch on Preferences > Beta that is not in ``core.beta_registry``
fails here: the test reads the Beta page's own save code and checks every key
written from a widget on that page."""
from __future__ import annotations

import inspect
import logging
import re

from core import beta_registry as br
from core.settings import DEFAULTS


class _FakeSettings:
    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def test_every_beta_default_is_registered():
    registered = set(br.BETA_SWITCHES)
    missing = [k for k in DEFAULTS if k.endswith("_beta") and k not in registered]
    assert not missing, missing
    for k in br.LOGGED_KEYS:
        assert k in DEFAULTS, k


def test_every_key_the_beta_page_writes_is_in_the_header(qapp):
    from ui.dialogs import settings_dialog as sd
    dlg = sd.SettingsDialog(_FakeSettings(), None)
    try:
        body = inspect.getsource(sd.SettingsDialog._save_and_close)
        pairs = re.findall(r's\.set\(\s*"(\w+)",\s*(?:\w+\()*\s*self\.(_\w+)', body)
        assert len(pairs) > 30
        on_beta, missing = [], []
        for key, attr in pairs:
            w = getattr(dlg, attr, None)
            if w is None or not hasattr(w, "isVisibleTo"):
                continue
            if dlg._beta_page.isAncestorOf(w):
                on_beta.append(key)
                if key not in br.LOGGED_KEYS:
                    missing.append(key)
        assert len(on_beta) >= 14, on_beta
        assert not missing, f"Beta page keys missing from core/beta_registry.py: {missing}"
    finally:
        dlg.deleteLater()


def test_the_header_names_each_switch_with_its_state(caplog):
    from core.session_header import header_lines, write_session_header
    s = _FakeSettings(ruler_check_beta=True, language="de")
    lines = header_lines(s)
    text = "\n".join(lines)
    for key in br.BETA_SWITCHES + br.BETA_SUB_OPTIONS + br.MEASURE_OPTIONS:
        assert f" {key}=" in text, key
    assert "ruler_check_beta=on" in text and "i1pro2_dual_scan_beta=off" in text
    assert "language=de" in text and "numeric_locale=" in text and "arch=" in text
    assert "chromiq=" in text and "os=" in text and "qt=" in text
    assert "beta_in_effect fd9=" in text and "misalign_safenet=on" in text
    with caplog.at_level(logging.INFO, logger="chromiq.session"):
        write_session_header(s, tools_in_background=False)
    msgs = [r.getMessage() for r in caplog.records if r.name == "chromiq.session"]
    assert any(m.startswith("session: tools argyll=") and "helper_build=" in m for m in msgs)
    assert len(msgs) == len(lines) + 1


#: the keys the test below changes (4.3.64 gate: they leaked into the worker's shared store)
_CHANGED = ("i1pro2_dual_scan_beta", "i1io_table_ask_after_each_step", "log_visible_lines")


def test_a_changed_beta_switch_is_logged_once(caplog, tmp_path, monkeypatch):
    """4.3.64 gate (2026-11-25): this test used to set CHROMIQ_SETTINGS_FILE and believe it was
    writing a scratch file. Under the suite it is not: tests/conftest.py replaces
    core.settings.QSettings with the worker's ONE sandboxed store, whatever path is asked for,
    so log_visible_lines=12 (and the two Beta keys) stayed in that store for every later test on
    the worker. A later window bound to it showed every log at 12 lines, and
    test_log_height_every_tab failed in two gates while passing alone. The store is now a real
    file of this test's own, and the worker's store is checked untouched afterwards."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    shared = AppSettings()
    before = {k: shared.get(k) for k in _CHANGED}
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    with caplog.at_level(logging.INFO, logger="core.settings"):
        s.set("i1pro2_dual_scan_beta", True)
        s.set("i1pro2_dual_scan_beta", True)    # unchanged: no second line
        s.set("i1io_table_ask_after_each_step", False)
        s.set("log_visible_lines", 12)           # not an option the log follows
    msgs = [r.getMessage() for r in caplog.records if "option changed" in r.getMessage()]
    assert msgs == ["option changed: i1pro2_dual_scan_beta=on (was off)",
                    "option changed: i1io_table_ask_after_each_step=off (was on)"]
    assert {k: AppSettings().get(k) for k in _CHANGED} == before    # nothing leaked


def test_every_checkbox_on_the_beta_page_saves_a_key_the_header_names(qapp):
    """S8 (review of 20 Nov): the source-reading check above misses a switch
    saved through a helper method (``self._save_x(s)``, the pattern
    ``_save_misread_table`` uses). This one asks the dialog itself: each
    checkbox on the Beta page is toggled, the page is saved, and the key whose
    value changed must be one the session header names."""
    from PyQt6.QtWidgets import QCheckBox
    from ui.dialogs import settings_dialog as sd

    class _Recording(_FakeSettings):
        def __init__(self):
            super().__init__()
            self.written = []

        def set(self, key, value):
            super().set(key, value)
            self.written.append((key, value))

        def __getattr__(self, _name):
            return lambda *a, **k: None

    s = _Recording()
    dlg = sd.SettingsDialog(s, None)
    try:
        def save():
            s.written = []
            dlg._save_and_close()
            return dict(s.written)
        base = save()
        boxes = dlg._beta_page.findChildren(QCheckBox)
        assert len(boxes) >= 14
        unnamed, silent = [], []
        for box in boxes:
            box.setChecked(not box.isChecked())
            after = save()
            box.setChecked(not box.isChecked())
            save()
            keys = [k for k in after if after.get(k) != base.get(k)]
            if not keys:
                silent.append(box.text()[:50])
            unnamed += [k for k in keys if k not in br.LOGGED_KEYS]
        assert not silent, f"a Beta checkbox whose state saves no key: {silent}"
        assert not unnamed, f"Beta page keys missing from core/beta_registry.py: {unnamed}"
    finally:
        dlg.deleteLater()


def test_the_real_start_up_writes_the_header_once_after_the_latches():
    """S9 (review of 20 Nov): shown on screen that main() writes the header
    once; pinned here. Exactly one call in the whole program, in main(), after
    the Beta latches (so it says what this session runs) and before the main
    window is built (so it precedes every measurement)."""
    import pathlib

    import main as app_main
    root = pathlib.Path(app_main.__file__).resolve().parent
    calls = []
    for sub in ("main.py", "core", "ui", "workflow"):
        p = root / sub
        for f in ([p] if p.is_file() else p.rglob("*.py")):
            if f.name == "session_header.py":
                continue
            if "write_session_header(" in f.read_text(encoding="utf-8"):
                calls.append(f.relative_to(root).as_posix())
    assert calls == ["main.py"], calls
    src = inspect.getsource(app_main.main)
    assert src.count("write_session_header(settings)") == 1
    assert src.index("_latch_page(settings)") < src.index("write_session_header(settings)")
    assert src.index("write_session_header(settings)") < src.index("MainWindow(")
