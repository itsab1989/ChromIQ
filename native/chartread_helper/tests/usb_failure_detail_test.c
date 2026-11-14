/* usb_failure_detail_test: the helper's read-only USB watch (4.3.36,
 * chromiq_usbwatch.c) with failures INJECTED on a FAKE USB layer, through
 * the REAL vendored i1Pro driver. Nothing here touches real hardware.
 *
 * Each scenario makes one reading the way the driver makes it (the trigger
 * thread's 0xD4 / 0xC0, the 0x82 measurement read until the short read),
 * with one transfer failing, and prints what the helper's error event would
 * carry: "<scn> JSON <fields>". tests/test_usb_failure_detail.py reads it.
 * The i1Pro 3's transfer names are checked on the watch alone.
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
#include "usbio.h"
#include "inst.h"
#include "i1pro.h"
#include "i1pro_imp.h"
#include "chromiq_usbwatch.h"

static const char *scn = "?";
static volatile int trig_sent = 0;
static int readings_left = 0;
static const int reading_bytes = 268;

/* What fails, and how. 0 = nothing. */
static int fail_ctl_req = 0, fail_ctl_se = 0;
static int fail_rd_ep = 0, fail_rd_se = 0, fail_rd_on = 1;	/* the Nth read of that ep */
static int rd_count = 0;
static int fail_wr_ep = 0, fail_wr_se = 0;

static int fake_control(icoms *p, int requesttype, int request, int value,
                        int index, unsigned char *rwbuf, int rwsize,
                        int *xferred, double tout) {
	(void)p; (void)value; (void)index; (void)tout;
	if (xferred != NULL)
		*xferred = rwsize;
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) != IUSB_ENDPOINT_OUT && rwbuf != NULL)
		memset(rwbuf, 0, rwsize);
	if ((request & 0xff) == 0xD4 || (request & 0xff) == 0xC0)
		trig_sent = 1;
	if (fail_ctl_req != 0 && (request & 0xff) == fail_ctl_req) {
		if (xferred != NULL)
			*xferred = 0;
		return fail_ctl_se;
	}
	return ICOM_OK;
}

static int fake_write(icoms *p, usb_cancelt *c, int ep, unsigned char *wbuf,
                      int wsize, int *bwritten, double tout) {
	(void)p; (void)c; (void)wbuf; (void)tout;
	*bwritten = wsize;
	if (fail_wr_ep != 0 && (ep & 0xff) == fail_wr_ep) {
		*bwritten = 0;
		return fail_wr_se;
	}
	return ICOM_OK;
}

static void started(usb_cancelt *c) {
	if (c != NULL) {
		amutex_lock(c->cmtx);
		if (c->state == 0) {
			c->state = 1;
			amutex_unlock(c->condx);
		}
		amutex_unlock(c->cmtx);
	}
}

static int fake_read(icoms *p, usb_cancelt *c, int ep, unsigned char *buf,
                     int bsize, int *bread, double tout) {
	int i, n;
	(void)p; (void)tout;
	started(c);
	*bread = 0;
	if (fail_rd_ep != 0 && (ep & 0xff) == fail_rd_ep && ++rd_count == fail_rd_on) {
		for (i = 0; (ep & 0xff) == 0x82 && !trig_sent && i < 5000; i++)
			msec_sleep(1);
		return fail_rd_se;
	}
	if ((ep & 0xff) == 0x82) {
		for (i = 0; !trig_sent && i < 5000; i++)
			msec_sleep(1);
		n = bsize / reading_bytes;
		if (n > readings_left)
			n = readings_left;
		readings_left -= n;
		memset(buf, 0, bsize);
		for (i = 0; i < n * reading_bytes; i += 2)
			buf[i] = 0x10;
		*bread = n * reading_bytes;
		return *bread < bsize ? ICOM_SHORT : ICOM_OK;
	}
	memset(buf, 0, bsize);
	*bread = bsize;
	return ICOM_OK;
}

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p;
	amutex_lock(c->condx);
	amutex_unlock(c->condx);
	return ICOM_OK;
}

static int fake_cancel_io(icoms *p, usb_cancelt *c) {
	(void)p; (void)c;
	return ICOM_OK;
}

