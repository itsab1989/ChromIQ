/* i1pro_ruler_scan_test: a hand-held STRIP SCAN of the i1Pro 2 and of the
 * original i1Pro through the REAL vendored driver (i1pro_read_patches_1:
 * the trigger, then the measurement read until the instrument's short read)
 * on a FAKE USB layer. Nothing here touches real hardware.
 *
 * Every request and every read on the instrument's endpoints is printed as
 * one line. Readings arrive on 0x82 in the sizes the driver asks for and end
 * with a short read after a fixed number of readings. The ruler channel 0x85
 * (the ruler check Beta, 2026-11-14) is printed separately, because its
 * reads run on their own thread.
 *
 * Compiled with CQ_BASE against the driver of the base branch
 * (feat/lights-i1pro3-signals 6de402163), which has no ruler code, the same
 * scans are what ChromIQ put on the wire before the Beta:
 * tests/data/i1pro_ruler_base_trace.txt (scripts/make_ruler_base_fixtures.py).
 * With the option off this tree must print exactly that.
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
#ifdef CQ_WATCHED
#include "chromiq_usbwatch.h"	/* 4.3.36: the helper's read-only USB watch */
#endif

static const char *scn = "?";
static volatile int trig_sent = 0;	/* the D4 / C0 trigger went out */
static int readings_left = 0;		/* readings the fake still has */
static int reading_bytes = 268;

#ifndef CQ_BASE
#include "cq_ruler.h"
/* ---- the ruler channel 0x85 (the ruler check Beta) ----------------------
 * What the fake i1Pro 2 streams: modelled on the two USB recordings (one byte
 * per integration clock, codes 0..3 in quadrature, 4096-byte reads, the last
 * one short, samples = readings x clocks - 5). Modes:
 *   clean    the stream as recorded, moving TRAVEL steps
 *   none     no ruler under the instrument: the code never changes
 *   garbled  clean, plus impossible jumps
 *   short    only half the samples, then the short read (dropped data)
 *   late     the whole stream arrives 400 ms after the scan ended
 *   error    every read fails with a USB error
 *   zero     the stream ends at once with no data
 *   noend    full reads every 50 ms and never a short read (only a cancel,
 *            and only one that lands DURING a read, as the real layers do)
 */
static int pace = 0;			/* 0x82 answers at the real reading rate */
static const char *ruler_mode = "clean";
static int ruler_travel = 300;
static volatile int scan_over = 0;	/* the fake's 0x82 stream has ended */
static volatile long r_total = 0, r_pos = 0;
static volatile int r_reads = 0, r_maxsize = 0, r_cancels = 0, r_in_read = 0;
static volatile int r_cancel_hit = 0;
static volatile int r_clearhalts = 0;	/* macOS-like: IOKit's clear-halt after an aborted read */
static int fail82 = 0;			/* the measurement read fails */

static unsigned char ruler_code(long i, long total) {
	static const unsigned char cyc[4] = { 0, 2, 3, 1 };	/* +1 in Argyll's table */
	long a = total / 10, b = total - total / 10, step;
	if (strcmp(ruler_mode, "none") == 0)
		return 3;
	if (i < a)
		step = 0;
	else if (i >= b)
		step = ruler_travel;
	else
		step = (i - a) * ruler_travel / (b - a);
	if (strcmp(ruler_mode, "garbled") == 0 && i == total / 2)
		return cyc[(4 - (step & 3) + 2) & 3];	/* an impossible jump */
	return cyc[(4 - (step & 3)) & 3];		/* moving the negative way */
}

