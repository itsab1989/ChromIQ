/* i1io_table_dual_test: the i1Pro 2's part of an i1iO 2 DUAL ROW (2026-11-18:
 * the lamp pass forward, the UV pass straight back, as i1Profiler 3.8.6 did it
 * on the volunteer's table) and the dual tile on the table's tile, through the
 * REAL vendored driver code (native/instlib/cq_i1pro2_dual.h, section (d)) on a
 * FAKE USB layer. Nothing here touches hardware.
 *
 * Every request the driver makes is printed as one line, with the ms since
 * the scenario's fire() was entered:
 *   <scn> CTL <req> <hex payload|inN> +<ms>
 *   <scn> WR <ep> <hex> +<ms>
 *   <scn> RD <ep> <asked> -> <got> +<ms>
 *   <scn> READY <rc> wait=<ms> why=<text>
 *   <scn> FIRE rc=<rc> got=<n> dark_ev=.. lit_ev=.. dark_sent=.. lit_sent=..
 *   <scn> END
 * tests/i1io_table/test_dual_helper_wire.py reads the trace.
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
#include "cq_dual.h"

extern int i1pro2_cq_dual_noproc_for_test;

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


/* the factory tables: INVENTED numbers in the shape of the EEPROM's */
static double fake_kA[18], fake_kD[18];
static int tables_n = 18;
static double *fake_get_doubles(struct _i1data *d, unsigned int *count, i1key key) {
	(void)d;
	*count = (unsigned int)tables_n;
	if ((int)key == 0x2f77) return tables_n > 0 ? fake_kA : NULL;
	if ((int)key == 0x2f76) return tables_n > 0 ? fake_kD : NULL;
	return NULL;
}
static void fake_data_del(struct _i1data *d) { free(d); }

static i1pro *make(devType dtype, int caps2) {
	i1pro *p = (i1pro *)calloc(1, sizeof(i1pro));
	icoms *ic = (icoms *)calloc(1, sizeof(icoms));
	i1proimp *m;
	int j;
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
	m->ms[0].cal_valid = 1;
	m->ms[0].dark_valid = 1;
	m->ms[0].cfdate = time(NULL);
	m->ms[0].inttime = 139 * 36e-6;		/* the strip integration of every recording */
	m->intclkp = 36e-6;
	m->intclkp2 = 36e-6;
	m->subclkdiv2 = 136;
	m->min_int_time = 136 * 36e-6;
	m->nsen = 134;
	m->nraw = 128;
	{	/* a white reading for the dual tile's checksum (white_data[-1 .. nraw-1]) */
		double *w = (double *)calloc((size_t)m->nraw + 1, sizeof(double));
		for (j = 0; j <= m->nraw; j++)
			w[j] = 1000.0 + j;
		m->ms[0].white_data = w + 1;
	}
	m->msec = msec_time();
	m->llamponoff = msec_time() - 10000;
	m->fwrev = 634;
	for (j = 0; j < 18; j++) {
		fake_kA[j] = j >= 3 ? 1.0e-4 * (1.0 + 0.05 * j) : 0.0;
		fake_kD[j] = j >= 3 ? 1.6 * fake_kA[j] : 0.0;
	}
	m->data = (struct _i1data *)calloc(1, sizeof(struct _i1data));
	m->data->get_doubles = fake_get_doubles;
	m->data->del = fake_data_del;
	return p;
}

static void on(i1pro *p) {
	double kA[36], kD[36];
	int r = i1pro2_cq_tdual_on(p, kA, kD);
	printf("%s ON %d ruler=%d\n", scn, r, ((i1proimp *)p->m)->cq_ruler_on);
	fflush(stdout);
}

static int ready(i1pro *p, int pass, int n, int tile) {
	char why[96] = "";
	int w = -1, rc = i1pro2_cq_tdual_ready(p, pass, n, tile, &w, why, sizeof(why));
	printf("%s READY %s %d wait=%s why=%s\n", scn, pass == CQ_TDUAL_PASS_UV ? "uv" : "lamp", rc,
	       rc == 0 ? (w > 0 ? "pos" : "zero") : (w == 0 ? "0" : "x"), why[0] ? why : "-");
	fflush(stdout);
	return rc;
}

static void fire(i1pro *p, int pass, int n) {
	cq_tscan_rec r;
	int rc, vb = -9, va = -9;
	trig_sent = 0;
	t0 = msec_time();
	printf("%s STEP fire %s %d\n", scn, pass == CQ_TDUAL_PASS_UV ? "uv" : "lamp", n);
	rc = i1pro2_cq_tdual_fire(p, pass, n, 0, &r, &vb, &va);
	printf("%s FIRE rc=%d got=%d dark_ev=0x%x lit_ev=0x%x lit_sent=%d dark_sent=%d volts=%d,%d\n",
	       scn, rc, r.ngot, r.dark_ev, r.lit_ev, r.lit_sent, r.dark_sent, vb, va);
	fflush(stdout);
	cq_tscan_rec_clear(&r);
}

static void lights(i1pro *p) {
	t0 = msec_time();
	printf("%s STEP lights_off\n", scn);
	printf("%s LIGHTS %d\n", scn, i1pro2_cq_tscan_lights_off(p));
}

static void tile(i1pro *p, int save) {
	cq_dual_tile t;
	int ev;
	t0 = msec_time();
	printf("%s STEP tile\n", scn);
	ev = i1pro2_cq_dual_tile(p, &t);
	printf("%s TILE ev=%d ok=%d uv_clocks=%d lamp_clocks=%d scan=%d\n", scn, ev, t.ok,
	       t.uv_clocks, t.lamp_clocks, t.mode_scan);
	if (save)
		printf("%s SAVED %d\n", scn, i1pro2_cq_dual_tile_save(p, &t));
	fflush(stdout);
}