static i1pro *make(devType dtype) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	ic->usb_cancel_io = fake_cancel_io;
	cq_usbwatch_install(ic, CQ_UW_I1PRO);	/* as the helper does */
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
	m->capabilities2 = 0x10;	/* I1PRO_CAP2_IND_LED */
	usb_init_cancel(&m->rd_sync);
	m->mmode = 0;
	m->ms[0].reflective = 1;
	m->ms[0].scan = 1;
	m->ms[0].lamptime = 0.2;
	m->intclkp2 = 36e-6;
	m->subclkdiv2 = 136;
	m->min_int_time = 136 * 36e-6;
	m->nsen = 134;
	m->nraw = 128;
	m->msec = msec_time();
	m->fwrev = dtype == instI1Pro2 ? 634 : 202;
	return p;
}

static void done_with(i1pro *p) {
	free(p->icom);
	p->icom = NULL;
}

/* One lit strip scan, as i1pro_imp_measure makes it. */
static void scan(i1pro *p, int nread) {
	i1proimp *m = (i1proimp *)p->m;
	double inttime = m->min_int_time;
	int nmeas = 0, maxn = 4000;
	unsigned int bsize = m->nsen * 2 * maxn;
	unsigned char *buf = (unsigned char *)malloc(bsize);
	i1pro_code ev;
	trig_sent = 0;
	readings_left = nread;
	ev = i1pro_read_patches_1(p, 10, maxn, &inttime, 0, &nmeas, buf, bsize);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	printf("%s RESULT ev=0x%x\n", scn, ev);
	free(buf);
}

static void report(void) {
	char j[2048];
	cq_usbwatch_json(j, sizeof(j));
	printf("%s JSON %s\n", scn, j);
	fflush(stdout);
}

static void reset_faults(void) {
	fail_ctl_req = fail_ctl_se = 0;
	fail_rd_ep = fail_rd_se = 0;
	fail_rd_on = 1;
	rd_count = 0;
	fail_wr_ep = fail_wr_se = 0;
}

/* The i1Pro 3's names, on the watch alone: a fake icoms that fails what it
 * is told to, called through the wrapped entry points. */
static int f3_se = 0;
static int f3_control(icoms *p, int rt, int rq, int v, int ix, unsigned char *b,
                      int n, int *x, double t) {
	(void)p; (void)rt; (void)rq; (void)v; (void)ix; (void)b; (void)t;
	if (x != NULL)
		*x = 0;
	(void)n;
	return f3_se;
}
static int f3_rw(icoms *p, usb_cancelt *c, int ep, unsigned char *b, int n,
                 int *d, double t) {
	(void)p; (void)c; (void)ep; (void)b; (void)n; (void)t;
	*d = 0;
	return f3_se;
}

