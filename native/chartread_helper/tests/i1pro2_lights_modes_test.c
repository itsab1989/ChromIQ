/* i1pro2_lights_modes_test: the i1Pro 2 lights Beta with its two choices
 * (result signals, lights during a reading; 2026-11-13) on a FAKE USB layer,
 * through the REAL vendored driver code. Nothing here touches real hardware.
 *
 * One whole life of an instrument per scenario, in the order the driver
 * (i1pro.c) and ChromIQ's helper (chromiq_chartread.c) make the calls:
 * open, calibration, strips accepted / refused / without a verdict / with a
 * late verdict, a patch, a second calibration, an EEPROM read, the close.
 * Every USB request is printed as one line (the format of
 * i1pro2_lights_test.c); tests/test_i1pro2_lights_modes.py reads the trace.
 *
 * Compiled with CQ_V4333 against the driver of ChromIQ 4.3.33 (ee661dc65),
 * which has none of the new entries, the same life is what 4.3.33 put on the
 * wire: tests/data/i1pro2_lights_v4333_trace.txt is that output
 * (scripts/make_lights_v4333_fixture.py makes it again). With both choices
 * off, this tree must print exactly that.
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
#include "i1pro.h"
#include "i1pro_imp.h"
#ifndef CQ_V4333
#include "cq_beta_pause.h"	/* 4.3.36: the choices an i1Pro 2 is given */
#endif
#ifdef CQ_WATCHED
#include "chromiq_usbwatch.h"	/* 4.3.36: the helper's read-only USB watch */
#endif

static const char *scn = "?";

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
	return ICOM_OK;
}

static int fake_read(icoms *p, usb_cancelt *c, int ep, unsigned char *buf,
                     int bsize, int *bread, double tout) {
	(void)p; (void)c; (void)tout;
	printf("%s RD %02x %d\n", scn, ep & 0xff, bsize);
	fflush(stdout);
	memset(buf, 0, bsize);
	*bread = bsize;
	return ICOM_OK;
}

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p; (void)c;
	return ICOM_OK;
}

static int fwrev = 634;

static i1pro *make(devType dtype, int caps2) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
#ifdef CQ_WATCHED
	cq_usbwatch_install(ic, CQ_UW_I1PRO);	/* the same life, watched */
	cq_usbwatch_begin();
#endif
	p->log = new_a1log_d(NULL);
	p->dtype = dtype;
	p->icom = ic;
	p->gotcoms = 1;
	p->inited = 1;
	if (add_i1proimp(p) != I1PRO_OK) {
		fprintf(stderr, "add_i1proimp failed\n");
		exit(2);
	}
	m = (i1proimp *)p->m;
	m->capabilities2 = caps2;
	usb_init_cancel(&m->rd_sync);
	m->mmode = 0;
	m->ms[0].reflective = 1;
	m->ms[0].lamptime = 0.2;
	m->intclkp2 = 36e-6;
	m->subclkdiv2 = 136;
	m->min_int_time = 0.004;
	m->msec = msec_time();
	m->fwrev = fwrev;		/* 634: the firmware of every recording */
	return p;
}

static void step(const char *what) {
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
}

static void trigger(i1pro *p, const char *what) {
	i1proimp *m = (i1proimp *)p->m;
	double inttime = 0.02;
	step(what);
	if (i1pro_trigger_one_measure(p, 1, &inttime, 0, i1p_cal) != I1PRO_OK)
		printf("%s TRIGGER-FAILED\n", scn);
	amutex_unlock(m->rd_sync.condx);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
}

/* i1pro_calibrate (i1pro.c): the calibration's triggers, then the ready hook. */
static void calibrate(i1pro *p) {
	trigger(p, "cal-dark");
	trigger(p, "cal-white");
	step("cal-returned");
	i1pro2_cq_lights_ready(p);
}

/* i1pro_read_strip / i1pro_read_sample (i1pro.c): a scan's dark and lit
 * triggers, between the reading hooks. 4.3.33 called the ready hook after. */