static int ruler_read(unsigned char *buf, int bsize, int *bread, double tout) {
	int i, n;
	r_reads++;
	if (bsize > r_maxsize)
		r_maxsize = bsize;
	*bread = 0;
	if (strcmp(ruler_mode, "error") == 0) {
		msec_sleep(2);
		return ICOM_USBR;
	}
	if (strcmp(ruler_mode, "zero") == 0)
		return ICOM_SHORT;
	if (strcmp(ruler_mode, "gone") == 0) {	/* the device was unplugged */
		msec_sleep(2);
		return ICOM_SYS;
	}
	if (strcmp(ruler_mode, "stall") == 0 || strcmp(ruler_mode, "stallnc") == 0) {
		/* nothing ever arrives; the real layers return only on the
		 * timeout or a cancel that lands during the read. stallnc: a
		 * cancel never works. On macOS both endings are an abort, which
		 * IOKit follows with a clear-halt request (r_clearhalts). */
		unsigned int t0r = msec_time();
		int cancellable = strcmp(ruler_mode, "stall") == 0;
		r_in_read = 1;
		while ((double)(msec_time() - t0r) < tout * 1000.0) {
			if (r_cancel_hit && cancellable)
				break;
			msec_sleep(1);
		}
		r_in_read = 0;
		r_clearhalts++;
		if (r_cancel_hit && cancellable) {
			r_cancel_hit = 0;
			return ICOM_CANC;
		}
		return ICOM_TO;
	}
	if (strcmp(ruler_mode, "huge") == 0) {	/* 3 MB fast, then the short read */
		if (r_pos >= 3L * 1024 * 1024) {
			*bread = 100;
			r_pos += 100;
			return ICOM_SHORT;
		}
		memset(buf, 1, bsize);
		*bread = bsize;
		r_pos += bsize;
		return ICOM_OK;
	}
	if (strcmp(ruler_mode, "late200") == 0) {	/* ends 200 ms after the scan */
		while (!scan_over)
			msec_sleep(2);
		msec_sleep(200);
		memset(buf, 3, 77);
		*bread = 77;
		return ICOM_SHORT;
	}
	if (strcmp(ruler_mode, "noend") == 0) {
		r_in_read = 1;
		for (i = 0; i < 50 && !r_cancel_hit; i++)
			msec_sleep(1);
		r_in_read = 0;
		if (r_cancel_hit) {
			r_cancel_hit = 0;
			r_clearhalts++;
			return ICOM_CANC;
		}
		memset(buf, 3, bsize);
		*bread = bsize;
		return ICOM_OK;
	}
	if (strcmp(ruler_mode, "late") == 0) {
		while (!scan_over)
			msec_sleep(2);
		msec_sleep(400);
	} else {
		while (!scan_over && r_pos + bsize > r_total / 3)
			msec_sleep(2);		/* the stream runs with the scan */
	}
	n = (int)((strcmp(ruler_mode, "short") == 0 ? r_total / 2 : r_total) - r_pos);
	if (n < 0)
		n = 0;
	if (n > bsize)
		n = bsize;
	for (i = 0; i < n; i++)
		buf[i] = ruler_code(r_pos + i, r_total);
	r_pos += n;
	*bread = n;
	return n < bsize ? ICOM_SHORT : ICOM_OK;
}
#endif

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
	if ((request & 0xff) == 0xD4 || (request & 0xff) == 0xC0)
		trig_sent = 1;
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

/* As the real layer does: a read with a sync token tells the waiting
 * trigger thread that it is pending. */
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
	(void)p;
	started(c);
	if ((ep & 0xff) == 0x82) {
		/* deterministic order: a reading is only ever answered after the
		 * trigger thread's request has been printed */
		for (i = 0; !trig_sent && i < 5000; i++)
			msec_sleep(1);
		n = bsize / reading_bytes;
		if (n > readings_left)
			n = readings_left;
		readings_left -= n;
#ifndef CQ_BASE
		if (fail82) {		/* the measurement read fails mid-scan */
			scan_over = 1;
			*bread = 0;
			printf("%s RD 82 %d -> FAIL tout=%.2f\n", scn, bsize, tout);
			fflush(stdout);
			return ICOM_USBR;
		}
		if (pace)
			msec_sleep((int)(n * 4.896 + 0.5));
		if (n * reading_bytes < bsize)
			scan_over = 1;
#endif
		memset(buf, 0, bsize);
		for (i = 0; i < n * reading_bytes; i += 2)
			buf[i] = 0x10;		/* a flat, unsaturated level */
		*bread = n * reading_bytes;
		printf("%s RD 82 %d -> %d tout=%.2f\n", scn, bsize, *bread, tout);
		fflush(stdout);
		return *bread < bsize ? ICOM_SHORT : ICOM_OK;
	}
#ifndef CQ_BASE
	if ((ep & 0xff) == 0x85)		/* the ruler: its own thread, not printed */
		return ruler_read(buf, bsize, bread, tout);
#endif
	printf("%s RD %02x %d tout=%.2f\n", scn, ep & 0xff, bsize, tout);
	fflush(stdout);
	memset(buf, 0, bsize);
	*bread = bsize;
	return ICOM_OK;
}

static int fake_wait_io(icoms *p, usb_cancelt *c) {
	(void)p;
	amutex_lock(c->condx);		/* as the real one: until the read started */
	amutex_unlock(c->condx);
	return ICOM_OK;
}

static int fake_cancel_io(icoms *p, usb_cancelt *c) {
	(void)p; (void)c;
#ifndef CQ_BASE
	r_cancels++;
	if (r_in_read)			/* as the real layers: only a pending read */
		r_cancel_hit = 1;
#else
	printf("%s CANCEL\n", scn);
	fflush(stdout);
#endif
	return ICOM_OK;
}

static i1pro *make(devType dtype, int caps2) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;

	ic->usb_control = fake_control;
	ic->usb_write = fake_write;
	ic->usb_read = fake_read;
	ic->usb_wait_io = fake_wait_io;
	ic->usb_cancel_io = fake_cancel_io;
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

