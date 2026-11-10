"""F-18 probe: outliers in the gamut-mapped node field of a captured build
(capture_b2a.py pickle). A node whose mapped displacement differs from the
median of its 6 lattice neighbours by > THR dE76 is an outlier.
    python map_outliers.py CAP.pkl [THR]"""
import pickle, sys
import numpy as np
cap = pickle.load(open(sys.argv[1], "rb"))
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
node = cap["inv"][0][0]
g = round(len(node) ** (1 / 3))
mapped_calls = [c for c in cap["inv"][1:] if len(c[0]) == len(node)]
for j, (tgt, d, r, _) in enumerate(mapped_calls):
    disp = (tgt - node).reshape(g, g, g, 3)
    pad = np.pad(disp, ((1, 1), (1, 1), (1, 1), (0, 0)), mode="edge")
    nb = np.stack([pad[2:, 1:-1, 1:-1], pad[:-2, 1:-1, 1:-1], pad[1:-1, 2:, 1:-1],
                   pad[1:-1, :-2, 1:-1], pad[1:-1, 1:-1, 2:], pad[1:-1, 1:-1, :-2]], 0)
    med = np.median(nb, 0)
    dev = np.linalg.norm(disp - med, axis=-1).reshape(-1)
    # only nodes whose source colour is plausible content: inside the
    # source gamut is unknown here, so report all and the near-neutral ones
    c = np.hypot(node[:, 1], node[:, 2])
    out = dev > thr
    print(f"mapped table {j}: outliers > {thr} dE: {out.sum()} of {len(dev)}; "
          f"near-neutral (C*<10) {np.sum(out & (c < 10))}; worst {dev.max():.1f} at node "
          f"{node[np.argmax(dev)].round(2).tolist()} -> {tgt[np.argmax(dev)].round(2).tolist()}")
    for i in np.argsort(-(dev * (c < 10)))[:5]:
        if dev[i] > thr:
            print(f"   near-neutral node {node[i].round(2).tolist()} -> {tgt[i].round(2).tolist()} (off {dev[i]:.1f})")
