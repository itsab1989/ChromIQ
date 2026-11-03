"""FD-9 (Beta) review round 3: R3-2 and R3-3.

R3-1 (a change the user makes with the Beta off is the user's, and a Generate
into an FD-9 run leaves no FD-9 behind) is proved on the real window in
``test_fd9_off_stale_project.py`` and its rule in
``test_fd9_off_changes_nothing.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
from tests.test_fd9_review_r2 import chart_tab  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


# ---- R3-3: Pages follows the loaded target, with no FD-9 override ----------
def test_target_change_has_no_fd9_page_count_override(chart_tab):
    t = chart_tab
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    t._pages_spin.setValue(5)
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("FD9"))
    assert getattr(t, "_fd9_guided_pages_was", None) is None      # project A's own value
    t._on_target_changed()                   # another project/run
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    assert t._pages_spin.value() == 5  # no instrument-specific forced page count


def test_opening_an_fd9_target_does_not_remember_the_last_ones_pages(
        chart_tab):
    """The reviewer's sequence: an i1Pro project with 5 pages is on screen,
    an FD-9 project is opened (its settings put FD-9 on screen), and the user
    then picks the i1Pro. Pages must not become the other project's 5."""
    t = chart_tab
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    t._pages_spin.setValue(5)
    t._loading_target_settings = True        # what load_target_settings does
    try:
        t._instr_combo.setCurrentIndex(t._instr_combo.findData("FD9"))
        t._pages_spin.setValue(1)
    finally:
        t._loading_target_settings = False
    assert getattr(t, "_fd9_guided_pages_was", None) is None
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    assert t._pages_spin.value() == 1


def test_a_load_that_leaves_the_fd9_keeps_the_stored_pages(chart_tab):
    t = chart_tab
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    t._pages_spin.setValue(3)
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("FD9"))
    t._loading_target_settings = True
    try:
        t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
        t._pages_spin.setValue(7)                # the stored value
    finally:
        t._loading_target_settings = False
    assert t._pages_spin.value() == 7 and getattr(t, "_fd9_guided_pages_was", None) is None


# ---- R3-2: every licence file the specs ship is listed --------------------
_LICENCE_NAME = re.compile(r"(?i)(licen[cs]e|copying|\bofl\b)[^/]*$")


def _shipped_licence_files() -> "set[str]":
    """Each licence file the three .spec files put in the app, as the path
    it has inside the bundle: named ones, and those in shipped folders."""
    out = set()
    for spec in ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"):
        text = (ROOT / spec).read_text(encoding="utf-8")
        for src, dest in re.findall(r"(?<!join)\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)",
                                    text):
            p = ROOT / src
            if p.is_file() and _LICENCE_NAME.search(p.name):
                out.add(f"{dest.strip('.').strip('/')}/{p.name}".lstrip("/"))
            elif p.is_dir():
                for f in p.rglob("*"):
                    if f.is_file() and _LICENCE_NAME.search(f.name):
                        rel = f.relative_to(p).as_posix()
                        out.add(f"{dest.strip('.').strip('/')}/{rel}"
                                .lstrip("/"))
    return out


def test_the_specs_ship_licence_files_this_test_can_see():
    got = _shipped_licence_files()
    assert {"LICENSE", "native/argyll/LICENSE",
            "native/instlib/License.txt"} <= got, got


def test_every_licence_file_a_built_app_ships_has_a_row(tmp_path,
                                                        monkeypatch):
    import ui.licences as lic
    shipped = _shipped_licence_files()
    frozen = tmp_path / "bundle"
    for rel in shipped:
        (frozen / rel).parent.mkdir(parents=True, exist_ok=True)
        (frozen / rel).write_text("licence", encoding="utf-8")
    monkeypatch.setattr(lic, "resource_path", lambda rel: frozen / rel)
    got = {lic.licence_file_label(p) for p in lic.bundled_licence_files()}
    assert shipped <= got, (
        "Preferences > Licences does not list these licence files the app "
        f"ships: {sorted(shipped - got)}")


def test_every_licence_file_is_listed_in_the_source_tree_too():
    import ui.licences as lic
    got = {lic.licence_file_label(p) for p in lic.bundled_licence_files()}
    want = set()
    for rel in _shipped_licence_files():
        # The built app keeps the FD-9 driver's licence under licenses/; the
        # source tree keeps it in vendor/.
        rel = rel.replace("licenses/fd9-independent/",
                          "vendor/fd9-independent/")
        if (ROOT / rel).is_file():
            want.add(rel)
    assert want and want <= got, sorted(want - got)


def test_a_licence_file_that_is_not_there_gets_no_row(tmp_path, monkeypatch):
    import ui.licences as lic
    frozen = tmp_path / "bundle"
    frozen.mkdir()
    (frozen / "LICENSE").write_text("GPL", encoding="utf-8")
    monkeypatch.setattr(lic, "resource_path", lambda rel: frozen / rel)
    assert [lic.licence_file_label(p) for p in lic.bundled_licence_files()] \
        == ["LICENSE"]
