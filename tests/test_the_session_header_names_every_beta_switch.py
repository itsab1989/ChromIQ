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


def test_a_changed_beta_switch_is_logged_once(caplog, tmp_path, monkeypatch):
    from core.settings import AppSettings
    monkeypatch.setenv("CHROMIQ_SETTINGS_FILE", str(tmp_path / "s.ini"))
    s = AppSettings()
    with caplog.at_level(logging.INFO, logger="core.settings"):
        s.set("i1pro2_dual_scan_beta", True)
        s.set("i1pro2_dual_scan_beta", True)    # unchanged: no second line
        s.set("i1io_table_ask_after_each_step", False)
        s.set("log_visible_lines", 12)           # not an option the log follows
    msgs = [r.getMessage() for r in caplog.records if "option changed" in r.getMessage()]
    assert msgs == ["option changed: i1pro2_dual_scan_beta=on (was off)",
                    "option changed: i1io_table_ask_after_each_step=off (was on)"]
