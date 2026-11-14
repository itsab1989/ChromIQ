/* i1pro3_lights_modes_test: the lights Beta's two choices (result signals,
 * lights during a reading) on an i1Pro 3 (2026-11-14), on a FAKE USB layer,
 * through the REAL vendored driver code. Nothing here touches real hardware.
 *
 * One whole life of an instrument per scenario, in the order the driver
 * (i1pro3.c) and ChromIQ's helper (chromiq_chartread.c) make the calls:
 * calibration, strips accepted / refused / without a verdict / with a late
 * verdict / with the button pressed before the verdict, a patch, an aborted
 * reading, a second calibration, an EEPROM read, the close. Every USB request
 * is printed as one line (the format of i1pro3_lights_test.c);
 * tests/test_i1pro3_lights_modes.py reads the trace.
 *
 * Compiled with CQ_V4334 against the driver of ChromIQ 4.3.34 (v4.3.34),
 * which has none of the new entries, the same life is what 4.3.34 put on the
 * wire: tests/data/i1pro3_lights_v4334_trace.txt is that output
 * (scripts/make_lights_v4334_fixtures.py makes it again). With both choices
 * off, this tree must print exactly that.
 *
 * Failure scenarios: the Nth light request (0x29) fails after blocking for
 * its whole timeout, as a dead transfer would; the trace says how long each
 * measurement took ("MEASURE-MS"), so the test can bound the delay.
 * AGPL-3.0 like the rest of the helper (see ../../instlib/License.txt). */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "numsup.h"
#include "rspl1.h"
#include "cgats.h"
#include "xspect.h"
#include "insttypes.h"
#include "conv.h"
#include "icoms.h"
#include "inst.h"
#include "i1pro3.h"
#include "i1pro3_imp.h"

static const char *scn = "?";
static int fail_29_at = 0, n_29 = 0;
static volatile int trig_sent = 0;	/* a measure request (0x22/0x27) went out */
static i1pro3imp *cur_m = NULL;		/* the instrument of the current life */
static int press_on_write = 0;		/* the button is pressed during a light's bytes */

static void hex(const unsigned char *b, int n) {
	int i;
	for (i = 0; i < n; i++)
		printf("%02x", b[i]);
}

static int fake_control(icoms *p, int requesttype, int request, int value,
                        int index, unsigned char *rwbuf, int rwsize,
                        int *xferred, double tout) {
	(void)p; (void)value; (void)index;
	printf("%s CTL %02x ", scn, request & 0xff);
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) == IUSB_ENDPOINT_OUT)
		hex(rwbuf, rwsize);
	else
		printf("in%d", rwsize);
	printf(" tout=%.2f\n", tout);
	fflush(stdout);
	if (xferred != NULL)
		*xferred = rwsize;
	if (request == 0x22 || request == 0x27)
		trig_sent = 1;
	if (request == 0x29) {
		n_29++;
		if (fail_29_at && n_29 == fail_29_at) {
			/* a dead transfer: it uses its whole timeout, then fails */
			msec_sleep((unsigned int)(tout * 1000.0 + 0.5));
			printf("%s FAIL 29\n", scn);
			fflush(stdout);
			return ICOM_TO;
		}
	}
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) != IUSB_ENDPOINT_OUT && rwbuf != NULL)
		memset(rwbuf, 0, rwsize);
	return ICOM_OK;
}

static int fake_write(icoms *p, usb_cancelt *c, int ep, unsigned char *wbuf,
                      int wsize, int *bwritten, double tout) {
	(void)p; (void)c;
	printf("%s WR %02x ", scn, ep & 0xff);
	hex(wbuf, wsize);
	printf(" tout=%.2f\n", tout);
	fflush(stdout);
	*bwritten = wsize;
	if (press_on_write && ep == 0x02 && cur_m != NULL) {
		press_on_write = 0;
		cur_m->switch_count++;		/* the switch thread saw a press */
		printf("%s PRESS\n", scn);
		fflush(stdout);
	}
	return ICOM_OK;
}

