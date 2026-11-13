/* i1pro2_lights_test: the i1Pro 2 indicator lights (Preferences > Beta,
 * 2026-11-13) on a FAKE USB layer, through the REAL vendored driver code.
 *
 * Nobody on the project owns an i1Pro 2, so this is how the patch in
 * native/instlib/i1pro_imp.c is proved: an i1pro object is built by hand with
 * a fake icoms whose usb_control / usb_write / usb_read record every request
 * the driver makes, and the driver's own functions are called the way the
 * instrument's life calls them (begin, trigger, EEPROM read, ready, close).
 * Every request is printed as one line; tests/test_i1pro2_lights_driver.py
 * reads the trace and checks it. Nothing here touches real hardware.
 *
 * Trace lines:
 *   <scenario> CTL <req> <hex payload> tout=<s>   control OUT/IN request
 *   <scenario> WR <ep> <hex data> tout=<s>        bulk/interrupt write
 *   <scenario> RD <ep> <n>                         bulk/interrupt read
 *   <scenario> NOTE white=<0|1> err=<icom err>     the driver's failure note
 *   <scenario> BEGIN <0|1>                         i1pro2_cq_lights_begin()
 *   <scenario> STEP <name>                         what the scenario does next
 *   <scenario> END                                 the scenario finished
 *
 * Built only on request: cmake --build <build> --target i1pro2_lights_test.
 * The same file, compiled with CQ_UPSTREAM against Argyll's own unpatched
 * i1pro_imp.c / i1pro.c (target i1pro2_lights_test_upstream), runs the
 * option-off session without the hooks, so the two wire traces can be
 * compared byte for byte.
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

static const char *scn = "?";

/* Fault injection: fail the Nth 0xD6 control (1-based), or short-write the
 * Nth write on endpoint 0x03. 0 = never. */
static int fail_d6_at = 0, short_wr_at = 0;
static int n_d6 = 0, n_wr03 = 0;

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
	if (request == 0xD6) {
		n_d6++;
		if (fail_d6_at && n_d6 == fail_d6_at)
			return ICOM_USBW;			/* a USB write failure */
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
	if (ep == 0x03) {
		n_wr03++;
		if (short_wr_at && n_wr03 == short_wr_at)
			*bwritten = wsize - 1;
	}
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

/* Non-zero: the trigger thread is held in its wait for the read to start
 * (scenario 12), as it is on a real instrument until the read is submitted. */
static volatile int hold_trigger = 0;

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p; (void)c;
	while (hold_trigger)
		msec_sleep(1);
	return ICOM_OK;
}

#ifndef CQ_UPSTREAM
static void note(int seq, int err) {
	printf("%s NOTE seq=%d err=0x%x\n", scn, seq, err);
	fflush(stdout);
}
#endif

/* An i1pro object as new_i1pro() + i1pro_imp_init() would leave it, with
 * only what the light hooks and the Rev E trigger path read. */
static i1pro *make(devType dtype, int caps2, int inited) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	p->log = new_a1log_d(NULL);
	p->dtype = dtype;
	p->icom = ic;
	p->gotcoms = 1;
	p->inited = inited;
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
	n_d6 = n_wr03 = 0;
	return p;
}

static void step(const char *what) {
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
}

/* One measurement trigger, the way every calibration and reading of this
 * driver is triggered; waits for the trigger thread so the trace is ordered. */
static void trigger(i1pro *p) {
	i1proimp *m = (i1proimp *)p->m;
	double inttime = 0.02;
	step("trigger");
	if (i1pro_trigger_one_measure(p, 1, &inttime, 0, i1p_cal) != I1PRO_OK)
		printf("%s TRIGGER-FAILED\n", scn);
	/* The measurement read starting, as usbio does for a real read: it is
	 * what lets the trigger thread send its 0xD4 (USE_RD_SYNC). */
	amutex_unlock(m->rd_sync.condx);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
}

static void eeprom(i1pro *p) {
	unsigned char buf[64];
	step("eeprom");
	if (i1pro_readEEProm(p, buf, 0x0c14, 64) != I1PRO_OK)
		printf("%s EEPROM-FAILED\n", scn);
}

static void ready(i1pro *p) {
	step("ready");
#ifndef CQ_UPSTREAM
	i1pro2_cq_lights_ready(p);	/* what i1pro.c does after a measure/calibrate */
#else
	(void)p;
#endif
}

#ifndef CQ_UPSTREAM
static void begin(i1pro *p) {
	step("begin");
	printf("%s BEGIN %d\n", scn, i1pro2_cq_lights_begin(p));
}
#endif

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

/* A whole session: begin (if asked), calibrate, wait, measure, wait,
 * an EEPROM read, wait, close. */
