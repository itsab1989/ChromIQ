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
     "\tint cq_lights_prog;\t\t/* the last sequence sent (CQ_LIGHTS_WHITE ..) */\n"
     "\tint cq_lights_signals;\t/* the helper's choices (0/0 = 4.3.33) */\n"
     "\tint cq_lights_left_on;\n"
     "\tint cq_lights_reading;\t/* inside read_strip / read_sample */\n"
     "\tint cq_lights_press_count;\t/* switch_count when that reading began */\n"
     "\tint cq_lights_owed;\t\t/* a result for a reported strip is owed */\n"
     "\tunsigned int cq_lights_owed_ms;\n"
     "\n"
     "}; typedef struct _i1proimp i1proimp;\n"),
    ("#ifdef __cplusplus\n\t}\n#endif\n\n#define I1PRO_IMP\n",
     "/* CHROMIQ PATCH: i1Pro 2 indicator lights (Beta), see i1pro_imp.c. Every\n"
     " * entry returns at once unless ChromIQ's helper called ..._begin(). */\n"
     "int i1pro2_cq_lights_begin(void *pp);\t/* ChromIQ's helper only */\n"
     "int i1pro2_cq_lights_end(void *pp);\t/* off now if needed, then never again; 1 = known off */\n"
     "void i1pro2_cq_lights_ready(void *pp);\t/* white, if in use and off */\n"
     "void i1pro2_cq_lights_trigger(void *pp);\t/* off, before a trigger */\n"
     "void i1pro2_cq_lights_eeprom(void *pp);\t/* off now, before an EEPROM read */\n"
     "void i1pro2_cq_lights_reading(void *pp, int on);\t/* around a reading */\n"
     "void i1pro2_cq_lights_after_read(void *pp);\t/* ready, unless the helper decides */\n"
     "void i1pro2_cq_lights_options(void *pp, int signals, int left_on);\t/* before begin */\n"
     "void i1pro2_cq_lights_owe(void *pp);\t/* a result is owed for a reported strip */\n"
     "int i1pro2_cq_lights_owed_ms(void *pp);\t/* how long; -1 = none */\n"
     "void i1pro2_cq_lights_result(void *pp, int good);\t/* 1 green, 0 red, -1 ready */\n"
     "int i1pro2_cq_lights_choices(void *pp);\t/* in use: 1 signals, 2 left on */\n"
     "int i1pro2_cq_lights_firmware(void *pp);\t/* firmware, -1 = not in use */\n"
     "extern void (*i1pro2_cq_lights_note)(int seq, int icom_err);\n"
     "extern void (*i1pro2_cq_lights_sent)(int seq);\t/* each sequence sent */\n"
     "\n"
     "#ifdef __cplusplus\n"
     "\t}\n"
     "#endif\n"
     "\n"
     "#define I1PRO_IMP\n"),
]
I1PRO_IMP_C_LIGHTS_BLOCK = r"""
/* ============================================================ */
/* CHROMIQ PATCH: the i1Pro 2 indicator lights (Preferences > Beta, 2026-11-13).
 *
 * Where the knowledge comes from: the request and the sequence format are
 * Argyll's own (i1pro2_indLEDseq above; all its callers are under #ifdef NEVER;
 * its notes say a running sequence interferes with an EEPROM read). Every
 * sequence is byte for byte one that X-Rite's i1Profiler 3.8.6 sent to a
 * user's own i1Pro 2 Rev E in a USB recording, each used where i1Profiler
 * used it:
 *   WHITE     once the instrument was open and ready (#129 and the Windows
 *             recording);
 *   OFF_SLOW  before every calibration (both), and every table scan (#129);
 *   OFF_NOW   when it let the instrument go, directly before EEPROM access
 *             (#129 only: the Windows recording has no release);
 *   PULSE     ready, after a calibration (Windows; = Argyll's own `b3`);
 *   GREEN2    after a strip or patch it accepted (Windows);
 *   RED2      after a strip it refused (Windows).
 * PULSE, GREEN2 and RED2 are in cq_i1pro2_programs.h, pinned by sha256.
 * Argyll's own i1pro2_indLEDoff bytes were never seen on the wire and are not
 * used. Nothing else is ever sent from here, and no EEPROM write is added.
 *
 * What is sent when depends on two choices the helper passes in
 * (i1pro2_cq_lights_options, before ..._begin). With both at 0 this block
 * sends exactly what ChromIQ 4.3.33 sent:
 *   signals  0: WHITE after every calibration and reading (4.3.33's own use
 *               of the recorded WHITE; i1Profiler sends it only at open).
 *            1: PULSE after a calibration; after a reading nothing here: the
 *               helper sends GREEN2 / RED2 / PULSE (..._result), because only
 *               it and ChromIQ know whether the reading was accepted.
 *   left_on  0: OFF_SLOW before every trigger while lit (4.3.33).
 *            1: i1Profiler's hand-held way: no off before the triggers of a
 *               reading (its dark and lit parts) while a pulse-family program
 *               (PULSE, GREEN2, RED2) plays, and PULSE in place of WHITE as the
 *               ready light. A calibration still starts with OFF_SLOW, as in
 *               the recording, and so does a reading while the steady WHITE of
 *               the open plays (i1Profiler never measured under it).
 *
 * Rules, all enforced in this block:
 *  - nothing happens until ChromIQ's helper calls i1pro2_cq_lights_begin(),
 *    which it does only when the user switched the option on, and which
 *    refuses anything but an inited i1Pro 2 whose EEPROM says it has the user
 *    indicator LEDs (I1PRO_CAP2_IND_LED). Every entry checks dtype first and
 *    returns at once while cq_lights is 0;
 *  - OFF_SLOW before every measurement trigger (i1pro_trigger_one_measure,
 *    which every calibration and reading of this driver passes through),
 *    except as left_on says; OFF_NOW before any EEPROM read and when the
 *    instrument is closed, so no sequence is left running;
 *  - every send is made on the thread that called into the driver, never
 *    while a trigger thread may still send its 0xD4: nothing is lit while one
 *    is pending, and a result the GUI decided is only taken while one is owed
 *    (cq_lights_owed: set by the helper when it reports an accepted strip,
 *    cleared by EVERY trigger), so a late one can never land in a reading;
 *  - a request that fails is never retried and never fails anything: the
 *    lights are given up for the rest of the session (cq_lights = DONE, not
 *    even a final off, because the instrument may still be waiting for the
 *    bytes of the failed one), the helper is told once, the caller carries on.
 */

#include "cq_i1pro2_programs.h"

#define CQ_LIGHTS_UNUSED 0	/* the default: never asked for, never sends */
#define CQ_LIGHTS_DARK   1	/* in use, the last sequence was an off (or none yet) */
#define CQ_LIGHTS_LIT    2	/* in use, the last sequence was not an off */
#define CQ_LIGHTS_DONE   3	/* ended or given up: never sends again */

#define CQ_LIGHTS_WHITE    1
#define CQ_LIGHTS_OFF_SLOW 2
#define CQ_LIGHTS_OFF_NOW  3
#define CQ_LIGHTS_PULSE    4
#define CQ_LIGHTS_GREEN2   5
#define CQ_LIGHTS_RED2     6

#define CQ_LIGHTS_TOUT       0.25	/* s per transfer; a good one takes a few ms */
#define CQ_LIGHTS_TOUT_TRIGGER 0.25	/* between the button and the trigger: short */
#define CQ_LIGHTS_TOUT_CLOSE 0.5	/* at the close, inside the helper's 1.5 s */
#define CQ_LIGHTS_SLOW_MS    2500	/* OFF_SLOW plays for about 2 s */
/* PULSE, GREEN2 and RED2 were recorded on an i1Pro 2 with firmware 634 (as
 * was every other i1Pro 2 recording). They go to any i1Pro 2 this block
 * accepts, exactly as 4.3.33's three sequences do: Argyll's light code has
 * no firmware condition, a program is data in one format through the same
 * request, and anything below firmware 600 is not an i1Pro 2 to Argyll (it is
 * run as a rev A-D, dtype instI1Pro, i1pro_imp.c) and never reaches here. The
 * helper reports the firmware with the session, so a tester's report says it. */

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
 * session at most). seq is CQ_LIGHTS_WHITE .. _RED2 (1-6). */
void (*i1pro2_cq_lights_note)(int seq, int icom_err) = NULL;

/* Set by ChromIQ's helper to hear about every sequence sent (for its log).
 * Called on the thread that sent it, after the transfer. */
void (*i1pro2_cq_lights_sent)(int seq) = NULL;

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

/* Send one of the six sequences. The only place a light request is made. */
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
	} else if (which == CQ_LIGHTS_PULSE) {
		seq = cq_lights_seq_pulse;    size = (int)sizeof(cq_lights_seq_pulse);
	} else if (which == CQ_LIGHTS_GREEN2) {
		seq = cq_lights_seq_green2;   size = (int)sizeof(cq_lights_seq_green2);
	} else if (which == CQ_LIGHTS_RED2) {
		seq = cq_lights_seq_red2;     size = (int)sizeof(cq_lights_seq_red2);
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
		m->cq_lights_owed = 0;
		a1logd(p->log,1,"i1pro2 lights: sequence %d failed, ICOM err 0x%x, wrote %d of %d;"
		                " lights not used again\n", which, se, wbytes, size);
		if (i1pro2_cq_lights_note != NULL)
			i1pro2_cq_lights_note(which, se);
		return;
	}
	if (which == CQ_LIGHTS_OFF_SLOW || which == CQ_LIGHTS_OFF_NOW)
		m->cq_lights = CQ_LIGHTS_DARK;
	else
		m->cq_lights = CQ_LIGHTS_LIT;
	m->cq_lights_prog = which;
	if (which == CQ_LIGHTS_OFF_SLOW)
		m->cq_lights_slow_ms = msec_time();
	else
		m->cq_lights_slow_ms = 0;
	a1logd(p->log,2,"i1pro2 lights: sequence %d sent\n", which);
	if (i1pro2_cq_lights_sent != NULL)
		i1pro2_cq_lights_sent(which);
}

/* Something may still be playing: anything lit, or an OFF_SLOW of the last 2.5 s. */
static int cq_lights_playing(i1proimp *m) {
	return m->cq_lights == CQ_LIGHTS_LIT
	    || (m->cq_lights_slow_ms != 0
	        && (msec_time() - m->cq_lights_slow_ms) < CQ_LIGHTS_SLOW_MS);
}

/* The ready light: WHITE as in 4.3.33, PULSE with either new choice. */
static int cq_lights_ready_prog(i1proimp *m) {
	return (m->cq_lights_signals || m->cq_lights_left_on)
	       ? CQ_LIGHTS_PULSE : CQ_LIGHTS_WHITE;
}

/* Before a trigger: OFF_SLOW, as i1Profiler sends before calibrations and
 * scans, when lit. With left_on, a reading's own triggers leave a
 * pulse-family program running, as i1Profiler does by hand. Every trigger
 * ends a result that is still owed. */
void i1pro2_cq_lights_trigger(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL)
		return;
	m->cq_lights_owed = 0;
	if (m->cq_lights != CQ_LIGHTS_LIT)
		return;
	if (m->cq_lights_left_on && m->cq_lights_reading
	 && (m->cq_lights_prog == CQ_LIGHTS_PULSE || m->cq_lights_prog == CQ_LIGHTS_GREEN2
	     || m->cq_lights_prog == CQ_LIGHTS_RED2))
		return;
	cq_lights_send(p, CQ_LIGHTS_OFF_SLOW, CQ_LIGHTS_TOUT_TRIGGER);
}

/* Before an EEPROM read: OFF_NOW, when anything may still be playing. */
void i1pro2_cq_lights_eeprom(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || !cq_lights_playing(m))
		return;
	cq_lights_send(p, CQ_LIGHTS_OFF_NOW, CQ_LIGHTS_TOUT);
}

/* The ready light, when in use and off, and no trigger is still to be sent.
 * After a calibration (i1pro.c). */
void i1pro2_cq_lights_ready(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || m->cq_lights != CQ_LIGHTS_DARK || cq_lights_trigger_pending(m))
		return;
	cq_lights_send(p, cq_lights_ready_prog(m), CQ_LIGHTS_TOUT);
}

/* Around a reading (read_strip / read_sample, i1pro.c): 1 before, 0 after. */
void i1pro2_cq_lights_reading(void *pp, int on) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL)
		return;
	m->cq_lights_reading = on;
	if (on)
		m->cq_lights_press_count = m->switch_count;
}

/* The instrument's button was pressed since the current reading began (the
 * switch thread counts presses): its trigger is about to be sent. */
static int cq_lights_pressed(i1proimp *m) {
	return m->cq_lights_reading && m->switch_count != m->cq_lights_press_count;
}

/* After a reading (i1pro.c): the ready light as 4.3.33 sends it, unless the
 * helper decides what follows a reading (signals). */
void i1pro2_cq_lights_after_read(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL)
		return;
	m->cq_lights_reading = 0;
	if (m->cq_lights_signals)
		return;
	i1pro2_cq_lights_ready(pp);
}

/* The helper's: a result is owed for the strip it has just reported. */
void i1pro2_cq_lights_owe(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || !m->cq_lights_signals)
		return;
	m->cq_lights_owed = 1;
	m->cq_lights_owed_ms = msec_time();
}

/* How long a result has been owed, in ms; -1 when none is. */
int i1pro2_cq_lights_owed_ms(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || !m->cq_lights_owed)
		return -1;
	return (int)(msec_time() - m->cq_lights_owed_ms);
}

/* The helper's, with signals only: 1 = GREEN2 (accepted), 0 = RED2 (refused,
 * please read again), -1 = the ready light if dark. Never while a trigger is
 * still to be sent. Ends an owed result. */
void i1pro2_cq_lights_result(void *pp, int good) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL || !m->cq_lights_signals || cq_lights_trigger_pending(m)
	 || cq_lights_pressed(m))
		return;
	m->cq_lights_owed = 0;
	if (good < 0) {
		if (m->cq_lights == CQ_LIGHTS_DARK)
			cq_lights_send(p, CQ_LIGHTS_PULSE, CQ_LIGHTS_TOUT);
		return;
	}
	cq_lights_send(p, good ? CQ_LIGHTS_GREEN2 : CQ_LIGHTS_RED2, CQ_LIGHTS_TOUT);
}

/* The two choices, from the helper, before ..._begin (0/0 = 4.3.33). */
void i1pro2_cq_lights_options(void *pp, int signals, int left_on) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	if (p == NULL || p->dtype != instI1Pro2 || (m = (i1proimp *)p->m) == NULL
	 || m->cq_lights != CQ_LIGHTS_UNUSED)
		return;
	m->cq_lights_signals = signals ? 1 : 0;
	m->cq_lights_left_on = left_on ? 1 : 0;
}

/* Start using the lights. ChromIQ's helper calls this, and only when the user
 * switched the option on. Returns non-zero when they are in use. The open
 * always shows WHITE, as i1Profiler does. */
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
		if (!cq_lights_trigger_pending(m))
			cq_lights_send(p, CQ_LIGHTS_WHITE, CQ_LIGHTS_TOUT);
	}
	return m->cq_lights == CQ_LIGHTS_DARK || m->cq_lights == CQ_LIGHTS_LIT;
}

/* The choices in use after ..._begin (bit 0 signals, bit 1 left_on); 0
 * when the lights are not in use. */
int i1pro2_cq_lights_choices(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL)
		return 0;
	return (m->cq_lights_signals ? 1 : 0) | (m->cq_lights_left_on ? 2 : 0);
}

/* The firmware of an i1Pro 2 whose lights are in use, for the helper's
 * report; -1 otherwise. */
int i1pro2_cq_lights_firmware(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	if (m == NULL)
		return -1;
	return m->fwrev;
}

/* Stop using the lights: OFF_NOW when anything may still be playing (and no
 * trigger is still to be sent), then never send again. Returns 1 when the
 * lights are known to be off afterwards (an off went out, or nothing was
 * playing), 0 when they may still be on: not in use (nothing to say), a
 * trigger still pending, or the off failed. */
int i1pro2_cq_lights_end(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = cq_lights_m(p);
	int off = 1;
	if (m == NULL)
		return 0;
	if (cq_lights_playing(m)) {
		if (cq_lights_trigger_pending(m))
			off = 0;
		else {
			cq_lights_send(p, CQ_LIGHTS_OFF_NOW, CQ_LIGHTS_TOUT_CLOSE);
			off = m->cq_lights == CQ_LIGHTS_DARK;
		}
	}
	m->cq_lights = CQ_LIGHTS_DONE;
	m->cq_lights_owed = 0;
	return off;
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
# The ready light once a measurement or a calibration has returned, whatever it
# returned: the instrument then waits for the user. Around a reading, the
# reading hooks (the choices inside the option, 2026-11-13; 0/0 = 4.3.33).
I1PRO_C_LIGHTS = [
    ("\trv = i1pro_imp_measure(p, vals, npatch, instClamp);\n",
     "\ti1pro2_cq_lights_reading(p, 1);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"
     "\trv = i1pro_imp_measure(p, vals, npatch, instClamp);\n"
     "\ti1pro2_cq_lights_after_read(p);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
    ("\trv = i1pro_imp_measure(p, val, 1, clamp);\n",
     "\ti1pro2_cq_lights_reading(p, 1);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"
     "\trv = i1pro_imp_measure(p, val, 1, clamp);\n"
     "\ti1pro2_cq_lights_after_read(p);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
    ("\trv = i1pro_imp_calibrate(p, calt, calc, idtype, id);\n",
     "\trv = i1pro_imp_calibrate(p, calt, calc, idtype, id);\n"
     "\ti1pro2_cq_lights_ready(p);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
]
# The same Beta for the i1Pro 3 (2026-11-13, from one user's recording of
# i1Profiler 3.8.5 with his own i1Pro 3; the model, 3 or 3 Plus, is not
# known). A different request (0x29, LE32 length, bytes on bulk OUT 0x02) and a
# different format: the four sequences below are the only ones ever sent.
# Argyll's own off (`00`, sent today at every open, i1pro3_imp.c
# i1pro3_imp_init) goes out before every measurement; i1Profiler's three
# recorded patterns only after one. tests/test_i1pro3_lights_driver.py pins it.
# 2026-11-14: the two choices (result signals, left on during a reading) for
# the i1Pro 3 too; tests/test_i1pro3_lights_modes.py.
I1PRO3_IMP_H_LIGHTS = [
    ("\tint ee_unk34;\n\n}; typedef struct _i1pro3imp i1pro3imp;\n",
     "\tint ee_unk34;\n"
     "\n"
     "\t/* CHROMIQ PATCH: i1Pro 3 indicator lights (Beta). 0 = not in use, the\n"
     "\t * calloc default, and then every light hook returns at once. */\n"
     "\tint cq_lights;\n"
     "\t/* ...and the two choices (2026-11-14; both 0 = ChromIQ 4.3.34), the\n"
     "\t * reading in progress, and a result ChromIQ owes for the last reading. */\n"
     "\tint cq_lights_signals;\t\t/* ChromIQ's verdict, not the driver's */\n"
     "\tint cq_lights_left_on;\t\t/* no off before a reading's measurements */\n"
     "\tint cq_lights_reading;\t\t/* inside read_strip / read_sample */\n"
     "\tint cq_lights_press_count;\t/* switch_count when the reading began */\n"
     "\tint cq_lights_owed;\t\t\t/* a result is owed for the last reading */\n"
     "\tunsigned int cq_lights_owed_ms;\n"
     "\tint cq_lights_force_off;\t/* a pattern went out as the button was pressed */\n"
     "\tint cq_lights_maybe_dark;\t/* \"left on\": a reading ran without our off */\n"
     "\n"
     "}; typedef struct _i1pro3imp i1pro3imp;\n"),
    ("#ifdef __cplusplus\n\t}\n#endif\n\n#define I1PRO3_IMP\n",
     "/* CHROMIQ PATCH: i1Pro 3 indicator lights (Beta), see i1pro3_imp.c. Every\n"
     " * entry returns at once unless ChromIQ's helper called ..._begin(). */\n"
     "int i1pro3_cq_lights_begin(void *pp);\t/* ChromIQ's helper only */\n"
     "int i1pro3_cq_lights_end(void *pp);\t/* off if lit, then never again; 1 = known off */\n"
     "void i1pro3_cq_lights_measure(void *pp);\t/* off, before a measurement */\n"
     "void i1pro3_cq_lights_after_read(void *pp, int rv);\t/* GOOD / BAD */\n"
     "void i1pro3_cq_lights_after_cal(void *pp, int rv);\t/* READY on success */\n"
     "extern void (*i1pro3_cq_lights_note)(int seq, int icom_err);\n"
     "void i1pro3_cq_lights_options(void *pp, int signals, int left_on);\t/* before begin */\n"
     "void i1pro3_cq_lights_reading(void *pp, int on);\t/* around a reading */\n"
     "void i1pro3_cq_lights_owe(void *pp);\t/* ChromIQ's helper: result owed */\n"
     "int i1pro3_cq_lights_owed_ms(void *pp);\t/* -1 = none owed */\n"
     "void i1pro3_cq_lights_result(void *pp, int good);\t/* 1 GOOD, 0 BAD, -1 READY */\n"
     "int i1pro3_cq_lights_choices(void *pp);\t/* bit 0 signals, bit 1 left_on */\n"
     "int i1pro3_cq_lights_firmware(void *pp);\t/* version x 100, -1 */\n"
     "extern void (*i1pro3_cq_lights_sent)(int seq);\n"
     "\n"
     "#ifdef __cplusplus\n"
     "\t}\n"
     "#endif\n"
     "\n"
     "#define I1PRO3_IMP\n"),
]
I1PRO3_IMP_C_LIGHTS_BLOCK = r"""
/* ============================================================ */
/* CHROMIQ PATCH: the i1Pro 3 indicator lights (Preferences > Beta, 2026-11-13;
 * the two choices since 2026-11-14).
 *
 * Where the knowledge comes from: the request (0x29, i1p3cc_set_ind) and the
 * format are Argyll's own (i1pro3_indLEDseq above and its comment; Argyll uses
 * it only for its off, `00`, at every open). The three patterns are byte for
 * byte what X-Rite's i1Profiler 3.8.5 sent to a user's own i1Pro 3 (two USB
 * recordings), each sent here where i1Profiler sent it:
 *   READY  `01 fa 04 12 05 00`  after its calibration readings (look of the
 *                               first part: GUESS, white blinks; the tester
 *                               saw slow white blinking after calibration);
 *   GOOD   `0a 14 02 12 05 00`  after every reading it accepted (strips and
 *                               spots; the tester saw green twice);
 *   BAD    `06 14 02 12 05 00`  after every strip it refused (partial swipe,
 *                               no ruler, incomplete; the tester saw red twice).
 *   OFF    `00`                 Argyll's own off, the bytes every ChromIQ sends
 *                               every i1Pro 3 at every open.
 * All three patterns end in `12 05 00`, the white pulse forever, so "lit"
 * always means one of them plays. i1Profiler never sent an off and kept them
 * playing through its readings; nothing else is sent from here: no 0x3B, no
 * memory write.
 *
 * Two choices, passed in by the helper before ..._begin (both 0 = exactly
 * what ChromIQ 4.3.34 sent):
 *   signals  0: after a reading the driver's own verdict: GOOD when the
 *               instrument returned a reading, BAD for a read error.
 *            1: after a reading nothing here: the helper sends GOOD / BAD /
 *               READY (..._result) once ChromIQ has decided about the strip
 *               or patch, as for the i1Pro 2.
 *   left_on  0: OFF before every measurement while lit (4.3.34).
 *            1: i1Profiler's hand-held way: no off before the measurements of
 *               a reading the instrument's button started (read_strip /
 *               read_sample: its dark and lit parts), and a reading's pattern
 *               is sent over the one playing. A calibration, and a reading
 *               started from the keyboard, still get the off before each
 *               measurement.
 *
 * Rules, all enforced in this block:
 *  - nothing happens until ChromIQ's helper calls i1pro3_cq_lights_begin(),
 *    which it does only when the user switched the option on, and which
 *    refuses anything but an inited i1Pro 3 (the driver's dtype, i1Pro 3 and
 *    3 Plus alike) whose EEPROM reports the indicator LEDs
 *    (I1PRO3_CAP_IND_LED). Every entry checks dtype first;
 *  - the off decision at the top of i1pro3_do_measure, the one function every
 *    calibration and reading of this driver passes through, before its 0x3B
 *    and trigger; every measurement also ends a result that is still owed;
 *  - the sender holds m->lock across the 0x29 request and its bytes, so no
 *    other request of this driver can come between them; it is never called
 *    with the lock held;
 *  - a pattern only once a measurement has returned and no trigger thread is
 *    still to send its request; a result from the helper only while one is
 *    owed or for its own refusal, and never once the button was pressed for
 *    the next reading;
 *  - a request that fails is never retried and fails nothing: the lights are
 *    given up for the session (not even a final off), the helper is told once.
 */

