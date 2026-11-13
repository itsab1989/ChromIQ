/* i1pro3_lights_test: the i1Pro 3 indicator lights (Preferences > Beta,
 * 2026-11-13) on a FAKE USB layer, through the REAL vendored driver code.
 *
 * As i1pro2_lights_test.c: an i1pro3 object is built by hand with a fake icoms
 * that records every request, and the driver's own i1pro3_do_measure (the
 * function every calibration and reading of this driver passes through),
 * i1pro3_readEEProm and del_i1pro3imp are run, with the light hooks called
 * where i1pro3.c calls them. tests/test_i1pro3_lights_driver.py reads the
 * trace. Compiled with CQ_UPSTREAM against Argyll's own unpatched
 * i1pro3_imp.c / i1pro3.c (target i1pro3_lights_test_upstream) it runs the
 * option-off sessions without the hooks, for a byte-for-byte comparison.
 * Nothing here touches real hardware.
 *
 * Trace lines as in i1pro2_lights_test.c; BEGIN, NOTE seq=<1-4>.
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

/* The i1Pro 2's entry points, for the cross-instrument check. */
void i1pro2_cq_lights_ready(void *pp);
void i1pro2_cq_lights_trigger(void *pp);
void i1pro2_cq_lights_eeprom(void *pp);

static const char *scn = "?";
static int fail_29_at = 0, n_29 = 0, short_wr_at = 0, n_wr02 = 0;
static volatile int hold_trigger = 0;
static volatile int trig_sent = 0;	/* a measure request (0x22/0x27) went out */

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
		if (fail_29_at && n_29 == fail_29_at)
			return ICOM_USBW;
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
	if (ep == 0x02) {
		n_wr02++;
		if (short_wr_at && n_wr02 == short_wr_at)
			*bwritten = 0;
	}
	return ICOM_OK;
}

static int fake_read(icoms *p, usb_cancelt *c, int ep, unsigned char *buf,
                     int bsize, int *bread, double tout) {
	(void)p; (void)tout;
	memset(buf, 0, bsize);
	/* As usbio does for a real read: signal that the read has started, which
	 * releases the trigger thread (USE_RD_SYNC); and, as the instrument does,
	 * deliver the readings only after the measure request has arrived. */
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
	while (hold_trigger)
		msec_sleep(1);
	if (c != NULL) {			/* wait until the read has started */
		amutex_lock(c->condx);
		amutex_unlock(c->condx);
	}
	return ICOM_OK;
}

#ifndef CQ_UPSTREAM
static void note(int seq, int err) {
	printf("%s NOTE seq=%d err=0x%x\n", scn, seq, err);
	fflush(stdout);
}
#endif

static i1pro3 *make(devType dtype, int caps, int inited) {
	i1pro3 *p = (i1pro3 *)calloc(1, sizeof(i1pro3));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1pro3imp *m;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	p->log = new_a1log_d(NULL);
	p->dtype = dtype;
	p->icom = ic;
	p->gotcoms = 1;
	p->inited = inited;
	if (add_i1pro3imp(p) != I1PRO3_OK) {
		fprintf(stderr, "add_i1pro3imp failed\n");
		exit(2);
	}
	m = (i1pro3imp *)p->m;
	m->capabilities = caps;
	usb_init_cancel(&m->rd_sync);
	usb_init_cancel(&m->rd_sync2);
	m->intclkp = 15.3e-6;
	m->min_int_time = 0.0025;
	m->nsen1 = 134;
	m->nsen2 = 282;
	m->nraw = 128;
	m->msec = msec_time();
	n_29 = n_wr02 = 0;
	return p;
}

static void step(const char *what) {
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
}

/* One measurement through the driver's own core function: an emissive dark
 * reading, the simplest thing i1pro3_do_measure does (no LED currents). */
static int measure(i1pro3 *p) {
	double **raw = NULL;
	int nummeas = 1;
	double inttime = 0.01;
	i1pro3_code ev;
	step("measure");
	ev = i1pro3_do_measure(p, i1p3mm_em, &raw, &nummeas, &inttime, NULL, NULL);
	if (raw != NULL)
		free_dmatrix(raw, 0, nummeas-1, -1, ((i1pro3imp *)p->m)->nraw-1);
	if (ev != I1PRO3_OK)
		printf("%s MEASURE-RETURNED 0x%x\n", scn, ev);
	return ev;
}

static void after_read(i1pro3 *p, int rv) {
	step("after-read");
#ifndef CQ_UPSTREAM
	i1pro3_cq_lights_after_read(p, rv);
#else
	(void)p; (void)rv;
#endif
}

static void after_cal(i1pro3 *p, int rv) {
	step("after-cal");
#ifndef CQ_UPSTREAM
	i1pro3_cq_lights_after_cal(p, rv);
#else
	(void)p; (void)rv;
#endif
}

