"""Integration test: ChartCreator routes through the ChromIQ layout engine
when ``use_chromiq_layout_engine`` is on (covers both Guided and Manual, since
they share generate())."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_creator import ChartCreator, ChartParams


def _real_ti1(path: Path, n: int = 60) -> None:
    rows = []
    vals = [0.0, 33.0, 66.0, 100.0]
    i = 0
    rows.append((100.0, 100.0, 100.0))  # white (media)
    for r in vals:
        for g in vals:
            for b in vals:
                if len(rows) >= n:
                    break
                rows.append((r, g, b))
    lines = ['CTI1', 'COLOR_REP "iRGB"',
             'NUMBER_OF_FIELDS 7', 'BEGIN_DATA_FORMAT',
             'SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
             f'NUMBER_OF_SETS {len(rows)}', 'BEGIN_DATA']
    for i, (r, g, b) in enumerate(rows, 1):
        lines.append(f'{i} {r:.4f} {g:.4f} {b:.4f} '
                     f'{r*0.95:.4f} {g:.4f} {b*1.08:.4f}')
    lines += ['END_DATA', '']
    path.write_text("\n".join(lines), encoding="utf-8")


class _EngineRunner:
    """targen writes a real .ti1; the engine (not printtarg) finishes the chart."""

    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        cwd = Path(cwd)
        stem = args[-1]
        if tool == "targen":
            _real_ti1(cwd / f"{stem}.ti1")
        if on_finish:
            on_finish(0)


class _MockFileManager:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._project = None

    def ensure_folder(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def clean_folder(self, exts):
        pass

    def project(self):
        from core.file_manager import Project
        if self._project is None:
            self._project = Project.create_or_load(self.root, self.root.name)
        return self._project

    def cwd_for_chart(self, *, cal_target: bool) -> Path:
        return self.project().current_run().ensure_dir()

    def chart_stem(self, *, cal_target: bool) -> str:
        return self.project().current_run().stem


class _EngineSettings:
    def get(self, key, default=None):
        if key == "use_chromiq_layout_engine":
            return True
        return default


def test_generate_uses_engine(tmp_path: Path) -> None:
    work_dir = tmp_path / "engine_proj"
    creator = ChartCreator(_EngineRunner(), _MockFileManager(work_dir), _EngineSettings())
    finished: list[list[Path]] = []
    creator.generate(
        ChartParams(instrument="i1", paper="A4", device_type="2", tiff_dpi=150),
        on_line=lambda _l: None,
        on_finish=lambda tiffs: finished.append(tiffs),
    )
    assert finished, "on_finish must fire"
    tiffs = finished[0]
    assert tiffs and all(p.exists() for p in tiffs), "engine must produce TIFF(s)"

    run_dir = work_dir / "runs" / "run1"
    stem = "engine_proj"
    assert (run_dir / f"{stem}.ti2").exists(), "engine must write the .ti2"
    sidecar = json.loads((run_dir / f"{stem}.channels.json").read_text(encoding="utf-8"))
    assert "layout" in sidecar, "channels.json must carry the layout geometry"
    layout = sidecar["layout"]
    assert layout["strips"] and layout["patches"], "strip + patch rects present"
    assert "seed" in layout and isinstance(layout["recipe"], dict)
    assert layout["recipe"]["instrument"] == "i1"
    # the standalone .strips.json is folded into channels.json
    assert not (run_dir / f"{stem}.strips.json").exists()


def test_auto_count_uses_engine_capacity(tmp_path: Path) -> None:
    """Guided (_lookup_patches) and Manual-auto (estimate_patches) request the
    engine's own capacity × pages so the chart fills the page."""
    from workflow.layout_engine import geometry, instruments, papers
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    p = ChartParams(instrument="i1", paper="A4", pages=1)
    kw = creator._engine_build_kwargs(p)
    geom = instruments.geom_from_build_kwargs(kw)
    cap = geometry.patches_per_sheet(geom, *papers.dimensions_mm(p.paper))
    assert cap > 0
    assert creator._engine_total_patches(p) == cap
    assert creator._lookup_patches(p) == cap          # guided generation count
    assert creator.estimate_patches(p) == cap         # manual-auto count
    # pages multiply the requested count
    p2 = ChartParams(instrument="i1", paper="A4", pages=3)
    assert creator._lookup_patches(p2) == cap * 3


