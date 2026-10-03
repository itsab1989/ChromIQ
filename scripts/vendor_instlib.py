"""Vendor Argyll's standalone instrument library into native/instlib.

Mirrors spectro/instlib.ksh (Graeme Gill's own standalone packaging script),
minus the tool mains we don't build (spotread.c, oeminst.c) and the display
tools it never included anyway. Every file is copied byte-identical, then the
ChromIQ patches in PATCHES are applied (each must match exactly once, or the
script stops); SHA256s go into PROVENANCE.md.

    python3 scripts/vendor_instlib.py [ARGYLL_SRC [DEST]]
"""
import hashlib
import sys
from pathlib import Path

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "/Users/Basti/Downloads/Argyll_V3.5.0_orig")
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else (
    Path(__file__).resolve().parents[1] / "native" / "instlib")

# ChromIQ's departures from upstream, re-applied on every re-vendor so a new
# Argyll release cannot silently undo them. dest-name -> [(old, new)].
# tests/test_engine_embeds_a_numeric_calibration.py pins the result.
RSPL1_UPSTREAM = (
    "\t\t*((int *)&iv[-1-1]) = n;\t/* Trick to supply grid index in iv[] */\n")
RSPL1_PATCHED = (
    "\t\t/* CHROMIQ PATCH, needed for ChromIQ's use of rspl1: its engine links */\n"
    "\t\t/* xcal.c against this 1-D rspl, a path stock Argyll never reaches */\n"
    "\t\t/* (it uses the full rspl). The contract above, rspl.h and rspl.c put */\n"
    "\t\t/* the index at iv[-e-1], i.e. iv[-0-1] here, and xcal.c reads it at */\n"
    "\t\t/* in[-0-1]; upstream 3.5.0 writes iv[-1-1]. Unpatched, every curve */\n"
    "\t\t/* came from an uninitialised index: an all-nan CAL table in the .ti3 */\n"
    "\t\t/* of any -K/-I chart. scripts/vendor_instlib.py re-applies this; */\n"
    "\t\t/* tests/test_engine_embeds_a_numeric_calibration.py pins it. */\n"
    "\t\t*((int *)&iv[-0-1]) = n;\t/* Trick to supply grid index in iv[] */\n"
)
# #148: the instrument-button beep on a macOS build that is not UNIX_APPLE
# (see the CHROMIQ_APPLE_BEEP note in native/chartread_helper/CMakeLists.txt).
# In the tree since 482d4f7c; recorded here so a re-vendor keeps it.
CONV_PATCHES = [
    ("#endif\n#endif /* UNIX_APPLE */\n\n#undef DEBUG\n",
     "#endif\n#endif /* UNIX_APPLE */\n\n"
     "/* ChromIQ (#148): the beep, and only the beep, on a macOS build that is\n"
     " * deliberately NOT UNIX_APPLE. Defining that symbol would also switch Argyll's\n"
     " * HID/USB layer, which this engine has no reason to change \u2014 so just the one\n"
     " * header the alert sound needs. AudioToolbox is linked by the CMake build. */\n"
     "#if defined(CHROMIQ_APPLE_BEEP) && !defined(UNIX_APPLE)\n"
     "# include <AudioToolbox/AudioServices.h>\n"
     "#endif\n\n#undef DEBUG\n"),
    ("\tSysBeep((beep_msec * 60)/1000);\n# endif\n#else\t/* UNIX */\n"
     "\t/* Linux is pretty lame in this regard... */\n",
     "\tSysBeep((beep_msec * 60)/1000);\n# endif\n"
     "#elif defined(CHROMIQ_APPLE_BEEP)\n"
     "\t/* ChromIQ (#148): this engine is built without UNIX_APPLE, because that\n"
     "\t * symbol also switches the HID/USB layer. Plain UNIX would write a BEL to\n"
     "\t * stdout \u2014 which ChromIQ reads as its JSON channel, so the cue after the\n"
     "\t * instrument's button is pressed was swallowed instead of heard. */\n"
     "\tAudioServicesPlayAlertSound(kUserPreferredAlert);\n"
     "#else\t/* UNIX */\n\t/* Linux is pretty lame in this regard... */\n"),
    ("\t\t\tSysBeep((msec * 60)/1000);\n# endif\n#else\t/* UNIX */\n"
     "\t\tfprintf(stdout, \"\\a\"); fflush(stdout);\n",
     "\t\t\tSysBeep((msec * 60)/1000);\n# endif\n"
     "#elif defined(CHROMIQ_APPLE_BEEP)\n"
     "\t\tAudioServicesPlayAlertSound(kUserPreferredAlert);   /* ChromIQ #148 */\n"
     "#else\t/* UNIX */\n\t\tfprintf(stdout, \"\\a\"); fflush(stdout);\n"),
]
PATCHES = {
    "rspl1.c": [(RSPL1_UPSTREAM, RSPL1_PATCHED)],
    "conv.c": CONV_PATCHES,
}

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
patched = []
for rel, dest in FILES:
    s = SRC / rel
    d = DST / dest
    data = s.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    lines.append(f"| `{dest}` | `{rel}` | `{h[:16]}…` |")
    for old, new in PATCHES.get(dest, ()):
        text = data.decode("utf-8", "surrogateescape")
        if text.count(old) != 1:
            if new in text:
                sys.exit(f"{rel}: upstream already carries the ChromIQ patch; "
                         "drop it from PATCHES")
            sys.exit(f"{rel}: the ChromIQ patch does not apply (expected the "
                     "upstream line exactly once); re-check it by hand")
        data = text.replace(old, new).encode("utf-8", "surrogateescape")
    if dest in PATCHES:
        ph = hashlib.sha256(data).hexdigest()
        patched.append(f"| `{dest}` | `{h[:16]}…` | `{ph[:16]}…` |")
    d.write_bytes(data)