/* One lit strip scan of *nread* readings, as i1pro_imp_measure makes it. */
static int armed = 0;			/* the helper arms each strip (option on) */

static void scan(i1pro *p, const char *what, int nread) {
	i1proimp *m = (i1proimp *)p->m;
	double inttime = m->min_int_time;
	int nmeas = 0;
	int maxn = 4000;
	unsigned int bsize = m->nsen * 2 * maxn;
	unsigned char *buf = (unsigned char *)malloc(bsize);
	i1pro_code ev;
	printf("%s STEP %s\n", scn, what);
	fflush(stdout);
	trig_sent = 0;
	readings_left = nread;
#ifndef CQ_BASE
	scan_over = 0;
	r_pos = 0;
	r_total = (long)nread * 136 - 5;
	if (armed)
		i1pro2_cq_ruler_arm(p, 1);
#endif
	ev = i1pro_read_patches_1(p, 10, maxn, &inttime, 0, &nmeas, buf, bsize);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	printf("%s RESULT ev=0x%x readings=%d\n", scn, ev, nmeas);
	fflush(stdout);
#ifndef CQ_BASE
	if (armed) {
		cq_ruler_rec r;
		if (i1pro2_cq_ruler_take(p, &r)) {
			printf("%s RULER ended=%d bytes=%ld samples=%ld nch=%d first=%d "
			       "readings=%d clocks=%d giveup=%d notend=%d err=0x%x state=%d\n",
			       scn, r.ended, r.bytes, r.samples, r.nch, r.first, r.readings,
			       r.clocks, r.giveup, r.stream_did_not_end, r.icom_err,
			       i1pro2_cq_ruler_state(p));
			cq_ruler_rec_clear(&r);
		} else
			printf("%s RULER none state=%d\n", scn, i1pro2_cq_ruler_state(p));
		i1pro2_cq_ruler_arm(p, 0);
		fflush(stdout);
	}
#endif
	free(buf);
}

static void life(const char *name, devType dtype) {
	i1pro *p;
	scn = name;
	p = make(dtype, dtype == instI1Pro2 ? 0x08 /* I1PRO_CAP2_ZEB_RUL */ : 0);
	scan(p, "strip-full", 570);
	scan(p, "strip-short", 140);
	scan(p, "strip-slow", 1370);
	free(p->icom);
	p->icom = NULL;
	printf("%s END\n", scn);
	fflush(stdout);
}

#ifndef CQ_BASE
/* The option on: the helper switches the ruler on for the session and arms
 * every strip. *mode* is what the fake instrument streams; the second and
 * third scans show what happens to the strips after it. */
static void ruler_life(const char *name, devType dtype, int caps2,
                       const char *mode, int lights) {
	i1pro *p;
	scn = name;
	ruler_mode = mode;
	r_reads = r_maxsize = r_cancels = r_clearhalts = 0;
	r_cancel_hit = 0;
	p = make(dtype, caps2);
	pace = 1;
	if (lights) {
		i1pro2_cq_lights_options(p, 1, 0);
		printf("%s LIGHTS %d\n", scn, i1pro2_cq_lights_begin(p));
	}
	printf("%s OPTIONS %d\n", scn, i1pro2_cq_ruler_options(p, 1));
	armed = 1;
	scan(p, "strip-1", 120);
	ruler_mode = "clean";
	scan(p, "strip-2", 120);
	scan(p, "strip-3", 120);
	armed = 0;
	pace = 0;
	printf("%s READS85 %d max=%d\n", scn, r_reads > 0, r_maxsize);
	printf("%s CLEARHALTS before close %d\n", scn, r_clearhalts);
	{
		unsigned int t0c = msec_time(), ms;
		i1pro2_cq_ruler_close(p);
		ms = msec_time() - t0c;
		printf("%s CLOSED cancels=%d within2600=%d\n", scn, r_cancels > 0,
		       ms < 2600);
	}
	if (lights)
		i1pro2_cq_lights_end(p);
	free(p->icom);
	p->icom = NULL;
	printf("%s END\n", scn);
	fflush(stdout);
}
#endif

#ifndef CQ_BASE
/* The recogniser with the ruler record open and closed: the patch values must
 * be bit for bit the same (the hooks only copy). A synthetic strip of 16
 * plateaus with sharp edges, as absolute raw values. */