#define CQ3_LIGHTS_UNUSED 0	/* the default: never asked for, never sends */
#define CQ3_LIGHTS_DARK   1	/* in use, the last sequence was OFF (or none yet) */
#define CQ3_LIGHTS_LIT    2	/* in use, a pattern is playing */
#define CQ3_LIGHTS_DONE   3	/* ended or given up: never sends again */

#define CQ3_LIGHTS_READY 1
#define CQ3_LIGHTS_GOOD  2
#define CQ3_LIGHTS_BAD   3
#define CQ3_LIGHTS_OFF   4

#define CQ3_LIGHTS_TOUT         0.25	/* s per transfer; a good one takes a few ms */
#define CQ3_LIGHTS_TOUT_MEASURE 0.25	/* between the button and the measurement */
#define CQ3_LIGHTS_TOUT_CLOSE   0.25	/* at the close, inside the helper's 1.5 s */

static const unsigned char cq3_lights_seq_ready[6] = { 0x01, 0xfa, 0x04,  0x12, 0x05, 0x00 };
static const unsigned char cq3_lights_seq_good[6]  = { 0x0a, 0x14, 0x02,  0x12, 0x05, 0x00 };
static const unsigned char cq3_lights_seq_bad[6]   = { 0x06, 0x14, 0x02,  0x12, 0x05, 0x00 };
static const unsigned char cq3_lights_seq_off[1]   = { 0x00 };

