"""BOTH CHART-IMPORT ROUTES CARRY THE SAME SIDE FILES, FROM ONE LIST (4.3.47).

A chart imported into an OPEN project (`workflow.chart_import.
import_external_chart`) brought every side file beside it: the recognition
file, the layout, the strip map, the FD-9, i1iO and i1iSis side files, the
control-strip declaration. The same chart imported with NO project open
(`ui.ti2_loader._copy_files`, a new project) brought only `.cht` and
`.channels.json`, so an i1iO chart lost `<stem>.i1io.json` and with it the
table drive (M-I1IO-NOT-YET at Start), an i1iSis chart its `.isis.json`, and a
layout-engine chart its strip map. Both now copy
`workflow.chart_import.CHART_IMPORT_SIDE_FILES`, and the no-project route also
draws the pages a chart arrived without, as the other route does
(`rebuild_missing_pages`, Knut 2026-09-11).
"""
from __future__ import annotations

import ast
from pathlib import Path

from core.file_manager import Project
from core.measurement_target import RUN_TYPE_PROFILING, MeasurementTarget

ROOT = Path(__file__).resolve().parent.parent


def _external(folder: Path, stem: str = "src", pages: int = 1):
    from workflow.chart_import import CHART_IMPORT_SIDE_FILES
    folder.mkdir(parents=True, exist_ok=True)
    ti2 = folder / f"{stem}.ti2"
    ti2.write_text("ti2", encoding="utf-8")
    ti1 = folder / f"{stem}.ti1"
    ti1.write_text("ti1", encoding="utf-8")
    for ext in CHART_IMPORT_SIDE_FILES:
        (folder / f"{stem}{ext}").write_text(ext, encoding="utf-8")
    tiffs = []
    for i in range(1, pages + 1):
        t = folder / f"{stem}_{i:02d}.tif"
        t.write_text("tif", encoding="utf-8")
        tiffs.append(t)
    return ti2, ti1, tiffs


def _side_files_in(folder: Path, stem: str) -> "set[str]":
    from workflow.chart_import import CHART_IMPORT_SIDE_FILES
    return {ext for ext in CHART_IMPORT_SIDE_FILES
            if (folder / f"{stem}{ext}").is_file()}


def test_the_list_holds_the_side_files_that_were_lost():
    from workflow.chart_import import CHART_IMPORT_SIDE_FILES
    for ext in (".i1io.json", ".isis.json", ".fd9.json", ".strips.json",
                ".control-strip.json", ".cht", ".channels.json"):
        assert ext in CHART_IMPORT_SIDE_FILES, ext


def test_no_project_import_carries_every_side_file(tmp_path):
    from ui.ti2_loader import _copy_files
    from workflow.chart_import import CHART_IMPORT_SIDE_FILES
    ti2, ti1, tiffs = _external(tmp_path / "ext")
    out, _ = _copy_files(ti2, ti1, tiffs, tmp_path / "work", "New Chart")
    got = _side_files_in(out.parent, out.stem)
    assert got == set(CHART_IMPORT_SIDE_FILES), \
        f"lost: {sorted(set(CHART_IMPORT_SIDE_FILES) - got)}"
    # each under the new chart's name, with its own content
    side = out.with_name(out.stem + ".i1io.json")
    assert side.read_text(encoding="utf-8") == ".i1io.json"


def test_both_routes_carry_the_same_set(tmp_path):
    from ui.ti2_loader import _copy_files
    from workflow.chart_import import import_external_chart
    ti2, ti1, tiffs = _external(tmp_path / "ext")
    a, _ = _copy_files(ti2, ti1, tiffs, tmp_path / "work", "A")
    proj = Project.create(tmp_path / "work" / "B", "B")
    proj.current_run().ensure_dir()
    b = import_external_chart(ti2, ti1, tiffs, proj, MeasurementTarget(
        run_type=RUN_TYPE_PROFILING, profile_run=""))
    assert _side_files_in(a.parent, a.stem) == _side_files_in(b.parent, b.stem)


def test_the_no_project_route_reads_the_one_list():
    """One list, not two: `_copy_files` names the shared tuple, and no longer
    spells side-file endings of its own."""
    src = (ROOT / "ui" / "ti2_loader.py").read_text(encoding="utf-8")
    body = src[src.index("def _copy_files("):]
    body = body[:body.index("\ndef ", 1)]
    assert "CHART_IMPORT_SIDE_FILES" in body
    assert '".channels.json"' not in body and "with_suffix(\".cht\")" not in body


def test_no_project_import_draws_missing_pages(tmp_path, monkeypatch):
    import workflow.chart_import as ci
    from ui.ti2_loader import _copy_files
    ti2, ti1, _ = _external(tmp_path / "ext", pages=0)
    asked = []

    def fake_rebuild(ti2_path, bin_dir):
        asked.append((Path(ti2_path), Path(bin_dir)))
        page = Path(ti2_path).with_name(Path(ti2_path).stem + ".tif")
        page.write_text("drawn", encoding="utf-8")
        return [page]

    monkeypatch.setattr(ci, "rebuild_missing_pages", fake_rebuild)
    out, pages = _copy_files(ti2, ti1, [], tmp_path / "work", "Drawn",
                             bin_dir=tmp_path / "bin")
    assert asked == [(out, tmp_path / "bin")]
    assert [p.name for p in pages] == [out.stem + ".tif"]


def test_no_project_import_without_binaries_draws_nothing(tmp_path,
                                                          monkeypatch):
    import workflow.chart_import as ci
    from ui.ti2_loader import _copy_files
    ti2, ti1, _ = _external(tmp_path / "ext", pages=0)
    monkeypatch.setattr(ci, "rebuild_missing_pages",
                        lambda *a: (_ for _ in ()).throw(AssertionError(a)))
    _copy_files(ti2, ti1, [], tmp_path / "work", "Plain")


def test_the_chart_doors_with_no_project_pass_the_binaries():
    """resolve_ti2 and resolve_ti3 hold the settings; the new-project route
    they call must be handed the binaries, as `import_external_chart` is."""
    tree = ast.parse((ROOT / "ui" / "ti2_loader.py").read_text(encoding="utf-8"))
    found = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name in ("resolve_ti2",
                                                           "resolve_ti3"):
            calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)
                     and isinstance(c.func, ast.Name)
                     and c.func.id == "_handle_outside"]
            found[fn.name] = calls
            assert calls, fn.name
            for c in calls:
                assert any(k.arg == "bin_dir" for k in c.keywords), \
                    f"{fn.name}:{c.lineno} passes no binaries"
    assert set(found) == {"resolve_ti2", "resolve_ti3"}
