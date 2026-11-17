/* i1io_table_scan_test: the i1Pro 2's part of an i1iO 2 ROW SCAN (study,
 * 2026-11-16) through the REAL vendored driver code (native/instlib/
 * cq_i1pro2_tscan.h) on a FAKE USB layer. Nothing here touches hardware.
 *
 * Every request the driver makes is printed as one line, with the ms since
 * the scenario's fire() was entered:
 *   <scn> CTL <req> <hex payload|inN> +<ms>
 *   <scn> WR <ep> <hex> +<ms>
 *   <scn> RD <ep> <asked> -> <got> +<ms>
 *   <scn> READY <rc> wait=<ms> why=<text>
 *   <scn> FIRE rc=<rc> got=<n> dark_ev=.. lit_ev=.. dark_sent=.. lit_sent=..
 *   <scn> END
 * tests/test_i1io_table_scan.py reads the trace.
 * AGPL-3.0 like the rest of the helper (see ../../instlib/License.txt). */

#ifdef SALONEINSTLIB
#include "sa_config.h"
#else
#include "aconfig.h"
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
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
#include "cq_tscan.h"

static const char *scn = "?";
static unsigned int t0 = 0;
static volatile int trig_sent = 0;
static int fail_rd_at = 0, n_rd82 = 0;	/* fail the Nth 0x82 read (1-based) */
static int fail_d4_at = 0, n_d4 = 0;	/* fail the Nth 0xD4 */
static int d4_failed = 0;			/* ...then no data comes: the read times out */

static void hex(const unsigned char *b, int n) {
	int i;
	for (i = 0; i < n; i++)
		printf("%02x", b[i]);
}

static int fake_control(icoms *p, int requesttype, int request, int value,
                        int index, unsigned char *rwbuf, int rwsize,
                        int *xferred, double tout) {
	(void)p; (void)value; (void)index; (void)tout;
	printf("%s CTL %02x ", scn, request & 0xff);
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) == IUSB_ENDPOINT_OUT)
		hex(rwbuf, rwsize);
	else
		printf("in%d", rwsize);
	printf(" +%u\n", msec_time() - t0);
	fflush(stdout);
	if (xferred != NULL)
		*xferred = rwsize;
	if ((requesttype & IUSB_ENDPOINT_DIR_MASK) != IUSB_ENDPOINT_OUT && rwbuf != NULL) {
		static const unsigned char misc[8] = { 0x02, 0x7a, 0x07, 0xd0, 0xfa, 0x00, 0x01, 0x00 };
		memset(rwbuf, 0, rwsize);
		if ((request & 0xff) == 0xC9 && rwsize == 8)
			memcpy(rwbuf, misc, 8);		/* as recorded: fw 634 */
	}
	if ((request & 0xff) == 0xD4) {
		n_d4++;
		trig_sent = 1;
		if (fail_d4_at == n_d4) {
			d4_failed = 1;
			return ICOM_USBW;
		}
	}
	return ICOM_OK;
}

static int fake_write(icoms *p, usb_cancelt *c, int ep, unsigned char *wbuf,
                      int wsize, int *bwritten, double tout) {
	(void)p; (void)c; (void)tout;
	printf("%s WR %02x ", scn, ep & 0xff);
	hex(wbuf, wsize);
	printf(" +%u\n", msec_time() - t0);
	fflush(stdout);
	*bwritten = wsize;
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
	int i;
	(void)p; (void)tout;
	started(c);
	if ((ep & 0xff) == 0x82) {
		for (i = 0; !trig_sent && i < 3000; i++)
			msec_sleep(1);
		trig_sent = 0;
		n_rd82++;
		if (d4_failed) {
			d4_failed = 0;
			*bread = 0;
			printf("%s RD 82 %d -> TIMEOUT +%u\n", scn, bsize, msec_time() - t0);
			fflush(stdout);
			return ICOM_TO;
		}
		if (fail_rd_at == n_rd82) {
			*bread = 0;
			printf("%s RD 82 %d -> FAIL +%u\n", scn, bsize, msec_time() - t0);
			fflush(stdout);
			return ICOM_USBR;
		}
		msec_sleep(bsize / 268 * 5 / 10);	/* a tenth of the real time */
		memset(buf, 0, bsize);
		for (i = 0; i < bsize; i += 2)
			buf[i] = 0x10;
		*bread = bsize;
		printf("%s RD 82 %d -> %d +%u\n", scn, bsize, bsize, msec_time() - t0);
		fflush(stdout);
		return ICOM_OK;
	}
	printf("%s RD %02x %d +%u\n", scn, ep & 0xff, bsize, msec_time() - t0);
	fflush(stdout);
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
	printf("%s CANCEL\n", scn);
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
	usb_init_cancel(&m->rd_sync);
	m->mmode = 0;
	m->ms[0].reflective = 1;
	m->ms[0].scan = 1;
	m->ms[0].lamptime = 0.2;
	m->ms[0].cal_valid = 1;
	m->ms[0].cfdate = time(NULL);
	m->intclkp2 = 36e-6;
	m->subclkdiv2 = 136;
	m->min_int_time = 136 * 36e-6;
	m->nsen = 134;
	m->nraw = 128;
	m->msec = msec_time();
	m->llamponoff = msec_time() - 10000;
	m->fwrev = 634;
	return p;
}

static void ready(i1pro *p, int n) {
	char why[96] = "";
	int w = -1, rc = i1pro2_cq_tscan_ready(p, n, &w, why, sizeof(why));
	printf("%s READY %d wait=%s why=%s\n", scn, rc,
	       rc == 0 ? (w > 0 ? "pos" : "zero") : (w == 0 ? "0" : "x"), why[0] ? why : "-");
	fflush(stdout);
}