/* Set by ChromIQ's helper to hear about a failed light request (one call per
 * session at most). seq is CQ3_LIGHTS_READY / _GOOD / _BAD / _OFF (1-4). */
void (*i1pro3_cq_lights_note)(int seq, int icom_err) = NULL;

/* Set by ChromIQ's helper to hear about every pattern sent (for its log). */
void (*i1pro3_cq_lights_sent)(int seq) = NULL;

/* The i1pro3imp of an i1Pro 3 whose lights are in use, else NULL. dtype is in
 * every instrument's base object, so this is safe to ask of any inst. */
static i1pro3imp *cq3_lights_m(i1pro3 *p) {
	i1pro3imp *m;
	if (p == NULL || p->dtype != instI1Pro3 || (m = (i1pro3imp *)p->m) == NULL
	 || p->icom == NULL)
		return NULL;
	if (m->cq_lights != CQ3_LIGHTS_DARK && m->cq_lights != CQ3_LIGHTS_LIT)
		return NULL;
	return m;
}

/* A trigger thread that has not sent its request yet. */
static int cq3_lights_trigger_pending(i1pro3imp *m) {
	return m->trig_thread != NULL && m->tr_t2 == 0;
}

/* Send one of the four sequences. The only place a light request is made. */
static void cq3_lights_send(i1pro3 *p, int which, double tout) {
	i1pro3imp *m = (i1pro3imp *)p->m;
	const unsigned char *seq;
	int size;
	unsigned char pbuf[4];
	int wbytes = 0;
	int se;

	if (which == CQ3_LIGHTS_READY) {
		seq = cq3_lights_seq_ready; size = (int)sizeof(cq3_lights_seq_ready);
	} else if (which == CQ3_LIGHTS_GOOD) {
		seq = cq3_lights_seq_good;  size = (int)sizeof(cq3_lights_seq_good);
	} else if (which == CQ3_LIGHTS_BAD) {
		seq = cq3_lights_seq_bad;   size = (int)sizeof(cq3_lights_seq_bad);
	} else {
		which = CQ3_LIGHTS_OFF;
		seq = cq3_lights_seq_off;   size = (int)sizeof(cq3_lights_seq_off);
	}

	write_INR32_le(pbuf, size);
	amutex_lock(m->lock);
	se = p->icom->usb_control(p->icom,
		               IUSB_ENDPOINT_OUT | IUSB_REQ_TYPE_VENDOR | IUSB_REQ_RECIP_DEVICE,
	                   i1p3cc_set_ind, 0, 0, pbuf, 4, NULL, tout);
	if (icoms2i1pro3_err(se) == I1PRO3_OK)
		se = p->icom->usb_write(p->icom, NULL, 0x02, (unsigned char *)seq, size,
		                        &wbytes, tout);
	amutex_unlock(m->lock);

	if (icoms2i1pro3_err(se) != I1PRO3_OK || wbytes != size) {
		m->cq_lights = CQ3_LIGHTS_DONE;		/* given up for this session */
		m->cq_lights_owed = 0;
		a1logd(p->log,1,"i1pro3 lights: sequence %d failed, ICOM err 0x%x, wrote %d of %d;"
		                " lights not used again\n", which, se, wbytes, size);
		if (i1pro3_cq_lights_note != NULL)
			i1pro3_cq_lights_note(which, se);
		return;
	}
	m->cq_lights = which == CQ3_LIGHTS_OFF ? CQ3_LIGHTS_DARK : CQ3_LIGHTS_LIT;
	m->cq_lights_maybe_dark = 0;
	a1logd(p->log,2,"i1pro3 lights: sequence %d sent\n", which);
	/* Patterns only: an OFF can go out between the press and the trigger,
	 * where the helper must not write (a full pipe would hold the scan). */
	if (which != CQ3_LIGHTS_OFF && i1pro3_cq_lights_sent != NULL)
		i1pro3_cq_lights_sent(which);
}

/* Before a measurement (the top of i1pro3_do_measure): it ends a result that
 * is still owed; then OFF when a pattern is playing, except inside a reading
 * with "left on" that the instrument's button started (the switch thread
 * counted a press since the reading began). A reading started from the
 * keyboard gets the off as in 4.3.34: i1Profiler was only ever recorded
 * measuring with a pattern playing after a press, when the instrument goes
 * dark by itself. */
void i1pro3_cq_lights_measure(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL)
		return;
	m->cq_lights_owed = 0;
	if (m->cq_lights != CQ3_LIGHTS_LIT)
		return;
	if (m->cq_lights_left_on && m->cq_lights_reading && !m->cq_lights_force_off
	 && m->switch_count != m->cq_lights_press_count) {
		/* The instrument most likely went dark by itself at the press (the
		 * tester's observation with i1Profiler): for the ready fallback
		 * only, the lights now count as dark. */
		m->cq_lights_maybe_dark = 1;
		return;
	}
	m->cq_lights_force_off = 0;
	cq3_lights_send(p, CQ3_LIGHTS_OFF, CQ3_LIGHTS_TOUT_MEASURE);
}

/* A pattern after a measurement: only when no trigger is pending, and (as
 * 4.3.34) only when off, unless "left on" keeps a pattern playing through the
 * reading: then the new one is sent over it, as i1Profiler does. */
static void cq3_lights_show(i1pro3 *p, int which) {
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL || cq3_lights_trigger_pending(m))
		return;
	if (m->cq_lights != CQ3_LIGHTS_DARK && !m->cq_lights_left_on)
		return;
	cq3_lights_send(p, which, CQ3_LIGHTS_TOUT);
}

/* Around i1pro3_imp_measure in read_strip / read_sample (i1pro3.c): 1 before.
 * ..._after_read ends it. imp_measure never calibrates (it returns
 * I1PRO3_RD_NEEDS_CAL instead), so every measurement in between is the
 * reading's. */
void i1pro3_cq_lights_reading(void *pp, int on) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL)
		return;
	m->cq_lights_reading = on;
	m->cq_lights_force_off = 0;
	if (on)
		m->cq_lights_press_count = m->switch_count;
}

