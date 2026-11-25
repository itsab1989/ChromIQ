"""THE PRINTED SHEETS OF AN i1iO CHART WHOSE PAGES ARE PIECES OF LARGER SHEETS.

The chart is its pieces (its page images, its ``.ti2``, its side file). What is
printed is the whole sheet: the piece images set on it as the chart's record
says (`pieces.Plan`), turned in whole quarter turns and at whole pixels, so no
pixel of a patch is resampled, with the cut lines between them. The sheet
images live in ``exports/`` (`core.file_manager.I1ioSheetFiles`), carry every
tag of a page image, and are built again whenever they do not fit the pages
they were built from (`ensure`): a printed sheet is never an unchecked one.

The sheet is put together on disk, one piece in memory at a time.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.file_manager import I1ioSheetFiles, write_json_atomically
from core.logger import get_logger
from core.stem_paths import without_ext
from workflow.overhang import writes_chart_pages

from . import pieces

log = get_logger(__name__)

#: The cut line: a solid quarter millimetre of 40 % black, from paper edge to
#: paper edge, on every edge of a piece inside the sheet. Thin and grey: seen
#: by a person with a knife, and never a row's or a mark's ink.
CUT_LINE_MM = 0.25
CUT_LINE_BLACK = 0.40
#: What every sheet image says of itself (TIFF tag Software): only a file that
#: says so is ChromIQ's, whatever its name.
MARK = "ChromIQ i1iO sheet of pieces"
#: Free space asked for over what a sheet needs while it is put together.
ROOM_TO_SPARE = 50_000_000
#: The sheet is written in strips of this many rows.
ROWS_PER_STRIP = 256
RECORD_SCHEMA = 1


class SheetsUnavailable(RuntimeError):
    """The sheets cannot be built: a piece's page image is not there, or it
    does not fit the chart's record (the reason is in the message, English,
    for the log)."""


#: What printing one sheet takes, per pixel: measured on A3 and A2 sheets at
#: 600 and 1200 dpi (the PostScript or PDF of a page: 8 bytes for RGB 8 bit, 21
#: for 16 bit, 11 and 28 for CMYK; its preview 8 to 11), rounded up.
BYTES_PER_PX_MIN = 12.0
BYTES_PER_INK_8 = 4.0
BYTES_PER_INK_16 = 7.5


#: What drawing the pieces took, over the page budget's own estimate: at most
#: 1.15 (CMYK on A3 and A2 at 600 dpi: 3.9 and 5.3 GB measured, 3.4 and 4.9
#: estimated), RGB less than the estimate.
DRAW_MARGIN = 1.2


def drawing_problem(w_px: int, h_px: int, n: int, *, early: bool = False,
                    **kind) -> "str | None":
    """Why *n* pieces of *w_px* x *h_px* take too much memory to draw, in
    words, else None. *early*: before anything ran."""
    from workflow.page_output import support as po
    need = DRAW_MARGIN * po.estimated_bytes(w_px, h_px, n, **kind)
    if need <= po.MEMORY_BUDGET_BYTES:
        return None
    from core.i18n import count_phrase, tr
    from workflow import measurement_messages as mm
    return (tr(mm._I1IO_PIECES_OVER_BUDGET).format(
        pieces=count_phrase(n, tr("1 piece"), tr("{n} pieces")),
        w=po.number(w_px), h=po.number(h_px),
        mpx=po.number(w_px * h_px / 1e6), gb=po.decimal(need / 1e9),
        limit=po.number(po.MEMORY_BUDGET_BYTES / 1e9))
        + " " + tr(mm._PAGE_NOTHING_WRITTEN if early else mm._PAGE_NOT_DRAWN))


def budget_problem(plan: pieces.Plan, dpi: float, *, inks: int = 3,
                   device: bool = False, bit16: bool = False,
                   early: bool = False) -> "str | None":
    """Why a sheet of *plan* at *dpi* is too large to print (the memory budget
    every page keeps to), in words, else None. *early*: before anything ran."""
    from workflow.page_output import support as po
    w, h = (po.pixels_of(v, dpi) for v in plan.sheet_mm)
    n = max(4 if device else 3, int(inks or 3))
    need = w * h * max(BYTES_PER_PX_MIN,
                       n * (BYTES_PER_INK_16 if bit16 else BYTES_PER_INK_8))
    if need <= po.MEMORY_BUDGET_BYTES:
        return None
    from core.i18n import tr
    from workflow import measurement_messages as mm
    return (tr(mm._I1IO_SHEET_OVER_BUDGET).format(
        w=po.number(w), h=po.number(h), mpx=po.number(w * h / 1e6),
        gb=po.decimal(need / 1e9),
        limit=po.number(po.MEMORY_BUDGET_BYTES / 1e9))
        + " " + tr(mm._PAGE_NOTHING_WRITTEN if early else mm._PAGE_NOT_DRAWN))


class NoRoom(SheetsUnavailable):
    """Not enough free space to put the sheets together."""

    def __init__(self, need: float, free: float):
        super().__init__(f"{need / 1e6:.0f} MB needed, {free / 1e6:.0f} MB free")
        self.need, self.free = need, free


@dataclass(frozen=True)
class SheetInfo:
    """What is known of a divided chart: its plan, its pages, its files, and
    how many pages its side file says it has (None: not known)."""
    ti2: Path
    plan: pieces.Plan
    pages: "tuple[Path, ...]"
    files: I1ioSheetFiles
    expected: "int | None" = None

    @property
    def sheets(self) -> int:
        return -(-len(self.pages) // self.plan.count)

    @property
    def sheet_files(self) -> "list[Path]":
        """The sheet images, under the names their record gives them."""
        other: "dict[int, int]" = {}
        try:
            for e in _record(self.files)["sheets"]:
                other[int(e["sheet"])] = int(e.get("other") or 0)
        except (KeyError, TypeError, ValueError):
            pass
        return [self.files.sheet(k + 1, other.get(k + 1, 0))
                for k in range(self.sheets)]

    def pages_of(self, sheet: int) -> "list[tuple[int, int]]":
        """``[(page, place)]``, 0-based, on sheet *sheet* (0-based)."""
        first = sheet * self.plan.count
        return [(first + k, k) for k in range(self.plan.count)
                if first + k < len(self.pages)]


def _record(files: I1ioSheetFiles) -> dict:
    """The sheets' record as it is on disk, {} without one."""
    try:
        doc = json.loads(files.record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def page_images(ti2, pages: "int | None" = None) -> "list[Path]":
    """The chart's page images that are there, in page order. *pages*: how
    many the chart's record says it has, which names them (``<stem>.tif`` for
    one, else ``<stem>_01.tif`` ...: any other file is nobody's page);
    without it, what is found."""
    stem = without_ext(ti2, ".ti2")
    one = stem.with_name(stem.name + ".tif")

    def nth(k: int) -> Path:
        return stem.with_name(f"{stem.name}_{k:02d}.tif")
    if pages == 1:
        return [one] if one.is_file() else []
    if pages is not None:
        return [nth(k) for k in range(1, pages + 1) if nth(k).is_file()]
    if one.is_file():
        return [one]
    out = []
    while nth(len(out) + 1).is_file():
        out.append(nth(len(out) + 1))
    return out


def chart_of_pages(pages) -> "Path | None":
    """The ``.ti2`` of the chart whose page images *pages* are (``<stem>.tif``
    or ``<stem>_NN.tif`` beside it), None when there is none."""
    try:
        page = Path(list(pages)[0])
    except (TypeError, IndexError):
        return None
    m = re.fullmatch(r"(.+)_\d{2,}", page.stem)
    for stem in ([m.group(1)] if m else []) + [page.stem]:
        ti2 = page.with_name(stem + ".ti2")
        if ti2.is_file():
            return ti2
    return None


def info(ti2) -> "SheetInfo | None":
    """What is known of the chart *ti2* when its pages are pieces of larger
    sheets, else None; `SheetsUnavailable` when its record cannot be trusted
    (`pieces.record_of`)."""
    try:
        plan = pieces.record_of(ti2)
    except pieces.PieceRecordError as exc:
        raise SheetsUnavailable(f"the pieces' record: {exc}") from exc
    if plan is None:
        return None
    n = None
    try:
        stem = without_ext(ti2, ".ti2")
        n = len(json.loads(stem.with_name(stem.name + ".i1io.json").read_text(
            encoding="utf-8"))["pages"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return SheetInfo(Path(ti2), plan, tuple(page_images(ti2, n)),
                     I1ioSheetFiles.for_chart(ti2), n)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fits(si: SheetInfo) -> bool:
    """Whether the sheet images on disk are the ones of these pages: every
    file there, its own checksum and those of its pages as recorded."""
    try:
        rec = _record(si.files)
        if si.expected not in (None, len(si.pages)):
            return False
        if rec.get("schema") != RECORD_SCHEMA or rec.get("token") != \
                si.plan.token or len(rec.get("sheets") or ()) != si.sheets:
            return False
        for k, f in enumerate(si.sheet_files):
            if not f.is_file() or _sha(f) != rec["sheets"][k]["sha256"]:
                return False
        return [_sha(p) for p in si.pages] == rec["pages_sha256"]
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _page_tags(path: Path) -> dict:
    """What a sheet takes over from its pages: the writer's arguments that
    describe the pixels (`raster.save_tiffs` / `save_separated_tiffs`)."""
    import tifffile
    with tifffile.TiffFile(str(path)) as tif:
        page = tif.pages[0]
        tags = page.tags

        def val(code):
            t = tags.get(code)
            return t.value if t is not None else None
        res = val(282)
        out = {"shape": page.shape, "dtype": page.dtype,
               "photometric": int(page.photometric),
               "compression": int(page.compression),
               "resolution": (tuple(res) if isinstance(res, tuple) else res),
               "resolutionunit": int(val(296) or 2),
               "ink_names": val(333), "inkset": val(332),
               "number_of_inks": val(334), "orientation": val(274),
               "icc": val(34675)}
    return out


def _write_args(tags: dict) -> dict:
    import tifffile
    res = tags["resolution"]
    if isinstance(res, tuple):
        res = res[0] / res[1]
    kw: dict = {"photometric": tags["photometric"],
                "resolution": (res, res),
                "resolutionunit": tags["resolutionunit"],
                "software": MARK,
                "compression": (None if tags["compression"] == 1
                                else tifffile.COMPRESSION(
                                    tags["compression"]).name.lower()),
                "rowsperstrip": ROWS_PER_STRIP}
    extra = []
    if tags["orientation"]:
        extra.append((274, "H", 1, int(tags["orientation"]), True))
    if tags["number_of_inks"]:
        extra.append((334, "H", 1, int(tags["number_of_inks"]), True))
    names = tags["ink_names"]
    if names:
        text = names if isinstance(names, str) else "\0".join(names)
        if not text.endswith("\0"):
            text += "\0"
        extra.append((333, "s", 0, text, True))
    if tags["inkset"]:
        extra.append((332, "H", 1, int(tags["inkset"]), True))
    if tags["icc"]:
        kw["iccprofile"] = bytes(tags["icc"])
    if extra:
        kw["extratags"] = extra
    return kw


def _black_of(tags: dict, dtype, n: int):
    """The pixel of a cut line, and the paper, in the page's own values."""
    import numpy as np
    top = np.iinfo(dtype).max
    if tags["photometric"] == 2:                              # RGB
        grey = int(round(top * (1.0 - CUT_LINE_BLACK)))
        return np.full(n, grey, dtype), np.full(n, top, dtype)
    paper = np.zeros(n, dtype)
    line = np.zeros(n, dtype)
    names = tags["ink_names"]
    names = [v.lower() for v in (names.split("\0") if isinstance(names, str)
                                 else names or ()) if v]
    value = int(round(top * CUT_LINE_BLACK))
    if "black" in names[:n]:
        line[names.index("black")] = value
    else:
        # no black ink (CMY with its empty fourth channel, other sets): the
        # same share of each of the first three, a grey
        line[:min(3, n)] = value
    return line, paper


def _turned(arr, turn: int):
    """A page's pixels as they lie on the sheet (whole quarter turns
    clockwise: no pixel changes)."""
    import numpy as np
    return np.rot90(arr, -turn) if turn else arr


def compose(si: SheetInfo) -> "list[Path]":
    """Build every sheet of *si* and its record; returns the files. Raises
    `SheetsUnavailable` (`NoRoom`) or OSError, and then no sheet of this
    chart is left that could be printed."""
    tidy(si.files)
    forget(si.files)
    try:
        return _compose(si)
    except BaseException:
        tidy(si.files)
        forget(si.files)
        raise


def _space_needed(si: SheetInfo, per_sheet: int) -> int:
    """What putting the sheets together takes on the disk: the sheet itself
    while it is built, and the images (the pages' own size, and half more)."""
    sizes = sum(p.stat().st_size for p in si.pages)
    return int(per_sheet + 1.5 * sizes + ROOM_TO_SPARE)


def _free_name(files: I1ioSheetFiles, number: int) -> "tuple[Path, int]":
    """The name of sheet *number*, and which of its names that is: the first
    one nobody else's file has."""
    other = 0
    while files.sheet(number, other).exists():
        other += 1
    return files.sheet(number, other), other


@writes_chart_pages
def _compose(si: SheetInfo) -> "list[Path]":
    import numpy as np
    import tifffile
    if not si.pages or si.expected not in (None, len(si.pages)):
        raise SheetsUnavailable(
            f"{len(si.pages)} of {si.expected} page images are there")
    first = _page_tags(si.pages[0])
    dtype = np.dtype(first["dtype"])
    shape = first["shape"]
    n = shape[2] if len(shape) == 3 else 1
    res = first["resolution"]
    res = res[0] / res[1] if isinstance(res, tuple) else float(res)
    per_mm = res / (10.0 if first["resolutionunit"] == 3 else 25.4)

    def px(mm: float) -> int:
        return int(round(mm * per_mm))
    W, H = px(si.plan.sheet_mm[0]), px(si.plan.sheet_mm[1])
    if abs(shape[1] - px(si.plan.piece_mm[0])) > 1 \
            or abs(shape[0] - px(si.plan.piece_mm[1])) > 1:
        raise SheetsUnavailable("a page image is not the size of a piece")
    line, paper = _black_of(first, dtype, n)
    si.files.folder.mkdir(parents=True, exist_ok=True)
    raw_size = W * H * n * dtype.itemsize
    need = _space_needed(si, raw_size)
    free = shutil.disk_usage(si.files.folder).free
    if free < need:
        raise NoRoom(need, free)
    out, record = [], []
    for k in range(si.sheets):
        target, other = _free_name(si.files, k + 1)
        fd, raw = tempfile.mkstemp(prefix="chromiq-sheet-", suffix=".raw",
                                   dir=si.files.folder)
        part = target.with_name(target.name + ".part")
        # WHAT IS BEING WORKED ON IS RECORDED FIRST: a run that is killed
        # leaves these two, and the next one removes them by these names
        sheet = None
        try:
            try:
                write_json_atomically(si.files.record, {
                    "schema": RECORD_SCHEMA,
                    "working": [Path(raw).name, part.name]})
                if hasattr(os, "posix_fallocate"):
                    os.posix_fallocate(fd, 0, raw_size)    # (no sparse file)
            finally:
                os.close(fd)
            sheet = np.memmap(raw, dtype=dtype, mode="r+", shape=(H, W, n)) \
                if Path(raw).stat().st_size == raw_size else \
                np.memmap(raw, dtype=dtype, mode="w+", shape=(H, W, n))
            for y in range(0, H, 512):
                sheet[y:y + 512] = paper
            for page, place in si.pages_of(k):
                arr = tifffile.imread(str(si.pages[page]))
                if arr.ndim == 2:
                    arr = arr[:, :, None]
                if arr.shape != (shape[0], shape[1], n) or arr.dtype != dtype:
                    raise SheetsUnavailable("the page images differ")
                arr = _turned(arr, si.plan.turn)
                x0, y0 = (px(v) for v in si.plan.places[place])
                h = min(arr.shape[0], H - y0)
                w = min(arr.shape[1], W - x0)
                sheet[y0:y0 + h, x0:x0 + w] = arr[:h, :w]
                del arr
            t = max(1, px(CUT_LINE_MM))
            for x in si.plan.cut_x:
                a = px(x) - t // 2
                sheet[:, max(0, a):a + t] = line
            for y in si.plan.cut_y:
                a = px(y) - t // 2
                sheet[max(0, a):a + t] = line
            sheet.flush()
            kw = _write_args(first)
            tifffile.imwrite(str(part), sheet if n > 1 else sheet[:, :, 0],
                             maxworkers=1, **kw)
            os.replace(part, target)
        finally:
            if sheet is not None:
                sheet._mmap.close()           # (or Windows keeps the file)
            del sheet
            for f in (Path(raw), part):
                try:
                    f.unlink()
                except OSError:
                    pass
        out.append(target)
        record.append({"sheet": k + 1, "sha256": _sha(target),
                       **({"other": other} if other else {}),
                       "pages": [p + 1 for p, _pl in si.pages_of(k)]})
    write_json_atomically(si.files.record, {
        "schema": RECORD_SCHEMA, "token": si.plan.token,
        "sheets": record, "pages_sha256": [_sha(p) for p in si.pages]})
    log.info("i1iO sheets: %d of %s built from %d pieces", len(out),
             "x".join(f"{v:g}" for v in si.plan.sheet_mm), len(si.pages))
    return out


def tidy(files: I1ioSheetFiles) -> None:
    """Remove what a killed run was working on: the two names its record
    gives, and nothing that only looks like them."""
    names = _record(files).get("working")
    for name in names if isinstance(names, list) else ():
        if isinstance(name, str) and name == Path(name).name and (
                re.fullmatch(r"chromiq-sheet-\w+\.raw", name)
                or name.startswith(f"{files.stem}-sheet_")
                and name.endswith(".tif.part")):
            try:
                (files.folder / name).unlink()
            except OSError:
                pass


def is_ours(path: Path) -> bool:
    """Whether the image at *path* is a sheet ChromIQ put together (`MARK`)."""
    import tifffile
    try:
        with tifffile.TiffFile(str(path)) as tif:
            tag = tif.pages[0].tags.get(305)
            return tag is not None and str(tag.value) == MARK
    except Exception:      # noqa: BLE001 - not an image of ours
        return False


def forget(files: I1ioSheetFiles) -> None:
    """Remove a chart's sheet images and their record (they are derived):
    the files of its sheets' names that ChromIQ put together. A file of
    somebody else's under such a name stays."""
    try:
        found = [p for p in files.folder.iterdir() if re.fullmatch(
            re.escape(files.stem) + r"-sheet_\d{2,}(-\d+)?\.tif", p.name)]
    except OSError:
        found = []
    for f in found:
        if is_ours(f):
            try:
                f.unlink()
            except OSError:
                pass
    try:
        files.record.unlink()
    except OSError:
        pass


def forget_of(ti2) -> None:
    """`forget` the sheets of the chart *ti2*, also without their record."""
    files = I1ioSheetFiles.for_chart(ti2)
    if files.folder.is_dir():
        tidy(files)
        forget(files)


def ensure(ti2) -> "list[Path]":
    """The printed sheets of the chart *ti2*, built when they are not there or
    do not fit its pages; [] for a chart whose pages are printed as they are.
    Raises `SheetsUnavailable` or OSError when they cannot be built: then no
    old sheet of this chart is left either."""
    try:
        si = info(ti2)
    except SheetsUnavailable:
        forget_of(ti2)
        raise
    if si is None:
        return []
    if not fits(si):
        return compose(si)
    return si.sheet_files
