"""Read a targen ``.ti1`` into a colorant-agnostic target.

targen emits different device columns per device type, all in the same CGATS
shape (verified with ``targen -d1/-d2/-d3/-d4``):

    -d1 Gray  COLOR_REP "W"     GRAY_W
    -d2 RGB   COLOR_REP "iRGB"  RGB_R RGB_G RGB_B
    -d3 CMY   COLOR_REP "RGB"   RGB_R RGB_G RGB_B   (subtractive, non-inverted)
    -d4 CMYK  COLOR_REP "CMYK"  CMYK_C CMYK_M CMYK_Y CMYK_K
    n-colour  COLOR_REP "CMYK…"  …more device columns…

So instead of hard-coding RGB we copy whatever device columns the ``.ti1``
declares straight through to the ``.ti2`` — supporting Gray, RGB, CMY, CMYK and
multi-colorant targets, matching what printtarg accepts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from core.text_io import read_text

# Columns that are not device colorant channels.
_NON_DEVICE = {"SAMPLE_ID", "SAMPLE_LOC", "INDEX", "SAMPLE_NAME"}


def _is_device_field(name: str) -> bool:
    if name in _NON_DEVICE:
        return False
    if name.startswith(("XYZ_", "LAB_", "SPEC_", "STDEV_", "D_")):
        return False
    return True


@dataclass(frozen=True)
class ColorTarget:
    color_rep: str                      # CGATS COLOR_REP (W / iRGB / RGB / CMYK / …)
    device_fields: list[str]            # e.g. ["CMYK_C","CMYK_M","CMYK_Y","CMYK_K"]
    patches: list[tuple[tuple[float, ...], tuple[float, float, float]]]
    # each patch = (device values, (X, Y, Z)); XYZ is (0,0,0) if absent
    # targen's TOTAL_INK_LIMIT (percent), carried .ti1 → .ti2 → .ti3 so the
    # profile build can read the chart's ink limit from the measurement (#72).
    ink_limit: float | None = None

    @property
    def n_channels(self) -> int:
        return len(self.device_fields)

    def media_patch(self) -> tuple[tuple[float, ...], tuple[float, float, float]]:
        """The brightest patch (max XYZ_Y) — paper white, used for padding.

        Falls back to the first patch if no XYZ is present.
        """
        if not self.patches:
            raise ValueError("target has no patches")
        if any(p[1][1] for p in self.patches):
            return max(self.patches, key=lambda p: p[1][1])
        return self.patches[0]


def read_ti1(path: str | Path) -> ColorTarget:
    """Parse a targen ``.ti1`` (the first data table) into a :class:`ColorTarget`."""
    text = read_text(Path(path), lenient=True)

    m = re.search(r'^COLOR_REP\s+"([^"]+)"', text, re.MULTILINE)
    color_rep = m.group(1) if m else "iRGB"

    m = re.search(r'^TOTAL_INK_LIMIT\s+"([\d.]+)"', text, re.MULTILINE)
    ink_limit = float(m.group(1)) if m else None

    fmt_m = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", text, re.DOTALL)
    if not fmt_m:
        raise ValueError("no BEGIN_DATA_FORMAT table in .ti1")
    fields = fmt_m.group(1).split()

    data_m = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.DOTALL)
    if not data_m:
        raise ValueError("no BEGIN_DATA table in .ti1")

    dev_idx = [i for i, f in enumerate(fields) if _is_device_field(f)]
    device_fields = [fields[i] for i in dev_idx]
    xyz_idx = {ax: (fields.index(f) if f in fields else None)
               for ax, f in (("X", "XYZ_X"), ("Y", "XYZ_Y"), ("Z", "XYZ_Z"))}

    patches: list[tuple[tuple[float, ...], tuple[float, float, float]]] = []
    for line in data_m.group(1).splitlines():
        toks = line.split()
        if len(toks) < len(fields):
            continue
        dev = tuple(float(toks[i]) for i in dev_idx)
        xyz = tuple(
            float(toks[xyz_idx[ax]]) if xyz_idx[ax] is not None else 0.0
            for ax in ("X", "Y", "Z")
        )
        patches.append((dev, xyz))  # type: ignore[arg-type]

    if not patches:
        raise ValueError("no data rows in .ti1")
    return ColorTarget(color_rep=color_rep, device_fields=device_fields,
                       patches=patches, ink_limit=ink_limit)
