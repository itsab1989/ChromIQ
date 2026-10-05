"""Agent 21 s3.1: where do the visible gradient jumps of an N-ink B2A come from?

Re-runs ncq NC5's 240 gradients (same seed) through the profile's B2A1 (Argyll) and, for
every visible jump (printed step > 3x target step and > 1 dE00), classifies it:

* model-visible: the profile's OWN A2B also sees the jump (A2B(dev) step > 3x target and
  > 1 dE00): the table itself is not colour-continuous there (refit averaging two metamer
  branches, a boundary clamp, the gamut-boundary facet change of Reinhard-Urban);
* model-hidden: the profile thinks the step is smooth but the printer does not: a metamer
  switch between two ink vectors the MODEL sees as the same colour and the printer does not
  (model error that differs between the branches);
plus the device step size, which inks moved, the target's depth inside the truth gamut, and the
inks-on count before/after.

    python jumpdiag.py PROFILE.icc PRINTER [--out file.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tree"))


def main():
    from benchmarks.research import cmm, colour, gmq
    from benchmarks.research.printers import build_printers
    prof, pid = sys.argv[1], sys.argv[2]
    p = build_printers()[pid]
    cloud = gmq.truth_cloud(p)
    gam = gmq.TruthGamut(cloud)
    rng = np.random.default_rng(31)
    n_pairs, steps = 120, 64
    inside = cloud[gam.depth(cloud) > 4.0]
    ends = inside[rng.choice(len(inside), (n_pairs, 2))]
    white = np.array([100.0, 0, 0])
    black = np.array([gam.black_l + 1.0, 0, 0])
    ends = np.vstack([ends, np.stack([np.tile(white, (n_pairs // 2, 1)),
                                      inside[rng.choice(len(inside), n_pairs // 2)]], 1),
                      np.stack([inside[rng.choice(len(inside), n_pairs // 2)],
                                np.tile(black, (n_pairs // 2, 1))], 1)])
    t = np.linspace(0, 1, steps)[:, None]
    paths = np.concatenate([a * (1 - t) + b * t for a, b in ends])
    dev = np.clip(cmm.b2a(prof, paths, "argyll"), 0, 1)
    printed = p.lab_rel(dev).reshape(len(ends), steps, 3)
    model = cmm.a2b(prof, dev, "argyll").reshape(len(ends), steps, 3)
    tgt = paths.reshape(len(ends), steps, 3)
    D = dev.reshape(len(ends), steps, -1)
    ps = colour.de2000(printed[:, 1:].reshape(-1, 3), printed[:, :-1].reshape(-1, 3))
    ms = colour.de2000(model[:, 1:].reshape(-1, 3), model[:, :-1].reshape(-1, 3))
    ts = colour.de2000(tgt[:, 1:].reshape(-1, 3), tgt[:, :-1].reshape(-1, 3))
    jumps = np.flatnonzero((ps > 3.0 * ts) & (ps > 1.0))
    dstep = np.abs(np.diff(D, axis=1)).reshape(-1, D.shape[2])
    a = D[:, :-1].reshape(-1, D.shape[2])
    b = D[:, 1:].reshape(-1, D.shape[2])
    mid = ((tgt[:, 1:] + tgt[:, :-1]) / 2).reshape(-1, 3)
    depth = gam.depth(mid[jumps]) if len(jumps) else np.array([])
    vis = (ms[jumps] > 3.0 * ts[jumps]) & (ms[jumps] > 1.0)
    letters = p.letters
    moved = [letters[int(i)] for i in dstep[jumps].argmax(1)] if len(jumps) else []
    on_a = (a[jumps] > 0.02).sum(1) if len(jumps) else np.array([])
    on_b = (b[jumps] > 0.02).sum(1) if len(jumps) else np.array([])
    res = {
        "profile": str(prof), "printer": pid, "visible_jumps": int(len(jumps)),
        "model_visible": int(vis.sum()), "model_hidden": int((~vis).sum()),
        "device_step_med_jump": float(np.median(dstep[jumps].max(1))) if len(jumps) else None,
        "device_step_p99_all": float(np.percentile(dstep.max(1), 99)),
        "depth_med": float(np.median(depth)) if len(jumps) else None,
        "near_boundary_lt2": int((depth < 2.0).sum()) if len(jumps) else 0,
        "most_moved_ink": {l: moved.count(l) for l in sorted(set(moved))},
        "inks_on_change": int((on_a != on_b).sum()) if len(jumps) else 0,
        "jump_target_L_med": float(np.median(mid[jumps, 0])) if len(jumps) else None,
        "jump_target_C_med": float(np.median(np.hypot(mid[jumps, 1], mid[jumps, 2]))) if len(jumps) else None,
        "printed_step_med_jump": float(np.median(ps[jumps])) if len(jumps) else None,
        "model_step_med_jump": float(np.median(ms[jumps])) if len(jumps) else None,
    }
    txt = json.dumps(res, indent=1)
    print(txt)
    if "--out" in sys.argv:
        Path(sys.argv[sys.argv.index("--out") + 1]).write_text(txt)


if __name__ == "__main__":
    main()
