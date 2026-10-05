"""Agent 25: replay the colorimetric B2A stage of a captured build with
research tokens, and splice the new B2A1 and gamt CLUTs into a copy of the
captured profile (v2 file). Everything else in the profile is the captured
build's bytes, so a rel. col. test of the copy measures the B2A1 change only.

    python -m benchmarks.research.oog25.replay CAP.pkl BASE.icc OUT.icc [--tokens a,b]

``--tokens ""`` must reproduce BASE.icc's B2A1 bit for bit (checked and
printed: this is what makes a replay a valid stand-in for a build).
"""
from __future__ import annotations

import argparse
import os
import pickle
import struct
import sys
import time
from pathlib import Path

import numpy as np

for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_k, "1")

TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))


def tag_table(data: bytes) -> dict:
    n = struct.unpack(">I", data[128:132])[0]
    out = {}
    for i in range(n):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        out[sig.decode("latin-1")] = (off, size)
    return out


def clut_span(data: bytes, off: int) -> tuple[int, int, int, int]:
    """(clut start, clut bytes, n_in, n_out) of an mft2 tag at ``off``."""
    assert data[off:off + 4] == b"mft2", data[off:off + 4]
    nin, nout, grid = data[off + 8], data[off + 9], data[off + 10]
    ine, oute = struct.unpack(">HH", data[off + 48:off + 52])
    start = off + 52 + nin * ine * 2
    return start, (grid ** nin) * nout * 2, nin, nout


def set_tokens(tokens) -> None:
    from workflow.profile_engine import b2a
    b2a.set_research_tokens(frozenset(tokens), is_additive=None)


def colorimetric_b2a(cap: dict, tokens=()) -> tuple[np.ndarray, np.ndarray]:
    """(dev_clut_shaped, residual) exactly as builder._build_profile_impl
    computes them for B2A1 (no a17-colpin, no joint-sep: not default)."""
    from workflow.profile_engine import b2a
    model = cap["model"]
    grid = cap["grid"]
    kw = dict(cap["build_kw"])
    b2a.set_research_tokens(frozenset(tokens), is_additive=kw["is_additive"])
    node_lab = kw["node_lab"]
    dev_clut, residual = b2a.build_b2a_clut(model, grid, **kw)
    fixed = None
    if "axis" in cap:
        fixed = b2a.apply_neutral_axis(dev_clut, node_lab, cap["axis"], model,
                                       **cap["axis_kw"])
    shaped = b2a.refine_b2a_clut(model, dev_clut, residual, grid,
                                 fixed_nodes=fixed, **cap["refine_kw"])
    channel_max = kw.get("channel_max")
    if channel_max is not None:
        top = model.shape_device(channel_max[None, :])
        shaped = np.minimum(shaped, top)
    shaped = b2a.pin_white_node(shaped, node_lab, kw["is_additive"])
    n = model.n_channels
    if kw["is_additive"]:
        device_black = np.zeros(n)
    else:
        black_node = int(np.argmin(np.linalg.norm(node_lab, axis=1)))
        device_black = dev_clut[black_node].copy()
    if channel_max is not None:
        device_black = np.minimum(device_black, channel_max)
    shaped = b2a.pin_black_node(shaped, node_lab,
                                model.shape_device(device_black[None, :])[0])
    b2a.set_research_tokens(frozenset(), is_additive=kw["is_additive"])
    return shaped, residual


def splice(base: Path, out: Path, shaped: np.ndarray, residual: np.ndarray) -> dict:
    from workflow.profile_engine import icc_writer as icw
    data = bytearray(base.read_bytes())
    tags = tag_table(bytes(data))
    off, _ = tags["B2A1"]
    start, nbytes, nin, nout = clut_span(bytes(data), off)
    new = icw.device_to_u16(shaped).tobytes()
    assert len(new) == nbytes, (len(new), nbytes)
    old = bytes(data[start:start + nbytes])
    data[start:start + nbytes] = new
    knee = np.clip((residual - 6.0) / 6.0, 0.0, 1.0)
    gamt_dist = np.maximum(residual - 6.0 * (1.0 - knee), 0.0)
    g = (np.clip(gamt_dist, 0, 128)[:, None] / 128 * 0xFFFF).round()
    goff, _ = tags["gamt"]
    gs, gn, _, _ = clut_span(bytes(data), goff)
    gnew = np.clip(g, 0, 0xFFFF).astype(">u2").tobytes()
    assert len(gnew) == gn
    gold = bytes(data[gs:gs + gn])
    data[gs:gs + gn] = gnew
    # profile ID (bytes 84..100) is zero in v2 files; a v4 copy would need it
    out.write_bytes(bytes(data))
    a = np.frombuffer(old, ">u2").astype(int)
    b = np.frombuffer(new, ">u2").astype(int)
    return {"b2a1_same": old == new, "gamt_same": gold == gnew,
            "b2a1_max_lsb": int(np.abs(a - b).max()),
            "b2a1_nodes_changed": int((np.abs(a - b).reshape(-1, nout).max(1) > 0).sum())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cap")
    ap.add_argument("base")
    ap.add_argument("out")
    ap.add_argument("--tokens", default="")
    a = ap.parse_args(argv)
    cap = pickle.loads(Path(a.cap).read_bytes())
    t0 = time.time()
    toks = [t for t in a.tokens.split(",") if t]
    shaped, residual = colorimetric_b2a(cap, toks)
    info = splice(Path(a.base), Path(a.out), shaped, residual)
    np.save(Path(a.out).with_suffix(".res.npy"), residual)
    info["seconds"] = round(time.time() - t0, 1)
    info["tokens"] = toks
    print("REPLAY", info, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