/* The instrument's button was pressed since the current reading began (the
 * switch thread counts presses): its measurement is about to start. */
static int cq3_lights_pressed(i1pro3imp *m) {
	return m->cq_lights_reading && m->switch_count != m->cq_lights_press_count;
}

/* After i1pro3_imp_measure: ends the reading. Without result signals, GOOD
 * for a reading, BAD for a reading the instrument could not take; nothing for
 * anything else (an abort, a command, a calibration needed, a USB or hardware
 * fault). With result signals nothing: ChromIQ's helper decides. */
void i1pro3_cq_lights_after_read(void *pp, int rv) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m;
	int which;
	if (p != NULL && p->dtype == instI1Pro3 && p->m != NULL) {
		((i1pro3imp *)p->m)->cq_lights_reading = 0;	/* whatever the state */
		((i1pro3imp *)p->m)->cq_lights_force_off = 0;
	}
	if ((m = cq3_lights_m(p)) == NULL)
		return;
	if (m->cq_lights_signals)
		return;
	if (rv == I1PRO3_OK)
		which = CQ3_LIGHTS_GOOD;
	else if (rv == I1PRO3_RD_SHORTMEAS || rv == I1PRO3_RD_READINCONS
	      || rv == I1PRO3_RD_NOTENOUGHPATCHES || rv == I1PRO3_RD_TOOMANYPATCHES
	      || rv == I1PRO3_RD_NOTENOUGHSAMPLES || rv == I1PRO3_RD_SENSORSATURATED
	      || rv == I1PRO3_RD_LEADTRAILINCONS)
		which = CQ3_LIGHTS_BAD;
	else
		return;
	cq3_lights_show(p, which);
}

/* After i1pro3_imp_calibrate: READY when it succeeded, nothing otherwise. */
void i1pro3_cq_lights_after_cal(void *pp, int rv) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (rv != I1PRO3_OK || m == NULL || m->cq_lights != CQ3_LIGHTS_DARK
	 || cq3_lights_trigger_pending(m))
		return;
	cq3_lights_send(p, CQ3_LIGHTS_READY, CQ3_LIGHTS_TOUT);
}

/* The helper's: a result is owed for the strip it has just reported. */
void i1pro3_cq_lights_owe(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL || !m->cq_lights_signals)
		return;
	m->cq_lights_owed = 1;
	m->cq_lights_owed_ms = msec_time();
}

/* How long a result has been owed, in ms; -1 when none is. */
int i1pro3_cq_lights_owed_ms(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL || !m->cq_lights_owed)
		return -1;
	return (int)(msec_time() - m->cq_lights_owed_ms);
}

/* The helper's, with result signals only: 1 = GOOD (accepted), 0 = BAD
 * (refused, please look at the screen), -1 = READY if dark (or, with "left
 * on", if a reading ran since the last pattern: the instrument most likely
 * went dark by itself at the press). Never while a
 * trigger is still to be sent, never once the button was pressed for the next
 * reading. Ends an owed result. */
void i1pro3_cq_lights_result(void *pp, int good) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	int count;
	if (m == NULL || !m->cq_lights_signals || cq3_lights_trigger_pending(m)
	 || cq3_lights_pressed(m))
		return;
	m->cq_lights_owed = 0;
	if (good < 0 && m->cq_lights != CQ3_LIGHTS_DARK && !m->cq_lights_maybe_dark)
		return;
	count = m->switch_count;
	cq3_lights_send(p, good < 0 ? CQ3_LIGHTS_READY
	                            : good ? CQ3_LIGHTS_GOOD : CQ3_LIGHTS_BAD,
	                CQ3_LIGHTS_TOUT);
	/* The button may have been pressed while the bytes were on their way
	 * (the switch thread sees a press a few ms late): then this reading's
	 * measurements get the off after all, even with "left on", so a pattern
	 * started at the press never plays through it. */
	if (m->cq_lights_reading && m->switch_count != count)
		m->cq_lights_force_off = 1;
}

/* The two choices, from the helper, before ..._begin (0/0 = 4.3.34). */
void i1pro3_cq_lights_options(void *pp, int signals, int left_on) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m;
	if (p == NULL || p->dtype != instI1Pro3 || (m = (i1pro3imp *)p->m) == NULL
	 || m->cq_lights != CQ3_LIGHTS_UNUSED)
		return;
	m->cq_lights_signals = signals ? 1 : 0;
	m->cq_lights_left_on = left_on ? 1 : 0;
}

/* Start using the lights. ChromIQ's helper calls this, and only when the user
 * switched the option on. Sends nothing: the first pattern follows the first
 * calibration or reading. Returns non-zero when they are in use. */
int i1pro3_cq_lights_begin(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m;

	if (p == NULL || p->dtype != instI1Pro3 || !p->gotcoms || !p->inited
	 || (m = (i1pro3imp *)p->m) == NULL || p->icom == NULL)
		return 0;
	if ((m->capabilities & I1PRO3_CAP_IND_LED) == 0)
		return 0;
	if (m->cq_lights == CQ3_LIGHTS_UNUSED)
		m->cq_lights = CQ3_LIGHTS_DARK;
	return m->cq_lights == CQ3_LIGHTS_DARK || m->cq_lights == CQ3_LIGHTS_LIT;
}

/* The choices in use after ..._begin (bit 0 signals, bit 1 left_on); 0 when
 * the lights are not in use. */
int i1pro3_cq_lights_choices(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL)
		return 0;
	return (m->cq_lights_signals ? 1 : 0) | (m->cq_lights_left_on ? 2 : 0);
}

/* The firmware (version x 100, as Argyll reads it at open) of an i1Pro 3
 * whose lights are in use, for the helper's report; -1 otherwise. Only
 * reported, never a condition: Argyll's light code has none. */
int i1pro3_cq_lights_firmware(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	if (m == NULL)
		return -1;
	return m->fwver;
}

/* Stop using the lights: OFF when a pattern is playing (and no trigger is
 * still to be sent), then never send again. Returns 1 when the lights are
 * known to be off afterwards (an off went out, or nothing was playing), 0
 * when they may still play: not in use (nothing to say), a trigger still
 * pending, or the off failed. */
int i1pro3_cq_lights_end(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = cq3_lights_m(p);
	int off = 1;
	if (m == NULL)
		return 0;
	if (m->cq_lights == CQ3_LIGHTS_LIT) {
		if (cq3_lights_trigger_pending(m))
			off = 0;
		else {
			cq3_lights_send(p, CQ3_LIGHTS_OFF, CQ3_LIGHTS_TOUT_CLOSE);
			off = m->cq_lights == CQ3_LIGHTS_DARK;
		}
	}
	m->cq_lights = CQ3_LIGHTS_DONE;
	m->cq_lights_owed = 0;
	return off;
}
"""
I1PRO3_IMP_C_LIGHTS = [
    ("\ta1logd(p->log,4,\"\\ni1pro3_do_measure: mm %d nummeas %d inttime %f\\n\",mm,*pnummeas,*pinttime);\n",
     "\ta1logd(p->log,4,\"\\ni1pro3_do_measure: mm %d nummeas %d inttime %f\\n\",mm,*pnummeas,*pinttime);\n\n"
     "\t/* CHROMIQ PATCH: the indicator lights go off before every measurement */\n"
     "\t/* (Beta, a no-op unless ChromIQ's helper switched them on). */\n"
     "\ti1pro3_cq_lights_measure(p);\n"),
    ("\t\ti1pro3_state *s;\n\t\ti1pro3_code ev;\n\n\t\t/* Terminate event monitor thread */\n",
     "\t\ti1pro3_state *s;\n\t\ti1pro3_code ev;\n\n"
     "\t\t/* CHROMIQ PATCH: lights off before the instrument is let go (Beta, */\n"
     "\t\t/* a no-op unless ChromIQ's helper switched them on). */\n"
     "\t\ti1pro3_cq_lights_end(p);\n\n"
     "\t\t/* Terminate event monitor thread */\n"),
    ("\ta1logd(p->log,2,\"i1pro3_indLEDoff: returning ICOM err 0x%x\\n\",rv);\n\n\treturn rv;\n}\n",
     "\ta1logd(p->log,2,\"i1pro3_indLEDoff: returning ICOM err 0x%x\\n\",rv);\n\n\treturn rv;\n}\n"
     + I1PRO3_IMP_C_LIGHTS_BLOCK),
]
I1PRO3_C_LIGHTS = [
    ("\trv = i1pro3_imp_measure(p, vals, npatch, instClamp);\n",
     "\ti1pro3_cq_lights_reading(p, 1);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"
     "\trv = i1pro3_imp_measure(p, vals, npatch, instClamp);\n"
     "\ti1pro3_cq_lights_after_read(p, rv);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
    ("\trv = i1pro3_imp_measure(p, val, 1, clamp);\n",
     "\ti1pro3_cq_lights_reading(p, 1);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"
     "\trv = i1pro3_imp_measure(p, val, 1, clamp);\n"
     "\ti1pro3_cq_lights_after_read(p, rv);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
    ("\trv = i1pro3_imp_calibrate(p, calt, calc, idtype, id);\n",
     "\ti1pro3_cq_lights_reading(p, 0);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"
     "\trv = i1pro3_imp_calibrate(p, calt, calc, idtype, id);\n"
     "\ti1pro3_cq_lights_after_cal(p, rv);\t/* CHROMIQ PATCH: Beta lights, no-op unless on */\n"),
]
# ---- RULER CHECK (generated section) ----
# The ruler check (Preferences > Beta, 2026-11-14; stage 1, CHECK ONLY).
# i1Pro 2: RULER_START | RULER_END on an ARMED strip's lit scan and the ruler
# stream on bulk IN 0x85, exactly as X-Rite's i1Profiler 3.8.6 does on every
# strip scan (two USB recordings of a user's own i1Pro 2, firmware 634); never
# 0xD7. i1Pro 3: nothing new on the wire; copies of what ArgyllCMS already
# reads. Both: read-only copies of the recogniser's cut and a coarse trace.
# Until ChromIQ's helper calls ..._options(on) and ..._arm(1) every hook
# returns at once. tests/test_ruler_scan_trace.py pins the wire.
I1PRO_IMP_H_RULER = [
    ("\tvolatile double whitestamp;\t/* meas_delay() white timestamp */\n",
     "\t/* CHROMIQ PATCH: the ruler check (Beta, 2026-11-14). All 0 = not in use. */\n"
     "\tint cq_ruler_on;\t\t\t/* the helper's option, this session */\n"
     "\tint cq_ruler_armed;\t\t/* armed for one read_strip */\n"
     "\tint cq_ruler_given_up;\t/* CQ_RULER_GIVEUP_*: never again this session */\n"
     "\tint cq_ruler_inscan;\t/* this lit scan carries the bits */\n"
     "\tint cq_ruler_recording;\t/* the recogniser's copies go to the record */\n"
     "\tathread *cq_ruler_th;\t/* the 0x85 reader */\n"
     "\tvoid *cq_ruler_ctx;\t\t/* what the reader touches (cq_ruler_ctx) */\n"
     "\tunsigned int cq_ruler_t0;\t/* msec_time() when the reader started */\n"
     "\tvoid *cq_ruler_rec;\t\t/* cq_ruler_rec (cq_ruler.h) */\n\n"
     "\tvolatile double whitestamp;\t/* meas_delay() white timestamp */\n"),
    ("/* CHROMIQ PATCH: i1Pro 2 indicator lights (Beta), see i1pro_imp.c. Every\n",
     "/* CHROMIQ PATCH: the ruler check (Beta), see i1pro_imp.c. */\n"
     "int i1pro2_cq_ruler_options(void *pp, int on);\t/* 1 = usable */\n"
     "void i1pro2_cq_ruler_arm(void *pp, int on);\t/* around one read_strip */\n"
     "int i1pro2_cq_ruler_state(void *pp);\t/* -1 off, 0 in use, >0 given up */\n"
     "int i1pro2_cq_ruler_firmware(void *pp);\n"
     "int i1pro2_cq_ruler_take(void *pp, void *out);\t/* cq_ruler_rec, 1 = one */\n"
     "int i1pro2_cq_ruler_bits(void *pp, int mmodif);\n"
     "void i1pro2_cq_ruler_start(void *pp);\n"
     "void i1pro2_cq_ruler_finish(void *pp, int nreadings, int ev);\n"
     "void i1pro2_cq_ruler_trace(void *pp, double **multimeas, int nummeas, double *maxval);\n"
     "void i1pro2_cq_ruler_cut(void *pp, int pix, int ss, int no);\n"
     "void i1pro2_cq_ruler_close(void *pp);\n"
     "extern int i1pro2_cq_ruler_fail_start_for_test;\t/* the fake-USB harness only */\n\n"
     "/* CHROMIQ PATCH: i1Pro 2 indicator lights (Beta), see i1pro_imp.c. Every\n"),
]
I1PRO_IMP_C_RULER_BLOCK = r"""
/* ============================================================ */
/* CHROMIQ PATCH: the ruler check (Preferences > Beta, 2026-11-14; stage 1,
 * CHECK ONLY). See ChromIQ's work notes and native/instlib/PROVENANCE.md.
 *
 * Inert unless ChromIQ's helper switched it on for an i1Pro 2 whose EEPROM
 * reports the ruler sensor (i1pro2_cq_ruler_options) AND armed it for one
 * read_strip (i1pro2_cq_ruler_arm). Only then, and only for that strip's lit
 * scan trigger (never a dark, calibration, UV, wavelength-LED or spot
 * trigger), does the driver
 *   - add RULER_START | RULER_END (0x0004 | 0x0008) to the 0xD4 flags, as
 *     X-Rite's i1Profiler 3.8.6 does on every single strip scan (two USB
 *     recordings of a user's own i1Pro 2, firmware 634), and
 *   - read the ruler stream on bulk IN 0x85 in 4096-byte reads on a thread of
 *     its own until a short read ends it, as i1Profiler does.
 * Nothing else is ever sent: never 0xD7 (stop ruler), in any case.
 *
 * Safety rules (ChromIQ's design review of 2026-11-14):
 *   - the trigger never waits for the ruler: the thread is started before the
 *     trigger thread and submits its first read at once;
 *   - a ruler read never times out while the instrument is in use (its
 *     timeout is a day), so a timeout, and on macOS the clear-halt request
 *     IOKit sends after any aborted read, can only come from the close; the
 *     normal end is the instrument's short read;
 *   - the reader works on a context of its own (cq_ruler_ctx), checks a stop
 *     flag before every read and is joined before the measurement returns,
 *     or, if the stream did not end by itself, kept draining (never stopped)
 *     until it does or the instrument is closed; the close stops it host
 *     side within about 2 s, and a read that cannot be aborted is left to
 *     the process's end with its context (never freed memory);
 *   - anything unusual (a USB error on 0x85, no data, a stream that did not
 *     end, a failed measurement read, readings faster than the clock allows,
 *     a thread that cannot start) gives the ruler up for the rest of the
 *     session: no more bits, and the measurement goes on exactly as without
 *     the option;
 *   - the readings, the patch recognition and every value are computed by
 *     the unchanged code; the hooks in the recogniser only COPY where it cut
 *     (cq_ruler_rec_cut) and a coarse trace (cq_ruler_rec_trace).
 */
