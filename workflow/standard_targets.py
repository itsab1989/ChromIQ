"""Discover the standard scanner-target ``.cht`` recognition files that ship
with ArgyllCMS (in ``<argyll>/ref/``), so ChromIQ can profile a scanner from a
target the user physically owns (Wolf Faust IT8, LaserSoft, ColorChecker, …)
without generating a chart (Knut #98, ask 2).

We rely on Argyll's own ``.cht`` set — Argyll is a hard dependency, the files
are validated, and bundling copies would only risk version skew. The colour
**reference** (``.cie`` / ``.txt``) is *not* here: it's specific to the user's
physical target batch and must come from the target's vendor.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger
from core.name_order import sort_names
from core.resource_path import resource_path
from core.text_io import read_text

log = get_logger(__name__)

# Friendly names for the well-known targets (filename stem → display). Anything
# not listed falls back to its stem. Ordered-priority list decides the combo
# order (most common scanner targets first).
_FRIENDLY: dict[str, str] = {
    "it8": "IT8.7/2 (generic)",
    "it8Wolf": "IT8 / ISO 12641-1 — Wolf Faust",
    "ISO12641_2_1": "IT8 / ISO 12641-2 — LaserSoft Advanced",
    # The three PAGES of the ISO 12641-2 three-page target set: identical
    # grid geometry, but each page carries different colours (columns 1–24 /
    # 25–48 / 49–72 in the reference) — all three are needed, one per sheet.
    # They are a SINGLE physical target, so ChromIQ folds them into one dropdown
    # entry (see MULTIPAGE_SETS) rather than three; these names are only used as
    # a fallback when a page is missing and the set can't be assembled.
    "ISO12641_2_3_1": "ISO 12641-2 (3-page set) — page 1",
    "ISO12641_2_3_2": "ISO 12641-2 (3-page set) — page 2",
    "ISO12641_2_3_3": "ISO 12641-2 (3-page set) — page 3",
    "LaserSoftDCPro": "LaserSoft DCPro",
    "ColorChecker": "X-Rite ColorChecker (24)",
    "ColorCheckerSG": "ColorChecker SG",
    "ColorCheckerDC": "ColorChecker DC",
    "ColorCheckerPassport": "ColorChecker Passport",
    "ColorCheckerHalfPassport": "ColorChecker Passport (half)",
    "SpyderChecker": "SpyderChecker",
    "SpyderChecker24": "SpyderChecker 24",
    "QPcard_201": "QPcard 201",
    "QPcard_202": "QPcard 202",
    "Hutchcolor": "HutchColor HCT",
    "i1_RGB_Scan_1.4": "i1 RGB Scan 1.4",
    "MLG": "MLG",
    "CMP_Digital_Target-4": "CMP Digital Target 4",
    "CMP_Digital_Target-7": "CMP Digital Target 7",
    "CMP_Digital_Target-2019": "CMP Digital Target 2019",
    "CMP_Digital_Target_Studio": "CMP Digital Target Studio",
    "CMP_DT_003": "CMP DT 003",
    "CMP_DT_mini": "CMP DT mini",
}

# Preferred display order — the common flatbed scanner targets on top.
_ORDER = [
    "it8Wolf", "it8", "ISO12641_2_1", "LaserSoftDCPro",
    "ColorChecker", "ColorCheckerSG", "ColorCheckerDC",
    "ColorCheckerPassport", "ColorCheckerHalfPassport",
    "SpyderChecker", "SpyderChecker24", "QPcard_201", "QPcard_202",
    "Hutchcolor", "i1_RGB_Scan_1.4",
]


# Standard targets that are physically ONE multi-page sheet set but ship as
# several ``.cht`` files, one per page. ChromIQ shows them as a single dropdown
# entry that then asks for one scan per page (each page's ``.cht`` is locked to
# its page), exactly like a multi-page ChromIQ chart — Knut's request, since the
# three ISO 12641-2 pages read against one shared reference and build one profile.
#   key -> (display name, (page-1 stem, page-2 stem, …))  in page order.
MULTIPAGE_SETS: dict[str, tuple[str, tuple[str, ...]]] = {
    "ISO12641_2_3": (
        "ISO 12641-2 (3-page set)",
        ("ISO12641_2_3_1", "ISO12641_2_3_2", "ISO12641_2_3_3"),
    ),
}


@dataclass(frozen=True)
class StandardTarget:
    """One selectable target in the "standard target I own" list — a single
    ``.cht`` sheet, or a multi-page set folded into one entry (:data:`MULTIPAGE_SETS`).

    ``cht_paths`` is one path for an ordinary target, or several (one per page)
    for a set; ``patch_counts`` is the patch total of each page, in the same
    order, used to annotate the dropdown name (Knut)."""
    key: str
    name: str                          # friendly name, WITHOUT the patch-count tail
    cht_paths: tuple[Path, ...]
    patch_counts: tuple[int, ...]

    @property
    def is_multipage(self) -> bool:
        return len(self.cht_paths) > 1

    @property
    def n_pages(self) -> int:
        return len(self.cht_paths)


def patch_count(cht: Path) -> int:
    """Number of patches described by a ``.cht`` (0 if it can't be parsed)."""
    from workflow.cht_parser import ChtParseError, parse_cht
    try:
        return len(parse_cht(read_text(cht, lenient=True)).patches)
    except (OSError, ChtParseError):
        return 0


def grouped_standard_targets(settings) -> list[StandardTarget]:
    """:func:`list_standard_targets`, with multi-page sets folded into a single
    :class:`StandardTarget` and every entry carrying its per-page patch counts.

    A set appears where its first page would have sorted; its individual pages
    are removed. If a set is incomplete (a page's ``.cht`` is missing), its
    available pages fall back to ordinary single entries so nothing vanishes."""
    raw = list_standard_targets(settings)
    by_stem: dict[str, Path] = {p.stem: p for _n, p in raw}
    stem_to_set: dict[str, str] = {
        stem: key for key, (_n, stems) in MULTIPAGE_SETS.items() for stem in stems}
    out: list[StandardTarget] = []
    emitted: set[str] = set()
    for name, p in raw:
        set_key = stem_to_set.get(p.stem)
        if set_key is None:
            out.append(StandardTarget(p.stem, name, (p,), (patch_count(p),)))
            continue
        if set_key in emitted:
            continue                       # a later page of an already-emitted set
        set_name, stems = MULTIPAGE_SETS[set_key]
        paths = [by_stem[s] for s in stems if s in by_stem]
        if len(paths) == len(stems):       # complete set → one folded entry
            out.append(StandardTarget(
                set_key, set_name, tuple(paths),
                tuple(patch_count(x) for x in paths)))
            emitted.add(set_key)
        else:                              # incomplete → keep this page standalone
            out.append(StandardTarget(p.stem, name, (p,), (patch_count(p),)))
    return out


def argyll_ref_dir(settings) -> Path | None:
    """The ArgyllCMS ``ref/`` folder for the configured ``bin`` dir, or None.

    Uses :func:`core.argyll_detect.resolve_ref_dir`, which follows Homebrew's
    symlinks so ``ref/`` is found even when ``bin`` is ``/opt/homebrew/bin``
    (its links point into the Cellar, where ``ref/`` really lives — Knut)."""
    from core.argyll_detect import resolve_ref_dir
    bin_path = settings.get("argyll_bin_path", "")
    if not bin_path:
        return None
    return resolve_ref_dir(bin_path)


def bundled_targets_dir() -> Path | None:
    """ChromIQ's bundled ``data/scanner_targets`` — Knut Larsson's corrected
    ``.cht`` files (see that folder's README). Preferred over Argyll's ``ref/``
    because several of Argyll's shipped files had wrong fiducial coordinates."""
    d = resource_path("data/scanner_targets")
    return d if d.is_dir() else None


def user_targets_dir(settings) -> Path:
    """The user-visible ``scanner-test-targets`` folder inside the ChromIQ
    output root (``~/ChromIQ`` or the custom output path). Holds a copy of
    every bundled target ``.cht`` so users can inspect or tweak them, plus the
    demo scans the "Try with a demo scan" button generates. A same-named
    ``.cht`` in here OVERRIDES the bundled one (Knut, beta.5) — that's how a
    user-modified recognition file takes effect."""
    custom = (settings.get("custom_output_path", "") or "") if settings else ""
    root = Path(custom) if custom else Path.home() / "ChromIQ"
    return root / "scanner-test-targets"


_USER_TARGETS_README = """\
About this folder (created by ChromIQ)

These are the recognition files (.cht) for the standard scanner/camera
targets ChromIQ knows, copied here so you can look at them — plus any demo
scans and references made by the "Try with a demo scan" button.

Want to tweak a target's patch geometry? Edit the .cht right here (or copy
your own over it, keeping the same file name). ChromIQ always prefers the
files in this folder over its built-in copies, so your version is what the
"Build profile with scanner or camera" tool actually uses.

Deleted something? No problem — ChromIQ puts a fresh copy of any missing
file back the next time you open the scanner tool. Your edited files are
never overwritten.
"""


def ensure_user_targets_dir(settings) -> Path | None:
    """Create/refresh the user ``scanner-test-targets`` folder: copy every
    bundled ``.cht`` (plus README/LICENSE and an explainer) that is missing,
    and refresh copies the user has NOT touched when a ChromIQ update ships a
    corrected file — a ``.provisioned.json`` manifest records the hash of what
    ChromIQ copied, so an unmodified copy is recognised and updated while an
    edited one is never overwritten (Knut, beta.5: updated files must reach
    users). Best-effort; returns the folder (None when nothing could be
    created)."""
    import hashlib
    import json
    import shutil

    def _sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    try:
        d = user_targets_dir(settings)
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        log.warning("could not create user targets folder: %s", exc)
        return None
    manifest_path = d / ".provisioned.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    bundled = bundled_targets_dir()
    if bundled is not None:
        for src in sorted(bundled.iterdir()):
            if not src.is_file():
                continue
            dst = d / src.name
            try:
                if not dst.exists():
                    shutil.copy2(src, dst)             # missing → (re)place
                    manifest[src.name] = _sha(src)
                    continue
                recorded = manifest.get(src.name)
                if recorded is None:
                    # Pre-manifest copy (or user-supplied file): adopt only a
                    # byte-identical file as "provisioned"; leave anything
                    # else alone — it may be a user's edit.
                    if _sha(dst) == _sha(src):
                        manifest[src.name] = _sha(src)
                    continue
                if _sha(dst) == recorded and recorded != _sha(src):
                    shutil.copy2(src, dst)             # untouched + update → refresh
                    manifest[src.name] = _sha(src)
            except OSError as exc:
                log.warning("could not provision %s: %s", src.name, exc)
    note = d / "About this folder.txt"
    if not note.exists():
        try:
            note.write_text(_USER_TARGETS_README, encoding="utf-8")
        except OSError:
            pass
    # WRITTEN ONLY WHEN IT CHANGED. This was unconditional, so merely LOOKING
    # at the standard targets rewrote the manifest - and because
    # `custom_output_path` defaults to "", which IS the owner's own ~/ChromIQ,
    # every gate run that happened to build a scanner window rewrote a file in
    # his real projects folder. It cost two agents a hunt apiece: one reported
    # it as an unexplained write it could not reproduce, and the suite's own
    # ~/ChromIQ guard then caught it intermittently, naming whichever test
    # happened to tear down next rather than the writer.
    #
    # Comparing before writing is the honest fix, and it is the right
    # behaviour regardless of the tests: nothing the user owns should have its
    # modification time moved by an operation that changed nothing in it.
    payload = json.dumps(manifest, indent=2, sort_keys=True)
    try:
        if not manifest_path.exists() or manifest_path.read_text(
                encoding="utf-8") != payload:
            manifest_path.write_text(payload, encoding="utf-8")
    except OSError:
        pass
    return d


def display_name(cht: Path) -> str:
    return _FRIENDLY.get(cht.stem, cht.stem)


def list_standard_targets(settings) -> list[tuple[str, Path]]:
    """``(display_name, cht_path)`` for every standard target ``.cht`` available,
    common flatbed targets first, then the rest alphabetically. Sources are
    ChromIQ's bundled corrected ``.cht`` (preferred) merged with the user's
    Argyll ``ref/`` (fallback), deduplicated by filename stem."""
    by_stem: dict[str, Path] = {}
    ref = argyll_ref_dir(settings)
    if ref is not None:
        by_stem.update({p.stem: p for p in ref.glob("*.cht")})
    bundled = bundled_targets_dir()
    if bundled is not None:                       # bundled corrected files win
        by_stem.update({p.stem: p for p in bundled.glob("*.cht")})
    # …and a user's copy in <output>/scanner-test-targets wins over everything:
    # that folder is exactly where a tweaked recognition file goes to take
    # effect (Knut, beta.5). Only stems the app already knows are overridden —
    # a stray demo/foreign .cht in the folder doesn't invent a new target.
    user_dir = user_targets_dir(settings)
    if user_dir.is_dir():
        by_stem.update({p.stem: p for p in user_dir.glob("*.cht")
                        if p.stem in by_stem})
    if not by_stem:
        return []
    ordered: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for stem in _ORDER:
        p = by_stem.get(stem)
        if p is not None:
            ordered.append((display_name(p), p))
            seen.add(stem)
    # The curated `_ORDER` comes first; everything else — including any .cht
    # the user drops in — follows in ChromIQ's one name order, not ASCII's.
    for stem in sort_names(by_stem):
        if stem not in seen:
            ordered.append((display_name(by_stem[stem]), by_stem[stem]))
    return ordered


def demo_patch_color(i: int, n: int) -> tuple[int, int, int]:
    """Colour for patch *i* of *n* in the demo scan. Deliberately spans dark→light
    with strongly-scrambled neighbours (golden-ratio hue + bit-reversed value), so
    that if the reading grid slips onto a neighbouring cell the colour it picks up
    is very different — turning the demo into a real misalignment detector rather
    than one that smooth gradients could hide (Knut). Deterministic."""
    import colorsys
    phi = 0.6180339887498949
    rev, f, k = 0.0, 0.5, i + 1                 # van der Corput (bit-reversal)
    while k > 0:
        rev += (k & 1) * f
        k >>= 1
        f *= 0.5
    h = (i * phi) % 1.0                          # consecutive hues far apart
    v = 0.16 + 0.80 * rev                        # wide, scrambled lightness
    s = 0.55 + 0.40 * ((i * phi * 2.0) % 1.0)
    return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(h, s, v))


