"""Which inks a chart's pages carry, decided from the chart itself (4.3.5, B2).

**THE CHANNEL COUNT IS NOT THE INK SET.** Every printing path used to choose
its colour space from the number of channels in the TIFF: 3 = DeviceRGB,
4 = DeviceCMYK, more = DeviceN. Measured on capture queues (report folder
``2026-10-10_435_photoshop_cmyk``, ``nonrgb/``) that is wrong twice:

* a CMY + orange chart has four channels, so its orange went to the printer
  as the BLACK ink (printtarg and the ChromIQ layout engine alike);
* a CMY chart made by the ChromIQ layout engine was an RGB TIFF holding the
  inverted ink values (``255 - ink``), so it went as RGB colours, while
  printtarg writes the same chart as CMYK with K = 0.

So the ink list is read from the chart (``<stem>.channels.json``, else the
``.ti2``'s ``COLOR_REP``) and the colour space follows it. An RGB or grey chart
never reaches anything here: :func:`plan_for` returns None for it, and every
caller keeps its RGB code exactly as it was (Basti, 2026-10-10: "no regressions
please since rgb printing finally seemed to work").
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.logger import get_logger

log = get_logger(__name__)

#: ``COLOR_REP`` letter token -> ChromIQ ink code (the convention of
#: ``ui.tiff_preview`` and ``.channels.json``).
_REP_TOKEN_CODE: dict[str, str] = {
    "C": "c", "M": "m", "Y": "y", "K": "k", "O": "o", "R": "r", "G": "g",
    "B": "b", "V": "v", "W": "w",
    "c": "lc", "m": "lm", "y": "ly", "k": "lk",
    "2c": "mc", "2m": "mm", "2y": "my", "2k": "mk", "1k": "llk",
}

CMYK = ("c", "m", "y", "k")
CMY = ("c", "m", "y")

#: TIFF photometric interpretations
_PHOTOMETRIC_RGB = 2
_PHOTOMETRIC_SEPARATED = 5


def rep_ink_codes(color_rep: str) -> list[str] | None:
    """``COLOR_REP`` -> ink codes, or None (RGB, grey or an unknown token)."""
    s = (color_rep or "").strip()
    if not s or s.upper() in ("RGB", "IRGB", "W", "K", "GRAY", "GREY"):
        return None
    out: list[str] = []
    i = 0
    while i < len(s):
        tok = s[i]
        if tok.isdigit():
            if i + 1 >= len(s):
                return None
            tok += s[i + 1]
            i += 1
        i += 1
        code = _REP_TOKEN_CODE.get(tok)
        if code is None:
            return None
        out.append(code)
    return out


def _chart_stem(path: Path) -> str:
    stem = path.stem
    while stem and (stem[-1].isdigit() or stem[-1] in "_- "):
        stem = stem[:-1]
    return stem


def sidecar_ink_codes(tiff_path: Path) -> list[str] | None:
    """The chart's ink list: ``<stem>.channels.json``, else its ``.ti2``."""
    tiff_path = Path(tiff_path)
    stem = _chart_stem(tiff_path)
    names = [tiff_path.stem] + ([stem] if stem and stem != tiff_path.stem else [])
    for name in names:
        side = tiff_path.parent / f"{name}.channels.json"
        if side.is_file():
            try:
                codes = json.loads(side.read_text(encoding="utf-8")).get("ink_channels")
                if isinstance(codes, list) and all(isinstance(c, str) for c in codes):
                    return list(codes)
            except Exception:  # noqa: BLE001 - a damaged sidecar: try the .ti2
                pass
    for name in names:
        ti2 = tiff_path.parent / f"{name}.ti2"
        if ti2.is_file():
            try:
                head = ti2.read_text(encoding="utf-8", errors="replace")[:4000]
            except OSError:
                continue
            m = re.search(r'^COLOR_REP\s+"([^"]+)"', head, re.M)
            if m:
                return rep_ink_codes(m.group(1))
    return None


@dataclass(frozen=True)
class InkPlan:
    """How a non-RGB chart page goes to a printer.

    ``space``: ``"DeviceCMYK"`` (CMYK, or CMY with K = 0) or ``"DeviceN"``.
    ``codes``: one ink code per channel of the array the page is sent as (for
    DeviceN the colorant names follow them). ``legacy_engine_cmy``: the page is
    a CMY chart the ChromIQ layout engine wrote before 4.3.5, an RGB TIFF of
    inverted ink values, which :func:`device_array` turns into CMYK with K = 0.
    """
    space: str
    codes: tuple[str, ...]
    legacy_engine_cmy: bool = False

    @property
    def is_cmy(self) -> bool:
        """CMY sent as CMYK with K = 0 (``codes`` = c, m, y, "k0")."""
        return self.codes == CMY + ("k0",)


