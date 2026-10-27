"""The File Guide lists the beta turned i1Profiler files while the option is
on, and only then (Basti, 2026-10-27: "let it list it when the option is on").

Off, the guide is 4.3.16's, byte for byte: measured against e73f93095's
`ui/file_guide.py` when this was written (body and HTML equal). Here that is
pinned as "ON is OFF plus exactly the three turned rows", and "OFF names no
turned file anywhere".
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ui.file_guide as fg                                   # noqa: E402

TURNED = ("-i1profiler-turned-i1Pro2.txf", "-i1profiler-turned-how-to.txt",
          "-i1profiler-turned.json")


def test_off_names_no_turned_file():
    for text in (fg.file_guide_body(turned=False),
                 fg.file_guide_html(turned=False)):
        assert "i1profiler-turned" not in text


def test_on_lists_every_turned_file_in_the_exports_group():
    groups = dict(fg._rows(True))
    exports = next(rows for title, rows in groups.items()
                   if title.startswith("exports/"))
    names = [r[0] for r in exports]
    for t in TURNED:
        assert any(t in n for n in names), (t, names)
    assert any("-i1Pro3.txf" in n for n in names)
    for f, folder, desc, origin in exports:
        if "turned" in f:
            assert folder == "runs/runN/exports"
            assert "—" not in desc
            assert len(desc) > 120, "an explanation, not a label"
    body = fg.file_guide_body(turned=True)
    html = fg.file_guide_html(turned=True)
    for t in TURNED:
        assert t in body and t in html


def test_on_is_off_plus_exactly_the_turned_rows():
    off, on = fg._rows(False), fg._rows(True)
    assert [t for t, _ in off] == [t for t, _ in on]
    for (title, a), (_t, b) in zip(off, on):
        assert [r for r in b if "i1profiler-turned" not in r[0]] == a
        if not title.startswith("exports/"):
            assert a == b


def test_without_an_argument_the_setting_decides(monkeypatch):
    monkeypatch.setattr(fg, "turned_export_on", lambda: False)
    assert fg.file_guide_body() == fg.file_guide_body(turned=False)
    assert fg.file_guide_html() == fg.file_guide_html(turned=False)
    monkeypatch.setattr(fg, "turned_export_on", lambda: True)
    assert fg.file_guide_body() == fg.file_guide_body(turned=True)
    assert fg.file_guide_html() == fg.file_guide_html(turned=True)


def test_the_setting_is_read_and_off_by_default():
    from core.settings import AppSettings
    s = AppSettings()
    was = s.get("i1profiler_turned_export", False)
    try:
        s.set("i1profiler_turned_export", False)
        assert fg.turned_export_on() is False
        s.set("i1profiler_turned_export", True)
        assert fg.turned_export_on() is True
    finally:
        s.set("i1profiler_turned_export", was)
