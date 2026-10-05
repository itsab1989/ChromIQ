import sys, numpy as np
sys.path.insert(0,'tree')
from benchmarks.research import cmm, colour, gmq
from benchmarks.research.printers import build_printers
prof, pid = sys.argv[1], sys.argv[2]
p = build_printers()[pid]; cloud = gmq.truth_cloud(p); gam = gmq.TruthGamut(cloud)
rng = np.random.default_rng(31); n_pairs, steps = 120, 64
inside = cloud[gam.depth(cloud) > 4.0]
ends = inside[rng.choice(len(inside), (n_pairs, 2))]
white = np.array([100.0, 0, 0]); black = np.array([gam.black_l + 1.0, 0, 0])
ends = np.vstack([ends, np.stack([np.tile(white, (n_pairs // 2, 1)), inside[rng.choice(len(inside), n_pairs // 2)]], 1),
                  np.stack([inside[rng.choice(len(inside), n_pairs // 2)], np.tile(black, (n_pairs // 2, 1))], 1)])
t = np.linspace(0, 1, steps)[:, None]
paths = np.concatenate([a * (1 - t) + b * t for a, b in ends])
dev = np.clip(cmm.b2a(prof, paths, "argyll"), 0, 1)
pr = p.lab_rel(dev).reshape(len(ends), steps, 3); D=dev.reshape(len(ends),steps,-1); P=paths.reshape(len(ends),steps,3)
d2 = np.linalg.norm(np.diff(pr, 2, axis=1), axis=2)
top = np.argsort(d2.ravel())[::-1][:int(sys.argv[3]) if len(sys.argv)>3 else 5]
for k in top:
    r, s = divmod(k, steps-2)
    print(f"ramp {r} step {s} d2 {d2[r,s]:.2f}  target {np.round(P[r,s+1],1)} depth {gam.depth(P[r,s+1:s+2])[0]:.1f}")
    for q in range(s, s+3): print("   dev%", np.round(D[r,q]*100,1), "printed", np.round(pr[r,q],1))