def plan_for(n_channels: int, photometric: int | None,
             codes: list[str] | None) -> InkPlan | None:
    """The plan for a page of *n_channels* with this *photometric* and ink list,
    or None when the page is RGB or grey, or when the channel count alone
    already gives the right colour space (plain CMYK, or a chart whose inks are
    not known): every caller then keeps its old code, unchanged.
    """
    codes = list(codes) if codes else None
    if n_channels == 3 and photometric == _PHOTOMETRIC_RGB:
        if codes == list(CMY):
            return InkPlan("DeviceCMYK", CMY + ("k0",), legacy_engine_cmy=True)
        return None                                  # an RGB chart
    if n_channels < 3 or codes is None:
        return None
    if n_channels == 4:
        if codes == list(CMYK):
            return None                              # DeviceCMYK, as before
        if codes == list(CMY):
            # printtarg's CMY chart: CMYK with K = 0 (as before; named here so
            # every message can say "CMY")
            return InkPlan("DeviceCMYK", CMY + ("k0",))
        if len(codes) == 4:
            return InkPlan("DeviceN", tuple(codes))
        return None
    if n_channels > 4 and len(codes) >= n_channels:
        return InkPlan("DeviceN", tuple(codes[:n_channels]))
    return None


def page_photometric(tiff_path: Path, frame: int = 0) -> tuple[int, int | None]:
    """(samples per pixel, photometric) of one page, read with tifffile."""
    import tifffile
    with tifffile.TiffFile(str(tiff_path)) as tif:
        page = tif.pages[min(frame, len(tif.pages) - 1)]
        shape = page.shape
        n = shape[2] if len(shape) == 3 else 1
        try:
            phot = int(page.photometric)
        except (TypeError, ValueError):
            phot = None
    return n, phot


def plan_for_file(tiff_path: Path, frame: int = 0,
                  codes: list[str] | None = None) -> InkPlan | None:
    """:func:`plan_for` for one page of a file; *codes* default to the chart's
    own ink list (:func:`sidecar_ink_codes`)."""
    n, phot = page_photometric(tiff_path, frame)
    return plan_for(n, phot, codes if codes is not None else sidecar_ink_codes(tiff_path))


def is_rgb_page(tiff_path: Path, frame: int = 0,
                codes: list[str] | None = None) -> bool:
    """True only for a page that is RGB in its file AND in its ink list: 3
    channels, photometric RGB, and not one of the layout engine's CMY charts."""
    n, phot = page_photometric(tiff_path, frame)
    if n != 3 or phot != _PHOTOMETRIC_RGB:
        return False
    return plan_for(n, phot, codes if codes is not None
                    else sidecar_ink_codes(tiff_path)) is None


def device_array(arr: np.ndarray, plan: InkPlan) -> np.ndarray:
    """The page as the ink values the plan sends: a legacy engine CMY page
    (RGB, ``255 - ink``) becomes CMYK with K = 0; any other is returned as is."""
    if not plan.legacy_engine_cmy:
        return arr
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"legacy CMY page has shape {arr.shape}")
    maxv = np.iinfo(arr.dtype).max
    ink = (maxv - arr).astype(arr.dtype)
    k = np.zeros(arr.shape[:2] + (1,), dtype=arr.dtype)
    return np.ascontiguousarray(np.concatenate([ink, k], axis=2))


# --- how the inks are named in messages (A5) ----------------------------------

def _ink_labels() -> dict[str, str]:
    from core.i18n import tr
    # The same names as the Edit patch recipe dialog's extra-ink list
    # (ui.dialogs.ti2_relayout_dialog._extra_ink_labels), so a translator sees
    # each ink once.
    return {
        "k": tr("Black"),                 # a grey chart's one ink
        "o": tr("Orange"), "r": tr("Red"), "g": tr("Green"),
        "b": tr("Blue"), "v": tr("Violet"), "w": tr("White"),
        "lc": tr("Light cyan"), "lm": tr("Light magenta"),
        "ly": tr("Light yellow"), "lk": tr("Light black"),
        "mc": tr("Medium cyan"), "mm": tr("Medium magenta"),
        "my": tr("Medium yellow"), "mk": tr("Medium black"),
        "llk": tr("Light-light black"),
    }


