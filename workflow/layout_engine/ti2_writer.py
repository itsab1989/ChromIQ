"""Emit a CGATS ``.ti2`` matching printtarg's structure (colorant-agnostic).

Given the canonical test patches, their device-field names + ``COLOR_REP`` (from
:mod:`workflow.layout_engine.ti1_reader`), a
:class:`~workflow.layout_engine.geometry.Layout` and the resolved
:class:`~workflow.layout_engine.instruments.Geom`, write a ``.ti2`` chartread
can consume.  Supports Gray / RGB / CMY / CMYK / multi-colorant targets — the
device columns are whatever the ``.ti1`` declared.  Padding patches are appended
as media so the final pass is full.
"""
from __future__ import annotations

from pathlib import Path

from . import permutation as perm
from .geometry import Layout
from .instruments import Geom

# Argyll's media-white APPROX_WHITE_POINT default seen in printtarg output.
DEFAULT_WHITE_POINT = (95.106486, 100.0, 108.844025)

Patch = tuple[tuple[float, ...], tuple[float, float, float]]  # (device, XYZ)


def _fmt(v: float) -> str:
    return f"{v:.5f}"


def build_ti2_text(
    test_patches: list[Patch],
    device_fields: list[str],
    layout: Layout,
    geom: Geom,
    *,
    color_rep: str = "iRGB",
    seed: int,
    randomize: bool = True,
    strip_pattern: str = perm.DEFAULT_STRIP_PATTERN,
    patch_pattern: str = perm.DEFAULT_PATCH_PATTERN,
    label_rule: str = perm.ARGYLL,
    paper_w_mm: float,
    paper_h_mm: float,
    media: Patch | None = None,
    white_point: tuple[float, float, float] = DEFAULT_WHITE_POINT,
    created: str | None = None,
    ink_limit: float | None = None,
) -> str:
    """Return the full ``.ti2`` text.

    *test_patches* are ``(device_tuple, (X, Y, Z))`` in canonical order; each
    ``device_tuple`` has one value per *device_fields* entry.  ``layout.padding``
    copies of *media* are appended (defaults to a white device patch).
    """
    ndev = len(device_fields)
    expected = layout.total_patches - layout.padding
    if len(test_patches) != expected:
        raise ValueError(f"expected {expected} test patches, got {len(test_patches)}")
    for dev, _ in test_patches:
        if len(dev) != ndev:
            raise ValueError(f"patch has {len(dev)} device values, expected {ndev}")

    if media is None:
        media = (tuple(100.0 for _ in range(ndev)), white_point)

    patches: list[Patch] = list(test_patches) + [media] * layout.padding
    total = len(patches)
    slots = perm.location_permutation(total, seed, randomize)

    # English whatever the locale, as ArgyllCMS writes it (core/cgats_date.py).
    from core.cgats_date import created_stamp
    created = created or created_stamp()
    seed_kw = ("RANDOM_START" if randomize else "CHART_ID", str(seed))
    n_fields = 2 + ndev + 3  # SAMPLE_ID SAMPLE_LOC <device…> XYZ_X XYZ_Y XYZ_Z

    lines: list[str] = []
    add = lines.append
    add("CTI2   ")
    add("")
    add('DESCRIPTOR "Argyll Calibration Target chart information 2"')
    add('ORIGINATOR "ChromIQ layout engine"')
    add(f'CREATED "{created}"')
    add(f'TARGET_INSTRUMENT "{geom.target_name}"')
    add('APPROX_WHITE_POINT "%s"' % " ".join(f"{c:.6f}" for c in white_point))
    add(f'COLOR_REP "{color_rep}"')
    if ink_limit is not None:
        # Carried from the .ti1 exactly as printtarg does, so the limit rides
        # the .ti2 → .ti3 chain and the profile build can prefill it (#72).
        add(f'TOTAL_INK_LIMIT "{ink_limit:.1f}"')
    add(f'PAPER_SIZE "{paper_w_mm:.1f}x{paper_h_mm:.1f}"')
    add(f'{seed_kw[0]} "{seed_kw[1]}"')
    for kw, val in geom.extra_keywords:
        add(f'{kw} "{val}"')
    add(f'STEPS_IN_PASS "{layout.steps_in_pass}"')
    # PASSES_IN_STRIPS2 is the per-page STRIP (pass) count, comma-separated, just
    # as printtarg writes it (e.g. "22,22,5") — chartread and the Create Chart
    # layout-info read it this way. The engine previously wrote a single number
    # (the last strip's row count), which mis-read as "page 1 has N strips"
    # (#93, Knut). Derive the real per-page strip counts here.
    _steps = layout.steps_in_pass or 1
    _per_page = layout.patches_per_page or 0
    _strip_counts: list[int] = []
    _remaining = layout.total_patches
    for _pg in range(max(1, layout.pages)):
        _on_page = min(_per_page, _remaining) if _per_page else _remaining
        _strip_counts.append((_on_page + _steps - 1) // _steps)
        _remaining -= _on_page
    add(f'PASSES_IN_STRIPS2 "{",".join(str(c) for c in _strip_counts)}"')
    add(f'STRIP_INDEX_PATTERN "{strip_pattern}"')
    add(f'PATCH_INDEX_PATTERN "{patch_pattern}"')
    add('INDEX_ORDER "STRIP_THEN_PATCH"')
    add("")
    add(f"NUMBER_OF_FIELDS {n_fields}")
    add("BEGIN_DATA_FORMAT")
    add("SAMPLE_ID SAMPLE_LOC " + "".join(f + " " for f in device_fields)
        + "XYZ_X XYZ_Y XYZ_Z ")
    add("END_DATA_FORMAT")
    add("")
    add(f"NUMBER_OF_SETS {total}")
    add("BEGIN_DATA")
    for i, (dev, xyz) in enumerate(patches):
        loc = perm.location_label(slots[i], layout.steps_in_pass,
                                  strip_pattern, patch_pattern, label_rule)
        dev_s = "".join(_fmt(v) + " " for v in dev)
        add(f'{i + 1} "{loc}" {dev_s}{_fmt(xyz[0])} {_fmt(xyz[1])} {_fmt(xyz[2])} ')
    add("END_DATA")
    add("")
    return "\n".join(lines)


def write_ti2(path: str | Path, *args, **kwargs) -> Path:
    """Build and write the ``.ti2`` to *path*; returns the path."""
    text = build_ti2_text(*args, **kwargs)
    p = Path(path)
    p.write_text(text, encoding="utf-8")
    return p
