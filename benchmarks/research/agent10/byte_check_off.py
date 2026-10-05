"""Engine OFF, byte level: each profile the app built with the engine off is
rebuilt with a colprof command typed here by hand (from colprof's own usage
text, not from ChromIQ's argument builder) on the same measurement, and the
two files are compared tag by tag (header creation date and profile ID
excluded). One colprof at a time.

    python byte_check_off.py run
"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / sys.argv[1]
R = json.loads((RUN / "result.json").read_text())
CP = "/Applications/Argyll/bin/colprof"
CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"
TI3 = RUN / "sandbox/projects/A10b-cmyk/runs/run1/A10b-cmyk.ti3"
# label -> the flags a user reading colprof's usage would type for that state
HAND = {
    "off-default": [],
    "off-qh": ["-qh"],
    "off-bh": ["-bh"],
    "off-r1": ["-r", "1"],
    "off-kx": ["-kx"],
    "off-kp": ["-kp", "0.1", "0.2", "0.8", "0.9", "1.2"],
    "off-tpa": ["-tpa"],
    "off-nI": ["-nI"],
    "off-nc": ["-nc"],
    "off-Zmp": ["-Zm", "-Zp"],
}


def tags(p):
    d = Path(p).read_bytes()
    (n,) = struct.unpack(">I", d[128:132])
    out = {}
    for i in range(n):
        sig, off, size = struct.unpack(">4sII", d[132 + 12 * i:144 + 12 * i])
        out[sig.decode("latin-1")] = d[off:off + size]
    hdr = d[:24] + d[36:84] + d[100:128]      # without date (24-35) and ID (84-99)
    return hdr, out


def text(t):
    n = struct.unpack(">I", t[8:12])[0]
    return t[12:12 + n].rstrip(b"\0").decode("latin-1")


def main():
    work = RUN / "bytecheck"
    work.mkdir(exist_ok=True)
    res = {}
    for b in R["builds"]:
        lab = b["label"]
        if lab not in HAND or not b.get("icc"):
            continue
        app = Path(b["icc"])
        _, at = tags(app)
        desc, mdl = text(at["desc"]), text(at["dmdd"])
        q = "h" if lab == "off-qh" else "l"
        flags = [f for f in HAND[lab] if not f.startswith("-q")]
        base = work / lab / "A10b-cmyk"
        base.parent.mkdir(exist_ok=True)
        shutil.copy2(TI3, str(base) + ".ti3")
        cmd = [CP, "-v", "-D", desc, "-al", f"-q{q}", "-A", "ChromIQ", "-M", mdl,
               "-S", CLAY, "-l300"] + flags + [str(base)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        hand = Path(str(base) + ".icc")
        if r.returncode != 0 or not hand.exists():
            res[lab] = {"cmd": cmd, "error": (r.stderr or r.stdout)[-400:]}
            continue
        ha, ht = tags(hand)
        aa, _ = tags(app)
        diff = sorted(k for k in set(at) | set(ht) if at.get(k) != ht.get(k))
        res[lab] = {"cmd": " ".join(cmd[1:]), "header_identical": aa == ha,
                    "tags_differing": diff, "identical": aa == ha and not diff}
        print(lab, res[lab]["identical"], diff, flush=True)
    (RUN / "bytecheck.json").write_text(json.dumps(res, indent=1))


main()
