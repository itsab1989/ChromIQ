"""Identity proof for run f05/runs/id: f05/s1 arms vs base (every tag but desc), l1 arm = the post-hoc
C-L1b transform of the base A2B tags (byte for byte)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "cl1"))
sys.path.insert(0, str(Path(__file__).parent / "tree"))
from icchelp import tags_of
from workflow.profile_engine.lab_l1 import encode_a2b_l1b
P = Path(__file__).parent / "f05/runs/id/profiles"
for base in sorted(P.glob("*-base*.icc")):
    tb = dict(tags_of(base.read_bytes()))
    for arm in ("f05", "s1", "l1"):
        p = base.with_name(base.name.replace("-base", f"-{arm}"))
        if not p.exists():
            continue
        ta = dict(tags_of(p.read_bytes()))
        diff = sorted(s for s in set(ta) | set(tb) if ta.get(s) != tb.get(s) and s != "desc")
        if arm == "l1":
            ok = all(ta[s] == encode_a2b_l1b(tb[s]) for s in diff if s.startswith("A2B")) and \
                all(s.startswith("A2B") for s in diff)
            print(f"{p.name}: differs in {diff}; equal to post-hoc C-L1b of base: {ok}")
        else:
            print(f"{p.name}: differs from base in {diff or 'nothing (byte-identical tags)'}")
