# Code map: ChromIQ layout engine and its consumers (read-only, generated 2026-09-07, commit 80975e65)

## workflow/layout_engine/ (Qt-free core)

### workflow/layout_engine/__init__.py (      22 lines)

### workflow/layout_engine/area_fit.py (     328 lines)
    24:def _usable(geom, w_mm: float, h_mm: float) -> tuple[float, float]:
    48:def _fit_columns(base: dict, w_mm: float, h_mm: float, cols: int,
    82:def _as_area_first(geom):
    98:def derive_area_patch_size(kw: dict) -> tuple[float, float] | None:

### workflow/layout_engine/calibration.py (     101 lines)
    26:class Calibration:
    58:def read_cal(path: str | Path) -> Calibration:
    84:def cal_table_text(cal: Calibration) -> str:
    89:def apply_to_target(target, cal: Calibration):

### workflow/layout_engine/chart.py (     427 lines)
    21:class ChartResult:
    37:def build_ti2_from_ti1(
    90:def build_chart(
    417:def build_from_recipe(ti1_path: str | Path, out_base: str | Path, recipe

### workflow/layout_engine/cht_writer.py (     145 lines)
    40:def _edge_list(positions_len: list[tuple[float, float]]) -> list[tuple[float, float, float]]:
    58:def fiducials_from_boxes(boxes: list[dict]) -> tuple[float, ...] | None:
    74:def build_cht_text(boxes: list[dict], expected: list[tuple[str, float, float, float]],
    123:def boxes_from_patch_rects(patch_rects: list[dict], paper_h_mm: float, dpi: int,
    140:def write_cht(path: str | Path, boxes: list[dict],

### workflow/layout_engine/cie_writer.py (      84 lines)
    44:def cie_rows_from_ti3(data: Ti3Data) -> list[tuple[str, float, float, float]]:
    52:def build_cie_text(rows: list[tuple[str, float, float, float]],
    75:def write_cie(path: str | Path, data_or_ti3: Ti3Data | str | Path,

### workflow/layout_engine/colorants.py (     270 lines)
    59:def rep_ink_codes(color_rep: str) -> list[str] | None:
    82:def _srgb1_to_linear(v: float) -> float:
    86:def _linear1_to_srgb(v: float) -> float:
    90:def _lab_to_linear_srgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    111:def ink_absorption_linear(code: str) -> tuple[float, float, float]:
    141:def _composite_extra_inks(base_rgb: tuple[float, float, float],
    163:def to_display_rgb(device: tuple[float, ...], color_rep: str) -> tuple[int, int, int]:
    205:def luminance(rgb: tuple[int, int, int]) -> float:
    211:def to_device_approx(rgb: tuple[int, int, int],
    239:def to_device_approx_array(rgb, device_fields: list[str]):

### workflow/layout_engine/contrast.py (      97 lines)
    14:LOW_CONTRAST_THRESHOLD = 32.0
    17:def spacer_rgb(above: tuple[int, int, int] | None,
    40:def _rgb_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    44:def colored_spacer_rgb(above: tuple[int, int, int] | None,
    67:def spacer_for_mode(mode: str, above, below,
    75:def min_boundary_contrast(patch_rgbs: list[tuple[int, int, int]]) -> float:
    88:def low_contrast_passes(slot_rgbs: list[tuple[int, int, int]], steps_in_pass: int

### workflow/layout_engine/geometry.py (     786 lines)
    18:class LayoutError(ValueError):
    23:class Layout:
    39:def compute(geom: Geom, paper_w_mm: float, paper_h_mm: float, npat: int,
    198:class Placement:
    220:def placement(geom: Geom, paper_w_mm: float, paper_h_mm: float, layout: Layout) -> Placement:
    336:def _align_fractions(align: str) -> tuple[float, float]:
    349:def realized_margins_mm(geom: Geom, paper_w_mm: float, paper_h_mm: float,
    386:CLIP_CONTENT_INSET_MM = 4.0
    389:def clip_area_mm(geom: Geom, paper_h_mm: float, paper_w_mm: float | None = None
    426:def clip_area_px(geom: Geom, paper_h_mm: float, dpi: int,
    437:def strip_rects_px(geom: Geom, paper_w_mm: float, paper_h_mm: float,
    483:def patch_rects_px(geom: Geom, paper_w_mm: float, paper_h_mm: float,
    558:def spacer_rects_px(geom: Geom, paper_w_mm: float, paper_h_mm: float,
    597:def patches_per_sheet(geom: Geom, paper_w_mm: float, paper_h_mm: float,
    610:def _comb(anchor: float, step: float, lo: float, hi: float) -> list[float]:
    643:def helper_marker_lines_mm(geom: Geom, paper_w_mm: float, paper_h_mm: float,

### workflow/layout_engine/instruments.py (     802 lines)
    22:MAXPPROW = 500          # printtarg.c: absolute max patches per pass/row
    23:MAXROWLEN = 5000.0      # printtarg.c MAXROWLEN — large enough to never bind for sheet sizes
    55:ROW_LABEL_BAND_MM = 7.5
    78:DELEGATED = {"isis"}
    80:def _inch(mm: float) -> float:
    85:class Geom:
    202:def is_hexagonal(geom) -> bool:
    214:def hex_capable(key: str) -> bool:
    228:def hex_capable_instruments() -> "list[str]":
    233:def supported() -> list[str]:
    237:def default_ruler_mm(key: str) -> float:
    260:def build(
    397:GEOM_BUILD_KEYS = (
    407:def geom_from_build_kwargs(kw: dict, thresholds: dict | None = None) -> Geom:
    461:def _build_base(

### workflow/layout_engine/margins_fit.py (     111 lines)
    32:def _num(v) -> float | None:
    41:def clamp_margins_to_thresholds(

### workflow/layout_engine/papers.py (     100 lines)
    44:def parse_custom(code: str) -> tuple[float, float] | None:
    55:def dimensions_mm(code: str) -> tuple[float, float]:
    65:def label(code: str) -> str:
    70:def friendly_label(code: str) -> str:
    84:def list_papers(instrument: str | None = None, *, for_engine: bool = False

### workflow/layout_engine/permutation.py (      98 lines)
    19:DEFAULT_STRIP_PATTERN = "A-Z, A-Z"
    20:DEFAULT_PATCH_PATTERN = "0-9,@-9,@-9;1-999"
    23:def alpha_label(n: int) -> str:
    34:def _is_alpha_pattern(pattern: str) -> bool:
    39:def make_labeller(pattern: str):
    52:def location_label(slot: int, steps_in_pass: int,
    67:def pick_seed(rng: random.Random | None = None) -> int:
    73:def location_permutation(n: int, seed: int, randomize: bool = True) -> list[int]:
    85:def preview(total: int, steps_in_pass: int,

### workflow/layout_engine/preflight.py (     153 lines)
    30:MIN_PATCH_MM = 6.0
    34:class PreflightReport:
    48:def check(geom: Geom, layout: Layout, *,
    77:def indicator_width_warning(geom, dpi: int, *, font: str = "JetBrains Mono",
    109:class RoundTripResult:
    116:def _bin(name: str, argyll_bin: str | None) -> str | None:
    123:def roundtrip_available(argyll_bin: str | None = None) -> bool:
    127:def validate_roundtrip(ti2_path: str | Path, profile_icc: str | Path,

### workflow/layout_engine/presets.py (     622 lines)
    24:SUPPORTED_INSTRUMENTS = ("i1", "p3", "CM", "41", "51", "SS", "CR30")
    28:class LayoutRecipe:
    494:def default_recipe(instrument: str = "i1", paper: str = "A4", *, mode: str | None = None
    548:class PresetStore:

### workflow/layout_engine/raster.py (    1959 lines)
    45:FONTS = {
    53:FONT_STYLE_FILES = {
    56:DEFAULT_INDICATOR_FONT = "JetBrains Mono"
    60:WORDMARK_FONT = "Instrument Serif"
    61:WORDMARK_RGB = (28, 27, 24)     # #1c1b18 — light-mode "Chrom" colour
    62:WORDMARK_IQ_RGB = (255, 69, 115)  # #ff4573 — magenta accent for "IQ"
    69:TEXT_EDGE_MARGIN_MM = 4.0
    71:ACCENT_RGB = (
    82:def _system_font_dirs() -> list[Path]:
    95:def _style_key(subfamily: str) -> str:
    102:def _system_font_map() -> dict[str, dict[str, str]]:
    128:def _font_path(family: str, style: str = "regular") -> str | None:
    140:def font_supports(family: str) -> tuple[bool, bool]:
    167:def _font(px: int, family: str = DEFAULT_INDICATOR_FONT,
    191:def _font_file_and_variation(family: str, bold: bool, italic: bool
    209:INDICATOR_LETTER_SPACING = 0.12
    212:INDICATOR_FIT_FRAC = 0.80
    213:INDICATOR_MIN_LEGIBLE_MM = 1.5   # auto-size floor — smaller is unreadable in print
    216:def _draw_indicator(draw, cx: int, top: int, text: str, font, spacing_px: int) -> None:
    237:def _indicator_tile(text: str, font, spacing_px: int, degrees: int) -> Image.Image:
    259:def _widest_upper_px(px: int, font: str) -> float:
    278:def effective_indicator_size_mm(geom, dpi: int, font: str, size_mm: float) -> float:
    306:def _furniture_reserves_mm(geom, kw: dict) -> tuple[float, float]:
    357:def apply_furniture_reserves(geom, kw: dict):
    372:ROW_LABEL_PITCH_FRAC = 0.85
    375:def effective_row_label_size_mm(geom, dpi: int, font: str,
    402:def apply_row_label_geometry(geom, kw: dict):
    476:def _rows_that_fit(geom, kw: dict) -> int:
    506:def clip_text_lines(text: "str | None") -> list[str]:
    541:def render_clip_strip(mode: str, *, width_px: int, height_px: int, dpi: int,
    628:def _italic_tile(text: str, font, fill: tuple, stroke_w: int = 0,
    679:def _fit_branding_sizes(extra_lines: list[str], width_px: int, height_px: int,
    750:def _vwordmark(extra_lines: list[str], width_px: int, height_px: int,
    837:def _vtext(text: str, font_family: str, width_px: int, height_px: int,
    910:def _notes_sample_ctx() -> dict:
    918:def _draw_wordmark_h(canvas: Image.Image, draw: "ImageDraw.ImageDraw",
    949:def _notes_row(draw: "ImageDraw.ImageDraw", font, y_center: float, x0: float,
    981:def _render_notes_strip(width_px: int, height_px: int, dpi: int,
    1054:class RenderResult:
    1069:def _hexagon_points(x0: int, y0: int, w: int, ph: int, step: int):

### workflow/layout_engine/ti1_reader.py (     100 lines)
    27:def _is_device_field(name: str) -> bool:
    36:class ColorTarget:
    61:def read_ti1(path: str | Path) -> ColorTarget:

### workflow/layout_engine/ti2_writer.py (     133 lines)
    21:DEFAULT_WHITE_POINT = (95.106486, 100.0, 108.844025)
    26:def _fmt(v: float) -> str:
    30:def build_ti2_text(
    128:def write_ti2(path: str | Path, *args, **kwargs) -> Path:

### workflow/layout_engine/vector_pdf.py (     314 lines)
    35:def _colorant_names(device_fields: list[str]) -> list[str]:
    52:def _tint_fn_body(device_fields: list[str]) -> str:
    75:class _Obj:
    113:def _fill_color_op(dev01: tuple[float, ...], n: int) -> str:
    125:def _page_content(page_elems: list[tuple], device_fields: list[str],
    212:def save_vector_pdf(result, target, out_path: str | Path, *,

### workflow/layout_engine/vector_text.py (     122 lines)
    21:def _face(path: str) -> freetype.Face:
    30:def _prepare(font_path: str, size_px: float, variation: str | None) -> freetype.Face:
    47:def ascent_px(font_path: str, size_px: float, variation: str | None = None) -> float:
    53:def _glyph_ops(face: freetype.Face, ch: str, ox: float, oy: float, px2pt: float
    91:def run_ops(text: str, font_path: str, size_px: float,

## Consumers

### workflow/chart_creator.py (    2165 lines)
    181:def match_printtarg_error(text: str) -> "tuple[str, str] | None":
    201:def printtarg_said(text: str) -> str:
    221:def _engine_padding_log_line(total: int, padding: int) -> str:
    239:def _chromiq_clip_active(p: "ChartParams") -> bool:
    261:def _effective_suppress_lb(p: "ChartParams") -> bool:
    273:def _extra_printtarg_affects_layout(extra: str) -> bool:
    320:def _shorten_for_stamp(token: str) -> str:
    328:def _shorten_argv_for_stamp(args: list[str]) -> list[str]:
    394:def _neutrals_from_eff_sheets(eff_sheets: float,
    418:def manual_neutrals(total_patches: int,
    437:def guided_neutrals(instrument: str,
    521:class ChartParams:
    631:class ChartCreator:
    672:    def generate(
    773:    def restart_with_fast_sampler(self) -> bool:
    820:    def cancel(self) -> None:
    844:    def estimate_patches(
    947:    def load_ti1_and_generate_preview(
    1125:    def primary_failure(self) -> tuple[str, str, str] | None:
    1130:    def unmatched_failure(self) -> tuple[str, str] | None:
    1140:    def captured_warnings(self) -> list[tuple[str, str, str]]:

### workflow/margin_inspector.py (     575 lines)
    49:class MarginReport:
    75:    def as_dict(self) -> dict[str, float | None]:
    84:class Violation:
    101:def check_violations(
    130:def _tolerance_mm(report: MarginReport) -> float:
    204:def measure_from_engine(
    311:def _tiff_dpi(path: Path, fallback: float) -> float:
    335:def _estimate_patch_width_mm(block_w_mm: float, n_strips: int) -> Optional[float]:
    349:def measure_margins(
    434:def _dense_run(fill: np.ndarray) -> Optional[tuple[int, int]]:
    506:def _patch_area_bbox(arr: np.ndarray) -> Optional[tuple[int, int, int, int]]:
    545:def _steps_in_pass(ti2_path: "Path | str") -> int | None:
    556:def _page_index_of(tif_path: Path, n_pages: int = 0) -> int:

### workflow/layout_from_render.py (     378 lines)
    37:class RenderGeometryError(ValueError):
    61:def _load_page(path: Path) -> tuple[np.ndarray, float]:
    71:def _grid_boundaries(candidates: list[int], n_cells: int, *,
    99:def _fit_starts(candidates: list[int], n: int,
    158:def _column_candidates(img: np.ndarray, y0: int, y1: int) -> list[int]:
    165:def _row_candidates(img: np.ndarray, x0: int, x1: int) -> list[int]:
    172:def _cluster(xs: np.ndarray) -> list[int]:
    182:def _ink_rows(img: np.ndarray) -> tuple[int, int]:
    196:def _strip_index(letters: str) -> int:
    205:def parse_ti2_strips(ti2_path: str | Path):
    237:def _expected_rgb8(rgb100: np.ndarray) -> np.ndarray:
    241:def _validate_cell(img: np.ndarray, x0: float, x1: float, y0: float, y1: float,
    260:def derive_layout_from_render(tiff_paths: list, ti2_path: str | Path) -> dict:
    338:def _validated_strip(img: np.ndarray, sx0: float, sx1: float,
    359:def _trim_to_colour(img: np.ndarray, x0: float, x1: float, y0: float,

### workflow/grid_layout_from_render.py (     296 lines)
    58:class GridGeometryError(ValueError):
    79:def _load_page(path: Path) -> tuple[np.ndarray, float]:
    93:def _rgb100_to_key8(rgb100: np.ndarray) -> np.ndarray:
    99:def _block_bbox(img: np.ndarray, patch_keys: np.ndarray) -> tuple[int, int, int, int]:
    115:def _cluster(xs: np.ndarray) -> list[int]:
    125:def _boundaries(img: np.ndarray, bbox, axis: int) -> list[int]:
    142:def _uniform_grid(lo: float, hi: float, n: int) -> list[float]:
    147:def _fit_count(edges: list[int], lo: int, hi: int) -> int | None:
    167:def _cell_ok(img: np.ndarray, x0, x1, y0, y1, want8) -> bool:
    179:def _cell_is_blank(img: np.ndarray, x0, x1, y0, y1) -> bool:
    187:def derive_grid_layout(tiff_paths: list, patch_rgb100, locs=None) -> dict:
    263:def _build_grid(loaded, cols, rows_total, rows_per_page, n_patches, want8,

### workflow/hex_support.py (     228 lines)
    47:def hex_scanner_message() -> str:
    74:def hex_scanner_allowed(settings) -> bool:
    109:def hex_two_heights_note() -> str:
    134:def hex_patch_height_mm(row_pitch_mm: float) -> float:
    145:def recipe_is_hexagonal(recipe) -> bool:
    171:def settings_are_hexagonal(create_chart_settings) -> bool:
    199:def chart_is_hexagonal(chart_path: "str | Path | None") -> bool:

### workflow/ti2_relayout.py (    2143 lines)
    98:class PrinttargCannotLayOutChart(RuntimeError):
    109:def _custom_paper_mm(paper_flag: str) -> "tuple[float, float] | None":
    120:def check_printtarg_can_lay_out(instrument_flag: str, paper_flag: str) -> None:
    152:def instrument_to_flag(target_instrument: str | None) -> str:
    192:def paper_to_flag(w_mm: float, h_mm: float) -> str:
    207:class Patch:
    215:class ChartSpec:
    235:    def n_channels(self) -> int:
    240:    def from_ti2(cls, path: Path) -> "ChartSpec":
    321:    def new(
    373:def _split_cgats(line: str) -> list[str]:
    381:def _loc_sort_key(p: "Patch") -> tuple[int, int]:
    391:def _read_sibling_density_extremes(
    446:class LayoutOptions:
    490:    def to_printtarg_args(self) -> list[str]:
    532:def _layout_from_dict(raw: dict | None) -> "LayoutOptions":
    541:def recipe_layout_from_options(options: "LayoutOptions") -> dict:
    578:def save_editor_meta(ti2_path: Path, spec: "ChartSpec",
    635:def load_editor_recipe(ti2_path: Path) -> dict | None:
    646:def load_editor_meta(ti2_path: Path) -> tuple["LayoutOptions", str] | None:
    666:def parse_color_values(text: str) -> list[tuple[float, float, float]]:
    711:def default_program(spec: ChartSpec) -> list[tuple[float, ...]]:
    729:def load_rgb_program(path: Path) -> list[tuple[float, float, float]]:
    772:def load_colour_file(path: Path) -> list[tuple[float, float, float]]:
    806:def seed_from_targen(
    864:def color_rep_for_inks(ink_codes: list[str] | tuple[str, ...]) -> tuple[str, list[str]]:
    902:def _naive_xyz_nchannel(
    916:    def lin(c8: int) -> float:
    927:def write_ti1_nchannel(
    988:def write_ti1(
    1039:class RegenResult:
    1048:def regenerate(
    1191:class RandomisationReport:
    1206:def _read_ti2_strips(ti2_path: Path) -> list["np.ndarray"]:
    1276:def _mean_row_dist(a: "np.ndarray", b: "np.ndarray") -> float:
    1284:def analyze_randomisation(ti2_path: Path) -> RandomisationReport:
    1346:def tag_ti2_randomised(ti2_path: Path) -> bool:
    1371:def _patch_ti2_for_triple_density(ti2: Path) -> None:
    1397:class Spacer:
    1405:    def area(self) -> int:
    1430:def _label_band_end(arr: np.ndarray) -> int | None:
    1467:def _patch_grid_bbox(arr: np.ndarray) -> tuple[int, int, int, int] | None:
    1533:def spacer_mask(default_tif: Path, bw_tif: Path, *, thresh: int = 8) -> np.ndarray:
    1556:def segment_spacers(
    1638:def _split_band_by_strips(
    1672:def _split_band_by_colour(
    1715:def recolor_spacers(
    1739:def assert_data_integrity(
    1798:def assert_patches_untouched(before_tif: Path, after_tif: Path, mask: np.ndarray) -> None:
    1810:def _imread_rgb(path: Path) -> np.ndarray:
    1839:def _per_strip_step_grids(clean_centres, steps):
    1873:    def lookup(within_strip: int) -> list[float]:
    1883:def patch_geometry_for_page(

### workflow/chart_slot.py (     164 lines)
    55:def _is_image(p: Path) -> bool:
    59:def has_layout_recipe(files) -> bool:
    65:class ChartSlot:
    75:    def live_files(self) -> "list[Path]":
    92:    def side_files(self) -> "list[Path]":
    103:    def files_to_copy(self) -> "list[Path]":
    116:def slot_for_run(run: Run) -> ChartSlot:
    124:def slot_for_verification(verification: Verification) -> ChartSlot:
    133:def slot_for_calibration(calibration: Calibration) -> ChartSlot:
    154:def slot_for(target) -> ChartSlot:

### workflow/chart_integrity.py (     246 lines)
    28:class Blast(Enum):
    44:class ChartCost:
    70:    def warn(self) -> bool:
    74:    def can_duplicate(self) -> bool:
    78:    def pages_are_the_only_copy(self) -> bool:
    83:def _attr(run, name):
    92:def _exists(path) -> bool:
    99:def _profile_exists(run) -> bool:
    116:def _pages(files) -> int:
    120:def _missing_for_duplicate(run) -> "list[str]":
    140:def _dated_verifications(run) -> int:
    147:def assess_profiling_chart(run) -> ChartCost:
    215:def assess_verification_chart(run) -> ChartCost:

### workflow/chart_exports.py (      96 lines)
    19:def _parse_cgats(path: Path) -> tuple[list[str], list[list[str]]]:
    33:def write_colours_txt(ti1_path: str | Path, txt_path: str | Path) -> Path | None:
    55:def write_sidecars(ti1_path: str | Path, out_dir: str | Path,

### workflow/page_geometry.py (     230 lines)
    37:def get_page_size_points(ppd_path: str | None, value: str) -> tuple[float, float] | None:
    70:def get_imageable_area_points(ppd_path: str | None, value: str) -> tuple[float, float] | None:
    109:def read_tiff_dimensions_points(tiff_path: Path, fallback_dpi: float = 300.0) -> tuple[float, float]:
    124:def _read_dpi(page: tifffile.TiffPage, fallback: float) -> float:
    158:def compute_orientation(
    184:def check_size_mismatch(

### ui/dialogs/layout_options_panel.py (    4698 lines)
    72:def mm_to_pt(mm: float) -> float:
    77:def pt_to_mm(pt: float) -> float:
    82:class LayoutOptionsPanel(QWidget):
    87:    def set_appearance(self, mode: str) -> None:
    165:    def mode_label_for(inst: str) -> str:
    181:    def mode_tooltip_for(inst: str) -> tuple[str, str]:
    260:    def modes_for(inst: str) -> list[tuple[str, str]]:
    2329:    def cal_settings(self) -> tuple[str | None, bool]:
    2339:    def set_cal(self, path: str, mode: str) -> None:
    2695:    def clip_enabled(self) -> bool:
    2700:    def set_clip_enabled(self, on: bool) -> None:
    2720:    def showEvent(self, event) -> None:      # noqa: N802 (Qt override)
    2726:    def changeEvent(self, event) -> None:    # noqa: N802 (Qt override)
    2827:    def set_label_style_defaults(self, fn) -> None:
    2870:    def refresh_label_style_defaults(self) -> None:
    2897:    def set_threshold_lookup(self, fn) -> None:
    3606:    def resume_clip_preview(self) -> None:
    3773:    def show_built_seed(self, seed: "int | None") -> None:
    3870:    def set_spacer_override(self, flat: int, hexcol: "str | None") -> None:
    4205:    def selection(self) -> tuple[str, str, str]:
    4215:    def get_pages(self) -> int:
    4218:    def set_pages(self, n: int) -> None:
    4222:    def set_pages_enabled(self, enabled: bool) -> None:
    4230:    def get_recipe(self, base: LayoutRecipe | None = None) -> LayoutRecipe:
    4294:    def set_helper_markers_supported(self, supported: bool,
    4338:    def set_recipe(self, r: LayoutRecipe) -> None:
    4575:    def apply_to_recipe(self, r: LayoutRecipe) -> LayoutRecipe:

### ui/margin_inspector_panel.py (     595 lines)
    54:def _edges():
    61:class MarginInspectorPanel(QGroupBox):
    337:    def set_appearance(self, mode: str) -> None:
    364:    def guides_enabled(self) -> bool:
    367:    def set_guides_checked(self, on: bool) -> None:
    370:    def measured_guides_enabled(self) -> bool:
    373:    def set_measured_guides_checked(self, on: bool) -> None:
    376:    def coords_enabled(self) -> bool:
    379:    def set_coords_checked(self, on: bool) -> None:
    394:    def text_notes(self) -> str:
    403:    def show_placeholder(self) -> None:
    410:    def update_report(

### ui/chart_layout_info_panel.py (     276 lines)
    28:def _flag_by_weight() -> bool:
    35:class ChartLayoutInfoPanel(QGroupBox):
    174:    def set_actual(self, *, total: int, rows: int, cols: int, pages: int,
    192:    def clear_actual(self) -> None:
    196:    def set_estimate(self, *, total: int, rows: int, cols: int, pages: int,
    206:    def clear_estimate(self) -> None:
    210:    def show_placeholder(self) -> None:

### ui/dialogs/preflight_dialog.py (     129 lines)
    27:def _neutral() -> bool:
    33:class PreflightDialog(QDialog):
    128:    def dont_ask_again(self) -> bool:

### ui/dialogs/ti2_relayout_dialog.py (    8224 lines)
    56:def _acc() -> str:
    67:def _dis_ind() -> str:
    83:def _magenta_tip(title: str, body: str, parent: QWidget | None = None,
    90:def _toggle_locked_prefix(edit: "PrefixLockedLineEdit", on: bool, prefix: str) -> None:
    338:def _padding_note(n: int) -> str:
    355:class _AutoHideLabel(QLabel):
    379:    def setText(self, text: str) -> None:  # noqa: N802
    387:def _uniform_button_width(buttons, *, pad: int = 0) -> None:
    400:def _hint_count_inactive(label: QLabel, active: bool) -> None:
    411:def _as_compact(*widgets) -> None:
    420:def _wire_spacer_mutex(boxes: tuple) -> None:
    450:def _patches_label(n: int) -> str:
    506:def _mod_keys() -> dict[str, str]:
    522:def _paper_code_known(code: str) -> bool:
    532:def _unchecked_indicator_css(settings) -> str:
    552:def _qcolor(rgb: tuple[float, float, float]) -> QColor:
    556:def _to100(c: QColor) -> tuple[float, float, float]:
    560:def _display100(vals: tuple, color_rep: str = "iRGB") -> tuple[float, float, float]:
    575:def _swatch_icon(rgb: tuple[float, float, float], size: int = _SWATCH) -> QIcon:
    594:def _ghost_swatch_icon(rgb: tuple[float, float, float], size: int = _SWATCH) -> QIcon:
    616:class _RegenWorker(QThread):
    626:    def run(self) -> None:
    653:class _SwatchDelegate(QStyledItemDelegate):
    673:    def paint(self, painter, opt, idx) -> None:
    710:    def sizeHint(self, opt, idx) -> QSize:
    719:class _ReorderListWidget(QListWidget):
    746:    def startDrag(self, supported_actions) -> None:  # noqa: N802
    763:    def dragMoveEvent(self, ev) -> None:  # noqa: N802
    814:    def dragLeaveEvent(self, ev) -> None:  # noqa: N802
    819:    def dropEvent(self, ev) -> None:  # noqa: N802
    824:    def paintEvent(self, ev) -> None:  # noqa: N802
    854:class _PreviewLabel(QLabel):
    873:    def set_base_pixmap(self, pm: QPixmap | None) -> None:
    880:    def resizeEvent(self, ev) -> None:  # noqa: N802
    884:    def mousePressEvent(self, ev) -> None:  # noqa: N802
    890:    def mouseMoveEvent(self, ev) -> None:  # noqa: N802
    897:    def mouseReleaseEvent(self, ev) -> None:  # noqa: N802
    913:    def paintEvent(self, ev) -> None:  # noqa: N802
    929:class _NewChartDialog(QDialog):
    3502:    def exec(self) -> int:  # noqa: A003 - intentional QDialog.exec override
    3667:    def showEvent(self, ev) -> None:  # noqa: N802
    3684:    def done(self, result: int) -> None:  # noqa: N802
    3944:class _AddPatchesDialog(_NewChartDialog):
    4223:class _EditorSnapshot:
    4240:    def key(self) -> tuple:
    4250:class Ti2RelayoutDialog(WorkAreaClamped, QDialog):
    8185:    def showEvent(self, ev) -> None:  # noqa: N802
    8213:    def closeEvent(self, ev) -> None:  # noqa: N802

## tab_chart.py engine touchpoints (grep engine|recipe|layout)

    1312:    def has_full_layout_setup(self) -> bool:
    5011:    def _set_engine_checked(self, on: bool) -> None:
    5027:    def _on_manual_engine_toggled(self, on: bool) -> None:
    5086:    def _convert_printtarg_to_engine(self) -> None:
    5163:    def _convert_engine_to_printtarg(self) -> None:
    5222:    def _schedule_manual_command_preview(self) -> None:
    5249:    def _refresh_manual_command_preview(self) -> None:
    5546:    def _refresh_layout_estimate(self, use_engine: "bool | None" = None) -> None:
    5606:    def _layout_store(self):
    5611:    def _init_manual_layout_panel(self) -> None:
    5632:    def _sync_engine_panel_selection(self) -> None:
    5683:    def _current_layout_recipe(self):
    5700:    def _pinned_layout_recipe(self):
    5721:    def _pin_restored_recipe(self, params) -> bool:
    5767:    def _layout_recipe_values(self, r) -> dict:
    5787:    def _layout_preset_status(self):
    5801:    def _refresh_manual_preset_bar(self, use_engine: bool, status=None) -> None:
    5812:    def _reset_manual_to_preset(self) -> None:
    5825:    def _update_manual_preset(self) -> None:
    5836:    def _edit_layout_defaults(self) -> None:
    6050:    def _shorten_for_preview(cls, name: str, max_len: int | None = None) -> str:
    6068:    def _preview_target_name(self, mode: str) -> str:
    7117:    def _sync_engine_panel_after_transfer(self) -> None:
    7133:    def _apply_guided_engine_recipe(self, guided_params) -> None:
    7494:    def _apply_instrument_default_margin(self) -> None:
    7765:    def _load_presets_from_settings(self) -> dict:
    7768:    def _save_presets_to_settings(self, presets: dict) -> None:
    7771:    def _is_deletable_preset(self, index: int) -> bool:
    7792:    def _add_builtin_preset_item(
    7863:    def _populate_preset_combo(self, presets: dict, select_name: str | None = None) -> None:
    8020:    def _revert_preset_combo(self, *, to_none: bool = False) -> None:
    8078:    def _open_builtin_preset_overlay(self) -> None:
    8098:    def _activate_builtin_preset(self, key: str) -> None:
    8199:    def _snapshot_preset_state(self) -> dict | None:
    8363:    def _assert_preset_checks(self, snap: dict) -> None:
    8388:    def _restore_preset_state(self, snap: dict) -> None:
    8629:    def _on_preset_activated(self, index: int) -> None:
    8655:    def _on_preset_selected(self, index: int) -> None:
    8960:    def _restore_user_preset(self, data: dict) -> None:
    9049:    def _preset_save_prefill(self) -> tuple[str, bool, bool, bool]:
    9095:    def comparable_presets(self) -> list[tuple[str, list[tuple[str, "Path"]]]]:
    9853:    def _seed_preset_name(self, target_name: str | None) -> None:
    9903:    def _on_preset_save(self) -> None:
    10136:    def _recipe_synced_to_manual(self, recipe: dict) -> dict:
    10161:    def _current_chart_recipe(self) -> dict | None:
    10174:    def _confirm_overwrite_preset(self, name: str) -> bool:
    10190:    def _on_preset_delete(self) -> None:
    10282:    def _seed_manual_printtarg_from_layout(self, opts) -> None:
    10398:    def _ti1_preset_active(self) -> bool:
    10410:    def _update_preset_locks(self) -> None:
    10517:    def _apply_tc918_preset(self, target_name: str | None = None) -> bool:
    10572:    def _apply_colormunki_td_preset(
    10649:    def _fls_engine_recipe(self, p: "_Ti1Preset"):
    10675:    def _seed_knut_preset(self, key: str, target_name: str | None = None) -> None:
    10784:    def _apply_knut_preset(self, key: str, target_name: str | None = None) -> bool:
    11551:    def _carry_engine_recipe_from(self, channels_json) -> None:
    11713:    def _apply_prebuilt_preset(self, key: str, target_name: str | None = None) -> bool:
    11987:    def _targen_skipped_layout_name(self) -> str | None:
    12006:    def _active_layout_name(self) -> str | None:
    12236:    def _engine_geom(self, instr: str, paper: str, *, dd: bool, td: bool,
    12304:    def _engine_capacity(self, instr: str, paper: str, *, dd: bool, td: bool,
    12318:    def _engine_info_line(self, instr: str, paper: str, dpi: int, *, dd: bool,
    12343:    def _engine_info_line_from_recipe(r) -> str:
    13796:    def _update_isis_preview_banner(self) -> None:
    15844:    def _gamut_coverage(self, profile: "Path", margin: str,
    15920:    def _recipe_capacity(self) -> "int | None":
    16122:    def _gamut_sheet_estimate(self, patches: int) -> str:
    17337:    def _set_margin_chart(self, tiffs: "list[Path]", ti2: "Path | None") -> None:
    17350:    def _estimate_patch_total(self) -> "int | None":
    17421:    def _predict_layout_info(self, geom, paper: str, pages_req: int,
    17457:    def _update_layout_info(self) -> None:
    17577:    def _update_margin_inspector(self) -> None:
    17708:    def _engine_text_overflow_warnings(self) -> "list[str]":
    17872:    def _refresh_margin_guides(self, report, thresholds, violations) -> None:
    17899:    def _on_margin_guides_toggled(self, on: bool) -> None:
    17903:    def _on_margin_measured_guides_toggled(self, on: bool) -> None:
    17966:    def _set_engine_recipe(self, recipe) -> None:
    18171:    def _on_margin_coords_toggled(self, on: bool) -> None:
    18176:    def _chart_own_margins(self) -> "dict | None":
    18272:    def current_margin_combo(self) -> "tuple[str, str, str] | None":
    18297:    def current_layout_combo(self) -> "tuple[str, str, str] | None":
    18324:    def refresh_margin_inspector_settings(self) -> None:
    18338:    def _recipe_rebuilds_its_own_sheet(ti2: Path) -> bool:
    18459:    def _on_auto_preview_toggled(self, on: bool) -> None:
    18518:    def _layout_signature(self) -> "str | None":
    18597:    def _settle_live_preview(self) -> None:
    18628:    def _cancel_pending_auto_preview(self) -> None:
    18658:    def _maybe_schedule_auto_preview(self) -> None:
    18679:    def _auto_regenerate_preview(self) -> None:
    18771:    def _preview_paused_body(self) -> str:
    18783:    def _say_preview_is_paused(self) -> None:
    19258:    def _resolve_total_patches(self, p: ChartParams, use_estimate: bool) -> int:
    19293:    def _apply_auto_neutrals(self, p: ChartParams, use_estimate: bool) -> None:

## Settings keys touching the engine (core/settings.py)

    51:    # generated by workflow/layout_engine instead of ArgyllCMS printtarg.
    61:    "use_chromiq_layout_engine": True,
    123:    # chartread's -T multiplies the instrument's patch consistency threshold:
    162:    "profcheck_refine_threshold":   2.0,
    227:    # Measurement Report Pass thresholds (ΔE00) — the defaults the report opens
    229:    "report_pass_threshold_avg": 2.0,
    230:    "report_pass_threshold_max": 3.0,
    255:    # threshold is expressed as "minimum samples per patch" (Knut's method:
    336:    # thresholds, and flag violations for jig/rig users.
    339:    "margin_violation_notify":   True,    # warn when a measured margin < threshold
    340:    "margin_guides_show":        False,   # dotted threshold guide lines on preview
    344:    # page edges so a ruler can be laid on the sheet while measuring. These are
    354:    "margin_thresholds":         "",      # JSON blob; "" → default_margin_thresholds()
    355:    # Scanner/camera profiling: misalignment-check thresholds (Knut #108).
    490:# Margin-threshold seed defaults
    495:# The i1Pro values come from the X-Rite/enlarged-ruler analysis (≈11 mm white
    509:_I1_DESC = "i1Pro ruler / jig"
    510:_CM_DESC = "ColorMunki ruler / jig"
    511:# Knut #82: thresholds are 10 mm sides/bottom + 24 mm Top (label edge) for the
    536:_I1P3_DESC = "i1Pro 3+ ruler / jig"
    584:    label is ignored — only the numeric thresholds decide equality)."""
    635:    6/6/24/6 or the schema-13 6/6/30/10. A threshold the user tuned for their own
    686:def default_margin_thresholds() -> dict[str, dict[str, Any]]:
    687:    """A fresh copy of the seed threshold table (see :data:`_MARGIN_SEED`)."""
    693:def parse_margin_thresholds(raw: str) -> dict[str, dict[str, Any]]:
    694:    """Decode the stored margin-threshold JSON blob (``""`` → seed defaults)."""
    698:        return default_margin_thresholds()
    704:        log.warning("Corrupt margin_thresholds blob — using seed defaults")
    705:    return default_margin_thresholds()
    708:def serialize_margin_thresholds(table: dict[str, dict[str, Any]]) -> str:
    715:    """Canonical "<instrument>|<paper> <Orientation>" threshold key."""
    722:# Engine instrument flag → margin-threshold instrument label (matches the seed
    730:# (named, "WxH", rotated) maps to one threshold-combo paper name; orientation is
    754:def thresholds_for_combo(
    758:    """The margin-threshold entry for an engine instrument flag + page size, or
    759:    None when the combo has no thresholds. Used to enforce the user's minimums
    895:            dropped.append("margin_thresholds[A4/Letter Landscape jig]")
    897:            dropped.append("margin_thresholds[i1Pro A4 Portrait/A3 Landscape bottom→19mm]")
    899:            dropped.append("margin_thresholds[ColorMunki top→30mm, bottom→10mm]")
    901:            dropped.append("margin_thresholds[ColorMunki top→33mm]")
    914:        if self._migrate_layout_engine_default():
    915:            dropped.append("use_chromiq_layout_engine (ChromIQ layout engine "
    1001:    def _migrate_layout_engine_default(self) -> bool:
    1010:        raw = self._qs.value("use_chromiq_layout_engine", None)
    1015:            self._qs.remove("use_chromiq_layout_engine")
    1027:        schema 9: the default floor moved to 50 ΔE, so the reset threshold tracks
    1044:        margins, matching portrait. Upgrades a stored ``margin_thresholds`` blob
    1049:        raw = self._qs.value("margin_thresholds", None)
    1053:            table = parse_margin_thresholds(str(raw))
    1058:            self._qs.setValue("margin_thresholds",
    1059:                              serialize_margin_thresholds(table))
    1065:        ``margin_thresholds`` blob in place, but only for rows still holding the
    1068:        raw = self._qs.value("margin_thresholds", None)
    1072:            table = parse_margin_thresholds(str(raw))
    1077:            self._qs.setValue("margin_thresholds",
    1078:                              serialize_margin_thresholds(table))
    1086:        Upgrades a stored ``margin_thresholds`` blob in place, but only rows
    1087:        still holding a shipped default. A threshold the user tuned is left
    1090:        raw = self._qs.value("margin_thresholds", None)
    1094:            table = parse_margin_thresholds(str(raw))

## Tests that pin engine behaviour (file: test count)

    test_a_chart_that_names_no_instrument_says_so.py: 4
    test_a_chart_without_a_preview_drops_the_old_geometry.py: 1
    test_a_guided_chart_is_judged_against_its_jig.py: 2
    test_a_hexagon_is_taller_than_its_row_pitch.py: 9
    test_a_long_label_is_not_clipped_by_its_indent.py: 2
    test_a_preset_is_not_a_target_with_nothing_stored.py: 4
    test_an_instrument_default_is_not_an_override.py: 22
    test_area_first_fills_the_margin_box.py: 4
    test_backing_out_of_a_preset_changes_nothing.py: 28
    test_chart_creator_engine.py: 14
    test_chart_creator.py: 41
    test_chart_instrument_comes_from_the_chart.py: 6
    test_chart_layout_info_panel.py: 4
    test_chartread_hex_simulation.py: 4
    test_cht_parser.py: 5
    test_cht_writer.py: 4
    test_clip_branding_wordmark.py: 9
    test_clip_example_table.py: 10
    test_clip_preview_for_every_band.py: 7
    test_clip_preview_renders_once.py: 7
    test_clip_says_when_it_is_overridden.py: 13
    test_colormunki_builtin_presets.py: 16
    test_colormunki_margins.py: 12
    test_cr30_a_gone_instrument_gets_a_window.py: 11
    test_cr30_a_second_instrument_keeps_its_own_tile.py: 6
    test_cr30_builtin_presets.py: 17
    test_cr30_manual_layout_defaults_to_no_spacers.py: 6
    test_cr30_one_instrument_one_learned_tile.py: 16
    test_cr30_opens_the_instrument_once.py: 2
    test_demo_package_readme_pdf.py: 3
    test_engine_accurate_mode.py: 21
    test_engine_builder.py: 11
    test_engine_comparison_help.py: 5
    test_engine_fallback.py: 42
    test_engine_gp.py: 8
    test_engine_no_combobox.py: 3
    test_engine_panel_selection_sync.py: 2
    test_engine_spot.py: 9
    test_engine_ucs.py: 8
    test_engine_ui.py: 39
    test_engine_v2_candidates.py: 12
    test_engine_v2_harness.py: 16
    test_engine_v2_options.py: 21
    test_engine_xychart.py: 4
    test_every_cht_this_app_writes_is_normalised.py: 2
    test_folder_layout_e2e.py: 9
    test_folder_layout_v2.py: 14
    test_grid_layout_from_render.py: 9
    test_guided_always_uses_the_engine.py: 5
    test_guided_has_no_marker_proposal.py: 4
    test_guided_manual_transfer.py: 12
    test_guided_refinement_advances_after_a_pace_prompt.py: 5
    test_guided_refinement_survives_settings_load.py: 5
    test_help_card_pdf_is_really_written.py: 4
    test_helper_marker_count.py: 5
    test_helper_marker_edges_and_overlay_honesty.py: 13
    test_helper_marker_overlay_follows_the_controls.py: 4
    test_helper_markers_reach_the_chart.py: 24
    test_helper_markers.py: 24
    test_hex_aspect_is_regular.py: 6
    test_hex_overlay_geometry.py: 11
    test_hex_sample_clamp.py: 8
    test_hex_scanner_support.py: 10
    test_hex_strip_overlay.py: 3
    test_hex_support.py: 3
    test_hexagon_locks_the_controls_it_ignores.py: 11
    test_i1pro_preset_order.py: 6
    test_i1pro_w8_builtin_presets.py: 16
    test_i1pro3_builtin_presets.py: 14
    test_instrument_linked_modes.py: 8
    test_instrument_matches_chart.py: 14
    test_knut_beta106_target_instrument.py: 14
    test_knut_beta115_spot_instrument.py: 15
    test_knut_beta116_restore_cht.py: 9
    test_knut_beta119_shortcuts_are_not_instrument_keys.py: 15
    test_knut_beta120_engine_only_features.py: 7
    test_knut_preview_geometry.py: 10
    test_knut_spyderprint_presets.py: 8
    test_layout_ab_sync.py: 4
    test_layout_calibration.py: 5
    test_layout_editor_close.py: 6
    test_layout_editor_undo.py: 10
    test_layout_from_render.py: 5
    test_layout_geometry.py: 46
    test_layout_info_prediction.py: 5
    test_layout_instrument_margins.py: 5
    test_layout_margin_thresholds.py: 6
    test_layout_named_preset_roundtrip.py: 5
    test_layout_options_panel.py: 30
    test_layout_papers.py: 6
    test_layout_permutation.py: 6
    test_layout_preflight.py: 4
    test_layout_presets.py: 12
    test_layout_raster.py: 41
    test_layout_ti1_reader.py: 4
    test_layout_ti2_writer.py: 6
    test_leftclip_engine_toggle.py: 1
    test_live_preview_does_not_replace_a_preset.py: 14
    test_manual_expert_persistence.py: 8
    test_manual_targen_extras.py: 7
    test_margin_check_knows_about_pixels.py: 4
    test_margin_inspector_help_icons.py: 5
    test_margin_inspector_instrument.py: 10
    test_margin_inspector_tab.py: 9
    test_margin_inspector.py: 15
    test_margin_thresholds.py: 12
    test_marker_overlay_says_when_it_is_a_proposal.py: 5
    test_marquee_geometry_cache.py: 7
    test_measure_engine_highlighter.py: 9
    test_measure_guided_shows_what_it_uses.py: 14
    test_measure_stripe_ti2.py: 3
    test_pace_area_layout.py: 7
    test_pace_marginal_band.py: 17
    test_pace_speed_estimate.py: 17
    test_page_geometry_mismatch.py: 5
    test_pdf_page_rules.py: 21
    test_prebuilt_engine_toggle.py: 1
    test_prebuilt_presets_offer_no_setup.py: 2
    test_precond_manual_mirror.py: 1
    test_preset_combo_popup.py: 2
    test_preset_honors_bar_run.py: 13
    test_preset_panel_locks.py: 20
    test_preset_save_prefill.py: 5
    test_redriver_presets_are_knuts.py: 10
    test_report_pdf_layout.py: 6
    test_row_numbers_follow_the_instrument.py: 6
    test_scanner_builtin_presets.py: 10
    test_scanner_two_panel_layout.py: 25
    test_settings_dialog_chart_layout.py: 19
    test_spot_read_instrument_help.py: 9
    test_spot_read_instrument_precedence.py: 31
    test_streaming_instrument_error.py: 8
    test_target_instrument_gate.py: 5
    test_the_estimate_matches_what_is_built.py: 2
    test_the_gamut_count_matches_the_layout.py: 4
    test_the_layout_estimate_follows_the_chart_on_screen.py: 6
    test_the_layout_panel_fits_the_pane_in_every_language.py: 2
    test_the_layout_panel_has_no_two_widgets_in_one_cell.py: 1
    test_the_manual_panel_does_not_scroll_sideways.py: 5
    test_the_margin_advice_is_true_of_this_chart.py: 8
    test_the_margin_warning_names_the_right_minimum.py: 4
    test_the_marker_follows_the_editable_design.py: 3
    test_the_patch_editor_never_asks_printtarg_for_an_engine_chart.py: 11
    test_the_raised_left_margin_is_reported.py: 5
    test_the_row_labels_follow_the_clip_setting.py: 7
    test_the_white_point_default_cannot_clip_a_real_original.py: 24
    test_ti2_loader_model.py: 18
    test_ti2_loader.py: 32
    test_ti2_relayout_nchannel.py: 20
    test_ti2_relayout.py: 42
    test_ti2_tag_gate.py: 8
    test_triple_density_roundtrip.py: 3
    test_vector_pdf.py: 9
    test_webengine_shutdown.py: 5
    test_winusb_never_reaches_a_serial_instrument.py: 7
