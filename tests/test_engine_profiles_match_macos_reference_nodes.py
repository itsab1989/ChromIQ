"""D-07 point 4 and 5: the engine's profiles on every CI platform against the
macOS references, node by node.

Byte identity across operating systems is not expected (numpy's BLAS
differs: Accelerate on macOS, OpenBLAS on Linux and Windows; F-01, CI run
37251847063). What D-07 requires instead: from the SAME input, every table
node within one lut16 LSB of the macOS build, OR, where a node moves more,
every benchmark endpoint unchanged at the protocol's minimum effect.

The inputs and the references live in ``tests/data/engine_reference/``: the
measurement files (``<case>.ti3``) and the profiles a macOS arm64 machine
built from them (``<case>.icc.gz``), written by :func:`make_references`.
Every platform builds the same cases from the same .ti3 files and compares
every lut16 tag (input curves, CLUT, output curves) as 16-bit integers.

Within one LSB everywhere: pass. Otherwise the test computes the endpoints
(A2B1 dE00 against the synthetic printer's truth on 2,000 device points;
B2A1 round trip dE00 through the truth on 2,000 in-gamut targets; median
and p95) for the reference and for this build, and passes only if every
endpoint is within max(0.02, 5 % of the reference) of the macOS value, the
protocol's minimum effect without the seed term (stricter). Either way the
max and p95 node differences and the endpoints are written to the report.

When ``CHROMIQ_CI_ARTIFACTS`` is set (tests.yml sets it), every profile built
here and a ``node-report-<case>.json`` are written into that folder, and the
workflow uploads it, so the numbers survive the runner.

Re-make the references (only on macOS arm64, only for a deliberate engine
change, and say so in the commit):
    .venv/bin/python -c "import tests.test_engine_profiles_match_macos_reference_nodes as t; t.make_references()"
"""
from __future__ import annotations

import gzip
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

REF_DIR = Path(__file__).resolve().parent / "data" / "engine_reference"
_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)

# case -> (printer id, engine mode, patches). Fast on the two devices whose
# bytes B-1 pinned (S3 CMYK, S5 CMYKOG), Maximum accuracy with its default
# tokens on a CMYK and an RGB device.
CASES = {
    "S3-fast-l": ("S3", "fast", 900),
    "S5-fast-l": ("S5", "fast", 900),
    "X3-accurate-l": ("X3", "accurate", 400),
    "S1-accurate-l": ("S1", "accurate", 400),
}
_LSB_TOL = 1


def _argyll() -> str | None:
    from tests.argyll_env import argyll_bin_dir
    d = argyll_bin_dir()
    return str(d) if d is not None else None


def _build(case: str, ti3: Path, out: Path) -> Path:
    from benchmarks.research.printers import build_printers
    from workflow.profile_engine.builder import BuildSettings, build_profile
    pid, mode, _n = CASES[case]
    p = build_printers()[pid]
    kw = {}
    if mode == "accurate":
        argyll = _argyll()
        if argyll is None:
            pytest.skip("ArgyllCMS not installed (Maximum accuracy needs it)")
        kw["argyll_bin"] = argyll
    icc = out / f"{case}.icc"
    build_profile(ti3, icc, BuildSettings(
        quality="l", gammap_mode=mode, ink_limit=p.tac, timestamp=_TS,
        progress=lambda m: None, **kw))
    return icc


def _lut_tags(path: Path) -> dict[str, np.ndarray]:
    """Every mft2 tag as its raw 16-bit words (curves + CLUT + curves)."""
    from benchmarks.iccread import IccProfile
    prof = IccProfile(path)
    out = {}
    for sig, blob in sorted(prof.tags.items()):
        if blob[:4] != b"mft2":
            continue
        n_in, n_out, grid = blob[8], blob[9], blob[10]
        n_ine, n_oute = int.from_bytes(blob[48:50], "big"), \
            int.from_bytes(blob[50:52], "big")
        count = n_in * n_ine + grid ** n_in * n_out + n_out * n_oute
        out[sig] = np.frombuffer(blob, dtype=">u2", count=count,
                                 offset=52).astype(np.int64)
    return out


def node_differences(ref: Path, got: Path) -> dict:
    a, b = _lut_tags(ref), _lut_tags(got)
    assert sorted(a) == sorted(b), (sorted(a), sorted(b))
    rep = {}
    for sig in a:
        assert a[sig].shape == b[sig].shape, sig
        d = np.abs(a[sig] - b[sig])
        rep[sig] = {"nodes": int(d.size), "max_lsb": int(d.max()),
                    "p95_lsb": float(np.percentile(d, 95)),
                    "over_1_lsb": int((d > _LSB_TOL).sum())}
    return rep


