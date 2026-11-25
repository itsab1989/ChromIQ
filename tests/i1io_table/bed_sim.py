"""BedSim: THE SIMULATED TABLE READS WHAT LIES ON IT (test and driver support, not shipped).

The simulated readers of ``reader_sim`` / ``part_c_sim`` give every place of the table a colour of
its own, which can show that the arm stands right and never that the SHEET does: a wrong piece, a
piece a row off, another chart or an uncut sheet all read "right" there. Here the bed holds a
PRINTED IMAGE (a page or sheet TIFF, or a cut of one) at a TRUE POSE (where its corner lies, how
far it is shifted and turned), and every reading, strip and patch by patch, is that image seen
through the instrument's 4.5 mm opening at the sheet point under the opening, from the arm's own
position. The readings never come from the chart's ``.ti2`` or side file: the helper's own copy of
the ``.ti2`` gives it the patch names to answer with, as the real helper's does, and nothing else.

    laid = Laid.from_tiff(run.dir / "chart.tif")      # what was printed
    bed = Bed(laid, shift_mm=(11.0, 0.0))             # where it lies (here one pitch off)
    job, sim, helper, run = bed_job(tmp_path, chart, bed)

Spectra come from the image's colours by a fixed smooth model (three lobes over the paper); noise
is a gain per reading and the strip reader's own per-band noise, as ``placement_synth`` sizes it.
Not modelled: the sweep during one 5 ms reading (0.3 to 0.4 mm at the chart's speeds), paper
gloss, fluorescence. Off the sheet the bed reads BED (a grey), at rest the white tile unless
paper lies over it.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from tests.i1io_table import reader_sim as RS

APERTURE_MM = 4.5
#: The table's surface under the opening where no paper lies (our invention: a mid grey).
BED = [0.25] * 36
PAPER_R = 0.88
BLACK_R = 0.03
#: Where the sheet's corner (the top left as it lies: page (0, height)) is put on the table.
ORIGIN = (1650.0, 700.0)
WL = [380 + 10 * j for j in range(36)]


def _lobes() -> np.ndarray:
    w = np.array(WL, float)

    def sig(x):
        return 1.0 / (1.0 + np.exp(-x))
    b = 1.0 - sig((w - 495.0) / 14.0)
    r = sig((w - 585.0) / 14.0)
    return np.stack([r, 1.0 - b - r, b])          # R, G, B over the bands


LOBES = _lobes()


def spectrum_of(linear_rgb) -> "list[float]":
    """The smooth model: linear display RGB (0..1) to reflectance per band."""
    v = np.asarray(linear_rgb, float)
    return [float(x) for x in BLACK_R + (PAPER_R - BLACK_R) * (v @ LOBES)]


def _linear(rgb8: np.ndarray) -> np.ndarray:
    c = rgb8.astype(np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _circle(step: float = 0.2) -> np.ndarray:
    r = APERTURE_MM / 2.0
    g = np.arange(-r + step / 2, r, step)
    x, y = np.meshgrid(g, g)
    keep = x * x + y * y <= r * r
    return np.stack([x[keep], y[keep]], axis=1)


CIRCLE = _circle()


@dataclass
class Laid:
    """A printed image: *pixels* (H x W x 3, 8 bit) of *w* x *h* mm, as printed (portrait)."""
    pixels: np.ndarray
    w: float
    h: float

    def __post_init__(self):
        self._lut = _linear(np.arange(256, dtype=np.uint8))
        self.sx = self.pixels.shape[1] / self.w
        self.sy = self.pixels.shape[0] / self.h

    @classmethod
    def from_tiff(cls, path, size_mm=None, frame: int = 0) -> "Laid":
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            im.seek(frame)
            dpi = im.info.get("dpi") or (150.0, 150.0)
            px = np.asarray(im.convert("RGB"))
        if size_mm is None:
            size_mm = (px.shape[1] / float(dpi[0]) * 25.4, px.shape[0] / float(dpi[1]) * 25.4)
        return cls(px, float(size_mm[0]), float(size_mm[1]))

    def cut(self, x0: float, y0: float, x1: float, y1: float) -> "Laid":
        """The piece between two corners (mm on this image), cut out of it."""
        a, b = int(round(x0 * self.sx)), int(round(x1 * self.sx))
        c, d = int(round(y0 * self.sy)), int(round(y1 * self.sy))
        return Laid(self.pixels[c:d, a:b], x1 - x0, y1 - y0)

    def turned(self, quarter_turns_clockwise: int = 1) -> "Laid":
        k = int(quarter_turns_clockwise) % 4
        px = np.rot90(self.pixels, -k)
        w, h = (self.h, self.w) if k % 2 else (self.w, self.h)
        return Laid(px, w, h)

    def seen(self, px: float, py: float) -> "np.ndarray | None":
        """The mean linear colour under the opening at page point (mm); None off the sheet. The
        part of the opening over the edge sees the bed."""
        pts = CIRCLE + (px, py)
        on = ((pts[:, 0] >= 0) & (pts[:, 0] < self.w) & (pts[:, 1] >= 0) & (pts[:, 1] < self.h))
        if not on.any():
            return None
        ix = np.clip((pts[on, 0] * self.sx).astype(int), 0, self.pixels.shape[1] - 1)
        iy = np.clip((pts[on, 1] * self.sy).astype(int), 0, self.pixels.shape[0] - 1)
        col = self._lut[self.pixels[iy, ix]].mean(axis=0)
        f = float(on.mean())
        if f < 1.0:
            col = f * col + (1 - f) * np.full(3, (BED[0] - BLACK_R) / (PAPER_R - BLACK_R))
        return col


@dataclass
class Bed:
    """*laid* on the table: its top left corner AS IT LIES (the page's bottom left, the sheet a
    quarter turn clockwise) at *origin* (table units), moved by *shift_mm* (along the table's
    left-to-right, towards the front) and turned by *turn_deg* about the sheet's middle."""
    laid: Laid
    origin: "tuple[float, float]" = ORIGIN
    shift_mm: "tuple[float, float]" = (0.0, 0.0)
    turn_deg: float = 0.0
    noise: float = 1.0
    rng: random.Random = field(default_factory=lambda: random.Random(20261125))

    def _lie(self, u, v):
        """As-it-lies mm (u to the right, v to the front) with the true shift and turn."""
        cu, cv = self.laid.h / 2.0, self.laid.w / 2.0
        a = math.radians(self.turn_deg)
        du, dv = u - cu, v - cv
        return (cu + du * math.cos(a) - dv * math.sin(a) + self.shift_mm[0],
                cv + du * math.sin(a) + dv * math.cos(a) + self.shift_mm[1])

    def table_of(self, page_mm) -> "tuple[float, float]":
        """A printed point (page mm) as the table's units, where it truly lies."""
        u, v = self._lie(self.laid.h - float(page_mm[1]), float(page_mm[0]))
        return (self.origin[0] - 10.0 * u, self.origin[1] + 10.0 * v)

    def page_of(self, x: float, y: float) -> "tuple[float, float]":
        """The printed point (page mm) under table point (x, y)."""
        u = (self.origin[0] - x) / 10.0 - self.shift_mm[0]
        v = (y - self.origin[1]) / 10.0 - self.shift_mm[1]
        cu, cv = self.laid.h / 2.0, self.laid.w / 2.0
        a = -math.radians(self.turn_deg)
        du, dv = u - cu, v - cv
        u, v = (cu + du * math.cos(a) - dv * math.sin(a),
                cv + du * math.sin(a) + dv * math.cos(a))
        return (v, self.laid.h - u)

    def true_spectrum(self, x: float, y: float) -> "list[float]":
        col = self.laid.seen(*self.page_of(x, y))
        if col is not None:
            return spectrum_of(col)
        return [RS.REST_TILE] * 36 if y < 300 else list(BED)

    def read(self, x: float, y: float) -> "list[float]":
        """One reading at the arm's place (x, y): the sheet seen through the opening, with the
        noise's gain."""
        g = 1.0 + self.noise * self.rng.gauss(0.0, 0.002)
        return [max(0.001, v * g) for v in self.true_spectrum(x, y)]

    def aims(self, sheet: dict, page: int = 0) -> "list[tuple[int, int]]":
        """Where the person puts the sight: on the marks (or corner patches) that the chart on
        the screen names, at the places they have ON THIS BED. The person trusts the sheet: a
        wrong sheet of the same grid is aimed at the same places."""
        from workflow.i1io.table import scan as sc
        out = []
        for a in sc.aims_of(sheet, page):
            x, y = self.table_of(a["page_mm"])
            out.append((int(round(x)), int(round(y))))
        return out