int main(void) {
	i1pro *p;

	/* The measure trigger fails; the read then times out. */
	scn = "trigger_fails";
	reset_faults();
	fail_ctl_req = 0xD4; fail_ctl_se = ICOM_USBW;
	fail_rd_ep = 0x82; fail_rd_se = ICOM_TO;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	scan(p, 120);
	report();
	done_with(p);

	/* The measurement data read fails (a timeout, nothing read). */
	scn = "read_fails";
	reset_faults();
	fail_rd_ep = 0x82; fail_rd_se = ICOM_TO;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	scan(p, 120);
	report();
	done_with(p);

	/* The first reading of the strip works, the second's read fails: the
	 * failure names the second trigger. */
	scn = "second_read_fails";
	reset_faults();
	fail_rd_ep = 0x82; fail_rd_se = ICOM_USBR; fail_rd_on = 2;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	scan(p, 120);
	scan(p, 120);
	report();
	done_with(p);

	/* The original i1Pro's trigger is 0xC0. */
	scn = "i1pro_trigger_fails";
	reset_faults();
	fail_ctl_req = 0xC0; fail_ctl_se = ICOM_TO;
	fail_rd_ep = 0x82; fail_rd_se = ICOM_TO;
	p = make(instI1Pro);
	cq_usbwatch_begin();
	scan(p, 120);
	report();
	done_with(p);

	/* The button read: an error is one, a timeout is how its wait ends. */
	scn = "button_fails";
	reset_faults();
	fail_rd_ep = 0x84; fail_rd_se = ICOM_USBR;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	printf("%s RESULT ev=0x%x\n", scn, i1pro_waitfor_switch(p, 0.1));
	report();
	done_with(p);

	scn = "button_timeout_is_routine";
	reset_faults();
	fail_rd_ep = 0x84; fail_rd_se = ICOM_TO;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	printf("%s RESULT ev=0x%x\n", scn, i1pro_waitfor_switch(p, 0.1));
	report();
	done_with(p);

	/* A light program's bulk write times out (the lights then stop; the
	 * reading is not affected). */
	scn = "light_fails";
	reset_faults();
	fail_wr_ep = 0x03; fail_wr_se = ICOM_TO;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	i1pro2_cq_lights_options(p, 0, 0);
	printf("%s BEGIN %d\n", scn, i1pro2_cq_lights_begin(p));
	report();
	done_with(p);

	/* Nothing fails: the short read that ends a scan is not a failure. */
	scn = "nothing_fails";
	reset_faults();
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	scan(p, 120);
	report();
	done_with(p);

	/* The last light program, and how long before the first trigger. */
	scn = "light_timing";
	reset_faults();
	fail_rd_ep = 0x82; fail_rd_se = ICOM_TO;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	cq_usbwatch_light("off_slow");
	msec_sleep(30);
	scan(p, 120);
	report();
	done_with(p);

	/* An earlier reading's failure is forgotten when the next begins. */
	scn = "begin_forgets";
	reset_faults();
	fail_rd_ep = 0x82; fail_rd_se = ICOM_TO;
	p = make(instI1Pro2);
	cq_usbwatch_begin();
	scan(p, 120);
	reset_faults();
	cq_usbwatch_begin();
	scan(p, 120);
	report();
	done_with(p);

	/* The i1Pro 3's transfers, by name. */
	{
		static const struct { const char *name; int kind, code, se; } t[] = {
			{ "i1pro3_trigger", CQ_UW_CONTROL, 0x22, ICOM_TO },
			{ "i1pro3_trigger_emis", CQ_UW_CONTROL, 0x27, ICOM_USBW },
			{ "i1pro3_read", CQ_UW_READ, 0x81, ICOM_TO },
			{ "i1pro3_ruler", CQ_UW_READ, 0x84, ICOM_USBR },
			{ "i1pro3_button", CQ_UW_READ, 0x83, ICOM_USBR },
			{ "i1pro3_button_timeout", CQ_UW_READ, 0x83, ICOM_TO },
			{ "i1pro3_light_ctl", CQ_UW_CONTROL, 0x29, ICOM_USBW },
			{ "i1pro3_light", CQ_UW_WRITE, 0x02, ICOM_TO },
			{ "i1pro3_other", CQ_UW_CONTROL, 0x10, ICOM_USBR },
		};
		int k, d;
		unsigned char b[8];
		for (k = 0; k < (int)(sizeof(t) / sizeof(t[0])); k++) {
			icoms *ic = (icoms *)calloc(1, sizeof(icoms));
			ic->usb_control = f3_control;
			ic->usb_read = f3_rw;
			ic->usb_write = f3_rw;
			cq_usbwatch_install(ic, CQ_UW_I1PRO3);
			cq_usbwatch_begin();
			f3_se = t[k].se;
			scn = t[k].name;
			if (t[k].kind == CQ_UW_CONTROL)
				ic->usb_control(ic, IUSB_ENDPOINT_OUT | IUSB_REQ_TYPE_VENDOR
				                | IUSB_REQ_RECIP_DEVICE, t[k].code, 0, 0, b, 8,
				                &d, 2.0);
			else if (t[k].kind == CQ_UW_READ)
				ic->usb_read(ic, NULL, t[k].code, b, 8, &d, 2.0);
			else
				ic->usb_write(ic, NULL, t[k].code, b, 8, &d, 2.0);
			report();
			free(ic);
		}
	}

	/* Forgotten: nothing to say, and the originals are back. */
	{
		icoms *ic = (icoms *)calloc(1, sizeof(icoms));
		ic->usb_control = f3_control;
		ic->usb_read = f3_rw;
		ic->usb_write = f3_rw;
		cq_usbwatch_install(ic, CQ_UW_I1PRO);
		cq_usbwatch_forget();
		scn = "forgotten";
		report();
		printf("%s RESTORED %d\n", scn, ic->usb_control == f3_control
		       && ic->usb_read == f3_rw && ic->usb_write == f3_rw);
		free(ic);
	}

	printf("ALL DONE\n");
	return 0;
}