prov = DST / "PROVENANCE.md"
prov.write_text(
    "# Vendored ArgyllCMS standalone instrument library\n\n"
    "These files are a subset of ArgyllCMS 3.5.0 by Graeme W. Gill, copied\n"
    "byte-identical from the official source distribution (except the two\n"
    "patched files listed below), following the file list of Graeme's own\n"
    "standalone packaging script\n"
    "`spectro/instlib.ksh` (the \"instlib\" distribution, GPLv2-or-later —\n"
    "see License2.txt; `chartread.c.orig` is from the main tree, AGPLv3 —\n"
    "see License.txt). `sa_config.h` is `h/aconfig.h` renamed, exactly as\n"
    "instlib.ksh does.\n\n"
    "ChromIQ's fork lives in `../chartread_helper/` and diffs against\n"
    "`chartread.c.orig`. To bump Argyll: re-run `scripts/vendor_instlib.py`\n"
    "against the new source tree and rebuild.\n\n"
    "## ChromIQ patches\n\n"
    "Two library files depart from upstream. `scripts/vendor_instlib.py`\n"
    "re-applies both patches on every re-vendor (its `PATCHES` table), and\n"
    "stops if one no longer applies.\n\n"
    "- **`rspl1.c`, `set_rspl`**: upstream writes the grid index at\n"
    "  `iv[-1-1]`. The function's own comment, `rspl.h` and the full `rspl.c`\n"
    "  put it at `iv[-e-1]`, which for this 1-D spline is `iv[-0-1]`, and\n"
    "  `xcal.c` reads it there. Unpatched, every calibration curve the engine\n"
    "  resamples comes from an uninitialised index, so the `.ti3` of any chart\n"
    "  carrying a printer calibration (`-K`/`-I`) got an all-`nan` CAL table\n"
    "  that colprof refuses. The fix is needed for ChromIQ's use of rspl1:\n"
    "  stock Argyll links the full rspl and never reaches this line.\n"
    "- **`conv.c`, `msec_beep`/`normal_beep`** (#148): under\n"
    "  `CHROMIQ_APPLE_BEEP` the beep plays through AudioToolbox instead of\n"
    "  writing a BEL to stdout, which is the engine's JSON channel. The macOS\n"
    "  build is deliberately not `UNIX_APPLE` (see `CMakeLists.txt`).\n\n"
    "| patched file | upstream sha256 (first 16) | shipped sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(patched) + "\n\n"
    "## Files\n\n"
    "- Upstream: https://www.argyllcms.com/ (Argyll_V3.5.0)\n\n"
    "| vendored file | upstream path | upstream sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(lines) + "\n"
, encoding="utf-8")
print(f"vendored {len(FILES)} files → {DST}")
