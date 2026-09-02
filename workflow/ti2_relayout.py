"""TI2 layout editor — headless core.

Takes any ArgyllCMS ``.ti2``, lets the caller reorder its patches and recolor
the inter-patch spacers, and emits a *new* ``.ti2`` + page TIFF(s) that are
valid measurement targets.

Design (validated 2026-05-28 — see memory project_ti2_layout_editor):

  * Reorder is realised by writing a fresh ``.ti1`` in the chosen order and
    running ``printtarg -r`` (don't randomise), so printtarg — the authority on
    layout — regenerates a mutually consistent ``.ti2`` + ``.tif``. Device
    values are copied verbatim; we never hand-edit the patch raster.
  * Spacers are located by a render diff: the same ``.ti1`` rendered with
    default (coloured) spacers vs ``-b`` (B&W) is pixel-identical *except* at
    the spacers (``-b`` does not change geometry). The differing pixels are the
    spacer mask — no coordinate math, no ``.cht`` transform. Both renders use
    the *same basename in separate temp dirs* so the stamped chart label can't
    pollute the mask.
  * Recolouring writes only masked pixels; patch interiors stay byte-identical,
    so measured patch values are provably unaffected.

This module is Qt-free and unit-testable. The popup UI lives in ui/dialogs.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections import deque
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

import numpy as np

from core.logger import get_logger
from core.strip_utils import letter_to_idx, parse_passes_per_page
from core.text_io import read_text

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Instrument / paper reverse maps  (CGATS keyword -> printtarg flag value)
# ---------------------------------------------------------------------------
# Mirror of ui.ti2_loader.KNOWN_INSTRUMENTS, kept local so workflow/ doesn't
# import the ui layer. printtarg -i accepts: 20|22|41|51|SS|i1|3p|CM.
def instrument_to_flag(target_instrument: str | None) -> str:
    name = (target_instrument or "").lower()
    # The CR30 is checked FIRST and is not a printtarg code at all (#159):
    # printtarg has no -iCR30 and never lays this chart out. It is returned so
    # a CR30 chart relayouts as a CR30 rather than silently falling through to
    # the i1Pro default below, which would re-lay a hand-placed grid as a strip
    # chart. chart_creator forces the layout engine for this key.
    if "cr30" in name:
        return "CR30"
    if "colormunki" in name:
        return "CM"
    if "spectroscan" in name:
        return "SS"
    if "i1 pro" in name or "i1pro" in name:
        # i1Pro 3 Plus has its own (larger-aperture) strip layout. printtarg
        # itself stamps both the i1Pro family and the 3 Plus as "i1Pro3", so a
        # plain printtarg-made chart can't be told apart here — but honour an
        # explicit "Plus" / "3+" marker when one is present (forward-compat).
        if "plus" in name or "3+" in name:
            return "3p"
        return "i1"
    return "i1"  # safe default: i1Pro strip layout reads the widest range


# printtarg -p named sizes (mm, width x height incl. orientation).
# Mirrors the dropdown in the Create Chart tab (data.patch_db.PAPER_LABELS).
_NAMED_PAPERS: dict[tuple[float, float], str] = {
    (420.0, 594.0): "A2",       (594.0, 420.0): "594x420",
    (329.0, 483.0): "329x483",  (483.0, 329.0): "483x329",   # A3+
    (297.0, 420.0): "A3",       (420.0, 297.0): "420x297",
    (279.4, 431.8): "11x17",
    (215.9, 355.6): "Legal",
    (210.0, 297.0): "A4",       (297.0, 210.0): "A4R",
    (215.9, 279.4): "Letter",   (279.4, 215.9): "LetterR",
    (203.0, 254.0): "203x254",
    (127.0, 178.0): "127x178",
    (101.6, 152.4): "4x6",
}


def paper_to_flag(w_mm: float, h_mm: float) -> str:
    """Map a PAPER_SIZE (mm) to a printtarg ``-p`` value.

    Falls back to printtarg's custom ``WWWxHHH`` form for unrecognised sizes.
    """
    for (w, h), name in _NAMED_PAPERS.items():
        if abs(w - w_mm) < 0.6 and abs(h - h_mm) < 0.6:
            return name
    return f"{w_mm:g}x{h_mm:g}"


# ---------------------------------------------------------------------------
# Parsed chart
# ---------------------------------------------------------------------------
@dataclass
class Patch:
    sample_id: str
    loc: str | None                       # SAMPLE_LOC, e.g. "A1" (None if absent)
    dev: tuple[float, ...]                # device values in dev_fields order
    xyz: tuple[float, float, float] | None


@dataclass
class ChartSpec:
    patches: list[Patch]
    dev_fields: list[str]                 # e.g. ["RGB_R","RGB_G","RGB_B"]
    has_xyz: bool
    color_rep: str                        # e.g. "iRGB"
    white_point: str | None               # raw APPROX_WHITE_POINT triplet
    instrument_flag: str                  # printtarg -i value, e.g. "i1"
    paper_flag: str                       # printtarg -p value, e.g. "A4"
    paper_mm: tuple[float, float]
    # Spacer palette read from the sibling .ti1's DENSITY_EXTREME_VALUES table.
    # Populated only when loading a chart whose .ti1 is alongside the .ti2 —
    # restores the original spacer palette on load so the preview matches the
    # source chart instead of resetting to printtarg's defaults.
    density_extremes: tuple[tuple[float, float, float], ...] | None = None
    # TOTAL_INK_LIMIT (percent) for multi-ink charts (#72): read back from the
    # .ti2 on load, stamped into re-saved .ti1s, threaded to targen -l /
    # colprof -l. None = no limit recorded (all RGB charts).
    ink_limit: float | None = None

    @property
    def n_channels(self) -> int:
        return len(self.dev_fields)

    # -- parsing -----------------------------------------------------------
    @classmethod
    def from_ti2(cls, path: Path) -> "ChartSpec":
        text = Path(path).read_text(encoding="utf-8", errors="ignore")

        def _kw(key: str) -> str | None:
            m = re.search(rf'^\s*{key}\s+"?([^"\n]*)"?\s*$', text, re.MULTILINE)
            return m.group(1).strip() if m else None

        color_rep = _kw("COLOR_REP") or "iRGB"
        white_point = _kw("APPROX_WHITE_POINT")
        instrument = _kw("TARGET_INSTRUMENT")

        paper = _kw("PAPER_SIZE") or "210.0x297.0"
        mp = re.match(r"\s*([\d.]+)\s*x\s*([\d.]+)", paper)
        paper_mm = (float(mp.group(1)), float(mp.group(2))) if mp else (210.0, 297.0)

        # DATA_FORMAT: field names between BEGIN/END (may span lines).
        fm = re.search(r"BEGIN_DATA_FORMAT(.*?)END_DATA_FORMAT", text, re.DOTALL)
        if not fm:
            raise ValueError(f"{path}: no BEGIN_DATA_FORMAT block")
        fields = fm.group(1).split()

        # Device fields are the colour-rep channels, identified by the
        # COLOR_REP token (e.g. iRGB -> RGB_*, CMYK -> CMYK_*).
        rep = color_rep.lstrip("i")  # iRGB -> RGB
        dev_fields = [f for f in fields if f.startswith(rep + "_")]
        if not dev_fields:
            # Fallback: anything that looks like a device channel, not XYZ/Lab.
            dev_fields = [f for f in fields
                          if "_" in f and not f.startswith(("XYZ", "LAB", "SPEC"))
                          and f not in ("SAMPLE_ID", "SAMPLE_LOC", "SAMPLE_NAME")]
        has_xyz = all(c in fields for c in ("XYZ_X", "XYZ_Y", "XYZ_Z"))

        idx = {name: i for i, name in enumerate(fields)}
        loc_i = idx.get("SAMPLE_LOC")
        id_i = idx.get("SAMPLE_ID", 0)
        dev_i = [idx[f] for f in dev_fields]
        xyz_i = [idx[c] for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")] if has_xyz else []

        dm = re.search(r"BEGIN_DATA(?!_FORMAT)(.*?)END_DATA", text, re.DOTALL)
        if not dm:
            raise ValueError(f"{path}: no BEGIN_DATA block")

        patches: list[Patch] = []
        for line in dm.group(1).splitlines():
            toks = _split_cgats(line)
            if len(toks) < len(fields):
                continue
            patches.append(Patch(
                sample_id=toks[id_i],
                loc=toks[loc_i].strip('"') if loc_i is not None else None,
                dev=tuple(float(toks[i]) for i in dev_i),
                xyz=tuple(float(toks[i]) for i in xyz_i) if has_xyz else None,
            ))
        if not patches:
            raise ValueError(f"{path}: no data rows parsed")
        # Sort patches into their visual order (top-to-bottom of strip A,
        # then strip B, …) so the editor's grid matches the printed chart's
        # layout. The .ti2's SAMPLE_ID order is the order printtarg wrote
        # rows in — for randomised charts (no `-r`) that's spatially
        # arbitrary. SAMPLE_LOC carries the spatial truth, so we sort by it
        # whenever it's populated.
        if any(p.loc for p in patches):
            patches.sort(key=_loc_sort_key)

        limit_s = _kw("TOTAL_INK_LIMIT")
        try:
            ink_limit = float(limit_s) if limit_s else None
        except ValueError:
            ink_limit = None

        return cls(
            patches=patches, dev_fields=dev_fields, has_xyz=has_xyz,
            color_rep=color_rep, white_point=white_point,
            instrument_flag=instrument_to_flag(instrument),
            paper_flag=paper_to_flag(*paper_mm), paper_mm=paper_mm,
            density_extremes=_read_sibling_density_extremes(Path(path)),
            ink_limit=ink_limit,
        )

    # -- from scratch ------------------------------------------------------
    @classmethod
    def new(
        cls,
        instrument_flag: str = "i1",
        paper_flag: str = "A4",
        *,
        device_type: str = "2",
        extra_inks: tuple[str, ...] | list[str] = (),
    ) -> "ChartSpec":
        """An empty chart spec for building a layout from scratch.

        Same downstream path as a parsed chart — the caller supplies the patch
        list via :func:`default_program`-style edits (add patches, set colours),
        then regenerates. instrument/paper are chosen by the user rather than
        read from a source file.

        ``device_type`` is the targen ``-d`` value as a string (the Manual
        tab's ``ChartParams.device_type`` convention); ``extra_inks`` are
        additional ink codes (targen ``-D``, e.g. ``("o", "g")``) using the
        same codes as :func:`ui.tiff_preview.resolve_ink_channels`. The
        default ``"2"`` (Print RGB) — and its Video-RGB twin ``"3"`` — build
        the exact spec this method always built; anything else derives the
        canonical Argyll ``COLOR_REP``/device fields via
        :func:`color_rep_for_inks` (#72).
        """
        inv = {v: k for k, v in _NAMED_PAPERS.items()}
        dt = str(device_type)
        if dt in ("2", "3") and not extra_inks:
            from workflow.i1profiler_import import WHITE_XYZ
            dev_fields, color_rep = ["RGB_R", "RGB_G", "RGB_B"], "iRGB"
            white_point = " ".join(f"{v:.6f}" for v in WHITE_XYZ)
        elif dt in ("0", "1") and not extra_inks:
            # targen -d0 (print grey) -> COLOR_REP "K" / GRAY_K;
            # -d1 (video grey) -> "W" / GRAY_W (verified, ArgyllCMS 3.5.0).
            color_rep = "K" if dt == "0" else "W"
            dev_fields = ["GRAY_K" if dt == "0" else "GRAY_W"]
            wx, wy, wz = _WHITE_XYZ_D50
            white_point = f"{wx:.6f} {wy:.6f} {wz:.6f}"
        else:
            from ui.tiff_preview import resolve_ink_channels
            codes = list(resolve_ink_channels(dt))
            codes += [c for c in extra_inks if c not in codes]
            color_rep, dev_fields = color_rep_for_inks(codes)
            wx, wy, wz = _WHITE_XYZ_D50
            white_point = f"{wx:.6f} {wy:.6f} {wz:.6f}"
        return cls(
            patches=[], dev_fields=dev_fields, has_xyz=True,
            color_rep=color_rep, white_point=white_point,
            instrument_flag=instrument_flag, paper_flag=paper_flag,
            paper_mm=inv.get(paper_flag, (210.0, 297.0)),
        )


def _split_cgats(line: str) -> list[str]:
    """Split a CGATS data row, honouring double-quoted tokens."""
    return re.findall(r'"[^"]*"|\S+', line.strip())


_LOC_RE = re.compile(r"^([A-Z]+)(\d+)$")


def _loc_sort_key(p: "Patch") -> tuple[int, int]:
    """Sort key turning a SAMPLE_LOC ("A12") into (strip-index, step) for
    visual ordering. Patches with no/unparseable LOC sort last."""
    loc = (p.loc or "").upper().strip()
    m = _LOC_RE.match(loc)
    if not m:
        return (10**9, 10**9)
    return (letter_to_idx(m.group(1)), int(m.group(2)))


def _read_sibling_density_extremes(
    ti2_path: Path,
) -> tuple[tuple[float, float, float], ...] | None:
    """Pull DENSITY_EXTREME_VALUES from the .ti1 next to a .ti2 (if present).

    printtarg always writes the .ti1 + .ti2 as a pair with matching stems. The
    .ti1's second CGATS table carries the spacer-colour palette the chart was
    rendered with, so reading it back on load lets the editor restore the
    original palette instead of resetting to printtarg's defaults. Returns
    None when no sibling .ti1 exists or the table is missing/malformed.
    """
    ti1 = ti2_path.with_suffix(".ti1")
    if not ti1.is_file():
        return None
    try:
        text = ti1.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    # Split into per-table sections by CTI1 marker so we read the 2nd table
    # only. The first table is the patch list; the second is the extremes.
    sections = re.split(r"^CTI1\s*$", text, flags=re.MULTILINE)
    # sections[0] is the file header; sections[1..] are the tables.
    extreme_section = None
    for s in sections[1:]:
        if "DENSITY_EXTREME_VALUES" in s:
            extreme_section = s
            break
    if extreme_section is None:
        return None
    fm = re.search(r"BEGIN_DATA_FORMAT(.*?)END_DATA_FORMAT", extreme_section, re.DOTALL)
    dm = re.search(r"BEGIN_DATA(?!_FORMAT)(.*?)END_DATA", extreme_section, re.DOTALL)
    if not fm or not dm:
        return None
    fields = fm.group(1).split()
    try:
        ri, gi, bi = fields.index("RGB_R"), fields.index("RGB_G"), fields.index("RGB_B")
    except ValueError:
        return None
    out: list[tuple[float, float, float]] = []
    for line in dm.group(1).splitlines():
        toks = _split_cgats(line)
        if len(toks) <= max(ri, gi, bi):
            continue
        try:
            out.append((float(toks[ri]), float(toks[gi]), float(toks[bi])))
        except ValueError:
            continue
    return tuple(out) if out else None


# ---------------------------------------------------------------------------
# .ti1 synthesis
# ---------------------------------------------------------------------------
# Printtarg layout knobs the editor exposes per chart.
@dataclass
class LayoutOptions:
    spacer_mode: str = "colored"        # "colored" | "bw" | "none"
    patch_scale: float = 1.0            # -a
    spacer_scale: float = 1.0           # -A
    margin_mm: int = 6                  # -m + -M (printtarg's default is 6 mm)
    suppress_left_clip: bool = False    # -L
    no_strip_limit: bool = False        # -P
    double_density: bool = False        # -h (ColorMunki double / SpectroScan hex)
    # ChromIQ-internal: rewrites -i to "i1" + applies the preset values, then
    # patches the produced .ti2's TARGET_INSTRUMENT back to ColorMunki. Mutually
    # exclusive with double_density. Mirrors tab_chart's triple-density preset
    # (see workflow/chart_creator.py's triple_density rewrite logic).
    triple_density: bool = False
    tiff_16bit: bool = False            # -T (vs -t) DPI flag
    dpi: int = 300                      # printtarg -t / -T value

    def __post_init__(self) -> None:
        # The -a / -A spinboxes step by 0.05, so values are 2-decimal by
        # intent; binary-float arithmetic (e.g. 1.3 → 1.2999999999999998) would
        # otherwise leak that noise into the saved meta.json. Round to 2 dp so
        # the stored knobs read cleanly and compare equal across save/load.
        self.patch_scale = round(float(self.patch_scale), 2)
        self.spacer_scale = round(float(self.spacer_scale), 2)

    def to_printtarg_args(self) -> list[str]:
        """Build the printtarg flag list this options bundle implies."""
        args: list[str] = []
        if self.spacer_mode == "bw":
            args.append("-b")
        elif self.spacer_mode == "none":
            args.append("-n")
        if abs(self.patch_scale - 1.0) > 0.01:
            args.append(f"-a{self.patch_scale:.2f}")
        if abs(self.spacer_scale - 1.0) > 0.01:
            args.append(f"-A{self.spacer_scale:.2f}")
        if self.margin_mm != 6:
            # -m sets the inter-strip margin, -M sets the outer page margin.
            # Both default to 6 mm in printtarg; ChromIQ's Create Chart tab
            # ties them together (see ui/tabs/tab_chart.py manual mode), so
            # we do the same here.
            args.append(f"-m{self.margin_mm}")
            args.append(f"-M{self.margin_mm}")
        if self.suppress_left_clip:
            args.append("-L")
        if self.no_strip_limit:
            args.append("-P")
        if self.double_density:
            args.append("-h")
        return args


# ---------------------------------------------------------------------------
# Editor meta.json — restore-as-saved
# ---------------------------------------------------------------------------
# The .ti2 records instrument + paper + spacer palette, but printtarg discards
# the rest of its layout knobs (-a/-A/-m/-t/bit-depth/spacer mode/-L/-P/-h) once
# the chart is rendered. So when the editor saves a chart it writes the same
# ``meta.json`` the main app writes for a run (RunMeta) into the chart folder,
# carrying instrument / paper / created_at / status PLUS the editor's
# LayoutOptions + basename under RunMeta.editor_layout / editor_basename.
# Reopening that chart reads meta.json back so the printtarg panel appears
# exactly as the user left it; the folder also reads like a main-app chart
# folder. Charts from elsewhere have no meta.json and fall back to defaults +
# whatever the .ti2 / .ti1 themselves reveal.


def _layout_from_dict(raw: dict | None) -> "LayoutOptions":
    """Build a LayoutOptions from a (possibly partial / future) dict, dropping
    unknown keys so a meta.json written by a newer schema still loads what it
    can instead of failing."""
    raw = raw or {}
    valid = {f.name for f in fields(LayoutOptions)}
    return LayoutOptions(**{k: v for k, v in raw.items() if k in valid})


def recipe_layout_from_options(options: "LayoutOptions") -> dict:
    """The Set-B ``layout`` block that corresponds to a Set-A ``LayoutOptions``.

    Single source of truth for keeping a chart's creation recipe (Set B) in step
    with the printtarg layout it was actually built with (Set A), so the two
    records can never disagree on scale / margin / density / etc. (#92). Mirrors
    the block ``_collect_gen_state`` writes in the editor."""
    return {
        "spacer_mode": options.spacer_mode,
        "patch_scale": options.patch_scale,
        "spacer_scale": options.spacer_scale,
        "margin": options.margin_mm,
        "dpi": options.dpi,
        "bit16": options.tiff_16bit,
        "L": options.suppress_left_clip,
        "P": options.no_strip_limit,
        "h": options.double_density,
        "td": options.triple_density,
    }


#: "This chart has no design", as distinct from "leave the record alone".
#:
#: `recipe=None` means a layout-only save, which must not wipe a chart's
#: creation recipe. But a REBUILD from a different patch set was passing None
#: too, so the run went on describing the chart it used to hold — and the false
#: record then travelled: into meta.json, into the preset saved from it, and
#: into "Load setup from preset" as the basis for the next design. Knut hit it
#: and knew it was wrong before we did: *"why did not the setup data update…
#: This should have been saved, but was not. Then the error was further
#: propagated when I used the chart to create another variant."* (#164)
#:
#: Pass this when the chart on disk was NOT built from a stored design, and the
#: record is cleared instead of inherited.
NO_RECIPE: dict = {}


def save_editor_meta(ti2_path: Path, spec: "ChartSpec",
                     options: "LayoutOptions", basename: str,
                     recipe: dict | None = None,
                     sync_layout: bool = True) -> None:
    """Write a main-app-style ``meta.json`` into the chart folder (next to
    *ti2_path*), carrying the editor's layout knobs so reopening restores the
    panel. Best-effort: a failure here must never block a successful chart
    save, so errors are swallowed.

    ``recipe`` is the New chart / Add window's creation recipe
    (``_collect_gen_state``); when given it's stored as ``editor_recipe`` so the
    design can be reloaded for tweaking/recreation. It has THREE states, and the
    third one exists because conflating it with the second corrupted real user
    data:

    * a dict — this is the design the chart was built from; store it;
    * ``None`` — don't touch the record (a layout-only save mustn't wipe it);
    * :data:`NO_RECIPE` — this chart was NOT built from a stored design, so
      clear the record rather than let the previous chart's design stand as a
      description of this one.

    ``sync_layout=False`` stores the recipe exactly as given. Used for charts
    the ChromIQ layout engine built: their real layout lives in the recipe in
    ``channels.json``, and *options* only mirrors printtarg widgets that didn't
    produce the chart — syncing from those would stamp unrelated values into
    the recipe (#100)."""
    from core.file_manager import Run, RunMeta
    try:
        run = Run.for_dir(Path(ti2_path).parent)
        meta = run.load_meta()              # preserve any existing fields
        meta.instrument = spec.instrument_flag
        meta.paper = spec.paper_flag
        if not meta.created_at:
            from datetime import datetime
            meta.created_at = datetime.now().isoformat(timespec="seconds")
        meta.editor_layout = asdict(options)
        meta.editor_basename = basename
        if recipe is not None and not recipe:
            meta.editor_recipe = None          # NO_RECIPE — see the docstring
        elif recipe is not None:
            # Keep the creation recipe's layout (Set B) in step with the layout
            # the chart was actually built with (Set A = options), so a chart's
            # two records never disagree (#92). Generators / colour-set params /
            # mode / patch count stay frozen — only the layout block (+ the
            # instrument / paper identity) syncs. Engine-built charts skip the
            # sync (see the docstring).
            synced = dict(recipe)
            if sync_layout:
                synced["layout"] = recipe_layout_from_options(options)
                synced["instr"] = spec.instrument_flag
                synced["paper"] = spec.paper_flag
            meta.editor_recipe = synced
        run.save_meta(meta)
    except Exception:  # noqa: BLE001 — sidecar write must never be fatal
        log.exception("could not write editor meta.json")


def load_editor_recipe(ti2_path: Path) -> dict | None:
    """Read the New chart / Add creation recipe back from the chart folder's
    ``meta.json`` (``editor_recipe``), or ``None`` when absent."""
    from core.file_manager import Run
    try:
        meta = Run.for_dir(Path(ti2_path).parent).load_meta()
    except Exception:  # noqa: BLE001
        return None
    return meta.editor_recipe if isinstance(meta.editor_recipe, dict) else None


def load_editor_meta(ti2_path: Path) -> tuple["LayoutOptions", str] | None:
    """Read the editor's layout knobs + basename back from the chart folder's
    ``meta.json``, or None when there's no meta.json or it carries no editor
    layout (e.g. a foreign chart, or a main-app run that never went through the
    editor). Returns ``(options, basename)``."""
    from core.file_manager import Run
    try:
        meta = Run.for_dir(Path(ti2_path).parent).load_meta()
    except Exception:  # noqa: BLE001
        return None
    if meta.editor_layout is None:
        return None
    opts = _layout_from_dict(meta.editor_layout)
    basename = meta.editor_basename or Path(ti2_path).stem or "chart"
    return opts, basename


_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_color_values(text: str) -> list[tuple[float, float, float]]:
    """Parse user-pasted colour values into a list of 0..100 RGB tuples.

    Accepts one colour per line in any of:
        #RRGGBB  or  RRGGBB        — hex 0..255 per channel
        R, G, B  or  R G B         — decimal; scale auto-detected (0..1 /
                                     0..100 / 0..255 / 0..65535) from the
                                     peak value across the input.

    Lines that don't look like a colour are skipped silently, so '#' comments
    or blank lines in pasted files are tolerated. Returns an empty list when
    nothing parseable was found.
    """
    triples: list[tuple[float, float, float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _HEX_RE.match(line)
        if m:
            h = m.group(1)
            triples.append((float(int(h[0:2], 16)),
                            float(int(h[2:4], 16)),
                            float(int(h[4:6], 16))))
            continue
        parts = re.split(r"[,;\s]+", line)
        if len(parts) >= 3:
            try:
                triples.append((float(parts[0]), float(parts[1]), float(parts[2])))
            except ValueError:
                pass
    if not triples:
        return []
    peak = max(max(t) for t in triples)
    if peak <= 1.5:
        f = 100.0
    elif peak <= 100.0:
        f = 1.0
    elif peak <= 255.0:
        f = 100.0 / 255.0
    else:
        f = 100.0 / 65535.0
    return [(r * f, g * f, b * f) for r, g, b in triples]


def default_program(spec: ChartSpec) -> list[tuple[float, ...]]:
    """The chart's current patches as an editable ordered device-value list.

    This is the unit the editor mutates: reordering permutes it, recolouring a
    patch replaces an entry, add/remove changes its length. Feed the result to
    :func:`write_ti1` / :func:`regenerate`.
    """
    return [p.dev for p in spec.patches]


# Patch files the editor can combine into the current chart. Dispatched on
# content where it matters (a CxF saved as .cgats still reads), so this set is
# a hint for the file-open filter, not a hard gate.
LOADABLE_PATCH_SUFFIXES = (
    ".ti2", ".ti1", ".ti3", ".cgats", ".txt", ".pxf", ".pwxf",
)


def load_rgb_program(path: Path) -> list[tuple[float, float, float]]:
    """Load any supported RGB patch file into a 0..100 RGB program.

    Used by the editor's "combine sets" feature: parse a second file's patches
    into the same flat list of device tuples the editor mutates, ready to splice
    onto the front or back of the current program.

    Supported sources:

    * ``.ti2`` — a full Argyll chart (read via :meth:`ChartSpec.from_ti2`, so
      its patches come back in visual / strip order).
    * ``.ti1`` / ``.ti3`` / ``.cgats`` / ``.txt`` — any CGATS table with
      ``RGB_R/RGB_G/RGB_B`` (or bare ``R/G/B``) columns.
    * ``.pxf`` / ``.pwxf`` — X-Rite i1Profiler CxF3 patch / workflow files.

    RGB only, matching the rest of the editor — a CMYK / extended-gamut source
    raises :class:`ValueError` with a readable message. The CGATS/CxF parsers
    auto-detect 0..1 / 0..100 / 0..255 scaling. Raises ``ValueError`` (or the
    parser's own error) when nothing usable is found.
    """
    path = Path(path)
    if path.suffix.lower() == ".ti2":
        spec = ChartSpec.from_ti2(path)
        rep = spec.color_rep.lstrip("i").upper()
        if rep != "RGB":
            raise ValueError(
                f"{path.name}: chart is {spec.color_rep!r}, not RGB — the "
                "layout editor combines RGB patch sets only."
            )
        return [tuple(p.dev[:3]) for p in spec.patches]

    # CGATS tables and CxF/XML both flow through i1profiler_import's parsers,
    # which already return RGB on the 0..100 scale and reject non-RGB sources.
    from workflow.i1profiler_import import (
        _looks_like_xml, parse_cgats, parse_pxf,
    )
    if path.suffix.lower() in (".pxf", ".pwxf") or _looks_like_xml(path):
        patches = parse_pxf(path)
    else:
        patches = parse_cgats(path)
    return [(p.r, p.g, p.b) for p in patches]


def load_colour_file(path: Path) -> list[tuple[float, float, float]]:
    """Load a **device-RGB** colour file into a 0..100 RGB program.

    Accepts device-RGB CGATS / CxF (ti1 / ti2 / ti3 / cgats / txt / pxf, via
    :func:`load_rgb_program`) and a plain hex / RGB value list. Raises
    ``ValueError`` if nothing usable is found. CIE reference files (XYZ / LAB
    only, no device values) are **not** supported — for full-cube coverage use
    the colour-set generators instead (#96).
    """
    path = Path(path)
    try:
        prog = load_rgb_program(path)
        if prog:
            return prog
    except ValueError:
        # A .ti2 is never a plain hex/RGB list, so falling through would only
        # bury the informative error (e.g. "chart is CMYK, not RGB" — #72 R6)
        # under a generic "no usable colour values found".
        if path.suffix.lower() == ".ti2":
            raise
    except Exception:  # noqa: BLE001 — fall through to the plain value list
        pass
    text = read_text(path, lenient=True)
    vals = parse_color_values(text)
    if vals:
        return vals
    if re.search(r"\b(XYZ_X|LAB_L)\b", text):
        raise ValueError(
            f"{path.name}: this is a CIE reference file (XYZ / LAB only), which "
            "isn't supported. Load a device-RGB chart (.ti1 / .ti2 / .ti3 / "
            "CGATS) or a hex / RGB list instead.")
    raise ValueError(f"{path.name}: no usable colour values found.")


def seed_from_targen(
    bin_dir: Path,
    n_patches: int,
    *,
    device: str = "2",
    grey_steps: int = 0,
    good_mode: bool = True,
    extra_args: list[str] | None = None,
) -> list[tuple[float, ...]]:
    """Generate an optimised patch set via targen, returned as a program.

    The "seed from targen" path for new-from-scratch mode: targen spreads
    patches well across the gamut (OFPS), giving a good base the user can then
    drag-arrange and recolour. Blank-canvas mode just skips this (empty program).

    Channel-generic since #72: ``device`` is any targen ``-d`` value (plus
    ``-D`` colorants via ``extra_args``) and the returned tuples carry however
    many channels targen emitted — 3-tuples for the RGB default, N-tuples for
    multi-ink device types.
    """
    targen = Path(bin_dir) / "targen"
    args = [f"-d{device}", f"-f{n_patches}"]
    if good_mode:
        args.append("-G")
    if grey_steps > 0:
        args.append(f"-g{grey_steps}")
    args += (extra_args or [])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        r = subprocess.run([str(targen), *args, "seed"], cwd=str(work),
                           capture_output=True, text=True, timeout=120,
                           stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"targen failed ({r.returncode}): {r.stderr.strip()}")
        from workflow.layout_engine.ti1_reader import read_ti1 as _read_ti1
        return [dev for dev, _xyz in _read_ti1(work / "seed.ti1").patches]


# Canonical Argyll colorant order and COLOR_REP letters (#72 hard problem 10).
# Order = the inkmask bit order in Argyll xicc/xcolorants.h (ICX_CYAN 0x1 …
# ICX_LIGHT_LIGHT_BLACK 0x1000000); letters = the ICX_C_* strings. Both were
# additionally verified against real `targen -d…/-D…` runs (ArgyllCMS 3.5.0):
# targen canonicalises user-supplied -D order into this bit order, so deriving
# COLOR_REP this way matches what every downstream Argyll tool expects.
# Ink codes follow ui.tiff_preview's convention (resolve_ink_channels).
_INK_BIT_ORDER: tuple[str, ...] = (
    "c", "m", "y", "k", "o", "r", "g", "b", "v", "w",
    "lc", "lm", "ly", "lk", "mc", "mm", "my", "mk", "llk",
)
_INK_REP_LETTER: dict[str, str] = {
    "c": "C", "m": "M", "y": "Y", "k": "K", "o": "O", "r": "R", "g": "G",
    "b": "B", "v": "V", "w": "W",
    "lc": "c", "lm": "m", "ly": "y", "lk": "k",
    "mc": "2c", "mm": "2m", "my": "2y", "mk": "2k",
    "llk": "1k",
}


def color_rep_for_inks(ink_codes: list[str] | tuple[str, ...]) -> tuple[str, list[str]]:
    """Derive the canonical ``(COLOR_REP, dev_fields)`` for a set of ink codes.

    ``ink_codes`` uses ChromIQ's ink-code convention (``"c" "m" "y" "k" "o"
    "lc" …``, see ``ui.tiff_preview``); order and duplicates are irrelevant —
    the result is always in Argyll's canonical colorant order, exactly as a
    ``targen -d…/-D…`` run would stamp it (e.g. ``("g", "o", "c", "m", "y",
    "k")`` → ``("CMYKOG", ["CMYKOG_C", …, "CMYKOG_G"])``).
    """
    wanted = set(ink_codes)
    unknown = wanted - set(_INK_BIT_ORDER)
    if unknown:
        raise ValueError(
            f"unknown ink code(s) {sorted(unknown)!r}; expected codes from "
            f"{list(_INK_BIT_ORDER)!r}"
        )
    letters = [_INK_REP_LETTER[c] for c in _INK_BIT_ORDER if c in wanted]
    bident = "".join(letters)
    return bident, [f"{bident}_{letter}" for letter in letters]


# Bradford-adapted sRGB -> XYZ(D50) matrix (#72 appendix C). Used only for the
# naive-XYZ fallback of hand-added N-channel patches: measured against profile
# truth it gives median |dY| 1.35 with lightness rank-order 0.974 — plausible
# with margin for its two consumers (spacer-colour choice, chartread strip-ID).
_SRGB_TO_XYZ_D50 = (
    (0.4360747, 0.3850649, 0.1430804),
    (0.2225045, 0.7168786, 0.0606169),
    (0.0139322, 0.0971045, 0.7141733),
)
# targen's D50 white point as stamped in its own multi-ink .ti1 headers.
_WHITE_XYZ_D50 = (96.42, 100.0, 82.49)
# Same 1% viewing-flare-toward-white targen applies (see i1profiler_import's
# _TARGEN_FLARE): keeps solid black off exact (0,0,0), which chartread's
# strip-ID logic and the engine's media-patch pick both dislike (#72 HP 12).
_NCH_FLARE = 0.01


def _naive_xyz_nchannel(
    dev: tuple[float, ...], color_rep: str
) -> tuple[float, float, float]:
    """Approximate XYZ(D50) for an N-channel device tuple (#72 appendix C).

    Display-RGB approximation of the ink values -> sRGB linearisation -> D50
    matrix, scaled to Y=100, with a 1% flare toward white. Only ever used for
    patches with no better source: targen patches carry targen's own model and
    profile-inverted patches get exact ``xicclu -ff`` values.
    """
    from workflow.layout_engine.colorants import to_display_rgb

    rgb = to_display_rgb(dev, color_rep)

    def lin(c8: int) -> float:
        c = c8 / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = lin(rgb[0]), lin(rgb[1]), lin(rgb[2])
    x, y, z = (100.0 * (m[0] * r + m[1] * g + m[2] * b) for m in _SRGB_TO_XYZ_D50)
    wx, wy, wz = _WHITE_XYZ_D50
    f = _NCH_FLARE
    return (x + f * (wx - x), y + f * (wy - y), z + f * (wz - z))


def write_ti1_nchannel(
    color_rep: str,
    dev_fields: list[str],
    rows: list[tuple[tuple[float, ...], tuple[float, float, float] | None]],
    out_path: Path,
    *,
    ink_limit: float | None = None,
) -> Path:
    """Write a **single-table** N-channel ``.ti1`` for the layout engine (#72).

    ``rows`` are ``(device_tuple, xyz_or_None)`` pairs on the TI1 0..100 scale;
    a ``None`` XYZ gets the naive D50 estimate (:func:`_naive_xyz_nchannel`).
    ``ink_limit`` (percent) is stamped as ``TOTAL_INK_LIMIT``, the keyword
    targen writes and colprof reads back from the measurement chain.

    This is the engine-format sidecar: :mod:`workflow.layout_engine.ti1_reader`
    reads only the first table, so one table is all the engine path needs.
    printtarg would reject this file ("doesn't contain two or three tables") —
    N-channel relayout is engine-only by design (#72 decision 0); the
    printtarg path keeps the 3-table RGB emitter untouched.
    """
    if not rows:
        raise ValueError("write_ti1_nchannel: no patches to write")
    n = len(dev_fields)
    if any(len(dev) != n for dev, _ in rows):
        raise ValueError(
            f"write_ti1_nchannel: device tuple length mismatch "
            f"(expected {n} channels for {color_rep!r})"
        )
    wx, wy, wz = _WHITE_XYZ_D50
    fmt = "{:.4f}".format
    lines = [
        "CTI1   ",
        "",
        'DESCRIPTOR "Argyll Calibration Target chart information 1"',
        'ORIGINATOR "ChromIQ"',
        f'APPROX_WHITE_POINT "{wx:.6f} {wy:.6f} {wz:.6f}"',
        f'COLOR_REP "{color_rep}"',
        *([f'TOTAL_INK_LIMIT "{ink_limit:.1f}"'] if ink_limit is not None else []),
        f'CREATED "{datetime.now().strftime("%a %b %d %H:%M:%S %Y")}"',
        "",
        f"NUMBER_OF_FIELDS {1 + n + 3}",
        "BEGIN_DATA_FORMAT",
        f"SAMPLE_ID {' '.join(dev_fields)} XYZ_X XYZ_Y XYZ_Z",
        "END_DATA_FORMAT",
        "",
        f"NUMBER_OF_SETS {len(rows)}",
        "BEGIN_DATA",
    ]
    for i, (dev, xyz) in enumerate(rows, start=1):
        if xyz is None:
            xyz = _naive_xyz_nchannel(dev, color_rep)
        lines.append(
            f"{i} {' '.join(fmt(v) for v in dev)} {' '.join(fmt(v) for v in xyz)}"
        )
    lines.append("END_DATA")
    out_path = Path(out_path)
    out_path.write_text("\n".join([*lines, ""]), encoding="utf-8")
    return out_path


def write_ti1(
    spec: ChartSpec,
    dev_values: list[tuple[float, ...]],
    out_path: Path,
    *,
    spacer_palette: tuple[tuple[float, float, float], ...] | None = None,
    ink_limit: float | None = None,
) -> Path:
    """Write a ``.ti1`` whose patches are exactly ``dev_values``.

    ``dev_values`` is the final ordered list of device tuples (0..100) — the
    edited chart program. Reordering, recolouring a patch (a changed entry), and
    add/remove are all just transforms of this list; the renderer places each
    value *and* writes it into the .ti2, so a recoloured patch's pixel and its
    .ti2 device value stay coupled by construction.

    **RGB** charts delegate to the battle-tested 3-table emitter in
    :mod:`workflow.i1profiler_import` (byte-identical to before #72 — printtarg
    needs the patch list **plus** the density-extremes table, which doubles as
    the spacer-colour palette; see printtarg.c ~L3576, plus the
    device-combinations table). ``spacer_palette`` (0..100 RGB triples) is
    forwarded as that density-extremes table so printtarg renders spacers in
    those colours natively.

    **Non-RGB** charts get the single-table engine-format file from
    :func:`write_ti1_nchannel` — N-channel is engine-only (#72 decision 0), and
    the engine takes its spacer palette natively via ``build_chart`` kwargs, so
    ``spacer_palette`` is ignored here. Each patch keeps the XYZ recorded in
    ``spec`` when its device tuple is unchanged; recoloured/new patches fall
    back to the naive D50 estimate.
    """
    rep = spec.color_rep.lstrip("i").upper()
    if rep != "RGB":
        xyz_by_dev: dict[tuple[float, ...], tuple[float, float, float]] = {
            tuple(p.dev): p.xyz for p in spec.patches if p.xyz is not None
        }
        rows = [(tuple(dev), xyz_by_dev.get(tuple(dev))) for dev in dev_values]
        return write_ti1_nchannel(
            spec.color_rep, list(spec.dev_fields), rows, Path(out_path),
            ink_limit=ink_limit if ink_limit is not None else spec.ink_limit,
        )
    from workflow.i1profiler_import import RgbPatch, write_ti1 as _write_ti1

    patches = [RgbPatch(*rgb) for rgb in dev_values]
    return _write_ti1(patches, Path(out_path), density_extremes=spacer_palette)


# ---------------------------------------------------------------------------
# Regeneration via printtarg
# ---------------------------------------------------------------------------
@dataclass
class RegenResult:
    ti2: Path
    tiffs: list[Path]               # default-spacer pages (the deliverable)
    bw_tiffs: list[Path | None]     # B&W-spacer twin pages (mask source);
    #                                 None for any deliverable page the twin
    #                                 render didn't produce (page-break skew)
    basename: str


def regenerate(
    spec: ChartSpec,
    dev_values: list[tuple[float, ...]],
    out_dir: Path,
    bin_dir: Path,
    *,
    basename: str = "chart",
    dpi: int = 300,
    extra_args: list[str] | None = None,
    spacer_palette: tuple[tuple[float, float, float], ...] | None = None,
    options: "LayoutOptions | None" = None,
    with_twin: bool = True,
    dpi_override: int | None = None,
) -> RegenResult:
    """Run printtarg twice (default + ``-b``) and return the artefact paths.

    Both runs use the *same* basename in *separate* directories so only the
    spacers differ between them (the stamped chart label is identical).

    ``spacer_palette`` recolours spacers natively on the deliverable render (the
    ``-b`` twin is only used to locate spacer pixels, so it keeps the default
    palette — geometry is pinned by ``-r`` regardless of palette).

    ``options`` carries the printtarg layout knobs the editor exposes (scale,
    spacer mode, ``-L``, ``-P``, ``-h``, margin, DPI, bit depth, triple-density).
    All non-spacer-mode flags are applied to BOTH renders so geometry matches;
    spacer-mode flags are stripped from the twin which always uses ``-b`` to
    provide a colour-only diff. ``options.dpi`` and ``options.tiff_16bit``
    override the ``dpi`` kwarg + 8-bit default; ``options.triple_density``
    overrides ``spec.instrument_flag`` to "i1" and rewrites the deliverable
    .ti2's TARGET_INSTRUMENT back to ColorMunki post-render (mirroring
    workflow/chart_creator.py's triple-density behaviour).
    """
    # N-channel charts are engine-only (#72 decision 0): write_ti1 would emit
    # the single-table engine format here, which printtarg rejects with an
    # unhelpful "doesn't contain two or three tables". Fail loudly instead —
    # the dialog routes non-RGB charts to the engine before ever calling this.
    if spec.color_rep.lstrip("i").upper() != "RGB":
        raise RuntimeError(
            f"printtarg relayout supports RGB charts only (got COLOR_REP "
            f"{spec.color_rep!r}); multi-ink charts re-render through the "
            "ChromIQ layout engine."
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bw_dir = out_dir / "_spacer_twin"
    bw_dir.mkdir(parents=True, exist_ok=True)

    printtarg = Path(bin_dir) / "printtarg"
    layout_args = options.to_printtarg_args() if options else []
    # Non-spacer-mode flags ride along on both renders so geometry matches.
    geometry_args = [a for a in layout_args
                     if not (a == "-b" or a == "-n" or a == "-c")]
    deliverable_args = list(layout_args)
    # Triple-density: render with the i1Pro strip layout regardless of the
    # chart's stored instrument flag. The .ti2's TARGET_INSTRUMENT is patched
    # back to ColorMunki after the run (see _patch_ti2_for_triple_density).
    triple = bool(options and options.triple_density)
    instr_flag = "i1" if triple else spec.instrument_flag
    # dpi_override lets the editor render a fast low-res *preview* while the
    # saved chart still uses options.dpi (the .ti2 patch data is DPI-independent,
    # so only the on-screen TIFF resolution changes).
    use_dpi = dpi_override if dpi_override else (options.dpi if options else dpi)
    dpi_flag = "-T" if options and options.tiff_16bit else "-t"
    base_args = [
        f"-i{instr_flag}",
        f"-p{spec.paper_flag}",
        f"{dpi_flag}{use_dpi}",
        "-r",                       # honour our .ti1 order, don't randomise
        *(extra_args or []),
    ]

    def _run(work: Path, bw: bool) -> list[Path]:
        # The bw twin always gets the shifted palette so default-mode white &
        # black spacer choices in the deliverable still diff against it.
        write_ti1(spec, dev_values, work / f"{basename}.ti1",
                  spacer_palette=_BW_TWIN_PALETTE if bw else spacer_palette)
        flags = (geometry_args + ["-b"]) if bw else deliverable_args
        args = [str(printtarg), *base_args, *flags, basename]
        r = subprocess.run(args, cwd=str(work), capture_output=True,
                           text=True, timeout=300, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"printtarg failed ({r.returncode}): {r.stderr.strip()}")
        return sorted({*work.glob(f"{basename}*.tif"), *work.glob(f"{basename}*.tiff")})

    tiffs = _run(out_dir, bw=False)
    # The B&W twin is a second printtarg run, used only to locate spacer pixels
    # (Spacers-mode selection) and to refine patch y-bands. The editor skips it
    # for the common Patches-mode preview (with_twin=False) to halve the render
    # cost; patch geometry then falls back to coarser bbox-only y-bands.
    bw_tiffs = _run(bw_dir, bw=True) if with_twin else []
    if not tiffs:
        raise RuntimeError("printtarg produced no TIFF pages")
    # The B&W twin exists only as a spacer-mask source for the editor. Its
    # spacer geometry differs from the deliverable's (it always forces -b and
    # drops -n / -A), so near a page boundary the two renders can spill onto a
    # different number of pages. That's harmless — the deliverable is what we
    # ship — so instead of failing, align the twin list to the deliverable:
    # pad short with None (that page just gets coarser, mask-less geometry) and
    # truncate any extra twin pages. spacer_mask / patch_geometry_for_page both
    # tolerate a missing or shape-mismatched twin.
    bw_aligned: list[Path | None] = [
        bw_tiffs[i] if i < len(bw_tiffs) else None
        for i in range(len(tiffs))
    ]
    ti2 = out_dir / f"{basename}.ti2"
    if triple:
        _patch_ti2_for_triple_density(ti2)
    return RegenResult(ti2, tiffs, bw_aligned, basename)


# ---------------------------------------------------------------------------
# "Tag as randomised" — gate + keyword rewrite
# ---------------------------------------------------------------------------
#
# The editor renders with printtarg ``-r`` (keep our order), so the .ti2 carries
# CHART_ID and chartread treats it as fixed-order: no auto strip-ID, no
# bidirectional reading. Re-labelling it RANDOM_START unlocks both — but only
# *safely* when the patch order is actually well mixed. On a structured order
# (a smooth ramp, or an i1Profiler-style RGB-cube grid) neighbouring strips look
# alike, so chartread can latch onto the wrong strip/direction and silently scramble
# the readings → a colour-cast profile (see the project_norandomize_chartread_bug
# diagnosis). The risk grows with strip count, i.e. with big charts.
#
# analyze_randomisation() measures, on the *produced* layout, the two things that
# break: whether any strip reads the same forwards and backwards (direction
# ambiguous), and whether any two strips are near-identical (strip ambiguous).
# Thresholds were calibrated on synthetic ramp / grid / shuffled charts from 24
# to 3000 patches: shuffled (safe) stayed at symmetry>=38 & confusability>=50 at
# every size, ramps collapsed to ~0-2, and grids collapsed in confusability as
# they grew (58 -> 10 by 3000 patches). The cut sits conservatively below the
# safe band so an uncertain chart is reported unsafe (the user can still override).

_SYM_THRESHOLD = 25.0     # min mean RGB distance between a strip and its reverse
_CONF_THRESHOLD = 40.0    # min mean RGB distance between any two strips


@dataclass
class RandomisationReport:
    """Verdict on whether a chart's layout is safe to tag as randomised."""
    safe: bool
    n_strips: int
    min_symmetry: float        # inf when undefined (e.g. single-patch strips)
    min_confusability: float   # inf when < 2 strips
    reason: str


_LOC_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
# printtarg writes CHART_ID (fixed order) / RANDOM_START (randomised); chartread
# keys auto strip-ID + bidirectional reading off the latter (chartread.c:2980).
_RANDOM_START_RE = re.compile(r"\bRANDOM_START\b")


def _read_ti2_strips(ti2_path: Path) -> list["np.ndarray"]:
    """Group a .ti2's patches into per-strip device-value sequences (by SAMPLE_LOC).

    Returns one ``[n_patches, n_channels]`` float array per strip, patches
    ordered by the numeric part of their SAMPLE_LOC (e.g. A1, A2, …). Strips
    are returned in first-seen order. Channel-generic since #72: the device
    columns are identified from ``COLOR_REP`` exactly like
    :meth:`ChartSpec.from_ti2` does, so CMYK/N charts are analysed for real
    instead of silently skipping (the old RGB-only parse returned ``[]`` for
    them — a silent bypass of the confusability gate).

    Raises ``ValueError`` when the file cannot be parsed (unreadable, no
    format/data block, no SAMPLE_LOC, no device columns) — callers must treat
    that as "cannot analyse", never as "safe".
    """
    try:
        text = ti2_path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        raise ValueError(f"{ti2_path.name}: unreadable ({exc})") from exc
    lines = text.splitlines()
    try:
        fmt_i = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA_FORMAT")
        fields = lines[fmt_i + 1].split()
        loc_ix = fields.index("SAMPLE_LOC")
        data_i = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    except (StopIteration, ValueError) as exc:
        raise ValueError(
            f"{ti2_path.name}: no parsable DATA_FORMAT/DATA/SAMPLE_LOC"
        ) from exc

    # Device columns, COLOR_REP-first with the same fallback as from_ti2.
    m_rep = re.search(r'^\s*COLOR_REP\s+"?([^"\n]*)"?\s*$', text, re.MULTILINE)
    rep = (m_rep.group(1).strip() if m_rep else "iRGB").lstrip("i")
    dev_ix = [i for i, f in enumerate(fields) if f.startswith(rep + "_")]
    if not dev_ix:
        dev_ix = [i for i, f in enumerate(fields)
                  if "_" in f and not f.startswith(("XYZ", "LAB", "SPEC"))
                  and f not in ("SAMPLE_ID", "SAMPLE_LOC", "SAMPLE_NAME")]
    if not dev_ix:
        raise ValueError(f"{ti2_path.name}: no device columns for COLOR_REP {rep!r}")

    strips: dict[str, list[tuple[int, tuple[float, ...]]]] = {}
    order: list[str] = []
    max_ix = max(loc_ix, *dev_ix)
    for l in lines[data_i + 1:]:
        if l.strip() == "END_DATA":
            break
        p = l.split()
        if len(p) <= max_ix:
            continue
        m = _LOC_RE.match(p[loc_ix].strip('"'))
        if not m:
            continue
        letter, num = m.group(1), int(m.group(2))
        try:
            dev = tuple(float(p[i]) for i in dev_ix)
        except ValueError:
            continue
        if letter not in strips:
            strips[letter] = []
            order.append(letter)
        strips[letter].append((num, dev))

    out: list[np.ndarray] = []
    for letter in order:
        seq = [dev for _, dev in sorted(strips[letter])]
        out.append(np.asarray(seq, dtype=float))
    return out


def _mean_row_dist(a: "np.ndarray", b: "np.ndarray") -> float:
    """Mean per-patch Euclidean RGB distance over the common length of two strips."""
    n = min(len(a), len(b))
    if n == 0:
        return float("inf")
    return float(np.linalg.norm(a[:n] - b[:n], axis=1).mean())


def analyze_randomisation(ti2_path: Path) -> RandomisationReport:
    """Judge whether ``ti2_path``'s layout is well-mixed enough to tag as randomised.

    Safe requires every strip to differ from its own reverse (direction is
    decidable) and every pair of strips to differ from each other in both
    orientations (the right strip is decidable), each by a calibrated margin.
    A chart with fewer than two multi-patch strips is trivially safe.

    A chart that cannot be *parsed* is reported **unsafe** ("cannot analyse"),
    never trivially safe — the pre-#72 RGB-only parse returned no strips for a
    CMYK chart and thereby waved every N-channel chart through the gate
    unchecked. The distance metric is Euclidean over all device channels
    (absolute device-%, #72 appendix E), so N-channel strips are analysed with
    the same calibrated thresholds as RGB.
    """
    try:
        strips = _read_ti2_strips(ti2_path)
    except ValueError as exc:
        return RandomisationReport(
            False, 0, float("nan"), float("nan"),
            f"The chart layout could not be analysed ({exc}) — leaving it "
            "untagged, so it will be measured one direction only.")
    multi = [s for s in strips if len(s) >= 2]
    n = len(strips)

    if len(multi) < 2:
        return RandomisationReport(True, n, float("inf"), float("inf"),
                                   "Too few strips to be confusable.")

    # Direction ambiguity: any strip that reads ~the same forwards and backwards.
    min_sym = min(_mean_row_dist(s, s[::-1]) for s in multi)
    if min_sym < _SYM_THRESHOLD:
        return RandomisationReport(
            False, n, min_sym, float("nan"),
            "A strip reads almost the same in both directions, so the reading "
            "direction can't be told apart.")

    # Strip ambiguity: any two strips near-identical in either orientation.
    # Compare equal-length strips vectorised; the last strip may be shorter, so
    # truncate everything to the shortest length for the pairwise pass.
    min_len = min(len(s) for s in multi)
    arr = np.stack([s[:min_len] for s in multi])           # [S, L, 3]
    rev = arr[:, ::-1, :]
    min_conf = float("inf")
    for i in range(len(arr)):
        # distance from strip i to every strip, forwards and reversed
        d_fwd = np.linalg.norm(arr - arr[i], axis=2).mean(axis=1)   # [S]
        d_rev = np.linalg.norm(rev - arr[i], axis=2).mean(axis=1)   # [S]
        d_fwd[i] = np.inf                                            # skip self
        local = float(min(d_fwd.min(), d_rev.min()))
        if local < min_conf:
            min_conf = local
        if min_conf < _CONF_THRESHOLD:
            return RandomisationReport(
                False, n, min_sym, min_conf,
                "Two strips look almost identical, so chartread can't reliably "
                "tell which strip is which.")

    return RandomisationReport(True, n, min_sym, min_conf,
                               "Layout is well mixed.")


def tag_ti2_randomised(ti2_path: Path) -> bool:
    """Relabel a fixed-order .ti2 as randomised (CHART_ID → RANDOM_START).

    chartread keys auto strip-ID and bidirectional reading off this keyword
    (chartread.c:2980); the physical layout (SAMPLE_LOC + values) is untouched,
    so the chart on paper is identical. Returns True if a rewrite happened,
    False if the file was already randomised or couldn't be read.
    """
    try:
        text = ti2_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if _RANDOM_START_RE.search(text):
        return False
    new = re.sub(r'\bCHART_ID\b', "RANDOM_START", text, count=1)
    if new == text:
        return False
    try:
        ti2_path.write_text(new, encoding="utf-8")
    except OSError as exc:
        log.warning("tag-as-randomised rewrite failed for %s: %s", ti2_path, exc)
        return False
    return True


def _patch_ti2_for_triple_density(ti2: Path) -> None:
    """Rewrite TARGET_INSTRUMENT from i1 Pro back to ColorMunki.

    Triple density uses the i1Pro strip layout so printtarg writes
    ``TARGET_INSTRUMENT "GretagMacbeth i1 Pro"`` into the .ti2; chartread
    needs to drive the ColorMunki the user actually has, so we patch that
    string post-run. Mirrors workflow.chart_creator._patch_ti2_instrument.
    """
    if not ti2.is_file():
        return
    try:
        text = ti2.read_text(encoding="utf-8", errors="ignore")
        new = text.replace(
            'TARGET_INSTRUMENT "GretagMacbeth i1 Pro"',
            'TARGET_INSTRUMENT "X-Rite ColorMunki"',
        )
        if new != text:
            ti2.write_text(new, encoding="utf-8")
    except OSError as exc:
        log.warning("triple-density ti2 patch failed for %s: %s", ti2, exc)


# ---------------------------------------------------------------------------
# Spacer detection + segmentation
# ---------------------------------------------------------------------------
@dataclass
class Spacer:
    """One contiguous spacer region on a page."""
    page: int
    pixels: tuple[np.ndarray, np.ndarray]   # (ys, xs) for fast recolour
    bbox: tuple[int, int, int, int]         # x0, y0, x1, y1 (inclusive)
    centroid: tuple[float, float]           # (cx, cy)

    @property
    def area(self) -> int:
        return int(self.pixels[0].size)


# Palette the ``-b`` twin renders with: defaults, but `pcol[0]` and `pcol[7]`
# are nudged a few code values off pure white / pure black. printtarg's `-b`
# mode picks one of these two entries per gap (see printtarg.c setup_spacer
# L1167), and the default deliverable palette has pure white/black at the
# same positions — so a default-mode WHITE or BLACK spacer choice (common:
# black between light patches, white between dark patches) used to collide
# with the twin's identical choice and was invisible to the diff. Nudging
# only the twin keeps the deliverable visually pure white/black; the small
# (~10/255) shift clears the diff threshold so those gaps now register.
_BW_TWIN_PALETTE: tuple[tuple[float, float, float], ...] = (
    (98.0, 100.0, 98.0),     # near-white (was 100,100,100)
    (0.0,  100.0, 100.0),    # cyan       (unchanged; -b ignores entries 1-6)
    (100.0, 0.0,  100.0),    # magenta
    (0.0,  0.0,   100.0),    # blue
    (100.0, 100.0, 0.0),     # yellow
    (0.0,  100.0, 0.0),      # green
    (100.0, 0.0,  0.0),      # red
    (2.0,  0.0,   2.0),      # near-black (was 0,0,0)
)


def _label_band_end(arr: np.ndarray) -> int | None:
    """Return the y of the last row in the strip-label band (A B C…), or None.

    The label band is at the top of the deliverable: a row of sparse darks
    (single-letter strip labels) on white. Detected as the topmost
    contiguous span of rows whose dark-pixel count is in
    ``[MIN_LABEL_DARK, 30% of width]`` — narrow enough to admit single
    letters but exclude solid patch rows. Extracted so callers needing
    only the y-anchor (e.g. patch_geometry_for_page) don't have to run
    the multi-strip-fragile bbox math in :func:`_patch_grid_bbox`.
    """
    h, w = arr.shape[:2]
    if h < 50 or w < 50:
        return None
    gray = arr.mean(axis=2)
    DARK            = 80
    MIN_LABEL_DARK  = max(5, w // 200)
    MAX_LABEL_FRAC  = 0.30
    EMPTY_STOP      = 8
    max_label_dark = int(w * MAX_LABEL_FRAC)
    y_lab_start: int | None = None
    y_lab_end:   int | None = None
    empty_streak = 0
    for y in range(h * 30 // 100):
        count = int((gray[y] < DARK).sum())
        if MIN_LABEL_DARK <= count <= max_label_dark:
            if y_lab_start is None:
                y_lab_start = y
            y_lab_end = y
            empty_streak = 0
        else:
            empty_streak += 1
            if y_lab_start is not None and empty_streak >= EMPTY_STOP:
                break
    return y_lab_end


def _patch_grid_bbox(arr: np.ndarray) -> tuple[int, int, int, int] | None:
    """Bounding box of the patch grid in a deliverable page.

    Adapted from ``ui.tabs.tab_measure._detect_uniform_stripe_rects`` — the
    same algorithm the Measure tab uses to position its strip highlighter
    over the patch block while explicitly ignoring the rotated title string
    printtarg prints down the right margin. Three passes:

    1. Find the label band at the top via :func:`_label_band_end`.
    2. Below the labels, look at every column's "has-content" count and
       take the **widest contiguous run** of content columns. The patch
       block is one solid edge-to-edge run; the right-margin title is a
       narrower run separated by a wide white gap and gets dropped.
    3. Take the vertical extent from the topmost to bottommost content row.

    Returns ``(y0, y1, x0, x1)`` inclusive, or ``None`` if the page can't be
    analysed (callers fall back to using the full image).
    """
    h, w = arr.shape[:2]
    if h < 50 or w < 50:
        return None
    gray = arr.mean(axis=2)  # 0..255 luminance proxy

    # ── 1. Label band → vertical anchor ───────────────────────────────────
    WHITE = 240
    y_lab_end = _label_band_end(arr)
    if y_lab_end is None:
        return None

    # ── 2. Patch block = widest contiguous run of content columns ─────────
    y0 = y_lab_end + 1
    y1 = int(h * 0.97)
    if y1 <= y0:
        return None
    col_content = (gray[y0:y1] < WHITE).sum(axis=0)
    thr = (y1 - y0) * 0.10
    gap = max(2, w // 250)
    best: tuple[int, int] | None = None
    run_start: int | None = None
    last = 0
    for x in range(w):
        if int(col_content[x]) > thr:
            if run_start is None:
                run_start = x
            last = x
        elif run_start is not None and x - last > gap:
            if best is None or (last - run_start) > (best[1] - best[0]):
                best = (run_start, last)
            run_start = None
    if run_start is not None and (
        best is None or (last - run_start) > (best[1] - best[0])
    ):
        best = (run_start, last)
    if best is None:
        return None
    block_l, block_r = best

    # ── 3. Vertical extent (top/bottom rows that contain any content) ─────
    sample = max(1, w // 250)
    any_content = (gray[:, ::sample] < WHITE).any(axis=1)
    nz = np.where(any_content)[0]
    y_top    = int(nz[0])  if nz.size else 0
    y_bottom = int(nz[-1]) if nz.size else h - 1
    return (max(y_lab_end + 1, y_top), y_bottom, block_l, block_r)


def spacer_mask(default_tif: Path, bw_tif: Path, *, thresh: int = 8) -> np.ndarray:
    """Boolean mask of spacer pixels in ``default_tif``.

    Computed as ``|default - bw_twin| > thresh`` and then clamped to the
    deliverable's patch-grid bounding box so the twin's near-white background
    diff in the margins doesn't bleed into the mask. The twin should be
    rendered via :func:`regenerate` (which uses :data:`_BW_TWIN_PALETTE`) so
    pure-white and pure-black spacer choices register too.
    """
    a = np.asarray(_imread_rgb(default_tif), dtype=np.int16)
    b = np.asarray(_imread_rgb(bw_tif), dtype=np.int16)
    if a.shape != b.shape:
        raise ValueError("default/bw page size mismatch — geometry not preserved")
    diff = np.abs(a - b).sum(axis=2) > thresh
    bbox = _patch_grid_bbox(a)
    if bbox is None:
        return diff
    y0, y1, x0, x1 = bbox
    out = np.zeros_like(diff)
    out[y0:y1 + 1, x0:x1 + 1] = diff[y0:y1 + 1, x0:x1 + 1]
    return out


def segment_spacers(
    mask: np.ndarray,
    page: int,
    *,
    min_area: int = 12,
    min_extent: int = 20,
    ref_arr: np.ndarray | None = None,
    strip_xs: list[int] | None = None,
) -> list[Spacer]:
    """Label connected spacer components (4-connectivity, scipy-free BFS).

    The mask is sparse (~1% of the page), so BFS over True pixels is cheap.

    ``min_extent`` rejects components whose longest bbox dimension is below
    this threshold (default 20 px). Real spacers are elongated bars — even a
    single-cell spacer is ≥ a patch width long. Stray label-text characters
    that survive the bbox restriction are typically <10 px in either
    dimension and get filtered out here.

    ``strip_xs`` (a list of x-coordinates where adjacent strips meet, derived
    from the .ti2's ``PASSES_IN_STRIPS2``) is the **authoritative** way to
    split wide horizontal bands into per-strip cells — it works even when two
    adjacent strips happen to pick the same spacer colour and the colour-jump
    heuristic can't see the boundary.

    Otherwise, when ``ref_arr`` (the deliverable page as HxWx3) is supplied,
    wide horizontal bands get split by colour discontinuity along the central
    row. This is a usable fallback when the strip layout is unknown.
    """
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    ys_all, xs_all = np.where(mask)
    raw: list[Spacer] = []

    for sy, sx in zip(ys_all.tolist(), xs_all.tolist()):
        if seen[sy, sx]:
            continue
        comp_y: list[int] = []
        comp_x: list[int] = []
        q = deque([(sy, sx)])
        seen[sy, sx] = True
        while q:
            y, x = q.popleft()
            comp_y.append(y)
            comp_x.append(x)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(comp_y) < min_area:
            continue
        ay = np.array(comp_y)
        ax = np.array(comp_x)
        bw = int(ax.max() - ax.min() + 1)
        bh = int(ay.max() - ay.min() + 1)
        if max(bw, bh) < min_extent:
            continue   # too small to be a spacer bar — likely stray text
        raw.append(Spacer(
            page=page,
            pixels=(ay, ax),
            bbox=(int(ax.min()), int(ay.min()), int(ax.max()), int(ay.max())),
            centroid=(float(ax.mean()), float(ay.mean())),
        ))

    if strip_xs is not None:
        refined: list[Spacer] = []
        for sp in raw:
            refined.extend(_split_band_by_strips(
                sp, strip_xs, page=page, min_area=min_area))
        return refined

    if ref_arr is None:
        return raw

    refined = []
    for sp in raw:
        sub = _split_band_by_colour(sp, ref_arr, page=page, min_area=min_area)
        refined.extend(sub)
    return refined


def _split_band_by_strips(
    sp: Spacer, strip_xs: list[int], *, page: int, min_area: int,
) -> list[Spacer]:
    """Split a wide horizontal band at known inter-strip x-boundaries.

    Each ``strip_xs`` entry is an x-coordinate where two adjacent strips meet.
    Pixels in the component are partitioned by which strip-cell they fall into.
    Components that aren't wide bands (bbox aspect ratio < 2) pass through.
    """
    x0, y0, x1, y1 = sp.bbox
    bw = x1 - x0 + 1
    bh = y1 - y0 + 1
    if bw <= 2 * bh:
        return [sp]
    bounds = sorted({x0, x1 + 1, *(b for b in strip_xs if x0 < b <= x1)})
    if len(bounds) <= 2:
        return [sp]
    ys, xs = sp.pixels
    cells: list[Spacer] = []
    for left, right in zip(bounds[:-1], bounds[1:]):
        sel = (xs >= left) & (xs < right)
        if int(sel.sum()) < min_area:
            continue
        cy = ys[sel]
        cx = xs[sel]
        cells.append(Spacer(
            page=page,
            pixels=(cy, cx),
            bbox=(int(cx.min()), int(cy.min()), int(cx.max()), int(cy.max())),
            centroid=(float(cx.mean()), float(cy.mean())),
        ))
    return cells or [sp]


def _split_band_by_colour(
    sp: Spacer, ref_arr: np.ndarray, *, page: int, min_area: int,
) -> list[Spacer]:
    """Split a wide horizontal band into per-strip cells by colour jumps.

    Only triggers when the bbox is at least 2× wider than tall — narrow /
    isolated spacers fall through untouched. Boundaries are detected by
    sampling colours along the band's central row and finding where consecutive
    pixels differ by more than ~30 (sum-of-channels). Single-strip bands
    naturally yield one cell == the original component.
    """
    x0, y0, x1, y1 = sp.bbox
    bw = x1 - x0 + 1
    bh = y1 - y0 + 1
    if bw <= 2 * bh:
        return [sp]

    yc = (y0 + y1) // 2
    row = ref_arr[yc, x0:x1 + 1].astype(np.int16)
    diff = np.abs(np.diff(row, axis=0)).sum(axis=1)
    splits = np.where(diff > 30)[0]
    # Build cell x-ranges (inclusive)
    boundaries = [x0] + [x0 + int(s) + 1 for s in splits] + [x1 + 1]
    ys, xs = sp.pixels
    cells: list[Spacer] = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        sel = (xs >= left) & (xs < right)
        if int(sel.sum()) < min_area:
            continue
        cy = ys[sel]
        cx = xs[sel]
        cells.append(Spacer(
            page=page,
            pixels=(cy, cx),
            bbox=(int(cx.min()), int(cy.min()), int(cx.max()), int(cy.max())),
            centroid=(float(cx.mean()), float(cy.mean())),
        ))
    return cells or [sp]


# ---------------------------------------------------------------------------
# Recolour + integrity
# ---------------------------------------------------------------------------
def recolor_spacers(
    page_tif: Path,
    spacers: list[Spacer],
    rgb: tuple[int, int, int],
    out_tif: Path,
    *,
    dpi: int = 300,
) -> None:
    """Paint ``rgb`` into the given spacers' pixels; write a format-faithful TIFF.

    Only the listed pixels change — every other pixel (all patches) is copied
    byte-for-byte from ``page_tif``.
    """
    import tifffile

    arr = _imread_rgb(page_tif).copy()
    for sp in spacers:
        ys, xs = sp.pixels
        arr[ys, xs] = rgb
    res = (dpi, dpi)
    tifffile.imwrite(str(out_tif), arr, photometric="rgb",
                     resolution=res, resolutionunit="INCH")


def assert_data_integrity(
    dev_values: list[tuple[float, ...]], new_ti2: Path
) -> int:
    """Raise unless every requested patch is present in the regenerated .ti2.

    "What you designed is what got built" — for a pure reorder ``dev_values`` is
    the source patches resequenced, and for recolours it's the edited values.
    Either way we require the requested device-value multiset to be contained in
    the output's. Two printtarg behaviours are accounted for:

    * It may **add** patches to complete a partial final strip (a full-strip
      chart round-trips exactly; only a partial last row gets padded).
    * It **quantises device values to 8-bit** (e.g. a hand-entered 75.0 becomes
      191/255 = 74.9). Real charts are already 8-bit-aligned so this is a no-op
      for them; we compare on the 8-bit grid so a snapped hand-picked colour
      still counts as present.

    Returns the number of padding patches printtarg added.
    """
    new = ChartSpec.from_ti2(new_ti2)

    def _code(v: float) -> int:
        # The 8-bit code printtarg renders this 0..100 device value to.
        return round(v / 100 * 255)

    def _codes(values) -> tuple[int, ...]:
        return tuple(_code(x) for x in values)

    # ±1-code tolerance per channel. printtarg snaps every device value to 8-bit;
    # our prediction of *which* code can differ from printtarg's by one at a
    # half-way boundary (round-half-to-even vs printtarg's own rounding). Charts
    # built from targen / imports are already 8-bit-aligned so this never bit,
    # but the "Generate colour sets" feature emits arbitrary floats that land on
    # those boundaries — a one-code shift there is below the device's own 8-bit
    # resolution, not a lost patch. A genuinely dropped patch is off by the full
    # colour distance and still fails. Neighbours are tried nearest-first so an
    # exact match is always preferred.
    from collections import Counter
    from itertools import product

    avail: Counter = Counter(_codes(p.dev) for p in new.patches)
    _offsets = sorted(product((0, -1, 1), repeat=3),
                      key=lambda o: sum(abs(c) for c in o))

    for want in dev_values:
        key = _codes(want)
        for off in _offsets:
            cand = tuple(c + d for c, d in zip(key, off))
            if avail.get(cand, 0) > 0:
                avail[cand] -= 1
                break
        else:
            raise AssertionError(
                f"requested patch {tuple(round(v, 3) for v in want)} missing "
                f"from regenerated chart (no 8-bit match within ±1 code)"
            )
    return len(new.patches) - len(dev_values)


def assert_patches_untouched(before_tif: Path, after_tif: Path, mask: np.ndarray) -> None:
    """Raise unless every non-spacer pixel is identical before vs after recolour."""
    before = _imread_rgb(before_tif)
    after = _imread_rgb(after_tif)
    if before.shape != after.shape:
        raise AssertionError("page size changed during recolour")
    outside = ~mask
    if not np.array_equal(before[outside], after[outside]):
        raise AssertionError("non-spacer pixels changed during recolour")


# ---------------------------------------------------------------------------
def _imread_rgb(path: Path) -> np.ndarray:
    """Read a TIFF page as an HxWx3 uint8 array (RGB).

    Device-native (separated CMYK / CMYK+N) charts can't be read by Pillow, so
    they're composited to a paper-white-vs-ink greyscale RGB — enough for the
    geometry consumers (margin inspector, patch-area detection). RGB charts keep
    the exact Pillow path unchanged. (#72 Tier D)
    """
    from PIL import Image
    try:
        import tifffile
        with tifffile.TiffFile(str(path)) as tf:
            if int(tf.pages[0].photometric) == 5:          # SEPARATED
                arr = tf.pages[0].asarray()
                if arr.ndim == 2:
                    arr = arr[..., None]
                maxv = (np.iinfo(arr.dtype).max
                        if np.issubdtype(arr.dtype, np.integer) else 1.0)
                ink = arr.astype(np.float32).max(axis=2) / float(maxv)
                g = np.clip((1.0 - ink) * 255.0, 0, 255).astype(np.uint8)
                return np.repeat(g[..., None], 3, axis=2)
    except Exception:                                      # noqa: BLE001
        pass                                               # fall back to Pillow
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Per-patch pixel geometry (for the preview's click + highlight overlay)
# ---------------------------------------------------------------------------
def _per_strip_step_grids(clean_centres, steps):
    """Build a ``within_strip -> [step-centre y, …]`` lookup from the per-strip
    detected patch-run centres.

    ``clean_centres[s]`` is strip *s*'s list of ``steps`` patch y-centres, or
    ``None`` when that strip's runs couldn't be resolved (patches matched their
    spacer colour, so they merge in the twin diff).

    A clean strip uses its own centres, which already carry any vertical offset
    — so ColorMunki double-density (``-h``) charts, where printtarg shifts
    alternate strips by half a patch (a zig-zag), are placed correctly (#48).
    An unresolved strip falls back to a grid pooled from the same-parity clean
    strips (the zig-zag is parity-regular), then to a global grid. Normal charts
    have every strip on one grid, so all parity grids coincide.

    Returns ``None`` when no strip resolved cleanly (caller uses a coarser
    image-anchored uniform divide instead).
    """
    import statistics

    def _median_grid(rows):
        return ([statistics.median(row[k] for row in rows) for k in range(steps)]
                if rows else None)

    by_parity = {0: [], 1: []}
    for s, c in enumerate(clean_centres):
        if c is not None:
            by_parity[s % 2].append(c)
    grid_all = _median_grid(by_parity[0] + by_parity[1])
    if grid_all is None:
        return None
    grid_by_parity = {0: _median_grid(by_parity[0]) or grid_all,
                      1: _median_grid(by_parity[1]) or grid_all}

    def lookup(within_strip: int) -> list[float]:
        c = (clean_centres[within_strip]
             if 0 <= within_strip < len(clean_centres) else None)
        if c is not None:
            return c
        return grid_by_parity[within_strip % 2]

    return lookup


def patch_geometry_for_page(
    ti2_path: Path, tif_path: Path, page: int,
    *, bw_tif_path: Path | None = None,
) -> dict[int, tuple[int, int, int, int]]:
    """Pixel bbox for each patch on a rendered page, keyed by SAMPLE_ID.

    Strategy:
        * The BW-twin diff gives the **outer** patch-block bbox (works for
          any strip count — spacers tile the block edge-to-edge).
        * That bbox is divided uniformly: ``n_strips`` columns × ``steps``
          rows. printtarg's i1Pro / ColorMunki layouts space patches
          uniformly within a strip, so a uniform divide places each rect
          close enough to its patch for click + highlight to feel right.
        * SAMPLE_LOC (e.g. "A12") in the .ti2 maps each SAMPLE_ID to a
          (strip, step) cell — strips go A,B,…,AA,AB,… across the chart,
          steps run 1..N down the strip.

    With ``-r`` (no-randomise) the .ti2's SAMPLE_ID order matches the
    editor's program order, so SAMPLE_ID N corresponds to grid index N-1
    and clicks can hop straight to the matching swatch.

    The simpler central-column-scan approach (find non-spacer runs)
    breaks on consecutive same-colour patches — printtarg picks a spacer
    colour that matches the patch, so the spacer is invisible in the diff
    and N consecutive patches merge into one run. Uniform divide sidesteps
    that.

    Returns an empty dict if anything can't be resolved (no ``bw_tif_path``,
    no SAMPLE_LOC, diff shape mismatch, …) — callers fall back gracefully.
    """
    if bw_tif_path is None:
        return {}
    try:
        text = Path(ti2_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    passes = parse_passes_per_page(ti2_path)
    if not passes or page >= len(passes):
        return {}
    sm = re.search(r'STEPS_IN_PASS\s+"?(\d+)"?', text)
    if not sm:
        return {}
    steps = int(sm.group(1))

    a = _imread_rgb(tif_path).astype(np.int16)
    b = _imread_rgb(bw_tif_path).astype(np.int16)
    if a.shape != b.shape:
        return {}
    diff = np.abs(a - b).sum(axis=2) > 8
    ys, xs = np.where(diff)
    if not ys.size:
        return {}
    y0_all, y1, x0, x1 = (int(ys.min()), int(ys.max()),
                          int(xs.min()), int(xs.max()))
    # The BW-diff x range is contaminated by the right-margin "ArgyllCMS …"
    # title that printtarg renders alongside the patch block — that text
    # diffs against the twin too, so x1 lands beyond the rightmost strip.
    # _patch_grid_bbox excludes the title by picking the widest content
    # column run, so use its x range when available.
    grid = _patch_grid_bbox(a.astype(np.uint8))
    if grid is not None:
        _, _, x0, x1 = grid
    # Snap y_top to just below the strip-label row (label letters diff
    # against the twin's near-white spacer 0). Without this, downstream
    # math lands the first row in the label band.
    lab_end = _label_band_end(a.astype(np.uint8))
    y_top = (lab_end + 2) if (lab_end is not None and lab_end + 2 < y1) else y0_all

    n_strips = passes[page]
    strip_w = (x1 - x0 + 1) / n_strips
    strips_before = sum(passes[:page])

    # Per-strip: walk the central column for non-spacer runs (= patches),
    # then keep only patch-sized ones — printtarg precedes each strip's
    # data with a tall leader patch (~3× a regular patch) and appends a
    # trailer at the bottom; both are too tall to be data patches, so
    # filtering by run-height drops them automatically. The remaining
    # `steps` runs in top→bottom order map straight onto step 1..N.
    strip_ranges: list[list[tuple[int, int]] | None] = []
    for s in range(n_strips):
        cx = int(x0 + (s + 0.5) * strip_w)
        col = diff[y_top:y1 + 1, cx]
        runs: list[tuple[int, int]] = []
        in_run = False
        start = 0
        for i, is_spacer in enumerate(col):
            if not is_spacer:
                if not in_run:
                    start = i
                    in_run = True
            elif in_run:
                runs.append((y_top + start, y_top + i - 1))
                in_run = False
        if in_run:
            runs.append((y_top + start, y_top + len(col) - 1))
        # Trim the page-margin run at the top/bottom of the scan. The strip
        # block sits inside the page's white margin, which is non-spacer
        # (white in both twin renders) so it surfaces as a tall white non-diff
        # run at the very top (and occasionally bottom). Left in, it passes the
        # height filter and — when a strip loses its bottom patch to a colour-
        # matched spacer — gets kept by the [-steps:] slice as a phantom
        # "step 0", pulling a highlight box up into the white area.
        #
        # A paper-white DATA patch renders pure white too, so colour alone
        # can't tell it from the margin. The structural tell: the margin abuts
        # the scan boundary (nothing separates it from the label band above /
        # page edge below), whereas a real top-of-strip patch is always held
        # off the boundary by its strip-start spacer. So only trim a white run
        # that touches the boundary — a genuine white first/last patch starts
        # well inside it and is kept.
        def _is_page_white(run: tuple[int, int]) -> bool:
            c = a[(run[0] + run[1]) // 2, cx]
            return int(c[0]) > 245 and int(c[1]) > 245 and int(c[2]) > 245
        if runs and runs[0][0] <= y_top + 2 and _is_page_white(runs[0]):
            runs.pop(0)
        if runs and runs[-1][1] >= y1 - 2 and _is_page_white(runs[-1]):
            runs.pop()
        if not runs:
            strip_ranges.append(None)
            continue
        # Estimate a normal patch height: the median of the bottom N
        # smallest runs. Leader and trailer are outliers and won't
        # contribute. Allow ±50 % around it as the "patch-like" band.
        heights = sorted(r[1] - r[0] + 1 for r in runs)
        med = heights[len(heights) // 2]
        keep_min = max(20, int(med * 0.5))
        keep_max = int(med * 1.5)
        patch_runs = [r for r in runs
                      if keep_min <= (r[1] - r[0] + 1) <= keep_max]
        # Take the BOTTOM-MOST `steps` of them: leader sits above and
        # trailer below the data — if filtering missed one, the bottom-
        # anchor is still the safer side because the trailer is usually
        # smaller and more uniform than the leader.
        if len(patch_runs) >= steps:
            strip_ranges.append(patch_runs[-steps:])
        else:
            strip_ranges.append(patch_runs or None)

    fm = re.search(r"BEGIN_DATA_FORMAT(.*?)END_DATA_FORMAT", text, re.DOTALL)
    dm = re.search(r"BEGIN_DATA(?!_FORMAT)(.*?)END_DATA", text, re.DOTALL)
    if not fm or not dm:
        return {}
    fields = fm.group(1).split()
    idx = {f: i for i, f in enumerate(fields)}
    id_i = idx.get("SAMPLE_ID", 0)
    loc_i = idx.get("SAMPLE_LOC")
    if loc_i is None:
        return {}

    # Build a step→y grid from the strips that detected a clean full set of
    # `steps` patch runs. A *single* shared grid would be wrong for ColorMunki
    # double density (-h), where printtarg offsets alternate strips by half a
    # patch (a zig-zag) — averaging the offset and non-offset strips lands every
    # box half a patch off on the shifted ones (issue #48). So:
    #   * a clean strip uses its OWN run centres (they already carry its offset);
    #   * a strip whose runs merged (patch == spacer colour, no clean set) falls
    #     back to a grid pooled from the *same-parity* clean strips, then to a
    #     global grid — preserving the robustness the pooled grid was added for.
    # Normal charts have all strips on one grid, so every parity grid coincides.
    import statistics

    clean_centres: list[list[float] | None] = [
        [(r0 + r1) / 2 for r0, r1 in r]
        if (r is not None and len(r) == steps) else None
        for r in strip_ranges
    ]
    _grid_for_strip = _per_strip_step_grids(clean_centres, steps)

    if _grid_for_strip is not None:
        all_clean = [r for r in strip_ranges if r is not None and len(r) == steps]
        box_half = statistics.median(
            r[k][1] - r[k][0] + 1 for r in all_clean for k in range(steps)) / 2
        step_cy = _grid_for_strip(0)   # representative grid (mid-y scan + range check)
    else:
        # No strip yielded a clean run set — the B&W twin is unusable (e.g. it
        # paginated differently from the deliverable, so its page doesn't line
        # up patch-for-patch). Don't divide from y_top: that band starts at the
        # label row and includes the white leader, which would push step 0 up
        # into the page margin (the "highlight floating above the chart" bug).
        # Anchor instead to the real patch block measured from the COLOURED
        # image: the first/last non-white pixel below the label band, median'd
        # across strips. printtarg tiles patches uniformly between those, so a
        # uniform divide of that range lands each step on its patch.
        tops, bots = [], []
        for s in range(n_strips):
            cx = int(x0 + (s + 0.5) * strip_w)
            colseg = a[y_top:y1 + 1, cx]
            nonwhite = np.where(~np.all(colseg > 245, axis=1))[0]
            if nonwhite.size:
                tops.append(y_top + int(nonwhite.min()))
                bots.append(y_top + int(nonwhite.max()))
        block_top = statistics.median(tops) if tops else y_top
        block_bot = statistics.median(bots) if bots else y1
        row_h = (block_bot - block_top + 1) / steps
        step_cy = [block_top + (k + 0.5) * row_h for k in range(steps)]
        box_half = row_h * 0.45

        def _grid_for_strip(within_strip: int) -> list[float]:
            return step_cy

    # Half-width of the highlight box, measured from the rendered image rather
    # than guessed. printtarg tiles strips uniformly and (for the common
    # no-vertical-spacer layout) patches fill the strip cell edge-to-edge, so
    # the old fixed 0.75 shrink left a rim of the patch's own colour around the
    # highlight — read as a mismatch. Scan out from each strip centre at a
    # known patch-centre row to the nearest strong colour edge (the strip
    # boundary, or an inter-strip spacer's edge when the layout has one); the
    # median across strips is the true patch half-width. Where a neighbour
    # shares the colour (no detectable edge) it falls back to the cell
    # boundary. A small inset keeps adjacent highlighted patches visually
    # separate.
    mid_y = int(step_cy[len(step_cy) // 2]) if step_cy else int((y_top + y1) // 2)
    mid_y = max(0, min(mid_y, a.shape[0] - 1))
    grad = np.abs(np.diff(a[mid_y].astype(np.int16), axis=0)).sum(axis=1)
    cell_half = strip_w / 2
    half_ws: list[float] = []
    for s in range(n_strips):
        cx = int(x0 + (s + 0.5) * strip_w)
        lo = max(int(x0 + s * strip_w), 0)
        hi = min(int(x0 + (s + 1) * strip_w), grad.size)
        left = next((cx - x for x in range(cx - 1, lo - 1, -1) if grad[x] > 60),
                    cell_half)
        right = next((x - cx for x in range(cx + 1, hi) if grad[x] > 60),
                     cell_half)
        half_ws.append(min(left, right))
    half_w = (statistics.median(half_ws) if half_ws else cell_half) * 0.97

    geom: dict[int, tuple[int, int, int, int]] = {}
    for line in dm.group(1).splitlines():
        toks = _split_cgats(line)
        if len(toks) <= max(id_i, loc_i):
            continue
        try:
            sid = int(toks[id_i])
        except ValueError:
            continue
        # printtarg pads a partial last strip with white patches whose
        # SAMPLE_ID is 0 — they don't correspond to anything the user
        # placed, so skip them (they'd also collide on the key).
        if sid <= 0:
            continue
        loc = toks[loc_i].strip('"')
        m = _LOC_RE.match(loc)
        if not m:
            continue
        strip_idx = letter_to_idx(m.group(1))
        step_idx = int(m.group(2)) - 1
        if not (strips_before <= strip_idx < strips_before + n_strips):
            continue
        within_strip = strip_idx - strips_before
        cx = x0 + (within_strip + 0.5) * strip_w
        # Per-strip y-grid so the -h zig-zag (alternate strips offset half a
        # patch) lands on the right row; falls back to the shared grid (#48).
        strip_cy = _grid_for_strip(within_strip)
        if 0 <= step_idx < len(strip_cy):
            cy = strip_cy[step_idx]
        else:
            continue   # step out of the resolved grid — skip rather than guess
        geom[sid] = (int(cx - half_w), int(cy - box_half),
                     int(cx + half_w), int(cy + box_half))
    return geom