#include "cq_ruler.h"

#define CQ_RULER_CHUNK        4096	/* i1Profiler's read size */
#define CQ_RULER_KEEP         (1 << 20)	/* bytes kept, about 37 s of stream */
#define CQ_RULER_END_WAIT_MS  250	/* after the measurement read ended */
#define CQ_RULER_MAX_ERRS     20	/* USB errors retried while the scan runs */
#define CQ_RULER_READ_TOUT    86400.0	/* s: only the close ends a pending read */
#define CQ_RULER_CLOSE_MS     2000	/* the close's bound on stopping the reader */

/* Test hook (the fake-USB harness only): make the reader's start fail. */
int i1pro2_cq_ruler_fail_start_for_test = 0;

/* Everything the reader thread touches. Allocated per reader and freed only
 * after a join; a reader the close could not stop keeps its context (and the
 * cancel token in it) until the process ends. */
typedef struct {
	i1pro *p;
	icoms *icom;
	usb_cancelt cancel;
	volatile int stop, done, end, err;
	unsigned char *buf;
	volatile long nbytes, extra;
} cq_ruler_ctx;

static cq_ruler_rec *cq_ruler_r(i1proimp *m) {
	return (cq_ruler_rec *)m->cq_ruler_rec;
}

static void cq_ruler_give_up(i1proimp *m, int why) {
	cq_ruler_rec *r = cq_ruler_r(m);
	if (!m->cq_ruler_given_up) {
		m->cq_ruler_given_up = why;
		if (r != NULL)
			r->giveup = why;
	}
}

static void cq_ruler_join(i1proimp *m) {
	cq_ruler_ctx *c = (cq_ruler_ctx *)m->cq_ruler_ctx;
	if (m->cq_ruler_th == NULL)
		return;
	m->cq_ruler_th->wait(m->cq_ruler_th);
	m->cq_ruler_th->del(m->cq_ruler_th);
	m->cq_ruler_th = NULL;
	if (c != NULL) {
		usb_uninit_cancel(&c->cancel);
		free(c->buf);
		free(c);
		m->cq_ruler_ctx = NULL;
	}
}

/* The helper: on (1) for this session, if this is an i1Pro 2 whose EEPROM
 * reports the ruler sensor. Returns 1 when the ruler can be used. */
int i1pro2_cq_ruler_options(void *pp, int on) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	if (p == NULL || (m = (i1proimp *)p->m) == NULL)
		return 0;
	if (!on || p->dtype != instI1Pro2 || !p->inited
	 || !(m->capabilities2 & I1PRO_CAP2_ZEB_RUL))
		return 0;
	if (m->cq_ruler_rec == NULL
	 && (m->cq_ruler_rec = calloc(1, sizeof(cq_ruler_rec))) == NULL)
		return 0;
	m->cq_ruler_on = 1;
	return 1;
}

/* The helper, around one read_strip: arm (1) / disarm (0). Arming clears the
 * last record. One-shot: the lit trigger that uses it clears it too. */
void i1pro2_cq_ruler_arm(void *pp, int on) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	if (p == NULL || (m = (i1proimp *)p->m) == NULL || !m->cq_ruler_on)
		return;
	if (m->cq_ruler_th != NULL && m->cq_ruler_ctx != NULL
	 && ((cq_ruler_ctx *)m->cq_ruler_ctx)->done)
		cq_ruler_join(m);		/* a drained stream that has ended since */
	if (on && cq_ruler_r(m) != NULL)
		cq_ruler_rec_clear(cq_ruler_r(m));
	m->cq_ruler_armed = on && !m->cq_ruler_given_up;
	m->cq_ruler_recording = 0;
}

/* Why the ruler was given up (CQ_RULER_GIVEUP_*), 0 = it is in use, -1 = not
 * in use at all. */
int i1pro2_cq_ruler_state(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	if (p == NULL || (m = (i1proimp *)p->m) == NULL || !m->cq_ruler_on)
		return -1;
	return m->cq_ruler_given_up;
}

int i1pro2_cq_ruler_firmware(void *pp) {
	i1pro *p = (i1pro *)pp;
	if (p == NULL || p->m == NULL)
		return -1;
	return ((i1proimp *)p->m)->fwrev;
}

/* The record of the last armed strip, handed over (the caller owns its
 * buffers and frees them with cq_ruler_rec_clear). 0 = none. */
int i1pro2_cq_ruler_take(void *pp, void *vout) {
	i1pro *p = (i1pro *)pp;
	cq_ruler_rec *out = (cq_ruler_rec *)vout;
	i1proimp *m;
	cq_ruler_rec *r;
	if (out != NULL)
		memset(out, 0, sizeof(*out));
	if (p == NULL || (m = (i1proimp *)p->m) == NULL
	 || (r = cq_ruler_r(m)) == NULL || !r->valid || out == NULL)
		return 0;
	*out = *r;
	memset(r, 0, sizeof(*r));		/* the buffers moved to *out */
	m->cq_ruler_recording = 0;
	return 1;
}

/* i1pro_trigger_one_measure: the extra flags, only for an armed lit scan. */
int i1pro2_cq_ruler_bits(void *pp, int mmodif) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	i1pro_state *s = &m->ms[m->mmode];
	m->cq_ruler_inscan = p->dtype == instI1Pro2 && m->cq_ruler_on
	    && m->cq_ruler_armed && !m->cq_ruler_given_up
	    && mmodif == i1p_norm && s->scan && s->reflective && !m->uv_en
	    && m->cq_ruler_th == NULL;		/* never over a stream still drained */
	if (m->cq_ruler_inscan)
		m->cq_ruler_armed = 0;			/* one-shot */
	return m->cq_ruler_inscan ? (I1PRO2_MMF_RULER_START | I1PRO2_MMF_RULER_END) : 0;
}