static int fake_read(icoms *p, usb_cancelt *c, int ep, unsigned char *buf,
                     int bsize, int *bread, double tout) {
	(void)p; (void)tout;
	memset(buf, 0, bsize);
	if (c != NULL) {
		amutex_unlock(c->condx);
		while (!trig_sent)
			msec_sleep(1);
		trig_sent = 0;
	}
	printf("%s RD %02x %d\n", scn, ep & 0xff, bsize);
	fflush(stdout);
	*bread = bsize;
	return ICOM_OK;
}

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p;
	if (c != NULL) {			/* wait until the read has started */
		amutex_lock(c->condx);
		amutex_unlock(c->condx);
	}
	return ICOM_OK;
}

#ifndef CQ_V4334
static void note(int seq, int err) {
	printf("%s NOTE seq=%d err=0x%x\n", scn, seq, err);
	fflush(stdout);
}
static void sent(int seq) {
	printf("%s SENT seq=%d\n", scn, seq);
	fflush(stdout);
}
#endif

static int fwver = 0;

static i1pro3 *make(int aperture) {
	i1pro3 *p = (i1pro3 *)calloc(1, sizeof(i1pro3));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1pro3imp *m;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	p->log = new_a1log_d(NULL);
	p->dtype = instI1Pro3;
	p->icom = ic;
	p->gotcoms = 1;
	p->inited = 1;
	if (add_i1pro3imp(p) != I1PRO3_OK) {
		fprintf(stderr, "add_i1pro3imp failed\n");
		exit(2);
	}
	m = (i1pro3imp *)p->m;
	m->capabilities = I1PRO3_CAP_IND_LED;
	m->aperture = aperture;
	m->fwver = fwver;
	usb_init_cancel(&m->rd_sync);
	usb_init_cancel(&m->rd_sync2);
	m->intclkp = 15.3e-6;
	m->min_int_time = 0.0025;
	m->nsen1 = 134;
	m->nsen2 = 282;
	m->nraw = 128;
	m->msec = msec_time();
	n_29 = 0;
	cur_m = m;
	return p;
}

static void step(const char *what) {
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
}

/* One measurement through the driver's own core function (an emissive dark
 * reading, the simplest thing i1pro3_do_measure does), timed. */
static int measure(i1pro3 *p, const char *what) {
	double **raw = NULL;
	int nummeas = 1;
	double inttime = 0.01;
	unsigned int t0;
	i1pro3_code ev;
	step(what);
	t0 = msec_time();
	ev = i1pro3_do_measure(p, i1p3mm_em, &raw, &nummeas, &inttime, NULL, NULL);
	printf("%s MEASURE-MS %u\n", scn, msec_time() - t0);
	if (raw != NULL)
		free_dmatrix(raw, 0, nummeas-1, -1, ((i1pro3imp *)p->m)->nraw-1);
	if (ev != I1PRO3_OK)
		printf("%s MEASURE-RETURNED 0x%x\n", scn, ev);
	return ev;
}

/* i1pro3_calibrate (i1pro3.c): the calibration's measurements, then the hook. */
static void calibrate(i1pro3 *p) {
	measure(p, "cal-dark");
	measure(p, "cal-white");
	step("cal-returned");
	i1pro3_cq_lights_after_cal(p, I1PRO3_OK);
}

/* i1pro3_read_strip / i1pro3_read_sample (i1pro3.c): the reading's dark and
 * lit measurements between the reading hooks; rv is what imp_measure returns.
 * The instrument's button starts it (the switch thread counts the press),
 * unless by_keyboard is set. */
static int by_keyboard = 0;
static void reading(i1pro3 *p, const char *what, int rv) {
	char b[64];
	snprintf(b, sizeof(b), "%s-start", what);
	step(b);
#ifndef CQ_V4334
	i1pro3_cq_lights_reading(p, 1);
#endif
	if (rv != I1PRO3_USER_ABORT && !by_keyboard)
		((i1pro3imp *)p->m)->switch_count++;	/* the press */
	if (rv != I1PRO3_USER_ABORT) {
		measure(p, "read-dark");
		measure(p, "read-lit");
	}
	snprintf(b, sizeof(b), "%s-returned", what);
	step(b);
	i1pro3_cq_lights_after_read(p, rv);
}

/* The helper's calls, made only when result signals are on (exactly as
 * cq_lights_signals_on() gates them); 4.3.34's helper made none for an i1Pro 3. */