static void restore(i1pro *p) {
	cq_dual_tile t;
	int r = i1pro2_cq_dual_tile_restore(p, &t);
	printf("%s RESTORE %d uv_clocks=%d\n", scn, r, r ? t.uv_clocks : -1);
	fflush(stdout);
}

static void end(i1pro *p) {
	free(p->icom);
	p->icom = NULL;
	printf("%s END\n", scn);
	fflush(stdout);
}

int main(int argc, char **argv) {
	i1pro *p;
	char path[1024];
	i1pro2_cq_tscan_noproc_for_test = 1;
	i1pro2_cq_dual_noproc_for_test = 1;
	i1pro2_cq_tscan_lampoff_ms_for_test = 5;
	i1pro2_cq_tscan_lightsoff_ms_for_test = 5;
	if (argc > 1)
		snprintf(path, sizeof(path), "%s", argv[1]);
	else		/* never the working folder (the repository, under pytest) */
		snprintf(path, sizeof(path), "%s/i1io_table_dual_test.%d.cqdual",
		         getenv("TMPDIR") != NULL ? getenv("TMPDIR") : "/tmp", (int)time(NULL));
	i1pro2_cq_dual_tile_path_for_test = path;
	remove(path);

	/* the dual tile on the table's tile, kept, and taken up again */
	scn = "tile";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL);
	on(p);
	restore(p);			/* nothing kept yet */
	tile(p, 1);
	restore(p);			/* the same white: taken up */
	((i1proimp *)p->m)->ms[0].cfdate -= 5;
	restore(p);			/* another white (date): not taken up */
	((i1proimp *)p->m)->ms[0].cfdate += 5;
	restore(p);			/* the date back: taken up again */
	((i1proimp *)p->m)->ms[0].white_data[5] += 0.5;
	restore(p);			/* another white of the SAME date (its checksum): not taken up */
	end(p);

	/* one dual row: the lamp pass forward, the UV pass straight back */
	scn = "row";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL);
	on(p);
	ready(p, CQ_TDUAL_PASS_UV, 550, 1);		/* never before the lamp pass */
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 0);		/* never without a dual tile */
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);		/* no lights-off yet: never */
	lights(p); msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_LAMP, 1160, 1);	/* longer than a dual row may ask for */
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);
	msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_UV, 550, 1);
	fire(p, CQ_TDUAL_PASS_UV, 550);
	ready(p, CQ_TDUAL_PASS_UV, 550, 1);		/* one UV pass per lamp pass */
	fire(p, CQ_TDUAL_PASS_UV, 550);			/* refused: nothing sent */
	end(p);

	/* the lamp pass's lit reading fails: no UV pass may follow */
	scn = "lampfail";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL);
	on(p);
	n_rd82 = 0; fail_rd_at = 1;
	lights(p); msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);
	fail_rd_at = 0;
	ready(p, CQ_TDUAL_PASS_UV, 550, 1);
	fire(p, CQ_TDUAL_PASS_UV, 550);
	end(p);

	/* the UV trigger fails on the wire: the dark and the volts still come */
	scn = "uvfail";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL);
	on(p);
	lights(p); msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);
	msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_UV, 550, 1);
	n_d4 = 0; fail_d4_at = 1;
	fire(p, CQ_TDUAL_PASS_UV, 550);
	fail_d4_at = 0;
	end(p);

	/* SHOULD-3 R10: a fire of a pass the last ready check did not allow sends
	 * nothing (the helper refuses an unarmed fire first; this is the second line) */
	scn = "unarmed";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL);
	on(p);
	lights(p); msec_sleep(10);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);		/* no ready at all: nothing */
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_UV, 550);			/* the lamp was allowed, not the UV: nothing */
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);		/* allowed: the lamp pass */
	msec_sleep(10);
	fire(p, CQ_TDUAL_PASS_UV, 550);			/* delivered lamp, but no ready for UV: nothing */
	end(p);

	/* re-review 2026-11-19: ONE fire per yes, and a later "no" clears an earlier yes */
	scn = "onceper";
	p = make(instI1Pro2, I1PRO_CAP2_UV_LED | I1PRO_CAP2_ZEB_RUL);
	on(p);
	lights(p); msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);		/* allowed: the lamp pass */
	msec_sleep(10);
	lights(p); msec_sleep(10);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);		/* the same yes again: nothing */
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);		/* a yes ... */
	ready(p, CQ_TDUAL_PASS_LAMP, 5000, 1);		/* ... then a no (count out of range) */
	fire(p, CQ_TDUAL_PASS_LAMP, 550);		/* the earlier yes does not count: nothing */
	end(p);

	/* not a dual session (an original i1Pro, or no UV LED): nothing at all */
	scn = "revad";
	p = make(instI1Pro, I1PRO_CAP2_UV_LED);
	on(p);
	lights(p);
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);
	end(p);

	scn = "nouv";
	p = make(instI1Pro2, I1PRO_CAP2_ZEB_RUL);
	on(p);
	lights(p); msec_sleep(10);
	ready(p, CQ_TDUAL_PASS_LAMP, 550, 1);
	fire(p, CQ_TDUAL_PASS_LAMP, 550);
	end(p);

	remove(path);
	printf("ALL DONE\n");
	return 0;
}