static int cq_ruler_thread(void *pp) {
	cq_ruler_ctx *c = (cq_ruler_ctx *)pp;	/* never the driver's own memory */
	unsigned char scratch[CQ_RULER_CHUNK];
	int errs = 0, end = CQ_RULER_END_NONE;

	for (;;) {
		unsigned char *dst;
		int rw = 0, se;
		if (c->stop) {			/* checked before EVERY read */
			end = CQ_RULER_END_CANCELLED;
			break;
		}
		dst = (c->buf != NULL && c->nbytes + CQ_RULER_CHUNK <= CQ_RULER_KEEP)
		    ? c->buf + c->nbytes : scratch;
		se = c->icom->usb_read(c->icom, &c->cancel, 0x85, dst,
		                       CQ_RULER_CHUNK, &rw, CQ_RULER_READ_TOUT);
		if (rw > 0) {
			if (dst != scratch)
				c->nbytes += rw;
			else
				c->extra += rw;		/* drained, not kept */
		}
		if (se == ICOM_OK)
			continue;
		if (se == ICOM_SHORT) {
			end = CQ_RULER_END_SHORT;
			break;
		}
		if (se & ICOM_CANC) {
			end = CQ_RULER_END_CANCELLED;
			break;
		}
		if (se & ICOM_TO) {
			end = CQ_RULER_END_TIMEOUT;
			break;
		}
		c->err = se;			/* a USB error: retried while the scan runs */
		if (++errs > CQ_RULER_MAX_ERRS || c->stop) {
			end = CQ_RULER_END_ERROR;
			break;
		}
		msec_sleep(5);
	}
	c->end = end;
	c->done = 1;
	return 0;
}

/* i1pro_trigger_one_measure, before the trigger thread: start the reader. */
void i1pro2_cq_ruler_start(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	cq_ruler_rec *r = cq_ruler_r(m);
	cq_ruler_ctx *c;
	if (!m->cq_ruler_inscan || r == NULL)
		return;
	cq_ruler_rec_clear(r);
	m->cq_ruler_t0 = msec_time();
	c = (cq_ruler_ctx *)calloc(1, sizeof(cq_ruler_ctx));
	if (c != NULL) {
		c->p = p;
		c->icom = p->icom;
		c->buf = (unsigned char *)malloc(CQ_RULER_KEEP);
		usb_init_cancel(&c->cancel);
		m->cq_ruler_ctx = c;
	}
	if (c == NULL || i1pro2_cq_ruler_fail_start_for_test
	 || (m->cq_ruler_th = new_athread(cq_ruler_thread, (void *)c)) == NULL) {
		/* This strip without the ruler: the bits must not go out with
		 * nobody reading 0x85 (the trigger thread sends c_measmodeflags2
		 * later), and the rest of the session without it. */
		m->c_measmodeflags2 &= ~(I1PRO2_MMF_RULER_START | I1PRO2_MMF_RULER_END);
		m->cq_ruler_inscan = 0;
		m->cq_ruler_th = NULL;
		if (c != NULL) {
			usb_uninit_cancel(&c->cancel);
			free(c->buf);
			free(c);
			m->cq_ruler_ctx = NULL;
		}
		r->valid = 1;
		r->gen = 2;
		r->ended = CQ_RULER_END_NOSTART;
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_NOSTART);
	}
}

/* i1pro_read_patches_1, on every way out after the trigger: the scan is
 * over. Never fails anything; at most 250 ms after the end of a scan whose
 * stream has not ended. */
void i1pro2_cq_ruler_finish(void *pp, int nreadings, int ev) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	cq_ruler_rec *r = cq_ruler_r(m);
	cq_ruler_ctx *c = (cq_ruler_ctx *)m->cq_ruler_ctx;
	long pos = 0, last_at = -1, kept;
	int last_code = -1;
	unsigned int t1;
	if (!m->cq_ruler_inscan || r == NULL || c == NULL)
		return;
	m->cq_ruler_inscan = 0;
	t1 = msec_time();
	while (!c->done && (msec_time() - t1) < CQ_RULER_END_WAIT_MS)
		msec_sleep(5);
	r->valid = 1;
	r->gen = 2;
	r->readings = nreadings;
	r->clocks = m->c_intclocks;
	r->clock_s = m->intclkp;
	r->inttime = m->c_inttime;
	r->rate_ms = (int)(t1 - m->cq_ruler_t0);
	kept = c->nbytes;
	r->icom_err = c->err;
	r->bytes = kept + c->extra;
	if (c->buf != NULL)
		cq_ruler_rec_feed(r, c->buf, kept, &pos, &last_at, &last_code);
	r->samples = r->bytes;
	if (c->done) {
		r->ended = c->end;
		cq_ruler_join(m);
	} else {
		/* The stream did not end by itself: it is drained on (never stopped,
		 * never 0xD7) until it does or the instrument is closed. Its reads
		 * never time out before the close. */
		r->ended = CQ_RULER_END_RUNNING;
		r->stream_did_not_end = 1;
	}
	m->cq_ruler_recording = 1;		/* the recogniser's cut and trace follow */

	if (r->stream_did_not_end)
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_NOTEND);
	else if (ev != I1PRO_OK)
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_MEASFAIL);
	else if (r->ended == CQ_RULER_END_ERROR)
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_ERROR);
	else if (r->ended == CQ_RULER_END_TIMEOUT)
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_TIMEOUT);
	else if (r->bytes == 0)
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_NODATA);
	else if (nreadings > 50 && r->inttime > 0.0
	      && r->rate_ms < (int)(0.9 * 1000.0 * nreadings * r->inttime))
		/* readings faster than the integration clock allows: the
		 * instrument behaves differently with the bits */
		cq_ruler_give_up(m, CQ_RULER_GIVEUP_RATE);
}

/* i1pro_extract_patches_multimeas: copies only, while a record is open. */
void i1pro2_cq_ruler_trace(void *pp, double **multimeas, int nummeas,
                           double *maxval) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	if (m->cq_ruler_recording && cq_ruler_r(m) != NULL)
		cq_ruler_rec_trace(cq_ruler_r(m), multimeas, nummeas, maxval,
		                   m->nraw, 0);
}

void i1pro2_cq_ruler_cut(void *pp, int pix, int ss, int no) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m = (i1proimp *)p->m;
	if (m->cq_ruler_recording && cq_ruler_r(m) != NULL)
		cq_ruler_rec_cut(cq_ruler_r(m), pix, ss, no, 0);
}

/* del_i1proimp, before anything is torn down: a stream still drained is
 * stopped host side (stop flag, then cancel until the thread is out; the
 * read's own timeout bounds the join), and everything is freed. */
void i1pro2_cq_ruler_close(void *pp) {
	i1pro *p = (i1pro *)pp;
	i1proimp *m;
	cq_ruler_ctx *c;
	unsigned int t0;
	if (p == NULL || (m = (i1proimp *)p->m) == NULL)
		return;
	c = (cq_ruler_ctx *)m->cq_ruler_ctx;
	if (m->cq_ruler_th != NULL && c != NULL) {
		c->stop = 1;
		t0 = msec_time();
		while (!c->done && (msec_time() - t0) < CQ_RULER_CLOSE_MS) {
			c->icom->usb_cancel_io(c->icom, &c->cancel);
			msec_sleep(10);
		}
		if (c->done)
			cq_ruler_join(m);
		else {
			/* A read that cannot be aborted: the process is ending; the
			 * reader keeps its context, nothing it uses is freed here. */
			m->cq_ruler_th = NULL;
			m->cq_ruler_ctx = NULL;
		}
	}
	if (m->cq_ruler_rec != NULL) {
		cq_ruler_rec_clear(cq_ruler_r(m));
		free(m->cq_ruler_rec);
		m->cq_ruler_rec = NULL;
	}
	m->cq_ruler_on = m->cq_ruler_armed = m->cq_ruler_inscan = 0;
}
"""
I1PRO_IMP_C_RULER = [
    ("\t\tif (gainmode != 0)\n\t\t\treturn I1PRO_INT_NO_HIGH_GAIN;\n\t}\n",
     "\t\tif (gainmode != 0)\n\t\t\treturn I1PRO_INT_NO_HIGH_GAIN;\n\n"
     "\t\tmeasmodeflags2 |= i1pro2_cq_ruler_bits(p, mmodif);\t/* CHROMIQ PATCH: ruler check (Beta), a no-op unless armed */\n\t}\n"),
    ("\t/* Trigger a measurement */\n\tusb_reinit_cancel(&m->rd_sync);\t\t\t/* Prepare to sync rd and trigger */\n",
     "\t/* CHROMIQ PATCH: ruler check (Beta): its reader starts first and the */\n"
     "\t/* trigger never waits for it (a no-op unless armed). */\n"
     "\ti1pro2_cq_ruler_start(p);\n\n"
     "\t/* Trigger a measurement */\n\tusb_reinit_cancel(&m->rd_sync);\t\t\t/* Prepare to sync rd and trigger */\n"),
    ("\tif ((ev = i1pro_trigger_one_measure(p, minnummeas, inttime, gainmode, mmod)) != I1PRO_OK) {\n\t\treturn ev;\n\t}\n\n"
     "\tif ((ev = i1pro_readmeasurement(p, minnummeas, m->c_measmodeflags & I1PRO_MMF_SCAN,\n"
     "\t                                             buf, bsize, nmeasuered, mmod)) != I1PRO_OK) {\n\t\treturn ev;\n\t}\n",
     "\tif ((ev = i1pro_trigger_one_measure(p, minnummeas, inttime, gainmode, mmod)) != I1PRO_OK) {\n"
     "\t\ti1pro2_cq_ruler_finish(p, 0, ev);\t/* CHROMIQ PATCH: ruler check (Beta), a no-op unless armed */\n\t\treturn ev;\n\t}\n\n"
     "\tif ((ev = i1pro_readmeasurement(p, minnummeas, m->c_measmodeflags & I1PRO_MMF_SCAN,\n"
     "\t                                             buf, bsize, nmeasuered, mmod)) != I1PRO_OK) {\n"
     "\t\ti1pro2_cq_ruler_finish(p, 0, ev);\t/* CHROMIQ PATCH: ruler check (Beta), a no-op unless armed */\n\t\treturn ev;\n\t}\n"
     "\ti1pro2_cq_ruler_finish(p, *nmeasuered, ev);\t/* CHROMIQ PATCH: ruler check (Beta), a no-op unless armed */\n"),
    ("\t\tif (maxval[j] < 1.0)\n\t\t\tmaxval[j] = 1.0;\n\t}\n\n#ifdef PATREC_DEBUG\n\tplot = dmatrixz(0, 10, 0, nummeas-1);",
     "\t\tif (maxval[j] < 1.0)\n\t\t\tmaxval[j] = 1.0;\n\t}\n"
     "\ti1pro2_cq_ruler_trace(p, multimeas, nummeas, maxval);\t/* CHROMIQ PATCH: ruler check, a copy */\n"
     "\n#ifdef PATREC_DEBUG\n\tplot = dmatrixz(0, 10, 0, nummeas-1);"),
    ("\t\tif (pat[k].use == 0)\n\t\t\tcontinue;\n\n\t\tif (pat[k].no <= MIN_SAMPLES) {",
     "\t\tif (pat[k].use == 0)\n\t\t\tcontinue;\n\n"
     "\t\ti1pro2_cq_ruler_cut(p, pix, pat[k].ss, pat[k].no);\t/* CHROMIQ PATCH: ruler check, a copy */\n\n"
     "\t\tif (pat[k].no <= MIN_SAMPLES) {"),
    ("\t\t/* i1pro_terminate_switch() seems to fail on a rev A & Rev C ?? */\n",
     "\t\t/* CHROMIQ PATCH: ruler check (Beta): a ruler read still running is */\n"
     "\t\t/* ended host side and joined before anything is torn down. */\n"
     "\t\ti1pro2_cq_ruler_close(p);\n\n"
     "\t\t/* i1pro_terminate_switch() seems to fail on a rev A & Rev C ?? */\n"),
    ("\tm->cq_lights = CQ_LIGHTS_DONE;\n\tm->cq_lights_owed = 0;\n\treturn off;\n}\n",
     "\tm->cq_lights = CQ_LIGHTS_DONE;\n\tm->cq_lights_owed = 0;\n\treturn off;\n}\n"
     + I1PRO_IMP_C_RULER_BLOCK),
]
I1PRO3_IMP_H_RULER = [
    ("\t/* Block 6 */\n\tint ee_unk34;\n",
     "\t/* CHROMIQ PATCH: the ruler check (Beta, 2026-11-14). All 0 = not in use. */\n"
     "\tint cq_ruler_on;\n\tint cq_ruler_armed;\n\tint cq_ruler_recording;\n"
     "\tvoid *cq_ruler_rec;\t\t/* cq_ruler_rec (cq_ruler.h) */\n\n"
     "\t/* Block 6 */\n\tint ee_unk34;\n"),
    ("/* CHROMIQ PATCH: i1Pro 3 indicator lights (Beta), see i1pro3_imp.c. Every\n",
     "/* CHROMIQ PATCH: the ruler check (Beta), see i1pro3_imp.c. Nothing new is sent. */\n"
     "int i1pro3_cq_ruler_options(void *pp, int on);\n"
     "void i1pro3_cq_ruler_arm(void *pp, int on);\n"
     "int i1pro3_cq_ruler_state(void *pp);\n"
     "int i1pro3_cq_ruler_firmware(void *pp);\n"
     "int i1pro3_cq_ruler_sensor(void *pp);\n"
     "int i1pro3_cq_ruler_take(void *pp, void *out);\n"
     "void i1pro3_cq_ruler_zeb(void *pp, unsigned char *zeb, int numzeb, int nummeas, int intclocks, double inttime, int zbytes);\n"
     "void i1pro3_cq_ruler_used(void *pp, int used, int npos);\n"
     "void i1pro3_cq_ruler_failed(void *pp, int err);\n"
     "void i1pro3_cq_ruler_trace(void *pp, double **rawmeas, int nummeas, double *maxval, int slots);\n"
     "void i1pro3_cq_ruler_cut(void *pp, void *pat, int npat, int slots);\n"
     "void i1pro3_cq_ruler_close(void *pp);\n\n"
     "/* CHROMIQ PATCH: i1Pro 3 indicator lights (Beta), see i1pro3_imp.c. Every\n"),
]
I1PRO3_IMP_C_RULER_BLOCK = r"""
/* ============================================================ */
/* CHROMIQ PATCH: the ruler check (Preferences > Beta, 2026-11-14; stage 1,
 * CHECK ONLY), the i1Pro 3 / 3 Plus. NOTHING NEW IS SENT: ArgyllCMS already
 * asks for the zebra ruler on every hand-held strip scan and reads it on 0x84
 * (i1pro3_do_measure, i1pro3_zebra_proc). While ChromIQ's helper has armed one
 * read_strip, these hooks only COPY what the driver already has: the decoded
 * ruler samples (before ArgyllCMS frees them), the counts, whether ArgyllCMS
 * placed the patches by the ruler (p2m), where its recogniser cut and a coarse
 * trace. ArgyllCMS's own behaviour (a failed ruler read fails the strip; its
 * own count check) is unchanged, option on or off.
 */