static void session(const char *name, devType dtype, int caps2, int inited,
                    int asked) {
	i1pro *p;
	scn = name;
	p = make(dtype, caps2, inited);
#ifndef CQ_UPSTREAM
	if (asked)
		begin(p);
#else
	(void)asked;
#endif
	trigger(p);			/* calibration */
	trigger(p);			/* its second reading: still off, nothing sent */
	ready(p);			/* calibration returned */
	trigger(p);			/* the strip */
	ready(p);			/* the strip returned */
	eeprom(p);
	ready(p);
	close_it(p);
}

int main(void) {
	i1pro *p;

	/* 1. Option off: the helper never calls begin(). Upstream runs only this
	 *    (and the original i1Pro and i1Monitor sessions, option off). */
	session("off_i1pro2", instI1Pro2, I1PRO_CAP2_IND_LED, 1, 0);
	session("off_i1pro", instI1Pro, I1PRO_CAP2_IND_LED, 1, 0);
	session("off_i1monitor", instI1Monitor, I1PRO_CAP2_IND_LED, 1, 0);
#ifdef CQ_UPSTREAM
	(void)p;
	printf("ALL DONE\n");
	return 0;
#else
	i1pro2_cq_lights_note = note;
	/* 2. Option on, a real i1Pro 2. */
	session("on_i1pro2", instI1Pro2, I1PRO_CAP2_IND_LED, 1, 1);
	/* 3. Option on, an original i1Pro (Rev A-D) or an i1Pro 2 in legacy mode. */
	session("on_i1pro", instI1Pro, I1PRO_CAP2_IND_LED, 1, 1);
	/* 4. Option on, an i1Monitor. */
	session("on_i1monitor", instI1Monitor, I1PRO_CAP2_IND_LED, 1, 1);
	/* 5. Option on, an i1Pro 2 whose EEPROM does not report the LEDs. */
	session("on_no_led_bit", instI1Pro2, 0, 1, 1);
	/* 6. Option on, but begin() before the instrument is inited. */
	session("on_not_inited", instI1Pro2, I1PRO_CAP2_IND_LED, 0, 1);

	/* 7. The OFF before a trigger fails at its 0xD6: noted once, the trigger
	 *    is still sent, nothing more is ever sent (not even at the close). */
	fail_d6_at = 2;
	session("fail_off", instI1Pro2, I1PRO_CAP2_IND_LED, 1, 1);
	fail_d6_at = 0;

	/* 8. The very first WHITE fails at its bulk write (short write). */
	short_wr_at = 1;
	session("fail_white", instI1Pro2, I1PRO_CAP2_IND_LED, 1, 1);
	short_wr_at = 0;

	/* 9. end() while lit (lights_off_exit, end of stdin, atexit), then the
	 *    session goes on: nothing more is sent. */
	scn = "end_cmd";
	p = make(instI1Pro2, I1PRO_CAP2_IND_LED, 1);
	begin(p);
	step("end");
	i1pro2_cq_lights_end(p);
	ready(p);
	trigger(p);
	ready(p);
	close_it(p);

	/* 10. begin() twice does not send WHITE twice. */
	scn = "begin_twice";
	p = make(instI1Pro2, I1PRO_CAP2_IND_LED, 1);
	begin(p);
	begin(p);
	close_it(p);

	/* 11. Closed within 2.5 s of an OFF_SLOW (still playing): OFF_NOW at
	 *     the close, so nothing is left running for the next open. */
	scn = "close_after_trigger";
	p = make(instI1Pro2, I1PRO_CAP2_IND_LED, 1);
	begin(p);
	trigger(p);
	close_it(p);

	/* 12. A trigger thread still waiting to send its 0xD4 (its read never
	 *     started): WHITE is held back, so no light request can meet it. */
	scn = "trigger_pending";
	p = make(instI1Pro2, I1PRO_CAP2_IND_LED, 1);
	begin(p);
	{
		i1proimp *m = (i1proimp *)p->m;
		double inttime = 0.02;
		step("trigger-without-read");
		hold_trigger = 1;
		i1pro_trigger_one_measure(p, 1, &inttime, 0, i1p_cal);
		ready(p);			/* the read never started: no WHITE */
		step("read-starts");
		hold_trigger = 0;
		amutex_unlock(m->rd_sync.condx);
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	close_it(p);

	/* 13. The light hooks asked of an instrument that is not an i1Pro 2
	 *     with cq_lights forced non-zero: dtype is checked first. */
	scn = "forced_state_i1pro";
	p = make(instI1Pro, I1PRO_CAP2_IND_LED, 1);
	((i1proimp *)p->m)->cq_lights = 2;
	ready(p);
	trigger(p);
	eeprom(p);
	step("end");
	i1pro2_cq_lights_end(p);
	((i1proimp *)p->m)->cq_lights = 0;
	close_it(p);

	printf("ALL DONE\n");
	return 0;
#endif
}