def endpoints(icc: Path, pid: str) -> dict:
    """A2B1 and B2A1 dE00 against the truth (median, p95), fixed samples."""
    from benchmarks.iccread import IccProfile
    from benchmarks.research.printers import build_printers
    from workflow.profile_engine.metrics import delta_e_2000
    p = build_printers()[pid]
    prof = IccProfile(icc)
    rng = np.random.default_rng(20261005)
    dev = rng.uniform(0.0, 1.0, (6000, p.n))
    if p.tac is not None and not p.is_additive:
        dev = dev[dev.sum(1) * 100.0 <= p.tac]
    dev = dev[:2000]
    truth = p.lab_rel(dev)
    a2b = delta_e_2000(prof.a2b_lab(dev, "A2B1"), truth)
    back = p.lab_rel(np.clip(prof.b2a_device(truth, "B2A1"), 0.0, 1.0))
    b2a = delta_e_2000(back, truth)
    return {"a2b_median": float(np.median(a2b)),
            "a2b_p95": float(np.percentile(a2b, 95)),
            "b2a_median": float(np.median(b2a)),
            "b2a_p95": float(np.percentile(b2a, 95))}


def _artifact_dir() -> Path | None:
    d = os.environ.get("CHROMIQ_CI_ARTIFACTS")
    if not d:
        return None
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p


@pytest.mark.slow
@pytest.mark.parametrize("case", sorted(CASES))
def test_profile_nodes_match_the_macos_reference(case, tmp_path):
    ti3 = REF_DIR / f"{case}.ti3"
    ref = tmp_path / f"{case}-macos-ref.icc"
    ref.write_bytes(gzip.decompress((REF_DIR / f"{case}.icc.gz").read_bytes()))
    got = _build(case, ti3, tmp_path)
    nodes = node_differences(ref, got)
    worst = max(r["max_lsb"] for r in nodes.values())
    report = {"case": case, "platform": f"{sys.platform}-{platform.machine()}",
              "numpy": np.__version__, "within_one_lsb": worst <= _LSB_TOL,
              "tags": nodes}
    failures = []
    if worst > _LSB_TOL:
        pid = CASES[case][0]
        e_ref, e_got = endpoints(ref, pid), endpoints(got, pid)
        report["endpoints_macos"] = e_ref
        report["endpoints_here"] = e_got
        for k, v in e_ref.items():
            margin = max(0.02, 0.05 * v)
            if abs(e_got[k] - v) > margin:
                failures.append(f"{k}: macOS {v:.4f}, here {e_got[k]:.4f} "
                                f"(margin {margin:.4f})")
    art = _artifact_dir()
    if art is not None:
        shutil.copy2(got, art / got.name)
        (art / f"node-report-{case}.json").write_text(
            json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report))
    assert not failures, (
        f"{case}: nodes beyond {_LSB_TOL} lut16 LSB of the macOS build "
        f"(max {worst}) AND benchmark endpoints moved: {failures}; "
        f"nodes: {nodes}")


def test_every_case_has_its_input_and_reference():
    for case in CASES:
        assert (REF_DIR / f"{case}.ti3").is_file(), case
        assert (REF_DIR / f"{case}.icc.gz").is_file(), case


def test_the_comparison_sees_a_one_lsb_change(tmp_path):
    """The node reader is not blind: one word changed by 2 in a CLUT shows."""
    src = tmp_path / "a.icc"
    src.write_bytes(gzip.decompress(
        (REF_DIR / "S3-fast-l.icc.gz").read_bytes()))
    data = bytearray(src.read_bytes())
    from benchmarks.iccread import IccProfile
    import struct
    prof = IccProfile(src)
    ntags = struct.unpack(">I", data[128:132])[0]
    for i in range(ntags):
        rec = data[132 + 12 * i:144 + 12 * i]
        if rec[:4] == b"A2B1":
            off = struct.unpack(">I", rec[4:8])[0]
            break
    blob = prof.tags["A2B1"]
    n_in, n_ine = blob[8], int.from_bytes(blob[48:50], "big")
    at = off + 52 + 2 * (n_in * n_ine) + 2 * 10       # a CLUT word
    w = int.from_bytes(data[at:at + 2], "big")
    data[at:at + 2] = (w + 2 if w < 0xFFFD else w - 2).to_bytes(2, "big")
    dst = tmp_path / "b.icc"
    dst.write_bytes(bytes(data))
    rep = node_differences(src, dst)
    assert rep["A2B1"]["max_lsb"] == 2 and rep["A2B1"]["over_1_lsb"] == 1
    # tags stored at A2B1's offset (A2B0/A2B2 aliases) move with it
    shared = {s for s, b in prof.tags.items() if b is not None and b == blob}
    assert all(r["max_lsb"] == 0 for s, r in rep.items() if s not in shared)


def make_references(out_dir: Path | None = None) -> None:   # macOS arm64 only
    """Write the inputs and the macOS reference profiles (see the docstring)."""
    from benchmarks.research import datasets as dsm
    import tempfile
    assert sys.platform == "darwin" and platform.machine() == "arm64"
    out_dir = Path(out_dir or REF_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="chromiq-engine-ref-"))
    for case, (pid, _mode, n) in CASES.items():
        ds = dsm.synthetic(pid, work, n)
        ti3 = out_dir / f"{case}.ti3"
        shutil.copyfile(ds.ti3, ti3)
        icc = _build(case, ti3, work)
        (out_dir / f"{case}.icc.gz").write_bytes(
            gzip.compress(icc.read_bytes(), mtime=0))
        print(case, icc.stat().st_size)
    shutil.rmtree(work, ignore_errors=True)