static void reading(i1pro *p, const char *what) {
	char b[64];
	snprintf(b, sizeof(b), "%s-start", what);
	step(b);
#ifndef CQ_V4333
	i1pro2_cq_lights_reading(p, 1);
#endif
	trigger(p, "read-dark");
	trigger(p, "read-lit");
	snprintf(b, sizeof(b), "%s-returned", what);
	step(b);
#ifndef CQ_V4333
	i1pro2_cq_lights_after_read(p);
#else
	i1pro2_cq_lights_ready(p);
#endif
}

/* The helper's calls, made only when result signals are on (exactly as
 * cq_lights_signals_on() gates them); 4.3.33's helper had none. */
static int sig = 0;
static void helper_prompt(i1pro *p) {
#ifndef CQ_V4333
	if (sig) {
		step("helper-prompt");
		if (i1pro2_cq_lights_owed_ms(p) < 0)
			i1pro2_cq_lights_result(p, -1);
	}
#else
	(void)p;
#endif
}
static void helper_say(i1pro *p, int good, const char *what) {
#ifndef CQ_V4333
	if (sig) {
		step(what);
		i1pro2_cq_lights_result(p, good);
	}
#else
	(void)p; (void)good; (void)what;
#endif
}
static void helper_owe(i1pro *p) {
#ifndef CQ_V4333
	if (sig) {
		step("helper-owe");
		i1pro2_cq_lights_owe(p);
	}
#else
	(void)p;
#endif
}
/* The poll in the armed wait: a verdict (1/0) applied only while owed;
 * -1 = no verdict came and the wait ran out (the 2 s fallback). */
static void helper_poll(i1pro *p, int verdict, const char *what) {
#ifndef CQ_V4333
	if (sig) {
		step(what);
		if (i1pro2_cq_lights_owed_ms(p) < 0) {
			step("poll-nothing-owed");
			return;
		}
		i1pro2_cq_lights_result(p, verdict);
	}
#else
	(void)p; (void)verdict; (void)what;
#endif
}

static void close_it(i1pro *p) {
	icoms *ic = p->icom;
	a1log *lg = p->log;
	step("close");
	del_i1proimp(p);
	free(p);
	free(ic);
	del_a1log(lg);
	printf("%s END\n", scn);
	fflush(stdout);
}

/* One whole life. asked = the Beta option is on (the helper calls begin). */
static void life(const char *name, devType dtype, int asked, int signals,
                 int left_on) {
	i1pro *p;
	unsigned char ee[64];
	scn = name;
	sig = asked ? signals : 0;
	p = make(dtype, I1PRO_CAP2_IND_LED);
	if (asked) {
		step("begin");
#ifndef CQ_V4333
		i1pro2_cq_lights_options(p, signals, left_on);
#else
		(void)left_on;
#endif
		printf("%s BEGIN %d\n", scn, i1pro2_cq_lights_begin(p));
	}
	calibrate(p);
	/* strip A: accepted by ChromIQ (GUI verdict good) */
	helper_prompt(p);
	reading(p, "strip-A");
	helper_owe(p);
	helper_prompt(p);				/* the next prompt: a result is owed */
	helper_poll(p, 1, "verdict-good");
	/* strip B: the engine refuses it (a misread): red twice at once */
	helper_prompt(p);
	reading(p, "strip-B");
	helper_say(p, 0, "helper-red");
	/* strip C: accepted, but ChromIQ asks again (GUI verdict bad) */
	helper_prompt(p);
	reading(p, "strip-C");
	helper_owe(p);
	helper_poll(p, 0, "verdict-bad");
	/* strip D: accepted, no verdict comes: the ready light after 2 s */
	helper_prompt(p);
	reading(p, "strip-D");
	helper_owe(p);
	helper_poll(p, -1, "verdict-timeout");
	/* strip E: accepted, the user presses again before the verdict */
	helper_prompt(p);
	reading(p, "strip-E");
	helper_owe(p);
	reading(p, "strip-F");			/* its triggers end what was owed */
	helper_poll(p, 1, "verdict-late");	/* E's verdict: dropped */
	helper_owe(p);
	helper_poll(p, 1, "verdict-good-F");
	/* strip H: accepted; the button is pressed for the next strip before
	 * the verdict is acted on: the driver refuses it (no light request may
	 * delay that trigger). */
	helper_prompt(p);
	reading(p, "strip-H");
	helper_owe(p);
#ifndef CQ_V4333
	if (sig) {
		i1proimp *m = (i1proimp *)p->m;
		step("press-next");
		i1pro2_cq_lights_reading(p, 1);	/* the next read_strip began */
		m->switch_count++;				/* the switch thread saw a press */
		helper_poll(p, 1, "verdict-after-press");
		i1pro2_cq_lights_reading(p, 0);
	}
#endif
	/* a patch, read by hand and kept */
	helper_prompt(p);
	reading(p, "patch-1");
	helper_say(p, 1, "helper-green");
	/* a calibration asked for between strips */
	helper_prompt(p);
	calibrate(p);
	helper_prompt(p);
	reading(p, "strip-G");
	helper_say(p, 0, "helper-red");
	step("eeprom");
	if (i1pro_readEEProm(p, ee, 0x0c14, 64) != I1PRO_OK)
		printf("%s EEPROM-FAILED\n", scn);
	close_it(p);
}

