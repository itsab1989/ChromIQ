"""Layout recipe + preset store.

A :class:`LayoutRecipe` is the complete, serialisable set of layout settings
used to build a chart.  It is:

* the **source of truth** persisted with a chart (run ``meta.json``) so the
  Create Chart tab and the Edit/Create Chart editor populate identically when a
  chart moves between them, and so the strip/patch geometry can be regenerated
  for the Measure-tab highlighter;
* the unit a **preset** stores, keyed by *instrument × paper × mode-toggle*
  (i1 clip-border on/off, ColorMunki high-density on/off, SpectroScan hex/flat).

The :class:`PresetStore` is a JSON-backed dict of recipes with export / import /
restore-factory-defaults.  All Qt-free.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from . import permutation

SUPPORTED_INSTRUMENTS = ("i1", "p3", "CM", "41", "51", "SS")


@dataclass
class LayoutRecipe:
    instrument: str = "i1"
    paper: str = "A4"
    dpi: int = 300
    randomize: bool = True
    seed: int | None = None
    hflag: bool = False            # SpectroScan hex (n/a elsewhere)
    cm_density: int = 1            # ColorMunki rows: 1 normal, 2 rig, 3 extra-high
    cm_stagger: bool = False       # ColorMunki: offset every second strip (rig)
    spacer_on: bool = True
    spacer_mode: str = "colored"   # "colored" | "bw" | "none"
    spacer_palette: list = field(default_factory=list)  # custom colored-spacer hexes
    spacer_overrides: dict = field(default_factory=dict)  # {str(flat_idx): "#hex"}
    # Bracket each strip with a spacer before the first patch and after the last
    # (what printtarg does). Only meaningful when spacers are on; fits in space
    # the layout already reserves, so it doesn't change the patch count.
    edge_spacers: bool = False
    # Where the patch block sits within the usable area: one of
    # "{top,center,bottom}-{left,center,right}" (middle is plain "center").
    # "top-left" is the default for new charts (Knut, #93); "center-left"
    # reproduces printtarg's behaviour and is kept for older dicts via from_dict.
    patch_area_align: str = "top-left"
    pscale: float = 1.0
    sscale: float = 1.0
    border: float = 6.0            # base margin (drives leader/clip-holder)
    margin_top: float = 6.0        # independent page-edge margins (mm)
    margin_right: float = 6.0
    margin_bottom: float = 6.0
    margin_left: float = 6.0
    # When True, the four margins are taken from Preferences → Instrument Margins
    # for this instrument/paper/orientation (read-only in the panel) (#93, Knut).
    # Defaults ON so a new chart respects the instrument's jig margins out of the
    # box (Knut); a saved preset/dict that set it False keeps its own value.
    use_instrument_margins: bool = True
    patch_w_mm: float = 0.0        # explicit patch width / height (mm); 0 = auto
    patch_h_mm: float = 0.0
    # Layout strategy (#93, Knut). "patch_first" (default) = size the patches
    # (above) and fit as many as possible to the page. "area_first" = fit a
    # target grid into the usable area and SIZE the patches to fill it:
    #   area_cols  strips across   (0 = auto / fill width)
    #   area_rows  patches/strip   (0 = auto / fill height)
    #   area_ratio patch HEIGHT as a fraction of width (height:width) for the
    #              auto-sized dimension; 0 = square. The panel shows it as a
    #              percentage ("minimum patch height, % of width": 150 → 1.5).
    #              Patch size is then derived, not set.
    # Defaults to area-first (Knut); with cols/rows on auto it fills like patch-
    # first until a count is pinned, so it's a safe default.
    layout_mode: str = "area_first"
    # How area-first sizes the grid: "by_width" = from a minimum patch width +
    # height%; "by_grid" = from explicit columns + rows (Knut's two methods).
    area_method: str = "by_width"
    area_cols: int = 0
    area_rows: int = 0
    area_ratio: float = 0.0
    # Minimum patch width (mm) for the auto path: with columns/rows on auto, the
    # engine fits the most patches at this minimum size and then grows them to
    # fill the area (Knut's "max friendliness"). 0 = not used.
    area_min_patch_mm: float = 0.0
    spacer_width_mm: float = 0.0   # 0 = instrument default
    inter_patch_mm: float = 0.0    # extra gap between patches
    strip_gap_mm: float = 0.0      # extra gap BETWEEN strips (adds to row pitch)
    max_strip_mm: float = 0.0      # 0 = no explicit cap
    strip_indicator_gap_mm: float = 0.0
    offset_x_mm: float = 0.0       # whole-chart offset
    offset_y_mm: float = 0.0
    bit16: bool = False            # 16-bit TIFF output
    compression: str = "lzw"       # "lzw" | "zlib" | "none"
    export_pdf: bool = False        # also write a vector PDF next to the TIFF
    show_strip_indicators: bool = True   # draw the per-strip letter labels
    indicator_font: str = "JetBrains Mono"
    indicator_size_mm: float = 0.0       # 0 = auto (instrument text height)
    indicator_bold: bool = False
    indicator_italic: bool = False
    indicator_rotation: int = 0          # 0 | 90 | 180 | 270 degrees
    # Justification of a rotated (90°/270°) multi-letter label along its reading
    # axis: "left" (reading-start anchored — first letter stays put, label grows
    # away from the patches), "center", or "right". Ignored at 0°/180°.
    indicator_align: str = "left"
    # Nudge the strip-label band up (negative) or down (positive) within the top
    # reserve, in mm. Default 0 keeps the label where printtarg places it; a small
    # negative value tucks the labels closer to the top margin (#93).
    strip_label_offset_mm: float = 0.0
    underline_mode: str = "off"          # "off" | "colored" | "black" rule
    underline_thickness_mm: float = 0.5  # under-indicator rule thickness
    underline_gap_mm: float = 0.5        # gap between the label and the rule
    chart_text: str = ""                 # custom on-sheet text (placeholders ok)
    chart_text_font: str = "Inter"
    chart_text_size_mm: float = 0.0      # 0 = default (~3.2 mm)
    chart_text_bold: bool = False
    chart_text_italic: bool = False
    # Ruler helper markers (#152, Knut): short printed dashes along all four
    # page edges, lined up with the strips across the page and the patches down
    # it, so a ruler can be laid on the sheet accurately while measuring.
    helper_markers: bool = False
    helper_marker_edge_mm: float = 2.0   # dash distance from the paper edge
    helper_marker_len_mm: float = 2.0    # how long each dash is, pointing in
    text_edge_mm: float = 4.0            # min distance, page edge → BOTTOM sheet
    #                                      text (printer-safe inset)
    text_edge_top_mm: float = 4.0        # min distance, page edge → strip labels
    text_edge_clip_mm: float = 4.0       # min distance, page edge → clip/notes
    stamp_command: bool = False          # stamp the layout summary on the sheet
    clip_border: bool = True       # i1/p3 only — paper clip border present
    clip_border_width_mm: float = 26.0   # reserved clip-zone width (mm)
    clip_side: str = "left"        # which edge the clip / notes band sits on
    # Clip-strip content (i1/p3): "off" | "text" | "image" | "branding" | "notes".
    # Defaults to the auto-filled notes record so every clip-border chart carries
    # its own documentation strip out of the box (#93). Only drawn where a clip
    # border exists (i1/p3 clip mode); harmless elsewhere.
    clip_content_mode: str = "notes"
    clip_text: str = ""                  # rotated text / notes caption (tokens ok)
    clip_text_font: str = "Inter"
    clip_text_size_mm: float = 0.0       # 0 = auto-fit to the strip width
    clip_image_path: str = ""            # imported logo/graphic for "image" mode
    clip_image_rotation: int = 0         # degrees, clip image transform
    clip_image_scale: float = 100.0      # % of fit-to-band (100 = fit)
    clip_image_offset_x_mm: float = 0.0  # move across the band (mm)
    clip_image_offset_y_mm: float = 0.0  # move along the band (mm)
    # Flip the clip content 180° from its per-side default reading direction. A
    # right-side clip is auto-turned 180° (read from the far side of the sheet);
    # this lets the user turn any clip the other way so its text reads the same
    # direction as the bottom stamp (Knut).
    clip_flip_180: bool = False
    nolimit: bool = False
    strip_pattern: str = permutation.DEFAULT_STRIP_PATTERN
    patch_pattern: str = permutation.DEFAULT_PATCH_PATTERN

    # ---- mode / preset identity ----------------------------------------
    CM_MODES = {1: "freehand", 2: "high", 3: "extrahigh"}

    def mode(self) -> str:
        if self.instrument in ("i1", "p3"):
            return "clip" if self.clip_border else "noclip"
        if self.instrument == "CM":
            return self.CM_MODES.get(self.cm_density, "freehand")
        if self.instrument == "SS":
            return "hex" if self.hflag else "flat"
        return "default"

    def preset_key(self) -> str:
        return f"{self.instrument}|{self.paper}|{self.mode()}"

    # ---- serialisation (meta.json round-trip) --------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LayoutRecipe":
        # build_kwargs uses different keys (nolpcbord, density, margins-tuple…);
        # if those are present this is a build-kwargs dict, not a recipe dict —
        # map it back so e.g. clip_border isn't silently lost (#93).
        if isinstance(d, dict) and ("nolpcbord" in d or "draw_indicators" in d):
            return cls.from_build_kwargs(d)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def from_build_kwargs(cls, d: dict) -> "LayoutRecipe":
        """Inverse of :meth:`build_kwargs` — reconstruct a recipe from the engine
        build kwargs (so a chart whose channels.json stored kwargs, not a recipe,
        still reloads faithfully)."""
        m = d.get("margins") or (6.0, 6.0, 6.0, 6.0)
        inst = d.get("instrument", "i1")
        r = cls(
            instrument=inst, paper=d.get("paper", "A4"), dpi=int(d.get("dpi", 300)),
            randomize=bool(d.get("randomize", True)), seed=d.get("seed"),
            hflag=bool(d.get("hflag", False)), cm_density=int(d.get("density", 1)),
            cm_stagger=bool(d.get("cm_stagger", False)),
            use_instrument_margins=bool(d.get("use_instrument_margins", False)),
            spacer_mode=d.get("spacer_mode", "colored"),
            spacer_palette=list(d.get("spacer_palette") or []),
            spacer_overrides=dict(d.get("spacer_overrides") or {}),
            edge_spacers=bool(d.get("edge_spacers", False)),
            patch_area_align=d.get("patch_area_align") or "center-left",
            pscale=float(d.get("pscale", 1.0)), sscale=float(d.get("sscale", 1.0)),
            border=float(d.get("border", 6.0)),
            margin_top=m[0], margin_right=m[1], margin_bottom=m[2], margin_left=m[3],
            patch_w_mm=float(d.get("patch_w") or 0.0),
            patch_h_mm=float(d.get("patch_h") or 0.0),
            layout_mode=d.get("layout_mode") or "patch_first",
            area_method=d.get("area_method") or "by_width",
            area_cols=int(d.get("area_cols") or 0),
            area_rows=int(d.get("area_rows") or 0),
            area_ratio=float(d.get("area_ratio") or 0.0),
            area_min_patch_mm=float(d.get("area_min_patch") or 0.0),
            spacer_width_mm=float(d.get("spacer_width") or 0.0),
            inter_patch_mm=float(d.get("inter_patch") or 0.0),
            strip_gap_mm=float(d.get("strip_gap") or 0.0),
            max_strip_mm=float(d.get("max_strip") or 0.0),
            strip_indicator_gap_mm=float(d.get("strip_indicator_gap") or 0.0),
            offset_x_mm=float(d.get("offset_x", 0.0)),
            offset_y_mm=float(d.get("offset_y", 0.0)),
            bit16=bool(d.get("bit16", False)), compression=d.get("compression", "lzw"),
            export_pdf=bool(d.get("export_pdf", False)),
            show_strip_indicators=bool(d.get("draw_indicators", True)),
            indicator_font=d.get("indicator_font", "JetBrains Mono"),
            indicator_size_mm=float(d.get("indicator_size_mm") or 0.0),
            indicator_bold=bool(d.get("indicator_bold", False)),
            indicator_italic=bool(d.get("indicator_italic", False)),
            indicator_rotation=int(d.get("indicator_rotation", 0)),
            indicator_align=d.get("indicator_align", "left"),
            strip_label_offset_mm=float(d.get("strip_label_offset_mm") or 0.0),
            underline_mode=d.get("underline_mode", "off"),
            underline_thickness_mm=float(d.get("underline_thickness_mm") or 0.5),
            underline_gap_mm=float(d.get("underline_gap_mm") or 0.5),
            chart_text=d.get("chart_text", ""),
            chart_text_font=d.get("chart_text_font", "Inter"),
            chart_text_size_mm=float(d.get("chart_text_size_mm") or 0.0),
            helper_markers=bool(d.get("helper_markers", False)),
            helper_marker_edge_mm=float(d.get("helper_marker_edge") or 2.0),
            helper_marker_len_mm=float(d.get("helper_marker_len") or 2.0),
            text_edge_mm=float(d.get("text_edge") or 4.0),
            text_edge_top_mm=float(d.get("text_edge_top") or 4.0),
            text_edge_clip_mm=float(d.get("text_edge_clip") or 4.0),
            chart_text_bold=bool(d.get("chart_text_bold", False)),
            chart_text_italic=bool(d.get("chart_text_italic", False)),
            stamp_command=bool(d.get("stamp_command", False)),
            clip_border=(not bool(d.get("nolpcbord", False)))
            if inst in ("i1", "p3") else True,
            clip_border_width_mm=float(d.get("clip_border_width") or 26.0),
            clip_side=d.get("clip_side") or "left",
            clip_content_mode=d.get("clip_content_mode", "off"),
            clip_text=d.get("clip_text", ""),
            clip_text_font=d.get("clip_text_font", "Inter"),
            clip_text_size_mm=float(d.get("clip_text_size_mm") or 0.0),
            clip_image_path=d.get("clip_image_path", ""),
            clip_image_rotation=int(d.get("clip_image_rotation") or 0),
            clip_image_scale=float(d.get("clip_image_scale") or 100.0),
            clip_image_offset_x_mm=float(d.get("clip_image_offset_x") or 0.0),
            clip_image_offset_y_mm=float(d.get("clip_image_offset_y") or 0.0),
            clip_flip_180=bool(d.get("clip_flip_180", False)),
            nolimit=bool(d.get("nolimit", False)),
            strip_pattern=d.get("strip_pattern") or permutation.DEFAULT_STRIP_PATTERN,
            patch_pattern=d.get("patch_pattern") or permutation.DEFAULT_PATCH_PATTERN,
        )
        return r

    @classmethod
    def from_channels_json(cls, path) -> "LayoutRecipe | None":
        """Load the engine recipe stored in a chart's ``channels.json`` layout
        block, or ``None`` if the chart wasn't built by the ChromIQ engine.

        Lets the Edit/create-chart editor seed its panel with exactly the layout
        a chart was created with (issue #93). The build seed (if recorded) is
        carried so the layout reproduces.
        """
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        lay = data.get("layout") if isinstance(data, dict) else None
        if not isinstance(lay, dict) or lay.get("engine") != "chromiq":
            return None
        rec = lay.get("recipe")
        if not isinstance(rec, dict):
            return None
        r = cls.from_dict(rec)
        if isinstance(lay.get("seed"), int):
            r.seed = lay["seed"]
        return r

    # ---- mapping to the engine build kwargs ----------------------------
    def build_kwargs(self) -> dict:
        """Kwargs for :func:`workflow.layout_engine.chart.build_chart`."""
        return {
            "instrument": self.instrument,
            "paper": self.paper,
            "seed": self.seed,
            "randomize": self.randomize,
            "dpi": self.dpi,
            "hflag": self.hflag,
            "density": self.cm_density,
            "cm_stagger": self.cm_stagger,
            "spacer_on": self.spacer_mode != "none",
            "spacer_mode": self.spacer_mode,
            "spacer_palette": list(self.spacer_palette) or None,
            "spacer_overrides": dict(self.spacer_overrides) or None,
            # Strip readers (i1/p3/CM) always bracket each strip with a leading +
            # trailing spacer, exactly like the Guided path (chart_creator) — so
            # the instrument starts/ends a strip on a spacer, and the small gap it
            # adds between the strip label and the first patch matches Guided
            # (Sebastian: "guided has a little more space, make it the Manual
            # default too"). Other instruments honour the stored field.
            "edge_spacers": (self.edge_spacers
                             or self.instrument in ("i1", "p3", "CM")),
            "patch_area_align": self.patch_area_align,
            "pscale": self.pscale,
            "sscale": self.sscale,
            "border": self.border,
            "margins": (self.margin_top, self.margin_right,
                        self.margin_bottom, self.margin_left),
            "patch_w": self.patch_w_mm or None,
            "patch_h": self.patch_h_mm or None,
            "layout_mode": self.layout_mode,
            "area_method": self.area_method,
            "area_cols": self.area_cols,
            "area_rows": self.area_rows,
            "area_ratio": self.area_ratio,
            "area_min_patch": self.area_min_patch_mm or None,
            "spacer_width": self.spacer_width_mm or None,
            "inter_patch": self.inter_patch_mm or None,
            "strip_gap": self.strip_gap_mm or None,
            "max_strip": self.max_strip_mm or None,
            "strip_indicator_gap": self.strip_indicator_gap_mm or None,
            "offset_x": self.offset_x_mm,
            "offset_y": self.offset_y_mm,
            "bit16": self.bit16,
            "compression": self.compression,
            "export_pdf": self.export_pdf,
            "draw_indicators": self.show_strip_indicators,
            "indicator_font": self.indicator_font,
            "indicator_size_mm": self.indicator_size_mm,
            "indicator_bold": self.indicator_bold,
            "indicator_italic": self.indicator_italic,
            "indicator_rotation": self.indicator_rotation,
            "indicator_align": self.indicator_align,
            "strip_label_offset_mm": self.strip_label_offset_mm,
            "underline_mode": self.underline_mode,
            "underline_thickness_mm": self.underline_thickness_mm,
            "underline_gap_mm": self.underline_gap_mm,
            "chart_text": self.chart_text,
            "chart_text_font": self.chart_text_font,
            "chart_text_size_mm": self.chart_text_size_mm,
            "helper_markers": bool(self.helper_markers),
            "helper_marker_edge": self.helper_marker_edge_mm or 2.0,
            "helper_marker_len": self.helper_marker_len_mm or 2.0,
            "text_edge": self.text_edge_mm or 4.0,
            "text_edge_top": self.text_edge_top_mm or 4.0,
            "text_edge_clip": self.text_edge_clip_mm or 4.0,
            # Drives "margins are the law" mode in the engine (Knut): only when on
            # are the margins exact (no leader/trailer). Off = printtarg-style.
            "use_instrument_margins": self.use_instrument_margins,
            "chart_text_bold": self.chart_text_bold,
            "chart_text_italic": self.chart_text_italic,
            "stamp_command": self.stamp_command,
            "nolpcbord": (not self.clip_border) if self.instrument in ("i1", "p3") else False,
            "clip_border_width": self.clip_border_width_mm or 26.0,
            "clip_side": self.clip_side or "left",
            "clip_content_mode": self.clip_content_mode,
            "clip_text": self.clip_text,
            "clip_text_font": self.clip_text_font,
            "clip_text_size_mm": self.clip_text_size_mm,
            "clip_image_path": self.clip_image_path,
            "clip_image_rotation": self.clip_image_rotation,
            "clip_image_scale": self.clip_image_scale or 100.0,
            "clip_image_offset_x": self.clip_image_offset_x_mm,
            "clip_image_offset_y": self.clip_image_offset_y_mm,
            "clip_flip_180": self.clip_flip_180,
            "nolimit": self.nolimit,
            "strip_pattern": self.strip_pattern,
            "patch_pattern": self.patch_pattern,
        }


def default_recipe(instrument: str = "i1", paper: str = "A4", *, mode: str | None = None
                   ) -> LayoutRecipe:
    """A sensible default recipe for *instrument*/*paper* (and optional *mode*)."""
    r = LayoutRecipe(instrument=instrument, paper=paper)
    # The SpectroScan is a flatbed XY-table: it reads a FIXED 2-D grid, so
    # "prioritise patch size, then fit to page" (patch_first) is its natural
    # layout — it gives the proper grid of hexagons/squares. The generic
    # area_first default with the "By minimum width" method collapses a flatbed
    # into a single full-width column of thin bands (there is no fixed aperture
    # to stop it), so patch_first is the right default here. area_first + "By
    # columns/rows" stays fully available for users who want an explicit grid.
    if instrument == "SS":
        r.layout_mode = "patch_first"
    # ColorMunki / SpectroScan have no physical clip; the notes band is opt-in, so
    # it defaults OFF for every mode (Sebastian). i1/p3 keep "notes" so that when
    # their clip border is on it carries the record strip.
    if instrument in ("CM", "SS"):
        r.clip_content_mode = "off"
    if mode is not None:
        if instrument in ("i1", "p3"):
            r.clip_border = (mode == "clip")
        elif instrument == "CM":
            r.cm_density = {"freehand": 1, "high": 2, "extrahigh": 3}.get(mode, 1)
            if mode == "extrahigh":
                # Match Guided's triple-density defaults exactly (Sebastian): the
                # engine-native dense ColorMunki strip uses 5 mm margins + border,
                # clip off, and the centred patch block (the extra gap below the
                # strip labels).
                r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 5.0
                r.border = 5.0
                r.patch_area_align = "center-left"
        elif instrument == "SS":
            r.hflag = (mode == "hex")
    return r


class PresetStore:
    """A keyed collection of :class:`LayoutRecipe` presets (JSON-backed)."""

    VERSION = 1

    def __init__(self, presets: dict[str, LayoutRecipe] | None = None):
        self._presets: dict[str, LayoutRecipe] = dict(presets or {})

    # ---- access --------------------------------------------------------
    def has(self, instrument: str, paper: str, mode: str) -> bool:
        """True when a user preset exists for this combo (vs a fresh default).
        Lets callers seed app-wide defaults (e.g. strip-indicator styling) only
        for fresh charts, leaving stored presets to carry their own."""
        return f"{instrument}|{paper}|{mode}" in self._presets

    def get(self, instrument: str, paper: str, mode: str) -> LayoutRecipe:
        key = f"{instrument}|{paper}|{mode}"
        if key in self._presets:
            return replace(self._presets[key])      # a copy
        return default_recipe(instrument, paper, mode=mode)

    def set(self, recipe: LayoutRecipe) -> None:
        # Presets store layout, not the per-chart seed.
        self._presets[recipe.preset_key()] = replace(recipe, seed=None)

    def delete(self, instrument: str, paper: str, mode: str) -> bool:
        return self._presets.pop(f"{instrument}|{paper}|{mode}", None) is not None

    def keys(self) -> list[str]:
        return sorted(self._presets)

    # ---- (de)serialisation ---------------------------------------------
    def to_dict(self) -> dict:
        return {"version": self.VERSION,
                "presets": {k: v.to_dict() for k, v in self._presets.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "PresetStore":
        raw = d.get("presets", {}) if isinstance(d, dict) else {}
        return cls({k: LayoutRecipe.from_dict(v) for k, v in raw.items()})

    # ---- bridge to core.preset_store's {name: data} file layout -------
    def as_named_dict(self) -> dict[str, dict]:
        """``{preset_key: recipe_dict}`` — one entry per user-browsable file."""
        return {k: v.to_dict() for k, v in self._presets.items()}

    @classmethod
    def from_named_dict(cls, d: dict[str, dict]) -> "PresetStore":
        return cls({k: LayoutRecipe.from_dict(v) for k, v in d.items()})

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "PresetStore":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    # export / import are just save / load to a user-chosen path
    export = save
    load_import = load

    @classmethod
    def factory_defaults(cls) -> "PresetStore":
        """The presets the app ships with — one default per instrument/mode."""
        presets: dict[str, LayoutRecipe] = {}
        for inst in SUPPORTED_INSTRUMENTS:
            modes = (["clip", "noclip"] if inst in ("i1", "p3")
                     else ["freehand", "high", "extrahigh"] if inst == "CM"
                     else ["flat", "hex"] if inst == "SS"
                     else ["default"])
            for m in modes:
                r = default_recipe(inst, "A4", mode=m)
                presets[r.preset_key()] = r
        return cls(presets)