def test_engine_build_kwargs_mapping(tmp_path: Path) -> None:
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    # Guided/Manual ColorMunki triple density → engine extra-high density (3).
    # patch_scale carries printtarg's -ii1 -a (1.3 = default); the engine's
    # native extra-high size is that -a1.3, so it converts to engine pscale
    # = -a / 1.3. The default 1.3 → 1.0 (unchanged native size, no regression).
    kw = creator._engine_build_kwargs(
        ChartParams(instrument="CM", paper="A3", triple_density=True,
                    no_spacers=True, patch_scale=1.3, tiff_dpi=600))
    assert kw["instrument"] == "CM" and kw["paper"] == "A3"
    assert kw["density"] == 3            # triple density → extra-high
    assert kw["spacer_on"] is False
    assert kw["pscale"] == 1.0 and kw["dpi"] == 600
    # A denser preset scale (printtarg -a1.04) converts to a sub-1 engine scale.
    kw2 = creator._engine_build_kwargs(
        ChartParams(instrument="CM", paper="A3", triple_density=True,
                    patch_scale=1.04))
    assert kw2["pscale"] == 1.04 / 1.3
    assert ChartParams(instrument="CM", double_density=True) and \
        creator._engine_build_kwargs(ChartParams(instrument="CM", double_density=True))["density"] == 2


def test_guided_and_manual_colormunki_extra_high_same_patch_geometry(tmp_path: Path) -> None:
    """Manual's ColorMunki Extra-high and Guided's triple density share the SAME
    native dense-strip patch geometry (10.4 mm patches, same spacing). They now
    legitimately differ in *layout mode*: Guided stays patch-first (printtarg-
    style), while Manual defaults to area-first ("margins are the law"), which
    fills the margin box and so fits a few more patches (Knut #93; Sebastian:
    keep Guided untouched, accept the divergence). The shared patch SIZE is what
    matters for readability."""
    import dataclasses
    from workflow.layout_engine import instruments, geometry
    from workflow.layout_engine.presets import default_recipe
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    gkw = creator._engine_build_kwargs(
        ChartParams(instrument="CM", paper="A4", triple_density=True,
                    margin_mm=5.0, patch_scale=1.3, no_strip_limit=True))
    mkw = default_recipe("CM", "A4", mode="extrahigh").build_kwargs()
    mkw["instrument"], mkw["paper"] = "CM", "A4"
    gg = instruments.geom_from_build_kwargs(gkw)
    # Patch-first parity: the dense ColorMunki patch SIZE is identical to Guided's
    # (the readable native dense-strip geometry — 10.4 mm patches, same spacing).
    gm_pf = instruments.geom_from_build_kwargs({**mkw, "layout_mode": "patch_first"})
    # margins_are_law / fill_beyond_ruler are layout-BOX flags, not patch geometry:
    # Guided here uses user margins while the Manual default recipe has "Use
    # instrument margins" on, so those two flags legitimately differ — exclude them
    # and assert the patch geometry proper is identical (Knut instrument-margins fix).
    _BOX_FLAGS = {"margins_are_law", "fill_beyond_ruler"}
    diffs = [f.name for f in dataclasses.fields(instruments.Geom)
             if f.name not in _BOX_FLAGS
             and getattr(gg, f.name) != getattr(gm_pf, f.name)]
    assert diffs == [], f"unexpected geometry diff: {diffs}"
    assert (gg.pwid, gg.plen, gg.rrsp, gg.pspa) == (gm_pf.pwid, gm_pf.plen,
                                                    gm_pf.rrsp, gm_pf.pspa)
    # Area-first (the Manual default) makes the margins law and FILLS the box: it
    # takes the dense size as a MINIMUM width and derives the patch from there, so
    # the width is at least the dense minimum (height follows the height-%) (Knut).
    gm_af = instruments.geom_from_build_kwargs(mkw)
    assert gm_af.margins_are_law and not gg.margins_are_law
    assert gm_af.pwid >= gm_pf.pwid - 0.1


def test_engine_kwargs_uses_full_recipe(tmp_path: Path) -> None:
    from workflow.layout_engine.presets import LayoutRecipe
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    recipe = LayoutRecipe(instrument="i1", paper="A4", margin_top=10,
                          patch_w_mm=9.0, offset_x_mm=4.0, spacer_mode="bw")
    params = ChartParams(instrument="i1", paper="Letter",
                         layout_recipe=recipe, engine_cal_path="/tmp/c.cal",
                         engine_apply_cal=True)
    kw = creator._engine_kwargs(params)
    # recipe drives the layout; instrument/paper come from ChartParams
    assert kw["margins"][0] == 10 and kw["patch_w"] == 9.0 and kw["offset_x"] == 4.0
    assert kw["spacer_mode"] == "bw"
    assert kw["paper"] == "Letter"          # ChartParams wins for paper
    assert kw["cal_path"] == "/tmp/c.cal" and kw["apply_cal"] is True