int main(void) {
	/* The Beta option off: the helper never calls begin(). */
	life("off_i1pro2", instI1Pro2, 0, 0, 0);
	life("off_i1pro", instI1Pro, 0, 0, 0);
	/* On, both choices off: ChromIQ 4.3.33 with the option on. */
	life("on_ready_off", instI1Pro2, 1, 0, 0);
	/* The original i1Pro (rev A-D), option on: nothing, in every combination. */
	life("revad_ready_off", instI1Pro, 1, 0, 0);
#ifndef CQ_V4333
	life("revad_signals_off", instI1Pro, 1, 1, 0);
	life("revad_ready_lefton", instI1Pro, 1, 0, 1);
	life("revad_signals_lefton", instI1Pro, 1, 1, 1);
	/* The three new combinations on an i1Pro 2. */
	life("on_signals_off", instI1Pro2, 1, 1, 0);
	life("on_ready_lefton", instI1Pro2, 1, 0, 1);
	life("on_signals_lefton", instI1Pro2, 1, 1, 1);
	/* Other firmware: the recordings were made on 634; the programs go to
	 * any i1Pro 2, as 4.3.33's do (no firmware condition, like Argyll's). */
	{
		static const int fws[] = { 600, 635, 700 };
		static char names[3][2][32];
		int k;
		for (k = 0; k < 3; k++) {
			fwrev = fws[k];
			snprintf(names[k][0], 32, "fw%d_signals_off", fws[k]);
			snprintf(names[k][1], 32, "fw%d_ready_off", fws[k]);
			life(names[k][0], instI1Pro2, 1, 1, 0);
			life(names[k][1], instI1Pro2, 1, 0, 0);
		}
		fwrev = 634;
	}
	/* 4.3.36: every stored combination, through the helper's own mapping
	 * (cq_beta_pause.h): an i1Pro 2 is given both choices off, so each life
	 * must be 4.3.33's (the fixture's on_ready_off). */
	{
		static char pnames[4][32];
		int c, s2, l2;
		for (c = 0; c < 4; c++) {
			snprintf(pnames[c], 32, "v4336_%s_%s", c & 1 ? "signals" : "ready",
			         c & 2 ? "lefton" : "off");
			cq_lights_choices_for(2, c & 1, (c >> 1) & 1, &s2, &l2);
			life(pnames[c], instI1Pro2, 1, s2, l2);
		}
	}
#endif
	printf("ALL DONE\n");
	return 0;
}