static void fire(i1pro *p, int n, int np) {
	cq_tscan_rec r;
	int rc;
	trig_sent = 0;
	t0 = msec_time();
	printf("%s STEP fire %d\n", scn, n);
	rc = i1pro2_cq_tscan_fire(p, n, np, &r);
	printf("%s FIRE rc=%d got=%d dark_ev=0x%x lit_ev=0x%x misc_ev=0x%x dark_sent=%d lit_sent=%d"
	       " ms_dark=%d ms_lit=%d ms_total=%u\n", scn, rc, r.ngot, r.dark_ev, r.lit_ev, r.misc_ev,
	       r.dark_sent, r.lit_sent, r.t_dark_trig ? (int)(r.t_dark_trig - r.t_fire) : -1,
	       r.t_lit_trig ? (int)(r.t_lit_trig - r.t_fire) : -1, msec_time() - t0);
	fflush(stdout);
	cq_tscan_rec_clear(&r);
}

static void lights(i1pro *p) {
	t0 = msec_time();
	printf("%s STEP lights_off\n", scn);
	printf("%s LIGHTS %d\n", scn, i1pro2_cq_tscan_lights_off(p));
}

static void end(i1pro *p) {
	free(p->icom);
	p->icom = NULL;
	printf("%s END\n", scn);
	fflush(stdout);
}

int main(int argc, char **argv) {
	i1pro *p;
	i1pro2_cq_tscan_noproc_for_test = 1;

	/* The byte audit against the recordings: one pass per count given,
	 * "--passes 520 680 ..." (ChromIQ-work 2026-11-16_i1io_scan_mode/tools/byte_audit.py). */
	if (argc > 2 && strcmp(argv[1], "--passes") == 0) {
		int k;
		char nm[32];
		i1pro2_cq_tscan_lampoff_ms_for_test = 5;
		i1pro2_cq_tscan_lightsoff_ms_for_test = 5;
		for (k = 2; k < argc; k++) {
			snprintf(nm, sizeof(nm), "audit%d", k - 1);
			scn = nm;
			p = make(instI1Pro2);
			lights(p);
			msec_sleep(10);
			ready(p, atoi(argv[k]));
			fire(p, atoi(argv[k]), 0);
			end(p);
		}
		printf("ALL DONE\n");
		return 0;
	}

	/* a normal pass, the waits real: armed only after the recorded spacing */
	scn = "pass";
	p = make(instI1Pro2);
	ready(p, 520);			/* no lights-off yet: never */
	lights(p);
	ready(p, 520);			/* just after the lights-off: not yet */
	msec_sleep(CQ_TSCAN_LIGHTSOFF_MS + 20);
	ready(p, 520);			/* now */
	fire(p, 520, 0);
	ready(p, 520);			/* the next pass needs its own lights-off */
	lights(p);
	msec_sleep(CQ_TSCAN_LIGHTSOFF_MS + 20);
	ready(p, 520);			/* the lamp went off just now: not yet */
	msec_sleep(CQ_TSCAN_LAMPOFF_MS);
	ready(p, 520);
	fire(p, 1190, 0);		/* the longest recorded pass */
	end(p);

	i1pro2_cq_tscan_lampoff_ms_for_test = 5;
	i1pro2_cq_tscan_lightsoff_ms_for_test = 5;

	/* the dark reading fails: the lamp trigger still goes out */
	scn = "darkfail";
	p = make(instI1Pro2);
	n_rd82 = 0; fail_rd_at = 1;
	lights(p); msec_sleep(10);
	fire(p, 520, 0);
	fail_rd_at = 0;
	end(p);

	/* the dark trigger itself fails: the lamp trigger still goes out */
	scn = "darktrigfail";
	p = make(instI1Pro2);
	n_d4 = 0; fail_d4_at = 1;
	lights(p); msec_sleep(10);
	fire(p, 520, 0);
	fail_d4_at = 0;
	end(p);

	/* the lit reading fails: reported, the status still read */
	scn = "litfail";
	p = make(instI1Pro2);
	n_rd82 = 0; fail_rd_at = 2;
	lights(p); msec_sleep(10);
	fire(p, 520, 0);
	fail_rd_at = 0;
	end(p);

	/* refusals that send NOTHING */
	scn = "range";
	p = make(instI1Pro2);
	lights(p); msec_sleep(10);
	ready(p, 5);
	ready(p, 5000);
	fire(p, 5, 0);
	fire(p, 5000, 0);
	end(p);

	scn = "notcal";
	p = make(instI1Pro2);
	((i1proimp *)p->m)->ms[0].cal_valid = 0;
	lights(p); msec_sleep(10);
	ready(p, 520);
	end(p);

	scn = "calold";
	p = make(instI1Pro2);
	((i1proimp *)p->m)->ms[0].cfdate = time(NULL) - (60 * 60 - 60);
	lights(p); msec_sleep(10);
	ready(p, 520);
	end(p);

	scn = "spotmode";
	p = make(instI1Pro2);
	((i1proimp *)p->m)->ms[0].scan = 0;
	lights(p); msec_sleep(10);
	ready(p, 520);
	end(p);

	scn = "revad";		/* an original i1Pro: nothing at all */
	p = make(instI1Pro);
	lights(p);
	ready(p, 520);
	fire(p, 520, 0);
	end(p);

	printf("ALL DONE\n");
	return 0;
}