#ifndef CQ_UPSTREAM
static void begin(i1pro3 *p) {
	step("begin");
	printf("%s BEGIN %d\n", scn, i1pro3_cq_lights_begin(p));
}
#endif

static void eeprom(i1pro3 *p) {
	unsigned char buf[64];
	step("eeprom");
	if (i1pro3_readEEProm(p, buf, 0x18, 64) != I1PRO3_OK)
		printf("%s EEPROM-FAILED\n", scn);
}

static void close_it(i1pro3 *p) {
	icoms *ic = p->icom;
	a1log *lg = p->log;
	step("close");
	del_i1pro3imp(p);
	free(p);
	free(ic);
	del_a1log(lg);
	printf("%s END\n", scn);
	fflush(stdout);
}

/* A session: (begin), a calibration (two measurements, then success), a
 * good reading, a reading the instrument could not take, an aborted one, an
 * EEPROM read, the close. */
static void session(const char *name, devType dtype, int caps, int inited,
                    int asked) {
	i1pro3 *p;
	scn = name;
	p = make(dtype, caps, inited);
#ifndef CQ_UPSTREAM
	if (asked)
		begin(p);
#else
	(void)asked;
#endif
	measure(p);
	measure(p);
	after_cal(p, I1PRO3_OK);
	after_read(p, measure(p));			/* GOOD */
	measure(p);
	after_read(p, I1PRO3_RD_SHORTMEAS);	/* BAD */
	measure(p);
	after_read(p, I1PRO3_USER_ABORT);	/* nothing */
	after_cal(p, I1PRO3_RD_WHITEREADINCONS);	/* failed calibration: nothing */
	eeprom(p);
	close_it(p);
}

int main(void) {
	i1pro3 *p;

	/* Option off: the helper never calls begin(). */
	session("off_i1pro3", instI1Pro3, I1PRO3_CAP_IND_LED, 1, 0);
#ifdef CQ_UPSTREAM
	(void)p;
	printf("ALL DONE\n");
	return 0;
#else
	i1pro3_cq_lights_note = note;

	session("on_i1pro3", instI1Pro3, I1PRO3_CAP_IND_LED, 1, 1);
	session("on_no_led_bit", instI1Pro3, 0, 1, 1);
	session("on_not_inited", instI1Pro3, I1PRO3_CAP_IND_LED, 0, 1);

	/* The i1Pro 2's entry points asked of an i1Pro 3, and the i1Pro 3's
	 * asked of an i1Pro 2-shaped object: dtype is checked first. */
	scn = "cross_dtype";
	p = make(instI1Pro3, I1PRO3_CAP_IND_LED, 1);
	((i1pro3imp *)p->m)->cq_lights = 2;
	step("i1pro2-entries");
	i1pro2_cq_lights_ready(p);
	i1pro2_cq_lights_trigger(p);
	i1pro2_cq_lights_eeprom(p);
	((i1pro3imp *)p->m)->cq_lights = 0;
	close_it(p);

	/* The OFF before the second measurement fails: noted once, the
	 * measurement still runs, nothing more is ever sent. */
	fail_29_at = 2;
	session("fail_off", instI1Pro3, I1PRO3_CAP_IND_LED, 1, 1);
	fail_29_at = 0;

	/* The bytes of the first pattern do not arrive (a short bulk write):
	 * noted once, nothing more is sent. */
	short_wr_at = 1;
	session("fail_write", instI1Pro3, I1PRO3_CAP_IND_LED, 1, 1);
	short_wr_at = 0;

	/* end() while lit (lights_off_exit, end of stdin, atexit). */
	scn = "end_cmd";
	p = make(instI1Pro3, I1PRO3_CAP_IND_LED, 1);
	begin(p);
	after_cal(p, I1PRO3_OK);
	step("end");
	i1pro3_cq_lights_end(p);
	after_read(p, measure(p));
	close_it(p);

	/* Closed while a pattern plays: Argyll's off at the close. And an i1Pro 3
	 * Plus (the driver's aperture flag, devtype 0x20) behaves the same. */
	scn = "close_lit_plus";
	p = make(instI1Pro3, I1PRO3_CAP_IND_LED, 1);
	((i1pro3imp *)p->m)->aperture = 1;
	begin(p);
	after_cal(p, I1PRO3_OK);
	close_it(p);

	/* A trigger thread still waiting to send its request: no pattern, and
	 * the close sends nothing until it is gone. */
	scn = "trigger_pending";
	p = make(instI1Pro3, I1PRO3_CAP_IND_LED, 1);
	begin(p);
	{
		i1pro3imp *m = (i1pro3imp *)p->m;
		step("trigger-held");
		hold_trigger = 1;
		i1pro3_trigger_measure(p, 0, 0, 1, 100, 0, 0);
		after_cal(p, I1PRO3_OK);		/* held back */
		step("trigger-released");
		hold_trigger = 0;
		amutex_unlock(m->rd_sync.condx);
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	close_it(p);

	printf("ALL DONE\n");
	return 0;
#endif
}
