"""Vendor Argyll's standalone instrument library into native/instlib.

Mirrors spectro/instlib.ksh (Graeme Gill's own standalone packaging script),
minus the tool mains we don't build (spotread.c, oeminst.c) and the display
tools it never included anyway. Every file is copied byte-identical; SHA256s
go into PROVENANCE.md.
"""
import hashlib
import shutil
from pathlib import Path

SRC = Path("/Users/Basti/Downloads/Argyll_V3.5.0_orig")
DST = Path("/Users/Basti/develop/ChromIQ/native/instlib")

# (source-relative, dest-name) — dest flat like the instlib zip
FILES = []

def add(rel, dest=None):
    FILES.append((rel, dest or Path(rel).name))

# instlib.ksh: H_FILES / NUMLIB / CGATS / XICC / RSPL
add("h/sort.h")
for f in ("numsup.h", "numsup.c"):
    add(f"numlib/{f}")
for f in ("pars.h", "pars.c", "parsstd.c", "cgats.h", "cgats.c", "cgatsstd.c"):
    add(f"cgats/{f}")
for f in ("xspect.h", "xspect.c", "ccss.h", "ccss.c", "ccmx.h", "ccmx.c",
          "xcolorants.h", "xcolorants.c", "xcal.h", "xcal.c"):
    add(f"xicc/{f}")
for f in ("rspl1.h", "rspl1.c"):
    add(f"rspl/{f}")

# instlib.ksh: SPECTRO_FILES minus spotread.c / Makefile.* (tool + build files)
SPECTRO = """License2.txt pollem.h pollem.c conv.h conv.c sa_conv.h sa_conv.c
aglob.c aglob.h hidio.h hidio.c icoms.h dev.h inst.h inst.c insttypes.c
insttypes.h insttypeinst.h instappsup.c instappsup.h disptechs.h disptechs.c
dtp20.c dtp20.h dtp22.c dtp22.h dtp41.c dtp41.h dtp51.c dtp51.h dtp92.c
dtp92.h ss.h ss.c ss_imp.h ss_imp.c i1disp.c i1disp.h i1d3.h i1d3.c i1pro.h
i1pro.c i1pro_imp.h i1pro_imp.c i1pro3.h i1pro3.c i1pro3_imp.h i1pro3_imp.c
munki.h munki.c munki_imp.h munki_imp.c hcfr.c hcfr.h huey.c huey.h
colorhug.c colorhug.h spyd2.c spyd2.h spydX.c spydX.h specbos.h specbos.c
kleink10.h kleink10.c ex1.c ex1.h smcube.h smcube.c cubecal.h
spydX2.c spydX2.h
oemarch.c oemarch.h vinflate.c inflate.c LzmaDec.c LzmaDec.h LzmaTypes.h
icoms.c icoms_nt.c icoms_ux.c iusb.h usbio.h usbio.c usbio_nt.c usbio_w0.c
usbio_dk.c usbio_ox.c usbio_lx.c usbio_bsd.c rspec.h rspec.c xdg_bds.c
xdg_bds.h base64.h base64.c xrga.h xrga.c driver_api.h""".split()
for f in SPECTRO:
    add(f"spectro/{f}")

# instlib.ksh renames aconfig.h → sa_config.h
add("h/aconfig.h", "sa_config.h")
# chartread's one extra dependency per the Jamfile
add("target/alphix.c")
add("target/alphix.h")
# chartread.c itself is AGPL3 from the main tree — keep both license texts
add("License.txt")
# the pristine upstream chartread.c, for provenance/diffing (fork lives elsewhere)
add("spectro/chartread.c", "chartread.c.orig")

DST.mkdir(parents=True, exist_ok=True)
lines = []
for rel, dest in FILES:
    s = SRC / rel
    d = DST / dest
    data = s.read_bytes()
    d.write_bytes(data)
    h = hashlib.sha256(data).hexdigest()
    lines.append(f"| `{dest}` | `{rel}` | `{h[:16]}…` |")

prov = DST / "PROVENANCE.md"
prov.write_text(
    "# Vendored ArgyllCMS standalone instrument library\n\n"
    "These files are an **unmodified** subset of ArgyllCMS 3.5.0 by Graeme\n"
    "W. Gill, copied byte-identical from the official source distribution,\n"
    "following the file list of Graeme's own standalone packaging script\n"
    "`spectro/instlib.ksh` (the \"instlib\" distribution, GPLv2-or-later —\n"
    "see License2.txt; `chartread.c.orig` is from the main tree, AGPLv3 —\n"
    "see License.txt). `sa_config.h` is `h/aconfig.h` renamed, exactly as\n"
    "instlib.ksh does.\n\n"
    "No source changes — ChromIQ's fork lives in `../chartread_helper/` and\n"
    "diffs against `chartread.c.orig`. To bump Argyll: re-run\n"
    "`scripts/vendor_instlib.py` against the new source tree and rebuild.\n\n"
    "- Upstream: https://www.argyllcms.com/ (Argyll_V3.5.0)\n\n"
    "| vendored file | upstream path | sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(lines) + "\n"
, encoding="utf-8")
print(f"vendored {len(FILES)} files → {DST}")