static void extract_check(void) {
	i1pro *p;
	i1proimp *m;
	int n = 16, per = 30, lead = 40, nummeas = 16 * 30 + 80, i, j, k, f1 = 0, f2 = 0;
	double **mm, **pa1, **pa2;
	cq_ruler_rec r;
	scn = "extract";
	p = make(instI1Pro2, 0x08);
	m = (i1proimp *)p->m;
	m->scan_toll_ratio = 1.0;
	mm = dmatrix(0, nummeas - 1, -1, m->nraw - 1);
	pa1 = dmatrix(0, n - 1, -1, m->nraw - 1);
	pa2 = dmatrix(0, n - 1, -1, m->nraw - 1);
	for (i = 0; i < nummeas; i++) {
		int pi = (i - lead) / per;
		for (j = -1; j < m->nraw; j++) {
			double v = 9000.0;		/* paper */
			if (i >= lead && pi < n)
				v = 1500.0 + 450.0 * ((pi * 7 + j / 16) % 16);
			mm[i][j] = v + (double)((i * 31 + j * 17) % 13);
		}
	}
	i1pro2_cq_ruler_options(p, 1);
	m->cq_ruler_recording = 0;
	k = i1pro_extract_patches_multimeas(p, &f1, pa1, n, mm, nummeas, NULL, 0.0, 0.0049);
	((cq_ruler_rec *)m->cq_ruler_rec)->valid = 1;
	m->cq_ruler_recording = 1;
	j = i1pro_extract_patches_multimeas(p, &f2, pa2, n, mm, nummeas, NULL, 0.0, 0.0049);
	{
		int same = (k == j) && (f1 == f2);
		for (i = 0; i < n && same; i++)
			same = memcmp(&pa1[i][-1], &pa2[i][-1], sizeof(double) * (m->nraw + 1)) == 0;
		i1pro2_cq_ruler_take(p, &r);
		printf("%s EXTRACT ev=0x%x identical=%d ncut=%d ntrace=%d\n", scn, k, same,
		       r.ncut, r.ntrace);
		cq_ruler_rec_clear(&r);
	}
	i1pro2_cq_ruler_close(p);
	free(p->icom);
	p->icom = NULL;
	printf("%s END\n", scn);
	fflush(stdout);
}
#endif

int main(void) {
	life("off_i1pro2", instI1Pro2);
	life("off_i1pro", instI1Pro);		/* the original i1Pro (Rev A-D) */
#ifndef CQ_BASE
	extract_check();
	ruler_life("on_clean", instI1Pro2, 0x08, "clean", 0);
	ruler_life("on_none", instI1Pro2, 0x08, "none", 0);
	ruler_life("on_garbled", instI1Pro2, 0x08, "garbled", 0);
	ruler_life("on_short", instI1Pro2, 0x08, "short", 0);
	ruler_life("on_late", instI1Pro2, 0x08, "late", 0);
	ruler_life("on_error", instI1Pro2, 0x08, "error", 0);
	ruler_life("on_zero", instI1Pro2, 0x08, "zero", 0);
	ruler_life("on_noend", instI1Pro2, 0x08, "noend", 0);
	/* the reviewer's faults: nothing ever arrives (cancellable / never),
	 * a 3 MB stream, the device gone, a stream ending 200 ms late */
	ruler_life("on_stall", instI1Pro2, 0x08, "stall", 0);
	ruler_life("on_stallnc", instI1Pro2, 0x08, "stallnc", 0);
	ruler_life("on_huge", instI1Pro2, 0x08, "huge", 0);
	ruler_life("on_gone", instI1Pro2, 0x08, "gone", 0);
	ruler_life("on_late200", instI1Pro2, 0x08, "late200", 0);
	/* the measurement read fails on the armed strip */
	fail82 = 1;
	ruler_life("on_fail82", instI1Pro2, 0x08, "clean", 0);
	fail82 = 0;
	/* the reader cannot start: the bits must not go out */
	i1pro2_cq_ruler_fail_start_for_test = 1;
	ruler_life("on_failstart", instI1Pro2, 0x08, "clean", 0);
	i1pro2_cq_ruler_fail_start_for_test = 0;
	/* no ruler sensor in the EEPROM, and the original i1Pro: never */
	ruler_life("on_nosensor", instI1Pro2, 0x00, "clean", 0);
	ruler_life("on_revad", instI1Pro, 0x08, "clean", 0);
	/* with the lights on (signals): both work, independently */
	ruler_life("on_clean_lights", instI1Pro2, 0x18, "clean", 1);
	/* readings faster than the clock: the rate guard */
	{
		ruler_mode = "clean";
		scn = "on_rate";
		{
			i1pro *p = make(instI1Pro2, 0x08);
			pace = 0;
			printf("%s OPTIONS %d\n", scn, i1pro2_cq_ruler_options(p, 1));
			armed = 1;
			scan(p, "strip-1", 120);
			scan(p, "strip-2", 120);
			armed = 0;
			i1pro2_cq_ruler_close(p);
			free(p->icom);
			p->icom = NULL;
			printf("%s END\n", scn);
		}
	}
#endif
	printf("ALL DONE\n");
	return 0;
}