def _ink_count(n: int) -> str:
    from core.i18n import tr
    # One key per count: Slavic languages decline the noun differently after
    # 3-4 and after 5 or more, so "{n} inks" cannot be translated once.
    by_n = {
        1: tr("1 ink"), 2: tr("2 inks"), 3: tr("3 inks"), 4: tr("4 inks"),
        5: tr("5 inks"), 6: tr("6 inks"), 7: tr("7 inks"), 8: tr("8 inks"),
    }
    return by_n.get(n) or tr("{n} inks").format(n=n)


def ink_set_label(codes: list[str] | tuple[str, ...] | None,
                  n_channels: int | None = None) -> str:
    """The chart's inks in words: "CMY, 3 inks", "CMYK + Orange, 5 inks",
    "CMY + Orange, 4 inks". A K = 0 channel printtarg adds to a CMY chart is not
    an ink and is not counted."""
    from core.i18n import tr
    codes = [c for c in (codes or []) if c != "k0"]
    if not codes:
        n = int(n_channels or 0)
        if n == 4:                       # no ink list: four channels print as CMYK
            codes = list(CMYK)
        else:
            return _ink_count(n) if n else "?"
    labels = _ink_labels()
    if codes[:4] == list(CMYK):
        head, rest = "CMYK", codes[4:]
    elif codes[:3] == list(CMY) and "k" not in codes:
        head, rest = "CMY", codes[3:]
    else:
        head, rest = "", codes
    parts = ([head] if head else []) + [
        labels.get(c, c.upper()) for c in rest]
    return tr("{inks}, {count}").format(inks=" + ".join(parts),
                                        count=_ink_count(len(codes)))


def split_page(tiff_path: Path, frame: int = 0) -> Path | None:
    """One page of a multi-page chart as its own temporary TIFF, written with
    tifffile so every channel, the photometric and the ink tags are kept (PIL
    cannot open a chart of five or more inks, and saved a CMYK page as RGB in
    some versions). None when the file has one page and *frame* is 0: it is
    then printed as it is. The caller deletes the file."""
    import os
    import tempfile
    import tifffile
    with tifffile.TiffFile(str(tiff_path)) as tif:
        if len(tif.pages) <= 1 and frame <= 0:
            return None
        page = tif.pages[min(frame, len(tif.pages) - 1)]
        arr = page.asarray()
        kwargs: dict = {"photometric": page.photometric}
        xr, yr = page.tags.get("XResolution"), page.tags.get("YResolution")
        if xr is not None and yr is not None:
            kwargs["resolution"] = (xr.value[0] / xr.value[1], yr.value[0] / yr.value[1])
            unit = page.tags.get("ResolutionUnit")
            kwargs["resolutionunit"] = unit.value if unit is not None else 2
        extratags = []
        for code, name, dtype in ((332, "InkSet", "H"), (334, "NumberOfInks", "H"),
                                  (333, "InkNames", "s")):
            tag = page.tags.get(name)
            if tag is not None:
                val = tag.value
                if dtype == "s":
                    val = val if isinstance(val, str) else "\0".join(val)
                    extratags.append((code, "s", 0, val.rstrip("\0") + "\0", True))
                else:
                    extratags.append((code, "H", 1, int(val), True))
        if extratags:
            kwargs["extratags"] = extratags
        es = page.tags.get("ExtraSamples")
        if es is not None:
            vals = es.value if isinstance(es.value, (tuple, list)) else (es.value,)
            kwargs["extrasamples"] = tuple(int(v) for v in vals)
    fd, tmp = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    tifffile.imwrite(tmp, arr, **kwargs)
    return Path(tmp)


def extra_ink_label(codes) -> str:
    """The inks past CMYK (or CMY) in words, joined with commas: "Orange",
    "Orange, Green"; "" when there are none."""
    codes = [c for c in (codes or []) if c != "k0"]
    if codes[:4] == list(CMYK):
        rest = codes[4:]
    elif codes[:3] == list(CMY) and "k" not in codes:
        rest = codes[3:]
    else:
        rest = codes
    labels = _ink_labels()
    return ", ".join(labels.get(c, c.upper()) for c in rest)