class _ThresholdSettings(_EngineSettings):
    """Engine on, plus a margin-threshold table (the real settings API)."""

    def get_margin_thresholds(self):
        from core.settings import margin_combo_key
        return {margin_combo_key("i1Pro", "A4", "Portrait"): {"T": 60, "R": 9}}


def test_recipe_margins_always_authoritative_no_clamp(tmp_path: Path) -> None:
    """The margin boxes are ALWAYS the law (Knut, new model): the engine never
    silently raises them to meet instrument-margin minimums, regardless of the
    "Use instrument margins" toggle. Going below a minimum is allowed and only
    flagged as a violation in the inspector (#93)."""
    from workflow.layout_engine.presets import LayoutRecipe
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "a"),
                           _ThresholdSettings())
    for uim in (False, True):
        r = LayoutRecipe(instrument="i1", paper="A4", margin_top=5.0,
                         use_instrument_margins=uim)
        kw = creator._engine_kwargs(ChartParams(instrument="i1", paper="A4",
                                                layout_recipe=r))
        assert kw["margins"][0] == 5.0       # never clamped up to the threshold
        assert not creator._threshold_notes


def test_guided_does_not_enforce_margin_thresholds(tmp_path: Path) -> None:
    """Guided mode (no recipe) does NOT clamp to the margin thresholds: it has
    no margin boxes and no "Use instrument margins" toggle, and clamping pinned
    the patch count regardless of the clip-border / strip-cap toggles. Reverted
    so Guided behaves like before the #93 threshold feature — the count must
    match an engine built without thresholds."""
    from workflow.layout_engine import instruments
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _ThresholdSettings())
    p = ChartParams(instrument="i1", paper="A4", pages=1)
    kw = creator._engine_kwargs(p)
    # geom_from_build_kwargs is called without thresholds → no silent clamp
    assert instruments.geom_from_build_kwargs(kw) is not None
    assert not creator._threshold_notes, "Guided must not record a clamp note"
    # capacity equals an engine with no threshold table at all
    plain = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "q"),
                         _EngineSettings())._engine_total_patches(p)
    assert creator._engine_total_patches(p) == plain


def test_full_recipe_chart_builds(tmp_path: Path) -> None:
    work_dir = tmp_path / "rp"
    creator = ChartCreator(_EngineRunner(), _MockFileManager(work_dir), _EngineSettings())
    from workflow.layout_engine.presets import LayoutRecipe
    finished: list[list[Path]] = []
    creator.generate(
        ChartParams(instrument="i1", paper="A4", device_type="2", tiff_dpi=120,
                    layout_recipe=LayoutRecipe(instrument="i1", paper="A4",
                                               margin_top=12, patch_h_mm=11.0,
                                               bit16=True, compression="zlib")),
        on_line=lambda _l: None, on_finish=lambda t: finished.append(t))
    assert finished and finished[0] and finished[0][0].exists()
    sidecar = json.loads(
        (work_dir / "runs" / "run1" / "rp.channels.json").read_text(encoding="utf-8"))
    assert sidecar["layout"]["engine"] == "chromiq"
    assert sidecar["layout"]["recipe"]["margin_top"] == 12


def test_guided_clip_border_uses_notes_when_kept(tmp_path: Path) -> None:
    """Guided/basic path: keeping the i1/p3 clip border fills it with the notes
    record; suppressing it leaves no clip content (#93)."""
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    kept = creator._engine_build_kwargs(
        ChartParams(instrument="i1", paper="A4", disable_left_border=False))
    assert kept["clip_content_mode"] == "notes" and kept["nolpcbord"] is False
    supp = creator._engine_build_kwargs(
        ChartParams(instrument="i1", paper="A4", disable_left_border=True))
    assert supp["clip_content_mode"] == "off" and supp["nolpcbord"] is True
    # non-clip instruments don't set it
    assert "clip_content_mode" not in creator._engine_build_kwargs(
        ChartParams(instrument="CM", paper="A4"))


def test_guided_uses_edge_spacers_for_strip_readers(tmp_path: Path) -> None:
    """Guided/basic path brackets each strip with edge spacers for i1Pro /
    i1Pro 3+ / ColorMunki, but not SpectroScan (#93)."""
    creator = ChartCreator(_EngineRunner(), _MockFileManager(tmp_path / "p"),
                           _EngineSettings())
    for inst in ("i1", "p3", "CM"):
        kw = creator._engine_build_kwargs(ChartParams(instrument=inst, paper="A4"))
        assert kw.get("edge_spacers") is True, inst
    assert creator._engine_build_kwargs(
        ChartParams(instrument="SS", paper="A4")).get("edge_spacers") is not True