def make_test_scan(cht_path, out_dir):
    """Render a known-good test scan (``.tif``) + reference (``.cie``) from a
    target's ``.cht``, so the reading grid can be tried without hardware. Each
    patch is a distinct solid colour; a correctly-placed grid reads them exactly.
    Returns ``(tif_path, cie_path)``."""
    from pathlib import Path as _P
    from PIL import Image
    from workflow.cht_parser import parse_cht
    cht_path = _P(cht_path); out_dir = _P(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    text = read_text(cht_path, lenient=True)
    boxes = parse_cht(text).patches
    minx = min(b.x1 for b in boxes); maxx = max(b.x2 for b in boxes)
    miny = min(b.y1 for b in boxes); maxy = max(b.y2 for b in boxes)
    scale = 1500.0 / max(maxx - minx, maxy - miny, 1.0); margin = 80
    W = int((maxx - minx) * scale + 2 * margin); H = int((maxy - miny) * scale + 2 * margin)
    from PIL import ImageDraw
    img = Image.new("RGB", (W, H), (236, 236, 236)); draw = ImageDraw.Draw(img)
    # Patches are painted at the .cht's own float geometry, each edge
    # rounded to the nearest pixel — shared edges round identically, so
    # adjacent cells stay contiguous with no seams. This is the SAME
    # geometry the marquee draws and the prepared scanin .cht carries
    # (#119, Knut's CMP Studio find: the old integer-edge repaint only
    # matched a grid whose corners were placed pixel-exactly; float
    # everywhere keeps all three views agreeing to within a pixel at any
    # placement).
    cie = ['CGATS.17', 'KEYWORD "SAMPLE_LOC"', 'NUMBER_OF_FIELDS 4', 'BEGIN_DATA_FORMAT',
           'SAMPLE_ID XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
           f'NUMBER_OF_SETS {len(boxes)}', 'BEGIN_DATA']
    for i, b in enumerate(boxes):
        r, g, bl = demo_patch_color(i, len(boxes))
        x0 = round((b.x1 - minx) * scale) + margin
        y0 = round((b.y1 - miny) * scale) + margin
        x1 = round((b.x2 - minx) * scale) + margin
        y1 = round((b.y2 - miny) * scale) + margin
        draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(r, g, bl))
        # Reference Y = the rendered colour's LUMINANCE (not the green channel):
        # the alignment check rank-compares read luminance against reference Y,
        # and the old pseudo-Y capped even a PERFECT demo read at ~0.93
        # agreement — Knut's stringent-floor test flagged flawless placements.
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * bl
        cie.append(f"{b.name} {r / 2.55 * 0.95:.3f} {lum / 2.55:.3f} {bl / 2.55 * 1.09:.3f}")
    cie += ['END_DATA', '']
    # Real flatbeds soften edges (MTF) and add sensor noise; matching both
    # keeps the demo's Check-alignment behaviour calibrated to the same
    # thresholds as real scans (a razor-sharp noise-free render lets
    # sub-patch offsets sample pure colour far longer than any physical
    # scan would, and reads implausibly cleanly). Blur first, then ~1.5 %
    # Gaussian noise on top — the order of a real optical chain (Knut asked
    # for noise; the level is what his real Epson V700 scans actually
    # measure, ~0.6–1.2 % per box). Seeded, so demo scans stay
    # byte-reproducible for the tests.
    from PIL import ImageFilter
    # σ=1 gives ~3–4 px transitions — what Knut measured on real 300 dpi
    # scans (σ=2 spread edges over 7–8 px, unrealistically soft; #108).
    img = img.filter(ImageFilter.GaussianBlur(1))
    import numpy as _np
    rng = _np.random.default_rng(42)
    arr = _np.asarray(img, dtype=_np.float64)
    arr = arr + rng.normal(0.0, 0.015 * 255.0, size=arr.shape)
    img = Image.fromarray(_np.clip(arr, 0, 255).astype(_np.uint8))
    tif = out_dir / f"{cht_path.stem}-test.tif"; ref = out_dir / f"{cht_path.stem}-test.cie"
    img.save(tif); ref.write_text("\n".join(cie), encoding="utf-8")
    return tif, ref


