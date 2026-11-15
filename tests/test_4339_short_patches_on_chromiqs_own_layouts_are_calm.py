"""Combined review of 4.3.39, MAJOR-2: the short-patch note fired as a red
warning on the out-of-box chart (Guided, i1Pro, A4, 484 patches at 9.5 mm).

When the patch length is ChromIQ's own automatic choice (a Guided chart, or a
Manual area-first chart with no patch size and no minimum set) and longer than
8.0 mm, it is said as one calm [INFO] line (M-CHART-PATCHES-SHORT-AUTO) in the
Create Chart and Measure logs, with nothing red on the panel. 8.0 mm or less
(the tester's real misreads were at 8.0 and 7.1 mm), and every size the person
set, keep the warning exactly as before.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow import measurement_messages as M
from workflow import patch_size_check as P


def _channels(tmp_path, h_px, *, guided=False, recipe=None, inst="i1",
              name="c"):
    layout = {"engine": "chromiq", "dpi": 300,
              "recipe": {"instrument": inst, **(recipe or {})},
              "patches": [{"loc": "1A", "h": h_px}]}
    if guided:
        layout["margins_chosen_by_user"] = False
    p = tmp_path / f"{name}.channels.json"
    p.write_text(json.dumps({"layout": layout}), encoding="utf-8")
    return p


AREA = {"layout_mode": "area_first"}


@pytest.mark.parametrize("label,h_px,kw,calm", [
    ("default Guided A4, 9.5 mm", 112, dict(guided=True), True),
    ("Guided, 8.1 mm", 96, dict(guided=True), True),
    ("Guided, 8.0 mm: the tester's misread size", 94, dict(guided=True),
     False),
    ("Manual area-first, nothing set, 9.0 mm", 106, dict(recipe=AREA), True),
    ("Manual area-first with a minimum set", 106,
     dict(recipe={**AREA, "area_min_patch_mm": 9.0}), False),
    ("Manual patch-first (a size the person set)", 106,
     dict(recipe={"layout_mode": "patch_first", "patch_h_mm": 9.0}), False),
])
def test_which_short_patches_are_calm(tmp_path, label, h_px, kw, calm):
    f = P.from_channels(_channels(tmp_path, h_px, **kw))
    assert f is not None, label
    assert f.calm is calm, label


def test_extra_high_density_keeps_its_warning(tmp_path):
    f = P.from_channels(_channels(tmp_path, 153, guided=True, inst="CM",
                                  recipe={"cm_density": 3}))
    assert f is not None and f.extra_high and not f.calm


def test_the_calm_words(tmp_path):
    f = P.from_channels(_channels(tmp_path, 112, guided=True))
    title, body = P.note_text(f)
    assert title == M.M_CHART_PATCHES_SHORT_AUTO.title
    assert "9.5 mm" in body and "10 mm" in body
    assert "Most strips read fine" in body and "fewer patches per page" in body
    assert "—" not in title + body
    assert P.log_line(f) == "[INFO] " + body
    assert M.M_CHART_PATCHES_SHORT_AUTO.id in M.PROPOSED


class _Log:
    def __init__(self):
        self.lines = []

    def appendPlainText(self, text):
        self.lines.append(text)


def _note(tmp_path, h_px, **kw):
    from ui.tabs.tab_chart import TabChart
    _channels(tmp_path, h_px, name="chart", **kw)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    fake = SimpleNamespace(_margin_ti2=ti2, _log=_Log())
    return TabChart._short_patch_note(fake), fake


def test_create_chart_calm_is_an_info_line_and_nothing_red(tmp_path):
    warn, fake = _note(tmp_path, 112, guided=True)
    assert warn is None                       # nothing counted, nothing red
    assert fake._short_patch_panel_line is None
    assert len(fake._log.lines) == 1 and fake._log.lines[0].startswith(
        "[INFO] The patches on this chart are 9.5 mm")


def test_create_chart_keeps_the_warning_for_a_size_the_person_set(tmp_path):
    warn, fake = _note(tmp_path, 94)
    assert warn and warn.startswith("⚠ ")
    assert fake._short_patch_panel_line.startswith("⚠ Patches 8 mm")
