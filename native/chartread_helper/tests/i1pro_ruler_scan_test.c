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

static const char *scn = "?";
static volatile int trig_sent = 0;	/* the D4 / C0 trigger went out */
static int readings_left = 0;		/* readings the fake still has */
static int reading_bytes = 268;

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
		memset(buf, 0, bsize);
		for (i = 0; i < n * reading_bytes; i += 2)
			buf[i] = 0x10;		/* a flat, unsaturated level */
		*bread = n * reading_bytes;
		printf("%s RD 82 %d -> %d tout=%.2f\n", scn, bsize, *bread, tout);
		fflush(stdout);
		return *bread < bsize ? ICOM_SHORT : ICOM_OK;
	}
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
	printf("%s CANCEL\n", scn);
	fflush(stdout);
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
	ev = i1pro_read_patches_1(p, 10, maxn, &inttime, 0, &nmeas, buf, bsize);
	if (m->trig_thread != NULL) {
		m->trig_thread->del(m->trig_thread);
		m->trig_thread = NULL;
	}
	printf("%s RESULT ev=0x%x readings=%d\n", scn, ev, nmeas);
	fflush(stdout);
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

int main(void) {
	life("off_i1pro2", instI1Pro2);
	if (getenv("CQ_SCAN_REVAD") != NULL)	/* the original i1Pro (Rev A-D) */
		life("off_i1pro", instI1Pro);
	printf("ALL DONE\n");
	return 0;
}
