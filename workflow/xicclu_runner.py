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
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Sequence

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary

log = get_logger(__name__)

_TIMEOUT_S = 120

#: Rows per xicclu process once a batch is split. A process costs about 0.08 s
#: to start and load the profile, and a row costs about 0.5-1.0 ms, so a slice
#: smaller than this spends more time starting than looking anything up.
#: Measured 2026-09-15 on ArgyllCMS 3.5.0: ``-fif`` over the 5,960-colour
#: master set cost 0.10 s for 60 rows and 3.31 s for all of them, so the work
#: is per-ROW and splitting it wins nearly linearly.
_SPLIT_MIN_ROWS_PER_PROCESS = 250


class XiccluError(RuntimeError):
    """xicclu failed or returned unparseable output (user-facing message)."""


def _split_workers(n_rows: int) -> int:
    """How many xicclu processes to spread *n_rows* over. 1 = do not split."""
    try:
        cpus = os.cpu_count() or 1
    except Exception:                    # noqa: BLE001 — a count must not raise
        cpus = 1
    return max(1, min(cpus, n_rows // _SPLIT_MIN_ROWS_PER_PROCESS))


def _run_xicclu(
    bin_dir: str | Path,
    args: list[str],
    profile: str | Path,
    input_lines: Sequence[str],
    runner: Callable[..., subprocess.CompletedProcess],
) -> list[list[float]]:
    """The batch, over as many xicclu processes as the rows are worth.

    **THE SAME QUESTION, NOT A CHEAPER ONE.** xicclu answers one stdin line per
    output line and nothing carries between lines, so N processes over N slices
    of the rows return exactly what one process over all of them returns, and
    the flags, the profile and the intent are untouched. Verified value by
    value on two real profiles and eight worker/chunk combinations
    (``~/Desktop/ChromIQ-beta18-proof/katrina-hang/fix/tune_the_split.py``):
    every one identical to the serial answer.

    It matters because xicclu is single-threaded and the reach query behind
    "From profile gamut" asks it for 5,960 colours on the GUI thread. Measured
    on this 16-core machine: 2.85 s serial → 0.54 s split, and on the slowest
    profile to hand 5.55 s → 0.84 s.

    An INJECTED ``runner`` is never split: a test's fake stands in for the
    process, and calling it N times with N slices would change what that test
    sees. Those callers keep exactly today's single call.
    """
    workers = (_split_workers(len(input_lines))
               if runner is subprocess.run else 1)
    if workers < 2:
        return _run_xicclu_once(bin_dir, args, profile, input_lines, runner)

    size = (len(input_lines) + workers - 1) // workers
    slices = [input_lines[i:i + size]
              for i in range(0, len(input_lines), size)]
    log.debug("xicclu: %d rows over %d processes", len(input_lines), len(slices))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(
            lambda s: _run_xicclu_once(bin_dir, args, profile, s, runner),
            slices))
    out: list[list[float]] = []
    for part in parts:
        out.extend(part)
    if len(out) != len(input_lines):
        raise XiccluError(
            f"xicclu returned {len(out)} results for {len(input_lines)} "
            "queries across the split batch")
    return out


def _run_xicclu_once(
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
    numeric_inverse: bool = False,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> list[tuple[float, ...]]:
    """Lab targets → device values (0..100).

    Uses ``-fb`` (fast Lut backward) normally, and ``-fif`` (numeric
    inverse-forward) when *numeric_inverse* is asked for OR an ``ink_limit`` is
    given: only that path actually *enforces* ``-l``, because on ``-fb`` the
    baked B2A table ignores it and the TAC pair is merely informational
    (verified live, ArgyllCMS 3.5.0).

    **AND THE ACCURATE PATH WAS REACHABLE ONLY THROUGH A CMYK ARGUMENT.** The
    switch used to be the ink limit alone. An ink limit is meaningless on an RGB
    output profile, so every RGB caller silently took the baked table, which is
    a fast approximation of an inverse rather than an inverse. Measured over the
    app's eleven bundled reference sets, 792 patches, round-tripped back through
    the same profile:

    ==================================  ==============  ==============
    how the Lab aim was inverted         mean dE00       within 0.5 dE00
    ==================================  ==============  ==============
    ``-fb``, the baked B2A table         0.366           659 of 792
    ``-fif``, the numeric inverse        **0.052**       **770 of 792**
    ==================================  ==============  ==============

    Reproduced with a direct ``-fif`` and no limit, so it is the inverse that
    matters here and not the limit. The cost is time and it is small: 1,617
    patches in 0.17 s.

    The flag is explicit rather than automatic. A caller that is placing ink on
    paper wants the accurate inverse; one that is only asking roughly where a
    colour lands can still have the fast table, and neither should change
    silently because somebody changed a default.

    ``k_rule`` is xicclu's ``-k`` black-generation rule (#72 decision: ``"r"``
    for v1, no UI knobs); it only applies to profiles with a K channel — pass
    ``None`` to omit. Trailing ``TAC``/``(clip)`` annotations are stripped
    from the parsed values.
    """
    args = ["-fif" if (numeric_inverse or ink_limit is not None) else "-fb",
            f"-i{intent}", "-pl"]
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