def merge_demo_references(cie_paths, out_path):
    """Concatenate several single-page demo ``.cie`` files into one reference
    covering every page — the shared reference a multi-page set is read against
    (the pages' patch names are disjoint, so no row collides). Returns
    ``out_path``."""
    from pathlib import Path as _P
    out_path = _P(out_path)
    header: list[str] | None = None
    rows: list[str] = []
    for cp in cie_paths:
        lines = read_text(_P(cp)).splitlines()
        ds = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
        de = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
        if header is None:
            header = lines[:ds + 1]
        rows += [l for l in lines[ds + 1:de] if l.strip()]
    out: list[str] = []
    for l in (header or []):
        out.append(f"NUMBER_OF_SETS {len(rows)}"
                   if l.strip().startswith("NUMBER_OF_SETS") else l)
    out += rows + ["END_DATA", ""]
    out_path.write_text("\n".join(out), encoding="utf-8")
    return out_path


def make_multipage_test_scans(cht_paths, out_dir):
    """A demo scan for each page of a multi-page set plus one merged reference
    covering all pages — the multi-page analogue of :func:`make_test_scan`, so a
    set can be tried end-to-end with no hardware. Returns ``(tif_paths, cie_path)``."""
    from pathlib import Path as _P
    cht_paths = [_P(c) for c in cht_paths]
    tifs: list[Path] = []
    cies: list[Path] = []
    for cht in cht_paths:
        tif, cie = make_test_scan(cht, out_dir)
        tifs.append(tif)
        cies.append(cie)
    stems = "+".join(c.stem for c in cht_paths)
    merged = _P(out_dir) / f"{stems}-test.cie"
    merge_demo_references(cies, merged)
    return tifs, merged
