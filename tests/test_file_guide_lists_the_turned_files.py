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


# ---- review 4.3.17 r3, NIT-1: off, but the project still holds the files ----

def _project_with_turned(tmp_path, *, valid: bool, beside: bool = False):
    import shutil
    from core.file_manager import Project
    from workflow import i1profiler_turned as T
    from tests.test_i1profiler_turned_export import _chart
    run = Project.create(tmp_path / "P", "P").current_run()
    run.ensure_dir()
    src = _chart(tmp_path / "src", "Src", 350)
    for f in src.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, run.dir / ("P" + f.name[len("Src"):]))
    T.write_turned_export(run.chart_ti2, run.dir if beside else run.exports_dir,
                          run.stem)
    if not valid:
        run.chart_ti2.write_text(
            run.chart_ti2.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    return run.dir.parent.parent


import pytest  # noqa: E402


@pytest.mark.parametrize("beside", [False, True],
                         ids=["in-exports", "beside-the-chart"])
def test_off_but_the_open_project_holds_turned_files_lists_them(
        tmp_path, monkeypatch, beside):
    root = _project_with_turned(tmp_path, valid=True, beside=beside)
    monkeypatch.setattr(fg, "turned_export_on", lambda: False)
    monkeypatch.setattr(fg, "_open_project_root", lambda: root)
    assert fg.project_holds_turned_files(root)
    assert fg.file_guide_body() == fg.file_guide_body(turned=True)
    assert fg.file_guide_html() == fg.file_guide_html(turned=True)


def test_off_with_a_stale_order_or_none_is_the_4316_guide(tmp_path,
                                                          monkeypatch):
    stale = _project_with_turned(tmp_path / "a", valid=False)
    monkeypatch.setattr(fg, "turned_export_on", lambda: False)
    for root in (stale, tmp_path / "missing", None):
        monkeypatch.setattr(fg, "_open_project_root", lambda r=root: r)
        assert not fg.project_holds_turned_files(root)
        assert fg.file_guide_body() == fg.file_guide_body(turned=False)
        assert fg.file_guide_html() == fg.file_guide_html(turned=False)
    # no project open at all (scripts, tests): the setting alone decides
    monkeypatch.setattr(fg, "_open_project_root", None)
    assert fg.file_guide_body() == fg.file_guide_body(turned=False)


def test_an_archived_or_stored_copy_does_not_count(tmp_path, monkeypatch):
    """old/ and chart/ hold copies of earlier charts: not the project's
    working files, so they do not bring the rows in."""
    import shutil
    root = _project_with_turned(tmp_path, valid=True)
    run_dir = root / "runs" / "run1"
    for sub in ("old/2026-10-27_000000", "chart"):
        d = run_dir / sub
        d.mkdir(parents=True)
        for f in list(run_dir.glob("P.*")) + [run_dir / "exports"]:
            (shutil.copytree if f.is_dir() else shutil.copy2)(
                f, d / f.name)
    shutil.rmtree(run_dir / "exports")
    assert not fg.project_holds_turned_files(root)


def test_the_readme_of_a_project_holding_turned_files_lists_them(
        tmp_path, monkeypatch):
    from core.file_manager import Project
    root = _project_with_turned(tmp_path, valid=True)
    monkeypatch.setattr(fg, "turned_export_on", lambda: False)
    proj = Project.load(root)
    proj.write_readme()
    assert "-i1profiler-turned.json" in proj.readme_path.read_text(
        encoding="utf-8")


def test_the_main_window_tells_the_guide_which_project_is_open():
    import inspect
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.__init__)
    assert "set_open_project_root(self._open_project_root_or_none)" in src
    body = inspect.getsource(MainWindow._open_project_root_or_none)
    assert "get_target_name" not in body