def test_load_ti1_uses_engine_when_enabled(tmp_path: Path) -> None:
    """A loaded preset / built-in .ti1 must be laid out by the engine when it's
    enabled — not silently fall back to printtarg (the bug Knut hit: columns /
    patch width / notes box did nothing with a preset loaded) (#93)."""
    work_dir = tmp_path / "preset_proj"
    creator = ChartCreator(_EngineRunner(), _MockFileManager(work_dir),
                           _EngineSettings())
    ti1 = tmp_path / "preset.ti1"
    _real_ti1(ti1, 60)
    finished: list[list[Path]] = []
    creator.load_ti1_and_generate_preview(
        ti1, ChartParams(instrument="i1", paper="A4", tiff_dpi=150),
        on_line=lambda _l: None, on_finish=lambda t: finished.append(t))
    assert finished and finished[0] and all(p.exists() for p in finished[0])
    run_dir = work_dir / "runs" / "run1"
    stem = "preset_proj"
    sidecar = json.loads((run_dir / f"{stem}.channels.json").read_text(encoding="utf-8"))
    assert sidecar.get("layout", {}).get("engine") == "chromiq", \
        "the engine must lay out the loaded .ti1, not printtarg"


def test_build_chart_accepts_area_default_kwargs(tmp_path: Path) -> None:
    """Regression (beta.26): the area-first default-patch-size keys threaded into
    the build kwargs (area_default_w/h) must be accepted by build_chart — they
    crashed engine generation with a TypeError."""
    from workflow.layout_engine import chart
    ti1 = tmp_path / "p.ti1"
    ti1.write_text(
        'CTI1\nCOLOR_REP "RGB"\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\nNUMBER_OF_SETS 3\n'
        'BEGIN_DATA\n1 100 0 0\n2 0 100 0\n3 0 0 100\nEND_DATA\n', encoding="utf-8")
    res = chart.build_chart(
        str(ti1), str(tmp_path / "out"), instrument="i1", paper="A4",
        layout_mode="area_first", area_method="by_grid",
        area_default_w=16.0, area_default_h=20.0, dpi=72)
    assert res.layout.total_patches >= 3


def test_engine_randomize_scrambles_locations(tmp_path: Path) -> None:
    """The engine honours randomize for a loaded .ti1 — the SAMPLE_LOC mapping is
    scrambled vs a preserve-order build (so a chart applied from the editor with
    "Randomise patch order" on is actually randomised; #93 Knut bug)."""
    import re
    from workflow.layout_engine import chart
    ti1 = tmp_path / "p.ti1"
    rows = "\n".join(f"{i} {i*4%101} {i*7%101} {i*11%101}" for i in range(1, 61))
    ti1.write_text('CTI1\nCOLOR_REP "RGB"\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
                   'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n'
                   'NUMBER_OF_SETS 60\nBEGIN_DATA\n' + rows + '\nEND_DATA\n', encoding="utf-8")

    def first_locs(rnd):
        chart.build_chart(str(ti1), str(tmp_path / f"o{rnd}"), instrument="i1",
                          paper="A4", seed=7, randomize=rnd, dpi=72)
        t = (tmp_path / f"o{rnd}.ti2").read_text(encoding="utf-8")
        return re.findall(r'^\d+ "([A-Z0-9]+)"', t, re.M)[:10]

    assert first_locs(False) != first_locs(True)   # randomise actually changes it


def test_engine_writes_per_page_strip_counts(tmp_path: Path) -> None:
    """PASSES_IN_STRIPS2 must be the per-page strip count, comma-separated, like
    printtarg — so chartread + the Create Chart layout-info read the right number
    of strips per page (#93, Knut: on-screen strips were wrong)."""
    import re
    from workflow.layout_engine import chart, geometry, instruments, papers
    from core.strip_utils import parse_passes_per_page
    ti1 = tmp_path / "p.ti1"
    rows = "\n".join(f"{i} {i*4%101} {i*7%101} {i*11%101}" for i in range(1, 1220))
    ti1.write_text('CTI1\nCOLOR_REP "RGB"\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
                   'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n'
                   'NUMBER_OF_SETS 1219\nBEGIN_DATA\n' + rows + '\nEND_DATA\n', encoding="utf-8")
    res = chart.build_chart(str(ti1), str(tmp_path / "out"), instrument="i1",
                            paper="A4", layout_mode="area_first",
                            area_method="by_grid", area_default_w=8.0,
                            area_default_h=10.0, dpi=72)
    counts = parse_passes_per_page(tmp_path / "out.ti2")
    assert len(counts) == res.layout.pages > 1          # one entry per page
    # passes × steps accounts for the whole (padded) patch set.
    assert sum(counts) * res.layout.steps_in_pass == res.layout.total_patches
    # not the old single-number bug (every page reads the same full count except last)
    assert counts[0] == counts[0] and counts[-1] <= counts[0]
