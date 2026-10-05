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
pr = p.lab_rel(dev); mo = cmm.a2b(prof, dev, "argyll")
ps = colour.de2000(pr[1:], pr[:-1]); ts = colour.de2000(paths[1:], paths[:-1])
J = np.flatnonzero((ps > 3*ts) & (ps > 1.0))
J = J[(J % steps) != steps-1]
print("ramp kinds of jumps (0-119 colour-colour, 120-179 white-colour, 180-239 colour-black):", np.bincount(J//steps//60, minlength=4))
for j in J[:int(sys.argv[3]) if len(sys.argv)>3 else 4]:
    r = j // steps; s = j % steps
    print(f"ramp {r} step {s}")
    for k in range(max(r*steps, j-2), min(r*steps+steps, j+4)):
        print("  tgt", np.round(paths[k],1), "dev", np.round(dev[k]*100,1), "printed", np.round(pr[k],1), "model", np.round(mo[k],1))