static int sig = 0;
static void helper_prompt(i1pro3 *p) {
#ifndef CQ_V4334
	if (sig) {
		step("helper-prompt");
		if (i1pro3_cq_lights_owed_ms(p) < 0)
			i1pro3_cq_lights_result(p, -1);
	}
#else
	(void)p;
#endif
}
static void helper_say(i1pro3 *p, int good, const char *what) {
#ifndef CQ_V4334
	if (sig) {
		step(what);
		i1pro3_cq_lights_result(p, good);
	}
#else
	(void)p; (void)good; (void)what;
#endif
}
static void helper_owe(i1pro3 *p) {
#ifndef CQ_V4334
	if (sig) {
		step("helper-owe");
		i1pro3_cq_lights_owe(p);
	}
#else
	(void)p;
#endif
}
static void helper_poll(i1pro3 *p, int verdict, const char *what) {
#ifndef CQ_V4334
	if (sig) {
		step(what);
		if (i1pro3_cq_lights_owed_ms(p) < 0) {
			step("poll-nothing-owed");
			return;
		}
		i1pro3_cq_lights_result(p, verdict);
	}
#else
	(void)p; (void)verdict; (void)what;
#endif
}

static void close_it(i1pro3 *p) {
	icoms *ic = p->icom;
	a1log *lg = p->log;
	step("close");
	cur_m = NULL;
	del_i1pro3imp(p);
	free(p);
	free(ic);
	del_a1log(lg);
	printf("%s END\n", scn);
	fflush(stdout);
}

/* One whole life. asked = the Beta option is on (the helper calls begin). */
static void life(const char *name, int asked, int signals, int left_on,
                 int aperture) {
	i1pro3 *p;
	unsigned char ee[64];
	scn = name;
	sig = asked ? signals : 0;
	p = make(aperture);
	if (asked) {
		step("begin");
#ifndef CQ_V4334
		i1pro3_cq_lights_options(p, signals, left_on);
#else
		(void)left_on;
#endif
		printf("%s BEGIN %d\n", scn, i1pro3_cq_lights_begin(p));
#ifndef CQ_V4334
		printf("%s CHOICES %d FW %d\n", scn, i1pro3_cq_lights_choices(p),
		       i1pro3_cq_lights_firmware(p));
#endif
	}
	calibrate(p);
	/* strip A: accepted by ChromIQ (GUI verdict good) */
	helper_prompt(p);
	reading(p, "strip-A", I1PRO3_OK);
	helper_owe(p);
	helper_prompt(p);				/* the next prompt: a result is owed */
	helper_poll(p, 1, "verdict-good");
	/* strip B: the instrument could not take it: the helper refuses it */
	helper_prompt(p);
	reading(p, "strip-B", I1PRO3_RD_SHORTMEAS);
	helper_say(p, 0, "helper-red");
	/* strip C: accepted, but ChromIQ asks again (GUI verdict bad) */
	helper_prompt(p);
	reading(p, "strip-C", I1PRO3_OK);
	helper_owe(p);
	helper_poll(p, 0, "verdict-bad");
	/* strip D: accepted, no verdict comes: the ready light after 3 s */
	helper_prompt(p);
	reading(p, "strip-D", I1PRO3_OK);
	helper_owe(p);
	helper_poll(p, -1, "verdict-timeout");
	/* strip E: accepted, the user reads the next strip before the verdict */
	helper_prompt(p);
	reading(p, "strip-E", I1PRO3_OK);
	helper_owe(p);
	reading(p, "strip-F", I1PRO3_OK);	/* its measurements end what was owed */
	helper_poll(p, 1, "verdict-late");	/* E's verdict: dropped */
	helper_owe(p);
	helper_poll(p, 1, "verdict-good-F");
	/* strip H: accepted; the button is pressed for the next strip before
	 * the verdict is acted on: the driver refuses it. */
	helper_prompt(p);
	reading(p, "strip-H", I1PRO3_OK);
	helper_owe(p);
#ifndef CQ_V4334
	if (sig) {
		i1pro3imp *m = (i1pro3imp *)p->m;
		step("press-next");
		i1pro3_cq_lights_reading(p, 1);	/* the next read_strip began */
		m->switch_count++;				/* the switch thread saw a press */
		helper_poll(p, 1, "verdict-after-press");
		i1pro3_cq_lights_reading(p, 0);
	}
#endif
	/* a patch, read by hand and kept */
	helper_prompt(p);
	reading(p, "patch-1", I1PRO3_OK);
	helper_say(p, 1, "helper-green");
	/* a reading the user aborted before any measurement */
	helper_prompt(p);
	reading(p, "strip-X", I1PRO3_USER_ABORT);
	/* a calibration asked for between strips */
	helper_prompt(p);
	calibrate(p);
	helper_prompt(p);
	reading(p, "strip-G", I1PRO3_RD_READINCONS);
	helper_say(p, 0, "helper-red");
	step("eeprom");
	if (i1pro3_readEEProm(p, ee, 0x18, 64) != I1PRO3_OK)
		printf("%s EEPROM-FAILED\n", scn);
	close_it(p);
}

