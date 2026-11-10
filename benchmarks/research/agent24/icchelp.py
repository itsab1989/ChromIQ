import struct
from pathlib import Path
import numpy as np

def pad4(b): return b + b"\0" * (-len(b) % 4)
def s15(x): return struct.pack(">i", int(round(x * 65536)))
def tags_of(d):
    n = struct.unpack(">I", d[128:132])[0]
    return [(d[132+12*i:136+12*i].decode(), d[o:o+l]) for i in range(n) for (o, l) in [struct.unpack(">II", d[136+12*i:144+12*i])]]
def write(path, hdr_src, tags, ver=None, creator=None, intent=None, flags=None):
    h = bytearray(hdr_src[:128])
    if ver: h[8:12] = bytes(ver)
    if creator is not None: h[80:84] = creator; h[4:8] = b"\0\0\0\0"
    if intent is not None: h[64:68] = struct.pack(">I", intent)
    if flags is not None: h[44:48] = struct.pack(">I", flags)
    h[84:100] = b"\0" * 16
    base = 128 + 4 + 12 * len(tags); data = b""; ents = []
    for s, b in tags:
        b = pad4(b); ents.append((s, base + len(data), len(b))); data += b
    h[0:4] = struct.pack(">I", base + len(data))
    Path(path).write_bytes(bytes(h) + struct.pack(">I", len(tags)) + b"".join(s.encode() + struct.pack(">II", o, n) for s, o, n in ents) + data)
    return Path(path)
def curv(vals):
    v = np.round(np.clip(np.asarray(vals, float), 0, 65535)).astype(int)
    return pad4(b"curv" + b"\0" * 4 + struct.pack(">I", len(v)) + struct.pack(">%dH" % len(v), *v))
def lut_ab(sig, nin, nout, bcurves, clut_grid, clut_u16, acurves):
    clut = pad4(bytes([clut_grid] * nin + [0] * (16 - nin)) + bytes([2, 0, 0, 0]) + struct.pack(">%dH" % clut_u16.size, *clut_u16.reshape(-1).astype(int)))
    Bb = b"".join(bcurves); Ab = b"".join(acurves)
    off_b = 32; off_c = off_b + len(Bb); off_a = off_c + len(clut)
    return sig + b"\0" * 4 + bytes([nin, nout, 0, 0]) + struct.pack(">5I", off_b, 0, 0, off_c, off_a) + Bb + clut + Ab