def xyz_of(spec) -> "list[float]":
    """D50 XYZ (0..100) of a reflectance spectrum (the project's own weights)."""
    from workflow.dual_scan.colour import _weights
    W, M = _weights()
    v = (np.atleast_2d(np.asarray(spec, float)) @ M.T) @ W.T
    return [float(a) for a in v[0]]


class BedHelper(RS.HelperSim):
    """``reader_sim.HelperSim`` whose readers see the bed, never the chart's files."""
    bed: "Bed | None" = None

    def proc_class(self):
        base = super().proc_class()
        helper = self

        class _P(base):
            def _xyz_here(self):
                spec = helper.bed.read(*helper.sim.pos)
                return [round(v, 4) for v in xyz_of(spec)], [100 * v for v in spec]
        return _P

    def colour_at(self, x: float, y: float) -> "list[float]":
        return self.bed.read(x, y)


# ---- a real chart in a run, and the job on it ------------------------------------------------

def patch_set(n: int, seed: int = 7) -> "list[tuple[float, float, float]]":
    """*n* device colours (0..100): random, with white, black and a grey ladder among them."""
    rnd = random.Random(seed)
    out = [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)]
    out += [(v, v, v) for v in (12.0, 25.0, 38.0, 50.0, 62.0, 75.0, 88.0)]
    while len(out) < n:
        out.append(tuple(round(rnd.uniform(0, 100), 3) for _ in range(3)))
    return out[:n]


