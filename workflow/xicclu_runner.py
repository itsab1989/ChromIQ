"""Batch colour lookups through an ICC profile via Argyll's ``xicclu`` (#72).

The perceptual bridge for N-channel chart generation: RGB-generator colours →
Lab → **backward** (``-fb``) through a preconditioning profile → device ink
values; device values → **forward** (``-ff``) → XYZ for the ``.ti1`` (or Lab
for the out-of-gamut round-trip check).

I/O grammar (verified live against ArgyllCMS 3.5.0, issue #72):

* one query per stdin line, whitespace-separated; one result line per query::

      50.000000 40.000000 30.000000 [Lab] -> Lut -> 0.126686 0.742860 0.733718 0.071004 [CMYK]

  → parse the tokens between the last ``->`` and the trailing ``[…]`` tag.
* device values are 0..1 on the wire (scaled ×100/÷100 at this boundary —
  TI1/TI2 files use 0..100); ``-pX`` returns XYZ already ×100 (TI1-ready);
  ``-pl`` returns Lab unscaled.
* ``-fb`` (Lut backward) emits **no clip marker** on out-of-gamut input — OOG
  detection is the caller's forward round-trip (#72 appendix B). ``-fif``
  (inverse forward) *does* append a ``(clip)`` marker after the tag; the
  parser tolerates both.
* an ink limit (``-l``) is only **enforced** by the numeric inverse-forward
  path (``-fif``) — on ``-fb`` the baked B2A table can't be limited and the
  ``TAC <n>`` pair is merely reported (verified live: ``-fb -l250`` happily
  returned TAC 2.87). :func:`backward_device` therefore switches to ``-fif``
  whenever an ink limit is given. The trailing ``TAC``/tag/marker tokens are
  all stripped from parsed values.

Process model: ``subprocess.run`` with an injectable ``runner`` (the
``reference_convert.py`` house pattern) — one process per batch, **never** the
ArgyllRunner QProcess singleton, whose ``is_running`` guard would make live
generator previews clash with a running chartread/colprof.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary

log = get_logger(__name__)

_TIMEOUT_S = 120


class XiccluError(RuntimeError):
    """xicclu failed or returned unparseable output (user-facing message)."""


def _run_xicclu(
    bin_dir: str | Path,
    args: list[str],
    profile: str | Path,
    input_lines: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess],
) -> list[list[float]]:
    """One xicclu process over all ``input_lines``; parsed per-line results.

    Falls back to ``icclu`` (a pure table walk) when xicclu's reverse
    machinery rejects the profile — its rspl code is compiled for at most 4
    device channels (``rev_set_lchw can't handle di = N``, ArgyllCMS 3.5.0),
    so 5+ channel profiles (the engine's nCLR output, #122) need the fallback
    for *both* directions. icclu understands ``-f``/``-i``/``-p`` but none of
    the inversion options (``-k``/``-l``/``-fif``); those are dropped — for
    engine profiles the ink limit is already baked into the B2A table.
    Scale note (verified live): icclu ``-pX`` returns XYZ on the 0..1 scale
    where xicclu returns ×100 — rescaled here so callers see one grammar.
    """
    exe = Path(bin_dir) / argyll_binary("xicclu")
    if not exe.exists():
        raise XiccluError(f"xicclu not found in {bin_dir}")
    cmd = [str(exe), *args, str(profile)]
    try:
        r = run_text(cmd, runner=runner, input="\n".join(input_lines) + "\n",
                     capture_output=True, timeout=_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise XiccluError(f"xicclu timed out after {_TIMEOUT_S}s") from exc
    if r.returncode != 0 and "can't handle di" in (r.stderr or r.stdout):
        return _run_icclu_fallback(bin_dir, args, profile, input_lines, runner)
    if r.returncode != 0:
        raise XiccluError(
            f"xicclu failed ({r.returncode}): {(r.stderr or r.stdout).strip()}")

    out: list[list[float]] = []
    for line in r.stdout.splitlines():
        if "->" not in line:
            continue                     # ignore any banner/blank lines
        # The result values are the leading float run after the last "->";
        # everything after it is annotation ("TAC <n>", "[CMYK]", "(clip)").
        vals: list[float] = []
        for tok in line.rsplit("->", 1)[1].split():
            try:
                vals.append(float(tok))
            except ValueError:
                break
        if not vals:
            raise XiccluError(f"unparseable xicclu line: {line!r}")
        out.append(vals)
    if len(out) != len(input_lines):
        raise XiccluError(
            f"xicclu returned {len(out)} results for {len(input_lines)} queries")
    return out


def _run_icclu_fallback(
    bin_dir: str | Path,
    args: list[str],
    profile: str | Path,
    input_lines: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess],
) -> list[list[float]]:
    """Re-run a >4-channel lookup through icclu (see :func:`_run_xicclu`)."""
    exe = Path(bin_dir) / argyll_binary("icclu")
    if not exe.exists():
        raise XiccluError(f"icclu not found in {bin_dir}")
    keep: list[str] = []
    xyz_out = False
    for a in args:
        if a == "-fif":
            keep.append("-fb")          # table walk instead of inversion
        elif a.startswith(("-k", "-l")):
            continue                    # baked into engine B2A tables
        else:
            keep.append(a)
        if a == "-pX":
            xyz_out = True
    log.info("xicclu can't invert >4-channel profile — using icclu fallback")
    cmd = [str(exe), *keep, str(profile)]
    try:
        r = run_text(cmd, runner=runner, input="\n".join(input_lines) + "\n",
                     capture_output=True, timeout=_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise XiccluError(f"icclu timed out after {_TIMEOUT_S}s") from exc
    if r.returncode != 0:
        raise XiccluError(
            f"icclu failed ({r.returncode}): {(r.stderr or r.stdout).strip()}")
    out: list[list[float]] = []
    for line in r.stdout.splitlines():
        if "->" not in line:
            continue
        vals: list[float] = []
        for tok in line.rsplit("->", 1)[1].split():
            try:
                vals.append(float(tok))
            except ValueError:
                break
        if not vals:
            raise XiccluError(f"unparseable icclu line: {line!r}")
        if xyz_out:
            vals = [v * 100.0 for v in vals]     # icclu -pX is 0..1 scale
        out.append(vals)
    if len(out) != len(input_lines):
        raise XiccluError(
            f"icclu returned {len(out)} results for {len(input_lines)} queries")
    return out


def forward_xyz(
    device_rows: Sequence[tuple[float, ...]],
    profile: str | Path,
    bin_dir: str | Path,
    *,
    intent: str = "r",
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[tuple[float, float, float]]:
    """Device values (0..100) → XYZ (Y=100 scale, TI1-ready) via ``-ff -pX``."""
    lines = [" ".join(f"{v / 100.0:.6f}" for v in row) for row in device_rows]
    res = _run_xicclu(bin_dir, ["-ff", f"-i{intent}", "-pX"],
                      profile, lines, runner)
    return [tuple(row) for row in res]   # -pX is already ×100


def forward_lab(
    device_rows: Sequence[tuple[float, ...]],
    profile: str | Path,
    bin_dir: str | Path,
    *,
    intent: str = "r",
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[tuple[float, float, float]]:
    """Device values (0..100) → Lab via ``-ff -pl`` (the OOG round-trip leg)."""
    lines = [" ".join(f"{v / 100.0:.6f}" for v in row) for row in device_rows]
    res = _run_xicclu(bin_dir, ["-ff", f"-i{intent}", "-pl"],
                      profile, lines, runner)
    return [tuple(row) for row in res]


def backward_device(
    lab_rows: Sequence[tuple[float, float, float]],
    profile: str | Path,
    bin_dir: str | Path,
    *,
    intent: str = "r",
    k_rule: str | None = "r",
    ink_limit: float | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[tuple[float, ...]]:
    """Lab targets → device values (0..100).

    Uses ``-fb`` (fast Lut backward) normally, but switches to ``-fif``
    (numeric inverse-forward) when ``ink_limit`` is given — only that path
    actually *enforces* ``-l``; on ``-fb`` the baked B2A table ignores it and
    the TAC pair is merely informational (verified live, ArgyllCMS 3.5.0).

    ``k_rule`` is xicclu's ``-k`` black-generation rule (#72 decision: ``"r"``
    for v1, no UI knobs); it only applies to profiles with a K channel — pass
    ``None`` to omit. Trailing ``TAC``/``(clip)`` annotations are stripped
    from the parsed values.
    """
    args = ["-fif" if ink_limit is not None else "-fb", f"-i{intent}", "-pl"]
    if k_rule:
        args.append(f"-k{k_rule}")
    if ink_limit is not None:
        args.append(f"-l{ink_limit:g}")
    lines = [" ".join(f"{v:.6f}" for v in row) for row in lab_rows]
    res = _run_xicclu(bin_dir, args, profile, lines, runner)
    return [tuple(v * 100.0 for v in row) for row in res]


# ---------------------------------------------------------------------------
# The perceptual bridge (#72 Tier C): RGB generator sets → device values
# ---------------------------------------------------------------------------

def _srgb_to_lab_rows(rgb_rows: Sequence[tuple[float, float, float]]
                      ) -> list[tuple[float, float, float]]:
    """sRGB 0..100 triples → Lab, via the patch generators' own converter (so
    the bridge sees exactly the colours the RGB sets were designed in)."""
    import numpy as np
    from workflow.patch_generators import _srgb_to_lab

    arr = np.asarray(rgb_rows, dtype=float) / 100.0
    lab = _srgb_to_lab(arr)
    return [tuple(float(v) for v in row) for row in lab]


def to_device_via_profile(
    rgb_patches: Sequence[tuple[float, float, float]],
    profile: str | Path,
    bin_dir: str | Path,
    *,
    intent: str = "r",
    k_rule: str | None = "r",
    ink_limit: float | None = None,
    moved_threshold: float = 3.0,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> tuple[list[tuple[float, ...]], int]:
    """Every RGB generator set becomes a device-value factory (#72 Tier C).

    RGB (0..100) → Lab → backward through the preconditioning ``profile`` →
    device tuples (0..100), plus the **honest displacement count**: the device
    values are run forward again and any patch whose round-trip Lab moved by
    ΔE76 > ``moved_threshold`` counts as "outside this printer's gamut, moved
    to the nearest printable colour" (#72 appendix B — the 3.0 threshold is
    empirically clean: fully-in-gamut sets stay under it, OOG sets are far
    above). Clipped targets land on *distinct* surface points, so patches are
    kept, deduplicated later in device space.

    Returns ``(device_rows, moved_count)``. One xicclu process per direction.
    """
    if not rgb_patches:
        return [], 0
    labs = _srgb_to_lab_rows(rgb_patches)
    dev = backward_device(labs, profile, bin_dir, intent=intent,
                          k_rule=k_rule, ink_limit=ink_limit, runner=runner)
    back = forward_lab(dev, profile, bin_dir, intent=intent, runner=runner)
    moved = sum(
        1 for want, got in zip(labs, back)
        if math.dist(want, got) > moved_threshold
    )
    return dev, moved
