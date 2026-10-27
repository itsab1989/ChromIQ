"""The beta "turned" i1Profiler export (Preferences -> Beta, off by default).

One ChromIQ print that i1Profiler can read too, after a quarter turn
(``workflow.i1profiler_turned``). The rules it follows were measured in
i1Profiler 3.8.8 (study of 2026-10-26, 540/540 and 1080/1080 patches in place);
these tests pin that the implementation follows them, that a chart which does
not qualify gets a reason with real numbers instead of a file, that nothing
changes with the option off, and that the way back pairs every reading with
its own patch or refuses.
"""
from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import i1profiler_turned as T                       # noqa: E402


# ---------------------------------------------------------------------------
# Real charts, built by the layout engine and stored as Create Chart stores
# them (the recipe and the geometry folded into channels.json).
# ---------------------------------------------------------------------------

def _ti1(path: Path, n: int, seed: int = 1) -> Path:
    rnd = random.Random(seed)
    rows = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)] + [
        tuple(round(rnd.uniform(0, 100), 4) for _ in range(3))
        for _ in range(n - 2)]
    lines = ["CTI1", "", 'DESCRIPTOR "test"', 'COLOR_REP "RGB"', "",
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             "", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i, (r, g, b) in enumerate(rows, 1):
        y = max(1.0, (r + g + b) / 3)
        lines.append(f"{i} {r:.4f} {g:.4f} {b:.4f} {y * .95:.4f} {y:.4f} "
                     f"{y * 1.08:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _chart(folder: Path, name: str, n: int = 350, **kw) -> Path:
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / f"{name}.ti1", n)
    args = dict(instrument="i1", layout_mode="patch_first", spacer_mode="none",
                seed=4242)
    args.update(kw)
    res, used = build_from_recipe(ti1, folder / name, LayoutRecipe(**args))
    strips = folder / f"{name}.strips.json"
    lay = json.loads(strips.read_text(encoding="utf-8"))
    lay.update(engine="chromiq", engine_version=1, seed=res.seed,
               recipe=used.to_dict())
    (folder / f"{name}.channels.json").write_text(json.dumps({"layout": lay}),
                                                  encoding="utf-8")
    strips.unlink()
    return folder / f"{name}.ti2"


@pytest.fixture(scope="module")
def charts(tmp_path_factory):
    d = tmp_path_factory.mktemp("turned")
    return {
        # ChromIQ's default i1Pro chart: 10 mm patches, 24 per strip
        "default": _chart(d / "default", "Default", 350),
        # the study's 8 x 8 mm chart: 30 per strip (both families since 4.3.18)
        "eight": _chart(d / "eight", "Eight", 350, patch_w_mm=8.0,
                        patch_h_mm=8.0),
        # two sheets
        "two": _chart(d / "two", "Two", 600),
        "spacers": _chart(d / "spacers", "Spacers", 200, spacer_mode="colored"),
        "munki": _chart(d / "munki", "Munki", 200, instrument="CM"),
        "long": _chart(d / "long", "Long", 200, patch_w_mm=8.0,
                       patch_h_mm=11.0),
    }


def _geometry(ti2: Path):
    lay = json.loads(ti2.with_name(f"{ti2.stem}.channels.json").read_text(encoding="utf-8"))
    return lay["layout"]


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

def test_the_window_rule_is_the_measured_one():
    """``242.4/(P+1) < L <= 241.5/P`` (i1Profiler's row cap, 241.5..242.4 mm)."""
    lo, hi = T.window_mm(24, "i1Pro 3")
    assert round(lo, 3) == 9.696 and round(hi, 4) == 10.0625
    lo, hi = T.window_mm(30, "i1Pro 2")
    assert round(lo, 3) == 7.819 and hi == pytest.approx(8.05)


def test_the_default_i1pro_chart_qualifies_for_both_families(charts):
    plan = T.plan_for(charts["default"])
    assert plan.families == ["i1Pro 2", "i1Pro 3"]
    assert plan.columns == 24 and plan.patch_len_mm == pytest.approx(10.0)
    assert len(plan.order) == plan.columns * plan.rows


def test_an_8_mm_chart_is_for_both_families(charts):
    """4.3.18, Basti 2026-10-27: the i1Pro 2 from 7 mm, like the i1Pro 3
    (4.3.17 wrote its file only from 10 mm)."""
    plan = T.plan_for(charts["eight"])
    assert plan.families == ["i1Pro 2", "i1Pro 3"], plan.family_reasons
    assert plan.family_reasons["i1Pro 2"] == []


def _strips_of(lay):
    strips = lay["strips"]
    by_strip: dict = {}
    for p in lay["patches"]:
        for si, s in enumerate(strips):
            if (s["page"] == p["page"] and s["x"] <= p["x"] + 1
                    and p["x"] < s["x"] + s["w"]):
                by_strip.setdefault(si, []).append(p)
                break
    for si in by_strip:
        by_strip[si].sort(key=lambda q: q["y"])
    return strips, by_strip


@pytest.mark.parametrize("key", ["default", "two"])
def test_clockwise_strip_a_is_the_top_row_read_from_its_last_patch(charts, key):
    """4.3.18 (Basti: the clip border belongs at the top). Entry j sits at
    i1Profiler column j // R, row j % R. Turned CLOCKWISE, the sheet's left
    edge goes to the top: row r is the (r+1)-th strip of its sheet counted
    from strip A, sheet by sheet, and column c is place P-1-c of that strip,
    because the label end of the strip is now on the right."""
    ti2 = charts[key]
    plan = T.plan_for(ti2)
    assert plan.turn == T.CLOCKWISE
    strips, by_strip = _strips_of(_geometry(ti2))
    pages = sorted({s["page"] for s in strips})
    rows = []
    for pg in pages:
        rows += [i for i, s in enumerate(strips) if s["page"] == pg]
    assert len(rows) == plan.rows
    for j, (_sid, loc, _v) in enumerate(plan.order):
        c, r = divmod(j, plan.rows)
        assert by_strip[rows[r]][plan.columns - 1 - c]["loc"] == loc
    assert plan.row_strips[0][2] == "A"
    if key == "two":
        assert plan.sheets == 2
        # sheet 2 starts with its own strip A... the strip after sheet 1's last
        first_of_2 = [r for r, sh, _l in plan.row_strips if sh == 2][0]
        assert first_of_2 == 1 + sum(1 for s in strips if s["page"] == pages[0])


@pytest.mark.parametrize("key", ["default", "two"])
def test_anticlockwise_is_4317s_order_exactly(charts, key):
    """The other quarter turn is 4.3.17's order, unchanged: each sheet's
    strips from last to first, each strip from its label end."""
    ti2 = charts[key]
    plan = T.plan_for(ti2, turn=T.ANTICLOCKWISE)
    strips, by_strip = _strips_of(_geometry(ti2))
    pages = sorted({s["page"] for s in strips})
    rows = []
    for pg in pages:
        rows += list(reversed([i for i, s in enumerate(strips)
                               if s["page"] == pg]))
    for j, (_sid, loc, _v) in enumerate(plan.order):
        c, r = divmod(j, plan.rows)
        assert by_strip[rows[r]][c]["loc"] == loc


def test_the_two_turns_are_not_the_same_order(charts):
    cw = [l for _s, l, _v in T.plan_for(charts["default"]).order]
    ccw = [l for _s, l, _v in T.plan_for(charts["default"],
                                         turn=T.ANTICLOCKWISE).order]
    assert sorted(cw) == sorted(ccw) and cw != ccw
    # the anticlockwise list is the clockwise one turned by half a turn
    assert ccw == list(reversed(cw))


def test_the_turn_puts_the_clip_border_at_the_top(tmp_path):
    """Left clip border (the default) or none: clockwise. Clip border on the
    right: anticlockwise, which puts THAT edge at the top."""
    assert T.turn_for({}) == T.CLOCKWISE
    assert T.turn_for({"clip_border": True, "clip_side": "left"}) == T.CLOCKWISE
    assert T.turn_for({"clip_border": True, "clip_side": "right"}) == T.ANTICLOCKWISE
    assert T.turn_for({"clip_border": False, "clip_side": "right"}) == T.CLOCKWISE
    right = _chart(tmp_path / "r", "Right", 200, clip_side="right")
    assert T.plan_for(right).turn == T.ANTICLOCKWISE
    off = _chart(tmp_path / "o", "Off", 200, clip_border=False)
    plan = T.plan_for(off)
    assert plan.turn == T.CLOCKWISE and not plan.clip_border


def test_the_clip_border_really_is_the_left_margin(tmp_path):
    """What the turn is chosen by, measured on a chart's own map: with the
    clip border on the left the patch block starts 26 mm from the left edge;
    with it on the right, 26 mm from the right edge, and the left margin is
    the base one."""
    from workflow.layout_engine import papers
    w_mm, _h = papers.dimensions_mm("A4")
    out = {}
    for side in ("left", "right"):
        ti2 = _chart(tmp_path / side, side.title(), 600, clip_side=side)
        lay = _geometry(ti2)
        mm = 25.4 / lay["dpi"]
        page0 = [p for p in lay["patches"] if p["page"] == 0]
        out[side] = (min(p["x"] for p in page0) * mm,
                     w_mm - max(p["x"] + p["w"] for p in page0) * mm)
    assert out["left"][0] == pytest.approx(26.0, abs=0.1)
    assert out["right"][1] >= 25.9 > out["right"][0]


def test_padding_is_in_the_list(charts):
    """350 patches at 24 per strip is 15 strips with 10 paper-white fillers:
    i1Profiler would add grey fillers of its own if they were missing."""
    plan = T.plan_for(charts["default"])
    assert len(plan.order) == 360


@pytest.mark.parametrize("key, words", [
    ("spacers", "spacers"),
    ("munki", "ColorMunki"),
])
def test_a_chart_that_does_not_qualify_gets_a_reason(charts, key, words):
    plan = T.plan_for(charts[key])
    assert not plan.qualifies
    assert any(words in r for r in plan.reasons)


def test_a_strip_shorter_than_the_ruler_window_qualifies_on_a_narrow_page(charts):
    """4.3.18: 8 x 11 mm on A4 is 21 patches, 231 mm, outside 4.3.17's window
    (i1Profiler's own cap would give 22 per row). The page is made just wide
    enough instead: 31 mm of i1Profiler margin plus 21.5 patches."""
    plan = T.plan_for(charts["long"])
    assert plan.qualifies and plan.families == ["i1Pro 2", "i1Pro 3"]
    lo, hi = T.window_mm(plan.columns, "i1Pro 3")
    assert not (lo < plan.patch_len_mm <= hi)
    w = T.page_width_mm(plan, "i1Pro 3")
    assert w == pytest.approx(31 + (plan.columns + 0.5) * plan.patch_len_mm)
    # i1Profiler's measured rule: floor((width - 31) / L) per row, capped
    assert int((w - 31) // plan.patch_len_mm) == plan.columns


def test_in_the_ruler_window_the_page_is_4317s(charts):
    plan = T.plan_for(charts["default"])
    for fam in T.FAMILIES:
        assert T.in_ruler_window(plan, fam)
        assert T.page_width_mm(plan, fam) == T.PAGE_W_MM


def test_the_page_width_always_gives_exactly_one_strip_per_row():
    """For every strip ChromIQ can make (patch length 6 to 25 mm, up to the
    241.5 mm row cap), i1Profiler's measured row rule, ``floor(min(cap,
    width - 31) / L)``, is the strip's patch count, whichever end of the
    measured cap (241.5 to 242.4 mm) is the true one."""
    from types import SimpleNamespace
    for tenth in range(60, 251):
        L = tenth / 10.0
        for per in range(1, int(241.5 // L) + 1):
            plan = SimpleNamespace(columns=per, patch_len_mm=L)
            w = T.page_width_mm(plan, "i1Pro 3")
            for cap in (241.5, 242.4):
                assert int(min(cap, w - 31) // L + 1e-9) == per, (L, per, w)


def test_a_strip_longer_than_an_i1profiler_row_gets_the_real_numbers(tmp_path):
    """Only a chart built with "No strip length limit" can have one."""
    ti2 = _chart(tmp_path / "nl", "NoLimit", 200, patch_w_mm=8.0,
                 patch_h_mm=10.0, paper="A3", nolimit=True)
    plan = T.plan_for(ti2)
    if plan.columns * plan.patch_len_mm <= 241.5:
        pytest.skip("this build did not make a strip past the cap")
    why = " ".join(plan.family_reasons["i1Pro 3"])
    assert "241.5 mm" in why and f"{plan.columns}" in why


def test_a_chart_with_no_patch_map_is_refused_politely(tmp_path):
    ti2 = tmp_path / "Plain.ti2"
    ti2.write_text('CTI2\n\nCOLOR_REP "iRGB"\nSTEPS_IN_PASS "4"\n\n'
                   "NUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
                   "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
                   'NUMBER_OF_SETS 1\nBEGIN_DATA\n1 "A1" 1 2 3\nEND_DATA\n',
                   encoding="utf-8")
    plan = T.plan_for(ti2)
    assert not plan.qualifies and "layout engine" in plan.reasons[0]


# ---------------------------------------------------------------------------
# The files
# ---------------------------------------------------------------------------

def _attrs(txf: Path) -> dict:
    text = txf.read_text(encoding="utf-8")
    return dict(re.findall(r'(\w+)="([^"]*)"',
                           text.split("<xrp:CustomAttributes", 1)[1]
                           .split("/>", 1)[0]))


def test_the_files_are_written_and_say_what_i1profiler_must_show(charts, tmp_path):
    out = tmp_path / "exports"
    res = T.write_turned_export(charts["default"], out, "Default")
    assert not res.skipped
    files = T.TurnedFiles(out, "Default")
    assert {p.name for p in res.written} == {p.name for p in files.all()}
    plan = T.plan_for(charts["default"])
    for fam in ("i1Pro 2", "i1Pro 3"):
        a = _attrs(files.txf(fam))
        assert a["MeasurementDevice"] == fam
        assert a["NumberPatchColumns"] == str(plan.columns)
        assert a["NumberPatchRows"] == str(plan.rows)
        assert a["NumberPatchPages"] == "1"
        assert a["ScramblePatches"] == "False"
        assert a["PatchSizeWidthValue"] == "10.00"
        wlo, whi = T.SLIDER[fam][:2]
        assert float(a["PatchSizeWidthPercent"]) == pytest.approx(
            (10.0 - wlo) / (whi - wlo) * 100)
        # the patch list, in the turned order, on i1Profiler's 0..255 scale
        # (whole code values, as the existing patch-set writer rounds them)
        reds = [float(v) for v in re.findall(
            r"<cc:R>([^<]+)</cc:R>", files.txf(fam).read_text(encoding="utf-8"))]
        assert reds == pytest.approx(
            [vals["R"] * 2.55 for _s, _l, vals in plan.order], abs=0.5)
    note = files.note.read_text(encoding="utf-8")
    # a WORD, not a substring: "CLOCKWISE" is also in "ANTICLOCKWISE"
    # (review 4.3.18 r1, N-2)
    assert re.search(r"\bCLOCKWISE\b", note)
    assert not re.search(r"\bANTICLOCKWISE\b", note)
    for must in ("clip border", "TOP row", "Test Chart", "Load",
                 f"columns: {plan.columns}, rows: {plan.rows}, pages: 1",
                 "Default display device", "-i1profiler-turned-i1Pro2.txf",
                 "Row 1: strip", "IMPORT", "Import Measurement", ".mxf",
                 "Nobody has yet read such a sheet with a real instrument",
                 "with the i1Pro 3 file",
                 # i1Profiler's own labels, per instrument (review 4.3.17 r1)
                 "With an i1Pro 2: Single Scan (M0), or Dual scan "
                 "(M0,M1,M2 and OBC)",
                 "With an i1Pro 3: Single scan (M0,M1,M2 and OBC)",
                 # what is checked, and by whom (S4)
                 "it does not prove that each row was read in the right place",
                 "i1Profiler checks every row as you read it",
                 # a partial file (S6) and a device-less one (S5)
                 "ChromIQ brings a turned measurement back only when every "
                 "patch has been read",
                 "Measurements without device values",
                 "turning the option off later does not change it",
                 "-i1profiler-turned.json"):
        assert must in note, must
    # NO FILE STEM: a project rename renames the files, and the note must not
    # send anyone looking for the old names (review 4.3.17 r1).
    assert "Default-" not in note and "Default.ti2" not in note
    assert "colours in the file agree" not in note
    order = json.loads(files.order.read_text(encoding="utf-8"))
    assert order["chart_sha256"] == T.sha256_of(charts["default"])
    assert [e["loc"] for e in order["order"]] == [l for _s, l, _v in plan.order]


def test_a_chart_that_does_not_qualify_gets_only_the_note(charts, tmp_path):
    out = tmp_path / "exports"
    res = T.write_turned_export(charts["spacers"], out, "Spacers")
    files = T.TurnedFiles(out, "Spacers")
    assert [p.name for p in res.written] == [files.note.name]
    assert "spacers" in res.skipped and files.note.name in res.skipped
    assert not any(files.txf(f).exists() for f in T.FAMILIES)
    assert "spacers" in files.note.read_text(encoding="utf-8")


def test_a_new_chart_replaces_a_stale_turned_export(charts, tmp_path):
    out = tmp_path / "exports"
    T.write_turned_export(charts["default"], out, "Same")
    assert T.TurnedFiles(out, "Same").txf("i1Pro 2").exists()
    T.write_turned_export(charts["spacers"], out, "Same")
    assert not T.TurnedFiles(out, "Same").txf("i1Pro 2").exists()
    assert not T.TurnedFiles(out, "Same").order.exists()


def test_the_export_never_raises(tmp_path):
    bad = tmp_path / "Broken.ti2"
    bad.write_bytes(b"\x00\xff not a chart")
    res = T.write_turned_export(bad, tmp_path / "exports", "Broken")
    assert res.skipped


def test_the_run_names_the_files_and_a_rename_carries_them(tmp_path):
    from core.file_manager import Run
    run = Run.for_dir(tmp_path / "Proj" / "runs" / "run1")
    f = run.i1profiler_turned
    assert f.txf("i1Pro 3").name == "Proj-i1profiler-turned-i1Pro3.txf"
    assert f.folder == run.exports_dir
    import inspect
    from core import file_manager
    src = inspect.getsource(file_manager)
    assert "-turned(-i1Pro[23]|-how-to)?" in src


def test_after_a_project_rename_the_note_names_no_old_file(tmp_path):
    """The rename carries the files (`Project.rename`'s tail pattern); the
    note, which names files by their endings only, stays true."""
    import shutil
    from core.file_manager import Project, exports_subdir
    proj = Project.create(tmp_path / "Old", "Old")
    run = proj.current_run()
    run.ensure_dir()
    src = _chart(tmp_path / "build", "Old", 350)
    for f in src.parent.iterdir():
        shutil.copy2(f, run.dir / f.name)
    T.write_turned_export(run.chart_ti2, exports_subdir(run.dir), run.stem)
    moved = tmp_path / "New"
    proj.root.rename(moved)
    proj = Project.load(moved)
    proj.rename("New")
    run = proj.current_run()
    names = sorted(p.name for p in run.exports_dir.iterdir())
    assert "New-i1profiler-turned-how-to.txt" in names, names
    assert not any(n.startswith("Old") for n in names), names
    note = (run.exports_dir / "New-i1profiler-turned-how-to.txt").read_text(
        encoding="utf-8")
    assert "Old" not in note
    assert T.turned_order_for(run.chart_ti2) is not None


# ---------------------------------------------------------------------------
# Off means unchanged
# ---------------------------------------------------------------------------

class _Settings(dict):
    def get(self, k, d=None):            # noqa: D401 — dict-like, as AppSettings
        return super().get(k, d)


def _create_chart_sidecars(ti2: Path, stem: str, on: bool) -> "tuple[dict, list]":
    """The exact sidecar step of `TabChart._on_generate_finished`: the old
    `write_sidecars` loop, then the new turned step, with a real log list."""
    from core.file_manager import exports_subdir
    from ui.tabs.tab_chart import TabChart
    from workflow.chart_exports import write_sidecars
    log: list = []
    fake = SimpleNamespace(
        _settings=_Settings(i1profiler_turned_export=on),
        _log=SimpleNamespace(appendPlainText=log.append))
    for e in write_sidecars(ti2.with_suffix(".ti1"), exports_subdir(ti2.parent),
                            stem):
        log.append(f"wrote {e.name}")
    TabChart._write_turned_i1profiler_export(fake, ti2, stem)
    out = exports_subdir(ti2.parent)
    files = {p.name: re.sub(rb"<cc:CreationDate>[^<]*", b"",
                            p.read_bytes())
             for p in sorted(out.iterdir())}
    return files, log


def test_with_the_option_off_exports_and_log_are_todays(charts, tmp_path):
    """Golden comparison. "Today" is what 4.3.16 does: `write_sidecars` and
    one "wrote" line per file. With the option off the new step adds no file,
    no byte and no line."""
    import shutil
    from core.file_manager import exports_subdir
    from workflow.chart_exports import write_sidecars
    src = charts["default"]
    a, b = tmp_path / "today", tmp_path / "off"
    for d in (a, b):
        d.mkdir()
        for p in src.parent.glob(f"{src.stem}*"):
            if p.is_file():
                shutil.copy2(p, d / p.name)
    golden_log = [f"wrote {e.name}" for e in write_sidecars(
        a / f"{src.stem}.ti1", exports_subdir(a), src.stem)]
    golden = {p.name: re.sub(rb"<cc:CreationDate>[^<]*", b"", p.read_bytes())
              for p in sorted(exports_subdir(a).iterdir())}
    files, log = _create_chart_sidecars(b / src.name, src.stem, on=False)
    assert files == golden
    assert log == golden_log
    assert sorted(golden) == [f"{src.stem}-colours.txt",
                              f"{src.stem}-i1profiler.pxf",
                              f"{src.stem}-i1profiler.txt"]


def test_with_the_option_on_the_log_says_wrote_and_why_not(charts, tmp_path):
    import shutil
    for key, stem in (("default", "Default"), ("spacers", "Spacers")):
        d = tmp_path / key
        d.mkdir()
        for p in charts[key].parent.glob(f"{stem}*"):
            if p.is_file():
                shutil.copy2(p, d / p.name)
        files, log = _create_chart_sidecars(d / f"{stem}.ti2", stem, on=True)
        if key == "default":
            for name in (f"{stem}-i1profiler-turned-i1Pro2.txf",
                         f"{stem}-i1profiler-turned-i1Pro3.txf",
                         f"{stem}-i1profiler-turned.json",
                         f"{stem}-i1profiler-turned-how-to.txt"):
                assert name in files and f"wrote {name}" in log
        else:
            assert not any(n.endswith(".txf") for n in files)
            assert any(l.startswith("No turned i1Profiler chart was written")
                       and "spacers" in l for l in log)


def test_the_option_is_off_by_default():
    from core.settings import DEFAULTS
    assert DEFAULTS["i1profiler_turned_export"] is False


def test_the_build_writes_it_after_the_old_sidecars_and_only_there():
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate_finished)
    assert src.index("write_sidecars(") < src.index(
        "self._write_turned_i1profiler_export(ti2, stem)")
    from ui.dialogs import ti2_relayout_dialog
    assert "i1profiler_turned_export" in inspect.getsource(ti2_relayout_dialog)


# ---------------------------------------------------------------------------
# 4.3.18: the clockwise turn, any paper size, the page-height limit
# ---------------------------------------------------------------------------

def test_a_narrow_page_txf_says_its_width_and_custom_format(charts, tmp_path):
    out = tmp_path / "exports"
    res = T.write_turned_export(charts["long"], out, "Long")
    assert not res.skipped
    plan = T.plan_for(charts["long"])
    a = _attrs(T.TurnedFiles(out, "Long").txf("i1Pro 3"))
    assert float(a["PageWidth"]) == pytest.approx(T.page_width_mm(plan, "i1Pro 3"))
    assert a["PaperFormat"] == "0"
    assert a["PatchSizeWidthValue"] == f"{plan.patch_len_mm:.2f}"


@pytest.mark.parametrize("paper, patch_h", [
    ("Letter", 10.0), ("A4R", 10.0), ("LetterR", 12.0), ("Legal", 10.0),
    ("A3", 11.0), ("329x483", 10.5), ("4x6", 10.0)])
def test_every_paper_size_qualifies_with_one_strip_per_row(tmp_path, paper,
                                                          patch_h):
    """Measured in i1Profiler 3.8.8: a row holds floor(min(cap, page width -
    31) / L) patches. Whatever the paper, the page width written makes that
    the strip's patch count."""
    ti2 = _chart(tmp_path / paper, "P", 200, paper=paper, patch_w_mm=8.0,
                 patch_h_mm=patch_h)
    plan = T.plan_for(ti2)
    assert plan.families == ["i1Pro 2", "i1Pro 3"], plan.family_reasons
    w = T.page_width_mm(plan, "i1Pro 2")
    assert int(min(241.5, w - 31) // plan.patch_len_mm) == plan.columns


def test_too_many_strips_for_one_i1profiler_page_get_the_real_numbers(tmp_path):
    """i1Profiler's page is at most 1270 mm tall (asked for 2045 mm, it made
    1270 mm and two pages)."""
    ti2 = _chart(tmp_path / "big", "Big", 4000, paper="A2")
    plan = T.plan_for(ti2)
    assert not plan.qualifies
    why = " ".join(plan.family_reasons["i1Pro 3"])
    assert "1270 mm" in why and f"{plan.rows} strips" in why
    res = T.write_turned_export(ti2, tmp_path / "exports", "Big")
    assert "1270 mm" in res.skipped


def test_the_note_says_which_way_for_each_clip_side(tmp_path):
    for kw, words in (({}, ("CLOCKWISE", "left-hand side", "TOP row", "RIGHT")),
                      ({"clip_side": "right"},
                       ("ANTICLOCKWISE", "right-hand side", "BOTTOM row", "LEFT")),
                      ({"clip_border": False},
                       ("CLOCKWISE", "left-hand edge", "TOP row"))):
        ti2 = _chart(tmp_path / str(len(kw)) / str(kw.get("clip_side")), "N",
                     200, **kw)
        out = tmp_path / f"ex{kw}"
        T.write_turned_export(ti2, out, "N")
        note = T.TurnedFiles(out, "N").note.read_text(encoding="utf-8")
        step2 = [l for l in note.splitlines() if l.startswith("2. ")][0]
        for w in words:
            # whole words: "CLOCKWISE" is also in "ANTICLOCKWISE"
            assert re.search(rf"\b{re.escape(w)}\b", step2), (kw, w, step2)
        other = "CLOCKWISE" if words[0] == "ANTICLOCKWISE" else "ANTICLOCKWISE"
        assert not re.search(rf"\b{other}\b", step2), (kw, step2)
        order = json.loads(T.TurnedFiles(out, "N").order.read_text(
            encoding="utf-8"))
        assert order["turn"] == T.plan_for(ti2).turn
        assert order["version"] == T.ORDER_VERSION == 2