def expected_xyz(rgb) -> "tuple[float, float, float]":
    """What a characterised printer would lay down (the bed's own model, no noise): the XYZ a
    ``.ti1`` made with a preliminary profile carries."""
    lin = _linear(np.round(np.array(rgb, float) / 100.0 * 255.0).astype(np.uint8))
    return tuple(xyz_of(spectrum_of(lin)))


def write_ti1(path: Path, colours, xyz=expected_xyz) -> Path:
    rows = []
    for i, c in enumerate(colours, 1):
        x = xyz(c) if callable(xyz) else xyz
        rows.append(f"{i} " + " ".join(f"{v:.4f}" for v in c) + " "
                    + " ".join(f"{v:.5f}" for v in x))
    path.write_text(
        'CTI1\n\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        'APPROX_WHITE_POINT "84.8 88.0 72.6"\nCOLOR_REP "RGB"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


@dataclass
class Chart:
    run: object
    sheet: dict
    tiffs: "list[Path]"
    colours: "list[tuple]"

    def laid(self, page: int = 0) -> Laid:
        return Laid.from_tiff(self.tiffs[page], tuple(self.sheet["paper_mm"]))


def build_chart(tmp_path, *, name="Bed-Target", count=None, paper="A4", colours=None, seed=3,
                xyz=expected_xyz, dpi=150, **kw) -> Chart:
    """A real i1iO chart, built by the layout engine into a run folder (the Beta on
    for the build)."""
    import json

    from core.file_manager import Project
    from workflow.i1io import support
    from workflow.layout_engine import chart as le
    run = Project.create(Path(tmp_path) / name, name).current_run()
    run.ensure_dir()
    stem = run.chart_ti2.name[:-4]
    colours = colours if colours is not None else patch_set(count or 96)
    ti1 = write_ti1(run.dir / f"{stem}.ti1", colours, xyz)
    was = support.i1io_enabled()
    support.set_enabled_for_this_process(True)
    try:
        res = le.build_chart(ti1, run.dir / stem, instrument="IO2", paper=paper, seed=seed,
                             dpi=dpi, project=name, chart_date="2026-01-01", **kw)
    finally:
        support.set_enabled_for_this_process(was)
    sheet = json.loads((run.dir / f"{stem}.i1io.json").read_text(encoding="utf-8"))
    return Chart(run, sheet, list(res.tiff_paths), list(colours))


def bed_job(tmp_path, chart: Chart, bed: Bed, **kw):
    """(job, sim, helper, run): the table job on *chart* with *bed* lying on the simulated
    table; the person aims where the bed's marks are."""
    job, sim, helper, run = RS.make_reading_job(
        tmp_path, sheet=chart.sheet, aims=kw.pop("aims", None) or bed.aims(chart.sheet),
        run=kw.pop("run", None) or chart.run, helper_class=BedHelper, **kw)
    helper.bed = bed
    # what the window hands the job at START
    from workflow.i1io.expected import expected_lab
    job.expected_lab, job.expected_why = expected_lab(chart.run.chart_ti2)
    return job, sim, helper, run


def values_of(chart: Chart, page: int = 0) -> "dict[str, list[float]]":
    """``{location: the spectrum of that printed patch}``, read off the page image at the patch
    centres: the truth a right reading gives."""
    laid = chart.laid(page)
    out = {}
    for st in chart.sheet["pages"][page]["strips"]:
        for q in st["patches"]:
            out[q["loc"]] = spectrum_of(laid.seen(*q["centre_mm"]))
    return out


def bed_window_sim(chart: Chart, bed: Bed, **kw):
    """A ``window_sim.WindowSim`` whose table holds *bed*: the real panel, the real job, readings
    from what lies on the table. ``sim.bed.laid`` / ``.shift_mm`` may change while it runs (the
    person lays another sheet). The person aims at the nominal marks of the chart."""
    from tests.i1io_table import window_sim as WS

    class _Sim(WS.WindowSim):
        reads_the_sheet = True

        def factory(self, *a, **k):
            real, WS.RS.HelperSim = WS.RS.HelperSim, BedHelper
            try:
                job = super().factory(*a, **k)
            finally:
                WS.RS.HelperSim = real
            self.helper.bed = self.bed
            return job
    sim = _Sim(aims=Bed(chart.laid()).aims(chart.sheet), **kw)
    sim.bed = bed
    return sim


def with_preview(chart: Chart) -> Chart:
    """The chart's ``.channels.json`` as Create Chart writes it (the Measure tab's preview reads
    its patch boxes there)."""
    import json
    stem = chart.run.chart_ti2.name[:-4]
    strips = chart.run.dir / f"{stem}.strips.json"
    layout = json.loads(strips.read_text(encoding="utf-8"))
    layout.update(engine="chromiq", engine_version=1, seed=3, color_rep="RGB")
    (chart.run.dir / f"{stem}.channels.json").write_text(json.dumps(
        {"ink_channels": [], "layout": layout}), encoding="utf-8")
    return chart