#include "cq_ruler.h"

static cq_ruler_rec *cq3_ruler_r(i1pro3imp *m) {
	return (cq_ruler_rec *)m->cq_ruler_rec;
}

int i1pro3_cq_ruler_options(void *pp, int on) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m;
	if (p == NULL || (m = (i1pro3imp *)p->m) == NULL)
		return 0;
	if (!on || p->dtype != instI1Pro3 || !p->inited)
		return 0;
	if (m->cq_ruler_rec == NULL
	 && (m->cq_ruler_rec = calloc(1, sizeof(cq_ruler_rec))) == NULL)
		return 0;
	m->cq_ruler_on = 1;
	return 1;
}

void i1pro3_cq_ruler_arm(void *pp, int on) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m;
	if (p == NULL || (m = (i1pro3imp *)p->m) == NULL || !m->cq_ruler_on)
		return;
	if (on && cq3_ruler_r(m) != NULL)
		cq_ruler_rec_clear(cq3_ruler_r(m));
	m->cq_ruler_armed = on;
	m->cq_ruler_recording = 0;
}

/* -1 = not in use, 0 = in use (the i1Pro 3 never gives the ruler up: nothing
 * of ChromIQ's runs on its USB). */
int i1pro3_cq_ruler_state(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	if (p == NULL || p->m == NULL || !((i1pro3imp *)p->m)->cq_ruler_on)
		return -1;
	return 0;
}

/* The firmware (version x 100), as the lights report it. */
int i1pro3_cq_ruler_firmware(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	if (p == NULL || p->m == NULL)
		return -1;
	return ((i1pro3imp *)p->m)->fwver;
}

/* Whether the instrument's EEPROM says it has the ruler sensor. */
int i1pro3_cq_ruler_sensor(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	if (p == NULL || p->m == NULL)
		return 0;
	return (((i1pro3imp *)p->m)->capabilities & I1PRO3_CAP_ZEB_RUL) != 0;
}

int i1pro3_cq_ruler_take(void *pp, void *vout) {
	i1pro3 *p = (i1pro3 *)pp;
	cq_ruler_rec *out = (cq_ruler_rec *)vout;
	i1pro3imp *m;
	cq_ruler_rec *r;
	if (out != NULL)
		memset(out, 0, sizeof(*out));
	if (p == NULL || (m = (i1pro3imp *)p->m) == NULL
	 || (r = cq3_ruler_r(m)) == NULL || !r->valid || out == NULL)
		return 0;
	*out = *r;
	memset(r, 0, sizeof(*r));
	m->cq_ruler_recording = 0;
	return 1;
}

/* i1pro3_do_measure: the decoded samples, before ArgyllCMS processes and
 * frees them. One-shot: only the armed strip's scan. */
void i1pro3_cq_ruler_zeb(void *pp, unsigned char *zeb, int numzeb,
                         int nummeas, int intclocks, double inttime, int zbytes) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = (i1pro3imp *)p->m;
	cq_ruler_rec *r = cq3_ruler_r(m);
	long pos = 0, last_at = -1;
	int last_code = -1;
	if (!m->cq_ruler_on || !m->cq_ruler_armed || r == NULL)
		return;
	m->cq_ruler_armed = 0;
	cq_ruler_rec_clear(r);
	r->valid = 1;
	r->gen = 3;
	r->ended = CQ_RULER_END_ARGYLL;
	r->readings = nummeas;
	r->clocks = intclocks;
	r->clock_s = m->intclkp;
	r->inttime = inttime;
	r->bytes = zbytes;
	if (zeb != NULL && numzeb > 0)
		cq_ruler_rec_feed(r, zeb, numzeb, &pos, &last_at, &last_code);
	r->samples = numzeb > 0 ? numzeb : 0;
	m->cq_ruler_recording = 1;
}

/* ...and whether ArgyllCMS then used it to place the patches. */
void i1pro3_cq_ruler_used(void *pp, int used, int npos) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = (i1pro3imp *)p->m;
	if (m->cq_ruler_recording && cq3_ruler_r(m) != NULL) {
		cq3_ruler_r(m)->argyll_used = used;
		cq3_ruler_r(m)->npos = npos;
	}
}

/* ArgyllCMS's own ruler read failed (it fails the strip, as always). */
void i1pro3_cq_ruler_failed(void *pp, int err) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = (i1pro3imp *)p->m;
	cq_ruler_rec *r = cq3_ruler_r(m);
	if (!m->cq_ruler_on || !m->cq_ruler_armed || r == NULL)
		return;
	m->cq_ruler_armed = 0;
	cq_ruler_rec_clear(r);
	r->valid = 1;
	r->gen = 3;
	r->ended = CQ_RULER_END_ERROR;
	r->icom_err = err;
}

/* i1pro3_locate_patches: copies only, while a record is open. */
void i1pro3_cq_ruler_trace(void *pp, double **rawmeas, int nummeas,
                           double *maxval, int slots) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = (i1pro3imp *)p->m;
	if (m->cq_ruler_recording && cq3_ruler_r(m) != NULL)
		cq_ruler_rec_trace(cq3_ruler_r(m), rawmeas, nummeas, maxval,
		                   m->nraw, slots ? 1 : 0);
}

void i1pro3_cq_ruler_cut(void *pp, void *vpat, int npat, int slots) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m = (i1pro3imp *)p->m;
	i1pro3_patch *pat = (i1pro3_patch *)vpat;
	int k, pix = 0;
	if (!m->cq_ruler_recording || cq3_ruler_r(m) == NULL || pat == NULL)
		return;
	for (k = 1; k < (npat - 1); k++) {
		if (!pat[k].use)
			continue;
		cq_ruler_rec_cut(cq3_ruler_r(m), pix++, pat[k].ss, pat[k].no,
		                 slots ? 1 : 0);
	}
}

