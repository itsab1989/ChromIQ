"""The "Strip Read Quickly" window names the same strip time as the line under
the preview (Knut, #202 5951426710, beta 2 on an i1Pro 2).

27 patches at 120 ms are 3.24 s. The line under the preview said "3.3 sec. or
more per strip" (rounded UP, `strip_limit_phrase`), the window said "Reading the
whole strip in about 3 s", rounded to the nearest second, which is below the
limit it was telling him to stay above.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _Fake(QWidget):
    pass


def _window_text(qapp, monkeypatch, target_s, patches, mean_s):
    from ui.tabs.tab_measure import TabMeasure
    seen = {}

    def _exec(_self, dlg):
        seen["text"] = " ".join(l.text() for l in dlg.findChildren(QLabel))
    fake = _Fake()
    fake._manager = SimpleNamespace(engine_active=True)
    fake._exec_measurement_window = lambda dlg: _exec(fake, dlg)
    fake._log = SimpleNamespace(appendPlainText=lambda *_: None,
                                ensureCursorVisible=lambda: None)
    pace = SimpleNamespace(mean_seconds=mean_s, patches=patches,
                           elapsed=mean_s * patches, est_samples=23)
    from core.measure_pace import PaceConfig
    config = PaceConfig(min_samples=24, sample_hz=0.0,
                        min_patch_seconds=target_s)
    TabMeasure._prompt_too_fast_strip(fake, "A", pace, config)
    return seen["text"]


def test_27_patches_at_120_ms_read_3_3_s(qapp, monkeypatch):
    text = _window_text(qapp, monkeypatch, 0.120, 27, 0.115)
    # and with the rate-based config an i1Pro 2 really has (24 at 200 Hz)
    from core.measure_pace import PaceConfig
    from ui.tabs.tab_measure import TabMeasure  # noqa: F401
    assert "<b>3.3 s</b>" in text, text
    assert "<b>120 ms</b>" in text


def test_the_window_and_the_line_under_the_preview_agree(qapp, monkeypatch):
    from core.measure_pace import PaceConfig, strip_limit_phrase
    for target, n in ((0.120, 27), (0.240, 25), (0.165, 30), (0.0333, 18)):
        text = _window_text(qapp, monkeypatch, target, n, target * 0.9)
        cfg = PaceConfig(min_samples=24, sample_hz=0.0,
                         min_patch_seconds=target)
        line = strip_limit_phrase(cfg, n)
        secs = line.split("— ")[1].split(" sec.")[0]
        assert f"<b>{secs} s</b>" in text, (target, n, line)
