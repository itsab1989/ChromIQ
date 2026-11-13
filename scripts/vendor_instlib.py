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
# The i1Pro 2 indicator lights (Preferences > Beta, 2026-11-13). Argyll has the
# request (0xD6, `i1pro2_indLEDseq`) but every caller is under `#ifdef NEVER`.
# These patches add a small, separate path that can send exactly three byte
# sequences, the three a recording of X-Rite's i1Profiler 3.8.6 showed it
# sending to a user's own i1Pro 2 Rev E (one white, two forms of off), and
# only after ChromIQ's helper has asked for it (`i1pro2_cq_lights_begin`).
# Until then every hook below returns at once, so with the option off the
# driver does exactly what upstream does.
# tests/test_i1pro2_lights_driver.py pins the bytes, the call sites and the
# wire trace against an upstream build.
I1PRO_IMP_H_LIGHTS = [
    ("\tvolatile double trigstamp;\t/* meas_delay() trigger timestamp */\n"
     "\n}; typedef struct _i1proimp i1proimp;\n",
     "\tvolatile double trigstamp;\t/* meas_delay() trigger timestamp */\n"
     "\n"
     "\t/* CHROMIQ PATCH: i1Pro 2 indicator lights (Beta). cq_lights 0 = not in\n"
     "\t * use, the calloc default, and then every light hook returns at once. */\n"
     "\tint cq_lights;\n"
     "\tunsigned int cq_lights_slow_ms;\t/* msec_time() of the last slow off */\n"
     "\n}; typedef struct _i1proimp i1proimp;\n"),
    ("#ifdef __cplusplus\n\t}\n#endif\n\n#define I1PRO_IMP\n",
     "/* CHROMIQ PATCH: i1Pro 2 indicator lights (Beta), see i1pro_imp.c. Every\n"
     " * entry returns at once unless ChromIQ's helper called ..._begin(). */\n"
     "int i1pro2_cq_lights_begin(void *pp);\t/* ChromIQ's helper only */\n"
     "void i1pro2_cq_lights_end(void *pp);\t/* off now if needed, then never again */\n"
     "void i1pro2_cq_lights_ready(void *pp);\t/* white, if in use and off */\n"
     "void i1pro2_cq_lights_trigger(void *pp);\t/* off, before a trigger */\n"
     "void i1pro2_cq_lights_eeprom(void *pp);\t/* off now, before an EEPROM read */\n"
     "extern void (*i1pro2_cq_lights_note)(int seq, int icom_err);\n"
     "\n#ifdef __cplusplus\n\t}\n#endif\n\n#define I1PRO_IMP\n"),
]
I1PRO_IMP_C_LIGHTS_BLOCK = r"""
/* ============================================================ */
/* CHROMIQ PATCH: the i1Pro 2 indicator lights (Preferences > Beta, 2026-11-13).
 *
 * Where the knowledge comes from: the request and the sequence format are
 * Argyll's own (i1pro2_indLEDseq above; all its callers are under #ifdef NEVER;
 * its notes say a running sequence interferes with an EEPROM read). The three
 * sequences are byte for byte the ones X-Rite's i1Profiler 3.8.6 sent to a
 * user's own i1Pro 2 Rev E in two USB recordings (ChromIQ issue #129), each
 * used where i1Profiler used it:
 *   WHITE     once the instrument was open and ready;
 *   OFF_SLOW  before every calibration and every scan;
 *   OFF_NOW   when it let the instrument go, directly before EEPROM access.
 * Argyll's own i1pro2_indLEDoff bytes were never seen on the wire and are not
 * used. Nothing else is ever sent from here, and no EEPROM write is added.
 * Sending WHITE again after every reading is ChromIQ's use of the recorded
 * WHITE (the recording was made on a measuring table, where i1Profiler kept
 * the lights dark): it is not something i1Profiler was seen doing.
 *
 * Rules, all enforced in this block:
 *  - nothing happens until ChromIQ's helper calls i1pro2_cq_lights_begin(),
 *    which it does only when the user switched the option on, and which
 *    refuses anything but an inited i1Pro 2 whose EEPROM says it has the user
 *    indicator LEDs (I1PRO_CAP2_IND_LED). Every entry checks dtype first and
 *    returns at once while cq_lights is 0;
 *  - OFF_SLOW before every measurement trigger (i1pro_trigger_one_measure,
 *    which every calibration and reading of this driver passes through);
 *    OFF_NOW before any EEPROM read and when the instrument is closed, so no
 *    sequence is left running; WHITE when a measurement or a calibration has
 *    returned and the instrument waits for the user again;
 *  - every send is made on the thread that called into the driver, never
 *    while a trigger thread may still send its 0xD4: WHITE is skipped while
 *    one is pending, and nothing is lit once a trigger has been prepared;
 *  - a request that fails is never retried and never fails anything: the
 *    lights are given up for the rest of the session (cq_lights = DONE, not
 *    even a final off, because the instrument may still be waiting for the
 *    bytes of the failed one), the helper is told once, the caller carries on.
 */

#define CQ_LIGHTS_UNUSED 0	/* the default: never asked for, never sends */
#define CQ_LIGHTS_DARK   1	/* in use, the last sequence was an off (or none yet) */
#define CQ_LIGHTS_LIT    2	/* in use, the last sequence was WHITE */
#define CQ_LIGHTS_DONE   3	/* ended or given up: never sends again */

#define CQ_LIGHTS_WHITE    1
#define CQ_LIGHTS_OFF_SLOW 2
#define CQ_LIGHTS_OFF_NOW  3

#define CQ_LIGHTS_TOUT       1.0	/* s per transfer; a good one takes a few ms */
#define CQ_LIGHTS_TOUT_CLOSE 0.5	/* at the close, inside the helper's 1.5 s */
#define CQ_LIGHTS_SLOW_MS    2500	/* OFF_SLOW plays for about 2 s */

/* WHITE: "off for 0x3640 clocks (about 1 s), then all six LEDs on, forever" */
static const unsigned char cq_lights_seq_white[32] = {
	0x00, 0x00, 0x00, 0x02,					/* two blocks */
	0x00, 0x00, 0x00, 0x0a,					/* block 1: 10 bytes */
	0x00, 0x00, 0x00, 0x01,					/*   played once */
	0x00, 0x36, 0x40,						/*   mask 00 for 0x3640 clocks */
	0x00, 0x00, 0x01,						/*   mask 00 for 1 clock */
	0x00, 0x00, 0x00, 0x0a,					/* block 2: 10 bytes */
	0xff, 0xff, 0xff, 0xff,					/*   repeated forever */
	0x3f, 0x36, 0x40,						/*   mask 3f for 0x3640 clocks */
	0x00, 0x00, 0x01						/*   mask 00 for 1 clock */
};

/* OFF_SLOW: "off for 0x3640 clocks, then 1 clock, played twice, then end" */
static const unsigned char cq_lights_seq_off_slow[18] = {
	0x00, 0x00, 0x00, 0x01,					/* one block */
	0x00, 0x00, 0x00, 0x0a,					/* 10 bytes */
	0x00, 0x00, 0x00, 0x02,					/* played twice */
	0x00, 0x36, 0x40,						/* mask 00 for 0x3640 clocks */
	0x00, 0x00, 0x01						/* mask 00 for 1 clock */
};

/* OFF_NOW: "off for 1 clock, played twice, then end" */
static const unsigned char cq_lights_seq_off_now[15] = {
	0x00, 0x00, 0x00, 0x01,					/* one block */
	0x00, 0x00, 0x00, 0x07,					/* 7 bytes */
	0x00, 0x00, 0x00, 0x02,					/* played twice */
	0x00, 0x00, 0x01						/* mask 00 for 1 clock */
};

/* Set by ChromIQ's helper to hear about a failed light request (one call per
 * session at most). seq is CQ_LIGHTS_WHITE / _OFF_SLOW / _OFF_NOW (1/2/3). */
void (*i1pro2_cq_lights_note)(int seq, int icom_err) = NULL;

/* The i1proimp of an i1Pro 2 whose lights are in use, else NULL. dtype is
 * read first: it is in every instrument's base object, so this is safe to
 * ask of any inst, and only an i1Pro 2 object is ever looked into. */
static i1proimp *cq_lights_m(i1pro *p) {
	i1proimp *m;
	if (p == NULL || p->dtype != instI1Pro2 || (m = (i1proimp *)p->m) == NULL
	 || p->icom == NULL)
		return NULL;
	if (m->cq_lights != CQ_LIGHTS_DARK && m->cq_lights != CQ_LIGHTS_LIT)
		return NULL;
	return m;
}

/* A trigger thread that has not sent its 0xD4 yet. */
static int cq_lights_trigger_pending(i1proimp *m) {
	return m->trig_thread != NULL && m->tr_t2 == 0;
}

/* Send one of the three sequences. The only place a light request is made. */
static void cq_lights_send(i1pro *p, int which, double tout) {
	i1proimp *m = (i1proimp *)p->m;
	const unsigned char *seq;
	int size;
	unsigned char pbuf[4];
	int wbytes = 0;
	int se;

	if (which == CQ_LIGHTS_WHITE) {
		seq = cq_lights_seq_white;    size = (int)sizeof(cq_lights_seq_white);
	} else if (which == CQ_LIGHTS_OFF_SLOW) {
		seq = cq_lights_seq_off_slow; size = (int)sizeof(cq_lights_seq_off_slow);
	} else {
		which = CQ_LIGHTS_OFF_NOW;
		seq = cq_lights_seq_off_now;  size = (int)sizeof(cq_lights_seq_off_now);
	}

	int2buf(pbuf, size);
	se = p->icom->usb_control(p->icom,
		               IUSB_ENDPOINT_OUT | IUSB_REQ_TYPE_VENDOR | IUSB_REQ_RECIP_DEVICE,
	                   0xD6, 0, 0, pbuf, 4, NULL, tout);
	if (icoms2i1pro_err(se) == I1PRO_OK)
		se = p->icom->usb_write(p->icom, NULL, 0x03, (unsigned char *)seq, size,
		                        &wbytes, tout);

	if (icoms2i1pro_err(se) != I1PRO_OK || wbytes != size) {
		m->cq_lights = CQ_LIGHTS_DONE;		/* given up for this session */
		a1logd(p->log,1,"i1pro2 lights: sequence %d failed, ICOM err 0x%x, wrote %d of %d;"
		                " lights not used again\n", which, se, wbytes, size);
		if (i1pro2_cq_lights_note != NULL)
			i1pro2_cq_lights_note(which, se);
		return;
	}
	if (which == CQ_LIGHTS_WHITE)
		m->cq_lights = CQ_LIGHTS_LIT;
	else
		m->cq_lights = CQ_LIGHTS_DARK;
	if (which == CQ_LIGHTS_OFF_SLOW)
		m->cq_lights_slow_ms = msec_time();
	else
		m->cq_lights_slow_ms = 0;
	a1logd(p->log,2,"i1pro2 lights: sequence %d sent\n", which);
}

/* Something may still be playing: WHITE, or an OFF_SLOW of the last 2.5 s. */
static int cq_lights_playing(i1proimp *m) {
	return m->cq_lights == CQ_LIGHTS_LIT
	    || (m->cq_lights_slow_ms != 0
	        && (msec_time() - m->cq_lights_slow_ms) < CQ_LIGHTS_SLOW_MS);
}

/* Before a trigger: OFF_SLOW, as i1Profiler sends before calibrations and
 * scans, when lit. */
void i1pro2_cq_lights_trigger(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || m->cq_lights != CQ_LIGHTS_LIT)
		return;
	cq_lights_send(p, CQ_LIGHTS_OFF_SLOW, CQ_LIGHTS_TOUT);
}

/* Before an EEPROM read: OFF_NOW, when anything may still be playing. */
void i1pro2_cq_lights_eeprom(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || !cq_lights_playing(m))
		return;
	cq_lights_send(p, CQ_LIGHTS_OFF_NOW, CQ_LIGHTS_TOUT);
}

/* WHITE, when in use and off, and no trigger is still to be sent. */
void i1pro2_cq_lights_ready(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || m->cq_lights != CQ_LIGHTS_DARK || cq_lights_trigger_pending(m))
		return;
	cq_lights_send(p, CQ_LIGHTS_WHITE, CQ_LIGHTS_TOUT);
}

/* Start using the lights. ChromIQ's helper calls this, and only when the user
 * switched the option on. Returns non-zero when they are in use. */
int i1pro2_cq_lights_begin(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;

	if (p == NULL || p->dtype != instI1Pro2 || !p->gotcoms || !p->inited
	 || (m = (i1proimp *)p->m) == NULL || p->icom == NULL)
		return 0;
	if ((m->capabilities2 & I1PRO_CAP2_IND_LED) == 0)
		return 0;
	if (m->cq_lights == CQ_LIGHTS_UNUSED) {
		m->cq_lights = CQ_LIGHTS_DARK;
		i1pro2_cq_lights_ready(p);
	}
	return m->cq_lights == CQ_LIGHTS_DARK || m->cq_lights == CQ_LIGHTS_LIT;
}

/* Stop using the lights: OFF_NOW when anything may still be playing (and no
 * trigger is still to be sent), then never send again. */
void i1pro2_cq_lights_end(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL)
		return;
	if (cq_lights_playing(m) && !cq_lights_trigger_pending(m))
		cq_lights_send(p, CQ_LIGHTS_OFF_NOW, CQ_LIGHTS_TOUT_CLOSE);
	m->cq_lights = CQ_LIGHTS_DONE;
}
"""
I1PRO_IMP_C_LIGHTS = [
    # OFF_SLOW before every trigger. Every measurement of this driver,
    # calibration included, is triggered through i1pro_trigger_one_measure.
    ("\tint measmodeflags2;\t/* Rev E Measurement mode command flags */\n\n"
     "\t/* Sanity check in case bad value was restored, due to switch */\n",
     "\tint measmodeflags2;\t/* Rev E Measurement mode command flags */\n\n"
     "\t/* CHROMIQ PATCH: the indicator lights go off before every trigger (Beta, */\n"
     "\t/* a no-op unless ChromIQ's helper switched them on). */\n"
     "\ti1pro2_cq_lights_trigger(p);\n\n"
     "\t/* Sanity check in case bad value was restored, due to switch */\n"),
    # OFF_NOW before any EEPROM read (Argyll: a running sequence interferes).
    ("\tif (size >= 0x10000)\n\t\treturn I1PRO_INT_EETOOBIG;\n\n"
     "\ta1logd(p->log,2,\"i1pro_readEEProm: address",
     "\tif (size >= 0x10000)\n\t\treturn I1PRO_INT_EETOOBIG;\n\n"
     "\t/* CHROMIQ PATCH: no light sequence may run during an EEPROM read (Beta, */\n"
     "\t/* a no-op unless ChromIQ's helper switched the lights on). */\n"
     "\ti1pro2_cq_lights_eeprom(p);\n\n"
     "\ta1logd(p->log,2,\"i1pro_readEEProm: address"),
    # OFF_NOW when the instrument is closed, before anything is torn down.
    ("\t\ti1pro_state *s;\n\t\ti1pro_code ev;\n\n"
     "\t\tif (p->dtype != instI1Pro2 && (ev = i1pro_update_log(p)) != I1PRO_OK) {\n",
     "\t\ti1pro_state *s;\n\t\ti1pro_code ev;\n\n"
     "\t\t/* CHROMIQ PATCH: lights off before the instrument is let go (Beta, */\n"
     "\t\t/* a no-op unless ChromIQ's helper switched them on). */\n"
     "\t\ti1pro2_cq_lights_end(p);\n\n"
     "\t\tif (p->dtype != instI1Pro2 && (ev = i1pro_update_log(p)) != I1PRO_OK) {\n"),
    # The block itself, right after Argyll's own (uncalled) light functions.
    ("\ta1logd(p->log,2,\"i1pro2_indLEDoff: returning ICOM err 0x%x\\n\",rv);\n"
     "\n\treturn rv;\n}\n",
     "\ta1logd(p->log,2,\"i1pro2_indLEDoff: returning ICOM err 0x%x\\n\",rv);\n"
     "\n\treturn rv;\n}\n" + I1PRO_IMP_C_LIGHTS_BLOCK),
]
# WHITE again once a measurement or a calibration has returned, whatever it
# returned: the instrument then waits for the user.
I1PRO_C_LIGHTS = [
    ("\trv = i1pro_imp_measure(p, vals, npatch, instClamp);\n",
     "\trv = i1pro_imp_measure(p, vals, npatch, instClamp);\n"
     "\ti1pro2_cq_lights_ready(p);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
    ("\trv = i1pro_imp_measure(p, val, 1, clamp);\n",
     "\trv = i1pro_imp_measure(p, val, 1, clamp);\n"
     "\ti1pro2_cq_lights_ready(p);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
    ("\trv = i1pro_imp_calibrate(p, calt, calc, idtype, id);\n",
     "\trv = i1pro_imp_calibrate(p, calt, calc, idtype, id);\n"
     "\ti1pro2_cq_lights_ready(p);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
]
PATCHES = {
    "rspl1.c": [(RSPL1_UPSTREAM, RSPL1_PATCHED)],
    "conv.c": CONV_PATCHES,
    "i1pro_imp.h": I1PRO_IMP_H_LIGHTS,
    "i1pro_imp.c": I1PRO_IMP_C_LIGHTS,
    "i1pro.c": I1PRO_C_LIGHTS,
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
    "byte-identical from the official source distribution (except the\n"
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
    "Five library files depart from upstream. `scripts/vendor_instlib.py`\n"
    "re-applies every patch on every re-vendor (its `PATCHES` table), and\n"
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
    "  build is deliberately not `UNIX_APPLE` (see `CMakeLists.txt`).\n"
    "- **`i1pro_imp.c`, `i1pro_imp.h`, `i1pro.c`: the i1Pro 2 indicator\n"
    "  lights** (Preferences > Beta, 2026-11-13). A separate path that can send\n"
    "  exactly three light sequences to an i1Pro 2 (request 0xD6, then the\n"
    "  bytes on bulk endpoint 0x03): WHITE (32 bytes, off about 1 s, then all\n"
    "  six LEDs on) when the instrument waits for the user, OFF_SLOW (18 bytes)\n"
    "  before every measurement trigger, and OFF_NOW (15 bytes, off at once)\n"
    "  before any EEPROM read and when the instrument is closed. Inert until\n"
    "  ChromIQ's helper calls `i1pro2_cq_lights_begin` (only with the option\n"
    "  on, `--i1pro2-lights`), which refuses anything but an inited i1Pro 2\n"
    "  whose EEPROM reports the user indicator LEDs (`I1PRO_CAP2_IND_LED`); a\n"
    "  failed request gives the lights up for the session and fails nothing.\n"
    "  Nothing is written to the EEPROM. Where the knowledge comes from:\n"
    "  Argyll's own request and sequence format (`i1pro2_indLEDseq` and its\n"
    "  comment; every caller is under `#ifdef NEVER`, and Argyll's notes say a\n"
    "  running sequence interferes with an EEPROM read), and two USB\n"
    "  recordings a user made of X-Rite's i1Profiler 3.8.6 with his own\n"
    "  i1Pro 2 Rev E (ChromIQ issue #129), in which i1Profiler sent exactly\n"
    "  these three sequences byte for byte, each where ChromIQ sends it\n"
    "  (WHITE at open, OFF_SLOW before calibrations and scans, OFF_NOW at\n"
    "  release). WHITE after every reading is ChromIQ's own use of the\n"
    "  recorded WHITE (the recording was made on a measuring table, where\n"
    "  i1Profiler kept the lights dark). Argyll's own `i1pro2_indLEDoff` bytes\n"
    "  were never seen on the wire and are not used.\n"
    "  Not tested on a real i1Pro 2 by the project.\n\n"
    "| patched file | upstream sha256 (first 16) | shipped sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(patched) + "\n\n"
    "## Files\n\n"
    "- Upstream: https://www.argyllcms.com/ (Argyll_V3.5.0)\n\n"
    "| vendored file | upstream path | upstream sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(lines) + "\n"
, encoding="utf-8")
print(f"vendored {len(FILES)} files → {DST}")