int main(void) {
	/* The Beta option off: the helper never calls begin(). */
	life("off", 0, 0, 0, 0);
	/* On, both choices off: ChromIQ 4.3.34 with the option on. */
	life("on_ready_off", 1, 0, 0, 0);
	life("plus_ready_off", 1, 0, 0, 1);
#ifndef CQ_V4334
	i1pro3_cq_lights_note = note;
	i1pro3_cq_lights_sent = sent;
	/* The three new combinations, i1Pro 3 and i1Pro 3 Plus (aperture 1). */
	life("on_signals_off", 1, 1, 0, 0);
	life("on_ready_lefton", 1, 0, 1, 0);
	life("on_signals_lefton", 1, 1, 1, 0);
	life("plus_signals_off", 1, 1, 0, 1);
	life("plus_ready_lefton", 1, 0, 1, 1);
	life("plus_signals_lefton", 1, 1, 1, 1);
	/* The button is pressed while a result's bytes are on their way (the
	 * switch thread sees it a few ms late): with "left on" the reading that
	 * press starts still gets the off before its measurements. */
	{
		i1pro3 *p;
		scn = "press_during_result";
		sig = 1;
		p = make(0);
		step("begin");
		i1pro3_cq_lights_options(p, 1, 1);
		printf("%s BEGIN %d\n", scn, i1pro3_cq_lights_begin(p));
		calibrate(p);
		reading(p, "strip-A", I1PRO3_OK);
		helper_owe(p);
		step("next-reading-waits");
		i1pro3_cq_lights_reading(p, 1);	/* read_strip began, armed wait */
		press_on_write = 1;
		helper_poll(p, 1, "verdict-good");	/* sent, the press lands in it */
		/* (the PRESS of the fake moved switch_count: a button reading) */
		measure(p, "read-dark");			/* the off after all */
		measure(p, "read-lit");
		step("strip-B-returned");
		i1pro3_cq_lights_after_read(p, I1PRO3_OK);
		helper_owe(p);
		helper_poll(p, 1, "verdict-good-B");
		reading(p, "strip-C", I1PRO3_OK);	/* left on again: no off */
		close_it(p);
	}
	/* A patch started from the keyboard (no press) under "left on": the off
	 * as in 4.3.34 (review item 2); the next one by the button: none. */
	{
		i1pro3 *p;
		scn = "keyboard_spot_lefton";
		sig = 0;
		p = make(0);
		step("begin");
		i1pro3_cq_lights_options(p, 0, 1);
		printf("%s BEGIN %d\n", scn, i1pro3_cq_lights_begin(p));
		calibrate(p);
		by_keyboard = 1;
		reading(p, "patch-key", I1PRO3_OK);
		by_keyboard = 0;
		reading(p, "patch-button", I1PRO3_OK);
		close_it(p);
	}
	/* The firmware is only reported, never a condition. */
	fwver = 123;
	life("fw123_signals_lefton", 1, 1, 1, 0);
	fwver = 0;
	/* Fault injection: the Nth light request is a dead transfer, in every
	 * combination; the measurement it precedes still runs. */
	{
		static char names[4][12][40];
		static const char *combo[4] = { "ready_off", "signals_off",
		                                "ready_lefton", "signals_lefton" };
		int c, k;
		for (c = 0; c < 4; c++) {
			for (k = 1; k <= 12; k++) {
				snprintf(names[c][k-1], 40, "fail%d_%s", k, combo[c]);
				fail_29_at = k;
				life(names[c][k-1], 1, c & 1, (c >> 1) & 1, 0);
			}
		}
		fail_29_at = 0;
	}
#endif
	printf("ALL DONE\n");
	return 0;
}
