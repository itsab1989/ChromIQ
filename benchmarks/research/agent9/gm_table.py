"""Markdown table of key gmq properties. usage: gm_table.py DIR NOISE READER INTENT ENGINES PRINTERS"""
import json, sys
from pathlib import Path
d, noise, rd, it, engs, pids = sys.argv[1:7]
K = [("M1_neutral_C_mean", "neutral C*"), ("M2_hue_ipt_wmean", "hue IPT"),
     ("M3_L_reversals", "L rev"), ("M3c_C_reversals", "C rev"), ("M4_d2_max", "d2 max"),
     ("M5_core_de_median", "core dE"), ("M6_plateau_mean", "plateau"),
     ("M7_outside_p05", "detail out p05"), ("M8_black_L", "black L"), ("M8_black_C", "black C"),
     ("M8_black_gap", "black gap"), ("M9_ink_max", "ink max"),
     ("M10_sep_d2_max", "sep d2"), ("M10_K_reversals", "K rev"), ("M11_rt_median", "rt med")]
print("| printer | engine | " + " | ".join(k[1] for k in K) + " |")
print("|" + "---|" * (len(K) + 2))
for pid in pids.split(","):
    for e in engs.split(","):
        f = Path(d) / f"{pid}-{noise}-{e}-{rd}-{it}.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text(encoding="utf-8"))
        cells = []
        for k, _ in K:
            v = r.get(k)
            cells.append("-" if v is None else (f"{v:.0f}" if isinstance(v, int) or k == "M9_ink_max" else f"{v:.2f}"))
        print(f"| {pid} | {e} | " + " | ".join(cells) + " |")