void i1pro3_cq_ruler_close(void *pp) {
	i1pro3 *p = (i1pro3 *)pp;
	i1pro3imp *m;
	if (p == NULL || (m = (i1pro3imp *)p->m) == NULL)
		return;
	if (m->cq_ruler_rec != NULL) {
		cq_ruler_rec_clear(cq3_ruler_r(m));
		free(m->cq_ruler_rec);
		m->cq_ruler_rec = NULL;
	}
	m->cq_ruler_on = m->cq_ruler_armed = m->cq_ruler_recording = 0;
}
"""
I1PRO3_IMP_C_RULER = [
    ("\t\tif (m->zebra_rv != I1PRO3_OK) {\n\t\t\ta1logd(p->log,1,\"i1pro3_zebra_thread failed with %d\\n\",m->zebra_rv);\n",
     "\t\tif (m->zebra_rv != I1PRO3_OK) {\n"
     "\t\t\ti1pro3_cq_ruler_failed(p, m->zebra_rv);\t/* CHROMIQ PATCH: ruler check, a note */\n"
     "\t\t\ta1logd(p->log,1,\"i1pro3_zebra_thread failed with %d\\n\",m->zebra_rv);\n"),
    ("\t\t/* Process the raw data into a list of meas patches at each 0.2 mm location */\n"
     "\t\tif ((ev = i1pro3_zebra_proc(p, p_p2m, p_npos, zeb, numzeb, inttime, nummeas)) != I1PRO3_OK)\n\t\t\treturn ev;\n",
     "\t\t/* CHROMIQ PATCH: ruler check (Beta): a copy, a no-op unless armed */\n"
     "\t\ti1pro3_cq_ruler_zeb(p, zeb, numzeb, nummeas, intclocks, inttime, m->zebra_bread);\n\n"
     "\t\t/* Process the raw data into a list of meas patches at each 0.2 mm location */\n"
     "\t\tif ((ev = i1pro3_zebra_proc(p, p_p2m, p_npos, zeb, numzeb, inttime, nummeas)) != I1PRO3_OK)\n\t\t\treturn ev;\n"
     "\t\ti1pro3_cq_ruler_used(p, *p_p2m != NULL, p_npos != NULL ? *p_npos : 0);\t/* CHROMIQ PATCH: ruler check */\n"),
    ("\t\tif (maxval[j] < 1.0)\n\t\t\tmaxval[j] = 1.0;\n\t}\n\n#ifdef PATREC_DEBUG\n\tplot = dmatrixz(0, 10, 0, nummeas-1);",
     "\t\tif (maxval[j] < 1.0)\n\t\t\tmaxval[j] = 1.0;\n\t}\n"
     "\ti1pro3_cq_ruler_trace(p, rawmeas, nummeas, maxval, p2m != NULL);\t/* CHROMIQ PATCH: ruler check, a copy */\n"
     "\n#ifdef PATREC_DEBUG\n\tplot = dmatrixz(0, 10, 0, nummeas-1);"),
    ("\t\tpat[k].ss += trim;\n\t\tpat[k].no = nnn;\n\t}\n",
     "\t\tpat[k].ss += trim;\n\t\tpat[k].no = nnn;\n\t}\n"
     "\ti1pro3_cq_ruler_cut(p, pat, npat, p2m != NULL);\t/* CHROMIQ PATCH: ruler check, a copy */\n"),
    ("\t\t/* Terminate event monitor thread */\n\t\tif (m->th != NULL) {\n\t\t\tm->th_term = 1;",
     "\t\t/* Terminate event monitor thread */\n"
     "\t\ti1pro3_cq_ruler_close(p);\t/* CHROMIQ PATCH: ruler check (Beta), frees its record */\n"
     "\t\tif (m->th != NULL) {\n\t\t\tm->th_term = 1;"),
    ("\n/* ============================================================ */\n/* Parse the EEProm contents */",
     I1PRO3_IMP_C_RULER_BLOCK
     + "\n/* ============================================================ */\n/* Parse the EEProm contents */"),
]
# ---- END RULER CHECK ----
# ChromIQ (2026-11-14, the ruler check's review, item 4): ArgyllCMS counts
# the USB transfers in progress in a plain shared int (`in_usb_rw`). Every
# back end (usbio_ox.c, usbio_lx.c, usbio_w0.c, usbio_dk.c, usbio_bsd.c, all
# #included into usbio.c) increments it before a transfer and decrements it
# after, and a transfer that finds it below zero calls exit(0), meant for the
# signal handler's cleanup. Two threads updating it at once can lose an update
# and end the helper silently with status 0 in the middle of a measurement.
# Today two threads already overlap (a measurement read and the i1Pro's button
# thread); the ruler check adds a third. Making the counter atomic (C11
# `_Atomic`, which GCC and Clang accept in this build's gnu99 mode, as
# every ChromIQ helper build uses: Apple Clang, GCC on Linux, MinGW GCC and
# LLVM-MinGW on Windows) turns every ++, -- and comparison into an atomic
# operation without touching any back-end line. It is not part of any
# request: nothing on the wire changes. A compiler without atomics keeps the
# plain int (upstream behaviour).
USBIO_PATCHES = [
    ("/* Counter set when we're in a USB read or write */\n"
     "/* Note - this isn't perfectly thread safe */\n"
     "int in_usb_rw = 0;\n",
     "/* Counter set when we're in a USB read or write */\n"
     "/* Note - this isn't perfectly thread safe */\n"
     "/* CHROMIQ PATCH: atomic, so that two transfers on different threads can */\n"
     "/* never lose an update and end the process through the exit(0) below */\n"
     "/* (see scripts/vendor_instlib.py, USBIO_PATCHES). No wire change. */\n"
     "#if !defined(__STDC_NO_ATOMICS__) && (defined(__GNUC__) || defined(__clang__) \\\n"
     "     || (defined(__STDC_VERSION__) && __STDC_VERSION__ >= 201112L))\n"
     "_Atomic int in_usb_rw = 0;\n"
     "#else\n"
     "int in_usb_rw = 0;\n"
     "#endif\n"),
]
PATCHES = {
    "rspl1.c": [(RSPL1_UPSTREAM, RSPL1_PATCHED)],
    "conv.c": CONV_PATCHES,
    "usbio.c": USBIO_PATCHES,
    "i1pro_imp.h": I1PRO_IMP_H_LIGHTS + I1PRO_IMP_H_RULER,
    "i1pro_imp.c": I1PRO_IMP_C_LIGHTS + I1PRO_IMP_C_RULER,
    "i1pro.c": I1PRO_C_LIGHTS,
    "i1pro3_imp.h": I1PRO3_IMP_H_LIGHTS + I1PRO3_IMP_H_RULER,
    "i1pro3_imp.c": I1PRO3_IMP_C_LIGHTS + I1PRO3_IMP_C_RULER,
    "i1pro3.c": I1PRO3_C_LIGHTS,
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
    "Nine library files depart from upstream. `scripts/vendor_instlib.py`\n"
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
    "  Two choices inside the option (2026-11-13, both off = the above, byte\n"
    "  for byte): result signals (`--lights-signals`) and lights left on during\n"
    "  a hand-held reading (`--lights-during-reading`). They add three more\n"
    "  sequences, all sent by i1Profiler 3.8.6 to a user's own i1Pro 2 in a\n"
    "  hand-held Windows recording: PULSE (2306 bytes, a soft white pulse,\n"
    "  byte for byte Argyll's own `b3`) as the ready light, GREEN2 (2990\n"
    "  bytes) after a reading ChromIQ accepted and RED2 (2990 bytes) after one\n"
    "  it refused. They live in ChromIQ's own `cq_i1pro2_programs.h` (not an\n"
    "  Argyll file; this script never writes it), pinned by sha256 in\n"
    "  `tests/test_i1pro2_light_programs.py`. They were recorded on firmware\n"
    "  634 and go, like the three above, to any i1Pro 2 the block accepts\n"
    "  (no firmware condition, as in Argyll's own light code).\n"
    "- **`i1pro3_imp.c`, `i1pro3_imp.h`, `i1pro3.c`: the same Beta for the\n"
    "  i1Pro 3** (2026-11-13). Its own request and format (0x29, LE32 length,\n"
    "  bytes on bulk endpoint 0x02, Argyll's `i1pro3_indLEDseq`). Exactly four\n"
    "  sequences: Argyll's own off `00` (sent by unpatched Argyll at every open)\n"
    "  before every measurement (top of `i1pro3_do_measure`) and at the close;\n"
    "  and, only after a measurement has returned, three patterns X-Rite's\n"
    "  i1Profiler 3.8.5 sent to a user's own i1Pro 3 in one USB recording, each\n"
    "  where i1Profiler sent it: READY `01 fa 04 12 05 00` after a successful\n"
    "  calibration, GOOD `0a 14 02 12 05 00` after a reading, BAD\n"
    "  `06 14 02 12 05 00` after a reading the instrument could not take. Inert\n"
    "  until the helper calls `i1pro3_cq_lights_begin` (option on), which\n"
    "  refuses anything but an inited i1Pro 3 (3 and 3 Plus, one dtype) whose\n"
    "  EEPROM reports the indicator LEDs. No 0x3B, no memory write. Not tested\n"
    "  on a real i1Pro 3 by the project.\n"
    "  Since 2026-11-14 the i1Pro 2's two choices apply here too\n"
    "  (`i1pro3_cq_lights_options`; both 0 = the 4.3.34 behaviour above, byte\n"
    "  for byte): result signals (GOOD / BAD / READY sent by the helper for\n"
    "  ChromIQ's own verdict on a strip or patch, only while one is owed and\n"
    "  never once the button was pressed for the next reading) and lights left\n"
    "  on during a reading (no off before the measurements of a hand-held\n"
    "  reading, as i1Profiler; a calibration still gets the off). The same\n"
    "  four sequences, nothing else.\n"
    "  Not tested on a real i1Pro 2 by the project.\n"
    "- **`i1pro_imp.c`, `i1pro_imp.h`, `i1pro3_imp.c`, `i1pro3_imp.h`: the ruler\n"
    "  check** (Preferences > Beta, 2026-11-14; stage 1, check only). Inert\n"
    "  until ChromIQ's helper switches it on (`--ruler`) and arms one strip.\n"
    "  i1Pro 2 (EEPROM reports `I1PRO_CAP2_ZEB_RUL`): the armed strip's lit\n"
    "  scan gets RULER_START | RULER_END (0x0004 | 0x0008) in the 0xD4 flags,\n"
    "  and the ruler stream is read on bulk IN 0x85 in 4096-byte reads until a\n"
    "  short read ends it: exactly what X-Rite's i1Profiler 3.8.6 does on every\n"
    "  strip scan in two USB recordings of a user's own i1Pro 2 (firmware 634).\n"
    "  Never 0xD7 (stop ruler), never anything else. Anything unusual gives the\n"
    "  ruler up for the session; a stream that does not end by itself is\n"
    "  drained until it does or the instrument is closed (on macOS that close\n"
    "  is a host-side abort, which IOKit follows with a clear-halt request).\n"
    "  i1Pro 3: nothing new on the wire; copies of the ruler samples ArgyllCMS\n"
    "  already reads. Both: read-only copies of where the recogniser cut and a\n"
    "  coarse trace, into ChromIQ's own `cq_ruler.h` record (not an Argyll file;\n"
    "  this script never writes it). Values and patch assignment never change.\n"
    "  Not tested on a real instrument by the project.\n"
    "- **`usbio.c`, the transfer counter `in_usb_rw`** (2026-11-14): made\n"
    "  atomic (C11 `_Atomic`, kept plain where a compiler has no atomics).\n"
    "  Every USB back end (macOS, Linux, Windows) counts transfers in it and\n"
    "  calls exit(0) when it goes below zero; two threads updating the plain\n"
    "  int at once could lose an update and end the helper silently. This is\n"
    "  shared USB code, so it concerns every USB instrument the ChromIQ helper\n"
    "  drives. Nothing on the wire changes.\n\n"
    "| patched file | upstream sha256 (first 16) | shipped sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(patched) + "\n\n"
    "## Files\n\n"
    "- Upstream: https://www.argyllcms.com/ (Argyll_V3.5.0)\n\n"
    "| vendored file | upstream path | upstream sha256 (first 16) |\n"
    "|---|---|---|\n" + "\n".join(lines) + "\n"
, encoding="utf-8")
print(f"vendored {len(FILES)} files → {DST}")
